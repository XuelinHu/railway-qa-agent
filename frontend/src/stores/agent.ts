/**
 * The conversation the agent panel and the full-page chat both render.
 *
 * One store rather than one per surface: the floating widget on an admin page
 * and the chat page are the same conversation, so opening the panel mid-thread
 * continues it instead of starting over.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as agentApi from '@/api/agent'
import { useSse } from '@/composables/useSse'
import type { ChatMessage, ChatSession } from '@/types/chat'
import type { Citation } from '@/types/chat'

/** Fired when an answer finishes or fails, so the panel can react (speak it). */
type AnswerListener = (message: ChatMessage) => void

export const useAgentStore = defineStore('agent', () => {
  const sessions = ref<ChatSession[]>([])
  const activeSessionId = ref<string | null>(null)
  const messages = ref<ChatMessage[]>([])
  const loadingSessions = ref(false)
  const loadingMessages = ref(false)
  const sending = ref(false)
  const error = ref<string | null>(null)

  const sse = useSse()
  const listeners = new Set<AnswerListener>()

  const streaming = computed(() => sse.active.value)
  const activeSession = computed(
    () => sessions.value.find((item) => item.id === activeSessionId.value) ?? null,
  )

  /** Subscribe to finished answers. Returns an unsubscribe function. */
  function onAnswer(listener: AnswerListener): () => void {
    listeners.add(listener)
    return () => listeners.delete(listener)
  }

  function announce(message: ChatMessage): void {
    for (const listener of listeners) listener(message)
  }

  async function loadSessions(): Promise<void> {
    loadingSessions.value = true
    try {
      sessions.value = await agentApi.listSessions()
    } catch (err) {
      error.value = err instanceof Error ? err.message : '无法加载会话列表'
    } finally {
      loadingSessions.value = false
    }
  }

  async function selectSession(sessionId: string): Promise<void> {
    if (sending.value) return
    activeSessionId.value = sessionId
    loadingMessages.value = true
    try {
      messages.value = await agentApi.getSessionMessages(sessionId)
      error.value = null
    } catch (err) {
      error.value = err instanceof Error ? err.message : '无法加载会话内容'
    } finally {
      loadingMessages.value = false
    }
  }

  function startNewSession(): void {
    stop()
    activeSessionId.value = null
    messages.value = []
    error.value = null
  }

  /** Stop an answer that is still arriving. The server keeps what it produced. */
  function stop(): void {
    sse.abort()
    sending.value = false
    const last = messages.value[messages.value.length - 1]
    if (last?.streaming) last.streaming = false
  }

  /**
   * Ask a question and stream the answer into the thread.
   *
   * The user's turn and the agent's are both added up front so the panel shows
   * the question immediately and the answer grows in place, rather than the
   * screen going blank until the first token arrives.
   */
  async function ask(text: string): Promise<void> {
    const question = text.trim()
    if (!question || sending.value) return

    error.value = null
    sending.value = true

    const userMessage: ChatMessage = {
      id: `local-${crypto.randomUUID()}`,
      session_id: activeSessionId.value ?? 'pending',
      role: 'user',
      content: question,
      language: 'auto',
      created_at: new Date().toISOString(),
    }
    const answer: ChatMessage = {
      id: `local-${crypto.randomUUID()}`,
      session_id: activeSessionId.value ?? 'pending',
      role: 'assistant',
      content: '',
      language: 'auto',
      created_at: new Date().toISOString(),
      streaming: true,
      citations: [],
    }
    messages.value.push(userMessage, answer)

    const finish = (): void => {
      answer.streaming = false
      sending.value = false
      announce(answer)
    }

    await sse.run('/agent/chat/stream', {
      message: question,
      session_id: activeSessionId.value,
      language: 'auto',
    }, (event, data) => {
      switch (event) {
        case 'meta':
          activeSessionId.value = data.session_id
          userMessage.session_id = data.session_id
          answer.session_id = data.session_id
          answer.language = data.language ?? 'auto'
          break
        case 'retrieval':
          answer.citations = (data.citations ?? []) as Citation[]
          break
        case 'thinking':
          answer.thinking = (answer.thinking ?? '') + (data.text ?? '')
          break
        case 'delta':
          answer.content += data.text ?? ''
          break
        case 'error':
          answer.error = data.detail ?? '生成回答时出错'
          break
        case 'done':
          if (data.message_id) answer.id = data.message_id
          finish()
          break
      }
    })

    // A stream that ended without a `done` — a dropped connection, or a stop
    // the viewer asked for — still leaves a message worth keeping.
    if (answer.streaming) {
      if (sse.error.value) answer.error = sse.error.value
      finish()
    }
    void loadSessions()
  }

  return {
    sessions,
    activeSessionId,
    activeSession,
    messages,
    loadingSessions,
    loadingMessages,
    sending,
    streaming,
    error,
    loadSessions,
    selectSession,
    startNewSession,
    stop,
    ask,
    onAnswer,
  }
})
