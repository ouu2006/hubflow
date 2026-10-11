// SSE 帧写出:mock 端点共用的事件流写出器。帧格式:
//   event: <name>\n data: <json>\n\n
// (原 harness 问答假流 runFakeChatStream 已随 2026-10-11 架构裁定移除;
//  当前唯一使用方为 traffic 假流 /api/traffic/stream。)

import type { MockRes } from './util.ts'

export class SseWriter {
  private closed = false
  private readonly res: MockRes

  constructor(res: MockRes) {
    this.res = res
  }

  open(): void {
    this.res.statusCode = 200
    this.res.setHeader('Content-Type', 'text/event-stream; charset=utf-8')
    this.res.setHeader('Cache-Control', 'no-cache')
    this.res.setHeader('Connection', 'keep-alive')
    this.res.setHeader('X-Accel-Buffering', 'no')
    this.res.flushHeaders()
  }

  send(event: string, payload: unknown): void {
    if (this.closed) return
    this.res.write(`event: ${event}\ndata: ${JSON.stringify(payload)}\n\n`)
  }

  isClosed(): boolean {
    return this.closed
  }

  close(): void {
    if (this.closed) return
    this.closed = true
    this.res.end()
  }
}
