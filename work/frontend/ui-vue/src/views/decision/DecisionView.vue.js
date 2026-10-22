/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 决策层 · 决策工作台(按设计稿 03 重写;业务口径继承旧 DecisionView.vue 与手册 §11.2 / README 第八·九节)。
// 三栏(1440×900 一屏,各栏 .td-scroll 独立滚动):
//   左 = 处置队列(按**告警四态**分组:待认领 / 处置中 / 已闭环 / 误报,组头显示条数);
//   中 = 处置工作台(概要带 → 处置建议 + 分流比例滑杆 → 下发渠道单选 + 回执 → 处置回写四选一);
//   右 = 因素与预测(人工置位) / 预测 · 时域外推 / 数据同化 · 断面门控。
// 视图:页头右切换「效果对比 / 处置队列」(本地视图切换,不影响顶栏数据源控件)。
// 状态机硬口径:
//   认领:待认领 → 处置中(仅置本地标记);下发:→ 处置中(允许覆盖回执重下发);
//   回写:**必须先有下发回执**(TC-07 闭环顺序:下发 → 回执 → 回写),无回执不得回写;
//   回写结果四选一 → 已消除 / 已缓解 = 已闭环;未改善 = 留在处置中;误报 = 误报;
//   终态(已闭环 / 误报)**不得再回写、不得互相翻转**。
// 口径:全部数据 is_simulated=true;效果对比属仿真对照不得称实测;预测只标 L0 无精度数字;
// 决策层 · 决策工作台(Issue #77 三页收敛:页头视图扩为**决策可视化 / 处置队列 / 效果对比**三段)。
// 业务口径继承旧 DecisionView.vue 与手册 §11.2 / README 第八·九节。
//
// 四个视图(页头分段切换,不影响顶栏数据源控件):
//   ① **决策可视化**(本单新增,排首位)= 全部输入数据 + 处理过程可视化 + 可调控演示 + 输出(业主口径);
//   ② **处置队列** = 三栏:左四态队列 / 中处置工作台(建议 + 比例滑杆 + 渠道 + 回执 + 回写)/ 右因素置位 · 预测 · 同化;
//   ③ **效果对比** = 三场景 A/B/C 仿真对照(TC-14 / TC-17);
//   ④ **路线规划**(Issue IKP5CE)= 读引擎产物做完整链路 + 一主二备 + 产物内 session 对比,
//      不重算、不造路线；场景注入 / 人工置位不会让路线变化,页面如实回答。
// 状态机硬口径(处置队列视图):
//   认领:待认领 → 处置中(仅置本地标记);下发:→ 处置中(允许覆盖回执重下发);
//   回写:**必须先有下发回执**(TC-07 闭环顺序:下发 → 回执 → 回写),无回执不得回写;
//   回写结果四选一 → 已消除 / 已缓解 = 已闭环;未改善 = 留在处置中;误报 = 误报;
//   终态(已闭环 / 误报)**不得再回写、不得互相翻转**。
// 口径:全部数据 is_simulated=true;效果对比属仿真对照不得称实测;预测只标 L0 无精度数字;
//   下发渠道 / 回写结果是**展示枚举**(一期无真实下发通道);空值一律「—」,不编造数字;
//   场景注入(环境侧)与人工置位(事件侧 F07 / F08 / F11)是两个口子,不得混称(手册 §:2222)。
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { activePack } from '../../station-packs/index';
import { demoSegment } from '../../shared/demoNetwork';
import AppShell from '../../components/AppShell.vue';
import LevelBadge from '../dashboard/components/LevelBadge.vue';
import AlertQueue from './components/AlertQueue.vue';
import AssimilationPanel from './components/AssimilationPanel.vue';
import DecisionFlowPanel from './components/DecisionFlowPanel.vue';
import EffectCompare from './components/EffectCompare.vue';
import FactorsPanel from './components/FactorsPanel.vue';
import PredictPanel from './components/PredictPanel.vue';
import RoutePlanView from './components/RoutePlanView.vue';
import { getTrafficAlerts, getTrafficContext, getTrafficMeta, getTrafficSegments, getTrafficSegmentSources, getTrafficThresholds, postPlanAck, postPlanDispatch, postTrafficAlertsReset, subscribeTrafficSnapshot, } from '../../api/traffic';
import { DISPATCH_CHANNELS, diversionSuggestions, fallbackSuggestion, } from '../../shared/demoDecision';
import { alertLevelOf, isStale, } from '../../shared/traffic';
import { formatClock, formatStamp } from '../../shared/traffic';
// ---------- 契约快照(与感知层 / 大屏同源) ----------
const alerts = ref([]);
const segMap = ref({});
const snapshotIso = ref('');
const snapshotMs = ref(0);
// 站点名初始值取当前站点包;拿到 meta 后由 meta.station.name 覆盖(单一口径)
const stationName = ref(activePack().station.name);
// ---------- 深链：大屏「查看完整决策过程 / 到决策页处置」→ #/decision?segment=SZ-005（Issue IKMS18） ----------
// 语义：优先选中该段的告警；该段无告警时「决策可视化」仍按该段展示（不伪造告警）。
const route = useRoute();
const deepSegment = computed(() => {
    const raw = route.query.segment;
    return typeof raw === 'string' ? raw : Array.isArray(raw) ? (raw[0] ?? '') : '';
});
/** 视图:决策可视化(新) / 处置队列 / 效果对比 / 路线规划(Issue IKP5CE) */
const view = ref('flow');
const sourceMode = ref('both');
const selectedId = ref(null);
/** 决策可视化视图用的环境上下文与阈值(判级演算口径) */
const ctx = ref(null);
const thresholds = ref(null);
// ---------- 处置工作流 ----------
// 下发回执与回写结果的**权威留痕在服务端 /alerts**(channels / dispatch_at / dispatch_ratio_pct / writeback),
// 本地 map 只叠加本次会话的最新操作;接口层未起时页面仍能按本地态演示。
// 状态存在 mock 服务端内存里(刷新页面不清,与后端落库口径一致),要清走页头「复位演示态」。
const statusMap = reactive({});
const receipts = reactive({});
const ackResults = reactive({});
/** 动作失败提示(下发 / 回写):一句话说清是哪一步失败、失败原因 */
const actionError = ref('');
const pct = ref(20);
const channel = ref(DISPATCH_CHANNELS[0]);
const queueRatio = ref('—');
const wbOperator = ref('张工(监控)');
const wbAction = ref('');
const wbResult = ref('已缓解');
/** 回写结果四选一(手册 §11.2);本页展示口径 */
const RESULTS = ['已消除', '已缓解', '未改善', '误报'];
/** 告警四态(手册 §11.2)展示顺序 */
const STATUS_ORDER = ['待认领', '处置中', '已闭环', '误报'];
// ---------- 工具(时间 / 时长一律同源于快照时间,不取浏览器墙钟) ----------
function parseStamp(s) {
    if (!s)
        return Number.NaN;
    const iso = s.includes('T') ? s : s.replace(' ', 'T');
    const ms = Date.parse(iso);
    return Number.isNaN(ms) ? Number.NaN : ms;
}
/** ISO(带偏移)→ 展示用 'YYYY-MM-DD HH:mm:ss' */
/** ISO → `YYYY-MM-DD HH:mm:ss`（本地展示口径，统一走 shared/traffic 的 formatStamp） */
function isoToStamp(iso) {
    return formatStamp(iso);
}
/** 留痕时间串只取时分秒（统一走 shared/traffic 的 formatClock） */
function timeOf(stamp) {
    return formatClock(stamp);
}
const hhmmss = timeOf;
function fmtDuration(ms) {
    if (!Number.isFinite(ms) || ms < 0)
        return '—';
    const total = Math.floor(ms / 1000);
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    if (h > 0)
        return `${h} h ${m} min`;
    if (m > 0)
        return s > 0 ? `${m} min ${s} s` : `${m} min`;
    return `${s} s`;
}
function isTerminalStatus(s) {
    return s === '已闭环' || s === '误报';
}
function segStale(segmentId) {
    const seg = segMap.value[segmentId];
    return seg ? isStale(seg) : false;
}
/**
 * 告警行 / 工作台显示的**判级**一律取**当前路段快照**(与态势总览、大屏同源),
 * 告警自带的 `level` 只是派生时的记录值——预置剧本与快照基线不同步时它会是旧值,
 * 直接上屏就会出现「队列写缓行、路段快照已拥堵」的自相矛盾(mock 侧两处基线各自维护)。
 * 快照缺该路段时退回告警记录值,不编造。
 *
 * ⚠️ 实现收敛到 `shared/traffic.ts` 的 `alertLevelOf`(Issue IKLLXG):
 *    与监控大屏的右栏关联告警 / 底部告警条**共用同一个函数**,四处只留一份口径。
 */
function segLevel(a) {
    return alertLevelOf(a, (id) => segMap.value[id]);
}
// ---------- 选中告警派生态 ----------
const selected = computed(() => alerts.value.find((a) => a.alert_id === selectedId.value) ?? null);
function statusOf(a) {
    return statusMap[a.alert_id] ?? a.status;
}
const selectedStatus = computed(() => (selected.value ? statusOf(selected.value) : null));
const statusLabel = computed(() => selectedStatus.value ?? '—');
const terminal = computed(() => selectedStatus.value !== null && isTerminalStatus(selectedStatus.value));
const selectedStale = computed(() => (selected.value ? segStale(selected.value.segment_id) : false));
const suggestion = computed(() => selected.value
    ? diversionSuggestions()[selected.value.segment_id] ?? fallbackSuggestion(selected.value.segment_id)
    : null);
/** 站点包是否给该路段预置了分流建议(base_pct > 0)。
 *  未预置时(remote 模式常见:告警路段与站点包预置段号不一定重合)**分流比例仍可人工设置**,
 *  页面如实标「无系统预置建议」,不把兜底的 0% 说成系统建议。 */
const hasSuggestion = computed(() => (suggestion.value?.base_pct ?? 0) > 0);
const suggestionMin = computed(() => (hasSuggestion.value ? (suggestion.value?.min_pct ?? 0) : 5));
const suggestionMax = computed(() => (hasSuggestion.value ? (suggestion.value?.max_pct ?? 100) : 100));
const receipt = computed(() => {
    const a = selected.value;
    if (!a)
        return null;
    const local = receipts[a.alert_id];
    if (local)
        return local;
    // 刷新 / 切页回来后从服务端留痕还原(channels + dispatch_at + dispatch_ratio_pct),审计不丢
    if (a.dispatch_at && a.channels && a.channels.length > 0) {
        const ch = a.channels[0] ?? '—';
        return {
            alert_id: a.alert_id,
            channel: ch,
            // 后端未回比例时保持缺省:回执行显示「—」而不是 0(0% 是另一个意思)
            ratio_pct: a.dispatch_ratio_pct,
            receipt: `${ch}已确认`,
            at: a.dispatch_at,
            is_simulated: true,
        };
    }
    return null;
});
/** 是否已下发(有派发回执);回写的前置条件(TC-07:下发 → 回执 → 回写) */
const dispatched = computed(() => receipt.value !== null);
const firstSeenText = computed(() => (selected.value ? timeOf(selected.value.first_seen) : '—'));
const durationText = computed(() => {
    const a = selected.value;
    if (!a || !snapshotMs.value)
        return '—';
    const t0 = parseStamp(a.first_seen);
    if (Number.isNaN(t0))
        return '—';
    return fmtDuration(snapshotMs.value - t0);
});
const dispatchLabel = computed(() => {
    if (!selected.value)
        return '下发';
    if (terminal.value)
        return `已终结（${statusLabel.value}）`;
    return receipt.value ? '重新下发(覆盖回执)' : `下发 · ${channel.value}`;
});
const submitDisabled = computed(() => terminal.value ||
    !dispatched.value ||
    wbOperator.value.trim() === '' ||
    wbAction.value.trim() === '');
const snapshotDisplay = computed(() => isoToStamp(snapshotIso.value));
// ---------- 左栏分组 ----------
const openCount = computed(() => alerts.value.filter((a) => !isTerminalStatus(statusOf(a))).length);
/** 终态行显示回写结果(已消除 / 已缓解 / 误报),其余显示四态本身 */
function chipOf(a) {
    const st = statusOf(a);
    if (st === '已闭环')
        return ackResults[a.alert_id] ?? a.writeback?.result ?? '已闭环';
    return st;
}
const groups = computed(() => STATUS_ORDER.map((state) => ({
    state,
    items: alerts.value
        .filter((a) => statusOf(a) === state)
        .map((a) => ({
        id: a.alert_id,
        segId: a.segment_id,
        name: a.segment_name,
        level: segLevel(a),
        stale: segStale(a.segment_id),
        time: timeOf(a.first_seen),
        chip: chipOf(a),
        state: statusOf(a),
    })),
})));
// ---------- 拉取 ----------
let unsubscribe = null;
/** 刷新序号:SSE 触发与手动刷新可能并发,只让最后一次的响应落到页面(旧响应丢弃) */
let refreshSeq = 0;
/** 接口层未起时的降级提示(空 = 正常) */
const dataError = ref('');
/** SSE 刷新通道连接状态:断开时页面不会自动刷新,必须显式提示(TC-06 断流降级) */
const sseConnected = ref(true);
async function refresh() {
    const seq = ++refreshSeq;
    try {
        const [alertsSnap, segSnap, ctxRes, thrRes] = await Promise.all([
            getTrafficAlerts(),
            getTrafficSegments(),
            getTrafficContext(),
            getTrafficThresholds(),
        ]);
        if (seq !== refreshSeq)
            return; // 已被更晚的一次刷新取代:丢弃本次响应
        alerts.value = alertsSnap.alerts;
        snapshotIso.value = alertsSnap.ts;
        snapshotMs.value = parseStamp(alertsSnap.ts);
        const map = {};
        for (const s of segSnap.segments)
            map[s.segment_id] = s;
        segMap.value = map;
        // 决策可视化用的环境上下文与阈值:取不到保持 null(面板如实显示「未取到」,不编造)
        ctx.value = ctxRes;
        thresholds.value = thrRes;
        dataError.value = '';
        // 默认选中第一条「待认领」；深链点名的段优先选它自己的告警（Issue IKMS18）。
        // 深链段没有告警时**不自动选别的段**——否则「决策可视化」会被别的段抢走，深链静默失效。
        if (selectedId.value === null && alerts.value.length > 0) {
            const wanted = deepSegment.value;
            if (wanted) {
                selectedId.value = alerts.value.find((a) => a.segment_id === wanted)?.alert_id ?? null;
            }
            else {
                const first = alerts.value.find((a) => a.status === '待认领') ?? alerts.value[0];
                selectedId.value = first?.alert_id ?? null;
            }
        }
    }
    catch (e) {
        if (seq !== refreshSeq)
            return;
        // 联调期接口层可能未起:SSE 重连后会再拉;此处如实提示,不静默
        dataError.value = `快照拉取失败:${e instanceof Error ? e.message : String(e)}`;
    }
}
/**
 * 排队比 L_q = 快照记录 L_q_m / L_seg_m(两位小数;取不到显示「—」)
 * 数据源视图(顶栏)在这里生效:`twin` 取孪生槽位、`video` 取视频槽位;
 * `both`(默认)沿本页原口径取**孪生链路**(= 虚拟检测器 L_q),不因接线而改变默认读数。
 */
async function loadQueueRatio(segmentId) {
    try {
        const pair = await getTrafficSegmentSources(segmentId);
        const want = sourceMode.value === 'video' ? 'video' : 'twin';
        const slot = pair.slots.find((s) => s.source === want)?.record ?? null;
        const fallback = pair.slots.find((s) => s.source === 'twin')?.record ?? null;
        const rec = slot ?? fallback;
        if (selected.value?.segment_id !== segmentId)
            return; // 选择已变:丢弃过期响应
        if (rec && typeof rec.L_q_m === 'number' && typeof rec.L_seg_m === 'number' && rec.L_seg_m > 0) {
            queueRatio.value = (rec.L_q_m / rec.L_seg_m).toFixed(2);
        }
        else {
            queueRatio.value = '—';
        }
    }
    catch {
        queueRatio.value = '—';
    }
}
// ---------- 交互 ----------
function onSelect(id) {
    selectedId.value = id;
}
function onFactorsChanged() {
    void refresh();
}
/** 认领:待认领 → 处置中(仅置本地标记) */
function claim() {
    const a = selected.value;
    if (!a || statusOf(a) !== '待认领')
        return;
    statusMap[a.alert_id] = '处置中';
}
/** 复位演示态:清服务端下发 / 回写运行态,再拉回初始快照(与 factors 复位同口径) */
const resetting = ref(false);
async function doReset() {
    resetting.value = true;
    actionError.value = '';
    try {
        await postTrafficAlertsReset();
        for (const k of Object.keys(statusMap))
            delete statusMap[k];
        for (const k of Object.keys(receipts))
            delete receipts[k];
        for (const k of Object.keys(ackResults))
            delete ackResults[k];
        await refresh();
    }
    catch (e) {
        actionError.value = `复位失败:${e instanceof Error ? e.message : String(e)}`;
    }
    finally {
        resetting.value = false;
    }
}
async function doDispatch() {
    const a = selected.value;
    const s = suggestion.value;
    if (!a || !s || terminal.value)
        return;
    actionError.value = '';
    try {
        const r = await postPlanDispatch({
            alert_id: a.alert_id,
            segment_id: a.segment_id,
            channel: channel.value,
            ratio_pct: pct.value,
        });
        receipts[a.alert_id] = r;
        statusMap[a.alert_id] = '处置中';
    }
    catch (e) {
        // 动作失败必须可见:不然操作员分不清"没点到"还是"下发被拒"
        actionError.value = `下发失败:${e instanceof Error ? e.message : String(e)}`;
    }
}
async function doAck() {
    const a = selected.value;
    if (!a || terminal.value)
        return;
    const operator = wbOperator.value.trim();
    const action = wbAction.value.trim();
    if (!operator || !action)
        return;
    if (!dispatched.value) {
        actionError.value = '回写失败:该告警尚未下发(无派发回执),请先下发分流方案';
        return;
    }
    actionError.value = '';
    try {
        await postPlanAck({
            alert_id: a.alert_id,
            segment_id: a.segment_id,
            operator,
            action,
            result: wbResult.value,
        });
        ackResults[a.alert_id] = wbResult.value;
        statusMap[a.alert_id] =
            wbResult.value === '误报' ? '误报' : wbResult.value === '未改善' ? '处置中' : '已闭环';
    }
    catch (e) {
        actionError.value = `回写失败:${e instanceof Error ? e.message : String(e)}`;
    }
}
// 选中变化:重置表单默认值(分流比例 = 建议基准;渠道不跨告警沿用)
watch(selectedId, () => {
    const a = selected.value;
    const s = suggestion.value;
    // 有系统预置建议 → 用建议基准比例;没有(兜底 0%)→ 给人工默认 20%,不把 0% 当建议
    pct.value = s && s.base_pct > 0 ? s.base_pct : 20;
    channel.value = DISPATCH_CHANNELS[0];
    wbResult.value = '已缓解';
    wbOperator.value = '张工(监控)';
    wbAction.value = s && s.base_pct > 0 ? `情报板诱导 · 分流至${s.target_name} ${s.base_pct}%` : '情报板诱导 · 分流(人工设置比例)';
    queueRatio.value = '—';
    actionError.value = '';
    if (a)
        void loadQueueRatio(a.segment_id);
});
// 数据源视图切换(顶栏):排队比按所选链路口径重取
watch(sourceMode, () => {
    const a = selected.value;
    if (a)
        void loadQueueRatio(a.segment_id);
});
onMounted(() => {
    void refresh();
    void (async () => {
        try {
            const meta = await getTrafficMeta();
            stationName.value = meta.station.name;
        }
        catch {
            /* 保持默认站点名 */
        }
    })();
    unsubscribe = subscribeTrafficSnapshot(() => {
        void refresh();
    }, (connected) => {
        sseConnected.value = connected;
        if (connected)
            void refresh();
    });
});
onUnmounted(() => {
    unsubscribe?.();
});
// ---------- 决策可视化视图(本单新增)的派生数据 ----------
/** 该视图按**路段**工作:优先选中告警所属路段;没有选中告警时深链段号优先,再退回首条路段快照 */
const flowSegmentId = computed(() => selected.value?.segment_id ?? (deepSegment.value || Object.keys(segMap.value)[0] || ''));
const flowRecord = computed(() => segMap.value[flowSegmentId.value] ?? null);
const flowName = computed(() => {
    const id = flowSegmentId.value;
    if (!id)
        return '—';
    return (demoSegment(id)?.name ??
        alerts.value.find((a) => a.segment_id === id)?.segment_name ??
        id);
});
/** 该路段的生效因素(从快照里取;与因素面板同源) */
const flowFactors = computed(() => {
    const r = flowRecord.value;
    if (!r)
        return [];
    return (r.factors_applied ?? []).map((f) => ({ ...f, segment_id: r.segment_id }));
});
/** 该路段的系统建议(站点包模板;未命中走兜底) */
const flowSuggestion = computed(() => flowSegmentId.value
    ? diversionSuggestions()[flowSegmentId.value] ?? fallbackSuggestion(flowSegmentId.value)
    : null);
/** 站点包的场景预设档(决策可视化的"一键注入") */
const scenarioPresets = computed(() => activePack().scenarios.map((s) => ({ ...s })));
/** 调控后重算:重拉快照(判级 / CI / 因素 / 预测随之更新) */
function onFlowChanged() {
    void refresh();
}
const __VLS_ctx = {};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
void __VLS_ctx, __VLS_components, __VLS_intrinsics, __VLS_directives;
// @ts-ignore
__VLS_withDotValue(view, {});
// @ts-ignore
__VLS_withDotValue(dataError, {});
// @ts-ignore
__VLS_withDotValue(sseConnected, {});
// @ts-ignore
__VLS_withDotValue(alerts, {});
// @ts-ignore
__VLS_withDotValue(selected, {});
// @ts-ignore
__VLS_withDotValue(statusLabel, {});
// @ts-ignore
__VLS_withDotValue(suggestion, {});
// @ts-ignore
__VLS_withDotValue(hasSuggestion, {});
// @ts-ignore
__VLS_withDotValue(channel, {});
// @ts-ignore
__VLS_withDotValue(receipt, {});
// @ts-ignore
__VLS_withDotValue(wbResult, {});
// @ts-ignore
__VLS_withDotValue(terminal, {});
// @ts-ignore
__VLS_withDotValue(dispatched, {});
// @ts-ignore
__VLS_withDotValue(actionError, {});
void {};
/** @type {__VLS_StyleScopedClasses['sec']} */ ;
/** @type {__VLS_StyleScopedClasses['sl-label']} */ ;
/** @type {__VLS_StyleScopedClasses['wd']} */ ;
/** @type {__VLS_StyleScopedClasses['td-input']} */ ;
/** @type {__VLS_StyleScopedClasses['flow-col']} */ ;
/** @type {__VLS_StyleScopedClasses['cmp-col']} */ ;
/** @type {__VLS_StyleScopedClasses['route-col']} */ ;
/** @type {__VLS_StyleScopedClasses['col-queue']} */ ;
/** @type {__VLS_StyleScopedClasses['col-work']} */ ;
/** @type {__VLS_StyleScopedClasses['col-side']} */ ;
/** @type {__VLS_StyleScopedClasses['td-body']} */ ;
/** @type {__VLS_StyleScopedClasses['snapshot']} */ ;
/** @type {__VLS_StyleScopedClasses['wb-body']} */ ;
/** @type {__VLS_StyleScopedClasses['wb-side']} */ ;
/** @type {__VLS_StyleScopedClasses['sec']} */ ;
/** @type {__VLS_StyleScopedClasses['td-body']} */ ;
/** @type {__VLS_StyleScopedClasses['slider-row']} */ ;
/** @type {__VLS_StyleScopedClasses['slider-row']} */ ;
/** @type {__VLS_StyleScopedClasses['range']} */ ;
/** @type {__VLS_StyleScopedClasses['wb-row']} */ ;
/** @type {__VLS_StyleScopedClasses['wd']} */ ;
/** @type {__VLS_StyleScopedClasses['wd']} */ ;
/** @type {__VLS_StyleScopedClasses['grow']} */ ;
/** @type {__VLS_StyleScopedClasses['td-input']} */ ;
/** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['band']} */ ;
/** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
/** @type {__VLS_StyleScopedClasses['sec-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['td-body']} */ ;
/** @type {__VLS_StyleScopedClasses['snapshot']} */ ;
/** @type {__VLS_StyleScopedClasses['td-seg']} */ ;
/** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
const __VLS_0 = AppShell || AppShell;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    // @ts-ignore
    active: "decision", station: (__VLS_unwrap(stationName, {})), ts: (__VLS_unwrap(snapshotDisplay, {})), sourceMode: (__VLS_unwrap(sourceMode, {})), title: "决策层", subtitle: "决策可视化 · 处置闭环(四态 / 下发回执 / 回写)· 效果对比 · 路线规划",
}));
const __VLS_2 = __VLS_1({
    active: "decision",
    station: (__VLS_unwrap(stationName, {})),
    ts: (__VLS_unwrap(snapshotDisplay, {})),
    sourceMode: (__VLS_unwrap(sourceMode, {})),
    title: "决策层",
    subtitle: "决策可视化 · 处置闭环(四态 / 下发回执 / 回写)· 效果对比 · 路线规划",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const { default: __VLS_5 } = __VLS_nonNull(__VLS_3.slots);
{
    const { headRight: __VLS_6 } = __VLS_nonNull(__VLS_3.slots);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-seg" },
        role: "group",
        'aria-label': "视图切换",
    });
    /** @type {__VLS_StyleScopedClasses['td-seg']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                return (view.value = 'flow');
                // @ts-ignore
                [stationName, snapshotDisplay, sourceMode, view,];
            } },
        ...{ class: "td-seg-item" },
        ...{ class: ({ on: view.value === 'flow' }) },
        role: "button",
        'aria-pressed': (view.value === 'flow'),
    });
    /** @type {__VLS_StyleScopedClasses['td-seg-item']} */ ;
    /** @type {__VLS_StyleScopedClasses['on']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                return (view.value = 'queue');
                // @ts-ignore
                [view, view, view,];
            } },
        ...{ class: "td-seg-item" },
        ...{ class: ({ on: view.value === 'queue' }) },
        role: "button",
        'aria-pressed': (view.value === 'queue'),
    });
    /** @type {__VLS_StyleScopedClasses['td-seg-item']} */ ;
    /** @type {__VLS_StyleScopedClasses['on']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                return (view.value = 'compare');
                // @ts-ignore
                [view, view, view,];
            } },
        ...{ class: "td-seg-item" },
        ...{ class: ({ on: view.value === 'compare' }) },
        role: "button",
        'aria-pressed': (view.value === 'compare'),
    });
    /** @type {__VLS_StyleScopedClasses['td-seg-item']} */ ;
    /** @type {__VLS_StyleScopedClasses['on']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                return (view.value = 'route');
                // @ts-ignore
                [view, view, view,];
            } },
        ...{ class: "td-seg-item" },
        ...{ class: ({ on: view.value === 'route' }) },
        role: "button",
        'aria-pressed': (view.value === 'route'),
    });
    /** @type {__VLS_StyleScopedClasses['td-seg-item']} */ ;
    /** @type {__VLS_StyleScopedClasses['on']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "snapshot td-mono" },
    });
    /** @type {__VLS_StyleScopedClasses['snapshot']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
    (__VLS_unwrap(snapshotDisplay, {}));
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (doReset) },
        type: "button",
        ...{ class: "td-btn sm" },
        disabled: (__VLS_unwrap(resetting, {})),
    });
    /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
    /** @type {__VLS_StyleScopedClasses['sm']} */ ;
    // @ts-ignore
    [snapshotDisplay, view, view, resetting,];
}
{
    const { headExtra: __VLS_7 } = __VLS_nonNull(__VLS_3.slots);
    if (dataError.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "head-err" },
        });
        /** @type {__VLS_StyleScopedClasses['head-err']} */ ;
        (dataError.value);
    }
    if (!sseConnected.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "head-err" },
        });
        /** @type {__VLS_StyleScopedClasses['head-err']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (refresh) },
            ...{ class: "td-btn sm" },
            type: "button",
        });
        /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm']} */ ;
    }
    // @ts-ignore
    [dataError, dataError, sseConnected,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-body" },
});
/** @type {__VLS_StyleScopedClasses['td-body']} */ ;
if (view.value === 'flow') {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-col flow-col td-scroll" },
    });
    /** @type {__VLS_StyleScopedClasses['td-col']} */ ;
    /** @type {__VLS_StyleScopedClasses['flow-col']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-scroll']} */ ;
    const __VLS_8 = DecisionFlowPanel;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
        // @ts-ignore
        ...{ 'onChanged': {} }, record: (__VLS_unwrap(flowRecord, {})), name: (__VLS_unwrap(flowName, {})), factors: (__VLS_unwrap(flowFactors, {})), ctx: (__VLS_unwrap(ctx, {})), thresholds: (__VLS_unwrap(thresholds, {})), suggestion: (__VLS_unwrap(flowSuggestion, {})), presets: (__VLS_unwrap(scenarioPresets, {})),
    }));
    const __VLS_10 = __VLS_9({
        ...{ 'onChanged': {} },
        record: (__VLS_unwrap(flowRecord, {})),
        name: (__VLS_unwrap(flowName, {})),
        factors: (__VLS_unwrap(flowFactors, {})),
        ctx: (__VLS_unwrap(ctx, {})),
        thresholds: (__VLS_unwrap(thresholds, {})),
        suggestion: (__VLS_unwrap(flowSuggestion, {})),
        presets: (__VLS_unwrap(scenarioPresets, {})),
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    let __VLS_13;
    const __VLS_14 = {
        /** @type {typeof __VLS_13.changed} */
        onChanged: (onFlowChanged),
    };
    void __VLS_14;
    var __VLS_11;
    var __VLS_12;
}
else if (view.value === 'queue') {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-col col-queue td-scroll" },
    });
    /** @type {__VLS_StyleScopedClasses['td-col']} */ ;
    /** @type {__VLS_StyleScopedClasses['col-queue']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-scroll']} */ ;
    const __VLS_15 = AlertQueue;
    // @ts-ignore
    const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
        // @ts-ignore
        ...{ 'onSelect': {} }, groups: (__VLS_unwrap(groups, {})), selectedId: (__VLS_unwrap(selectedId, {})), total: (alerts.value.length), openCount: (__VLS_unwrap(openCount, {})),
    }));
    const __VLS_17 = __VLS_16({
        ...{ 'onSelect': {} },
        groups: (__VLS_unwrap(groups, {})),
        selectedId: (__VLS_unwrap(selectedId, {})),
        total: (alerts.value.length),
        openCount: (__VLS_unwrap(openCount, {})),
    }, ...__VLS_functionalComponentArgsRest(__VLS_16));
    let __VLS_20;
    const __VLS_21 = {
        /** @type {typeof __VLS_20.select} */
        onSelect: (onSelect),
    };
    void __VLS_21;
    var __VLS_18;
    var __VLS_19;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-col col-work td-scroll" },
    });
    /** @type {__VLS_StyleScopedClasses['td-col']} */ ;
    /** @type {__VLS_StyleScopedClasses['col-work']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-scroll']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
        ...{ class: "td-card" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-card-head" },
    });
    /** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-mono wb-id" },
    });
    /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
    /** @type {__VLS_StyleScopedClasses['wb-id']} */ ;
    (selected.value ? selected.value.alert_id : '—');
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-chip" },
    });
    /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
    (statusLabel.value);
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (claim) },
        type: "button",
        ...{ class: "td-btn sm claim" },
        disabled: (statusLabel.value !== '待认领'),
    });
    /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
    /** @type {__VLS_StyleScopedClasses['sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['claim']} */ ;
    (statusLabel.value === '待认领' ? '认领' : '已认领');
    if (selected.value && suggestion.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "td-card-body wb-body" },
        });
        /** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
        /** @type {__VLS_StyleScopedClasses['wb-body']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "wb-main" },
        });
        /** @type {__VLS_StyleScopedClasses['wb-main']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "band" },
        });
        /** @type {__VLS_StyleScopedClasses['band']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "bi" },
        });
        /** @type {__VLS_StyleScopedClasses['bi']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "bk" },
        });
        /** @type {__VLS_StyleScopedClasses['bk']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "bv" },
        });
        /** @type {__VLS_StyleScopedClasses['bv']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (selected.value.segment_id);
        (selected.value.segment_name);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "bi" },
        });
        /** @type {__VLS_StyleScopedClasses['bi']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "bk" },
        });
        /** @type {__VLS_StyleScopedClasses['bk']} */ ;
        const __VLS_22 = LevelBadge;
        // @ts-ignore
        const __VLS_23 = __VLS_asFunctionalComponent1(__VLS_22, new __VLS_22({
            // @ts-ignore
            level: (segLevel(selected.value)), stale: (__VLS_unwrap(selectedStale, {})),
        }));
        const __VLS_24 = __VLS_23({
            level: (segLevel(selected.value)),
            stale: (__VLS_unwrap(selectedStale, {})),
        }, ...__VLS_functionalComponentArgsRest(__VLS_23));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "bi" },
        });
        /** @type {__VLS_StyleScopedClasses['bi']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "bk" },
        });
        /** @type {__VLS_StyleScopedClasses['bk']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "bv td-num" },
        });
        /** @type {__VLS_StyleScopedClasses['bv']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
        (__VLS_unwrap(firstSeenText, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "bi" },
        });
        /** @type {__VLS_StyleScopedClasses['bi']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "bk" },
        });
        /** @type {__VLS_StyleScopedClasses['bk']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "bv td-num" },
        });
        /** @type {__VLS_StyleScopedClasses['bv']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
        (__VLS_unwrap(durationText, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "bi" },
        });
        /** @type {__VLS_StyleScopedClasses['bi']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "bk" },
        });
        /** @type {__VLS_StyleScopedClasses['bk']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "bv td-num" },
        });
        /** @type {__VLS_StyleScopedClasses['bv']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
        (__VLS_unwrap(queueRatio, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
            ...{ class: "sec" },
        });
        /** @type {__VLS_StyleScopedClasses['sec']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "sec-head" },
        });
        /** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "sec-tag" },
        });
        /** @type {__VLS_StyleScopedClasses['sec-tag']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "why" },
        });
        /** @type {__VLS_StyleScopedClasses['why']} */ ;
        (suggestion.value.why);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "slider-row" },
        });
        /** @type {__VLS_StyleScopedClasses['slider-row']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "sl-label" },
        });
        /** @type {__VLS_StyleScopedClasses['sl-label']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
        (__VLS_unwrap(pct, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
            ...{ class: "range" },
            type: "range",
            min: (__VLS_unwrap(suggestionMin, {})),
            max: (__VLS_unwrap(suggestionMax, {})),
            step: "5",
        });
        (__VLS_unwrap(pct, {}));
        /** @type {__VLS_StyleScopedClasses['range']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "sl-label" },
        });
        /** @type {__VLS_StyleScopedClasses['sl-label']} */ ;
        (hasSuggestion.value ? `分流上限 ${__VLS_unwrap(suggestionMax, {})}%` : '无系统预置建议 · 人工设置比例');
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "hint" },
        });
        /** @type {__VLS_StyleScopedClasses['hint']} */ ;
        if (hasSuggestion.value) {
            (100 - __VLS_unwrap(pct, {}));
            (suggestion.value.target_name);
            (suggestion.value.target_segment_id);
            (suggestion.value.expect);
        }
        else {
            (100 - __VLS_unwrap(pct, {}));
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
            ...{ class: "sec" },
        });
        /** @type {__VLS_StyleScopedClasses['sec']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "sec-head" },
        });
        /** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "sec-tag" },
        });
        /** @type {__VLS_StyleScopedClasses['sec-tag']} */ ;
        (channel.value);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "chips" },
        });
        /** @type {__VLS_StyleScopedClasses['chips']} */ ;
        const __VLS_27 = __VLS_tryAsConstant((__VLS_unwrap(DISPATCH_CHANNELS, {})));
        for (const [c] of __VLS_vFor(__VLS_nonNull(__VLS_27))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ onClick: // @ts-ignore
                    (...[$event]) => {
                        void $event;
                        if (!!(view.value === 'flow'))
                            throw 0;
                        if (!(view.value === 'queue'))
                            throw 0;
                        if (!(selected.value && suggestion.value))
                            throw 0;
                        return (channel.value = c);
                        // @ts-ignore
                        [view, view, flowRecord, flowName, flowFactors, ctx, thresholds, flowSuggestion, scenarioPresets, groups, selectedId, alerts, openCount, selected, selected, selected, selected, selected, selected, statusLabel, statusLabel, statusLabel, suggestion, suggestion, suggestion, suggestion, suggestion, selectedStale, firstSeenText, durationText, queueRatio, pct, pct, pct, pct, suggestionMin, suggestionMax, suggestionMax, hasSuggestion, hasSuggestion, channel, channel, DISPATCH_CHANNELS,];
                    } },
                key: (c),
                ...{ class: "td-chip pick" },
                ...{ class: ({ on: c === channel.value }) },
                role: "button",
                'aria-pressed': (c === channel.value),
            });
            /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
            /** @type {__VLS_StyleScopedClasses['pick']} */ ;
            /** @type {__VLS_StyleScopedClasses['on']} */ ;
            (c);
            // @ts-ignore
            [channel, channel,];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (doDispatch) },
            type: "button",
            ...{ class: "td-btn primary" },
            disabled: (terminal.value),
        });
        /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
        /** @type {__VLS_StyleScopedClasses['primary']} */ ;
        (__VLS_unwrap(dispatchLabel, {}));
        if (receipt.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "receipt" },
            });
            /** @type {__VLS_StyleScopedClasses['receipt']} */ ;
            (receipt.value.receipt);
            (receipt.value.ratio_pct ?? '—');
            (__VLS_unwrap(hhmmss, {})(receipt.value.at));
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "note" },
        });
        /** @type {__VLS_StyleScopedClasses['note']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
            ...{ class: "sec" },
        });
        /** @type {__VLS_StyleScopedClasses['sec']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "sec-head" },
        });
        /** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "chips" },
        });
        /** @type {__VLS_StyleScopedClasses['chips']} */ ;
        const __VLS_28 = __VLS_tryAsConstant((__VLS_unwrap(RESULTS, {})));
        for (const [r] of __VLS_vFor(__VLS_nonNull(__VLS_28))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ onClick: // @ts-ignore
                    (...[$event]) => {
                        void $event;
                        if (!!(view.value === 'flow'))
                            throw 0;
                        if (!(view.value === 'queue'))
                            throw 0;
                        if (!(selected.value && suggestion.value))
                            throw 0;
                        return (wbResult.value = r);
                        // @ts-ignore
                        [terminal, dispatchLabel, receipt, receipt, receipt, receipt, hhmmss, RESULTS, wbResult,];
                    } },
                key: (r),
                ...{ class: "td-chip pick" },
                ...{ class: ({ on: r === wbResult.value }) },
                role: "button",
                'aria-pressed': (r === wbResult.value),
            });
            /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
            /** @type {__VLS_StyleScopedClasses['pick']} */ ;
            /** @type {__VLS_StyleScopedClasses['on']} */ ;
            (r);
            // @ts-ignore
            [wbResult, wbResult,];
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
            value: (__VLS_unwrap(wbOperator, {})),
            ...{ class: "td-input" },
            type: "text",
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
            value: (__VLS_unwrap(wbAction, {})),
            ...{ class: "td-input" },
            type: "text",
        });
        /** @type {__VLS_StyleScopedClasses['td-input']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (doAck) },
            type: "button",
            ...{ class: "td-btn primary" },
            disabled: (__VLS_unwrap(submitDisabled, {})),
        });
        /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
        /** @type {__VLS_StyleScopedClasses['primary']} */ ;
        (terminal.value ? '结果已回写' : '提交回写');
        if (!terminal.value && !dispatched.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "note warn-note" },
            });
            /** @type {__VLS_StyleScopedClasses['note']} */ ;
            /** @type {__VLS_StyleScopedClasses['warn-note']} */ ;
        }
        if (terminal.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "note" },
            });
            /** @type {__VLS_StyleScopedClasses['note']} */ ;
        }
        if (terminal.value && selected.value?.writeback) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "note" },
            });
            /** @type {__VLS_StyleScopedClasses['note']} */ ;
            (selected.value.writeback.operator);
            (selected.value.writeback.action);
            (selected.value.writeback.result);
            (__VLS_unwrap(hhmmss, {})(selected.value.writeback.at));
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "sep" },
            });
            /** @type {__VLS_StyleScopedClasses['sep']} */ ;
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "note" },
            });
            /** @type {__VLS_StyleScopedClasses['note']} */ ;
        }
        if (actionError.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "note err-note" },
            });
            /** @type {__VLS_StyleScopedClasses['note']} */ ;
            /** @type {__VLS_StyleScopedClasses['err-note']} */ ;
            (actionError.value);
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "wb-side" },
        });
        /** @type {__VLS_StyleScopedClasses['wb-side']} */ ;
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "td-card-body" },
        });
        /** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "empty" },
        });
        /** @type {__VLS_StyleScopedClasses['empty']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-col col-side td-scroll" },
    });
    /** @type {__VLS_StyleScopedClasses['td-col']} */ ;
    /** @type {__VLS_StyleScopedClasses['col-side']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-scroll']} */ ;
    const __VLS_29 = FactorsPanel;
    // @ts-ignore
    const __VLS_30 = __VLS_asFunctionalComponent1(__VLS_29, new __VLS_29({
        // @ts-ignore
        ...{ 'onChanged': {} }, segmentId: (selected.value ? selected.value.segment_id : ''),
    }));
    const __VLS_31 = __VLS_30({
        ...{ 'onChanged': {} },
        segmentId: (selected.value ? selected.value.segment_id : ''),
    }, ...__VLS_functionalComponentArgsRest(__VLS_30));
    let __VLS_34;
    const __VLS_35 = {
        /** @type {typeof __VLS_34.changed} */
        onChanged: (onFactorsChanged),
    };
    void __VLS_35;
    var __VLS_32;
    var __VLS_33;
    const __VLS_36 = PredictPanel;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent1(__VLS_36, new __VLS_36({
        // @ts-ignore
        segmentId: (selected.value ? selected.value.segment_id : ''),
    }));
    const __VLS_38 = __VLS_37({
        segmentId: (selected.value ? selected.value.segment_id : ''),
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    const __VLS_41 = AssimilationPanel;
    // @ts-ignore
    const __VLS_42 = __VLS_asFunctionalComponent1(__VLS_41, new __VLS_41({
    // @ts-ignore
    }));
    const __VLS_43 = __VLS_42({}, ...__VLS_functionalComponentArgsRest(__VLS_42));
}
else if (view.value === 'compare') {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-col cmp-col td-scroll" },
    });
    /** @type {__VLS_StyleScopedClasses['td-col']} */ ;
    /** @type {__VLS_StyleScopedClasses['cmp-col']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-scroll']} */ ;
    const __VLS_46 = EffectCompare;
    // @ts-ignore
    const __VLS_47 = __VLS_asFunctionalComponent1(__VLS_46, new __VLS_46({
    // @ts-ignore
    }));
    const __VLS_48 = __VLS_47({}, ...__VLS_functionalComponentArgsRest(__VLS_47));
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-col route-col td-scroll" },
    });
    /** @type {__VLS_StyleScopedClasses['td-col']} */ ;
    /** @type {__VLS_StyleScopedClasses['route-col']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-scroll']} */ ;
    const __VLS_51 = RoutePlanView;
    // @ts-ignore
    const __VLS_52 = __VLS_asFunctionalComponent1(__VLS_51, new __VLS_51({
    // @ts-ignore
    }));
    const __VLS_53 = __VLS_52({}, ...__VLS_functionalComponentArgsRest(__VLS_52));
}
{
    const { foot: __VLS_56 } = __VLS_nonNull(__VLS_3.slots);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (__VLS_unwrap(snapshotDisplay, {}));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "right td-mono" },
    });
    /** @type {__VLS_StyleScopedClasses['right']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
    // @ts-ignore
    [snapshotDisplay, view, selected, selected, selected, selected, selected, selected, selected, selected, selected, terminal, terminal, terminal, terminal, hhmmss, wbOperator, wbAction, submitDisabled, dispatched, actionError, actionError,];
}
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
