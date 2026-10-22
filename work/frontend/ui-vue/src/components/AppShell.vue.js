/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 四页共用的应用壳(TDesign Light):顶栏(品牌 + 页签 + 站点 + 数据源 + 快照时间 + 演示角标)+ 页头 + 主体 + 页脚。
// 顶栏骨架在 4 张设计稿里完全一致,抽成一处以免四页各写一套(改一次四处生效)。
// 语义纪律:页签「当前页」与数据源「已选」一律用品牌蓝;等级色不得出现在壳层。
import { computed, onBeforeUnmount, onMounted, ref, useSlots } from 'vue';
import { RouterLink } from 'vue-router';
import { backendReachable } from '../api/http';
import { APP_TABS, DEMO_BADGE, SOURCE_ITEMS } from '../shared/nav';
import { USE_MOCK } from '../shared/env';
import { basemapEnabled, directionsVisible, setBasemapEnabled, setDirectionsVisible, } from '../shared/settings';
import { formatStamp } from '../shared/traffic';
import { TD } from '../shared/theme';
import { activePack, activePackKey, onPackChange, packItems } from '../station-packs/index';
import { switchStation } from '../shared/stationSwitch';
const { defineProps, defineEmits, withDefaults, } = {};
const props = withDefaults(defineProps(), { ts: '', sourceMode: null, title: '', subtitle: '' });
const emit = defineEmits();
const slots = useSlots();
const showHead = computed(() => props.title !== '' || !!slots.headRight);
/** 包键代号：切站时 +1，给"读 activePack() 的 computed"补一个响应式依赖（IKPFR4） */
const packTick = ref(0);
/**
 * 顶栏站点 chip。缺省从**当前站点包**取 —— 注意不能把 `activePack().station.name`
 * 写进 `withDefaults` 的默认值:那个表达式在**模块求值期**就跑了,早于入口
 * (`main.ts` / vite 配置)注入包键,会恒定取到默认包(而不是入口注入的那个)。所以这里惰性取。
 *
 * ⚠️ Issue IKPFR4：`activePack()` 读的是模块级变量，computed 不知道它变了 ——
 *    所以显式读一次 `packTick`（切站时由 `onPackChange` 更新），兜底站名才会跟着换。
 */
const stationName = computed(() => {
    if (props.station !== undefined)
        return props.station;
    void packTick.value; // 显式依赖：切站时 packTick 变化 → 这里重算，取到新包的站名
    return activePack().station.name;
});
const modeChip = computed(() => {
    if (USE_MOCK) {
        return {
            label: 'mock',
            note: 'mock：/api 由 vite mock 中间件回答，不需要 traffic.py（npm run dev）',
            warn: false,
        };
    }
    if (backendReachable.value === false) {
        return {
            label: 'remote · 后端不可达',
            note: 'remote：/api 走 vite 代理到 127.0.0.1:8000，请先起接口层：python work/assembly/traffic.py --port 8000',
            warn: true,
        };
    }
    return {
        label: 'remote',
        note: 'remote：/api 走 vite 代理到 traffic.py（127.0.0.1:8000）',
        warn: false,
    };
});
// ---- 线路图切换器(业主 2026-10-14):顶栏直接选包,选完即换整套路网/基线 ----
// 2026-10-17(IKMDKY 子单①):切包器恢复显示；2026-10-21(IKP5D3):Z21 过渡包已删除，
// 现为 Z(61 段)/ GZ(708 段)两个站包 —— 切包键必须都在后端站点登记表里，否则切过去全站 404。
// 只有一个包时仍不渲染(留一个只有单项的下拉就是死控件)。
const packList = packItems();
const packKey = ref(activePackKey());
const packOpen = ref(false);
// 包键是模块级变量、不参与响应式 —— 订阅一次把它同步成 ref，
// 这样在大屏工具条上切的站，顶栏这里的标签也跟着变（两个入口一个真相）。
const offPackSync = onPackChange(() => {
    packKey.value = activePackKey();
    packTick.value += 1;
});
onBeforeUnmount(offPackSync);
/**
 * 换站。**不再整页刷新**（Issue IKPFR4）：统一走 `switchStation()` ——
 * 切包 → 重建路网几何 → 站内状态重置 → 缓存优先渲染首屏 → 后台补拉 → 同步 URL。
 * 详情见 `shared/stationSwitch.ts` 头部注释与 `work/frontend/README.md` 第二十四节。
 */
function choosePack(key) {
    packOpen.value = false;
    if (key === packKey.value)
        return;
    // 立即回写一次，让"点了就变"；`onPackChange` 那条订阅是同一份数据的同步，
    // 两处都写是幂等的（键相同不会再触发流程）。返回 false = 键没换（非法键 / 已经是该站）
    if (switchStation(key))
        packKey.value = key;
}
// ---- 设置（业主 2026-10-16 / Issue IKP5BD）：大屏地图的**底图开关 + 方向标记开关** ----
// 底图：开 = 矢量底图（OpenFreeMap，OSM 数据）+ 描出的路网；关 = **只画路网**（原来「示例路网」那个观感），
// 一个底图请求都不发。底图那一层挂掉也不影响路网（见 `MapLibreViewer.vue`：本地兜底样式建图）。
// 方向标记：开 = 画方向箭头；关 = 一支都不画（图例同步写「已隐藏方向标记」）。
const settingsOpen = ref(false);
// ---- 弹出层（线路图切换器 / 设置）的关闭规则 ----
// ⚠️ 2026-10-17 修 bug：原来靠 `@mouseleave` 收起，而菜单与按钮之间有 4px 空隙 ——
//    鼠标一往下移就离开 wrapper，菜单先收起、指针根本到不了里面的开关（"老是点不着"）。
//    现在改成：点按钮开/关 + 点外部关闭 + Esc 关闭，菜单不再跟着鼠标走。
const packRoot = ref(null);
const settingsRoot = ref(null);
function onDocPointerDown(e) {
    const t = e.target;
    if (packRoot.value && !packRoot.value.contains(t))
        packOpen.value = false;
    if (settingsRoot.value && !settingsRoot.value.contains(t))
        settingsOpen.value = false;
}
function onDocKeydown(e) {
    if (e.key === 'Escape') {
        packOpen.value = false;
        settingsOpen.value = false;
    }
}
onMounted(() => {
    document.addEventListener('pointerdown', onDocPointerDown);
    document.addEventListener('keydown', onDocKeydown);
});
onBeforeUnmount(() => {
    document.removeEventListener('pointerdown', onDocPointerDown);
    document.removeEventListener('keydown', onDocKeydown);
});
const __VLS_defaults = { ts: '', sourceMode: null, title: '', subtitle: '' };
void __VLS_defaults;
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
__VLS_withDotValue(packList, {});
// @ts-ignore
__VLS_withDotValue(packOpen, {});
// @ts-ignore
__VLS_withDotValue(packKey, {});
// @ts-ignore
__VLS_withDotValue(modeChip, {});
// @ts-ignore
__VLS_withDotValue(settingsOpen, {});
// @ts-ignore
__VLS_withDotValue(basemapEnabled, {});
// @ts-ignore
__VLS_withDotValue(directionsVisible, {});
// @ts-ignore
__VLS_withDotValue(showHead, {});
// @ts-ignore
__VLS_withDotValue(TD, {});
void {};
/** @type {__VLS_StyleScopedClasses['net-switch-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['net-switch-item']} */ ;
/** @type {__VLS_StyleScopedClasses['net-switch-item']} */ ;
/** @type {__VLS_StyleScopedClasses['net-switch-item']} */ ;
/** @type {__VLS_StyleScopedClasses['on']} */ ;
/** @type {__VLS_StyleScopedClasses['net-switch-name']} */ ;
/** @type {__VLS_StyleScopedClasses['td-settings-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['td-settings-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['on']} */ ;
/** @type {__VLS_StyleScopedClasses['td-switch']} */ ;
/** @type {__VLS_StyleScopedClasses['on']} */ ;
/** @type {__VLS_StyleScopedClasses['td-switch']} */ ;
/** @type {__VLS_StyleScopedClasses['on']} */ ;
/** @type {__VLS_StyleScopedClasses['td-switch-knob']} */ ;
/** @type {__VLS_StyleScopedClasses['td-mode-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['td-mode-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['warn']} */ ;
/** @type {__VLS_StyleScopedClasses['td-mode-prefix']} */ ;
/** @type {__VLS_StyleScopedClasses['td-main']} */ ;
/** @type {__VLS_StyleScopedClasses['net-switch-menu']} */ ;
/** @type {__VLS_StyleScopedClasses['td-settings-menu']} */ ;
/** @type {__VLS_StyleScopedClasses['net-switch-label']} */ ;
/** @type {__VLS_StyleScopedClasses['net-switch-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['td-settings-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['net-switch-menu']} */ ;
/** @type {__VLS_StyleScopedClasses['td-settings-menu']} */ ;
/** @type {__VLS_StyleScopedClasses['td-settings-menu']} */ ;
/** @type {__VLS_StyleScopedClasses['td-set-note']} */ ;
(TD.value.brand);
(TD.value.brand);
(TD.value.brand);
(TD.value.brand);
(TD.value.brand);
(TD.value.brand);
// @ts-ignore
[TD, TD, TD, TD, TD, TD,];
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-page" },
});
/** @type {__VLS_StyleScopedClasses['td-page']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
    ...{ class: "td-top" },
});
/** @type {__VLS_StyleScopedClasses['td-top']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-brand" },
});
/** @type {__VLS_StyleScopedClasses['td-brand']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-logo" },
});
/** @type {__VLS_StyleScopedClasses['td-logo']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-brand-sub" },
});
/** @type {__VLS_StyleScopedClasses['td-brand-sub']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.nav, __VLS_intrinsics.nav)({
    ...{ class: "td-tabs" },
});
/** @type {__VLS_StyleScopedClasses['td-tabs']} */ ;
const __VLS_0 = __VLS_tryAsConstant((__VLS_unwrap(APP_TABS, {})));
for (const [t] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
    let __VLS_1;
    /** @ts-ignore @type { | typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
    RouterLink;
    // @ts-ignore
    const __VLS_2 = __VLS_asFunctionalComponent1(__VLS_1, new __VLS_1({
        // @ts-ignore
        key: (t.key), ...{ class: "td-tab" }, ...{ class: ({ on: t.key === __VLS_ctx.active }) }, to: (t.route),
    }));
    const __VLS_3 = __VLS_2({
        key: (t.key),
        ...{ class: "td-tab" },
        ...{ class: ({ on: t.key === __VLS_ctx.active }) },
        to: (t.route),
    }, ...__VLS_functionalComponentArgsRest(__VLS_2));
    /** @type {__VLS_StyleScopedClasses['td-tab']} */ ;
    /** @type {__VLS_StyleScopedClasses['on']} */ ;
    const { default: __VLS_6 } = __VLS_nonNull(__VLS_4.slots);
    (t.name);
    // @ts-ignore
    [APP_TABS, active,];
    var __VLS_4;
    // @ts-ignore
    [];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-top-right" },
});
/** @type {__VLS_StyleScopedClasses['td-top-right']} */ ;
if (packList.value.length > 1) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ref: "packRoot",
        ...{ class: "net-switch" },
    });
    /** @type {__VLS_StyleScopedClasses['net-switch']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                if (!(packList.value.length > 1))
                    throw 0;
                return (packOpen.value = !packOpen.value);
                // @ts-ignore
                [packList, packOpen, packOpen,];
            } },
        type: "button",
        ...{ class: "net-switch-btn" },
        'aria-expanded': (packOpen.value),
        'aria-haspopup': "listbox",
    });
    /** @type {__VLS_StyleScopedClasses['net-switch-btn']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "net-switch-label" },
    });
    /** @type {__VLS_StyleScopedClasses['net-switch-label']} */ ;
    (packList.value.find((p) => p.key === packKey.value)?.name ?? __VLS_unwrap(stationName, {}));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "net-switch-caret" },
    });
    /** @type {__VLS_StyleScopedClasses['net-switch-caret']} */ ;
    if (packOpen.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "net-switch-menu" },
            role: "listbox",
            'aria-label': "切换线路图",
        });
        /** @type {__VLS_StyleScopedClasses['net-switch-menu']} */ ;
        const __VLS_7 = __VLS_tryAsConstant((packList.value));
        for (const [p] of __VLS_vFor(__VLS_nonNull(__VLS_7))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                ...{ onClick: // @ts-ignore
                    (...[$event]) => {
                        void $event;
                        if (!(packList.value.length > 1))
                            throw 0;
                        if (!(packOpen.value))
                            throw 0;
                        return (choosePack(p.key));
                        // @ts-ignore
                        [packList, packList, packOpen, packOpen, packKey, stationName,];
                    } },
                key: (p.key),
                type: "button",
                ...{ class: "net-switch-item" },
                ...{ class: ({ on: p.key === packKey.value }) },
                role: "option",
                'aria-selected': (p.key === packKey.value),
            });
            /** @type {__VLS_StyleScopedClasses['net-switch-item']} */ ;
            /** @type {__VLS_StyleScopedClasses['on']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "net-switch-name" },
            });
            /** @type {__VLS_StyleScopedClasses['net-switch-name']} */ ;
            (p.name);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "net-switch-note" },
            });
            /** @type {__VLS_StyleScopedClasses['net-switch-note']} */ ;
            (p.note);
            // @ts-ignore
            [packKey, packKey,];
        }
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-chip" },
});
/** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
(__VLS_unwrap(stationName, {}));
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-mode-chip" },
    ...{ class: ({ warn: modeChip.value.warn }) },
    title: (modeChip.value.note),
    'aria-label': (`运行模式：${modeChip.value.label}。${modeChip.value.note}`),
});
/** @type {__VLS_StyleScopedClasses['td-mode-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['warn']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-mode-prefix" },
});
/** @type {__VLS_StyleScopedClasses['td-mode-prefix']} */ ;
(modeChip.value.label);
if (__VLS_ctx.sourceMode !== null && __VLS_ctx.sourceMode !== undefined) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-seg" },
        role: "group",
        'aria-label': "数据源视图",
    });
    /** @type {__VLS_StyleScopedClasses['td-seg']} */ ;
    const __VLS_8 = __VLS_tryAsConstant((__VLS_unwrap(SOURCE_ITEMS, {})));
    for (const [s] of __VLS_vFor(__VLS_nonNull(__VLS_8))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ onClick: // @ts-ignore
                (...[$event]) => {
                    void $event;
                    if (!(__VLS_ctx.sourceMode !== null && __VLS_ctx.sourceMode !== undefined))
                        throw 0;
                    return (__VLS_unwrap(emit, {})('update:sourceMode', s.key));
                    // @ts-ignore
                    [stationName, modeChip, modeChip, modeChip, modeChip, modeChip, sourceMode, sourceMode, SOURCE_ITEMS, emit,];
                } },
            key: (s.key),
            ...{ class: "td-seg-item" },
            ...{ class: ({ on: s.key === __VLS_ctx.sourceMode }) },
            'aria-pressed': (s.key === __VLS_ctx.sourceMode),
            role: "button",
        });
        /** @type {__VLS_StyleScopedClasses['td-seg-item']} */ ;
        /** @type {__VLS_StyleScopedClasses['on']} */ ;
        (s.name);
        // @ts-ignore
        [sourceMode, sourceMode,];
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-mono" },
    ...{ style: {} },
});
/** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
(__VLS_ctx.ts ? __VLS_unwrap(formatStamp, {})(__VLS_ctx.ts) : '—');
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ref: "settingsRoot",
    ...{ class: "td-settings" },
});
/** @type {__VLS_StyleScopedClasses['td-settings']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: // @ts-ignore
        (...[$event]) => {
            void $event;
            return (settingsOpen.value = !settingsOpen.value);
            // @ts-ignore
            [ts, ts, formatStamp, settingsOpen, settingsOpen,];
        } },
    type: "button",
    ...{ class: "td-settings-btn" },
    ...{ class: ({ on: settingsOpen.value }) },
    'aria-expanded': (settingsOpen.value),
    'aria-haspopup': "dialog",
});
/** @type {__VLS_StyleScopedClasses['td-settings-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['on']} */ ;
if (settingsOpen.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-settings-menu" },
        role: "dialog",
        'aria-label': "设置",
    });
    /** @type {__VLS_StyleScopedClasses['td-settings-menu']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-set-row" },
    });
    /** @type {__VLS_StyleScopedClasses['td-set-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-set-main" },
    });
    /** @type {__VLS_StyleScopedClasses['td-set-main']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-set-name" },
    });
    /** @type {__VLS_StyleScopedClasses['td-set-name']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-set-note" },
    });
    /** @type {__VLS_StyleScopedClasses['td-set-note']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.br)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                __VLS_withDotValue(basemapEnabled, {});
                if (!(settingsOpen.value))
                    throw 0;
                return (__VLS_unwrap(setBasemapEnabled, {})(!basemapEnabled.value));
                // @ts-ignore
                [settingsOpen, settingsOpen, settingsOpen, setBasemapEnabled, basemapEnabled,];
            } },
        type: "button",
        ...{ class: "td-switch" },
        ...{ class: ({ on: basemapEnabled.value }) },
        role: "switch",
        'aria-checked': (basemapEnabled.value),
        'aria-label': "矢量底图开关",
    });
    /** @type {__VLS_StyleScopedClasses['td-switch']} */ ;
    /** @type {__VLS_StyleScopedClasses['on']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
        ...{ class: "td-switch-knob" },
    });
    /** @type {__VLS_StyleScopedClasses['td-switch-knob']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-set-row td-set-row-gap" },
    });
    /** @type {__VLS_StyleScopedClasses['td-set-row']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-set-row-gap']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-set-main" },
    });
    /** @type {__VLS_StyleScopedClasses['td-set-main']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-set-name" },
    });
    /** @type {__VLS_StyleScopedClasses['td-set-name']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-set-note" },
    });
    /** @type {__VLS_StyleScopedClasses['td-set-note']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.br)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                __VLS_withDotValue(directionsVisible, {});
                if (!(settingsOpen.value))
                    throw 0;
                return (__VLS_unwrap(setDirectionsVisible, {})(!directionsVisible.value));
                // @ts-ignore
                [basemapEnabled, basemapEnabled, setDirectionsVisible, directionsVisible,];
            } },
        type: "button",
        ...{ class: "td-switch" },
        ...{ class: ({ on: directionsVisible.value }) },
        role: "switch",
        'aria-checked': (directionsVisible.value),
        'aria-label': "方向标记开关",
    });
    /** @type {__VLS_StyleScopedClasses['td-switch']} */ ;
    /** @type {__VLS_StyleScopedClasses['on']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
        ...{ class: "td-switch-knob" },
    });
    /** @type {__VLS_StyleScopedClasses['td-switch-knob']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-set-foot" },
    });
    /** @type {__VLS_StyleScopedClasses['td-set-foot']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-badge-demo" },
});
/** @type {__VLS_StyleScopedClasses['td-badge-demo']} */ ;
(__VLS_unwrap(DEMO_BADGE, {}));
if (showHead.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-head" },
    });
    /** @type {__VLS_StyleScopedClasses['td-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    if (__VLS_ctx.title) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "td-head-title" },
        });
        /** @type {__VLS_StyleScopedClasses['td-head-title']} */ ;
        (__VLS_ctx.title);
    }
    if (__VLS_ctx.subtitle) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "td-head-sub" },
        });
        /** @type {__VLS_StyleScopedClasses['td-head-sub']} */ ;
        (__VLS_ctx.subtitle);
    }
    var __VLS_9 = {};
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "td-head-right" },
    });
    /** @type {__VLS_StyleScopedClasses['td-head-right']} */ ;
    var __VLS_11 = {};
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-main" },
});
/** @type {__VLS_StyleScopedClasses['td-main']} */ ;
var __VLS_13 = {};
__VLS_asFunctionalElement1(__VLS_intrinsics.footer, __VLS_intrinsics.footer)({
    ...{ class: "td-foot" },
});
/** @type {__VLS_StyleScopedClasses['td-foot']} */ ;
var __VLS_15 = {};
var __VLS_10 = __VLS_9, __VLS_12 = __VLS_11, __VLS_14 = __VLS_13, __VLS_16 = __VLS_15;
// @ts-ignore
[directionsVisible, directionsVisible, DEMO_BADGE, showHead, title, title, subtitle, subtitle,];
const __VLS_base = (await import('vue')).defineComponent({
    __typeEmits: {},
    __defaults: __VLS_defaults,
    __typeProps: {},
});
const __VLS_export = {};
export default {};
