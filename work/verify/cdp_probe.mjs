#!/usr/bin/env node
/**
 * cdp_probe.mjs —— 验收用探针：确认能否从页面里拿到 MapLibre 的 map 实例。
 *
 * 为什么需要它：L3 硬指标「箭头落点与路段相对位置偏差 < 1px」不能靠肉眼看 PNG，
 * 必须拿到 map.project() 把经纬度换算成屏幕像素再比。仓库当前**没有** window.__map 之类的
 * 调试钩子（grep 过 MapLibreViewer.vue），所以我先探「开发模式下 Vue 组件树能不能摸到 map」，
 * 这条路不用改任何产品代码。
 *
 * 用法：node scripts/../work/verify/cdp_probe.mjs [url]
 */
import { spawn } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { setTimeout as sleep } from 'node:timers/promises'
import os from 'node:os'
import path from 'node:path'

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const URL_ = process.argv[2] || 'http://127.0.0.1:5373/dashboard'
const PORT = 9333
const TMP = path.join(os.tmpdir(), `hubflow-verify-edge-${process.pid}`)
mkdirSync(TMP, { recursive: true })

/** 极简 CDP 客户端：一个 WebSocket，send 返回 promise，事件走 handler 表。 */
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
      const list = this.handlers.get(msg.method) || []
      for (const fn of list) fn(msg.params)
    })
  }
  send(method, params = {}) {
    const id = ++this.id
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
      this.ws.send(JSON.stringify({ id, method, params }))
    })
  }
  on(method, fn) {
    if (!this.handlers.has(method)) this.handlers.set(method, [])
    this.handlers.get(method).push(fn)
  }
  async eval(expression, awaitPromise = true) {
    const r = await this.send('Runtime.evaluate', {
      expression,
      awaitPromise,
      returnByValue: true,
      allowUnsafeEvalBlockedByCSP: true,
    })
    if (r.exceptionDetails) throw new Error('EVAL THROW: ' + JSON.stringify(r.exceptionDetails).slice(0, 800))
    return r.result.value
  }
}

async function fetchJson(url) {
  const res = await fetch(url)
  return res.json()
}

const edge = spawn(
  EDGE,
  [
    '--headless=new',
    '--disable-gpu-sandbox',
    '--enable-unsafe-swiftshader',
    '--use-gl=swiftshader',
    '--hide-scrollbars',
    '--mute-audio',
    '--no-first-run',
    '--no-default-browser-check',
    `--user-data-dir=${TMP}`,
    `--remote-debugging-port=${PORT}`,
    '--window-size=1280,720',
    'about:blank',
  ],
  { stdio: ['ignore', 'pipe', 'pipe'] },
)
edge.stderr.on('data', () => {})

let target = null
for (let i = 0; i < 60; i++) {
  try {
    const list = await fetchJson(`http://127.0.0.1:${PORT}/json/list`)
    target = list.find((t) => t.type === 'page')
    if (target) break
  } catch {}
  await sleep(250)
}
if (!target) {
  edge.kill()
  throw new Error('Edge 没起来 / CDP 端口没响应')
}

const ws = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((res, rej) => {
  ws.addEventListener('open', res)
  ws.addEventListener('error', rej)
})
const cdp = new CDP(ws)

const logs = []
cdp.on('Runtime.consoleAPICalled', (p) => {
  const text = (p.args || []).map((a) => a.value ?? a.description ?? a.type).join(' ')
  logs.push(`[${p.type}] ${text}`)
})
cdp.on('Runtime.exceptionThrown', (p) => {
  logs.push(`[exception] ${p.exceptionDetails?.text} ${p.exceptionDetails?.exception?.description ?? ''}`)
})

await cdp.send('Page.enable')
await cdp.send('Runtime.enable')
await cdp.send('Emulation.setDeviceMetricsOverride', {
  width: 1280,
  height: 720,
  deviceScaleFactor: 1,
  mobile: false,
})
await cdp.send('Page.navigate', { url: URL_ })
await sleep(9000)

const probe = await cdp.eval(`(() => {
  const out = { href: location.href, title: document.title, maps: [] };
  const pick = (o) => o && typeof o.project === 'function' && typeof o.getSource === 'function';
  const seen = new Set();
  const visit = (comp, depth) => {
    if (!comp || seen.has(comp) || depth > 40) return;
    seen.add(comp);
    try {
      const ss = comp.setupState;
      if (ss) {
        for (const k of Object.keys(ss)) {
          let v = null;
          try { v = ss[k] } catch { continue }
          if (pick(v)) out.maps.push({ via: 'setupState.' + k, kind: 'direct' });
          if (v && typeof v === 'object' && pick(v.value)) out.maps.push({ via: 'setupState.' + k + '.value', kind: 'ref' });
        }
      }
      const ctx = comp.ctx;
      if (ctx) for (const k of Object.keys(ctx)) {
        let v = null; try { v = ctx[k] } catch { continue }
        if (pick(v)) out.maps.push({ via: 'ctx.' + k, kind: 'direct' });
      }
    } catch (e) {}
    visit(comp.parent, depth + 1);
  };
  // 入口1：任意 maplibre DOM 元素上的 __vueParentComponent
  const el = document.querySelector('.maplibregl-map, .maplibregl-canvas, #map, [class*=maplibre]');
  out.hasMapEl = !!el;
  out.mapElClass = el ? el.className : null;
  if (el && el.__vueParentComponent) visit(el.__vueParentComponent, 0);
  // 入口2：挂载根上的 __vue_app__
  const rootEl = document.querySelector('#app');
  out.hasApp = !!(rootEl && rootEl.__vue_app__);
  if (rootEl && rootEl.__vue_app__) visit(rootEl.__vue_app__._instance, 0);
  // 入口3：通用全局钩子（以防有人已经加了）
  out.windowMap = !!(window.__map);
  out.vueKeys = rootEl ? Object.keys(rootEl).filter(k => k.startsWith('__vue')) : [];
  return out;
})()`)

console.log(JSON.stringify(probe, null, 2))
console.log('--- console/exception 记录（前 40 条） ---')
console.log(logs.slice(0, 40).join('\n') || '(无)')

ws.close()
edge.kill()
await sleep(300)
process.exit(0)
