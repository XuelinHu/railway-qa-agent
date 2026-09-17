/**
 * Who is signed in, and what they may do.
 *
 * The access token itself lives in the API client, not here — the store only
 * holds the identity the server reported, so a component never has to know how
 * authentication is transported.
 */

import { defineStore } from 'pinia'

import * as authApi from '@/api/auth'
import {
  refreshAccessToken,
  setAccessToken,
  setUnauthorizedHandler,
} from '@/api/client'
import type {
  LoginRequest,
  MenuDef,
  RegisterRequest,
  TokenResponse,
  User,
} from '@/types/api'

interface AuthState {
  user: User | null
  roles: string[]
  permissions: string[]
  menus: MenuDef[]
  /** True until the initial "is there a session?" check has finished. */
  initialising: boolean
  ready: boolean
  error: string | null
}

function applyToken(state: AuthState, payload: TokenResponse): void {
  setAccessToken(payload.access_token)
  state.user = payload.user
  state.roles = payload.roles
  state.permissions = payload.permissions
  state.menus = payload.menus
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    user: null,
    roles: [],
    permissions: [],
    menus: [],
    initialising: true,
    ready: false,
    error: null,
  }),

  getters: {
    isAuthenticated: (state) => state.user !== null,
    isSuperuser: (state) => state.user?.is_superuser ?? false,
    displayName: (state) => state.user?.display_name || state.user?.username || '',
    /** True when the account must pick a new password before anything else. */
    mustChangePassword: (state) => state.user?.must_change_password ?? false,
  },

  actions: {
    /** Permission check used by the router guard and by menu rendering. */
    can(permission: string | null | undefined): boolean {
      if (!permission) return true
      if (this.user?.is_superuser) return true
      return this.permissions.includes(permission)
    },

    canAny(permissions: string[]): boolean {
      return permissions.some((permission) => this.can(permission))
    },

    /**
     * Restore a session after a reload.
     *
     * The access token is never persisted, so this trades the HttpOnly refresh
     * cookie for a new one. A failure here is the ordinary "not signed in"
     * case, not an error worth showing.
     */
    async bootstrap(): Promise<void> {
      this.initialising = true
      try {
        if (await refreshAccessToken()) {
          const me = await authApi.me()
          this.user = me.user
          this.roles = me.roles
          this.permissions = me.permissions
          this.menus = me.menus
        }
      } catch {
        setAccessToken(null)
        this.user = null
      } finally {
        this.initialising = false
        this.ready = true
      }
    },

    async login(payload: LoginRequest): Promise<void> {
      this.error = null
      applyToken(this, await authApi.login(payload))
    },

    async register(payload: RegisterRequest): Promise<User> {
      this.error = null
      return await authApi.register(payload)
    },

    async logout(): Promise<void> {
      try {
        await authApi.logout()
      } catch {
        // The local session is cleared either way: if the server call failed,
        // the refresh token expires on its own.
      }
      this.clear()
    },

    /** Re-read the identity, e.g. after changing a profile field. */
    async refreshIdentity(): Promise<void> {
      const me = await authApi.me()
      this.user = me.user
      this.roles = me.roles
      this.permissions = me.permissions
      this.menus = me.menus
    },

    setUser(user: User): void {
      this.user = user
    },

    clear(): void {
      setAccessToken(null)
      this.user = null
      this.roles = []
      this.permissions = []
      this.menus = []
    },

    /** Wire the client's "refresh failed" signal to this store. */
    installUnauthorizedHandler(onExpired: () => void): void {
      setUnauthorizedHandler(() => {
        this.clear()
        onExpired()
      })
    },
  },
})
