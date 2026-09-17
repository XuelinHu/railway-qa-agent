<script setup lang="ts">
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import * as admin from '@/api/admin'
import DataTable from '@/components/admin/DataTable.vue'
import PaginationBar from '@/components/admin/PaginationBar.vue'
import SearchToolbar from '@/components/admin/SearchToolbar.vue'
import { usePagination } from '@/composables/usePagination'
import { useAuthStore } from '@/stores/auth'
import type { TerminologyEntry } from '@/types/api'

const auth = useAuthStore()

const filters = reactive<{ category: string | null; source_language: string | null }>({
  category: null,
  source_language: null,
})

const table = usePagination<TerminologyEntry>({
  fetcher: (params) => admin.listTerminology(params as admin.TerminologyQuery),
  filters: () => ({
    category: filters.category,
    source_language: filters.source_language,
  }),
})

const categories = ref<string[]>([])

// --- create / edit ---------------------------------------------------------

const editorOpen = ref(false)
const editorMode = ref<'create' | 'edit'>('create')
const editorSaving = ref(false)
const editorForm = reactive({
  id: '',
  source_term: '',
  target_term: '',
  source_language: 'zh',
  target_language: 'en',
  category: '',
  definition: '',
  aliases: '',
})

function openCreate() {
  editorMode.value = 'create'
  Object.assign(editorForm, {
    id: '',
    source_term: '',
    target_term: '',
    source_language: 'zh',
    target_language: 'en',
    category: '',
    definition: '',
    aliases: '',
  })
  editorOpen.value = true
}

function openEdit(entry: TerminologyEntry) {
  editorMode.value = 'edit'
  Object.assign(editorForm, {
    id: entry.id,
    source_term: entry.source_term,
    target_term: entry.target_term,
    source_language: entry.source_language,
    target_language: entry.target_language,
    category: entry.category ?? '',
    definition: entry.definition ?? '',
    aliases: (entry.aliases ?? []).join('，'),
  })
  editorOpen.value = true
}

async function saveEditor() {
  if (!editorForm.source_term.trim() || !editorForm.target_term.trim()) {
    ElMessage.warning('源术语与目标术语不能为空')
    return
  }
  const payload = {
    source_term: editorForm.source_term,
    target_term: editorForm.target_term,
    source_language: editorForm.source_language,
    target_language: editorForm.target_language,
    category: editorForm.category || null,
    definition: editorForm.definition || null,
    aliases: editorForm.aliases
      .split(/[,，;；]/)
      .map((item) => item.trim())
      .filter(Boolean),
  }

  editorSaving.value = true
  try {
    if (editorMode.value === 'create') {
      await admin.createTerminology(payload)
      ElMessage.success('术语已新增')
    } else {
      await admin.updateTerminology(editorForm.id, payload)
      ElMessage.success('术语已更新')
    }
    editorOpen.value = false
    await table.load()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    editorSaving.value = false
  }
}

async function remove(entry: TerminologyEntry) {
  try {
    await ElMessageBox.confirm(`确定删除术语「${entry.source_term}」？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await admin.deleteTerminology(entry.id)
    ElMessage.success('已删除')
    await table.load()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '删除失败')
  }
}

// --- import ----------------------------------------------------------------

const importOpen = ref(false)
const importing = ref(false)
const importResult = ref<{ created: number; updated: number; skipped: number; errors: string[] } | null>(null)
const selectedFile = ref<File | null>(null)

function pickFile(file: { raw?: File }) {
  selectedFile.value = file.raw ?? null
}

async function runImport() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  importing.value = true
  try {
    importResult.value = await admin.importTerminology(selectedFile.value)
    ElMessage.success('导入完成')
    await table.load()
    await loadCategories()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '导入失败')
  } finally {
    importing.value = false
  }
}

async function loadCategories() {
  try {
    categories.value = await admin.terminologyCategories()
  } catch {
    categories.value = []
  }
}

onMounted(loadCategories)
</script>

<template>
  <div class="terminology-manage">
    <SearchToolbar
      v-model="table.keyword.value"
      placeholder="中英双向搜索：术语、分类或释义"
      :loading="table.loading.value"
      @search="table.search"
      @reset="() => { filters.category = null; filters.source_language = null; table.reset() }"
    >
      <template #filters>
        <el-select
          v-model="filters.category"
          placeholder="分类"
          clearable
          filterable
          style="width: 180px"
        >
          <el-option v-for="item in categories" :key="item" :label="item" :value="item" />
        </el-select>
        <el-select v-model="filters.source_language" placeholder="源语言" clearable style="width: 120px">
          <el-option label="中文" value="zh" />
          <el-option label="English" value="en" />
        </el-select>
      </template>

      <template #actions>
        <el-button v-if="auth.can('terminology:import')" @click="importOpen = true">
          批量导入
        </el-button>
        <el-button v-if="auth.can('terminology:create')" type="primary" @click="openCreate">
          新增术语
        </el-button>
      </template>
    </SearchToolbar>

    <DataTable
      :data="table.items.value"
      :loading="table.loading.value"
      empty-text="没有匹配的术语"
      empty-hint="支持中英双向关键词搜索"
    >
      <el-table-column prop="source_term" label="源术语" min-width="180" show-overflow-tooltip />
      <el-table-column prop="target_term" label="目标术语" min-width="180" show-overflow-tooltip />
      <el-table-column label="语言" width="120">
        <template #default="{ row }">{{ row.source_language }} → {{ row.target_language }}</template>
      </el-table-column>
      <el-table-column prop="category" label="分类" min-width="140" show-overflow-tooltip />
      <el-table-column prop="definition" label="释义" min-width="240" show-overflow-tooltip />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button v-if="auth.can('terminology:update')" link type="primary" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button v-if="auth.can('terminology:delete')" link type="danger" @click="remove(row)">
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
      :title="editorMode === 'create' ? '新增术语' : '编辑术语'"
      width="560px"
    >
      <el-form label-width="100px">
        <el-form-item label="源术语">
          <el-input v-model="editorForm.source_term" />
        </el-form-item>
        <el-form-item label="目标术语">
          <el-input v-model="editorForm.target_term" />
        </el-form-item>
        <el-form-item label="语言方向">
          <el-input v-model="editorForm.source_language" style="width: 100px" />
          <span class="terminology-manage__arrow">→</span>
          <el-input v-model="editorForm.target_language" style="width: 100px" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="editorForm.category" />
        </el-form-item>
        <el-form-item label="别名">
          <el-input v-model="editorForm.aliases" placeholder="多个别名用逗号分隔" />
        </el-form-item>
        <el-form-item label="释义">
          <el-input v-model="editorForm.definition" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorOpen = false">取消</el-button>
        <el-button type="primary" :loading="editorSaving" @click="saveEditor">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="importOpen" title="批量导入术语" width="520px">
      <el-upload
        drag
        :auto-upload="false"
        :limit="1"
        accept=".csv,.json,.xlsx,.xls"
        :on-change="pickFile"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽文件到此处，或<em>点击选择</em></div>
        <template #tip>
          <div class="el-upload__tip">支持 CSV / JSON / Excel，列名与术语字段一致即可</div>
        </template>
      </el-upload>

      <el-alert
        v-if="importResult"
        class="terminology-manage__result"
        type="success"
        :closable="false"
        show-icon
      >
        <p>
          新增 {{ importResult.created }} 条，更新 {{ importResult.updated }} 条，跳过
          {{ importResult.skipped }} 条
        </p>
        <p v-for="(item, index) in importResult.errors.slice(0, 5)" :key="index" class="terminology-manage__error">
          {{ item }}
        </p>
      </el-alert>

      <template #footer>
        <el-button @click="importOpen = false">关闭</el-button>
        <el-button type="primary" :loading="importing" @click="runImport">开始导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.terminology-manage__arrow {
  margin: 0 8px;
  color: #5c6972;
}

.terminology-manage__result {
  margin-top: 14px;
}

.terminology-manage__error {
  margin: 4px 0 0;
  color: #b45309;
  font-size: 12px;
}
</style>
