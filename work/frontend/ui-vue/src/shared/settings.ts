// 全局设置（顶栏「设置」）—— 目前只有一项：**矢量底图开关**。
//
// 为什么要有这个开关（业主 2026-10-16 口径）：
//   大屏地图现在是**一个渲染器**（MapLibre），但**底图这一层是可选的**：
//     · 开 = 矢量底图（OpenFreeMap，数据来自 OpenStreetMap）+ 描出的路网；
//     · 关 = **只画路网**（＝原先「示例路网」那个观感），**一个底图请求都不发**。
//   底图这一层挂掉也不影响路网：地图用**本地兜底样式**建图，路网照画（见 `MapLibreViewer.vue`）。
//
// 记忆口径与站点包键 / 栏宽一致：落 `localStorage`；读不到、内容坏了**静默退回默认值**（开），
// 不抛错——Node 侧（mock 中间件）没有 `localStorage`，同样走默认值。
import { ref, type Ref } from 'vue'

/** 底图开关的存储键（带项目前缀，不与别的页串味） */
const KEY = 'hubflow.settings.basemap'

/** 矢量底图开关（默认**开**）；`false` = 只画路网，不拉任何底图资源 */
export const basemapEnabled: Ref<boolean> = ref(true)

/** 启动时读回（入口 `main.ts` 在挂载前调一次） */
export function restoreSettings(): void {
  try {
    const raw = localStorage.getItem(KEY)
    if (raw === '1' || raw === 'true') basemapEnabled.value = true
    else if (raw === '0' || raw === 'false') basemapEnabled.value = false
    // 其他值（旧版本写的 / 手改坏了）= 默认值，不算错
  } catch {
    /* localStorage 不可用（隐私模式 / Node 侧）：用默认值 */
  }
}

/** 切换并落盘（写不进去不影响本次会话内的切换） */
export function setBasemapEnabled(on: boolean): void {
  basemapEnabled.value = on
  try {
    localStorage.setItem(KEY, on ? '1' : '0')
  } catch {
    /* 隐私模式等写不进去：只影响刷新后是否记得 */
  }
}
