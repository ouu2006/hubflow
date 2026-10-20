<script setup lang="ts">
// 视频感知(YOLO 链路)页 · Issue #78 按设计稿 04 重写。
//
// 数据来源(两个,不混):
//  ① 感知演示服务(/perception-api → work/perception/server.py):离线样本视频的逐帧检测框 / 抽帧画面 / 通道 meta;
//  ② traffic 契约快照(mock / 接口层):映射路段的 video 槽位字段、断面同化门控。
//
// 硬口径(违反即不通过):
//  · 画面是**离线样本视频**,不是实时流、不是本站现场 → 页头黄色口径标 + 页脚写明;
//  · 深色(token)只出现在监控画面格内,页面壳层 / 卡片 / 表格一律浅色;
//  · 车型框色(CLASS_COLORS)与等级四级色解耦,画面区不出现等级色;
//  · 拿不到的字段(越线计数 / SVR / 标定 / 平均 Q)一律「—」并注明出处,绝不用推算值或设计稿示例值冒充。
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../../components/AppShell.vue'
import {
  getPerceptionDetections,
  getPerceptionStreams,
  getPerceptionSummary,
  type PerceptionDetections,
  type PerceptionStreamMeta,
  type PerceptionSummary,
} from '../../api/perception'
import {
  getTrafficAssimilationFull,
  getTrafficContext,
  getTrafficMeta,
  getTrafficSegmentSources,
  getTrafficSegments,
} from '../../api/traffic'
import type { AssimilationSnapshotFull, SegmentSourcePair, TrafficContext } from '../../shared/traffic'
import { formatStamp } from '../../shared/traffic'
import ChannelLedger from './components/ChannelLedger.vue'
import DataSupplyPanel from './components/DataSupplyPanel.vue'
import DetailPanel from './components/DetailPanel.vue'
import EnvContextBar from './components/EnvContextBar.vue'
import MonitorWall from './components/MonitorWall.vue'
import PipelinePanel from './components/PipelinePanel.vue'
import SemanticsPanel from './components/SemanticsPanel.vue'
import { channels as packChannels, type ChannelDef, type ChannelState } from './components/channels'
import { activePack } from '../../station-packs/index'
import { demoCameraCount } from '../../shared/cameras'

const streams = ref<PerceptionStreamMeta[]>([])
const detMap = ref<Record<string, PerceptionDetections>>({})
/** detections 请求失败的通道(meta 在、检测取不到)——失败不得冒充"无检测结果" */
const detFailedSet = ref<Record<string, true>>({})
const pStatus = ref<'loading' | 'ready' | 'error'>('loading')
const pError = ref('')

/** 当前检测通道(默认 C-05 track1,与设计稿一致) */
const currentSource = ref('track1')
/** 台账/监控墙再次点中同一路时,currentSource 不变但也要让监控墙回到该页/取消筛选 */
const selectTick = ref(0)

// ---- 深链:大屏点摄像头进来 = `#/perception?source=cam-03`(Issue IKLX5Y) ----
//
// 两条纪律:
//   ① **在挂载前就落定**,不等 `/perception-api/streams` 回来 —— 本批摄像头**没有视频源**,
//      感知服务多半根本没起;若把深链放在"服务拉成功"的分支里,点摄像头进来会静默落回默认通道
//      (那就是"点了没反应")。
//   ② 只在**通道目录里真有这个 source** 时才采纳:参数是外部给的,写错了不能让页面
//      落到不存在的通道上。写错就忽略、保持默认通道 —— 深链是便利,不是入口条件。
const route = useRoute()
function deepLinkSource(): string | null {
  const raw = route.query.source
  const src = typeof raw === 'string' ? raw : Array.isArray(raw) ? raw[0] : null
  if (!src) return null
  return packChannels().some((c) => c.source === src) ? src : null
}

const linkedSource = deepLinkSource()
if (linkedSource) currentSource.value = linkedSource

// 组件已挂载时地址栏再变(浏览器前进/后退、或从别处再点一次摄像头):跟着走,
// 否则 setup 期读过一次就再也不认新参数,会出现"链接换了、选中的还是那一路"。
watch(() => route.query.source, () => {
  const next = deepLinkSource()
  if (next) currentSource.value = next
})

/** 本包通道数 N(= 当前站点包 channels 条数 = 登记表 cameras 条数;0 路合法,不再固定 6) */
const channelTotal = computed(() => packChannels().length)
/** 一期演示口径摄像头总数：N 段 = N 摄像头 = N 视频（mock 复用；与源台账分开说，IKNBT2） */
const demoCameraTotal = computed(() => demoCameraCount())
/** 本包是否至少声明了一路有视频源的通道 —— 没有就不该报"服务未连接" */
const packHasVideo = computed(() => packChannels().some((c) => c.hasVideo))
/** 是否布了摄像头:N=0(新站/未布点站)合法,页面如实显示空态、不渲染"当前通道"详情 */
const hasChannels = computed(() => channelTotal.value > 0)
/** 0 路时的占位定义:只为让 current 计算有非空返回;N=0 时详情面板整体不渲染,不会冒充真实通道 */
const EMPTY_CHANNEL: ChannelDef = {
  cid: '—',
  source: '',
  name: '源台账未登记（一期为演示摄像头）',
  segmentId: '—',
  hasVideo: false,
}

/**
 * 页头口径(随包走,不写死):
 *   有视频源 → "样本视频"口径;
 *   本包全部没有视频源 → 如实说"未接入视频源";
 *   0 路源台账 → 如实说"源台账 0 路（仅初始映射）"，并注明一期 N 段 = N 摄像头 = N 视频（mock 复用），
 *   不得把源台账 0 路写成"本站没有摄像头/没有视频"（IKNBT2 口径）。
 */
const subLine = computed(() => {
  if (!hasChannels.value) {
    return `源台账 0 路（仅初始映射）· 一期演示摄像头 ${demoCameraTotal.value} 路（按路段数，mock 复用样本视频）· 本页只展示源台账通道`
  }
  const ledger = `源台账 ${channelTotal.value} 路（仅初始映射，不代表一期总数；一期 N 段 = N 摄像头 = N 视频，mock 复用）`
  return packHasVideo.value
    ? `样本视频 · 检测 → 跟踪 → 透视标定 → 四项指标 · ${ledger}`
    : `${channelTotal.value} 路源台账通道 · 全部未接入视频源(本期留空) · ${ledger} · 检测 → 跟踪 → 透视标定 → 四项指标暂无输入`
})
const sourceBadge = computed(() => {
  if (!hasChannels.value) {
    return `源台账 0 路 · 一期演示摄像头 ${demoCameraTotal.value} 路（mock 复用）`
  }
  return packHasVideo.value
    ? '离线样本视频 · 非实时流 · 非本站现场'
    : '本批源台账摄像头未接入视频源 · 页面不显示任何画面'
})
/** 页脚出处(同一条纪律:没有视频源就不说"样本视频";0 路源台账照实说"仅初始映射") */
const footSourceLine = computed(() => {
  if (!hasChannels.value) {
    return `源台账 0 路（仅初始映射）· 一期演示摄像头 ${demoCameraTotal.value} 路（按路段数，mock 复用）· 非${stationName.value}现场 · 非实时流`
  }
  const ledger = `一期口径：N 段 = N 摄像头 = N 视频（演示，mock 复用；源台账 ${channelTotal.value} 路仅初始映射，不代表一期总数）`
  return packHasVideo.value
    ? `视频为公开样本视频 · 非${stationName.value}现场 · 非实时流 · ${ledger}`
    : `本轮无视频画面 · 非${stationName.value}现场 · 非实时流 · ${ledger}`
})

const summary = ref<PerceptionSummary | null>(null)
const summaryUnavailable = ref(true)
const sourcePair = ref<SegmentSourcePair | null>(null)
const assimilation = ref<AssimilationSnapshotFull | null>(null)
/** 环境上下文(Issue #77:天气 / 时间 / 因地制宜的路况因子)—— 演示值,见 EnvContextBar 口径注 */
const ctx = ref<TrafficContext | null>(null)
const ctxError = ref('')
const snapshotTs = ref('')
/** 站点名(顶栏 chip):默认取当前站点包,拿到 meta 后由 meta.station.name 覆盖 —— 四页同一口径 */
const stationName = ref(activePack().station.name)

// 可用性一律由服务端实际返回判定:返回里有的才「就绪 / 检测中」,没有的「未导出」;取不到检测的标「读取失败」
const channels = computed<ChannelState[]>(() =>
  packChannels().map((def) => {
    const meta = streams.value.find((m) => m.stream_id === def.source) ?? null
    const det = detMap.value[def.source] ?? null
    return {
      def,
      meta,
      det,
      detTotal: det ? det.frames.reduce((s, f) => s + f.det.length, 0) : null,
      detFailed: meta !== null && det === null && detFailedSet.value[def.source] === true,
    }
  }),
)

const current = computed<ChannelState>(() => {
  const hit = channels.value.find((c) => c.def.source === currentSource.value)
  return (
    hit ?? channels.value[0] ?? { def: EMPTY_CHANNEL, meta: null, det: null, detTotal: null, detFailed: false }
  )
})

const processedAt = computed(() =>
  current.value.meta ? formatStamp(current.value.meta.generated_at) : '—',
)

/** 检测读取失败的通道编号(页级提示:故障必须显式,不得静默成"无检出") */
const detFailedCids = computed(() =>
  channels.value.filter((c) => c.detFailed).map((c) => `${c.def.cid} ${c.def.source}`),
)

async function loadStreams(): Promise<void> {
  pStatus.value = 'loading'
  pError.value = ''
  try {
    const res = await getPerceptionStreams()
    const list: PerceptionStreamMeta[] = Array.isArray(res.streams) ? res.streams : []
    // 只拉已导出通道的逐帧检测(未导出通道服务端没有该端点数据)
    const settled = await Promise.allSettled(list.map((m) => getPerceptionDetections(m.stream_id)))
    const dets: Record<string, PerceptionDetections> = {}
    const failed: Record<string, true> = {}
    list.forEach((m, i) => {
      const r = settled[i]
      if (r && r.status === 'fulfilled') dets[m.stream_id] = r.value
      // meta 在、检测取不到 = 该通道读取失败:记下来,由 UI 如实报错,
      // 不把"请求失败"显示成"本帧无检出"(那是把故障说成结果)
      else failed[m.stream_id] = true
    })
    streams.value = list
    detMap.value = dets
    detFailedSet.value = failed
    pStatus.value = 'ready'
    clearRetryTimer()
    // 当前通道:深链点名过就**不动**;否则若这一路不在服务端返回里,落第一路(既有行为)
    if (!linkedSource) {
      const first = list[0]
      if (first && !list.some((m) => m.stream_id === currentSource.value)) {
        currentSource.value = first.stream_id
      }
    }
  } catch {
    // 感知服务没起:本批摄像头本来就没视频源(业主:视频样本先不弄),
    // 所以只在"包里确实声明了有视频源的通道"时才报服务未连接 —— 否则那是误报。
    if (packHasVideo.value) {
      pStatus.value = 'error'
      pError.value = '感知演示服务未连接(先启动 work/perception/server.py,默认 127.0.0.1:8101)'
      // 断流恢复后自动重连(TC-06):错误态下每 5 s 重试一次,成功后清掉;也可点「重试」立即重拉
      scheduleRetry()
    } else {
      pStatus.value = 'ready'
      streams.value = []
      detMap.value = {}
      detFailedSet.value = {}
    }
  }
}

/** 错误态自动重试定时器(断流恢复后无需手动刷新页面) */
let retryTimer: ReturnType<typeof setTimeout> | null = null
function clearRetryTimer(): void {
  if (retryTimer) {
    clearTimeout(retryTimer)
    retryTimer = null
  }
}
function scheduleRetry(): void {
  if (retryTimer) return
  retryTimer = setTimeout(() => {
    retryTimer = null
    if (pStatus.value === 'error') void loadStreams()
  }, 5000)
}

// 当前通道详情:汇总(感知服务,当前未实现 → 降级)+ 该映射路段的 video 槽位
async function loadDetail(src: string): Promise<void> {
  summary.value = null
  summaryUnavailable.value = true
  sourcePair.value = null
  const def = packChannels().find((c) => c.source === src)
  if (!def) return
  const [sum, pair] = await Promise.allSettled([
    getPerceptionSummary(src),
    getTrafficSegmentSources(def.segmentId),
  ])
  if (sum.status === 'fulfilled' && sum.value && Array.isArray(sum.value.class_stats)) {
    summary.value = sum.value
    summaryUnavailable.value = false
  }
  if (pair.status === 'fulfilled') sourcePair.value = pair.value
}

async function loadTrafficBase(): Promise<void> {
  try {
    const snap = await getTrafficSegments()
    snapshotTs.value = snap.ts
  } catch {
    // 快照接口未起:页头时间戳留「—」,不阻塞感知数据展示
  }
  try {
    stationName.value = (await getTrafficMeta()).station.name
  } catch {
    // meta 未起:顶栏保持站点包里的站名,不影响感知画面
  }
  try {
    assimilation.value = await getTrafficAssimilationFull()
  } catch {
    assimilation.value = null
  }
  // 环境上下文(Issue #77):取不到就如实说"未取到",不回落到任何编造值
  try {
    ctx.value = await getTrafficContext()
    ctxError.value = ''
  } catch {
    ctx.value = null
    ctxError.value = '环境上下文未取到(traffic 接口层未起?)—— 本卡不显示未经确认的天气 / 时段值。'
  }
}

function onSelect(source: string): void {
  currentSource.value = source
  // 同一路再次点击时 currentSource 不会变,用 tick 通知监控墙"用户又点了这一路"
  selectTick.value += 1
}

watch(currentSource, (src) => void loadDetail(src), { immediate: true })

onMounted(() => {
  void loadStreams()
  void loadTrafficBase()
})

onUnmounted(() => {
  clearRetryTimer()
})
</script>

<template>
  <AppShell
    class="p-perception"
    active="perception"
    :station="stationName"
    :ts="snapshotTs"
    title="感知层 · 模拟识别（演示）· 视频链路（YOLO 仅项目代号）+ 环境上下文"
    :subtitle="subLine"
  >
    <template #headRight>
      <span class="td-badge-warn">{{ sourceBadge }}</span>
      <span class="td-mono head-ts">处理时间戳 {{ processedAt }}</span>
    </template>

    <template #headExtra>
      <div v-if="detFailedCids.length > 0" class="head-err">
        ⚠ {{ detFailedCids.length }} 路检测读取失败({{ detFailedCids.join(' / ') }})——该路检测框不可用,是接口故障,不是"无检出"。
      </div>
    </template>

    <!-- 环境上下文(天气 / 时间 / 因地制宜的路况因子):感知层"能获取的数据"之一 -->
    <EnvContextBar :ctx="ctx" :error="ctxError" />

    <div class="td-body">
      <div class="td-col col-left">
        <ChannelLedger :channels="channels" :current-id="currentSource" @select="onSelect" />
      </div>

      <div class="td-col col-mid">
        <section v-if="pStatus === 'error'" class="td-card">
          <div class="td-card-body err-body">
            <span class="err-text">{{ pError }}</span>
            <button class="td-btn sm" type="button" @click="loadStreams">重试</button>
          </div>
        </section>
        <MonitorWall :channels="channels" :current-id="currentSource" :select-tick="selectTick" @select="onSelect" />
        <PipelinePanel
          v-if="hasChannels"
          :channels="channels"
          :current="current.def"
          :meta="current.meta"
          :summary="summary"
          :summary-unavailable="summaryUnavailable"
        />
        <SemanticsPanel />
      </div>

      <div v-if="hasChannels" class="td-col col-right">
        <DetailPanel
          :ch="current"
          :summary="summary"
          :summary-unavailable="summaryUnavailable"
          :source-pair="sourcePair"
          :assimilation="assimilation"
        />
      </div>
    </div>

    <!-- 数据供给 ↔ 需求对照(能获取的数据 / 要用到的数据 + 缺口);0 路时无可对照 -->
    <DataSupplyPanel v-if="hasChannels" :channels="channels" :current="current.def" :source-pair="sourcePair" />

    <template #foot>
      <span>{{ footSourceLine }}</span>
      <span class="right">
        检测只输出路段聚合数 · 不出车牌与身份(D3) · 全局数值 is_simulated = true · 演示数据(模拟)
      </span>
    </template>
  </AppShell>
</template>

<style scoped>
.td-body > .col-left {
  flex: 0 0 254px;
}
.td-body > .col-mid {
  flex: 1 1 auto;
  min-width: 0;
}
.td-body > .col-right {
  flex: 0 0 372px;
}
.head-ts {
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
/* 检测读取失败提示:接口故障显式可见 */
.head-err {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.5;
  color: #a06a00;
}
.err-body {
  display: flex;
  align-items: center;
  gap: 10px;
}
.err-text {
  font-size: 12px;
  color: var(--td-warning-color);
}

/* ---------- 响应式（Issue IKP3EV） ---------- */
/* 断点口径与全局 foundation 统一：max-width 1180 / 1080 / 900 / 768 / 560。
   本页 scoped 规则（.td-body > .col-left 等）特异性高于全局 .td-col，因此必须在同一断点
   显式覆盖，否则三栏的固定宽度（254 / flex / 372）会赢过全局的纵向单列。 */
@media (max-width: 1180px) {
  /* 三栏 → 纵向单列：整页由文档滚动（高度 auto / 栏内滚动取消由全局 foundation 负责） */
  .td-body {
    flex-direction: column;
    gap: 10px;
  }
  .td-body > .col-left,
  .td-body > .col-mid,
  .td-body > .col-right {
    flex: 0 0 auto;
    width: 100%;
    min-width: 0;
  }
  /* 页头错误条在窄屏可折行，长文案不再顶出横向滚动 */
  .err-body {
    flex-wrap: wrap;
  }
  .err-text,
  .head-err {
    overflow-wrap: anywhere;
  }
}
/* ≤768：页头右侧「口径角标 + 处理时间戳」不再强制一行，长角标内部可折行 */
@media (max-width: 768px) {
  .td-badge-warn,
  .head-ts {
    white-space: normal;
    overflow-wrap: anywhere;
  }
  .head-err {
    font-size: 11px;
    line-height: 1.55;
  }
  .err-body {
    align-items: flex-start;
  }
}

/* ---- 低高度桌面（≤1000px 高，且宽 >1180）：整页文档滚动 ----
   本页的 EnvContextBar / DataSupplyPanel 在 .td-body 之外；三栏 100% 高 + 页面锁一屏时，
   中间栏会被压扁、监控墙被裁且无滚动条（1366×768 / 1440×900 实测）。
   这里把栏目恢复为自然高度，由全局 `.td-page.p-perception` 放开页面高度（style.css）。
   1920×1080（1080 > 1000）不命中，桌面布局不变。 */
@media (max-height: 1000px) and (min-width: 1181px) {
  .td-body {
    flex: 0 0 auto;
  }
  .td-body > .col-left,
  .td-body > .col-mid,
  .td-body > .col-right {
    height: auto;
    max-height: none;
    overflow: visible;
  }
  /* 台账卡在低高度下不再靠 46vh 内部滚动撑高，改用自然高度 + 整页滚动 */
  .td-body > .col-left :deep(.td-card) {
    max-height: none;
  }
}
</style>
