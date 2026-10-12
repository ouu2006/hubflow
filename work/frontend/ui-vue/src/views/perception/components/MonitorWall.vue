<script setup lang="ts">
// 监控墙:6 格(3×2)样本视频抽帧墙。整墙共用一个抽帧时钟(设计稿口径「抽帧 1 帧 / 2 s」),
// 各通道按自己的 fps 推进自己的帧序,故六格帧号各自独立。
// 深色 token 只在本卡片内的画面格生效(CSS 变量下发,避免深色外溢到壳层)。
import { onMounted, onUnmounted, ref } from 'vue'
import { TD_VIDEO } from '../../../shared/theme'
import MonitorCell from './MonitorCell.vue'
import type { ChannelState } from './channels'

const props = defineProps<{ channels: ChannelState[]; currentId: string }>()
const emit = defineEmits<{ (e: 'select', source: string): void }>()

const GAP = 6
const TICK_MS = 2000

const idxMap = ref<Record<string, number>>({})
const playing = ref(true)
const speed = ref(1)
const gridRef = ref<HTMLElement | null>(null)
const cellW = ref(0)
let timer = 0
let ro: ResizeObserver | null = null

const SPEEDS = [1, 2, 4]

// 深色例外 token:仅本卡片内的画面格引用这些变量(对象字面量不加显式 Record 注解,便于 :style 绑定)
const videoVars = {
  '--v-bg': TD_VIDEO.bg,
  '--v-bg1': TD_VIDEO.bg1,
  '--v-bg2': TD_VIDEO.bg2,
  '--v-line': TD_VIDEO.line,
  '--v-dim': TD_VIDEO.dim,
  '--v-text': TD_VIDEO.text,
  '--v-textdim': TD_VIDEO.textDim,
  '--v-brand': TD_VIDEO.brand,
}

const exported = () => props.channels.filter((c) => c.meta !== null).length

function tick(): void {
  if (!playing.value) return
  const next: Record<string, number> = { ...idxMap.value }
  for (const c of props.channels) {
    const m = c.meta
    if (!m || m.total_frames <= 0) continue
    const step = Math.max(1, Math.round(m.fps * 2 * speed.value))
    const cur = next[c.def.source] ?? 0
    next[c.def.source] = (cur + step) % m.total_frames
  }
  idxMap.value = next
}

function measure(): void {
  const el = gridRef.value
  if (!el) return
  cellW.value = el.clientWidth > 0 ? (el.clientWidth - GAP * 2) / 3 : 0
}

function indexOf(source: string): number {
  return idxMap.value[source] ?? 0
}

function scaleOf(c: ChannelState): number | null {
  if (!c.meta || cellW.value <= 0) return null
  return cellW.value / c.meta.width
}

onMounted(() => {
  measure()
  if (typeof ResizeObserver !== 'undefined' && gridRef.value) {
    ro = new ResizeObserver(measure)
    ro.observe(gridRef.value)
  }
  timer = window.setInterval(tick, TICK_MS)
})

onUnmounted(() => {
  if (ro) ro.disconnect()
  window.clearInterval(timer)
})
</script>

<template>
  <section class="td-card" :style="videoVars">
    <div class="td-card-head">
      监控墙 · 6 路样本视频
      <span class="td-head-tag">抽帧 1 帧 / 2 s · 框 = 检测输出(抽帧) · 虚线 = 越线计数线</span>
    </div>
    <div class="wall-tools">
      <button class="td-btn sm" type="button" @click="playing = !playing">
        {{ playing ? '暂停' : '播放' }}
      </button>
      <span class="td-seg" role="group" aria-label="抽帧倍速">
        <span
          v-for="s in SPEEDS"
          :key="s"
          class="td-seg-item"
          :class="{ on: speed === s }"
          role="button"
          :aria-pressed="speed === s"
          @click="speed = s"
        >
          {{ s }}×
        </span>
      </span>
      <span class="wall-hint">已导出 {{ exported() }} / 6 路 · 未导出通道显示深色占位</span>
    </div>
    <div ref="gridRef" class="wall-grid">
      <MonitorCell
        v-for="c in channels"
        :key="c.def.source"
        :ch="c"
        :index="indexOf(c.def.source)"
        :selected="c.def.source === currentId"
        :scale="scaleOf(c)"
        @select="emit('select', c.def.source)"
      />
    </div>
  </section>
</template>

<style scoped>
.wall-tools {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--td-component-stroke);
}
.wall-hint {
  margin-left: auto;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
.wall-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  grid-auto-rows: min-content;
  gap: 6px;
  padding: 10px 12px;
}
</style>
