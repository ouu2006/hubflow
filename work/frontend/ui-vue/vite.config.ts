import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'
import { basemapProxyPlugin } from './src/dev/basemap-proxy.ts'
import { mockApiPlugin } from './src/mock/index.ts'
import { setActivePackKey } from './src/station-packs/index.ts'

// 工程约定:
// - VITE_USE_MOCK=1(默认,mode=development)→ 挂本地 traffic mock 中间件(态势大屏假数据 + SSE 假流);
// - VITE_USE_MOCK=0(mode=remote/production)→ 不挂 mock,/api 走代理/同源,VITE_API_BASE 为代理目标。
// - 感知演示服务(work/perception/server.py,默认 127.0.0.1:8101)走独立前缀 /perception-api,
//   代理时重写为服务端的 /api/perception/*——不复用 /api 前缀,避免与 traffic mock 中间件
//   互相吞路径(mock 对未匹配 /api 路径一律 404,是刻意设计,不改)(Issue #54)。
// - 孪生预览服务(work/frontend/tools/twin_preview/server.py,默认 127.0.0.1:8102)走独立前缀 /twin-api,
//   代理时重写为服务端的 /api/twin/*——不复用 /api 前缀,避免被 traffic mock 中间件吞路径
//   (mock 对未匹配 /api 路径一律 404,是刻意设计,不改)(Issue #61)。
// - **站点包**(2026-10-12;2026-10-16 IKM4KP 起以 Z 为主、IKM4XX 起**只剩 Z**):`VITE_STATION_PACK`
//   选哪个包(`src/station-packs/`,现只有 Z),`vite --mode z` 即在 `.env.z` 里把它设成 Z。
//   两侧取值必须一致,所以这里读到的键**显式注入** mock 中间件 —— 浏览器侧由 main.ts 注入同一个键,
//   页面与 mock 才不会一站一路网。⚠️ 兜底默认值必须与 `main.ts` 的同为 Z(只改一处会错位)。
// (VITE_MOCK_ERROR error 注入随 harness mock 一并移除,待新接口面定稿后重订。)
export default defineConfig(({ mode }) => {
  // 前缀 '' 连同 shell 导出的 VITE_* 一起读入
  const env = loadEnv(mode, process.cwd(), '')
  setActivePackKey(env.VITE_STATION_PACK || process.env.VITE_STATION_PACK || 'Z')

  const useMock = env.VITE_USE_MOCK !== '0'
  const apiTarget = env.VITE_API_BASE || 'http://127.0.0.1:8000'
  const perceptionTarget = env.VITE_PERCEPTION_API_BASE || 'http://127.0.0.1:8101'
  const perceptionProxy = {
    '/perception-api': {
      target: perceptionTarget,
      changeOrigin: true,
      rewrite: (p: string) => p.replace(/^\/perception-api/, '/api/perception'),
    },
  }
  const twinTarget = env.VITE_TWIN_API_BASE || 'http://127.0.0.1:8102'
  const twinProxy = {
    '/twin-api': {
      target: twinTarget,
      changeOrigin: true,
      rewrite: (p: string) => p.replace(/^\/twin-api/, '/api/twin'),
    },
  }
  const trafficProxy = { '/api': { target: apiTarget, changeOrigin: true, ws: false } }
  const proxy = { ...perceptionProxy, ...twinProxy, ...trafficProxy }

  // dev:z 起在独立端口:6895(与默认 5173 并存,同一个包 Z 可开两份对照着看)
  // 端口策略（Issue IKP58M）：前端固定 5173（或 VITE_DEV_PORT 显式指定），strictPort 打开后
  // 端口被占**直接启动失败并提示**，不会静默顺延到 5174 —— README 全篇写的是 5173，
  // 顺延会让「照文档打开」变成打开另一个空端口，反而像项目坏了。
  const server = {
    proxy,
    port: Number(env.VITE_DEV_PORT) || 5173,
    strictPort: true,
  }

  return {
    plugins: [
      vue(),
      ...(useMock ? [mockApiPlugin()] : []),
      // 底图同源直通(2026-10-16):dev/preview 上把 /basemap/* 转发到 OpenFreeMap。
      // 为什么不用现成的 vite proxy:vite 的 http-proxy 同样跑在 Node(一样绕开系统代理),
      // 但它会把上游响应头**原样全透**、且路径任意拼——写自家中继是为了**只透传白名单响应头 +
      // 不接受完整 URL**(上游主机写死),不把这条路由做成开放代理。见 src/dev/basemap-proxy.ts。
      basemapProxyPlugin(),
    ],
    // ⚠️ 必须把 maplibre-gl 排除出依赖预打包,否则**矢量底图起不来**:
    //   MapLibre 主包用 `new URL('./maplibre-gl-worker.mjs', import.meta.url)` 引一个
    //   独立的 508 KB worker 文件(矢量瓦片解析全在 worker 里跑)。
    //   Vite 的 esbuild 预打包只产出 `deps/maplibre-gl.js`,**不会把那个 worker 一起产出** ——
    //   运行时 worker URL 落到不存在的 `deps/maplibre-gl-worker.mjs`,报
    //   「Worker failed to load」+ 504,底图整块空白(实测踩过)。
    //   排除后走原生 ESM,worker 与主包同在 dist/ 下,相对路径自然对得上。
    optimizeDeps: { exclude: ['maplibre-gl'] },
    server,
    preview: { proxy, port: Number(env.VITE_DEV_PORT) || 4173 },
  }
})
