// 落客点 / 场区的**只读展示门面**（Issue IKP5BZ）。
//
// 唯一真值源（队长 2026-10-20 裁定 = 方案 A）：**前端站点包**
// `activePack().dropoffs` / `.zones`（类型 `PackLandmark`，见 `station-packs/types.ts`）。
// 不读 `/api/traffic/network`——那份 `dropoffs` / `zones` 在 Z 站是 `SEG-###` 样例点、
// 在 GZ 站是空表，与本站真网段号对不上（详见 `work/frontend/README.md` 对应小节）。
//
// 口径：
//   ① 包里的坐标是**路段折线上的演示点**，不是踏勘点位，页面一律标「演示点」；
//   ② `PackLandmark` 本身**没有 `segment_id`**（不新增接口字段、不改站点包形状），
//      「所属路段」按**点到折线的最近距离**推定，只用于浮牌展示与点选跳转；
//   ③ 本模块只做几何距离展示，不参与判级 / 路线 / 任何计算。
import { activePack } from '../station-packs/index';
/** 米 / 度换算用的地球半径近似（只用于展示距离，不参与任何业务计算） */
const METERS_PER_DEG = 111_320;
/** 邻近判定半径（米）：选中路段时列出此范围内的点位（同段或邻近段） */
export const NEARBY_RADIUS_M = 150;
function metersPerLon(lat) {
    return METERS_PER_DEG * Math.cos((lat * Math.PI) / 180);
}
/**
 * 点到线段（经纬度，近似平面）的最近距离，单位米。
 * 经度按当前纬度做 cos 压缩——演示距离够用，不引入投影依赖。
 */
function pointToSegmentM(lon, lat, a, b) {
    const mx = metersPerLon(lat);
    const ax = a[0] * mx;
    const ay = a[1] * METERS_PER_DEG;
    const bx = b[0] * mx;
    const by = b[1] * METERS_PER_DEG;
    const px = lon * mx;
    const py = lat * METERS_PER_DEG;
    const dx = bx - ax;
    const dy = by - ay;
    const len2 = dx * dx + dy * dy;
    if (len2 <= 0)
        return Math.hypot(px - ax, py - ay);
    const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / len2));
    return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}
/** 点到折线的最近距离（米） */
function pointToLineM(lon, lat, coords) {
    if (coords.length === 0)
        return Number.POSITIVE_INFINITY;
    if (coords.length === 1) {
        const mx = metersPerLon(lat);
        return Math.hypot((lon - coords[0][0]) * mx, (lat - coords[0][1]) * METERS_PER_DEG);
    }
    let best = Number.POSITIVE_INFINITY;
    for (let i = 1; i < coords.length; i++) {
        const d = pointToSegmentM(lon, lat, coords[i - 1], coords[i]);
        if (d < best)
            best = d;
    }
    return best;
}
/** 在一组路段里找离该点最近的一条（同距取先出现者；空集返回 null） */
function nearestSegment(lon, lat, segments) {
    let best = null;
    for (const segment of segments) {
        const d = pointToLineM(lon, lat, segment.coords);
        if (!best || d < best.distance_m)
            best = { segment, distance_m: d };
    }
    return best;
}
/** 包内全部落客点 + 场区（按包键缓存：切换站点包会整页刷新，缓存不会跨包串味） */
let cachedKey = '';
let cachedViews = [];
function landmarkViews() {
    const pack = activePack();
    if (pack.key === cachedKey)
        return cachedViews;
    const out = [];
    const add = (list, kind) => {
        for (const item of list) {
            const near = nearestSegment(item.lon, item.lat, pack.segments);
            out.push({
                ...item,
                kind,
                // 包里没有点位 ↔ 路段映射；推不出时如实留空，不编一个段号
                segment_id: near?.segment.segment_id ?? '',
                segment_name: near?.segment.name ?? '未标定',
                distance_m: near?.distance_m ?? Number.POSITIVE_INFINITY,
            });
        }
    };
    add(pack.dropoffs ?? [], 'dropoff');
    add(pack.zones ?? [], 'zone');
    cachedKey = pack.key;
    cachedViews = out;
    return out;
}
/** 地图 Marker 用：全部落客点 + 场区（坐标、名称、推定路段、演示点 id） */
export function landmarkPins() {
    return landmarkViews();
}
/**
 * 选中路段附近的点位（同段或邻近段）：按到**该路段折线**的最近距离筛选并按距离升序。
 * 右栏文字入口用：图上点不到时也能查，点条目选中其所属路段。
 */
export function landmarksNearSegment(segmentId, radiusM = NEARBY_RADIUS_M) {
    if (!segmentId)
        return [];
    const pack = activePack();
    const segment = pack.segments.find((s) => s.segment_id === segmentId);
    if (!segment)
        return [];
    return landmarkViews()
        .map((item) => ({ ...item, distance_m: pointToLineM(item.lon, item.lat, segment.coords) }))
        .filter((item) => item.segment_id === segmentId || item.distance_m <= radiusM)
        .sort((a, b) => a.distance_m - b.distance_m);
}
/** 点位类别文案（图例 / 列表 / 浮牌共用同一套措辞） */
export function landmarkKindLabel(kind) {
    return kind === 'dropoff' ? '落客点' : '场区';
}
