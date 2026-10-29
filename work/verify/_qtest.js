// 探针：为什么 queryRenderedFeatures 在同样"已画好"的视口上有时读到 0 有时读到 61。
// cdp_eval.mjs 已经把 `V = window.__vf` 注进作用域，别重复声明。
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
V.getMap()
V.callSetupFn('pickStation', 'Z')
for (let i = 0; i < 60; i++) {
  await sleep(250)
  const s = V.survey(['motionPhase'])[0]
  if (s && s.keys && s.keys.motionPhase === 'station') break
}
const m = V.getMap()
const LAYER = 'hubflow-direction-marker'
const q = (opt) => { try { return m.queryRenderedFeatures(opt).length } catch (e) { return 'ERR:' + e.message } }

await new Promise((res) => { let d = false; const f = () => { if (!d) { d = true; res() } }; try { m.once('idle', f) } catch (e) {}; setTimeout(f, 8000) })
await sleep(500)
// 轮询到「瓦片全载完」再查：loaded()=false 时 queryRenderedFeatures 对 geojson 源会返回 0（假 0）
let waited = 0
while (waited < 20000 && !(m.loaded() && m.isStyleLoaded())) { await sleep(300); waited += 300 }

const a = q({ layers: [LAYER] })
m.triggerRepaint()
await sleep(400)
const b = q({ layers: [LAYER] })

const bear = m.getBearing()
m.setBearing(bear + 0.0005)
await sleep(500)
const c = q({ layers: [LAYER] })
m.setBearing(bear)
await sleep(400)
const d2 = q({ layers: [LAYER] })

return {
  zoom: m.getZoom(),
  layer: !!m.getLayer(LAYER),
  vis: m.getLayoutProperty(LAYER, 'visibility'),
  a_direct: a, b_repaint: b, c_afterRedraw: c, d_afterRestore: d2, allFeatures: q({}),
  loaded: m.loaded(), styleLoaded: m.isStyleLoaded(), waitedMs: waited,
  canvas: [m.getCanvas().clientWidth, m.getCanvas().clientHeight],
}
