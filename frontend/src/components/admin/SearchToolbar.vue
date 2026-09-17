<script setup lang="ts">
/**
 * Keyword search plus whatever filters a screen needs.
 *
 * Filters live in the `filters` slot and are read by the view's pagination
 * composable at request time, so a filter change only has to trigger a search
 * rather than push state back up here.
 */
import { Search } from '@element-plus/icons-vue'

defineProps<{
  modelValue: string
  placeholder?: string
  loading?: boolean
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
  (event: 'search'): void
  (event: 'reset'): void
}>()
</script>

<template>
  <div class="toolbar">
    <el-input
      class="toolbar__search"
      :model-value="modelValue"
      :placeholder="placeholder ?? '搜索'"
      clearable
      @update:model-value="emit('update:modelValue', $event)"
      @keyup.enter="emit('search')"
      @clear="emit('search')"
    >
      <template #prefix>
        <el-icon><Search /></el-icon>
      </template>
    </el-input>

    <slot name="filters" />

    <el-button type="primary" :loading="loading" @click="emit('search')">查询</el-button>
    <el-button :disabled="loading" @click="emit('reset')">重置</el-button>

    <div class="toolbar__spacer" />
    <slot name="actions" />
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.toolbar__search {
  width: 260px;
}

.toolbar__spacer {
  flex: 1;
}
</style>
