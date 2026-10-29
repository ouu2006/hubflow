// 进站取景复核：落点 zoom 是否 ≥ DIR_ZOOM_FULL(15.5)，方向箭头是否真的可见（rendered>0）
const map = V.getMap()
const b = map.getBounds()
const arrows = (() => {
  try {
    return map.queryRenderedFeatures({ layers: ['hubflow-direction-marker'] }).length
  } catch (e) {
    return String(e)
  }
})()
return {
  zoom: map.getZoom(),
  center: [map.getCenter().lng, map.getCenter().lat],
  boundsFinite: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].every((v) => Number.isFinite(v)),
  canvas: { w: map.getCanvas().clientWidth, h: map.getCanvas().clientHeight },
  dirLayerExists: !!map.getLayer('hubflow-direction-marker'),
  dirRendered: arrows,
  routeArrowRendered: (() => {
    try {
      return map.queryRenderedFeatures({ layers: ['hubflow-route-arrow-marker'] }).length
    } catch (e) {
      return String(e)
    }
  })(),
}
