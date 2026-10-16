import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import { applyNetworkOverride, type DemoSegment } from './shared/demoNetwork'
import { activePack, restorePackKey, setActivePackKey } from './station-packs/index'
import 'element-plus/dist/index.css'
import './style.css'

// 站点包注入(**必须早于任何用到包的模块求值**):`.env.z` 里写 `VITE_STATION_PACK=Z`,
// `vite --mode z` 起来就是肇庆东站 OSM 真路网。取不到则落默认包 Z
// —— **本仓现在只有一个包:Z**(IKM4KP 删 B / Y、IKM4XX 删 A)。
// ⚠️ 先问 `restorePackKey`:顶栏线路图切换器选完会整页刷新,而包键是模块级变量、刷新即丢 ——
//    不读回 localStorage 的话,切换器选完就退回默认包(等于坏的)。
// ⚠️ 这个兜底必须与 `vite.config.ts` 注入 mock 的默认值**同为 Z**:只改一处就会出现
//    「页面画 Z 的路网、mock 发另一个包的基线」的错位画面。
setActivePackKey(restorePackKey(import.meta.env.VITE_STATION_PACK ?? 'Z'))

// #61 twin_preview:挂载前拉 SUMO 真路网(原地替换站点包路网,NetMap/面板/mock 统一生效)。
// 桥接服务(:8102,经 /twin-api 代理)不可用即保持站点包路网,1.2 s 超时不阻塞白屏。
//
// ⚠️ 是否拉由**站点包**决定(`pack.bridge.enabled`):桥接服务跑的是它自己那份 OSM 切片,
// 对自建示意路网的站毫无关系 —— 拉下来会把别站的路网画到本站图上,所以包说关就不拉
// (唯一站点包 Z 自己就是 OSM 真几何,`bridge.enabled = false`)。
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
