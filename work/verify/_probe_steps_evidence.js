// 验收取证（新链路）：路线箭头数据源来自「按 request_id 拉取的 steps」
// 输出：steps 请求记录 / 兜底告警有无 / 路线箭头逐支朝向 / 全网方向箭头数
const m = V.getMap()
const out = { stepsReq: null, routeArrow: null, directionArrow: null }

for (const e of performance.getEntriesByType('resource')) {
  if (e.name.includes('/steps')) {
    out.stepsReq = {
      url: e.name.replace(location.origin, ''),
      ms: Math.round(e.duration),
      status: e.responseStatus ?? null,
      bytes: e.transferSize ?? null,
    }
  }
}

const dataOf = (id) => {
  try {
    const ser = m.getSource(id)?.serialize?.()
    return ser?.data ?? null
  } catch {
    return null
  }
}
const feats = (id) => {
  const d = dataOf(id)
  return Array.isArray(d?.features) ? d.features : []
}

const ra = feats('hubflow-route-arrow')
out.routeArrow = {
  count: ra.length,
  arrows: ra.map((f) => ({
    segment_id: f.properties?.segment_id ?? null,
    edge_id: f.properties?.edge_id ?? null,
    rotate: f.properties?.rotate ?? f.properties?.bearing ?? null,
    point: f.geometry?.coordinates ?? null,
    trimmed_len_m: f.properties?.length_m ?? null,
  })),
}
const da = feats('hubflow-direction')
out.directionArrow = { count: da.length }
out.viewport = { zoom: +m.getZoom().toFixed(3) }
return out
