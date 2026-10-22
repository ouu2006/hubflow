/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 路段 × 时间热力矩阵:每行 = 一个路段,每列 = 一个时间桶(labels),
// 格子色 = ciColor(v)（拥堵版）/ 流量档位色（流量版, Issue IKNB9G）;
// null(该桶数据不可用 / 流量版只给当前快照)= 灰 #8B8B8B(绝不用 0 冒充)。
import { ciColor, UNAVAILABLE } from '../../../shared/traffic';
import { flowBandOfQ } from '../../../shared/flow';
const { defineProps, withDefaults, } = {};
const props = withDefaults(defineProps(), { mode: 'ci' });
function cellColor(v) {
    if (v === null)
        return UNAVAILABLE.color;
    if (props.mode === 'flow')
        return flowBandOfQ(v)?.color ?? UNAVAILABLE.color;
    return ciColor(v);
}
function cellTitle(label, v) {
    if (v === null)
        return `${label} · ${props.mode === 'flow' ? '无流量数据（该桶未提供 q）' : '数据不可用'}`;
    return props.mode === 'flow' ? `${label} · q ${v.toFixed(0)} 辆/h` : `${label} · CI ${v.toFixed(1)}`;
}
const __VLS_defaults = { mode: 'ci' };
void __VLS_defaults;
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
void __VLS_ctx, __VLS_components, __VLS_intrinsics, __VLS_directives;
void {};
/** @type {__VLS_StyleScopedClasses['hm-lab']} */ ;
/** @type {__VLS_StyleScopedClasses['hm']} */ ;
/** @type {__VLS_StyleScopedClasses['hm-row']} */ ;
/** @type {__VLS_StyleScopedClasses['hm-name']} */ ;
/** @type {__VLS_StyleScopedClasses['hm']} */ ;
/** @type {__VLS_StyleScopedClasses['hm-row']} */ ;
if (__VLS_ctx.matrix) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "hm td-scroll" },
    });
    /** @type {__VLS_StyleScopedClasses['hm']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-scroll']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "hm-row hm-head" },
    });
    /** @type {__VLS_StyleScopedClasses['hm-row']} */ ;
    /** @type {__VLS_StyleScopedClasses['hm-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "hm-name" },
    });
    /** @type {__VLS_StyleScopedClasses['hm-name']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "hm-cells" },
    });
    /** @type {__VLS_StyleScopedClasses['hm-cells']} */ ;
    const __VLS_0 = __VLS_tryAsConstant((__VLS_ctx.matrix.labels));
    for (const [l, i] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.i, __VLS_intrinsics.i)({
            key: (i),
            ...{ class: "hm-lab" },
        });
        /** @type {__VLS_StyleScopedClasses['hm-lab']} */ ;
        (l.slice(0, 5));
        // @ts-ignore
        [matrix, matrix,];
    }
    const __VLS_1 = __VLS_tryAsConstant((__VLS_ctx.matrix.rows));
    for (const [row] of __VLS_vFor(__VLS_nonNull(__VLS_1))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (row.segment_id),
            ...{ class: "hm-row" },
        });
        /** @type {__VLS_StyleScopedClasses['hm-row']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "hm-name" },
        });
        /** @type {__VLS_StyleScopedClasses['hm-name']} */ ;
        (row.name);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "hm-cells" },
        });
        /** @type {__VLS_StyleScopedClasses['hm-cells']} */ ;
        const __VLS_2 = __VLS_tryAsConstant((row.buckets));
        for (const [v, i] of __VLS_vFor(__VLS_nonNull(__VLS_2))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.i)({
                key: (i),
                ...{ class: "hm-cell" },
                ...{ style: ({ background: cellColor(v) }) },
                title: (cellTitle(__VLS_ctx.matrix.labels[i] ?? '', v)),
            });
            /** @type {__VLS_StyleScopedClasses['hm-cell']} */ ;
            // @ts-ignore
            [matrix, matrix,];
        }
        // @ts-ignore
        [];
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "hm-empty" },
    });
    /** @type {__VLS_StyleScopedClasses['hm-empty']} */ ;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __defaults: __VLS_defaults,
    __typeProps: {},
});
export default {};
