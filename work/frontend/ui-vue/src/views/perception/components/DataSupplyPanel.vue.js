/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 数据供给 ↔ 需求对照带(Issue #77 三页收敛 · 感知层)。
//
// 业主口径:「感知层 yolo 获取图像数据,将**能获取的数据**和**要用到的数据**都出现在这个感知层上面来」。
// 本卡就是把这两列并排摆出来,中间标出**映射关系与缺口**:
//   · 左列「能获取的数据」= 感知链路实际产出的东西(逐帧检测框 / 轨迹 / 透视标定 / 四项指标);
//   · 右列「要用到的数据」= 下游(判级 / 决策 / 大屏)真正消费的字段(路段级 q / v / k / L_q / x / ci / level);
//   · 中间 = 一条通道 → 一条路段的映射,以及**缺什么、缺在哪一步**。
//
// ⚠️ 口径铁律(违反即不通过):
//   ① 拿不到的字段一律「—」并注明出处,**绝不用前端推算值或设计稿示例值冒充**;
//   ② 三分口径沿用感知页既有纪律:「未导出(服务端无该路)」「读取失败(接口报错)」「无检出(数据为空)」
//      分开显示,失败不得静默成"无检出";
//   ③ 全部 `is_simulated = true`,页面不出现「实测 / 实时 / 现场」。
import { computed } from 'vue';
import { UNAVAILABLE, isStale } from '../../../shared/traffic';
import { fmtDur } from './channels';
const { defineProps, } = {};
const props = defineProps();
/** 当前通道状态 */
const ch = computed(() => props.channels.find((c) => c.def.source === props.current.source) ?? null);
/** 该通道映射路段的 video 槽位(判级链路真正吃进去的那一份) */
const videoSlot = computed(() => props.sourcePair?.slots.find((s) => s.source === 'video')?.record ?? null);
/** 状态四分的文字(未接入视频源 / 未导出 / 读取失败 / 已导出),与通道台账同口径 */
const exportState = computed(() => {
    const c = ch.value;
    if (!c)
        return { text: '—', cls: 'out' };
    if (!c.def.hasVideo)
        return { text: '未接入视频源', cls: 'out' };
    if (c.meta === null)
        return { text: '未导出', cls: 'out' };
    if (c.detFailed)
        return { text: '读取失败', cls: 'err' };
    return { text: '已导出', cls: 'ok' };
});
const supplyRows = computed(() => {
    const c = ch.value;
    const m = c?.meta ?? null;
    const det = c?.det ?? null;
    if (c && !c.def.hasVideo) {
        // 未接入视频源(Issue IKLX5Y):不是"未导出"——本路压根还没接视频,四行全空且缺口写清
        return [
            { name: '样本视频帧', value: '—', ok: false, gap: '该通道未接入视频源（路网上已布点，本期留空）' },
            { name: '逐帧检测框 / 轨迹', value: '—', ok: false, gap: '无源可处理' },
            { name: '透视标定(RANGE / RMSE)', value: '—', ok: false, gap: '无源可标定' },
            { name: '四项指标 q / v / k / L_q', value: '—', ok: false, gap: '依赖上三项，当前不可用' },
        ];
    }
    if (!m) {
        return [
            { name: '样本视频帧', value: '—', ok: false, gap: '该通道未导出(服务端无此路)' },
            { name: '逐帧检测框 / 轨迹', value: '—', ok: false, gap: '该通道未导出' },
            { name: '透视标定(RANGE / RMSE)', value: '—', ok: false, gap: '由感知服务 /summary 提供,当前未实现' },
            { name: '四项指标 q / v / k / L_q', value: '—', ok: false, gap: '依赖上两项,当前不可用' },
        ];
    }
    const detTotal = c?.detTotal ?? null;
    return [
        {
            name: '样本视频帧',
            value: `${m.width}×${m.height} · ${m.fps} fps · 时长 ${fmtDur(m.duration_s)} · ${m.total_frames} 帧`,
            ok: true,
        },
        {
            name: '逐帧检测框 / 轨迹',
            value: c?.detFailed
                ? '—'
                : `轨迹 ${m.track_total} · 检测框 ${detTotal === null ? '—' : detTotal}`,
            ok: !c?.detFailed,
            gap: c?.detFailed ? 'detections 接口报错(是接口故障,不是"无检出")' : undefined,
        },
        {
            name: '目标检测 / 跟踪模型',
            value: `${m.model} · ${m.backend} · conf ${m.conf_threshold}`,
            ok: true,
        },
        {
            name: '透视标定(RANGE / RMSE)',
            value: '—',
            ok: false,
            gap: '由感知服务 /summary 提供,当前未实现(前端无复算条件)',
        },
        {
            name: '四项指标 q / v / k / L_q',
            value: det ? '经标定折算后进入路段指标(见右列)' : '—',
            ok: false,
            gap: '标定不可用时四项指标不可用;当前右列取自站点包演示基线',
        },
    ];
});
const slot = computed(() => videoSlot.value);
function num(v, digits = 2) {
    return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—';
}
const demandRows = computed(() => {
    const r = slot.value;
    if (!r) {
        return [
            { name: '饱和度 x', unit: '', value: '—', fromVideo: false, note: '该路段无视频链路槽位' },
            { name: '车速 v', unit: 'km/h', value: '—', fromVideo: false },
            { name: '流量 q', unit: '辆/h', value: '—', fromVideo: false },
            { name: '密度 k', unit: '辆/km', value: '—', fromVideo: false },
            { name: '排队长度 L_q', unit: 'm', value: '—', fromVideo: false },
            { name: '拥堵等级 level', unit: '', value: '—', fromVideo: false },
            { name: '拥挤指数 ci', unit: '', value: '—', fromVideo: false },
        ];
    }
    const stale = isStale(r);
    return [
        { name: '饱和度 x', unit: '', value: num(r.x), fromVideo: true },
        { name: '车速 v', unit: 'km/h', value: num(r.v_kmh, 1), fromVideo: true },
        { name: '流量 q', unit: '辆/h', value: num(r.q_vph, 0), fromVideo: true },
        { name: '密度 k', unit: '辆/km', value: num(r.k_vpk, 1), fromVideo: true },
        { name: '排队长度 L_q', unit: 'm', value: num(r.L_q_m, 0), fromVideo: true },
        {
            name: '拥堵等级 level',
            unit: '',
            value: stale ? UNAVAILABLE.name : String(r.level),
            fromVideo: true,
            note: stale ? '数据陈旧(data_age_s > 120s)' : undefined,
        },
        { name: '拥挤指数 ci', unit: '', value: num(r.ci, 1), fromVideo: true },
    ];
});
/** 缺口汇总(两侧一比,说清"缺什么"而不是"缺几项") */
const gaps = computed(() => {
    const out = [];
    const c = ch.value;
    if (c && !c.def.hasVideo) {
        out.push('该通道未接入视频源(路网上已布点、本期视频留空):检测框 / 轨迹 / 标定 / 四项指标全部不可用');
    }
    else if (!c?.meta) {
        out.push('该通道样本视频未导出:检测框 / 轨迹 / 标定 / 四项指标全部不可用');
    }
    else if (c.detFailed) {
        out.push('detections 接口报错:该路检测框不可用(接口故障,非"无检出")');
    }
    if (c?.meta)
        out.push('透视标定与轨迹质量(SVR / Q / RANGE-RMSE)由感知服务 /summary 提供,当前未实现');
    out.push('路段级四项指标当前取自**站点包演示基线**(预置值 + 抖动),不是感知链路的实测产出');
    return out;
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
__VLS_withDotValue(exportState, {});
void {};
/** @type {__VLS_StyleScopedClasses['sup-row']} */ ;
/** @type {__VLS_StyleScopedClasses['sup-row']} */ ;
/** @type {__VLS_StyleScopedClasses['s-val']} */ ;
/** @type {__VLS_StyleScopedClasses['s-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['s-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['supply-body']} */ ;
/** @type {__VLS_StyleScopedClasses['sup-col']} */ ;
/** @type {__VLS_StyleScopedClasses['sup-mid']} */ ;
/** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['s-gap']} */ ;
/** @type {__VLS_StyleScopedClasses['sup-row']} */ ;
/** @type {__VLS_StyleScopedClasses['s-name']} */ ;
/** @type {__VLS_StyleScopedClasses['supply-card']} */ ;
/** @type {__VLS_StyleScopedClasses['sup-col']} */ ;
/** @type {__VLS_StyleScopedClasses['sup-mid']} */ ;
/** @type {__VLS_StyleScopedClasses['s-name']} */ ;
/** @type {__VLS_StyleScopedClasses['s-val']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-band']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
    ...{ class: "td-card supply-card" },
});
/** @type {__VLS_StyleScopedClasses['td-card']} */ ;
/** @type {__VLS_StyleScopedClasses['supply-card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-head" },
});
/** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
(__VLS_ctx.current.cid);
(__VLS_ctx.current.source);
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-head-tag" },
});
/** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-chip" },
    ...{ class: (exportState.value.cls) },
});
/** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
(exportState.value.text);
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-chip warn" },
});
/** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['warn']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-body supply-body" },
});
/** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
/** @type {__VLS_StyleScopedClasses['supply-body']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sup-col" },
});
/** @type {__VLS_StyleScopedClasses['sup-col']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "col-title" },
});
/** @type {__VLS_StyleScopedClasses['col-title']} */ ;
const __VLS_0 = __VLS_tryAsConstant((__VLS_unwrap(supplyRows, {})));
for (const [r] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        key: (r.name),
        ...{ class: "sup-row" },
        ...{ class: ({ bad: !r.ok }) },
    });
    /** @type {__VLS_StyleScopedClasses['sup-row']} */ ;
    /** @type {__VLS_StyleScopedClasses['bad']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "s-name" },
    });
    /** @type {__VLS_StyleScopedClasses['s-name']} */ ;
    (r.name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "s-val td-mono" },
    });
    /** @type {__VLS_StyleScopedClasses['s-val']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
    (r.value);
    if (r.gap) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "s-gap" },
        });
        /** @type {__VLS_StyleScopedClasses['s-gap']} */ ;
        (r.gap);
    }
    // @ts-ignore
    [current, current, exportState, exportState, supplyRows,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sup-mid" },
});
/** @type {__VLS_StyleScopedClasses['sup-mid']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "arrow" },
});
/** @type {__VLS_StyleScopedClasses['arrow']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "map-note" },
});
/** @type {__VLS_StyleScopedClasses['map-note']} */ ;
(__VLS_ctx.current.cid);
__VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
    ...{ class: "td-mono" },
});
/** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
(__VLS_ctx.current.segmentId);
__VLS_asFunctionalElement1(__VLS_intrinsics.br)({});
(__VLS_ctx.current.name);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "arrow" },
});
/** @type {__VLS_StyleScopedClasses['arrow']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sup-col" },
});
/** @type {__VLS_StyleScopedClasses['sup-col']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "col-title" },
});
/** @type {__VLS_StyleScopedClasses['col-title']} */ ;
const __VLS_1 = __VLS_tryAsConstant((__VLS_unwrap(demandRows, {})));
for (const [r] of __VLS_vFor(__VLS_nonNull(__VLS_1))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        key: (r.name),
        ...{ class: "sup-row" },
    });
    /** @type {__VLS_StyleScopedClasses['sup-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "s-name" },
    });
    /** @type {__VLS_StyleScopedClasses['s-name']} */ ;
    (r.name);
    if (r.unit) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "unit" },
        });
        /** @type {__VLS_StyleScopedClasses['unit']} */ ;
        (r.unit);
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "s-val td-num" },
    });
    /** @type {__VLS_StyleScopedClasses['s-val']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
    (r.value);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "s-tag" },
        ...{ class: (r.fromVideo ? 'ok' : 'out') },
    });
    /** @type {__VLS_StyleScopedClasses['s-tag']} */ ;
    (r.fromVideo ? '视频链路槽位' : '无此槽位');
    if (r.note) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "s-gap" },
        });
        /** @type {__VLS_StyleScopedClasses['s-gap']} */ ;
        (r.note);
    }
    // @ts-ignore
    [current, current, current, demandRows,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "gap-band" },
});
/** @type {__VLS_StyleScopedClasses['gap-band']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "gap-title" },
});
/** @type {__VLS_StyleScopedClasses['gap-title']} */ ;
const __VLS_2 = __VLS_tryAsConstant((__VLS_unwrap(gaps, {})));
for (const [g, i] of __VLS_vFor(__VLS_nonNull(__VLS_2))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        key: (i),
        ...{ class: "gap-item" },
    });
    /** @type {__VLS_StyleScopedClasses['gap-item']} */ ;
    (g);
    // @ts-ignore
    [gaps,];
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
