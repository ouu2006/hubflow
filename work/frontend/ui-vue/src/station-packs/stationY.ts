// 站点包 Y ·「Y 型单行道路网」V0 演示站（Issue IKLR30）。
//
// 业主 2026-10-14 三版 6 路段口径：
//   SEG-01 主线整条（南入口→汇流口，黑框段）
//   SEG-02/03 左支线走廊 近岔段/远段
//   SEG-04/05 右支线走廊 近岔段/远段
//   SEG-06 站前服务段
// 每条走廊双向合并画（「分左回右去」由断面与指标承载）；右支拥堵、左支通畅；不画车辆小球。
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

  // 告警剧本（只挂右支线拥堵侧与站前，与基线自洽）
  alerts: STATION_Y_ALERTS,

  seedDispatch: {},

  // 分流建议（右支拥堵时引导去左支）
  diversion: {
    'SEG-04': {
      segment_id: 'SEG-04',
      target_segment_id: 'SEG-02',
      target_name: '左支线·近岔段',
      base_pct: 30,
      min_pct: 10,
      max_pct: 50,
      expect: '右支线排队预计 -45%,行程时间 -4.2 分钟',
      why: '右支线(SEG-04/05)拥堵至严重拥堵(x=0.74/0.95);左支线当前畅通(x=0.20),有余量承接,绕行代价可接受。',
    },
    'SEG-05': {
      segment_id: 'SEG-05',
      target_segment_id: 'SEG-03',
      target_name: '左支线·远段',
      base_pct: 30,
      min_pct: 10,
      max_pct: 50,
      expect: '右支线远段排队预计 -50%,行程时间 -5.1 分钟',
      why: '右支线远段严重拥堵(x=0.95, v=12 km/h);左支线远段畅通(x=0.16),有余量承接。',
    },
  },
  diversionFallback: {
    segment_id: '',
    target_segment_id: 'SEG-02',
    target_name: '左支线·近岔段',
    base_pct: 20,
    min_pct: 10,
    max_pct: 40,
    expect: '预计受影响路段排队与行程时间下降(演示模板)',
    why: '按相邻路段饱和度排序自动选择承接路段(演示模板)。',
  },

  // 感知通道映射
  channels: STATION_Y_CHANNELS,
  videoCovered: ['SEG-01', 'SEG-02', 'SEG-04', 'SEG-06'],

  // 同化记录:每条路段一条回方向 boundary(允许回灌) + 一条去方向 internal(禁止)
  assimilation: [
    { point_id: 'D-01', name: '主线·回方向断面(上游)', segment_id: 'SEG-01', role: 'boundary', enabled: true, flow_dev_pct: 2.1, speed_dev_pct: 3.2, confidence: 0.92, gate_reason: null, gate_detail: null, reason: null },
    { point_id: 'D-02', name: '左支线·近岔段·回方向断面(上游)', segment_id: 'SEG-02', role: 'boundary', enabled: true, flow_dev_pct: 2.6, speed_dev_pct: 2.2, confidence: 0.91, gate_reason: null, gate_detail: null, reason: null },
    { point_id: 'D-03', name: '左支线·远段·回方向断面(上游)', segment_id: 'SEG-03', role: 'boundary', enabled: true, flow_dev_pct: 1.8, speed_dev_pct: 2.5, confidence: 0.94, gate_reason: null, gate_detail: null, reason: null },
    { point_id: 'D-04', name: '右支线·近岔段·回方向断面(上游)', segment_id: 'SEG-04', role: 'boundary', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.62, gate_reason: 'confidence_low', gate_detail: '数据置信度 0.62 < 门控阈值 0.75,停止回灌并留日志', reason: 'confidence_low' },
    { point_id: 'D-05', name: '右支线·远段·回方向断面(上游)', segment_id: 'SEG-05', role: 'boundary', enabled: true, flow_dev_pct: 4.2, speed_dev_pct: 5.1, confidence: 0.87, gate_reason: null, gate_detail: null, reason: null },
    { point_id: 'D-06', name: '站前服务段·回方向断面(上游)', segment_id: 'SEG-06', role: 'boundary', enabled: true, flow_dev_pct: 2.9, speed_dev_pct: 3.8, confidence: 0.90, gate_reason: null, gate_detail: null, reason: null },
    { point_id: 'D-11', name: '主线·去方向断面(下游)', segment_id: 'SEG-01', role: 'internal', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.0, gate_reason: null, gate_detail: '仅 role=boundary 断面允许回灌(手册门控口径)', reason: null },
    { point_id: 'D-12', name: '左支线·近岔段·去方向断面(下游)', segment_id: 'SEG-02', role: 'internal', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.0, gate_reason: null, gate_detail: '仅 role=boundary 断面允许回灌(手册门控口径)', reason: null },
    { point_id: 'D-13', name: '左支线·远段·去方向断面(下游)', segment_id: 'SEG-03', role: 'internal', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.0, gate_reason: null, gate_detail: '仅 role=boundary 断面允许回灌(手册门控口径)', reason: null },
    { point_id: 'D-14', name: '右支线·近岔段·去方向断面(下游)', segment_id: 'SEG-04', role: 'internal', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.0, gate_reason: null, gate_detail: '仅 role=boundary 断面允许回灌(手册门控口径)', reason: null },
    { point_id: 'D-15', name: '右支线·远段·去方向断面(下游)', segment_id: 'SEG-05', role: 'internal', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.0, gate_reason: null, gate_detail: '仅 role=boundary 断面允许回灌(手册门控口径)', reason: null },
    { point_id: 'D-16', name: '站前服务段·去方向断面(下游)', segment_id: 'SEG-06', role: 'internal', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.0, gate_reason: null, gate_detail: '仅 role=boundary 断面允许回灌(手册门控口径)', reason: null },
  ],
  assimilationGate: { confidence_min: 0.75, data_age_max_s: 120 },

  // 环境上下文与场景注入
  context: STATION_Y_CONTEXT,
  scenarios: STATION_Y_SCENARIOS,

  recommend: {
    location_segment_id: 'SEG-01',
    location_offset_m: 1500,
    arrival_segments: ['SEG-01', 'SEG-02', 'SEG-06'],
    arrival_eta_min: 5.8,
    arrival_dropoff_point: 'DROP-Y-01',
    arrival_walk_min: 2.4,
    departure_segments: ['SEG-06', 'SEG-05'],
    departure_eta_min: 6.1,
    alternatives: [
      { path_id: 'P-2', segments: ['SEG-01', 'SEG-04', 'SEG-06'], eta_min: 9.6, note: '走右支线,当前拥堵不推荐' },
    ],
    why: '主线畅通(x=0.32);右支线拥堵(x=0.74/0.95),建议走左支线;站前服务段缓行(x=0.52)可接受。',
  },

  // 本站不接孪生桥接服务
  bridge: { enabled: false, base: '' },
}
