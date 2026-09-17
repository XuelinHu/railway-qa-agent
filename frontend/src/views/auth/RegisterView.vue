<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const form = reactive({
  username: '',
  display_name: '',
  email: '',
  password: '',
  confirm: '',
})
const loading = ref(false)
const error = ref<string | null>(null)

async function submit() {
  error.value = null
  if (!form.username || !form.password) {
    error.value = '用户名和密码不能为空'
    return
  }
  if (form.password !== form.confirm) {
    error.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  try {
    await auth.register({
      username: form.username,
      password: form.password,
      display_name: form.display_name || null,
      email: form.email || null,
    })
    ElMessage.success('注册成功，请登录')
    await router.push({ name: 'login' })
  } catch (err) {
    error.value = err instanceof Error ? err.message : '注册失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-card">
    <h2>注册</h2>
    <p class="auth-card__lead">注册后即可使用问答、语音与个人中心。</p>

    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item label="用户名">
        <el-input v-model="form.username" placeholder="3-32 位字母、数字、下划线、点或短横线" />
      </el-form-item>
      <el-form-item label="显示名称">
        <el-input v-model="form.display_name" placeholder="选填，用于界面展示" />
      </el-form-item>
      <el-form-item label="邮箱">
        <el-input v-model="form.email" placeholder="选填，用于找回密码" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input v-model="form.password" type="password" show-password placeholder="至少 8 位，需含字母和数字" />
      </el-form-item>
      <el-form-item label="确认密码">
        <el-input
          v-model="form.confirm"
          type="password"
          show-password
          placeholder="再次输入密码"
          @keyup.enter="submit"
        />
      </el-form-item>

      <el-alert v-if="error" class="auth-card__error" type="error" :closable="false" :title="error" />

      <el-button class="auth-card__submit" type="primary" :loading="loading" @click="submit">
        注册
      </el-button>
    </el-form>

    <div class="auth-card__links">
      <RouterLink :to="{ name: 'login' }">已有账号，去登录</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.auth-card {
  width: min(400px, 100%);
}

.auth-card h2 {
  margin-bottom: 6px;
}

.auth-card__lead {
  margin-bottom: 18px;
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
  margin-top: 16px;
  font-size: 13px;
}
</style>
