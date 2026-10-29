// 375×812：把地图面板滚进视口后再查 rendered（证明"手机竖屏也不丢箭头"）
// 注意：queryRenderedFeatures 只查**当前视口**，所以必须先把 canvas 滚进视口。
const map = V.getMap()
const canvas = map.getCanvas()
const raf = () => new Promise((r) => requestAnimationFrame(r))
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

// 找到真正可滚动的那层祖先，把 canvas 居中
let scroller = canvas.parentElement
while (scroller && scroller !== document.body && scroller.scrollHeight <= scroller.clientHeight) {
  scroller = scroller.parentElement
}
const target = scroller && scroller !== document.body ? scroller : window
if (target === window) {
  const rect = canvas.getBoundingClientRect()
  window.scrollTo({ top: window.scrollY + rect.top - 40, behavior: 'instant' })
} else {
  const rect = canvas.getBoundingClientRect()
  const hostRect = target.getBoundingClientRect()
  target.scrollTop += rect.top - hostRect.top - 20
}
await raf()
await raf()
await sleep(1200)
await raf()

const r = canvas.getBoundingClientRect()
const count = (id) => {
  try {
    return map.queryRenderedFeatures({ layers: [id], validate: false }).length
  } catch (e) {
    return String(e)
  }
}
return {
  zoom: map.getZoom(),
  canvasClient: { w: canvas.clientWidth, h: canvas.clientHeight },
  canvasInViewport: { top: Math.round(r.top), bottom: Math.round(r.bottom), h: Math.round(r.height), viewportH: window.innerHeight, visible: r.top < window.innerHeight && r.bottom > 0 },
  layerVisibility: map.getLayer('hubflow-direction-marker') ? map.getLayoutProperty('hubflow-direction-marker', 'visibility') ?? 'visible' : 'missing',
  iconOpacityExpr: map.getPaintProperty('hubflow-direction-marker', 'icon-opacity') ?? null,
  dirRendered: count('hubflow-direction-marker'),
  routeArrowRendered: count('hubflow-route-arrow-marker'),
}
