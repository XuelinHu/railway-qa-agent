export interface Citation {
  source_file?: string | null
  heading?: string | null
  chunk_index?: number | null
  text: string
  score?: number | null
  kind: string
}

export interface ChatRequest {
  message: string
  session_id?: string | null
  language?: 'auto' | 'zh' | 'en' | null
}

export interface ChatResponse {
  session_id: string
  message_id: string
  answer: string
  language: string
  citations: Citation[]
}

export interface ChatSession {
  id: string
  user_id?: string | null
  title: string
  language: string
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant' | string
  content: string
  language: string
  created_at: string
  citations?: Citation[]
  pending?: boolean
  /** Answer still arriving; the bubble shows a caret while true. */
  streaming?: boolean
  /** Reasoning text from a thinking model, rendered collapsed. */
  thinking?: string | null
  /** Set when generation failed; `content` may still hold a partial answer. */
  error?: string | null
}

export interface HealthResponse {
  status: string
  app: string
  environment: string
}

