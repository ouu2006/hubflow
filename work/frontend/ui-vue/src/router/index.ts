// 路由:2026-10-13 三页收敛(Issue #77)——**感知层 → 决策层 → 监控大屏**三层,不再有第四页。
//   监控大屏 /dashboard(第三层):左「选择监控」/ 中「全路段状态」/ 右「路段信息」/ 底部「热力带 + 告警」,
//     原 `/heat` 拥挤度热力页**已并入本页**(视图切换 + 档位分布 + 热力矩阵 + CI 色阶全在底部热力带);
//   决策层 /decision(第二层):决策可视化 / 处置队列 / 效果对比三视图;
//   感知层 /perception(第一层):YOLO 链路 + 环境上下文 + 数据供给对照。
// 均为公开直达页;hash 模式:dist 交给后端同源托管时无需服务端 SPA fallback。

import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import DashboardView from '../views/dashboard/DashboardView.vue'
import DecisionView from '../views/decision/DecisionView.vue'
import PerceptionView from '../views/perception/PerceptionView.vue'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/dashboard' },
  { path: '/perception', name: 'perception', component: PerceptionView, meta: { title: '感知层' } },
  { path: '/decision', name: 'decision', component: DecisionView, meta: { title: '决策层' } },
  { path: '/dashboard', name: 'dashboard', component: DashboardView, meta: { title: '监控大屏' } },
  // 旧的四页划分里的 /heat(Issue #66 独立页)已并入 /dashboard(Issue #77):老书签 / 外链一律回大屏,
  // 不留 404 —— 演示现场有人按旧地址进不来是最没必要的事故。
  { path: '/heat', redirect: '/dashboard' },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${String(to.meta.title)} · hubflow 管理端` : 'hubflow 管理端'
})
