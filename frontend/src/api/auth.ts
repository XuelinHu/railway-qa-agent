import { get, post, patch } from '@/api/client'
import type {
  ChangePasswordRequest,
  ForgotPasswordResponse,
  LoginRequest,
  MeResponse,
  MessageResponse,
  ProfileUpdateRequest,
  RegisterRequest,
  TokenResponse,
  User,
} from '@/types/api'

/** login and register must not trigger the refresh-and-retry path: a 401 there
 * means the credentials were wrong, not that the token expired. */
const noRetry = { retryOnUnauthorized: false }

export const login = (payload: LoginRequest) =>
  post<TokenResponse>('/auth/login', payload, noRetry)

export const register = (payload: RegisterRequest) =>
  post<User>('/auth/register', payload, noRetry)

export const logout = () => post<MessageResponse>('/auth/logout', undefined, noRetry)

export const me = () => get<MeResponse>('/auth/me')

export const updateProfile = (payload: ProfileUpdateRequest) =>
  patch<User>('/auth/profile', payload)

export const changePassword = (payload: ChangePasswordRequest) =>
  post<MessageResponse>('/auth/change-password', payload)

export const forgotPassword = (username: string) =>
  post<ForgotPasswordResponse>('/auth/forgot-password', { username }, noRetry)

export const resetPassword = (token: string, newPassword: string) =>
  post<MessageResponse>(
    '/auth/reset-password',
    { token, new_password: newPassword },
    noRetry,
  )
