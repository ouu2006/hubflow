/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 中栏下部:框与线的语义(车型框色图例 + 越线计数线语义 + 输出口径)。
// 车型框色与等级四级色解耦(手册 §6.2);画面区不出现等级色。
import { CLASS_COLORS } from '../../../shared/theme';
import { CLASS_KEYS, CLASS_LABEL, COUNT_LINE_POS } from './channels';
const legend = CLASS_KEYS.map((k) => ({ key: k, label: CLASS_LABEL[k], color: CLASS_COLORS[k] }));
const lineNote = `虚线 = 越线计数线(line_position = ${COUNT_LINE_POS},归一化画面高度)`;
const __VLS_ctx = {};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
void __VLS_ctx, __VLS_components, __VLS_intrinsics, __VLS_directives;
void {};
/** @type {__VLS_StyleScopedClasses['line']} */ ;
/** @type {__VLS_StyleScopedClasses['legend']} */ ;
/** @type {__VLS_StyleScopedClasses['line']} */ ;
/** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-body" },
});
/** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "legend" },
});
/** @type {__VLS_StyleScopedClasses['legend']} */ ;
const __VLS_0 = __VLS_tryAsConstant((__VLS_unwrap(legend, {})));
for (const [l] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        key: (l.key),
        ...{ class: "lg" },
    });
    /** @type {__VLS_StyleScopedClasses['lg']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.i)({
        ...{ class: "dot" },
        ...{ style: ({ background: l.color }) },
    });
    /** @type {__VLS_StyleScopedClasses['dot']} */ ;
    (l.label);
    // @ts-ignore
    [legend,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "line" },
});
/** @type {__VLS_StyleScopedClasses['line']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "line" },
});
/** @type {__VLS_StyleScopedClasses['line']} */ ;
(__VLS_unwrap(lineNote, {}));
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "line" },
});
/** @type {__VLS_StyleScopedClasses['line']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({});
// @ts-ignore
[lineNote,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
