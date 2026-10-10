// traffic 大屏 mock(仅 M1,Issue #52):端点与 SSE 事件名依据 work/assembly/README.md 第二节
// 的端点清单;实现基准 = PR #51 分支上的 work/assembly/traffic.py(未并入 main 前以该分支为准),
// 字段名对照 docs/数据契约.md v2.0。口径铁律:
//   ① 所有数据 is_simulated=true,示例数据、非实测;
//   ② 只读快照、不算业务——数值是预置基线加抖动,不是任何模型的输出;
//   ③ SSE 只新增事件名 traffic_snapshot,不改既有事件名;
//   ④ SEG-010 恒为数据陈旧(data_age_s > 120s),用于演示灰色"数据不可用"(TC-11 展示侧)。

import type { MockReq, MockRes } from './util.ts'
import { json, readJson, rid } from './util.ts'
import { SseWriter } from './sse-writer.ts'
import { demoSegment, pointAtOffset, segmentLengthM } from '../shared/demoNetwork.ts'
import {
  TRAFFIC_SNAPSHOT_EVENT,
  type RecommendResult,
  type SegmentRecord,
  type SegmentsSnapshot,
  type TrafficSnapshotPing,
  type VehicleRecord,
  type VehiclesSnapshot,
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
      c_vph: 900, // F09 打的是 demand,不动 c
      factors_applied: [
        {
          factor_id: 'F09',
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
    const q_vph = Math.round(jitter(base.q_vph ?? 0, 0.04))
    const v_kmh = round(jitter(base.v_kmh ?? 0, 0.03), 1)
    const c_vph = base.c_vph ?? 0
    const ageBase = base.data_age_s ?? 0
    return {
      ...base,
      q_vph,
      v_kmh,
      k_vpk: round(jitter(base.k_vpk ?? 0, 0.03), 1),
      L_q_m: Math.round(jitter(base.L_q_m ?? 0, 0.06)),
      x: round(q_vph / Math.max(1, c_vph), 2),
      ci: round(jitter(base.ci ?? 0, 0.02), 1),
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

// ---------- HTTP 处理(path 不含 /api 前缀,与 mock/index.ts 的 connect 挂载一致) ----------

export async function handleTraffic(path: string, method: string, req: MockReq, res: MockRes): Promise<boolean> {
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
    json(res, 200, buildVehiclesSnapshot())
    return true
  }

  if (path === '/traffic/route/recommend' && method === 'POST') {
    await readJson(req) // 请求体形状见契约(session_id / location);mock 不校验,原样回推荐快照
    json(res, 200, buildRecommend())
    return true
  }

  if (path === '/traffic/stream' && method === 'GET') {
    streamSnapshots(req, res)
    return true
  }

  return false
}

// SSE 假流:每 2 秒推一次 traffic_snapshot 轻量事件,页面收到后重新拉快照(只读快照口径)
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
  req.on('close', () => {
    clearInterval(timer)
    sse.close()
  })
}
