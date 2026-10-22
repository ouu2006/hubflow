/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 决策层 · 路线规划视图（Issue IKP5CE）。
//
// 队长裁定走方案 A（保守）：本页只在**已有引擎产物**范围内做对比——
// 同一 OD 的推荐 vs 备选、不同 session、不同站点包；不触发任何算路。
// 场景注入 / 人工置位 / 告警下发都不会让路线变化，页面必须把这句话说清楚
// （见「路线是否随参数变化」卡），不得把回放讲成规划，更不得在前端编路线或改 ETA。
//
// 数据来源：
//   · GET  /api/traffic/route/options  —— 只读辅助端点（非契约 §七），端出引擎产物的
//     OD / session 摘要；mock 模式没有该端点（404），页面跳过请求并如实标注，不刷 404。
//   · POST /api/traffic/route/recommend —— 选中 session 后取完整推荐（arrival / alternatives /
//     departure）；段号与 eta_min 原样透传，本页只做「差值 = 两次产物 ETA 相减」的展示。
//
// 数据源口径：接口层真网产物优先、样例产物回退（engine.routes.real / engine.routes.sample）；
// mock 侧回退站点包演示骨架。路线一律标「演示数据（模拟）」，沿用现有对外口径纪律。
import { computed, onMounted, ref } from 'vue';
import { getTrafficRouteOptions, postRouteRecommend } from '../../../api/traffic';
import { demoSegment } from '../../../shared/demoNetwork';
import { USE_MOCK } from '../../../shared/env';
import { activePack } from '../../../station-packs/index';
// ---------- 引擎产物选项（GET /route/options） ----------
const options = ref([]);
const optionsMeta = ref(null);
const optionsLoading = ref(false);
/** 空 = 正常；非空 = 辅助端点缺失 / 产物缺失，页面已回退演示会话（如实展示） */
const optionsError = ref('');
// ---------- 当前 session 的完整路线（POST /route/recommend） ----------
const mainSession = ref('');
const main = ref(null);
const mainLoading = ref(false);
const mainError = ref('');
let mainSeq = 0;
// ---------- 两个 session 的产物内对比 ----------
const leftSession = ref('');
const rightSession = ref('');
const left = ref(null);
const right = ref(null);
const leftLoading = ref(false);
const rightLoading = ref(false);
const leftError = ref('');
const rightError = ref('');
let leftSeq = 0;
let rightSeq = 0;
const canCompare = computed(() => options.value.length >= 2);
// ---------- 产物回放复核（同一 session 重新读取一次，不解算） ----------
const recheckState = ref('idle');
const recheckText = ref('');
function fmtEta(value) {
    return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(2) : '—';
}
function deltaValue(base, value) {
    if (typeof base !== 'number' ||
        typeof value !== 'number' ||
        !Number.isFinite(base) ||
        !Number.isFinite(value)) {
        return null;
    }
    return value - base;
}
function deltaText(base, value) {
    const d = deltaValue(base, value);
    if (d === null)
        return '—';
    return `${d > 0 ? '+' : ''}${d.toFixed(2)} min`;
}
function sameSegments(a, b) {
    return a.length === b.length && a.every((id, index) => id === b[index]);
}
function segmentName(id) {
    if (!id)
        return '—';
    return demoSegment(id)?.name ?? '站点包未收录该段';
}
function dropoffName(id) {
    if (!id)
        return '';
    return activePack().dropoffs.find((item) => item.id === id)?.name ?? '站点包未收录该落客点';
}
/** 契约里 arrival_route 必填，但引擎在「无可行路径」时按 no_alternative 例外写 null；页面按空窗处理。 */
function arrivalOf(record) {
    return record ? (record.arrival_route ?? null) : null;
}
function optionLabel(option) {
    const od = option.od_id ?? 'OD—';
    const alternatives = option.alternatives?.length ?? 0;
    return `${od} · ${option.session_id ?? '—'} · 到达 ${fmtEta(option.arrival_route?.eta_min)} min · 备选 ${alternatives} 条`;
}
/**
 * 链路条四段：起点 → 场区/落客点 → 终点（到达末段）→ 离站方向。
 * 落客点缺失时只如实写"引擎产物未给落客点"并用末段段号/路段名兜底，
 * 不把末段冒充成落客点（契约里 dropoff_point 为 null 就是 null）。
 */
function chainNodes(record) {
    if (!record)
        return [];
    const arrival = arrivalOf(record);
    const arrivalSegments = arrival?.segments ?? [];
    const lastSegment = arrivalSegments[arrivalSegments.length - 1];
    const dropoff = arrival?.dropoff_point && arrival.dropoff_point.trim() ? arrival.dropoff_point : null;
    const departure = record.departure_route;
    const departureSegments = departure?.segments ?? [];
    const startSegment = record.location?.segment_id ?? '';
    return [
        {
            key: 'start',
            step: '①',
            title: '起点',
            primary: startSegment || '引擎产物未给起点段',
            secondary: startSegment ? segmentName(startSegment) : 'location.segment_id 为空',
            tag: record.location?.source ?? 'source 缺省',
            note: '定位来源（location.source）',
            empty: !startSegment,
        },
        {
            key: 'dropoff',
            step: '②',
            title: '场区 / 落客点',
            primary: dropoff ?? '引擎产物未给落客点',
            secondary: dropoff
                ? dropoffName(dropoff)
                : lastSegment
                    ? `末段兜底：${lastSegment} · ${segmentName(lastSegment)}（仅作位置参照）`
                    : '到达段为空，无末段可兜底',
            tag: dropoff ? 'dropoff_point' : 'null',
            note: dropoff ? 'arrival_route.dropoff_point' : '如实空窗 · 不补造落客点',
            empty: !dropoff,
        },
        {
            key: 'end',
            step: '③',
            title: '终点（到达末段）',
            primary: lastSegment ?? '引擎产物未给终点段',
            secondary: lastSegment ? segmentName(lastSegment) : 'arrival_route 为空',
            tag: arrivalSegments.length ? `${arrivalSegments.length} 段` : '—',
            note: lastSegment ? '推荐路线最后一段' : '不补造终点',
            empty: !lastSegment,
        },
        {
            key: 'departure',
            step: '④',
            title: '离站方向',
            primary: departure ? departure.path_id || '离站路线' : '引擎产物未给离站路线',
            secondary: departure
                ? `${departureSegments.length} 段 · ETA ${fmtEta(departure.eta_min)} min`
                : 'departure_route = null',
            tag: departure ? 'departure_route' : 'null',
            note: departure && departureSegments.length
                ? `首段 ${departureSegments[0]} → 末段 ${departureSegments[departureSegments.length - 1]}`
                : departure
                    ? '离站段为空'
                    : '如实空窗 · 不补造离站路线',
            empty: !departure,
        },
    ];
}
const mainChain = computed(() => chainNodes(main.value));
const leftChain = computed(() => chainNodes(left.value));
const rightChain = computed(() => chainNodes(right.value));
const arrivalSegments = computed(() => arrivalOf(main.value)?.segments ?? []);
const alternatives = computed(() => main.value?.alternatives ?? []);
const mainArrival = computed(() => arrivalOf(main.value));
/** 备选不足 / no_alternative 的如实说明（不凑数）。 */
const alternativeNotice = computed(() => {
    const record = main.value;
    if (!record)
        return '';
    if (record.no_alternative === true) {
        const reason = record.no_alternative_reason?.trim();
        return `引擎标记 no_alternative = true：${reason || '产物未给 no_alternative_reason'}（本 OD 备选 ${alternatives.value.length} 条，按产物如实展示，不凑数）`;
    }
    if (alternatives.value.length < 2) {
        return `本 OD 仅 ${alternatives.value.length} 条候选（契约要求 ≥2 条备选）`;
    }
    return '';
});
const mainSourceLabel = computed(() => {
    const record = main.value;
    if (!record)
        return '—';
    if (record.data_source === 'engine.routes.real')
        return '真网算路产物 engine.routes.real';
    if (record.data_source === 'engine.routes.sample')
        return '样例产物 engine.routes.sample（非本站真网）';
    if (USE_MOCK)
        return 'mock 站点包演示骨架（非引擎产物）';
    return record.data_source || '接口未标来源';
});
const mainSourceNote = computed(() => main.value?.data_source_note ?? '');
/** session 未匹配 / mock 侧不按 session 区分时，必须显式说明，不伪装成该车行程。 */
const sessionWarning = computed(() => {
    const record = main.value;
    if (!record)
        return '';
    if (record.session_matched === false) {
        return `请求的 session_id（${record.requested_session_id ?? mainSession.value}）不在引擎产物里：当前端出的是产物首条请求作为演示路线，非该车行程；页面不伪装成匹配结果。`;
    }
    if (USE_MOCK) {
        return 'mock 侧按站点包演示骨架返回，不按 session 区分（响应里的 session 号由 mock 生成）；这是演示路线，不是引擎算路产物。';
    }
    return '';
});
const optionsHint = computed(() => {
    if (USE_MOCK) {
        return 'mock 模式无 GET /api/traffic/route/options 辅助端点（404）：本页跳过该请求，回退演示会话路线；不冒充引擎 OD / session 列表。';
    }
    if (optionsError.value) {
        return `路线选项不可用：${optionsError.value}。已回退演示会话路线；不编造 OD / session。`;
    }
    if (optionsMeta.value && options.value.length === 0) {
        return '引擎产物没有可用 OD / session：不编造路线选择。';
    }
    return '';
});
async function fetchRecommendation(session) {
    const pack = activePack();
    const option = options.value.find((item) => item.session_id === session) ?? null;
    return postRouteRecommend({
        session_id: session,
        location: {
            // 有引擎选项时用该 OD 的起点；没有（mock / 回退）沿用站点包演示锚点，与请求形状一致
            segment_id: option?.location.segment_id ?? pack.recommend.location_segment_id,
            offset_m: option?.location.offset_m ?? pack.recommend.location_offset_m,
        },
    });
}
async function loadMain() {
    const session = mainSession.value;
    const seq = ++mainSeq;
    if (!session) {
        main.value = null;
        mainError.value = '未选择 session：不能读取路线。';
        return;
    }
    mainLoading.value = true;
    mainError.value = '';
    try {
        const record = await fetchRecommendation(session);
        if (seq !== mainSeq)
            return; // 选择已变：丢弃过期响应
        main.value = record;
        recheckState.value = 'idle';
        recheckText.value = '';
    }
    catch (e) {
        if (seq !== mainSeq)
            return;
        main.value = null;
        mainError.value = `推荐接口不可达：${e instanceof Error ? e.message : String(e)}。本页保持空窗，不编造演示路线。`;
    }
    finally {
        if (seq === mainSeq)
            mainLoading.value = false;
    }
}
/**
 * 左右两列各自独立发一次 POST /route/recommend：
 * 左列结果只写 left、右列只写 right，绝不复用同一份响应伪造"两个 session 的差异"。
 */
async function loadSide(side) {
    const isLeft = side === 'left';
    const session = isLeft ? leftSession.value : rightSession.value;
    const target = isLeft ? left : right;
    const loading = isLeft ? leftLoading : rightLoading;
    const error = isLeft ? leftError : rightError;
    const seq = isLeft ? ++leftSeq : ++rightSeq;
    if (!session) {
        target.value = null;
        error.value = '';
        loading.value = false;
        return;
    }
    loading.value = true;
    error.value = '';
    try {
        const record = await fetchRecommendation(session);
        if (seq !== (isLeft ? leftSeq : rightSeq))
            return;
        target.value = record;
    }
    catch (e) {
        if (seq !== (isLeft ? leftSeq : rightSeq))
            return;
        target.value = null;
        error.value = `读取失败：${e instanceof Error ? e.message : String(e)}`;
    }
    finally {
        if (seq === (isLeft ? leftSeq : rightSeq))
            loading.value = false;
    }
}
/** 同 session 连续两次读取的差异；用于回答"产物是否变过"，不是重算。 */
function diffOfSameSession(before, after) {
    const out = [];
    const beforeArrival = arrivalOf(before);
    const afterArrival = arrivalOf(after);
    if ((beforeArrival === null) !== (afterArrival === null))
        out.push('到达路线有无不同');
    if (beforeArrival && afterArrival) {
        if (!sameSegments(beforeArrival.segments, afterArrival.segments))
            out.push('推荐段序列不同');
        if (beforeArrival.eta_min !== afterArrival.eta_min) {
            out.push(`到达 ETA ${fmtEta(beforeArrival.eta_min)} → ${fmtEta(afterArrival.eta_min)} min`);
        }
    }
    const beforeDeparture = before.departure_route;
    const afterDeparture = after.departure_route;
    if ((beforeDeparture === null) !== (afterDeparture === null)) {
        out.push('离站路线有无不同');
    }
    else if (beforeDeparture && afterDeparture) {
        if (beforeDeparture.path_id !== afterDeparture.path_id ||
            !sameSegments(beforeDeparture.segments, afterDeparture.segments) ||
            beforeDeparture.eta_min !== afterDeparture.eta_min) {
            out.push('离站路线或 ETA 不同');
        }
    }
    if ((before.alternatives?.length ?? 0) !== (after.alternatives?.length ?? 0)) {
        out.push(`备选条数 ${before.alternatives?.length ?? 0} → ${after.alternatives?.length ?? 0}`);
    }
    return out;
}
async function recheckSameSession() {
    const before = main.value;
    if (!before || !mainSession.value || recheckState.value === 'running')
        return;
    recheckState.value = 'running';
    recheckText.value = '';
    try {
        const after = await fetchRecommendation(mainSession.value);
        const diffs = diffOfSameSession(before, after);
        if (diffs.length === 0) {
            recheckState.value = 'same';
            recheckText.value = '与上次读取一致：推荐 / 备选 / 离站段序列与 ETA 全部相同。';
        }
        else {
            recheckState.value = 'diff';
            recheckText.value = `与上次读取不同：${diffs.join('；')}。只可能来自产物文件更新；本页不自行重算。`;
        }
    }
    catch (e) {
        recheckState.value = 'diff';
        recheckText.value = `重新读取失败：${e instanceof Error ? e.message : String(e)}`;
    }
}
const compare = computed(() => {
    const a = left.value;
    const b = right.value;
    if (!a || !b)
        return null;
    const beforeArrival = arrivalOf(a);
    const afterArrival = arrivalOf(b);
    const beforeDeparture = a.departure_route;
    const afterDeparture = b.departure_route;
    const sameSession = Boolean(leftSession.value) && leftSession.value === rightSession.value;
    const arrivalSame = (beforeArrival === null) === (afterArrival === null) &&
        (beforeArrival?.path_id ?? '') === (afterArrival?.path_id ?? '') &&
        sameSegments(beforeArrival?.segments ?? [], afterArrival?.segments ?? []);
    const departureSame = (beforeDeparture === null) === (afterDeparture === null) &&
        (beforeDeparture?.path_id ?? '') === (afterDeparture?.path_id ?? '') &&
        sameSegments(beforeDeparture?.segments ?? [], afterDeparture?.segments ?? []);
    const etaDelta = deltaValue(beforeArrival?.eta_min, afterArrival?.eta_min);
    const departureEtaDelta = deltaValue(beforeDeparture?.eta_min, afterDeparture?.eta_min);
    const beforeAlternatives = a.alternatives?.length ?? 0;
    const afterAlternatives = b.alternatives?.length ?? 0;
    const changed = !sameSession &&
        (!arrivalSame ||
            !departureSame ||
            (etaDelta !== null && etaDelta !== 0) ||
            (departureEtaDelta !== null && departureEtaDelta !== 0) ||
            beforeAlternatives !== afterAlternatives);
    return {
        sameSession,
        arrivalSame,
        departureSame,
        etaDeltaText: deltaText(beforeArrival?.eta_min, afterArrival?.eta_min),
        departureEtaDeltaText: deltaText(beforeDeparture?.eta_min, afterDeparture?.eta_min),
        beforeAlternatives,
        afterAlternatives,
        changed,
    };
});
const compareSummary = computed(() => {
    const result = compare.value;
    if (!result)
        return '';
    if (result.sameSession) {
        return '两个选择器指向同一 session：不构成对比，请把其中一个换成别的 session。';
    }
    const parts = [
        result.arrivalSame ? '推荐段序列相同' : '推荐段序列不同',
        result.etaDeltaText !== '—' ? `到达 ETA 差 ${result.etaDeltaText}` : '到达 ETA 缺值',
        result.departureSame ? '离站路线相同' : '离站路线不同',
        result.beforeAlternatives === result.afterAlternatives
            ? `备选均 ${result.beforeAlternatives} 条`
            : `备选 ${result.beforeAlternatives} / ${result.afterAlternatives} 条`,
    ];
    if (!result.changed) {
        return `无差异：${parts.join('；')}。产物内这两条 session 指向同一条路线，页面如实显示「无变化」，不编造差异。`;
    }
    return `有差异：${parts.join('；')}。差异来自两次 POST /api/traffic/route/recommend 的产物，不是前端改的。`;
});
async function loadOptions() {
    optionsLoading.value = true;
    optionsError.value = '';
    optionsMeta.value = null;
    options.value = [];
    // mock 中间件未匹配路径一律 404：不打一条注定 404 的请求，直接按「mock 无该辅助端点」降级
    if (USE_MOCK) {
        optionsError.value = 'mock 模式无 /api/traffic/route/options 辅助端点（辅助端点仅真接口提供）';
        mainSession.value = `demo-${activePack().key}`;
        optionsLoading.value = false;
        await loadMain();
        return;
    }
    try {
        const snapshot = await getTrafficRouteOptions();
        optionsMeta.value = snapshot;
        options.value = (Array.isArray(snapshot.options) ? snapshot.options : []).filter((item) => Boolean(item.session_id));
        if (options.value.length > 0) {
            mainSession.value = options.value[0]?.session_id ?? '';
            leftSession.value = options.value[0]?.session_id ?? '';
            rightSession.value = options.value[1]?.session_id ?? '';
            await loadMain();
            if (leftSession.value)
                await loadSide('left');
            if (canCompare.value)
                await loadSide('right');
        }
        else {
            mainSession.value = `demo-${activePack().key}`;
            await loadMain();
        }
    }
    catch (e) {
        optionsError.value = e instanceof Error ? e.message : String(e);
        mainSession.value = `demo-${activePack().key}`;
        await loadMain();
    }
    finally {
        optionsLoading.value = false;
    }
}
onMounted(() => {
    void loadOptions();
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
void __VLS_ctx, __VLS_components, __VLS_intrinsics, __VLS_directives;
// @ts-ignore
__VLS_withDotValue(optionsLoading, {});
// @ts-ignore
__VLS_withDotValue(optionsHint, {});
// @ts-ignore
__VLS_withDotValue(optionsMeta, {});
// @ts-ignore
__VLS_withDotValue(options, {});
// @ts-ignore
__VLS_withDotValue(mainLoading, {});
// @ts-ignore
__VLS_withDotValue(mainSession, {});
// @ts-ignore
__VLS_withDotValue(mainError, {});
// @ts-ignore
__VLS_withDotValue(main, {});
// @ts-ignore
__VLS_withDotValue(mainChain, {});
// @ts-ignore
__VLS_withDotValue(mainArrival, {});
// @ts-ignore
__VLS_withDotValue(arrivalSegments, {});
// @ts-ignore
__VLS_withDotValue(alternatives, {});
// @ts-ignore
__VLS_withDotValue(mainSourceNote, {});
// @ts-ignore
__VLS_withDotValue(sessionWarning, {});
// @ts-ignore
__VLS_withDotValue(alternativeNotice, {});
// @ts-ignore
__VLS_withDotValue(canCompare, {});
// @ts-ignore
__VLS_withDotValue(leftLoading, {});
// @ts-ignore
__VLS_withDotValue(leftError, {});
// @ts-ignore
__VLS_withDotValue(left, {});
// @ts-ignore
__VLS_withDotValue(leftChain, {});
// @ts-ignore
__VLS_withDotValue(rightLoading, {});
// @ts-ignore
__VLS_withDotValue(rightError, {});
// @ts-ignore
__VLS_withDotValue(right, {});
// @ts-ignore
__VLS_withDotValue(rightChain, {});
// @ts-ignore
__VLS_withDotValue(compareSummary, {});
// @ts-ignore
__VLS_withDotValue(compare, {});
// @ts-ignore
__VLS_withDotValue(recheckState, {});
// @ts-ignore
__VLS_withDotValue(recheckText, {});
void {};
/** @type {__VLS_StyleScopedClasses['src']} */ ;
/** @type {__VLS_StyleScopedClasses['src']} */ ;
/** @type {__VLS_StyleScopedClasses['route-select']} */ ;
/** @type {__VLS_StyleScopedClasses['chain-node']} */ ;
/** @type {__VLS_StyleScopedClasses['chain-node']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['cn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['chain-node']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['cn-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['chain']} */ ;
/** @type {__VLS_StyleScopedClasses['chain-node']} */ ;
/** @type {__VLS_StyleScopedClasses['chain']} */ ;
/** @type {__VLS_StyleScopedClasses['compact']} */ ;
/** @type {__VLS_StyleScopedClasses['cn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['chain']} */ ;
/** @type {__VLS_StyleScopedClasses['compact']} */ ;
/** @type {__VLS_StyleScopedClasses['cn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['route-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['seg-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['cmp-side']} */ ;
/** @type {__VLS_StyleScopedClasses['cmp-eta']} */ ;
/** @type {__VLS_StyleScopedClasses['cmp-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['recheck-text']} */ ;
/** @type {__VLS_StyleScopedClasses['warn']} */ ;
/** @type {__VLS_StyleScopedClasses['chain']} */ ;
/** @type {__VLS_StyleScopedClasses['chain-arrow']} */ ;
/** @type {__VLS_StyleScopedClasses['cmp-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['pick-row']} */ ;
/** @type {__VLS_StyleScopedClasses['route-select']} */ ;
/** @type {__VLS_StyleScopedClasses['sub-head']} */ ;
/** @type {__VLS_StyleScopedClasses['sub-tag']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "route-view" },
});
/** @type {__VLS_StyleScopedClasses['route-view']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
    ...{ class: "td-card" },
});
/** @type {__VLS_StyleScopedClasses['td-card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-head" },
});
/** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-chip on" },
});
/** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['on']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-chip warn" },
});
/** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['warn']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-body" },
});
/** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "src" },
});
/** @type {__VLS_StyleScopedClasses['src']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "sep" },
});
/** @type {__VLS_StyleScopedClasses['sep']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
if (optionsLoading.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "src" },
    });
    /** @type {__VLS_StyleScopedClasses['src']} */ ;
}
else if (optionsHint.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "src warn" },
    });
    /** @type {__VLS_StyleScopedClasses['src']} */ ;
    /** @type {__VLS_StyleScopedClasses['warn']} */ ;
    (optionsHint.value);
}
if (optionsMeta.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "src" },
    });
    /** @type {__VLS_StyleScopedClasses['src']} */ ;
    (optionsMeta.value.data_source_note || optionsMeta.value.data_source);
    (options.value.length);
    ((optionsMeta.value.segment_namespaces || []).join(' / ') || '—');
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "pick-row" },
});
/** @type {__VLS_StyleScopedClasses['pick-row']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    ...{ class: "pick-label" },
    for: "route-main-session",
});
/** @type {__VLS_StyleScopedClasses['pick-label']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)({
    ...{ onChange: (loadMain) },
    id: "route-main-session",
    value: (mainSession.value),
    ...{ class: "route-select" },
    disabled: (optionsLoading.value || mainLoading.value || (options.value.length === 0 && !mainSession.value)),
});
/** @type {__VLS_StyleScopedClasses['route-select']} */ ;
const __VLS_0 = __VLS_tryAsConstant((options.value));
for (const [option] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
        key: (option.session_id || option.request_id || ''),
        value: (option.session_id || ''),
    });
    (optionLabel(option));
    // @ts-ignore
    [optionsLoading, optionsLoading, optionsHint, optionsHint, optionsMeta, optionsMeta, optionsMeta, optionsMeta, options, options, options, mainSession, mainSession, mainLoading,];
}
if (options.value.length === 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
        value: (mainSession.value),
    });
    (mainSession.value);
}
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (loadMain) },
    type: "button",
    ...{ class: "td-btn sm" },
    disabled: (mainLoading.value || !mainSession.value),
});
/** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['sm']} */ ;
if (mainLoading.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "src" },
    });
    /** @type {__VLS_StyleScopedClasses['src']} */ ;
}
else if (mainError.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "src err" },
    });
    /** @type {__VLS_StyleScopedClasses['src']} */ ;
    /** @type {__VLS_StyleScopedClasses['err']} */ ;
    (mainError.value);
}
else if (main.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "chain" },
        'aria-label': "完整路线链路",
    });
    /** @type {__VLS_StyleScopedClasses['chain']} */ ;
    const __VLS_1 = __VLS_tryAsConstant((mainChain.value));
    for (const [node, index] of __VLS_vFor(__VLS_nonNull(__VLS_1))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.template)({
            key: (node.key),
        });
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "chain-node" },
            ...{ class: ({ empty: node.empty }) },
        });
        /** @type {__VLS_StyleScopedClasses['chain-node']} */ ;
        /** @type {__VLS_StyleScopedClasses['empty']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cn-step" },
        });
        /** @type {__VLS_StyleScopedClasses['cn-step']} */ ;
        (node.step);
        (node.title);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cn-primary" },
        });
        /** @type {__VLS_StyleScopedClasses['cn-primary']} */ ;
        (node.primary);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cn-secondary" },
        });
        /** @type {__VLS_StyleScopedClasses['cn-secondary']} */ ;
        (node.secondary);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cn-tag td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['cn-tag']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (node.tag);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cn-note" },
        });
        /** @type {__VLS_StyleScopedClasses['cn-note']} */ ;
        (node.note);
        if (index < mainChain.value.length - 1) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "chain-arrow" },
                'aria-hidden': "true",
            });
            /** @type {__VLS_StyleScopedClasses['chain-arrow']} */ ;
        }
        // @ts-ignore
        [options, mainSession, mainSession, mainSession, mainLoading, mainLoading, mainError, mainError, main, mainChain, mainChain,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "route-meta" },
    });
    /** @type {__VLS_StyleScopedClasses['route-meta']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
        ...{ class: "td-mono" },
    });
    /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
    (mainArrival.value?.path_id ?? '—');
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (arrivalSegments.value.length);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
        ...{ class: "td-num" },
    });
    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
    (fmtEta(mainArrival.value?.eta_min));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
        ...{ class: "td-num" },
    });
    /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
    (fmtEta(main.value.departure_route?.eta_min));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    (alternatives.value.length);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    (__VLS_unwrap(mainSourceLabel, {}));
    if (mainSourceNote.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "src" },
        });
        /** @type {__VLS_StyleScopedClasses['src']} */ ;
        (mainSourceNote.value);
    }
    if (sessionWarning.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "src warn" },
        });
        /** @type {__VLS_StyleScopedClasses['src']} */ ;
        /** @type {__VLS_StyleScopedClasses['warn']} */ ;
        (sessionWarning.value);
    }
    if ((main.value.segments_not_in_snapshot?.length ?? 0) > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "src warn" },
        });
        /** @type {__VLS_StyleScopedClasses['src']} */ ;
        /** @type {__VLS_StyleScopedClasses['warn']} */ ;
        (main.value.segments_not_in_snapshot?.length);
        ((main.value.segments_not_in_snapshot || []).join('、'));
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "sub-head" },
    });
    /** @type {__VLS_StyleScopedClasses['sub-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "seg-trail" },
    });
    /** @type {__VLS_StyleScopedClasses['seg-trail']} */ ;
    const __VLS_2 = __VLS_tryAsConstant((arrivalSegments.value));
    for (const [segmentId, index] of __VLS_vFor(__VLS_nonNull(__VLS_2))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.template)({
            key: (`${segmentId}-${index}`),
        });
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "seg-chip" },
        });
        /** @type {__VLS_StyleScopedClasses['seg-chip']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
            ...{ class: "td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (segmentId);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        (segmentName(segmentId));
        if (index < arrivalSegments.value.length - 1) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "trail-arrow" },
                'aria-hidden': "true",
            });
            /** @type {__VLS_StyleScopedClasses['trail-arrow']} */ ;
        }
        // @ts-ignore
        [main, main, main, main, mainArrival, mainArrival, arrivalSegments, arrivalSegments, arrivalSegments, alternatives, mainSourceLabel, mainSourceNote, mainSourceNote, sessionWarning, sessionWarning,];
    }
    if (arrivalSegments.value.length === 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "src" },
        });
        /** @type {__VLS_StyleScopedClasses['src']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "why" },
    });
    /** @type {__VLS_StyleScopedClasses['why']} */ ;
    (main.value.why || '引擎产物未给 why');
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "sub-head" },
    });
    /** @type {__VLS_StyleScopedClasses['sub-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "sub-tag" },
    });
    /** @type {__VLS_StyleScopedClasses['sub-tag']} */ ;
    (alternatives.value.length);
    if (alternativeNotice.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "src warn" },
        });
        /** @type {__VLS_StyleScopedClasses['src']} */ ;
        /** @type {__VLS_StyleScopedClasses['warn']} */ ;
        (alternativeNotice.value);
    }
    if (alternatives.value.length > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "alt-list" },
        });
        /** @type {__VLS_StyleScopedClasses['alt-list']} */ ;
        const __VLS_3 = __VLS_tryAsConstant((alternatives.value));
        for (const [alt, index] of __VLS_vFor(__VLS_nonNull(__VLS_3))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                key: (`${alt.path_id}-${index}`),
                ...{ class: "alt-row" },
            });
            /** @type {__VLS_StyleScopedClasses['alt-row']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "alt-head" },
            });
            /** @type {__VLS_StyleScopedClasses['alt-head']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "alt-name" },
            });
            /** @type {__VLS_StyleScopedClasses['alt-name']} */ ;
            (index + 1);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "td-mono" },
            });
            /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
            (alt.path_id);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "alt-eta td-num" },
            });
            /** @type {__VLS_StyleScopedClasses['alt-eta']} */ ;
            /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
            (fmtEta(alt.eta_min));
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "td-chip" },
            });
            /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
            (deltaText(mainArrival.value?.eta_min, alt.eta_min));
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "alt-why" },
            });
            /** @type {__VLS_StyleScopedClasses['alt-why']} */ ;
            (alt.reason || '引擎产物未给 reason');
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "alt-segs td-mono" },
            });
            /** @type {__VLS_StyleScopedClasses['alt-segs']} */ ;
            /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
            ((alt.segments || []).join(' → ') || '引擎产物未给备选段序列');
            // @ts-ignore
            [main, mainArrival, arrivalSegments, alternatives, alternatives, alternatives, alternativeNotice, alternativeNotice,];
        }
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "src" },
        });
        /** @type {__VLS_StyleScopedClasses['src']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "foot-line" },
    });
    /** @type {__VLS_StyleScopedClasses['foot-line']} */ ;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "src" },
    });
    /** @type {__VLS_StyleScopedClasses['src']} */ ;
}
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
    ...{ class: "src" },
});
/** @type {__VLS_StyleScopedClasses['src']} */ ;
if (canCompare.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cmp-grid" },
    });
    /** @type {__VLS_StyleScopedClasses['cmp-grid']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cmp-side" },
    });
    /** @type {__VLS_StyleScopedClasses['cmp-side']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cmp-head" },
    });
    /** @type {__VLS_StyleScopedClasses['cmp-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "cmp-title" },
    });
    /** @type {__VLS_StyleScopedClasses['cmp-title']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)({
        ...{ onChange: // @ts-ignore
            (...[$event]) => {
                void $event;
                if (!(canCompare.value))
                    throw 0;
                return (loadSide('left'));
                // @ts-ignore
                [canCompare,];
            } },
        value: (__VLS_unwrap(leftSession, {})),
        ...{ class: "route-select" },
        'aria-label': "左列 session",
    });
    /** @type {__VLS_StyleScopedClasses['route-select']} */ ;
    const __VLS_4 = __VLS_tryAsConstant((options.value));
    for (const [option] of __VLS_vFor(__VLS_nonNull(__VLS_4))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
            key: (`left-${option.session_id || option.request_id || ''}`),
            value: (option.session_id || ''),
        });
        (optionLabel(option));
        // @ts-ignore
        [options, leftSession,];
    }
    if (leftLoading.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "src" },
        });
        /** @type {__VLS_StyleScopedClasses['src']} */ ;
    }
    else if (leftError.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "src err" },
        });
        /** @type {__VLS_StyleScopedClasses['src']} */ ;
        /** @type {__VLS_StyleScopedClasses['err']} */ ;
        (leftError.value);
    }
    else if (left.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "chain compact" },
        });
        /** @type {__VLS_StyleScopedClasses['chain']} */ ;
        /** @type {__VLS_StyleScopedClasses['compact']} */ ;
        const __VLS_5 = __VLS_tryAsConstant((leftChain.value));
        for (const [node, index] of __VLS_vFor(__VLS_nonNull(__VLS_5))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.template)({
                key: (`left-${node.key}`),
            });
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "chain-node" },
                ...{ class: ({ empty: node.empty }) },
            });
            /** @type {__VLS_StyleScopedClasses['chain-node']} */ ;
            /** @type {__VLS_StyleScopedClasses['empty']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cn-step" },
            });
            /** @type {__VLS_StyleScopedClasses['cn-step']} */ ;
            (node.step);
            (node.title);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cn-primary" },
            });
            /** @type {__VLS_StyleScopedClasses['cn-primary']} */ ;
            (node.primary);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cn-secondary" },
            });
            /** @type {__VLS_StyleScopedClasses['cn-secondary']} */ ;
            (node.secondary);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cn-tag td-mono" },
            });
            /** @type {__VLS_StyleScopedClasses['cn-tag']} */ ;
            /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
            (node.tag);
            if (index < leftChain.value.length - 1) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "chain-arrow" },
                    'aria-hidden': "true",
                });
                /** @type {__VLS_StyleScopedClasses['chain-arrow']} */ ;
            }
            // @ts-ignore
            [leftLoading, leftError, leftError, left, leftChain, leftChain,];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cmp-eta" },
        });
        /** @type {__VLS_StyleScopedClasses['cmp-eta']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
            ...{ class: "td-num" },
        });
        /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
        (fmtEta(arrivalOf(left.value)?.eta_min));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "sep" },
        });
        /** @type {__VLS_StyleScopedClasses['sep']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
            ...{ class: "td-num" },
        });
        /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
        (fmtEta(left.value.departure_route?.eta_min));
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "why" },
        });
        /** @type {__VLS_StyleScopedClasses['why']} */ ;
        (left.value.why || '—');
        if (left.value.session_matched === false) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "src warn" },
            });
            /** @type {__VLS_StyleScopedClasses['src']} */ ;
            /** @type {__VLS_StyleScopedClasses['warn']} */ ;
        }
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "src" },
        });
        /** @type {__VLS_StyleScopedClasses['src']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cmp-side" },
    });
    /** @type {__VLS_StyleScopedClasses['cmp-side']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cmp-head" },
    });
    /** @type {__VLS_StyleScopedClasses['cmp-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "cmp-title" },
    });
    /** @type {__VLS_StyleScopedClasses['cmp-title']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)({
        ...{ onChange: // @ts-ignore
            (...[$event]) => {
                void $event;
                if (!(canCompare.value))
                    throw 0;
                return (loadSide('right'));
                // @ts-ignore
                [left, left, left, left,];
            } },
        value: (__VLS_unwrap(rightSession, {})),
        ...{ class: "route-select" },
        'aria-label': "右列 session",
    });
    /** @type {__VLS_StyleScopedClasses['route-select']} */ ;
    const __VLS_6 = __VLS_tryAsConstant((options.value));
    for (const [option] of __VLS_vFor(__VLS_nonNull(__VLS_6))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
            key: (`right-${option.session_id || option.request_id || ''}`),
            value: (option.session_id || ''),
        });
        (optionLabel(option));
        // @ts-ignore
        [options, rightSession,];
    }
    if (rightLoading.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "src" },
        });
        /** @type {__VLS_StyleScopedClasses['src']} */ ;
    }
    else if (rightError.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "src err" },
        });
        /** @type {__VLS_StyleScopedClasses['src']} */ ;
        /** @type {__VLS_StyleScopedClasses['err']} */ ;
        (rightError.value);
    }
    else if (right.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "chain compact" },
        });
        /** @type {__VLS_StyleScopedClasses['chain']} */ ;
        /** @type {__VLS_StyleScopedClasses['compact']} */ ;
        const __VLS_7 = __VLS_tryAsConstant((rightChain.value));
        for (const [node, index] of __VLS_vFor(__VLS_nonNull(__VLS_7))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.template)({
                key: (`right-${node.key}`),
            });
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "chain-node" },
                ...{ class: ({ empty: node.empty }) },
            });
            /** @type {__VLS_StyleScopedClasses['chain-node']} */ ;
            /** @type {__VLS_StyleScopedClasses['empty']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cn-step" },
            });
            /** @type {__VLS_StyleScopedClasses['cn-step']} */ ;
            (node.step);
            (node.title);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cn-primary" },
            });
            /** @type {__VLS_StyleScopedClasses['cn-primary']} */ ;
            (node.primary);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cn-secondary" },
            });
            /** @type {__VLS_StyleScopedClasses['cn-secondary']} */ ;
            (node.secondary);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cn-tag td-mono" },
            });
            /** @type {__VLS_StyleScopedClasses['cn-tag']} */ ;
            /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
            (node.tag);
            if (index < rightChain.value.length - 1) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "chain-arrow" },
                    'aria-hidden': "true",
                });
                /** @type {__VLS_StyleScopedClasses['chain-arrow']} */ ;
            }
            // @ts-ignore
            [rightLoading, rightError, rightError, right, rightChain, rightChain,];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cmp-eta" },
        });
        /** @type {__VLS_StyleScopedClasses['cmp-eta']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
            ...{ class: "td-num" },
        });
        /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
        (fmtEta(arrivalOf(right.value)?.eta_min));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "sep" },
        });
        /** @type {__VLS_StyleScopedClasses['sep']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
            ...{ class: "td-num" },
        });
        /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
        (fmtEta(right.value.departure_route?.eta_min));
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "why" },
        });
        /** @type {__VLS_StyleScopedClasses['why']} */ ;
        (right.value.why || '—');
        if (right.value.session_matched === false) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "src warn" },
            });
            /** @type {__VLS_StyleScopedClasses['src']} */ ;
            /** @type {__VLS_StyleScopedClasses['warn']} */ ;
        }
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "src" },
        });
        /** @type {__VLS_StyleScopedClasses['src']} */ ;
    }
    if (compareSummary.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "cmp-summary" },
            ...{ class: ({ diff: compare.value?.changed }) },
        });
        /** @type {__VLS_StyleScopedClasses['cmp-summary']} */ ;
        /** @type {__VLS_StyleScopedClasses['diff']} */ ;
        (compareSummary.value);
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "src warn" },
    });
    /** @type {__VLS_StyleScopedClasses['src']} */ ;
    /** @type {__VLS_StyleScopedClasses['warn']} */ ;
    (options.value.length);
    (options.value.length === 0 ? '无引擎 session 选项，下面只展示当前回退演示会话路线' : '只展示当前唯一 session 的路线');
    if (main.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cmp-side single" },
        });
        /** @type {__VLS_StyleScopedClasses['cmp-side']} */ ;
        /** @type {__VLS_StyleScopedClasses['single']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "chain compact" },
        });
        /** @type {__VLS_StyleScopedClasses['chain']} */ ;
        /** @type {__VLS_StyleScopedClasses['compact']} */ ;
        const __VLS_8 = __VLS_tryAsConstant((mainChain.value));
        for (const [node, index] of __VLS_vFor(__VLS_nonNull(__VLS_8))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.template)({
                key: (`single-${node.key}`),
            });
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "chain-node" },
                ...{ class: ({ empty: node.empty }) },
            });
            /** @type {__VLS_StyleScopedClasses['chain-node']} */ ;
            /** @type {__VLS_StyleScopedClasses['empty']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cn-step" },
            });
            /** @type {__VLS_StyleScopedClasses['cn-step']} */ ;
            (node.step);
            (node.title);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cn-primary" },
            });
            /** @type {__VLS_StyleScopedClasses['cn-primary']} */ ;
            (node.primary);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cn-secondary" },
            });
            /** @type {__VLS_StyleScopedClasses['cn-secondary']} */ ;
            (node.secondary);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cn-tag td-mono" },
            });
            /** @type {__VLS_StyleScopedClasses['cn-tag']} */ ;
            /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
            (node.tag);
            if (index < mainChain.value.length - 1) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "chain-arrow" },
                    'aria-hidden': "true",
                });
                /** @type {__VLS_StyleScopedClasses['chain-arrow']} */ ;
            }
            // @ts-ignore
            [options, options, main, mainChain, mainChain, right, right, right, right, compareSummary, compareSummary, compare,];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cmp-eta" },
        });
        /** @type {__VLS_StyleScopedClasses['cmp-eta']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
            ...{ class: "td-num" },
        });
        /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
        (fmtEta(mainArrival.value?.eta_min));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "sep" },
        });
        /** @type {__VLS_StyleScopedClasses['sep']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({
            ...{ class: "td-num" },
        });
        /** @type {__VLS_StyleScopedClasses['td-num']} */ ;
        (fmtEta(main.value.departure_route?.eta_min));
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "src" },
        });
        /** @type {__VLS_StyleScopedClasses['src']} */ ;
    }
}
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "verdict" },
});
/** @type {__VLS_StyleScopedClasses['verdict']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "tbl-wrap" },
});
/** @type {__VLS_StyleScopedClasses['tbl-wrap']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.table, __VLS_intrinsics.table)({
    ...{ class: "td-table" },
});
/** @type {__VLS_StyleScopedClasses['td-table']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.thead, __VLS_intrinsics.thead)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.tbody, __VLS_intrinsics.tbody)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "recheck" },
});
/** @type {__VLS_StyleScopedClasses['recheck']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (recheckSameSession) },
    type: "button",
    ...{ class: "td-btn sm" },
    disabled: (recheckState.value === 'running' || !main.value),
});
/** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['sm']} */ ;
(recheckState.value === 'running' ? '正在重新读取…' : '重新读取当前 session 产物并比对');
if (recheckText.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "recheck-text" },
        ...{ class: ({ warn: recheckState.value === 'diff' }) },
    });
    /** @type {__VLS_StyleScopedClasses['recheck-text']} */ ;
    /** @type {__VLS_StyleScopedClasses['warn']} */ ;
    (recheckText.value);
}
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "src" },
});
/** @type {__VLS_StyleScopedClasses['src']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "foot-line" },
});
/** @type {__VLS_StyleScopedClasses['foot-line']} */ ;
// @ts-ignore
[main, main, mainArrival, recheckState, recheckState, recheckState, recheckText, recheckText,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
