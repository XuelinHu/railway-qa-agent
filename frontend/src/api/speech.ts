/** Server-side speech, used only when the browser cannot do it itself. */

import { fetchBlob, get, upload } from '@/api/client'
import type { SpeechCapabilities, VoiceOption } from '@/types/api'

export const speechCapabilities = () => get<SpeechCapabilities>('/speech/capabilities')

export const listVoices = () => get<VoiceOption[]>('/speech/voices')

export interface Transcript {
  text: string
  language: string | null
  duration: number | null
}

/** Send a recorded clip to be transcribed. */
export function transcribe(clip: Blob, filename = 'clip.webm'): Promise<Transcript> {
  const form = new FormData()
  form.append('file', clip, filename)
  return upload<Transcript>('/speech/transcribe', form)
}

/**
 * Synthesize speech.
 *
 * Returns a blob rather than a URL so the caller owns the object URL's
 * lifetime — an `<audio src>` pointing at the endpoint would need the token in
 * a query string, which is the one place tokens leak into logs.
 */
export function synthesize(text: string, voice?: string | null, rate?: string | null): Promise<Blob> {
  return fetchBlob('/speech/synthesize', { text, voice: voice ?? null, rate: rate ?? null })
}
