// 全局设置（大屏工具条 / 地图自身）—— 目前四项：**矢量底图 / 方向标记 / 凸显路线 / 地图图例**。
// 前三项的开关在顶栏「设置」弹层里；第四项「地图图例」的入口在地图上（见下方注释）。
//
// 为什么要有第一个开关（业主 2026-10-16 口径）：
//   大屏地图现在是**一个渲染器**（MapLibre），但**底图这一层是可选的**：
//     · 开 = 矢量底图（OpenFreeMap，数据来自 OpenStreetMap）+ 描出的路网；
//     · 关 = **只画路网**（＝原先「示例路网」那个观感），**一个底图请求都不发**。
//   底图这一层挂掉也不影响路网：地图用**本地兜底样式**建图，路网照画（见 `MapLibreViewer.vue`）。
//
// 为什么要有「方向标记」开关（Issue IKP5BD）：
//   方向箭头是叠在路况色上的第二层语义，评审 / 截图时需要能整体关掉——
//   **关掉后一支箭头都不留**，图例同步写「已隐藏方向标记」（不能出现"关了但图例还在讲箭头"）。
//
// 为什么要有「凸显路线」开关（Issue IKP5CK）：
//   有推荐路线时，非路线段统一压成中性灰细线，路线才一眼找到；
//   但评审整体路况时仍要看满图四级色，所以开关默认**开**、关掉即恢复原观感。
//
// 为什么要有「地图图例」开关（业主 2026-10-19 口径，本分支新增）：
//   图例面板压在地图左下角、盖住路网，想看那一片就得先把面板收起来。
//   收起后**不丢功能**——地图工具条左下角会出现「图例 ▸」按钮，点了又展开。
//   与上面三个开关一样落 `localStorage`，刷新后仍是上次的样子。
//   ⚠️ 入口**只有地图自己**这一个（展开态是面板内的叉键、收起态是工具条的「图例 ▸」）；
//   顶栏「设置」弹层（`AppShell.vue`）目前只有底图 / 方向标记两开关，本分支**没有**动它。
//
// 记忆口径与站点包键 / 栏宽一致：落 `localStorage`；读不到、内容坏了**静默退回默认值**（开），
// 不抛错——Node 侧（mock 中间件）没有 `localStorage`，同样走默认值。
import { ref, type Ref } from 'vue'

/** 底图开关的存储键（带项目前缀，不与别的页串味） */
const KEY_BASEMAP = 'hubflow.settings.basemap'
/** 方向标记开关（Issue IKP5BD） */
const KEY_DIRECTIONS = 'hubflow.settings.directions'
/** 路线凸显开关（Issue IKP5CK） */
const KEY_ROUTE_EMPHASIS = 'hubflow.settings.routeEmphasis'
/** 地图图例展开/收起开关（业主 2026-10-19） */
const KEY_LEGEND = 'hubflow.settings.legend'

/** 矢量底图开关（默认**开**）；`false` = 只画路网，不拉任何底图资源 */
export const basemapEnabled: Ref<boolean> = ref(true)
/** 方向标记开关（默认**开**，Issue IKP5BD）；`false` = 地图上一支方向箭头都不画 */
export const directionsVisible: Ref<boolean> = ref(true)
/** 凸显路线开关（默认**开**，Issue IKP5CK）；`false` = 恢复满图等级色，不做非路线段压灰 */
export const routeEmphasisEnabled: Ref<boolean> = ref(true)
/**
 * 地图图例（左下角那块说明面板）是否展开（默认**开**，业主 2026-10-19 口径）。
 * 收起 / 展开两个方向都落 `localStorage`（`setLegendVisible()`），刷新后仍是上次的样子。
 */
export const legendVisible: Ref<boolean> = ref(true)

/**
 * 读一个布尔开关：只认 `1/0/true/false`，其他值（旧版本写的 / 手改坏了）走默认值。
 * 读写都包 try/catch：隐私模式、Node 侧没有 `localStorage` 时只影响"刷新后是否记得"。
 */
function readStoredBool(key: string, fallback: boolean): boolean {
  try {
    const raw = localStorage.getItem(key)
    if (raw === '1' || raw === 'true') return true
    if (raw === '0' || raw === 'false') return false
    return fallback
  } catch {
    return fallback
  }
}

function writeStoredBool(key: string, on: boolean): void {
  try {
    localStorage.setItem(key, on ? '1' : '0')
  } catch {
    /* 隐私模式等写不进去：只影响刷新后是否记得 */
  }
}

/** 启动时读回（入口 `main.ts` 在挂载前调一次） */
export function restoreSettings(): void {
  basemapEnabled.value = readStoredBool(KEY_BASEMAP, true)
  directionsVisible.value = readStoredBool(KEY_DIRECTIONS, true)
  routeEmphasisEnabled.value = readStoredBool(KEY_ROUTE_EMPHASIS, true)
  legendVisible.value = readStoredBool(KEY_LEGEND, true)
}

/** 切换底图并落盘（写不进去不影响本次会话内的切换） */
export function setBasemapEnabled(on: boolean): void {
  basemapEnabled.value = on
  writeStoredBool(KEY_BASEMAP, on)
}

/** 切换方向标记并落盘（Issue IKP5BD） */
export function setDirectionsVisible(on: boolean): void {
  directionsVisible.value = on
  writeStoredBool(KEY_DIRECTIONS, on)
}

/** 切换「凸显路线」并落盘（Issue IKP5CK） */
export function setRouteEmphasisEnabled(on: boolean): void {
  routeEmphasisEnabled.value = on
  writeStoredBool(KEY_ROUTE_EMPHASIS, on)
}

/** 收起 / 展开地图图例并落盘（业主 2026-10-19） */
export function setLegendVisible(on: boolean): void {
  legendVisible.value = on
  writeStoredBool(KEY_LEGEND, on)
}
