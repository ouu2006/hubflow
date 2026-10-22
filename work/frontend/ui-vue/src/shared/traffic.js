// traffic 态势大屏共享类型与四级编码(运行时零依赖,浏览器 / mock 中间件共用)。
// 字段名逐个对照 docs/数据契约.md v2.0(snake_case);四级色值与图标照抄手册 §6.2,不新造。
// ⚠️ 2026-10-12 配色整体切换 TDesign Light(手册 §6.2 / §6.2.1 / §6.2.2):
// 图形色取官方色板(success-5 / warning-5 / error-6 / gray-7),文字色深一阶;
// 旧值(蓝 #1E6FD9 / 黄 #F2B705 / 橙 #E8760C / 红 #C62828 / 灰 #8C8C8C)已作废。
// 关键语义:旧「畅通蓝」与品牌蓝 #0052D9 撞车,故畅通改 success 绿——等级色**不得**使用品牌蓝。
export const LEVELS = {
    1: { name: '畅通', color: '#2BA471', text: '#006C45', bars: 1 },
    2: { name: '缓行', color: '#E9B32E', text: '#A06A00', bars: 2 },
    3: { name: '拥堵', color: '#E37318', text: '#BE5A00', bars: 3 },
    4: { name: '严重拥堵', color: '#D54941', text: '#AD352F', bars: 4 },
};
// 非等级状态:数据陈旧(> 120 s【待标定】)显示灰色,只展示不推荐(TC-11 展示侧)
export const UNAVAILABLE = { name: '数据不可用', color: '#8B8B8B', text: '#8B8B8B', bars: 0 };
export const STALE_AFTER_S = 120;
/**
 * ISO8601(可带偏移)→ `YYYY-MM-DD HH:mm:ss`(本地展示口径)。
 * 快照时间在页面上只作展示,统一走本函数——避免顶栏/页脚出现 `2026-10-12T16:23:54+08:00` 这种机器格式。
 * 解析失败原样返回(不猜、不产出 Invalid Date)。
 */
export function formatStamp(iso) {
    if (!iso)
        return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime()))
        return iso;
    const p = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}
/** 只取时分秒(首次观测时间等行内展示用) */
export function formatClock(iso) {
    if (!iso)
        return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime()))
        return iso;
    const p = (n) => String(n).padStart(2, '0');
    return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}
export function isStale(seg) {
    return (seg.data_age_s ?? 0) > STALE_AFTER_S;
}
/** 等级色：数据陈旧 / 上游未判级(level=0) / 非法等级一律灰色「数据不可用」，绝不落进通配色(TC-11) */
export function levelStyle(seg) {
    const style = LEVELS[seg.level];
    return isStale(seg) || !style ? UNAVAILABLE : style;
}
/** 等级文字色(深一阶):用于浅底上的等级文字,与图形色同源但对比度更高 */
export function levelTextColor(seg) {
    return levelStyle(seg).text;
}
// ---------- 拥挤指数(CI)展示口径(Issue #66;手册 §6.5 第 1 条) ----------
// 硬口径:CI 只用于**热力展示与辅助排序**,**不得作为判级依据**;CI 与四项指标冲突时一律以四项指标为准。
// 权重与档位边界不在前端定义——真实来源是 stations/thresholds.json(唯一写手开发B)。
export const CI_MAX = 100;
/** CI 档位边界 = **展示口径**(文档未定档,此处均分四档;判级一律以 level 为准,图例逐条写明) */
export const CI_BANDS = [0, 25, 50, 75, 100];
export const CI_DISCLAIMER = 'CI(拥挤指数)只用于热力展示与辅助排序,不得作为判级依据;与四项指标冲突时一律以四项指标为准(手册 §6.5 第 1 条)';
export const CI_BAND_NOTE = '档位边界为展示口径(文档未定档),判级一律以 level 为准';
function hexToRgb(hex) {
    const h = hex.replace('#', '');
    return [
        Number.parseInt(h.slice(0, 2), 16),
        Number.parseInt(h.slice(2, 4), 16),
        Number.parseInt(h.slice(4, 6), 16),
    ];
}
function rgbToHex(rgb) {
    return `#${rgb.map((v) => Math.round(Math.min(255, Math.max(0, v))).toString(16).padStart(2, '0')).join('')}`;
}
function lerpColor(a, b, t) {
    const [r1, g1, b1] = hexToRgb(a);
    const [r2, g2, b2] = hexToRgb(b);
    return rgbToHex([r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t]);
}
// 色阶锚点取手册 §6.2 的四级色值(档心为锚点,档间线性过渡)——
// **不自造第五套颜色语义**;灰 #8B8B8B 仍只表示"数据不可用",不参与色阶。
//
// ⚠️ 已知取舍(独立审查发现,记此不改):TDesign 下畅通绿 #2BA471 与缓行黄 #E9B32E 之间的
//   线性过渡中点必然接近中性灰——本实现的过渡中点落在 ci≈25(锚点 12.5 / 37.5 的中点),
//   视觉上与"数据不可用"灰 #8B8B8B 相近。这是**手册 §6.2 四级色顺序本身**带来的,不是自造色阶;
//   改锚点顺序或改色相会动到手册语义,故不改。判据仍以灰档行(三重编码 + 文字「不可用」)为准,
//   不靠颜色单通道区分"不可用"与"低 ci"。
const CI_ANCHORS = [
    { at: 12.5, color: LEVELS[1].color },
    { at: 37.5, color: LEVELS[2].color },
    { at: 62.5, color: LEVELS[3].color },
    { at: 87.5, color: LEVELS[4].color },
];
/** CI → 颜色:0~100 线性映射到四级色阶(超出范围按端点夹取) */
export function ciColor(ci) {
    // 非有限入参(NaN / ±Infinity)不落到函数末尾被画成红色"严重拥堵",与 ciAvailable 同口径交灰档
    if (!Number.isFinite(ci))
        return UNAVAILABLE.color;
    const v = Math.min(CI_MAX, Math.max(0, ci));
    const first = CI_ANCHORS[0];
    const last = CI_ANCHORS[CI_ANCHORS.length - 1];
    if (v <= first.at)
        return first.color;
    if (v >= last.at)
        return last.color;
    for (let i = 0; i < CI_ANCHORS.length - 1; i++) {
        const a = CI_ANCHORS[i];
        const b = CI_ANCHORS[i + 1];
        if (v >= a.at && v <= b.at)
            return lerpColor(a.color, b.color, (v - a.at) / (b.at - a.at));
    }
    return last.color;
}
/** 该路段能否画拥挤指数:缺 `ci` 或数据陈旧 → 灰色"数据不可用"(TC-11),**绝不落进通配色** */
export function ciAvailable(seg) {
    return !isStale(seg) && typeof seg.ci === 'number' && Number.isFinite(seg.ci);
}
/** 拥挤指数渲染色(不可用即灰) */
export function ciStyleColor(seg) {
    return ciAvailable(seg) ? ciColor(seg.ci) : UNAVAILABLE.color;
}
/** 指数色阶图例的渐变色标(CSS linear-gradient 用,自低到高) */
export function ciGradientCss() {
    const stops = [0, 20, 40, 60, 80, 100];
    return `linear-gradient(90deg, ${stops.map((s) => `${ciColor(s)} ${s}%`).join(', ')})`;
}
// ---------- SSE ----------
// 事件名是新增的(不改既有事件名),与 work/assembly/traffic.py 的 GET /api/traffic/stream 对齐
export const TRAFFIC_SNAPSHOT_EVENT = 'traffic_snapshot';
/** 按当前路段快照重算告警等级(快照缺该路段 / 上游未判级 level=0 时退回告警记录值) */
export function alertLevelOf(a, findSegment) {
    const segLevel = findSegment(a.segment_id)?.level;
    return typeof segLevel === 'number' && segLevel >= 1 && segLevel <= 4 ? segLevel : a.level;
}
