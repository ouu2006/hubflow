/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// CI 走势 · 近 12 期:竖向色块(色 = ciColor),底部对齐;叠加 65 / 85 阈值虚线。
import { ciColor } from '../../../shared/traffic';
const { defineProps, } = {};
const __VLS_props = defineProps();
function pct(ci) {
    return `${Math.min(100, Math.max(2, ci))}%`;
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
void {};
/** @type {__VLS_StyleScopedClasses['plot']} */ ;
/** @type {__VLS_StyleScopedClasses['bar']} */ ;
if (__VLS_ctx.history) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "trend" },
    });
    /** @type {__VLS_StyleScopedClasses['trend']} */ ;
    if (__VLS_ctx.history.points.length > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "plot" },
        });
        /** @type {__VLS_StyleScopedClasses['plot']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
            ...{ class: "thr" },
            ...{ style: ({ bottom: '65%' }) },
        });
        /** @type {__VLS_StyleScopedClasses['thr']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
            ...{ class: "thr" },
            ...{ style: ({ bottom: '85%' }) },
        });
        /** @type {__VLS_StyleScopedClasses['thr']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "bars" },
        });
        /** @type {__VLS_StyleScopedClasses['bars']} */ ;
        const __VLS_0 = __VLS_tryAsConstant((__VLS_ctx.history.points));
        for (const [p, i] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                key: (i),
                ...{ class: "bar" },
                ...{ style: ({ height: pct(p.ci), background: __VLS_unwrap(ciColor, {})(p.ci) }) },
                title: (`${p.ts} · CI ${p.ci}`),
            });
            /** @type {__VLS_StyleScopedClasses['bar']} */ ;
            // @ts-ignore
            [history, history, history, ciColor,];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "axis" },
        });
        /** @type {__VLS_StyleScopedClasses['axis']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (__VLS_ctx.history.min === null ? '—' : __VLS_ctx.history.min.toFixed(1));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (__VLS_ctx.history.max === null ? '—' : __VLS_ctx.history.max.toFixed(1));
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "trend-empty" },
        });
        /** @type {__VLS_StyleScopedClasses['trend-empty']} */ ;
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "trend-empty" },
    });
    /** @type {__VLS_StyleScopedClasses['trend-empty']} */ ;
}
// @ts-ignore
[history, history, history, history,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
