<script setup lang="ts">
import { ChatDotRound, Document, SwitchButton } from '@element-plus/icons-vue'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getHealth } from './api'
import type { Health } from './shared/protocol'
import { clearAuth, getSavedUser } from './stores/auth'

// 应用壳:顶栏(导航 + MOCK 徽标 + health 轮询 + 用户/退出);登录页不显示壳。
const route = useRoute()
const router = useRouter()
const isMock = import.meta.env.VITE_USE_MOCK !== '0'
const user = getSavedUser()

const health = ref<Health | null>(null)
const healthDead = ref(false)
let timer: ReturnType<typeof setInterval> | undefined

async function poll(): Promise<void> {
  try {
    health.value = await getHealth()
    healthDead.value = false
  } catch {
    healthDead.value = true
  }
}

onMounted(() => {
  void poll()
  timer = setInterval(() => void poll(), 30000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})

// 大屏(Issue #52)全屏沉浸、自带顶栏,同样不显示管理台壳。
const showChrome = computed(() => route.path !== '/login' && route.path !== '/dashboard')
const healthText = computed(() =>
  healthDead.value ? '不可达' : health.value ? `内核 ${health.value.kernel} · DB ${health.value.db}` : '检测中…',
)
const healthState = computed<'up' | 'down'>(() =>
  healthDead.value || health.value?.kernel === 'down' ? 'down' : 'up',
)

function logout(): void {
  clearAuth()
  void router.replace('/login')
}
</script>

<template>
  <el-container class="app">
    <el-header v-if="showChrome" class="app-header" height="56px">
      <div class="brand">
        <span class="logo">◈</span>
        <span class="name">harness-core 管理后台</span>
        <el-tag v-if="isMock" size="small" type="warning" effect="dark">MOCK</el-tag>
      </div>
      <el-menu mode="horizontal" :default-active="route.path" router class="app-menu" :ellipsis="false">
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          问答对话
        </el-menu-item>
        <el-menu-item index="/documents">
          <el-icon><Document /></el-icon>
          文档管理
        </el-menu-item>
      </el-menu>
      <div class="right">
        <span class="health" :class="healthState">
          <i class="dot" />
          {{ healthText }}
        </span>
        <el-tag v-if="user" size="small" type="info" effect="plain">{{ user }}</el-tag>
        <el-button link :icon="SwitchButton" @click="logout()">退出</el-button>
      </div>
    </el-header>
    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<style scoped>
.app {
  height: 100vh;
}
.app-header {
  display: flex;
  align-items: center;
  gap: 24px;
  border-bottom: 1px solid var(--el-border-color-light);
  background: #fff;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}
.brand .logo {
  color: var(--el-color-primary);
  font-size: 20px;
}
.brand .name {
  font-weight: 600;
  font-size: 15px;
  color: #1f2d3d;
}
.app-menu {
  border-bottom: none;
  flex: 1;
  min-width: 0;
}
.right {
  display: flex;
  align-items: center;
  gap: 12px;
  white-space: nowrap;
}
.health {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #909399;
}
.health .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.health.up .dot {
  background: var(--el-color-success);
  box-shadow: 0 0 0 3px var(--el-color-success-light-8);
}
.health.down .dot {
  background: var(--el-color-danger);
  box-shadow: 0 0 0 3px var(--el-color-danger-light-8);
}
.app-main {
  padding: 0;
  background: var(--el-bg-color-page);
  overflow: hidden;
}
</style>
