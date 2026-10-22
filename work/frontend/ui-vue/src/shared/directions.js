// 路段方向 / 车道 / 对向 / 贯通字段的**只读展示门面**（Issue IKOQEJ）。
//
// 数据来源：站点包 `segmentDirections`（由 `work/frontend/tools/gen_station_directions.py`
// 从 `work/twin/netpack/…/network_junction.enriched.json` **只读生成**）。
// 口径铁律：
//   ① 这些字段**不是契约字段、不进接口、不参与判级/路线计算**；页面只展示，不据此改网络；
//   ② 缺值 / 老包没有方向字段 → 一律「— / 未标定」，**不编真实车道数/方向**；
//   ③ 页面上如实标注来源（OSM oneway / 推导 / 默认演示值），不宣称"真实车道/方向来自实测"；
//   ④ `continuity.tail_connected=false` 或断口 gap 未闭合 → 显示「贯通性待核」，只提示不改网络。
import { activePack } from '../station-packs/index';
/** 某段的方向/车道/贯通字段；源台账没有 → null（页面显示未标定） */
export function directionOf(segmentId) {
    if (!segmentId)
        return null;
    return activePack().segmentDirections?.[segmentId] ?? null;
}
/** 单向 = forward/backward；双向 = bidirectional；缺字段/未知 = unknown（地图画灰色「?」标，不画真箭头） */
export function directionKindOf(direction) {
    const raw = direction?.direction;
    if (raw === 'forward' || raw === 'backward' || raw === 'bidirectional')
        return raw;
    return 'unknown';
}
export function directionLabel(kind) {
    switch (kind) {
        case 'forward':
            return '单向（正向）';
        case 'backward':
            return '单向（反向）';
        case 'bidirectional':
            return '双向（左右两向）';
        default:
            return '未标定';
    }
}
/** 来源文案：osm / derived / default 分别说清，不混成"实测" */
export function fieldSourceLabel(source) {
    switch (source) {
        case 'osm':
            return 'OSM oneway';
        case 'derived':
            return '推导';
        case 'default':
            return '默认演示值';
        default:
            return '未标定';
    }
}
export function directionSourceLabel(direction) {
    if (!direction)
        return '未标定';
    return fieldSourceLabel(direction.field_sources?.direction);
}
function laneValue(value) {
    return typeof value === 'number' && Number.isFinite(value) ? String(value) : '—';
}
/** 车道数（前 / 后 / 共）；缺值如实「—」，不拿 0/1 冒充真实车道 */
export function lanesOf(direction) {
    if (!direction) {
        return { forward: '—', backward: '—', total: '—', any: false, text: '— / — / —', source: '未标定' };
    }
    const forward = laneValue(direction.lanes_forward);
    const backward = laneValue(direction.lanes_backward);
    const total = laneValue(direction.lanes_total);
    const labels = new Set();
    for (const key of ['lanes_forward', 'lanes_backward', 'lanes_total']) {
        const raw = direction.field_sources?.[key];
        if (raw)
            labels.add(fieldSourceLabel(raw));
    }
    return {
        forward,
        backward,
        total,
        any: [direction.lanes_forward, direction.lanes_backward, direction.lanes_total].some((value) => typeof value === 'number' && Number.isFinite(value)),
        text: `${forward} / ${backward} / ${total}`,
        source: labels.size > 0 ? [...labels].join(' / ') : '未标定',
    };
}
/** 贯通性：尾端未贯通 / 断口未闭合 → 「贯通性待核」（只提示，不自动改网络） */
export function continuityOf(direction) {
    const continuity = direction?.continuity;
    if (!direction || !continuity) {
        return { state: 'unknown', label: '未标定', detail: '源台账无该段贯通字段', tone: 'muted' };
    }
    const tail = continuity.tail_connected;
    const head = continuity.head_connected;
    const gap = continuity.gap_to_next_m;
    if (tail === false) {
        const gapText = typeof gap === 'number' && Number.isFinite(gap)
            ? gap === 0
                ? '（gap 0 m，节点/相切待核）'
                : `（gap ${gap.toFixed(1)} m）`
            : '（断口距离未标定）';
        return {
            state: 'pending',
            label: '贯通性待核',
            detail: `尾端未贯通${gapText}；仅提示，不改动网络`,
            tone: 'warn',
        };
    }
    if (tail === true) {
        return {
            state: 'ok',
            label: '贯通',
            detail: head === false ? '头端未贯通、尾端贯通（enriched 推导）' : '头/尾端贯通（enriched 推导）',
            tone: 'ok',
        };
    }
    return {
        state: 'unknown',
        label: '未标定',
        detail: 'enriched 未给 tail_connected，不猜贯通与否',
        tone: 'muted',
    };
}
/** 对向段段号；null = 未标定（不拿同链上一段冒充） */
export function oppositeOf(direction) {
    return direction?.opposite_segment_id ?? null;
}
/**
 * 路段走向方位角（度；0 = 北，顺时针）。
 * ⚠️ 只用于地图「方向标」旋转，**不是**精确测向；几何来自 OSM，展示口径。
 */
export function bearingDeg(coords) {
    if (!Array.isArray(coords) || coords.length < 2)
        return 0;
    const [lon1, lat1] = coords[0];
    const [lon2, lat2] = coords[coords.length - 1];
    const latRad = (((lat1 + lat2) / 2) * Math.PI) / 180;
    const east = (lon2 - lon1) * Math.cos(latRad);
    const north = lat2 - lat1;
    const deg = (Math.atan2(east, north) * 180) / Math.PI;
    return (deg + 360) % 360;
}
/**
 * 折线上按长度比例取点（用于把方向标放在路段中段）。
 * 近似平面（经度按 cos(lat) 压缩）足以定位展示点，不参与任何计算。
 */
export function pointAtFraction(coords, fraction) {
    if (!Array.isArray(coords) || coords.length === 0)
        return [0, 0];
    if (coords.length === 1)
        return coords[0];
    const f = Math.min(1, Math.max(0, fraction));
    const lat0 = (coords[0][1] * Math.PI) / 180;
    const sx = Math.cos(lat0);
    const lengths = [];
    let total = 0;
    for (let i = 1; i < coords.length; i++) {
        const [lonA, latA] = coords[i - 1];
        const [lonB, latB] = coords[i];
        const dx = (lonB - lonA) * sx;
        const dy = latB - latA;
        const len = Math.hypot(dx, dy);
        lengths.push(len);
        total += len;
    }
    if (total <= 0)
        return coords[0];
    let target = total * f;
    for (let i = 0; i < lengths.length; i++) {
        const len = lengths[i];
        if (target <= len) {
            const t = len <= 0 ? 0 : target / len;
            const [lonA, latA] = coords[i];
            const [lonB, latB] = coords[i + 1];
            return [lonA + (lonB - lonA) * t, latA + (latB - latA) * t];
        }
        target -= len;
    }
    return coords[coords.length - 1];
}
