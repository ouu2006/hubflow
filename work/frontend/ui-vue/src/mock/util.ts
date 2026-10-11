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
