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
    expect: '西出站疏解路排队预计 -22%,消散时间 -3.1 分钟',
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

/** 人工置位预设(手册第 19 章:人为因素走管理端人工置位口子 F07/F08/F11) */
export interface ManualFactorPreset {
  factor_id: string
  name: string
  target: 'c' | 'demand' | 'lanes'
  multiplier: number
  note: string
}

export const MANUAL_FACTOR_PRESETS: ManualFactorPreset[] = [
  { factor_id: 'F01', name: '大雨(人工确认)', target: 'c', multiplier: 0.75, note: '通行能力 ×0.75' },
  { factor_id: 'F07', name: '大型活动(人工置位)', target: 'demand', multiplier: 1.3, note: '到达需求 ×1.3' },
  { factor_id: 'F08', name: '临时管制(人工置位)', target: 'lanes', multiplier: 0.5, note: '车道 ×0.5' },
]

// ---------- 效果对比(TC-14/TC-17 仿真对照演示) ----------

export interface EffectMetric {
  name: string
  unit: string
  /** 关推荐(对照) */
  baseline: number
  /** 开推荐(实验) */
  guided: number
  /** 数值越大越好? */
  better: 'up' | 'down'
}

export interface EffectScenario {
  key: string
  name: string
  metrics: EffectMetric[]
}

export const EFFECT_SCENARIOS: EffectScenario[] = [
  {
    key: 'peak',
    name: '列车集中到达峰值',
    metrics: [
      { name: '饱和度 x', unit: '', baseline: 0.91, guided: 0.74, better: 'down' },
      { name: '平均车速', unit: 'km/h', baseline: 9.8, guided: 14.6, better: 'up' },
      { name: '排队长度', unit: 'm', baseline: 340, guided: 180, better: 'down' },
      { name: '总行程时间', unit: 'min', baseline: 12.4, guided: 9.1, better: 'down' },
    ],
  },
  {
    key: 'normal',
    name: '常态平峰',
    metrics: [
      { name: '饱和度 x', unit: '', baseline: 0.42, guided: 0.38, better: 'down' },
      { name: '平均车速', unit: 'km/h', baseline: 28.3, guided: 29.1, better: 'up' },
      { name: '排队长度', unit: 'm', baseline: 40, guided: 25, better: 'down' },
      { name: '总行程时间', unit: 'min', baseline: 7.2, guided: 6.9, better: 'down' },
    ],
  },
  {
    key: 'incident',
    name: '突发事件',
    metrics: [
      { name: '饱和度 x', unit: '', baseline: 0.97, guided: 0.81, better: 'down' },
      { name: '平均车速', unit: 'km/h', baseline: 6.2, guided: 9.4, better: 'up' },
      { name: '排队长度', unit: 'm', baseline: 410, guided: 260, better: 'down' },
      { name: '总行程时间', unit: 'min', baseline: 15.8, guided: 11.9, better: 'down' },
    ],
  },
]

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
