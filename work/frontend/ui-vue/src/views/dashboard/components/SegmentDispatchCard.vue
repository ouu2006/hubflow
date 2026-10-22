<script setup lang="ts">
// 大屏右栏 · 直接下令（Issue IKMS18 大屏监控平台化）。
//
// 目标：像监控管理平台一样，在**大屏路段详情卡里**完成「选告警 → 下发（渠道 / 分流比例）→ 回执 → 回写」，
// 调用的是与决策页完全相同的接口（`POST /plan/dispatch` / `POST /plan/ack`），
// 状态存在接口层进程内存（重启复位）→ 大屏与决策页读同一个 `GET /alerts`，状态共享。
//
// 不造假口径：
//   · 该路段无快照记录 → 不提供下令入口（没有指标可依据，不伪造）；
//   · 该路段无关联告警 / 只剩终态告警 → 控件 disabled + 如实文案，不假装可操作；
//   · 回写必须先有下发回执（TC-07 闭环顺序），无回执时提交按钮 disabled 并给原因；
//   · 渠道是展示枚举、一期无真实下发通道、后端内存态 → 卡片内常驻说明（不得说成真实下发）。
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { postPlanAck, postPlanDispatch } from '../../../api/traffic'
import {
  DISPATCH_CHANNELS,
  diversionSuggestions,
  fallbackSuggestion,
} from '../../../shared/demoDecision'
import { formatClock, type AlertStatus, type DispatchReceipt, type SegmentRecord, type TrafficAlert, type WritebackResult } from '../../../shared/traffic'

const props = defineProps<{
  segmentId: string
  record: SegmentRecord | null
  alerts: TrafficAlert[]
}>()

const emit = defineEmits<{ (e: 'changed'): void }>()

const TERMINAL: AlertStatus[] = ['已闭环', '误报']
const RESULTS: WritebackResult[] = ['已消除', '已缓解', '未改善', '误报']

function isTerminal(status: AlertStatus): boolean {
  return TERMINAL.includes(status)
}

const candidates = computed(() => props.alerts.filter((alert) => alert.segment_id === props.segmentId))
const active = computed(() => candidates.value.filter((alert) => !isTerminal(alert.status)))
const terminalCount = computed(() => candidates.value.length - active.value.length)

const selectedId = ref<string | null>(null)
const selectedAlert = computed(() => active.value.find((alert) => alert.alert_id === selectedId.value) ?? null)

const channel = ref<string>(DISPATCH_CHANNELS[0])
const pct = ref(20)
const operator = ref('张工(大屏)')
const action = ref('')
const result = ref<WritebackResult>('已缓解')
const busy = ref(false)
const error = ref('')
const ackMsg = ref('')
/** 本次会话刚拿到的回执（服务端留痕刷新前先显示；刷新后以 /alerts 为准） */
const localReceipt = ref<DispatchReceipt | null>(null)
/** 用户是否手改过处置动作（没改过时随分流比例联动默认文案） */
const actionTouched = ref(false)

function isAutoAction(text: string): boolean {
  return text === '' || text.startsWith('情报板诱导 · 分流')
}

function resetForm(): void {
  const alert = selectedAlert.value
  localReceipt.value = null
  error.value = ''
  ackMsg.value = ''
  actionTouched.value = false
  channel.value = DISPATCH_CHANNELS[0]
  result.value = '已缓解'
  operator.value = '张工(大屏)'
  const suggestion = diversionSuggestions()[props.segmentId] ?? fallbackSuggestion(props.segmentId)
  pct.value = suggestion.base_pct > 0 ? suggestion.base_pct : 20
  action.value = suggestion.base_pct > 0
    ? `情报板诱导 · 分流至${suggestion.target_name} ${pct.value}%`
    : `情报板诱导 · 分流 ${pct.value}%`
  void alert
}

function ensureSelection(): void {
  if (!active.value.some((alert) => alert.alert_id === selectedId.value)) {
    selectedId.value = active.value[0]?.alert_id ?? null
    resetForm()
  }
}

watch(
  () => props.segmentId,
  () => {
    selectedId.value = null
    ensureSelection()
  },
  { immediate: true },
)
watch(active, ensureSelection)

watch(pct, (value) => {
  if (!actionTouched.value || isAutoAction(action.value)) {
    action.value = `情报板诱导 · 分流 ${value}%`
  }
})

/** 权威回执：优先本次会话回执；否则从服务端 /alerts 留痕还原（channels + dispatch_at + ratio） */
const receipt = computed<DispatchReceipt | null>(() => {
  const alert = selectedAlert.value
  if (!alert) return null
  if (localReceipt.value && localReceipt.value.alert_id === alert.alert_id) return localReceipt.value
  if (alert.dispatch_at && alert.channels && alert.channels.length > 0) {
    const ch = alert.channels[0] ?? '—'
    return {
      alert_id: alert.alert_id,
      channel: ch,
      ratio_pct: alert.dispatch_ratio_pct,
      receipt: `${ch}已确认`,
      at: alert.dispatch_at,
      is_simulated: true,
    }
  }
  return null
})

const dispatched = computed<boolean>(() => receipt.value !== null)
const terminal = computed<boolean>(() => (selectedAlert.value ? isTerminal(selectedAlert.value.status) : false))

/** 本段告警的处置留痕（下发回执 + 回写四项）——告警转终态后仍可见（TC-07） */
const historyRows = computed(() =>
  candidates.value
    .filter((alert) => alert.dispatch_at || alert.writeback)
    .map((alert) => ({
      alert,
      dispatch: alert.dispatch_at
        ? `${(alert.channels ?? ['—']).join(' / ')} · 分流 ${alert.dispatch_ratio_pct ?? '—'}% · ${formatClock(alert.dispatch_at)}`
        : '—',
      writeback: alert.writeback
        ? `${alert.writeback.operator} · ${alert.writeback.action} · 结果 ${alert.writeback.result} · ${formatClock(alert.writeback.at)}`
        : '—',
    })),
)
const canDispatch = computed<boolean>(
  () => Boolean(props.record) && selectedAlert.value !== null && !terminal.value && !busy.value,
)
const canAck = computed<boolean>(
  () =>
    Boolean(props.record) &&
    selectedAlert.value !== null &&
    !terminal.value &&
    dispatched.value &&
    !busy.value &&
    operator.value.trim() !== '' &&
    action.value.trim() !== '',
)

async function doDispatch(): Promise<void> {
  const alert = selectedAlert.value
  if (!alert || !canDispatch.value) return
  busy.value = true
  error.value = ''
  ackMsg.value = ''
  try {
    const r = await postPlanDispatch({
      alert_id: alert.alert_id,
      segment_id: alert.segment_id,
      channel: channel.value,
      ratio_pct: pct.value,
    })
    localReceipt.value = r
    emit('changed')
  } catch (e) {
    error.value = `下发失败：${e instanceof Error ? e.message : String(e)}`
  } finally {
    busy.value = false
  }
}

async function doAck(): Promise<void> {
  const alert = selectedAlert.value
  if (!alert || !canAck.value) return
  if (!dispatched.value) {
    error.value = '回写前置：请先下发并拿到回执（TC-07 闭环顺序：下发 → 回执 → 回写）'
    return
  }
  busy.value = true
  error.value = ''
  try {
    const r = await postPlanAck({
      alert_id: alert.alert_id,
      segment_id: alert.segment_id,
      operator: operator.value.trim(),
      action: action.value.trim(),
      result: result.value,
    })
    ackMsg.value = `回写成功：${r.result} → 状态「${r.status}」（以后端 /alerts 为准，决策页同步可见）`
    emit('changed')
  } catch (e) {
    error.value = `回写失败：${e instanceof Error ? e.message : String(e)}`
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="cmd-card">
    <div class="sec-head">
      直接下令
      <span class="td-chip ok">与决策页同一后端状态</span>
      <span class="td-chip warn">演示态 · 重启复位</span>
    </div>

    <!-- 无快照记录：不给下令入口（不伪造依据） -->
    <p v-if="!record" class="empty sm">
      该路段无路况快照（数据不可用）—— 不下发、不回写，避免拿编造指标下令。
    </p>

    <template v-else>
      <!-- 无待处置告警：如实 disabled -->
      <template v-if="active.length === 0">
        <p class="empty sm">
          <template v-if="candidates.length === 0">
            该路段暂无待处置告警（/alerts 里没有 segment_id 匹配且未闭环的记录）——无对象可下令。
          </template>
          <template v-else>
            该路段暂无待处置告警（已有 {{ terminalCount }} 条终态：已闭环 / 误报，不可重复下令）。
          </template>
        </p>
      </template>

      <template v-else>
        <!-- ① 关联告警（多条时可选） -->
        <div class="sub-head">① 关联告警<span class="sub-tag">仅未闭环可下令</span></div>
        <div v-if="active.length > 1" class="chips">
          <span
            v-for="alert in active"
            :key="alert.alert_id"
            class="td-chip pick"
            :class="{ on: alert.alert_id === selectedId }"
            role="button"
            :aria-pressed="alert.alert_id === selectedId"
            @click="selectedId = alert.alert_id; resetForm()"
          >
            {{ alert.alert_id }}（{{ alert.status }}）
          </span>
        </div>
        <div v-if="selectedAlert" class="alert-line">
          <span class="td-mono">{{ selectedAlert.alert_id }}</span>
          <span class="td-chip">{{ selectedAlert.status }}</span>
          <span class="tiny-inline">首次观测 {{ formatClock(selectedAlert.first_seen) }}</span>
          <span v-if="receipt" class="tiny-inline">已下发 {{ receipt.ratio_pct ?? '—' }}%</span>
        </div>

        <!-- ② 下发 -->
        <div class="sub-head">② 下发（渠道 + 分流比例）</div>
        <div class="ctl-row">
          <span class="ctl-k">渠道</span>
          <span class="chips">
            <span
              v-for="item in DISPATCH_CHANNELS"
              :key="item"
              class="td-chip pick"
              :class="{ on: item === channel }"
              role="button"
              :aria-pressed="item === channel"
              :aria-disabled="!canDispatch"
              @click="canDispatch && (channel = item)"
            >
              {{ item }}
            </span>
          </span>
        </div>
        <div class="ctl-row">
          <span class="ctl-k">分流</span>
          <input
            v-model.number="pct"
            class="range"
            type="range"
            min="5"
            max="100"
            step="5"
            :disabled="!canDispatch"
          />
          <span class="ctl-v td-num">{{ pct }}%</span>
        </div>
        <div class="btn-row">
          <button class="td-btn primary sm" type="button" :disabled="!canDispatch" @click="doDispatch">
            {{ receipt ? '重新下发（覆盖回执）' : `下发 · ${channel}` }}
          </button>
          <span class="tiny-inline">渠道为展示枚举 · 一期无真实下发通道</span>
        </div>
        <p v-if="receipt" class="receipt">
          回执：{{ receipt.receipt }} · 分流 {{ receipt.ratio_pct ?? '—' }}% ·
          {{ formatClock(receipt.at) }}（后端内存态，重启复位）
        </p>

        <!-- ③ 回写 -->
        <div class="sub-head">③ 处置回写（四选一）</div>
        <div class="chips">
          <span
            v-for="item in RESULTS"
            :key="item"
            class="td-chip pick"
            :class="{ on: item === result }"
            role="button"
            :aria-pressed="item === result"
            :aria-disabled="!canAck"
            @click="canAck && (result = item)"
          >
            {{ item }}
          </span>
        </div>
        <div class="wb-row">
          <label class="wd">
            <span class="wk">认领人</span>
            <input v-model="operator" class="td-input" type="text" :disabled="!canAck" />
          </label>
          <label class="wd grow">
            <span class="wk">处置动作</span>
            <input
              v-model="action"
              class="td-input"
              type="text"
              :disabled="!canAck"
              @input="actionTouched = true"
            />
          </label>
        </div>
        <div class="btn-row">
          <button class="td-btn primary sm" type="button" :disabled="!canAck" @click="doAck">
            提交回写
          </button>
          <span v-if="!dispatched" class="tiny-inline">回写前置：须先下发并拿到回执（TC-07）</span>
        </div>
        <p v-if="terminal" class="receipt">该告警已是终态（已闭环 / 误报），不可再回写，也不得互相翻转。</p>
      </template>

      <!-- 结果提示放在条件外：回写成功后告警转为终态、从 active 列表移除，提示仍需可见 -->
      <p v-if="ackMsg" class="ok-msg">{{ ackMsg }}</p>
      <p v-if="error" class="err-msg">{{ error }}</p>

      <!-- 处置留痕（TC-07）：谁 / 何时 / 动作 / 结果；告警转终态后仍从 /alerts 读回显示 -->
      <div v-if="historyRows.length > 0" class="history">
        <div class="sub-head">处置留痕（TC-07 · 后端内存态，重启复位）</div>
        <div v-for="row in historyRows" :key="row.alert.alert_id" class="hist-row">
          <span class="td-mono">{{ row.alert.alert_id }}</span>
          <span class="td-chip">{{ row.alert.status }}</span>
          <span class="tiny-inline">回执：{{ row.dispatch }}</span>
          <span class="tiny-inline">回写：{{ row.writeback }}</span>
        </div>
      </div>

      <p class="cmd-note">
        状态存在接口层进程内存（演示态，重启复位）；大屏与决策页读同一个 GET /api/traffic/alerts，
        下发回执 / 回写结果跨页一致。四项留痕：认领人（本卡输入）、时间（回执）、动作、结果（四选一）。
      </p>
    </template>

    <RouterLink class="deep-link" :to="{ path: '/decision', query: { segment: segmentId } }">
      到决策页处置（同一告警状态）→
    </RouterLink>
  </section>
</template>

<style scoped>
.cmd-card {
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
.sub-head {
  margin: 6px 0 3px;
  font-size: 11px;
  font-weight: 500;
  color: var(--td-text-color-secondary);
}
.sub-tag {
  margin-left: 4px;
  font-size: 10px;
  font-weight: 400;
  color: var(--td-text-color-placeholder);
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.pick {
  cursor: pointer;
}
.alert-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin: 2px 0 4px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.ctl-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.ctl-k {
  flex: 0 0 36px;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
.ctl-v {
  min-width: 40px;
  font-size: 11px;
  color: var(--td-text-color-primary);
}
.range {
  flex: 1;
  min-width: 0;
  accent-color: var(--td-brand-color);
}
.btn-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}
.receipt {
  margin: 4px 0 0;
  padding: 4px 8px;
  border-radius: 3px;
  background: var(--td-brand-color-1);
  font-size: 10px;
  line-height: 1.6;
  color: var(--td-text-color-primary);
}
.wb-row {
  display: flex;
  gap: 6px;
  margin-top: 4px;
}
.wd {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.wd.grow {
  flex: 1;
}
.wk {
  font-size: 10px;
  color: var(--td-text-color-placeholder);
}
.td-input {
  height: 24px;
  padding: 0 6px;
  font-size: 11px;
  border: 1px solid var(--td-component-border);
  border-radius: var(--td-radius-sm);
  background: var(--td-bg-color-container);
  color: var(--td-text-color-primary);
}
.td-input:disabled {
  opacity: 0.6;
}
.tiny-inline {
  font-size: 10px;
  color: var(--td-text-color-placeholder);
}
.empty {
  margin: 4px 0;
  font-size: 11px;
  line-height: 1.6;
  color: var(--td-text-color-placeholder);
}
.ok-msg {
  margin: 4px 0 0;
  font-size: 10px;
  color: var(--td-success-color);
}
.history {
  margin-top: 4px;
  padding: 4px 6px;
  border-radius: 3px;
  background: var(--td-bg-color-secondarycontainer);
}
.hist-row {
  display: flex;
  flex-direction: column;
  gap: 1px;
  margin-top: 3px;
  font-size: 10px;
  line-height: 1.5;
}
.err-msg {
  margin: 4px 0 0;
  padding: 4px 8px;
  border-radius: 3px;
  background: var(--td-error-color-1, #fdecee);
  color: var(--td-error-color, #d54941);
  font-size: 10px;
  line-height: 1.5;
}
.cmd-note {
  margin: 6px 0 0;
  font-size: 10px;
  line-height: 1.6;
  color: var(--td-text-color-placeholder);
}
.deep-link {
  display: inline-block;
  margin-top: 6px;
  font-size: 11px;
  color: var(--td-brand-color);
  text-decoration: none;
}

/* ==========================================================================
   响应式（Issue IKP3EV）
   断点与 DashboardView 一致：1180 / 768 / 560。
   组件本身都是 flex-wrap 的，这里只处理「渠道 chips / 滑杆 / 回写输入框」
   在手机宽度下被挤成看不清的窄列。
   ========================================================================== */
@media (max-width: 1180px) {
  /* 堆叠后右栏整行宽：不要让渠道选项和滑杆拉成一条超长的线，限制控制行内容宽度。 */
  .ctl-row .chips {
    max-width: 100%;
  }
}

@media (max-width: 560px) {
  .ctl-row {
    flex-wrap: wrap;
    row-gap: 4px;
  }
  .ctl-row .range {
    flex: 1 1 120px;
  }
  .wb-row {
    flex-wrap: wrap;
  }
  /* 认领人 / 处置动作两个输入框各占一整行（否则各剩 ~130px 宽）。 */
  .wd,
  .wd.grow {
    flex: 1 1 100%;
  }
  .td-input {
    width: 100%;
  }
  /* 两排按钮在窄屏下等宽铺开，保证可点面积。 */
  .btn-row .td-btn {
    flex: 1 1 auto;
  }
  .deep-link {
    display: block;
    margin-top: 8px;
  }
}
</style>
