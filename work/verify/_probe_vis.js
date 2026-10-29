const map = V.getMap()
const ids = ['hubflow-direction-marker', 'hubflow-route-arrow-marker']
const out = { zoom: map.getZoom(), canvas: { w: map.getCanvas().clientWidth, h: map.getCanvas().clientHeight }, layers: [], samples: [] }
for (const id of ids) {
  if (!map.getLayer(id)) { out.layers.push({ id, missing: true }); continue }
  out.layers.push({
    id,
    visibility: map.getLayoutProperty(id, 'visibility') ?? 'visible',
    iconOpacity: map.getPaintProperty(id, 'icon-opacity') ?? null,
    iconSize: map.getPaintProperty(id, 'icon-size') ?? null,
  })
  try {
    const fs = map.queryRenderedFeatures({ layers: [id], validate: false })
    out.samples.push({ id, rendered: fs.length })
  } catch (e) { out.samples.push({ id, error: String(e) }) }
}
// 取一个方向要素，检查它此刻是否落在可视范围内
const src = map.getSource('hubflow-direction')
const ser = src?.serialize?.()
const feats = ser?.data?.features ?? []
if (feats.length) {
  const f = feats[0]
  const c = f.geometry.coordinates
  out.firstFeature = { segment: f.properties?.segment_id, rotate: f.properties?.rotate, screen: map.project(c), inViewport: (() => { const p = map.project(c); const cv = map.getCanvas(); return p.x >= 0 && p.y >= 0 && p.x <= cv.clientWidth && p.y <= cv.clientHeight })() }
}
return out
