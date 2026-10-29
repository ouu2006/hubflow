// 校验 trim 口径（行进序）：对若干 OD 组合打 /route/plan，检查
//  Σsteps.length_m − trim_head_m(first) − trim_tail_m(last) == routes[].length_m
// 且 forward 首段 trim_head_m == offset_travel_m、routes[].trim_* 与首末段一致
const BASE = 'http://127.0.0.1:8001'
const ods = [
  ['SZ-023', 20, 'SZ-036', 0],
  ['SZ-023', 20, 'SZ-035', 0],
  ['SZ-004', 40, 'SZ-023', 20],
  ['SZ-035', 0, 'SZ-036', 0],
  ['SZ-036', 0, 'SZ-035', 0],
]
const rows = []
for (const [os, oo, ds, dof] of ods) {
  const res = await fetch(`${BASE}/api/traffic/route/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ origin: { segment_id: os, offset_m: oo }, destination: { segment_id: ds, offset_m: dof } }),
  })
  const j = await res.json()
  const r = (j.routes || [])[0]
  if (!r) {
    rows.push({ od: `${os}@${oo}→${ds}@${dof}`, routes: 0, reason: j.reason || j.alternatives_status || 'no route' })
    continue
  }
  const st = r.steps || []
  const sum = st.reduce((a, x) => a + (x.length_m || 0), 0)
  const th = r.trim_head_m ?? st[0].trim_head_m
  const tt = r.trim_tail_m ?? st[st.length - 1].trim_tail_m
  rows.push({
    od: `${os}@${oo}→${ds}@${dof}`,
    first: `${st[0].segment_id}/${st[0].direction}`,
    firstTrimHead: st[0].trim_head_m,
    startOffsetTravel: j.start_point?.offset_travel_m,
    startOffsetM: j.start_point?.offset_m,
    sumLen: +sum.toFixed(1),
    minusTrims: +(sum - th - tt).toFixed(1),
    routeLen: r.length_m,
    routeTrims: [r.trim_head_m, r.trim_tail_m],
    identity: Math.abs(sum - th - tt - r.length_m) <= 0.2 ? 'OK' : 'FAIL',
    destPoint: j.destination_point ? `${j.destination_point.segment_id}/${j.destination_point.direction}@${j.destination_point.offset_m}(${j.destination_point.lon},${j.destination_point.lat})` : null,
  })
}
console.log(JSON.stringify(rows, null, 1))
