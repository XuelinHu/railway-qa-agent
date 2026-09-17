<script setup lang="ts">
/**
 * The conversation itself, shared by the floating widget and the chat page.
 *
 * Kept free of dialog chrome so both surfaces can host it: the widget wraps it
 * in a modal, the chat page puts it beside the session list.
 */
import { Clock, CirclePlus, Promotion, Setting, VideoPause } from '@element-plus/icons-vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import MessageBubble from '@/components/MessageBubble.vue'
import ModelSwitcher from '@/components/agent/ModelSwitcher.vue'
import VoiceButton from '@/components/agent/VoiceButton.vue'
import VoiceSettings from '@/components/agent/VoiceSettings.vue'
import { useSpeech } from '@/composables/useSpeech'
import { useAgentStore } from '@/stores/agent'

const props = withDefaults(
  defineProps<{
    /** Hides the session list where the host already shows one. */
    showHistory?: boolean
  }>(),
  { showHistory: true },
)

const agent = useAgentStore()
const speech = useSpeech()

const draft = ref('')
const pane = ref<HTMLElement | null>(null)
const historyOpen = ref(false)
const speakingId = ref<string | null>(null)

const busy = computed(() => agent.sending)
const canSend = computed(() => draft.value.trim().length > 0 && !busy.value)
const lastAnswer = computed(() => {
  for (let index = agent.messages.length - 1; index >= 0; index -= 1) {
    const message = agent.messages[index]
    if (message.role !== 'user') return message
  }
  return null
})

function scrollToBottom() {
  nextTick(() => {
    if (pane.value) pane.value.scrollTop = pane.value.scrollHeight
  })
}

watch(() => agent.messages.map((message) => message.content.length).join(','), scrollToBottom)

async function send(text?: string) {
  const value = (text ?? draft.value).trim()
  if (!value || busy.value) return
  draft.value = ''
  await agent.ask(value)
}

/** Speak a message, or stop it if that message is already being read. */
async function speak(message: { id: string; content: string }) {
  if (speakingId.value === message.id) {
    speech.stopSpeaking()
    speakingId.value = null
    return
  }
  speakingId.value = message.id
  await speech.speak(message.content)
  if (speakingId.value === message.id) speakingId.value = null
}

/**
 * Read each finished answer aloud, and in hands-free mode go straight back to
 * listening. Registered against the store rather than the send call so an
 * answer that arrives after a re-render is still spoken.
 */
const unsubscribe = agent.onAnswer(async (message) => {
  if (!speech.autoSpeak.value || !message.content) return
  speakingId.value = message.id
  await speech.speak(message.content)
  if (speakingId.value === message.id) speakingId.value = null
  if (speech.continuous.value && speech.conversationActive.value) {
    speech.startConversation((text) => void send(text))
  }
})

function toggleMicrophone() {
  // Pressing the microphone while the answer is being read is the interrupt:
  // the audio stops on this tick, and listening begins immediately after.
  if (speech.status.value === 'speaking') speech.stopSpeaking()
  speech.toggleListening()
}

function openHistory() {
  historyOpen.value = true
  void agent.loadSessions()
}

async function pickSession(sessionId: string) {
  historyOpen.value = false
  await agent.selectSession(sessionId)
  scrollToBottom()
}

function newSession() {
  agent.startNewSession()
  historyOpen.value = false
  draft.value = ''
}

onMounted(() => {
  speech.setOnFinalText((text) => void send(text))
  void speech.loadCapabilities()
  if (agent.sessions.length === 0) void agent.loadSessions()
  scrollToBottom()
})

onBeforeUnmount(() => {
  unsubscribe()
  speech.setOnFinalText(null)
  speech.shutdown()
})
</script>

<template>
  <section class="agent-panel">
    <header class="agent-panel__head">
      <div class="agent-panel__title">
        <strong>{{ agent.activeSession?.title ?? '新的对话' }}</strong>
        <span class="agent-panel__sub">
          {{ agent.activeSessionId ? `会话 ${agent.activeSessionId.slice(0, 8)}` : '尚未开始' }}
        </span>
      </div>

      <div class="agent-panel__tools">
        <ModelSwitcher />
        <el-button :icon="CirclePlus" text @click="newSession">新对话</el-button>
        <el-button v-if="props.showHistory" :icon="Clock" text @click="openHistory">历史</el-button>
        <el-popover :width="480" trigger="click" placement="bottom-end">
          <template #reference>
            <el-button :icon="Setting" text>语音设置</el-button>
          </template>
          <VoiceSettings />
        </el-popover>
      </div>
    </header>

    <div ref="pane" class="agent-panel__messages">
      <div v-if="agent.messages.length === 0" class="agent-panel__empty">
        <h3>问点什么</h3>
        <p>例如「牵引供电系统的组成」「接触网悬挂方式有哪些」「什么是 ETCS」</p>
      </div>

      <MessageBubble
        v-for="message in agent.messages"
        :key="message.id"
        :message="message"
        speakable
        :speaking="speakingId === message.id"
        @speak="speak(message)"
      />
    </div>

    <p v-if="agent.error" class="agent-panel__error">{{ agent.error }}</p>

    <footer class="agent-panel__composer">
      <el-input
        v-model="draft"
        type="textarea"
        resize="none"
        :autosize="{ minRows: 2, maxRows: 5 }"
        placeholder="输入铁路规章、术语或工程问题，Enter 发送"
        @keydown.enter.exact.prevent="send()"
      />

      <div class="agent-panel__actions">
        <VoiceButton
          :status="speech.status.value"
          :interim="speech.interim.value"
          :hint="speech.microphoneHint.value"
          :disabled="speech.canUseMicrophone.value === false"
          @toggle="toggleMicrophone"
        />

        <div class="agent-panel__spacer" />

        <el-button v-if="busy" :icon="VideoPause" @click="agent.stop()">停止生成</el-button>
        <el-button type="primary" :icon="Promotion" :disabled="!canSend" @click="send()">
          发送
        </el-button>
      </div>

      <p v-if="lastAnswer?.error" class="agent-panel__hint">{{ lastAnswer.error }}</p>
    </footer>

    <el-drawer v-model="historyOpen" title="历史会话" size="360px">
      <el-empty v-if="agent.sessions.length === 0" description="还没有历史会话" />
      <ul v-else class="agent-panel__history">
        <li v-for="session in agent.sessions" :key="session.id">
          <button
            type="button"
            :class="{ 'is-active': session.id === agent.activeSessionId }"
            @click="pickSession(session.id)"
          >
            <span class="agent-panel__history-title">{{ session.title }}</span>
            <small>{{ new Date(session.updated_at).toLocaleString() }}</small>
          </button>
        </li>
      </ul>
    </el-drawer>
  </section>
</template>

<style scoped>
.agent-panel {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto auto;
  height: 100%;
  min-height: 0;
}

.agent-panel__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8ea;
}

.agent-panel__title {
  display: flex;
  flex-direction: column;
}

.agent-panel__sub {
  color: #8a949b;
  font-size: 12px;
}

.agent-panel__tools {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.agent-panel__messages {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
  padding: 16px 2px;
  overflow-y: auto;
}

.agent-panel__empty {
  margin: auto;
  color: #5c6972;
  text-align: center;
}

.agent-panel__empty h3 {
  margin-bottom: 6px;
  color: #14213d;
}

.agent-panel__error {
  margin: 0 0 8px;
  color: #b91c1c;
  font-size: 13px;
}

.agent-panel__composer {
  display: grid;
  gap: 10px;
  padding-top: 12px;
  border-top: 1px solid #e2e8ea;
}

.agent-panel__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.agent-panel__spacer {
  flex: 1;
}

.agent-panel__hint {
  margin-bottom: 0;
  color: #b45309;
  font-size: 12px;
}

.agent-panel__history {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.agent-panel__history button {
  display: grid;
  gap: 4px;
  width: 100%;
  padding: 10px 12px;
  color: #24313a;
  text-align: left;
  background: #ffffff;
  border: 1px solid #dde5e8;
  border-radius: 8px;
}

.agent-panel__history button:hover,
.agent-panel__history button.is-active {
  border-color: #1f7a75;
  background: #eef8f6;
}

.agent-panel__history-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-panel__history small {
  color: #8a949b;
}
</style>
