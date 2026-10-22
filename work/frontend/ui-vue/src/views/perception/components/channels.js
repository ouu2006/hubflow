import { activePack } from '../../../station-packs/index.ts';
import { CLASS_COLORS } from '../../../shared/theme';
/**
 * 当前站点包的通道映射。
 * 取值函数而不是常量:本模块在 `import` 阶段就被求值,而包键是入口在挂载前注入的。
 */
export function channels() {
    return activePack().channels.map((c) => ({
        cid: c.cid,
        source: c.source,
        name: c.name,
        segmentId: c.segment_id,
        // 不写 `hasVideo` 的老包 = true(既有行为:有样本视频,能不能读看服务端)
        hasVideo: c.hasVideo !== false,
    }));
}
/** 越线计数线位置(归一化画面高度;手册/设计稿口径 line_position = 0.62) */
export const COUNT_LINE_POS = 0.62;
/** 四分的文字 + 样式类(全页同口径:台账 / 监控墙 / 详情 / 供给对照共用) */
export const FEED_TEXT = {
    'no-source': { text: '未接入视频源', cls: 'out' },
    unexported: { text: '未导出', cls: 'out' },
    failed: { text: '检测读取失败', cls: 'err' },
    ok: { text: '已导出', cls: 'ok' },
};
/** 判定顺序:包说没视频源 → 那一档;否则看服务端返回(未导出 / 读取失败 / 已导出) */
export function feedOf(c) {
    if (!c.def.hasVideo)
        return 'no-source';
    if (c.meta === null)
        return 'unexported';
    if (c.detFailed)
        return 'failed';
    return 'ok';
}
/** 四分的文字(便捷取用) */
export function feedText(c) {
    return FEED_TEXT[feedOf(c)];
}
/** 车型槽位短名(画面区/图例用,与 DESIGN 的四槽口径一致) */
export const CLASS_SHORT = {
    car: 'car',
    van: 'van',
    bus: 'bus',
    truck: 'truck',
};
/** 图例全名(设计稿 04:car 私家车 / van 面包车 / bus 大巴 / truck 货车) */
export const CLASS_LABEL = {
    car: 'car 私家车',
    van: 'van 面包车',
    bus: 'bus 大巴',
    truck: 'truck 货车',
};
export const CLASS_KEYS = ['car', 'van', 'bus', 'truck'];
/**
 * 类别 → 车型槽位(class_names 语义映射;行人等非车辆返回 null)。
 * 口径:小汽车=car / 货车=truck / 公交车=bus / 摩托车·自行车=van(设计稿四槽)。
 */
export function vehicleKeyOf(classId, className) {
    if (classId === 2 || className.includes('小汽车'))
        return 'car';
    if (classId === 7 || className.includes('货车'))
        return 'truck';
    if (classId === 5 || className.includes('公交车'))
        return 'bus';
    if (classId === 1 || classId === 3 || className.includes('摩托') || className.includes('自行车')) {
        return 'van';
    }
    return null;
}
/** 检测框颜色:车辆类别取车型色;非车辆类别交中性灰(不借车型色,也不使用等级四级色) */
export function classColorOf(classId, className) {
    const key = vehicleKeyOf(classId, className);
    return key ? CLASS_COLORS[key] : '#9E9E9E';
}
/** ≤ i 的最近检测帧(二分;与旧页同口径,回退 / 跳转 / 抽帧都稳) */
export function frameAt(det, i) {
    if (!det || det.frames.length === 0)
        return null;
    const arr = det.frames;
    let lo = 0;
    let hi = arr.length - 1;
    let ans = -1;
    while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        const el = arr[mid];
        if (el && el.i <= i) {
            ans = mid;
            lo = mid + 1;
        }
        else {
            hi = mid - 1;
        }
    }
    if (ans < 0)
        return null;
    return arr[ans]?.det ?? null;
}
/** 当前帧按车型分组计数(只出四个车型槽;非车辆类别单独计) */
export function classCountsOf(dets, classNames) {
    const acc = new Map();
    if (dets) {
        for (const d of dets) {
            const cls = d[4] ?? 0;
            const name = classNames[String(cls)] ?? `类${cls}`;
            const key = vehicleKeyOf(cls, name);
            if (key)
                acc.set(key, (acc.get(key) ?? 0) + 1);
        }
    }
    return CLASS_KEYS.filter((k) => (acc.get(k) ?? 0) > 0).map((k) => ({
        key: k,
        short: CLASS_SHORT[k],
        count: acc.get(k) ?? 0,
    }));
}
/** 当前帧轨迹数(不重复 track_id) */
export function trackCountOf(dets) {
    if (!dets)
        return 0;
    const ids = new Set();
    for (const d of dets)
        ids.add(d[6]);
    return ids.size;
}
/**
 * 累计轨迹按车型分组 —— 口径取自 detections.first_seen 的 class 字段(旧页成熟口径),
 * 不是把逐帧框数累加(那会把同一辆车的多帧重复计数)。
 */
export function cumClassCounts(det, classNames) {
    const byKey = new Map();
    let other = 0;
    let total = 0;
    if (det) {
        for (const v of Object.values(det.first_seen)) {
            total += 1;
            const name = classNames[String(v.class)] ?? `类${v.class}`;
            const key = vehicleKeyOf(v.class, name);
            if (key)
                byKey.set(key, (byKey.get(key) ?? 0) + 1);
            else
                other += 1;
        }
    }
    return { byKey, other, total };
}
/** 秒 → mm:ss(mm:ss 时长展示,不引入任何示例数值) */
export function fmtDur(seconds) {
    if (seconds === null || !Number.isFinite(seconds))
        return '—';
    const s = Math.max(0, Math.round(seconds));
    const m = Math.floor(s / 60);
    return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}
/** 分辨率 + 帧率 + 时长 + 轨迹/检测(全部来自 meta;该路未导出则统计列显示「—」) */
export function metaLine(meta, detTotal) {
    if (!meta)
        return '—';
    const parts = [
        `${meta.width}×${meta.height}`,
        `${meta.fps} fps`,
        fmtDur(meta.duration_s),
        `轨迹 ${meta.track_total}`,
        `检测 ${detTotal === null ? '—' : detTotal}`,
    ];
    return parts.join(' · ');
}
