<script setup lang="ts">
// 大屏右栏 · 关联摄像头（Issue IKMS18 大屏监控平台化）。
//
// 点选路段 → 该段登记摄像头的**感知服务真实帧预览**：
//   · 有视频源 + 感知服务已导出该通道：按 `meta.total_frames` 定时抽帧
//     （`<img>` 拉 `/perception-api/streams/{source}/frames/{n}.jpg`，与感知页同一路径），
//     常驻「样本视频回放 · 非本站现场」角标；可播放 / 暂停；
//   · 有视频源、服务在、但该通道没导出：「未导出（样本视频未处理）」；
//   · 无视频源：「未接入视频源 · 本期留空」；
//   · 感知服务整体不可用：可读错误 + 重试（8 s 自动重试），**绝不伪造画面**；
//   · 该段登记摄像头 0 路：「该路段无摄像头」。
//
// 唯一真值来源 = 站点包 `channels`（由 work/perception/mapping/camera-segments.json 生成），
// 与感知页 / 地图摄像头图钉同一个 `source` / `hasVideo` 键，不另造第二份。
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { getPerceptionStreams, perceptionFrameUrl, type PerceptionStreamMeta } from '../../../api/perception'
import { camerasOfSegment, perceptionHref } from '../../../shared/cameras'

const props = defineProps<{ segmentId: string }>()

const streams = ref<PerceptionStreamMeta[] | null>(null)
const loading = ref(false)
const error = ref('')
/** 帧级加载失败（抽帧 404 / 服务中途挂掉）：该路显示"帧不可用"，不保留破图 */
const frameFailed = ref<Record<string, boolean>>({})
const playing = ref(true)
/** 播放时钟：每 500 ms 走 1 步，抽帧序号 = 时钟 × FRAME_STEP（对 total_frames 取模循环） */
const tick = ref(0)
const FRAME_STEP = 5
const CLOCK_MS = 500

const cameras = computed(() => camerasOfSegment(props.segmentId))
const views = computed(() =>
  cameras.value.map((camera) => ({
    cid: camera.cid,
    source: camera.source,
    name: camera.name,
    hasVideo: camera.hasVideo !== false,
    meta: streams.value?.find((item) => item.stream_id === camera.source) ?? null,
  })),
)
const hasPlayable = computed(() => views.value.some((v) => v.hasVideo && v.meta !== null))
const videoCount = computed(() => views.value.filter((v) => v.hasVideo).length)
const playLabel = computed(() => (!hasPlayable.value ? '—' : playing.value ? '暂停' : '播放'))

/** 第 1 帧起的抽帧序号（各通道帧数不同，各自取模） */
function frameOf(view: { meta: PerceptionStreamMeta | null }): number {
  const total = Math.max(1, view.meta?.total_frames ?? 1)
  return ((tick.value * FRAME_STEP) % total) + 1
}

let clock: ReturnType<typeof setInterval> | null = null
let retryTimer: ReturnType<typeof setTimeout> | null = null

function clearRetry(): void {
  if (retryTimer) {
    clearTimeout(retryTimer)
    retryTimer = null
  }
}

function scheduleRetry(): void {
  if (retryTimer) return
  retryTimer = setTimeout(() => {
    retryTimer = null
    if (error.value) void loadStreams()
  }, 8000)
}

/** 帧加载失败：不回退到别的帧/假图，只如实标"帧不可用"并允许手动重试 */
function onFrameError(source: string): void {
  frameFailed.value = { ...frameFailed.value, [source]: true }
}

function retryFrame(source: string): void {
  const next = { ...frameFailed.value }
  delete next[source]
  frameFailed.value = next
  tick.value += 1
}

async function loadStreams(): Promise<void> {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const res = await getPerceptionStreams()
    streams.value = Array.isArray(res.streams) ? res.streams : []
    clearRetry()
  } catch (e) {
    streams.value = null
    error.value = `感知服务未连接 / 不可用：${e instanceof Error ? e.message : String(e)}`
    // 有视频源的摄像头才需要重试；无视频源的段不因服务没起而报错
    if (cameras.value.some((c) => c.hasVideo !== false)) scheduleRetry()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  clock = setInterval(() => {
    if (playing.value) tick.value += 1
  }, CLOCK_MS)
  void loadStreams()
})

onUnmounted(() => {
  if (clock) clearInterval(clock)
  clearRetry()
})

// 切路段：帧序号归零（各通道帧数不同，避免沿用上一段的大序号）；帧失败标记也清掉
watch(
  () => props.segmentId,
  () => {
    tick.value = 0
    frameFailed.value = {}
  },
)
</script>

<template>
  <section class="cam-card">
    <div class="sec-head">
      关联摄像头
      <span class="sub-tag">{{ cameras.length }} 路</span>
      <span v-if="hasPlayable" class="td-chip warn">样本视频回放 · 非本站现场</span>
      <a
        v-if="hasPlayable"
        class="cam-play"
        role="button"
        :aria-pressed="playing"
        @click="playing = !playing"
      >
        {{ playLabel }}
      </a>
    </div>

    <!-- 0 路摄像头：如实说"该路段无摄像头"，不画占位画面 -->
    <p v-if="cameras.length === 0" class="empty sm">
      该路段无摄像头（登记表 0 路）—— 路网上不显示摄像头图钉，也不提供画面。
    </p>

    <template v-else>
      <p v-if="error && videoCount > 0" class="cam-warn">
        ⚠ {{ error }}
        <button class="td-btn sm" type="button" @click="loadStreams">重试</button>
      </p>
      <p v-else-if="loading && streams === null" class="empty sm">正在读取感知服务通道…</p>

      <div v-for="view in views" :key="view.cid" class="cam-row">
        <div class="cam-head">
          <span class="cam-id td-mono">{{ view.cid }} · {{ view.source }}</span>
          <span class="cam-name">{{ view.name }}</span>
          <span
            class="td-chip"
            :class="{ ok: view.hasVideo && view.meta, out: !view.hasVideo, err: view.hasVideo && !view.meta && !error }"
          >
            {{ !view.hasVideo ? '未接入视频源' : frameFailed[view.source] ? '帧加载失败' : view.meta ? '样本视频回放' : error ? '服务不可用' : '未导出' }}
          </span>
        </div>

        <!-- 有视频源：真实帧预览（帧级失败 → 空窗 + 重试，不留破图、不伪造） -->
        <template v-if="view.hasVideo && view.meta">
          <div class="cam-media">
            <img
              v-if="!frameFailed[view.source]"
              class="cam-img"
              :src="perceptionFrameUrl(view.source, frameOf(view))"
              :alt="`${view.cid} ${view.name} 样本视频抽帧`"
              loading="lazy"
              @error="onFrameError(view.source)"
            />
            <div v-else class="cam-media cam-nosource">
              <span class="ns-l1">帧加载失败</span>
              <span class="ns-l2">不保留破图、不伪造画面</span>
              <button class="td-btn sm" type="button" @click="retryFrame(view.source)">重试本帧</button>
            </div>
            <span v-if="!frameFailed[view.source]" class="cam-badge">样本视频回放 · 非本站现场</span>
          </div>
          <div class="cam-meta td-mono">
            {{ view.meta.width }}×{{ view.meta.height }} · {{ view.meta.fps }} fps · 共
            {{ view.meta.total_frames }} 帧 · 轨迹 {{ view.meta.track_total }}
            <span class="sep">|</span>
            <a class="cam-link" :href="perceptionHref(view.source)">打开感知画面 ›</a>
          </div>
        </template>

        <!-- 有视频源但服务没导出该通道 / 服务不可用：空窗，不画假画面 -->
        <template v-else-if="view.hasVideo">
          <div class="cam-media cam-nosource">
            <span class="ns-l1">{{ error ? '感知服务不可用' : '未导出' }}</span>
            <span class="ns-l2">{{ error ? '画面不可用（不伪造）' : '有样本视频，等待感知服务处理' }}</span>
          </div>
          <div class="cam-meta">
            <a class="cam-link" :href="perceptionHref(view.source)">打开感知页查看 ›</a>
          </div>
        </template>

        <!-- 无视频源：空窗（与"未导出"分开说） -->
        <template v-else>
          <div class="cam-media cam-nosource">
            <span class="ns-l1">未接入视频源</span>
            <span class="ns-l2">本期留空 · 路网上已布点</span>
          </div>
        </template>
      </div>

      <p class="cam-note">
        摄像头 ↔ 通道 ↔ 路段取 work/perception/mapping/camera-segments.json（唯一真值来源，动态 N 路）；
        有视频源的通道画面为<b>样本视频回放</b>，非本站现场、非实时流。
      </p>
    </template>
  </section>
</template>

<style scoped>
.cam-card {
  padding: 8px 0;
  border-bottom: 1px solid var(--td-component-stroke);
}
.sec-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}
.sub-tag {
  font-size: 11px;
  font-weight: 400;
  color: var(--td-text-color-placeholder);
}
.cam-play {
  margin-left: auto;
  font-size: 11px;
  color: var(--td-brand-color);
  cursor: pointer;
  user-select: none;
}
.cam-row {
  margin-bottom: 8px;
}
.cam-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 4px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.cam-id {
  color: var(--td-text-color-placeholder);
}
.cam-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cam-media {
  position: relative;
  border-radius: var(--td-radius-sm);
  overflow: hidden;
  background: #101418;
  aspect-ratio: 16 / 10;
  display: flex;
  align-items: center;
  justify-content: center;
}
.cam-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.cam-badge {
  position: absolute;
  left: 6px;
  bottom: 6px;
  padding: 1px 6px;
  border-radius: 3px;
  background: rgba(0, 0, 0, 0.6);
  color: #ffd666;
  font-size: 10px;
}
.cam-nosource {
  flex-direction: column;
  gap: 2px;
  border: 1px dashed var(--td-component-border);
  background: var(--td-bg-color-secondarycontainer);
}
.ns-l1 {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}
.ns-l2 {
  font-size: 10px;
  color: var(--td-text-color-placeholder);
}
.cam-meta {
  margin-top: 3px;
  font-size: 10px;
  line-height: 1.6;
  color: var(--td-text-color-placeholder);
}
.sep {
  margin: 0 4px;
  color: var(--td-text-color-placeholder);
}
.cam-link {
  color: var(--td-brand-color);
  text-decoration: none;
}
.cam-warn {
  margin: 0 0 6px;
  padding: 5px 8px;
  border-radius: 3px;
  background: var(--td-warning-color-1);
  color: #a06a00;
  font-size: 11px;
  line-height: 1.5;
}
.cam-note {
  margin: 4px 0 0;
  font-size: 10px;
  line-height: 1.6;
  color: var(--td-text-color-placeholder);
}
.empty {
  margin: 4px 0;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
</style>
