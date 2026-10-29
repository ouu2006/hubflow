// 起点/终点 trim 口径核对：`trim_head_m` 应当用 `offset_travel_m`（geometry 已按行进序），
// 而不是 `offset_m`（coords 序）。reverse 段上两者互补，混用会把路线首端裁错。
// 用法：API_BASE=http://127.0.0.1:8001 node --experimental-strip-types work/verify/verify-trim-caliber.mjs
import { readFileSync } from 'node:fs'

const API = process.env.API_BASE || 'http://127.0.0.1:8001'
const T = 'file:///D:/hubflow/_arrows/work/verify/.tmp/src'
const { pointAtFraction, polylineLengthM } = await import(`${T}/shared/directions.ts`)

const net = readFileSync('work/frontend/ui-vue/src/station-packs/stationZ.network.ts', 'utf8')
const segs = new Map()
for (const m of net.matchAll(/segment_id: '([^']+)'[\s\S]*?coords: (\[[\s\S]*?\n\s*\])/g)) {
  segs.set(m[1], JSON.parse(m[2].replace(/\s+/g, '')))
}
const LAT_M = 111_320
const lonMPerDeg = (lat) => LAT_M * Math.cos((lat * Math.PI) / 180)
const distM = (a, b) => Math.hypot((a[0] - b[0]) * lonMPerDeg(a[1]), (a[1] - b[1]) * LAT_M)

const plan = async (origin, destination) => {
  const r = await fetch(`${API}/api/traffic/route/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ origin, destination }),
  })
  return r.json()
}

console.log('前提：前端起点标记 = pointAtOffset(coords, offset_m)（coords 序）；路线首段 geometry 已按行进序，')
console.log('      所以首段要裁掉的行进里程 = offset_travel_m。测「标记点」与「裁后路线首点」的距离：\n')
console.log('段号    方向     段长m   offset_m  offset_travel_m  trim_head_m  标记↔路线首点距离m  判定')

for (const off of [10, 40, 60, 100]) {
  const j = await plan({ segment_id: 'SZ-004', offset_m: off }, { segment_id: 'SZ-023', offset_m: 30 })
  const o = j.origin ?? {}
  const steps = (j.routes ?? [])[0]?.steps ?? []
  const st = steps[0]
  if (!st) {
    console.log(`SZ-004 offset_m=${off}: 无路线`)
    continue
  }
  // 前端起点标记（coords 序）
  const coords = segs.get('SZ-004')
  const marker = coords[0] // offset 0
  const L = polylineLengthM(coords)
  // marker = pointAtOffset(coords, off)，这里直接用共享函数重算
  const { pointAtOffset } = await import(`${T}/shared/demoNetwork.ts`).catch(() => ({}))
  const mk = pointAtOffset ? pointAtOffset(coords, off) : null
  // 路线首段裁掉 trim_head_m 后的首点
  const geom = st.geometry
  const head = st.trim_head_m ?? 0
  const p0 = pointAtFraction(geom, head / Math.max(1e-9, polylineLengthM(geom)))
  const d = mk ? distM(mk, p0) : NaN
  const ok = d < 2
  console.log(
    `SZ-004 ${String(j.origin.direction).padEnd(9)} ${L.toFixed(1).padStart(6)} ${String(off).padStart(8)} ` +
      `${String(o.offset_travel_m).padStart(14)} ${String(head).padStart(12)} ${d.toFixed(1).padStart(18)}   ${ok ? 'OK' : '✗ 不一致'}`,
  )
}
