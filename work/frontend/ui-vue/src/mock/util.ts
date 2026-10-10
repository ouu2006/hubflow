// mock 中间件工具(运行于 vite dev/preview server)。
// 约束:与浏览器代码共用 tsconfig.app 检查,禁止 Node 专有全局(Buffer/process),
// 二进制一律走 Uint8Array/TextEncoder/TextDecoder。

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

export function noContent(res: MockRes): void {
  res.statusCode = 204
  res.end()
}

export function rid(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 8)}${Date.now().toString(36).slice(-4)}`
}

export function bearerToken(req: MockReq): string | null {
  const h = req.headers.authorization
  if (typeof h !== 'string') return null
  const m = /^Bearer\s+(.+)$/i.exec(h)
  return m ? m[1].trim() : null
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

export function bytesIndexOf(hay: Uint8Array, needle: Uint8Array, from = 0): number {
  outer: for (let i = from; i + needle.length <= hay.length; i++) {
    for (let j = 0; j < needle.length; j++) {
      if (hay[i + j] !== needle[j]) continue outer
    }
    return i
  }
  return -1
}

export interface ParsedFilePart {
  filename: string
  size: number
}

// 极简 multipart 解析:仅承诺自研客户端(浏览器 FormData,单文件字段 file)的形状。
// mock 专用,不做通用健壮性(集成期由 B 侧 FastAPI 真解析)。
export function parseMultipartFile(body: Uint8Array, contentType?: string): ParsedFilePart | null {
  if (!contentType) return null
  const bm = /boundary=(?:"([^"]+)"|([^;]+))/i.exec(contentType)
  if (!bm) return null
  const delim = new TextEncoder().encode(`--${(bm[1] ?? bm[2] ?? '').trim()}`)
  const crlf2 = new TextEncoder().encode('\r\n\r\n')
  const pos = bytesIndexOf(body, delim)
  let cur = pos
  while (cur !== -1) {
    const headStart = cur + delim.length
    if (body[headStart] === 45 && body[headStart + 1] === 45) return null // 结束符 "--"
    const headerEnd = bytesIndexOf(body, crlf2, headStart)
    if (headerEnd === -1) return null
    const headers = new TextDecoder().decode(body.slice(headStart, headerEnd))
    const contentStart = headerEnd + 4
    const next = bytesIndexOf(body, delim, contentStart)
    if (next === -1) return null
    const fm = /filename\*=UTF-8''([^;\r\n]+)/i.exec(headers)
    const plain = /filename="([^"]*)"/i.exec(headers)
    if (plain || fm) {
      let filename = plain ? plain[1] : ''
      if (fm) {
        try {
          filename = decodeURIComponent(fm[1])
        } catch {
          filename = fm[1]
        }
      }
      return { filename, size: Math.max(0, next - 2 - contentStart) } // 去掉前置 \r\n
    }
    cur = next
  }
  return null
}
