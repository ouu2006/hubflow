<script setup lang="ts">
// 中栏下部:检测流水线(5 环节横向流程)+ 六路汇总(本次批处理)。
// 环节产物取当前通道 meta;服务未提供的量(标定 RANGE/RMSE、越线、平均 Q、处理用时)如实显示「—」。
import { computed } from 'vue'
import type { PerceptionSummary, PerceptionStreamMeta } from '../../../api/perception'
import { fmtDur } from './channels'
import type { ChannelDef, ChannelState } from './channels'

const props = defineProps<{
  channels: ChannelState[]
  current: ChannelDef
  meta: PerceptionStreamMeta | null
  summary: PerceptionSummary | null
  summaryUnavailable: boolean
}>()

const exportsCount = computed(() => props.channels.filter((c) => c.meta !== null).length)

const stages = computed(() => {
  const m = props.meta
  const backend = m?.backend ?? ''
  return [
    { name: '源视频', value: `6 段 · 离线样本(已导出 ${exportsCount.value} 路)`, on: false },
    { name: '目标检测', value: m ? `${m.model} · ${m.conf_threshold} conf` : '—', on: false },
    {
      name: '多目标跟踪',
      value: m && backend.includes('ByteTrack') ? `ByteTrack · ${m.track_total} 轨迹` : '—',
      on: false,
    },
    { name: '透视标定', value: 'RANGE — · RMSE —', on: false },
    { name: '四项指标', value: 'q · v · k · L_q', on: true },
  ]
})

const trackSum = computed(() =>
  props.channels.reduce((acc, c) => acc + (c.meta?.track_total ?? 0), 0),
)
const detSum = computed(() => {
  const known = props.channels.filter((c) => c.detTotal !== null)
  if (known.length === 0) return null
  return known.reduce((acc, c) => acc + (c.detTotal ?? 0), 0)
})
/** 检测读取失败的通道数:合计口径里必须显式提示,避免"少算几路"被当成"就这么多" */
const detFailedCount = computed(() => props.channels.filter((c) => c.detFailed).length)

const summaryRows = computed(() => {
  const s = props.summary
  return [
    { k: '轨迹总数', v: `${trackSum.value} 条` },
    { k: '检测框总数', v: detSum.value === null ? '—' : `${detSum.value} 框` },
    { k: '累计越线计数', v: s ? String(s.cross_total) : '—' },
    { k: '平均 Q', v: s && s.avg_quality !== null ? s.avg_quality.toFixed(2) : '—' },
    {
      k: '处理用时',
      v: s && s.pipeline ? fmtDur(s.pipeline.duration_s) : '—',
    },
  ]
})
</script>

<template>
  <section class="td-card">
    <div class="td-card-head">
      检测流水线
      <span class="td-head-tag">当前处理 {{ current.cid }} {{ current.source }}</span>
    </div>
    <div class="td-card-body">
      <div class="flow">
        <template v-for="(st, i) in stages" :key="st.name">
          <span v-if="i > 0" class="arrow" aria-hidden="true">›</span>
          <div class="stage" :class="{ on: st.on }">
            <span class="st-name">{{ st.name }}</span>
            <span class="st-val td-mono">{{ st.value }}</span>
          </div>
        </template>
      </div>
      <p class="flow-note">单 CPU · 离线批处理 · 6 段样本({{ exportsCount }} 路已导出)</p>

      <div class="sep">
        六路汇总 · 本次批处理
        <span class="td-head-tag">{{ exportsCount }} / 6 完成</span>
      </div>
      <div class="kv" v-for="row in summaryRows" :key="row.k">
        <span class="k">{{ row.k }}</span>
        <span class="v td-mono">{{ row.v }}</span>
      </div>
      <p v-if="detFailedCount > 0" class="note err">
        有 {{ detFailedCount }} 路检测读取失败,未计入上表合计(故障不等于该路无检出)。
      </p>
      <p v-if="summaryUnavailable" class="note">
        累计越线计数 / 平均 Q / 处理用时由感知服务提供,当前不可用 → 显示「—」。
      </p>
    </div>
  </section>
</template>

<style scoped>
.flow {
  display: flex;
  align-items: stretch;
  gap: 6px;
  flex-wrap: wrap;
}
.arrow {
  align-self: center;
  color: var(--td-text-color-placeholder);
  font-size: 14px;
}
.stage {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 7px 10px;
  border-radius: var(--td-radius-sm);
  background: var(--td-bg-color-secondarycontainer);
  min-width: 108px;
}
.stage.on {
  background: var(--td-brand-color-1);
}
.st-name {
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.stage.on .st-name {
  color: var(--td-brand-color);
}
.st-val {
  font-size: 11px;
  color: var(--td-text-color-primary);
}
.flow-note {
  margin: 8px 0 0;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
.sep {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px 0 6px;
  padding-top: 10px;
  border-top: 1px solid var(--td-component-stroke);
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}
.sep .td-head-tag {
  margin-left: auto;
  font-size: 11px;
  font-weight: 400;
  color: var(--td-text-color-placeholder);
}
.kv {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 3px 0;
  font-size: 12px;
}
.kv .k {
  color: var(--td-text-color-secondary);
}
.kv .v {
  margin-left: auto;
  color: var(--td-text-color-primary);
}
.note {
  margin: 6px 0 0;
  font-size: 11px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder);
}
/* 接口故障提示:与"服务未提供该字段"的说明区分开 */
.note.err {
  color: #ad352f;
}
</style>
