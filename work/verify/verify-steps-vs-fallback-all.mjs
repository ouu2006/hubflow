// 新链路回归：大屏路线箭头改为「按 request_id 单拉 steps」后，逐组核对
//   A. 映射是否完整：`stepsOfRouteKey()` 用到的 key（arrival / alt:1 / alt:2 / departure）
//      在 `GET /api/traffic/route/{request_id}/steps` 的 `routes{}` 里都能取到 steps；
//   B. 与兜底链式定向（`segmentIdsToArrowSteps`）是否仍等价 —— Δ 应与改造前基线一致（0 段不一致）。
//
// 用法：API_BASE=http://127.0.0.1:8001 node --experimental-strip-types work/verify/verify-steps-vs-fallback-all.mjs
const API = process.env.API_BASE || 'http://127.0.0.1:8001'
const T = 'file:///D:/hubflow/_arrows/work/verify/.tmp/src'
const RA = await import(`${T}/shared/routeArrows.ts`)
const D = await import(`${T}/shared/directions.ts`)
const { demoSegment } = await import(`${T}/shared/demoNetwork.ts`)

const { segmentIdsToArrowSteps, stepsToArrowSteps } = RA
const { directionKindOf, directionOf, pointAtFraction, tangentBearingAt, polylineLengthM, trimPolylineM } = D

const DIR_TANGENT_SPAN_M = 15
const DIR_MIN_DRAW_LEN_M = 30
const LAT_M = 111_320
const lonMPerDeg = (lat) => LAT_M * Math.cos((lat * Math.PI) / 180)
const distM = (a, b) => Math.hypot((a[0] - b[0]) * lonMPerDeg(a[1]), (a[1] - b[1]) * LAT_M)
const angDiff = (a, b) => {
  const d = Math.abs((((a - b) % 360) + 360) % 360)
  return Math.min(d, 360 - d)
}

function arrowOf(coords, trimHead = 0, trimTail = 0) {
  const c = trimPolylineM(coords, trimHead, trimTail)
  if (!Array.isArray(c) || c.length < 2) return null
  if (polylineLengthM(c) < DIR_MIN_DRAW_LEN_M) return null
  const [lon, lat] = pointAtFraction(c, 0.5)
  return { point: [lon, lat], bearing: tangentBearingAt(c, 0.5, DIR_TANGENT_SPAN_M) }
}

const coordsOfSegment = (id) => demoSegment(id)?.coords ?? null

// ---- 1. 大屏实际走的接口（无 steps）------------------------------------------------
const rec = await (await fetch(`${API}/api/traffic/route/recommend`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({}),
})).json()
const requestId = rec.request_id
console.log(`/route/recommend → request_id=${requestId}`)
console.log(`  arrival_route 有无 steps: ${rec.arrival_route?.steps ? '有' : '无（必须靠 steps 端点）'}`)

// ---- 2. 新链路取的权威 steps -------------------------------------------------------
const snap = await (await fetch(`${API}/api/traffic/route/${encodeURIComponent(requestId)}/steps`)).json()
const r = snap.routes ?? {}

/** 复刻 DashboardView.vue 的 `stepsOfRouteKey()` */
function stepsOfRouteKey(key) {
  const pick = (x) => (x && Array.isArray(x.steps) && x.steps.length > 0 ? x.steps : null)
  if (key === 'arrival') return pick(r.arrival_route)
  if (key === 'departure') return pick(r.departure_route)
  if (key === 'pickup') return pick(r.pickup_route)
  const alt = /^alt:(\d+)$/.exec(key)
  if (alt) return pick(r.alternatives?.[Number(alt[1]) - 1])
  return null
}

// 地图分组：与 routeHighlights / customRouteHighlights 同口径
const groups = [{ key: 'arrival', segments: rec.arrival_route?.segments ?? [] }]
;(rec.alternatives ?? []).forEach((a, i) => {
  if ((a.segments ?? []).length > 0) groups.push({ key: `alt:${i + 1}`, segments: a.segments })
})
if ((rec.departure_route?.segments ?? []).length > 0) {
  groups.push({ key: 'departure', segments: rec.departure_route.segments })
}

console.log(`\nsteps 端点 routes{} 键：${Object.keys(r).join(',')}`)
let mappingMissing = 0
let badTotal = 0
for (const g of groups) {
  const steps = stepsOfRouteKey(g.key)
  const groupName = `${g.key}（${g.segments.length} 段）`
  if (!steps) {
    mappingMissing++
    console.log(`\n=== ${groupName}  ✗ 权威 steps 缺失 → 前端会退回链式定向并打 [route-arrows] 日志`)
    const fb = segmentIdsToArrowSteps(g.segments, coordsOfSegment)
    console.log(`    兜底可画的箭头数：${fb.length}`)
    continue
  }
  const auth = stepsToArrowSteps(steps)
  const fb = segmentIdsToArrowSteps(g.segments, coordsOfSegment)
  console.log(`\n=== ${groupName}  权威 steps ${steps.length} 步 → 箭头 ${auth.length} 支；兜底箭头 ${fb.length} 支`)
  console.log('段号        方向        权威朝向    兜底朝向     Δ')
  let bad = 0
  for (const st of steps) {
    const base = String(st.segment_id).replace(/_rev$/, '')
    const f = fb.find((s) => String(s.segment_id).replace(/_rev$/, '') === base)
    const aArrow = arrowOf(st.geometry, st.trim_head_m, st.trim_tail_m)
    const fArrow = f ? arrowOf(f.geometry, f.trim_head_m, f.trim_tail_m) : null
    if (!aArrow || !fArrow) {
      console.log(`${st.segment_id.padEnd(12)} ${String(st.direction).padEnd(11)} (段长不足，不画箭头)`)
      continue
    }
    const d = angDiff(aArrow.bearing, fArrow.bearing)
    const kind = directionKindOf(directionOf(st.segment_id))
    const ok = kind === 'bidirectional' ? d < 2 || Math.abs(d - 180) < 2 : d < 2
    if (!ok) bad++
    console.log(
      `${st.segment_id.padEnd(12)} ${String(st.direction).padEnd(11)} ` +
        `${aArrow.bearing.toFixed(1).padStart(8)}° ${fArrow.bearing.toFixed(1).padStart(10)}° ${d.toFixed(1).padStart(6)}° ${ok ? '✓' : '✗'}`,
    )
  }
  badTotal += bad
  console.log(`  不一致段数：${bad}`)
}

console.log(`\n合计：映射缺失 ${mappingMissing} 组；权威 vs 兜底 不一致 ${badTotal} 段`)
console.log('（改造前基线：arrival 单组 Δ=0.0°、不一致 0 段；本次切到 steps 端点后应保持 0）')
