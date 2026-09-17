<script setup lang="ts">
/** The pager every admin table ends with. `total` comes from the server. */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    page: number
    pageSize: number
    total: number
    pageSizes?: number[]
    disabled?: boolean
  }>(),
  { pageSizes: () => [10, 20, 50, 100], disabled: false },
)

const emit = defineEmits<{
  (event: 'update:page', value: number): void
  (event: 'update:pageSize', value: number): void
}>()

const range = computed(() => {
  if (props.total === 0) return '共 0 条'
  const from = (props.page - 1) * props.pageSize + 1
  const to = Math.min(props.page * props.pageSize, props.total)
  return `第 ${from}-${to} 条 / 共 ${props.total} 条`
})
</script>

<template>
  <div class="pagination-bar">
    <span class="pagination-bar__range">{{ range }}</span>
    <el-pagination
      background
      :current-page="page"
      :page-size="pageSize"
      :page-sizes="pageSizes"
      :total="total"
      :disabled="disabled"
      layout="sizes, prev, pager, next, jumper"
      @update:current-page="emit('update:page', $event)"
      @update:page-size="emit('update:pageSize', $event)"
    />
  </div>
</template>

<style scoped>
.pagination-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 16px;
}

.pagination-bar__range {
  color: #5c6972;
  font-size: 13px;
}
</style>
