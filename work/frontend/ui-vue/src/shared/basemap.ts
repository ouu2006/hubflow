// 底图（OpenFreeMap）的地址口径 —— 加一层"同源直通"的开关（2026-10-16）。
//
// 为什么要这一层（本机实测，PR 里附了证据）：
//   本机浏览器走的系统代理（`127.0.0.1:7897`）**把境外域名黑洞掉**：`curl -x` 对
//   `tiles.openfreemap.org` 返回 000；`curl --noproxy '*'` 同一地址 200。落到页面上就是
//   **样式 JSON 命中 HTTP 缓存拿得到（200，3 ms），tilejson 与整片 `.pbf` 瓦片一直挂到超时**
//   —— 地图只剩 Liberty 样式里的底色层：没有路、没有建筑。
//
// 解法分两半：
//   ① **服务器侧**：`src/dev/basemap-proxy.ts` 在 dev / preview 上挂一条同源直通路由
//      `/basemap/*`（vite dev server 跑在 Node 里，Node 的 `fetch` 不读系统代理 → 直连拿得到）；
//      **只转发、不落盘、不预取、不批量下载**（`docs/条款核实.md` 红线 1 / 必做 2）。
//   ② **浏览器侧**：先探一下那条路由在不在，在就把所有上游地址换成同源前缀；不在（生产构建、
//      或预览里没挂这个插件）就照旧直连上游。
//
// ⚠️ 本文件**同时被浏览器侧与 vite 插件（Node 侧）引用**，所以只放**纯字符串逻辑**：
//    任何 `window` / DOM 依赖都会在 `tsconfig.node.json` 下报错（那里 `types: ["node"]`、无 DOM lib）。
//    探测函数因用到 `window.setTimeout`，落在 `MapLibreViewer.vue` 里。

/** 上游底图服务：样式里的 `sources` / `sprites` / `glyphs` 全都指向它 */
export const BASEMAP_UPSTREAM = 'https://tiles.openfreemap.org'
/** OpenFreeMap Liberty 样式（免 Key、免注册；数据来自 OpenStreetMap） */
export const BASEMAP_STYLE_URL = `${BASEMAP_UPSTREAM}/styles/liberty`
/** dev / preview 直通代理的同源前缀（与 `src/dev/basemap-proxy.ts` 同一常量，改一处即可） */
export const BASEMAP_PROXY_PREFIX = '/basemap'
/** 代理的存活探测端点（返回 `{"ok":true}`；没挂这条路时拿到的不是 JSON，见下） */
export const BASEMAP_PROXY_PROBE = `${BASEMAP_PROXY_PREFIX}/health`

// 探测结果放模块级而不是组件状态：一次会话里只探一次，`MapLibreViewer` 重挂也照样有效。
let proxyDetected = false

export function setBasemapProxyDetected(on: boolean): void {
  proxyDetected = on
}

/**
 * 上游地址 → 同源代理地址。
 * 没探到代理、或不是上游那个源的地址，一律**原样返回**（样式里可能混着别家的 URL，不动它们）。
 * MapLibre 只认绝对地址，所以这里是"前缀替换"而不是"相对路径拼接"。
 */
export function toBasemapUrl(url: string): string {
  if (!proxyDetected) return url
  const prefix = `${BASEMAP_UPSTREAM}/`
  if (!url.startsWith(prefix)) return url
  return `${BASEMAP_PROXY_PREFIX}/${url.slice(prefix.length)}`
}
