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
