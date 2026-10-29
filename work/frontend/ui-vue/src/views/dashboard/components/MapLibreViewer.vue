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
  type CircleLayerSpecification,
  type ExpressionSpecification,
  type FilterSpecification,
  type FillLayerSpecification,
  type GeoJSONSource,
  type GeoJSONSourceSpecification,
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
  camerasVisible,
  dropoffsVisible,
  zonesVisible,
  directionsVisible,
  legendVisible,
  routeEmphasisEnabled,
  setLegendVisible,
} from '../../../shared/settings'
import {
  activePack,
  activePackKey,
  onPackChange,
  packVersion,
  stationEntries,
  type StationEntry,
} from '../../../station-packs/index'
// IKPFVN：全国视角 / 站区视角的镜头运动集中在 `shared/mapMotion.ts`（时长、中国范围、留白、打断规则）
import {
  cancelMotion,
  clampOverviewZoom,
  fitBoxCamera,
  fitOverviewCamera,
  fitStationCamera,
  flyToOverview,
  flyToStation,
  overviewCamera,
  overviewPadding,
  stationCamera,
  stationPadding,
  type CameraPadding,
  type MotionPhase,
} from '../../../shared/mapMotion'
// 方向层的缩放档位住在 shared 里：进站取景的**缩放下限**用的就是 `DIR_ZOOM_FULL`
// （`shared/mapMotion.ts` 的 `fitBoxCamera`），两边各写一个 15.5 迟早分叉。
import { DIR_ZOOM_FADE, DIR_ZOOM_FULL } from '../../../shared/directionZoom'
// 底图拉不到时的**兜底轮廓**（Natural Earth 1:110m 简化，公有领域）。
// ⚠️ 用 `?raw` 把文件当**文本**导入，而不是 `import … from '…geojson'`：
//    ① `.geojson` 不是 `.json`，`resolveJsonModule` 不认它（改 tsconfig 属于为一个素材文件动全局配置）；
//    ② `?url` 也不行 —— Vite 的已知素材类型表里没有 `.geojson`，打包时直接报 Module not found；
//    ③ 进 `public/` 又要把素材搬一份。`?raw` 内联成字符串、运行时 `JSON.parse`，零配置、零重复文件。
import chinaOutlineText from '../../../assets/geo/china-outline.geojson?raw'
import {
  landmarkKindLabel,
  landmarkPins,
  type PackLandmarkView,
} from '../../../shared/landmarks'
// IKOQEJ：方向标记（只读 enriched 字段；不是判级/契约数据）
import {
  directionKindOf,
  directionOf,
  pointAtFraction,
  polylineLengthM,
  tangentBearingAt,
  trimPolylineM,
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
  type RouteArrowStep,
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
// ---- 真值路网底衬（2026-10-29 演示验收）----
//
// 为什么要在**底图之外**再画一遍路网：
//   底图源（OpenFreeMap `planet`）TileJSON 的 `maxzoom` 是 **14**，而站区视角 zoom≈16.5
//   —— 等于把 z14 瓦片放大 2.5~3.6 倍。z14 瓦片里没有 service/track 级道路，本站 44 段
//   ramp（停车场内部通道 / 服务道路 / 连接匝道）在底图上是空白 + 建筑面，彩色路段看起来
//   "悬空穿过场地"，被业主读成"线路画错了"；干道也被 z14 合并简化过，彩色线与底图黄线
//   肉眼错开 10~15 m。
//   先排除过"几何画错"：61 段逐顶点 + 每条边每 5% 内插点到实时 OSM 车道的距离，
//   `N>5m 0 / N>15m 0 / median 0.0 m / 最大偏差 0.2 m` —— 几何是真值。所以修法是换底衬。
//   做法：把同一份 OSM 切片里的车行道自己画一遍（数据见站点包 `roads`，生成脚本
//   `work/frontend/scripts/gen_station_roads.py`），并让底图道路图层在站区档整族退出。
const ROADS_SRC = 'hubflow-truth-roads'
const LAYER_ROADS_CASING = `${ROADS_SRC}-casing`
const LAYER_ROADS_LINE = `${ROADS_SRC}-line`
/**
 * 底图道路图层的**退出档**：zoom ≥ 14.5 时整族不画，站区路网一律由上面那份真值底衬承担。
 * 为什么是 14.5：底图瓦片只到 z14，14→14.5 是"瓦片还够用"的最后半档；再放大就全是 overzoom
 * 的插值结果，留着的唯一效果是**和自绘路网打架**（两套宽窄、两套简化程度）。
 * 全国视角（zoom 3~6）与过渡中仍用底图道路 —— 那时底图是够准的，自绘底衬也是隐藏的。
 */
const BASEMAP_ROAD_MAXZOOM = 14.5
/**
 * 把底图道路「放回来」时用的 `maxzoom`。
 *
 * Liberty 的道路层多数不写 `maxzoom`（等价于一路画到 24）。`setLayerZoomRange()` 必须给一个
 * 具体数值，所以用 24 这个"等于没限制"的值兜底 —— 只有当原层本来就没写时才用得上。
 */
const BASEMAP_ROAD_RESTORE_MAXZOOM = 24
/** Liberty 样式里矢量源的 id（底图道路图层的 `source`；关它之前要按这个筛） */
const OPENMAPTILES_SRC = 'openmaptiles'
/**
 * 底衬的外观分档（屏幕 px，不参与 `applyLineScale()` 的缩放折算 —— 它只在站区视角出现，
 * 而站区视角的 zoom 基本固定在 fitZoom 附近）。
 *
 * `edge` = 灰色路缘（外圈），`road` = 路面（内圈）。取"比彩色段自己的描边明显更宽"
 * （彩色段 casing 主 11 / 支 9，路面 15.5 / 8.6）：这样彩色段像**压在路面上的一条检测线**，
 * 两侧各露出 3 px 左右的路肩，一眼就能看出"线长在路上"，而不是悬空的色块。
 * 停车场通道（aisle）最细，免得把 44 段 ramp 糊掉。
 *
 * ⚠️ 第一版取「比彩色段宽 1~2 px」+ 纯白路面，实测**等于没画**：纯白跟底图 landuse 底色
 * （≈`#F8F4F0`）糊成一片，截图像素统计里路缘色只有几十个像素。所以路面色是**比背景深半档**
 * 的米灰，宽度也拉到彩色段之外 —— 这两个值要一起调，只改一个都看不出来。
 */
const ROADS_W_EDGE = { arterial: 18, link: 15, local: 12.5, aisle: 10.5 } as const
const ROADS_W_ROAD = { arterial: 15.5, link: 12.6, local: 10.2, aisle: 8.6 } as const
const ROADS_C_EDGE = { arterial: '#BEB3A5', link: '#C3B9AC', local: '#CCC3B6', aisle: '#D2CABE' } as const
/**
 * 路面色：比底图的 landuse 底色（≈`#F8F4F0`）**深半档**，而不是纯白 —— 纯白在这个底色上
 * 会跟背景糊成一片（第一版就是这样，等于白画），只有比背景深的路面才看得出"这里有一条路"。
 */
const ROADS_C_ROAD = { arterial: '#F1EBE2', link: '#F3EEE6', local: '#F6F1EA', aisle: '#F8F4EE' } as const
/**
 * 灰底版（`colorMode='gray'`，业主 2026-10-29）的底衬色：**只保留按 `cls` 的明度差**
 * （干道最深 → 场内通道最浅），路网结构仍可读；不表示任何路况。
 * 与彩色档的米色底衬**同结构、同宽度**，只换色相 —— 换档时底衬不会忽粗忽细。
 */
const ROADS_C_EDGE_GRAY = { arterial: '#A8AEB8', link: '#AFB5BF', local: '#B6BCC5', aisle: '#BDC3CB' } as const
const ROADS_C_ROAD_GRAY = { arterial: '#E3E6EA', link: '#E7EAEE', local: '#EBEDF0', aisle: '#EFF1F3' } as const

/** 按底衬分类取宽度/颜色（`cls` 由生成脚本打，取值见 `PackRoadClass`） */
function roadsByClass(
  table: Record<'arterial' | 'link' | 'local' | 'aisle', number>,
): ExpressionSpecification {
  return [
    'match',
    ['get', 'cls'],
    'arterial', table.arterial,
    'link', table.link,
    'local', table.local,
    'aisle', table.aisle,
    table.arterial,
  ] as ExpressionSpecification
}

/** 同上，颜色版（`line-color` 不接受 number） */
function roadsColorByClass(
  table: Record<'arterial' | 'link' | 'local' | 'aisle', string>,
): ExpressionSpecification {
  return [
    'match',
    ['get', 'cls'],
    'arterial', table.arterial,
    'link', table.link,
    'local', table.local,
    'aisle', table.aisle,
    table.arterial,
  ] as ExpressionSpecification
}

/**
 * 底衬色表按**颜色模式**切换（业主 2026-10-29）：
 *   彩色三档（congestion / flow / custom）用米色底衬，灰底版用去饱和的冷灰底衬。
 * 结构 / 宽度两套完全一致，只换色相 —— 所以换档时路网不会忽粗忽细（`ROADS_W_*` 只有一份）。
 */
function roadsEdgeColors(): Record<'arterial' | 'link' | 'local' | 'aisle', string> {
  return isGrayMode.value ? ROADS_C_EDGE_GRAY : ROADS_C_EDGE
}
function roadsRoadColors(): Record<'arterial' | 'link' | 'local' | 'aisle', string> {
  return isGrayMode.value ? ROADS_C_ROAD_GRAY : ROADS_C_ROAD
}
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
/**
 * 方向箭头的**基准宽度**（屏幕 px，业主 2026-10-23 第三次定版：**34px**）。
 *
 * 演进留痕（完整口径链，别只看最后一行）：
 *   ① 7.5px —— 初版「比 11 略小」，业主真机反馈「不放大看不到」作废；
 *   ② 24px —— 四档对比（12/16/20/24）选定，真机看后业主仍觉得不够；
 *   ③ 34px —— 业主本轮拍板「再大一点，到 34」，箭头字高约 23px，最醒目。
 * 参照物：道路主线 5.5 px —— 34px 约为其 6.2 倍，属于「压路换醒目」的强展示口径。
 * 图标原图是 64px canvas，`icon-size = 34 / 64` 才是 MapLibre 的尺寸系数。
 */
const DIR_ICON_PX = 34
/** 方向图标 canvas 的边长（`directionIconImage()` 里的 size 常量，两处必须同源） */
const DIR_ICON_CANVAS = 64
// `DIR_ZOOM_FULL` / `DIR_ZOOM_FADE` 从 `shared/directionZoom.ts` 引入（顶部 import）：
// 前者同时是进站取景的缩放下限，必须与取景逻辑共用同一份常量。
const LAYER_HEAT = `${SRC}-heat`
const LAYER_CASING = `${SRC}-casing`
const LAYER_LINE = `${SRC}-line`
/** 推荐路线（品牌蓝实线；「当前 / 已选」语义，不得用等级色） */
const LAYER_ROUTE_HALO = `${SRC}-route-halo`
const LAYER_ROUTE = `${SRC}-route`
/**
 * 备选 1 / 备选 2（Issue IKP5CK）：两条备选必须**互相可区分**（原来一起画灰虚线）。
 * 分两个图层而不是一个「按属性取色」的图层：两者的**虚线节律 + 平行偏移**也不同，
 * 叠在同一段路时靠「节律 + ±2px 平行线」区分。
 * 2026-10-29 业主反转配色后，两条备选与主推荐**同色**（浅蓝 #38BDF8）、同宽（3 px），
 * 区分只靠节律与偏置；共用段只由备选 1 画，避免两条虚线夹出脏色。
 */
const LAYER_ROUTE_ALT1_HALO = `${SRC}-route-alt1-halo`
const LAYER_ROUTE_ALT1 = `${SRC}-route-alt1`
const LAYER_ROUTE_ALT2_HALO = `${SRC}-route-alt2-halo`
const LAYER_ROUTE_ALT2 = `${SRC}-route-alt2`
/** 离站路线（紫色实线；第三种语义色，与等级色 / 品牌蓝分开） */
const LAYER_ROUTE_DEP_HALO = `${SRC}-route-dep-halo`
const LAYER_ROUTE_DEP = `${SRC}-route-dep`
/**
 * 被选中的那条路线（业主 2026-10-29 口径**反转**后）：品牌蓝实线、压在所有其它路线之上。
 * 底层各路线图层会把「被选中路线的段号」从 filter 里剔除，避免弱色粗线盖住高光蓝线。
 */
const LAYER_ROUTE_PICK_HALO = `${SRC}-route-pick-halo`
const LAYER_ROUTE_PICK = `${SRC}-route-pick`
/**
 * 路线高光**反转**（业主 2026-10-29，IKRK8B）—— 方向与 2026-10-28 那版正好相反：
 *   · **选中**（`pickedRouteKey` 那条）= 品牌蓝 `#0052D9`、实线 4.2 px（强）；
 *   · **未选中**（主推荐 + 两条备用**同待遇**）= 浅蓝 `#38BDF8`、3 px（弱）；
 *   · 离站仍紫 `#7B61FF`（不在「规划 / 备用 / 选中」这条层级里）。
 *
 * 即：`#38BDF8` 原来表示「选中」，现在表示「未选中 / 非高光」；`#0052D9` 从「主推荐」
 * 搬去「选中」。**只对调语义、不新增色值**（业主原话「自定义路线的颜色复用」）。
 *
 * 三条可辨（IKP5CK 判定）**不许退**：三条同为浅蓝后，只靠线型 + 平行偏置区分 ——
 * 主推荐实线、备选 1 长虚线左偏 2 px、备选 2 短虚线右偏 2 px。
 */
const ROUTE_IDLE_COLOR = '#38BDF8'
/** 高光（选中）路线色 = 品牌蓝。单独起名，是为了「品牌蓝一色两用」的场合能指针到语义 */
const ROUTE_PICKED_COLOR = BRAND
/**
 * 路线下方的**浅色底衬**（半透明白，压在 LAYER_LINE 之上、所有路线之下）。
 * 解决业主截图里「路线压住判级色、两边只露 1 px」的脏边：底衬比路线宽一圈，
 * 把判级色在路线两侧的碎片整段盖掉，路线读起来是"压在干净路面上的一条线"。
 */
const LAYER_ROUTE_BED = `${SRC}-route-bed`
/**
 * 选中**路段**描边色：中性深灰（IKRK8B C 节）。
 * 原来是品牌蓝 `#0052D9` —— 和「主推荐路线 / 选中的路线」同一个蓝，一色两义，
 * 业主「分不清这种带颜色的路线」的根因就在这。改中性色后，「虚线 = 当前路段」只表示选中。
 */
const SEGMENT_SELECTED_STROKE = '#1F2430'
const LAYER_SELECTED = `${SRC}-selected`
/**
 * 「路线」这一族图层的 id（底衬 + 主推荐 + 两条备选 + 离站 + 选中路线，含各自的 halo）。
 * 灰底版（`colorMode='gray'`）要把它们**整族**藏掉 —— 见 `isGrayMode` 与 `applyModeLayers()`。
 * 集中成一张表，是为了加新路线图层时不会漏藏（漏藏 = 灰底版里冒出一条蓝线）。
 */
const ROUTE_LAYER_IDS: readonly string[] = [
  LAYER_ROUTE_BED,
  LAYER_ROUTE_HALO,
  LAYER_ROUTE,
  LAYER_ROUTE_ALT1_HALO,
  LAYER_ROUTE_ALT1,
  LAYER_ROUTE_ALT2_HALO,
  LAYER_ROUTE_ALT2,
  LAYER_ROUTE_DEP_HALO,
  LAYER_ROUTE_DEP,
  LAYER_ROUTE_PICK_HALO,
  LAYER_ROUTE_PICK,
]

// ---- IKPFVN · 全国视角的两个图层族（站点 pin / 底图兜底轮廓）----
//
// 为什么站点用 GeoJSON source + 图层，而不是 DOM Marker：站只会越加越多（现为 Z / GZ），
// DOM Marker 每个都要建元素、挂事件、随地图重排；图层一次挂好，加站只换 data。
// 点击 / 悬停也走同一条通道（`queryRenderedFeatures`），不用给每个 pin 绑一对监听。
const STATION_SRC = 'hubflow-station'
/** 透明大圆：**只用来命中**（视觉半径 6~9 px，命中半径 15 px → 30 px 热区，≥ 24 px 要求） */
const LAYER_STATION_HIT = `${STATION_SRC}-hit`
/** 站点实心圆；选中环就画在**它自己**身上（`feature-state.selected`），不另建一套图层 */
const LAYER_STATION_DOT = `${STATION_SRC}-dot`
/** 站名（canvas 生成图片的 symbol 图层，见 `stationLabelLayerSpec()` 里为什么不用 text-field） */
const LAYER_STATION_LABEL = `${STATION_SRC}-label`
const STATION_LABEL_ICON_PREFIX = 'hubflow-station-label-'
/** 非当前站的中性深灰（品牌蓝只给「当前 / 已选」） */
const STATION_DOT_COLOR = '#475569'
/** 底图拉不到时的中国轮廓（淡填充 + 细描边，不抢路网） */
const OUTLINE_SRC = 'hubflow-china-outline'
const LAYER_OUTLINE_FILL = `${OUTLINE_SRC}-fill`
const LAYER_OUTLINE_LINE = `${OUTLINE_SRC}-line`

// ---- 落客区（终点区域）可视化（业主 2026-10-25：进入区域 → 停车场落客的可视化终点划分）----
// 每个落客点画一个半透明圆（fill + outline），选中路线的终点落客点另有一层高亮。
// 口径：圆是**演示范围圈**（以落客点为圆心的示意划分，非实地划线、非真实围栏）。
const DZ_SRC = 'hubflow-dropzone'
const LAYER_DZ_FILL = `${DZ_SRC}-fill`
const LAYER_DZ_HL = `${DZ_SRC}-hl`
const LAYER_DZ_LINE = `${DZ_SRC}-line`
/** 演示范围圈半径（米） */
const DROPZONE_RADIUS_M = 35
/** 落客区颜色与「落」图钉同族（teal） */
const DZ_COLOR = '#0f766e'
/** 高亮圈的填充透明度（底圈 0.10、描边 0.5） */
const DZ_HL_OPACITY = 0.26
const EMPTY_FC: FeatureCollection = { type: 'FeatureCollection', features: [] }

/**
 * 路线配色（业主 2026-10-29 复核版，IKRK8B）：
 *   · **未选中**的路线（主推荐 + 备选 1 + 备选 2，同待遇）= 浅蓝 `#38BDF8`、3 px（弱）；
 *   · **选中**的那条 = 品牌蓝 `#0052D9`、4.2 px 实线（强），见 `ROUTE_PICKED_COLOR`；
 *   · 离站 = 紫 `#7B61FF`（另一段行程，不在这条层级里）。
 *
 * ⚠️ 2026-10-28 那版把三档按**明度**排开（天蓝选中 > 中蓝备选 > 品牌蓝规划），
 *    业主 2026-10-29 明确要求**反过来**：选中的才是深蓝、其余压成浅蓝。
 *    所以三条路线现在**同色同宽**，可辨性全部押在「线型 + 平行偏置」上（IKP5CK 判定）：
 *    主推荐实线（无偏置）· 备选 1 长虚 12/6 左偏 2 px · 备选 2 短虚 2.5/4.5 右偏 2 px。
 *
 * 与既有颜色的边界（保持不撞）：
 *   · 四级判级色 #2BA471 / #E9B32E / #E37318 / #D54941 —— 浅蓝 / 品牌蓝都不含绿 / 黄 / 红；
 *   · 数据不可用灰 #8B8B8B、凸显压灰 #C9CDD4、灰底版路网灰 #6E7681 —— 三者语义各不相同；
 *   · 离站紫 #7B61FF 与品牌蓝的色相夹角足够大，叠在同一条路上也分得开。
 */
const ROUTE_ALT1_COLOR = ROUTE_IDLE_COLOR
const ROUTE_ALT2_COLOR = ROUTE_IDLE_COLOR
/** 离站路线色：仍用紫色（它不在「规划 / 备用 / 选中」这条层级里，是另一段行程） */
const ROUTE_DEPART_COLOR = '#7B61FF'
/**
 * 「凸显路线」时非路线段的中性灰（Issue IKP5CK）。
 * 必须与「数据不可用灰」#8B8B8B 视觉可区分：更浅（#C9CDD4）、更细（2 px vs 5.5 px）、
 * 透明度更低（0.55）、**不加虚线**；且只在 `colorMode='custom'` 这一档才生效
 * （2026-10-29 收紧：其余三档它是空操作，见 `routeEmphasisOn`）。
 */
const ROUTE_EMPHASIS_GRAY = '#C9CDD4'
/**
 * 灰底版（`colorMode='gray'`）的**路网线色**。
 * ⚠️ **不许**用 `#8B8B8B` —— 那是「有摄像头但数据不可用 / 陈旧」的语义色，灰底版不得挪用；
 * 这里取更深的冷灰，让「路网本体」在灰底衬上读得出来，同时一眼看出它不是等级色。
 */
const GRAY_MODE_LINE = '#6E7681'

/** 悬停浮牌尺寸（只用于翻面判断，与 CSS 里的 min/max-width 对应） */
const CHIP_W = 210
const CHIP_H = 26
/** 摄像头浮牌宽度（与 <style> 中 .cam-chip 的 width 保持一致；窄屏 CSS 会用 min() 收小） */
const CAM_CHIP_W = 192
/** 落客点 / 场区浮牌宽度（与 <style> 中 .lm-chip 的 width 保持一致；窄屏同样用 min() 收小） */
const LM_CHIP_W = 220
/** 全国站点浮牌宽度（与 <style> 中 .st-chip 的 width 保持一致） */
const ST_CHIP_W = 176

/** 'level' = 四级视图（默认） · 'index' = 拥挤指数视图 */
type MapMode = CongestionViewMode
/**
 * IKPFVN：视角范围。
 *   `national` = 全国大地图（只画站点 pin，不画任何站的路网 / 路线）
 *   `station`  = 站区视角（当前站路网 + 路线 + 图例 + 浮牌）
 * 与上面的 `MapMode`（上色口径）是两回事，**不要合并**。
 */
type MapScope = 'national' | 'station'

const props = withDefaults(
  defineProps<{
    segments: SegmentRecord[]
    selectedId: string | null
    /** 孪生车辆动点（位置随快照刷新平滑移动） */
    vehicles?: VehicleRecord[]
    /** 推荐 / 备选 / 离站三组路线高亮（IKMF1W；空数组 = 不画路线） */
    routes?: RouteHighlight[]
    /**
     * 被选中的那条路线的 key（前端展示字段，非契约）：`arrival` / `alt:<序号>` / `departure`。
     * 业主 2026-10-28：被选中的路线（不管是推荐还是备选）要画成天蓝、压在其它路线之上。
     * `null` = 没有选中任何整条路线（此时规划蓝 / 备选中蓝按原样画）。
     */
    pickedRouteKey?: string | null
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
    /**
     * 视角范围（Issue IKPFVN）：`national` = 全国大地图（只画站点 pin，不画任何站的路网 / 路线）；
     * `station` = 站区视角（当前站路网 + 路线 + 图例）。
     *
     * ⚠️ 与上面的 `mode`（四级 / 指数视图）**不是一回事**：那个管上色口径，这个管“看多远”。
     *    当初差点把这个 prop 也叫 `mode`——两个同名 prop 会直接报重复声明，也算提醒。
     */
    mapMode?: MapScope
    /**
     * 点图拾取模式（业主 2026-10-28 当面要求：直接点图选起终点，不在右边列表里挑）：
     *   `'origin'` / `'destination'` = 正在等用户点哪一端；`null` = 不拾取（点击仍走既有「选路段」）。
     *
     * 本组件只负责**把点击坐标交出去**（`pick-point`）；吸附到最近路段、算路全部由后端做，
     * 地图侧不做任何匹配 / 纠偏，也不画假点——标记回显等父级把吸附结果传回 `routeStart/routeEnd`。
     */
    pickMode?: 'origin' | 'destination' | null
    /**
     * 路线行进箭头数据（业主 2026-10-29：路线上一支方向箭头都没有，后端标的向对不对肉眼无法验证）。
     *
     * **只吃后端口径**：`geometry` 必须已经按**行车顺序**排好（后端 `steps[].geometry`，
     * 由 `/arrival_route`、`/route/plan` 直接给出）；没有 `steps` 的老链路
     * （`/route/recommend`）由父级先用**链式连通性**定向（`shared/routeArrows.ts`）再传进来，
     * 地图侧**不做**二次定向、也不按 `_rev` 后缀猜 —— 方向解释只允许有一份。
     * 空数组 = 一支都不画（宁可不画，也不按几何顺序误导）。
     */
    routeSteps?: RouteArrowStep[]
  }>(),
  {
    vehicles: () => [],
    routes: () => [],
    pickedRouteKey: null,
    routeStart: null,
    routeEnd: null,
    mode: 'level',
    colorMode: 'congestion',
    ts: '',
    hoverChip: '',
    legend: true,
    mapMode: 'national',
    pickMode: null,
    routeSteps: () => [],
  },
)

const emit = defineEmits<{
  (e: 'select', segmentId: string): void
  /** 点全国浮层卡片 / 点站点 pin：请求切到该站（切站唯一入口仍由父级调 `switchStation`） */
  (e: 'switch-station', key: string): void
  /** 镜头真的落到站区（父级据此提交页面数据，见 IKPFVN D 节时序） */
  (e: 'arrived'): void
  /**
   * 点图拾取到坐标（业主 2026-10-28）：`pickMode` 非空时，点图不再报路段，只报经纬度。
   * 父级拿这个坐标调 `/route/snap` 吸附，再把结果回显。
   */
  (e: 'pick-point', point: { lon: number; lat: number }): void
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
// ⚠️ 2026-10-29 起**没有**「缩放后重建方向标记数据」这条路径了：箭头位置固定在路段
// 50% 弧长点、双向段固定在 50% 一支双头箭头、零横向偏移，尺寸交给 `icon-size` 的 zoom
// 插值表达式。数据与视口无关 ⇒ `move` 里不再需要去抖计时器（`dirDataTimer` 已删）。
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

/** 按**当前站点包**现取一份几何（不依赖 `DEMO_NETWORK` 的惰性缓存，见 `applyPackChange`） */
function segmentsFromPack(): DemoSegment[] {
  return activePack().segments.map((s) => ({
    segment_id: s.segment_id,
    name: s.name,
    kind: s.kind,
    coords: s.coords.map((c) => [c[0], c[1]] as [number, number]),
  }))
}

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

/** 当前站键（响应式）：挂在容器 `data-station` 上，切站后跟着变 */
const currentStationKey = computed<string>(() => {
  void packTick.value
  return activePackKey()
})

/**
 * 全国浮层 / 站点 pin 的点击：只**请求**切站，真正的切站在父级（唯一入口 `switchStation()`）。
 * 本组件不碰包、不碰数据 —— 否则又会出现“地图自己换了一套包、面板还停在上一坑”的老毛病。
 */
function pickStation(key: string): void {
  emit('switch-station', key)
}
/**
 * 上色策略由站点包 `colorPolicy` 决定（IKP5DM 起 Z/GZ 均为 `'all'`：全段按等级上色，
 * 灰只表示数据不可用/陈旧，不再表示「这段没摄像头」）。
 * 图钉与上色策略**解耦**：图钉画全量 N 段 N 路（2026-10-25），图例按 `pins.length` 显隐（见模板）。
 */
/** 摄像头图钉（随包变化：Z 61 路 = 源台账 6 + 演示层 55；GZ 708 路 = 演示层） */
const pins = computed(() => {
  void packTick.value
  return cameraPins()
})

// 落客区图例样式（与 LAYER_DZ_* 的 paint 同源；脚本 setup 里的模板绑定用小写别名）
const dzColor = DZ_COLOR
const dzSwatchBg = 'rgba(15, 118, 110, 0.18)'

// ---- 路段染色（四级 / 指数两种视图） ----

const segById = computed(() => new Map(props.segments.map((s) => [s.segment_id, s])))
const isIndex = computed(() => props.mode === 'index')
/**
 * 颜色模式的**值**（4 档：`congestion` / `flow` / `custom` / `gray`），一律按 string 收口。
 *
 * ⚠️ 为什么不当面写 `props.colorMode === 'custom'`：`ColorMode` 的类型在 `shared/flow.ts`，
 *    本轮由另一路同步把它从 2 值扩成 4 值；若对端还没合进来，直接拿 4 值和 2 值联合类型比较
 *    会被 vue-tsc 判成「不可能相等」而报错（TS2367），把本文件拖进无法收敛的类型问题。
 *    收成 string 之后，本组件对「2 值定义」和「4 值定义」都成立，类型永远不会成为阻塞项。
 */
const colorModeKey = computed<string>(() => String(props.colorMode ?? 'congestion'))
/** 纯车流量版（Issue IKNB9G）：颜色只看 q_vph 分档，忽略 level / CI / 摄像头覆盖策略 */
const isFlow = computed(() => colorModeKey.value === 'flow')
/**
 * 自定义路线档（业主 2026-10-29，IKRK8B）：**进入即全网灰**。
 * 非路线段一律中性灰细线（沿用「凸显路线」那套 2 px / 0.55），heat 归一化到 0，
 * 不按 level / ci / q 上色 —— 这一档的图面上除了路线**没有任何路况信息**。
 */
const isCustomMode = computed(() => colorModeKey.value === 'custom')
/**
 * 灰底版（业主 2026-10-29，IKRK8B）：**全部线段（含路线本身）一律灰**，
 * 不画热力晕染、不画路线；只保留 roads 底衬按 `cls` 的明度差，让路网结构仍可读。
 * 与 `custom` 档的差别只有一处：custom 档**画路线**、灰底版**一条路线都不画**。
 */
const isGrayMode = computed(() => colorModeKey.value === 'gray')

/**
 * 该段是否"有可展示的数据"（决定线宽 / 透明度）。
 *   · 拥堵版：沿用「只摄像头段上色」策略（业主 2026-10-15）；色块按 level / CI；
 *   · 流量版：**有 q 且不陈旧**即可上色（流量是全网口径，不受摄像头覆盖限制），缺 q 灰档；
 *   · custom / gray 档：恒 true —— 这两档**没有"数据可得性"这件事**（全网同一档灰），
 *     线宽交给 `emphasis_gray`（custom 的非路线段）或基准宽度（gray 档）决定。
 */
function coveredOf(seg: DemoSegment): boolean {
  if (isCustomMode.value || isGrayMode.value) return true
  if (isFlow.value) return flowBandOf(segById.value.get(seg.segment_id)) !== null
  return isCameraCovered(seg.segment_id)
}

/**
 * 路段色。**六档，别混**（前四档是拥堵版的四种情况，后两档是 2026-10-29 新增的颜色模式）：
 *   ① 流量版：q 四档蓝阶（缺 q / 陈旧 → 灰）；
 *   ② 拥堵版有监控且数据可用 → 等级色 / ci 色阶；
 *   ③ 拥堵版有监控但数据不可用 → 灰（粗，`UNAVAILABLE`）；
 *   ④ 拥堵版**没监控** → 灰（细、淡）——"这段没摄像头"本身是个信息，不能与 ③ 长得一样；
 *   ⑤ custom 档 → 中性浅灰 `ROUTE_EMPHASIS_GRAY`（**含路线段**：路线色的那点在路线图层上，
 *      底下的路段必须是灰的，否则等级色会从路线两侧漏出来 → 违反"全网无等级色像素"）；
 *   ⑥ gray 档 → 冷灰 `GRAY_MODE_LINE`（全网一色，不按 `cls`/level 分，路网结构靠底衬读）。
 *
 * ⚠️ ③ 的 `#8B8B8B` 语义**只属于拥堵版**（"有摄像头但数据不可用/陈旧"），
 *    灰底版 ⑥ 不得挪用（业主明确要求图例把两者写清）。
 */
function colorOf(seg: DemoSegment): string {
  const rec = segById.value.get(seg.segment_id)
  if (isGrayMode.value) return GRAY_MODE_LINE
  if (isCustomMode.value) return ROUTE_EMPHASIS_GRAY
  if (isFlow.value) {
    return flowBandOf(rec)?.color ?? UNAVAILABLE.color
  }
  if (!isCameraCovered(seg.segment_id)) return UNAVAILABLE.color
  if (!rec) return UNAVAILABLE.color
  return isIndex.value ? ciStyleColor(rec) : levelStyle(rec).color
}

/** 热力晕染强度（**仅拥堵版指数视图**且 ci 可用；流量版、四级视图、custom、gray 一律 0 = 不画）。
 *
 * ⚠️ 四级视图必须返 0（业主 2026-10-20 口径：「每个道路都要颜色，然后周围还有往外衍生的一圈
 * 淡淡的颜色，把那个去掉」）。四级色本身已经把等级说清楚了，26 px 的半透明同色宽带只是往两边
 * 漫出去的雾。
 *
 * ⚠️ custom / gray 档也必须返 0（2026-10-29）：这两档图面上只有灰线 / 路线，
 * 一旦按 ci 漫出等级色，就等于把"不表示路况"的承诺破掉了。
 *
 * ⚠️ 影响面如实记（独立审查 P2 实测）：heat 只在**摄像头覆盖段**上非零，量级是
 * GZ 708 段里 6 段（6 路摄像头）、Z 61 段里 6 段 —— 不是「每段都给 0.1–0.6」，
 * 25 条也不是「几百条晕染互叠」。所以这一项修的是**局部路口那圈橙绿雾**，
 * 不是「满图一坨」的主因（满图那坨主要是方向箭头，业主 2026-10-22 明确推迟）。
 * `LAYER_HEAT` 的注释从第一版起就写着「四级视图 heat 恒 0」，此前 `heatOf()` 少了这一条判断，
 * 属于代码与注释不一致，这里补齐。
 */
function heatOf(seg: DemoSegment): number {
  if (!isIndex.value) return 0
  if (isFlow.value) return 0
  if (isCustomMode.value || isGrayMode.value) return 0
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
 * 方向箭头的位置 / 朝向 / 尺寸口径（业主 2026-10-29「路段箭头方向」重做）。
 *
 * 三条硬纪律 —— 本文件里凡画方向箭头，三条必须同时成立：
 *   ① **位置**：路段 **50% 弧长点**（`pointAtFraction` 按累计弧长插值，不是首末点连线的中点）；
 *   ② **朝向**：该点的 **局部切线方位角**（`tangentBearingAt()`，取该点前后各
 *      `DIR_TANGENT_SPAN_M` 米的弦）—— 弯道上箭头才贴着路面指；
 *   ③ **尺寸**：`icon-size` 的 **zoom 插值表达式**（`dirIconSizeExpression()`），
 *      不按 zoom 桶 `setLayoutProperty`。
 *
 * ⚠️ 本轮**删除**的旧实现（别再写回来，换分辨率 / 换纬度 / 换瓦片尺寸就会错位的那一套）：
 *   · `metersPerPixel(fitZoom)`（`156543.03 / 2^zoom × cos(22.99°)`）—— 写死纬度、写死 256px 瓦片；
 *   · `DIR_BIDIR_OFFSET_PX` / `DIR_BIDIR_OFFSET_MAX_M` / `offsetByNormal()` —— 双向段按「像素→米」
 *     做横向偏移，偏哪一侧、偏多远全看当前档位；离线复刻实测：`fitZoom=15.55` 时 12 px = 36.05 m，
 *     而 13 段停车场内部通道只有 16.3~19.2 m 长 —— 箭头偏出去比整段还长，正是「箭头跑到没路的地方」；
 *   · `applyDirectionScale()` + `dirIconSizeOf()` —— 用 `setLayoutProperty` 按档改 `icon-size`，
 *     缩放时尺寸跳变，还要在 `move` 里逐帧贴回、并按档重建 GeoJSON（曾自激成 setData→move 循环）。
 *   现在箭头**位置写死在数据里、尺寸写死在表达式里**：缩放不再重算数据、也不重贴 layout。
 */
/** 双向段双头箭头的最小段长（米）：更短改画中性圆点，理由见 `directionGeoJson()` 里的注释 */
const DIR_BIDIR_MIN_LEN_M = 25
/** 局部切线取样的半跨（米）：取该点前后各这么长的弦，压掉单点 / 短段噪声 */
const DIR_TANGENT_SPAN_M = 15

/**
 * 方向标记 GeoJSON（IKOQEJ；2026-10-29 重做位置与朝向）。
 *   · forward / backward → 50% 弧长点**一支箭头**，朝向 = 该点局部切线（backward 再加 180°）；
 *   · bidirectional → 50% 弧长点**一支双头箭头**（同轴、零横向偏移）；段长 < `DIR_BIDIR_MIN_LEN_M`
 *     改画中性圆点（原因见下）；
 *   · 未标定 → 灰色「?」（只针对**包里有方向字段、该段缺值**的情况）；
 *   · 包整体缺方向字段 / 顶栏开关关掉 → 空集合（一支都不画）。
 *
 * ⚠️ 双向段为什么不再"两支箭头分列路两侧"：MapLibre 的 `icon-offset` 是**屏幕空间**偏移，
 *    不随 `icon-rotate` 转、也不随路段走向转 —— 南北走向的路 ±x 恰好是法向，东西走向的路 ±x
 *    就变成**沿路方向**，两支箭头只会在线上前后挪。要做真法向偏移只能回到「像素→米」换算，
 *    而那正是本轮要删掉的东西（见上方删除清单）。一支双头箭头语义更直白，也不存在偏移。
 *
 * ⚠️ 短双向段的圆点阈值按**段长（米）**判，不掺像素换算：本包 13 段停车场通道 16.3~19.2 m，
 *    34 px 的箭头在默认视野（≈3 m/px）下就有一百多米宽，画上去只是一团墨；圆点只说
 *    「这段是双向」，不假装能读出朝向。
 */
function directionGeoJson(): FeatureCollection {
  if (!directionDrawable.value) return { type: 'FeatureCollection', features: [] }
  const features: Feature<Point>[] = []
  for (const seg of net.value) {
    const kind = directionKindOf(directionOf(seg.segment_id))
    const coords = seg.coords
    if (coords.length < 2) continue
    const [lon, lat] = pointAtFraction(coords, 0.5)
    const tangent = tangentBearingAt(coords, 0.5, DIR_TANGENT_SPAN_M)
    if (kind === 'bidirectional') {
      const short = polylineLengthM(coords) < DIR_BIDIR_MIN_LEN_M
      features.push({
        type: 'Feature',
        properties: {
          segment_id: seg.segment_id,
          dir_kind: kind,
          icon: DIR_ICON_PREFIX + (short ? 'bidir-dot' : kind),
          rotate: short ? 0 : tangent,
        },
        geometry: { type: 'Point', coordinates: [lon, lat] },
      })
      continue
    }
    features.push({
      type: 'Feature',
      properties: {
        segment_id: seg.segment_id,
        dir_kind: kind,
        icon: DIR_ICON_PREFIX + kind,
        // backward = 几何 from/to 与行车方向相反 ⇒ 行车朝向 = 局部切线 + 180°
        rotate: kind === 'backward' ? (tangent + 180) % 360 : tangent,
      },
      geometry: { type: 'Point', coordinates: [lon, lat] },
    })
  }
  return { type: 'FeatureCollection', features }
}

/**
 * 在 canvas 上画一支**朝正上方**（= 方位角 0°，北）的箭头：杆 + 三角头，`double=true` 时尾端再画一个头。
 *
 * 为什么整支箭头都用路径画、不用 `fillText('↑')`：①本轮新增的双头箭头没有现成字形；
 * ②字形图标在缺字体的机器上会退化成豆腐块。路径绘制在哪儿都一样，且不需要任何 glyph 资源。
 * 白色描边画两遍：压在任意路网色 / 底图色上都能看清。
 */
function paintArrowGlyph(
  ctx: CanvasRenderingContext2D,
  size: number,
  color: string,
  double: boolean,
): void {
  const cx = size / 2
  const pad = size * 0.09
  const shaftHalf = size * 0.07
  const headHalf = size * 0.2
  const headLen = size * 0.25
  const tipY = pad
  const tailY = size - pad
  const shaftTop = tipY + headLen
  const shaftBottom = double ? tailY - headLen : tailY
  ctx.beginPath()
  // 杆
  ctx.moveTo(cx - shaftHalf, shaftTop)
  ctx.lineTo(cx + shaftHalf, shaftTop)
  ctx.lineTo(cx + shaftHalf, shaftBottom)
  ctx.lineTo(cx - shaftHalf, shaftBottom)
  ctx.closePath()
  // 头（正上方）
  ctx.moveTo(cx, tipY)
  ctx.lineTo(cx - headHalf, tipY + headLen)
  ctx.lineTo(cx + headHalf, tipY + headLen)
  ctx.closePath()
  if (double) {
    // 尾端的反向头（双头箭头：一条双向路）
    ctx.moveTo(cx, tailY)
    ctx.lineTo(cx - headHalf, tailY - headLen)
    ctx.lineTo(cx + headHalf, tailY - headLen)
    ctx.closePath()
  }
  ctx.lineJoin = 'round'
  ctx.lineWidth = size * 0.08
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.96)'
  ctx.stroke()
  ctx.fillStyle = color
  ctx.fill()
}

/** 用 canvas 生成方向图标（ImageData，不需要字体 glyph 资源） */
function directionIconImage(kind: DirectionKind | 'bidir-dot'): ImageData {
  const size = DIR_ICON_CANVAS
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  if (!ctx) return new ImageData(size, size)
  ctx.clearRect(0, 0, size, size)
  if (kind === 'unknown') {
    // 未标定仍用字形「?」：它本来就不是箭头，用文字最省事
    ctx.font = `bold ${Math.round(size * 0.68)}px "Segoe UI Symbol", "Noto Sans Symbols", system-ui, sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.lineWidth = size * 0.12
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.96)'
    ctx.strokeText('?', size / 2, size / 2 + 2)
    ctx.fillStyle = DIR_COLORS.unknown
    ctx.fillText('?', size / 2, size / 2 + 2)
    return ctx.getImageData(0, 0, size, size)
  }
  if (kind === 'bidir-dot') {
    // 短双向段中性圆点（不带朝向含义，见 `directionGeoJson()` 的说明）
    ctx.beginPath()
    ctx.arc(size / 2, size / 2, size * 0.16, 0, Math.PI * 2)
    ctx.closePath()
    ctx.lineWidth = size * 0.07
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.96)'
    ctx.stroke()
    ctx.fillStyle = DIR_COLORS.bidirectional
    ctx.fill()
    return ctx.getImageData(0, 0, size, size)
  }
  paintArrowGlyph(ctx, size, DIR_COLORS[kind], kind === 'bidirectional')
  return ctx.getImageData(0, 0, size, size)
}

/** 注册进样式的全部方向图标（含短双向段的圆点） */
const DIR_ICON_KINDS = ['forward', 'backward', 'bidirectional', 'unknown', 'bidir-dot'] as const

/** 把方向图标注册进当前样式（换样式后要重新注册 —— setStyle 会清空 image 资源） */
function addDirectionImages(map: MapLibreMap): void {
  for (const kind of DIR_ICON_KINDS) {
    const name = DIR_ICON_PREFIX + kind
    if (!map.hasImage(name)) map.addImage(name, directionIconImage(kind))
  }
}

/**
 * 箭头尺寸系数（icon-size，业主 2026-10-23 第三次定版：34px）：
 *   · **150 m 档（zoom 15.5）及更近 → 基准 34 px**，放大**不再变大**（与线宽 / 图钉同一纪律）；
 *   · **比 150 m 更远 → 每远一档减半**（`2^-d`），与路网等比缩。
 */
const DIR_ICON_BASE = DIR_ICON_PX / DIR_ICON_CANVAS

/**
 * 尺寸的 **zoom 插值表达式**（2026-10-29 起由表达式负责，不再用 `setLayoutProperty` 按档贴回）。
 *
 * 上面那条口径是**等比**的（每档 ÷2），所以用 `['exponential', 2]` + 相隔 1 档的一对停靠点就能
 * **精确**重现 `DIR_ICON_BASE × 2^(zoom − 15.5)`：指数底为 2 时，两个停靠点相隔 1 档 ⇒ 中间每档
 * 正好翻倍 / 减半。更高一档再压一个同值停靠点，把「放大不再变大」也钉住。
 *
 * ⚠️ MapLibre 硬性限制（style-spec `findZoomCurve()` 实证）：`zoom` **只能出现在顶层
 * interpolate 的输入位**；写成 `['*', zoom插值, …]` 会直接报错、整个 `setStyle` 失败
 * （底图会永远停在「加载中」）。所以任何系数都必须落在**每个停靠点的输出**上，不能套在外层。
 */
function dirIconSizeExpression(): ExpressionSpecification {
  const farStop = DIR_ZOOM_FULL - 1
  return [
    'interpolate',
    ['exponential', 2],
    ['zoom'],
    farStop, DIR_ICON_BASE / 2,
    DIR_ZOOM_FULL, DIR_ICON_BASE,
    DIR_ZOOM_FULL + 6.5, DIR_ICON_BASE,
  ] as unknown as ExpressionSpecification
}

/**
 * 箭头淡出（业主 2026-10-23 口径「150 到 200 不断变淡，200 之后完全消失」）：
 *   · zoom ≥ 15.5（150 m 及更近）→ 恒 1；
 *   · 15.0 ~ 15.5（150→200 m）→ 线性 1 → 0；
 *   · zoom ≤ 15.0（200 m 及更远）→ 0（一支不画）。
 */
function dirIconOpacityExpression(): ExpressionSpecification {
  return [
    'interpolate',
    ['linear'],
    ['zoom'],
    DIR_ZOOM_FADE, 0,
    DIR_ZOOM_FULL, 1,
  ] as unknown as ExpressionSpecification
}

/** 方向标记图层（symbol + icon，无 text/glyphs 依赖；随地图旋转对齐） */
function directionLayerSpec(): SymbolLayerSpecification {
  return {
    id: LAYER_DIRECTION,
    type: 'symbol',
    source: DIR_SRC,
    layout: {
      'icon-image': ['get', 'icon'],
      // 尺寸 = zoom 插值表达式（位置与朝向已在数据里定死，缩放不再重算数据）
      'icon-size': dirIconSizeExpression(),
      'icon-rotate': ['get', 'rotate'],
      'icon-rotation-alignment': 'map',
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
      // 关掉 / 包无方向字段时不画：换样式重建图层也要带上，否则一开底图就又把箭头画回来
      visibility: directionDrawable.value ? 'visible' : 'none',
    },
    paint: { 'icon-opacity': dirIconOpacityExpression() },
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

/** 路线箭头显隐（只跟「有没有箭头数据」有关；但仍在站区才画，与路网同生命周期） */
function applyRouteArrowVisibility(map: MapLibreMap): void {
  if (!map.getLayer(LAYER_ROUTE_ARROW)) return
  const on = motionPhase.value === 'station' && routeArrowDrawable.value
  map.setLayoutProperty(LAYER_ROUTE_ARROW, 'visibility', on ? 'visible' : 'none')
}

/**
 * 建图 / 换样式后把方向源与图标备齐（源/图标存在则跳过）。
 * ⚠️ 图层本身**不在这里 `addLayer`**：绘制顺序统一由 `ownLayerSpecs()` 一份决定，
 * 两条路各排一套顺序的话，方向标一下子在路线上、一下子在路线下。
 */
function ensureDirectionSource(map: MapLibreMap): void {
  addDirectionImages(map)
  if (!map.getSource(DIR_SRC)) {
    map.addSource(DIR_SRC, { type: 'geojson', data: directionGeoJson() })
  }
}

// ---- 路线行进箭头（业主 2026-10-29：路线上一支方向箭头都没有，后端标的向对不对肉眼无法验证）----
//
// 口径（方案 §3）：
//   · **只认后端 `steps[].geometry`**（父级经 `routeSteps` prop 传进来，几何已按行车顺序排好）——
//     前端不再按 `segment_id` / `_rev` 后缀二次判向，避免两份方向解释打架；
//   · 没有 steps 的老链路（`/route/recommend`）由父级按**链式连通性**定向后再传
//     （看 `shared/routeArrows.ts`）；**不许**直接按 `coords` 顺序画：那是几何方向，不是行车顺序；
//   · 每段画一支，取 50% 弧长点，朝向与路网方向箭头**共用** `tangentBearingAt()`（不出现第二套切线）。
//
// ⚠️ 数据是死的：位置在 GeoJSON 里算定，尺寸是常量 `icon-size`（屏幕像素口径），
//    与路网方向箭头一样**不随缩放重算数据、不随缩放重贴 layout**。
const ROUTE_ARROW_SRC = 'hubflow-route-arrow'
const LAYER_ROUTE_ARROW = `${ROUTE_ARROW_SRC}-marker`
const ROUTE_ARROW_ICON = 'hubflow-route-arrow'
/** 图标 canvas 边长 / 基准屏幕尺寸（px）：比路网方向箭头（34px）小一档，别抢路线的蓝色 */
const ROUTE_ARROW_CANVAS = 48
const ROUTE_ARROW_PX = 22
const ROUTE_ARROW_BASE = ROUTE_ARROW_PX / ROUTE_ARROW_CANVAS
/** 白箭头 + 品牌蓝描边：压在蓝路线 / 判级色路面上都读得出 */
const ROUTE_ARROW_COLOR = '#FFFFFF'
const ROUTE_ARROW_OUTLINE = '#0052D9'
/**
 * 裁掉 `trim_head_m` / `trim_tail_m` 之后，剩余长度**小于这个值就不画该段箭头**（米）。
 *
 * 为什么：切线方位角取的是"该点前后各 `min(DIR_TANGENT_SPAN_M, 段长/4)` 米"的弦，段越短
 * 弦越退化 —— 裁到只剩几米时，一两个折点就把方位角带偏几十度，箭头会乱指；位置也会挤在
 * 一小截里像墨团。这里取 `2 × DIR_TANGENT_SPAN_M`（= 30 m）作下限：低于它，切线弦的中跨
 * 恒等于 `段长/4 < 7.5 m`，那个量级已经不可信了。
 * ⚠️ 这是**米**口径的几何下限，不是像素换算。
 */
const DIR_MIN_DRAW_LEN_M = 2 * DIR_TANGENT_SPAN_M

/** 有箭头数据才画；父级没给 steps 就一支都不画（不猜方向） */
const routeArrowDrawable = computed<boolean>(() => (props.routeSteps ?? []).length > 0)

/** 路线箭头图标：白色实心 + 品牌蓝描边（与路网方向箭头的"白描边 + 语义色填充"正好相反） */
function routeArrowIconImage(): ImageData {
  const size = ROUTE_ARROW_CANVAS
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  if (!ctx) return new ImageData(size, size)
  ctx.clearRect(0, 0, size, size)
  const cx = size / 2
  const pad = size * 0.1
  const shaftHalf = size * 0.09
  const headHalf = size * 0.24
  const headLen = size * 0.28
  const tipY = pad
  const tailY = size - pad
  ctx.beginPath()
  // 杆
  ctx.moveTo(cx - shaftHalf, tipY + headLen)
  ctx.lineTo(cx + shaftHalf, tipY + headLen)
  ctx.lineTo(cx + shaftHalf, tailY)
  ctx.lineTo(cx - shaftHalf, tailY)
  ctx.closePath()
  // 头（朝正上方 = 方位角 0°）
  ctx.moveTo(cx, tipY)
  ctx.lineTo(cx - headHalf, tipY + headLen)
  ctx.lineTo(cx + headHalf, tipY + headLen)
  ctx.closePath()
  ctx.lineJoin = 'round'
  ctx.lineWidth = size * 0.12
  ctx.strokeStyle = ROUTE_ARROW_OUTLINE
  ctx.stroke()
  ctx.fillStyle = ROUTE_ARROW_COLOR
  ctx.fill()
  return ctx.getImageData(0, 0, size, size)
}

/** 路线箭头 GeoJSON：每段一支，位置 = 50% 弧长点，朝向 = 局部切线方位角 */
function routeArrowGeoJson(): FeatureCollection {
  const features: Feature<Point>[] = []
  for (const step of props.routeSteps ?? []) {
    // `geometry` 已按**行车顺序**排好（后端遍历边口径），所以这里只取局部切线，
    // 不再按 `segment_id` / `_rev` / `direction` 二次判向 —— 两份方向解释只会打架。
    // 首 / 尾按 `trim_head_m` / `trim_tail_m` 裁掉不在行程内的部分（方案 §2 附加字段）。
    const coords = trimPolylineM(
      step.geometry,
      step.trim_head_m ?? 0,
      step.trim_tail_m ?? 0,
    )
    if (!Array.isArray(coords) || coords.length < 2) continue
    // 裁完太短就不画：短段上切线弦退化、方位角噪声放大，画出来只会乱指（见 `DIR_MIN_DRAW_LEN_M`）
    if (polylineLengthM(coords) < DIR_MIN_DRAW_LEN_M) continue
    const [lon, lat] = pointAtFraction(coords, 0.5)
    features.push({
      type: 'Feature',
      properties: {
        segment_id: step.segment_id ?? '',
        edge_id: step.edge_id ?? '',
        rotate: tangentBearingAt(coords, 0.5, DIR_TANGENT_SPAN_M),
      },
      geometry: { type: 'Point', coordinates: [lon, lat] },
    })
  }
  return { type: 'FeatureCollection', features }
}

/** 路线箭头图层（白箭头压在路线之上；显隐由 `applyModeLayers()` / `applyDirectionVisibility()` 管） */
function routeArrowLayerSpec(): SymbolLayerSpecification {
  return {
    id: LAYER_ROUTE_ARROW,
    type: 'symbol',
    source: ROUTE_ARROW_SRC,
    layout: {
      'icon-image': ROUTE_ARROW_ICON,
      // 尺寸恒定（屏幕像素口径）：它的作用就是「读出这条线往哪走」，缩没了等于没画。
      // 常量值，不涉及任何米 / 像素换算，也不需要 zoom 表达式。
      'icon-size': ROUTE_ARROW_BASE,
      'icon-rotate': ['get', 'rotate'],
      'icon-rotation-alignment': 'map',
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
      visibility: 'none',
    },
    paint: { 'icon-opacity': 0.95 },
  }
}

/** 建图 / 换样式后备齐路线箭头的图标与源（存在则跳过） */
function ensureRouteArrowSource(map: MapLibreMap): void {
  // ⚠️ 必须容错：本函数会被 `applyViewState()` 从 `styledata` 回调里调到，那一刻样式
  // 可能还没 `_loaded`，`addImage` / `addSource` 会抛 `Style is not done loading`，
  // 未捕获就会把整个 watcher / 组件更新链打断（dev-c 实测连爆一串 Vue warn）。
  // 正常换样式路径下 source 已随 `mergedStyle()` 一起下发，这里只补"建图第一条路"与图标。
  try {
    if (!map.hasImage(ROUTE_ARROW_ICON)) map.addImage(ROUTE_ARROW_ICON, routeArrowIconImage())
    if (!map.getSource(ROUTE_ARROW_SRC)) {
      map.addSource(ROUTE_ARROW_SRC, { type: 'geojson', data: routeArrowGeoJson() })
    }
  } catch {
    // 样式还没就绪：图层在样式里自带 source，等下一次 `styledata` / 数据变化的 watch 再补
  }
}

/**
 * 当前是否处于「凸显路线」：开关开 **且** 在**自定义路线档**（`colorMode='custom'`）
 * **且**真有路线可凸显。
 *
 * ⚠️ 2026-10-29 收紧（IKRK8B D 节）：原来判据只有「开关开 && 有路线」——
 *    于是拥堵 / 流量档下，只要页面里还留着上一次算出来的路线，一按「凸显路线」整张图就压灰，
 *    业主读成"全网数据不可用"。现在它**只对自定义路线档有意义**，其余三档一律空操作：
 *    `congestion` / `flow` 本来就该满图等级色 / 流量色，`gray` 档自己就是灰底，都不需要再压。
 *    没路线时同样不能压灰（否则又变成"全网数据不可用"）。
 */
const routeEmphasisOn = computed<boolean>(
  () => routeEmphasisEnabled.value && isCustomMode.value && hasRoutes.value,
)
/** 任一语义组里的段号（判断"这段是否在路线上"用；同段重复只算一次） */
function routeSegmentIds(): Set<string> {
  const out = new Set<string>()
  for (const g of props.routes ?? []) for (const id of g.segments) out.add(id)
  return out
}

/**
 * 真值路网底衬的 GeoJSON（2026-10-29 演示验收）。
 *
 * 数据直接取**当前站点包**的 `roads`（脚本生成，几何是 OSM 原始节点），不做任何加工：
 * 不简化、不合并、不补插值 —— 底衬的价值就在于"和彩色段同源同口径"，一动就失真。
 * 包没有 `roads`（老包 / 未生成底衬的站）时返回空集合：图层还在但什么都不画，
 * 底图道路也不会被关掉（`applyBasemapRoadMask()` 按同一判据），页面退化成改之前的样子。
 */
function roadsGeoJson(): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: (activePack().roads ?? []).map((r) => ({
      type: 'Feature' as const,
      properties: { cls: r.cls, hw: r.hw, name: r.name ?? '' },
      geometry: { type: 'LineString' as const, coordinates: r.coords },
    })),
  }
}

/** 站点包坐标是 WGS-84，**直接喂给 MapLibre** —— 不做任何坐标转换 */
function routeGeoJson(): FeatureCollection {
  const routed = routeSegmentIds()
  // ⚠️ 压灰在 custom 档是**结构性的**（进入即全网灰），不再依赖「凸显路线」开关：
  //    开关只决定"非路线段压到最淡还是略实"，颜色永远是灰、永远不按 level/ci/q 上色。
  const custom = isCustomMode.value
  return {
    type: 'FeatureCollection',
    features: net.value.map((seg) => {
      const emphasisGray = custom && !routed.has(seg.segment_id)
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
          /**
           * custom 档的「非路线段」标记：paint 直接读它决定细线 / 淡透明度。
           * congestion / flow / gray 三档恒 false ⇒ `applyLineScale()` 里那两处特判自然成为空操作。
           */
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

/**
 * 路网三层的**基准线宽**（主 / 支两档，单位屏幕像素，取值对应 `fitZoom` 档）。
 * 缩远时由 `applyLineScale()` 按档位整体折算 —— 这里只放基准值，别再散落魔法数字。
 */
const LINE_W_CASING: readonly [number, number] = [11, 9]
const LINE_W_HEAT: readonly [number, number] = [26, 22]
const LINE_W_LINE: readonly [number, number] = [5.5, 4.5]

/**
 * 默认视野（取景后）的 zoom。`fitZoom` 之后才知道，所以先给 14 兜底，
 * 由 `fitStationInstant()` / `fitOverviewInstant()` 在 `fitBounds()` 之后写回。
 *
 * 为什么不能写死：Z 站演示范围 500 m、GZ 站 1000 m，两站默认档本来就不同。
 */
let fitZoom = 14

/**
 * 线宽随缩放的系数（业主 2026-10-20 定版口径）：
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

/** 上一次贴上去的线宽系数（避免每帧重建表达式；`force` 用于换样式后强制重贴） */
let lastLineScale = -1

/**
 * 把当前缩放档折算成线宽 / 热力透明度贴回图层（`move` 事件里逐帧调）。
 *
 * 三层的线宽表达式与 `lineLayerSpecs()` 里的**结构保持一致**（含「凸显路线」压灰那两支），
 * 否则一旦开启路线凸显，压灰段会突然变回粗线。
 *
 * `force = true` 的两个时机：① `fitZoom` 刚被取景函数改写；
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
    ['case', ['==', ['get', 'emphasis_gray'], true], 3.5 * s,
      widthExpr(LINE_W_CASING[0] * s, LINE_W_CASING[1] * s)],
  )
  // 逐层判存在：本函数会在 `load` / 取景 / 换样式多个时机被调，此时三层未必都挂好了；
  // 少判一层就会 `setPaintProperty` 抛错，把调用方（可能是镜头状态机）整段打断，
  // 表现是「路网一直不显示、图钉却在」（图钉是 DOM Marker，不依赖图层）。
  if (map.getLayer(LAYER_HEAT)) {
    map.setPaintProperty(LAYER_HEAT, 'line-width', widthExpr(LINE_W_HEAT[0] * s, LINE_W_HEAT[1] * s))
    map.setPaintProperty(LAYER_HEAT, 'line-opacity', ['*', ['get', 'heat'], heatFadeOf(zoom)])
  }
  if (map.getLayer(LAYER_LINE)) {
    map.setPaintProperty(
      LAYER_LINE,
      'line-width',
      ['case', ['==', ['get', 'emphasis_gray'], true], 2 * s,
        widthExpr(LINE_W_LINE[0] * s, LINE_W_LINE[1] * s)],
    )
  }
}

/**
 * 记下「当前视角的默认档」，并立刻按它重算一遍线宽 / 热力 / 图钉系数。
 *
 * ⚠️ 三个调用面，少一个就会让整单失效（独立审查 P0）：
 *   ① `fitStationInstant()` / `fitOverviewInstant()` —— 无动画取景；
 *   ② `syncCamera()` 里 `await flyToStation()` / `await flyToOverview()` 之后 ——
 *      **这条才是「全国 → 点站」的主路径**（快链 `?station=` 也走它）。`flyToStation()`
 *      内部 `fitBounds` 走的是动画版，**不经过 ①② 的 instant 版**，所以这里不补写，
 *      `fitZoom` 会一直停在首屏全国那一档（≈3）：站内 `d = fitZoom - zoom` 恒为负，
 *      `lineScaleOf / heatFadeOf / camPinScaleOf` 全部恒等 1，业主反馈的「缩远糊成一片」
 *      在最常用的一条路上**一点没改**。
 *   ③ `applyViewState()`（换底图样式后）—— 只重贴 paint，不动 `fitZoom`。
 *
 * 取的是取景**之后**的实测 zoom，不能写死：Z 站演示范围 500 m、GZ 站 1000 m，
 * 两站 `fitBounds` 落到的档位本来就不同。
 */
function commitFitZoom(map: MapLibreMap): void {
  const zoom = map.getZoom()
  fitZoom = zoom
  applyLineScale(map, true)
  applyCameraPinScale(map, true)
  // ⚠️ 2026-10-29 起这里**不再重建方向标记数据**：位置与朝向已与视口无关（50% 弧长点 /
  // 双向段 50% 一支双头箭头零偏移 / 局部切线方位角），尺寸走 `icon-size` 的 zoom 插值
  // 表达式，缩放由 MapLibre 自己插值。旧代码在这里 `applyDirectionScale()` +
  // `refreshDirectionData()`，正是「换分辨率就错位」的根源，整条路径已删。
}

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

/**
 * 路线底衬层用：**所有**语义组（规划 / 离站 / 备选）的段号并集，与具体语义无关。
 * 底衬只看"这段在不在任意一条路线上"，不看它属于哪一组 —— 三条同色之后，
 * 底衬也必须同样同色，否则会在路线上画出语义边。
 */
function routeAllFilter(): FilterSpecification {
  return routeFilterOf('arrival', 'departure', 'alternative')
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

/**
 * 「两条备选共用同一段」时只让小序号那条画（业主 2026-10-28 反馈：备用路线与绿色路面
 * 重叠处看着发紫、发脏）。
 *
 * 病根是**两套 3 px 深蓝虚线各带一条 2 px 白边、分别向左右偏 2 px**，在同一条路上紧贴成
 * 「深蓝-白-深蓝」三明治；白边把中间的判级绿漂成灰紫，远看就是一条脏色带。
 * 共用段只留一条路线（备选 1 优先）后，这条路上只剩单色虚线 + 单侧白边，不再产生交界脏色。
 *
 * 注意：这**不改变任何路线数据**，只决定共用段归谁画 —— 两张路线卡仍然各自如实列出自己的段号。
 */
function routeIdsOnlyInAlternative(n: 1 | 2): string[] {
  const own = routeIdsOfAlternative(n)
  const other = routeIdsOfAlternative(n === 1 ? 2 : 1)
  const taken = new Set(other)
  // 备选 1 优先：备选 2 主动让出共用段；备选 1 则保留全部自有段
  return n === 2 ? own.filter((id) => !taken.has(id)) : own
}

function altFilterExclusive(n: 1 | 2): FilterSpecification {
  return ['in', ['get', 'segment_id'], ['literal', routeIdsOnlyInAlternative(n)]]
}

/**
 * 被选中的那条路线（业主 2026-10-28 口径）：
 *   规划路线 = 品牌蓝、未选中的备用路线 = 中蓝、**被选中的路线（不管它原本是推荐还是备选）= 天蓝**。
 *
 * 所以「选中」不是独立的第五种颜色，而是**覆盖掉**该路线原本的蓝色档：
 * 选中层画在最上面（`LAYER_ROUTE_PICK`），同时把底层里这条路线自己的段号从它的
 * 常规图层 filter 里剔除 —— 否则天蓝细线会被自己的中蓝粗线盖住（MapLibre 不做 alpha 混合替换）。
 */
function isPicked(g: RouteHighlight): boolean {
  const key = props.pickedRouteKey ?? null
  if (!key) return false
  return (g.key ?? `${g.kind}:${altIndex(g)}`) === key
}

function routeIdsOfPicked(): string[] {
  const out = new Set<string>()
  for (const g of props.routes ?? []) {
    if (!isPicked(g)) continue
    for (const id of g.segments) out.add(id)
  }
  return [...out]
}

/** Legacy（表达式式）filter 的联合类型里 `['all', ...]` 的第二项必须是表达式子集，
 *  而本文件其余 filter 都用 `FilterSpecification`（含 boolean 分支）——类型上拼不起来。
 *  这里按 Legacy 形状收窄：`['all', legacy, ['!', ['in', ...]]]` 是 MapLibre 支持的标准写法。 */
function routeFilterExcludingPicked(base: FilterSpecification): FilterSpecification {
  const picked = routeIdsOfPicked()
  if (picked.length === 0) return base
  const exclude = ['!', ['in', ['get', 'segment_id'], ['literal', picked]]]
  return ['all', base, exclude] as unknown as FilterSpecification
}

/** 选中路线的图层 filter（没有选中路线时永不命中，图层等于不画） */
function pickedRouteFilter(): FilterSpecification {
  return ['in', ['get', 'segment_id'], ['literal', routeIdsOfPicked()]]
}

/**
 * 图例里「已选中：XX」那一行的名字（业主 2026-10-28）。
 * 空串 = 没有选中任何整条路线（或选中的那条当前不在可见分组里）→ 图例不出这行。
 */
const pickedRouteName = computed<string>(() => {
  const key = props.pickedRouteKey ?? null
  if (!key) return ''
  for (const g of props.routes ?? []) {
    const gk = g.key ?? (g.kind === 'alternative' ? `alt:${altIndex(g)}` : g.kind)
    if (gk !== key) continue
    if (g.kind === 'arrival') return '规划路线'
    if (g.kind === 'departure') return '离站路线'
    return `备选 ${altIndex(g)}`
  }
  return ''
})

/** 任一组路线存在时才在图上画图例（否则不占地方） */
const hasRoutes = computed(() => (props.routes ?? []).some((g) => g.segments.length > 0))
/** 图例里的「备选 N 条」：按实际分组计数，不足 2 条时如实少画（不凑等价路线） */
const altRouteCount = computed(
  () => (props.routes ?? []).filter((g) => g.kind === 'alternative' && g.segments.length > 0).length,
)

/**
 * 本组件自有的图层（按绘制顺序：底衬 → 热力 → 色线 → 路线浅色底衬 → 路线 → 选中路段描边）。
 * 同一份规格用在两处：建图时按顺序 `addLayer`；底图样式合进来时作为 `layers` 尾部一起挂载
 * —— **两处只有一份定义**，不会出现"底图在/不在时路网长得不一样"。
 *
 * 颜色模式的差异**不进这张表**：它只改 `paint` / `visibility` / 源数据
 * （`colorOf()` / `coveredOf()` / `heatOf()` + `applyModeLayers()`），
 * 不产生第二套图层规格 —— 否则两套 specs 迟早不同步。
 */
function lineLayerSpecs(): LineLayerSpecification[] {
  return [
    // ---- 真值路网底衬（2026-10-29 演示验收）：先铺灰路缘、再铺白路面，然后才轮到彩色路段 ----
    {
      id: LAYER_ROADS_CASING,
      type: 'line',
      source: ROADS_SRC,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': roadsColorByClass(roadsEdgeColors()),
        // 场内小路压在建筑面上时容易显得"多了一层厚边"，按分类压一档透明度退回背景；
        // 干道保持实色 —— 它是业主看"线是不是长在路上"的第一参照物，不能虚。
        'line-opacity': [
          'match', ['get', 'cls'],
          'arterial', 1, 'link', 1, 'local', 0.85, 'aisle', 0.8,
          1,
        ] as ExpressionSpecification,
        'line-width': roadsByClass(ROADS_W_EDGE),
      },
    },
    {
      id: LAYER_ROADS_LINE,
      type: 'line',
      source: ROADS_SRC,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': roadsColorByClass(roadsRoadColors()),
        'line-opacity': [
          'match', ['get', 'cls'],
          'arterial', 1, 'link', 1, 'local', 0.9, 'aisle', 0.85,
          1,
        ] as ExpressionSpecification,
        'line-width': roadsByClass(ROADS_W_ROAD),
      },
    },
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
          widthExpr(LINE_W_CASING[0], LINE_W_CASING[1]),
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
          widthExpr(LINE_W_LINE[0], LINE_W_LINE[1]),
        ],
        'line-opacity': [
          'case',
          ['==', ['get', 'emphasis_gray'], true],
          0.55,
          ['case', ['==', ['get', 'covered'], false], 0.4, 1],
        ],
      },
    },
    // ---- 路线浅色底衬（IKRK8B）：比路线宽一圈的半透明白，压在 LAYER_LINE 之上、所有路线之下 ----
    // 业主截图里的真问题：一条路上叠了三层（判级色 → 离站紫 halo → 路线色），路线压住判级色后
    // 两侧只露出 1 px 的绿 / 橙碎片，颜色读起来是脏的。底衬把这圈碎片整段盖掉 —— 路线不再是
    // "挤在彩色路面里的一条线"，而是"压在干净浅色路面上的一条线"。
    // 为什么是**半透明白**而不是实白：路网底衬与判级色边缘还应透出来一点，否则路线走位会和
    // 真实道路脱离；0.82 是"碎片看不见、路面仍在"的折中（业主看截图后认可的一档）。
    {
      id: LAYER_ROUTE_BED,
      type: 'line',
      source: SRC,
      filter: routeAllFilter(),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#FFFFFF', 'line-width': 8, 'line-opacity': 0.82 },
    },
    // 备选 1 / 备选 2：**同为浅蓝**、同宽，靠虚线节律（长虚 12/6、短虚 2.5/4.5）+ ±2 px 平行偏置
    // 区分（业主 2026-10-29 反转后：选中 = 品牌蓝强，其余一律浅蓝弱，三条不用色相区分）。
    // 白边（halo）透明度 0.35：原来的 0.65 会把中间夹的判级绿漂成灰紫（业主反馈「看着像紫色」）。
    {
      id: LAYER_ROUTE_ALT1_HALO,
      type: 'line',
      source: SRC,
      filter: routeFilterExcludingPicked(altFilterExclusive(1)),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#FFFFFF',
        'line-width': 9,
        'line-offset': -2,
        'line-opacity': 0.35,
      },
    },
    {
      id: LAYER_ROUTE_ALT1,
      type: 'line',
      source: SRC,
      filter: routeFilterExcludingPicked(altFilterExclusive(1)),
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
      filter: routeFilterExcludingPicked(altFilterExclusive(2)),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#FFFFFF',
        'line-width': 9,
        'line-offset': 2,
        'line-opacity': 0.35,
      },
    },
    {
      id: LAYER_ROUTE_ALT2,
      type: 'line',
      source: SRC,
      filter: routeFilterExcludingPicked(altFilterExclusive(2)),
      layout: { 'line-cap': 'butt', 'line-join': 'round' },
      paint: {
        'line-color': ROUTE_ALT2_COLOR,
        'line-width': 3,
        'line-offset': 2,
        'line-dasharray': [2.5, 4.5],
        'line-opacity': 0.95,
      },
    },
    // 离站路线：紫色实线（不在「规划 / 备用 / 选中」这条行程层级里）
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
      filter: routeFilterExcludingPicked(routeFilterOf('departure')),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': ROUTE_DEPART_COLOR, 'line-width': 3, 'line-opacity': 0.92 },
    },
    // 规划路线（主推荐，**未被选中时**）：浅蓝实线 —— 「弱」那一档
    {
      id: LAYER_ROUTE_HALO,
      type: 'line',
      source: SRC,
      filter: routeFilter(),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': ROUTE_IDLE_COLOR, 'line-width': 13, 'line-opacity': 0.22 },
    },
    {
      // ⚠️ 实线与旧版虚线的差别：IKMF1W 起推荐路线用**实线**（"当前 / 已选"语义），
      //    备选是虚线。2026-10-29 业主反转配色后：推荐与备选**同色同宽**（浅蓝 3 px），
      //    只靠线型（实线 vs 虚线）+ 平行偏置区分；"选中"才升级为品牌蓝 4.2 px。
      id: LAYER_ROUTE,
      type: 'line',
      source: SRC,
      filter: routeFilterExcludingPicked(routeFilter()),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': ROUTE_IDLE_COLOR, 'line-width': 3, 'line-opacity': 0.95 },
    },
    // 被选中的那条路线（品牌蓝 4.2 px，压在规划 / 备选之上）：底色图层已把它的段号剔除，
    // 所以这里不会出现「浅蓝细线把品牌蓝粗线盖住」。
    {
      id: LAYER_ROUTE_PICK_HALO,
      type: 'line',
      source: SRC,
      filter: pickedRouteFilter(),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': ROUTE_PICKED_COLOR, 'line-width': 13, 'line-opacity': 0.22 },
    },
    {
      id: LAYER_ROUTE_PICK,
      type: 'line',
      source: SRC,
      filter: pickedRouteFilter(),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': ROUTE_PICKED_COLOR, 'line-width': 4.2, 'line-opacity': 1 },
    },
    // 选中**路段**描边：中性深灰虚线（IKRK8B C 节）。
    // ⚠️ 原来是品牌蓝 `#0052D9` —— 和「选中的路线」共用同一支蓝，一色两义，
    //    业主「分不清这种带颜色的路线」的根因就在这：他以为那条蓝虚线是路线，其实是路段选中描边。
    //    改中性色后，「虚线 = 当前选中的那一段」只表示选中，不与任何路线语义抢颜色。
    {
      id: LAYER_SELECTED,
      type: 'line',
      source: SRC,
      filter: selectedFilter(),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': SEGMENT_SELECTED_STROKE,
        'line-width': 2.4,
        'line-dasharray': [4, 6],
        'line-opacity': 0.9,
      },
    },
  ]
}

// ---- IKPFVN · 全国视角：站点 pin / 兜底轮廓 / 三态图层开关 / 镜头取景 ----

/**
 * 镜头状态（由 `shared/mapMotion.ts` 的状态机驱动）。本组件**只读它**来决定图层显隐：
 *   `national`                 → 站点 pin 层可见，路网 / 路线层隐藏
 *   `leaving` / `entering`（过渡中）→ 与全国同（pin 可见、路网隐藏）
 *   （2026-10-23 起没有 `panning`：缩远与平移合成一段，见 mapMotion.ts 文件头）
 *   `station`                  → 反过来
 */
const motionPhase = ref<MotionPhase>(props.mapMode === 'station' ? 'station' : 'national')

/** 全国站表（生成物 `stations.generated.ts`，不在这里拼）—— pin / 浮层卡片 / 镜头目标共用 */
const stations = computed<StationEntry[]>(() => stationEntries())

function stationGeoJson(): FeatureCollection {
  const features: Feature<Point>[] = stations.value.map((s, index) => ({
    type: 'Feature' as const,
    // 数字 id：`setFeatureState` / `removeFeatureState` 靠它定位一个站（不能用站键字符串）
    id: index,
    properties: {
      key: s.key,
      name: s.name,
      segments: s.segment_count ?? 0,
      label_icon: STATION_LABEL_ICON_PREFIX + s.key,
    },
    geometry: { type: 'Point' as const, coordinates: [s.lon, s.lat] },
  }))
  return { type: 'FeatureCollection', features }
}

/**
 * 站名标签图片（canvas 生成，不依赖字体 glyphs）。
 *
 * 为什么不用 `text-field`：`text-field` 必须配底图样式的 `glyphs`，而**本地兜底样式没有 glyphs**
 * —— 底图拉不到时那一层会直接报 `use of "text-field" requires a style "glyphs" property`，
 * 控制台脏了、标签也画不出来。canvas 图片在任何样式下都能画（方向标记也是这么干的）。
 */
function stationLabelImage(name: string): ImageData {
  const pad = 6
  const height = 23
  const font = '600 14px "PingFang SC", "Microsoft YaHei", system-ui, sans-serif'
  const canvas = document.createElement('canvas')
  const probe = canvas.getContext('2d')
  if (!probe) return new ImageData(1, 1)
  probe.font = font
  const width = Math.ceil(probe.measureText(name).width) + pad * 2
  // 2× 后备缓冲：高分屏上文字不糊
  canvas.width = Math.ceil(width * 2)
  canvas.height = height * 2
  const ctx = canvas.getContext('2d')
  if (!ctx) return new ImageData(1, 1)
  ctx.scale(2, 2)
  ctx.fillStyle = 'rgba(255, 255, 255, 0.95)'
  ctx.strokeStyle = 'rgba(71, 85, 105, 0.55)'
  ctx.lineWidth = 1
  if (typeof ctx.roundRect === 'function') {
    ctx.beginPath()
    ctx.roundRect(0.5, 0.5, width - 1, height - 1, 6)
    ctx.fill()
    ctx.stroke()
  } else {
    ctx.fillRect(0.5, 0.5, width - 1, height - 1)
    ctx.strokeRect(0.5, 0.5, width - 1, height - 1)
  }
  ctx.font = font
  ctx.fillStyle = '#1F2937'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(name, width / 2, height / 2 + 1)
  return ctx.getImageData(0, 0, canvas.width, canvas.height)
}

/** 注册站名标签图标（换样式后要重新注册，`setStyle` 会清空 image 资源） */
function addStationImages(map: MapLibreMap): void {
  for (const s of stations.value) {
    const name = STATION_LABEL_ICON_PREFIX + s.key
    if (!map.hasImage(name)) map.addImage(name, stationLabelImage(s.name))
  }
}

/** 站点三个图层：命中区（透明大圆）→ 实心圆（选中环就画在它身上）→ 站名 */
function stationLayerSpecs(): (CircleLayerSpecification | SymbolLayerSpecification)[] {
  const selected: ExpressionSpecification = ['boolean', ['feature-state', 'selected'], false]
  const hovered: ExpressionSpecification = ['boolean', ['feature-state', 'hover'], false]
  return [
    {
      id: LAYER_STATION_HIT,
      type: 'circle',
      source: STATION_SRC,
      // 半径 15 px → 30 px 直径热区（要求 ≥ 24 px）；全透明，视觉上看不见
      paint: { 'circle-radius': 15, 'circle-color': '#000000', 'circle-opacity': 0 },
    },
    {
      id: LAYER_STATION_DOT,
      type: 'circle',
      source: STATION_SRC,
      paint: {
        // 选中环不另建图层：同一图层用 feature-state 把半径 / 描边 / 颜色一起切
        'circle-radius': ['case', selected, 9, ['case', hovered, 7.5, 6]],
        'circle-color': ['case', selected, BRAND, STATION_DOT_COLOR],
        'circle-stroke-width': ['case', selected, 3, 1.5],
        'circle-stroke-color': '#FFFFFF',
        'circle-stroke-opacity': 0.95,
      },
    },
    {
      id: LAYER_STATION_LABEL,
      type: 'symbol',
      source: STATION_SRC,
      layout: {
        'icon-image': ['get', 'label_icon'],
        'icon-anchor': 'bottom',
        'icon-offset': [0, -10],
        // ⚠️ icon-size 约 0.5（不是 1）：标签图片是 **2× 后备缓冲**（高分屏不糊），
        //    按 1 渲染就是两倍大 —— 首版就是这么大得餐人（详见文件内注释）。
        // 随缩放略放大：全国（3~4 档）不抢视线，接近站区（6 档）才看得清。
        'icon-size': ['interpolate', ['linear'], ['zoom'], 3, 0.5, 6, 0.62],
        // 两个条站相距约 100 km，在全国缩放下不到 10 px —— 强制全部画会叠成一团，
        // 交给 MapLibre 的碰撞检测：叠不下时只留一个，放大自然都出来。
        'icon-allow-overlap': false,
        'icon-ignore-placement': false,
      },
    },
  ]
}

/** 上一帧高亮 / 选中的站（清 feature-state 时要先知道是谁） */
let selectedStationKey: string | null = null
let hoverStationKey: string | null = null
/** 被悬停的站（DOM 浮牌用）。两个条站相距不到 10 px（全国缩放），光有 pin 分不清谁是谁 */
const hoverStation = ref<StationEntry | null>(null)

/** 把“当前站”的选中环贴到图层上（站区视角才高亮：全国里没有“当前站”这回事） */
function syncStationSelection(map: MapLibreMap): void {
  if (!map.getSource(STATION_SRC)) return
  const next = props.mapMode === 'station' ? activePackKey() : null
  if (selectedStationKey !== null) {
    const prev = stations.value.findIndex((s) => s.key === selectedStationKey)
    if (prev >= 0) map.removeFeatureState({ source: STATION_SRC, id: prev }, 'selected')
  }
  selectedStationKey = next
  if (next === null) return
  const index = stations.value.findIndex((s) => s.key === next)
  if (index >= 0) map.setFeatureState({ source: STATION_SRC, id: index }, { selected: true })
}

/** 悬停高亮（只改 feature-state，不重建图层、不重建数据） */
function syncStationHover(map: MapLibreMap, key: string | null): void {
  if (hoverStationKey === key) return
  const prev = stations.value.findIndex((s) => s.key === hoverStationKey)
  if (prev >= 0) map.removeFeatureState({ source: STATION_SRC, id: prev }, 'hover')
  hoverStationKey = key
  hoverStation.value = stations.value.find((s) => s.key === key) ?? null
  const index = stations.value.findIndex((s) => s.key === key)
  if (index >= 0) map.setFeatureState({ source: STATION_SRC, id: index }, { hover: true })
}

/** 悬停站点浮牌落点 = pin 正上方（与摄像头 / 落客点浮牌同一套夹边逻辑） */
const stationChipStyle = computed(() => {
  const map = mapRef.value
  const s = hoverStation.value
  void camTick.value // 地图动过就重算
  if (!map || !s) return {}
  const pt = map.project([s.lon, s.lat])
  const w = containerRef.value?.clientWidth ?? 0
  const width = ST_CHIP_W
  const rawLeft = Math.max(6, pt.x - width / 2)
  const left = w > width + 12 ? Math.min(rawLeft, w - width - 6) : 6
  return { left: `${left}px`, top: `${Math.max(6, pt.y - 76)}px` }
})

/** 站点源 + 站名图标备齐（图层顺序同上，统一交给 `ownLayerSpecs()`） */
function ensureStationSource(map: MapLibreMap): void {
  addStationImages(map)
  if (!map.getSource(STATION_SRC)) {
    map.addSource(STATION_SRC, { type: 'geojson', data: stationGeoJson() })
  }
}

// ---- 底图兜底轮廓（Natural Earth 1:110m 简化，公有领域）----

/**
 * 兜底轮廓数据。只在**真的用得上**的时候拉一次（底图不可用时），懒加载 + 模块内缓存：
 * 4.3 KB 的文件没必要每次都请求，也不该在底图正常时白占带宽。
 */
const outlineData = shallowRef<FeatureCollection | null>(null)
let outlineLoading: Promise<FeatureCollection | null> | null = null

function loadOutline(): Promise<FeatureCollection | null> {
  if (outlineData.value) return Promise.resolve(outlineData.value)
  if (outlineLoading) return outlineLoading
  outlineLoading = (async () => {
    try {
      const data = JSON.parse(chinaOutlineText) as FeatureCollection
      if (!data || data.type !== 'FeatureCollection') return null
      outlineData.value = data
      return data
    } catch {
      // 兜底图形的兜底：解析失败就只画站点 pin（依然不白屏）
      return null
    }
  })()
  return outlineLoading
}

function outlineSource(): GeoJSONSourceSpecification {
  return { type: 'geojson', data: outlineData.value ?? EMPTY_FC }
}

/** 淡填充 + 细描边：它只是“这里有块陆地”的提示，不能抢路网 / pin 的视线 */
function outlineLayerSpecs(): (FillLayerSpecification | LineLayerSpecification)[] {
  return [
    {
      id: LAYER_OUTLINE_FILL,
      type: 'fill',
      source: OUTLINE_SRC,
      paint: { 'fill-color': '#C7D2FE', 'fill-opacity': 0.3 },
    },
    {
      id: LAYER_OUTLINE_LINE,
      type: 'line',
      source: OUTLINE_SRC,
      paint: { 'line-color': '#94A3B8', 'line-width': 1.1, 'line-opacity': 0.6 },
    },
  ]
}

/** 本组件自有图层的**唯一一份**绘制顺序（底图在 / 不在时长得一样，靠的就是只有这一份定义） */
type OwnLayer =
  | LineLayerSpecification
  | SymbolLayerSpecification
  | CircleLayerSpecification
  | FillLayerSpecification

/**
 * 以 (lon, lat) 为圆心、radiusM 为半径的近似圆环（36 段多边形）。
 * 米→度换算用球面近似（lat 度 ≈ 110.54 km，lon 度 ≈ 111.32·cos(lat) km），
 * 站区尺度（≤1 km、半径 35 m）下误差可忽略；这是**演示范围圈**，不是测地圆。
 */
function circleRing(lon: number, lat: number, radiusM: number, segs = 36): [number, number][] {
  const ring: [number, number][] = []
  const cosLat = Math.cos((lat * Math.PI) / 180)
  for (let i = 0; i <= segs; i++) {
    const a = (i / segs) * 2 * Math.PI
    ring.push([
      lon + (radiusM * Math.cos(a)) / (111_320 * cosLat),
      lat + (radiusM * Math.sin(a)) / 110_540,
    ])
  }
  return ring
}

/**
 * 落客区（终点区域）GeoJSON：当前站点包每个落客点一个圆。
 * 数据源 = 站点包 `dropoffs`（与右栏「本段附近的落客点」同一份，`lm-pin`「落」同族）；
 * 切站由 `applyViewState()` 重setData，不在包里另存一份。
 */
function dropZoneGeoJson(): FeatureCollection {
  const features = activePack().dropoffs.map((d) => ({
    type: 'Feature' as const,
    properties: { id: d.id, name: d.name },
    geometry: { type: 'Polygon' as const, coordinates: [circleRing(d.lon, d.lat, DROPZONE_RADIUS_M)] },
  }))
  return { type: 'FeatureCollection', features }
}

/** 高亮层 filter：选中路线的终点落客点（`routeEnd.point_id`）；没选中时永假（全不亮） */
function dropZoneHighlightFilter(): FilterSpecification {
  const id = props.routeEnd?.point_id ?? '__none__'
  return ['==', ['get', 'id'], id] as unknown as FilterSpecification
}

function dropZoneLayerSpecs(): OwnLayer[] {
  const common = { source: DZ_SRC, filter: ['all'] as unknown as FilterSpecification }
  return [
    {
      id: LAYER_DZ_FILL,
      type: 'fill',
      ...common,
      paint: { 'fill-color': DZ_COLOR, 'fill-opacity': 0.1 },
    },
    {
      id: LAYER_DZ_HL,
      type: 'fill',
      ...common,
      // 选中路线的终点落客点高亮；默认 filter 永假（id 不可能为空串）
      filter: ['==', ['get', 'id'], '__none__'] as unknown as FilterSpecification,
      paint: { 'fill-color': DZ_COLOR, 'fill-opacity': DZ_HL_OPACITY },
    },
    {
      id: LAYER_DZ_LINE,
      type: 'line',
      ...common,
      paint: { 'line-color': DZ_COLOR, 'line-width': 1.4, 'line-opacity': 0.55 },
    },
  ]
}

function ownLayerSpecs(): OwnLayer[] {
  const own: OwnLayer[] = [...outlineLayerSpecs(), ...lineLayerSpecs()]
  // 方向标记插在路线图层之前（路网 → 方向标 → 落客区 → 路线 → 选中）
  const at = own.findIndex((layer) => layer.id === LAYER_ROUTE_ALT1_HALO)
  const insertAt = at < 0 ? own.length : at
  own.splice(insertAt, 0, directionLayerSpec(), ...dropZoneLayerSpecs())
  // 路线行进箭头压在路线之上、站点 pin 之下（顺序只此一份）
  own.push(routeArrowLayerSpec())
  // 站点 pin 永远在最上层（切站入口不能被路网盖住）
  own.push(...stationLayerSpecs())
  return own
}

function setLayerVisible(map: MapLibreMap, id: string, visible: boolean): void {
  if (!map.getLayer(id)) return
  const next = visible ? 'visible' : 'none'
  if (map.getLayoutProperty(id, 'visibility') === next) return
  map.setLayoutProperty(id, 'visibility', next)
}

/**
 * **三态图层开关的唯一一处**（全国 / 过渡中 / 站区）：
 *
 * | 图层族                    | national | leaving·entering（过渡中）| station |
 * |---------------------------|----------|--------------------------|---------|
 * | 路网 / 热力 / 选中 / 路线 |  隐藏    |          隐藏            |  可见   |
 * | 方向标记                  |  隐藏    |          隐藏            | 按开关  |
 * | 站点 pin（命中/圆/文字）  |  可见    |          可见            |  隐藏   |
 * | 兜底轮廓                  | 底图≠ok时可见 | 同左                 |  隐藏   |
 *
 * 为什么过渡中也藏路网：那时父级已经把上一站的 `routes` 清空了，但**几何还是上一站的**
 * ——“地图缩小时还看得见旧站路网”正是 IKPFVN D4 要禁的东西。
 */
function applyModeLayers(map: MapLibreMap): void {
  const atStation = motionPhase.value === 'station'
  for (const spec of lineLayerSpecs()) setLayerVisible(map, spec.id, atStation)
  // 灰底版（`colorMode='gray'`）：**一条路线都不画**（业主 2026-10-29）。
  // 这一档的承诺是"只留路网结构"，任何路线色（连底衬的白）都不属于这一档 —— 所以整族藏掉。
  // ⚠️ 与 `custom` 档的分界就在这一句：custom 档**画路线**（路线是它的全部内容），
  //    gray 档**不画**。两档都灰、但一个带路线一个不带，这是它们唯一且必须成立的区别。
  const routesVisible = atStation && !isGrayMode.value
  for (const id of ROUTE_LAYER_IDS) setLayerVisible(map, id, routesVisible)
  // 底图道路与自绘真值路网是**互斥的一对**：站区有底衬就让底图道路退出，其余场合放回来
  applyBasemapRoadMask(map, atStation)
  setLayerVisible(map, LAYER_DIRECTION, atStation && directionDrawable.value)
  // 路线行进箭头：只有拿到后端 steps 才画，且只在站区（全国视角不画）
  setLayerVisible(map, LAYER_ROUTE_ARROW, atStation && routeArrowDrawable.value)
  // 落客区（终点区域）也是「某一个站」的面：全国不画、到站才画；「落客点」开关关掉时也不画
  // （否则视角往返/换站后 applyModeLayers 会把关掉的圈重新打开，与开关状态打架）
  const dropZoneVisible = atStation && dropoffsVisible.value
  setLayerVisible(map, LAYER_DZ_FILL, dropZoneVisible)
  setLayerVisible(map, LAYER_DZ_HL, dropZoneVisible)
  setLayerVisible(map, LAYER_DZ_LINE, dropZoneVisible)
  setLayerVisible(map, LAYER_STATION_HIT, !atStation)
  setLayerVisible(map, LAYER_STATION_DOT, !atStation)
  setLayerVisible(map, LAYER_STATION_LABEL, !atStation)
  const outline = basemap.value !== 'ok' && !atStation
  setLayerVisible(map, LAYER_OUTLINE_FILL, outline)
  setLayerVisible(map, LAYER_OUTLINE_LINE, outline)
  syncStationSelection(map)
  if (outline) void loadOutline().then((data) => {
    if (!data || disposed) return
    const src = mapRef.value?.getSource(OUTLINE_SRC) as GeoJSONSource | undefined
    if (src) void src.setData(data)
  })
}

/** 把全部自有图层挂上（建图 / 刚换完样式时调一次；顺序只有 `ownLayerSpecs()` 一份） */
function addOwnLayers(map: MapLibreMap): void {
  if (!map.getSource(OUTLINE_SRC)) map.addSource(OUTLINE_SRC, outlineSource())
  if (!map.getSource(SRC)) map.addSource(SRC, { type: 'geojson', data: routeGeoJson() })
  // 真值路网底衬：必须排在 `ownLayerSpecs()` 之前建源，否则第一层的 addLayer 会报 source 找不到
  if (!map.getSource(ROADS_SRC)) map.addSource(ROADS_SRC, { type: 'geojson', data: roadsGeoJson() })
  if (!map.getSource(DZ_SRC)) map.addSource(DZ_SRC, { type: 'geojson', data: dropZoneGeoJson() })
  ensureDirectionSource(map)
  ensureRouteArrowSource(map)
  ensureStationSource(map)
  for (const spec of ownLayerSpecs()) {
    if (!map.getLayer(spec.id)) map.addLayer(spec)
  }
  applyModeLayers(map)
  applyDropZoneVisibility(map)
}

// ---- 镜头取景（IKPFVN C 节；动效参数与状态机全在 `shared/mapMotion.ts`）----

function containerViewport(map: MapLibreMap): { width: number; height: number } {
  const c = map.getContainer()
  return { width: c.clientWidth, height: c.clientHeight }
}

/**
 * 站区取景留白：把左右栏宽度也算进去（IKPFVN C3）。
 * 栏在容器**外面**（中栏就是地图容器），所以不去重复扣，只在 `stationPadding` 里作对称余量；
 * 这里量的是 **当前真实宽度** —— 栏是滑入的，写死 296 / 396 会在拖过栏宽的页面上取偏。
 */
function sideColumnsWidth(): number {
  const self = containerRef.value
  const splitter = self?.closest('.el-splitter')
  if (!self || !splitter) return 0
  let total = 0
  for (const child of Array.from(splitter.children)) {
    if (!child.classList.contains('el-splitter-panel')) continue
    if (child.contains(self)) continue // 自己所在的中栏不算
    total += (child as HTMLElement).clientWidth
  }
  return total
}

function stationPaddingNow(map: MapLibreMap): CameraPadding {
  const view = containerViewport(map)
  return stationPadding({
    ...view,
    columnsWidth: sideColumnsWidth(),
    // 图例在宽屏是左下角浮层，会给站区最外侧的起点段让位；窄屏图例已收进折叠浮层 → 0
    legendWidth: props.legend && legendOpen.value && view.width > 900 ? 440 : 0,
  })
}

/**
 * 先量准容器尺寸再取景：左右栏刚滑入时宽高还是旧的，直接 fitBounds 会偏（IKPFVN E1）。
 *
 * ⚠️ 2026-10-23 补：光等一帧不够，必须等**宽度真的稳定**。全国 ⇄ 站区切换时左右栏是 250 ms 的
 * 宽度过渡，容器宽度在这段时间里一直在变。以前"缩远那一段"恰好占掉 700 ms，等 `fitBounds` 时
 * 布局早就稳了，所以没人发现这个漏口；现在把缩远并进一段之后，`fitBounds` 会落在过渡中途
 * （实测读到 1194 px，最终 1886 px），结果是 `← 全国` 落地后中心偏东约 24°（中国被挤到画面左侧）。
 * 这里等到"连续两帧宽高都不变"（上限 500 ms）再 resize 一次，取景就按最终尺寸算。
 */
async function resizeMap(map: MapLibreMap): Promise<void> {
  map.resize()
  const el = map.getContainer()
  const started = performance.now()
  let stableRounds = 0
  let lastW = el.clientWidth
  let lastH = el.clientHeight
  while (stableRounds < 2 && performance.now() - started < 500) {
    await new Promise<void>((resolve) => {
      window.requestAnimationFrame(() => resolve())
    })
    const w = el.clientWidth
    const h = el.clientHeight
    if (w === lastW && h === lastH) stableRounds++
    else {
      stableRounds = 0
      lastW = w
      lastH = h
    }
  }
  map.resize()
}

function fitStationInstant(map: MapLibreMap, key: string): void {
  const cam = stationCamera(key)
  if (!cam) return
  // 走 `fitStationCamera`（不是裸 `fitBounds`）：它带**缩放下限 = DIR_ZOOM_FULL**，
  // 小屏 / 窗口化进站才不会落在方向层的淡出区（1440×900 裸 fitBounds 只到 zoom 13.02，
  // 箭头全透明 —— 见 `shared/mapMotion.ts` 的 `fitBoxCamera` 注释）。
  fitStationCamera(map, cam, { padding: stationPaddingNow(map), duration: 0 })
  // 记下这一站的默认档：线宽 / 热力 / 图钉的缩放基准都相对它算（两站范围不同，不能写死）
  commitFitZoom(map)
}

function fitOverviewInstant(map: MapLibreMap): void {
  const cam = overviewCamera()
  // 全国视角**不加**缩放下限（全国就该小、箭头在此淡出是设计），但也走同一套有效性闸：
  // 1280×720 下裸 `fitBounds` 会抛 `Invalid LngLat (NaN,-90)`（留白吃掉可视框）。
  fitOverviewCamera(map, cam, { padding: overviewPadding(containerViewport(map)), duration: 0 })
  // 容器偏矮时 `fitBounds` 会把中国算到 2 档（大陆变成中间一小块）——按判定的下界抬到 3 档
  clampOverviewZoom(map)
  commitFitZoom(map)
}

/**
 * 框住一批路段（业主 2026-10-28 观感要求）：点「开始」出路线后，站区全览下三条线只有几十像素，
 * 看不出「出路线了」，所以由父级把结果路线的段号丢进来，这里平滑缩到这批段的包围盒。
 *
 * 几何口径沿用本文件既有的 `net.value`（当前站点包的路段折线，与 `routeGeoJson()` / 浮牌取点同源），
 * 不另外造一套几何、也不去读后端返回的 `edges`。
 *
 * 取不到几何（段号不在当前包里 / 地图还没就绪）时**静默 return**：不动相机、不抛错
 * —— 宁可地图停在原处，也不能因为一条段号对不上就把视野甩到别处或崩掉。
 */
function fitSegments(segmentIds: string[]): void {
  const map = mapRef.value
  if (!map || !ready.value || disposed) return
  const ids = new Set(segmentIds.filter((id) => typeof id === 'string' && id.length > 0))
  if (ids.size === 0) return
  let west = Number.POSITIVE_INFINITY
  let south = Number.POSITIVE_INFINITY
  let east = Number.NEGATIVE_INFINITY
  let north = Number.NEGATIVE_INFINITY
  let points = 0
  for (const seg of net.value) {
    if (!ids.has(seg.segment_id)) continue
    for (const [lon, lat] of seg.coords) {
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue
      if (lon < west) west = lon
      if (lon > east) east = lon
      if (lat < south) south = lat
      if (lat > north) north = lat
      points++
    }
  }
  if (points === 0) return
  // 只有一段、且几何退化成一条线（东西或南北跨度为 0）时撑开一点点，
  // 否则 MapLibre 会把它算成无限缩放（虽然有 maxZoom 兜着，但先给个有限盒子更稳）
  const minSpan = 1e-6 // ≈0.1 m，肉眼无感
  if (east - west < minSpan) {
    const mid = (east + west) / 2
    west = mid - minSpan / 2
    east = mid + minSpan / 2
  }
  if (north - south < minSpan) {
    const mid = (north + south) / 2
    south = mid - minSpan / 2
    north = mid + minSpan / 2
  }
  // 走 `fitBoxCamera`（不是裸 `fitBounds`）：① 有效性闸（1280×720 下裸 fitBounds 会抛
  // `Invalid LngLat (NaN,-90)`）；② 缩放下限 = `DIR_ZOOM_FULL` —— 框住路线本来就是为了看清箭头，
  // 落在方向层淡出区里就白框了。上限仍 18，避免单段路线被顶到最大档后失去参照。
  fitBoxCamera(
    map,
    { sw: [west, south], ne: [east, north] },
    { padding: { top: 80, right: 80, bottom: 80, left: 80 }, duration: 600, maxZoom: 18, minZoom: DIR_ZOOM_FULL, label: 'route-box' },
  )
}

/** 对父级开放的能力：目前只有「框住一批段」（父级用 `ref` 调用；`<script setup>` 默认是封闭的） */
defineExpose({ fitSegments })

/**
 * 快门标志：`flyToStation()` / `flyToOverview()` 正在跑。
 *
 * 为什么需要（2026-10-23 实测）：容器尺寸变化 / 底图换样式会触发**无动画**的"补算取景"
 * （`syncCamera(false)` → `fitStationInstant`）。补算不经过 `runSeq`，所以它不会被 `map.stop()`
 * 打断 —— 一旦在动画途中发生，就是**把相机一帧顶到终点**，动画直接看不见了
 * （实测：全国 → 点站的 1.35 s 转场被压成 0 ms 的硬切）。所以动画在跑时拒收无动画补算；
 * 补算本来只是"尺寸变了重算一次取景"，动画落点会自己把尺寸算准，跳过它不会留错。
 */
let cameraAnimating = false

/**
 * 镜头同步（唯一入口）：按 `mapMode` 决定落到全国还是落进某个站。
 * `animated=false` 只用于"不能有动画"的场合（起手建图、换完底图样式后、容器尺寸变化后的补算）。
 */
async function syncCamera(animated: boolean): Promise<void> {
  const map = mapRef.value
  if (!map || !ready.value || disposed) return
  if (!animated && cameraAnimating) return
  if (animated) cameraAnimating = true
  try {
    await runCameraSync(map, animated)
  } finally {
    if (animated) cameraAnimating = false
  }
}

async function runCameraSync(map: MapLibreMap, animated: boolean): Promise<void> {
  if (props.mapMode === 'station') {
    const key = activePackKey()
    if (!animated || !stationCamera(key)) {
      fitStationInstant(map, key)
      motionPhase.value = 'station'
      applyModeLayers(map)
      // 站包几何为空时也没别的去处：如实按“已到站”通知父级，别让数据永远挂在“过渡中”
      emit('arrived')
      return
    }
    motionPhase.value = 'leaving'
    applyModeLayers(map)
    const result = await flyToStation(map, key, {
      padding: () => stationPaddingNow(map),
      onPhase: (phase) => {
        motionPhase.value = phase
        const live = mapRef.value
        if (live) applyModeLayers(live)
      },
      beforeFit: () => resizeMap(map),
    })
    if (result.cancelled) return
    motionPhase.value = 'station'
    applyModeLayers(map)
    // 动画落站后补写 `fitZoom`：这是「全国 → 点站」的主路径，缺这一句整单的缩放逻辑全部落空
    commitFitZoom(map)
    emit('arrived')
    return
  }
  if (!animated) {
    fitOverviewInstant(map)
    motionPhase.value = 'national'
    applyModeLayers(map)
    return
  }
  motionPhase.value = 'leaving'
  applyModeLayers(map)
  const result = await flyToOverview(map, {
    padding: () => overviewPadding(containerViewport(map)),
    onPhase: (phase) => {
      motionPhase.value = phase
      const live = mapRef.value
      if (live) applyModeLayers(live)
    },
    beforeFit: () => resizeMap(map),
  })
  if (result.cancelled) return
  motionPhase.value = 'national'
  applyModeLayers(map)
  // 同上：动画退回全国后 `fitZoom` 要跟着变成全国档，否则站区档位残留
  commitFitZoom(map)
}

/**
 * 把镜头同步合并到**下一个微任务**里跑一次。
 *
 * 为什么需要合并：切站那一瞬 `mapMode` 与 `packTick` 往往**同时**变（从全国点一个站），
 * 两个 watch 各叫一次 `syncCamera()` 就会“取消一次再重开一次”——画面抖一下。
 * 合并之后同一轮只跑一次，状态机里“只允许一个动画”也就真的只剩一个。
 *
 * `resizeFirst = true`：视角切了（左右栏收起 / 滑入），必须先 `map.resize()` 再取景。
 */
let cameraPending = false
let cameraNeedsResize = false
function scheduleCameraSync(resizeFirst = false): void {
  if (resizeFirst) cameraNeedsResize = true
  if (cameraPending) return
  cameraPending = true
  void nextTick().then(async () => {
    cameraPending = false
    const map = mapRef.value
    if (!map || !ready.value || disposed) {
      cameraNeedsResize = false
      return
    }
    const needResize = cameraNeedsResize
    cameraNeedsResize = false
    if (needResize) await resizeMap(map)
    await syncCamera(true)
  })
}

/**
 * 容器尺寸一变就按**当前视角**重新取景（IKPFVN）。
 *
 * 为什么必须有：地图建在 `el-splitter` 的弹性中栏里 —— 全国模式下左右栏收起要 250 ms，
 * 挂载首帧的容器宽度也未必已经定型。按那一刻的尺寸 `fitBounds` 会把中国算到 2.3 档
 * （大陆只占中间一小块，达不到「全国大地图」的观感），而定型之后没有任何一处会再重算。
 * 尺寸真的变了（拖栏 / 窗口缩放 / 窄屏单列 / 左右栏收放）就补一次**无动画**取景。
 *
 * 三条纪律：① 动画途中不抢镜头（否则一次飞行被切成两段）；② 只在尺寸真的变了才动
 * （`ResizeObserver` 会因为一次过渡触发很多次回调）；③ 防抖 140 ms，等布局稳定再算。
 */
let resizeObserver: ResizeObserver | null = null
let resizeTimer = 0
let lastFitSize = { width: 0, height: 0 }

function watchContainerSize(map: MapLibreMap): void {
  const el = containerRef.value
  if (!el || typeof ResizeObserver === 'undefined') return
  resizeObserver?.disconnect()
  resizeObserver = new ResizeObserver(() => {
    // ① 飞行途中（leaving / entering）不插手
    if (motionPhase.value !== 'national' && motionPhase.value !== 'station') return
    window.clearTimeout(resizeTimer)
    resizeTimer = window.setTimeout(() => {
      const live = mapRef.value
      if (!live || disposed || !ready.value) return
      const size = containerViewport(live)
      // ② 尺寸没变就不动（过渡期间的中间态回调全部走到这里被挡掉）
      if (size.width === lastFitSize.width && size.height === lastFitSize.height) return
      lastFitSize = { width: size.width, height: size.height }
      void live.resize()
      // ③ 无动画：取景是"补算"，不是一次新的转场
      void syncCamera(false)
    }, 140)
  })
  resizeObserver.observe(el)
  lastFitSize = containerViewport(map)
}

// ---- 摄像头布点 ----

/** 摄像头标记（重绘 / 卸载时移除） */
let camMarkers: Marker[] = []
/** 被悬停的摄像头（浮牌钉在图钉上方，与路段浮牌区分） */
const pin = ref<CameraPin | null>(null)

/** 窄屏专用：跨断点复位（Issue IKP3EV），与桌面全局开关互不干扰。必须在 legendOpen 之前声明。 */
const narrowLegendOpen = ref(
  !(typeof window !== 'undefined' && window.matchMedia('(max-width: 1180px)').matches),
)

/**
 * 图例是否展开。两套口径合并（Issue IKP3EV + 业主 2026-10-19 追加）：
 *   · **窄屏（≤1180）**：单列后地图整行变宽，整幅图例会盖住路网主体 → 默认收起（地图优先），
 *     跨断点自动复位（见下方 `legendMq`）；
 *   · **桌面（>1180）**：原本常开、没法收；业主反馈图例压住路网后，改为读全局
 *     `legendVisible`（顶栏「设置」与地图工具条的「图例」键共用同一个状态，落 localStorage）。
 *
 * 统一到本组件的一个 computed，是为了让 `legendWidth`（取景留白要用它）只认一个来源。
 */
const legendOpen = computed<boolean>(() => {
  if (props.mapMode !== 'station') return legendVisible.value
  if (typeof window !== 'undefined' && window.matchMedia('(max-width: 1180px)').matches) {
    return narrowLegendOpen.value
  }
  return legendVisible.value
})

function toggleLegend(): void {
  if (typeof window !== 'undefined' && window.matchMedia('(max-width: 1180px)').matches) {
    narrowLegendOpen.value = !narrowLegendOpen.value
    return
  }
  setLegendVisible(!legendVisible.value)
}

/**
 * 跨断点复位图例开合（Issue IKP3EV 独立审查整改）：窄屏 ref 只在 setup 求值一次，
 * 桌面加载后再把窗口缩到 ≤1180，图例仍保持展开、会盖住地图（需刷新才复位）。
 * 监听 1180 断点：跨入窄屏默认收起（地图优先），跨回桌面交还全局开关。
 */
const legendMq = typeof window !== 'undefined' ? window.matchMedia('(max-width: 1180px)') : null
function onLegendMqChange(e: MediaQueryListEvent): void {
  narrowLegendOpen.value = !e.matches
}
onMounted(() => legendMq?.addEventListener('change', onLegendMqChange))
onUnmounted(() => legendMq?.removeEventListener('change', onLegendMqChange))

/**
 * 摄像头布点（Issue IKLX5Y；业主 2026-10-25 起画**全量 N 段 N 路**）：
 * 位置取站点包 `channels[].lon/lat`（源台账 = 登记表演示布点；演示层 = camera-plan 每段
 * offset_m 落折线，**不是路测点位**），点击跳到感知层对应通道（演示层通道也有画面，演示复用）。
 * 口径：N 段 = N 摄像头 = N 视频（演示）落图——路段有多少摄像头，图上就有多少图钉；
 * 源台账 6 路 + 演示层（Z 55 / GZ 708）= 每段一路、一段最多 1 路。
 * 实心 = 有自有样本视频源（演示，非本站现场）、空心 = 演示复用画面（取 road2/track1，
 * 标注「演示复用」，不得读成"该摄像头自己的视频"或"数据可用/真实接入"）。
 */
/**
 * 摄像头图钉随缩放收缩（业主 2026-10-20 口径「缩小地图后还是挤在一起」）。
 *
 * 为什么必须单独处理：`addCameraPins()` 用 `new Marker({ element })` 造的是 **DOM 元素**，
 * 屏幕像素恒定、**天然不随 zoom 缩**；缩远后路网只剩几十像素，20 px 的图钉却还是 20 px。
 * 方向箭头是 symbol 图层（`icon-size` 可调），图钉不是。
 *
 * ⚠️ 影响面（2026-10-25 更新）：图钉现为全量 N 段 N 路（Z 61 / GZ 708），缩放淡出对两站都生效；
 * 全国视角另有 `.mlmap.mode-national` 的 `display:none`（DOM Marker 属于某一个站，全国不画）。
 * 演示层点位是 camera-plan 每段 offset_m 落折线的演示布点，不是踏勘点位。
 *
 * 两层 DOM 的原因：MapLibre 会往它自己创建的那个元素上写 `transform: translate(...)`，
 * 如果把缩放写在同一个元素上就会**覆盖掉定位**、图钉跑位。所以外层 `.cam-pin-wrap` 交给
 * Marker 定位，内层 `.cam-pin` 只承接缩放/透明度。
 */
function camPinScaleOf(zoom: number): number {
  const d = fitZoom - zoom
  if (d <= 0) return 1
  return Math.min(1, Math.max(0.28, Math.pow(2, -d * 0.36)))
}

/** 比默认视野缩远 1 档开始淡、1.6 档彻底淡出（完全透明时放开指针事件，不挡地图操作） */
function camPinOpacityOf(zoom: number): number {
  const d = fitZoom - zoom
  if (d <= 0) return 1
  if (d >= 1.6) return 0
  return Math.max(0, 1 - (d - 1) / 0.6)
}

/** 上一次贴上去的图钉缩放（去抖，别每帧写 61 个元素的 style） */
let lastCamPinScale = -1

/**
 * 把图钉缩放 / 透明度贴到**内层**元素上（`move` 事件里逐帧调，`force` 用于换样式 / 重建图钉后）。
 * 注意找的是 `.cam-pin-wrap` 的子元素：外层是 MapLibre 的定位壳，不能碰。
 */
function applyCameraPinScale(map: MapLibreMap | null, force = false): void {
  if (!map) return
  const zoom = map.getZoom()
  const s = camPinScaleOf(zoom)
  if (!force && Math.abs(s - lastCamPinScale) < 0.004) return
  lastCamPinScale = s
  const op = camPinOpacityOf(zoom)
  for (const m of camMarkers) {
    // Marker 被移除后 `getElement()` 可能是空壳：一次异常就把 `move` 监听整段打断，
    // 地图后续的缩放/平移全部失效 —— 所以这里逐项兜住。
    const wrap = m.getElement()
    const inner = wrap?.firstElementChild as HTMLElement | null
    if (!inner) continue
    inner.style.transform = `scale(${s})`
    inner.style.opacity = String(op)
    inner.style.pointerEvents = op <= 0.01 ? 'none' : 'auto'
  }
}

function addCameraPins(map: MapLibreMap): void {
  for (const p of pins.value) {
    // 外层交给 Marker 定位，内层承接缩放（见 camPinScaleOf 上方说明）
    const wrap = document.createElement('div')
    wrap.className = 'cam-pin-wrap'
    const el = document.createElement('div')
    el.className = p.hasVideo ? 'cam-pin' : 'cam-pin empty'
    // 圈内数字 = 摄像头编号尾号（源台账 cam-01 → 01；演示层 CAM-Z-001 → 001 / CAM-GZ-708 → 708）
    el.textContent = (p.camId ?? p.source).split('-').pop() ?? p.cid
    const feedNote = p.hasVideo
      ? '有样本视频源（演示，非本站现场）'
      : p.reuseOf
        ? `演示复用画面 ← ${p.reuseOf}（公开样本视频，不是本路视频）`
        : '无视频源（画面留空）'
    el.title = `${p.cid} ${p.camId ?? p.source} · ${p.name} · ${p.segment_id} · ${
      p.demo ? '演示布点（camera-plan 演示层）· ' : '源台账布点 · '
    }${feedNote} · 点击进感知层`
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
    camMarkers.push(new Marker({ element: wrap }).setLngLat([p.lon, p.lat]).addTo(map))
  }
  // 建完立刻按当前档贴一次，否则缩远状态下重建图钉会先以 20 px 闪一下
  lastCamPinScale = -1
  applyCameraPinScale(map, true)
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
//
// IKPFVN 把取景收成两件事：全国视角 = 中国范围 `fitBounds`；站区视角 = 该站包几何的
// min/max（见 `shared/mapMotion.ts` 的 `stationCamera()`）。原先那个“适配到当前路网”的
// `fitToNetwork()` 已删：它只会在站区视角下有意义，而站区取景现在由状态机统一算，
// 两套取景各写一份必然对不上（图例留白、左右栏宽度只会在其中一处生效）。

// ---- 底图：异步、可失败、失败只丢自己 ----

/**
 * 让底图道路图层在**站区档**整族退出（2026-10-29 演示验收）。
 *
 * 为什么必须按「到站」判断、不能按 zoom 写死在样式里：底图源 TileJSON `maxzoom: 14`，
 * 站区视角 zoom≈16.5 是 overzoom，z14 瓦片里没有 service/track 级道路，本站 44 段 ramp
 * （停车场内部通道/服务道路/连接匝道）在底图上是空白 + 建筑面，彩色段看起来"悬空穿场地"；
 * 干道也被合并简化，彩色线与底图黄线错开 10~15 m。所以站区档要关掉底图道路、改用自绘真值路网。
 *
 * 但**「不在站区」时必须把底图道路放回来**：全国模式下手动放大到 z16~18 是常态
 * （演示时观众会自己滚轮），那时没有自绘路网（全国档路网图层是隐藏的），
 * 若底图道路也被 zoom 挡住，整幅地图会空成一张白纸 —— 这比"线不贴路"更难看。
 * 因此这里用运行时 `setLayerZoomRange()`，判据跟着 `motionPhase` 走，
 * 并由 `applyModeLayers()`（唯一的三态开关入口）在每次相位变化后重贴。
 *
 * 判据：① 该包**真的有**真值路网底衬（否则关掉底图道路会把站区画成空白，宁可不动）；
 *      ② 图层 id 落在 Liberty 的道路族（`road_*` / `bridge_road_*` / `tunnel_road_*`）；
 *      ③ 该层确实是底图矢量源（别误伤别家的 `road_` 图层）。
 * 已经有更小 `maxzoom` 的层保持原样（只收紧不放松）。
 */
function applyBasemapRoadMask(map: MapLibreMap, hide: boolean): void {
  if (!(activePack().roads ?? []).length) return
  // 建图/换样式瞬间 `getStyle()` 可能还没有 `layers`（真报过 `Cannot read properties of undefined
  // (reading 'layers')`），这里当"样式还没到"处理，下一次 `applyModeLayers()` 会补上
  const layers = map.getStyle()?.layers
  if (!Array.isArray(layers)) return
  for (const layer of layers) {
    if (!/^(?:bridge_|tunnel_)?road_/.test(layer.id)) continue
    if ((layer as { source?: string }).source !== OPENMAPTILES_SRC) continue
    const orig = (layer as { maxzoom?: number }).maxzoom
    const maxzoom = hide
      ? (typeof orig === 'number' ? Math.min(orig, BASEMAP_ROAD_MAXZOOM) : BASEMAP_ROAD_MAXZOOM)
      : (typeof orig === 'number' ? orig : BASEMAP_ROAD_RESTORE_MAXZOOM)
    try {
      map.setLayerZoomRange(layer.id, (layer as { minzoom?: number }).minzoom ?? 0, maxzoom)
    } catch {
      // 图层刚被 setStyle 换掉时 getStyle() 与 setLayerZoomRange 之间有窗口期，忽略即可
    }
  }
}

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
    sources: {
      ...(remote.sources ?? {}),
      // 兜底轮廓 / 站点 pin / 路网 / 方向标 / 落客区 —— 五份 source 都必须带上，否则 setStyle 之后
      // 图层在、数据源没了，地图会报错且 pin 直接消失。
      // ⚠️ `DZ_SRC` 是 2026-10-25（!82 落客区）新加的一份：当时只补进了 `addOwnLayers()`（建图那条路），
      // 漏在这里，于是**只要底图样式换过一次**（`applyBasemap` 成功或 `dropBasemap` 退回兜底），
      // 新样式里的三个落客区图层就找不到 source —— MapLibre 在 `_load` 里直接抛
      // `layers[N]: source "hubflow-dropzone" not found`，整份样式加载失败、底图整块不画
      // （表现就是"底图刷新不出来"，且退回兜底样式也照样报错）。新增自有 source 时**两处都要加**。
      [OUTLINE_SRC]: outlineSource(),
      [SRC]: { type: 'geojson', data: routeGeoJson() },
      // 真值路网底衬（2026-10-29）：漏在这里的话，底图一换样式第一层 addLayer 就报
      // `source "hubflow-truth-roads" not found`，整份样式加载失败（同 DZ_SRC 那次事故）
      [ROADS_SRC]: { type: 'geojson', data: roadsGeoJson() },
      [DIR_SRC]: { type: 'geojson', data: directionGeoJson() },
      [STATION_SRC]: { type: 'geojson', data: stationGeoJson() },
      [DZ_SRC]: { type: 'geojson', data: dropZoneGeoJson() },
      // 路线行进箭头（2026-10-29）：`routeArrowLayerSpec()` 在 `ownLayerSpecs()` 里，所以这里
      // **必须**同时下发 source —— 否则 MapLibre 在 `_load` 里直接抛
      // `layers[N]: source "hubflow-route-arrow" not found`，整份样式加载失败（dev-c 实测报错）。
      [ROUTE_ARROW_SRC]: { type: 'geojson', data: routeArrowGeoJson() },
    },
    // 自有图层的绘制顺序只有 `ownLayerSpecs()` 一份；
    // 底图道路的退出不在这里做（那是"到站才关"的运行时状态，见 `applyBasemapRoadMask()`），
    // 合成样式时保持远程原样 —— 否则全国档放大就成了白纸。
    layers: [...(remote.layers ?? []), ...ownLayerSpecs()],
  }
}

/** 把底图那一层**整层撤掉**：样式换回"本地兜底 + 本组件图层"，路网一行不动 */
function dropBasemap(map: MapLibreMap): void {
  window.clearTimeout(retryTimer)
  if (!remoteApplied) return // 本来就是"只有路网"，不必再换一次样式
  remoteApplied = false
  map.once('styledata', () => {
    if (disposed) return
    // 换样式后不能“动画回位”（会突然飞一下）：停住时才按当前视角 Instant 重新取景
    refitAfterStyleSwap(map)
  })
  map.setStyle(mergedStyle(FALLBACK_STYLE), { diff: false })
}

/**
 * 换完底图样式后补一次取景（IKPFVN）。
 *
 * ⚠️ 只在**停住**的时候补（`national` / `station`）。`setStyle` 本身会保留相机，所以
 * 飞行途中（leaving / entering）**根本不需要**补：那里补一次 `syncCamera(false)`
 * 等于把正在跑的镜头按下去、把 `motionPhase` 强置成 `station` 并提前 `emit('arrived')`
 * —— 表现就是"路网在半空显形、页面数据提前放行"（PR !77 独立审查发现的漏口）。
 */
function refitAfterStyleSwap(map: MapLibreMap): void {
  applyViewState(map)
  if (motionPhase.value !== 'national' && motionPhase.value !== 'station') return
  void syncCamera(false)
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
      refitAfterStyleSwap(map)
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

/** 样式尚未就绪时，已挂好"样式就绪后再贴一次"的等待标记（避免重复挂监听） */
let viewStatePending = false

/** 数据/选中/路线/视角变化后，把视图状态贴回图层（换样式之后也要重贴一次） */
function applyViewState(map: MapLibreMap): void {
  // ⚠️ 样式未 `_loaded` 时 `addImage` / `addSource` / `addLayer` 都会抛
  // `Style is not done loading`（未捕获会打断 watcher / 组件更新链，dev-c 实测）。本函数会被
  // `styledata` 回调调到，而那一刻样式可能只加载到一半 —— 此时不贴，等下一次 `styledata`。
  // `setStyle({diff:false})` 的新样式里 source 与 layer 都是**随样式一起下发**的（见
  // `mergedStyle()`），所以换样式这条路不需要在这里重挂 source / 重加 layer。
  if (!map.isStyleLoaded()) {
    if (!viewStatePending) {
      viewStatePending = true
      map.once('styledata', () => {
        viewStatePending = false
        if (!disposed) applyViewState(map)
      })
    }
    return
  }
  // 换样式会清空 image 资源：方向图标与站名标签都要补回去
  addDirectionImages(map)
  addStationImages(map)
  applyDirectionVisibility(map)
  syncStationSelection(map)
  const dirSrc = map.getSource(DIR_SRC) as GeoJSONSource | undefined
  if (dirSrc) void dirSrc.setData(directionGeoJson())
  // 路线行进箭头：换样式后源与图标都可能被清掉，数据和显隐一起重贴
  ensureRouteArrowSource(map)
  const raSrc = map.getSource(ROUTE_ARROW_SRC) as GeoJSONSource | undefined
  if (raSrc) void raSrc.setData(routeArrowGeoJson())
  applyRouteArrowVisibility(map)
  const stSrc = map.getSource(STATION_SRC) as GeoJSONSource | undefined
  if (stSrc) void stSrc.setData(stationGeoJson())
  const src = map.getSource(SRC) as GeoJSONSource | undefined
  if (src) void src.setData(routeGeoJson())
  // 真值路网底衬（2026-10-29）：切站后按新包重贴（Z / GZ 各一份；包没有 roads 时是空集合）
  const roadsSrc = map.getSource(ROADS_SRC) as GeoJSONSource | undefined
  if (roadsSrc) void roadsSrc.setData(roadsGeoJson())
  // 落客区（终点区域）：切站 / 换样式后按当前包重贴；高亮层按选中路线的终点落客点收口
  const dzSrc = map.getSource(DZ_SRC) as GeoJSONSource | undefined
  if (dzSrc) void dzSrc.setData(dropZoneGeoJson())
  if (map.getLayer(LAYER_DZ_HL)) {
    map.setFilter(LAYER_DZ_HL, dropZoneHighlightFilter())
  }
  if (map.getLayer(LAYER_SELECTED)) map.setFilter(LAYER_SELECTED, selectedFilter())
  if (map.getLayer(LAYER_ROUTE_BED)) map.setFilter(LAYER_ROUTE_BED, routeAllFilter())
  if (map.getLayer(LAYER_ROUTE)) map.setFilter(LAYER_ROUTE, routeFilterExcludingPicked(routeFilter()))
  if (map.getLayer(LAYER_ROUTE_HALO)) map.setFilter(LAYER_ROUTE_HALO, routeFilter())
  if (map.getLayer(LAYER_ROUTE_ALT1)) map.setFilter(LAYER_ROUTE_ALT1, routeFilterExcludingPicked(altFilterExclusive(1)))
  if (map.getLayer(LAYER_ROUTE_ALT1_HALO)) map.setFilter(LAYER_ROUTE_ALT1_HALO, altFilterExclusive(1))
  if (map.getLayer(LAYER_ROUTE_ALT2)) map.setFilter(LAYER_ROUTE_ALT2, routeFilterExcludingPicked(altFilterExclusive(2)))
  if (map.getLayer(LAYER_ROUTE_ALT2_HALO)) map.setFilter(LAYER_ROUTE_ALT2_HALO, altFilterExclusive(2))
  if (map.getLayer(LAYER_ROUTE_DEP)) map.setFilter(LAYER_ROUTE_DEP, routeFilterExcludingPicked(routeFilterOf('departure')))
  if (map.getLayer(LAYER_ROUTE_PICK)) map.setFilter(LAYER_ROUTE_PICK, pickedRouteFilter())
  if (map.getLayer(LAYER_ROUTE_PICK_HALO)) map.setFilter(LAYER_ROUTE_PICK_HALO, pickedRouteFilter())
  // 底衬色调按颜色模式重贴：灰底版换成去饱和冷灰底衬（`ROADS_C_*_GRAY`）。
  // spec 里只给了初值，切到 / 切回 gray 档必须重贴，否则底衬还停在上一档的米色。
  if (map.getLayer(LAYER_ROADS_CASING)) {
    map.setPaintProperty(LAYER_ROADS_CASING, 'line-color', roadsColorByClass(roadsEdgeColors()))
  }
  if (map.getLayer(LAYER_ROADS_LINE)) {
    map.setPaintProperty(LAYER_ROADS_LINE, 'line-color', roadsColorByClass(roadsRoadColors()))
  }
  // 三态图层显隐也重贴一次：换样式会把 `visibility` 回到默认的 visible
  applyModeLayers(map)
  // 换样式后 paint 全部回到 `lineLayerSpecs()` 的基准值 —— 必须强制重贴，
  // 否则「底图加载完那一刻线宽突然变粗」（业主会看到路网突然胖一圈）
  applyLineScale(map, true)
  applyCameraPinScale(map, true)
  // ⚠️ 方向标记不再需要「换样式后重贴尺寸」：尺寸是 layout 里的 zoom 插值表达式，
  // 样式一换由 MapLibre 自己按当前 zoom 求值（旧代码在这里 applyDirectionScale 强制重贴）。
  // motionPhase 兜底（修「深链 ?station= / 镜头中断后路网与箭头一支不画」）：
  // `applyModeLayers()` 只认 `motionPhase === 'station'` 才开路网/箭头。正常切站由
  // `syncCamera()` 落态；但深链直进、飞行被取消等场合 motionPhase 停在 'national' /
  // 'leaving'，图层开关就永远关着（缩放也不会回来）。这里按**声明的视角**兜底：
  // 页面说自己在站区（mapMode='station'）且镜头不在飞（停态）→ 视为已到站。
  if (props.mapMode === 'station'
      && (motionPhase.value === 'national' || motionPhase.value === 'leaving')) {
    motionPhase.value = 'station'
    applyModeLayers(map)
  }
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

/**
 * 鼠标下的站点（全国视角的切站入口）。
 * 命中用那个**透明大圆**图层（半径 15 px），而不是可见小圆：可见圆只有 12~18 px 直径，
 * 鼠标要正中才能点中；热区要求 ≥ 24 px。
 */
function stationKeyAt(map: MapLibreMap, point: MapMouseEvent['point']): string | null {
  if (props.mapMode === 'station') return null
  if (!map.getLayer(LAYER_STATION_HIT)) return null
  const hit = map.queryRenderedFeatures(point, { layers: [LAYER_STATION_HIT] })
  const key = hit?.[0]?.properties?.key
  return typeof key === 'string' && key ? key : null
}

function onMapMouseMove(e: MapMouseEvent): void {
  const map = mapRef.value
  if (!map) return
  mouse.value = { x: e.point.x, y: e.point.y }
  // 点图拾取模式（业主 2026-10-28）：十字光标 + **不**随悬停改选中路段，
  // 否则鼠标一路划过，右侧面板的段信息会乱跳，用户点下去还会以为选错了对象。
  if (props.pickMode) {
    map.getCanvas().style.cursor = 'crosshair'
    return
  }
  // 全国视角：只有站点 pin 是可选对象（路网图层已隐藏，路口悬停不该再报路段）
  const stationKey = stationKeyAt(map, e.point)
  syncStationHover(map, stationKey)
  if (props.mapMode !== 'station') {
    map.getCanvas().style.cursor = stationKey ? 'pointer' : ''
    return
  }
  const id = hoveredSegmentId(map, e.point)
  map.getCanvas().style.cursor = id ? 'pointer' : ''
  // 悬停即切换选中（业主 2026-10-14：不要"靠点击才切换"）——浮牌据此吸附在当前路段上
  if (id && id !== props.selectedId) emit('select', id)
}

function onMapMouseOut(): void {
  mouse.value = null
  const map = mapRef.value
  if (map) syncStationHover(map, null)
}

function onMapClick(e: MapMouseEvent): void {
  const map = mapRef.value
  if (!map) return
  // 点图拾取起 / 终点（业主 2026-10-28）：优先级最高——正在选点时用户点的每一处都是「坐标」，
  // 不能顺手切站、也不能顺手改选中路段（那会让右侧面板的段信息跳走，干扰「点哪儿就是哪儿」）。
  if (props.pickMode) {
    emit('pick-point', { lon: e.lngLat.lng, lat: e.lngLat.lat })
    return
  }
  // 全国视角：点 pin = 切站（父级走 `switchStation`，本组件不自己换包）
  const stationKey = stationKeyAt(map, e.point)
  if (stationKey) {
    emit('switch-station', stationKey)
    return
  }
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
  const overview = overviewCamera()
  const map = new MapLibreMap({
    container: containerRef.value,
    // ⚠️ 起手是**本地兜底样式**：路网 / 站点 pin 据此立刻画出来，不等公网（本单的核心）
    style: FALLBACK_STYLE,
    // IKPFVN：起手取景不再是写死的肇庆东（`center:[112.657,23.215] / zoom:14`），
    // 而是**中国范围**（常量在 `shared/mapMotion.ts`）。真正的取景在 `load` 里 `fitBounds`。
    center: overview.center,
    zoom: overview.zoom,
    // 底图那几类请求（样式 / tilejson / 瓦片 / sprite / 字形）统一过一遍地址改写：
    // 探到同源直通就换成本地前缀（绕开系统代理），没探到就原样返回。
    transformRequest: (url) => ({ url: toBasemapUrl(url) }),
    // 不隐藏默认署名控件：OSM/ODbL 要求署名（见文件头「合规」）
  })
  mapRef.value = map
  // 验收钩子（**只在 dev 生效**；生产构建里 `import.meta.env.DEV === false`，这块会被摇掉）：
  // 本单的完成判定里有两条只能读地图实例 —— `map.getZoom()`（全国 3–6 / 站区 ≥14）与
  // `map.querySourceFeatures` 里的路线段号（切 Z 全 `SZ-`、切 GZ 全 `GZ-`）。
  // 它与容器上的 `data-map-mode` / `data-station` / `data-motion-phase` 是同一套验收设施。
  if (import.meta.env.DEV) {
    ;(window as unknown as { __hubflowMap?: MapLibreMap }).__hubflowMap = map
  }
  map.addControl(new NavigationControl({ visualizePitch: true }), 'top-right')
  // 比例尺放右下（左下角留给图例）
  map.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-right')

  map.on('load', () => {
    addOwnLayers(map)
    addCameraPins(map)
    addLandmarkPins(map)
    updateRouteEndpointMarkers(map)
    // 起手取景按**当前视角**：全国（默认）→ 中国范围；深链 `?station=` → 直接站区（无动画）
    motionPhase.value = props.mapMode === 'station' ? 'station' : 'national'
    ready.value = true
    // 落客点/场区开关：样式刚加载完补一次（`addOwnLayers()` 里 ready 还是 false，会被前置条件挡掉）
    applyDropZoneVisibility(map)
    void syncCamera(false)
    // 首帧的容器宽度可能还没定型（左右栏正在收起 / 挂载时布局未稳定）——
    // 尺寸一变就补一次取景，见 `watchContainerSize()`。
    watchContainerSize(map)
    // 车辆要在 ready 之后再同步（`syncVehicles` 以 ready 为前置）
    syncVehicles(map)
    map.on('move', () => {
      camTick.value++
      // 线宽 / 热力透明度 / 图钉按当前档位逐帧贴回
      // （业主 2026-10-20：缩远不能糊成一片）
      applyLineScale(map)
      applyCameraPinScale(map)
      // ⚠️ 方向箭头**不在**这里了（2026-10-29）：位置/朝向/尺寸都与视口无关 —— 尺寸是
      // `icon-size` 的 zoom 插值表达式，MapLibre 自己插值；旧代码在这里贴 icon-size
      // （`setLayoutProperty` 按档桶跳变）并按新档重算双向段侧偏（像素→米），两条都删了。
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
  // 直接从**当前站点包**取几何，不经 `DEMO_NETWORK` 的惰性缓存：
  // 那份缓存用 `initedKey` 自校验，但它与本组件的 `packTick` 是两套时序，切站瞬间可能
  // 仍持有上一站的几何（症状：标题已是广州南站、地图上一条线都没有）。
  // 包本身就是唯一真值源（`index.ts`「答案只能有一个来源」），这里按包现取。
  net.value = segmentsFromPack()
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
  // 方向 / 路网 / 站点 pin 重贴数据与显隐；**取景交给镜头状态机**（IKPFVN C）
  applyViewState(map)
  scheduleCameraSync()
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

/**
 * 路线行进箭头数据（后端 `steps[].geometry`）变化：只换这一个源的 data + 显隐，
 * 不动其他图层（`applyViewState` 太重，路线每变一次会连源数据带 filter 全重贴一遍）。
 * 同样按**内容**监听：父级给的是 computed 产物，引用每次都新。
 */
const routeArrowKey = computed(() =>
  (props.routeSteps ?? [])
    .map((s) => `${s.edge_id ?? s.segment_id ?? ''}:${s.geometry.length}:${s.geometry[0]?.join(',') ?? ''}`)
    .join('|'),
)
watch(routeArrowKey, () => {
  const map = mapRef.value
  if (!map || !ready.value) return
  if (!map.getLayer(LAYER_ROUTE_ARROW)) return
  const src = map.getSource(ROUTE_ARROW_SRC) as GeoJSONSource | undefined
  if (src) void src.setData(routeArrowGeoJson())
  applyRouteArrowVisibility(map)
})

// 选中整条路线（业主 2026-10-29 反转后）：被选中那条画品牌蓝 4.2 px，其余（规划 + 备选）仍是浅蓝 3 px。
// 只换 filter（不动源数据）——`applyViewState` 会顺带重贴一次，这里直连更省一次重算。
watch(
  () => props.pickedRouteKey ?? null,
  () => {
    const map = mapRef.value
    if (!map || !ready.value) return
    if (map.getLayer(LAYER_ROUTE)) map.setFilter(LAYER_ROUTE, routeFilterExcludingPicked(routeFilter()))
    if (map.getLayer(LAYER_ROUTE_ALT1)) map.setFilter(LAYER_ROUTE_ALT1, routeFilterExcludingPicked(altFilterExclusive(1)))
    if (map.getLayer(LAYER_ROUTE_ALT2)) map.setFilter(LAYER_ROUTE_ALT2, routeFilterExcludingPicked(altFilterExclusive(2)))
    if (map.getLayer(LAYER_ROUTE_DEP)) map.setFilter(LAYER_ROUTE_DEP, routeFilterExcludingPicked(routeFilterOf('departure')))
    if (map.getLayer(LAYER_ROUTE_PICK)) map.setFilter(LAYER_ROUTE_PICK, pickedRouteFilter())
    if (map.getLayer(LAYER_ROUTE_PICK_HALO)) map.setFilter(LAYER_ROUTE_PICK_HALO, pickedRouteFilter())
  },
)

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
/**
 * 摄像头图钉显隐开关（业主 2026-10-25）：关 = 整层不画（`.mlmap.cams-off` 的 CSS
 * `display:none`，与全国模式同一套机制），悬停浮牌一并清掉；数据、台账、右栏路段卡不动。
 */
watch(camerasVisible, (on) => {
  if (!on) pin.value = null
})

/**
 * 落客点 / 场区显示开关。
 *
 * 落客点 = 图钉（`.lm-pin.dropoff`，CSS 类控制）+ 35 m 落客区演示圈（地图图层，走 `setLayoutProperty`）；
 * 场区 = 只有图钉（`.lm-pin.zone`）。两层互不影响；关掉只是不画，右栏列表与接口数据不动。
 */
function applyDropZoneVisibility(map: MapLibreMap | null = mapRef.value): void {
  if (!map || !ready.value) return
  const visibility = dropoffsVisible.value ? 'visible' : 'none'
  for (const id of [LAYER_DZ_FILL, LAYER_DZ_HL, LAYER_DZ_LINE]) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', visibility)
  }
}

watch(dropoffsVisible, (on) => {
  if (!on) landmarkPin.value = null
  applyDropZoneVisibility()
})
watch(zonesVisible, (on) => {
  if (!on && landmarkPin.value?.kind === 'zone') landmarkPin.value = null
})

/** 选中路线变化 → 终点落客点的「终点区域」高亮跟着走（换 OD / 换站都经这里） */
watch(
  () => props.routeEnd?.point_id,
  () => {
    const map = mapRef.value
    if (!map || !ready.value || !map.getLayer(LAYER_DZ_HL)) return
    map.setFilter(LAYER_DZ_HL, dropZoneHighlightFilter())
  },
)

/** 顶栏「设置」里的底图开关：开 → 拉底图；关 → 撤掉底图层（路网一行不动） */
watch(basemapEnabled, () => {
  const map = mapRef.value
  if (!map || !ready.value) return
  retryStep = 0
  void applyBasemap(map)
})

/**
 * 底图状态一变（ok / failed / off）就重算图层显隐：兜底轮廓的可见性挂在它上面
 * （`basemap !== 'ok'` 才画轮廓，见 `applyModeLayers()`）。
 */
watch(basemap, () => {
  const map = mapRef.value
  if (!map || !ready.value) return
  applyModeLayers(map)
})

/**
 * 视角切换（IKPFVN E1/E2）：`national` ⇄ `station`。
 *
 * 顺序不能反：**先 `map.resize()` 再 `fitBounds`**。左右栏是滑入 / 收起的，
 * resize 之前量到的是旧宽高，直接取景会偏（图例留白、中栏宽度都按旧值算）。
 */
watch(
  () => props.mapMode,
  () => {
    // 先让左右栏把位置定下来（`resizeFirst`），再动镜头；两者都合并到同一轮，
    // 避免与 `packTick` 同时变化时“取消一次再重开一次”（见 `scheduleCameraSync`）。
    scheduleCameraSync(true)
  },
)

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
  window.clearTimeout(resizeTimer)
  resizeObserver?.disconnect()
  resizeObserver = null
  inflightCtrl?.abort()
  // 镜头动画也要停：组件没了还跑着 `easeTo` 会往一个已销毁的渲染器里写
  const map = mapRef.value
  if (map) cancelMotion(map)
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
  <!-- 地图容器：`data-map-mode` / `data-station` 是验收与自动化用的**机器可读标记**（IKPFVN E3），
       不要拿文案去判断当前视角。 -->
  <div
    class="mlmap"
    :class="{
      'mode-national': mapMode === 'national',
      'cams-off': !camerasVisible,
      'dropoffs-off': !dropoffsVisible,
      'zones-off': !zonesVisible,
    }"
    :data-map-mode="mapMode"
    :data-station="currentStationKey"
    :data-motion-phase="motionPhase"
  >
    <div ref="containerRef" class="mlmap-canvas" />

    <!-- 全国视角浮层（IKPFVN B3）：已接入车站一览，点站名 = 切站（与点 pin 同一条通道） -->
    <div v-if="mapMode === 'national'" class="nation-card">
      <div class="nc-head">已接入车站 {{ stations.length }} 个</div>
      <button
        v-for="station in stations"
        :key="station.key"
        type="button"
        class="nc-item"
        :title="`切换到${station.name}：地图缩远 → 移动到该站 → 放大 → 显示该站路网`"
        @click="pickStation(station.key)"
      >
        <span class="nc-name">{{ station.name }}</span>
        <span class="nc-seg">{{ station.segment_count ?? '—' }} 段</span>
        <span class="nc-demo">演示数据</span>
      </button>
      <div class="nc-note">
        只有已接入的站有演示路网；其余区域不上色、不画路线。点站名或地图上的站点圆点进入站区。
      </div>
      <!-- 兜底轮廓的署名与口径：不写审图号之类没依据的话 -->
      <div v-if="basemap !== 'ok'" class="nc-note">
        轮廓简化，仅作示意，不代表边界主张（Natural Earth 1:110m）。
      </div>
    </div>

    <!-- 底图状态角标：**只占一个小角、不覆盖地图** —— 底图拉不出来（或设置里关掉）时路网照样看。
         旧版是一块 inset:0 的整屏遮罩，会把路网一起盖住。 -->
    <div v-if="basemap !== 'ok'" class="basemap-note" :class="{ 'note-bottom': mapMode === 'national' }">
      <template v-if="basemap === 'off'">底图已关闭（顶栏「设置」里可开）· 只画路网</template>
      <template v-else-if="basemap === 'loading'">底图加载中…</template>
      <template v-else>
        <span v-if="mapMode === 'national'">底图不可用 · 仅显示站点与站区路网</span>
        <span v-else>底图不可用（{{ basemapMsg }}）· 路网照画</span>
        <!-- ⚠️ 按钮**文案不许变**：自动重试时若在「重试 / 重试中…」之间改文案，按钮宽度跟着变，
             CDP 端会一直判它 "element is not stable"（实测点了 30 s 点不上）。
             所以「正在重试…」另起一个 span，按钮只切换 disabled（只改透明度，不改尺寸）。 -->
        <span v-if="basemapRetrying" class="basemap-retrying">正在重试…</span>
        <button type="button" class="basemap-retry" :disabled="basemapRetrying" @click="retryBasemap">
          重试
        </button>
      </template>
    </div>

    <!-- 来源口径水印（自绘视图搬来）——全国视角不写“当前站来源”，那样会让人以为全国都有路网 -->
    <div v-if="mapMode === 'station'" class="watermark">{{ sourceLabel }}</div>

    <!-- 路网 OSM 署名：单独一份，**底图挂了也仍在**（E-11 / E-13） -->
    <div v-if="osmActive" class="attribution">
      <a :href="OSM_COPYRIGHT_URL" target="_blank" rel="noopener">{{ OSM_ATTRIBUTION }}</a>
    </div>

    <!-- 全国视角：悬停站点 pin 的浮牌（两个站近得叠在一起时，这是分辨“我指到的是哪个”的依据） -->
    <div v-if="mapMode === 'national' && hoverStation" class="st-chip" :style="stationChipStyle">
      <b>{{ hoverStation.name }}</b>
      <span class="st-chip-sub">{{ hoverStation.segment_count ?? '—' }} 段 · 演示数据 · 点击进入站区</span>
    </div>

    <!-- 摄像头浮牌（悬停图钉时；与路段浮牌是两套，不混） -->
    <div v-if="pin" class="cam-chip" :style="camChipStyle">
      <b>{{ pin.cid }} {{ pin.camId ?? pin.source }}</b> {{ pin.name }}
      <span class="cam-chip-sub">
        {{ pin.segment_id }} · {{ pin.demo ? '演示布点（camera-plan 演示层）' : '源台账布点' }}：{{
          pin.hasVideo
            ? '有样本视频源（演示，非本站现场）'
            : pin.reuseOf
              ? `演示复用画面 ← ${pin.reuseOf}（非本路视频）`
              : '无视频源（画面留空）'
        }} · 点击进感知层
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

    <!-- 跟随鼠标的信息浮牌：吸附在当前选中路段上，沿线走（站区视角才有路段可选） -->    <div v-if="mapMode === 'station' && mouse && hoverChip" class="hover-chip" :style="chipStyle">
      {{ hoverChip }}
    </div>

    <!-- 图例（自绘视图搬来；flow=流量四档 / index=CI 色阶 / level=四级）。
         Issue IKP3EV：≤1180 单列后地图变成整行宽，整幅图例（600px+ 宽）会盖住路网主体，
         所以窄屏把图例收进可折叠浮层（默认收起，点「图例」展开）。
         业主 2026-10-19 追加（本分支）：**桌面端也能收起** —— 图例压住地图左下角，想看那片车流
         就得先收面板；收起状态落 localStorage（`legendVisible`），刷新后保持。
         抬头的开合状态由 `legendOpen` 一处给出（窄屏看断点 ref、桌面看全局开关）。 -->
    <div v-if="legend && mapMode === 'station'" class="legend-dock" :class="{ open: legendOpen }">
      <button
        type="button"
        class="legend-toggle"
        :aria-expanded="legendOpen"
        title="图例压住路网时可收起，点一下再展开（状态会记住）"
        @click="toggleLegend()"
      >
        图例 ▸
      </button>
      <div class="legend">
      <!-- 收起键（在面板内部右上角）：展开状态下，工具条上的「图例 ▸」是隐藏的，
           真人只能点这个叉键收起 —— 只有吃进面板里才点得到，别挪回工具条。 -->
      <button
        type="button"
        class="lg-close"
        title="收起图例（会记住，刷新后保持收起）"
        aria-label="收起图例"
        @click="toggleLegend()"
      >
        ×
      </button>
      <!-- IKOQEJ · 方向标记图例（IKP5BD：三行与开关状态一致；包无方向字段时明确说明） -->
      <template v-if="!directionsAvailable">
        <div class="lg-title">方向标记</div>
        <div class="lg-row">本包无方向字段（旧 21 段对照包）：不绘制方向标记</div>
        <div class="lg-note">方向字段只在 Z / GZ 站点包提供；旧 21 段包仅用于路网对照，不给每个点画灰「?」。</div>
      </template>
      <template v-else-if="!directionsVisible">
        <div class="lg-title">方向标记（只读 enriched）</div>
        <div class="lg-row">已隐藏方向箭头（地图工具条「箭头」键或顶栏「设置 → 方向标记」可开）</div>
      </template>
      <template v-else>
        <div class="lg-title">方向标记（只读 enriched）</div>
        <div class="lg-row">
          <span class="dir-mark" :style="{ color: '#1D5FD8' }">↑</span>单向 ·
          <span class="dir-mark both" :style="{ color: '#6D28D9' }"><span>↕</span></span>双向（中点一支双头箭头）·
          <span class="dir-mark" :style="{ color: '#8B8B8B' }">?</span>未标定
        </div>
        <div class="lg-note">方向来自 OSM oneway + 只读 enriched（演示标注，不是真实方向数据）；车道 / 对向段 / 贯通性见右栏路段详情。150 m 及以内箭头为醒目尺寸，更远等比缩小；150→200 m 渐隐，200 m 以远不画。</div>
      </template>
      <div class="lg-sep" />
      <!-- ④ 自定义路线档（colorMode='custom'）：全网中性灰 + 只画路线。
           这一档的承诺是「图面上除了路线，没有任何路况信息」——所以没有色阶、没有热力、
           非路线段一律中性浅灰；路线仍是「选中品牌蓝 / 其余浅蓝 / 离站紫」那一套。
           与灰底版的最大差别就写在最上面一行：**本档画路线**。 -->
      <template v-if="isCustomMode">
        <div class="lg-title">自定义路线档（全网中性灰 · 只画路线）</div>
        <div class="lg-row"><span class="lg-line idle-gray" />非路线段：中性浅灰 {{ ROUTE_EMPHASIS_GRAY }} · 2 px · 不按等级 / 流量上色</div>
        <div class="lg-row">本档无色阶、无热力晕染 —— 灰线只表示「这段不是路线」，不表示路况</div>
        <template v-if="hasRoutes">
          <div class="lg-sep" />
          <div class="lg-row"><span class="lg-line recommended" />规划路线 · 未选中（浅蓝 {{ ROUTE_IDLE_COLOR }} · 实线 3 px）</div>
          <div v-if="altRouteCount >= 1" class="lg-row"><span class="lg-line alt1" />备选 1 · 未选中（浅蓝 · 长虚线）</div>
          <div v-if="altRouteCount >= 2" class="lg-row"><span class="lg-line alt2" />备选 2 · 未选中（浅蓝 · 短虚线）</div>
          <div class="lg-row"><span class="lg-line departure" />离站路线（紫 {{ ROUTE_DEPART_COLOR }} · 实线）</div>
          <div v-if="pickedRouteName" class="lg-row">
            <span class="lg-line picked" />已选中：{{ pickedRouteName }}（品牌蓝 {{ ROUTE_PICKED_COLOR }} · 4.2 px 实线，压在其它路线之上）
          </div>
          <div class="lg-row"><span class="lg-line sel-stroke" />当前选中路段（中性深灰 {{ SEGMENT_SELECTED_STROKE }} 虚线 · 不是路线）</div>
          <div v-if="routeStart" class="lg-row">
            <span class="rt-dot start">起</span>{{ routeStart.label }} · {{ routeStart.segment_id }}（{{ routeStart.note || '起点' }}）
          </div>
          <div v-if="routeEnd" class="lg-row">
            <span class="rt-dot end">终</span>{{ routeEnd.label }} · {{ routeEnd.segment_id }}（{{ routeEnd.note || '终点' }}）
          </div>
          <div class="lg-note">备选 {{ altRouteCount }} 条（契约要求 ≥2；不足如实少画，不凑等价路线）</div>
        </template>
        <div class="lg-note">与灰底版的区别：本档**灰底 + 画路线**；灰底版全灰且一条路线都不画</div>
        <div class="lg-row ts">更新 {{ props.ts || '—' }}</div>
      </template>
      <!-- ③ 灰底版（colorMode='gray'）：全部线段一律灰，**不画任何路线**。
           这一档只回答「路网在哪」，不回答「路况如何」，也不回答「路线怎么走」——
           所以连路线都藏掉（`applyModeLayers()` 里整族隐藏），图例必须这么写。 -->
      <template v-else-if="isGrayMode">
        <div class="lg-title">灰底版（全网灰 · 不画路线）</div>
        <div class="lg-row"><span class="lg-line gray-net" />路网：冷灰 {{ GRAY_MODE_LINE }}（按道路分类只留明度差）</div>
        <div class="lg-row">本档不表示路况：无色阶、无热力晕染、不按等级 / 流量上色</div>
        <div class="lg-row">本档不画路线：规划 / 备选 / 离站 / 选中路线一律隐藏（含路线浅色底衬）</div>
        <div class="lg-note">灰 {{ UNAVAILABLE.color }} 属于拥堵版的「有摄像头但数据不可用 / 陈旧」语义，灰底版不挪用，避免两义。</div>
        <div class="lg-note">与自定义路线档的区别：自定义档灰底 + 画路线；本档全灰、一条路线都不画。</div>
        <div class="lg-row ts">更新 {{ props.ts || '—' }}</div>
      </template>
      <template v-else-if="isFlow">
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
          <div class="lg-row"><span class="lg-line recommended" />规划路线 · 未选中（浅蓝 {{ ROUTE_IDLE_COLOR }} · 实线 3 px）</div>
          <div v-if="altRouteCount >= 1" class="lg-row"><span class="lg-line alt1" />备选 1 · 未选中（浅蓝 · 长虚线）</div>
          <div v-if="altRouteCount >= 2" class="lg-row"><span class="lg-line alt2" />备选 2 · 未选中（浅蓝 · 短虚线）</div>
          <div class="lg-row"><span class="lg-line departure" />离站路线（紫 {{ ROUTE_DEPART_COLOR }} · 实线）</div>
          <div v-if="pickedRouteName" class="lg-row">
            <span class="lg-line picked" />已选中：{{ pickedRouteName }}（品牌蓝 {{ ROUTE_PICKED_COLOR }} · 4.2 px 实线，压在其它路线之上）
          </div>
          <div class="lg-row"><span class="lg-line sel-stroke" />当前选中路段（中性深灰 {{ SEGMENT_SELECTED_STROKE }} 虚线 · 不是路线）</div>
          <div v-if="routeStart" class="lg-row">
            <span class="rt-dot start">起</span>{{ routeStart.label }} · {{ routeStart.segment_id }}（{{ routeStart.note || '起点' }}）
          </div>
          <div v-if="routeEnd" class="lg-row">
            <span class="rt-dot end">终</span>{{ routeEnd.label }} · {{ routeEnd.segment_id }}（{{ routeEnd.note || '终点' }}）
          </div>
          <div class="lg-note">备选 {{ altRouteCount }} 条（契约要求 ≥2；不足如实少画，不凑等价路线）</div>
          <div class="lg-note">
            凸显路线：{{ routeEmphasisOn ? '开 — 非路线段中性灰细线，不按等级上色' : '关（本档无效：凸显只在自定义路线档生效）' }}
          </div>
          <div class="lg-note">路线由接口端出（真网产物优先 / 样例回退 / mock 演示骨架），原样描线、不随时间重算</div>
        </template>
        <!-- 图钉语义与上色策略解耦（IKP5DM）；2026-10-25 起图钉画全量 N 段 N 路 -->
        <template v-if="pins.length > 0">
          <div class="lg-sep" />
          <div class="lg-row"><span class="dot cam-dot" />摄像头 {{ pins.length }} 路 · 有样本视频源（演示，非本站现场）</div>
          <div class="lg-row"><span class="dot cam-dot empty" />摄像头 · 演示复用画面（road2 / track1，非本站现场）</div>
          <div class="lg-note">图钉 = 全量 N 段 N 路（源台账 + 演示层，一段最多 1 路）；流量版有 q 即上色；工具条「摄像头」键可整体隐藏（数据不受影响）</div>
        </template>
        <!-- 落客区（终点区域）：station 级面状元素，站区视角常画（选中路线的终点圈高亮） -->
        <template v-if="mapMode === 'station'">
          <div class="lg-sep" />
          <div class="lg-row"><span class="dot" :style="{ background: dzSwatchBg, border: `1.4px solid ${dzColor}` }" />落客区（终点区域 · 演示范围圈）<template v-if="routeEnd?.point_id"> · 亮 = 本条路线终点</template></div>
          <div class="lg-note">以落客点为圆心 35 m 示意划分，非实地划线、非真实围栏；起点 = 外围入口段「起」标注，终点 = 落客点「终」标注</div>
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
          <div class="lg-row"><span class="lg-line recommended" />规划路线 · 未选中（浅蓝 {{ ROUTE_IDLE_COLOR }} · 实线 3 px）</div>
          <div v-if="altRouteCount >= 1" class="lg-row"><span class="lg-line alt1" />备选 1 · 未选中（浅蓝 · 长虚线）</div>
          <div v-if="altRouteCount >= 2" class="lg-row"><span class="lg-line alt2" />备选 2 · 未选中（浅蓝 · 短虚线）</div>
          <div class="lg-row"><span class="lg-line departure" />离站路线（紫 {{ ROUTE_DEPART_COLOR }} · 实线）</div>
          <div v-if="pickedRouteName" class="lg-row">
            <span class="lg-line picked" />已选中：{{ pickedRouteName }}（品牌蓝 {{ ROUTE_PICKED_COLOR }} · 4.2 px 实线，压在其它路线之上）
          </div>
          <div class="lg-row"><span class="lg-line sel-stroke" />当前选中路段（中性深灰 {{ SEGMENT_SELECTED_STROKE }} 虚线 · 不是路线）</div>
          <div v-if="routeStart" class="lg-row">
            <span class="rt-dot start">起</span>{{ routeStart.label }} · {{ routeStart.segment_id }}（{{ routeStart.note || '起点' }}）
          </div>
          <div v-if="routeEnd" class="lg-row">
            <span class="rt-dot end">终</span>{{ routeEnd.label }} · {{ routeEnd.segment_id }}（{{ routeEnd.note || '终点' }}）
          </div>
          <div class="lg-note">备选 {{ altRouteCount }} 条（契约要求 ≥2；不足如实少画，不凑等价路线）</div>
          <div class="lg-note">
            凸显路线：{{ routeEmphasisOn ? '开 — 非路线段中性灰细线，不按等级上色' : '关（本档无效：凸显只在自定义路线档生效）' }}
          </div>
          <div class="lg-note">路线由接口端出（真网产物优先 / 样例回退 / mock 演示骨架），原样描线、不随时间重算</div>
        </template>
        <!-- 图钉 = 全量 N 段 N 路（业主 2026-10-25）；上色策略仍是全段按等级上色，两者分开说 -->
        <template v-if="pins.length > 0">
          <div class="lg-sep" />
          <div class="lg-row"><span class="dot cam-dot" />摄像头 {{ pins.length }} 路 · 有样本视频源（演示，非本站现场）</div>
          <div class="lg-row"><span class="dot cam-dot empty" />摄像头 · 演示复用画面（road2 / track1，非本站现场）</div>
          <div class="lg-note">
            图钉 = 全量 N 段 N 路（业主 2026-10-25：源台账 + 演示层，一段最多 1 路）；
            「演示复用」画面取公开样本视频确定性复用，不是该摄像头自己的视频（真实接入归 IKMHMX）；
            工具条「摄像头」键可整体隐藏（只关图钉层，数据不受影响）。
          </div>
        </template>
        <!-- 落客区（终点区域）：station 级面状元素，站区视角常画（选中路线的终点圈高亮） -->
        <template v-if="mapMode === 'station'">
          <div class="lg-sep" />
          <div class="lg-row"><span class="dot" :style="{ background: dzSwatchBg, border: `1.4px solid ${dzColor}` }" />落客区（终点区域 · 演示范围圈）<template v-if="routeEnd?.point_id"> · 亮 = 本条路线终点</template></div>
          <div class="lg-note">以落客点为圆心 35 m 示意划分，非实地划线、非真实围栏；起点 = 外围入口段「起」标注，终点 = 落客点「终」标注</div>
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

/* 图例收起键（面板内右上角，业主 2026-10-19 追加）：
   点击热区要 ≥ 24 px，否则压在路网上很难点准。

   ⚠️ 必须是 `sticky` 而不是 `absolute`（独立审查 P1）：`.legend` 是
   `max-height: min(72%, 400px) + overflow-y: auto` 的滚动容器，绝对定位子元素会
   跟着内容一起滚走 —— 本组件图例（方向 / 四级 / 路线 / 起终 / 摄像头）实测常超 400 px，
   一滚叉键就出视野；而展开状态下工具条的 `.legend-toggle` 是 `display:none`，
   桌面端就没有第二个收起入口了。`sticky + top:0` 让它钉在可视区上沿。
   `margin-bottom: -20px` 抵消自身高度，避免把第一行往下推（视觉与改造前一致）。 */
.lg-close {
  position: sticky;
  top: 0;
  align-self: flex-end;
  margin-bottom: -20px;
  z-index: 3;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  font-size: 15px;
  line-height: 1;
  color: #757575;
  background: rgba(255, 255, 255, 0.92);
  border: none;
  border-radius: 4px;
  cursor: pointer;
  pointer-events: auto;
}
.lg-close:hover {
  color: #1a1a1a;
  background: #efefef;
}
.lg-close:focus-visible {
  outline: 2px solid v-bind('BRAND');
  outline-offset: 1px;
}

/* 图例浮层容器（Issue IKP3EV）：桌面 display:contents，DOM 包裹层对布局零影响
   （.legend 仍相对 .mlmap 绝对定位）；窄屏媒体查询里才变成真正的折叠浮层。

   业主 2026-10-19 追加（本分支）：**桌面端也要能收起**。图例压在地图左下角、盖住路网，
   想看那一片车流就得先把面板收起来；原先只有 ≤1180 窄屏有收起键，桌面端 `display:none`
   等于没法收。这里把收起键在桌面端也放出来（定位到地图工具条左下方），
   收起状态落 `localStorage`（`legendVisible`），刷新后保持。 */
.legend-dock {
  display: contents;
}
.legend-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  position: absolute;
  left: 12px;
  bottom: 12px;
  z-index: 3;
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
/* 展开时收起键不占位：图例本体还压在左下角（与改造前的观感一致） */
.legend-dock.open .legend-toggle {
  display: none;
}
/* 桌面端收起：图例本体隐掉，收起键留在原位 */
.legend-dock:not(.open) .legend {
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
/* 双向图例：一支双头箭头（与地图上「双向段中点画一支共轴双头箭头」的画法对应） */
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
/* 路线图例：用短线段示意线型（实线 / 虚线 / 颜色档）。
   2026-10-29 配色反转后：**未选中 = 浅蓝 #38BDF8 · 3 px（弱）**，与地图弱档同色同宽。 */
.lg-line {
  width: 22px;
  height: 0;
  margin-right: 7px;
  display: inline-block;
  border-top: 3px solid #38bdf8;
}
/* 备选 1 / 2 的图例线段：同为浅蓝 #38BDF8（与主推荐同色同宽），
   靠虚线节律区分（长虚 12/6 vs 短虚 2.5/4.5）—— 与地图上那两层同源。 */
.lg-line.alt1 {
  height: 3px;
  border-top: 0;
  background: repeating-linear-gradient(90deg, #38bdf8 0 7px, transparent 7px 10px);
}
.lg-line.alt2 {
  height: 3px;
  border-top: 0;
  background: repeating-linear-gradient(90deg, #38bdf8 0 3px, transparent 3px 6px);
}
.lg-line.departure {
  border-top: 3px solid #7b61ff;
}
/* 已选中：**品牌蓝 #0052D9 · 4 px**（比未选中那档粗一档、深一档，对应 LAYER_ROUTE_PICK） */
.lg-line.picked {
  border-top: 4px solid #0052d9;
}
/* 当前选中**路段**的描边：中性深灰虚线（对应 LAYER_SELECTED 的 2.4 px / 4-6 虚线）。
   单列一档，是为了让图例自己把「这条虚线 ≠ 路线」说清楚（业主分不清的正是它）。 */
.lg-line.sel-stroke {
  height: 2px;
  border-top: 0;
  background: repeating-linear-gradient(90deg, #1f2430 0 4px, transparent 4px 8px);
}
/* 自定义路线档的「非路线段」灰线：中性浅灰 2 px（对应 LAYER_LINE 的 emphasis_gray 分支） */
.lg-line.idle-gray {
  border-top: 2px solid #c9cdd4;
}
/* 灰底版的路网线：冷灰 #6E7681，比「数据不可用灰 #8B8B8B」更深一档，两者在图例上必须分得开 */
.lg-line.gray-net {
  border-top: 3px solid #6e7681;
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
   Marker 的 DOM 由 document.createElement 造，不在 scoped 作用域内，故用 :deep()。

   两层结构（业主 2026-10-20 缩远糊成一团的整改）：外层 `.cam-pin-wrap` 是 Marker 定位壳，
   **不带尺寸、不设 transform**（MapLibre 要往它身上写 translate）；内层 `.cam-pin` 才是
   可见圆点，缩放与透明度由 `applyCameraPinScale()` 逐帧写到它身上。 */
/* 外层 `.cam-pin-wrap` 尺寸必须与内层一致（20×20）：Marker 按外层元素实际尺寸算居中偏移
   （`translate(-w/2, -h/2)`），留 0 尺寸会让图钉整体偏出半个身位。
   但它**不带任何可见样式、不设 transform** —— MapLibre 要往它身上写 translate。 */
:deep(.cam-pin-wrap) {
  width: 20px;
  height: 20px;
}
:deep(.cam-pin) {
  position: absolute;
  left: 0;
  top: 0;
  transform-origin: center center;
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

/* ---------- 全国视角（Issue IKPFVN） ---------- */
/* 全国浮层卡片：左上方（右上角是 MapLibre 的缩放控件、右下是署名 + 比例尺）。
   `pointer-events` 只给按钮：卡片背景不吞地图拖拽的鼠标事件。 */
.nation-card {
  position: absolute;
  top: 10px;
  left: 12px;
  z-index: 4;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
  pointer-events: none;
  max-width: min(320px, calc(100% - 24px));
}
.nc-head {
  font-size: 12px;
  font-weight: 600;
  color: var(--td-text-color-primary, #1a1a1a);
}
.nc-item {
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 8px;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  background: #ffffff;
  font: inherit;
  font-size: 12px;
  color: var(--td-text-color-primary, #1a1a1a);
  cursor: pointer;
  text-align: left;
}
.nc-item:hover {
  border-color: v-bind('BRAND');
  background: #eef4ff;
}
.nc-name {
  font-weight: 500;
}
.nc-seg {
  font-size: 11px;
  color: var(--td-text-color-secondary, #666666);
}
.nc-demo {
  margin-left: auto;
  font-size: 10px;
  color: #b45309;
  background: #fef3c7;
  border-radius: 3px;
  padding: 0 4px;
}
.nc-note {
  font-size: 10px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder, #999999);
}

/* 全国视角里把底图状态角标改放**左下**：左上角是站点浮层卡片（`top/left 10~12px`），
   两个都放左上会叠在一起（实测截图里提示被卡片盖住）。全国视角没有图例，左下是空的。 */
.basemap-note.note-bottom {
  top: auto;
  bottom: 12px;
}

/* 全国站点悬停浮牌（宽度与 script 里的 ST_CHIP_W 一致） */
.st-chip {
  position: absolute;
  width: 176px;
  padding: 4px 8px;
  background: #ffffff;
  border: 1.2px solid v-bind('BRAND');
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  font-size: 11px;
  color: v-bind('BRAND');
  display: flex;
  flex-direction: column;
  gap: 1px;
  pointer-events: none;
  z-index: 4;
}
.st-chip-sub {
  font-size: 10px;
  color: var(--td-text-color-secondary, #666666);
}

/* 全国视角里 DOM Marker（摄像头 / 落客点 / 起终点 / 车辆）一律不画：
   它们属于**某一个站**，放到全国尺度上就是一堆坐标不明的点，会把站点 pin 淹掉。
   为什么用 CSS 而不是删 Marker：Marker 是切站时重建的，来回删建比换个 display 贵得多。 */
.mlmap.mode-national :deep(.cam-pin),
.mlmap.mode-national :deep(.lm-pin),
.mlmap.mode-national :deep(.rt-pin),
.mlmap.mode-national :deep(.veh-dot) {
  display: none;
}

/* 摄像头图钉显示开关（业主 2026-10-25）：关 = 整层不画（连外壳一起 display:none，
   悬停/点击也随之失效）；与全国模式同一套 CSS 机制，不删建 Marker。
   只关"图钉层"——台账、右栏路段卡、监控墙的数据与画面不受影响。 */
.mlmap.dropoffs-off :deep(.lm-pin.dropoff),
.mlmap.zones-off :deep(.lm-pin.zone) {
  display: none;
}
.mlmap.cams-off :deep(.cam-pin-wrap) {
  display: none;
}
</style>
