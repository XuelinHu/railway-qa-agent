<script setup lang="ts">
import { computed } from 'vue'

import type { ChatMessage } from '@/types/chat'

const props = withDefaults(
  defineProps<{
    message: ChatMessage
    /** Offered on agent turns; omitted where there is no voice control. */
    speakable?: boolean
    speaking?: boolean
  }>(),
  { speakable: false, speaking: false },
)

const emit = defineEmits<{ (event: 'speak', text: string): void }>()

const isUser = computed(() => props.message.role === 'user')
const label = computed(() => (isUser.value ? '我' : '智能体'))
const empty = computed(() => !props.message.content && props.message.streaming)
const citationCount = computed(() => props.message.citations?.length ?? 0)
</script>

<template>
  <article class="message" :class="`message--${isUser ? 'user' : 'assistant'}`">
    <div class="message__meta">
      <span>{{ label }}</span>
      <span v-if="message.streaming" class="message__state">生成中…</span>
      <button
        v-else-if="speakable && message.content"
        class="message__speak"
        type="button"
        :title="speaking ? '停止播报' : '朗读'"
        @click="emit('speak', message.content)"
      >
        {{ speaking ? '停止' : '朗读' }}
      </button>
    </div>

    <details v-if="message.thinking" class="message__thinking">
      <summary>思考过程</summary>
      <p>{{ message.thinking }}</p>
    </details>

    <div v-if="empty" class="message__content message__content--waiting">
      <span class="message__caret" />
    </div>
    <div v-else class="message__content">{{ message.content }}</div>

    <p v-if="message.error" class="message__error">{{ message.error }}</p>

    <details v-if="citationCount" class="message__citations">
      <summary>引用来源（{{ citationCount }}）</summary>
      <ul>
        <li v-for="(citation, index) in message.citations" :key="`${citation.text}-${index}`">
          <div class="citation__source">
            {{ citation.kind }}
            <span v-if="citation.source_file"> · {{ citation.source_file }}</span>
            <span v-if="citation.score != null"> · {{ citation.score.toFixed(3) }}</span>
          </div>
          <p>{{ citation.text }}</p>
        </li>
      </ul>
    </details>
  </article>
</template>

<style scoped>
.message {
  width: min(820px, 100%);
}

.message__state {
  color: #1f7a75;
}

.message__speak {
  padding: 2px 8px;
  color: #1f7a75;
  background: transparent;
  border: 1px solid #c7d7d5;
  border-radius: 999px;
  font-size: 12px;
}

.message__content--waiting {
  display: flex;
  align-items: center;
  min-height: 20px;
}

.message__caret {
  display: inline-block;
  width: 8px;
  height: 16px;
  background: #1f7a75;
  animation: caret 1s steps(2, start) infinite;
}

@keyframes caret {
  50% {
    opacity: 0;
  }
}

.message__thinking {
  margin-bottom: 10px;
  color: #5c6972;
  font-size: 13px;
}

.message__thinking summary {
  color: #8a5b17;
  user-select: none;
}

.message__thinking p {
  margin: 8px 0 0;
  padding-left: 12px;
  border-left: 2px solid #e2e8ea;
  white-space: pre-wrap;
}

.message__error {
  margin: 10px 0 0;
  padding: 8px 10px;
  color: #7f1d1d;
  background: #fff1f1;
  border: 1px solid #f3b6b6;
  border-radius: 6px;
  font-size: 13px;
}
</style>
