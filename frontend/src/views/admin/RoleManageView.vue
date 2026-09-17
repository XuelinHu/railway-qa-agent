<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import * as admin from '@/api/admin'
import DataTable from '@/components/admin/DataTable.vue'
import PaginationBar from '@/components/admin/PaginationBar.vue'
import SearchToolbar from '@/components/admin/SearchToolbar.vue'
import { usePagination } from '@/composables/usePagination'
import { useAuthStore } from '@/stores/auth'
import type { PermissionNode, Role } from '@/types/api'

const auth = useAuthStore()

const table = usePagination<Role>({
  fetcher: (params) => admin.listRoles(params),
})

const permissionTree = ref<PermissionNode[]>([])
/** Node keys are tree positions; permissions are codes. These map between them. */
const keyByPermission = ref(new Map<string, string>())
const permissionByKey = ref(new Map<string, string>())

const treeRef = ref<{ setCheckedKeys: (keys: string[]) => void; getCheckedKeys: (leafOnly?: boolean) => string[]; getHalfCheckedKeys: () => string[] } | null>(null)

const editorOpen = ref(false)
const editorMode = ref<'create' | 'edit'>('create')
const editorSaving = ref(false)
const editorForm = reactive({ id: '', code: '', name: '', description: '' })

function indexPermissions(nodes: PermissionNode[], index: Map<string, string>): void {
  for (const node of nodes) {
    if (node.perm) index.set(node.perm, node.key)
    indexPermissions(node.children, index)
  }
}

async function loadPermissions() {
  permissionTree.value = await admin.listPermissions()
  const forward = new Map<string, string>()
  indexPermissions(permissionTree.value, forward)
  keyByPermission.value = forward
  const reverse = new Map<string, string>()
  for (const [permission, key] of forward) reverse.set(key, permission)
  permissionByKey.value = reverse
}

function openCreate() {
  editorMode.value = 'create'
  Object.assign(editorForm, { id: '', code: '', name: '', description: '' })
  editorOpen.value = true
}

function openEdit(role: Role) {
  editorMode.value = 'edit'
  Object.assign(editorForm, {
    id: role.id,
    code: role.code,
    name: role.name,
    description: role.description ?? '',
  })
  editorOpen.value = true
}

async function saveEditor() {
  editorSaving.value = true
  try {
    if (editorMode.value === 'create') {
      await admin.createRole({
        code: editorForm.code,
        name: editorForm.name,
        description: editorForm.description || null,
      })
      ElMessage.success('角色已创建')
    } else {
      await admin.updateRole(editorForm.id, {
        name: editorForm.name,
        description: editorForm.description || null,
      })
      ElMessage.success('角色已更新')
    }
    editorOpen.value = false
    await table.load()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    editorSaving.value = false
  }
}

// --- permissions -----------------------------------------------------------

const permOpen = ref(false)
const permSaving = ref(false)
const permTarget = ref<Role | null>(null)

function openPermissions(role: Role) {
  permTarget.value = role
  permOpen.value = true
  const keys = role.permissions
    .map((permission) => keyByPermission.value.get(permission))
    .filter((key): key is string => Boolean(key))
  // The tree renders inside a dialog, so it only exists on the next frame.
  window.setTimeout(() => treeRef.value?.setCheckedKeys(keys), 0)
}

async function savePermissions() {
  if (!permTarget.value || !treeRef.value) return
  const checked = [
    ...treeRef.value.getCheckedKeys(),
    ...treeRef.value.getHalfCheckedKeys(),
  ]
  const permissions = checked
    .map((key) => permissionByKey.value.get(key))
    .filter((permission): permission is string => Boolean(permission))

  permSaving.value = true
  try {
    await admin.setRolePermissions(permTarget.value.id, permissions)
    ElMessage.success('权限已更新')
    permOpen.value = false
    await table.load()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    permSaving.value = false
  }
}

// --- delete ----------------------------------------------------------------

async function remove(role: Role) {
  try {
    await ElMessageBox.confirm(`确定删除角色「${role.name}」？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await admin.deleteRole(role.id)
    ElMessage.success('已删除')
    await table.load()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '删除失败')
  }
}

onMounted(loadPermissions)
</script>

<template>
  <div class="role-manage">
    <SearchToolbar
      v-model="table.keyword.value"
      placeholder="搜索角色编码、名称或描述"
      :loading="table.loading.value"
      @search="table.search"
      @reset="table.reset"
    >
      <template #actions>
        <el-button v-if="auth.can('role:create')" type="primary" @click="openCreate">
          新建角色
        </el-button>
      </template>
    </SearchToolbar>

    <DataTable
      :data="table.items.value"
      :loading="table.loading.value"
      empty-text="没有匹配的角色"
      empty-hint="角色决定菜单可见范围与按钮权限"
    >
      <el-table-column prop="code" label="编码" min-width="140" />
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip />
      <el-table-column label="权限数" width="100">
        <template #default="{ row }">{{ row.permissions.length }}</template>
      </el-table-column>
      <el-table-column label="用户数" width="100">
        <template #default="{ row }">{{ row.user_count }}</template>
      </el-table-column>
      <el-table-column label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_system ? 'warning' : 'info'" size="small">
            {{ row.is_system ? '内置' : '自定义' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="auth.can('role:update')"
            link
            type="primary"
            @click="openPermissions(row)"
          >
            配置权限
          </el-button>
          <el-button v-if="auth.can('role:update')" link type="primary" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button
            v-if="auth.can('role:delete') && !row.is_system"
            link
            type="danger"
            @click="remove(row)"
          >
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
      :title="editorMode === 'create' ? '新建角色' : '编辑角色'"
      width="480px"
    >
      <el-form label-width="90px">
        <el-form-item label="编码">
          <el-input
            v-model="editorForm.code"
            :disabled="editorMode === 'edit'"
            placeholder="小写字母、数字、下划线或短横线"
          />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="editorForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editorForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorOpen = false">取消</el-button>
        <el-button type="primary" :loading="editorSaving" @click="saveEditor">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="permOpen" title="配置权限" width="560px">
      <p class="role-manage__hint">
        勾选后该角色即可看到对应菜单与操作按钮；保存后相关用户下次进入页面即生效。
      </p>
      <el-tree
        ref="treeRef"
        :data="permissionTree"
        node-key="key"
        show-checkbox
        default-expand-all
        :props="{ label: 'title', children: 'children' }"
      />
      <template #footer>
        <el-button @click="permOpen = false">取消</el-button>
        <el-button type="primary" :loading="permSaving" @click="savePermissions">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.role-manage__hint {
  margin-bottom: 12px;
  color: #5c6972;
  font-size: 13px;
}
</style>
