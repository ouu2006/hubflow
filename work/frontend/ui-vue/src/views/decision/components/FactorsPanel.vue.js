/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 右栏 ① · 因素与预测(人工置位段)。
// 依据:手册第 19 章「管理端人工置位口子」= F07 事故/故障车、F08 施工/临时管制、F11 大型活动,
//   与 shared/demoDecision.ts 的 MANUAL_FACTOR_PRESETS 同一份清单(三行)。
// 口径:置位走 POST /api/traffic/factors;mock 模式在 mock 内存态里生效并重算判级(演示行为),
//   真接口模式(traffic.py)只登记因素状态、**不重算判级**(判级由感知层统一重算)——
//   两种模式的文案必须分开说,不能把"已登记"说成"判级已变";
//   当前是否已置位以 GET /api/traffic/factors?segment_id= 为准(不靠纯本地态,免得刷新后说假话);
//   "已置位"开关用**品牌蓝**(「当前生效」语义)——不用成功绿,避免与等级色(畅通绿 #2BA471)撞车(硬性口径 4)。
import { onMounted, reactive, ref, watch } from 'vue';
import { getTrafficFactors, postTrafficFactor, postTrafficFactorReset } from '../../../api/traffic';
import { MANUAL_FACTOR_PRESETS } from '../../../shared/demoDecision';
import { MEMORY_STATE_LABEL, USE_MOCK } from '../../../shared/env';
const { defineProps, defineEmits, } = {};
const props = defineProps();
const emit = defineEmits();
const placed = reactive({});
const msg = ref('');
const busy = ref(false);
/** 合成下限(设计稿注):展示口径,阈值真源见 stations/thresholds.json */
const SYNTH_FLOOR = '合成下限 40%';
async function load() {
    for (const p of MANUAL_FACTOR_PRESETS)
        placed[p.factor_id] = false;
    if (!props.segmentId)
        return;
    try {
        const res = await getTrafficFactors(props.segmentId);
        const ids = new Set(res.factors.map((f) => f.factor_id));
        for (const p of MANUAL_FACTOR_PRESETS)
            placed[p.factor_id] = ids.has(p.factor_id);
    }
    catch {
        /* 接口层未起:保持未置位,不编造 */
    }
}
async function apply(factorId) {
    const preset = MANUAL_FACTOR_PRESETS.find((p) => p.factor_id === factorId);
    if (!preset || !props.segmentId || busy.value)
        return;
    busy.value = true;
    try {
        const r = await postTrafficFactor({
            segment_id: props.segmentId,
            factor_id: preset.factor_id,
            name: preset.name,
            target: preset.target,
            multiplier: preset.multiplier,
        });
        msg.value =
            r.level_recomputed === false
                ? `已置位 ${preset.factor_id} → ${props.segmentId}（接口层内存态，重启复位）；只登记因素状态，判级由感知层统一重算、接口层不重算`
                : `已置位 ${preset.factor_id} → ${props.segmentId} 判级「${r.level_name}」(${MEMORY_STATE_LABEL},60 分钟后自动过期)`;
        emit('changed');
        await load();
    }
    catch {
        msg.value = USE_MOCK ? '置位失败(mock 中间件未起?)' : '置位失败(接口层未起? 先启动 traffic.py)';
    }
    finally {
        busy.value = false;
    }
}
function toggle(factorId) {
    if (placed[factorId]) {
        msg.value = '单条撤销请用下方「复位」（当前只提供整体复位口子）';
        return;
    }
    void apply(factorId);
}
async function reset() {
    if (busy.value)
        return;
    busy.value = true;
    try {
        await postTrafficFactorReset();
        msg.value = '已清空全部人工置位';
        emit('changed');
        await load();
    }
    catch {
        msg.value = '复位失败(接口层未起?)';
    }
    finally {
        busy.value = false;
    }
}
onMounted(() => {
    void load();
});
watch(() => props.segmentId, () => {
    msg.value = '';
    void load();
});
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
__VLS_withDotValue(placed, {});
// @ts-ignore
__VLS_withDotValue(busy, {});
// @ts-ignore
__VLS_withDotValue(msg, {});
void {};
/** @type {__VLS_StyleScopedClasses['sw']} */ ;
/** @type {__VLS_StyleScopedClasses['sw']} */ ;
/** @type {__VLS_StyleScopedClasses['sw']} */ ;
/** @type {__VLS_StyleScopedClasses['frow']} */ ;
/** @type {__VLS_StyleScopedClasses['sw']} */ ;
/** @type {__VLS_StyleScopedClasses['foot-row']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
    ...{ class: "td-card" },
});
/** @type {__VLS_StyleScopedClasses['td-card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-head" },
});
/** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-head-tag td-mono" },
});
/** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
(__VLS_ctx.segmentId || '—');
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-body" },
});
/** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sub" },
});
/** @type {__VLS_StyleScopedClasses['sub']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "dim" },
});
/** @type {__VLS_StyleScopedClasses['dim']} */ ;
(__VLS_unwrap(SYNTH_FLOOR, {}));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "rows" },
});
/** @type {__VLS_StyleScopedClasses['rows']} */ ;
const __VLS_0 = __VLS_tryAsConstant((__VLS_unwrap(MANUAL_FACTOR_PRESETS, {})));
for (const [p] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        key: (p.factor_id),
        ...{ class: "frow" },
        title: (`${p.name} · ${p.note}`),
    });
    /** @type {__VLS_StyleScopedClasses['frow']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "fid td-mono" },
    });
    /** @type {__VLS_StyleScopedClasses['fid']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
    (p.factor_id);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "fname" },
    });
    /** @type {__VLS_StyleScopedClasses['fname']} */ ;
    (p.name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                return (toggle(p.factor_id));
                // @ts-ignore
                [segmentId, SYNTH_FLOOR, MANUAL_FACTOR_PRESETS,];
            } },
        type: "button",
        ...{ class: "sw" },
        ...{ class: ({ on: placed.value[p.factor_id] }) },
        disabled: (busy.value || !__VLS_ctx.segmentId),
    });
    /** @type {__VLS_StyleScopedClasses['sw']} */ ;
    /** @type {__VLS_StyleScopedClasses['on']} */ ;
    (placed.value[p.factor_id] ? '已置位' : '未置位');
    // @ts-ignore
    [segmentId, placed, placed, busy,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "foot-row" },
});
/** @type {__VLS_StyleScopedClasses['foot-row']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (reset) },
    type: "button",
    ...{ class: "td-btn sm" },
    disabled: (busy.value || !__VLS_ctx.segmentId),
});
/** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['sm']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "dim" },
});
/** @type {__VLS_StyleScopedClasses['dim']} */ ;
(__VLS_unwrap(MEMORY_STATE_LABEL, {}));
if (msg.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "msg" },
    });
    /** @type {__VLS_StyleScopedClasses['msg']} */ ;
    (msg.value);
}
// @ts-ignore
[segmentId, busy, MEMORY_STATE_LABEL, msg, msg,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
