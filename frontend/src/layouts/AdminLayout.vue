<script setup lang="ts">
import { ArrowDown, Back, House } from '@element-plus/icons-vue'
import * as icons from '@element-plus/icons-vue'
import { computed, type Component } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'

import AgentWidget from '@/components/agent/AgentWidget.vue'
import ModelSwitcher from '@/components/agent/ModelSwitcher.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

/**
 * Menus come from the server rather than being declared here: the same
 * permission set that guards the routes decides what a role sees, so a role
 * edit cannot leave a link pointing at a page that will refuse to load.
 */
const menus = computed(() => auth.menus)

const activeMenu = computed(() => route.path)

/**
 * Menu icons are named by the server as Element Plus icon components. A name
 * that does not resolve leaves the item without an icon rather than breaking
 * the whole sidebar.
 */
function iconFor(name: string): Component | null {
  if (!name) return null
  const registry = icons as unknown as Record<string, Component>
  return registry[name] ?? null
}

async function signOut() {
  await auth.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <el-container class="admin-shell">
    <el-aside width="220px" class="admin-shell__aside">
      <div class="admin-shell__brand">
        <p class="eyebrow">Railway QA</p>
        <h1>管理台</h1>
      </div>

      <el-menu :default-active="activeMenu" router class="admin-shell__menu">
        <el-menu-item v-for="menu in menus" :key="menu.key" :index="menu.path">
          <el-icon v-if="iconFor(menu.icon)"><component :is="iconFor(menu.icon)" /></el-icon>
          <span>{{ menu.title }}</span>
        </el-menu-item>
      </el-menu>

      <div class="admin-shell__aside-foot">
        <el-button link :icon="Back" @click="router.push({ name: 'chat' })">返回问答</el-button>
      </div>
    </el-aside>

    <el-container>
      <el-header class="admin-shell__header">
        <div class="admin-shell__crumb">
          <el-icon><House /></el-icon>
          <span>{{ route.meta.title ?? '管理台' }}</span>
        </div>

        <div class="admin-shell__actions">
          <ModelSwitcher />
          <el-dropdown trigger="click">
            <span class="admin-shell__account">
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
        </div>
      </el-header>

      <el-main class="admin-shell__main">
        <RouterView />
      </el-main>
    </el-container>

    <AgentWidget />
  </el-container>
</template>

<style scoped>
.admin-shell {
  min-height: 100vh;
}

.admin-shell__aside {
  display: flex;
  flex-direction: column;
  border-right: 1px solid #d8e0e3;
  background: #f8faf9;
}

.admin-shell__brand {
  padding: 20px 20px 12px;
}

.admin-shell__brand h1 {
  font-size: 20px;
}

.admin-shell__menu {
  flex: 1;
  border-right: 0;
  background: transparent;
}

.admin-shell__aside-foot {
  padding: 12px 20px 20px;
}

.admin-shell__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: auto;
  padding: 12px 24px;
  border-bottom: 1px solid #d8e0e3;
  background: #ffffff;
}

.admin-shell__crumb {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #24313a;
  font-size: 15px;
}

.admin-shell__actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.admin-shell__account {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #24313a;
  cursor: pointer;
  font-size: 14px;
}

.admin-shell__main {
  padding: 20px 24px 40px;
  background: #eef2f3;
}

@media (max-width: 860px) {
  .admin-shell {
    flex-direction: column;
  }

  .admin-shell__aside {
    width: 100% !important;
    border-right: 0;
    border-bottom: 1px solid #d8e0e3;
  }
}
</style>
