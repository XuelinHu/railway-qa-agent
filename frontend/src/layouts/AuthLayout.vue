<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="auth-shell">
    <section class="auth-shell__brand">
      <p class="eyebrow">Railway QA</p>
      <h1>铁路知识检索增强<br />智能问答软件</h1>
      <p class="auth-shell__lead">
        中英双语铁路术语、规章与工程文档检索问答，支持流式作答、语音播报与语音提问。
      </p>
      <ul class="auth-shell__points">
        <li>术语库 3 万余条，中英双向检索</li>
        <li>引用可溯源，回答附带原文出处</li>
        <li>可切换本地大模型，数据不出内网</li>
      </ul>
    </section>

    <section class="auth-shell__panel">
      <RouterView />
    </section>
  </div>
</template>

<style scoped>
.auth-shell {
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  min-height: 100vh;
  background:
    linear-gradient(120deg, rgba(31, 122, 117, 0.12), transparent 55%),
    #eef2f3;
}

.auth-shell__brand {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 18px;
  padding: 64px 56px;
}

.auth-shell__brand h1 {
  font-size: 38px;
  line-height: 1.25;
}

.auth-shell__lead {
  max-width: 460px;
  color: #44515a;
  font-size: 15px;
  line-height: 1.75;
}

.auth-shell__points {
  display: grid;
  gap: 8px;
  margin: 0;
  padding-left: 18px;
  color: #5c6972;
  font-size: 14px;
}

.auth-shell__panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 40px;
  background: #f8faf9;
  border-left: 1px solid #d8e0e3;
}

@media (max-width: 960px) {
  .auth-shell {
    grid-template-columns: 1fr;
  }

  .auth-shell__brand {
    padding: 40px 24px 8px;
  }

  .auth-shell__brand h1 {
    font-size: 28px;
  }

  .auth-shell__panel {
    padding: 24px;
    border-left: 0;
  }
}
</style>
