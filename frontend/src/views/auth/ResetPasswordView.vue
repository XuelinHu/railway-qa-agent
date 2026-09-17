<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { resetPassword } from '@/api/auth'

const route = useRoute()
const router = useRouter()

const form = reactive({ token: '', password: '', confirm: '' })
const loading = ref(false)
const error = ref<string | null>(null)

// The mailed link carries the token in the query string.
onMounted(() => {
  const token = route.query.token
  if (typeof token === 'string') form.token = token
})

async function submit() {
  error.value = null
  if (!form.token) {
    error.value = '请填写重置令牌'
    return
  }
  if (form.password !== form.confirm) {
    error.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  try {
    await resetPassword(form.token, form.password)
    ElMessage.success('密码已重置，请用新密码登录')
    await router.push({ name: 'login' })
  } catch (err) {
    error.value = err instanceof Error ? err.message : '重置失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-card">
    <h2>重置密码</h2>
    <p class="auth-card__lead">填写重置令牌与新密码。令牌由邮件或管理员提供，一次性使用。</p>

    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item label="重置令牌">
        <el-input v-model="form.token" placeholder="粘贴重置令牌" />
      </el-form-item>
      <el-form-item label="新密码">
        <el-input v-model="form.password" type="password" show-password placeholder="至少 8 位，需含字母和数字" />
      </el-form-item>
      <el-form-item label="确认新密码">
        <el-input
          v-model="form.confirm"
          type="password"
          show-password
          placeholder="再次输入新密码"
          @keyup.enter="submit"
        />
      </el-form-item>

      <el-alert v-if="error" class="auth-card__error" type="error" :closable="false" :title="error" />

      <el-button class="auth-card__submit" type="primary" :loading="loading" @click="submit">
        提交
      </el-button>
    </el-form>

    <div class="auth-card__links">
      <RouterLink :to="{ name: 'login' }">返回登录</RouterLink>
      <RouterLink :to="{ name: 'forgot-password' }">还没有令牌</RouterLink>
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

.auth-card__links {
  display: flex;
  justify-content: space-between;
  margin-top: 16px;
  font-size: 13px;
}
</style>
