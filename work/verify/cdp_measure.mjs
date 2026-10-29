#!/usr/bin/env node
/**
 * cdp_measure.mjs —— L3「箭头标向」三档视口像素级测量器（验收用，不改任何产品代码）
 *
 * 为什么要有它：判据里「箭头落在路段中点、锥尖朝行进方向、与路段相对位置偏差 < 1px」
 * 肉眼看 PNG 证明不了。本脚本用 CDP 驱动真 Edge + 真 MapLibre：
 *   · map 实例从 Vue 开发态组件树 `setupState` 拿（仓库没有 window.__map 钩子，也不需要加）；
 *   · 页内测量逻辑在 `_measure_body.js`（独立实现的弧长/切线算法，不 import 产品代码）；
 *   · 三个 pass：自然取景（走应用自己的 pickStation）、钉死相机（跨视口同中心同缩放）、
 *     钉死相机 + bearing 30°（验「转地图后箭头是否仍贴合路面」）。
 *
 * 用法：
 *   node work/verify/cdp_measure.mjs --width 1280 --height 720
 *   node work/verify/cdp_measure.mjs --width 1920 --height 1080 --out work/verify/shots/1920x1080
 *   可选：--url --port --edge --station Z --zoom 16.2 --skip-rotated
 *
 * 产物（落 --out 目录）：direction-natural.png / direction-pinned.png / direction-rotated.png /
 *   measure.json（含逐段 rows、最大误差、图层 layout 表达式）
 */
import { spawn } from 'node:child_process'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { setTimeout as sleep } from 'node:timers/promises'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const argv = process.argv.slice(2)
const arg = (name, fallback = null) => {
  const i = argv.indexOf('--' + name)
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : fallback
}
const flag = (name) => argv.includes('--' + name)

const WIDTH = Number(arg('width', '1280'))
const HEIGHT = Number(arg('height', '720'))
const URL_ = arg('url', 'http://127.0.0.1:5373/dashboard')
const PORT = Number(arg('port', '9333'))
const STATION = arg('station', 'Z')
const ZOOM = Number(arg('zoom', '16.2'))
const OUT = arg('out', `work/verify/shots/${WIDTH}x${HEIGHT}`)
const EDGE = arg('edge', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
const SKIP_ROTATED = flag('skip-rotated')
const SKIP_CLEAN = flag('skip-clean')

mkdirSync(OUT, { recursive: true })
const LIB = readFileSync(path.join(HERE, '_page_lib.js'), 'utf8')
const BODY = readFileSync(path.join(HERE, '_measure_body.js'), 'utf8')

class CDP {
  constructor(ws) {
    this.ws = ws
    this.id = 0
    this.pending = new Map()
    this.handlers = new Map()
    ws.addEventListener('message', (ev) => {
      const msg = JSON.parse(ev.data)
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id)
        this.pending.delete(msg.id)
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result)
        return
      }
      for (const fn of this.handlers.get(msg.method) || []) fn(msg.params)
    })
  }
  send(method, params = {}) {
    const id = ++this.id
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
      this.ws.send(JSON.stringify({ id, method, params }))
    })
  }
  on(m, fn) {
    if (!this.handlers.has(m)) this.handlers.set(m, [])
    this.handlers.get(m).push(fn)
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', {
      expression, awaitPromise: true, returnByValue: true, allowUnsafeEvalBlockedByCSP: true,
    })
    if (r.exceptionDetails) {
      const d = r.exceptionDetails
      throw new Error('EVAL THROW: ' + (d.exception?.description || d.text || JSON.stringify(d)).slice(0, 1500))
    }
    return r.result.value
  }
}

const TMP = path.join(os.tmpdir(), `hubflow-verify-shot-${process.pid}`)
mkdirSync(TMP, { recursive: true })

const edge = spawn(EDGE, [
  '--headless=new', '--enable-unsafe-swiftshader', '--use-gl=swiftshader',
  '--hide-scrollbars', '--mute-audio', '--no-first-run', '--no-default-browser-check',
  '--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding',
  `--user-data-dir=${TMP}`, `--remote-debugging-port=${PORT}`, `--window-size=${WIDTH},${HEIGHT}`, 'about:blank',
], { stdio: ['ignore', 'pipe', 'pipe'] })
edge.stderr.on('data', () => {})

let target = null
for (let i = 0; i < 100; i++) {
  try {
    const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()
    target = list.find((t) => t.type === 'page')
    if (target) break
  } catch {}
  await sleep(250)
}
if (!target) { edge.kill(); throw new Error('Edge 没起来 / CDP 无响应') }

const ws = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej) })
const cdp = new CDP(ws)
const logs = []
const log = (m) => { console.log(m); logs.push('[measure] ' + m) }
cdp.on('Runtime.consoleAPICalled', (p) => logs.push(`[${p.type}] ` + (p.args || []).map((a) => a.value ?? a.description ?? a.type).join(' ')))
cdp.on('Runtime.exceptionThrown', (p) => logs.push('[exception] ' + (p.exceptionDetails?.exception?.description || p.exceptionDetails?.text || '')))

await cdp.send('Page.enable')
await cdp.send('Runtime.enable')
await cdp.send('Emulation.setDeviceMetricsOverride', { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: false })
await cdp.send('Page.addScriptToEvaluateOnNewDocument', { source: LIB })
await cdp.send('Page.navigate', { url: URL_ })
await sleep(9000)

// 「进站后箭头看不看得见」的量化检查：把地图面板滚进视口 → 等真正画完一帧 → 数 queryRenderedFeatures。
// 为什么不能直接信 pass 里的 renderedCounts：那一帧刚 fit 完、瓦片还没上屏，实测所有视口都读到 0（假 0）。
const visibility = async (label) => cdp.eval(`(async () => {
  const V = window.__vf; const m = V.getMap(); const c = m.getContainer();
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const rectOf = () => { const r = c.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height } };
  const before = rectOf();
  let scrolled = 'not-needed';
  if (before.y < 8 || before.y + before.h > window.innerHeight - 8) {
    scrolled = 'scrollIntoView';
    c.scrollIntoView({ block: 'center', inline: 'center' });
    await sleep(220);
    let r = rectOf();
    if (r.y + r.h < 8 || r.y > window.innerHeight - 8) {
      scrolled = 'ancestors';
      const cands = [document.scrollingElement, document.documentElement, document.body];
      let e = c.parentElement;
      while (e) {
        const s = getComputedStyle(e);
        if (/(auto|scroll)/.test(s.overflowY) && e.scrollHeight > e.clientHeight) cands.push(e);
        e = e.parentElement;
      }
      for (const el of cands) {
        if (!el) continue;
        try { el.scrollTop = el.scrollTop + (rectOf().y - window.innerHeight / 2); } catch (err) {}
      }
      await sleep(220);
      r = rectOf();
      if (r.y + r.h < 8 || r.y > window.innerHeight - 8) scrolled = 'failed';
    }
  }
  // 三步：等到瓦片全载完 → 强制重绘一帧 → 再查。
  // 少了任何一步都会读到假 0：loaded() 为 false 时 geojson 源不进查询；没重绘则沿用上一帧的空缓存。
  let waited = 0;
  while (waited < 25000 && !(m.loaded() && m.isStyleLoaded())) { await sleep(300); waited += 300 }
  await sleep(300);
  // 小屏档滚进视口后容器尺寸会变，MapLibre 要自己 resize 一次才按新尺寸切瓦片，否则 query 读到 0。
  try { m.resize() } catch (e) {}
  await sleep(200);
  // 读 0 还有第三个陷阱：相机/尺寸一变，geojson 源会重新切瓦片，这段时间里 query 返回 0（实测 1280 档
  // 先读到 61、setBearing 后立刻变 0、再变回 61）。所以「读不到就重绘重读」，取多次里的最大值。
  let rendered = 0;
  let attempts = 0;
  for (let i = 1; i <= 10 && !rendered; i++) {
    attempts = i;
    try { m.triggerRepaint() } catch (e) {}
    await sleep(700);
    try { rendered = m.queryRenderedFeatures({ layers: ['hubflow-direction-marker'] }).length } catch (e) { rendered = 'ERR:' + e.message; break }
  }
  const r = rectOf();
  const inViewport = r.y + r.h > 0 && r.y < window.innerHeight && r.x + r.w > 0 && r.x < window.innerWidth;
  let opacity = null;
  try { opacity = m.getPaintProperty('hubflow-direction-marker', 'icon-opacity') } catch (e) {}
  return {
    label: ${JSON.stringify(label)}, zoom: m.getZoom(), rect: r, inViewport,
    scrollY: window.scrollY, innerHeight: window.innerHeight, scrolled, rendered, opacity,
    attempts, waitedMs: waited, loaded: (() => { try { return m.loaded() } catch (e) { return null } })(),
  };
})()`)

const shot = async (name, pass) => {
  // 小屏档（375×812）地图容器在首屏下方：不滚进视口里，截出来的就是页面顶部，箭头根本不在画面内。
  // 滚动会改变容器的页面坐标，所以滚完必须重读 containerRect 回写到本 pass（pixel_vs_projection 裁图要用）。
  const rect = await cdp.eval(`(() => {
    const m = window.__vf.getMap(); const c = m.getContainer();
    const r = c.getBoundingClientRect();
    if (r.top < 8 || r.bottom > window.innerHeight - 8) c.scrollIntoView({ block: 'center', inline: 'center' });
    const q = c.getBoundingClientRect();
    return { x: q.left + window.scrollX, y: q.top + window.scrollY, w: q.width, h: q.height };
  })()`).catch(() => null)
  if (rect && pass) pass.containerRect = rect
  await sleep(300)
  const r = await cdp.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  const p = path.join(OUT, name)
  writeFileSync(p, Buffer.from(r.data, 'base64'))
  return p
}


// 等地图把这一帧真的画完再截图：queryRenderedFeatures 是「按变换现算」，可能出现
// 要素查得到、画布还没重绘的情况 —— 直接截会截到上一帧（箭头看不见）。
const settle = async () => {
  await cdp.eval(`(async () => {
    const m = window.__vf.getMap();
    await new Promise((res) => { let done = false; const f = () => { if (!done) { done = true; res() } };
      try { m.once('idle', f) } catch (e) {} ; setTimeout(f, 5000) });
    // 不用 rAF：headless 里页面不可见时 rAF 可能一直不触发（会把 awaitPromise 挂死）
    await new Promise((r) => setTimeout(r, 400));
    return true;
  })()`)
  await sleep(300)
}

// —— 走进「站内」：走应用自己的入口 pickStation，不伪造图层状态 ——
const entered = await cdp.eval(`(async () => {
  const V = window.__vf;
  V.getMap();
  const r = V.callSetupFn('pickStation', ${JSON.stringify(STATION)});
  // 等镜头真的落站（组件自己会把 motionPhase 置 station）
  for (let i = 0; i < 60; i++) {
    await new Promise((res) => setTimeout(res, 250));
    const s = V.survey(['motionPhase'])[0];
    if (s && s.keys && s.keys.motionPhase === 'station') break;
  }
  const map = V.getMap();
  await new Promise((res) => { let d = false; const f = () => { if (!d) { d = true; res() } }; try { if (map.loaded() && map.isStyleLoaded()) f() } catch (e) {}; map.once('idle', f); setTimeout(f, 8000) });
  return {
    called: r, phase: (V.survey(['motionPhase'])[0] || {}).keys || null,
    cam: { center: map.getCenter().toArray(), zoom: map.getZoom(), bearing: map.getBearing(), pitch: map.getPitch() },
    dirVisibility: map.getLayoutProperty('hubflow-direction-marker', 'visibility'),
    rendered: (() => { try { return map.queryRenderedFeatures({ layers: ['hubflow-direction-marker'] }).length } catch (e) { return 'ERR:' + e.message } })(),
  };
})()`)

const result = {
  meta: { width: WIDTH, height: HEIGHT, url: URL_, station: STATION, zoom: ZOOM, at: new Date().toISOString(), entered },
  passes: {},
}

// pass A：自然取景（应用自己 fit）
result.passes.natural = await cdp.eval(`(async () => { const V = window.__vf; ${BODY} })()`)
await settle()
// 进站可见性（lead 要的那一列）：滚动 → 等一帧 → queryRenderedFeatures 计数
result.passes.natural.visibility = await visibility('natural')
await settle()
result.passes.natural.shot = path.basename(await shot('direction-natural.png', result.passes.natural))
await sleep(400)

// pass B：钉死相机（同中心同缩放，只换视口）—— 分辨率无关的硬证据
// 中心取**站点包几何的中位数**（不用箭头均值：万一相机没落站、要素被裁，均值会漂）
const siteCenter = (result.passes.natural && result.passes.natural.siteCenter) || null
// 钉死的相机必须**真的钉住**：组件自己的相机同步会在容器尺寸变化后再 fit 一次，
// 曾经出现过 pinned 档实测 zoom=16.73/center 被改掉（跨档比对因此整列不可比）。
// 所以每钉一次都验一遍，不符就再钉一次，仍不符就整轮判失败（宁可红，不要假绿）。
const PIN_TOL = { zoom: 1e-6, lnglat: 1e-9 }
const pinOk = (pass, want) => {
  const cam = (pass && pass.cam) || {}
  const c = cam.center || []
  return Math.abs((cam.zoom ?? -99) - want.zoom) < PIN_TOL.zoom
    && Math.abs((c[0] ?? 999) - want.center[0]) < PIN_TOL.lnglat
    && Math.abs((c[1] ?? 999) - want.center[1]) < PIN_TOL.lnglat
    && Math.abs((cam.bearing ?? -99) - (want.bearing ?? 0)) < 1e-6
}
const pinPass = async (want, label) => {
  let pass = null
  for (let attempt = 1; attempt <= 2; attempt++) {
    pass = await cdp.eval(`(async () => {
      window.__PIN__ = ${JSON.stringify(want)};
      const V = window.__vf;
      ${BODY}
    })()`)
    await settle()
    if (pinOk(pass, want)) return pass
    log(`  [pin] ${label} 第 ${attempt} 次没钉住（实测 zoom=${pass?.cam?.zoom} center=${JSON.stringify(pass?.cam?.center)}），重钉`)
    await sleep(1200)
  }
  return pass
}
if (siteCenter) {
  result.pinnedCamera = { center: siteCenter, zoom: ZOOM, bearing: 0, pitch: 0 }
  result.passes.pinned = await pinPass(result.pinnedCamera, 'pinned')
  result.passes.pinned.shot = path.basename(await shot('direction-pinned.png', result.passes.pinned))
  await sleep(400)

  if (!SKIP_ROTATED) {
    // pass C：地图像北偏 30° —— 验 `icon-rotation-alignment: map`（箭头该跟着路一起转）
    result.passes.rotated = await pinPass({ center: siteCenter, zoom: ZOOM, bearing: 30, pitch: 0 }, 'rotated')
    result.passes.rotated.shot = path.basename(await shot('direction-rotated.png', result.passes.rotated))
  }

  if (!SKIP_CLEAN) {
    // pass D：干净图 —— 把站点圆点/标签临时藏掉（只活在这一次浏览器会话里，不改代码），
    // 让 12 条反向段的方向箭头能被人眼直接看清「锥尖朝哪、压没压在中点」。
    result.passes.clean = await pinPass({ center: siteCenter, zoom: ZOOM, bearing: 0, pitch: 0 }, 'clean')
    const HIDDEN = ['hubflow-station-hit', 'hubflow-station-dot', 'hubflow-station-label', 'hubflow-route-arrow-marker'];
    await cdp.eval(`(() => { const m = window.__vf.getMap();
      window.__HIDDEN_PREV = {};
      for (const id of ${JSON.stringify(HIDDEN)}) {
        if (!m.getLayer(id)) continue;
        window.__HIDDEN_PREV[id] = m.getLayoutProperty(id, 'visibility') ?? 'visible';
        m.setLayoutProperty(id, 'visibility', 'none');
      }
      return Object.keys(window.__HIDDEN_PREV); })()`)
    await settle()
    result.passes.clean.shot = path.basename(await shot('direction-clean.png', result.passes.clean))
    // 恢复失败不致命（前端 HMR 重挂载会让 map 实例失效）——兜住，别把整轮测量搞崩
    await cdp.eval(`(() => { try { const m = window.__vf.getMap();
      if (!m) return 'no-map'; for (const [id, v] of Object.entries(window.__HIDDEN_PREV || {})) m.setLayoutProperty(id, 'visibility', v);
      return 'restored'; } catch (e) { return 'restore-failed:' + e.message } })()`).catch(() => 'eval-failed')
  }

}

if (result.passes.pinned && result.passes.pinned.layerDump) {
  writeFileSync(path.join(OUT, 'layer-dump.json'), JSON.stringify(result.passes.pinned.layerDump, null, 2))
  writeFileSync('work/verify/layer-dump.json', JSON.stringify(result.passes.pinned.layerDump, null, 2))
}
result.consoleLog = logs.slice(0, 80)
writeFileSync(path.join(OUT, 'measure.json'), JSON.stringify(result, null, 2))

const brief = (p) => !p ? null : !p.ok ? p : ({
  cam: { zoom: +p.cam.zoom.toFixed(6), bearing: +p.cam.bearing.toFixed(6), center: p.cam.center.map((v) => +v.toFixed(7)) },
  counts: p.counts,
  max: Object.fromEntries(Object.entries(p.max).map(([k, v]) => [k, v == null ? null : +Number(v).toFixed(4)])),
  iconOffset: p.layout.iconOffset,
  iconSizeIsExpression: Array.isArray(p.layout.iconSize),
  iconRotationAlignment: p.layout.iconRotationAlignment,
  visibility: p.layout.visibility,
})
console.log(JSON.stringify({
  out: OUT,
  entered: { called: entered.called, phase: entered.phase, cam: entered.cam, rendered: entered.rendered },
  natural: brief(result.passes.natural),
  pinned: brief(result.passes.pinned),
  rotated: brief(result.passes.rotated),
}, null, 2))

ws.close(); edge.kill(); await sleep(200); process.exit(0)
