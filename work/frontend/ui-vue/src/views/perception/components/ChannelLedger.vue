<script setup lang="ts">
// 左栏:视频源台账(N 路,可用性以 /perception-api/streams 实际返回判定)+ 跟踪环节清单。
// IKMS1T 起不再固定 6 路:行数 = 源台账 cameras 条数 N(0 路合法),左栏自身滚动;
// 数字一律取 meta;服务未提供的环节(透视标定 / 越线计数 / 判级)显示「—」并注明出处。
//
// 2026-10-18 口径(IKNBT2):**N 段 = N 摄像头 = N 视频(演示,mock 复用)**——
// 本台账只是**源台账/初始映射**,不代表一期摄像头总数;0 路源台账 ≠ 本站没有摄像头/视频。
import { computed } from 'vue'
import { demoCameraCount } from '../../../shared/cameras'
import { feedOf, feedText, metaLine } from './channels'
import type { ChannelState } from './channels'

const props = defineProps<{ channels: ChannelState[]; currentId: string }>()
const emit = defineEmits<{ (e: 'select', source: string): void }>()

/** 一期演示摄像头总数 = 路段数（Z=61 / GZ=433；与源台账分开说） */
const demoCameraTotal = computed(() => demoCameraCount())

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
        <template v-if="channels.length === 0">源台账 0 路（仅初始映射）· 一期演示 {{ demoCameraTotal }} 路</template>
        <template v-else>源台账 {{ channels.length }} 路（仅初始映射）· 已导出 {{ exportedCount }}<template v-if="noSourceCount > 0">
          · 未接入视频源 {{ noSourceCount }}</template></template>
      </span>
    </div>
    <div class="td-card-body flush">
      <!-- 0 路源台账合法(IKMS1T):如实显示"仅初始映射"，并注明一期演示摄像头口径（IKNBT2） -->
      <div v-if="channels.length === 0" class="ledger-empty">
        <span class="le-l1">源台账 0 路（仅源侧初始映射）</span>
        <span class="le-l2">
          一期口径：N 段 = N 摄像头 = N 视频（演示）——本站 {{ demoCameraTotal }} 段 =
          {{ demoCameraTotal }} 路演示摄像头，视频为 mock 复用样本；本页只展示源台账通道。
        </span>
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
              {{ !c.def.hasVideo ? '源台账无视频源 · 本期留空(演示复用见大屏路段卡)' : metaLine(c.meta, c.detTotal) }}
            </div>
          </div>
        </div>
      </template>
      <p class="ledger-note">
        一期口径：<b>N 段 = N 摄像头 = N 视频（演示）</b>——本站 {{ demoCameraTotal }} 段即
        {{ demoCameraTotal }} 路演示摄像头，每路都有画面（视频为 mock 复用，同一份样本可多路复用）；
        本台账 {{ channels.length }} 路是<b>源台账/初始映射</b>，<b>不代表一期摄像头总数</b>；真实接入归 IKMHMX。
      </p>
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
        <template v-if="channels.length === 0">源台账 0 路（仅初始映射）· 一期演示 {{ demoCameraTotal }} 路（按路段数，mock 复用）</template>
        <template v-else-if="allNoSource">源台账 {{ channels.length }} 路均无独立视频源（演示复用见大屏路段卡；源台账不代表一期总数）</template>
        <template v-else>一期 · 离线样本视频（演示 mock；同一份视频可多路复用）</template>
      </p>
      <p class="line">二期 · 现场摄像头流(本期不接入)</p>
      <p class="line strong">点位与字段不变 · 只换视频源</p>
      <p class="note">
        另有「源台账未接入视频源」的通道:路网上已布点(大屏可点),但源台账侧没有独立视频源 ——
        一期按 <b>N 段 = N 摄像头 = N 视频（演示，mock 复用）</b>口径，画面用演示复用样本视频补齐；
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
/* 源台账 vs 一期演示口径的说明（IKNBT2）：贴在台账底部，常驻可见 */
.ledger-note {
  margin: 0;
  padding: 8px 12px 10px;
  border-top: 1px solid var(--td-component-stroke);
  font-size: 10px;
  line-height: 1.6;
  color: var(--td-text-color-placeholder);
}
.ledger-note b {
  color: var(--td-text-color-secondary);
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

/* ---------- 响应式（Issue IKP3EV） ---------- */
/* ≤1180：整页改为文档滚动后，左栏不再靠 .td-col 的内部滚动限高；
   台账列表保留一个合理上限 + 自身滚动（61 路时不会把监控墙推出去），其余卡片自然高度。 */
@media (max-width: 1180px) {
  .td-card-body.flush {
    max-height: 46vh;
    overflow-y: auto;
  }
  .td-card-head {
    flex-wrap: wrap;
    row-gap: 2px;
  }
  .td-card-head .td-head-tag {
    margin-left: 0;
  }
  .chan-l1 {
    flex-wrap: wrap;
    row-gap: 2px;
  }
  .chan-l1 .td-chip {
    margin-left: 0;
  }
  .chan-l3 {
    overflow-wrap: anywhere;
  }
  .kv {
    flex-wrap: wrap;
    row-gap: 1px;
  }
}
/* ≤768：说明文案 / 长值折行，不产生页面级横向滚动 */
@media (max-width: 768px) {
  .ledger-note,
  .note,
  .line,
  .kv .v {
    overflow-wrap: anywhere;
  }
}
</style>
