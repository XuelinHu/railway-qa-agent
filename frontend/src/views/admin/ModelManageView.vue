<script setup lang="ts">
/**
 * Local model lifecycle.
 *
 * The machine's GPU is shared with other work, so unloading is deliberately
 * fenced: the server refuses to evict a model this application did not load
 * unless the operator says so explicitly, and that confirmation is surfaced
 * here rather than hidden behind a retry.
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, onBeforeUnmount, reactive, ref } from 'vue'

import * as modelsApi from '@/api/models'
import DataTable from '@/components/admin/DataTable.vue'
import { useAuthStore } from '@/stores/auth'
import { useModelStore } from '@/stores/models'
import type { ModelInfo, ModelListResponse, PullJob } from '@/types/api'

const auth = useAuthStore()
const modelStore = useModelStore()

const payload = ref<ModelListResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const busyModel = ref<string | null>(null)

// --- pulling ---------------------------------------------------------------

const pullForm = reactive({ name: '' })
const jobs = ref<Record<string, PullJob>>({})
let controller: AbortController | null = null

const runningJobs = computed(() =>
  Object.values(jobs.value).filter((job) => job.status === 'running'),
)

const suggestions = [
  'deepseek-r1:14b',
  'qwen3:14b',
  'qwen2.5:14b',
  'glm4:9b',
  'llama3.1:8b',
]

async function load() {
  loading.value = true
  error.value = null
  try {
    payload.value = await modelsApi.adminListModels()
    modelStore.active = payload.value.active_model
    modelStore.available = payload.value.ollama_online
  } catch (err) {
    error.value = err instanceof Error ? err.message : '模型列表加载失败'
  } finally {
    loading.value = false
  }
}

async function activate(model: ModelInfo) {
  busyModel.value = model.name
  try {
    const result = await modelsApi.activateModel(model.name, { preload: true })
    payload.value = result
    ElMessage.success(`已切换到 ${model.name}`)
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '切换失败')
  } finally {
    busyModel.value = null
  }
}

async function preload(model: ModelInfo) {
  busyModel.value = model.name
  try {
    await modelsApi.loadModel(model.name)
    ElMessage.success(`${model.name} 已加载到显存`)
    await load()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '加载失败')
  } finally {
    busyModel.value = null
  }
}

async function unload(model: ModelInfo, force = false) {
  busyModel.value = model.name
  try {
    await modelsApi.unloadModel(model.name, force)
    ElMessage.success(`${model.name} 已卸载`)
    await load()
  } catch (err) {
    const message = err instanceof Error ? err.message : '卸载失败'
    // 409 means the model was loaded outside this application. That is a
    // shared-GPU decision, so it is asked rather than assumed.
    if (!force && message.includes('不是本系统加载的')) {
      try {
        await ElMessageBox.confirm(
          '该模型不是本系统加载的，卸载可能影响其他正在使用它的程序。确定继续？',
          '共享显存提示',
          { type: 'warning', confirmButtonText: '仍然卸载', cancelButtonText: '取消' },
        )
        await unload(model, true)
        return
      } catch {
        return
      }
    }
    ElMessage.error(message)
  } finally {
    busyModel.value = null
  }
}

async function remove(model: ModelInfo) {
  try {
    await ElMessageBox.confirm(
      `确定从磁盘删除模型「${model.name}」？需要时可重新下载。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  busyModel.value = model.name
  try {
    await modelsApi.deleteModel(model.name)
    ElMessage.success('已删除')
    await load()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '删除失败')
  } finally {
    busyModel.value = null
  }
}

// --- download progress -----------------------------------------------------

function watchPull(name: string) {
  controller?.abort()
  controller = new AbortController()
  jobs.value = {
    ...jobs.value,
    [name]: {
      model: name,
      status: 'running',
      error: null,
      completed: 0,
      total: 0,
      percent: 0,
      started_at: new Date().toISOString(),
      finished_at: null,
    },
  }

  void modelsApi.streamPull(name, {
    signal: controller.signal,
    onProgress: (job) => {
      jobs.value = {
        ...jobs.value,
        [name]: { ...jobs.value[name], ...job, model: name },
      }
    },
    onDone: (job) => {
      jobs.value = { ...jobs.value, [name]: { ...job, model: name } }
      ElMessage.success(`${name} 下载完成`)
      void load()
    },
    onError: (detail) => {
      jobs.value = {
        ...jobs.value,
        [name]: { ...jobs.value[name], status: 'error', error: detail },
      }
      ElMessage.error(detail)
    },
  })
}

async function startPull() {
  const name = pullForm.name.trim()
  if (!name) {
    ElMessage.warning('请输入要下载的模型名称')
    return
  }
  try {
    await modelsApi.pullModel(name)
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '无法开始下载')
    return
  }
  pullForm.name = ''
  watchPull(name)
}

/** Reattach to downloads already in flight, so a reload does not lose them. */
async function reattach() {
  try {
    const active = await modelsApi.activePulls()
    for (const job of active) watchPull(job.model)
  } catch {
    // Nothing in flight, or the endpoint is unreachable; either way the page
    // works without it.
  }
}

function sizeLabel(model: ModelInfo): string {
  return model.size_label || `${(model.size / 1024 / 1024 / 1024).toFixed(1)} GB`
}

onMounted(async () => {
  await load()
  await reattach()
})

onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <div class="model-manage">
    <el-alert
      v-if="payload && !payload.ollama_online"
      class="model-manage__alert"
      type="error"
      show-icon
      :closable="false"
      title="无法连接本地 Ollama 服务"
      description="请确认 ollama 已启动（默认 127.0.0.1:11434），或检查 OLLAMA_BASE_URL 配置。"
    />
    <el-alert v-else-if="error" class="model-manage__alert" type="error" show-icon :closable="false" :title="error" />
    <el-alert
      v-else-if="payload?.gpu_note"
      class="model-manage__alert"
      type="info"
      show-icon
      :closable="false"
      :title="payload.gpu_note"
    />

    <el-card shadow="never" class="model-manage__summary">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="当前模型">
          {{ payload?.active_model ?? '未配置' }}
        </el-descriptions-item>
        <el-descriptions-item label="提供方">{{ payload?.provider ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="Ollama 版本">
          {{ payload?.ollama_version ?? '—' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="never" class="model-manage__pull">
      <template #header><span>在线拉取</span></template>
      <div class="model-manage__pull-form">
        <el-input
          v-model="pullForm.name"
          placeholder="模型名称，例如 deepseek-r1:14b"
          :disabled="!auth.can('model:pull')"
          @keyup.enter="startPull"
        >
          <template #append>
            <el-button
              :disabled="!auth.can('model:pull')"
              :loading="runningJobs.length > 0"
              @click="startPull"
            >
              下载
            </el-button>
          </template>
        </el-input>
        <div class="model-manage__chips">
          <el-tag
            v-for="item in suggestions"
            :key="item"
            class="model-manage__chip"
            effect="plain"
            :disabled="!auth.can('model:pull')"
            @click="pullForm.name = item"
          >
            {{ item }}
          </el-tag>
        </div>
      </div>

      <div v-for="job in Object.values(jobs)" :key="job.model" class="model-manage__job">
        <div class="model-manage__job-head">
          <span>{{ job.model }}</span>
          <el-tag
            size="small"
            :type="job.status === 'success' ? 'success' : job.status === 'error' ? 'danger' : 'warning'"
          >
            {{ job.status === 'running' ? '下载中' : job.status === 'success' ? '完成' : '失败' }}
          </el-tag>
        </div>
        <el-progress
          :percentage="Math.round(job.percent ?? 0)"
          :status="job.status === 'error' ? 'exception' : job.status === 'success' ? 'success' : undefined"
        />
        <p v-if="job.error" class="model-manage__job-error">{{ job.error }}</p>
      </div>
    </el-card>

    <DataTable
      :data="payload?.models ?? []"
      :loading="loading"
      empty-text="本地还没有模型"
      empty-hint="可以在上方输入模型名称在线下载"
    >
      <el-table-column prop="name" label="模型" min-width="200" />
      <el-table-column label="参数规模" width="120">
        <template #default="{ row }">{{ row.parameter_size ?? '—' }}</template>
      </el-table-column>
      <el-table-column label="量化" width="110">
        <template #default="{ row }">{{ row.quantization ?? '—' }}</template>
      </el-table-column>
      <el-table-column label="大小" width="110">
        <template #default="{ row }">{{ sizeLabel(row) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="180">
        <template #default="{ row }">
          <el-tag v-if="row.is_active" type="success" size="small" class="model-manage__tag">使用中</el-tag>
          <el-tag v-if="row.loaded" type="warning" size="small" class="model-manage__tag">
            已加载 {{ (row.size_vram / 1024 / 1024 / 1024).toFixed(1) }}G
          </el-tag>
          <span v-if="!row.is_active && !row.loaded" class="model-manage__muted">未加载</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="auth.can('model:switch') && !row.is_active"
            link
            type="primary"
            :loading="busyModel === row.name"
            @click="activate(row)"
          >
            设为当前
          </el-button>
          <el-button
            v-if="auth.can('model:manage') && !row.loaded"
            link
            type="primary"
            :loading="busyModel === row.name"
            @click="preload(row)"
          >
            加载
          </el-button>
          <el-button
            v-if="auth.can('model:manage') && row.loaded"
            link
            :loading="busyModel === row.name"
            @click="unload(row)"
          >
            卸载
          </el-button>
          <el-button
            v-if="auth.can('model:manage') && !row.is_active"
            link
            type="danger"
            :loading="busyModel === row.name"
            @click="remove(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </DataTable>
  </div>
</template>

<style scoped>
.model-manage {
  display: grid;
  gap: 16px;
}

.model-manage__alert {
  margin-bottom: 0;
}

.model-manage__pull-form {
  display: grid;
  gap: 10px;
}

.model-manage__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.model-manage__chip {
  cursor: pointer;
}

.model-manage__job {
  margin-top: 14px;
}

.model-manage__job-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 13px;
}

.model-manage__job-error {
  margin: 6px 0 0;
  color: #b91c1c;
  font-size: 12px;
}

.model-manage__tag {
  margin-right: 6px;
}

.model-manage__muted {
  color: #8a949b;
}
</style>
