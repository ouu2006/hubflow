// 路由:2026-10-11 架构裁定后存态势大屏 + 感知层页面(harness 四页登录/问答/文档/溯源已移除);
// 感知画面页 /perception(Issue #54)与态势大屏同为公开直达页。
// hash 模式:dist 交给后端同源托管时无需服务端 SPA fallback。

import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import DashboardView from '../views/dashboard/DashboardView.vue'
import PerceptionView from '../views/perception/PerceptionView.vue'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'dashboard', component: DashboardView, meta: { title: '交通态势大屏' } },
  { path: '/perception', name: 'perception', component: PerceptionView, meta: { title: '感知检测画面' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${String(to.meta.title)} · hubflow 管理端` : 'hubflow 管理端'
})
