<script setup lang="ts">
// 感知层 · YOLO 路面监控(Issue #54,三层前端之一):
//   左 = 监控画面(样本视频帧序列 + 逐帧检测框/轨迹叠加,数据来自感知演示服务
//        work/perception/server.py,由 dump_monitor_data.py 离线 MindSpore 推理导出);
//   右 = 检测通道 + 实时检测统计;下 = video/twin 双链路指标快照(TC-19 口径)。
// 口径:画面是样本视频离线回放(非本站现场、非实时流);检测框/轨迹为一期接口面
//   新增形状(非契约 v2.0 字段);路段指标仍为契约 mock 快照。页面不出现"实时画面/实测"。
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { getTrafficSegments, subscribeTrafficSnapshot } from '../../api/traffic'
import {
  getPerceptionDetections,
  getPerceptionStreams,
  perceptionFrameUrl,
  type Detection,
  type DetectionFrame,
  type PerceptionDetections,
  type PerceptionStreamMeta,
} from '../../api/perception'
import { demoSegment } from '../../shared/demoNetwork'
import { isStale, levelStyle, type SegmentRecord, type TrafficSource } from '../../shared/traffic'
import LevelBadge from '../dashboard/components/LevelBadge.vue'

// ---------- 路段指标快照(契约 mock,与态势大屏同源) ----------
const segments = ref<SegmentRecord[]>([])
const live = ref(false)
const snapshotTs = ref('')

let unsubscribe: (() => void) | null = null

async function refresh(): Promise<void> {
  try {
    const snap = await getTrafficSegments()
    segments.value = snap.segments
    snapshotTs.value = snap.ts
  } catch {
    /* 联调期接口层可能未起:SSE 重连后会再拉 */
  }
}

const SOURCE_LABEL: Record<TrafficSource, string> = {
  video: '视频链路',
  twin: '孪生链路',
}
const videoRows = computed(() => rowsOf('video'))
const twinRows = computed(() => rowsOf('twin'))

function rowsOf(source: TrafficSource) {
  return segments.value
    .filter((seg) => seg.source === source)
    .map((seg) => ({
      seg,
      name: demoSegment(seg.segment_id)?.name ?? seg.segment_id,
      stale: isStale(seg),
      color: levelStyle(seg).color,
    }))
}

// ---------- 感知检测流(真实离线推理数据) ----------
const streams = ref<PerceptionStreamMeta[]>([])
const curId = ref('')
const det = ref<PerceptionDetections | null>(null)
const pStatus = ref<'loading' | 'ready' | 'error'>('loading')
const pError = ref('')

async function loadStreams(): Promise<void> {
  pStatus.value = 'loading'
  pError.value = ''
  try {
    const res = await getPerceptionStreams()
    streams.value = res.streams
    if (res.streams.length === 0) {
      pStatus.value = 'error'
      pError.value = '感知服务无通道数据(先运行 work/perception/tools/dump_monitor_data.py 导出)'
      return
    }
    await loadStream(res.streams[0].stream_id)
  } catch {
    pStatus.value = 'error'
    pError.value = '感知服务未连接(先启动 work/perception/server.py,默认 127.0.0.1:8101)'
  }
}

async function loadStream(id: string): Promise<void> {
  curId.value = id
  pStatus.value = 'loading'
  try {
    det.value = await getPerceptionDetections(id)
    resetPlayer()
    pStatus.value = 'ready'
  } catch {
    pStatus.value = 'error'
    pError.value = '检测数据加载失败'
  }
}

const curMeta = computed(() => streams.value.find((s) => s.stream_id === curId.value) ?? null)
const streamIndex = computed(() => streams.value.findIndex((s) => s.stream_id === curId.value))

// ---------- 帧播放器(canvas) ----------
const idx = ref(0)
const playing = ref(true)
const speed = ref(1)
const canvasRef = ref<HTMLCanvasElement | null>(null)

const total = computed(() => det.value?.total_frames ?? 0)
const fpsNum = computed(() => det.value?.fps ?? 25)
const framesArr = computed(() => det.value?.frames ?? [])

// 轨迹拖尾:tid → 归一化坐标平铺数组(与上游轨迹视频同色系,琥珀色)
const trails = new Map<number, number[]>()
// 帧图缓存:1 起帧号 → Image
const imgCache = new Map<number, HTMLImageElement>()
let raf = 0
let acc = 0
let ctx: CanvasRenderingContext2D | null = null

const CLASS_COLORS: Record<number, string> = {
  0: '#b58cff',
  1: '#7fd7a0',
  2: '#37d6ff',
  3: '#69e0e0',
  5: '#ffd479',
  7: '#ff9f6a',
}

function resetPlayer(): void {
  idx.value = 0
  playing.value = true
  speed.value = 1
  trails.clear()
  imgCache.clear()
  acc = 0
  const meta = curMeta.value
  const cv = canvasRef.value
  if (meta && cv) {
    cv.width = meta.width
    cv.height = meta.height
    ensureImg(meta.stream_id, 1) // 预取首帧,门控放行前先有图
  }
}

function seek(i: number): void {
  idx.value = Math.max(0, Math.min(total.value - 1, i))
  trails.clear()
}

function advance(n: number): void {
  const t = total.value
  if (!t) return
  const from = idx.value
  const to = from + n
  if (to >= t) {
    seek(0)
    return
  }
  idx.value = to
  // 路过的每个检测帧都向拖尾贡献一个点(速度倍增时也正确)
  const arr = framesArr.value
  for (const e of arr) {
    if (e.i <= from) continue
    if (e.i > to) break
    for (const d of e.det) pushTrail(d)
  }
}

function pushTrail(d: Detection): void {
  const tid = d[6]
  let pts = trails.get(tid)
  if (!pts) {
    pts = []
    trails.set(tid, pts)
  }
  pts.push(((d[0] + d[2]) / 2), d[3])
  if (pts.length > 80) pts.splice(0, pts.length - 80)
}

// ≤i 的最近检测帧(二分;比维护游标对回退/跳转更稳)
function detAt(i: number): DetectionFrame | null {
  const arr = framesArr.value
  let lo = 0
  let hi = arr.length - 1
  let ans = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (arr[mid].i <= i) {
      ans = mid
      lo = mid + 1
    } else {
      hi = mid - 1
    }
  }
  return ans >= 0 ? arr[ans] : null
}

const curFrame = computed(() => detAt(idx.value))
const activeCount = computed(() => curFrame.value?.det.length ?? 0)
const avgConf = computed(() => {
  const d = curFrame.value?.det ?? []
  if (d.length === 0) return null
  return d.reduce((s, x) => s + x[5], 0) / d.length
})

// 累计轨迹/类别计数:按 first_seen 逐帧扫描一次,预成查表数组
const cum = computed(() => {
  const d = det.value
  if (!d) return null
  const totalN = d.total_frames
  const events = Object.values(d.first_seen)
    .map((v) => ({ f: v.frame, cls: v.class }))
    .sort((a, b) => a.f - b.f)
  const clsIds = [...new Set(events.map((e) => e.cls))]
  const byClass = new Map<number, Int32Array>(clsIds.map((c) => [c, new Int32Array(totalN + 1)]))
  const cumTotal = new Int32Array(totalN + 1)
  const runCls = new Map<number, number>()
  let ei = 0
  let run = 0
  for (let i = 0; i <= totalN; i++) {
    while (ei < events.length && events[ei].f <= i) {
      run++
      const c = events[ei].cls
      runCls.set(c, (runCls.get(c) ?? 0) + 1)
      ei++
    }
    cumTotal[i] = run
    for (const c of clsIds) byClass.get(c)![i] = runCls.get(c) ?? 0
  }
  return { cumTotal, byClass }
})
const cumTracks = computed(() => cum.value?.cumTotal[idx.value] ?? 0)
const clsChips = computed(() => {
  const c = cum.value
  if (!c) return []
  return [...c.byClass.entries()]
    .filter(([, arr]) => arr[idx.value] > 0)
    .map(([cls, arr]) => ({
      cls,
      name: curMeta.value?.class_names[String(cls)] ?? `类${cls}`,
      color: CLASS_COLORS[cls] ?? '#37d6ff',
      count: arr[idx.value],
    }))
    .sort((a, b) => b.count - a.count)
})

function hexA(hex: string, alpha: number): string {
  const n = parseInt(hex.slice(1), 16)
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`
}

function ensureImg(sid: string, n: number): HTMLImageElement | null {
  let img = imgCache.get(n)
  if (!img) {
    img = new Image()
    img.src = perceptionFrameUrl(sid, n)
    imgCache.set(n, img)
    if (imgCache.size > 160) {
      for (const k of imgCache.keys()) if (Math.abs(k - n) > 90) imgCache.delete(k)
    }
  }
  return img
}

function drawBoxes(ctx2d: CanvasRenderingContext2D, W: number, H: number, f: DetectionFrame): void {
  const meta = curMeta.value
  for (const d of f.det) {
    const [x1, y1, x2, y2, cls, conf, tid] = d
    const color = CLASS_COLORS[cls] ?? '#37d6ff'
    const name = meta?.class_names[String(cls)] ?? `类${cls}`
    ctx2d.fillStyle = hexA(color, 0.1)
    ctx2d.fillRect(x1 * W, y1 * H, (x2 - x1) * W, (y2 - y1) * H)
    ctx2d.strokeStyle = color
    ctx2d.lineWidth = 2
    ctx2d.strokeRect(x1 * W, y1 * H, (x2 - x1) * W, (y2 - y1) * H)
    const label = `${name} ${(conf * 100).toFixed(0)}% #${tid}`
    ctx2d.font = '600 12px system-ui, sans-serif'
    const tw = ctx2d.measureText(label).width
    const lx = Math.min(Math.max(x1 * W, 0), W - tw - 12)
    const ly = Math.max(y1 * H - 19, 0)
    ctx2d.fillStyle = color
    ctx2d.fillRect(lx, ly, tw + 10, 17)
    ctx2d.fillStyle = '#07101e'
    ctx2d.fillText(label, lx + 5, ly + 12.5)
  }
}

function drawTrails(ctx2d: CanvasRenderingContext2D, W: number, H: number): void {
  ctx2d.strokeStyle = 'rgba(250,170,0,0.55)'
  ctx2d.lineWidth = 2
  for (const pts of trails.values()) {
    if (pts.length < 4) continue
    ctx2d.beginPath()
    ctx2d.moveTo(pts[0] * W, pts[1] * H)
    for (let k = 2; k < pts.length; k += 2) ctx2d.lineTo(pts[k] * W, pts[k + 1] * H)
    ctx2d.stroke()
  }
}

function draw(): void {
  const cv = canvasRef.value
  if (!cv) return
  if (!ctx) ctx = cv.getContext('2d')
  const ctx2d = ctx
  if (!ctx2d) return
  const meta = curMeta.value
  // 惰性校正缓冲尺寸:canvas 在 pStatus=ready 分支里才挂载,watch(curMeta) 可能错过挂载时机
  if (meta && (cv.width !== meta.width || cv.height !== meta.height)) {
    cv.width = meta.width
    cv.height = meta.height
  }
  const W = cv.width
  const H = cv.height
  ctx2d.fillStyle = '#04080f'
  ctx2d.fillRect(0, 0, W, H)
  if (!meta || !det.value) return
  const img = ensureImg(meta.stream_id, idx.value + 1)
  if (img && img.complete && img.naturalWidth > 0) ctx2d.drawImage(img, 0, 0, W, H)
  drawTrails(ctx2d, W, H)
  const f = detAt(idx.value)
  if (f) drawBoxes(ctx2d, W, H, f)
}

// 推进节奏走定时器(后台标签也会触发,配合墙钟补偿,可见性变化不影响回放进度);
// rAF 只负责画。
let paceTimer = 0
let lastTick = 0

function pace(): void {
  const now = performance.now()
  const dt = lastTick ? Math.min((now - lastTick) / 1000, 1) : 0
  lastTick = now
  if (!playing.value || pStatus.value !== 'ready') return
  // 缓冲门控:当前帧图未就绪时不推进(等价视频缓冲,避免黑底浮标签)
  const img = imgCache.get(idx.value + 1)
  if (img && img.complete && img.naturalWidth > 0) {
    acc += dt * fpsNum.value * speed.value
    const n = Math.floor(acc)
    if (n > 0) {
      acc -= n
      advance(Math.min(n, 60))
    }
  } else {
    acc = 0
    if (curId.value) ensureImg(curId.value, idx.value + 1)
  }
}

function loop(): void {
  raf = requestAnimationFrame(loop)
  draw()
}

watch(curMeta, (meta) => {
  const cv = canvasRef.value
  if (meta && cv) {
    cv.width = meta.width
    cv.height = meta.height
  }
})

function fmtT(s: number): string {
  const m = Math.floor(s / 60)
  const ss = Math.floor(s % 60)
  return `${m}:${String(ss).padStart(2, '0')}`
}
const curT = computed(() => fmtT(idx.value / (fpsNum.value || 25)))
const durT = computed(() => fmtT(total.value / (fpsNum.value || 25)))

onMounted(() => {
  void refresh()
  unsubscribe = subscribeTrafficSnapshot(
    () => {
      void refresh()
    },
    (connected) => {
      live.value = connected
    },
  )
  void loadStreams()
  raf = requestAnimationFrame(loop)
  paceTimer = window.setInterval(pace, 250)
})

onUnmounted(() => {
  unsubscribe?.()
  cancelAnimationFrame(raf)
  window.clearInterval(paceTimer)
})
</script>

<template>
  <div class="perc-page">
    <header class="bar">
      <div class="bar-left">
        <span class="logo">◈</span>
        <span class="app-name">感知层 · YOLO 路面监控</span>
        <span class="badge svc">感知演示服务</span>
      </div>
      <div class="bar-mid">
        <span class="badge sim">样本视频回放(非本站现场)· 演示数据(模拟)· is_simulated = true</span>
      </div>
      <div class="bar-right">
        <span class="conn" :class="live ? 'up' : 'down'">
          <i class="dot" />
          {{ live ? '快照流已连接' : '快照流未连接' }}
        </span>
        <RouterLink class="dash-link" to="/dashboard">态势大屏 ›</RouterLink>
      </div>
    </header>

    <div class="main">
      <section class="panel monitor-panel">
        <div class="panel-head">监控画面 · 样本视频回放(YOLO 逐帧检测框 + 轨迹叠加)</div>

        <div v-if="pStatus === 'error'" class="pstate err">
          <p>{{ pError }}</p>
          <button class="retry" type="button" @click="loadStreams">重试</button>
        </div>
        <div v-else-if="pStatus === 'loading' && !det" class="pstate">加载检测数据…</div>

        <template v-else>
          <div v-if="curMeta" class="canvas-wrap">
            <canvas ref="canvasRef" class="scene" />
            <div class="hud hud-tl">
              <span class="rec-dot" />
              回放 · 样本通道 {{ streamIndex + 1 }}({{ curMeta.source_file }})
            </div>
            <div class="hud hud-tr">YOLOv8n · MindSpore</div>
            <div class="hud hud-bl">
              置信度 ≥ {{ curMeta.conf_threshold }} · IoU {{ curMeta.iou_threshold }} ·
              {{ curMeta.fps }} fps
            </div>
            <div class="hud hud-br">
              当前目标 {{ activeCount }} · 累计轨迹 {{ cumTracks }}
            </div>
          </div>

          <div class="controls">
            <button class="ctl play" type="button" @click="playing = !playing">
              {{ playing ? '⏸' : '▶' }}
            </button>
            <div class="spd">
              <button
                v-for="s in [1, 2, 4]"
                :key="s"
                type="button"
                class="ctl"
                :class="{ on: speed === s }"
                @click="speed = s"
              >
                {{ s }}×
              </button>
            </div>
            <input
              class="scrub"
              type="range"
              min="0"
              :max="Math.max(total - 1, 0)"
              :value="idx"
              @input="seek(Number(($event.target as HTMLInputElement).value))"
            />
            <span class="tcode">{{ curT }} / {{ durT }} · 帧 {{ idx + 1 }}/{{ total }}</span>
          </div>

          <p class="frame-meta">
            检测链路:MindSpore(MindYOLO yolov8n.ckpt)逐帧检测 + ByteTrack 跟踪(离线导出,回放);
            检测框/轨迹 ID/置信度为逐帧真实推理输出。路段指标快照(下)为契约 v2.0 mock 数据。
          </p>
        </template>
      </section>

      <aside class="col">
        <section class="panel">
          <div class="panel-head">检测通道(样本视频)</div>
          <div class="ch-list">
            <button
              v-for="(s, i) in streams"
              :key="s.stream_id"
              type="button"
              class="ch"
              :class="{ on: s.stream_id === curId }"
              @click="loadStream(s.stream_id)"
            >
              <span class="ch-name">样本通道 {{ i + 1 }} · {{ s.source_file }}</span>
              <span class="ch-meta">
                {{ s.duration_s ?? '—' }}s · {{ s.width }}×{{ s.height }} · {{ s.track_total }} 条轨迹
              </span>
            </button>
            <p v-if="pStatus === 'ready' && streams.length === 0" class="empty">无通道数据</p>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">实时检测统计(当前回放进度)</div>
          <div class="stats">
            <div class="stat">
              <span class="num">{{ activeCount }}</span>
              <span class="lbl">当前帧目标</span>
            </div>
            <div class="stat">
              <span class="num">{{ cumTracks }}</span>
              <span class="lbl">累计轨迹</span>
            </div>
            <div class="stat">
              <span class="num">{{ curMeta?.duration_s ?? '—' }}s</span>
              <span class="lbl">样本时长</span>
            </div>
          </div>
          <div class="chips">
            <span
              v-for="chip in clsChips"
              :key="chip.cls"
              class="chip"
              :style="{ borderColor: chip.color, color: chip.color }"
            >
              {{ chip.name }} ×{{ chip.count }}
            </span>
            <span v-if="clsChips.length === 0" class="empty">本帧前无轨迹</span>
          </div>
          <div class="meta-lines">
            <span>模型:{{ curMeta?.model }} · {{ curMeta?.backend }}</span>
            <span>
              画面:{{ curMeta?.width }}×{{ curMeta?.height }} · {{ fpsNum }} fps ·
              平均置信度 {{ avgConf == null ? '—' : avgConf.toFixed(2) }}
            </span>
            <span>导出:{{ curMeta?.generated_at }} · 离线推理产物</span>
          </div>
        </section>
      </aside>
    </div>

    <div class="bottom">
      <section class="panel link-panel">
        <div class="panel-head">视频感知链路(source = video)</div>
        <div class="seg-list">
          <div v-for="row in videoRows" :key="row.seg.segment_id" class="row" :class="{ stale: row.stale }">
            <LevelBadge :level="row.seg.level" :stale="row.stale" />
            <span class="meta">
              <span class="name">{{ row.name }}</span>
              <span class="id">{{ row.seg.segment_id }} · {{ SOURCE_LABEL[row.seg.source] }}</span>
            </span>
            <span class="metrics" :style="row.stale ? { color: '#8C8C8C' } : { color: row.color }">
              <template v-if="row.stale">不可用</template>
              <template v-else>
                {{ row.seg.q_vph ?? '—' }} vph · {{ row.seg.v_kmh ?? '—' }} km/h · 排队
                {{ row.seg.L_q_m ?? 0 }} m
              </template>
            </span>
          </div>
          <p v-if="videoRows.length === 0" class="empty">快照为空(接口层未起?)</p>
        </div>
      </section>

      <section class="panel link-panel">
        <div class="panel-head">孪生链路(source = twin)</div>
        <div class="seg-list">
          <div v-for="row in twinRows" :key="row.seg.segment_id" class="row" :class="{ stale: row.stale }">
            <LevelBadge :level="row.seg.level" :stale="row.stale" />
            <span class="meta">
              <span class="name">{{ row.name }}</span>
              <span class="id">{{ row.seg.segment_id }} · {{ SOURCE_LABEL[row.seg.source] }}</span>
            </span>
            <span class="metrics" :style="row.stale ? { color: '#8C8C8C' } : { color: row.color }">
              <template v-if="row.stale">不可用</template>
              <template v-else>
                {{ row.seg.q_vph ?? '—' }} vph · {{ row.seg.v_kmh ?? '—' }} km/h · 排队
                {{ row.seg.L_q_m ?? 0 }} m
              </template>
            </span>
          </div>
          <p v-if="twinRows.length === 0" class="empty">快照为空(接口层未起?)</p>
        </div>
      </section>
    </div>

    <footer class="foot">
      <span>快照时间 {{ snapshotTs || '—' }}</span>
      <span>检测流:感知演示服务(样本视频离线推理)· 指标快照:契约 v2.0 mock · is_simulated 恒 true</span>
      <span>一期无实时视频流 · 现场实时画面归二期</span>
    </footer>
  </div>
</template>

<style scoped>
.perc-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100vh;
  padding: 16px 20px;
  box-sizing: border-box;
  background: radial-gradient(1200px 700px at 50% 38%, #0d1c33 0%, #081222 62%, #060d1a 100%);
  color: #cfe0f5;
  overflow: hidden;
}
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  height: 52px;
  padding: 0 18px;
  border: 1px solid #1d3354;
  border-radius: 10px;
  background: linear-gradient(90deg, rgba(16, 32, 58, 0.9), rgba(12, 25, 48, 0.9));
  white-space: nowrap;
}
.bar-left,
.bar-mid,
.bar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.logo {
  color: #37d6ff;
  font-size: 22px;
}
.app-name {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #e6eefc;
}
.badge {
  font-size: 11px;
  padding: 2px 9px;
  border-radius: 4px;
  border: 1px solid;
}
.badge.svc {
  color: #37d6ff;
  border-color: #2a7f9e;
  background: rgba(55, 214, 255, 0.08);
}
.badge.sim {
  color: #ffd479;
  border-color: #8a6d1f;
  background: rgba(255, 212, 121, 0.1);
}
.conn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #7c93b5;
}
.conn .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.conn.up .dot {
  background: #35d08c;
  box-shadow: 0 0 0 3px rgba(53, 208, 140, 0.18);
}
.conn.down .dot {
  background: #e0564f;
  box-shadow: 0 0 0 3px rgba(224, 86, 79, 0.18);
}
.dash-link {
  font-size: 13px;
  color: #37d6ff;
  text-decoration: none;
  border: 1px solid #1d3354;
  border-radius: 6px;
  padding: 4px 10px;
}
.dash-link:hover {
  border-color: #2c4a78;
  background: rgba(55, 214, 255, 0.08);
}
.main {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr);
  gap: 14px;
}
.col {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
}
.bottom {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  height: 172px;
}
.panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 14px;
  border: 1px solid #1d3354;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(16, 32, 58, 0.75), rgba(11, 23, 43, 0.85));
}
.panel-head {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 2px;
  color: #9fb6d9;
  margin-bottom: 10px;
  padding-left: 8px;
  border-left: 3px solid #37d6ff;
  line-height: 1.2;
}
.monitor-panel {
  min-height: 0;
}
.pstate {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #7c93b5;
  font-size: 14px;
  border: 1px dashed #1d3354;
  border-radius: 8px;
}
.pstate.err {
  color: #e0a04f;
}
.retry {
  border: 1px solid #2a7f9e;
  color: #37d6ff;
  background: transparent;
  border-radius: 6px;
  padding: 6px 18px;
  cursor: pointer;
}
.canvas-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #1d3354;
  background: #04080f;
}
.scene {
  display: block;
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
}
.hud {
  position: absolute;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  line-height: 1;
  padding: 5px 10px;
  border-radius: 4px;
  background: rgba(5, 10, 20, 0.62);
  border: 1px solid rgba(29, 51, 84, 0.9);
  color: #cfe0f5;
  white-space: nowrap;
}
.hud-tl {
  top: 10px;
  left: 10px;
}
.hud-tr {
  top: 10px;
  right: 10px;
  color: #7fe7ff;
}
.hud-bl {
  bottom: 10px;
  left: 10px;
  color: #7c93b5;
}
.hud-br {
  bottom: 10px;
  right: 10px;
  color: #ffd479;
}
.rec-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #e0564f;
  animation: blink 1.4s infinite;
}
@keyframes blink {
  50% {
    opacity: 0.25;
  }
}
.controls {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
}
.ctl {
  border: 1px solid #1d3354;
  background: rgba(20, 38, 66, 0.55);
  color: #cfe0f5;
  border-radius: 6px;
  padding: 5px 12px;
  cursor: pointer;
  font-size: 13px;
  line-height: 1.2;
}
.ctl:hover {
  border-color: #2c4a78;
}
.ctl.play {
  width: 40px;
  font-size: 15px;
}
.ctl.on {
  color: #07101e;
  background: #37d6ff;
  border-color: #37d6ff;
  font-weight: 700;
}
.spd {
  display: flex;
  gap: 4px;
}
.scrub {
  flex: 1;
  accent-color: #37d6ff;
}
.tcode {
  font-size: 12px;
  color: #7c93b5;
  white-space: nowrap;
}
.frame-meta {
  margin: 8px 2px 0;
  font-size: 12px;
  line-height: 1.6;
  color: #7c93b5;
}
.ch-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
  min-height: 0;
}
.ch {
  display: flex;
  flex-direction: column;
  gap: 3px;
  text-align: left;
  padding: 9px 10px;
  background: rgba(20, 38, 66, 0.55);
  border: 1px solid #1d3354;
  border-radius: 8px;
  color: #cfe0f5;
  cursor: pointer;
}
.ch:hover {
  border-color: #2c4a78;
}
.ch.on {
  border-color: #37d6ff;
  background: rgba(55, 214, 255, 0.08);
}
.ch-name {
  font-size: 13px;
  color: #e6eefc;
}
.ch-meta {
  font-size: 11px;
  color: #7c93b5;
}
.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 10px;
}
.stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: center;
  padding: 10px 4px;
  background: rgba(20, 38, 66, 0.55);
  border: 1px solid #1d3354;
  border-radius: 8px;
}
.stat .num {
  font-size: 22px;
  font-weight: 700;
  color: #37d6ff;
}
.stat .lbl {
  font-size: 11px;
  color: #7c93b5;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}
.chip {
  font-size: 11px;
  padding: 2px 9px;
  border-radius: 4px;
  border: 1px solid;
  background: rgba(8, 18, 34, 0.6);
}
.meta-lines {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 11px;
  color: #7c93b5;
}
.seg-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
  padding-right: 2px;
}
.row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 10px;
  background: rgba(20, 38, 66, 0.55);
  border: 1px solid #1d3354;
  border-radius: 8px;
}
.row.stale {
  color: #8c8c8c;
}
.meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}
.name {
  font-size: 13px;
  color: #e6eefc;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.row.stale .name {
  color: #8c8c8c;
}
.id {
  font-size: 11px;
  color: #7c93b5;
}
.metrics {
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.empty {
  font-size: 12px;
  color: #5f7396;
  padding: 8px 2px;
}
.foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 30px;
  font-size: 12px;
  color: #5f7396;
  white-space: nowrap;
}
@media (max-width: 1100px) {
  .perc-page {
    overflow-y: auto;
    height: auto;
  }
  .main,
  .bottom {
    grid-template-columns: 1fr;
  }
  .bottom {
    height: auto;
  }
  .canvas-wrap {
    max-height: none;
  }
}
</style>
