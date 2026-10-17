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
import { useRouter } from 'vue-router'
import {
  getTrafficAlerts,
  getTrafficCiHistory,
  getTrafficFactors,
  getTrafficHeatMatrix,
  getTrafficMeta,
  getTrafficNetwork,
  getTrafficOverview,
  getTrafficSegmentSources,
  getTrafficSegments,
  getTrafficThresholds,
  getTrafficVehicles,
  postRouteRecommend,
  subscribeTrafficSnapshot,
} from '../../api/traffic'
import { demoSegment, networkGeometryNote, networkSourceLabel } from '../../shared/demoNetwork'
import { basemapEnabled } from '../../shared/settings'
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
  type SegmentRecord,
  type SegmentSourcePair,
  type ThresholdSnapshot,
  type TrafficAlert,
  type TrafficNetwork,
  type TrafficOverview,
  type VehicleRecord,
} from '../../shared/traffic'
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

const router = useRouter()

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

// ---------- 本站范围与路段数（Issue IKM4B4）----------
// 来源：`work/twin/site-ranges.json`（每站一份登记表）→ 站点包 station 字段 → 本页只展示。
// 口径：范围是**脚本推定 / 人工圈定**的结果，不是官方划定；页面不报精度数字。
const siteMeta = computed(() => activePack().station)
const RANGE_SOURCE_LABEL: Record<string, string> = {
  manual: '人工圈定',
  script: '脚本推定',
  'ai-assisted': 'AI 辅助候选（已人工确认）',
}
const rangeSourceLabel = computed<string>(() => {
  const src = siteMeta.value.range_source
  return src ? (RANGE_SOURCE_LABEL[src] ?? src) : '来源未登记'
})

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

const selectedName = computed<string>(() => {
  const s = selected.value
  if (!s) return '—'
  return demoSegment(s.segment_id)?.name ?? s.segment_id
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
  if (meta.status === 'fulfilled') stationName.value = meta.value.station.name
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

async function loadRecommend(): Promise<void> {
  recommendLoading.value = true
  recommendError.value = ''
  try {
    const pack = activePack()
    recommend.value = await postRouteRecommend({
      // 演示车固定用站点包的定位锚点（与 App 绑定演示车同一口径）；一期不是真实行程
      session_id: `demo-${pack.key}`,
      location: {
        segment_id: pack.recommend.location_segment_id,
        offset_m: pack.recommend.location_offset_m,
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
        note: '送完人之后的离站方向（契约 departure_route）；一期为演示路线',
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

onMounted(() => {
  void refresh()
  void loadRecommend()
  unsubscribe = subscribeTrafficSnapshot(() => {
    void refresh()
  })
})

onUnmounted(() => {
  unsubscribe?.()
})

// ---------- 文案 / 格式化助手 ----------
const CN_NUM: Record<CongestionLevel, string> = { 1: '一', 2: '二', 3: '三', 4: '四' }

function levelName(seg: SegmentRecord): string {
  return isStale(seg) ? UNAVAILABLE.name : (seg.level_name ?? LEVELS[seg.level].name)
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

const dist = computed<DistRow[]>(() =>
  (overview.value?.level_distribution ?? []).map((r) => ({
    level: r.level,
    name: r.name,
    count: r.count,
    color: r.level === 0 ? UNAVAILABLE.color : LEVELS[r.level].color,
  })),
)

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
}

/** 监控范围过滤(0 = 数据不可用档) */
const scoped = computed<SegmentRecord[]>(() => {
  const s = scope.value
  if (s === null) return segments.value
  if (s === 0) return segments.value.filter((x) => isStale(x))
  return segments.value.filter((x) => !isStale(x) && x.level === s)
})

/** 四级视图:按等级降序、同档按饱和度降序(与默认选中同口径);指数视图:按 CI 降序、不可用排最后 */
const segRows = computed<SegRow[]>(() => {
  const list = [...scoped.value]
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
  const parts = [`${CN_NUM[s.level]}级`, levelName(s)]
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
  return r && ciAvailable(r) ? LEVELS[r.level].text : UNAVAILABLE.color
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
  const avail = segments.value.filter(ciAvailable)
  const out: { level: CongestionLevel; name: string; count: number }[] = []
  for (let lv = 4; lv >= 1; lv--) {
    const lo = CI_BANDS[lv - 1] ?? 0
    const hi = CI_BANDS[lv] ?? 100
    const count = avail.filter((s) => {
      const ci = s.ci as number
      return lv === 4 ? ci >= lo && ci <= hi : ci >= lo && ci < hi
    }).length
    out.push({ level: lv as CongestionLevel, name: LEVELS[lv as CongestionLevel].name, count })
  }
  return out
})

const unavailableCount = computed(() => segments.value.filter((s) => !ciAvailable(s)).length)

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
  void router.push('/decision')
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
      ⚠ 本次刷新未取到:{{ failedPanels.join(' / ') }} —— 这些面板显示的是上一版数据,请勿据此判断当前态势。
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
                    四级视图
                  </span>
                  <span
                    class="td-seg-item"
                    :class="{ on: viewMode === 'index' }"
                    role="button"
                    :aria-pressed="viewMode === 'index'"
                    @click="viewMode = 'index'"
                  >
                    拥挤指数视图
                  </span>
                </div>
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
                    <LevelBadge :level="r.level === 0 ? 1 : r.level" :stale="r.level === 0" />
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
                <span class="td-head-tag">{{ viewMode === 'index' ? '按 CI 降序' : '按等级排序' }}</span>
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
                      <span class="seg-value td-num" :style="{ color: row.stale ? UNAVAILABLE.text : row.text }">
                        <template v-if="row.stale">数据不可用 · 陈旧 {{ row.seg.data_age_s ?? '—' }}s</template>
                        <template v-else>x {{ fmt(row.seg.x) }}</template>
                      </span>
                      <LevelBadge :level="row.seg.level" :stale="row.stale" />
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
        <!-- 推荐路线（Issue IKMF1W）：三态切换 + 演示骨架标注；接口不可达时不画路线、不编造假路线 -->
        <section class="td-card route-card">
          <div class="td-card-head">
            推荐路线
            <span class="td-head-tag">演示骨架 · 连通段拼接</span>
          </div>
          <div class="td-card-body">
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
              <p class="route-why">
                演示路线：在 {{ packSegmentCount }} 段真 OSM 路网上按“相邻段连通”拼出的演示序列，<b>不是</b>引擎 K 最短路 + 预约输出，也<b>不是</b>按当前路况重算出来的结果。
                颜色语义：品牌蓝实线 = 推荐 / 当前，灰虚线 = 备选，紫色实线 = 离站。
              </p>
            </template>
            <p v-else class="route-hint">无推荐数据：保持不画路线（不编造演示路线）</p>
          </div>
        </section>
        <section class="td-card">
          <div class="td-card-head">
            路段信息<span class="td-head-tag td-mono">{{ selected?.segment_id ?? '—' }}</span>
          </div>
          <div class="td-card-body">
            <template v-if="selected">
              <div class="d-title">
                <span class="d-name">{{ selectedName }}</span>
                <LevelBadge :level="selected.level" :stale="isStale(selected)" />
              </div>
              <div class="d-summary">{{ detailSummary }}</div>

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

              <!-- 关联告警(原 /heat 右栏) -->
              <div class="sec-head">
                关联告警<span class="sub-tag">{{ selectedAlerts.length }} 条未闭环</span>
              </div>
              <AlertList :alerts="selectedAlerts" :level-of="segLevelOf" />

              <button class="td-btn primary act-btn" type="button" @click="gotoDecision">
                下发分流方案 ›
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
          档位分布 · 当前时刻<span class="td-head-tag">灰档 {{ unavailableCount }}</span>
        </div>
        <div class="td-card-body">
          <BandDistribution :rows="bandRows" :unavailable="unavailableCount" />
          <p class="note">共 {{ distTotal }} 个路段 · 灰档不计入均值,与地图同源</p>
        </div>
      </section>

      <section class="td-card band-card wide">
        <div class="td-card-head">
          路段 × 时间热力矩阵<span class="td-head-tag">最近 12 个快照 · 每 60 s 一档 · 左旧右新</span>
        </div>
        <div class="td-card-body flush">
          <HeatMatrixTable :matrix="heat" />
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
      <span>本站范围 {{ siteMeta.range_m ?? '—' }} m（{{ rangeSourceLabel }}）· 路段 {{ siteMeta.segment_count ?? segments.length }} 条</span>
      <span>数据来源:mock 示例快照(契约 v2.0)· is_simulated = true · 底图:{{ sourceLabel }}</span>
      <span class="right">
        口径:一期全部示例数据(模拟)· 等级三重编码(颜色 + 竖条 + 文字)· 数据不可用灰显(TC-11)· {{ CI_DISCLAIMER }}
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
</style>
