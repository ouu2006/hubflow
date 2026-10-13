import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import { applyNetworkOverride, type DemoSegment } from './shared/demoNetwork'
import { activePack, setActivePackKey } from './station-packs/index'
import 'element-plus/dist/index.css'
import './style.css'

// 站点包注入(**必须早于任何用到包的模块求值**):`.env.station2` 里写 `VITE_STATION_PACK=B`,
// `vite --mode station2` 起来就是第二个站。取不到则落默认包 A(肇庆东站示例路网)。
// 这一步在 `import` 语句之后执行但早于下面任何函数调用 —— 包是惰性读的(见 demoNetwork.ts),
// 所以"模块加载期就读包"的坑不会踩到。
setActivePackKey(import.meta.env.VITE_STATION_PACK ?? 'A')

// #61 twin_preview:挂载前拉 SUMO 真路网(原地替换站点包路网,NetMap/面板/mock 统一生效)。
// 桥接服务(:8102,经 /twin-api 代理)不可用即保持站点包路网,1.2 s 超时不阻塞白屏。
//
// ⚠️ 是否拉由**站点包**决定(`pack.bridge.enabled`):桥接服务跑的是肇庆东站的 OSM 切片,
// 对自建示意路网的站(二站)毫无关系 —— 拉下来会把别站的路网画到本站图上,所以包说关就不拉。
async function loadTwinNetwork(): Promise<void> {
  if (!activePack().bridge.enabled) return
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 1200)
  try {
    const res = await fetch('/twin-api/network', { signal: ctrl.signal })
    if (!res.ok) return
    const data = (await res.json()) as { note?: unknown; segments?: unknown }
    if (!Array.isArray(data.segments) || data.segments.length === 0) return
    applyNetworkOverride(data.segments as DemoSegment[], String(data.note ?? 'OSM 真路网 · SUMO 仿真演示'))
  } catch {
    // 桥接服务不在:回落站点包路网
  } finally {
    clearTimeout(timer)
  }
}

await loadTwinNetwork()
createApp(App).use(ElementPlus, { locale: zhCn }).use(router).mount('#app')
