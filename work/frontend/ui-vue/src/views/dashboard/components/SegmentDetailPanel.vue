<script setup lang="ts">
// 右栏·路段详情:四项指标 + 饱和度/拥挤指数 + 生效因素 + L0 预测 + 溯源信息。
// 全部字段名对照 docs/数据契约.md v2.0;不计算任何业务指标,只渲染快照。
import { computed } from 'vue'
import { demoSegment } from '../../../shared/demoNetwork'
import {
  isStale,
  STALE_AFTER_S,
  type FactorApplied,
  type SegmentRecord,
  type TrafficSource,
} from '../../../shared/traffic'
import LevelBadge from './LevelBadge.vue'

const props = defineProps<{
  segment: SegmentRecord | null
}>()

const name = computed(() =>
  props.segment ? (demoSegment(props.segment.segment_id)?.name ?? props.segment.segment_id) : '',
)

const stale = computed(() => (props.segment ? isStale(props.segment) : false))

interface Metric {
  label: string
  value: string
  unit: string
}

const metrics = computed<Metric[]>(() => {
  const s = props.segment
  if (!s) return []
  return [
    { label: '流量 q', value: `${s.q_vph ?? '—'}`, unit: '辆/h' },
    { label: '平均车速 v', value: `${s.v_kmh ?? '—'}`, unit: `km/h · 畅通 ${s.v_f_kmh ?? '—'}` },
    { label: '密度 k', value: `${s.k_vpk ?? '—'}`, unit: '辆/km' },
    { label: '排队长度', value: `${s.L_q_m ?? '—'}`, unit: 'm' },
  ]
})

interface KV {
  label: string
  value: string
}

const secondary = computed<KV[]>(() => {
  const s = props.segment
  if (!s) return []
  return [
    { label: '饱和度 x', value: `${s.x ?? '—'}` },
    { label: '拥挤指数 ci', value: `${s.ci ?? '—'}` },
    { label: '消散时间', value: s.T_d_min ? `${s.T_d_min} min` : '—' },
    { label: '通行能力', value: s.c_vph ? `${s.c_vph} / 基准 ${s.c_base_vph ?? '—'} 辆/h` : '—' },
  ]
})

function factorText(f: FactorApplied): string {
  const targetLabel: Record<string, string> = {
    c: '通行能力',
    v_f: '畅通速度',
    demand: '需求',
    lanes: '车道数',
    confidence: '检测置信度',
  }
  return `${targetLabel[f.target] ?? f.target} ×${f.multiplier}`
}

function untilText(iso: string): string {
  return iso.length >= 16 ? iso.slice(11, 16) : iso
}

const SOURCE_LABEL: Record<TrafficSource, string> = {
  video: '视频链路(video)',
  twin: '孪生链路(twin)',
}
</script>

<template>
  <div class="detail">
    <template v-if="props.segment">
      <div class="head">
        <div class="title">
          <span class="name">{{ name }}</span>
          <span class="sid">{{ props.segment.segment_id }}</span>
        </div>
        <LevelBadge :level="props.segment.level" :stale="stale" />
      </div>

      <div v-if="stale" class="stale-warn">
        数据年龄 {{ props.segment.data_age_s }}s &gt; {{ STALE_AFTER_S }}s:数据不可用,仅展示、不进入推荐计算
      </div>

      <div class="metric-grid">
        <div v-for="m in metrics" :key="m.label" class="metric">
          <div class="m-label">{{ m.label }}</div>
          <div class="m-value">{{ m.value }}<span class="m-unit">{{ m.unit }}</span></div>
        </div>
      </div>

      <div class="kv-grid">
        <div v-for="kv in secondary" :key="kv.label" class="kv">
          <span class="k">{{ kv.label }}</span>
          <span class="v">{{ kv.value }}</span>
        </div>
      </div>

      <div class="section">
        <div class="s-title">当前生效因素</div>
        <template v-if="props.segment.factors_applied?.length">
          <div v-for="f in props.segment.factors_applied" :key="f.factor_id" class="factor">
            <span class="f-name">{{ f.name }}</span>
            <span class="f-code">{{ f.factor_id }}</span>
            <span class="f-effect">{{ factorText(f) }}</span>
            <span class="f-until">至 {{ untilText(f.until) }}</span>
          </div>
        </template>
        <div v-else class="none">无(未受因素影响)</div>
      </div>

      <div class="section">
        <div class="s-title">
          未来预测
          <span v-if="props.segment.pred" class="model-tag">{{ props.segment.pred.model }} · 历史同期</span>
        </div>
        <template v-if="props.segment.pred">
          <div class="pred-row">
            <span class="p-h">15 分钟</span>
            <LevelBadge :level="props.segment.pred.h15.level" />
            <span class="p-q">{{ props.segment.pred.h15.q_vph }} 辆/h</span>
          </div>
          <div class="pred-row">
            <span class="p-h">30 分钟</span>
            <LevelBadge :level="props.segment.pred.h30.level" />
            <span class="p-q">{{ props.segment.pred.h30.q_vph }} 辆/h</span>
          </div>
        </template>
        <div v-else class="none">暂无预测</div>
      </div>

      <div class="section">
        <div class="s-title">数据溯源</div>
        <div class="trace">
          <span class="chip source">{{ SOURCE_LABEL[props.segment.source] }}</span>
          <span class="chip sim">is_simulated = true</span>
        </div>
        <div class="kv-grid">
          <div class="kv"><span class="k">数据年龄</span><span class="v">{{ props.segment.data_age_s ?? '—' }} s</span></div>
          <div class="kv"><span class="k">置信度</span><span class="v">{{ props.segment.confidence ?? '—' }}</span></div>
        </div>
        <div v-if="props.segment.triggered_by?.length" class="trig">
          判级触发:
          <span v-for="t in props.segment.triggered_by" :key="t" class="chip trig-chip">{{ t }}</span>
        </div>
      </div>
    </template>
    <div v-else class="empty">
      <div class="empty-icon">◈</div>
      点击左侧列表或地图中的路段<br />查看指标、因素与预测
    </div>
  </div>
</template>

<style scoped>
.detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
  padding-right: 2px;
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.title {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.name {
  font-size: 17px;
  font-weight: 700;
  color: #e6eefc;
}
.sid {
  font-size: 11px;
  color: #7c93b5;
}
.stale-warn {
  padding: 8px 10px;
  border: 1px solid #5a5a5a;
  background: rgba(140, 140, 140, 0.12);
  color: #b8b8b8;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.5;
}
.metric-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.metric {
  padding: 10px;
  background: rgba(20, 38, 66, 0.55);
  border: 1px solid #1d3354;
  border-radius: 8px;
}
.m-label {
  font-size: 11px;
  color: #7c93b5;
}
.m-value {
  margin-top: 4px;
  font-size: 20px;
  font-weight: 700;
  color: #e6eefc;
}
.m-unit {
  margin-left: 5px;
  font-size: 10px;
  font-weight: 400;
  color: #7c93b5;
}
.kv-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px 12px;
}
.kv {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}
.k {
  color: #7c93b5;
}
.v {
  color: #d9e4f5;
  font-weight: 600;
}
.section {
  border-top: 1px solid #1d3354;
  padding-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.s-title {
  font-size: 12px;
  color: #7c93b5;
  display: flex;
  align-items: center;
  gap: 8px;
}
.model-tag {
  font-size: 10px;
  color: #7fe7ff;
  border: 1px solid #2a7f9e;
  border-radius: 4px;
  padding: 0 5px;
}
.factor {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.f-name {
  color: #ffd479;
  font-weight: 600;
}
.f-code {
  color: #7c93b5;
  font-size: 10px;
}
.f-effect {
  color: #d9e4f5;
  margin-left: auto;
}
.f-until {
  color: #7c93b5;
  font-size: 11px;
}
.pred-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}
.p-h {
  color: #9fb6d9;
  width: 52px;
}
.p-q {
  color: #d9e4f5;
}
.trace {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.chip {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid #37507a;
  color: #b7c8e3;
}
.chip.source {
  color: #8feaff;
  border-color: #2a7f9e;
}
.chip.sim {
  color: #ffd479;
  border-color: #8a6d1f;
}
.chip.trig-chip {
  color: #ff9e9e;
  border-color: #8f3a3a;
}
.trig {
  font-size: 12px;
  color: #7c93b5;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.none {
  font-size: 12px;
  color: #5f7396;
}
.empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #5f7396;
  font-size: 13px;
  text-align: center;
  line-height: 1.8;
}
.empty-icon {
  font-size: 34px;
  color: #2c4a78;
}
</style>
