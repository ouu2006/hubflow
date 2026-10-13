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
//   下发渠道 / 回写结果是**展示枚举**(一期无真实下发通道);空值一律「—」,不编造数字。
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { activePack } from '../../station-packs/index'
import AppShell from '../../components/AppShell.vue'
import LevelBadge from '../dashboard/components/LevelBadge.vue'
import AlertQueue from './components/AlertQueue.vue'
import AssimilationPanel from './components/AssimilationPanel.vue'
import EffectCompare from './components/EffectCompare.vue'
import FactorsPanel from './components/FactorsPanel.vue'
import PredictPanel from './components/PredictPanel.vue'
import {
  getTrafficAlerts,
  getTrafficMeta,
  getTrafficSegments,
  getTrafficSegmentSources,
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
  isStale,
  type AlertStatus,
  type CongestionLevel,
  type DispatchReceipt,
  type SegmentRecord,
  type TrafficAlert,
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
const view = ref<'queue' | 'compare'>('queue')
const sourceMode = ref<SourceMode>('both')
const selectedId = ref<string | null>(null)

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
 * 告警行 / 工作台显示的**判级**一律取**当前路段快照**(与态势总览、热力页同源),
 * 告警自带的 `level` 只是派生时的记录值——预置剧本与快照基线不同步时它会是旧值,
 * 直接上屏就会出现「队列写缓行、路段快照已拥堵」的自相矛盾(mock 侧两处基线各自维护)。
 * 快照缺该路段时退回告警记录值,不编造。
 */
function segLevel(a: TrafficAlert): CongestionLevel {
  return segMap.value[a.segment_id]?.level ?? a.level
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

async function refresh(): Promise<void> {
  const seq = ++refreshSeq
  try {
    const [alertsSnap, segSnap] = await Promise.all([getTrafficAlerts(), getTrafficSegments()])
    if (seq !== refreshSeq) return // 已被更晚的一次刷新取代:丢弃本次响应
    alerts.value = alertsSnap.alerts
    snapshotIso.value = alertsSnap.ts
    snapshotMs.value = parseStamp(alertsSnap.ts)
    const map: Record<string, SegmentRecord> = {}
    for (const s of segSnap.segments) map[s.segment_id] = s
    segMap.value = map
    dataError.value = ''
    // 默认选中第一条「待认领」
    if (selectedId.value === null && alerts.value.length > 0) {
      const first = alerts.value.find((a) => a.status === '待认领') ?? alerts.value[0]
      selectedId.value = first ? first.alert_id : null
    }
  } catch (e) {
    if (seq !== refreshSeq) return
    // 联调期接口层可能未起:SSE 重连后会再拉;此处如实提示,不静默
    dataError.value = `快照拉取失败:${e instanceof Error ? e.message : String(e)}`
  }
}

/** 排队比 L_q = 快照记录 L_q_m / L_seg_m(两位小数;取不到显示「—」)
 *  数据源视图(顶栏)在这里生效:both/video 取视频链路槽位,twin 取孪生链路槽位。 */
async function loadQueueRatio(segmentId: string): Promise<void> {
  try {
    const pair = await getTrafficSegmentSources(segmentId)
    const want: TrafficSource = sourceMode.value === 'twin' ? 'twin' : 'video'
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
  pct.value = s ? s.base_pct : 20
  channel.value = DISPATCH_CHANNELS[0]
  wbResult.value = '已缓解'
  wbOperator.value = '张工(监控)'
  wbAction.value = s ? `情报板诱导 · 分流至${s.target_name} ${s.base_pct}%` : ''
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
  unsubscribe = subscribeTrafficSnapshot(() => {
    void refresh()
  })
})

onUnmounted(() => {
  unsubscribe?.()
})
</script>

<template>
  <AppShell
    active="decision"
    :station="stationName"
    :ts="snapshotDisplay"
    v-model:sourceMode="sourceMode"
    title="决策工作台"
    subtitle="告警四态 · 渠道下发回执 · 处置结果回写"
  >
    <template #headRight>
      <span class="td-seg" role="group" aria-label="视图切换">
        <span
          class="td-seg-item"
          :class="{ on: view === 'compare' }"
          role="button"
          :aria-pressed="view === 'compare'"
          @click="view = 'compare'"
        >
          效果对比
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
      </span>
      <span class="snapshot td-mono">快照 {{ snapshotDisplay }}</span>
      <button type="button" class="td-btn sm" :disabled="resetting" @click="doReset">复位演示态</button>
    </template>

    <template #headExtra>
      <div v-if="dataError" class="head-err">{{ dataError }}</div>
    </template>

    <div class="td-body">
      <template v-if="view === 'queue'">
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
                    :min="suggestion.min_pct"
                    :max="suggestion.max_pct"
                    step="5"
                  />
                  <span class="sl-label">分流上限 {{ suggestion.max_pct }}%</span>
                </div>
                <p class="hint">
                  保留直行 {{ 100 - pct }}% · 承接路段 {{ suggestion.target_name }}（{{
                    suggestion.target_segment_id
                  }}）· 预期 {{ suggestion.expect }}
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
      <span>效果对比属仿真对照，不得称实测</span>
      <span>工作流状态存于服务端演示态 · 刷新不清，页头「复位演示态」可清</span>
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

@media (max-width: 1180px) {
  .td-body {
    flex-direction: column;
    overflow-y: auto;
  }
  .col-queue,
  .col-side,
  .col-work {
    flex: 0 0 auto;
  }
}
</style>
