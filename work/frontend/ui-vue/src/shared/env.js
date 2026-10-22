// 运行模式开关(与 `vite.config.ts` / `.env.*` 同源,浏览器侧可读):
//   · `VITE_USE_MOCK=1`(默认 `npm run dev` / preview:mock)→ 三页吃 vite mock 中间件,无后端也能演示;
//   · `VITE_USE_MOCK=0`(npm run dev:remote / build)→ `/api/traffic/*` 走 vite 代理到 traffic.py。
// 页面文案据此区分「mock 侧生效」与「接口层内存态」——两种模式都必须能独立演示(IKMS17)。
// 注意:浏览器端**不读** VITE_API_BASE(同源相对路径 + vite 代理),该变量只作代理目标。
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== '0';
/** 演示态称呼:mock=前端内存模拟;remote=接口层进程内存(重启复位) */
export const MEMORY_STATE_LABEL = USE_MOCK ? 'mock 侧生效' : '接口层内存态（重启复位）';
