<script setup lang="ts">
// 监控墙单格:一帧抽帧画面 + SVG 检测框覆盖层 + 越线计数线 + 底部口径行。
// 深色例外仅限本格(画面区);框色走 CLASS_COLORS(与等级四级色解耦),线色走 TD_VIDEO.brand。
// 越线计数是感知服务当前**未提供**的字段 → 格内如实标「越线计数:未提供」,不画推算值。
import { computed } from 'vue'
import { perceptionFrameUrl } from '../../../api/perception'
import { TD_VIDEO } from '../../../shared/theme'
import { COUNT_LINE_POS, classColorOf, classCountsOf, frameAt, trackCountOf, vehicleKeyOf } from './channels'
import type { ChannelState } from './channels'

const props = defineProps<{
  ch: ChannelState
  /** 0 基帧序号(抽帧位) */
  index: number
  selected: boolean
  /** 画面在当前格内的显示缩放(媒体宽 ÷ 源宽);未测到为 null */
  scale: number | null
}>()

const emit = defineEmits<{ (e: 'select'): void }>()

const meta = computed(() => props.ch.meta)
const classNames = computed(() => meta.value?.class_names ?? {})
const dets = computed(() => frameAt(props.ch.det, props.index))

/**
 * 格内状态。⚠️「未接入视频源」必须与「未导出」分开(Issue IKLX5Y):
 * 前者是"这条路还没接视频",后者是"有样本视频、服务端没处理"。合成一句会误导。
 */
const status = computed(() => {
  if (!props.ch.def.hasVideo) return '未接入视频源'
  if (!meta.value) return '未导出'
  if (props.ch.detFailed) return '检测读取失败'
  return props.selected ? '检测中' : '就绪'
})

/** 没有视频源的通道:格内显示留空窗占位(不报错、不白屏) */
const noSource = computed(() => !props.ch.def.hasVideo)

const url = computed(() =>
  meta.value && !noSource.value ? perceptionFrameUrl(props.ch.def.source, props.index + 1) : null,
)

// 画面区尺寸取源分辨率(缺 meta 时给占位尺寸);模板只引用这两个 computed,避免在模板里对 meta 做空值收窄
const vbW = computed(() => meta.value?.width ?? 960)
const vbH = computed(() => meta.value?.height ?? 600)
const mediaStyle = computed(() => ({ aspectRatio: `${vbW.value} / ${vbH.value}` }))
const viewBox = computed(() => `0 0 ${vbW.value} ${vbH.value}`)
const lineY = computed(() => Math.round(vbH.value * COUNT_LINE_POS))

interface Box {
  x: number
  y: number
  w: number
  h: number
  color: string
  label: string
}

// 归一化坐标(0~1)→ 百分比定位;框顶标签 = 类别 · 置信度(两位小数,设计稿去前导零)
const boxes = computed<Box[]>(() => {
  const list = dets.value
  if (!list) return []
  return list.map((d) => {
    const [x1, y1, x2, y2, cls, conf] = d
    const name = classNames.value[String(cls)] ?? `类${cls}`
    const key = vehicleKeyOf(cls, name)
    return {
      x: x1 * 100,
      y: y1 * 100,
      w: (x2 - x1) * 100,
      h: (y2 - y1) * 100,
      color: classColorOf(cls, name),
      label: `${key ?? name} ${conf.toFixed(2).replace(/^0/, '')}`,
    }
  })
})

const trackCount = computed(() => trackCountOf(dets.value))
const classLine = computed(() => {
  const rows = classCountsOf(dets.value, classNames.value)
  return rows.length > 0 ? rows.map((r) => `${r.short} ${r.count}`).join(' · ') : '本帧无检出'
})
const scaleText = computed(() => (props.scale === null ? '—' : `${props.scale.toFixed(2)}×`))
</script>

<template>
  <div class="cell" :class="{ on: selected }" @click="emit('select')">
    <div class="cell-top">
      <span class="ct-name">{{ ch.def.cid }} · {{ ch.def.source }}</span>
      <span
        class="ct-state"
        :class="{ live: selected && !noSource && meta !== null && !ch.detFailed, err: ch.detFailed, off: meta === null || noSource }"
      >
        {{ status }}
      </span>
    </div>

    <!-- 空窗占位(业主 2026-10-15:视频样本先不弄) -->
    <template v-if="noSource">
      <div class="cell-media cell-nosource" :style="mediaStyle">
        <span class="ns-l1">未接入视频源</span>
        <span class="ns-l2">本期留空 · 路网上已布点</span>
      </div>
      <div class="cell-foot">
        <span class="cf-classes">—</span>
        <span class="cf-cnt">越线计数:未提供</span>
      </div>
      <div class="cell-sub">{{ ch.def.cid }} · {{ ch.def.source }} · 缩放 — · 帧 — · 轨迹 —</div>
    </template>

    <template v-else-if="meta">
      <div class="cell-media" :style="mediaStyle">
        <img v-if="url" class="cm-img" :src="url" :alt="`${ch.def.cid} 抽帧画面`" />
        <svg class="cm-svg" :viewBox="viewBox" preserveAspectRatio="xMidYMid meet">
          <line
            x1="0"
            :y1="lineY"
            :x2="vbW"
            :y2="lineY"
            :stroke="TD_VIDEO.brand"
            stroke-width="1.5"
            stroke-dasharray="9 7"
            vector-effect="non-scaling-stroke"
          />
          <rect
            v-for="(b, i) in boxes"
            :key="i"
            :x="(b.x / 100) * vbW"
            :y="(b.y / 100) * vbH"
            :width="(b.w / 100) * vbW"
            :height="(b.h / 100) * vbH"
            :stroke="b.color"
            fill="none"
            stroke-width="1.6"
            vector-effect="non-scaling-stroke"
          />
        </svg>
        <span
          v-for="(b, i) in boxes"
          :key="`l${i}`"
          class="cm-label"
          :style="{ left: `${b.x}%`, top: `${b.y}%`, color: b.color }"
        >
          {{ b.label }}
        </span>
      </div>
      <div class="cell-foot">
        <span class="cf-classes">{{ ch.detFailed ? '检测读取失败' : classLine }}</span>
        <span class="cf-cnt">越线计数:未提供</span>
      </div>
      <div class="cell-sub">
        <template v-if="ch.detFailed">检测接口读取失败 · 无框可画(不是"本帧无检出")</template>
        <template v-else>
          {{ ch.def.cid }} · {{ ch.def.source }} · 缩放 {{ scaleText }} · 帧 {{ index + 1 }} · 轨迹
          {{ trackCount }}
        </template>
      </div>
    </template>

    <template v-else>
      <div class="cell-media cell-empty" :style="mediaStyle">
        <span>未导出 · 样本视频未处理</span>
      </div>
      <div class="cell-foot">
        <span class="cf-classes">—</span>
        <span class="cf-cnt">越线计数:未提供</span>
      </div>
      <div class="cell-sub">{{ ch.def.cid }} · {{ ch.def.source }} · 缩放 — · 帧 — · 轨迹 —</div>
    </template>
  </div>
</template>

<style scoped>
.cell {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--v-line);
  border-radius: var(--td-radius-sm);
  overflow: hidden;
  background: var(--v-bg);
  cursor: pointer;
}
/* 当前选中格 = 「当前」语义 → 品牌浅蓝描边(画面区唯一允许的交互态色) */
.cell.on {
  border-color: var(--v-brand);
  box-shadow: 0 0 0 1px var(--v-brand);
}
.cell-top {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  background: var(--v-bg1);
}
.ct-name {
  font-size: 10px;
  color: var(--v-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ct-state {
  margin-left: auto;
  font-size: 10px;
  color: var(--v-textdim);
}
.ct-state.live {
  color: var(--v-brand);
}
.ct-state.err {
  color: #e37318;
}
.ct-state.off {
  color: var(--v-dim);
}
.cell-media {
  position: relative;
  width: 100%;
  background: #000;
  overflow: hidden;
}
.cm-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.cm-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.cm-label {
  position: absolute;
  transform: translateY(-100%);
  font-family: var(--td-font-family-mono);
  font-size: 9px;
  line-height: 1.1;
  white-space: nowrap;
  text-shadow: 0 0 3px #000;
  pointer-events: none;
}
.cell-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--v-dim);
  font-size: 11px;
}
/* 空窗占位:比"未导出"更中性(不是故障,是本期没接视频) */
.cell-nosource {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  background: #14181c;
  color: var(--v-dim);
}
.ns-l1 {
  font-size: 12px;
  color: var(--v-textdim);
}
.ns-l2 {
  font-size: 10px;
  color: var(--v-dim);
}
.cell-foot {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 6px;
  background: var(--v-bg1);
  font-family: var(--td-font-family-mono);
  font-size: 10px;
  color: var(--v-text);
}
.cf-classes {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cf-cnt {
  margin-left: auto;
  color: var(--v-dim);
  white-space: nowrap;
}
.cell-sub {
  padding: 2px 6px 4px;
  background: var(--v-bg1);
  font-family: var(--td-font-family-mono);
  font-size: 10px;
  line-height: 1.35;
  color: var(--v-textdim);
  word-break: break-word;
}

/* ---------- 响应式（Issue IKP3EV） ---------- */
/* ≤900：监控墙两列后画面区设最小高度，避免窄屏把 16:9 画面压成细条；
   标题行 / 指标行允许换行，不顶破格宽。aspect-ratio 仍按源分辨率（960×600 ≈ 16:10）由行内样式给定。 */
@media (max-width: 900px) {
  .cell-media {
    min-height: 160px;
  }
  .cell-top {
    flex-wrap: wrap;
    row-gap: 2px;
  }
  .cell-foot {
    flex-wrap: wrap;
    row-gap: 1px;
  }
}
/* ≤560：单列，画面区保持 16:9 观感所需的最小高度 */
@media (max-width: 560px) {
  .cell-media {
    min-height: 180px;
  }
  .ct-name {
    font-size: 11px;
  }
  .cf-cnt {
    margin-left: 0;
  }
}
</style>
