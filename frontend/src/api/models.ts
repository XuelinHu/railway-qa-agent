/** Model listing and, for administrators, the full lifecycle. */

import { del, get, post, stream } from '@/api/client'
import type {
  MessageResponse,
  ModelListResponse,
  ModelOptionsResponse,
  PullJob,
} from '@/types/api'

/** The read-only view a member may use to pick a model. */
export const listModelOptions = () => get<ModelOptionsResponse>('/models')

export const adminListModels = () => get<ModelListResponse>('/admin/models')

export const activePulls = () => get<PullJob[]>('/admin/models/pulls')

export const modelDetail = (name: string) =>
  get<Record<string, unknown>>(`/admin/models/${encodeURIComponent(name)}/detail`)

export const activateModel = (
  model: string,
  options: { preload?: boolean; unloadPrevious?: boolean } = {},
) =>
  post<ModelListResponse>('/admin/models/activate', {
    model,
    preload: options.preload ?? true,
    unload_previous: options.unloadPrevious ?? false,
  })

export const loadModel = (model: string) =>
  post<MessageResponse>('/admin/models/load', { model })

export const unloadModel = (model: string, force = false) =>
  post<MessageResponse>('/admin/models/unload', { model, force })

export const pullModel = (model: string) =>
  post<PullJob>('/admin/models/pull', { model })

export const deleteModel = (name: string) =>
  del<MessageResponse>(`/admin/models/${encodeURIComponent(name)}`)

/**
 * Follow a download's progress.
 *
 * The stream replays everything that has happened so far before following it
 * live, so attaching late — or after a page reload — still shows the whole
 * download rather than starting from the current percentage.
 */
export function streamPull(
  model: string,
  handlers: {
    onProgress: (job: Partial<PullJob> & { status?: string }) => void
    onDone: (job: PullJob) => void
    onError?: (detail: string) => void
    signal?: AbortSignal
  },
): Promise<void> {
  return stream(
    `/admin/models/pull/stream?name=${encodeURIComponent(model)}`,
    undefined,
    {
      signal: handlers.signal,
      onEvent: (event, data) => {
        if (event === 'progress') handlers.onProgress(data)
        else if (event === 'done') handlers.onDone(data)
        else if (event === 'error') handlers.onError?.(data.detail ?? '下载失败')
      },
    },
  )
}
