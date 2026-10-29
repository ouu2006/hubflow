// 为什么 rendered=0：查 layer→source 绑定、source 规模、filter、map 加载态
const map = V.getMap()
const out = {
  loaded: map.loaded(),
  styleLoaded: map.isStyleLoaded(),
  canvasWH: { w: map.getCanvas().width, h: map.getCanvas().height },
  layers: [],
  sources: {},
}
for (const id of ['hubflow-route-line', 'hubflow-direction-marker', 'hubflow-route-arrow-marker']) {
  if (!map.getLayer(id)) {
    out.layers.push({ id, missing: true })
    continue
  }
  const l = map.getLayer(id)
  out.layers.push({ id, type: l.type, source: l.source ?? null, sourceLayer: l.sourceLayer ?? null, filter: l.filter ?? null, minzoom: l.minzoom ?? null, maxzoom: l.maxzoom ?? null })
}
for (const sid of ['hubflow-route', 'hubflow-direction', 'hubflow-route-arrow']) {
  const src = map.getSource(sid)
  const ser = src?.serialize?.()
  const data = ser?.data
  out.sources[sid] = {
    exists: !!src,
    isSourceLoaded: src ? map.isSourceLoaded(sid) : null,
    featureCount: data && Array.isArray(data.features) ? data.features.length : data && data.type ? 'object' : null,
  }
}
// 用 bbox 再查一次（不靠 viewport 推断）
const b = map.getBounds()
try {
  out.renderedWithBbox = {}
  for (const id of ['hubflow-route-line', 'hubflow-direction-marker', 'hubflow-route-arrow-marker']) {
    out.renderedWithBbox[id] = map.queryRenderedFeatures({ layers: [id], validate: false }).length
  }
} catch (e) {
  out.renderedWithBbox = String(e)
}
out.bounds = { sw: [b.getWest(), b.getSouth()], ne: [b.getEast(), b.getNorth()] }
return out
