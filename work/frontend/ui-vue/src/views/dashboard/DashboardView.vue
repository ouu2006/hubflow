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
  getTrafficNetwork,
  getTrafficOverview,
  getTrafficRouteOptions,
  getTrafficSegmentSources,
  getTrafficSegments,
  getTrafficThresholds,
  getTrafficVehicles,
  postRouteRecommend,
  subscribeTrafficSnapshot,
} from '../../api/traffic'
import { demoSegment, networkGeometryNote, networkSourceLabel } from '../../shared/demoNetwork'
import { basemapEnabled } from '../../shared/settings'
import { USE_MOCK } from '../../shared/env'
import { cameraCountOf } from '../../shared/cameras'
import { activePack, activePackKey, packItems, switchPack } from '../../station-packs/index'
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
  type FactorApplied,
  type HeatMatrix,
  type RecommendResult,
  type RouteHighlight,
  type RouteOption,
  type RouteOptionsSnapshot,
  type SegmentRecord,
  type SegmentSourcePair,
  type ThresholdSnapshot,
  type TrafficAlert,
  type TrafficMeta,
  type TrafficNetwork,
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

/** 三栏回到默认宽度(左 296 / 中弹性 / 右 396)。双击分隔条时调用;默认态即此值,故本函数幂等 */
function resetCols(): void {
  colLeft.value = COL_DEFAULT_LEFT
  colRight.value = COL_DEFAULT_RIGHT
  saveColMem()
}

loadColMem()

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

/** 路网来源短文案(页面页脚口径用):桥接覆盖过就是真路网,否则报包自己的口径 */
const sourceLabel = networkSourceLabel()
/** 路网几何出处(真值 / 示例样例)—— 真几何与示意几何不能混说(见 demoNetwork.networkGeometryNote) */
const geometryNote = networkGeometryNote()

/** 中栏工具条上的底图口径:顶栏「设置」里的**底图开关**状态直接反映出来(业主 2026-10-16) */
const basemapTag = computed(() =>
  basemapEnabled.value
    ? '底图：OpenFreeMap · OSM（拉不到时只画路网）'
    : '底图：已关闭 · 只画路网（顶栏「设置」里可开）',
)

/** 图下注脚:底图关掉时**不许**再写"底图来源:OpenFreeMap" —— 页面不撒谎 */
const mapCaption = computed(() =>
  basemapEnabled.value
    ? `底图来源:OpenFreeMap(OpenStreetMap 数据,ODbL)· 署名见地图内 · 不缓存瓦片 · 路网:${geometryNote}`
    : `底图已在顶栏「设置」里关闭 · 只画路网 · 路网:${geometryNote} · OSM 署名见地图内`,
)
/** 站点名(顶栏 chip):默认取当前站点包,拿到 meta 后由 meta.station.name 覆盖 —— 三页同一口径 */
const stationName = ref(activePack().station.name)
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
const siteMeta = computed(() => activePack().station)
const RANGE_SOURCE_LABEL: Record<string, string> = {
  manual: '人工圈定',
  script: '脚本推定',
  'ai-assisted': 'AI 辅助候选（已人工确认）',
}

// 大屏工具条上的「路网版本」切换（IKMDKY 子单①）：Z = 61 段新几何 / Z21 = 旧 21 段对照。
// 与顶栏「线路图切换器」同一支 switchPack()——整页刷新后路网、基线、摄像头映射一起换。
const packChoices = packItems()
const currentPackKey = activePackKey()
function onPackChange(key: string): void {
  if (key === currentPackKey) return
  switchPack(key)
  window.location.reload()
}

// ---------- 快照状态 ----------
const overview = ref<TrafficOverview | null>(null)
const segments = ref<SegmentRecord[]>([])
const vehicles = ref<VehicleRecord[]>([])
const network = ref<TrafficNetwork | null>(null)
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
/** 本次刷新中失败的接口(页头提示用;失败面板保留旧值但必须标"上一版",不得冒充当前) */
const failedPanels = ref<string[]>([])
/** SSE 刷新通道连接状态:断开时页面不会自动刷新,必须显式提示(TC-06 断流降级) */
const sseConnected = ref(true)

const PANEL_LABEL: Record<string, string> = {
  overview: 'KPI',
  segments: '路段监测',
  vehicles: '车辆',
  network: '路网',
  alerts: '告警',
  factors: '因素',
  matrix: '热力矩阵',
  thresholds: '阈值与 CI 权重',
}

async function refresh(): Promise<void> {
  const seq = ++refreshSeq
  const [ov, seg, veh, net, al, fa, meta, matrix, thr] = await Promise.allSettled([
    getTrafficOverview(),
    getTrafficSegments(),
    getTrafficVehicles(),
    getTrafficNetwork(),
    getTrafficAlerts(),
    getTrafficFactors(),
    getTrafficMeta(),
    getTrafficHeatMatrix(12, 60),
    getTrafficThresholds(),
  ])
  if (seq !== refreshSeq) return // 已被更晚的一次刷新取代:丢弃本次响应
  const failed: string[] = []
  const track = (name: string, ok: boolean): void => {
    if (!ok) failed.push(PANEL_LABEL[name] ?? name)
  }
  if (ov.status === 'fulfilled') overview.value = ov.value
  track('overview', ov.status === 'fulfilled')
  if (seg.status === 'fulfilled') {
    segments.value = seg.value.segments
    snapshotTs.value = seg.value.ts
    if (selectedId.value === null) selectedId.value = pickDefaultId(seg.value.segments)
    applyDeepSegment()
  }
  track('segments', seg.status === 'fulfilled')
  if (veh.status === 'fulfilled') vehicles.value = veh.value.vehicles
  track('vehicles', veh.status === 'fulfilled')
  if (net.status === 'fulfilled') network.value = net.value
  track('network', net.status === 'fulfilled')
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
    stationName.value = meta.value.station.name
  }
  failedPanels.value = failed
  await loadSelectedSide(selectedId.value)
}

watch(selectedId, (id) => {
  void loadSelectedSide(id)
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
/** 三态切换：全部 / 推荐 / 备选 / 离站（截图三态用同一套按钮） */
const routeView = ref<RouteView>('all')
/** 当前站点包内的段数（卡片文案用；切包后不写死 61） */
const packSegmentCount = computed(() => activePack().segments.length)
/** 当前站点包内的段号集合：路线引用的段必须都在包里，防悬空画假线 */
const packSegmentIds = new Set(activePack().segments.map((s) => s.segment_id))

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

/** 地图要高亮的路线分组（按 routeView 过滤；无数据时为空数组） */
const routeHighlights = computed<RouteHighlight[]>(() => {
  const r = recommend.value
  if (!r) return []
  const groups: RouteHighlight[] = []
  if (routeView.value === 'all' || routeView.value === 'arrival') {
    groups.push({ kind: 'arrival', segments: r.arrival_route.segments })
  }
  if (routeView.value === 'all' || routeView.value === 'alternative') {
    for (const a of r.alternatives) {
      if (a.segments && a.segments.length > 0) groups.push({ kind: 'alternative', segments: a.segments })
    }
  }
  if (routeView.value === 'all' || routeView.value === 'departure') {
    if (r.departure_route && r.departure_route.segments.length > 0) {
      groups.push({ kind: 'departure', segments: r.departure_route.segments })
    }
  }
  return groups
})

interface RouteCard {
  key: string
  kind: RouteHighlight['kind']
  kindName: string
  pathId: string
  eta: number
  segments: string[]
  note: string
}

/** 右栏路线卡片（与地图用同一份 recommend 数据，不另算） */
const routeCards = computed<RouteCard[]>(() => {
  const r = recommend.value
  if (!r) return []
  const cards: RouteCard[] = []
  if (routeView.value === 'all' || routeView.value === 'arrival') {
    cards.push({
      key: 'arrival',
      kind: 'arrival',
      kindName: '推荐路线',
      pathId: r.arrival_route.path_id,
      eta: r.arrival_route.eta_min,
      segments: r.arrival_route.segments,
      note: r.why,
    })
  }
  if (routeView.value === 'all' || routeView.value === 'alternative') {
    r.alternatives.forEach((a, i) => {
      cards.push({
        key: `alt-${a.path_id}-${i}`,
        kind: 'alternative',
        kindName: `备选 ${i + 1}`,
        pathId: a.path_id,
        eta: a.eta_min,
        segments: a.segments ?? [],
        note: a.reason,
      })
    })
  }
  if (routeView.value === 'all' || routeView.value === 'departure') {
    if (r.departure_route) {
      cards.push({
        key: 'departure',
        kind: 'departure',
        kindName: '离站路线',
        pathId: r.departure_route.path_id,
        eta: r.departure_route.eta_min,
        segments: r.departure_route.segments,
        note: '送完人之后的离站方向（契约 departure_route）',
      })
    }
  }
  return cards
})

/** 路线里引用了当前站点包不存在的段号 → 如实提示（不画点不出的段） */
const routeMissing = computed<string[]>(() => {
  const missing = new Set<string>()
  for (const g of routeHighlights.value) {
    for (const id of g.segments) if (!packSegmentIds.has(id)) missing.add(id)
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
    return '接口层只端引擎算路产物（真网产物优先、样例产物回退），不代算 ETA；颜色语义：品牌蓝实线 = 推荐 / 当前，灰虚线 = 备选，紫色实线 = 离站。'
  }
  return `演示路线：在 ${packSegmentCount.value} 段真 OSM 路网上按“相邻段连通”拼出的演示序列，不是引擎 K 最短路 + 预约输出，也不是按当前路况重算出来的结果。颜色语义：品牌蓝实线 = 推荐 / 当前，灰虚线 = 备选，紫色实线 = 离站。`
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
})

onUnmounted(() => {
  unsubscribe?.()
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
// 极简口径(业主 2026-10-14):图上只画路段线,断面/落客点/场区/站点不再下发地图;
// 文字只出现在跟随鼠标的浮牌(hover-chip)里。

/** 选中 chip:路段拥堵 · 摄像头 2 路 · x 0.91 / 0.84(video/twin);video 不可用只显示 twin 并注明 */
const mapChip = computed<string>(() => {
  // 摄像头数按**段号**现算(Issue IKLX5Y),不看有没有快照记录:
  // 没有摄像头的那 16 段**本来就没有记录**,若等记录才拼浮牌,这些段悬停时什么都没有
  // —— 那就答不上"每段可查摄像头数、没有的如实显示 0"。
  const id = selectedId.value
  if (!id) return ''
  const cam = `摄像头 ${cameraCountOf(id)} 路`
  const s = selected.value
  const flow = isFlow.value
  if (flow) {
    // 纯车流量版（IKNB9G）：浮牌只报 q 与流量档位，不写等级/CI（避免把流量读成拥堵结论）
    if (!s) return `${id} 无流量记录 · ${cam}`
    const band = flowBandOf(s)
    const qText = band ? `q ${fmt(s.q_vph, 0)} 辆/h` : FLOW_UNAVAILABLE_LABEL
    return `${s.segment_id} ${band ? band.name : FLOW_UNAVAILABLE_LABEL} · ${qText} · ${cam}（流量版：仅按 q 分档）`
  }
  if (!s) return `${id} 无路况记录 · ${cam}`
  const v = pair.value?.slots.find((x) => x.source === 'video')
  const t = pair.value?.slots.find((x) => x.source === 'twin')
  const vx = v?.record?.x
  const tx = t?.record?.x
  const head = `${s.segment_id} ${levelName(s)} · ${cam}`
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
      <el-splitter class="el-splitter td-splitter" @resize-end="saveColMem" @mousedown="onBarMouseDown">
        <!-- `v-model:size` 而不是 `:size`:单向绑定不会把 ElSplitter 拖出来的 px 宽度
             回写到 colLeft/colRight,那样 @resize-end 存的一直是默认值,记忆功能等于没有。
             两个 ref 都是 `number | string`(元素自身声明 `size: { type: [String, Number] }`)。 -->
        <el-splitter-panel v-model:size="colLeft" :min="COL_MIN_LEFT">
          <!-- 左栏 · 选择监控 -->
          <div class="td-col col-left">
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
                      {{ scope === null ? '快照为空(接口层未起?)' : '该范围当前没有路段' }}
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
                  <span class="map-title">全路段状态</span>
                  <span class="map-tag">{{ basemapTag }}</span>
                </div>
                <!-- 路网版本切换（IKMDKY 子单①）：Z=61 段新几何 / Z21=旧 21 段对照 -->
                <div class="map-toolbar-right">
                  <span class="pack-switch" role="group" aria-label="切换路网版本">
                    <button
                      v-for="p in packChoices"
                      :key="p.key"
                      type="button"
                      class="pack-switch-item"
                      :class="{ on: p.key === currentPackKey }"
                      :aria-pressed="p.key === currentPackKey"
                      @click="onPackChange(p.key)"
                    >
                      {{ p.name }}
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
                  :mode="viewMode"
                  :color-mode="colorMode"
                  :ts="snapshotTs"
                  :hover-chip="mapChip"
                  :legend="true"
                  @select="onSelect"
                />
              </div>
              <div class="map-caption">
                {{ mapCaption }}
              </div>
            </section>
          </div>
        </el-splitter-panel>

        <el-splitter-panel v-model:size="colRight" :min="COL_MIN_RIGHT">
          <!-- 右栏 · 路段信息 -->
          <div class="td-col col-right td-scroll">
        <!-- 推荐路线（Issue IKMF1W）：三态切换 + 来源标注；接口不可达时不画路线、不编造假路线 -->
        <section class="td-card route-card">
          <div class="td-card-head">
            推荐路线
            <span class="td-head-tag">{{ routeSourceTag }}</span>
          </div>
          <div class="td-card-body">
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
                    {{ option.od_id ?? 'OD' }} · {{ option.session_id }} · 到达
                    {{ fmtEta(option.arrival_route?.eta_min) }} min
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
                <span>
                  起点 {{ recommend.location.segment_id }} · 定位来源
                  {{ recommend.location.source === 'twin' ? '孪生真值' : 'App 定位' }}
                </span>
              </div>
              <p v-if="routeSourceNote" class="route-source">{{ routeSourceNote }}</p>
              <div v-for="c in routeCards" :key="c.key" class="route-item" :class="c.kind">
                <div class="route-item-head">
                  <span class="route-kind">{{ c.kindName }}</span>
                  <span class="route-eta td-num">{{ c.eta }} min</span>
                </div>
                <div class="route-segs td-mono">{{ c.segments.join(' → ') || '—' }}</div>
                <div class="route-note">{{ c.note }}</div>
              </div>
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

    <!-- 底部热力带(原 /heat:档位分布 | 路段×时间热力矩阵 | CI 色阶与口径) -->
    <div class="heat-band">
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
      <span>{{ footStationLine }}</span>
      <span>数据来源:{{ footDataSource }} · 底图:{{ sourceLabel }}</span>
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

/* ---------- 底部热力带(原 /heat 三栏内容) ---------- */
.heat-band {
  flex: 0 0 auto;
  display: flex;
  gap: 10px;
  margin: 0 16px 8px;
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
  border-left: 3px solid #0052d9;
}
.route-item.alternative {
  border-left-color: #8c8c8c;
}
.route-item.departure {
  border-left-color: #7b61ff;
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

/* 右栏顺序（Issue IKMS18）：点路段后**先看路段信息**（关联摄像头 / 决策计算摘要 / 直接下令），
   推荐路线卡排在其后 —— 监控管理平台的操作面板优先，不是删掉路线能力（C-2 一项不删）。
   .td-col 是 flex column，用 order 调整顺序，不改 DOM 结构。 */
.col-right > .td-card:not(.route-card) {
  order: 1;
}
.col-right > .route-card {
  order: 2;
}
</style>
