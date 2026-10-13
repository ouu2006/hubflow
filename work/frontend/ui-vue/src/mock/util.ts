// mock 中间件工具(运行于 vite dev/preview server)。
// 约束:与浏览器代码共用 tsconfig.app 检查,禁止 Node 专有全局(Buffer/process),
// 二进制一律走 Uint8Array/TextEncoder/TextDecoder。
// 鉴权/上传解析工具已随 2026-10-11 架构裁定移除,待新接口面定稿后按需重建。

import type { ServerResponse } from 'node:http'
import type { Connect } from 'vite'

export type MockReq = Connect.IncomingMessage
export type MockRes = ServerResponse

export interface ErrShape {
  code: string
  message: string
}

export function errShape(code: string, message: string): ErrShape {
  return { code, message }
}
/**
 * 状态写入端点的**同源校验**(演示态防护,独立审查 Sourcery 提出)。
 *
 * 背景:mock 挂在 vite dev/preview 的 loopback 上,而浏览器的**跨站表单 / 简单请求**
 * 不受同源策略限制——宿主开着演示时,误点(或恶意页)发一个跨源 POST 打到
 * `/api/traffic/scenario` / `/scenario/reset` / `/factors` / `/plan/*` 就能改掉
 * 正在演示的判级与处置态。这里按 HTTP 惯例**拒绝带外源 Origin 的写请求**。
 *
 * 口径:`Origin` 缺失 = **放行**(curl / 脚本 / 同源老浏览器不带该头,本地联调要用;
 * 跨站伪造**一定**会带上自己的 Origin)。所以这道门拦的是"浏览器里的别的站",不是"所有非浏览器调用"。
 */
export function crossSiteWriteBlocked(req: MockReq): boolean {
  const origin = req.headers.origin
  if (typeof origin !== 'string' || origin === '') return false
  try {
    const host = origin.startsWith('http') ? new URL(origin).host : ''
    return host !== req.headers.host
  } catch {
    return true // 解析不了的 Origin 一律当外源
  }
}

/** 跨站写请求的统一拒绝体(403) */
export function forbiddenCrossSite(res: MockRes): void {
  json(res, 403, errShape('CROSS_SITE_BLOCKED', '跨站写请求已拒绝(mock 演示态只接受同源写;缺 Origin 的本地调用放行)'))
}

export function json(res: MockRes, status: number, payload: unknown): void {
  res.statusCode = status
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.end(JSON.stringify(payload))
}

export function rid(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 8)}${Date.now().toString(36).slice(-4)}`
}

// 读请求体;超过 maxBytes 返回 null(调用方回 413)
export function readBody(req: MockReq, maxBytes: number): Promise<Uint8Array | null> {
  return new Promise((resolve) => {
    const chunks: Uint8Array[] = []
    let total = 0
    let settled = false
    const settle = (v: Uint8Array | null) => {
      if (settled) return
      settled = true
      resolve(v)
    }
    req.on('data', (chunk: Uint8Array) => {
      if (settled) return
      total += chunk.byteLength
      if (total > maxBytes) {
        settled = true
        resolve(null)
        req.destroy()
        return
      }
      chunks.push(chunk)
    })
    req.on('end', () => settle(concatChunks(chunks)))
    req.on('error', () => settle(null))
  })
}

export async function readJson(req: MockReq, maxBytes = 1024 * 1024): Promise<unknown> {
  const raw = await readBody(req, maxBytes)
  if (!raw || raw.byteLength === 0) return null
  try {
    return JSON.parse(new TextDecoder().decode(raw)) as unknown
  } catch {
    return null
  }
}

function concatChunks(chunks: Uint8Array[]): Uint8Array {
  const total = chunks.reduce((n, c) => n + c.byteLength, 0)
  const out = new Uint8Array(total)
  let off = 0
  for (const c of chunks) {
    out.set(c, off)
    off += c.byteLength
  }
  return out
}
