<script setup lang="ts">
// 左栏:视频源台账(N 路,可用性以 /perception-api/streams 实际返回判定)+ 跟踪环节清单。
// IKMS1T 起不再固定 6 路:行数 = 登记表 cameras 条数 N(0 路合法),左栏自身滚动;
// 数字一律取 meta;服务未提供的环节(透视标定 / 越线计数 / 判级)显示「—」并注明出处。
import { computed } from 'vue'
import { feedOf, feedText, metaLine } from './channels'
import type { ChannelState } from './channels'

const props = defineProps<{ channels: ChannelState[]; currentId: string }>()
const emit = defineEmits<{ (e: 'select', source: string): void }>()

/** 有视频源且服务端真返回了 meta 的通道数(未接入视频源的不算"已导出") */
const exportedCount = computed(() =>
  props.channels.filter((c) => c.def.hasVideo && c.meta !== null).length,
)
/** 未接入视频源的通道数(Issue IKLX5Y:布了点、视频留空窗) */
const noSourceCount = computed(() => props.channels.filter((c) => !c.def.hasVideo).length)
/** 全包都没有视频源(站点包 Z):这时不能自称"离线样本"——样本视频压根没有 */
const allNoSource = computed(
  () => props.channels.length > 0 && noSourceCount.value === props.channels.length,
)

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
  const f = feedOf(c)
  // 「当前」态只在真有画面可看时才亮(未接入视频源的通道谈不上"检测中")
  if (f === 'ok' && c.def.source === props.currentId) return { text: '检测中', cls: 'on' }
  return feedText(c)
}
</script>

<template>
  <section class="td-card">
    <div class="td-card-head">
      视频源
      <span class="td-head-tag">
        <template v-if="channels.length === 0">0 路 · 本站未布摄像头</template>
        <template v-else-if="allNoSource">{{ channels.length }} 路 · 全部未接入视频源(本期留空)</template>
        <template v-else>{{ channels.length }} 路 · 离线样本(已导出 {{ exportedCount }})<template v-if="noSourceCount > 0">
          · 未接入视频源 {{ noSourceCount }} 路</template></template>
      </span>
    </div>
    <div class="td-card-body flush">
      <!-- 0 路合法(IKMS1T):如实显示,不报错、不拿别的站数据顶 -->
      <div v-if="channels.length === 0" class="ledger-empty">
        <span class="le-l1">本站未布摄像头</span>
        <span class="le-l2">登记表 cameras 0 条（N = 0 路 · 0 路合法）</span>
      </div>
      <template v-if="channels.length > 0">
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
            <div class="chan-l3 td-mono">
              {{ !c.def.hasVideo ? '未接入视频源 · 本期留空(路网上已布点)' : metaLine(c.meta, c.detTotal) }}
            </div>
          </div>
        </div>
      </template>
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
      <p class="line">
        <template v-if="channels.length === 0">本包 · 0 路通道(本站未布摄像头)</template>
        <template v-else-if="allNoSource">本包 · {{ channels.length }} 路通道全部未接入视频源(本期留空)</template>
        <template v-else>一期 · 离线样本视频(批处理;文件数由登记表 video_streams 决定)</template>
      </p>
      <p class="line">二期 · 现场摄像头流(本期不接入)</p>
      <p class="line strong">点位与字段不变 · 只换视频源</p>
      <p class="note">
        另有「未接入视频源」的通道:路网上已布点(大屏可点),但本期不给视频 ——
        它与「未导出」(有样本视频、服务端还没处理)不是一回事,故分两档显示。
      </p>
    </div>
  </section>
</template>

<style scoped>
/* 0 路空态:如实写明,不报错、不拿别的站数据顶 */
.ledger-empty {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 18px 12px;
  text-align: center;
}
.le-l1 {
  font-size: 13px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}
.le-l2 {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
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
