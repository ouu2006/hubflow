// SSE-over-fetch:POST + ReadableStream 增量解析(EventSource 不支持 POST,故手写解析器)。
// 帧格式(与 mock/B 对齐):event: <name>\n data: <json>\n\n;容忍 \r\n 与多 data 行。

import { getToken } from '../stores/auth'
import { ApiError } from './http'

export type SseListener = (event: string, data: string) => void

export async function ssePost(path: string, body: unknown, onEvent: SseListener, signal?: AbortSignal): Promise<void> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  }
  if (token) headers.Authorization = `Bearer ${token}`

  let res: Response
  try {
    res = await fetch(path, { method: 'POST', headers, body: JSON.stringify(body), signal })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw new ApiError(0, 'NETWORK', '网络错误:SSE 连接建立失败(联调模式请确认后端已启动)')
  }

  if (!res.ok) {
    let code = `HTTP_${res.status}`
    let message = res.statusText || `SSE 建流失败(${res.status})`
    try {
      const data = (await res.json()) as { code?: unknown; message?: unknown }
      if (typeof data.code === 'string') code = data.code
      if (typeof data.message === 'string') message = data.message
    } catch {
      /* 非 JSON 错误体 */
    }
    throw new ApiError(res.status, code, message)
  }
  if (!res.body) throw new ApiError(0, 'NO_BODY', '响应无可读流')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''

  const dispatch = (block: string): void => {
    let event = 'message'
    const dataLines: string[] = []
    for (const line of block.split(/\r?\n/)) {
      if (!line || line.startsWith(':')) continue
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''))
    }
    if (dataLines.length) onEvent(event, dataLines.join('\n'))
  }

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let m: RegExpExecArray | null
      const sep = /\r?\n\r?\n/
      for (;;) {
        m = sep.exec(buf)
        if (!m) break
        dispatch(buf.slice(0, m.index))
        buf = buf.slice(m.index + m[0].length)
      }
    }
    const tail = decoder.decode()
    if (tail.trim()) dispatch(tail)
  } finally {
    reader.releaseLock()
  }
}
