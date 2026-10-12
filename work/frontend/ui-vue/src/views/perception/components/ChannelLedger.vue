<script setup lang="ts">
// 左栏:视频源台账(6 路,可用性以 /perception-api/streams 实际返回判定)+ 跟踪环节清单。
// 数字一律取 meta;服务未提供的环节(透视标定 / 越线计数 / 判级)显示「—」并注明出处。
import { computed } from 'vue'
import { metaLine } from './channels'
import type { ChannelState } from './channels'

const props = defineProps<{ channels: ChannelState[]; currentId: string }>()
const emit = defineEmits<{ (e: 'select', source: string): void }>()

const exportedCount = computed(() => props.channels.filter((c) => c.meta !== null).length)

const current = computed(() => props.channels.find((c) => c.def.source === props.currentId) ?? null)
const currentMeta = computed(() => current.value?.meta ?? null)

const linkRows = computed(() => {
  const m = currentMeta.value
  const backend = m?.backend ?? ''
  return [
    { k: '目标检测', v: m ? m.model : '—' },
    { k: '后端 / 框架', v: backend || '—' },
    { k: '多目标跟踪', v: backend.includes('ByteTrack') ? 'ByteTrack' : '—' },
    { k: '轨迹总数', v: m ? String(m.track_total) : '—' },
    { k: '类别白名单', v: m ? Object.values(m.class_names).join(' / ') : '—' },
    { k: '透视标定', v: '—' },
    { k: '越线计数', v: '—' },
    { k: '判级', v: '—' },
  ]
})

function stateOf(c: ChannelState): { text: string; cls: string } {
  if (!c.meta) return { text: '未导出', cls: 'out' }
  if (c.def.source === props.currentId) return { text: '检测中', cls: 'on' }
  return { text: '就绪', cls: 'ok' }
}
</script>

<template>
  <section class="td-card">
    <div class="td-card-head">
      视频源
      <span class="td-head-tag">6 路 · 离线样本(已导出 {{ exportedCount }})</span>
    </div>
    <div class="td-card-body flush">
      <div
        v-for="c in channels"
        :key="c.def.source"
        class="td-row chan"
        :class="{ on: c.def.source === currentId }"
        role="button"
        :aria-pressed="c.def.source === currentId"
        @click="emit('select', c.def.source)"
      >
        <div class="chan-main">
          <div class="chan-l1">
            <span class="cid td-mono">{{ c.def.cid }}</span>
            <span class="src">· {{ c.def.source }}</span>
            <span class="td-chip" :class="stateOf(c).cls">{{ stateOf(c).text }}</span>
          </div>
          <div class="chan-l2">{{ c.def.segmentId }} {{ c.def.name }}</div>
          <div class="chan-l3 td-mono">{{ metaLine(c.meta, c.detTotal) }}</div>
        </div>
      </div>
    </div>
  </section>

  <section class="td-card">
    <div class="td-card-head">
      跟踪环节
      <span class="td-head-tag">{{ current ? `当前 ${current.def.cid} ${current.def.source}` : '未选通道' }}</span>
    </div>
    <div class="td-card-body">
      <div v-for="row in linkRows" :key="row.k" class="kv">
        <span class="k">{{ row.k }}</span>
        <span class="v td-mono">{{ row.v }}</span>
      </div>
      <p class="note">
        透视标定 / 越线计数 / 判级三项由感知服务提供,当前不可用 → 显示「—」,不以推算值冒充。
      </p>
    </div>
  </section>

  <section class="td-card">
    <div class="td-card-head">
      点位与口径
      <span class="td-head-tag">D1′</span>
    </div>
    <div class="td-card-body">
      <p class="line">一期 · 6 段样本视频(离线批处理)</p>
      <p class="line">二期 · 现场摄像头流(本期不接入)</p>
      <p class="line strong">点位与字段不变 · 只换视频源</p>
    </div>
  </section>
</template>

<style scoped>
.chan {
  align-items: flex-start;
}
.chan-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  width: 100%;
}
.chan-l1 {
  display: flex;
  align-items: center;
  gap: 6px;
}
.chan-l1 .td-chip {
  margin-left: auto;
}
.cid {
  font-weight: 600;
  color: var(--td-text-color-primary);
}
.src {
  color: var(--td-text-color-secondary);
}
.chan-l2 {
  font-size: 12px;
  color: var(--td-text-color-primary);
}
.chan-l3 {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
.kv {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 3px 0;
  font-size: 12px;
  border-bottom: 1px dashed var(--td-component-stroke);
}
.kv:last-of-type {
  border-bottom: none;
}
.kv .k {
  color: var(--td-text-color-secondary);
  flex: 0 0 auto;
}
.kv .v {
  margin-left: auto;
  color: var(--td-text-color-primary);
  text-align: right;
  overflow-wrap: anywhere;
}
.note {
  margin: 8px 0 0;
  font-size: 11px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder);
}
.line {
  margin: 0 0 4px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}
.line.strong {
  margin-bottom: 0;
  color: var(--td-text-color-primary);
  font-weight: 500;
}
</style>
