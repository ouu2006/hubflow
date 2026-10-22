/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import LevelBadge from './LevelBadge.vue';
const { defineProps, } = {};
const __VLS_props = defineProps();
// 未闭环 = 待认领 / 处置中(已闭环 / 误报为终态)
const OPEN_STATUS = ['待认领', '处置中'];
function statusClass(s) {
    return OPEN_STATUS.includes(s) ? 'open' : 'closed';
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
/** @type {__VLS_StyleScopedClasses['al-row']} */ ;
/** @type {__VLS_StyleScopedClasses['al-status']} */ ;
/** @type {__VLS_StyleScopedClasses['al-status']} */ ;
/** @type {__VLS_StyleScopedClasses['al-row']} */ ;
/** @type {__VLS_StyleScopedClasses['al-line1']} */ ;
/** @type {__VLS_StyleScopedClasses['al-line2']} */ ;
/** @type {__VLS_StyleScopedClasses['al-status']} */ ;
if (__VLS_ctx.alerts.length > 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "al" },
    });
    /** @type {__VLS_StyleScopedClasses['al']} */ ;
    const __VLS_0 = __VLS_tryAsConstant((__VLS_ctx.alerts));
    for (const [a] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (a.alert_id),
            ...{ class: "al-row" },
        });
        /** @type {__VLS_StyleScopedClasses['al-row']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "al-line1" },
        });
        /** @type {__VLS_StyleScopedClasses['al-line1']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "al-id td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['al-id']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (a.alert_id);
        const __VLS_1 = LevelBadge;
        // @ts-ignore
        const __VLS_2 = __VLS_asFunctionalComponent1(__VLS_1, new __VLS_1({
            // @ts-ignore
            level: (__VLS_ctx.levelOf(a)),
        }));
        const __VLS_3 = __VLS_2({
            level: (__VLS_ctx.levelOf(a)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_2));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "al-status" },
            ...{ class: (statusClass(a.status)) },
        });
        /** @type {__VLS_StyleScopedClasses['al-status']} */ ;
        (a.status);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "al-line2" },
        });
        /** @type {__VLS_StyleScopedClasses['al-line2']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        (a.segment_name);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "al-time td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['al-time']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (a.first_seen);
        // @ts-ignore
        [alerts, alerts, levelOf,];
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "al-empty" },
    });
    /** @type {__VLS_StyleScopedClasses['al-empty']} */ ;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
