// TDesign Light 设计令牌(手册 §6.2 / §6.2.1,2026-10-12 配色整体切换)。
// 这里是**唯一色源**:页面 / 组件 / 图表一律从本文件取值,不得在 SFC 内硬编码他色。
// 语义分工(手册 §6.2「语义分工」,改色前必读):
//   ① 品牌蓝只表示「可操作 / 当前 / 已选」;② 四级色只服务路况等级;
//   ③ 数据不可用恒为中性灰,绝不显示为蓝/绿;④ 车型框色与等级色解耦(视频页专用)。
// 深色例外只限视频感知页的**监控画面区**(tdVideo),不得外溢到页面壳层。
/** 页面壳层与通用组件 token */
export const TD = {
    // 底色与容器
    bgPage: '#EEEEEE',
    bgContainer: '#FFFFFF',
    bgSecondary: '#F3F3F3',
    bgComponent: '#E8E8E8',
    bgHover: '#F7F8FA',
    // 描边
    stroke: '#E8E8E8',
    border: '#DDDDDD',
    // 品牌(独占「可操作 / 当前 / 已选」)
    brand: '#0052D9',
    brandHover: '#366EF4',
    brandActive: '#003CAB',
    brand1: '#F2F3FF',
    brand2: '#D9E1FF',
    brand3: '#A0C0FF',
    // 功能色
    success: '#2BA471',
    success1: '#E3F9E9',
    warning: '#E37318',
    warning1: '#FFF1E9',
    error: '#D54941',
    error1: '#FFF0ED',
    // 文字四级
    textPrimary: '#1A1A1A',
    textSecondary: '#666666',
    textPlaceholder: '#999999',
    textDisabled: '#BDBDBD',
    textAnti: '#FFFFFF',
    // 圆角
    radiusSm: '3px',
    radiusMd: '6px',
    radiusLg: '9px',
};
/** 字段名(单位)与数值字号用等宽字体;中文用 Noto Sans SC,本机缺失时逐级回落 */
export const FONT_SANS = "'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', '微软雅黑', 'Helvetica Neue', Arial, sans-serif";
export const FONT_MONO = "'JetBrains Mono', 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace";
/**
 * 视频监控画面区深色 token(手册 §6.2.1「深色例外」)。
 * ⚠️ 仅限画面区:YOLO 检测框与越线计数线需要高对比底,且真实监控画面本就是深色。
 */
export const TD_VIDEO = {
    bg: '#181818',
    bg1: '#242424',
    bg2: '#2C2C2C',
    line: '#393939',
    dim: '#5E5E5E',
    text: '#EDEDED',
    textDim: '#9E9E9E',
    brand: '#699EF5',
};
/** 车型框色(视频感知页专用,与等级色**解耦**;手册 §6.2) */
export const CLASS_COLORS = {
    car: '#16C7B4',
    van: '#4A90D9',
    bus: '#9B7BE0',
    truck: '#E05299',
};
/** 司机类型(D1 送客 / D2 接客 / D3 往返)动点色——轻量、只作点缀,不与等级色/车型色重号 */
export const DRIVER_COLORS = {
    D1: '#FFC53D',
    D2: '#4FD1C5',
    D3: '#B58BFF',
};
/** 把 token 挂成 CSS 变量(页面根节点调用一次即可,供 style/CSS 内使用) */
export function themeVars() {
    return {
        '--td-bg-color-page': TD.bgPage,
        '--td-bg-color-container': TD.bgContainer,
        '--td-bg-color-secondarycontainer': TD.bgSecondary,
        '--td-bg-color-component': TD.bgComponent,
        '--td-component-stroke': TD.stroke,
        '--td-component-border': TD.border,
        '--td-brand-color': TD.brand,
        '--td-brand-color-1': TD.brand1,
        '--td-brand-color-3': TD.brand3,
        '--td-success-color': TD.success,
        '--td-warning-color': TD.warning,
        '--td-error-color': TD.error,
        '--td-text-color-primary': TD.textPrimary,
        '--td-text-color-secondary': TD.textSecondary,
        '--td-text-color-placeholder': TD.textPlaceholder,
        '--td-text-color-disabled': TD.textDisabled,
        '--td-text-color-anti': TD.textAnti,
        '--td-font-family': FONT_SANS,
        '--td-font-family-mono': FONT_MONO,
    };
}
