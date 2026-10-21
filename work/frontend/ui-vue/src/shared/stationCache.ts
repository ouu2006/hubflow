// 站点快照缓存（Issue IKPFR4，业主 2026-10-21 裁定）——**只在内存里，不进 localStorage**。
//
// 要解决的事：切站过去必须整页刷新，因为路网几何 / 站点名 / 快照全是 setup 期拍下来的。
// 改成原地切站之后，切过去总得先有东西画 —— 没有缓存就只能白屏等网络。
// 所以两站各留一份**首批快照**在内存里，切站时同步吃缓存秒开，随后后台刷新按字段替换。
//
// 为什么**不进 localStorage**（业主裁定原文口径）：缓存快照是会过期的数据 ——
// 落到磁盘上，用户隔天打开就会看到"昨天的路况"且没人能察觉；只放内存，页面一关就没了，
// 最坏情况也只是回落到"没缓存 → 骨架屏 → 拉最新"，不会撒谎。
//
// 失效规则（只有两条，写死在代码里，不留可配项）：
//   ① 页面进程结束即全部失效（内存 Map 的自然属性）；
//   ② 条目超过 `CACHE_TTL_MS` 视为过期：`readStationCache()` 直接返回 null（宁缺毋滥）。
//
// ⚠️ 缓存**只按包键分桶**，不按"当前活跃站"复用：`writeStationCache(key, …)` 的 key 是
//    这次数据配属的站键。预热别站时靠 `SnapshotFetchOptions.station` 钉住请求的站，
//    否则会把本站的响应写进别站的桶里 —— 那就是"把 Z 的数据当 GZ 显示"。

import {
  getTrafficAlerts,
  getTrafficFactors,
  getTrafficMeta,
  getTrafficOverview,
  getTrafficSegments,
  getTrafficThresholds,
} from '../api/traffic'
import { PACKS } from '../station-packs/index'
import type {
  AlertsSnapshot,
  FactorApplied,
  HeatMatrix,
  SegmentsSnapshot,
  ThresholdSnapshot,
  TrafficMeta,
  TrafficOverview,
} from './traffic'

/**
 * 一站的首批快照（字段名照 `shared/traffic.ts` 的类型取，不另造一套）。
 *
 * 为什么只留这几项：切站首屏要用的是「路网段数 / KPI / 站点名 / 路段列表 / 告警 / 图例口径」，
 * 它们分别来自 overview / segments / meta / thresholds / alerts / factors；
 * 热力矩阵(matrix)与车辆动点(vehicles)也存一份，前者是首屏底部必现的，
 * 后者是**高频变化的位置流**，缓存了反而会在切站瞬间出现"幽灵车"，故不入缓存。
 */
export interface StationSnapshotCache {
  /** 这份数据配属的站键（与 Map 的 key 同值，写读两侧都校验） */
  key: string
  overview: TrafficOverview | null
  segments: SegmentsSnapshot | null
  meta: TrafficMeta | null
  thresholds: ThresholdSnapshot | null
  alerts: AlertsSnapshot | null
  /** 全网生效因素（各路段 factors_applied 展平，与大屏 KPI 第 4 格同源） */
  factors: (FactorApplied & { segment_id: string })[] | null
  matrix: HeatMatrix | null
  /** 写入时刻（ms）：只用于"这缓存有多旧"的展示与 TTL 判断 */
  ts: number
}

/** 缓存条目有效期（10 min）。超了就当没有 —— 快照数据不该被当成当前态势。 */
export const CACHE_TTL_MS = 10 * 60_000
/** 写入后这么短时间内不重复预热（避免首屏刚刷完又替同一站拉一遍） */
const CACHE_FRESH_MS = 15_000

const store = new Map<string, StationSnapshotCache>()

/** 读一站的缓存；没有 / 过期 / 站键对不上 → null（调用方据此走骨架屏） */
export function readStationCache(key: string): StationSnapshotCache | null {
  const hit = store.get(key)
  if (!hit) return null
  if (hit.key !== key) return null
  if (Date.now() - hit.ts > CACHE_TTL_MS) {
    store.delete(key)
    return null
  }
  return hit
}

/**
 * 按字段合并写入（只覆盖传进来的字段）。
 * 为什么要合并而不是整份替换：刷新是 8 个接口并发的，某个接口失败时不该把它上一次
 * 好数据一起抹掉（页面上的"上一版"标注由大屏 `failedPanels` 负责，不是缓存的事）。
 */
export function writeStationCache(key: string, patch: Partial<Omit<StationSnapshotCache, 'key' | 'ts'>>): void {
  if (!PACKS[key]) return
  const prev = store.get(key)
  const base: StationSnapshotCache =
    prev && prev.key === key
      ? prev
      : {
          key,
          overview: null,
          segments: null,
          meta: null,
          thresholds: null,
          alerts: null,
          factors: null,
          matrix: null,
          ts: 0,
        }
  store.set(key, { ...base, ...patch, key, ts: Date.now() })
}

/** 清掉一站 / 全部缓存（站包自检、调试用；正常链路没人调） */
export function clearStationCache(key?: string): void {
  if (key) store.delete(key)
  else store.clear()
}

/** 缓存有多旧（秒）；没有缓存返回 null —— 页脚 / 提示条据此写"缓存 xs 前" */
export function cacheAgeSeconds(key: string): number | null {
  const hit = readStationCache(key)
  if (!hit) return null
  return Math.max(0, Math.round((Date.now() - hit.ts) / 1000))
}

/**
 * 替**一个站**拉首批快照并写进缓存。
 *
 * 三件事都写死在这里，不留给调用方拼：
 *   ① 一律通过 `station` 选项把请求钉在目标站（否则拿到的是当前站的响应）；
 *   ② 全部用 `Promise.allSettled`：某个接口挂了就保留该字段为空，**不因为一个字段
 *      拖垮整份缓存**（切站时"有 KPI 没告警"远好过"什么都没有"）；
 *   ③ 失败**静默**：预热是加分项，不该在页面上弹错、也不该进 `failedPanels`。
 */
export async function prefetchStation(key: string, signal?: AbortSignal): Promise<StationSnapshotCache | null> {
  if (!PACKS[key]) return null
  const opts = { station: key, signal }
  const [ov, seg, meta, thr, al, fa] = await Promise.allSettled([
    getTrafficOverview(opts),
    getTrafficSegments(opts),
    getTrafficMeta(opts),
    getTrafficThresholds(opts),
    getTrafficAlerts(opts),
    getTrafficFactors(undefined, opts),
  ])
  if (signal?.aborted) return null
  const patch: Partial<Omit<StationSnapshotCache, 'key' | 'ts'>> = {}
  if (ov.status === 'fulfilled') patch.overview = ov.value
  if (seg.status === 'fulfilled') patch.segments = seg.value
  if (meta.status === 'fulfilled') patch.meta = meta.value
  if (thr.status === 'fulfilled') patch.thresholds = thr.value
  if (al.status === 'fulfilled') patch.alerts = al.value
  if (fa.status === 'fulfilled') patch.factors = fa.value.factors
  // 一个字段都没拿到 = 接口层没起 / 全挂：不写空壳，免得下次切站"有缓存却是空的"
  if (Object.keys(patch).length === 0) return null
  writeStationCache(key, patch)
  return readStationCache(key)
}

/**
 * 两站常驻预热（业主裁定：允许两站常驻预热缓存）。
 *
 * 时机：首屏 `refresh()` 成功之后，`requestIdleCallback`（浏览器空闲）或 **1 s 兜底** ——
 * 预热不能抢首屏带宽，否则"秒开"是用首屏变慢换来的。
 * 跳过条件：该站缓存刚写过（`CACHE_FRESH_MS` 内），避免首屏刷完马上又拉一遍同一站。
 */
export function prewarmStations(keys: string[] = Object.keys(PACKS)): void {
  for (const key of keys) {
    const hit = store.get(key)
    // 刚写过的（当前站，由 `refresh()` 写）跳过：不为同一份数据再打一轮接口
    if (hit && Date.now() - hit.ts < CACHE_FRESH_MS) continue
    void prefetchStation(key).catch(() => {
      /* 预热失败静默：切到该站时自然会走骨架屏 + 正常刷新链路 */
    })
  }
}

/**
 * 把预热排到首屏之后：有 `requestIdleCallback` 就用它（浏览器空闲时跑，最迟 2 s），
 * 没有就用 `setTimeout` 1 s 兜底 —— Safari 与部分内嵌 WebView 至今没有前者。
 */
export function schedulePrewarm(): void {
  type IdleWindow = Window & {
    requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number
  }
  const w = window as IdleWindow
  if (typeof w.requestIdleCallback === 'function') {
    w.requestIdleCallback(() => prewarmStations(), { timeout: 2000 })
    return
  }
  window.setTimeout(() => prewarmStations(), 1000)
}
