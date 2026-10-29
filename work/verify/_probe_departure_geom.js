// 取离站路线折线的屏幕坐标（供图注把"路"画出来，底图瓦片离线时也能看清箭头贴在哪条路上）
const map = V.getMap()
const ser = (id) => map.getSource(id)?.serialize?.()
const feats = ser('hubflow-route')?.data?.features ?? []
const proj = (c) => {
  const p = map.project(c)
  return [Math.round(p.x), Math.round(p.y)]
}
const lines = []
for (const f of feats) {
  const g = f.geometry
  if (!g) continue
  if (g.type === 'LineString') lines.push({ kind: f.properties?.kind ?? null, pts: g.coordinates.map(proj) })
  else if (g.type === 'MultiLineString') {
    for (const part of g.coordinates) lines.push({ kind: f.properties?.kind ?? null, pts: part.map(proj) })
  }
}
const canvas = map.getCanvas()
const cr = canvas.getBoundingClientRect()
return { rect: { x: Math.round(cr.x), y: Math.round(cr.y), w: Math.round(cr.width), h: Math.round(cr.height) }, zoom: map.getZoom(), lineCount: lines.length, lines }
