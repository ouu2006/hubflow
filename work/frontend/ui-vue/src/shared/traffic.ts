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

// ---------- SSE ----------

// 事件名是新增的(不改既有事件名),与 work/assembly/traffic.py 的 GET /api/traffic/stream 对齐
export const TRAFFIC_SNAPSHOT_EVENT = 'traffic_snapshot'

export interface TrafficSnapshotPing {
  ts: string
  is_simulated: true
  note?: string
}
