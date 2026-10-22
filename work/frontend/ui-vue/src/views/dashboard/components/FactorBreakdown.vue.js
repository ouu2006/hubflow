/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
const { defineProps, } = {};
const __VLS_props = defineProps();
const MANUAL_FACTOR_IDS = new Set(['F07', 'F08', 'F11']);
function isManual(factorId) {
    return MANUAL_FACTOR_IDS.has(factorId);
}
function multText(m) {
    return `${m >= 1 ? '+' : ''}${m}`;
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
/** @type {__VLS_StyleScopedClasses['tag']} */ ;
/** @type {__VLS_StyleScopedClasses['tag']} */ ;
/** @type {__VLS_StyleScopedClasses['fac-row']} */ ;
/** @type {__VLS_StyleScopedClasses['fac-name']} */ ;
/** @type {__VLS_StyleScopedClasses['fac-m']} */ ;
if (__VLS_ctx.factors.length > 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "fac" },
    });
    /** @type {__VLS_StyleScopedClasses['fac']} */ ;
    const __VLS_0 = __VLS_tryAsConstant((__VLS_ctx.factors));
    for (const [f] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (f.factor_id),
            ...{ class: "fac-row" },
        });
        /** @type {__VLS_StyleScopedClasses['fac-row']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "fac-id td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['fac-id']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (f.factor_id);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "fac-name" },
        });
        /** @type {__VLS_StyleScopedClasses['fac-name']} */ ;
        (f.name);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "tag" },
            ...{ class: (isManual(f.factor_id) ? 'manual' : 'auto') },
        });
        /** @type {__VLS_StyleScopedClasses['tag']} */ ;
        (isManual(f.factor_id) ? '人工' : '自动');
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "fac-m td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['fac-m']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (multText(f.multiplier));
        // @ts-ignore
        [factors, factors,];
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "fac-empty" },
    });
    /** @type {__VLS_StyleScopedClasses['fac-empty']} */ ;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
