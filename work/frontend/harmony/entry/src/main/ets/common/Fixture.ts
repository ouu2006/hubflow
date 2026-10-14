import { RouteRecommend, VehiclesSnapshot, TripRecord, SegmentsSnapshot, Segment } from './Contract';

/**
 * 工程内 fixture（#88 单：不写网络代码，四页只读这里）。
 * 内容逐字取自数据契约 v2.0 §二（routes 示例）与 §四（vehicles 示例）。
 * quota 按契约 §2.1 的数组口径承载（原文对象语义：P-2=12 / P-1=9 / P-5=15）。
 */
export const ROUTES_FIXTURE: RouteRecommend = {
  request_id: 'REQ-20261010-173200-0007',
  session_id: 'S-9f2c41a7',
  driver_type: 'D1',
  parking_mode: 'S2',
  location: {
    segment_id: 'SEG-002',
    offset_m: 85,
    match_confidence: 1.0,
    source: 'twin'
  },
  arrival_route: {
    path_id: 'P-2',
    segments: ['SEG-001', 'SEG-004', 'SEG-007'],
    eta_min: 6.4,
    dropoff_point: 'DROP-03',
    walk_min: 2.1
  },
  departure_route: {
    path_id: 'P-5',
    segments: ['SEG-007', 'SEG-009'],
    eta_min: 4.2
  },
  pickup_route: null,
  alternatives: [
    { path_id: 'P-1', eta_min: 7.8, reason: '多经过 1 个信号路口' },
    { path_id: 'P-3', eta_min: 8.6, reason: '需绕行掉头，但落客通道无排队' }
  ],
  reservation: {
    slots_reserved: 9,
    lease_expire_s: 90,
    harm_check: {
      max_eta_increase_s: 12,
      max_slot_x: 0.81,
      passed: true
    }
  },
  reroute: { count: 0, reason: null },
  factors_note: 'SEG-004 大雨，通行能力按 0.75 折减（F01）',
  why: '当前推荐路线比备选少 1.4 分钟，且未加重落客通道排队；后车进入不会让前车变慢（最大增加 12 秒）',
  quota: [
    { path_id: 'P-2', remaining: 12 },
    { path_id: 'P-1', remaining: 9 },
    { path_id: 'P-5', remaining: 15 }
  ],
  is_simulated: true
};

/** vehicles 快照（契约 §四 示例；twin-0456 为 is_demo_bound 演示车） */
export const VEHICLES_FIXTURE: VehiclesSnapshot = {
  ts: '2026-10-08T17:32:00+08:00',
  is_simulated: true,
  vehicles: [
    {
      vehicle_id: 'twin-0123',
      driver_type: 'D1',
      segment_id: 'SEG-004',
      offset_m: 40,
      lon: 112.4312,
      lat: 23.0621,
      state: '行驶',
      guided: true,
      is_demo_bound: false
    },
    {
      vehicle_id: 'twin-0456',
      driver_type: 'D2',
      segment_id: 'SEG-007',
      offset_m: 118,
      lon: 112.4327,
      lat: 23.0614,
      state: '候客',
      guided: true,
      is_demo_bound: true
    }
  ]
};

/** 演示车（C-3：一期只绑一辆 is_demo_bound=true 的车） */
export const DEMO_VEHICLE_ID: string = 'twin-0456';

/** 我的行程：本地会话记录（如实标注「未采纳推荐」） */
export const TRIPS_FIXTURE: TripRecord[] = [
  {
    session_id: 'S-9f2c41a7',
    time_label: '本次会话',
    path_id: 'P-2',
    adopted: true,
    note: '已采纳推荐路线'
  },
  {
    session_id: 'S-71bd03e2',
    time_label: '上一次会话（演示记录）',
    path_id: 'P-1',
    adopted: false,
    note: '未采纳推荐：司机自行选择原路线'
  }
];

/** 告知文案（手册 §11.1(3)，必现） */
export const DISCLAIMER_TEXT: string = '该建议基于当前路况，可能随流量变化';

/** 数据来源角标（M1-7，每页必现） */
export const SIM_BADGE_TEXT: string = '演示数据（模拟）· 双数据源（视频链路 + 孪生链路）';

/**
 * 路段等级快照（契约 §一 形状，#88 单只用它显示路段等级）。
 * 取值全部为演示数据；`source` 一期两条链路并存（视频链路 + 孪生链路）。
 */
export const SEGMENTS_FIXTURE: SegmentsSnapshot = {
  ts: '2026-10-10T17:32:00+08:00',
  is_simulated: true,
  segments: [
    { segment_id: 'SEG-001', source: 'video', level: 1, level_name: '畅通', is_simulated: true },
    { segment_id: 'SEG-002', source: 'twin', level: 2, level_name: '缓行', is_simulated: true },
    { segment_id: 'SEG-004', source: 'video', level: 3, level_name: '拥堵', is_simulated: true },
    { segment_id: 'SEG-007', source: 'twin', level: 1, level_name: '畅通', is_simulated: true },
    { segment_id: 'SEG-009', source: 'video', level: 2, level_name: '缓行', is_simulated: true }
  ]
};

/** 取路段等级；取不到返回 -1（页面按「数据不可用」灰档处理） */
export function segmentLevelOf(segmentId: string): number {
  for (let i = 0; i < SEGMENTS_FIXTURE.segments.length; i++) {
    const seg: Segment = SEGMENTS_FIXTURE.segments[i];
    if (seg.segment_id === segmentId) {
      return seg.level;
    }
  }
  return -1;
}
