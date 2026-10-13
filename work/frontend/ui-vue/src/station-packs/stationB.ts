// 站点包 B ·「一环五射」虚构示范站(业主 2026-10-12 定的第二站)。
//
// 用途:验证手册 §8.4 的判定标准 —— **换一个站只新增 / 替换配置文件,不改引擎代码**。
// 本站的路网、路段基线、断面、点位全部由 SUMO 产物生成(见 `stationB.network.ts` 头部
// 的复现命令),本文件只放**演示剧本**:站名、告警、分流建议、感知通道映射、推荐骨架。
//
// 口径红线(与生成脚本那边的 README 一致):
//  · 路网是**凭空造的示意路网**,不指任何真实车站;坐标是占位锚点,未做地理配准;
//  · 站名取「虚构示范站」是**故意**的:不能用任何像真站的名字,免得被当成实测数据;
//  · 基线由 FCD 折算(DEMAND_SCALE=5 峰值工况),判级按手册 §6.3 档位边界;
//  · 本站**不接孪生桥接服务**(twin_preview 是肇庆东站的 OSM 切片,与本站路网无关)。

import {
  STATION_B_DROPOFFS,
  STATION_B_SEGMENT_BASES,
  STATION_B_SEGMENTS,
  STATION_B_SECTIONS,
  STATION_B_STATIONS,
  STATION_B_ZONES,
} from './stationB.network.ts'
import type { StationPack } from './types.ts'

export const STATION_B: StationPack = {
  key: 'B',
  note: '虚构示范站 · 自建示意路网「一环五射」· 基线由 FCD 折算(峰值工况)',
  station: {
    station_id: 'DEMO-B',
    name: '虚构示范站',
    subtitle: '一环五射示意路网 · 非任何真实车站',
  },

  segments: STATION_B_SEGMENTS,
  source: {
    osm: false,
    label: '自建示意路网「一环五射」· 非实测 · 未配准',
  },
  sections: STATION_B_SECTIONS,
  dropoffs: STATION_B_DROPOFFS,
  zones: STATION_B_ZONES,
  stations: STATION_B_STATIONS,

  segmentBases: STATION_B_SEGMENT_BASES,

  // 合成车基线:本站不接桥接服务,孪生车辆一律走这一份(2 s 一帧按各自速度在段内前进、到段尾回卷)。
  // 车种与站位按"站前服务段"的实际组织摆:地下落客通道停驻 / 上客道排队 / 港湾 / 两个场区。
  vehicleBases: [
    { vehicle_id: 'twin-0001', driver_type: 'D1', segment_id: 'SEG-001', offset_m: 120, speed_mps: 8.4, state: '行驶', guided: true, is_demo_bound: true },
    { vehicle_id: 'twin-0002', driver_type: 'D1', segment_id: 'SEG-001', offset_m: 640, speed_mps: 5.2, state: '行驶', guided: true },
    { vehicle_id: 'twin-0003', driver_type: 'D2', segment_id: 'SEG-002', offset_m: 210, speed_mps: 3.1, state: '排队', guided: false },
    { vehicle_id: 'twin-0004', driver_type: 'D1', segment_id: 'SEG-003', offset_m: 480, speed_mps: 4.4, state: '行驶', guided: true },
    { vehicle_id: 'twin-0005', driver_type: 'D2', segment_id: 'SEG-004', offset_m: 300, speed_mps: 1.4, state: '排队', guided: false },
    { vehicle_id: 'twin-0006', driver_type: 'D1', segment_id: 'SEG-005', offset_m: 520, speed_mps: 14.2, state: '行驶', guided: true },
    { vehicle_id: 'twin-0007', driver_type: 'D2', segment_id: 'SEG-006', offset_m: 260, speed_mps: 12.6, state: '行驶', guided: false },
    { vehicle_id: 'twin-0008', driver_type: 'D1', segment_id: 'SEG-007', offset_m: 410, speed_mps: 14.8, state: '行驶', guided: true },
    { vehicle_id: 'twin-0009', driver_type: 'D1', segment_id: 'SEG-009', offset_m: 350, speed_mps: 13.9, state: '行驶', guided: false },
    { vehicle_id: 'twin-0010', driver_type: 'D1', segment_id: 'SEG-010', offset_m: 460, speed_mps: 3.0, state: '行驶', guided: true },
    { vehicle_id: 'twin-0011', driver_type: 'D2', segment_id: 'SEG-011', offset_m: 96, speed_mps: 2.7, state: '落客服务', guided: false },
    { vehicle_id: 'twin-0012', driver_type: 'D1', segment_id: 'SEG-012', offset_m: 120, speed_mps: 2.6, state: '落客服务', guided: false },
    { vehicle_id: 'twin-0013', driver_type: 'D1', segment_id: 'SEG-013', offset_m: 88, speed_mps: 1.1, state: '候客', guided: false },
    { vehicle_id: 'twin-0014', driver_type: 'D2', segment_id: 'SEG-014', offset_m: 150, speed_mps: 0.9, state: '候客', guided: false },
  ],

  // 告警剧本:四态条数与一站一致(待认领 2 / 处置中 1 / 已闭环 3 / 误报 1),路段与等级
  // 对本站基线自洽(等级不高于该段当前 level 的下一档,避免"畅通段挂红档"这种自打脸)。
  alerts: [
    { alert_id: 'B-2412-004', segment_id: 'SEG-004', level: 4, triggered_by: ['x', 'L_q'], factor_ids: ['F07'], ago_min: 2, status: '待认领' },
    { alert_id: 'B-2412-006', segment_id: 'SEG-013', level: 4, triggered_by: ['v', 'L_q'], ago_min: 6, status: '待认领' },
    { alert_id: 'B-2412-002', segment_id: 'SEG-002', level: 3, triggered_by: ['x', 'v'], factor_ids: ['F01', 'F06'], ago_min: 11, status: '处置中' },
    { alert_id: 'B-2410-118', segment_id: 'SEG-003', level: 3, triggered_by: ['x', 'L_q'], ago_min: 42, status: '已闭环' },
    { alert_id: 'B-2410-121', segment_id: 'SEG-010', level: 3, triggered_by: ['x'], factor_ids: ['F01'], ago_min: 55, status: '已闭环' },
    { alert_id: 'B-2410-109', segment_id: 'SEG-001', level: 3, triggered_by: ['x'], ago_min: 73, status: '已闭环' },
    { alert_id: 'B-2410-096', segment_id: 'SEG-008', level: 1, triggered_by: [], ago_min: 90, status: '误报' },
  ],

  seedDispatch: { 'B-2412-002': { channel: '情报板', ratio_pct: 30, dispatch_ago_min: 5 } },

  // 分流建议:承接段一律挑**同向、当前畅通**的放射路/环路,理由写明"它现在有余量"。
  diversion: {
    'SEG-004': {
      segment_id: 'SEG-004',
      target_segment_id: 'SEG-009',
      target_name: '西北放射路',
      base_pct: 35,
      min_pct: 15,
      max_pct: 50,
      expect: '西侧环路排队预计 -40%,总行程时间 -3.4 分钟',
      why: '交通事故(F07,车道 ×0.5)把西侧环路通行能力砍半,饱和度 x 已到 1.71;西北放射路当前畅通(v/v_f = 0.84),有余量承接,绕行多 0.6 km。',
    },
    'SEG-002': {
      segment_id: 'SEG-002',
      target_segment_id: 'SEG-007',
      target_name: '南放射路',
      base_pct: 25,
      min_pct: 10,
      max_pct: 45,
      expect: '东侧环路排队预计 -22%,消散时间 -2.8 分钟',
      why: '东侧环路缓行至拥堵(F01 大雨 c×0.75 + F06 违停占道 lanes×0.8);南放射路畅通,可承接绕行车流。',
    },
    'SEG-013': {
      segment_id: 'SEG-013',
      target_segment_id: 'SEG-011',
      target_name: '出租车上客道',
      base_pct: 20,
      min_pct: 10,
      max_pct: 40,
      expect: '社会停车场通道等待预计 -30%,等待 -5.2 分钟',
      why: '社会停车场通道内平均车速已掉到 2.9 km/h(v/v_f = 0.14),场内已满;出租上客道仍有空档,建议社会车辆改停公交港湾外侧临停位。',
    },
  },
  diversionFallback: {
    segment_id: '',
    target_segment_id: 'SEG-007',
    target_name: '南放射路',
    base_pct: 20,
    min_pct: 10,
    max_pct: 40,
    expect: '预计受影响路段排队与行程时间下降(演示模板)',
    why: '按相邻路段饱和度排序自动选择承接路段(演示模板)。',
  },

  // 感知通道映射:6 路公开样本视频 → 本站路段。映射只决定"这一路画面算到哪条路段上",
  // 与视频本身是不是本站无关(页脚常驻写明"公开样本视频 · 非本站现场")。
  channels: [
    { cid: 'C-01', source: 'road1', name: '东北放射路', segment_id: 'SEG-005' },
    { cid: 'C-02', source: 'road2', name: '西北放射路', segment_id: 'SEG-009' },
    { cid: 'C-03', source: 'cross1', name: '站前环路东', segment_id: 'SEG-002' },
    { cid: 'C-04', source: 'cross2', name: '站前环路西', segment_id: 'SEG-004' },
    { cid: 'C-05', source: 'track1', name: '地下落客通道', segment_id: 'SEG-010' },
    { cid: 'C-06', source: 'short_cross', name: '出租车上客道', segment_id: 'SEG-011' },
  ],

  videoCovered: ['SEG-005', 'SEG-009', 'SEG-002', 'SEG-004', 'SEG-010', 'SEG-011'],

  // 同化记录:5 条边界断面(放射路站外端,允许回灌)+ 2 条内部断面(站前服务段,制度上不允许)。
  // 门控阈值取 0.75,与 E-04 那条 gate_detail 的文案对齐(不再出现"0.62 < 0.6 却门控"的矛盾)。
  assimilation: [
    { point_id: 'E-01', name: '东北放射路·边界', segment_id: 'SEG-005', role: 'boundary', enabled: true, flow_dev_pct: 2.6, speed_dev_pct: 3.4, confidence: 0.91, gate_reason: null, gate_detail: null, reason: null },
    { point_id: 'E-02', name: '东南放射路·边界', segment_id: 'SEG-006', role: 'boundary', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.0, gate_reason: 'data_age', gate_detail: '该断面检测器离线 186 s > 新鲜度门 120 s,停止回灌并留日志', reason: 'data_age' },
    { point_id: 'E-03', name: '南放射路·边界', segment_id: 'SEG-007', role: 'boundary', enabled: true, flow_dev_pct: 1.9, speed_dev_pct: 2.2, confidence: 0.93, gate_reason: null, gate_detail: null, reason: null },
    { point_id: 'E-04', name: '西南放射路·边界', segment_id: 'SEG-008', role: 'boundary', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.62, gate_reason: 'confidence_low', gate_detail: '数据置信度 0.62 < 门控阈值 0.75,停止回灌并留日志', reason: 'confidence_low' },
    { point_id: 'E-05', name: '西北放射路·边界', segment_id: 'SEG-009', role: 'boundary', enabled: true, flow_dev_pct: 3.8, speed_dev_pct: 2.9, confidence: 0.88, gate_reason: null, gate_detail: null, reason: null },
    { point_id: 'E-08', name: '站前路·内部', segment_id: 'SEG-001', role: 'internal', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.9, gate_reason: null, gate_detail: '仅 role=boundary 断面允许回灌(手册门控口径)', reason: 'internal_not_allowed' },
    { point_id: 'E-09', name: '地下落客通道·内部', segment_id: 'SEG-010', role: 'internal', enabled: false, flow_dev_pct: null, speed_dev_pct: null, confidence: 0.9, gate_reason: null, gate_detail: '仅 role=boundary 断面允许回灌(手册门控口径)', reason: 'internal_not_allowed' },
  ],
  assimilationGate: { confidence_min: 0.75, data_age_max_s: 120 },

  // 环境上下文与场景注入(Issue #77)。⚠️ 全部是**编造的演示值**(与包 A 同口径,数值按本站剧本另编);
  // 字段口径对齐手册第 19 章因素登记表 F01 / F02 / F03 / F10。
  // 包 B 的基线(FCD 折算,峰值工况)**不含**天气因素,故这里声明 `多云`(晴天口径,不折减)。
  context: {
    weather: { condition: '多云', temp_c: 26, humidity_pct: 74, visibility_km: 9, precip_mm: 0, wind: '偏东风 2 级' },
    calendar: '工作日',
    next_train_note: '演示值 · 真实来源 = T3 列车时刻表(12306 公开时刻表手填)',
  },
  scenarios: [
    { key: 'baseline', name: '常态基准', note: '多云 + 平峰:不注入任何环境因素,作为对照基准', factor_ids: [] },
    { key: 'accident-loop', name: '西侧环路事故', note: 'F07 事故封道(人工置位口径)+ F10 早高峰需求 ×1.2:本站剧本的事故段在 SEG-004', factor_ids: ['F07', 'F10'] },
    { key: 'fog-night', name: '大雾夜间', note: 'F01 大雾(×0.7)+ F02 昼夜(检测置信度下降,不做强推荐)', factor_ids: ['F01', 'F02'] },
    { key: 'train-burst', name: '列车集中到达', note: 'F03 列车到发:到达需求 ×1.35,地下落客通道压力最大', factor_ids: ['F03'] },
  ],

  recommend: {
    location_segment_id: 'SEG-001',
    location_offset_m: 210,
    arrival_segments: ['SEG-001', 'SEG-010'],
    arrival_eta_min: 5.8,
    arrival_dropoff_point: 'DROP-01',
    arrival_walk_min: 2.4,
    departure_segments: ['SEG-010', 'SEG-003'],
    departure_eta_min: 6.1,
    alternatives: [
      { path_id: 'P-2', segments: ['SEG-001', 'SEG-011'], eta_min: 7.2, note: '走地面出租上客道,少 1 层坡道,但上客道当前有排队' },
      { path_id: 'P-3', segments: ['SEG-003', 'SEG-002', 'SEG-001', 'SEG-010'], eta_min: 9.4, note: '南侧绕行避开西侧环路事故段,里程多 1.2 km' },
    ],
    why: '地下落客通道(SEG-010)当前 4.5 km/h 但落客位空、排队短,预计 5.8 分钟;西侧环路(SEG-004)因事故封道饱和度过 1,不推荐;预约未伤及前车(最大 +9 秒)。',
  },

  // 本站**不接**孪生桥接服务:work/frontend/tools/twin_preview 跑的是肇庆东站的 OSM 切片,
  // 与本站示意路网对不上。开它会把别站的车辆坐标画到本站图上(口径事故),所以关掉走合成车。
  bridge: { enabled: false, base: '' },
}
