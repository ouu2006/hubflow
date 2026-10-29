<script setup lang="ts">
// 决策可视化(Issue #77 三页收敛 · 决策层第二层的新视图)。
//
// 业主口径:「决策层我要看见**全部数据**和**处理数据的结果**,还有**可调控的全部可视化过程**,
// 差不多就是决策判断的可视化演示」。本面板按四段摆开:
//   ① **输入**   —— 选中路段的全部指标 + 生效因素 + 环境上下文(判级与决策实际吃进去的东西);
//   ② **处理过程** —— x = q_vph / c_vph 的逐步演算 → 四档阈值对比(当前值落在哪档、离边界多远)→ level;
//                    因素加权 → 通行能力折减 → x 前后对照;CI 四项加权构成;
//   ③ **可调控** —— 场景注入(环境侧)+ 人工置位(事件侧,在处置队列视图)+ 分流比例(在处置工作台),
//                    mock 模式由 mock 服务端重算并显示注入前后对照;真接口模式(traffic.py)只更新
//                    环境上下文 / 因素状态、**不重算判级 / CI**,面板如实显示「已注入 + 折算因素」;
//   ④ **输出**   —— 系统建议(承接段 / 比例 / 预期 / why)+ 预测三档。
//
// ⚠️ 口径铁律(违反即不通过):
//   ① 面板上每个数字都带单位或口径标注,取不到一律「—」,**绝不编造**;
//   ② 「处理过程」是**演示口径的演算展示**(阈值档位来自接口 /thresholds,不是前端自造),
//      不得说成"模型推理";真接口模式的判级来自上游链路 level 字段,接口层不重算(原样透传);
//   ③ CI 只用于展示与辅助排序,**不得作为判级依据**(手册 §6.5 第 1 条),冲突以四项指标为准;
//   ④ 全部 is_simulated = true。
import { computed } from 'vue'
import LevelBadge from '../../dashboard/components/LevelBadge.vue'
import FactorBreakdown from '../../dashboard/components/FactorBreakdown.vue'
import ScenarioInjectPanel from './ScenarioInjectPanel.vue'
import {
  ciAvailable,
  UNAVAILABLE,
  type CongestionLevel,
  type FactorApplied,
  type SegmentRecord,
  type ThresholdSnapshot,
  type TrafficContext,
} from '../../../shared/traffic'
import type { DiversionSuggestion } from '../../../shared/demoDecision'
import { USE_MOCK } from '../../../shared/env'

const props = defineProps<{
  record: SegmentRecord | null
  name: string
  factors: (FactorApplied & { segment_id: string })[]
  ctx: TrafficContext | null
  thresholds: ThresholdSnapshot | null
  suggestion: DiversionSuggestion | null
  presets: { key: string; name: string; note: string; factor_ids: string[] }[]
}>()

const emit = defineEmits<{ (e: 'changed'): void }>()

function fmt(v: number | undefined | null, digits = 2): string {
  return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—'
}

/** 环境上下文一行:真接口模式没有天气观测量 → 缺项一律「—」,不显示 "null℃ / 空单位" */
const weatherLine = computed<string>(() => {
  const weather = props.ctx?.weather
  if (!weather) return '—'
  const parts = [weather.condition ?? '天气未接入']
  if (typeof weather.temp_c === 'number') parts.push(`${weather.temp_c}℃`)
  if (typeof weather.visibility_km === 'number') parts.push(`能见度 ${weather.visibility_km} km`)
  return parts.join(' · ')
})

/** 站点包是否给该路段预置了分流建议(base_pct > 0);未预置时比例仍可人工设置,不伪造建议 */
const hasSuggestion = computed<boolean>(() => (props.suggestion?.base_pct ?? 0) > 0)

// ---------- ① 输入:全部指标 ----------
interface InRow {
  k: string
  v: string
  note?: string
}

const inputRows = computed<InRow[]>(() => {
  const r = props.record
  if (!r) return []
  return [
    { k: '流量 q', v: `${fmt(r.q_vph, 0)} 辆/h` },
    { k: '车速 v', v: `${fmt(r.v_kmh, 1)} km/h` },
    { k: '畅通速度 v_f', v: `${fmt(r.v_f_kmh, 1)} km/h` },
    // 密度直接用快照给的 `k_vpk`:本面板的口径是"把快照原样摆出来",不自己按 q / v 反算
    // (独立审查 Sourcery 提出:反算值会与快照 / 大屏上的 k 不一致,同一个字段两处两个数)
    { k: '密度 k', v: `${fmt(r.k_vpk, 1)} 辆/km` },
    { k: '排队长度 L_q', v: `${fmt(r.L_q_m, 0)} m` },
    { k: '路段长度 L_seg', v: `${fmt(r.L_seg_m, 0)} m` },
    { k: '消散时间 T_d', v: `${fmt(r.T_d_min, 1)} min` },
    { k: '通行能力 c', v: `${fmt(r.c_vph, 0)} 辆/h`, note: capacityNote(r) },
    { k: '饱和度 x', v: fmt(r.x) },
    { k: '检测置信度', v: fmt(r.confidence) },
    { k: '数据年龄', v: `${r.data_age_s ?? '—'} s`, note: '> 120 s 判陈旧(TC-11)' },
    { k: '来源', v: r.source },
  ]
})

// ---------- ② 处理过程:四项指标并列落档(与 work/perception/level.py 同口径) ----------
//
// 为什么要把四项都摆出来,而不是只对比 x:
//   判级本体 work/perception/level.py 的 four_metrics_level() 口径是「四项各按自己的边界算档,
//   **取最高档、不做平均**」—— 于是「x 落在 1 档」与「判级 4 档」可以同时成立,顶上去的是别的指标。
//   原面板只画 x 一条轨迹,屏幕上就出现「落在 1 档」下一行「严重拥堵」的自相矛盾(演示时会被当场追问);
//   四项并列 + 高亮「判级依据」那一项,这条口径不用解释就自证了。
//   本块**只做演算展示**:判级结果仍原样取快照的 level 字段,不改判级(接口层也不重算)。

/** 面板固定的四项 = stations/thresholds.json 的 grading.level_bounds(x / v / L_q / T_d) */
interface MetricSpec {
  /** 与 level_bounds 的 indicator 同名,便于与阈值表对读 */
  key: 'x' | 'v' | 'L_q' | 'T_d'
  /** 面板展示名(带指标符号) */
  name: string
  /** 摘要里用的短名(如「x 仅 1 档」) */
  short: string
  /** 快照字段名 —— 只作口径标注(格子里 hover 可见),真取值走 valueOf() */
  field: string
  /** 阈值行文案关键词:mock 侧与真接口的 metric 文案不同(「速度 v」/「速度比 v/v_f」),
   *  按关键词认行;认不到就是「未加载」,绝不拿别的指标的边界顶替 */
  match: string[]
  digits: number
}

const METRIC_SPECS: MetricSpec[] = [
  { key: 'x', name: '饱和度 x', short: 'x', field: 'x', match: ['饱和度'], digits: 2 },
  { key: 'v', name: '速度 v', short: 'v', field: 'v_kmh', match: ['速度'], digits: 1 },
  { key: 'L_q', name: '排队长度 L_q', short: 'L_q', field: 'L_q_m', match: ['排队'], digits: 0 },
  { key: 'T_d', name: '消散时间 T_d', short: 'T_d', field: 'T_d_min', match: ['消散', 'T_d'], digits: 1 },
]

/** 一条阈值行的可判读形式:接口只给 level + max,档位方向要靠边界之间的大小关系自己认 */
interface BandInfo {
  /** 三个真实边界(接口第 4 档是哨兵 999 不是边界,已剔除) */
  bounds: number[]
  /** true = 升序(越大越堵:x / L_q / T_d);false = 降序(越小越堵:v 速度) */
  ascending: boolean
  unit: string
  /** true = 该行阈值是比值口径(mock 侧的「速度比 v/v_f」/「排队比 L_q/L_seg」) */
  ratio: boolean
}

function bandInfoOf(spec: MetricSpec): BandInfo | null {
  const rows = props.thresholds?.rows ?? []
  const row = rows.find((r) => spec.match.some((kw) => r.metric.includes(kw)))
  if (!row) return null
  const bounds = row.bands.filter((b) => b.level <= 3).map((b) => b.max)
  // 边界不足 3 个 = 接口不符合契约(work/assembly/traffic.py 的 build_thresholds 对 len(bounds) < 3 直接跳过),
  // 前端不补数、不猜,按「未加载」处理
  if (bounds.length < 3) return null
  const ratio = row.metric.includes('比')
  return {
    bounds,
    ascending: (bounds[0] as number) < (bounds[bounds.length - 1] as number),
    unit: ratio ? '' : row.unit,
    ratio,
  }
}

/** 数值除法(取不到 / 除零给 null);ratio() 也走它,保证「—」的口径只有一处 */
function divOrNull(a?: number, b?: number): number | null {
  if (typeof a !== 'number' || typeof b !== 'number' || !Number.isFinite(a) || !Number.isFinite(b) || b === 0) {
    return null
  }
  return a / b
}

/**
 * 该指标的当前值 —— 口径必须与阈值行一致:
 * 真接口的阈值行是**原始量**(v 为 km/h、L_q 为 m),mock 侧可能有**比值**行(v/v_f、L_q/L_seg),
 * 拿 km/h 去比无量纲边界会算出一个假档位,所以比值行按比值取值。
 */
function valueOf(spec: MetricSpec, band: BandInfo | null): number | null {
  const r = props.record
  if (!r) return null
  if (band?.ratio) {
    if (spec.key === 'v') return divOrNull(r.v_kmh, r.v_f_kmh)
    if (spec.key === 'L_q') return divOrNull(r.L_q_m, r.L_seg_m)
  }
  switch (spec.key) {
    case 'x':
      return typeof r.x === 'number' && Number.isFinite(r.x) ? r.x : null
    case 'v':
      return typeof r.v_kmh === 'number' && Number.isFinite(r.v_kmh) ? r.v_kmh : null
    case 'L_q':
      return typeof r.L_q_m === 'number' && Number.isFinite(r.L_q_m) ? r.L_q_m : null
    case 'T_d':
      return typeof r.T_d_min === 'number' && Number.isFinite(r.T_d_min) ? r.T_d_min : null
  }
}

/**
 * 单项落档:照抄 work/perception/level.py 的 `_indicator_level()`。
 * 升序边界(越大越堵) → 数「value >= 边界」的个数;降序边界(越小越堵,只有 v 速度) → 数「value < 边界」的个数;
 * 档位 = 1 + 命中数,封顶 4 档。
 * ⚠️ 降序必须用 `<` 而不是 `<=`:用反了 v 越小档位反而越低,与判级本体正好相反 —— 演示时一眼能看出算错。
 */
function indicatorLevel(value: number, bounds: number[]): CongestionLevel {
  const ascending = (bounds[0] as number) < (bounds[bounds.length - 1] as number)
  const hits = bounds.filter((b) => (ascending ? value >= b : value < b)).length
  return Math.min(4, 1 + hits) as CongestionLevel
}

/** 四档判定条件的展示文案(顺序即接口的档位顺序;升序档读作"上界",降序档读作"下界") */
function boundsTextOf(band: BandInfo, digits: number): string {
  const b = band.bounds
  const parts = band.ascending
    ? [`< ${fmt(b[0], digits)}`, `< ${fmt(b[1], digits)}`, `< ${fmt(b[2], digits)}`, `≥ ${fmt(b[2], digits)}`]
    : [`≥ ${fmt(b[0], digits)}`, `< ${fmt(b[0], digits)}`, `< ${fmt(b[1], digits)}`, `< ${fmt(b[2], digits)}`]
  const unit = band.unit ? ` ${band.unit}` : ''
  const note = band.ratio ? '(比值口径)' : ''
  return `四档边界 ${parts.join(' / ')}${unit}${note}`
}

/**
 * 「判级依据」那一项距下一档边界还差多少 —— 升序档越过上界即进下一档,降序档跌破下界才进下一档,
 * 两种方向的余量算反了会显示成「还差 -0.3」,演示时会被当场抓到;已在 4 档时反过来给"越过开口边界多少"。
 */
function marginTextOf(value: number, band: BandInfo, level: CongestionLevel, digits: number): string {
  const b = band.bounds
  const last = b[b.length - 1] as number
  const unit = band.unit ? ` ${band.unit}` : ''
  if (level >= 4) {
    const over = band.ascending ? value - last : last - value
    return `已越过 4 档开口边界 ${fmt(last, digits)}${unit}(${band.ascending ? '高出' : '低于'} ${fmt(over, digits)})`
  }
  const bound = b[level - 1] as number
  const gap = band.ascending ? bound - value : value - bound
  const next = b[level]
  const label = band.ascending ? '上界' : '下界'
  return `距本档${label} ${fmt(bound, digits)} 还差 ${fmt(gap, digits)} · 下一档 ${(level + 1) as CongestionLevel} 档${label} ${fmt(next, digits)}`
}

interface MetricView {
  key: string
  name: string
  short: string
  /** 快照字段名(格子上 hover 可查,证明值不是前端编的) */
  field: string
  /** 当前值展示文本(带单位;比值口径不带) */
  valueText: string
  /** 四档边界文案;阈值未取到 = null(显示「边界未加载」) */
  boundsText: string | null
  /** 落档;阈值或当前值缺失 = null */
  level: CongestionLevel | null
  /** 是否判级依据(达到最高档的那一项) */
  focused: boolean
  /** 只有判级依据那一项给余量文案,其余项不显示(四列都写余量反而看不清哪项是依据) */
  marginText: string | null
}

const metricViews = computed<MetricView[]>(() => {
  const rows = METRIC_SPECS.map((spec) => {
    const band = bandInfoOf(spec)
    const value = valueOf(spec, band)
    return { spec, band, value, level: band && value !== null ? indicatorLevel(value, band.bounds) : null }
  })
  // 判级口径 = 四项取最高(不做平均):达到最高档的项都是"判级依据",并列时一并高亮
  let best: CongestionLevel | null = null
  for (const row of rows) {
    if (row.level !== null && (best === null || row.level > best)) best = row.level
  }
  return rows.map(({ spec, band, value, level }) => {
    const focused = best !== null && level === best
    const unit = band && !band.ratio && band.unit ? ` ${band.unit}` : ''
    return {
      key: spec.key,
      name: spec.name,
      short: spec.short,
      field: spec.field,
      valueText: value === null ? '—' : `${fmt(value, spec.digits)}${unit}`,
      boundsText: band ? boundsTextOf(band, spec.digits) : null,
      level,
      focused,
      marginText: focused && band && value !== null && level !== null ? marginTextOf(value, band, level, spec.digits) : null,
    }
  })
})

/** 至少有一项能落档才谈"演算";全取不到就沿用「阈值未取到」空态,不摆四列空壳 */
const metricsReady = computed<boolean>(() => metricViews.value.some((m) => m.boundsText !== null))

/** 四项里最高的那一档(取最差项);阈值未取到 = null */
const bestLevel = computed<CongestionLevel | null>(() => {
  let best: CongestionLevel | null = null
  for (const m of metricViews.value) {
    if (m.level !== null && (best === null || m.level > best)) best = m.level
  }
  return best
})

/** 判级依据(达到最高档的指标短名),并列时一并列出 */
const focusNames = computed<string>(() => metricViews.value.filter((m) => m.focused).map((m) => m.short).join('、'))

/** 其余各项的一句话摘要,如「x 1 档 · L_q 2 档」 —— 让「x 只 1 档却判 4 档」这个反直觉点自己讲清楚 */
const othersText = computed<string>(() =>
  metricViews.value
    .filter((m) => !m.focused && m.level !== null)
    .map((m) => `${m.short} ${m.level} 档`)
    .join(' · '),
)

/** 判级依据那一项(并列时取第一项显示余量,不把四列都写成"还差多少") */
const focusMetric = computed<MetricView | null>(() => metricViews.value.find((m) => m.marginText !== null) ?? null)

/** 快照等级是否落在四级内(0 = 上游未判级 / 数据不可用,TC-11 灰档,不参与档位文案) */
const levelKnown = computed<boolean>(() => {
  const lv = props.record?.level
  return typeof lv === 'number' && lv >= 1 && lv <= 4
})

/**
 * 四项取最高 ≠ 快照等级时如实说明差在哪:上游判级还可能被①硬触发(F07/F08 直接给 hard_trigger_level)、
 * ②因素修正后回灌(容量折减 → x 变)、③降档防抖(降档需连续 N 个周期)改写。
 * 面板只展示演算,不因为对不上就改判级,也不把口径差异藏起来。
 */
const mismatchNote = computed<string>(() => {
  const snap = props.record?.level
  if (bestLevel.value === null || !levelKnown.value || typeof snap !== 'number') return ''
  if (snap === bestLevel.value) return ''
  return `四项取最高 ${bestLevel.value} 档、快照等级 ${snap} 档:上游判级还会被硬触发(F07/F08)、因素修正后回灌、降档防抖(降档需连续 N 个周期)改写,本面板只展示演算过程,不改判级。`
})

/** 因素对通行能力 / 需求 / 置信度的合成折减(与 mock 同口径:相乘) */
const factorEffect = computed(() => {
  let c = 1
  let q = 1
  let conf = 1
  for (const f of props.factors) {
    if (f.target === 'demand') q *= f.multiplier
    else if (f.target === 'confidence') conf *= f.multiplier
    else c *= f.multiplier
  }
  return { c, q, conf, count: props.factors.length }
})

/** 运营阶段的容量系数(孪生侧 capacity.py 标定;缺省 1 = 未标定) */
const phaseFactor = computed(() => {
  const v = props.record?.capacity_phase_factor
  return typeof v === 'number' && v > 0 ? v : 1
})
const phaseLabel = computed(() => {
  const p = props.record?.capacity_phase
  return typeof p === 'string' ? p : ''
})

/** CI 四项加权构成 */
const weights = computed(() => props.thresholds?.ci_weights ?? [])
const ciValue = computed(() => {
  const r = props.record
  return r && ciAvailable(r) ? (r.ci as number).toFixed(1) : UNAVAILABLE.name
})

function ratio(a?: number, b?: number): string {
  const q = divOrNull(a, b)
  return q === null ? '—' : q.toFixed(2)
}

/** 通行能力的基准说明:路型基线 × 运营阶段系数(缺阶段字段时退回旧口径) */
function capacityNote(r: typeof props.record): string | undefined {
  if (!r) return undefined
  const base = r.c_base_vph
  if (typeof base !== 'number') return undefined
  const f = r.capacity_phase_factor
  const phase = r.capacity_phase
  if (typeof f === 'number' && f > 0 && phase) {
    return `路型基线 ${fmt(base, 0)} 辆/h × 阶段 ${fmt(f, 2)}(${phase})`
  }
  return `基准 ${fmt(base, 0)} 辆/h`
}

function metricValue(key: string): string {
  const r = props.record
  if (!r) return '—'
  switch (key) {
    case 'x':
      return typeof r.x === 'number' ? String(r.x) : '—'
    case 'v':
      return ratio(r.v_kmh, r.v_f_kmh)
    case 'k':
      return ratio(r.L_q_m, r.L_seg_m)
    case 'T_d':
      return typeof r.T_d_min === 'number' ? String(r.T_d_min) : '—'
    default:
      return '—'
  }
}

</script>

<template>
  <div class="flow">
    <p v-if="!record" class="empty">← 先在「处置队列」里选一条告警,或在大屏选一个路段,再回到本视图看决策链路</p>

    <template v-else>
      <!-- ① 输入 -->
      <section class="td-card">
        <div class="td-card-head">
          ① 输入 · 判级与决策吃进去的全部数据
          <span class="td-head-tag td-mono">{{ record.segment_id }} {{ name }}</span>
        </div>
        <div class="td-card-body">
          <div class="in-grid">
            <div v-for="r in inputRows" :key="r.k" class="in-cell">
              <span class="in-k">{{ r.k }}</span>
              <span class="in-v td-num">{{ r.v }}</span>
              <span v-if="r.note" class="in-note">{{ r.note }}</span>
            </div>
          </div>

          <div class="sec-head">
            生效因素<span class="sub-tag">{{ factors.length }} 项</span>
          </div>
          <FactorBreakdown :factors="factors" />

          <div class="sec-head">环境上下文(演示数据(模拟))</div>
          <div v-if="ctx" class="ctx-line">
            {{ weatherLine }}
            <span class="sep">|</span>{{ ctx.time.clock }} · {{ ctx.time.session }} · {{ ctx.time.calendar }}
            <span class="sep">|</span>{{ ctx.injected ? '已按演示场景注入' : (ctx.scenario ? '未注入(无环境数据源)' : '站点包默认环境') }}
          </div>
          <p v-else class="empty sm">环境上下文未取到</p>
        </div>
      </section>

      <!-- ② 处理过程 -->
      <section class="td-card">
        <div class="td-card-head">
          ② 处理过程 · 判级演算(演示口径,阈值来自接口)
          <span class="td-head-tag">{{ USE_MOCK ? '非模型推理 · level.py 未实现' : '接口层不重算判级 · 快照原样展示' }}</span>
        </div>
        <div class="td-card-body">
          <!-- 步骤 1:因素折减 -->
          <div class="step">
            <span class="step-no">1</span>
            <div class="step-body">
              <div class="step-title">因素加权 · 通行能力折减</div>
              <div class="step-line td-num">
                c = c_base {{ fmt(record.c_base_vph, 0) }}
                <template v-if="phaseLabel">
                  × 阶段 {{ fmt(phaseFactor, 2) }}<span class="phase-tag">{{ phaseLabel }}</span>
                </template>
                × 因素 {{ fmt(factorEffect.c, 2) }} = <b>{{ fmt(record.c_vph, 0) }}</b> 辆/h
                <span class="sep">|</span>需求 q × {{ fmt(factorEffect.q, 2) }}
                <span class="sep">|</span>置信度 × {{ fmt(factorEffect.conf, 2) }}
              </div>
              <div class="step-note">
                容量三段式:c_base(路型基数 × 每方向车道数) → × 运营阶段系数 → × 多因素相乘修正;
                手册第 19 章:多因素**相乘**修正通行能力与畅通速度,合成后不低于原值 40%【待标定】
              </div>
            </div>
          </div>

          <!-- 步骤 2:x = q / c -->
          <div class="step">
            <span class="step-no">2</span>
            <div class="step-body">
              <div class="step-title">饱和度</div>
              <div class="step-line td-num">
                x = q / c = {{ fmt(record.q_vph, 0) }} / {{ fmt(record.c_vph, 0) }} = <b>{{ fmt(record.x) }}</b>
              </div>
            </div>
          </div>

          <!-- 步骤 3:四项指标并列落档 → 取四项最高(不做平均) -->
          <div class="step">
            <span class="step-no">3</span>
            <div class="step-body">
              <div class="step-title">四档阈值比对 → 判级(四项各按自己的边界落档,取最高,不做平均)</div>
              <template v-if="metricsReady">
                <!-- 四项并列:判级依据那一项描边高亮,其余压淡 —— 让"x 只 1 档却判 4 档"在第一眼就有解释 -->
                <div class="band-grid">
                  <div
                    v-for="m in metricViews"
                    :key="m.key"
                    class="band-cell"
                    :class="{ focus: m.focused, dim: !m.focused }"
                  >
                    <div class="band-cell-h">
                      <span class="band-cell-name">{{ m.name }}</span>
                      <LevelBadge v-if="m.level !== null" :level="m.level" :name="`${m.level} 档`" />
                      <span v-else class="band-cell-none">未判档</span>
                    </div>
                    <div class="band-cell-v td-num" :title="`快照字段 ${m.field}`">{{ m.valueText }}</div>
                    <div class="band-cell-b td-mono">{{ m.boundsText ?? '边界未加载' }}</div>
                    <div v-if="m.focused" class="basis-tag">判级依据</div>
                  </div>
                </div>

                <div class="step-line">
                  判级结果:
                  <LevelBadge :level="record.level" />
                  <template v-if="levelKnown">({{ record.level }} 档)</template>
                  <template v-if="bestLevel !== null">
                    <span class="sep">·</span>取四项最高:
                    <b>{{ focusNames }} → {{ bestLevel }} 档</b>
                    <template v-if="othersText">
                      <span class="sep">·</span>{{ othersText }}
                    </template>
                  </template>
                  <span class="sep">·</span>接口快照给的等级为 {{ record.level
                  }}{{ USE_MOCK ? '(站点包预置,判级模型未落地)' : '(判级来自上游链路 level 字段,接口层不重算)' }}
                </div>

                <!-- 原有信息量不丢:判级依据那一项距下一档边界还差多少(只对它显示) -->
                <div v-if="focusMetric" class="step-line">
                  判级依据 <b>{{ focusMetric.name }}</b>:
                  <span class="td-num">{{ focusMetric.valueText }}</span>
                  <span class="sep">·</span>{{ focusMetric.marginText }}
                </div>

                <div v-if="mismatchNote" class="step-line note-warn">{{ mismatchNote }}</div>

                <div class="step-note">
                  口径:边界取自接口 /thresholds 的 grading.level_bounds(不写死);升序档(饱和度 x / 排队长度 L_q /
                  消散时间 T_d,越大越堵)按「值 ≥ 边界」计数,降序档(速度 v,越小越堵)按「值 &lt; 边界」计数,
                  档位 = 1 + 命中数(封顶 4 档),与 level.py 的 four_metrics_level / _indicator_level 一致;
                  四项各算各的档再取最高,不做平均(取最差项)。
                </div>
              </template>
              <p v-else class="empty sm">阈值档位未取到(/thresholds 未起),不做档位演算</p>
            </div>
          </div>

          <!-- 步骤 4:CI 构成 -->
          <div class="step">
            <span class="step-no">4</span>
            <div class="step-body">
              <div class="step-title">拥挤指数 CI 构成(只展示,不判级)</div>
              <div class="ci-line">
                <span class="ci-big td-num" :style="{ color: ciAvailable(record) ? undefined : UNAVAILABLE.color }">
                  {{ ciValue }}
                </span>
                <span class="ci-formula td-mono">
                  <template v-if="weights.length > 0">
                    {{ weights.map((w) => `${w.label} ${metricValue(w.key)}×${w.weight.toFixed(2)}`).join(' + ') }}
                  </template>
                  <template v-else>权重加载中…</template>
                </span>
              </div>
              <div class="step-note">CI 只用于热力展示与辅助排序,不得作为判级依据(手册 §6.5 第 1 条)</div>
            </div>
          </div>
        </div>
      </section>

      <!-- ③ 可调控 -->
      <section class="td-card">
        <div class="td-card-head">
          {{ USE_MOCK ? '③ 可调控 · 改任一项,服务端重算判级 / CI / 建议 / 预测' : '③ 可调控 · 改任一项只更新环境上下文 / 因素状态（判级由感知层统一重算）' }}
        </div>
        <div class="td-card-body">
          <ScenarioInjectPanel :ctx="ctx" :segment-id="record.segment_id" :presets="presets" @changed="emit('changed')" />
          <p class="note">
            另两个调控口子在「处置队列」视图:人工置位(F07 / F08 / F11,事件侧)与分流比例滑杆(下发时用)。
          </p>
        </div>
      </section>

      <!-- ④ 输出 -->
      <section class="td-card">
        <div class="td-card-head">④ 输出 · 系统建议与预测</div>
        <div class="td-card-body">
          <template v-if="suggestion && hasSuggestion">
            <div class="out-line">
              建议分流至 <b>{{ suggestion.target_name }}</b>({{ suggestion.target_segment_id }})
              <span class="sep">·</span>基准比例 <b>{{ suggestion.base_pct }}%</b>
              (可调 {{ suggestion.min_pct }}–{{ suggestion.max_pct }}%)
              <span class="sep">·</span>预期 {{ suggestion.expect }}
            </div>
            <p class="why">{{ suggestion.why }}</p>
          </template>
          <p v-else class="empty sm">
            本路段暂无系统预置分流建议(站点包未预置) —— 分流比例可在「处置队列」人工设置;这不是"不需要分流"的结论。
          </p>

          <!-- Issue IKP5CE：输出侧补一行路线引用；完整链路在「路线规划」视图，本面板不重复算 -->
          <div class="sec-head">路线<span class="sub-tag">见「路线规划」视图</span></div>
          <p class="out-line">
            完整路线（起点 → 落客 → 终点 → 离站）与一主二备在页头「路线规划」视图；
            读引擎算路产物，本页不重算。场景注入 / 人工置位不会让路线变化（引擎产物不随参数变化）。
          </p>

          <div class="sec-head">未来 15 / 30 分钟预测<span class="sub-tag">L0 · 不报精度</span></div>
          <div v-if="record.pred" class="pred-grid">
            <div class="pred-box">
              <div class="pred-h">+15 min</div>
              <div class="pred-v td-num">{{ record.pred.h15.q_vph }} 辆/h</div>
              <LevelBadge :level="record.pred.h15.level" />
            </div>
            <div class="pred-box">
              <div class="pred-h">+30 min</div>
              <div class="pred-v td-num">{{ record.pred.h30.q_vph }} 辆/h</div>
              <LevelBadge :level="record.pred.h30.level" />
            </div>
          </div>
          <p v-else class="empty sm">本路段无预测</p>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.flow {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.empty {
  margin: 8px 2px;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}
.empty.sm {
  font-size: 11px;
}

/* ① 输入网格 */
.in-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 6px 14px;
}
.in-cell {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12px;
}
.in-k {
  color: var(--td-text-color-secondary);
  white-space: nowrap;
}
.in-v {
  color: var(--td-text-color-primary);
}
.in-note {
  font-size: 10px;
  color: var(--td-text-color-placeholder);
}
.ctx-line {
  font-size: 12px;
  color: var(--td-text-color-primary);
  line-height: 1.8;
}
.sep {
  margin: 0 4px;
  color: var(--td-text-color-placeholder);
}
/* 运营阶段标签:紧贴阶段系数,证明容量随阶段变化 */
.phase-tag {
  display: inline-block;
  margin: 0 2px 0 3px;
  padding: 0 4px;
  border-radius: 3px;
  background: var(--td-brand-color-light);
  color: var(--td-brand-color);
  font-size: 10px;
  line-height: 14px;
  vertical-align: 1px;
}

/* ② 处理过程步骤 */
.step {
  display: flex;
  gap: 10px;
  padding: 9px 0;
  border-bottom: 1px dashed var(--td-component-stroke);
}
.step:last-child {
  border-bottom: none;
}
.step-no {
  flex: 0 0 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--td-brand-color-1);
  color: var(--td-brand-color);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
}
.step-body {
  flex: 1;
  min-width: 0;
}
.step-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-primary);
  margin-bottom: 4px;
}
.step-line {
  font-size: 12px;
  line-height: 1.8;
  color: var(--td-text-color-primary);
}
.step-note {
  margin-top: 3px;
  font-size: 10px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder);
}
/* 四档阈值格(四项并列):档位色由 LevelBadge 承担,这里只做布局 + 「判级依据」的描边高亮 */
.band-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
  margin-bottom: 6px;
}
.band-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding: 5px 7px;
  border: 1px solid var(--td-component-stroke);
  border-radius: var(--td-radius-sm);
  background: var(--td-bg-color-secondarycontainer);
}
/* 判级依据:品牌色描边 + 品牌色浅底(与步骤序号的色轴一致,不引入第二套强调色) */
.band-cell.focus {
  border-color: var(--td-brand-color);
  background: var(--td-brand-color-1);
}
/* 非依据项压淡:一眼看上去就知道等级是被哪一项顶上去的 */
.band-cell.dim {
  opacity: 0.62;
}
.band-cell-h {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-width: 0;
}
.band-cell-name {
  min-width: 0;
  overflow: hidden;
  font-size: 11px;
  color: var(--td-text-color-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.band-cell-v {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.2;
  color: var(--td-text-color-primary);
}
.band-cell-b {
  font-size: 10px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder);
  word-break: break-word;
}
.band-cell-none {
  font-size: 10px;
  color: var(--td-text-color-placeholder);
  white-space: nowrap;
}
.basis-tag {
  align-self: flex-start;
  margin-top: 2px;
  padding: 0 4px;
  border-radius: var(--td-radius-sm);
  background: var(--td-brand-color);
  color: var(--td-text-color-anti);
  font-size: 10px;
  line-height: 15px;
}
/* 口径差异如实提示:沿用决策页既有的警告色,不新造色值 */
.note-warn {
  color: #a06a00;
}
/* CI */
.ci-line {
  display: flex;
  align-items: baseline;
  gap: 12px;
}
.ci-big {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.1;
}
.ci-formula {
  flex: 1;
  min-width: 0;
  font-size: 11px;
  color: var(--td-text-color-secondary);
  word-break: break-word;
}

/* ③ */
.note {
  margin: 8px 0 0;
  font-size: 11px;
  line-height: 1.6;
  color: var(--td-text-color-placeholder);
}

/* ④ */
.out-line {
  font-size: 12px;
  line-height: 1.8;
  color: var(--td-text-color-primary);
}
.why {
  margin: 6px 0 0;
  font-size: 11px;
  line-height: 1.7;
  color: var(--td-text-color-secondary);
}
.sec-head {
  margin: 12px 0 6px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}
.sub-tag {
  margin-left: auto;
  font-size: 10px;
  font-weight: 400;
  color: var(--td-text-color-placeholder);
}
.pred-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.pred-box {
  padding: 8px 10px;
  border: 1px solid var(--td-component-stroke);
  border-radius: var(--td-radius-sm);
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.pred-h {
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.pred-v {
  font-size: 16px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

/* ---------- 响应式（Issue IKP3EV） ---------- */
/* ≤1180:单列时面板占满整宽,卡片之间保持 8px 间距(与页内其它卡片一致);
   步骤体上裁掉横向溢出:四项格子的边界文案在窄栏里可能顶到边,
   单列后列内不再裁剪 → 保留这道裁切,避免整页出现横向滚动条(格子本身仍在栏内)。 */
@media (max-width: 1180px) {
  .flow {
    gap: 8px;
  }
  .step-body {
    overflow-x: clip;
  }
}
/* ≤900:卡片内边距 / 步骤间距压缩,首屏信息密度提升 */
@media (max-width: 900px) {
  .td-card-body {
    padding: 8px 10px;
  }
  .step {
    gap: 8px;
    padding: 7px 0;
  }
  .ci-big {
    font-size: 22px;
  }
  .td-card-head {
    flex-wrap: wrap;
    gap: 4px 8px;
  }
}
/* ≤768:输入网格从 auto-fill(150px)降为固定 2 列,避免窄屏出现半列空档 */
@media (max-width: 768px) {
  .in-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 6px 10px;
  }
  .pred-grid {
    gap: 6px;
  }
  /* 四项阈值格子 4 列 → 2 列:窄屏一列放四个会把边界文案压成两三个字一行 */
  .band-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
/* ≤560:单列输入网格;四项阈值格子保持 2 列并压缩内边距 / CI 公式折行,不撑破页面 */
@media (max-width: 560px) {
  .in-grid {
    grid-template-columns: 1fr;
  }
  .ci-line {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  .ci-big {
    font-size: 20px;
  }
  .band-cell {
    padding: 4px 5px;
  }
  .band-cell-v {
    font-size: 13px;
  }
  .step-no {
    flex: 0 0 18px;
    height: 18px;
  }
  .sec-head {
    margin: 10px 0 5px;
    font-size: 11px;
  }
  .pred-v {
    font-size: 15px;
  }
}
</style>
