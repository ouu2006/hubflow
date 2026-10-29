// 全国视角 ↔ 站区视角的**镜头运动**（Issue IKPFVN）。
//
// 业主 2026-10-21 原话口径：「切换高铁站要有动作展示：地图缩小 → 移动到对应高铁站 →
// 放大 → 路线显示、信息切换」。
//
// ⚠️ 2026-10-23 业主改口径：「缩放不用这么夸张，不用上升到全国的，缩放到能看见两个站点就可以了，
// 缩放和移动是同步进行的，一边缩放一边移动」。据此把"三段"并成"两段"，且**每一段都是缩放+平移同时做**：
//   · 缩远的上限不再写死 `panZoom = 5.5`（那是省域尺度，两站相隔 67 km 时两个 pin 只差约 30 px，
//     等于先飞一趟全国再飞回来），改为按「我现在在哪 + 目标站站区」的合并包围盒现算（`transitCamera()`）；
//   · "停在低缩放下平移"那一段取消 —— 平移不再独占一段时间，`easeTo`/`fitBounds` 的 center+zoom
//     本来就一起插值；
//   · 站 → 全国的中间段同样取消：目标就是全国，没必要先在 5.5 停一下。
//
// 这里剩下的正事是三件：
//   ① 把时长、中国范围、站区取景、中间视野**收在这一处**，别散在组件里；
//   ② 提供**唯一一条**动画通道：任何时刻只允许一个进行中的运动，新选择先 `map.stop()` 再从当前
//      相机重新开始 —— 不排队、不叠加（连点两个站时，最终必须停在**最后点的那一站**）；
//   ③ 尊重 `prefers-reduced-motion`：那种设置下不做"缩远再放大"这种花活，≤250 ms 直接到站区，
//      但**信息仍然正确**（到站、换站名、换路网这件事一样不少）。
//
// 为什么不用 `setInterval` 逐帧改 center：那会自己造一条"假动画"通道，与 MapLibre 内部的
// 相机状态打架（拖拽、惯性、`fitBounds` 同时跑会互相踩），也没有 `moveend` 可以等人。
// 这里一律用 `easeTo` / `fitBounds` + `once('moveend')`，动画由渲染器自己插值。
//
// ⚠️ 本文件**不做**任何业务判断：站点包 / 数据 / 面板状态都由调用方管，这里只管相机。

import type { Map as MapLibreMap } from 'maplibre-gl'
import { PACKS, STATIONS } from '../station-packs/index'
// 箭头完全不透明的那一档 = 进站取景的缩放下限（见下方 `fitBoxCamera` 的注释）
import { DIR_ZOOM_FULL } from './directionZoom'

/**
 * 两段动作的时长（ms）——**集中在这里调**，不要在调用方再写魔法数字。
 *
 * 业主 2026-10-23 口径改版：「缩放不用这么夸张，不用上升到全国的，缩放到能看见两个站点
 * 就可以了，缩放和移动是同步进行的，一边缩放一边移动」。所以：
 *   · 原来那套「缩远 700 → 停在 5.5 平移 550 → 放大 950」（共 2.2 s）拆掉了 ——
 *     中间那一档 5.5 是"省域/半个中国"的尺度，两站相距 67 km 时两个 pin 只隔约 30 px，
 *     等于为了换站先飞一趟全国，然后又飞回来，观感很夸张；
 *   · 现在只有两段，**每一段都是 center 与 zoom 一起变**（`easeTo` / `fitBounds` 本来就同时插值）：
 *     ① 离开当前站：缩远到「当前所在位置 + 目标站」刚好同框（缩到多少由 `transitCamera()` 现算，
 *        不是写死的常数），同时平移到两站之间；
 *     ② 落进目标站：`fitBounds` 一边放大一边移到站区。
 *
 * 时长不再给"远距离跳变"买单：`zoomInMs` 会按"要跨几档"再补一点（见 `enterMs()`），
 * 全国 → 点站那种一脚跨 10 档的路径不会被 0.85 s 硬拽过去。
 */
export const MOTION = {
  /** ① 缩远 + 平移（同时进行）：退到"两站同框" */
  transitMs: 620,
  /** ② 放大 + 平移（同时进行）：落进站区取景；跨的档数多时 `enterMs()` 会再加时 */
  zoomInMs: 850,
  /** 放大段的额外时长上限（每跨 1 档加 45 ms，最多加这么多） */
  zoomInExtraMaxMs: 500,
  /** 退回全国视角（「← 全国」按钮）：同样是一次 center+zoom 同时变 */
  overviewMs: 1100,
  /** `prefers-reduced-motion: reduce` 下的总时长（必须 ≤250 ms，见文件头第 ③ 条） */
  reducedMs: 200,
  /** 站区取景的最大缩放：太小看不清段，太大底图瓦片会糊 */
  fitMaxZoom: 17.5,
} as const

export interface CameraPadding {
  top: number
  right: number
  bottom: number
  left: number
}

/** 经纬度包围盒（WGS-84；站点包与 OSM 底图同坐标系，不做任何转换） */
export interface Bounds {
  sw: [number, number]
  ne: [number, number]
}

/**
 * 中国范围（全国视角的取景框）。
 *
 * 数值 = `src/assets/geo/china-outline.geojson`（Natural Earth 1:110m 简化轮廓）的实际外包框，
 * 与底图无关：底图拉得到时它是起手视野，拉不到时它正好框住兜底轮廓。
 * ⚠️ 这是**显示用外包框**，不是国土主张范围；页面文案不得据此写任何边界话术。
 */
export const CHINA_BBOX: Bounds = { sw: [73.675, 18.198], ne: [135.026, 53.459] }

/** 全国视角的起手缩放（`fitBounds` 之前的初值；实际取景一律走 `fitBounds`） */
export const CHINA_ZOOM = 3.4

/**
 * 全国视角的**最小**缩放（3 = 「全国视角 zoom 落在 3–6」这条判定的下界）。
 *
 * 为什么需要一个下限：`fitBounds` 是**按容器高度**收敛的 —— 中栏只有 380 px 高时，
 * 把 35 个纬度装进去会算到 2.3 档，中国大陆缩成中间一小块，一点也不像"全国大地图"。
 * 窗口再矮、KPI / 告警条再占几像素，都还会更低。所以宽高装不下时**宁可轻微裁掉南北边**，
 * 也要保住"一眼看出是全国"的体量；装得下时它不生效（`zoom` 本来就 ≥3）。
 */
export const NATIONAL_ZOOM_MIN = 3

/**
 * 全国取景的收尾：低于下限就抬到下限（`duration: 0` = 不是一次新的转场，只是把
 * `fitBounds` 的结果贴到可接受的档位）。站区取景不走这里。
 */
export function clampOverviewZoom(map: MapLibreMap): void {
  const zoom = map.getZoom()
  if (Number.isFinite(zoom) && zoom < NATIONAL_ZOOM_MIN) {
    map.easeTo({ zoom: NATIONAL_ZOOM_MIN, duration: 0 })
  }
}

/**
 * 镜头状态机的四个状态（`national` 与 `station` 是"停住"的两端）。
 *
 * ⚠️ 2026-10-23 起没有 `panning` 了：原来"缩远 → **停在固定档位平移** → 放大"是三个动作，
 * 现在只有两段，且每段都同时改 center 与 zoom（业主口径「缩放和移动是同步进行的」）。
 * 过渡期统一算 `leaving`（离开当前站，缩远+平移）与 `entering`（落进目标站，放大+平移）。
 */
export type MotionPhase = 'national' | 'leaving' | 'entering' | 'station'

export interface MotionResult {
  /** 落点站键；`null` = 落到全国视角 */
  key: string | null
  phase: MotionPhase
  /** `true` = 这次运动被后来的操作打断（调用方**不该**据此提交"已到站"） */
  cancelled: boolean
}

export interface MotionOptions {
  /** 取景留白；传函数时在 `fitBounds` 那一刻求值（容器尺寸可能刚变过） */
  padding: CameraPadding | (() => CameraPadding)
  /** 每进入一个状态回调一次（组件据此切图层可见性） */
  onPhase?: (phase: MotionPhase) => void
  /** 缩远/平移走完、`fitBounds` 之前的一次回调（组件在这里 `map.resize()`） */
  beforeFit?: () => Promise<void> | void
}

// ---------------------------------------------------------------- 是否"减弱动效"

/**
 * 用户是否要求减少动效。
 * 读 `matchMedia` 而不是缓存一次：系统设置在页面开着的时候也能改。
 */
export function motionReduced(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

// ---------------------------------------------------------------- 取景目标

/** 全国视角：中心 + 缩放 + 外包框（起手建图与「← 全国」共用） */
export function overviewCamera(): { center: [number, number]; zoom: number; bounds: Bounds } {
  const center: [number, number] = [
    (CHINA_BBOX.sw[0] + CHINA_BBOX.ne[0]) / 2,
    (CHINA_BBOX.sw[1] + CHINA_BBOX.ne[1]) / 2,
  ]
  return { center, zoom: CHINA_ZOOM, bounds: CHINA_BBOX }
}

/**
 * 一个站的**真实**取景范围 = 该站包 `segments` 折线的经纬度 min/max。
 *
 * 为什么不用站区范围 `range_m` 折算：`range_m` 是"站区有多大"的登记值（Z 500 m / GZ 1000 m），
 * 而路网实际铺开的矩形并不等于那个圆；按包内几何算，`fitBounds` 才真的一屏装下整套路网。
 * 包内几何为空（坏包 / 空站）时返回 `null`，调用方退回全国视角 —— 不猜。
 */
export function stationBounds(key: string): Bounds | null {
  const pack = PACKS[key]
  if (!pack) return null
  let minLon = Number.POSITIVE_INFINITY
  let minLat = Number.POSITIVE_INFINITY
  let maxLon = Number.NEGATIVE_INFINITY
  let maxLat = Number.NEGATIVE_INFINITY
  for (const seg of pack.segments) {
    for (const [lon, lat] of seg.coords) {
      if (lon < minLon) minLon = lon
      if (lon > maxLon) maxLon = lon
      if (lat < minLat) minLat = lat
      if (lat > maxLat) maxLat = lat
    }
  }
  if (!Number.isFinite(minLon) || !Number.isFinite(minLat)) return null
  // 单点 / 零面积的路网：给一个极小的框，免得 fitBounds 把缩放顶到 maxZoom 后画面乱飘
  const padLon = maxLon - minLon > 0 ? 0 : 1e-4
  const padLat = maxLat - minLat > 0 ? 0 : 1e-4
  return {
    sw: [minLon - padLon, minLat - padLat],
    ne: [maxLon + padLon, maxLat + padLat],
  }
}

export interface StationCamera {
  key: string
  bounds: Bounds
  center: [number, number]
  maxZoom: number
}

/** 站区视角：取景框 + 平移落点（低缩放下的目标中心取**站区锚点**，见 `STATIONS`） */
export function stationCamera(key: string): StationCamera | null {
  const bounds = stationBounds(key)
  if (!bounds) return null
  const entry = STATIONS.find((s) => s.key === key)
  const center: [number, number] = entry
    ? [entry.lon, entry.lat]
    : [(bounds.sw[0] + bounds.ne[0]) / 2, (bounds.sw[1] + bounds.ne[1]) / 2]
  return { key, bounds, center, maxZoom: MOTION.fitMaxZoom }
}

// ---------------------------------------------------------------- 取景（唯一实现）

/**
 * 包围盒可用性：四值都是有限数，且 `ne` 严格在 `sw` 的东/北侧。
 *
 * 为什么必须有这道闸（2026-10-29 实测）：1280×720 容器下取景抛
 * `Error: Invalid LngLat (NaN,-90)` —— 侧栏/图例把可用宽度挤到接近 0 时，
 * 留白吃掉了整个可视框，`cameraForBounds` 的中心经纬度退化成 NaN。
 * 宁可「这一档不取景、停在原相机」，也不能让 NaN 泄进渲染器（一抛就是整图黑掉）。
 */
export function isUsableBounds(bounds: Bounds | null | undefined): bounds is Bounds {
  if (!bounds || !bounds.sw || !bounds.ne) return false
  const { sw, ne } = bounds
  if (![sw[0], sw[1], ne[0], ne[1]].every((v) => typeof v === 'number' && Number.isFinite(v))) {
    return false
  }
  return ne[0] > sw[0] && ne[1] > sw[1]
}

/**
 * 留白归一化：每一边不超过容器对应边长的 35%。
 * 留白大于可视区时会算出**负的**取景框（NaN 的直接来源，见 `isUsableBounds` 的注释），这里先夹住。
 */
function normalizePadding(map: MapLibreMap, padding: CameraPadding): CameraPadding {
  const canvas = map.getCanvas()
  const w = canvas.clientWidth || canvas.width || 0
  const h = canvas.clientHeight || canvas.height || 0
  const cap = (v: number, dim: number): number => {
    const n = Number.isFinite(v) ? v : 0
    return Math.max(0, Math.min(n, dim * 0.35))
  }
  return {
    top: cap(padding.top, h),
    right: cap(padding.right, w),
    bottom: cap(padding.bottom, h),
    left: cap(padding.left, w),
  }
}

/** `cameraForBounds` 的结果能不能用（失败时它返回 undefined，退化时会给出 NaN） */
function isUsableCamera(fit: ReturnType<MapLibreMap['cameraForBounds']>): boolean {
  if (!fit) return false
  const center = fit.center as { lng?: number; lat?: number } | undefined
  if (!center) return false
  if (typeof center.lng !== 'number' || typeof center.lat !== 'number') return false
  return Number.isFinite(center.lng) && Number.isFinite(center.lat) && Number.isFinite(fit.zoom as number)
}

/**
 * 取景（**唯一实现**：动画进站、无动画补算、`prefers-reduced-motion`、框住一批段的都走它）。
 *
 * ① 缩放下限 `opts.minZoom`（进站传 `DIR_ZOOM_FULL`）。
 *    实测各视口「进站」实际落点（2026-10-29，dev-C 四档截图）：1440×900 → **13.02**、
 *    375×812 → **13.49**、1920×1080 → 15.76、2560×1440 → 16.73。
 *    方向层在 `DIR_ZOOM_FADE(15) → DIR_ZOOM_FULL(15.5)` 之间淡出，所以**小屏 / 窗口化进站时
 *    箭头全透明、根本看不见**（业主「箭头很乱 / 看不懂」的体感里，有一份就是这个「看不见」）。
 *    给进站取景加下限 = 让四档视口落进同一个 zoom 区间，正是「不因分辨率不同而不同」。
 *    为什么不改成下调淡出阈值：那会让 61 段在全览 zoom 13 处同时变实，比淡出乱得多 ——
 *    淡出是**正确的降级设计**（全览时密密麻麻没有意义），错的只是「默认进站视图落进淡出区」。
 *    副作用（设计如此，不是 bug）：小容器下站内不再一屏全览；要全览得手动缩小，箭头随即淡出。
 * ② 显式把 `zoom` 交给 `fitBounds`：MapLibre 的 `FitBoundsOptions` 会以调用方 options 覆盖它
 *    自己算出的相机（`node_modules/maplibre-gl/src/ui/camera.ts:730` 的 `_fitInternal` 里
 *    `extend(calculatedOptions, options)`），所以 `center` 仍取按留白算好的值、`zoom` 用我们夹过的
 *    值 —— 比只给 `minZoom` 可靠（`minZoom` 在 `flyTo` 里只约束「弧线收敛时的临时缩远」，
 *    见 `geo/projection/mercator_camera_helper.ts:174-178`，不保证终点档位）。
 * ③ 一切无效输入（包围盒 / 留白 / 相机）都**跳过而不抛**，见 `isUsableBounds`。
 */
export function fitBoxCamera(
  map: MapLibreMap,
  bounds: Bounds,
  opts: {
    padding: CameraPadding
    duration: number
    essential?: boolean
    /** 缩放下限（进站传 `DIR_ZOOM_FULL`；全国视角不传） */
    minZoom?: number
    maxZoom?: number
    /** 仅用于日志：这次取景是给谁算的 */
    label?: string
  },
): boolean {
  if (!isUsableBounds(bounds)) {
    console.warn('[mapMotion] 包围盒无效，跳过取景：', opts.label ?? '', bounds)
    return false
  }
  const padding = normalizePadding(map, opts.padding)
  // ⚠️ `maxZoom` **不能显式传 undefined**：MapLibre 的 `_cameraForBoxAndBearing` 用
  // `extend({maxZoom: transform.maxZoom}, options)` 合并，显式的 `undefined` 会覆盖掉默认值，
  // 于是 `Math.min(算出档位, undefined) = NaN` → 抛 `Invalid LngLat object: (NaN, NaN)`。
  // 另一个坑：maplibre 6.x 的 `cameraForBounds` 在退化输入下是**抛异常**而不是返回 undefined，
  // 所以这里必须 try/catch —— 宁可这一档不取景，也不能让异常冒到渲染循环里（一抛就是黑图）。
  const boxOptions: { padding: CameraPadding; maxZoom?: number } = { padding }
  if (typeof opts.maxZoom === 'number' && Number.isFinite(opts.maxZoom)) boxOptions.maxZoom = opts.maxZoom
  let fit: ReturnType<MapLibreMap['cameraForBounds']>
  try {
    fit = map.cameraForBounds([bounds.sw, bounds.ne], boxOptions)
  } catch (err) {
    console.warn('[mapMotion] cameraForBounds 抛错，跳过取景：', opts.label ?? '', err)
    return false
  }
  if (!fit || !isUsableCamera(fit)) {
    console.warn('[mapMotion] cameraForBounds 失败（容器过小 / 留白过大），跳过取景：', opts.label ?? '', padding)
    return false
  }
  const fitted = fit.zoom as number
  const lower = opts.minZoom ?? -Infinity
  const upper = opts.maxZoom ?? Infinity
  const zoom = Math.min(upper, Math.max(fitted, lower))
  const fitBoundsOptions: {
    padding: CameraPadding
    duration: number
    essential: boolean
    zoom: number
    maxZoom?: number
    minZoom?: number
  } = { padding, duration: opts.duration, essential: opts.essential ?? true, zoom }
  if (boxOptions.maxZoom !== undefined) fitBoundsOptions.maxZoom = boxOptions.maxZoom
  if (typeof opts.minZoom === 'number' && Number.isFinite(opts.minZoom)) fitBoundsOptions.minZoom = opts.minZoom
  map.fitBounds([bounds.sw, bounds.ne], fitBoundsOptions)
  return true
}

/** 站区取景：`fitBoxCamera` + 缩放下限 = 箭头完全不透明那一档 */
export function fitStationCamera(
  map: MapLibreMap,
  cam: StationCamera,
  opts: { padding: CameraPadding; duration: number; essential?: boolean },
): boolean {
  return fitBoxCamera(map, cam.bounds, {
    ...opts,
    minZoom: DIR_ZOOM_FULL,
    maxZoom: cam.maxZoom,
    label: `station:${cam.key}`,
  })
}

/** 全国视角取景：同一套有效性闸，但**不加缩放下限**（全国本来就该小，箭头在此淡出是设计） */
export function fitOverviewCamera(
  map: MapLibreMap,
  cam: { bounds: Bounds },
  opts: { padding: CameraPadding; duration: number; essential?: boolean },
): boolean {
  return fitBoxCamera(map, cam.bounds, { ...opts, label: 'overview' })
}

// ---------------------------------------------------------------- 留白

/** 取景留白的通用边距（px）：顶部给工具条呼吸，底部给比例尺 / 注脚 */
export const MOTION_MARGIN_PX = 36

export interface MotionViewport {
  /** 地图容器当前宽高（px；量 `map.getContainer()`，不要猜） */
  width: number
  height: number
  /** 站区模式下左右栏合计宽（px）—— 栏在容器**外面**，这里只用来估"栏刚滑入"的余量 */
  columnsWidth?: number
  /** 图例（左下角浮层）占位宽（px）；窄屏图例收起时传 0 */
  legendWidth?: number
}

/**
 * 站区取景留白。
 *
 * 三块：
 *   ① 图例：宽屏时它在左下角，能压住站区最外侧的起点段（业主 2026-10-21 的"起终点"就在路网边缘），
 *      必须让出来 —— 上限取容器宽的 36%，窄屏时调用方直接传 0（图例已收进折叠浮层）；
 *   ② 左右栏：**栏在容器外**（中栏就是地图容器），不重复扣；但栏是"滑入"的，`resize()` 与
 *      `fitBounds` 之间可能差一帧，用 `columnsWidth` 折 4% 作对称余量兜住这点误差；
 *   ③ 上下：工具条已在地图容器外，这里只留最小的呼吸与底部注脚空间。
 */
export function stationPadding(v: MotionViewport): CameraPadding {
  const settle = Math.round((v.columnsWidth ?? 0) * 0.04)
  const legend = Math.min(v.legendWidth ?? 0, Math.round(v.width * 0.36))
  return {
    top: MOTION_MARGIN_PX + 20 + settle,
    right: MOTION_MARGIN_PX + settle,
    bottom: MOTION_MARGIN_PX + 28 + settle,
    left: Math.max(legend + settle, MOTION_MARGIN_PX + settle),
  }
}

/** 全国取景留白：全国模式左右栏收起，只要一点点对称留白（外加图例收起时的 0） */
export function overviewPadding(v: MotionViewport): CameraPadding {
  const settle = Math.round(Math.min(v.width, v.height) * 0.02)
  const edge = 16 + settle
  return { top: edge, right: edge, bottom: edge + 8, left: edge }
}

/**
 * 切站中间视野的留白：对称、小。
 *
 * 为什么不用 `stationPadding()`（那一份要扣图例宽，左边界最多扣掉 36%）：中间视野只存在半秒，
 * 目的是"让人看见从哪来、到哪去"，也不需要给图例让位 —— 扣图例反而会把两站挤在右半边。
 */
export function transitPadding(): CameraPadding {
  const edge = MOTION_MARGIN_PX + 24
  return { top: edge, right: edge, bottom: edge + 16, left: edge }
}

/**
 * 切站时**缩远只缩到这里**：让「我现在所在的位置」和「目标站的站区」刚好同框。
 *
 * 业主 2026-10-23 口径：「缩放不用这么夸张，不用上升到全国的，缩放到能看见两个站点就可以了」。
 * 所以中间档不再写死（旧值 `panZoom = 5.5` 是省域尺度 —— Z 与 GZ 相距 67 km 时两个 pin
 * 只隔约 30 px，等于先飞一趟全国再飞回来），改成按**当前相机中心 + 目标站站区框**的合并包围盒
 * 现算：`cameraForBounds()` 给出的就是"这两样东西刚好装进容器（扣掉留白）"的那一档。
 *
 * 举例（1920×1080、中栏 1240×530）：全国 → GZ 时当前中心在华中，算出来约 5.6 档；
 * 而 GZ → Z 这种"站到站"算出来约 10.3 档（旧版是 5.5，缩得远远超出"看见两站"的需要）。
 *
 * 返回 `null` = 不需要中间视野：目标站几何取不到，或当前中心已经落在目标站框里（就地起跳）。
 */
export function transitCamera(
  map: MapLibreMap,
  key: string,
  padding: CameraPadding = transitPadding(),
): { center: [number, number]; zoom: number } | null {
  const target = stationCamera(key)
  if (!target) return null
  const here = map.getCenter()
  const sw: [number, number] = [
    Math.min(here.lng, target.bounds.sw[0]),
    Math.min(here.lat, target.bounds.sw[1]),
  ]
  const ne: [number, number] = [
    Math.max(here.lng, target.bounds.ne[0]),
    Math.max(here.lat, target.bounds.ne[1]),
  ]
  // 已经和目标站几乎重合（重复点同一站）：没有再缩远的必要，直接走"落进站区"
  if (Math.max(ne[0] - sw[0], ne[1] - sw[1]) < 1e-6) return null
  const cam = map.cameraForBounds([sw, ne], { padding, maxZoom: MOTION.fitMaxZoom })
  // MapLibre 的返回类型里 `zoom` 是可选的（理论上可能只给 center）：拿不到就不做中间视野
  if (!cam || typeof cam.zoom !== 'number') return null
  return { center: cam.center as [number, number], zoom: cam.zoom }
}

/**
 * 「落进站区」那一段的时长：跨的档数越多给得越长，避免一脚跨 10 档被 0.85 s 硬拽过去。
 * 只对**放大**加时（缩小的观感本身不刺眼），且封顶 `zoomInExtraMaxMs`。
 */
export function enterMs(fromZoom: number, toZoom: number): number {
  const levels = Math.max(0, toZoom - fromZoom)
  const extra = Math.min(MOTION.zoomInExtraMaxMs, Math.round(levels * 45))
  return MOTION.zoomInMs + extra
}

// ---------------------------------------------------------------- 动画通道（只允许一条）

/**
 * 运动代次。每发起一次运动 +1；任何一步在 await 之后都对一下代次，对不上就**立刻收手**。
 *
 * 这就是"只允许一个动画在跑"的实现方式：不排队、不叠加 —— 新运动先把 `map.stop()` 打断旧的，
 * 再把代次 +1；旧的那条链醒来发现代次变了，直接返回 `cancelled`，一个像素都不再改。
 */
let runSeq = 0

/** 打断当前运动（组件切模式 / 卸载 / 新一轮选择前调用） */
export function cancelMotion(map: MapLibreMap): void {
  runSeq += 1
  map.stop()
}

function resolvePadding(padding: CameraPadding | (() => CameraPadding)): CameraPadding {
  return typeof padding === 'function' ? padding() : padding
}

/**
 * 等一次相机移动结束。
 *
 * 返回 `false` = 这次运动已经被打断（代次变了），调用方应停止后续步骤。
 * 兜底超时取 `预算 + 120 ms`：`easeTo` 到"已经在这个位置"时 MapLibre 可能一个 `moveend`
 * 都不发，没有兜底就会永远挂住（切站流程会卡在"过渡中"）。
 */
function waitMoveEnd(map: MapLibreMap, budgetMs: number, run: number): Promise<boolean> {
  return new Promise<boolean>((resolve) => {
    let settled = false
    const finish = (ok: boolean): void => {
      if (settled) return
      settled = true
      map.off('moveend', onEnd)
      window.clearTimeout(timer)
      resolve(ok)
    }
    const onEnd = (): void => finish(run === runSeq)
    map.once('moveend', onEnd)
    const timer = window.setTimeout(() => finish(run === runSeq), budgetMs + 120)
  })
}

const cancelled = (key: string | null, phase: MotionPhase): MotionResult => ({
  key,
  phase,
  cancelled: true,
})

/**
 * 飞到某个站：**两段，每段都是"缩放 + 平移"同时进行**。
 *
 * 业主 2026-10-23 口径：「缩放不用这么夸张，不用上升到全国的，缩放到能看见两个站点就可以了，
 * 缩放和移动是同步进行的，一边缩放一边移动」。对应两处改动：
 *   ① 缩远的上限不再写死 5.5，而是"当前所在位置 + 目标站"刚好同框（`transitCamera()` 现算）；
 *   ② 原来"停在低缩放下平移"那一段取消 —— 平移与缩放合到同一段里，靠 `easeTo`（center+zoom
 *      一起插值）和 `fitBounds`（本身就是 center+zoom）实现，不再有"定着不动只平移"的画面。
 *
 * 打断语义：任何时刻点另一站，从**当前相机**重新开始（`map.stop()` 保留当下的 center/zoom），
 * 最终状态一定等于最后点击的那一站。
 *
 * `prefers-reduced-motion: reduce`：只做最后一步 `fitBounds`（≤250 ms），不缩远不平移；
 * 到站这件事、换站名换路网这件事照旧发生（信息正确性不因动效偏好而打折）。
 */
export async function flyToStation(
  map: MapLibreMap,
  key: string,
  opts: MotionOptions,
): Promise<MotionResult> {
  const cam = stationCamera(key)
  // 包里没有这个站 / 站包几何为空：不猜落点，就地返回（调用方退回全国视角）
  if (!cam) return { key, phase: 'station', cancelled: false }
  const run = ++runSeq
  map.stop()

  if (motionReduced()) {
    opts.onPhase?.('entering')
    await opts.beforeFit?.()
    if (run !== runSeq) return cancelled(key, 'entering')
    const fitted = fitStationCamera(map, cam, {
      padding: resolvePadding(opts.padding),
      duration: MOTION.reducedMs,
    })
    if (fitted) await waitMoveEnd(map, MOTION.reducedMs, run)
    return run === runSeq ? { key, phase: 'station', cancelled: false } : cancelled(key, 'station')
  }

  // ① 离开当前站：缩远 **与** 平移一起做，且只缩到"两站同框"。
  //    `transitCamera()` 返回 null = 没必要缩（已经在目标站框里 / 取不到站区几何）——
  //    此时也不做"平移"，直接进 ②：`fitBounds` 同样是一边缩放一边移动。
  const transit = transitCamera(map, key)
  if (transit && map.getZoom() > transit.zoom + 0.2) {
    opts.onPhase?.('leaving')
    map.easeTo({
      center: transit.center,
      zoom: transit.zoom,
      duration: MOTION.transitMs,
      essential: true,
    })
    if (!(await waitMoveEnd(map, MOTION.transitMs, run))) return cancelled(key, 'leaving')
  }

  // ② 落进站区：`beforeFit` 里组件先 `map.resize()` —— 左右栏刚滑入，resize 之前量到的宽高是旧的，
  //    直接 fitBounds 会取偏。`fitBounds` 本身就是 center+zoom 同时变，不需要再拆成两步。
  const padding = resolvePadding(opts.padding)
  const target = map.cameraForBounds([cam.bounds.sw, cam.bounds.ne], {
    padding,
    maxZoom: cam.maxZoom,
  })
  const duration = enterMs(map.getZoom(), target?.zoom ?? map.getZoom())
  opts.onPhase?.('entering')
  await opts.beforeFit?.()
  if (run !== runSeq) return cancelled(key, 'entering')
  const fitted = fitStationCamera(map, cam, { padding, duration })
  if (fitted && !(await waitMoveEnd(map, duration, run))) return cancelled(key, 'entering')
  return { key, phase: 'station', cancelled: false }
}

/**
 * 退回全国视角（「← 全国」按钮 / 首次进站后返回）。
 *
 * 一次运动：`fitBounds` 到中国范围，center 与 zoom 同时插值。
 * 2026-10-23 起去掉了"先缩远到 5.5 停一下"的中间段 —— 那一段既不多看到什么，
 * 又让整趟从 1.6 s 变成 2 段；业主口径是「缩放和移动同步进行」，这里直接一趟走完。
 * 与 `flyToStation` 共用同一个代次，所以"飞到一半点全国"同样是"打断 + 从当前相机重开"。
 */
export async function flyToOverview(map: MapLibreMap, opts: MotionOptions): Promise<MotionResult> {
  const run = ++runSeq
  map.stop()
  const cam = overviewCamera()

  if (motionReduced()) {
    opts.onPhase?.('entering')
    await opts.beforeFit?.()
    if (run !== runSeq) return cancelled(null, 'entering')
    const fitted = fitOverviewCamera(map, cam, {
      padding: resolvePadding(opts.padding),
      duration: MOTION.reducedMs,
    })
    if (fitted) await waitMoveEnd(map, MOTION.reducedMs, run)
    if (run !== runSeq) return cancelled(null, 'national')
    clampOverviewZoom(map)
    return { key: null, phase: 'national', cancelled: false }
  }

  opts.onPhase?.('entering')
  await opts.beforeFit?.()
  if (run !== runSeq) return cancelled(null, 'entering')
  const fitted = fitOverviewCamera(map, cam, {
    padding: resolvePadding(opts.padding),
    duration: MOTION.overviewMs,
  })
  if (fitted && !(await waitMoveEnd(map, MOTION.overviewMs, run))) return cancelled(null, 'entering')
  clampOverviewZoom(map)
  return { key: null, phase: 'national', cancelled: false }
}
