// fit 后检查方向层/路线层是否真的在渲染（queryRenderedFeatures），并给出箭头屏幕位置
const map = V.getMap()
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const routeArrows = map.getSource('hubflow-route-arrow')?.serialize?.()?.data?.features ?? []
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
  map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], {
    padding: 120, duration: 0, maxZoom: 18,
  })
}
await sleep(1500)
const layers = map.getStyle().layers.map((l) => l.id).filter((id) => /direction|route-arrow|route-line/i.test(id))
const rendered = {}
for (const id of layers) {
  let n = 0
  try { n = map.queryRenderedFeatures({ layers: [id] }).length } catch (e) { n = -1 }
  rendered[id] = n
}
const rows = routeArrows.map((f) => {
  const sid = f.properties?.segment_id ?? '?'
  const g = f.geometry
  const c = g.type === 'Point' ? g.coordinates : g.coordinates[Math.floor(g.coordinates.length / 2)]
  const s = c ? map.project(c) : null
  const vis = map.getLayoutProperty('hubflow-route-arrow', 'visibility') ?? 'visible'
  return { segment_id: sid, rotate: +Number(f.properties?.rotate ?? 0).toFixed(1), screen: s ? { x: Math.round(s.x), y: Math.round(s.y) } : null, layerVisibility: vis }
})
return {
  zoom: +map.getZoom().toFixed(2),
  canvasRect: (({ x, y, width, height }) => ({ x: Math.round(x), y: Math.round(y), w: Math.round(width), h: Math.round(height) }))(map.getCanvas().getBoundingClientRect()),
  layers,
  rendered,
  rows,
}
