// REST 访问面:fetch 封装。同源相对路径(浏览器端不读 VITE_API_BASE——
// dev 走 vite 代理/mock 中间件,集成方式待新后端规划定稿)。
// 鉴权方案未定(随接口面重新规划),当前所有端点公开访问。

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

export interface RequestOptions {
  body?: unknown
  signal?: AbortSignal
}

export async function request<T>(method: string, path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
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
    throw new ApiError(0, 'NETWORK', '网络错误:后端不可达(mock 模式请确认 vite dev server 已启动)')
  }

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
