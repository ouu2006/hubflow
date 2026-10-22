/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 左栏:视频源台账(N 路,可用性以 /perception-api/streams 实际返回判定)+ 跟踪环节清单。
// IKMS1T 起不再固定 6 路:行数 = 源台账 cameras 条数 N(0 路合法),左栏自身滚动;
// 数字一律取 meta;服务未提供的环节(透视标定 / 越线计数 / 判级)显示「—」并注明出处。
//
// 2026-10-18 口径(IKNBT2):**N 段 = N 摄像头 = N 视频(演示,mock 复用)**——
// 本台账只是**源台账/初始映射**,不代表一期摄像头总数;0 路源台账 ≠ 本站没有摄像头/视频。
import { computed } from 'vue';
import { demoCameraCount } from '../../../shared/cameras';
import { feedOf, feedText, metaLine } from './channels';
const { defineProps, defineEmits, } = {};
const props = defineProps();
const emit = defineEmits();
/** 一期演示摄像头总数 = 路段数（Z=61 / GZ=433；与源台账分开说） */
const demoCameraTotal = computed(() => demoCameraCount());
/** 有视频源且服务端真返回了 meta 的通道数(未接入视频源的不算"已导出") */
const exportedCount = computed(() => props.channels.filter((c) => c.def.hasVideo && c.meta !== null).length);
/** 未接入视频源的通道数(Issue IKLX5Y:布了点、视频留空窗) */
const noSourceCount = computed(() => props.channels.filter((c) => !c.def.hasVideo).length);
/** 全包都没有视频源(站点包 Z):这时不能自称"离线样本"——样本视频压根没有 */
const allNoSource = computed(() => props.channels.length > 0 && noSourceCount.value === props.channels.length);
const current = computed(() => props.channels.find((c) => c.def.source === props.currentId) ?? null);
const currentMeta = computed(() => current.value?.meta ?? null);
const linkRows = computed(() => {
    const m = currentMeta.value;
    const backend = m?.backend ?? '';
    return [
        { k: '目标检测', v: m ? m.model : '—' },
        { k: '后端 / 框架', v: backend || '—' },
        { k: '多目标跟踪', v: backend.includes('ByteTrack') ? 'ByteTrack' : '—' },
        { k: '轨迹总数', v: m ? String(m.track_total) : '—' },
        { k: '类别白名单', v: m ? Object.values(m.class_names).join(' / ') : '—' },
        { k: '透视标定', v: '—' },
        { k: '越线计数', v: '—' },
        { k: '判级', v: '—' },
    ];
});
function stateOf(c) {
    const f = feedOf(c);
    // 「当前」态只在真有画面可看时才亮(未接入视频源的通道谈不上"检测中")
    if (f === 'ok' && c.def.source === props.currentId)
        return { text: '检测中', cls: 'on' };
    return feedText(c);
}
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
__VLS_withDotValue(current, {});
// @ts-ignore
__VLS_withDotValue(allNoSource, {});
void {};
/** @type {__VLS_StyleScopedClasses['ledger-note']} */ ;
/** @type {__VLS_StyleScopedClasses['chan-l1']} */ ;
/** @type {__VLS_StyleScopedClasses['kv']} */ ;
/** @type {__VLS_StyleScopedClasses['kv']} */ ;
/** @type {__VLS_StyleScopedClasses['kv']} */ ;
/** @type {__VLS_StyleScopedClasses['line']} */ ;
/** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['chan-l1']} */ ;
/** @type {__VLS_StyleScopedClasses['chan-l1']} */ ;
/** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['chan-l3']} */ ;
/** @type {__VLS_StyleScopedClasses['kv']} */ ;
/** @type {__VLS_StyleScopedClasses['ledger-note']} */ ;
/** @type {__VLS_StyleScopedClasses['note']} */ ;
/** @type {__VLS_StyleScopedClasses['line']} */ ;
/** @type {__VLS_StyleScopedClasses['kv']} */ ;
/** @type {__VLS_StyleScopedClasses['v']} */ ;
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
if (__VLS_ctx.channels.length === 0) {
    (__VLS_unwrap(demoCameraTotal, {}));
}
else {
    (__VLS_ctx.channels.length);
    (__VLS_unwrap(exportedCount, {}));
    if (__VLS_unwrap(noSourceCount, {}) > 0) {
        (__VLS_unwrap(noSourceCount, {}));
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-body flush" },
});
/** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
/** @type {__VLS_StyleScopedClasses['flush']} */ ;
if (__VLS_ctx.channels.length === 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "ledger-empty" },
    });
    /** @type {__VLS_StyleScopedClasses['ledger-empty']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "le-l1" },
    });
    /** @type {__VLS_StyleScopedClasses['le-l1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "le-l2" },
    });
    /** @type {__VLS_StyleScopedClasses['le-l2']} */ ;
    (__VLS_unwrap(demoCameraTotal, {}));
    (__VLS_unwrap(demoCameraTotal, {}));
}
if (__VLS_ctx.channels.length > 0) {
    const __VLS_0 = __VLS_tryAsConstant((__VLS_ctx.channels));
    for (const [c] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ onClick: // @ts-ignore
                (...[$event]) => {
                    void $event;
                    if (!(__VLS_ctx.channels.length > 0))
                        throw 0;
                    return (__VLS_unwrap(emit, {})('select', c.def.source));
                    // @ts-ignore
                    [channels, channels, channels, channels, channels, demoCameraTotal, demoCameraTotal, demoCameraTotal, exportedCount, noSourceCount, noSourceCount, emit,];
                } },
            key: (c.def.source),
            ...{ class: "td-row chan" },
            ...{ class: ({ on: c.def.source === __VLS_ctx.currentId }) },
            role: "button",
            'aria-pressed': (c.def.source === __VLS_ctx.currentId),
        });
        /** @type {__VLS_StyleScopedClasses['td-row']} */ ;
        /** @type {__VLS_StyleScopedClasses['chan']} */ ;
        /** @type {__VLS_StyleScopedClasses['on']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "chan-main" },
        });
        /** @type {__VLS_StyleScopedClasses['chan-main']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "chan-l1" },
        });
        /** @type {__VLS_StyleScopedClasses['chan-l1']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "cid td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['cid']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (c.def.cid);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "src" },
        });
        /** @type {__VLS_StyleScopedClasses['src']} */ ;
        (c.def.source);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "td-chip" },
            ...{ class: (stateOf(c).cls) },
        });
        /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
        (stateOf(c).text);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "chan-l2" },
        });
        /** @type {__VLS_StyleScopedClasses['chan-l2']} */ ;
        (c.def.segmentId);
        (c.def.name);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "chan-l3 td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['chan-l3']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (!c.def.hasVideo ? '源台账无视频源 · 本期留空(演示复用见大屏路段卡)' : __VLS_unwrap(metaLine, {})(c.meta, c.detTotal));
        // @ts-ignore
        [currentId, currentId, metaLine,];
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "ledger-note" },
});
/** @type {__VLS_StyleScopedClasses['ledger-note']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
(__VLS_unwrap(demoCameraTotal, {}));
(__VLS_unwrap(demoCameraTotal, {}));
(__VLS_ctx.channels.length);
__VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
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
(current.value ? `当前 ${current.value.def.cid} ${current.value.def.source}` : '未选通道');
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-body" },
});
/** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
const __VLS_1 = __VLS_tryAsConstant((__VLS_unwrap(linkRows, {})));
for (const [row] of __VLS_vFor(__VLS_nonNull(__VLS_1))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        key: (row.k),
        ...{ class: "kv" },
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
    [channels, demoCameraTotal, demoCameraTotal, current, current, current, linkRows,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "note" },
});
/** @type {__VLS_StyleScopedClasses['note']} */ ;
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
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "line" },
});
/** @type {__VLS_StyleScopedClasses['line']} */ ;
if (__VLS_ctx.channels.length === 0) {
    (__VLS_unwrap(demoCameraTotal, {}));
}
else if (allNoSource.value) {
    (__VLS_ctx.channels.length);
}
else {
}
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "line" },
});
/** @type {__VLS_StyleScopedClasses['line']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "line strong" },
});
/** @type {__VLS_StyleScopedClasses['line']} */ ;
/** @type {__VLS_StyleScopedClasses['strong']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "note" },
});
/** @type {__VLS_StyleScopedClasses['note']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
// @ts-ignore
[channels, channels, demoCameraTotal, allNoSource,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
