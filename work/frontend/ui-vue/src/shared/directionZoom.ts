// 方向箭头图层的**缩放档位常量**（唯一真源）。
//
// 为什么单独开一个文件、而不是留在 `views/dashboard/components/MapLibreViewer.vue` 里：
// 「进站取景的最小缩放」等于「箭头完全不透明的那一档」（`DIR_ZOOM_FULL`），
// 而取景逻辑住在 `shared/mapMotion.ts`。两边各写一个 15.5 迟早分叉 ——
// 组件里调了阈值、取景没跟上，就又是「小屏进站看不见箭头」那一类 bug。

/** 箭头完全不透明的档（zoom）：150 m 档。业主口径「150 及以内箭头和道路一样大」 */
export const DIR_ZOOM_FULL = 15.5
/** 箭头开始淡出的档（zoom）：200 m 档。更远一支不画（opacity 0） */
export const DIR_ZOOM_FADE = 15.0
