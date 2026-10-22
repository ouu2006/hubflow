/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 环境上下文条(Issue #77 三页收敛 · 感知层第一层)。
//
// 为什么放在感知层:业主口径——感知层放「能获取的数据」,天气 / 时间 / 因地制宜的路况正是环境侧的
// 可获取输入(手册第 19 章因素登记表 F01 天气 / F02 昼夜 / F03 列车到发 / F10 时段日历)。
//
// ⚠️ 口径铁律(违反即不通过):
//   ① **全部是编造的演示值**(真实气象与列车数据拿不到),卡片头必须常驻「演示数据(模拟)」;
//   ② 页面**不出现**「实测 / 实时 / 现场」表述;
//   ③ `derived_factors` 是**当前真实生效**的环境因素(默认态 = 站点包声明的那套环境,
//      `injected = false`;被场景注入改过则 `injected = true`)——两种状态分开显示,
//      不得把"站点包默认环境"说成"注入的"、也不得把观测值说成"未生效"。
import { UNAVAILABLE } from '../../../shared/traffic';
const { defineProps, } = {};
const __VLS_props = defineProps();
const TARGET_LABEL = {
    c: '通行能力',
    v_f: '畅通速度',
    demand: '需求',
    lanes: '车道数',
    confidence: '检测置信度',
};
function multText(m) {
    return `×${Number.isFinite(m) ? Number(m.toFixed(2)) : '—'}`;
}
/** 观测值缺失 → 「—」（不显示成 "null" / 空单位；真接口模式天气观测量本就没有数据源） */
function unitText(value, unit) {
    return typeof value === 'number' && Number.isFinite(value) ? `${value} ${unit}` : '—';
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
__VLS_withDotValue(TARGET_LABEL, {});
// @ts-ignore
__VLS_withDotValue(UNAVAILABLE, {});
void {};
/** @type {__VLS_StyleScopedClasses['env-block']} */ ;
/** @type {__VLS_StyleScopedClasses['env-block']} */ ;
/** @type {__VLS_StyleScopedClasses['grow']} */ ;
/** @type {__VLS_StyleScopedClasses['env-block']} */ ;
/** @type {__VLS_StyleScopedClasses['grow']} */ ;
/** @type {__VLS_StyleScopedClasses['env-title']} */ ;
/** @type {__VLS_StyleScopedClasses['env-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['env-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['env-body']} */ ;
/** @type {__VLS_StyleScopedClasses['env-block']} */ ;
/** @type {__VLS_StyleScopedClasses['env-block']} */ ;
/** @type {__VLS_StyleScopedClasses['grow']} */ ;
/** @type {__VLS_StyleScopedClasses['env-block']} */ ;
/** @type {__VLS_StyleScopedClasses['grow']} */ ;
/** @type {__VLS_StyleScopedClasses['env-title']} */ ;
/** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['env-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['v']} */ ;
/** @type {__VLS_StyleScopedClasses['env-err']} */ ;
/** @type {__VLS_StyleScopedClasses['env-note']} */ ;
/** @type {__VLS_StyleScopedClasses['env-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['env-body']} */ ;
/** @type {__VLS_StyleScopedClasses['env-block']} */ ;
/** @type {__VLS_StyleScopedClasses['env-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['env-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['k']} */ ;
/** @type {__VLS_StyleScopedClasses['env-note']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
    ...{ class: "td-card env-bar" },
});
/** @type {__VLS_StyleScopedClasses['td-card']} */ ;
/** @type {__VLS_StyleScopedClasses['env-bar']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-head" },
});
/** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-head-tag" },
});
/** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-chip warn" },
});
/** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['warn']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-body env-body" },
});
/** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
/** @type {__VLS_StyleScopedClasses['env-body']} */ ;
if (__VLS_ctx.error) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "env-err" },
    });
    /** @type {__VLS_StyleScopedClasses['env-err']} */ ;
    (__VLS_ctx.error);
}
else if (__VLS_ctx.ctx) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "env-block" },
    });
    /** @type {__VLS_StyleScopedClasses['env-block']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "env-title" },
    });
    /** @type {__VLS_StyleScopedClasses['env-title']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "env-kv" },
    });
    /** @type {__VLS_StyleScopedClasses['env-kv']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "k" },
    });
    /** @type {__VLS_StyleScopedClasses['k']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "v" },
    });
    /** @type {__VLS_StyleScopedClasses['v']} */ ;
    (__VLS_ctx.ctx.weather.condition ?? '—');
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "env-kv" },
    });
    /** @type {__VLS_StyleScopedClasses['env-kv']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "k" },
    });
    /** @type {__VLS_StyleScopedClasses['k']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "v td-num" },
    });
    /** @type {__VLS_StyleScopedClasses['v']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
    (unitText(__VLS_ctx.ctx.weather.temp_c, '℃'));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "env-kv" },
    });
    /** @type {__VLS_StyleScopedClasses['env-kv']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "k" },
    });
    /** @type {__VLS_StyleScopedClasses['k']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "v td-num" },
    });
    /** @type {__VLS_StyleScopedClasses['v']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
    (unitText(__VLS_ctx.ctx.weather.humidity_pct, '%'));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "env-kv" },
    });
    /** @type {__VLS_StyleScopedClasses['env-kv']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "k" },
    });
    /** @type {__VLS_StyleScopedClasses['k']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "v td-num" },
    });
    /** @type {__VLS_StyleScopedClasses['v']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
    (unitText(__VLS_ctx.ctx.weather.visibility_km, 'km'));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "env-kv" },
    });
    /** @type {__VLS_StyleScopedClasses['env-kv']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "k" },
    });
    /** @type {__VLS_StyleScopedClasses['k']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "v td-num" },
    });
    /** @type {__VLS_StyleScopedClasses['v']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
    (unitText(__VLS_ctx.ctx.weather.precip_mm, 'mm'));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "env-kv" },
    });
    /** @type {__VLS_StyleScopedClasses['env-kv']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "k" },
    });
    /** @type {__VLS_StyleScopedClasses['k']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "v" },
    });
    /** @type {__VLS_StyleScopedClasses['v']} */ ;
    (__VLS_ctx.ctx.weather.wind ?? '—');
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "env-block" },
    });
    /** @type {__VLS_StyleScopedClasses['env-block']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "env-title" },
    });
    /** @type {__VLS_StyleScopedClasses['env-title']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "env-kv" },
    });
    /** @type {__VLS_StyleScopedClasses['env-kv']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "k" },
    });
    /** @type {__VLS_StyleScopedClasses['k']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "v td-mono" },
    });
    /** @type {__VLS_StyleScopedClasses['v']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
    (__VLS_ctx.ctx.time.clock);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "env-kv" },
    });
    /** @type {__VLS_StyleScopedClasses['env-kv']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "k" },
    });
    /** @type {__VLS_StyleScopedClasses['k']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "v" },
    });
    /** @type {__VLS_StyleScopedClasses['v']} */ ;
    (__VLS_ctx.ctx.time.session);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "env-kv" },
    });
    /** @type {__VLS_StyleScopedClasses['env-kv']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "k" },
    });
    /** @type {__VLS_StyleScopedClasses['k']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "v" },
    });
    /** @type {__VLS_StyleScopedClasses['v']} */ ;
    (__VLS_ctx.ctx.time.calendar);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "env-kv" },
    });
    /** @type {__VLS_StyleScopedClasses['env-kv']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "k" },
    });
    /** @type {__VLS_StyleScopedClasses['k']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "v td-mono" },
    });
    /** @type {__VLS_StyleScopedClasses['v']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
    (__VLS_ctx.ctx.time.next_train ?? '—');
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "env-block grow" },
    });
    /** @type {__VLS_StyleScopedClasses['env-block']} */ ;
    /** @type {__VLS_StyleScopedClasses['grow']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "env-title" },
    });
    /** @type {__VLS_StyleScopedClasses['env-title']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-chip" },
        ...{ class: (__VLS_ctx.ctx.injected ? 'ok' : '') },
    });
    /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
    (__VLS_ctx.ctx.injected ? '已按演示场景注入' : '站点包默认环境');
    if (__VLS_ctx.ctx.derived_factors.length > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "fac-row" },
        });
        /** @type {__VLS_StyleScopedClasses['fac-row']} */ ;
        const __VLS_0 = __VLS_tryAsConstant((__VLS_ctx.ctx.derived_factors));
        for (const [f] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                key: (f.factor_id),
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
            (TARGET_LABEL.value[f.target] ?? f.target);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "sep" },
            });
            /** @type {__VLS_StyleScopedClasses['sep']} */ ;
            (multText(f.multiplier));
            // @ts-ignore
            [error, error, ctx, ctx, ctx, ctx, ctx, ctx, ctx, ctx, ctx, ctx, ctx, ctx, ctx, ctx, ctx, TARGET_LABEL,];
        }
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "env-none" },
        });
        /** @type {__VLS_StyleScopedClasses['env-none']} */ ;
    }
    if (__VLS_ctx.ctx.injected) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "env-none" },
        });
        /** @type {__VLS_StyleScopedClasses['env-none']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "env-sum" },
    });
    /** @type {__VLS_StyleScopedClasses['env-sum']} */ ;
    (__VLS_ctx.ctx.summary);
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "env-none" },
    });
    /** @type {__VLS_StyleScopedClasses['env-none']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "env-note" },
});
/** @type {__VLS_StyleScopedClasses['env-note']} */ ;
if (__VLS_ctx.ctx) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (__VLS_ctx.ctx.source);
}
if (__VLS_ctx.ctx && !__VLS_ctx.ctx.injected) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.i)({
        ...{ class: "sw" },
        ...{ style: ({ background: UNAVAILABLE.value.color }) },
    });
    /** @type {__VLS_StyleScopedClasses['sw']} */ ;
}
// @ts-ignore
[ctx, ctx, ctx, ctx, ctx, ctx, UNAVAILABLE,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
