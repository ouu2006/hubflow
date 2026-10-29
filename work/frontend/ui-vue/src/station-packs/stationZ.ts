// 站点包 Z ·「站点 OSM 真路网」演示站（Issue IKLX5Y）。
//
// 业主 2026-10-15 口径：
//   ① 把真路网（仓库内 OSM 切片）当成**一张地图**放到监控大屏上（跟 Y 型那张一样）；
//   ② 大屏**新增摄像头位置**，点击直接跳到感知层对应摄像头的画面；
//   ③ **只有摄像头监控下的路段才显示颜色（拥堵情况）**，其余只画灰色路网轮廓；
//   ④ **视频样本先不弄**——摄像头视频留个空窗。
//
// 几何来源：`work/twin/netpack/build_junction_pack.py`（先路线 → 再分段 → 再打标签，IKMERX）
//   从 OSM 切片产出 **61 段（站区 500 m）**，见 `stationZ.network.ts`（脚本产物勿手改）。
// **2026-10-17 IKMDKY 子单①：大屏切新段（21 段退役）**——段号由 2 位（SZ-01…）改 3 位（SZ-001…）。
// **2026-10-21 IKP5D3：Z21 旧 21 段过渡包已删除**——后端站点登记表只登记 Z / GZ，
//   留着 Z21 会让顶栏切到一个后端 404 的键（切包即全站 404），故与裁定一致地移出 PACKS。
// **几何是真值（OSM）；路况指标一律是演示数据（模拟）。**
// 本单不判定主干 / 分支；走廊落位另开单。

import { STATION_Z_SEGMENTS } from './stationZ.network.ts'
// IKOQEJ：方向/车道/对向/贯通字段（由 tools/gen_station_directions.py 只读 enriched 生成）
import { STATION_Z_DIRECTIONS } from './stationZ.directions.generated.ts'
import { CAMERA_CHANNELS } from './cameraChannels.generated.ts'
import { DEMO_CAMERA_CHANNELS } from './demoCameraChannels.generated.ts'
// 2026-10-29 演示验收：真值路网底衬（脚本 work/frontend/scripts/gen_station_roads.py 生成）
import { STATION_Z_ROADS } from './stationZ.roads.ts'
import type { PackSegmentBase, StationPack } from './types.ts'

// ---- 摄像头：源台账（6 路）＋ 演示层 N 段 N 路（业主 2026-10-25 口径落页面）----
//
// **源台账唯一真值来源 = `work/perception/mapping/camera-segments.json`**（IKMDKY 三段映射登记表）；
// 本文件**不再手写通道表**，只 import 两份生成物（生成器：`work/perception/tools/gen_station_channels.py`；
// 改映射先改登记表 / camera-plan 再生成）：
//   · `cameraChannels.generated.ts` = 源台账 6 路：cam_id ↔ channel_id（= `source`，感知服务
//     stream_id）↔ segment_id；C-02 / C-05 能对上样本视频（road2 / track1，非本站现场、映射仅演示），
//     其余 4 路 `hasVideo: false`——**不等于**没有摄像头、更不等于数据可用；
//   · `demoCameraChannels.generated.ts` = 演示层 55 路（61 段 − 源台账 6 段，`demo: true`、
//     画面走 `reuseOf` 演示复用）——点位取 camera-plan 每段 `offset_m` 落折线（演示布点）。
// ⚠️ **IKMDKY 切新段后的段号映射**：6 个源台账摄像头按**几何最近**落到新 61 段上（段号 2 位 → 3 位）；
//    C-06 原坐标在站区 500 m 之外，沿鼎湖大道就近落到站区边界段 SZ-015（演示布点，非实测坐标）。
// 合并后本包 61 路 = 61 段（一段最多 1 路，源台账优先、演示层补齐），图钉 / 感知台账 / 监控墙
// 都按这份合并结果渲染（业主 2026-10-25：路段有多少摄像头，监控墙就要有多少摄像头画面）。

// ---- 路段基线（演示值）----
//
// **只给摄像头源台账覆盖的 6 条段基线**——这 6 条是源台账初始映射所在段。
// 上色策略自 IKP5DM 起改为 `all`（与 GZ 一致）：61 段都按等级上色，不再把其余 55 段
// 画成"没监控"；图钉自 2026-10-25 起画全部 61 路摄像头（源台账 6 + 演示层 55，见上方通道合并）。
// 数值是**编造的演示值**（一眼能看出是整数 / 整档），不是任何模型的输出。
//
// ⚠️ **`source` 一律取 `'twin'`（孪生链路 / 虚拟检测器）**，不是 `'video'`：
//    本包没有任何**本站段**的视频链路指标；6 路摄像头里只有 C-02/C-05 有样本视频，
//    而样本视频非本站现场、不产出本站段指标。若在这里写 `'video'`，双数据源并排（TC-19）与
//    数据供给对照带（DataSupplyPanel）就会把编造的演示值列成"视频链路槽位"，
//    与"样本视频只做感知演示"的口径**自相矛盾**（口径红线：不得把模拟值说成实测值）。
//
// 等级分布刻意做成"进场堵、场区通"的演示剧情：
//   新段号（由旧段迁入）：SZ-010 / SZ-005（旧 SZ-01 吉庆大道）  3 级 拥堵
//                         SZ-015（旧 SZ-03 鼎湖大道）          2 级 缓行
//                         SZ-054（旧 SZ-05 场区出入道）        2 级 缓行
//                         SZ-024（旧 SZ-07 停车场北支）        1 级 畅通
//                         SZ-019（旧 SZ-12 停车场站门口）      4 级 严重拥堵
//
// ⚠️ **迁到新段后 L_q_m / T_d_min 按新段长收口**：旧包是按"整条路"给的排队长度
//    （旧 SZ-01 段长 3873 m、L_q=420 m），新段只有 49.6 / 83.1 m，原值会算出
//    L_q/L_seg ≈ 8.5 这种不成立的排队比。这里按"排队长度不超过段长"重给演示值，
//    仍然全是编造值，不是实测。
const SEGMENT_BASES: PackSegmentBase[] = [
  {
    segment_id: 'SZ-010',
    source: 'twin',
    q_vph: 3200,
    v_kmh: 18,
    v_f_kmh: 50,
    k_vpk: 178,
    L_q_m: 36,
    L_seg_m: 49.6,
    T_d_min: 1.5,
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
    derive: '演示值（编造）· 迁自旧 21 段 SZ-01「吉庆大道进场拥堵」档',
  },
  {
    segment_id: 'SZ-005',
    source: 'twin',
    q_vph: 3200,
    v_kmh: 18,
    v_f_kmh: 50,
    k_vpk: 178,
    L_q_m: 58,
    L_seg_m: 83.1,
    T_d_min: 2,
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
    derive: '演示值（编造）· 迁自旧 21 段 SZ-01「吉庆大道进场拥堵」档',
  },
  {
    segment_id: 'SZ-054',
    source: 'twin',
    q_vph: 900,
    v_kmh: 22,
    v_f_kmh: 30,
    k_vpk: 41,
    L_q_m: 60,
    L_seg_m: 544.7,
    T_d_min: 2,
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
    derive: '演示值（编造）· 迁自旧 21 段 SZ-05「场区出入道缓行」档',
  },
  {
    segment_id: 'SZ-019',
    source: 'twin',
    q_vph: 700,
    v_kmh: 9,
    v_f_kmh: 20,
    k_vpk: 78,
    L_q_m: 150,
    L_seg_m: 238.8,
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
    derive: '演示值（编造）· 迁自旧 21 段 SZ-12「站门口严重拥堵」档',
  },
  {
    segment_id: 'SZ-024',
    source: 'twin',
    q_vph: 260,
    v_kmh: 14,
    v_f_kmh: 14,
    k_vpk: 19,
    L_q_m: 40,
    L_seg_m: 63.4,
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
    derive: '演示值（编造）· 迁自旧 21 段 SZ-07「停车场内部畅通」档',
  },
  {
    segment_id: 'SZ-015',
    source: 'twin',
    q_vph: 1600,
    v_kmh: 34,
    v_f_kmh: 50,
    k_vpk: 47,
    L_q_m: 30,
    L_seg_m: 54.3,
    T_d_min: 1,
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
    derive: '演示值（编造）· 迁自旧 21 段 SZ-03「鼎湖大道缓行」档',
  },
]

export const STATION_Z: StationPack = {
  key: 'Z',
  label: 'Z · 61 段',
  note: '站点 OSM 真路网 61 段（站区 500 m）· 几何为真值（OSM）· 摄像头 61 路 = 61 段（源台账 6 + 演示层 55，N 段 = N 摄像头 = N 视频，2026-10-25）',
  station: {
    station_id: 'ZQNZ',
    name: '肇庆东站',
    // ⚠️ 范围/段数来自 `work/twin/site-ranges.json`（IKM4B4 登记表，脚本推定 500 m / 61 段）；
    //    改范围先改登记表，再跑 `python work/twin/netpack/check_site_ranges.py` 对账。
    subtitle: '真路网 · 站区 500 m（脚本推定）/ 61 段 · 吉庆大道 / 鼎湖大道 / 场区通道',
    range_m: 500,
    range_source: 'script',
    segment_count: 61,
  },

  segments: STATION_Z_SEGMENTS,
  /**
   * **真值路网底衬**（2026-10-29 演示验收）。
   *
   * 底图源 TileJSON maxzoom=14，站区视角 zoom≈16.5 是 overzoom：z14 瓦片没有 service/track
   * 级道路，本站 44 段 ramp（停车场内部通道/服务道路/连接匝道）在底图上是空白 + 建筑面，
   * 彩色路段看起来"悬空穿场地"；干道也被合并简化，彩色线与底图黄线错开 10~15 m。
   *
   * 解决办法：把同一份 OSM 切片里的车行道自己画一遍当底衬，并让底图道路图层在
   * zoom ≥ 14.5 整族退出（见 `MapLibreViewer.vue` 的 `BASEMAP_ROAD_MAXZOOM`）。
   * 几何取 OSM 原始节点，与 `stationZ.network.ts` 的 61 段同源同口径 —— 所以彩色段
   * 一定长在自己画的路网上，也与图上那句「路网几何为真值（OSM 切片）」自洽。
   */
  roads: STATION_Z_ROADS,
  // IKOQEJ：方向 / 车道 / 对向 / 贯通（只读 enriched 生成；非契约、不参与判级）
  segmentDirections: STATION_Z_DIRECTIONS,

  // 真 OSM 几何 → 触发 OSM 署名义务（条款核实 E-11 / E-13）
  source: {
    osm: true,
    label: 'OSM 真路网 · 几何为真值 · 指标为演示数据（模拟）',
    attribution: '地图数据 © OpenStreetMap 贡献者，依 ODbL 许可',
  },

  // ---- 断面 / 点位（IKM4TE mock 数据；业主 2026-10-17：先用 mock 代替，真实化归 IKMHMX）----
  // ⚠️ `sections` 是**候选清单**，`boundary/internal` 逐条标了 role，但**尚未经队长签字冻结**
  //    （冻结清单属 M1-10 / TC-20 前置；IKMHMX 负责签字冻结与真实化）。这里只是让页面/契约形状先跑通。
  sections: [
    // 边界候选：主干道外围断面（允许回灌的候选）
    { point_id: 'P-B01', segment_id: 'SZ-001', name: '吉庆大道西侧上游断面（候选边界·待冻结）', role: 'boundary', offset: 0.5 },
    { point_id: 'P-B02', segment_id: 'SZ-003', name: '吉庆大道北侧上游断面（候选边界·待冻结）', role: 'boundary', offset: 0.5 },
    { point_id: 'P-B03', segment_id: 'SZ-004', name: '吉庆大道东侧上游断面（候选边界·待冻结）', role: 'boundary', offset: 0.5 },
    { point_id: 'P-B04', segment_id: 'SZ-009', name: '吉庆大道南侧上游断面（候选边界·待冻结）', role: 'boundary', offset: 0.5 },
    { point_id: 'P-B05', segment_id: 'SZ-015', name: '鼎湖大道北侧上游断面（候选边界·待冻结）', role: 'boundary', offset: 0.5 },
    // 内部断面：站前/停车场内部，**禁止回灌**（TC-20 第②项）
    { point_id: 'P-I01', segment_id: 'SZ-018', name: '停车场内部通道断面（内部·禁止回灌）', role: 'internal', offset: 0.5 },
    { point_id: 'P-I02', segment_id: 'SZ-019', name: '停车场·站门口断面（内部·禁止回灌）', role: 'internal', offset: 0.5 },
    { point_id: 'P-I03', segment_id: 'SZ-022', name: '停车场内部通道断面2（内部·禁止回灌）', role: 'internal', offset: 0.5 },
    { point_id: 'P-I04', segment_id: 'SZ-024', name: '停车场北支断面（内部·禁止回灌）', role: 'internal', offset: 0.5 },
    { point_id: 'P-I05', segment_id: 'SZ-054', name: '场区出入道断面（内部·禁止回灌）', role: 'internal', offset: 0.5 },
    { point_id: 'P-I06', segment_id: 'SZ-055', name: '场区出入道断面2（内部·禁止回灌）', role: 'internal', offset: 0.5 },
  ],
  // 落客点 / 候客区（mock：坐标取对应路段折线上的演示点，不是踏勘点位；真实化归 IKMHMX）
  dropoffs: [
    { id: 'DROP-01', name: '停车场·站门口落客区（演示点）', lon: 112.6582025, lat: 23.21537 },
    { id: 'DROP-02', name: '停车场北支落客区（演示点）', lon: 112.6583471, lat: 23.21514 },
    { id: 'DROP-03', name: '场区落客区（演示点）', lon: 112.6562027, lat: 23.2158868 },
  ],
  zones: [
    { id: 'ZONE-01', name: '候客区·停车场北支（演示点）', lon: 112.6588897, lat: 23.2148643 },
    { id: 'ZONE-02', name: '蓄车区·场区通道（演示点）', lon: 112.6558858, lat: 23.2147712 },
  ],
  stations: [
    // 站点块 = 站房位置（坐标取自 OSM node 9195330007 的公开坐标；该节点**不在本切片内**，
    // 故它只当锚点用，图上站点块是示意，不代表站房轮廓）
    { id: 'STA-ZQNZ', name: '肇庆东站', lon: 112.6581162, lat: 23.2173959, sub: '站房（示意锚点，非站房轮廓）' },
  ],

  segmentBases: SEGMENT_BASES,

  // 不画车辆小球（业主口径：用路段级着色表达路况）
  vehicleBases: [],

  // ---- 告警 / 下发 / 分流建议（IKM4TE mock 数据；演示剧本，非现场实况）----
  // 四态各一条：待认领 / 处置中 / 已闭环 / 误报；level 会被 mock 按**当前路段快照**重映射（#75 第④条）。
  alerts: [
    {
      alert_id: 'DEMO-AL-2026-1017-001',
      segment_id: 'SZ-019',
      level: 4,
      triggered_by: ['L_q', 'x'],
      factor_ids: ['F07'],
      ago_min: 12,
      status: '待认领',
    },
    {
      alert_id: 'DEMO-AL-2026-1017-002',
      segment_id: 'SZ-010',
      level: 3,
      triggered_by: ['x'],
      factor_ids: ['F11'],
      ago_min: 20,
      status: '处置中',
    },
    {
      alert_id: 'DEMO-AL-2026-1017-003',
      segment_id: 'SZ-054',
      level: 2,
      triggered_by: ['v'],
      factor_ids: [],
      ago_min: 35,
      status: '已闭环',
    },
    {
      alert_id: 'DEMO-AL-2026-1017-004',
      segment_id: 'SZ-005',
      level: 2,
      triggered_by: ['v'],
      factor_ids: [],
      ago_min: 45,
      status: '误报',
    },
  ],

  // 预置一条「已下发」回执，演示处置工作台有历史可看（mock 内存态，刷新复位）
  seedDispatch: {
    'DEMO-AL-2026-1017-002': { channel: '导航软件推送', ratio_pct: 15, dispatch_ago_min: 5 },
  },

  // 分流建议（演示值，非模型输出）：未命中路段走 diversionFallback
  diversion: {
    'SZ-019': {
      segment_id: 'SZ-019',
      target_segment_id: 'SZ-024',
      target_name: '停车场·北支',
      base_pct: 30,
      min_pct: 10,
      max_pct: 50,
      expect: '站门口排队长度下降（演示值）',
      why: '站门口段演示严重拥堵，建议把部分车流导向停车场北支 / 候客区（演示建议，非模型输出）',
    },
    'SZ-010': {
      segment_id: 'SZ-010',
      target_segment_id: 'SZ-015',
      target_name: '鼎湖大道',
      base_pct: 20,
      min_pct: 0,
      max_pct: 40,
      expect: '进场干道饱和度下降（演示值）',
      why: '吉庆大道进场段演示拥堵，建议部分车流走鼎湖大道进场（演示建议，非模型输出）',
    },
  },
  diversionFallback: {
    segment_id: '',
    target_segment_id: '',
    target_name: '',
    base_pct: 0,
    min_pct: 0,
    max_pct: 0,
    expect: '本路段暂无分流建议（演示包未预置）',
    why: '本路段暂无分流建议（演示包未预置；不是"不需要分流"的结论）',
  },

  // 感知通道 = 源台账 6 路（生成物）+ 演示层 55 路（生成物）= 61 路 = 61 段
  //（业主 2026-10-25：路段有多少摄像头，监控墙就要有多少摄像头画面；来源见文件头注释）
  channels: [...CAMERA_CHANNELS, ...DEMO_CAMERA_CHANNELS.Z],
  /**
   * **视频链路覆盖 = 空**：本包没有任何**本站段**的视频链路指标（站点包 Z 不给 `source: "video"` 的段基线）。
   * ⚠️ 注意别和"有没有视频源"混：6 路摄像头里 C-02/C-05 有**样本视频**（感知演示用，非本站现场），
   *    但样本视频**不产出本站段指标**，所以 video 槽位仍如实显示"不可用"（TC-19/TC-11），
   *    不拿编造的演示值冒充视频链路，也不把样本视频算成"本站实测"。
   * ⚠️ 这与 `colorPolicy` **不是一回事**：那条说的是"路网按等级上色"（IKP5DM 起全段上色），
   *    本条说的是"哪几条段有**视频链路数据**"。
   */
  videoCovered: [],

  /**
   * 上色策略：**全段按等级上色**（IKP5DM 选 A，与 GZ 一致）——一期口径是
   * **N 段 = N 演示摄像头 = N 视频（mock 复用）**，若仍按源台账 6 路决定上色，
   * 其余 55 段会被画成灰、读成"没监控"，与口径矛盾。
   * 图钉自 2026-10-25 起画全部 61 路（源台账 6 + 演示层 55，`channels` 合并生成物）。
   * 无数据 / 陈旧段仍走灰档，与"没摄像头"不是一回事。
   */
  colorPolicy: 'all',

  // 数据同化状态（IKM4TE mock 数据）：仅候选边界断面允许回灌；内部断面恒 false（TC-20 第②项）。
  // ⚠️ 本批是**演示值（mock）**，不是真实回灌；真实回灌 / 门控 / 熔断归 IKMHMX（M1-10 / TC-20）。
  assimilation: [
    {
      point_id: 'P-B01',
      name: '吉庆大道西侧上游断面（候选边界）',
      segment_id: 'SZ-001',
      role: 'boundary',
      enabled: false,
      flow_dev_pct: null,
      speed_dev_pct: null,
      confidence: 0.62,
      gate_reason: 'confidence_low',
      gate_detail: '置信度 0.62 < 门控 0.75（演示值；真实回灌/门控归 IKMHMX）',
      reason: '演示值：同化未开启（mock 状态，非真实回灌；IKMHMX 真实化后按边界断面接入）',
    },
    {
      point_id: 'P-B05',
      name: '鼎湖大道北侧上游断面（候选边界）',
      segment_id: 'SZ-015',
      role: 'boundary',
      enabled: false,
      flow_dev_pct: null,
      speed_dev_pct: null,
      confidence: 0.52,
      gate_reason: 'confidence_low',
      gate_detail: '置信度 0.52 < 门控 0.75（演示值）',
      reason: '演示门控：置信度不足，停止回灌（mock 数据）',
    },
    {
      point_id: 'P-I02',
      name: '停车场·站门口断面（内部）',
      segment_id: 'SZ-019',
      role: 'internal',
      enabled: false,
      flow_dev_pct: null,
      speed_dev_pct: null,
      confidence: 0.0,
      gate_reason: null,
      gate_detail: null,
      reason: '内部断面禁止回灌（TC-20 第②项；演示数据）',
    },
  ],
  assimilationGate: { confidence_min: 0.75, data_age_max_s: 120 },

  context: {
    weather: { condition: '多云', temp_c: 25, humidity_pct: 70, visibility_km: 10, precip_mm: 0, wind: '偏东风 2 级' },
    calendar: '工作日',
    next_train_note: '演示值 · 本包不含列车数据',
  },
  // 场景剧本（IKM4TE mock 数据）：**环境上下文侧预设**（F01/F02/F03/F10），与「人工置位」（F07/F08/F11）是两个口子；
  // key 必须与 `ScenarioInjectPanel.vue` 的 applyPreset 对应，否则页面 chip 点了没反应。
  scenarios: [
    {
      key: 'baseline',
      name: '基线（晴·平峰）',
      note: '天气晴 + 平峰时段（演示剧本；每档都可一键注入并重算判级）',
      factor_ids: [],
    },
    {
      key: 'rain-peak',
      name: '大雨·晚高峰',
      note: 'F01 大雨 × 0.75 通行能力 + 晚高峰需求（演示剧本）',
      factor_ids: ['F01', 'F10'],
    },
    {
      key: 'fog-night',
      name: '大雾·夜间',
      note: 'F01 大雾 + F02 夜间（演示剧本；检测置信度按因素表折减）',
      factor_ids: ['F01', 'F02'],
    },
    {
      key: 'train-burst',
      name: '列车到达·需求×1.35',
      note: 'F03 列车到达放量 + F10 时段（演示剧本）',
      factor_ids: ['F03', 'F10'],
    },
    {
      key: 'accident-loop',
      name: '事故后绕行峰值',
      note: '早高峰 + 需求 ×1.2 的环境侧演示档（事故本身走「人工置位」F07，别混口子）',
      factor_ids: ['F10'],
    },
  ],

  // ⚠️ 演示骨架（IKMF1W 2026-10-17）：三组段序列是**在 61 段真 OSM 几何上按"相邻段端点落在
  //    另一段折线上（≤25 m）"的连通关系拼出来的**，不是引擎的 K 最短路 + 预约输出，也不是
  //    按当时路况重算的结果；只改数据、不改 mock 结构（契约 §二形状不变）。相邻性自检见本 PR。
  recommend: {
    location_segment_id: 'SZ-010',
    location_offset_m: 40,
    // 推荐：吉庆大道进口 → 场区通道 → 停车场·站门口（575 m ≈ 2.9 min，按演示速度估算）
    arrival_segments: ['SZ-010', 'SZ-013', 'SZ-002', 'SZ-011', 'SZ-019'],
    arrival_eta_min: 2.9,
    arrival_dropoff_point: '',
    arrival_walk_min: 3.0,
    // 离站：站门口 → 吉庆大道 → 鼎湖大道方向（688 m ≈ 3.3 min）
    departure_segments: ['SZ-019', 'SZ-011', 'SZ-002', 'SZ-013', 'SZ-010', 'SZ-006', 'SZ-015'],
    departure_eta_min: 3.3,
    // 契约要求备选 ≥2 条；两条都是连通序列，且与推荐路线不完全重叠
    alternatives: [
      { path_id: 'P-2', segments: ['SZ-010', 'SZ-012', 'SZ-001', 'SZ-019'], eta_min: 3.9, note: '经吉庆大道直行（演示备选，约 777 m）' },
      { path_id: 'P-3', segments: ['SZ-010', 'SZ-013', 'SZ-002', 'SZ-011', 'SZ-005', 'SZ-019'], eta_min: 3.3, note: '经吉庆大道东段绕行（演示备选，约 658 m）' },
    ],
    why: '演示路线：在 61 段真 OSM 路网上按相邻关系拼出的连通序列（不是引擎 K 最短路 + 预约输出，也不是按当时路况重算的结果）；吉庆大道进场段演示拥堵、站门口段演示严重拥堵。',
  },

  // 本站不接孪生桥接服务（桥接服务跑的是另一份路网，接上会把坐标画错位）
  bridge: { enabled: false, base: '' },
}
