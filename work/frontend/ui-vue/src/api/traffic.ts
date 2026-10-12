// traffic 态势大屏访问面(Issue #52):只读快照 + SSE,不做任何业务计算。
// 2026-10-11 架构裁定:harness 架构不复用,后端接口面待按前端页面重新规划
// (原实现基准 PR #51 骨架已收回,内容可在该 PR 页面回看;mock 端点暂沿 Issue #52 清单)。
// 一期 mock 演示:全部数据 is_simulated=true,页面显著标注"示例数据"。

import type {
  AlertsSnapshot,
  AssimilationSnapshot,
  AssimilationSnapshotFull,
  CiHistory,
  DispatchInput,
  DispatchReceipt,
  FactorApplied,
  HeatMatrix,
  ManualFactorInput,
  ManualFactorResult,
  PredictResponse,
  RecommendResult,
  SegmentRecord,
  SegmentSourcePair,
  SegmentsSnapshot,
  ThresholdSnapshot,
  TrafficMeta,
  TrafficNetwork,
  TrafficOverview,
  VehiclesSnapshot,
  WritebackInput,
  WritebackReceipt,
} from '../shared/traffic'
import { TRAFFIC_SNAPSHOT_EVENT, type TrafficSnapshotPing } from '../shared/traffic'
import { request } from './http'

// GET /api/traffic/segments → segments 快照(契约 v2.0)
export function getTrafficSegments(): Promise<SegmentsSnapshot> {
  return request<SegmentsSnapshot>('GET', '/api/traffic/segments')
}

// GET /api/traffic/segments/{id} → 单路段详情(含 factors_applied / pred),形状与列表元素一致
export function getTrafficSegment(segmentId: string): Promise<SegmentRecord> {
  return request<SegmentRecord>('GET', `/api/traffic/segments/${encodeURIComponent(segmentId)}`)
}

// GET /api/traffic/vehicles → 孪生车辆位置(仅一期演示用,二期端点下线)
export function getTrafficVehicles(): Promise<VehiclesSnapshot> {
  return request<VehiclesSnapshot>('GET', '/api/traffic/vehicles')
}

// POST /api/traffic/route/recommend → 推荐路线快照(引擎写入 routes.json,接口层只端出来)
export function postRouteRecommend(body: { session_id: string; location: { segment_id: string; offset_m: number } }): Promise<RecommendResult> {
  return request<RecommendResult>('POST', '/api/traffic/route/recommend', { body })
}

// GET /api/traffic/stream(SSE,事件 traffic_snapshot)→ 轻量刷新事件;页面收到后重新拉快照。
// EventSource 无法附带鉴权头;当前端点公开访问,鉴权方案随接口面重新规划一并定稿。
export function subscribeTrafficSnapshot(
  onPing: (ping: TrafficSnapshotPing) => void,
  onState?: (connected: boolean) => void,
): () => void {
  const es = new EventSource('/api/traffic/stream')
  es.onopen = () => onState?.(true)
  es.onerror = () => onState?.(false) // EventSource 会自动重连,状态只作展示
  es.addEventListener(TRAFFIC_SNAPSHOT_EVENT, (ev: MessageEvent) => {
    let payload: TrafficSnapshotPing = { ts: '', is_simulated: true }
    try {
      payload = JSON.parse(ev.data) as TrafficSnapshotPing
    } catch {
      /* 非 JSON 帧:按空载荷处理,只当刷新信号 */
    }
    onPing(payload)
  })
  return () => es.close()
}

// ---------- 决策工作台(Issue #59,接口面新增) ----------

// GET /api/traffic/assimilation → 数据同化状态(哪些边界断面在回灌、门控原因)
export function getTrafficAssimilation(): Promise<AssimilationSnapshot> {
  return request<AssimilationSnapshot>('GET', '/api/traffic/assimilation')
}

// POST /api/traffic/factors → 人工置位因素(管理端口子;mock 侧生效并重算判级,演示行为)
export function postTrafficFactor(body: ManualFactorInput): Promise<ManualFactorResult> {
  return request<ManualFactorResult>('POST', '/api/traffic/factors', { body })
}

// POST /api/traffic/factors/reset → 清空人工置位(演示复位)
export function postTrafficFactorReset(): Promise<{ reset: boolean; is_simulated: boolean }> {
  return request<{ reset: boolean; is_simulated: boolean }>('POST', '/api/traffic/factors/reset')
}

// =====================================================================================
// 四页重做(Issue #78):按 4 张设计稿重新规划出的接口面
// 约定沿用:同源相对路径;每个响应带 is_simulated 信封;只读快照、不做业务计算。
// 后端尚未实现,当前全部由 src/mock/traffic.ts 端出(未匹配路径一律 404)。
// =====================================================================================

// GET /api/traffic/meta → 站点 / 数据源 / 顶栏页签 / 口径角标
export function getTrafficMeta(): Promise<TrafficMeta> {
  return request<TrafficMeta>('GET', '/api/traffic/meta')
}

// GET /api/traffic/overview → 全网 KPI(均速与环比 / 最堵路段 / 在途与采纳率 / 生效因素数 / 等级分布)
export function getTrafficOverview(): Promise<TrafficOverview> {
  return request<TrafficOverview>('GET', '/api/traffic/overview')
}

// GET /api/traffic/network → 路网几何 + 断面(边界/内部) + 落客点 + 场区(地图底图)
export function getTrafficNetwork(): Promise<TrafficNetwork> {
  return request<TrafficNetwork>('GET', '/api/traffic/network')
}

// GET /api/traffic/segments/{id}/sources → 同一路段 video / twin 并排 + 差值(TC-19 展示侧)
export function getTrafficSegmentSources(segmentId: string): Promise<SegmentSourcePair> {
  return request<SegmentSourcePair>('GET', `/api/traffic/segments/${encodeURIComponent(segmentId)}/sources`)
}

// GET /api/traffic/alerts → 告警列表(四态 + 指标依据 + 首次观测时间)
export function getTrafficAlerts(): Promise<AlertsSnapshot> {
  return request<AlertsSnapshot>('GET', '/api/traffic/alerts')
}

// POST /api/traffic/alerts/reset → 复位告警下发 / 回写演示态(mock 侧内存态;刷新页面不清,要清走这里)
export function postTrafficAlertsReset(): Promise<{ reset: boolean; is_simulated: boolean }> {
  return request<{ reset: boolean; is_simulated: boolean }>('POST', '/api/traffic/alerts/reset')
}

// POST /api/traffic/plan/dispatch → 下发分流方案(渠道 + 分流比例),返回回执
export function postPlanDispatch(body: DispatchInput): Promise<DispatchReceipt> {
  return request<DispatchReceipt>('POST', '/api/traffic/plan/dispatch', { body })
}

// POST /api/traffic/plan/ack → 处置回写(认领人 / 动作 / 结果四选一)
export function postPlanAck(body: WritebackInput): Promise<WritebackReceipt> {
  return request<WritebackReceipt>('POST', '/api/traffic/plan/ack', { body })
}

// GET /api/traffic/predict?segment_id=&h=15 → 预测(一期 L0,不报精度数字)
export function getTrafficPredict(segmentId: string, h: 15 | 30 | 60): Promise<PredictResponse> {
  return request<PredictResponse>(
    'GET',
    `/api/traffic/predict?segment_id=${encodeURIComponent(segmentId)}&h=${h}`,
  )
}

// GET /api/traffic/thresholds → 判级阈值 + CI 加权构成 + 变更留痕(只读,P1)
export function getTrafficThresholds(): Promise<ThresholdSnapshot> {
  return request<ThresholdSnapshot>('GET', '/api/traffic/thresholds')
}

// GET /api/traffic/heat-matrix?window=&bucket= → 路段 × 时间热力矩阵(近 window 个桶)
export function getTrafficHeatMatrix(buckets = 12, bucketSec = 60): Promise<HeatMatrix> {
  return request<HeatMatrix>('GET', `/api/traffic/heat-matrix?window=${buckets}&bucket=${bucketSec}`)
}

// GET /api/traffic/ci-history?segment_id=&points=12 → 单路段 CI 走势
export function getTrafficCiHistory(segmentId: string, points = 12): Promise<CiHistory> {
  return request<CiHistory>(
    'GET',
    `/api/traffic/ci-history?segment_id=${encodeURIComponent(segmentId)}&points=${points}`,
  )
}

// GET /api/traffic/factors?segment_id= → 当前生效因素清单(可选按路段过滤)
export function getTrafficFactors(segmentId?: string): Promise<{ ts: string; is_simulated: true; factors: (FactorApplied & { segment_id: string })[] }> {
  const q = segmentId ? `?segment_id=${encodeURIComponent(segmentId)}` : ''
  return request('GET', `/api/traffic/factors${q}`)
}

// GET /api/traffic/assimilation → 数据同化状态(含断面 role:仅 role=boundary 允许回灌)
export function getTrafficAssimilationFull(): Promise<AssimilationSnapshotFull> {
  return request<AssimilationSnapshotFull>('GET', '/api/traffic/assimilation')
}
