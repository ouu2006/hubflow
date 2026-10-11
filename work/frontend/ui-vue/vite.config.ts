import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'
import { mockApiPlugin } from './src/mock/index.ts'

// 工程约定:
// - VITE_USE_MOCK=1(默认,mode=development)→ 挂本地 traffic mock 中间件(态势大屏假数据 + SSE 假流);
// - VITE_USE_MOCK=0(mode=remote/production)→ 不挂 mock,/api 走代理/同源,VITE_API_BASE 为代理目标。
// (VITE_MOCK_ERROR error 注入随 harness mock 一并移除,待新接口面定稿后重订。)
export default defineConfig(({ mode }) => {
  // 前缀 '' 连同 shell 导出的 VITE_* 一起读入
  const env = loadEnv(mode, process.cwd(), '')
  const useMock = env.VITE_USE_MOCK !== '0'
  const apiTarget = env.VITE_API_BASE || 'http://127.0.0.1:8000'
  const proxy = { '/api': { target: apiTarget, changeOrigin: true, ws: false } }

  return {
    plugins: [vue(), ...(useMock ? [mockApiPlugin()] : [])],
    server: useMock ? {} : { proxy },
    preview: useMock ? {} : { proxy },
  }
})
