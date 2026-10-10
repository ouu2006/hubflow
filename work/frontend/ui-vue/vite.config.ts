import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'
import { mockApiPlugin } from './src/mock/index.ts'

// C 轨(04 任务书)工程约定:
// - VITE_USE_MOCK=1(默认,mode=development)→ 挂本地 mock 中间件(§5.2 全端点假数据 + SSE 假流);
// - VITE_USE_MOCK=0(mode=remote/production)→ 不挂 mock,/api 走代理/同源,VITE_API_BASE 为代理目标。
export default defineConfig(({ mode }) => {
  // 前缀 '' 连同 shell 导出的 VITE_* 一起读入(Git Bash `VITE_MOCK_ERROR=1 npm run dev` 生效)
  const env = loadEnv(mode, process.cwd(), '')
  const useMock = env.VITE_USE_MOCK !== '0'
  const errorInject = env.VITE_MOCK_ERROR === '1'
  const apiTarget = env.VITE_API_BASE || 'http://127.0.0.1:8000'
  const proxy = { '/api': { target: apiTarget, changeOrigin: true, ws: false } }

  return {
    plugins: [vue(), ...(useMock ? [mockApiPlugin({ errorInject })] : [])],
    server: useMock ? {} : { proxy },
    preview: useMock ? {} : { proxy },
  }
})
