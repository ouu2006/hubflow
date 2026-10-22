/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 右栏 ③ · 数据同化 · 断面门控(设计稿 03)。
// 口径:门控铁律 = **仅 role=boundary(边界)断面允许视频实测回灌孪生**;
//   内部断面恒为 assimilating=false(reason = internal_not_allowed),不是"门控中",是制度上不允许。
// 数据:GET /api/traffic/assimilation(AssimilationSnapshotFull,带 role / 断面编号 / 计数)。
import { computed, onMounted, ref } from 'vue';
import { getTrafficAssimilationFull } from '../../../api/traffic';
const snap = ref(null);
async function load() {
    try {
        snap.value = await getTrafficAssimilationFull();
    }
    catch {
        snap.value = null; // 显式空态:接口未起,显示「—」不编造
    }
}
const GLYPH = { 已回灌: '●', 门控中: '◐', 不回灌: '○' };
function stateOf(r) {
    if (r.enabled)
        return '已回灌';
    if (r.role === 'internal' || r.reason === 'internal_not_allowed')
        return '不回灌';
    return '门控中';
}
function descOf(r) {
    if (r.enabled) {
        const f = r.flow_dev_pct;
        const s = r.speed_dev_pct;
        return `视频实测回灌孪生 · dev ${f ?? '—'}% / ${s ?? '—'}%`;
    }
    if (stateOf(r) === '不回灌')
        return `${r.reason ?? 'internal_not_allowed'} · 因为 assimilating=false`;
    return r.gate_detail ?? '—';
}
const counts = computed(() => snap.value?.counts ?? { boundary: 0, internal: 0 });
onMounted(() => {
    void load();
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
void __VLS_ctx, __VLS_components, __VLS_intrinsics, __VLS_directives;
// @ts-ignore
__VLS_withDotValue(counts, {});
// @ts-ignore
__VLS_withDotValue(snap, {});
// @ts-ignore
__VLS_withDotValue(GLYPH, {});
void {};
/** @type {__VLS_StyleScopedClasses['arow']} */ ;
/** @type {__VLS_StyleScopedClasses['atop']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
    ...{ class: "td-card" },
});
/** @type {__VLS_StyleScopedClasses['td-card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-head" },
});
/** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-head-tag td-num" },
});
/** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['td-num']} */ ;
(counts.value.boundary);
(counts.value.internal);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-body" },
});
/** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
const __VLS_0 = __VLS_tryAsConstant((snap.value?.records ?? []));
for (const [r] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        key: (r.point_id),
        ...{ class: "arow" },
    });
    /** @type {__VLS_StyleScopedClasses['arow']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "atop" },
    });
    /** @type {__VLS_StyleScopedClasses['atop']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "acode td-mono" },
    });
    /** @type {__VLS_StyleScopedClasses['acode']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
    (r.point_code ?? r.point_id);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "aname" },
    });
    /** @type {__VLS_StyleScopedClasses['aname']} */ ;
    (r.name ?? r.segment_id);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-chip astate" },
    });
    /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
    /** @type {__VLS_StyleScopedClasses['astate']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.i, __VLS_intrinsics.i)({
        ...{ class: "gt" },
    });
    /** @type {__VLS_StyleScopedClasses['gt']} */ ;
    (GLYPH.value[stateOf(r)]);
    (stateOf(r));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "adesc" },
    });
    /** @type {__VLS_StyleScopedClasses['adesc']} */ ;
    (descOf(r));
    // @ts-ignore
    [counts, counts, snap, GLYPH,];
}
if (!snap.value) {
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
[snap,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
