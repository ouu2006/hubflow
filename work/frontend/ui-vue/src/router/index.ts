// 路由:2026-10-11 架构裁定后仅存态势大屏(harness 四页登录/问答/文档/溯源已移除);
// 感知画面页 /perception 由 PR #56 分支携带,接口面按新规划定稿后一并重述。
// hash 模式:dist 交给后端同源托管时无需服务端 SPA fallback。

import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import DashboardView from '../views/dashboard/DashboardView.vue'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'dashboard', component: DashboardView, meta: { title: '交通态势大屏' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${String(to.meta.title)} · hubflow 管理端` : 'hubflow 管理端'
})
