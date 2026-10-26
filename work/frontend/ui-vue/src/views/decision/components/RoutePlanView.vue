<script setup lang="ts">
// 决策层 · 路线规划视图（Issue IKP5CE）。
//
// 队长裁定走方案 A（保守）：本页只在**已有引擎产物**范围内做对比——
// 同一 OD 的推荐 vs 备选、不同 session、不同站点包；不触发任何算路。
// 场景注入 / 人工置位 / 告警下发都不会让路线变化，页面必须把这句话说清楚
// （见「路线是否随参数变化」卡），不得把回放讲成规划，更不得在前端编路线或改 ETA。
//
// 数据来源：
//   · GET  /api/traffic/route/options  —— 只读辅助端点（非契约 §七），端出引擎产物的
//     OD / session 摘要；mock 模式没有该端点（404），页面跳过请求并如实标注，不刷 404。
//   · POST /api/traffic/route/recommend —— 选中 session 后取完整推荐（arrival / alternatives /
//     departure）；段号与 eta_min 原样透传，本页只做「差值 = 两次产物 ETA 相减」的展示。
//
// 数据源口径：接口层真网产物优先、样例产物回退（engine.routes.real / engine.routes.sample）；
// mock 侧回退站点包演示骨架。路线一律标「演示数据（模拟）」，沿用现有对外口径纪律。
import { computed, onMounted, ref } from 'vue'
import { getTrafficEmergency, getTrafficRouteOptions, postRouteRecommend } from '../../../api/traffic'
import { demoSegment } from '../../../shared/demoNetwork'
import { USE_MOCK } from '../../../shared/env'
import { activePack } from '../../../station-packs/index'
import type {
  EmergencyState,
  RecommendResult,
  RouteOption,
  RouteOptionsSnapshot,
  RoutePath,
} from '../../../shared/traffic'

interface ChainNode {
  key: string
  step: string
  title: string
  primary: string
  secondary: string
  tag: string
  note: string
  empty: boolean
}

// ---------- 引擎产物选项（GET /route/options） ----------
const options = ref<RouteOption[]>([])
const optionsMeta = ref<RouteOptionsSnapshot | null>(null)
const optionsLoading = ref(false)
/** 空 = 正常；非空 = 辅助端点缺失 / 产物缺失，页面已回退演示会话（如实展示） */
const optionsError = ref('')

/**
 * 应急态（TC-10，手册 §11.1(3)）：应急时**停下路线引导**，替换为「请服从现场指挥」。
 *
 * 口径：只消费接口层派生的 `emergency`（`GET /api/traffic/emergency`），**不自己判级**；
 *      读不到 = 常态（不误停引导）；应急时只撤「路线规划」这一块的引导，
 *      页面其余部分（来源行、选择器说明等）不动。
 */
const emergency = ref<EmergencyState | null>(null)
const emergencyActive = computed(() => emergency.value?.active === true)
const emergencySegmentText = computed(() => {
  const ids = emergency.value?.segment_ids ?? []
  if (ids.length === 0) return ''
  const head = ids.slice(0, 3).join('、')
  return ids.length > 3 ? `${head} 等 ${ids.length} 段` : head
})

// ---------- 当前 session 的完整路线（POST /route/recommend） ----------
const mainSession = ref('')
const main = ref<RecommendResult | null>(null)
const mainLoading = ref(false)
const mainError = ref('')
let mainSeq = 0

// ---------- 两个 session 的产物内对比 ----------
const leftSession = ref('')
const rightSession = ref('')
const left = ref<RecommendResult | null>(null)
const right = ref<RecommendResult | null>(null)
const leftLoading = ref(false)
const rightLoading = ref(false)
const leftError = ref('')
const rightError = ref('')
let leftSeq = 0
let rightSeq = 0
const canCompare = computed<boolean>(() => options.value.length >= 2)

// ---------- 产物回放复核（同一 session 重新读取一次，不解算） ----------
const recheckState = ref<'idle' | 'running' | 'same' | 'diff'>('idle')
const recheckText = ref('')

function fmtEta(value: number | null | undefined): string {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(2) : '—'
}

function deltaValue(base: number | null | undefined, value: number | null | undefined): number | null {
  if (
    typeof base !== 'number' ||
    typeof value !== 'number' ||
    !Number.isFinite(base) ||
    !Number.isFinite(value)
  ) {
    return null
  }
  return value - base
}

function deltaText(base: number | null | undefined, value: number | null | undefined): string {
  const d = deltaValue(base, value)
  if (d === null) return '—'
  return `${d > 0 ? '+' : ''}${d.toFixed(2)} min`
}

function sameSegments(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((id, index) => id === b[index])
}

function segmentName(id: string | null | undefined): string {
  if (!id) return '—'
  return demoSegment(id)?.name ?? '站点包未收录该段'
}

function dropoffName(id: string | null | undefined): string {
  if (!id) return ''
  return activePack().dropoffs.find((item) => item.id === id)?.name ?? '站点包未收录该落客点'
}

/** 契约里 arrival_route 必填，但引擎在「无可行路径」时按 no_alternative 例外写 null；页面按空窗处理。 */
function arrivalOf(record: RecommendResult | null): RoutePath | null {
  return record ? ((record.arrival_route as RoutePath | null) ?? null) : null
}

function optionLabel(option: RouteOption): string {
  const od = option.od_id ?? 'OD—'
  const alternatives = option.alternatives?.length ?? 0
  return `${od} · ${option.session_id ?? '—'} · 到达 ${fmtEta(option.arrival_route?.eta_min)} min · 备选 ${alternatives} 条`
}

/**
 * 链路条四段：起点 → 场区/落客点 → 终点（到达末段）→ 离站方向。
 * 落客点缺失时只如实写"引擎产物未给落客点"并用末段段号/路段名兜底，
 * 不把末段冒充成落客点（契约里 dropoff_point 为 null 就是 null）。
 */
function chainNodes(record: RecommendResult | null): ChainNode[] {
  if (!record) return []
  const arrival = arrivalOf(record)
  const arrivalSegments = arrival?.segments ?? []
  const lastSegment = arrivalSegments[arrivalSegments.length - 1]
  const dropoff = arrival?.dropoff_point && arrival.dropoff_point.trim() ? arrival.dropoff_point : null
  const departure = record.departure_route
  const departureSegments = departure?.segments ?? []
  const startSegment = record.location?.segment_id ?? ''

  return [
    {
      key: 'start',
      step: '①',
      title: '起点',
      primary: startSegment || '引擎产物未给起点段',
      secondary: startSegment ? segmentName(startSegment) : 'location.segment_id 为空',
      tag: record.location?.source ?? 'source 缺省',
      note: '定位来源（location.source）',
      empty: !startSegment,
    },
    {
      key: 'dropoff',
      step: '②',
      title: '场区 / 落客点',
      primary: dropoff ?? '引擎产物未给落客点',
      secondary: dropoff
        ? dropoffName(dropoff)
        : lastSegment
          ? `末段兜底：${lastSegment} · ${segmentName(lastSegment)}（仅作位置参照）`
          : '到达段为空，无末段可兜底',
      tag: dropoff ? 'dropoff_point' : 'null',
      note: dropoff ? 'arrival_route.dropoff_point' : '如实空窗 · 不补造落客点',
      empty: !dropoff,
    },
    {
      key: 'end',
      step: '③',
      title: '终点（到达末段）',
      primary: lastSegment ?? '引擎产物未给终点段',
      secondary: lastSegment ? segmentName(lastSegment) : 'arrival_route 为空',
      tag: arrivalSegments.length ? `${arrivalSegments.length} 段` : '—',
      note: lastSegment ? '推荐路线最后一段' : '不补造终点',
      empty: !lastSegment,
    },
    {
      key: 'departure',
      step: '④',
      title: '离站方向',
      primary: departure ? departure.path_id || '离站路线' : '引擎产物未给离站路线',
      secondary: departure
        ? `${departureSegments.length} 段 · ETA ${fmtEta(departure.eta_min)} min`
        : 'departure_route = null',
      tag: departure ? 'departure_route' : 'null',
      note:
        departure && departureSegments.length
          ? `首段 ${departureSegments[0]} → 末段 ${departureSegments[departureSegments.length - 1]}`
          : departure
            ? '离站段为空'
            : '如实空窗 · 不补造离站路线',
      empty: !departure,
    },
  ]
}

const mainChain = computed<ChainNode[]>(() => chainNodes(main.value))
const leftChain = computed<ChainNode[]>(() => chainNodes(left.value))
const rightChain = computed<ChainNode[]>(() => chainNodes(right.value))
const arrivalSegments = computed<string[]>(() => arrivalOf(main.value)?.segments ?? [])
const alternatives = computed(() => main.value?.alternatives ?? [])
const mainArrival = computed<RoutePath | null>(() => arrivalOf(main.value))

/** 备选不足 / no_alternative 的如实说明（不凑数）。 */
const alternativeNotice = computed<string>(() => {
  const record = main.value
  if (!record) return ''
  if (record.no_alternative === true) {
    const reason = record.no_alternative_reason?.trim()
    return `引擎标记 no_alternative = true：${reason || '产物未给 no_alternative_reason'}（本 OD 备选 ${alternatives.value.length} 条，按产物如实展示，不凑数）`
  }
  if (alternatives.value.length < 2) {
    return `本 OD 仅 ${alternatives.value.length} 条候选（契约要求 ≥2 条备选）`
  }
  return ''
})

const mainSourceLabel = computed<string>(() => {
  const record = main.value
  if (!record) return '—'
  if (record.data_source === 'engine.routes.real') return '真网算路产物 engine.routes.real'
  if (record.data_source === 'engine.routes.sample') return '样例产物 engine.routes.sample（非本站真网）'
  if (USE_MOCK) return 'mock 站点包演示骨架（非引擎产物）'
  return record.data_source || '接口未标来源'
})

const mainSourceNote = computed<string>(() => main.value?.data_source_note ?? '')

/** session 未匹配 / mock 侧不按 session 区分时，必须显式说明，不伪装成该车行程。 */
const sessionWarning = computed<string>(() => {
  const record = main.value
  if (!record) return ''
  if (record.session_matched === false) {
    return `请求的 session_id（${record.requested_session_id ?? mainSession.value}）不在引擎产物里：当前端出的是产物首条请求作为演示路线，非该车行程；页面不伪装成匹配结果。`
  }
  if (USE_MOCK) {
    return 'mock 侧按站点包演示骨架返回，不按 session 区分（响应里的 session 号由 mock 生成）；这是演示路线，不是引擎算路产物。'
  }
  return ''
})

const optionsHint = computed<string>(() => {
  if (USE_MOCK) {
    return 'mock 模式无 GET /api/traffic/route/options 辅助端点（404）：本页跳过该请求，回退演示会话路线；不冒充引擎 OD / session 列表。'
  }
  if (optionsError.value) {
    return `路线选项不可用：${optionsError.value}。已回退演示会话路线；不编造 OD / session。`
  }
  if (optionsMeta.value && options.value.length === 0) {
    return '引擎产物没有可用 OD / session：不编造路线选择。'
  }
  return ''
})

async function fetchRecommendation(session: string): Promise<RecommendResult> {
  const pack = activePack()
  const option = options.value.find((item) => item.session_id === session) ?? null
  return postRouteRecommend({
    session_id: session,
    location: {
      // 有引擎选项时用该 OD 的起点；没有（mock / 回退）沿用站点包演示锚点，与请求形状一致
      segment_id: option?.location.segment_id ?? pack.recommend.location_segment_id,
      offset_m: option?.location.offset_m ?? pack.recommend.location_offset_m,
    },
  })
}

async function loadMain(): Promise<void> {
  const session = mainSession.value
  const seq = ++mainSeq
  if (!session) {
    main.value = null
    mainError.value = '未选择 session：不能读取路线。'
    return
  }
  mainLoading.value = true
  mainError.value = ''
  try {
    const record = await fetchRecommendation(session)
    if (seq !== mainSeq) return // 选择已变：丢弃过期响应
    main.value = record
    recheckState.value = 'idle'
    recheckText.value = ''
  } catch (e) {
    if (seq !== mainSeq) return
    main.value = null
    mainError.value = `推荐接口不可达：${e instanceof Error ? e.message : String(e)}。本页保持空窗，不编造演示路线。`
  } finally {
    if (seq === mainSeq) mainLoading.value = false
  }
}

/**
 * 左右两列各自独立发一次 POST /route/recommend：
 * 左列结果只写 left、右列只写 right，绝不复用同一份响应伪造"两个 session 的差异"。
 */
async function loadSide(side: 'left' | 'right'): Promise<void> {
  const isLeft = side === 'left'
  const session = isLeft ? leftSession.value : rightSession.value
  const target = isLeft ? left : right
  const loading = isLeft ? leftLoading : rightLoading
  const error = isLeft ? leftError : rightError
  const seq = isLeft ? ++leftSeq : ++rightSeq
  if (!session) {
    target.value = null
    error.value = ''
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  try {
    const record = await fetchRecommendation(session)
    if (seq !== (isLeft ? leftSeq : rightSeq)) return
    target.value = record
  } catch (e) {
    if (seq !== (isLeft ? leftSeq : rightSeq)) return
    target.value = null
    error.value = `读取失败：${e instanceof Error ? e.message : String(e)}`
  } finally {
    if (seq === (isLeft ? leftSeq : rightSeq)) loading.value = false
  }
}

/** 同 session 连续两次读取的差异；用于回答"产物是否变过"，不是重算。 */
function diffOfSameSession(before: RecommendResult, after: RecommendResult): string[] {
  const out: string[] = []
  const beforeArrival = arrivalOf(before)
  const afterArrival = arrivalOf(after)
  if ((beforeArrival === null) !== (afterArrival === null)) out.push('到达路线有无不同')
  if (beforeArrival && afterArrival) {
    if (!sameSegments(beforeArrival.segments, afterArrival.segments)) out.push('推荐段序列不同')
    if (beforeArrival.eta_min !== afterArrival.eta_min) {
      out.push(`到达 ETA ${fmtEta(beforeArrival.eta_min)} → ${fmtEta(afterArrival.eta_min)} min`)
    }
  }
  const beforeDeparture = before.departure_route
  const afterDeparture = after.departure_route
  if ((beforeDeparture === null) !== (afterDeparture === null)) {
    out.push('离站路线有无不同')
  } else if (beforeDeparture && afterDeparture) {
    if (
      beforeDeparture.path_id !== afterDeparture.path_id ||
      !sameSegments(beforeDeparture.segments, afterDeparture.segments) ||
      beforeDeparture.eta_min !== afterDeparture.eta_min
    ) {
      out.push('离站路线或 ETA 不同')
    }
  }
  if ((before.alternatives?.length ?? 0) !== (after.alternatives?.length ?? 0)) {
    out.push(`备选条数 ${before.alternatives?.length ?? 0} → ${after.alternatives?.length ?? 0}`)
  }
  return out
}

async function recheckSameSession(): Promise<void> {
  const before = main.value
  if (!before || !mainSession.value || recheckState.value === 'running') return
  recheckState.value = 'running'
  recheckText.value = ''
  try {
    const after = await fetchRecommendation(mainSession.value)
    const diffs = diffOfSameSession(before, after)
    if (diffs.length === 0) {
      recheckState.value = 'same'
      recheckText.value = '与上次读取一致：推荐 / 备选 / 离站段序列与 ETA 全部相同。'
    } else {
      recheckState.value = 'diff'
      recheckText.value = `与上次读取不同：${diffs.join('；')}。只可能来自产物文件更新；本页不自行重算。`
    }
  } catch (e) {
    recheckState.value = 'diff'
    recheckText.value = `重新读取失败：${e instanceof Error ? e.message : String(e)}`
  }
}

const compare = computed(() => {
  const a = left.value
  const b = right.value
  if (!a || !b) return null
  const beforeArrival = arrivalOf(a)
  const afterArrival = arrivalOf(b)
  const beforeDeparture = a.departure_route
  const afterDeparture = b.departure_route
  const sameSession = Boolean(leftSession.value) && leftSession.value === rightSession.value
  const arrivalSame =
    (beforeArrival === null) === (afterArrival === null) &&
    (beforeArrival?.path_id ?? '') === (afterArrival?.path_id ?? '') &&
    sameSegments(beforeArrival?.segments ?? [], afterArrival?.segments ?? [])
  const departureSame =
    (beforeDeparture === null) === (afterDeparture === null) &&
    (beforeDeparture?.path_id ?? '') === (afterDeparture?.path_id ?? '') &&
    sameSegments(beforeDeparture?.segments ?? [], afterDeparture?.segments ?? [])
  const etaDelta = deltaValue(beforeArrival?.eta_min, afterArrival?.eta_min)
  const departureEtaDelta = deltaValue(beforeDeparture?.eta_min, afterDeparture?.eta_min)
  const beforeAlternatives = a.alternatives?.length ?? 0
  const afterAlternatives = b.alternatives?.length ?? 0
  const changed =
    !sameSession &&
    (!arrivalSame ||
      !departureSame ||
      (etaDelta !== null && etaDelta !== 0) ||
      (departureEtaDelta !== null && departureEtaDelta !== 0) ||
      beforeAlternatives !== afterAlternatives)
  return {
    sameSession,
    arrivalSame,
    departureSame,
    etaDeltaText: deltaText(beforeArrival?.eta_min, afterArrival?.eta_min),
    departureEtaDeltaText: deltaText(beforeDeparture?.eta_min, afterDeparture?.eta_min),
    beforeAlternatives,
    afterAlternatives,
    changed,
  }
})

const compareSummary = computed<string>(() => {
  const result = compare.value
  if (!result) return ''
  if (result.sameSession) {
    return '两个选择器指向同一 session：不构成对比，请把其中一个换成别的 session。'
  }
  const parts = [
    result.arrivalSame ? '推荐段序列相同' : '推荐段序列不同',
    result.etaDeltaText !== '—' ? `到达 ETA 差 ${result.etaDeltaText}` : '到达 ETA 缺值',
    result.departureSame ? '离站路线相同' : '离站路线不同',
    result.beforeAlternatives === result.afterAlternatives
      ? `备选均 ${result.beforeAlternatives} 条`
      : `备选 ${result.beforeAlternatives} / ${result.afterAlternatives} 条`,
  ]
  if (!result.changed) {
    return `无差异：${parts.join('；')}。产物内这两条 session 指向同一条路线，页面如实显示「无变化」，不编造差异。`
  }
  return `有差异：${parts.join('；')}。差异来自两次 POST /api/traffic/route/recommend 的产物，不是前端改的。`
})

async function loadOptions(): Promise<void> {
  optionsLoading.value = true
  optionsError.value = ''
  optionsMeta.value = null
  options.value = []
  // mock 中间件未匹配路径一律 404：不打一条注定 404 的请求，直接按「mock 无该辅助端点」降级
  if (USE_MOCK) {
    optionsError.value = 'mock 模式无 /api/traffic/route/options 辅助端点（辅助端点仅真接口提供）'
    mainSession.value = `demo-${activePack().key}`
    optionsLoading.value = false
    await loadMain()
    return
  }
  try {
    const snapshot = await getTrafficRouteOptions()
    optionsMeta.value = snapshot
    options.value = (Array.isArray(snapshot.options) ? snapshot.options : []).filter((item) =>
      Boolean(item.session_id),
    )
    if (options.value.length > 0) {
      mainSession.value = options.value[0]?.session_id ?? ''
      leftSession.value = options.value[0]?.session_id ?? ''
      rightSession.value = options.value[1]?.session_id ?? ''
      await loadMain()
      if (leftSession.value) await loadSide('left')
      if (canCompare.value) await loadSide('right')
    } else {
      mainSession.value = `demo-${activePack().key}`
      await loadMain()
    }
  } catch (e) {
    optionsError.value = e instanceof Error ? e.message : String(e)
    mainSession.value = `demo-${activePack().key}`
    await loadMain()
  } finally {
    optionsLoading.value = false
  }
}

/**
 * 读应急态（只读派生结果，不参与算路）。
 *
 * 失败时保持 `null` = 按常态渲染：应急是**停下引导**的强动作，读不到就不能擅自停，
 * 也不能自己从路段等级里猜一个「大概是应急吧」。
 */
async function loadEmergency() {
  if (USE_MOCK) {
    emergency.value = null
    return
  }
  try {
    emergency.value = await getTrafficEmergency()
  } catch {
    emergency.value = null
  }
}

onMounted(() => {
  void loadOptions()
  void loadEmergency()
})
</script>

<template>
  <div class="route-view">
    <section class="td-card">
      <div class="td-card-head">
        路线规划 · 完整链路（起点 → 落客 → 终点 → 离站）
        <span class="td-chip on">读引擎算路产物，本页不重算</span>
        <span class="td-chip warn">演示数据（模拟）</span>
      </div>
      <div class="td-card-body">
        <p class="src">
          数据来源：<b>GET /api/traffic/route/options</b>（OD / session 摘要，只读辅助端点）
          <span class="sep">+</span>
          <b>POST /api/traffic/route/recommend</b>（完整路线 / ETA 原样透传）；
          本页不调用任何算路，也不改 ETA。
        </p>
        <p v-if="optionsLoading" class="src">正在读取引擎路线选项…</p>
        <p v-else-if="optionsHint" class="src warn">{{ optionsHint }}</p>
        <p v-if="optionsMeta" class="src">
          选项来源：{{ optionsMeta.data_source_note || optionsMeta.data_source }} · {{ options.length }} 条 ·
          段号命名空间 {{ (optionsMeta.segment_namespaces || []).join(' / ') || '—' }}
        </p>

        <div class="pick-row">
          <label class="pick-label" for="route-main-session">当前 session</label>
          <select
            id="route-main-session"
            v-model="mainSession"
            class="route-select"
            :disabled="optionsLoading || mainLoading || (options.length === 0 && !mainSession)"
            @change="loadMain"
          >
            <option
              v-for="option in options"
              :key="option.session_id || option.request_id || ''"
              :value="option.session_id || ''"
            >
              {{ optionLabel(option) }}
            </option>
            <option v-if="options.length === 0" :value="mainSession">
              {{ mainSession }}（回退演示会话 · 非引擎 OD）
            </option>
          </select>
          <button
            type="button"
            class="td-btn sm"
            :disabled="mainLoading || !mainSession"
            @click="loadMain"
          >
            重新读取
          </button>
        </div>

        <p v-if="mainLoading" class="src">正在读取推荐快照…</p>
        <!-- 应急态（TC-10，手册 §11.1(3)）：停下路线引导，替换为固定措辞。
             注意：只替「路线规划」这一块，页面其它内容（来源行、选择器、说明）一字不减。 -->
        <div v-else-if="emergencyActive" class="emergency-panel" role="alert">
          <div class="em-title">{{ emergency?.message ?? '请服从现场指挥' }}</div>
          <p class="em-line">
            应急状态下<b>停止路线引导</b>（优先级高于一切推荐），请以现场指挥为准；引导恢复前不再给出推荐路线与 ETA。
          </p>
          <p v-if="emergencySegmentText" class="em-line">
            影响路段：<b class="td-mono">{{ emergencySegmentText }}</b>
          </p>
          <p v-if="emergency?.level !== null && emergency?.level !== undefined" class="em-line">
            等级：<b>{{ emergency.level }} 级</b>（由感知层判定，本页不重算）
          </p>
          <p v-else-if="emergency?.level_source === 'pending_perception_recompute'" class="em-line">
            等级：<b>待重算</b> —— 事故/管制已登记，等感知层重算后才出等级；此处<b>不填任何档位</b>。
          </p>
          <p class="em-src">{{ emergency?.note ?? '' }}</p>
        </div>
        <p v-else-if="mainError" class="src err">{{ mainError }}</p>
        <template v-else-if="main">
          <div class="chain" aria-label="完整路线链路">
            <template v-for="(node, index) in mainChain" :key="node.key">
              <div class="chain-node" :class="{ empty: node.empty }">
                <div class="cn-step">{{ node.step }} {{ node.title }}</div>
                <div class="cn-primary">{{ node.primary }}</div>
                <div class="cn-secondary">{{ node.secondary }}</div>
                <div class="cn-tag td-mono">{{ node.tag }}</div>
                <div class="cn-note">{{ node.note }}</div>
              </div>
              <div v-if="index < mainChain.length - 1" class="chain-arrow" aria-hidden="true">→</div>
            </template>
          </div>

          <div class="route-meta">
            <span>推荐 <b class="td-mono">{{ mainArrival?.path_id ?? '—' }}</b></span>
            <span>{{ arrivalSegments.length }} 段</span>
            <span>到达 ETA <b class="td-num">{{ fmtEta(mainArrival?.eta_min) }} min</b></span>
            <span>离站 ETA <b class="td-num">{{ fmtEta(main.departure_route?.eta_min) }} min</b></span>
            <span>备选 <b>{{ alternatives.length }}</b> 条</span>
            <span>来源 <b>{{ mainSourceLabel }}</b></span>
          </div>
          <p v-if="mainSourceNote" class="src">来源说明：{{ mainSourceNote }}</p>
          <p v-if="sessionWarning" class="src warn">{{ sessionWarning }}</p>
          <p v-if="(main.segments_not_in_snapshot?.length ?? 0) > 0" class="src warn">
            路线引用的 {{ main.segments_not_in_snapshot?.length }} 段不在当前路段快照里（{{
              (main.segments_not_in_snapshot || []).join('、')
            }}）：页面只按站点包显示段名，不并入指标、不混算。
          </p>

          <div class="sub-head">推荐路线 · 段序列</div>
          <div class="seg-trail">
            <template v-for="(segmentId, index) in arrivalSegments" :key="`${segmentId}-${index}`">
              <span class="seg-chip">
                <b class="td-mono">{{ segmentId }}</b>
                <span>{{ segmentName(segmentId) }}</span>
              </span>
              <span v-if="index < arrivalSegments.length - 1" class="trail-arrow" aria-hidden="true">→</span>
            </template>
            <span v-if="arrivalSegments.length === 0" class="src">引擎产物未给到达段序列。</span>
          </div>
          <p class="why">推荐原因（why）：{{ main.why || '引擎产物未给 why' }}</p>

          <div class="sub-head">
            一主二备 · 备选
            <span class="sub-tag">推荐 1 条 + 备选 {{ alternatives.length }} 条</span>
          </div>
          <p v-if="alternativeNotice" class="src warn">{{ alternativeNotice }}</p>
          <div v-if="alternatives.length > 0" class="alt-list">
            <div v-for="(alt, index) in alternatives" :key="`${alt.path_id}-${index}`" class="alt-row">
              <div class="alt-head">
                <span class="alt-name">
                  备选 {{ index + 1 }} · <span class="td-mono">{{ alt.path_id }}</span>
                </span>
                <span class="alt-eta td-num">{{ fmtEta(alt.eta_min) }} min</span>
                <span class="td-chip">较推荐 {{ deltaText(mainArrival?.eta_min, alt.eta_min) }}</span>
              </div>
              <div class="alt-why">{{ alt.reason || '引擎产物未给 reason' }}</div>
              <div class="alt-segs td-mono">
                {{ (alt.segments || []).join(' → ') || '引擎产物未给备选段序列' }}
              </div>
            </div>
          </div>
          <p v-else class="src">产物未给备选路径（不补造等价路线）。</p>

          <p class="foot-line">
            路线来自固定产物，参数改动不会重算；本页只做产物回放。全部数据 is_simulated = true。
          </p>
        </template>
        <p v-else class="src">暂无可展示的路线产物。</p>
      </div>
    </section>

    <section class="td-card">
      <div class="td-card-head">
        变化效果 · 两个 session 并排
        <span class="td-head-tag">两次 POST /route/recommend · 各读各的产物</span>
      </div>
      <div class="td-card-body">
        <p class="src">
          默认取选项第 1、第 2 条 session；切换后各发一次 POST /api/traffic/route/recommend，
          左右两列的数据互不复用；这里比较的是两条已算好的产物，不是两次重算。
        </p>

        <template v-if="canCompare">
          <div class="cmp-grid">
            <div class="cmp-side">
              <div class="cmp-head">
                <span class="cmp-title">A · 第 1 条选择</span>
                <select
                  v-model="leftSession"
                  class="route-select"
                  aria-label="左列 session"
                  @change="loadSide('left')"
                >
                  <option
                    v-for="option in options"
                    :key="`left-${option.session_id || option.request_id || ''}`"
                    :value="option.session_id || ''"
                  >
                    {{ optionLabel(option) }}
                  </option>
                </select>
              </div>
              <p v-if="leftLoading" class="src">正在读取左列…</p>
              <p v-else-if="leftError" class="src err">{{ leftError }}</p>
              <template v-else-if="left">
                <div class="chain compact">
                  <template v-for="(node, index) in leftChain" :key="`left-${node.key}`">
                    <div class="chain-node" :class="{ empty: node.empty }">
                      <div class="cn-step">{{ node.step }} {{ node.title }}</div>
                      <div class="cn-primary">{{ node.primary }}</div>
                      <div class="cn-secondary">{{ node.secondary }}</div>
                      <div class="cn-tag td-mono">{{ node.tag }}</div>
                    </div>
                    <div v-if="index < leftChain.length - 1" class="chain-arrow" aria-hidden="true">→</div>
                  </template>
                </div>
                <div class="cmp-eta">
                  到达 ETA <b class="td-num">{{ fmtEta(arrivalOf(left)?.eta_min) }} min</b>
                  <span class="sep">·</span>
                  离站 ETA <b class="td-num">{{ fmtEta(left.departure_route?.eta_min) }} min</b>
                </div>
                <p class="why">引擎原因（why）：{{ left.why || '—' }}</p>
                <p v-if="left.session_matched === false" class="src warn">
                  该 session 未在产物里匹配：端出的是产物首条请求，非该车行程。
                </p>
              </template>
              <p v-else class="src">选择 session 后读取路线。</p>
            </div>

            <div class="cmp-side">
              <div class="cmp-head">
                <span class="cmp-title">B · 第 2 条选择</span>
                <select
                  v-model="rightSession"
                  class="route-select"
                  aria-label="右列 session"
                  @change="loadSide('right')"
                >
                  <option
                    v-for="option in options"
                    :key="`right-${option.session_id || option.request_id || ''}`"
                    :value="option.session_id || ''"
                  >
                    {{ optionLabel(option) }}
                  </option>
                </select>
              </div>
              <p v-if="rightLoading" class="src">正在读取右列…</p>
              <p v-else-if="rightError" class="src err">{{ rightError }}</p>
              <template v-else-if="right">
                <div class="chain compact">
                  <template v-for="(node, index) in rightChain" :key="`right-${node.key}`">
                    <div class="chain-node" :class="{ empty: node.empty }">
                      <div class="cn-step">{{ node.step }} {{ node.title }}</div>
                      <div class="cn-primary">{{ node.primary }}</div>
                      <div class="cn-secondary">{{ node.secondary }}</div>
                      <div class="cn-tag td-mono">{{ node.tag }}</div>
                    </div>
                    <div v-if="index < rightChain.length - 1" class="chain-arrow" aria-hidden="true">→</div>
                  </template>
                </div>
                <div class="cmp-eta">
                  到达 ETA <b class="td-num">{{ fmtEta(arrivalOf(right)?.eta_min) }} min</b>
                  <span class="sep">·</span>
                  离站 ETA <b class="td-num">{{ fmtEta(right.departure_route?.eta_min) }} min</b>
                </div>
                <p class="why">引擎原因（why）：{{ right.why || '—' }}</p>
                <p v-if="right.session_matched === false" class="src warn">
                  该 session 未在产物里匹配：端出的是产物首条请求，非该车行程。
                </p>
              </template>
              <p v-else class="src">选择 session 后读取路线。</p>
            </div>
          </div>
          <p v-if="compareSummary" class="cmp-summary" :class="{ diff: compare?.changed }">
            {{ compareSummary }}
          </p>
        </template>

        <template v-else>
          <p class="src warn">
            可选 session 仅 {{ options.length }} 条（不足 2 条），并排对比退化为一列：
            {{ options.length === 0 ? '无引擎 session 选项，下面只展示当前回退演示会话路线' : '只展示当前唯一 session 的路线' }}；
            不补造第二个 session，也不伪造差异。
          </p>
          <div v-if="main" class="cmp-side single">
            <div class="chain compact">
              <template v-for="(node, index) in mainChain" :key="`single-${node.key}`">
                <div class="chain-node" :class="{ empty: node.empty }">
                  <div class="cn-step">{{ node.step }} {{ node.title }}</div>
                  <div class="cn-primary">{{ node.primary }}</div>
                  <div class="cn-secondary">{{ node.secondary }}</div>
                  <div class="cn-tag td-mono">{{ node.tag }}</div>
                </div>
                <div v-if="index < mainChain.length - 1" class="chain-arrow" aria-hidden="true">→</div>
              </template>
            </div>
            <div class="cmp-eta">
              到达 ETA <b class="td-num">{{ fmtEta(mainArrival?.eta_min) }} min</b>
              <span class="sep">·</span>
              离站 ETA <b class="td-num">{{ fmtEta(main.departure_route?.eta_min) }} min</b>
            </div>
          </div>
          <p v-else class="src">当前 session 的路线也未能读取，无并排数据。</p>
        </template>
      </div>
    </section>

    <section class="td-card">
      <div class="td-card-head">
        路线是否随参数变化
        <span class="td-head-tag">方案 A · 保守口径（队长裁定）</span>
      </div>
      <div class="td-card-body">
        <div class="verdict">
          <b>结论：路线不会因为场景注入 / 人工置位 / 告警下发而变化——引擎产物不随参数变化，本页只做产物回放。</b>
        </div>
        <div class="tbl-wrap">
          <table class="td-table">
            <thead>
              <tr>
                <th>操作</th>
                <th>路线是否变化</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>切换 session</td>
                <td>会（换一条已有产物）</td>
                <td>换读另一条已算好的路线；两次 POST /route/recommend 各自取产物，不是重算。</td>
              </tr>
              <tr>
                <td>场景注入（环境侧）</td>
                <td>不会</td>
                <td>只改环境上下文与判级因素，不触发 route/recommend 重算。</td>
              </tr>
              <tr>
                <td>人工置位（F07 / F08 / F11）</td>
                <td>不会</td>
                <td>事件侧因素只影响判级 / CI / 建议，不触发算路。</td>
              </tr>
              <tr>
                <td>告警下发 / 回写</td>
                <td>不会</td>
                <td>只改告警状态与处置留痕，路线产物不动。</td>
              </tr>
              <tr>
                <td>切换站点包</td>
                <td>会（换站重读）</td>
                <td>页面重载后读该站自己的已有产物；不拿别的站路线冒充本站。</td>
              </tr>
              <tr>
                <td>引擎产物重新生成</td>
                <td>可能</td>
                <td>离线重跑引擎后重新读取才可能看到新版；本页不检测、不重算、不代算 ETA。</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="recheck">
          <button
            type="button"
            class="td-btn sm"
            :disabled="recheckState === 'running' || !main"
            @click="recheckSameSession"
          >
            {{ recheckState === 'running' ? '正在重新读取…' : '重新读取当前 session 产物并比对' }}
          </button>
          <span v-if="recheckText" class="recheck-text" :class="{ warn: recheckState === 'diff' }">
            {{ recheckText }}
          </span>
        </div>
        <p class="src">
          复核口径：同一 session 连续两次 POST /api/traffic/route/recommend —— 段序列 / ETA 相同即说明产物没变；
          不同则列出差异（只可能来自产物文件更新）。本页不检测引擎、不重算路线。
        </p>
      </div>
    </section>

    <p class="foot-line">
      数据来源：GET /api/traffic/route/options + POST /api/traffic/route/recommend ·
      路线来自固定产物，参数改动不会重算 · 演示数据（模拟）· 全部数据 is_simulated = true
    </p>
  </div>
</template>

<style scoped>
/* 颜色一律走 AppShell 注入的 TD CSS 变量（shared/theme.ts），本文件不写死色值。 */
.route-view {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}
/* ---------- 应急态（TC-10）：停下引导，替换为「请服从现场指挥」 ----------
   位置纪律：只替「路线规划」这一块；页面其它内容一字不减（见 scripts/frontend_gate.py 的
   gate_emergency_keep 记录的历史教训）。颜色走 TD 变量，本文件不写死色值。 */
.emergency-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0 0 8px;
  padding: 10px 12px;
  border-left: 4px solid var(--td-error-color);
  background: var(--td-error-color-1);
  border-radius: var(--td-radius-sm);
}
.em-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--td-error-color);
}
.em-line {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--td-text-color-primary);
}
.em-src {
  margin: 2px 0 0;
  font-size: 11px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder);
}
.src {
  margin: 0 0 8px;
  font-size: 11px;
  line-height: 1.6;
  color: var(--td-text-color-placeholder);
}
.src.warn {
  padding: 5px 8px;
  color: var(--td-warning-color);
  background: var(--td-warning-color-1);
  border-radius: var(--td-radius-sm);
}
.src.err {
  padding: 5px 8px;
  color: var(--td-error-color);
  background: var(--td-error-color-1);
  border-radius: var(--td-radius-sm);
}
.sep {
  margin: 0 4px;
  color: var(--td-text-color-placeholder);
}

/* session 选择器 */
.pick-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.pick-label {
  flex: 0 0 auto;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}
.route-select {
  flex: 1;
  min-width: 0;
  height: 26px;
  padding: 0 6px;
  font-size: 11px;
  color: var(--td-text-color-primary);
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-border);
  border-radius: var(--td-radius-sm);
}
.route-select:focus {
  outline: none;
  border-color: var(--td-brand-color);
}

/* 四段链路条：首尾相接，箭头只作连接语义 */
.chain {
  display: grid;
  grid-template-columns:
    minmax(0, 1fr) 16px minmax(0, 1fr) 16px minmax(0, 1fr) 16px
    minmax(0, 1fr);
  align-items: stretch;
  margin: 6px 0 8px;
}
.chain-node {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding: 8px 9px;
  background: var(--td-bg-color-secondarycontainer);
  border: 1px solid var(--td-component-stroke);
  border-radius: var(--td-radius-sm);
}
.chain-node.empty {
  border-style: dashed;
  background: var(--td-bg-color-container);
}
.chain-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: var(--td-text-color-placeholder);
}
.cn-step {
  font-size: 10px;
  color: var(--td-text-color-placeholder);
  white-space: nowrap;
}
.cn-primary {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
  color: var(--td-text-color-primary);
  word-break: break-all;
}
.chain-node.empty .cn-primary {
  color: var(--td-text-color-secondary);
  font-weight: 400;
}
.cn-secondary {
  font-size: 11px;
  line-height: 1.5;
  color: var(--td-text-color-secondary);
  word-break: break-word;
}
.cn-tag {
  align-self: flex-start;
  margin-top: 2px;
  padding: 0 5px;
  font-size: 10px;
  color: var(--td-brand-color);
  background: var(--td-brand-color-1);
  border-radius: var(--td-radius-sm);
}
.chain-node.empty .cn-tag {
  color: var(--td-text-color-placeholder);
  background: var(--td-bg-color-component);
}
.cn-note {
  font-size: 10px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder);
}
.chain.compact .chain-node {
  padding: 5px 6px;
  gap: 1px;
}
.chain.compact .cn-primary {
  font-size: 11px;
}
.chain.compact .cn-secondary {
  font-size: 10px;
}

/* 路线摘要 / 段序列 */
.route-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 14px;
  margin-bottom: 6px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.route-meta b {
  color: var(--td-text-color-primary);
}
.sub-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 10px 0 5px;
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}
.sub-tag {
  margin-left: auto;
  font-size: 10px;
  font-weight: 400;
  color: var(--td-text-color-placeholder);
}
.seg-trail {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}
.seg-chip {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  padding: 2px 6px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
  background: var(--td-bg-color-secondarycontainer);
  border: 1px solid var(--td-component-stroke);
  border-radius: var(--td-radius-sm);
}
.seg-chip b {
  color: var(--td-text-color-primary);
  font-size: 10px;
}
.trail-arrow {
  font-size: 10px;
  color: var(--td-text-color-placeholder);
}
.why {
  margin: 8px 0 0;
  font-size: 11px;
  line-height: 1.7;
  color: var(--td-text-color-secondary);
}

/* 一主二备 */
.alt-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.alt-row {
  padding: 7px 9px;
  border: 1px solid var(--td-component-stroke);
  border-radius: var(--td-radius-sm);
}
.alt-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
}
.alt-name {
  font-size: 12px;
  color: var(--td-text-color-primary);
}
.alt-eta {
  font-size: 12px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}
.alt-why {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.6;
  color: var(--td-text-color-secondary);
}
.alt-segs {
  margin-top: 3px;
  font-size: 10px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder);
  word-break: break-all;
}
.foot-line {
  margin: 10px 0 0;
  padding-top: 8px;
  border-top: 1px dashed var(--td-component-stroke);
  font-size: 10px;
  line-height: 1.6;
  color: var(--td-text-color-placeholder);
}

/* 两个 session 并排 */
.cmp-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.cmp-side {
  min-width: 0;
  padding: 8px 9px;
  border: 1px solid var(--td-component-stroke);
  border-radius: var(--td-radius-sm);
}
.cmp-side.single {
  max-width: 100%;
}
.cmp-head {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 4px;
}
.cmp-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}
.cmp-eta {
  margin-top: 4px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.cmp-eta b {
  color: var(--td-text-color-primary);
}
.cmp-summary {
  margin: 10px 0 0;
  padding: 7px 9px;
  font-size: 11px;
  line-height: 1.6;
  color: var(--td-brand-color);
  background: var(--td-brand-color-1);
  border-radius: var(--td-radius-sm);
}
.cmp-summary.diff {
  color: var(--td-warning-color);
  background: var(--td-warning-color-1);
}

/* 参数是否影响路线 */
.verdict {
  margin-bottom: 8px;
  padding: 8px 10px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--td-text-color-primary);
  background: var(--td-bg-color-secondarycontainer);
  border-left: 3px solid var(--td-warning-color);
  border-radius: var(--td-radius-sm);
}
.tbl-wrap {
  overflow-x: auto;
}
.recheck {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 10px 0 6px;
}
.recheck-text {
  font-size: 11px;
  line-height: 1.5;
  color: var(--td-success-color);
}
.recheck-text.warn {
  color: var(--td-warning-color);
}

/* ---------- 窄屏（与全局 1180 / 900 / 560 断点对齐） ---------- */
@media (max-width: 900px) {
  .chain {
    grid-template-columns: minmax(0, 1fr);
  }
  .chain-arrow {
    transform: rotate(90deg);
  }
  .cmp-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (max-width: 560px) {
  .pick-row {
    flex-direction: column;
    align-items: stretch;
  }
  .route-select {
    height: 32px;
  }
  .sub-head {
    flex-wrap: wrap;
  }
  .sub-tag {
    margin-left: 0;
  }
}
</style>
