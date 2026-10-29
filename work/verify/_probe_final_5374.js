// 终检：5374(→8001, mode remote) 页面加载后的箭头状态与 console 干净度
const map = V.getMap()
const ser = (id) => map.getSource(id)?.serialize?.()
const arrows = ser('hubflow-route-arrow')?.data?.features ?? []
const dirs = ser('hubflow-direction')?.data?.features ?? []
const bySeg = {}
for (const f of arrows) {
  const sid = f.properties?.segment_id ?? '?'
  ;(bySeg[sid] ||= []).push(Number(f.properties?.rotate).toFixed(1))
}
return {
  routeArrowCount: arrows.length,
  directionArrowCount: dirs.length,
  routeArrows: bySeg,
  styleLoaded: map.isStyleLoaded(),
  zoom: +map.getZoom().toFixed(2),
}
