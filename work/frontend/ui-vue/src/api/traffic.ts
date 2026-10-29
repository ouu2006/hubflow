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
  ReportCompare,
  RouteOptionsSnapshot,
  RoutePlanAnchor,
  RoutePlanResult,
  RoutePointsSnapshot,
  RouteSnapResult,
  RouteStepsSnapshot,
  ScenarioInput,
  ScenarioResult,
  SegmentRecord,
  SegmentSeries,
  SegmentSourcePair,
  SegmentsSnapshot,
  ThresholdSnapshot,
  EmergencyState,
  TrafficContext,
  TrafficMeta,
  TrafficNetwork,
  TrafficOverview,
  VehiclesSnapshot,
  WritebackInput,
  WritebackReceipt,
} from '../shared/traffic'
import { TRAFFIC_SNAPSHOT_EVENT, type TrafficSnapshotPing } from '../shared/traffic'
import { request } from './http'

/**
 * 快照类只读取数的可选参数（Issue IKPFR4）：
 *   · `signal` —— 切页 / 切站时中止在途请求（旧站的响应不该再回来落地）；
 *   · `station` —— 把这次请求钉在某个站键上（两站常驻预热时替另一站取数）。
 * 两个都不改变端点路径、请求头与响应形状。
 */
export interface SnapshotFetchOptions {
  signal?: AbortSignal
  station?: string
}

// GET /api/traffic/segments → segments 快照(契约 v2.0)
export function getTrafficSegments(opts: SnapshotFetchOptions = {}): Promise<SegmentsSnapshot> {
  return request<SegmentsSnapshot>('GET', '/api/traffic/segments', opts)
}

// GET /api/traffic/segments/{id} → 单路段详情(含 factors_applied / pred),形状与列表元素一致
export function getTrafficSegment(segmentId: string): Promise<SegmentRecord> {
  return request<SegmentRecord>('GET', `/api/traffic/segments/${encodeURIComponent(segmentId)}`)
}

// GET /api/traffic/segment-series?segment_id=&limit= → 段级真时序(孪生 60 s 快照)
// 口径:接口层只回产物里真实存在的点,不插值不补点;缺产物如实 404,页面按空窗降级。
// `signal` 是切路段的丢弃通道:先发的旧段请求晚回来会盖掉新段的曲线,
// 图上就成了「选了 A 段、画的是 B 段」——只多一个中止通道,不改端点/路径/响应形状。
export function getTrafficSegmentSeries(
  segmentId: string,
  limit?: number,
  opts: SnapshotFetchOptions = {},
): Promise<SegmentSeries> {
  const tail = typeof limit === 'number' && limit > 0 ? `&limit=${limit}` : ''
  return request<SegmentSeries>(
    'GET',
    `/api/traffic/segment-series?segment_id=${encodeURIComponent(segmentId)}${tail}`,
    opts,
  )
}

// GET /api/traffic/vehicles → 孪生车辆位置(仅一期演示用,二期端点下线)
export function getTrafficVehicles(opts: SnapshotFetchOptions = {}): Promise<VehiclesSnapshot> {
  return request<VehiclesSnapshot>('GET', '/api/traffic/vehicles', opts)
}

// POST /api/traffic/route/recommend → 推荐路线快照(引擎写入 routes.json,接口层只端出来)
export function postRouteRecommend(body: { session_id: string; location: { segment_id: string; offset_m: number } }): Promise<RecommendResult> {
  return request<RecommendResult>('POST', '/api/traffic/route/recommend', { body })
}

// GET /api/traffic/route/options → 引擎路线产物的 OD/session 摘要列表（Issue IKNAUI，非契约辅助端点）
// 供大屏「整条路线规划」选择器；缺产物时接口层如实 404，页面按空窗 + note 降级（不编 ETA）。
export function getTrafficRouteOptions(): Promise<RouteOptionsSnapshot> {
  return request<RouteOptionsSnapshot>('GET', '/api/traffic/route/options')
}

// =====================================================================================
// 自定义起终点算路（业主 2026-10-28 当面要求；非契约辅助端点，真接口才有）
// 口径：**页面不选段号、不做地图匹配**——点图给坐标，吸附 / 算路 / ETA / 备选全在后端；
// 前端只负责「问 → 原样显示」。不可达时后端仍回 HTTP 200 + reachable:false，**不是错误**。
// =====================================================================================

/**
 * POST /api/traffic/route/snap → 点击坐标吸附到最近路段。
 * `site` 省略 = 按请求头 `X-Station-Pack` 的当前站点包（与其余接口同口径）。
 */
export function postRouteSnap(body: { site?: string; lon: number; lat: number }): Promise<RouteSnapResult> {
  return request<RouteSnapResult>('POST', '/api/traffic/route/snap', { body })
}

/**
 * POST /api/traffic/route/plan → 一主二备（+ 离站单独算）。
 * 起 / 终点传 `{lon,lat}`（后端吸附），也支持 `{point_id}` / `{segment_id,offset_m}` 两种形态。
 */
export function postRoutePlan(body: {
  site?: string
  origin: RoutePlanAnchor
  destination: RoutePlanAnchor
  with_departure?: boolean
}): Promise<RoutePlanResult> {
  return request<RoutePlanResult>('POST', '/api/traffic/route/plan', { body })
}

// GET /api/traffic/route/points?site= → 候选点位清单（辅助；页面选点走地图点击，不用这份）
export function getRoutePoints(site?: string): Promise<RoutePointsSnapshot> {
  const q = site ? `?site=${encodeURIComponent(site)}` : ''
  return request<RoutePointsSnapshot>('GET', `/api/traffic/route/points${q}`)
}

/**
 * GET /api/traffic/route/{request_id}/steps → 该请求下各条路线的 `steps[]`（**非契约辅助端点**）。
 *
 * 为什么单开一条（lead 2026-10-29 拍板）：`/route/options`、`/route/recommend` 的 `arrival_route`
 * 不带 `steps` / `start_point`，而契约字段集不动（改一次要业主侧全量回归）。大屏因此改为
 * 「按 request_id 单拉一份」，一次拿全 arrival / departure / pickup / alternatives 的 steps，
 * 浏览器侧按 request_id 缓存 —— 这样路线箭头拿到的是**后端权威行进序**，不是前端启发式。
 *
 * 超时压到 4 s：这条挂了不能拖着整屏等；拿不到就由调用方退回链式定向并**打日志**（不许静默降级）。
 */
export function getRouteSteps(requestId: string, opts: { timeoutMs?: number; signal?: AbortSignal } = {}): Promise<RouteStepsSnapshot> {
  return request<RouteStepsSnapshot>('GET', `/api/traffic/route/${encodeURIComponent(requestId)}/steps`, {
    timeoutMs: 4000,
    ...opts,
  })
}

// POST /api/traffic/locate → 一期定位结果（Issue IKP5C6；非契约辅助端点，真接口才有）
// 口径：接口层只端引擎产物 `requests[].location`（孪生真值直读），**不做地图匹配、不编定位**；
// 页面据此显示“本次起点”的来源/置信度，并给使用者一个显式确认动作。
export interface LocateResult {
  segment_id: string | null
  offset_m: number | null
  match_confidence: number | null
  /** 'twin' = 孪生真值；二期才是 'app_gnss'。缺省按 twin 解释（接口层已兜底） */
  source: string
  data_source: string
  data_source_note: string
  session_matched: boolean
  requested_session_id: string | null
  is_simulated: true
  note: string
}

export function postTrafficLocate(body: { session_id?: string } = {}): Promise<LocateResult> {
  return request<LocateResult>('POST', '/api/traffic/locate', { body })
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
export function getTrafficMeta(opts: SnapshotFetchOptions = {}): Promise<TrafficMeta> {
  return request<TrafficMeta>('GET', '/api/traffic/meta', opts)
}

// GET /api/traffic/overview → 全网 KPI(均速与环比 / 最堵路段 / 在途与采纳率 / 生效因素数 / 等级分布)
export function getTrafficOverview(opts: SnapshotFetchOptions = {}): Promise<TrafficOverview> {
  return request<TrafficOverview>('GET', '/api/traffic/overview', opts)
}

// GET /api/traffic/network → 路网几何 + 断面(边界/内部) + 落客点 + 场区(地图底图)
export function getTrafficNetwork(): Promise<TrafficNetwork> {
  return request<TrafficNetwork>('GET', '/api/traffic/network')
}

// GET /api/traffic/segments/{id}/sources → 同一路段 video / twin 并排 + 差值(TC-19 展示侧)
export function getTrafficSegmentSources(
  segmentId: string,
  opts: SnapshotFetchOptions = {},
): Promise<SegmentSourcePair> {
  return request<SegmentSourcePair>(
    'GET',
    `/api/traffic/segments/${encodeURIComponent(segmentId)}/sources`,
    opts,
  )
}

// GET /api/traffic/alerts → 告警列表(四态 + 指标依据 + 首次观测时间)
export function getTrafficAlerts(opts: SnapshotFetchOptions = {}): Promise<AlertsSnapshot> {
  return request<AlertsSnapshot>('GET', '/api/traffic/alerts', opts)
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
export function getTrafficThresholds(opts: SnapshotFetchOptions = {}): Promise<ThresholdSnapshot> {
  return request<ThresholdSnapshot>('GET', '/api/traffic/thresholds', opts)
}

// GET /api/traffic/heat-matrix?window=&bucket= → 路段 × 时间热力矩阵(近 window 个桶)
export function getTrafficHeatMatrix(
  buckets = 12,
  bucketSec = 60,
  opts: SnapshotFetchOptions = {},
): Promise<HeatMatrix> {
  return request<HeatMatrix>(
    'GET',
    `/api/traffic/heat-matrix?window=${buckets}&bucket=${bucketSec}`,
    opts,
  )
}

// GET /api/traffic/ci-history?segment_id=&points=12 → 单路段 CI 走势
export function getTrafficCiHistory(
  segmentId: string,
  points = 12,
  opts: SnapshotFetchOptions = {},
): Promise<CiHistory> {
  return request<CiHistory>(
    'GET',
    `/api/traffic/ci-history?segment_id=${encodeURIComponent(segmentId)}&points=${points}`,
    opts,
  )
}

// GET /api/traffic/factors?segment_id= → 当前生效因素清单(可选按路段过滤)
/** 生效因素清单。`segmentId` 省略 = 全网(各路段展平);`opts` 见 `SnapshotFetchOptions` */
export function getTrafficFactors(
  segmentId?: string,
  opts: SnapshotFetchOptions = {},
): Promise<{ ts: string; is_simulated: true; factors: (FactorApplied & { segment_id: string })[] }> {
  const q = segmentId ? `?segment_id=${encodeURIComponent(segmentId)}` : ''
  return request('GET', `/api/traffic/factors${q}`, opts)
}

// GET /api/traffic/assimilation → 数据同化状态(含断面 role:仅 role=boundary 允许回灌)
export function getTrafficAssimilationFull(): Promise<AssimilationSnapshotFull> {
  return request<AssimilationSnapshotFull>('GET', '/api/traffic/assimilation')
}

// =====================================================================================
// 三页收敛(Issue #77):环境上下文 + 场景注入
// 口径:天气 / 时段是**编造的演示值**(拿不到真实数据),一律标「演示数据(模拟)」;
// 场景注入与「人工置位」(F07 / F08 / F11)是两个口子,不得混称。
// =====================================================================================

// GET /api/traffic/context → 环境上下文(天气 / 时间 + 折算出的因素 F01/F02/F03/F10)
export function getTrafficContext(): Promise<TrafficContext> {
  return request<TrafficContext>('GET', '/api/traffic/context')
}

// GET /api/traffic/report/compare → 效果对比报表(接口层无报表产物时 rows 为空 + note,页面如实降级)
export function getTrafficReportCompare(): Promise<ReportCompare> {
  return request<ReportCompare>('GET', '/api/traffic/report/compare')
}

// GET /api/traffic/emergency → 应急态(TC-10):停下路线引导,替换为「请服从现场指挥」
// 口径:接口层只派生不重算 —— active 时页面**必须**收起推荐,guidance === 'stopped'
export function getTrafficEmergency(): Promise<EmergencyState> {
  return request<EmergencyState>('GET', '/api/traffic/emergency')
}

// POST /api/traffic/scenario → 场景注入(天气 / 时段 / 需求倍率 → 因素),返回判级前后对照
export function postTrafficScenario(body: ScenarioInput): Promise<ScenarioResult> {
  return request<ScenarioResult>('POST', '/api/traffic/scenario', { body })
}

// POST /api/traffic/scenario/reset → 清场景注入(演示复位,与 factors/reset 同口径)
export function postTrafficScenarioReset(): Promise<{ reset: boolean; is_simulated: boolean }> {
  return request<{ reset: boolean; is_simulated: boolean }>('POST', '/api/traffic/scenario/reset')
}
