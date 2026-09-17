<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { reactive, ref } from 'vue'

import * as admin from '@/api/admin'
import DataTable from '@/components/admin/DataTable.vue'
import PaginationBar from '@/components/admin/PaginationBar.vue'
import SearchToolbar from '@/components/admin/SearchToolbar.vue'
import { usePagination } from '@/composables/usePagination'
import { useAuthStore } from '@/stores/auth'
import type { ConversationDetail, SessionAdmin } from '@/types/api'

const auth = useAuthStore()

const filters = reactive<{ language: string | null; range: [string, string] | null }>({
  language: null,
  range: null,
})

const table = usePagination<SessionAdmin>({
  fetcher: (params) => admin.listSessions(params as admin.SessionQuery),
  filters: () => ({
    language: filters.language,
    created_from: filters.range?.[0] ?? null,
    created_to: filters.range?.[1] ?? null,
  }),
  sort: 'updated_at',
})

// --- conversation detail ---------------------------------------------------

const detailOpen = ref(false)
const detail = ref<ConversationDetail | null>(null)
const detailLoading = ref(false)
const detailTarget = ref<SessionAdmin | null>(null)
const messagePage = ref(1)
const messagePageSize = ref(10)

async function openDetail(session: SessionAdmin, page = 1) {
  detailTarget.value = session
  detailOpen.value = true
  detailLoading.value = true
  messagePage.value = page
  try {
    detail.value = await admin.getConversation(session.id, {
      page,
      page_size: messagePageSize.value,
    })
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '加载会话失败')
  } finally {
    detailLoading.value = false
  }
}

async function remove(session: SessionAdmin) {
  try {
    await ElMessageBox.confirm(
      `确定删除会话「${session.title}」及其全部消息？该操作不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await admin.deleteSession(session.id)
    ElMessage.success('已删除')
    await table.load()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '删除失败')
  }
}
</script>

<template>
  <div class="session-manage">
    <SearchToolbar
      v-model="table.keyword.value"
      placeholder="搜索会话标题或所属用户"
      :loading="table.loading.value"
      @search="table.search"
      @reset="() => { filters.language = null; filters.range = null; table.reset() }"
    >
      <template #filters>
        <el-select v-model="filters.language" placeholder="语言" clearable style="width: 120px">
          <el-option label="中文" value="zh" />
          <el-option label="English" value="en" />
        </el-select>
        <el-date-picker
          v-model="filters.range"
          type="datetimerange"
          value-format="YYYY-MM-DDTHH:mm:ss"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          style="width: 380px"
        />
      </template>
    </SearchToolbar>

    <DataTable
      :data="table.items.value"
      :loading="table.loading.value"
      empty-text="没有匹配的会话"
      empty-hint="可按用户、语言或时间范围筛选"
    >
      <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip />
      <el-table-column label="所属用户" min-width="140">
        <template #default="{ row }">
          {{ row.username ?? (row.user_id ? row.user_id.slice(0, 8) : '匿名会话') }}
        </template>
      </el-table-column>
      <el-table-column prop="language" label="语言" width="90" />
      <el-table-column label="消息数" width="90">
        <template #default="{ row }">{{ row.message_count }}</template>
      </el-table-column>
      <el-table-column label="更新时间" min-width="170">
        <template #default="{ row }">{{ new Date(row.updated_at).toLocaleString() }}</template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">查看</el-button>
          <el-button v-if="auth.can('chat:delete')" link type="danger" @click="remove(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </DataTable>

    <PaginationBar
      :page="table.page.value"
      :page-size="table.pageSize.value"
      :total="table.total.value"
      :disabled="table.loading.value"
      @update:page="table.changePage"
      @update:page-size="table.changeSize"
    />

    <el-drawer v-model="detailOpen" title="会话详情" size="620px">
      <div v-loading="detailLoading" class="session-manage__detail">
        <el-descriptions v-if="detail" :column="2" border size="small">
          <el-descriptions-item label="标题">{{ detail.session.title }}</el-descriptions-item>
          <el-descriptions-item label="用户">
            {{ detail.session.username ?? '匿名会话' }}
          </el-descriptions-item>
          <el-descriptions-item label="语言">{{ detail.session.language }}</el-descriptions-item>
          <el-descriptions-item label="消息数">{{ detail.session.message_count }}</el-descriptions-item>
        </el-descriptions>

        <div v-for="message in detail?.messages ?? []" :key="message.id" class="session-manage__msg">
          <div class="session-manage__msg-head">
            <el-tag :type="message.role === 'user' ? 'info' : 'success'" size="small">
              {{ message.role === 'user' ? '用户' : '智能体' }}
            </el-tag>
            <span>{{ new Date(message.created_at).toLocaleString() }}</span>
          </div>
          <p class="session-manage__msg-body">{{ message.content }}</p>

          <details v-if="message.trace" class="session-manage__trace">
            <summary>检索轨迹（{{ message.trace.hits.length }} 条命中）</summary>
            <p class="session-manage__query">查询词：{{ message.trace.query }}</p>
            <ul>
              <li v-for="(hit, index) in message.trace.hits" :key="index">
                <span class="session-manage__hit-source">
                  {{ hit.source_file ?? hit.kind }}
                  <template v-if="hit.score != null"> · {{ hit.score.toFixed(3) }}</template>
                </span>
                <p>{{ hit.text }}</p>
              </li>
            </ul>
          </details>
        </div>

        <el-empty v-if="detail && detail.messages.length === 0" description="该会话没有消息" />

        <el-pagination
          v-if="detailTarget"
          class="session-manage__pager"
          layout="prev, pager, next"
          :current-page="messagePage"
          :page-size="messagePageSize"
          :total="detail?.session.message_count ?? 0"
          @current-change="(page: number) => detailTarget && openDetail(detailTarget, page)"
        />
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.session-manage__detail {
  display: grid;
  gap: 14px;
}

.session-manage__msg {
  padding: 12px;
  background: #f8faf9;
  border: 1px solid #e2e8ea;
  border-radius: 8px;
}

.session-manage__msg-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #5c6972;
  font-size: 12px;
}

.session-manage__msg-body {
  margin: 8px 0 0;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  line-height: 1.6;
}

.session-manage__trace {
  margin-top: 8px;
  font-size: 13px;
}

.session-manage__trace summary {
  color: #1f7a75;
  cursor: pointer;
}

.session-manage__query {
  margin: 6px 0;
  color: #5c6972;
}

.session-manage__trace ul {
  display: grid;
  gap: 8px;
  padding-left: 16px;
}

.session-manage__hit-source {
  color: #8a5b17;
  font-size: 12px;
}

.session-manage__pager {
  justify-content: center;
}
</style>
