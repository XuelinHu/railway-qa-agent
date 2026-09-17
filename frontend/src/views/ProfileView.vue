<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { changePassword, updateProfile } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

/** Set when an administrator issued the password, or the account expired it. */
const forced = computed(() => route.query.force === '1' || auth.mustChangePassword)

const profile = reactive({ display_name: '', email: '' })
const savingProfile = ref(false)

const password = reactive({ old_password: '', new_password: '', confirm: '' })
const savingPassword = ref(false)
const passwordError = ref<string | null>(null)

onMounted(() => {
  profile.display_name = auth.user?.display_name ?? ''
  profile.email = auth.user?.email ?? ''
})

async function saveProfile() {
  savingProfile.value = true
  try {
    const user = await updateProfile({
      display_name: profile.display_name || null,
      email: profile.email || null,
    })
    auth.setUser(user)
    ElMessage.success('资料已保存')
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    savingProfile.value = false
  }
}

async function savePassword() {
  passwordError.value = null
  if (password.new_password !== password.confirm) {
    passwordError.value = '两次输入的新密码不一致'
    return
  }
  savingPassword.value = true
  try {
    await changePassword({
      old_password: password.old_password,
      new_password: password.new_password,
    })
    ElMessage.success('密码已修改，请重新登录')
    await auth.logout()
    await router.push({ name: 'login' })
  } catch (err) {
    passwordError.value = err instanceof Error ? err.message : '修改失败'
  } finally {
    savingPassword.value = false
  }
}
</script>

<template>
  <div class="profile">
    <el-alert
      v-if="forced"
      class="profile__force"
      type="warning"
      show-icon
      :closable="false"
      title="请先修改初始密码"
      description="当前密码由管理员发放，修改后才能继续使用其他功能。"
    />

    <el-card shadow="never">
      <template #header><span class="profile__title">账号信息</span></template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="用户名">{{ auth.user?.username }}</el-descriptions-item>
        <el-descriptions-item label="角色">{{ auth.roles.join('、') || '—' }}</el-descriptions-item>
        <el-descriptions-item label="最近登录">
          {{ auth.user?.last_login_at ? new Date(auth.user.last_login_at).toLocaleString() : '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="登录次数">{{ auth.user?.login_count ?? 0 }}</el-descriptions-item>
      </el-descriptions>

      <el-form class="profile__form" label-width="90px" @submit.prevent="saveProfile">
        <el-form-item label="显示名称">
          <el-input v-model="profile.display_name" placeholder="用于界面展示" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="profile.email" placeholder="用于找回密码" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="savingProfile" @click="saveProfile">保存资料</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <template #header><span class="profile__title">修改密码</span></template>
      <el-form class="profile__form" label-width="90px" @submit.prevent="savePassword">
        <el-form-item label="当前密码">
          <el-input v-model="password.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input
            v-model="password.new_password"
            type="password"
            show-password
            placeholder="至少 8 位，需含字母和数字"
          />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input
            v-model="password.confirm"
            type="password"
            show-password
            @keyup.enter="savePassword"
          />
        </el-form-item>
        <el-alert
          v-if="passwordError"
          class="profile__error"
          type="error"
          :closable="false"
          :title="passwordError"
        />
        <el-form-item>
          <el-button type="primary" :loading="savingPassword" @click="savePassword">
            修改密码
          </el-button>
          <span class="profile__note">修改后当前登录状态会失效，需要用新密码重新登录。</span>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.profile {
  display: grid;
  gap: 18px;
  max-width: 880px;
  margin: 0 auto;
  padding: 24px 20px 60px;
}

.profile__force {
  margin-bottom: 0;
}

.profile__title {
  font-weight: 600;
}

.profile__form {
  margin-top: 20px;
  max-width: 520px;
}

.profile__error {
  margin-bottom: 14px;
}

.profile__note {
  margin-left: 12px;
  color: #5c6972;
  font-size: 12px;
}
</style>
