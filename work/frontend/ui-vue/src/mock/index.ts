// traffic mock 中间件:vite dev/preview server 挂载,仅态势大屏端点(Issue #52)。
// harness 八端点 mock 已随 2026-10-11 架构裁定移除;新后端接口面按前端页面重新规划定稿后在此重建。
// 铁律:不臆造端点——未匹配路径一律 404 并明示。

import type { Connect, Plugin } from 'vite'
import { handleTraffic } from './traffic.ts'
import { errShape, json, type MockReq, type MockRes } from './util.ts'

export function mockApiPlugin(): Plugin {
  const name = 'ui-vue-mock-api'
  const install = (middlewares: Connect.Server): void => {
    middlewares.use('/api', (req, res, next) => {
      handle(req, res, next).catch(() => {
        if (!res.writableEnded) json(res, 500, errShape('MOCK_INTERNAL', 'mock 中间件内部错误'))
      })
    })
  }
  return {
    name,
    apply: 'serve',
    configureServer(server) {
      install(server.middlewares)
      server.config.logger.info(`  ${name}: traffic mock 已挂载(/api/traffic/*)`, { timestamp: true })
    },
    configurePreviewServer(server) {
      install(server.middlewares)
      server.config.logger.info(`  ${name}: traffic mock 已挂载(dist 自演示)`, { timestamp: true })
    },
  }
}

async function handle(req: MockReq, res: MockRes, _next: Connect.NextFunction): Promise<void> {
  const method = (req.method ?? 'GET').toUpperCase()
  const url = new URL(req.url ?? '/', 'http://mock.local')
  const path = url.pathname.replace(/\/+$/, '') || '/'

  if (path.startsWith('/traffic/')) {
    const handled = await handleTraffic(path, method, req, res)
    if (handled) return
  }

  return json(res, 404, errShape('NOT_FOUND', `无此端点(表外): ${method} /api${path}`))
}
