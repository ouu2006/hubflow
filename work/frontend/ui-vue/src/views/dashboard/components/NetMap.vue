<script setup lang="ts">
// 中央路网图:零依赖 SVG 渲染(TDesign Light,2026-10-12 配色切换)。
//   mode = 'level' → 四级染色(判级产出);mode = 'index' → 拥挤指数色阶(ci,仅展示)。
// 叠加层:路线高亮 / 车辆动点 / **跟随鼠标的信息浮牌**(业主 2026-10-14:
//   鼠标放在哪条路段上,蓝框信息牌就出现在那条线上、跟着鼠标沿线移动)。
// 底图数据 = 示例路网(非实测,#36/#37 站点包落地后替换;真路网时触发 OSM 署名)。
// 语义纪律:品牌蓝只画"当前/已选/推荐路线";路段色只表示等级;数据不可用一律灰。
// 极简口径(业主 2026-10-14):图上**只画路段线本身**——站点块/场区/断面/落客点/
//   节点白点等标注一律不画;文字只出现在跟随鼠标的浮牌里。
//
// 2026-10-15(Issue IKLX5Y)新增三件,都只对声明了策略的包生效:
//   ① **摄像头标记**:站点包 `channels` 里带 `lon`/`lat` 的通道画成可点的摄像头图钉;
//   ② **只摄像头段上色**:`colorPolicy === 'camera-covered'` 时,没摄像头覆盖的段
//      只画中性灰轮廓(细线),一眼看出"这段没监控";
//   ③ **点摄像头跳感知层**:图钉点击 → 跳到 `/perception?source=<通道>`。
//   老包(策略 `'all'`、通道无坐标)行为**一字不动**。
import { computed, ref } from 'vue'
import {
  DEMO_NETWORK,
  isOsmNetwork,
  networkSourceLabel,
  OSM_ATTRIBUTION,
  OSM_COPYRIGHT_URL,
  type DemoSegment,
} from '../../../shared/demoNetwork'
import {
  cameraPins,
  isCameraCovered,
  packColorPolicy,
  perceptionHref,
  type CameraPin,
} from '../../../shared/cameras'
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
  type SegmentRecord,
  type VehicleRecord,
} from '../../../shared/traffic'
import LevelBadge from './LevelBadge.vue'

const UNAVAILABLE_COLOR = UNAVAILABLE.color
const BRAND = TD.brand
/** 摄像头钉身:中性深灰(不是等级色,也不是品牌蓝——品牌蓝只表示"当前/已选/可操作") */
const CAM_FILL = '#37474F'
const CAM_STROKE = TD.brand

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
    /** 跟随鼠标的信息浮牌文字(空串不画) */
    hoverChip?: string
    /** 紧凑图例(右栏无独立图例时用) */
    legend?: boolean
  }>(),
  {
    mode: 'level',
    ts: '',
    hoverChip: '',
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

// ---- 只摄像头段上色(Issue IKLX5Y;业主 2026-10-15 裁定) ----
//
// 策略来自站点包(`colorPolicy`):`'camera-covered'` 时,没摄像头覆盖的段**不上色**
// —— 用同一个"数据不可用"灰,靠**线宽 + 透明度**与"有摄像头但没数据"区分开,
// 不引入第二套灰(手册 §6.2:等级色只表示等级、灰只表示"没有"）。
const colorPolicy = packColorPolicy()
const cameraOnly = colorPolicy === 'camera-covered'

/** 该段是否有摄像头覆盖(策略为 'all' 时恒 true,即老行为) */
function covered(seg: DemoSegment): boolean {
  return isCameraCovered(seg.segment_id)
}

/**
 * 路段色。三档,别混:
 *   ① 有监控且数据可用 → 等级色 / ci 色阶;
 *   ② 有监控但数据不可用 → 灰(粗,`UNAVAILABLE`);
 *   ③ **没监控** → 灰(细、淡)——"这段没摄像头"本身是个信息,不能与 ② 长得一样。
 */
function colorOf(seg: DemoSegment): string {
  if (!covered(seg)) return UNAVAILABLE_COLOR
  const rec = recOf(seg)
  if (!rec) return UNAVAILABLE_COLOR
  return isIndex.value ? ciStyleColor(rec) : levelStyle(rec).color
}

/** 热力晕染:仅指数视图且 ci 可用时渲染,强度随 ci 单调增(不改任何判级着色) */
function heatOpacity(seg: DemoSegment): number {
  if (!covered(seg)) return 0
  const rec = recOf(seg)
  if (!rec || !ciAvailable(rec)) return 0
  const v = Math.min(CI_MAX, Math.max(0, rec.ci as number))
  return Math.round((0.1 + (v / CI_MAX) * 0.5) * 100) / 100
}

function heatWidth(seg: DemoSegment): number {
  return seg.kind === 'main' ? 26 : 22
}

function baseWidth(seg: DemoSegment): number {
  return seg.kind === 'main' ? 18 : 14
}

function casingWidth(seg: DemoSegment): number {
  return baseWidth(seg) + 6
}

/** 轮廓宽:没监控的段细(8),有监控的段按 kind(与热力晕染同宽,保证色块大小一致) */
function outlineWidth(seg: DemoSegment): number {
  return covered(seg) ? baseWidth(seg) : 8
}

/** 轮廓透明度:没监控的段更淡,与"有监控但数据不可用"再拉开一档 */
function outlineOpacity(seg: DemoSegment): number {
  return covered(seg) ? 1 : 0.45
}

// ---- 摄像头标记(Issue IKLX5Y) ----
//
// 位置来自站点包 `channels[].lon/lat`(生成脚本投影到路段线上的示意点)。
// 语义纪律:图钉用**中性深灰 + 品牌蓝描边**(「可操作」语义),不用等级四级色;
//   没有视频源的图钉多一个空心圈(视觉上区分"还没接视频"),文字说明在浮牌与感知层。
const pins = cameraPins()
const pinPts = computed(() =>
  pins.map((p) => {
    const [x, y] = px(p.lon, p.lat)
    return { ...p, x, y }
  }),
)

/** 摄像头浮牌(悬停时显示;点段浮牌是另一套,不混) */
const pin = ref<CameraPin | null>(null)

/** 点摄像头 → 当前窗口开感知层对应通道(深链见 shared/cameras.ts) */
function openCamera(p: CameraPin): void {
  window.location.href = perceptionHref(p.source)
}

const osmActive = computed(() => isOsmNetwork())

// ---- 路线高亮 ----

const routeSet = computed(() => new Set(props.routeSegments))

// ---- 跟随鼠标的信息浮牌(业主 2026-10-14) ----
// 坐标系:鼠标事件落在 HTML 元素上,拿的是相对 .netmap 的 CSS 像素;
// 浮牌画在 HTML 层(div,不在 SVG 里),避掉 SVG viewBox 缩放换算。
// 显示口径(业主 2026-10-14 定稿):鼠标一旦悬停上某条线,浮牌**常驻不消失**,
//   只是"吸附"在那条线上——鼠标在图上任何地方移动,浮牌都钉在
//   **当前悬停选中的那条路段**上,顺着线走;鼠标离开整张图才整体隐藏。

const CHIP_W = 210
const CHIP_H = 26

const mouse = ref<{ x: number; y: number } | null>(null)
const overRoad = ref(false)

function onMapMouseMove(ev: MouseEvent): void {
  const host = ev.currentTarget as HTMLElement
  const rect = host.getBoundingClientRect()
  mouse.value = { x: ev.clientX - rect.left, y: ev.clientY - rect.top }
}

function onMapMouseLeave(): void {
  mouse.value = null
  overRoad.value = false
}

/** 悬停进/出某条路段线 */
function onRoadEnter(): void {
  overRoad.value = true
}

function onRoadLeave(): void {
  overRoad.value = false
}

/**
 * 浮牌落点 = 选中路段折线上**离鼠标最近的那个采样点**——
 * 鼠标沿线走,浮牌就贴在线上跟着走;鼠标离开线,浮牌停在线上不动(不消失)。
 * px() 与 pointsFor() 用同一套投影,单位 = CSS 像素(viewBox 等比缩放已含在 SCALE 内)。
 */
const chipStyle = computed(() => {
  if (!mouse.value || !props.selectedId) return {}
  const seg = net.find((s) => s.segment_id === props.selectedId)
  if (!seg) return {}
  let best = px(seg.coords[0][0], seg.coords[0][1])
  let bestD = Infinity
  for (const [lon, lat] of seg.coords) {
    const [x, y] = px(lon, lat)
    const d = (x - mouse.value.x) ** 2 + (y - mouse.value.y) ** 2
    if (d < bestD) {
      bestD = d
      best = [x, y]
    }
  }
  // 注意:SVG 用户坐标 == CSS 像素(外层 svg width/height 都是 100%,
  // viewBox 等比缩放,浏览器把用户坐标映射到显示尺寸;这里直接按用户坐标摆,
  // 除以实际显示/viewBox 比例即可——用 getBoundingClientRect 换算)
  const svg = document.querySelector('.netmap svg')
  if (!svg) return {}
  const rect = svg.getBoundingClientRect()
  const kx = rect.width / W
  const ky = rect.height / H
  const cx = best[0] * kx
  const cy = best[1] * ky
  const chipW = CHIP_W * kx
  const chipH = CHIP_H * ky
  const flipX = cx + chipW + 18 > rect.width
  const flipY = cy - chipH - 14 < 0
  return {
    left: `${flipX ? cx - chipW - 14 : cx + 14}px`,
    top: `${flipY ? cy + 16 : cy - chipH - 12}px`,
  }
})

/** 摄像头浮牌落点 = 图钉正上方(与路段浮牌不同:那个跟着鼠标沿线走,这个钉在图钉上) */
const camChipStyle = computed(() => {
  const p = pin.value
  if (!p) return {}
  const svg = document.querySelector('.netmap svg')
  if (!svg) return {}
  const rect = svg.getBoundingClientRect()
  const [ux, uy] = px(p.lon, p.lat)
  const cx = ux * (rect.width / W)
  const cy = uy * (rect.height / H)
  return { left: `${Math.max(6, cx - 96)}px`, top: `${Math.max(6, cy - 62)}px` }
})

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
  <div class="netmap" @mousemove="onMapMouseMove" @mouseleave="onMapMouseLeave">
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
        @mouseenter="hoverSelect(s); onRoadEnter()"
        @mouseleave="onRoadLeave()"
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
          :stroke-width="outlineWidth(s)"
          :style="{ opacity: outlineOpacity(s) }"
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

      <!-- 摄像头布点(Issue IKLX5Y):点一下跳感知层该通道;有/无视频源用实心/空心圈区分 -->
      <g
        v-for="p in pinPts"
        :key="`cam-${p.cid}`"
        class="cam"
        :style="{ transform: `translate(${p.x}px, ${p.y}px)` }"
        @mouseenter="pin = p"
        @mouseleave="pin = null"
        @click.stop="openCamera(p)"
      >
        <title>{{ p.cid }} · {{ p.name }} · {{ p.segment_id }} · {{ p.hasVideo ? '有视频源' : '未接入视频源(本期留空)' }}</title>
        <!-- 外圈:白底衬,让图钉在彩线上也看得清 -->
        <circle r="9.5" fill="#FFFFFF" fill-opacity="0.92" />
        <!-- 钉身:实心 = 有视频源;空心(白心) = 未接入视频源 -->
        <circle
          r="6"
          :fill="p.hasVideo ? CAM_FILL : '#FFFFFF'"
          :stroke="CAM_STROKE"
          stroke-width="2"
        />
        <text class="cam-cid" y="3.2" text-anchor="middle" :fill="p.hasVideo ? '#FFFFFF' : CAM_FILL">{{ p.cid.replace('C-', '') }}</text>
      </g>
    </svg>

    <!-- 摄像头浮牌(悬停图钉时;与路段浮牌是两套,不混) -->
    <div v-if="pin" class="cam-chip" :style="camChipStyle">
      <b>{{ pin.cid }}</b> {{ pin.name }}
      <span class="cam-chip-sub">{{ pin.segment_id }} · {{ pin.hasVideo ? '有视频源' : '未接入视频源 · 本期留空' }} · 点击进感知层</span>
    </div>

    <!-- 跟随鼠标的信息浮牌:吸附在当前选中路段上,沿线走,不消失(业主 2026-10-14) -->
    <div v-if="mouse && overRoad && hoverChip" class="hover-chip" :style="chipStyle">
      {{ hoverChip }}
    </div>

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
        <!-- 「只摄像头段上色」的图例(Issue IKLX5Y):说清灰轮廓 = 这段没监控 -->
        <template v-if="cameraOnly">
          <div class="lg-sep" />
          <div class="lg-row"><span class="dot cam-dot" />摄像头布点（点击进感知层）</div>
          <div class="lg-row"><span class="dot cam-dot empty" />摄像头 · 未接入视频源</div>
          <div class="lg-note">未挂摄像头的路段**只画灰轮廓**、不上色</div>
        </template>
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
/* 跟随鼠标的信息浮牌:蓝框白底,贴鼠标右上、越界翻面,不挡鼠标(pointer-events:none) */
.hover-chip {
  position: absolute;
  min-width: 120px;
  max-width: 260px;
  padding: 4px 10px;
  background: #ffffff;
  border: 1.2px solid v-bind('BRAND');
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  font-size: 11px;
  font-weight: 500;
  color: v-bind('BRAND');
  white-space: nowrap;
  pointer-events: none;
  z-index: 3;
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
.lg-row.ts {
  color: #999999;
}
.lg-note {
  font-size: 10px;
  color: #999999;
}
.lg-note.strong {
  color: #666666;
}
.lg-sep {
  height: 1px;
  background: #eeeeee;
  margin: 2px 0;
}
.dot.flow {
  background: linear-gradient(90deg, transparent 40%, #0052d9 40%);
}
/* 摄像头图钉(Issue IKLX5Y):钉身中性深灰 + 品牌蓝描边(「可操作」语义) */
.cam {
  cursor: pointer;
}
.cam-cid {
  font-size: 9px;
  font-weight: 600;
  pointer-events: none;
}
/* 图例里的摄像头小圆点:与外圈同款(实心 = 有视频源、空心 = 未接入) */
.dot.cam-dot {
  background: #37474f;
  border: 1.6px solid v-bind('BRAND');
}
.dot.cam-dot.empty {
  background: #ffffff;
}
/* 摄像头浮牌:钉在图钉上方,不跟鼠标(与路段浮牌区分) */
.cam-chip {
  position: absolute;
  width: 192px;
  padding: 5px 9px;
  background: #ffffff;
  border: 1.2px solid v-bind('BRAND');
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.14);
  font-size: 11px;
  color: #1a1a1a;
  line-height: 1.5;
  pointer-events: none;
  z-index: 4;
}
.cam-chip-sub {
  display: block;
  color: #666666;
}
</style>
