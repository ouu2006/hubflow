// 决策工作台演示数据(仅 /decision 页面用,Issue #59)。
// 口径:效果对比是仿真对照(TC-14/TC-17 演示数据,同输入跑两遍),不是实测;
// 分流建议与阈值为演示值;告警与因素从契约 segments 快照派生,人工置位走
// mock POST /api/traffic/factors(手册第 19 章管理端人工置位口子)。
//
// ⚠️ 2026-10-12(站点包层):**分流建议不再写在本文件里** —— "建议往哪条路分流"取决于
// 这个站的路长什么样,属于站点包的内容,已移进 `station-packs/stationZ.ts`;
// 本文件只把当前包的那份转发出来。阈值 / 渠道枚举 / 效果对比这些**与站点无关**的展示口径
// 仍留在这里。
import { activePack } from '../station-packs/index.ts';
/**
 * 当前站点包的分流建议表(按 `segment_id` 取;未命中的路段走 `fallbackSuggestion`)。
 * 返回的是一个取值函数而不是常量:页面在挂载后读、包键在挂载前注入,常量在 `import`
 * 阶段求值会读到还没注入的默认包。
 */
export function diversionSuggestions() {
    return activePack().diversion;
}
/** 建议不存在时的兜底模板(来自当前站点包;承接段与 `segment_id` 回填为入参路段) */
export function fallbackSuggestion(segmentId) {
    const fb = activePack().diversionFallback;
    return { ...fb, segment_id: segmentId };
}
export const MANUAL_FACTOR_PRESETS = [
    { factor_id: 'F07', name: '交通事故 / 故障车(人工置位)', target: 'lanes', multiplier: 0.5, note: '封闭车道 → 触发红档(手册 §:2840)' },
    { factor_id: 'F08', name: '施工 / 临时管制(人工置位)', target: 'lanes', multiplier: 0.5, note: '车道 ×0.5,带生效时间窗(手册 §:2841)' },
    { factor_id: 'F11', name: '大型活动(人工置位)', target: 'demand', multiplier: 1.3, note: '到达需求 ×1.3(手册 §:2844)' },
];
// ---------- 分流下发渠道(Issue #66,手册 §11.2:系统建议 + 人工可编辑 + **下发渠道** + 回执) ----------
// 口径:一期**没有真实下发通道**,回执为演示态(存 mock 服务端内存态,刷新页面不清,
// 页头「复位演示态」清);信号只"生成建议并推送,
// 不下发到信号机"(手册 §:2262),所以渠道是**演示枚举**,不暗示已对接任何外部系统。
export const DISPATCH_CHANNELS = ['情报板', '导航软件推送', '现场调度', '广播'];
export const EFFECT_SCENARIOS = [
    {
        key: 'peak',
        name: '列车集中到达峰值',
        window: '仿真时钟 18:00–19:00 · 评估窗 30 min · 固定种子三跑',
        metrics: [
            { name: '全网总行程时间', unit: 'min', no_guide: 12.4, fastest: 11.1, cooperative: 9.1, better: 'down' },
            { name: '先进入车辆到达时间增量', unit: 's', no_guide: 0, fastest: 42, cooperative: 18, better: 'down' },
            { name: '新增橙/红路段数', unit: '个', no_guide: 0, fastest: 2, cooperative: 0, better: 'down' },
            { name: '排队长度峰值', unit: 'm', no_guide: 410, fastest: 355, cooperative: 180, better: 'down' },
            { name: '饱和度峰值 x', unit: '', no_guide: 0.98, fastest: 0.93, cooperative: 0.74, better: 'down' },
        ],
        counts: { inserted: 412, removed: 0, not_entered: 12, completed: 400 },
    },
    {
        key: 'normal',
        name: '常态平峰',
        window: '仿真时钟 14:00–15:00 · 评估窗 30 min · 固定种子三跑',
        metrics: [
            { name: '全网总行程时间', unit: 'min', no_guide: 7.2, fastest: 7.0, cooperative: 6.9, better: 'down' },
            { name: '先进入车辆到达时间增量', unit: 's', no_guide: 0, fastest: 6, cooperative: 3, better: 'down' },
            { name: '新增橙/红路段数', unit: '个', no_guide: 0, fastest: 0, cooperative: 0, better: 'down' },
            { name: '排队长度峰值', unit: 'm', no_guide: 48, fastest: 45, cooperative: 25, better: 'down' },
            { name: '饱和度峰值 x', unit: '', no_guide: 0.46, fastest: 0.45, cooperative: 0.38, better: 'down' },
        ],
        counts: { inserted: 268, removed: 0, not_entered: 0, completed: 268 },
    },
    {
        key: 'incident',
        name: '突发事件(事故封道)',
        window: '仿真时钟 08:10–09:10 · 评估窗 30 min · 固定种子三跑',
        metrics: [
            { name: '全网总行程时间', unit: 'min', no_guide: 15.8, fastest: 14.2, cooperative: 11.9, better: 'down' },
            { name: '先进入车辆到达时间增量', unit: 's', no_guide: 0, fastest: 68, cooperative: 24, better: 'down' },
            { name: '新增橙/红路段数', unit: '个', no_guide: 3, fastest: 3, cooperative: 0, better: 'down' },
            { name: '排队长度峰值', unit: 'm', no_guide: 520, fastest: 470, cooperative: 260, better: 'down' },
            { name: '饱和度峰值 x', unit: '', no_guide: 1.04, fastest: 0.99, cooperative: 0.81, better: 'down' },
        ],
        counts: { inserted: 356, removed: 18, not_entered: 26, completed: 312 },
    },
];
export const ACK_COMPARISON = {
    window: '处置前 30 min vs 处置后 30 min(仿真对照,时间窗等长对齐)',
    rows: [
        { name: '排队长度峰值', unit: 'm', before: 340, after: 180, better: 'down' },
        { name: '拥堵持续时间', unit: 'min', before: 26, after: 11, better: 'down' },
        { name: '饱和度和差', unit: 'Δx 合计', before: 3.42, after: 2.05, better: 'down' },
    ],
};
export const LEVEL_THRESHOLDS = [
    { metric: '饱和度 x', unit: '', bands: [{ level: 1, max: 0.45 }, { level: 2, max: 0.7 }, { level: 3, max: 0.9 }, { level: 4, max: 999 }] },
    { metric: '速度比 v/v_f', unit: '', bands: [{ level: 1, max: 0.6 }, { level: 2, max: 0.45 }, { level: 3, max: 0.25 }, { level: 4, max: 999 }] },
    { metric: '密度 k', unit: '辆/公里', bands: [{ level: 1, max: 20 }, { level: 2, max: 45 }, { level: 3, max: 70 }, { level: 4, max: 999 }] },
    { metric: '排队长度 L_q', unit: 'm', bands: [{ level: 1, max: 50 }, { level: 2, max: 150 }, { level: 3, max: 300 }, { level: 4, max: 999 }] },
];
export const THRESHOLD_CHANGELOG = [
    { time: '2026-10-10 16:20', operator: '开发B', change: 'L_q 三档上限 150 → 180 m(列车到达日试标定,留痕待签发)' },
    { time: '2026-10-09 10:05', operator: '开发B', change: '初始阈值导入 stations/thresholds.json v0.1' },
];
