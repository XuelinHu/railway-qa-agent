/**
 * The single place the app talks HTTP.
 *
 * Two decisions worth knowing about:
 *
 * 1. The access token is held in memory only, never in localStorage. It is
 *    recovered on page load by trading the HttpOnly refresh cookie for a new
 *    one, so a reload keeps you signed in without a token that any script on
 *    the page could read.
 * 2. A 401 triggers exactly one refresh and one retry, shared between all
 *    callers. Without the shared promise, a screen issuing six requests at once
 *    would fire six refreshes and invalidate its own tokens.
 */

import type { TokenResponse } from '@/types/api'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

let accessToken: string | null = null
let refreshInFlight: Promise<boolean> | null = null

/** Called by the auth store; the client never persists the token itself. */
export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

/** Notified when refreshing fails, so the app can send the user to sign in. */
type UnauthorizedHandler = () => void
let onUnauthorized: UnauthorizedHandler | null = null

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorized = handler
}

function authHeaders(): Record<string, string> {
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : {}
}

async function readError(response: Response): Promise<ApiError> {
  let detail = `请求失败（${response.status}）`
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string') {
      detail = body.detail
    } else if (Array.isArray(body?.detail)) {
      // FastAPI validation errors arrive as a list of {loc, msg}.
      detail = body.detail.map((item: { msg?: string }) => item.msg ?? '').join('；')
    }
  } catch {
    // A body that is not JSON leaves the status-based message in place.
  }
  return new ApiError(response.status, detail)
}

async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight

  refreshInFlight = (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      })
      if (!response.ok) return false
      const data = (await response.json()) as TokenResponse
      accessToken = data.access_token
      return true
    } catch {
      return false
    } finally {
      // Cleared on the next tick so concurrent callers join this attempt
      // rather than starting their own.
      setTimeout(() => {
        refreshInFlight = null
      }, 0)
    }
  })()

  return refreshInFlight
}

export interface RequestOptions extends RequestInit {
  /** Set false for endpoints that must not trigger a refresh, e.g. login. */
  retryOnUnauthorized?: boolean
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { retryOnUnauthorized = true, ...init } = options

  const send = (): Promise<Response> =>
    fetch(`${API_BASE_URL}${path}`, {
      ...init,
      credentials: 'include',
      headers: {
        ...(init.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
        ...authHeaders(),
        ...((init.headers as Record<string, string>) ?? {}),
      },
    })

  let response = await send()

  if (response.status === 401 && retryOnUnauthorized) {
    if (await refreshAccessToken()) {
      response = await send()
    } else {
      accessToken = null
      onUnauthorized?.()
    }
  }

  if (!response.ok) throw await readError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const get = <T>(path: string, options?: RequestOptions) =>
  request<T>(path, { ...options, method: 'GET' })

export const post = <T>(path: string, body?: unknown, options?: RequestOptions) =>
  request<T>(path, {
    ...options,
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  })

export const patch = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'PATCH', body: JSON.stringify(body ?? {}) })

export const put = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'PUT', body: JSON.stringify(body ?? {}) })

export const del = <T>(path: string) => request<T>(path, { method: 'DELETE' })

/** Build a query string, dropping empty values so the URL stays readable. */
export function query(params: Record<string, unknown>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

export { refreshAccessToken }

// --- streaming --------------------------------------------------------------

export interface SseHandlers {
  /** One call per event; `data` is the parsed JSON payload. */
  onEvent: (event: string, data: any) => void
  onError?: (error: Error) => void
  signal?: AbortSignal
}

/**
 * Consume a server-sent event stream.
 *
 * `EventSource` cannot be used: it cannot carry an Authorization header, which
 * every one of these endpoints requires, so the frames are parsed from a plain
 * fetch body. Pass a body for a POST, or `undefined` for a GET.
 */
export async function stream(
  path: string,
  body: unknown,
  handlers: SseHandlers,
): Promise<void> {
  const isGet = body === undefined
  const send = () =>
    fetch(`${API_BASE_URL}${path}`, {
      method: isGet ? 'GET' : 'POST',
      credentials: 'include',
      headers: isGet ? authHeaders() : { 'Content-Type': 'application/json', ...authHeaders() },
      body: isGet ? undefined : JSON.stringify(body),
      signal: handlers.signal,
    })

  let response = await send()
  if (response.status === 401 && (await refreshAccessToken())) {
    response = await send()
  }
  if (!response.ok) throw await readError(response)
  if (!response.body) throw new ApiError(500, '服务器没有返回流式响应')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // Frames are separated by a blank line; a partial frame stays buffered.
      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        boundary = buffer.indexOf('\n\n')
        dispatchFrame(frame, handlers)
      }
    }
  } finally {
    reader.releaseLock()
  }
}

function dispatchFrame(frame: string, handlers: SseHandlers): void {
  let event = 'message'
  const dataLines: string[] = []

  for (const line of frame.split('\n')) {
    if (line.startsWith(':')) continue // keep-alive comment
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }

  if (dataLines.length === 0) return
  try {
    handlers.onEvent(event, JSON.parse(dataLines.join('\n')))
  } catch {
    handlers.onEvent(event, dataLines.join('\n'))
  }
}

/** Fetch a binary response, used for synthesized speech. */
export async function fetchBlob(path: string, body: unknown): Promise<Blob> {
  const send = () =>
    fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(body),
    })

  let response = await send()
  if (response.status === 401 && (await refreshAccessToken())) {
    response = await send()
  }
  if (!response.ok) throw await readError(response)
  return await response.blob()
}

/** Upload a file as multipart form data. */
export async function upload<T>(path: string, form: FormData): Promise<T> {
  return request<T>(path, { method: 'POST', body: form })
}
