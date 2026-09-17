/**
 * One pagination implementation for every admin table.
 *
 * The backend returns the same `Page` envelope from every collection endpoint,
 * so the only thing a screen supplies is how to fetch a page and which extra
 * filters it wants. Wiring this once is what keeps "every menu is paginated"
 * true rather than a claim each view makes separately.
 */

import { computed, ref } from 'vue'

import type { Page } from '@/types/api'

export interface UsePaginationOptions<T> {
  /** Called with the full query object for one page. */
  fetcher: (params: Record<string, unknown>) => Promise<Page<T>>
  /** Extra filters, read at request time so a form does not need to sync. */
  filters?: () => Record<string, unknown>
  pageSize?: number
  sort?: string
  order?: 'asc' | 'desc'
  /** Fetch immediately on creation. Turn off to wait for an explicit search. */
  immediate?: boolean
}

export function usePagination<T>(options: UsePaginationOptions<T>) {
  const items = ref([]) as { value: T[] }
  const total = ref(0)
  const pages = ref(0)
  const page = ref(1)
  const pageSize = ref(options.pageSize ?? 20)
  const keyword = ref('')
  const sort = ref<string | null>(options.sort ?? null)
  const order = ref<'asc' | 'desc'>(options.order ?? 'desc')
  const loading = ref(false)
  const error = ref<string | null>(null)
  const loaded = ref(false)

  const isEmpty = computed(() => loaded.value && items.value.length === 0)

  async function load(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const payload = await options.fetcher({
        page: page.value,
        page_size: pageSize.value,
        keyword: keyword.value || undefined,
        sort: sort.value ?? undefined,
        order: order.value,
        ...(options.filters?.() ?? {}),
      })
      items.value = payload.items
      total.value = payload.total
      pages.value = payload.pages
      // The server clamps the page; mirror it so the pager stays honest after
      // a filter shrinks the result set.
      page.value = payload.page
      loaded.value = true
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载失败'
      items.value = []
      total.value = 0
      pages.value = 0
    } finally {
      loading.value = false
    }
  }

  /** Run a new search: back to the first page, since the old one may not exist. */
  function search(): void {
    page.value = 1
    void load()
  }

  function reset(): void {
    keyword.value = ''
    page.value = 1
    void load()
  }

  function changePage(next: number): void {
    page.value = next
    void load()
  }

  function changeSize(size: number): void {
    pageSize.value = size
    page.value = 1
    void load()
  }

  /** Toggle or set the sort column, resetting to the first page. */
  function changeSort(column: string, direction?: 'asc' | 'desc'): void {
    if (direction) {
      sort.value = column
      order.value = direction
    } else if (sort.value === column) {
      order.value = order.value === 'asc' ? 'desc' : 'asc'
    } else {
      sort.value = column
      order.value = 'desc'
    }
    page.value = 1
    void load()
  }

  if (options.immediate !== false) void load()

  return {
    items,
    total,
    pages,
    page,
    pageSize,
    keyword,
    sort,
    order,
    loading,
    error,
    loaded,
    isEmpty,
    load,
    search,
    reset,
    changePage,
    changeSize,
    changeSort,
  }
}
