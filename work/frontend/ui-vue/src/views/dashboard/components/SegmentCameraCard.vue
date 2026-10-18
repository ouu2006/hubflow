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
//   · 该段 0 路摄像头 / 登记摄像头均无视频源：按业主口径显示「演示复用样本视频」
//     （从 road2/track1 确定性复用，明确标注非真实摄像头，详见 IKNAUI）。
//
// 唯一真值来源 = 站点包 `channels`（由 work/perception/mapping/camera-segments.json 生成），
// 与感知页 / 地图摄像头图钉同一个 `source` / `hasVideo` 键，不另造第二份。
//
// 2026-10-18 口径（IKNBT2）：**N 段 = N 摄像头 = N 视频（演示）**——
// 源台账 0 路不再写「无独立摄像头」，而是「演示摄像头 · 复用样本视频」；有登记摄像头段保持
// 源台账身份，但同样说明"一期每路都有视频（mock 复用）"。不伪造真实摄像头/登记表。
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { getPerceptionStreams, perceptionFrameUrl, type PerceptionStreamMeta } from '../../../api/perception'
import { camerasOfSegment, demoCameraCount, perceptionHref } from '../../../shared/cameras'

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
/** 一期演示口径的摄像头总数：N 段 = N 摄像头（Z=61 / GZ=433；与源台账分开说） */
const demoCameraTotal = computed(() => demoCameraCount())
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
/** 该段是否有任何“有视频源”的登记摄像头；false 时（含 0 路）走演示复用视频 */
const hasAnyVideo = computed(() => cameras.value.some((c) => c.hasVideo !== false))
/** 登记了但无视频源的摄像头 cid 列表（用于说明“登记摄像头均无视频源”） */
const noVideoCids = computed(() =>
  cameras.value.filter((c) => c.hasVideo === false).map((c) => c.cid).join(' / '),
)

// ---------- 全路段视频复用（Issue IKNAUI 业主口径：全部 61 段都要有视频显示）----------
//
// **对没有登记摄像头、或登记摄像头均无视频源的段启用**：从现有 2 路样本视频 road2 / track1 中
// 按 segment_id **确定性**挑一路（同一段永远同一路，不用随机），复用它真实的抽帧画面。
// 不新增 / 不伪造摄像头登记——感知页台账仍是登记表里的 6 路；这里只是「演示复用视频」。
const REUSE_SOURCES = ['road2', 'track1'] as const
function reuseSourceOf(segmentId: string): string {
  let hash = 0
  for (const ch of segmentId) hash = (hash * 31 + (ch.codePointAt(0) ?? 0)) >>> 0
  return REUSE_SOURCES[hash % REUSE_SOURCES.length]!
}
const reuseStream = computed<string>(() =>
  !hasAnyVideo.value ? reuseSourceOf(props.segmentId) : '',
)
const reuseMeta = computed<PerceptionStreamMeta | null>(() => {
  if (!reuseStream.value) return null
  return streams.value?.find((item) => item.stream_id === reuseStream.value) ?? null
})
const reuseFrameFailed = computed<boolean>(() =>
  Boolean(reuseStream.value && frameFailed.value[`reuse:${reuseStream.value}`]),
)
const reuseFrameNo = computed<number>(() => {
  const total = Math.max(1, reuseMeta.value?.total_frames ?? 1)
  return ((tick.value * FRAME_STEP) % total) + 1
})
const hasAnyPlayable = computed<boolean>(() => hasPlayable.value || reuseMeta.value !== null)
const playLabel = computed(() => (!hasAnyPlayable.value ? '—' : playing.value ? '暂停' : '播放'))

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
    // 服务错误总与卡片画面相关（有视频源→原视频；无视频源/0 路→演示复用视频），统一 8s 重试
    scheduleRetry()
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
      <span class="sub-tag">
        {{
          cameras.length > 0
            ? `源台账 ${cameras.length} 路`
            : `演示摄像头 · 复用样本视频（按路段数 ${demoCameraTotal} 路）`
        }}
      </span>
      <span v-if="!hasAnyVideo && reuseMeta" class="td-chip warn">演示复用 · 非本站现场 · 非实时</span>
      <span v-else-if="hasPlayable" class="td-chip warn">样本视频回放 · 非本站现场</span>
      <a
        v-if="hasAnyPlayable"
        class="cam-play"
        role="button"
        :aria-pressed="playing"
        @click="playing = !playing"
      >
        {{ playLabel }}
      </a>
    </div>

    <!-- 无真实登记源 / 登记摄像头均无视频源：按一期口径显示「演示摄像头 · 复用样本视频」（确定性复用 2 路样本视频之一） -->
    <template v-if="!hasAnyVideo">
      <div class="cam-row">
        <div class="cam-head">
          <span class="cam-id td-mono">{{ cameras.length === 0 ? '演示摄像头' : `登记源台账 ${noVideoCids}` }}</span>
          <span class="cam-name">
            {{ cameras.length === 0 ? '演示复用样本视频（本段演示画面 · mock 复用）' : '源台账无独立视频源 · 演示复用样本视频' }}
          </span>
          <span class="td-chip" :class="{ ok: reuseMeta, err: Boolean(error) || reuseFrameFailed }">
            {{
              reuseFrameFailed
                ? '帧加载失败'
                : reuseMeta
                  ? '演示复用'
                  : error
                    ? '服务不可用'
                    : '未导出'
            }}
          </span>
        </div>

        <template v-if="reuseMeta && !error">
          <div class="cam-media">
            <img
              v-if="!reuseFrameFailed"
              class="cam-img"
              :src="perceptionFrameUrl(reuseStream, reuseFrameNo)"
              :alt="`${segmentId} 演示复用样本视频抽帧`"
              loading="lazy"
              @error="onFrameError(`reuse:${reuseStream}`)"
            />
            <div v-else class="cam-media cam-nosource">
              <span class="ns-l1">帧加载失败</span>
              <span class="ns-l2">不保留破图、不伪造画面</span>
              <button class="td-btn sm" type="button" @click="retryFrame(`reuse:${reuseStream}`)">重试本帧</button>
            </div>
            <span v-if="!reuseFrameFailed" class="cam-badge">
              演示复用 · 非本站现场 · 非实时
            </span>
          </div>
          <div class="cam-meta td-mono">
            复用样本通道 {{ reuseStream }} · {{ reuseMeta.width }}×{{ reuseMeta.height }} ·
            {{ reuseMeta.fps }} fps · 共 {{ reuseMeta.total_frames }} 帧
            <span class="sep">|</span>
            <a class="cam-link" :href="perceptionHref(reuseStream)">打开感知画面 ›</a>
          </div>
        </template>

        <template v-else-if="error">
          <div class="cam-media cam-nosource">
            <span class="ns-l1">感知服务不可用</span>
            <span class="ns-l2">复用样本视频不可用（不伪造画面）</span>
          </div>
          <div class="cam-meta">
            <button class="td-btn sm" type="button" @click="loadStreams">重试</button>
          </div>
        </template>

        <p v-else-if="loading && streams === null" class="empty sm">正在读取感知服务通道…</p>

        <template v-else>
          <div class="cam-media cam-nosource">
            <span class="ns-l1">复用样本视频未导出</span>
            <span class="ns-l2">感知服务未提供 {{ reuseStream }} 画面（如实空窗）</span>
          </div>
          <div class="cam-meta">
            <a class="cam-link" :href="perceptionHref(reuseStream)">打开感知页查看 ›</a>
          </div>
        </template>
      </div>
      <p class="cam-note">
        一期口径：<b>N 段 = N 摄像头 = N 视频（演示）</b>——本站 {{ demoCameraTotal }} 段即
        {{ demoCameraTotal }} 路演示摄像头，每路都有画面；视频为 <b>mock 复用</b>（同一份 road2 / track1
        可被多路复用），<b>演示复用 · 非本站现场 · 非实时</b>。
        <template v-if="cameras.length === 0">
          本段无真实登记源 → 显示「演示摄像头」，不代表没有摄像头/视频；
        </template>
        <template v-else>
          本段源台账摄像头（{{ noVideoCids }}）无独立视频源 → 画面为演示复用；
        </template>
        不伪造真实摄像头 / 登记表（源台账 {{ cameras.length }} 路仅作初始映射，不代表一期摄像头总数；真实接入归 IKMHMX）。
      </p>
    </template>


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
        源台账摄像头 ↔ 通道 ↔ 路段取 work/perception/mapping/camera-segments.json（**仅初始映射**，源台账
        {{ cameras.length }} 路，不代表一期摄像头总数）；有视频源的通道画面为<b>样本视频回放</b>
        （演示复用，非本站现场、非实时）。
        一期口径：<b>N 段 = N 摄像头 = N 视频（演示）</b>——本站 {{ demoCameraTotal }} 段 =
        {{ demoCameraTotal }} 路演示摄像头，每路都有画面；真实接入归 IKMHMX。
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
