// 站点包(前端侧)· 类型定义。
//
// 为什么前端也要有"站点包"这一层:手册第 8 章的判定标准是"**换一个站只新增 / 替换
// 配置文件,不改引擎代码**"。管理端此前把站点名、路网几何、路段基线、断面编号、
// 感知通道映射全部写死在 `shared/demoNetwork.ts` / `mock/traffic.ts` 里 —— 那是
// 一份包,换不了站。本目录把那部分抽出来,一站一个包,页面与 mock 只认这里。
//
// 与后端 `stations/*.json` 的关系:
//   · 后端站点包是**引擎**的输入(`network.json` / `points.json` / `thresholds.json` …),
//     形状见 `docs/数据契约.md` 与 `手册第 8 章`;由 `map_ingest.py` 从 OSM + netconvert 产出。
//   · 本目录是**管理端演示**的输入(mock 未接后端时的替身),字段是后端包的子集 +
//     演示用基线(路段指标初值、告警剧本、分流建议、感知通道)。
//   · 后端接口面就绪后,这里退化为"离线兜底",不再承担真值;但**包与页面的边界不变**。

import type { CongestionLevel, FactorApplied, TrafficSource } from '../shared/traffic.ts'

/** 站点标识(顶栏 chip 与 meta 端点用) */
export interface PackStation {
  station_id: string
  name: string
  subtitle: string
  /**
   * 本站演示范围（米）——来自 `work/twin/site-ranges.json`（IKM4B4 登记表），
   * 由 `work/twin/netpack/check_site_ranges.py` 对账。页面只展示，不参与任何计算。
   */
  range_m?: number
  /** 范围来源：manual=人工圈定 / script=脚本推定 / ai-assisted=AI 辅助候选（已人工确认） */
  range_source?: 'manual' | 'script' | 'ai-assisted'
  /** 本站路段数（= site-ranges.json 的 seg_target），页面只展示，不参与计算 */
  segment_count?: number
}

/** 路段几何(契约 `TrafficNetwork.segments` 的子集) */
export interface PackSegment {
  segment_id: string
  name: string
  kind: 'main' | 'ramp'
  /** [lon, lat] 折线 */
  coords: [number, number][]
}

/** 检测断面(契约 `points.json` 的 detector 类点位;`role` 与 `sumo_edge_id` 是数据同化的前提) */
export interface PackSection {
  point_id: string
  segment_id: string
  name: string
  /** boundary = 围栏外→站前的上游断面(允许回灌);internal = 站前内部路段(禁止回灌) */
  role: 'boundary' | 'internal'
  /** 在路段内的相对位置 0~1(仅用于落点,不代表实测里程) */
  offset: number
  /** 该断面在 SUMO 路网里的边(站点包里 `sumo_edge_id` 的对应物) */
  sumo_edge_id?: string
}

/** 点位/场区/站点标注 */
export interface PackLandmark {
  id: string
  name: string
  lon: number
  lat: number
  /** 站点块的第二行副标(仅站点用;不填则不画副标,免得别站被写上肇庆东站的英文名) */
  sub?: string
}

/** 路段指标基线(mock 未接后端时的初值;不是任何模型的输出) */
export interface PackSegmentBase {
  segment_id: string
  source: TrafficSource
  q_vph: number
  v_kmh: number
  v_f_kmh: number
  k_vpk: number
  L_q_m: number
  L_seg_m: number
  T_d_min: number
  x: number
  c_base_vph: number
  c_vph: number
  factors_applied: FactorApplied[]
  ci: number
  level: CongestionLevel
  triggered_by: string[]
  confidence: number
  data_age_s: number
  /** 该路段是否恒为"数据不可用"(演示灰色档位;TC-11 展示侧) */
  stale: boolean
  /** 预测档(mock 只回传,不做模型) */
  pred?: { h15: { q_vph: number; level: CongestionLevel }; h30: { q_vph: number; level: CongestionLevel }; model: 'L0' }
  /** 该基线的来源说明(FCD 折算 / 预置演示值),供复核 */
  derive?: string
}

/** 合成车基线(mock 未接桥接服务时的替身;接上后不使用) */
export interface PackVehicleBase {
  vehicle_id: string
  driver_type: 'D1' | 'D2'
  segment_id: string
  offset_m: number
  speed_mps: number
  state: '行驶' | '排队' | '落客服务' | '候客' | '违停' | '已离开'
  guided: boolean
  is_demo_bound?: boolean
}

/** 告警剧本(四态流转在 mock 内存态里跑) */
export interface PackAlertBase {
  alert_id: string
  segment_id: string
  level: CongestionLevel
  triggered_by: string[]
  factor_ids?: string[]
  /** 首次观测 = 快照时间往前推 ago_min 分钟 */
  ago_min: number
  status: '待认领' | '处置中' | '已闭环' | '误报'
}

/** 分流建议(决策工作台;未命中的路段走 pack.diversionFallback) */
export interface PackDiversion {
  segment_id: string
  target_segment_id: string
  target_name: string
  base_pct: number
  min_pct: number
  max_pct: number
  expect: string
  why: string
}

/** 感知通道 ↔ 路段映射(`source` 与感知服务 stream_id 对齐) */
export interface PackChannel {
  cid: string
  source: string
  name: string
  segment_id: string
  /**
   * 摄像头在地图上的位置(Issue IKLX5Y)。
   * 有它 → 大屏在该点画摄像头标记、可点;没有 → 该通道不上图(老包不带这个字段)。
   */
  lon?: number
  lat?: number
  /**
   * 该通道当前**是否有视频源**(Issue IKLX5Y)。
   * `false` = 摄像头已布点、视频留空窗;感知层要显示「未接入视频源」占位,
   * **不得**套用「样本视频未导出」(那是另一回事,会让人以为有样本视频)。
   * 不写 = 老行为(按感知服务实际返回判定)。
   */
  hasVideo?: boolean
}

/**
 * 路网上色策略(Issue IKLX5Y)。
 * 默认(不写)= 老行为:所有路段按等级上色。
 * `'camera-covered'` = **只有摄像头监控下的路段才显示颜色**,其余只画中性灰轮廓
 * —— 业主 2026-10-15 裁定,一眼看出"这段没监控"。
 */
export type PackColorPolicy = 'all' | 'camera-covered'

/** 推荐快照骨架(引擎 routes.json 就绪前,由站点包给出演示路线) */
export interface PackRecommend {
  location_segment_id: string
  location_offset_m: number
  arrival_segments: string[]
  arrival_eta_min: number
  arrival_dropoff_point: string
  arrival_walk_min: number
  departure_segments: string[]
  departure_eta_min: number
  /** 备选路径(契约:备选 ≥2 条) */
  alternatives: { path_id: string; segments: string[]; eta_min: number; note: string }[]
  why: string
}

/** 数据同化记录基线(断面回灌状态;门控由 mock 侧按 pack.assimilationGate 判) */
export interface PackAssimilation {
  point_id: string
  name: string
  segment_id: string
  role: 'boundary' | 'internal'
  enabled: boolean
  flow_dev_pct: number | null
  speed_dev_pct: number | null
  confidence: number
  gate_reason: 'confidence_low' | 'data_age' | 'deviation_fuse' | null
  gate_detail: string | null
  reason: string | null
}

/**
 * 环境上下文基线(Issue #77;站点包按站给默认天气 / 日历)。
 * ⚠️ **全部是编造的演示值**——真实数据拿不到,字段口径对齐手册第 19 章因素登记表
 * (F01 天气 / F02 昼夜 / F03 列车到发 / F10 时段日历)。不做成真值,页面标「演示数据(模拟)」。
 *
 * 折减系数**不在包里**——它是因素登记表的参数(F01 一期由 T5 因素表手填,二期由气象接口校准),
 * 只在 mock 侧一张表里,免得包与代码两处各写一份再对不上。包只声明"这个站是什么天气"。
 */
export interface PackContext {
  weather: {
    condition: '晴' | '多云' | '小雨' | '大雨' | '大雾' | '台风'
    temp_c: number
    humidity_pct: number
    visibility_km: number
    precip_mm: number
    wind: string
  }
  calendar: '工作日' | '周末' | '节假日'
  /** 下一班列车口径说明(演示;真实来源 = T3 列车时刻表) */
  next_train_note: string
}

/** 场景注入预设档(Issue #77 决策可视化用;每档 = 一组可一键应用的演示场景) */
export interface PackScenario {
  key: string
  name: string
  /** 一句话说明这一档演示什么 */
  note: string
  /** 对照用的因素编号(仅展示) */
  factor_ids: string[]
}

/** 一个完整的站点包 */
export interface StationPack {
  /** 包标识(与文件名/环境变量取值一致) */
  key: string
  /** 顶栏切换器 / 大屏按钮上的短标签(多包同站时用来区分);缺省用 `station.name` */
  label?: string
  /** 一句话说明这个包是什么(页面页脚/自检用) */
  note: string
  station: PackStation

  // ---- 路网与标注 ----
  segments: PackSegment[]
  /** 底图来源口径(页面水印用);`osm` 为真时触发 OSM 署名义务 */
  source: { osm: boolean; label: string; attribution?: string }
  sections: PackSection[]
  dropoffs: PackLandmark[]
  zones: PackLandmark[]
  stations: PackLandmark[]

  // ---- mock 演示数据 ----
  segmentBases: PackSegmentBase[]
  vehicleBases: PackVehicleBase[]
  alerts: PackAlertBase[]
  /** 预置"已下发"留痕(处置中的那条告警,演示可直接走回写;TC-07) */
  seedDispatch: Record<string, { channel: string; ratio_pct: number; dispatch_ago_min: number }>
  diversion: Record<string, PackDiversion>
  diversionFallback: PackDiversion
  channels: PackChannel[]
  /** 一期有视频链路覆盖的路段(双源并排的 video 槽位可用性) */
  videoCovered: string[]
  /**
   * 路网上色策略(Issue IKLX5Y)。不写 = `'all'`(老行为:所有段按等级上色)。
   * `'camera-covered'` = 只有摄像头覆盖的段上色,其余画灰轮廓。
   */
  colorPolicy?: PackColorPolicy
  assimilation: PackAssimilation[]
  assimilationGate: { confidence_min: number; data_age_max_s: number }
  recommend: PackRecommend

  // ---- 环境上下文与场景注入(Issue #77;全部为编造的演示值) ----
  /** 本站默认天气与时段基调(页面展示「能获取的环境数据」) */
  context: PackContext
  /** 场景注入预设档(决策可视化一键应用) */
  scenarios: PackScenario[]

  /** 孪生桥接服务(TraCI 车辆真值):该站是否启用,以及端口 */
  bridge: { enabled: boolean; base: string }
}
