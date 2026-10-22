/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 大屏右栏 · 关联摄像头（Issue IKMS18 大屏监控平台化）。
//
// 点选路段 → 该段登记摄像头的**感知服务真实帧预览**：
//   · 有视频源 + 感知服务已导出该通道：按 `meta.total_frames` 定时抽帧
//     （`<img>` 拉 `/perception-api/streams/{source}/frames/{n}.jpg`，与感知页同一路径），
//     常驻「样本视频回放 · 非本站现场」角标；可播放 / 暂停；
//   · 有视频源、服务在、但该通道没导出：「未导出（样本视频未处理）」；
//   · 无视频源：「未接入视频源 · 本期留空」；
//   · 感知服务整体不可用：可读错误 + 重试（8 s 自动重试），**绝不伪造画面**；
//   · 该段 0 路摄像头 / 登记摄像头均无视频源：按业主口径显示「演示复用样本视频」
//     （从 road2/track1 确定性复用，明确标注非真实摄像头，详见 IKNAUI）。
//
// 唯一真值来源 = 站点包 `channels`（由 work/perception/mapping/camera-segments.json 生成），
// 与感知页 / 地图摄像头图钉同一个 `source` / `hasVideo` 键，不另造第二份。
//
// 2026-10-18 口径（IKNBT2）：**N 段 = N 摄像头 = N 视频（演示）**——
// 源台账 0 路不再写「无独立摄像头」，而是「演示摄像头 · 复用样本视频」；有登记摄像头段保持
// 源台账身份，但同样说明"一期每路都有视频（mock 复用）"。不伪造真实摄像头/登记表。
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { getPerceptionStreams, perceptionFrameUrl } from '../../../api/perception';
import { camerasOfSegment, demoCameraCount, perceptionHref } from '../../../shared/cameras';
const { defineProps, } = {};
const props = defineProps();
const streams = ref(null);
const loading = ref(false);
const error = ref('');
/** 帧级加载失败（抽帧 404 / 服务中途挂掉）：该路显示"帧不可用"，不保留破图 */
const frameFailed = ref({});
const playing = ref(true);
/** 播放时钟：每 500 ms 走 1 步，抽帧序号 = 时钟 × FRAME_STEP（对 total_frames 取模循环） */
const tick = ref(0);
const FRAME_STEP = 5;
const CLOCK_MS = 500;
const cameras = computed(() => camerasOfSegment(props.segmentId));
/** 一期演示口径的摄像头总数：N 段 = N 摄像头（Z=61 / GZ=433；与源台账分开说） */
const demoCameraTotal = computed(() => demoCameraCount());
const views = computed(() => cameras.value.map((camera) => ({
    cid: camera.cid,
    source: camera.source,
    name: camera.name,
    hasVideo: camera.hasVideo !== false,
    meta: streams.value?.find((item) => item.stream_id === camera.source) ?? null,
})));
const hasPlayable = computed(() => views.value.some((v) => v.hasVideo && v.meta !== null));
const videoCount = computed(() => views.value.filter((v) => v.hasVideo).length);
/** 该段是否有任何“有视频源”的登记摄像头；false 时（含 0 路）走演示复用视频 */
const hasAnyVideo = computed(() => cameras.value.some((c) => c.hasVideo !== false));
/** 登记了但无视频源的摄像头 cid 列表（用于说明“登记摄像头均无视频源”） */
const noVideoCids = computed(() => cameras.value.filter((c) => c.hasVideo === false).map((c) => c.cid).join(' / '));
// ---------- 全路段视频复用（Issue IKNAUI 业主口径：全部 61 段都要有视频显示）----------
//
// **对没有登记摄像头、或登记摄像头均无视频源的段启用**：从现有 2 路样本视频 road2 / track1 中
// 按 segment_id **确定性**挑一路（同一段永远同一路，不用随机），复用它真实的抽帧画面。
// 不新增 / 不伪造摄像头登记——感知页台账仍是登记表里的 6 路；这里只是「演示复用视频」。
const REUSE_SOURCES = ['road2', 'track1'];
function reuseSourceOf(segmentId) {
    let hash = 0;
    for (const ch of segmentId)
        hash = (hash * 31 + (ch.codePointAt(0) ?? 0)) >>> 0;
    return REUSE_SOURCES[hash % REUSE_SOURCES.length];
}
const reuseStream = computed(() => !hasAnyVideo.value ? reuseSourceOf(props.segmentId) : '');
const reuseMeta = computed(() => {
    if (!reuseStream.value)
        return null;
    return streams.value?.find((item) => item.stream_id === reuseStream.value) ?? null;
});
const reuseFrameFailed = computed(() => Boolean(reuseStream.value && frameFailed.value[`reuse:${reuseStream.value}`]));
const reuseFrameNo = computed(() => {
    const total = Math.max(1, reuseMeta.value?.total_frames ?? 1);
    return ((tick.value * FRAME_STEP) % total) + 1;
});
const hasAnyPlayable = computed(() => hasPlayable.value || reuseMeta.value !== null);
const playLabel = computed(() => (!hasAnyPlayable.value ? '—' : playing.value ? '暂停' : '播放'));
/** 第 1 帧起的抽帧序号（各通道帧数不同，各自取模） */
function frameOf(view) {
    const total = Math.max(1, view.meta?.total_frames ?? 1);
    return ((tick.value * FRAME_STEP) % total) + 1;
}
let clock = null;
let retryTimer = null;
function clearRetry() {
    if (retryTimer) {
        clearTimeout(retryTimer);
        retryTimer = null;
    }
}
function scheduleRetry() {
    if (retryTimer)
        return;
    retryTimer = setTimeout(() => {
        retryTimer = null;
        if (error.value)
            void loadStreams();
    }, 8000);
}
/** 帧加载失败：不回退到别的帧/假图，只如实标"帧不可用"并允许手动重试 */
function onFrameError(source) {
    frameFailed.value = { ...frameFailed.value, [source]: true };
}
function retryFrame(source) {
    const next = { ...frameFailed.value };
    delete next[source];
    frameFailed.value = next;
    tick.value += 1;
}
async function loadStreams() {
    if (loading.value)
        return;
    loading.value = true;
    error.value = '';
    try {
        const res = await getPerceptionStreams();
        streams.value = Array.isArray(res.streams) ? res.streams : [];
        clearRetry();
    }
    catch (e) {
        streams.value = null;
        error.value = `感知服务未连接 / 不可用：${e instanceof Error ? e.message : String(e)}`;
        // 服务错误总与卡片画面相关（有视频源→原视频；无视频源/0 路→演示复用视频），统一 8s 重试
        scheduleRetry();
    }
    finally {
        loading.value = false;
    }
}
onMounted(() => {
    clock = setInterval(() => {
        if (playing.value)
            tick.value += 1;
    }, CLOCK_MS);
    void loadStreams();
});
onUnmounted(() => {
    if (clock)
        clearInterval(clock);
    clearRetry();
});
// 切路段：帧序号归零（各通道帧数不同，避免沿用上一段的大序号）；帧失败标记也清掉
watch(() => props.segmentId, () => {
    tick.value = 0;
    frameFailed.value = {};
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
__VLS_withDotValue(cameras, {});
// @ts-ignore
__VLS_withDotValue(hasAnyVideo, {});
// @ts-ignore
__VLS_withDotValue(reuseMeta, {});
// @ts-ignore
__VLS_withDotValue(hasPlayable, {});
// @ts-ignore
__VLS_withDotValue(hasAnyPlayable, {});
// @ts-ignore
__VLS_withDotValue(playing, {});
// @ts-ignore
__VLS_withDotValue(error, {});
// @ts-ignore
__VLS_withDotValue(reuseFrameFailed, {});
// @ts-ignore
__VLS_withDotValue(loading, {});
// @ts-ignore
__VLS_withDotValue(streams, {});
// @ts-ignore
__VLS_withDotValue(frameFailed, {});
void {};
/** @type {__VLS_StyleScopedClasses['cam-media']} */ ;
/** @type {__VLS_StyleScopedClasses['cam-media']} */ ;
/** @type {__VLS_StyleScopedClasses['cam-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['cam-head']} */ ;
/** @type {__VLS_StyleScopedClasses['cam-media']} */ ;
/** @type {__VLS_StyleScopedClasses['cam-note']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
    ...{ class: "cam-card" },
});
/** @type {__VLS_StyleScopedClasses['cam-card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sec-head" },
});
/** @type {__VLS_StyleScopedClasses['sec-head']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "sub-tag" },
});
/** @type {__VLS_StyleScopedClasses['sub-tag']} */ ;
(cameras.value.length > 0
    ? `源台账 ${cameras.value.length} 路`
    : `演示摄像头 · 复用样本视频（按路段数 ${__VLS_unwrap(demoCameraTotal, {})} 路）`);
if (!hasAnyVideo.value && reuseMeta.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-chip warn" },
    });
    /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
    /** @type {__VLS_StyleScopedClasses['warn']} */ ;
}
else if (hasPlayable.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-chip warn" },
    });
    /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
    /** @type {__VLS_StyleScopedClasses['warn']} */ ;
}
if (hasAnyPlayable.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
        ...{ onClick: // @ts-ignore
            (...[$event]) => {
                void $event;
                if (!(hasAnyPlayable.value))
                    throw 0;
                return (playing.value = !playing.value);
                // @ts-ignore
                [cameras, cameras, demoCameraTotal, hasAnyVideo, reuseMeta, hasPlayable, hasAnyPlayable, playing, playing,];
            } },
        ...{ class: "cam-play" },
        role: "button",
        'aria-pressed': (playing.value),
    });
    /** @type {__VLS_StyleScopedClasses['cam-play']} */ ;
    (__VLS_unwrap(playLabel, {}));
}
if (!hasAnyVideo.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cam-row" },
    });
    /** @type {__VLS_StyleScopedClasses['cam-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cam-head" },
    });
    /** @type {__VLS_StyleScopedClasses['cam-head']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "cam-id td-mono" },
    });
    /** @type {__VLS_StyleScopedClasses['cam-id']} */ ;
    /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
    (cameras.value.length === 0 ? '演示摄像头' : `登记源台账 ${__VLS_unwrap(noVideoCids, {})}`);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "cam-name" },
    });
    /** @type {__VLS_StyleScopedClasses['cam-name']} */ ;
    (cameras.value.length === 0 ? '演示复用样本视频（本段演示画面 · mock 复用）' : '源台账无独立视频源 · 演示复用样本视频');
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "td-chip" },
        ...{ class: ({ ok: reuseMeta.value, err: Boolean(error.value) || reuseFrameFailed.value }) },
    });
    /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
    /** @type {__VLS_StyleScopedClasses['ok']} */ ;
    /** @type {__VLS_StyleScopedClasses['err']} */ ;
    (reuseFrameFailed.value
        ? '帧加载失败'
        : reuseMeta.value
            ? '演示复用'
            : error.value
                ? '服务不可用'
                : '未导出');
    if (reuseMeta.value && !error.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cam-media" },
        });
        /** @type {__VLS_StyleScopedClasses['cam-media']} */ ;
        if (!reuseFrameFailed.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.img)({
                ...{ onError: // @ts-ignore
                    (...[$event]) => {
                        void $event;
                        if (!(!hasAnyVideo.value))
                            throw 0;
                        if (!(reuseMeta.value && !error.value))
                            throw 0;
                        if (!(!reuseFrameFailed.value))
                            throw 0;
                        return (onFrameError(`reuse:${__VLS_unwrap(reuseStream, {})}`));
                        // @ts-ignore
                        [cameras, cameras, hasAnyVideo, reuseMeta, reuseMeta, reuseMeta, playing, playLabel, noVideoCids, error, error, error, reuseFrameFailed, reuseFrameFailed, reuseFrameFailed, reuseStream,];
                    } },
                ...{ class: "cam-img" },
                src: (__VLS_unwrap(perceptionFrameUrl, {})(__VLS_unwrap(reuseStream, {}), __VLS_unwrap(reuseFrameNo, {}))),
                alt: (`${__VLS_ctx.segmentId} 演示复用样本视频抽帧`),
                loading: "lazy",
            });
            /** @type {__VLS_StyleScopedClasses['cam-img']} */ ;
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cam-media cam-nosource" },
            });
            /** @type {__VLS_StyleScopedClasses['cam-media']} */ ;
            /** @type {__VLS_StyleScopedClasses['cam-nosource']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "ns-l1" },
            });
            /** @type {__VLS_StyleScopedClasses['ns-l1']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "ns-l2" },
            });
            /** @type {__VLS_StyleScopedClasses['ns-l2']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                ...{ onClick: // @ts-ignore
                    (...[$event]) => {
                        void $event;
                        if (!(!hasAnyVideo.value))
                            throw 0;
                        if (!(reuseMeta.value && !error.value))
                            throw 0;
                        if (!!(!reuseFrameFailed.value))
                            throw 0;
                        return (retryFrame(`reuse:${__VLS_unwrap(reuseStream, {})}`));
                        // @ts-ignore
                        [reuseStream, reuseStream, perceptionFrameUrl, reuseFrameNo, segmentId,];
                    } },
                ...{ class: "td-btn sm" },
                type: "button",
            });
            /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
            /** @type {__VLS_StyleScopedClasses['sm']} */ ;
        }
        if (!reuseFrameFailed.value) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "cam-badge" },
            });
            /** @type {__VLS_StyleScopedClasses['cam-badge']} */ ;
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cam-meta td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['cam-meta']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (__VLS_unwrap(reuseStream, {}));
        (reuseMeta.value.width);
        (reuseMeta.value.height);
        (reuseMeta.value.fps);
        (reuseMeta.value.total_frames);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "sep" },
        });
        /** @type {__VLS_StyleScopedClasses['sep']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
            ...{ class: "cam-link" },
            href: (__VLS_unwrap(perceptionHref, {})(__VLS_unwrap(reuseStream, {}))),
        });
        /** @type {__VLS_StyleScopedClasses['cam-link']} */ ;
    }
    else if (error.value) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cam-media cam-nosource" },
        });
        /** @type {__VLS_StyleScopedClasses['cam-media']} */ ;
        /** @type {__VLS_StyleScopedClasses['cam-nosource']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "ns-l1" },
        });
        /** @type {__VLS_StyleScopedClasses['ns-l1']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "ns-l2" },
        });
        /** @type {__VLS_StyleScopedClasses['ns-l2']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cam-meta" },
        });
        /** @type {__VLS_StyleScopedClasses['cam-meta']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (loadStreams) },
            ...{ class: "td-btn sm" },
            type: "button",
        });
        /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm']} */ ;
    }
    else if (loading.value && streams.value === null) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "empty sm" },
        });
        /** @type {__VLS_StyleScopedClasses['empty']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm']} */ ;
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cam-media cam-nosource" },
        });
        /** @type {__VLS_StyleScopedClasses['cam-media']} */ ;
        /** @type {__VLS_StyleScopedClasses['cam-nosource']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "ns-l1" },
        });
        /** @type {__VLS_StyleScopedClasses['ns-l1']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "ns-l2" },
        });
        /** @type {__VLS_StyleScopedClasses['ns-l2']} */ ;
        (__VLS_unwrap(reuseStream, {}));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cam-meta" },
        });
        /** @type {__VLS_StyleScopedClasses['cam-meta']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
            ...{ class: "cam-link" },
            href: (__VLS_unwrap(perceptionHref, {})(__VLS_unwrap(reuseStream, {}))),
        });
        /** @type {__VLS_StyleScopedClasses['cam-link']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "cam-note" },
    });
    /** @type {__VLS_StyleScopedClasses['cam-note']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    (__VLS_unwrap(demoCameraTotal, {}));
    (__VLS_unwrap(demoCameraTotal, {}));
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    if (cameras.value.length === 0) {
    }
    else {
        (__VLS_unwrap(noVideoCids, {}));
    }
    (cameras.value.length);
}
else {
    if (error.value && __VLS_unwrap(videoCount, {}) > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "cam-warn" },
        });
        /** @type {__VLS_StyleScopedClasses['cam-warn']} */ ;
        (error.value);
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (loadStreams) },
            ...{ class: "td-btn sm" },
            type: "button",
        });
        /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm']} */ ;
    }
    else if (loading.value && streams.value === null) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "empty sm" },
        });
        /** @type {__VLS_StyleScopedClasses['empty']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm']} */ ;
    }
    const __VLS_0 = __VLS_tryAsConstant((__VLS_unwrap(views, {})));
    for (const [view] of __VLS_vFor(__VLS_nonNull(__VLS_0))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (view.cid),
            ...{ class: "cam-row" },
        });
        /** @type {__VLS_StyleScopedClasses['cam-row']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cam-head" },
        });
        /** @type {__VLS_StyleScopedClasses['cam-head']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "cam-id td-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['cam-id']} */ ;
        /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
        (view.cid);
        (view.source);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "cam-name" },
        });
        /** @type {__VLS_StyleScopedClasses['cam-name']} */ ;
        (view.name);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "td-chip" },
            ...{ class: ({ ok: view.hasVideo && view.meta, out: !view.hasVideo, err: view.hasVideo && !view.meta && !error.value }) },
        });
        /** @type {__VLS_StyleScopedClasses['td-chip']} */ ;
        /** @type {__VLS_StyleScopedClasses['ok']} */ ;
        /** @type {__VLS_StyleScopedClasses['out']} */ ;
        /** @type {__VLS_StyleScopedClasses['err']} */ ;
        (!view.hasVideo ? '未接入视频源' : frameFailed.value[view.source] ? '帧加载失败' : view.meta ? '样本视频回放' : error.value ? '服务不可用' : '未导出');
        if (view.hasVideo && view.meta) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cam-media" },
            });
            /** @type {__VLS_StyleScopedClasses['cam-media']} */ ;
            if (!frameFailed.value[view.source]) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.img)({
                    ...{ onError: // @ts-ignore
                        (...[$event]) => {
                            void $event;
                            if (!!(!hasAnyVideo.value))
                                throw 0;
                            if (!(view.hasVideo && view.meta))
                                throw 0;
                            if (!(!frameFailed.value[view.source]))
                                throw 0;
                            return (onFrameError(view.source));
                            // @ts-ignore
                            [cameras, cameras, demoCameraTotal, demoCameraTotal, reuseMeta, reuseMeta, reuseMeta, reuseMeta, noVideoCids, error, error, error, error, error, reuseFrameFailed, reuseStream, reuseStream, reuseStream, reuseStream, perceptionHref, perceptionHref, loading, loading, streams, streams, videoCount, views, frameFailed, frameFailed,];
                        } },
                    ...{ class: "cam-img" },
                    src: (__VLS_unwrap(perceptionFrameUrl, {})(view.source, frameOf(view))),
                    alt: (`${view.cid} ${view.name} 样本视频抽帧`),
                    loading: "lazy",
                });
                /** @type {__VLS_StyleScopedClasses['cam-img']} */ ;
            }
            else {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "cam-media cam-nosource" },
                });
                /** @type {__VLS_StyleScopedClasses['cam-media']} */ ;
                /** @type {__VLS_StyleScopedClasses['cam-nosource']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "ns-l1" },
                });
                /** @type {__VLS_StyleScopedClasses['ns-l1']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "ns-l2" },
                });
                /** @type {__VLS_StyleScopedClasses['ns-l2']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                    ...{ onClick: // @ts-ignore
                        (...[$event]) => {
                            void $event;
                            if (!!(!hasAnyVideo.value))
                                throw 0;
                            if (!(view.hasVideo && view.meta))
                                throw 0;
                            if (!!(!frameFailed.value[view.source]))
                                throw 0;
                            return (retryFrame(view.source));
                            // @ts-ignore
                            [perceptionFrameUrl,];
                        } },
                    ...{ class: "td-btn sm" },
                    type: "button",
                });
                /** @type {__VLS_StyleScopedClasses['td-btn']} */ ;
                /** @type {__VLS_StyleScopedClasses['sm']} */ ;
            }
            if (!frameFailed.value[view.source]) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "cam-badge" },
                });
                /** @type {__VLS_StyleScopedClasses['cam-badge']} */ ;
            }
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cam-meta td-mono" },
            });
            /** @type {__VLS_StyleScopedClasses['cam-meta']} */ ;
            /** @type {__VLS_StyleScopedClasses['td-mono']} */ ;
            (view.meta.width);
            (view.meta.height);
            (view.meta.fps);
            (view.meta.total_frames);
            (view.meta.track_total);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "sep" },
            });
            /** @type {__VLS_StyleScopedClasses['sep']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
                ...{ class: "cam-link" },
                href: (__VLS_unwrap(perceptionHref, {})(view.source)),
            });
            /** @type {__VLS_StyleScopedClasses['cam-link']} */ ;
        }
        else if (view.hasVideo) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cam-media cam-nosource" },
            });
            /** @type {__VLS_StyleScopedClasses['cam-media']} */ ;
            /** @type {__VLS_StyleScopedClasses['cam-nosource']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "ns-l1" },
            });
            /** @type {__VLS_StyleScopedClasses['ns-l1']} */ ;
            (error.value ? '感知服务不可用' : '未导出');
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "ns-l2" },
            });
            /** @type {__VLS_StyleScopedClasses['ns-l2']} */ ;
            (error.value ? '画面不可用（不伪造）' : '有样本视频，等待感知服务处理');
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cam-meta" },
            });
            /** @type {__VLS_StyleScopedClasses['cam-meta']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
                ...{ class: "cam-link" },
                href: (__VLS_unwrap(perceptionHref, {})(view.source)),
            });
            /** @type {__VLS_StyleScopedClasses['cam-link']} */ ;
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cam-media cam-nosource" },
            });
            /** @type {__VLS_StyleScopedClasses['cam-media']} */ ;
            /** @type {__VLS_StyleScopedClasses['cam-nosource']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "ns-l1" },
            });
            /** @type {__VLS_StyleScopedClasses['ns-l1']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "ns-l2" },
            });
            /** @type {__VLS_StyleScopedClasses['ns-l2']} */ ;
        }
        // @ts-ignore
        [error, error, perceptionHref, perceptionHref, frameFailed,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "cam-note" },
    });
    /** @type {__VLS_StyleScopedClasses['cam-note']} */ ;
    (cameras.value.length);
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    (__VLS_unwrap(demoCameraTotal, {}));
    (__VLS_unwrap(demoCameraTotal, {}));
}
// @ts-ignore
[cameras, demoCameraTotal, demoCameraTotal,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
