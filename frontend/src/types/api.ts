/** Shapes shared with the backend. Kept in one file so a schema change has one
 * place to land rather than one per view. */

import type { Citation } from '@/types/chat'

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
  has_next: boolean
  has_prev: boolean
}

export interface MessageResponse {
  message: string
}

export interface PageQuery {
  page?: number
  page_size?: number
  keyword?: string
  sort?: string
  order?: 'asc' | 'desc'
  [key: string]: unknown
}

// --- identity ---------------------------------------------------------------

export interface RoleBrief {
  id: string
  code: string
  name: string
}

export interface User {
  id: string
  username: string
  display_name: string | null
  email: string | null
  is_active: boolean
  is_superuser: boolean
  must_change_password: boolean
  last_login_at: string | null
  login_count: number
  created_at: string | null
  roles: string[]
}

export interface MenuDef {
  key: string
  title: string
  path: string
  icon: string
  perm: string | null
  children: MenuDef[]
}

export interface MeResponse {
  user: User
  roles: string[]
  permissions: string[]
  menus: MenuDef[]
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
  roles: string[]
  permissions: string[]
  menus: MenuDef[]
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  password: string
  display_name?: string | null
  email?: string | null
}

export interface ChangePasswordRequest {
  old_password: string
  new_password: string
}

export interface ProfileUpdateRequest {
  display_name?: string | null
  email?: string | null
}

export interface ForgotPasswordResponse {
  message: string
  dev_reset_token?: string | null
}

// --- administration ---------------------------------------------------------

export interface Role {
  id: string
  code: string
  name: string
  description: string | null
  is_system: boolean
  permissions: string[]
  user_count: number
  created_at: string | null
}

export interface PermissionNode {
  key: string
  title: string
  perm: string | null
  children: PermissionNode[]
}

export interface DashboardStats {
  users_total: number
  users_active: number
  users_new_7d: number
  sessions_total: number
  sessions_today: number
  messages_total: number
  terminology_total: number
  roles_total: number
  pending_reset_requests: number
  model_name: string | null
  model_provider: string | null
  ollama_online: boolean
  ollama_models: number
}

export interface SessionAdmin {
  id: string
  title: string
  language: string
  user_id: string | null
  username: string | null
  message_count: number
  created_at: string
  updated_at: string
}

export interface ConversationDetail {
  session: SessionAdmin
  messages: Array<{
    id: string
    role: string
    content: string
    language: string
    created_at: string
    citations?: Citation[]
    trace?: { query: string; hits: Citation[] } | null
  }>
}

export interface TerminologyEntry {
  id: string
  source_term: string
  target_term: string
  source_language: string
  target_language: string
  category: string | null
  definition: string | null
  aliases: string[] | null
  source_file: string | null
  created_at: string | null
}

export interface TerminologyImportResult {
  created: number
  updated: number
  skipped: number
  errors: string[]
}

export interface ResetRequest {
  id: string
  user_id: string
  username: string | null
  display_name: string | null
  status: string
  note: string | null
  created_at: string
  expires_at: string | null
  used_at: string | null
}

export interface IssueResetTokenResponse {
  token: string
  expires_at: string
  message: string
}

// --- models -----------------------------------------------------------------

export interface ModelInfo {
  name: string
  size: number
  size_label: string
  family: string | null
  parameter_size: string | null
  quantization: string | null
  modified_at: string | null
  capabilities: string[]
  context_length: number | null
  loaded: boolean
  size_vram: number
  expires_at: string | null
  is_active: boolean
  loaded_by_app: boolean
}

export interface ModelListResponse {
  active_model: string | null
  provider: string
  ollama_online: boolean
  ollama_version: string | null
  gpu_note: string | null
  models: ModelInfo[]
}

export interface PullJob {
  model: string
  status: 'running' | 'success' | 'error'
  error: string | null
  completed: number
  total: number
  percent: number
  started_at: string
  finished_at: string | null
}

export interface ModelOptionsResponse {
  active_model: string | null
  provider: string
  available: boolean
  can_switch: boolean
  models: Array<{
    name: string
    is_active: boolean
    loaded: boolean
    parameter_size: string | null
    quantization: string | null
    size_label: string
  }>
}

// --- speech -----------------------------------------------------------------

export interface SpeechCapability {
  available: boolean
  reason: string | null
  model?: string | null
  device?: string | null
  default_voice?: string | null
}

export interface VoiceOption {
  name: string
  label: string
  language: string
  gender: string
}

export interface SpeechCapabilities {
  asr: SpeechCapability
  tts: SpeechCapability
  voices: VoiceOption[]
}
