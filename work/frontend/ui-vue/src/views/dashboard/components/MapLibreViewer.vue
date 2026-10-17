<script setup lang="ts">
// 大屏中央路网图：**MapLibre GL 单渲染器**（Issue IKM5T1）。
//
// 业主 2026-10-16 口径：大屏地图只留一个 —— 删掉「示例路网」那套自绘 SVG（NetMap.vue），
// 只留矢量地图；「示例路网」不再是一个模式，它**退化成矢量地图里的那些路网线条本身**。
//
// 本文件的两件正事：
//   ① **底图与路网解耦**：先用**本地兜底样式**把地图建起来，路网 source/layer 立刻加上并取景；
//      OpenFreeMap 的样式**随后**异步拉，成功再把底图合进来，失败就只用兜底那份。
//      于是"底图拉不出来"只影响底图 —— **路网照画、不白屏、不被提示层遮住**。
//   ② **功能一项不少**：原先自绘视图里的四件事搬到本文件 ——
//      车辆动点 / 悬停浮牌 / 推荐路线 / 图例 + 水印（图例、水印、浮牌都是 DOM 覆盖层，
//      不进 MapLibre 的图层栈）。
//
// 为什么不走高德（2026-10-15 换，PR !19）：
//   ① **坐标系不用转** —— 站点包统一存 WGS-84，OpenFreeMap 的 OSM 数据也是 WGS-84，天然对齐；
//   ② **不需要 Key / 注册** —— 没有高德「商业目的须先购买技术服务许可」那条风险；
//   ③ 与仓库既定方向一致 —— 手册 §8.3 / D7 的口径就是「路网走 OSM」。
//
// 合规（改之前先读 `docs/条款核实.md`）：
//   · OSM 数据受 ODbL 约束，**必须署名** —— MapLibre 默认的 AttributionControl 保留，
//     不得隐藏、不得被 UI 遮挡；**路网那一份署名单独画**（`.attribution`），
//     这样底图挂了署名仍在（条款核实 E-11 / E-13）；
//   · **不缓存瓦片、不做离线包**。断网演示的正解是**自建瓦片**，不是缓存别人的公共服务；
//   · OpenFreeMap 是第三方免费公共服务（无 SLA），其自身条款**尚未进过本仓库的条款核实清单** ——
//     对外发布前须补核（另见「审图号」要求，OSM 底图无审图号）。
//
// 语义纪律（照抄自绘视图）：路段色只表示拥挤度/等级；品牌蓝只画「当前 / 已选 / 推荐」。
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import {
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  ScaleControl,
  setWorkerUrl,
  type ExpressionSpecification,
  type FilterSpecification,
  type GeoJSONSource,
  type LineLayerSpecification,
  type MapMouseEvent,
  type StyleSpecification,
} from 'maplibre-gl'
// ⚠️ 必须显式指定 worker 地址，否则**生产构建底图空白**（实测踩过）：
//   MapLibre 的矢量瓦片解析跑在独立 worker 里（508 KB），主包按
//   `new URL('./maplibre-gl-worker.mjs', import.meta.url)` 找它。dev 下（已 exclude 出依赖预打包）
//   它恰好与主包同目录、能被 Vite 直接端出来；但**打包后那个兄弟文件不会被产出** ——
//   dist 里只有 index.js/css，运行时去要 `/assets/maplibre-gl-worker.mjs` 直接落空，
//   报「Worker failed to load」，地图整块空白且不报 HTTP 错（worker 加载失败不走 response 事件）。
//   用 `?url` 让 Vite 把这个 worker 文件真正产出到 assets/ 并返回它的地址。
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
// ⚠️ 也必须显式 import：`tsconfig.app.json` 的 `types: ["vite/client"]` 只放行 vite/client，
//    所以 `@types/geojson` 的全局 `GeoJSON` 命名空间**不可见**（用 `GeoJSON.FeatureCollection`
//    会报 TS2503 Cannot find namespace 'GeoJSON'）。
import type { FeatureCollection } from 'geojson'
import 'maplibre-gl/dist/maplibre-gl.css'

setWorkerUrl(maplibreWorkerUrl)

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
import { basemapEnabled } from '../../../shared/settings'
import {
  BASEMAP_PROXY_PROBE,
  BASEMAP_STYLE_URL,
  setBasemapProxyDetected,
  toBasemapUrl,
} from '../../../shared/basemap'
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
  type RouteHighlight,
  type SegmentRecord,
  type VehicleRecord,
} from '../../../shared/traffic'
import LevelBadge from './LevelBadge.vue'

const BRAND = TD.brand

/**
 * OpenFreeMap 的 Liberty 样式（免 Key、免注册；数据来自 OpenStreetMap）。
 * 地址口径与"同源直通"开关都在 `shared/basemap.ts`（本机系统代理会黑洞掉上游域名，见那里注释）。
 */
const STYLE_URL = BASEMAP_STYLE_URL
/**
 * **本地兜底样式**：不依赖任何公网资源，只用来把地图建起来。
 * 路网图层与摄像头图钉在这份样式上就位，因此"底图能不能拉到"**不参与**路网是否画得出来。
 */
const FALLBACK_STYLE: StyleSpecification = { version: 8, sources: {}, layers: [] }
/** 底图**样式**拉取上限：超时即按"底图不可用"处理，**不阻塞路网** */
const BASEMAP_TIMEOUT_MS = 8000
/**
 * 底图**瓦片**就绪上限。样式拿到 ≠ 底图画得出来：本机实测过"样式命中 HTTP 缓存 3 ms 返回 200，
 * 而 tilejson / `.pbf` 全部挂到超时"——那时地图只剩 Liberty 样式里的底色层（没有路、没有建筑），
 * 旧代码却已经把状态写成 `ok`。所以拿到样式后还要**等矢量瓦片真的就绪**，等不到一样算失败。
 */
const BASEMAP_TILES_TIMEOUT_MS = 8000
/** 同源直通代理的探测上限（探不到就直连上游，不能让探测本身拖慢建图） */
const BASEMAP_PROBE_TIMEOUT_MS = 1500

const SRC = 'hubflow-route'
const LAYER_HEAT = `${SRC}-heat`
const LAYER_CASING = `${SRC}-casing`
const LAYER_LINE = `${SRC}-line`
/** 推荐路线（品牌蓝实线；「当前 / 已选」语义，不得用等级色） */
const LAYER_ROUTE_HALO = `${SRC}-route-halo`
const LAYER_ROUTE = `${SRC}-route`
/** 备选路线（灰虚线；可多条一起画） */
const LAYER_ROUTE_ALT_HALO = `${SRC}-route-alt-halo`
const LAYER_ROUTE_ALT = `${SRC}-route-alt`
/** 离站路线（紫色实线；第三种语义色，与等级色 / 品牌蓝分开） */
const LAYER_ROUTE_DEP_HALO = `${SRC}-route-dep-halo`
const LAYER_ROUTE_DEP = `${SRC}-route-dep`
const LAYER_SELECTED = `${SRC}-selected`

/** 备选路线的灰（TDesign gray-7 同族；不是等级色，也不是"数据不可用"的灰档） */
const ROUTE_ALT_COLOR = '#6B6B6B'
/** 离站路线色（紫色；与品牌蓝 / 四级色都不撞，只表示"第 3 种路线语义"） */
const ROUTE_DEPART_COLOR = '#7B61FF'

/** 悬停浮牌尺寸（只用于翻面判断，与 CSS 里的 min/max-width 对应） */
const CHIP_W = 210
const CHIP_H = 26

/** 'level' = 四级视图（默认） · 'index' = 拥挤指数视图 */
type MapMode = CongestionViewMode

const props = withDefaults(
  defineProps<{
    segments: SegmentRecord[]
    selectedId: string | null
    /** 孪生车辆动点（位置随快照刷新平滑移动） */
    vehicles?: VehicleRecord[]
    /** 推荐 / 备选 / 离站三组路线高亮（IKMF1W；空数组 = 不画路线） */
    routes?: RouteHighlight[]
    mode?: MapMode
    /** 快照时间（热力视图的"更新时间戳"，手册 §11.2 必现） */
    ts?: string
    /** 跟随鼠标的信息浮牌文字（空串不画） */
    hoverChip?: string
    /** 紧凑图例 */
    legend?: boolean
  }>(),
  {
    vehicles: () => [],
    routes: () => [],
    mode: 'level',
    ts: '',
    hoverChip: '',
    legend: true,
  },
)

const emit = defineEmits<{ (e: 'select', segmentId: string): void }>()

/** 容器**始终渲染**（不用 v-if 挂载），从根上避免「容器还没进 DOM 就初始化」那类静默失败 */
const containerRef = ref<HTMLDivElement | null>(null)
/**
 * ⚠️ 地图实例用 `shallowRef`：`ref()` 会对它做深度解包（`UnwrapRef`），
 * 解出来的类型丢掉类的私有成员与方法，再传回 `map.setFilter(...)` 这类接口就报
 * 「missing _setupResizeObserver」的假类型错；何况地图实例本来也不该被深度代理。
 */
const mapRef = shallowRef<MapLibreMap | null>(null)
/** 路网是否已经就位 —— **只判本地样式**，不判公网底图 */
const ready = ref(false)
/**
 * 底图这一层的状态（**只管底图，不管路网**）：
 *   `off`     —— 顶栏「设置」里关掉了：不拉任何底图资源，只剩路网（＝原「示例路网」观感）
 *   `loading` —— 正在拉 OpenFreeMap 样式
 *   `ok`      —— 底图已合入
 *   `failed`  —— 拉不到：路网照画 + 角标给「重试」，并按退避自动重试
 */
const basemap = ref<'off' | 'loading' | 'ok' | 'failed'>(basemapEnabled.value ? 'loading' : 'off')
const basemapMsg = ref('')
/**
 * 「正在再试一次」——**只在失败态追加**，不把状态切回 `loading`。
 * 为什么：自动重试若把角标切回「加载中」，那个模板分支会把「重试」按钮**卸载再挂载**，
 * 按钮在 DOM 里不稳定（实测：CDP 点它时被 Playwright 判为 "element is not stable"，
 * 点了 30 s 点不上）。留在失败态、只换按钮文案，按钮才点得动。
 */
const basemapRetrying = ref(false)
/** 失败后的**退避自动重试**间隔（手动「重试」会把计数清零） */
const RETRY_DELAYS_MS = [2000, 6000, 12000]
let retryStep = 0
let retryTimer = 0
/**
 * 底图这一轮拉取的**代次**。每次 `applyBasemap` 自增，用来让"上一轮"的异步尾巴（瓦片轮询、
 * 关开关后的在途请求）认出自己已经过期 —— 只看 `disposed` 不够：开关一开一关、或手动连点两次
 * 「重试」时，旧那一轮还会把状态写回 `ok`。
 */
let basemapRun = 0
/** 当前挂载的是不是"底图已合入"的那份样式（关开关时据此决定要不要换回兜底样式） */
let remoteApplied = false
/**
 * 在途的底图请求。关开关时**连在途的那一次也 abort 掉** ——
 * 否则"关＝一个请求都不发"只在冷启动成立（页面已加载再关，在途那一次仍会走完）。
 */
let inflightCtrl: AbortController | null = null

/**
 * 路网几何与来源口径。
 * ⚠️ `DEMO_NETWORK.segments` 是当前站点包的惰性快照：桥接覆盖发生在挂载前
 * （`main.ts` 拉 `/twin-api/network`），本组件挂载时它已经定了。
 */
const net = DEMO_NETWORK.segments
const sourceLabel = networkSourceLabel()
const osmActive = computed(() => isOsmNetwork())
/** 只摄像头段上色（站点包 `colorPolicy`）——老包的 `'all'` 行为不变 */
const cameraOnly = packColorPolicy() === 'camera-covered'
const pins = cameraPins()

// ---- 路段染色（四级 / 指数两种视图） ----

const segById = computed(() => new Map(props.segments.map((s) => [s.segment_id, s])))
const isIndex = computed(() => props.mode === 'index')

/**
 * 路段色。三档，别混：
 *   ① 有监控且数据可用 → 等级色 / ci 色阶；
 *   ② 有监控但数据不可用 → 灰（粗，`UNAVAILABLE`）；
 *   ③ **没监控** → 灰（细、淡）——"这段没摄像头"本身是个信息，不能与 ② 长得一样。
 */
function colorOf(seg: DemoSegment): string {
  if (!isCameraCovered(seg.segment_id)) return UNAVAILABLE.color
  const rec = segById.value.get(seg.segment_id)
  if (!rec) return UNAVAILABLE.color
  return isIndex.value ? ciStyleColor(rec) : levelStyle(rec).color
}

/** 热力晕染强度（仅指数视图且 ci 可用）：随 ci 单调增，不改任何判级着色 */
function heatOf(seg: DemoSegment): number {
  if (!isCameraCovered(seg.segment_id)) return 0
  const rec = segById.value.get(seg.segment_id)
  if (!rec || !ciAvailable(rec)) return 0
  const v = Math.min(CI_MAX, Math.max(0, rec.ci as number))
  return Math.round((0.1 + (v / CI_MAX) * 0.5) * 100) / 100
}

/** 站点包坐标是 WGS-84，**直接喂给 MapLibre** —— 不做任何坐标转换 */
function routeGeoJson(): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: net.map((seg) => ({
      type: 'Feature',
      properties: {
        segment_id: seg.segment_id,
        name: seg.name,
        kind: seg.kind,
        color: colorOf(seg),
        /** 该段是否有摄像头覆盖（策略 'all' 时恒 true）—— 线宽/透明度按它分档 */
        covered: isCameraCovered(seg.segment_id),
        /** 热力晕染强度（0 = 不画） */
        heat: heatOf(seg),
      },
      geometry: { type: 'LineString', coordinates: seg.coords },
    })),
  }
}

/**
 * 线宽 = 主/支两档 × 「没摄像头覆盖」系数。
 * 收细 + 压透明度是「只摄像头段上色」策略下"这段没监控"的画法（业主 2026-10-15），
 * 与"有摄像头但当前没数据"的灰区分开（后者用正常线宽）。
 */
const widthExpr = (main: number, ramp: number): ExpressionSpecification => [
  '*',
  ['case', ['==', ['get', 'kind'], 'main'], main, ramp],
  ['case', ['==', ['get', 'covered'], false], 0.55, 1],
]

function selectedFilter(): FilterSpecification {
  return ['==', ['get', 'segment_id'], props.selectedId ?? '']
}

function routeFilter(): FilterSpecification {
  return ['in', ['get', 'segment_id'], ['literal', routeIdsOf('arrival')]]
}

/**
 * 取某一组（或多组）路线要高亮的路段 id —— 去重后作为图层 filter 的 `literal`。
 * 备选可能有多条，叠成一组灰虚线一起画（同一条段重复出现只画一次）。
 */
function routeIdsOf(...kinds: RouteHighlight['kind'][]): string[] {
  const out = new Set<string>()
  for (const g of props.routes ?? []) {
    if (!kinds.includes(g.kind)) continue
    for (const id of g.segments) out.add(id)
  }
  return [...out]
}

function routeFilterOf(...kinds: RouteHighlight['kind'][]): FilterSpecification {
  return ['in', ['get', 'segment_id'], ['literal', routeIdsOf(...kinds)]]
}

/** 任一组路线存在时才在图上画图例三行（否则不占地方） */
const hasRoutes = computed(() => (props.routes ?? []).some((g) => g.segments.length > 0))

/**
 * 本组件自有的图层（按绘制顺序：底衬 → 热力 → 色线 → 路线 → 选中）。
 * 同一份规格用在两处：建图时按顺序 `addLayer`；底图样式合进来时作为 `layers` 尾部一起挂载
 * —— **两处只有一份定义**，不会出现"底图在/不在时路网长得不一样"。
 */
function lineLayerSpecs(): LineLayerSpecification[] {
  return [
    // 白色描边底衬：让彩色路段在浅底图上分得开（与自绘视图同一手法）
    {
      id: LAYER_CASING,
      type: 'line',
      source: SRC,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#FFFFFF', 'line-width': widthExpr(11, 9) },
    },
    // 热力晕染：只指数视图有值；四级视图 heat 恒 0，等于不画
    {
      id: LAYER_HEAT,
      type: 'line',
      source: SRC,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': ['get', 'color'],
        'line-width': widthExpr(26, 22),
        'line-opacity': ['get', 'heat'],
      },
    },
    {
      id: LAYER_LINE,
      type: 'line',
      source: SRC,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': ['get', 'color'],
        'line-width': widthExpr(5.5, 4.5),
        'line-opacity': ['case', ['==', ['get', 'covered'], false], 0.4, 1],
      },
    },
    // 备选路线：灰虚线（在推荐 / 离站下面画，避免盖住主路线）
    {
      id: LAYER_ROUTE_ALT_HALO,
      type: 'line',
      source: SRC,
      filter: routeFilterOf('alternative'),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#FFFFFF', 'line-width': 10, 'line-opacity': 0.7 },
    },
    {
      id: LAYER_ROUTE_ALT,
      type: 'line',
      source: SRC,
      filter: routeFilterOf('alternative'),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': ROUTE_ALT_COLOR,
        'line-width': 3,
        'line-dasharray': [9, 7],
        'line-opacity': 0.95,
      },
    },
    // 离站路线：紫色实线（第三语义色；不与推荐蓝、等级色混用）
    {
      id: LAYER_ROUTE_DEP_HALO,
      type: 'line',
      source: SRC,
      filter: routeFilterOf('departure'),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#FFFFFF', 'line-width': 11, 'line-opacity': 0.7 },
    },
    {
      id: LAYER_ROUTE_DEP,
      type: 'line',
      source: SRC,
      filter: routeFilterOf('departure'),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': ROUTE_DEPART_COLOR, 'line-width': 3, 'line-opacity': 0.92 },
    },
    // 推荐路线：品牌蓝（「推荐」语义，不得用等级色）——实线，最上层
    {
      id: LAYER_ROUTE_HALO,
      type: 'line',
      source: SRC,
      filter: routeFilter(),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': BRAND, 'line-width': 17, 'line-opacity': 0.16 },
    },
    {
      // ⚠️ 实线与旧版虚线的差别：IKMF1W 起推荐路线用**品牌蓝实线**（"当前 / 已选"语义），
      //    备选才是灰虚线；旧版把"推荐"画成虚线，和"选中路段"的虚线语义撞车。
      id: LAYER_ROUTE,
      type: 'line',
      source: SRC,
      filter: routeFilter(),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': BRAND, 'line-width': 3.4, 'line-opacity': 0.95 },
    },
    // 选中路段描边：品牌蓝（「当前 / 已选」语义），虚线，不覆盖判级色
    {
      id: LAYER_SELECTED,
      type: 'line',
      source: SRC,
      filter: selectedFilter(),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': BRAND, 'line-width': 2.4, 'line-dasharray': [4, 6], 'line-opacity': 0.9 },
    },
  ]
}

function addRouteLayers(map: MapLibreMap): void {
  if (map.getSource(SRC)) return
  map.addSource(SRC, { type: 'geojson', data: routeGeoJson() })
  for (const spec of lineLayerSpecs()) map.addLayer(spec)
}

// ---- 摄像头布点 ----

/** 摄像头标记（重绘 / 卸载时移除） */
let camMarkers: Marker[] = []
/** 被悬停的摄像头（浮牌钉在图钉上方，与路段浮牌区分） */
const pin = ref<CameraPin | null>(null)

/**
 * 摄像头布点（Issue IKLX5Y）：位置取站点包 `channels[].lon/lat`（落在该段折线上的示意点，
 * **不是路测点位**），点击跳到感知层对应通道。
 * 实心 = 有视频源、空心 = 未接入视频源（本期留空）——两件事在页面上要分开说。
 */
function addCameraPins(map: MapLibreMap): void {
  for (const p of pins) {
    const el = document.createElement('div')
    el.className = p.hasVideo ? 'cam-pin' : 'cam-pin empty'
    el.textContent = p.cid.replace('C-', '')
    el.title = `${p.cid} ${p.name} · ${p.segment_id} · ${
      p.hasVideo ? '有视频源' : '未接入视频源 · 本期留空'
    } · 点击进感知层`
    el.addEventListener('mouseenter', () => {
      pin.value = p
    })
    el.addEventListener('mouseleave', () => {
      pin.value = null
    })
    el.addEventListener('click', () => {
      window.location.href = perceptionHref(p.source)
    })
    camMarkers.push(new Marker({ element: el }).setLngLat([p.lon, p.lat]).addTo(map))
  }
}

// ---- 车辆动点（自绘视图搬来：`transform` 过渡 = 平滑移动） ----

const VEH_LABEL: Record<DriverType, string> = {
  D1: '送客车辆',
  D2: '接客车辆',
  D3: '往返车辆(出租车 / 网约车)',
}

// 图例**由 DRIVER_COLORS 生成**，不手写行——否则新增司机类型时地图画了、图例却漏
const VEH_LEGEND = (Object.keys(DRIVER_COLORS) as DriverType[]).map((t) => ({
  t,
  color: DRIVER_COLORS[t],
  label: VEH_LABEL[t],
}))

const vehMarkers = new Map<string, { marker: Marker; el: HTMLDivElement }>()

function syncVehicles(map: MapLibreMap | null): void {
  if (!map || !ready.value) return
  const alive = new Set<string>()
  for (const v of props.vehicles ?? []) {
    alive.add(v.vehicle_id)
    const existing = vehMarkers.get(v.vehicle_id)
    if (existing) {
      existing.marker.setLngLat([v.lon, v.lat])
      existing.el.title = `${v.vehicle_id} · ${v.state} · ${v.segment_id}${
        v.is_demo_bound ? ' · 演示绑定车' : ''
      }`
      continue
    }
    const el = document.createElement('div')
    el.className = 'veh-dot'
    el.style.background = DRIVER_COLORS[v.driver_type]
    el.title = `${v.vehicle_id} · ${v.state} · ${v.segment_id}${v.is_demo_bound ? ' · 演示绑定车' : ''}`
    // 首帧不要过渡：否则新车会从左上角滑进来
    el.style.transition = 'none'
    requestAnimationFrame(() => {
      el.style.transition = 'transform 1.9s linear'
    })
    const marker = new Marker({ element: el }).setLngLat([v.lon, v.lat]).addTo(map)
    vehMarkers.set(v.vehicle_id, { marker, el })
  }
  for (const [id, item] of vehMarkers) {
    if (alive.has(id)) continue
    item.marker.remove()
    vehMarkers.delete(id)
  }
}

// ---- 取景 ----

/** 视野适配到整张路网（边界留白，避免线贴边） */
function fitToNetwork(map: MapLibreMap): void {
  const lons = net.flatMap((s) => s.coords.map((c) => c[0]))
  const lats = net.flatMap((s) => s.coords.map((c) => c[1]))
  if (lons.length === 0) return
  map.fitBounds(
    [
      [Math.min(...lons), Math.min(...lats)],
      [Math.max(...lons), Math.max(...lats)],
    ],
    { padding: 56, duration: 0 },
  )
}

// ---- 底图：异步、可失败、失败只丢自己 ----

/**
 * 把 OpenFreeMap 的样式与**本组件自己的图层**合成一份再挂载。
 *
 * 为什么不用 `map.setStyle(STYLE_URL)` 直接换：那会把路网图层一起冲掉，
 * 换完还得"再挂一遍"，中间那段时间图上什么都没有 —— 正是本单要避免的状态。
 * 合成后再切，路网在整份样式里，从一开始就在。
 */
function mergedStyle(remote: StyleSpecification): StyleSpecification {
  return {
    ...remote,
    sources: { ...(remote.sources ?? {}), [SRC]: { type: 'geojson', data: routeGeoJson() } },
    layers: [...(remote.layers ?? []), ...lineLayerSpecs()],
  }
}

/** 把底图那一层**整层撤掉**：样式换回"本地兜底 + 本组件图层"，路网一行不动 */
function dropBasemap(map: MapLibreMap): void {
  window.clearTimeout(retryTimer)
  if (!remoteApplied) return // 本来就是"只有路网"，不必再换一次样式
  remoteApplied = false
  map.once('styledata', () => {
    if (disposed) return
    fitToNetwork(map)
    applyViewState(map)
  })
  map.setStyle(mergedStyle(FALLBACK_STYLE), { diff: false })
}

/** 失败后按 2s / 6s / 12s 退避自动重试（最多三次）；开关关掉或组件卸载即停 */
function scheduleRetry(map: MapLibreMap): void {
  if (retryStep >= RETRY_DELAYS_MS.length) return
  const delay = RETRY_DELAYS_MS[retryStep]
  retryStep++
  retryTimer = window.setTimeout(() => {
    if (!disposed) void applyBasemap(map, { retry: true })
  }, delay)
}

/** 手动「重试」（角标上的按钮）：计数清零，立刻再拉一次 */
function retryBasemap(): void {
  const map = mapRef.value
  if (!map || !ready.value) return
  retryStep = 0
  void applyBasemap(map, { retry: true })
}

/**
 * 拉底图并合入。四件事按顺序判：
 *   ① 设置里关着 → **一个请求都不发**，把已有的底图层撤掉；
 *   ② 样式拉到了 → 与**本组件自己的图层规格**合成一份 style 再挂载（路网在整份样式里，不会中途空窗）；
 *   ③ **瓦片真的就绪** → 才把状态写成 `ok`；
 *   ④ 任何一步拉不到 → 退回兜底样式（路网照画），角标给原因 + 「重试」，并按退避自动重试。
 *
 * 为什么不用 `map.setStyle(STYLE_URL)` 直接换：那会把路网图层一起冲掉，换完还得"再挂一遍"，
 * 中间那段时间图上什么都没有 —— 正是本单要避免的状态。
 *
 * ⚠️ ③ 不是多余的：本机实测过"样式命中 HTTP 缓存 3 ms 返回 200，而 tilejson / `.pbf` 全部挂到超时"
 * —— 那时地图只剩 Liberty 样式里的底色层（没有路、没有建筑），单看②就报"底图正常"是**假的**。
 *
 * `retry: true` = 失败后的再试：**状态留在 `failed`**，只把按钮文案换掉（见 `basemapRetrying`）。
 */
async function applyBasemap(map: MapLibreMap, opts: { retry?: boolean } = {}): Promise<void> {
  window.clearTimeout(retryTimer)
  if (!basemapEnabled.value) {
    // 关开关：在途的那一次也掐掉，别让"不发任何底图请求"只在冷启动成立
    inflightCtrl?.abort()
    inflightCtrl = null
    basemap.value = 'off'
    basemapRetrying.value = false
    dropBasemap(map)
    return
  }
  if (opts.retry) basemapRetrying.value = true
  else basemap.value = 'loading'
  const run = ++basemapRun
  const stale = () => disposed || run !== basemapRun || !basemapEnabled.value
  const ctrl = new AbortController()
  inflightCtrl = ctrl
  const timer = window.setTimeout(() => ctrl.abort(), BASEMAP_TIMEOUT_MS)
  try {
    const res = await fetch(toBasemapUrl(STYLE_URL), { signal: ctrl.signal })
    if (!res.ok) throw new Error(`样式 http ${res.status}`)
    const remote = (await res.json()) as StyleSpecification
    if (remote?.version !== 8 || !remote.sources || !Array.isArray(remote.layers)) {
      throw new Error('样式形状不对')
    }
    if (stale()) return
    // 换样式后重新取景 + 重贴选中态；车辆与摄像头是 DOM Marker，不受影响。
    // ⚠️ 监听要先挂再 `setStyle` —— 反过来万一 styledata 已同步派发就漏掉了。
    map.once('styledata', () => {
      if (disposed) return
      fitToNetwork(map)
      applyViewState(map)
    })
    map.setStyle(mergedStyle(remote), { diff: false })
    remoteApplied = true
    if (!(await waitForBasemapTiles(map, remote, stale))) {
      throw new Error('瓦片拉取超时')
    }
    if (stale()) return
    basemap.value = 'ok'
    basemapRetrying.value = false
    retryStep = 0
  } catch (e) {
    if (stale()) return
    basemap.value = 'failed'
    basemapRetrying.value = false
    // 样式已经挂上去过（②之后才失败）→ 退回去，别留着"只有底色"的半张底图
    if (remoteApplied) dropBasemap(map)
    basemapMsg.value = e instanceof Error ? e.message : '拉取失败'
    if (e instanceof Error && e.name === 'AbortError') basemapMsg.value = '拉取超时'
    scheduleRetry(map)
  } finally {
    window.clearTimeout(timer)
    if (inflightCtrl === ctrl) inflightCtrl = null
  }
}

/** 这份样式里"要从公网拉瓦片"的源（geojson 是我们自己的路网，不算） */
function tileSourceIds(remote: StyleSpecification): string[] {
  return Object.entries(remote.sources ?? {})
    .filter(([, spec]) => (spec as { type?: string })?.type !== 'geojson')
    .map(([id]) => id)
}

/**
 * 等底图瓦片真的就绪（轮询 `isSourceLoaded`）。到点还没就绪 → `false`。
 * 轮询而不是挂 `sourcedata` 监听：事件只在"有变化"时来，黑洞代理下可能**一个都不来**。
 */
async function waitForBasemapTiles(
  map: MapLibreMap,
  remote: StyleSpecification,
  stale: () => boolean,
): Promise<boolean> {
  const ids = tileSourceIds(remote)
  if (ids.length === 0) return true
  const deadline = Date.now() + BASEMAP_TILES_TIMEOUT_MS
  while (Date.now() < deadline) {
    if (stale()) return false
    const present = new Set(Object.keys(map.getStyle()?.sources ?? {}))
    if (ids.every((id) => present.has(id) && map.isSourceLoaded(id))) return true
    await new Promise((r) => window.setTimeout(r, 300))
  }
  return false
}

/** 数据/选中/路线变化后，把视图状态贴回图层（换样式之后也要重贴一次） */
function applyViewState(map: MapLibreMap): void {
  const src = map.getSource(SRC) as GeoJSONSource | undefined
  if (src) void src.setData(routeGeoJson())
  if (map.getLayer(LAYER_SELECTED)) map.setFilter(LAYER_SELECTED, selectedFilter())
  if (map.getLayer(LAYER_ROUTE)) map.setFilter(LAYER_ROUTE, routeFilter())
  if (map.getLayer(LAYER_ROUTE_HALO)) map.setFilter(LAYER_ROUTE_HALO, routeFilter())
}

// ---- 交互：点击选中 / 悬停即切换选中 + 浮牌跟随 ----

const mouse = ref<{ x: number; y: number } | null>(null)
/** 地图移动/缩放后要重算浮牌落点（`map.project()` 不是响应式的） */
const camTick = ref(0)

function hoveredSegmentId(map: MapLibreMap, point: MapMouseEvent['point']): string | null {
  if (!map.getLayer(LAYER_LINE)) return null
  const hit = map.queryRenderedFeatures(point, { layers: [LAYER_LINE] })
  const id = hit?.[0]?.properties?.segment_id
  return typeof id === 'string' && id ? id : null
}

function onMapMouseMove(e: MapMouseEvent): void {
  const map = mapRef.value
  if (!map) return
  mouse.value = { x: e.point.x, y: e.point.y }
  const id = hoveredSegmentId(map, e.point)
  map.getCanvas().style.cursor = id ? 'pointer' : ''
  // 悬停即切换选中（业主 2026-10-14：不要"靠点击才切换"）——浮牌据此吸附在当前路段上
  if (id && id !== props.selectedId) emit('select', id)
}

function onMapMouseOut(): void {
  mouse.value = null
}

function onMapClick(e: MapMouseEvent): void {
  const map = mapRef.value
  if (!map) return
  const id = hoveredSegmentId(map, e.point)
  if (id) emit('select', id)
}

/** 跟随鼠标的信息浮牌落点 = 选中路段折线上离鼠标最近的采样点（沿线走，鼠标离开线也不消失） */
const chipStyle = computed(() => {
  const map = mapRef.value
  const m = mouse.value
  void camTick.value // 地图动过就重算
  if (!map || !m || !props.selectedId || !props.hoverChip) return {}
  const seg = net.find((s) => s.segment_id === props.selectedId)
  if (!seg) return {}
  let best = map.project(seg.coords[0] as [number, number])
  let bestD = Number.POSITIVE_INFINITY
  for (const c of seg.coords) {
    const p = map.project(c as [number, number])
    const d = (p.x - m.x) ** 2 + (p.y - m.y) ** 2
    if (d < bestD) {
      bestD = d
      best = p
    }
  }
  const w = containerRef.value?.clientWidth ?? 0
  const flipX = best.x + CHIP_W + 18 > w
  const flipY = best.y - CHIP_H - 14 < 0
  return {
    left: `${flipX ? best.x - CHIP_W - 14 : best.x + 14}px`,
    top: `${flipY ? best.y + 16 : best.y - CHIP_H - 12}px`,
  }
})

/** 摄像头浮牌落点 = 图钉正上方（钉在图钉上，不跟鼠标） */
const camChipStyle = computed(() => {
  const map = mapRef.value
  const p = pin.value
  void camTick.value
  if (!map || !p) return {}
  const pt = map.project([p.lon, p.lat])
  return { left: `${Math.max(6, pt.x - 96)}px`, top: `${Math.max(6, pt.y - 62)}px` }
})

// ---- 建图 ----

let disposed = false

/**
 * 探一下 dev/preview 上那条**底图同源直通**路由在不在（见 `shared/basemap.ts` 头部）。
 *
 * 为什么要探而不是"配个 env 开关了事"：生产构建里根本没有这条路由，写死同源前缀会让线上
 * 底图 100% 404；而"按 mode 分支"又管不到 `vite preview` 看 dist 的场景。探一下最省事：
 * 拿到 JSON 就是挂了，拿到 HTML（SPA 回退的 index.html）或超时就当没挂，回落直连上游。
 *
 * 探测失败**不影响建图**：它就是一次 1.5 s 上限的请求，拿不到就照旧走公网。
 */
async function detectBasemapProxy(): Promise<void> {
  const ctrl = new AbortController()
  const timer = window.setTimeout(() => ctrl.abort(), BASEMAP_PROBE_TIMEOUT_MS)
  try {
    const res = await fetch(BASEMAP_PROXY_PROBE, { signal: ctrl.signal, cache: 'no-store' })
    if (!res.ok) return
    const body = (await res.json()) as { ok?: boolean }
    setBasemapProxyDetected(body?.ok === true)
  } catch {
    setBasemapProxyDetected(false)
  } finally {
    window.clearTimeout(timer)
  }
}

function initMap(): void {
  if (!containerRef.value) return
  const map = new MapLibreMap({
    container: containerRef.value,
    // ⚠️ 起手是**本地兜底样式**：路网据此立刻画出来，不等公网（本单的核心）
    style: FALLBACK_STYLE,
    center: [112.657, 23.215],
    zoom: 14,
    // 底图那几类请求（样式 / tilejson / 瓦片 / sprite / 字形）统一过一遍地址改写：
    // 探到同源直通就换成本地前缀（绕开系统代理），没探到就原样返回。
    transformRequest: (url) => ({ url: toBasemapUrl(url) }),
    // 不隐藏默认署名控件：OSM/ODbL 要求署名（见文件头「合规」）
  })
  mapRef.value = map
  map.addControl(new NavigationControl({ visualizePitch: true }), 'top-right')
  // 比例尺放右下（左下角留给图例）
  map.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-right')

  map.on('load', () => {
    addRouteLayers(map)
    addCameraPins(map)
    fitToNetwork(map)
    ready.value = true
    // 车辆要在 ready 之后再同步（`syncVehicles` 以 ready 为前置）
    syncVehicles(map)
    map.on('move', () => {
      camTick.value++
    })
    map.on('mousemove', onMapMouseMove)
    map.on('mouseout', onMapMouseOut)
    map.on('click', onMapClick)
    // 底图**随后**再拉（设置里关着就一个请求都不发）：成功就把底图合进来，失败就保持"只有路网"
    void applyBasemap(map)
  })

  // 单块瓦片失败是常态噪声，不打扰用户；这里只留一个不遮挡地图的状态角标
}

// ---- 响应式：数据 / 模式 / 选中 / 路线 / 车辆 ----

watch(
  () => [props.segments, props.mode] as const,
  () => {
    const map = mapRef.value
    if (!map || !ready.value) return
    applyViewState(map)
  },
)

watch(
  () => props.selectedId,
  () => {
    const map = mapRef.value
    if (!map || !ready.value || !map.getLayer(LAYER_SELECTED)) return
    map.setFilter(LAYER_SELECTED, selectedFilter())
  },
)

/**
 * 路线高亮按**内容**监听，不按数组引用：父组件传的是 computed 产物，快照刷新时会重建引用，
 * 按引用监听的写法会在每次刷新时白跑一遍 `setFilter`。
 */
const routeKey = computed(() =>
  (props.routes ?? []).map((g) => `${g.kind}:${g.segments.join(',')}`).join('|'),
)

watch(routeKey, () => {
  const map = mapRef.value
  if (!map || !ready.value) return
  const updates: [string, FilterSpecification][] = [
    [LAYER_ROUTE, routeFilter()],
    [LAYER_ROUTE_HALO, routeFilter()],
    [LAYER_ROUTE_ALT, routeFilterOf('alternative')],
    [LAYER_ROUTE_ALT_HALO, routeFilterOf('alternative')],
    [LAYER_ROUTE_DEP, routeFilterOf('departure')],
    [LAYER_ROUTE_DEP_HALO, routeFilterOf('departure')],
  ]
  for (const [id, filter] of updates) {
    if (map.getLayer(id)) map.setFilter(id, filter)
  }
})

/** 顶栏「设置」里的底图开关：开 → 拉底图；关 → 撤掉底图层（路网一行不动） */
watch(basemapEnabled, () => {
  const map = mapRef.value
  if (!map || !ready.value) return
  retryStep = 0
  void applyBasemap(map)
})

watch(
  () => props.vehicles,
  () => {
    syncVehicles(mapRef.value)
  },
)

onMounted(async () => {
  // 容器始终在 DOM 里，nextTick 只为确保布局尺寸已就绪（尺寸为 0 时地图会渲染成空白）
  await nextTick()
  // 先探代理再建图：`applyBasemap` 的第一次样式请求也要走同源直通（探测本身有 1.5 s 上限）
  await detectBasemapProxy()
  initMap()
})

onUnmounted(() => {
  disposed = true
  window.clearTimeout(retryTimer)
  inflightCtrl?.abort()
  camMarkers.forEach((m) => m.remove())
  camMarkers = []
  vehMarkers.forEach((v) => v.marker.remove())
  vehMarkers.clear()
  mapRef.value?.remove()
  mapRef.value = null
  ready.value = false
})
</script>

<template>
  <div class="mlmap">
    <div ref="containerRef" class="mlmap-canvas" />

    <!-- 底图状态角标：**只占一个小角、不覆盖地图** —— 底图拉不出来（或设置里关掉）时路网照样看。
         旧版是一块 inset:0 的整屏遮罩，会把路网一起盖住。 -->
    <div v-if="basemap !== 'ok'" class="basemap-note">
      <template v-if="basemap === 'off'">底图已关闭（顶栏「设置」里可开）· 只画路网</template>
      <template v-else-if="basemap === 'loading'">底图加载中…</template>
      <template v-else>
        <span>底图不可用（{{ basemapMsg }}）· 路网照画</span>
        <!-- ⚠️ 按钮**文案不许变**：自动重试时若在「重试 / 重试中…」之间改文案，按钮宽度跟着变，
             CDP 端会一直判它 "element is not stable"（实测点了 30 s 点不上）。
             所以「正在重试…」另起一个 span，按钮只切换 disabled（只改透明度，不改尺寸）。 -->
        <span v-if="basemapRetrying" class="basemap-retrying">正在重试…</span>
        <button type="button" class="basemap-retry" :disabled="basemapRetrying" @click="retryBasemap">
          重试
        </button>
      </template>
    </div>

    <!-- 来源口径水印（自绘视图搬来） -->
    <div class="watermark">{{ sourceLabel }}</div>

    <!-- 路网 OSM 署名：单独一份，**底图挂了也仍在**（E-11 / E-13） -->
    <div v-if="osmActive" class="attribution">
      <a :href="OSM_COPYRIGHT_URL" target="_blank" rel="noopener">{{ OSM_ATTRIBUTION }}</a>
    </div>

    <!-- 摄像头浮牌（悬停图钉时；与路段浮牌是两套，不混） -->
    <div v-if="pin" class="cam-chip" :style="camChipStyle">
      <b>{{ pin.cid }}</b> {{ pin.name }}
      <span class="cam-chip-sub">
        {{ pin.segment_id }} · {{ pin.hasVideo ? '有视频源' : '未接入视频源 · 本期留空' }} · 点击进感知层
      </span>
    </div>

    <!-- 跟随鼠标的信息浮牌：吸附在当前选中路段上，沿线走 -->
    <div v-if="mouse && hoverChip" class="hover-chip" :style="chipStyle">
      {{ hoverChip }}
    </div>

    <!-- 图例（自绘视图搬来；index 视图是色阶版，level 视图是四级版） -->
    <div v-if="legend" class="legend">
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
        <div v-for="v in VEH_LEGEND" :key="v.t" class="lg-row">
          <span class="dot" :style="{ background: v.color }" />{{ v.t }} {{ v.label }}
        </div>
        <div class="lg-row ts">更新 {{ props.ts || '—' }}</div>
      </template>
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
        <!-- IKMF1W：路线三种语义的图例（有路线时才出现） -->
        <template v-if="hasRoutes">
          <div class="lg-sep" />
          <div class="lg-row"><span class="lg-line recommended" />推荐路线（品牌蓝实线）</div>
          <div class="lg-row"><span class="lg-line alternative" />备选路线（灰虚线）</div>
          <div class="lg-row"><span class="lg-line departure" />离站路线（紫色实线）</div>
          <div class="lg-note">演示路线：连通段序列拼接，不随时间重算</div>
        </template>
        <!-- 「只摄像头段上色」的图例（Issue IKLX5Y）：说清灰轮廓 = 这段没监控 -->
        <template v-if="cameraOnly">
          <div class="lg-sep" />
          <div class="lg-row"><span class="dot cam-dot" />摄像头布点（点击进感知层）</div>
          <div class="lg-row"><span class="dot cam-dot empty" />摄像头 · 未接入视频源</div>
          <div class="lg-note">未挂摄像头的路段只画灰轮廓、不上色</div>
        </template>
      </template>
    </div>
  </div>
</template>

<style scoped>
.mlmap {
  position: relative;
  width: 100%;
  height: 100%;
  background: #f7f8fa;
  border-radius: 6px;
  overflow: hidden;
}
.mlmap-canvas {
  width: 100%;
  height: 100%;
}

/* 底图状态角标：小、不挡视线、不响应鼠标；只有里面的「重试」按钮可点（路网才是主角） */
.basemap-note {
  position: absolute;
  top: 10px;
  left: 12px;
  padding: 3px 8px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  font-size: 11px;
  color: #666666;
  pointer-events: none;
  z-index: 3;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.basemap-retry {
  pointer-events: auto;
  padding: 1px 8px;
  font: inherit;
  font-size: 11px;
  color: v-bind('BRAND');
  background: #ffffff;
  border: 1px solid v-bind('BRAND');
  border-radius: 3px;
  cursor: pointer;
}
.basemap-retry:hover {
  background: #eef4ff;
}
.basemap-retry:disabled {
  opacity: 0.6;
  cursor: default;
}
.basemap-retrying {
  color: #999999;
}

/* 来源口径水印（顶部居中偏左，避开右上角的缩放控件与右下角的署名） */
.watermark {
  position: absolute;
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 11px;
  color: #999999;
  pointer-events: none;
  z-index: 2;
}

/* 路网 OSM 署名：**左上角**（图角）——右下角已经有三样东西（MapLibre 自带署名控件、
   比例尺、右下角缩放控件），实测会与自带署名控件重叠 10 px（审查发现，已实测 bounding box）。
   这里改为左上角、且在底图状态角标下方一行，两者不叠。 */
.attribution {
  position: absolute;
  top: 34px;
  left: 12px;
  font-size: 10px;
  color: #666666;
  background: rgba(255, 255, 255, 0.85);
  padding: 1px 4px;
  border-radius: 3px;
  z-index: 2;
}
.attribution a {
  color: #666666;
}

/* 跟随鼠标的信息浮牌：蓝框白底，贴鼠标右上、越界翻面，不挡鼠标 */
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
  z-index: 4;
}

/* 图例：左下角（比例尺已挪到右下，不再打架） */
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
  z-index: 2;
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
.lg-ramp {
  height: 8px;
  border-radius: 2px;
}
.lg-scale {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
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
/* 路线图例：用短线段示意线型（实线 / 虚线 / 第三种颜色） */
.lg-line {
  width: 22px;
  height: 0;
  margin-right: 7px;
  display: inline-block;
  border-top: 3px solid #0052d9;
}
.lg-line.alternative {
  border-top: 3px dashed #8c8c8c;
}
.lg-line.departure {
  border-top: 3px solid #7b61ff;
}
/* 图例里的摄像头小圆点：与外圈同款（实心 = 有视频源、空心 = 未接入） */
.dot.cam-dot {
  background: #37474f;
  border: 1.6px solid v-bind('BRAND');
}
.dot.cam-dot.empty {
  background: #ffffff;
}

/* 车辆动点：从自绘视图搬来 —— transform 过渡 = 平滑移动 */
.veh-dot {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  border: 1.6px solid #ffffff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
}

/* 摄像头浮牌：钉在图钉上方，不跟鼠标 */
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
  z-index: 5;
}
.cam-chip-sub {
  display: block;
  color: #666666;
}

/* MapLibre 自己生成的 DOM 不在 scoped 作用域内，须用 :deep() 才生效。
   署名控件只调字号，**不隐藏、不遮挡**（OSM/ODbL 署名义务）。 */
:deep(.maplibregl-ctrl-attrib) {
  font-size: 10px;
}
:deep(.maplibregl-ctrl-scale) {
  font-size: 10px;
  background: rgba(255, 255, 255, 0.85);
}

/* 摄像头图钉（Issue IKLX5Y）：与自绘视图同款语义 ——
   实心深灰 = 有视频源；空心白底 = 未接入视频源（本期留空）。
   品牌蓝只作描边（「可操作」语义），不当填充色用。
   Marker 的 DOM 由 document.createElement 造，不在 scoped 作用域内，故用 :deep()。 */
:deep(.cam-pin) {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #455a64;
  border: 2px solid v-bind('BRAND');
  color: #ffffff;
  font-size: 10px;
  line-height: 16px;
  text-align: center;
  cursor: pointer;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25);
}
:deep(.cam-pin.empty) {
  background: #ffffff;
  color: #455a64;
}
</style>
