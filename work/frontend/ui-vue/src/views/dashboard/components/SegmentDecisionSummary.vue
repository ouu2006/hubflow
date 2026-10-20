<script setup lang="ts">
// 大屏右栏 · 决策计算摘要（Issue IKMS18 大屏监控平台化）。
//
// 口径（硬约束）：
//   · **前端不重算判级**——level / level_name / triggered_by / CI / 因素全部原样展示接口快照；
//   · 四档阈值来自 `GET /api/traffic/thresholds`，只做「当前值 vs 四档边界」的**展示对照**，
//     不据此推导等级（判级唯一实现是 work/perception/level.py，接口层也不重算）；
//   · 输入指标缺字段一律「—」，不编造；无快照记录时如实写「该路段无运行指标」；
//   · 详细演算过程不在这里复制一份：给「查看完整决策过程 →」深链到决策页（带 segment 参数）。
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import LevelBadge from './LevelBadge.vue'
import {
  ciAvailable,
  CI_DISCLAIMER,
  type CongestionLevel,
  type FactorApplied,
  type SegmentRecord,
  type ThresholdSnapshot,
} from '../../../shared/traffic'

const props = defineProps<{
  segmentId: string
  record: SegmentRecord | null
  factors: (FactorApplied & { segment_id: string })[]
  thresholds: ThresholdSnapshot | null
  stale: boolean
}>()

function fmt(value: number | null | undefined, digits = 2): string {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—'
}

// ---------- ① 输入指标（接口快照原样） ----------
interface InputRow {
  key: string
  label: string
  value: string
}

const inputRows = computed<InputRow[]>(() => {
  const r = props.record
  return [
    { key: 'q', label: '流量 q', value: r ? `${fmt(r.q_vph, 0)} 辆/h` : '—' },
    { key: 'v', label: '车速 v', value: r ? `${fmt(r.v_kmh, 1)} km/h` : '—' },
    { key: 'k', label: '密度 k', value: r ? `${fmt(r.k_vpk, 1)} 辆/km` : '—' },
    { key: 'L_q', label: '排队 L_q', value: r ? `${fmt(r.L_q_m, 0)} m` : '—' },
    { key: 'x', label: '饱和度 x', value: r ? fmt(r.x) : '—' },
    { key: 'confidence', label: '置信度', value: r ? fmt(r.confidence) : '—' },
    { key: 'data_age', label: '数据年龄', value: r ? `${r.data_age_s ?? '—'} s` : '—' },
    { key: 'source', label: '来源', value: r?.source ?? '—' },
  ]
})

const dataAgeNote = computed<string>(() => {
  const age = props.record?.data_age_s
  if (!props.record) return '快照无该段记录 → 按「数据不可用」处理'
  if (typeof age !== 'number') return '数据年龄未知（缺字段）'
  return age > 120 ? `> 120 s 判陈旧（${age}s）` : '≤ 120 s（展示口径）'
})

const levelOf = computed<CongestionLevel | null>(() => {
  const level = props.record?.level
  return typeof level === 'number' && level >= 1 && level <= 4 ? (level as CongestionLevel) : null
})

const levelText = computed<string>(() => {
  if (!props.record) return '数据不可用（快照无该段记录）'
  if (!levelOf.value) return '数据不可用（上游未判级）'
  return props.record.level_name ?? '—'
})

const triggeredText = computed<string>(() => {
  const list = props.record?.triggered_by
  return Array.isArray(list) && list.length > 0 ? list.join(' / ') : '—'
})

const ciText = computed<string>(() => {
  const r = props.record
  return r && ciAvailable(r) ? (r.ci as number).toFixed(1) : '不可用'
})

// ---------- ② 四档阈值对照（展示用；不推导等级） ----------
// ⚠️ 阈值行的「当前值」口径随接口来源不同：
//   · traffic.py（真接口）阈值行是**原始量**（速度 v/km·h⁻¹、排队长度 L_q/m…），
//   · mock 侧阈值行有的是**比值**（速度比 v/v_f、排队比 L_q/L_seg）。
// 因此按标签识别口径，展示对应的当前值；不在这里判级，也不把比值与原始量混用。
interface CurrentValue {
  /** 用于画轨道位置的数值（口径与阈值行一致） */
  value: number | null
  /** 展示文本（不编造：取不到给「—」） */
  text: string
}

function numValue(value: number | null | undefined, unit = ''): CurrentValue {
  if (typeof value !== 'number' || !Number.isFinite(value)) return { value: null, text: '—' }
  return { value, text: `${fmt(value)}${unit ? ' ' + unit : ''}` }
}

function ratioValue(numerator: number | null | undefined, denominator: number | null | undefined): number | null {
  if (
    typeof numerator !== 'number' ||
    typeof denominator !== 'number' ||
    !Number.isFinite(numerator) ||
    !Number.isFinite(denominator) ||
    denominator === 0
  ) {
    return null
  }
  return numerator / denominator
}

/** 阈值行 label → 当前值（同时识别"原始量"与"比值"两种口径） */
function currentOfMetric(metric: string, unit: string): CurrentValue {
  const r = props.record
  if (!r) return { value: null, text: '—' }
  if (metric.includes('饱和度') || metric === 'x') return numValue(r.x)
  if (metric.includes('速度比') || metric.includes('v/v_f')) return numValue(ratioValue(r.v_kmh, r.v_f_kmh))
  if (metric.includes('速度')) return numValue(r.v_kmh, unit)
  if (metric.includes('排队比') || metric.includes('L_q/L_seg')) return numValue(ratioValue(r.L_q_m, r.L_seg_m))
  if (metric.includes('排队长度') || metric.includes('L_q')) return numValue(r.L_q_m, unit)
  if (metric.includes('消散') || metric.includes('T_d')) return numValue(r.T_d_min, unit)
  if (metric.includes('密度') || metric === 'k') return numValue(r.k_vpk, unit)
  return { value: null, text: '—' }
}

interface ThresholdRowView {
  metric: string
  unit: string
  current: CurrentValue
  bounds: number[]
  levels: number[]
}

const thresholdRows = computed<ThresholdRowView[]>(() => {
  const rows = props.thresholds?.rows ?? []
  return rows.map((row) => {
    const unit = row.unit ?? ''
    const bands = (row.bands ?? []).filter((band) => band.level <= 3)
    return {
      metric: row.metric,
      unit,
      current: currentOfMetric(row.metric, unit),
      bounds: bands.map((band) => band.max),
      levels: (row.bands ?? []).map((band) => band.level),
    }
  })
})

/** 饱和度轨道的当前值位置（只算"值画在哪"，不做等级归类的结论文案） */
const xTrack = computed<{ pct: number; bands: ThresholdRowView | null } | null>(() => {
  const row = thresholdRows.value.find((item) => item.metric.includes('饱和度') || item.metric === 'x')
  if (!row || row.current.value === null) return null
  const lastBound = row.bounds[row.bounds.length - 1] ?? 1
  const scaleMax = lastBound > 0 ? lastBound * 1.1 : 1
  return { pct: Math.max(0, Math.min(100, (row.current.value / scaleMax) * 100)), bands: row }
})

const xSampleNote = computed<string>(() => {
  const row = thresholdRows.value.find((item) => item.metric.includes('饱和度') || item.metric === 'x')
  if (!row) return '阈值未取到（/thresholds 未返回饱和度行）'
  const text = row.bounds.map((bound, index) => `${index + 1} 档 ≤ ${bound}`).join(' / ')
  return `四档边界（接口 /thresholds）：${text}${row.bounds.length === 3 ? ' / 4 档 > ' + row.bounds[2] : ''}`
})

const thresholdsSource = computed<string>(() => {
  const ts = props.thresholds?.ts
  return ts ? `阈值快照 ${ts}` : '阈值未取到'
})

function targetLabel(target: string): string {
  const map: Record<string, string> = {
    c: '通行能力',
    v_f: '畅通速度',
    demand: '需求',
    lanes: '车道数',
    confidence: '置信度',
  }
  return map[target] ?? target
}
</script>

<template>
  <section class="sum-card">
    <div class="sec-head">
      决策计算摘要
      <span class="td-chip warn">演示数据（模拟）</span>
      <span class="sec-tag">前端不重算判级</span>
    </div>

    <!-- 无快照记录：如实空壳，不编指标 -->
    <p v-if="!record" class="empty sm">
      该路段在当前快照里没有运行指标（段号未被感知 / 孪生产物覆盖）——输入指标一律「—」，
      等级按「数据不可用」灰档处理（TC-11），不给编造值。
    </p>

    <template v-else>
      <!-- ① 输入 -->
      <div class="sub-head">① 输入（接口快照原样）</div>
      <div class="in-grid">
        <div v-for="row in inputRows" :key="row.key" class="in-item">
          <span class="in-k">{{ row.label }}</span>
          <span class="in-v td-num">{{ row.value }}</span>
        </div>
      </div>
      <p class="tiny">
        数据年龄口径：{{ dataAgeNote }}<span class="sep">|</span>来源 video = 视频感知链路、twin = 孪生链路
      </p>

      <!-- ② 判级（后端下发，不重算） -->
      <div class="sub-head">② 判级（后端下发，原样展示）</div>
      <div class="lv-row">
        <LevelBadge v-if="levelOf" :level="levelOf" :stale="stale" />
        <span v-else class="unavail">数据不可用</span>
        <span class="lv-text">{{ levelText }}</span>
        <span class="sep">·</span>
        <span class="tiny">触发依据 {{ triggeredText }}</span>
      </div>
      <p class="tiny">
        level / level_name / triggered_by 均来自接口快照；<b>前端不重算等级</b>，
        详细演算过程见决策页「决策可视化」。
      </p>

      <!-- ③ 四档阈值对照（展示用） -->
      <div class="sub-head">③ 四档阈值对照（接口 /thresholds，展示用不判级）</div>
      <template v-if="thresholdRows.length > 0">
        <div v-if="xTrack" class="band-box">
          <div class="band-track">
            <span
              v-for="level in xTrack.bands?.levels ?? []"
              :key="level"
              class="band-seg"
              :class="{ hit: levelOf !== null && level === levelOf }"
            >
              {{ level }} 档
            </span>
            <span class="band-cursor" :style="{ left: xTrack.pct + '%' }" aria-hidden="true" />
          </div>
          <p class="tiny">{{ xSampleNote }}<span class="sep">|</span>当前 x = {{ fmt(record.x) }}</p>
        </div>
        <!-- 响应式（Issue IKP3EV）：窄屏下三列表格会撑破右栏，外面套一层横向滚动容器，
             桌面宽度下容器与表格同宽，不产生任何视觉变化。 -->
        <div class="tbl-scroll">
        <table class="td-table th-table">
          <thead>
            <tr>
              <th>指标</th>
              <th class="num">当前值</th>
              <th>四档边界（level 1 / 2 / 3）</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in thresholdRows" :key="row.metric">
              <td>{{ row.metric }}</td>
              <td class="num td-num">{{ row.current.text }}</td>
              <td class="td-num">{{ row.bounds.length ? row.bounds.join(' / ') : '—' }}</td>
            </tr>
          </tbody>
        </table>
        </div>
        <p class="tiny">{{ thresholdsSource }}<span class="sep">|</span>{{ CI_DISCLAIMER }}</p>
      </template>
      <p v-else class="empty sm">阈值未取到（/thresholds 不可用）——不伪造四档边界。</p>

      <!-- ④ 因素 + CI -->
      <div class="sub-head">
        ④ 生效因素<span class="sub-tag">{{ factors.length }} 项</span>
        <span class="sep">|</span>CI <b class="td-num">{{ ciText }}</b>
        <span class="sub-tag">（CI 只展示不判级）</span>
      </div>
      <div v-if="factors.length > 0" class="fac-row">
        <span v-for="f in factors" :key="`${f.segment_id}-${f.factor_id}`" class="fac">
          <b>{{ f.factor_id }}</b> {{ f.name }}
          <span class="sep">·</span>作用{{ targetLabel(f.target) }}
          <span class="sep">·</span>×{{ Number(f.multiplier.toFixed(2)) }}
        </span>
      </div>
      <p v-else class="tiny">本期无生效因素（基线口径，非"没有考虑因素"）。</p>
    </template>

    <RouterLink class="deep-link" :to="{ path: '/decision', query: { segment: segmentId } }">
      查看完整决策过程 →
    </RouterLink>
    <p class="tiny deep-note">
      深链：决策页「决策可视化」（输入 → 判级演算 → 可调控 → 输出）按该段展示；状态与决策页同源。
    </p>
  </section>
</template>

<style scoped>
.sum-card {
  padding: 8px 0;
  border-bottom: 1px solid var(--td-component-stroke);
}
.sec-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}
.sec-tag {
  margin-left: auto;
  font-size: 11px;
  font-weight: 400;
  color: var(--td-text-color-placeholder);
}
.sub-head {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px;
  margin: 6px 0 3px;
  font-size: 11px;
  font-weight: 500;
  color: var(--td-text-color-secondary);
}
.sub-tag {
  font-size: 10px;
  font-weight: 400;
  color: var(--td-text-color-placeholder);
}
.in-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2px 10px;
}
.in-item {
  display: flex;
  justify-content: space-between;
  gap: 6px;
  font-size: 11px;
  line-height: 1.6;
}
.in-k {
  color: var(--td-text-color-placeholder);
}
.in-v {
  color: var(--td-text-color-primary);
}
.lv-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 11px;
}
.lv-text {
  color: var(--td-text-color-primary);
}
.unavail {
  color: var(--td-text-color-placeholder);
}
.tiny {
  margin: 3px 0 0;
  font-size: 10px;
  line-height: 1.6;
  color: var(--td-text-color-placeholder);
}
.sep {
  margin: 0 4px;
  color: var(--td-text-color-placeholder);
}
.band-box {
  margin-bottom: 4px;
}
.band-track {
  position: relative;
  display: flex;
  height: 18px;
  border-radius: 3px;
  overflow: visible;
  background: var(--td-bg-color-secondarycontainer);
}
.band-seg {
  flex: 1;
  font-size: 10px;
  line-height: 18px;
  text-align: center;
  color: var(--td-text-color-placeholder);
  border-right: 1px solid var(--td-component-stroke);
}
.band-seg:last-child {
  border-right: none;
}
.band-seg.hit {
  background: var(--td-brand-color-1);
  color: var(--td-brand-color);
  font-weight: 600;
}
.band-cursor {
  position: absolute;
  top: -3px;
  width: 2px;
  height: 24px;
  background: var(--td-brand-color);
  transform: translateX(-1px);
}
.band-cursor::before {
  content: '';
  position: absolute;
  top: -4px;
  left: -3px;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-top: 5px solid var(--td-brand-color);
}
.th-table {
  font-size: 10px;
}
.th-table th,
.th-table td {
  padding: 3px 6px;
}
.fac-row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.fac {
  padding: 2px 7px;
  border: 1px solid var(--td-component-stroke);
  border-radius: var(--td-radius-sm);
  background: var(--td-bg-color-secondarycontainer);
  font-size: 10px;
  color: var(--td-text-color-primary);
}
.empty {
  margin: 4px 0;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
.deep-link {
  display: inline-block;
  margin-top: 8px;
  font-size: 11px;
  color: var(--td-brand-color);
  text-decoration: none;
}
.deep-note {
  margin-top: 2px;
}
/* 表格横向滚动容器：桌面宽度下与表格同宽（不产生横滚条），窄屏才真正起作用。 */
.tbl-scroll {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

/* ==========================================================================
   响应式（Issue IKP3EV）
   断点与 DashboardView 一致：1180 / 768 / 560。
   ========================================================================== */
@media (max-width: 768px) {
  /* 四档阈值三列表格：给它一个最小宽度，由外层 .tbl-scroll 横向滑动，
     而不是把「四档边界」列压成两个字一行。 */
  .th-table {
    min-width: 400px;
  }
}

@media (max-width: 560px) {
  /* 输入网格 2 列→1 列：手机宽度下 label + value 各占半行会被折成两行。 */
  .in-grid {
    grid-template-columns: 1fr;
  }
  .deep-link {
    display: block;
    margin-top: 10px;
  }
}
</style>
