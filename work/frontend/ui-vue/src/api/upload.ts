// 文档上传:XHR(multipart)+ 进度回调。fetch 的上传进度需流式请求体,兼容性差,故用 XHR。

import { getToken } from '../stores/auth'
import type { UploadResult } from '../shared/protocol'
import { ApiError } from './http'

export interface UploadHooks {
  onProgress?: (percent: number) => void
  signal?: AbortSignal
}

export function uploadDocument(file: File, hooks: UploadHooks = {}): Promise<UploadResult> {
  return new Promise<UploadResult>((resolve, reject) => {
    const form = new FormData()
    form.append('file', file)

    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/kb/documents')
    const token = getToken()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)

    const onAbort = (): void => xhr.abort()
    hooks.signal?.addEventListener('abort', onAbort, { once: true })
    const cleanup = (): void => hooks.signal?.removeEventListener('abort', onAbort)

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) hooks.onProgress?.(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onerror = () => {
      cleanup()
      reject(new ApiError(0, 'NETWORK', '网络错误:上传失败(联调模式请确认后端已启动)'))
    }
    xhr.onabort = () => {
      cleanup()
      reject(new ApiError(0, 'ABORTED', '上传已取消'))
    }
    xhr.onload = () => {
      cleanup()
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as UploadResult)
        } catch {
          reject(new ApiError(xhr.status, 'BAD_SHAPE', '上传响应非 JSON'))
        }
        return
      }
      let code = `HTTP_${xhr.status}`
      let message = `上传失败(${xhr.status})`
      try {
        const data = JSON.parse(xhr.responseText) as { code?: unknown; message?: unknown }
        if (typeof data.code === 'string') code = data.code
        if (typeof data.message === 'string') message = data.message
      } catch {
        /* 非 JSON 错误体 */
      }
      reject(new ApiError(xhr.status, code, message))
    }
    xhr.send(form)
  })
}
