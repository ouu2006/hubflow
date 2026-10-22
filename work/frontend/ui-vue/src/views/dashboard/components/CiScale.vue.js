/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// CI 色阶条(展示档位):色标复用四级色阶(ciGradientCss),刻度 = CI_BANDS(0/25/50/75/100)。
// 灰 #8B8B8B 不参与色阶——灰只表示「数据不可用」,由父级另起一行说明(手册 §6.2 语义分工)。
import { CI_BANDS, ciGradientCss } from '../../../shared/traffic';
const __VLS_ctx = {};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
void __VLS_ctx, __VLS_components, __VLS_intrinsics, __VLS_directives;
void {};
/** @type {__VLS_StyleScopedClasses['ramp']} */ ;
/** @type {__VLS_StyleScopedClasses['ticks']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "ci-scale" },
});
/** @type {__VLS_StyleScopedClasses['ci-scale']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div)({
    ...{ class: "ramp" },
    ...{ style: ({ background: __VLS_unwrap(ciGradientCss, {})() }) },
});
/** @type {__VLS_StyleScopedClasses['ramp']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "ticks" },
});
/** @type {__VLS_StyleScopedClasses['ticks']} */ ;
const __VLS_0 = __VLS_tryAsConstant((__VLS_unwrap(CI_BANDS, {})));
for (const [b] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        key: (b),
        ...{ class: "tick" },
    });
    /** @type {__VLS_StyleScopedClasses['tick']} */ ;
    (b);
    // @ts-ignore
    [ciGradientCss, CI_BANDS,];
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
