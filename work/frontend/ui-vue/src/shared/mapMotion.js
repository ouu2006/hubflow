// 全国视角 ↔ 站区视角的**镜头运动**（Issue IKPFVN）。
//
// 业主 2026-10-21 原话口径：「切换高铁站要有动作展示：地图缩小 → 移动到对应高铁站 →
// 放大 → 路线显示、信息切换」。所以这里的正事是三件：
//   ① 把"缩远 / 平移 / 放大"三段时长、中国范围、站区取景**收在这一处**，别散在组件里；
//   ② 提供**唯一一条**动画通道：任何时刻只允许一个进行中的运动，新选择先 `map.stop()` 再从当前
//      相机重新开始 —— 不排队、不叠加（连点两个站时，最终必须停在**最后点的那一站**）；
//   ③ 尊重 `prefers-reduced-motion`：那种设置下不要"缩远再放大"这种花活，≤250 ms 直接到站区，
//      但**信息仍然正确**（到站、换站名、换路网这件事一样不少）。
//
// 为什么不用 `setInterval` 逐帧改 center：那会自己造一条"假动画"通道，与 MapLibre 内部的
// 相机状态打架（拖拽、惯性、`fitBounds` 同时跑会互相踩），也没有 `moveend` 可以等人。
// 这里一律用 `easeTo` / `fitBounds` + `once('moveend')`，动画由渲染器自己插值。
//
// ⚠️ 本文件**不做**任何业务判断：站点包 / 数据 / 面板状态都由调用方管，这里只管相机。
import { PACKS, STATIONS } from '../station-packs/index';
/**
 * 三段动作的时长（ms）——**集中在这里调**，不要在调用方再写魔法数字。
 *
 * 取值理由：缩远 700 是"先让人看清自己离开了哪"；平移 550 略快，因为在低缩放下移动距离
 * 短、画面变化小；放大 950 收尾最慢，让最后落点看得清。三段合计约 2.2 s，比一次硬切
 * 有仪式感，又不至于让人等。
 */
export const MOTION = {
    /** ① 缩远：从当前视野退到中间缩放 */
    zoomOutMs: 700,
    /** ② 平移：在中间缩放下移到目标站 */
    panMs: 550,
    /** ③ 放大：落进站区取景 */
    zoomInMs: 950,
    /** 退回全国视角（「← 全国」按钮）的总时长 */
    overviewMs: 900,
    /** `prefers-reduced-motion: reduce` 下的总时长（必须 ≤250 ms，见文件头第 ③ 条） */
    reducedMs: 200,
    /**
     * 平移时的中间缩放。取 5.5（约"省域"尺度）：Z（肇庆东）与 GZ（广州南）相距约 100 km，
     * 在这个尺度下两站都在一屏里，"从哪来、到哪去"看得出来；再大就只剩两个点。
     */
    panZoom: 5.5,
    /** 站区取景的最大缩放：太小看不清段，太大底图瓦片会糊 */
    fitMaxZoom: 17.5,
};
/**
 * 中国范围（全国视角的取景框）。
 *
 * 数值 = `src/assets/geo/china-outline.geojson`（Natural Earth 1:110m 简化轮廓）的实际外包框，
 * 与底图无关：底图拉得到时它是起手视野，拉不到时它正好框住兜底轮廓。
 * ⚠️ 这是**显示用外包框**，不是国土主张范围；页面文案不得据此写任何边界话术。
 */
export const CHINA_BBOX = { sw: [73.675, 18.198], ne: [135.026, 53.459] };
/** 全国视角的起手缩放（`fitBounds` 之前的初值；实际取景一律走 `fitBounds`） */
export const CHINA_ZOOM = 3.4;
/**
 * 全国视角的**最小**缩放（3 = 「全国视角 zoom 落在 3–6」这条判定的下界）。
 *
 * 为什么需要一个下限：`fitBounds` 是**按容器高度**收敛的 —— 中栏只有 380 px 高时，
 * 把 35 个纬度装进去会算到 2.3 档，中国大陆缩成中间一小块，一点也不像"全国大地图"。
 * 窗口再矮、KPI / 告警条再占几像素，都还会更低。所以宽高装不下时**宁可轻微裁掉南北边**，
 * 也要保住"一眼看出是全国"的体量；装得下时它不生效（`zoom` 本来就 ≥3）。
 */
export const NATIONAL_ZOOM_MIN = 3;
/**
 * 全国取景的收尾：低于下限就抬到下限（`duration: 0` = 不是一次新的转场，只是把
 * `fitBounds` 的结果贴到可接受的档位）。站区取景不走这里。
 */
export function clampOverviewZoom(map) {
    const zoom = map.getZoom();
    if (Number.isFinite(zoom) && zoom < NATIONAL_ZOOM_MIN) {
        map.easeTo({ zoom: NATIONAL_ZOOM_MIN, duration: 0 });
    }
}
// ---------------------------------------------------------------- 是否"减弱动效"
/**
 * 用户是否要求减少动效。
 * 读 `matchMedia` 而不是缓存一次：系统设置在页面开着的时候也能改。
 */
export function motionReduced() {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function')
        return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}
// ---------------------------------------------------------------- 取景目标
/** 全国视角：中心 + 缩放 + 外包框（起手建图与「← 全国」共用） */
export function overviewCamera() {
    const center = [
        (CHINA_BBOX.sw[0] + CHINA_BBOX.ne[0]) / 2,
        (CHINA_BBOX.sw[1] + CHINA_BBOX.ne[1]) / 2,
    ];
    return { center, zoom: CHINA_ZOOM, bounds: CHINA_BBOX };
}
/**
 * 一个站的**真实**取景范围 = 该站包 `segments` 折线的经纬度 min/max。
 *
 * 为什么不用站区范围 `range_m` 折算：`range_m` 是"站区有多大"的登记值（Z 500 m / GZ 1000 m），
 * 而路网实际铺开的矩形并不等于那个圆；按包内几何算，`fitBounds` 才真的一屏装下整套路网。
 * 包内几何为空（坏包 / 空站）时返回 `null`，调用方退回全国视角 —— 不猜。
 */
export function stationBounds(key) {
    const pack = PACKS[key];
    if (!pack)
        return null;
    let minLon = Number.POSITIVE_INFINITY;
    let minLat = Number.POSITIVE_INFINITY;
    let maxLon = Number.NEGATIVE_INFINITY;
    let maxLat = Number.NEGATIVE_INFINITY;
    for (const seg of pack.segments) {
        for (const [lon, lat] of seg.coords) {
            if (lon < minLon)
                minLon = lon;
            if (lon > maxLon)
                maxLon = lon;
            if (lat < minLat)
                minLat = lat;
            if (lat > maxLat)
                maxLat = lat;
        }
    }
    if (!Number.isFinite(minLon) || !Number.isFinite(minLat))
        return null;
    // 单点 / 零面积的路网：给一个极小的框，免得 fitBounds 把缩放顶到 maxZoom 后画面乱飘
    const padLon = maxLon - minLon > 0 ? 0 : 1e-4;
    const padLat = maxLat - minLat > 0 ? 0 : 1e-4;
    return {
        sw: [minLon - padLon, minLat - padLat],
        ne: [maxLon + padLon, maxLat + padLat],
    };
}
/** 站区视角：取景框 + 平移落点（低缩放下的目标中心取**站区锚点**，见 `STATIONS`） */
export function stationCamera(key) {
    const bounds = stationBounds(key);
    if (!bounds)
        return null;
    const entry = STATIONS.find((s) => s.key === key);
    const center = entry
        ? [entry.lon, entry.lat]
        : [(bounds.sw[0] + bounds.ne[0]) / 2, (bounds.sw[1] + bounds.ne[1]) / 2];
    return { key, bounds, center, maxZoom: MOTION.fitMaxZoom };
}
// ---------------------------------------------------------------- 留白
/** 取景留白的通用边距（px）：顶部给工具条呼吸，底部给比例尺 / 注脚 */
export const MOTION_MARGIN_PX = 36;
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
export function stationPadding(v) {
    const settle = Math.round((v.columnsWidth ?? 0) * 0.04);
    const legend = Math.min(v.legendWidth ?? 0, Math.round(v.width * 0.36));
    return {
        top: MOTION_MARGIN_PX + 20 + settle,
        right: MOTION_MARGIN_PX + settle,
        bottom: MOTION_MARGIN_PX + 28 + settle,
        left: Math.max(legend + settle, MOTION_MARGIN_PX + settle),
    };
}
/** 全国取景留白：全国模式左右栏收起，只要一点点对称留白（外加图例收起时的 0） */
export function overviewPadding(v) {
    const settle = Math.round(Math.min(v.width, v.height) * 0.02);
    const edge = 16 + settle;
    return { top: edge, right: edge, bottom: edge + 8, left: edge };
}
// ---------------------------------------------------------------- 动画通道（只允许一条）
/**
 * 运动代次。每发起一次运动 +1；任何一步在 await 之后都对一下代次，对不上就**立刻收手**。
 *
 * 这就是"只允许一个动画在跑"的实现方式：不排队、不叠加 —— 新运动先把 `map.stop()` 打断旧的，
 * 再把代次 +1；旧的那条链醒来发现代次变了，直接返回 `cancelled`，一个像素都不再改。
 */
let runSeq = 0;
/** 打断当前运动（组件切模式 / 卸载 / 新一轮选择前调用） */
export function cancelMotion(map) {
    runSeq += 1;
    map.stop();
}
function resolvePadding(padding) {
    return typeof padding === 'function' ? padding() : padding;
}
/**
 * 等一次相机移动结束。
 *
 * 返回 `false` = 这次运动已经被打断（代次变了），调用方应停止后续步骤。
 * 兜底超时取 `预算 + 120 ms`：`easeTo` 到"已经在这个位置"时 MapLibre 可能一个 `moveend`
 * 都不发，没有兜底就会永远挂住（切站流程会卡在"过渡中"）。
 */
function waitMoveEnd(map, budgetMs, run) {
    return new Promise((resolve) => {
        let settled = false;
        const finish = (ok) => {
            if (settled)
                return;
            settled = true;
            map.off('moveend', onEnd);
            window.clearTimeout(timer);
            resolve(ok);
        };
        const onEnd = () => finish(run === runSeq);
        map.once('moveend', onEnd);
        const timer = window.setTimeout(() => finish(run === runSeq), budgetMs + 120);
    });
}
const cancelled = (key, phase) => ({
    key,
    phase,
    cancelled: true,
});
/**
 * 飞到某个站（缩远 → 平移 → 放大）。
 *
 * 打断语义：任何时刻点另一站，从**当前相机**重新开始（`map.stop()` 保留当下的 center/zoom），
 * 最终状态一定等于最后点击的那一站。
 *
 * `prefers-reduced-motion: reduce`：只做最后一步 `fitBounds`（≤250 ms），不缩远不平移；
 * 到站这件事、换站名换路网这件事照旧发生（信息正确性不因动效偏好而打折）。
 */
export async function flyToStation(map, key, opts) {
    const cam = stationCamera(key);
    // 包里没有这个站 / 站包几何为空：不猜落点，就地返回（调用方退回全国视角）
    if (!cam)
        return { key, phase: 'station', cancelled: false };
    const run = ++runSeq;
    map.stop();
    if (motionReduced()) {
        opts.onPhase?.('entering');
        await opts.beforeFit?.();
        if (run !== runSeq)
            return cancelled(key, 'entering');
        map.fitBounds([cam.bounds.sw, cam.bounds.ne], {
            padding: resolvePadding(opts.padding),
            maxZoom: cam.maxZoom,
            duration: MOTION.reducedMs,
            essential: true,
        });
        await waitMoveEnd(map, MOTION.reducedMs, run);
        return run === runSeq ? { key, phase: 'station', cancelled: false } : cancelled(key, 'station');
    }
    // ① 缩远。已经在中间缩放下（刚点「← 全国」又点回来）就跳过这一跳，
    //    否则会先"放大"到 5.5 再平移 —— 与业主口径的"缩小 → 移动 → 放大"相反。
    const from = map.getZoom();
    if (from > MOTION.panZoom + 0.15) {
        opts.onPhase?.('leaving');
        map.easeTo({ zoom: MOTION.panZoom, duration: MOTION.zoomOutMs, essential: true });
        if (!(await waitMoveEnd(map, MOTION.zoomOutMs, run)))
            return cancelled(key, 'leaving');
    }
    // ② 在低缩放下平移到目标站（中心取站区锚点，而不是取景框中心：落点更符合"到站"的直觉）
    opts.onPhase?.('panning');
    map.easeTo({ center: cam.center, zoom: MOTION.panZoom, duration: MOTION.panMs, essential: true });
    if (!(await waitMoveEnd(map, MOTION.panMs, run)))
        return cancelled(key, 'panning');
    // ③ 放大落进站区。`beforeFit` 里组件会先 `map.resize()` —— 左右栏刚滑入，
    //    resize 之前量到的宽高是旧的，直接 fitBounds 会取偏。
    opts.onPhase?.('entering');
    await opts.beforeFit?.();
    if (run !== runSeq)
        return cancelled(key, 'entering');
    map.fitBounds([cam.bounds.sw, cam.bounds.ne], {
        padding: resolvePadding(opts.padding),
        maxZoom: cam.maxZoom,
        duration: MOTION.zoomInMs,
        essential: true,
    });
    if (!(await waitMoveEnd(map, MOTION.zoomInMs, run)))
        return cancelled(key, 'entering');
    return { key, phase: 'station', cancelled: false };
}
/**
 * 退回全国视角（「← 全国」按钮 / 首次进站后返回）。
 *
 * 只有两步：先缩远（把站区展开成省域，避免"一下子飞没"），再 `fitBounds` 到中国范围。
 * 与 `flyToStation` 共用同一个代次，所以"飞到一半点全国"同样是"打断 + 从当前相机重开"。
 */
export async function flyToOverview(map, opts) {
    const run = ++runSeq;
    map.stop();
    const cam = overviewCamera();
    if (motionReduced()) {
        opts.onPhase?.('entering');
        await opts.beforeFit?.();
        if (run !== runSeq)
            return cancelled(null, 'entering');
        map.fitBounds([cam.bounds.sw, cam.bounds.ne], {
            padding: resolvePadding(opts.padding),
            duration: MOTION.reducedMs,
            essential: true,
        });
        await waitMoveEnd(map, MOTION.reducedMs, run);
        if (run !== runSeq)
            return cancelled(null, 'national');
        clampOverviewZoom(map);
        return { key: null, phase: 'national', cancelled: false };
    }
    if (map.getZoom() > MOTION.panZoom + 0.15) {
        opts.onPhase?.('leaving');
        map.easeTo({ zoom: MOTION.panZoom, duration: MOTION.zoomOutMs, essential: true });
        if (!(await waitMoveEnd(map, MOTION.zoomOutMs, run)))
            return cancelled(null, 'leaving');
    }
    opts.onPhase?.('entering');
    await opts.beforeFit?.();
    if (run !== runSeq)
        return cancelled(null, 'entering');
    map.fitBounds([cam.bounds.sw, cam.bounds.ne], {
        padding: resolvePadding(opts.padding),
        duration: MOTION.overviewMs,
        essential: true,
    });
    if (!(await waitMoveEnd(map, MOTION.overviewMs, run)))
        return cancelled(null, 'entering');
    clampOverviewZoom(map);
    return { key: null, phase: 'national', cancelled: false };
}
