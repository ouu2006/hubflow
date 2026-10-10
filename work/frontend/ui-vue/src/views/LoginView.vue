<script setup lang="ts">
import { Lock, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../api'
import { setAuth } from '../stores/auth'

// 登录深度按 04 任务书 §6 裁定:登录框 + token 附加请求头即可,鉴权语义归 B 轨。
const router = useRouter()
const isMock = import.meta.env.VITE_USE_MOCK !== '0'

const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({ user: '', password: '' })
const rules: FormRules = {
  user: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit(): Promise<void> {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  loading.value = true
  try {
    const { token } = await login(form.user, form.password)
    setAuth(token, form.user)
    ElMessage.success('登录成功')
    void router.replace('/')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card" shadow="always">
      <div class="login-title">
        <span class="logo">◈</span>
        <h1>harness-core 管理后台</h1>
        <p class="sub">文档上传 · 问答对话(SSE 流式) · 溯源引用</p>
      </div>
      <el-alert
        v-if="isMock"
        class="mock-tip"
        title="mock 模式:任意非空凭据即可登录(token 为假值)"
        type="info"
        :closable="false"
      />
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="submit"
      >
        <el-form-item label="用户名" prop="user">
          <el-input v-model="form.user" :prefix-icon="User" placeholder="用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            :prefix-icon="Lock"
            show-password
            placeholder="密码"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button class="login-btn" type="primary" native-type="submit" :loading="loading">
          登 录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(160deg, #10182a 0%, #1d2b45 55%, #24405e 100%);
}
.login-card {
  width: 400px;
  padding: 8px 12px 4px;
}
.login-title {
  text-align: center;
  margin-bottom: 18px;
}
.login-title .logo {
  font-size: 34px;
  color: #409eff;
}
.login-title h1 {
  font-size: 20px;
  margin: 6px 0 4px;
  color: #1f2d3d;
}
.login-title .sub {
  margin: 0;
  font-size: 12px;
  color: #8492a6;
}
.mock-tip {
  margin-bottom: 16px;
}
.login-btn {
  width: 100%;
  margin-top: 4px;
}
</style>
