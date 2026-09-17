<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const form = reactive({ username: '', password: '' })
const loading = ref(false)
const error = ref<string | null>(null)

async function submit() {
  if (!form.username || !form.password) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  error.value = null
  try {
    await auth.login({ username: form.username, password: form.password })
    ElMessage.success('登录成功')

    // A forced password change comes before wherever they were heading: the
    // account is usable but not yet theirs to keep.
    if (auth.mustChangePassword) {
      await router.push({ name: 'profile', query: { force: '1' } })
      return
    }
    const redirect = route.query.redirect
    await router.push(typeof redirect === 'string' ? redirect : { name: 'chat' })
  } catch (err) {
    error.value = err instanceof Error ? err.message : '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-card">
    <h2>登录</h2>
    <p class="auth-card__lead">使用账号登录，或先注册一个。</p>

    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item label="用户名">
        <el-input v-model="form.username" autocomplete="username" placeholder="用户名" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input
          v-model="form.password"
          type="password"
          show-password
          autocomplete="current-password"
          placeholder="密码"
          @keyup.enter="submit"
        />
      </el-form-item>

      <el-alert v-if="error" class="auth-card__error" type="error" :closable="false" :title="error" />

      <el-button class="auth-card__submit" type="primary" :loading="loading" @click="submit">
        登录
      </el-button>
    </el-form>

    <div class="auth-card__links">
      <RouterLink :to="{ name: 'register' }">注册新账号</RouterLink>
      <RouterLink :to="{ name: 'forgot-password' }">忘记密码</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.auth-card {
  width: min(380px, 100%);
}

.auth-card h2 {
  margin-bottom: 6px;
}

.auth-card__lead {
  margin-bottom: 22px;
  color: #5c6972;
  font-size: 14px;
}

.auth-card__error {
  margin-bottom: 14px;
}

.auth-card__submit {
  width: 100%;
}

.auth-card__links {
  display: flex;
  justify-content: space-between;
  margin-top: 16px;
  font-size: 13px;
}
</style>
