/** Administration console endpoints. Every collection returns a `Page`. */

import { del, get, patch, post, put, query, upload } from '@/api/client'
import type {
  ConversationDetail,
  DashboardStats,
  IssueResetTokenResponse,
  MessageResponse,
  Page,
  PageQuery,
  PermissionNode,
  ResetRequest,
  Role,
  SessionAdmin,
  TerminologyEntry,
  TerminologyImportResult,
  User,
} from '@/types/api'

// --- dashboard --------------------------------------------------------------

export const dashboardStats = () => get<DashboardStats>('/admin/stats')

// --- users ------------------------------------------------------------------

export interface UserQuery extends PageQuery {
  is_active?: boolean | null
  role_code?: string | null
}

export const listUsers = (params: UserQuery) =>
  get<Page<User>>(`/admin/users${query(params)}`)

export const createUser = (payload: Record<string, unknown>) =>
  post<User>('/admin/users', payload)

export const updateUser = (id: string, payload: Record<string, unknown>) =>
  patch<User>(`/admin/users/${id}`, payload)

export const deleteUser = (id: string) => del<MessageResponse>(`/admin/users/${id}`)

export const assignRoles = (id: string, roleCodes: string[]) =>
  put<User>(`/admin/users/${id}/roles`, { role_codes: roleCodes })

export const resetUserPassword = (id: string, newPassword: string, requireChange: boolean) =>
  post<MessageResponse>(`/admin/users/${id}/reset-password`, {
    new_password: newPassword,
    require_change: requireChange,
  })

export const listResetRequests = () => get<ResetRequest[]>('/admin/users/reset-requests')

export const issueResetToken = (requestId: string) =>
  post<IssueResetTokenResponse>(`/admin/users/reset-requests/${requestId}/issue`)

// --- roles ------------------------------------------------------------------

export const listRoles = (params: PageQuery) =>
  get<Page<Role>>(`/admin/roles${query(params)}`)

export const listPermissions = () => get<PermissionNode[]>('/admin/roles/permissions')

export const createRole = (payload: Record<string, unknown>) =>
  post<Role>('/admin/roles', payload)

export const updateRole = (id: string, payload: Record<string, unknown>) =>
  patch<Role>(`/admin/roles/${id}`, payload)

export const setRolePermissions = (id: string, permissions: string[]) =>
  put<Role>(`/admin/roles/${id}/permissions`, { permissions })

export const deleteRole = (id: string) => del<MessageResponse>(`/admin/roles/${id}`)

// --- conversations ----------------------------------------------------------

export interface SessionQuery extends PageQuery {
  user_id?: string | null
  language?: string | null
  created_from?: string | null
  created_to?: string | null
}

export const listSessions = (params: SessionQuery) =>
  get<Page<SessionAdmin>>(`/admin/sessions${query(params)}`)

/** The message list inside a conversation is paginated too. */
export const getConversation = (id: string, params: PageQuery = {}) =>
  get<ConversationDetail>(`/admin/sessions/${id}${query(params)}`)

export const deleteSession = (id: string) =>
  del<MessageResponse>(`/admin/sessions/${id}`)

// --- terminology ------------------------------------------------------------

export interface TerminologyQuery extends PageQuery {
  category?: string | null
  source_language?: string | null
}

export const listTerminology = (params: TerminologyQuery) =>
  get<Page<TerminologyEntry>>(`/admin/terminology${query(params)}`)

export const terminologyCategories = () => get<string[]>('/admin/terminology/categories')

export const createTerminology = (payload: Record<string, unknown>) =>
  post<TerminologyEntry>('/admin/terminology', payload)

export const updateTerminology = (id: string, payload: Record<string, unknown>) =>
  patch<TerminologyEntry>(`/admin/terminology/${id}`, payload)

export const deleteTerminology = (id: string) =>
  del<MessageResponse>(`/admin/terminology/${id}`)

export const importTerminology = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return upload<TerminologyImportResult>('/admin/terminology/import', form)
}
