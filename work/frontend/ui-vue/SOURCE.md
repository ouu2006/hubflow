# 来源说明(工程落位留痕)

本目录 = 上游仓 `agentic-traffic-management/harness-core/ui-vue` 的**整体拷贝**(Issue #52,2026-10-11),作为 hubflow 一期管理端的开发基线。上游仓保持零改动。

| 项 | 值 |
|---|---|
| 来源仓库 | `YONEK0/agentic-traffic-management`(本地 clone,与本仓库同级) |
| 基线 | `main` 分支 commit `356361d`;工作树相对该 commit 仅有 `package-lock.json` 一处未提交修改(随拷贝带入)与若干 docs 层未提交删除(与本工程无关,未拷贝) |
| 拷贝排除 | `node_modules/`、`dist/`、`.env`(门禁禁入名单;内容只是 `VITE_USE_MOCK=1` 开关,缺省行为见 `.env.mock`) |
| 拷贝后修改 | `tsconfig.app.json` / `tsconfig.node.json` 去掉 JSONC 注释(仓库门禁对受管 JSON 做严格解析,注释会报红;编译行为不变) |
| 健壮性加固(2026-10-11,AI 审查清单逐条落地,均不改变页面结构与端点契约) | ① `api/http.ts` 导出 `onUnauthorized`,`api/sse.ts` / `api/upload.ts` 401 同样清登录态回登录页;② `api/sse.ts` 流 EOF 未见 finish/error 时显式发 `STREAM_INTERRUPTED` error,中断不再伪装成完整回答;③ `mock/db.ts` `pickDocs` 只取 `ready` 文档、种子 `doc-0004` 4s 收敛到 ready(文档页轮询可终止)、新增 `buildAnswerWithTrace` 保证回答与溯源同池;④ `mock/sse-writer.ts` 改用 `buildAnswerWithTrace`;⑤ `views/ChatView.vue` / `TraceView.vue` 问题文本改走 sessionStorage,不再进 URL(旧 `?q=` 链接仍兜底可用);⑥ `scripts/verify-mock.sh` `TMP` 前置初始化、`scripts/wsl-build.sh` 开 `pipefail`;⑦ `package-lock.json` `source-map-js` 升 1.2.2(CVE-2026-93749) |
| 本仓库内的新增/改动 | 见下表;**2026-10-11 业主裁定:web 端不复用 harness 架构,harness 四页已整体移除**(见文末) |

## 相对上游基线的改动(Issue #52 · M1)

| 文件 | 改动 |
|---|---|
| `src/router/index.ts` | 新增 `/dashboard` 路由(`meta.public` 放行登录守卫,守卫加一个条件);既有四条路由未动 |
| `src/App.vue` | `showChrome` 排除 `/dashboard`(大屏全屏沉浸、自带顶栏),一行 |
| `src/mock/index.ts` | 开头加 `handleTraffic` 转发(约 6 行),traffic 路径不匹配时仍走原 404 |
| `src/shared/traffic.ts` `src/shared/demoNetwork.ts` | 新增:契约 v2.0 类型 + 四级编码 + 示例路网(非实测) |
| `src/api/traffic.ts` | 新增:traffic 只读调用面(与 harness 冻结 8 端点的 `api/index.ts` 相互独立) |
| `src/mock/traffic.ts` | 新增:traffic mock(端点清单见 `work/assembly/README.md` 第二节,实现基准 = PR #51 分支上的 `work/assembly/traffic.py`)+ `traffic_snapshot` SSE 假流 |
| `src/views/dashboard/` | 新增:态势大屏页(左栏路段/线路 · 中央 SVG 路网 · 右栏详情) |

真路网由 #36(`netbuild.py` → `sumo/*.net.xml`)与 #37(`map_ingest.py` → `network.json`)落地后替换 `src/shared/demoNetwork.ts`。

## 2026-10-11 harness 架构移除(业主裁定:web 端不复用 harness 架构,后端按前端页面重新规划)

| 类别 | 内容 |
|---|---|
| 整体移除 | harness 四页(`views/LoginView.vue` / `ChatView.vue` / `DocumentsView.vue` / `TraceView.vue`)、冻结 8 端点调用面(`api/index.ts` / `api/upload.ts` / `api/sse.ts`)、harness mock 数据与假流(`mock/db.ts` 及 `mock/sse-writer.ts` 假流编排)、登录态(`stores/auth.ts`)、harness 协议类型(`shared/protocol.ts`) |
| 裁剪 | `api/http.ts` 去 Bearer/401 处置;`router/index.ts` 去登录守卫,仅存 `/dashboard`(根路径重定向);`App.vue` 去管理台壳与 health 轮询,仅存路由出口;`mock/index.ts` 仅存 traffic 转发;`mock/util.ts` 去鉴权/上传解析工具;`mock/sse-writer.ts` 仅存 `SseWriter`(traffic SSE 假流复用);`vite.config.ts` 去 `VITE_MOCK_ERROR` 注入;`scripts/verify-mock.sh` 重写为 traffic 冒烟 |
| 不变 | traffic 调用面(`api/traffic.ts`)与 traffic mock、`shared/traffic.ts` / `demoNetwork.ts`、态势大屏页面;上游仓零改动 |
