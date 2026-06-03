<script setup lang="ts">
import type { ChatMessage } from '@/types/chat'

defineProps<{
  message: ChatMessage
}>()
</script>

<template>
  <article class="message" :class="`message--${message.role}`">
    <div class="message__meta">
      <span>{{ message.role === 'user' ? 'User' : 'Agent' }}</span>
      <span v-if="message.pending">Saving</span>
    </div>
    <div class="message__content">{{ message.content }}</div>
    <details v-if="message.citations?.length" class="message__citations">
      <summary>Sources</summary>
      <ul>
        <li v-for="(citation, index) in message.citations" :key="`${citation.text}-${index}`">
          <div class="citation__source">
            {{ citation.kind }}
            <span v-if="citation.source_file"> · {{ citation.source_file }}</span>
          </div>
          <p>{{ citation.text }}</p>
        </li>
      </ul>
    </details>
  </article>
</template>

