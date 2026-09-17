/**
 * Run one server-sent event stream at a time, cancelably.
 *
 * Deliberately free of lifecycle hooks so it also works inside a Pinia setup
 * store, which has no component instance to hang `onUnmounted` from.
 */

import { ref } from 'vue'

import { stream } from '@/api/client'

export function useSse() {
  const active = ref(false)
  const error = ref<string | null>(null)
  let controller: AbortController | null = null

  /**
   * Stream `path` until it ends, is aborted, or fails.
   *
   * A caller that aborts on purpose gets `onEvent` stopped without an error:
   * cancelling is a normal thing to do here, not a failure to report.
   */
  async function run(
    path: string,
    body: unknown,
    onEvent: (event: string, data: any) => void,
  ): Promise<void> {
    abort()
    controller = new AbortController()
    active.value = true
    error.value = null
    try {
      await stream(path, body, { onEvent, signal: controller.signal })
    } catch (err) {
      if (!controller?.signal.aborted) {
        error.value = err instanceof Error ? err.message : '连接中断'
      }
    } finally {
      active.value = false
      controller = null
    }
  }

  function abort(): void {
    controller?.abort()
    controller = null
    active.value = false
  }

  return { active, error, run, abort }
}
