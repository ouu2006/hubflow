/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 场景注入面板(Issue #77 决策层「决策可视化」的可调控段之一)。
//
// 口径铁律(违反即不通过):
//   ① **场景注入 ≠ 人工置位**。手册 §:2222 规定管理端人工置位的口子只有 F07 / F08 / F11
//      (交通事故 / 施工管制 / 大型活动);天气(F01)、昼夜(F02)、列车到发(F03)、时段日历(F10)
//      是**环境上下文**,走 `POST /api/traffic/scenario` 这个独立口子。本面板必须写明这一点,
//      不得把两者混称。
//   ② 天气 / 时段为**编造的演示值**,面板头常驻「演示数据(模拟)」。
//   ③ mock 模式:注入后判级 / CI / 建议 / 预测随之重算,面板显示注入前后对照;
//      **真接口模式(traffic.py)**:接口层只更新环境上下文与 derived_factors、**不重算判级 / ci**,
//      所以 effects 如实为空 —— 面板只显示「已注入 / 折算因素」，不伪造等级变化(判级由感知层统一重算)。
import { computed, ref } from 'vue';
import { postTrafficScenario, postTrafficScenarioReset } from '../../../api/traffic';
import { USE_MOCK } from '../../../shared/env';
const { defineProps, defineEmits, } = {};
const props = defineProps();
const emit = defineEmits();
const WEATHERS = ['晴', '多云', '小雨', '大雨', '大雾', '台风'];
const SESSIONS = ['早高峰', '平峰', '晚高峰', '夜间'];
const weather = ref(null);
const session = ref(null);
const demandMult = ref(1.0);
/**
 * 需求倍率是否**被显式调过**。
 * 没调过就**不发** `demand_mult` —— 服务端只在收到该字段时才用它,否则按所选时段的
 * F10 倍率折算(独立审查发现:恒发 `demand_mult: 1.0` 会让「时段」单独点选对判级零效果)。
 */
const demandTouched = ref(false);
const result = ref(null);
const msg = ref('');
const busy = ref(false);
/** 当前选中路段在注入前后的判级对照(服务端返回的 effects 里取) */
const effect = computed(() => {
    const e = result.value?.effects.find((x) => x.segment_id === props.segmentId);
    return e ?? null;
});
async function apply() {
    if (busy.value)
        return;
    busy.value = true;
    msg.value = '';
    try {
        // 取消选中的芯片发**显式 null**(= 清除该项),不是省略——省略会被服务端当作"不改",
        // 页面显示"没选"而旧值仍在生效(独立审查 Sourcery 提出的口径漏洞)。
        result.value = await postTrafficScenario({
            weather: weather.value,
            session: session.value,
            demand_mult: demandTouched.value ? demandMult.value : undefined,
            segment_id: props.segmentId || undefined,
        });
        msg.value = USE_MOCK
            ? '已注入(服务端重算判级 / CI,演示口径)'
            : '已注入（接口层只更新环境上下文与折算因素；判级由感知层统一重算，接口层不重算；接口层内存态，重启复位）';
        emit('changed');
    }
    catch (e) {
        msg.value = `注入失败:${e instanceof Error ? e.message : String(e)}`;
    }
    finally {
        busy.value = false;
    }
}
async function applyPreset(key) {
    // `demand` = 该档要显式注入的需求倍率;不给就是"按所选时段的 F10 倍率折算"(服务端算)
    const map = {
        baseline: { weather: '晴', session: '平峰' },
        'rain-peak': { weather: '大雨', session: '晚高峰' },
        'fog-night': { weather: '大雾', session: '夜间' },
        'train-burst': { weather: '多云', session: '平峰', demand: 1.35 },
        'accident-loop': { weather: '多云', session: '早高峰', demand: 1.2 },
    };
    const p = map[key];
    if (!p)
        return;
    weather.value = p.weather ?? null;
    session.value = p.session ?? null;
    demandTouched.value = p.demand !== undefined;
    demandMult.value = p.demand ?? 1.0;
    await apply();
}
async function reset() {
    if (busy.value)
        return;
    busy.value = true;
    try {
        await postTrafficScenarioReset();
        weather.value = null;
        session.value = null;
        demandTouched.value = false;
        demandMult.value = 1.0;
        result.value = null;
        msg.value = '已复位到站点包默认环境';
        emit('changed');
    }
    catch (e) {
        msg.value = `复位失败:${e instanceof Error ? e.message : String(e)}`;
    }
    finally {
        busy.value = false;
    }
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
__VLS_withDotValue(weather, {});
// @ts-ignore
__VLS_withDotValue(session, {});
// @ts-ignore
__VLS_withDotValue(demandTouched, {});
// @ts-ignore
__VLS_withDotValue(demandMult, {});
// @ts-ignore
__VLS_withDotValue(USE_MOCK, {});
// @ts-ignore
__VLS_withDotValue(effect, {});
// @ts-ignore
__VLS_withDotValue(result, {});
// @ts-ignore
__VLS_withDotValue(msg, {});
void {};
/** @type {__VLS_StyleScopedClasses['ctl-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['note']} */ ;
/** @type {__VLS_StyleScopedClasses['ctl-row']} */ ;
/** @type {__VLS_StyleScopedClasses['ctl-k']} */ ;
/** @type {__VLS_StyleScopedClasses['ctl-row']} */ ;
/** @type {__VLS_StyleScopedClasses['range']} */ ;
/** @type {__VLS_StyleScopedClasses['cmp']} */ ;
/** @type {__VLS_StyleScopedClasses['sec-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-row']} */ ;
/** @type {__VLS_StyleScopedClasses['ctl-k']} */ ;
/** @type {__VLS_StyleScopedClasses['note']} */ ;
/** @type {__VLS_StyleScopedClasses['inline']} */ ;
/** @type {__VLS_StyleScopedClasses['range']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
    ...{ class: "sec" },
});
/** @type {__VLS_StyleScopedClasses['sec']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sec-head" },
});
/** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-chip warn" },
});
/** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['warn']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "sec-tag" },
});
/** @type {__VLS_StyleScopedClasses['sec-tag']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "note" },
});
/** @type {__VLS_StyleScopedClasses['note']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "chips" },
});
/** @type {__VLS_StyleScopedClasses['chips']} */ ;
const __VLS_0 = __VLS_tryAsConstant((__VLS_ctx.presets));
for (const [p] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                return (applyPreset(p.key));
                // @ts-ignore
                [presets,];
            } },
        key: (p.key),
        ...{ class: "td-chip pick" },
        role: "button",
        title: (p.note),
    });
    /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
    /** @type {__VLS_StyleScopedClasses['pick']} */ ;
    (p.name);
    if (p.factor_ids.length > 0) {
        (p.factor_ids.join('+'));
    }
    // @ts-ignore
    [];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "ctl-row" },
});
/** @type {__VLS_StyleScopedClasses['ctl-row']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "ctl-k" },
});
/** @type {__VLS_StyleScopedClasses['ctl-k']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "chips" },
});
/** @type {__VLS_StyleScopedClasses['chips']} */ ;
const __VLS_1 = __VLS_tryAsConstant((__VLS_unwrap(WEATHERS, {})));
for (const [w] of __VLS_vFor(__VLS_nonNull(__VLS_1))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                return (weather.value = weather.value === w ? null : w);
                // @ts-ignore
                [WEATHERS, weather, weather,];
            } },
        key: (w),
        ...{ class: "td-chip pick" },
        ...{ class: ({ on: weather.value === w }) },
        role: "button",
        'aria-pressed': (weather.value === w),
    });
    /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
    /** @type {__VLS_StyleScopedClasses['pick']} */ ;
    /** @type {__VLS_StyleScopedClasses['on']} */ ;
    (w);
    // @ts-ignore
    [weather, weather,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "ctl-row" },
});
/** @type {__VLS_StyleScopedClasses['ctl-row']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "ctl-k" },
});
/** @type {__VLS_StyleScopedClasses['ctl-k']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "chips" },
});
/** @type {__VLS_StyleScopedClasses['chips']} */ ;
const __VLS_2 = __VLS_tryAsConstant((__VLS_unwrap(SESSIONS, {})));
for (const [s] of __VLS_vFor(__VLS_nonNull(__VLS_2))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                return (session.value = session.value === s ? null : s);
                // @ts-ignore
                [SESSIONS, session, session,];
            } },
        key: (s),
        ...{ class: "td-chip pick" },
        ...{ class: ({ on: session.value === s }) },
        role: "button",
        'aria-pressed': (session.value === s),
    });
    /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
    /** @type {__VLS_StyleScopedClasses['pick']} */ ;
    /** @type {__VLS_StyleScopedClasses['on']} */ ;
    (s);
    // @ts-ignore
    [session, session,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "ctl-row" },
});
/** @type {__VLS_StyleScopedClasses['ctl-row']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "ctl-k" },
});
/** @type {__VLS_StyleScopedClasses['ctl-k']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.input)({
    ...{ onInput: // @ts-ignore
        (...[$event]) => {
            void $event;
            return (demandTouched.value = true);
            // @ts-ignore
            [demandTouched,];
        } },
    ...{ class: "range" },
    type: "range",
    min: "0.4",
    max: "2",
    step: "0.05",
});
(demandMult.value);
/** @type {__VLS_StyleScopedClasses['range']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "ctl-v td-num" },
});
/** @type {__VLS_StyleScopedClasses['ctl-v']} */ ;
/** @type {__VLS_StyleScopedClasses['td-num']} */ ;
(demandMult.value.toFixed(2));
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "ctl-tag" },
    ...{ class: ({ on: demandTouched.value }) },
});
/** @type {__VLS_StyleScopedClasses['ctl-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['on']} */ ;
(demandTouched.value ? '已手动指定' : '跟随所选时段');
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "btn-row" },
});
/** @type {__VLS_StyleScopedClasses['btn-row']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (apply) },
    type: "button",
    ...{ class: "td-btn primary" },
    disabled: (__VLS_unwrap(busy, {})),
});
/** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
(USE_MOCK.value ? '注入并重算' : '注入环境上下文');
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (reset) },
    type: "button",
    ...{ class: "td-btn" },
    disabled: (__VLS_unwrap(busy, {})),
});
/** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "note inline" },
});
/** @type {__VLS_StyleScopedClasses['note']} */ ;
/** @type {__VLS_StyleScopedClasses['inline']} */ ;
(__VLS_ctx.ctx ? `${__VLS_ctx.ctx.weather.condition ?? '天气未接入'} · ${__VLS_ctx.ctx.time.session}` : '—');
if (__VLS_ctx.ctx) {
    (__VLS_ctx.ctx.injected ? '已注入' : '站点包默认');
}
if (effect.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cmp" },
    });
    /** @type {__VLS_StyleScopedClasses['cmp']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "cmp-k" },
    });
    /** @type {__VLS_StyleScopedClasses['cmp-k']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "cmp-v" },
    });
    /** @type {__VLS_StyleScopedClasses['cmp-v']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    (effect.value.level_before);
    (effect.value.level_after);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "sep" },
    });
    /** @type {__VLS_StyleScopedClasses['sep']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
        ...{ class: "td-num" },
    });
    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
    (effect.value.x_before);
    (effect.value.x_after);
}
else if (result.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "note msg" },
    });
    /** @type {__VLS_StyleScopedClasses['note']} */ ;
    /** @type {__VLS_StyleScopedClasses['msg']} */ ;
    (result.value.effects_note ?? '接口层未返回注入前后判级对照（判级由感知层统一重算，前端不自己算）');
}
if (result.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "note msg" },
    });
    /** @type {__VLS_StyleScopedClasses['note']} */ ;
    /** @type {__VLS_StyleScopedClasses['msg']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    (result.value.factors.map((f) => `${f.factor_id} ${f.name} ×${f.multiplier}`).join('；') || '无（当前环境不产生 F01/F02/F03/F10）');
}
if (msg.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "note msg" },
    });
    /** @type {__VLS_StyleScopedClasses['note']} */ ;
    /** @type {__VLS_StyleScopedClasses['msg']} */ ;
    (msg.value);
}
// @ts-ignore
[demandTouched, demandTouched, demandMult, demandMult, busy, busy, USE_MOCK, ctx, ctx, ctx, ctx, ctx, effect, effect, effect, effect, effect, result, result, result, result, msg, msg,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
