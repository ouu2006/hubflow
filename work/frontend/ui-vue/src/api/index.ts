// 冻结契约端点函数(总控 00 §5.2 八端点)。禁止在此之外新增任何 /api 调用面。

import type { DocRecord, Health, LoginResult, SessionResult, TraceItem } from '../shared/protocol'
import { request } from './http'
import { ssePost } from './sse'
import type { SseListener } from './sse'

// POST /api/auth/login  {user, password} → {token}
export function login(user: string, password: string): Promise<LoginResult> {
  return request<LoginResult>('POST', '/api/auth/login', { body: { user, password }, auth: false })
}

// POST /api/sessions  → {session_id}
export function createSession(): Promise<SessionResult> {
  return request<SessionResult>('POST', '/api/sessions')
}

// POST /api/sessions/{id}/chat  {text} → SSE(delta | finish | usage | error)
export function chatStream(
  sessionId: string,
  text: string,
  onEvent: SseListener,
  signal?: AbortSignal,
): Promise<void> {
  return ssePost(`/api/sessions/${encodeURIComponent(sessionId)}/chat`, { text }, onEvent, signal)
}

// GET /api/kb/documents  → [{doc_id, name, version, status}]
export function listDocuments(): Promise<DocRecord[]> {
  return request<DocRecord[]>('GET', '/api/kb/documents')
}

// POST /api/kb/documents  multipart → {doc_id, stored_path}(见 api/upload.ts,带进度)
export { uploadDocument } from './upload'
export type { UploadHooks } from './upload'

// DELETE /api/kb/documents/{doc_id}  → 204
export function deleteDocument(docId: string): Promise<void> {
  return request<void>('DELETE', `/api/kb/documents/${encodeURIComponent(docId)}`)
}

// GET /api/answers/{answer_id}/trace  → [{doc_id, snippet, score, source}]
export function getTrace(answerId: string): Promise<TraceItem[]> {
  return request<TraceItem[]>('GET', `/api/answers/${encodeURIComponent(answerId)}/trace`)
}

// GET /api/health  → {kernel, db}
export function getHealth(): Promise<Health> {
  return request<Health>('GET', '/api/health', { auth: false })
}
