<script setup lang="ts">
/** The full-page chat: the same conversation the floating widget shows. */
import { CirclePlus } from '@element-plus/icons-vue'
import { onMounted } from 'vue'

import AgentPanel from '@/components/agent/AgentPanel.vue'
import { useAgentStore } from '@/stores/agent'

const agent = useAgentStore()

onMounted(() => {
  void agent.loadSessions()
})
</script>

<template>
  <div class="chat-page">
    <aside class="chat-page__aside">
      <el-button class="chat-page__new" :icon="CirclePlus" @click="agent.startNewSession()">
        新对话
      </el-button>

      <nav class="chat-page__sessions" aria-label="历史会话">
        <el-empty v-if="agent.sessions.length === 0" description="暂无历史会话" :image-size="72" />
        <button
          v-for="session in agent.sessions"
          :key="session.id"
          class="chat-page__session"
          :class="{ 'chat-page__session--active': session.id === agent.activeSessionId }"
          type="button"
          @click="agent.selectSession(session.id)"
        >
          <span class="chat-page__session-title">{{ session.title }}</span>
          <small>{{ new Date(session.updated_at).toLocaleDateString() }}</small>
        </button>
      </nav>
    </aside>

    <section class="chat-page__main">
      <AgentPanel :show-history="false" />
    </section>
  </div>
</template>

<style scoped>
.chat-page {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  height: calc(100vh - 68px);
  min-height: 0;
}

.chat-page__aside {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  padding: 20px;
  border-right: 1px solid #d8e0e3;
  background: #f8faf9;
}

.chat-page__new {
  width: 100%;
}

.chat-page__sessions {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  overflow-y: auto;
}

.chat-page__session {
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

.chat-page__session:hover,
.chat-page__session--active {
  border-color: #1f7a75;
  background: #eef8f6;
}

.chat-page__session-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-page__session small {
  color: #8a949b;
}

.chat-page__main {
  min-width: 0;
  min-height: 0;
  padding: 20px 24px 24px;
}

@media (max-width: 860px) {
  .chat-page {
    grid-template-columns: 1fr;
    height: auto;
  }

  .chat-page__aside {
    border-right: 0;
    border-bottom: 1px solid #d8e0e3;
  }

  .chat-page__sessions {
    max-height: 180px;
  }

  .chat-page__main {
    height: 70vh;
  }
}
</style>
