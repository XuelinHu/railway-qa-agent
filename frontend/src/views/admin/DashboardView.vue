<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { dashboardStats } from '@/api/admin'
import { useAuthStore } from '@/stores/auth'
import type { DashboardStats } from '@/types/api'

const router = useRouter()
const auth = useAuthStore()

const stats = ref<DashboardStats | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

const tiles = [
  { key: 'users_total', label: '用户总数', route: 'admin-users', perm: 'user:read' },
  { key: 'users_new_7d', label: '近 7 天新增用户', route: 'admin-users', perm: 'user:read' },
  { key: 'sessions_total', label: '会话总数', route: 'admin-conversations', perm: 'chat:read' },
  { key: 'sessions_today', label: '今日会话', route: 'admin-conversations', perm: 'chat:read' },
  { key: 'messages_total', label: '消息总数', route: 'admin-conversations', perm: 'chat:read' },
  { key: 'terminology_total', label: '术语条目', route: 'admin-terminology', perm: 'terminology:read' },
  { key: 'roles_total', label: '角色数量', route: 'admin-roles', perm: 'role:read' },
  { key: 'pending_reset_requests', label: '待处理重置申请', route: 'admin-users', perm: 'user:read' },
] as const

function valueOf(key: string): number | string {
  const payload = stats.value as unknown as Record<string, number> | null
  return payload?.[key] ?? 0
}

onMounted(async () => {
  try {
    stats.value = await dashboardStats()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '统计数据加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-loading="loading" class="dashboard">
    <el-alert v-if="error" type="error" :closable="false" :title="error" show-icon />

    <el-row :gutter="16">
      <el-col v-for="tile in tiles" :key="tile.key" :xs="12" :sm="12" :md="6">
        <el-card
          shadow="hover"
          class="dashboard__tile"
          @click="auth.can(tile.perm) && router.push({ name: tile.route })"
        >
          <p class="dashboard__label">{{ tile.label }}</p>
          <p class="dashboard__value">{{ valueOf(tile.key) }}</p>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="dashboard__model">
      <template #header><span>当前模型</span></template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="模型">
          {{ stats?.model_name ?? '未配置' }}
        </el-descriptions-item>
        <el-descriptions-item label="提供方">
          {{ stats?.model_provider ?? '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="Ollama 状态">
          <el-tag :type="stats?.ollama_online ? 'success' : 'info'" size="small">
            {{ stats?.ollama_online ? '在线' : '离线' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="本地模型数量">
          {{ stats?.ollama_models ?? 0 }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<style scoped>
.dashboard {
  display: grid;
  gap: 16px;
}

.dashboard__tile {
  margin-bottom: 16px;
  cursor: pointer;
}

.dashboard__label {
  margin-bottom: 6px;
  color: #5c6972;
  font-size: 13px;
}

.dashboard__value {
  margin-bottom: 0;
  color: #14213d;
  font-size: 28px;
  font-weight: 600;
}
</style>
