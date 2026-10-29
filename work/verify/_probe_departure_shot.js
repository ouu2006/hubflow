// 验收截图：先把视野 fit 到路线范围（否则 zoom 3 上全部段挤成一个点），
// 再读离站回程下「路线箭头 vs 静态箭头」的朝向与屏幕坐标（供图注标段号）
const map = V.getMap()
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const ser = (id) => map.getSource(id)?.serialize?.()
const routeArrows = ser('hubflow-route-arrow')?.data?.features ?? []
const staticArrows = ser('hubflow-direction')?.data?.features ?? []

// fit 到路线箭头覆盖范围
const pts = []
for (const f of routeArrows) {
  const g = f.geometry
  if (!g) continue
  if (g.type === 'Point') pts.push(g.coordinates)
  else if (Array.isArray(g.coordinates)) pts.push(...g.coordinates)
}
if (pts.length >= 2) {
  const lons = pts.map((p) => p[0])
  const lats = pts.map((p) => p[1])
  map.fitBounds(
    [
      [Math.min(...lons), Math.min(...lats)],
      [Math.max(...lons), Math.max(...lats)],
    ],
    { padding: 140, duration: 0, maxZoom: 18 },
  )
}
await sleep(1500)

// 静态层按段号索引
const staticBySeg = {}
for (const f of staticArrows) {
  const sid = f.properties?.segment_id ?? '?'
  if (!staticBySeg[sid]) staticBySeg[sid] = { rotate: Number(f.properties?.rotate ?? 0) }
}
const midOf = (g) => {
  if (!g) return null
  if (g.type === 'Point') return g.coordinates
  const cs = g.coordinates
  return cs[Math.floor(cs.length / 2)]
}
const rows = routeArrows.map((f) => {
  const sid = f.properties?.segment_id ?? '?'
  const rot = Number(f.properties?.rotate ?? 0)
  const c = midOf(f.geometry)
  const scr = c ? map.project(c) : null
  const st = staticBySeg[sid] ?? null
  const delta = st ? Math.abs(((rot - st.rotate + 540) % 360) - 180) : null
  return {
    segment_id: sid,
    edge_id: f.properties?.edge_id ?? null,
    routeRotate: +rot.toFixed(1),
    staticRotate: st ? +st.rotate.toFixed(1) : null,
    sameDirection: delta === null ? null : delta < 1,
    screen: scr ? { x: Math.round(scr.x), y: Math.round(scr.y) } : null,
  }
})
const canvas = map.getCanvas()
return {
  size: { w: canvas.clientWidth, h: canvas.clientHeight },
  zoom: +map.getZoom().toFixed(2),
  center: { lon: +map.getCenter().lng.toFixed(5), lat: +map.getCenter().lat.toFixed(5) },
  routeArrowCount: routeArrows.length,
  staticArrowCount: staticArrows.length,
  rows,
  looksLikeDeparture: rows.some((r) => [208.7, 120.5, 209.8].some((b) => Math.abs(r.routeRotate - b) < 1.5)),
}
