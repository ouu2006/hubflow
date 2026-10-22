/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 监控墙单格:一帧抽帧画面 + SVG 检测框覆盖层 + 越线计数线 + 底部口径行。
// 深色例外仅限本格(画面区);框色走 CLASS_COLORS(与等级四级色解耦),线色走 TD_VIDEO.brand。
// 越线计数是感知服务当前**未提供**的字段 → 格内如实标「越线计数:未提供」,不画推算值。
import { computed } from 'vue';
import { perceptionFrameUrl } from '../../../api/perception';
import { TD_VIDEO } from '../../../shared/theme';
import { COUNT_LINE_POS, classColorOf, classCountsOf, frameAt, trackCountOf, vehicleKeyOf } from './channels';
const { defineProps, defineEmits, } = {};
const props = defineProps();
const emit = defineEmits();
const meta = computed(() => props.ch.meta);
const classNames = computed(() => meta.value?.class_names ?? {});
const dets = computed(() => frameAt(props.ch.det, props.index));
/**
 * 格内状态。⚠️「未接入视频源」必须与「未导出」分开(Issue IKLX5Y):
 * 前者是"这条路还没接视频",后者是"有样本视频、服务端没处理"。合成一句会误导。
 */
const status = computed(() => {
    if (!props.ch.def.hasVideo)
        return '未接入视频源';
    if (!meta.value)
        return '未导出';
    if (props.ch.detFailed)
        return '检测读取失败';
    return props.selected ? '检测中' : '就绪';
});
/** 没有视频源的通道:格内显示留空窗占位(不报错、不白屏) */
const noSource = computed(() => !props.ch.def.hasVideo);
const url = computed(() => meta.value && !noSource.value ? perceptionFrameUrl(props.ch.def.source, props.index + 1) : null);
// 画面区尺寸取源分辨率(缺 meta 时给占位尺寸);模板只引用这两个 computed,避免在模板里对 meta 做空值收窄
const vbW = computed(() => meta.value?.width ?? 960);
const vbH = computed(() => meta.value?.height ?? 600);
const mediaStyle = computed(() => ({ aspectRatio: `${vbW.value} / ${vbH.value}` }));
const viewBox = computed(() => `0 0 ${vbW.value} ${vbH.value}`);
const lineY = computed(() => Math.round(vbH.value * COUNT_LINE_POS));
// 归一化坐标(0~1)→ 百分比定位;框顶标签 = 类别 · 置信度(两位小数,设计稿去前导零)
const boxes = computed(() => {
    const list = dets.value;
    if (!list)
        return [];
    return list.map((d) => {
        const [x1, y1, x2, y2, cls, conf] = d;
        const name = classNames.value[String(cls)] ?? `类${cls}`;
        const key = vehicleKeyOf(cls, name);
        return {
            x: x1 * 100,
            y: y1 * 100,
            w: (x2 - x1) * 100,
            h: (y2 - y1) * 100,
            color: classColorOf(cls, name),
            label: `${key ?? name} ${conf.toFixed(2).replace(/^0/, '')}`,
        };
    });
});
const trackCount = computed(() => trackCountOf(dets.value));
const classLine = computed(() => {
    const rows = classCountsOf(dets.value, classNames.value);
    return rows.length > 0 ? rows.map((r) => `${r.short} ${r.count}`).join(' · ') : '本帧无检出';
});
const scaleText = computed(() => (props.scale === null ? '—' : `${props.scale.toFixed(2)}×`));
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
__VLS_withDotValue(noSource, {});
// @ts-ignore
__VLS_withDotValue(meta, {});
// @ts-ignore
__VLS_withDotValue(url, {});
// @ts-ignore
__VLS_withDotValue(TD_VIDEO, {});
void {};
/** @type {__VLS_StyleScopedClasses['cell']} */ ;
/** @type {__VLS_StyleScopedClasses['ct-state']} */ ;
/** @type {__VLS_StyleScopedClasses['ct-state']} */ ;
/** @type {__VLS_StyleScopedClasses['ct-state']} */ ;
/** @type {__VLS_StyleScopedClasses['cell-media']} */ ;
/** @type {__VLS_StyleScopedClasses['cell-top']} */ ;
/** @type {__VLS_StyleScopedClasses['cell-foot']} */ ;
/** @type {__VLS_StyleScopedClasses['cell-media']} */ ;
/** @type {__VLS_StyleScopedClasses['ct-name']} */ ;
/** @type {__VLS_StyleScopedClasses['cf-cnt']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ onClick: // @ts-ignore
        (...[$event]) => {
            void $event;
            return (__VLS_unwrap(emit, {})('select'));
            // @ts-ignore
            [emit,];
        } },
    ...{ class: "cell" },
    ...{ class: ({ on: __VLS_ctx.selected }) },
});
/** @type {__VLS_StyleScopedClasses['cell']} */ ;
/** @type {__VLS_StyleScopedClasses['on']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "cell-top" },
});
/** @type {__VLS_StyleScopedClasses['cell-top']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "ct-name" },
});
/** @type {__VLS_StyleScopedClasses['ct-name']} */ ;
(__VLS_ctx.ch.def.cid);
(__VLS_ctx.ch.def.source);
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "ct-state" },
    ...{ class: ({ live: __VLS_ctx.selected && !noSource.value && meta.value !== null && !__VLS_ctx.ch.detFailed, err: __VLS_ctx.ch.detFailed, off: meta.value === null || noSource.value }) },
});
/** @type {__VLS_StyleScopedClasses['ct-state']} */ ;
/** @type {__VLS_StyleScopedClasses['live']} */ ;
/** @type {__VLS_StyleScopedClasses['err']} */ ;
/** @type {__VLS_StyleScopedClasses['off']} */ ;
(__VLS_unwrap(status, {}));
if (noSource.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell-media cell-nosource" },
        ...{ style: (__VLS_unwrap(mediaStyle, {})) },
    });
    /** @type {__VLS_StyleScopedClasses['cell-media']} */ ;
    /** @type {__VLS_StyleScopedClasses['cell-nosource']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "ns-l1" },
    });
    /** @type {__VLS_StyleScopedClasses['ns-l1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "ns-l2" },
    });
    /** @type {__VLS_StyleScopedClasses['ns-l2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell-foot" },
    });
    /** @type {__VLS_StyleScopedClasses['cell-foot']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "cf-classes" },
    });
    /** @type {__VLS_StyleScopedClasses['cf-classes']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "cf-cnt" },
    });
    /** @type {__VLS_StyleScopedClasses['cf-cnt']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell-sub" },
    });
    /** @type {__VLS_StyleScopedClasses['cell-sub']} */ ;
    (__VLS_ctx.ch.def.cid);
    (__VLS_ctx.ch.def.source);
}
else if (meta.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell-media" },
        ...{ style: (__VLS_unwrap(mediaStyle, {})) },
    });
    /** @type {__VLS_StyleScopedClasses['cell-media']} */ ;
    if (url.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.img)({
            ...{ class: "cm-img" },
            src: (url.value),
            alt: (`${__VLS_ctx.ch.def.cid} 抽帧画面`),
        });
        /** @type {__VLS_StyleScopedClasses['cm-img']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.svg, __VLS_intrinsics.svg)({
        ...{ class: "cm-svg" },
        viewBox: (__VLS_unwrap(viewBox, {})),
        preserveAspectRatio: "xMidYMid meet",
    });
    /** @type {__VLS_StyleScopedClasses['cm-svg']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.line)({
        x1: "0",
        y1: (__VLS_unwrap(lineY, {})),
        x2: (__VLS_unwrap(vbW, {})),
        y2: (__VLS_unwrap(lineY, {})),
        stroke: (TD_VIDEO.value.brand),
        'stroke-width': "1.5",
        'stroke-dasharray': "9 7",
        'vector-effect': "non-scaling-stroke",
    });
    const __VLS_0 = __VLS_tryAsConstant((__VLS_unwrap(boxes, {})));
    for (const [b, i] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.rect)({
            key: (i),
            x: ((b.x / 100) * __VLS_unwrap(vbW, {})),
            y: ((b.y / 100) * __VLS_unwrap(vbH, {})),
            width: ((b.w / 100) * __VLS_unwrap(vbW, {})),
            height: ((b.h / 100) * __VLS_unwrap(vbH, {})),
            stroke: (b.color),
            fill: "none",
            'stroke-width': "1.6",
            'vector-effect': "non-scaling-stroke",
        });
        // @ts-ignore
        [selected, selected, ch, ch, ch, ch, ch, ch, ch, noSource, noSource, noSource, meta, meta, meta, status, mediaStyle, mediaStyle, url, url, viewBox, lineY, lineY, vbW, vbW, vbW, TD_VIDEO, boxes, vbH, vbH,];
    }
    const __VLS_1 = __VLS_tryAsConstant((__VLS_unwrap(boxes, {})));
    for (const [b, i] of __VLS_vFor(__VLS_nonNull(__VLS_1))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            key: (`l${i}`),
            ...{ class: "cm-label" },
            ...{ style: ({ left: `${b.x}%`, top: `${b.y}%`, color: b.color }) },
        });
        /** @type {__VLS_StyleScopedClasses['cm-label']} */ ;
        (b.label);
        // @ts-ignore
        [boxes,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell-foot" },
    });
    /** @type {__VLS_StyleScopedClasses['cell-foot']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "cf-classes" },
    });
    /** @type {__VLS_StyleScopedClasses['cf-classes']} */ ;
    (__VLS_ctx.ch.detFailed ? '检测读取失败' : __VLS_unwrap(classLine, {}));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "cf-cnt" },
    });
    /** @type {__VLS_StyleScopedClasses['cf-cnt']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell-sub" },
    });
    /** @type {__VLS_StyleScopedClasses['cell-sub']} */ ;
    if (__VLS_ctx.ch.detFailed) {
    }
    else {
        (__VLS_ctx.ch.def.cid);
        (__VLS_ctx.ch.def.source);
        (__VLS_unwrap(scaleText, {}));
        (__VLS_ctx.index + 1);
        (__VLS_unwrap(trackCount, {}));
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell-media cell-empty" },
        ...{ style: (__VLS_unwrap(mediaStyle, {})) },
    });
    /** @type {__VLS_StyleScopedClasses['cell-media']} */ ;
    /** @type {__VLS_StyleScopedClasses['cell-empty']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell-foot" },
    });
    /** @type {__VLS_StyleScopedClasses['cell-foot']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "cf-classes" },
    });
    /** @type {__VLS_StyleScopedClasses['cf-classes']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "cf-cnt" },
    });
    /** @type {__VLS_StyleScopedClasses['cf-cnt']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell-sub" },
    });
    /** @type {__VLS_StyleScopedClasses['cell-sub']} */ ;
    (__VLS_ctx.ch.def.cid);
    (__VLS_ctx.ch.def.source);
}
// @ts-ignore
[ch, ch, ch, ch, ch, ch, mediaStyle, classLine, scaleText, index, trackCount,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
