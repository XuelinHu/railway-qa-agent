<script setup lang="ts">
/**
 * Push to talk.
 *
 * Disabled with a reason rather than silently doing nothing: the commonest
 * failure is a microphone the browser will refuse because the page is served
 * over plain HTTP, and a button that looks broken is worse than one that
 * explains itself.
 */
import { Microphone, Loading, VideoPause } from '@element-plus/icons-vue'
import { computed } from 'vue'

const props = defineProps<{
  status: 'idle' | 'listening' | 'thinking' | 'speaking'
  disabled?: boolean
  hint?: string | null
  /** Live partial transcript, shown next to the microphone. */
  interim?: string
}>()

const emit = defineEmits<{ (event: 'toggle'): void }>()

const listening = computed(() => props.status === 'listening')
const busy = computed(() => props.status === 'thinking')

const label = computed(() => {
  if (busy.value) return '识别中'
  if (listening.value) return '正在聆听'
  if (props.status === 'speaking') return '播报中'
  return '按住说话'
})
</script>

<template>
  <div class="voice-button">
    <el-tooltip :content="hint ?? label" placement="top" :disabled="!hint && !listening">
      <el-button
        class="voice-button__button"
        :class="{ 'voice-button__button--live': listening }"
        :type="listening ? 'danger' : 'default'"
        :disabled="disabled"
        circle
        @click="emit('toggle')"
      >
        <el-icon v-if="busy"><Loading /></el-icon>
        <el-icon v-else-if="status === 'speaking'"><VideoPause /></el-icon>
        <el-icon v-else><Microphone /></el-icon>
      </el-button>
    </el-tooltip>

    <span v-if="interim" class="voice-button__interim">{{ interim }}</span>
    <span v-else-if="hint" class="voice-button__hint">{{ hint }}</span>
  </div>
</template>

<style scoped>
.voice-button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.voice-button__button--live {
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  50% {
    box-shadow: 0 0 0 8px rgba(245, 108, 108, 0.18);
  }
}

.voice-button__interim,
.voice-button__hint {
  max-width: 260px;
  overflow: hidden;
  color: #5c6972;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.voice-button__hint {
  color: #b45309;
}
</style>
