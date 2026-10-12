<script setup lang="ts">
// 决策层 · 决策工作台(Issue #59,三层前端之二;Issue #66 按手册 §11.2 对齐判定口径):
//   左 = 事件告警列表(等级/路段/时间/指标依据/状态四态) + 处置工作流(系统建议 → 人工编辑 → 下发渠道 → 回执 → 处置回写);
//   右 = 因素与预测(含人工置位,TC-16 口径) + 数据同化状态 + 阈值配置(P1 只读);
//   下 = 效果对比报表(不推荐 / 此刻最快 / 协同推荐 三组对比 + 处置前后三项,TC-14/TC-17)。
// 数据:告警/因素/预测从契约 segments 快照派生(getTrafficSegments + SSE);
//   人工置位走 mock POST /api/traffic/factors;同化状态读 mock /api/traffic/assimilation;
//   分流建议/效果对照/阈值为演示数据(demoDecision.ts)。全部 is_simulated=true。
// 口径:效果对比属仿真结果不得称实测;预测不显示精度数字;工作流状态为页面内存态(刷新复位);
//   一期无真实下发通道(信号只生成建议,不下发信号机,手册 §:2262)。
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import {
  getTrafficAssimilation,
  getTrafficSegments,
  postTrafficFactor,
  postTrafficFactorReset,
  subscribeTrafficSnapshot,
} from '../../api/traffic'
import { demoSegment } from '../../shared/demoNetwork'
import {
  ACK_COMPARISON,
  DISPATCH_CHANNELS,
  DIVERSION_SUGGESTIONS,
  EFFECT_SCENARIOS,
  fallbackSuggestion,
  LEVEL_THRESHOLDS,
  MANUAL_FACTOR_PRESETS,
  THRESHOLD_CHANGELOG,
  type DiversionSuggestion,
  type EffectMetric,
} from '../../shared/demoDecision'
import {
  isStale,
  type AssimilationSnapshot,
  type CongestionLevel,
  type SegmentRecord,
} from '../../shared/traffic'
import LevelBadge from '../dashboard/components/LevelBadge.vue'

// ---------- 契约快照(与感知层/大屏同源) ----------
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

function segName(id: string): string {
  return demoSegment(id)?.name ?? id
}

// ---------- 事件告警列表(从快照派生) ----------
// 状态四态照抄手册 §11.2(:1860):待认领 / 处置中 / 已闭环 / 误报。
// 流转:待认领 --下发--> 处置中 --回写--> 已闭环(已消除|已缓解) | 误报 | 未改善则留在处置中。
type AlertStatus = 'unclaimed' | 'processing' | 'closed' | 'false_alarm'
const STATUS_LABEL: Record<AlertStatus, string> = {
  unclaimed: '待认领',
  processing: '处置中',
  closed: '已闭环',
  false_alarm: '误报',
}
const TRIGGER_LABEL: Record<string, string> = { x: '饱和度', v: '车速', k: '密度', L_q: '排队长度', T_d: '消散时间' }
// 硬触发类(手册 §:2840-2841 / §:3048 封路类优先):F06 违停占道 / F07 事故故障车封道 / F08 施工管制
const HARD_FACTOR_IDS = ['F06', 'F07', 'F08']

interface AlertItem {
  id: string
  segment_id: string
  name: string
  level: CongestionLevel
  stale: boolean
  title: string
  basis: string
  status: AlertStatus
}

const statusMap = reactive<Record<string, AlertStatus>>({})

/** 告警时间(手册 §11.2 要求"时间"列):记录该告警**首次被观测到**的快照时间(仿真时钟,不混墙钟) */
const firstSeen = reactive<Record<string, string>>({})

const alerts = computed<AlertItem[]>(() => {
  const out: AlertItem[] = []
  for (const seg of segments.value) {
    const name = segName(seg.segment_id)
    const status = statusMap[seg.segment_id] ?? 'unclaimed'
    if (isStale(seg)) {
      out.push({
        id: `${seg.segment_id}:stale`,
        segment_id: seg.segment_id,
        name,
        level: seg.level,
        stale: true,
        title: '数据不可用(陈旧)',
        basis: 'data_age_s 超限,只展示、不进推荐计算',
        status,
      })
      continue
    }
    const hard = (seg.factors_applied ?? []).find((f) => HARD_FACTOR_IDS.includes(f.factor_id))
    if (hard) {
      out.push({
        id: `${seg.segment_id}:hard`,
        segment_id: seg.segment_id,
        name,
        level: seg.level,
        stale: false,
        title: `事件 · ${hard.name}`,
        basis: '硬触发因素,判级直接上高档',
        status,
      })
    }
    if (seg.level >= 3) {
      out.push({
        id: `${seg.segment_id}:level`,
        segment_id: seg.segment_id,
        name,
        level: seg.level,
        stale: false,
        title: `${seg.level_name}(x = ${seg.x ?? '—'})`,
        basis: (seg.triggered_by ?? []).map((t) => TRIGGER_LABEL[t] ?? t).join('、') || '综合指标',
        status,
      })
    }
  }
  return out
})

const selectedId = ref<string | null>(null)
const selectedAlert = computed(() => alerts.value.find((a) => a.id === selectedId.value) ?? null)

// 首次观测时间:某条告警第一次出现在快照里时,记下当时的快照时间(仿真时钟;快照未到时留空)
watch(
  alerts,
  (list) => {
    const ts = snapshotTs.value
    if (!ts) return
    for (const a of list) {
      if (firstSeen[a.id] === undefined) firstSeen[a.id] = ts
    }
  },
  { immediate: true },
)

// ---------- 处置工作流(页面内存态,刷新复位) ----------
// 回执为演示态:一期没有真实下发通道(手册 §:2262 信号只生成建议、不下发信号机),页面已标注。
const dispatches = reactive<
  Record<string, { ack_id: string; at: string; pct: number; target: string; channel: string }>
>({})
const writebacks = reactive<
  { id: string; alertTitle: string; segment: string; owner: string; action: string; result: string; at: string }[]
>([])

const suggestion = computed<DiversionSuggestion | null>(() => {
  const a = selectedAlert.value
  if (!a) return null
  return DIVERSION_SUGGESTIONS[a.segment_id] ?? fallbackSuggestion(a.segment_id)
})

const dispatchPct = ref(30)
const dispatchChannel = ref<string>(DISPATCH_CHANNELS[0])
watch(selectedId, () => {
  dispatchPct.value = suggestion.value?.base_pct ?? 20
})

function dispatch(): void {
  const a = selectedAlert.value
  const s = suggestion.value
  if (!a || !s) return
  dispatches[a.id] = {
    ack_id: `ACK-${Date.now().toString(36).toUpperCase()}`,
    at: snapshotTs.value || new Date().toLocaleTimeString(),
    pct: dispatchPct.value,
    target: s.target_name,
    channel: dispatchChannel.value,
  }
  statusMap[a.segment_id] = 'processing'
}

const ACTIONS = ['现场疏导', '情报板诱导', '临时管制', '上报等待']
// 回写结果四选一照抄手册 §11.2(:1862):已消除 / 已缓解 / 未改善 / 误报
const RESULTS = ['已消除', '已缓解', '未改善', '误报'] as const
const wbOwner = ref('值班员 A')
const wbAction = ref(ACTIONS[1] ?? '情报板诱导')
const wbResult = ref<string>(RESULTS[1])

function submitWriteback(): void {
  const a = selectedAlert.value
  const d = a ? dispatches[a.id] : null
  if (!a || !d) return
  writebacks.unshift({
    id: `WB-${Date.now().toString(36).toUpperCase()}`,
    alertTitle: a.title,
    segment: a.name,
    owner: wbOwner.value,
    action: wbAction.value,
    result: wbResult.value,
    at: new Date().toLocaleTimeString(),
  })
  // 结果 → 告警状态(手册 §:1862 + 值守纪律 §:3333:未改善不得进已闭环,留在处置中)
  if (wbResult.value === '误报') statusMap[a.segment_id] = 'false_alarm'
  else if (wbResult.value === '未改善') statusMap[a.segment_id] = 'processing'
  else statusMap[a.segment_id] = 'closed'
}

// ---------- 因素与预测 + 人工置位(TC-16) ----------
const factorRows = computed(() =>
  segments.value
    .filter((s) => (s.factors_applied?.length ?? 0) > 0 || s.pred)
    .map((s) => ({ seg: s })),
)

const mfSegment = ref('SEG-001')
const mfPresetIdx = ref(0)
const mfMsg = ref('')

async function applyFactor(): Promise<void> {
  const preset = MANUAL_FACTOR_PRESETS[mfPresetIdx.value]
  if (!preset) return
  try {
    const r = await postTrafficFactor({
      segment_id: mfSegment.value,
      factor_id: preset.factor_id,
      name: preset.name,
      target: preset.target,
      multiplier: preset.multiplier,
    })
    mfMsg.value = `已置位 → ${segName(r.segment_id)} 判级变为「${r.level_name}」(mock 生效,60 分钟后自动过期)`
    void refresh()
  } catch {
    mfMsg.value = '置位失败(mock 未起?)'
  }
}

async function resetFactors(): Promise<void> {
  try {
    await postTrafficFactorReset()
    mfMsg.value = '已清空全部人工置位'
    void refresh()
  } catch {
    mfMsg.value = '复位失败(mock 未起?)'
  }
}

// ---------- 数据同化状态 ----------
const assim = ref<AssimilationSnapshot | null>(null)

async function loadAssim(): Promise<void> {
  try {
    assim.value = await getTrafficAssimilation()
  } catch {
    assim.value = null // 显式空态:接口未起
  }
}

const GATE_LABEL: Record<string, string> = {
  confidence_low: '置信度不足',
  data_age: '数据过旧',
  deviation_fuse: '偏差超标熔断',
}

// ---------- 效果对比(TC-14/TC-17 仿真对照演示;手册 §11.2 三组对比) ----------
// 三组 = ① 不推荐(对照组) ② "此刻最快"推荐(普通导航) ③ 协同推荐(本项目:时段预约 + 不伤害前车)。
// ②③ 的差就是本项目核心机制的举证口——"不给每个人此刻最快的那条路"。
const scenarioKey = ref(EFFECT_SCENARIOS[0]?.key ?? 'peak')
const scenario = computed(() => EFFECT_SCENARIOS.find((s) => s.key === scenarioKey.value) ?? EFFECT_SCENARIOS[0]!)

function barPct(v: number, max: number): string {
  return `${Math.round((v / Math.max(max, 0.0001)) * 100)}%`
}

/** 相对变化;基准为 0 时显示绝对值差,避免出现 ∞ 或 -100% 的假象 */
function deltaText(from: number, to: number): string {
  if (Math.abs(from) < 0.0001) {
    const abs = to - from
    return `${abs >= 0 ? '+' : ''}${Number(abs.toFixed(2))}`
  }
  const d = ((to - from) / Math.abs(from)) * 100
  return `${d >= 0 ? '+' : ''}${d.toFixed(1)}%`
}

function isGood(m: EffectMetric, value: number, ref0: number): boolean {
  return m.better === 'up' ? value >= ref0 : value <= ref0
}

/** 一行指标的三个取值与条宽基准 */
function rowMax(m: EffectMetric): number {
  return Math.max(m.no_guide, m.fastest, m.cooperative, 0.0001)
}

onMounted(() => {
  void refresh()
  void loadAssim()
  unsubscribe = subscribeTrafficSnapshot(
    () => {
      void refresh()
      void loadAssim()
    },
    (connected) => {
      live.value = connected
    },
  )
})

onUnmounted(() => {
  unsubscribe?.()
})
</script>

<template>
  <div class="dec-page">
    <header class="bar">
      <div class="bar-left">
        <span class="logo">◈</span>
        <span class="app-name">决策层 · 决策工作台</span>
        <span class="badge svc">决策演示</span>
      </div>
      <div class="bar-mid">
        <span class="badge sim">演示数据(模拟)· is_simulated = true · 工作流状态刷新复位</span>
      </div>
      <div class="bar-right">
        <span class="conn" :class="live ? 'up' : 'down'">
          <i class="dot" />
          {{ live ? '快照流已连接' : '快照流未连接' }}
        </span>
        <RouterLink class="nav-link" to="/heat">拥挤度热力 ›</RouterLink>
        <RouterLink class="nav-link" to="/perception">感知层 ›</RouterLink>
        <RouterLink class="nav-link" to="/dashboard">态势大屏 ›</RouterLink>
      </div>
    </header>

    <div class="main">
      <div class="col">
        <section class="panel">
          <div class="panel-head">事件告警列表(从契约快照派生 · 快照时间 {{ snapshotTs || '—' }})</div>
          <div class="alert-list">
            <button
              v-for="a in alerts"
              :key="a.id"
              type="button"
              class="alert"
              :class="{ on: a.id === selectedId }"
              @click="selectedId = a.id"
            >
              <LevelBadge :level="a.level" :stale="a.stale" />
              <span class="al-mid">
                <span class="al-title">
                  {{ a.name }} · {{ a.title }}
                  <i class="status" :class="a.status">{{ STATUS_LABEL[a.status] }}</i>
                </span>
                <span class="al-basis">{{ a.basis }}</span>
                <span class="al-time">时间(首次观测) {{ firstSeen[a.id] ?? '—' }}</span>
              </span>
            </button>
            <p v-if="alerts.length === 0" class="empty">当前快照无 ≥3 级路段、无硬触发事件</p>
          </div>
        </section>

        <section class="panel flow-panel">
          <div class="panel-head">处置工作流(系统建议 → 人工编辑 → 下发回执 → 处置回写)</div>
          <template v-if="selectedAlert && suggestion">
            <div class="flow-block">
              <div class="flow-title">针对告警:{{ selectedAlert.name }} · {{ selectedAlert.title }}</div>
              <p class="sug-why">{{ suggestion.why }}</p>
              <div class="sug-row">
                <span class="sug-item">
                  承接路段:<b>{{ suggestion.target_name }}</b>({{ suggestion.target_segment_id }})
                </span>
                <span class="sug-item">
                  分流比例:<b>{{ dispatchPct }}%</b>
                  <input
                    v-model.number="dispatchPct"
                    class="pct"
                    type="range"
                    :min="suggestion.min_pct"
                    :max="suggestion.max_pct"
                    step="5"
                  />
                  <span class="dim">范围 {{ suggestion.min_pct }}~{{ suggestion.max_pct }}%</span>
                </span>
                <span class="sug-item">
                  下发渠道:
                  <select v-model="dispatchChannel" class="wb-input ch">
                    <option v-for="c in DISPATCH_CHANNELS" :key="c">{{ c }}</option>
                  </select>
                </span>
                <span class="sug-item dim">预期:{{ suggestion.expect }}</span>
              </div>
              <button class="act primary" type="button" :disabled="dispatches[selectedAlert.id] != null" @click="dispatch">
                {{ dispatches[selectedAlert.id] ? '已下发' : '下发分流指令' }}
              </button>
            </div>

            <div v-if="dispatches[selectedAlert.id]" class="flow-block ack">
              <div class="flow-title">下发回执</div>
              <p class="mono">
                {{ dispatches[selectedAlert.id]!.ack_id }} · {{ dispatches[selectedAlert.id]!.at }} ·
                渠道 {{ dispatches[selectedAlert.id]!.channel }} ·
                向{{ dispatches[selectedAlert.id]!.target }}分流 {{ dispatches[selectedAlert.id]!.pct }}% ·
                is_simulated = true
              </p>
              <p class="dim">
                演示回执(页面内存态,刷新复位)· 一期无真实下发通道,未下发到信号机
              </p>
            </div>

            <div v-if="dispatches[selectedAlert.id]" class="flow-block">
              <div class="flow-title">处置回写</div>
              <div class="wb-form">
                <label>认领人<input v-model="wbOwner" class="wb-input" type="text" /></label>
                <label>动作<select v-model="wbAction" class="wb-input"><option v-for="x in ACTIONS" :key="x">{{ x }}</option></select></label>
                <label>结果<select v-model="wbResult" class="wb-input"><option v-for="x in RESULTS" :key="x">{{ x }}</option></select></label>
                <button class="act" type="button" @click="submitWriteback">提交回写</button>
              </div>
            </div>
          </template>
          <p v-else class="empty">← 在上方选择一条告警开始处置流程</p>

          <div v-if="writebacks.length > 0" class="wb-records">
            <div class="flow-title">回写记录({{ writebacks.length }})</div>
            <div v-for="w in writebacks" :key="w.id" class="wb-row mono">
              {{ w.at }} · {{ w.segment }}[{{ w.alertTitle }}] · {{ w.owner }} · {{ w.action }} · 结果:{{ w.result }} · {{ w.id }}
            </div>
          </div>
        </section>
      </div>

      <aside class="col">
        <section class="panel">
          <div class="panel-head">因素与预测展示(TC-16 口径)</div>
          <div class="factor-list">
            <div v-for="row in factorRows" :key="row.seg.segment_id" class="factor">
              <div class="f-head">
                <b>{{ segName(row.seg.segment_id) }}</b>
                <span class="dim">{{ row.seg.segment_id }} · {{ row.seg.level_name }}</span>
              </div>
              <div class="f-chips">
                <span
                  v-for="f in row.seg.factors_applied ?? []"
                  :key="f.factor_id"
                  class="chip"
                  :class="{ manual: f.name.includes('人工') }"
                  :title="`${f.target} ×${f.multiplier} · 至 ${f.until}`"
                >
                  {{ f.factor_id }} {{ f.name }} ×{{ f.multiplier }}
                </span>
                <span v-if="(row.seg.factors_applied?.length ?? 0) === 0" class="dim">无生效因素</span>
              </div>
              <div v-if="row.seg.pred" class="f-pred">
                预测(L0,无精度数字):15 分钟 → {{ row.seg.pred.h15.q_vph }} vph / {{ row.seg.pred.h15.level }} 级 ·
                30 分钟 → {{ row.seg.pred.h30.q_vph }} vph / {{ row.seg.pred.h30.level }} 级
              </div>
            </div>
            <p v-if="factorRows.length === 0" class="empty">快照为空(接口层未起?)</p>
          </div>
          <div class="mf-form">
            <div class="flow-title">人工置位(管理端口子 · mock 侧生效)</div>
            <div class="mf-row">
              <select v-model="mfSegment" class="wb-input">
                <option v-for="s in segments" :key="s.segment_id" :value="s.segment_id" :disabled="isStale(s)">
                  {{ segName(s.segment_id) }}{{ isStale(s) ? '(数据不可用)' : '' }}
                </option>
              </select>
              <select v-model.number="mfPresetIdx" class="wb-input">
                <option v-for="(p, i) in MANUAL_FACTOR_PRESETS" :key="p.factor_id" :value="i">
                  {{ p.name }}({{ p.note }})
                </option>
              </select>
              <button class="act" type="button" @click="applyFactor">置位</button>
              <button class="act ghost" type="button" @click="resetFactors">复位</button>
            </div>
            <p v-if="mfMsg" class="mf-msg">{{ mfMsg }}</p>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">数据同化状态(边界断面回灌 · 门控)</div>
          <template v-if="assim">
            <div class="asm-meta mono">
              门控:置信度 ≥ {{ assim.gate.confidence_min }} · 数据年龄 ≤ {{ assim.gate.data_age_max_s }}s · ts {{ assim.ts }}
            </div>
            <div v-for="r in assim.records" :key="r.point_id" class="asm-row">
              <span class="asm-state" :class="r.enabled ? 'on' : 'off'">{{ r.enabled ? '回灌中' : '已停灌' }}</span>
              <span class="asm-mid">
                <span class="al-title">{{ r.point_id }} → {{ segName(r.segment_id) }}</span>
                <span class="al-basis">
                  {{ r.enabled ? `流量偏差 ${r.flow_dev_pct}% · 车速偏差 ${r.speed_dev_pct}%` : (r.gate_detail ?? GATE_LABEL[r.gate_reason ?? ''] ?? '—') }}
                </span>
              </span>
            </div>
          </template>
          <p v-else class="empty">同化状态不可用(接口层未起?)</p>
        </section>

        <section class="panel">
          <div class="panel-head">阈值配置(P1 · 只读演示)</div>
          <div class="th-row th-head">
            <span>指标</span><span>1 级</span><span>2 级</span><span>3 级</span><span>4 级</span>
          </div>
          <div v-for="t in LEVEL_THRESHOLDS" :key="t.metric" class="th-row">
            <span>{{ t.metric }}{{ t.unit && `(${t.unit})` }}</span>
            <span v-for="(b, i) in t.bands" :key="i">≤ {{ b.max >= 999 ? '—' : b.max }}</span>
          </div>
          <div class="th-log">
            <div v-for="(c, i) in THRESHOLD_CHANGELOG" :key="i" class="mono dim">留痕:{{ c.time }} · {{ c.operator }} · {{ c.change }}</div>
          </div>
        </section>
      </aside>
    </div>

    <section class="panel cmp-panel">
      <div class="panel-head">
        效果对比报表(TC-14/TC-17 · 仿真对照演示)
        <select v-model="scenarioKey" class="wb-input sc">
          <option v-for="s in EFFECT_SCENARIOS" :key="s.key" :value="s.key">{{ s.name }}</option>
        </select>
      </div>
      <div class="cmp-window dim">
        时间窗:{{ scenario?.window }} · 来源:仿真对照(同一随机种子三跑,只切推荐口径)· is_simulated = true
      </div>
      <div class="cmp-grid">
        <div v-for="m in scenario?.metrics ?? []" :key="m.name" class="cmp-row">
          <span class="cmp-name">{{ m.name }}{{ m.unit && `(${m.unit})` }}</span>
          <div class="cmp-bars">
            <div class="cmp-track">
              <span class="cmp-fill base" :style="{ width: barPct(m.no_guide, rowMax(m)) }" />
              <span class="cmp-val">{{ m.no_guide }}</span>
            </div>
            <div class="cmp-track">
              <span class="cmp-fill fastest" :style="{ width: barPct(m.fastest, rowMax(m)) }" />
              <span class="cmp-val">{{ m.fastest }}</span>
            </div>
            <div class="cmp-track">
              <span class="cmp-fill guided" :style="{ width: barPct(m.cooperative, rowMax(m)) }" />
              <span class="cmp-val">{{ m.cooperative }}</span>
            </div>
          </div>
          <span class="cmp-delta" :class="isGood(m, m.cooperative, m.fastest) ? 'good' : 'bad'">
            ③vs② {{ deltaText(m.fastest, m.cooperative) }}
          </span>
          <span class="cmp-delta" :class="isGood(m, m.cooperative, m.no_guide) ? 'good' : 'bad'">
            ③vs① {{ deltaText(m.no_guide, m.cooperative) }}
          </span>
        </div>
      </div>
      <div class="cmp-legend dim">
        灰条 = ① 不推荐(对照组)· 琥珀条 = ② "此刻最快"推荐(普通导航口径)· 绿条 = ③ 协同推荐(本项目:时段预约 + 不伤害前车)·
        数值为仿真对照演示数据,非实测;同输入跑三遍只切推荐口径。
      </div>
      <div class="cmp-counts dim">
        评测协议四计数(分工表 §8.4):inserted {{ scenario?.counts.inserted }} · removed {{ scenario?.counts.removed }} ·
        not_entered {{ scenario?.counts.not_entered }} · completed {{ scenario?.counts.completed }}
      </div>

      <div class="panel-head sub">
        处置前后对比(手册 §11.2:排队长度峰值 / 拥堵持续时间 / 饱和度和差)
      </div>
      <div class="cmp-window dim">时间窗:{{ ACK_COMPARISON.window }} · 来源:仿真对照 · is_simulated = true</div>
      <div class="cmp-grid">
        <div v-for="r in ACK_COMPARISON.rows" :key="r.name" class="cmp-row">
          <span class="cmp-name">{{ r.name }}{{ r.unit && `(${r.unit})` }}</span>
          <div class="cmp-bars">
            <div class="cmp-track">
              <span class="cmp-fill base" :style="{ width: barPct(r.before, Math.max(r.before, r.after, 0.0001)) }" />
              <span class="cmp-val">{{ r.before }}</span>
            </div>
            <div class="cmp-track">
              <span class="cmp-fill guided" :style="{ width: barPct(r.after, Math.max(r.before, r.after, 0.0001)) }" />
              <span class="cmp-val">{{ r.after }}</span>
            </div>
          </div>
          <span class="cmp-delta" :class="r.better === 'up' ? (r.after >= r.before ? 'good' : 'bad') : r.after <= r.before ? 'good' : 'bad'">
            {{ deltaText(r.before, r.after) }}
          </span>
        </div>
      </div>
    </section>

    <footer class="foot">
      <span>快照时间 {{ snapshotTs || '—' }}</span>
      <span>数据来源:契约 v2.0 mock 快照 + 决策工作台演示数据 · is_simulated 恒 true · 四级编码见手册 §6.2</span>
      <span>效果对比属仿真对照,不得称实测 · 预测只展示 L0 接口通,无精度数字 · 工作流为演示态(刷新复位)</span>
    </footer>
  </div>
</template>

<style scoped>
.dec-page {
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
  color: #7fe7ff;
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
.nav-link {
  font-size: 13px;
  color: #37d6ff;
  text-decoration: none;
  border: 1px solid #1d3354;
  border-radius: 6px;
  padding: 4px 10px;
}
.nav-link:hover {
  border-color: #2c4a78;
  background: rgba(55, 214, 255, 0.08);
}
.main {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(360px, 1fr);
  gap: 14px;
}
.col {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
}
/* 右栏三块面板内容天然超高:栏内自滚动,面板保持内容高度不再互相叠压 */
.main > aside.col {
  overflow-y: auto;
  padding-right: 2px;
}
.main > aside.col .panel {
  flex: 0 0 auto;
}
.panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 14px;
  border: 1px solid #1d3354;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(16, 32, 58, 0.75), rgba(11, 23, 43, 0.85));
  gap: 8px;
}
.panel-head {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 2px;
  color: #9fb6d9;
  padding-left: 8px;
  border-left: 3px solid #37d6ff;
  line-height: 1.2;
}
.flow-panel {
  flex: 1;
}
.alert-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
  min-height: 0;
}
.alert {
  display: flex;
  align-items: center;
  gap: 10px;
  text-align: left;
  padding: 9px 10px;
  background: rgba(20, 38, 66, 0.55);
  border: 1px solid #1d3354;
  border-radius: 8px;
  color: #cfe0f5;
  cursor: pointer;
}
.alert:hover {
  border-color: #2c4a78;
}
.alert.on {
  border-color: #37d6ff;
  background: rgba(55, 214, 255, 0.08);
}
.al-mid {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.al-title {
  font-size: 13px;
  color: #e6eefc;
}
.al-basis {
  font-size: 11px;
  color: #7c93b5;
}
.al-time {
  font-size: 11px;
  color: #5f7396;
  font-variant-numeric: tabular-nums;
}
.status {
  margin-left: 8px;
  font-size: 10px;
  font-style: normal;
  padding: 1px 7px;
  border-radius: 4px;
  border: 1px solid;
}
/* 告警状态四态照抄手册 §11.2(:1860):待认领 / 处置中 / 已闭环 / 误报 */
.status.unclaimed {
  color: #ffd479;
  border-color: #8a6d1f;
}
.status.processing {
  color: #37d6ff;
  border-color: #2a7f9e;
}
.status.closed {
  color: #35d08c;
  border-color: #1f7a54;
}
.status.false_alarm {
  color: #9fb6d9;
  border-color: #3c4d6b;
}
.flow-block {
  padding: 10px 12px;
  background: rgba(20, 38, 66, 0.55);
  border: 1px solid #1d3354;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.flow-block.ack {
  border-color: #2a7f9e;
}
.flow-title {
  font-size: 12px;
  font-weight: 600;
  color: #9fb6d9;
}
.sug-why {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: #cfe0f5;
}
.sug-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sug-item {
  font-size: 12px;
  color: #cfe0f5;
}
.sug-item b {
  color: #37d6ff;
}
.pct {
  width: 140px;
  vertical-align: middle;
  accent-color: #37d6ff;
}
.dim {
  color: #7c93b5;
  font-size: 11px;
}
.mono {
  font-family: Consolas, Menlo, monospace;
  font-size: 11px;
  color: #7fe7ff;
}
.act {
  align-self: flex-start;
  border: 1px solid #2a7f9e;
  color: #07101e;
  background: #37d6ff;
  border-radius: 6px;
  padding: 6px 16px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
}
.act:disabled {
  opacity: 0.55;
  cursor: default;
}
.act.ghost {
  background: transparent;
  color: #37d6ff;
  font-weight: 400;
}
.wb-form {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.wb-form label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #9fb6d9;
}
.wb-input {
  background: rgba(8, 18, 34, 0.8);
  border: 1px solid #1d3354;
  border-radius: 6px;
  color: #cfe0f5;
  padding: 5px 8px;
  font-size: 12px;
}
.wb-records {
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
  min-height: 0;
}
.wb-row {
  padding: 5px 8px;
  background: rgba(20, 38, 66, 0.4);
  border-radius: 6px;
  color: #7c93b5;
}
.factor-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  min-height: 0;
}
.factor {
  padding: 8px 10px;
  background: rgba(20, 38, 66, 0.55);
  border: 1px solid #1d3354;
  border-radius: 8px;
}
.f-head {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  margin-bottom: 5px;
}
.f-head b {
  color: #e6eefc;
}
.f-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.chip {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid #8a6d1f;
  color: #ffd479;
  background: rgba(255, 212, 121, 0.08);
}
.chip.manual {
  border-color: #2a7f9e;
  color: #7fe7ff;
  background: rgba(55, 214, 255, 0.08);
}
.f-pred {
  margin-top: 5px;
  font-size: 11px;
  color: #7c93b5;
}
.mf-form {
  border-top: 1px dashed #1d3354;
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.mf-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.mf-row .wb-input {
  flex: 1;
  min-width: 0;
}
.mf-msg {
  margin: 0;
  font-size: 11px;
  color: #7fe7ff;
}
.asm-meta {
  font-size: 11px;
  color: #5f7396;
}
.asm-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 10px;
  background: rgba(20, 38, 66, 0.55);
  border: 1px solid #1d3354;
  border-radius: 8px;
}
.asm-state {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid;
  white-space: nowrap;
}
.asm-state.on {
  color: #35d08c;
  border-color: #1f7a54;
}
.asm-state.off {
  color: #8c8c8c;
  border-color: #4a5568;
}
.asm-mid {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.th-row {
  display: grid;
  grid-template-columns: 1.4fr repeat(4, 1fr);
  gap: 6px;
  font-size: 12px;
  padding: 4px 2px;
  border-bottom: 1px dashed rgba(29, 51, 84, 0.6);
}
.th-head {
  color: #9fb6d9;
  font-weight: 600;
}
.th-log {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-top: 6px;
}
.cmp-panel {
  flex: 0 0 auto;
}
.cmp-panel .panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.wb-input.sc {
  color: #cfe0f5;
}
.cmp-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 24px;
}
.cmp-row {
  display: grid;
  grid-template-columns: 130px 1fr 74px 74px;
  align-items: center;
  gap: 10px;
}
.cmp-name {
  font-size: 12px;
  color: #cfe0f5;
}
.cmp-bars {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.cmp-track {
  position: relative;
  height: 9px;
  border-radius: 5px;
  background: rgba(8, 18, 34, 0.8);
  overflow: hidden;
}
.cmp-fill {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: 5px;
}
.cmp-fill.base {
  background: #5f7396;
}
/* ② "此刻最快"推荐(普通导航口径):琥珀色,与①灰、③绿三分 */
.cmp-fill.fastest {
  background: #f2b705;
}
.cmp-fill.guided {
  background: #35d08c;
}
.cmp-val {
  position: absolute;
  right: 6px;
  top: -3px;
  font-size: 10px;
  color: #e6eefc;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.8);
}
.cmp-delta {
  font-size: 12px;
  font-weight: 700;
  text-align: right;
}
.cmp-delta.good {
  color: #35d08c;
}
.cmp-delta.bad {
  color: #e0564f;
}
.cmp-legend {
  font-size: 11px;
}
.cmp-window,
.cmp-counts {
  font-size: 11px;
  margin-top: 6px;
}
.panel-head.sub {
  margin-top: 14px;
}
.wb-input.ch {
  width: 130px;
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
  .dec-page {
    overflow-y: auto;
    height: auto;
  }
  .main,
  .cmp-grid {
    grid-template-columns: 1fr;
  }
}
</style>
