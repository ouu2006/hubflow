// 路线 `steps` 的浏览器侧缓存（lead 2026-10-29 拍板）。
//
// 背景：`/route/options`、`/route/recommend` 的 `arrival_route` **不带 steps / start_point**
// （契约字段集不动：一改就要业主侧全量回归），而路线箭头要的是**后端权威行进序**。
// 正解是 drik 非契约端点 `GET /api/traffic/route/{request_id}/steps` 单拉一份，一次拿全
// arrival / departure / pickup / alternatives 的 steps。
//
// 为什么不用 pinia：本项目**没有装 pinia**（`package.json` 只有 vue / vue-router / element-plus /
// maplibre-gl），为了一个缓存引入新运行时依赖不划算。这里用模块级 Map，语义等价于
// "按 request_id 键的全局缓存"：同一 request_id 全站只拉一次，跨页面/跨组件共享。
//
// 三条硬规矩（对应 lead 的要求）：
//   ① **只拉一次**：成功结果常驻；在途请求去重（同一 id 并发只发一个 fetch）；
//   ② **失败可见**：失败不缓存成"空数据"当没事，而是记失败时间 + 交给调用方打日志；
//      失败后 `RETRY_AFTER_MS` 内不再重试，避免每次渲染都去捅一个挂掉的端点；
//   ③ **兜底要留痕**：`ensureRouteSteps()` 返回 `null` 就是"该请求没有权威 steps"，
//      调用方必须走链式定向并打 `[route-arrows] steps unavailable for <id>, …`。
import { getRouteSteps } from '../api/traffic'
import { activePackKey } from '../station-packs/index'
import type { RouteStepsSnapshot } from './traffic'

/**
 * 缓存键 = `包键::request_id`。
 * 为什么带包键：两站（Z / GZ）的 `request_id` 形如 `REQ-REAL-0001`，**会撞号**；不带包键就会出现
 * "把 Z 的权威 steps 贴到 GZ 的线上"（和 Issue IKPFR4 里那次跨站串数据同一类错误）。
 */
function keyOf(requestId: string): string {
  return `${activePackKey()}::${requestId}`
}

/** 成功后常驻的缓存：包键::request_id → 快照 */
const cache = new Map<string, RouteStepsSnapshot>()
/** 在途请求（同一 request_id 并发去重） */
const inflight = new Map<string, Promise<RouteStepsSnapshot | null>>()
/** 失败记录：包键::request_id → 失败时刻（毫秒） */
const failedAt = new Map<string, number>()
/** 失败后的冷却窗口：窗口内不重试，避免挂掉的端点被每次渲染反复捅 */
const RETRY_AFTER_MS = 30_000

/** 缓存里**已有**的快照（同步读，供 computed 用；没有就 null） */
export function cachedRouteSteps(requestId: string | null | undefined): RouteStepsSnapshot | null {
  if (!requestId) return null
  return cache.get(keyOf(requestId)) ?? null
}

/** 该 request_id 是不是刚失败过（冷却窗口内），供调用方决定要不要直接走兜底 */
export function routeStepsRecentlyFailed(requestId: string | null | undefined): boolean {
  if (!requestId) return false
  const at = failedAt.get(keyOf(requestId))
  return at !== undefined && Date.now() - at < RETRY_AFTER_MS
}

/**
 * 取某请求的 steps 快照；拿不到返回 `null`（**不抛异常**）。
 * 超时 / 404 / 字段缺失都算拿不到 —— 由调用方决定兜底并打日志。
 */
export async function ensureRouteSteps(
  requestId: string | null | undefined,
): Promise<RouteStepsSnapshot | null> {
  if (!requestId) return null
  const key = keyOf(requestId)
  const hit = cache.get(key)
  if (hit) return hit
  const running = inflight.get(key)
  if (running) return running
  if (routeStepsRecentlyFailed(requestId)) return null

  const task = (async (): Promise<RouteStepsSnapshot | null> => {
    try {
      const snap = await getRouteSteps(requestId)
      // 形状校验：`routes` 缺了或一条 steps 都没有 ⇒ 当作"没有权威 steps"，不进缓存
      if (!snap || typeof snap !== 'object' || !snap.routes || !hasAnySteps(snap)) {
        failedAt.set(key, Date.now())
        return null
      }
      cache.set(key, snap)
      failedAt.delete(key)
      return snap
    } catch {
      failedAt.set(key, Date.now())
      return null
    } finally {
      inflight.delete(key)
    }
  })()

  inflight.set(key, task)
  return task
}

/** 快照里是否至少有一条路线带非空 `steps[]` */
export function hasAnySteps(snap: RouteStepsSnapshot | null): boolean {
  const r = snap?.routes
  if (!r) return false
  const one = (x: { steps?: unknown[] | null } | null | undefined): boolean =>
    Array.isArray(x?.steps) && (x!.steps as unknown[]).length > 0
  return (
    one(r.arrival_route) ||
    one(r.departure_route) ||
    one(r.pickup_route) ||
    (Array.isArray(r.alternatives) && r.alternatives.some((a) => one(a)))
  )
}

/** 清缓存（切站 / 切包时用：不同包的同名 request_id 不能复用） */
export function resetRouteStepsCache(): void {
  cache.clear()
  inflight.clear()
  failedAt.clear()
}
