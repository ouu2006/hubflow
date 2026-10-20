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
import { basemapEnabled, directionsVisible } from '../../../shared/settings'
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
/**
 * 默认视野档（`fitToNetwork()` 里 `map.fitBounds()` 之后记下真实档位）。
 * 图钉的缩放 / 淡出、方向箭头的基准尺寸都以它为锚 —— **不能写死 zoom 14**：
 * Z 站演示范围 500 m、GZ 站 1000 m，两者的默认视野档不是一个数。
 */
let fitZoom = 14
/** 方向箭头在「默认视野档」下的基准尺寸（业主 2026-10-19：默认就固定这么大，放大不再变） */
const DIR_ICON_BASE = 0.8
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
    mode: 'level',
    colorMode: 'congestion',
    ts: '',
    hoverChip: '',
    legend: true,
  },
)

const emit = defineEmits<{
  (e: 'select', segmentId: string): void
  /** 点了图例右上角的叉键（收起由父组件决定，因为重开的按钮在工具条上） */
  (e: 'close-legend'): void
}>()

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

/**
 * 热力晕染强度（**仅拥堵版指数视图**且 ci 可用；流量版、四级视图一律 0 = 不画）。
 *
 * ⚠️ 四级视图必须返 0（业主 2026-10-20：「每个道路都要颜色，周围还有往外衍生的一圈淡淡的颜色，
 * 把那个去掉」）。四级色本身已经把等级说清楚了，26 px 的半透明同色宽带只是往两边漫出去的雾；
 * 广州南站 708 段这种密度下，几百条晕染互相叠会糊成一整坨，反而看不出哪条路是什么色。
 * `LAYER_HEAT` 的注释也写着「四级视图 heat 恒 0」，此前 `heatOf()` 少了这一条判断，
 * 属于代码与注释不一致，这里补齐。
 */
function heatOf(seg: DemoSegment): number {
  if (!isIndex.value) return 0
  if (isFlow.value) return 0
  if (!isCameraCovered(seg.segment_id)) return 0
  const rec = segById.value.get(seg.segment_id)
  if (!rec || !ciAvailable(rec)) return 0
  const v = Math.min(CI_MAX, Math.max(0, rec.ci as number))
  return Math.round((0.1 + (v / CI_MAX) * 0.5) * 100) / 100
}

/**
 * 方向标记 GeoJSON（IKOQEJ）：每段一个点（折线中段），带图标名与旋转角。
 *   · forward/backward → 单箭头（沿走向旋转；backward 加 180°）；
 *   · bidirectional → 双向箭头（双头，沿走向旋转，表达"有来有回"）；
 *   · 未标定 → 灰色「?」（不画真箭头，避免把缺字段读成单向）。
 * 字段只读自站点包（enriched 生成物），不参与判级 / 路线。
 */
function directionGeoJson(): FeatureCollection {
  const features = net.map((seg) => {
    const kind = directionKindOf(directionOf(seg.segment_id))
    const bearing = bearingDeg(seg.coords)
    const rotate = kind === 'backward' ? (bearing + 180) % 360 : bearing
    const [lon, lat] = pointAtFraction(seg.coords, 0.5)
    return {
      type: 'Feature' as const,
      properties: {
        segment_id: seg.segment_id,
        dir_kind: kind,
        icon: DIR_ICON_PREFIX + kind,
        rotate,
      },
      geometry: { type: 'Point' as const, coordinates: [lon, lat] },
    }
  })
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
  const glyph = kind === 'bidirectional' ? '↕' : kind === 'unknown' ? '?' : '↑'
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

/**
 * 方向标记图层（symbol + icon，无 text/glyphs 依赖；随地图旋转对齐）。
 *
 * `icon-size`（业主 2026-10-19 第三次口径，最终定版）：
 *   原话「让箭头的大小不要变了，就是默认值的大小固定，然后缩小地图，箭头也跟着缩小」。
 *   即：**默认视野档（`fitZoom`）就是基准尺寸 `DIR_ICON_BASE`，放大不再变大**；
 *   只有缩远时箭头才跟着地图一起缩。所以这里**不能再写 zoom 插值**——
 *   插值表达式是编译期常量，锚不住 fitBounds 之后才知道的档位（各站演示范围不同：
 *   Z 500 m / GZ 1000 m，默认档不是一个数）。尺寸改为运行时算：
 *   见 `dirIconSizeOf()` / `applyDirectionScale()`，`move` 事件里逐帧贴回图层。
 *   缩放比例取「每降 1 档减半」：箭头屏幕上占的是**地图比例尺**的位置，
 *   视野每放大一倍（+1 档）同样的东西就该大一倍，反过来缩远就减半 ——
 *   这也正是旧版 `exponential 2` 想要的效果，只是旧版顺带把「放大变大」也做了，
 *   且锚点写死在 15 档，业主明确不要前者。
 *   另：`icon-allow-overlap` / `icon-ignore-placement` 保持 `true` —— 关掉会做**随机避让**，
 *   有些路段的方向箭头会凭空消失，方向语义就不完整了（变小可以，"缺失"不行）。
 *   这里**不做透明度淡出**：业主口径是「缩小地图箭头也跟着缩小」，淡到没有就不是缩小了。
 *   缩远后还嫌挡图，挡的其实是摄像头图钉（见第二十四章 `camPinOpacityOf`），不是箭头。
 *   `visibility` 跟着 `directionsVisible` 走：换样式重建图层时也要带上，否则关掉后
 *   一切底图/设置就又把箭头画回来。
 */
function directionLayerSpec(): SymbolLayerSpecification {
  return {
    id: LAYER_DIRECTION,
    type: 'symbol',
    source: DIR_SRC,
    layout: {
      'icon-image': ['get', 'icon'],
      // 只给基准值：真实尺寸由 applyDirectionScale() 按当前档位运行时刻算并覆盖
      'icon-size': DIR_ICON_BASE,
      'icon-rotate': ['get', 'rotate'],
      'icon-rotation-alignment': 'map',
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
      visibility: directionsVisible.value ? 'visible' : 'none',
    },
  }
}

/** 建图 / 换样式后把方向源与图层挂上（源/图层存在则跳过；图标缺则补） */
function addDirectionLayers(map: MapLibreMap): void {
  addDirectionImages(map)
  if (!map.getSource(DIR_SRC)) {
    map.addSource(DIR_SRC, { type: 'geojson', data: directionGeoJson() })
  }
  if (!map.getLayer(LAYER_DIRECTION)) {
    const before = map.getLayer(LAYER_ROUTE_ALT_HALO) ? LAYER_ROUTE_ALT_HALO : undefined
    map.addLayer(directionLayerSpec(), before)
  }
  applyDirectionVisibility(map)
  // 建图层时 `icon-size` 只写了基准值，立刻按当前档位贴一次真实值
  applyDirectionScale(map)
}

/**
 * 把「方向箭头显隐」贴到图层上。
 * 图层还没建（或样式正在换）时**静默跳过** —— `addDirectionLayers` 会再调一次，
 * 不需要在这里排队重试。
 */
function applyDirectionVisibility(map: MapLibreMap): void {
  if (!map.getLayer(LAYER_DIRECTION)) return
  map.setLayoutProperty(
    LAYER_DIRECTION,
    'visibility',
    directionsVisible.value ? 'visible' : 'none',
  )
}

/**
 * 方向箭头在某个缩放档下的尺寸（业主 2026-10-19 定版口径）：
 *   - **默认视野档 `fitZoom` 及更近（放大）→ 一律 `DIR_ICON_BASE`，不再变大**；
 *   - **比默认视野更远（缩小）→ 随地图等比缩小**：每降 1 档尺寸减半。
 * 只在下限 0.04 处截断（那时箭头已不足 3 px，本来就看不见了），
 * **不做透明度淡出** —— 业主明确要的是「缩小时箭头跟着缩小」，淡到没有就不是缩小了。
 * 低缩放下真正挡图的是摄像头图钉（见 `camPinOpacityOf`），不是箭头。
 */
function dirIconSizeOf(zoom: number): number {
  const d = fitZoom - zoom // 比默认视野缩远了多少档（负数 = 放大）
  if (d <= 0) return DIR_ICON_BASE
  return Math.max(0.04, DIR_ICON_BASE * Math.pow(2, -d))
}

/** 把当前档位折算成方向箭头的尺寸贴回图层（`move` 事件里逐帧调） */
function applyDirectionScale(map: MapLibreMap): void {
  if (!map.getLayer(LAYER_DIRECTION)) return
  map.setLayoutProperty(LAYER_DIRECTION, 'icon-size', dirIconSizeOf(map.getZoom()))
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
        /** 该段是否有可展示数据（拥堵版=摄像头覆盖；流量版=有 q 且不陈旧）—— 线宽/透明度按它分档 */
        covered: coveredOf(seg),
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

/**
 * 路网三层的**基准线宽**（主 / 支两档，单位屏幕像素，取值对应 `fitZoom` 档）。
 * 缩远时由 `applyLineScale()` 按档位整体折算 —— 这里只放基准值，别再散落魔法数字。
 */
const LINE_W_CASING: readonly [number, number] = [11, 9]
const LINE_W_HEAT: readonly [number, number] = [26, 22]
const LINE_W_LINE: readonly [number, number] = [5.5, 4.5]

/**
 * 线宽随缩放的系数（业主 2026-10-20 定版口径，与方向箭头同一套相对 `fitZoom` 的算法）：
 *   - **`fitZoom` 及更近（放大）→ 恒为 1**，默认视野观感一点不动；
 *   - **比默认视野更远 → 每降 1 档减半**（`2^-d`）。
 *
 * 为什么必须是 `2^-d`（等比）而不是随手拍一条缓曲线：
 * `line-width` / `line-opacity` 的单位是**屏幕像素**，缩放时不变，而路网在屏幕上的
 * **跨度**按 `2^-d` 缩、**面积**按 `4^-d` 缩。线宽若不跟着缩，同样的线在更小的地盘上
 * 重叠 → 覆盖率按 `2^d` 爆，缩 2 档就是 ×4、3 档 ×8，于是「糊成一片、外面像包了层色」。
 * 线宽严格按 `2^-d` 收，覆盖率才保持不变，缩多小都是同一张图的等比缩小版。
 *
 * 下限 0.15：再小下去主线不足 1 px、会被抗锯齿吃成虚影，反而不如留一根细线。
 */
function lineScaleOf(zoom: number): number {
  const d = fitZoom - zoom // 比默认视野缩远了多少档（负数 = 放大）
  if (d <= 0) return 1
  return Math.max(0.15, Math.pow(2, -d))
}

/**
 * 热力晕染的**额外淡出**系数：线宽已经按 `2^-d` 收过一遍，但热力是同色半透明宽带，
 * 相邻段叠在一起仍会加深（0.1–0.6 的 opacity 叠两三层就到 0.8+）。
 * 所以热力在「又缩」之外再按 `2^(-0.8d)` 单独压一道 —— 缩 2 档约 0.33、3 档触底 0.25。
 *
 * ⚠️ 下限 0.25，**不能归零**：业主明确「这个颜色不能完全去掉」，热力是拥挤指数视图的
 * 主要读图线索，远景也要能看出哪里红。
 */
function heatFadeOf(zoom: number): number {
  const d = fitZoom - zoom
  if (d <= 0) return 1
  return Math.max(0.25, Math.pow(2, -d * 0.8))
}

/** 上一次贴上去的线宽系数（避免每帧重建三个表达式；`force` 用于换样式后强制重贴） */
let lastLineScale = -1

/**
 * 把当前缩放档折算成线宽 / 热力透明度贴回图层（`move` 事件里逐帧调）。
 *
 * `force = true` 的两个时机：① `fitZoom` 刚被 `fitToNetwork()` 改写；
 * ② `setStyle()` 之后 —— 样式一换，paint 属性全部回到 `lineLayerSpecs()` 的基准值，
 * 不强制重贴就会「底图加载完成那一刻线宽突然变粗」。
 */
function applyLineScale(map: MapLibreMap, force = false): void {
  if (!map.getLayer(LAYER_CASING)) return
  const zoom = map.getZoom()
  const s = lineScaleOf(zoom)
  if (!force && Math.abs(s - lastLineScale) < 0.004) return
  lastLineScale = s
  map.setPaintProperty(
    LAYER_CASING,
    'line-width',
    widthExpr(LINE_W_CASING[0] * s, LINE_W_CASING[1] * s),
  )
  map.setPaintProperty(LAYER_HEAT, 'line-width', widthExpr(LINE_W_HEAT[0] * s, LINE_W_HEAT[1] * s))
  map.setPaintProperty(LAYER_HEAT, 'line-opacity', ['*', ['get', 'heat'], heatFadeOf(zoom)])
  map.setPaintProperty(LAYER_LINE, 'line-width', widthExpr(LINE_W_LINE[0] * s, LINE_W_LINE[1] * s))
}

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
      paint: { 'line-color': '#FFFFFF', 'line-width': widthExpr(LINE_W_CASING[0], LINE_W_CASING[1]) },
    },
    // 热力晕染：只指数视图有值；四级视图 heat 恒 0，等于不画
    {
      id: LAYER_HEAT,
      type: 'line',
      source: SRC,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': ['get', 'color'],
        'line-width': widthExpr(LINE_W_HEAT[0], LINE_W_HEAT[1]),
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
        'line-width': widthExpr(LINE_W_LINE[0], LINE_W_LINE[1]),
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
  // IKOQEJ：方向标记画在路网之上、路线之下（路线语义仍是最上层）
  addDirectionLayers(map)
}

// ---- 摄像头布点 ----

/** 摄像头标记（重绘 / 卸载时移除） */
let camMarkers: Marker[] = []
/** 图钉外壳（缩放系数写在它的 CSS 变量上，Marker 自己的 transform 不被覆盖） */
let camPinEls: HTMLElement[] = []

/**
 * 图钉随缩放变化：**DOM Marker 不会自己缩**（它是屏幕像素尺寸），
 * 而本站演示范围只有 500 m，滚轮缩到比默认视野更远时整张路网只剩屏幕中央一小团，
 * 61 个 20 px 的编号钉就会糊成一圈、把路网整个盖住（业主 2026-10-19 第二次反馈）。
 * 这里让图钉跟着地图一起缩：以「默认视野档」（`fitZoom`，fitBounds 之后的档位）为 1，
 * 每降 1 档乘约 0.78。用相对档位而不是写死 zoom 14，是因为各站点的默认视野档不一样。
 */
function camPinScaleOf(zoom: number): number {
  return Math.min(1.15, Math.max(0.28, Math.pow(2, (zoom - fitZoom) * 0.36)))
}

/**
 * 图钉透明度：**比默认视野再缩出去 1 档就开始淡，缩 1.6 档彻底淡出**。
 * 只缩小不够：本站 61 段几乎每段一个钉，缩远后整张网只剩屏幕中央一小团，
 * 就算每个钉只有 6 px，61 个 6 px 圆叠在同一小块上照样糊成一片（实测过，仍然看不清路网）。
 * 所以远景直接不画图钉 —— 那个档位本来就只是在看"路网形状"，单个摄像头的编号没有意义；
 * 放大回默认视野就重新淡入。完全透明时同时置 `pointer-events: none`，避免隐形钉吃点击。
 */
function camPinOpacityOf(zoom: number): number {
  const d = fitZoom - zoom // 比默认视野缩远了多少档
  if (d <= 1) return 1
  if (d >= 1.6) return 0
  return 1 - (d - 1) / 0.6
}

/** 把当前缩放档折算成图钉的尺寸 / 透明度写进 CSS 变量（`move` / `zoom` 事件里调） */
function applyCameraPinScale(map: MapLibreMap): void {
  const zoom = map.getZoom()
  const s = camPinScaleOf(zoom).toFixed(3)
  const o = camPinOpacityOf(zoom)
  for (const el of camPinEls) {
    el.style.setProperty('--cam-pin-scale', s)
    el.style.setProperty('--cam-pin-opacity', o.toFixed(3))
    // 完全透明时不要再吃鼠标事件（否则远景点不到地图，只有一堆隐形钉在拦）
    el.style.pointerEvents = o <= 0.02 ? 'none' : ''
  }
}
/** 被悬停的摄像头（浮牌钉在图钉上方，与路段浮牌区分） */
const pin = ref<CameraPin | null>(null)

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
  for (const p of pins) {
    // 外壳 = Marker 自己的定位元素（MapLibre 会在它身上写 transform 做平移），
    // 缩放变量挂在外壳上、由里层 `.cam-pin` 的 transform 消费 —— 两者不抢同一个 transform。
    const wrap = document.createElement('div')
    wrap.className = 'cam-pin-wrap'
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
    wrap.appendChild(el)
    camPinEls.push(wrap)
    camMarkers.push(new Marker({ element: wrap }).setLngLat([p.lon, p.lat]).addTo(map))
  }
  applyCameraPinScale(map)
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
  // 记下默认视野档：图钉的缩放 / 淡出、方向箭头的基准尺寸、路网线宽的折算都以「相对默认视野缩远了多少档」为准
  fitZoom = map.getZoom()
  // 档位一变之前算出的箭头尺寸就过期了（图层里只存着基准值），立刻按新基准重算
  applyDirectionScale(map)
  applyCameraPinScale(map)
  // 线宽 / 热力也是相对 fitZoom 折算的，基准一换必须强制重贴
  applyLineScale(map, true)
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
  const at = own.findIndex((layer) => layer.id === LAYER_ROUTE_ALT_HALO)
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
  const dirSrc = map.getSource(DIR_SRC) as GeoJSONSource | undefined
  if (dirSrc) void dirSrc.setData(directionGeoJson())
  // 换样式会按 `directionLayerSpec()` 重建图层（里面已带 visibility），这里再贴一次兜底：
  // 万一样式没换、只是数据刷新，用户刚关掉的箭头不该被这次刷新带回来。
  applyDirectionVisibility(map)
  // 新建的图层里 `icon-size` 只有基准值，按当前档位重算一次真实尺寸 / 透明度
  applyDirectionScale(map)
  // 线宽 / 热力透明度同理：`setStyle()` 后 paint 属性全部回到基准值，这里强制重贴
  applyLineScale(map, true)
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
    // fitBounds 之后才定下默认视野档，图钉要按新基准再折算一次
    applyCameraPinScale(map)
    ready.value = true
    // 车辆要在 ready 之后再同步（`syncVehicles` 以 ready 为前置）
    syncVehicles(map)
    map.on('move', () => {
      camTick.value++
      // 图钉是 DOM（屏幕像素尺寸）、方向箭头只写了基准尺寸、路网线宽也是屏幕像素
      // —— 每帧按当前档位折算一次
      applyCameraPinScale(map)
      applyDirectionScale(map)
      applyLineScale(map)
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

/** 方向箭头开关：只切图层 visibility，不动数据（关掉再开不用重建源） */
watch(directionsVisible, () => {
  const map = mapRef.value
  if (!map || !ready.value) return
  applyDirectionVisibility(map)
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
  camPinEls = []
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

    <!-- 跟随鼠标的信息浮牌：吸附在当前选中路段上，沿线走 -->
    <div v-if="mouse && hoverChip" class="hover-chip" :style="chipStyle">
      {{ hoverChip }}
    </div>

    <!-- 图例（自绘视图搬来；flow=流量四档 / index=CI 色阶 / level=四级）
         面板压在地图左下角,**会挡住那一片的路网** —— 右上角给一个叉键收起来(业主 2026-10-19);
         收起后重新打开的按钮在地图工具条「Z · 61 段」左边(DashboardView),两个方向都能回来。 -->
    <div v-if="legend" class="legend">
      <button
        type="button"
        class="lg-close"
        title="收起图例"
        aria-label="收起图例"
        @click="emit('close-legend')"
      >
        ×
      </button>
      <!-- 面板内容单独一层滚动：叉键钉在外层右上角，滚动时不会跟着跑掉 -->
      <div class="lg-body">
        <!-- IKOQEJ · 方向标记图例：两种颜色模式都有（方向标不随拥堵/流量换色） -->
        <div class="lg-title">方向标记（只读 enriched）</div>
        <div class="lg-row">
          <span class="dir-mark" :style="{ color: '#1D5FD8' }">↑</span>单向 ·
          <span class="dir-mark both" :style="{ color: '#6D28D9' }">↕</span>双向（左右两向）·
          <span class="dir-mark" :style="{ color: '#8B8B8B' }">?</span>未标定
        </div>
        <div class="lg-note">方向来自 OSM oneway + 只读 enriched（演示标注，非实测）；车道 / 对向段 / 贯通性见右栏路段详情。</div>
        <!-- 箭头被关掉时说明一句：否则图例上还画着三种箭头，图上却一个都没有，会以为是画丢了 -->
        <div v-if="!directionsVisible" class="lg-note strong">当前已隐藏方向箭头（工具条「箭头」键可打开）</div>
        <div class="lg-note">箭头默认档尺寸固定，缩小地图时跟着缩小，不会糊住路段线。</div>
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
            <div class="lg-row"><span class="lg-line alternative" />备选路线（灰虚线）</div>
            <div class="lg-row"><span class="lg-line departure" />离站路线（紫色实线）</div>
            <div class="lg-note">路线由接口端出（真网产物优先 / 样例回退 / mock 演示骨架），原样描线、不随时间重算</div>
          </template>
          <!-- 「只摄像头段上色」是拥堵版的策略；流量版对所有有 q 的段上色，这里只解释图钉语义 -->
          <template v-if="cameraOnly">
            <div class="lg-sep" />
            <div class="lg-row"><span class="dot cam-dot" />源台账摄像头 · 有样本视频源（演示，非本站现场）</div>
            <div class="lg-row"><span class="dot cam-dot empty" />源台账摄像头 · 无独立视频源（演示复用）</div>
            <div class="lg-note">流量版按 q 分档上色：源台账无布点的段只要有流量数据同样上色（颜色只表示流量大小）</div>
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
            <div class="lg-row"><span class="lg-line alternative" />备选路线（灰虚线）</div>
            <div class="lg-row"><span class="lg-line departure" />离站路线（紫色实线）</div>
            <div class="lg-note">路线由接口端出（真网产物优先 / 样例回退 / mock 演示骨架），原样描线、不随时间重算</div>
          </template>
          <!-- 「只摄像头段上色」的图例（Issue IKLX5Y）：说清灰轮廓 = 这段没监控 -->
          <template v-if="cameraOnly">
            <div class="lg-sep" />
            <div class="lg-row"><span class="dot cam-dot" />源台账摄像头 · 有样本视频源（演示，非本站现场）</div>
            <div class="lg-row"><span class="dot cam-dot empty" />源台账摄像头 · 无独立视频源（演示复用）</div>
            <div class="lg-note">
              图钉仅源台账布点（初始映射，不代表一期总数）；一期 N 段 = N 摄像头 = N 视频（mock 复用，画面见右栏路段卡）；
              拥堵版仅源台账布点段上色。
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
  /* 面板压在地图左下角、内容比地图还高时**上半截会被地图裁掉**（原先就有这现象），
     叉键钉在右上角就会跟着飞出去 —— 所以给它一个高度上限，滚动交给里面那层
     `.lg-body`：面板永远落在地图内，右上角的叉键永远点得到。 */
  max-height: calc(100% - 24px);
  overflow: hidden;
  /* 宽度按「紧凑面板」定住：不加这条会按最长那句说明的单行宽度把面板拉满整幅地图
     （绝对定位元素的 shrink-to-fit 取 max-content），叉键就跑到地图中间去了。 */
  max-width: 320px;
  /* 整块 `auto`：叉键要能点、超高时也要能滚。代价是这块面板下方不再透传地图拖拽
     （纯展示面板本来也不需要；地图拖拽可用地图其余部分）。 */
  pointer-events: auto;
  z-index: 2;
}
/* 面板内容（可滚动的那一层）：原先直接挂在外层 flex 上的行，现在收到这一层里，
   间距口径与外层原样一致（5px），叉键仍钉在外层右上角、不随滚动跑。 */
.lg-body {
  display: flex;
  flex-direction: column;
  gap: 5px;
  /* 撑满外层可用高度并在内部滚动（叉键在外层，不参与滚动） */
  min-height: 0;
  overflow-y: auto;
}
/* 收起键：钉在面板右上角，压在 padding 上（不占文档流，故用绝对定位） */
.lg-close {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 18px;
  height: 18px;
  padding: 0;
  border: 0;
  border-radius: 3px;
  background: transparent;
  color: #8b8b8b;
  font: inherit;
  font-size: 15px;
  line-height: 1;
  cursor: pointer;
  pointer-events: auto;
}
.lg-close:hover {
  background: #f0f1f3;
  color: #1a1a1a;
}
.lg-close:focus-visible {
  outline: 2px solid v-bind('BRAND');
  outline-offset: 1px;
}
/* 图例标题右让一点，避免顶到叉键 */
.lg-title {
  font-size: 11px;
  color: #666666;
  margin-bottom: 1px;
  padding-right: 20px;
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
   Marker 的 DOM 由 document.createElement 造，不在 scoped 作用域内，故用 :deep()。

   缩放：外壳 `.cam-pin-wrap` 上挂着 `--cam-pin-scale` / `--cam-pin-opacity`（由
   `applyCameraPinScale()` 按 zoom 写），**变换必须落在里层 `.cam-pin`**——外壳的
   transform 是 Marker 用来定位的，覆盖掉图钉就会跑位。
   缩放原点取圆心，否则钉子在放大时会向右下"漂"半个身位。 */
:deep(.cam-pin-wrap) {
  /* 外壳只负责被 Marker 定位（尺寸随里层图钉走，锚点圆心正好压在坐标上），不参与缩放 */
  line-height: 0;
}
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
  /* 低缩放时随地图一起缩、一起淡（值由 applyCameraPinScale() 写在父级上） */
  transform: scale(var(--cam-pin-scale, 1));
  transform-origin: center center;
  opacity: var(--cam-pin-opacity, 1);
  transition:
    transform 0.12s linear,
    opacity 0.12s linear;
}
:deep(.cam-pin.empty) {
  background: #ffffff;
  color: #455a64;
}
</style>
