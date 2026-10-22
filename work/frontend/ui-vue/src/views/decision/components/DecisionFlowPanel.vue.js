/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 决策可视化(Issue #77 三页收敛 · 决策层第二层的新视图)。
//
// 业主口径:「决策层我要看见**全部数据**和**处理数据的结果**,还有**可调控的全部可视化过程**,
// 差不多就是决策判断的可视化演示」。本面板按四段摆开:
//   ① **输入**   —— 选中路段的全部指标 + 生效因素 + 环境上下文(判级与决策实际吃进去的东西);
//   ② **处理过程** —— x = q_vph / c_vph 的逐步演算 → 四档阈值对比(当前值落在哪档、离边界多远)→ level;
//                    因素加权 → 通行能力折减 → x 前后对照;CI 四项加权构成;
//   ③ **可调控** —— 场景注入(环境侧)+ 人工置位(事件侧,在处置队列视图)+ 分流比例(在处置工作台),
//                    mock 模式由 mock 服务端重算并显示注入前后对照;真接口模式(traffic.py)只更新
//                    环境上下文 / 因素状态、**不重算判级 / CI**,面板如实显示「已注入 + 折算因素」;
//   ④ **输出**   —— 系统建议(承接段 / 比例 / 预期 / why)+ 预测三档。
//
// ⚠️ 口径铁律(违反即不通过):
//   ① 面板上每个数字都带单位或口径标注,取不到一律「—」,**绝不编造**;
//   ② 「处理过程」是**演示口径的演算展示**(阈值档位来自接口 /thresholds,不是前端自造),
//      不得说成"模型推理";真接口模式的判级来自上游链路 level 字段,接口层不重算(原样透传);
//   ③ CI 只用于展示与辅助排序,**不得作为判级依据**(手册 §6.5 第 1 条),冲突以四项指标为准;
//   ④ 全部 is_simulated = true。
import { computed } from 'vue';
import LevelBadge from '../../dashboard/components/LevelBadge.vue';
import FactorBreakdown from '../../dashboard/components/FactorBreakdown.vue';
import ScenarioInjectPanel from './ScenarioInjectPanel.vue';
import { ciAvailable, UNAVAILABLE, } from '../../../shared/traffic';
import { USE_MOCK } from '../../../shared/env';
const { defineProps, defineEmits, } = {};
const props = defineProps();
const emit = defineEmits();
function fmt(v, digits = 2) {
    return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—';
}
/** 环境上下文一行:真接口模式没有天气观测量 → 缺项一律「—」,不显示 "null℃ / 空单位" */
const weatherLine = computed(() => {
    const weather = props.ctx?.weather;
    if (!weather)
        return '—';
    const parts = [weather.condition ?? '天气未接入'];
    if (typeof weather.temp_c === 'number')
        parts.push(`${weather.temp_c}℃`);
    if (typeof weather.visibility_km === 'number')
        parts.push(`能见度 ${weather.visibility_km} km`);
    return parts.join(' · ');
});
/** 站点包是否给该路段预置了分流建议(base_pct > 0);未预置时比例仍可人工设置,不伪造建议 */
const hasSuggestion = computed(() => (props.suggestion?.base_pct ?? 0) > 0);
const inputRows = computed(() => {
    const r = props.record;
    if (!r)
        return [];
    return [
        { k: '流量 q', v: `${fmt(r.q_vph, 0)} 辆/h` },
        { k: '车速 v', v: `${fmt(r.v_kmh, 1)} km/h` },
        { k: '畅通速度 v_f', v: `${fmt(r.v_f_kmh, 1)} km/h` },
        // 密度直接用快照给的 `k_vpk`:本面板的口径是"把快照原样摆出来",不自己按 q / v 反算
        // (独立审查 Sourcery 提出:反算值会与快照 / 大屏上的 k 不一致,同一个字段两处两个数)
        { k: '密度 k', v: `${fmt(r.k_vpk, 1)} 辆/km` },
        { k: '排队长度 L_q', v: `${fmt(r.L_q_m, 0)} m` },
        { k: '路段长度 L_seg', v: `${fmt(r.L_seg_m, 0)} m` },
        { k: '消散时间 T_d', v: `${fmt(r.T_d_min, 1)} min` },
        { k: '通行能力 c', v: `${fmt(r.c_vph, 0)} 辆/h`, note: r.c_base_vph !== undefined ? `基准 ${r.c_base_vph} 辆/h` : undefined },
        { k: '饱和度 x', v: fmt(r.x) },
        { k: '检测置信度', v: fmt(r.confidence) },
        { k: '数据年龄', v: `${r.data_age_s ?? '—'} s`, note: '> 120 s 判陈旧(TC-11)' },
        { k: '来源', v: r.source },
    ];
});
// ---------- ② 处理过程:x = q / c 与四档阈值 ----------
/** 饱和度阈值档(来自 /thresholds;取不到用契约口径的演示值并注明) */
const xBands = computed(() => {
    const row = props.thresholds?.rows.find((r) => r.metric.includes('饱和度') || r.metric === 'x');
    return row?.bands ?? [];
});
const xValue = computed(() => (typeof props.record?.x === 'number' ? props.record.x : null));
/** 当前 x 落在哪一档 + 离下一档边界多远(展示口径的演算,不是模型) */
const xAnalysis = computed(() => {
    const x = xValue.value;
    const bands = xBands.value;
    if (x === null || bands.length === 0)
        return null;
    const hit = bands.find((b) => x <= b.max) ?? bands[bands.length - 1];
    const idx = bands.indexOf(hit);
    const next = bands[idx + 1];
    return {
        level: hit.level,
        upper: hit.max,
        /** 距本档上界(负数=已接近下一档) */
        margin: Number.isFinite(hit.max) ? hit.max - x : null,
        nextLevel: next?.level,
        nextBound: next?.max,
    };
});
/** 因素对通行能力 / 需求 / 置信度的合成折减(与 mock 同口径:相乘) */
const factorEffect = computed(() => {
    let c = 1;
    let q = 1;
    let conf = 1;
    for (const f of props.factors) {
        if (f.target === 'demand')
            q *= f.multiplier;
        else if (f.target === 'confidence')
            conf *= f.multiplier;
        else
            c *= f.multiplier;
    }
    return { c, q, conf, count: props.factors.length };
});
/** 未折减的通行能力(从 c 反推;用于展示"折减前 → 折减后") */
const cBeforeFactors = computed(() => {
    const r = props.record;
    if (!r || typeof r.c_vph !== 'number')
        return null;
    const m = factorEffect.value.c;
    return m > 0 ? r.c_vph / m : null;
});
/** CI 四项加权构成 */
const weights = computed(() => props.thresholds?.ci_weights ?? []);
const ciValue = computed(() => {
    const r = props.record;
    return r && ciAvailable(r) ? r.ci.toFixed(1) : UNAVAILABLE.name;
});
function ratio(a, b) {
    if (typeof a !== 'number' || typeof b !== 'number' || !Number.isFinite(a) || !Number.isFinite(b) || b === 0)
        return '—';
    return (a / b).toFixed(2);
}
function metricValue(key) {
    const r = props.record;
    if (!r)
        return '—';
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
/** 档位条上的位置(0~100%) */
function bandPos(x, max) {
    const top = Number.isFinite(max) && max > 0 ? max : 1;
    return `${Math.min(100, Math.max(0, (x / top) * 100))}%`;
}
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
__VLS_withDotValue(USE_MOCK, {});
// @ts-ignore
__VLS_withDotValue(factorEffect, {});
// @ts-ignore
__VLS_withDotValue(xAnalysis, {});
// @ts-ignore
__VLS_withDotValue(xValue, {});
// @ts-ignore
__VLS_withDotValue(UNAVAILABLE, {});
// @ts-ignore
__VLS_withDotValue(weights, {});
// @ts-ignore
__VLS_withDotValue(hasSuggestion, {});
void {};
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['step']} */ ;
/** @type {__VLS_StyleScopedClasses['band-seg']} */ ;
/** @type {__VLS_StyleScopedClasses['band-cursor']} */ ;
/** @type {__VLS_StyleScopedClasses['flow']} */ ;
/** @type {__VLS_StyleScopedClasses['step-body']} */ ;
/** @type {__VLS_StyleScopedClasses['step']} */ ;
/** @type {__VLS_StyleScopedClasses['ci-big']} */ ;
/** @type {__VLS_StyleScopedClasses['in-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['pred-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['band-track']} */ ;
/** @type {__VLS_StyleScopedClasses['in-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['ci-line']} */ ;
/** @type {__VLS_StyleScopedClasses['ci-big']} */ ;
/** @type {__VLS_StyleScopedClasses['band-seg']} */ ;
/** @type {__VLS_StyleScopedClasses['step-no']} */ ;
/** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pred-v']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flow" },
});
/** @type {__VLS_StyleScopedClasses['flow']} */ ;
if (!__VLS_ctx.record) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "empty" },
    });
    /** @type {__VLS_StyleScopedClasses['empty']} */ ;
}
else {
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
    (__VLS_ctx.record.segment_id);
    (__VLS_ctx.name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-body" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "in-grid" },
    });
    /** @type {__VLS_StyleScopedClasses['in-grid']} */ ;
    const __VLS_0 = __VLS_tryAsConstant((__VLS_unwrap(inputRows, {})));
    for (const [r] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (r.k),
            ...{ class: "in-cell" },
        });
        /** @type {__VLS_StyleScopedClasses['in-cell']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "in-k" },
        });
        /** @type {__VLS_StyleScopedClasses['in-k']} */ ;
        (r.k);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "in-v td-num" },
        });
        /** @type {__VLS_StyleScopedClasses['in-v']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
        (r.v);
        if (r.note) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "in-note" },
            });
            /** @type {__VLS_StyleScopedClasses['in-note']} */ ;
            (r.note);
        }
        // @ts-ignore
        [record, record, name, inputRows,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "sec-head" },
    });
    /** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "sub-tag" },
    });
    /** @type {__VLS_StyleScopedClasses['sub-tag']} */ ;
    (__VLS_ctx.factors.length);
    const __VLS_1 = FactorBreakdown;
    // @ts-ignore
    const __VLS_2 = __VLS_asFunctionalComponent1(__VLS_1, new __VLS_1({
        // @ts-ignore
        factors: (__VLS_ctx.factors),
    }));
    const __VLS_3 = __VLS_2({
        factors: (__VLS_ctx.factors),
    }, ...__VLS_functionalComponentArgsRest(__VLS_2));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "sec-head" },
    });
    /** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
    if (__VLS_ctx.ctx) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "ctx-line" },
        });
        /** @type {__VLS_StyleScopedClasses['ctx-line']} */ ;
        (__VLS_unwrap(weatherLine, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "sep" },
        });
        /** @type {__VLS_StyleScopedClasses['sep']} */ ;
        (__VLS_ctx.ctx.time.clock);
        (__VLS_ctx.ctx.time.session);
        (__VLS_ctx.ctx.time.calendar);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "sep" },
        });
        /** @type {__VLS_StyleScopedClasses['sep']} */ ;
        (__VLS_ctx.ctx.injected ? '已按演示场景注入' : (__VLS_ctx.ctx.scenario ? '未注入(无环境数据源)' : '站点包默认环境'));
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "empty sm" },
        });
        /** @type {__VLS_StyleScopedClasses['empty']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm']} */ ;
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
        ...{ class: "td-head-tag" },
    });
    /** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
    (USE_MOCK.value ? '非模型推理 · level.py 未实现' : '接口层不重算判级 · 快照原样展示');
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-body" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "step" },
    });
    /** @type {__VLS_StyleScopedClasses['step']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "step-no" },
    });
    /** @type {__VLS_StyleScopedClasses['step-no']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "step-body" },
    });
    /** @type {__VLS_StyleScopedClasses['step-body']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "step-title" },
    });
    /** @type {__VLS_StyleScopedClasses['step-title']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "step-line td-num" },
    });
    /** @type {__VLS_StyleScopedClasses['step-line']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
    (fmt(__VLS_unwrap(cBeforeFactors, {}), 0));
    (fmt(factorEffect.value.c, 2));
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    (fmt(__VLS_ctx.record.c_vph, 0));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "sep" },
    });
    /** @type {__VLS_StyleScopedClasses['sep']} */ ;
    (fmt(factorEffect.value.q, 2));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "sep" },
    });
    /** @type {__VLS_StyleScopedClasses['sep']} */ ;
    (fmt(factorEffect.value.conf, 2));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "step-note" },
    });
    /** @type {__VLS_StyleScopedClasses['step-note']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "step" },
    });
    /** @type {__VLS_StyleScopedClasses['step']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "step-no" },
    });
    /** @type {__VLS_StyleScopedClasses['step-no']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "step-body" },
    });
    /** @type {__VLS_StyleScopedClasses['step-body']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "step-title" },
    });
    /** @type {__VLS_StyleScopedClasses['step-title']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "step-line td-num" },
    });
    /** @type {__VLS_StyleScopedClasses['step-line']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
    (fmt(__VLS_ctx.record.q_vph, 0));
    (fmt(__VLS_ctx.record.c_vph, 0));
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    (fmt(__VLS_ctx.record.x));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "step" },
    });
    /** @type {__VLS_StyleScopedClasses['step']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "step-no" },
    });
    /** @type {__VLS_StyleScopedClasses['step-no']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "step-body" },
    });
    /** @type {__VLS_StyleScopedClasses['step-body']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "step-title" },
    });
    /** @type {__VLS_StyleScopedClasses['step-title']} */ ;
    if (xAnalysis.value && xValue.value !== null) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "band-track" },
        });
        /** @type {__VLS_StyleScopedClasses['band-track']} */ ;
        const __VLS_6 = __VLS_tryAsConstant((__VLS_unwrap(xBands, {})));
        for (const [b] of __VLS_vFor(__VLS_nonNull(__VLS_6))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                key: (b.level),
                ...{ class: "band-seg" },
                ...{ class: ({ hit: b.level === xAnalysis.value.level }) },
            });
            /** @type {__VLS_StyleScopedClasses['band-seg']} */ ;
            /** @type {__VLS_StyleScopedClasses['hit']} */ ;
            (b.level);
            (Number.isFinite(b.max) ? b.max : '∞');
            // @ts-ignore
            [record, record, record, record, factors, factors, ctx, ctx, ctx, ctx, ctx, ctx, weatherLine, USE_MOCK, cBeforeFactors, factorEffect, factorEffect, factorEffect, xAnalysis, xAnalysis, xValue, xBands,];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
            ...{ class: "band-cursor" },
            ...{ style: ({ left: bandPos(xValue.value, xAnalysis.value.upper) }) },
        });
        /** @type {__VLS_StyleScopedClasses['band-cursor']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "step-line" },
        });
        /** @type {__VLS_StyleScopedClasses['step-line']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
            ...{ class: "td-num" },
        });
        /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
        (fmt(xValue.value));
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
        (xAnalysis.value.level);
        if (xAnalysis.value.margin !== null) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "sep" },
            });
            /** @type {__VLS_StyleScopedClasses['sep']} */ ;
            (xAnalysis.value.upper);
            __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
                ...{ class: "td-num" },
            });
            /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
            (fmt(xAnalysis.value.margin));
        }
        if (xAnalysis.value.nextBound !== undefined) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "sep" },
            });
            /** @type {__VLS_StyleScopedClasses['sep']} */ ;
            (xAnalysis.value.nextLevel);
            (xAnalysis.value.nextBound);
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "step-line" },
        });
        /** @type {__VLS_StyleScopedClasses['step-line']} */ ;
        const __VLS_7 = LevelBadge;
        // @ts-ignore
        const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
            // @ts-ignore
            level: (__VLS_ctx.record.level),
        }));
        const __VLS_9 = __VLS_8({
            level: (__VLS_ctx.record.level),
        }, ...__VLS_functionalComponentArgsRest(__VLS_8));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "sep" },
        });
        /** @type {__VLS_StyleScopedClasses['sep']} */ ;
        (__VLS_ctx.record.level);
        (USE_MOCK.value ? '(站点包预置,判级模型未落地)' : '(判级来自上游链路 level 字段,接口层不重算)');
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "empty sm" },
        });
        /** @type {__VLS_StyleScopedClasses['empty']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "step" },
    });
    /** @type {__VLS_StyleScopedClasses['step']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "step-no" },
    });
    /** @type {__VLS_StyleScopedClasses['step-no']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "step-body" },
    });
    /** @type {__VLS_StyleScopedClasses['step-body']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "step-title" },
    });
    /** @type {__VLS_StyleScopedClasses['step-title']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "ci-line" },
    });
    /** @type {__VLS_StyleScopedClasses['ci-line']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "ci-big td-num" },
        ...{ style: ({ color: __VLS_unwrap(ciAvailable, {})(__VLS_ctx.record) ? undefined : UNAVAILABLE.value.color }) },
    });
    /** @type {__VLS_StyleScopedClasses['ci-big']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
    (__VLS_unwrap(ciValue, {}));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "ci-formula td-mono" },
    });
    /** @type {__VLS_StyleScopedClasses['ci-formula']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
    if (weights.value.length > 0) {
        (weights.value.map((w) => `${w.label} ${metricValue(w.key)}×${w.weight.toFixed(2)}`).join(' + '));
    }
    else {
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "step-note" },
    });
    /** @type {__VLS_StyleScopedClasses['step-note']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
        ...{ class: "td-card" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-head" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
    (USE_MOCK.value ? '③ 可调控 · 改任一项,服务端重算判级 / CI / 建议 / 预测' : '③ 可调控 · 改任一项只更新环境上下文 / 因素状态（判级由感知层统一重算）');
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-body" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
    const __VLS_12 = ScenarioInjectPanel;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent1(__VLS_12, new __VLS_12({
        // @ts-ignore
        ...{ 'onChanged': {} }, ctx: (__VLS_ctx.ctx), segmentId: (__VLS_ctx.record.segment_id), presets: (__VLS_ctx.presets),
    }));
    const __VLS_14 = __VLS_13({
        ...{ 'onChanged': {} },
        ctx: (__VLS_ctx.ctx),
        segmentId: (__VLS_ctx.record.segment_id),
        presets: (__VLS_ctx.presets),
    }, ...__VLS_functionalComponentArgsRest(__VLS_13));
    let __VLS_17;
    const __VLS_18 = {
        /** @type {typeof __VLS_17.changed} */
        onChanged: // @ts-ignore
        (...[$event]) => {
            void $event;
            if (!!(!__VLS_ctx.record))
                throw 0;
            return (__VLS_unwrap(emit, {})('changed'));
            // @ts-ignore
            [record, record, record, record, ctx, USE_MOCK, USE_MOCK, xAnalysis, xAnalysis, xAnalysis, xAnalysis, xAnalysis, xAnalysis, xAnalysis, xAnalysis, xValue, xValue, ciAvailable, UNAVAILABLE, ciValue, weights, weights, presets, emit,];
        },
    };
    void __VLS_18;
    var __VLS_15;
    var __VLS_16;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "note" },
    });
    /** @type {__VLS_StyleScopedClasses['note']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
        ...{ class: "td-card" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-head" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-body" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
    if (__VLS_ctx.suggestion && hasSuggestion.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "out-line" },
        });
        /** @type {__VLS_StyleScopedClasses['out-line']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
        (__VLS_ctx.suggestion.target_name);
        (__VLS_ctx.suggestion.target_segment_id);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "sep" },
        });
        /** @type {__VLS_StyleScopedClasses['sep']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
        (__VLS_ctx.suggestion.base_pct);
        (__VLS_ctx.suggestion.min_pct);
        (__VLS_ctx.suggestion.max_pct);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "sep" },
        });
        /** @type {__VLS_StyleScopedClasses['sep']} */ ;
        (__VLS_ctx.suggestion.expect);
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "why" },
        });
        /** @type {__VLS_StyleScopedClasses['why']} */ ;
        (__VLS_ctx.suggestion.why);
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
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "out-line" },
    });
    /** @type {__VLS_StyleScopedClasses['out-line']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "sec-head" },
    });
    /** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "sub-tag" },
    });
    /** @type {__VLS_StyleScopedClasses['sub-tag']} */ ;
    if (__VLS_ctx.record.pred) {
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
        (__VLS_ctx.record.pred.h15.q_vph);
        const __VLS_19 = LevelBadge;
        // @ts-ignore
        const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
            // @ts-ignore
            level: (__VLS_ctx.record.pred.h15.level),
        }));
        const __VLS_21 = __VLS_20({
            level: (__VLS_ctx.record.pred.h15.level),
        }, ...__VLS_functionalComponentArgsRest(__VLS_20));
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
        (__VLS_ctx.record.pred.h30.q_vph);
        const __VLS_24 = LevelBadge;
        // @ts-ignore
        const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
            // @ts-ignore
            level: (__VLS_ctx.record.pred.h30.level),
        }));
        const __VLS_26 = __VLS_25({
            level: (__VLS_ctx.record.pred.h30.level),
        }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "empty sm" },
        });
        /** @type {__VLS_StyleScopedClasses['empty']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm']} */ ;
    }
}
// @ts-ignore
[record, record, record, record, record, suggestion, suggestion, suggestion, suggestion, suggestion, suggestion, suggestion, suggestion, hasSuggestion,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
