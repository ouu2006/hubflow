<script setup lang="ts">
// 监控大屏(Issue #77 三页收敛 · 原 Issue #78 设计稿 01 的态势总览 + 设计稿 02 的拥挤度热力**并成一页**):
//   顶栏(壳层) → KPI 条(4 格)
//   → 三栏(左:**选择监控**(视图切换 + 监控范围 + 等级分布 + 路段列表)
//           中:**全路段状态**(路网图,四级 / 拥挤指数两视图)
//           右:**路段信息**(详情 / 双源并排 / 因素 / CI 与四项加权 / CI 走势 / 关联告警 / 预测 / 下发))
//   → 底部**热力带**(档位分布 | 路段×时间热力矩阵 | CI 色阶与口径)+ 告警条 → 页脚口径条。
//
// 为什么热力页并进来:业主 2026-10-13 裁定 Web 只保留三层(感知 / 决策 / 大屏),`/heat` 不再是独立页。
// 并入方式是**保信息不保页**:原 `/heat` 的 8 个 widget 各有落点(见 README 第十二节映射表),
// 视图切换与 CI 口径(只展示、不判级)原样保留,页脚 / 图例 / 列表三处标注一句不删。
//
// 数据:全部走只读快照接口(src/api/traffic.ts),不做任何业务计算。
// 口径铁律:
//   ① 一期全部 is_simulated=true 示例数据,页面不出现「实时 / 实测 / 现场」表述;
//   ② 三重编码(颜色 + 竖条图标 + 文字)由 LevelBadge 保证;
//   ③ 数据不可用(缺字段或 data_age_s > 120s)恒为灰 + 「不可用」文字分支(TC-11),绝不显示成蓝/绿;
//   ④ 品牌蓝只用于「当前 / 已选 / 可操作」(选中行、选中路段、主按钮、当前页签),等级色只表示路况等级;
//   ⑤ CI 只用于热力展示与辅助排序,**不得作为判级依据**(手册 §6.5 第 1 条),冲突以四级为准;
//   ⑥ 不做 3D、不做无断面间标注的内插;所有数字带单位或口径标注,空值一律「—」,不编造。
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  getTrafficAlerts,
  getTrafficCiHistory,
  getTrafficFactors,
  getTrafficHeatMatrix,
  getTrafficMeta,
  getTrafficNetwork,
  getTrafficOverview,
  getTrafficSegmentSources,
  getTrafficSegments,
  getTrafficThresholds,
  getTrafficVehicles,
  subscribeTrafficSnapshot,
} from '../../api/traffic'
import { demoSegment, isOsmNetwork, networkSourceLabel } from '../../shared/demoNetwork'
import { activePack } from '../../station-packs/index'
import type { SourceMode } from '../../shared/nav'
import { TD } from '../../shared/theme'
import {
  ciAvailable,
  CI_BAND_NOTE,
  CI_BANDS,
  CI_DISCLAIMER,
  formatStamp,
  isStale,
  LEVELS,
  levelStyle,
  UNAVAILABLE,
  type CiHistory,
  type CongestionLevel,
  type CongestionViewMode,
  type FactorApplied,
  type HeatMatrix,
  type SegmentRecord,
  type SegmentSourcePair,
  type ThresholdSnapshot,
  type TrafficAlert,
  type TrafficNetwork,
  type TrafficOverview,
  type VehicleRecord,
} from '../../shared/traffic'
import AppShell from '../../components/AppShell.vue'
import LevelBadge from './components/LevelBadge.vue'
import NetMap from './components/NetMap.vue'
import AlertList from './components/AlertList.vue'
import BandDistribution from './components/BandDistribution.vue'
import CiScale from './components/CiScale.vue'
import CiTrendBars from './components/CiTrendBars.vue'
import FactorBreakdown from './components/FactorBreakdown.vue'
import HeatMatrixTable from './components/HeatMatrixTable.vue'
import SegmentRankTable from './components/SegmentRankTable.vue'

const router = useRouter()
/** 底图来源短文案(页面水印/页脚口径用):桥接覆盖过就是真路网,否则报包自己的口径 */
const sourceLabel = networkSourceLabel()
/** 底图是否真 OSM 路网 —— 只有它为真时地图内才有署名,底图说明文案随之分支(否则不写"署名见地图内") */
const osmActive = isOsmNetwork()
/** 站点名(顶栏 chip):默认取当前站点包,拿到 meta 后由 meta.station.name 覆盖 —— 三页同一口径 */
const stationName = ref(activePack().station.name)

// ---------- 快照状态 ----------
const overview = ref<TrafficOverview | null>(null)
const segments = ref<SegmentRecord[]>([])
const vehicles = ref<VehicleRecord[]>([])
const network = ref<TrafficNetwork | null>(null)
const alerts = ref<TrafficAlert[]>([])
/** 全网生效因素(各路段 factors_applied 展平,供 KPI 第 4 格取前 3 条) */
const allFactors = ref<(FactorApplied & { segment_id: string })[]>([])
/** 选中路段的双源并排(video / twin + 差值,TC-19 展示侧) */
const pair = ref<SegmentSourcePair | null>(null)
/** 选中路段的生效因素 */
const segFactors = ref<(FactorApplied & { segment_id: string })[]>([])
/** 选中路段的 CI 走势(原 /heat 右栏) */
const history = ref<CiHistory | null>(null)
/** 路段 × 时间热力矩阵(原 /heat 中栏) */
const heat = ref<HeatMatrix | null>(null)
/** 判级阈值 + CI 四项加权构成(原 /heat 右栏;权重不写死,来自接口) */
const thresholds = ref<ThresholdSnapshot | null>(null)

const selectedId = ref<string | null>(null)
/** 数据源视图(顶栏)：决定右栏「双数据源并排」表按哪一侧口径读数 */
const sourceMode = ref<SourceMode>('both')
/** 视图模式:四级视图(判级产出)/ 拥挤指数视图(展示量,原 /heat 页头切换) */
const viewMode = ref<CongestionViewMode>('level')
/** 监控范围筛选(左栏「选择监控」):null = 全部;0 = 数据不可用档 */
const scope = ref<CongestionLevel | 0 | null>(null)
const snapshotTs = ref('')

let unsubscribe: (() => void) | null = null

const selected = computed<SegmentRecord | null>(
  () => segments.value.find((s) => s.segment_id === selectedId.value) ?? null,
)

const selectedName = computed<string>(() => {
  const s = selected.value
  if (!s) return '—'
  return demoSegment(s.segment_id)?.name ?? s.segment_id
})

/** 默认选中:非陈旧路段里 level 最高者(同档取 x 大者);无可用则退回首条 */
function pickDefaultId(list: SegmentRecord[]): string | null {
  if (list.length === 0) return null
  const usable = list.filter((s) => !isStale(s))
  const pool = usable.length > 0 ? usable : list
  let best = pool[0]!
  for (const s of pool) {
    if (s.level > best.level || (s.level === best.level && (s.x ?? 0) > (best.x ?? 0))) best = s
  }
  return best.segment_id
}

/** 选中路段相关的三个接口(并排表 + 因素 + CI 走势);选中变化与快照刷新都会重拉 */
async function loadSelectedSide(segmentId: string | null): Promise<void> {
  if (!segmentId) {
    pair.value = null
    segFactors.value = []
    history.value = null
    return
  }
  const [p, f, h] = await Promise.allSettled([
    getTrafficSegmentSources(segmentId),
    getTrafficFactors(segmentId),
    getTrafficCiHistory(segmentId, 12),
  ])
  if (selectedId.value !== segmentId) return // 选择已变:丢弃过期响应
  pair.value = p.status === 'fulfilled' ? p.value : null
  segFactors.value = f.status === 'fulfilled' ? f.value.factors : []
  history.value = h.status === 'fulfilled' ? h.value : null
}

/**
 * 刷新序号:SSE 触发与手动刷新可能并发。只有"最新一次"的响应允许落到页面,
 * 否则先发出、后返回的旧响应会覆盖新快照(页面显示上一版数据)。
 */
let refreshSeq = 0
/** 本次刷新中失败的接口(页头提示用;失败面板保留旧值但必须标"上一版",不得冒充当前) */
const failedPanels = ref<string[]>([])

const PANEL_LABEL: Record<string, string> = {
  overview: 'KPI',
  segments: '路段监测',
  vehicles: '车辆',
  network: '路网',
  alerts: '告警',
  factors: '因素',
  matrix: '热力矩阵',
  thresholds: '阈值与 CI 权重',
}

async function refresh(): Promise<void> {
  const seq = ++refreshSeq
  const [ov, seg, veh, net, al, fa, meta, matrix, thr] = await Promise.allSettled([
    getTrafficOverview(),
    getTrafficSegments(),
    getTrafficVehicles(),
    getTrafficNetwork(),
    getTrafficAlerts(),
    getTrafficFactors(),
    getTrafficMeta(),
    getTrafficHeatMatrix(12, 60),
    getTrafficThresholds(),
  ])
  if (seq !== refreshSeq) return // 已被更晚的一次刷新取代:丢弃本次响应
  const failed: string[] = []
  const track = (name: string, ok: boolean): void => {
    if (!ok) failed.push(PANEL_LABEL[name] ?? name)
  }
  if (ov.status === 'fulfilled') overview.value = ov.value
  track('overview', ov.status === 'fulfilled')
  if (seg.status === 'fulfilled') {
    segments.value = seg.value.segments
    snapshotTs.value = seg.value.ts
    if (selectedId.value === null) selectedId.value = pickDefaultId(seg.value.segments)
  }
  track('segments', seg.status === 'fulfilled')
  if (veh.status === 'fulfilled') vehicles.value = veh.value.vehicles
  track('vehicles', veh.status === 'fulfilled')
  if (net.status === 'fulfilled') network.value = net.value
  track('network', net.status === 'fulfilled')
  if (al.status === 'fulfilled') alerts.value = al.value.alerts
  track('alerts', al.status === 'fulfilled')
  if (fa.status === 'fulfilled') allFactors.value = fa.value.factors
  track('factors', fa.status === 'fulfilled')
  if (matrix.status === 'fulfilled') heat.value = matrix.value
  track('matrix', matrix.status === 'fulfilled')
  if (thr.status === 'fulfilled') thresholds.value = thr.value
  track('thresholds', thr.status === 'fulfilled')
  // 站名只用于顶栏 chip:取不到就保持站点包里的名字,不因此把整页标成"上一版数据"
  if (meta.status === 'fulfilled') stationName.value = meta.value.station.name
  failedPanels.value = failed
  await loadSelectedSide(selectedId.value)
}

watch(selectedId, (id) => {
  void loadSelectedSide(id)
})

onMounted(() => {
  void refresh()
  unsubscribe = subscribeTrafficSnapshot(() => {
    void refresh()
  })
})

onUnmounted(() => {
  unsubscribe?.()
})

// ---------- 文案 / 格式化助手 ----------
const CN_NUM: Record<CongestionLevel, string> = { 1: '一', 2: '二', 3: '三', 4: '四' }

function levelName(seg: SegmentRecord): string {
  return isStale(seg) ? UNAVAILABLE.name : (seg.level_name ?? LEVELS[seg.level].name)
}

function fmt(v: number | undefined | null, digits = 2): string {
  return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—'
}

/** 'YYYY-MM-DD HH:mm:ss' → 'HH:mm:ss'(告警条首次观测时间) */
function hhmmss(stamp: string): string {
  return stamp.length >= 8 ? stamp.slice(-8) : stamp
}

/** 路段名(矩阵 / 排行里的行不带 name,统一从路网取,与地图同源) */
function nameOf(id: string): string {
  return demoSegment(id)?.name ?? id
}

// ---------- KPI 条 ----------
/** 环比文案:负 = 变慢(较上一版慢 x km/h) */
const avgDeltaText = computed(() => {
  const d = overview.value?.avg_speed_delta_kmh
  if (typeof d !== 'number') return '—'
  if (Math.abs(d) < 0.05) return '较上一版持平'
  return `较上一版${d > 0 ? '快' : '慢'} ${Math.abs(d).toFixed(1)} km/h`
})

/** 采纳率:guided_rate(0~1) → 百分数保留一位 */
const adoptText = computed(() => {
  const o = overview.value
  if (!o) return '—'
  return `已引导 ${o.vehicles_guided} · 采纳率 ${(o.guided_rate * 100).toFixed(1)}%`
})

/** 前 3 条生效因素名(按 factor_id 去重,展示口径) */
const topFactors = computed(() => {
  const seen = new Set<string>()
  const out: string[] = []
  for (const f of allFactors.value) {
    if (seen.has(f.factor_id)) continue
    seen.add(f.factor_id)
    out.push(`${f.factor_id} ${f.name}`)
    if (out.length === 3) break
  }
  return out
})

// ---------- 左栏 · 等级分布 + 监控范围 ----------
interface DistRow {
  level: CongestionLevel | 0
  name: string
  count: number
  color: string
}

const dist = computed<DistRow[]>(() =>
  (overview.value?.level_distribution ?? []).map((r) => ({
    level: r.level,
    name: r.name,
    count: r.count,
    color: r.level === 0 ? UNAVAILABLE.color : LEVELS[r.level].color,
  })),
)

const distTotal = computed(() => {
  const o = overview.value
  if (o) return o.segment_total
  return dist.value.reduce((acc, r) => acc + r.count, 0)
})

function distWidth(r: DistRow): string {
  const total = dist.value.reduce((acc, x) => acc + x.count, 0)
  if (total <= 0 || r.count <= 0) return '0%'
  return `${(r.count / total) * 100}%`
}

/** 监控范围切换(点分布条 / 点档位图例 / 「全部」) */
function toggleScope(level: CongestionLevel | 0): void {
  scope.value = scope.value === level ? null : level
}

// ---------- 左栏 · 路段列表(四级 = 原序;指数视图 = 按 CI 降序,原 /heat 左栏口径) ----------
interface SegRow {
  seg: SegmentRecord
  color: string
  text: string
  stale: boolean
  name: string
}

/** 监控范围过滤(0 = 数据不可用档) */
const scoped = computed<SegmentRecord[]>(() => {
  const s = scope.value
  if (s === null) return segments.value
  if (s === 0) return segments.value.filter((x) => isStale(x))
  return segments.value.filter((x) => !isStale(x) && x.level === s)
})

/** 四级视图:按等级降序、同档按饱和度降序(与默认选中同口径);指数视图:按 CI 降序、不可用排最后 */
const segRows = computed<SegRow[]>(() => {
  const list = [...scoped.value]
  if (viewMode.value === 'index') {
    list.sort((a, b) => {
      const av = ciAvailable(a)
      const bv = ciAvailable(b)
      if (av !== bv) return av ? -1 : 1
      return (b.ci ?? 0) - (a.ci ?? 0)
    })
  } else {
    list.sort((a, b) => b.level - a.level || (b.x ?? 0) - (a.x ?? 0))
  }
  return list.map((seg) => {
    const st = levelStyle(seg)
    return {
      seg,
      color: st.color,
      text: st.text,
      stale: isStale(seg),
      name: nameOf(seg.segment_id),
    }
  })
})

/** 指数视图的左栏排行(原 /heat 的 SegmentRankTable 口径,含不可用清单) */
const rankRows = computed(() =>
  scoped.value
    .map((s) => ({
      id: s.segment_id,
      name: nameOf(s.segment_id),
      ci: ciAvailable(s) ? (s.ci as number) : null,
      level: s.level,
      available: ciAvailable(s),
    }))
    .sort((a, b) => {
      if (a.available !== b.available) return a.available ? -1 : 1
      return (b.ci ?? 0) - (a.ci ?? 0)
    }),
)

// ---------- 中栏 · 地图 ----------
const sections = computed(() => network.value?.sections ?? [])
const dropoffs = computed(() => network.value?.dropoffs ?? [])
const zones = computed(() => network.value?.zones ?? [])
const stations = computed(() => network.value?.stations ?? [])

/** 选中 chip:SEG-003 拥堵 · x 0.91 / 0.84(video/twin);video 不可用只显示 twin 并注明 */
const mapChip = computed<string>(() => {
  const s = selected.value
  if (!s) return ''
  const v = pair.value?.slots.find((x) => x.source === 'video')
  const t = pair.value?.slots.find((x) => x.source === 'twin')
  const vx = v?.record?.x
  const tx = t?.record?.x
  const head = `${s.segment_id} ${levelName(s)}`
  if (v?.available === true && typeof vx === 'number' && typeof tx === 'number') {
    return `${head} · x ${vx} / ${tx}`
  }
  if (typeof tx === 'number') return `${head} · x ${tx}(仅孪生链路)`
  return head
})

// ---------- 右栏 · 双数据源并排(TC-19) ----------
/** 并排表只取四项(饱和度 x / 车速 / 排队长度 / 排队消散),按设计稿口径 */
const DELTA_KEYS = ['x', 'v_kmh', 'L_q_m', 'T_d_min']

const deltaRows = computed(() =>
  (pair.value?.deltas ?? []).filter((d) => DELTA_KEYS.includes(d.key)),
)

const videoAvailable = computed(
  () => pair.value?.slots.find((s) => s.source === 'video')?.available === true,
)

// ---------- 右栏 · 路段详情摘要 + CI ----------
const detailSummary = computed<string>(() => {
  const s = selected.value
  if (!s) return ''
  const parts = [`${CN_NUM[s.level]}级`, levelName(s)]
  parts.push(`更新 ${s.data_age_s ?? '—'}s 前`)
  parts.push(`饱和度 ${fmt(s.x)}`)
  if (s.triggered_by && s.triggered_by.length > 0) parts.push(`触发 ${s.triggered_by.join(' / ')}`)
  return parts.join(' · ')
})

const ciText = computed(() => {
  const r = selected.value
  return r && ciAvailable(r) ? (r.ci as number).toFixed(1) : '不可用'
})

const ciTextColor = computed(() => {
  const r = selected.value
  return r && ciAvailable(r) ? LEVELS[r.level].text : UNAVAILABLE.color
})

/** 四个 CI 权重(来自 thresholds,不写死) */
const weights = computed(() => thresholds.value?.ci_weights ?? [])
const weightText = computed(() =>
  weights.value.length > 0 ? weights.value.map((w) => w.weight.toFixed(2)).join('/') : '—',
)

/** 各权重要素的「数值」:饱和度 x / 速度比 v/v_f / 排队比 L_q/L_seg / 消散 T_d(缺字段显示「—」) */
function metricText(key: string): string {
  const r = selected.value
  if (!r) return '—'
  const ratio = (a?: number, b?: number): string =>
    typeof a === 'number' && typeof b === 'number' && Number.isFinite(a) && Number.isFinite(b) && b !== 0
      ? (a / b).toFixed(2)
      : '—'
  switch (key) {
    case 'x':
      return typeof r.x === 'number' ? String(r.x) : '—'
    case 'v':
      return ratio(r.v_kmh, r.v_f_kmh)
    case 'k':
      return ratio(r.L_q_m, r.L_seg_m)
    case 'T_d':
      return typeof r.T_d_min === 'number' ? String(r.T_d_min) : '—'
    default:
      return '—'
  }
}

// ---------- 右栏 · 关联告警(原 /heat 右栏) ----------
const selectedAlerts = computed(() =>
  alerts.value.filter(
    (a) => a.segment_id === selectedId.value && a.status !== '已闭环' && a.status !== '误报',
  ),
)

// ---------- 底部 · 档位分布(原 /heat 左栏) ----------
const bandRows = computed(() => {
  const avail = segments.value.filter(ciAvailable)
  const out: { level: CongestionLevel; name: string; count: number }[] = []
  for (let lv = 4; lv >= 1; lv--) {
    const lo = CI_BANDS[lv - 1] ?? 0
    const hi = CI_BANDS[lv] ?? 100
    const count = avail.filter((s) => {
      const ci = s.ci as number
      return lv === 4 ? ci >= lo && ci <= hi : ci >= lo && ci < hi
    }).length
    out.push({ level: lv as CongestionLevel, name: LEVELS[lv as CongestionLevel].name, count })
  }
  return out
})

const unavailableCount = computed(() => segments.value.filter((s) => !ciAvailable(s)).length)

// ---------- 底部 · 告警条 ----------
const unclosed = computed(() =>
  alerts.value.filter((a) => a.status === '待认领' || a.status === '处置中'),
)
const unclaimedCount = computed(() => alerts.value.filter((a) => a.status === '待认领').length)
const processingCount = computed(() => alerts.value.filter((a) => a.status === '处置中').length)

/** 第一条未闭环告警(默认取列表序=待认领在前) */
const firstAlert = computed<TrafficAlert | null>(() => unclosed.value[0] ?? null)

/** 告警摘要里的 x:从该路段快照取(不编造) */
const firstAlertX = computed<string>(() => {
  const a = firstAlert.value
  if (!a) return '—'
  const seg = segments.value.find((s) => s.segment_id === a.segment_id)
  return fmt(seg?.x)
})

// ---------- 交互 ----------
function onSelect(id: string): void {
  selectedId.value = id
}

function gotoDecision(): void {
  void router.push('/decision')
}
</script>

<template>
  <AppShell
    active="dashboard"
    :station="stationName"
    :ts="snapshotTs"
    v-model:sourceMode="sourceMode"
    title=""
  >
    <div v-if="failedPanels.length > 0" class="stale-bar" role="status">
      ⚠ 本次刷新未取到:{{ failedPanels.join(' / ') }} —— 这些面板显示的是上一版数据,请勿据此判断当前态势。
    </div>

    <!-- KPI 条(取代页头) -->
    <div class="td-card kpi-bar">
      <div class="kpi-cell">
        <div class="kpi-label">全网平均车速</div>
        <div class="kpi-value">{{ fmt(overview?.avg_speed_kmh, 1) }}<span class="kpi-unit">km/h</span></div>
        <div class="kpi-sub">{{ avgDeltaText }}</div>
      </div>
      <div class="kpi-cell">
        <div class="kpi-label">最堵路段</div>
        <div class="kpi-value td-mono">{{ overview?.worst_segment?.segment_id ?? '—' }}</div>
        <div class="kpi-sub">
          <template v-if="overview?.worst_segment">
            <LevelBadge :level="overview.worst_segment.level" />
            <span class="kpi-sep">·</span>{{ overview.worst_segment.name }}
            <span class="kpi-sep">·</span>x {{ fmt(overview.worst_segment.x) }}
          </template>
          <template v-else>—</template>
        </div>
      </div>
      <div class="kpi-cell">
        <div class="kpi-label">站前在途车辆</div>
        <div class="kpi-value">{{ overview?.vehicles_inbound ?? '—' }}<span class="kpi-unit">辆</span></div>
        <div class="kpi-sub">{{ adoptText }}</div>
      </div>
      <div class="kpi-cell">
        <div class="kpi-label">当前生效因素</div>
        <div class="kpi-value">{{ overview?.active_factors ?? '—' }}<span class="kpi-unit">项</span></div>
        <div class="kpi-sub">
          <template v-if="topFactors.length > 0">{{ topFactors.join(' · ') }}</template>
          <template v-else>无生效因素</template>
        </div>
      </div>
    </div>

    <div class="td-body">
      <!-- 左栏 · 选择监控 -->
      <div class="td-col col-left">
        <section class="td-card">
          <div class="td-card-head">
            选择监控<span class="td-head-tag">{{ distTotal }} 个路段</span>
          </div>
          <div class="td-card-body">
            <div class="td-seg view-seg" role="group" aria-label="视图切换">
              <span
                class="td-seg-item"
                :class="{ on: viewMode === 'level' }"
                role="button"
                :aria-pressed="viewMode === 'level'"
                @click="viewMode = 'level'"
              >
                四级视图
              </span>
              <span
                class="td-seg-item"
                :class="{ on: viewMode === 'index' }"
                role="button"
                :aria-pressed="viewMode === 'index'"
                @click="viewMode = 'index'"
              >
                拥挤指数视图
              </span>
            </div>
            <div class="dist-bar" :style="{ background: TD.bgSecondary }">
              <span
                v-for="r in dist"
                :key="`d-${r.level}`"
                class="dist-seg"
                :class="{ dim: scope !== null && scope !== r.level }"
                :style="{ width: distWidth(r), background: r.color }"
                role="button"
                :title="`只看 ${r.name}(${r.count} 个路段)`"
                @click="toggleScope(r.level)"
              />
            </div>
            <div class="dist-legend">
              <span
                v-for="r in dist"
                :key="`lg-${r.level}`"
                class="dist-item"
                :class="{ on: scope === r.level }"
                role="button"
                :aria-pressed="scope === r.level"
                @click="toggleScope(r.level)"
              >
                <LevelBadge :level="r.level === 0 ? 1 : r.level" :stale="r.level === 0" />
                <span class="td-num dist-count">{{ r.count }}</span>
              </span>
              <span class="dist-item all" :class="{ on: scope === null }" role="button" @click="scope = null">
                全部
              </span>
            </div>
            <p v-if="viewMode === 'index'" class="note">{{ CI_DISCLAIMER }}</p>
          </div>
        </section>

        <!-- 四级视图:路段监测列表;指数视图:按 CI 降序排行(原 /heat 左栏) -->
        <section class="td-card seg-card">
          <div class="td-card-head">
            路段监测
            <span class="td-head-tag">{{ viewMode === 'index' ? '按 CI 降序' : '按等级排序' }}</span>
          </div>
          <div class="td-card-body flush seg-body">
            <div class="td-scroll seg-list">
              <SegmentRankTable
                v-if="viewMode === 'index'"
                :items="rankRows"
                :selected-id="selectedId"
                @select="onSelect"
              />
              <template v-else>
                <div
                  v-for="row in segRows"
                  :key="row.seg.segment_id"
                  class="td-row"
                  :class="{ on: row.seg.segment_id === selectedId }"
                  role="button"
                  :aria-pressed="row.seg.segment_id === selectedId"
                  @click="onSelect(row.seg.segment_id)"
                >
                  <span class="lvl-bar" :style="{ background: row.color }" />
                  <span class="seg-meta">
                    <span class="seg-name">{{ row.name }}</span>
                    <span class="seg-id td-mono">{{ row.seg.segment_id }}</span>
                  </span>
                  <span class="seg-value td-num" :style="{ color: row.stale ? UNAVAILABLE.text : row.text }">
                    <template v-if="row.stale">数据不可用 · 陈旧 {{ row.seg.data_age_s ?? '—' }}s</template>
                    <template v-else>x {{ fmt(row.seg.x) }}</template>
                  </span>
                  <LevelBadge :level="row.seg.level" :stale="row.stale" />
                </div>
                <p v-if="segRows.length === 0" class="empty">
                  {{ scope === null ? '快照为空(接口层未起?)' : '该范围当前没有路段' }}
                </p>
              </template>
            </div>
          </div>
        </section>
      </div>

      <!-- 中栏 · 全路段状态 -->
      <div class="td-col col-mid">
        <section class="td-card map-card">
          <div class="td-card-body flush map-body">
            <NetMap
              :segments="segments"
              :vehicles="vehicles"
              :selected-id="selectedId"
              :route-segments="[]"
              :mode="viewMode"
              :ts="snapshotTs"
              :sections="sections"
              :dropoffs="dropoffs"
              :zones="zones"
              :stations="stations"
              :selected-chip="mapChip"
              :legend="true"
              @select="onSelect"
            />
          </div>
          <div class="map-caption">
            底图来源:{{ sourceLabel }} · 路网为示例样例(非实测)<template v-if="osmActive"> · OSM 署名见地图内</template>
          </div>
        </section>
      </div>

      <!-- 右栏 · 路段信息 -->
      <div class="td-col col-right td-scroll">
        <section class="td-card">
          <div class="td-card-head">
            路段信息<span class="td-head-tag td-mono">{{ selected?.segment_id ?? '—' }}</span>
          </div>
          <div class="td-card-body">
            <template v-if="selected">
              <div class="d-title">
                <span class="d-name">{{ selectedName }}</span>
                <LevelBadge :level="selected.level" :stale="isStale(selected)" />
              </div>
              <div class="d-summary">{{ detailSummary }}</div>

              <!-- 大号 CI + 四项加权构成(原 /heat 右栏;CI 只展示不判级) -->
              <div class="ci-head">
                <div class="idx-ci td-num" :style="{ color: ciTextColor }">{{ ciText }}</div>
                <div class="ci-side">
                  <div class="ci-label">拥挤指数 CI</div>
                  <div class="ci-sub">四项加权 {{ weightText }}</div>
                </div>
              </div>
              <div v-for="w in weights" :key="w.key" class="wt-row">
                <span class="wt-label">{{ w.label }}</span>
                <span class="wt-val td-mono">{{ metricText(w.key) }} × {{ w.weight.toFixed(2) }}</span>
              </div>

              <!-- TC-19:双数据源并排 -->
              <div class="sec-head">
                双数据源并排 · 同一路段 · 字段逐字一致(TC-19)
              </div>
              <table class="td-table tc19-table">
                <thead>
                  <tr>
                    <th>指标</th>
                    <th v-if="sourceMode !== 'twin'" class="c">视频链路</th>
                    <th v-if="sourceMode !== 'video'" class="c">孪生链路</th>
                    <th v-if="sourceMode === 'both'" class="c">差值</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="d in deltaRows" :key="d.key">
                    <td>{{ d.label }}</td>
                    <td v-if="sourceMode !== 'twin'" class="c td-num">{{ typeof d.video === 'number' ? d.video : '—' }}</td>
                    <td v-if="sourceMode !== 'video'" class="c td-num">{{ typeof d.twin === 'number' ? d.twin : '—' }}</td>
                    <td v-if="sourceMode === 'both'" class="c td-num">
                      {{ typeof d.delta === 'number' ? `${d.delta > 0 ? '+' : ''}${d.delta}` : '—' }}
                    </td>
                  </tr>
                </tbody>
              </table>
              <p v-if="pair && !videoAvailable" class="tc19-none">该路段无视频链路数据</p>
              <p class="tc19-note">
                视频链路 = 视频感知链路(YOLO 指标快照) · 孪生链路 = 虚拟检测器 ·
                差值 = 视频 − 孪生 · 一期均为示例数据
              </p>

              <!-- 当前生效因素(原 /heat 成因拆解口径) -->
              <div class="sec-head">
                当前生效因素<span class="sub-tag">{{ segFactors.length }} 项</span>
              </div>
              <FactorBreakdown :factors="segFactors" />

              <!-- CI 走势(原 /heat 右栏) -->
              <div class="sec-head">
                CI 走势 · 近 {{ history?.points.length ?? 12 }} 期<span class="sub-tag">阈值线 65 / 85</span>
              </div>
              <CiTrendBars :history="history" />

              <!-- 预测 -->
              <div class="sec-head">
                未来 15 / 30 分钟预测
                <span class="td-chip warn">L0 · 演示数据(模拟) · 不报精度</span>
              </div>
              <div v-if="selected.pred" class="pred-grid">
                <div class="pred-box">
                  <div class="pred-h">+15 min</div>
                  <div class="pred-v td-num">{{ selected.pred.h15.q_vph }} 辆/h</div>
                  <LevelBadge :level="selected.pred.h15.level" />
                </div>
                <div class="pred-box">
                  <div class="pred-h">+30 min</div>
                  <div class="pred-v td-num">{{ selected.pred.h30.q_vph }} 辆/h</div>
                  <LevelBadge :level="selected.pred.h30.level" />
                </div>
              </div>
              <p v-else class="empty">本路段无预测</p>

              <!-- 关联告警(原 /heat 右栏) -->
              <div class="sec-head">
                关联告警<span class="sub-tag">{{ selectedAlerts.length }} 条未闭环</span>
              </div>
              <AlertList :alerts="selectedAlerts" />

              <button class="td-btn primary act-btn" type="button" @click="gotoDecision">
                下发分流方案 ›
              </button>
            </template>
            <p v-else class="empty">点击左侧列表或地图中的路段查看详情</p>
          </div>
        </section>
      </div>
    </div>

    <!-- 底部热力带(原 /heat:档位分布 | 路段×时间热力矩阵 | CI 色阶与口径) -->
    <div class="heat-band">
      <section class="td-card band-card">
        <div class="td-card-head">
          档位分布 · 当前时刻<span class="td-head-tag">灰档 {{ unavailableCount }}</span>
        </div>
        <div class="td-card-body">
          <BandDistribution :rows="bandRows" :unavailable="unavailableCount" />
          <p class="note">共 {{ distTotal }} 个路段 · 灰档不计入均值,与地图同源</p>
        </div>
      </section>

      <section class="td-card band-card wide">
        <div class="td-card-head">
          路段 × 时间热力矩阵<span class="td-head-tag">最近 12 个快照 · 每 60 s 一档 · 左旧右新</span>
        </div>
        <div class="td-card-body flush">
          <HeatMatrixTable :matrix="heat" />
        </div>
      </section>

      <section class="td-card band-card">
        <div class="td-card-head">
          CI 色阶 · 展示档位<span class="td-head-tag td-mono">更新 {{ formatStamp(snapshotTs) }}</span>
        </div>
        <div class="td-card-body">
          <CiScale />
          <div class="gray-row">
            <i class="gray-swatch" />
            <span>灰档 = 数据不可用(缺 CI 或数据陈旧),绝不落进通配色</span>
          </div>
          <p class="note">{{ CI_BAND_NOTE }}</p>
        </div>
      </section>
    </div>

    <!-- 底部告警条 -->
    <div class="td-card alert-bar">
      <div class="alert-left">
        <span class="alert-icon" aria-hidden="true">▲</span>
        <span class="alert-title">
          待认领告警 · {{ firstAlert ? `${LEVELS[firstAlert.level].name}（${CN_NUM[firstAlert.level]}级）` : '—' }}
        </span>
        <span class="alert-summary">
          <template v-if="firstAlert">
            {{ firstAlert.alert_id }} {{ firstAlert.segment_name }} · x {{ firstAlertX }} ·
            首次观测 {{ hhmmss(firstAlert.first_seen) }} · 触发依据 {{ firstAlert.triggered_by.join(', ') }}
          </template>
          <template v-else>当前无待认领告警</template>
        </span>
      </div>
      <div class="alert-right">
        <span class="alert-counts">共 {{ unclaimedCount }} 条待认领 · {{ processingCount }} 条处置中</span>
        <RouterLink class="alert-link" to="/decision">前往决策层处置 ›</RouterLink>
      </div>
    </div>

    <template #foot>
      <span>快照时间 {{ formatStamp(snapshotTs) }}</span>
      <span>数据来源:mock 示例快照(契约 v2.0)· is_simulated = true · 底图:{{ sourceLabel }}</span>
      <span class="right">
        口径:一期全部示例数据(模拟)· 等级三重编码(颜色 + 竖条 + 文字)· 数据不可用灰显(TC-11)· {{ CI_DISCLAIMER }}
      </span>
    </template>
  </AppShell>
</template>

<style scoped>
/* 部分接口失败提示条:提醒当前页混装有上一版数据 */
.stale-bar {
  flex: 0 0 auto;
  margin: 10px 16px 0;
  padding: 6px 10px;
  font-size: 11px;
  line-height: 1.5;
  border-radius: var(--td-radius-sm);
  background: var(--td-warning-color-1);
  color: #a06a00;
}

/* ---------- KPI 条 ---------- */
.kpi-bar {
  flex: 0 0 auto;
  flex-direction: row;
  display: flex;
  margin: 12px 16px 10px;
}
.kpi-cell {
  flex: 1;
  min-width: 0;
  padding: 10px 14px;
  border-left: 1px solid var(--td-component-stroke);
}
.kpi-cell:first-child {
  border-left: none;
}
.kpi-label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}
.kpi-value {
  margin-top: 4px;
  font-size: 22px;
  font-weight: 700;
  line-height: 1.15;
  color: var(--td-text-color-primary);
}
.kpi-unit {
  margin-left: 5px;
  font-size: 12px;
  font-weight: 400;
  color: var(--td-text-color-placeholder);
}
.kpi-sub {
  margin-top: 3px;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.kpi-sep {
  color: var(--td-text-color-placeholder);
}

/* ---------- 三栏 ---------- */
.col-left {
  flex: 0 0 296px;
  overflow: hidden;
}
.col-mid {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
}
.col-right {
  flex: 0 0 396px;
}

/* ---------- 左栏 · 选择监控 ---------- */
.view-seg {
  width: 100%;
  margin-bottom: 10px;
}
.view-seg .td-seg-item {
  flex: 1;
  text-align: center;
}
.dist-bar {
  display: flex;
  height: 14px;
  border-radius: 3px;
  overflow: hidden;
}
.dist-seg {
  height: 100%;
  cursor: pointer;
}
.dist-seg.dim {
  opacity: 0.3;
}
.dist-legend {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
}
.dist-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 1px 4px;
  border-radius: var(--td-radius-sm);
  cursor: pointer;
}
.dist-item.on {
  background: var(--td-brand-color-1);
}
.dist-item.all {
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.dist-count {
  font-size: 12px;
  color: var(--td-text-color-primary);
}

/* ---------- 左栏 · 路段监测 ---------- */
.seg-card {
  flex: 1 1 auto;
  min-height: 0;
}
.seg-body {
  flex: 1;
  min-height: 0;
  display: flex;
}
.seg-list {
  flex: 1;
  min-height: 0;
}
.td-row {
  gap: 8px;
}
.lvl-bar {
  flex: 0 0 4px;
  align-self: stretch;
  min-height: 18px;
  border-radius: 2px;
}
.seg-meta {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
  flex: 1;
}
.seg-name {
  font-size: 13px;
  color: var(--td-text-color-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.seg-id {
  font-size: 10px;
  color: var(--td-text-color-placeholder);
}
.seg-value {
  font-size: 12px;
  white-space: nowrap;
}

/* ---------- 中栏地图 ---------- */
.map-card {
  flex: 1 1 auto;
  min-height: 0;
}
.map-body {
  flex: 1;
  min-height: 0;
}
.map-caption {
  flex: 0 0 auto;
  padding: 6px 12px;
  border-top: 1px solid var(--td-component-stroke);
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}

/* ---------- 右栏 · 路段信息 ---------- */
.d-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.d-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}
.d-summary {
  margin-top: 3px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
/* 大号 CI(原 /heat 右栏;CI 只展示不判级) */
.ci-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: var(--td-radius-sm);
  background: var(--td-bg-color-secondarycontainer);
}
.idx-ci {
  font-size: 30px;
  font-weight: 700;
  line-height: 1.1;
}
.ci-side {
  min-width: 0;
}
.ci-label {
  font-size: 12px;
  color: var(--td-text-color-primary);
}
.ci-sub {
  margin-top: 2px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.wt-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 3px 2px;
  font-size: 12px;
}
.wt-label {
  color: var(--td-text-color-secondary);
}
.wt-val {
  color: var(--td-text-color-primary);
}
.tc19-table th,
.tc19-table td {
  padding: 6px 8px;
}
.tc19-table th.c,
.tc19-table td.c {
  text-align: center;
}
.tc19-none {
  margin: 6px 0 0;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.tc19-note {
  margin: 6px 0 0;
  font-size: 10px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder);
}
.sec-head {
  margin: 12px 0 6px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
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
.pred-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.pred-box {
  padding: 8px 10px;
  border: 1px solid var(--td-component-stroke);
  border-radius: var(--td-radius-sm);
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.pred-h {
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.pred-v {
  font-size: 16px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}
.act-btn {
  margin-top: 12px;
  width: 100%;
  height: 34px;
  font-size: 13px;
}

/* ---------- 底部热力带(原 /heat 三栏内容) ---------- */
.heat-band {
  flex: 0 0 auto;
  display: flex;
  gap: 10px;
  margin: 0 16px 8px;
}
.band-card {
  flex: 0 0 240px;
  min-height: 0;
}
.band-card.wide {
  flex: 1 1 auto;
  min-width: 0;
}
.band-card .td-card-body {
  max-height: 176px;
  overflow: hidden;
}
.gray-swatch {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 2px;
  background: #8b8b8b;
  flex: 0 0 auto;
}
.gray-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.note {
  margin: 6px 0 0;
  font-size: 10px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder);
}

/* ---------- 底部告警条 ---------- */
.alert-bar {
  flex: 0 0 auto;
  flex-direction: row;
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 16px 8px;
  padding: 8px 12px;
}
.alert-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.alert-icon {
  color: var(--td-error-color);
  font-size: 11px;
}
.alert-title {
  color: var(--td-error-color);
  font-weight: 500;
  font-size: 12px;
  white-space: nowrap;
}
.alert-summary {
  font-size: 11px;
  color: var(--td-text-color-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.alert-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
  white-space: nowrap;
}
.alert-counts {
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.alert-link {
  font-size: 12px;
  color: var(--td-brand-color);
  text-decoration: none;
  font-weight: 500;
}
.alert-link:hover {
  text-decoration: underline;
}

.empty {
  margin: 8px 2px;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}
</style>
