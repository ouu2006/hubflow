// 顶栏页签目录(顶栏与路由共用一处,避免两处各写一份导致漂移)。
export const APP_TABS = [
  { key: 'dashboard', name: '态势总览', route: '/dashboard' },
  { key: 'heat', name: '拥挤度热力', route: '/heat' },
  { key: 'decision', name: '决策工作台', route: '/decision' },
  { key: 'perception', name: '视频感知', route: '/perception' },
] as const

export type AppTabKey = (typeof APP_TABS)[number]['key']

/** 数据源视图(TC-19 展示侧:同一路段可并排展示 video / twin 两个来源) */
export type SourceMode = 'video' | 'twin' | 'both'

export const SOURCE_ITEMS: { key: SourceMode; name: string }[] = [
  { key: 'video', name: '视频链路' },
  { key: 'twin', name: '孪生链路' },
  { key: 'both', name: '并排' },
]

/** 顶栏常驻口径角标(手册:页面必须标「演示数据(模拟)· 双数据源」) */
export const DEMO_BADGE = '演示数据(模拟)· 双数据源(视频链路 + 孪生链路)'
