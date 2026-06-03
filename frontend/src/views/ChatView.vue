<script setup lang="ts">
import { CirclePlus, SendHorizontal } from '@lucide/vue'
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import MessageBubble from '@/components/MessageBubble.vue'
import { useChatStore } from '@/stores/chat'

const chat = useChatStore()
const draft = ref('')
const messagePane = ref<HTMLElement | null>(null)

const healthType = computed(() => (chat.health?.status === 'ok' ? 'success' : 'danger'))

async function submit() {
  const value = draft.value
  draft.value = ''
  await chat.submitMessage(value)
}

function scrollToBottom() {
  nextTick(() => {
    if (messagePane.value) {
      messagePane.value.scrollTop = messagePane.value.scrollHeight
    }
  })
}

watch(() => chat.messages.length, scrollToBottom)

onMounted(async () => {
  await Promise.all([chat.refreshHealth(), chat.loadSessions()])
})
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="sidebar__brand">
        <div>
          <p class="eyebrow">Railway QA</p>
          <h1>Bilingual Agent</h1>
        </div>
        <el-tag :type="healthType" size="small">API</el-tag>
      </div>

      <button class="new-button" type="button" @click="chat.startNewSession">
        <CirclePlus :size="18" />
        <span>New</span>
      </button>

      <nav class="session-list" aria-label="Chat sessions">
        <button
          v-for="session in chat.sessions"
          :key="session.id"
          class="session-item"
          :class="{ 'session-item--active': session.id === chat.activeSessionId }"
          type="button"
          @click="chat.selectSession(session.id)"
        >
          <span>{{ session.title }}</span>
          <small>{{ session.language.toUpperCase() }}</small>
        </button>
      </nav>
    </aside>

    <main class="workspace">
      <header class="workspace__header">
        <div>
          <p class="eyebrow">ECRL · Railway Terminology · Regulations</p>
          <h2>International Railway Support</h2>
        </div>
        <el-tag effect="plain">ZH / EN</el-tag>
      </header>

      <section ref="messagePane" class="messages" aria-live="polite">
        <div v-if="chat.messages.length === 0" class="empty-state">
          <h3>Railway regulatory QA</h3>
          <p>中文、English、术语、规章引用</p>
        </div>

        <MessageBubble v-for="message in chat.messages" :key="message.id" :message="message" />
      </section>

      <p v-if="chat.error" class="error-line">{{ chat.error }}</p>

      <form class="composer" @submit.prevent="submit">
        <el-input
          v-model="draft"
          class="composer__input"
          :autosize="{ minRows: 2, maxRows: 6 }"
          resize="none"
          type="textarea"
          placeholder="输入铁路规章或术语问题"
          @keydown.meta.enter.prevent="submit"
          @keydown.ctrl.enter.prevent="submit"
        />
        <button class="send-button" type="submit" :disabled="chat.sending || !draft.trim()">
          <SendHorizontal :size="20" />
          <span>Send</span>
        </button>
      </form>
    </main>
  </div>
</template>
