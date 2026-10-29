// 离站分组取证：SZ-036 / SZ-023 / SZ-035 三条双向段的
//   ① 静态方向层箭头（位置 + rotate）② 路线箭头（位置 + rotate + 段号/edge_id）
// 两者朝向一致 = "同一段上静态箭头与路线箭头不打架"
const map = V.getMap()
const WANT = ['SZ-036', 'SZ-023', 'SZ-035']
const canvas = map.getCanvas()
const toScreen = (coords) => {
  const p = map.project(coords)
  return { x: Math.round(p.x), y: Math.round(p.y) }
}
const collect = (srcId) => {
  const src = map.getSource(srcId)
  const ser = src?.serialize?.()
  const feats = ser?.data?.features ?? []
  return feats.map((f) => ({
    layer: srcId,
    props: f.properties ?? {},
    geometryType: f.geometry?.type,
    coords: f.geometry?.type === 'Point' ? f.geometry.coordinates : null,
    screen: f.geometry?.type === 'Point' ? toScreen(f.geometry.coordinates) : null,
  }))
}
const dir = collect('hubflow-direction')
const route = collect('hubflow-route-arrow')
const pick = (rows, ids) =>
  rows.filter((r) => {
    const sid = String(r.props.segment_id ?? r.props.seg ?? '')
    const eid = String(r.props.edge_id ?? '')
    return ids.some((w) => sid === w || sid === `${w}_rev` || eid === w || eid === `${w}_rev`)
  })
const wantSet = WANT
return {
  zoom: map.getZoom(),
  canvas: { w: canvas.clientWidth, h: canvas.clientHeight },
  dirTotal: dir.length,
  routeTotal: route.length,
  dirRows: pick(dir, wantSet),
  routeRows: pick(route, wantSet),
  routeAllProps: route.slice(0, 3).map((r) => r.props),
}
