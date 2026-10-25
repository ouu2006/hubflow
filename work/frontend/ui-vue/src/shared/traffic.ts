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
  /**
   * 判级。契约类型是四级；接口层在「上游未判级」时如实返回 0（level_name=数据不可用），
   * 页面按 levelStyle()/LevelBadge 的灰档兜底处理，绝不落进通配色（TC-11）。
   */
  level: CongestionLevel | 0
  level_name?: string
  triggered_by?: string[]
  confidence?: number
  data_age_s?: number
  pred?: PredBlock
  is_simulated: true
  /** 接口层写端点（人工置位）已登记、待感知层重算的因素（不参与判级，接口层不重算） */
  factors_injected?: FactorApplied[]
  pending_recompute?: boolean
  injected_note?: string
  /** 上游未判级时接口层标注的来源（如 upstream_missing） */
  level_source?: string
}

export interface SegmentsSnapshot {
  ts: string
  window_sec: number
  is_simulated: true
  segments: SegmentRecord[]
  /** 接口层写端点内存态摘要（重启复位）：人工置位条数 / 场景注入状态 */
  injected_state?: {
    manual_factors: number
    scenario: {
      weather: string | null
      session: string | null
      demand_mult: number | null
      injected: boolean
    }
  }
  note?: string
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
  // ---- 接口层附加的来源 / 降级字段（mock 侧可缺省，页面按缺省口径显示）----
  /** 真网算路产物 engine.routes.real / 样例产物 engine.routes.sample */
  data_source?: string
  data_source_note?: string
  /** 请求的 session_id 是否真在产物里匹配上（false = 端出首条演示路线，非该车行程） */
  session_matched?: boolean
  requested_session_id?: string | null
  /** 路线段号命名空间（如 ['SZ'] / ['SEG']） */
  segment_namespaces?: string[]
  /** 路线引用、但当前路段快照里没有的段号（不并入指标、不混算） */
  segments_not_in_snapshot?: string[]
  segments_in_snapshot?: number
  /**
   * 契约 v2.4 §十.3 的例外标记：只有一条候选通过重叠度约束时，引擎输出
   * `no_alternative: true` + `no_alternative_reason`。接口层原样透传（缺省 = 未声明）。
   * **只读展示字段，不新增 / 不改契约形状**；页面据此如实提示「备选不足」。
   */
  no_alternative?: boolean
  no_alternative_reason?: string | null
  note?: string
}

/**
 * 地图路线高亮分组（Issue IKMF1W；Issue IKP5CK 扩展备选序号）。
 * - `arrival`  推荐路线：品牌蓝实线（「当前 / 已选」语义，不用等级色）
 * - `alternative` 备选路线：按 `index` 分「备选 1 / 备选 2」两色 + 不同虚线节律
 * - `departure` 离站路线：紫色实线（第三种语义色，与等级色 / 品牌蓝分开）
 *
 * ⚠️ 这是**前端展示类型**（不是后端契约字段）：`index` 只用于地图配色分组，
 * 不参与接口 / 判级 / 路线计算；不传时按「备选 1」处理（兼容旧调用）。
 */
export interface RouteHighlight {
  kind: 'arrival' | 'alternative' | 'departure'
  segments: string[]
  /** 仅 `alternative` 用：1 = 备选 1，2 = 备选 2（>2 一并按备选 2 的画法，不新增第五色） */
  index?: number
}

/**
 * 路线起点 / 终点的地图标注（Issue IKP5C6 追加；业主 2026-10-21 口径：
 * 「那些大道最外面的路段就是起点，然后停车场落客点是终点」）。
 *
 * **前端展示类型**，不是契约字段：坐标由前端按站点包路段折线 + 落客点演示点推出，
 * 只用于地图上的「起 / 终」标记与浮牌，不参与算路、不改 ETA。
 */
export interface RouteEndpointMarker {
  kind: 'start' | 'end'
  /** 浮牌标题：起点 / 终点（落客点） */
  label: string
  /** 所属路段 */
  segment_id: string
  /** 路段名（起点）或点位名（终点） */
  name: string
  lon: number
  lat: number
  /** 补充说明：外围边界断面 / 场内落客点 / 演示点等 */
  note?: string
}

// ---------- 整条路线规划选项（Issue IKNAUI；非契约辅助端点 /route/options） ----------
// 接口层只把引擎产物 requests 的 OD / session / 路径摘要端出来（ETA / 段号原样透传），
// 页面选中后用 session_id 调 POST /route/recommend 画完整路线，不在前端重算。

export interface RoutePathSummary {
  path_id: string | null
  segments: string[]
  segment_count: number
  eta_min: number | null
  length_m?: number | null
  dropoff_point?: string | null
  walk_min?: number | null
  /** 仅备选路径带：引擎给的 reason（原样） */
  reason?: string | null
}

export interface RouteOptionLocation {
  segment_id: string | null
  offset_m: number | null
  source: string | null
}

export interface RouteOption {
  od_id: string | null
  session_id: string | null
  request_id: string | null
  driver_type: string | null
  parking_mode: string | null
  location: RouteOptionLocation
  arrival_route: RoutePathSummary | null
  alternatives: RoutePathSummary[]
  departure_route: RoutePathSummary | null
  why: string | null
  is_simulated: true
}

export interface RouteOptionsSnapshot {
  ts: string
  is_simulated: true
  /** engine.routes.real（真网优先）/ engine.routes.sample（回退） */
  data_source: string
  data_source_note: string
  segment_namespaces: string[]
  count: number
  options: RouteOption[]
  note?: string
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

/** 等级色：数据陈旧 / 上游未判级(level=0) / 非法等级一律灰色「数据不可用」，绝不落进通配色(TC-11) */
export function levelStyle(seg: SegmentRecord): LevelStyle {
  const style = LEVELS[seg.level as CongestionLevel]
  return isStale(seg) || !style ? UNAVAILABLE : style
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
  /** 当前快照原值（注入前），不是注入后判级；0 = 数据不可用 */
  level: CongestionLevel | 0
  level_name: string
  factors_applied: FactorApplied[]
  is_simulated: true
  // ---- 接口层（真接口）附加字段；mock 侧可缺省 ----
  factor_id?: string
  name?: string
  target?: string
  multiplier?: number
  until?: string
  /** 接口层不重算判级：恒 false（level / level_name 只是快照原值） */
  level_recomputed?: boolean
  injected_factors?: FactorApplied[]
  note?: string
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
  /**
   * 站点元信息。`range_m` / `range_source` / `segment_count` 来自
   * `work/twin/site-ranges.json`（IKM4B4 登记表，每站一份），由接口层原样透传；
   * 缺省可缺（老包 / 老接口保持兼容），大屏只展示、不参与计算。
   */
  station: {
    station_id: string
    name: string
    subtitle: string
    range_m?: number
    range_source?: 'manual' | 'script' | 'ai-assisted'
    segment_count?: number
  }
  /** 两条链路(D1′):视频感知链路 + 孪生链路 */
  sources: { key: TrafficSource; name: string }[]
  /** 口径角标(手册要求页面常驻「演示数据(模拟)· 双数据源」) */
  demo_badge: string
  /** 路由 ↔ 页面标题(顶栏页签;当前页由前端高亮) */
  tabs: { key: string; name: string; route: string }[]
  // ---- 接口层附加：数据源角标（真接口模式用于页脚如实标来源；mock 侧可缺省）----
  data_sources?: {
    /** 路段快照实际落到的数据源层（perception.video / twin.latest / stations.baseline 等） */
    segments?: string
    /** 路线数据源（engine.routes.real / engine.routes.sample / null） */
    routes?: string | null
    routes_note?: string
    routes_fallback_layers?: string[]
    /** 写端点内存态是否在生效（人工置位 / 场景注入，重启复位） */
    write_endpoints_memory_state?: boolean
    scenario_injected?: boolean
    manual_factors?: number
  }
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

// ---------- 告警判级(唯一口径:Issue #75 第④条 / Issue IKLLXG) ----------
//
// 告警自带的 `level` 是**派生时的记录值**(站点包预置剧本),它与当前路段快照**可能不同步**——
// 同一页就会出现「左栏路段列表写严重拥堵、右栏同一条告警写拥堵」的自相矛盾。
// 口径:**四处(决策队列 / 决策工作台 / 大屏底部告警条 / 大屏右栏关联告警)一律取当前路段快照**;
// 快照里没有该路段时**退回告警记录值**,不编造(CongestionLevel 没有"未知"档)。
//
// 为什么收进 shared:这句重映射曾在 #77 页面迁移时被漏搬一处(只写在 HeatView 里、随页删除),
// 收成一个函数 + `AlertList` 的**必需** `levelOf` 回调后,漏传会被 `vue-tsc` 当场拦下。
export type SegmentLookup = (segmentId: string) => SegmentRecord | undefined

/** 按当前路段快照重算告警等级(快照缺该路段 / 上游未判级 level=0 时退回告警记录值) */
export function alertLevelOf(a: TrafficAlert, findSegment: SegmentLookup): CongestionLevel {
  const segLevel = findSegment(a.segment_id)?.level
  return typeof segLevel === 'number' && segLevel >= 1 && segLevel <= 4 ? (segLevel as CongestionLevel) : a.level
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

// ---------- 效果对比报表(/api/traffic/report/compare) ----------
// TC-09：接口层端引擎 --compare 三组对照产物（只读、不代算）；产物缺失时 rows 为空 + note（如实空壳，不编对比数字）。
export interface ReportCompareRow {
  /** 组键：no_guidance / fastest / cooperative */
  group: string
  /** 组名（引擎 group_labels 原文） */
  label: string
  attempted: number | null
  inserted: number | null
  completed: number | null
  in_transit: number | null
  not_entered: number | null
  orange_red_segment_count: number
  orange_red_segments: string[]
  total_travel_time_s: number | null
  network_total_time_s: number | null
  max_eta_increase_s: number | null
}

export interface ReportCompare {
  ts: string
  is_simulated: true
  /** 报表行（TC-09：引擎 --compare 三组对照；产物缺失时为空 + note） */
  rows: ReportCompareRow[]
  /** 时间窗与来源标注（TC-09 判定要求） */
  window?: {
    base_ts: string | null
    window_sec: number | null
    vehicle_count: number | null
    od_count: number | null
    seed: number | null
    site_id: string | null
  }
  /** 数据源层（engine.compare.real / engine.compare.sample / none） */
  source?: string
  source_note?: string
  /** TC-17 三项判定随报表一并透出（只读展示，前端不重算） */
  tc17?: { passed: boolean | null; criteria: Record<string, unknown> }
  note?: string
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

// =====================================================================================
// 三页收敛(Issue #77)新增接口面:环境上下文 + 场景注入
//
// 口径铁律(违反即不通过):
//   ① **天气 / 时段全部是编造的演示值**(拿不到真实数据),字段名与口径对齐手册第 19 章
//      因素登记表,**页面与文档都不得称实测**;每个响应带 is_simulated 信封。
//   ② **场景注入 ≠ 人工置位**:手册 §:2222 规定管理端人工置位的口子只有 F07 / F08 / F11
//      (交通事故 / 施工管制 / 大型活动);天气(F01)、昼夜(F02)、列车到发(F03)、
//      时段日历(F10)是**环境上下文**,按因素登记表的「一期来源 = T5 因素表手填 /
//      T3 列车时刻表 / 场景注入」注入,单开端点,不得写成"人工置位"。
//   ③ 注入只影响**演示基线**(mock / 站点包),不触碰契约字段(segments.json / routes.json /
//      vehicles.json 一字未动)。
// =====================================================================================

/** 天气状况(手册 F01 一期手填口径枚举) */
export type WeatherCondition = '晴' | '多云' | '小雨' | '大雨' | '大雾' | '台风'

/** 时段类型(手册 F10 时段 / 日历口径) */
export type TimeSession = '早高峰' | '平峰' | '晚高峰' | '夜间'

export interface WeatherContext {
  /**
   * 天气状况。mock 侧恒有值；**真接口模式接口层拿不到气象数据源时为 null**（如实缺数，不编造）。
   * 页面一律按「null → —」渲染，不得显示成 "null" 或空单位。
   */
  condition: WeatherCondition | null
  temp_c: number | null
  humidity_pct: number | null
  visibility_km: number | null
  precip_mm: number | null
  /** 风向 / 风力(展示口径一句话) */
  wind: string | null
}

export interface TimeContext {
  /** 当前时刻 'HH:mm:ss'(取自快照时间,不另取浏览器墙钟) */
  clock: string
  session: TimeSession
  calendar: '工作日' | '周末' | '节假日'
  /** 下一班列车到达(演示值;一期来源 = T3 列车时刻表手填) */
  next_train: string | null
}

/**
 * 环境上下文:天气 + 时间,以及由它们**按因素登记表折算出的因素**。
 *
 * 口径(与 mock 侧一致):
 *   · **默认态 = 站点包声明的那套环境**(包里基线已按它折算过),`injected = false`;
 *   · `POST /api/traffic/scenario` 改环境状态后,环境因素**重放**(不是叠加),
 *     包里烘进的环境因素先被剔除再按新状态折算,`injected = true`;
 *   · 因此 `derived_factors` **始终**是当前真实生效的那套环境因素,不是"仅供参考的建议值";
 *     页面可据 `injected` 区分「站点包默认环境」与「演示注入环境」。
 */
export interface TrafficContext {
  ts: string
  is_simulated: true
  station_id: string
  weather: WeatherContext
  time: TimeContext
  /** 当前环境折算出的因素(F01 天气 / F02 昼夜 / F03 列车到发 / F10 时段日历) */
  derived_factors: FactorApplied[]
  /** 环境是否已被场景注入改过(false = 站点包默认环境 / 无数据源) */
  injected: boolean
  /** 环境结论一句话(展示口径,如「大雨 · 晚高峰,通行能力折减 ×0.75」) */
  summary: string
  source: string
  /** 接口层附加：写端点场景注入内存态（重启复位） */
  scenario?: {
    weather: string | null
    session: string | null
    demand_mult: number | null
    injected: boolean
  }
  station_active_factors?: number
  note?: string
}

/**
 * 场景注入输入(管理端演示口子)。
 *
 * 字段语义(独立审查 Sourcery 提出,别改错):**缺省 = 不改该项**,**显式 `null` = 清除该项**
 * (天气 / 时段清回站点包声明或时钟推导,需求倍率清回"跟随所选时段")。前端把取消选中的芯片
 * 发成 `null` 而不是省略——省略会让服务端保留上一个值,页面显示"没选"却仍在生效。
 */
export interface ScenarioInput {
  weather?: WeatherCondition | null
  session?: TimeSession | null
  /** 需求倍率(1.0 = 不变;作用于 q_vph,与 F03 / F10 / F11 的 demand 口径一致) */
  demand_mult?: number | null
  /** 目标路段;缺省 = 全路网生效 */
  segment_id?: string
}

/** 场景注入结果(返回应用后的因素与受影响路段) */
export interface ScenarioResult {
  applied: true
  ts: string
  is_simulated: true
  /** 本次注入折算出的因素 */
  factors: FactorApplied[]
  /** 受影响路段(缺省全路网) */
  segment_ids: string[]
  /** 受影响路段的判级变化(注入前 → 注入后)；0 = 上游未判级（数据不可用） */
  effects: { segment_id: string; name: string; level_before: CongestionLevel | 0; level_after: CongestionLevel | 0; x_before: number; x_after: number }[]
  note: string
  // ---- 接口层（真接口）附加字段：判级不下发则 effects 如实为空，不伪造等级变化 ----
  /** 接口层不重算 level / ci：恒为 false（effects 为空） */
  recomputed?: boolean
  effects_note?: string
  scenario?: {
    weather: string | null
    session: string | null
    demand_mult: number | null
    injected: boolean
  }
}
