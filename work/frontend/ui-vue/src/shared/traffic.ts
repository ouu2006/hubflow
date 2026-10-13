// traffic 态势大屏共享类型与四级编码(运行时零依赖,浏览器 / mock 中间件共用)。
// 字段名逐个对照 docs/数据契约.md v2.0(snake_case);四级色值与图标照抄手册 §6.2,不新造。

export type CongestionLevel = 1 | 2 | 3 | 4

export type TrafficSource = 'video' | 'twin'

export type FactorTarget = 'c' | 'v_f' | 'demand' | 'lanes' | 'confidence'

export interface FactorApplied {
  factor_id: string // F01~F14,对应《全流程计划》第 6 节因素登记表
  name: string
  target: FactorTarget
  multiplier: number
  until: string // ISO 时间,不留空
}

export interface PredPoint {
  q_vph: number
  level: CongestionLevel
}

// 一期只做 L0(历史同期均值),不报精度数字;pred 可选,缺省不写键(不写 null 占位)
export interface PredBlock {
  h15: PredPoint
  h30: PredPoint
  model: 'L0'
}

export interface SegmentRecord {
  segment_id: string
  source: TrafficSource
  q_vph?: number
  v_kmh?: number
  v_f_kmh?: number
  k_vpk?: number
  L_q_m?: number
  L_seg_m?: number
  T_d_min?: number
  x?: number
  c_base_vph?: number
  c_vph?: number
  factors_applied?: FactorApplied[]
  ci?: number
  level: CongestionLevel
  level_name?: string
  triggered_by?: string[]
  confidence?: number
  data_age_s?: number
  pred?: PredBlock
  is_simulated: true
}

export interface SegmentsSnapshot {
  ts: string
  window_sec: number
  is_simulated: true
  segments: SegmentRecord[]
}

export type DriverType = 'D1' | 'D2' | 'D3'

// 契约 §四:state 取值集合封闭,新增状态要先改契约
export type VehicleState = '行驶' | '排队' | '落客服务' | '候客' | '违停' | '已离开'

// 契约 §四:is_simulated 只写在信封层(顶层),车辆元素不重复放该字段
export interface VehicleRecord {
  vehicle_id: string
  driver_type: DriverType
  segment_id: string
  offset_m: number
  lon: number
  lat: number
  state: VehicleState
  /** 是否已被引导(采纳率与前后车协同举证用) */
  guided: boolean
  /** 是否演示绑定车(同一时刻最多一辆 true) */
  is_demo_bound: boolean
}

export interface VehiclesSnapshot {
  ts: string
  is_simulated: true
  vehicles: VehicleRecord[]
}

export interface RoutePath {
  path_id: string
  segments: string[]
  eta_min: number
  dropoff_point?: string
  walk_min?: number
}

/** 备选:契约示例在 path_id / eta_min 之外必带 reason;segments 等渲染字段与 arrival_route 同族 */
export interface AlternativePath {
  path_id: string
  eta_min: number
  reason: string
  segments?: string[]
  dropoff_point?: string
  walk_min?: number
}

// 契约 §2.1:预约格数 / 租约秒数(默认 90s,未确认采纳即释放)
export interface ReservationBlock {
  slots_reserved: number
  lease_expire_s: number
  harm_check?: { max_eta_increase_s: number; max_slot_x: number; passed: boolean }
}

export type LocateSource = 'twin' | 'app_gnss'

export interface RecommendResult {
  request_id: string
  session_id: string
  driver_type: DriverType
  parking_mode: 'S1' | 'S2'
  location: { segment_id: string; offset_m: number; match_confidence: number; source: LocateSource }
  arrival_route: RoutePath
  departure_route: RoutePath | null
  pickup_route: RoutePath | null
  alternatives: AlternativePath[] // 契约:备选 ≥2 条
  reservation: ReservationBlock
  why: string
  is_simulated: true
}

// ---------- 四级编码(手册 §6.2,照抄) ----------

export interface LevelStyle {
  name: string
  /** 图形色(地图路段 / 热力晕染 / 色阶 / 等级条) */
  color: string
  /** 文字色(深一阶,浅底上保证可读性;手册 §6.2 表「文字色值」列) */
  text: string
  bars: number // 竖条数图标;与颜色、文字共同构成三重编码
}

// ⚠️ 2026-10-12 配色整体切换 TDesign Light(手册 §6.2 / §6.2.1 / §6.2.2):
// 图形色取官方色板(success-5 / warning-5 / error-6 / gray-7),文字色深一阶;
// 旧值(蓝 #1E6FD9 / 黄 #F2B705 / 橙 #E8760C / 红 #C62828 / 灰 #8C8C8C)已作废。
// 关键语义:旧「畅通蓝」与品牌蓝 #0052D9 撞车,故畅通改 success 绿——等级色**不得**使用品牌蓝。
export const LEVELS: Record<CongestionLevel, LevelStyle> = {
  1: { name: '畅通', color: '#2BA471', text: '#006C45', bars: 1 },
  2: { name: '缓行', color: '#E9B32E', text: '#A06A00', bars: 2 },
  3: { name: '拥堵', color: '#E37318', text: '#BE5A00', bars: 3 },
  4: { name: '严重拥堵', color: '#D54941', text: '#AD352F', bars: 4 },
}

// 非等级状态:数据陈旧(> 120 s【待标定】)显示灰色,只展示不推荐(TC-11 展示侧)
export const UNAVAILABLE: LevelStyle = { name: '数据不可用', color: '#8B8B8B', text: '#8B8B8B', bars: 0 }

export const STALE_AFTER_S = 120

/**
 * ISO8601(可带偏移)→ `YYYY-MM-DD HH:mm:ss`(本地展示口径)。
 * 快照时间在页面上只作展示,统一走本函数——避免顶栏/页脚出现 `2026-10-12T16:23:54+08:00` 这种机器格式。
 * 解析失败原样返回(不猜、不产出 Invalid Date)。
 */
export function formatStamp(iso: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number): string => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

/** 只取时分秒(首次观测时间等行内展示用) */
export function formatClock(iso: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number): string => String(n).padStart(2, '0')
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

export function isStale(seg: SegmentRecord): boolean {
  return (seg.data_age_s ?? 0) > STALE_AFTER_S
}

export function levelStyle(seg: SegmentRecord): LevelStyle {
  return isStale(seg) ? UNAVAILABLE : LEVELS[seg.level]
}

/** 等级文字色(深一阶):用于浅底上的等级文字,与图形色同源但对比度更高 */
export function levelTextColor(seg: SegmentRecord): string {
  return levelStyle(seg).text
}

// ---------- 拥挤指数(CI)展示口径(Issue #66;手册 §6.5 第 1 条) ----------
// 硬口径:CI 只用于**热力展示与辅助排序**,**不得作为判级依据**;CI 与四项指标冲突时一律以四项指标为准。
// 权重与档位边界不在前端定义——真实来源是 stations/thresholds.json(唯一写手开发B)。

export const CI_MAX = 100

/** 视图模式:'level' = 四级视图(判级产出) · 'index' = 拥挤指数视图(展示量,手册 §11.2"可切拥挤指数视图") */
export type CongestionViewMode = 'level' | 'index'

/** CI 档位边界 = **展示口径**(文档未定档,此处均分四档;判级一律以 level 为准,图例逐条写明) */
export const CI_BANDS: readonly number[] = [0, 25, 50, 75, 100]

export const CI_DISCLAIMER =
  'CI(拥挤指数)只用于热力展示与辅助排序,不得作为判级依据;与四项指标冲突时一律以四项指标为准(手册 §6.5 第 1 条)'

export const CI_BAND_NOTE = '档位边界为展示口径(文档未定档),判级一律以 level 为准'

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [
    Number.parseInt(h.slice(0, 2), 16),
    Number.parseInt(h.slice(2, 4), 16),
    Number.parseInt(h.slice(4, 6), 16),
  ]
}

function rgbToHex(rgb: [number, number, number]): string {
  return `#${rgb.map((v) => Math.round(Math.min(255, Math.max(0, v))).toString(16).padStart(2, '0')).join('')}`
}

function lerpColor(a: string, b: string, t: number): string {
  const [r1, g1, b1] = hexToRgb(a)
  const [r2, g2, b2] = hexToRgb(b)
  return rgbToHex([r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t])
}

// 色阶锚点取手册 §6.2 的四级色值(档心为锚点,档间线性过渡)——
// **不自造第五套颜色语义**;灰 #8B8B8B 仍只表示"数据不可用",不参与色阶。
//
// ⚠️ 已知取舍(独立审查发现,记此不改):TDesign 下畅通绿 #2BA471 与缓行黄 #E9B32E 之间的
//   线性过渡中点必然接近中性灰——本实现的过渡中点落在 ci≈25(锚点 12.5 / 37.5 的中点),
//   视觉上与"数据不可用"灰 #8B8B8B 相近。这是**手册 §6.2 四级色顺序本身**带来的,不是自造色阶;
//   改锚点顺序或改色相会动到手册语义,故不改。判据仍以灰档行(三重编码 + 文字「不可用」)为准,
//   不靠颜色单通道区分"不可用"与"低 ci"。
const CI_ANCHORS: { at: number; color: string }[] = [
  { at: 12.5, color: LEVELS[1].color },
  { at: 37.5, color: LEVELS[2].color },
  { at: 62.5, color: LEVELS[3].color },
  { at: 87.5, color: LEVELS[4].color },
]

/** CI → 颜色:0~100 线性映射到四级色阶(超出范围按端点夹取) */
export function ciColor(ci: number): string {
  // 非有限入参(NaN / ±Infinity)不落到函数末尾被画成红色"严重拥堵",与 ciAvailable 同口径交灰档
  if (!Number.isFinite(ci)) return UNAVAILABLE.color
  const v = Math.min(CI_MAX, Math.max(0, ci))
  const first = CI_ANCHORS[0]!
  const last = CI_ANCHORS[CI_ANCHORS.length - 1]!
  if (v <= first.at) return first.color
  if (v >= last.at) return last.color
  for (let i = 0; i < CI_ANCHORS.length - 1; i++) {
    const a = CI_ANCHORS[i]!
    const b = CI_ANCHORS[i + 1]!
    if (v >= a.at && v <= b.at) return lerpColor(a.color, b.color, (v - a.at) / (b.at - a.at))
  }
  return last.color
}

/** 该路段能否画拥挤指数:缺 `ci` 或数据陈旧 → 灰色"数据不可用"(TC-11),**绝不落进通配色** */
export function ciAvailable(seg: SegmentRecord): boolean {
  return !isStale(seg) && typeof seg.ci === 'number' && Number.isFinite(seg.ci)
}

/** 拥挤指数渲染色(不可用即灰) */
export function ciStyleColor(seg: SegmentRecord): string {
  return ciAvailable(seg) ? ciColor(seg.ci as number) : UNAVAILABLE.color
}

/** 指数色阶图例的渐变色标(CSS linear-gradient 用,自低到高) */
export function ciGradientCss(): string {
  const stops = [0, 20, 40, 60, 80, 100]
  return `linear-gradient(90deg, ${stops.map((s) => `${ciColor(s)} ${s}%`).join(', ')})`
}

// ---------- SSE ----------

// 事件名是新增的(不改既有事件名),与 work/assembly/traffic.py 的 GET /api/traffic/stream 对齐
export const TRAFFIC_SNAPSHOT_EVENT = 'traffic_snapshot'

export interface TrafficSnapshotPing {
  ts: string
  is_simulated: true
  note?: string
}

// ---------- 决策工作台(Issue #59,接口面新增;字段 snake_case,非契约 v2.0 冻结范围) ----------

/** 数据同化单断面状态(契约 §数据同化 gate 字段口径) */
export type AssimilationGateReason = 'confidence_low' | 'data_age' | 'deviation_fuse' | null

export interface AssimilationRecord {
  point_id: string
  segment_id: string
  enabled: boolean
  flow_dev_pct: number | null
  speed_dev_pct: number | null
  gate_reason: AssimilationGateReason
  gate_detail: string | null
  last_apply_at: string | null
}

export interface AssimilationSnapshot {
  ts: string
  is_simulated: true
  gate: { confidence_min: number; data_age_max_s: number }
  records: AssimilationRecord[]
}

/** 人工置位因素输入(mock 侧生效,管理端口子,手册第 19 章) */
export interface ManualFactorInput {
  segment_id: string
  factor_id: string
  name: string
  target: 'c' | 'demand' | 'lanes'
  multiplier: number
}

export interface ManualFactorResult {
  applied: true
  segment_id: string
  level: CongestionLevel
  level_name: string
  factors_applied: FactorApplied[]
  is_simulated: true
}

// =====================================================================================
// 四页重做(Issue #78)新增接口面
// 依据 2026-10-11 裁定「后端接口面按前端页面重新规划」:本段即按 4 张设计稿重新规划出的
// 端点形状。前端只读快照 / 只端出结果,不做业务计算;每个响应仍带 is_simulated 信封。
// =====================================================================================

// ---------- 站点与数据源元信息(顶栏 / 页头共用) ----------

export interface TrafficMeta {
  ts: string
  is_simulated: true
  station: { station_id: string; name: string; subtitle: string }
  /** 两条链路(D1′):视频感知链路 + 孪生链路 */
  sources: { key: TrafficSource; name: string }[]
  /** 口径角标(手册要求页面常驻「演示数据(模拟)· 双数据源」) */
  demo_badge: string
  /** 路由 ↔ 页面标题(顶栏页签;当前页由前端高亮) */
  tabs: { key: string; name: string; route: string }[]
}

// ---------- 全网 KPI(态势总览顶部 KPI 条) ----------

export interface LevelDistributionRow {
  level: CongestionLevel | 0 // 0 = 数据不可用(非等级,单独成档)
  name: string
  count: number
}

export interface TrafficOverview {
  ts: string
  is_simulated: true
  window_sec: number
  /** 全网平均车速(km/h,窗口均值的加权平均) */
  avg_speed_kmh: number
  /** 与上一版快照的差(负 = 变慢) */
  avg_speed_delta_kmh: number
  /** 最堵路段(按 x 饱和度的最高档口径,同档取 x 大者) */
  worst_segment: { segment_id: string; name: string; level: CongestionLevel; x: number } | null
  /** 站前在途车辆(孪生真值口径) */
  vehicles_inbound: number
  vehicles_guided: number
  /** 采纳率 0~1 */
  guided_rate: number
  /** 当前生效因素条数(各路段 factors_applied 展平后计数) */
  active_factors: number
  level_distribution: LevelDistributionRow[]
  segment_total: number
  unavailable_count: number
}

// ---------- 同一路段双数据源并排(TC-19 展示侧) ----------

export interface SegmentSourceSlot {
  source: TrafficSource
  record: SegmentRecord | null
  available: boolean
}

/** 并排差值行:video − twin(负数表示视频链路更低) */
export interface SegmentSourceDelta {
  key: string
  label: string
  unit: string
  video: number | null
  twin: number | null
  delta: number | null
}

export interface SegmentSourcePair {
  segment_id: string
  ts: string
  is_simulated: true
  /** 同一路段、同一指标口径、同一字段的 video / twin 两条记录(TC-19) */
  slots: SegmentSourceSlot[]
  deltas: SegmentSourceDelta[]
}

// ---------- 路网拓扑(地图几何 + 断面 + 落客点 + 场区) ----------

export type SectionRole = 'boundary' | 'internal'

export interface NetworkSection {
  point_id: string
  segment_id: string
  name: string
  /** 边界断面允许回灌孪生;内部断面禁止(assimilating=false, reason=internal_not_allowed) */
  role: SectionRole
  /** 断面在路段内的相对位置 0~1(仅用于落点,不代表实测里程) */
  offset: number
}

export interface NetworkLandmark {
  id: string
  name: string
  lon: number
  lat: number
  /** 站点块副标(站点包声明;缺省不画,免得别站被写上别的站的英文名) */
  sub?: string
}

export interface TrafficNetwork {
  ts: string
  is_simulated: true
  /** 底图来源:'demo' 示例路网 / 'osm' 真路网(OSM 需署名) */
  origin: 'demo' | 'osm'
  note: string
  attribution?: string
  segments: { segment_id: string; name: string; kind: 'main' | 'ramp'; coords: [number, number][] }[]
  sections: NetworkSection[]
  dropoffs: NetworkLandmark[]
  zones: NetworkLandmark[]
  stations: NetworkLandmark[]
}

// ---------- 告警列表(手册 §11.2 四态) ----------

/** 告警四态(手册 §:1860):待认领 / 处置中 / 已闭环 / 误报 */
export type AlertStatus = '待认领' | '处置中' | '已闭环' | '误报'

export interface TrafficAlert {
  alert_id: string
  segment_id: string
  segment_name: string
  level: CongestionLevel
  /** 指标依据(手册:triggered_by) */
  triggered_by: string[]
  /** 首次观测时间 = 该告警首次出现在快照里的快照时间(不另取浏览器时间) */
  first_seen: string
  status: AlertStatus
  /** 处置时识别的因素编号(F01~F14) */
  factor_ids?: string[]
  /** 已下发渠道(回执口径;未下发则缺省) */
  channels?: string[]
  /** 最近一次下发回执时间 */
  dispatch_at?: string
  /** 最近一次下发的分流比例(%),与回执同源;刷新后据此还原下发留痕(TC-07) */
  dispatch_ratio_pct?: number
  /** 处置回写:认领人 / 动作 / 结果四选一 / 时间 */
  writeback?: {
    operator: string
    action: string
    result: '已消除' | '已缓解' | '未改善' | '误报'
    at: string
  }
}

export interface AlertsSnapshot {
  ts: string
  is_simulated: true
  alerts: TrafficAlert[]
}

// ---------- 下发 / 回写(决策工作台) ----------

export interface DispatchInput {
  alert_id: string
  segment_id: string
  channel: string
  /** 人工可编辑的分流比例(%) */
  ratio_pct: number
}

export interface DispatchReceipt {
  alert_id: string
  channel: string
  /**
   * 本次下发的分流比例(%)。写入回执必带;由 `/alerts` 留痕还原的展示回执在
   * 后端未回该字段时缺省(缺省显示「—」,不显示 0——0 是另一个意思)。
   */
  ratio_pct?: number
  /** 回执文案(演示态:一期无真实下发通道) */
  receipt: string
  at: string
  is_simulated: true
}

export type WritebackResult = '已消除' | '已缓解' | '未改善' | '误报'

export interface WritebackInput {
  alert_id: string
  segment_id: string
  operator: string
  action: string
  result: WritebackResult
}

export interface WritebackReceipt {
  alert_id: string
  status: AlertStatus
  result: WritebackResult
  at: string
  is_simulated: true
}

// ---------- 预测(一期 L0,不报精度数字) ----------

export interface PredictPoint {
  h: 15 | 30 | 60
  ci: number
  /** 与当前 ci 的差(负数 = 预计缓解) */
  delta_ci: number
  level: CongestionLevel
  level_name: string
}

export interface PredictResponse {
  segment_id: string
  ts: string
  is_simulated: true
  model: 'L0'
  /** 只展示接口通 / L0 跑得动,严禁出现精度数字 */
  points: PredictPoint[]
}

// ---------- 判级阈值与 CI 权重(P1,只读;真实来源 stations/thresholds.json) ----------

export interface ThresholdBand {
  level: CongestionLevel
  max: number
}

/** 阈值表(避免与 demoDecision.ts 的展示用 ThresholdRow 重名) */
export interface ThresholdMetricRow {
  metric: string
  unit: string
  bands: ThresholdBand[]
}

export interface ThresholdSnapshot {
  ts: string
  is_simulated: true
  /** CI 四项加权构成权重(0~1,合计 1) */
  ci_weights: { key: string; label: string; weight: number }[]
  rows: ThresholdMetricRow[]
  changelog: { time: string; operator: string; change: string }[]
}

// ---------- 热力矩阵(路段 × 时间) ----------

export interface HeatMatrixRow {
  segment_id: string
  name: string
  /** 逐桶 CI;null = 该桶数据不可用(灰) */
  buckets: (number | null)[]
}

export interface HeatMatrix {
  ts: string
  is_simulated: true
  /** 桶粒度(秒)与窗口桶数 */
  bucket_sec: number
  buckets: number
  /** 各桶的起点时间(与 buckets 对齐) */
  labels: string[]
  rows: HeatMatrixRow[]
}

// ---------- CI 走势(单路段近 12 期) ----------

export interface CiHistoryPoint {
  ts: string
  ci: number
  level: CongestionLevel
}

export interface CiHistory {
  segment_id: string
  is_simulated: true
  points: CiHistoryPoint[]
  /** 窗口内 min / max(走势条标注用) */
  min: number
  max: number
}

// ---------- 数据同化(扩展:断面 role 与断面编号) ----------

/** 断面的同化记录(带 role,供决策页与视频页共用) */
export interface AssimilationRecordV2 extends AssimilationRecord {
  /** 断面编号(E-01 …),仅展示 */
  point_code?: string
  /** 断面名称(如「东进站路·边界」),仅展示;路段名另由 segment_id 查 */
  name?: string
  role: SectionRole
  /** reason 短码,视频页展示用(如 internal_not_allowed) */
  reason?: string | null
  /** 置信度(演示值,门控展示用) */
  confidence?: number
}

export interface AssimilationSnapshotFull extends AssimilationSnapshot {
  /** 边界断面 / 内部断面计数(页头展示「边界 3 / 内部 1」) */
  counts: { boundary: number; internal: number }
  records: AssimilationRecordV2[]
}
