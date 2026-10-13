<script setup lang="ts">
// 决策可视化(Issue #77 三页收敛 · 决策层第二层的新视图)。
//
// 业主口径:「决策层我要看见**全部数据**和**处理数据的结果**,还有**可调控的全部可视化过程**,
// 差不多就是决策判断的可视化演示」。本面板按四段摆开:
//   ① **输入**   —— 选中路段的全部指标 + 生效因素 + 环境上下文(判级与决策实际吃进去的东西);
//   ② **处理过程** —— x = q_vph / c_vph 的逐步演算 → 四档阈值对比(当前值落在哪档、离边界多远)→ level;
//                    因素加权 → 通行能力折减 → x 前后对照;CI 四项加权构成;
//   ③ **可调控** —— 场景注入(环境侧)+ 人工置位(事件侧,在处置队列视图)+ 分流比例(在处置工作台),
//                    任一变动由服务端重算,本面板显示注入前后对照;
//   ④ **输出**   —— 系统建议(承接段 / 比例 / 预期 / why)+ 预测三档。
//
// ⚠️ 口径铁律(违反即不通过):
//   ① 面板上每个数字都带单位或口径标注,取不到一律「—」,**绝不编造**;
//   ② 「处理过程」是**演示口径的演算展示**(阈值档位来自接口 /thresholds,不是前端自造),
//      不得说成"模型推理";一期无真实判级模型(level.py 未实现,站点包给预置等级);
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
    { k: '通行能力 c', v: `${fmt(r.c_vph, 0)} 辆/h`, note: r.c_base_vph !== undefined ? `基准 ${r.c_base_vph} 辆/h` : undefined },
    { k: '饱和度 x', v: fmt(r.x) },
    { k: '检测置信度', v: fmt(r.confidence) },
    { k: '数据年龄', v: `${r.data_age_s ?? '—'} s`, note: '> 120 s 判陈旧(TC-11)' },
    { k: '来源', v: r.source },
  ]
})

// ---------- ② 处理过程:x = q / c 与四档阈值 ----------
/** 饱和度阈值档(来自 /thresholds;取不到用契约口径的演示值并注明) */
const xBands = computed(() => {
  const row = props.thresholds?.rows.find((r) => r.metric.includes('饱和度') || r.metric === 'x')
  return row?.bands ?? []
})

const xValue = computed(() => (typeof props.record?.x === 'number' ? props.record.x : null))

/** 当前 x 落在哪一档 + 离下一档边界多远(展示口径的演算,不是模型) */
const xAnalysis = computed(() => {
  const x = xValue.value
  const bands = xBands.value
  if (x === null || bands.length === 0) return null
  const hit = bands.find((b) => x <= b.max) ?? bands[bands.length - 1]!
  const idx = bands.indexOf(hit)
  const next = bands[idx + 1]
  return {
    level: hit.level as CongestionLevel,
    upper: hit.max,
    /** 距本档上界(负数=已接近下一档) */
    margin: Number.isFinite(hit.max) ? hit.max - x : null,
    nextLevel: next?.level as CongestionLevel | undefined,
    nextBound: next?.max,
  }
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

/** 未折减的通行能力(从 c 反推;用于展示"折减前 → 折减后") */
const cBeforeFactors = computed(() => {
  const r = props.record
  if (!r || typeof r.c_vph !== 'number') return null
  const m = factorEffect.value.c
  return m > 0 ? r.c_vph / m : null
})

/** CI 四项加权构成 */
const weights = computed(() => props.thresholds?.ci_weights ?? [])
const ciValue = computed(() => {
  const r = props.record
  return r && ciAvailable(r) ? (r.ci as number).toFixed(1) : UNAVAILABLE.name
})

function ratio(a?: number, b?: number): string {
  if (typeof a !== 'number' || typeof b !== 'number' || !Number.isFinite(a) || !Number.isFinite(b) || b === 0) return '—'
  return (a / b).toFixed(2)
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

/** 档位条上的位置(0~100%) */
function bandPos(x: number, max: number): string {
  const top = Number.isFinite(max) && max > 0 ? max : 1
  return `${Math.min(100, Math.max(0, (x / top) * 100))}%`
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
            {{ ctx.weather.condition }} · {{ ctx.weather.temp_c }}℃ · 能见度 {{ ctx.weather.visibility_km }} km
            <span class="sep">|</span>{{ ctx.time.clock }} · {{ ctx.time.session }} · {{ ctx.time.calendar }}
            <span class="sep">|</span>{{ ctx.injected ? '已按演示场景注入' : '站点包默认环境' }}
          </div>
          <p v-else class="empty sm">环境上下文未取到</p>
        </div>
      </section>

      <!-- ② 处理过程 -->
      <section class="td-card">
        <div class="td-card-head">
          ② 处理过程 · 判级演算(演示口径,阈值来自接口)
          <span class="td-head-tag">非模型推理 · level.py 未实现</span>
        </div>
        <div class="td-card-body">
          <!-- 步骤 1:因素折减 -->
          <div class="step">
            <span class="step-no">1</span>
            <div class="step-body">
              <div class="step-title">因素加权 · 通行能力折减</div>
              <div class="step-line td-num">
                c = {{ fmt(cBeforeFactors, 0) }} × {{ fmt(factorEffect.c, 2) }} = <b>{{ fmt(record.c_vph, 0) }}</b> 辆/h
                <span class="sep">|</span>需求 q × {{ fmt(factorEffect.q, 2) }}
                <span class="sep">|</span>置信度 × {{ fmt(factorEffect.conf, 2) }}
              </div>
              <div class="step-note">
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

          <!-- 步骤 3:四档阈值对比 -->
          <div class="step">
            <span class="step-no">3</span>
            <div class="step-body">
              <div class="step-title">四档阈值对比 → 判级</div>
              <template v-if="xAnalysis && xValue !== null">
                <div class="band-track">
                  <span
                    v-for="b in xBands"
                    :key="b.level"
                    class="band-seg"
                    :class="{ hit: b.level === xAnalysis.level }"
                  >
                    {{ b.level }} 档 ≤ {{ Number.isFinite(b.max) ? b.max : '∞' }}
                  </span>
                </div>
                <div class="band-cursor" :style="{ left: bandPos(xValue, xAnalysis.upper) }" />
                <div class="step-line">
                  当前 x = <b class="td-num">{{ fmt(xValue) }}</b>
                  落在 <b>{{ xAnalysis.level }} 档</b>
                  <template v-if="xAnalysis.margin !== null">
                    <span class="sep">·</span>距本档上界 {{ xAnalysis.upper }} 还差
                    <b class="td-num">{{ fmt(xAnalysis.margin) }}</b>
                  </template>
                  <template v-if="xAnalysis.nextBound !== undefined">
                    <span class="sep">·</span>下一档 {{ xAnalysis.nextLevel }} 档上界 {{ xAnalysis.nextBound }}
                  </template>
                </div>
                <div class="step-line">
                  判级结果:
                  <LevelBadge :level="record.level" />
                  <span class="sep">·</span>接口快照给的等级为 {{ record.level }}(站点包预置,判级模型未落地)
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
          ③ 可调控 · 改任一项,服务端重算判级 / CI / 建议 / 预测
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
          <template v-if="suggestion">
            <div class="out-line">
              建议分流至 <b>{{ suggestion.target_name }}</b>({{ suggestion.target_segment_id }})
              <span class="sep">·</span>基准比例 <b>{{ suggestion.base_pct }}%</b>
              (可调 {{ suggestion.min_pct }}–{{ suggestion.max_pct }}%)
              <span class="sep">·</span>预期 {{ suggestion.expect }}
            </div>
            <p class="why">{{ suggestion.why }}</p>
          </template>
          <p v-else class="empty sm">本路段无系统建议模板(走站点包兜底)</p>

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
/* 四档阈值条 */
.band-track {
  position: relative;
  display: flex;
  gap: 2px;
  margin-bottom: 6px;
}
.band-seg {
  flex: 1;
  padding: 3px 0;
  text-align: center;
  font-size: 10px;
  color: var(--td-text-color-secondary);
  background: var(--td-bg-color-secondarycontainer);
  border-radius: var(--td-radius-sm);
}
.band-seg.hit {
  background: var(--td-brand-color-1);
  color: var(--td-brand-color);
  font-weight: 600;
}
.band-cursor {
  position: relative;
  height: 0;
}
.band-cursor::before {
  content: '▲';
  position: absolute;
  top: -8px;
  transform: translateX(-50%);
  font-size: 9px;
  color: var(--td-brand-color);
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
</style>
