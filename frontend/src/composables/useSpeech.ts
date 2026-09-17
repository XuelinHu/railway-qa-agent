/**
 * Voice in and voice out, browser first with a server fallback.
 *
 * The browser path (`speechSynthesis`, `SpeechRecognition`) is instant and
 * costs nothing, so it is always preferred. It is not always there: Firefox
 * ships no recogniser, and any page served over plain HTTP on a public address
 * is refused the microphone outright, because capture requires a secure
 * context. In those cases the server's own models take over — when they are
 * installed, which the backend reports rather than pretends.
 *
 * State is shared between every caller: the floating widget, the settings
 * panel and the chat page are all looking at the same microphone.
 */

import { computed, ref } from 'vue'

import { speechCapabilities, synthesize, transcribe } from '@/api/speech'
import type { SpeechCapabilities } from '@/types/api'

export type SpeechStatus = 'idle' | 'listening' | 'thinking' | 'speaking'

// --- minimal Web Speech typings ------------------------------------------
// The DOM lib does not declare these consistently across browsers, and only a
// corner of the API is used, so the shape is declared here rather than pulled
// in as a dependency.

interface RecognitionAlternative {
  transcript: string
}
interface RecognitionResult {
  readonly length: number
  isFinal: boolean
  [index: number]: RecognitionAlternative
}
interface RecognitionResultList {
  readonly length: number
  [index: number]: RecognitionResult
}
interface RecognitionEvent {
  resultIndex: number
  results: RecognitionResultList
}
interface RecognitionErrorEvent {
  error: string
}
interface Recognition {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number
  start(): void
  stop(): void
  abort(): void
  onresult: ((event: RecognitionEvent) => void) | null
  onerror: ((event: RecognitionErrorEvent) => void) | null
  onend: (() => void) | null
}
type RecognitionConstructor = new () => Recognition

function recognitionConstructor(): RecognitionConstructor | null {
  const scope = window as unknown as {
    SpeechRecognition?: RecognitionConstructor
    webkitSpeechRecognition?: RecognitionConstructor
  }
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition ?? null
}

// --- persisted preferences ------------------------------------------------

const STORAGE_KEY = 'railway.speech'

interface Preferences {
  autoSpeak: boolean
  continuous: boolean
  voice: string | null
  rate: number
}

function readPreferences(): Preferences {
  const fallback: Preferences = { autoSpeak: true, continuous: false, voice: null, rate: 0 }
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? { ...fallback, ...(JSON.parse(raw) as Partial<Preferences>) } : fallback
  } catch {
    // A browser with site data blocked still gets working defaults.
    return fallback
  }
}

function writePreferences(value: Preferences): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
  } catch {
    // Not being able to remember the choice is not a reason to fail the action.
  }
}

// --- shared state ---------------------------------------------------------

const preferences = readPreferences()

const status = ref<SpeechStatus>('idle')
/** Live partial transcript, shown while the viewer is still speaking. */
const interim = ref('')
const error = ref<string | null>(null)
const autoSpeak = ref(preferences.autoSpeak)
const continuous = ref(preferences.continuous)
const voiceName = ref<string | null>(preferences.voice)
const rate = ref(preferences.rate)
const capabilities = ref<SpeechCapabilities | null>(null)
const conversationActive = ref(false)

let recogniser: Recognition | null = null
let recorder: MediaRecorder | null = null
let recordingChunks: Blob[] = []
let recorderStream: MediaStream | null = null
let utterance: SpeechSynthesisUtterance | null = null
let player: HTMLAudioElement | null = null
let resolveSpeech: (() => void) | null = null
let onFinalText: ((text: string) => void) | null = null

function persist(): void {
  writePreferences({
    autoSpeak: autoSpeak.value,
    continuous: continuous.value,
    voice: voiceName.value,
    rate: rate.value,
  })
}

// --- capability detection -------------------------------------------------

const hasSynthesis = typeof window !== 'undefined' && 'speechSynthesis' in window
const hasRecorder = typeof window !== 'undefined' && 'MediaRecorder' in window
const hasRecognition = recognitionConstructor() !== null

/**
 * Microphone capture — for the recogniser and for recording alike — is only
 * allowed in a secure context. This is a browser rule, not something the app
 * can opt out of, so it is reported plainly instead of failing on click.
 */
const secureContext = typeof window !== 'undefined' && window.isSecureContext

const canUseMicrophone = computed(() => secureContext && (hasRecognition || hasRecorder))

const ttsMode = computed<'browser' | 'server' | 'none'>(() => {
  if (hasSynthesis) return 'browser'
  return capabilities.value?.tts.available ? 'server' : 'none'
})

const asrMode = computed<'browser' | 'server' | 'none'>(() => {
  if (!secureContext) return 'none'
  if (hasRecognition) return 'browser'
  if (hasRecorder && capabilities.value?.asr.available) return 'server'
  return 'none'
})

const microphoneHint = computed<string | null>(() => {
  if (asrMode.value !== 'none') return null
  if (!secureContext) {
    return '当前为非安全上下文，浏览器会拒绝麦克风。请改用 https:// 或 http://localhost 访问'
  }
  if (!hasRecognition && !hasRecorder) {
    return '当前浏览器不支持录音，请使用 Chrome、Edge 或新版 Safari'
  }
  return capabilities.value?.asr.reason ?? '语音识别不可用'
})

const speakingHint = computed<string | null>(() => {
  if (ttsMode.value !== 'none') return null
  return capabilities.value?.tts.reason ?? '语音播报不可用'
})

// --- server capabilities --------------------------------------------------

const capabilitiesRequested = ref(false)

/** Ask the server what it can do. Failure is reported, never thrown. */
async function loadCapabilities(): Promise<void> {
  if (capabilitiesRequested.value) return
  capabilitiesRequested.value = true
  try {
    capabilities.value = await speechCapabilities()
    if (!voiceName.value) voiceName.value = capabilities.value.tts.default_voice ?? null
  } catch (err) {
    error.value = err instanceof Error ? err.message : '无法获取语音能力'
  }
}

// --- speaking -------------------------------------------------------------

function languageOf(text: string): 'zh' | 'en' {
  return /[一-鿿]/.test(text) ? 'zh' : 'en'
}

function pickBrowserVoice(text: string): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis.getVoices()
  if (voices.length === 0) return null
  const prefix = languageOf(text)
  return (
    voices.find((voice) => voice.lang.toLowerCase().startsWith(prefix)) ??
    voices.find((voice) => voice.lang.toLowerCase().startsWith('zh')) ??
    null
  )
}

/** Play a synthesized clip. Resolves when it ends or is stopped. */
function playBlob(blob: Blob): Promise<void> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)
    player = audio
    const done = (): void => {
      URL.revokeObjectURL(url)
      if (player === audio) player = null
      resolve()
    }
    audio.onended = done
    audio.onerror = done
    audio.play().catch(() => {
      error.value = '浏览器阻止了自动播放，请先点击页面任意位置'
      done()
    })
  })
}

async function speakWithBrowser(text: string): Promise<void> {
  await new Promise<void>((resolve) => {
    const item = new SpeechSynthesisUtterance(text)
    const voice = pickBrowserVoice(text)
    if (voice) item.voice = voice
    item.lang = voice?.lang ?? (languageOf(text) === 'zh' ? 'zh-CN' : 'en-US')
    item.rate = Math.min(10, Math.max(0.1, 1 + rate.value / 100))
    utterance = item
    resolveSpeech = resolve
    item.onend = () => {
      if (utterance === item) utterance = null
      resolveSpeech = null
      resolve()
    }
    // A browser that has no usable voice fires `error` rather than `end`; the
    // caller falls back to the server on a rejection it can see.
    item.onerror = () => {
      if (utterance === item) utterance = null
      resolveSpeech = null
      resolve()
    }
    window.speechSynthesis.speak(item)
  })
}

/**
 * Read `text` aloud, browser first, server second.
 *
 * Resolves when playback finishes, so a hands-free loop can wait for it — and
 * resolves early when the viewer interrupts, which is what makes barge-in feel
 * immediate rather than queued.
 */
async function speak(text: string): Promise<void> {
  const trimmed = text.trim()
  if (!trimmed || ttsMode.value === 'none') return
  stopSpeaking()
  error.value = null
  status.value = 'speaking'
  try {
    if (ttsMode.value === 'browser') {
      await speakWithBrowser(trimmed)
    } else {
      await playBlob(await synthesize(trimmed, voiceName.value, formatRate()))
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '语音播报失败'
  } finally {
    if (status.value === 'speaking') status.value = 'idle'
  }
}

function formatRate(): string {
  const value = Math.round(rate.value)
  return `${value >= 0 ? '+' : ''}${value}%`
}

/** Stop playback immediately, resolving any pending `speak`. */
function stopSpeaking(): void {
  if (utterance) {
    window.speechSynthesis.cancel()
    utterance = null
  }
  if (player) {
    player.pause()
    player = null
  }
  resolveSpeech?.()
  resolveSpeech = null
  if (status.value === 'speaking') status.value = 'idle'
}

// --- listening ------------------------------------------------------------

function stopRecorder(): void {
  if (recorder && recorder.state !== 'inactive') recorder.stop()
  recorder = null
  recorderStream?.getTracks().forEach((track) => track.stop())
  recorderStream = null
}

function stopListening(): void {
  if (recogniser) {
    recogniser.onresult = null
    recogniser.onerror = null
    recogniser.onend = null
    recogniser.abort()
    recogniser = null
  }
  stopRecorder()
  interim.value = ''
  if (status.value === 'listening') status.value = 'idle'
}

function startBrowserRecognition(): void {
  const Constructor = recognitionConstructor()
  if (!Constructor) return

  const instance = new Constructor()
  instance.lang = 'zh-CN'
  instance.continuous = true
  instance.interimResults = true
  instance.maxAlternatives = 1

  instance.onresult = (event) => {
    let finalText = ''
    let pending = ''
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const result = event.results[index]
      const text = result[0]?.transcript ?? ''
      if (result.isFinal) finalText += text
      else pending += text
    }
    interim.value = pending
    if (finalText.trim()) {
      interim.value = ''
      onFinalText?.(finalText.trim())
    }
  }

  instance.onerror = (event) => {
    if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
      error.value = '麦克风权限被拒绝，请在浏览器地址栏允许后重试'
      conversationActive.value = false
    } else if (event.error !== 'aborted' && event.error !== 'no-speech') {
      error.value = `语音识别失败：${event.error}`
    }
  }

  // Chrome ends the session after a pause; in hands-free mode it is restarted
  // so the viewer does not have to press the button again.
  instance.onend = () => {
    if (recogniser !== instance) return
    recogniser = null
    interim.value = ''
    if (conversationActive.value && status.value === 'listening') {
      window.setTimeout(() => {
        if (conversationActive.value) startListening()
      }, 250)
    } else if (status.value === 'listening') {
      status.value = 'idle'
    }
  }

  recogniser = instance
  instance.start()
}

function startServerRecognition(): void {
  navigator.mediaDevices
    .getUserMedia({ audio: true })
    .then((stream) => {
      recorderStream = stream
      recordingChunks = []
      const instance = new MediaRecorder(stream)
      recorder = instance

      instance.ondataavailable = (event) => {
        if (event.data.size > 0) recordingChunks.push(event.data)
      }
      instance.onstop = async () => {
        const clip = new Blob(recordingChunks, { type: instance.mimeType || 'audio/webm' })
        recordingChunks = []
        stream.getTracks().forEach((track) => track.stop())
        recorderStream = null
        if (clip.size === 0) {
          status.value = 'idle'
          return
        }
        status.value = 'thinking'
        try {
          const result = await transcribe(clip)
          status.value = 'idle'
          onFinalText?.(result.text.trim())
        } catch (err) {
          status.value = 'idle'
          error.value = err instanceof Error ? err.message : '语音识别失败'
        }
      }
      instance.start()
    })
    .catch((err: unknown) => {
      status.value = 'idle'
      error.value =
        err instanceof Error && err.name === 'NotAllowedError'
          ? '麦克风权限被拒绝，请在浏览器地址栏允许后重试'
          : '无法访问麦克风'
      conversationActive.value = false
    })
}

/** Begin listening. Recognised speech is delivered to the last `onFinal`. */
function startListening(): void {
  if (asrMode.value === 'none') {
    error.value = microphoneHint.value
    return
  }
  stopSpeaking()
  stopListening()
  error.value = null
  interim.value = ''
  status.value = 'listening'
  if (asrMode.value === 'browser') startBrowserRecognition()
  else startServerRecognition()
}

function toggleListening(): void {
  if (status.value === 'listening') {
    conversationActive.value = false
    stopListening()
  } else {
    startListening()
  }
}

// --- hands-free conversation ---------------------------------------------

/**
 * Keep a conversation going without touching the screen.
 *
 * Barge-in here means pressing the microphone while the answer is being read:
 * with the microphone open the recogniser would otherwise hear the playback
 * and transcribe it back as a question. Always-on interruption detection
 * needs echo cancellation the browser does not reliably give us, so the button
 * is the interrupt — and it stops the audio on the same tick, which is what
 * makes it feel like one.
 */
function startConversation(deliver: (text: string) => void): void {
  onFinalText = deliver
  conversationActive.value = true
  startListening()
}

/**
 * Route recognised speech somewhere without opening the microphone yet.
 *
 * The panel calls this as soon as it is on screen so the ordinary
 * press-to-talk button works, and only turns on the hands-free loop when the
 * viewer asks for it.
 */
function setOnFinalText(deliver: ((text: string) => void) | null): void {
  onFinalText = deliver
}

function stopConversation(): void {
  conversationActive.value = false
  onFinalText = null
  stopListening()
  stopSpeaking()
}

function setAutoSpeak(value: boolean): void {
  autoSpeak.value = value
  if (!value) stopSpeaking()
  persist()
}

function setContinuous(value: boolean): void {
  continuous.value = value
  if (!value) stopConversation()
  persist()
}

function setVoice(name: string | null): void {
  voiceName.value = name
  persist()
}

function setRate(value: number): void {
  rate.value = value
  persist()
}

/** Release the microphone and any audio; call when the panel closes. */
function shutdown(): void {
  stopConversation()
}

export function useSpeech() {
  return {
    status,
    interim,
    error,
    autoSpeak,
    continuous,
    voiceName,
    rate,
    capabilities,
    conversationActive,
    ttsMode,
    asrMode,
    canUseMicrophone,
    microphoneHint,
    speakingHint,
    secureContext,
    loadCapabilities,
    speak,
    stopSpeaking,
    startListening,
    stopListening,
    toggleListening,
    startConversation,
    stopConversation,
    setOnFinalText,
    setAutoSpeak,
    setContinuous,
    setVoice,
    setRate,
    shutdown,
  }
}
