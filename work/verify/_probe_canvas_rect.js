// 取 canvas 在页面里的矩形（CSS px）+ dpr，供截图裁切/标注用
const map = V.getMap()
const canvas = map.getCanvas()
const r = canvas.getBoundingClientRect()
return {
  rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
  dpr: window.devicePixelRatio,
  zoom: map.getZoom(),
  innerW: window.innerWidth,
  innerH: window.innerHeight,
}
