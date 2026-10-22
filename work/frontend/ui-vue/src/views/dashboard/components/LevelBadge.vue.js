/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 等级徽章 = 三重编码的"图标 + 文字"(颜色由使用处的 currentColor / 边框承担):
// 竖条数图标照手册 §6.2(单/双/三/四竖条);数据陈旧 / 上游未判级(level=0,接口层不兜底成畅通)
// 一律显示灰色问号(非等级状态)——TC-11:没数据绝不显示成蓝/绿。
// 2026-10-12 TDesign Light 切换:图形(竖条/问号)用标准阶 color,文字用深一阶 text,
// 保证浅底上文字对比度达标(手册 §6.2 表的「图形色值 / 文字色值」两列)。
import { computed } from 'vue';
import { LEVELS, UNAVAILABLE } from '../../../shared/traffic';
const { defineProps, } = {};
const props = defineProps();
const style = computed(() => {
    const known = LEVELS[props.level];
    return props.stale === true || !known ? UNAVAILABLE : known;
});
const text = computed(() => props.name ?? style.value.name);
const textColor = computed(() => (props.anti === true ? '#FFFFFF' : style.value.text));
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
__VLS_withDotValue(style, {});
void {};
/** @type {__VLS_StyleScopedClasses['bars']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "lv-badge" },
    ...{ style: ({ color: style.value.color }) },
});
/** @type {__VLS_StyleScopedClasses['lv-badge']} */ ;
if (style.value.bars === 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "unknown" },
    });
    /** @type {__VLS_StyleScopedClasses['unknown']} */ ;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "bars" },
    });
    /** @type {__VLS_StyleScopedClasses['bars']} */ ;
    const __VLS_0 = __VLS_tryAsConstant((style.value.bars));
    for (const [n] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.i)({
            key: (n),
        });
        // @ts-ignore
        [style, style, style,];
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "txt" },
    ...{ style: ({ color: __VLS_unwrap(textColor, {}) }) },
});
/** @type {__VLS_StyleScopedClasses['txt']} */ ;
(__VLS_unwrap(text, {}));
// @ts-ignore
[textColor, text,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
