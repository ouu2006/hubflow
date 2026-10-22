// 站点包选择器 —— 浏览器与 vite mock 中间件**共用同一份**(mock 也从这个图里取包)。
//
// 为什么需要"选择器"这一层:站点包讲的是"一份包 = 一个站",而运行时要回答的问题是
// "现在这份前端跑的是哪个站"。答案只能有一个来源,否则会出现"页面画一个站的路网、
// mock 端另一个站的基线"这种对不上的画面。两个入口各注入一次、共用这一个键:
//   · 浏览器:`main.ts` 读构建期的 `import.meta.env.VITE_STATION_PACK`(`.env.z` 里写),
//     在挂载前注入 —— 之后所有组件与模块读到的都是同一份包;
//   · vite mock:`vite.config.ts` 用 `loadEnv` 读同一个变量,经 `mockApiPlugin({ pack })` 注入。
// **多站**：`Z` = 肇庆东站（61 段，站区 500 m）；`GZ` = 广州南站（IKNB9F，独立 OSM 真网 +
// 脚本生成的演示站点包，708 段）。
// **Z21 旧 21 段过渡包已于 IKP5D3 移除**：后端站点登记表 `work/twin/site-ranges.json` 只登记
// Z / GZ 两站，留着 Z21 只会让顶栏能切到一个后端 404 的键 —— 切包即全站 404，已按裁定删包。
// 顶栏「线路图切换器」与监控大屏工具条各有一个入口;取不到就落默认包 Z。
//
// ⚠️ **选择器这一层一个字不删**:手册 §8.4「换一个站只改配置、不改引擎代码」靠它成立 ——
//    将来加站还是"加一个包 + 一行 env",页面与 mock 各自读同一个键这件事不变。
import { STATION_Z } from './stationZ.ts';
import { STATION_GZ } from './stationGZ.ts';
import { STATIONS } from './stations.generated.ts';
export const PACKS = {
    Z: STATION_Z,
    // IKNB9F 多站框架：广州南站（GZ-### 真网几何，站点包由脚本生成）
    GZ: STATION_GZ,
};
export const DEFAULT_PACK_KEY = 'Z';
let injectedKey = null;
/**
 * 包键版本号 + 订阅（Issue IKPFR4）。
 *
 * 为什么需要：包键是**模块级变量**，改它不会惊动 Vue 的响应式系统。切站曾经只能
 * `window.location.reload()` 整页刷新，就是为了让那些"setup 期拍下的快照"（路网几何、
 * 站点名、图钉、路段集合）跟着重算。现在改成原地切站，就必须有一个**显式的变更信号**：
 * 谁持有 setup 期快照，谁 `onPackChange()` 订阅一次，在回调里重取。
 *
 * ⚠️ 这里**不许** `import { ref } from 'vue'`：本文件同时被 `vite.config.ts`（Node 侧 mock
 *    中间件）引用，必须保持**零依赖**。所以只给"版本号 + 订阅"，响应式的 ref 由使用方自建。
 */
let version = 0;
const listeners = new Set();
/** 当前包键版本号：每切一次站 +1（同键重复选不增） */
export function packVersion() {
    return version;
}
/**
 * 订阅包键变更，返回取消订阅函数。
 *
 * 订阅者只负责"重取自己那份快照"，不要在这里做业务判断 —— 包键是否合法已由 `switchPack` 挡住。
 * ⚠️ 回调是**同步**跑的（在 `switchPack` 里），所以只该改响应式 ref / 置脏标记，
 *    真正的重绘交给 Vue 的 watch（微任务里才跑，那时路网几何已按新包重建完）。
 */
export function onPackChange(fn) {
    listeners.add(fn);
    return () => {
        listeners.delete(fn);
    };
}
/** 记忆用户选过的线路图(顶部栏切换器)。键名带项目前缀,不与别的页串味 */
const PACK_MEM_KEY = 'hubflow.stationPack';
/**
 * 由入口注入当前包键(浏览器在挂载前、mock 在插件装配时各调一次)。
 *
 * ⚠️ 这条是**注入**通道，故意**不发通知、不增版本号**（Issue IKPFR4）：
 *    · 浏览器侧它在挂载前跑一次，那时还没有任何订阅者；
 *    · Node 侧 mock 每个请求都调它（按请求头现取站），发通知只会把"请求级切换"错当成
 *      "用户切站"，浏览器侧的订阅者根本不在同一个进程里。
 *    用户切站走 `switchStation()`（`shared/stationSwitch.ts`）→ `switchPack()`。
 */
export function setActivePackKey(key) {
    injectedKey = key;
}
/**
 * 启动时读回用户上次选过的包(`switchPack` 写的那份)。
 *
 * 为什么需要:包键是模块级变量,用户切站后重开页面 / 强刷即丢 —— 没有这一步,切换器
 * **选完再打开就退回默认包**,等于坏的。读不到 / 读坏了就落回注入值(构建期的 `VITE_STATION_PACK`,
 * 或 `?pack=` 深链命中的键,见 `main.ts`)。Node 侧(mock 中间件)没有 `localStorage`,
 * 靠 try/catch 静默落回注入值。
 *
 * ⚠️ 老浏览器里可能残留**已删除的包键**(`'A'` / `'B'` / `'Y'` 随 IKM4XX / IKM4KP 删除,
 *    `'Z21'` 随 IKP5D3 删除):`PACKS[k]` 这一关就是为它设的 —— 未知键一律落回注入值,
 *    不白屏、也不会把坏键写回去(见 `switchPack` 的首行守卫)。
 */
export function restorePackKey(fallback) {
    try {
        const k = localStorage.getItem(PACK_MEM_KEY);
        if (k && PACKS[k])
            return k;
    }
    catch {
        /* localStorage 不可用(隐私模式 / Node 侧):用注入值 */
    }
    return fallback;
}
/**
 * 运行时切换站点包(顶部栏线路图切换器 / 大屏工具条,业主 2026-10-14)。
 * 只改浏览器侧的键:几何(demoNetwork 按包键惰性重建)与 mock(每次请求读包)都从
 * `activePack()` 现取,所以切完包页面路网/基线/告警整套跟着换;
 * 同时落一份 localStorage,好让下次打开仍然停在这个站。
 *
 * ⚠️ IKPFR4 起**不再整页刷新**：键真的变了才 `version++` 并通知订阅者(见 `onPackChange`)，
 *    由订阅者各自重取 setup 期快照。所以本函数只管"换个键 + 报信"，重绘/重置/拉数据
 *    一律不在这个零依赖文件里做。
 *
 * 现在有两个站包(Z 61 段 / GZ 708 段),顶栏切换器与大屏工具条按钮都调 `switchStation()`。
 * 未知键直接 return(不写 localStorage):切到后端没登记的包 = 全站 404,坏键还会持久化。
 */
export function switchPack(key) {
    if (!PACKS[key])
        return;
    const changed = activePackKey() !== key;
    injectedKey = key;
    try {
        localStorage.setItem(PACK_MEM_KEY, key);
    }
    catch {
        /* 隐私模式等写不进去:不影响本次会话内切换,只是刷新后不记忆 */
    }
    if (!changed)
        return;
    version++;
    // 复制一份再遍历:订阅回调里可能顺手取消订阅(切页 / 卸载),直接遍历 Set 会漏掉后面的订阅者
    for (const fn of [...listeners]) {
        try {
            fn();
        }
        catch (e) {
            // 一个订阅者抛错不能把整次切站拖垮(其余订阅者还要重绘各自的快照)
            console.error('[station-packs] 包键订阅者执行失败', e);
        }
    }
}
/**
 * 当前生效的包键。
 * 键不存在时落默认包(不抛错):演示站多起来以后,"包里没有这个键"要表现得像"走默认站",
 * 而不是整页白屏;但键写错这件事要在页脚可见(见 `packNote()` 会同时打出键与包名)。
 */
export function activePackKey() {
    const key = injectedKey ?? DEFAULT_PACK_KEY;
    return PACKS[key] ? key : DEFAULT_PACK_KEY;
}
/** 当前生效的站点包 */
export function activePack() {
    return PACKS[activePackKey()] ?? STATION_Z;
}
/** 包自检说明(页脚展示用):包键 + 这个包是什么 */
export function packNote() {
    const p = activePack();
    return `站点包 ${p.key} · ${p.note}`;
}
/** 可选线路清单(顶部栏切换器 / 大屏按钮用):键 + 短标签(缺省站名) + 一句话口径 */
export function packItems() {
    return Object.values(PACKS).map((p) => ({
        key: p.key,
        name: p.label ?? p.station.name,
        note: p.note,
    }));
}
/**
 * 已接入车站的**全国站表**（Issue IKPFVN A）：键 / 站名 / 经纬度 / 站区范围 / 段数 / 包路径。
 *
 * 为什么单独一支、而不是让各处继续拼 `packItems()`：`packItems()` 只有 `key/name/note`，
 * 没有经纬度也没有站区范围 —— 全国地图的 pin 不知道钉在哪、切站镜头不知道该飞多近。
 * 这份数据来自生成物 `stations.generated.ts`（源头是 `work/twin/site-ranges.json`），
 * 全国 pin / 全国浮层卡片 / 切站镜头 / 顶栏切换器**共用这一份**，加站只改配置 + 重跑脚本。
 *
 * 只读：不要在调用方改写返回的数组或元素（它就是生成物里的那一份）。
 */
export function stationEntries() {
    return STATIONS;
}
export { STATIONS };
