/** Conversations with the agent, streaming and otherwise. */

import { get, post, stream } from '@/api/client'
import type { ChatMessage, ChatResponse, ChatSession, HealthResponse } from '@/types/chat'
import type { Citation } from '@/types/chat'

export const getHealth = () => get<HealthResponse>('/health')

export const listSessions = () => get<ChatSession[]>('/chat/sessions')

export const getSessionMessages = (sessionId: string) =>
  get<ChatMessage[]>(`/chat/sessions/${sessionId}`)

/** The non-streaming path, kept for callers that cannot read a stream. */
export const sendChat = (payload: { message: string; session_id?: string | null }) =>
  post<ChatResponse>('/chat', { ...payload, language: 'auto' })

export interface StreamCallbacks {
  /** The server assigned a session; fires before any text arrives. */
  onMeta?: (meta: { session_id: string; language: string; model: string | null }) => void
  /** Retrieval finished; these are the sources the answer will cite. */
  onRetrieval?: (citations: Citation[]) => void
  /** Reasoning text from a thinking model, shown collapsed. */
  onThinking?: (text: string) => void
  onDelta?: (text: string) => void
  onError?: (detail: string) => void
  onDone?: (result: { message_id: string | null; session_id: string; partial: boolean }) => void
  signal?: AbortSignal
}

/**
 * Ask a question and stream the answer back.
 *
 * `error` is not the end of the story: text that arrived before it is kept and
 * `done` still follows, so a partial answer is rendered with a warning rather
 * than thrown away.
 */
export function streamChat(
  payload: { message: string; session_id?: string | null; language?: string },
  callbacks: StreamCallbacks,
): Promise<void> {
  return stream('/agent/chat/stream', { ...payload, language: payload.language ?? 'auto' }, {
    signal: callbacks.signal,
    onEvent: (event, data) => {
      switch (event) {
        case 'meta':
          callbacks.onMeta?.(data)
          break
        case 'retrieval':
          callbacks.onRetrieval?.(data.citations ?? [])
          break
        case 'thinking':
          callbacks.onThinking?.(data.text ?? '')
          break
        case 'delta':
          callbacks.onDelta?.(data.text ?? '')
          break
        case 'error':
          callbacks.onError?.(data.detail ?? '生成回答时出错')
          break
        case 'done':
          callbacks.onDone?.(data)
          break
      }
    },
  })
}
