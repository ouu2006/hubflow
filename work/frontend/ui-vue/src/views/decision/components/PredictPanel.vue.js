/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 右栏 ② · 预测 · 时域外推(设计稿 03)。
// 口径:一期只做 L0 基线,**仅时域外推**;不出现任何预测精度数字(硬性口径 1 / 手册 §11.2)。
// 数据:GET /api/traffic/predict?segment_id=&h=15|30|60,取三档同屏。
import { computed, onMounted, ref, watch } from 'vue';
import { getTrafficPredict } from '../../../api/traffic';
import LevelBadge from '../../dashboard/components/LevelBadge.vue';
const { defineProps, } = {};
const props = defineProps();
const points = ref([]);
async function load() {
    points.value = [];
    if (!props.segmentId)
        return;
    try {
        const [a, b, c] = await Promise.all([
            getTrafficPredict(props.segmentId, 15),
            getTrafficPredict(props.segmentId, 30),
            getTrafficPredict(props.segmentId, 60),
        ]);
        // 三档去重后按 h 升序展示(h 为 15/30/60)
        const byH = new Map();
        for (const r of [a, b, c])
            for (const p of r.points)
                byH.set(p.h, p);
        points.value = [15, 30, 60]
            .map((h) => byH.get(h))
            .filter((p) => p !== undefined);
    }
    catch {
        points.value = [];
    }
}
/** ± 号:正 = 预计变差,负 = 预计缓解(中性色,不引入第四色轴) */
function signed(v) {
    return `${v >= 0 ? '+' : ''}${v.toFixed(1)}`;
}
const hasData = computed(() => points.value.length > 0);
onMounted(() => {
    void load();
});
watch(() => props.segmentId, () => {
    void load();
});
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
__VLS_withDotValue(hasData, {});
void {};
/** @type {__VLS_StyleScopedClasses['prow']} */ ;
/** @type {__VLS_StyleScopedClasses['prow']} */ ;
/** @type {__VLS_StyleScopedClasses['pd']} */ ;
/** @type {__VLS_StyleScopedClasses['pv']} */ ;
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
const __VLS_0 = __VLS_tryAsConstant((__VLS_unwrap(points, {})));
for (const [p] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        key: (p.h),
        ...{ class: "prow" },
    });
    /** @type {__VLS_StyleScopedClasses['prow']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "ph td-mono" },
    });
    /** @type {__VLS_StyleScopedClasses['ph']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
    (p.h);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "pl" },
    });
    /** @type {__VLS_StyleScopedClasses['pl']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "pd td-num" },
    });
    /** @type {__VLS_StyleScopedClasses['pd']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
    (signed(p.delta_ci));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "pv td-num" },
    });
    /** @type {__VLS_StyleScopedClasses['pv']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
    (p.ci.toFixed(1));
    const __VLS_1 = LevelBadge;
    // @ts-ignore
    const __VLS_2 = __VLS_asFunctionalComponent1(__VLS_1, new __VLS_1({
        // @ts-ignore
        level: (p.level), name: (p.level_name),
    }));
    const __VLS_3 = __VLS_2({
        level: (p.level),
        name: (p.level_name),
    }, ...__VLS_functionalComponentArgsRest(__VLS_2));
    // @ts-ignore
    [points,];
}
if (!hasData.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "empty" },
    });
    /** @type {__VLS_StyleScopedClasses['empty']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "note" },
});
/** @type {__VLS_StyleScopedClasses['note']} */ ;
// @ts-ignore
[hasData,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
