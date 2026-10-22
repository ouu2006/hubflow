/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 中栏下部:检测流水线(5 环节横向流程)+ N 路汇总(本次批处理;N 随登记表动态,IKMS1T 起不再固定 6)。
// 环节产物取当前通道 meta;服务未提供的量(标定 RANGE/RMSE、越线、平均 Q、处理用时)如实显示「—」。
import { computed } from 'vue';
import { fmtDur } from './channels';
const { defineProps, } = {};
const props = defineProps();
/** 有视频源且服务端真返回了 meta 的通道数(未接入视频源的不算"已导出") */
const exportsCount = computed(() => props.channels.filter((c) => c.def.hasVideo && c.meta !== null).length);
/** 通道总数(不再写死 6 —— 换站后通道数跟着包走) */
const chanTotal = computed(() => props.channels.length);
/** 未接入视频源的通道数(Issue IKLX5Y) */
const noSourceCount = computed(() => props.channels.filter((c) => !c.def.hasVideo).length);
/** 全包都没有视频源(站点包 Z):这时"源视频"这一环整环是空的,不能自称"离线样本" */
const allNoSource = computed(() => props.channels.length > 0 && noSourceCount.value === props.channels.length);
const stages = computed(() => {
    const m = props.meta;
    const backend = m?.backend ?? '';
    const srcLine = allNoSource.value
        ? `${chanTotal.value} 路通道 · 全部未接入视频源(本期留空)`
        : noSourceCount.value > 0
            ? `${chanTotal.value} 路通道(已导出 ${exportsCount.value} · 未接入视频源 ${noSourceCount.value})`
            : `${chanTotal.value} 路 · 离线样本(已导出 ${exportsCount.value} 路)`;
    return [
        { name: '源视频', value: srcLine, on: false },
        { name: '目标检测', value: m ? `${m.model} · ${m.conf_threshold} conf` : '—', on: false },
        {
            name: '多目标跟踪',
            value: m && backend.includes('ByteTrack') ? `ByteTrack · ${m.track_total} 轨迹` : '—',
            on: false,
        },
        { name: '透视标定', value: 'RANGE — · RMSE —', on: false },
        { name: '四项指标', value: 'q · v · k · L_q', on: true },
    ];
});
const trackSum = computed(() => props.channels.reduce((acc, c) => acc + (c.meta?.track_total ?? 0), 0));
const detSum = computed(() => {
    const known = props.channels.filter((c) => c.detTotal !== null);
    if (known.length === 0)
        return null;
    return known.reduce((acc, c) => acc + (c.detTotal ?? 0), 0);
});
/** 检测读取失败的通道数:合计口径里必须显式提示,避免"少算几路"被当成"就这么多" */
const detFailedCount = computed(() => props.channels.filter((c) => c.detFailed).length);
const summaryRows = computed(() => {
    const s = props.summary;
    return [
        { k: '轨迹总数', v: `${trackSum.value} 条` },
        { k: '检测框总数', v: detSum.value === null ? '—' : `${detSum.value} 框` },
        { k: '累计越线计数', v: s ? String(s.cross_total) : '—' },
        { k: '平均 Q', v: s && s.avg_quality !== null ? s.avg_quality.toFixed(2) : '—' },
        {
            k: '处理用时',
            v: s && s.pipeline ? fmtDur(s.pipeline.duration_s) : '—',
        },
    ];
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
__VLS_withDotValue(allNoSource, {});
void {};
/** @type {__VLS_StyleScopedClasses['stage']} */ ;
/** @type {__VLS_StyleScopedClasses['stage']} */ ;
/** @type {__VLS_StyleScopedClasses['on']} */ ;
/** @type {__VLS_StyleScopedClasses['st-name']} */ ;
/** @type {__VLS_StyleScopedClasses['sep']} */ ;
/** @type {__VLS_StyleScopedClasses['kv']} */ ;
/** @type {__VLS_StyleScopedClasses['kv']} */ ;
/** @type {__VLS_StyleScopedClasses['note']} */ ;
/** @type {__VLS_StyleScopedClasses['sep']} */ ;
/** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['sep']} */ ;
/** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['stage']} */ ;
/** @type {__VLS_StyleScopedClasses['st-val']} */ ;
/** @type {__VLS_StyleScopedClasses['kv']} */ ;
/** @type {__VLS_StyleScopedClasses['note']} */ ;
/** @type {__VLS_StyleScopedClasses['flow-note']} */ ;
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
(__VLS_ctx.current.cid);
(__VLS_ctx.current.source);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-body" },
});
/** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flow" },
});
/** @type {__VLS_StyleScopedClasses['flow']} */ ;
const __VLS_0 = __VLS_tryAsConstant((__VLS_unwrap(stages, {})));
for (const [st, i] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.template)({
        key: (st.name),
    });
    if (i > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "arrow" },
            'aria-hidden': "true",
        });
        /** @type {__VLS_StyleScopedClasses['arrow']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "stage" },
        ...{ class: ({ on: st.on }) },
    });
    /** @type {__VLS_StyleScopedClasses['stage']} */ ;
    /** @type {__VLS_StyleScopedClasses['on']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "st-name" },
    });
    /** @type {__VLS_StyleScopedClasses['st-name']} */ ;
    (st.name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "st-val td-mono" },
    });
    /** @type {__VLS_StyleScopedClasses['st-val']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
    (st.value);
    // @ts-ignore
    [current, current, stages,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "flow-note" },
});
/** @type {__VLS_StyleScopedClasses['flow-note']} */ ;
if (allNoSource.value) {
    (__VLS_unwrap(chanTotal, {}));
}
else {
    (__VLS_unwrap(chanTotal, {}));
    (__VLS_unwrap(exportsCount, {}));
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sep" },
});
/** @type {__VLS_StyleScopedClasses['sep']} */ ;
(__VLS_unwrap(chanTotal, {}));
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-head-tag" },
});
/** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
(__VLS_unwrap(exportsCount, {}));
(__VLS_unwrap(chanTotal, {}));
const __VLS_1 = __VLS_tryAsConstant((__VLS_unwrap(summaryRows, {})));
for (const [row] of __VLS_vFor(__VLS_nonNull(__VLS_1))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "kv" },
        key: (row.k),
    });
    /** @type {__VLS_StyleScopedClasses['kv']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "k" },
    });
    /** @type {__VLS_StyleScopedClasses['k']} */ ;
    (row.k);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "v td-mono" },
    });
    /** @type {__VLS_StyleScopedClasses['v']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
    (row.v);
    // @ts-ignore
    [allNoSource, chanTotal, chanTotal, chanTotal, chanTotal, exportsCount, exportsCount, summaryRows,];
}
if (__VLS_unwrap(detFailedCount, {}) > 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "note err" },
    });
    /** @type {__VLS_StyleScopedClasses['note']} */ ;
    /** @type {__VLS_StyleScopedClasses['err']} */ ;
    (__VLS_unwrap(detFailedCount, {}));
}
if (__VLS_ctx.summaryUnavailable) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "note" },
    });
    /** @type {__VLS_StyleScopedClasses['note']} */ ;
}
// @ts-ignore
[detFailedCount, detFailedCount, summaryUnavailable,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
