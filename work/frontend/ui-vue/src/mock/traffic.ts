// traffic 大屏 mock(仅 M1,Issue #52):端点与 SSE 事件名暂沿 work/assembly/README.md 第二节
// 的历史清单——2026-10-11 架构裁定后接口面待按前端页面重新规划,原实现基准 PR #51 骨架已收回,
// 字段名对照 docs/数据契约.md v2.0。口径铁律:
//   ① 所有数据 is_simulated=true,示例数据、非实测;
//   ② 只读快照、不算业务——数值是预置基线加抖动,不是任何模型的输出;
//   ③ SSE 只新增事件名 traffic_snapshot,不改既有事件名;
//   ④ SEG-010 恒为数据陈旧(data_age_s > 120s),用于演示灰色"数据不可用"(TC-11 展示侧)。

import type { MockReq, MockRes } from './util.ts'
import { json, readJson, rid } from './util.ts'
import { SseWriter } from './sse-writer.ts'
import {
  DEMO_NETWORK,
  demoSegment,
  isOsmNetwork,
  networkSourceLabel,
  OSM_ATTRIBUTION,
  pointAtOffset,
  segmentLengthM,
} from '../shared/demoNetwork.ts'
import { APP_TABS, DEMO_BADGE } from '../shared/nav.ts'
import { LEVEL_THRESHOLDS, THRESHOLD_CHANGELOG } from '../shared/demoDecision.ts'
import {
  TRAFFIC_SNAPSHOT_EVENT,
  type AlertsSnapshot,
  type AssimilationRecordV2,
  type AssimilationSnapshotFull,
  type CiHistory,
  type CongestionLevel,
  type DispatchInput,
  type DispatchReceipt,
  type HeatMatrix,
  type ManualFactorInput,
  type ManualFactorResult,
  type PredictResponse,
  type RecommendResult,
  type SegmentRecord,
  type SegmentSourceDelta,
  type SegmentSourcePair,
  type SegmentsSnapshot,
  type ThresholdSnapshot,
  type TrafficAlert,
  type TrafficMeta,
  type TrafficNetwork,
  type TrafficOverview,
  type TrafficSnapshotPing,
  type VehicleRecord,
  type VehiclesSnapshot,
  type WritebackInput,
  type WritebackReceipt,
} from '../shared/traffic.ts'

// ---------- 预置基线(契约 v2.0 形状;x = q_vph / c_vph) ----------

interface SegmentBase {
  base: Omit<SegmentRecord, 'is_simulated'>
  /** 陈旧路段每轮继续累加数据年龄;正常路段限制在窗口内 */
  stale: boolean
}

const SEGMENT_BASES: SegmentBase[] = [
  {
    stale: false,
    base: {
      segment_id: 'SEG-001',
      source: 'video',
      q_vph: 820,
      v_kmh: 22.5,
      v_f_kmh: 40,
      k_vpk: 36.4,
      L_q_m: 90,
      L_seg_m: 520,
      T_d_min: 3.2,
      x: 0.55,
      c_base_vph: 1500,
      c_vph: 1500,
      factors_applied: [],
      ci: 38.2,
      level: 2,
      level_name: '缓行',
      triggered_by: ['v'],
      confidence: 0.88,
      data_age_s: 6,
      pred: { h15: { q_vph: 860, level: 2 }, h30: { q_vph: 780, level: 2 }, model: 'L0' },
    },
  },
  {
    stale: false,
    base: {
      segment_id: 'SEG-002',
      source: 'twin',
      q_vph: 430,
      v_kmh: 35.1,
      v_f_kmh: 40,
      k_vpk: 12.3,
      L_q_m: 0,
      L_seg_m: 640,
      T_d_min: 0,
      x: 0.27,
      c_base_vph: 1600,
      c_vph: 1600,
      factors_applied: [],
      ci: 12.5,
      level: 1,
      level_name: '畅通',
      triggered_by: [],
      confidence: 0.92,
      data_age_s: 4,
    },
  },
  {
    stale: false,
    base: {
      segment_id: 'SEG-003',
      source: 'video',
      q_vph: 610,
      v_kmh: 6.8,
      v_f_kmh: 35,
      k_vpk: 89.7,
      L_q_m: 350,
      L_seg_m: 380,
      T_d_min: 9.6,
      x: 0.94,
      c_base_vph: 1288,
      c_vph: 647, // 1288 × 0.75 × 0.67(F01 大雨 + F06 违停占道)
      factors_applied: [
        {
          factor_id: 'F01',
          name: '大雨',
          target: 'c',
          multiplier: 0.75,
          until: '2026-10-11T23:30:00+08:00',
        },
        {
          factor_id: 'F06',
          name: '路边违停占道',
          target: 'lanes',
          multiplier: 0.67,
          until: '2026-10-11T23:10:00+08:00',
        },
      ],
      ci: 82.4,
      level: 4,
      level_name: '严重拥堵',
      triggered_by: ['x', 'L_q'],
      confidence: 0.81,
      data_age_s: 8,
      pred: { h15: { q_vph: 640, level: 4 }, h30: { q_vph: 520, level: 3 }, model: 'L0' },
    },
  },
  {
    stale: false,
    base: {
      segment_id: 'SEG-004',
      source: 'twin',
      q_vph: 690,
      v_kmh: 21.0,
      v_f_kmh: 40,
      k_vpk: 32.9,
      L_q_m: 70,
      L_seg_m: 700,
      T_d_min: 2.4,
      x: 0.43,
      c_base_vph: 1600,
      c_vph: 1600,
      factors_applied: [],
      ci: 34.1,
      level: 2,
      level_name: '缓行',
      triggered_by: ['v'],
      confidence: 0.9,
      data_age_s: 5,
    },
  },
  {
    stale: false,
    base: {
      segment_id: 'SEG-005',
      source: 'twin',
      q_vph: 320,
      v_kmh: 38.2,
      v_f_kmh: 45,
      k_vpk: 8.4,
      L_q_m: 0,
      L_seg_m: 610,
      T_d_min: 0,
      x: 0.23,
      c_base_vph: 1400,
      c_vph: 1400,
      factors_applied: [],
      ci: 9.8,
      level: 1,
      level_name: '畅通',
      triggered_by: [],
      confidence: 0.93,
      data_age_s: 7,
    },
  },
  {
    stale: false,
    base: {
      segment_id: 'SEG-006',
      source: 'twin',
      q_vph: 260,
      v_kmh: 41.5,
      v_f_kmh: 45,
      k_vpk: 6.3,
      L_q_m: 0,
      L_seg_m: 480,
      T_d_min: 0,
      x: 0.22,
      c_base_vph: 1200,
      c_vph: 1200,
      factors_applied: [],
      ci: 8.1,
      level: 1,
      level_name: '畅通',
      triggered_by: [],
      confidence: 0.91,
      data_age_s: 9,
    },
  },
  {
    stale: false,
    base: {
      segment_id: 'SEG-007',
      source: 'video',
      q_vph: 540,
      v_kmh: 12.4,
      v_f_kmh: 35,
      k_vpk: 43.5,
      L_q_m: 180,
      L_seg_m: 560,
      T_d_min: 6.1,
      x: 0.65,
      c_base_vph: 1100,
      c_vph: 825, // 1100 × 0.75(F01 大雨)
      factors_applied: [
        {
          factor_id: 'F01',
          name: '大雨',
          target: 'c',
          multiplier: 0.75,
          until: '2026-10-11T23:30:00+08:00',
        },
      ],
      ci: 58.7,
      level: 3,
      level_name: '拥堵',
      triggered_by: ['v'],
      confidence: 0.84,
      data_age_s: 11,
      pred: { h15: { q_vph: 590, level: 3 }, h30: { q_vph: 430, level: 2 }, model: 'L0' },
    },
  },
  {
    stale: false,
    base: {
      segment_id: 'SEG-008',
      source: 'twin',
      q_vph: 470,
      v_kmh: 9.5,
      v_f_kmh: 35,
      k_vpk: 49.5,
      L_q_m: 210,
      L_seg_m: 420,
      T_d_min: 7.0,
      x: 0.52,
      c_base_vph: 900,
      c_vph: 900, // F11 打的是 demand,不动 c
      factors_applied: [
        {
          factor_id: 'F11',
          name: '大型活动散场',
          target: 'demand',
          multiplier: 1.25,
          until: '2026-10-11T23:55:00+08:00',
        },
      ],
      ci: 61.3,
      level: 3,
      level_name: '拥堵',
      triggered_by: ['v'],
      confidence: 0.87,
      data_age_s: 6,
    },
  },
  {
    stale: false,
    base: {
      segment_id: 'SEG-009',
      source: 'video',
      q_vph: 760,
      v_kmh: 18.6,
      v_f_kmh: 35,
      k_vpk: 40.9,
      L_q_m: 110,
      L_seg_m: 450,
      T_d_min: 3.8,
      x: 0.58,
      c_base_vph: 1300,
      c_vph: 1300,
      factors_applied: [],
      ci: 41.6,
      level: 2,
      level_name: '缓行',
      triggered_by: ['v'],
      confidence: 0.79,
      data_age_s: 13,
    },
  },
  {
    stale: true, // 演示灰色"数据不可用":>120s 只展示、不推荐(TC-11 展示侧)
    base: {
      segment_id: 'SEG-010',
      source: 'video',
      q_vph: 410,
      v_kmh: 24.0,
      v_f_kmh: 40,
      k_vpk: 17.1,
      L_q_m: 0,
      L_seg_m: 520,
      T_d_min: 0,
      x: 0.33,
      c_base_vph: 1250,
      c_vph: 1250,
      factors_applied: [],
      ci: 26.0,
      level: 2,
      level_name: '缓行',
      triggered_by: ['v'],
      confidence: 0.31,
      data_age_s: 186,
    },
  },
]

// ---------- 孪生车辆(仅一期演示,二期 vehicles 端点下线) ----------

interface VehicleBase {
  vehicle_id: string
  driver_type: VehicleRecord['driver_type']
  segment_id: string
  offset_m: number
  speed_mps: number
  state: VehicleRecord['state']
  guided: boolean
  is_demo_bound?: boolean
}

const VEHICLE_BASES: VehicleBase[] = [
  { vehicle_id: 'twin-0001', driver_type: 'D1', segment_id: 'SEG-001', offset_m: 60, speed_mps: 7.5, state: '行驶', guided: true, is_demo_bound: true },
  { vehicle_id: 'twin-0002', driver_type: 'D1', segment_id: 'SEG-002', offset_m: 120, speed_mps: 9.8, state: '行驶', guided: true },
  { vehicle_id: 'twin-0003', driver_type: 'D1', segment_id: 'SEG-003', offset_m: 40, speed_mps: 1.2, state: '落客服务', guided: true },
  { vehicle_id: 'twin-0004', driver_type: 'D2', segment_id: 'SEG-003', offset_m: 210, speed_mps: 0.8, state: '排队', guided: false },
  { vehicle_id: 'twin-0005', driver_type: 'D1', segment_id: 'SEG-004', offset_m: 300, speed_mps: 6.4, state: '行驶', guided: true },
  { vehicle_id: 'twin-0006', driver_type: 'D2', segment_id: 'SEG-005', offset_m: 150, speed_mps: 10.6, state: '行驶', guided: false },
  { vehicle_id: 'twin-0007', driver_type: 'D2', segment_id: 'SEG-005', offset_m: 380, speed_mps: 9.9, state: '行驶', guided: true },
  { vehicle_id: 'twin-0008', driver_type: 'D1', segment_id: 'SEG-007', offset_m: 90, speed_mps: 3.4, state: '行驶', guided: false },
  { vehicle_id: 'twin-0009', driver_type: 'D2', segment_id: 'SEG-008', offset_m: 60, speed_mps: 1.6, state: '排队', guided: false },
  { vehicle_id: 'twin-0010', driver_type: 'D1', segment_id: 'SEG-009', offset_m: 200, speed_mps: 5.2, state: '行驶', guided: true },
  { vehicle_id: 'twin-0011', driver_type: 'D2', segment_id: 'SEG-002', offset_m: 420, speed_mps: 8.8, state: '行驶', guided: false },
  { vehicle_id: 'twin-0012', driver_type: 'D1', segment_id: 'SEG-006', offset_m: 110, speed_mps: 11.2, state: '行驶', guided: false },
]

// ---------- 人工置位因素(管理端口子,手册第 19 章 F07/F08/F11;mock 内存态,Issue #59) ----------
// 置位后对目标路段生效:target=demand 乘 q,c/lanes 乘 c,再按演示阈值重算 level(演示行为,
// 非判级模型输出);reset 端点清空,供反复演示。

interface ManualFactor {
  segment_id: string
  factor_id: string
  name: string
  target: 'c' | 'demand' | 'lanes'
  multiplier: number
  until: string
}

const manualFactors: ManualFactor[] = []

const LEVEL_NAME: Record<number, string> = { 1: '畅通', 2: '缓行', 3: '拥堵', 4: '严重拥堵' }

function applyManualFactors(base: Omit<SegmentRecord, 'is_simulated'>): Omit<SegmentRecord, 'is_simulated'> {
  const mine = manualFactors.filter((f) => f.segment_id === base.segment_id)
  if (mine.length === 0) return base
  let q = base.q_vph ?? 0
  let c = base.c_vph ?? 0
  for (const f of mine) {
    if (f.target === 'demand') q *= f.multiplier
    else c *= f.multiplier // c / lanes 都折算通行能力
  }
  const x2 = q / Math.max(1, c)
  const xLevel: CongestionLevel = x2 >= 0.9 ? 4 : x2 >= 0.7 ? 3 : x2 >= 0.5 ? 2 : 1
  const level = Math.max(base.level, xLevel) as CongestionLevel
  const baseTrig = base.triggered_by ?? []
  const triggered = xLevel > base.level && !baseTrig.includes('x') ? [...baseTrig, 'x'] : baseTrig
  const scale = base.x && base.x > 0 ? x2 / base.x : 1
  return {
    ...base,
    q_vph: Math.round(q),
    c_vph: Math.round(c),
    x: round(x2, 2),
    ci: round(Math.min(100, (base.ci ?? 0) * scale), 1),
    level,
    level_name: LEVEL_NAME[level],
    triggered_by: triggered,
    factors_applied: [
      ...(base.factors_applied ?? []),
      ...mine.map((f) => ({ factor_id: f.factor_id, name: f.name, target: f.target, multiplier: f.multiplier, until: f.until })),
    ],
  }
}

// 数据同化的完整实现见下方 buildAssimilationFull()(带断面 role / 编号 / 计数)。

// ---------- 快照构造(tick 驱动抖动;数值是演示基线,不是模型输出) ----------

let tick = 0

function jitter(value: number, pct: number): number {
  return value * (1 + (Math.random() * 2 - 1) * pct)
}

function round(value: number, digits: number): number {
  const f = 10 ** digits
  return Math.round(value * f) / f
}

// 本地时区 ISO8601(契约示例带 +08:00 偏移,不用 UTC 的 Z)
function localIso(d: Date): string {
  const off = -d.getTimezoneOffset()
  const sign = off >= 0 ? '+' : '-'
  const pad = (n: number): string => String(Math.abs(n)).padStart(2, '0')
  const t = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  const date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  return `${date}T${t}${sign}${pad(Math.floor(Math.abs(off) / 60))}:${pad(Math.abs(off) % 60)}`
}

function buildSegmentsSnapshot(): SegmentsSnapshot {
  tick += 1
  const segments: SegmentRecord[] = SEGMENT_BASES.map(({ base, stale }) => {
    const src = applyManualFactors(base) // 人工置位先生效,再走抖动
    const q_vph = Math.round(jitter(src.q_vph ?? 0, 0.04))
    const v_kmh = round(jitter(src.v_kmh ?? 0, 0.03), 1)
    const c_vph = src.c_vph ?? 0
    const ageBase = src.data_age_s ?? 0
    return {
      ...src,
      q_vph,
      v_kmh,
      k_vpk: round(jitter(src.k_vpk ?? 0, 0.03), 1),
      L_q_m: Math.round(jitter(src.L_q_m ?? 0, 0.06)),
      x: round(q_vph / Math.max(1, c_vph), 2),
      ci: round(jitter(src.ci ?? 0, 0.02), 1),
      data_age_s: stale ? ageBase + (tick % 30) * 2 : Math.min(ageBase + (tick % 6) * 2, 110),
      is_simulated: true,
    }
  })
  return { ts: localIso(new Date()), window_sec: 900, is_simulated: true, segments }
}

function buildVehiclesSnapshot(): VehiclesSnapshot {
  const vehicles: VehicleRecord[] = []
  for (const v of VEHICLE_BASES) {
    const seg = demoSegment(v.segment_id)
    if (!seg) continue // 示例路网缺该路段(换路网时 id 未对齐)就不画这辆车
    const len = segmentLengthM(seg.coords)
    // 2 秒一帧:按各自速度前进,到段尾回卷(演示观感,非仿真输出)
    const offset = (v.offset_m + v.speed_mps * 2 * tick) % Math.max(50, len)
    const [lon, lat] = pointAtOffset(seg.coords, offset)
    vehicles.push({
      vehicle_id: v.vehicle_id,
      driver_type: v.driver_type,
      segment_id: v.segment_id,
      offset_m: Math.round(offset),
      lon: round(lon, 6),
      lat: round(lat, 6),
      state: v.state,
      guided: v.guided,
      is_demo_bound: v.is_demo_bound === true,
    })
  }
  return { ts: localIso(new Date()), is_simulated: true, vehicles }
}

// ---------- 孪生车辆真值接入(#61 twin_preview) ----------
// 桥接服务(work/frontend/tools/twin_preview/server.py,:8102)在跑时,vehicles 优先用
// SUMO TraCI 真值;不可用回落上方合成车基线。缓存 5 s + 在飞去重,2 s 轮询不会打满桥接。

const TWIN_BRIDGE = process.env.VITE_TWIN_API_BASE || 'http://127.0.0.1:8102'
const VEHICLE_STATES: readonly VehicleRecord['state'][] = ['行驶', '排队', '落客服务', '候客', '违停', '已离开']

let twinCache: { at: number; vehicles: VehicleRecord[] } | null = null
let twinInflight: Promise<VehicleRecord[] | null> | null = null

function toVehicleRecords(raw: unknown): VehicleRecord[] | null {
  if (!raw || typeof raw !== 'object') return null
  const env = raw as { is_simulated?: unknown; vehicles?: unknown }
  if (env.is_simulated !== true || !Array.isArray(env.vehicles)) return null
  const out: VehicleRecord[] = []
  for (const item of env.vehicles) {
    if (!item || typeof item !== 'object') return null
    const v = item as Record<string, unknown>
    if (
      typeof v.vehicle_id !== 'string' ||
      typeof v.segment_id !== 'string' ||
      typeof v.offset_m !== 'number' ||
      typeof v.lon !== 'number' ||
      typeof v.lat !== 'number' ||
      !VEHICLE_STATES.includes(v.state as VehicleRecord['state'])
    ) {
      return null // 形状不对整包拒绝,宁可用合成车也不画脏数据
    }
    out.push({
      vehicle_id: v.vehicle_id,
      driver_type: v.driver_type === 'D2' ? 'D2' : 'D1',
      segment_id: v.segment_id,
      offset_m: Math.round(v.offset_m),
      lon: v.lon,
      lat: v.lat,
      state: v.state as VehicleRecord['state'],
      guided: v.guided === true,
      is_demo_bound: v.is_demo_bound === true,
    })
  }
  return out
}

async function fetchTwinVehicles(): Promise<VehicleRecord[] | null> {
  const now = Date.now()
  if (twinCache && now - twinCache.at < 5000) return twinCache.vehicles
  if (!twinInflight) {
    twinInflight = (async (): Promise<VehicleRecord[] | null> => {
      try {
        const res = await fetch(`${TWIN_BRIDGE}/api/twin/vehicles`, { signal: AbortSignal.timeout(700) })
        if (!res.ok) throw new Error(`twin bridge http ${res.status}`)
        const records = toVehicleRecords(await res.json())
        if (records && records.length > 0) twinCache = { at: Date.now(), vehicles: records }
        return records
      } catch {
        return null
      } finally {
        twinInflight = null
      }
    })()
  }
  return twinInflight
}

async function buildVehiclesSnapshotWithTwin(): Promise<VehiclesSnapshot> {
  const twin = await fetchTwinVehicles()
  // 桥接可达就信它的结果,包括空列表(仿真刚起步 genuinely 0 车)——
  // 此时回落合成车反而会造成"假车混进真仿真"的口径问题;只有不可达才回落
  if (twin) return { ts: localIso(new Date()), is_simulated: true, vehicles: twin }
  return buildVehiclesSnapshot()
}

// ---------- 推荐快照(静态演示:引擎写入 routes.json 后由接口层端出,这里原样假造) ----------

function buildRecommend(): RecommendResult {
  return {
    request_id: rid('REQ'),
    session_id: rid('S'),
    driver_type: 'D1',
    parking_mode: 'S1',
    location: { segment_id: 'SEG-001', offset_m: 85, match_confidence: 1.0, source: 'twin' },
    arrival_route: {
      path_id: 'P-2',
      segments: ['SEG-001', 'SEG-002', 'SEG-004'],
      eta_min: 6.4,
      dropoff_point: 'DROP-03',
      walk_min: 2.1,
    },
    departure_route: { path_id: 'P-2-D', segments: ['SEG-004', 'SEG-006'], eta_min: 5.2 },
    pickup_route: null,
    alternatives: [
      {
        path_id: 'P-1',
        eta_min: 7.8,
        reason: '经到达层通道,少 0.5 分钟步行,但到达层排队更多',
        segments: ['SEG-001', 'SEG-009', 'SEG-003'],
        dropoff_point: 'DROP-03',
        walk_min: 1.6,
      },
      {
        path_id: 'P-5',
        eta_min: 8.9,
        reason: '南进站路更空,但落客点离出站口远、步行长',
        segments: ['SEG-005', 'SEG-008'],
        dropoff_point: 'DROP-05',
        walk_min: 3.4,
      },
    ],
    reservation: {
      slots_reserved: 9,
      lease_expire_s: 90,
      harm_check: { max_eta_increase_s: 12, max_slot_x: 0.81, passed: true },
    },
    why: 'P-2 预计 6.4 分钟,比备选少 1.4 分钟;落客平台(SEG-003)严重拥堵,推荐走环道南侧落客;预约未伤及前车(最大 +12 秒)。',
    is_simulated: true,
  }
}

// =====================================================================================
// 四页重做(Issue #78)新增端点实现
// 与既有端点同口径:只读快照 / 不做业务计算(数值为演示基线 + 抖动,不是模型输出);
// 每个响应带 is_simulated=true 信封;状态类端点(下发 / 回写)在 mock 内存态里流转,
// 供演示反复操作(刷新复位),后端实现时须落库并留痕。
// =====================================================================================

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v))
}

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

/** 'HH:mm:ss' */
function clockOf(d: Date): string {
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`
}

/** 'YYYY-MM-DD HH:mm:ss'(首次观测时间等留痕字段用) */
function stampOf(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${clockOf(d)}`
}

function nameOfSegment(id: string): string {
  return demoSegment(id)?.name ?? id
}

/** 演示基线与抖动共用的陈旧判据(与 shared/traffic.ts 的 STALE_AFTER_S = 120 对齐) */
function isStaleRec(seg: SegmentRecord): boolean {
  return (seg.data_age_s ?? 0) > 120
}

// ---------- 站点 / 数据源元信息 ----------

function buildMeta(): TrafficMeta {
  return {
    ts: localIso(new Date()),
    is_simulated: true,
    station: { station_id: 'ZQD', name: '肇庆东站', subtitle: '高铁站外交通' },
    sources: [
      { key: 'video', name: '视频链路' },
      { key: 'twin', name: '孪生链路' },
    ],
    demo_badge: DEMO_BADGE,
    tabs: APP_TABS.map((t) => ({ key: t.key, name: t.name, route: t.route })),
  }
}

// ---------- 全网 KPI(态势总览) ----------

const LEVEL_ORDER: CongestionLevel[] = [1, 2, 3, 4]
let prevAvgSpeed: number | null = null

function buildOverview(): TrafficOverview {
  const snap = buildSegmentsSnapshot()
  const segments = snap.segments
  const usable = segments.filter((s) => !isStaleRec(s))

  // 全网均速 = 按流量加权的平均车速(窗口均值口径;陈旧路段不参与,避免把"没数据"算成"很畅通")
  const qSum = usable.reduce((acc, s) => acc + (s.q_vph ?? 0), 0)
  const avg = qSum > 0 ? usable.reduce((acc, s) => acc + (s.v_kmh ?? 0) * (s.q_vph ?? 0), 0) / qSum : 0
  const avgRounded = round(avg, 1)
  const delta = prevAvgSpeed === null ? 0 : round(avgRounded - prevAvgSpeed, 1)
  prevAvgSpeed = avgRounded

  // 最堵路段:先按 level 取最高档,同档取 x(饱和度)大者
  const worst = [...segments].sort((a, b) => b.level - a.level || (b.x ?? 0) - (a.x ?? 0))[0] ?? null

  // 站前在途车辆与采纳率:演示基线(车速/流量同源抖动口径,不是仿真输出)
  const vehiclesInbound = 128 + (tick % 7) - 3
  const guidedRate = 0.742
  const guided = Math.round(vehiclesInbound * guidedRate)

  const levelDist: TrafficOverview['level_distribution'] = [
    ...LEVEL_ORDER.map((lv) => ({
      level: lv as CongestionLevel | 0,
      name: LEVEL_NAME[lv] ?? String(lv),
      count: segments.filter((s) => !isStaleRec(s) && s.level === lv).length,
    })),
    { level: 0 as CongestionLevel | 0, name: '不可用', count: segments.filter((s) => isStaleRec(s)).length },
  ]

  return {
    ts: snap.ts,
    is_simulated: true,
    window_sec: snap.window_sec,
    avg_speed_kmh: avgRounded,
    avg_speed_delta_kmh: delta,
    worst_segment: worst
      ? { segment_id: worst.segment_id, name: nameOfSegment(worst.segment_id), level: worst.level, x: worst.x ?? 0 }
      : null,
    vehicles_inbound: vehiclesInbound,
    vehicles_guided: guided,
    guided_rate: round(guided / Math.max(1, vehiclesInbound), 4),
    active_factors: segments.flatMap((s) => s.factors_applied ?? []).length,
    level_distribution: levelDist,
    segment_total: segments.length,
    unavailable_count: segments.filter((s) => isStaleRec(s)).length,
  }
}

// ---------- 路网拓扑(地图几何 + 断面 + 落客点 + 场区) ----------

interface SectionBase {
  point_id: string
  segment_id: string
  name: string
  role: 'boundary' | 'internal'
  offset: number
}

// 断面目录:边界断面允许回灌孪生,内部断面恒为 not allowed(手册门控口径)。
// 编号沿用设计稿的 E-xx 展示编号(非契约字段);boundary 3 / internal 1,与设计稿页头计数一致。
const SECTION_BASES: SectionBase[] = [
  { point_id: 'E-01', segment_id: 'SEG-002', name: '东进站路·边界', role: 'boundary', offset: 0.5 },
  { point_id: 'E-04', segment_id: 'SEG-007', name: '西进站路·边界', role: 'boundary', offset: 0.5 },
  { point_id: 'E-07', segment_id: 'SEG-005', name: '南进站路·边界', role: 'boundary', offset: 0.5 },
  { point_id: 'E-09', segment_id: 'SEG-001', name: '站前路·内部', role: 'internal', offset: 0.5 },
]

function pointOnSegment(segmentId: string, t: number): [number, number] {
  const seg = demoSegment(segmentId)
  if (!seg) return [112.4309, 23.0626]
  return pointAtOffset(seg.coords, segmentLengthM(seg.coords) * t)
}

function buildNetwork(): TrafficNetwork {
  const osm = isOsmNetwork()
  const dropoff = pointOnSegment('SEG-003', 0.85)
  const zoneWait = pointOnSegment('SEG-008', 0.6)
  const zonePark = pointOnSegment('SEG-007', 0.7)
  const station = pointOnSegment('SEG-004', 0.5)
  return {
    ts: localIso(new Date()),
    is_simulated: true,
    origin: osm ? 'osm' : 'demo',
    note: networkSourceLabel(),
    // OSM 署名是展示义务(条款核实 §2.1):真路网时必须带出,示例路网不带
    attribution: osm ? OSM_ATTRIBUTION : undefined,
    segments: DEMO_NETWORK.segments.map((s) => ({
      segment_id: s.segment_id,
      name: s.name,
      kind: s.kind,
      coords: s.coords,
    })),
    sections: SECTION_BASES.map((s) => ({ ...s })),
    dropoffs: [{ id: 'DROP-03', name: '落客点 DROP-03', lon: dropoff[0], lat: dropoff[1] }],
    zones: [
      { id: 'Z-01', name: '车辆候客区', lon: zoneWait[0], lat: zoneWait[1] },
      { id: 'Z-02', name: '社会停车场', lon: zonePark[0], lat: zonePark[1] },
    ],
    stations: [{ id: 'ZQD', name: '肇庆东站', lon: station[0], lat: station[1] }],
  }
}

// ---------- 同一路段双数据源并排(TC-19) ----------

/** 一期有视频链路覆盖的路段(预置基线里 source=video 的路段 + 视频感知页台账映射的路段) */
// SEG-004 追加理由:视频感知页的通道台账把样本视频 C-05 track1 映射到 SEG-004(设计稿数据线索
// 「C-05 track1 = SEG-004 落客通道」),该路段的指标确实由视频链路产出,故并排时 video 槽位必须可用。
const VIDEO_COVERED = new Set(['SEG-001', 'SEG-003', 'SEG-004', 'SEG-007', 'SEG-009', 'SEG-010'])

/** 由孪生记录派生视频记录:视频侧偏差略大(演示差值:饱和度 +0.07 / 车速 −2.6 / 排队 +42 / 消散 +0.6) */
function deriveVideoFromTwin(base: SegmentRecord): SegmentRecord {
  return {
    ...base,
    source: 'video',
    q_vph: Math.round((base.q_vph ?? 0) * 1.09),
    c_vph: base.c_vph,
    x: round(Math.min(1.4, (base.x ?? 0) * 1.083), 2),
    v_kmh: round(Math.max(0, (base.v_kmh ?? 0) - 2.6), 1),
    k_vpk: round((base.k_vpk ?? 0) * 1.06, 1),
    L_q_m: Math.round((base.L_q_m ?? 0) + 42),
    T_d_min: round((base.T_d_min ?? 0) + 0.6, 1),
    ci: round(clamp((base.ci ?? 0) * 1.05 + 2, 0, 100), 1),
    confidence: round(clamp((base.confidence ?? 0.8) - 0.04, 0, 1), 2),
  }
}

/** 由视频记录派生孪生记录(视频侧已更差时的反向派生) */
function deriveTwinFromVideo(base: SegmentRecord): SegmentRecord {
  return {
    ...base,
    source: 'twin',
    q_vph: Math.round((base.q_vph ?? 0) / 1.09),
    x: round(Math.max(0, (base.x ?? 0) / 1.083), 2),
    v_kmh: round((base.v_kmh ?? 0) + 2.6, 1),
    L_q_m: Math.max(0, Math.round((base.L_q_m ?? 0) - 42)),
    T_d_min: round(Math.max(0, (base.T_d_min ?? 0) - 0.6), 1),
    ci: round(clamp(((base.ci ?? 0) - 2) / 1.05, 0, 100), 1),
    confidence: round(clamp((base.confidence ?? 0.8) + 0.04, 0, 1), 2),
  }
}

function buildSegmentSources(segmentId: string): SegmentSourcePair | null {
  const snap = buildSegmentsSnapshot()
  const base = snap.segments.find((s) => s.segment_id === segmentId)
  if (!base) return null
  // 哪一侧是"实测基线":预置基线的 source 字段即该路段的真实来源
  const twinIsBase = base.source === 'twin'
  const twin = twinIsBase ? base : deriveTwinFromVideo(base)
  let video: SegmentRecord | null = null
  if (VIDEO_COVERED.has(segmentId)) video = twinIsBase ? deriveVideoFromTwin(base) : base

  const pick = (r: SegmentRecord | null, k: keyof SegmentRecord): number | null =>
    r && typeof r[k] === 'number' ? (r[k] as number) : null
  const rows: [string, string, string, keyof SegmentRecord][] = [
    ['x', '饱和度 x', '', 'x'],
    ['v_kmh', '车速 km/h', 'km/h', 'v_kmh'],
    ['L_q_m', '排队长度 m', 'm', 'L_q_m'],
    ['T_d_min', '排队消散 min', 'min', 'T_d_min'],
    ['ci', '拥挤指数 CI', '', 'ci'],
  ]
  const deltas: SegmentSourceDelta[] = rows.map(([key, label, unit, field]) => {
    const v = pick(video, field)
    const t = pick(twin, field)
    return { key, label, unit, video: v, twin: t, delta: v !== null && t !== null ? round(v - t, 2) : null }
  })

  return {
    segment_id: segmentId,
    ts: snap.ts,
    is_simulated: true,
    slots: [
      { source: 'video', record: video, available: video !== null },
      { source: 'twin', record: twin, available: true },
    ],
    deltas,
  }
}

// ---------- 告警(四态,内存态流转) ----------

interface AlertBase {
  alert_id: string
  segment_id: string
  level: CongestionLevel
  triggered_by: string[]
  factor_ids?: string[]
  /** 首次观测 = 快照时间往前推 ago_min 分钟(不另取浏览器时间) */
  ago_min: number
  status: TrafficAlert['status']
}

// 预置告警(沿用设计稿的告警编号与路段线索):待认领 2 / 处置中 1 / 已闭环 3 / 误报 1,
// 与 page2「关联告警 2 条未闭环」、page3「待认领 7 条·未闭环 3」的口径自洽:未闭环 = 待认领 + 处置中。
const ALERT_BASES: AlertBase[] = [
  { alert_id: 'A-2412-018', segment_id: 'SEG-004', level: 3, triggered_by: ['x', 'L_q'], ago_min: 3, status: '待认领' },
  { alert_id: 'A-2412-021', segment_id: 'SEG-007', level: 2, triggered_by: ['v'], ago_min: 5, status: '待认领' },
  {
    alert_id: 'A-2412-015',
    segment_id: 'SEG-003',
    level: 3,
    triggered_by: ['x'],
    factor_ids: ['F01', 'F06'],
    ago_min: 9,
    status: '处置中',
  },
  { alert_id: 'A-2410-306', segment_id: 'SEG-002', level: 3, triggered_by: ['v'], ago_min: 38, status: '已闭环' },
  { alert_id: 'A-2410-308', segment_id: 'SEG-001', level: 3, triggered_by: ['x'], ago_min: 59, status: '已闭环' },
  { alert_id: 'A-2410-298', segment_id: 'SEG-005', level: 3, triggered_by: ['v'], ago_min: 78, status: '已闭环' },
  { alert_id: 'A-2410-291', segment_id: 'SEG-001', level: 2, triggered_by: ['x'], ago_min: 95, status: '误报' },
]

interface AlertRuntime {
  status?: TrafficAlert['status']
  channels?: string[]
  dispatch_at?: string
  writeback?: TrafficAlert['writeback']
}

const alertRuntime = new Map<string, AlertRuntime>()

function buildAlerts(): AlertsSnapshot {
  const now = Date.now()
  const alerts: TrafficAlert[] = ALERT_BASES.map((a) => {
    const rt = alertRuntime.get(a.alert_id) ?? {}
    return {
      alert_id: a.alert_id,
      segment_id: a.segment_id,
      segment_name: nameOfSegment(a.segment_id),
      level: a.level,
      triggered_by: a.triggered_by,
      first_seen: stampOf(new Date(now - a.ago_min * 60_000)),
      status: rt.status ?? a.status,
      factor_ids: a.factor_ids,
      channels: rt.channels,
      dispatch_at: rt.dispatch_at,
      writeback: rt.writeback,
    }
  })
  return { ts: localIso(new Date()), is_simulated: true, alerts }
}

// ---------- 预测(一期 L0,不报精度数字) ----------

/** 演示预测档:15 / 30 / 60 分钟相对当前 CI 的变化(设计稿口径 −3.4 / −11.0 / −20.8) */
const PREDICT_PROFILE: { h: 15 | 30 | 60; delta: number }[] = [
  { h: 15, delta: -3.4 },
  { h: 30, delta: -11.0 },
  { h: 60, delta: -20.8 },
]

/** CI → 演示档位(仅供 pred 的等级展示;判级一律以四项指标为准,见 CI 硬口径) */
function demoLevelFromCi(ci: number): CongestionLevel {
  if (ci >= 85) return 4
  if (ci >= 65) return 3
  if (ci >= 40) return 2
  return 1
}

function buildPredict(segmentId: string): PredictResponse | null {
  const rec = buildSegmentsSnapshot().segments.find((s) => s.segment_id === segmentId)
  if (!rec) return null
  const baseCi = rec.ci ?? 0
  const points = PREDICT_PROFILE.map(({ h, delta }) => {
    const ci = round(clamp(baseCi + delta, 0, 100), 1)
    const level = demoLevelFromCi(ci)
    return { h, ci, delta_ci: round(ci - baseCi, 1), level, level_name: LEVEL_NAME[level] ?? String(level) }
  })
  return { segment_id: segmentId, ts: localIso(new Date()), is_simulated: true, model: 'L0', points }
}

// ---------- 阈值与 CI 权重(只读演示;真实来源 stations/thresholds.json) ----------

function buildThresholds(): ThresholdSnapshot {
  return {
    ts: localIso(new Date()),
    is_simulated: true,
    // CI 四项加权构成(设计稿口径 0.40 / 0.25 / 0.25 / 0.10,合计 1)
    ci_weights: [
      { key: 'x', label: '饱和度 x', weight: 0.4 },
      { key: 'v', label: '速度比 v/v_f', weight: 0.25 },
      { key: 'k', label: '排队比 L_q', weight: 0.25 },
      { key: 'T_d', label: '消散 T_d', weight: 0.1 },
    ],
    rows: LEVEL_THRESHOLDS.map((r) => ({ metric: r.metric, unit: r.unit, bands: r.bands })),
    changelog: THRESHOLD_CHANGELOG.map((c) => ({ ...c })),
  }
}

// ---------- 热力矩阵 / CI 走势 ----------

function buildHeatMatrix(buckets: number): HeatMatrix {
  const count = Math.min(24, Math.max(4, buckets))
  const snap = buildSegmentsSnapshot()
  const now = Date.now()
  const labels = Array.from({ length: count }, (_, i) => clockOf(new Date(now - (count - 1 - i) * 60_000)))
  const rows = snap.segments.map((s) => {
    const available = !isStaleRec(s) && typeof s.ci === 'number'
    const vals: (number | null)[] = labels.map((_, i) => {
      if (!available) return null // 数据不可用 → 灰档,绝不用 0 冒充
      const wave = Math.sin((i / Math.max(1, count - 1)) * Math.PI * 1.6)
      return round(clamp((s.ci ?? 0) + wave * 14 - 8, 0, 100), 1)
    })
    return { segment_id: s.segment_id, name: nameOfSegment(s.segment_id), buckets: vals }
  })
  return { ts: snap.ts, is_simulated: true, bucket_sec: 60, buckets: count, labels, rows }
}

function buildCiHistory(segmentId: string, points: number): CiHistory | null {
  const rec = buildSegmentsSnapshot().segments.find((s) => s.segment_id === segmentId)
  if (!rec) return null
  const count = Math.min(48, Math.max(4, points))
  const base = rec.ci ?? 0
  const now = Date.now()
  const series = Array.from({ length: count }, (_, i) => {
    const t = i / Math.max(1, count - 1)
    const drift = (t - 0.5) * 10 // 近期缓慢上升的演示趋势
    const ci = round(clamp(base + drift + Math.sin(i * 0.9) * 4, 0, 100), 1)
    return { ts: clockOf(new Date(now - (count - 1 - i) * 5 * 60_000)), ci, level: demoLevelFromCi(ci) }
  })
  const values = series.map((p) => p.ci)
  return { segment_id: segmentId, is_simulated: true, points: series, min: Math.min(...values), max: Math.max(...values) }
}

// ---------- 数据同化(扩展:断面 role / 编号 / 计数) ----------

function buildAssimilationFull(): AssimilationSnapshotFull {
  const now = localIso(new Date())
  const nowStamp = stampOf(new Date())
  const det = (
    pointId: string,
    name: string,
    segmentId: string,
    role: 'boundary' | 'internal',
    enabled: boolean,
    flow: number | null,
    speed: number | null,
    confidence: number,
    gateReason: 'confidence_low' | 'data_age' | 'deviation_fuse' | null,
    gateDetail: string | null,
    reason: string | null,
  ): AssimilationRecordV2 => ({
    point_code: pointId,
    point_id: pointId,
    name,
    segment_id: segmentId,
    role,
    enabled,
    flow_dev_pct: flow,
    speed_dev_pct: speed,
    confidence,
    gate_reason: gateReason,
    gate_detail: gateDetail,
    reason,
    last_apply_at: enabled ? nowStamp : null,
  })

  const records: AssimilationRecordV2[] = [
    // 边界断面 3 条:可回灌(其中一条门控中)
    det('E-01', '东进站路·边界', 'SEG-002', 'boundary', true, 3.2, 4.1, 0.88, null, null, null),
    det(
      'E-04',
      '西进站路·边界',
      'SEG-007',
      'boundary',
      false,
      null,
      null,
      0.62,
      'confidence_low',
      '数据置信度 0.62 < 门控阈值 0.75,停止回灌并留日志',
      'confidence_low',
    ),
    det('E-07', '南进站路·边界', 'SEG-005', 'boundary', true, 1.8, 2.4, 0.91, null, null, null),
    // 内部断面 1 条:恒为 assimilating=false,reason 写死(不是"门控中",是"制度上不允许")
    det(
      'E-09',
      '站前路·内部',
      'SEG-001',
      'internal',
      false,
      null,
      null,
      0.9,
      null,
      '仅 role=boundary 断面允许回灌(手册门控口径)',
      'internal_not_allowed',
    ),
  ]

  return {
    ts: now,
    is_simulated: true,
    gate: { confidence_min: 0.6, data_age_max_s: 120 },
    counts: { boundary: records.filter((r) => r.role === 'boundary').length, internal: records.filter((r) => r.role === 'internal').length },
    records,
  }
}

// ---------- HTTP 处理(path 不含 /api 前缀,与 mock/index.ts 的 connect 挂载一致) ----------

export async function handleTraffic(path: string, method: string, req: MockReq, res: MockRes): Promise<boolean> {
  // 查询参数(Issue #78 的 ?segment_id= / ?points= / ?window= 等);path 已由调用方去尾斜杠
  const url = new URL(req.url ?? path, 'http://mock.local')
  let m = /^\/traffic\/segments$/.exec(path)
  if (m && method === 'GET') {
    json(res, 200, buildSegmentsSnapshot())
    return true
  }

  m = /^\/traffic\/segments\/([^/]+)$/.exec(path)
  if (m && method === 'GET') {
    const id = decodeURIComponent(m[1])
    const seg = buildSegmentsSnapshot().segments.find((s) => s.segment_id === id)
    if (!seg) {
      json(res, 404, { code: 'SEGMENT_NOT_FOUND', message: `路段不存在: ${id}` })
      return true
    }
    json(res, 200, seg)
    return true
  }

  if (path === '/traffic/vehicles' && method === 'GET') {
    json(res, 200, await buildVehiclesSnapshotWithTwin())
    return true
  }

  if (path === '/traffic/route/recommend' && method === 'POST') {
    await readJson(req) // 请求体形状见契约(session_id / location);mock 不校验,原样回推荐快照
    json(res, 200, buildRecommend())
    return true
  }

  // 决策工作台(Issue #59,接口面新增):同化状态 / 人工置位因素
  if (path === '/traffic/assimilation' && method === 'GET') {
    json(res, 200, buildAssimilationFull())
    return true
  }

  // 契约 L440 预留端点的 GET:当前生效因素清单(含预置演示因素与人工置位,
  // 从 segments 快照展平——POST 置位 / reset 复位后此处随动)。
  // Issue #78:支持 ?segment_id= 过滤(拥挤度热力页的"成因拆解"按路段取)。
  if (path === '/traffic/factors' && method === 'GET') {
    const only = url.searchParams.get('segment_id')
    const factors = buildSegmentsSnapshot()
      .segments.filter((s) => !only || s.segment_id === only)
      .flatMap((s) => (s.factors_applied ?? []).map((f) => ({ ...f, segment_id: s.segment_id })))
    json(res, 200, { ts: localIso(new Date()), is_simulated: true, factors })
    return true
  }

  // ---------- Issue #78 新增端点 ----------

  if (path === '/traffic/meta' && method === 'GET') {
    json(res, 200, buildMeta())
    return true
  }

  if (path === '/traffic/overview' && method === 'GET') {
    json(res, 200, buildOverview())
    return true
  }

  if (path === '/traffic/network' && method === 'GET') {
    json(res, 200, buildNetwork())
    return true
  }

  m = /^\/traffic\/segments\/([^/]+)\/sources$/.exec(path)
  if (m && method === 'GET') {
    const pair = buildSegmentSources(decodeURIComponent(m[1]))
    if (!pair) {
      json(res, 404, { code: 'SEGMENT_NOT_FOUND', message: `路段不存在: ${decodeURIComponent(m[1])}` })
      return true
    }
    json(res, 200, pair)
    return true
  }

  if (path === '/traffic/alerts' && method === 'GET') {
    json(res, 200, buildAlerts())
    return true
  }

  if (path === '/traffic/plan/dispatch' && method === 'POST') {
    const body = (await readJson(req)) as Partial<DispatchInput>
    if (!body.alert_id || !body.channel || typeof body.ratio_pct !== 'number') {
      json(res, 400, { code: 'DISPATCH_INVALID', message: '下发参数不完整(需 alert_id/channel/ratio_pct)' })
      return true
    }
    const at = stampOf(new Date())
    const rt = alertRuntime.get(body.alert_id) ?? {}
    rt.status = '处置中'
    rt.channels = [body.channel]
    rt.dispatch_at = at
    alertRuntime.set(body.alert_id, rt)
    const receipt: DispatchReceipt = {
      alert_id: body.alert_id,
      channel: body.channel,
      ratio_pct: body.ratio_pct,
      // 一期无真实下发通道:回执是演示态(页面已标「mock 侧」)
      receipt: `${body.channel}已确认`,
      at,
      is_simulated: true,
    }
    json(res, 200, receipt)
    return true
  }

  if (path === '/traffic/plan/ack' && method === 'POST') {
    const body = (await readJson(req)) as Partial<WritebackInput>
    if (!body.alert_id || !body.operator || !body.action || !body.result) {
      json(res, 400, { code: 'ACK_INVALID', message: '回写参数不完整(需 alert_id/operator/action/result)' })
      return true
    }
    // 结果 → 状态流转(手册 §11.2):已消除 / 已缓解 → 已闭环;未改善 → 留在处置中;误报 → 误报
    const status: TrafficAlert['status'] =
      body.result === '误报' ? '误报' : body.result === '未改善' ? '处置中' : '已闭环'
    const at = stampOf(new Date())
    const rt = alertRuntime.get(body.alert_id) ?? {}
    rt.status = status
    rt.writeback = { operator: body.operator, action: body.action, result: body.result, at }
    alertRuntime.set(body.alert_id, rt)
    const receipt: WritebackReceipt = {
      alert_id: body.alert_id,
      status,
      result: body.result,
      at,
      is_simulated: true,
    }
    json(res, 200, receipt)
    return true
  }

  if (path === '/traffic/predict' && method === 'GET') {
    const sid = url.searchParams.get('segment_id')
    if (!sid) {
      json(res, 400, { code: 'PREDICT_INVALID', message: '缺少 segment_id' })
      return true
    }
    const pred = buildPredict(sid)
    if (!pred) {
      json(res, 404, { code: 'SEGMENT_NOT_FOUND', message: `路段不存在: ${sid}` })
      return true
    }
    json(res, 200, pred)
    return true
  }

  if (path === '/traffic/thresholds' && method === 'GET') {
    json(res, 200, buildThresholds())
    return true
  }

  if (path === '/traffic/heat-matrix' && method === 'GET') {
    const buckets = Number(url.searchParams.get('bucket') ?? url.searchParams.get('window') ?? '12')
    json(res, 200, buildHeatMatrix(Number.isFinite(buckets) ? buckets : 12))
    return true
  }

  if (path === '/traffic/ci-history' && method === 'GET') {
    const sid = url.searchParams.get('segment_id')
    if (!sid) {
      json(res, 400, { code: 'CI_HISTORY_INVALID', message: '缺少 segment_id' })
      return true
    }
    const points = Number(url.searchParams.get('points') ?? '12')
    const hist = buildCiHistory(sid, Number.isFinite(points) ? points : 12)
    if (!hist) {
      json(res, 404, { code: 'SEGMENT_NOT_FOUND', message: `路段不存在: ${sid}` })
      return true
    }
    json(res, 200, hist)
    return true
  }

  if (path === '/traffic/factors' && method === 'POST') {
    const body = (await readJson(req)) as Partial<ManualFactorInput>
    const seg = SEGMENT_BASES.find((s) => s.base.segment_id === body.segment_id)
    if (!seg || !body.factor_id || !body.target || typeof body.multiplier !== 'number') {
      json(res, 400, { code: 'FACTOR_INVALID', message: '置位参数不完整(需 segment_id/factor_id/target/multiplier)' })
      return true
    }
    const until = new Date(Date.now() + 60 * 60 * 1000) // 演示:置位 60 分钟后自动过期
    manualFactors.push({
      segment_id: seg.base.segment_id,
      factor_id: body.factor_id,
      name: body.name ?? body.factor_id,
      target: body.target,
      multiplier: body.multiplier,
      until: localIso(until),
    })
    const seg0 = applyManualFactors(seg.base)
    const result: ManualFactorResult = {
      applied: true,
      segment_id: seg0.segment_id,
      level: seg0.level,
      level_name: seg0.level_name ?? LEVEL_NAME[seg0.level],
      factors_applied: seg0.factors_applied ?? [],
      is_simulated: true,
    }
    json(res, 200, result)
    return true
  }

  if (path === '/traffic/factors/reset' && method === 'POST') {
    manualFactors.length = 0
    json(res, 200, { reset: true, is_simulated: true })
    return true
  }

  if (path === '/traffic/stream' && method === 'GET') {
    streamSnapshots(req, res)
    return true
  }

  return false
}

// SSE 假流:每 2 秒推一次 traffic_snapshot 轻量事件,页面收到后重新拉快照(只读快照口径)。
// 清理挂 res 'close'(响应侧:连接断开或流结束都触发),配一次性护栏防止重复清理。
function streamSnapshots(req: MockReq, res: MockRes): void {
  const sse = new SseWriter(res)
  sse.open()
  const send = (): void => {
    const ping: TrafficSnapshotPing = {
      ts: localIso(new Date()),
      is_simulated: true,
      note: '示例快照刷新事件(traffic mock)',
    }
    sse.send(TRAFFIC_SNAPSHOT_EVENT, ping)
  }
  send()
  const timer = setInterval(send, 2000)
  let cleaned = false
  const cleanup = (): void => {
    if (cleaned) return
    cleaned = true
    clearInterval(timer)
    sse.close()
  }
  res.on('close', cleanup)
  req.on('error', cleanup)
}
