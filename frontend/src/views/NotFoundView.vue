<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="not-found">
    <p class="not-found__code">404</p>
    <h1>页面不存在</h1>
    <p class="not-found__hint">链接可能已经失效，或者你没有访问该页面的权限。</p>
    <div class="not-found__actions">
      <el-button type="primary" @click="router.push({ name: 'chat' })">返回问答</el-button>
      <el-button @click="router.back()">返回上一页</el-button>
    </div>
  </div>
</template>

<style scoped>
.not-found {
  display: grid;
  place-content: center;
  gap: 10px;
  min-height: 70vh;
  text-align: center;
}

.not-found__code {
  margin-bottom: 0;
  color: #1f7a75;
  font-size: 56px;
  font-weight: 700;
  line-height: 1;
}

.not-found__hint {
  color: #5c6972;
}

.not-found__actions {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 8px;
}
</style>
