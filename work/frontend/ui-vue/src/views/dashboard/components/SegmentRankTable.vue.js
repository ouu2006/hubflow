/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 路段指数排行:仅 ciAvailable 为真者参与「按 CI 降序」排序并显示数值;
// 不可用路段恒灰、排最后、显示「不可用」(TC-11:缺 CI 或数据陈旧绝不落进通配色)。
// 列表底部标注 CI 免责口径(手册 §6.5 第 1 条:页脚 / 图例 / 列表三处必现)。
import { CI_DISCLAIMER } from '../../../shared/traffic';
import LevelBadge from './LevelBadge.vue';
const { defineProps, defineEmits, } = {};
const __VLS_props = defineProps();
const emit = defineEmits();
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
void {};
/** @type {__VLS_StyleScopedClasses['rank-ci']} */ ;
/** @type {__VLS_StyleScopedClasses['rank-out']} */ ;
/** @type {__VLS_StyleScopedClasses['rank-ci']} */ ;
/** @type {__VLS_StyleScopedClasses['rank-note']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "rank" },
});
/** @type {__VLS_StyleScopedClasses['rank']} */ ;
const __VLS_0 = __VLS_tryAsConstant((__VLS_ctx.items));
for (const [it] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                return (__VLS_unwrap(emit, {})('select', it.id));
                // @ts-ignore
                [items, emit,];
            } },
        key: (it.id),
        ...{ class: "td-row rank-row" },
        ...{ class: ({ on: it.id === __VLS_ctx.selectedId }) },
        role: "button",
    });
    /** @type {__VLS_StyleScopedClasses['td-row']} */ ;
    /** @type {__VLS_StyleScopedClasses['rank-row']} */ ;
    /** @type {__VLS_StyleScopedClasses['on']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "rank-name" },
    });
    /** @type {__VLS_StyleScopedClasses['rank-name']} */ ;
    (it.name);
    if (it.available && it.ci !== null) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "rank-ci td-num" },
        });
        /** @type {__VLS_StyleScopedClasses['rank-ci']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
        ((it.ci ?? 0).toFixed(1));
        const __VLS_1 = LevelBadge;
        // @ts-ignore
        const __VLS_2 = __VLS_asFunctionalComponent1(__VLS_1, new __VLS_1({
            // @ts-ignore
            level: (it.level),
        }));
        const __VLS_3 = __VLS_2({
            level: (it.level),
        }, ...__VLS_functionalComponentArgsRest(__VLS_2));
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "rank-out" },
        });
        /** @type {__VLS_StyleScopedClasses['rank-out']} */ ;
    }
    // @ts-ignore
    [selectedId,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "rank-note" },
});
/** @type {__VLS_StyleScopedClasses['rank-note']} */ ;
(__VLS_unwrap(CI_DISCLAIMER, {}));
// @ts-ignore
[CI_DISCLAIMER,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
