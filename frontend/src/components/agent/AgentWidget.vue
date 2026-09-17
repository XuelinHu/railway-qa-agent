<script setup lang="ts">
/**
 * The floating ball, present on every signed-in page.
 *
 * It hosts the same panel the chat page uses, so a question asked from the
 * admin console lands in the same conversation rather than a parallel one.
 */
import { ChatDotRound, Close } from '@element-plus/icons-vue'
import { onBeforeUnmount, ref, watch } from 'vue'

import AgentPanel from '@/components/agent/AgentPanel.vue'

const open = ref(false)
const unread = ref(0)

watch(open, (value) => {
  if (value) unread.value = 0
})

// A keyboard route to the panel, so it is reachable without a mouse.
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && open.value) open.value = false
  if (event.altKey && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    open.value = !open.value
  }
}

window.addEventListener('keydown', onKeydown)
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="agent-widget">
    <button
      v-show="!open"
      class="agent-widget__ball"
      type="button"
      title="智能助手（Alt+K）"
      @click="open = true"
    >
      <el-icon :size="22"><ChatDotRound /></el-icon>
      <span v-if="unread" class="agent-widget__badge">{{ unread }}</span>
    </button>

    <el-dialog
      v-model="open"
      class="agent-widget__dialog"
      width="min(880px, 94vw)"
      top="6vh"
      :show-close="false"
      append-to-body
      destroy-on-close
    >
      <template #header>
        <div class="agent-widget__header">
          <span>智能助手</span>
          <el-button :icon="Close" text circle @click="open = false" />
        </div>
      </template>
      <div class="agent-widget__body">
        <AgentPanel />
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.agent-widget__ball {
  position: fixed;
  right: 28px;
  bottom: 28px;
  z-index: 2000;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  color: #ffffff;
  background: #1f7a75;
  border: 0;
  border-radius: 50%;
  box-shadow: 0 10px 26px rgba(31, 122, 117, 0.35);
  transition: transform 0.15s ease;
}

.agent-widget__ball:hover {
  transform: translateY(-2px);
}

.agent-widget__badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 20px;
  padding: 0 6px;
  color: #ffffff;
  background: #d97706;
  border-radius: 999px;
  font-size: 12px;
  line-height: 20px;
}

.agent-widget__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 16px;
  font-weight: 600;
}

/* The panel manages its own scrolling; the dialog only bounds the height. */
.agent-widget__body {
  height: min(70vh, 640px);
}

@media (max-width: 640px) {
  .agent-widget__ball {
    right: 16px;
    bottom: 16px;
  }

  .agent-widget__body {
    height: 74vh;
  }
}
</style>
