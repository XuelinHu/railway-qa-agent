<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import * as admin from '@/api/admin'
import DataTable from '@/components/admin/DataTable.vue'
import PaginationBar from '@/components/admin/PaginationBar.vue'
import SearchToolbar from '@/components/admin/SearchToolbar.vue'
import { usePagination } from '@/composables/usePagination'
import { useAuthStore } from '@/stores/auth'
import type { ResetRequest, Role, User } from '@/types/api'

const auth = useAuthStore()

const filters = reactive<{ is_active: boolean | null; role_code: string | null }>({
  is_active: null,
  role_code: null,
})

const table = usePagination<User>({
  fetcher: (params) => admin.listUsers(params as admin.UserQuery),
  filters: () => ({ is_active: filters.is_active, role_code: filters.role_code }),
})

const roles = ref<Role[]>([])
const resetRequests = ref<ResetRequest[]>([])

// --- create / edit ---------------------------------------------------------

const editorOpen = ref(false)
const editorMode = ref<'create' | 'edit'>('create')
const editorSaving = ref(false)
const editorForm = reactive({
  id: '',
  username: '',
  password: '',
  display_name: '',
  email: '',
  is_active: true,
})

function openCreate() {
  editorMode.value = 'create'
  Object.assign(editorForm, {
    id: '',
    username: '',
    password: '',
    display_name: '',
    email: '',
    is_active: true,
  })
  editorOpen.value = true
}

function openEdit(user: User) {
  editorMode.value = 'edit'
  Object.assign(editorForm, {
    id: user.id,
    username: user.username,
    password: '',
    display_name: user.display_name ?? '',
    email: user.email ?? '',
    is_active: user.is_active,
  })
  editorOpen.value = true
}

async function saveEditor() {
  editorSaving.value = true
  try {
    if (editorMode.value === 'create') {
      await admin.createUser({
        username: editorForm.username,
        password: editorForm.password,
        display_name: editorForm.display_name || null,
        email: editorForm.email || null,
        is_active: editorForm.is_active,
      })
      ElMessage.success('用户已创建')
    } else {
      await admin.updateUser(editorForm.id, {
        display_name: editorForm.display_name || null,
        email: editorForm.email || null,
        is_active: editorForm.is_active,
      })
      ElMessage.success('用户已更新')
    }
    editorOpen.value = false
    await table.load()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    editorSaving.value = false
  }
}

// --- roles -----------------------------------------------------------------

const roleOpen = ref(false)
const roleSaving = ref(false)
const roleTarget = ref<User | null>(null)
const selectedRoles = ref<string[]>([])

function openRoles(user: User) {
  roleTarget.value = user
  selectedRoles.value = [...user.roles]
  roleOpen.value = true
}

async function saveRoles() {
  if (!roleTarget.value) return
  roleSaving.value = true
  try {
    await admin.assignRoles(roleTarget.value.id, selectedRoles.value)
    ElMessage.success('角色已更新')
    roleOpen.value = false
    await table.load()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '分配失败')
  } finally {
    roleSaving.value = false
  }
}

// --- reset password --------------------------------------------------------

const resetOpen = ref(false)
const resetSaving = ref(false)
const resetTarget = ref<User | null>(null)
const resetForm = reactive({ new_password: '', require_change: true })

function openReset(user: User) {
  resetTarget.value = user
  resetForm.new_password = ''
  resetForm.require_change = true
  resetOpen.value = true
}

async function saveReset() {
  if (!resetTarget.value) return
  resetSaving.value = true
  try {
    await admin.resetUserPassword(
      resetTarget.value.id,
      resetForm.new_password,
      resetForm.require_change,
    )
    ElMessage.success('密码已重置')
    resetOpen.value = false
    await table.load()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '重置失败')
  } finally {
    resetSaving.value = false
  }
}

// --- reset requests from the login page ------------------------------------

const issuedToken = ref<string | null>(null)

async function loadResetRequests() {
  try {
    resetRequests.value = await admin.listResetRequests()
  } catch {
    resetRequests.value = []
  }
}

async function issueToken(request: ResetRequest) {
  try {
    const result = await admin.issueResetToken(request.id)
    issuedToken.value = result.token
    await loadResetRequests()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '发放失败')
  }
}

// --- row actions -----------------------------------------------------------

async function toggleActive(user: User) {
  try {
    await admin.updateUser(user.id, { is_active: !user.is_active })
    ElMessage.success(user.is_active ? '已禁用' : '已启用')
    await table.load()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '操作失败')
  }
}

async function remove(user: User) {
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${user.username}」？该操作不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await admin.deleteUser(user.id)
    ElMessage.success('已删除')
    await table.load()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '删除失败')
  }
}

onMounted(async () => {
  try {
    const payload = await admin.listRoles({ page: 1, page_size: 100 })
    roles.value = payload.items
  } catch {
    roles.value = []
  }
  await loadResetRequests()
})
</script>

<template>
  <div class="user-manage">
    <el-alert
      v-if="resetRequests.length"
      class="user-manage__requests"
      type="warning"
      show-icon
      :closable="false"
    >
      <template #title>有 {{ resetRequests.length }} 条待处理的密码重置申请</template>
      <ul class="user-manage__request-list">
        <li v-for="request in resetRequests" :key="request.id">
          <span>{{ request.username ?? request.user_id }} · {{ new Date(request.created_at).toLocaleString() }}</span>
          <el-button
            v-if="auth.can('user:reset-password')"
            link
            type="primary"
            @click="issueToken(request)"
          >
            发放重置令牌
          </el-button>
        </li>
      </ul>
    </el-alert>

    <SearchToolbar
      v-model="table.keyword.value"
      placeholder="搜索用户名、姓名或邮箱"
      :loading="table.loading.value"
      @search="table.search"
      @reset="() => { filters.is_active = null; filters.role_code = null; table.reset() }"
    >
      <template #filters>
        <el-select v-model="filters.is_active" placeholder="状态" clearable style="width: 120px">
          <el-option label="启用" :value="true" />
          <el-option label="禁用" :value="false" />
        </el-select>
        <el-select v-model="filters.role_code" placeholder="角色" clearable style="width: 160px">
          <el-option v-for="role in roles" :key="role.code" :label="role.name" :value="role.code" />
        </el-select>
      </template>

      <template #actions>
        <el-button v-if="auth.can('user:create')" type="primary" @click="openCreate">
          新建用户
        </el-button>
      </template>
    </SearchToolbar>

    <DataTable
      :data="table.items.value"
      :loading="table.loading.value"
      empty-text="没有匹配的用户"
      empty-hint="换个关键词，或清空筛选条件后重试"
    >
      <el-table-column prop="username" label="用户名" min-width="140" sortable />
      <el-table-column prop="display_name" label="姓名" min-width="120" />
      <el-table-column prop="email" label="邮箱" min-width="180" />
      <el-table-column label="角色" min-width="160">
        <template #default="{ row }">
          <el-tag v-for="role in row.roles" :key="role" size="small" class="user-manage__role">
            {{ role }}
          </el-tag>
          <span v-if="!row.roles.length" class="user-manage__muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最近登录" min-width="170">
        <template #default="{ row }">
          {{ row.last_login_at ? new Date(row.last_login_at).toLocaleString() : '—' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button v-if="auth.can('user:update')" link type="primary" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button
            v-if="auth.can('user:assign-role')"
            link
            type="primary"
            @click="openRoles(row)"
          >
            角色
          </el-button>
          <el-button
            v-if="auth.can('user:reset-password')"
            link
            type="primary"
            @click="openReset(row)"
          >
            重置密码
          </el-button>
          <el-button v-if="auth.can('user:update')" link @click="toggleActive(row)">
            {{ row.is_active ? '禁用' : '启用' }}
          </el-button>
          <el-button v-if="auth.can('user:delete')" link type="danger" @click="remove(row)">
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

    <el-dialog
      v-model="editorOpen"
      :title="editorMode === 'create' ? '新建用户' : '编辑用户'"
      width="480px"
    >
      <el-form label-width="90px">
        <el-form-item label="用户名">
          <el-input v-model="editorForm.username" :disabled="editorMode === 'edit'" />
        </el-form-item>
        <el-form-item v-if="editorMode === 'create'" label="初始密码">
          <el-input v-model="editorForm.password" type="password" show-password placeholder="至少 8 位，需含字母和数字" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="editorForm.display_name" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="editorForm.email" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="editorForm.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorOpen = false">取消</el-button>
        <el-button type="primary" :loading="editorSaving" @click="saveEditor">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="roleOpen" title="分配角色" width="420px">
      <el-checkbox-group v-model="selectedRoles">
        <el-checkbox v-for="role in roles" :key="role.code" :value="role.code">
          {{ role.name }}（{{ role.code }}）
        </el-checkbox>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="roleOpen = false">取消</el-button>
        <el-button type="primary" :loading="roleSaving" @click="saveRoles">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetOpen" title="重置密码" width="460px">
      <el-form label-width="90px">
        <el-form-item label="新密码">
          <el-input v-model="resetForm.new_password" type="password" show-password placeholder="至少 8 位，需含字母和数字" />
        </el-form-item>
        <el-form-item label="首次登录">
          <el-switch v-model="resetForm.require_change" active-text="要求修改密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetOpen = false">取消</el-button>
        <el-button type="primary" :loading="resetSaving" @click="saveReset">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog :model-value="issuedToken !== null" title="重置令牌" width="520px" @close="issuedToken = null">
      <p>请将下面的令牌交给用户，用户在“重置密码”页面使用，令牌一次性有效。</p>
      <code class="user-manage__token">{{ issuedToken }}</code>
      <template #footer>
        <el-button type="primary" @click="issuedToken = null">知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.user-manage__requests {
  margin-bottom: 16px;
}

.user-manage__request-list {
  margin: 6px 0 0;
  padding-left: 16px;
}

.user-manage__request-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
}

.user-manage__role {
  margin-right: 6px;
}

.user-manage__muted {
  color: #8a949b;
}

.user-manage__token {
  display: block;
  margin-top: 10px;
  padding: 10px;
  overflow-wrap: anywhere;
  background: #f4f6f7;
  border-radius: 6px;
  font-size: 12px;
}
</style>
