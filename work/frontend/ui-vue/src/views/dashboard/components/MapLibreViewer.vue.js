/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
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
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue';
import { Map as MapLibreMap, Marker, NavigationControl, ScaleControl, setWorkerUrl, } from 'maplibre-gl';
// ⚠️ 必须显式指定 worker 地址，否则**生产构建底图空白**（实测踩过）：
//   MapLibre 的矢量瓦片解析跑在独立 worker 里（508 KB），主包按
//   `new URL('./maplibre-gl-worker.mjs', import.meta.url)` 找它。dev 下（已 exclude 出依赖预打包）
//   它恰好与主包同目录、能被 Vite 直接端出来；但**打包后那个兄弟文件不会被产出** ——
//   dist 里只有 index.js/css，运行时去要 `/assets/maplibre-gl-worker.mjs` 直接落空，
//   报「Worker failed to load」，地图整块空白且不报 HTTP 错（worker 加载失败不走 response 事件）。
//   用 `?url` 让 Vite 把这个 worker 文件真正产出到 assets/ 并返回它的地址。
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import 'maplibre-gl/dist/maplibre-gl.css';
const { defineProps, defineEmits, withDefaults, } = {};
setWorkerUrl(maplibreWorkerUrl);
import { DEMO_NETWORK, isOsmNetwork, networkSourceLabel, OSM_ATTRIBUTION, OSM_COPYRIGHT_URL, } from '../../../shared/demoNetwork';
import { cameraPins, isCameraCovered, perceptionHref, } from '../../../shared/cameras';
import { DRIVER_COLORS, TD } from '../../../shared/theme';
import { basemapEnabled, directionsVisible, legendVisible, routeEmphasisEnabled, setLegendVisible, } from '../../../shared/settings';
import { activePack, activePackKey, onPackChange, packVersion, stationEntries, } from '../../../station-packs/index';
// IKPFVN：全国视角 / 站区视角的镜头运动集中在 `shared/mapMotion.ts`（时长、中国范围、留白、打断规则）
import { cancelMotion, clampOverviewZoom, flyToOverview, flyToStation, overviewCamera, overviewPadding, stationCamera, stationPadding, } from '../../../shared/mapMotion';
// 底图拉不到时的**兜底轮廓**（Natural Earth 1:110m 简化，公有领域）。
// ⚠️ 用 `?raw` 把文件当**文本**导入，而不是 `import … from '…geojson'`：
//    ① `.geojson` 不是 `.json`，`resolveJsonModule` 不认它（改 tsconfig 属于为一个素材文件动全局配置）；
//    ② `?url` 也不行 —— Vite 的已知素材类型表里没有 `.geojson`，打包时直接报 Module not found；
//    ③ 进 `public/` 又要把素材搬一份。`?raw` 内联成字符串、运行时 `JSON.parse`，零配置、零重复文件。
import chinaOutlineText from '../../../assets/geo/china-outline.geojson?raw';
import { landmarkKindLabel, landmarkPins, } from '../../../shared/landmarks';
// IKOQEJ：方向标记（只读 enriched 字段；不是判级/契约数据）
import { bearingDeg, directionKindOf, directionOf, pointAtFraction, } from '../../../shared/directions';
import { FLOW_BANDS, FLOW_COLOR_NOTE, FLOW_MODE_LABEL, FLOW_MODE_NOTE, flowBandOf, flowRangeLabel, } from '../../../shared/flow';
import { BASEMAP_PROXY_PROBE, BASEMAP_STYLE_URL, setBasemapProxyDetected, toBasemapUrl, } from '../../../shared/basemap';
import { ciAvailable, ciGradientCss, ciStyleColor, CI_BAND_NOTE, CI_BANDS, CI_DISCLAIMER, CI_MAX, levelStyle, UNAVAILABLE, } from '../../../shared/traffic';
import LevelBadge from './LevelBadge.vue';
const BRAND = TD.brand;
/**
 * OpenFreeMap 的 Liberty 样式（免 Key、免注册；数据来自 OpenStreetMap）。
 * 地址口径与"同源直通"开关都在 `shared/basemap.ts`（本机系统代理会黑洞掉上游域名，见那里注释）。
 */
const STYLE_URL = BASEMAP_STYLE_URL;
/**
 * **本地兜底样式**：不依赖任何公网资源，只用来把地图建起来。
 * 路网图层与摄像头图钉在这份样式上就位，因此"底图能不能拉到"**不参与**路网是否画得出来。
 */
const FALLBACK_STYLE = { version: 8, sources: {}, layers: [] };
/** 底图**样式**拉取上限：超时即按"底图不可用"处理，**不阻塞路网** */
const BASEMAP_TIMEOUT_MS = 8000;
/**
 * 底图**瓦片**就绪上限。样式拿到 ≠ 底图画得出来：本机实测过"样式命中 HTTP 缓存 3 ms 返回 200，
 * 而 tilejson / `.pbf` 全部挂到超时"——那时地图只剩 Liberty 样式里的底色层（没有路、没有建筑），
 * 旧代码却已经把状态写成 `ok`。所以拿到样式后还要**等矢量瓦片真的就绪**，等不到一样算失败。
 */
const BASEMAP_TILES_TIMEOUT_MS = 8000;
/** 同源直通代理的探测上限（探不到就直连上游，不能让探测本身拖慢建图） */
const BASEMAP_PROBE_TIMEOUT_MS = 1500;
const SRC = 'hubflow-route';
// IKOQEJ · 方向标记：独立 GeoJSON 点源 + canvas 生成的图标（不依赖字体 glyph ——
// 底图挂掉走本地兜底样式时也能画，不会只剩一根无方向的线）
const DIR_SRC = 'hubflow-direction';
const LAYER_DIRECTION = `${DIR_SRC}-marker`;
const DIR_ICON_PREFIX = 'hubflow-dir-';
/** 方向语义色（与拥堵等级色 / 品牌蓝 / 路线三态色都不撞）：只表示方向，不表示拥堵 */
const DIR_COLORS = {
    forward: '#1D5FD8',
    backward: '#B45309',
    bidirectional: '#6D28D9',
    unknown: '#8B8B8B',
};
const LAYER_HEAT = `${SRC}-heat`;
const LAYER_CASING = `${SRC}-casing`;
const LAYER_LINE = `${SRC}-line`;
/** 推荐路线（品牌蓝实线；「当前 / 已选」语义，不得用等级色） */
const LAYER_ROUTE_HALO = `${SRC}-route-halo`;
const LAYER_ROUTE = `${SRC}-route`;
/**
 * 备选 1 / 备选 2（Issue IKP5CK）：两条备选必须**互相可区分**（原来一起画灰虚线）。
 * 分两个图层而不是一个「按属性取色」的图层：两者的**虚线节律 + 平行偏移**也不同，
 * 叠在同一段路时靠「颜色 + 节律 + ±2px 平行线」三重区分，不只靠颜色单通道。
 */
const LAYER_ROUTE_ALT1_HALO = `${SRC}-route-alt1-halo`;
const LAYER_ROUTE_ALT1 = `${SRC}-route-alt1`;
const LAYER_ROUTE_ALT2_HALO = `${SRC}-route-alt2-halo`;
const LAYER_ROUTE_ALT2 = `${SRC}-route-alt2`;
/** 离站路线（紫色实线；第三种语义色，与等级色 / 品牌蓝分开） */
const LAYER_ROUTE_DEP_HALO = `${SRC}-route-dep-halo`;
const LAYER_ROUTE_DEP = `${SRC}-route-dep`;
const LAYER_SELECTED = `${SRC}-selected`;
// ---- IKPFVN · 全国视角的两个图层族（站点 pin / 底图兜底轮廓）----
//
// 为什么站点用 GeoJSON source + 图层，而不是 DOM Marker：站只会越加越多（现为 Z / GZ），
// DOM Marker 每个都要建元素、挂事件、随地图重排；图层一次挂好，加站只换 data。
// 点击 / 悬停也走同一条通道（`queryRenderedFeatures`），不用给每个 pin 绑一对监听。
const STATION_SRC = 'hubflow-station';
/** 透明大圆：**只用来命中**（视觉半径 6~9 px，命中半径 15 px → 30 px 热区，≥ 24 px 要求） */
const LAYER_STATION_HIT = `${STATION_SRC}-hit`;
/** 站点实心圆；选中环就画在**它自己**身上（`feature-state.selected`），不另建一套图层 */
const LAYER_STATION_DOT = `${STATION_SRC}-dot`;
/** 站名（canvas 生成图片的 symbol 图层，见 `stationLabelLayerSpec()` 里为什么不用 text-field） */
const LAYER_STATION_LABEL = `${STATION_SRC}-label`;
const STATION_LABEL_ICON_PREFIX = 'hubflow-station-label-';
/** 非当前站的中性深灰（品牌蓝只给「当前 / 已选」） */
const STATION_DOT_COLOR = '#475569';
/** 底图拉不到时的中国轮廓（淡填充 + 细描边，不抢路网） */
const OUTLINE_SRC = 'hubflow-china-outline';
const LAYER_OUTLINE_FILL = `${OUTLINE_SRC}-fill`;
const LAYER_OUTLINE_LINE = `${OUTLINE_SRC}-line`;
const EMPTY_FC = { type: 'FeatureCollection', features: [] };
/**
 * 备选 1 = 青 `#0E7490`、备选 2 = 琥珀 `#B45309`（队长 2026-10-20 裁定）：
 * 两色都避开四级判级色（#2BA471 / #E9B32E / #E37318 / #D54941）、
 * 数据不可用灰 #8B8B8B、品牌蓝 #0052D9、离站紫 #7B61FF。
 * 虚线节律再分一套：备选 1 长虚（12/6）、备选 2 短虚（2.5/4.5）。
 */
const ROUTE_ALT1_COLOR = '#0E7490';
const ROUTE_ALT2_COLOR = '#B45309';
/** 离站路线色（紫色；与品牌蓝 / 四级色都不撞，只表示"第 3 种路线语义"） */
const ROUTE_DEPART_COLOR = '#7B61FF';
/**
 * 「凸显路线」时非路线段的中性灰（Issue IKP5CK）。
 * 必须与「数据不可用灰」#8B8B8B 视觉可区分：更浅（#C9CDD4）、更细（2 px vs 5.5 px）、
 * 透明度更低（0.55）、**不加虚线**；且只有路线存在、开关打开时才生效。
 */
const ROUTE_EMPHASIS_GRAY = '#C9CDD4';
/** 悬停浮牌尺寸（只用于翻面判断，与 CSS 里的 min/max-width 对应） */
const CHIP_W = 210;
const CHIP_H = 26;
/** 摄像头浮牌宽度（与 <style> 中 .cam-chip 的 width 保持一致；窄屏 CSS 会用 min() 收小） */
const CAM_CHIP_W = 192;
/** 落客点 / 场区浮牌宽度（与 <style> 中 .lm-chip 的 width 保持一致；窄屏同样用 min() 收小） */
const LM_CHIP_W = 220;
/** 全国站点浮牌宽度（与 <style> 中 .st-chip 的 width 保持一致） */
const ST_CHIP_W = 176;
const props = withDefaults(defineProps(), {
    vehicles: () => [],
    routes: () => [],
    routeStart: null,
    routeEnd: null,
    mode: 'level',
    colorMode: 'congestion',
    ts: '',
    hoverChip: '',
    legend: true,
    mapMode: 'national',
});
const emit = defineEmits();
/** 容器**始终渲染**（不用 v-if 挂载），从根上避免「容器还没进 DOM 就初始化」那类静默失败 */
const containerRef = ref(null);
/**
 * ⚠️ 地图实例用 `shallowRef`：`ref()` 会对它做深度解包（`UnwrapRef`），
 * 解出来的类型丢掉类的私有成员与方法，再传回 `map.setFilter(...)` 这类接口就报
 * 「missing _setupResizeObserver」的假类型错；何况地图实例本来也不该被深度代理。
 */
const mapRef = shallowRef(null);
/** 路网是否已经就位 —— **只判本地样式**，不判公网底图 */
const ready = ref(false);
/**
 * 底图这一层的状态（**只管底图，不管路网**）：
 *   `off`     —— 顶栏「设置」里关掉了：不拉任何底图资源，只剩路网（＝原「示例路网」观感）
 *   `loading` —— 正在拉 OpenFreeMap 样式
 *   `ok`      —— 底图已合入
 *   `failed`  —— 拉不到：路网照画 + 角标给「重试」，并按退避自动重试
 */
const basemap = ref(basemapEnabled.value ? 'loading' : 'off');
const basemapMsg = ref('');
/**
 * 「正在再试一次」——**只在失败态追加**，不把状态切回 `loading`。
 * 为什么：自动重试若把角标切回「加载中」，那个模板分支会把「重试」按钮**卸载再挂载**，
 * 按钮在 DOM 里不稳定（实测：CDP 点它时被 Playwright 判为 "element is not stable"，
 * 点了 30 s 点不上）。留在失败态、只换按钮文案，按钮才点得动。
 */
const basemapRetrying = ref(false);
/** 失败后的**退避自动重试**间隔（手动「重试」会把计数清零） */
const RETRY_DELAYS_MS = [2000, 6000, 12000];
let retryStep = 0;
let retryTimer = 0;
/**
 * 底图这一轮拉取的**代次**。每次 `applyBasemap` 自增，用来让"上一轮"的异步尾巴（瓦片轮询、
 * 关开关后的在途请求）认出自己已经过期 —— 只看 `disposed` 不够：开关一开一关、或手动连点两次
 * 「重试」时，旧那一轮还会把状态写回 `ok`。
 */
let basemapRun = 0;
/** 当前挂载的是不是"底图已合入"的那份样式（关开关时据此决定要不要换回兜底样式） */
let remoteApplied = false;
/**
 * 在途的底图请求。关开关时**连在途的那一次也 abort 掉** ——
 * 否则"关＝一个请求都不发"只在冷启动成立（页面已加载再关，在途那一次仍会走完）。
 */
let inflightCtrl = null;
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
const net = shallowRef(DEMO_NETWORK.segments);
/**
 * 包键代号：切站时 +1。所有"读 activePack() 的 computed / 一次性快照"都靠它刷新。
 * 注意 `packVersion()` 是模块级**数字**，不是 Vue 的 ref —— 所以这里自己建一个 ref 订阅。
 */
const packTick = ref(packVersion());
const offPackTick = onPackChange(() => {
    packTick.value = packVersion();
});
const sourceLabel = computed(() => {
    void packTick.value;
    return networkSourceLabel();
});
const osmActive = computed(() => {
    void packTick.value;
    return isOsmNetwork();
});
/** 当前站键（响应式）：挂在容器 `data-station` 上，切站后跟着变 */
const currentStationKey = computed(() => {
    void packTick.value;
    return activePackKey();
});
/**
 * 全国浮层 / 站点 pin 的点击：只**请求**切站，真正的切站在父级（唯一入口 `switchStation()`）。
 * 本组件不碰包、不碰数据 —— 否则又会出现“地图自己换了一套包、面板还停在上一坑”的老毛病。
 */
function pickStation(key) {
    emit('switch-station', key);
}
/**
 * 上色策略由站点包 `colorPolicy` 决定（IKP5DM 起 Z/GZ 均为 `'all'`：全段按等级上色，
 * 灰只表示数据不可用/陈旧，不再表示「这段没摄像头」）。
 * 图钉与上色策略**解耦**：图钉只画源台账 6 路，图例按 `pins.length` 显隐（见模板）。
 */
/** 摄像头图钉（随包变化：Z 站 6 路源台账 / GZ 站 0 路） */
const pins = computed(() => {
    void packTick.value;
    return cameraPins();
});
// ---- 路段染色（四级 / 指数两种视图） ----
const segById = computed(() => new Map(props.segments.map((s) => [s.segment_id, s])));
const isIndex = computed(() => props.mode === 'index');
/** 纯车流量版（Issue IKNB9G）：颜色只看 q_vph 分档，忽略 level / CI / 摄像头覆盖策略 */
const isFlow = computed(() => props.colorMode === 'flow');
/**
 * 该段是否"有可展示的数据"（决定线宽 / 透明度）。
 *   · 拥堵版：沿用「只摄像头段上色」策略（业主 2026-10-15）；色块按 level / CI；
 *   · 流量版：**有 q 且不陈旧**即可上色（流量是全网口径，不受摄像头覆盖限制），缺 q 灰档。
 */
function coveredOf(seg) {
    if (isFlow.value)
        return flowBandOf(segById.value.get(seg.segment_id)) !== null;
    return isCameraCovered(seg.segment_id);
}
/**
 * 路段色。四档，别混：
 *   ① 流量版：q 四档蓝阶（缺 q / 陈旧 → 灰）；
 *   ② 拥堵版有监控且数据可用 → 等级色 / ci 色阶；
 *   ③ 拥堵版有监控但数据不可用 → 灰（粗，`UNAVAILABLE`）；
 *   ④ 拥堵版**没监控** → 灰（细、淡）——"这段没摄像头"本身是个信息，不能与 ③ 长得一样。
 */
function colorOf(seg) {
    const rec = segById.value.get(seg.segment_id);
    if (isFlow.value) {
        return flowBandOf(rec)?.color ?? UNAVAILABLE.color;
    }
    if (!isCameraCovered(seg.segment_id))
        return UNAVAILABLE.color;
    if (!rec)
        return UNAVAILABLE.color;
    return isIndex.value ? ciStyleColor(rec) : levelStyle(rec).color;
}
/** 热力晕染强度（**仅拥堵版指数视图**且 ci 可用；流量版、四级视图一律 0 = 不画）。
 *
 * ⚠️ 四级视图必须返 0（业主 2026-10-20 口径：「每个道路都要颜色，然后周围还有往外衍生的一圈
 * 淡淡的颜色，把那个去掉」）。四级色本身已经把等级说清楚了，26 px 的半透明同色宽带只是往两边
 * 漫出去的雾；广州南站 708 段那种密度下，几百条晕染互相叠会糊成一整坨，反而看不出哪条路是什么色。
 * `LAYER_HEAT` 的注释从第一版起就写着「四级视图 heat 恒 0」，此前 `heatOf()` 少了这一条判断，
 * 属于代码与注释不一致，这里补齐。
 */
function heatOf(seg) {
    if (!isIndex.value)
        return 0;
    if (isFlow.value)
        return 0;
    if (!isCameraCovered(seg.segment_id))
        return 0;
    const rec = segById.value.get(seg.segment_id);
    if (!rec || !ciAvailable(rec))
        return 0;
    const v = Math.min(CI_MAX, Math.max(0, rec.ci));
    return Math.round((0.1 + (v / CI_MAX) * 0.5) * 100) / 100;
}
/**
 * 当前站点包有没有方向字段（Issue IKP5BD 第④条）。
 * 旧 21 段对照包（Z21）没有 `segmentDirections`：整包**一支箭头都不画**，
 * 图例写明「本包无方向字段」——不能像现在这样给每个点画灰 `?`，让人误读成"未标定数据"。
 */
const directionsAvailable = computed(() => {
    void packTick.value; // 切站后包变了，方向字段有无也跟着变，必须重算
    return Object.keys(activePack().segmentDirections ?? {}).length > 0;
});
/** 真正可画 = 包里方向字段在该 + 顶栏「设置」里开关开着 */
const directionDrawable = computed(() => directionsAvailable.value && directionsVisible.value);
/**
 * 双向段的箭头横向偏移（米）。取 14 m 而不是几米：默认视野（fitBounds 后约 16~17 档，
 * 1.4~1.6 m/px）下约 9 px，两支反向箭头分列折线两侧还能看出"一来一回"；
 * 再小就会被箭头图标自身盖住。
 */
const DIR_BIDIR_OFFSET_M = 14;
/** 双向段两支箭头的沿线位置（中点前后）：不用 0.45/0.55——短段（本包中位约 53 m）会叠在一起 */
const DIR_BIDIR_FRACTIONS = [0.35, 0.65];
/** 沿走向法向偏移一个点（米 → 度；近似平面，只用于展示落点） */
function offsetByNormal(point, bearing, offsetM) {
    const rad = (bearing * Math.PI) / 180;
    // 走向单位向量（东, 北）；右法向 = (cos b, -sin b)
    const east = Math.cos(rad) * offsetM;
    const north = -Math.sin(rad) * offsetM;
    const lat = point[1] + north / 111_320;
    const lon = point[0] + east / (111_320 * Math.cos((point[1] * Math.PI) / 180));
    return [lon, lat];
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
function directionGeoJson() {
    if (!directionDrawable.value)
        return { type: 'FeatureCollection', features: [] };
    const features = [];
    for (const seg of net.value) {
        const kind = directionKindOf(directionOf(seg.segment_id));
        const bearing = bearingDeg(seg.coords);
        if (kind === 'bidirectional') {
            DIR_BIDIR_FRACTIONS.forEach((fraction, i) => {
                const base = pointAtFraction(seg.coords, fraction);
                // 第一支偏左、顺走向；第二支偏右、逆走向
                const offset = i === 0 ? DIR_BIDIR_OFFSET_M : -DIR_BIDIR_OFFSET_M;
                const [lon, lat] = offsetByNormal(base, bearing, offset);
                const rotate = i === 0 ? bearing : (bearing + 180) % 360;
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
                });
            });
            continue;
        }
        const rotate = kind === 'backward' ? (bearing + 180) % 360 : bearing;
        const [lon, lat] = pointAtFraction(seg.coords, 0.5);
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
        });
    }
    return { type: 'FeatureCollection', features };
}
/** 用 canvas 生成方向图标（ImageData，不需要字体 glyph 资源） */
function directionIconImage(kind) {
    const size = 64;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    if (!ctx)
        return new ImageData(size, size);
    // Issue IKP5BD：双向段不再用 `↕` 字形 —— 由 `directionGeoJson()` 生成两支单箭头
    // （各自带 rotate、分列折线两侧），图标本身保持单箭头形状，只是染双向语义色。
    const glyph = kind === 'unknown' ? '?' : '↑';
    ctx.clearRect(0, 0, size, size);
    ctx.font = 'bold 44px "Segoe UI Symbol", "Noto Sans Symbols", system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    // 白色描边画两遍：压在任意路网色上都能看清
    ctx.lineWidth = 8;
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.96)';
    ctx.strokeText(glyph, size / 2, size / 2 + 2);
    ctx.fillStyle = DIR_COLORS[kind];
    ctx.fillText(glyph, size / 2, size / 2 + 2);
    return ctx.getImageData(0, 0, size, size);
}
/** 把四个方向图标注册进当前样式（换样式后要重新注册 —— setStyle 会清空 image 资源） */
function addDirectionImages(map) {
    for (const kind of ['forward', 'backward', 'bidirectional', 'unknown']) {
        const name = DIR_ICON_PREFIX + kind;
        if (!map.hasImage(name))
            map.addImage(name, directionIconImage(kind));
    }
}
/** 方向标记图层（symbol + icon，无 text/glyphs 依赖；随地图旋转对齐） */
function directionLayerSpec() {
    return {
        id: LAYER_DIRECTION,
        type: 'symbol',
        source: DIR_SRC,
        layout: {
            'icon-image': ['get', 'icon'],
            // 双向段用 `icon_scale` 收小（0.8×）；单/双向共用同一套随缩放尺寸。
            // ⚠️ `zoom` **只能**出现在顶层 `interpolate` / `step` 的输入位（MapLibre 硬性限制）：
            //    原来写成 `['*', ['interpolate', …zoom…], ['get','icon_scale']]` 会让整个
            //    `setStyle(mergedStyle(…))` 直接抛
            //    「layers.hubflow-direction-marker.layout.icon-size: "zoom" expression may only be used
            //      as input to a top-level "step" or "interpolate" expression」——
            //    底图就永远停在「底图加载中…」（改前 main 上就有，与 IKPFR4 无关）。
            //    正确写法：`zoom` 当顶层 interpolate 输入，`icon_scale` 放进**各 stop 的输出值**。
            'icon-size': [
                'interpolate',
                ['linear'],
                ['zoom'],
                12,
                ['*', 0.5, ['get', 'icon_scale']],
                15,
                ['*', 0.85, ['get', 'icon_scale']],
            ],
            'icon-rotate': ['get', 'rotate'],
            'icon-rotation-alignment': 'map',
            'icon-allow-overlap': true,
            'icon-ignore-placement': true,
            // 关掉 / 包无方向字段时不画：换样式重建图层也要带上，否则一开底图就又把箭头画回来
            visibility: directionDrawable.value ? 'visible' : 'none',
        },
    };
}
/** 把方向标记显隐贴到图层（开关切换时调用；图层还没建就跳过，建图层时会再带一次） */
function applyDirectionVisibility(map) {
    if (!map.getLayer(LAYER_DIRECTION))
        return;
    map.setLayoutProperty(LAYER_DIRECTION, 'visibility', directionDrawable.value ? 'visible' : 'none');
}
/**
 * 建图 / 换样式后把方向源与图标备齐（源/图标存在则跳过）。
 * ⚠️ 图层本身**不在这里 `addLayer`**：绘制顺序统一由 `ownLayerSpecs()` 一份决定，
 * 两条路各排一套顺序的话，方向标一下子在路线上、一下子在路线下。
 */
function ensureDirectionSource(map) {
    addDirectionImages(map);
    if (!map.getSource(DIR_SRC)) {
        map.addSource(DIR_SRC, { type: 'geojson', data: directionGeoJson() });
    }
}
/**
 * 当前是否处于「凸显路线」：开关开 **且** 真有路线可凸显。
 * 没路线时不能把整张图压灰——那会让人读成"全网数据不可用"。
 */
const routeEmphasisOn = computed(() => routeEmphasisEnabled.value && hasRoutes.value);
/** 任一语义组里的段号（判断"这段是否在路线上"用；同段重复只算一次） */
function routeSegmentIds() {
    const out = new Set();
    for (const g of props.routes ?? [])
        for (const id of g.segments)
            out.add(id);
    return out;
}
/** 站点包坐标是 WGS-84，**直接喂给 MapLibre** —— 不做任何坐标转换 */
function routeGeoJson() {
    const routed = routeSegmentIds();
    const emphasize = routeEmphasisOn.value;
    return {
        type: 'FeatureCollection',
        features: net.value.map((seg) => {
            // 非路线段统一压灰（Issue IKP5CK）：不再按 level 上色，改用中性浅灰细线。
            // heat 一并归零——否则指数视图还会在灰线外圈漫出一层等级色，等于没压。
            const emphasisGray = emphasize && !routed.has(seg.segment_id);
            return {
                type: 'Feature',
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
                geometry: { type: 'LineString', coordinates: seg.coords },
            };
        }),
    };
}
/**
 * 线宽 = 主/支两档 × 「没摄像头覆盖」系数。
 * 收细 + 压透明度是「只摄像头段上色」策略下"这段没监控"的画法（业主 2026-10-15），
 * 与"有摄像头但当前没数据"的灰区分开（后者用正常线宽）。
 */
const widthExpr = (main, ramp) => [
    '*',
    ['case', ['==', ['get', 'kind'], 'main'], main, ramp],
    ['case', ['==', ['get', 'covered'], false], 0.55, 1],
];
/**
 * 路网三层的**基准线宽**（主 / 支两档，单位屏幕像素，取值对应 `fitZoom` 档）。
 * 缩远时由 `applyLineScale()` 按档位整体折算 —— 这里只放基准值，别再散落魔法数字。
 */
const LINE_W_CASING = [11, 9];
const LINE_W_HEAT = [26, 22];
const LINE_W_LINE = [5.5, 4.5];
/**
 * 默认视野（取景后）的 zoom。`fitZoom` 之后才知道，所以先给 14 兜底，
 * 由 `fitStationInstant()` / `fitOverviewInstant()` 在 `fitBounds()` 之后写回。
 *
 * 为什么不能写死：Z 站演示范围 500 m、GZ 站 1000 m，两站默认档本来就不同。
 */
let fitZoom = 14;
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
function lineScaleOf(zoom) {
    const d = fitZoom - zoom; // 比默认视野缩远了多少档（负数 = 放大）
    if (d <= 0)
        return 1;
    return Math.max(0.15, Math.pow(2, -d));
}
/**
 * 热力晕染的**额外淡出**系数：线宽已经按 `2^-d` 收过一遍，但热力是同色半透明宽带，
 * 相邻段叠在一起仍会加深（0.1–0.6 的 opacity 叠两三层就到 0.8+）。
 * 所以热力在「又缩」之外再按 `2^(-0.8d)` 单独压一道 —— 缩 2 档约 0.33、3 档触底 0.25。
 *
 * ⚠️ 下限 0.25，**不能归零**：业主明确「这个颜色不能完全去掉」，热力是拥挤指数视图的
 * 主要读图线索，远景也要能看出哪里红。
 */
function heatFadeOf(zoom) {
    const d = fitZoom - zoom;
    if (d <= 0)
        return 1;
    return Math.max(0.25, Math.pow(2, -d * 0.8));
}
/** 上一次贴上去的线宽系数（避免每帧重建表达式；`force` 用于换样式后强制重贴） */
let lastLineScale = -1;
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
function applyLineScale(map, force = false) {
    if (!map.getLayer(LAYER_CASING))
        return;
    const zoom = map.getZoom();
    const s = lineScaleOf(zoom);
    if (!force && Math.abs(s - lastLineScale) < 0.004)
        return;
    lastLineScale = s;
    map.setPaintProperty(LAYER_CASING, 'line-width', ['case', ['==', ['get', 'emphasis_gray'], true], 3.5 * s,
        widthExpr(LINE_W_CASING[0] * s, LINE_W_CASING[1] * s)]);
    map.setPaintProperty(LAYER_HEAT, 'line-width', widthExpr(LINE_W_HEAT[0] * s, LINE_W_HEAT[1] * s));
    map.setPaintProperty(LAYER_HEAT, 'line-opacity', ['*', ['get', 'heat'], heatFadeOf(zoom)]);
    map.setPaintProperty(LAYER_LINE, 'line-width', ['case', ['==', ['get', 'emphasis_gray'], true], 2 * s,
        widthExpr(LINE_W_LINE[0] * s, LINE_W_LINE[1] * s)]);
}
function selectedFilter() {
    return ['==', ['get', 'segment_id'], props.selectedId ?? ''];
}
function routeFilter() {
    return ['in', ['get', 'segment_id'], ['literal', routeIdsOf('arrival')]];
}
/**
 * 取某一组（或多组）路线要高亮的路段 id —— 去重后作为图层 filter 的 `literal`。
 * 推荐 / 离站各一组；备选按序号拆两色，另见 `routeIdsOfAlternative()`（Issue IKP5CK）。
 */
function routeIdsOf(...kinds) {
    const out = new Set();
    for (const g of props.routes ?? []) {
        if (!kinds.includes(g.kind))
            continue;
        for (const id of g.segments)
            out.add(id);
    }
    return [...out];
}
function routeFilterOf(...kinds) {
    return ['in', ['get', 'segment_id'], ['literal', routeIdsOf(...kinds)]];
}
/** 备选分组序号（兼容旧调用：没有 `index` 时按备选 1） */
function altIndex(g) {
    return typeof g.index === 'number' && g.index >= 1 ? g.index : 1;
}
/**
 * 取「备选 N」的段号：N=1 取 index 1，N=2 取 index ≥2（第 3 条及以后一并按备选 2 画，
 * 不新增第五种颜色；页面只承诺"一主二备"三色可辨）。
 */
function routeIdsOfAlternative(n) {
    const out = new Set();
    for (const g of props.routes ?? []) {
        if (g.kind !== 'alternative')
            continue;
        const idx = altIndex(g);
        if (n === 1 ? idx !== 1 : idx < 2)
            continue;
        for (const id of g.segments)
            out.add(id);
    }
    return [...out];
}
function altFilter(n) {
    return ['in', ['get', 'segment_id'], ['literal', routeIdsOfAlternative(n)]];
}
/** 任一组路线存在时才在图上画图例（否则不占地方） */
const hasRoutes = computed(() => (props.routes ?? []).some((g) => g.segments.length > 0));
/** 图例里的「备选 N 条」：按实际分组计数，不足 2 条时如实少画（不凑等价路线） */
const altRouteCount = computed(() => (props.routes ?? []).filter((g) => g.kind === 'alternative' && g.segments.length > 0).length);
/**
 * 本组件自有的图层（按绘制顺序：底衬 → 热力 → 色线 → 路线 → 选中）。
 * 同一份规格用在两处：建图时按顺序 `addLayer`；底图样式合进来时作为 `layers` 尾部一起挂载
 * —— **两处只有一份定义**，不会出现"底图在/不在时路网长得不一样"。
 */
function lineLayerSpecs() {
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
    ];
}
// ---- IKPFVN · 全国视角：站点 pin / 兜底轮廓 / 三态图层开关 / 镜头取景 ----
/**
 * 镜头状态（由 `shared/mapMotion.ts` 的状态机驱动）。本组件**只读它**来决定图层显隐：
 *   `national`                 → 站点 pin 层可见，路网 / 路线层隐藏
 *   `leaving` / `panning` / `entering`（过渡中）→ 与全国同（pin 可见、路网隐藏）
 *   `station`                  → 反过来
 */
const motionPhase = ref(props.mapMode === 'station' ? 'station' : 'national');
/** 全国站表（生成物 `stations.generated.ts`，不在这里拼）—— pin / 浮层卡片 / 镜头目标共用 */
const stations = computed(() => stationEntries());
function stationGeoJson() {
    const features = stations.value.map((s, index) => ({
        type: 'Feature',
        // 数字 id：`setFeatureState` / `removeFeatureState` 靠它定位一个站（不能用站键字符串）
        id: index,
        properties: {
            key: s.key,
            name: s.name,
            segments: s.segment_count ?? 0,
            label_icon: STATION_LABEL_ICON_PREFIX + s.key,
        },
        geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
    }));
    return { type: 'FeatureCollection', features };
}
/**
 * 站名标签图片（canvas 生成，不依赖字体 glyphs）。
 *
 * 为什么不用 `text-field`：`text-field` 必须配底图样式的 `glyphs`，而**本地兜底样式没有 glyphs**
 * —— 底图拉不到时那一层会直接报 `use of "text-field" requires a style "glyphs" property`，
 * 控制台脏了、标签也画不出来。canvas 图片在任何样式下都能画（方向标记也是这么干的）。
 */
function stationLabelImage(name) {
    const pad = 6;
    const height = 23;
    const font = '600 14px "PingFang SC", "Microsoft YaHei", system-ui, sans-serif';
    const canvas = document.createElement('canvas');
    const probe = canvas.getContext('2d');
    if (!probe)
        return new ImageData(1, 1);
    probe.font = font;
    const width = Math.ceil(probe.measureText(name).width) + pad * 2;
    // 2× 后备缓冲：高分屏上文字不糊
    canvas.width = Math.ceil(width * 2);
    canvas.height = height * 2;
    const ctx = canvas.getContext('2d');
    if (!ctx)
        return new ImageData(1, 1);
    ctx.scale(2, 2);
    ctx.fillStyle = 'rgba(255, 255, 255, 0.95)';
    ctx.strokeStyle = 'rgba(71, 85, 105, 0.55)';
    ctx.lineWidth = 1;
    if (typeof ctx.roundRect === 'function') {
        ctx.beginPath();
        ctx.roundRect(0.5, 0.5, width - 1, height - 1, 6);
        ctx.fill();
        ctx.stroke();
    }
    else {
        ctx.fillRect(0.5, 0.5, width - 1, height - 1);
        ctx.strokeRect(0.5, 0.5, width - 1, height - 1);
    }
    ctx.font = font;
    ctx.fillStyle = '#1F2937';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(name, width / 2, height / 2 + 1);
    return ctx.getImageData(0, 0, canvas.width, canvas.height);
}
/** 注册站名标签图标（换样式后要重新注册，`setStyle` 会清空 image 资源） */
function addStationImages(map) {
    for (const s of stations.value) {
        const name = STATION_LABEL_ICON_PREFIX + s.key;
        if (!map.hasImage(name))
            map.addImage(name, stationLabelImage(s.name));
    }
}
/** 站点三个图层：命中区（透明大圆）→ 实心圆（选中环就画在它身上）→ 站名 */
function stationLayerSpecs() {
    const selected = ['boolean', ['feature-state', 'selected'], false];
    const hovered = ['boolean', ['feature-state', 'hover'], false];
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
    ];
}
/** 上一帧高亮 / 选中的站（清 feature-state 时要先知道是谁） */
let selectedStationKey = null;
let hoverStationKey = null;
/** 被悬停的站（DOM 浮牌用）。两个条站相距不到 10 px（全国缩放），光有 pin 分不清谁是谁 */
const hoverStation = ref(null);
/** 把“当前站”的选中环贴到图层上（站区视角才高亮：全国里没有“当前站”这回事） */
function syncStationSelection(map) {
    if (!map.getSource(STATION_SRC))
        return;
    const next = props.mapMode === 'station' ? activePackKey() : null;
    if (selectedStationKey !== null) {
        const prev = stations.value.findIndex((s) => s.key === selectedStationKey);
        if (prev >= 0)
            map.removeFeatureState({ source: STATION_SRC, id: prev }, 'selected');
    }
    selectedStationKey = next;
    if (next === null)
        return;
    const index = stations.value.findIndex((s) => s.key === next);
    if (index >= 0)
        map.setFeatureState({ source: STATION_SRC, id: index }, { selected: true });
}
/** 悬停高亮（只改 feature-state，不重建图层、不重建数据） */
function syncStationHover(map, key) {
    if (hoverStationKey === key)
        return;
    const prev = stations.value.findIndex((s) => s.key === hoverStationKey);
    if (prev >= 0)
        map.removeFeatureState({ source: STATION_SRC, id: prev }, 'hover');
    hoverStationKey = key;
    hoverStation.value = stations.value.find((s) => s.key === key) ?? null;
    const index = stations.value.findIndex((s) => s.key === key);
    if (index >= 0)
        map.setFeatureState({ source: STATION_SRC, id: index }, { hover: true });
}
/** 悬停站点浮牌落点 = pin 正上方（与摄像头 / 落客点浮牌同一套夹边逻辑） */
const stationChipStyle = computed(() => {
    const map = mapRef.value;
    const s = hoverStation.value;
    void camTick.value; // 地图动过就重算
    if (!map || !s)
        return {};
    const pt = map.project([s.lon, s.lat]);
    const w = containerRef.value?.clientWidth ?? 0;
    const width = ST_CHIP_W;
    const rawLeft = Math.max(6, pt.x - width / 2);
    const left = w > width + 12 ? Math.min(rawLeft, w - width - 6) : 6;
    return { left: `${left}px`, top: `${Math.max(6, pt.y - 76)}px` };
});
/** 站点源 + 站名图标备齐（图层顺序同上，统一交给 `ownLayerSpecs()`） */
function ensureStationSource(map) {
    addStationImages(map);
    if (!map.getSource(STATION_SRC)) {
        map.addSource(STATION_SRC, { type: 'geojson', data: stationGeoJson() });
    }
}
// ---- 底图兜底轮廓（Natural Earth 1:110m 简化，公有领域）----
/**
 * 兜底轮廓数据。只在**真的用得上**的时候拉一次（底图不可用时），懒加载 + 模块内缓存：
 * 4.3 KB 的文件没必要每次都请求，也不该在底图正常时白占带宽。
 */
const outlineData = shallowRef(null);
let outlineLoading = null;
function loadOutline() {
    if (outlineData.value)
        return Promise.resolve(outlineData.value);
    if (outlineLoading)
        return outlineLoading;
    outlineLoading = (async () => {
        try {
            const data = JSON.parse(chinaOutlineText);
            if (!data || data.type !== 'FeatureCollection')
                return null;
            outlineData.value = data;
            return data;
        }
        catch {
            // 兜底图形的兜底：解析失败就只画站点 pin（依然不白屏）
            return null;
        }
    })();
    return outlineLoading;
}
function outlineSource() {
    return { type: 'geojson', data: outlineData.value ?? EMPTY_FC };
}
/** 淡填充 + 细描边：它只是“这里有块陆地”的提示，不能抢路网 / pin 的视线 */
function outlineLayerSpecs() {
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
    ];
}
function ownLayerSpecs() {
    const own = [...outlineLayerSpecs(), ...lineLayerSpecs()];
    // 方向标记插在路线图层之前（路网 → 方向标 → 路线 → 选中）
    const at = own.findIndex((layer) => layer.id === LAYER_ROUTE_ALT1_HALO);
    own.splice(at < 0 ? own.length : at, 0, directionLayerSpec());
    // 站点 pin 永远在最上层（切站入口不能被路网盖住）
    own.push(...stationLayerSpecs());
    return own;
}
function setLayerVisible(map, id, visible) {
    if (!map.getLayer(id))
        return;
    const next = visible ? 'visible' : 'none';
    if (map.getLayoutProperty(id, 'visibility') === next)
        return;
    map.setLayoutProperty(id, 'visibility', next);
}
/**
 * **三态图层开关的唯一一处**（全国 / 过渡中 / 站区）：
 *
 * | 图层族                    | national | leaving·panning·entering | station |
 * |---------------------------|----------|--------------------------|---------|
 * | 路网 / 热力 / 选中 / 路线 |  隐藏    |          隐藏            |  可见   |
 * | 方向标记                  |  隐藏    |          隐藏            | 按开关  |
 * | 站点 pin（命中/圆/文字）  |  可见    |          可见            |  隐藏   |
 * | 兜底轮廓                  | 底图≠ok时可见 | 同左                 |  隐藏   |
 *
 * 为什么过渡中也藏路网：那时父级已经把上一站的 `routes` 清空了，但**几何还是上一站的**
 * ——“地图缩小时还看得见旧站路网”正是 IKPFVN D4 要禁的东西。
 */
function applyModeLayers(map) {
    const atStation = motionPhase.value === 'station';
    for (const spec of lineLayerSpecs())
        setLayerVisible(map, spec.id, atStation);
    setLayerVisible(map, LAYER_DIRECTION, atStation && directionDrawable.value);
    setLayerVisible(map, LAYER_STATION_HIT, !atStation);
    setLayerVisible(map, LAYER_STATION_DOT, !atStation);
    setLayerVisible(map, LAYER_STATION_LABEL, !atStation);
    const outline = basemap.value !== 'ok' && !atStation;
    setLayerVisible(map, LAYER_OUTLINE_FILL, outline);
    setLayerVisible(map, LAYER_OUTLINE_LINE, outline);
    syncStationSelection(map);
    if (outline)
        void loadOutline().then((data) => {
            if (!data || disposed)
                return;
            const src = mapRef.value?.getSource(OUTLINE_SRC);
            if (src)
                void src.setData(data);
        });
}
/** 把全部自有图层挂上（建图 / 刚换完样式时调一次；顺序只有 `ownLayerSpecs()` 一份） */
function addOwnLayers(map) {
    if (!map.getSource(OUTLINE_SRC))
        map.addSource(OUTLINE_SRC, outlineSource());
    if (!map.getSource(SRC))
        map.addSource(SRC, { type: 'geojson', data: routeGeoJson() });
    ensureDirectionSource(map);
    ensureStationSource(map);
    for (const spec of ownLayerSpecs()) {
        if (!map.getLayer(spec.id))
            map.addLayer(spec);
    }
    applyModeLayers(map);
}
// ---- 镜头取景（IKPFVN C 节；动效参数与状态机全在 `shared/mapMotion.ts`）----
function containerViewport(map) {
    const c = map.getContainer();
    return { width: c.clientWidth, height: c.clientHeight };
}
/**
 * 站区取景留白：把左右栏宽度也算进去（IKPFVN C3）。
 * 栏在容器**外面**（中栏就是地图容器），所以不去重复扣，只在 `stationPadding` 里作对称余量；
 * 这里量的是 **当前真实宽度** —— 栏是滑入的，写死 296 / 396 会在拖过栏宽的页面上取偏。
 */
function sideColumnsWidth() {
    const self = containerRef.value;
    const splitter = self?.closest('.el-splitter');
    if (!self || !splitter)
        return 0;
    let total = 0;
    for (const child of Array.from(splitter.children)) {
        if (!child.classList.contains('el-splitter-panel'))
            continue;
        if (child.contains(self))
            continue; // 自己所在的中栏不算
        total += child.clientWidth;
    }
    return total;
}
function stationPaddingNow(map) {
    const view = containerViewport(map);
    return stationPadding({
        ...view,
        columnsWidth: sideColumnsWidth(),
        // 图例在宽屏是左下角浮层，会给站区最外侧的起点段让位；窄屏图例已收进折叠浮层 → 0
        legendWidth: props.legend && legendOpen.value && view.width > 900 ? 440 : 0,
    });
}
/** 先量准容器尺寸再取景：左右栏刚滑入时宽高还是旧的，直接 fitBounds 会偏（IKPFVN E1） */
async function resizeMap(map) {
    map.resize();
    await new Promise((resolve) => {
        window.requestAnimationFrame(() => resolve());
    });
    map.resize();
}
function fitStationInstant(map, key) {
    const cam = stationCamera(key);
    if (!cam)
        return;
    map.fitBounds([cam.bounds.sw, cam.bounds.ne], {
        padding: stationPaddingNow(map),
        maxZoom: cam.maxZoom,
        duration: 0,
    });
    // 记下这一站的默认档：线宽 / 热力 / 图钉的缩放基准都相对它算（两站范围不同，不能写死）
    fitZoom = map.getZoom();
    applyLineScale(map, true);
}
function fitOverviewInstant(map) {
    const cam = overviewCamera();
    map.fitBounds([cam.bounds.sw, cam.bounds.ne], {
        padding: overviewPadding(containerViewport(map)),
        duration: 0,
    });
    // 容器偏矮时 `fitBounds` 会把中国算到 2 档（大陆变成中间一小块）——按判定的下界抬到 3 档
    clampOverviewZoom(map);
    fitZoom = map.getZoom();
    applyLineScale(map, true);
}
/**
 * 镜头同步（唯一入口）：按 `mapMode` 决定落到全国还是落进某个站。
 * `animated=false` 只用于“不能有动画”的场合（起手建图、换完底图样式后）。
 */
async function syncCamera(animated) {
    const map = mapRef.value;
    if (!map || !ready.value || disposed)
        return;
    if (props.mapMode === 'station') {
        const key = activePackKey();
        if (!animated || !stationCamera(key)) {
            fitStationInstant(map, key);
            motionPhase.value = 'station';
            applyModeLayers(map);
            // 站包几何为空时也没别的去处：如实按“已到站”通知父级，别让数据永远挂在“过渡中”
            emit('arrived');
            return;
        }
        motionPhase.value = 'leaving';
        applyModeLayers(map);
        const result = await flyToStation(map, key, {
            padding: () => stationPaddingNow(map),
            onPhase: (phase) => {
                motionPhase.value = phase;
                const live = mapRef.value;
                if (live)
                    applyModeLayers(live);
            },
            beforeFit: () => resizeMap(map),
        });
        if (result.cancelled)
            return;
        motionPhase.value = 'station';
        applyModeLayers(map);
        emit('arrived');
        return;
    }
    if (!animated) {
        fitOverviewInstant(map);
        motionPhase.value = 'national';
        applyModeLayers(map);
        return;
    }
    motionPhase.value = 'leaving';
    applyModeLayers(map);
    const result = await flyToOverview(map, {
        padding: () => overviewPadding(containerViewport(map)),
        onPhase: (phase) => {
            motionPhase.value = phase;
            const live = mapRef.value;
            if (live)
                applyModeLayers(live);
        },
        beforeFit: () => resizeMap(map),
    });
    if (result.cancelled)
        return;
    motionPhase.value = 'national';
    applyModeLayers(map);
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
let cameraPending = false;
let cameraNeedsResize = false;
function scheduleCameraSync(resizeFirst = false) {
    if (resizeFirst)
        cameraNeedsResize = true;
    if (cameraPending)
        return;
    cameraPending = true;
    void nextTick().then(async () => {
        cameraPending = false;
        const map = mapRef.value;
        if (!map || !ready.value || disposed) {
            cameraNeedsResize = false;
            return;
        }
        const needResize = cameraNeedsResize;
        cameraNeedsResize = false;
        if (needResize)
            await resizeMap(map);
        await syncCamera(true);
    });
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
let resizeObserver = null;
let resizeTimer = 0;
let lastFitSize = { width: 0, height: 0 };
function watchContainerSize(map) {
    const el = containerRef.value;
    if (!el || typeof ResizeObserver === 'undefined')
        return;
    resizeObserver?.disconnect();
    resizeObserver = new ResizeObserver(() => {
        // ① 飞行途中（leaving / panning / entering）不插手
        if (motionPhase.value !== 'national' && motionPhase.value !== 'station')
            return;
        window.clearTimeout(resizeTimer);
        resizeTimer = window.setTimeout(() => {
            const live = mapRef.value;
            if (!live || disposed || !ready.value)
                return;
            const size = containerViewport(live);
            // ② 尺寸没变就不动（过渡期间的中间态回调全部走到这里被挡掉）
            if (size.width === lastFitSize.width && size.height === lastFitSize.height)
                return;
            lastFitSize = { width: size.width, height: size.height };
            void live.resize();
            // ③ 无动画：取景是"补算"，不是一次新的转场
            void syncCamera(false);
        }, 140);
    });
    resizeObserver.observe(el);
    lastFitSize = containerViewport(map);
}
// ---- 摄像头布点 ----
/** 摄像头标记（重绘 / 卸载时移除） */
let camMarkers = [];
/** 被悬停的摄像头（浮牌钉在图钉上方，与路段浮牌区分） */
const pin = ref(null);
/** 窄屏专用：跨断点复位（Issue IKP3EV），与桌面全局开关互不干扰。必须在 legendOpen 之前声明。 */
const narrowLegendOpen = ref(!(typeof window !== 'undefined' && window.matchMedia('(max-width: 1180px)').matches));
/**
 * 图例是否展开。两套口径合并（Issue IKP3EV + 业主 2026-10-19 追加）：
 *   · **窄屏（≤1180）**：单列后地图整行变宽，整幅图例会盖住路网主体 → 默认收起（地图优先），
 *     跨断点自动复位（见下方 `legendMq`）；
 *   · **桌面（>1180）**：原本常开、没法收；业主反馈图例压住路网后，改为读全局
 *     `legendVisible`（顶栏「设置」与地图工具条的「图例」键共用同一个状态，落 localStorage）。
 *
 * 统一到本组件的一个 computed，是为了让 `legendWidth`（取景留白要用它）只认一个来源。
 */
const legendOpen = computed(() => {
    if (props.mapMode !== 'station')
        return legendVisible.value;
    if (typeof window !== 'undefined' && window.matchMedia('(max-width: 1180px)').matches) {
        return narrowLegendOpen.value;
    }
    return legendVisible.value;
});
function toggleLegend() {
    if (typeof window !== 'undefined' && window.matchMedia('(max-width: 1180px)').matches) {
        narrowLegendOpen.value = !narrowLegendOpen.value;
        return;
    }
    setLegendVisible(!legendVisible.value);
}
/**
 * 跨断点复位图例开合（Issue IKP3EV 独立审查整改）：窄屏 ref 只在 setup 求值一次，
 * 桌面加载后再把窗口缩到 ≤1180，图例仍保持展开、会盖住地图（需刷新才复位）。
 * 监听 1180 断点：跨入窄屏默认收起（地图优先），跨回桌面交还全局开关。
 */
const legendMq = typeof window !== 'undefined' ? window.matchMedia('(max-width: 1180px)') : null;
function onLegendMqChange(e) {
    narrowLegendOpen.value = !e.matches;
}
onMounted(() => legendMq?.addEventListener('change', onLegendMqChange));
onUnmounted(() => legendMq?.removeEventListener('change', onLegendMqChange));
/**
 * 摄像头布点（Issue IKLX5Y）：位置取站点包 `channels[].lon/lat`（落在该段折线上的示意点，
 * **不是路测点位**），点击跳到感知层对应通道。
 * ⚠️ 2026-10-18 口径（IKNBT2）：图钉只是**源台账布点**（初始映射），不代表一期摄像头总数——
 * 一期 **N 段 = N 摄像头 = N 视频（演示，mock 复用）**；源台账无布点的段也有演示摄像头与复用视频
 * （见大屏右栏「关联摄像头」卡），不要把"没图钉"读成"没摄像头/没视频"。
 * 实心 = 源台账有**样本视频源**（演示，非本站现场）、空心 = 源台账无独立视频源（画面为演示复用）——
 * "有样本视频"**不得**被读成"数据可用/真实接入"（IKMDKY 口径）。
 */
/**
 * 摄像头图钉随缩放收缩（业主 2026-10-20 口径「缩小地图后还是挤在一起」的真凶）。
 *
 * 为什么必须单独处理：`addCameraPins()` 用 `new Marker({ element })` 造的是 **DOM 元素**，
 * 屏幕像素恒定、**天然不随 zoom 缩**——61 段几乎每段挂一个 20 px 圆，缩远后路网只剩几十像素，
 * 图钉却还是 20 px，当然糊成一团。方向箭头是 symbol 图层（`icon-size` 可调），图钉不是。
 *
 * 两层 DOM 的原因：MapLibre 会往它自己创建的那个元素上写 `transform: translate(...)`，
 * 如果把缩放写在同一个元素上就会**覆盖掉定位**、图钉跑位。所以外层 `.cam-pin-wrap` 交给
 * Marker 定位，内层 `.cam-pin` 只承接缩放/透明度。
 */
function camPinScaleOf(zoom) {
    const d = fitZoom - zoom;
    if (d <= 0)
        return 1;
    return Math.min(1, Math.max(0.28, Math.pow(2, -d * 0.36)));
}
/** 比默认视野缩远 1 档开始淡、1.6 档彻底淡出（完全透明时放开指针事件，不挡地图操作） */
function camPinOpacityOf(zoom) {
    const d = fitZoom - zoom;
    if (d <= 0)
        return 1;
    if (d >= 1.6)
        return 0;
    return Math.max(0, 1 - (d - 1) / 0.6);
}
/** 上一次贴上去的图钉缩放（去抖，别每帧写 61 个元素的 style） */
let lastCamPinScale = -1;
/**
 * 把图钉缩放 / 透明度贴到**内层**元素上（`move` 事件里逐帧调，`force` 用于换样式 / 重建图钉后）。
 * 注意找的是 `.cam-pin-wrap` 的子元素：外层是 MapLibre 的定位壳，不能碰。
 */
function applyCameraPinScale(map, force = false) {
    const zoom = map.getZoom();
    const s = camPinScaleOf(zoom);
    if (!force && Math.abs(s - lastCamPinScale) < 0.004)
        return;
    lastCamPinScale = s;
    const op = camPinOpacityOf(zoom);
    for (const m of camMarkers) {
        const wrap = m.getElement();
        const inner = wrap.firstElementChild;
        if (!inner)
            continue;
        inner.style.transform = `scale(${s})`;
        inner.style.opacity = String(op);
        inner.style.pointerEvents = op <= 0.01 ? 'none' : 'auto';
    }
}
function addCameraPins(map) {
    for (const p of pins.value) {
        // 外层交给 Marker 定位，内层承接缩放（见 camPinScaleOf 上方说明）
        const wrap = document.createElement('div');
        wrap.className = 'cam-pin-wrap';
        const el = document.createElement('div');
        el.className = p.hasVideo ? 'cam-pin' : 'cam-pin empty';
        el.textContent = p.cid.replace('C-', '');
        el.title = `${p.cid} ${p.name} · ${p.segment_id} · 源台账图钉：${p.hasVideo ? '有样本视频源（演示，非本站现场）' : '无独立视频源（演示复用见右栏路段卡）'} · 点击进感知层`;
        el.addEventListener('mouseenter', () => {
            pin.value = p;
        });
        el.addEventListener('mouseleave', () => {
            pin.value = null;
        });
        el.addEventListener('click', () => {
            window.location.href = perceptionHref(p.source);
        });
        wrap.appendChild(el);
        camMarkers.push(new Marker({ element: wrap }).setLngLat([p.lon, p.lat]).addTo(map));
    }
    // 建完立刻按当前档贴一次，否则缩远状态下重建图钉会先以 20 px 闪一下
    lastCamPinScale = -1;
    applyCameraPinScale(map, true);
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
let landmarkMarkers = [];
/** 被悬停的落客点 / 场区（浮牌钉在标记上方，与摄像头浮牌是两套） */
const landmarkPin = ref(null);
function landmarkTitle(p) {
    return `${p.name} · 所属路段 ${p.segment_id || '未标定'}（最近折线推定） · ${p.id} · 演示点`;
}
function addLandmarkPins(map) {
    for (const p of landmarkPins()) {
        const el = document.createElement('div');
        el.className = `lm-pin ${p.kind}`;
        el.textContent = p.kind === 'dropoff' ? '落' : '场';
        el.title = `${landmarkTitle(p)} · 点击选中该路段`;
        el.addEventListener('mouseenter', () => {
            landmarkPin.value = p;
        });
        el.addEventListener('mouseleave', () => {
            landmarkPin.value = null;
        });
        // 图上点不到路段时，标记本身就是入口：点它选中推定路段
        el.addEventListener('click', (event) => {
            event.stopPropagation();
            if (p.segment_id)
                emit('select', p.segment_id);
        });
        landmarkMarkers.push(new Marker({ element: el }).setLngLat([p.lon, p.lat]).addTo(map));
    }
}
// ---- 路线起点 / 终点标注（业主 2026-10-21：「大道最外侧路段 = 起点，停车场落客点 = 终点」）----
/**
 * 起 / 终两个 Marker：与摄像头 / 落客点图钉同族（DOM + 悬停 title），
 * 但用**圆底 + 起/终 字**在视觉上置顶，避免与「落」「场」混淆。
 * 只认父组件传进来的展示坐标（父组件按站点包折线 / 落客点算），本组件不做任何路线计算。
 */
let routeEndpointMarkers = [];
function updateRouteEndpointMarkers(map) {
    for (const marker of routeEndpointMarkers)
        marker.remove();
    routeEndpointMarkers = [];
    for (const p of [props.routeStart, props.routeEnd]) {
        if (!p)
            continue;
        const el = document.createElement('div');
        el.className = `rt-pin ${p.kind}`;
        el.textContent = p.kind === 'start' ? '起' : '终';
        el.title = `${p.label} · ${p.segment_id} · ${p.name}${p.note ? ` · ${p.note}` : ''}`;
        el.addEventListener('click', (event) => {
            event.stopPropagation();
            if (p.segment_id)
                emit('select', p.segment_id);
        });
        routeEndpointMarkers.push(new Marker({ element: el, anchor: 'bottom' }).setLngLat([p.lon, p.lat]).addTo(map));
    }
}
/** 落客点 / 场区浮牌落点 = 标记正上方（与摄像头浮牌同一套夹边逻辑，宽度不同） */
const landmarkChipStyle = computed(() => {
    const map = mapRef.value;
    const p = landmarkPin.value;
    void camTick.value;
    if (!map || !p)
        return {};
    const pt = map.project([p.lon, p.lat]);
    const w = containerRef.value?.clientWidth ?? 0;
    const half = LM_CHIP_W / 2;
    const rawLeft = Math.max(6, pt.x - half);
    const left = w > LM_CHIP_W + 12 ? Math.min(rawLeft, w - LM_CHIP_W - 6) : 6;
    return { left: `${left}px`, top: `${Math.max(6, pt.y - 66)}px` };
});
// ---- 车辆动点（自绘视图搬来：`transform` 过渡 = 平滑移动） ----
const VEH_LABEL = {
    D1: '送客车辆',
    D2: '接客车辆',
    D3: '往返车辆(出租车 / 网约车)',
};
// 图例**由 DRIVER_COLORS 生成**，不手写行——否则新增司机类型时地图画了、图例却漏
const VEH_LEGEND = Object.keys(DRIVER_COLORS).map((t) => ({
    t,
    color: DRIVER_COLORS[t],
    label: VEH_LABEL[t],
}));
const vehMarkers = new Map();
function syncVehicles(map) {
    if (!map || !ready.value)
        return;
    const alive = new Set();
    for (const v of props.vehicles ?? []) {
        alive.add(v.vehicle_id);
        const existing = vehMarkers.get(v.vehicle_id);
        if (existing) {
            existing.marker.setLngLat([v.lon, v.lat]);
            existing.el.title = `${v.vehicle_id} · ${v.state} · ${v.segment_id}${v.is_demo_bound ? ' · 演示绑定车' : ''}`;
            continue;
        }
        const el = document.createElement('div');
        el.className = 'veh-dot';
        el.style.background = DRIVER_COLORS[v.driver_type];
        el.title = `${v.vehicle_id} · ${v.state} · ${v.segment_id}${v.is_demo_bound ? ' · 演示绑定车' : ''}`;
        // 首帧不要过渡：否则新车会从左上角滑进来
        el.style.transition = 'none';
        requestAnimationFrame(() => {
            el.style.transition = 'transform 1.9s linear';
        });
        const marker = new Marker({ element: el }).setLngLat([v.lon, v.lat]).addTo(map);
        vehMarkers.set(v.vehicle_id, { marker, el });
    }
    for (const [id, item] of vehMarkers) {
        if (alive.has(id))
            continue;
        item.marker.remove();
        vehMarkers.delete(id);
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
 * 把 OpenFreeMap 的样式与**本组件自己的图层**合成一份再挂载。
 *
 * 为什么不用 `map.setStyle(STYLE_URL)` 直接换：那会把路网图层一起冲掉，
 * 换完还得"再挂一遍"，中间那段时间图上什么都没有 —— 正是本单要避免的状态。
 * 合成后再切，路网在整份样式里，从一开始就在。
 */
function mergedStyle(remote) {
    return {
        ...remote,
        sources: {
            ...(remote.sources ?? {}),
            // 兜底轮廓 / 站点 pin / 路网 / 方向标 —— 四份 source 都必须带上，否则 setStyle 之后
            // 图层在、数据源没了，地图会报错且 pin 直接消失。
            [OUTLINE_SRC]: outlineSource(),
            [SRC]: { type: 'geojson', data: routeGeoJson() },
            [DIR_SRC]: { type: 'geojson', data: directionGeoJson() },
            [STATION_SRC]: { type: 'geojson', data: stationGeoJson() },
        },
        // 自有图层的绘制顺序只有 `ownLayerSpecs()` 一份
        layers: [...(remote.layers ?? []), ...ownLayerSpecs()],
    };
}
/** 把底图那一层**整层撤掉**：样式换回"本地兜底 + 本组件图层"，路网一行不动 */
function dropBasemap(map) {
    window.clearTimeout(retryTimer);
    if (!remoteApplied)
        return; // 本来就是"只有路网"，不必再换一次样式
    remoteApplied = false;
    map.once('styledata', () => {
        if (disposed)
            return;
        // 换样式后不能“动画回位”（会突然飞一下）：停住时才按当前视角 Instant 重新取景
        refitAfterStyleSwap(map);
    });
    map.setStyle(mergedStyle(FALLBACK_STYLE), { diff: false });
}
/**
 * 换完底图样式后补一次取景（IKPFVN）。
 *
 * ⚠️ 只在**停住**的时候补（`national` / `station`）。`setStyle` 本身会保留相机，所以
 * 飞行途中（leaving / panning / entering）**根本不需要**补：那里补一次 `syncCamera(false)`
 * 等于把正在跑的镜头按下去、把 `motionPhase` 强置成 `station` 并提前 `emit('arrived')`
 * —— 表现就是"路网在半空显形、页面数据提前放行"（PR !77 独立审查发现的漏口）。
 */
function refitAfterStyleSwap(map) {
    applyViewState(map);
    if (motionPhase.value !== 'national' && motionPhase.value !== 'station')
        return;
    void syncCamera(false);
}
/** 失败后按 2s / 6s / 12s 退避自动重试（最多三次）；开关关掉或组件卸载即停 */
function scheduleRetry(map) {
    if (retryStep >= RETRY_DELAYS_MS.length)
        return;
    const delay = RETRY_DELAYS_MS[retryStep];
    retryStep++;
    retryTimer = window.setTimeout(() => {
        if (!disposed)
            void applyBasemap(map, { retry: true });
    }, delay);
}
/** 手动「重试」（角标上的按钮）：计数清零，立刻再拉一次 */
function retryBasemap() {
    const map = mapRef.value;
    if (!map || !ready.value)
        return;
    retryStep = 0;
    void applyBasemap(map, { retry: true });
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
async function applyBasemap(map, opts = {}) {
    window.clearTimeout(retryTimer);
    if (!basemapEnabled.value) {
        // 关开关：在途的那一次也掐掉，别让"不发任何底图请求"只在冷启动成立
        inflightCtrl?.abort();
        inflightCtrl = null;
        basemap.value = 'off';
        basemapRetrying.value = false;
        dropBasemap(map);
        return;
    }
    if (opts.retry)
        basemapRetrying.value = true;
    else
        basemap.value = 'loading';
    const run = ++basemapRun;
    const stale = () => disposed || run !== basemapRun || !basemapEnabled.value;
    const ctrl = new AbortController();
    inflightCtrl = ctrl;
    const timer = window.setTimeout(() => ctrl.abort(), BASEMAP_TIMEOUT_MS);
    try {
        const res = await fetch(toBasemapUrl(STYLE_URL), { signal: ctrl.signal });
        if (!res.ok)
            throw new Error(`样式 http ${res.status}`);
        const remote = (await res.json());
        if (remote?.version !== 8 || !remote.sources || !Array.isArray(remote.layers)) {
            throw new Error('样式形状不对');
        }
        if (stale())
            return;
        // 换样式后重新取景 + 重贴选中态；车辆与摄像头是 DOM Marker，不受影响。
        // ⚠️ 监听要先挂再 `setStyle` —— 反过来万一 styledata 已同步派发就漏掉了。
        map.once('styledata', () => {
            if (disposed)
                return;
            refitAfterStyleSwap(map);
        });
        map.setStyle(mergedStyle(remote), { diff: false });
        remoteApplied = true;
        if (!(await waitForBasemapTiles(map, remote, stale))) {
            throw new Error('瓦片拉取超时');
        }
        if (stale())
            return;
        basemap.value = 'ok';
        basemapRetrying.value = false;
        retryStep = 0;
    }
    catch (e) {
        if (stale())
            return;
        basemap.value = 'failed';
        basemapRetrying.value = false;
        // 样式已经挂上去过（②之后才失败）→ 退回去，别留着"只有底色"的半张底图
        if (remoteApplied)
            dropBasemap(map);
        basemapMsg.value = e instanceof Error ? e.message : '拉取失败';
        if (e instanceof Error && e.name === 'AbortError')
            basemapMsg.value = '拉取超时';
        scheduleRetry(map);
    }
    finally {
        window.clearTimeout(timer);
        if (inflightCtrl === ctrl)
            inflightCtrl = null;
    }
}
/** 这份样式里"要从公网拉瓦片"的源（geojson 是我们自己的路网，不算） */
function tileSourceIds(remote) {
    return Object.entries(remote.sources ?? {})
        .filter(([, spec]) => spec?.type !== 'geojson')
        .map(([id]) => id);
}
/**
 * 等底图瓦片真的就绪（轮询 `isSourceLoaded`）。到点还没就绪 → `false`。
 * 轮询而不是挂 `sourcedata` 监听：事件只在"有变化"时来，黑洞代理下可能**一个都不来**。
 */
async function waitForBasemapTiles(map, remote, stale) {
    const ids = tileSourceIds(remote);
    if (ids.length === 0)
        return true;
    const deadline = Date.now() + BASEMAP_TILES_TIMEOUT_MS;
    while (Date.now() < deadline) {
        if (stale())
            return false;
        const present = new Set(Object.keys(map.getStyle()?.sources ?? {}));
        if (ids.every((id) => present.has(id) && map.isSourceLoaded(id)))
            return true;
        await new Promise((r) => window.setTimeout(r, 300));
    }
    return false;
}
/** 数据/选中/路线/视角变化后，把视图状态贴回图层（换样式之后也要重贴一次） */
function applyViewState(map) {
    // 换样式会清空 image 资源：方向图标与站名标签都要补回去
    addDirectionImages(map);
    addStationImages(map);
    applyDirectionVisibility(map);
    syncStationSelection(map);
    const dirSrc = map.getSource(DIR_SRC);
    if (dirSrc)
        void dirSrc.setData(directionGeoJson());
    const stSrc = map.getSource(STATION_SRC);
    if (stSrc)
        void stSrc.setData(stationGeoJson());
    const src = map.getSource(SRC);
    if (src)
        void src.setData(routeGeoJson());
    if (map.getLayer(LAYER_SELECTED))
        map.setFilter(LAYER_SELECTED, selectedFilter());
    if (map.getLayer(LAYER_ROUTE))
        map.setFilter(LAYER_ROUTE, routeFilter());
    if (map.getLayer(LAYER_ROUTE_HALO))
        map.setFilter(LAYER_ROUTE_HALO, routeFilter());
    if (map.getLayer(LAYER_ROUTE_ALT1))
        map.setFilter(LAYER_ROUTE_ALT1, altFilter(1));
    if (map.getLayer(LAYER_ROUTE_ALT1_HALO))
        map.setFilter(LAYER_ROUTE_ALT1_HALO, altFilter(1));
    if (map.getLayer(LAYER_ROUTE_ALT2))
        map.setFilter(LAYER_ROUTE_ALT2, altFilter(2));
    if (map.getLayer(LAYER_ROUTE_ALT2_HALO))
        map.setFilter(LAYER_ROUTE_ALT2_HALO, altFilter(2));
    // 三态图层显隐也重贴一次：换样式会把 `visibility` 回到默认的 visible
    applyModeLayers(map);
    // 换样式后 paint 全部回到 `lineLayerSpecs()` 的基准值 —— 必须强制重贴，
    // 否则「底图加载完那一刻线宽突然变粗」（业主会看到路网突然胖一圈）
    applyLineScale(map, true);
    applyCameraPinScale(map, true);
}
// ---- 交互：点击选中 / 悬停即切换选中 + 浮牌跟随 ----
const mouse = ref(null);
/** 地图移动/缩放后要重算浮牌落点（`map.project()` 不是响应式的） */
const camTick = ref(0);
function hoveredSegmentId(map, point) {
    if (!map.getLayer(LAYER_LINE))
        return null;
    const hit = map.queryRenderedFeatures(point, { layers: [LAYER_LINE] });
    const id = hit?.[0]?.properties?.segment_id;
    return typeof id === 'string' && id ? id : null;
}
/**
 * 鼠标下的站点（全国视角的切站入口）。
 * 命中用那个**透明大圆**图层（半径 15 px），而不是可见小圆：可见圆只有 12~18 px 直径，
 * 鼠标要正中才能点中；热区要求 ≥ 24 px。
 */
function stationKeyAt(map, point) {
    if (props.mapMode === 'station')
        return null;
    if (!map.getLayer(LAYER_STATION_HIT))
        return null;
    const hit = map.queryRenderedFeatures(point, { layers: [LAYER_STATION_HIT] });
    const key = hit?.[0]?.properties?.key;
    return typeof key === 'string' && key ? key : null;
}
function onMapMouseMove(e) {
    const map = mapRef.value;
    if (!map)
        return;
    mouse.value = { x: e.point.x, y: e.point.y };
    // 全国视角：只有站点 pin 是可选对象（路网图层已隐藏，路口悬停不该再报路段）
    const stationKey = stationKeyAt(map, e.point);
    syncStationHover(map, stationKey);
    if (props.mapMode !== 'station') {
        map.getCanvas().style.cursor = stationKey ? 'pointer' : '';
        return;
    }
    const id = hoveredSegmentId(map, e.point);
    map.getCanvas().style.cursor = id ? 'pointer' : '';
    // 悬停即切换选中（业主 2026-10-14：不要"靠点击才切换"）——浮牌据此吸附在当前路段上
    if (id && id !== props.selectedId)
        emit('select', id);
}
function onMapMouseOut() {
    mouse.value = null;
    const map = mapRef.value;
    if (map)
        syncStationHover(map, null);
}
function onMapClick(e) {
    const map = mapRef.value;
    if (!map)
        return;
    // 全国视角：点 pin = 切站（父级走 `switchStation`，本组件不自己换包）
    const stationKey = stationKeyAt(map, e.point);
    if (stationKey) {
        emit('switch-station', stationKey);
        return;
    }
    const id = hoveredSegmentId(map, e.point);
    if (id)
        emit('select', id);
}
/** 跟随鼠标的信息浮牌落点 = 选中路段折线上离鼠标最近的采样点（沿线走，鼠标离开线也不消失） */
const chipStyle = computed(() => {
    const map = mapRef.value;
    const m = mouse.value;
    void camTick.value; // 地图动过就重算
    if (!map || !m || !props.selectedId || !props.hoverChip)
        return {};
    const seg = net.value.find((s) => s.segment_id === props.selectedId);
    if (!seg)
        return {};
    let best = map.project(seg.coords[0]);
    let bestD = Number.POSITIVE_INFINITY;
    for (const c of seg.coords) {
        const p = map.project(c);
        const d = (p.x - m.x) ** 2 + (p.y - m.y) ** 2;
        if (d < bestD) {
            bestD = d;
            best = p;
        }
    }
    const w = containerRef.value?.clientWidth ?? 0;
    const flipX = best.x + CHIP_W + 18 > w;
    const flipY = best.y - CHIP_H - 14 < 0;
    return {
        left: `${flipX ? best.x - CHIP_W - 14 : best.x + 14}px`,
        top: `${flipY ? best.y + 16 : best.y - CHIP_H - 12}px`,
    };
});
/** 摄像头浮牌落点 = 图钉正上方（钉在图钉上，不跟鼠标） */
const camChipStyle = computed(() => {
    const map = mapRef.value;
    const p = pin.value;
    void camTick.value;
    if (!map || !p)
        return {};
    const pt = map.project([p.lon, p.lat]);
    // Issue IKP3EV：旧逻辑只夹左边界，窄地图（≤560 时画布可能只有 340px 宽）上图钉靠右时
    // 192px 的浮牌右缘会被推出画布。这里左右都夹：先保左不越界，再保右不越界。
    const w = containerRef.value?.clientWidth ?? 0;
    const half = CAM_CHIP_W / 2;
    const rawLeft = Math.max(6, pt.x - half);
    const left = w > CAM_CHIP_W + 12 ? Math.min(rawLeft, w - CAM_CHIP_W - 6) : 6;
    return { left: `${left}px`, top: `${Math.max(6, pt.y - 62)}px` };
});
// ---- 建图 ----
let disposed = false;
/**
 * 探一下 dev/preview 上那条**底图同源直通**路由在不在（见 `shared/basemap.ts` 头部）。
 *
 * 为什么要探而不是"配个 env 开关了事"：生产构建里根本没有这条路由，写死同源前缀会让线上
 * 底图 100% 404；而"按 mode 分支"又管不到 `vite preview` 看 dist 的场景。探一下最省事：
 * 拿到 JSON 就是挂了，拿到 HTML（SPA 回退的 index.html）或超时就当没挂，回落直连上游。
 *
 * 探测失败**不影响建图**：它就是一次 1.5 s 上限的请求，拿不到就照旧走公网。
 */
async function detectBasemapProxy() {
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => ctrl.abort(), BASEMAP_PROBE_TIMEOUT_MS);
    try {
        const res = await fetch(BASEMAP_PROXY_PROBE, { signal: ctrl.signal, cache: 'no-store' });
        if (!res.ok)
            return;
        const body = (await res.json());
        setBasemapProxyDetected(body?.ok === true);
    }
    catch {
        setBasemapProxyDetected(false);
    }
    finally {
        window.clearTimeout(timer);
    }
}
function initMap() {
    if (!containerRef.value)
        return;
    const overview = overviewCamera();
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
    });
    mapRef.value = map;
    // 验收钩子（**只在 dev 生效**；生产构建里 `import.meta.env.DEV === false`，这块会被摇掉）：
    // 本单的完成判定里有两条只能读地图实例 —— `map.getZoom()`（全国 3–6 / 站区 ≥14）与
    // `map.querySourceFeatures` 里的路线段号（切 Z 全 `SZ-`、切 GZ 全 `GZ-`）。
    // 它与容器上的 `data-map-mode` / `data-station` / `data-motion-phase` 是同一套验收设施。
    if (import.meta.env.DEV) {
        ;
        window.__hubflowMap = map;
    }
    map.addControl(new NavigationControl({ visualizePitch: true }), 'top-right');
    // 比例尺放右下（左下角留给图例）
    map.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-right');
    map.on('load', () => {
        addOwnLayers(map);
        addCameraPins(map);
        addLandmarkPins(map);
        updateRouteEndpointMarkers(map);
        // 起手取景按**当前视角**：全国（默认）→ 中国范围；深链 `?station=` → 直接站区（无动画）
        motionPhase.value = props.mapMode === 'station' ? 'station' : 'national';
        ready.value = true;
        void syncCamera(false);
        // 首帧的容器宽度可能还没定型（左右栏正在收起 / 挂载时布局未稳定）——
        // 尺寸一变就补一次取景，见 `watchContainerSize()`。
        watchContainerSize(map);
        // 车辆要在 ready 之后再同步（`syncVehicles` 以 ready 为前置）
        syncVehicles(map);
        map.on('move', () => {
            camTick.value++;
            // 线宽 / 热力透明度按当前档位逐帧贴回（业主 2026-10-20：缩远不能糊成一片）
            applyLineScale(map);
            applyCameraPinScale(map);
        });
        map.on('mousemove', onMapMouseMove);
        map.on('mouseout', onMapMouseOut);
        map.on('click', onMapClick);
        // 底图**随后**再拉（设置里关着就一个请求都不发）：成功就把底图合进来，失败就保持"只有路网"
        void applyBasemap(map);
    });
    // 单块瓦片失败是常态噪声，不打扰用户；这里只留一个不遮挡地图的状态角标
}
// ---- 响应式：数据 / 模式 / 选中 / 路线 / 车辆 ----
watch(() => [props.segments, props.mode, props.colorMode], () => {
    const map = mapRef.value;
    if (!map || !ready.value)
        return;
    applyViewState(map);
});
watch(() => props.selectedId, () => {
    const map = mapRef.value;
    if (!map || !ready.value || !map.getLayer(LAYER_SELECTED))
        return;
    map.setFilter(LAYER_SELECTED, selectedFilter());
});
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
function applyPackChange() {
    const map = mapRef.value;
    net.value = DEMO_NETWORK.segments;
    // 悬停浮牌指向的是上一站的图钉/点位，切站即清空（业主裁定：站内状态一律重置）
    pin.value = null;
    landmarkPin.value = null;
    if (!map || !ready.value || disposed)
        return;
    camMarkers.forEach((m) => m.remove());
    camMarkers = [];
    addCameraPins(map);
    landmarkMarkers.forEach((m) => m.remove());
    landmarkMarkers = [];
    addLandmarkPins(map);
    // 方向 / 路网 / 站点 pin 重贴数据与显隐；**取景交给镜头状态机**（IKPFVN C）
    applyViewState(map);
    scheduleCameraSync();
}
watch(packTick, applyPackChange);
/**
 * 路线高亮按**内容**监听，不按数组引用：父组件传的是 computed 产物，快照刷新时会重建引用，
 * 按引用监听的写法会在每次刷新时白跑一遍 `setFilter`。
 */
const routeKey = computed(() => (props.routes ?? [])
    .map((g) => `${g.kind}:${g.index ?? 0}:${g.segments.join(',')}`)
    .join('|'));
// 路线变化要连**数据**一起重算：非路线段压灰依赖 feature 属性（emphasis_gray），
// 只换 filter 不够（Issue IKP5CK）。applyViewState 会重贴源数据 + 全部 filter。
watch(routeKey, () => {
    const map = mapRef.value;
    if (!map || !ready.value)
        return;
    applyViewState(map);
});
/** 起点 / 终点标注随推荐路线（或手动选起点）变化：重建两个 Marker 即可，不动其他图层。
 *  用**稳定字符串键**而不是数组/对象：数组每次求值都是新引用，会让 watch 在每次渲染都触发，
 *  反复重建 Marker 会把地图拖进渲染循环（表现为整张图空白）。 */
watch(() => [
    props.routeStart?.segment_id ?? '',
    props.routeStart?.lon ?? '',
    props.routeStart?.lat ?? '',
    props.routeEnd?.segment_id ?? '',
    props.routeEnd?.lon ?? '',
    props.routeEnd?.lat ?? '',
].join('|'), () => {
    const map = mapRef.value;
    if (!map || !ready.value)
        return;
    updateRouteEndpointMarkers(map);
});
/** 顶栏 / 工具条两个开关：方向标记显隐、凸显路线（压灰） */
watch(directionsVisible, () => {
    const map = mapRef.value;
    if (!map || !ready.value)
        return;
    applyViewState(map);
});
watch(routeEmphasisEnabled, () => {
    const map = mapRef.value;
    if (!map || !ready.value)
        return;
    applyViewState(map);
});
/** 顶栏「设置」里的底图开关：开 → 拉底图；关 → 撤掉底图层（路网一行不动） */
watch(basemapEnabled, () => {
    const map = mapRef.value;
    if (!map || !ready.value)
        return;
    retryStep = 0;
    void applyBasemap(map);
});
/**
 * 底图状态一变（ok / failed / off）就重算图层显隐：兜底轮廓的可见性挂在它上面
 * （`basemap !== 'ok'` 才画轮廓，见 `applyModeLayers()`）。
 */
watch(basemap, () => {
    const map = mapRef.value;
    if (!map || !ready.value)
        return;
    applyModeLayers(map);
});
/**
 * 视角切换（IKPFVN E1/E2）：`national` ⇄ `station`。
 *
 * 顺序不能反：**先 `map.resize()` 再 `fitBounds`**。左右栏是滑入 / 收起的，
 * resize 之前量到的是旧宽高，直接取景会偏（图例留白、中栏宽度都按旧值算）。
 */
watch(() => props.mapMode, () => {
    // 先让左右栏把位置定下来（`resizeFirst`），再动镜头；两者都合并到同一轮，
    // 避免与 `packTick` 同时变化时“取消一次再重开一次”（见 `scheduleCameraSync`）。
    scheduleCameraSync(true);
});
watch(() => props.vehicles, () => {
    syncVehicles(mapRef.value);
});
onMounted(async () => {
    // 容器始终在 DOM 里，nextTick 只为确保布局尺寸已就绪（尺寸为 0 时地图会渲染成空白）
    await nextTick();
    // 先探代理再建图：`applyBasemap` 的第一次样式请求也要走同源直通（探测本身有 1.5 s 上限）
    await detectBasemapProxy();
    initMap();
});
onUnmounted(() => {
    disposed = true;
    offPackTick();
    window.clearTimeout(retryTimer);
    window.clearTimeout(resizeTimer);
    resizeObserver?.disconnect();
    resizeObserver = null;
    inflightCtrl?.abort();
    // 镜头动画也要停：组件没了还跑着 `easeTo` 会往一个已销毁的渲染器里写
    const map = mapRef.value;
    if (map)
        cancelMotion(map);
    camMarkers.forEach((m) => m.remove());
    camMarkers = [];
    landmarkMarkers.forEach((m) => m.remove());
    landmarkMarkers = [];
    vehMarkers.forEach((v) => v.marker.remove());
    vehMarkers.clear();
    mapRef.value?.remove();
    mapRef.value = null;
    ready.value = false;
});
const __VLS_defaults = {
    vehicles: () => [],
    routes: () => [],
    routeStart: null,
    routeEnd: null,
    mode: 'level',
    colorMode: 'congestion',
    ts: '',
    hoverChip: '',
    legend: true,
    mapMode: 'national',
};
void __VLS_defaults;
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
void __VLS_ctx, __VLS_components, __VLS_intrinsics, __VLS_directives;
// @ts-ignore
__VLS_withDotValue(stations, {});
// @ts-ignore
__VLS_withDotValue(basemap, {});
// @ts-ignore
__VLS_withDotValue(basemapRetrying, {});
// @ts-ignore
__VLS_withDotValue(osmActive, {});
// @ts-ignore
__VLS_withDotValue(hoverStation, {});
// @ts-ignore
__VLS_withDotValue(pin, {});
// @ts-ignore
__VLS_withDotValue(landmarkPin, {});
// @ts-ignore
__VLS_withDotValue(mouse, {});
// @ts-ignore
__VLS_withDotValue(directionsAvailable, {});
// @ts-ignore
__VLS_withDotValue(directionsVisible, {});
// @ts-ignore
__VLS_withDotValue(isFlow, {});
// @ts-ignore
__VLS_withDotValue(hasRoutes, {});
// @ts-ignore
__VLS_withDotValue(routeEmphasisOn, {});
// @ts-ignore
__VLS_withDotValue(pins, {});
// @ts-ignore
__VLS_withDotValue(isIndex, {});
void {};
/** @type {__VLS_StyleScopedClasses['basemap-retry']} */ ;
/** @type {__VLS_StyleScopedClasses['basemap-retry']} */ ;
/** @type {__VLS_StyleScopedClasses['attribution']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-dock']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-toggle']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-dock']} */ ;
/** @type {__VLS_StyleScopedClasses['open']} */ ;
/** @type {__VLS_StyleScopedClasses['legend']} */ ;
/** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
/** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
/** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
/** @type {__VLS_StyleScopedClasses['dir-mark']} */ ;
/** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
/** @type {__VLS_StyleScopedClasses['dir-mark']} */ ;
/** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
/** @type {__VLS_StyleScopedClasses['dir-mark']} */ ;
/** @type {__VLS_StyleScopedClasses['both']} */ ;
/** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
/** @type {__VLS_StyleScopedClasses['lg-note']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['lg-line']} */ ;
/** @type {__VLS_StyleScopedClasses['lg-line']} */ ;
/** @type {__VLS_StyleScopedClasses['lg-line']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['cam-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['cam-pin']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['lm-pin']} */ ;
/** @type {__VLS_StyleScopedClasses['lm-pin']} */ ;
/** @type {__VLS_StyleScopedClasses['rt-pin']} */ ;
/** @type {__VLS_StyleScopedClasses['rt-pin']} */ ;
/** @type {__VLS_StyleScopedClasses['rt-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['start']} */ ;
/** @type {__VLS_StyleScopedClasses['rt-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['end']} */ ;
/** @type {__VLS_StyleScopedClasses['basemap-note']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-dock']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-toggle']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-dock']} */ ;
/** @type {__VLS_StyleScopedClasses['legend']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-dock']} */ ;
/** @type {__VLS_StyleScopedClasses['open']} */ ;
/** @type {__VLS_StyleScopedClasses['legend']} */ ;
/** @type {__VLS_StyleScopedClasses['lg-note']} */ ;
/** @type {__VLS_StyleScopedClasses['watermark']} */ ;
/** @type {__VLS_StyleScopedClasses['basemap-note']} */ ;
/** @type {__VLS_StyleScopedClasses['attribution']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-dock']} */ ;
/** @type {__VLS_StyleScopedClasses['lg-title']} */ ;
/** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
/** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
/** @type {__VLS_StyleScopedClasses['ts']} */ ;
/** @type {__VLS_StyleScopedClasses['lg-note']} */ ;
/** @type {__VLS_StyleScopedClasses['hover-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['cam-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['lm-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-dock']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-dock']} */ ;
/** @type {__VLS_StyleScopedClasses['legend']} */ ;
/** @type {__VLS_StyleScopedClasses['lg-title']} */ ;
/** @type {__VLS_StyleScopedClasses['nc-item']} */ ;
/** @type {__VLS_StyleScopedClasses['basemap-note']} */ ;
/** @type {__VLS_StyleScopedClasses['mlmap']} */ ;
/** @type {__VLS_StyleScopedClasses['cam-pin']} */ ;
/** @type {__VLS_StyleScopedClasses['mlmap']} */ ;
/** @type {__VLS_StyleScopedClasses['mode-national']} */ ;
/** @type {__VLS_StyleScopedClasses['lm-pin']} */ ;
/** @type {__VLS_StyleScopedClasses['mlmap']} */ ;
/** @type {__VLS_StyleScopedClasses['mode-national']} */ ;
/** @type {__VLS_StyleScopedClasses['rt-pin']} */ ;
/** @type {__VLS_StyleScopedClasses['mlmap']} */ ;
/** @type {__VLS_StyleScopedClasses['mode-national']} */ ;
/** @type {__VLS_StyleScopedClasses['veh-dot']} */ ;
(__VLS_unwrap(BRAND, {}));
(__VLS_unwrap(BRAND, {}));
(__VLS_unwrap(BRAND, {}));
(__VLS_unwrap(BRAND, {}));
(__VLS_unwrap(BRAND, {}));
(__VLS_unwrap(BRAND, {}));
(__VLS_unwrap(BRAND, {}));
(__VLS_unwrap(BRAND, {}));
(__VLS_unwrap(BRAND, {}));
(__VLS_unwrap(BRAND, {}));
// @ts-ignore
[BRAND, BRAND, BRAND, BRAND, BRAND, BRAND, BRAND, BRAND, BRAND, BRAND,];
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "mlmap" },
    ...{ class: ({ 'mode-national': __VLS_ctx.mapMode === 'national' }) },
    'data-map-mode': (__VLS_ctx.mapMode),
    'data-station': (__VLS_unwrap(currentStationKey, {})),
    'data-motion-phase': (__VLS_unwrap(motionPhase, {})),
});
/** @type {__VLS_StyleScopedClasses['mlmap']} */ ;
/** @type {__VLS_StyleScopedClasses['mode-national']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div)({
    ref: "containerRef",
    ...{ class: "mlmap-canvas" },
});
/** @type {__VLS_StyleScopedClasses['mlmap-canvas']} */ ;
if (__VLS_ctx.mapMode === 'national') {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "nation-card" },
    });
    /** @type {__VLS_StyleScopedClasses['nation-card']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "nc-head" },
    });
    /** @type {__VLS_StyleScopedClasses['nc-head']} */ ;
    (stations.value.length);
    const __VLS_0 = __VLS_tryAsConstant((stations.value));
    for (const [station] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: // @ts-ignore
                (...[$event]) => {
                    void $event;
                    if (!(__VLS_ctx.mapMode === 'national'))
                        throw 0;
                    return (pickStation(station.key));
                    // @ts-ignore
                    [mapMode, mapMode, mapMode, currentStationKey, motionPhase, stations, stations,];
                } },
            key: (station.key),
            type: "button",
            ...{ class: "nc-item" },
            title: (`切换到${station.name}：地图缩远 → 移动到该站 → 放大 → 显示该站路网`),
        });
        /** @type {__VLS_StyleScopedClasses['nc-item']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "nc-name" },
        });
        /** @type {__VLS_StyleScopedClasses['nc-name']} */ ;
        (station.name);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "nc-seg" },
        });
        /** @type {__VLS_StyleScopedClasses['nc-seg']} */ ;
        (station.segment_count ?? '—');
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "nc-demo" },
        });
        /** @type {__VLS_StyleScopedClasses['nc-demo']} */ ;
        // @ts-ignore
        [];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "nc-note" },
    });
    /** @type {__VLS_StyleScopedClasses['nc-note']} */ ;
    if (basemap.value !== 'ok') {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "nc-note" },
        });
        /** @type {__VLS_StyleScopedClasses['nc-note']} */ ;
    }
}
if (basemap.value !== 'ok') {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "basemap-note" },
        ...{ class: ({ 'note-bottom': __VLS_ctx.mapMode === 'national' }) },
    });
    /** @type {__VLS_StyleScopedClasses['basemap-note']} */ ;
    /** @type {__VLS_StyleScopedClasses['note-bottom']} */ ;
    if (basemap.value === 'off') {
    }
    else if (basemap.value === 'loading') {
    }
    else {
        if (__VLS_ctx.mapMode === 'national') {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            (__VLS_unwrap(basemapMsg, {}));
        }
        if (basemapRetrying.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "basemap-retrying" },
            });
            /** @type {__VLS_StyleScopedClasses['basemap-retrying']} */ ;
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (retryBasemap) },
            type: "button",
            ...{ class: "basemap-retry" },
            disabled: (basemapRetrying.value),
        });
        /** @type {__VLS_StyleScopedClasses['basemap-retry']} */ ;
    }
}
if (__VLS_ctx.mapMode === 'station') {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "watermark" },
    });
    /** @type {__VLS_StyleScopedClasses['watermark']} */ ;
    (__VLS_unwrap(sourceLabel, {}));
}
if (osmActive.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "attribution" },
    });
    /** @type {__VLS_StyleScopedClasses['attribution']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
        href: (__VLS_unwrap(OSM_COPYRIGHT_URL, {})),
        target: "_blank",
        rel: "noopener",
    });
    (__VLS_unwrap(OSM_ATTRIBUTION, {}));
}
if (__VLS_ctx.mapMode === 'national' && hoverStation.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "st-chip" },
        ...{ style: (__VLS_unwrap(stationChipStyle, {})) },
    });
    /** @type {__VLS_StyleScopedClasses['st-chip']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    (hoverStation.value.name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "st-chip-sub" },
    });
    /** @type {__VLS_StyleScopedClasses['st-chip-sub']} */ ;
    (hoverStation.value.segment_count ?? '—');
}
if (pin.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cam-chip" },
        ...{ style: (__VLS_unwrap(camChipStyle, {})) },
    });
    /** @type {__VLS_StyleScopedClasses['cam-chip']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    (pin.value.cid);
    (pin.value.name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "cam-chip-sub" },
    });
    /** @type {__VLS_StyleScopedClasses['cam-chip-sub']} */ ;
    (pin.value.segment_id);
    (pin.value.hasVideo ? '有样本视频源（演示，非本站现场）' : '无独立视频源（演示复用见右栏路段卡）');
}
if (landmarkPin.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "lm-chip" },
        ...{ style: (__VLS_unwrap(landmarkChipStyle, {})) },
    });
    /** @type {__VLS_StyleScopedClasses['lm-chip']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    (landmarkPin.value.name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "lm-chip-sub" },
    });
    /** @type {__VLS_StyleScopedClasses['lm-chip-sub']} */ ;
    (__VLS_unwrap(landmarkKindLabel, {})(landmarkPin.value.kind));
    (landmarkPin.value.segment_id || '未标定');
    (landmarkPin.value.id);
}
if (__VLS_ctx.mapMode === 'station' && mouse.value && __VLS_ctx.hoverChip) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "hover-chip" },
        ...{ style: (__VLS_unwrap(chipStyle, {})) },
    });
    /** @type {__VLS_StyleScopedClasses['hover-chip']} */ ;
    (__VLS_ctx.hoverChip);
}
if (__VLS_ctx.legend && __VLS_ctx.mapMode === 'station') {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "legend-dock" },
        ...{ class: ({ open: __VLS_unwrap(legendOpen, {}) }) },
    });
    /** @type {__VLS_StyleScopedClasses['legend-dock']} */ ;
    /** @type {__VLS_StyleScopedClasses['open']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                if (!(__VLS_ctx.legend && __VLS_ctx.mapMode === 'station'))
                    throw 0;
                return (toggleLegend());
                // @ts-ignore
                [mapMode, mapMode, mapMode, mapMode, mapMode, mapMode, basemap, basemap, basemap, basemap, basemapMsg, basemapRetrying, basemapRetrying, sourceLabel, osmActive, OSM_COPYRIGHT_URL, OSM_ATTRIBUTION, hoverStation, hoverStation, hoverStation, stationChipStyle, pin, pin, pin, pin, pin, camChipStyle, landmarkPin, landmarkPin, landmarkPin, landmarkPin, landmarkPin, landmarkChipStyle, landmarkKindLabel, mouse, hoverChip, hoverChip, chipStyle, legend, legendOpen,];
            } },
        type: "button",
        ...{ class: "legend-toggle" },
        'aria-expanded': (__VLS_unwrap(legendOpen, {})),
        title: "图例压住路网时可收起，点一下再展开（状态会记住）",
    });
    /** @type {__VLS_StyleScopedClasses['legend-toggle']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "legend" },
    });
    /** @type {__VLS_StyleScopedClasses['legend']} */ ;
    if (!directionsAvailable.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-title" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-title']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-row" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-note" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-note']} */ ;
    }
    else if (!directionsVisible.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-title" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-title']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-row" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-title" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-title']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-row" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "dir-mark" },
            ...{ style: ({ color: '#1D5FD8' }) },
        });
        /** @type {__VLS_StyleScopedClasses['dir-mark']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "dir-mark both" },
            ...{ style: ({ color: '#6D28D9' }) },
        });
        /** @type {__VLS_StyleScopedClasses['dir-mark']} */ ;
        /** @type {__VLS_StyleScopedClasses['both']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "flip" },
        });
        /** @type {__VLS_StyleScopedClasses['flip']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "dir-mark" },
            ...{ style: ({ color: '#8B8B8B' }) },
        });
        /** @type {__VLS_StyleScopedClasses['dir-mark']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-note" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-note']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
        ...{ class: "lg-sep" },
    });
    /** @type {__VLS_StyleScopedClasses['lg-sep']} */ ;
    if (isFlow.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-title" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-title']} */ ;
        const __VLS_1 = __VLS_tryAsConstant((__VLS_unwrap(FLOW_BANDS, {})));
        for (const [band] of __VLS_vFor(__VLS_nonNull(__VLS_1))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                key: (band.band),
                ...{ class: "lg-row" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                ...{ class: "dot" },
                ...{ style: ({ background: band.color }) },
            });
            /** @type {__VLS_StyleScopedClasses['dot']} */ ;
            (band.band);
            (band.name);
            (__VLS_unwrap(flowRangeLabel, {})(band));
            // @ts-ignore
            [legendOpen, directionsAvailable, directionsVisible, isFlow, FLOW_BANDS, flowRangeLabel,];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-row" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
        const __VLS_2 = LevelBadge;
        // @ts-ignore
        const __VLS_3 = __VLS_asFunctionalComponent1(__VLS_2, new __VLS_2({
            // @ts-ignore
            level: (1), stale: true,
        }));
        const __VLS_4 = __VLS_3({
            level: (1),
            stale: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_3));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-note strong" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-note']} */ ;
        /** @type {__VLS_StyleScopedClasses['strong']} */ ;
        (__VLS_unwrap(FLOW_MODE_LABEL, {}));
        (__VLS_unwrap(FLOW_MODE_NOTE, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-note" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-note']} */ ;
        (__VLS_unwrap(FLOW_COLOR_NOTE, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
            ...{ class: "lg-sep" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-sep']} */ ;
        const __VLS_7 = __VLS_tryAsConstant((__VLS_unwrap(VEH_LEGEND, {})));
        for (const [v] of __VLS_vFor(__VLS_nonNull(__VLS_7))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                key: (v.t),
                ...{ class: "lg-row" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                ...{ class: "dot" },
                ...{ style: ({ background: v.color }) },
            });
            /** @type {__VLS_StyleScopedClasses['dot']} */ ;
            (v.t);
            (v.label);
            // @ts-ignore
            [FLOW_MODE_LABEL, FLOW_MODE_NOTE, FLOW_COLOR_NOTE, VEH_LEGEND,];
        }
        if (hasRoutes.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
                ...{ class: "lg-sep" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-sep']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "lg-row" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                ...{ class: "lg-line recommended" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-line']} */ ;
            /** @type {__VLS_StyleScopedClasses['recommended']} */ ;
            if (__VLS_unwrap(altRouteCount, {}) >= 1) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "lg-row" },
                });
                /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                    ...{ class: "lg-line alt1" },
                });
                /** @type {__VLS_StyleScopedClasses['lg-line']} */ ;
                /** @type {__VLS_StyleScopedClasses['alt1']} */ ;
            }
            if (__VLS_unwrap(altRouteCount, {}) >= 2) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "lg-row" },
                });
                /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                    ...{ class: "lg-line alt2" },
                });
                /** @type {__VLS_StyleScopedClasses['lg-line']} */ ;
                /** @type {__VLS_StyleScopedClasses['alt2']} */ ;
            }
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "lg-row" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                ...{ class: "lg-line departure" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-line']} */ ;
            /** @type {__VLS_StyleScopedClasses['departure']} */ ;
            if (__VLS_ctx.routeStart) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "lg-row" },
                });
                /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "rt-dot start" },
                });
                /** @type {__VLS_StyleScopedClasses['rt-dot']} */ ;
                /** @type {__VLS_StyleScopedClasses['start']} */ ;
                (__VLS_ctx.routeStart.label);
                (__VLS_ctx.routeStart.segment_id);
            }
            if (__VLS_ctx.routeEnd) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "lg-row" },
                });
                /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "rt-dot end" },
                });
                /** @type {__VLS_StyleScopedClasses['rt-dot']} */ ;
                /** @type {__VLS_StyleScopedClasses['end']} */ ;
                (__VLS_ctx.routeEnd.label);
            }
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "lg-note" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-note']} */ ;
            (__VLS_unwrap(altRouteCount, {}));
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "lg-note" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-note']} */ ;
            (routeEmphasisOn.value ? '开 — 非路线段中性灰细线，不按等级上色' : '关 — 满图等级色，路线叠加');
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "lg-note" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-note']} */ ;
        }
        if (pins.value.length > 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
                ...{ class: "lg-sep" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-sep']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "lg-row" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                ...{ class: "dot cam-dot" },
            });
            /** @type {__VLS_StyleScopedClasses['dot']} */ ;
            /** @type {__VLS_StyleScopedClasses['cam-dot']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "lg-row" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                ...{ class: "dot cam-dot empty" },
            });
            /** @type {__VLS_StyleScopedClasses['dot']} */ ;
            /** @type {__VLS_StyleScopedClasses['cam-dot']} */ ;
            /** @type {__VLS_StyleScopedClasses['empty']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "lg-note" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-note']} */ ;
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-row ts" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
        /** @type {__VLS_StyleScopedClasses['ts']} */ ;
        (props.ts || '—');
    }
    else if (isIndex.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-title" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-title']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
            ...{ class: "lg-ramp" },
            ...{ style: ({ background: __VLS_unwrap(ciGradientCss, {})() }) },
        });
        /** @type {__VLS_StyleScopedClasses['lg-ramp']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-scale" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-scale']} */ ;
        const __VLS_8 = __VLS_tryAsConstant((__VLS_unwrap(CI_BANDS, {})));
        for (const [b] of __VLS_vFor(__VLS_nonNull(__VLS_8))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                key: (b),
            });
            (b);
            // @ts-ignore
            [hasRoutes, altRouteCount, altRouteCount, altRouteCount, routeStart, routeStart, routeStart, routeEnd, routeEnd, routeEmphasisOn, pins, isIndex, ciGradientCss, CI_BANDS,];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-note" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-note']} */ ;
        (__VLS_unwrap(CI_BAND_NOTE, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-note strong" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-note']} */ ;
        /** @type {__VLS_StyleScopedClasses['strong']} */ ;
        (__VLS_unwrap(CI_DISCLAIMER, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
            ...{ class: "lg-sep" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-sep']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-row" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
        const __VLS_9 = LevelBadge;
        // @ts-ignore
        const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
            // @ts-ignore
            level: (1), stale: true,
        }));
        const __VLS_11 = __VLS_10({
            level: (1),
            stale: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_10));
        const __VLS_14 = __VLS_tryAsConstant((__VLS_unwrap(VEH_LEGEND, {})));
        for (const [v] of __VLS_vFor(__VLS_nonNull(__VLS_14))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                key: (v.t),
                ...{ class: "lg-row" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                ...{ class: "dot" },
                ...{ style: ({ background: v.color }) },
            });
            /** @type {__VLS_StyleScopedClasses['dot']} */ ;
            (v.t);
            (v.label);
            // @ts-ignore
            [VEH_LEGEND, CI_BAND_NOTE, CI_DISCLAIMER,];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-row ts" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
        /** @type {__VLS_StyleScopedClasses['ts']} */ ;
        (props.ts || '—');
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-title" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-title']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-row" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
        const __VLS_15 = LevelBadge;
        // @ts-ignore
        const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
            // @ts-ignore
            level: (1),
        }));
        const __VLS_17 = __VLS_16({
            level: (1),
        }, ...__VLS_functionalComponentArgsRest(__VLS_16));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-row" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
        const __VLS_20 = LevelBadge;
        // @ts-ignore
        const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
            // @ts-ignore
            level: (2),
        }));
        const __VLS_22 = __VLS_21({
            level: (2),
        }, ...__VLS_functionalComponentArgsRest(__VLS_21));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-row" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
        const __VLS_25 = LevelBadge;
        // @ts-ignore
        const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
            // @ts-ignore
            level: (3),
        }));
        const __VLS_27 = __VLS_26({
            level: (3),
        }, ...__VLS_functionalComponentArgsRest(__VLS_26));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-row" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
        const __VLS_30 = LevelBadge;
        // @ts-ignore
        const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
            // @ts-ignore
            level: (4),
        }));
        const __VLS_32 = __VLS_31({
            level: (4),
        }, ...__VLS_functionalComponentArgsRest(__VLS_31));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "lg-row" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
        const __VLS_35 = LevelBadge;
        // @ts-ignore
        const __VLS_36 = __VLS_asFunctionalComponent1(__VLS_35, new __VLS_35({
            // @ts-ignore
            level: (1), stale: true,
        }));
        const __VLS_37 = __VLS_36({
            level: (1),
            stale: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_36));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
            ...{ class: "lg-sep" },
        });
        /** @type {__VLS_StyleScopedClasses['lg-sep']} */ ;
        const __VLS_40 = __VLS_tryAsConstant((__VLS_unwrap(VEH_LEGEND, {})));
        for (const [v] of __VLS_vFor(__VLS_nonNull(__VLS_40))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                key: (v.t),
                ...{ class: "lg-row" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                ...{ class: "dot" },
                ...{ style: ({ background: v.color }) },
            });
            /** @type {__VLS_StyleScopedClasses['dot']} */ ;
            (v.t);
            (v.label);
            // @ts-ignore
            [VEH_LEGEND,];
        }
        if (hasRoutes.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
                ...{ class: "lg-sep" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-sep']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "lg-row" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                ...{ class: "lg-line recommended" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-line']} */ ;
            /** @type {__VLS_StyleScopedClasses['recommended']} */ ;
            if (__VLS_unwrap(altRouteCount, {}) >= 1) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "lg-row" },
                });
                /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                    ...{ class: "lg-line alt1" },
                });
                /** @type {__VLS_StyleScopedClasses['lg-line']} */ ;
                /** @type {__VLS_StyleScopedClasses['alt1']} */ ;
            }
            if (__VLS_unwrap(altRouteCount, {}) >= 2) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "lg-row" },
                });
                /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                    ...{ class: "lg-line alt2" },
                });
                /** @type {__VLS_StyleScopedClasses['lg-line']} */ ;
                /** @type {__VLS_StyleScopedClasses['alt2']} */ ;
            }
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "lg-row" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                ...{ class: "lg-line departure" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-line']} */ ;
            /** @type {__VLS_StyleScopedClasses['departure']} */ ;
            if (__VLS_ctx.routeStart) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "lg-row" },
                });
                /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "rt-dot start" },
                });
                /** @type {__VLS_StyleScopedClasses['rt-dot']} */ ;
                /** @type {__VLS_StyleScopedClasses['start']} */ ;
                (__VLS_ctx.routeStart.label);
                (__VLS_ctx.routeStart.segment_id);
            }
            if (__VLS_ctx.routeEnd) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "lg-row" },
                });
                /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "rt-dot end" },
                });
                /** @type {__VLS_StyleScopedClasses['rt-dot']} */ ;
                /** @type {__VLS_StyleScopedClasses['end']} */ ;
                (__VLS_ctx.routeEnd.label);
            }
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "lg-note" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-note']} */ ;
            (__VLS_unwrap(altRouteCount, {}));
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "lg-note" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-note']} */ ;
            (routeEmphasisOn.value ? '开 — 非路线段中性灰细线，不按等级上色' : '关 — 满图等级色，路线叠加');
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "lg-note" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-note']} */ ;
        }
        if (pins.value.length > 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
                ...{ class: "lg-sep" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-sep']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "lg-row" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                ...{ class: "dot cam-dot" },
            });
            /** @type {__VLS_StyleScopedClasses['dot']} */ ;
            /** @type {__VLS_StyleScopedClasses['cam-dot']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "lg-row" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-row']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                ...{ class: "dot cam-dot empty" },
            });
            /** @type {__VLS_StyleScopedClasses['dot']} */ ;
            /** @type {__VLS_StyleScopedClasses['cam-dot']} */ ;
            /** @type {__VLS_StyleScopedClasses['empty']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "lg-note" },
            });
            /** @type {__VLS_StyleScopedClasses['lg-note']} */ ;
        }
    }
}
// @ts-ignore
[hasRoutes, altRouteCount, altRouteCount, altRouteCount, routeStart, routeStart, routeStart, routeEnd, routeEnd, routeEmphasisOn, pins,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __defaults: __VLS_defaults,
    __typeProps: {},
});
export default {};
