# 来源说明(工程落位留痕)

本目录 = 上游仓 `agentic-traffic-management/harness-core/ui-vue` 的**整体拷贝**(Issue #52,2026-10-11),作为 hubflow 一期管理端的开发基线。上游仓保持零改动。

| 项 | 值 |
|---|---|
| 来源仓库 | `YONEK0/agentic-traffic-management`(本地 `D:\work\agentic-traffic-management`) |
| 基线 | `main` 分支 commit `356361d`;工作树相对该 commit 仅有 `package-lock.json` 一处未提交修改(随拷贝带入)与若干 docs 层未提交删除(与本工程无关,未拷贝) |
| 拷贝排除 | `node_modules/`、`dist/`、`.env`(门禁禁入名单;内容只是 `VITE_USE_MOCK=1` 开关,缺省行为见 `.env.mock`) |
| 拷贝后修改 | `tsconfig.app.json` / `tsconfig.node.json` 去掉 JSONC 注释(仓库门禁对受管 JSON 做严格解析,注释会报红;编译行为不变) |
| 本仓库内的新增/改动 | 见下表,harness 四页(登录/问答/文档/溯源)原样保留 |

## 相对上游基线的改动(Issue #52 · M1)

| 文件 | 改动 |
|---|---|
| `src/router/index.ts` | 新增 `/dashboard` 路由(`meta.public` 放行登录守卫,守卫加一个条件);既有四条路由未动 |
| `src/App.vue` | `showChrome` 排除 `/dashboard`(大屏全屏沉浸、自带顶栏),一行 |
| `src/mock/index.ts` | 开头加 `handleTraffic` 转发(约 6 行),traffic 路径不匹配时仍走原 404 |
| `src/shared/traffic.ts` `src/shared/demoNetwork.ts` | 新增:契约 v2.0 类型 + 四级编码 + 示例路网(非实测) |
| `src/api/traffic.ts` | 新增:traffic 只读调用面(与 harness 冻结 8 端点的 `api/index.ts` 相互独立) |
| `src/mock/traffic.ts` | 新增:traffic mock(端点形状照抄 `work/assembly/traffic.py`)+ `traffic_snapshot` SSE 假流 |
| `src/views/dashboard/` | 新增:态势大屏页(左栏路段/线路 · 中央 SVG 路网 · 右栏详情) |

真路网由 #36(`netbuild.py` → `sumo/*.net.xml`)与 #37(`map_ingest.py` → `network.json`)落地后替换 `src/shared/demoNetwork.ts`。
