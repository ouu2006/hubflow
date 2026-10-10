// SSE 帧写出 + 假流编排:字级 delta 间隔推送(打字机节奏),收尾序列 usage → finish,
// error 注入 = 前 N 个 delta 后推 error 并终止。帧形状:
//   event: delta\ndata: {"text":"..."}\n\n
// 契约:事件名冻结于总控 §5.2;载荷形状为 mock 裁定,B 侧实现对齐(见 shared/protocol.ts)。

import {
  SSE_EVENT,
  type DeltaPayload,
  type FinishPayload,
  type SseErrorPayload,
  type UsagePayload,
} from '../shared/protocol.ts'
import { buildAnswer, buildTrace, db, newAnswerId } from './db.ts'
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

export interface FakeChatOptions {
  question: string
  errorInject: boolean
}

// 启动假流;返回 cancel(客户端断开时清理定时器)
export function runFakeChatStream(sse: SseWriter, opts: FakeChatOptions): () => void {
  const { question, errorInject } = opts
  const answerId = newAnswerId()
  const answerText = buildAnswer(question)
  const promptTokens = 48 + question.length
  const completionTokens = Math.ceil(answerText.length / 2)
  let i = 0
  let sentDeltas = 0
  let timer: ReturnType<typeof setTimeout> | null = null
  let done = false

  const finish = (): void => {
    if (done) return
    done = true
    const usage: UsagePayload = {
      prompt_tokens: promptTokens,
      completion_tokens: completionTokens,
      total_tokens: promptTokens + completionTokens,
    }
    sse.send(SSE_EVENT.usage, usage)
    const fin: FinishPayload = { answer_id: answerId }
    sse.send(SSE_EVENT.finish, fin)
    sse.close()
    db.traces.set(answerId, { question, items: buildTrace(question) })
  }

  const step = (): void => {
    if (sse.isClosed()) {
      done = true
      return
    }
    // 注入锚点按 delta 计数(字符下标会被随机字级分块跳过)
    if (errorInject && sentDeltas === 6) {
      done = true
      const err: SseErrorPayload = {
        code: 'KERNEL_DOWN',
        message: 'mock 注入错误:内核 sidecar 无响应(SSE error 分支演示,VITE_MOCK_ERROR=1)',
      }
      sse.send(SSE_EVENT.error, err)
      sse.close()
      return
    }
    if (i >= answerText.length) {
      finish()
      return
    }
    const size = 2 + Math.floor(Math.random() * 2) // 字级:每次 2~3 字符
    const delta: DeltaPayload = { text: answerText.slice(i, i + size) }
    sse.send(SSE_EVENT.delta, delta)
    i += size
    sentDeltas += 1
    timer = setTimeout(step, 26 + Math.random() * 22)
  }

  step()
  return () => {
    if (timer !== null) clearTimeout(timer)
    sse.close()
  }
}
