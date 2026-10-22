/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 大屏右栏 · 决策计算摘要（Issue IKMS18 大屏监控平台化）。
//
// 口径（硬约束）：
//   · **前端不重算判级**——level / level_name / triggered_by / CI / 因素全部原样展示接口快照；
//   · 四档阈值来自 `GET /api/traffic/thresholds`，只做「当前值 vs 四档边界」的**展示对照**，
//     不据此推导等级（判级唯一实现是 work/perception/level.py，接口层也不重算）；
//   · 输入指标缺字段一律「—」，不编造；无快照记录时如实写「该路段无运行指标」；
//   · 详细演算过程不在这里复制一份：给「查看完整决策过程 →」深链到决策页（带 segment 参数）。
import { computed } from 'vue';
import { RouterLink } from 'vue-router';
import LevelBadge from './LevelBadge.vue';
import { ciAvailable, CI_DISCLAIMER, } from '../../../shared/traffic';
const { defineProps, } = {};
const props = defineProps();
function fmt(value, digits = 2) {
    return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—';
}
const inputRows = computed(() => {
    const r = props.record;
    return [
        { key: 'q', label: '流量 q', value: r ? `${fmt(r.q_vph, 0)} 辆/h` : '—' },
        { key: 'v', label: '车速 v', value: r ? `${fmt(r.v_kmh, 1)} km/h` : '—' },
        { key: 'k', label: '密度 k', value: r ? `${fmt(r.k_vpk, 1)} 辆/km` : '—' },
        { key: 'L_q', label: '排队 L_q', value: r ? `${fmt(r.L_q_m, 0)} m` : '—' },
        { key: 'x', label: '饱和度 x', value: r ? fmt(r.x) : '—' },
        { key: 'confidence', label: '置信度', value: r ? fmt(r.confidence) : '—' },
        { key: 'data_age', label: '数据年龄', value: r ? `${r.data_age_s ?? '—'} s` : '—' },
        { key: 'source', label: '来源', value: r?.source ?? '—' },
    ];
});
const dataAgeNote = computed(() => {
    const age = props.record?.data_age_s;
    if (!props.record)
        return '快照无该段记录 → 按「数据不可用」处理';
    if (typeof age !== 'number')
        return '数据年龄未知（缺字段）';
    return age > 120 ? `> 120 s 判陈旧（${age}s）` : '≤ 120 s（展示口径）';
});
const levelOf = computed(() => {
    const level = props.record?.level;
    return typeof level === 'number' && level >= 1 && level <= 4 ? level : null;
});
const levelText = computed(() => {
    if (!props.record)
        return '数据不可用（快照无该段记录）';
    if (!levelOf.value)
        return '数据不可用（上游未判级）';
    return props.record.level_name ?? '—';
});
const triggeredText = computed(() => {
    const list = props.record?.triggered_by;
    return Array.isArray(list) && list.length > 0 ? list.join(' / ') : '—';
});
const ciText = computed(() => {
    const r = props.record;
    return r && ciAvailable(r) ? r.ci.toFixed(1) : '不可用';
});
function numValue(value, unit = '') {
    if (typeof value !== 'number' || !Number.isFinite(value))
        return { value: null, text: '—' };
    return { value, text: `${fmt(value)}${unit ? ' ' + unit : ''}` };
}
function ratioValue(numerator, denominator) {
    if (typeof numerator !== 'number' ||
        typeof denominator !== 'number' ||
        !Number.isFinite(numerator) ||
        !Number.isFinite(denominator) ||
        denominator === 0) {
        return null;
    }
    return numerator / denominator;
}
/** 阈值行 label → 当前值（同时识别"原始量"与"比值"两种口径） */
function currentOfMetric(metric, unit) {
    const r = props.record;
    if (!r)
        return { value: null, text: '—' };
    if (metric.includes('饱和度') || metric === 'x')
        return numValue(r.x);
    if (metric.includes('速度比') || metric.includes('v/v_f'))
        return numValue(ratioValue(r.v_kmh, r.v_f_kmh));
    if (metric.includes('速度'))
        return numValue(r.v_kmh, unit);
    if (metric.includes('排队比') || metric.includes('L_q/L_seg'))
        return numValue(ratioValue(r.L_q_m, r.L_seg_m));
    if (metric.includes('排队长度') || metric.includes('L_q'))
        return numValue(r.L_q_m, unit);
    if (metric.includes('消散') || metric.includes('T_d'))
        return numValue(r.T_d_min, unit);
    if (metric.includes('密度') || metric === 'k')
        return numValue(r.k_vpk, unit);
    return { value: null, text: '—' };
}
const thresholdRows = computed(() => {
    const rows = props.thresholds?.rows ?? [];
    return rows.map((row) => {
        const unit = row.unit ?? '';
        const bands = (row.bands ?? []).filter((band) => band.level <= 3);
        return {
            metric: row.metric,
            unit,
            current: currentOfMetric(row.metric, unit),
            bounds: bands.map((band) => band.max),
            levels: (row.bands ?? []).map((band) => band.level),
        };
    });
});
/** 饱和度轨道的当前值位置（只算"值画在哪"，不做等级归类的结论文案） */
const xTrack = computed(() => {
    const row = thresholdRows.value.find((item) => item.metric.includes('饱和度') || item.metric === 'x');
    if (!row || row.current.value === null)
        return null;
    const lastBound = row.bounds[row.bounds.length - 1] ?? 1;
    const scaleMax = lastBound > 0 ? lastBound * 1.1 : 1;
    return { pct: Math.max(0, Math.min(100, (row.current.value / scaleMax) * 100)), bands: row };
});
const xSampleNote = computed(() => {
    const row = thresholdRows.value.find((item) => item.metric.includes('饱和度') || item.metric === 'x');
    if (!row)
        return '阈值未取到（/thresholds 未返回饱和度行）';
    const text = row.bounds.map((bound, index) => `${index + 1} 档 ≤ ${bound}`).join(' / ');
    return `四档边界（接口 /thresholds）：${text}${row.bounds.length === 3 ? ' / 4 档 > ' + row.bounds[2] : ''}`;
});
const thresholdsSource = computed(() => {
    const ts = props.thresholds?.ts;
    return ts ? `阈值快照 ${ts}` : '阈值未取到';
});
function targetLabel(target) {
    const map = {
        c: '通行能力',
        v_f: '畅通速度',
        demand: '需求',
        lanes: '车道数',
        confidence: '置信度',
    };
    return map[target] ?? target;
}
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
void __VLS_ctx, __VLS_components, __VLS_intrinsics, __VLS_directives;
// @ts-ignore
__VLS_withDotValue(levelOf, {});
// @ts-ignore
__VLS_withDotValue(thresholdRows, {});
// @ts-ignore
__VLS_withDotValue(xTrack, {});
void {};
/** @type {__VLS_StyleScopedClasses['band-seg']} */ ;
/** @type {__VLS_StyleScopedClasses['band-seg']} */ ;
/** @type {__VLS_StyleScopedClasses['band-cursor']} */ ;
/** @type {__VLS_StyleScopedClasses['th-table']} */ ;
/** @type {__VLS_StyleScopedClasses['th-table']} */ ;
/** @type {__VLS_StyleScopedClasses['th-table']} */ ;
/** @type {__VLS_StyleScopedClasses['in-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['deep-link']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
    ...{ class: "sum-card" },
});
/** @type {__VLS_StyleScopedClasses['sum-card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sec-head" },
});
/** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-chip warn" },
});
/** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['warn']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "sec-tag" },
});
/** @type {__VLS_StyleScopedClasses['sec-tag']} */ ;
if (!__VLS_ctx.record) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "empty sm" },
    });
    /** @type {__VLS_StyleScopedClasses['empty']} */ ;
    /** @type {__VLS_StyleScopedClasses['sm']} */ ;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "sub-head" },
    });
    /** @type {__VLS_StyleScopedClasses['sub-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "in-grid" },
    });
    /** @type {__VLS_StyleScopedClasses['in-grid']} */ ;
    const __VLS_0 = __VLS_tryAsConstant((__VLS_unwrap(inputRows, {})));
    for (const [row] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (row.key),
            ...{ class: "in-item" },
        });
        /** @type {__VLS_StyleScopedClasses['in-item']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "in-k" },
        });
        /** @type {__VLS_StyleScopedClasses['in-k']} */ ;
        (row.label);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "in-v td-num" },
        });
        /** @type {__VLS_StyleScopedClasses['in-v']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
        (row.value);
        // @ts-ignore
        [record, inputRows,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "tiny" },
    });
    /** @type {__VLS_StyleScopedClasses['tiny']} */ ;
    (__VLS_unwrap(dataAgeNote, {}));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "sep" },
    });
    /** @type {__VLS_StyleScopedClasses['sep']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "sub-head" },
    });
    /** @type {__VLS_StyleScopedClasses['sub-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "lv-row" },
    });
    /** @type {__VLS_StyleScopedClasses['lv-row']} */ ;
    if (levelOf.value) {
        const __VLS_1 = LevelBadge;
        // @ts-ignore
        const __VLS_2 = __VLS_asFunctionalComponent1(__VLS_1, new __VLS_1({
            // @ts-ignore
            level: (levelOf.value), stale: (__VLS_ctx.stale),
        }));
        const __VLS_3 = __VLS_2({
            level: (levelOf.value),
            stale: (__VLS_ctx.stale),
        }, ...__VLS_functionalComponentArgsRest(__VLS_2));
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "unavail" },
        });
        /** @type {__VLS_StyleScopedClasses['unavail']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "lv-text" },
    });
    /** @type {__VLS_StyleScopedClasses['lv-text']} */ ;
    (__VLS_unwrap(levelText, {}));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "sep" },
    });
    /** @type {__VLS_StyleScopedClasses['sep']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "tiny" },
    });
    /** @type {__VLS_StyleScopedClasses['tiny']} */ ;
    (__VLS_unwrap(triggeredText, {}));
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "tiny" },
    });
    /** @type {__VLS_StyleScopedClasses['tiny']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "sub-head" },
    });
    /** @type {__VLS_StyleScopedClasses['sub-head']} */ ;
    if (thresholdRows.value.length > 0) {
        if (xTrack.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "band-box" },
            });
            /** @type {__VLS_StyleScopedClasses['band-box']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "band-track" },
            });
            /** @type {__VLS_StyleScopedClasses['band-track']} */ ;
            const __VLS_6 = __VLS_tryAsConstant((xTrack.value.bands?.levels ?? []));
            for (const [level] of __VLS_vFor(__VLS_nonNull(__VLS_6))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    key: (level),
                    ...{ class: "band-seg" },
                    ...{ class: ({ hit: levelOf.value !== null && level === levelOf.value }) },
                });
                /** @type {__VLS_StyleScopedClasses['band-seg']} */ ;
                /** @type {__VLS_StyleScopedClasses['hit']} */ ;
                (level);
                // @ts-ignore
                [dataAgeNote, levelOf, levelOf, levelOf, levelOf, stale, levelText, triggeredText, thresholdRows, xTrack, xTrack,];
            }
            __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                ...{ class: "band-cursor" },
                ...{ style: ({ left: xTrack.value.pct + '%' }) },
                'aria-hidden': "true",
            });
            /** @type {__VLS_StyleScopedClasses['band-cursor']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "tiny" },
            });
            /** @type {__VLS_StyleScopedClasses['tiny']} */ ;
            (__VLS_unwrap(xSampleNote, {}));
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "sep" },
            });
            /** @type {__VLS_StyleScopedClasses['sep']} */ ;
            (fmt(__VLS_ctx.record.x));
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "tbl-scroll" },
        });
        /** @type {__VLS_StyleScopedClasses['tbl-scroll']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.table, __VLS_intrinsics.table)({
            ...{ class: "td-table th-table" },
        });
        /** @type {__VLS_StyleScopedClasses['td-table']} */ ;
        /** @type {__VLS_StyleScopedClasses['th-table']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.thead, __VLS_intrinsics.thead)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
            ...{ class: "num" },
        });
        /** @type {__VLS_StyleScopedClasses['num']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.tbody, __VLS_intrinsics.tbody)({});
        const __VLS_7 = __VLS_tryAsConstant((thresholdRows.value));
        for (const [row] of __VLS_vFor(__VLS_nonNull(__VLS_7))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({
                key: (row.metric),
            });
            __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
            (row.metric);
            __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                ...{ class: "num td-num" },
            });
            /** @type {__VLS_StyleScopedClasses['num']} */ ;
            /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
            (row.current.text);
            __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                ...{ class: "td-num" },
            });
            /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
            (row.bounds.length ? row.bounds.join(' / ') : '—');
            // @ts-ignore
            [record, thresholdRows, xTrack, xSampleNote,];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "tiny" },
        });
        /** @type {__VLS_StyleScopedClasses['tiny']} */ ;
        (__VLS_unwrap(thresholdsSource, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "sep" },
        });
        /** @type {__VLS_StyleScopedClasses['sep']} */ ;
        (__VLS_unwrap(CI_DISCLAIMER, {}));
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "empty sm" },
        });
        /** @type {__VLS_StyleScopedClasses['empty']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "sub-head" },
    });
    /** @type {__VLS_StyleScopedClasses['sub-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "sub-tag" },
    });
    /** @type {__VLS_StyleScopedClasses['sub-tag']} */ ;
    (__VLS_ctx.factors.length);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "sep" },
    });
    /** @type {__VLS_StyleScopedClasses['sep']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
        ...{ class: "td-num" },
    });
    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
    (__VLS_unwrap(ciText, {}));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "sub-tag" },
    });
    /** @type {__VLS_StyleScopedClasses['sub-tag']} */ ;
    if (__VLS_ctx.factors.length > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "fac-row" },
        });
        /** @type {__VLS_StyleScopedClasses['fac-row']} */ ;
        const __VLS_8 = __VLS_tryAsConstant((__VLS_ctx.factors));
        for (const [f] of __VLS_vFor(__VLS_nonNull(__VLS_8))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                key: (`${f.segment_id}-${f.factor_id}`),
                ...{ class: "fac" },
            });
            /** @type {__VLS_StyleScopedClasses['fac']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
            (f.factor_id);
            (f.name);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "sep" },
            });
            /** @type {__VLS_StyleScopedClasses['sep']} */ ;
            (targetLabel(f.target));
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "sep" },
            });
            /** @type {__VLS_StyleScopedClasses['sep']} */ ;
            (Number(f.multiplier.toFixed(2)));
            // @ts-ignore
            [thresholdsSource, CI_DISCLAIMER, factors, factors, factors, ciText,];
        }
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "tiny" },
        });
        /** @type {__VLS_StyleScopedClasses['tiny']} */ ;
    }
}
let __VLS_9;
/** @ts-ignore @type { | typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
RouterLink;
// @ts-ignore
const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
    // @ts-ignore
    ...{ class: "deep-link" }, to: ({ path: '/decision', query: { segment: __VLS_ctx.segmentId } }),
}));
const __VLS_11 = __VLS_10({
    ...{ class: "deep-link" },
    to: ({ path: '/decision', query: { segment: __VLS_ctx.segmentId } }),
}, ...__VLS_functionalComponentArgsRest(__VLS_10));
/** @type {__VLS_StyleScopedClasses['deep-link']} */ ;
const { default: __VLS_14 } = __VLS_nonNull(__VLS_12.slots);
// @ts-ignore
[segmentId,];
var __VLS_12;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "tiny deep-note" },
});
/** @type {__VLS_StyleScopedClasses['tiny']} */ ;
/** @type {__VLS_StyleScopedClasses['deep-note']} */ ;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
