/**
 * 全局复用色值常量（避免硬编码分散在多个页面）。
 *
 * 统一管理原则：
 * 1. 语义化命名：TEXT_PRIMARY / BG_BASE / ACCENT_EMERGENCY 等；
 * 2. 仅放入 2 处以上复用色；页面独特色可留在本页；
 * 3. 主题切换时只改本文件即可。
 */

// ---- 文字色 ----
export const TEXT_PRIMARY: string = '#1A1A1A';
export const TEXT_SECONDARY: string = '#666666';
export const TEXT_TERTIARY: string = '#8B8B8B';
export const TEXT_WHITE: string = '#FFFFFF';
export const TEXT_ON_EMERGENCY: string = '#FFFFFF';
export const TEXT_ON_EMERGENCY_SUB: string = '#FBE9E7';

// ---- 背景色 ----
export const BG_BASE: string = '#FFFFFF';
export const BG_GRAY_LIGHT: string = '#FAFAFA';
export const BG_GRAY_LIGHTER: string = '#F5F5F5';
export const BG_GRAY_OFF: string = '#F0F0F0';
export const BG_HIGHLIGHT: string = '#F0F5FF';
/** 顶部页签选中态底色（比 BG_HIGHLIGHT 更淡一档，压在标题栏上不抢视线） */
export const BG_TAB_ACTIVE: string = '#EAF1FE';
/** 方案卡「当前选中」底色（比 BG_TAB_ACTIVE 略深一档）；禁止态下不得使用 */
export const BG_SELECTED: string = '#E8F1FE';

// ---- 应急/降级/不可用/去色 ----
export const ACCENT_EMERGENCY: string = '#C62828';
export const ACCENT_EMERGENCY_BG: string = '#D54941';
export const ACCENT_UNAVAILABLE: string = '#5F5E5A';
export const ACCENT_DEGRADED: string = '#A06A00';
export const ACCENT_COLOR_BLIND: string = '#0052D9';

// ---- 边框/分割线 ----
export const BORDER_PRIMARY: string = '#E8E8E8';
export const BORDER_ACCENT: string = '#0052D9';

// ---- 状态色 ----
export const STATE_ADOPTED: string = '#006C45';
export const STATE_REJECTED: string = '#A06A00';

// ---- 降级 / 不可用提示条专用（深底白字，与页面级ACCENT_* 区分：这里是条内文字色）----
/** 降级提示条正文色（琥珀深底上的浅米色） */
export const TEXT_ON_DEGRADED: string = '#F0E2C8';
/** 降级提示条底色（比 ACCENT_DEGRADED 更深，保证白字对比度） */
export const BG_DEGRADED_BAR: string = '#7A5A16';
/** 应急提示条副标题色（比 TEXT_ON_EMERGENCY_SUB 略深） */
export const TEXT_ON_EMERGENCY_BAR_SUB: string = '#F5D9D9';
/** 不可用提示条副标题色（灰底上的浅灰） */
export const TEXT_ON_UNAVAILABLE_BAR_SUB: string = '#E4E4E4';

/** 地图角标「路网」文字色 */
export const TEXT_MAP_LABEL: string = '#2A3B4D';
/** 地图角标次级说明文字色 */
export const TEXT_MAP_LABEL_SUB: string = '#3C4A52';
/** 地图角标底部说明文字色 */
export const TEXT_MAP_FOOT: string = '#5A6B72';
/** 地图应急角标底色（带透明度，8 位hex） */
export const BG_MAP_TAG_EMERGENCY: string = '#B33939E6';
/** 地图常态角标底色（带透明度） */
export const BG_MAP_TAG: string = '#F2F5F0E6';
/** 地图常态角标次级底色（更透明，压在地图上不遮挡路网） */
export const BG_MAP_TAG_SUB: string = '#F2F5F0CC';
