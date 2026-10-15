// 站点包 Z ·「站点 OSM 真路网」演示站（Issue IKLX5Y）。
//
// 业主 2026-10-15 口径：
//   ① 把真路网（仓库内 OSM 切片）当成**一张地图**放到监控大屏上（跟 Y 型那张一样）；
//   ② 大屏**新增摄像头位置**，点击直接跳到感知层对应摄像头的画面；
//   ③ **只有摄像头监控下的路段才显示颜色（拥堵情况）**，其余只画灰色路网轮廓；
//   ④ **视频样本先不弄**——摄像头视频留个空窗。
//
// 几何来源：`work/twin/netpack/build_station_pack.py` 从 OSM 切片归并产出
//   （见 `stationZ.network.ts`，脚本产物勿手改）。
// **几何是真值（OSM）；路况指标一律是演示数据（模拟）。**
// 本单不判定主干 / 分支；走廊落位另开单。

import { STATION_Z_SEGMENTS } from './stationZ.network.ts'
import type { PackChannel, PackSegmentBase, StationPack } from './types.ts'

// ---- 摄像头布点（6 路）----
//
// 布点口径：**按决策点布**——把"司机要在哪儿做选择"的地方各放一个：
//   cam-01 吉庆大道·西进口（从西侧进场，含走廊最西那个口子）
//   cam-02 吉庆大道·中段（三个东侧口子汇入处）
//   cam-03 场区出入口（拐进停车场那一下）
//   cam-04 停车场·站门口（走到站口最后一段）
//   cam-05 停车场·北支（停车场内部北侧通道）
//   cam-06 鼎湖大道·进场（另一条进场干道）
//
// ⚠️ **坐标不是路测点，是"落在这条路段线上"的示意位置**（经纬度取自该段折线上的点，
//    由生成脚本投影得到）——本批摄像头是**示意布点**，不是踏勘定的点位。
// ⚠️ **`hasVideo: false`**：本批摄像头**全部没有视频源**（业主：视频样本先不弄）。
//    感知层对它们显示「未接入视频源 · 本期留空」，**不得**说成"样本视频未导出"。
const CHANNELS: PackChannel[] = [
  { cid: 'C-01', source: 'cam-01', name: '吉庆大道·西进口', segment_id: 'SZ-01', lon: 112.6548733, lat: 23.2151734, hasVideo: false },
  { cid: 'C-02', source: 'cam-02', name: '吉庆大道·中段', segment_id: 'SZ-01', lon: 112.6573791, lat: 23.2139003, hasVideo: false },
  { cid: 'C-03', source: 'cam-03', name: '场区出入口', segment_id: 'SZ-05', lon: 112.6570652, lat: 23.2140549, hasVideo: false },
  { cid: 'C-04', source: 'cam-04', name: '停车场·站门口', segment_id: 'SZ-12', lon: 112.6577645, lat: 23.2156324, hasVideo: false },
  { cid: 'C-05', source: 'cam-05', name: '停车场·北支', segment_id: 'SZ-07', lon: 112.6588897, lat: 23.2148643, hasVideo: false },
  { cid: 'C-06', source: 'cam-06', name: '鼎湖大道·进场', segment_id: 'SZ-03', lon: 112.652399, lat: 23.2128006, hasVideo: false },
]

// ---- 路段基线（演示值）----
//
// **只给摄像头覆盖的 5 条段基线**——本站的上色策略是 `camera-covered`：
// 只有这些段会显示颜色，其余 16 段画灰轮廓（"这段没监控"）。
// 数值是**编造的演示值**（一眼能看出是整数 / 整档），不是任何模型的输出。
//
// 等级分布刻意做成"进场堵、场区通"的演示剧情：
//   SZ-01 吉庆大道（进场主路）  3 级 拥堵
//   SZ-03 鼎湖大道·进场          2 级 缓行
//   SZ-05 场区出入道             2 级 缓行
//   SZ-07 停车场·北支            1 级 畅通
//   SZ-12 停车场·站门口          4 级 严重拥堵
const SEGMENT_BASES: PackSegmentBase[] = [
  {
    segment_id: 'SZ-01',
    source: 'video',
    q_vph: 3200,
    v_kmh: 18,
    v_f_kmh: 50,
    k_vpk: 178,
    L_q_m: 420,
    L_seg_m: 3873,
    T_d_min: 13.0,
    x: 0.8,
    c_base_vph: 4000,
    c_vph: 4000,
    factors_applied: [],
    ci: 68,
    level: 3,
    triggered_by: ['x', 'v'],
    confidence: 0.86,
    data_age_s: 6,
    stale: false,
    derive: '演示值（编造）· 本站只演示"进场拥堵"这一档',
  },
  {
    segment_id: 'SZ-03',
    source: 'video',
    q_vph: 1600,
    v_kmh: 34,
    v_f_kmh: 50,
    k_vpk: 47,
    L_q_m: 80,
    L_seg_m: 793,
    T_d_min: 1.4,
    x: 0.6,
    c_base_vph: 2667,
    c_vph: 2667,
    factors_applied: [],
    ci: 46,
    level: 2,
    triggered_by: ['x'],
    confidence: 0.81,
    data_age_s: 8,
    stale: false,
    derive: '演示值（编造）· 缓行档',
  },
  {
    segment_id: 'SZ-05',
    source: 'video',
    q_vph: 900,
    v_kmh: 22,
    v_f_kmh: 30,
    k_vpk: 41,
    L_q_m: 60,
    L_seg_m: 746,
    T_d_min: 2.0,
    x: 0.6,
    c_base_vph: 1500,
    c_vph: 1500,
    factors_applied: [],
    ci: 47,
    level: 2,
    triggered_by: ['x'],
    confidence: 0.79,
    data_age_s: 9,
    stale: false,
    derive: '演示值（编造）· 场区出入道缓行档',
  },
  {
    segment_id: 'SZ-07',
    source: 'video',
    q_vph: 260,
    v_kmh: 14,
    v_f_kmh: 14,
    k_vpk: 19,
    L_q_m: 40,
    L_seg_m: 443,
    T_d_min: 1.9,
    x: 0.35,
    c_base_vph: 743,
    c_vph: 743,
    factors_applied: [],
    ci: 22,
    level: 1,
    triggered_by: [],
    confidence: 0.83,
    data_age_s: 11,
    stale: false,
    derive: '演示值（编造）· 停车场内部畅通档',
  },
  {
    segment_id: 'SZ-12',
    source: 'video',
    q_vph: 700,
    v_kmh: 9,
    v_f_kmh: 20,
    k_vpk: 78,
    L_q_m: 150,
    L_seg_m: 239,
    T_d_min: 1.6,
    x: 0.9,
    c_base_vph: 778,
    c_vph: 778,
    factors_applied: [],
    ci: 82,
    level: 4,
    triggered_by: ['x', 'v', 'L_q'],
    confidence: 0.88,
    data_age_s: 5,
    stale: false,
    derive: '演示值（编造）· 站门口严重拥堵档',
  },
]

export const STATION_Z: StationPack = {
  key: 'Z',
  note: '站点 OSM 真路网 · 几何为真值（OSM）· 只摄像头段上色 · 6 路摄像头（视频留空窗）',
  station: {
    station_id: 'ZQNZ',
    name: '肇庆东站',
    subtitle: '真路网 · 吉庆大道 / 鼎湖大道 / 场区通道',
  },

  segments: STATION_Z_SEGMENTS,

  // 真 OSM 几何 → 触发 OSM 署名义务（条款核实 E-11 / E-13）
  source: {
    osm: true,
    label: 'OSM 真路网 · 几何为真值 · 指标为演示数据（模拟）',
    attribution: '地图数据 © OpenStreetMap 贡献者，依 ODbL 许可',
  },

  // 断面：本单不落断面（断面是走廊/同化那条线的事，另开单）
  sections: [],
  dropoffs: [],
  zones: [],
  stations: [
    // 站点块 = 站房位置（OSM node 9195330007 的坐标由生成脚本外的口径给出，属示意）
    { id: 'STA-ZQNZ', name: '肇庆东站', lon: 112.6581162, lat: 23.2173959, sub: '站房（OSM node 示意）' },
  ],

  segmentBases: SEGMENT_BASES,

  // 不画车辆小球（业主口径：用路段级着色表达路况）
  vehicleBases: [],

  alerts: [],

  seedDispatch: {},

  diversion: {},
  diversionFallback: {
    segment_id: '',
    target_segment_id: '',
    target_name: '',
    base_pct: 0,
    min_pct: 0,
    max_pct: 0,
    expect: '本包不提供分流建议（演示范围只到"路网 + 摄像头"）',
    why: '本包不提供分流建议（演示范围只到"路网 + 摄像头"）',
  },

  // 感知通道 = 6 路摄像头（本批无视频源：`hasVideo: false`）
  channels: CHANNELS,
  /** 有摄像头覆盖的路段（其余段只画灰轮廓，不上色） */
  videoCovered: CHANNELS.map((c) => c.segment_id),

  /**
   * 上色策略：**只有摄像头监控下的路段才显示颜色**（业主 2026-10-15 裁定）。
   * 其余路段画中性灰轮廓 —— 一眼看出"这段没监控"。
   */
  colorPolicy: 'camera-covered',

  // 断面同化不在本单范围
  assimilation: [],
  assimilationGate: { confidence_min: 0.75, data_age_max_s: 120 },

  context: {
    weather: { condition: '多云', temp_c: 25, humidity_pct: 70, visibility_km: 10, precip_mm: 0, wind: '偏东风 2 级' },
    calendar: '工作日',
    next_train_note: '演示值 · 本包不含列车数据',
  },
  scenarios: [],

  recommend: {
    location_segment_id: 'SZ-01',
    location_offset_m: 1000,
    arrival_segments: ['SZ-01', 'SZ-05'],
    arrival_eta_min: 6.5,
    arrival_dropoff_point: '',
    arrival_walk_min: 3.0,
    departure_segments: ['SZ-12', 'SZ-05'],
    departure_eta_min: 4.0,
    alternatives: [
      { path_id: 'P-2', segments: ['SZ-03', 'SZ-05'], eta_min: 8.2, note: '走鼎湖大道进场（缓行）' },
    ],
    why: '吉庆大道进场段拥堵（x=0.80），鼎湖大道稍好（x=0.60）；站门口一段严重拥堵。',
  },

  // 本站不接孪生桥接服务（桥接服务跑的是另一份路网，接上会把坐标画错位）
  bridge: { enabled: false, base: '' },
}
