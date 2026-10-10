// C 轨 mock 中间件(任务 A):vite dev/preview server 挂载,覆盖总控 §5.2 全部 8 个冻结端点。
// 铁律:不臆造端点——未匹配路径一律 404 并明示"冻结表外"。
// error 注入(VITE_MOCK_ERROR=1):chat SSE 中途 error、上传/删除/溯源 500、health kernel=down;
// 登录不受注入影响(保持可进入三页演示 error 分支)。

import type { Connect, Plugin } from 'vite'
import { MAX_UPLOAD_BYTES } from '../shared/protocol.ts'
import { addUploadedDoc, db, newSessionId, newToken, resolveTrace } from './db.ts'
import { runFakeChatStream, SseWriter } from './sse-writer.ts'
import {
  bearerToken,
  errShape,
  json,
  noContent,
  parseMultipartFile,
  readBody,
  readJson,
  type MockReq,
  type MockRes,
} from './util.ts'

export interface MockApiOptions {
  errorInject?: boolean
}

export function mockApiPlugin(options: MockApiOptions = {}): Plugin {
  const errorInject = options.errorInject === true
  const name = errorInject ? 'ui-vue-mock-api(error-inject)' : 'ui-vue-mock-api'
  const install = (middlewares: Connect.Server): void => {
    middlewares.use('/api', (req, res, next) => {
      handle(req, res, next, errorInject).catch(() => {
        if (!res.writableEnded) json(res, 500, errShape('MOCK_INTERNAL', 'mock 中间件内部错误'))
      })
    })
  }
  return {
    name,
    apply: 'serve',
    configureServer(server) {
      install(server.middlewares)
      server.config.logger.info(
        `  ${name}: §5.2 冻结端点 8/8 已挂载${errorInject ? '(error 注入开启)' : ''}`,
        { timestamp: true },
      )
    },
    configurePreviewServer(server) {
      install(server.middlewares)
      server.config.logger.info(`  ${name}: §5.2 冻结端点 8/8 已挂载(dist 自演示)`, {
        timestamp: true,
      })
    },
  }
}

async function handle(
  req: MockReq,
  res: MockRes,
  _next: Connect.NextFunction,
  errorInject: boolean,
): Promise<void> {
  const method = (req.method ?? 'GET').toUpperCase()
  const url = new URL(req.url ?? '/', 'http://mock.local')
  const path = url.pathname.replace(/\/+$/, '') || '/'

  // ---- 开放端点:health / login ----

  if (path === '/health' && method === 'GET') {
    return json(res, 200, { kernel: errorInject ? 'down' : 'up', db: 'dev' })
  }

  if (path === '/auth/login' && method === 'POST') {
    const body = (await readJson(req)) as Record<string, unknown> | null
    const user = String(body?.user ?? '')
    const password = String(body?.password ?? '')
    if (!user || !password) {
      return json(res, 401, errShape('BAD_CREDENTIALS', '用户名与密码均需非空(mock 模式:任意非空凭据可登录)'))
    }
    const token = newToken()
    db.tokens.add(token)
    return json(res, 200, { token })
  }

  // ---- 受保护端点:Bearer token 门 ----

  const token = bearerToken(req)
  if (!token || !db.tokens.has(token)) {
    return json(res, 401, errShape('UNAUTHORIZED', '缺少或无效的 Authorization: Bearer token'))
  }

  if (path === '/sessions' && method === 'POST') {
    const sessionId = newSessionId()
    db.sessions.add(sessionId)
    return json(res, 200, { session_id: sessionId })
  }

  let m = /^\/sessions\/([^/]+)\/chat$/.exec(path)
  if (m && method === 'POST') {
    const sessionId = decodeURIComponent(m[1])
    if (!db.sessions.has(sessionId)) {
      return json(res, 404, errShape('SESSION_NOT_FOUND', `会话不存在或已随 mock 重启失效: ${sessionId}`))
    }
    const body = (await readJson(req)) as Record<string, unknown> | null
    const text = typeof body?.text === 'string' ? body.text : ''
    if (!text.trim()) {
      return json(res, 400, errShape('BAD_REQUEST', 'text 不能为空'))
    }
    const sse = new SseWriter(res)
    sse.open()
    const cancel = runFakeChatStream(sse, { question: text, errorInject })
    req.on('close', cancel)
    return
  }

  if (path === '/kb/documents' && method === 'GET') {
    const records = db.docs.map((d) => ({ doc_id: d.doc_id, name: d.name, version: d.version, status: d.status }))
    return json(res, 200, records)
  }

  if (path === '/kb/documents' && method === 'POST') {
    if (errorInject) {
      return json(res, 500, errShape('MOCK_INJECTED', 'mock 注入错误:上传通道故障(REST error 分支演示)'))
    }
    // 双层护栏:先看声明长度,再在实读时限量(与后端 >16MB 护栏呼应,总控 §7-4)
    const declared = Number(req.headers['content-length'] ?? 0)
    if (declared > MAX_UPLOAD_BYTES + 1024 * 1024) {
      return json(res, 413, errShape('PAYLOAD_TOO_LARGE', '上传体超过 16MB 桥帧上限'))
    }
    const raw = await readBody(req, MAX_UPLOAD_BYTES + 1024 * 1024)
    if (!raw) {
      return json(res, 413, errShape('PAYLOAD_TOO_LARGE', '上传体超过 16MB 桥帧上限'))
    }
    const part = parseMultipartFile(raw, req.headers['content-type'])
    if (!part) {
      return json(res, 400, errShape('BAD_MULTIPART', 'multipart 解析失败(mock 仅支持浏览器 FormData 单文件字段 file)'))
    }
    if (part.size > MAX_UPLOAD_BYTES) {
      return json(res, 413, errShape('PAYLOAD_TOO_LARGE', `文件「${part.filename}」超过 16MB 桥帧上限`))
    }
    const doc = addUploadedDoc(part.filename)
    setTimeout(() => {
      doc.status = 'ready'
    }, 2500) // 版本态流水:processing → ready
    return json(res, 200, { doc_id: doc.doc_id, stored_path: doc.stored_path })
  }

  m = /^\/kb\/documents\/([^/]+)$/.exec(path)
  if (m && method === 'DELETE') {
    if (errorInject) {
      return json(res, 500, errShape('MOCK_INJECTED', 'mock 注入错误:删除通道故障(REST error 分支演示)'))
    }
    const docId = decodeURIComponent(m[1])
    const idx = db.docs.findIndex((d) => d.doc_id === docId)
    if (idx === -1) {
      return json(res, 404, errShape('DOC_NOT_FOUND', `文档不存在: ${docId}`))
    }
    db.docs.splice(idx, 1)
    return noContent(res)
  }

  m = /^\/answers\/([^/]+)\/trace$/.exec(path)
  if (m && method === 'GET') {
    if (errorInject) {
      return json(res, 500, errShape('MOCK_INJECTED', 'mock 注入错误:溯源服务故障(REST error 分支演示)'))
    }
    return json(res, 200, resolveTrace(decodeURIComponent(m[1])))
  }

  return json(res, 404, errShape('NOT_FOUND', `无此契约端点(冻结表外): ${method} /api${path}`))
}
