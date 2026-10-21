// 切站唯一入口（Issue IKPFR4）——顶栏「线路图切换器」与监控大屏工具条**共用这一支**。
//
// 为什么要有这个文件：切站此前是两处各写一遍 `switchPack(key)` + `window.location.reload()`，
// 于是"换个站"= 重新下载整个文档、重建地图、重拉底图。现在改成**原地切站**，顺序不能乱，
// 所以收成一个函数，两处入口都只调用它：
//
//   ① `switchPack(key)` —— 换包键、`version++`、通知订阅者（几何相关的 setup 快照据此重建）；
//   ② `resetNetwork()` —— 路网几何按新包重建（地图只换 GeoJSON data，不重建 Map、不 setStyle）；
//   ③ 站内状态**一律重置**（业主 2026-10-21 裁定：selectedId / hover / 路线 session /
//      热力选中 / 深链选中 / 滚动到顶部，**不做**跨站恢复）+ 中止在途请求；
//   ④ **缓存优先**：同步吃内存缓存渲染首屏（热缓存 ≤0.3 s 可见），无缓存才让页面走骨架屏；
//   ⑤ 后台立刻补拉一次（不等 SSE 的下一个 2 s tick）；
//   ⑥ 同步 URL `?pack=`（深链可分享、刷新后仍停在该站）。
//
// ⚠️ 这里**不重建地图实例、不 setStyle**：底图瓦片是跨站可复用的公共资源，重建一次就是
//    几 MB 重新下载 + 一次白屏 —— 那正是本单要消灭的。
//
// ⚠️ 非大屏页面（决策层 / 感知层）没有注册 hook：它们的快照在 setup 期取，走"同路由重挂载"
//    兜底（`stationRemountKey`，见 `App.vue`）—— 组件重新 setup、数据按新包重取，
//    但**不重新请求文档**，也不算整页刷新。

import { ref } from 'vue'
import { PACKS, activePackKey, switchPack } from '../station-packs/index'
import { resetNetwork } from './demoNetwork'
import { readStationCache, schedulePrewarm, type StationSnapshotCache } from './stationCache'

/** URL 上的站键参数名（深链 `#/dashboard?pack=GZ`） */
export const PACK_QUERY_KEY = 'pack'

/**
 * 页面级切站钩子（由监控大屏注册）。
 * 三个回调的**调用顺序**是契约，见文件头时序：reset → applyCached → refresh。
 */
export interface StationSwitchHooks {
  /** 站内状态一律重置 + 中止在途请求（不跨站恢复任何选中态） */
  resetStationState(): void
  /**
   * 缓存优先渲染：`snapshot` 为该站的缓存快照；`null` = 没有缓存（页面据此显示骨架屏）。
   * 必须是**同步**的 —— 秒开靠的就是"不等网络先把能画的画出来"。
   */
  applyCachedSnapshot(snapshot: StationSnapshotCache | null): void
  /** 后台刷新（新数据到达后按字段替换；不阻塞首屏） */
  refresh(): void
}

let hooks: StationSwitchHooks | null = null

/**
 * 注册 / 注销页面钩子。返回注销函数，组件 `onUnmounted` 必须调用 ——
 * 否则切页后旧组件的钩子还挂着，切站会往一个已经卸载的页面里写数据。
 */
export function bindStationSwitch(next: StationSwitchHooks): () => void {
  hooks = next
  return () => {
    if (hooks === next) hooks = null
  }
}

/**
 * 没有注册钩子的页面（决策层 / 感知层）的兜底：让 `App.vue` 的 `<router-view>` 换 key，
 * 组件重新 setup（数据按新包重取），但**不重新请求文档**、不重下底图。
 */
export const stationRemountKey = ref(0)

/** 从当前 URL 读 `?pack=`（hash 路由下参数在 hash 里；也兼容真实的 search 段） */
export function readPackKeyFromUrl(): string | null {
  if (typeof window === 'undefined') return null
  const fromSearch = new URLSearchParams(window.location.search).get(PACK_QUERY_KEY)
  if (fromSearch && PACKS[fromSearch]) return fromSearch
  const hash = window.location.hash || ''
  const q = hash.indexOf('?')
  if (q < 0) return null
  const fromHash = new URLSearchParams(hash.slice(q + 1)).get(PACK_QUERY_KEY)
  return fromHash && PACKS[fromHash] ? fromHash : null
}

/**
 * 把当前站键写回 URL（hash 路由：`#/dashboard?segment=…&pack=GZ`）。
 * 用 `history.replaceState` 而不是 `router.push`：URL 要跟着变，但**不该触发一次路由跳转**
 * （那会把页面组件重建一遍，等于把刚省下来的刷新又加回去）。
 */
export function syncPackUrl(key: string): void {
  if (typeof window === 'undefined') return
  try {
    const url = new URL(window.location.href)
    const rawHash = url.hash || '#/dashboard'
    const hashBody = rawHash.replace(/^#/, '')
    const q = hashBody.indexOf('?')
    const path = q < 0 ? hashBody : hashBody.slice(0, q)
    const params = new URLSearchParams(q < 0 ? '' : hashBody.slice(q + 1))
    if (params.get(PACK_QUERY_KEY) === key) return
    params.set(PACK_QUERY_KEY, key)
    url.hash = `#${path}?${params.toString()}`
    window.history.replaceState(window.history.state, '', url.toString())
  } catch {
    /* 地址栏不可写（内嵌 WebView 等）：不影响切站本身，只是深链不更新 */
  }
}

/**
 * 换站（唯一入口）。
 *
 * 返回值：`true` = 真的换了；`false` = 键不合法或与当前站相同（重复点同一个站不重跑一遍流程）。
 */
export function switchStation(key: string): boolean {
  if (!PACKS[key]) return false
  const prev = activePackKey()
  if (key === prev) return false

  // ① 换包并广播：订阅者（地图 / 面板）只更新自己的响应式 ref，真正的重绘在下一个微任务
  switchPack(key)
  // ② 路网几何按新包重建。放在广播之后：`switchPack` 的通知只改 ref，Vue 的 watch 在微任务里才跑，
  //    等它跑到时几何已经是新包的了（`demoNetwork.ensureInit` 还会按包键自校验，双保险）
  resetNetwork()

  if (hooks) {
    // ③ 站内状态一律重置（含中止在途请求）→ ④ 缓存优先渲染 → ⑤ 后台补拉
    hooks.resetStationState()
    const snapshot = readStationCache(key)
    hooks.applyCachedSnapshot(snapshot)
    hooks.refresh()
  } else {
    // 非大屏页面：同路由重挂载兜底（组件重新 setup，按新包重取数据；不重新请求文档）
    stationRemountKey.value += 1
  }

  // ⑥ URL 深链同步
  syncPackUrl(key)
  // ⑦ 站在新站上，顺手把其余站的缓存补齐（空闲时；失败静默）
  schedulePrewarm()
  return true
}
