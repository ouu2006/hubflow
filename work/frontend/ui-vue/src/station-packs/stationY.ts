// 站点包 Y ·「Y 型单行道路网」V0 演示站（Issue IKLR30）。
//
// 业主 2026-10-14 二版：真道路双车道模型——主线左/右两车道，分流后各接左/右支线车道，
// 分叉处车道弧线圆滑；右支线拥堵、左支线通畅；不画车辆小球。
// 用途:验证「几何→数据→大屏」全链路（不依赖任何后端 / SUMO / 桥接服务）。

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
  note: 'Y 型单行道路网 · V0 演示站 · 右支拥堵/左支通畅 · 不接桥接服务',
  station: {
    station_id: 'DEMO-Y',
    name: 'Y 型汇流口(演示)',
    subtitle: '单行道自下而上 · 右支拥堵 / 左支通畅',
  },

  segments: STATION_Y_SEGMENTS,
  source: {
    osm: false,
    label: '手工 Y 型单行道示意路网 · 非实测 · 未配准',
  },
  sections: STATION_Y_SECTIONS,
  dropoffs: STATION_Y_DROPOFFS,
  zones: STATION_Y_ZONES,
  stations: STATION_Y_STATIONS,

  segmentBases: STATION_Y_SEGMENT_BASES,

  // V0 演示：不画小球（业主口径），车辆数据不提供
  vehicleBases: [],

  // 告警剧本（只挂右支线拥堵侧，与基线自洽）
  alerts: STATION_Y_ALERTS,

  seedDispatch: {},

  // 分流建议（右支拥堵时引导去左支）
  diversion: {
    'SEG-B': {
      segment_id: 'SEG-B',
      target_segment_id: 'SEG-A',
      target_name: '左支线车道',
      base_pct: 30,
      min_pct: 10,
      max_pct: 50,
      expect: '右支线排队预计 -45%,行程时间 -4.2 分钟',
      why: '右支线(SEG-B)严重拥堵(x=0.92, v=10 km/h);左支线当前畅通(x=0.20, v=50 km/h),有余量承接,绕行代价可接受。',
    },
  },
  diversionFallback: {
    segment_id: '',
    target_segment_id: 'SEG-A',
    target_name: '左支线车道',
    base_pct: 20,
    min_pct: 10,
    max_pct: 40,
    expect: '预计受影响路段排队与行程时间下降(演示模板)',
    why: '按相邻路段饱和度排序自动选择承接路段(演示模板)。',
  },

  // 感知通道映射
  channels: STATION_Y_CHANNELS,
  videoCovered: ['SEG-S1', 'SEG-A', 'SEG-B'],

  // 同化记录:每条车道一条上游 boundary(允许回灌) + 一条下游 internal(禁止)
  assimilation: [
    { point_id: 'DS-01', name: '主线入口段·左车道·上游断面', segment_id: 'SEG-S1', role: 'boundary', enabled: true, flow_dev_pct: 2.1, speed_dev_pct: 3.2, confidence: 0.92, gate_reason: null, gate_detail: null, reason: null },
    { point_id: 'DS-02', name: '主线入口段·右车道·上游断面', segment_id: 'SEG-S2', role: 'boundary', enabled: true, flow_dev_pct: 1.8, speed_dev_pct: 2.9, confidence: 0.93, gate_reason: null, gate_detail: null, reason: null },
    { point_id: 'DB-01', name: '左支线车道·上游断面', segment_id: 'SEG-A', role: 'boundary', enabled: true, flow_dev_pct: 2.6, speed_dev_pct: 2.2, confidence: 0.91, gate_reason: null, gate_detail: null, reason: null },
    { point_id: 'DB-02', name: '右支线车道·上游断面', segment_id: 'SEG-B', role: 'boundary', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.62, gate_reason: 'confidence_low', gate_detail: '数据置信度 0.62 < 门控阈值 0.75,停止回灌并留日志', reason: 'confidence_low' },
    { point_id: 'DS-11', name: '主线入口段·左车道·下游断面', segment_id: 'SEG-S1', role: 'internal', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.0, gate_reason: null, gate_detail: '仅 role=boundary 断面允许回灌(手册门控口径)', reason: null },
    { point_id: 'DS-12', name: '主线入口段·右车道·下游断面', segment_id: 'SEG-S2', role: 'internal', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.0, gate_reason: null, gate_detail: '仅 role=boundary 断面允许回灌(手册门控口径)', reason: null },
    { point_id: 'DB-11', name: '左支线车道·下游断面', segment_id: 'SEG-A', role: 'internal', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.0, gate_reason: null, gate_detail: '仅 role=boundary 断面允许回灌(手册门控口径)', reason: null },
    { point_id: 'DB-12', name: '右支线车道·下游断面', segment_id: 'SEG-B', role: 'internal', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.0, gate_reason: null, gate_detail: '仅 role=boundary 断面允许回灌(手册门控口径)', reason: null },
  ],
  assimilationGate: { confidence_min: 0.75, data_age_max_s: 120 },

  // 环境上下文与场景注入
  context: STATION_Y_CONTEXT,
  scenarios: STATION_Y_SCENARIOS,

  recommend: {
    location_segment_id: 'SEG-S1',
    location_offset_m: 800,
    arrival_segments: ['SEG-S2', 'SEG-A'],
    arrival_eta_min: 5.8,
    arrival_dropoff_point: 'DROP-Y-01',
    arrival_walk_min: 2.4,
    departure_segments: ['SEG-A2', 'SEG-B2'],
    departure_eta_min: 6.1,
    alternatives: [
      { path_id: 'P-2', segments: ['SEG-S2', 'SEG-B'], eta_min: 9.6, note: '走右支线,当前严重拥堵不推荐' },
    ],
    why: '主线尚有余量(v=35 km/h, x=0.30);右支线严重拥堵(x=0.92),建议走左支线绕行。',
  },

  // 本站不接孪生桥接服务
  bridge: { enabled: false, base: '' },
}
