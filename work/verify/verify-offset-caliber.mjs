// 起点标记 / 偏移口径自证（一次性取证脚本，可重复运行，无副作用：只读接口）
//
// 口径待证命题：`offset_m` 一律从 `coords[0]` 量起（coords 序），落点用
// `shared/demoNetwork.ts` 的 `pointAtOffset(coords, offset_m)`，**不做** reverse 段的镜像换算。
//
// 证法（真接口 `POST /api/traffic/route/snap`，后端用自己的几何 + 偏移口径把经纬度吸附回段上的点）：
//   ① 取段几何（`src/station-packs/stationZ.network.ts`）；
//   ② 用前端 `pointAtOffset` 把 offset_m 换成经纬度 P；
//   ③ 把 P 丢给 `/route/snap`，看它回什么 `segment_id / offset_m / lon / lat`；
//   ④ 判据：段号一致 + 回显 offset_m ≈ 输入 offset_m（往返一致）+ P 与回显经纬度 < 2 m。
//   ⚠️ 关键设计：reverse 段上取"非中点"的 offset（如 20 / 40 / 90），若口径搞反，
//      回显 offset 会变成 `length_m - offset`（120.7-20=100.7），一眼看得见；
//      中点 60.4 附近两种口径重合（互补），**不能**用来判别。
//
// 用法：node --experimental-strip-types work/verify/verify-offset-caliber.mjs
import { readFileSync } from 'node:fs'

const UI = 'work/frontend/ui-vue'
const API = process.env.API_BASE || 'http://127.0.0.1:8000'
const net = readFileSync(`${UI}/src/station-packs/stationZ.network.ts`, 'utf8')
const dirs = readFileSync(`${UI}/src/station-packs/stationZ.directions.generated.ts`, 'utf8')

const segs = new Map()
for (const m of net.matchAll(/segment_id: '([^']+)'[\s\S]*?coords: (\[[\s\S]*?\n\s*\])/g)) {
  segs.set(m[1], JSON.parse(m[2].replace(/\s+/g, '')))
}
const reverse = new Map()
for (const [, id, d] of dirs.matchAll(/"([^"]+)": \{"direction":"([a-z]+)"/g)) reverse.set(id, d)

const LAT_M = 111_320
const lonMPerDeg = (lat) => LAT_M * Math.cos((lat * Math.PI) / 180)

// 与 shared/demoNetwork.ts:166 `pointAtOffset` 逐行同构（同一个平面近似：经度按该点纬度压缩）
function pointAtOffset(coords, offsetM) {
  let remain = Math.max(0, offsetM)
  for (let i = 1; i < coords.length; i++) {
    const dLon = coords[i][0] - coords[i - 1][0]
    const dLat = coords[i][1] - coords[i - 1][1]
    const len = Math.hypot(dLon * lonMPerDeg(coords[i][1]), dLat * LAT_M)
    if (len <= 0) continue
    if (remain <= len) {
      const t = remain / len
      return [coords[i - 1][0] + dLon * t, coords[i - 1][1] + dLat * t]
    }
    remain -= len
  }
  return coords[coords.length - 1]
}

function lengthM(coords) {
  let total = 0
  for (let i = 1; i < coords.length; i++) {
    const dLon = coords[i][0] - coords[i - 1][0]
    const dLat = coords[i][1] - coords[i - 1][1]
    total += Math.hypot(dLon * lonMPerDeg(coords[i][1]), dLat * LAT_M)
  }
  return total
}

const distM = (a, b) => Math.hypot((a[0] - b[0]) * lonMPerDeg(a[1]), (a[1] - b[1]) * LAT_M)

async function snap(lon, lat) {
  const res = await fetch(`${API}/api/traffic/route/snap`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lon, lat }),
  })
  return res.json()
}

// SZ-004：direction=reverse（几何 from/to 与行车方向相反），length_m=120.7
// Z 段里另挑一条 reverse 的多折点段做对照
const CASES = [
  { seg: 'SZ-004', offsets: [0, 20, 40, 60.4, 90] },
  { seg: 'SZ-001', offsets: [20, 60] },
]

const rows = []
for (const { seg, offsets } of CASES) {
  const coords = segs.get(seg)
  if (!coords) {
    console.log(`(跳过 ${seg}：包内无该段几何)`)
    continue
  }
  const L = lengthM(coords)
  const dir = reverse.get(seg)
  for (const off of offsets) {
    const p = pointAtOffset(coords, off)
    const r = await snap(p[0], p[1])
    const back = [r.lon, r.lat]
    const dP = Number.isFinite(r.lon) ? distM(p, back) : NaN
    const dOff = Number.isFinite(r.offset_m) ? Math.abs(r.offset_m - off) : NaN
    rows.push({ seg, dir, L, off, rSeg: r.segment_id, rOff: r.offset_m, dOff, dP, dSeg: r.distance_m })
  }
}

console.log(`\noffset_m 口径自证（真接口 ${API}，snap 往返）`)
console.log('段号    方向        段长m  输入off  snap回显段  snap回显off  Δoff m  两点距离m  snap点-段距离m')
let worst = 0
for (const r of rows) {
  worst = Math.max(worst, r.dP)
  console.log(
    `${r.seg} ${String(r.dir).padEnd(11)} ${r.L.toFixed(1).padStart(6)} ${String(r.off).padStart(7)}  ` +
      `${String(r.rSeg).padEnd(10)} ${String(r.rOff).padStart(10)}  ${r.dOff.toFixed(2).padStart(7)}  ` +
      `${r.dP.toFixed(2).padStart(9)}  ${String(r.dSeg).padStart(6)}`,
  )
}
const segOk = rows.every((r) => r.rSeg === r.seg)
const offOk = rows.every((r) => r.dOff < 2)
console.log(`\n判据：段号一致=${segOk}  offset 往返一致(<2m)=${offOk}  两点最大偏差=${worst.toFixed(2)} m`)
console.log(
  worst < 2 && segOk && offOk
    ? '结论：pointAtOffset(coords, offset_m)（coords 序、不镜像）与后端口径一致。'
    : '结论：不一致，需复查。',
)
