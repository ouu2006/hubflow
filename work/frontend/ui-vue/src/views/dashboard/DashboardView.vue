<script setup lang="ts">
// 页面结构(见 `work/frontend/README.md` 第十三节;2026-10-13 三页收敛 Issue #77):
//   顶栏(壳层) → KPI 条(4 格)
//   → 三栏(左:**选择监控**(视图切换 + 监控范围 + 等级分布 + 路段列表)
//           中:**全路段状态**(路网图,四级 / 拥挤指数两视图)
//           右:**路段信息**(详情 / 双源并排 / 因素 / CI 与四项加权 / CI 走势 / 关联告警 / 预测 / 下发))
//   → 底部**热力带**(档位分布 | 路段×时间热力矩阵 | CI 色阶与口径)+ 告警条 → 页脚口径条。
//
// 为什么热力页并进来:业主 2026-10-13 裁定 Web 只保留三层(感知 / 决策 / 大屏),`/heat` 不再是独立页。
// 并入方式是**保信息不保页**:原 `/heat` 的 8 个 widget 各有落点(见 README 第十三节落点对照表),
// 视图切换与 CI 口径(只展示、不判级)原样保留,页脚 / 图例 / 列表三处标注一句不删。
//
// 数据:全部走只读快照接口(src/api/traffic.ts),不做任何业务计算。
// 口径铁律:
//   ① 一期全部 is_simulated=true 示例数据,页面不出现「实时 / 实测 / 现场」表述;
//   ② 三重编码(颜色 + 竖条图标 + 文字)由 LevelBadge 保证;
//   ③ 数据不可用(缺字段或 data_age_s > 120s)恒为灰 + 「不可用」文字分支(TC-11),绝不显示成蓝/绿;
//   ④ 品牌蓝只用于「当前 / 已选 / 可操作」(选中行、选中路段、主按钮、当前页签),等级色只表示路况等级;
//   ⑤ CI 只用于热力展示与辅助排序,**不得作为判级依据**(手册 §6.5 第 1 条),冲突以四级为准;
//   ⑥ 不做 3D、不做无断面间标注的内插;所有数字带单位或口径标注,空值一律「—」,不编造。
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getTrafficAlerts,
  getTrafficCiHistory,
  getTrafficFactors,
  getTrafficHeatMatrix,
  getTrafficMeta,
  getTrafficOverview,
  getTrafficRouteOptions,
  getTrafficSegmentSources,
  getTrafficSegments,
  getTrafficThresholds,
  getTrafficVehicles,
  postRouteRecommend,
  postTrafficLocate,
  subscribeTrafficSnapshot,
} from '../../api/traffic'
import type { LocateResult } from '../../api/traffic'
import { demoSegment, networkGeometryNote, networkSourceLabel, pointAtOffset, segmentLengthM } from '../../shared/demoNetwork'
import {
  basemapEnabled,
  camerasVisible,
  directionsVisible,
  routeEmphasisEnabled,
  setCamerasVisible,
  setDirectionsVisible,
  setRouteEmphasisEnabled,
} from '../../shared/settings'
import { landmarksNearSegment } from '../../shared/landmarks'
import { USE_MOCK } from '../../shared/env'
import { cameraCountOf } from '../../shared/cameras'
// IKOQEJ：方向 / 车道 / 对向 / 贯通（只读 enriched 生成字段；缺值→未标定，不编）
import {
  continuityOf,
  directionKindOf,
  directionLabel,
  directionOf,
  directionSourceLabel,
  lanesOf,
  oppositeOf,
} from '../../shared/directions'
import { activePack, activePackKey, onPackChange, packItems, packNote, packVersion } from '../../station-packs/index'
import { bindStationSwitch, switchStation } from '../../shared/stationSwitch'
import { schedulePrewarm, writeStationCache, type StationSnapshotCache } from '../../shared/stationCache'
import type { SourceMode } from '../../shared/nav'
import { TD } from '../../shared/theme'
import {
  alertLevelOf,
  ciAvailable,
  CI_BAND_NOTE,
  CI_BANDS,
  CI_DISCLAIMER,
  formatClock,
  formatStamp,
  isStale,
  LEVELS,
  levelStyle,
  UNAVAILABLE,
  type CiHistory,
  type CongestionLevel,
  type CongestionViewMode,
  type EmergencyState,
  type FactorApplied,
  type HeatMatrix,
  type RecommendResult,
  type RouteHighlight,
  type RouteEndpointMarker,
  type RouteOption,
  type RouteOptionsSnapshot,
  type SegmentRecord,
  type SegmentSourcePair,
  type ThresholdSnapshot,
  type TrafficAlert,
  type TrafficMeta,
  type TrafficOverview,
  type VehicleRecord,
} from '../../shared/traffic'
import {
  COLOR_MODE_QUERY_KEY,
  COLOR_MODE_STORAGE_KEY,
  FLOW_BANDS,
  FLOW_COLOR_NOTE,
  FLOW_MODE_LABEL,
  FLOW_MODE_NOTE,
  FLOW_UNAVAILABLE_LABEL,
  flowBandOf,
  flowRangeLabel,
  parseColorMode,
  storeColorMode,
  type ColorMode,
  type FlowBand,
} from '../../shared/flow'
import AppShell from '../../components/AppShell.vue'
import LevelBadge from './components/LevelBadge.vue'
import MapLibreViewer from './components/MapLibreViewer.vue'
import AlertList from './components/AlertList.vue'
import BandDistribution from './components/BandDistribution.vue'
import CiScale from './components/CiScale.vue'
import CiTrendBars from './components/CiTrendBars.vue'
import FactorBreakdown from './components/FactorBreakdown.vue'
import HeatMatrixTable from './components/HeatMatrixTable.vue'
import SegmentRankTable from './components/SegmentRankTable.vue'
import SegmentCameraCard from './components/SegmentCameraCard.vue'
import SegmentDecisionSummary from './components/SegmentDecisionSummary.vue'
import SegmentDispatchCard from './components/SegmentDispatchCard.vue'

const router = useRouter()
const route = useRoute()

// ---------- 深链选中（Issue IKMS18）：#/dashboard?segment=SZ-010 ----------
// 语义：站点包存在的段即可选中（地图上任一段都可点）；快照没覆盖的段由详情卡按「无数据」降级。
// 用于从别的页面 / 外链直接定位某段看摄像头与下令，不改变默认选中逻辑。
const deepSegment = computed<string>(() => {
  const raw = route.query.segment
  return typeof raw === 'string' ? raw : Array.isArray(raw) ? (raw[0] ?? '') : ''
})
let deepApplied = false
/** 段号是否可选：站点包几何里有，或当前快照里有（快照段号不一定在包里，允许深链选中） */
function isSelectableSegment(id: string): boolean {
  if (!id) return false
  return Boolean(demoSegment(id)) || segments.value.some((item) => item.segment_id === id)
}
function applyDeepSegment(): void {
  const id = deepSegment.value
  if (!id || deepApplied) return
  deepApplied = true
  if (isSelectableSegment(id)) selectedId.value = id
}
watch(deepSegment, (id) => {
  if (id && isSelectableSegment(id)) {
    deepApplied = true
    selectedId.value = id
  }
})

// ---------- 三栏可拖拽(Issue #81,业主 2026-10-13 口径:「宽度谁定」交给用户) ----------
//
// 组件选型:**不加任何新依赖**,用现有 element-plus 自带的 `ElSplitter` / `ElSplitterPanel`
// (element-plus@2.14.5 已装,`main.ts` 已全局注册)。用别的做法(自己写拖拽 / 换组件库)
// 须按 `docs/开发规范.md` 文首总原则在 PR 的「实现方式」栏申报。
//
// 默认宽度**不许改**:设计稿按 1440×900 对齐,左 296 / 中 弹性 / 右 396(口径红线第 3 条)。
// 最小宽度建议值(Issue #81 第 2 条,数值写进注释):左 220 / 中 320 / 右 280。
// 拖到最小宽度时内容不叠压、不溢出、按钮仍点得到。
//
// ⚠️ 三个易踩点(实现时逐一处理,勿删本注释):
//   ① `.el-splitter-panel` 自带 `overflow: auto`(element-plus theme-chalk 实测),
//      而滚动容器是内部 `.td-col`(含 `.td-scroll`)。**panel 不滚、内部 .td-col 照旧滚**,
//      否则出双层滚动条或「滚不动」——见本文件 <style> 内 `.el-splitter.td-splitter > .el-splitter-panel` 覆盖规则。
//   ② `.el-splitter-bar` 宽度是 0(只有 16px 的 dragger 绝对定位覆盖),
//      且 `.td-body { gap: 10px }` 换成 splitter 后不再生效 → 需给 bar 一个宽度维持栏间距。
//   ③ 中栏地图(一个 MapLibre 画布,矢量的平移/缩放由 MapLibre 自己跟踪容器尺寸),
//      栏宽变化不会坏,但**改完要亲手拖一次地图栏**,确认路网仍铺满、不跑偏。
//
// ⚠️ 第四个易踩点(实测 CDP 拖拽才暴露,静态检查看不出来):
//   `ElSplitterPanel` 内部拖完后改的是**它自己的** panel.size,并 emit `update:size`;
//   `:size="colLeft"` 是**单向**绑定,不会回写 colLeft → colLeft 永远停在 296,
//   `@resize-end="saveColMem"` 存进去的永远是默认值(刷新后宽度归零,功能形同虚设)。
//   正确做法:① `:size` 改成 `v-model:size`(双向,colLeft/colRight 跟着拖拽实时变);
//            ② resize-end 回调的第二个形参就是 pxSizes 全量数组,用它在松手那一刻落盘。
//
// ⚠️ 第五个易踩点:element-plus 的激活态类名是 `.el-splitter-bar__dragger-active`,
//   **不是** `.is-active`(写错时鼠标一移开、还按着不放,就露出默认蓝 #409EFF)。
//
// 已知限制如实记:**ElSplitter 只有鼠标 / 触摸拖拽,没有键盘操作**
// (实测 split-bar 只有 mousedown / touchstart,无 tabindex / keydown / role)。
// 本单不补键盘可达,也不得对外称「无障碍已达标」。
const COL_DEFAULT_LEFT = 296
const COL_DEFAULT_RIGHT = 396
const COL_MIN_LEFT = 220
const COL_MIN_MID = 320
const COL_MIN_RIGHT = 280
/** 记忆用户拖过的宽度(可选加分项 #5);键名带页面前缀,不与别的页串味 */
const COL_MEM_KEY = 'hubflow.dashboard.colWidth'

/** 左栏 / 右栏宽度(px)。中栏弹性,不给 size —— 交给 ElSplitter 自动伸缩(第 1 条判定) */
const colLeft = ref<number | string>(COL_DEFAULT_LEFT)
const colRight = ref<number | string>(COL_DEFAULT_RIGHT)

/* ---------- 左右栏收起 / 展开（业主 2026-10-28） ----------
 * 诉求原话：「我这个样子中间的图都被挤到特别小，能不能改成那种可以拉式放大的方式」。
 * 做法：栏顶给「收起」键、地图工具条给「展开」键；收起时把 ElSplitterPanel 的 size
 * 置 0，中栏是弹性栏，会自动吃掉腾出来的宽度（不需要手动算 px，也不碰 ElSplitter 的拖拽）。
 *
 * ⚠️ 三个约束（改这块前必读）:
 *   ① `:min="COL_MIN_LEFT"` 会把 size 钳在 220 —— 光把 colLeft 设 0 拖不动。
 *      所以收起态必须**同时撤掉 :min**（见模板里 `:min="colLeftCollapsed ? 0 : COL_MIN_LEFT"`）。
 *   ② 收起前的宽度要单独记住（COL_RECALL_LEFT/RIGHT），否则展开只能回默认值，
 *      把用户自己拖过的宽度丢掉。
 *   ③ 记忆 key 与 `COL_MEM_KEY` 分开存：收起态是「布局偏好」，不是「栏宽」，
 *      两者混一个 JSON 会让老版本读回来的 left:0 变成 220 的怪宽度。
 * 与全国视角 `is-national` 的关系：那条是 CSS 强压 0（地图铺满），本功能是用户主动收起。
 * 两者互不干扰 —— 全国视角下左右栏内容本来就 v-if 掉了，收起键也就不可见。
 */
const COL_FOLD_KEY = 'hubflow.dashboard.colCollapsed'
const COL_RECALL_LEFT = ref<number>(COL_DEFAULT_LEFT)
const COL_RECALL_RIGHT = ref<number>(COL_DEFAULT_RIGHT)
const colLeftCollapsed = ref(false)
const colRightCollapsed = ref(false)

/** 记住当前栏宽（收起要先把宽度存起来，展开才有得回） */
function rememberWidth(side: 'left' | 'right'): void {
  const cur = side === 'left' ? colLeft.value : colRight.value
  const n = Number(cur)
  if (!Number.isFinite(n) || n <= 0) return
  if (side === 'left') COL_RECALL_LEFT.value = n
  else COL_RECALL_RIGHT.value = n
}

/**
 * 收起 / 展开一栏。
 * 收起时先记宽度再置 0；展开时回记住的宽度（保证至少到 min，避免被钳成非法值）。
 */
function setColCollapsed(side: 'left' | 'right', collapsed: boolean): void {
  const isLeft = side === 'left'
  const flag = isLeft ? colLeftCollapsed : colRightCollapsed
  if (flag.value === collapsed) return
  if (collapsed) {
    rememberWidth(side)
    flag.value = true
    if (isLeft) colLeft.value = 0
    else colRight.value = 0
  } else {
    flag.value = false
    const back = Math.max(isLeft ? COL_RECALL_LEFT.value : COL_RECALL_RIGHT.value, isLeft ? COL_MIN_LEFT : COL_MIN_RIGHT)
    if (isLeft) colLeft.value = back
    else colRight.value = back
  }
  saveColFoldMem()
}

function loadColFoldMem(): void {
  try {
    const raw = localStorage.getItem(COL_FOLD_KEY)
    if (!raw) return
    const v = JSON.parse(raw) as { left?: unknown; right?: unknown }
    if (v.left === true) setColCollapsed('left', true)
    if (v.right === true) setColCollapsed('right', true)
  } catch {
    /* localStorage 不可用 / 内容坏了:静默退回「都展开」，不影响可用性 */
  }
}

function saveColFoldMem(): void {
  try {
    localStorage.setItem(
      COL_FOLD_KEY,
      JSON.stringify({ left: colLeftCollapsed.value, right: colRightCollapsed.value }),
    )
  } catch {
    /* 隐私模式等场景写不进去:不影响收起本身，只是不记忆 */
  }
}

/** 拖完写一次记忆。切页 / 刷新时读回来;读不到或读坏了就用默认值,不影响可用性 */
function loadColMem(): void {
  try {
    const raw = localStorage.getItem(COL_MEM_KEY)
    if (!raw) return
    const v = JSON.parse(raw) as { left?: unknown; right?: unknown }
    if (typeof v.left === 'number' && Number.isFinite(v.left)) colLeft.value = v.left
    if (typeof v.right === 'number' && Number.isFinite(v.right)) colRight.value = v.right
  } catch {
    /* localStorage 不可用 / 内容坏了:静默退回默认值,不算错 */
  }
}

/**
 * 拖完写一次记忆。切页 / 刷新时读回来;读不到或读坏了就用默认值,不影响可用性。
 * `ElSplitter` 的 `resize-end` 形参是 `(index, pxSizes)`,第二个是全量 px 宽度数组,
 * 但**不要**拿它算要记的值:左/右两栏已由 `v-model:size` 同步到 colLeft/colRight,
 * 直接记这两个即可(中栏是弹性栏,宽度由两侧和视口决定,记了下次打开也对不上)。
 */
function saveColMem(): void {
  try {
    localStorage.setItem(COL_MEM_KEY, JSON.stringify({ left: colLeft.value, right: colRight.value }))
  } catch {
    /* 隐私模式等场景写不进去:不影响拖拽本身,只是不记忆 */
  }
}

/* ---------- 上下拉：三栏区 ↔ 底部热力带（业主 2026-10-28「上下可以那样拉吗」） ----------
 * 之前只有左右能拖，底部热力带是 `flex: 0 0 auto` 固定高度、不给拖。
 * 做法：在 `.td-body` 与 `.heat-band` 之间插一条 10px 横向拖条（`.band-drag`），
 * 拖它改的是热力带的高度 `.heat-band` 的 `--band-h`：
 *   往上拖 → 热力带变矮、三栏（含地图）变高；往下拖 → 热力带变高。
 *
 * ⚠️ 约束（改这块前必读）:
 *   ① 热力带高度用 CSS 变量 `--band-h` 传给 `.heat-band`（`height: var(--band-h)`），
 *      不把高度写成行内 style —— 否则窄屏断点里 `.heat-band` 的 flex 覆盖会打架。
 *   ② 用 pointer 事件 + `setPointerCapture`，不是 mousedown：拖出拖条范围仍能继续拖，
 *      松手一定收到 pointerup（mouse 事件离开窗口会收不到，拖条会卡在"粘手"状态）。
 *   ③ 拖动期间给 body 加 `is-vdrag` 禁选中，否则拖动会顺手把页面文字刷蓝。
 *   ④ 收起 / 展开走 `setBandCollapsed()`；展开回记住的高度，与左右栏的 COL_RECALL_* 同套路。
 */
const BAND_MEM_KEY = 'hubflow.dashboard.bandHeight'
const BAND_DEFAULT_H = 196
const BAND_MIN_H = 96
const BAND_MAX_H = 460
/** 记住的高度（展开时要回这个值，而不是默认值） */
const BAND_RECALL_H = ref<number>(BAND_DEFAULT_H)
const bandHeight = ref<number>(BAND_DEFAULT_H)

function clampBand(h: number): number {
  const n = Math.round(h)
  return Math.min(BAND_MAX_H, Math.max(BAND_MIN_H, n))
}

function saveBandMem(): void {
  try {
    localStorage.setItem(BAND_MEM_KEY, String(bandHeight.value))
  } catch {
    /* 隐私模式写不进去：不记忆，不影响拖动 */
  }
}

function loadBandMem(): void {
  try {
    const raw = localStorage.getItem(BAND_MEM_KEY)
    if (raw === null) return
    const n = Number(raw)
    if (Number.isFinite(n) && n > 0) {
      bandHeight.value = clampBand(n)
      BAND_RECALL_H.value = bandHeight.value
    }
  } catch {
    /* localStorage 不可用 / 内容坏了：静默退回默认高度 */
  }
}

/** 热力带收到最小高度（相当于"收起到只剩标题"） */
function collapseBand(): void {
  if (bandHeight.value > BAND_MIN_H) BAND_RECALL_H.value = bandHeight.value
  bandHeight.value = BAND_MIN_H
  saveBandMem()
}

/** 展开回到收起前的高度 */
function expandBand(): void {
  bandHeight.value = clampBand(BAND_RECALL_H.value)
  saveBandMem()
}

function resetBand(): void {
  bandHeight.value = BAND_DEFAULT_H
  BAND_RECALL_H.value = BAND_DEFAULT_H
  saveBandMem()
}

/**
 * 拖条上的 pointerdown：记录起点，之后 move 按位移改高度。
 * 拖条在热力带**上方**，所以鼠标上移（clientY 变小）= 热力带变高；
 * 反过来 `startH - dy` 才是正确方向（写成 `startH + dy` 会上下颠倒，踩过）。
 */
let bandDrag: { startY: number; startH: number } | null = null

function onBandDragDown(e: PointerEvent): void {
  if (e.button !== 0) return
  bandDrag = { startY: e.clientY, startH: bandHeight.value }
  BAND_RECALL_H.value = bandHeight.value
  ;(e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId)
  document.body.classList.add('is-vdrag')
  e.preventDefault()
}

function onBandDragMove(e: PointerEvent): void {
  if (!bandDrag) return
  bandHeight.value = clampBand(bandDrag.startH - (e.clientY - bandDrag.startY))
}

function onBandDragUp(e: PointerEvent): void {
  if (!bandDrag) return
  bandDrag = null
  ;(e.currentTarget as HTMLElement).releasePointerCapture?.(e.pointerId)
  document.body.classList.remove('is-vdrag')
  saveBandMem()
}

/** 拖条上双击 = 热力带回默认高度（与左右栏双击分隔条复位的习惯一致） */
function onBandDblClick(): void {
  resetBand()
}

/** 热力带当前是否已收到底（拖条上的箭头按钮据此切换方向） */
const bandCollapsed = computed(() => bandHeight.value <= BAND_MIN_H + 1)

loadBandMem()

/** 三栏回到默认宽度(左 296 / 中弹性 / 右 396)。双击分隔条时调用;默认态即此值,故本函数幂等 */
function resetCols(): void {
  // 收起态也一并复位：否则双击分隔条后 colLeft=296、colLeftCollapsed 仍 true，
  // 两者打架（面板被 :min 钳住但被判定为"已收起"），展开键与宽度都不对。
  colLeftCollapsed.value = false
  colRightCollapsed.value = false
  colLeft.value = COL_DEFAULT_LEFT
  colRight.value = COL_DEFAULT_RIGHT
  COL_RECALL_LEFT.value = COL_DEFAULT_LEFT
  COL_RECALL_RIGHT.value = COL_DEFAULT_RIGHT
  saveColMem()
  saveColFoldMem()
}

loadColMem()
loadColFoldMem()

/**
 * 分隔条上的鼠标按下:自己识别双击并调 `resetCols()`(可选加分项 #6)。
 *
 * ⚠️ 这里**不能靠 `@dblclick`** —— 实测(CDP 真实鼠标事件序列)事件根本不会派发到分隔条上:
 *   第 1 次 mousedown 落在 `.el-splitter-bar__dragger`,而 ElSplitter 在 `moveStart` 时
 *   会盖一层 `z-index:999` 的 `.el-splitter__mask`(用于吞掉 iframe 的 touch 事件)。
 *   mouseup 就落在这层 mask 上 → mousedown 与 mouseup 的 target 不一致 →
 *   浏览器不派发 `click`,更没有 `dblclick`。事件日志实测:
 *     mousedown:el-splitter-bar__dragger → mouseup:el-splitter__mask(无 click、无 dblclick)
 *   换成页面上任何普通元素双击,click×2 + dblclick 照常派发 —— 说明是遮罩的问题,不是探针。
 *   所以改成在 `mousedown` 上自己计次:mousedown 始终落在 dragger 上,是可靠的。
 *
 * 另外只在**分隔条自身**命中时计数:直接挂根元素裸监听会把「双击栏内任意空白处」也当复位。
 */
const DBL_MS = 400
let lastBarDown = { at: 0, x: 0, y: 0 }

function onBarMouseDown(e: MouseEvent): void {
  const t = e.target as HTMLElement | null
  if (!t || !t.classList.contains('el-splitter-bar__dragger')) return
  const now = e.timeStamp || Date.now()
  // 同一根分隔条、相邻 400ms 内的第二次按下 = 双击
  if (now - lastBarDown.at < DBL_MS && Math.abs(e.clientX - lastBarDown.x) < 8 && Math.abs(e.clientY - lastBarDown.y) < 8) {
    lastBarDown = { at: 0, x: 0, y: 0 }
    resetCols()
    return
  }
  lastBarDown = { at: now, x: e.clientX, y: e.clientY }
}

/**
 * 包键代号（Issue IKPFR4）：切站时 +1。
 * `activePack()` / `demoSegment()` 读的是**模块级变量**，Vue 不知道它变了 —— 所有
 * "由站点包派生"的 computed 显式读一次 `packTick.value`，切站才能自动重算。
 */
const packTick = ref(packVersion())
/** 当前包键（工具条按钮的选中态 / 切站早退判断用）：跟着 packTick 走，不再是一次性常量 */
const currentPackKey = ref<string>(activePackKey())
const offPackTick = onPackChange(() => {
  packTick.value = packVersion()
  currentPackKey.value = activePackKey()
  // IKPFVN E2：顶栏「线路图切换器」也走同一个 `switchStation()`，本页只收到包键变更通知 ——
  // 据它把视角切到站区，否则用户从顶栏选了站、大屏还停在全国视角看 pin。
  if (mapScope.value !== 'station') mapScope.value = 'station'
})

/** 路网来源短文案(页面页脚口径用):桥接覆盖过就是真路网,否则报包自己的口径 */
const sourceLabel = computed(() => {
  void packTick.value
  return networkSourceLabel()
})
/** 路网几何出处(真值 / 示例样例)—— 真几何与示意几何不能混说(见 demoNetwork.networkGeometryNote) */
const geometryNote = computed(() => {
  void packTick.value
  return networkGeometryNote()
})
/** 页脚站点包自检（`packNote()`：包键 + 这个包是什么）——切站后跟着换，不只报站名 */
const packLine = computed<string>(() => {
  void packTick.value
  return packNote()
})

/** 中栏工具条上的底图口径:顶栏「设置」里的**底图开关**状态直接反映出来(业主 2026-10-16) */
const basemapTag = computed(() =>
  basemapEnabled.value
    ? '底图：OpenFreeMap · OSM（拉不到时只画路网）'
    : '底图：已关闭 · 只画路网（顶栏「设置」里可开）',
)

/** 图下注脚:底图关掉时**不许**再写"底图来源:OpenFreeMap" —— 页面不撒谎 */
const mapCaption = computed(() =>
  basemapEnabled.value
    ? `底图来源:OpenFreeMap(OpenStreetMap 数据,ODbL)· 署名见地图内 · 不缓存瓦片 · 路网:${geometryNote.value}`
    : `底图已在顶栏「设置」里关闭 · 只画路网 · 路网:${geometryNote.value} · OSM 署名见地图内`,
)
/**
 * 站点名(顶栏 chip):默认取当前站点包,拿到 meta 后由 meta.station.name 覆盖 —— 三页同一口径。
 *
 * ⚠️ IKPFR4：兜底值改成 computed（原先是 `ref(activePack().station.name)` 的 setup 期快照，
 *    切站不刷新就永远停在上一站的站名）。meta 那份仍存在独立的 ref 里，切站即清空 ——
 *    让"站名先回落站点包、meta 回来再覆盖"，两站之间不串味。
 */
const metaStationName = ref<string | null>(null)
const stationName = computed<string>(() => {
  if (metaStationName.value) return metaStationName.value
  void packTick.value
  return activePack().station.name
})
/** 接口层 meta(真接口模式:页脚数据来源 / 站点范围 / 快照段数如实取自响应;mock 侧字段可缺省) */
const metaInfo = ref<TrafficMeta | null>(null)
/**
 * 页脚数据来源(真接口模式):不再是写死的「mock 示例快照」——
 * 路段快照数据源 / 路线来自真网还是样例 / 写端点内存态，一律以接口响应为准。
 */
const footDataSource = computed<string>(() => {
  const ds = metaInfo.value?.data_sources
  if (!ds) {
    // mock 模式 meta 没有 data_sources 角标(接口层字段)：如实说 mock 示例快照，不冒充真接口
    return USE_MOCK
      ? 'mock 示例快照（契约 v2.0）· is_simulated = true'
      : '数据来源未取到（接口层未起?）· is_simulated = true'
  }
  const parts = [`路段快照数据源 ${ds.segments ?? '—'}`]
  if (ds.routes) parts.push(`路线 ${ds.routes_note ?? ds.routes}`)
  else parts.push('路线产物缺失（不画路线）')
  if (ds.manual_factors) parts.push(`人工置位 ${ds.manual_factors} 条（内存态）`)
  if (ds.scenario_injected) parts.push('场景已注入（内存态）')
  return `${parts.join(' · ')} · is_simulated = true`
})
/** 页脚站点范围:接口 meta 优先(真接口) → 站点包兜底;站点包路网段数 与 本次快照段数分开说，不混算 */
const footStationLine = computed<string>(() => {
  const station = metaInfo.value?.station
  const range = station?.range_m ?? siteMeta.value.range_m
  const sourceKey = station?.range_source ?? siteMeta.value.range_source
  const source = sourceKey ? (RANGE_SOURCE_LABEL[sourceKey] ?? sourceKey) : '来源未登记'
  const snapshotCount = station?.segment_count ?? segments.value.length
  return `本站范围 ${range ?? '—'} m（${source}）· 站点包路网 ${packSegmentCount.value} 段 · 本次快照 ${snapshotCount} 段`
})

// ---------- 本站范围与路段数（Issue IKM4B4）----------
// 来源：`work/twin/site-ranges.json`（每站一份登记表）→ 站点包 station 字段 → 本页只展示。
// 口径：范围是**脚本推定 / 人工圈定**的结果，不是官方划定；页面不报精度数字。
const siteMeta = computed(() => {
  void packTick.value
  return activePack().station
})
const RANGE_SOURCE_LABEL: Record<string, string> = {
  manual: '人工圈定',
  script: '脚本推定',
  'ai-assisted': 'AI 辅助候选（已人工确认）',
}

// 大屏工具条上的「路网版本」切换（IKMDKY 子单①；IKP5D3 起只剩 Z=61 段 / GZ=708 段两个真站包，Z21 旧包已删）。
// 与顶栏「线路图切换器」**共用同一支** `switchStation()`（IKPFR4）：
// 切包 → 重建路网几何 → 站内状态一律重置 → 缓存优先渲染首屏 → 后台补拉 → 同步 URL。
// 不再整页刷新（原因见 `shared/stationSwitch.ts` 头部与本文件 `resetStationState()`）。
const packChoices = packItems()
/** 合法包键集合（URL 参数校验 / 自动飞入校验共用，不另址一份名单） */
const PACK_KEYS = new Set(packChoices.map((p) => p.key))

// ---------- 全国视角 / 站区视角（Issue IKPFVN）----------
//
// 业主 2026-10-21 口径：「实时渲染的全国大地图，选到对应高铁站再放大展示路网，其他站的路线不展示；
// 切换高铁站要有动作展示：地图缩小 → 移动到对应高铁站 → 放大 → 路线显示、信息切换。」
//
// 两个概念分开，别混：
//   · `mapScope` —— 看多远（全国 / 站区），本页管；镜头运动在 `MapLibreViewer` 里按它跑；
//   · 站点包键 —— 看哪个站（`activePackKey()`），切站唯一入口仍是 `switchStation()`。
//
// ⚠️ 地图组件**始终挂载**（只切左/右栏内容的显隐）：把整块 `v-if` 掉会销毁并重建 Map 实例，
//    那就把 IKPFR4“不重建 Map、不 setStyle”的成果一次性丢掉了。
type MapScope = 'national' | 'station'

/**
 * 首屏视角：`?station=Z|GZ` 直达站区；`?pack=` 是 IKPFR4 已有的**等价参数**（同一语义：指定当前站），
 * 两个都认（取值相同不会打架）；缺省 → 全国视角首屏。
 */
function initialMapScope(): MapScope {
  const raw = route.query.station ?? route.query.pack
  const key = typeof raw === 'string' ? raw : ''
  return PACK_KEYS.has(key) ? 'station' : 'national'
}
const mapScope = ref<MapScope>(initialMapScope())

/**
 * 到站门控（IKPFVN D 节时序）：业主口径是“镜头到站 → 路线显示、信息切换”，
 * 所以页面数据要**等到站再落地**：
 *   · `arriving = true`（切站一开始）→ `refresh()` 的响应先挂住不写面板，骨架屏继续亮；
 *   · 地图组件 `arrived` → `markArrived()` 放行，数据一次性铺上去；
 *   · 兜底 4 s：镜头动画异常 / 地图还没建好（`arrived` 不会来）时，数据不能永远不落地。
 */
const arriving = ref(false)
const ARRIVE_TIMEOUT_MS = 4000
let arriveWaiters: (() => void)[] = []
let arriveTimer = 0

function whenArrived(): Promise<void> {
  if (!arriving.value) return Promise.resolve()
  return new Promise<void>((resolve) => {
    arriveWaiters.push(resolve)
    window.clearTimeout(arriveTimer)
    arriveTimer = window.setTimeout(() => markArrived(), ARRIVE_TIMEOUT_MS)
  })
}

function markArrived(): void {
  window.clearTimeout(arriveTimer)
  arriveTimer = 0
  if (arriving.value) {
    arriving.value = false
    const waiters = arriveWaiters
    arriveWaiters = []
    for (const resolve of waiters) resolve()
  }
  flushPendingCache()
}

/** 缓存快照先挂在一边，到站后再铺（见 `arriving` 的说明） */
let pendingCache: StationSnapshotCache | null = null
let pendingCacheReady = false

function flushPendingCache(): void {
  if (!pendingCacheReady) return
  const snapshot = pendingCache
  pendingCacheReady = false
  pendingCache = null
  commitCachedSnapshot(snapshot)
}

// 首屏自动飞入（IKPFVN E4，业主推荐的 A 方案）：
// 默认全国视角；上次选过的站（`localStorage` 里那份）在 1.2 s 后自动飞进去 ——
// 但**用户一碰就取消**（点 pin / 点浮层卡片 / 点工具条 / 点「← 全国」）。
const AUTO_FLY_DELAY_MS = 1200
const AUTO_FLY_STORAGE_KEY = 'hubflow.stationPack'
let autoFlyTimer = 0
let autoFlyCancelled = false

function cancelAutoFly(): void {
  autoFlyCancelled = true
  window.clearTimeout(autoFlyTimer)
  autoFlyTimer = 0
}

function scheduleAutoFly(): void {
  if (mapScope.value !== 'national') return
  let saved: string | null = null
  try {
    saved = localStorage.getItem(AUTO_FLY_STORAGE_KEY)
  } catch {
    saved = null // 隐私模式：读不到就不飞，首屏保持全国视角，不算错
  }
  if (!saved || !PACK_KEYS.has(saved)) return
  const key = saved
  autoFlyTimer = window.setTimeout(() => {
    autoFlyTimer = 0
    if (autoFlyCancelled || mapScope.value !== 'national') return
    pickStation(key)
  }, AUTO_FLY_DELAY_MS)
}

/**
 * 选站（全国浮层卡片 / 站点 pin / 工具条按钮三处**共用**这一个入口）。
 *
 * 切站本身仍只走 `shared/stationSwitch.ts` 的 `switchStation()`；这里只多做两件事：
 * “把视角切到站区”（镜头由地图组件按 `mapScope` 跑）与取消首屏自动飞入。
 */
function pickStation(key: string): void {
  cancelAutoFly()
  if (!PACK_KEYS.has(key)) {
    mapScope.value = 'national'
    return
  }
  mapScope.value = 'station'
  // `switchStation` 返回 false = 就是当前站：包没变，但镜头仍要从全国飞进去一次。
  // 过渡期并行拉目标站数据：`refresh()` 会拿目标站的 8 个只读快照，并写进该站自己的
  // `stationCache` 桶（等价于预热；再额外调一次 `prefetchStation` 只会把每个接口打两遍）。
  // 数据真正上屏在“到站”之后，见 `arriving` / `whenArrived()`。
  switchStation(key)
}

/** 退回全国视角（工具条「← 全国」）：包不换，只换看多远；站内选中态一并清掉 */
function enterNational(): void {
  cancelAutoFly()
  mapScope.value = 'national'
  selectedId.value = null
}

/** 地图组件报“镜头已落到站区” —— 放行页面数据 */
function onMotionArrived(): void {
  markArrived()
}

// ---------- 快照状态 ----------
const overview = ref<TrafficOverview | null>(null)
const segments = ref<SegmentRecord[]>([])
const vehicles = ref<VehicleRecord[]>([])
const alerts = ref<TrafficAlert[]>([])
/** 全网生效因素(各路段 factors_applied 展平,供 KPI 第 4 格取前 3 条) */
const allFactors = ref<(FactorApplied & { segment_id: string })[]>([])
/** 选中路段的双源并排(video / twin + 差值,TC-19 展示侧) */
const pair = ref<SegmentSourcePair | null>(null)
/** 选中路段的生效因素 */
const segFactors = ref<(FactorApplied & { segment_id: string })[]>([])
/** 选中路段的 CI 走势(原 /heat 右栏) */
const history = ref<CiHistory | null>(null)
/** 路段 × 时间热力矩阵(原 /heat 中栏) */
const heat = ref<HeatMatrix | null>(null)
/** 判级阈值 + CI 四项加权构成(原 /heat 右栏;权重不写死,来自接口) */
const thresholds = ref<ThresholdSnapshot | null>(null)

const selectedId = ref<string | null>(null)
/** 数据源视图(顶栏)：决定右栏「双数据源并排」表按哪一侧口径读数 */
const sourceMode = ref<SourceMode>('both')
/** 视图模式:四级视图(判级产出)/ 拥挤指数视图(展示量,原 /heat 页头切换) */
const viewMode = ref<CongestionViewMode>('level')
// ---------- 颜色模式（Issue IKNB9G，业主 2026-10-18）----------
// 两套颜色，二选一，切换即时重绘（地图 / 列表 / 图例 / 热力 / 排序）：
//   · congestion（默认）= 决策拥堵版：按接口 level 四级判级配色（C-2 既有行为，不改判级）；
//   · flow = 纯车流量版：按 q_vph 分四档（阈值集中在 shared/flow.ts），**仅展示、不参与判级**。
// 持久化：localStorage 键 `hubflow.dashboard.colorMode`；`?color=flow|congestion` 深链可覆盖一次。
// 口径：flow 只用 q，不读 level / CI；缺 q 或数据陈旧 → 灰档「无流量数据」；不宣称 YOLO 已实装。
function initialColorMode(): ColorMode {
  const fromQuery = parseColorMode(route.query[COLOR_MODE_QUERY_KEY])
  if (fromQuery) return fromQuery
  try {
    return parseColorMode(localStorage.getItem(COLOR_MODE_STORAGE_KEY)) ?? 'congestion'
  } catch {
    return 'congestion'
  }
}
const colorMode = ref<ColorMode>(initialColorMode())
const isFlow = computed<boolean>(() => colorMode.value === 'flow')
storeColorMode(colorMode.value)
watch(
  () => route.query[COLOR_MODE_QUERY_KEY],
  (raw) => {
    const mode = parseColorMode(raw)
    if (mode && mode !== colorMode.value) applyColorMode(mode)
  },
)
/** 切模式：写 localStorage；flow 下不提供 CI 视图（CI 是决策口径），自动回四级视图 */
function applyColorMode(mode: ColorMode): void {
  colorMode.value = mode
  storeColorMode(mode)
  if (mode === 'flow' && viewMode.value === 'index') viewMode.value = 'level'
}
function setColorMode(mode: ColorMode): void {
  if (colorMode.value === mode) return
  applyColorMode(mode)
}
/** 监控范围筛选(左栏「选择监控」):null = 全部;0 = 数据不可用档 */
const scope = ref<CongestionLevel | 0 | null>(null)
const snapshotTs = ref('')

// ---------- 中栏地图 · 单渲染器(Issue IKM5T1) ----------
// 只留**一个**地图组件(MapLibre:矢量底图 + 描出的路网)。原先"示例路网 / 矢量地图"两个模式已删:
//   · 自绘那套(NetMap.vue)的四件事——车辆动点 / 悬停浮牌 / 推荐路线 / 图例+水印——搬进了地图组件;
//   · 而"示例路网"那个观感**在底图拉不出来时自动出现**:地图先用本地兜底样式建起来、路网立刻画,
//     底图失败只丢底图(详见 `components/MapLibreViewer.vue` 头部注释)。
// 只剩站点包 Z、几何统一 WGS-84,所以不再需要"按包 / 按路网切底图"的分支。

let unsubscribe: (() => void) | null = null

const selected = computed<SegmentRecord | null>(
  () => segments.value.find((s) => s.segment_id === selectedId.value) ?? null,
)

// Issue IKMS18：允许选中**站点包里但快照没覆盖**的路段（地图上任一段都可点）。
// 这种段：摄像头卡照常按登记表展示；指标 / 判级 / 下令一律如实「无数据 / 不可用」，不编造。
const selectedName = computed<string>(() => {
  const id = selectedId.value
  if (!id) return '—'
  return demoSegment(id)?.name ?? selected.value?.segment_id ?? id
})

// ---------- IKP5BZ：本段附近的落客点 / 场区（唯一真值源 = 前端站点包） ----------
// 图上 Marker 之外再给一处**文字入口**：选中路段时列出同段 / 邻近段（≤150 m）的点位，
// 点条目 → 选中其所属路段（地图上点不到时仍可查）。坐标是演示点，不是踏勘点位。
const nearbyLandmarks = computed(() => landmarksNearSegment(selectedId.value ?? ''))
/** 距离显示（米）：非有限值如实「未标定」，不写 0 */
function landmarkDistance(v: number): string {
  return Number.isFinite(v) ? `约 ${Math.round(v)} m` : '距离未标定'
}

// ---------- IKOQEJ：方向 / 车道 / 对向 / 贯通（只读站点包字段，非契约、不参与判级） ----------
const segDirection = computed(() => directionOf(selectedId.value ?? ''))
const segDirectionKind = computed(() => directionKindOf(segDirection.value))
const segDirectionLabel = computed(() => directionLabel(segDirectionKind.value))
const segDirectionSource = computed(() => directionSourceLabel(segDirection.value))
const segLanes = computed(() => lanesOf(segDirection.value))
const segContinuity = computed(() => continuityOf(segDirection.value))
const segOpposite = computed(() => oppositeOf(segDirection.value))
/** 对向段是否在当前前端站点包里（GZ enriched 708 段 > 前端 433 段时，部分对向段尚未同步） */
const segOppositePresent = computed(() => Boolean(segOpposite.value && demoSegment(segOpposite.value)))
/** 浮牌里的短口径（方向 / 车道 / 对向 / 贯通），字段缺省一律「未标定」 */
const segContinuityChip = computed<string>(() => {
  if (segContinuity.value.state !== 'pending') return segContinuity.value.label
  const gap = segDirection.value?.continuity?.gap_to_next_m
  return typeof gap === 'number' && Number.isFinite(gap)
    ? `贯通性待核(gap ${gap} m)`
    : '贯通性待核(gap 未标定)'
})
const segDirectionChip = computed<string>(() => {
  const parts = [
    `方向 ${segDirectionKind.value === 'unknown' ? '未标定' : segDirectionLabel.value.replace(/（.*）/, '')}`,
    `车道 ${segLanes.value.text}`,
  ]
  if (segOpposite.value) {
    parts.push(`对向 ${segOpposite.value}${segOppositePresent.value ? '' : '(待同步)'}`)
  }
  parts.push(segContinuityChip.value)
  return parts.join(' · ')
})

/** 默认选中:非陈旧路段里 level 最高者(同档取 x 大者);无可用则退回首条 */
function pickDefaultId(list: SegmentRecord[]): string | null {
  if (list.length === 0) return null
  const usable = list.filter((s) => !isStale(s))
  const pool = usable.length > 0 ? usable : list
  let best = pool[0]!
  for (const s of pool) {
    if (s.level > best.level || (s.level === best.level && (s.x ?? 0) > (best.x ?? 0))) best = s
  }
  return best.segment_id
}

/** 选中路段相关的三个接口(并排表 + 因素 + CI 走势);选中变化与快照刷新都会重拉 */
async function loadSelectedSide(segmentId: string | null): Promise<void> {
  if (!segmentId) {
    pair.value = null
    segFactors.value = []
    history.value = null
    return
  }
  // 站点包里有、但当前快照没覆盖的段（Issue IKMS18 允许地图选中）：不请求不存在的快照端点，
  // 详情卡按「无数据」如实降级（避免 404 噪声，也不拿别的段顶替）。
  if (!selected.value) {
    pair.value = null
    segFactors.value = []
    history.value = null
    return
  }
  const [p, f, h] = await Promise.allSettled([
    getTrafficSegmentSources(segmentId),
    getTrafficFactors(segmentId),
    getTrafficCiHistory(segmentId, 12),
  ])
  if (selectedId.value !== segmentId) return // 选择已变:丢弃过期响应
  pair.value = p.status === 'fulfilled' ? p.value : null
  segFactors.value = f.status === 'fulfilled' ? f.value.factors : []
  history.value = h.status === 'fulfilled' ? h.value : null
}

/**
 * 刷新序号:SSE 触发与手动刷新可能并发。只有"最新一次"的响应允许落到页面,
 * 否则先发出、后返回的旧响应会覆盖新快照(页面显示上一版数据)。
 */
let refreshSeq = 0
/**
 * 在途刷新的中止句柄（Issue IKPFR4）。切站时**必须**把上一站的请求掐掉：否则旧站响应会在
 * 几百毫秒后回来，把刚渲染好的新站首屏覆盖成旧站数据 —— 那正是"把 Z 的数据当 GZ 显示"。
 * 与"响应回来时校验站点键"是**两道闸**，都留着（中止省带宽，校验兜底）。
 */
let refreshCtrl: AbortController | null = null
/** 首屏之后是否已经排过预热（只排一次，避免每次 SSE 刷新都替别站重拉） */
let prewarmed = false
/** 本次刷新中失败的接口(页头提示用;失败面板保留旧值但必须标"上一版",不得冒充当前) */
const failedPanels = ref<string[]>([])
/** SSE 刷新通道连接状态:断开时页面不会自动刷新,必须显式提示(TC-06 断流降级) */
const sseConnected = ref(true)

/** 切站加载态：无缓存时才亮（极简骨架条），有缓存不走这里 */
const switching = ref(false)
/** 是否正在显示缓存快照：后台刷新回来立刻清掉 —— 缓存数据不得冒充最新（业主口径） */
const servedFromCache = ref(false)
/** 缓存写入时刻（ms），提示条据此写"缓存于 N s 前" */
const cacheStamp = ref(0)
/**
 * 「缓存于 N s 前」的时钟源（PR !76 审查意见）。
 * 为什么需要单独一个 ref：`Date.now()` 不是响应式的 —— 没有它，秒数会**停在切站那一刻**
 * （数据没错，但"几秒前"这句话会变成假的）。只在亮着缓存条时开 1 s 定时器，条件一变就停。
 */
const cacheClockTick = ref(0)
let cacheClockTimer = 0
watch(servedFromCache, (on) => {
  window.clearInterval(cacheClockTimer)
  if (!on) return
  cacheClockTimer = window.setInterval(() => {
    cacheClockTick.value += 1
  }, 1000)
})
/** 缓存提示文案；空 = 当前数据就是这次网络拉到的，不用标"缓存" */
const cacheNote = computed<string>(() => {
  if (!servedFromCache.value) return ''
  void cacheClockTick.value // 每秒 +1，让"几秒前"跟着走（见上）
  const age = Math.max(0, Math.round((Date.now() - cacheStamp.value) / 1000))
  return `当前显示「${stationName.value}」的缓存快照（缓存于 ${age} s 前）· 正在后台刷新，新数据到达即替换 —— 缓存数据不代表最新态势`
})

const PANEL_LABEL: Record<string, string> = {
  overview: 'KPI',
  segments: '路段监测',
  vehicles: '车辆',
  alerts: '告警',
  factors: '因素',
  matrix: '热力矩阵',
  thresholds: '阈值与 CI 权重',
}

async function refresh(): Promise<void> {
  const seq = ++refreshSeq
  // ⚠️ 这里**不掐**上一轮：慢后端（GZ 站远端首载可到十几秒，见 README 23.9 登记）会碰上 SSE 每 2 s 的一次
  //    刷新 —— 每轮都 abort 的话所有请求都在半路被杀，数据永远落不下来。上一轮的响应靠
  //    `refreshSeq` 作废即可（见下方两道闸），abort 只在**切站**时用（`resetStationState`）。
  const ctrl = new AbortController()
  refreshCtrl = ctrl
  // 这一轮请求配属的站键：写缓存、校验响应都以它为准（不要用 activePackKey() 事后现取）
  const stationKey = activePackKey()
  const opts = { signal: ctrl.signal }
  // Issue IKP5BZ（方案 A）：不再请求 `/api/traffic/network`——落客点/场区唯一真值源是前端站点包，
  // 这条端点的 dropoffs/zones 与本站真网段号对不上（Z 是 SEG-### 样例点、GZ 为空表），
  // 取了也不用；留着只会在页头打「本次刷新未取到：路网」，而页面上并没有路网面板。
  const [ov, seg, veh, al, fa, meta, matrix, thr] = await Promise.allSettled([
    getTrafficOverview(opts),
    getTrafficSegments(opts),
    getTrafficVehicles(opts),
    getTrafficAlerts(opts),
    getTrafficFactors(undefined, opts),
    getTrafficMeta(opts),
    getTrafficHeatMatrix(12, 60, opts),
    getTrafficThresholds(opts),
  ])
  if (seq !== refreshSeq) return // 已被更晚的一次刷新取代:丢弃本次响应
  // 第二道闸:站点键已换(切站) → 这批响应属于上一站,一律丢弃
  if (stationKey !== activePackKey()) return
  // IKPFVN D2：镜头还在飞就先挂住响应 —— 到站后再一次性铺数据（骨架屏继续亮）。
  // ⚠️ await 之后必须**重新验证两道闸**：等镜头这几秒里用户完全可能又点了一个站。
  if (arriving.value) {
    await whenArrived()
    if (seq !== refreshSeq) return
    if (stationKey !== activePackKey()) return
  }
  switching.value = false
  const failed: string[] = []
  const track = (name: string, ok: boolean): void => {
    if (!ok) failed.push(PANEL_LABEL[name] ?? name)
  }
  if (ov.status === 'fulfilled') overview.value = ov.value
  track('overview', ov.status === 'fulfilled')
  if (seg.status === 'fulfilled') {
    segments.value = seg.value.segments
    snapshotTs.value = seg.value.ts
    // 应急态(TC-10)：接口层已在快照顶层派生好，这里**原样消费**，不自己判等级
    emergency.value = seg.value.emergency ?? null
    if (selectedId.value === null) selectedId.value = pickDefaultId(seg.value.segments)
    applyDeepSegment()
  }
  track('segments', seg.status === 'fulfilled')
  if (veh.status === 'fulfilled') vehicles.value = veh.value.vehicles
  track('vehicles', veh.status === 'fulfilled')
  if (al.status === 'fulfilled') alerts.value = al.value.alerts
  track('alerts', al.status === 'fulfilled')
  if (fa.status === 'fulfilled') allFactors.value = fa.value.factors
  track('factors', fa.status === 'fulfilled')
  if (matrix.status === 'fulfilled') heat.value = matrix.value
  track('matrix', matrix.status === 'fulfilled')
  if (thr.status === 'fulfilled') thresholds.value = thr.value
  track('thresholds', thr.status === 'fulfilled')
  // 站名只用于顶栏 chip:取不到就保持站点包里的名字,不因此把整页标成"上一版数据"
  if (meta.status === 'fulfilled') {
    metaInfo.value = meta.value
    metaStationName.value = meta.value.station.name
  }
  failedPanels.value = failed
  // 只有真的拿到新快照才撤掉"缓存"标识：这一轮全挂时页面上仍是缓存数据，
  // 撤标就等于让缓存冒充最新（上面那条失败提示条负责说明"看到的是上一版"）
  if (seg.status === 'fulfilled' || ov.status === 'fulfilled') {
    servedFromCache.value = false
    cacheStamp.value = 0
  }
  // 把这一轮拿到的字段写进**该站自己的**缓存桶（切站时就是靠它秒开）
  writeStationCache(stationKey, {
    ...(ov.status === 'fulfilled' ? { overview: ov.value } : {}),
    ...(seg.status === 'fulfilled' ? { segments: seg.value } : {}),
    ...(meta.status === 'fulfilled' ? { meta: meta.value } : {}),
    ...(thr.status === 'fulfilled' ? { thresholds: thr.value } : {}),
    ...(al.status === 'fulfilled' ? { alerts: al.value } : {}),
    ...(fa.status === 'fulfilled' ? { factors: fa.value.factors } : {}),
    ...(matrix.status === 'fulfilled' ? { matrix: matrix.value } : {}),
  })
  // 首屏就位后再预热（不抢首屏带宽；失败静默）
  if (!prewarmed && seg.status === 'fulfilled') {
    prewarmed = true
    schedulePrewarm()
  }
  await loadSelectedSide(selectedId.value)
}

watch(selectedId, (id) => {
  void loadSelectedSide(id)
})

// ---------- 原地切站（Issue IKPFR4，业主 2026-10-21 裁定）----------
//
// 三件正事，顺序就是 `switchStation()` 里的调用顺序：
//   ① `resetStationState()` —— 站内状态**一律重置**，不做跨站恢复：
//      selectedId / 监控范围（热力带选中）/ 路线 session / 推荐与定位 / 深链选中 / 失败面板 /
//      上一站的 meta 与快照，一律清空；页面回到顶部；在途请求中止。
//   ② `applyCachedSnapshot()` —— 缓存优先：目标站有缓存就**同步**渲染首屏（不白屏、不加载态）；
//      没缓存才亮骨架条，等第 ③ 步的网络结果。
//   ③ `refresh()` —— 后台补拉一次（不等 SSE 的下一个 2 s tick），新数据到达后按字段替换。

/** 页面回到顶部：整页 + 三栏内部滚动容器（左「路段监测」/ 右「路段信息」） */
function scrollPageToTop(): void {
  window.scrollTo({ top: 0 })
  for (const el of document.querySelectorAll<HTMLElement>('.td-scroll, .seg-list')) el.scrollTop = 0
}

/** 站内状态一律重置（业主裁定：切站不跨站恢复任何选中态） */
function resetStationState(): void {
  // 中止上一站的在途请求：序号也 +1，让"已经飞出去但还没回来的"那一轮认不出自己是最新的
  refreshCtrl?.abort()
  refreshCtrl = null
  refreshSeq += 1

  selectedId.value = null
  scope.value = null
  deepApplied = false
  // 路线 / 定位 / 双源 / 走势：都是"按某个段、某个 session 取回来的"，跨站一律不保留
  selectedSession.value = ''
  recommend.value = null
  recommendError.value = ''
  routeOptions.value = null
  routeOptionsError.value = ''
  pair.value = null
  segFactors.value = []
  history.value = null
  locateInfo.value = null
  locateError.value = ''
  startConfirmed.value = false
  manualStart.value = false
  manualStartId.value = ''
  // 快照侧：先清空，再由缓存或新一轮刷新填回来（清空这一步保证绝不会把上一站的数据当本站显示）
  overview.value = null
  segments.value = []
  vehicles.value = []
  alerts.value = []
  allFactors.value = []
  thresholds.value = null
  heat.value = null
  metaInfo.value = null
  metaStationName.value = null
  snapshotTs.value = ''
  failedPanels.value = []
  servedFromCache.value = false
  cacheStamp.value = 0
  // 应急态跟着快照一起清：切站后未拿到新快照前不得沿用上一站的应急结论
  emergency.value = null
  // IKPFVN D 节：从这一行起，页面数据等“镜头到站”再上屏（骨架屏先亮着）；
  // `markArrived()`（地图组件报 arrived / 4 s 兜底）会把它放行。
  arriving.value = true
  switching.value = true

  scrollPageToTop()
}

/**
 * 缓存优先渲染（切站钩子）。
 *
 * IKPFVN D 节：镜头还在飞的时候**不往面板上铺**（业主口径是“到站再信息切换”），
 * 先把快照挂在一边，`markArrived()` 时再走 `commitCachedSnapshot()`。
 * 本函数仍保持**同步**语义（只是存一下，不等网络）——秒开靠的是“不等网络”，与何时上屏无关。
 */
function applyCachedSnapshot(snapshot: StationSnapshotCache | null): void {
  if (arriving.value) {
    pendingCache = snapshot
    pendingCacheReady = true
    return
  }
  commitCachedSnapshot(snapshot)
}

/** 真正把缓存铺到首屏（切站开始时与到站后各可能调一次） */
function commitCachedSnapshot(snapshot: StationSnapshotCache | null): void {
  if (!snapshot) {
    // 没有缓存（首次访问该站 / 预热还没完成）：只亮骨架条，页面本身不白屏
    switching.value = true
    return
  }
  // 缓存里若连 segments 都没有（当初那个接口就没取到）：列表/地图仍空，骨架条照样亮着
  switching.value = !snapshot.segments
  servedFromCache.value = true
  cacheStamp.value = snapshot.ts
  overview.value = snapshot.overview
  if (snapshot.segments) {
    segments.value = snapshot.segments.segments
    snapshotTs.value = snapshot.segments.ts
    // 应急态(TC-10)：缓存里带着当时的派生结果，恢复时一并还原（不重算）
    emergency.value = snapshot.segments.emergency ?? null
  }
  alerts.value = snapshot.alerts?.alerts ?? []
  allFactors.value = snapshot.factors ?? []
  thresholds.value = snapshot.thresholds
  heat.value = snapshot.matrix
  metaInfo.value = snapshot.meta
  metaStationName.value = snapshot.meta?.station.name ?? null
  // 车辆动点不入缓存：宁可空着等下一轮刷新，也不画"上一次看到的车"（位置流每 2 s 就过期）
  vehicles.value = []
}

/** 注销钩子（组件卸载时必须调，否则切站会往已卸载的页面里写数据） */
const unbindStationSwitch = bindStationSwitch({
  resetStationState,
  applyCachedSnapshot,
  refresh: () => {
    void refresh()
    // 路线产物是**按站**出的（引擎每个站一份 routes.json）：切站后重新取一次 OD 选项，
    // 别让右栏停在上一站的 session 上（这是"站内状态一律重置"里"路线 session"那一条）
    void loadRouteOptions()
  },
})
onUnmounted(() => {
  unbindStationSwitch()
  offPackTick()
  // 卸载时把在途请求一并掐掉（切页 / 关页都不该让响应回来往空组件里写）
  refreshCtrl?.abort()
  refreshCtrl = null
  // 「缓存于 N s 前」的时钟也一起停，别让定时器在已卸载的页面上空转
  window.clearInterval(cacheClockTimer)
})

// ---------- 推荐路线（Issue IKMF1W）----------
//
// 数据来自 `POST /api/traffic/route/recommend`（vite mock 与接口层同一契约；引擎 routes.json
// 就绪后由接口层端出真结果，本页数据形状不变）。
// 口径三条（判定依据见 Issue IKMF1W「完成判定」）：
//   ① 只消费契约字段 `arrival_route` / `alternatives[].segments` / `departure_route`，不新增字段；
//   ② 接口不可达 → **保持不画路线** + 可读提示，绝不用本地 fallback 编一条假路线（与 TC-11 同口径）；
//   ③ 路线是**连通图拼出来的演示骨架**，不是引擎 K 最短路 + 预约输出，也**不是按当时路况重算的结果**——
//      页面文案与图例必须如实标注。
type RouteView = 'all' | 'arrival' | 'alternative' | 'departure'
const ROUTE_VIEWS: { key: RouteView; name: string }[] = [
  { key: 'all', name: '全部' },
  { key: 'arrival', name: '推荐' },
  { key: 'alternative', name: '备选' },
  { key: 'departure', name: '离站' },
]
/** 推荐快照（null = 接口不可达或无数据；此时地图不画任何路线） */
const recommend = ref<RecommendResult | null>(null)
const recommendLoading = ref(false)
const recommendError = ref('')
/**
 * 应急态（TC-10，手册 §11.1(3)）：应急时**停下路线引导**，替换为固定措辞「请服从现场指挥」，
 * 优先级高于一切推荐。
 *
 * 口径三条（别改错）：
 *   ① 只消费接口层派生的 `emergency`，**不自己判**：不自算等级、不比对阈值、不看 factors 猜；
 *   ② `active === false` 即常态，页面照常给推荐 —— 不得把「读不到」兜底成应急（会误停引导）；
 *   ③ 应急 ≠ 清空页面：只收起**推荐路线那块**（这是被停下的「引导」），
 *      地图、KPI、路段信息、车辆等正文一律照常显示。
 */
const emergency = ref<EmergencyState | null>(null)
/** 应急是否生效（接口未给/读不到 → false，宁可不误停） */
const emergencyActive = computed(() => emergency.value?.active === true)
/** 应急影响路段的可读文案（超过 3 段只列前 3 段 + 省略，不糊满整行） */
const emergencySegmentText = computed(() => {
  const ids = emergency.value?.segment_ids ?? []
  if (ids.length === 0) return ''
  const head = ids.slice(0, 3).join('、')
  return ids.length > 3 ? `${head} 等 ${ids.length} 段` : head
})
/** 应急已登记因素的可读文案（只列编号 + 目标 + 倍率，原样透传不自算） */
const emergencyFactorText = computed(() => {
  const list = emergency.value?.factors ?? []
  return list
    .slice(0, 4)
    .map((f) => `${f.factor_id ?? '—'}（${f.target ?? '—'} ×${f.multiplier ?? '—'}）`)
    .join('、')
})
/** 三态切换：全部 / 推荐 / 备选 / 离站（截图三态用同一套按钮） */
const routeView = ref<RouteView>('all')
/** 当前站点包内的段数（卡片文案用；切包后不写死 61） */
const packSegmentCount = computed(() => {
  void packTick.value
  return activePack().segments.length
})
/**
 * 当前站点包内的段号集合：路线引用的段必须都在包里，防悬空画假线。
 * ⚠️ IKPFR4：原先是 setup 期的 `Set` 常量 —— 切站后仍是上一站的段号集合（Z 61 段看 GZ 708 段
 *    的路线会全部被判"不在包里"）。改成 computed，用它的地方一律取 `.value`。
 */
const packSegmentIds = computed<Set<string>>(() => {
  void packTick.value
  return new Set(activePack().segments.map((s) => s.segment_id))
})

// ---------- 整条路线规划（Issue IKNAUI）----------
//
// 入口：`GET /api/traffic/route/options`（只读辅助端点、非契约 §七）端出引擎产物的
// OD / session / 进场路线 / 备选 / 离站路线**摘要**；选中后用真实 `session_id` 调
// `POST /route/recommend`，地图用同一份 recommend 数据画三态路线（RouteHighlight）。
// 口径：ETA / 段号原样透传，**前端不重算路线**；无产物 / 无选项 / 不匹配 → 如实空窗 + note。
const routeOptions = ref<RouteOptionsSnapshot | null>(null)
const routeOptionsLoading = ref(false)
const routeOptionsError = ref('')
/** 当前选中的引擎 session（空 = 回退演示会话路线） */
const selectedSession = ref('')
const selectedOption = computed<RouteOption | null>(() => {
  const options = routeOptions.value?.options ?? []
  return options.find((item) => item.session_id === selectedSession.value) ?? null
})

function fmtEta(value: number | null | undefined): string {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(2) : '—'
}

/** 全程摘要（进场 → 落客 → 离站）：字段全部原样来自引擎摘要，不重算。 */
const tripSummary = computed(() => {
  const option = selectedOption.value
  if (!option) return null
  const arrival = option.arrival_route
  const departure = option.departure_route
  return {
    od: option.od_id ?? '—',
    session: option.session_id ?? '—',
    start: option.location.segment_id ?? '—',
    arrivalSegments: arrival?.segments.length ?? 0,
    arrivalEta: fmtEta(arrival?.eta_min),
    arrivalPath: arrival?.segments.join(' → ') ?? '',
    dropoff: arrival?.dropoff_point ?? null,
    alternatives: option.alternatives.length,
    departureSegments: departure?.segments.length ?? 0,
    departureEta: fmtEta(departure?.eta_min),
    departurePath: departure?.segments.join(' → ') ?? '',
    source: routeOptions.value?.data_source ?? 'engine.routes.real',
    sourceNote: routeOptions.value?.data_source_note ?? '',
  }
})

async function loadRecommend(sessionId?: string): Promise<void> {
  recommendLoading.value = true
  recommendError.value = ''
  try {
    const pack = activePack()
    const session = sessionId || `demo-${pack.key}`
    const option = sessionId ? selectedOption.value : null
    recommend.value = await postRouteRecommend({
      // 有引擎选项时用该 OD 的起点（引擎产物里的 location），否则沿用站点包演示锚点
      session_id: session,
      location: {
        segment_id: option?.location.segment_id ?? pack.recommend.location_segment_id,
        offset_m: option?.location.offset_m ?? pack.recommend.location_offset_m,
      },
    })
  } catch (e) {
    // 失败降级：清空路线 + 给出可读提示；不得拿 fallback 假数据兜底
    recommend.value = null
    recommendError.value = `推荐接口不可达（${e instanceof Error ? e.message : '未知错误'}）：保持不画路线，不编造演示路线`
  } finally {
    recommendLoading.value = false
    // 起点与推荐同源（同一份引擎产物）：每次取推荐后同步刷新 /locate，避免两块显示两个起点
    void refreshLocate()
  }
}

/** 载入引擎 OD 选项 → 默认选第一条并画其完整路线；无选项 / mock 无该端点 → 回退演示会话路线 */
async function loadRouteOptions(): Promise<void> {
  routeOptionsLoading.value = true
  routeOptionsError.value = ''
  // mock 中间件没有 /route/options（未匹配路径一律 404）：不去打一条注定 404 的请求，
  // 直接按「mock 无该辅助端点」如实提示并回退演示会话路线（页面不崩、控制台不刷 404）。
  if (USE_MOCK) {
    routeOptions.value = null
    routeOptionsError.value = 'mock 模式无 /api/traffic/route/options 端点（辅助端点仅真接口提供）'
    await loadRecommend()
    routeOptionsLoading.value = false
    return
  }
  try {
    const res = await getTrafficRouteOptions()
    const options = (Array.isArray(res.options) ? res.options : []).filter((item) => Boolean(item.session_id))
    routeOptions.value = options.length > 0 ? { ...res, options } : null
    if (options.length > 0) {
      selectedSession.value = options[0]!.session_id as string
      await loadRecommend(selectedSession.value)
    } else {
      await loadRecommend()
    }
  } catch (e) {
    routeOptions.value = null
    routeOptionsError.value = e instanceof Error ? e.message : String(e)
    await loadRecommend()
  } finally {
    routeOptionsLoading.value = false
  }
}

function onRouteSessionChange(): void {
  if (!selectedSession.value) return
  void loadRecommend(selectedSession.value)
}

// ---------- 起点 / 终点确认（Issue IKP5C6）----------
//
// 一期口径：起点是**孪生真值**（接口 `/api/traffic/locate` 直读引擎产物 `requests[].location`，
// 接口层不做地图匹配），所以这里的“确认”只是把这份真值显式摆给使用者看并留下一个确认动作，
// **不是用户定位**；未确认时页面必须写明「按孪生真值演示」，不得暗示“已确认你的位置”。
// TC-05 展示侧兜底：定位不可用 / 置信度低时，可从当前站点包手动选一段作为起点（流程不中断）。
const locateInfo = ref<LocateResult | null>(null)
const locateLoading = ref(false)
const locateError = ref('')
/** 使用者是否点过「以这里为起点」（切换 session 后重置） */
const startConfirmed = ref(false)
/** 手动选起点（兜底）：从当前站点包路段下拉里选一段 */
const manualStartId = ref('')
const manualStart = ref(false)

const packSegments = computed(() => {
  void packTick.value
  return activePack().segments
})

/** 当前起点：手动选择优先 → /locate 结果 → 推荐响应自带的 location（失败降级，不编） */
const currentStart = computed<{
  segment_id: string
  offset_m: number | null
  match_confidence: number | null
  source: string
} | null>(() => {
  if (manualStart.value && manualStartId.value) {
    return { segment_id: manualStartId.value, offset_m: 0, match_confidence: null, source: 'manual' }
  }
  const loc = locateInfo.value
  if (loc && loc.segment_id) {
    return {
      segment_id: loc.segment_id,
      offset_m: loc.offset_m,
      match_confidence: loc.match_confidence,
      source: loc.source,
    }
  }
  const rec = recommend.value?.location
  if (rec) {
    return {
      segment_id: rec.segment_id,
      offset_m: rec.offset_m,
      match_confidence: rec.match_confidence ?? null,
      source: rec.source,
    }
  }
  return null
})
const startName = computed(() => (currentStart.value ? nameOf(currentStart.value.segment_id) : '—'))
const startSourceLabel = computed(() => {
  const source = currentStart.value?.source
  if (source === 'twin') return '孪生真值'
  if (source === 'app_gnss') return 'App 定位'
  if (source === 'manual') return '手动选择'
  return source || '—'
})
const confidenceText = computed(() => {
  const c = currentStart.value?.match_confidence
  return typeof c === 'number' && Number.isFinite(c) ? c.toFixed(2) : '—'
})
const offsetText = computed(() => {
  const v = currentStart.value?.offset_m
  return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(1) : '—'
})
/** 与 `work/engine/locate.py` 的 MATCH_CONFIDENCE_MIN 同口径：< 0.6 提示定位不稳定（不改判定） */
const confidenceLow = computed(() => {
  const c = currentStart.value?.match_confidence
  return typeof c === 'number' && Number.isFinite(c) && c < 0.6
})

/** 终点：优先 `arrival_route.dropoff_point`；为 null 时给 `why` 里的具体原因 + 末段兜底 */
const tripEnd = computed(() => {
  const r = recommend.value
  if (!r) return null
  const segs = r.arrival_route.segments ?? []
  const last = segs.length > 0 ? segs[segs.length - 1]! : null
  const drop = r.arrival_route.dropoff_point ?? null
  const landmark = drop
    ? [...activePack().dropoffs, ...activePack().zones].find((p) => p.id === drop)
    : undefined
  // why 里的原因用 [] 括起（引擎口径）；只挑与终点 / 点位相关的条目，别把离站原因混进来
  const notes = (r.why.match(/\[[^\]]+\]/g) ?? []).filter((n) => /落客|上客|点位|终点/.test(n))
  return {
    drop,
    pointName: landmark?.name ?? null,
    last,
    lastName: last ? nameOf(last) : '—',
    reason: notes.join(' '),
  }
})

// ---------- 地图上的「起点 / 终点」标注（业主 2026-10-21 口径） ----------
// 「那些大道最外面的路段就是起点，然后停车场落客点是终点」：起点用推荐路线实际起点路段
// （引擎边界推导的进场段，站点包里登记为 boundary 的 P-Bxx），终点优先对齐站点包里的
// 停车场落客点（演示点），对不上才退回末段终点——只做展示，不改算路 / ETA。
const startBoundarySection = computed(() => {
  const id = currentStart.value?.segment_id
  if (!id) return null
  return (activePack().sections ?? []).find((s) => s.segment_id === id && s.role === 'boundary') ?? null
})

const routeStartMarker = computed<RouteEndpointMarker | null>(() => {
  // 应急态：起点标记属于引导，一并收起
  if (emergencyActive.value) return null
  const s = currentStart.value
  if (!s) return null
  const seg = demoSegment(s.segment_id)
  if (!seg || seg.coords.length === 0) return null
  const p = pointAtOffset(seg.coords, s.offset_m ?? 0)
  return {
    kind: 'start',
    label: '起点',
    segment_id: s.segment_id,
    name: seg.name,
    lon: p[0],
    lat: p[1],
    note: startBoundarySection.value
      ? `外围边界断面 ${startBoundarySection.value.point_id}（演示）`
      : '路网内部段（演示）',
  }
})

const routeEndMarker = computed<RouteEndpointMarker | null>(() => {
  // 应急态：终点标记属于引导，一并收起
  if (emergencyActive.value) return null
  const r = recommend.value
  if (!r) return null
  const segs = r.arrival_route.segments ?? []
  const last = segs.length > 0 ? segs[segs.length - 1]! : null
  if (!last) return null
  const seg = demoSegment(last)
  const dropId = r.arrival_route.dropoff_point ?? null
  if (dropId) {
    const point = activePack().dropoffs.find((d) => d.id === dropId)
    if (point) {
      return {
        kind: 'end',
        label: '终点·落客点',
        segment_id: last,
        name: point.name,
        lon: point.lon,
        lat: point.lat,
        note: `点位 ${dropId}（演示点）`,
        point_id: dropId,
      }
    }
  }
  const near = landmarksNearSegment(last)
    .filter((x) => x.kind === 'dropoff')
    .sort((a, b) => a.distance_m - b.distance_m)[0]
  if (near) {
    return {
      kind: 'end',
      label: '终点·落客点',
      segment_id: last,
      name: near.name,
      lon: near.lon,
      lat: near.lat,
      note: `停车场落客点 ${near.id}（演示点）· 距末段 ${Math.round(near.distance_m)} m`,
      point_id: near.id,
    }
  }
  if (!seg || seg.coords.length === 0) return null
  const p = pointAtOffset(seg.coords, Math.max(0, segmentLengthM(seg.coords) - 1))
  return {
    kind: 'end',
    label: '终点',
    segment_id: last,
    name: seg.name,
    lon: p[0],
    lat: p[1],
    note: '引擎产物未给落客点；落在末段终点（演示）',
  }
})

/** 拉一次 /locate（真接口才有；mock 如实标注降级，不编起点） */
async function refreshLocate(): Promise<void> {
  locateError.value = ''
  locateInfo.value = null
  startConfirmed.value = false
  manualStart.value = false
  manualStartId.value = ''
  if (USE_MOCK) {
    locateError.value = 'mock 模式无 /api/traffic/locate 端点（辅助端点仅真接口提供）'
    return
  }
  locateLoading.value = true
  try {
    locateInfo.value = await postTrafficLocate({ session_id: selectedSession.value || undefined })
  } catch (e) {
    locateError.value = `定位接口不可达（${
      e instanceof Error ? e.message : '未知错误'
    }）；当前按推荐响应自带的 location 显示，不编起点`
  } finally {
    locateLoading.value = false
  }
}

function confirmStart(): void {
  if (currentStart.value) startConfirmed.value = true
}

function applyManualStart(): void {
  if (!manualStartId.value) return
  manualStart.value = true
  startConfirmed.value = true
}



/** 地图要高亮的路线分组（按 routeView 过滤；无数据时为空数组） */
const routeHighlights = computed<RouteHighlight[]>(() => {
  // 应急态（TC-10）：路线引导已停下 → 地图上不再画任何推荐/备选/离站路线。
  // 这是「停下路线引导」的落地：只停引导，不隐藏车流与路况本身（那些是态势，不是引导）。
  if (emergencyActive.value) return []
  const r = recommend.value
  if (!r) return []
  const groups: RouteHighlight[] = []
  if (routeView.value === 'all' || routeView.value === 'arrival') {
    groups.push({ kind: 'arrival', key: 'arrival', segments: r.arrival_route.segments })
  }
  if (routeView.value === 'all' || routeView.value === 'alternative') {
    // Issue IKP5CK：备选不能再全压成同一个 `alternative` 分组（两条备选会画成同一套灰虚线）。
    // `index` 是前端展示类型字段（非契约）：1 = 备选 1（长虚）、2 = 备选 2（短虚）；
    // 2026-10-28 业主统一蓝色系后两条备选同色（中蓝 #2563EB），只靠节律 + 平行偏置区分。
    r.alternatives.forEach((a, i) => {
      if (a.segments && a.segments.length > 0) {
        groups.push({ kind: 'alternative', index: i + 1, key: `alt:${i + 1}`, segments: a.segments })
      }
    })
  }
  if (routeView.value === 'all' || routeView.value === 'departure') {
    if (r.departure_route && r.departure_route.segments.length > 0) {
      groups.push({ kind: 'departure', key: 'departure', segments: r.departure_route.segments })
    }
  }
  return groups
})

interface RouteCard {
  key: string
  /**
   * 对应地图 `RouteHighlight.key`（业主 2026-10-28）：点这张卡就把它那条路线画成天蓝。
   * 与 `key` 分开是因为卡片的 key 带 path_id（防重复），地图分组只按「第几条」编号。
   */
  highlightKey: string
  kind: RouteHighlight['kind']
  kindName: string
  pathId: string
  eta: number
  segments: string[]
  note: string
  /**
   * 同一份 recommend 的备选条数（Issue IKP5CK）。路线卡用它如实提示
   * 「本 OD 仅 N 条候选（契约要求 ≥2 条备选）」；**不凑等价路线**。
   */
  alternativeCount: number
  /** 引擎声明的 `no_alternative_reason`（只读；未声明 = null） */
  noAlternativeReason: string | null
}

/**
 * 被选中的那条路线（业主 2026-10-28：选中的路线为天蓝，备用路线被选中就变成选中的样子）。
 *
 * 为什么只存一个 key 而不存段号：
 *   · 两条备选可能共享段号（都走同一段主路），按段号存会对不准是「哪一条」被点了；
 *   · key 与 `RouteHighlight.key` 同名字符串（`arrival` / `alt:<序号>` / `departure`），
 *     地图侧直接比对即可，不需要任何反查。
 *
 * 默认选中推荐路线：业主那次的原话是「选中的路线为天蓝色」——第一次进站就有一条亮着的，
 * 才叫「选中的规划路线」；点别的高亮条就换过去，再点同一条则取消（回到「只有规划蓝」）。
 */
const pickedRouteKey = ref<string | null>('arrival')

function pickRoute(key: string): void {
  pickedRouteKey.value = pickedRouteKey.value === key ? null : key
}

/** 右栏路线卡片（与地图用同一份 recommend 数据，不另算） */
const routeCards = computed<RouteCard[]>(() => {
  const r = recommend.value
  if (!r) return []
  const cards: RouteCard[] = []
  // Issue IKP5CK：备选不足的判定依据（`alternatives.length` + 引擎 `no_alternative_reason`）
  // 放进每张卡的数据结构，供路线卡区域如实提示；页面不据此补画等价路线。
  const alternativeCount = r.alternatives.length
  const noAlternativeReason = r.no_alternative_reason ?? null
  if (routeView.value === 'all' || routeView.value === 'arrival') {
    cards.push({
      key: 'arrival',
      highlightKey: 'arrival',
      kind: 'arrival',
      kindName: '推荐路线',
      pathId: r.arrival_route.path_id,
      eta: r.arrival_route.eta_min,
      segments: r.arrival_route.segments,
      note: r.why,
      alternativeCount,
      noAlternativeReason,
    })
  }
  if (routeView.value === 'all' || routeView.value === 'alternative') {
    r.alternatives.forEach((a, i) => {
      cards.push({
        key: `alt-${a.path_id}-${i}`,
        highlightKey: `alt:${i + 1}`,
        kind: 'alternative',
        kindName: `备选 ${i + 1}`,
        pathId: a.path_id,
        eta: a.eta_min,
        segments: a.segments ?? [],
        note: a.reason,
        alternativeCount,
        noAlternativeReason,
      })
    })
  }
  if (routeView.value === 'all' || routeView.value === 'departure') {
    if (r.departure_route) {
      cards.push({
        key: 'departure',
        highlightKey: 'departure',
        kind: 'departure',
        kindName: '离站路线',
        pathId: r.departure_route.path_id,
        eta: r.departure_route.eta_min,
        segments: r.departure_route.segments,
        note: '送完人之后的离站方向（契约 departure_route）',
        alternativeCount,
        noAlternativeReason,
      })
    }
  }
  return cards
})

/** 路线里引用了当前站点包不存在的段号 → 如实提示（不画点不出的段） */
const routeMissing = computed<string[]>(() => {
  const missing = new Set<string>()
  for (const g of routeHighlights.value) {
    for (const id of g.segments) if (!packSegmentIds.value.has(id)) missing.add(id)
  }
  return [...missing]
})

/** 路线来源角标:真接口按响应 data_source 标（真网 / 样例），mock 侧沿用「演示骨架」口径 */
const routeSourceTag = computed<string>(() => {
  const source = recommend.value?.data_source
  if (source === 'engine.routes.real') return '真网算路产物（IKMS11）'
  if (source === 'engine.routes.sample') return '样例产物 · 非本站真网'
  return '演示骨架 · 连通段拼接'
})
/** 路线来源人话（响应 data_source_note；mock 侧为空） */
const routeSourceNote = computed<string>(() => recommend.value?.data_source_note ?? '')
/** 路线说明：真接口只端引擎产物（不代算）；mock 侧保持原「演示骨架」文案 */
const routeWhyLine = computed<string>(() => {
  const source = recommend.value?.data_source
  if (source === 'engine.routes.real' || source === 'engine.routes.sample') {
    return '接口层只端引擎算路产物（真网产物优先、样例产物回退），不代算 ETA；颜色语义：品牌蓝实线 = 推荐 / 当前，中蓝长虚线 = 备选 1，中蓝短虚线 = 备选 2，紫色实线 = 离站，天蓝 = 当前选中的那条。'
  }
  return `演示路线：在 ${packSegmentCount.value} 段真 OSM 路网上按“相邻段连通”拼出的演示序列，不是引擎 K 最短路 + 预约输出，也不是按当前路况重算出来的结果。颜色语义：品牌蓝实线 = 推荐 / 当前，中蓝长虚线 = 备选 1，中蓝短虚线 = 备选 2，紫色实线 = 离站，天蓝 = 当前选中的那条。`
})
/** 路线降级说明（session 未匹配 / 段号命名空间不一致等，来自接口响应 note；无则空）。
 *  session 未匹配已在下方单独用显式警示段落呈现，这里去掉重复的第一句。 */
const routeDegradedNote = computed<string>(() => {
  const note = recommend.value?.note ?? ''
  return note
    .split('；')
    .filter((part) => part.trim() && !part.startsWith('请求的 session_id'))
    .join('；')
})

onMounted(() => {
  void refresh()
  // Issue IKNAUI：先载入引擎 OD 选项（有则默认画第一条完整路线；无则回退演示会话）
  void loadRouteOptions()
  unsubscribe = subscribeTrafficSnapshot(
    () => {
      void refresh()
    },
    (connected) => {
      sseConnected.value = connected
      // 重连成功 → 立刻补拉一次,恢复后的数据不用等下一个心跳
      if (connected) void refresh()
    },
  )
  // IKPFVN E4：首屏默认全国视角；上次选过的站 1.2 s 后自动飞入（用户一碰就取消）
  scheduleAutoFly()
})

onUnmounted(() => {
  unsubscribe?.()
  // 首屏自动飞入 / 到站门控的定时器一起停：它们会往已卸载的页面里写状态
  window.clearTimeout(autoFlyTimer)
  window.clearTimeout(arriveTimer)
})

// ---------- 文案 / 格式化助手 ----------
const CN_NUM: Record<CongestionLevel, string> = { 1: '一', 2: '二', 3: '三', 4: '四' }

function levelName(seg: SegmentRecord): string {
  return isStale(seg) ? UNAVAILABLE.name : (seg.level_name ?? levelStyle(seg).name)
}

function fmt(v: number | undefined | null, digits = 2): string {
  return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—'
}

/** 'YYYY-MM-DD HH:mm:ss' → 'HH:mm:ss'(告警条首次观测时间) */
function hhmmss(stamp: string): string {
  return stamp.length >= 8 ? stamp.slice(-8) : stamp
}

/** 路段名(矩阵 / 排行里的行不带 name,统一从路网取,与地图同源) */
function nameOf(id: string): string {
  return demoSegment(id)?.name ?? id
}

// ---------- KPI 条 ----------
/** 环比文案:负 = 变慢(较上一版慢 x km/h) */
const avgDeltaText = computed(() => {
  const d = overview.value?.avg_speed_delta_kmh
  if (typeof d !== 'number') return '—'
  if (Math.abs(d) < 0.05) return '较上一版持平'
  return `较上一版${d > 0 ? '快' : '慢'} ${Math.abs(d).toFixed(1)} km/h`
})

/** 采纳率:guided_rate(0~1) → 百分数保留一位 */
const adoptText = computed(() => {
  const o = overview.value
  if (!o) return '—'
  return `已引导 ${o.vehicles_guided} · 采纳率 ${(o.guided_rate * 100).toFixed(1)}%`
})

/** 前 3 条生效因素名(按 factor_id 去重,展示口径) */
const topFactors = computed(() => {
  const seen = new Set<string>()
  const out: string[] = []
  for (const f of allFactors.value) {
    if (seen.has(f.factor_id)) continue
    seen.add(f.factor_id)
    out.push(`${f.factor_id} ${f.name}`)
    if (out.length === 3) break
  }
  return out
})

// ---------- 左栏 · 等级分布 + 监控范围 ----------
interface DistRow {
  level: CongestionLevel | 0
  name: string
  count: number
  color: string
}

const dist = computed<DistRow[]>(() => {
  // 纯车流量版（Issue IKNB9G）：按 q_vph 四档统计（数据来自 /segments；缺 q / 陈旧→无流量数据灰档）
  if (isFlow.value) {
    const counts = new Map<number, number>()
    let missing = 0
    for (const seg of segments.value) {
      const band = flowBandOf(seg)
      if (band) counts.set(band.band, (counts.get(band.band) ?? 0) + 1)
      else missing += 1
    }
    return [
      ...FLOW_BANDS.map((band) => ({
        level: band.band as CongestionLevel,
        name: band.name,
        count: counts.get(band.band) ?? 0,
        color: band.color,
      })),
      { level: 0 as const, name: FLOW_UNAVAILABLE_LABEL, count: missing, color: UNAVAILABLE.color },
    ]
  }
  // 决策拥堵版：沿用接口 level_distribution（C-2 既有口径，不重算）
  return (overview.value?.level_distribution ?? []).map((r) => ({
    level: r.level,
    name: r.name,
    count: r.count,
    color: r.level === 0 ? UNAVAILABLE.color : LEVELS[r.level].color,
  }))
})

const distTotal = computed(() => {
  const o = overview.value
  if (o) return o.segment_total
  return dist.value.reduce((acc, r) => acc + r.count, 0)
})

function distWidth(r: DistRow): string {
  const total = dist.value.reduce((acc, x) => acc + x.count, 0)
  if (total <= 0 || r.count <= 0) return '0%'
  return `${(r.count / total) * 100}%`
}

/** 监控范围切换(点分布条 / 点档位图例 / 「全部」) */
function toggleScope(level: CongestionLevel | 0): void {
  scope.value = scope.value === level ? null : level
}

// ---------- 左栏 · 路段列表(四级 = 原序;指数视图 = 按 CI 降序,原 /heat 左栏口径) ----------
interface SegRow {
  seg: SegmentRecord
  color: string
  text: string
  stale: boolean
  name: string
  /** 流量版（IKNB9G）：该段流量档位；null = 无流量数据（拥堵版恒为 null） */
  flowBand: FlowBand | null
  /** 行尾数值文案（流量版 = q 辆/h；拥堵/指数版为空，沿用原模板） */
  valueText: string
}

/** 监控范围过滤(0 = 数据不可用档;流量版 = 四档 band) */
const scoped = computed<SegmentRecord[]>(() => {
  const s = scope.value
  if (s === null) return segments.value
  if (isFlow.value) {
    if (s === 0) return segments.value.filter((x) => !flowBandOf(x))
    return segments.value.filter((x) => flowBandOf(x)?.band === s)
  }
  if (s === 0) return segments.value.filter((x) => isStale(x))
  return segments.value.filter((x) => !isStale(x) && x.level === s)
})

/**
 * 路段列表行：
 *   · 流量版：按 q 四档降序（同档按 q 降序），行尾显示 q、角标显示流量档位（不用 LevelBadge，
 *     避免把流量读成判级）；缺 q / 陈旧 → 灰档「无流量数据」；
 *   · 拥堵版：四级视图按等级降序 / 指数视图按 CI 降序（既有行为，C-2 不改）。
 */
const segRows = computed<SegRow[]>(() => {
  const list = [...scoped.value]
  if (isFlow.value) {
    list.sort(
      (a, b) =>
        (flowBandOf(b)?.band ?? 0) - (flowBandOf(a)?.band ?? 0) ||
        (b.q_vph ?? -1) - (a.q_vph ?? -1),
    )
    return list.map((seg) => {
      const band = flowBandOf(seg)
      const stale = isStale(seg)
      return {
        seg,
        color: band?.color ?? UNAVAILABLE.color,
        text: band?.textColor ?? UNAVAILABLE.text,
        stale: !band,
        name: nameOf(seg.segment_id),
        flowBand: band,
        valueText: band
          ? `${fmt(seg.q_vph, 0)} 辆/h`
          : stale
            ? `数据不可用 · 陈旧 ${seg.data_age_s ?? '—'}s`
            : FLOW_UNAVAILABLE_LABEL,
      }
    })
  }
  if (viewMode.value === 'index') {
    list.sort((a, b) => {
      const av = ciAvailable(a)
      const bv = ciAvailable(b)
      if (av !== bv) return av ? -1 : 1
      return (b.ci ?? 0) - (a.ci ?? 0)
    })
  } else {
    list.sort((a, b) => b.level - a.level || (b.x ?? 0) - (a.x ?? 0))
  }
  return list.map((seg) => {
    const st = levelStyle(seg)
    return {
      seg,
      color: st.color,
      text: st.text,
      stale: isStale(seg),
      name: nameOf(seg.segment_id),
      flowBand: null,
      valueText: '',
    }
  })
})

/** 指数视图的左栏排行(原 /heat 的 SegmentRankTable 口径,含不可用清单) */
const rankRows = computed(() =>
  scoped.value
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

// ---------- 中栏 · 地图 ----------
// 2026-10-14 极简口径只画路段线；Issue IKP5BZ 起补回落客点 / 场区 Marker（唯一真值源 = 前端站点包）——
// 断面仍未上图，路段摘要仍只用跟随鼠标的浮牌（hover-chip）。

/** 选中 chip:路段拥堵 · 摄像头 2 路 · x 0.91 / 0.84(video/twin);video 不可用只显示 twin 并注明 */
const mapChip = computed<string>(() => {
  // 摄像头数按**段号**现算(Issue IKLX5Y),不看有没有快照记录:
  // 没有摄像头的那 16 段**本来就没有记录**,若等记录才拼浮牌,这些段悬停时什么都没有
  // —— 那就答不上"每段可查摄像头数、没有的如实显示 0"。
  const id = selectedId.value
  if (!id) return ''
  // IKNBT2 口径：N 段 = N 摄像头 = N 视频（演示）。源台账 0 路不写「0 路/没摄像头」，
  // 而是「演示摄像头（复用样本视频）」；源台账有的写「源台账 N 路」以示这只是初始映射。
  const camCount = cameraCountOf(id)
  const cam = camCount > 0 ? `源台账摄像头 ${camCount} 路` : '演示摄像头（复用样本视频）'
  // IKOQEJ：方向 / 车道 / 对向 / 贯通（缺值「未标定」，只展示不判级）
  const dir = segDirectionChip.value
  const s = selected.value
  const flow = isFlow.value
  if (flow) {
    // 纯车流量版（IKNB9G）：浮牌只报 q 与流量档位，不写等级/CI（避免把流量读成拥堵结论）
    if (!s) return `${id} 无流量记录 · ${cam} · ${dir}`
    const band = flowBandOf(s)
    const qText = band ? `q ${fmt(s.q_vph, 0)} 辆/h` : FLOW_UNAVAILABLE_LABEL
    return `${s.segment_id} ${band ? band.name : FLOW_UNAVAILABLE_LABEL} · ${qText} · ${cam}（流量版：仅按 q 分档）· ${dir}`
  }
  if (!s) return `${id} 无路况记录 · ${cam} · ${dir}`
  const v = pair.value?.slots.find((x) => x.source === 'video')
  const t = pair.value?.slots.find((x) => x.source === 'twin')
  const vx = v?.record?.x
  const tx = t?.record?.x
  const head = `${s.segment_id} ${levelName(s)} · ${cam} · ${dir}`
  if (v?.available === true && typeof vx === 'number' && typeof tx === 'number') {
    return `${head} · x ${vx} / ${tx}`
  }
  if (typeof tx === 'number') return `${head} · x ${tx}(仅孪生链路)`
  return head
})

// ---------- 右栏 · 双数据源并排(TC-19) ----------
/** 并排表只取四项(饱和度 x / 车速 / 排队长度 / 排队消散),按设计稿口径 */
const DELTA_KEYS = ['x', 'v_kmh', 'L_q_m', 'T_d_min']

const deltaRows = computed(() =>
  (pair.value?.deltas ?? []).filter((d) => DELTA_KEYS.includes(d.key)),
)

const videoAvailable = computed(
  () => pair.value?.slots.find((s) => s.source === 'video')?.available === true,
)

// ---------- 右栏 · 路段详情摘要 + CI ----------
const detailSummary = computed<string>(() => {
  const s = selected.value
  if (!s) return ''
  const parts = [`${s.level >= 1 ? CN_NUM[s.level as CongestionLevel] : '不可用'}级`, levelName(s)]
  parts.push(`更新 ${s.data_age_s ?? '—'}s 前`)
  parts.push(`饱和度 ${fmt(s.x)}`)
  if (s.triggered_by && s.triggered_by.length > 0) parts.push(`触发 ${s.triggered_by.join(' / ')}`)
  return parts.join(' · ')
})

const ciText = computed(() => {
  const r = selected.value
  return r && ciAvailable(r) ? (r.ci as number).toFixed(1) : '不可用'
})

const ciTextColor = computed(() => {
  const r = selected.value
  return r && ciAvailable(r) ? levelStyle(r).text : UNAVAILABLE.color
})

/** 四个 CI 权重(来自 thresholds,不写死) */
const weights = computed(() => thresholds.value?.ci_weights ?? [])
const weightText = computed(() =>
  weights.value.length > 0 ? weights.value.map((w) => w.weight.toFixed(2)).join('/') : '—',
)

/** 各权重要素的「数值」:饱和度 x / 速度比 v/v_f / 排队比 L_q/L_seg / 消散 T_d(缺字段显示「—」) */
function metricText(key: string): string {
  const r = selected.value
  if (!r) return '—'
  const ratio = (a?: number, b?: number): string =>
    typeof a === 'number' && typeof b === 'number' && Number.isFinite(a) && Number.isFinite(b) && b !== 0
      ? (a / b).toFixed(2)
      : '—'
  switch (key) {
    case 'x':
      return typeof r.x === 'number' ? String(r.x) : '—'
    case 'v':
      return ratio(r.v_kmh, r.v_f_kmh)
    case 'k':
      return ratio(r.L_q_m, r.L_seg_m)
    case 'T_d':
      return typeof r.T_d_min === 'number' ? String(r.T_d_min) : '—'
    default:
      return '—'
  }
}

// ---------- 右栏 · 关联告警(原 /heat 右栏) ----------
//
// ⚠️ 等级**不在这里重映射**:本卡把 `segLevelOf` 作为 `levelOf` 回调交给 `AlertList`,
//    由它逐行取当前路段快照(Issue IKLLXG)。以前这里是裸 filter,徽章读告警记录值,
//    与左栏路段列表 / 底部告警条同页两个等级——#77 迁移时把 #75 第④条的重映射漏搬了一处。
//    收成「一个 shared 函数 + 子组件必需回调」后,漏传会被 `vue-tsc` 拦下。
const selectedAlerts = computed(() =>
  alerts.value.filter(
    (a) => a.segment_id === selectedId.value && a.status !== '已闭环' && a.status !== '误报',
  ),
)

// ---------- 底部 · 档位分布(原 /heat 左栏) ----------
const bandRows = computed(() => {
  // 纯车流量版（IKNB9G）：q 四档分布（高→低排列，与拥堵版档位分布同向）
  if (isFlow.value) {
    const counts = new Map<number, number>()
    for (const seg of segments.value) {
      const band = flowBandOf(seg)
      if (band) counts.set(band.band, (counts.get(band.band) ?? 0) + 1)
    }
    const rows = FLOW_BANDS.map((band) => ({
      level: band.band as CongestionLevel,
      name: `${band.name}（${flowRangeLabel(band)}）`,
      count: counts.get(band.band) ?? 0,
      color: band.color,
    }))
    return rows.reverse()
  }
  // 决策拥堵版：沿用既有 CI 四档口径（C-2 不改）
  const avail = segments.value.filter(ciAvailable)
  const out: { level: CongestionLevel; name: string; count: number; color: string }[] = []
  for (let lv = 4; lv >= 1; lv--) {
    const lo = CI_BANDS[lv - 1] ?? 0
    const hi = CI_BANDS[lv] ?? 100
    const count = avail.filter((s) => {
      const ci = s.ci as number
      return lv === 4 ? ci >= lo && ci <= hi : ci >= lo && ci < hi
    }).length
    out.push({
      level: lv as CongestionLevel,
      name: LEVELS[lv as CongestionLevel].name,
      count,
      color: LEVELS[lv as CongestionLevel].color,
    })
  }
  return out
})

const unavailableCount = computed(() =>
  isFlow.value
    ? segments.value.filter((s) => !flowBandOf(s)).length
    : segments.value.filter((s) => !ciAvailable(s)).length,
)

// ---------- 底部 · 热力矩阵：流量版用 q 单桶矩阵（接口只给当前快照；历史桶如实灰） ----------
function flowHeatLabels(): string[] {
  const moment = Date.parse(snapshotTs.value)
  const count = 12
  const bucketSec = 60
  if (Number.isNaN(moment)) return Array.from({ length: count }, () => '—')
  return Array.from({ length: count }, (_, index) =>
    formatClock(new Date(moment - (count - 1 - index) * bucketSec * 1000).toISOString()),
  )
}

const flowHeat = computed<HeatMatrix | null>(() => {
  if (!isFlow.value) return null
  const labels = heat.value?.labels?.length ? heat.value.labels : flowHeatLabels()
  const rows = segments.value.map((seg) => {
    const q = flowBandOf(seg) ? (seg.q_vph as number) : null
    return {
      segment_id: seg.segment_id,
      name: nameOf(seg.segment_id),
      buckets: [...Array(Math.max(0, labels.length - 1)).fill(null), q] as (number | null)[],
    }
  })
  return {
    ts: heat.value?.ts ?? snapshotTs.value,
    is_simulated: true,
    bucket_sec: heat.value?.bucket_sec ?? 60,
    buckets: labels.length,
    labels,
    rows,
  }
})

// ---------- 底部 · 告警条 ----------
const unclosed = computed(() =>
  alerts.value.filter((a) => a.status === '待认领' || a.status === '处置中'),
)
const unclaimedCount = computed(() => alerts.value.filter((a) => a.status === '待认领').length)
const processingCount = computed(() => alerts.value.filter((a) => a.status === '处置中').length)

/** 第一条未闭环告警(默认取列表序=待认领在前) */
const firstAlert = computed<TrafficAlert | null>(() => unclosed.value[0] ?? null)

/**
 * 告警等级取**当前路段快照**(与左栏 / 地图 / 右栏同一口径)。
 * 告警自带的 `level` 是派生时的记录值,预置剧本与快照基线不同步时会是旧值——
 * 直接用会与同一页的路段列表自相矛盾。
 *
 * ⚠️ 实现收敛到 `shared/traffic.ts` 的 `alertLevelOf`(Issue IKLLXG):
 *    本页的右栏关联告警 / 底部告警条**共用这一个函数**,不再各写一份。
 */
function segLevelOf(a: TrafficAlert): CongestionLevel {
  return alertLevelOf(a, findSegment)
}

/** 快照查路段的唯一口径(本页共用) */
function findSegment(id: string): SegmentRecord | undefined {
  return segments.value.find((s) => s.segment_id === id)
}

/** 告警摘要里的 x:从该路段快照取(不编造) */
const firstAlertX = computed<string>(() => {
  const a = firstAlert.value
  if (!a) return '—'
  return fmt(findSegment(a.segment_id)?.x)
})

// ---------- 交互 ----------
function onSelect(id: string): void {
  selectedId.value = id
}

function gotoDecision(): void {
  // 带段号深链：决策页「决策可视化」按该段展示（与右栏「查看完整决策过程」同一口径）
  const segment = selectedId.value
  void router.push(segment ? { path: '/decision', query: { segment } } : '/decision')
}

/** 大屏下令成功（下发 / 回写）→ 重拉快照：告警状态、回执留痕与决策页保持同一后端状态 */
function onCommandChanged(): void {
  void refresh()
}
</script>

<template>
  <AppShell
    active="dashboard"
    :station="stationName"
    :ts="snapshotTs"
    v-model:sourceMode="sourceMode"
    title=""
  >
    <div v-if="failedPanels.length > 0" class="stale-bar" role="status">
      ⚠ 本次刷新未取到:{{ failedPanels.join(' / ') }} —— 这些面板显示的是上一版数据或空态(灰色「数据不可用」),请勿据此判断当前态势。
      <button class="td-btn sm" type="button" @click="refresh">立即重试</button>
    </div>
    <div v-if="!sseConnected" class="stale-bar" role="status">
      ⚠ 实时刷新通道(SSE)未连接 —— 页面不会自动刷新,正在自动重连;数据可能已陈旧。
      <button class="td-btn sm" type="button" @click="refresh">立即刷新</button>
    </div>

    <!-- 应急态（TC-10，手册 §11.1(3)）：顶部红条 + 固定措辞，优先级高于一切推荐。
         口径：**只加提示，不删正文** —— 下面的 KPI / 地图 / 路段 / 车辆照常显示；
         被停掉的只有「推荐路线」那一块的引导（那张卡自己会换成应急卡）。 -->
    <div v-if="emergencyActive" class="emergency-bar" role="alert" aria-live="assertive">
      <span class="emergency-tag">应急态</span>
      <b class="emergency-msg">{{ emergency?.message ?? '请服从现场指挥' }}</b>
      <span class="emergency-sub">
        已停下路线引导（优先级高于一切推荐）<template v-if="emergencySegmentText">；影响路段
          {{ emergencySegmentText }}</template
        ><template v-if="emergency?.level_source === 'pending_perception_recompute'">
          ；判级待重算，此处不展示等级</template
        >。
      </span>
    </div>

    <!-- 切站缓存提示（Issue IKPFR4）：缓存数据必须有标识，不得冒充最新。
         有缓存 = 首屏已秒开，这里只说明"这是缓存、正在刷新"；没缓存才亮下面的骨架条。 -->
    <div v-if="cacheNote" class="cache-bar" role="status">
      缓存 · 刷新中 —— {{ cacheNote }}
    </div>
    <div v-if="switching" class="switch-bar" role="status" aria-live="polite">
      <span class="switch-spinner" aria-hidden="true" />
      正在加载「{{ stationName }}」的首屏快照（该站暂无内存缓存：首次访问 / 预热尚未完成）—— 数据到达即渲染，不刷新整页。
      <span class="switch-skeleton" aria-hidden="true"><i /><i /><i /></span>
    </div>

    <!-- KPI 条(取代页头) -->
    <div class="td-card kpi-bar">
      <div class="kpi-cell">
        <div class="kpi-label">全网平均车速</div>
        <div class="kpi-value">{{ fmt(overview?.avg_speed_kmh, 1) }}<span class="kpi-unit">km/h</span></div>
        <div class="kpi-sub">{{ avgDeltaText }}</div>
      </div>
      <div class="kpi-cell">
        <div class="kpi-label">最堵路段</div>
        <div class="kpi-value td-mono">{{ overview?.worst_segment?.segment_id ?? '—' }}</div>
        <div class="kpi-sub">
          <template v-if="overview?.worst_segment">
            <LevelBadge :level="overview.worst_segment.level" />
            <span class="kpi-sep">·</span>{{ overview.worst_segment.name }}
            <span class="kpi-sep">·</span>x {{ fmt(overview.worst_segment.x) }}
          </template>
          <template v-else>—</template>
        </div>
      </div>
      <div class="kpi-cell">
        <div class="kpi-label">站前在途车辆</div>
        <div class="kpi-value">{{ overview?.vehicles_inbound ?? '—' }}<span class="kpi-unit">辆</span></div>
        <div class="kpi-sub">{{ adoptText }}</div>
      </div>
      <div class="kpi-cell">
        <div class="kpi-label">当前生效因素</div>
        <div class="kpi-value">{{ overview?.active_factors ?? '—' }}<span class="kpi-unit">项</span></div>
        <div class="kpi-sub">
          <template v-if="topFactors.length > 0">{{ topFactors.join(' · ') }}</template>
          <template v-else>无生效因素</template>
        </div>
      </div>
    </div>

    <!-- 颜色模式切换（Issue IKNB9G，业主 2026-10-18）：决策拥堵版 ↔ 纯车流量版 -->
    <div class="color-mode-bar" role="group" aria-label="颜色模式切换">
      <span class="cm-title">颜色模式</span>
      <button
        type="button"
        class="cm-item"
        :class="{ on: !isFlow }"
        :aria-pressed="!isFlow"
        @click="setColorMode('congestion')"
      >
        决策拥堵版
      </button>
      <button
        type="button"
        class="cm-item flow"
        :class="{ on: isFlow }"
        :aria-pressed="isFlow"
        @click="setColorMode('flow')"
      >
        纯车流量版
      </button>
      <span v-if="isFlow" class="cm-note">
        <b>{{ FLOW_MODE_LABEL }}</b> · {{ FLOW_MODE_NOTE }} · {{ FLOW_COLOR_NOTE }}
        · 仅颜色 / 列表 / 图例 / 热力随模式切换；KPI 与右栏决策信息仍为决策口径
      </span>
      <span v-else class="cm-note">
        决策拥堵版：按接口 level 四级判级配色（判级来自感知层，前端不重算）
      </span>
    </div>

    <!-- 主体三栏 · 横向可拖(Issue #81)。
         ElSplitter 的每个 panel 后面自带一条 bar,两条 bar 把三栏隔开;
         bar 宽度为 0(只有 16px dragger 绝对定位),栏间距由 .spl-gap 补回 10px。
         中栏不传 size → 弹性伸缩(默认仍是弹性栏,口径红线第 3 条)。 -->
    <div class="td-body">
      <el-splitter
        class="el-splitter td-splitter"
        :class="{ 'is-national': mapScope === 'national', 'is-fold-left': colLeftCollapsed, 'is-fold-right': colRightCollapsed }"
        @resize-end="saveColMem"
        @mousedown="onBarMouseDown"
      >
        <!-- `v-model:size` 而不是 `:size`:单向绑定不会把 ElSplitter 拖出来的 px 宽度
             回写到 colLeft/colRight,那样 @resize-end 存的一直是默认值,记忆功能等于没有。
             两个 ref 都是 `number | string`(元素自身声明 `size: { type: [String, Number] }`)。 -->
        <!-- ⚠️ `:min` 在收起态要撤成 0：ElSplitter 会用 min 钳住 size，
             不撤的话 colLeft=0 会被弹回 220，收起按钮看起来「没反应」（踩过一次）。 -->
        <el-splitter-panel v-model:size="colLeft" :min="colLeftCollapsed ? 0 : COL_MIN_LEFT">
          <!-- 左栏 · 选择监控。
               IKPFVN：全国视角下左栏整体收起（v-if 卸掉内容 + `is-national` 把面板宽压到 0），
               地图占满内容区；站区视角再滑入。
               业主 2026-10-28：「中间的图都被挤到特别小」→ 左栏顶部加「‹ 收起」按钮，
               收起后左栏宽度归零、地图吃掉腾出来的宽度（见 script 内 COL_RECALL_LEFT）。 -->
          <div v-if="mapScope === 'station'" class="td-col col-left">
            <div class="col-head">
              <span class="col-head-title">路段监控</span>
              <button
                type="button"
                class="col-fold"
                aria-label="收起左栏（地图变宽）"
                title="收起左栏：地图拿走这块宽度；收起后地图左上角出现「› 展开」"
                @click="setColCollapsed('left', true)"
              >
                ‹ 收起
              </button>
            </div>
            <section class="td-card">
              <div class="td-card-head">
                选择监控<span class="td-head-tag">{{ distTotal }} 个路段</span>
              </div>
              <div class="td-card-body">
                <div class="td-seg view-seg" role="group" aria-label="视图切换">
                  <span
                    class="td-seg-item"
                    :class="{ on: viewMode === 'level' }"
                    role="button"
                    :aria-pressed="viewMode === 'level'"
                    @click="viewMode = 'level'"
                  >
                    {{ isFlow ? '流量四档' : '四级视图' }}
                  </span>
                  <span
                    class="td-seg-item"
                    :class="{ on: viewMode === 'index', disabled: isFlow }"
                    role="button"
                    :aria-pressed="viewMode === 'index'"
                    :aria-disabled="isFlow"
                    :title="isFlow ? '流量版不提供 CI 视图（CI 是决策口径）；切回决策拥堵版可用' : ''"
                    @click="!isFlow && (viewMode = 'index')"
                  >
                    拥挤指数视图
                  </span>
                </div>
                <p v-if="isFlow" class="note">流量版不提供 CI 视图（CI 是决策口径）；切回「决策拥堵版」可用，C-2 既有能力未删。</p>
                <div class="dist-bar" :style="{ background: TD.bgSecondary }">
                  <span
                    v-for="r in dist"
                    :key="`d-${r.level}`"
                    class="dist-seg"
                    :class="{ dim: scope !== null && scope !== r.level }"
                    :style="{ width: distWidth(r), background: r.color }"
                    role="button"
                    :title="`只看 ${r.name}(${r.count} 个路段)`"
                    @click="toggleScope(r.level)"
                  />
                </div>
                <div class="dist-legend">
                  <span
                    v-for="r in dist"
                    :key="`lg-${r.level}`"
                    class="dist-item"
                    :class="{ on: scope === r.level }"
                    role="button"
                    :aria-pressed="scope === r.level"
                    @click="toggleScope(r.level)"
                  >
                    <span v-if="isFlow" class="flow-swatch" :style="{ background: r.color }" />
                    <LevelBadge v-else :level="r.level === 0 ? 1 : r.level" :stale="r.level === 0" />
                    <span class="td-num dist-count">{{ r.count }}</span>
                  </span>
                  <span class="dist-item all" :class="{ on: scope === null }" role="button" @click="scope = null">
                    全部
                  </span>
                </div>
                <p v-if="viewMode === 'index'" class="note">{{ CI_DISCLAIMER }}</p>
              </div>
            </section>

            <!-- 四级视图:路段监测列表;指数视图:按 CI 降序排行(原 /heat 左栏) -->
            <section class="td-card seg-card">
              <div class="td-card-head">
                路段监测
                <span class="td-head-tag">{{ isFlow ? '按车流量降序' : viewMode === 'index' ? '按 CI 降序' : '按等级排序' }}</span>
              </div>
              <div class="td-card-body flush seg-body">
                <div class="td-scroll seg-list">
                  <SegmentRankTable
                    v-if="viewMode === 'index'"
                    :items="rankRows"
                    :selected-id="selectedId"
                    @select="onSelect"
                  />
                  <template v-else>
                    <div
                      v-for="row in segRows"
                      :key="row.seg.segment_id"
                      class="td-row"
                      :class="{ on: row.seg.segment_id === selectedId }"
                      role="button"
                      :aria-pressed="row.seg.segment_id === selectedId"
                      @click="onSelect(row.seg.segment_id)"
                    >
                      <span class="lvl-bar" :style="{ background: row.color }" />
                      <span class="seg-meta">
                        <span class="seg-name">{{ row.name }}</span>
                        <span class="seg-id td-mono">{{ row.seg.segment_id }}</span>
                      </span>
                      <template v-if="isFlow">
                        <span class="seg-value td-num" :style="{ color: row.stale ? UNAVAILABLE.text : row.text }">
                          {{ row.valueText }}
                        </span>
                        <span
                          class="flow-badge"
                          :class="{ off: !row.flowBand }"
                          :style="row.flowBand ? { background: row.flowBand.color, color: row.flowBand.textColor } : {}"
                        >
                          {{ row.flowBand ? row.flowBand.name : FLOW_UNAVAILABLE_LABEL }}
                        </span>
                      </template>
                      <template v-else>
                        <span class="seg-value td-num" :style="{ color: row.stale ? UNAVAILABLE.text : row.text }">
                          <template v-if="row.stale">数据不可用 · 陈旧 {{ row.seg.data_age_s ?? '—' }}s</template>
                          <template v-else>x {{ fmt(row.seg.x) }}</template>
                        </span>
                        <LevelBadge :level="row.seg.level" :stale="row.stale" />
                      </template>
                    </div>
                    <p v-if="segRows.length === 0" class="empty">
                      {{
                        switching
                          ? '正在加载该站首屏快照…'
                          : scope === null
                            ? '快照为空(接口层未起?)'
                            : '该范围当前没有路段'
                      }}
                    </p>
                  </template>
                </div>
              </div>
            </section>
            </div>
        </el-splitter-panel>

        <el-splitter-panel :min="COL_MIN_MID">
          <!-- 中栏 · 全路段状态 -->
          <div class="td-col col-mid">
            <section class="td-card map-card">
              <div class="map-toolbar">
                <div class="map-toolbar-left">
                  <span class="map-title">{{ mapScope === 'national' ? '全国地图' : '全路段状态' }}</span>
                  <span class="map-tag">{{ basemapTag }}</span>
                  <!-- 业主 2026-10-28：左右栏各自有「收起」键，收起后地图占满腾出的宽度。
                       展开键放这里，跟标题同一行，一眼能找到，也在视线落点上。 -->
                  <button
                    v-if="mapScope === 'station' && colLeftCollapsed"
                    type="button"
                    class="map-fold-btn"
                    aria-label="展开左栏"
                    title="展开左栏（恢复原来的栏宽）"
                    @click="setColCollapsed('left', false)"
                  >
                    › 展开左栏
                  </button>
                </div>
                <!-- 路网版本切换（IKMDKY 子单①；IKP5D3 起 Z21 旧包已删，只剩 Z / GZ） -->
                <div class="map-toolbar-right">
                  <button
                    v-if="mapScope === 'station' && colRightCollapsed"
                    type="button"
                    class="map-fold-btn"
                    aria-label="展开右栏"
                    title="展开右栏（恢复原来的栏宽）"
                    @click="setColCollapsed('right', false)"
                  >
                    ‹ 展开右栏
                  </button>
                  <!-- IKPFVN E2：「← 全国」与站点按钮走同一条链路（`pickStation` / `enterNational`），
                       不刷新、不重建地图，只换视角与镜头。 -->
                  <button
                    v-if="mapScope === 'station'"
                    type="button"
                    class="map-back-btn"
                    title="退回全国视角（地图缩远到中国范围，站点 pin 重新出现）"
                    @click="enterNational"
                  >
                    ← 全国
                  </button>
                  <span
                    class="pack-switch"
                    role="group"
                    aria-label="已接入车站（切站：缩远 → 移动 → 放大）"
                  >
                    <button
                      v-for="p in packChoices"
                      :key="p.key"
                      type="button"
                      class="pack-switch-item"
                      :class="{ on: p.key === currentPackKey && mapScope === 'station' }"
                      :aria-pressed="p.key === currentPackKey && mapScope === 'station'"
                      @click="pickStation(p.key)"
                    >
                      {{ p.name }}
                    </button>
                  </span>
                  <!-- 方向箭头开关（业主 2026-10-23：地图上直接给一个键，不用进「设置」翻）。
                       与顶栏「设置 → 方向标记」共用同一状态（directionsVisible）、同落 localStorage。
                       背景：箭头按比例尺档显隐（200 m 以远不画），业主反馈「每次打开可能没有箭头」
                       ——加此键后可以一眼确认是「关了」还是「在远档」，也能手动强制显示状态。 -->
                  <span class="pack-switch" role="group" aria-label="方向箭头">
                    <button
                      type="button"
                      class="pack-switch-item"
                      :class="{ on: directionsVisible }"
                      role="switch"
                      :aria-checked="directionsVisible"
                      :title="
                        directionsVisible
                          ? '方向箭头：开（150 m 及以内显示，200 m 以远自动不画）；点击全部隐藏'
                          : '方向箭头：关（一支都不画）；点击恢复（放大到 200 m 以内即可见）'
                      "
                      @click="setDirectionsVisible(!directionsVisible)"
                    >
                      箭头 {{ directionsVisible ? '开' : '关' }}
                    </button>
                  </span>
                  <!-- 摄像头图钉开关（业主 2026-10-25：图钉全量 61/708 后，与「箭头」键同款给一键整体隐藏）。
                       只关"图钉层"——台账、右栏路段卡、监控墙的数据与画面不受影响；同落 localStorage。 -->
                  <span class="pack-switch" role="group" aria-label="摄像头图钉">
                    <button
                      type="button"
                      class="pack-switch-item"
                      :class="{ on: camerasVisible }"
                      role="switch"
                      :aria-checked="camerasVisible"
                      :title="
                        camerasVisible
                          ? '摄像头图钉：开（全量 N 段 N 路上图）；点击整体隐藏'
                          : '摄像头图钉：关（图上一支不画）；点击恢复（台账与路段卡不受影响）'
                      "
                      @click="setCamerasVisible(!camerasVisible)"
                    >
                      摄像头 {{ camerasVisible ? '开' : '关' }}
                    </button>
                  </span>
                  <!-- 凸显路线开关（Issue IKP5CK）：开 = 非路线段压灰、关 = 满图等级色。
                       默认开，落 localStorage；状态在图上与图例里都能看到。 -->
                  <span class="pack-switch" role="group" aria-label="凸显路线">
                    <button
                      type="button"
                      class="pack-switch-item"
                      :class="{ on: routeEmphasisEnabled }"
                      role="switch"
                      :aria-checked="routeEmphasisEnabled"
                      :title="
                        routeEmphasisEnabled
                          ? '凸显路线：开（非路线段中性灰细线，不按等级上色）；点击恢复满图等级色'
                          : '凸显路线：关（满图等级色 + 路线叠加）；点击压灰非路线段'
                      "
                      @click="setRouteEmphasisEnabled(!routeEmphasisEnabled)"
                    >
                      凸显路线 {{ routeEmphasisEnabled ? '开' : '关' }}
                    </button>
                  </span>
                </div>
              </div>
              <div class="td-card-body flush map-body">
                <MapLibreViewer
                  :segments="segments"
                  :vehicles="vehicles"
                  :selected-id="selectedId"
                  :routes="routeHighlights"
                  :picked-route-key="pickedRouteKey"
                  :route-start="routeStartMarker"
                  :route-end="routeEndMarker"
                  :mode="viewMode"
                  :color-mode="colorMode"
                  :map-mode="mapScope"
                  :ts="snapshotTs"
                  :hover-chip="mapChip"
                  :legend="true"
                  @select="onSelect"
                  @switch-station="pickStation"
                  @arrived="onMotionArrived"
                />
              </div>
              <div class="map-caption">
                {{ mapCaption }}
              </div>
            </section>
          </div>
        </el-splitter-panel>

        <el-splitter-panel v-model:size="colRight" :min="colRightCollapsed ? 0 : COL_MIN_RIGHT">
          <!-- 右栏 · 路段信息（IKPFVN：全国视角下同样收起，见左栏注释） -->
          <!-- 收起后这里只剩一条 0 宽的面板，展开键移到地图工具条（见中栏 `.map-fold-*`） -->
          <div v-if="mapScope === 'station'" class="td-col col-right td-scroll">
            <div class="col-head">
              <span class="col-head-title">路段信息</span>
              <button
                type="button"
                class="col-fold"
                aria-label="收起右栏（地图变宽）"
                title="收起右栏：地图拿走这块宽度；收起后地图右上角出现「‹ 展开」"
                @click="setColCollapsed('right', true)"
              >
                收起 ›
              </button>
            </div>
        <!-- 推荐路线（Issue IKMF1W）：三态切换 + 来源标注；接口不可达时不画路线、不编造假路线 -->
        <section class="td-card route-card">
          <div class="td-card-head">
            {{ emergencyActive ? '路线引导' : '推荐路线' }}
            <span class="td-head-tag">{{ emergencyActive ? '应急态 · 已停下' : routeSourceTag }}</span>
          </div>
          <!-- 应急态（TC-10，手册 §11.1(3)）：**只撤这一块的引导**，换成固定措辞。
               注意这是替换「推荐」而非删正文：右边路段信息、地图、KPI 一律照常。 -->
          <div v-if="emergencyActive" class="td-card-body emergency-card" role="alert">
            <div class="em-title">{{ emergency?.message ?? '请服从现场指挥' }}</div>
            <p class="em-line">
              应急状态下<b>停止路线引导</b>（优先级高于一切推荐），请以现场指挥为准。
            </p>
            <p v-if="emergencySegmentText" class="em-line">
              影响路段：<b class="td-mono">{{ emergencySegmentText }}</b>
            </p>
            <p v-if="emergency?.level !== null && emergency?.level !== undefined" class="em-line">
              等级：<b>{{ emergency.level }} 级</b>（由感知层判定，本页不重算）
            </p>
            <p v-else-if="emergency?.level_source === 'pending_perception_recompute'" class="em-line">
              等级：<b>待重算</b> —— 事故/管制已登记，等感知层重算后才出等级；此处<b>不填任何档位</b>。
            </p>
            <p v-if="emergency?.factors?.length" class="em-line">
              已登记因素：<b>{{ emergencyFactorText }}</b>
            </p>
            <p class="em-src">{{ emergency?.note ?? '' }}</p>
          </div>
          <div v-else class="td-card-body">
            <!-- 整条路线规划（Issue IKNAUI）：引擎产物 OD/session 选择 → 完整路线 + 进场/落客/离站全程摘要 -->
            <div class="route-plan">
              <div class="route-plan-head">
                整条路线规划
                <span class="td-head-tag">引擎路线产物</span>
                <span class="route-badge">演示数据（模拟）</span>
              </div>
              <p v-if="routeOptionsLoading" class="route-hint">正在读取引擎路线选项…</p>
              <template v-else-if="routeOptions && routeOptions.options.length > 0">
                <select
                  v-model="selectedSession"
                  class="route-select"
                  aria-label="选择引擎 OD / 行程"
                  @change="onRouteSessionChange"
                >
                  <option
                    v-for="option in routeOptions.options"
                    :key="option.session_id || option.request_id || ''"
                    :value="option.session_id || ''"
                  >
                    {{ option.od_id ?? 'OD' }} · 起点 {{ option.location.segment_id ?? '—' }}
                    <template v-if="option.location.segment_id">（{{ nameOf(option.location.segment_id) }}）</template>
                    · 到达 {{ fmtEta(option.arrival_route?.eta_min) }} min
                  </option>
                </select>
                <div v-if="tripSummary" class="trip-summary">
                  <div class="trip-line">
                    <b>进场</b>：起点 {{ tripSummary.start }} · 推荐路径 {{ tripSummary.arrivalSegments }} 段 ·
                    ETA {{ tripSummary.arrivalEta }} min
                  </div>
                  <div class="trip-segs td-mono">{{ tripSummary.arrivalPath || '—' }}</div>
                  <div class="trip-line">
                    <b>落客</b>：{{ tripSummary.dropoff ?? '引擎产物未给落客点（如实空窗）' }} · 备选
                    {{ tripSummary.alternatives }} 条
                  </div>
                  <div class="trip-line">
                    <b>离站</b>：
                    <template v-if="tripSummary.departureSegments > 0">
                      {{ tripSummary.departureSegments }} 段 · ETA {{ tripSummary.departureEta }} min
                    </template>
                    <template v-else>引擎产物未给离站路线（如实空窗）</template>
                  </div>
                  <div v-if="tripSummary.departurePath" class="trip-segs td-mono">
                    {{ tripSummary.departurePath }}
                  </div>
                  <p class="route-source">
                    来源 {{ tripSummary.source }} · 段号命名空间
                    {{ (routeOptions.segment_namespaces || []).join(' / ') || '—' }} ·
                    ETA / 路径原样透传，接口层与前端均不代算
                  </p>
                </div>
              </template>
              <p v-else-if="routeOptionsError" class="route-hint">
                <template v-if="USE_MOCK">
                  mock 模式无整条路线选项端点（/route/options）：下方为演示会话路线，不冒充引擎 OD。
                </template>
                <template v-else>引擎路线选项不可用：{{ routeOptionsError }}</template>
              </p>
              <p v-else class="route-hint">引擎产物无 OD / session 选项：不编造路线选择。</p>
            </div>
            <p v-if="recommendLoading" class="route-hint">正在读取推荐快照…</p>
            <p v-else-if="recommendError" class="route-hint warn">{{ recommendError }}</p>
            <template v-else-if="recommend">
              <div class="route-tabs">
                <button
                  v-for="t in ROUTE_VIEWS"
                  :key="t.key"
                  type="button"
                  class="route-tab"
                  :class="{ on: routeView === t.key }"
                  @click="routeView = t.key"
                >
                  {{ t.name }}
                </button>
              </div>
              <div class="route-meta">
                <span class="route-badge">演示数据（模拟）</span>
                <span>路线来自引擎算路产物 · 本页不重算</span>
              </div>
              <!-- IKP5C6：起点 / 终点确认（起点=孪生真值，不是用户定位；终点优先 dropoff_point，空窗给原因 + 末段兜底） -->
              <div class="start-end">
                <div class="se-block">
                  <div class="se-head">
                    本次起点
                    <span class="se-tag" :class="{ warn: !startConfirmed }">
                      {{ startConfirmed ? '已确认' : '未确认' }}
                    </span>
                    <span v-if="locateLoading" class="se-tag">读取定位中</span>
                  </div>
                  <div class="se-line">
                    段号 <b class="td-mono">{{ currentStart?.segment_id ?? '—' }}</b> · 路段名 {{ startName }}
                  </div>
                  <div class="se-line">
                    位置类型
                    <b>{{ startBoundarySection ? `外围边界断面 ${startBoundarySection.point_id}` : '路网内部段' }}</b>
                    <span class="se-note">（演示口径：外围入口段 → 停车场落客点）</span>
                  </div>
                  <div class="se-line">
                    来源 {{ startSourceLabel }} · offset {{ offsetText }} m · match_confidence
                    {{ confidenceText }}
                  </div>
                  <p v-if="!startConfirmed" class="se-note">
                    起点未确认（按{{ startSourceLabel }}演示）：点「以这里为起点」表示认可此起点后再看路线。
                  </p>
                  <p v-if="confidenceLow" class="se-warn">
                    定位不稳定（match_confidence &lt; 0.6）：可改用下方手动选起点。
                  </p>
                  <p v-if="locateError" class="se-note">{{ locateError }}</p>
                  <div class="se-actions">
                    <button
                      type="button"
                      class="se-btn"
                      :disabled="!currentStart"
                      @click="confirmStart"
                    >
                      以这里为起点
                    </button>
                    <select
                      v-model="manualStartId"
                      class="route-select se-select"
                      aria-label="手动选择起点路段"
                    >
                      <option value="">手动选起点（兜底）…</option>
                      <option v-for="seg in packSegments" :key="seg.segment_id" :value="seg.segment_id">
                        {{ seg.segment_id }} · {{ seg.name }}
                      </option>
                    </select>
                    <button
                      type="button"
                      class="se-btn"
                      :disabled="!manualStartId"
                      @click="applyManualStart"
                    >
                      用这段
                    </button>
                  </div>
                </div>
                <div class="se-block">
                  <div class="se-head">本次终点 <span class="se-tag">落客点</span></div>
                  <template v-if="tripEnd?.drop">
                    <div class="se-line">
                      点位 <b class="td-mono">{{ tripEnd.drop }}</b>
                      <template v-if="tripEnd.pointName"> · {{ tripEnd.pointName }}</template>
                    </div>
                    <div class="se-line">
                      所在末段 <b class="td-mono">{{ tripEnd.last ?? '—' }}</b> · {{ tripEnd.lastName }}
                    </div>
                  </template>
                  <template v-else>
                    <div class="se-line">落客点位：引擎产物未给（如实空窗）</div>
                    <p v-if="tripEnd?.reason" class="se-note">原因：{{ tripEnd.reason }}</p>
                    <p v-else class="se-note">
                      原因：引擎 why 未附说明（点位表未登记真网段号，补齐归 IKMHMX）。
                    </p>
                    <div class="se-line">
                      替代信息：终点所在末段 <b class="td-mono">{{ tripEnd?.last ?? '—' }}</b> ·
                      {{ tripEnd?.lastName ?? '—' }}
                    </div>
                  </template>
                </div>
              </div>
              <p v-if="routeSourceNote" class="route-source">{{ routeSourceNote }}</p>
              <div
                v-for="c in routeCards"
                :key="c.key"
                class="route-item"
                :class="[c.kind, { picked: pickedRouteKey === c.highlightKey }]"
                role="button"
                tabindex="0"
                :aria-pressed="pickedRouteKey === c.highlightKey"
                :title="pickedRouteKey === c.highlightKey ? '再点一次取消选中（全部按规划蓝 / 备选中蓝画）' : '点为选中路线（地图上画成天蓝，压在其它路线之上）'"
                @click="pickRoute(c.highlightKey)"
                @keydown.enter.prevent="pickRoute(c.highlightKey)"
                @keydown.space.prevent="pickRoute(c.highlightKey)"
              >
                <div class="route-item-head">
                  <span class="route-kind">{{ c.kindName }}</span>
                  <span v-if="pickedRouteKey === c.highlightKey" class="route-picked-tag">已选中</span>
                  <span class="route-eta td-num">{{ c.eta }} min</span>
                </div>
                <div class="route-segs td-mono">{{ c.segments.join(' → ') || '—' }}</div>
                <div class="route-note">{{ c.note }}</div>
              </div>
              <!-- IKP5CK：备选不足如实说明（契约要求 ≥2 条；不凑等价路线，不空白） -->
              <p v-if="recommend.alternatives.length < 2" class="route-hint warn">
                本 OD 仅 {{ recommend.alternatives.length }} 条候选（契约要求 ≥2 条备选）<template
                  v-if="recommend.no_alternative_reason"
                >：{{ recommend.no_alternative_reason }}</template>；不为凑数补画等价路线。
              </p>
              <p v-if="routeMissing.length" class="route-hint warn">
                路线里有 {{ routeMissing.length }} 段不在当前站点包（{{ routeMissing.join(', ') }}），这些段不会被画出；不补造数据。
              </p>
              <p v-if="recommend.session_matched === false" class="route-hint warn">
                请求的 session_id（{{ recommend.requested_session_id }}）不在引擎产物里：当前端出的是产物首条请求的演示路线，
                <b>非该车行程</b>；不伪装成匹配结果。
              </p>
              <p class="route-why">{{ routeWhyLine }}</p>
              <p v-if="routeDegradedNote" class="route-hint">{{ routeDegradedNote }}</p>
            </template>
            <p v-else class="route-hint">无推荐数据：保持不画路线（不编造演示路线）</p>
          </div>
        </section>
        <section class="td-card">
          <div class="td-card-head">
            路段信息<span class="td-head-tag td-mono">{{ selected?.segment_id ?? selectedId ?? '—' }}</span>
          </div>
          <div class="td-card-body">
            <template v-if="selectedId">
              <div class="d-title">
                <span class="d-name">{{ selectedName }}</span>
                <LevelBadge v-if="selected" :level="selected.level" :stale="isStale(selected)" />
                <span v-else class="td-chip">无路况记录 · 数据不可用</span>
              </div>
              <div class="d-summary">
                {{
                  selected
                    ? detailSummary
                    : '该路段在当前快照里没有运行指标（段号未被感知 / 孪生产物覆盖）——不显示等级，按数据不可用灰档处理（TC-11）。'
                }}
              </div>

              <!-- IKOQEJ · 方向 / 车道 / 对向 / 贯通（只读站点包 enriched 生成字段；
                   非契约、不参与判级；缺值如实「—/未标定」，贯通性待核只提示不改网络） -->
              <div class="dir-block">
                <div class="sec-head">
                  方向 / 车道 / 贯通<span class="sub-tag">{{ segDirectionLabel }}</span>
                  <span class="td-chip" :class="{ warn: segContinuity.state === 'pending' }">
                    {{ segContinuity.label }}
                  </span>
                </div>
                <div class="dir-kv">
                  <span class="k">方向</span>
                  <span class="v">
                    <b>{{ segDirectionLabel }}</b>
                    <span class="dir-src">来源 {{ segDirectionSource }}</span>
                  </span>
                </div>
                <div class="dir-kv">
                  <span class="k">车道（前 / 后 / 共）</span>
                  <span class="v">
                    <span class="td-mono">{{ segLanes.text }}</span>
                    <span class="dir-src">来源 {{ segLanes.source }}</span>
                  </span>
                </div>
                <div class="dir-kv">
                  <span class="k">对向段</span>
                  <span class="v">
                    <button
                      v-if="segOpposite && segOppositePresent"
                      type="button"
                      class="dir-link"
                      :title="`跳转到对向段 ${segOpposite}`"
                      @click="onSelect(segOpposite)"
                    >
                      {{ segOpposite }} ↗
                    </button>
                    <template v-else-if="segOpposite">
                      {{ segOpposite }}
                      <span class="dir-src">不在当前路网（前端站点包待同步，暂不可跳转）</span>
                    </template>
                    <span v-else>—</span>
                    <span class="dir-src">enriched 推导</span>
                  </span>
                </div>
                <div class="dir-kv">
                  <span class="k">贯通性</span>
                  <span class="v">
                    <span class="dir-cont" :class="segContinuity.tone">{{ segContinuity.label }}</span>
                    <span class="dir-detail">{{ segContinuity.detail }}</span>
                  </span>
                </div>
                <p class="dir-note">
                  方向 / 车道 / 对向 / 贯通来自站点包<b>只读字段</b>（tools/gen_station_directions.py 从 enriched 生成）：
                  方向来自 OSM oneway，车道多为默认演示值——<b>不是实测车道/实测方向</b>；缺值一律「—/未标定」；
                  贯通性待核只提示，不改路网。
                </p>
              </div>

              <!-- IKP5BZ · 本段附近的落客点 / 场区：图上 Marker 之外的第二入口（文字可查、可点选） -->
              <div class="lm-block">
                <div class="sec-head">
                  本段附近的落客点 / 场区<span class="sub-tag">{{ nearbyLandmarks.length }} 个 · 演示点</span>
                </div>
                <p v-if="nearbyLandmarks.length === 0" class="lm-empty">
                  本段 150 m 内暂无登记点位（数据源：本站站点包）。图上标记仍可在全图范围内悬停查看。
                </p>
                <ul v-else class="lm-list">
                  <li v-for="p in nearbyLandmarks" :key="`${p.kind}-${p.id}`">
                    <button
                      type="button"
                      class="lm-item"
                      :title="`${p.name} · 所属路段 ${p.segment_id || '未标定'} · ${p.id} · 演示点 · 点击选中该路段`"
                      @click="onSelect(p.segment_id)"
                    >
                      <span class="lm-icon" :class="p.kind">{{ p.kind === 'dropoff' ? '落' : '场' }}</span>
                      <span class="lm-main">
                        <span class="lm-name">{{ p.name }}</span>
                        <span class="lm-meta">
                          {{ p.segment_id || '路段未标定' }} · {{ p.id }} · {{ landmarkDistance(p.distance_m) }}
                        </span>
                      </span>
                    </button>
                  </li>
                </ul>
                <p class="lm-note">
                  数据源：本站站点包（唯一真值源）· 坐标为路段折线上的<b>演示点</b>，不是踏勘点位 ·
                  点击条目选中其所属路段（所属路段按最近折线推定）。
                </p>
              </div>

              <!-- ① 关联摄像头（Issue IKMS18）：该段登记摄像头 + 感知服务真实帧预览 / 如实空窗 -->
              <SegmentCameraCard :segment-id="selectedId || ''" />

              <!-- ② 决策计算摘要（Issue IKMS18）：输入 + 判级（后端下发，前端不重算）+ 四档阈值对照 + 因素/CI -->
              <SegmentDecisionSummary
                :segment-id="selectedId || ''"
                :record="selected"
                :factors="segFactors"
                :thresholds="thresholds"
                :stale="selected ? isStale(selected) : true"
              />

              <!-- ③ 直接下令（Issue IKMS18）：关联告警 → 下发（渠道/比例）→ 回执 → 回写；
                   与决策页调用同一 plan/dispatch · plan/ack，状态共享（GET /alerts）。
                   放在摘要之后、既有热力/双源等块之前——「摄像头 → 计算摘要 → 下令」三联动同屏可见。 -->
              <SegmentDispatchCard
                :segment-id="selectedId || ''"
                :record="selected"
                :alerts="alerts"
                @changed="onCommandChanged"
              />

              <template v-if="selected">
              <!-- 大号 CI + 四项加权构成(原 /heat 右栏;CI 只展示不判级) -->
              <div class="ci-head">
                <div class="idx-ci td-num" :style="{ color: ciTextColor }">{{ ciText }}</div>
                <div class="ci-side">
                  <div class="ci-label">拥挤指数 CI</div>
                  <div class="ci-sub">四项加权 {{ weightText }}</div>
                </div>
              </div>
              <div v-for="w in weights" :key="w.key" class="wt-row">
                <span class="wt-label">{{ w.label }}</span>
                <span class="wt-val td-mono">{{ metricText(w.key) }} × {{ w.weight.toFixed(2) }}</span>
              </div>

              <!-- TC-19:双数据源并排 -->
              <div class="sec-head">
                双数据源并排 · 同一路段 · 字段逐字一致(TC-19)
              </div>
              <table class="td-table tc19-table">
                <thead>
                  <tr>
                    <th>指标</th>
                    <th v-if="sourceMode !== 'twin'" class="c">视频链路</th>
                    <th v-if="sourceMode !== 'video'" class="c">孪生链路</th>
                    <th v-if="sourceMode === 'both'" class="c">差值</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="d in deltaRows" :key="d.key">
                    <td>{{ d.label }}</td>
                    <td v-if="sourceMode !== 'twin'" class="c td-num">{{ typeof d.video === 'number' ? d.video : '—' }}</td>
                    <td v-if="sourceMode !== 'video'" class="c td-num">{{ typeof d.twin === 'number' ? d.twin : '—' }}</td>
                    <td v-if="sourceMode === 'both'" class="c td-num">
                      {{ typeof d.delta === 'number' ? `${d.delta > 0 ? '+' : ''}${d.delta}` : '—' }}
                    </td>
                  </tr>
                </tbody>
              </table>
              <p v-if="pair && !videoAvailable" class="tc19-none">该路段无视频链路数据</p>
              <p class="tc19-note">
                视频链路 = 视频感知链路(YOLO 指标快照) · 孪生链路 = 虚拟检测器 ·
                差值 = 视频 − 孪生 · 一期均为示例数据
              </p>

              <!-- 当前生效因素(原 /heat 成因拆解口径) -->
              <div class="sec-head">
                当前生效因素<span class="sub-tag">{{ segFactors.length }} 项</span>
              </div>
              <FactorBreakdown :factors="segFactors" />

              <!-- CI 走势(原 /heat 右栏) -->
              <div class="sec-head">
                CI 走势 · 近 {{ history?.points.length ?? 12 }} 期<span class="sub-tag">阈值线 65 / 85</span>
              </div>
              <CiTrendBars :history="history" />

              <!-- 预测 -->
              <div class="sec-head">
                未来 15 / 30 分钟预测
                <span class="td-chip warn">L0 · 演示数据(模拟) · 不报精度</span>
              </div>
              <div v-if="selected.pred" class="pred-grid">
                <div class="pred-box">
                  <div class="pred-h">+15 min</div>
                  <div class="pred-v td-num">{{ selected.pred.h15.q_vph }} 辆/h</div>
                  <LevelBadge :level="selected.pred.h15.level" />
                </div>
                <div class="pred-box">
                  <div class="pred-h">+30 min</div>
                  <div class="pred-v td-num">{{ selected.pred.h30.q_vph }} 辆/h</div>
                  <LevelBadge :level="selected.pred.h30.level" />
                </div>
              </div>
              <p v-else class="empty">本路段无预测</p>
              </template>
              <p v-else class="empty sm">
                无运行指标：CI / 双数据源 / 因素 / 走势 / 预测均不给编造值（数据不可用灰档，TC-11）。
              </p>

              <!-- 关联告警(原 /heat 右栏) -->
              <div class="sec-head">
                关联告警<span class="sub-tag">{{ selectedAlerts.length }} 条未闭环</span>
              </div>
              <AlertList :alerts="selectedAlerts" :level-of="segLevelOf" />

              <button class="td-btn act-btn" type="button" @click="gotoDecision">
                到决策页处置（完整工作台）›
              </button>
            </template>
            <p v-else class="empty">点击左侧列表或地图中的路段查看详情</p>
          </div>
          </section>
        </div>
        </el-splitter-panel>
      </el-splitter>
    </div>

    <!-- 上下拉条（业主 2026-10-28「上下可以那样拉吗」）：
         夹在三栏区与底部热力带之间，拖它改热力带高度 = 三栏区（含地图）跟着变高变矮。
         用 pointer 事件 + setPointerCapture，拖出条外也能继续拖、松手一定收到 pointerup。
         右侧小箭头键：热力带一键收到底 / 回记住的高度（与左右栏的收起键同一套习惯）。 -->
    <div
      v-if="mapScope === 'station'"
      class="band-drag"
      role="separator"
      aria-orientation="horizontal"
      aria-label="拖动调整地图与底部热力带的高度"
      :title="`拖动调整高度（双击复位 ${BAND_DEFAULT_H}px）· 当前 ${bandHeight}px`"
      @pointerdown="onBandDragDown"
      @pointermove="onBandDragMove"
      @pointerup="onBandDragUp"
      @pointercancel="onBandDragUp"
      @dblclick="onBandDblClick"
    >
      <span class="band-drag-grip" aria-hidden="true" />
      <button
        type="button"
        class="band-drag-fold"
        :aria-label="bandCollapsed ? '展开底部热力带' : '收起底部热力带（地图变高）'"
        :title="bandCollapsed ? '展开底部热力带' : '收起底部热力带：地图拿走这块高度'"
        @pointerdown.stop
        @click.stop="bandCollapsed ? expandBand() : collapseBand()"
      >
        {{ bandCollapsed ? '⌃ 展开' : '⌄ 收起' }}
      </button>
    </div>

    <!-- 底部热力带(原 /heat:档位分布 | 路段×时间热力矩阵 | CI 色阶与口径)
         IKPFVN E1：全国视角下整条收起 —— 它三块内容全是"当前站"的路段维度
         （档位分布 / 路段×时间矩阵 / CI 色阶），站在全国视角时既没有当前站也不该占高度；
         收起后地图才真的"占满内容区"（NS 视角拿到的地图高度从 ~377 px 涨到 ~680 px，
         全国取景的 zoom 也随之落在 3–6 档，而不是挤在 2 档）。 -->
    <div
      v-if="mapScope === 'station'"
      class="heat-band"
      :style="{ '--band-h': `${bandHeight}px` }"
    >
      <section class="td-card band-card">
        <div class="td-card-head">
          档位分布 · 当前时刻<span class="td-head-tag">
            {{ isFlow ? `流量四档 · ${FLOW_UNAVAILABLE_LABEL} ${unavailableCount}` : `灰档 ${unavailableCount}` }}
          </span>
        </div>
        <div class="td-card-body">
          <BandDistribution
            :rows="bandRows"
            :unavailable="unavailableCount"
            :unavailable-label="isFlow ? FLOW_UNAVAILABLE_LABEL : '不可用'"
          />
          <p class="note">
            共 {{ distTotal }} 个路段 ·
            {{ isFlow ? `${FLOW_UNAVAILABLE_LABEL}不计入分档,分档阈值见 shared/flow.ts` : '灰档不计入均值,与地图同源' }}
          </p>
        </div>
      </section>

      <section class="td-card band-card wide">
        <div class="td-card-head">
          路段 × 时间热力矩阵<span class="td-head-tag">
            {{ isFlow ? '流量版：仅当前快照桶有 q，历史桶灰' : '最近 12 个快照 · 每 60 s 一档 · 左旧右新' }}
          </span>
        </div>
        <div class="td-card-body flush">
          <HeatMatrixTable :matrix="isFlow ? flowHeat : heat" :mode="isFlow ? 'flow' : 'ci'" />
          <p v-if="isFlow" class="note" style="padding: 4px 10px 0">
            流量版矩阵只展示<b>当前快照</b>的 q（接口没有流量时序）；历史桶如实为空（灰），不用 0 或波形冒充历史。
          </p>
        </div>
      </section>

      <section class="td-card band-card">
        <div class="td-card-head">
          CI 色阶 · 展示档位<span class="td-head-tag td-mono">更新 {{ formatStamp(snapshotTs) }}</span>
        </div>
        <div class="td-card-body">
          <CiScale />
          <div class="gray-row">
            <i class="gray-swatch" />
            <span>灰档 = 数据不可用(缺 CI 或数据陈旧),绝不落进通配色</span>
          </div>
          <p class="note">{{ CI_BAND_NOTE }}</p>
          <p v-if="isFlow" class="note">
            CI 色阶为决策口径展示，<b>不参与流量版配色</b>（流量版只用 q 分档；C-2 既有元素保留）。
          </p>
        </div>
      </section>
    </div>

    <!-- 底部告警条 -->
    <div class="td-card alert-bar">
      <div class="alert-left">
        <span class="alert-icon" aria-hidden="true">▲</span>
        <span class="alert-title">
          待认领告警 · {{ firstAlert ? `${LEVELS[segLevelOf(firstAlert)].name}（${CN_NUM[segLevelOf(firstAlert)]}级）` : '—' }}
        </span>
        <span class="alert-summary">
          <template v-if="firstAlert">
            {{ firstAlert.alert_id }} {{ firstAlert.segment_name }} · x {{ firstAlertX }} ·
            首次观测 {{ hhmmss(firstAlert.first_seen) }} · 触发依据 {{ firstAlert.triggered_by.join(', ') }}
          </template>
          <template v-else>当前无待认领告警</template>
        </span>
      </div>
      <div class="alert-right">
        <span class="alert-counts">共 {{ unclaimedCount }} 条待认领 · {{ processingCount }} 条处置中</span>
        <RouterLink class="alert-link" to="/decision">前往决策层处置 ›</RouterLink>
      </div>
    </div>

    <template #foot>
      <span>快照时间 {{ formatStamp(snapshotTs) }}</span>
      <!-- 切站缓存标识（IKPFR4）：页脚也要能看出"这不是刚拉到的" -->
      <span v-if="servedFromCache">数据标识:内存缓存快照 · 后台刷新中</span>
      <span>{{ footStationLine }}</span>
      <span>数据来源:{{ footDataSource }} · 底图:{{ sourceLabel }}</span>
      <span>{{ packLine }}</span>
      <span>
        颜色模式:{{ isFlow ? '纯车流量（q 四档，仅展示，不代表拥堵结论）' : '决策拥堵（接口 level）' }}
      </span>
      <span class="right">
        口径:
        <template v-if="isFlow">
          一期全部示例数据(模拟)· {{ FLOW_MODE_LABEL }} · {{ FLOW_MODE_NOTE }} ·
          数据不可用灰显(TC-11) · {{ FLOW_COLOR_NOTE }}
        </template>
        <template v-else>
          一期全部示例数据(模拟)· 等级三重编码(颜色 + 竖条 + 文字)· 数据不可用灰显(TC-11)· {{ CI_DISCLAIMER }}
        </template>
      </span>
    </template>
  </AppShell>
</template>

<style scoped>
/* 部分接口失败提示条:提醒当前页混装有上一版数据 */
.stale-bar {
  flex: 0 0 auto;
  margin: 10px 16px 0;
  padding: 6px 10px;
  font-size: 11px;
  line-height: 1.5;
  border-radius: var(--td-radius-sm);
  background: var(--td-warning-color-1);
  color: #a06a00;
}

/* ---------- 应急态（TC-10）：红 = 停下引导，不等于整页变红 ----------
   位置纪律：这是**顶部提示条 + 推荐卡替换**，正文（KPI / 地图 / 路段 / 车辆）一字不减。
   历史教训见 scripts/frontend_gate.py 的 gate_emergency_keep：曾把正文包进 !emergency 条件，
   应急一亮整页只剩一条红条，被业主驳回。 */
.emergency-bar {
  flex: 0 0 auto;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
  margin: 10px 16px 0;
  padding: 8px 12px;
  font-size: 12px;
  line-height: 1.6;
  border-radius: var(--td-radius-sm);
  border-left: 4px solid #d92d20;
  background: #fef3f2;
  color: #7a271a;
}

.emergency-tag {
  flex: 0 0 auto;
  padding: 1px 6px;
  border-radius: 3px;
  background: #d92d20;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
}

.emergency-msg {
  font-size: 13px;
}

.emergency-sub {
  color: #93370d;
}

/* 推荐卡里的应急替身：只替这一块，不占别人的位置 */
.emergency-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.em-title {
  font-size: 15px;
  font-weight: 600;
  color: #b42318;
}

.em-line {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--td-text-color-primary);
}

.em-src {
  margin: 2px 0 0;
  font-size: 11px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder);
}

/* ---------- 颜色模式切换（Issue IKNB9G：决策拥堵版 ↔ 纯车流量版） ---------- */
.color-mode-bar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 16px 6px;
  padding: 6px 10px;
  border: 1px solid var(--td-component-stroke);
  border-radius: var(--td-radius-md);
  background: var(--td-bg-color-container);
}
.cm-title {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}
.cm-item {
  height: 26px;
  padding: 0 12px;
  font-size: 12px;
  border: 1px solid var(--td-component-border);
  border-radius: var(--td-radius-sm);
  background: var(--td-bg-color-secondarycontainer);
  color: var(--td-text-color-secondary);
  cursor: pointer;
}
.cm-item:hover {
  border-color: var(--td-brand-color);
  color: var(--td-brand-color);
}
.cm-item.on {
  background: var(--td-brand-color);
  border-color: var(--td-brand-color);
  color: var(--td-text-color-anti);
}
/* 流量版用蓝阶主色（与拥堵版品牌蓝按钮区分：这里只是「当前模式」语义） */
.cm-item.flow.on {
  background: #2f54eb;
  border-color: #2f54eb;
}
.cm-note {
  flex: 1;
  min-width: 240px;
  font-size: 11px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder);
}
.cm-note b {
  color: var(--td-brand-color);
}
/* 流量版列表角标（不用 LevelBadge：避免把车流量读成判级） */
.flow-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 64px;
  height: 20px;
  padding: 0 7px;
  border-radius: 3px;
  border: 1px solid transparent;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}
.flow-badge.off {
  background: var(--td-bg-color-secondarycontainer);
  color: var(--td-text-color-placeholder);
  border-color: var(--td-component-border);
}
.flow-swatch {
  width: 14px;
  height: 14px;
  border-radius: 2px;
  flex: 0 0 auto;
}
.view-seg .td-seg-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ---------- 切站提示条 / 骨架（Issue IKPFR4）----------
   口径：① 「缓存 · 刷新中」用中性琥珀（说明性状态，不是告警、不用等级色、不抢品牌蓝）；
        ② 无缓存时的骨架条只有一行 + 三根呼吸条，**不做整屏 spinner、不白屏** ——
           切站是同一页内的局部刷新，不是重新打开一个应用。 */
.cache-bar {
  flex: 0 0 auto;
  margin: 10px 16px 0;
  padding: 6px 10px;
  font-size: 11px;
  line-height: 1.5;
  border-radius: var(--td-radius-sm);
  border: 1px dashed #e0a800;
  background: var(--td-warning-color-1);
  color: #8a5b00;
}
.switch-bar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 10px 16px 0;
  padding: 6px 10px;
  font-size: 11px;
  line-height: 1.5;
  border-radius: var(--td-radius-sm);
  border: 1px solid var(--td-component-stroke);
  background: var(--td-bg-color-secondarycontainer);
  color: var(--td-text-color-secondary);
}
.switch-spinner {
  flex: 0 0 auto;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid var(--td-brand-color-1);
  border-top-color: var(--td-brand-color);
  animation: switch-spin 0.9s linear infinite;
}
@keyframes switch-spin {
  to {
    transform: rotate(360deg);
  }
}
/* 骨架：三根长度不一的呼吸条，暗示"内容正在来"，但不假装已经有数字 */
.switch-skeleton {
  display: inline-flex;
  gap: 6px;
  margin-left: 4px;
}
.switch-skeleton i {
  display: block;
  width: 42px;
  height: 8px;
  border-radius: 4px;
  background: var(--td-component-border);
  animation: switch-breathe 1.2s ease-in-out infinite;
}
.switch-skeleton i:nth-child(2) {
  width: 30px;
  animation-delay: 0.15s;
}
.switch-skeleton i:nth-child(3) {
  width: 54px;
  animation-delay: 0.3s;
}
@keyframes switch-breathe {
  0%,
  100% {
    opacity: 0.35;
  }
  50% {
    opacity: 0.9;
  }
}
@media (prefers-reduced-motion: reduce) {
  .switch-spinner,
  .switch-skeleton i {
    animation: none;
  }
}

/* ---------- KPI 条 ---------- */
.kpi-bar {
  flex: 0 0 auto;
  flex-direction: row;
  display: flex;
  margin: 12px 16px 10px;
}
.kpi-cell {
  flex: 1;
  min-width: 0;
  padding: 10px 14px;
  border-left: 1px solid var(--td-component-stroke);
}
.kpi-cell:first-child {
  border-left: none;
}
.kpi-label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}
.kpi-value {
  margin-top: 4px;
  font-size: 22px;
  font-weight: 700;
  line-height: 1.15;
  color: var(--td-text-color-primary);
}
.kpi-unit {
  margin-left: 5px;
  font-size: 12px;
  font-weight: 400;
  color: var(--td-text-color-placeholder);
}
.kpi-sub {
  margin-top: 3px;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.kpi-sep {
  color: var(--td-text-color-placeholder);
}

/* ---------- 三栏 · 横向可拖(Issue #81) ----------
   ① 必须用 `:deep()`:本 <style> 是 scoped,编译后会给选择器加 [data-v-xxx] 属性。
      而 `.el-splitter-panel` / `.el-splitter-bar` / `__dragger` 都是 **ElSplitter 子组件内部**
      渲染的元素,不会带上**本组件**的 scope 属性 —— 写成 `.td-splitter > .el-splitter-bar` 会被
      编译成 `.td-splitter[data-v-x] > .el-splitter-bar[data-v-x]`,后者永远匹配不上,规则整条失效。
      `:deep()` 后半段不带属性,只对根元素(.td-splitter 在本模板里,带属性)生效,才是对的。
   ② 每条规则都以 `.el-splitter.td-splitter` **双类**开头,不是装饰:element-plus 自带的
      `.el-splitter-bar__dragger:hover:not(.is-disabled):before` 权重 (0,3,1);
      单类 + :deep 只能到 (0,4,1) 勉强压过 hover 那条,而默认态那条
      `.el-splitter-bar__dragger:before` 只有 (0,1,1),用单类也够。双类是为了让 hover/active
      与默认态都稳定压过,不依赖打包后的 CSS 注入顺序。改这几条时别把双类删掉。 */
.el-splitter.td-splitter {
  width: 100%;
  height: 100%;
  min-width: 0;
}
.el-splitter.td-splitter :deep(> .el-splitter-panel) {
  /* panel 自带 overflow:auto 会和内部 .td-scroll 叠成双层滚动条 ——
     显式关掉,滚动职责仍归各栏内部的 .td-scroll(左: .td-scroll/seg-list,右: .td-scroll)。 */
  overflow: hidden;
}
.el-splitter.td-splitter :deep(> .el-splitter-bar) {
  /* bar 自身宽度是 0(行内 style `width:0`,element-plus 只让 16px 的 dragger 绝对定位盖在上面),
     而原 .td-body{gap:10px} 换成 splitter 后不再作用在栏之间 → 必须给 bar 一个宽度。
     取 **16px** 而不是照搬原来的 10px:dragger 的拖拽热区宽度是 16px(行内 style),
     若 bar 只有 10px,热区会向左右各溢出 3px 盖到面板边缘上,吃掉面板最边上 3px 的点击。
     16px 让热区正好落在 bar 内,零重叠;代价是栏间距 10px→16px(中栏随之宽 12px,
     三栏默认宽度 296/弹性/396 一律未动,不影响设计稿对齐)。 */
  flex: 0 0 16px;
  background: transparent;
}
.el-splitter.td-splitter :deep(.el-splitter-bar .el-splitter-bar__dragger::before) {
  /* 真正画出那条竖线的伪元素。拖拽热区 dragger 本体是 16px 宽且**行内 style**,
     CSS 改不动也不该改 —— 只改伪元素的可见竖线。
     默认色 var(--el-border-color-light)=#E4E7ED、hover/active 是 --el-color-primary-light-5/3
     即 element-plus 默认蓝 #409EFF:既违反「品牌蓝只表示当前/已选/可操作」,
     又与 --td-brand-color 构成第二套蓝。这里换成设计令牌的中性边框色。
     ⚠️ 这里**不能写 `> .el-splitter-bar__dragger`**:dragger 是 .el-splitter-bar 的子元素
     (实测 split-bar 模板:.el-splitter-bar > [collapse-icon] + .el-splitter-bar__dragger),
     不是 splitter 的直接子元素 —— 用子代组合符会让整条规则永远匹配不上(已踩过)。 */
  background-color: var(--td-component-border);
  width: 1px;
}
/* element-plus 另有 `.el-splitter-bar__dragger:after`(激活时偏移的第二道线,默认 opacity .4),
   会叠出一条半透明默认蓝 —— 一并改掉,否则拖拽时仍见默认蓝。 */
.el-splitter.td-splitter :deep(.el-splitter-bar .el-splitter-bar__dragger::after) {
  background-color: var(--td-component-border);
}
.el-splitter.td-splitter :deep(.el-splitter-bar .el-splitter-bar__dragger:hover:not(.is-disabled)::before),
.el-splitter.td-splitter :deep(.el-splitter-bar .el-splitter-bar__dragger-active::before) {
  /* hover/拖拽中用品牌蓝:此时分隔条是「正在被操作」的对象,符合品牌蓝语义 */
  background-color: var(--td-brand-color);
  width: 2px;
}

/* ---------- 三栏内部列宽 ----------
   宽度改由 ElSplitter 的 :size 驱动(见 script 内 COL_DEFAULT_* / COL_MIN_*),
   这里的 flex 硬编码宽度已撤掉,只保留 flex 列布局与不换行的最小约束。 */
.col-left {
  flex: 0 0 auto;
  height: 100%;
  min-width: 0;
  overflow: hidden;
}
.col-mid {
  flex: 1 1 auto;
  height: 100%;
  min-width: 0;
  overflow: hidden;
}
.col-right {
  flex: 0 0 auto;
  height: 100%;
  min-width: 0;
}

/* ---------- 左右栏收起 / 展开（业主 2026-10-28） ----------
   面板 width 已由 `colLeft/colRight = 0` + `:min="0"` 驱动，这里只补两件事：
   ① 收起时把面板的 padding / border 也清掉，否则会留 1~2px 的"线"；
   ② 收起面板对应的分隔条隐藏（两侧都收起 / 单侧收起时那条线拖不动，留着是死线）。
   ⚠️ 与全国视角 `is-national` 的规则同权重（都是 !important），本块在**它之前**，
      两者不会同时命中（全国视角下 colLeftCollapsed 无意义），不会打架。 */
.el-splitter.td-splitter.is-fold-left :deep(> .el-splitter-panel:first-child),
.el-splitter.td-splitter.is-fold-right :deep(> .el-splitter-panel:last-child) {
  overflow: hidden;
  opacity: 0;
  transition: flex-basis 220ms ease, opacity 160ms ease;
}
.el-splitter.td-splitter.is-fold-left :deep(> .el-splitter-bar:nth-child(2)),
.el-splitter.td-splitter.is-fold-right :deep(> .el-splitter-bar:nth-child(4)) {
  display: none !important;
}

/* 栏顶工具条：左边是栏名，右边是「收起」键。吸在滚动容器顶部，
   右栏整栏要滚（.td-scroll），不吸顶的话收起键会跟着内容滚走。 */
.col-head {
  position: sticky;
  top: 0;
  z-index: 3;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 2px 2px 6px;
  background: var(--td-bg-color-container);
}
.col-head-title {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}
.col-fold {
  flex: 0 0 auto;
  padding: 2px 8px;
  border: 1px solid var(--td-component-stroke);
  border-radius: 4px;
  background: var(--td-bg-color-container);
  font: inherit;
  font-size: 11px;
  color: var(--td-text-color-secondary);
  cursor: pointer;
  white-space: nowrap;
}
.col-fold:hover {
  border-color: var(--td-brand-color);
  color: var(--td-brand-color);
}
/* 地图工具条上的「展开」键：与「← 全国」同款中性描边，不用品牌蓝 */
.map-fold-btn {
  padding: 3px 8px;
  border: 1px solid var(--td-component-stroke);
  border-radius: 4px;
  background: var(--td-bg-color-container);
  font: inherit;
  font-size: 11px;
  color: var(--td-text-color-secondary);
  cursor: pointer;
  white-space: nowrap;
}
.map-fold-btn:hover {
  border-color: var(--td-brand-color);
  color: var(--td-brand-color);
}

/* ---------- 左栏 · 选择监控 ---------- */
.view-seg {
  width: 100%;
  margin-bottom: 10px;
}
.view-seg .td-seg-item {
  flex: 1;
  text-align: center;
}
.dist-bar {
  display: flex;
  height: 14px;
  border-radius: 3px;
  overflow: hidden;
}
.dist-seg {
  height: 100%;
  cursor: pointer;
}
.dist-seg.dim {
  opacity: 0.3;
}
.dist-legend {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
}
.dist-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 1px 4px;
  border-radius: var(--td-radius-sm);
  cursor: pointer;
}
.dist-item.on {
  background: var(--td-brand-color-1);
}
.dist-item.all {
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.dist-count {
  font-size: 12px;
  color: var(--td-text-color-primary);
}

/* ---------- 左栏 · 路段监测 ---------- */
.seg-card {
  flex: 1 1 auto;
  min-height: 0;
}
.seg-body {
  flex: 1;
  min-height: 0;
  display: flex;
}
.seg-list {
  flex: 1;
  min-height: 0;
}
.td-row {
  gap: 8px;
}
.lvl-bar {
  flex: 0 0 4px;
  align-self: stretch;
  min-height: 18px;
  border-radius: 2px;
}
.seg-meta {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
  flex: 1;
}
.seg-name {
  font-size: 13px;
  color: var(--td-text-color-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.seg-id {
  font-size: 10px;
  color: var(--td-text-color-placeholder);
}
.seg-value {
  font-size: 12px;
  white-space: nowrap;
}

/* ---------- 中栏地图 ---------- */
.map-card {
  flex: 1 1 auto;
  min-height: 0;
}
/* 地图工具条(业主 2026-10-16):只留"全路段状态"+当前底图口径 ——
   「示例路网 / 矢量地图」两个模式标签已删(Issue IKM5T1:只留一个渲染器) */
.map-toolbar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--td-component-stroke);
  gap: 10px;
}
.map-toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.map-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
/* 路网版本切换（IKMDKY 子单①）：两段式小按钮，选中态用品牌蓝 */
.pack-switch {
  display: inline-flex;
  border: 1px solid var(--td-component-stroke);
  border-radius: 4px;
  overflow: hidden;
}
.pack-switch-item {
  padding: 3px 10px;
  border: 0;
  background: #ffffff;
  font: inherit;
  font-size: 11px;
  color: var(--td-text-color-secondary);
  cursor: pointer;
  white-space: nowrap;
}
.pack-switch-item + .pack-switch-item {
  border-left: 1px solid var(--td-component-stroke);
}
.pack-switch-item.on {
  background: v-bind('TD.brand');
  color: #ffffff;
}
.map-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}
.map-tag {
  font-size: 11px;
  color: var(--td-text-color-secondary);
  background: var(--td-bg-color-secondary);
  padding: 2px 8px;
  border-radius: 10px;
}
.map-body {
  flex: 1;
  min-height: 0;
}
.map-caption {
  flex: 0 0 auto;
  padding: 6px 12px;
  border-top: 1px solid var(--td-component-stroke);
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}

/* ---------- 右栏 · 路段信息 ---------- */
.d-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.d-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}
.d-summary {
  margin-top: 3px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
/* IKOQEJ · 方向 / 车道 / 对向 / 贯通（只读 enriched 字段；缺值「—/未标定」） */
.dir-block {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px dashed var(--td-component-stroke);
}
.dir-kv {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 2px 0;
  font-size: 12px;
}
.dir-kv .k {
  flex: 0 0 106px;
  color: var(--td-text-color-secondary);
}
.dir-kv .v {
  flex: 1;
  min-width: 0;
  color: var(--td-text-color-primary);
  word-break: break-all;
}
.dir-src {
  margin-left: 6px;
  font-size: 10px;
  color: var(--td-text-color-placeholder);
  font-weight: 400;
}
.dir-link {
  padding: 0;
  border: none;
  background: none;
  font: inherit;
  font-size: 12px;
  color: var(--td-brand-color);
  cursor: pointer;
}
.dir-link:hover {
  text-decoration: underline;
}
.dir-cont {
  font-weight: 600;
}
.dir-cont.ok {
  color: var(--td-success-color);
}
.dir-cont.warn {
  color: var(--td-warning-color);
}
.dir-cont.muted {
  color: var(--td-text-color-placeholder);
  font-weight: 400;
}
.dir-detail {
  margin-left: 6px;
  font-size: 10px;
  color: var(--td-text-color-placeholder);
}
.dir-note {
  margin: 4px 0 2px;
  font-size: 10px;
  line-height: 1.6;
  color: var(--td-text-color-placeholder);
}
/* IKP5BZ · 本段附近的落客点 / 场区（与地图 Marker 同一份演示点位） */
.lm-block {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px dashed var(--td-component-stroke);
}
.lm-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.lm-item {
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 7px;
  padding: 4px 6px;
  text-align: left;
  font: inherit;
  background: var(--td-bg-color-container-hover);
  border: 1px solid transparent;
  border-radius: var(--td-radius-sm);
  cursor: pointer;
}
.lm-item:hover {
  border-color: var(--td-brand-color);
}
.lm-icon {
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  border-radius: 4px;
  color: #ffffff;
  font-size: 10px;
  line-height: 18px;
  text-align: center;
}
.lm-icon.dropoff {
  background: #0f766e;
}
.lm-icon.zone {
  background: #8a5a2b;
}
.lm-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.lm-name {
  font-size: 12px;
  line-height: 1.4;
  color: var(--td-text-color-primary);
}
.lm-meta {
  font-size: 10px;
  color: var(--td-text-color-placeholder);
}
.lm-empty {
  margin: 2px 0;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
.lm-note {
  margin: 5px 0 0;
  font-size: 10px;
  line-height: 1.6;
  color: var(--td-text-color-placeholder);
}
/* 大号 CI(原 /heat 右栏;CI 只展示不判级) */
.ci-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: var(--td-radius-sm);
  background: var(--td-bg-color-secondarycontainer);
}
.idx-ci {
  font-size: 30px;
  font-weight: 700;
  line-height: 1.1;
}
.ci-side {
  min-width: 0;
}
.ci-label {
  font-size: 12px;
  color: var(--td-text-color-primary);
}
.ci-sub {
  margin-top: 2px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.wt-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 3px 2px;
  font-size: 12px;
}
.wt-label {
  color: var(--td-text-color-secondary);
}
.wt-val {
  color: var(--td-text-color-primary);
}
.tc19-table th,
.tc19-table td {
  padding: 6px 8px;
}
.tc19-table th.c,
.tc19-table td.c {
  text-align: center;
}
.tc19-none {
  margin: 6px 0 0;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.tc19-note {
  margin: 6px 0 0;
  font-size: 10px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder);
}
.sec-head {
  margin: 12px 0 6px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}
.sub-tag {
  margin-left: auto;
  font-size: 10px;
  font-weight: 400;
  color: var(--td-text-color-placeholder);
}
.pred-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.pred-box {
  padding: 8px 10px;
  border: 1px solid var(--td-component-stroke);
  border-radius: var(--td-radius-sm);
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.pred-h {
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.pred-v {
  font-size: 16px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}
.act-btn {
  margin-top: 12px;
  width: 100%;
  height: 34px;
  font-size: 13px;
}

/* ---------- 上下拉条（三栏区 ↔ 底部热力带） ---------- */
.band-drag {
  flex: 0 0 auto;
  position: relative;
  height: 10px;
  margin: 0 16px;
  cursor: ns-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  touch-action: none;
  /* 命中区比视觉高度大一圈：10px 太细，往上/下各偷 3px，拖起来不费劲 */
  padding: 3px 0;
  box-sizing: content-box;
}
.band-drag-grip {
  width: 40px;
  height: 3px;
  border-radius: 2px;
  background: var(--td-component-stroke);
  transition: background 120ms ease, width 120ms ease;
}
.band-drag:hover .band-drag-grip {
  width: 64px;
  background: var(--td-brand-color);
}
.band-drag-fold {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  padding: 1px 6px;
  font-size: 10px;
  line-height: 1.4;
  color: var(--td-text-color-placeholder);
  background: transparent;
  border: 1px solid var(--td-component-stroke);
  border-radius: 3px;
  cursor: pointer;
}
.band-drag-fold:hover {
  color: var(--td-brand-color);
  border-color: var(--td-brand-color);
}
/* 拖动期间禁选中：否则上下拖会顺手把页面文字刷蓝。
   本 <style> 是 scoped，body 不在组件内 → 必须用 :global(...)，写法是
   `:global(body).is-vdrag`（`:global(body.is-vdrag)` 那种整段包进去的写法在
   Vue 3 里会报编译错，别改）。 */
:global(body).is-vdrag {
  user-select: none;
}

/* ---------- 底部热力带(原 /heat 三栏内容) ---------- */
.heat-band {
  /* 业主 2026-10-28「上下可以那样拉吗」：高度由拉条写入的 --band-h 决定，
     不用 flex 撑（撑开的话拉条改高度会被内容 min-height 顶回去）。 */
  flex: 0 0 auto;
  height: var(--band-h, 196px);
  min-height: 0;
  display: flex;
  gap: 10px;
  margin: 0 16px 8px;
  overflow: hidden;
}
.band-card {
  flex: 0 0 240px;
  min-height: 0;
}
.band-card.wide {
  flex: 1 1 auto;
  min-width: 0;
}
.band-card .td-card-body {
  max-height: 176px;
  overflow: hidden;
}
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

/* ---------- 底部告警条 ---------- */
.alert-bar {
  flex: 0 0 auto;
  flex-direction: row;
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 16px 8px;
  padding: 8px 12px;
}
.alert-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.alert-icon {
  color: var(--td-error-color);
  font-size: 11px;
}
.alert-title {
  color: var(--td-error-color);
  font-weight: 500;
  font-size: 12px;
  white-space: nowrap;
}
.alert-summary {
  font-size: 11px;
  color: var(--td-text-color-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.alert-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
  white-space: nowrap;
}
.alert-counts {
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.alert-link {
  font-size: 12px;
  color: var(--td-brand-color);
  text-decoration: none;
  font-weight: 500;
}
.alert-link:hover {
  text-decoration: underline;
}

.empty {
  margin: 8px 2px;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}

/* ---------- 推荐路线卡片（IKMF1W）---------- */
.route-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}
.route-tab {
  flex: 1;
  padding: 5px 0;
  font-size: 12px;
  color: var(--td-text-color-secondary);
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-stroke);
  border-radius: var(--td-radius-sm);
  cursor: pointer;
}
.route-tab.on {
  color: #ffffff;
  background: var(--td-brand-color);
  border-color: var(--td-brand-color);
}
.route-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.route-source {
  margin: 0 2px 8px;
  font-size: 11px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder);
}
.route-badge {
  padding: 1px 6px;
  font-size: 10px;
  color: #a06a00;
  background: var(--td-warning-color-1);
  border-radius: 3px;
}
.route-item {
  margin-bottom: 8px;
  padding: 7px 9px;
  background: var(--td-bg-color-container-hover);
  border-radius: var(--td-radius-sm);
  /* 左侧色条 = 该路线在地图上的颜色（业主 2026-10-28 统一蓝色系）：
     规划蓝 #0052D9 / 备选中蓝 #2563EB / 离站紫 #7B61FF / 选中天蓝 #38BDF8 */
  border-left: 3px solid #0052d9;
  cursor: pointer;
  transition: box-shadow 0.15s ease;
}
.route-item:hover {
  box-shadow: inset 0 0 0 1px rgba(0, 82, 217, 0.28);
}
.route-item:focus-visible {
  outline: 2px solid #0052d9;
  outline-offset: 1px;
}
.route-item.alternative {
  border-left-color: #2563eb;
}
.route-item.departure {
  border-left-color: #7b61ff;
}
/* 被选中的那条：天蓝（与地图上的选中路线同色），再点一次取消 */
.route-item.picked {
  border-left-color: #38bdf8;
  box-shadow: inset 0 0 0 1px rgba(56, 189, 248, 0.65);
}
.route-picked-tag {
  margin-left: auto;
  margin-right: 6px;
  padding: 0 6px;
  font-size: 11px;
  line-height: 16px;
  color: #0b4a63;
  background: #bae6fd;
  border-radius: 8px;
  white-space: nowrap;
}
.route-item-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.route-kind {
  font-size: 12px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}
.route-eta {
  font-size: 12px;
  color: var(--td-text-color-primary);
}
.route-segs {
  margin-top: 3px;
  font-size: 11px;
  line-height: 1.5;
  color: var(--td-text-color-secondary);
  word-break: break-all;
}
.route-note {
  margin-top: 3px;
  font-size: 11px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder);
}
.route-hint {
  margin: 6px 2px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}
.route-hint.warn {
  color: #a06a00;
  background: var(--td-warning-color-1);
  padding: 5px 8px;
  border-radius: 3px;
}
.route-why {
  margin: 8px 2px 2px;
  font-size: 11px;
  line-height: 1.6;
  color: var(--td-text-color-placeholder);
}

/* ---------- 整条路线规划（Issue IKNAUI） ---------- */
.route-plan {
  margin-bottom: 8px;
  padding: 7px 9px;
  border: 1px solid var(--td-component-stroke);
  border-radius: var(--td-radius-sm);
  background: var(--td-bg-color-secondarycontainer);
}
.route-plan-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 5px;
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}
.route-select {
  width: 100%;
  height: 26px;
  margin-bottom: 5px;
  padding: 0 6px;
  font-size: 11px;
  color: var(--td-text-color-primary);
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-border);
  border-radius: var(--td-radius-sm);
}
.trip-summary {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.trip-line {
  font-size: 11px;
  line-height: 1.6;
  color: var(--td-text-color-primary);
}
.trip-line b {
  display: inline-block;
  min-width: 32px;
  margin-right: 4px;
  color: var(--td-brand-color);
}
.trip-segs {
  margin: 0 0 3px 36px;
  font-size: 10px;
  line-height: 1.5;
  color: var(--td-text-color-secondary);
  word-break: break-all;
}

/* ---------- 起点 / 终点确认（Issue IKP5C6） ---------- */
.start-end {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 8px 0 6px;
}
.se-block {
  padding: 6px 8px;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-stroke);
  border-left: 3px solid var(--td-brand-color);
  border-radius: var(--td-radius-sm);
}
.se-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}
.se-tag {
  padding: 0 5px;
  font-size: 10px;
  line-height: 16px;
  color: var(--td-brand-color);
  background: var(--td-brand-color-1);
  border-radius: 2px;
}
.se-tag.warn {
  color: var(--td-warning-color);
  background: var(--td-warning-color-1);
}
.se-line {
  margin-top: 3px;
  font-size: 11px;
  line-height: 1.6;
  color: var(--td-text-color-primary);
}
.se-note,
.se-warn {
  margin: 3px 0 0;
  font-size: 10px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder);
}
.se-warn {
  color: var(--td-warning-color);
}
.se-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 5px;
}
.se-select {
  flex: 1 1 auto;
  min-width: 0;
  margin-bottom: 0;
}
.se-btn {
  flex: 0 0 auto;
  height: 24px;
  padding: 0 8px;
  font-size: 11px;
  color: var(--td-brand-color);
  cursor: pointer;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-brand-color);
  border-radius: var(--td-radius-sm);
}
.se-btn:disabled {
  color: var(--td-text-color-disabled);
  cursor: not-allowed;
  border-color: var(--td-component-border);
}

/* 右栏顺序（Issue IKMS18）：点路段后**先看路段信息**（关联摄像头 / 决策计算摘要 / 直接下令），
   推荐路线卡排在其后 —— 监控管理平台的操作面板优先，不是删掉路线能力（C-2 一项不删）。
   .td-col 是 flex column，用 order 调整顺序，不改 DOM 结构。 */
.col-right > .td-card:not(.route-card) {
  order: 1;
}
.col-right > .route-card {
  order: 2;
}

/* ==========================================================================
   响应式（Issue IKP3EV：管理端 Web 自适应，适配 1080×1920 及以下屏幕）
   断点统一 max-width，由大到小：1366 → 1180 → 1080 → 900 → 768 → 560。
   1920×1080 设计稿零变化：本区块所有规则都在媒体查询内，不覆盖上面任何桌面规则。
   分工：页面壳层（.td-page / .td-main / .td-body / .td-foot / 顶栏）由全局
   style.css + AppShell.vue 负责；本区块只管「大屏页内部」的栏堆叠、卡片高度、
   KPI / 地图 / 热力带 / 告警条与宽表滚动。
   ========================================================================== */

/* ---------- ≤1366：三栏仍并排（1366×768 属于该区间），只收窄左右栏 + 压缩留白 ---------- */
@media (max-width: 1366px) {
  /* 仅该区间固定左右栏宽：296 / 396 是 1920 设计稿值，在 1366 屏上会把弹性中栏压到
     不足 700px。这里用 !important 压过 ElSplitter 写在 panel 上的行内 flex-basis。
     ⚠️ 本区间（>1180 且 ≤1366）用户拖拽记忆不生效：拖拽回调仍会存宽度，但视觉宽度
        被这两条固定 —— 属于「窄屏优先保证地图与右栏可读」的有意取舍。 */
  .el-splitter.td-splitter :deep(> .el-splitter-panel:first-child) {
    flex-basis: 240px !important;
  }
  .el-splitter.td-splitter :deep(> .el-splitter-panel:last-child) {
    flex-basis: 320px !important;
  }
  .kpi-bar {
    margin: 10px 12px 8px;
  }
  .color-mode-bar,
  .heat-band,
  .alert-bar {
    margin-left: 12px;
    margin-right: 12px;
  }
  .stale-bar {
    margin: 10px 12px 0;
  }
  .kpi-cell {
    padding: 9px 12px;
  }
  .kpi-value {
    font-size: 20px;
  }
  .band-card {
    flex: 0 0 210px;
  }
  .heat-band {
    gap: 8px;
  }
  .el-splitter.td-splitter :deep(> .el-splitter-bar) {
    flex-basis: 12px;
  }
}

/* ---------- ≤1180：三栏纵向堆叠，整页文档滚动（本单主断点） ---------- */
@media (max-width: 1180px) {
  /* ① ElSplitter 改为纵向：bar 隐藏，panel 的「宽度」换成「整行」。
     panel 上有组件写的行内 flex-basis（px），纵向布局下会变成「高度」，
     必须用 !important 覆盖成 auto，否则三栏会被钉成 296 / 396 高。 */
  .el-splitter.td-splitter {
    display: flex;
    flex-direction: column;
    height: auto;
    gap: 10px;
  }
  .el-splitter.td-splitter :deep(> .el-splitter-bar) {
    display: none;
  }
  .el-splitter.td-splitter :deep(> .el-splitter-panel) {
    flex: 0 0 auto !important;
    width: 100%;
    overflow: visible;
  }
  /* 再压一次 first/last：≤1366 区块给它们设了固定 flex-basis（那里是宽度），
     堆叠后同一属性会变成高度，必须清回 auto（同权重、本块在后，按源顺序生效）。 */
  .el-splitter.td-splitter :deep(> .el-splitter-panel:first-child),
  .el-splitter.td-splitter :deep(> .el-splitter-panel:last-child) {
    flex-basis: auto !important;
  }
  /* ② 三栏自身回到自然高度；滚动交给各卡片内部，不再出第二层纵向滚动。 */
  .col-left,
  .col-mid,
  .col-right {
    height: auto;
    overflow: visible;
  }
  /* .col-right 同时挂了全局 .td-scroll（overflow-y:auto），用双类确保堆叠后不再整栏滚动。 */
  .col-right.td-scroll {
    overflow: visible;
  }

  /* ③ 左栏：路段监测列表给固定高度 + 内部滚动（其余卡片自然高度）。 */
  .seg-card {
    flex: 0 0 auto;
    height: 420px;
  }

  /* ④ 中栏地图：按视口占比给高度，上下限防止矮屏太小 / 超长竖屏太大。 */
  .map-card {
    flex: 0 0 auto;
    height: clamp(320px, 56vh, 620px);
    min-height: 320px;
  }
  .map-toolbar {
    flex-wrap: wrap;
    row-gap: 6px;
  }
  .map-toolbar-left,
  .map-toolbar-right {
    flex-wrap: wrap;
    row-gap: 6px;
  }

  /* ⑤ 底部热力带：纵向堆叠；卡身不再裁剪（桌面为了一屏放下限制了 176px 高）。 */
  .heat-band {
    flex-direction: column;
    gap: 10px;
    margin-left: 12px;
    margin-right: 12px;
  }
  .band-card,
  .band-card.wide {
    flex: 0 0 auto;
    width: 100%;
  }
  .band-card .td-card-body {
    max-height: none;
    overflow: visible;
  }

  /* ⑥ 底部告警条：允许换行，不再用 nowrap + 省略号硬挤。 */
  .alert-bar {
    flex-wrap: wrap;
    row-gap: 6px;
    margin-left: 12px;
    margin-right: 12px;
  }
  .alert-left {
    flex-wrap: wrap;
    row-gap: 4px;
    min-width: 0;
  }
  .alert-right {
    margin-left: 0;
  }
}

/* ---------- ≤1080：本单主验收尺寸（1080×1920 竖屏） ---------- */
@media (max-width: 1080px) {
  .kpi-bar {
    margin: 8px 10px 8px;
  }
  .color-mode-bar,
  .heat-band,
  .alert-bar {
    margin-left: 10px;
    margin-right: 10px;
  }
  .stale-bar {
    margin: 8px 10px 0;
  }
  /* 竖屏 1920 高时 56vh≈1075 会被 clamp 上限 620 截住；这里再降到 560，
     让「地图 + 左栏列表 + 底部热力带」在竖屏首屏内更接近完整可见。 */
  .map-card {
    height: clamp(320px, 52vh, 560px);
  }
  .seg-card {
    height: 400px;
  }
}

/* ---------- ≤900：平板竖屏 / 手机横屏 ---------- */
@media (max-width: 900px) {
  /* KPI 4 格一行在 900 以下会把数字挤换行 —— 改 2×2。
     odd 去掉左分隔线（每行首格），第 3/4 格补上分隔线。 */
  .kpi-bar {
    flex-wrap: wrap;
  }
  .kpi-cell {
    flex: 1 1 50%;
    max-width: 50%;
    border-left: 1px solid var(--td-component-stroke);
  }
  .kpi-cell:nth-child(odd) {
    border-left: none;
  }
  .kpi-cell:nth-child(n + 3) {
    border-top: 1px solid var(--td-component-stroke);
  }
  .seg-card {
    height: 380px;
  }
  .map-card {
    height: clamp(320px, 52vh, 520px);
  }
}

/* ---------- ≤768：手机横屏 / 小平板 ---------- */
@media (max-width: 768px) {
  .kpi-bar {
    margin: 8px 10px;
  }
  .color-mode-bar,
  .heat-band,
  .alert-bar {
    margin-left: 10px;
    margin-right: 10px;
  }
  .color-mode-bar {
    margin-bottom: 8px;
  }
  .stale-bar {
    margin: 8px 10px 0;
  }
  .kpi-cell {
    padding: 8px 10px;
  }
  .kpi-value {
    font-size: 19px;
  }
  .seg-card {
    height: 340px;
  }
  .map-card {
    height: clamp(320px, 52vh, 460px);
  }
  .map-toolbar {
    padding: 7px 10px;
  }
  .map-caption {
    padding: 5px 10px;
  }
  /* 告警摘要允许自然换行：手机宽度下 nowrap + 省略号会把「触发依据」整段吃掉。 */
  .alert-summary {
    white-space: normal;
    overflow: visible;
    text-overflow: clip;
  }
}

/* ---------- ≤560：手机竖屏（390×844 等） ---------- */
@media (max-width: 560px) {
  .kpi-bar {
    margin: 8px 8px;
  }
  .color-mode-bar,
  .heat-band,
  .alert-bar {
    margin-left: 8px;
    margin-right: 8px;
  }
  .stale-bar {
    margin: 8px 8px 0;
  }
  .cm-note {
    flex: 1 1 100%;
    min-width: 0;
  }
  .kpi-cell {
    padding: 7px 8px;
  }
  .kpi-label {
    font-size: 11px;
  }
  .kpi-value {
    font-size: 18px;
  }
  .kpi-unit {
    margin-left: 3px;
    font-size: 11px;
  }
  .kpi-sub {
    font-size: 10px;
  }
  .seg-card {
    height: 320px;
  }
  .map-card {
    height: clamp(320px, 50vh, 440px);
  }
  .map-toolbar-left,
  .map-toolbar-right {
    gap: 6px;
  }
  .pack-switch-item {
    padding: 3px 8px;
  }
  .map-caption {
    font-size: 10px;
    line-height: 1.5;
  }
  /* 右栏预测两列在 340px 宽内会挤成窄条 —— 小屏单列。 */
  .pred-grid {
    grid-template-columns: 1fr;
  }
  /* 方向 / 车道 的键列从固定 106px 收到 84px，值列允许换行到下一行。 */
  .dir-kv {
    flex-wrap: wrap;
    gap: 2px 8px;
  }
  .dir-kv .k {
    flex: 0 0 84px;
  }
  .dir-kv .v {
    flex: 1 1 160px;
  }
  .route-item-head {
    flex-wrap: wrap;
  }
  .route-meta {
    gap: 4px 8px;
  }
  .trip-segs {
    margin-left: 0;
  }
  .alert-title {
    white-space: normal;
  }
  .alert-summary {
    flex: 1 1 100%;
  }
  .alert-right {
    flex-wrap: wrap;
  }
  .sec-head {
    margin: 10px 0 5px;
  }
  .act-btn {
    height: 36px;
  }
  .heat-band {
    margin-bottom: 6px;
  }
}

/* ---------- 矮屏桌面（1366×768 / 1280×720 投影）：纵向留白再压一档 ----------
   与 Lead 的全局 @media (max-height:800px) 同断点，只管大屏页内部：
   不改数据、不改文案，只压 KPI / 颜色模式条 / 地图工具条的内边距，
   把省下的高度还给地图（目标：地图可视高度 ≥300px、左栏列表 ≥2~3 行）。 */
@media (max-height: 800px) and (min-width: 1181px) {
  .kpi-bar {
    margin: 6px 12px 6px;
  }
  .kpi-cell {
    padding: 6px 10px;
  }
  .kpi-label {
    font-size: 11px;
  }
  .kpi-value {
    margin-top: 2px;
    font-size: 18px;
  }
  .kpi-sub {
    margin-top: 2px;
    font-size: 10px;
  }
  .color-mode-bar {
    margin-bottom: 4px;
    padding: 4px 8px;
  }
  .cm-title {
    font-size: 11px;
  }
  .cm-item {
    height: 22px;
    padding: 0 10px;
    font-size: 11px;
  }
  .cm-note {
    font-size: 10px;
    line-height: 1.4;
  }
  /* 地图工具条回到单行：底图口径文案单行省略（完整文案仍在页脚口径条），
     不再因为换行多吃一行高度。 */
  .map-toolbar {
    padding: 4px 10px;
    gap: 8px;
    flex-wrap: nowrap;
  }
  .map-toolbar-left {
    flex: 1 1 auto;
    min-width: 0;
    flex-wrap: nowrap;
    gap: 6px;
  }
  .map-title {
    white-space: nowrap;
    flex: 0 0 auto;
  }
  .map-tag {
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .map-toolbar-right {
    flex: 0 0 auto;
  }
  .map-caption {
    padding: 4px 10px;
    font-size: 10px;
    line-height: 1.4;
  }
  /* 热力带卡身裁剪 176px → 150px（内容本身有内部滚动，不藏数据） */
  .band-card .td-card-body {
    max-height: 150px;
  }
  .heat-band {
    margin-bottom: 6px;
  }
  .alert-bar {
    padding: 6px 10px;
  }
  .alert-title {
    font-size: 11px;
  }
  .alert-summary,
  .alert-counts,
  .alert-link {
    font-size: 10.5px;
  }
  /* 左栏「选择监控」内部收紧，把高度让给下方路段列表（多出 1~2 行可见） */
  .view-seg {
    margin-bottom: 6px;
  }
  .dist-legend {
    margin-top: 5px;
    gap: 4px 10px;
  }
}

/* ==========================================================================
   全国视角：左右栏收起（Issue IKPFVN E1）
   ==========================================================================
   为什么用 CSS 把面板宽压到 0 + `!important`，而不是改 `colLeft/colRight`：
   ElSplitter 把尺寸写在 panel 的**行内 style** 上（`flex-basis: 296px`），
   且 `:min` 会把它钳住（220 / 280），改成 0 会被 elast 回去；只有带 !important 的
   外部分类能稳定盖住行内值。宽度过渡 250 ms 与地图 `resize()` 配套（见 MapLibreViewer）。
   ⚠️ 本区块放在**所有媒体查询之后**：≤1366 / ≤1180 那两个区块也用 !important 改面板尺寸，
   同权重时按源顺序生效，放最后才能保证“全国视角一定收起”。 */
.el-splitter.td-splitter.is-national :deep(> .el-splitter-panel:first-child),
.el-splitter.td-splitter.is-national :deep(> .el-splitter-panel:last-child) {
  flex: 0 0 0 !important;
  width: 0 !important;
  min-width: 0 !important;
  padding: 0 !important;
  overflow: hidden;
  opacity: 0;
  transition: flex-basis 250ms ease, opacity 250ms ease;
}
/* 两条分隔条也不需要了：少了左右栏，留着就是两根拖不动的死横线 */
.el-splitter.td-splitter.is-national :deep(> .el-splitter-bar) {
  display: none !important;
}
/* 中栏（地图）自己接住腾出来的宽度：ElSplitter 是按“总宽 - 两侧 size”把 px 写在中栏
   行内 `flex-basis` 上的（实测：两侧压成 0 后中栏仍停在 876px，右侧留一大片空白）。
   外部分类把它改成 flex:1，不依赖 ElSplitter 自己重算。 */
.el-splitter.td-splitter.is-national :deep(> .el-splitter-panel:nth-child(3)) {
  flex: 1 1 auto !important;
  width: auto !important;
  min-width: 0 !important;
}

/* 工具条上的「← 全国」小按钮：中性描边，不用品牌蓝（品牌蓝只给“当前 / 已选 / 可操作”） */
.map-back-btn {
  padding: 3px 10px;
  border: 1px solid var(--td-component-stroke);
  border-radius: 4px;
  background: #ffffff;
  font: inherit;
  font-size: 11px;
  color: var(--td-text-color-secondary);
  cursor: pointer;
  white-space: nowrap;
}
.map-back-btn:hover {
  border-color: var(--td-brand-color);
  color: var(--td-brand-color);
}
</style>
