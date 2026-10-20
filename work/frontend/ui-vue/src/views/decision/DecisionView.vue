<script setup lang="ts">
// 决策层 · 决策工作台(按设计稿 03 重写;业务口径继承旧 DecisionView.vue 与手册 §11.2 / README 第八·九节)。
// 三栏(1440×900 一屏,各栏 .td-scroll 独立滚动):
//   左 = 处置队列(按**告警四态**分组:待认领 / 处置中 / 已闭环 / 误报,组头显示条数);
//   中 = 处置工作台(概要带 → 处置建议 + 分流比例滑杆 → 下发渠道单选 + 回执 → 处置回写四选一);
//   右 = 因素与预测(人工置位) / 预测 · 时域外推 / 数据同化 · 断面门控。
// 视图:页头右切换「效果对比 / 处置队列」(本地视图切换,不影响顶栏数据源控件)。
// 状态机硬口径:
//   认领:待认领 → 处置中(仅置本地标记);下发:→ 处置中(允许覆盖回执重下发);
//   回写:**必须先有下发回执**(TC-07 闭环顺序:下发 → 回执 → 回写),无回执不得回写;
//   回写结果四选一 → 已消除 / 已缓解 = 已闭环;未改善 = 留在处置中;误报 = 误报;
//   终态(已闭环 / 误报)**不得再回写、不得互相翻转**。
// 口径:全部数据 is_simulated=true;效果对比属仿真对照不得称实测;预测只标 L0 无精度数字;
// 决策层 · 决策工作台(Issue #77 三页收敛:页头视图扩为**决策可视化 / 处置队列 / 效果对比**三段)。
// 业务口径继承旧 DecisionView.vue 与手册 §11.2 / README 第八·九节。
//
// 三个视图(页头分段切换,不影响顶栏数据源控件):
//   ① **决策可视化**(本单新增,排首位)= 全部输入数据 + 处理过程可视化 + 可调控演示 + 输出(业主口径);
//   ② **处置队列** = 三栏:左四态队列 / 中处置工作台(建议 + 比例滑杆 + 渠道 + 回执 + 回写)/ 右因素置位 · 预测 · 同化;
//   ③ **效果对比** = 三场景 A/B/C 仿真对照(TC-14 / TC-17)。
// 状态机硬口径(处置队列视图):
//   认领:待认领 → 处置中(仅置本地标记);下发:→ 处置中(允许覆盖回执重下发);
//   回写:**必须先有下发回执**(TC-07 闭环顺序:下发 → 回执 → 回写),无回执不得回写;
//   回写结果四选一 → 已消除 / 已缓解 = 已闭环;未改善 = 留在处置中;误报 = 误报;
//   终态(已闭环 / 误报)**不得再回写、不得互相翻转**。
// 口径:全部数据 is_simulated=true;效果对比属仿真对照不得称实测;预测只标 L0 无精度数字;
//   下发渠道 / 回写结果是**展示枚举**(一期无真实下发通道);空值一律「—」,不编造数字;
//   场景注入(环境侧)与人工置位(事件侧 F07 / F08 / F11)是两个口子,不得混称(手册 §:2222)。
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { activePack } from '../../station-packs/index'
import { demoSegment } from '../../shared/demoNetwork'
import AppShell from '../../components/AppShell.vue'
import LevelBadge from '../dashboard/components/LevelBadge.vue'
import AlertQueue from './components/AlertQueue.vue'
import AssimilationPanel from './components/AssimilationPanel.vue'
import DecisionFlowPanel from './components/DecisionFlowPanel.vue'
import EffectCompare from './components/EffectCompare.vue'
import FactorsPanel from './components/FactorsPanel.vue'
import PredictPanel from './components/PredictPanel.vue'
import {
  getTrafficAlerts,
  getTrafficContext,
  getTrafficMeta,
  getTrafficSegments,
  getTrafficSegmentSources,
  getTrafficThresholds,
  postPlanAck,
  postPlanDispatch,
  postTrafficAlertsReset,
  subscribeTrafficSnapshot,
} from '../../api/traffic'
import {
  DISPATCH_CHANNELS,
  diversionSuggestions,
  fallbackSuggestion,
  type DiversionSuggestion,
} from '../../shared/demoDecision'
import {
  alertLevelOf,
  isStale,
  type AlertStatus,
  type CongestionLevel,
  type DispatchReceipt,
  type SegmentRecord,
  type ThresholdSnapshot,
  type TrafficAlert,
  type TrafficContext,
  type TrafficSource,
  type WritebackResult,
} from '../../shared/traffic'
import { formatClock, formatStamp } from '../../shared/traffic'
import type { SourceMode } from '../../shared/nav'

// ---------- 契约快照(与感知层 / 大屏同源) ----------
const alerts = ref<TrafficAlert[]>([])
const segMap = ref<Record<string, SegmentRecord>>({})
const snapshotIso = ref('')
const snapshotMs = ref(0)
// 站点名初始值取当前站点包;拿到 meta 后由 meta.station.name 覆盖(单一口径)
const stationName = ref(activePack().station.name)

// ---------- 深链：大屏「查看完整决策过程 / 到决策页处置」→ #/decision?segment=SZ-005（Issue IKMS18） ----------
// 语义：优先选中该段的告警；该段无告警时「决策可视化」仍按该段展示（不伪造告警）。
const route = useRoute()
const deepSegment = computed<string>(() => {
  const raw = route.query.segment
  return typeof raw === 'string' ? raw : Array.isArray(raw) ? (raw[0] ?? '') : ''
})
/** 视图:决策可视化(新) / 处置队列 / 效果对比 */
const view = ref<'flow' | 'queue' | 'compare'>('flow')
const sourceMode = ref<SourceMode>('both')
const selectedId = ref<string | null>(null)
/** 决策可视化视图用的环境上下文与阈值(判级演算口径) */
const ctx = ref<TrafficContext | null>(null)
const thresholds = ref<ThresholdSnapshot | null>(null)

// ---------- 处置工作流 ----------
// 下发回执与回写结果的**权威留痕在服务端 /alerts**(channels / dispatch_at / dispatch_ratio_pct / writeback),
// 本地 map 只叠加本次会话的最新操作;接口层未起时页面仍能按本地态演示。
// 状态存在 mock 服务端内存里(刷新页面不清,与后端落库口径一致),要清走页头「复位演示态」。
const statusMap = reactive<Record<string, AlertStatus>>({})
const receipts = reactive<Record<string, DispatchReceipt>>({})
const ackResults = reactive<Record<string, WritebackResult>>({})
/** 动作失败提示(下发 / 回写):一句话说清是哪一步失败、失败原因 */
const actionError = ref('')

const pct = ref(20)
const channel = ref<string>(DISPATCH_CHANNELS[0])
const queueRatio = ref('—')
const wbOperator = ref('张工(监控)')
const wbAction = ref('')
const wbResult = ref<WritebackResult>('已缓解')

/** 回写结果四选一(手册 §11.2);本页展示口径 */
const RESULTS: WritebackResult[] = ['已消除', '已缓解', '未改善', '误报']
/** 告警四态(手册 §11.2)展示顺序 */
const STATUS_ORDER: AlertStatus[] = ['待认领', '处置中', '已闭环', '误报']

// ---------- 工具(时间 / 时长一律同源于快照时间,不取浏览器墙钟) ----------
function parseStamp(s: string): number {
  if (!s) return Number.NaN
  const iso = s.includes('T') ? s : s.replace(' ', 'T')
  const ms = Date.parse(iso)
  return Number.isNaN(ms) ? Number.NaN : ms
}

/** ISO(带偏移)→ 展示用 'YYYY-MM-DD HH:mm:ss' */
/** ISO → `YYYY-MM-DD HH:mm:ss`（本地展示口径，统一走 shared/traffic 的 formatStamp） */
function isoToStamp(iso: string): string {
  return formatStamp(iso)
}

/** 留痕时间串只取时分秒（统一走 shared/traffic 的 formatClock） */
function timeOf(stamp: string): string {
  return formatClock(stamp)
}

const hhmmss = timeOf

function fmtDuration(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return '—'
  const total = Math.floor(ms / 1000)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h > 0) return `${h} h ${m} min`
  if (m > 0) return s > 0 ? `${m} min ${s} s` : `${m} min`
  return `${s} s`
}

function isTerminalStatus(s: AlertStatus): boolean {
  return s === '已闭环' || s === '误报'
}

function segStale(segmentId: string): boolean {
  const seg = segMap.value[segmentId]
  return seg ? isStale(seg) : false
}

/**
 * 告警行 / 工作台显示的**判级**一律取**当前路段快照**(与态势总览、大屏同源),
 * 告警自带的 `level` 只是派生时的记录值——预置剧本与快照基线不同步时它会是旧值,
 * 直接上屏就会出现「队列写缓行、路段快照已拥堵」的自相矛盾(mock 侧两处基线各自维护)。
 * 快照缺该路段时退回告警记录值,不编造。
 *
 * ⚠️ 实现收敛到 `shared/traffic.ts` 的 `alertLevelOf`(Issue IKLLXG):
 *    与监控大屏的右栏关联告警 / 底部告警条**共用同一个函数**,四处只留一份口径。
 */
function segLevel(a: TrafficAlert): CongestionLevel {
  return alertLevelOf(a, (id) => segMap.value[id])
}

// ---------- 选中告警派生态 ----------
const selected = computed(() => alerts.value.find((a) => a.alert_id === selectedId.value) ?? null)

function statusOf(a: TrafficAlert): AlertStatus {
  return statusMap[a.alert_id] ?? a.status
}

const selectedStatus = computed<AlertStatus | null>(() => (selected.value ? statusOf(selected.value) : null))
const statusLabel = computed(() => selectedStatus.value ?? '—')
const terminal = computed(() => selectedStatus.value !== null && isTerminalStatus(selectedStatus.value))
const selectedStale = computed(() => (selected.value ? segStale(selected.value.segment_id) : false))

const suggestion = computed<DiversionSuggestion | null>(() =>
  selected.value
    ? diversionSuggestions()[selected.value.segment_id] ?? fallbackSuggestion(selected.value.segment_id)
    : null,
)

/** 站点包是否给该路段预置了分流建议(base_pct > 0)。
 *  未预置时(remote 模式常见:告警路段与站点包预置段号不一定重合)**分流比例仍可人工设置**,
 *  页面如实标「无系统预置建议」,不把兜底的 0% 说成系统建议。 */
const hasSuggestion = computed<boolean>(() => (suggestion.value?.base_pct ?? 0) > 0)
const suggestionMin = computed<number>(() => (hasSuggestion.value ? (suggestion.value?.min_pct ?? 0) : 5))
const suggestionMax = computed<number>(() => (hasSuggestion.value ? (suggestion.value?.max_pct ?? 100) : 100))

const receipt = computed<DispatchReceipt | null>(() => {
  const a = selected.value
  if (!a) return null
  const local = receipts[a.alert_id]
  if (local) return local
  // 刷新 / 切页回来后从服务端留痕还原(channels + dispatch_at + dispatch_ratio_pct),审计不丢
  if (a.dispatch_at && a.channels && a.channels.length > 0) {
    const ch = a.channels[0] ?? '—'
    return {
      alert_id: a.alert_id,
      channel: ch,
      // 后端未回比例时保持缺省:回执行显示「—」而不是 0(0% 是另一个意思)
      ratio_pct: a.dispatch_ratio_pct,
      receipt: `${ch}已确认`,
      at: a.dispatch_at,
      is_simulated: true,
    }
  }
  return null
})

/** 是否已下发(有派发回执);回写的前置条件(TC-07:下发 → 回执 → 回写) */
const dispatched = computed(() => receipt.value !== null)

const firstSeenText = computed(() => (selected.value ? timeOf(selected.value.first_seen) : '—'))

const durationText = computed(() => {
  const a = selected.value
  if (!a || !snapshotMs.value) return '—'
  const t0 = parseStamp(a.first_seen)
  if (Number.isNaN(t0)) return '—'
  return fmtDuration(snapshotMs.value - t0)
})

const dispatchLabel = computed(() => {
  if (!selected.value) return '下发'
  if (terminal.value) return `已终结（${statusLabel.value}）`
  return receipt.value ? '重新下发(覆盖回执)' : `下发 · ${channel.value}`
})

const submitDisabled = computed(
  () =>
    terminal.value ||
    !dispatched.value ||
    wbOperator.value.trim() === '' ||
    wbAction.value.trim() === '',
)

const snapshotDisplay = computed(() => isoToStamp(snapshotIso.value))

// ---------- 左栏分组 ----------
const openCount = computed(() => alerts.value.filter((a) => !isTerminalStatus(statusOf(a))).length)

/** 终态行显示回写结果(已消除 / 已缓解 / 误报),其余显示四态本身 */
function chipOf(a: TrafficAlert): string {
  const st = statusOf(a)
  if (st === '已闭环') return ackResults[a.alert_id] ?? a.writeback?.result ?? '已闭环'
  return st
}

const groups = computed(() =>
  STATUS_ORDER.map((state) => ({
    state,
    items: alerts.value
      .filter((a) => statusOf(a) === state)
      .map((a) => ({
        id: a.alert_id,
        segId: a.segment_id,
        name: a.segment_name,
        level: segLevel(a),
        stale: segStale(a.segment_id),
        time: timeOf(a.first_seen),
        chip: chipOf(a),
        state: statusOf(a),
      })),
  })),
)

// ---------- 拉取 ----------
let unsubscribe: (() => void) | null = null
/** 刷新序号:SSE 触发与手动刷新可能并发,只让最后一次的响应落到页面(旧响应丢弃) */
let refreshSeq = 0
/** 接口层未起时的降级提示(空 = 正常) */
const dataError = ref('')
/** SSE 刷新通道连接状态:断开时页面不会自动刷新,必须显式提示(TC-06 断流降级) */
const sseConnected = ref(true)

async function refresh(): Promise<void> {
  const seq = ++refreshSeq
  try {
    const [alertsSnap, segSnap, ctxRes, thrRes] = await Promise.all([
      getTrafficAlerts(),
      getTrafficSegments(),
      getTrafficContext(),
      getTrafficThresholds(),
    ])
    if (seq !== refreshSeq) return // 已被更晚的一次刷新取代:丢弃本次响应
    alerts.value = alertsSnap.alerts
    snapshotIso.value = alertsSnap.ts
    snapshotMs.value = parseStamp(alertsSnap.ts)
    const map: Record<string, SegmentRecord> = {}
    for (const s of segSnap.segments) map[s.segment_id] = s
    segMap.value = map
    // 决策可视化用的环境上下文与阈值:取不到保持 null(面板如实显示「未取到」,不编造)
    ctx.value = ctxRes
    thresholds.value = thrRes
    dataError.value = ''
    // 默认选中第一条「待认领」；深链点名的段优先选它自己的告警（Issue IKMS18）。
    // 深链段没有告警时**不自动选别的段**——否则「决策可视化」会被别的段抢走，深链静默失效。
    if (selectedId.value === null && alerts.value.length > 0) {
      const wanted = deepSegment.value
      if (wanted) {
        selectedId.value = alerts.value.find((a) => a.segment_id === wanted)?.alert_id ?? null
      } else {
        const first = alerts.value.find((a) => a.status === '待认领') ?? alerts.value[0]
        selectedId.value = first?.alert_id ?? null
      }
    }
  } catch (e) {
    if (seq !== refreshSeq) return
    // 联调期接口层可能未起:SSE 重连后会再拉;此处如实提示,不静默
    dataError.value = `快照拉取失败:${e instanceof Error ? e.message : String(e)}`
  }
}

/**
 * 排队比 L_q = 快照记录 L_q_m / L_seg_m(两位小数;取不到显示「—」)
 * 数据源视图(顶栏)在这里生效:`twin` 取孪生槽位、`video` 取视频槽位;
 * `both`(默认)沿本页原口径取**孪生链路**(= 虚拟检测器 L_q),不因接线而改变默认读数。
 */
async function loadQueueRatio(segmentId: string): Promise<void> {
  try {
    const pair = await getTrafficSegmentSources(segmentId)
    const want: TrafficSource = sourceMode.value === 'video' ? 'video' : 'twin'
    const slot = pair.slots.find((s) => s.source === want)?.record ?? null
    const fallback = pair.slots.find((s) => s.source === 'twin')?.record ?? null
    const rec = slot ?? fallback
    if (selected.value?.segment_id !== segmentId) return // 选择已变:丢弃过期响应
    if (rec && typeof rec.L_q_m === 'number' && typeof rec.L_seg_m === 'number' && rec.L_seg_m > 0) {
      queueRatio.value = (rec.L_q_m / rec.L_seg_m).toFixed(2)
    } else {
      queueRatio.value = '—'
    }
  } catch {
    queueRatio.value = '—'
  }
}

// ---------- 交互 ----------
function onSelect(id: string): void {
  selectedId.value = id
}

function onFactorsChanged(): void {
  void refresh()
}

/** 认领:待认领 → 处置中(仅置本地标记) */
function claim(): void {
  const a = selected.value
  if (!a || statusOf(a) !== '待认领') return
  statusMap[a.alert_id] = '处置中'
}

/** 复位演示态:清服务端下发 / 回写运行态,再拉回初始快照(与 factors 复位同口径) */
const resetting = ref(false)
async function doReset(): Promise<void> {
  resetting.value = true
  actionError.value = ''
  try {
    await postTrafficAlertsReset()
    for (const k of Object.keys(statusMap)) delete statusMap[k]
    for (const k of Object.keys(receipts)) delete receipts[k]
    for (const k of Object.keys(ackResults)) delete ackResults[k]
    await refresh()
  } catch (e) {
    actionError.value = `复位失败:${e instanceof Error ? e.message : String(e)}`
  } finally {
    resetting.value = false
  }
}

async function doDispatch(): Promise<void> {
  const a = selected.value
  const s = suggestion.value
  if (!a || !s || terminal.value) return
  actionError.value = ''
  try {
    const r = await postPlanDispatch({
      alert_id: a.alert_id,
      segment_id: a.segment_id,
      channel: channel.value,
      ratio_pct: pct.value,
    })
    receipts[a.alert_id] = r
    statusMap[a.alert_id] = '处置中'
  } catch (e) {
    // 动作失败必须可见:不然操作员分不清"没点到"还是"下发被拒"
    actionError.value = `下发失败:${e instanceof Error ? e.message : String(e)}`
  }
}

async function doAck(): Promise<void> {
  const a = selected.value
  if (!a || terminal.value) return
  const operator = wbOperator.value.trim()
  const action = wbAction.value.trim()
  if (!operator || !action) return
  if (!dispatched.value) {
    actionError.value = '回写失败:该告警尚未下发(无派发回执),请先下发分流方案'
    return
  }
  actionError.value = ''
  try {
    await postPlanAck({
      alert_id: a.alert_id,
      segment_id: a.segment_id,
      operator,
      action,
      result: wbResult.value,
    })
    ackResults[a.alert_id] = wbResult.value
    statusMap[a.alert_id] =
      wbResult.value === '误报' ? '误报' : wbResult.value === '未改善' ? '处置中' : '已闭环'
  } catch (e) {
    actionError.value = `回写失败:${e instanceof Error ? e.message : String(e)}`
  }
}

// 选中变化:重置表单默认值(分流比例 = 建议基准;渠道不跨告警沿用)
watch(selectedId, () => {
  const a = selected.value
  const s = suggestion.value
  // 有系统预置建议 → 用建议基准比例;没有(兜底 0%)→ 给人工默认 20%,不把 0% 当建议
  pct.value = s && s.base_pct > 0 ? s.base_pct : 20
  channel.value = DISPATCH_CHANNELS[0]
  wbResult.value = '已缓解'
  wbOperator.value = '张工(监控)'
  wbAction.value = s && s.base_pct > 0 ? `情报板诱导 · 分流至${s.target_name} ${s.base_pct}%` : '情报板诱导 · 分流(人工设置比例)'
  queueRatio.value = '—'
  actionError.value = ''
  if (a) void loadQueueRatio(a.segment_id)
})

// 数据源视图切换(顶栏):排队比按所选链路口径重取
watch(sourceMode, () => {
  const a = selected.value
  if (a) void loadQueueRatio(a.segment_id)
})

onMounted(() => {
  void refresh()
  void (async () => {
    try {
      const meta = await getTrafficMeta()
      stationName.value = meta.station.name
    } catch {
      /* 保持默认站点名 */
    }
  })()
  unsubscribe = subscribeTrafficSnapshot(
    () => {
      void refresh()
    },
    (connected) => {
      sseConnected.value = connected
      if (connected) void refresh()
    },
  )
})

onUnmounted(() => {
  unsubscribe?.()
})

// ---------- 决策可视化视图(本单新增)的派生数据 ----------
/** 该视图按**路段**工作:优先选中告警所属路段;没有选中告警时深链段号优先,再退回首条路段快照 */
const flowSegmentId = computed<string>(
  () => selected.value?.segment_id ?? (deepSegment.value || Object.keys(segMap.value)[0] || ''),
)

const flowRecord = computed<SegmentRecord | null>(() => segMap.value[flowSegmentId.value] ?? null)

const flowName = computed<string>(() => {
  const id = flowSegmentId.value
  if (!id) return '—'
  return (
    demoSegment(id)?.name ??
    alerts.value.find((a) => a.segment_id === id)?.segment_name ??
    id
  )
})

/** 该路段的生效因素(从快照里取;与因素面板同源) */
const flowFactors = computed(() => {
  const r = flowRecord.value
  if (!r) return []
  return (r.factors_applied ?? []).map((f) => ({ ...f, segment_id: r.segment_id }))
})

/** 该路段的系统建议(站点包模板;未命中走兜底) */
const flowSuggestion = computed<DiversionSuggestion | null>(() =>
  flowSegmentId.value
    ? diversionSuggestions()[flowSegmentId.value] ?? fallbackSuggestion(flowSegmentId.value)
    : null,
)

/** 站点包的场景预设档(决策可视化的"一键注入") */
const scenarioPresets = computed(() => activePack().scenarios.map((s) => ({ ...s })))

/** 调控后重算:重拉快照(判级 / CI / 因素 / 预测随之更新) */
function onFlowChanged(): void {
  void refresh()
}
</script>

<template>
  <AppShell
    active="decision"
    :station="stationName"
    :ts="snapshotDisplay"
    v-model:sourceMode="sourceMode"
    title="决策层"
    subtitle="决策可视化 · 处置闭环(四态 / 下发回执 / 回写)· 效果对比"
  >
    <template #headRight>
      <span class="td-seg" role="group" aria-label="视图切换">
        <span
          class="td-seg-item"
          :class="{ on: view === 'flow' }"
          role="button"
          :aria-pressed="view === 'flow'"
          @click="view = 'flow'"
        >
          决策可视化
        </span>
        <span
          class="td-seg-item"
          :class="{ on: view === 'queue' }"
          role="button"
          :aria-pressed="view === 'queue'"
          @click="view = 'queue'"
        >
          处置队列
        </span>
        <span
          class="td-seg-item"
          :class="{ on: view === 'compare' }"
          role="button"
          :aria-pressed="view === 'compare'"
          @click="view = 'compare'"
        >
          效果对比
        </span>
      </span>
      <span class="snapshot td-mono">快照 {{ snapshotDisplay }}</span>
      <button type="button" class="td-btn sm" :disabled="resetting" @click="doReset">复位演示态</button>
    </template>

    <template #headExtra>
      <div v-if="dataError" class="head-err">{{ dataError }}</div>
      <div v-if="!sseConnected" class="head-err">
        ⚠ 实时刷新通道(SSE)未连接 —— 页面不会自动刷新,正在自动重连;请勿把当前显示当作最新快照。
        <button class="td-btn sm" type="button" @click="refresh">立即刷新</button>
      </div>
    </template>

    <div class="td-body">
      <!-- 决策可视化视图(本单新增):全部输入 + 处理过程 + 可调控 + 输出 -->
      <div v-if="view === 'flow'" class="td-col flow-col td-scroll">
        <DecisionFlowPanel
          :record="flowRecord"
          :name="flowName"
          :factors="flowFactors"
          :ctx="ctx"
          :thresholds="thresholds"
          :suggestion="flowSuggestion"
          :presets="scenarioPresets"
          @changed="onFlowChanged"
        />
      </div>

      <template v-else-if="view === 'queue'">
        <!-- 左栏 · 处置队列 -->
        <div class="td-col col-queue td-scroll">
          <AlertQueue
            :groups="groups"
            :selected-id="selectedId"
            :total="alerts.length"
            :open-count="openCount"
            @select="onSelect"
          />
        </div>

        <!-- 中栏 · 处置工作台 -->
        <div class="td-col col-work td-scroll">
          <section class="td-card">
            <div class="td-card-head">
              <span class="td-mono wb-id">{{ selected ? selected.alert_id : '—' }}</span>
              <span class="td-chip">{{ statusLabel }}</span>
              <button
                type="button"
                class="td-btn sm claim"
                :disabled="statusLabel !== '待认领'"
                @click="claim"
              >
                {{ statusLabel === '待认领' ? '认领' : '已认领' }}
              </button>
            </div>

            <div v-if="selected && suggestion" class="td-card-body wb-body">
              <div class="wb-main">
              <!-- 概要带 -->
              <div class="band">
                <div class="bi">
                  <span class="bk">路段</span>
                  <span class="bv">
                    <span class="td-mono">{{ selected.segment_id }}</span>
                    {{ selected.segment_name }}
                  </span>
                </div>
                <div class="bi">
                  <span class="bk">当前判级(路段快照)</span>
                  <LevelBadge :level="segLevel(selected)" :stale="selectedStale" />
                </div>
                <div class="bi">
                  <span class="bk">首次观测</span>
                  <span class="bv td-num">{{ firstSeenText }}</span>
                </div>
                <div class="bi">
                  <span class="bk">持续</span>
                  <span class="bv td-num">{{ durationText }}</span>
                </div>
                <div class="bi">
                  <span class="bk">排队比 L_q</span>
                  <span class="bv td-num">{{ queueRatio }}</span>
                </div>
              </div>

              <!-- ① 处置建议 · 系统生成 -->
              <section class="sec">
                <div class="sec-head">
                  处置建议 · 系统生成
                  <span class="sec-tag">分流比例可人工编辑</span>
                </div>
                <p class="why">{{ suggestion.why }}</p>
                <div class="slider-row">
                  <span class="sl-label">分流 <b>{{ pct }}%</b></span>
                  <input
                    v-model.number="pct"
                    class="range"
                    type="range"
                    :min="suggestionMin"
                    :max="suggestionMax"
                    step="5"
                  />
                  <span class="sl-label">
                    {{ hasSuggestion ? `分流上限 ${suggestionMax}%` : '无系统预置建议 · 人工设置比例' }}
                  </span>
                </div>
                <p class="hint">
                  <template v-if="hasSuggestion">
                    保留直行 {{ 100 - pct }}% · 承接路段 {{ suggestion.target_name }}（{{
                      suggestion.target_segment_id
                    }}）· 预期 {{ suggestion.expect }}
                  </template>
                  <template v-else>
                    保留直行 {{ 100 - pct }}% · 系统无预置承接段（站点包未覆盖该路段）；渠道为展示枚举，下发仍会留回执
                  </template>
                </p>
              </section>

              <!-- ② 下发渠道 · 单选 -->
              <section class="sec">
                <div class="sec-head">
                  下发渠道 · 单选
                  <span class="sec-tag">已选:{{ channel }}</span>
                </div>
                <div class="chips">
                  <span
                    v-for="c in DISPATCH_CHANNELS"
                    :key="c"
                    class="td-chip pick"
                    :class="{ on: c === channel }"
                    role="button"
                    :aria-pressed="c === channel"
                    @click="channel = c"
                  >
                    {{ c }}
                  </span>
                </div>
                <button type="button" class="td-btn primary" :disabled="terminal" @click="doDispatch">
                  {{ dispatchLabel }}
                </button>
                <p v-if="receipt" class="receipt">
                  回执:{{ receipt.receipt }} · 分流 {{ receipt.ratio_pct ?? '—' }}% · {{ hhmmss(receipt.at) }}
                </p>
                <p class="note">渠道为展示枚举 · 一期无真实下发通道(本页展示口径)</p>
              </section>
              <!-- ③ 处置回写 · 结果四选一 -->
              <section class="sec">
                <div class="sec-head">处置回写 · 结果四选一</div>
                <div class="chips">
                  <span
                    v-for="r in RESULTS"
                    :key="r"
                    class="td-chip pick"
                    :class="{ on: r === wbResult }"
                    role="button"
                    :aria-pressed="r === wbResult"
                    @click="wbResult = r"
                  >
                    {{ r }}
                  </span>
                </div>
                <div class="wb-row">
                  <label class="wd">
                    <span class="wk">认领人</span>
                    <input v-model="wbOperator" class="td-input" type="text" />
                  </label>
                  <label class="wd grow">
                    <span class="wk">处置动作</span>
                    <input v-model="wbAction" class="td-input" type="text" />
                  </label>
                </div>
                <button type="button" class="td-btn primary" :disabled="submitDisabled" @click="doAck">
                  {{ terminal ? '结果已回写' : '提交回写' }}
                </button>
                <p v-if="!terminal && !dispatched" class="note warn-note">
                  回写前置:须先下发并拿到派发回执(TC-07 闭环顺序:下发 → 回执 → 回写)。
                </p>
                <p v-if="terminal" class="note">终态（已闭环 / 误报）不可再回写，也不得互相翻转。</p>
                <p v-if="terminal && selected?.writeback" class="note">
                  回写留痕：{{ selected.writeback.operator }} · {{ selected.writeback.action }} ·
                  结果 {{ selected.writeback.result }} · {{ hhmmss(selected.writeback.at) }}
                  <span class="sep">|</span>与决策页 / 大屏同源（GET /api/traffic/alerts）
                </p>
                <p v-else class="note">
                  结果四选一为展示口径 · 流转:已消除 / 已缓解 → 已闭环;未改善 → 留在处置中;误报 → 误报
                </p>
                <p v-if="actionError" class="note err-note">{{ actionError }}</p>
              </section>
              </div>
              <!-- 卡片右侧竖排小注:结果回写须同步至效果对比报表 -->
              <div class="wb-side">结果回写须同步至效果对比报表</div>
            </div>

            <div v-else class="td-card-body">
              <p class="empty">← 在左栏选择一条告警开始处置</p>
            </div>
          </section>
        </div>

        <!-- 右栏 · 因素与预测 / 预测 / 数据同化 -->
        <div class="td-col col-side td-scroll">
          <FactorsPanel :segment-id="selected ? selected.segment_id : ''" @changed="onFactorsChanged" />
          <PredictPanel :segment-id="selected ? selected.segment_id : ''" />
          <AssimilationPanel />
        </div>
      </template>

      <!-- 效果对比视图 -->
      <div v-else class="td-col cmp-col td-scroll">
        <EffectCompare />
      </div>
    </div>

    <template #foot>
      <span>快照时间 {{ snapshotDisplay }}</span>
      <span>效果对比属仿真对照,不得称实测</span>
      <span>工作流状态存于服务端演示态 · 刷新不清,页头「复位演示态」可清</span>
      <span class="right td-mono">全部数据 is_simulated = true</span>
    </template>
  </AppShell>
</template>

<style scoped>
/* 三栏宽度:左(队列)固定 / 中(工作台)弹性 / 右(因素·预测·同化)固定。
   三栏都带 .td-scroll(栏内自滚动),避免旧页左栏漏滚动导致按钮被后续面板遮挡点不到。 */
.col-queue {
  flex: 0 0 236px;
}
.col-work {
  flex: 1 1 auto;
  min-width: 0;
}
.col-side {
  flex: 0 0 380px;
}
.cmp-col {
  flex: 1 1 auto;
  min-width: 0;
}
.flow-col {
  flex: 1 1 auto;
  min-width: 0;
}
.snapshot {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}

/* 工作台卡片头 */
.wb-id {
  font-size: 13px;
  color: var(--td-text-color-primary);
}
.claim {
  margin-left: auto;
}

/* 主体 + 右侧竖排小注 */
.wb-body {
  display: flex;
  gap: 10px;
}
.wb-main {
  flex: 1;
  min-width: 0;
}
.wb-side {
  writing-mode: vertical-rl;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-left: 6px;
  border-left: 1px dashed var(--td-component-stroke);
  font-size: 11px;
  letter-spacing: 1px;
  color: var(--td-text-color-placeholder);
}

/* 概要带 */
.band {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 20px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--td-component-stroke);
}
.bi {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}
.bk {
  color: var(--td-text-color-placeholder);
}
.bv {
  color: var(--td-text-color-primary);
}

/* 工作台各段 */
.sec {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 0;
  border-bottom: 1px solid var(--td-component-stroke);
}
.sec:last-child {
  border-bottom: none;
  padding-bottom: 0;
}
.sec-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}
.sec-tag {
  margin-left: auto;
  font-size: 11px;
  font-weight: 400;
  color: var(--td-text-color-placeholder);
}
.why {
  margin: 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--td-text-color-primary);
}
.slider-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.range {
  flex: 1;
  min-width: 0;
  accent-color: var(--td-brand-color);
}
.sl-label {
  font-size: 11px;
  color: var(--td-text-color-secondary);
  white-space: nowrap;
}
.sl-label b {
  color: var(--td-text-color-primary);
}
.hint {
  margin: 0;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.pick {
  cursor: pointer;
}
.receipt {
  margin: 0;
  font-size: 12px;
  color: var(--td-text-color-primary);
}
.note {
  margin: 0;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
.wb-row {
  display: flex;
  gap: 10px;
}
.wd {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.wd.grow {
  flex: 1;
}
.wk {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  white-space: nowrap;
}
.td-input {
  flex: 1;
  min-width: 0;
  height: 26px;
  padding: 0 8px;
  font-size: 12px;
  font-family: inherit;
  color: var(--td-text-color-primary);
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-border);
  border-radius: var(--td-radius-sm);
}
.td-input:focus {
  outline: none;
  border-color: var(--td-brand-color);
}
.empty {
  margin: 0;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}

/* 失败 / 前置提示:警告色文字,不引入新色轴 */
.warn-note {
  color: #a06a00;
}
.err-note {
  color: #ad352f;
}
.head-err {
  margin-top: 4px;
  font-size: 11px;
  color: #ad352f;
}

/* ---------- 响应式（Issue IKP3EV） ---------- */
/* 断点与全局 foundation 对齐:1366 / 1180 / 1080 / 900 / 768 / 560(一律 max-width)。
   全局在 ≤1180 负责「整页文档滚动」(.td-page 高度 auto、.td-main 不再 flex:1、
   .td-body 纵向单列、.td-col 高度 auto 且 overflow visible),本文件不再重复定义整页高度,
   只补决策页自己的列宽 / 列级滚动 / 间距 / 控件。 */

/* ≤1180:三个视图(决策可视化单列 / 处置队列三栏 / 效果对比两列)一律占满整宽;
   列级 .td-scroll 取消内滚动,统一交给整页文档滚动(避免滚动套滚动)。
   断点内同时覆盖基础列宽,即使全局 foundation 尚未生效也不会横向溢出。 */
@media (max-width: 1180px) {
  .td-body {
    flex-direction: column;
    gap: 8px;
    padding: 0 12px 10px;
  }
  .flow-col,
  .cmp-col,
  .col-queue,
  .col-work,
  .col-side {
    flex: 0 0 auto;
    width: 100%;
    min-width: 0;
  }
  .td-col {
    overflow: visible;
    min-height: 0;
  }
}

/* ≤1080(含 1080×1920 竖屏):单列已成立,进一步压缩主体左右留白。 */
@media (max-width: 1080px) {
  .td-body {
    padding: 0 10px 8px;
  }
}

/* ≤900:页头右侧控件(视图切换 / 快照 / 复位按钮)可压缩换行;
   工作台右侧竖排小注改横排(保留文案,不隐藏信息)。 */
@media (max-width: 900px) {
  .td-seg {
    flex-wrap: wrap;
  }
  .snapshot {
    font-size: 10px;
  }
  .wb-body {
    flex-direction: column;
    gap: 6px;
  }
  .wb-side {
    writing-mode: horizontal-tb;
    justify-content: flex-start;
    padding: 6px 0 0;
    border-left: none;
    border-top: 1px dashed var(--td-component-stroke);
    letter-spacing: 0;
  }
  .sec {
    gap: 6px;
    padding: 8px 0;
  }
}

/* ≤768:工作台滑杆 / 输入行换行并全宽,按钮触摸高度抬到 32px。 */
@media (max-width: 768px) {
  .td-body {
    padding: 0 10px 8px;
  }
  .slider-row {
    flex-wrap: wrap;
    gap: 6px;
  }
  .slider-row .range {
    flex: 1 1 100%;
  }
  .wb-row {
    flex-wrap: wrap;
    gap: 6px;
  }
  .wd,
  .wd.grow {
    flex: 1 1 100%;
  }
  .td-input {
    height: 32px;
  }
  .td-btn {
    height: 32px;
  }
  .td-btn.sm {
    height: 28px;
  }
  .band {
    gap: 6px 12px;
  }
  .sec-head {
    flex-wrap: wrap;
  }
  .sec-tag {
    margin-left: 0;
  }
}

/* ≤560:页头仅留视图切换与复位(快照时间在顶栏 / 页脚同源展示);分段控件占满整行。 */
@media (max-width: 560px) {
  .td-body {
    padding: 0 8px 8px;
  }
  .snapshot {
    display: none;
  }
  .td-seg {
    width: 100%;
  }
  .td-seg-item {
    flex: 1 1 0;
    padding: 3px 4px;
    text-align: center;
    white-space: nowrap;
  }
  .td-btn {
    padding: 0 10px;
  }
  .sec-head {
    font-size: 11px;
  }
}
</style>
