<script setup lang="ts">
/**
 * The model the agent answers with.
 *
 * Read-only for members — it shows what is in use. Switching is an
 * administrative act, so the dropdown only becomes selectable for accounts
 * holding `model:switch`, and there is exactly one code path that writes it.
 */
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

import { useModelStore } from '@/stores/models'

const models = useModelStore()
const error = ref<string | null>(null)

onMounted(() => {
  models.load().catch((err: unknown) => {
    error.value = err instanceof Error ? err.message : '无法获取模型列表'
  })
})

async function change(name: string) {
  if (name === models.active) return
  try {
    await models.activate(name)
    ElMessage.success(`已切换为 ${name}`)
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '切换模型失败')
    await models.load().catch(() => undefined)
  }
}
</script>

<template>
  <div class="model-switcher">
    <el-select
      v-if="models.canSwitch"
      :model-value="models.active"
      :loading="models.loading || models.switching"
      :disabled="!models.available"
      placeholder="选择模型"
      size="default"
      class="model-switcher__select"
      @change="change"
    >
      <el-option
        v-for="option in models.options"
        :key="option.name"
        :label="option.name"
        :value="option.name"
      >
        <span class="model-switcher__name">{{ option.name }}</span>
        <span class="model-switcher__meta">
          {{ option.parameter_size ?? option.size_label }}
          <template v-if="option.loaded"> · 已加载</template>
        </span>
      </el-option>
    </el-select>

    <el-tooltip v-else :content="'当前使用 ' + (models.active ?? '未配置')" placement="bottom">
      <el-tag effect="plain" type="info">
        {{ models.active ?? (models.available ? '未选择模型' : '模型服务不可用') }}
      </el-tag>
    </el-tooltip>

    <span v-if="error" class="model-switcher__error">{{ error }}</span>
  </div>
</template>

<style scoped>
.model-switcher {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.model-switcher__select {
  width: 200px;
}

.model-switcher__name {
  margin-right: 12px;
}

.model-switcher__meta {
  float: right;
  color: #8a949b;
  font-size: 12px;
}

.model-switcher__error {
  color: #b91c1c;
  font-size: 12px;
}
</style>
