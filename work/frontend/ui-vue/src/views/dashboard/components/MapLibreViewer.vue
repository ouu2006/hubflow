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
  type SymbolLayerSpecification,
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
import type { Feature, FeatureCollection, Point } from 'geojson'
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
  perceptionHref,
  type CameraPin,
} from '../../../shared/cameras'
import { DRIVER_COLORS, TD } from '../../../shared/theme'
import {
  basemapEnabled,
  directionsVisible,
  routeEmphasisEnabled,
} from '../../../shared/settings'
import { activePack, onPackChange, packVersion } from '../../../station-packs/index'
import {
  landmarkKindLabel,
  landmarkPins,
  type PackLandmarkView,
} from '../../../shared/landmarks'
// IKOQEJ：方向标记（只读 enriched 字段；不是判级/契约数据）
import {
  bearingDeg,
  directionKindOf,
  directionOf,
  pointAtFraction,
  type DirectionKind,
} from '../../../shared/directions'
import {
  FLOW_BANDS,
  FLOW_COLOR_NOTE,
  FLOW_MODE_LABEL,
  FLOW_MODE_NOTE,
  flowBandOf,
  flowRangeLabel,
  type ColorMode,
} from '../../../shared/flow'
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
  type RouteEndpointMarker,
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
// IKOQEJ · 方向标记：独立 GeoJSON 点源 + canvas 生成的图标（不依赖字体 glyph ——
// 底图挂掉走本地兜底样式时也能画，不会只剩一根无方向的线）
const DIR_SRC = 'hubflow-direction'
const LAYER_DIRECTION = `${DIR_SRC}-marker`
const DIR_ICON_PREFIX = 'hubflow-dir-'
/** 方向语义色（与拥堵等级色 / 品牌蓝 / 路线三态色都不撞）：只表示方向，不表示拥堵 */
const DIR_COLORS: Record<DirectionKind, string> = {
  forward: '#1D5FD8',
  backward: '#B45309',
  bidirectional: '#6D28D9',
  unknown: '#8B8B8B',
}
const LAYER_HEAT = `${SRC}-heat`
const LAYER_CASING = `${SRC}-casing`
const LAYER_LINE = `${SRC}-line`
/** 推荐路线（品牌蓝实线；「当前 / 已选」语义，不得用等级色） */
const LAYER_ROUTE_HALO = `${SRC}-route-halo`
const LAYER_ROUTE = `${SRC}-route`
/**
 * 备选 1 / 备选 2（Issue IKP5CK）：两条备选必须**互相可区分**（原来一起画灰虚线）。
 * 分两个图层而不是一个「按属性取色」的图层：两者的**虚线节律 + 平行偏移**也不同，
 * 叠在同一段路时靠「颜色 + 节律 + ±2px 平行线」三重区分，不只靠颜色单通道。
 */
const LAYER_ROUTE_ALT1_HALO = `${SRC}-route-alt1-halo`
const LAYER_ROUTE_ALT1 = `${SRC}-route-alt1`
const LAYER_ROUTE_ALT2_HALO = `${SRC}-route-alt2-halo`
const LAYER_ROUTE_ALT2 = `${SRC}-route-alt2`
/** 离站路线（紫色实线；第三种语义色，与等级色 / 品牌蓝分开） */
const LAYER_ROUTE_DEP_HALO = `${SRC}-route-dep-halo`
const LAYER_ROUTE_DEP = `${SRC}-route-dep`
const LAYER_SELECTED = `${SRC}-selected`

/**
 * 备选 1 = 青 `#0E7490`、备选 2 = 琥珀 `#B45309`（队长 2026-10-20 裁定）：
 * 两色都避开四级判级色（#2BA471 / #E9B32E / #E37318 / #D54941）、
 * 数据不可用灰 #8B8B8B、品牌蓝 #0052D9、离站紫 #7B61FF。
 * 虚线节律再分一套：备选 1 长虚（12/6）、备选 2 短虚（2.5/4.5）。
 */
const ROUTE_ALT1_COLOR = '#0E7490'
const ROUTE_ALT2_COLOR = '#B45309'
/** 离站路线色（紫色；与品牌蓝 / 四级色都不撞，只表示"第 3 种路线语义"） */
const ROUTE_DEPART_COLOR = '#7B61FF'
/**
 * 「凸显路线」时非路线段的中性灰（Issue IKP5CK）。
 * 必须与「数据不可用灰」#8B8B8B 视觉可区分：更浅（#C9CDD4）、更细（2 px vs 5.5 px）、
 * 透明度更低（0.55）、**不加虚线**；且只有路线存在、开关打开时才生效。
 */
const ROUTE_EMPHASIS_GRAY = '#C9CDD4'

/** 悬停浮牌尺寸（只用于翻面判断，与 CSS 里的 min/max-width 对应） */
const CHIP_W = 210
const CHIP_H = 26
/** 摄像头浮牌宽度（与 <style> 中 .cam-chip 的 width 保持一致；窄屏 CSS 会用 min() 收小） */
const CAM_CHIP_W = 192
/** 落客点 / 场区浮牌宽度（与 <style> 中 .lm-chip 的 width 保持一致；窄屏同样用 min() 收小） */
const LM_CHIP_W = 220

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
    /** 路线起点标注（业主 2026-10-21：大道最外侧路段 = 起点） */
    routeStart?: RouteEndpointMarker | null
    /** 路线终点标注（停车场落客点 = 终点） */
    routeEnd?: RouteEndpointMarker | null
    mode?: MapMode
    /**
     * 颜色模式（Issue IKNB9G）：
     *   `congestion`（默认）= 决策拥堵 level 四级配色；
     *   `flow` = 纯车流量 q_vph 四档配色（仅展示，不参与判级；有 q 的段都上色，缺 q / 陈旧灰档）。
     */
    colorMode?: ColorMode
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
    routeStart: null,
    routeEnd: null,
    mode: 'level',
    colorMode: 'congestion',
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
 * 路网几何与来源口径（Issue IKPFR4：**随包变化**）。
 *
 * 以前这里是 setup 期的两个常量（`DEMO_NETWORK.segments` / `networkSourceLabel()`），
 * 切站只能靠整页刷新把它们重拍一遍。现在改成 `shallowRef` + 订阅：
 * 切站时 `switchStation()` 已把几何按新包重建，这里的订阅只负责**换引用**，
 * 真正重绘由下面的 `watch(packTick)` 完成（只换 GeoJSON data，不重建 Map、不 setStyle）。
 *
 * ⚠️ 用 `shallowRef` 而不是 `ref`：`DemoSegment` 是几百到几千条折线的纯数据，
 *    深响应式代理在这里纯属浪费，而且地图本来也不靠逐点响应式（我们自己 setData）。
 */
const net = shallowRef<DemoSegment[]>(DEMO_NETWORK.segments)

/**
 * 包键代号：切站时 +1。所有"读 activePack() 的 computed / 一次性快照"都靠它刷新。
 * 注意 `packVersion()` 是模块级**数字**，不是 Vue 的 ref —— 所以这里自己建一个 ref 订阅。
 */
const packTick = ref(packVersion())
const offPackTick = onPackChange(() => {
  packTick.value = packVersion()
})

const sourceLabel = computed(() => {
  void packTick.value
  return networkSourceLabel()
})
const osmActive = computed(() => {
  void packTick.value
  return isOsmNetwork()
})
/**
 * 上色策略由站点包 `colorPolicy` 决定（IKP5DM 起 Z/GZ 均为 `'all'`：全段按等级上色，
 * 灰只表示数据不可用/陈旧，不再表示「这段没摄像头」）。
 * 图钉与上色策略**解耦**：图钉只画源台账 6 路，图例按 `pins.length` 显隐（见模板）。
 */
/** 摄像头图钉（随包变化：Z 站 6 路源台账 / GZ 站 0 路） */
const pins = computed(() => {
  void packTick.value
  return cameraPins()
})

// ---- 路段染色（四级 / 指数两种视图） ----

const segById = computed(() => new Map(props.segments.map((s) => [s.segment_id, s])))
const isIndex = computed(() => props.mode === 'index')
/** 纯车流量版（Issue IKNB9G）：颜色只看 q_vph 分档，忽略 level / CI / 摄像头覆盖策略 */
const isFlow = computed(() => props.colorMode === 'flow')

/**
 * 该段是否"有可展示的数据"（决定线宽 / 透明度）。
 *   · 拥堵版：沿用「只摄像头段上色」策略（业主 2026-10-15）；色块按 level / CI；
 *   · 流量版：**有 q 且不陈旧**即可上色（流量是全网口径，不受摄像头覆盖限制），缺 q 灰档。
 */
function coveredOf(seg: DemoSegment): boolean {
  if (isFlow.value) return flowBandOf(segById.value.get(seg.segment_id)) !== null
  return isCameraCovered(seg.segment_id)
}

/**
 * 路段色。四档，别混：
 *   ① 流量版：q 四档蓝阶（缺 q / 陈旧 → 灰）；
 *   ② 拥堵版有监控且数据可用 → 等级色 / ci 色阶；
 *   ③ 拥堵版有监控但数据不可用 → 灰（粗，`UNAVAILABLE`）；
 *   ④ 拥堵版**没监控** → 灰（细、淡）——"这段没摄像头"本身是个信息，不能与 ③ 长得一样。
 */
function colorOf(seg: DemoSegment): string {
  const rec = segById.value.get(seg.segment_id)
  if (isFlow.value) {
    return flowBandOf(rec)?.color ?? UNAVAILABLE.color
  }
  if (!isCameraCovered(seg.segment_id)) return UNAVAILABLE.color
  if (!rec) return UNAVAILABLE.color
  return isIndex.value ? ciStyleColor(rec) : levelStyle(rec).color
}

/** 热力晕染强度（仅拥堵版指数视图且 ci 可用；流量版不用 CI 热力，按色阶直读） */
function heatOf(seg: DemoSegment): number {
  if (isFlow.value) return 0
  if (!isCameraCovered(seg.segment_id)) return 0
  const rec = segById.value.get(seg.segment_id)
  if (!rec || !ciAvailable(rec)) return 0
  const v = Math.min(CI_MAX, Math.max(0, rec.ci as number))
  return Math.round((0.1 + (v / CI_MAX) * 0.5) * 100) / 100
}

/**
 * 当前站点包有没有方向字段（Issue IKP5BD 第④条）。
 * 旧 21 段对照包（Z21）没有 `segmentDirections`：整包**一支箭头都不画**，
 * 图例写明「本包无方向字段」——不能像现在这样给每个点画灰 `?`，让人误读成"未标定数据"。
 */
const directionsAvailable = computed<boolean>(() => {
  void packTick.value // 切站后包变了，方向字段有无也跟着变，必须重算
  return Object.keys(activePack().segmentDirections ?? {}).length > 0
})
/** 真正可画 = 包里方向字段在该 + 顶栏「设置」里开关开着 */
const directionDrawable = computed<boolean>(() => directionsAvailable.value && directionsVisible.value)

/**
 * 双向段的箭头横向偏移（米）。取 14 m 而不是几米：默认视野（fitBounds 后约 16~17 档，
 * 1.4~1.6 m/px）下约 9 px，两支反向箭头分列折线两侧还能看出"一来一回"；
 * 再小就会被箭头图标自身盖住。
 */
const DIR_BIDIR_OFFSET_M = 14
/** 双向段两支箭头的沿线位置（中点前后）：不用 0.45/0.55——短段（本包中位约 53 m）会叠在一起 */
const DIR_BIDIR_FRACTIONS: readonly [number, number] = [0.35, 0.65]

/** 沿走向法向偏移一个点（米 → 度；近似平面，只用于展示落点） */
function offsetByNormal(
  point: [number, number],
  bearing: number,
  offsetM: number,
): [number, number] {
  const rad = (bearing * Math.PI) / 180
  // 走向单位向量（东, 北）；右法向 = (cos b, -sin b)
  const east = Math.cos(rad) * offsetM
  const north = -Math.sin(rad) * offsetM
  const lat = point[1] + north / 111_320
  const lon = point[0] + east / (111_320 * Math.cos((point[1] * Math.PI) / 180))
  return [lon, lat]
}

/**
 * 方向标记 GeoJSON（IKOQEJ；Issue IKP5BD 改双向画法）。
 *   · forward/backward → 单箭头（沿走向旋转；backward 加 180°）；
 *   · bidirectional → **中点前后各一支**：两支反向箭头分别偏到折线两侧（法向 ±14 m），
 *     一支顺走向、一支逆走向，形成"有来有回"；不再用单个 `↕` 字形；
 *   · 未标定 → 灰色「?」（只针对**包里有方向字段、该段缺值**的情况）。
 * 包整体缺方向字段 / 开关关掉 → 返回空集合（一支都不画）。
 * 字段只读自站点包（enriched 生成物），不参与判级 / 路线。
 */
function directionGeoJson(): FeatureCollection {
  if (!directionDrawable.value) return { type: 'FeatureCollection', features: [] }
  const features: Feature<Point>[] = []
  for (const seg of net.value) {
    const kind = directionKindOf(directionOf(seg.segment_id))
    const bearing = bearingDeg(seg.coords)
    if (kind === 'bidirectional') {
      DIR_BIDIR_FRACTIONS.forEach((fraction, i) => {
        const base = pointAtFraction(seg.coords, fraction)
        // 第一支偏左、顺走向；第二支偏右、逆走向
        const offset = i === 0 ? DIR_BIDIR_OFFSET_M : -DIR_BIDIR_OFFSET_M
        const [lon, lat] = offsetByNormal(base, bearing, offset)
        const rotate = i === 0 ? bearing : (bearing + 180) % 360
        features.push({
          type: 'Feature',
          properties: {
            segment_id: seg.segment_id,
            dir_kind: kind,
            icon: DIR_ICON_PREFIX + kind,
            rotate,
            // 双向段两支箭头略小（0.8×），否则默认视野下两支图标互相盖住
            icon_scale: 0.8,
          },
          geometry: { type: 'Point', coordinates: [lon, lat] },
        })
      })
      continue
    }
    const rotate = kind === 'backward' ? (bearing + 180) % 360 : bearing
    const [lon, lat] = pointAtFraction(seg.coords, 0.5)
    features.push({
      type: 'Feature',
      properties: {
        segment_id: seg.segment_id,
        dir_kind: kind,
        icon: DIR_ICON_PREFIX + kind,
        rotate,
        icon_scale: 1,
      },
      geometry: { type: 'Point', coordinates: [lon, lat] },
    })
  }
  return { type: 'FeatureCollection', features }
}

/** 用 canvas 生成方向图标（ImageData，不需要字体 glyph 资源） */
function directionIconImage(kind: DirectionKind): ImageData {
  const size = 64
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  if (!ctx) return new ImageData(size, size)
  // Issue IKP5BD：双向段不再用 `↕` 字形 —— 由 `directionGeoJson()` 生成两支单箭头
  // （各自带 rotate、分列折线两侧），图标本身保持单箭头形状，只是染双向语义色。
  const glyph = kind === 'unknown' ? '?' : '↑'
  ctx.clearRect(0, 0, size, size)
  ctx.font = 'bold 44px "Segoe UI Symbol", "Noto Sans Symbols", system-ui, sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  // 白色描边画两遍：压在任意路网色上都能看清
  ctx.lineWidth = 8
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.96)'
  ctx.strokeText(glyph, size / 2, size / 2 + 2)
  ctx.fillStyle = DIR_COLORS[kind]
  ctx.fillText(glyph, size / 2, size / 2 + 2)
  return ctx.getImageData(0, 0, size, size)
}

/** 把四个方向图标注册进当前样式（换样式后要重新注册 —— setStyle 会清空 image 资源） */
function addDirectionImages(map: MapLibreMap): void {
  for (const kind of ['forward', 'backward', 'bidirectional', 'unknown'] as DirectionKind[]) {
    const name = DIR_ICON_PREFIX + kind
    if (!map.hasImage(name)) map.addImage(name, directionIconImage(kind))
  }
}

/** 方向标记图层（symbol + icon，无 text/glyphs 依赖；随地图旋转对齐） */
function directionLayerSpec(): SymbolLayerSpecification {
  return {
    id: LAYER_DIRECTION,
    type: 'symbol',
    source: DIR_SRC,
    layout: {
      'icon-image': ['get', 'icon'],
      // 双向段用 `icon_scale` 收小（0.8×）；单/双向共用同一套随缩放尺寸
      'icon-size': [
        '*',
        ['interpolate', ['linear'], ['zoom'], 12, 0.5, 15, 0.85],
        ['get', 'icon_scale'],
      ],
      'icon-rotate': ['get', 'rotate'],
      'icon-rotation-alignment': 'map',
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
      // 关掉 / 包无方向字段时不画：换样式重建图层也要带上，否则一开底图就又把箭头画回来
      visibility: directionDrawable.value ? 'visible' : 'none',
    },
  }
}

/** 把方向标记显隐贴到图层（开关切换时调用；图层还没建就跳过，建图层时会再带一次） */
function applyDirectionVisibility(map: MapLibreMap): void {
  if (!map.getLayer(LAYER_DIRECTION)) return
  map.setLayoutProperty(
    LAYER_DIRECTION,
    'visibility',
    directionDrawable.value ? 'visible' : 'none',
  )
}

/** 建图 / 换样式后把方向源与图层挂上（源/图层存在则跳过；图标缺则补） */
function addDirectionLayers(map: MapLibreMap): void {
  addDirectionImages(map)
  if (!map.getSource(DIR_SRC)) {
    map.addSource(DIR_SRC, { type: 'geojson', data: directionGeoJson() })
  }
  if (!map.getLayer(LAYER_DIRECTION)) {
    const before = map.getLayer(LAYER_ROUTE_ALT1_HALO) ? LAYER_ROUTE_ALT1_HALO : undefined
    map.addLayer(directionLayerSpec(), before)
  }
  applyDirectionVisibility(map)
}

/**
 * 当前是否处于「凸显路线」：开关开 **且** 真有路线可凸显。
 * 没路线时不能把整张图压灰——那会让人读成"全网数据不可用"。
 */
const routeEmphasisOn = computed<boolean>(
  () => routeEmphasisEnabled.value && hasRoutes.value,
)
/** 任一语义组里的段号（判断"这段是否在路线上"用；同段重复只算一次） */
function routeSegmentIds(): Set<string> {
  const out = new Set<string>()
  for (const g of props.routes ?? []) for (const id of g.segments) out.add(id)
  return out
}

/** 站点包坐标是 WGS-84，**直接喂给 MapLibre** —— 不做任何坐标转换 */
function routeGeoJson(): FeatureCollection {
  const routed = routeSegmentIds()
  const emphasize = routeEmphasisOn.value
  return {
    type: 'FeatureCollection',
    features: net.value.map((seg) => {
      // 非路线段统一压灰（Issue IKP5CK）：不再按 level 上色，改用中性浅灰细线。
      // heat 一并归零——否则指数视图还会在灰线外圈漫出一层等级色，等于没压。
      const emphasisGray = emphasize && !routed.has(seg.segment_id)
      return {
        type: 'Feature' as const,
        properties: {
          segment_id: seg.segment_id,
          name: seg.name,
          kind: seg.kind,
          color: colorOf(seg),
          /** 该段是否有可展示数据（拥堵版=摄像头覆盖；流量版=有 q 且不陈旧）—— 线宽/透明度按它分档 */
          covered: coveredOf(seg),
          /** 热力晕染强度（0 = 不画） */
          heat: emphasisGray ? 0 : heatOf(seg),
          /** 凸显路线时该段不在任何路线上 → 用中性灰细线画（paint 直接读这个属性） */
          emphasis_gray: emphasisGray,
        },
        geometry: { type: 'LineString' as const, coordinates: seg.coords },
      }
    }),
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
 * 推荐 / 离站各一组；备选按序号拆两色，另见 `routeIdsOfAlternative()`（Issue IKP5CK）。
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

/** 备选分组序号（兼容旧调用：没有 `index` 时按备选 1） */
function altIndex(g: RouteHighlight): number {
  return typeof g.index === 'number' && g.index >= 1 ? g.index : 1
}

/**
 * 取「备选 N」的段号：N=1 取 index 1，N=2 取 index ≥2（第 3 条及以后一并按备选 2 画，
 * 不新增第五种颜色；页面只承诺"一主二备"三色可辨）。
 */
function routeIdsOfAlternative(n: 1 | 2): string[] {
  const out = new Set<string>()
  for (const g of props.routes ?? []) {
    if (g.kind !== 'alternative') continue
    const idx = altIndex(g)
    if (n === 1 ? idx !== 1 : idx < 2) continue
    for (const id of g.segments) out.add(id)
  }
  return [...out]
}

function altFilter(n: 1 | 2): FilterSpecification {
  return ['in', ['get', 'segment_id'], ['literal', routeIdsOfAlternative(n)]]
}

/** 任一组路线存在时才在图上画图例（否则不占地方） */
const hasRoutes = computed(() => (props.routes ?? []).some((g) => g.segments.length > 0))
/** 图例里的「备选 N 条」：按实际分组计数，不足 2 条时如实少画（不凑等价路线） */
const altRouteCount = computed(
  () => (props.routes ?? []).filter((g) => g.kind === 'alternative' && g.segments.length > 0).length,
)

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
      paint: {
        'line-color': '#FFFFFF',
        // 压灰段只有 2 px 线，白色底衬也得跟着收细，否则一张灰图上全是粗白边
        'line-width': [
          'case',
          ['==', ['get', 'emphasis_gray'], true],
          3.5,
          widthExpr(11, 9),
        ],
      },
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
        // 「凸显路线」开：非路线段 = 中性浅灰细线（不是 level 色，也不是数据不可用灰）
        'line-color': [
          'case',
          ['==', ['get', 'emphasis_gray'], true],
          ROUTE_EMPHASIS_GRAY,
          ['get', 'color'],
        ],
        'line-width': [
          'case',
          ['==', ['get', 'emphasis_gray'], true],
          2,
          widthExpr(5.5, 4.5),
        ],
        'line-opacity': [
          'case',
          ['==', ['get', 'emphasis_gray'], true],
          0.55,
          ['case', ['==', ['get', 'covered'], false], 0.4, 1],
        ],
      },
    },
    // 备选 1 / 备选 2：青 + 琥珀，长虚 / 短虚，且各偏 ±2 px 成平行线
    // （两条备选叠在同一段时，颜色、节律、平行位置三处都可分辨；Issue IKP5CK）
    {
      id: LAYER_ROUTE_ALT1_HALO,
      type: 'line',
      source: SRC,
      filter: altFilter(1),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#FFFFFF',
        'line-width': 9,
        'line-offset': -2,
        'line-opacity': 0.65,
      },
    },
    {
      id: LAYER_ROUTE_ALT1,
      type: 'line',
      source: SRC,
      filter: altFilter(1),
      layout: { 'line-cap': 'butt', 'line-join': 'round' },
      paint: {
        'line-color': ROUTE_ALT1_COLOR,
        'line-width': 3,
        'line-offset': -2,
        'line-dasharray': [12, 6],
        'line-opacity': 0.95,
      },
    },
    {
      id: LAYER_ROUTE_ALT2_HALO,
      type: 'line',
      source: SRC,
      filter: altFilter(2),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#FFFFFF',
        'line-width': 9,
        'line-offset': 2,
        'line-opacity': 0.65,
      },
    },
    {
      id: LAYER_ROUTE_ALT2,
      type: 'line',
      source: SRC,
      filter: altFilter(2),
      layout: { 'line-cap': 'butt', 'line-join': 'round' },
      paint: {
        'line-color': ROUTE_ALT2_COLOR,
        'line-width': 3,
        'line-offset': 2,
        'line-dasharray': [2.5, 4.5],
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
      //    备选是另一种虚线（IKP5CK 起按备选 1/2 分青、琥珀两色）；旧版把"推荐"画成虚线，
      //    和"选中路段"的虚线语义撞车。
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
  // IKOQEJ：方向标记画在路网之上、路线之下（路线语义仍是最上层）
  addDirectionLayers(map)
}

// ---- 摄像头布点 ----

/** 摄像头标记（重绘 / 卸载时移除） */
let camMarkers: Marker[] = []
/** 被悬停的摄像头（浮牌钉在图钉上方，与路段浮牌区分） */
const pin = ref<CameraPin | null>(null)

/**
 * 图例是否展开（Issue IKP3EV）。≤1180 单列后地图整行变宽，整幅图例会盖住路网主体，
 * 所以窄屏把图例收进可折叠浮层；手机/平板默认收起（地图优先），>1180 该状态不参与样式。
 */
const legendOpen = ref(!(typeof window !== 'undefined' && window.matchMedia('(max-width: 1180px)').matches))

/**
 * 跨断点复位图例开合（Issue IKP3EV 独立审查整改）：上面只在 setup 求值一次，
 * 桌面加载后再把窗口缩到 ≤1180，图例仍保持展开、会盖住地图（需刷新才复位）。
 * 监听 1180 断点：跨入窄屏默认收起（地图优先），跨回桌面默认展开。
 * 用户手动点开/收起的状态在同一个断点区间内不受影响。
 */
const legendMq = typeof window !== 'undefined' ? window.matchMedia('(max-width: 1180px)') : null
function onLegendMqChange(e: MediaQueryListEvent): void {
  legendOpen.value = !e.matches
}
onMounted(() => legendMq?.addEventListener('change', onLegendMqChange))
onUnmounted(() => legendMq?.removeEventListener('change', onLegendMqChange))

/**
 * 摄像头布点（Issue IKLX5Y）：位置取站点包 `channels[].lon/lat`（落在该段折线上的示意点，
 * **不是路测点位**），点击跳到感知层对应通道。
 * ⚠️ 2026-10-18 口径（IKNBT2）：图钉只是**源台账布点**（初始映射），不代表一期摄像头总数——
 * 一期 **N 段 = N 摄像头 = N 视频（演示，mock 复用）**；源台账无布点的段也有演示摄像头与复用视频
 * （见大屏右栏「关联摄像头」卡），不要把"没图钉"读成"没摄像头/没视频"。
 * 实心 = 源台账有**样本视频源**（演示，非本站现场）、空心 = 源台账无独立视频源（画面为演示复用）——
 * "有样本视频"**不得**被读成"数据可用/真实接入"（IKMDKY 口径）。
 */
function addCameraPins(map: MapLibreMap): void {
  for (const p of pins.value) {
    const el = document.createElement('div')
    el.className = p.hasVideo ? 'cam-pin' : 'cam-pin empty'
    el.textContent = p.cid.replace('C-', '')
    el.title = `${p.cid} ${p.name} · ${p.segment_id} · 源台账图钉：${
      p.hasVideo ? '有样本视频源（演示，非本站现场）' : '无独立视频源（演示复用见右栏路段卡）'
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

// ---- 落客点 / 场区（Issue IKP5BZ） ----

/**
 * 落客点 + 场区 Marker（唯一数据源 = 前端站点包，见 `shared/landmarks.ts`）。
 *
 * 与摄像头图钉同族：20 px 左右、细描边、轻投影、悬停出浮牌；
 * 靠**形状 + 颜色**区分：摄像头 = 圆形深灰；落客点 = 圆角方「落」青；
 * 场区（停车场 / 候客 / 蓄车）= 圆角方「场」棕。坐标是路段折线上的**演示点**，
 * 不是踏勘点位——浮牌与列表都标明「演示点」（不新增接口字段、不动 stations/*.json）。
 */
let landmarkMarkers: Marker[] = []
/** 被悬停的落客点 / 场区（浮牌钉在标记上方，与摄像头浮牌是两套） */
const landmarkPin = ref<PackLandmarkView | null>(null)

function landmarkTitle(p: PackLandmarkView): string {
  return `${p.name} · 所属路段 ${p.segment_id || '未标定'}（最近折线推定） · ${p.id} · 演示点`
}

function addLandmarkPins(map: MapLibreMap): void {
  for (const p of landmarkPins()) {
    const el = document.createElement('div')
    el.className = `lm-pin ${p.kind}`
    el.textContent = p.kind === 'dropoff' ? '落' : '场'
    el.title = `${landmarkTitle(p)} · 点击选中该路段`
    el.addEventListener('mouseenter', () => {
      landmarkPin.value = p
    })
    el.addEventListener('mouseleave', () => {
      landmarkPin.value = null
    })
    // 图上点不到路段时，标记本身就是入口：点它选中推定路段
    el.addEventListener('click', (event) => {
      event.stopPropagation()
      if (p.segment_id) emit('select', p.segment_id)
    })
    landmarkMarkers.push(new Marker({ element: el }).setLngLat([p.lon, p.lat]).addTo(map))
  }
}

// ---- 路线起点 / 终点标注（业主 2026-10-21：「大道最外侧路段 = 起点，停车场落客点 = 终点」）----

/**
 * 起 / 终两个 Marker：与摄像头 / 落客点图钉同族（DOM + 悬停 title），
 * 但用**圆底 + 起/终 字**在视觉上置顶，避免与「落」「场」混淆。
 * 只认父组件传进来的展示坐标（父组件按站点包折线 / 落客点算），本组件不做任何路线计算。
 */
let routeEndpointMarkers: Marker[] = []

function updateRouteEndpointMarkers(map: MapLibreMap): void {
  for (const marker of routeEndpointMarkers) marker.remove()
  routeEndpointMarkers = []
  for (const p of [props.routeStart, props.routeEnd]) {
    if (!p) continue
    const el = document.createElement('div')
    el.className = `rt-pin ${p.kind}`
    el.textContent = p.kind === 'start' ? '起' : '终'
    el.title = `${p.label} · ${p.segment_id} · ${p.name}${p.note ? ` · ${p.note}` : ''}`
    el.addEventListener('click', (event) => {
      event.stopPropagation()
      if (p.segment_id) emit('select', p.segment_id)
    })
    routeEndpointMarkers.push(
      new Marker({ element: el, anchor: 'bottom' }).setLngLat([p.lon, p.lat]).addTo(map),
    )
  }
}

/** 落客点 / 场区浮牌落点 = 标记正上方（与摄像头浮牌同一套夹边逻辑，宽度不同） */
const landmarkChipStyle = computed(() => {
  const map = mapRef.value
  const p = landmarkPin.value
  void camTick.value
  if (!map || !p) return {}
  const pt = map.project([p.lon, p.lat])
  const w = containerRef.value?.clientWidth ?? 0
  const half = LM_CHIP_W / 2
  const rawLeft = Math.max(6, pt.x - half)
  const left = w > LM_CHIP_W + 12 ? Math.min(rawLeft, w - LM_CHIP_W - 6) : 6
  return { left: `${left}px`, top: `${Math.max(6, pt.y - 66)}px` }
})

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
  const lons = net.value.flatMap((s) => s.coords.map((c) => c[0]))
  const lats = net.value.flatMap((s) => s.coords.map((c) => c[1]))
  if (lons.length === 0) return
  map.fitBounds(
    [
      [Math.min(...lons), Math.min(...lats)],
      [Math.max(...lons), Math.max(...lats)],
    ],
    {
      // 宽屏时左侧给图例留出 440px：起点多在大道最外侧（路网边缘），不留白会被图例压住。
      padding:
        map.getContainer().clientWidth > 900
          ? { top: 36, right: 56, bottom: 72, left: 440 }
          : 56,
      duration: 0,
    },
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
  // 方向标记插在路线图层之前（与建图时的顺序一致：路网 → 方向标 → 路线 → 选中）
  const own: (LineLayerSpecification | SymbolLayerSpecification)[] = [...lineLayerSpecs()]
  const at = own.findIndex((layer) => layer.id === LAYER_ROUTE_ALT1_HALO)
  own.splice(at < 0 ? own.length : at, 0, directionLayerSpec())
  return {
    ...remote,
    sources: {
      ...(remote.sources ?? {}),
      [SRC]: { type: 'geojson', data: routeGeoJson() },
      [DIR_SRC]: { type: 'geojson', data: directionGeoJson() },
    },
    layers: [...(remote.layers ?? []), ...own],
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
  // 换样式会清空 image 资源：先把方向图标补回去，再更新方向源
  addDirectionImages(map)
  applyDirectionVisibility(map)
  const dirSrc = map.getSource(DIR_SRC) as GeoJSONSource | undefined
  if (dirSrc) void dirSrc.setData(directionGeoJson())
  const src = map.getSource(SRC) as GeoJSONSource | undefined
  if (src) void src.setData(routeGeoJson())
  if (map.getLayer(LAYER_SELECTED)) map.setFilter(LAYER_SELECTED, selectedFilter())
  if (map.getLayer(LAYER_ROUTE)) map.setFilter(LAYER_ROUTE, routeFilter())
  if (map.getLayer(LAYER_ROUTE_HALO)) map.setFilter(LAYER_ROUTE_HALO, routeFilter())
  if (map.getLayer(LAYER_ROUTE_ALT1)) map.setFilter(LAYER_ROUTE_ALT1, altFilter(1))
  if (map.getLayer(LAYER_ROUTE_ALT1_HALO)) map.setFilter(LAYER_ROUTE_ALT1_HALO, altFilter(1))
  if (map.getLayer(LAYER_ROUTE_ALT2)) map.setFilter(LAYER_ROUTE_ALT2, altFilter(2))
  if (map.getLayer(LAYER_ROUTE_ALT2_HALO)) map.setFilter(LAYER_ROUTE_ALT2_HALO, altFilter(2))
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
  const seg = net.value.find((s) => s.segment_id === props.selectedId)
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
  // Issue IKP3EV：旧逻辑只夹左边界，窄地图（≤560 时画布可能只有 340px 宽）上图钉靠右时
  // 192px 的浮牌右缘会被推出画布。这里左右都夹：先保左不越界，再保右不越界。
  const w = containerRef.value?.clientWidth ?? 0
  const half = CAM_CHIP_W / 2
  const rawLeft = Math.max(6, pt.x - half)
  const left = w > CAM_CHIP_W + 12 ? Math.min(rawLeft, w - CAM_CHIP_W - 6) : 6
  return { left: `${left}px`, top: `${Math.max(6, pt.y - 62)}px` }
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
    addLandmarkPins(map)
    updateRouteEndpointMarkers(map)
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
  () => [props.segments, props.mode, props.colorMode] as const,
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

// ---- 原地切站（Issue IKPFR4）----
//
// 切站时**只换数据、不动渲染器**：
//   · 换 `net` 引用（几何已由 `switchStation()` → `resetNetwork()` 按新包重建）；
//   · `applyViewState` 把路网 / 方向两个 GeoJSON source `setData` 成新包几何，重贴全部 filter；
//   · 摄像头图钉 / 落客点场区是 DOM Marker，按新包**重建**（不重建不刷新，几何变了没处贴）；
//   · 重新取景（Z 61 段与 GZ 708 段的经纬度范围完全不同，不取景会停在旧站的视野里看空气）。
//
// ⚠️ 这里**不许** `map.remove()` + 新建 Map，也**不许** `setStyle`：底图瓦片是公共资源，
//    重建一次就是几 MB 重下 + 一次白屏，正是本单要消灭的。路网是自家 GeoJSON，换 data 即可。
function applyPackChange(): void {
  const map = mapRef.value
  net.value = DEMO_NETWORK.segments
  // 悬停浮牌指向的是上一站的图钉/点位，切站即清空（业主裁定：站内状态一律重置）
  pin.value = null
  landmarkPin.value = null
  if (!map || !ready.value || disposed) return
  camMarkers.forEach((m) => m.remove())
  camMarkers = []
  addCameraPins(map)
  landmarkMarkers.forEach((m) => m.remove())
  landmarkMarkers = []
  addLandmarkPins(map)
  // 方向图层：图标已在 map 里（同一套 canvas 图标），只需重贴数据与显隐
  applyViewState(map)
  fitToNetwork(map)
}

watch(packTick, applyPackChange)

/**
 * 路线高亮按**内容**监听，不按数组引用：父组件传的是 computed 产物，快照刷新时会重建引用，
 * 按引用监听的写法会在每次刷新时白跑一遍 `setFilter`。
 */
const routeKey = computed(() =>
  (props.routes ?? [])
    .map((g) => `${g.kind}:${g.index ?? 0}:${g.segments.join(',')}`)
    .join('|'),
)

// 路线变化要连**数据**一起重算：非路线段压灰依赖 feature 属性（emphasis_gray），
// 只换 filter 不够（Issue IKP5CK）。applyViewState 会重贴源数据 + 全部 filter。
watch(routeKey, () => {
  const map = mapRef.value
  if (!map || !ready.value) return
  applyViewState(map)
})

/** 起点 / 终点标注随推荐路线（或手动选起点）变化：重建两个 Marker 即可，不动其他图层。
 *  用**稳定字符串键**而不是数组/对象：数组每次求值都是新引用，会让 watch 在每次渲染都触发，
 *  反复重建 Marker 会把地图拖进渲染循环（表现为整张图空白）。 */
watch(
  () =>
    [
      props.routeStart?.segment_id ?? '',
      props.routeStart?.lon ?? '',
      props.routeStart?.lat ?? '',
      props.routeEnd?.segment_id ?? '',
      props.routeEnd?.lon ?? '',
      props.routeEnd?.lat ?? '',
    ].join('|'),
  () => {
    const map = mapRef.value
    if (!map || !ready.value) return
    updateRouteEndpointMarkers(map)
  },
)

/** 顶栏 / 工具条两个开关：方向标记显隐、凸显路线（压灰） */
watch(directionsVisible, () => {
  const map = mapRef.value
  if (!map || !ready.value) return
  applyViewState(map)
})
watch(routeEmphasisEnabled, () => {
  const map = mapRef.value
  if (!map || !ready.value) return
  applyViewState(map)
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
  offPackTick()
  window.clearTimeout(retryTimer)
  inflightCtrl?.abort()
  camMarkers.forEach((m) => m.remove())
  camMarkers = []
  landmarkMarkers.forEach((m) => m.remove())
  landmarkMarkers = []
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
        {{ pin.segment_id }} · 源台账：{{ pin.hasVideo ? '有样本视频源（演示，非本站现场）' : '无独立视频源（演示复用见右栏路段卡）' }} · 点击进感知层
      </span>
    </div>

    <!-- 落客点 / 场区浮牌（悬停标记时；Issue IKP5BZ）——名称 · 所属路段 · 点位 id，一律标「演示点」 -->
    <div v-if="landmarkPin" class="lm-chip" :style="landmarkChipStyle">
      <b>{{ landmarkPin.name }}</b>
      <span class="lm-chip-sub">
        {{ landmarkKindLabel(landmarkPin.kind) }} · 所属路段 {{ landmarkPin.segment_id || '未标定' }}（最近折线推定）
        · {{ landmarkPin.id }} · 演示点
      </span>
    </div>

    <!-- 跟随鼠标的信息浮牌：吸附在当前选中路段上，沿线走 -->
    <div v-if="mouse && hoverChip" class="hover-chip" :style="chipStyle">
      {{ hoverChip }}
    </div>

    <!-- 图例（自绘视图搬来；flow=流量四档 / index=CI 色阶 / level=四级）。
         Issue IKP3EV：≤1180 单列后地图变成整行宽，整幅图例（600px+ 宽）会盖住路网主体，
         所以窄屏把图例收进可折叠浮层（默认收起，点「图例」展开）；
         桌面 (>1180) 不包一层布局：.legend-dock 用 display:contents，.legend 仍相对 .mlmap 定位，
         视觉与改造前完全一致。 -->
    <div v-if="legend" class="legend-dock" :class="{ open: legendOpen }">
      <button
        type="button"
        class="legend-toggle"
        :aria-expanded="legendOpen"
        @click="legendOpen = !legendOpen"
      >
        {{ legendOpen ? '图例 ▾' : '图例 ▸' }}
      </button>
      <div class="legend">
      <!-- IKOQEJ · 方向标记图例（IKP5BD：三行与开关状态一致；包无方向字段时明确说明） -->
      <template v-if="!directionsAvailable">
        <div class="lg-title">方向标记</div>
        <div class="lg-row">本包无方向字段（旧 21 段对照包）：不绘制方向标记</div>
        <div class="lg-note">方向字段只在 Z / GZ 站点包提供；旧 21 段包仅用于路网对照，不给每个点画灰「?」。</div>
      </template>
      <template v-else-if="!directionsVisible">
        <div class="lg-title">方向标记（只读 enriched）</div>
        <div class="lg-row">已隐藏方向标记（顶栏「设置 → 方向标记」可开）</div>
      </template>
      <template v-else>
        <div class="lg-title">方向标记（只读 enriched）</div>
        <div class="lg-row">
          <span class="dir-mark" :style="{ color: '#1D5FD8' }">↑</span>单向 ·
          <span class="dir-mark both" :style="{ color: '#6D28D9' }"><span>↑</span><span class="flip">↑</span></span>双向（中点前后各一支）·
          <span class="dir-mark" :style="{ color: '#8B8B8B' }">?</span>未标定
        </div>
        <div class="lg-note">方向来自 OSM oneway + 只读 enriched（演示标注，不是真实方向数据）；车道 / 对向段 / 贯通性见右栏路段详情。</div>
      </template>
      <div class="lg-sep" />
      <template v-if="isFlow">
        <div class="lg-title">纯车流量色阶（q_vph · 4 档）</div>
        <div v-for="band in FLOW_BANDS" :key="band.band" class="lg-row">
          <span class="dot" :style="{ background: band.color }" />
          {{ band.band }} 档 {{ band.name }} · {{ flowRangeLabel(band) }}
        </div>
        <div class="lg-row"><LevelBadge :level="1" stale />灰 = 无流量数据（缺 q / 数据陈旧），不硬填</div>
        <div class="lg-note strong">{{ FLOW_MODE_LABEL }} · {{ FLOW_MODE_NOTE }}</div>
        <div class="lg-note">{{ FLOW_COLOR_NOTE }}</div>
        <div class="lg-sep" />
        <div v-for="v in VEH_LEGEND" :key="v.t" class="lg-row">
          <span class="dot" :style="{ background: v.color }" />{{ v.t }} {{ v.label }}
        </div>
        <!-- IKMF1W：路线三种语义的图例（有路线时才出现） -->
        <template v-if="hasRoutes">
          <div class="lg-sep" />
          <div class="lg-row"><span class="lg-line recommended" />推荐路线（品牌蓝实线）</div>
          <div v-if="altRouteCount >= 1" class="lg-row"><span class="lg-line alt1" />备选 1（青 · 长虚线）</div>
          <div v-if="altRouteCount >= 2" class="lg-row"><span class="lg-line alt2" />备选 2（琥珀 · 短虚线）</div>
          <div class="lg-row"><span class="lg-line departure" />离站路线（紫色实线）</div>
          <div v-if="routeStart" class="lg-row">
            <span class="rt-dot start">起</span>{{ routeStart.label }} · {{ routeStart.segment_id }}（外围入口段）
          </div>
          <div v-if="routeEnd" class="lg-row">
            <span class="rt-dot end">终</span>{{ routeEnd.label }} · 停车场落客点（演示）
          </div>
          <div class="lg-note">备选 {{ altRouteCount }} 条（契约要求 ≥2；不足如实少画，不凑等价路线）</div>
          <div class="lg-note">
            凸显路线：{{ routeEmphasisOn ? '开 — 非路线段中性灰细线，不按等级上色' : '关 — 满图等级色，路线叠加' }}
          </div>
          <div class="lg-note">路线由接口端出（真网产物优先 / 样例回退 / mock 演示骨架），原样描线、不随时间重算</div>
        </template>
        <!-- 图钉语义与上色策略解耦（IKP5DM）：图钉只画源台账，流量版有 q 即上色 -->
        <template v-if="pins.length > 0">
          <div class="lg-sep" />
          <div class="lg-row"><span class="dot cam-dot" />源台账摄像头 · 有样本视频源（演示，非本站现场）</div>
          <div class="lg-row"><span class="dot cam-dot empty" />源台账摄像头 · 无独立视频源（演示复用）</div>
          <div class="lg-note">图钉只画源台账登记段；流量版有 q 即上色，演示摄像头按 N 段 N 路（mock 复用）</div>
        </template>
        <div class="lg-row ts">更新 {{ props.ts || '—' }}</div>
      </template>
      <template v-else-if="isIndex">
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
          <div v-if="altRouteCount >= 1" class="lg-row"><span class="lg-line alt1" />备选 1（青 · 长虚线）</div>
          <div v-if="altRouteCount >= 2" class="lg-row"><span class="lg-line alt2" />备选 2（琥珀 · 短虚线）</div>
          <div class="lg-row"><span class="lg-line departure" />离站路线（紫色实线）</div>
          <div v-if="routeStart" class="lg-row">
            <span class="rt-dot start">起</span>{{ routeStart.label }} · {{ routeStart.segment_id }}（外围入口段）
          </div>
          <div v-if="routeEnd" class="lg-row">
            <span class="rt-dot end">终</span>{{ routeEnd.label }} · 停车场落客点（演示）
          </div>
          <div class="lg-note">备选 {{ altRouteCount }} 条（契约要求 ≥2；不足如实少画，不凑等价路线）</div>
          <div class="lg-note">
            凸显路线：{{ routeEmphasisOn ? '开 — 非路线段中性灰细线，不按等级上色' : '关 — 满图等级色，路线叠加' }}
          </div>
          <div class="lg-note">路线由接口端出（真网产物优先 / 样例回退 / mock 演示骨架），原样描线、不随时间重算</div>
        </template>
        <!-- 图钉只画源台账（IKP5DM 选 A：全段按等级上色，图钉语义与上色策略分开说） -->
        <template v-if="pins.length > 0">
          <div class="lg-sep" />
          <div class="lg-row"><span class="dot cam-dot" />源台账摄像头 · 有样本视频源（演示，非本站现场）</div>
          <div class="lg-row"><span class="dot cam-dot empty" />源台账摄像头 · 无独立视频源（演示复用）</div>
          <div class="lg-note">
            图钉只画源台账登记段（初始映射，不代表一期总数）；演示摄像头按 N 段 N 路（mock 复用，画面见右栏路段卡）；
            路网全段按等级上色，灰 = 数据不可用，不是「没摄像头」。
          </div>
        </template>
      </template>
    </div>
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

/* 图例浮层容器（Issue IKP3EV）：桌面 display:contents，DOM 包裹层对布局零影响
   （.legend 仍相对 .mlmap 绝对定位）；只有窄屏媒体查询里才变成真正的折叠浮层。 */
.legend-dock {
  display: contents;
}
.legend-toggle {
  display: none;
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
  /* 图例内容较长（方向 / 四级 / 路线 / 起终点），限宽 + 内部滚动：
     既保证信息一条不丢，又不让它盖住整张地图（起点在路网左下角时最容易被压住）。 */
  max-width: min(420px, 40%);
  max-height: min(72%, 400px);
  overflow-y: auto;
  pointer-events: auto;
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
/* IKOQEJ · 方向标记图例的字符图标（与地图 canvas 图标同款字符/颜色） */
.lg-row .dir-mark {
  width: 13px;
  height: 13px;
  margin: 0 3px 0 7px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  flex: 0 0 auto;
}
.lg-row .dir-mark:first-child {
  margin-left: 0;
}
/* 双向图例：两支反向箭头（与地图上「中点前后各一支」的画法对应） */
.lg-row .dir-mark.both {
  width: auto;
  gap: 1px;
}
.lg-row .dir-mark.both .flip {
  display: inline-block;
  transform: rotate(180deg);
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
/* 备选 1 / 2 的图例线段：颜色 + 节律都与地图一致（长虚 12/6 vs 短虚 2.5/4.5） */
.lg-line.alt1 {
  height: 3px;
  border-top: 0;
  background: repeating-linear-gradient(90deg, #0e7490 0 7px, transparent 7px 10px);
}
.lg-line.alt2 {
  height: 3px;
  border-top: 0;
  background: repeating-linear-gradient(90deg, #b45309 0 3px, transparent 3px 6px);
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

/* 落客点 / 场区浮牌（Issue IKP5BZ）：与摄像头浮牌同一族，宽度略大以容纳「所属路段 + 点位 id」 */
.lm-chip {
  position: absolute;
  width: 220px;
  padding: 5px 9px;
  background: #ffffff;
  border: 1.2px solid #0f766e;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.14);
  font-size: 11px;
  color: #1a1a1a;
  line-height: 1.5;
  pointer-events: none;
  z-index: 5;
}
.lm-chip-sub {
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

/* 落客点 / 场区（Issue IKP5BZ）：与摄像头图钉同族（20 px、细边、轻投影、悬停浮牌），
   靠形状（圆角方 vs 圆）+ 颜色区分：落客点=青「落」，场区=棕「场」。
   坐标是路段折线上的演示点，不是踏勘点位。 */
:deep(.lm-pin) {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  border: 2px solid #ffffff;
  color: #ffffff;
  font-size: 10px;
  line-height: 14px;
  text-align: center;
  cursor: pointer;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
}
:deep(.lm-pin.dropoff) {
  background: #0f766e;
}
:deep(.lm-pin.zone) {
  background: #8a5a2b;
}

/* ---- 路线起点 / 终点标注（业主 2026-10-21：外围入口段 = 起点，停车场落客点 = 终点）---- */
:deep(.rt-pin) {
  width: 26px;
  height: 26px;
  color: #ffffff;
  font-size: 12px;
  font-weight: 700;
  line-height: 22px;
  text-align: center;
  cursor: pointer;
  border: 2px solid #ffffff;
  border-radius: 50%;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.35);
}
:deep(.rt-pin.start) {
  background: #0052d9;
}
:deep(.rt-pin.end) {
  background: #b45309;
}
.rt-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  margin-right: 5px;
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
  border-radius: 50%;
}
.rt-dot.start {
  background: #0052d9;
}
.rt-dot.end {
  background: #b45309;
}

/* ==========================================================================
   响应式（Issue IKP3EV）
   地图是「容器尺寸驱动」的：≤1180 三栏堆叠后地图变整行宽，≤768/≤560 画布又收窄，
   浮层（图例 / 浮牌 / 水印 / 底图角标）必须自己收，不能撑出画布或盖住比例尺。
   断点含义与 DashboardView 一致：1180 / 768 / 560。
   ========================================================================== */
@media (max-width: 1180px) {
  /* 堆叠后地图整行变宽，底图角标给右侧缩放控件让位，避免长文案压到控件上。 */
  .basemap-note {
    max-width: calc(100% - 96px);
  }
  /* 堆叠后地图高 320~620px，而整幅图例内容高 450px+、宽 670px+，会盖住大半张图。
     窄屏改为「图例 ▸」折叠浮层：默认收起（只有一个小按钮），展开后限宽
     min(320px, 72vw)、限高 min(360px, 36vh) 并内部滚动，信息一条不少。 */
  .legend-dock {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
    position: absolute;
    left: 8px;
    bottom: 8px;
    z-index: 2;
    max-width: min(320px, 72vw);
    pointer-events: none;
  }
  .legend-toggle {
    display: inline-flex;
    align-items: center;
    height: 24px;
    padding: 0 9px;
    font: inherit;
    font-size: 11px;
    color: #1a1a1a;
    background: rgba(255, 255, 255, 0.94);
    border: 1px solid #e8e8e8;
    border-radius: 4px;
    cursor: pointer;
    pointer-events: auto;
  }
  .legend-dock .legend {
    position: static;
    left: auto;
    bottom: auto;
    max-width: 100%;
    max-height: min(360px, 36vh);
    overflow: auto;
    pointer-events: auto;
    padding: 7px 9px;
    gap: 4px;
    -webkit-overflow-scrolling: touch;
  }
  .legend-dock:not(.open) .legend {
    display: none;
  }
  .lg-note {
    font-size: 10px;
    line-height: 1.5;
  }
}

@media (max-width: 768px) {
  /* 顶部三层：底图角标（左上）/ 水印（上中）/ 缩放控件（右上）——逐个限宽，互不重叠。 */
  .watermark {
    max-width: 46%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 10px;
  }
  .basemap-note {
    top: 8px;
    left: 8px;
    max-width: calc(100% - 84px);
    padding: 2px 6px;
    gap: 5px;
    font-size: 10px;
  }
  .attribution {
    top: 30px;
    left: 8px;
    max-width: calc(100% - 16px);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 9px;
  }
  /* 图例在 ≤1180 已是折叠浮层：这里只收紧字号 / 限宽，给右下比例尺让位。 */
  .legend-dock {
    max-width: min(300px, 76vw);
  }
  .lg-title,
  .lg-row,
  .lg-row.ts {
    font-size: 10px;
  }
  .lg-note {
    font-size: 9px;
    line-height: 1.45;
  }
  /* 浮牌：内容允许换行，宽度不超过画布。 */
  .hover-chip {
    max-width: min(220px, calc(100% - 16px));
    white-space: normal;
  }
  .cam-chip {
    width: min(192px, calc(100% - 16px));
  }
  .lm-chip {
    width: min(220px, calc(100% - 16px));
  }
}

@media (max-width: 560px) {
  .legend-dock {
    left: 6px;
    bottom: 6px;
    max-width: min(280px, 78vw);
  }
  .legend-dock .legend {
    padding: 6px 8px;
    max-height: min(300px, 34vh);
  }
  .lg-title {
    font-size: 9.5px;
  }
  /* MapLibre 自带控件（缩放 / 比例尺）在窄地图里收紧外边距，避免与图例/水印打架。 */
  :deep(.maplibregl-ctrl-top-right) {
    margin: 4px 4px 0 0;
  }
  :deep(.maplibregl-ctrl-bottom-right) {
    margin: 0 4px 4px 0;
  }
}
</style>
