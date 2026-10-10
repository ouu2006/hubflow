// mock 内存态:文档库 / token / 会话 / 溯源缓存。dev server 生命周期即持久期,
// 重启后清空(溯源查询对未知 answer_id 走确定性合成兜底,保证演示不塌)。

import { extractKeywords, type DocRecord, type TraceItem } from '../shared/protocol.ts'
import { rid } from './util.ts'

export interface MockDoc extends DocRecord {
  stored_path: string
}

export interface TraceEntry {
  question: string
  items: TraceItem[]
}

const SEED_DOCS: MockDoc[] = [
  { doc_id: 'doc-0001', name: '内核桥接协议说明.pdf', version: 2, status: 'ready', stored_path: 'local_store/doc-0001.pdf' },
  { doc_id: 'doc-0002', name: 'openGauss三域DDL草案.md', version: 1, status: 'ready', stored_path: 'local_store/doc-0002.md' },
  { doc_id: 'doc-0003', name: 'FastAPI宿主接口契约.docx', version: 3, status: 'ready', stored_path: 'local_store/doc-0003.docx' },
  { doc_id: 'doc-0004', name: '鲲鹏移植清单.xlsx', version: 1, status: 'processing', stored_path: 'local_store/doc-0004.xlsx' },
  { doc_id: 'doc-0005', name: 'RAG流水线设计评审纪要.pdf', version: 2, status: 'failed', stored_path: 'local_store/doc-0005.pdf' },
  { doc_id: 'doc-0006', name: '前端三页原型说明.md', version: 1, status: 'ready', stored_path: 'local_store/doc-0006.md' },
]

export const db = {
  docs: SEED_DOCS.map((d) => ({ ...d })),
  tokens: new Set<string>(),
  sessions: new Set<string>(),
  traces: new Map<string, TraceEntry>(),
  seq: 7,
}

export function addUploadedDoc(filename: string): MockDoc {
  const docId = `doc-${String(db.seq).padStart(4, '0')}`
  db.seq += 1
  const sameName = db.docs.filter((d) => d.name === filename)
  // 同名重传 = 版本递增(版本态演示);异名 = v1
  const version = sameName.length ? Math.max(...sameName.map((d) => d.version)) + 1 : 1
  const dot = filename.lastIndexOf('.')
  const ext = dot > 0 ? filename.slice(dot) : '.bin'
  const doc: MockDoc = {
    doc_id: docId,
    name: filename,
    version,
    status: 'processing',
    stored_path: `local_store/${docId}${ext}`,
  }
  db.docs.push(doc)
  return doc
}

// ---------- 假答案 / 假溯源构造(与客户端 extractKeywords 共用,保证高亮命中) ----------

const SOURCES = ['hybrid:vector#1', 'hybrid:bm25#2', 'graph:entity#1']
const SCORES = [0.92, 0.85, 0.73]
const SNIPPET_TPL = [
  '……第 3 节:关于「{kw}」的处理,须经 16MB 帧限校验后入桥,由宿主侧登记元数据(当前 v{v})……',
  '……《{name}》记载:「{kw}」关联三域之中的落账字段设计,检索时按版本号降序召回……',
  '……图实体对齐显示「{kw}」与内核 sidecar 监管重启流程存在强关联,置信度中高……',
]

function pickDocs(seed: string): MockDoc[] {
  const pool = db.docs.filter((d) => d.status !== 'failed')
  if (!pool.length) return []
  const off = hash32(seed) % pool.length
  const rotated = pool.map((_, i) => pool[(i + off) % pool.length])
  return rotated.slice(0, 3)
}

export function buildAnswer(question: string): string {
  const kw = primaryKeyword(question)
  const picks = pickDocs(question)
  const body = picks.length
    ? picks.map(
        (d, i) =>
          `${i + 1}. 《${d.name}》(v${d.version}):与「${kw}」相关的第 ${i + 1} 节要点——入桥校验、落盘登记与检索召回均按冻结契约执行;`,
      )
    : ['知识库暂无可用文档,请先在「文档管理」页上传后重试;']
  return [
    `围绕「${kw}」完成知识库混合检索,归纳如下:`,
    '',
    ...body,
    '',
    `以上为 mock 生成的回答(共 ${picks.length} 个片段参与),点击回答下方「溯源」可查看引用明细与得分。`,
  ].join('\n')
}

export function buildTrace(question: string): TraceItem[] {
  const kw = primaryKeyword(question)
  return pickDocs(question).map((d, i) => ({
    doc_id: d.doc_id,
    snippet: SNIPPET_TPL[i % SNIPPET_TPL.length]
      .replaceAll('{kw}', kw)
      .replaceAll('{name}', d.name)
      .replaceAll('{v}', String(d.version)),
    score: SCORES[i % SCORES.length],
    source: SOURCES[i % SOURCES.length],
  }))
}

// mock 进程重启后 traces 已清空:按 answer_id 确定性合成,页面不空转
export function resolveTrace(answerId: string): TraceItem[] {
  const hit = db.traces.get(answerId)
  if (hit) return hit.items
  return pickDocs(answerId).map((d, i) => ({
    doc_id: d.doc_id,
    snippet: `……(确定性合成片段:answer_id ${answerId} 的原始问答缓存已随 mock 重启清空)《${d.name}》v${d.version} 与该回答的引用关联仍在,可跳转文档管理页核对……`,
    score: [0.88, 0.79, 0.66][i % 3],
    source: SOURCES[i % SOURCES.length],
  }))
}

function primaryKeyword(question: string): string {
  const kws = extractKeywords(question)
  return kws[0] ?? question.slice(0, 6) ?? '检索'
}

function hash32(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

// 保留 rid 引用面:会话/答案 id 由本模块族统一生成
export function newSessionId(): string {
  return rid('sess')
}

export function newToken(): string {
  return rid('mock-token')
}

export function newAnswerId(): string {
  return rid('ans')
}
