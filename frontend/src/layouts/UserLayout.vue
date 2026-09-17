<script setup lang="ts">
import { ArrowDown, ChatDotRound, Setting, User } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import AgentWidget from '@/components/agent/AgentWidget.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

// The console entry only appears for accounts that can read at least one of
// its menus; an empty console is worse than no link.
const canOpenConsole = computed(() => auth.canAny(['dashboard:read', 'user:read', 'role:read', 'chat:read', 'terminology:read', 'model:read']))

async function signOut() {
  await auth.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <div class="user-shell">
    <header class="user-shell__header">
      <div class="user-shell__brand">
        <p class="eyebrow">Railway QA</p>
        <h1>铁路知识问答</h1>
      </div>

      <nav class="user-shell__nav">
        <RouterLink class="nav-link" :class="{ 'nav-link--active': route.name === 'chat' }" :to="{ name: 'chat' }">
          <el-icon><ChatDotRound /></el-icon>
          <span>智能问答</span>
        </RouterLink>
        <RouterLink
          class="nav-link"
          :class="{ 'nav-link--active': route.name === 'profile' }"
          :to="{ name: 'profile' }"
        >
          <el-icon><User /></el-icon>
          <span>个人中心</span>
        </RouterLink>
        <RouterLink v-if="canOpenConsole" class="nav-link" :to="{ name: 'admin-dashboard' }">
          <el-icon><Setting /></el-icon>
          <span>管理台</span>
        </RouterLink>
      </nav>

      <el-dropdown trigger="click">
        <span class="user-shell__account">
          {{ auth.displayName }}
          <el-icon><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="router.push({ name: 'profile' })">个人中心</el-dropdown-item>
            <el-dropdown-item divided @click="signOut">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </header>

    <main class="user-shell__body">
      <RouterView />
    </main>

    <AgentWidget />
  </div>
</template>

<style scoped>
.user-shell {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-height: 100vh;
}

.user-shell__header {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 14px 28px;
  border-bottom: 1px solid #d8e0e3;
  background: rgba(255, 255, 255, 0.86);
}

.user-shell__brand h1 {
  font-size: 20px;
}

.user-shell__nav {
  display: flex;
  flex: 1;
  gap: 6px;
}

.nav-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  color: #44515a;
  border-radius: 8px;
  font-size: 14px;
  text-decoration: none;
}

.nav-link:hover,
.nav-link--active {
  color: #1f7a75;
  background: #eef8f6;
}

.user-shell__account {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #24313a;
  cursor: pointer;
  font-size: 14px;
}

.user-shell__body {
  min-height: 0;
}

@media (max-width: 860px) {
  .user-shell__header {
    flex-wrap: wrap;
    gap: 12px;
    padding: 12px 16px;
  }
}
</style>
