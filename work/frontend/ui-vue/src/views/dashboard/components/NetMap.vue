<script setup lang="ts">
// 中央路网图:零依赖 SVG 渲染。两种视图模式(Issue #66):
//   mode = 'level' → 四级染色(判级产出);mode = 'index' → 拥挤指数色阶(ci,仅展示)。
// 另有:选中描边 + 推荐路线高亮(流动虚线) + 孪生车辆动点(位置随快照刷新,CSS transition 平滑移动)。
// 底图数据 = 示例路网(非实测,#36/#37 站点包落地后替换;真路网时触发 OSM 署名)。
import { computed } from 'vue'
import {
  DEMO_NETWORK,
  isOsmNetwork,
  networkSourceLabel,
  OSM_ATTRIBUTION,
  OSM_COPYRIGHT_URL,
  type DemoSegment,
} from '../../../shared/demoNetwork'
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
  type SegmentRecord,
  type VehicleRecord,
} from '../../../shared/traffic'
import LevelBadge from './LevelBadge.vue'

const UNAVAILABLE_COLOR = UNAVAILABLE.color

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
  }>(),
  { mode: 'level', ts: '' },
)

const emit = defineEmits<{ (e: 'select', segmentId: string): void }>()

// ---- 投影:经纬度 → SVG 用户坐标(等距圆柱近似,经度按 cos(纬度) 修正) ----

const W = 1100
const H = 680
const PAD = 52

const net = DEMO_NETWORK.segments
const sourceLabel = networkSourceLabel()
const lons = net.flatMap((s) => s.coords.map((c) => c[0]))
const lats = net.flatMap((s) => s.coords.map((c) => c[1]))
const minLon = Math.min(...lons)
const maxLat = Math.max(...lats)
const cosLat = Math.cos((((Math.min(...lats) + maxLat) / 2) * Math.PI) / 180)

const rawW = (Math.max(...lons) - minLon) * cosLat
const rawH = maxLat - Math.min(...lats)
const SCALE = Math.min((W - PAD * 2) / rawW, (H - PAD * 2) / rawH)
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
  return Math.round((0.12 + (v / CI_MAX) * 0.58) * 100) / 100
}

function heatWidth(seg: DemoSegment): number {
  return seg.kind === 'main' ? 26 : 22
}

const osmActive = computed(() => isOsmNetwork())

// ---- 路线高亮与落客点 ----

const routeSet = computed(() => new Set(props.routeSegments))

const dropoff = computed<[number, number] | null>(() => {
  const lastId = props.routeSegments[props.routeSegments.length - 1]
  if (!lastId) return null
  const seg = net.find((s) => s.segment_id === lastId)
  if (!seg) return null
  const end = seg.coords[seg.coords.length - 1]
  return px(end[0], end[1])
})

// ---- 车辆动点 ----

const VEH_COLORS: Record<DriverType, string> = {
  D1: '#FFC53D',
  D2: '#4FD1C5',
  D3: '#B58BFF',
}

// 三类司机(数据契约 :332 / 手册 :175):D1 送客 / D2 接客 / D3 往返(出租车、网约车)
const VEH_LABEL: Record<DriverType, string> = {
  D1: '送客车辆',
  D2: '接客车辆',
  D3: '往返车辆(出租车 / 网约车)',
}

// 图例**由 VEH_COLORS 生成**,不手写行——否则新增司机类型(如 D3)时地图画了、图例却漏(Sourcery 意见)
const VEH_LEGEND = (Object.keys(VEH_COLORS) as DriverType[]).map((t) => ({
  t,
  color: VEH_COLORS[t],
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
      <!-- 路基描边(暗色底衬,增强与背景的层次) -->
      <g v-for="s in net" :key="`casing-${s.segment_id}`">
        <polyline
          :points="pointsFor(s)"
          fill="none"
          stroke="#050D1A"
          :stroke-width="s.kind === 'main' ? 15 : 12"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </g>
      <!-- 路段:四级染色 + 路线高亮 + 选中描边 -->
      <g
        v-for="s in net"
        :key="`road-${s.segment_id}`"
        class="road"
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
          :stroke-width="s.kind === 'main' ? 11 : 8"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <template v-if="routeSet.has(s.segment_id)">
          <polyline
            :points="pointsFor(s)"
            fill="none"
            stroke="#37D6FF"
            stroke-width="14"
            opacity="0.25"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <polyline
            class="flowline"
            :points="pointsFor(s)"
            fill="none"
            stroke="#8FEAFF"
            stroke-width="3"
            stroke-linecap="round"
            stroke-dasharray="16 12"
          />
        </template>
        <polyline
          v-if="props.selectedId === s.segment_id"
          :points="pointsFor(s)"
          fill="none"
          stroke="#FFFFFF"
          stroke-width="2.5"
          stroke-dasharray="3 7"
          stroke-linecap="round"
          opacity="0.95"
        />
      </g>
      <!-- 落客点 -->
      <g v-if="dropoff" class="dropoff" :transform="`translate(${dropoff[0]},${dropoff[1]})`">
        <circle r="9" fill="#0A1424" stroke="#FFC53D" stroke-width="2.5" />
        <circle r="3" fill="#FFC53D" />
        <text y="-16" text-anchor="middle">落客点</text>
      </g>
      <!-- 孪生车辆动点(位置随快照刷新平滑移动) -->
      <g
        v-for="v in vehPts"
        :key="v.vehicle_id"
        class="veh"
        :style="{ transform: `translate(${v.x}px, ${v.y}px)` }"
      >
        <circle r="6" :fill="VEH_COLORS[v.driver_type]" stroke="#081222" stroke-width="1.5" />
        <title>{{ v.vehicle_id }} · {{ v.state }} · {{ v.segment_id }}{{ v.is_demo_bound ? ' · 演示绑定车' : '' }}</title>
      </g>
    </svg>

    <div class="watermark">{{ sourceLabel }}</div>

    <div v-if="osmActive" class="attribution">
      <a :href="OSM_COPYRIGHT_URL" target="_blank" rel="noopener">{{ OSM_ATTRIBUTION }}</a>
    </div>

    <div class="legend">
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
        <!-- 车辆动点在**任何** mode 下都照画(:220-228),图例必须跟着给,否则指数视图出现无说明的彩色圆点；
             且行由 VEH_LEGEND 生成,D1/D2/D3 一个不落 -->
        <div v-for="v in VEH_LEGEND" :key="v.t" class="lg-row">
          <span class="dot" :style="{ background: v.color }" />{{ v.t }} {{ v.label }}
        </div>
        <div class="lg-row ts">更新 {{ props.ts || '—' }}</div>
      </template>
      <!-- 四级视图的图例(原有) -->
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
        <div class="lg-row"><span class="dot flow" />路线高亮</div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.netmap {
  position: relative;
  width: 100%;
  height: 100%;
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
    stroke-dashoffset: -28;
  }
}
.veh {
  transition: transform 1.9s linear;
}
.dropoff text {
  fill: #ffd479;
  font-size: 15px;
}
.watermark {
  position: absolute;
  top: 10px;
  right: 16px;
  font-size: 13px;
  letter-spacing: 2px;
  color: rgba(150, 175, 210, 0.5);
  pointer-events: none;
}
.legend {
  position: absolute;
  left: 14px;
  bottom: 12px;
  padding: 10px 14px;
  background: rgba(8, 18, 34, 0.82);
  border: 1px solid #1d3354;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  pointer-events: none;
}
.lg-title {
  font-size: 11px;
  color: #7c93b5;
  margin-bottom: 2px;
}
.lg-row {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  color: #d9e4f5;
}
.lg-row .dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  margin-right: 7px;
  display: inline-block;
}
.lg-row .dot.flow {
  background: repeating-linear-gradient(90deg, #8feaff 0 6px, transparent 6px 10px);
}
.lg-sep {
  height: 1px;
  background: #1d3354;
  margin: 3px 0;
}
/* 拥挤指数视图(色阶图例 + 热力晕染) */
.lg-ramp {
  height: 10px;
  width: 190px;
  border-radius: 3px;
  border: 1px solid #1d3354;
}
.lg-scale {
  display: flex;
  justify-content: space-between;
  width: 190px;
  font-size: 10px;
  color: #7c93b5;
}
.lg-note {
  max-width: 210px;
  font-size: 10px;
  line-height: 1.5;
  color: #7c93b5;
  white-space: normal;
}
.lg-note.strong {
  color: #ffd479;
}
.lg-row.ts {
  font-size: 11px;
  color: #9fb6d9;
}
.heat {
  filter: blur(7px);
}
.attribution {
  position: absolute;
  right: 16px;
  bottom: 12px;
  font-size: 11px;
  pointer-events: auto;
}
.attribution a {
  color: rgba(150, 175, 210, 0.72);
  text-decoration: none;
}
.attribution a:hover {
  color: #37d6ff;
  text-decoration: underline;
}
</style>
