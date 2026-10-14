// 站点包 Y ·「Y 型交叉口」V0 演示站（Issue IKLR30）。
//
// 用途:验证「几何→数据→大屏」全链路（不依赖任何后端 / SUMO / 桥接服务）。
// 来源:纯手工 Y-junction 几何 + 预置演示基线 + 默认分级（右侧拥堵 / 左侧通畅 / 无小球）。

import {
  STATION_Y_ALERTS,
  STATION_Y_CHANNELS,
  STATION_Y_CONTEXT,
  STATION_Y_DROPOFFS,
  STATION_Y_SCENARIOS,
  STATION_Y_SEGMENT_BASES,
  STATION_Y_SEGMENTS,
  STATION_Y_SECTIONS,
  STATION_Y_STATIONS,
  STATION_Y_ZONES,
} from './stationY.network.ts'
import type { StationPack } from './types.ts'

export const STATION_Y: StationPack = {
  key: 'Y',
  note: 'Y 型交叉口 · V0 演示站 · 右侧拥堵/左侧通畅 · 不接桥接服务',
  station: {
    station_id: 'DEMO-Y',
    name: 'Y 型交叉口(演示)',
    subtitle: 'V0 演示 · 右侧拥堵 / 左侧通畅',
  },

  segments: STATION_Y_SEGMENTS,
  source: {
    osm: false,
    label: '手工 Y-junction 示意路网 · 非实测 · 未配准',
  },
  sections: STATION_Y_SECTIONS,
  dropoffs: STATION_Y_DROPOFFS,
  zones: STATION_Y_ZONES,
  stations: STATION_Y_STATIONS,

  segmentBases: STATION_Y_SEGMENT_BASES,

  // V0 演示：不画小球，所以不提供 vehicleBases
  // 前端会因 vehicleBases 为空而只画路网颜色，不画车辆圆点。
  vehicleBases: [],

  // 告警剧本（与包 Y 基线自洽）
  alerts: STATION_Y_ALERTS,

  seedDispatch: {},

  // 分流建议（右侧 BND-BA 拥堵时，引导去左侧畅通路段）
  diversion: {
    'BND-BA': {
      segment_id: 'BND-BA',
      target_segment_id: 'BND-AS',
      target_name: 'A-S 转角缘石(左侧)',
      base_pct: 25,
      min_pct: 10,
      max_pct: 40,
      expect: '右侧拥堵预计缓解，等待时间减少',
      why: '右侧 B 腿严重拥堵，左侧 A 腿仍有容量，建议绕行左侧路口。',
    },
  },
  diversionFallback: {
    segment_id: '',
    target_segment_id: 'BND-AS',
    target_name: 'A-S 转角缘石(左侧)',
    base_pct: 20,
    min_pct: 10,
    max_pct: 35,
    expect: '预计受影响路段排队与行程时间下降(演示模板)',
    why: '按相邻路段饱和度排序自动选择承接路段(演示模板)。',
  },

  // 感知通道映射
  channels: STATION_Y_CHANNELS,
  videoCovered: ['INT-S-CW', 'INT-B-CW', 'INT-A-CW'],

  // 同化记录:3 路边界断面(允许回灌) + 3 路内部断面(制度上不允许)
  assimilation: [
    { point_id: 'DS-01', name: 'S 腿上游', segment_id: 'INT-S-CW', role: 'boundary', enabled: true, flow_dev_pct: 2.1, speed_dev_pct: 3.2, confidence: 0.92, gate_reason: null, gate_detail: null, reason: null },
    { point_id: 'DB-01', name: 'B 腿上游', segment_id: 'INT-B-CW', role: 'boundary', enabled: true, flow_dev_pct: 3.5, speed_dev_pct: 4.1, confidence: 0.88, gate_reason: null, gate_detail: null, reason: null },
    { point_id: 'DA-01', name: 'A 腿上游', segment_id: 'INT-A-CW', role: 'boundary', enabled: true, flow_dev_pct: 1.8, speed_dev_pct: 2.5, confidence: 0.94, gate_reason: null, gate_detail: null, reason: null },
    { point_id: 'DS-02', name: 'S 腿下游', segment_id: 'INT-S-CW', role: 'internal', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.0, gate_reason: null, gate_detail: '仅 role=boundary 断面允许回灌(手册门控口径)', reason: null },
    { point_id: 'DB-02', name: 'B 腿下游', segment_id: 'INT-B-CW', role: 'internal', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.0, gate_reason: null, gate_detail: '仅 role=boundary 断面允许回灌(手册门控口径)', reason: null },
    { point_id: 'DA-02', name: 'A 腿下游', segment_id: 'INT-A-CW', role: 'internal', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.0, gate_reason: null, gate_detail: '仅 role=boundary 断面允许回灌(手册门控口径)', reason: null },
  ],
  assimilationGate: { confidence_min: 0.75, data_age_max_s: 120 },

  // 环境上下文与场景注入
  context: STATION_Y_CONTEXT,
  scenarios: STATION_Y_SCENARIOS,

  recommend: {
    location_segment_id: 'INT-S-CW',
    location_offset_m: 210,
    arrival_segments: ['INT-S-CW', 'INT-S-CCW'],
    arrival_eta_min: 5.8,
    arrival_dropoff_point: 'DROP-Y-01',
    arrival_walk_min: 2.4,
    departure_segments: ['INT-S-CCW', 'BND-BA'],
    departure_eta_min: 6.1,
    alternatives: [
      { path_id: 'P-2', segments: ['INT-S-CW', 'BND-AS'], eta_min: 7.2, note: '左侧绕行，避开右侧拥堵段' },
    ],
    why: '主线进站尚有余量(v=40 km/h, x=0.57)；右侧 B 腿严重拥堵(x=0.91)，建议走左侧绕行。',
  },

  // 本站不接孪生桥接服务
  bridge: { enabled: false, base: '' },
}
