<script setup lang="ts">
// 中央路网图:零依赖 SVG 渲染(TDesign Light,2026-10-12 配色切换)。
//   mode = 'level' → 四级染色(判级产出);mode = 'index' → 拥挤指数色阶(ci,仅展示)。
// 叠加层:站点块 / 场区(虚线框)/ 断面标记(边界·内部)/ 落客点 / 孪生车辆动点 / 路线高亮。
// 底图数据 = 示例路网(非实测,#36/#37 站点包落地后替换;真路网时触发 OSM 署名)。
// 语义纪律:品牌蓝只画"当前/已选/推荐路线";路段色只表示等级;数据不可用一律灰。
import { computed } from 'vue'
import {
  DEMO_NETWORK,
  isOsmNetwork,
  networkSourceLabel,
  OSM_ATTRIBUTION,
  OSM_COPYRIGHT_URL,
  type DemoSegment,
} from '../../../shared/demoNetwork'
import { DRIVER_COLORS, TD } from '../../../shared/theme'
import {
  ciAvailable,
  ciGradientCss,
  ciStyleColor,
  CI_BAND_NOTE,
  CI_BANDS,
  CI_DISCLAIMER,
  CI_MAX,
  levelStyle,
  UNAVAILABLE,
  type CongestionViewMode,
  type DriverType,
  type NetworkLandmark,
  type NetworkSection,
  type SegmentRecord,
  type VehicleRecord,
} from '../../../shared/traffic'
import LevelBadge from './LevelBadge.vue'

const UNAVAILABLE_COLOR = UNAVAILABLE.color
const BRAND = TD.brand

/** 'level' = 四级视图(默认) · 'index' = 拥挤指数视图 */
type MapMode = CongestionViewMode

const props = withDefaults(
  defineProps<{
    segments: SegmentRecord[]
    vehicles: VehicleRecord[]
    selectedId: string | null
    /** 当前高亮路线包含的路段 id(推荐/备选/离站) */
    routeSegments: string[]
    mode?: MapMode
    /** 快照时间(热力视图的"更新时间戳",手册 §11.2 必现) */
    ts?: string
    /** 断面标记(边界断面允许回灌 / 内部断面禁止) */
    sections?: NetworkSection[]
    /** 落客点 */
    dropoffs?: NetworkLandmark[]
    /** 场区(车辆候客区 / 社会停车场) */
    zones?: NetworkLandmark[]
    /** 站点 */
    stations?: NetworkLandmark[]
    /** 选中所属来源标签(选中 chip 上的 x / 双源值;缺省不画 chip) */
    selectedChip?: string
    /** 紧凑图例(右栏无独立图例时用) */
    legend?: boolean
  }>(),
  {
    mode: 'level',
    ts: '',
    sections: () => [],
    dropoffs: () => [],
    zones: () => [],
    stations: () => [],
    selectedChip: '',
    legend: true,
  },
)

const emit = defineEmits<{ (e: 'select', segmentId: string): void }>()

/** hover 即切换选中(业主 2026-10-14:不要"靠点击才切换");点击仍保留同一行为 */
function hoverSelect(seg: DemoSegment): void {
  emit('select', seg.segment_id)
}

// ---- 投影:经纬度 → SVG 用户坐标(等距圆柱近似,经度按 cos(纬度) 修正) ----

const W = 1100
const H = 680
const PAD = 62

const net = DEMO_NETWORK.segments
const sourceLabel = networkSourceLabel()

const allLon = [...net.flatMap((s) => s.coords.map((c) => c[0]))]
const allLat = [...net.flatMap((s) => s.coords.map((c) => c[1]))]
const minLon = Math.min(...allLon)
const maxLat = Math.max(...allLat)
const minLat = Math.min(...allLat)
const cosLat = Math.cos((((minLat + maxLat) / 2) * Math.PI) / 180)

const rawW = (Math.max(...allLon) - minLon) * cosLat
const rawH = maxLat - minLat
const SCALE = Math.min((W - PAD * 2) / Math.max(rawW, 1e-6), (H - PAD * 2) / Math.max(rawH, 1e-6))
const OFF_X = (W - rawW * SCALE) / 2
const OFF_Y = (H - rawH * SCALE) / 2

function px(lon: number, lat: number): [number, number] {
  return [OFF_X + (lon - minLon) * cosLat * SCALE, OFF_Y + (maxLat - lat) * SCALE]
}

function pointsFor(seg: DemoSegment): string {
  return seg.coords.map(([lon, lat]) => px(lon, lat).join(',')).join(' ')
}

// ---- 路段染色(两种视图模式) ----

const segById = computed(() => new Map(props.segments.map((s) => [s.segment_id, s])))

const isIndex = computed(() => props.mode === 'index')

function recOf(seg: DemoSegment): SegmentRecord | undefined {
  return segById.value.get(seg.segment_id)
}

/** 路段色:四级视图取判级色;拥挤指数视图取 ci 色阶;无记录/不可用一律灰(数据不可用) */
function colorOf(seg: DemoSegment): string {
  const rec = recOf(seg)
  if (!rec) return UNAVAILABLE_COLOR
  return isIndex.value ? ciStyleColor(rec) : levelStyle(rec).color
}

/** 热力晕染:仅指数视图且 ci 可用时渲染,强度随 ci 单调增(不改任何判级着色) */
function heatOpacity(seg: DemoSegment): number {
  const rec = recOf(seg)
  if (!rec || !ciAvailable(rec)) return 0
  const v = Math.min(CI_MAX, Math.max(0, rec.ci as number))
  return Math.round((0.1 + (v / CI_MAX) * 0.5) * 100) / 100
}

function heatWidth(seg: DemoSegment): number {
  return seg.kind === 'main' ? 26 : 22
}

function baseWidth(seg: DemoSegment): number {
  // 车道级渲染：路幅宽度按车道模型取值(双车道比单车道宽)
  return seg.kind === 'main' ? 18 : 14
}

function casingWidth(seg: DemoSegment): number {
  return baseWidth(seg) + 6
}

const osmActive = computed(() => isOsmNetwork())

// ---- 路线高亮 ----

const routeSet = computed(() => new Set(props.routeSegments))

// ---- 车辆动点 ----

const VEH_LABEL: Record<DriverType, string> = {
  D1: '送客车辆',
  D2: '接客车辆',
  D3: '往返车辆(出租车 / 网约车)',
}

// 图例**由 DRIVER_COLORS 生成**,不手写行——否则新增司机类型时地图画了、图例却漏
const VEH_LEGEND = (Object.keys(DRIVER_COLORS) as DriverType[]).map((t) => ({
  t,
  color: DRIVER_COLORS[t],
  label: VEH_LABEL[t],
}))

const vehPts = computed(() =>
  props.vehicles.map((v) => {
    const [x, y] = px(v.lon, v.lat)
    return { ...v, x, y }
  }),
)
</script>

<template>
  <div class="netmap">
    <svg :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="xMidYMid meet" role="img" aria-label="路网态势图">
      <!-- 底:浅灰画布 -->
      <rect :x="0" :y="0" :width="W" :height="H" :fill="'#F7F8FA'" />

      <!-- 路基描边(白色底衬,让彩色路段在浅底上分离) -->
      <g v-for="s in net" :key="`casing-${s.segment_id}`">
        <polyline
          :points="pointsFor(s)"
          fill="none"
          stroke="#FFFFFF"
          :stroke-width="casingWidth(s)"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </g>

      <!-- 路段:四级染色 + 路线高亮 + 选中描边(hover 即切换选中,业主 2026-10-14) -->
      <g
        v-for="s in net"
        :key="`road-${s.segment_id}`"
        class="road"
        @mouseenter="hoverSelect(s)"
        @click="emit('select', s.segment_id)"
      >
        <!-- 热力晕染(仅拥挤指数视图):强度随 ci 单调增,不改变任何路段的判级着色 -->
        <polyline
          v-if="isIndex && heatOpacity(s) > 0"
          class="heat"
          :points="pointsFor(s)"
          fill="none"
          :stroke="colorOf(s)"
          :stroke-width="heatWidth(s)"
          :style="{ opacity: heatOpacity(s) }"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <polyline
          :points="pointsFor(s)"
          fill="none"
          :stroke="colorOf(s)"
          :stroke-width="baseWidth(s)"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <!-- 路线高亮:品牌蓝(「已选/推荐」语义,不得用等级色) -->
        <template v-if="routeSet.has(s.segment_id)">
          <polyline
            :points="pointsFor(s)"
            fill="none"
            :stroke="BRAND"
            stroke-width="17"
            opacity="0.16"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <polyline
            class="flowline"
            :points="pointsFor(s)"
            fill="none"
            :stroke="BRAND"
            stroke-width="3"
            stroke-linecap="round"
            stroke-dasharray="14 10"
          />
        </template>
        <polyline
          v-if="props.selectedId === s.segment_id"
          :points="pointsFor(s)"
          fill="none"
          :stroke="BRAND"
          stroke-width="2.4"
          stroke-dasharray="4 6"
          stroke-linecap="round"
        />
      </g>

      <!-- 孪生车辆动点(位置随快照刷新平滑移动) -->
      <g
        v-for="v in vehPts"
        :key="v.vehicle_id"
        class="veh"
        :style="{ transform: `translate(${v.x}px, ${v.y}px)` }"
      >
        <circle r="5.5" :fill="DRIVER_COLORS[v.driver_type]" fill-opacity="1" stroke="#FFFFFF" stroke-width="1.6" />
        <title>{{ v.vehicle_id }} · {{ v.state }} · {{ v.segment_id }}{{ v.is_demo_bound ? ' · 演示绑定车' : '' }}</title>
      </g>
    </svg>

    <div class="watermark">{{ sourceLabel }}</div>

    <div v-if="osmActive" class="attribution">
      <a :href="OSM_COPYRIGHT_URL" target="_blank" rel="noopener">{{ OSM_ATTRIBUTION }}</a>
    </div>

    <div v-if="legend" class="legend">
      <!-- 拥挤指数视图的图例:色阶 + 档位刻度 + 与四级视图的互证说明(手册 §11.2 必现图例) -->
      <template v-if="isIndex">
        <div class="lg-title">拥挤指数色阶(ci · 0~100)</div>
        <div class="lg-ramp" :style="{ background: ciGradientCss() }" />
        <div class="lg-scale">
          <span v-for="b in CI_BANDS" :key="b">{{ b }}</span>
        </div>
        <div class="lg-note">{{ CI_BAND_NOTE }}</div>
        <div class="lg-note strong">{{ CI_DISCLAIMER }}</div>
        <div class="lg-sep" />
        <div class="lg-row"><LevelBadge :level="1" stale />灰 = 数据不可用(缺 ci 或数据陈旧)</div>
        <!-- 车辆动点在**任何** mode 下都照画,图例必须跟着给 -->
        <div v-for="v in VEH_LEGEND" :key="v.t" class="lg-row">
          <span class="dot" :style="{ background: v.color }" />{{ v.t }} {{ v.label }}
        </div>
        <div class="lg-row ts">更新 {{ props.ts || '—' }}</div>
      </template>
      <!-- 四级视图的图例 -->
      <template v-else>
        <div class="lg-title">四级编码(颜色 · 竖条 · 文字)</div>
        <div class="lg-row"><LevelBadge :level="1" /></div>
        <div class="lg-row"><LevelBadge :level="2" /></div>
        <div class="lg-row"><LevelBadge :level="3" /></div>
        <div class="lg-row"><LevelBadge :level="4" /></div>
        <div class="lg-row"><LevelBadge :level="1" stale /></div>
        <div class="lg-sep" />
        <div v-for="v in VEH_LEGEND" :key="v.t" class="lg-row">
          <span class="dot" :style="{ background: v.color }" />{{ v.t }} {{ v.label }}
        </div>
        <div class="lg-row"><span class="dot flow" />推荐路线(当前)</div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.netmap {
  position: relative;
  width: 100%;
  height: 100%;
  background: #f7f8fa;
  border-radius: 6px;
  overflow: hidden;
}
svg {
  width: 100%;
  height: 100%;
  display: block;
}
.road {
  cursor: pointer;
}
.flowline {
  animation: dash-flow 1.1s linear infinite;
}
@keyframes dash-flow {
  to {
    stroke-dashoffset: -24;
  }
}
.veh {
  transition: transform 1.9s linear;
}
.lbl {
  fill: #666666;
  font-size: 12px;
}
.station-name {
  fill: #1a1a1a;
  font-size: 13px;
  font-weight: 600;
}
.station-en {
  fill: #999999;
  font-size: 10px;
}
.sec-lbl {
  fill: #666666;
  font-size: 11px;
}
.drop-lbl {
  fill: #0052d9;
  font-size: 11px;
}
.sel-chip {
  fill: #0052d9;
  font-size: 11px;
  font-weight: 500;
}
.watermark {
  position: absolute;
  top: 10px;
  right: 14px;
  font-size: 11px;
  color: #999999;
  pointer-events: none;
}
.legend {
  position: absolute;
  left: 12px;
  bottom: 12px;
  padding: 9px 12px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  pointer-events: none;
}
.lg-title {
  font-size: 11px;
  color: #666666;
  margin-bottom: 1px;
}
.lg-row {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  color: #1a1a1a;
}
.lg-row .dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  margin-right: 7px;
  display: inline-block;
}
.lg-row .dot.flow {
  background: repeating-linear-gradient(90deg, #0052d9 0 6px, transparent 6px 10px);
  border-radius: 0;
}
.lg-sep {
  height: 1px;
  background: #e8e8e8;
  margin: 3px 0;
}
.lg-ramp {
  height: 10px;
  width: 186px;
  border-radius: 3px;
  border: 1px solid #e8e8e8;
}
.lg-scale {
  display: flex;
  justify-content: space-between;
  width: 186px;
  font-size: 10px;
  color: #999999;
}
.lg-note {
  max-width: 210px;
  font-size: 10px;
  line-height: 1.5;
  color: #666666;
  white-space: normal;
}
.lg-note.strong {
  color: #a06a00;
}
.lg-row.ts {
  font-size: 10px;
  color: #999999;
}
.heat {
  filter: blur(7px);
}
.attribution {
  position: absolute;
  right: 14px;
  bottom: 10px;
  font-size: 10px;
  pointer-events: auto;
}
.attribution a {
  color: #999999;
  text-decoration: none;
}
.attribution a:hover {
  color: #0052d9;
  text-decoration: underline;
}
</style>
