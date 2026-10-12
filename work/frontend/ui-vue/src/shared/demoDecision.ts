// 决策工作台演示数据(仅 /decision 页面用,Issue #59)。
// 口径:效果对比是仿真对照(TC-14/TC-17 演示数据,同输入跑两遍),不是实测;
// 分流建议与阈值为演示值;告警与因素从契约 segments 快照派生,人工置位走
// mock POST /api/traffic/factors(手册第 19 章管理端人工置位口子)。

export interface DiversionSuggestion {
  segment_id: string
  target_segment_id: string
  target_name: string
  /** 系统建议分流比例(%) */
  base_pct: number
  min_pct: number
  max_pct: number
  /** 预期效果(演示表述) */
  expect: string
  /** 系统建议理由 */
  why: string
}

export const DIVERSION_SUGGESTIONS: Record<string, DiversionSuggestion> = {
  'SEG-003': {
    segment_id: 'SEG-003',
    target_segment_id: 'SEG-005',
    target_name: '南进站路',
    base_pct: 30,
    min_pct: 10,
    max_pct: 50,
    expect: '落客平台排队预计 -35%,总行程时间 -2.6 分钟',
    why: '落客平台严重拥堵(F01 大雨 + F06 违停占道,通行能力 -50%);南进站路饱和度 0.23,有余量承接,且不伤及已引导车辆(预约校验通过)。',
  },
  'SEG-007': {
    segment_id: 'SEG-007',
    target_segment_id: 'SEG-006',
    target_name: '北出站疏解路',
    base_pct: 25,
    min_pct: 10,
    max_pct: 40,
    expect: '社会停车场联络线排队预计 -22%,消散时间 -3.1 分钟',
    why: '社会停车场联络线拥堵(F01 大雨);北出站疏解路畅通,可承接绕行车流。',
  },
  'SEG-008': {
    segment_id: 'SEG-008',
    target_segment_id: 'SEG-002',
    target_name: '出发层环道·东',
    base_pct: 20,
    min_pct: 10,
    max_pct: 40,
    expect: '网约车蓄车场通道排队预计 -18%,等待 -4.0 分钟',
    why: '大型活动散场(F09,需求 +25%)推高排队;环道东侧畅通,建议网约车改东侧蓄车入口。',
  },
}

/** 建议不存在时的兜底模板 */
export function fallbackSuggestion(segmentId: string): DiversionSuggestion {
  return {
    segment_id: segmentId,
    target_segment_id: 'SEG-005',
    target_name: '南进站路',
    base_pct: 20,
    min_pct: 10,
    max_pct: 40,
    expect: '预计受影响路段排队与行程时间下降(演示模板)',
    why: '按相邻路段饱和度排序自动选择承接路段(演示模板)。',
  }
}

/** 人工置位预设(手册 §19 / §:2222:人为因素走管理端人工置位口子 = **F07 事故 / F08 施工管制 / F11 大型活动**) */
export interface ManualFactorPreset {
  factor_id: string
  name: string
  target: 'c' | 'demand' | 'lanes'
  multiplier: number
  note: string
}

export const MANUAL_FACTOR_PRESETS: ManualFactorPreset[] = [
  { factor_id: 'F07', name: '交通事故 / 故障车(人工置位)', target: 'lanes', multiplier: 0.5, note: '封闭车道 → 触发红档(手册 §:2840)' },
  { factor_id: 'F08', name: '施工 / 临时管制(人工置位)', target: 'lanes', multiplier: 0.5, note: '车道 ×0.5,带生效时间窗(手册 §:2841)' },
  { factor_id: 'F11', name: '大型活动(人工置位)', target: 'demand', multiplier: 1.3, note: '到达需求 ×1.3(手册 §:2844)' },
]

// ---------- 分流下发渠道(Issue #66,手册 §11.2:系统建议 + 人工可编辑 + **下发渠道** + 回执) ----------
// 口径:一期**没有真实下发通道**,回执为演示态(存 mock 服务端内存态,刷新页面不清,
// 页头「复位演示态」清);信号只"生成建议并推送,
// 不下发到信号机"(手册 §:2262),所以渠道是**演示枚举**,不暗示已对接任何外部系统。
export const DISPATCH_CHANNELS = ['情报板', '导航软件推送', '现场调度', '广播'] as const
export type DispatchChannel = (typeof DISPATCH_CHANNELS)[number]

// ---------- 效果对比(TC-14/TC-17 仿真对照演示;手册 §11.2 三组对比) ----------

export interface EffectMetric {
  name: string
  unit: string
  /** ① 不推荐(对照组) */
  no_guide: number
  /** ② "此刻最快"推荐(普通导航口径) */
  fastest: number
  /** ③ 协同推荐(本项目:时段预约 + 不伤害前车) */
  cooperative: number
  /** 数值越大越好? */
  better: 'up' | 'down'
}

export interface EffectCounts {
  inserted: number
  removed: number
  not_entered: number
  completed: number
}

export interface EffectScenario {
  key: string
  name: string
  /** 时间窗(TC-09:报表必须标清时间窗与来源) */
  window: string
  metrics: EffectMetric[]
  /** 评测协议四计数(分工表 §:76;同一随机种子下的三跑对照) */
  counts: EffectCounts
}

export const EFFECT_SCENARIOS: EffectScenario[] = [
  {
    key: 'peak',
    name: '列车集中到达峰值',
    window: '仿真时钟 18:00–19:00 · 评估窗 30 min · 固定种子三跑',
    metrics: [
      { name: '全网总行程时间', unit: 'min', no_guide: 12.4, fastest: 11.1, cooperative: 9.1, better: 'down' },
      { name: '先进入车辆到达时间增量', unit: 's', no_guide: 0, fastest: 42, cooperative: 18, better: 'down' },
      { name: '新增橙/红路段数', unit: '个', no_guide: 0, fastest: 2, cooperative: 0, better: 'down' },
      { name: '排队长度峰值', unit: 'm', no_guide: 410, fastest: 355, cooperative: 180, better: 'down' },
      { name: '饱和度峰值 x', unit: '', no_guide: 0.98, fastest: 0.93, cooperative: 0.74, better: 'down' },
    ],
    counts: { inserted: 412, removed: 0, not_entered: 12, completed: 400 },
  },
  {
    key: 'normal',
    name: '常态平峰',
    window: '仿真时钟 14:00–15:00 · 评估窗 30 min · 固定种子三跑',
    metrics: [
      { name: '全网总行程时间', unit: 'min', no_guide: 7.2, fastest: 7.0, cooperative: 6.9, better: 'down' },
      { name: '先进入车辆到达时间增量', unit: 's', no_guide: 0, fastest: 6, cooperative: 3, better: 'down' },
      { name: '新增橙/红路段数', unit: '个', no_guide: 0, fastest: 0, cooperative: 0, better: 'down' },
      { name: '排队长度峰值', unit: 'm', no_guide: 48, fastest: 45, cooperative: 25, better: 'down' },
      { name: '饱和度峰值 x', unit: '', no_guide: 0.46, fastest: 0.45, cooperative: 0.38, better: 'down' },
    ],
    counts: { inserted: 268, removed: 0, not_entered: 0, completed: 268 },
  },
  {
    key: 'incident',
    name: '突发事件(事故封道)',
    window: '仿真时钟 08:10–09:10 · 评估窗 30 min · 固定种子三跑',
    metrics: [
      { name: '全网总行程时间', unit: 'min', no_guide: 15.8, fastest: 14.2, cooperative: 11.9, better: 'down' },
      { name: '先进入车辆到达时间增量', unit: 's', no_guide: 0, fastest: 68, cooperative: 24, better: 'down' },
      { name: '新增橙/红路段数', unit: '个', no_guide: 3, fastest: 3, cooperative: 0, better: 'down' },
      { name: '排队长度峰值', unit: 'm', no_guide: 520, fastest: 470, cooperative: 260, better: 'down' },
      { name: '饱和度峰值 x', unit: '', no_guide: 1.04, fastest: 0.99, cooperative: 0.81, better: 'down' },
    ],
    counts: { inserted: 356, removed: 18, not_entered: 26, completed: 312 },
  },
]

// ---------- 处置前后对比(手册 §11.2:排队长度峰值 / 拥堵持续时间 / 饱和度和差) ----------

export interface AckCompareRow {
  name: string
  unit: string
  before: number
  after: number
  better: 'up' | 'down'
}

export interface AckComparison {
  /** TC-09:处置前后必须标清时间窗与来源 */
  window: string
  rows: AckCompareRow[]
}

export const ACK_COMPARISON: AckComparison = {
  window: '处置前 30 min vs 处置后 30 min(仿真对照,时间窗等长对齐)',
  rows: [
    { name: '排队长度峰值', unit: 'm', before: 340, after: 180, better: 'down' },
    { name: '拥堵持续时间', unit: 'min', before: 26, after: 11, better: 'down' },
    { name: '饱和度和差', unit: 'Δx 合计', before: 3.42, after: 2.05, better: 'down' },
  ],
}

// ---------- 判级阈值(只读演示,P1;真实来源 stations/thresholds.json) ----------

export interface ThresholdRow {
  metric: string
  unit: string
  bands: { level: 1 | 2 | 3 | 4; max: number }[]
}

export const LEVEL_THRESHOLDS: ThresholdRow[] = [
  { metric: '饱和度 x', unit: '', bands: [{ level: 1, max: 0.45 }, { level: 2, max: 0.7 }, { level: 3, max: 0.9 }, { level: 4, max: 999 }] },
  { metric: '速度比 v/v_f', unit: '', bands: [{ level: 1, max: 0.6 }, { level: 2, max: 0.45 }, { level: 3, max: 0.25 }, { level: 4, max: 999 }] },
  { metric: '密度 k', unit: '辆/公里', bands: [{ level: 1, max: 20 }, { level: 2, max: 45 }, { level: 3, max: 70 }, { level: 4, max: 999 }] },
  { metric: '排队长度 L_q', unit: 'm', bands: [{ level: 1, max: 50 }, { level: 2, max: 150 }, { level: 3, max: 300 }, { level: 4, max: 999 }] },
]

export interface ThresholdChange {
  time: string
  operator: string
  change: string
}

export const THRESHOLD_CHANGELOG: ThresholdChange[] = [
  { time: '2026-10-10 16:20', operator: '开发B', change: 'L_q 三档上限 150 → 180 m(列车到达日试标定,留痕待签发)' },
  { time: '2026-10-09 10:05', operator: '开发B', change: '初始阈值导入 stations/thresholds.json v0.1' },
]
