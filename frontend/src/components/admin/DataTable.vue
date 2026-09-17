<script setup lang="ts">
/**
 * A table with the loading and empty states every screen needs.
 *
 * Columns come in through the default slot; the point of wrapping `el-table`
 * is that an empty result reads as "nothing matched this search" rather than
 * as a blank rectangle the viewer has to interpret.
 */
withDefaults(
  defineProps<{
    data: unknown[]
    loading?: boolean
    emptyText?: string
    emptyHint?: string
    rowKey?: string
    stripe?: boolean
  }>(),
  {
    loading: false,
    emptyText: '暂无数据',
    emptyHint: '',
    rowKey: 'id',
    stripe: true,
  },
)
</script>

<template>
  <div v-loading="loading" class="data-table">
    <el-table :data="data" :row-key="rowKey" :stripe="stripe" border style="width: 100%">
      <slot />
      <template #empty>
        <div class="data-table__empty">
          <p class="data-table__empty-title">{{ emptyText }}</p>
          <p v-if="emptyHint" class="data-table__empty-hint">{{ emptyHint }}</p>
        </div>
      </template>
    </el-table>
  </div>
</template>

<style scoped>
.data-table {
  min-height: 200px;
}

.data-table__empty {
  padding: 32px 0;
  color: #5c6972;
}

.data-table__empty-title {
  margin-bottom: 4px;
  font-size: 14px;
}

.data-table__empty-hint {
  margin-bottom: 0;
  color: #8a949b;
  font-size: 12px;
}
</style>
