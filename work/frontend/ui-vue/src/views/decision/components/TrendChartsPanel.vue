<script setup lang="ts">
// 决策层 · 变化图表（曲线图 / 竖状图 / 点线图）—— 带时间轴播放器。
//
// 业主口径：
//   2026-10-29 当面要求「能不能在决策层这里搞点变化图表来，什么曲线图、竖状图这些，
//   最好再搞点点线图来」；
//   随后追问「这个表为什么不是动态表」——**图表必须随时间轴动起来**；
//   再追问「这个动态很奇怪，为什么是这样子播放的」——看过一版逐帧生长 + 循环重播后否掉。
//
// 为什么"逐帧生长 + 循环重播"是错的（本版已改）：
//   孪生时序是 60 s 窗口的仿真计数，相邻帧几乎不相关。实测 SZ-001 的 q 序列：
//   540 → 60 → 360 → 1140 → 120 → 300 …（相邻帧跳 19 倍），对应等级 1 → 3 → 1 → 1 → 3 …
//   ——这是**抽样噪声**，不是趋势。把噪声做成 240 ms/帧的"重画 + 循环"，等于把噪声快放
//   250 倍再从头再抽一遍，观感就是抽搐 + 卡带感。所以本版：
//   ① **先平滑再画**（5 点滑动平均，只作用于曲线/轨迹的**形状**；读数行仍显示产物原始值）；
//   ② **不再逐帧生长**——曲线与轨迹一次画完整（静态形状是稳定包络），游标只是扫过去：
//      竖线移动 + 当前点高亮 + 读数跳变，不做"整张图重画"；
//   ③ **播到底就停**，不循环回卷；
//   ④ 判级跳变单独用刻度标出（顶端小点，颜色 = 升到的等级），不再混在曲线锯齿里让人误读。
//
// 数据：GET /api/traffic/segment-series（孪生侧真时序，每 60 s 一个快照）。
//
// 口径铁律（违反即不通过）：
//   ① 只用接口真实回过的点，**不插值、不补点、不脑补曲线**；点数不足 2 个如实说「暂无可用时序」；
//      平滑只改"线的画法"，不新增点、不外推，读数与占比一律回到产物原值；
//   ② 阈值虚线来自接口 /thresholds 的 grading.level_bounds（不写死）；取不到就不画那条线；
//   ③ 曲线图三条线量级差太大（q≈千辆/h、v≈几十 km/h、x≈0~1.3），各自按**全量程归一化**后叠画
//      ——归一化量程必须锁死在全量数据上，否则拖动游标时曲线会整体缩放抖动；
//   ④ 全部 is_simulated = true，图上标注「孪生仿真快照，非实测」。
import { computed, onUnmounted, ref, watch } from 'vue'
import { getTrafficSegmentSeries } from '../../../api/traffic'
import {
  formatClock,
  type SegmentRecord,
  type SegmentSeries,
  type SegmentSeriesPoint,
  type ThresholdSnapshot,
} from '../../../shared/traffic'

const props = defineProps<{
  segmentId: string
  segmentName: string
  record: SegmentRecord | null
  thresholds: ThresholdSnapshot | null
}>()

// ---------- 取数 ----------
const series = ref<SegmentSeries | null>(null)
const loading = ref(false)
const errorText = ref('')

function reasonOf(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err)
  if (raw.includes('SERIES_NOT_AVAILABLE')) return '孪生时序产物缺失（未跑孪生主循环）'
  if (raw.includes('SERIES_NOT_FOUND')) return '该路段不在孪生时序产物内'
  return raw
}

async function load(): Promise<void> {
  if (!props.segmentId) {
    series.value = null
    return
  }
  loading.value = true
  errorText.value = ''
  try {
    series.value = await getTrafficSegmentSeries(props.segmentId)
    cursor.value = 0
  } catch (err) {
    series.value = null
    errorText.value = reasonOf(err)
  } finally {
    loading.value = false
  }
}

watch(() => props.segmentId, load, { immediate: true })

const points = computed<SegmentSeriesPoint[]>(() => series.value?.series ?? [])
const all = computed(() => points.value)
const total = computed(() => points.value.length)
const hasCurve = computed(() => total.value >= 2)

/**
 * 口径错位提示：时序产物只有孪生侧一条链路（61 段全量），
 * 而快照里 2 段（SZ-005 / SZ-024）是视频检测占位的 -> 同一段会同时存在
 * 「当期值（视频口径）」与「时序曲线（孪生口径）」，数值不可直接对照，必须当面说清。
 */
const sourceMismatch = computed<boolean>(() => {
  const src = props.record?.source
  if (!src) return false
  return src !== 'twin'
})

// ---------- 时间轴播放器 ----------
/** 游标 = 当前播到第几个快照（0-based） */
const cursor = ref(0)
const playing = ref(true)
/** 每帧步进间隔（ms）：1x = 240，2x = 120 */
const stepMs = ref(240)
let timer: ReturnType<typeof setInterval> | null = null

function stopTimer(): void {
  if (timer !== null) {
    clearInterval(timer)
    timer = null
  }
}

function startTimer(): void {
  stopTimer()
  timer = setInterval(() => {
    const n = total.value
    if (n < 2) return
    // 播到最后一帧就停住，不循环回卷 —— 回卷会让人以为是「重新加载了一遍」
    if (cursor.value + 1 >= n) {
      playing.value = false
      return
    }
    cursor.value += 1
  }, stepMs.value)
}

watch(
  () => [playing.value, stepMs.value] as const,
  () => {
    if (playing.value) startTimer()
    else stopTimer()
  },
  { immediate: true },
)

onUnmounted(stopTimer)

function togglePlay(): void {
  playing.value = !playing.value
}

function setSpeed(ms: number): void {
  stepMs.value = ms
  playing.value = true
}

function onScrub(event: Event): void {
  const raw = Number((event.target as HTMLInputElement).value)
  if (Number.isFinite(raw)) cursor.value = Math.min(Math.max(0, raw), Math.max(0, total.value - 1))
  playing.value = false
}

/** 游标当前点（原始值，读数用） */
const current = computed<SegmentSeriesPoint | null>(() => all.value[cursor.value] ?? null)
const currentPhase = computed<string>(() => current.value?.phase ?? '')

// ---------- 公共几何 ----------
const CHART_W = 680
const PAD_L = 48
const PAD_R = 18
const PLOT_W = CHART_W - PAD_L - PAD_R
const CURVE_H = 176
const BAR_H = 168
const SCAT_H = 190
const PAD_T = 14
const PAD_B = 26

/** 横轴位置始终按**全量点数**算，播放时坐标轴不伸缩 */
function xAt(index: number): number {
  const n = total.value
  if (n <= 1) return PAD_L + PLOT_W / 2
  return PAD_L + (index / (n - 1)) * PLOT_W
}

function num(value: number | null | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

// ---------- ① 曲线图 ----------
/** 四级判级色（与 shared/traffic.ts 的 LEVELS 同源：0 不可用 / 1~4 畅通→严重拥堵） */
const LEVEL_COLOR = ['#8B8B8B', '#2BA471', '#E9B32E', '#E37318', '#D54941']
const UNAVAILABLE_COLOR = '#8B8B8B'

type SeriesKey = 'q_vph' | 'v_kmh' | 'x'

interface LineSpec {
  key: SeriesKey
  label: string
  unit: string
  color: string
  digits: number
  area: boolean
}

const LINE_SPECS: LineSpec[] = [
  { key: 'q_vph', label: '流量 q', unit: '辆/h', color: '#0052D9', digits: 0, area: true },
  { key: 'v_kmh', label: '车速 v', unit: 'km/h', color: '#2BA471', digits: 1, area: false },
  { key: 'x', label: '饱和度 x', unit: '', color: '#E37318', digits: 2, area: false },
]

interface CurveLine extends LineSpec {
  path: string
  areaPath: string
  min: number
  max: number
  last: number
  lastY: number
}

const curveBaseY = CURVE_H - PAD_B

/**
 * 平滑：5 点居中滑动平均，**只用于画线的形状**。
 *
 * 为什么必须平滑：孪生时序是 60 s 窗口的计数，短路段（如 44 m 的停车场内部通道）每分钟
 * 只过十几辆车，帧间抖动可达 19 倍。实测 SZ-001 的 q：540 → 60 → 360 → 1140 → 120 …
 * 直接把原始点连起来是一团噪声锯齿，再拿去做"一帧一帧重画"的动画就是抽搐。
 * 平滑到 5 点后留下趋势包络，讲「什么时候开始恶化、恶化到什么程度」才有意义。
 *
 * 边界窗口自动收窄（首尾不补零、不外推），原始值一个不丢 ——
 * 读数行、等级占比、超容量占比一律用产物原值，只有线的画法用平滑值。
 */
const SMOOTH_WINDOW = 5

function smoothSeries(pts: SegmentSeriesPoint[], key: SeriesKey): (number | null)[] {
  const raw = pts.map((p) => num(p[key]))
  const half = Math.floor(SMOOTH_WINDOW / 2)
  return raw.map((_, i) => {
    const win: number[] = []
    for (let j = i - half; j <= i + half; j += 1) {
      const v = raw[j]
      if (typeof v === 'number') win.push(v)
    }
    if (!win.length) return null
    return win.reduce((a, b) => a + b, 0) / win.length
  })
}

/** 三条线的平滑序列（换段/换数据才重算） */
const smoothCache = computed<Map<SeriesKey, (number | null)[]>>(() => {
  const pts = all.value
  const cache = new Map<SeriesKey, (number | null)[]>()
  if (pts.length < 2) return cache
  for (const spec of LINE_SPECS) cache.set(spec.key, smoothSeries(pts, spec.key))
  return cache
})

const curveLines = computed<CurveLine[]>(() => {
  const full = all.value
  if (full.length < 2) return []
  const out: CurveLine[] = []
  for (const spec of LINE_SPECS) {
    const sv = smoothCache.value.get(spec.key)
    if (!sv || sv.length < 2) continue
    // 量程锁在全量平滑序列上（不随游标变），否则拖游标时曲线会整体缩放抖动
    const finite = sv.filter((v): v is number => v !== null)
    if (finite.length < 2) continue
    const min = Math.min(...finite)
    const max = Math.max(...finite)
    const span = max - min || Math.abs(max) || 1
    const yOf = (v: number): number => PAD_T + (1 - (v - min) / span) * (curveBaseY - PAD_T)
    let path = ''
    let started = false
    let firstIdx = -1
    let lastIdx = -1
    // 曲线一次画完整（不按游标截断）：静态形状是稳定包络，游标只负责扫过高亮
    sv.forEach((v, i) => {
      if (v === null) {
        started = false
        return
      }
      path += `${started ? 'L' : 'M'}${xAt(i).toFixed(1)} ${yOf(v).toFixed(1)} `
      started = true
      if (firstIdx < 0) firstIdx = i
      lastIdx = i
    })
    const areaPath = spec.area && path && firstIdx >= 0
      ? `${path}L${xAt(lastIdx).toFixed(1)} ${curveBaseY} L${xAt(firstIdx).toFixed(1)} ${curveBaseY} Z`
      : ''
    // 端点跟随游标：y 用平滑值（贴线），读数用原始值
    const curSmooth = num(sv[cursor.value]) ?? finite[finite.length - 1] ?? 0
    const curRaw = num(full[cursor.value]?.[spec.key]) ?? curSmooth
    out.push({ ...spec, path: path.trim(), areaPath, min, max, last: curRaw, lastY: yOf(curSmooth) })
  }
  return out
})

/**
 * 判级升档事件：等级调高的那一帧。
 * 单独标出来而不是让它混在曲线锯齿里 —— 「哪一刻从缓行跳到严重拥堵」才是要讲的话。
 */
interface LevelJump {
  x: number
  level: number
  ts: string
  color: string
}

const levelJumps = computed<LevelJump[]>(() => {
  const pts = all.value
  if (pts.length < 2) return []
  const out: LevelJump[] = []
  for (let i = 1; i < pts.length; i += 1) {
    const prev = Math.round(num(pts[i - 1]?.level) ?? 0)
    const next = Math.round(num(pts[i]?.level) ?? 0)
    if (next > prev) {
      out.push({
        x: xAt(i),
        level: next,
        ts: pts[i]?.ts ?? '',
        color: LEVEL_COLOR[Math.min(4, Math.max(0, next))] ?? UNAVAILABLE_COLOR,
      })
    }
  }
  return out
})

// 运营阶段色带：连续同阶段的点并成一段
const PHASE_FILL: Record<string, string> = {
  早高峰: '#FFF0E6',
  平峰: '#EAF2FF',
  晚高峰: '#FFEAF0',
  夜间: '#EDEEF2',
}

interface PhaseBand {
  x: number
  w: number
  phase: string
  fill: string
}

const phaseBands = computed<PhaseBand[]>(() => {
  const pts = all.value
  if (pts.length < 2) return []
  const bands: PhaseBand[] = []
  let start = 0
  let phase = pts[0]?.phase ?? ''
  for (let i = 1; i <= pts.length; i += 1) {
    const next = i < pts.length ? pts[i]?.phase ?? '' : '\u0000'
    if (next !== phase || i === pts.length) {
      const x0 = xAt(start)
      const x1 = i === pts.length ? xAt(pts.length - 1) : xAt(i)
      if (phase) {
        bands.push({ x: x0, w: Math.max(1, x1 - x0), phase, fill: PHASE_FILL[phase] ?? '#F3F4F6' })
      }
      start = i
      phase = next
    }
  }
  return bands
})

// 阶段切换处的竖虚线
const phaseTicks = computed<{ x: number; label: string }[]>(() => {
  const pts = all.value
  if (pts.length < 2) return []
  const ticks: { x: number; label: string }[] = []
  for (let i = 1; i < pts.length; i += 1) {
    if (pts[i]?.phase !== pts[i - 1]?.phase) ticks.push({ x: xAt(i), label: pts[i]?.phase ?? '' })
  }
  return ticks
})

const curveAxis = computed(() => {
  const pts = all.value
  if (pts.length < 2) return { left: '', mid: '', right: '' }
  const half = Math.floor((pts.length - 1) / 2)
  return {
    left: formatClock(pts[0]?.ts ?? ''),
    mid: formatClock(pts[half]?.ts ?? ''),
    right: formatClock(pts[pts.length - 1]?.ts ?? ''),
  }
})

/** 游标在曲线图上的横坐标 */
const cursorX = computed<number>(() => xAt(cursor.value))

// ---------- ② 竖状图（阶段容量） ----------
interface PhaseBar {
  phase: string
  factor: number
  value: number
  x: number
  w: number
  y: number
  h: number
  current: boolean
}

const phaseBars = computed<PhaseBar[]>(() => {
  const cap = series.value?.capacity
  const base = num(props.record?.c_base_vph)
  if (!cap || base === null) return []
  const order = cap.phase_order ?? []
  if (!order.length) return []
  const values = order.map((ph) => base * (cap.phase_capacity_factor[ph] ?? 1))
  const maxV = Math.max(...values, base)
  const top = 18
  const bottom = BAR_H - PAD_B
  const slot = PLOT_W / order.length
  const barW = Math.min(52, slot * 0.52)
  return order.map((ph, i) => {
    const value = values[i] as number
    const h = Math.max(1, (value / maxV) * (bottom - top))
    return {
      phase: ph,
      factor: cap.phase_capacity_factor[ph] ?? 1,
      value,
      x: PAD_L + slot * i + (slot - barW) / 2,
      w: barW,
      y: bottom - h,
      h,
      current: ph === currentPhase.value,
    }
  })
})

const barBase = computed<number | null>(() => {
  const cap = series.value?.capacity
  const base = num(props.record?.c_base_vph)
  if (!cap || base === null) return null
  const values = (cap.phase_order ?? []).map((ph) => base * (cap.phase_capacity_factor[ph] ?? 1))
  const maxV = Math.max(...values, base, 1)
  const top = 18
  const bottom = BAR_H - PAD_B
  return bottom - (base / maxV) * (bottom - top)
})

// ---------- ③ 点线图（流量–饱和度轨迹） ----------
const xBounds = computed<number[]>(() => {
  const rows = props.thresholds?.rows ?? []
  const row = rows.find((r) => r.metric.includes('x') || r.metric.includes('饱和'))
  if (!row) return []
  const bounds = row.bands.filter((b) => b.level <= 3).map((b) => b.max)
  return bounds.length === 3 ? bounds : []
})

/** 坐标域锁在全量上，播放时散点不会整体漂移 */
const scatterDomain = computed(() => {
  const pts = all.value.filter((p) => num(p.q_vph) !== null && num(p.x) !== null)
  if (pts.length < 2) return { qMin: 0, qMax: 1, xMax: 1.15 }
  const qs = pts.map((p) => num(p.q_vph) as number)
  const xs = pts.map((p) => num(p.x) as number)
  return {
    qMin: Math.min(...qs),
    qMax: Math.max(...qs),
    xMax: Math.max(1.15, ...xs),
  }
})

interface ScatterDot {
  cx: number
  cy: number
  color: string
  level: number
  ts: string
  isCursor: boolean
}

const scatterDots = computed<ScatterDot[]>(() => {
  const dom = scatterDomain.value
  const qSpan = dom.qMax - dom.qMin || 1
  const bottom = SCAT_H - PAD_B
  const out: ScatterDot[] = []
  // 点云一次画完整（不平滑、不按游标截断）：轨迹的分布形状本身就是要看的信息，
  // 平滑会把"贴着阈值线上冲"这种关键形态抹平；游标只负责高亮当前点。
  all.value.forEach((p, i) => {
    const q = num(p.q_vph)
    const x = num(p.x)
    if (q === null || x === null) return
    const level = Math.round(num(p.level) ?? 0)
    out.push({
      cx: PAD_L + ((q - dom.qMin) / qSpan) * PLOT_W,
      cy: bottom - (Math.min(x, dom.xMax) / dom.xMax) * (bottom - PAD_T),
      color: LEVEL_COLOR[Math.min(4, Math.max(0, level))] ?? UNAVAILABLE_COLOR,
      level,
      ts: p.ts,
      isCursor: i === cursor.value,
    })
  })
  return out
})

const scatterPolyline = computed<string>(() =>
  scatterDots.value.map((d) => `${d.cx.toFixed(1)},${d.cy.toFixed(1)}`).join(' '),
)

function scatterYOf(value: number): number {
  const bottom = SCAT_H - PAD_B
  const xMax = scatterDomain.value.xMax || 1
  return bottom - (Math.min(value, xMax) / xMax) * (bottom - PAD_T)
}

// ---------- 读数与文案 ----------
const windowText = computed(() => {
  const s = series.value
  if (!s) return ''
  return `${s.points} 个快照 × ${Math.round(s.window_sec)} s`
})

const cursorText = computed(() => {
  const c = current.value
  if (!c) return '—'
  const atEnd = cursor.value + 1 >= total.value
  const tail = atEnd && !playing.value ? ' · 已播完' : ''
  return `${formatClock(c.ts)}（${cursor.value + 1}/${total.value}）${tail}`
})

const readout = computed(() => {
  const c = current.value
  if (!c) return []
  const lv = Math.round(num(c.level) ?? 0)
  return [
    { k: '流量 q', v: `${(num(c.q_vph) ?? 0).toFixed(0)} 辆/h` },
    { k: '车速 v', v: `${(num(c.v_kmh) ?? 0).toFixed(1)} km/h` },
    { k: '饱和度 x', v: (num(c.x) ?? 0).toFixed(3) },
    { k: '该点容量 c', v: `${(num(c.c_vph) ?? 0).toFixed(0)} 辆/h` },
    { k: '等级', v: `${LEVEL_NAME[lv] ?? '—'}` },
  ]
})

const LEVEL_NAME = ['不可用', '畅通', '缓行', '拥堵', '严重拥堵']

const levelShareText = computed<string>(() => {
  const pts = all.value.filter((p) => num(p.level) !== null)
  if (!pts.length) return '—'
  const counts = [0, 0, 0, 0, 0]
  pts.forEach((p) => {
    const lv = Math.round(num(p.level) as number)
    if (lv >= 0 && lv <= 4) counts[lv] = (counts[lv] ?? 0) + 1
  })
  return LEVEL_NAME.map((n, i) =>
    counts[i] ? `${n} ${(((counts[i] as number) / pts.length) * 100).toFixed(0)}%` : '',
  )
    .filter(Boolean)
    .join(' · ')
})

const overCapacityShare = computed<string>(() => {
  const pts = all.value.filter((p) => num(p.x) !== null)
  if (!pts.length) return '—'
  const over = pts.filter((p) => (num(p.x) as number) > 1).length
  return `${((over / pts.length) * 100).toFixed(0)}%`
})
</script>

<template>
  <section class="trend">
    <header class="trend-head">
      <div class="trend-title">
        变化图表
        <span class="trend-sub">{{ segmentName }} · 孪生真时序</span>
      </div>
      <div class="trend-meta">
        <span v-if="windowText">{{ windowText }}</span>
        <span v-if="currentPhase" class="phase-tag">{{ currentPhase }}</span>
      </div>
    </header>

    <p v-if="loading" class="trend-note">正在读取孪生时序…</p>
    <p v-else-if="errorText" class="trend-note warn">时序不可用：{{ errorText }}（不画替代曲线）</p>
    <p v-else-if="!hasCurve" class="trend-note">该路段暂无可用时序（快照点不足 2 个），不画替代曲线。</p>
    <p v-if="sourceMismatch && hasCurve" class="trend-note warn">
      口径提示：本段当前快照来自「{{ record?.source }}」检测，下图曲线来自孪生仿真，
      两者不是同一把尺子，<b>不可直接对照</b>（讲解时以面板当期值为准，曲线只看走势）。
    </p>

    <!-- 时间轴播放器 -->
    <div v-if="hasCurve" class="player">
      <button class="player-btn" type="button" :title="playing ? '暂停' : '播放'" @click="togglePlay">
        <span v-if="playing">❚❚</span>
        <span v-else>▶</span>
      </button>
      <input
        class="player-range"
        type="range"
        :min="0"
        :max="Math.max(0, total - 1)"
        :value="cursor"
        @input="onScrub"
      />
      <span class="player-clock td-mono">{{ cursorText }}</span>
      <button class="player-speed" :class="{ on: stepMs === 240 }" type="button" @click="setSpeed(240)">1×</button>
      <button class="player-speed" :class="{ on: stepMs === 120 }" type="button" @click="setSpeed(120)">2×</button>
    </div>

    <!-- 游标读数（产物原值，不做平滑） -->
    <div v-if="hasCurve" class="readout">
      <span class="readout-item readout-origin">
        <span class="readout-k">该帧原值</span>
      </span>
      <span v-for="r in readout" :key="r.k" class="readout-item">
        <span class="readout-k">{{ r.k }}</span>
        <span class="readout-v td-mono">{{ r.v }}</span>
      </span>
    </div>

    <!-- ① 曲线图 -->
    <div v-if="hasCurve" class="chart-block">
      <div class="chart-cap">
        <span class="chart-cap-t">① 曲线 · 流量 / 车速 / 饱和度随时间</span>
        <span class="chart-cap-n">
          各线按全量程归一化叠画，已做 5 点滑动平均（原始 60 s 窗口计数抖动大，不平滑看不出趋势）；
          顶端小点 = 判级升档的那一帧，颜色 = 升到的等级；竖实线是播放游标
        </span>
      </div>
      <svg class="chart" :viewBox="`0 0 ${CHART_W} ${CURVE_H}`" role="img"
           :aria-label="`${segmentId} 流量车速饱和度时序曲线`">
        <g>
          <rect v-for="(b, i) in phaseBands" :key="`band-${i}`" :x="b.x" :y="PAD_T" :width="b.w"
                :height="curveBaseY - PAD_T" :fill="b.fill" />
        </g>
        <g>
          <line v-for="(t, i) in phaseTicks" :key="`tick-${i}`" :x1="t.x" :y1="PAD_T" :x2="t.x"
                :y2="curveBaseY" stroke="#C6CBD4" stroke-width="1" stroke-dasharray="3 3" />
        </g>
        <line :x1="PAD_L" :y1="curveBaseY" :x2="CHART_W - PAD_R" :y2="curveBaseY" stroke="#D9DDE3" stroke-width="1" />
        <g v-for="line in curveLines" :key="line.key">
          <path v-if="line.areaPath" :d="line.areaPath" :fill="line.color" fill-opacity="0.10" />
          <path :d="line.path" fill="none" :stroke="line.color" stroke-width="1.8"
                stroke-linejoin="round" stroke-linecap="round" />
          <circle :cx="cursorX" :cy="line.lastY" r="2.8" :fill="line.color" />
        </g>
        <!-- 判级升档刻度：等级调高的那一帧（单列出来讲，不跟曲线锯齿混在一起） -->
        <g v-for="(j, i) in levelJumps" :key="`jump-${i}`">
          <line :x1="j.x" :y1="PAD_T" :x2="j.x" :y2="curveBaseY" :stroke="j.color"
                stroke-width="1" stroke-opacity="0.26" stroke-dasharray="2 3" />
          <circle :cx="j.x" :cy="PAD_T + 5" r="2.2" :fill="j.color" fill-opacity="0.85">
            <title>{{ formatClock(j.ts) }} · 升到 {{ LEVEL_NAME[j.level] ?? '—' }}</title>
          </circle>
        </g>
        <!-- 播放游标 -->
        <line :x1="cursorX" :y1="PAD_T" :x2="cursorX" :y2="curveBaseY" stroke="#1F2329" stroke-width="1"
              stroke-opacity="0.45" />
        <text :x="PAD_L" :y="CURVE_H - 8" class="axis" text-anchor="start">{{ curveAxis.left }}</text>
        <text :x="PAD_L + PLOT_W / 2" :y="CURVE_H - 8" class="axis" text-anchor="middle">{{ curveAxis.mid }}</text>
        <text :x="CHART_W - PAD_R" :y="CURVE_H - 8" class="axis" text-anchor="end">{{ curveAxis.right }}</text>
      </svg>
      <div class="legend">
        <span v-for="line in curveLines" :key="`lg-${line.key}`" class="legend-item">
          <i class="legend-dot" :style="{ background: line.color }" />
          {{ line.label }}
          <span class="legend-range">
            {{ line.min.toFixed(line.digits) }}–{{ line.max.toFixed(line.digits) }}{{ line.unit ? ` ${line.unit}` : '' }}
          </span>
        </span>
      </div>
    </div>

    <!-- ② 竖状图 -->
    <div v-if="hasCurve && phaseBars.length" class="chart-block">
      <div class="chart-cap">
        <span class="chart-cap-t">② 竖状 · 各运营阶段的有效通行能力</span>
        <span class="chart-cap-n">虚线 = 路型基线 c_base（不随阶段变），柱 = c_base × 阶段系数，蓝柱跟随游标换阶段</span>
      </div>
      <svg class="chart" :viewBox="`0 0 ${CHART_W} ${BAR_H}`" role="img"
           :aria-label="`${segmentId} 各阶段有效通行能力`">
        <line :x1="PAD_L" :y1="BAR_H - PAD_B" :x2="CHART_W - PAD_R" :y2="BAR_H - PAD_B"
              stroke="#D9DDE3" stroke-width="1" />
        <line v-if="barBase !== null" :x1="PAD_L" :y1="barBase" :x2="CHART_W - PAD_R" :y2="barBase"
              stroke="#8B8B8B" stroke-width="1" stroke-dasharray="5 4" />
        <text v-if="barBase !== null" :x="CHART_W - PAD_R" :y="barBase - 4" class="axis" text-anchor="end">
          基线 {{ Math.round(props.record?.c_base_vph ?? 0) }}
        </text>
        <g v-for="b in phaseBars" :key="b.phase">
          <rect :x="b.x" :y="b.y" :width="b.w" :height="b.h" rx="3"
                :fill="b.current ? '#0052D9' : '#C9D6EA'" :fill-opacity="b.current ? 0.9 : 0.75" />
          <text :x="b.x + b.w / 2" :y="b.y - 5" class="bar-val" text-anchor="middle">
            {{ Math.round(b.value) }}
          </text>
          <text :x="b.x + b.w / 2" :y="BAR_H - 10" class="axis" text-anchor="middle">
            {{ b.phase }}<tspan v-if="b.current"> ·当前</tspan>
          </text>
          <text :x="b.x + b.w / 2" :y="BAR_H - 1" class="bar-factor" text-anchor="middle">
            ×{{ b.factor.toFixed(2) }}
          </text>
        </g>
      </svg>
    </div>

    <!-- ③ 点线图 -->
    <div v-if="hasCurve && scatterDots.length" class="chart-block">
      <div class="chart-cap">
        <span class="chart-cap-t">③ 点线 · 流量–饱和度轨迹（游标高亮当前点）</span>
        <span class="chart-cap-n">横轴 = 流量 q，纵轴 = 饱和度 x；灰虚线 = 1/2/3 档上界，越线即升级；点色 = 该帧判级，黑框点是游标当前帧</span>
      </div>
      <svg class="chart" :viewBox="`0 0 ${CHART_W} ${SCAT_H}`" role="img"
           :aria-label="`${segmentId} 流量饱和度轨迹散点`">
        <g v-for="(bound, i) in xBounds" :key="`xb-${i}`">
          <line :x1="PAD_L" :y1="scatterYOf(bound)" :x2="CHART_W - PAD_R" :y2="scatterYOf(bound)"
                stroke="#B7BDC7" stroke-width="1" stroke-dasharray="5 4" />
          <text :x="PAD_L - 6" :y="scatterYOf(bound) + 3" class="axis" text-anchor="end">
            {{ bound.toFixed(2) }}
          </text>
        </g>
        <line :x1="PAD_L" :y1="SCAT_H - PAD_B" :x2="CHART_W - PAD_R" :y2="SCAT_H - PAD_B"
              stroke="#D9DDE3" stroke-width="1" />
        <polyline :points="scatterPolyline" fill="none" stroke="#BFC6D2" stroke-width="1.2" />
        <circle v-for="(d, i) in scatterDots" :key="`dot-${i}`" :cx="d.cx" :cy="d.cy"
                :r="d.isCursor ? 4.6 : 2.6" :fill="d.color" :fill-opacity="d.isCursor ? 1 : 0.9"
                :stroke="d.isCursor ? '#1F2329' : 'none'" stroke-width="1">
          <title>{{ formatClock(d.ts) }} · x 级 {{ d.level }}</title>
        </circle>
        <text :x="PAD_L" :y="SCAT_H - 8" class="axis" text-anchor="start">
          q {{ scatterDomain.qMin.toFixed(0) }}
        </text>
        <text :x="CHART_W - PAD_R" :y="SCAT_H - 8" class="axis" text-anchor="end">
          q {{ scatterDomain.qMax.toFixed(0) }} 辆/h
        </text>
      </svg>
      <div class="legend">
        <span class="legend-item"><i class="legend-dot" style="background:#2BA471" />畅通</span>
        <span class="legend-item"><i class="legend-dot" style="background:#E9B32E" />缓行</span>
        <span class="legend-item"><i class="legend-dot" style="background:#E37318" />拥堵</span>
        <span class="legend-item"><i class="legend-dot" style="background:#D54941" />严重拥堵</span>
        <span class="legend-item legend-gap">全程超容量(x&gt;1) 占 {{ overCapacityShare }}</span>
      </div>
    </div>

    <p v-if="hasCurve" class="trend-foot">
      全程等级占比：{{ levelShareText }} —— 等级按四项并列取最高（饱和度 x / 车速 v / 排队 L_q / 消散 T_d），
      所以会出现「x 未超线但车速很低 → 判拥堵」的时段。<br />
      口径：孪生仿真快照，非实测；曲线做过 5 点滑动平均仅用于呈现趋势，读数行与占比统计均为产物原值，
      不插值、不外推。单帧抖动（60 s 窗口计数，短路段帧间可跳十几倍）不作为判断依据。
    </p>
  </section>
</template>

<style scoped>
.trend {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.trend-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.trend-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}
.trend-sub {
  margin-left: 6px;
  font-size: 11px;
  font-weight: 400;
  color: var(--td-text-color-secondary);
}
.trend-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
  white-space: nowrap;
}
.phase-tag {
  display: inline-block;
  padding: 0 5px;
  border-radius: 3px;
  background: var(--td-brand-color-light);
  color: var(--td-brand-color);
  font-size: 10px;
  line-height: 16px;
}
.trend-note {
  margin: 2px 0 0;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
.trend-note.warn {
  color: var(--td-warning-color, #e37318);
}

/* 时间轴播放器 */
.player {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 8px;
  border-radius: 4px;
  background: var(--td-bg-color-container-hover, #f5f6f8);
}
.player-btn {
  width: 24px;
  height: 24px;
  border: 1px solid var(--td-component-stroke);
  border-radius: 4px;
  background: #fff;
  color: var(--td-text-color-primary);
  font-size: 10px;
  line-height: 1;
  cursor: pointer;
  flex: none;
}
.player-btn:hover {
  border-color: var(--td-brand-color);
  color: var(--td-brand-color);
}
.player-range {
  flex: 1 1 auto;
  min-width: 60px;
  accent-color: var(--td-brand-color, #0052d9);
  cursor: pointer;
}
.player-clock {
  font-size: 11px;
  color: var(--td-text-color-secondary);
  white-space: nowrap;
}
.player-speed {
  padding: 0 6px;
  height: 20px;
  border: 1px solid var(--td-component-stroke);
  border-radius: 3px;
  background: #fff;
  color: var(--td-text-color-secondary);
  font-size: 10px;
  cursor: pointer;
  flex: none;
}
.player-speed.on {
  border-color: var(--td-brand-color);
  color: var(--td-brand-color);
  background: var(--td-brand-color-light);
}

/* 游标读数 */
.readout {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  font-size: 11px;
}
.readout-item {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
}
.readout-k {
  color: var(--td-text-color-placeholder);
}
.readout-v {
  color: var(--td-text-color-primary);
}
/* 「该帧原值」小标签：说明这一行没有参与曲线平滑 */
.readout-origin {
  padding: 0 6px;
  border-radius: 3px;
  background: var(--td-bg-color-component, #f3f4f6);
}
.readout-origin .readout-k {
  color: var(--td-text-color-secondary, #666);
}

.chart-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 6px;
  border-top: 1px dashed var(--td-component-stroke);
}
.chart-cap {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
}
.chart-cap-t {
  font-size: 12px;
  color: var(--td-text-color-primary);
}
.chart-cap-n {
  font-size: 10px;
  color: var(--td-text-color-placeholder);
}
.chart {
  width: 100%;
  max-width: 100%;
  height: auto;
  display: block;
}
.axis {
  font-size: 9px;
  fill: var(--td-text-color-placeholder);
}
.bar-val {
  font-size: 9px;
  fill: var(--td-text-color-secondary);
}
.bar-factor {
  font-size: 8px;
  fill: var(--td-text-color-placeholder);
}
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  font-size: 10px;
  color: var(--td-text-color-secondary);
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.legend-gap {
  margin-left: auto;
  color: var(--td-text-color-placeholder);
}
.legend-dot {
  width: 7px;
  height: 7px;
  border-radius: 2px;
  display: inline-block;
}
.legend-range {
  color: var(--td-text-color-placeholder);
  font-variant-numeric: tabular-nums;
}
.trend-foot {
  margin: 2px 0 0;
  font-size: 10px;
  color: var(--td-text-color-placeholder);
  line-height: 1.6;
}
</style>
