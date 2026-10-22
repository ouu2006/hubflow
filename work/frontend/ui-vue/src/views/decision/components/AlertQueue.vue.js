/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 左栏 · 处置队列(设计稿 03):按告警四态分组(待认领 / 处置中 / 已闭环 / 误报),组头显示条数。
// 口径纪律:
//   ① 状态 chip **不用彩色**——四态一律中性底 + 文字 + 形态符号(○ ◐ ● ✕)区分,
//      避免第三条色彩轴与 LevelBadge 的等级色混淆(硬性口径 3);
//   ② 组内行 = 告警号 + 路段名 + 等级徽章 + 时间 + 状态 chip;
//   ③ 选中行用品牌浅底 + 左侧品牌竖条 = 「已选」语义(硬性口径 4)。
import LevelBadge from '../../dashboard/components/LevelBadge.vue';
const { defineProps, defineEmits, } = {};
const __VLS_props = defineProps();
const emit = defineEmits();
/** 四态形态符号(中性,不承载颜色语义) */
const GLYPH = {
    待认领: '○',
    处置中: '◐',
    已闭环: '●',
    误报: '✕',
};
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
// @ts-ignore
__VLS_withDotValue(GLYPH, {});
void {};
/** @type {__VLS_StyleScopedClasses['grp']} */ ;
/** @type {__VLS_StyleScopedClasses['q-row']} */ ;
/** @type {__VLS_StyleScopedClasses['q-empty']} */ ;
/** @type {__VLS_StyleScopedClasses['q-seg']} */ ;
/** @type {__VLS_StyleScopedClasses['q-bot']} */ ;
/** @type {__VLS_StyleScopedClasses['grp']} */ ;
/** @type {__VLS_StyleScopedClasses['q-row']} */ ;
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
(__VLS_ctx.total);
(__VLS_ctx.openCount);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-body flush" },
});
/** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
/** @type {__VLS_StyleScopedClasses['flush']} */ ;
const __VLS_0 = __VLS_tryAsConstant((__VLS_ctx.groups));
for (const [g] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.template)({
        key: (g.state),
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "grp" },
    });
    /** @type {__VLS_StyleScopedClasses['grp']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "grp-glyph" },
    });
    /** @type {__VLS_StyleScopedClasses['grp-glyph']} */ ;
    (GLYPH.value[g.state]);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "grp-name" },
    });
    /** @type {__VLS_StyleScopedClasses['grp-name']} */ ;
    (g.state);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "grp-cnt td-num" },
    });
    /** @type {__VLS_StyleScopedClasses['grp-cnt']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
    (g.items.length);
    const __VLS_1 = __VLS_tryAsConstant((g.items));
    for (const [row] of __VLS_vFor(__VLS_nonNull(__VLS_1))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: // @ts-ignore
                (...[$event]) => {
                    void $event;
                    return (__VLS_unwrap(emit, {})('select', row.id));
                    // @ts-ignore
                    [total, openCount, groups, GLYPH, emit,];
                } },
            key: (row.id),
            type: "button",
            ...{ class: "td-row q-row" },
            ...{ class: ({ on: row.id === __VLS_ctx.selectedId }) },
        });
        /** @type {__VLS_StyleScopedClasses['td-row']} */ ;
        /** @type {__VLS_StyleScopedClasses['q-row']} */ ;
        /** @type {__VLS_StyleScopedClasses['on']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "q-top" },
        });
        /** @type {__VLS_StyleScopedClasses['q-top']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "td-mono q-id" },
        });
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        /** @type {__VLS_StyleScopedClasses['q-id']} */ ;
        (row.id);
        const __VLS_2 = LevelBadge;
        // @ts-ignore
        const __VLS_3 = __VLS_asFunctionalComponent1(__VLS_2, new __VLS_2({
            // @ts-ignore
            level: (row.level), stale: (row.stale),
        }));
        const __VLS_4 = __VLS_3({
            level: (row.level),
            stale: (row.stale),
        }, ...__VLS_functionalComponentArgsRest(__VLS_3));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "q-seg" },
        });
        /** @type {__VLS_StyleScopedClasses['q-seg']} */ ;
        (row.segId);
        (row.name);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "q-bot" },
        });
        /** @type {__VLS_StyleScopedClasses['q-bot']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "td-num q-time" },
        });
        /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
        /** @type {__VLS_StyleScopedClasses['q-time']} */ ;
        (row.time);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "td-chip q-chip" },
        });
        /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
        /** @type {__VLS_StyleScopedClasses['q-chip']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.i, __VLS_intrinsics.i)({
            ...{ class: "gt" },
        });
        /** @type {__VLS_StyleScopedClasses['gt']} */ ;
        (GLYPH.value[row.state]);
        (row.chip);
        // @ts-ignore
        [GLYPH, selectedId,];
    }
    if (g.items.length === 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "q-empty" },
        });
        /** @type {__VLS_StyleScopedClasses['q-empty']} */ ;
    }
    // @ts-ignore
    [];
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
