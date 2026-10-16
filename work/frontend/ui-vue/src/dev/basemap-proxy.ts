// 底图（OpenFreeMap）**同源直通**中间件：dev / preview 挂载（2026-10-16）。
//
// 存在的理由（不是"加速"，是"能不能拿到"）：
//   vite dev server 跑在 **Node** 里，Node 的 `fetch` **不读系统代理**（实测：本机 Windows 系统代理
//   把 `tiles.openfreemap.org` 黑洞掉，`curl -x 127.0.0.1:7897` 返 000，`--noproxy '*'` 返 200）。
//   浏览器侧走的是系统代理，于是"样式 JSON 命中 HTTP 缓存能拿到、瓦片一直挂到超时"，
//   地图只剩底色、没有路和建筑。经这条路由转发后，浏览器只访问**同源**地址，绕开代理。
//
// 合规（改之前先读 `docs/条款核实.md`）：
//   · **只转发、不落盘**：不写瓦片缓存层、不预取、不批量下载（红线 1 / 必做 2）；
//   · 上游响应的 `Cache-Control` **原样透传**，不自己加长缓存、不覆盖上游的头（OSM 瓦片政策第 3.2 节
//     要求"尊重服务端缓存头"）；
//   · 上游地址**写死在白名单里**（`BASEMAP_UPSTREAM`），路径里不接受完整 URL —— 否则就成了
//     一个可被拿去打任意站点的开放代理。
//
// 生产构建**没有这条路**：`vite build` 产物里不含本插件，浏览器侧探测不到就回落成直连上游
// （`src/shared/basemap.ts` 的 `toBasemapUrl`）。要让线上也走代理，那是**部署侧反向代理**的事，
// 不在本期范围。

import type { Connect, Plugin } from 'vite'
import { BASEMAP_PROXY_PREFIX, BASEMAP_UPSTREAM } from '../shared/basemap.ts'

/** 单次转发的上游超时（瓦片很小，超过这个数基本就是"网络不通"，早失败早显示失败态） */
const UPSTREAM_TIMEOUT_MS = 8000

/** 透传哪些上游响应头（白名单：只透传"给浏览器用得上"的那几个，别的（Set-Cookie / NEL 等）丢掉） */
const PASS_THROUGH_HEADERS = ['content-type', 'content-length', 'cache-control', 'expires', 'etag', 'last-modified']

export function basemapProxyPlugin(): Plugin {
  const install = (middlewares: Connect.Server): void => {
    middlewares.use(BASEMAP_PROXY_PREFIX, (req, res, next) => {
      const url = new URL(req.url ?? '/', 'http://basemap.local')
      const path = url.pathname
      // 前缀本身（`/basemap` 或 `/basemap/`）不是资源，交回给后面的中间件（SPA 回退）
      if (path === '/' || path === '') return next()

      const method = (req.method ?? 'GET').toUpperCase()
      if (method !== 'GET' && method !== 'HEAD') {
        res.statusCode = 405
        res.setHeader('Allow', 'GET, HEAD')
        res.end()
        return
      }

      if (path === '/health') {
        res.statusCode = 200
        res.setHeader('Content-Type', 'application/json; charset=utf-8')
        res.setHeader('Cache-Control', 'no-store')
        res.end(JSON.stringify({ ok: true, upstream: BASEMAP_UPSTREAM }))
        return
      }

      void forward(req, res, `${BASEMAP_UPSTREAM}${path}${url.search}`)
    })
  }
  return {
    name: 'ui-vue-basemap-proxy',
    apply: 'serve',
    configureServer(server) {
      install(server.middlewares)
      server.config.logger.info(
        `  ui-vue-basemap-proxy: 底图同源直通已挂载(${BASEMAP_PROXY_PREFIX}/* → ${BASEMAP_UPSTREAM}，不落盘)`,
        { timestamp: true },
      )
    },
    configurePreviewServer(server) {
      install(server.middlewares)
      server.config.logger.info(
        `  ui-vue-basemap-proxy: 底图同源直通已挂载(${BASEMAP_PROXY_PREFIX}/* → ${BASEMAP_UPSTREAM}，不落盘)`,
        { timestamp: true },
      )
    },
  }
}

async function forward(
  req: Connect.IncomingMessage,
  res: import('node:http').ServerResponse,
  target: string,
): Promise<void> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), UPSTREAM_TIMEOUT_MS)
  try {
    const upstream = await fetch(target, {
      signal: ctrl.signal,
      // 不带 Cookie / 不带 Referer：我们只是把公共底图取回来给本机页面看
      headers: { Accept: String(req.headers.accept ?? '*/*') },
      redirect: 'follow',
    })
    res.statusCode = upstream.status
    for (const h of PASS_THROUGH_HEADERS) {
      const v = upstream.headers.get(h)
      if (v) res.setHeader(h, v)
    }
    // 二进制（.pbf / .png）与文本（.json）一律按字节透传，不做任何改写。
    // ⚠️ 用 `Uint8Array` 而不是 `Buffer`：与 `src/mock/` 同一条纪律（服务器侧代码不碰 Node 专有全局）
    const body = new Uint8Array(await upstream.arrayBuffer())
    res.setHeader('Content-Length', String(body.byteLength))
    res.end(body)
  } catch (e) {
    const aborted = e instanceof Error && e.name === 'AbortError'
    res.statusCode = 504
    res.setHeader('Content-Type', 'application/json; charset=utf-8')
    res.setHeader('Cache-Control', 'no-store')
    res.end(
      JSON.stringify({
        ok: false,
        code: aborted ? 'BASEMAP_UPSTREAM_TIMEOUT' : 'BASEMAP_UPSTREAM_FAILED',
        message: aborted
          ? `底图直通超时（>${UPSTREAM_TIMEOUT_MS} ms）：${target}`
          : `底图直通失败：${target}`,
      }),
    )
  } finally {
    clearTimeout(timer)
  }
}
