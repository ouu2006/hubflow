// 取证：大屏路线箭头是否真的改走「按 request_id 拉 steps」这条链路
// 判据：
//   ① 页面确实发过 GET /api/traffic/route/{id}/steps（resource timing 有记录且 200）；
//   ② 该请求完成**之后**控制台不再出现 [route-arrows] steps unavailable（cdp_eval 的 console 字段是全程记录，
//      若只在首帧出现"拿不到"告警、且 steps 是 200，说明告警逻辑把"在路上"误判成"失败"）；
//   ③ 路线箭头 / 全网方向图层仍有要素（切到 steps 后箭头没丢）。
const m = V.getMap()
const out = { stepsReqs: [], routeArrows: null, staticArrows: null, sourceKeys: [] }

for (const e of performance.getEntriesByType('resource')) {
  if (e.name.includes('/steps')) {
    out.stepsReqs.push({
      url: e.name.replace(location.origin, ''),
      ms: Math.round(e.duration),
      status: e.responseStatus ?? null,
      bytes: e.transferSize ?? null,
    })
  }
}

const feats = (id) => {
  try {
    const q = m.querySourceFeatures(id)
    if (q && q.length) return q
  } catch {}
  try {
    const d = m.getSource(id)?._data
    return Array.isArray(d?.features) ? d.features : []
  } catch {
    return []
  }
}
const summary = (id) => {
  const fs = feats(id)
  return {
    source: id,
    count: fs.length,
    layers: m.getStyle().layers.filter((l) => l.source === id).map((l) => l.id),
    sample: fs.slice(0, 3).map((f) => f.properties ?? {}),
  }
}
out.routeArrows = summary('hubflow-route-arrow')
out.staticArrows = summary('hubflow-direction')
out.sourceKeys = Object.keys(m.getStyle().sources || {}).filter((k) => k.startsWith('hubflow-'))
return out
