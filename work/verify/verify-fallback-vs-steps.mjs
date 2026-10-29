// 大屏回退路径交叉验证：`/route/recommend` 没有 steps（实测），所以大屏路线箭头走
// `segmentIdsToArrowSteps(segments, coordsOfSegment)`（链式连通性定向，DashboardView.vue:1745-1766）。
// 这里把它的输出与后端权威 steps（`/route/{id}/steps`）逐段比朝向，Δ 应≈0°（双向段 0 或 180 都算一致）。
// 用法：API_BASE=http://127.0.0.1:8001 node --experimental-strip-types work/verify/verify-fallback-vs-steps.mjs
const API = process.env.API_BASE || 'http://127.0.0.1:8001'
const T = 'file:///D:/hubflow/_arrows/work/verify/.tmp/src'
const RA = await import(`${T}/shared/routeArrows.ts`)
const D = await import(`${T}/shared/directions.ts`)
const { demoSegment } = await import(`${T}/shared/demoNetwork.ts`)

const { segmentIdsToArrowSteps, stepsToArrowSteps } = RA
const { directionKindOf, directionOf, pointAtFraction, tangentBearingAt, polylineLengthM } = D

const DIR_TANGENT_SPAN_M = 15
const DIR_MIN_DRAW_LEN_M = 30
const LAT_M = 111_320
const lonMPerDeg = (lat) => LAT_M * Math.cos((lat * Math.PI) / 180)
const distM = (a, b) => Math.hypot((a[0] - b[0]) * lonMPerDeg(a[1]), (a[1] - b[1]) * LAT_M)
const angDiff = (a, b) => {
  const d = Math.abs((((a - b) % 360) + 360) % 360)
  return Math.min(d, 360 - d)
}

// 复刻 MapLibreViewer.vue:957-983 routeArrowGeoJson 的单步计算
function arrowOf(coords, trimHead = 0, trimTail = 0) {
  const c = D.trimPolylineM(coords, trimHead, trimTail)
  if (!Array.isArray(c) || c.length < 2) return null
  if (polylineLengthM(c) < DIR_MIN_DRAW_LEN_M) return null
  const [lon, lat] = pointAtFraction(c, 0.5)
  return { point: [lon, lat], bearing: tangentBearingAt(c, 0.5, DIR_TANGENT_SPAN_M) }
}

const coordsOfSegment = (id) => demoSegment(id)?.coords ?? null

const stepsPayload = await (await fetch(`${API}/api/traffic/route/REQ-REAL-0001/steps`)).json()
const arrival = stepsPayload.routes.arrival_route
const truthSteps = arrival.steps

// 大屏实际拿到的数据：/route/options 的 arrival_route.segments（无 steps）
const options = await (await fetch(`${API}/api/traffic/route/options`)).json()
const bigScreen = options.options[0].arrival_route
console.log(`大屏 arrival_route 字段：${Object.keys(bigScreen).join(',')}  → 有无 steps: ${bigScreen.steps ? '有' : '无（走回退）'}`)
console.log(`segments: ${(bigScreen.segments ?? []).join(' → ')}\n`)

const fallback = segmentIdsToArrowSteps(bigScreen.segments ?? [], coordsOfSegment)
const authoritative = stepsToArrowSteps(truthSteps)

console.log('段号      方向        权威steps朝向  回退(链式)朝向   Δ   回退几何与权威几何首点距离m  判定')
let bad = 0
for (const st of truthSteps) {
  const fb = fallback.find((s) => String(s.segment_id).replace(/_rev$/, '') === String(st.segment_id).replace(/_rev$/, ''))
  const authArrow = arrowOf(st.geometry, st.trim_head_m, st.trim_tail_m)
  const fbArrow = fb ? arrowOf(fb.geometry, fb.trim_head_m, fb.trim_tail_m) : null
  if (!authArrow || !fbArrow) {
    console.log(`${st.segment_id}  (无箭头：段长不足)`)
    continue
  }
  const d = angDiff(authArrow.bearing, fbArrow.bearing)
  const kind = directionKindOf(directionOf(st.segment_id))
  const ok = kind === 'bidirectional' ? d < 2 || Math.abs(d - 180) < 2 : d < 2
  if (!ok) bad++
  const dGeo = distM(st.geometry[0], fb.geometry[0])
  console.log(
    `${st.segment_id} ${String(st.direction).padEnd(10)} ${authArrow.bearing.toFixed(1).padStart(9)}° ${fbArrow.bearing.toFixed(1).padStart(11)}° ` +
      `${d.toFixed(1).padStart(5)}° ${dGeo.toFixed(1).padStart(20)}   ${ok ? '✓' : '✗'} ${kind}`,
  )
}
console.log(`\n回退路径与权威 steps 不一致段数：${bad}`)
console.log('（`edges` 里带 `_rev` 的遍历边一律按 coords 反序处理；回退只用于 /route/recommend 无 steps 的大屏路径）')
