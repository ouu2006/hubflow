// 路由:2026-10-11 架构裁定后的三层页面——态势大屏 /dashboard(第三层,收录两层产出)、
// 感知层 /perception(Issue #54)、决策层 /decision(Issue #59);均为公开直达页。
// 拥挤度热力 /heat(Issue #66,手册 §11.2 P0 页面:四级色 + 图例 + 更新时间戳,可切拥挤指数视图)。
// hash 模式:dist 交给后端同源托管时无需服务端 SPA fallback。

import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import DashboardView from '../views/dashboard/DashboardView.vue'
import DecisionView from '../views/decision/DecisionView.vue'
import HeatView from '../views/heat/HeatView.vue'
import PerceptionView from '../views/perception/PerceptionView.vue'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'dashboard', component: DashboardView, meta: { title: '交通态势大屏' } },
  { path: '/heat', name: 'heat', component: HeatView, meta: { title: '拥挤度热力' } },
  { path: '/perception', name: 'perception', component: PerceptionView, meta: { title: '感知检测画面' } },
  { path: '/decision', name: 'decision', component: DecisionView, meta: { title: '决策工作台' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${String(to.meta.title)} · hubflow 管理端` : 'hubflow 管理端'
})
