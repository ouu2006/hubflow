import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { getTrafficAlerts, getTrafficCiHistory, getTrafficFactors, getTrafficHeatMatrix, getTrafficMeta, getTrafficOverview, getTrafficRouteOptions, getTrafficSegmentSources, getTrafficSegments, getTrafficThresholds, getTrafficVehicles, postRouteRecommend, postTrafficLocate, subscribeTrafficSnapshot, } from '../../api/traffic';
import { demoSegment, networkGeometryNote, networkSourceLabel } from '../../shared/demoNetwork';
import { basemapEnabled, directionsVisible, legendVisible, setDirectionsVisible, setLegendVisible, } from '../../shared/settings';
import { USE_MOCK } from '../../shared/env';
import { cameraCountOf } from '../../shared/cameras';
// IKOQEJ：方向 / 车道 / 对向 / 贯通（只读 enriched 生成字段；缺值→未标定，不编）
import { continuityOf, directionKindOf, directionLabel, directionOf, directionSourceLabel, lanesOf, oppositeOf, } from '../../shared/directions';
import { activePack, activePackKey, onPackChange, packItems, packNote, packVersion } from '../../station-packs/index';
import { bindStationSwitch, switchStation } from '../../shared/stationSwitch';
import { schedulePrewarm, writeStationCache } from '../../shared/stationCache';
import { TD } from '../../shared/theme';
import { alertLevelOf, ciAvailable, CI_BAND_NOTE, CI_BANDS, CI_DISCLAIMER, formatClock, formatStamp, isStale, LEVELS, levelStyle, UNAVAILABLE, } from '../../shared/traffic';
import { COLOR_MODE_QUERY_KEY, COLOR_MODE_STORAGE_KEY, FLOW_BANDS, FLOW_COLOR_NOTE, FLOW_MODE_LABEL, FLOW_MODE_NOTE, FLOW_UNAVAILABLE_LABEL, flowBandOf, flowRangeLabel, parseColorMode, storeColorMode, } from '../../shared/flow';
import AppShell from '../../components/AppShell.vue';
import LevelBadge from './components/LevelBadge.vue';
import MapLibreViewer from './components/MapLibreViewer.vue';
import AlertList from './components/AlertList.vue';
import BandDistribution from './components/BandDistribution.vue';
import CiScale from './components/CiScale.vue';
import CiTrendBars from './components/CiTrendBars.vue';
import FactorBreakdown from './components/FactorBreakdown.vue';
import HeatMatrixTable from './components/HeatMatrixTable.vue';
import SegmentRankTable from './components/SegmentRankTable.vue';
import SegmentCameraCard from './components/SegmentCameraCard.vue';
import SegmentDecisionSummary from './components/SegmentDecisionSummary.vue';
import SegmentDispatchCard from './components/SegmentDispatchCard.vue';
const router = useRouter();
const route = useRoute();
// ---------- 深链选中（Issue IKMS18）：#/dashboard?segment=SZ-010 ----------
// 语义：站点包存在的段即可选中（地图上任一段都可点）；快照没覆盖的段由详情卡按「无数据」降级。
// 用于从别的页面 / 外链直接定位某段看摄像头与下令，不改变默认选中逻辑。
const deepSegment = computed(() => {
    const raw = route.query.segment;
    return typeof raw === 'string' ? raw : Array.isArray(raw) ? (raw[0] ?? '') : '';
});
let deepApplied = false;
/** 段号是否可选：站点包几何里有，或当前快照里有（快照段号不一定在包里，允许深链选中） */
function isSelectableSegment(id) {
    if (!id)
        return false;
    return Boolean(demoSegment(id)) || segments.value.some((item) => item.segment_id === id);
}
function applyDeepSegment() {
    const id = deepSegment.value;
    if (!id || deepApplied)
        return;
    deepApplied = true;
    if (isSelectableSegment(id))
        selectedId.value = id;
}
watch(deepSegment, (id) => {
    if (id && isSelectableSegment(id)) {
        deepApplied = true;
        selectedId.value = id;
    }
});
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
const COL_DEFAULT_LEFT = 296;
const COL_DEFAULT_RIGHT = 396;
const COL_MIN_LEFT = 220;
const COL_MIN_MID = 320;
const COL_MIN_RIGHT = 280;
/** 记忆用户拖过的宽度(可选加分项 #5);键名带页面前缀,不与别的页串味 */
const COL_MEM_KEY = 'hubflow.dashboard.colWidth';
/** 左栏 / 右栏宽度(px)。中栏弹性,不给 size —— 交给 ElSplitter 自动伸缩(第 1 条判定) */
const colLeft = ref(COL_DEFAULT_LEFT);
const colRight = ref(COL_DEFAULT_RIGHT);
/** 拖完写一次记忆。切页 / 刷新时读回来;读不到或读坏了就用默认值,不影响可用性 */
function loadColMem() {
    try {
        const raw = localStorage.getItem(COL_MEM_KEY);
        if (!raw)
            return;
        const v = JSON.parse(raw);
        if (typeof v.left === 'number' && Number.isFinite(v.left))
            colLeft.value = v.left;
        if (typeof v.right === 'number' && Number.isFinite(v.right))
            colRight.value = v.right;
    }
    catch {
        /* localStorage 不可用 / 内容坏了:静默退回默认值,不算错 */
    }
}
/**
 * 拖完写一次记忆。切页 / 刷新时读回来;读不到或读坏了就用默认值,不影响可用性。
 * `ElSplitter` 的 `resize-end` 形参是 `(index, pxSizes)`,第二个是全量 px 宽度数组,
 * 但**不要**拿它算要记的值:左/右两栏已由 `v-model:size` 同步到 colLeft/colRight,
 * 直接记这两个即可(中栏是弹性栏,宽度由两侧和视口决定,记了下次打开也对不上)。
 */
function saveColMem() {
    try {
        localStorage.setItem(COL_MEM_KEY, JSON.stringify({ left: colLeft.value, right: colRight.value }));
    }
    catch {
        /* 隐私模式等场景写不进去:不影响拖拽本身,只是不记忆 */
    }
}
/** 三栏回到默认宽度(左 296 / 中弹性 / 右 396)。双击分隔条时调用;默认态即此值,故本函数幂等 */
function resetCols() {
    colLeft.value = COL_DEFAULT_LEFT;
    colRight.value = COL_DEFAULT_RIGHT;
    saveColMem();
}
loadColMem();
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
const DBL_MS = 400;
let lastBarDown = { at: 0, x: 0, y: 0 };
function onBarMouseDown(e) {
    const t = e.target;
    if (!t || !t.classList.contains('el-splitter-bar__dragger'))
        return;
    const now = e.timeStamp || Date.now();
    // 同一根分隔条、相邻 400ms 内的第二次按下 = 双击
    if (now - lastBarDown.at < DBL_MS && Math.abs(e.clientX - lastBarDown.x) < 8 && Math.abs(e.clientY - lastBarDown.y) < 8) {
        lastBarDown = { at: 0, x: 0, y: 0 };
        resetCols();
        return;
    }
    lastBarDown = { at: now, x: e.clientX, y: e.clientY };
}
/**
 * 包键代号（Issue IKPFR4）：切站时 +1。
 * `activePack()` / `demoSegment()` 读的是**模块级变量**，Vue 不知道它变了 —— 所有
 * "由站点包派生"的 computed 显式读一次 `packTick.value`，切站才能自动重算。
 */
const packTick = ref(packVersion());
/** 当前包键（工具条按钮的选中态 / 切站早退判断用）：跟着 packTick 走，不再是一次性常量 */
const currentPackKey = ref(activePackKey());
const offPackTick = onPackChange(() => {
    packTick.value = packVersion();
    currentPackKey.value = activePackKey();
    // IKPFVN E2：顶栏「线路图切换器」也走同一个 `switchStation()`，本页只收到包键变更通知 ——
    // 据它把视角切到站区，否则用户从顶栏选了站、大屏还停在全国视角看 pin。
    if (mapScope.value !== 'station')
        mapScope.value = 'station';
});
/** 路网来源短文案(页面页脚口径用):桥接覆盖过就是真路网,否则报包自己的口径 */
const sourceLabel = computed(() => {
    void packTick.value;
    return networkSourceLabel();
});
/** 路网几何出处(真值 / 示例样例)—— 真几何与示意几何不能混说(见 demoNetwork.networkGeometryNote) */
const geometryNote = computed(() => {
    void packTick.value;
    return networkGeometryNote();
});
/** 页脚站点包自检（`packNote()`：包键 + 这个包是什么）——切站后跟着换，不只报站名 */
const packLine = computed(() => {
    void packTick.value;
    return packNote();
});
/** 中栏工具条上的底图口径:顶栏「设置」里的**底图开关**状态直接反映出来(业主 2026-10-16) */
const basemapTag = computed(() => basemapEnabled.value
    ? '底图：OpenFreeMap · OSM（拉不到时只画路网）'
    : '底图：已关闭 · 只画路网（顶栏「设置」里可开）');
/** 图下注脚:底图关掉时**不许**再写"底图来源:OpenFreeMap" —— 页面不撒谎 */
const mapCaption = computed(() => basemapEnabled.value
    ? `底图来源:OpenFreeMap(OpenStreetMap 数据,ODbL)· 署名见地图内 · 不缓存瓦片 · 路网:${geometryNote.value}`
    : `底图已在顶栏「设置」里关闭 · 只画路网 · 路网:${geometryNote.value} · OSM 署名见地图内`);
/**
 * 站点名(顶栏 chip):默认取当前站点包,拿到 meta 后由 meta.station.name 覆盖 —— 三页同一口径。
 *
 * ⚠️ IKPFR4：兜底值改成 computed（原先是 `ref(activePack().station.name)` 的 setup 期快照，
 *    切站不刷新就永远停在上一站的站名）。meta 那份仍存在独立的 ref 里，切站即清空 ——
 *    让"站名先回落站点包、meta 回来再覆盖"，两站之间不串味。
 */
const metaStationName = ref(null);
const stationName = computed(() => {
    if (metaStationName.value)
        return metaStationName.value;
    void packTick.value;
    return activePack().station.name;
});
/** 接口层 meta(真接口模式:页脚数据来源 / 站点范围 / 快照段数如实取自响应;mock 侧字段可缺省) */
const metaInfo = ref(null);
/**
 * 页脚数据来源(真接口模式):不再是写死的「mock 示例快照」——
 * 路段快照数据源 / 路线来自真网还是样例 / 写端点内存态，一律以接口响应为准。
 */
const footDataSource = computed(() => {
    const ds = metaInfo.value?.data_sources;
    if (!ds) {
        // mock 模式 meta 没有 data_sources 角标(接口层字段)：如实说 mock 示例快照，不冒充真接口
        return USE_MOCK
            ? 'mock 示例快照（契约 v2.0）· is_simulated = true'
            : '数据来源未取到（接口层未起?）· is_simulated = true';
    }
    const parts = [`路段快照数据源 ${ds.segments ?? '—'}`];
    if (ds.routes)
        parts.push(`路线 ${ds.routes_note ?? ds.routes}`);
    else
        parts.push('路线产物缺失（不画路线）');
    if (ds.manual_factors)
        parts.push(`人工置位 ${ds.manual_factors} 条（内存态）`);
    if (ds.scenario_injected)
        parts.push('场景已注入（内存态）');
    return `${parts.join(' · ')} · is_simulated = true`;
});
/** 页脚站点范围:接口 meta 优先(真接口) → 站点包兜底;站点包路网段数 与 本次快照段数分开说，不混算 */
const footStationLine = computed(() => {
    const station = metaInfo.value?.station;
    const range = station?.range_m ?? siteMeta.value.range_m;
    const sourceKey = station?.range_source ?? siteMeta.value.range_source;
    const source = sourceKey ? (RANGE_SOURCE_LABEL[sourceKey] ?? sourceKey) : '来源未登记';
    const snapshotCount = station?.segment_count ?? segments.value.length;
    return `本站范围 ${range ?? '—'} m（${source}）· 站点包路网 ${packSegmentCount.value} 段 · 本次快照 ${snapshotCount} 段`;
});
// ---------- 本站范围与路段数（Issue IKM4B4）----------
// 来源：`work/twin/site-ranges.json`（每站一份登记表）→ 站点包 station 字段 → 本页只展示。
// 口径：范围是**脚本推定 / 人工圈定**的结果，不是官方划定；页面不报精度数字。
const siteMeta = computed(() => {
    void packTick.value;
    return activePack().station;
});
const RANGE_SOURCE_LABEL = {
    manual: '人工圈定',
    script: '脚本推定',
    'ai-assisted': 'AI 辅助候选（已人工确认）',
};
// 大屏工具条上的「路网版本」切换（IKMDKY 子单①；IKP5D3 起只剩 Z=61 段 / GZ=708 段两个真站包，Z21 旧包已删）。
// 与顶栏「线路图切换器」**共用同一支** `switchStation()`（IKPFR4）：
// 切包 → 重建路网几何 → 站内状态一律重置 → 缓存优先渲染首屏 → 后台补拉 → 同步 URL。
// 不再整页刷新（原因见 `shared/stationSwitch.ts` 头部与本文件 `resetStationState()`）。
const packChoices = packItems();
/** 合法包键集合（URL 参数校验 / 自动飞入校验共用，不另址一份名单） */
const PACK_KEYS = new Set(packChoices.map((p) => p.key));
/**
 * 首屏视角：`?station=Z|GZ` 直达站区；`?pack=` 是 IKPFR4 已有的**等价参数**（同一语义：指定当前站），
 * 两个都认（取值相同不会打架）；缺省 → 全国视角首屏。
 */
function initialMapScope() {
    const raw = route.query.station ?? route.query.pack;
    const key = typeof raw === 'string' ? raw : '';
    return PACK_KEYS.has(key) ? 'station' : 'national';
}
const mapScope = ref(initialMapScope());
/**
 * 到站门控（IKPFVN D 节时序）：业主口径是“镜头到站 → 路线显示、信息切换”，
 * 所以页面数据要**等到站再落地**：
 *   · `arriving = true`（切站一开始）→ `refresh()` 的响应先挂住不写面板，骨架屏继续亮；
 *   · 地图组件 `arrived` → `markArrived()` 放行，数据一次性铺上去；
 *   · 兜底 4 s：镜头动画异常 / 地图还没建好（`arrived` 不会来）时，数据不能永远不落地。
 */
const arriving = ref(false);
const ARRIVE_TIMEOUT_MS = 4000;
let arriveWaiters = [];
let arriveTimer = 0;
function whenArrived() {
    if (!arriving.value)
        return Promise.resolve();
    return new Promise((resolve) => {
        arriveWaiters.push(resolve);
        window.clearTimeout(arriveTimer);
        arriveTimer = window.setTimeout(() => markArrived(), ARRIVE_TIMEOUT_MS);
    });
}
function markArrived() {
    window.clearTimeout(arriveTimer);
    arriveTimer = 0;
    if (arriving.value) {
        arriving.value = false;
        const waiters = arriveWaiters;
        arriveWaiters = [];
        for (const resolve of waiters)
            resolve();
    }
    flushPendingCache();
}
/** 缓存快照先挂在一边，到站后再铺（见 `arriving` 的说明） */
let pendingCache = null;
let pendingCacheReady = false;
function flushPendingCache() {
    if (!pendingCacheReady)
        return;
    const snapshot = pendingCache;
    pendingCacheReady = false;
    pendingCache = null;
    commitCachedSnapshot(snapshot);
}
// 首屏自动飞入（IKPFVN E4，业主推荐的 A 方案）：
// 默认全国视角；上次选过的站（`localStorage` 里那份）在 1.2 s 后自动飞进去 ——
// 但**用户一碰就取消**（点 pin / 点浮层卡片 / 点工具条 / 点「← 全国」）。
const AUTO_FLY_DELAY_MS = 1200;
const AUTO_FLY_STORAGE_KEY = 'hubflow.stationPack';
let autoFlyTimer = 0;
let autoFlyCancelled = false;
function cancelAutoFly() {
    autoFlyCancelled = true;
    window.clearTimeout(autoFlyTimer);
    autoFlyTimer = 0;
}
function scheduleAutoFly() {
    if (mapScope.value !== 'national')
        return;
    let saved = null;
    try {
        saved = localStorage.getItem(AUTO_FLY_STORAGE_KEY);
    }
    catch {
        saved = null; // 隐私模式：读不到就不飞，首屏保持全国视角，不算错
    }
    if (!saved || !PACK_KEYS.has(saved))
        return;
    const key = saved;
    autoFlyTimer = window.setTimeout(() => {
        autoFlyTimer = 0;
        if (autoFlyCancelled || mapScope.value !== 'national')
            return;
        pickStation(key);
    }, AUTO_FLY_DELAY_MS);
}
/**
 * 选站（全国浮层卡片 / 站点 pin / 工具条按钮三处**共用**这一个入口）。
 *
 * 切站本身仍只走 `shared/stationSwitch.ts` 的 `switchStation()`；这里只多做两件事：
 * “把视角切到站区”（镜头由地图组件按 `mapScope` 跑）与取消首屏自动飞入。
 */
function pickStation(key) {
    cancelAutoFly();
    if (!PACK_KEYS.has(key)) {
        mapScope.value = 'national';
        return;
    }
    mapScope.value = 'station';
    // `switchStation` 返回 false = 就是当前站：包没变，但镜头仍要从全国飞进去一次。
    // 过渡期并行拉目标站数据：`refresh()` 会拿目标站的 8 个只读快照，并写进该站自己的
    // `stationCache` 桶（等价于预热；再额外调一次 `prefetchStation` 只会把每个接口打两遍）。
    // 数据真正上屏在“到站”之后，见 `arriving` / `whenArrived()`。
    switchStation(key);
}
/** 退回全国视角（工具条「← 全国」）：包不换，只换看多远；站内选中态一并清掉 */
function enterNational() {
    cancelAutoFly();
    mapScope.value = 'national';
    selectedId.value = null;
}
/** 地图组件报“镜头已落到站区” —— 放行页面数据 */
function onMotionArrived() {
    markArrived();
}
// ---------- 快照状态 ----------
const overview = ref(null);
const segments = ref([]);
const vehicles = ref([]);
const alerts = ref([]);
/** 全网生效因素(各路段 factors_applied 展平,供 KPI 第 4 格取前 3 条) */
const allFactors = ref([]);
/** 选中路段的双源并排(video / twin + 差值,TC-19 展示侧) */
const pair = ref(null);
/** 选中路段的生效因素 */
const segFactors = ref([]);
/** 选中路段的 CI 走势(原 /heat 右栏) */
const history = ref(null);
/** 路段 × 时间热力矩阵(原 /heat 中栏) */
const heat = ref(null);
/** 判级阈值 + CI 四项加权构成(原 /heat 右栏;权重不写死,来自接口) */
const thresholds = ref(null);
const selectedId = ref(null);
/** 数据源视图(顶栏)：决定右栏「双数据源并排」表按哪一侧口径读数 */
const sourceMode = ref('both');
/** 视图模式:四级视图(判级产出)/ 拥挤指数视图(展示量,原 /heat 页头切换) */
const viewMode = ref('level');
// ---------- 颜色模式（Issue IKNB9G，业主 2026-10-18）----------
// 两套颜色，二选一，切换即时重绘（地图 / 列表 / 图例 / 热力 / 排序）：
//   · congestion（默认）= 决策拥堵版：按接口 level 四级判级配色（C-2 既有行为，不改判级）；
//   · flow = 纯车流量版：按 q_vph 分四档（阈值集中在 shared/flow.ts），**仅展示、不参与判级**。
// 持久化：localStorage 键 `hubflow.dashboard.colorMode`；`?color=flow|congestion` 深链可覆盖一次。
// 口径：flow 只用 q，不读 level / CI；缺 q 或数据陈旧 → 灰档「无流量数据」；不宣称 YOLO 已实装。
function initialColorMode() {
    const fromQuery = parseColorMode(route.query[COLOR_MODE_QUERY_KEY]);
    if (fromQuery)
        return fromQuery;
    try {
        return parseColorMode(localStorage.getItem(COLOR_MODE_STORAGE_KEY)) ?? 'congestion';
    }
    catch {
        return 'congestion';
    }
}
const colorMode = ref(initialColorMode());
const isFlow = computed(() => colorMode.value === 'flow');
storeColorMode(colorMode.value);
watch(() => route.query[COLOR_MODE_QUERY_KEY], (raw) => {
    const mode = parseColorMode(raw);
    if (mode && mode !== colorMode.value)
        applyColorMode(mode);
});
/** 切模式：写 localStorage；flow 下不提供 CI 视图（CI 是决策口径），自动回四级视图 */
function applyColorMode(mode) {
    colorMode.value = mode;
    storeColorMode(mode);
    if (mode === 'flow' && viewMode.value === 'index')
        viewMode.value = 'level';
}
function setColorMode(mode) {
    if (colorMode.value === mode)
        return;
    applyColorMode(mode);
}
/** 监控范围筛选(左栏「选择监控」):null = 全部;0 = 数据不可用档 */
const scope = ref(null);
const snapshotTs = ref('');
// ---------- 中栏地图 · 单渲染器(Issue IKM5T1) ----------
// 只留**一个**地图组件(MapLibre:矢量底图 + 描出的路网)。原先"示例路网 / 矢量地图"两个模式已删:
//   · 自绘那套(NetMap.vue)的四件事——车辆动点 / 悬停浮牌 / 推荐路线 / 图例+水印——搬进了地图组件;
//   · 而"示例路网"那个观感**在底图拉不出来时自动出现**:地图先用本地兜底样式建起来、路网立刻画,
//     底图失败只丢底图(详见 `components/MapLibreViewer.vue` 头部注释)。
// 只剩站点包 Z、几何统一 WGS-84,所以不再需要"按包 / 按路网切底图"的分支。
let unsubscribe = null;
const selected = computed(() => segments.value.find((s) => s.segment_id === selectedId.value) ?? null);
// Issue IKMS18：允许选中**站点包里但快照没覆盖**的路段（地图上任一段都可点）。
// 这种段：摄像头卡照常按登记表展示；指标 / 判级 / 下令一律如实「无数据 / 不可用」，不编造。
const selectedName = computed(() => {
    const id = selectedId.value;
    if (!id)
        return '—';
    return demoSegment(id)?.name ?? selected.value?.segment_id ?? id;
});
// ---------- IKP5BZ：本段附近的落客点 / 场区（唯一真值源 = 前端站点包） ----------
// 图上 Marker 之外再给一处**文字入口**：选中路段时列出同段 / 邻近段（≤150 m）的点位，
// 点条目 → 选中其所属路段（地图上点不到时仍可查）。坐标是演示点，不是踏勘点位。
const nearbyLandmarks = computed(() => landmarksNearSegment(selectedId.value ?? ''));
/** 距离显示（米）：非有限值如实「未标定」，不写 0 */
function landmarkDistance(v) {
    return Number.isFinite(v) ? `约 ${Math.round(v)} m` : '距离未标定';
}
// ---------- IKOQEJ：方向 / 车道 / 对向 / 贯通（只读站点包字段，非契约、不参与判级） ----------
const segDirection = computed(() => directionOf(selectedId.value ?? ''));
const segDirectionKind = computed(() => directionKindOf(segDirection.value));
const segDirectionLabel = computed(() => directionLabel(segDirectionKind.value));
const segDirectionSource = computed(() => directionSourceLabel(segDirection.value));
const segLanes = computed(() => lanesOf(segDirection.value));
const segContinuity = computed(() => continuityOf(segDirection.value));
const segOpposite = computed(() => oppositeOf(segDirection.value));
/** 对向段是否在当前前端站点包里（GZ enriched 708 段 > 前端 433 段时，部分对向段尚未同步） */
const segOppositePresent = computed(() => Boolean(segOpposite.value && demoSegment(segOpposite.value)));
/** 浮牌里的短口径（方向 / 车道 / 对向 / 贯通），字段缺省一律「未标定」 */
const segContinuityChip = computed(() => {
    if (segContinuity.value.state !== 'pending')
        return segContinuity.value.label;
    const gap = segDirection.value?.continuity?.gap_to_next_m;
    return typeof gap === 'number' && Number.isFinite(gap)
        ? `贯通性待核(gap ${gap} m)`
        : '贯通性待核(gap 未标定)';
});
const segDirectionChip = computed(() => {
    const parts = [
        `方向 ${segDirectionKind.value === 'unknown' ? '未标定' : segDirectionLabel.value.replace(/（.*）/, '')}`,
        `车道 ${segLanes.value.text}`,
    ];
    if (segOpposite.value) {
        parts.push(`对向 ${segOpposite.value}${segOppositePresent.value ? '' : '(待同步)'}`);
    }
    parts.push(segContinuityChip.value);
    return parts.join(' · ');
});
/** 默认选中:非陈旧路段里 level 最高者(同档取 x 大者);无可用则退回首条 */
function pickDefaultId(list) {
    if (list.length === 0)
        return null;
    const usable = list.filter((s) => !isStale(s));
    const pool = usable.length > 0 ? usable : list;
    let best = pool[0];
    for (const s of pool) {
        if (s.level > best.level || (s.level === best.level && (s.x ?? 0) > (best.x ?? 0)))
            best = s;
    }
    return best.segment_id;
}
/** 选中路段相关的三个接口(并排表 + 因素 + CI 走势);选中变化与快照刷新都会重拉 */
async function loadSelectedSide(segmentId) {
    if (!segmentId) {
        pair.value = null;
        segFactors.value = [];
        history.value = null;
        return;
    }
    // 站点包里有、但当前快照没覆盖的段（Issue IKMS18 允许地图选中）：不请求不存在的快照端点，
    // 详情卡按「无数据」如实降级（避免 404 噪声，也不拿别的段顶替）。
    if (!selected.value) {
        pair.value = null;
        segFactors.value = [];
        history.value = null;
        return;
    }
    const [p, f, h] = await Promise.allSettled([
        getTrafficSegmentSources(segmentId),
        getTrafficFactors(segmentId),
        getTrafficCiHistory(segmentId, 12),
    ]);
    if (selectedId.value !== segmentId)
        return; // 选择已变:丢弃过期响应
    pair.value = p.status === 'fulfilled' ? p.value : null;
    segFactors.value = f.status === 'fulfilled' ? f.value.factors : [];
    history.value = h.status === 'fulfilled' ? h.value : null;
}
/**
 * 刷新序号:SSE 触发与手动刷新可能并发。只有"最新一次"的响应允许落到页面,
 * 否则先发出、后返回的旧响应会覆盖新快照(页面显示上一版数据)。
 */
let refreshSeq = 0;
/**
 * 在途刷新的中止句柄（Issue IKPFR4）。切站时**必须**把上一站的请求掐掉：否则旧站响应会在
 * 几百毫秒后回来，把刚渲染好的新站首屏覆盖成旧站数据 —— 那正是"把 Z 的数据当 GZ 显示"。
 * 与"响应回来时校验站点键"是**两道闸**，都留着（中止省带宽，校验兜底）。
 */
let refreshCtrl = null;
/** 首屏之后是否已经排过预热（只排一次，避免每次 SSE 刷新都替别站重拉） */
let prewarmed = false;
/** 本次刷新中失败的接口(页头提示用;失败面板保留旧值但必须标"上一版",不得冒充当前) */
const failedPanels = ref([]);
/** SSE 刷新通道连接状态:断开时页面不会自动刷新,必须显式提示(TC-06 断流降级) */
const sseConnected = ref(true);
/** 切站加载态：无缓存时才亮（极简骨架条），有缓存不走这里 */
const switching = ref(false);
/** 是否正在显示缓存快照：后台刷新回来立刻清掉 —— 缓存数据不得冒充最新（业主口径） */
const servedFromCache = ref(false);
/** 缓存写入时刻（ms），提示条据此写"缓存于 N s 前" */
const cacheStamp = ref(0);
/**
 * 「缓存于 N s 前」的时钟源（PR !76 审查意见）。
 * 为什么需要单独一个 ref：`Date.now()` 不是响应式的 —— 没有它，秒数会**停在切站那一刻**
 * （数据没错，但"几秒前"这句话会变成假的）。只在亮着缓存条时开 1 s 定时器，条件一变就停。
 */
const cacheClockTick = ref(0);
let cacheClockTimer = 0;
watch(servedFromCache, (on) => {
    window.clearInterval(cacheClockTimer);
    if (!on)
        return;
    cacheClockTimer = window.setInterval(() => {
        cacheClockTick.value += 1;
    }, 1000);
});
/** 缓存提示文案；空 = 当前数据就是这次网络拉到的，不用标"缓存" */
const cacheNote = computed(() => {
    if (!servedFromCache.value)
        return '';
    void cacheClockTick.value; // 每秒 +1，让"几秒前"跟着走（见上）
    const age = Math.max(0, Math.round((Date.now() - cacheStamp.value) / 1000));
    return `当前显示「${stationName.value}」的缓存快照（缓存于 ${age} s 前）· 正在后台刷新，新数据到达即替换 —— 缓存数据不代表最新态势`;
});
const PANEL_LABEL = {
    overview: 'KPI',
    segments: '路段监测',
    vehicles: '车辆',
    alerts: '告警',
    factors: '因素',
    matrix: '热力矩阵',
    thresholds: '阈值与 CI 权重',
};
async function refresh() {
    const seq = ++refreshSeq;
    // ⚠️ 这里**不掐**上一轮：慢后端（GZ 站远端首载可到十几秒，见 README 23.9 登记）会碰上 SSE 每 2 s 的一次
    //    刷新 —— 每轮都 abort 的话所有请求都在半路被杀，数据永远落不下来。上一轮的响应靠
    //    `refreshSeq` 作废即可（见下方两道闸），abort 只在**切站**时用（`resetStationState`）。
    const ctrl = new AbortController();
    refreshCtrl = ctrl;
    // 这一轮请求配属的站键：写缓存、校验响应都以它为准（不要用 activePackKey() 事后现取）
    const stationKey = activePackKey();
    const opts = { signal: ctrl.signal };
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
    ]);
    if (seq !== refreshSeq)
        return; // 已被更晚的一次刷新取代:丢弃本次响应
    // 第二道闸:站点键已换(切站) → 这批响应属于上一站,一律丢弃
    if (stationKey !== activePackKey())
        return;
    // IKPFVN D2：镜头还在飞就先挂住响应 —— 到站后再一次性铺数据（骨架屏继续亮）。
    // ⚠️ await 之后必须**重新验证两道闸**：等镜头这几秒里用户完全可能又点了一个站。
    if (arriving.value) {
        await whenArrived();
        if (seq !== refreshSeq)
            return;
        if (stationKey !== activePackKey())
            return;
    }
    switching.value = false;
    const failed = [];
    const track = (name, ok) => {
        if (!ok)
            failed.push(PANEL_LABEL[name] ?? name);
    };
    if (ov.status === 'fulfilled')
        overview.value = ov.value;
    track('overview', ov.status === 'fulfilled');
    if (seg.status === 'fulfilled') {
        segments.value = seg.value.segments;
        snapshotTs.value = seg.value.ts;
        if (selectedId.value === null)
            selectedId.value = pickDefaultId(seg.value.segments);
        applyDeepSegment();
    }
    track('segments', seg.status === 'fulfilled');
    if (veh.status === 'fulfilled')
        vehicles.value = veh.value.vehicles;
    track('vehicles', veh.status === 'fulfilled');
    if (al.status === 'fulfilled')
        alerts.value = al.value.alerts;
    track('alerts', al.status === 'fulfilled');
    if (fa.status === 'fulfilled')
        allFactors.value = fa.value.factors;
    track('factors', fa.status === 'fulfilled');
    if (matrix.status === 'fulfilled')
        heat.value = matrix.value;
    track('matrix', matrix.status === 'fulfilled');
    if (thr.status === 'fulfilled')
        thresholds.value = thr.value;
    track('thresholds', thr.status === 'fulfilled');
    // 站名只用于顶栏 chip:取不到就保持站点包里的名字,不因此把整页标成"上一版数据"
    if (meta.status === 'fulfilled') {
        metaInfo.value = meta.value;
        metaStationName.value = meta.value.station.name;
    }
    failedPanels.value = failed;
    // 只有真的拿到新快照才撤掉"缓存"标识：这一轮全挂时页面上仍是缓存数据，
    // 撤标就等于让缓存冒充最新（上面那条失败提示条负责说明"看到的是上一版"）
    if (seg.status === 'fulfilled' || ov.status === 'fulfilled') {
        servedFromCache.value = false;
        cacheStamp.value = 0;
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
    });
    // 首屏就位后再预热（不抢首屏带宽；失败静默）
    if (!prewarmed && seg.status === 'fulfilled') {
        prewarmed = true;
        schedulePrewarm();
    }
    await loadSelectedSide(selectedId.value);
}
watch(selectedId, (id) => {
    void loadSelectedSide(id);
});
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
function scrollPageToTop() {
    window.scrollTo({ top: 0 });
    for (const el of document.querySelectorAll('.td-scroll, .seg-list'))
        el.scrollTop = 0;
}
/** 站内状态一律重置（业主裁定：切站不跨站恢复任何选中态） */
function resetStationState() {
    // 中止上一站的在途请求：序号也 +1，让"已经飞出去但还没回来的"那一轮认不出自己是最新的
    refreshCtrl?.abort();
    refreshCtrl = null;
    refreshSeq += 1;
    selectedId.value = null;
    scope.value = null;
    deepApplied = false;
    // 路线 / 定位 / 双源 / 走势：都是"按某个段、某个 session 取回来的"，跨站一律不保留
    selectedSession.value = '';
    recommend.value = null;
    recommendError.value = '';
    routeOptions.value = null;
    routeOptionsError.value = '';
    pair.value = null;
    segFactors.value = [];
    history.value = null;
    locateInfo.value = null;
    locateError.value = '';
    startConfirmed.value = false;
    manualStart.value = false;
    manualStartId.value = '';
    // 快照侧：先清空，再由缓存或新一轮刷新填回来（清空这一步保证绝不会把上一站的数据当本站显示）
    overview.value = null;
    segments.value = [];
    vehicles.value = [];
    alerts.value = [];
    allFactors.value = [];
    thresholds.value = null;
    heat.value = null;
    metaInfo.value = null;
    metaStationName.value = null;
    snapshotTs.value = '';
    failedPanels.value = [];
    servedFromCache.value = false;
    cacheStamp.value = 0;
    // IKPFVN D 节：从这一行起，页面数据等“镜头到站”再上屏（骨架屏先亮着）；
    // `markArrived()`（地图组件报 arrived / 4 s 兜底）会把它放行。
    arriving.value = true;
    switching.value = true;
    scrollPageToTop();
}
/**
 * 缓存优先渲染（切站钩子）。
 *
 * IKPFVN D 节：镜头还在飞的时候**不往面板上铺**（业主口径是“到站再信息切换”），
 * 先把快照挂在一边，`markArrived()` 时再走 `commitCachedSnapshot()`。
 * 本函数仍保持**同步**语义（只是存一下，不等网络）——秒开靠的是“不等网络”，与何时上屏无关。
 */
function applyCachedSnapshot(snapshot) {
    if (arriving.value) {
        pendingCache = snapshot;
        pendingCacheReady = true;
        return;
    }
    commitCachedSnapshot(snapshot);
}
/** 真正把缓存铺到首屏（切站开始时与到站后各可能调一次） */
function commitCachedSnapshot(snapshot) {
    if (!snapshot) {
        // 没有缓存（首次访问该站 / 预热还没完成）：只亮骨架条，页面本身不白屏
        switching.value = true;
        return;
    }
    // 缓存里若连 segments 都没有（当初那个接口就没取到）：列表/地图仍空，骨架条照样亮着
    switching.value = !snapshot.segments;
    servedFromCache.value = true;
    cacheStamp.value = snapshot.ts;
    overview.value = snapshot.overview;
    if (snapshot.segments) {
        segments.value = snapshot.segments.segments;
        snapshotTs.value = snapshot.segments.ts;
    }
    alerts.value = snapshot.alerts?.alerts ?? [];
    allFactors.value = snapshot.factors ?? [];
    thresholds.value = snapshot.thresholds;
    heat.value = snapshot.matrix;
    metaInfo.value = snapshot.meta;
    metaStationName.value = snapshot.meta?.station.name ?? null;
    // 车辆动点不入缓存：宁可空着等下一轮刷新，也不画"上一次看到的车"（位置流每 2 s 就过期）
    vehicles.value = [];
}
/** 注销钩子（组件卸载时必须调，否则切站会往已卸载的页面里写数据） */
const unbindStationSwitch = bindStationSwitch({
    resetStationState,
    applyCachedSnapshot,
    refresh: () => {
        void refresh();
        // 路线产物是**按站**出的（引擎每个站一份 routes.json）：切站后重新取一次 OD 选项，
        // 别让右栏停在上一站的 session 上（这是"站内状态一律重置"里"路线 session"那一条）
        void loadRouteOptions();
    },
});
onUnmounted(() => {
    unbindStationSwitch();
    offPackTick();
    // 卸载时把在途请求一并掐掉（切页 / 关页都不该让响应回来往空组件里写）
    refreshCtrl?.abort();
    refreshCtrl = null;
    // 「缓存于 N s 前」的时钟也一起停，别让定时器在已卸载的页面上空转
    window.clearInterval(cacheClockTimer);
});
const ROUTE_VIEWS = [
    { key: 'all', name: '全部' },
    { key: 'arrival', name: '推荐' },
    { key: 'alternative', name: '备选' },
    { key: 'departure', name: '离站' },
];
/** 推荐快照（null = 接口不可达或无数据；此时地图不画任何路线） */
const recommend = ref(null);
const recommendLoading = ref(false);
const recommendError = ref('');
/** 三态切换：全部 / 推荐 / 备选 / 离站（截图三态用同一套按钮） */
const routeView = ref('all');
/** 当前站点包内的段数（卡片文案用；切包后不写死 61） */
const packSegmentCount = computed(() => {
    void packTick.value;
    return activePack().segments.length;
});
/**
 * 当前站点包内的段号集合：路线引用的段必须都在包里，防悬空画假线。
 * ⚠️ IKPFR4：原先是 setup 期的 `Set` 常量 —— 切站后仍是上一站的段号集合（Z 61 段看 GZ 708 段
 *    的路线会全部被判"不在包里"）。改成 computed，用它的地方一律取 `.value`。
 */
const packSegmentIds = computed(() => {
    void packTick.value;
    return new Set(activePack().segments.map((s) => s.segment_id));
});
// ---------- 落客点 / 候客区（业主 2026-10-20：先只上广州南站，别站先不动）----------
//
// 数据只吃**站点包**（`stationGZ.ts` 的 `dropoffs` / `zones`），不吃接口：
//   · 接口侧 `GET /network` 对非默认站恒返回空点位表（`work/assembly/traffic.py` 如实给
//     `points: []`，T1 点位表归池·S），拿它渲染只会在真接口模式下变成「没点位」的假空态；
//   · 站点包里的坐标是**所在路段折线上的演示点**，不是踏勘实测 —— 卡上必须写清，不能当实测发布。
// 开放范围先只到 GZ：Z（肇庆东）包也已有 3+2 个同类演示点，但业主这一轮只要广州南站，
// 不擅自把别的站也放上界面；以后要开，改 `LANDMARK_ENABLED_PACKS` 一处即可。
const LANDMARK_ENABLED_PACKS = ['GZ'];
const landmarksVisible = computed(() => LANDMARK_ENABLED_PACKS.includes(activePack().key));
const packDropoffs = computed(() => activePack().dropoffs);
const packZones = computed(() => activePack().zones);
const landmarkCount = computed(() => packDropoffs.value.length + packZones.value.length);
/** 卡脚注用的两个字段（站点包键 / 推荐的落客点），单独取成 computed，免得模板里反复调 activePack() */
const landmarkPackKey = computed(() => activePack().key);
const landmarkArrivalDropoff = computed(() => activePack().recommend.arrival_dropoff_point || '—');
/** 经纬度展示：6 位小数 ≈ 0.1 m，够看清演示点落位，不假装更高精度 */
function fmtLonLat(lon, lat) {
    return `${lon.toFixed(6)}, ${lat.toFixed(6)}`;
}
// ---------- 整条路线规划（Issue IKNAUI）----------
//
// 入口：`GET /api/traffic/route/options`（只读辅助端点、非契约 §七）端出引擎产物的
// OD / session / 进场路线 / 备选 / 离站路线**摘要**；选中后用真实 `session_id` 调
// `POST /route/recommend`，地图用同一份 recommend 数据画三态路线（RouteHighlight）。
// 口径：ETA / 段号原样透传，**前端不重算路线**；无产物 / 无选项 / 不匹配 → 如实空窗 + note。
const routeOptions = ref(null);
const routeOptionsLoading = ref(false);
const routeOptionsError = ref('');
/** 当前选中的引擎 session（空 = 回退演示会话路线） */
const selectedSession = ref('');
const selectedOption = computed(() => {
    const options = routeOptions.value?.options ?? [];
    return options.find((item) => item.session_id === selectedSession.value) ?? null;
});
function fmtEta(value) {
    return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(2) : '—';
}
/** 全程摘要（进场 → 落客 → 离站）：字段全部原样来自引擎摘要，不重算。 */
const tripSummary = computed(() => {
    const option = selectedOption.value;
    if (!option)
        return null;
    const arrival = option.arrival_route;
    const departure = option.departure_route;
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
    };
});
async function loadRecommend(sessionId) {
    recommendLoading.value = true;
    recommendError.value = '';
    try {
        const pack = activePack();
        const session = sessionId || `demo-${pack.key}`;
        const option = sessionId ? selectedOption.value : null;
        recommend.value = await postRouteRecommend({
            // 有引擎选项时用该 OD 的起点（引擎产物里的 location），否则沿用站点包演示锚点
            session_id: session,
            location: {
                segment_id: option?.location.segment_id ?? pack.recommend.location_segment_id,
                offset_m: option?.location.offset_m ?? pack.recommend.location_offset_m,
            },
        });
    }
    catch (e) {
        // 失败降级：清空路线 + 给出可读提示；不得拿 fallback 假数据兜底
        recommend.value = null;
        recommendError.value = `推荐接口不可达（${e instanceof Error ? e.message : '未知错误'}）：保持不画路线，不编造演示路线`;
    }
    finally {
        recommendLoading.value = false;
        // 起点与推荐同源（同一份引擎产物）：每次取推荐后同步刷新 /locate，避免两块显示两个起点
        void refreshLocate();
    }
}
/** 载入引擎 OD 选项 → 默认选第一条并画其完整路线；无选项 / mock 无该端点 → 回退演示会话路线 */
async function loadRouteOptions() {
    routeOptionsLoading.value = true;
    routeOptionsError.value = '';
    // mock 中间件没有 /route/options（未匹配路径一律 404）：不去打一条注定 404 的请求，
    // 直接按「mock 无该辅助端点」如实提示并回退演示会话路线（页面不崩、控制台不刷 404）。
    if (USE_MOCK) {
        routeOptions.value = null;
        routeOptionsError.value = 'mock 模式无 /api/traffic/route/options 端点（辅助端点仅真接口提供）';
        await loadRecommend();
        routeOptionsLoading.value = false;
        return;
    }
    try {
        const res = await getTrafficRouteOptions();
        const options = (Array.isArray(res.options) ? res.options : []).filter((item) => Boolean(item.session_id));
        routeOptions.value = options.length > 0 ? { ...res, options } : null;
        if (options.length > 0) {
            selectedSession.value = options[0].session_id;
            await loadRecommend(selectedSession.value);
        }
        else {
            await loadRecommend();
        }
    }
    catch (e) {
        routeOptions.value = null;
        routeOptionsError.value = e instanceof Error ? e.message : String(e);
        await loadRecommend();
    }
    finally {
        routeOptionsLoading.value = false;
    }
}
function onRouteSessionChange() {
    if (!selectedSession.value)
        return;
    void loadRecommend(selectedSession.value);
}
// ---------- 起点 / 终点确认（Issue IKP5C6）----------
//
// 一期口径：起点是**孪生真值**（接口 `/api/traffic/locate` 直读引擎产物 `requests[].location`，
// 接口层不做地图匹配），所以这里的“确认”只是把这份真值显式摆给使用者看并留下一个确认动作，
// **不是用户定位**；未确认时页面必须写明「按孪生真值演示」，不得暗示“已确认你的位置”。
// TC-05 展示侧兜底：定位不可用 / 置信度低时，可从当前站点包手动选一段作为起点（流程不中断）。
const locateInfo = ref(null);
const locateLoading = ref(false);
const locateError = ref('');
/** 使用者是否点过「以这里为起点」（切换 session 后重置） */
const startConfirmed = ref(false);
/** 手动选起点（兜底）：从当前站点包路段下拉里选一段 */
const manualStartId = ref('');
const manualStart = ref(false);
const packSegments = computed(() => {
    void packTick.value;
    return activePack().segments;
});
/** 当前起点：手动选择优先 → /locate 结果 → 推荐响应自带的 location（失败降级，不编） */
const currentStart = computed(() => {
    if (manualStart.value && manualStartId.value) {
        return { segment_id: manualStartId.value, offset_m: 0, match_confidence: null, source: 'manual' };
    }
    const loc = locateInfo.value;
    if (loc && loc.segment_id) {
        return {
            segment_id: loc.segment_id,
            offset_m: loc.offset_m,
            match_confidence: loc.match_confidence,
            source: loc.source,
        };
    }
    const rec = recommend.value?.location;
    if (rec) {
        return {
            segment_id: rec.segment_id,
            offset_m: rec.offset_m,
            match_confidence: rec.match_confidence ?? null,
            source: rec.source,
        };
    }
    return null;
});
const startName = computed(() => (currentStart.value ? nameOf(currentStart.value.segment_id) : '—'));
const startSourceLabel = computed(() => {
    const source = currentStart.value?.source;
    if (source === 'twin')
        return '孪生真值';
    if (source === 'app_gnss')
        return 'App 定位';
    if (source === 'manual')
        return '手动选择';
    return source || '—';
});
const confidenceText = computed(() => {
    const c = currentStart.value?.match_confidence;
    return typeof c === 'number' && Number.isFinite(c) ? c.toFixed(2) : '—';
});
const offsetText = computed(() => {
    const v = currentStart.value?.offset_m;
    return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(1) : '—';
});
/** 与 `work/engine/locate.py` 的 MATCH_CONFIDENCE_MIN 同口径：< 0.6 提示定位不稳定（不改判定） */
const confidenceLow = computed(() => {
    const c = currentStart.value?.match_confidence;
    return typeof c === 'number' && Number.isFinite(c) && c < 0.6;
});
/** 终点：优先 `arrival_route.dropoff_point`；为 null 时给 `why` 里的具体原因 + 末段兜底 */
const tripEnd = computed(() => {
    const r = recommend.value;
    if (!r)
        return null;
    const segs = r.arrival_route.segments ?? [];
    const last = segs.length > 0 ? segs[segs.length - 1] : null;
    const drop = r.arrival_route.dropoff_point ?? null;
    const landmark = drop
        ? [...activePack().dropoffs, ...activePack().zones].find((p) => p.id === drop)
        : undefined;
    // why 里的原因用 [] 括起（引擎口径）；只挑与终点 / 点位相关的条目，别把离站原因混进来
    const notes = (r.why.match(/\[[^\]]+\]/g) ?? []).filter((n) => /落客|上客|点位|终点/.test(n));
    return {
        drop,
        pointName: landmark?.name ?? null,
        last,
        lastName: last ? nameOf(last) : '—',
        reason: notes.join(' '),
    };
});
// ---------- 地图上的「起点 / 终点」标注（业主 2026-10-21 口径） ----------
// 「那些大道最外面的路段就是起点，然后停车场落客点是终点」：起点用推荐路线实际起点路段
// （引擎边界推导的进场段，站点包里登记为 boundary 的 P-Bxx），终点优先对齐站点包里的
// 停车场落客点（演示点），对不上才退回末段终点——只做展示，不改算路 / ETA。
const startBoundarySection = computed(() => {
    const id = currentStart.value?.segment_id;
    if (!id)
        return null;
    return (activePack().sections ?? []).find((s) => s.segment_id === id && s.role === 'boundary') ?? null;
});
const routeStartMarker = computed(() => {
    const s = currentStart.value;
    if (!s)
        return null;
    const seg = demoSegment(s.segment_id);
    if (!seg || seg.coords.length === 0)
        return null;
    const p = pointAtOffset(seg.coords, s.offset_m ?? 0);
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
    };
});
const routeEndMarker = computed(() => {
    const r = recommend.value;
    if (!r)
        return null;
    const segs = r.arrival_route.segments ?? [];
    const last = segs.length > 0 ? segs[segs.length - 1] : null;
    if (!last)
        return null;
    const seg = demoSegment(last);
    const dropId = r.arrival_route.dropoff_point ?? null;
    if (dropId) {
        const point = activePack().dropoffs.find((d) => d.id === dropId);
        if (point) {
            return {
                kind: 'end',
                label: '终点·落客点',
                segment_id: last,
                name: point.name,
                lon: point.lon,
                lat: point.lat,
                note: `点位 ${dropId}（演示点）`,
            };
        }
    }
    const near = landmarksNearSegment(last)
        .filter((x) => x.kind === 'dropoff')
        .sort((a, b) => a.distance_m - b.distance_m)[0];
    if (near) {
        return {
            kind: 'end',
            label: '终点·落客点',
            segment_id: last,
            name: near.name,
            lon: near.lon,
            lat: near.lat,
            note: `停车场落客点 ${near.id}（演示点）· 距末段 ${Math.round(near.distance_m)} m`,
        };
    }
    if (!seg || seg.coords.length === 0)
        return null;
    const p = pointAtOffset(seg.coords, Math.max(0, segmentLengthM(seg.coords) - 1));
    return {
        kind: 'end',
        label: '终点',
        segment_id: last,
        name: seg.name,
        lon: p[0],
        lat: p[1],
        note: '引擎产物未给落客点；落在末段终点（演示）',
    };
});
/** 拉一次 /locate（真接口才有；mock 如实标注降级，不编起点） */
async function refreshLocate() {
    locateError.value = '';
    locateInfo.value = null;
    startConfirmed.value = false;
    manualStart.value = false;
    manualStartId.value = '';
    if (USE_MOCK) {
        locateError.value = 'mock 模式无 /api/traffic/locate 端点（辅助端点仅真接口提供）';
        return;
    }
    locateLoading.value = true;
    try {
        locateInfo.value = await postTrafficLocate({ session_id: selectedSession.value || undefined });
    }
    catch (e) {
        locateError.value = `定位接口不可达（${e instanceof Error ? e.message : '未知错误'}）；当前按推荐响应自带的 location 显示，不编起点`;
    }
    finally {
        locateLoading.value = false;
    }
}
function confirmStart() {
    if (currentStart.value)
        startConfirmed.value = true;
}
function applyManualStart() {
    if (!manualStartId.value)
        return;
    manualStart.value = true;
    startConfirmed.value = true;
}
/** 地图要高亮的路线分组（按 routeView 过滤；无数据时为空数组） */
const routeHighlights = computed(() => {
    const r = recommend.value;
    if (!r)
        return [];
    const groups = [];
    if (routeView.value === 'all' || routeView.value === 'arrival') {
        groups.push({ kind: 'arrival', segments: r.arrival_route.segments });
    }
    if (routeView.value === 'all' || routeView.value === 'alternative') {
        // Issue IKP5CK：备选不能再全压成同一个 `alternative` 分组（两条备选会画成同一套灰虚线）。
        // `index` 是前端展示类型字段（非契约）：1 = 备选 1（青/长虚）、2 = 备选 2（琥珀/短虚）。
        r.alternatives.forEach((a, i) => {
            if (a.segments && a.segments.length > 0) {
                groups.push({ kind: 'alternative', index: i + 1, segments: a.segments });
            }
        });
    }
    if (routeView.value === 'all' || routeView.value === 'departure') {
        if (r.departure_route && r.departure_route.segments.length > 0) {
            groups.push({ kind: 'departure', segments: r.departure_route.segments });
        }
    }
    return groups;
});
/** 右栏路线卡片（与地图用同一份 recommend 数据，不另算） */
const routeCards = computed(() => {
    const r = recommend.value;
    if (!r)
        return [];
    const cards = [];
    // Issue IKP5CK：备选不足的判定依据（`alternatives.length` + 引擎 `no_alternative_reason`）
    // 放进每张卡的数据结构，供路线卡区域如实提示；页面不据此补画等价路线。
    const alternativeCount = r.alternatives.length;
    const noAlternativeReason = r.no_alternative_reason ?? null;
    if (routeView.value === 'all' || routeView.value === 'arrival') {
        cards.push({
            key: 'arrival',
            kind: 'arrival',
            kindName: '推荐路线',
            pathId: r.arrival_route.path_id,
            eta: r.arrival_route.eta_min,
            segments: r.arrival_route.segments,
            note: r.why,
            alternativeCount,
            noAlternativeReason,
        });
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
                alternativeCount,
                noAlternativeReason,
            });
        });
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
                alternativeCount,
                noAlternativeReason,
            });
        }
    }
    return cards;
});
/** 路线里引用了当前站点包不存在的段号 → 如实提示（不画点不出的段） */
const routeMissing = computed(() => {
    const missing = new Set();
    for (const g of routeHighlights.value) {
        for (const id of g.segments)
            if (!packSegmentIds.value.has(id))
                missing.add(id);
    }
    return [...missing];
});
/** 路线来源角标:真接口按响应 data_source 标（真网 / 样例），mock 侧沿用「演示骨架」口径 */
const routeSourceTag = computed(() => {
    const source = recommend.value?.data_source;
    if (source === 'engine.routes.real')
        return '真网算路产物（IKMS11）';
    if (source === 'engine.routes.sample')
        return '样例产物 · 非本站真网';
    return '演示骨架 · 连通段拼接';
});
/** 路线来源人话（响应 data_source_note；mock 侧为空） */
const routeSourceNote = computed(() => recommend.value?.data_source_note ?? '');
/** 路线说明：真接口只端引擎产物（不代算）；mock 侧保持原「演示骨架」文案 */
const routeWhyLine = computed(() => {
    const source = recommend.value?.data_source;
    if (source === 'engine.routes.real' || source === 'engine.routes.sample') {
        return '接口层只端引擎算路产物（真网产物优先、样例产物回退），不代算 ETA；颜色语义：品牌蓝实线 = 推荐 / 当前，青长虚线 = 备选 1，琥珀短虚线 = 备选 2，紫色实线 = 离站。';
    }
    return `演示路线：在 ${packSegmentCount.value} 段真 OSM 路网上按“相邻段连通”拼出的演示序列，不是引擎 K 最短路 + 预约输出，也不是按当前路况重算出来的结果。颜色语义：品牌蓝实线 = 推荐 / 当前，青长虚线 = 备选 1，琥珀短虚线 = 备选 2，紫色实线 = 离站。`;
});
/** 路线降级说明（session 未匹配 / 段号命名空间不一致等，来自接口响应 note；无则空）。
 *  session 未匹配已在下方单独用显式警示段落呈现，这里去掉重复的第一句。 */
const routeDegradedNote = computed(() => {
    const note = recommend.value?.note ?? '';
    return note
        .split('；')
        .filter((part) => part.trim() && !part.startsWith('请求的 session_id'))
        .join('；');
});
onMounted(() => {
    void refresh();
    // Issue IKNAUI：先载入引擎 OD 选项（有则默认画第一条完整路线；无则回退演示会话）
    void loadRouteOptions();
    unsubscribe = subscribeTrafficSnapshot(() => {
        void refresh();
    }, (connected) => {
        sseConnected.value = connected;
        // 重连成功 → 立刻补拉一次,恢复后的数据不用等下一个心跳
        if (connected)
            void refresh();
    });
    // IKPFVN E4：首屏默认全国视角；上次选过的站 1.2 s 后自动飞入（用户一碰就取消）
    scheduleAutoFly();
});
onUnmounted(() => {
    unsubscribe?.();
    // 首屏自动飞入 / 到站门控的定时器一起停：它们会往已卸载的页面里写状态
    window.clearTimeout(autoFlyTimer);
    window.clearTimeout(arriveTimer);
});
// ---------- 文案 / 格式化助手 ----------
const CN_NUM = { 1: '一', 2: '二', 3: '三', 4: '四' };
function levelName(seg) {
    return isStale(seg) ? UNAVAILABLE.name : (seg.level_name ?? levelStyle(seg).name);
}
function fmt(v, digits = 2) {
    return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—';
}
/** 'YYYY-MM-DD HH:mm:ss' → 'HH:mm:ss'(告警条首次观测时间) */
function hhmmss(stamp) {
    return stamp.length >= 8 ? stamp.slice(-8) : stamp;
}
/** 路段名(矩阵 / 排行里的行不带 name,统一从路网取,与地图同源) */
function nameOf(id) {
    return demoSegment(id)?.name ?? id;
}
// ---------- KPI 条 ----------
/** 环比文案:负 = 变慢(较上一版慢 x km/h) */
const avgDeltaText = computed(() => {
    const d = overview.value?.avg_speed_delta_kmh;
    if (typeof d !== 'number')
        return '—';
    if (Math.abs(d) < 0.05)
        return '较上一版持平';
    return `较上一版${d > 0 ? '快' : '慢'} ${Math.abs(d).toFixed(1)} km/h`;
});
/** 采纳率:guided_rate(0~1) → 百分数保留一位 */
const adoptText = computed(() => {
    const o = overview.value;
    if (!o)
        return '—';
    return `已引导 ${o.vehicles_guided} · 采纳率 ${(o.guided_rate * 100).toFixed(1)}%`;
});
/** 前 3 条生效因素名(按 factor_id 去重,展示口径) */
const topFactors = computed(() => {
    const seen = new Set();
    const out = [];
    for (const f of allFactors.value) {
        if (seen.has(f.factor_id))
            continue;
        seen.add(f.factor_id);
        out.push(`${f.factor_id} ${f.name}`);
        if (out.length === 3)
            break;
    }
    return out;
});
const dist = computed(() => {
    // 纯车流量版（Issue IKNB9G）：按 q_vph 四档统计（数据来自 /segments；缺 q / 陈旧→无流量数据灰档）
    if (isFlow.value) {
        const counts = new Map();
        let missing = 0;
        for (const seg of segments.value) {
            const band = flowBandOf(seg);
            if (band)
                counts.set(band.band, (counts.get(band.band) ?? 0) + 1);
            else
                missing += 1;
        }
        return [
            ...FLOW_BANDS.map((band) => ({
                level: band.band,
                name: band.name,
                count: counts.get(band.band) ?? 0,
                color: band.color,
            })),
            { level: 0, name: FLOW_UNAVAILABLE_LABEL, count: missing, color: UNAVAILABLE.color },
        ];
    }
    // 决策拥堵版：沿用接口 level_distribution（C-2 既有口径，不重算）
    return (overview.value?.level_distribution ?? []).map((r) => ({
        level: r.level,
        name: r.name,
        count: r.count,
        color: r.level === 0 ? UNAVAILABLE.color : LEVELS[r.level].color,
    }));
});
const distTotal = computed(() => {
    const o = overview.value;
    if (o)
        return o.segment_total;
    return dist.value.reduce((acc, r) => acc + r.count, 0);
});
function distWidth(r) {
    const total = dist.value.reduce((acc, x) => acc + x.count, 0);
    if (total <= 0 || r.count <= 0)
        return '0%';
    return `${(r.count / total) * 100}%`;
}
/** 监控范围切换(点分布条 / 点档位图例 / 「全部」) */
function toggleScope(level) {
    scope.value = scope.value === level ? null : level;
}
/** 监控范围过滤(0 = 数据不可用档;流量版 = 四档 band) */
const scoped = computed(() => {
    const s = scope.value;
    if (s === null)
        return segments.value;
    if (isFlow.value) {
        if (s === 0)
            return segments.value.filter((x) => !flowBandOf(x));
        return segments.value.filter((x) => flowBandOf(x)?.band === s);
    }
    if (s === 0)
        return segments.value.filter((x) => isStale(x));
    return segments.value.filter((x) => !isStale(x) && x.level === s);
});
/**
 * 路段列表行：
 *   · 流量版：按 q 四档降序（同档按 q 降序），行尾显示 q、角标显示流量档位（不用 LevelBadge，
 *     避免把流量读成判级）；缺 q / 陈旧 → 灰档「无流量数据」；
 *   · 拥堵版：四级视图按等级降序 / 指数视图按 CI 降序（既有行为，C-2 不改）。
 */
const segRows = computed(() => {
    const list = [...scoped.value];
    if (isFlow.value) {
        list.sort((a, b) => (flowBandOf(b)?.band ?? 0) - (flowBandOf(a)?.band ?? 0) ||
            (b.q_vph ?? -1) - (a.q_vph ?? -1));
        return list.map((seg) => {
            const band = flowBandOf(seg);
            const stale = isStale(seg);
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
            };
        });
    }
    if (viewMode.value === 'index') {
        list.sort((a, b) => {
            const av = ciAvailable(a);
            const bv = ciAvailable(b);
            if (av !== bv)
                return av ? -1 : 1;
            return (b.ci ?? 0) - (a.ci ?? 0);
        });
    }
    else {
        list.sort((a, b) => b.level - a.level || (b.x ?? 0) - (a.x ?? 0));
    }
    return list.map((seg) => {
        const st = levelStyle(seg);
        return {
            seg,
            color: st.color,
            text: st.text,
            stale: isStale(seg),
            name: nameOf(seg.segment_id),
            flowBand: null,
            valueText: '',
        };
    });
});
/** 指数视图的左栏排行(原 /heat 的 SegmentRankTable 口径,含不可用清单) */
const rankRows = computed(() => scoped.value
    .map((s) => ({
    id: s.segment_id,
    name: nameOf(s.segment_id),
    ci: ciAvailable(s) ? s.ci : null,
    level: s.level,
    available: ciAvailable(s),
}))
    .sort((a, b) => {
    if (a.available !== b.available)
        return a.available ? -1 : 1;
    return (b.ci ?? 0) - (a.ci ?? 0);
}));
// ---------- 中栏 · 地图 ----------
// 2026-10-14 极简口径只画路段线；Issue IKP5BZ 起补回落客点 / 场区 Marker（唯一真值源 = 前端站点包）——
// 断面仍未上图，路段摘要仍只用跟随鼠标的浮牌（hover-chip）。
/** 选中 chip:路段拥堵 · 摄像头 2 路 · x 0.91 / 0.84(video/twin);video 不可用只显示 twin 并注明 */
const mapChip = computed(() => {
    // 摄像头数按**段号**现算(Issue IKLX5Y),不看有没有快照记录:
    // 没有摄像头的那 16 段**本来就没有记录**,若等记录才拼浮牌,这些段悬停时什么都没有
    // —— 那就答不上"每段可查摄像头数、没有的如实显示 0"。
    const id = selectedId.value;
    if (!id)
        return '';
    // IKNBT2 口径：N 段 = N 摄像头 = N 视频（演示）。源台账 0 路不写「0 路/没摄像头」，
    // 而是「演示摄像头（复用样本视频）」；源台账有的写「源台账 N 路」以示这只是初始映射。
    const camCount = cameraCountOf(id);
    const cam = camCount > 0 ? `源台账摄像头 ${camCount} 路` : '演示摄像头（复用样本视频）';
    // IKOQEJ：方向 / 车道 / 对向 / 贯通（缺值「未标定」，只展示不判级）
    const dir = segDirectionChip.value;
    const s = selected.value;
    const flow = isFlow.value;
    if (flow) {
        // 纯车流量版（IKNB9G）：浮牌只报 q 与流量档位，不写等级/CI（避免把流量读成拥堵结论）
        if (!s)
            return `${id} 无流量记录 · ${cam} · ${dir}`;
        const band = flowBandOf(s);
        const qText = band ? `q ${fmt(s.q_vph, 0)} 辆/h` : FLOW_UNAVAILABLE_LABEL;
        return `${s.segment_id} ${band ? band.name : FLOW_UNAVAILABLE_LABEL} · ${qText} · ${cam}（流量版：仅按 q 分档）· ${dir}`;
    }
    if (!s)
        return `${id} 无路况记录 · ${cam} · ${dir}`;
    const v = pair.value?.slots.find((x) => x.source === 'video');
    const t = pair.value?.slots.find((x) => x.source === 'twin');
    const vx = v?.record?.x;
    const tx = t?.record?.x;
    const head = `${s.segment_id} ${levelName(s)} · ${cam} · ${dir}`;
    if (v?.available === true && typeof vx === 'number' && typeof tx === 'number') {
        return `${head} · x ${vx} / ${tx}`;
    }
    if (typeof tx === 'number')
        return `${head} · x ${tx}(仅孪生链路)`;
    return head;
});
// ---------- 右栏 · 双数据源并排(TC-19) ----------
/** 并排表只取四项(饱和度 x / 车速 / 排队长度 / 排队消散),按设计稿口径 */
const DELTA_KEYS = ['x', 'v_kmh', 'L_q_m', 'T_d_min'];
const deltaRows = computed(() => (pair.value?.deltas ?? []).filter((d) => DELTA_KEYS.includes(d.key)));
const videoAvailable = computed(() => pair.value?.slots.find((s) => s.source === 'video')?.available === true);
// ---------- 右栏 · 路段详情摘要 + CI ----------
const detailSummary = computed(() => {
    const s = selected.value;
    if (!s)
        return '';
    const parts = [`${s.level >= 1 ? CN_NUM[s.level] : '不可用'}级`, levelName(s)];
    parts.push(`更新 ${s.data_age_s ?? '—'}s 前`);
    parts.push(`饱和度 ${fmt(s.x)}`);
    if (s.triggered_by && s.triggered_by.length > 0)
        parts.push(`触发 ${s.triggered_by.join(' / ')}`);
    return parts.join(' · ');
});
const ciText = computed(() => {
    const r = selected.value;
    return r && ciAvailable(r) ? r.ci.toFixed(1) : '不可用';
});
const ciTextColor = computed(() => {
    const r = selected.value;
    return r && ciAvailable(r) ? levelStyle(r).text : UNAVAILABLE.color;
});
/** 四个 CI 权重(来自 thresholds,不写死) */
const weights = computed(() => thresholds.value?.ci_weights ?? []);
const weightText = computed(() => weights.value.length > 0 ? weights.value.map((w) => w.weight.toFixed(2)).join('/') : '—');
/** 各权重要素的「数值」:饱和度 x / 速度比 v/v_f / 排队比 L_q/L_seg / 消散 T_d(缺字段显示「—」) */
function metricText(key) {
    const r = selected.value;
    if (!r)
        return '—';
    const ratio = (a, b) => typeof a === 'number' && typeof b === 'number' && Number.isFinite(a) && Number.isFinite(b) && b !== 0
        ? (a / b).toFixed(2)
        : '—';
    switch (key) {
        case 'x':
            return typeof r.x === 'number' ? String(r.x) : '—';
        case 'v':
            return ratio(r.v_kmh, r.v_f_kmh);
        case 'k':
            return ratio(r.L_q_m, r.L_seg_m);
        case 'T_d':
            return typeof r.T_d_min === 'number' ? String(r.T_d_min) : '—';
        default:
            return '—';
    }
}
// ---------- 右栏 · 关联告警(原 /heat 右栏) ----------
//
// ⚠️ 等级**不在这里重映射**:本卡把 `segLevelOf` 作为 `levelOf` 回调交给 `AlertList`,
//    由它逐行取当前路段快照(Issue IKLLXG)。以前这里是裸 filter,徽章读告警记录值,
//    与左栏路段列表 / 底部告警条同页两个等级——#77 迁移时把 #75 第④条的重映射漏搬了一处。
//    收成「一个 shared 函数 + 子组件必需回调」后,漏传会被 `vue-tsc` 拦下。
const selectedAlerts = computed(() => alerts.value.filter((a) => a.segment_id === selectedId.value && a.status !== '已闭环' && a.status !== '误报'));
// ---------- 底部 · 档位分布(原 /heat 左栏) ----------
const bandRows = computed(() => {
    // 纯车流量版（IKNB9G）：q 四档分布（高→低排列，与拥堵版档位分布同向）
    if (isFlow.value) {
        const counts = new Map();
        for (const seg of segments.value) {
            const band = flowBandOf(seg);
            if (band)
                counts.set(band.band, (counts.get(band.band) ?? 0) + 1);
        }
        const rows = FLOW_BANDS.map((band) => ({
            level: band.band,
            name: `${band.name}（${flowRangeLabel(band)}）`,
            count: counts.get(band.band) ?? 0,
            color: band.color,
        }));
        return rows.reverse();
    }
    // 决策拥堵版：沿用既有 CI 四档口径（C-2 不改）
    const avail = segments.value.filter(ciAvailable);
    const out = [];
    for (let lv = 4; lv >= 1; lv--) {
        const lo = CI_BANDS[lv - 1] ?? 0;
        const hi = CI_BANDS[lv] ?? 100;
        const count = avail.filter((s) => {
            const ci = s.ci;
            return lv === 4 ? ci >= lo && ci <= hi : ci >= lo && ci < hi;
        }).length;
        out.push({
            level: lv,
            name: LEVELS[lv].name,
            count,
            color: LEVELS[lv].color,
        });
    }
    return out;
});
const unavailableCount = computed(() => isFlow.value
    ? segments.value.filter((s) => !flowBandOf(s)).length
    : segments.value.filter((s) => !ciAvailable(s)).length);
// ---------- 底部 · 热力矩阵：流量版用 q 单桶矩阵（接口只给当前快照；历史桶如实灰） ----------
function flowHeatLabels() {
    const moment = Date.parse(snapshotTs.value);
    const count = 12;
    const bucketSec = 60;
    if (Number.isNaN(moment))
        return Array.from({ length: count }, () => '—');
    return Array.from({ length: count }, (_, index) => formatClock(new Date(moment - (count - 1 - index) * bucketSec * 1000).toISOString()));
}
const flowHeat = computed(() => {
    if (!isFlow.value)
        return null;
    const labels = heat.value?.labels?.length ? heat.value.labels : flowHeatLabels();
    const rows = segments.value.map((seg) => {
        const q = flowBandOf(seg) ? seg.q_vph : null;
        return {
            segment_id: seg.segment_id,
            name: nameOf(seg.segment_id),
            buckets: [...Array(Math.max(0, labels.length - 1)).fill(null), q],
        };
    });
    return {
        ts: heat.value?.ts ?? snapshotTs.value,
        is_simulated: true,
        bucket_sec: heat.value?.bucket_sec ?? 60,
        buckets: labels.length,
        labels,
        rows,
    };
});
// ---------- 底部 · 告警条 ----------
const unclosed = computed(() => alerts.value.filter((a) => a.status === '待认领' || a.status === '处置中'));
const unclaimedCount = computed(() => alerts.value.filter((a) => a.status === '待认领').length);
const processingCount = computed(() => alerts.value.filter((a) => a.status === '处置中').length);
/** 第一条未闭环告警(默认取列表序=待认领在前) */
const firstAlert = computed(() => unclosed.value[0] ?? null);
/**
 * 告警等级取**当前路段快照**(与左栏 / 地图 / 右栏同一口径)。
 * 告警自带的 `level` 是派生时的记录值,预置剧本与快照基线不同步时会是旧值——
 * 直接用会与同一页的路段列表自相矛盾。
 *
 * ⚠️ 实现收敛到 `shared/traffic.ts` 的 `alertLevelOf`(Issue IKLLXG):
 *    本页的右栏关联告警 / 底部告警条**共用这一个函数**,不再各写一份。
 */
function segLevelOf(a) {
    return alertLevelOf(a, findSegment);
}
/** 快照查路段的唯一口径(本页共用) */
function findSegment(id) {
    return segments.value.find((s) => s.segment_id === id);
}
/** 告警摘要里的 x:从该路段快照取(不编造) */
const firstAlertX = computed(() => {
    const a = firstAlert.value;
    if (!a)
        return '—';
    return fmt(findSegment(a.segment_id)?.x);
});
// ---------- 交互 ----------
function onSelect(id) {
    selectedId.value = id;
}
function gotoDecision() {
    // 带段号深链：决策页「决策可视化」按该段展示（与右栏「查看完整决策过程」同一口径）
    const segment = selectedId.value;
    void router.push(segment ? { path: '/decision', query: { segment } } : '/decision');
}
/** 大屏下令成功（下发 / 回写）→ 重拉快照：告警状态、回执留痕与决策页保持同一后端状态 */
function onCommandChanged() {
    void refresh();
}
const __VLS_ctx = {};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
void __VLS_ctx, __VLS_components, __VLS_intrinsics, __VLS_directives;
// @ts-ignore
__VLS_withDotValue(failedPanels, {});
// @ts-ignore
__VLS_withDotValue(sseConnected, {});
// @ts-ignore
__VLS_withDotValue(cacheNote, {});
// @ts-ignore
__VLS_withDotValue(switching, {});
// @ts-ignore
__VLS_withDotValue(overview, {});
// @ts-ignore
__VLS_withDotValue(topFactors, {});
// @ts-ignore
__VLS_withDotValue(isFlow, {});
// @ts-ignore
__VLS_withDotValue(mapScope, {});
// @ts-ignore
__VLS_withDotValue(viewMode, {});
// @ts-ignore
__VLS_withDotValue(TD, {});
// @ts-ignore
__VLS_withDotValue(scope, {});
// @ts-ignore
__VLS_withDotValue(selectedId, {});
// @ts-ignore
__VLS_withDotValue(UNAVAILABLE, {});
// @ts-ignore
__VLS_withDotValue(segRows, {});
// @ts-ignore
__VLS_withDotValue(legendVisible, {});
// @ts-ignore
__VLS_withDotValue(directionsVisible, {});
// @ts-ignore
__VLS_withDotValue(currentPackKey, {});
// @ts-ignore
__VLS_withDotValue(routeOptionsLoading, {});
// @ts-ignore
__VLS_withDotValue(routeOptions, {});
// @ts-ignore
__VLS_withDotValue(tripSummary, {});
// @ts-ignore
__VLS_withDotValue(routeOptionsError, {});
// @ts-ignore
__VLS_withDotValue(USE_MOCK, {});
// @ts-ignore
__VLS_withDotValue(recommendLoading, {});
// @ts-ignore
__VLS_withDotValue(recommendError, {});
// @ts-ignore
__VLS_withDotValue(recommend, {});
// @ts-ignore
__VLS_withDotValue(routeView, {});
// @ts-ignore
__VLS_withDotValue(startConfirmed, {});
// @ts-ignore
__VLS_withDotValue(locateLoading, {});
// @ts-ignore
__VLS_withDotValue(currentStart, {});
// @ts-ignore
__VLS_withDotValue(startBoundarySection, {});
// @ts-ignore
__VLS_withDotValue(confidenceLow, {});
// @ts-ignore
__VLS_withDotValue(locateError, {});
// @ts-ignore
__VLS_withDotValue(manualStartId, {});
// @ts-ignore
__VLS_withDotValue(tripEnd, {});
// @ts-ignore
__VLS_withDotValue(routeSourceNote, {});
// @ts-ignore
__VLS_withDotValue(routeMissing, {});
// @ts-ignore
__VLS_withDotValue(routeDegradedNote, {});
// @ts-ignore
__VLS_withDotValue(landmarksVisible, {});
// @ts-ignore
__VLS_withDotValue(packDropoffs, {});
// @ts-ignore
__VLS_withDotValue(packZones, {});
// @ts-ignore
__VLS_withDotValue(selected, {});
// @ts-ignore
__VLS_withDotValue(segContinuity, {});
// @ts-ignore
__VLS_withDotValue(segLanes, {});
// @ts-ignore
__VLS_withDotValue(segOpposite, {});
// @ts-ignore
__VLS_withDotValue(segOppositePresent, {});
// @ts-ignore
__VLS_withDotValue(nearbyLandmarks, {});
// @ts-ignore
__VLS_withDotValue(sourceMode, {});
// @ts-ignore
__VLS_withDotValue(pair, {});
// @ts-ignore
__VLS_withDotValue(videoAvailable, {});
// @ts-ignore
__VLS_withDotValue(segFactors, {});
// @ts-ignore
__VLS_withDotValue(history, {});
// @ts-ignore
__VLS_withDotValue(selectedAlerts, {});
// @ts-ignore
__VLS_withDotValue(firstAlert, {});
// @ts-ignore
__VLS_withDotValue(LEVELS, {});
// @ts-ignore
__VLS_withDotValue(CN_NUM, {});
// @ts-ignore
__VLS_withDotValue(servedFromCache, {});
void {};
/** @type {__VLS_StyleScopedClasses['cm-item']} */ ;
/** @type {__VLS_StyleScopedClasses['cm-item']} */ ;
/** @type {__VLS_StyleScopedClasses['cm-item']} */ ;
/** @type {__VLS_StyleScopedClasses['on']} */ ;
/** @type {__VLS_StyleScopedClasses['cm-note']} */ ;
/** @type {__VLS_StyleScopedClasses['flow-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['switch-skeleton']} */ ;
/** @type {__VLS_StyleScopedClasses['switch-skeleton']} */ ;
/** @type {__VLS_StyleScopedClasses['switch-skeleton']} */ ;
/** @type {__VLS_StyleScopedClasses['switch-spinner']} */ ;
/** @type {__VLS_StyleScopedClasses['switch-skeleton']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter-bar__dragger']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter-bar__dragger']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['view-seg']} */ ;
/** @type {__VLS_StyleScopedClasses['view-seg']} */ ;
/** @type {__VLS_StyleScopedClasses['td-seg-item']} */ ;
/** @type {__VLS_StyleScopedClasses['dist-seg']} */ ;
/** @type {__VLS_StyleScopedClasses['dist-item']} */ ;
/** @type {__VLS_StyleScopedClasses['on']} */ ;
/** @type {__VLS_StyleScopedClasses['dist-item']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-toggle']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-toggle']} */ ;
/** @type {__VLS_StyleScopedClasses['on']} */ ;
/** @type {__VLS_StyleScopedClasses['pack-switch-item']} */ ;
/** @type {__VLS_StyleScopedClasses['pack-switch-item']} */ ;
/** @type {__VLS_StyleScopedClasses['pack-switch-item']} */ ;
/** @type {__VLS_StyleScopedClasses['on']} */ ;
/** @type {__VLS_StyleScopedClasses['dir-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['dir-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['dir-link']} */ ;
/** @type {__VLS_StyleScopedClasses['dir-cont']} */ ;
/** @type {__VLS_StyleScopedClasses['dir-cont']} */ ;
/** @type {__VLS_StyleScopedClasses['dir-cont']} */ ;
/** @type {__VLS_StyleScopedClasses['lm-item']} */ ;
/** @type {__VLS_StyleScopedClasses['lm-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['lm-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['tc19-table']} */ ;
/** @type {__VLS_StyleScopedClasses['tc19-table']} */ ;
/** @type {__VLS_StyleScopedClasses['tc19-table']} */ ;
/** @type {__VLS_StyleScopedClasses['c']} */ ;
/** @type {__VLS_StyleScopedClasses['band-card']} */ ;
/** @type {__VLS_StyleScopedClasses['band-card']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-link']} */ ;
/** @type {__VLS_StyleScopedClasses['route-tab']} */ ;
/** @type {__VLS_StyleScopedClasses['on']} */ ;
/** @type {__VLS_StyleScopedClasses['route-item']} */ ;
/** @type {__VLS_StyleScopedClasses['route-item']} */ ;
/** @type {__VLS_StyleScopedClasses['route-hint']} */ ;
/** @type {__VLS_StyleScopedClasses['warn']} */ ;
/** @type {__VLS_StyleScopedClasses['trip-line']} */ ;
/** @type {__VLS_StyleScopedClasses['landmark-note']} */ ;
/** @type {__VLS_StyleScopedClasses['landmark-group']} */ ;
/** @type {__VLS_StyleScopedClasses['se-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['warn']} */ ;
/** @type {__VLS_StyleScopedClasses['se-warn']} */ ;
/** @type {__VLS_StyleScopedClasses['se-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['col-right']} */ ;
/** @type {__VLS_StyleScopedClasses['col-right']} */ ;
/** @type {__VLS_StyleScopedClasses['route-card']} */ ;
/** @type {__VLS_StyleScopedClasses['col-right']} */ ;
/** @type {__VLS_StyleScopedClasses['td-card']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['color-mode-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['heat-band']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['stale-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-value']} */ ;
/** @type {__VLS_StyleScopedClasses['band-card']} */ ;
/** @type {__VLS_StyleScopedClasses['heat-band']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['col-left']} */ ;
/** @type {__VLS_StyleScopedClasses['col-mid']} */ ;
/** @type {__VLS_StyleScopedClasses['col-right']} */ ;
/** @type {__VLS_StyleScopedClasses['col-right']} */ ;
/** @type {__VLS_StyleScopedClasses['seg-card']} */ ;
/** @type {__VLS_StyleScopedClasses['map-card']} */ ;
/** @type {__VLS_StyleScopedClasses['map-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['map-toolbar-left']} */ ;
/** @type {__VLS_StyleScopedClasses['map-toolbar-right']} */ ;
/** @type {__VLS_StyleScopedClasses['heat-band']} */ ;
/** @type {__VLS_StyleScopedClasses['band-card']} */ ;
/** @type {__VLS_StyleScopedClasses['band-card']} */ ;
/** @type {__VLS_StyleScopedClasses['wide']} */ ;
/** @type {__VLS_StyleScopedClasses['band-card']} */ ;
/** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-left']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-right']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['color-mode-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['heat-band']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['stale-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['map-card']} */ ;
/** @type {__VLS_StyleScopedClasses['seg-card']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['seg-card']} */ ;
/** @type {__VLS_StyleScopedClasses['map-card']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['color-mode-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['heat-band']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['color-mode-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['stale-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-value']} */ ;
/** @type {__VLS_StyleScopedClasses['seg-card']} */ ;
/** @type {__VLS_StyleScopedClasses['map-card']} */ ;
/** @type {__VLS_StyleScopedClasses['map-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['map-caption']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['color-mode-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['heat-band']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['stale-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['cm-note']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-label']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-value']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-unit']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-sub']} */ ;
/** @type {__VLS_StyleScopedClasses['seg-card']} */ ;
/** @type {__VLS_StyleScopedClasses['map-card']} */ ;
/** @type {__VLS_StyleScopedClasses['map-toolbar-left']} */ ;
/** @type {__VLS_StyleScopedClasses['map-toolbar-right']} */ ;
/** @type {__VLS_StyleScopedClasses['pack-switch-item']} */ ;
/** @type {__VLS_StyleScopedClasses['map-caption']} */ ;
/** @type {__VLS_StyleScopedClasses['pred-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['dir-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['dir-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['k']} */ ;
/** @type {__VLS_StyleScopedClasses['dir-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['v']} */ ;
/** @type {__VLS_StyleScopedClasses['route-item-head']} */ ;
/** @type {__VLS_StyleScopedClasses['route-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['trip-segs']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-title']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-right']} */ ;
/** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
/** @type {__VLS_StyleScopedClasses['act-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['heat-band']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-label']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-value']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-sub']} */ ;
/** @type {__VLS_StyleScopedClasses['color-mode-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['cm-title']} */ ;
/** @type {__VLS_StyleScopedClasses['cm-item']} */ ;
/** @type {__VLS_StyleScopedClasses['cm-note']} */ ;
/** @type {__VLS_StyleScopedClasses['map-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['map-toolbar-left']} */ ;
/** @type {__VLS_StyleScopedClasses['map-title']} */ ;
/** @type {__VLS_StyleScopedClasses['map-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['map-toolbar-right']} */ ;
/** @type {__VLS_StyleScopedClasses['map-caption']} */ ;
/** @type {__VLS_StyleScopedClasses['band-card']} */ ;
/** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
/** @type {__VLS_StyleScopedClasses['heat-band']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-title']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-counts']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-link']} */ ;
/** @type {__VLS_StyleScopedClasses['view-seg']} */ ;
/** @type {__VLS_StyleScopedClasses['dist-legend']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['is-national']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['is-national']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['is-national']} */ ;
/** @type {__VLS_StyleScopedClasses['el-splitter-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['map-back-btn']} */ ;
(TD.value.brand);
(TD.value.brand);
(TD.value.brand);
// @ts-ignore
[TD, TD, TD,];
const __VLS_0 = AppShell || AppShell;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    // @ts-ignore
    active: "dashboard", station: (__VLS_unwrap(stationName, {})), ts: (__VLS_unwrap(snapshotTs, {})), sourceMode: (sourceMode.value), title: "",
}));
const __VLS_2 = __VLS_1({
    active: "dashboard",
    station: (__VLS_unwrap(stationName, {})),
    ts: (__VLS_unwrap(snapshotTs, {})),
    sourceMode: (sourceMode.value),
    title: "",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const { default: __VLS_5 } = __VLS_nonNull(__VLS_3.slots);
if (failedPanels.value.length > 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "stale-bar" },
        role: "status",
    });
    /** @type {__VLS_StyleScopedClasses['stale-bar']} */ ;
    (failedPanels.value.join(' / '));
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (refresh) },
        ...{ class: "td-btn sm" },
        type: "button",
    });
    /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
    /** @type {__VLS_StyleScopedClasses['sm']} */ ;
}
if (!sseConnected.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "stale-bar" },
        role: "status",
    });
    /** @type {__VLS_StyleScopedClasses['stale-bar']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (refresh) },
        ...{ class: "td-btn sm" },
        type: "button",
    });
    /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
    /** @type {__VLS_StyleScopedClasses['sm']} */ ;
}
if (cacheNote.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cache-bar" },
        role: "status",
    });
    /** @type {__VLS_StyleScopedClasses['cache-bar']} */ ;
    (cacheNote.value);
}
if (switching.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "switch-bar" },
        role: "status",
        'aria-live': "polite",
    });
    /** @type {__VLS_StyleScopedClasses['switch-bar']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
        ...{ class: "switch-spinner" },
        'aria-hidden': "true",
    });
    /** @type {__VLS_StyleScopedClasses['switch-spinner']} */ ;
    (__VLS_unwrap(stationName, {}));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "switch-skeleton" },
        'aria-hidden': "true",
    });
    /** @type {__VLS_StyleScopedClasses['switch-skeleton']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.i)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.i)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.i)({});
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card kpi-bar" },
});
/** @type {__VLS_StyleScopedClasses['td-card']} */ ;
/** @type {__VLS_StyleScopedClasses['kpi-bar']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "kpi-cell" },
});
/** @type {__VLS_StyleScopedClasses['kpi-cell']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "kpi-label" },
});
/** @type {__VLS_StyleScopedClasses['kpi-label']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "kpi-value" },
});
/** @type {__VLS_StyleScopedClasses['kpi-value']} */ ;
(fmt(overview.value?.avg_speed_kmh, 1));
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "kpi-unit" },
});
/** @type {__VLS_StyleScopedClasses['kpi-unit']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "kpi-sub" },
});
/** @type {__VLS_StyleScopedClasses['kpi-sub']} */ ;
(__VLS_unwrap(avgDeltaText, {}));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "kpi-cell" },
});
/** @type {__VLS_StyleScopedClasses['kpi-cell']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "kpi-label" },
});
/** @type {__VLS_StyleScopedClasses['kpi-label']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "kpi-value td-mono" },
});
/** @type {__VLS_StyleScopedClasses['kpi-value']} */ ;
/** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
(overview.value?.worst_segment?.segment_id ?? '—');
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "kpi-sub" },
});
/** @type {__VLS_StyleScopedClasses['kpi-sub']} */ ;
if (overview.value?.worst_segment) {
    const __VLS_6 = LevelBadge;
    // @ts-ignore
    const __VLS_7 = __VLS_asFunctionalComponent1(__VLS_6, new __VLS_6({
        // @ts-ignore
        level: (overview.value.worst_segment.level),
    }));
    const __VLS_8 = __VLS_7({
        level: (overview.value.worst_segment.level),
    }, ...__VLS_functionalComponentArgsRest(__VLS_7));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "kpi-sep" },
    });
    /** @type {__VLS_StyleScopedClasses['kpi-sep']} */ ;
    (overview.value.worst_segment.name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "kpi-sep" },
    });
    /** @type {__VLS_StyleScopedClasses['kpi-sep']} */ ;
    (fmt(overview.value.worst_segment.x));
}
else {
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "kpi-cell" },
});
/** @type {__VLS_StyleScopedClasses['kpi-cell']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "kpi-label" },
});
/** @type {__VLS_StyleScopedClasses['kpi-label']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "kpi-value" },
});
/** @type {__VLS_StyleScopedClasses['kpi-value']} */ ;
(overview.value?.vehicles_inbound ?? '—');
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "kpi-unit" },
});
/** @type {__VLS_StyleScopedClasses['kpi-unit']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "kpi-sub" },
});
/** @type {__VLS_StyleScopedClasses['kpi-sub']} */ ;
(__VLS_unwrap(adoptText, {}));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "kpi-cell" },
});
/** @type {__VLS_StyleScopedClasses['kpi-cell']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "kpi-label" },
});
/** @type {__VLS_StyleScopedClasses['kpi-label']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "kpi-value" },
});
/** @type {__VLS_StyleScopedClasses['kpi-value']} */ ;
(overview.value?.active_factors ?? '—');
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "kpi-unit" },
});
/** @type {__VLS_StyleScopedClasses['kpi-unit']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "kpi-sub" },
});
/** @type {__VLS_StyleScopedClasses['kpi-sub']} */ ;
if (topFactors.value.length > 0) {
    (topFactors.value.join(' · '));
}
else {
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "color-mode-bar" },
    role: "group",
    'aria-label': "颜色模式切换",
});
/** @type {__VLS_StyleScopedClasses['color-mode-bar']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "cm-title" },
});
/** @type {__VLS_StyleScopedClasses['cm-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: // @ts-ignore
        (...[$event]) => {
            void $event;
            return (setColorMode('congestion'));
            // @ts-ignore
            [stationName, stationName, snapshotTs, sourceMode, failedPanels, failedPanels, sseConnected, cacheNote, cacheNote, switching, overview, overview, overview, overview, overview, overview, overview, overview, avgDeltaText, adoptText, topFactors, topFactors,];
        } },
    type: "button",
    ...{ class: "cm-item" },
    ...{ class: ({ on: !isFlow.value }) },
    'aria-pressed': (!isFlow.value),
});
/** @type {__VLS_StyleScopedClasses['cm-item']} */ ;
/** @type {__VLS_StyleScopedClasses['on']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: // @ts-ignore
        (...[$event]) => {
            void $event;
            return (setColorMode('flow'));
            // @ts-ignore
            [isFlow, isFlow,];
        } },
    type: "button",
    ...{ class: "cm-item flow" },
    ...{ class: ({ on: isFlow.value }) },
    'aria-pressed': (isFlow.value),
});
/** @type {__VLS_StyleScopedClasses['cm-item']} */ ;
/** @type {__VLS_StyleScopedClasses['flow']} */ ;
/** @type {__VLS_StyleScopedClasses['on']} */ ;
if (isFlow.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "cm-note" },
    });
    /** @type {__VLS_StyleScopedClasses['cm-note']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    (__VLS_unwrap(FLOW_MODE_LABEL, {}));
    (__VLS_unwrap(FLOW_MODE_NOTE, {}));
    (__VLS_unwrap(FLOW_COLOR_NOTE, {}));
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "cm-note" },
    });
    /** @type {__VLS_StyleScopedClasses['cm-note']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-body" },
});
/** @type {__VLS_StyleScopedClasses['td-body']} */ ;
let __VLS_11;
/** @ts-ignore @type { | typeof __VLS_components.elSplitter | typeof __VLS_components.ElSplitter | typeof __VLS_components['el-splitter'] | typeof __VLS_components.elSplitter | typeof __VLS_components.ElSplitter | typeof __VLS_components['el-splitter']} */
elSplitter;
// @ts-ignore
const __VLS_12 = __VLS_asFunctionalComponent1(__VLS_11, new __VLS_11({
    // @ts-ignore
    ...{ 'onResizeEnd': {} }, ...{ 'onMousedown': {} }, ...{ class: "el-splitter td-splitter" }, ...{ class: ({ 'is-national': mapScope.value === 'national' }) },
}));
const __VLS_13 = __VLS_12({
    ...{ 'onResizeEnd': {} },
    ...{ 'onMousedown': {} },
    ...{ class: "el-splitter td-splitter" },
    ...{ class: ({ 'is-national': mapScope.value === 'national' }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_12));
let __VLS_16;
const __VLS_17 = {
    /** @type {typeof __VLS_16.resizeEnd} */
    onResizeEnd: (saveColMem),
};
void __VLS_17;
const __VLS_18 = {
    /** @type {typeof __VLS_16.mousedown} */
    onMousedown: (onBarMouseDown),
};
void __VLS_18;
/** @type {__VLS_StyleScopedClasses['el-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['td-splitter']} */ ;
/** @type {__VLS_StyleScopedClasses['is-national']} */ ;
const { default: __VLS_19 } = __VLS_nonNull(__VLS_14.slots);
let __VLS_20;
/** @ts-ignore @type { | typeof __VLS_components.elSplitterPanel | typeof __VLS_components.ElSplitterPanel | typeof __VLS_components['el-splitter-panel'] | typeof __VLS_components.elSplitterPanel | typeof __VLS_components.ElSplitterPanel | typeof __VLS_components['el-splitter-panel']} */
elSplitterPanel;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
    // @ts-ignore
    size: (__VLS_unwrap(colLeft, {})), min: (__VLS_unwrap(COL_MIN_LEFT, {})),
}));
const __VLS_22 = __VLS_21({
    size: (__VLS_unwrap(colLeft, {})),
    min: (__VLS_unwrap(COL_MIN_LEFT, {})),
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
const { default: __VLS_25 } = __VLS_nonNull(__VLS_23.slots);
if (mapScope.value === 'station') {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-col col-left" },
    });
    /** @type {__VLS_StyleScopedClasses['td-col']} */ ;
    /** @type {__VLS_StyleScopedClasses['col-left']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
        ...{ class: "td-card" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-head" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-head-tag" },
    });
    /** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
    (__VLS_unwrap(distTotal, {}));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-body" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-seg view-seg" },
        role: "group",
        'aria-label': "视图切换",
    });
    /** @type {__VLS_StyleScopedClasses['td-seg']} */ ;
    /** @type {__VLS_StyleScopedClasses['view-seg']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                if (!(mapScope.value === 'station'))
                    throw 0;
                return (viewMode.value = 'level');
                // @ts-ignore
                [isFlow, isFlow, isFlow, FLOW_MODE_LABEL, FLOW_MODE_NOTE, FLOW_COLOR_NOTE, mapScope, mapScope, colLeft, COL_MIN_LEFT, distTotal, viewMode,];
            } },
        ...{ class: "td-seg-item" },
        ...{ class: ({ on: viewMode.value === 'level' }) },
        role: "button",
        'aria-pressed': (viewMode.value === 'level'),
    });
    /** @type {__VLS_StyleScopedClasses['td-seg-item']} */ ;
    /** @type {__VLS_StyleScopedClasses['on']} */ ;
    (isFlow.value ? '流量四档' : '四级视图');
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                if (!(mapScope.value === 'station'))
                    throw 0;
                return (!isFlow.value && (viewMode.value = 'index'));
                // @ts-ignore
                [isFlow, isFlow, viewMode, viewMode, viewMode,];
            } },
        ...{ class: "td-seg-item" },
        ...{ class: ({ on: viewMode.value === 'index', disabled: isFlow.value }) },
        role: "button",
        'aria-pressed': (viewMode.value === 'index'),
        'aria-disabled': (isFlow.value),
        title: (isFlow.value ? '流量版不提供 CI 视图（CI 是决策口径）；切回决策拥堵版可用' : ''),
    });
    /** @type {__VLS_StyleScopedClasses['td-seg-item']} */ ;
    /** @type {__VLS_StyleScopedClasses['on']} */ ;
    /** @type {__VLS_StyleScopedClasses['disabled']} */ ;
    if (isFlow.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "note" },
        });
        /** @type {__VLS_StyleScopedClasses['note']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "dist-bar" },
        ...{ style: ({ background: TD.value.bgSecondary }) },
    });
    /** @type {__VLS_StyleScopedClasses['dist-bar']} */ ;
    const __VLS_26 = __VLS_tryAsConstant((__VLS_unwrap(dist, {})));
    for (const [r] of __VLS_vFor(__VLS_nonNull(__VLS_26))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
            ...{ onClick: // @ts-ignore
                (...[$event]) => {
                    void $event;
                    if (!(mapScope.value === 'station'))
                        throw 0;
                    return (toggleScope(r.level));
                    // @ts-ignore
                    [isFlow, isFlow, isFlow, isFlow, viewMode, viewMode, TD, dist,];
                } },
            key: (`d-${r.level}`),
            ...{ class: "dist-seg" },
            ...{ class: ({ dim: scope.value !== null && scope.value !== r.level }) },
            ...{ style: ({ width: distWidth(r), background: r.color }) },
            role: "button",
            title: (`只看 ${r.name}(${r.count} 个路段)`),
        });
        /** @type {__VLS_StyleScopedClasses['dist-seg']} */ ;
        /** @type {__VLS_StyleScopedClasses['dim']} */ ;
        // @ts-ignore
        [scope, scope,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "dist-legend" },
    });
    /** @type {__VLS_StyleScopedClasses['dist-legend']} */ ;
    const __VLS_27 = __VLS_tryAsConstant((__VLS_unwrap(dist, {})));
    for (const [r] of __VLS_vFor(__VLS_nonNull(__VLS_27))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ onClick: // @ts-ignore
                (...[$event]) => {
                    void $event;
                    if (!(mapScope.value === 'station'))
                        throw 0;
                    return (toggleScope(r.level));
                    // @ts-ignore
                    [dist,];
                } },
            key: (`lg-${r.level}`),
            ...{ class: "dist-item" },
            ...{ class: ({ on: scope.value === r.level }) },
            role: "button",
            'aria-pressed': (scope.value === r.level),
        });
        /** @type {__VLS_StyleScopedClasses['dist-item']} */ ;
        /** @type {__VLS_StyleScopedClasses['on']} */ ;
        if (isFlow.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                ...{ class: "flow-swatch" },
                ...{ style: ({ background: r.color }) },
            });
            /** @type {__VLS_StyleScopedClasses['flow-swatch']} */ ;
        }
        else {
            const __VLS_28 = LevelBadge;
            // @ts-ignore
            const __VLS_29 = __VLS_asFunctionalComponent1(__VLS_28, new __VLS_28({
                // @ts-ignore
                level: (r.level === 0 ? 1 : r.level), stale: (r.level === 0),
            }));
            const __VLS_30 = __VLS_29({
                level: (r.level === 0 ? 1 : r.level),
                stale: (r.level === 0),
            }, ...__VLS_functionalComponentArgsRest(__VLS_29));
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "td-num dist-count" },
        });
        /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
        /** @type {__VLS_StyleScopedClasses['dist-count']} */ ;
        (r.count);
        // @ts-ignore
        [isFlow, scope, scope,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                if (!(mapScope.value === 'station'))
                    throw 0;
                return (scope.value = null);
                // @ts-ignore
                [scope,];
            } },
        ...{ class: "dist-item all" },
        ...{ class: ({ on: scope.value === null }) },
        role: "button",
    });
    /** @type {__VLS_StyleScopedClasses['dist-item']} */ ;
    /** @type {__VLS_StyleScopedClasses['all']} */ ;
    /** @type {__VLS_StyleScopedClasses['on']} */ ;
    if (viewMode.value === 'index') {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "note" },
        });
        /** @type {__VLS_StyleScopedClasses['note']} */ ;
        (__VLS_unwrap(CI_DISCLAIMER, {}));
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
        ...{ class: "td-card seg-card" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card']} */ ;
    /** @type {__VLS_StyleScopedClasses['seg-card']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-head" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-head-tag" },
    });
    /** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
    (isFlow.value ? '按车流量降序' : viewMode.value === 'index' ? '按 CI 降序' : '按等级排序');
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-body flush seg-body" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
    /** @type {__VLS_StyleScopedClasses['flush']} */ ;
    /** @type {__VLS_StyleScopedClasses['seg-body']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-scroll seg-list" },
    });
    /** @type {__VLS_StyleScopedClasses['td-scroll']} */ ;
    /** @type {__VLS_StyleScopedClasses['seg-list']} */ ;
    if (viewMode.value === 'index') {
        const __VLS_33 = SegmentRankTable;
        // @ts-ignore
        const __VLS_34 = __VLS_asFunctionalComponent1(__VLS_33, new __VLS_33({
            // @ts-ignore
            ...{ 'onSelect': {} }, items: (__VLS_unwrap(rankRows, {})), selectedId: (selectedId.value),
        }));
        const __VLS_35 = __VLS_34({
            ...{ 'onSelect': {} },
            items: (__VLS_unwrap(rankRows, {})),
            selectedId: (selectedId.value),
        }, ...__VLS_functionalComponentArgsRest(__VLS_34));
        let __VLS_38;
        const __VLS_39 = {
            /** @type {typeof __VLS_38.select} */
            onSelect: (onSelect),
        };
        void __VLS_39;
        var __VLS_36;
        var __VLS_37;
    }
    else {
        const __VLS_40 = __VLS_tryAsConstant((segRows.value));
        for (const [row] of __VLS_vFor(__VLS_nonNull(__VLS_40))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ onClick: // @ts-ignore
                    (...[$event]) => {
                        void $event;
                        if (!(mapScope.value === 'station'))
                            throw 0;
                        if (!!(viewMode.value === 'index'))
                            throw 0;
                        return (onSelect(row.seg.segment_id));
                        // @ts-ignore
                        [isFlow, viewMode, viewMode, viewMode, scope, CI_DISCLAIMER, rankRows, selectedId, segRows,];
                    } },
                key: (row.seg.segment_id),
                ...{ class: "td-row" },
                ...{ class: ({ on: row.seg.segment_id === selectedId.value }) },
                role: "button",
                'aria-pressed': (row.seg.segment_id === selectedId.value),
            });
            /** @type {__VLS_StyleScopedClasses['td-row']} */ ;
            /** @type {__VLS_StyleScopedClasses['on']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                ...{ class: "lvl-bar" },
                ...{ style: ({ background: row.color }) },
            });
            /** @type {__VLS_StyleScopedClasses['lvl-bar']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "seg-meta" },
            });
            /** @type {__VLS_StyleScopedClasses['seg-meta']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "seg-name" },
            });
            /** @type {__VLS_StyleScopedClasses['seg-name']} */ ;
            (row.name);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "seg-id td-mono" },
            });
            /** @type {__VLS_StyleScopedClasses['seg-id']} */ ;
            /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
            (row.seg.segment_id);
            if (isFlow.value) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "seg-value td-num" },
                    ...{ style: ({ color: row.stale ? UNAVAILABLE.value.text : row.text }) },
                });
                /** @type {__VLS_StyleScopedClasses['seg-value']} */ ;
                /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
                (row.valueText);
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "flow-badge" },
                    ...{ class: ({ off: !row.flowBand }) },
                    ...{ style: (row.flowBand ? { background: row.flowBand.color, color: row.flowBand.textColor } : {}) },
                });
                /** @type {__VLS_StyleScopedClasses['flow-badge']} */ ;
                /** @type {__VLS_StyleScopedClasses['off']} */ ;
                (row.flowBand ? row.flowBand.name : __VLS_unwrap(FLOW_UNAVAILABLE_LABEL, {}));
            }
            else {
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "seg-value td-num" },
                    ...{ style: ({ color: row.stale ? UNAVAILABLE.value.text : row.text }) },
                });
                /** @type {__VLS_StyleScopedClasses['seg-value']} */ ;
                /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
                if (row.stale) {
                    (row.seg.data_age_s ?? '—');
                }
                else {
                    (fmt(row.seg.x));
                }
                const __VLS_41 = LevelBadge;
                // @ts-ignore
                const __VLS_42 = __VLS_asFunctionalComponent1(__VLS_41, new __VLS_41({
                    // @ts-ignore
                    level: (row.seg.level), stale: (row.stale),
                }));
                const __VLS_43 = __VLS_42({
                    level: (row.seg.level),
                    stale: (row.stale),
                }, ...__VLS_functionalComponentArgsRest(__VLS_42));
            }
            // @ts-ignore
            [isFlow, selectedId, selectedId, UNAVAILABLE, UNAVAILABLE, FLOW_UNAVAILABLE_LABEL,];
        }
        if (segRows.value.length === 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "empty" },
            });
            /** @type {__VLS_StyleScopedClasses['empty']} */ ;
            (switching.value
                ? '正在加载该站首屏快照…'
                : scope.value === null
                    ? '快照为空(接口层未起?)'
                    : '该范围当前没有路段');
        }
    }
}
// @ts-ignore
[switching, scope, segRows,];
var __VLS_23;
let __VLS_46;
/** @ts-ignore @type { | typeof __VLS_components.elSplitterPanel | typeof __VLS_components.ElSplitterPanel | typeof __VLS_components['el-splitter-panel'] | typeof __VLS_components.elSplitterPanel | typeof __VLS_components.ElSplitterPanel | typeof __VLS_components['el-splitter-panel']} */
elSplitterPanel;
// @ts-ignore
const __VLS_47 = __VLS_asFunctionalComponent1(__VLS_46, new __VLS_46({
    // @ts-ignore
    min: (__VLS_unwrap(COL_MIN_MID, {})),
}));
const __VLS_48 = __VLS_47({
    min: (__VLS_unwrap(COL_MIN_MID, {})),
}, ...__VLS_functionalComponentArgsRest(__VLS_47));
const { default: __VLS_51 } = __VLS_nonNull(__VLS_49.slots);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-col col-mid" },
});
/** @type {__VLS_StyleScopedClasses['td-col']} */ ;
/** @type {__VLS_StyleScopedClasses['col-mid']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
    ...{ class: "td-card map-card" },
});
/** @type {__VLS_StyleScopedClasses['td-card']} */ ;
/** @type {__VLS_StyleScopedClasses['map-card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "map-toolbar" },
});
/** @type {__VLS_StyleScopedClasses['map-toolbar']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "map-toolbar-left" },
});
/** @type {__VLS_StyleScopedClasses['map-toolbar-left']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "map-title" },
});
/** @type {__VLS_StyleScopedClasses['map-title']} */ ;
(mapScope.value === 'national' ? '全国地图' : '全路段状态');
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "map-tag" },
});
/** @type {__VLS_StyleScopedClasses['map-tag']} */ ;
(__VLS_unwrap(basemapTag, {}));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "map-toolbar-right" },
});
/** @type {__VLS_StyleScopedClasses['map-toolbar-right']} */ ;
if (!legendVisible.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                __VLS_withDotValue(legendVisible, {});
                if (!(!legendVisible.value))
                    throw 0;
                return (__VLS_unwrap(setLegendVisible, {})(true));
                // @ts-ignore
                [mapScope, COL_MIN_MID, basemapTag, legendVisible, setLegendVisible,];
            } },
        type: "button",
        ...{ class: "legend-toggle" },
        title: "展开图例",
        'aria-label': "展开图例",
    });
    /** @type {__VLS_StyleScopedClasses['legend-toggle']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: // @ts-ignore
        (...[$event]) => {
            void $event;
            __VLS_withDotValue(directionsVisible, {});
            return (__VLS_unwrap(setDirectionsVisible, {})(!directionsVisible.value));
            // @ts-ignore
            [setDirectionsVisible, directionsVisible,];
        } },
    type: "button",
    ...{ class: "legend-toggle" },
    ...{ class: ({ on: directionsVisible.value }) },
    'aria-pressed': (directionsVisible.value),
    title: (directionsVisible.value ? '隐藏方向箭头' : '显示方向箭头'),
    'aria-label': (directionsVisible.value ? '隐藏方向箭头' : '显示方向箭头'),
});
/** @type {__VLS_StyleScopedClasses['legend-toggle']} */ ;
/** @type {__VLS_StyleScopedClasses['on']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "pack-switch" },
    role: "group",
    'aria-label': "切换路网版本",
});
/** @type {__VLS_StyleScopedClasses['pack-switch']} */ ;
if (mapScope.value === 'station') {
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (enterNational) },
        type: "button",
        ...{ class: "map-back-btn" },
        title: "退回全国视角（地图缩远到中国范围，站点 pin 重新出现）",
    });
    /** @type {__VLS_StyleScopedClasses['map-back-btn']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "pack-switch" },
    role: "group",
    'aria-label': "已接入车站（切站：缩远 → 移动 → 放大）",
});
/** @type {__VLS_StyleScopedClasses['pack-switch']} */ ;
const __VLS_52 = __VLS_tryAsConstant((__VLS_unwrap(packChoices, {})));
for (const [p] of __VLS_vFor(__VLS_nonNull(__VLS_52))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                return (pickStation(p.key));
                // @ts-ignore
                [mapScope, directionsVisible, directionsVisible, directionsVisible, directionsVisible, packChoices,];
            } },
        key: (p.key),
        type: "button",
        ...{ class: "pack-switch-item" },
        ...{ class: ({ on: p.key === currentPackKey.value && mapScope.value === 'station' }) },
        'aria-pressed': (p.key === currentPackKey.value && mapScope.value === 'station'),
    });
    /** @type {__VLS_StyleScopedClasses['pack-switch-item']} */ ;
    /** @type {__VLS_StyleScopedClasses['on']} */ ;
    (p.name);
    // @ts-ignore
    [mapScope, mapScope, currentPackKey, currentPackKey,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "pack-switch" },
    role: "group",
    'aria-label': "凸显路线",
});
/** @type {__VLS_StyleScopedClasses['pack-switch']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: // @ts-ignore
        (...[$event]) => {
            void $event;
            return (__VLS_ctx.setRouteEmphasisEnabled(!__VLS_ctx.routeEmphasisEnabled));
            // @ts-ignore
            [setRouteEmphasisEnabled, routeEmphasisEnabled,];
        } },
    type: "button",
    ...{ class: "pack-switch-item" },
    ...{ class: ({ on: __VLS_ctx.routeEmphasisEnabled }) },
    role: "switch",
    'aria-checked': (__VLS_ctx.routeEmphasisEnabled),
    title: (__VLS_ctx.routeEmphasisEnabled
        ? '凸显路线：开（非路线段中性灰细线，不按等级上色）；点击恢复满图等级色'
        : '凸显路线：关（满图等级色 + 路线叠加）；点击压灰非路线段'),
});
/** @type {__VLS_StyleScopedClasses['pack-switch-item']} */ ;
/** @type {__VLS_StyleScopedClasses['on']} */ ;
(__VLS_ctx.routeEmphasisEnabled ? '开' : '关');
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-body flush map-body" },
});
/** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
/** @type {__VLS_StyleScopedClasses['flush']} */ ;
/** @type {__VLS_StyleScopedClasses['map-body']} */ ;
const __VLS_53 = MapLibreViewer;
// @ts-ignore
const __VLS_54 = __VLS_asFunctionalComponent1(__VLS_53, new __VLS_53({
    // @ts-ignore
    ...{ 'onSelect': {} }, ...{ 'onCloseLegend': {} }, ...{ 'onSwitchStation': {} }, ...{ 'onArrived': {} }, segments: (__VLS_unwrap(segments, {})), vehicles: (__VLS_unwrap(vehicles, {})), selectedId: (selectedId.value), routes: (__VLS_unwrap(routeHighlights, {})), routeStart: (__VLS_unwrap(routeStartMarker, {})), routeEnd: (__VLS_unwrap(routeEndMarker, {})), mode: (viewMode.value), colorMode: (__VLS_unwrap(colorMode, {})), mapMode: (mapScope.value), ts: (__VLS_unwrap(snapshotTs, {})), hoverChip: (__VLS_unwrap(mapChip, {})), legend: (legendVisible.value), '<<<<<<<': true, HEAD: true, '=': "=====",
}));
const __VLS_55 = __VLS_54({
    ...{ 'onSelect': {} },
    ...{ 'onCloseLegend': {} },
    ...{ 'onSwitchStation': {} },
    ...{ 'onArrived': {} },
    segments: (__VLS_unwrap(segments, {})),
    vehicles: (__VLS_unwrap(vehicles, {})),
    selectedId: (selectedId.value),
    routes: (__VLS_unwrap(routeHighlights, {})),
    routeStart: (__VLS_unwrap(routeStartMarker, {})),
    routeEnd: (__VLS_unwrap(routeEndMarker, {})),
    mode: (viewMode.value),
    colorMode: (__VLS_unwrap(colorMode, {})),
    mapMode: (mapScope.value),
    ts: (__VLS_unwrap(snapshotTs, {})),
    hoverChip: (__VLS_unwrap(mapChip, {})),
    legend: (legendVisible.value),
    '<<<<<<<': true,
    HEAD: true,
    '=': "=====",
}, ...__VLS_functionalComponentArgsRest(__VLS_54));
let __VLS_58;
const __VLS_59 = {
    /** @type {typeof __VLS_58.select} */
    onSelect: (onSelect),
};
void __VLS_59;
const __VLS_60 = {
    /** @type {typeof __VLS_58.closeLegend} */
    onCloseLegend: // @ts-ignore
    (...[$event]) => {
        void $event;
        return (__VLS_unwrap(setLegendVisible, {})(false));
        // @ts-ignore
        [snapshotTs, mapScope, viewMode, selectedId, legendVisible, setLegendVisible, routeEmphasisEnabled, routeEmphasisEnabled, routeEmphasisEnabled, routeEmphasisEnabled, segments, vehicles, routeHighlights, routeStartMarker, routeEndMarker, colorMode, mapChip,];
    },
};
void __VLS_60;
const __VLS_61 = {
    /** @type {typeof __VLS_58.switchStation} */
    onSwitchStation: (pickStation),
};
void __VLS_61;
const __VLS_62 = {
    /** @type {typeof __VLS_58.arrived} */
    onArrived: (onMotionArrived),
};
void __VLS_62;
const { default: __VLS_63 } = __VLS_nonNull(__VLS_56.slots);
// @ts-ignore
[];
var __VLS_56;
var __VLS_57;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "map-caption" },
});
/** @type {__VLS_StyleScopedClasses['map-caption']} */ ;
(__VLS_unwrap(mapCaption, {}));
// @ts-ignore
[mapCaption,];
var __VLS_49;
let __VLS_64;
/** @ts-ignore @type { | typeof __VLS_components.elSplitterPanel | typeof __VLS_components.ElSplitterPanel | typeof __VLS_components['el-splitter-panel'] | typeof __VLS_components.elSplitterPanel | typeof __VLS_components.ElSplitterPanel | typeof __VLS_components['el-splitter-panel']} */
elSplitterPanel;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent1(__VLS_64, new __VLS_64({
    // @ts-ignore
    size: (__VLS_unwrap(colRight, {})), min: (__VLS_unwrap(COL_MIN_RIGHT, {})),
}));
const __VLS_66 = __VLS_65({
    size: (__VLS_unwrap(colRight, {})),
    min: (__VLS_unwrap(COL_MIN_RIGHT, {})),
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
const { default: __VLS_69 } = __VLS_nonNull(__VLS_67.slots);
if (mapScope.value === 'station') {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-col col-right td-scroll" },
    });
    /** @type {__VLS_StyleScopedClasses['td-col']} */ ;
    /** @type {__VLS_StyleScopedClasses['col-right']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-scroll']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
        ...{ class: "td-card route-card" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card']} */ ;
    /** @type {__VLS_StyleScopedClasses['route-card']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-head" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-head-tag" },
    });
    /** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
    (__VLS_unwrap(routeSourceTag, {}));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-body" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "route-plan" },
    });
    /** @type {__VLS_StyleScopedClasses['route-plan']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "route-plan-head" },
    });
    /** @type {__VLS_StyleScopedClasses['route-plan-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-head-tag" },
    });
    /** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "route-badge" },
    });
    /** @type {__VLS_StyleScopedClasses['route-badge']} */ ;
    if (routeOptionsLoading.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "route-hint" },
        });
        /** @type {__VLS_StyleScopedClasses['route-hint']} */ ;
    }
    else if (routeOptions.value && routeOptions.value.options.length > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)({
            ...{ onChange: (onRouteSessionChange) },
            value: (__VLS_unwrap(selectedSession, {})),
            ...{ class: "route-select" },
            'aria-label': "选择引擎 OD / 行程",
        });
        /** @type {__VLS_StyleScopedClasses['route-select']} */ ;
        const __VLS_70 = __VLS_tryAsConstant((routeOptions.value.options));
        for (const [option] of __VLS_vFor(__VLS_nonNull(__VLS_70))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
                key: (option.session_id || option.request_id || ''),
                value: (option.session_id || ''),
            });
            (option.od_id ?? 'OD');
            (option.location.segment_id ?? '—');
            if (option.location.segment_id) {
                (nameOf(option.location.segment_id));
            }
            (fmtEta(option.arrival_route?.eta_min));
            // @ts-ignore
            [mapScope, colRight, COL_MIN_RIGHT, routeSourceTag, routeOptionsLoading, routeOptions, routeOptions, routeOptions, selectedSession,];
        }
        if (tripSummary.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "trip-summary" },
            });
            /** @type {__VLS_StyleScopedClasses['trip-summary']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "trip-line" },
            });
            /** @type {__VLS_StyleScopedClasses['trip-line']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
            (tripSummary.value.start);
            (tripSummary.value.arrivalSegments);
            (tripSummary.value.arrivalEta);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "trip-segs td-mono" },
            });
            /** @type {__VLS_StyleScopedClasses['trip-segs']} */ ;
            /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
            (tripSummary.value.arrivalPath || '—');
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "trip-line" },
            });
            /** @type {__VLS_StyleScopedClasses['trip-line']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
            (tripSummary.value.dropoff ?? '引擎产物未给落客点（如实空窗）');
            (tripSummary.value.alternatives);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "trip-line" },
            });
            /** @type {__VLS_StyleScopedClasses['trip-line']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
            if (tripSummary.value.departureSegments > 0) {
                (tripSummary.value.departureSegments);
                (tripSummary.value.departureEta);
            }
            else {
            }
            if (tripSummary.value.departurePath) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "trip-segs td-mono" },
                });
                /** @type {__VLS_StyleScopedClasses['trip-segs']} */ ;
                /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
                (tripSummary.value.departurePath);
            }
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "route-source" },
            });
            /** @type {__VLS_StyleScopedClasses['route-source']} */ ;
            (tripSummary.value.source);
            ((routeOptions.value.segment_namespaces || []).join(' / ') || '—');
        }
    }
    else if (routeOptionsError.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "route-hint" },
        });
        /** @type {__VLS_StyleScopedClasses['route-hint']} */ ;
        if (USE_MOCK.value) {
        }
        else {
            (routeOptionsError.value);
        }
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "route-hint" },
        });
        /** @type {__VLS_StyleScopedClasses['route-hint']} */ ;
    }
    if (recommendLoading.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "route-hint" },
        });
        /** @type {__VLS_StyleScopedClasses['route-hint']} */ ;
    }
    else if (recommendError.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "route-hint warn" },
        });
        /** @type {__VLS_StyleScopedClasses['route-hint']} */ ;
        /** @type {__VLS_StyleScopedClasses['warn']} */ ;
        (recommendError.value);
    }
    else if (recommend.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "route-tabs" },
        });
        /** @type {__VLS_StyleScopedClasses['route-tabs']} */ ;
        const __VLS_71 = __VLS_tryAsConstant((__VLS_unwrap(ROUTE_VIEWS, {})));
        for (const [t] of __VLS_vFor(__VLS_nonNull(__VLS_71))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                ...{ onClick: // @ts-ignore
                    (...[$event]) => {
                        void $event;
                        if (!(mapScope.value === 'station'))
                            throw 0;
                        if (!!(recommendLoading.value))
                            throw 0;
                        if (!!(recommendError.value))
                            throw 0;
                        if (!(recommend.value))
                            throw 0;
                        return (routeView.value = t.key);
                        // @ts-ignore
                        [routeOptions, tripSummary, tripSummary, tripSummary, tripSummary, tripSummary, tripSummary, tripSummary, tripSummary, tripSummary, tripSummary, tripSummary, tripSummary, tripSummary, routeOptionsError, routeOptionsError, USE_MOCK, recommendLoading, recommendError, recommendError, recommend, ROUTE_VIEWS, routeView,];
                    } },
                key: (t.key),
                type: "button",
                ...{ class: "route-tab" },
                ...{ class: ({ on: routeView.value === t.key }) },
            });
            /** @type {__VLS_StyleScopedClasses['route-tab']} */ ;
            /** @type {__VLS_StyleScopedClasses['on']} */ ;
            (t.name);
            // @ts-ignore
            [routeView,];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "route-meta" },
        });
        /** @type {__VLS_StyleScopedClasses['route-meta']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "route-badge" },
        });
        /** @type {__VLS_StyleScopedClasses['route-badge']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "start-end" },
        });
        /** @type {__VLS_StyleScopedClasses['start-end']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "se-block" },
        });
        /** @type {__VLS_StyleScopedClasses['se-block']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "se-head" },
        });
        /** @type {__VLS_StyleScopedClasses['se-head']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "se-tag" },
            ...{ class: ({ warn: !startConfirmed.value }) },
        });
        /** @type {__VLS_StyleScopedClasses['se-tag']} */ ;
        /** @type {__VLS_StyleScopedClasses['warn']} */ ;
        (startConfirmed.value ? '已确认' : '未确认');
        if (locateLoading.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "se-tag" },
            });
            /** @type {__VLS_StyleScopedClasses['se-tag']} */ ;
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "se-line" },
        });
        /** @type {__VLS_StyleScopedClasses['se-line']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
            ...{ class: "td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (currentStart.value?.segment_id ?? '—');
        (__VLS_unwrap(startName, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "se-line" },
        });
        /** @type {__VLS_StyleScopedClasses['se-line']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
        (startBoundarySection.value ? `外围边界断面 ${startBoundarySection.value.point_id}` : '路网内部段');
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "se-note" },
        });
        /** @type {__VLS_StyleScopedClasses['se-note']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "se-line" },
        });
        /** @type {__VLS_StyleScopedClasses['se-line']} */ ;
        (__VLS_unwrap(startSourceLabel, {}));
        (__VLS_unwrap(offsetText, {}));
        (__VLS_unwrap(confidenceText, {}));
        if (!startConfirmed.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "se-note" },
            });
            /** @type {__VLS_StyleScopedClasses['se-note']} */ ;
            (__VLS_unwrap(startSourceLabel, {}));
        }
        if (confidenceLow.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "se-warn" },
            });
            /** @type {__VLS_StyleScopedClasses['se-warn']} */ ;
        }
        if (locateError.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "se-note" },
            });
            /** @type {__VLS_StyleScopedClasses['se-note']} */ ;
            (locateError.value);
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "se-actions" },
        });
        /** @type {__VLS_StyleScopedClasses['se-actions']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (confirmStart) },
            type: "button",
            ...{ class: "se-btn" },
            disabled: (!currentStart.value),
        });
        /** @type {__VLS_StyleScopedClasses['se-btn']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)({
            value: (manualStartId.value),
            ...{ class: "route-select se-select" },
            'aria-label': "手动选择起点路段",
        });
        /** @type {__VLS_StyleScopedClasses['route-select']} */ ;
        /** @type {__VLS_StyleScopedClasses['se-select']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
            value: "",
        });
        const __VLS_72 = __VLS_tryAsConstant((__VLS_unwrap(packSegments, {})));
        for (const [seg] of __VLS_vFor(__VLS_nonNull(__VLS_72))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
                key: (seg.segment_id),
                value: (seg.segment_id),
            });
            (seg.segment_id);
            (seg.name);
            // @ts-ignore
            [startConfirmed, startConfirmed, startConfirmed, locateLoading, currentStart, currentStart, startName, startBoundarySection, startBoundarySection, startSourceLabel, startSourceLabel, offsetText, confidenceText, confidenceLow, locateError, locateError, manualStartId, packSegments,];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (applyManualStart) },
            type: "button",
            ...{ class: "se-btn" },
            disabled: (!manualStartId.value),
        });
        /** @type {__VLS_StyleScopedClasses['se-btn']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "se-block" },
        });
        /** @type {__VLS_StyleScopedClasses['se-block']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "se-head" },
        });
        /** @type {__VLS_StyleScopedClasses['se-head']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "se-tag" },
        });
        /** @type {__VLS_StyleScopedClasses['se-tag']} */ ;
        if (tripEnd.value?.drop) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "se-line" },
            });
            /** @type {__VLS_StyleScopedClasses['se-line']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
                ...{ class: "td-mono" },
            });
            /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
            (tripEnd.value.drop);
            if (tripEnd.value.pointName) {
                (tripEnd.value.pointName);
            }
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "se-line" },
            });
            /** @type {__VLS_StyleScopedClasses['se-line']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
                ...{ class: "td-mono" },
            });
            /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
            (tripEnd.value.last ?? '—');
            (tripEnd.value.lastName);
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "se-line" },
            });
            /** @type {__VLS_StyleScopedClasses['se-line']} */ ;
            if (tripEnd.value?.reason) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                    ...{ class: "se-note" },
                });
                /** @type {__VLS_StyleScopedClasses['se-note']} */ ;
                (tripEnd.value.reason);
            }
            else {
                __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                    ...{ class: "se-note" },
                });
                /** @type {__VLS_StyleScopedClasses['se-note']} */ ;
            }
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "se-line" },
            });
            /** @type {__VLS_StyleScopedClasses['se-line']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
                ...{ class: "td-mono" },
            });
            /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
            (tripEnd.value?.last ?? '—');
            (tripEnd.value?.lastName ?? '—');
        }
        if (routeSourceNote.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "route-source" },
            });
            /** @type {__VLS_StyleScopedClasses['route-source']} */ ;
            (routeSourceNote.value);
        }
        const __VLS_73 = __VLS_tryAsConstant((__VLS_unwrap(routeCards, {})));
        for (const [c] of __VLS_vFor(__VLS_nonNull(__VLS_73))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                key: (c.key),
                ...{ class: "route-item" },
                ...{ class: (c.kind) },
            });
            /** @type {__VLS_StyleScopedClasses['route-item']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "route-item-head" },
            });
            /** @type {__VLS_StyleScopedClasses['route-item-head']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "route-kind" },
            });
            /** @type {__VLS_StyleScopedClasses['route-kind']} */ ;
            (c.kindName);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "route-eta td-num" },
            });
            /** @type {__VLS_StyleScopedClasses['route-eta']} */ ;
            /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
            (c.eta);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "route-segs td-mono" },
            });
            /** @type {__VLS_StyleScopedClasses['route-segs']} */ ;
            /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
            (c.segments.join(' → ') || '—');
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "route-note" },
            });
            /** @type {__VLS_StyleScopedClasses['route-note']} */ ;
            (c.note);
            // @ts-ignore
            [manualStartId, tripEnd, tripEnd, tripEnd, tripEnd, tripEnd, tripEnd, tripEnd, tripEnd, tripEnd, tripEnd, routeSourceNote, routeSourceNote, routeCards,];
        }
        if (recommend.value.alternatives.length < 2) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "route-hint warn" },
            });
            /** @type {__VLS_StyleScopedClasses['route-hint']} */ ;
            /** @type {__VLS_StyleScopedClasses['warn']} */ ;
            (recommend.value.alternatives.length);
            if (recommend.value.no_alternative_reason) {
                (recommend.value.no_alternative_reason);
            }
        }
        if (routeMissing.value.length) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "route-hint warn" },
            });
            /** @type {__VLS_StyleScopedClasses['route-hint']} */ ;
            /** @type {__VLS_StyleScopedClasses['warn']} */ ;
            (routeMissing.value.length);
            (routeMissing.value.join(', '));
        }
        if (recommend.value.session_matched === false) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "route-hint warn" },
            });
            /** @type {__VLS_StyleScopedClasses['route-hint']} */ ;
            /** @type {__VLS_StyleScopedClasses['warn']} */ ;
            (recommend.value.requested_session_id);
            __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "route-why" },
        });
        /** @type {__VLS_StyleScopedClasses['route-why']} */ ;
        (__VLS_unwrap(routeWhyLine, {}));
        if (routeDegradedNote.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "route-hint" },
            });
            /** @type {__VLS_StyleScopedClasses['route-hint']} */ ;
            (routeDegradedNote.value);
        }
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "route-hint" },
        });
        /** @type {__VLS_StyleScopedClasses['route-hint']} */ ;
    }
    if (landmarksVisible.value && __VLS_unwrap(landmarkCount, {}) > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
            ...{ class: "td-card landmark-card" },
        });
        /** @type {__VLS_StyleScopedClasses['td-card']} */ ;
        /** @type {__VLS_StyleScopedClasses['landmark-card']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "td-card-head" },
        });
        /** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "td-head-tag" },
        });
        /** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "td-card-body" },
        });
        /** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "landmark-note" },
        });
        /** @type {__VLS_StyleScopedClasses['landmark-note']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "landmark-group" },
        });
        /** @type {__VLS_StyleScopedClasses['landmark-group']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "landmark-group-head" },
        });
        /** @type {__VLS_StyleScopedClasses['landmark-group-head']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "landmark-count" },
        });
        /** @type {__VLS_StyleScopedClasses['landmark-count']} */ ;
        (packDropoffs.value.length);
        if (packDropoffs.value.length) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
                ...{ class: "landmark-list" },
            });
            /** @type {__VLS_StyleScopedClasses['landmark-list']} */ ;
            const __VLS_74 = __VLS_tryAsConstant((packDropoffs.value));
            for (const [d] of __VLS_vFor(__VLS_nonNull(__VLS_74))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
                    key: (d.id),
                    ...{ class: "landmark-item" },
                });
                /** @type {__VLS_StyleScopedClasses['landmark-item']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "landmark-id td-mono" },
                });
                /** @type {__VLS_StyleScopedClasses['landmark-id']} */ ;
                /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
                (d.id);
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "landmark-name" },
                });
                /** @type {__VLS_StyleScopedClasses['landmark-name']} */ ;
                (d.name);
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "landmark-ll td-mono" },
                });
                /** @type {__VLS_StyleScopedClasses['landmark-ll']} */ ;
                /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
                (fmtLonLat(d.lon, d.lat));
                // @ts-ignore
                [recommend, recommend, recommend, recommend, recommend, recommend, routeMissing, routeMissing, routeMissing, routeWhyLine, routeDegradedNote, routeDegradedNote, landmarksVisible, landmarkCount, packDropoffs, packDropoffs, packDropoffs,];
            }
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "landmark-empty" },
            });
            /** @type {__VLS_StyleScopedClasses['landmark-empty']} */ ;
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "landmark-group" },
        });
        /** @type {__VLS_StyleScopedClasses['landmark-group']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "landmark-group-head" },
        });
        /** @type {__VLS_StyleScopedClasses['landmark-group-head']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "landmark-count" },
        });
        /** @type {__VLS_StyleScopedClasses['landmark-count']} */ ;
        (packZones.value.length);
        if (packZones.value.length) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
                ...{ class: "landmark-list" },
            });
            /** @type {__VLS_StyleScopedClasses['landmark-list']} */ ;
            const __VLS_75 = __VLS_tryAsConstant((packZones.value));
            for (const [z] of __VLS_vFor(__VLS_nonNull(__VLS_75))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
                    key: (z.id),
                    ...{ class: "landmark-item" },
                });
                /** @type {__VLS_StyleScopedClasses['landmark-item']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "landmark-id td-mono" },
                });
                /** @type {__VLS_StyleScopedClasses['landmark-id']} */ ;
                /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
                (z.id);
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "landmark-name" },
                });
                /** @type {__VLS_StyleScopedClasses['landmark-name']} */ ;
                (z.name);
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "landmark-ll td-mono" },
                });
                /** @type {__VLS_StyleScopedClasses['landmark-ll']} */ ;
                /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
                (fmtLonLat(z.lon, z.lat));
                // @ts-ignore
                [packZones, packZones, packZones,];
            }
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "landmark-empty" },
            });
            /** @type {__VLS_StyleScopedClasses['landmark-empty']} */ ;
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "landmark-foot" },
        });
        /** @type {__VLS_StyleScopedClasses['landmark-foot']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (__VLS_unwrap(landmarkPackKey, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (__VLS_unwrap(landmarkArrivalDropoff, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
        ...{ class: "td-card" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-head" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-head-tag td-mono" },
    });
    /** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
    (selected.value?.segment_id ?? selectedId.value ?? '—');
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-body" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
    if (selectedId.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "d-title" },
        });
        /** @type {__VLS_StyleScopedClasses['d-title']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "d-name" },
        });
        /** @type {__VLS_StyleScopedClasses['d-name']} */ ;
        (__VLS_unwrap(selectedName, {}));
        if (selected.value) {
            const __VLS_76 = LevelBadge;
            // @ts-ignore
            const __VLS_77 = __VLS_asFunctionalComponent1(__VLS_76, new __VLS_76({
                // @ts-ignore
                level: (selected.value.level), stale: (__VLS_unwrap(isStale, {})(selected.value)),
            }));
            const __VLS_78 = __VLS_77({
                level: (selected.value.level),
                stale: (__VLS_unwrap(isStale, {})(selected.value)),
            }, ...__VLS_functionalComponentArgsRest(__VLS_77));
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "td-chip" },
            });
            /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "d-summary" },
        });
        /** @type {__VLS_StyleScopedClasses['d-summary']} */ ;
        (selected.value
            ? __VLS_unwrap(detailSummary, {})
            : '该路段在当前快照里没有运行指标（段号未被感知 / 孪生产物覆盖）——不显示等级，按数据不可用灰档处理（TC-11）。');
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "dir-block" },
        });
        /** @type {__VLS_StyleScopedClasses['dir-block']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "sec-head" },
        });
        /** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "sub-tag" },
        });
        /** @type {__VLS_StyleScopedClasses['sub-tag']} */ ;
        (__VLS_unwrap(segDirectionLabel, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "td-chip" },
            ...{ class: ({ warn: segContinuity.value.state === 'pending' }) },
        });
        /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
        /** @type {__VLS_StyleScopedClasses['warn']} */ ;
        (segContinuity.value.label);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "dir-kv" },
        });
        /** @type {__VLS_StyleScopedClasses['dir-kv']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "k" },
        });
        /** @type {__VLS_StyleScopedClasses['k']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "v" },
        });
        /** @type {__VLS_StyleScopedClasses['v']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
        (__VLS_unwrap(segDirectionLabel, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "dir-src" },
        });
        /** @type {__VLS_StyleScopedClasses['dir-src']} */ ;
        (__VLS_unwrap(segDirectionSource, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "dir-kv" },
        });
        /** @type {__VLS_StyleScopedClasses['dir-kv']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "k" },
        });
        /** @type {__VLS_StyleScopedClasses['k']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "v" },
        });
        /** @type {__VLS_StyleScopedClasses['v']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (segLanes.value.text);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "dir-src" },
        });
        /** @type {__VLS_StyleScopedClasses['dir-src']} */ ;
        (segLanes.value.source);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "dir-kv" },
        });
        /** @type {__VLS_StyleScopedClasses['dir-kv']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "k" },
        });
        /** @type {__VLS_StyleScopedClasses['k']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "v" },
        });
        /** @type {__VLS_StyleScopedClasses['v']} */ ;
        if (segOpposite.value && segOppositePresent.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                ...{ onClick: // @ts-ignore
                    (...[$event]) => {
                        void $event;
                        if (!(mapScope.value === 'station'))
                            throw 0;
                        if (!(selectedId.value))
                            throw 0;
                        if (!(segOpposite.value && segOppositePresent.value))
                            throw 0;
                        return (onSelect(segOpposite.value));
                        // @ts-ignore
                        [selectedId, selectedId, landmarkPackKey, landmarkArrivalDropoff, selected, selected, selected, selected, selected, selectedName, isStale, detailSummary, segDirectionLabel, segDirectionLabel, segContinuity, segContinuity, segDirectionSource, segLanes, segLanes, segOpposite, segOpposite, segOppositePresent,];
                    } },
                type: "button",
                ...{ class: "dir-link" },
                title: (`跳转到对向段 ${segOpposite.value}`),
            });
            /** @type {__VLS_StyleScopedClasses['dir-link']} */ ;
            (segOpposite.value);
        }
        else if (segOpposite.value) {
            (segOpposite.value);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "dir-src" },
            });
            /** @type {__VLS_StyleScopedClasses['dir-src']} */ ;
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "dir-src" },
        });
        /** @type {__VLS_StyleScopedClasses['dir-src']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "dir-kv" },
        });
        /** @type {__VLS_StyleScopedClasses['dir-kv']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "k" },
        });
        /** @type {__VLS_StyleScopedClasses['k']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "v" },
        });
        /** @type {__VLS_StyleScopedClasses['v']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "dir-cont" },
            ...{ class: (segContinuity.value.tone) },
        });
        /** @type {__VLS_StyleScopedClasses['dir-cont']} */ ;
        (segContinuity.value.label);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "dir-detail" },
        });
        /** @type {__VLS_StyleScopedClasses['dir-detail']} */ ;
        (segContinuity.value.detail);
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "dir-note" },
        });
        /** @type {__VLS_StyleScopedClasses['dir-note']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lm-block" },
        });
        /** @type {__VLS_StyleScopedClasses['lm-block']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "sec-head" },
        });
        /** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "sub-tag" },
        });
        /** @type {__VLS_StyleScopedClasses['sub-tag']} */ ;
        (nearbyLandmarks.value.length);
        if (nearbyLandmarks.value.length === 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "lm-empty" },
            });
            /** @type {__VLS_StyleScopedClasses['lm-empty']} */ ;
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
                ...{ class: "lm-list" },
            });
            /** @type {__VLS_StyleScopedClasses['lm-list']} */ ;
            const __VLS_81 = __VLS_tryAsConstant((nearbyLandmarks.value));
            for (const [p] of __VLS_vFor(__VLS_nonNull(__VLS_81))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
                    key: (`${p.kind}-${p.id}`),
                });
                __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                    ...{ onClick: // @ts-ignore
                        (...[$event]) => {
                            void $event;
                            if (!(mapScope.value === 'station'))
                                throw 0;
                            if (!(selectedId.value))
                                throw 0;
                            if (!!(nearbyLandmarks.value.length === 0))
                                throw 0;
                            return (onSelect(p.segment_id));
                            // @ts-ignore
                            [segContinuity, segContinuity, segContinuity, segOpposite, segOpposite, segOpposite, segOpposite, nearbyLandmarks, nearbyLandmarks, nearbyLandmarks,];
                        } },
                    type: "button",
                    ...{ class: "lm-item" },
                    title: (`${p.name} · 所属路段 ${p.segment_id || '未标定'} · ${p.id} · 演示点 · 点击选中该路段`),
                });
                /** @type {__VLS_StyleScopedClasses['lm-item']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "lm-icon" },
                    ...{ class: (p.kind) },
                });
                /** @type {__VLS_StyleScopedClasses['lm-icon']} */ ;
                (p.kind === 'dropoff' ? '落' : '场');
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "lm-main" },
                });
                /** @type {__VLS_StyleScopedClasses['lm-main']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "lm-name" },
                });
                /** @type {__VLS_StyleScopedClasses['lm-name']} */ ;
                (p.name);
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "lm-meta" },
                });
                /** @type {__VLS_StyleScopedClasses['lm-meta']} */ ;
                (p.segment_id || '路段未标定');
                (p.id);
                (landmarkDistance(p.distance_m));
                // @ts-ignore
                [];
            }
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "lm-note" },
        });
        /** @type {__VLS_StyleScopedClasses['lm-note']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
        const __VLS_82 = SegmentCameraCard;
        // @ts-ignore
        const __VLS_83 = __VLS_asFunctionalComponent1(__VLS_82, new __VLS_82({
            // @ts-ignore
            segmentId: (selectedId.value || ''),
        }));
        const __VLS_84 = __VLS_83({
            segmentId: (selectedId.value || ''),
        }, ...__VLS_functionalComponentArgsRest(__VLS_83));
        const __VLS_87 = SegmentDecisionSummary;
        // @ts-ignore
        const __VLS_88 = __VLS_asFunctionalComponent1(__VLS_87, new __VLS_87({
            // @ts-ignore
            segmentId: (selectedId.value || ''), record: (selected.value), factors: (segFactors.value), thresholds: (__VLS_unwrap(thresholds, {})), stale: (selected.value ? __VLS_unwrap(isStale, {})(selected.value) : true),
        }));
        const __VLS_89 = __VLS_88({
            segmentId: (selectedId.value || ''),
            record: (selected.value),
            factors: (segFactors.value),
            thresholds: (__VLS_unwrap(thresholds, {})),
            stale: (selected.value ? __VLS_unwrap(isStale, {})(selected.value) : true),
        }, ...__VLS_functionalComponentArgsRest(__VLS_88));
        const __VLS_92 = SegmentDispatchCard;
        // @ts-ignore
        const __VLS_93 = __VLS_asFunctionalComponent1(__VLS_92, new __VLS_92({
            // @ts-ignore
            ...{ 'onChanged': {} }, segmentId: (selectedId.value || ''), record: (selected.value), alerts: (__VLS_unwrap(alerts, {})),
        }));
        const __VLS_94 = __VLS_93({
            ...{ 'onChanged': {} },
            segmentId: (selectedId.value || ''),
            record: (selected.value),
            alerts: (__VLS_unwrap(alerts, {})),
        }, ...__VLS_functionalComponentArgsRest(__VLS_93));
        let __VLS_97;
        const __VLS_98 = {
            /** @type {typeof __VLS_97.changed} */
            onChanged: (onCommandChanged),
        };
        void __VLS_98;
        var __VLS_95;
        var __VLS_96;
        if (selected.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "ci-head" },
            });
            /** @type {__VLS_StyleScopedClasses['ci-head']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "idx-ci td-num" },
                ...{ style: ({ color: __VLS_unwrap(ciTextColor, {}) }) },
            });
            /** @type {__VLS_StyleScopedClasses['idx-ci']} */ ;
            /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
            (__VLS_unwrap(ciText, {}));
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "ci-side" },
            });
            /** @type {__VLS_StyleScopedClasses['ci-side']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "ci-label" },
            });
            /** @type {__VLS_StyleScopedClasses['ci-label']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "ci-sub" },
            });
            /** @type {__VLS_StyleScopedClasses['ci-sub']} */ ;
            (__VLS_unwrap(weightText, {}));
            const __VLS_99 = __VLS_tryAsConstant((__VLS_unwrap(weights, {})));
            for (const [w] of __VLS_vFor(__VLS_nonNull(__VLS_99))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    key: (w.key),
                    ...{ class: "wt-row" },
                });
                /** @type {__VLS_StyleScopedClasses['wt-row']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "wt-label" },
                });
                /** @type {__VLS_StyleScopedClasses['wt-label']} */ ;
                (w.label);
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "wt-val td-mono" },
                });
                /** @type {__VLS_StyleScopedClasses['wt-val']} */ ;
                /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
                (metricText(w.key));
                (w.weight.toFixed(2));
                // @ts-ignore
                [selectedId, selectedId, selectedId, selected, selected, selected, selected, selected, isStale, segFactors, thresholds, alerts, ciTextColor, ciText, weightText, weights,];
            }
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "sec-head" },
            });
            /** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.table, __VLS_intrinsics.table)({
                ...{ class: "td-table tc19-table" },
            });
            /** @type {__VLS_StyleScopedClasses['td-table']} */ ;
            /** @type {__VLS_StyleScopedClasses['tc19-table']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.thead, __VLS_intrinsics.thead)({});
            __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({});
            __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({});
            if (sourceMode.value !== 'twin') {
                __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
                    ...{ class: "c" },
                });
                /** @type {__VLS_StyleScopedClasses['c']} */ ;
            }
            if (sourceMode.value !== 'video') {
                __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
                    ...{ class: "c" },
                });
                /** @type {__VLS_StyleScopedClasses['c']} */ ;
            }
            if (sourceMode.value === 'both') {
                __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
                    ...{ class: "c" },
                });
                /** @type {__VLS_StyleScopedClasses['c']} */ ;
            }
            __VLS_asFunctionalElement1(__VLS_intrinsics.tbody, __VLS_intrinsics.tbody)({});
            const __VLS_100 = __VLS_tryAsConstant((__VLS_unwrap(deltaRows, {})));
            for (const [d] of __VLS_vFor(__VLS_nonNull(__VLS_100))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({
                    key: (d.key),
                });
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
                (d.label);
                if (sourceMode.value !== 'twin') {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                        ...{ class: "c td-num" },
                    });
                    /** @type {__VLS_StyleScopedClasses['c']} */ ;
                    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
                    (typeof d.video === 'number' ? d.video : '—');
                }
                if (sourceMode.value !== 'video') {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                        ...{ class: "c td-num" },
                    });
                    /** @type {__VLS_StyleScopedClasses['c']} */ ;
                    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
                    (typeof d.twin === 'number' ? d.twin : '—');
                }
                if (sourceMode.value === 'both') {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                        ...{ class: "c td-num" },
                    });
                    /** @type {__VLS_StyleScopedClasses['c']} */ ;
                    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
                    (typeof d.delta === 'number' ? `${d.delta > 0 ? '+' : ''}${d.delta}` : '—');
                }
                // @ts-ignore
                [sourceMode, sourceMode, sourceMode, sourceMode, sourceMode, sourceMode, deltaRows,];
            }
            if (pair.value && !videoAvailable.value) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                    ...{ class: "tc19-none" },
                });
                /** @type {__VLS_StyleScopedClasses['tc19-none']} */ ;
            }
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "tc19-note" },
            });
            /** @type {__VLS_StyleScopedClasses['tc19-note']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "sec-head" },
            });
            /** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "sub-tag" },
            });
            /** @type {__VLS_StyleScopedClasses['sub-tag']} */ ;
            (segFactors.value.length);
            const __VLS_101 = FactorBreakdown;
            // @ts-ignore
            const __VLS_102 = __VLS_asFunctionalComponent1(__VLS_101, new __VLS_101({
                // @ts-ignore
                factors: (segFactors.value),
            }));
            const __VLS_103 = __VLS_102({
                factors: (segFactors.value),
            }, ...__VLS_functionalComponentArgsRest(__VLS_102));
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "sec-head" },
            });
            /** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
            (history.value?.points.length ?? 12);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "sub-tag" },
            });
            /** @type {__VLS_StyleScopedClasses['sub-tag']} */ ;
            const __VLS_106 = CiTrendBars;
            // @ts-ignore
            const __VLS_107 = __VLS_asFunctionalComponent1(__VLS_106, new __VLS_106({
                // @ts-ignore
                history: (history.value),
            }));
            const __VLS_108 = __VLS_107({
                history: (history.value),
            }, ...__VLS_functionalComponentArgsRest(__VLS_107));
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "sec-head" },
            });
            /** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "td-chip warn" },
            });
            /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
            /** @type {__VLS_StyleScopedClasses['warn']} */ ;
            if (selected.value.pred) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "pred-grid" },
                });
                /** @type {__VLS_StyleScopedClasses['pred-grid']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "pred-box" },
                });
                /** @type {__VLS_StyleScopedClasses['pred-box']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "pred-h" },
                });
                /** @type {__VLS_StyleScopedClasses['pred-h']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "pred-v td-num" },
                });
                /** @type {__VLS_StyleScopedClasses['pred-v']} */ ;
                /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
                (selected.value.pred.h15.q_vph);
                const __VLS_111 = LevelBadge;
                // @ts-ignore
                const __VLS_112 = __VLS_asFunctionalComponent1(__VLS_111, new __VLS_111({
                    // @ts-ignore
                    level: (selected.value.pred.h15.level),
                }));
                const __VLS_113 = __VLS_112({
                    level: (selected.value.pred.h15.level),
                }, ...__VLS_functionalComponentArgsRest(__VLS_112));
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "pred-box" },
                });
                /** @type {__VLS_StyleScopedClasses['pred-box']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "pred-h" },
                });
                /** @type {__VLS_StyleScopedClasses['pred-h']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "pred-v td-num" },
                });
                /** @type {__VLS_StyleScopedClasses['pred-v']} */ ;
                /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
                (selected.value.pred.h30.q_vph);
                const __VLS_116 = LevelBadge;
                // @ts-ignore
                const __VLS_117 = __VLS_asFunctionalComponent1(__VLS_116, new __VLS_116({
                    // @ts-ignore
                    level: (selected.value.pred.h30.level),
                }));
                const __VLS_118 = __VLS_117({
                    level: (selected.value.pred.h30.level),
                }, ...__VLS_functionalComponentArgsRest(__VLS_117));
            }
            else {
                __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                    ...{ class: "empty" },
                });
                /** @type {__VLS_StyleScopedClasses['empty']} */ ;
            }
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "empty sm" },
            });
            /** @type {__VLS_StyleScopedClasses['empty']} */ ;
            /** @type {__VLS_StyleScopedClasses['sm']} */ ;
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "sec-head" },
        });
        /** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "sub-tag" },
        });
        /** @type {__VLS_StyleScopedClasses['sub-tag']} */ ;
        (selectedAlerts.value.length);
        const __VLS_121 = AlertList;
        // @ts-ignore
        const __VLS_122 = __VLS_asFunctionalComponent1(__VLS_121, new __VLS_121({
            // @ts-ignore
            alerts: (selectedAlerts.value), levelOf: (segLevelOf),
        }));
        const __VLS_123 = __VLS_122({
            alerts: (selectedAlerts.value),
            levelOf: (segLevelOf),
        }, ...__VLS_functionalComponentArgsRest(__VLS_122));
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (gotoDecision) },
            ...{ class: "td-btn act-btn" },
            type: "button",
        });
        /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
        /** @type {__VLS_StyleScopedClasses['act-btn']} */ ;
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "empty" },
        });
        /** @type {__VLS_StyleScopedClasses['empty']} */ ;
    }
}
// @ts-ignore
[selected, selected, selected, selected, selected, segFactors, segFactors, pair, videoAvailable, history, history, selectedAlerts, selectedAlerts,];
var __VLS_67;
// @ts-ignore
[];
var __VLS_14;
var __VLS_15;
if (mapScope.value === 'station') {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "heat-band" },
    });
    /** @type {__VLS_StyleScopedClasses['heat-band']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
        ...{ class: "td-card band-card" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card']} */ ;
    /** @type {__VLS_StyleScopedClasses['band-card']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-head" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-head-tag" },
    });
    /** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
    (isFlow.value ? `流量四档 · ${__VLS_unwrap(FLOW_UNAVAILABLE_LABEL, {})} ${__VLS_unwrap(unavailableCount, {})}` : `灰档 ${__VLS_unwrap(unavailableCount, {})}`);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-body" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
    const __VLS_126 = BandDistribution;
    // @ts-ignore
    const __VLS_127 = __VLS_asFunctionalComponent1(__VLS_126, new __VLS_126({
        // @ts-ignore
        rows: (__VLS_unwrap(bandRows, {})), unavailable: (__VLS_unwrap(unavailableCount, {})), unavailableLabel: (isFlow.value ? __VLS_unwrap(FLOW_UNAVAILABLE_LABEL, {}) : '不可用'),
    }));
    const __VLS_128 = __VLS_127({
        rows: (__VLS_unwrap(bandRows, {})),
        unavailable: (__VLS_unwrap(unavailableCount, {})),
        unavailableLabel: (isFlow.value ? __VLS_unwrap(FLOW_UNAVAILABLE_LABEL, {}) : '不可用'),
    }, ...__VLS_functionalComponentArgsRest(__VLS_127));
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "note" },
    });
    /** @type {__VLS_StyleScopedClasses['note']} */ ;
    (__VLS_unwrap(distTotal, {}));
    (isFlow.value ? `${__VLS_unwrap(FLOW_UNAVAILABLE_LABEL, {})}不计入分档,分档阈值见 shared/flow.ts` : '灰档不计入均值,与地图同源');
    __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
        ...{ class: "td-card band-card wide" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card']} */ ;
    /** @type {__VLS_StyleScopedClasses['band-card']} */ ;
    /** @type {__VLS_StyleScopedClasses['wide']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-head" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-head-tag" },
    });
    /** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
    (isFlow.value ? '流量版：仅当前快照桶有 q，历史桶灰' : '最近 12 个快照 · 每 60 s 一档 · 左旧右新');
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-body flush" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
    /** @type {__VLS_StyleScopedClasses['flush']} */ ;
    const __VLS_131 = HeatMatrixTable;
    // @ts-ignore
    const __VLS_132 = __VLS_asFunctionalComponent1(__VLS_131, new __VLS_131({
        // @ts-ignore
        matrix: (isFlow.value ? __VLS_unwrap(flowHeat, {}) : __VLS_unwrap(heat, {})), mode: (isFlow.value ? 'flow' : 'ci'),
    }));
    const __VLS_133 = __VLS_132({
        matrix: (isFlow.value ? __VLS_unwrap(flowHeat, {}) : __VLS_unwrap(heat, {})),
        mode: (isFlow.value ? 'flow' : 'ci'),
    }, ...__VLS_functionalComponentArgsRest(__VLS_132));
    if (isFlow.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "note" },
            ...{ style: {} },
        });
        /** @type {__VLS_StyleScopedClasses['note']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
        ...{ class: "td-card band-card" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card']} */ ;
    /** @type {__VLS_StyleScopedClasses['band-card']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-head" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-head-tag td-mono" },
    });
    /** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
    (__VLS_unwrap(formatStamp, {})(__VLS_unwrap(snapshotTs, {})));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-body" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
    const __VLS_136 = CiScale;
    // @ts-ignore
    const __VLS_137 = __VLS_asFunctionalComponent1(__VLS_136, new __VLS_136({
    // @ts-ignore
    }));
    const __VLS_138 = __VLS_137({}, ...__VLS_functionalComponentArgsRest(__VLS_137));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "gray-row" },
    });
    /** @type {__VLS_StyleScopedClasses['gray-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.i)({
        ...{ class: "gray-swatch" },
    });
    /** @type {__VLS_StyleScopedClasses['gray-swatch']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "note" },
    });
    /** @type {__VLS_StyleScopedClasses['note']} */ ;
    (__VLS_unwrap(CI_BAND_NOTE, {}));
    if (isFlow.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "note" },
        });
        /** @type {__VLS_StyleScopedClasses['note']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card alert-bar" },
});
/** @type {__VLS_StyleScopedClasses['td-card']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-bar']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "alert-left" },
});
/** @type {__VLS_StyleScopedClasses['alert-left']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "alert-icon" },
    'aria-hidden': "true",
});
/** @type {__VLS_StyleScopedClasses['alert-icon']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "alert-title" },
});
/** @type {__VLS_StyleScopedClasses['alert-title']} */ ;
(firstAlert.value ? `${LEVELS.value[segLevelOf(firstAlert.value)].name}（${CN_NUM.value[segLevelOf(firstAlert.value)]}级）` : '—');
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "alert-summary" },
});
/** @type {__VLS_StyleScopedClasses['alert-summary']} */ ;
if (firstAlert.value) {
    (firstAlert.value.alert_id);
    (firstAlert.value.segment_name);
    (__VLS_unwrap(firstAlertX, {}));
    (hhmmss(firstAlert.value.first_seen));
    (firstAlert.value.triggered_by.join(', '));
}
else {
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "alert-right" },
});
/** @type {__VLS_StyleScopedClasses['alert-right']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "alert-counts" },
});
/** @type {__VLS_StyleScopedClasses['alert-counts']} */ ;
(__VLS_unwrap(unclaimedCount, {}));
(__VLS_unwrap(processingCount, {}));
let __VLS_141;
/** @ts-ignore @type { | typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
RouterLink;
// @ts-ignore
const __VLS_142 = __VLS_asFunctionalComponent1(__VLS_141, new __VLS_141({
    // @ts-ignore
    ...{ class: "alert-link" }, to: "/decision",
}));
const __VLS_143 = __VLS_142({
    ...{ class: "alert-link" },
    to: "/decision",
}, ...__VLS_functionalComponentArgsRest(__VLS_142));
/** @type {__VLS_StyleScopedClasses['alert-link']} */ ;
const { default: __VLS_146 } = __VLS_nonNull(__VLS_144.slots);
// @ts-ignore
[snapshotTs, isFlow, isFlow, isFlow, isFlow, isFlow, isFlow, isFlow, isFlow, mapScope, distTotal, FLOW_UNAVAILABLE_LABEL, FLOW_UNAVAILABLE_LABEL, FLOW_UNAVAILABLE_LABEL, unavailableCount, unavailableCount, unavailableCount, bandRows, flowHeat, heat, formatStamp, CI_BAND_NOTE, firstAlert, firstAlert, firstAlert, firstAlert, firstAlert, firstAlert, firstAlert, firstAlert, LEVELS, CN_NUM, firstAlertX, unclaimedCount, processingCount,];
var __VLS_144;
{
    const { foot: __VLS_147 } = __VLS_nonNull(__VLS_3.slots);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (__VLS_unwrap(formatStamp, {})(__VLS_unwrap(snapshotTs, {})));
    if (servedFromCache.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (__VLS_unwrap(footStationLine, {}));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (__VLS_unwrap(footDataSource, {}));
    (__VLS_unwrap(sourceLabel, {}));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (__VLS_unwrap(packLine, {}));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (isFlow.value ? '纯车流量（q 四档，仅展示，不代表拥堵结论）' : '决策拥堵（接口 level）');
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "right" },
    });
    /** @type {__VLS_StyleScopedClasses['right']} */ ;
    if (isFlow.value) {
        (__VLS_unwrap(FLOW_MODE_LABEL, {}));
        (__VLS_unwrap(FLOW_MODE_NOTE, {}));
        (__VLS_unwrap(FLOW_COLOR_NOTE, {}));
    }
    else {
        (__VLS_unwrap(CI_DISCLAIMER, {}));
    }
    // @ts-ignore
    [snapshotTs, isFlow, isFlow, FLOW_MODE_LABEL, FLOW_MODE_NOTE, FLOW_COLOR_NOTE, CI_DISCLAIMER, formatStamp, servedFromCache, footStationLine, footDataSource, sourceLabel, packLine,];
}
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
