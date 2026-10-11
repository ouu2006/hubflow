import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import { applyNetworkOverride, type DemoSegment } from './shared/demoNetwork'
import 'element-plus/dist/index.css'
import './style.css'

// #61 twin_preview:挂载前拉 SUMO 真路网(原地替换示例路网,NetMap/面板/mock 统一生效)。
// 桥接服务(:8102,经 /twin-api 代理)不可用即保持示例路网,1.2 s 超时不阻塞白屏。
async function loadTwinNetwork(): Promise<void> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 1200)
  try {
    const res = await fetch('/twin-api/network', { signal: ctrl.signal })
    if (!res.ok) return
    const data = (await res.json()) as { note?: unknown; segments?: unknown }
    if (!Array.isArray(data.segments) || data.segments.length === 0) return
    applyNetworkOverride(data.segments as DemoSegment[], String(data.note ?? 'OSM 真路网 · SUMO 仿真演示'))
  } catch {
    // 桥接服务不在:回落示例路网
  } finally {
    clearTimeout(timer)
  }
}

await loadTwinNetwork()
createApp(App).use(ElementPlus, { locale: zhCn }).use(router).mount('#app')
