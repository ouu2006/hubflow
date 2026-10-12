<script setup lang="ts">
// 路段指数明细(右栏单卡):选中路段的大号 CI + 四项加权构成 + 数据不可用路段
// + CI 走势 + 成因拆解 + 关联告警 + 前往决策工作台处置。
// 硬口径:CI 只用于展示与辅助排序;选中路段缺 CI / 陈旧时显示灰「不可用」,绝不编造数字。
import { computed } from 'vue'
import { ciAvailable, ciColor, CI_MAX, UNAVAILABLE, type CiHistory, type FactorApplied, type SegmentRecord, type TrafficAlert } from '../../../shared/traffic'
import LevelBadge from '../../dashboard/components/LevelBadge.vue'
import AlertList from './AlertList.vue'
import CiTrendBars from './CiTrendBars.vue'
import FactorBreakdown from './FactorBreakdown.vue'

const props = defineProps<{
  record: SegmentRecord | null
  name: string
  weights: { key: string; label: string; weight: number }[]
  weightText: string
  history: CiHistory | null
  factors: (FactorApplied & { segment_id: string })[]
  alerts: TrafficAlert[]
  unavailable: { id: string; name: string; reason: string; ageText: string; confidence: string }[]
}>()

const emit = defineEmits<{ (e: 'goto-decision'): void }>()

/** 选中路段 CI 是否可用(缺 CI 或陈旧 → 灰「不可用」) */
const available = computed(() => (props.record ? ciAvailable(props.record) : false))
const ciText = computed(() => {
  const r = props.record
  return r && ciAvailable(r) ? (r.ci as number).toFixed(1) : '不可用'
})
const ciTextColor = computed(() => {
  const r = props.record
  return r && ciAvailable(r) ? ciColor(r.ci as number) : UNAVAILABLE.color
})

function signed(v?: number): string {
  return typeof v === 'number' && Number.isFinite(v) ? String(v) : '—'
}

function ratio(a?: number, b?: number): string {
  if (typeof a !== 'number' || typeof b !== 'number' || !Number.isFinite(a) || !Number.isFinite(b) || b === 0) {
    return '—'
  }
  return (a / b).toFixed(2)
}

/** 各权重要素的「数值」:饱和度 x / 速度比 v/v_f / 排队比 L_q/L_seg / 消散 T_d(缺字段显示「—」) */
function metricText(key: string): string {
  const r = props.record
  if (!r) return '—'
  switch (key) {
    case 'x':
      return signed(r.x)
    case 'v':
      return ratio(r.v_kmh, r.v_f_kmh)
    case 'k':
      return ratio(r.L_q_m, r.L_seg_m)
    case 'T_d':
      return signed(r.T_d_min)
    default:
      return '—'
  }
}
</script>

<template>
  <div class="td-card">
    <div class="td-card-head">
      路段指数明细<span class="td-head-tag td-mono">{{ record?.segment_id ?? '—' }}</span>
    </div>
    <div class="td-card-body idx-body">
      <template v-if="record">
        <!-- 大号 CI + 等级徽章(三重编码) -->
        <div class="idx-head">
          <div class="idx-title">
            <span class="idx-name">{{ name }}</span>
            <LevelBadge :level="record.level" :stale="!available" />
          </div>
          <div class="idx-ci td-num" :style="{ color: ciTextColor }">{{ ciText }}</div>
          <div class="idx-sub">拥挤指数 CI（0~{{ CI_MAX }}）· 四项加权 {{ weightText }}</div>
        </div>

        <!-- 四项加权构成 -->
        <div class="sub-head">四项加权构成</div>
        <div v-for="w in weights" :key="w.key" class="wt-row">
          <span class="wt-label">{{ w.label }}</span>
          <span class="wt-val td-mono">{{ metricText(w.key) }} × {{ w.weight.toFixed(2) }}</span>
        </div>
        <p v-if="weights.length === 0" class="empty">权重加载中…</p>

        <!-- 数据不可用路段 -->
        <div class="sub-head">
          数据不可用路段<span class="sub-tag">{{ unavailable.length }} 段</span>
        </div>
        <div v-if="unavailable.length > 0" class="un-list">
          <div v-for="u in unavailable" :key="u.id" class="un-row">
            <span class="un-id td-mono">{{ u.id }}</span>
            <span class="un-name">{{ u.name }}</span>
            <span class="un-reason">{{ u.reason }}{{ u.ageText === '—' ? '' : ` ${u.ageText}` }}</span>
            <span class="un-conf td-mono">置信度 {{ u.confidence }}</span>
          </div>
        </div>
        <p v-else class="empty">无不可用路段</p>

        <!-- CI 走势 -->
        <div class="sub-head">
          CI 走势 · 近 {{ history?.points.length ?? 12 }} 期<span class="sub-tag">阈值线 65 / 85</span>
        </div>
        <CiTrendBars :history="history" />

        <!-- 成因拆解 -->
        <div class="sub-head">成因拆解 · 本期生效因素<span class="sub-tag">{{ factors.length }} 项</span></div>
        <FactorBreakdown :factors="factors" />

        <!-- 关联告警 -->
        <div class="sub-head">关联告警<span class="sub-tag">{{ alerts.length }} 条未闭环</span></div>
        <AlertList :alerts="alerts" />

        <div class="idx-foot">
          <button type="button" class="td-btn primary idx-btn" @click="emit('goto-decision')">
            前往决策工作台处置
          </button>
        </div>
      </template>
      <p v-else class="empty">未选中路段</p>
    </div>
  </div>
</template>

<style scoped>
.idx-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.idx-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.idx-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.idx-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}
.idx-ci {
  font-size: 30px;
  font-weight: 700;
  line-height: 1.1;
}
.idx-sub {
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.sub-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px solid var(--td-component-stroke);
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
.wt-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
}
.wt-label {
  color: var(--td-text-color-secondary);
}
.wt-val {
  color: var(--td-text-color-primary);
}
.un-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.un-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
}
.un-id {
  color: var(--td-text-color-placeholder);
}
.un-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--td-text-color-secondary);
}
/* 原因 / 置信度 = 数据不可用语义,用灰 */
.un-reason,
.un-conf {
  color: #8b8b8b;
  white-space: nowrap;
}
.idx-foot {
  margin-top: 6px;
  padding-top: 10px;
  border-top: 1px solid var(--td-component-stroke);
}
.idx-btn {
  width: 100%;
  height: 32px;
  font-size: 13px;
}
.empty {
  margin: 0;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}
</style>
