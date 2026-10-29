// 诊断：fitBounds 之后 zoom 会不会被 App 自己的 fit 覆盖回去（决定截图取景策略）
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
const series = []
series.push({ t: 0, zoom: +map.getZoom().toFixed(2), note: 'before fit' })
if (pts.length >= 2) {
  const lons = pts.map((p) => p[0])
  const lats = pts.map((p) => p[1])
  map.fitBounds(
    [
      [Math.min(...lons), Math.min(...lats)],
      [Math.max(...lons), Math.max(...lats)],
    ],
    { padding: 120, duration: 0, maxZoom: 18 },
  )
}
for (let i = 1; i <= 12; i++) {
  await sleep(500)
  series.push({ t: i * 500, zoom: +map.getZoom().toFixed(2), center: { lon: +map.getCenter().lng.toFixed(5), lat: +map.getCenter().lat.toFixed(5) } })
}
return { points: pts.length, series, canvasRect: (({ x, y, width, height }) => ({ x: Math.round(x), y: Math.round(y), w: Math.round(width), h: Math.round(height) }))(map.getCanvas().getBoundingClientRect()) }
