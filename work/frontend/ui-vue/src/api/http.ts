// REST 访问面:fetch 封装。同源相对路径(浏览器端不读 VITE_API_BASE——
// dev 走 vite 代理/mock 中间件,集成期走 FastAPI StaticFiles 同源挂载)。
// token 附加 Authorization: Bearer(04 任务书 §6:登录框 + token 附加请求头即可)。

import { clearAuth, getToken } from '../stores/auth'

export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

function onUnauthorized(): void {
  clearAuth()
  // hash 路由:直接改 hash 不引入 api→router 依赖环
  window.location.hash = '#/login'
}

export interface RequestOptions {
  body?: unknown
  auth?: boolean
  signal?: AbortSignal
}

export async function request<T>(method: string, path: string, opts: RequestOptions = {}): Promise<T> {
  const withAuth = opts.auth ?? true
  const headers: Record<string, string> = {}
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  if (withAuth) {
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }
  let res: Response
  try {
    res = await fetch(path, {
      method,
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      signal: opts.signal,
    })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw new ApiError(0, 'NETWORK', '网络错误:后端不可达(联调模式请确认 FastAPI dev server 已启动)')
  }

  if (res.status === 401 && withAuth) onUnauthorized()

  if (!res.ok) {
    let code = `HTTP_${res.status}`
    let message = res.statusText || `请求失败(${res.status})`
    try {
      const data = (await res.json()) as { code?: unknown; message?: unknown; error?: { message?: unknown } }
      if (typeof data.code === 'string') code = data.code
      if (typeof data.message === 'string') message = data.message
      else if (typeof data.error?.message === 'string') message = data.error.message
    } catch {
      /* 非 JSON 错误体:用状态文本 */
    }
    throw new ApiError(res.status, code, message)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}
