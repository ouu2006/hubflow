/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 右栏:检测详情(当前通道)。
// ① 头部(通道 + 映射路段 + 状态) ② 累计轨迹按车型分组(first_seen 口径) ③ 轨迹质量与标定(降级)
// ④ 输出字段(该路段 video 槽位) ⑤ 实测回灌孪生(同化门控)。
// 铁律:拿不到的数据一律「—」+ 注明出处;输出字段的陈旧态走灰(UNAVAILABLE),绝不显示成蓝/绿。
import { computed } from 'vue';
import { UNAVAILABLE, isStale } from '../../../shared/traffic';
import { CLASS_COLORS } from '../../../shared/theme';
import { CLASS_KEYS, CLASS_LABEL, cumClassCounts, fmtDur } from './channels';
const { defineProps, } = {};
const props = defineProps();
const meta = computed(() => props.ch.meta);
/** 未接入视频源的通道(Issue IKLX5Y):与"未导出"分开说 */
const noSource = computed(() => !props.ch.def.hasVideo);
const stateChip = computed(() => noSource.value
    ? { text: '未接入视频源', cls: 'out' }
    : meta.value
        ? { text: '已导出', cls: 'ok' }
        : { text: '未导出', cls: 'out' });
const resLine = computed(() => {
    if (noSource.value)
        return '未接入视频源 · 本期留空(路网上已布点,点击来自大屏)';
    const m = meta.value;
    if (!m)
        return '样本视频未导出 · 无检测数据';
    return `${m.width}×${m.height} · ${m.fps} fps · 时长 ${fmtDur(m.duration_s)} · ${m.total_frames} 帧`;
});
const classNames = computed(() => meta.value?.class_names ?? {});
const cum = computed(() => cumClassCounts(props.ch.det, classNames.value));
const classRows = computed(() => CLASS_KEYS.map((k) => ({
    key: k,
    label: CLASS_LABEL[k],
    color: CLASS_COLORS[k],
    count: cum.value.byKey.get(k) ?? 0,
})));
// ---------- 轨迹质量与标定(感知服务提供;当前不可用 → 「—」) ----------
const qualityRows = computed(() => {
    const s = props.summary;
    return [
        { k: 'ID 切换占比 SVR', v: s && s.id_switch_svr !== null ? s.id_switch_svr.toFixed(2) : '—' },
        { k: '轨迹质量因子 Q', v: s && s.avg_quality !== null ? s.avg_quality.toFixed(2) : '—' },
        {
            k: '标定控制点 · RANGE',
            v: s && s.calibration ? `${s.calibration.range_px} px · RMSE ${s.calibration.rmse_px} px` : '—',
        },
        { k: '有效标定帧数', v: s && s.pipeline ? String(s.pipeline.frames) : '—' },
    ];
});
// ---------- 输出字段(该路段 source === 'video' 的槽位) ----------
const videoSlot = computed(() => props.sourcePair?.slots.find((s) => s.source === 'video') ?? null);
const outRecord = computed(() => {
    const slot = videoSlot.value;
    return slot && slot.available ? slot.record : null;
});
const outStale = computed(() => {
    const r = outRecord.value;
    return r ? isStale(r) : false;
});
function num(v, digits) {
    return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—';
}
const outRows = computed(() => {
    const r = outRecord.value;
    return [
        { k: 'q_vph', u: 'veh/h', v: num(r?.q_vph, 0) },
        { k: 'v_kmh', u: 'km/h', v: num(r?.v_kmh, 1) },
        { k: 'L_q_m', u: 'm', v: num(r?.L_q_m, 0) },
        { k: 'k_vpk', u: 'veh/km/ln', v: num(r?.k_vpk, 1) },
        { k: 'confidence', u: '', v: num(r?.confidence, 2) },
        { k: 'data_age_s', u: 's', v: num(r?.data_age_s, 0) },
    ];
});
// ---------- 实测回灌孪生(同化门控:按 segment_id 找断面记录) ----------
const gate = computed(() => props.assimilation?.records.find((r) => r.segment_id === props.ch.def.segmentId) ?? null);
/** 命中断面时的展示编号(E-xx);未命中为 null */
const gatePoint = computed(() => {
    const g = gate.value;
    return g ? (g.point_code ?? g.point_id) : null;
});
const gateState = computed(() => {
    const g = gate.value;
    if (!g) {
        return {
            enabled: false,
            point: '—',
            text: '该路段未登记断面 · 不参与回灌',
            reason: `${props.ch.def.segmentId} 在 network.sections 中无断面记录,故无同化记录`,
        };
    }
    if (g.role === 'internal') {
        return {
            enabled: false,
            point: g.point_code ?? g.point_id,
            text: 'internal_not_allowed · 内部断面不允许回灌',
            reason: g.gate_detail ?? g.reason ?? '仅 role=boundary 断面允许回灌(手册门控口径)',
        };
    }
    if (g.enabled) {
        return {
            enabled: true,
            point: g.point_code ?? g.point_id,
            text: '已回灌',
            reason: g.gate_detail ?? `role=boundary · confidence ${g.confidence ?? '—'}`,
        };
    }
    return {
        enabled: false,
        point: g.point_code ?? g.point_id,
        text: '门控未放行 · 未回灌',
        reason: g.gate_detail ?? g.reason ?? g.gate_reason ?? '门控原因未提供',
    };
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
__VLS_withDotValue(stateChip, {});
// @ts-ignore
__VLS_withDotValue(gatePoint, {});
// @ts-ignore
__VLS_withDotValue(cum, {});
// @ts-ignore
__VLS_withDotValue(noSource, {});
// @ts-ignore
__VLS_withDotValue(outRecord, {});
// @ts-ignore
__VLS_withDotValue(outStale, {});
// @ts-ignore
__VLS_withDotValue(UNAVAILABLE, {});
// @ts-ignore
__VLS_withDotValue(gateState, {});
void {};
/** @type {__VLS_StyleScopedClasses['d-head']} */ ;
/** @type {__VLS_StyleScopedClasses['sep']} */ ;
/** @type {__VLS_StyleScopedClasses['kv']} */ ;
/** @type {__VLS_StyleScopedClasses['kv']} */ ;
/** @type {__VLS_StyleScopedClasses['k']} */ ;
/** @type {__VLS_StyleScopedClasses['kv']} */ ;
/** @type {__VLS_StyleScopedClasses['note']} */ ;
/** @type {__VLS_StyleScopedClasses['d-head']} */ ;
/** @type {__VLS_StyleScopedClasses['sep']} */ ;
/** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['sep']} */ ;
/** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['kv']} */ ;
/** @type {__VLS_StyleScopedClasses['kv']} */ ;
/** @type {__VLS_StyleScopedClasses['v']} */ ;
/** @type {__VLS_StyleScopedClasses['td-table']} */ ;
/** @type {__VLS_StyleScopedClasses['note']} */ ;
/** @type {__VLS_StyleScopedClasses['gate-line']} */ ;
/** @type {__VLS_StyleScopedClasses['d-sub']} */ ;
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
(__VLS_ctx.ch.def.cid);
(__VLS_ctx.ch.def.segmentId);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-body detail" },
});
/** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
/** @type {__VLS_StyleScopedClasses['detail']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "d-head" },
});
/** @type {__VLS_StyleScopedClasses['d-head']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "d-title" },
});
/** @type {__VLS_StyleScopedClasses['d-title']} */ ;
(__VLS_ctx.ch.def.cid);
(__VLS_ctx.ch.def.source);
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-chip" },
    ...{ class: (stateChip.value.cls) },
});
/** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
(stateChip.value.text);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "d-sub" },
});
/** @type {__VLS_StyleScopedClasses['d-sub']} */ ;
(__VLS_ctx.ch.def.segmentId);
(__VLS_ctx.ch.def.name);
if (gatePoint.value) {
    (gatePoint.value);
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "d-sub td-mono" },
});
/** @type {__VLS_StyleScopedClasses['d-sub']} */ ;
/** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
(__VLS_unwrap(resLine, {}));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sep" },
});
/** @type {__VLS_StyleScopedClasses['sep']} */ ;
if (__VLS_ctx.ch.det) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.table, __VLS_intrinsics.table)({
        ...{ class: "td-table" },
    });
    /** @type {__VLS_StyleScopedClasses['td-table']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.thead, __VLS_intrinsics.thead)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
        ...{ class: "num" },
    });
    /** @type {__VLS_StyleScopedClasses['num']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.tbody, __VLS_intrinsics.tbody)({});
    const __VLS_0 = __VLS_tryAsConstant((__VLS_unwrap(classRows, {})));
    for (const [row] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({
            key: (row.key),
        });
        __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
            ...{ class: "dot" },
            ...{ style: ({ background: row.color }) },
        });
        /** @type {__VLS_StyleScopedClasses['dot']} */ ;
        (row.label);
        __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
            ...{ class: "num" },
        });
        /** @type {__VLS_StyleScopedClasses['num']} */ ;
        (row.count);
        // @ts-ignore
        [ch, ch, ch, ch, ch, ch, ch, stateChip, stateChip, gatePoint, gatePoint, resLine, classRows,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({
        ...{ class: "tot" },
    });
    /** @type {__VLS_StyleScopedClasses['tot']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
        ...{ class: "num" },
    });
    /** @type {__VLS_StyleScopedClasses['num']} */ ;
    (cum.value.total);
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "note" },
    });
    /** @type {__VLS_StyleScopedClasses['note']} */ ;
    (cum.value.other);
}
else if (__VLS_ctx.ch.detFailed) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "note err" },
    });
    /** @type {__VLS_StyleScopedClasses['note']} */ ;
    /** @type {__VLS_StyleScopedClasses['err']} */ ;
}
else if (noSource.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "note" },
    });
    /** @type {__VLS_StyleScopedClasses['note']} */ ;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "note" },
    });
    /** @type {__VLS_StyleScopedClasses['note']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "kv" },
});
/** @type {__VLS_StyleScopedClasses['kv']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "k" },
});
/** @type {__VLS_StyleScopedClasses['k']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "v td-mono" },
});
/** @type {__VLS_StyleScopedClasses['v']} */ ;
/** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sep" },
});
/** @type {__VLS_StyleScopedClasses['sep']} */ ;
const __VLS_1 = __VLS_tryAsConstant((__VLS_unwrap(qualityRows, {})));
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
    [ch, cum, cum, noSource, qualityRows,];
}
if (__VLS_ctx.summaryUnavailable) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "note" },
    });
    /** @type {__VLS_StyleScopedClasses['note']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sep" },
});
/** @type {__VLS_StyleScopedClasses['sep']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-head-tag" },
});
/** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
if (outRecord.value) {
    const __VLS_2 = __VLS_tryAsConstant((__VLS_unwrap(outRows, {})));
    for (const [row] of __VLS_vFor(__VLS_nonNull(__VLS_2))) {
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
        if (row.u) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "u" },
            });
            /** @type {__VLS_StyleScopedClasses['u']} */ ;
            (row.u);
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "v td-mono" },
            ...{ style: (outStale.value ? { color: UNAVAILABLE.value.color } : {}) },
        });
        /** @type {__VLS_StyleScopedClasses['v']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (row.v);
        // @ts-ignore
        [summaryUnavailable, outRecord, outRows, outStale, UNAVAILABLE,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "note" },
    });
    /** @type {__VLS_StyleScopedClasses['note']} */ ;
    if (outStale.value) {
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "note" },
    });
    /** @type {__VLS_StyleScopedClasses['note']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sep" },
});
/** @type {__VLS_StyleScopedClasses['sep']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-head-tag" },
});
/** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ class: "td-btn primary reflow" },
    type: "button",
    disabled: (!gateState.value.enabled),
});
/** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['reflow']} */ ;
(gateState.value.enabled ? `回灌孪生 · ${gateState.value.point} 已回灌` : '回灌孪生 · 当前断面不可用');
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "gate-line" },
});
/** @type {__VLS_StyleScopedClasses['gate-line']} */ ;
(gateState.value.text);
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "note" },
});
/** @type {__VLS_StyleScopedClasses['note']} */ ;
(gateState.value.reason);
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "note" },
});
/** @type {__VLS_StyleScopedClasses['note']} */ ;
// @ts-ignore
[outStale, gateState, gateState, gateState, gateState, gateState,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
