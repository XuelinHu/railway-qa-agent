<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { forgotPassword } from '@/api/auth'

const router = useRouter()

const username = ref('')
const loading = ref(false)
const error = ref<string | null>(null)
const sent = ref(false)
/**
 * When no mail server is configured the backend hands the token back instead
 * of pretending an email went out, so the flow stays usable without SMTP.
 */
const devToken = ref<string | null>(null)

async function submit() {
  if (!username.value) {
    error.value = '请输入用户名'
    return
  }
  loading.value = true
  error.value = null
  try {
    const result = await forgotPassword(username.value)
    sent.value = true
    devToken.value = result.dev_reset_token ?? null
  } catch (err) {
    error.value = err instanceof Error ? err.message : '提交失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-card">
    <h2>找回密码</h2>
    <p class="auth-card__lead">
      提交用户名后，系统会向账号绑定的邮箱发送重置链接；未绑定邮箱的账号由管理员在管理台发放重置令牌。
    </p>

    <el-form v-if="!sent" label-position="top" @submit.prevent="submit">
      <el-form-item label="用户名">
        <el-input v-model="username" placeholder="用户名" @keyup.enter="submit" />
      </el-form-item>

      <el-alert v-if="error" class="auth-card__error" type="error" :closable="false" :title="error" />

      <el-button class="auth-card__submit" type="primary" :loading="loading" @click="submit">
        提交
      </el-button>
    </el-form>

    <div v-else class="auth-card__done">
      <el-alert type="success" :closable="false" show-icon title="请求已提交，请按提示完成重置" />

      <el-alert v-if="devToken" class="auth-card__error" type="warning" :closable="false">
        <p>当前未配置邮件服务，可直接使用下面的重置令牌：</p>
        <code class="auth-card__token">{{ devToken }}</code>
      </el-alert>

      <el-button class="auth-card__submit" type="primary" @click="router.push({ name: 'reset-password' })">
        去重置密码
      </el-button>
    </div>

    <div class="auth-card__links">
      <RouterLink :to="{ name: 'login' }">返回登录</RouterLink>
      <RouterLink :to="{ name: 'reset-password' }">已有重置令牌</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.auth-card {
  width: min(420px, 100%);
}

.auth-card h2 {
  margin-bottom: 6px;
}

.auth-card__lead {
  margin-bottom: 20px;
  color: #5c6972;
  font-size: 14px;
  line-height: 1.7;
}

.auth-card__error {
  margin-bottom: 14px;
}

.auth-card__submit {
  width: 100%;
}

.auth-card__done {
  display: grid;
  gap: 14px;
}

.auth-card__token {
  display: block;
  margin-top: 6px;
  padding: 8px;
  overflow-wrap: anywhere;
  background: #ffffff;
  border-radius: 6px;
  font-size: 12px;
}

.auth-card__links {
  display: flex;
  justify-content: space-between;
  margin-top: 16px;
  font-size: 13px;
}
</style>
