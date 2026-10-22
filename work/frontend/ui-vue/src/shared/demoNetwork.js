// 路网几何与底图口径 —— **不再自带数据**,一律从当前站点包取(`src/station-packs/`)。
//
// 为什么要改成这样:手册 §8.4 的判定标准是"**换一个站只新增 / 替换配置文件,不改引擎代码**"。
// 本文件此前把站名、几何、路段 id 全部写死,是"一份包";现在它退化成一个**只读门面**:
// 页面与 mock 继续按原来的函数名调用,换站时改的是包,不是这里。
//
// 坐标口径:包里的坐标是 `[lon, lat]` 度(契约形状)。唯一站点包 Z 是 **OSM 真值几何**,
// `source.osm = true` 触发 OSM 署名义务;那种"示意路网 = 占位锚点、不做地理配准"的包
// (A / B / Y)已随 IKM4KP / IKM4XX 删除 —— 将来若再加,仍按"示意几何不得当真值说"办。
//
// ⚠️ 这里**故意不在模块初始化时读包**:模块在 `import` 阶段就被求值,而包键是入口
// (`main.ts` / vite 配置)在挂载前才注入的。所以几何统一走 `ensureInit()` 惰性构建 ——
// 谁先用到谁触发,触发时包键一定已经就位。
//
// ⚠️ IKPFR4：**按包键校验**惰性构建(不再"构建一次管一辈子")。切站不再整页刷新,
//    包键会在同一个 JS 上下文里换掉;如果还沿用第一次构建的那份 segments,画面就会出现
//    「标题写着 GZ、线还是 Z 的 61 段」这种跨站串味。所以 `initedKey` 记住这份几何是
//    按哪个包建的,读到包键不一致就重建成新包的。`resetNetwork()` 是显式的同一件事。
//
// ⚠️ 另一层保障在 `switchStation()`（`shared/stationSwitch.ts`）：切站时**先**调
//    `resetNetwork()` 再渲染首屏,所以正常情况下第一次读就已经是新包了。
import { activePack, activePackKey } from '../station-packs/index.ts';
const state = { note: '', segments: [] };
const SEGMENT_MAP = new Map();
let inited = false;
/** 这份几何是按哪个包键建的(切站校验用;null = 还没建过) */
let initedKey = null;
/** 深拷贝包里的路段:`applyNetworkOverride()` 会**原地**替换这份副本,包里的常量不能被改 */
function cloneSegments(src) {
    return src.map((s) => ({
        segment_id: s.segment_id,
        name: s.name,
        kind: s.kind,
        coords: s.coords.map((c) => [c[0], c[1]]),
    }));
}
function ensureInit() {
    const key = activePackKey();
    if (inited && initedKey === key)
        return;
    inited = true;
    initedKey = key;
    const pack = activePack();
    state.note = pack.source.label;
    // 换一个**新数组**:地图那边用 `shallowRef` 持有这份引用,原地 splice 它察觉不到
    state.segments = cloneSegments(pack.segments);
    SEGMENT_MAP.clear();
    for (const s of state.segments)
        SEGMENT_MAP.set(s.segment_id, s);
}
/**
 * 丢弃当前几何并按**现在生效的包**重建（Issue IKPFR4 原地切站用）。
 *
 * 为什么需要显式一支:虽然 `ensureInit()` 已经会按包键自愈,但切站那一刻地图组件、
 * 面板、路线校验可能各自在不同时序上读几何 —— 先统一重建一次,后面的读取就都是新包了,
 * 不会出现"半秒内新旧两套几何各自被引用"的窗口。
 *
 * ⚠️ 桥接真路网覆盖(`applyNetworkOverride`,见下)在切站后**不再保留**:覆盖是"给当前站
 *    换个几何源"的一次性动作,跨站沿用就等于把甲站的线画到乙站上。两站包都声明
 *    `bridge.enabled=false`,正常情况下这条根本不会触发。
 */
export function resetNetwork() {
    inited = false;
    initedKey = null;
    state.segments = [];
    SEGMENT_MAP.clear();
    NETWORK_SOURCE.twin = false;
    ensureInit();
}
/** 当前包的路网(惰性初始化;`applyNetworkOverride()` 原地改的就是这里的 segments) */
export const DEMO_NETWORK = {
    get note() {
        ensureInit();
        return state.note;
    },
    set note(v) {
        state.note = v;
    },
    get segments() {
        ensureInit();
        return state.segments;
    },
};
export function demoSegment(id) {
    ensureInit();
    return SEGMENT_MAP.get(id);
}
// ---- 真路网覆盖(#61 twin_preview):入口在挂载前拉 /twin-api/network 原地替换,
// 地图 / 两个面板 / mock 的静态读取统一生效;桥接服务不可用则保持站点包路网不变。
// 二站(自建示意路网)关掉桥接(`pack.bridge.enabled === false`),入口不拉,也就不会覆盖。
const NETWORK_SOURCE = { twin: false };
export function applyNetworkOverride(segments, note) {
    if (segments.length === 0)
        return;
    ensureInit();
    state.segments.splice(0, state.segments.length, ...segments);
    state.note = note;
    SEGMENT_MAP.clear();
    for (const s of state.segments)
        SEGMENT_MAP.set(s.segment_id, s);
    NETWORK_SOURCE.twin = true;
}
/** 底图来源短文案(页面水印/页脚口径用):桥接覆盖过就是真路网,否则报包自己的口径 */
export function networkSourceLabel() {
    return NETWORK_SOURCE.twin ? 'OSM 真路网 · SUMO 仿真演示' : activePack().source.label;
}
/** 当前底图是否为真 OSM 路网(桥接覆盖或包自己声明)——OSM 署名义务随之触发 */
export function isOsmNetwork() {
    return NETWORK_SOURCE.twin || activePack().source.osm;
}
/**
 * 路网几何的出处一句话(大屏图下注脚用)。
 * 真 OSM 路网说"几何为真值",示意路网说"示例样例(非实测)"——两者不能混说,
 * 否则真几何会被读成编的、编的会被读成真的。
 */
export function networkGeometryNote() {
    return isOsmNetwork() ? '路网几何为真值（OSM 切片）' : '路网为示例样例(非实测)';
}
/** 底图署名(有则给,如 OSM 的 ODbL);站点包没声明就不署名 */
export function networkAttribution() {
    return NETWORK_SOURCE.twin ? OSM_ATTRIBUTION : activePack().source.attribution;
}
/** OSM 署名(ODbL 要求;条款核实 §2.1:对外展示 OSM 数据须署名并给超链接) */
export const OSM_ATTRIBUTION = '地图数据 © OpenStreetMap 贡献者,依 ODbL 许可';
export const OSM_COPYRIGHT_URL = 'https://www.openstreetmap.org/copyright';
const LAT_M_PER_DEG = 111_320;
function lonMPerDeg(lat) {
    return LAT_M_PER_DEG * Math.cos((lat * Math.PI) / 180);
}
/** 折线累计长度(米,近似) */
export function segmentLengthM(coords) {
    let total = 0;
    for (let i = 1; i < coords.length; i++) {
        const dLon = coords[i][0] - coords[i - 1][0];
        const dLat = coords[i][1] - coords[i - 1][1];
        const mx = dLon * lonMPerDeg(coords[i][1]);
        const my = dLat * LAT_M_PER_DEG;
        total += Math.hypot(mx, my);
    }
    return total;
}
/** 路段内偏移(米)→ 经纬度;offset 超长时取终点 */
export function pointAtOffset(coords, offsetM) {
    let remain = Math.max(0, offsetM);
    for (let i = 1; i < coords.length; i++) {
        const dLon = coords[i][0] - coords[i - 1][0];
        const dLat = coords[i][1] - coords[i - 1][1];
        const mx = dLon * lonMPerDeg(coords[i][1]);
        const my = dLat * LAT_M_PER_DEG;
        const len = Math.hypot(mx, my);
        if (len <= 0)
            continue;
        if (remain <= len) {
            const t = remain / len;
            return [coords[i - 1][0] + dLon * t, coords[i - 1][1] + dLat * t];
        }
        remain -= len;
    }
    return coords[coords.length - 1];
}
