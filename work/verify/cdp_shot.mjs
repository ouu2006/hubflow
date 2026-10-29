#!/usr/bin/env node
/**
 * cdp_shot.mjs —— 打开真页面 → 跑一段勘察 JS（返回页面状态）→ 存整页截图。
 *
 * 与 cdp_eval.mjs 的区别：它额外把 `Page.captureScreenshot` 存成 png，
 * 且勘察 JS 与截图在**同一个会话/同一套视口**里完成 —— 这样 JS 里
 * `map.project([lon,lat])` 拿到的屏幕坐标可以直接用来在图注里标点/标段号。
 *
 * 用法：
 *   node work/verify/cdp_shot.mjs <js文件> --url ... --png out.png [--width 1600] [--height 900]
 *        [--wait 12000] [--port 9345]
 * 输出：{ ok, error, value, png, console }
 */
import { spawn } from 'node:child_process'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { setTimeout as sleep } from 'node:timers/promises'
import os from 'node:os'
import path from 'node:path'

const argv = process.argv.slice(2)
const positional = argv.filter((a) => !a.startsWith('--'))
const arg = (name, fallback = null) => {
  const i = argv.indexOf('--' + name)
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : fallback
}
const jsPath = positional[0]
const PNG = arg('png')
if (!jsPath || !PNG) {
  console.error('用法: node work/verify/cdp_shot.mjs <js文件> --png out.png [--url ...]')
  process.exit(2)
}
const WIDTH = Number(arg('width', '1600'))
const HEIGHT = Number(arg('height', '900'))
const URL_ = arg('url', 'http://127.0.0.1:5374/?view=departure')
const PORT = Number(arg('port', '9345'))
const WAIT = Number(arg('wait', '14000'))
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const TMP = path.join(os.tmpdir(), `hubflow-verify-shot-${process.pid}`)
mkdirSync(TMP, { recursive: true })
const LIB_SRC = readFileSync(new URL('./_page_lib.js', import.meta.url), 'utf8')

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

const edge = spawn(EDGE, [
  '--headless=new', '--enable-unsafe-swiftshader', '--use-gl=swiftshader',
  '--hide-scrollbars', '--mute-audio', '--no-first-run', '--no-default-browser-check',
  `--user-data-dir=${TMP}`, `--remote-debugging-port=${PORT}`, `--window-size=${WIDTH},${HEIGHT}`, 'about:blank',
], { stdio: ['ignore', 'pipe', 'pipe'] })
edge.stderr.on('data', () => {})

let target = null
for (let i = 0; i < 80; i++) {
  try {
    const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()
    target = list.find((t) => t.type === 'page')
    if (target) break
  } catch {}
  await sleep(250)
}
if (!target) { edge.kill(); throw new Error('Edge 没起来') }

const ws = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej) })
const cdp = new CDP(ws)
const logs = []
cdp.on('Runtime.consoleAPICalled', (p) => {
  logs.push(`[${p.type}] ` + (p.args || []).map((a) => a.value ?? a.description ?? a.type).join(' '))
})
cdp.on('Runtime.exceptionThrown', (p) => {
  logs.push('[exception] ' + (p.exceptionDetails?.exception?.description || p.exceptionDetails?.text || ''))
})

await cdp.send('Page.enable')
await cdp.send('Runtime.enable')
await cdp.send('Emulation.setDeviceMetricsOverride', { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: false })
await cdp.send('Page.addScriptToEvaluateOnNewDocument', { source: LIB_SRC })
await cdp.send('Page.navigate', { url: URL_ })
await sleep(WAIT)
await cdp.eval('window.__vf && window.__vf.getMap() ? true : false')

const body = readFileSync(jsPath, 'utf8')
let value, err = null
try {
  value = await cdp.eval(`(async () => { const V = window.__vf; ${body} })()`)
} catch (e) {
  err = String(e.message || e)
}
await sleep(600)
const shot = await cdp.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
writeFileSync(PNG, Buffer.from(shot.data, 'base64'))
const payload = { ok: !err, error: err, value, png: PNG, console: logs.slice(0, 30) }
console.log(JSON.stringify(payload, null, 2))

ws.close(); edge.kill(); await sleep(200); process.exit(0)
