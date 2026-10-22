// 顶栏页签目录(顶栏与路由共用一处,避免两处各写一份导致漂移)。
//
// 2026-10-13 三页收敛(Issue #77):Web 只保留三层,顺序即分层顺序 ——
// 感知层 → 决策层 → 监控大屏;原「拥挤度热力 /heat」并入监控大屏,不再是独立页签。
export const APP_TABS = [
    { key: 'perception', name: '感知层', route: '/perception' },
    { key: 'decision', name: '决策层', route: '/decision' },
    { key: 'dashboard', name: '监控大屏', route: '/dashboard' },
];
export const SOURCE_ITEMS = [
    { key: 'video', name: '视频链路' },
    { key: 'twin', name: '孪生链路' },
    { key: 'both', name: '并排' },
];
/** 顶栏常驻口径角标(手册:页面必须标「演示数据(模拟)· 双数据源」) */
export const DEMO_BADGE = '演示数据(模拟)· 双数据源(视频链路 + 孪生链路)';
