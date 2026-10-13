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
import { computed, onMounted, ref, watch } from 'vue'
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
  getTrafficMeta,
  getTrafficSegmentSources,
  getTrafficSegments,
} from '../../api/traffic'
import type { AssimilationSnapshotFull, SegmentSourcePair } from '../../shared/traffic'
import { formatStamp } from '../../shared/traffic'
import ChannelLedger from './components/ChannelLedger.vue'
import DetailPanel from './components/DetailPanel.vue'
import MonitorWall from './components/MonitorWall.vue'
import PipelinePanel from './components/PipelinePanel.vue'
import SemanticsPanel from './components/SemanticsPanel.vue'
import { channels as packChannels, type ChannelDef, type ChannelState } from './components/channels'
import { activePack } from '../../station-packs/index'

const streams = ref<PerceptionStreamMeta[]>([])
const detMap = ref<Record<string, PerceptionDetections>>({})
/** detections 请求失败的通道(meta 在、检测取不到)——失败不得冒充"无检测结果" */
const detFailedSet = ref<Record<string, true>>({})
const pStatus = ref<'loading' | 'ready' | 'error'>('loading')
const pError = ref('')

/** 当前检测通道(默认 C-05 track1,与设计稿一致) */
const currentSource = ref('track1')

const summary = ref<PerceptionSummary | null>(null)
const summaryUnavailable = ref(true)
const sourcePair = ref<SegmentSourcePair | null>(null)
const assimilation = ref<AssimilationSnapshotFull | null>(null)
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

const fallbackDef = packChannels()[0] as ChannelDef
const current = computed<ChannelState>(() => {
  const hit = channels.value.find((c) => c.def.source === currentSource.value)
  return (
    hit ?? channels.value[0] ?? { def: fallbackDef, meta: null, det: null, detTotal: null, detFailed: false }
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
    const first = list[0]
    if (first && !list.some((m) => m.stream_id === currentSource.value)) {
      currentSource.value = first.stream_id
    }
  } catch {
    pStatus.value = 'error'
    pError.value = '感知演示服务未连接(先启动 work/perception/server.py,默认 127.0.0.1:8101)'
  }
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
}

function onSelect(source: string): void {
  currentSource.value = source
}

watch(currentSource, (src) => void loadDetail(src), { immediate: true })

onMounted(() => {
  void loadStreams()
  void loadTrafficBase()
})
</script>

<template>
  <AppShell
    active="perception"
    :station="stationName"
    :ts="snapshotTs"
    title="视频感知 · YOLO 链路"
    subtitle="6 段样本视频 · 检测 → 跟踪 → 透视标定 → 四项指标"
  >
    <template #headRight>
      <span class="td-badge-warn">离线样本视频 · 非实时流 · 非本站现场</span>
      <span class="td-mono head-ts">处理时间戳 {{ processedAt }}</span>
    </template>

    <template #headExtra>
      <div v-if="detFailedCids.length > 0" class="head-err">
        ⚠ {{ detFailedCids.length }} 路检测读取失败({{ detFailedCids.join(' / ') }})——该路检测框不可用,是接口故障,不是"无检出"。
      </div>
    </template>

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
        <MonitorWall :channels="channels" :current-id="currentSource" @select="onSelect" />
        <PipelinePanel
          :channels="channels"
          :current="current.def"
          :meta="current.meta"
          :summary="summary"
          :summary-unavailable="summaryUnavailable"
        />
        <SemanticsPanel />
      </div>

      <div class="td-col col-right">
        <DetailPanel
          :ch="current"
          :summary="summary"
          :summary-unavailable="summaryUnavailable"
          :source-pair="sourcePair"
          :assimilation="assimilation"
        />
      </div>
    </div>

    <template #foot>
      <span>视频为公开样本视频 · 非{{ stationName }}现场 · 非实时流</span>
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
</style>
