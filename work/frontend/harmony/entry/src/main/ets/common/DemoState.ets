/**
 * 演示态说明（四页共用的四个开关，工程内模拟，非业务逻辑）：
 * 由 Index 用 @State 持有，再以 @Prop 下发给各页——**不使用模块级全局状态**，
 * 避免多次切换后「点了没反应 / 状态不同步」。
 * - emergency 应急状态：停止路线引导，替换为「请服从现场指挥」（手册 §11.1(3)）
 * - unavailable 数据不可用：等级一律灰色「数据不可用」，绝不显示成蓝色（TC-11）
 * - degraded 拒绝授权降级：降级为「手动选所在道路 / 只看路况」，流程不中断（TC-05 App 侧演示）
 * - colorBlind 去色校验：抽掉颜色通道，验证图标 + 文字仍能区分四级（手册 §11.3）
 *
 * 手动选择的道路是页面本地状态（RecommendPage 内的 @State），不进这里。
 */
export const DEMO_SWITCHES: string[] = ['emergency', 'unavailable', 'degraded', 'colorBlind'];
