<script setup lang="ts">
// 监控墙:N 路摄像头**分页**展示(默认每页 12 格 = 3 列 × 4 行)。
//
// IKMS1T 去固定 6 路:登记表 N 动态(0..路段数,默认每段最多 1 路),61 路不能一屏挤爆,
// 故本组件负责 ① 分页(每页 12) ② 筛选(全部 / 有视频源 / 无视频源) ③ 0 路空态。
// 整墙共用一个抽帧时钟(设计稿口径「抽帧 1 帧 / 2 s」),各通道按自己的 fps 推进自己的帧序。
// 深色 token 只在本卡片内的画面格生效(CSS 变量下发,避免深色外溢到壳层)。
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { TD_VIDEO } from '../../../shared/theme'
import { demoCameraCount } from '../../../shared/cameras'
import MonitorCell from './MonitorCell.vue'
import type { ChannelState } from './channels'

const props = defineProps<{ channels: ChannelState[]; currentId: string; selectTick?: number }>()
const emit = defineEmits<{ (e: 'select', source: string): void }>()

const GAP = 6
const TICK_MS = 2000
/** 每页格数:3 列 × 4 行;61 路 → 6 页,不会一格挤爆 */
const PAGE_SIZE = 12

type FilterKey = 'all' | 'video' | 'novideo'

const idxMap = ref<Record<string, number>>({})
const playing = ref(true)
const speed = ref(1)
const filter = ref<FilterKey>('all')
const page = ref(1)
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

/** 通道总数 N(源台账条数;0 路合法;≠ 一期演示摄像头总数,见 demoCameraTotal) */
const total = computed(() => props.channels.length)
/** 一期演示摄像头总数 = 路段数（N 段 = N 摄像头 = N 视频，mock 复用；IKNBT2） */
const demoCameraTotal = computed(() => demoCameraCount())
/** 有视频源的通道数(登记表 has_video_source=true;不等于样本视频已导出) */
const videoCount = computed(() => props.channels.filter((c) => c.def.hasVideo).length)
/** 未接入视频源的通道数(Issue IKLX5Y) */
const noVideoCount = computed(() => total.value - videoCount.value)
/** 有视频源且服务端真返回了 meta 的通道数(未接入视频源的不算"已导出") */
const exportedCount = computed(() => props.channels.filter((c) => c.def.hasVideo && c.meta !== null).length)

const filters = computed<{ key: FilterKey; text: string; count: number }[]>(() => [
  { key: 'all', text: '全部', count: total.value },
  { key: 'video', text: '有视频源', count: videoCount.value },
  { key: 'novideo', text: '无视频源', count: noVideoCount.value },
])

/** 当前筛选下的通道(IKMS1T:61 路按"有 / 无视频源"过滤,不靠肉眼在墙上找) */
const filtered = computed<ChannelState[]>(() => {
  if (filter.value === 'video') return props.channels.filter((c) => c.def.hasVideo)
  if (filter.value === 'novideo') return props.channels.filter((c) => !c.def.hasVideo)
  return props.channels
})
const pageCount = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE_SIZE)))
/** 实际生效页码:筛选变化后条数变少时自动收口,不出现"空页" */
const safePage = computed(() => Math.min(Math.max(1, page.value), pageCount.value))
// 分页切片:每页 12 格;61 路 → 6 页(3 × 4 × 6)
const paged = computed(() => filtered.value.slice((safePage.value - 1) * PAGE_SIZE, safePage.value * PAGE_SIZE))
const rangeText = computed(() => {
  const n = filtered.value.length
  if (n === 0) return '0 路'
  const from = (safePage.value - 1) * PAGE_SIZE + 1
  const to = Math.min(safePage.value * PAGE_SIZE, n)
  return `${from}–${to} / ${n} 路`
})

const emptyHint = computed(() => {
  if (total.value === 0) {
    return `源台账 0 路（仅初始映射）· 一期演示摄像头 ${demoCameraTotal.value} 路（N 段 = N 摄像头 = N 视频，mock 复用）`
  }
  if (filter.value === 'video' && videoCount.value === 0) return `当前 ${total.value} 路都没有视频源`
  if (filter.value === 'novideo' && noVideoCount.value === 0) return `全部 ${total.value} 路都已接入视频源`
  return `切回「全部」可看 ${total.value} 路（其中 ${noVideoCount.value} 路未接入视频源）`
})

function setFilter(key: FilterKey): void {
  filter.value = key
  page.value = 1
}
function goto(p: number): void {
  page.value = Math.min(Math.max(1, p), pageCount.value)
}

// 左栏台账点选 → 监控墙跳到该路所在页;若它被当前筛选藏掉,先切回"全部"再跳。
// 监听 `selectTick`:再次点中同一路时 currentId 不变,但也要回到该页/取消筛选。
// `immediate`:61 路深链/默认选中不在第 1 页时,首屏就要落在正确页。
watch(
  [() => props.currentId, () => props.selectTick ?? 0],
  ([id]) => {
    const allIdx = props.channels.findIndex((c) => c.def.source === id)
    if (allIdx < 0) return
    const idx = filtered.value.findIndex((c) => c.def.source === id)
    if (idx >= 0) {
      page.value = Math.floor(idx / PAGE_SIZE) + 1
      return
    }
    filter.value = 'all'
    page.value = Math.floor(allIdx / PAGE_SIZE) + 1
  },
  { immediate: true },
)

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
  // 列数随断点变化（≤900 两列 / ≤560 单列），从计算样式里读实际轨道数，不再写死 3 列；
  // 三列时的取值公式与改前完全一致（(宽 - 2 个间隙) / 3），1920×1080 的缩放显示不退化。
  const tracks = (getComputedStyle(el).gridTemplateColumns || '').split(' ').filter(Boolean).length || 3
  cellW.value = el.clientWidth > 0 ? (el.clientWidth - GAP * (tracks - 1)) / tracks : 0
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
      监控墙 · {{ total }} 路
      <span class="td-head-tag">
        每页 {{ PAGE_SIZE }} 格 · 抽帧 1 帧 / 2 s · 框 = 检测输出(抽帧) · 虚线 = 越线计数线
      </span>
    </div>

    <!-- 0 路源台账合法(IKMS1T):如实说"仅初始映射"，并注明一期演示摄像头口径（IKNBT2） -->
    <div v-if="total === 0" class="wall-empty">
      <span class="we-l1">源台账 0 路（仅源侧初始映射）</span>
      <span class="we-l2">
        一期口径：N 段 = N 摄像头 = N 视频（演示）——本站 {{ demoCameraTotal }} 段 =
        {{ demoCameraTotal }} 路演示摄像头，视频为 mock 复用；本墙只展示源台账通道。
      </span>
    </div>

    <template v-else>
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
        <span class="td-seg" role="group" aria-label="按视频源筛选">
          <span
            v-for="f in filters"
            :key="f.key"
            class="td-seg-item"
            :class="{ on: filter === f.key }"
            role="button"
            :aria-pressed="filter === f.key"
            @click="setFilter(f.key)"
          >
            {{ f.text }} {{ f.count }}
          </span>
        </span>
        <!-- 顶部也放一条分页:61 路时墙体高于一屏,滚到底才能点底部分页 -->
        <span v-if="pageCount > 1" class="wall-pager top">
          <button class="td-btn sm" type="button" :disabled="safePage <= 1" @click="goto(safePage - 1)">上一页</button>
          <span class="page-info td-mono">第 {{ safePage }} / {{ pageCount }} 页</span>
          <button class="td-btn sm" type="button" :disabled="safePage >= pageCount" @click="goto(safePage + 1)">
            下一页
          </button>
        </span>
        <span class="wall-hint">
          已导出 {{ exportedCount }} / {{ total }} 路<template v-if="noVideoCount > 0">
            · 未接入视频源 {{ noVideoCount }} 路(本期留空)</template>
        </span>
      </div>

      <div ref="gridRef" class="wall-grid">
        <MonitorCell
          v-for="c in paged"
          :key="c.def.source"
          :ch="c"
          :index="indexOf(c.def.source)"
          :selected="c.def.source === currentId"
          :scale="scaleOf(c)"
          @select="emit('select', c.def.source)"
        />
      </div>

      <div v-if="filtered.length === 0" class="wall-empty small">
        <span class="we-l1">该筛选下没有通道</span>
        <span class="we-l2">{{ emptyHint }}</span>
      </div>

      <!-- 分页:61 路 → 6 页;上下各一条,滚到墙底也能翻页 -->
      <div v-if="pageCount > 1" class="wall-pager">
        <button class="td-btn sm" type="button" :disabled="safePage <= 1" @click="goto(1)">首页</button>
        <button class="td-btn sm" type="button" :disabled="safePage <= 1" @click="goto(safePage - 1)">上一页</button>
        <span class="page-info td-mono">第 {{ safePage }} / {{ pageCount }} 页 · {{ rangeText }}</span>
        <button class="td-btn sm" type="button" :disabled="safePage >= pageCount" @click="goto(safePage + 1)">
          下一页
        </button>
        <button class="td-btn sm" type="button" :disabled="safePage >= pageCount" @click="goto(pageCount)">末页</button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.wall-tools {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
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
/* 0 路 / 筛选空态:如实写明,不用编造画面占位 */
.wall-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 40px 16px;
  color: var(--td-text-color-secondary);
}
.wall-empty.small {
  padding: 12px 16px 18px;
}
.we-l1 {
  font-size: 14px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}
.we-l2 {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
.wall-pager {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid var(--td-component-stroke);
}
/* 顶部紧凑分页:并进工具条,不另占一行 */
.wall-pager.top {
  padding: 0;
  border: none;
}
.wall-pager.top .page-info {
  margin: 0;
}
.wall-hint {
  margin-left: auto;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
.page-info {
  font-size: 11px;
  color: var(--td-text-color-secondary);
  margin: 0 auto;
}

/* ---------- 响应式（Issue IKP3EV） ---------- */
/* ≤900：监控墙 3 列 → 2 列（窄屏下每格仍有足够画面尺寸） */
@media (max-width: 900px) {
  .wall-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .td-card-head {
    flex-wrap: wrap;
    row-gap: 2px;
  }
  .td-card-head .td-head-tag {
    margin-left: 0;
  }
}
/* ≤560：2 列 → 1 列；工具条 / 分页 / 空态说明按整宽换行，不横向溢出 */
@media (max-width: 560px) {
  .wall-grid {
    grid-template-columns: minmax(0, 1fr);
    padding: 8px;
  }
  .wall-tools,
  .wall-pager {
    padding: 8px;
    gap: 6px;
  }
  .wall-hint {
    margin-left: 0;
    width: 100%;
    font-size: 10px;
  }
  .wall-empty {
    padding: 24px 12px;
    text-align: center;
  }
  .we-l2 {
    overflow-wrap: anywhere;
  }
}
</style>
