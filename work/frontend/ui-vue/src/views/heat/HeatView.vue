<script setup lang="ts">
// 拥挤度热力(Issue #78 四页重做 · 设计稿 02,TDesign Light):
//   左栏 = CI 色阶 / 路段指数排行 / 档位分布;中栏 = 路网拥挤指数热力 + 时段热力矩阵;
//   右栏 = 路段指数明细(大号 CI + 四项加权 + 走势 + 成因 + 关联告警)。
// 硬口径(手册 §6.5 第 1 条):CI 只用于热力展示与辅助排序,不得作为判级依据;
//   页脚 / 图例 / 列表三处标注;视图切换同页互证,冲突以四级为准。
// 数据:接口面(只读快照)+ SSE traffic_snapshot;一期全部 is_simulated=true,不出现"实时/实测"。
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppShell from '../../components/AppShell.vue'
import NetMap from '../dashboard/components/NetMap.vue'
import {
  getTrafficAlerts,
  getTrafficCiHistory,
  getTrafficFactors,
  getTrafficHeatMatrix,
  getTrafficMeta,
  getTrafficNetwork,
  getTrafficOverview,
  getTrafficSegments,
  getTrafficThresholds,
  getTrafficVehicles,
  subscribeTrafficSnapshot,
} from '../../api/traffic'
import { activePack } from '../../station-packs/index'
import {
  CI_BANDS,
  CI_BAND_NOTE,
  CI_DISCLAIMER,
  LEVELS,
  ciAvailable,
  formatStamp,
  isStale,
  type CiHistory,
  type CongestionLevel,
  type CongestionViewMode,
  type FactorApplied,
  type HeatMatrix,
  type SegmentRecord,
  type ThresholdSnapshot,
  type TrafficAlert,
  type TrafficNetwork,
  type TrafficOverview,
  type VehicleRecord,
} from '../../shared/traffic'
import BandDistribution from './components/BandDistribution.vue'
import CiScale from './components/CiScale.vue'
import HeatMatrixTable from './components/HeatMatrixTable.vue'
import SegmentIndexPanel from './components/SegmentIndexPanel.vue'
import SegmentRankTable from './components/SegmentRankTable.vue'

const router = useRouter()

// ---- 状态 ----
const viewMode = ref<CongestionViewMode>('index')
const segments = ref<SegmentRecord[]>([])
const vehicles = ref<VehicleRecord[]>([])
const network = ref<TrafficNetwork | null>(null)
const heat = ref<HeatMatrix | null>(null)
const thresholds = ref<ThresholdSnapshot | null>(null)
const overview = ref<TrafficOverview | null>(null)
const alerts = ref<TrafficAlert[]>([])
const history = ref<CiHistory | null>(null)
const factors = ref<(FactorApplied & { segment_id: string })[]>([])
const selectedId = ref<string | null>(null)
const snapshotTs = ref('')
// 站点名初始值取当前站点包;拿到 meta 后由 meta.station.name 覆盖(单一口径)
const stationName = ref(activePack().station.name)

let unsubscribe: (() => void) | null = null

/** 默认选中:CI 最高的可用路段(不可用路段不参与) */
function pickDefault(list: SegmentRecord[]): string | null {
  const best = [...list].filter(ciAvailable).sort((a, b) => (b.ci ?? 0) - (a.ci ?? 0))[0]
  return best?.segment_id ?? list[0]?.segment_id ?? null
}

/** 选中路段派生数据(CI 走势 / 生效因素) */
async function loadDerived(id: string | null): Promise<void> {
  if (!id) {
    history.value = null
    factors.value = []
    return
  }
  const [h, f] = await Promise.allSettled([getTrafficCiHistory(id, 12), getTrafficFactors(id)])
  if (selectedId.value !== id) return // 选择已变:丢弃过期响应
  if (h.status === 'fulfilled') history.value = h.value
  if (f.status === 'fulfilled') factors.value = f.value.factors
}

/** 刷新序号:SSE 触发与手动刷新可能并发,只让最后一次的响应落页(旧响应丢弃) */
let refreshSeq = 0
/** 本次刷新中失败的接口(页头提示用;失败面板保留旧值但必须标"上一版") */
const failedPanels = ref<string[]>([])

const PANEL_LABEL: Record<string, string> = {
  segments: '路段快照',
  vehicles: '车辆',
  network: '路网',
  meta: '站点元信息',
  thresholds: '阈值与 CI 权重',
  alerts: '告警',
  matrix: '热力矩阵',
  overview: 'KPI',
}

async function refresh(): Promise<void> {
  const seq = ++refreshSeq
  const [seg, veh, net, meta, thr, alert, matrix, over] = await Promise.allSettled([
    getTrafficSegments(),
    getTrafficVehicles(),
    getTrafficNetwork(),
    getTrafficMeta(),
    getTrafficThresholds(),
    getTrafficAlerts(),
    getTrafficHeatMatrix(12, 60),
    getTrafficOverview(),
  ])
  if (seq !== refreshSeq) return // 已被更晚的一次刷新取代:丢弃本次响应
  const failed: string[] = []
  const track = (name: string, ok: boolean): void => {
    if (!ok) failed.push(PANEL_LABEL[name] ?? name)
  }
  if (seg.status === 'fulfilled') {
    segments.value = seg.value.segments
    snapshotTs.value = seg.value.ts
    if (selectedId.value === null) selectedId.value = pickDefault(seg.value.segments)
  }
  track('segments', seg.status === 'fulfilled')
  if (veh.status === 'fulfilled') vehicles.value = veh.value.vehicles
  track('vehicles', veh.status === 'fulfilled')
  if (net.status === 'fulfilled') network.value = net.value
  track('network', net.status === 'fulfilled')
  if (meta.status === 'fulfilled') stationName.value = meta.value.station.name
  track('meta', meta.status === 'fulfilled')
  if (thr.status === 'fulfilled') thresholds.value = thr.value
  track('thresholds', thr.status === 'fulfilled')
  if (alert.status === 'fulfilled') alerts.value = alert.value.alerts
  track('alerts', alert.status === 'fulfilled')
  if (matrix.status === 'fulfilled') heat.value = matrix.value
  track('matrix', matrix.status === 'fulfilled')
  if (over.status === 'fulfilled') overview.value = over.value
  track('overview', over.status === 'fulfilled')
  failedPanels.value = failed
  await loadDerived(selectedId.value)
}

onMounted(() => {
  void refresh()
  unsubscribe = subscribeTrafficSnapshot(
    () => {
      void refresh()
    },
    () => {
      /* 连接态由顶栏角标承担,本页无额外展示 */
    },
  )
})

onUnmounted(() => {
  unsubscribe?.()
})

watch(selectedId, (id) => {
  void loadDerived(id)
})

// ---- 名称映射(路段名从路网 / 热力矩阵取,记录本身不含 name) ----
const nameById = computed(() => {
  const m = new Map<string, string>()
  for (const r of heat.value?.rows ?? []) m.set(r.segment_id, r.name)
  for (const s of network.value?.segments ?? []) m.set(s.segment_id, s.name)
  return m
})

function nameOf(id: string): string {
  return nameById.value.get(id) ?? id
}

// ---- 选中路段 ----
const selected = computed<SegmentRecord | null>(
  () => segments.value.find((s) => s.segment_id === selectedId.value) ?? null,
)
const selectedName = computed(() => (selectedId.value ? nameOf(selectedId.value) : '—'))

const selectedChip = computed(() => {
  const s = selected.value
  if (!s) return ''
  return ciAvailable(s) ? `${selectedName.value} · CI ${(s.ci as number).toFixed(1)}` : `${selectedName.value} · 数据不可用`
})

/**
 * 关联告警的等级一律按**当前路段快照**上屏(与右侧指数明细同一口径)——
 * 告警自带的 level 是派生时的记录值,预置剧本与快照基线不同步时会是旧值,
 * 直接用就会出现"同一路段、两个等级"。
 */
const selectedAlerts = computed(() =>
  alerts.value
    .filter((a) => a.segment_id === selectedId.value && a.status !== '已闭环' && a.status !== '误报')
    .map((a) => ({ ...a, level: selected.value?.level ?? a.level })),
)

// ---- 左栏:路段指数排行(可用者按 CI 降序,不可用排最后) ----
const rankRows = computed(() =>
  segments.value
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

// ---- 左栏:档位分布(按 CI_BANDS 四档 + 不可用单独成档) ----
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
const totalSegments = computed(() => overview.value?.segment_total ?? segments.value.length)

// ---- 右栏:数据不可用路段清单 ----
const unavailableRows = computed(() =>
  segments.value
    .filter((s) => !ciAvailable(s))
    .map((s) => ({
      id: s.segment_id,
      name: nameOf(s.segment_id),
      reason: isStale(s) ? '数据陈旧' : '缺 CI',
      ageText: typeof s.data_age_s === 'number' ? `${s.data_age_s}s` : '—',
      confidence: typeof s.confidence === 'number' ? s.confidence.toFixed(2) : '—',
    })),
)

// ---- 右栏:四个 CI 权重(来自 thresholds,不写死) ----
const weights = computed(() => thresholds.value?.ci_weights ?? [])
const weightText = computed(() => (weights.value.length > 0 ? weights.value.map((w) => w.weight.toFixed(2)).join('/') : '—'))

function goDecision(): void {
  void router.push('/decision')
}
</script>

<template>
  <AppShell
    active="heat"
    :station="stationName"
    :ts="snapshotTs"
    title="拥挤度热力"
    subtitle="强度晕染随 CI 单调增 · 不做断面间无标注内插"
  >
    <template #headRight>
      <span class="td-seg" role="group" aria-label="视图切换">
        <span
          class="td-seg-item"
          :class="{ on: viewMode === 'level' }"
          :aria-pressed="viewMode === 'level'"
          role="button"
          @click="viewMode = 'level'"
        >
          四级视图
        </span>
        <span
          class="td-seg-item"
          :class="{ on: viewMode === 'index' }"
          :aria-pressed="viewMode === 'index'"
          role="button"
          @click="viewMode = 'index'"
        >
          拥挤指数视图
        </span>
      </span>
      <span class="head-ts td-mono">快照 {{ formatStamp(snapshotTs) }}</span>
    </template>

    <template #headExtra>
      <div v-if="failedPanels.length > 0" class="head-err">
        ⚠ 本次刷新未取到:{{ failedPanels.join(' / ') }} —— 这些面板显示的是上一版数据,请勿据此判断当前态势。
      </div>
    </template>

    <div class="td-body">
      <!-- 左栏 -->
      <section class="td-col col-left td-scroll">
        <div class="td-card">
          <div class="td-card-head">CI 色阶 · 展示档位</div>
          <div class="td-card-body">
            <CiScale />
            <div class="gray-row">
              <i class="gray-swatch" />
              <span>灰档 = 数据不可用(缺 CI 或数据陈旧),绝不落进通配色</span>
            </div>
            <p class="note">{{ CI_DISCLAIMER }}</p>
            <p class="note">{{ CI_BAND_NOTE }}</p>
          </div>
        </div>

        <div class="td-card">
          <div class="td-card-head">路段指数排行<span class="td-head-tag">按 CI 降序</span></div>
          <div class="td-card-body flush">
            <SegmentRankTable :items="rankRows" :selected-id="selectedId" @select="selectedId = $event" />
          </div>
        </div>

        <div class="td-card">
          <div class="td-card-head">档位分布 · 当前时刻</div>
          <div class="td-card-body">
            <BandDistribution :rows="bandRows" :unavailable="unavailableCount" />
            <p class="note">共 {{ totalSegments }} 个路段 · 灰档不计入均值,与地图同源</p>
          </div>
        </div>
      </section>

      <!-- 中栏 -->
      <section class="td-col col-mid td-scroll">
        <div class="td-card">
          <div class="td-card-head">拥挤度热力 · 强度晕染随 CI 单调增 · 不做断面间无标注内插</div>
          <div class="td-card-body flush">
            <div class="map-wrap">
              <NetMap
                :segments="segments"
                :vehicles="vehicles"
                :selected-id="selectedId"
                :route-segments="[]"
                :mode="viewMode"
                :ts="snapshotTs"
                :sections="network?.sections ?? []"
                :dropoffs="network?.dropoffs ?? []"
                :zones="network?.zones ?? []"
                :stations="network?.stations ?? []"
                :selected-chip="selectedChip"
                :legend="false"
                @select="selectedId = $event"
              />
            </div>
            <div class="map-legend">
              <CiScale />
              <div class="legend-notes">
                <span class="legend-ts td-mono">更新 {{ formatStamp(snapshotTs) }}</span>
                <span class="legend-gray"><i class="gray-swatch" />灰 = 数据不可用</span>
                <span>{{ CI_DISCLAIMER }}</span>
                <span>{{ CI_BAND_NOTE }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="td-card">
          <div class="td-card-head">
            路段 × 时间热力矩阵<span class="td-head-tag">最近 12 个快照 · 每 60 s 一档 · 左旧右新</span>
          </div>
          <div class="td-card-body flush">
            <HeatMatrixTable :matrix="heat" />
          </div>
        </div>
      </section>

      <!-- 右栏 -->
      <section class="td-col col-right td-scroll">
        <SegmentIndexPanel
          :record="selected"
          :name="selectedName"
          :weights="weights"
          :weight-text="weightText"
          :history="history"
          :factors="factors"
          :alerts="selectedAlerts"
          :unavailable="unavailableRows"
          @goto-decision="goDecision"
        />
      </section>
    </div>

    <template #foot>
      <span>快照时间 {{ formatStamp(snapshotTs) }}</span>
      <span>{{ CI_DISCLAIMER }}</span>
      <span class="right">口径:CI 图例见地图下方 · 两种视图同页互证,冲突以四级为准 · 示例数据(is_simulated)</span>
    </template>
  </AppShell>
</template>

<style scoped>
/* 部分接口失败提示:提醒当前页混装有上一版数据 */
.head-err {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.5;
  color: #a06a00;
}
.col-left {
  flex: 0 0 292px;
}
.col-mid {
  flex: 1 1 auto;
  min-width: 0;
}
.col-right {
  flex: 0 0 372px;
}
.head-ts {
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
/* 数据不可用灰(非等级色) */
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
.map-wrap {
  height: 360px;
}
.map-legend {
  padding: 8px 12px 10px;
  border-top: 1px solid var(--td-component-stroke);
}
.legend-notes {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 14px;
  margin-top: 6px;
  font-size: 10px;
  color: var(--td-text-color-placeholder);
}
.legend-ts {
  color: var(--td-text-color-secondary);
}
.legend-gray {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
</style>
