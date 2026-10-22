/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 档位分布 · 当前时刻:按档位统计路段数 + 色块;
//   拥堵版 = CI 四档（沿用既有口径，色取等级色）；
//   流量版（Issue IKNB9G）= q_vph 四档（色由调用方按 shared/flow.ts 配置传入）。
// 不可用单独成档——灰虚线框 + 斜杠符号(手册 §6.2「档位分布用灰虚线框 + 斜杠」),绝不用蓝/绿。
import { LEVELS } from '../../../shared/traffic';
const { defineProps, withDefaults, } = {};
const props = withDefaults(defineProps(), { unavailableLabel: '不可用' });
function rowColor(level, color) {
    return color ?? LEVELS[level]?.color ?? '#8B8B8B';
}
const __VLS_defaults = { unavailableLabel: '不可用' };
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
/** @type {__VLS_StyleScopedClasses['unbox']} */ ;
/** @type {__VLS_StyleScopedClasses['dist-row']} */ ;
/** @type {__VLS_StyleScopedClasses['dist-count']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "dist" },
});
/** @type {__VLS_StyleScopedClasses['dist']} */ ;
const __VLS_0 = __VLS_tryAsConstant((props.rows));
for (const [r] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        key: (r.level),
        ...{ class: "dist-row" },
    });
    /** @type {__VLS_StyleScopedClasses['dist-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
        ...{ class: "swatch" },
        ...{ style: ({ background: rowColor(r.level, r.color) }) },
    });
    /** @type {__VLS_StyleScopedClasses['swatch']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "dist-name" },
    });
    /** @type {__VLS_StyleScopedClasses['dist-name']} */ ;
    (r.name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "dist-count td-num" },
    });
    /** @type {__VLS_StyleScopedClasses['dist-count']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
    (r.count);
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "dist-row" },
});
/** @type {__VLS_StyleScopedClasses['dist-row']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "unbox" },
});
/** @type {__VLS_StyleScopedClasses['unbox']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.i)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "dist-name" },
});
/** @type {__VLS_StyleScopedClasses['dist-name']} */ ;
(props.unavailableLabel);
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "dist-count td-num" },
});
/** @type {__VLS_StyleScopedClasses['dist-count']} */ ;
/** @type {__VLS_StyleScopedClasses['td-num']} */ ;
(props.unavailable);
const __VLS_export = (await import('vue')).defineComponent({
    __defaults: __VLS_defaults,
    __typeProps: {},
});
export default {};
