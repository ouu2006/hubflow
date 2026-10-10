// 冻结契约(总控 00 §5.2)+ mock 侧补充裁定。
// 此文件被浏览器代码与 mock 中间件(vite.config 图)共用,必须保持
// 运行时零依赖、不触碰 DOM/Node 专有全局。

// ---------- REST 契约类型 ----------

export interface LoginResult {
  token: string
}

export interface SessionResult {
  session_id: string
}

export interface DocRecord {
  doc_id: string
  name: string
  version: number // mock 裁定:整数版本号,展示层渲染为 v{n}
  status: DocStatus
}

export type DocStatus = 'ready' | 'processing' | 'failed'

export interface UploadResult {
  doc_id: string
  stored_path: string
}

export interface TraceItem {
  doc_id: string
  snippet: string
  score: number
  source: string
}

export interface Health {
  kernel: 'up' | 'down'
  db: 'up' | 'down' | 'dev'
}

// ---------- SSE 契约(事件名冻结;载荷形状为 mock 裁定,B 实现对齐) ----------

export const SSE_EVENT = {
  delta: 'delta', // {text: string} 增量文本(字级)
  usage: 'usage', // {prompt_tokens, completion_tokens, total_tokens}
  finish: 'finish', // {answer_id} 收尾事件(delta* → usage → finish)
  error: 'error', // {code, message} 注入失败后流终止
} as const

export interface DeltaPayload {
  text: string
}

export interface UsagePayload {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export interface FinishPayload {
  answer_id: string
}

export interface SseErrorPayload {
  code: string
  message: string
}

// ---------- 护栏 ----------

// 与内核桥 16MB 帧限呼应(总控 §7-4):前端预检与 mock 服务端护栏共用同一常量
export const MAX_UPLOAD_BYTES = 16 * 1024 * 1024

export function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${bytes} B`
}

// ---------- 关键词提取(客户端高亮与 mock 溯源构造共用,保证命中一致) ----------

export function extractKeywords(question: string): string[] {
  const tokens = question
    .split(/[\s,，。.、;；:：!！?？'"「」《》()[\]{}…—·]+/)
    .map((t) => t.trim())
    .filter((t) => t.length >= 2)
  // 过长 token(无空格分词的中文长句)取前 6 字作为检索/高亮锚点
  const anchors = tokens.filter((t) => t.length > 8).map((t) => t.slice(0, 6))
  return [...new Set([...tokens, ...anchors])].slice(0, 8)
}
