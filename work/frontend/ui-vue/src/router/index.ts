// 三页路由(04 任务书 §1):文档上传 / 问答对话 / 溯源引用。
// hash 模式:dist 由 FastAPI StaticFiles 同源挂载时无需服务端 SPA fallback(S-6 零负担)。

import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import { getToken } from '../stores/auth'
import ChatView from '../views/ChatView.vue'
import DocumentsView from '../views/DocumentsView.vue'
import LoginView from '../views/LoginView.vue'
import TraceView from '../views/TraceView.vue'

const routes: RouteRecordRaw[] = [
  { path: '/login', name: 'login', component: LoginView, meta: { title: '登录' } },
  { path: '/', redirect: '/chat' },
  { path: '/chat', name: 'chat', component: ChatView, meta: { title: '问答对话' } },
  { path: '/documents', name: 'documents', component: DocumentsView, meta: { title: '文档管理' } },
  { path: '/trace/:answerId', name: 'trace', component: TraceView, meta: { title: '溯源引用' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach((to) => {
  const authed = getToken() !== null
  if (to.path !== '/login' && !authed) return { path: '/login' }
  if (to.path === '/login' && authed) return { path: '/chat' }
  return true
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${String(to.meta.title)} · harness-core` : 'harness-core'
})
