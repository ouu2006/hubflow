/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 效果对比报表(设计稿 03 底部「效果对比 · 场景切换 (A/B/C)」)。
// 口径(硬性口径 1):三组对照全部是**仿真对照**,不得称实测;数据 is_simulated = true;
//   ② ③ 的差 = 本项目核心机制的举证口("不给每个人此刻最快的那条路",README §9.2)。
// 数据来源分两层,页面分开标注:
//   · 接口层 `GET /api/traffic/report/compare` —— 一期没有「同输入多跑对照」的报表产物,
//     响应 rows 如实为空 + note;页面把接口 note 显式展示(不静默当没有);
//   · 下方 A/B/C 三组与处置前后对比来自 `shared/demoDecision.ts` 的**前端演示脚本**,
//     在接口无报表数据时兜底展示,常驻「仿真对照 · 前端演示脚本」标注(不冒充接口数据)。
import { computed, onMounted, ref } from 'vue';
import { ACK_COMPARISON, EFFECT_SCENARIOS } from '../../../shared/demoDecision';
import { getTrafficReportCompare } from '../../../api/traffic';
import { USE_MOCK } from '../../../shared/env';
const picked = ref(EFFECT_SCENARIOS[0]?.key ?? 'peak');
const scenario = computed(() => EFFECT_SCENARIOS.find((s) => s.key === picked.value) ?? EFFECT_SCENARIOS[0]);
/** 接口报表(rows 为空 = 接口层无报表产物,页面如实标注) */
const report = ref(null);
const reportError = ref('');
const reportRows = computed(() => report.value?.rows ?? []);
const reportColumns = computed(() => Object.keys(reportRows.value[0] ?? {}));
onMounted(async () => {
    // mock 模式没有 /report/compare(实测 404):不请求、不常驻告警,A/B/C 仍按"前端演示脚本"展示
    if (USE_MOCK)
        return;
    try {
        report.value = await getTrafficReportCompare();
    }
    catch (e) {
        reportError.value = `效果对比报表接口未取到:${e instanceof Error ? e.message : String(e)}`;
    }
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
void __VLS_ctx, __VLS_components, __VLS_intrinsics, __VLS_directives;
// @ts-ignore
__VLS_withDotValue(picked, {});
// @ts-ignore
__VLS_withDotValue(USE_MOCK, {});
// @ts-ignore
__VLS_withDotValue(reportError, {});
// @ts-ignore
__VLS_withDotValue(report, {});
// @ts-ignore
__VLS_withDotValue(reportRows, {});
// @ts-ignore
__VLS_withDotValue(scenario, {});
// @ts-ignore
__VLS_withDotValue(ACK_COMPARISON, {});
void {};
/** @type {__VLS_StyleScopedClasses['src']} */ ;
/** @type {__VLS_StyleScopedClasses['tbl-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['tbl-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['td-table']} */ ;
/** @type {__VLS_StyleScopedClasses['seg']} */ ;
/** @type {__VLS_StyleScopedClasses['tbl-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['tbl-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['td-table']} */ ;
/** @type {__VLS_StyleScopedClasses['td-table']} */ ;
/** @type {__VLS_StyleScopedClasses['td-table']} */ ;
/** @type {__VLS_StyleScopedClasses['sub']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
    ...{ class: "td-card" },
});
/** @type {__VLS_StyleScopedClasses['td-card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-head" },
});
/** @type {__VLS_StyleScopedClasses['td-card-head']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "td-seg seg" },
});
/** @type {__VLS_StyleScopedClasses['td-seg']} */ ;
/** @type {__VLS_StyleScopedClasses['seg']} */ ;
const __VLS_0 = __VLS_tryAsConstant((__VLS_unwrap(EFFECT_SCENARIOS, {})));
for (const [s] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                return (picked.value = s.key);
                // @ts-ignore
                [EFFECT_SCENARIOS, picked,];
            } },
        key: (s.key),
        ...{ class: "td-seg-item" },
        ...{ class: ({ on: s.key === picked.value }) },
        role: "button",
        'aria-pressed': (s.key === picked.value),
    });
    /** @type {__VLS_StyleScopedClasses['td-seg-item']} */ ;
    /** @type {__VLS_StyleScopedClasses['on']} */ ;
    (s.name);
    // @ts-ignore
    [picked, picked,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "td-card-body" },
});
/** @type {__VLS_StyleScopedClasses['td-card-body']} */ ;
if (USE_MOCK.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "src" },
    });
    /** @type {__VLS_StyleScopedClasses['src']} */ ;
}
else if (reportError.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "src warn" },
    });
    /** @type {__VLS_StyleScopedClasses['src']} */ ;
    /** @type {__VLS_StyleScopedClasses['warn']} */ ;
    (reportError.value);
}
else if (report.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "src" },
    });
    /** @type {__VLS_StyleScopedClasses['src']} */ ;
    (reportRows.value.length);
    if (report.value.note) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "src warn" },
        });
        /** @type {__VLS_StyleScopedClasses['src']} */ ;
        /** @type {__VLS_StyleScopedClasses['warn']} */ ;
        (report.value.note);
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "tbl-wrap" },
    });
    /** @type {__VLS_StyleScopedClasses['tbl-wrap']} */ ;
    if (reportRows.value.length > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.table, __VLS_intrinsics.table)({
            ...{ class: "td-table" },
        });
        /** @type {__VLS_StyleScopedClasses['td-table']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.thead, __VLS_intrinsics.thead)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({});
        const __VLS_1 = __VLS_tryAsConstant((__VLS_unwrap(reportColumns, {})));
        for (const [key] of __VLS_vFor(__VLS_nonNull(__VLS_1))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
                key: (key),
            });
            (key);
            // @ts-ignore
            [USE_MOCK, reportError, reportError, report, report, report, reportRows, reportRows, reportColumns,];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.tbody, __VLS_intrinsics.tbody)({});
        const __VLS_2 = __VLS_tryAsConstant((reportRows.value));
        for (const [row, index] of __VLS_vFor(__VLS_nonNull(__VLS_2))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({
                key: (index),
            });
            const __VLS_3 = __VLS_tryAsConstant((__VLS_unwrap(reportColumns, {})));
            for (const [key] of __VLS_vFor(__VLS_nonNull(__VLS_3))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    key: (key),
                });
                (row[key]);
                // @ts-ignore
                [reportRows, reportColumns,];
            }
            // @ts-ignore
            [];
        }
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "src" },
    });
    /** @type {__VLS_StyleScopedClasses['src']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "src" },
});
/** @type {__VLS_StyleScopedClasses['src']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "src" },
});
/** @type {__VLS_StyleScopedClasses['src']} */ ;
(scenario.value.window);
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
__VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
    ...{ class: "num" },
});
/** @type {__VLS_StyleScopedClasses['num']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
    ...{ class: "num" },
});
/** @type {__VLS_StyleScopedClasses['num']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
    ...{ class: "num hl" },
});
/** @type {__VLS_StyleScopedClasses['num']} */ ;
/** @type {__VLS_StyleScopedClasses['hl']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.tbody, __VLS_intrinsics.tbody)({});
const __VLS_4 = __VLS_tryAsConstant((scenario.value.metrics));
for (const [m] of __VLS_vFor(__VLS_nonNull(__VLS_4))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({
        key: (m.name),
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
    (m.name);
    if (m.unit) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "unit" },
        });
        /** @type {__VLS_StyleScopedClasses['unit']} */ ;
        (m.unit);
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
        ...{ class: "num" },
    });
    /** @type {__VLS_StyleScopedClasses['num']} */ ;
    (m.no_guide);
    __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
        ...{ class: "num" },
    });
    /** @type {__VLS_StyleScopedClasses['num']} */ ;
    (m.fastest);
    __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
        ...{ class: "num hl" },
    });
    /** @type {__VLS_StyleScopedClasses['num']} */ ;
    /** @type {__VLS_StyleScopedClasses['hl']} */ ;
    (m.cooperative);
    // @ts-ignore
    [scenario, scenario,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sub" },
});
/** @type {__VLS_StyleScopedClasses['sub']} */ ;
(ACK_COMPARISON.value.window);
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
__VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
    ...{ class: "num" },
});
/** @type {__VLS_StyleScopedClasses['num']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
    ...{ class: "num hl" },
});
/** @type {__VLS_StyleScopedClasses['num']} */ ;
/** @type {__VLS_StyleScopedClasses['hl']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.tbody, __VLS_intrinsics.tbody)({});
const __VLS_5 = __VLS_tryAsConstant((ACK_COMPARISON.value.rows));
for (const [r] of __VLS_vFor(__VLS_nonNull(__VLS_5))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({
        key: (r.name),
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
    (r.name);
    if (r.unit) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "unit" },
        });
        /** @type {__VLS_StyleScopedClasses['unit']} */ ;
        (r.unit);
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
        ...{ class: "num" },
    });
    /** @type {__VLS_StyleScopedClasses['num']} */ ;
    (r.before);
    __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
        ...{ class: "num hl" },
    });
    /** @type {__VLS_StyleScopedClasses['num']} */ ;
    /** @type {__VLS_StyleScopedClasses['hl']} */ ;
    (r.after);
    // @ts-ignore
    [ACK_COMPARISON, ACK_COMPARISON,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "note" },
});
/** @type {__VLS_StyleScopedClasses['note']} */ ;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
