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
  color: string
  bars: number // 竖条数图标;与颜色、文字共同构成三重编码
}

export const LEVELS: Record<CongestionLevel, LevelStyle> = {
  1: { name: '畅通', color: '#1E6FD9', bars: 1 },
  2: { name: '缓行', color: '#F2B705', bars: 2 },
  3: { name: '拥堵', color: '#E8760C', bars: 3 },
  4: { name: '严重拥堵', color: '#C62828', bars: 4 },
}

// 非等级状态:数据陈旧(> 120 s【待标定】)显示灰色,只展示不推荐(TC-11 展示侧)
export const UNAVAILABLE: LevelStyle = { name: '数据不可用', color: '#8C8C8C', bars: 0 }

export const STALE_AFTER_S = 120

export function isStale(seg: SegmentRecord): boolean {
  return (seg.data_age_s ?? 0) > STALE_AFTER_S
}

export function levelStyle(seg: SegmentRecord): LevelStyle {
  return isStale(seg) ? UNAVAILABLE : LEVELS[seg.level]
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
// **不自造第五套颜色语义**;灰 #8C8C8C 仍只表示"数据不可用",不参与色阶。
const CI_ANCHORS: { at: number; color: string }[] = [
  { at: 12.5, color: LEVELS[1].color },
  { at: 37.5, color: LEVELS[2].color },
  { at: 62.5, color: LEVELS[3].color },
  { at: 87.5, color: LEVELS[4].color },
]

/** CI → 颜色:0~100 线性映射到四级色阶(超出范围按端点夹取) */
export function ciColor(ci: number): string {
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
