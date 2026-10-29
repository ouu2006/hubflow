// 路线「行进箭头」的几何整理（2026-10-29 方案 §3；业主：路线上一支方向箭头都没有，
// 后端标的向对不对，肉眼根本无法验证 —— 这块就是补这个可验证性）。
//
// 三条口径，按优先级用：
//   ① **首选后端 `steps[].geometry`**（接口层已按行车顺序排好，reverse 段也是正向）——
//      前端不再自己判向，避免两份方向解释打架。真接口的正路是
//      `GET /api/traffic/route/{request_id}/steps`（非契约只读端点；`/route/recommend` 的
//      响应是白名单形状，`steps` 被接口层剥掉了，所以大屏那条推荐线从这里取几何）；
//   ② 没有 steps（老链路 / mock / 端点 404）→ 按**链式连通性**定向：一段的终点接下一段
//      的起点，一串到底；**禁止**直接按 `coords` 顺序画（那是几何方向，不是行车方向）；
//   ③ reverse 段（包内 `direction='backward'`，topology 里叫 `reverse`）的行车顺序 = `coords` 反序；
//      遍历边 id 带 `_rev` 后缀的（双向段额外生成的那条反向遍历边）同样反序。
//
// ⚠️ 别把 ③ 的"行车顺序 = coords 反序"套到 `offset_m` 上：`offset_m` 一律从 `coords[0]` 量起
// （twin 真值口径，见下方 `baseSegmentId` 之后的说明），落点用 `pointAtOffset()`，不做镜像换算。
//
// ⚠️ 这里只做**展示用**的几何整理：不进接口、不参与算路 / ETA / 判级，也不改网络。
import { directionOf } from './directions'
import type { RouteArrowStep, RouteStep } from './traffic'

const LAT_M_PER_DEG = 111_320

function lonMPerDeg(lat: number): number {
  return LAT_M_PER_DEG * Math.cos((lat * Math.PI) / 180)
}

/** 两点平面距离（米，与 `segmentLengthM` 同一套近似；只用于判"端点是否相接"） */
function gapM(a: [number, number], b: [number, number]): number {
  const mx = (b[0] - a[0]) * lonMPerDeg(a[1])
  const my = (b[1] - a[1]) * LAT_M_PER_DEG
  return Math.hypot(mx, my)
}

/**
 * 该段的行车顺序是否与 `coords` 相反。
 *
 * · 段号带 `_rev` 后缀 = 遍历边（`work/engine/realnet_topology.py:174-216` 给双向段额外生成的
 *   那条反向边，from/to 与 `coords` 反序）；
 * · 包内 `direction='backward'`（= `work/twin/netpack/topology.py:240-241` 的 `reverse`：
 *   反向单行，几何 from/to 与行车方向相反）。
 */
export function isTravelReversed(segmentId: string): boolean {
  if (!segmentId) return false
  if (/_rev$/.test(segmentId)) return true
  // 站点包里写 backward，topology 里写 reverse —— 两种写法都认，别只认一种。
  // （`DirectionKind` 的类型圈里只有 backward，reverse 是后端 sidecar 的叫法，故走字符串比较）
  const raw = String(directionOf(segmentId)?.direction ?? '')
  return raw === 'backward' || raw === 'reverse'
}

/** 段号的"基段"（去掉 `_rev` 后缀），用于查包内方向 / 取几何 */
export function baseSegmentId(segmentId: string): string {
  return segmentId.replace(/_rev$/, '')
}

// ⚠️ 偏移口径只有**一种**：`pointAtOffset(coords, offset_m)`（`shared/demoNetwork`），
// reverse 段也**不做**镜像换算。曾经在这里有一个 `pointAtTravelOffset()`（把 offset_m 当行进口径、
// 在 reverse 段上按 `length - offset` 反算），2026-10-29 已删除，别再改回去 —— 依据：
// · `work/twin/sumonet.py:344-355` 建 SUMO 边时 `shape` 就是 `coords` 顺序、from/to 也是几何
//   from/to（**不看 oneway**，SZ-004 这类 oneway=reverse 的段照样按 coords 顺序建边）；
// · `work/twin/loop.py:1066-1071` 的 `_rev` 补边是 `offset_m = length_m - getLanePosition()`
//   （注释写明"换算回**原段起点**起算的里程"）。
// ⇒ 真值 `/locate`、点位注册表、前端三者同口径，`offset_m` 一律从 `coords[0]` 量起。
// reverse 段起点错位的真因在引擎 `_start_from`（把 coords 序当行进序读），不在前端换算。
// 实测取证：`work/verify/verify-offset-caliber.mjs`（snap 往返，SZ-004 offset 20/90 m 回显一致）。

/** 按行车顺序排好的一段（`reversed=true` 表示几何被反用过） */
export interface OrientedLeg {
  segment_id: string
  geometry: [number, number][]
  reversed: boolean
}

function orientedCoords(coords: [number, number][], reversed: boolean): [number, number][] {
  return reversed ? [...coords].reverse() : coords
}

/** 按包内方向 / `_rev` 规则给出一段的初步行车几何（不看连通性，只看标注） */
export function orientLeg(coords: [number, number][], segmentId: string): OrientedLeg {
  const reversed = isTravelReversed(segmentId)
  return { segment_id: segmentId, geometry: orientedCoords(coords, reversed), reversed }
}

/**
 * 打通一条路线的**链式定向**（没有后端 steps 时的回退；`/route/recommend` 走这条）。
 *
 * 做法：先把每段按标注摆成"疑似行车方向"，再从"没有任何一段接在它前面"的那段起头，
 * 每一步找**首点接上当前尾点**的下一段（首点接不上但尾点接得上 → 把这段整段翻过来）。
 * 端点容差 `toleranceM`：路口几何不一定严格共点（本包节点间距 ~1 m 级，取 25 m 足够宽松）。
 *
 * ⚠️ 允许翻转：双向段的"几何方向"本身不带行车含义，只有连通性说得清哪头是头。
 */
export function orientByConnectivity(
  segmentIds: string[],
  coordsOf: (segmentId: string) => [number, number][] | null,
  toleranceM = 25,
): OrientedLeg[] {
  const pool: OrientedLeg[] = []
  segmentIds.forEach((id) => {
    const coords = coordsOf(baseSegmentId(id))
    if (!coords || coords.length < 2) return
    pool.push(orientLeg(coords, id))
  })
  if (pool.length <= 1) return pool

  const used = new Set<number>()
  const out: OrientedLeg[] = []
  /** 找与 `tail` 相接的下一个未用段（优先首点相接，其次尾点相接并翻转） */
  const nextFrom = (tail: [number, number]): { index: number; leg: OrientedLeg } | null => {
    let best: { index: number; leg: OrientedLeg; gap: number } | null = null
    for (let i = 0; i < pool.length; i++) {
      if (used.has(i)) continue
      const leg = pool[i]!
      const head = leg.geometry[0]!
      const end = leg.geometry[leg.geometry.length - 1]!
      const gapHead = gapM(tail, head)
      const gapEnd = gapM(tail, end)
      let cand: { index: number; leg: OrientedLeg; gap: number } | null = null
      if (gapHead <= toleranceM) {
        cand = { index: i, leg, gap: gapHead }
      } else if (gapEnd <= toleranceM) {
        cand = {
          index: i,
          leg: {
            segment_id: leg.segment_id,
            geometry: [...leg.geometry].reverse(),
            reversed: !leg.reversed,
          },
          gap: gapEnd,
        }
      } else if (gapHead <= toleranceM * 8) {
        // 完全接不上：退而求其次接最近的一段，避免整串断在一处就"一支箭头都不画"
        cand = { index: i, leg, gap: gapHead }
      }
      if (cand && (!best || cand.gap < best.gap)) best = cand
    }
    return best ? { index: best.index, leg: best.leg } : null
  }

  // 起头：找"没有任何别的段能接在它前面"的那段（其首点不被其它段的尾点命中）
  let start = 0
  for (let i = 0; i < pool.length; i++) {
    const head = pool[i]!.geometry[0]!
    const hasPred = pool.some((other, j) => {
      if (j === i) return false
      return gapM(other.geometry[other.geometry.length - 1]!, head) <= toleranceM
    })
    if (!hasPred) {
      start = i
      break
    }
  }
  used.add(start)
  out.push(pool[start]!)

  while (out.length < pool.length) {
    const tail = out[out.length - 1]!.geometry[out[out.length - 1]!.geometry.length - 1]!
    const next = nextFrom(tail)
    if (!next) break
    used.add(next.index)
    out.push(next.leg)
  }
  // 兜底：连通性断掉剩下的段仍按原顺序补在尾部（宁可箭头位置怪，也不要"整条路线一支箭头都没有"）
  pool.forEach((leg, i) => {
    if (!used.has(i)) out.push(leg)
  })
  return out
}

/** 后端 `steps[]` → 地图箭头段（几何已按行车顺序，原样透传，不改向） */
export function stepsToArrowSteps(steps: RouteStep[] | undefined | null): RouteArrowStep[] {
  const out: RouteArrowStep[] = []
  for (const step of steps ?? []) {
    const geom = step.geometry
    if (!Array.isArray(geom) || geom.length < 2) continue
    out.push({
      segment_id: step.segment_id,
      edge_id: step.edge_id ?? undefined,
      geometry: geom,
      // `trim_head_m` / `trim_tail_m`（方案 §2 附加字段）：起点 / 终点落在段中时，
      // 首尾各有若干米不在本次行程内 —— 透传下去，箭头取 50% 弧长点时才不会落到行程外那半截。
      ...(typeof step.trim_head_m === 'number' ? { trim_head_m: step.trim_head_m } : {}),
      ...(typeof step.trim_tail_m === 'number' ? { trim_tail_m: step.trim_tail_m } : {}),
    })
  }
  return out
}

/** 段号列表（无 steps 时）→ 地图箭头段：链式连通性定向，不按 `coords` 顺序瞎画 */
export function segmentIdsToArrowSteps(
  segmentIds: string[],
  coordsOf: (segmentId: string) => [number, number][] | null,
): RouteArrowStep[] {
  return orientByConnectivity(segmentIds, coordsOf).map((leg) => ({
    segment_id: leg.segment_id,
    geometry: leg.geometry,
  }))
}
