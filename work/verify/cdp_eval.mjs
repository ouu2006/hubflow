#!/usr/bin/env node
/**
 * cdp_eval.mjs —— 通用「在真页面里跑一段 JS」的小工具（验收勘察用）。
 *
 * 用途：三档截图前夕反复确认页面状态（mapScope / motionPhase / 方向层可见性 /
 * 源要素数 / 控制台报错）。它不产出交付物，只是让勘察可以复现、不用手点浏览器。
 *
 * 用法：
 *   node work/verify/cdp_eval.mjs <js文件> [--url ...] [--width 1280] [--height 720]
 *        [--wait 9000] [--out path.json] [--port 9333]
 *   · js 文件内容是一段**表达式或 IIFE**，返回值会被 JSON 打印；
 *     里面可用 `V` = 页面内工具集（getMap/sourceData/lens/pointAt/tangentAt）。
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
if (!jsPath) {
  console.error('用法: node work/verify/cdp_eval.mjs <js文件> [--url ...]')
  process.exit(2)
}
const WIDTH = Number(arg('width', '1280'))
const HEIGHT = Number(arg('height', '720'))
const URL_ = arg('url', 'http://127.0.0.1:5373/dashboard')
const PORT = Number(arg('port', '9333'))
const WAIT = Number(arg('wait', '9000'))
const OUT = arg('out', null)
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const TMP = path.join(os.tmpdir(), `hubflow-verify-eval-${process.pid}`)
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
const payload = { ok: !err, error: err, value, console: logs.slice(0, 40) }
if (OUT) writeFileSync(OUT, JSON.stringify(payload, null, 2))
console.log(JSON.stringify(payload, null, 2))

ws.close(); edge.kill(); await sleep(200); process.exit(0)
