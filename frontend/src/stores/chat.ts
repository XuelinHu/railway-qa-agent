import { defineStore } from 'pinia'

import { getHealth, getSessionMessages, listSessions, sendChat } from '@/api/client'
import type { ChatMessage, ChatSession, HealthResponse } from '@/types/chat'

interface ChatState {
  activeSessionId: string | null
  sessions: ChatSession[]
  messages: ChatMessage[]
  health: HealthResponse | null
  loading: boolean
  sending: boolean
  error: string | null
}

export const useChatStore = defineStore('chat', {
  state: (): ChatState => ({
    activeSessionId: null,
    sessions: [],
    messages: [],
    health: null,
    loading: false,
    sending: false,
    error: null,
  }),
  actions: {
    async refreshHealth() {
      try {
        this.health = await getHealth()
      } catch (error) {
        this.health = null
        this.error = error instanceof Error ? error.message : 'Health check failed'
      }
    },
    async loadSessions() {
      this.loading = true
      try {
        this.sessions = await listSessions()
      } catch (error) {
        this.error = error instanceof Error ? error.message : 'Unable to load sessions'
      } finally {
        this.loading = false
      }
    },
    async selectSession(sessionId: string) {
      this.activeSessionId = sessionId
      this.loading = true
      try {
        this.messages = await getSessionMessages(sessionId)
      } catch (error) {
        this.error = error instanceof Error ? error.message : 'Unable to load messages'
      } finally {
        this.loading = false
      }
    },
    startNewSession() {
      this.activeSessionId = null
      this.messages = []
      this.error = null
    },
    async submitMessage(content: string) {
      const trimmed = content.trim()
      if (!trimmed || this.sending) return

      this.error = null
      this.sending = true
      const optimistic: ChatMessage = {
        id: crypto.randomUUID(),
        session_id: this.activeSessionId ?? 'pending',
        role: 'user',
        content: trimmed,
        language: 'auto',
        created_at: new Date().toISOString(),
        pending: true,
      }
      this.messages.push(optimistic)

      try {
        const response = await sendChat({
          message: trimmed,
          session_id: this.activeSessionId,
          language: 'auto',
        })

        this.activeSessionId = response.session_id
        optimistic.session_id = response.session_id
        optimistic.pending = false

        this.messages.push({
          id: response.message_id,
          session_id: response.session_id,
          role: 'assistant',
          content: response.answer,
          language: response.language,
          created_at: new Date().toISOString(),
          citations: response.citations,
        })
        await this.loadSessions()
      } catch (error) {
        optimistic.pending = false
        this.error = error instanceof Error ? error.message : 'Message failed'
      } finally {
        this.sending = false
      }
    },
  },
})

