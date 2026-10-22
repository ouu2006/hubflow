/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 大屏右栏 · 直接下令（Issue IKMS18 大屏监控平台化）。
//
// 目标：像监控管理平台一样，在**大屏路段详情卡里**完成「选告警 → 下发（渠道 / 分流比例）→ 回执 → 回写」，
// 调用的是与决策页完全相同的接口（`POST /plan/dispatch` / `POST /plan/ack`），
// 状态存在接口层进程内存（重启复位）→ 大屏与决策页读同一个 `GET /alerts`，状态共享。
//
// 不造假口径：
//   · 该路段无快照记录 → 不提供下令入口（没有指标可依据，不伪造）；
//   · 该路段无关联告警 / 只剩终态告警 → 控件 disabled + 如实文案，不假装可操作；
//   · 回写必须先有下发回执（TC-07 闭环顺序），无回执时提交按钮 disabled 并给原因；
//   · 渠道是展示枚举、一期无真实下发通道、后端内存态 → 卡片内常驻说明（不得说成真实下发）。
import { computed, ref, watch } from 'vue';
import { RouterLink } from 'vue-router';
import { postPlanAck, postPlanDispatch } from '../../../api/traffic';
import { DISPATCH_CHANNELS, diversionSuggestions, fallbackSuggestion, } from '../../../shared/demoDecision';
import { formatClock } from '../../../shared/traffic';
const { defineProps, defineEmits, } = {};
const props = defineProps();
const emit = defineEmits();
const TERMINAL = ['已闭环', '误报'];
const RESULTS = ['已消除', '已缓解', '未改善', '误报'];
function isTerminal(status) {
    return TERMINAL.includes(status);
}
const candidates = computed(() => props.alerts.filter((alert) => alert.segment_id === props.segmentId));
const active = computed(() => candidates.value.filter((alert) => !isTerminal(alert.status)));
const terminalCount = computed(() => candidates.value.length - active.value.length);
const selectedId = ref(null);
const selectedAlert = computed(() => active.value.find((alert) => alert.alert_id === selectedId.value) ?? null);
const channel = ref(DISPATCH_CHANNELS[0]);
const pct = ref(20);
const operator = ref('张工(大屏)');
const action = ref('');
const result = ref('已缓解');
const busy = ref(false);
const error = ref('');
const ackMsg = ref('');
/** 本次会话刚拿到的回执（服务端留痕刷新前先显示；刷新后以 /alerts 为准） */
const localReceipt = ref(null);
/** 用户是否手改过处置动作（没改过时随分流比例联动默认文案） */
const actionTouched = ref(false);
function isAutoAction(text) {
    return text === '' || text.startsWith('情报板诱导 · 分流');
}
function resetForm() {
    const alert = selectedAlert.value;
    localReceipt.value = null;
    error.value = '';
    ackMsg.value = '';
    actionTouched.value = false;
    channel.value = DISPATCH_CHANNELS[0];
    result.value = '已缓解';
    operator.value = '张工(大屏)';
    const suggestion = diversionSuggestions()[props.segmentId] ?? fallbackSuggestion(props.segmentId);
    pct.value = suggestion.base_pct > 0 ? suggestion.base_pct : 20;
    action.value = suggestion.base_pct > 0
        ? `情报板诱导 · 分流至${suggestion.target_name} ${pct.value}%`
        : `情报板诱导 · 分流 ${pct.value}%`;
    void alert;
}
function ensureSelection() {
    if (!active.value.some((alert) => alert.alert_id === selectedId.value)) {
        selectedId.value = active.value[0]?.alert_id ?? null;
        resetForm();
    }
}
watch(() => props.segmentId, () => {
    selectedId.value = null;
    ensureSelection();
}, { immediate: true });
watch(active, ensureSelection);
watch(pct, (value) => {
    if (!actionTouched.value || isAutoAction(action.value)) {
        action.value = `情报板诱导 · 分流 ${value}%`;
    }
});
/** 权威回执：优先本次会话回执；否则从服务端 /alerts 留痕还原（channels + dispatch_at + ratio） */
const receipt = computed(() => {
    const alert = selectedAlert.value;
    if (!alert)
        return null;
    if (localReceipt.value && localReceipt.value.alert_id === alert.alert_id)
        return localReceipt.value;
    if (alert.dispatch_at && alert.channels && alert.channels.length > 0) {
        const ch = alert.channels[0] ?? '—';
        return {
            alert_id: alert.alert_id,
            channel: ch,
            ratio_pct: alert.dispatch_ratio_pct,
            receipt: `${ch}已确认`,
            at: alert.dispatch_at,
            is_simulated: true,
        };
    }
    return null;
});
const dispatched = computed(() => receipt.value !== null);
const terminal = computed(() => (selectedAlert.value ? isTerminal(selectedAlert.value.status) : false));
/** 本段告警的处置留痕（下发回执 + 回写四项）——告警转终态后仍可见（TC-07） */
const historyRows = computed(() => candidates.value
    .filter((alert) => alert.dispatch_at || alert.writeback)
    .map((alert) => ({
    alert,
    dispatch: alert.dispatch_at
        ? `${(alert.channels ?? ['—']).join(' / ')} · 分流 ${alert.dispatch_ratio_pct ?? '—'}% · ${formatClock(alert.dispatch_at)}`
        : '—',
    writeback: alert.writeback
        ? `${alert.writeback.operator} · ${alert.writeback.action} · 结果 ${alert.writeback.result} · ${formatClock(alert.writeback.at)}`
        : '—',
})));
const canDispatch = computed(() => Boolean(props.record) && selectedAlert.value !== null && !terminal.value && !busy.value);
const canAck = computed(() => Boolean(props.record) &&
    selectedAlert.value !== null &&
    !terminal.value &&
    dispatched.value &&
    !busy.value &&
    operator.value.trim() !== '' &&
    action.value.trim() !== '');
async function doDispatch() {
    const alert = selectedAlert.value;
    if (!alert || !canDispatch.value)
        return;
    busy.value = true;
    error.value = '';
    ackMsg.value = '';
    try {
        const r = await postPlanDispatch({
            alert_id: alert.alert_id,
            segment_id: alert.segment_id,
            channel: channel.value,
            ratio_pct: pct.value,
        });
        localReceipt.value = r;
        emit('changed');
    }
    catch (e) {
        error.value = `下发失败：${e instanceof Error ? e.message : String(e)}`;
    }
    finally {
        busy.value = false;
    }
}
async function doAck() {
    const alert = selectedAlert.value;
    if (!alert || !canAck.value)
        return;
    if (!dispatched.value) {
        error.value = '回写前置：请先下发并拿到回执（TC-07 闭环顺序：下发 → 回执 → 回写）';
        return;
    }
    busy.value = true;
    error.value = '';
    try {
        const r = await postPlanAck({
            alert_id: alert.alert_id,
            segment_id: alert.segment_id,
            operator: operator.value.trim(),
            action: action.value.trim(),
            result: result.value,
        });
        ackMsg.value = `回写成功：${r.result} → 状态「${r.status}」（以后端 /alerts 为准，决策页同步可见）`;
        emit('changed');
    }
    catch (e) {
        error.value = `回写失败：${e instanceof Error ? e.message : String(e)}`;
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
__VLS_withDotValue(active, {});
// @ts-ignore
__VLS_withDotValue(candidates, {});
// @ts-ignore
__VLS_withDotValue(selectedId, {});
// @ts-ignore
__VLS_withDotValue(selectedAlert, {});
// @ts-ignore
__VLS_withDotValue(receipt, {});
// @ts-ignore
__VLS_withDotValue(canDispatch, {});
// @ts-ignore
__VLS_withDotValue(channel, {});
// @ts-ignore
__VLS_withDotValue(canAck, {});
// @ts-ignore
__VLS_withDotValue(result, {});
// @ts-ignore
__VLS_withDotValue(actionTouched, {});
// @ts-ignore
__VLS_withDotValue(dispatched, {});
// @ts-ignore
__VLS_withDotValue(terminal, {});
// @ts-ignore
__VLS_withDotValue(ackMsg, {});
// @ts-ignore
__VLS_withDotValue(error, {});
// @ts-ignore
__VLS_withDotValue(historyRows, {});
void {};
/** @type {__VLS_StyleScopedClasses['wd']} */ ;
/** @type {__VLS_StyleScopedClasses['td-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ctl-row']} */ ;
/** @type {__VLS_StyleScopedClasses['chips']} */ ;
/** @type {__VLS_StyleScopedClasses['ctl-row']} */ ;
/** @type {__VLS_StyleScopedClasses['ctl-row']} */ ;
/** @type {__VLS_StyleScopedClasses['range']} */ ;
/** @type {__VLS_StyleScopedClasses['wb-row']} */ ;
/** @type {__VLS_StyleScopedClasses['wd']} */ ;
/** @type {__VLS_StyleScopedClasses['wd']} */ ;
/** @type {__VLS_StyleScopedClasses['grow']} */ ;
/** @type {__VLS_StyleScopedClasses['td-input']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-row']} */ ;
/** @type {__VLS_StyleScopedClasses['deep-link']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
    ...{ class: "cmd-card" },
});
/** @type {__VLS_StyleScopedClasses['cmd-card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sec-head" },
});
/** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-chip ok" },
});
/** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['ok']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-chip warn" },
});
/** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['warn']} */ ;
if (!__VLS_ctx.record) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "empty sm" },
    });
    /** @type {__VLS_StyleScopedClasses['empty']} */ ;
    /** @type {__VLS_StyleScopedClasses['sm']} */ ;
}
else {
    if (active.value.length === 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "empty sm" },
        });
        /** @type {__VLS_StyleScopedClasses['empty']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm']} */ ;
        if (candidates.value.length === 0) {
        }
        else {
            (__VLS_unwrap(terminalCount, {}));
        }
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "sub-head" },
        });
        /** @type {__VLS_StyleScopedClasses['sub-head']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "sub-tag" },
        });
        /** @type {__VLS_StyleScopedClasses['sub-tag']} */ ;
        if (active.value.length > 1) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "chips" },
            });
            /** @type {__VLS_StyleScopedClasses['chips']} */ ;
            const __VLS_0 = __VLS_tryAsConstant((active.value));
            for (const [alert] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ onClick: // @ts-ignore
                        (...[$event]) => {
                            void $event;
                            if (!!(!__VLS_ctx.record))
                                throw 0;
                            if (!!(active.value.length === 0))
                                throw 0;
                            if (!(active.value.length > 1))
                                throw 0;
                            selectedId.value = alert.alert_id;
                            resetForm();
                            // @ts-ignore
                            [record, active, active, active, candidates, terminalCount, selectedId,];
                        } },
                    key: (alert.alert_id),
                    ...{ class: "td-chip pick" },
                    ...{ class: ({ on: alert.alert_id === selectedId.value }) },
                    role: "button",
                    'aria-pressed': (alert.alert_id === selectedId.value),
                });
                /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
                /** @type {__VLS_StyleScopedClasses['pick']} */ ;
                /** @type {__VLS_StyleScopedClasses['on']} */ ;
                (alert.alert_id);
                (alert.status);
                // @ts-ignore
                [selectedId, selectedId,];
            }
        }
        if (selectedAlert.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "alert-line" },
            });
            /** @type {__VLS_StyleScopedClasses['alert-line']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "td-mono" },
            });
            /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
            (selectedAlert.value.alert_id);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "td-chip" },
            });
            /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
            (selectedAlert.value.status);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "tiny-inline" },
            });
            /** @type {__VLS_StyleScopedClasses['tiny-inline']} */ ;
            (__VLS_unwrap(formatClock, {})(selectedAlert.value.first_seen));
            if (receipt.value) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "tiny-inline" },
                });
                /** @type {__VLS_StyleScopedClasses['tiny-inline']} */ ;
                (receipt.value.ratio_pct ?? '—');
            }
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "sub-head" },
        });
        /** @type {__VLS_StyleScopedClasses['sub-head']} */ ;
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
        const __VLS_1 = __VLS_tryAsConstant((__VLS_unwrap(DISPATCH_CHANNELS, {})));
        for (const [item] of __VLS_vFor(__VLS_nonNull(__VLS_1))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ onClick: // @ts-ignore
                    (...[$event]) => {
                        void $event;
                        if (!!(!__VLS_ctx.record))
                            throw 0;
                        if (!!(active.value.length === 0))
                            throw 0;
                        return (canDispatch.value && (channel.value = item));
                        // @ts-ignore
                        [selectedAlert, selectedAlert, selectedAlert, selectedAlert, formatClock, receipt, receipt, DISPATCH_CHANNELS, canDispatch, channel,];
                    } },
                key: (item),
                ...{ class: "td-chip pick" },
                ...{ class: ({ on: item === channel.value }) },
                role: "button",
                'aria-pressed': (item === channel.value),
                'aria-disabled': (!canDispatch.value),
            });
            /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
            /** @type {__VLS_StyleScopedClasses['pick']} */ ;
            /** @type {__VLS_StyleScopedClasses['on']} */ ;
            (item);
            // @ts-ignore
            [canDispatch, channel, channel,];
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
            ...{ class: "range" },
            type: "range",
            min: "5",
            max: "100",
            step: "5",
            disabled: (!canDispatch.value),
        });
        (__VLS_unwrap(pct, {}));
        /** @type {__VLS_StyleScopedClasses['range']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "ctl-v td-num" },
        });
        /** @type {__VLS_StyleScopedClasses['ctl-v']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
        (__VLS_unwrap(pct, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "btn-row" },
        });
        /** @type {__VLS_StyleScopedClasses['btn-row']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (doDispatch) },
            ...{ class: "td-btn primary sm" },
            type: "button",
            disabled: (!canDispatch.value),
        });
        /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
        /** @type {__VLS_StyleScopedClasses['primary']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm']} */ ;
        (receipt.value ? '重新下发（覆盖回执）' : `下发 · ${channel.value}`);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "tiny-inline" },
        });
        /** @type {__VLS_StyleScopedClasses['tiny-inline']} */ ;
        if (receipt.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "receipt" },
            });
            /** @type {__VLS_StyleScopedClasses['receipt']} */ ;
            (receipt.value.receipt);
            (receipt.value.ratio_pct ?? '—');
            (__VLS_unwrap(formatClock, {})(receipt.value.at));
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "sub-head" },
        });
        /** @type {__VLS_StyleScopedClasses['sub-head']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "chips" },
        });
        /** @type {__VLS_StyleScopedClasses['chips']} */ ;
        const __VLS_2 = __VLS_tryAsConstant((__VLS_unwrap(RESULTS, {})));
        for (const [item] of __VLS_vFor(__VLS_nonNull(__VLS_2))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ onClick: // @ts-ignore
                    (...[$event]) => {
                        void $event;
                        if (!!(!__VLS_ctx.record))
                            throw 0;
                        if (!!(active.value.length === 0))
                            throw 0;
                        return (canAck.value && (result.value = item));
                        // @ts-ignore
                        [formatClock, receipt, receipt, receipt, receipt, receipt, canDispatch, canDispatch, channel, pct, pct, RESULTS, canAck, result,];
                    } },
                key: (item),
                ...{ class: "td-chip pick" },
                ...{ class: ({ on: item === result.value }) },
                role: "button",
                'aria-pressed': (item === result.value),
                'aria-disabled': (!canAck.value),
            });
            /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
            /** @type {__VLS_StyleScopedClasses['pick']} */ ;
            /** @type {__VLS_StyleScopedClasses['on']} */ ;
            (item);
            // @ts-ignore
            [canAck, result, result,];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "wb-row" },
        });
        /** @type {__VLS_StyleScopedClasses['wb-row']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
            ...{ class: "wd" },
        });
        /** @type {__VLS_StyleScopedClasses['wd']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "wk" },
        });
        /** @type {__VLS_StyleScopedClasses['wk']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
            value: (__VLS_unwrap(operator, {})),
            ...{ class: "td-input" },
            type: "text",
            disabled: (!canAck.value),
        });
        /** @type {__VLS_StyleScopedClasses['td-input']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
            ...{ class: "wd grow" },
        });
        /** @type {__VLS_StyleScopedClasses['wd']} */ ;
        /** @type {__VLS_StyleScopedClasses['grow']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "wk" },
        });
        /** @type {__VLS_StyleScopedClasses['wk']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
            ...{ onInput: // @ts-ignore
                (...[$event]) => {
                    void $event;
                    if (!!(!__VLS_ctx.record))
                        throw 0;
                    if (!!(active.value.length === 0))
                        throw 0;
                    return (actionTouched.value = true);
                    // @ts-ignore
                    [canAck, operator, actionTouched,];
                } },
            value: (__VLS_unwrap(action, {})),
            ...{ class: "td-input" },
            type: "text",
            disabled: (!canAck.value),
        });
        /** @type {__VLS_StyleScopedClasses['td-input']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "btn-row" },
        });
        /** @type {__VLS_StyleScopedClasses['btn-row']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (doAck) },
            ...{ class: "td-btn primary sm" },
            type: "button",
            disabled: (!canAck.value),
        });
        /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
        /** @type {__VLS_StyleScopedClasses['primary']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm']} */ ;
        if (!dispatched.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "tiny-inline" },
            });
            /** @type {__VLS_StyleScopedClasses['tiny-inline']} */ ;
        }
        if (terminal.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "receipt" },
            });
            /** @type {__VLS_StyleScopedClasses['receipt']} */ ;
        }
    }
    if (ackMsg.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "ok-msg" },
        });
        /** @type {__VLS_StyleScopedClasses['ok-msg']} */ ;
        (ackMsg.value);
    }
    if (error.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "err-msg" },
        });
        /** @type {__VLS_StyleScopedClasses['err-msg']} */ ;
        (error.value);
    }
    if (historyRows.value.length > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "history" },
        });
        /** @type {__VLS_StyleScopedClasses['history']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "sub-head" },
        });
        /** @type {__VLS_StyleScopedClasses['sub-head']} */ ;
        const __VLS_3 = __VLS_tryAsConstant((historyRows.value));
        for (const [row] of __VLS_vFor(__VLS_nonNull(__VLS_3))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                key: (row.alert.alert_id),
                ...{ class: "hist-row" },
            });
            /** @type {__VLS_StyleScopedClasses['hist-row']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "td-mono" },
            });
            /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
            (row.alert.alert_id);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "td-chip" },
            });
            /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
            (row.alert.status);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "tiny-inline" },
            });
            /** @type {__VLS_StyleScopedClasses['tiny-inline']} */ ;
            (row.dispatch);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "tiny-inline" },
            });
            /** @type {__VLS_StyleScopedClasses['tiny-inline']} */ ;
            (row.writeback);
            // @ts-ignore
            [canAck, canAck, action, dispatched, terminal, ackMsg, ackMsg, error, error, historyRows, historyRows,];
        }
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "cmd-note" },
    });
    /** @type {__VLS_StyleScopedClasses['cmd-note']} */ ;
}
let __VLS_4;
/** @ts-ignore @type { | typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
RouterLink;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent1(__VLS_4, new __VLS_4({
    // @ts-ignore
    ...{ class: "deep-link" }, to: ({ path: '/decision', query: { segment: __VLS_ctx.segmentId } }),
}));
const __VLS_6 = __VLS_5({
    ...{ class: "deep-link" },
    to: ({ path: '/decision', query: { segment: __VLS_ctx.segmentId } }),
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
/** @type {__VLS_StyleScopedClasses['deep-link']} */ ;
const { default: __VLS_9 } = __VLS_nonNull(__VLS_7.slots);
// @ts-ignore
[segmentId,];
var __VLS_7;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
