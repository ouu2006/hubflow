<script setup lang="ts">
// 左栏:摄像头台账(N 路 = 源台账 + 演示层 = 路段数,2026-10-25 起;可用性以 /perception-api/streams
// 实际返回判定)+ 跟踪环节清单。左栏自身滚动;数字一律取 meta;
// 服务未提供的环节(透视标定 / 越线计数 / 判级)显示「—」并注明出处。
//
// 口径(业主 2026-10-25):**N 段 = N 摄像头 = N 视频(演示)**落到页面——路段有多少摄像头,
// 台账与监控墙就有多少路;自有源通道标「已导出/未导出」,演示复用通道标「演示复用」
// (画面来自公开样本视频确定性复用,不是该摄像头自己的视频;真实接入归 IKMHMX)。
import { computed } from 'vue'
import { feedOf, feedText, metaLine } from './channels'
import type { ChannelState } from './channels'

const props = defineProps<{ channels: ChannelState[]; currentId: string }>()
const emit = defineEmits<{ (e: 'select', source: string): void }>()

/** 源台账条数(demo !== true;仅初始映射) */
const ledgerCount = computed(() => props.channels.filter((c) => c.def.demo !== true).length)
/** 演示层条数(demo === true,来自 camera-plan 每段一行) */
const demoCount = computed(() => props.channels.filter((c) => c.def.demo === true).length)
/** 有画面且服务端真返回了 meta 的通道数(自有源 + 演示复用都算) */
const exportedCount = computed(
  () => props.channels.filter((c) => (c.def.hasVideo || c.def.reuseOf) && c.meta !== null).length,
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
  if (f === 'reuse' && c.def.source === props.currentId) return { text: '演示复用 · 检测中', cls: 'warn' }
  return feedText(c)
}
</script>

<template>
  <section class="td-card">
    <div class="td-card-head">
      摄像头台账
      <span class="td-head-tag">
        <template v-if="channels.length === 0">本站 0 路（未布点站合法）</template>
        <template v-else>{{ channels.length }} 路 = 源台账 {{ ledgerCount }} + 演示层 {{ demoCount }} · 有画面 {{ exportedCount }}</template>
      </span>
    </div>
    <div class="td-card-body flush">
      <!-- 0 路合法(IKMS1T):未布点站如实空态 -->
      <div v-if="channels.length === 0" class="ledger-empty">
        <span class="le-l1">本站 0 路摄像头</span>
        <span class="le-l2">未布点站合法（IKMS1T：0 路合法）；布点后台账按路段数出全量行。</span>
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
              <span class="src">· {{ c.def.camId ?? c.def.source }}</span>
              <span class="td-chip" :class="stateOf(c).cls">{{ stateOf(c).text }}</span>
            </div>
            <div class="chan-l2">{{ c.def.segmentId }} {{ c.def.name }}</div>
            <div class="chan-l3 td-mono">
              {{
                !c.def.hasVideo && c.def.reuseOf
                  ? `演示复用 ← ${c.def.reuseOf} · ${metaLine(c.meta, c.detTotal)}`
                  : !c.def.hasVideo
                    ? '源台账无视频源 · 本期留空'
                    : metaLine(c.meta, c.detTotal)
              }}
            </div>
          </div>
        </div>
      </template>
      <p class="ledger-note">
        一期口径：<b>N 段 = N 摄像头 = N 视频（演示）</b>——路段有多少摄像头，台账与监控墙就有多少路
        （本站 {{ channels.length }} 路 = 源台账 {{ ledgerCount }} + 演示层 {{ demoCount }}）；
        「演示复用」的画面来自公开样本视频（road2 / track1）确定性复用、<b>不是该摄像头自己的视频</b>；
        真实接入归 IKMHMX。
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
        <template v-if="channels.length === 0">本站 0 路摄像头（未布点站合法）</template>
        <template v-else>一期 · {{ channels.length }} 路 = {{ channels.length }} 段（N 段 = N 摄像头 = N 视频，演示）；画面为公开样本视频自有源或演示复用</template>
      </p>
      <p class="line">二期 · 现场摄像头流(本期不接入)</p>
      <p class="line strong">点位与字段不变 · 只换视频源</p>
      <p class="note">
        「演示复用」的通道:路网上已布点、画面取公开样本视频(road2 / track1)确定性复用 ——
        它<b>有画面</b>,但不是该摄像头自己的视频;与「未导出」(有自有样本视频、服务端还没处理)
        和「未接入视频源」(老包,两者皆无)不是一回事,故分档显示。
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
