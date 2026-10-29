// 路线箭头联调取证（真后端 + 真前端模块，一次性取证脚本，只读接口）
//
// 覆盖 lead 要求的三条重点（m00644）：
//   ① 路线箭头与路段静态箭头在**同一段**上朝向一致；
//   ② 双向段不打架；
//   ③ 首末段 `trim_head_m/trim_tail_m` 裁掉后，箭头不落在被裁区（残余 < 30 m 不画）。
//
// 前端两处被测逻辑（逻辑本体在 SFC 里，这里按同一套 shared 函数重放，行号即源码位置）：
//   · 静态方向层 `MapLibreViewer.vue:653-689 directionGeoJson()`
//     50% 弧长点 + `tangentBearingAt(coords, .5, DIR_TANGENT_SPAN_M=15)`，backward 再 +180°
//   · 路线箭头层 `MapLibreViewer.vue:957-983 routeArrowGeoJson()`
//     `trimPolylineM(geometry, trim_head_m, trim_tail_m)` → 长度 < `DIR_MIN_DRAW_LEN_M=30` 跳过
//     → 50% 弧长点 + `tangentBearingAt(coords, .5, 15)`
//
// 用法：API_BASE=http://127.0.0.1:8001 node --experimental-strip-types work/verify/verify-route-arrows.mjs
// 前置：node work/verify/prep-tmp-src.mjs（把 src 镜像成可直跑的 .ts）
import { readFileSync } from 'node:fs'

const API = process.env.API_BASE || 'http://127.0.0.1:8001'
const T = 'file:///D:/hubflow/_arrows/work/verify/.tmp/src'
const D = await import(`${T}/shared/directions.ts`)
const { directionOf, directionKindOf, bearingDeg, polylineLengthM, pointAtFraction, tangentBearingAt, trimPolylineM } = D

const DIR_TANGENT_SPAN_M = 15
const DIR_MIN_DRAW_LEN_M = 2 * DIR_TANGENT_SPAN_M // = 30
const DIR_BIDIR_MIN_LEN_M = 25

const LAT_M = 111_320
const lonMPerDeg = (lat) => LAT_M * Math.cos((lat * Math.PI) / 180)
const distM = (a, b) => Math.hypot((a[0] - b[0]) * lonMPerDeg(a[1]), (a[1] - b[1]) * LAT_M)
const angDiff = (a, b) => {
  const d = Math.abs(((a - b) % 360 + 360) % 360)
  return Math.min(d, 360 - d)
}

// 站点包几何（前端同源：stationZ.network.ts）
const net = readFileSync('work/frontend/ui-vue/src/station-packs/stationZ.network.ts', 'utf8')
const segs = new Map()
for (const m of net.matchAll(/segment_id: '([^']+)'[\s\S]*?coords: (\[[\s\S]*?\n\s*\])/g)) {
  segs.set(m[1], JSON.parse(m[2].replace(/\s+/g, '')))
}
const baseId = (id) => String(id ?? '').replace(/_rev$/, '')

// ── 静态方向层（重放 MapLibreViewer.vue:653-689） ──
function staticArrow(segmentId) {
  const id = baseId(segmentId)
  const coords = segs.get(id)
  if (!coords || coords.length < 2) return null
  const kind = directionKindOf(directionOf(id))
  const tangent = tangentBearingAt(coords, 0.5, DIR_TANGENT_SPAN_M)
  const [lon, lat] = pointAtFraction(coords, 0.5)
  return {
    kind,
    coords,
    point: [lon, lat],
    // bidirectional = 一支双头（两支方向都算"一致"）；backward = 切线 +180°
    bearing: kind === 'backward' ? (tangent + 180) % 360 : tangent,
    bidir: kind === 'bidirectional',
    bidirShort: kind === 'bidirectional' && polylineLengthM(coords) < DIR_BIDIR_MIN_LEN_M,
    chord: bearingDeg(coords),
  }
}

// ── 路线箭头层（重放 MapLibreViewer.vue:957-983） ──
function routeArrow(step) {
  const coords = trimPolylineM(step.geometry, step.trim_head_m ?? 0, step.trim_tail_m ?? 0)
  if (!Array.isArray(coords) || coords.length < 2) return { skipped: 'trim-empty' }
  const len = polylineLengthM(coords)
  if (len < DIR_MIN_DRAW_LEN_M) return { skipped: `residual ${len.toFixed(1)}m < ${DIR_MIN_DRAW_LEN_M}m`, len }
  const [lon, lat] = pointAtFraction(coords, 0.5)
  return {
    point: [lon, lat],
    bearing: tangentBearingAt(coords, 0.5, DIR_TANGENT_SPAN_M),
    len,
    // 箭头落点距"被裁掉那一头"的弧长（应 > 0，且落在保留段内）
    headOffset: (step.trim_head_m ?? 0) + len / 2,
    rawLen: polylineLengthM(step.geometry),
  }
}

const post = async (path, body) => {
  const r = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return r.json()
}
const get = async (path) => (await fetch(`${API}${path}`)).json()

const cases = [
  ['真网 arrival（REQ-REAL-0001）', () => get('/api/traffic/route/REQ-REAL-0001/steps').then((j) => j.routes.arrival_route)],
  ['plan 起点段中间(offset_m=60) reverse', () => post('/api/traffic/route/plan', { origin: { segment_id: 'SZ-004', offset_m: 60 }, destination: { segment_id: 'SZ-023', offset_m: 30 } }).then((j) => j.routes[0])],
  ['plan 起点段尾(offset_m=100) reverse→残余 20.7m', () => post('/api/traffic/route/plan', { origin: { segment_id: 'SZ-004', offset_m: 100 }, destination: { segment_id: 'SZ-023', offset_m: 30 } }).then((j) => j.routes[0])],
  ['plan 起点段中间(offset_m=30) forward', () => post('/api/traffic/route/plan', { origin: { segment_id: 'SZ-023', offset_m: 30 }, destination: { segment_id: 'SZ-055', offset_m: 10 } }).then((j) => j.routes[0])],
]

let bad = 0
const notes = []
for (const [label, load] of cases) {
  const route = await load()
  if (!route) {
    console.log(`\n■ ${label}: 无路线`)
    continue
  }
  const steps = route.steps ?? []
  console.log(`\n■ ${label}  steps=${steps.length}  length_m=${route.length_m}`)

  for (const st of steps) {
    const want = ['segment_id', 'edge_id', 'direction', 'from_node', 'to_node', 'length_m', 'geometry', 'trim_head_m', 'trim_tail_m']
    const miss = want.filter((k) => !(k in st))
    const ra = routeArrow(st)
    const sa = staticArrow(st.segment_id)
    const tag = `${st.segment_id}${st.edge_id && st.edge_id !== st.segment_id ? `(${st.edge_id})` : ''} ${st.direction}`

    // ② geometry 是否真按行进序：reverse 段首点应 == 包几何末点
    let geoNote = ''
    if (sa) {
      const expect = st.direction === 'reverse' || /_rev$/.test(String(st.edge_id))
        ? sa.coords[sa.coords.length - 1]
        : sa.coords[0]
      const d = distM(st.geometry[0], expect)
      geoNote = d < 0.5 ? '行进序✓' : `行进序✗(首点距期望 ${d.toFixed(1)}m)`
      if (d >= 0.5) bad++
    }

    // ① 朝向一致性
    let dirNote = ''
    if (sa && ra.bearing !== undefined) {
      let diff = angDiff(ra.bearing, sa.bearing)
      if (sa.bidir) diff = Math.min(diff, angDiff(ra.bearing, (sa.bearing + 180) % 360))
      dirNote = `朝向Δ=${diff.toFixed(1)}°${diff > 1 ? ' ✗' : ' ✓'}`
      if (diff > 1) bad++
    }

    // ③ trim：箭头不得落在被裁区
    let trimNote = ''
    const th = st.trim_head_m ?? 0
    const tt = st.trim_tail_m ?? 0
    if (th || tt) {
      trimNote = `trim_head=${th} trim_tail=${tt}`
      if (ra.point) {
        const outside = ra.headOffset < th - 0.01 || ra.headOffset > ra.rawLen - tt + 0.01
        const inside = !outside
        trimNote += inside ? ' 落点在残余段内✓' : ' ✗落在被裁区'
        if (!inside) bad++
        trimNote += `（箭头距保留段首 ${(ra.headOffset - th).toFixed(1)}m）`
      } else {
        trimNote += ` ⇒ 不画：${ra.skipped}`
      }
    }

    if (miss.length) {
      bad++
      notes.push(`${label} / ${tag}: 缺字段 ${miss.join(',')}`)
    }
    console.log(
      `   ${tag.padEnd(26)} ${(miss.length ? `缺字段[${miss}]` : '字段✓').padEnd(10)} ${geoNote.padEnd(22)} ` +
        `${ra.point ? `箭头@${ra.bearing.toFixed(1)}°` : '不画'} ${dirNote} ` +
        `${sa ? `静态@${sa.bearing.toFixed(1)}°(${sa.kind}${sa.bidir ? (sa.bidirShort ? ',短→圆点' : ',双头') : ''})` : '静态—'} ${trimNote}`,
    )
  }
}

// ④ 双向段专项：包里双向段在当前路线里出现时，静态层是"一支双头"，路线层只有一支
console.log('\n■ 双向段专项（静态=一支共轴双头，路线=按 steps.geometry 一支）')
const bidir = [...segs.keys()].filter((id) => directionKindOf(directionOf(id)) === 'bidirectional')
console.log(`   包内双向段 ${bidir.length} 条：${bidir.slice(0, 8).join(', ')}${bidir.length > 8 ? ' …' : ''}`)
for (const id of bidir.slice(0, 4)) {
  const sa = staticArrow(id)
  console.log(
    `   ${id} 段长=${polylineLengthM(sa.coords).toFixed(1)}m 静态=${sa.bidirShort ? '圆点(短段)' : '双头箭头'} bearing=${sa.bearing.toFixed(1)}°`,
  )
}

console.log(`\n汇总：异常项 ${bad}`)
console.log(bad === 0 ? '结论：契约字段齐、geometry 行进序、朝向与静态层一致、trim 后箭头不落被裁区。' : '结论：见上方 ✗ 项。')
