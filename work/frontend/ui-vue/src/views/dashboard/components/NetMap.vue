<script setup lang="ts">
// 中央路网图:零依赖 SVG 渲染。四级染色 + 选中描边 + 推荐路线高亮(流动虚线)+
// 孪生车辆动点(位置随快照刷新,CSS transition 平滑移动)。
// 底图数据 = 示例路网(非实测,#36/#37 站点包落地后替换)。
import { computed } from 'vue'
import { DEMO_NETWORK, type DemoSegment } from '../../../shared/demoNetwork'
import { levelStyle, type DriverType, type SegmentRecord, type VehicleRecord } from '../../../shared/traffic'
import LevelBadge from './LevelBadge.vue'

const props = defineProps<{
  segments: SegmentRecord[]
  vehicles: VehicleRecord[]
  selectedId: string | null
  /** 当前高亮路线包含的路段 id(推荐/备选/离站) */
  routeSegments: string[]
}>()

const emit = defineEmits<{ (e: 'select', segmentId: string): void }>()

// ---- 投影:经纬度 → SVG 用户坐标(等距圆柱近似,经度按 cos(纬度) 修正) ----

const W = 1100
const H = 680
const PAD = 52

const net = DEMO_NETWORK.segments
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

// ---- 路段染色 ----

const segById = computed(() => new Map(props.segments.map((s) => [s.segment_id, s])))

function colorOf(seg: DemoSegment): string {
  const rec = segById.value.get(seg.segment_id)
  return rec ? levelStyle(rec).color : '#8C8C8C' // 无数据 = 灰色(数据不可用)
}

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

    <div class="watermark">示例路网 · 非实测</div>

    <div class="legend">
      <div class="lg-title">四级编码(颜色 · 竖条 · 文字)</div>
      <div class="lg-row"><LevelBadge :level="1" /></div>
      <div class="lg-row"><LevelBadge :level="2" /></div>
      <div class="lg-row"><LevelBadge :level="3" /></div>
      <div class="lg-row"><LevelBadge :level="4" /></div>
      <div class="lg-row"><LevelBadge :level="1" stale /></div>
      <div class="lg-sep" />
      <div class="lg-row"><span class="dot" :style="{ background: VEH_COLORS.D1 }" />D1 送客车辆</div>
      <div class="lg-row"><span class="dot" :style="{ background: VEH_COLORS.D2 }" />D2 接客车辆</div>
      <div class="lg-row"><span class="dot flow" />路线高亮</div>
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
</style>
