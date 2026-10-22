/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 监控墙:N 路摄像头**分页**展示(默认每页 12 格 = 3 列 × 4 行)。
//
// IKMS1T 去固定 6 路:登记表 N 动态(0..路段数,默认每段最多 1 路),61 路不能一屏挤爆,
// 故本组件负责 ① 分页(每页 12) ② 筛选(全部 / 有视频源 / 无视频源) ③ 0 路空态。
// 整墙共用一个抽帧时钟(设计稿口径「抽帧 1 帧 / 2 s」),各通道按自己的 fps 推进自己的帧序。
// 深色 token 只在本卡片内的画面格生效(CSS 变量下发,避免深色外溢到壳层)。
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { TD_VIDEO } from '../../../shared/theme';
import { demoCameraCount } from '../../../shared/cameras';
import MonitorCell from './MonitorCell.vue';
const { defineProps, defineEmits, } = {};
const props = defineProps();
const emit = defineEmits();
const GAP = 6;
const TICK_MS = 2000;
/** 每页格数:3 列 × 4 行;61 路 → 6 页,不会一格挤爆 */
const PAGE_SIZE = 12;
const idxMap = ref({});
const playing = ref(true);
const speed = ref(1);
const filter = ref('all');
const page = ref(1);
const gridRef = ref(null);
const cellW = ref(0);
let timer = 0;
let ro = null;
const SPEEDS = [1, 2, 4];
// 深色例外 token:仅本卡片内的画面格引用这些变量(对象字面量不加显式 Record 注解,便于 :style 绑定)
const videoVars = {
    '--v-bg': TD_VIDEO.bg,
    '--v-bg1': TD_VIDEO.bg1,
    '--v-bg2': TD_VIDEO.bg2,
    '--v-line': TD_VIDEO.line,
    '--v-dim': TD_VIDEO.dim,
    '--v-text': TD_VIDEO.text,
    '--v-textdim': TD_VIDEO.textDim,
    '--v-brand': TD_VIDEO.brand,
};
/** 通道总数 N(源台账条数;0 路合法;≠ 一期演示摄像头总数,见 demoCameraTotal) */
const total = computed(() => props.channels.length);
/** 一期演示摄像头总数 = 路段数（N 段 = N 摄像头 = N 视频，mock 复用；IKNBT2） */
const demoCameraTotal = computed(() => demoCameraCount());
/** 有视频源的通道数(登记表 has_video_source=true;不等于样本视频已导出) */
const videoCount = computed(() => props.channels.filter((c) => c.def.hasVideo).length);
/** 未接入视频源的通道数(Issue IKLX5Y) */
const noVideoCount = computed(() => total.value - videoCount.value);
/** 有视频源且服务端真返回了 meta 的通道数(未接入视频源的不算"已导出") */
const exportedCount = computed(() => props.channels.filter((c) => c.def.hasVideo && c.meta !== null).length);
const filters = computed(() => [
    { key: 'all', text: '全部', count: total.value },
    { key: 'video', text: '有视频源', count: videoCount.value },
    { key: 'novideo', text: '无视频源', count: noVideoCount.value },
]);
/** 当前筛选下的通道(IKMS1T:61 路按"有 / 无视频源"过滤,不靠肉眼在墙上找) */
const filtered = computed(() => {
    if (filter.value === 'video')
        return props.channels.filter((c) => c.def.hasVideo);
    if (filter.value === 'novideo')
        return props.channels.filter((c) => !c.def.hasVideo);
    return props.channels;
});
const pageCount = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE_SIZE)));
/** 实际生效页码:筛选变化后条数变少时自动收口,不出现"空页" */
const safePage = computed(() => Math.min(Math.max(1, page.value), pageCount.value));
// 分页切片:每页 12 格;61 路 → 6 页(3 × 4 × 6)
const paged = computed(() => filtered.value.slice((safePage.value - 1) * PAGE_SIZE, safePage.value * PAGE_SIZE));
const rangeText = computed(() => {
    const n = filtered.value.length;
    if (n === 0)
        return '0 路';
    const from = (safePage.value - 1) * PAGE_SIZE + 1;
    const to = Math.min(safePage.value * PAGE_SIZE, n);
    return `${from}–${to} / ${n} 路`;
});
const emptyHint = computed(() => {
    if (total.value === 0) {
        return `源台账 0 路（仅初始映射）· 一期演示摄像头 ${demoCameraTotal.value} 路（N 段 = N 摄像头 = N 视频，mock 复用）`;
    }
    if (filter.value === 'video' && videoCount.value === 0)
        return `当前 ${total.value} 路都没有视频源`;
    if (filter.value === 'novideo' && noVideoCount.value === 0)
        return `全部 ${total.value} 路都已接入视频源`;
    return `切回「全部」可看 ${total.value} 路（其中 ${noVideoCount.value} 路未接入视频源）`;
});
function setFilter(key) {
    filter.value = key;
    page.value = 1;
}
function goto(p) {
    page.value = Math.min(Math.max(1, p), pageCount.value);
}
// 左栏台账点选 → 监控墙跳到该路所在页;若它被当前筛选藏掉,先切回"全部"再跳。
// 监听 `selectTick`:再次点中同一路时 currentId 不变,但也要回到该页/取消筛选。
// `immediate`:61 路深链/默认选中不在第 1 页时,首屏就要落在正确页。
watch([() => props.currentId, () => props.selectTick ?? 0], ([id]) => {
    const allIdx = props.channels.findIndex((c) => c.def.source === id);
    if (allIdx < 0)
        return;
    const idx = filtered.value.findIndex((c) => c.def.source === id);
    if (idx >= 0) {
        page.value = Math.floor(idx / PAGE_SIZE) + 1;
        return;
    }
    filter.value = 'all';
    page.value = Math.floor(allIdx / PAGE_SIZE) + 1;
}, { immediate: true });
function tick() {
    if (!playing.value)
        return;
    const next = { ...idxMap.value };
    for (const c of props.channels) {
        const m = c.meta;
        if (!m || m.total_frames <= 0)
            continue;
        const step = Math.max(1, Math.round(m.fps * 2 * speed.value));
        const cur = next[c.def.source] ?? 0;
        next[c.def.source] = (cur + step) % m.total_frames;
    }
    idxMap.value = next;
}
function measure() {
    const el = gridRef.value;
    if (!el)
        return;
    // 列数随断点变化（≤900 两列 / ≤560 单列），从计算样式里读实际轨道数，不再写死 3 列；
    // 三列时的取值公式与改前完全一致（(宽 - 2 个间隙) / 3），1920×1080 的缩放显示不退化。
    const tracks = (getComputedStyle(el).gridTemplateColumns || '').split(' ').filter(Boolean).length || 3;
    cellW.value = el.clientWidth > 0 ? (el.clientWidth - GAP * (tracks - 1)) / tracks : 0;
}
function indexOf(source) {
    return idxMap.value[source] ?? 0;
}
function scaleOf(c) {
    if (!c.meta || cellW.value <= 0)
        return null;
    return cellW.value / c.meta.width;
}
onMounted(() => {
    measure();
    if (typeof ResizeObserver !== 'undefined' && gridRef.value) {
        ro = new ResizeObserver(measure);
        ro.observe(gridRef.value);
    }
    timer = window.setInterval(tick, TICK_MS);
});
onUnmounted(() => {
    if (ro)
        ro.disconnect();
    window.clearInterval(timer);
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
__VLS_withDotValue(total, {});
// @ts-ignore
__VLS_withDotValue(playing, {});
// @ts-ignore
__VLS_withDotValue(speed, {});
// @ts-ignore
__VLS_withDotValue(filter, {});
// @ts-ignore
__VLS_withDotValue(filtered, {});
void {};
/** @type {__VLS_StyleScopedClasses['wall-empty']} */ ;
/** @type {__VLS_StyleScopedClasses['wall-pager']} */ ;
/** @type {__VLS_StyleScopedClasses['wall-pager']} */ ;
/** @type {__VLS_StyleScopedClasses['top']} */ ;
/** @type {__VLS_StyleScopedClasses['wall-hint']} */ ;
/** @type {__VLS_StyleScopedClasses['page-info']} */ ;
/** @type {__VLS_StyleScopedClasses['wall-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['wall-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['wall-tools']} */ ;
/** @type {__VLS_StyleScopedClasses['wall-pager']} */ ;
/** @type {__VLS_StyleScopedClasses['wall-hint']} */ ;
/** @type {__VLS_StyleScopedClasses['wall-empty']} */ ;
/** @type {__VLS_StyleScopedClasses['we-l2']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
    ...{ class: "td-card" },
    ...{ style: (__VLS_unwrap(videoVars, {})) },
});
/** @type {__VLS_StyleScopedClasses['td-card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-head" },
});
/** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
(total.value);
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-head-tag" },
});
/** @type {__VLS_StyleScopedClasses['td-head-tag']} */ ;
(__VLS_unwrap(PAGE_SIZE, {}));
if (total.value === 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "wall-empty" },
    });
    /** @type {__VLS_StyleScopedClasses['wall-empty']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "we-l1" },
    });
    /** @type {__VLS_StyleScopedClasses['we-l1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "we-l2" },
    });
    /** @type {__VLS_StyleScopedClasses['we-l2']} */ ;
    (__VLS_unwrap(demoCameraTotal, {}));
    (__VLS_unwrap(demoCameraTotal, {}));
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "wall-tools" },
    });
    /** @type {__VLS_StyleScopedClasses['wall-tools']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                if (!!(total.value === 0))
                    throw 0;
                return (playing.value = !playing.value);
                // @ts-ignore
                [videoVars, total, total, PAGE_SIZE, demoCameraTotal, demoCameraTotal, playing, playing,];
            } },
        ...{ class: "td-btn sm" },
        type: "button",
    });
    /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
    /** @type {__VLS_StyleScopedClasses['sm']} */ ;
    (playing.value ? '暂停' : '播放');
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-seg" },
        role: "group",
        'aria-label': "抽帧倍速",
    });
    /** @type {__VLS_StyleScopedClasses['td-seg']} */ ;
    const __VLS_0 = __VLS_tryAsConstant((__VLS_unwrap(SPEEDS, {})));
    for (const [s] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ onClick: // @ts-ignore
                (...[$event]) => {
                    void $event;
                    if (!!(total.value === 0))
                        throw 0;
                    return (speed.value = s);
                    // @ts-ignore
                    [playing, SPEEDS, speed,];
                } },
            key: (s),
            ...{ class: "td-seg-item" },
            ...{ class: ({ on: speed.value === s }) },
            role: "button",
            'aria-pressed': (speed.value === s),
        });
        /** @type {__VLS_StyleScopedClasses['td-seg-item']} */ ;
        /** @type {__VLS_StyleScopedClasses['on']} */ ;
        (s);
        // @ts-ignore
        [speed, speed,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-seg" },
        role: "group",
        'aria-label': "按视频源筛选",
    });
    /** @type {__VLS_StyleScopedClasses['td-seg']} */ ;
    const __VLS_1 = __VLS_tryAsConstant((__VLS_unwrap(filters, {})));
    for (const [f] of __VLS_vFor(__VLS_nonNull(__VLS_1))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ onClick: // @ts-ignore
                (...[$event]) => {
                    void $event;
                    if (!!(total.value === 0))
                        throw 0;
                    return (setFilter(f.key));
                    // @ts-ignore
                    [filters,];
                } },
            key: (f.key),
            ...{ class: "td-seg-item" },
            ...{ class: ({ on: filter.value === f.key }) },
            role: "button",
            'aria-pressed': (filter.value === f.key),
        });
        /** @type {__VLS_StyleScopedClasses['td-seg-item']} */ ;
        /** @type {__VLS_StyleScopedClasses['on']} */ ;
        (f.text);
        (f.count);
        // @ts-ignore
        [filter, filter,];
    }
    if (__VLS_unwrap(pageCount, {}) > 1) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "wall-pager top" },
        });
        /** @type {__VLS_StyleScopedClasses['wall-pager']} */ ;
        /** @type {__VLS_StyleScopedClasses['top']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: // @ts-ignore
                (...[$event]) => {
                    void $event;
                    if (!!(total.value === 0))
                        throw 0;
                    if (!(__VLS_unwrap(pageCount, {}) > 1))
                        throw 0;
                    return (goto(__VLS_unwrap(safePage, {}) - 1));
                    // @ts-ignore
                    [pageCount, safePage,];
                } },
            ...{ class: "td-btn sm" },
            type: "button",
            disabled: (__VLS_unwrap(safePage, {}) <= 1),
        });
        /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "page-info td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['page-info']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (__VLS_unwrap(safePage, {}));
        (__VLS_unwrap(pageCount, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: // @ts-ignore
                (...[$event]) => {
                    void $event;
                    if (!!(total.value === 0))
                        throw 0;
                    if (!(__VLS_unwrap(pageCount, {}) > 1))
                        throw 0;
                    return (goto(__VLS_unwrap(safePage, {}) + 1));
                    // @ts-ignore
                    [pageCount, safePage, safePage, safePage,];
                } },
            ...{ class: "td-btn sm" },
            type: "button",
            disabled: (__VLS_unwrap(safePage, {}) >= __VLS_unwrap(pageCount, {})),
        });
        /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "wall-hint" },
    });
    /** @type {__VLS_StyleScopedClasses['wall-hint']} */ ;
    (__VLS_unwrap(exportedCount, {}));
    (total.value);
    if (__VLS_unwrap(noVideoCount, {}) > 0) {
        (__VLS_unwrap(noVideoCount, {}));
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ref: "gridRef",
        ...{ class: "wall-grid" },
    });
    /** @type {__VLS_StyleScopedClasses['wall-grid']} */ ;
    const __VLS_2 = __VLS_tryAsConstant((__VLS_unwrap(paged, {})));
    for (const [c] of __VLS_vFor(__VLS_nonNull(__VLS_2))) {
        const __VLS_3 = MonitorCell;
        // @ts-ignore
        const __VLS_4 = __VLS_asFunctionalComponent1(__VLS_3, new __VLS_3({
            // @ts-ignore
            ...{ 'onSelect': {} }, key: (c.def.source), ch: (c), index: (indexOf(c.def.source)), selected: (c.def.source === __VLS_ctx.currentId), scale: (scaleOf(c)),
        }));
        const __VLS_5 = __VLS_4({
            ...{ 'onSelect': {} },
            key: (c.def.source),
            ch: (c),
            index: (indexOf(c.def.source)),
            selected: (c.def.source === __VLS_ctx.currentId),
            scale: (scaleOf(c)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_4));
        let __VLS_8;
        const __VLS_9 = {
            /** @type {typeof __VLS_8.select} */
            onSelect: // @ts-ignore
            (...[$event]) => {
                void $event;
                if (!!(total.value === 0))
                    throw 0;
                return (__VLS_unwrap(emit, {})('select', c.def.source));
                // @ts-ignore
                [total, pageCount, safePage, exportedCount, noVideoCount, noVideoCount, paged, currentId, emit,];
            },
        };
        void __VLS_9;
        var __VLS_6;
        var __VLS_7;
        // @ts-ignore
        [];
    }
    if (filtered.value.length === 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "wall-empty small" },
        });
        /** @type {__VLS_StyleScopedClasses['wall-empty']} */ ;
        /** @type {__VLS_StyleScopedClasses['small']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "we-l1" },
        });
        /** @type {__VLS_StyleScopedClasses['we-l1']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "we-l2" },
        });
        /** @type {__VLS_StyleScopedClasses['we-l2']} */ ;
        (__VLS_unwrap(emptyHint, {}));
    }
    if (__VLS_unwrap(pageCount, {}) > 1) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "wall-pager" },
        });
        /** @type {__VLS_StyleScopedClasses['wall-pager']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: // @ts-ignore
                (...[$event]) => {
                    void $event;
                    if (!!(total.value === 0))
                        throw 0;
                    if (!(__VLS_unwrap(pageCount, {}) > 1))
                        throw 0;
                    return (goto(1));
                    // @ts-ignore
                    [pageCount, filtered, emptyHint,];
                } },
            ...{ class: "td-btn sm" },
            type: "button",
            disabled: (__VLS_unwrap(safePage, {}) <= 1),
        });
        /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: // @ts-ignore
                (...[$event]) => {
                    void $event;
                    if (!!(total.value === 0))
                        throw 0;
                    if (!(__VLS_unwrap(pageCount, {}) > 1))
                        throw 0;
                    return (goto(__VLS_unwrap(safePage, {}) - 1));
                    // @ts-ignore
                    [safePage, safePage,];
                } },
            ...{ class: "td-btn sm" },
            type: "button",
            disabled: (__VLS_unwrap(safePage, {}) <= 1),
        });
        /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "page-info td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['page-info']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (__VLS_unwrap(safePage, {}));
        (__VLS_unwrap(pageCount, {}));
        (__VLS_unwrap(rangeText, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: // @ts-ignore
                (...[$event]) => {
                    void $event;
                    if (!!(total.value === 0))
                        throw 0;
                    if (!(__VLS_unwrap(pageCount, {}) > 1))
                        throw 0;
                    return (goto(__VLS_unwrap(safePage, {}) + 1));
                    // @ts-ignore
                    [pageCount, safePage, safePage, safePage, rangeText,];
                } },
            ...{ class: "td-btn sm" },
            type: "button",
            disabled: (__VLS_unwrap(safePage, {}) >= __VLS_unwrap(pageCount, {})),
        });
        /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: // @ts-ignore
                (...[$event]) => {
                    void $event;
                    if (!!(total.value === 0))
                        throw 0;
                    if (!(__VLS_unwrap(pageCount, {}) > 1))
                        throw 0;
                    return (goto(__VLS_unwrap(pageCount, {})));
                    // @ts-ignore
                    [pageCount, pageCount, safePage,];
                } },
            ...{ class: "td-btn sm" },
            type: "button",
            disabled: (__VLS_unwrap(safePage, {}) >= __VLS_unwrap(pageCount, {})),
        });
        /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm']} */ ;
    }
}
// @ts-ignore
[pageCount, safePage,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
