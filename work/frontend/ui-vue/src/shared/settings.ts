// 全局设置（顶栏「设置」）—— 目前三项：**矢量底图开关**、**地图图例开关**、**方向箭头开关**。
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

/** 地图图例开关的存储键 */
const KEY_LEGEND = 'hubflow.settings.legend'

/** 方向箭头开关的存储键 */
const KEY_DIRECTIONS = 'hubflow.settings.directions'

/** 矢量底图开关（默认**开**）；`false` = 只画路网，不拉任何底图资源 */
export const basemapEnabled: Ref<boolean> = ref(true)

/**
 * 地图图例（左下角那块说明面板）是否展开（默认**开**）。
 *
 * 为什么要能收（业主 2026-10-19 口径）：图例压在地图左下角、盖住路网，
 * 想看那一片的车流就得先把面板收起来。收起后**不丢功能**——地图工具条
 * 「Z · 61 段」左边会出现一个「图例」按钮，点了又展开（见 `DashboardView.vue`）。
 * 两个方向都落 `localStorage`，刷新后仍是上次的样子。
 */
export const legendVisible: Ref<boolean> = ref(true)

/**
 * 地图上的**方向箭头**是否显示（默认**开**）。
 *
 * 为什么要能关（业主 2026-10-19 口径）：路网稠密 / 缩放很小的时候，方向箭头会
 * 一根接一根堆在一起，把底下的路段线盖住。现在低缩放已经让箭头跟着地图一起缩
 * （见 `MapLibreViewer.vue` 的 `directionLayerSpec()`），但"完全不想看箭头"也是
 * 一个正当诉求 —— 关掉就是关掉，不是调小。
 * 同样落 `localStorage`，刷新后仍是上次的样子。
 */
export const directionsVisible: Ref<boolean> = ref(true)

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
  try {
    const raw = localStorage.getItem(KEY_LEGEND)
    if (raw === '1' || raw === 'true') legendVisible.value = true
    else if (raw === '0' || raw === 'false') legendVisible.value = false
    // 其他值 = 默认值（展开），不算错
  } catch {
    /* 同上 */
  }
  try {
    const raw = localStorage.getItem(KEY_DIRECTIONS)
    if (raw === '1' || raw === 'true') directionsVisible.value = true
    else if (raw === '0' || raw === 'false') directionsVisible.value = false
    // 其他值 = 默认值（显示），不算错
  } catch {
    /* 同上 */
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

/** 收起 / 展开地图图例，并落盘（同上：写不进去只影响刷新后是否记得） */
export function setLegendVisible(on: boolean): void {
  legendVisible.value = on
  try {
    localStorage.setItem(KEY_LEGEND, on ? '1' : '0')
  } catch {
    /* 同上 */
  }
}

/** 显示 / 隐藏地图上的方向箭头，并落盘（同上） */
export function setDirectionsVisible(on: boolean): void {
  directionsVisible.value = on
  try {
    localStorage.setItem(KEY_DIRECTIONS, on ? '1' : '0')
  } catch {
    /* 同上 */
  }
}
