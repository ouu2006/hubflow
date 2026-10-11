import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'
import { mockApiPlugin } from './src/mock/index.ts'

// 工程约定:
// - VITE_USE_MOCK=1(默认,mode=development)→ 挂本地 traffic mock 中间件(态势大屏假数据 + SSE 假流);
// - VITE_USE_MOCK=0(mode=remote/production)→ 不挂 mock,/api 走代理/同源,VITE_API_BASE 为代理目标。
// - 感知演示服务(work/perception/server.py,默认 127.0.0.1:8101)走独立前缀 /perception-api,
//   代理时重写为服务端的 /api/perception/*——不复用 /api 前缀,避免与 traffic mock 中间件
//   互相吞路径(mock 对未匹配 /api 路径一律 404,是刻意设计,不改)(Issue #54)。
// (VITE_MOCK_ERROR error 注入随 harness mock 一并移除,待新接口面定稿后重订。)
export default defineConfig(({ mode }) => {
  // 前缀 '' 连同 shell 导出的 VITE_* 一起读入
  const env = loadEnv(mode, process.cwd(), '')
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
  const trafficProxy = { '/api': { target: apiTarget, changeOrigin: true, ws: false } }
  const proxy = { ...perceptionProxy, ...trafficProxy }

  return {
    plugins: [vue(), ...(useMock ? [mockApiPlugin()] : [])],
    server: { proxy },
    preview: { proxy },
  }
})
