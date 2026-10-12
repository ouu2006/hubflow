<script setup lang="ts">
// 态势总览(Issue #78 四页重做 · 设计稿 01),TDesign Light:
//   顶栏(壳层) → KPI 条(4 格)→ 三栏(左:等级分布 + 路段监测;中:路网图;右:路段详情 / 双源并排 / 因素 / 预测 / 下发)
//   → 底部告警条 → 页脚口径条。
// 数据:全部走只读快照接口(src/api/traffic.ts 的 Issue #78 接口面),不做任何业务计算。
// 口径铁律:
//   ① 一期全部 is_simulated=true 示例数据,页面不出现「实时 / 实测 / 现场」表述;
//   ② 三重编码(颜色 + 竖条图标 + 文字)由 LevelBadge 保证;
//   ③ 数据不可用(缺字段或 data_age_s > 120s)恒为灰 + 「不可用」文字分支(TC-11),绝不显示成蓝/绿;
//   ④ 品牌蓝只用于「当前 / 已选 / 可操作」(选中行、选中路段、主按钮、当前页签),等级色只表示路况等级;
//   ⑤ 不做 3D、不做无标注内插;所有数字带单位或口径标注,空值一律「—」,不编造。
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  getTrafficAlerts,
  getTrafficFactors,
  getTrafficNetwork,
  getTrafficOverview,
  getTrafficSegmentSources,
  getTrafficSegments,
  getTrafficVehicles,
  subscribeTrafficSnapshot,
} from '../../api/traffic'
import { demoSegment, networkSourceLabel } from '../../shared/demoNetwork'
import type { SourceMode } from '../../shared/nav'
import { TD } from '../../shared/theme'
import {
  isStale,
  LEVELS,
  levelStyle,
  UNAVAILABLE,
  formatStamp,
  type CongestionLevel,
  type FactorApplied,
  type SegmentRecord,
  type SegmentSourcePair,
  type TrafficAlert,
  type TrafficNetwork,
  type TrafficOverview,
  type VehicleRecord,
} from '../../shared/traffic'
import AppShell from '../../components/AppShell.vue'
import LevelBadge from './components/LevelBadge.vue'
import NetMap from './components/NetMap.vue'

const router = useRouter()
const sourceLabel = networkSourceLabel()

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

const selectedId = ref<string | null>(null)
const sourceMode = ref<SourceMode>('both')
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

/** 选中路段相关的两个接口(并排表 + 因素);选中变化与快照刷新都会重拉 */
async function loadSelectedSide(segmentId: string | null): Promise<void> {
  if (!segmentId) {
    pair.value = null
    segFactors.value = []
    return
  }
  const [p, f] = await Promise.allSettled([
    getTrafficSegmentSources(segmentId),
    getTrafficFactors(segmentId),
  ])
  pair.value = p.status === 'fulfilled' ? p.value : null
  segFactors.value = f.status === 'fulfilled' ? f.value.factors : []
}

async function refresh(): Promise<void> {
  const [ov, seg, veh, net, al, fa] = await Promise.allSettled([
    getTrafficOverview(),
    getTrafficSegments(),
    getTrafficVehicles(),
    getTrafficNetwork(),
    getTrafficAlerts(),
    getTrafficFactors(),
  ])
  if (ov.status === 'fulfilled') overview.value = ov.value
  if (seg.status === 'fulfilled') {
    segments.value = seg.value.segments
    snapshotTs.value = seg.value.ts
    if (selectedId.value === null) selectedId.value = pickDefaultId(seg.value.segments)
  }
  if (veh.status === 'fulfilled') vehicles.value = veh.value.vehicles
  if (net.status === 'fulfilled') network.value = net.value
  if (al.status === 'fulfilled') alerts.value = al.value.alerts
  if (fa.status === 'fulfilled') allFactors.value = fa.value.factors
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

/** 因素作用对象 → 中文(与 SegmentDetailPanel 同口径) */
const TARGET_LABEL: Record<string, string> = {
  c: '通行能力',
  v_f: '畅通速度',
  demand: '需求',
  lanes: '车道数',
  confidence: '检测置信度',
}

/** 倍率显示:×0.75 / ×1.25 */
function multText(m: number): string {
  return `×${Number.isFinite(m) ? Number(m.toFixed(2)) : '—'}`
}

/** ISO → 'HH:mm'(生效至 / 首次观测时分) */
function hhmm(iso: string): string {
  return iso.length >= 16 ? iso.slice(11, 16) : iso
}

/** '2026-10-12 12:38:20' → '12:38:20' */
function hhmmss(stamp: string): string {
  return stamp.length >= 8 ? stamp.slice(-8) : stamp
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

// ---------- 左栏 · 等级分布 ----------
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

// ---------- 左栏 · 路段监测 ----------
interface SegRow {
  seg: SegmentRecord
  color: string
  text: string
  stale: boolean
  name: string
}

const segRows = computed<SegRow[]>(() =>
  segments.value.map((seg) => {
    const st = levelStyle(seg)
    return {
      seg,
      color: st.color,
      text: st.text,
      stale: isStale(seg),
      name: demoSegment(seg.segment_id)?.name ?? seg.segment_id,
    }
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

// ---------- 右栏 · 路段详情摘要 ----------
const detailSummary = computed<string>(() => {
  const s = selected.value
  if (!s) return ''
  const parts = [`${CN_NUM[s.level]}级`, levelName(s)]
  parts.push(`更新 ${s.data_age_s ?? '—'}s 前`)
  parts.push(`饱和度 ${fmt(s.x)}`)
  if (s.triggered_by && s.triggered_by.length > 0) parts.push(`触发 ${s.triggered_by.join(' / ')}`)
  return parts.join(' · ')
})

// ---------- 底部告警条 ----------
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
  <AppShell active="dashboard" :ts="snapshotTs" v-model:sourceMode="sourceMode" title="">
    <!-- KPI 条(取代态势总览的页头) -->
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
      <!-- 左栏 -->
      <div class="td-col col-left">
        <section class="td-card">
          <div class="td-card-head">
            等级分布<span class="td-head-tag">{{ distTotal }} 个路段</span>
          </div>
          <div class="td-card-body">
            <div class="dist-bar" :style="{ background: TD.bgSecondary }">
              <span
                v-for="r in dist"
                :key="`d-${r.level}`"
                class="dist-seg"
                :style="{ width: distWidth(r), background: r.color }"
                :title="`${r.name} ${r.count} 个路段`"
              />
            </div>
            <div class="dist-legend">
              <span v-for="r in dist" :key="`lg-${r.level}`" class="dist-item">
                <LevelBadge :level="r.level === 0 ? 1 : r.level" :stale="r.level === 0" />
                <span class="td-num dist-count">{{ r.count }}</span>
              </span>
            </div>
          </div>
        </section>

        <section class="td-card seg-card">
          <div class="td-card-head">
            路段监测<span class="td-head-tag">按等级排序</span>
          </div>
          <div class="td-card-body flush seg-body">
            <div class="td-scroll seg-list">
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
              <p v-if="segRows.length === 0" class="empty">快照为空(接口层未起?)</p>
            </div>
          </div>
        </section>
      </div>

      <!-- 中栏 -->
      <div class="td-col col-mid">
        <section class="td-card map-card">
          <div class="td-card-body flush map-body">
            <NetMap
              :segments="segments"
              :vehicles="vehicles"
              :selected-id="selectedId"
              :route-segments="[]"
              mode="level"
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
            底图来源:{{ sourceLabel }} · 路网为示例样例(非实测) · OSM 署名见地图内
          </div>
        </section>
      </div>

      <!-- 右栏 -->
      <div class="td-col col-right">
        <section class="td-card">
          <div class="td-card-head">
            路段详情<span class="td-head-tag td-mono">{{ selected?.segment_id ?? '—' }}</span>
          </div>
          <div class="td-card-body">
            <template v-if="selected">
              <div class="d-title">
                <span class="d-name">{{ selectedName }}</span>
                <LevelBadge :level="selected.level" :stale="isStale(selected)" />
              </div>
              <div class="d-summary">{{ detailSummary }}</div>

              <!-- TC-19:双数据源并排 -->
              <div class="tc19-label">双数据源并排 · 同一路段 · 字段逐字一致(TC-19)</div>
              <table class="td-table tc19-table">
                <thead>
                  <tr>
                    <th>指标</th>
                    <th class="c">视频链路</th>
                    <th class="c">孪生链路</th>
                    <th class="c">差值</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="d in deltaRows" :key="d.key">
                    <td>{{ d.label }}</td>
                    <td class="c td-num">{{ typeof d.video === 'number' ? d.video : '—' }}</td>
                    <td class="c td-num">{{ typeof d.twin === 'number' ? d.twin : '—' }}</td>
                    <td class="c td-num">{{ typeof d.delta === 'number' ? `${d.delta > 0 ? '+' : ''}${d.delta}` : '—' }}</td>
                  </tr>
                </tbody>
              </table>
              <p v-if="pair && !videoAvailable" class="tc19-none">该路段无视频链路数据</p>
              <p class="tc19-note">
                视频链路 = 视频感知链路(YOLO 指标快照) · 孪生链路 = 虚拟检测器 ·
                差值 = 视频 − 孪生 · 一期均为示例数据
              </p>

              <!-- 当前生效因素 -->
              <div class="sec-head">当前生效因素 · {{ segFactors.length }} 项</div>
              <template v-if="segFactors.length > 0">
                <div v-for="f in segFactors" :key="f.factor_id" class="factor-row">
                  {{ f.factor_id }} {{ f.name }}
                  <span class="dot-sep">·</span>倍率 {{ multText(f.multiplier) }}
                  <span class="dot-sep">·</span>作用{{ TARGET_LABEL[f.target] ?? f.target }} {{ f.target }}
                  <span class="dot-sep">·</span>至 {{ hhmm(f.until) }}
                </div>
              </template>
              <p v-else class="empty">本路段无生效因素</p>

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

              <button class="td-btn primary act-btn" type="button" @click="gotoDecision">
                下发分流方案 ›
              </button>
            </template>
            <p v-else class="empty">点击左侧列表或地图中的路段查看详情</p>
          </div>
        </section>
      </div>
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
        <RouterLink class="alert-link" to="/decision">前往决策工作台处置 ›</RouterLink>
      </div>
    </div>

    <template #foot>
      <span>快照时间 {{ formatStamp(snapshotTs) }}</span>
      <span>数据来源:mock 示例快照(契约 v2.0)· is_simulated = true · 底图:{{ sourceLabel }}</span>
      <span class="right">口径:一期全部示例数据(模拟)· 等级三重编码(颜色 + 竖条 + 文字)· 数据不可用灰显(TC-11)</span>
    </template>
  </AppShell>
</template>

<style scoped>
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
  flex: 0 0 372px;
}

/* ---------- 等级分布 ---------- */
.dist-bar {
  display: flex;
  height: 14px;
  border-radius: 3px;
  overflow: hidden;
}
.dist-seg {
  height: 100%;
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
}
.dist-count {
  font-size: 12px;
  color: var(--td-text-color-primary);
}

/* ---------- 路段监测 ---------- */
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

/* ---------- 右栏 · 详情 ---------- */
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
.tc19-label {
  margin: 12px 0 6px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
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
.factor-row {
  padding: 6px 9px;
  margin-bottom: 5px;
  border: 1px solid var(--td-component-stroke);
  border-radius: var(--td-radius-sm);
  background: var(--td-bg-color-secondarycontainer);
  font-size: 11px;
  color: var(--td-text-color-primary);
}
.factor-row:last-child {
  margin-bottom: 0;
}
.dot-sep {
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
