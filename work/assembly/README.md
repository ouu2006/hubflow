# work/assembly · 接口与总装（开发C）

> ⚠️ **2026-10-11 业主裁定（推翻前述接口规划）**：web 端整体推翻 harness 架构，后端接口面改为**根据前端页面重新规划**后再落地。本文件第二节的端点清单、"既有 8 个端点零改动"边界与"PR #51 实现基准"**作废待重订**（PR #51 已收回，traffic.py 骨架可在该 PR 页面回看）；重订前第二节仅作历史参考。

> **产出**：接口层 `traffic.py` + **一键演示 `demo_all.py` / `demo_all.ps1`（C-4）** + **压测 `stress_test.py` + `压测报告.md`（C-5）** + **对外接口 `对外接口.md`（C-6）** + **`部署与监控.md` / `monitor_check.py`（C-7）** + 启动脚本 `run_all.py`
> **同时负责**：**公共文件的唯一修改人**（根 `README.md`、`.gitignore`、`.gitee/`、`docs/数据契约.md`、路由注册）
> **注意**：这里登记的是**公共文件由开发C 改、队长复核**，不是"开发C 想怎么改就怎么改"。

## 一、负责什么

1. **接口层** `traffic.py`：演示前最后一步，把快照文件（`segments.json` / `routes.json` / `vehicles.json`）包成 HTTP 接口给双端调用；
2. **一键演示脚本**（C-4）：`demo_all.py`（`demo_all.ps1` 双击/命令行均可）一条命令完成环境检查 → 真网算路 → 感知链路 → 起接口层 → 端点自检 → 收尾；`--rounds 3` 即 **M1-6 无人干预连跑 3 轮**，每轮日志/产物/内存留存，**失败即停、缺前置如实标阻塞**；
3. **公共文件**：根目录 `README.md`、`.gitignore`、`.gitee/`、`docs/数据契约.md`、`app/main.py` 注册与路由表 —— **只由你一人改，队长复核**；
4. **压力测试**（C-5）：`stress_test.py` 3 轮 × 多并发打只读端点，记录启动耗时 / P50·P95 / 错误数 / 内存曲线，报告写实测数字、**不判定"性能达标"**；交付文档见 C-6 [`对外接口.md`](对外接口.md) / C-7 [`部署与监控.md`](部署与监控.md)。

## 二、接口层（演示前最后一步）

**一期主链路不依赖 HTTP**（文件快照当契约）。这一层**只读快照，不写快照**——它不产生任何数据，只把已经落盘的结果端出去。

> **2026-10-12 重订（Issue #78）**：管理端四页按 Ardot 设计稿整体重做，接口面**已按页面重新规划完成**（2026-10-11 裁定的落地动作）。
> 下表即**重订后的接口面**。**前端已全部接通、`src/mock/traffic.ts` 已实现**；**后端按本表实现即可**，
> 字段形状以 [`../frontend/README.md`](../frontend/README.md) §10.3 与 `work/frontend/ui-vue/src/shared/traffic.ts` 的类型定义为准（**两者是同一份口径**）。

| 端点 | 方法 | 用途 | 状态 |
|---|---|---|---|
| `/api/traffic/segments` | GET | 路段级指标与等级列表 | **已实现**（IKMF1T） |
| `/api/traffic/segments/{id}` | GET | 单路段详情（含 `factors_applied` / `pred`） | **已实现**（IKMF1T） |
| `/api/traffic/segments/{id}/sources` | GET | **同一路段 `video` / `twin` 并排 + 差值（TC-19 展示侧）** | **已实现**（IKMF1T） |
| `/api/traffic/vehicles` | GET | 一期演示：孪生车辆位置（读 `vehicles.json`）。**二期下线** | 沿用（已实现；缺产物时空列表 + note） |
| `/api/traffic/route/recommend` | POST | 请求推荐（请求体含 `session_id` / `location`） | **已实现**（IKMF1T；IKMS17 起真网产物优先） |
| `/api/traffic/locate` | POST | 定位 → 路段。一期由孪生真值调用，二期由 App 调用 | 已实现（读引擎产物 `requests[].location`，不做地图匹配） |
| `/api/traffic/factors` | GET | 当前生效因素清单（`?segment_id=` 过滤） | 沿用 + 扩参（已实现；IKMS17 起含写端点内存态） |
| `/api/traffic/factors` | POST | 人工置位（F07 / F08 / F11，手册第 19 章） | **已实现**（IKMS17；内存态、重启复位、**不重算判级**） |
| `/api/traffic/factors/reset` | POST | 清空人工置位 | **已实现**（IKMS17；内存态复位） |
| `/api/traffic/assimilation` | GET | 数据同化状态（`counts` + 每条 `role` / `point_code` / `name` / `reason`） | 沿用 + 扩字段（已实现） |
| `/api/traffic/meta` | GET | 站点 / 数据源 / 页签 / 常驻口径角标 | **已实现**（IKMF1T；IKMS17 起带 `data_sources` 角标） |
| `/api/traffic/overview` | GET | 全网 KPI（均速 + 环比 / 最堵路段 / 在途·已引导·采纳率 / 生效因素数 / 等级分布） | **已实现**（IKMF1T） |
| `/api/traffic/network` | GET | 路网几何 + 断面（边界 / 内部）+ 落客点 + 场区 + 站点 | **已实现**（IKMF1T） |
| `/api/traffic/alerts` | GET | 告警列表（四态 + `triggered_by` + 首次观测时间 + 回执 / 回写留痕） | **已实现**（IKMF1T 由快照派生；**IKMS1H 起读持久化后的运行态**） |
| `/api/traffic/plan/dispatch` | POST | 下发分流方案（渠道 + 比例）→ 回执 | **已实现**（**IKMS1H 起 JSON 文件仓持久化**，重启不复位；审计可查） |
| `/api/traffic/plan/ack` | POST | 处置回写（认领人 / 动作 / 结果四选一）→ 状态流转 | **已实现**（**IKMS1H 起 JSON 文件仓持久化**，重启不复位；审计可查） |
| `/api/traffic/plan/audit` | GET | 处置闭环审计（只读**辅助端点**，非契约端点；`?limit=1..1000&alert_id=`，`total` 为未截断匹配总数） | **已实现**（IKMS1H；按 seq 返回 dispatch / ack / reset 记录） |
| `/api/traffic/predict` | GET | 预测：`?segment_id=&h=15`。一期 **L0**，不报精度数字 | **已实现**（IKMF1T；无 pred 产物时空点 + note） |
| `/api/traffic/thresholds` | GET | 判级阈值 + CI 四项加权构成 + 变更留痕（只读，P1） | **已实现**（IKMF1T；读 `stations/thresholds.json`） |
| `/api/traffic/heat-matrix` | GET | 路段 × 时间热力矩阵（`?window=&bucket=`） | **已实现**（IKMF1T；只回当前快照桶，其余 null 灰格） |
| `/api/traffic/ci-history` | GET | 单路段 CI 走势（`?segment_id=&points=`） | **已实现**（IKMF1T；无时序历史，只回单点） |
| `/api/traffic/context` | GET | **环境上下文**：天气 / 时间 + 折算出的因素（F01 / F02 / F03 / F10） | **已实现**（IKMS17；含场景注入内存态） |
| `/api/traffic/scenario` | POST | **场景注入**（天气 / 时段 / 需求倍率）→ 折算因素 | **已实现**（IKMS17；内存态、**effects 如实为空**、不重算判级） |
| `/api/traffic/scenario/reset` | POST | 清场景注入（与 `factors/reset` 同口径） | **已实现**（IKMS17；内存态复位） |
| `/api/traffic/report/compare` | GET | 效果对比报表 | 空壳 + note（接口层无报表产物；前端已接，rows 空时如实提示） |
| `/perception-api/streams/{sid}/summary` | GET | 感知通道汇总（分车型 / 轨迹质量与标定 / 输出字段 / 处理口径） | **未实现**（属感知面，见 [`../perception/README.md`](../perception/README.md)；前端显示「—」并注明） |

**2026-10-13 页面收敛（Issue #77）后的接口面变化**：管理端 Web 由四页收敛为**三层 3 页**（感知层 / 决策层 / 监控大屏，
详见 [`../frontend/README.md`](../frontend/README.md) 第十三节）。接口面**只增不改**——上表三个 `context` / `scenario` 端点是本单新增，
**存量端点形状一字未动**。口径两条：

1. **环境数据是编造的演示值**（真实气象 / 列车数据拿不到），响应带 `is_simulated = true` 信封，页面标「演示数据（模拟）」，
   **不得称实测**；字段口径对齐手册第 19 章因素登记表（F01 / F02 / F03 / F10）。
2. **场景注入 ≠ 人工置位**——手册 §:2222 的人工置位口子只有 F07 / F08 / F11（走 `POST /api/traffic/factors`）；
   `POST /api/traffic/scenario` 是**环境侧**注入口，**后端实现时须把两者分开留痕**（谁在什么时候把环境改成了什么）。

**约定**：`is_simulated` 字段在**每一个**响应里出现；事件流复用现有 SSE 形状，**新增**事件名，**不改既有事件名**；**一期是非视频端点驱动的页面**——**视频感知链路**（YOLO 跑样本视频，`source: "video"`）**一期就在跑**，但它的结果以 `segments` 快照的形式进接口层（**不新增视频流 / 画面端点**）。`/api/traffic/segments` 与 `/segments/{id}` 必须能按 `source` **并排返回 `video` / `twin` 两个来源**（**TC-19 的展示侧**，页面用 `/segments/{id}/sources` 取并排对）。

**写接口的留痕要求（已落地，见 §2.2）**：`plan/dispatch` 与 `plan/ack` 是接口面里**仅有的两个处置状态写入**，
前端已按「回执 + 回写留痕」展示（渠道、比例、认领人、动作、结果四选一、时间）。**IKMS1H 起**这两个端点与
`GET /alerts` / `POST /alerts/reset` 共用一份**持久化运行态**（JSON 文件仓，重启不复位）并追加式写审计，
决策层的「处置闭环」可跨页面 / 跨重启举证；仍是**演示态、无真实下发通道**。

**前端当前降级说明**（后端未实现前的如实表现，不要当成 bug）：
① 六路样本视频只有 `road2` / `track1` 已导出，其余显示「未导出」；② 越线计数 / 平均 Q / SVR / 标定 RANGE-RMSE
由感知服务提供，`/summary` 未实现时前端显示「—」并注明出处，**不用推算值冒充**。

### 2.1 接真接口（IKMS17，2026-10-18）：三页已切 `traffic.py`、补写端点、真网路线优先

**前端开关**：`npm run dev`（`VITE_USE_MOCK=1`）仍是 mock 演示；`npm run dev:remote`
（`--mode remote` → `.env.remote` 的 `VITE_USE_MOCK=0`）三页全部走 vite 代理到本文件服务：

```bash
# 终端 1：接口层（本目录）
python work/assembly/traffic.py --port 8000
# 终端 2：感知服务（可选，感知页视频需要；数据目录用样本导出产物）
python work/perception/server.py --port 8101
# 终端 3：前端 remote 模式
cd work/frontend/ui-vue && npm run dev:remote    # http://localhost:5173/#/dashboard
```

**写端点（factors / scenario 一期：进程内存态，重启复位；不落库、不写快照、不重算判级）**：

> 处置闭环写端点（`plan/dispatch` / `plan/ack` / `alerts/reset`）自 **IKMS1H** 起已改为持久化，见 [§2.2 处置闭环持久化](#22-处置闭环持久化ikms1h2026-10-18下发--回执--回写落盘重启不丢)。

| 端点 | 入参（与 mock 同形） | 行为 | 响应口径 |
|---|---|---|---|
| `POST /api/traffic/factors` | `{segment_id, factor_id, name?, target, multiplier}`，`factor_id` 限 **F07 / F08 / F11** | 校验路段/因素/目标/倍率 → 覆盖式登记到内存 | `applied:true` + `level_recomputed:false` + `note`；`level/level_name` 是**当前快照原值（注入前）**，不是注入后判级 |
| `POST /api/traffic/factors/reset` | — | 清空人工置位（幂等） | `{reset:true, cleared:N, note}` |
| `POST /api/traffic/scenario` | `{weather?, session?, demand_mult?, segment_id?}`；**缺省 = 不改，显式 null = 清除** | 只更新环境状态 → 折算 F01/F02/F03/F10 | `applied:true` + `factors` + `effects:[]` + `recomputed:false` + `note`（接口层不伪造注入前后判级对照） |
| `POST /api/traffic/scenario/reset` | — | 清空场景注入（幂等） | `{reset:true, was_injected:bool, note}` |

- **两个口子不混用**：人工置位只有 F07/F08/F11；F01/F02/F03/F10 属环境侧，只走 `/scenario`。
- **接口层不重算 level / ci**（判级唯一实现是感知层 `level.py`）：写端点只更新 `context` /
  `derived_factors` / 因素状态；`GET /factors`、`GET /segments` 里登记的因素带
  `injected:true, pending_recompute:true`，**不伪造等级变化**。复位方式：factors / scenario 走三个
  `POST *reset` 或重启进程（内存态）；处置闭环运行态见 §2.2（持久化，重启不丢，复位走
  `POST /alerts/reset` 或 `--reset-state`）。
- 所有响应恒带 `is_simulated:true`；参数不合法 400（`FACTOR_INVALID` / `SCENARIO_INVALID`）、
  路段不存在 404、未注册路径/方法 404（统一信封）——不静默吞路径。

**路线数据源优先级（`route/recommend` / `locate`）**：

| 优先级 | 产物 | 段号命名空间 | 响应角标 |
|---|---|---|---|
| ① | `work/engine/out/real/routes.json`（IKMS11 真网算路） | `SZ-###` | `data_source: engine.routes.real`；响应头 `X-Traffic-Data-Source: engine.routes.real` |
| ② | `work/engine/out/routes.json`（7 节点样例网，仅回退） | `SEG-###` | `data_source: engine.routes.sample` |

- 给了 `session_id` 逐层严格匹配；**全层都没有该 session** 时端出最高优先级产物首条请求作演示路线，
  响应带 `session_matched:false` + `note`（写明「非该车行程」），页面显式提示；不静默当匹配。
- 两层的段号命名空间不同：响应给 `segment_namespaces` / `segments_not_in_snapshot`，
  **不把路线 ETA 与路段快照指标混算**；地图只画站点包几何里存在的段。
- 两层产物都缺失 → 如实 404 `ROUTE_UNAVAILABLE` + note（不代算 ETA）。

**自检（真跑命令）**：

```bash
python work/assembly/traffic.py --check            # 数据源 / 路线优先级 / 处置运行态(持久化)摘要
python work/assembly/selfcheck_ikms1h.py           # IKMS1H 自检：重启持久化 / 幂等 / 顺序 / 终态 / 复位 / 审计 / 跨页
curl -s http://127.0.0.1:8000/api/traffic/meta     # 响应头 X-Traffic-Data-Source
curl -s http://127.0.0.1:8000/api/traffic/alerts   # 读持久化后的告警四态
curl -s -X POST http://127.0.0.1:8000/api/traffic/plan/dispatch -H "Content-Type: application/json" \
     -d '{"alert_id":"<GET /alerts 里的一条>","channel":"情报板","ratio_pct":30,"operator":"值班员A"}'
curl -s -X POST http://127.0.0.1:8000/api/traffic/plan/ack -H "Content-Type: application/json" \
     -d '{"alert_id":"<同一条>","operator":"值班员A","action":"分流","result":"已缓解"}'
curl -s "http://127.0.0.1:8000/api/traffic/plan/audit?limit=10"   # 审计留痕
curl -s -X POST http://127.0.0.1:8000/api/traffic/alerts/reset    # 演示复位（留痕）
```

> 注：本单不改 `selfcheck_ikmf1t.py`。该脚本仍按 IKMF1T 当时的口径断言
> `POST /factors`、`/scenario`、`/scenario/reset` 是 404（"unimplemented"）；IKMS17 已把它们实现为
> 内存态端点，**这三条断言已过时**；IKMS1H 又给 `/alerts` 信封加了 note、写端点加了持久化字段，
> 该脚本的对照结果会如实记差异但不作为本单证据。IKMS1H 的自检走 `selfcheck_ikms1h.py`（**独立运行态文件，
> 不污染演示态**），证据见 `自检记录-IKMS1H.md`。

### 2.2 处置闭环持久化（IKMS1H，2026-10-18）：下发 / 回执 / 回写落盘、重启不丢

**一句话**：`plan/dispatch` → `plan/ack` → `GET /alerts` 的运行时状态不再只活在进程内存里，而是落盘到
`work/assembly/data/dispatch.json`；停服务 / 重启后状态、回执、回写留痕、审计都还在，大屏与决策页读到**同一份状态**。

**选型：JSON 文件仓（不是 SQLite）**：

| 判据 | 取舍 |
|---|---|
| 进程模型 | 一期是单进程演示后端（uvicorn 单 worker），没有并发写库 / 多进程事务需求 |
| 依赖 | `json` / `os.replace` / `fsync` 都是 stdlib，零新依赖；文件人能直接读 / diff / 备份（演示前删一个文件即回初始态） |
| 数据量 | 几条告警 + 审计上限 1000 条，一次全量读写 < 1 ms，不需要索引 / 事务 |
| 崩溃安全 | 写临时文件 + `os.replace` 原子替换 + `fsync`，不会留半截 JSON；坏文件 / 旧 schema 改名留证（`*.corrupt-<时间>`）后按初始态启动 |
| 迁移 | 二期换 SQLite / openGauss 只替换 `DispatchStore` 一类，端点形状与审计字段不变 |

**位置与拦截**：`work/assembly/data/dispatch.json`（**不入库**）。同目录 [`data/.gitignore`](data/.gitignore)
只放行它自己，`dispatch.json` 被忽略；`.db` / `out/` 运行态与自检测试数据同样不提交。

**schema（`schema_version: 1`）**：

```json
{
  "schema_version": 1,
  "is_simulated": true,
  "note": "演示态、无真实下发通道；运行态随本文件持久化（重启不复位）",
  "updated_at": "2026-10-18T13:46:41+08:00",
  "alerts": {
    "<alert_id>": {
      "status": "已闭环",
      "segment_id": "SZ-005",
      "channels": ["情报板"],
      "dispatch_at": "2026-10-18 13:46:38",
      "dispatch_ratio_pct": 30,
      "dispatch_operator": "值班员A",
      "dispatch_audit_seq": 1,
      "writeback": {
        "operator": "值班员A",
        "action": "分流",
        "result": "已缓解",
        "at": "2026-10-18 13:46:41",
        "audit_seq": 2
      }
    }
  },
  "seed_dispatch": {},
  "audit": [
    {
      "seq": 1,
      "at": "2026-10-18 13:46:38",
      "action": "dispatch",
      "alert_id": "AL-...",
      "segment_id": "SZ-005",
      "channel": "情报板",
      "ratio_pct": 30,
      "operator": "值班员A",
      "result": null,
      "status_after": "处置中"
    }
  ],
  "audit_seq": 2,
  "audit_total": 2,
  "reset_count": 0
}
```

**写操作语义（与 mock 同一套状态机，差异只在持久化 / 审计）**：

| 场景 | 行为 |
|---|---|
| 首次下发 | 200 回执（渠道 / 比例 / 时间 / 操作者）+ 状态「处置中」；追加 `dispatch` 审计 |
| 同告警 + 同渠道 + 同比例重复下发（回写前） | 200 `idempotent:true`，沿用首次回执时间；**不重复写审计** |
| 无下发回执直接回写 | 409 `ACK_NO_DISPATCH`（TC-07 闭环顺序） |
| 回写四选一 | 已消除 / 已缓解 → 已闭环；未改善 → 处置中；误报 → 误报；追加 `ack` 审计 |
| 同人 + 同动作 + 同结果重复回写 | 200 `idempotent:true` 回放既有回执；不重复写审计 |
| 终态（已闭环 / 误报）再下发或换结果回写 | 409 `ALERT_TERMINAL`，不可翻转 |
| 复位 `POST /alerts/reset` | 清运行态 → 重放 `seed_dispatch`（接口层默认空 → 全部回「待认领」）+ 写一条 `reset` 审计 |
| 落盘失败 | 500 `PERSIST_FAILED` + note；内存与磁盘都保持旧状态（不假成功） |
| 并发状态变化 | 端点先在锁外校验，`DispatchStore` 在写锁内**再复查一次**终态 / 下发回执：并发下若状态已变（例如另一请求刚把告警改成终态、或刚 reset），返回 409 `ALERT_TERMINAL` / `ACK_NO_DISPATCH`，**不落盘、不写审计**、不改内存 |

**审计（TC-07 / 效果对比可引用）**：`GET /api/traffic/plan/audit?limit=&alert_id=`（只读**辅助端点**，非契约端点）
按 `seq` 返回 dispatch / ack / reset 记录。语义：

- `limit` 允许 **1..1000**（默认 50，与运行态文件保留上限 `DISPATCH_AUDIT_MAX=1000` 一致；超出按上限夹取）；
- 响应里 `records` 是最近 `limit` 条；**`total` 是过滤后未截断总数**（`?limit=2` 时 `total` 仍可能是 4），
  `returned` 是本次返回条数，`limit` 是生效上限，`audit_total` 是累计追加总数（单调递增，不受文件保留上限影响）；
- 字段：`seq / at / action / alert_id / segment_id / channel / ratio_pct / operator / operator_action(ack) / result / status_after`。

**seed 与复位**：接口层没有站点包预置下发剧本（mock 的 `seedDispatch` 在前端站点包 TS 里，搬到后端等于伪造回执），
所以默认 `seed_dispatch = {}`；需要预置演示态时在运行态文件的 `seed_dispatch` 里声明，再 `POST /alerts/reset`
或 `python work/assembly/traffic.py --reset-state` 重放（复位本身留一条 `reset` 审计）。

**迁移 / 清理**：

- 回初始态（留审计）：`POST /api/traffic/alerts/reset` 或 `python work/assembly/traffic.py --reset-state`；
- 全清（含审计）：停服务 → 删 `work/assembly/data/dispatch.json` → 重启（首次写入时重建，含 `seed_dispatch`）；
- 换 schema：升 `schema_version` 并在本节写迁移说明；旧版本 / 坏文件会改名留证（`*.corrupt-<时间>`）后按初始态启动；
- 换路径：`--state-path work/assembly/out/xxx.json`（相对路径按仓库根解析；自检用它做隔离）。
  **安全校验**：只允许 `work/assembly/data/` 或 `work/assembly/out/` 下的 `.json`——误传已跟踪文件
  （如 `README.md`）、非 `.json`、或其它目录（如 `docs/`）会直接报错退出（退出码 2），
  **不会对目标文件做改名 / 覆盖**。

**与前端同源 / 演示态边界**：

- 决策页与大屏都调同一套 `src/api/traffic.ts` 函数（`getTrafficAlerts` / `postPlanDispatch` / `postPlanAck`），
  所以同一后端状态在页面切换 / 刷新后一致；**本单不改前端**。
- **演示态、无真实下发通道**：渠道只是展示枚举（情报板 / 导航软件推送 / 现场调度 / 广播），回执只是
  「已确认」的演示回执，**不得**说成已通知司机 / 情报板；所有写端点响应 `is_simulated:true` + note。
- 一期范围：**一进程一 JSON 文件仓**；多 worker / 真实落库（openGauss）归二期。

**完成判定对照（TC-07 等）**：

| 条目 | 怎么验 | 证据 |
|---|---|---|
| TC-07 | 下发 → 回执 → 回写状态可推进；四项留痕；停服务重启后仍在 | `selfcheck_ikms1h.py` 第 3~7 步真跑重启 |
| 开发规范 §7（幂等） | 同操作重复提交幂等（回执时间不变、审计不重复） | 第 3 / 6 步断言 |
| 本单专属一（前置校验） | 无回执回写 409；终态不可翻转 | 第 2 / 6 步断言 |
| 本单专属二（跨页共享） | 大屏 / 决策页同一后端状态（API 层两次读一致 + 源码同源引用） | 第 9 步 + 前端源码引用 |
| 本单专属三（可复位） | reset / `--reset-state` 回明确初始态并留痕 | 第 8 步断言 + 审计 |
| 独立审查修复 | 终态并发不变量（锁内复查）/ 审计 `limit` 与 `total` 语义 / `--state-path` 路径安全 | `selfcheck_ikms1h.py` 审查修复断言 + 自检记录第四节 |

**自检（真跑命令）**：

```bash
python work/assembly/selfcheck_ikms1h.py       # 一键：重启持久化 / 幂等 / 顺序 / 终态 / 复位 / 审计 / 跨页 / doc_gate
python work/assembly/traffic.py --check        # 看运行态文件与审计摘要
python work/assembly/traffic.py --reset-state  # 复位运行态（留审计；不起服务）
```

> 证据：`work/assembly/自检记录-IKMS1H.md`（真跑断言表 + 重启前后 JSON + 审计全量）；运行态文件与 `out/`
> 测试数据均被 gitignore，不入库。

### 2.3 交付包索引（C-4 ~ C-7，IKMS1I，2026-10-18）

> 手册附录 B.3 的四件交付物已落地。**全部为演示数据（模拟）口径**：不接真实下发通道、无真实用户数据；
> 缺前置（真网产物 / 感知样本导出 / 前端 dev server）时脚本**如实标阻塞，不写「通过」**。

| 交付物 | 文件 | 一条命令 / 怎么用 | 判定口径 |
|---|---|---|---|
| **C-4 一键演示** | [`demo_all.py`](demo_all.py) · [`demo_all.ps1`](demo_all.ps1) | `python work/assembly/demo_all.py --rounds 3`（Windows 也可 `demo_all.ps1 --rounds 3`） | 环境检查 → 真网算路 → 感知链路 → 接口层 → 端点自检；每轮日志在 `out/demo/round-<n>/`，汇总 `out/demo_all_report.json`；退出码 0=全成功 / 2=有阻塞 / 1=有失败 |
| **C-4 证据** | [`自检记录-IKMS1I.md`](自检记录-IKMS1I.md) | 见该文件「M1-6 三轮」一节 | 三轮逐轮结果 / 耗时 / 内存 / 阻塞项如实记录 |
| **C-5 压测** | [`stress_test.py`](stress_test.py) · [`压测报告.md`](压测报告.md) | `python work/assembly/stress_test.py` | 3 轮 × 14 只读端点 × 20 次 × 8 并发；实测启动耗时 / P50·P95 / 错误数 / RSS；**不判定性能达标** |
| **C-6 对外接口** | [`对外接口.md`](对外接口.md) | 直接阅读 | 端点表（27 条，`/plan/audit` 标非契约）/ 请求响应示例 / 信封 / 鉴权形状 / **围栏衔接** / 错误码表 / 演示环境声明 |
| **C-7 部署与监控** | [`部署与监控.md`](部署与监控.md) · [`monitor_check.py`](monitor_check.py) | `python work/assembly/monitor_check.py` | 单机部署步骤 / 端口 / 守护 / 日志 / 回滚 + 监控项清单（数据·服务·效果分层，一期/二期标注） |

## 三、一键演示与压测（C-4 / C-5）

**一条命令演示（C-4）**——环境检查 → 真网算路 → 感知链路 → 起接口层 → 端点自检 → 收尾：

```bash
# 1 轮（彩排）
python work/assembly/demo_all.py
# M1-6：无人干预连跑 3 轮（每轮日志/产物/内存都留存；失败即停，不隐藏）
python work/assembly/demo_all.py --rounds 3
# Windows 双击或 PowerShell 入口（参数原样透传）
powershell -ExecutionPolicy Bypass -File work/assembly/demo_all.ps1 --rounds 3
# 只验接口层（真网/感知前置缺失时也能跑）
python work/assembly/demo_all.py --skip-engine --skip-perception
```

| 参数 | 作用 |
|---|---|
| `--rounds N` | 连跑轮数（默认 1；M1-6 用 3） |
| `--with-perception-server` | 额外起感知服务 :8101（样本数据在场时） |
| `--skip-engine` / `--skip-perception` | 跳过对应上游步骤（缺前置时如实标阻塞） |
| `--keep-going` | 某轮失败后仍跑完剩余轮次（默认失败即停） |
| `--json-report <path>` | 汇总报告路径（默认 `work/assembly/out/demo_all_report.json`，gitignored） |

- 每轮目录：`work/assembly/out/demo/round-<n>/`（`engine-real.log` / `perception-chain.log` / `traffic-server.log` 等）；
- 汇总报告与**退出码**：`0` 全部步骤成功；`2` 跑完但有阻塞项（**如实记录，不算 M1-6 通过**）；`1` 有失败 / 异常；
- **不伪造成功**：感知链路在缺 `work/perception/data/monitor/` 样本导出时会「0 通道产出」——
  脚本把这种「命令退出码 0 但产物为空」判为**阻塞**并写明原因（照 README 第五节的产物存在性纪律）。

**压测（C-5）**——3 轮 × 多并发打只读端点，记录启动耗时 / P50·P95 / 错误数 / 内存曲线：

```bash
python work/assembly/stress_test.py
# 自定义：python work/assembly/stress_test.py --rounds 3 --concurrency 8 --requests-per-endpoint 20
```

- 报告：[`压测报告.md`](压测报告.md)（每次运行重写；写**本机实测**环境与数字，**不给「性能达标」结论**）；
- 原始数据：`work/assembly/out/stress_test_report.json`（gitignored）；
- 只压只读 GET 端点（写端点会改持久化运行态，另见 §2.2 与 `自检记录-IKMS1H.md`）。

**监控自检（C-7）**：

```bash
python work/assembly/monitor_check.py            # 进程 / 端口 / 数据陈旧 / 5xx / 磁盘 / 持久化文件
```

> 历史说明：早期 README 列的 `demo.bat` / `stress.py` 是**计划中的脚本名**，仓库里一直没有这两个文件；
> 本单落地为 `demo_all.py`（C-4）与 `stress_test.py`（C-5），旧的 `run_all.py` 仍保留（只起接口层，可选感知服务）。

## 四、硬性边界

- **既有 8 个端点零改动**：`app/main.py` 的 diff **只包含"新增注册"**；
- **公共文件只你改**，其他人只提 Issue；**改完队长复核**；
- **契约字段**（`segments` / `routes` / `vehicles`）的裁定人是**开发B**，你只改文件、不裁定字段；
- 视频、权重、图片数据集**不进仓库**；
- **一期就有视频链路**（D1′）：YOLO 跑 6 段真实样本视频 → 透视标定 → 四项指标，`source: "video"`，**可以做"视频识别正在算路段拥堵"的表述**；但必须同时讲清**视频是样本视频、非本站现场**，接口层与页面**不得**把它说成"现场实测"、**不得**把孪生算出来的数说成实测（口径见 [`../../docs/全流程计划.md`](../../docs/全流程计划.md) 第 1 节）。

## 五、⚠️ 产物存在性断言（**别只信退出码**）

```text
每一步跑完，先断言"产物文件真的存在且不是 0 字节"，再看退出码。
```

理由：**这类"命令报成功、产物根本没生成"的假通过已实测复现过**——**验收时看不出来，比报错更危险**。

`run_all.py` / `stress.py` 里必须做的断言：

- [ ] `segments.json` / `routes.json` / `vehicles.json` 存在且非空；
- [ ] `ts` 字段是**本次运行**的时间戳（不是上一轮的残留文件）；
- [ ] 时序输出的统计点数满足门槛（**M1-2：≥ 60 个统计点**）；
- [ ] 接口层起来后能 `GET /api/traffic/segments` 拿到数据；
- [ ] **每一次运行前先清空 / 隔离输出目录**，否则上一轮的产物会让"假通过"看起来像真的通过。

## 六、⚠️ 两个已知缺陷（**仍在，演示脚本必须先绕过**）

2026-10-09 执行 0-1~0-4 时发现，详见 [`现状核实.md`](现状核实.md) 第 4.3 节：

| # | 缺陷 | 绕过办法 |
|---|---|---|
| 1 | **OpenCV 不支持中文绝对路径**——`cv2.imwrite` / `cv2.imread` 传中文绝对路径直接失败，而 `image` 模式的输出目录由 `REPO_ROOT` 拼出，**必为中文绝对路径** | ① 把两个仓库放到同一纯英文路径下、上游与本仓库同级（**推荐**，根因消除）；或 ② 写出改 `cv2.imencode` + `open(...,'wb')`、读入改 `np.fromfile` + `cv2.imdecode` |
| 2 | **`track` / `count` 的输出目录不存在时静默失败**——`_write_frames()` 既不 `makedirs` 也不检查 `isOpened()`，**命令照样打印"轨迹条数: 9"但视频文件根本没生成** | `run_all.py` 里先 `os.makedirs(..., exist_ok=True)`；**压测脚本里加一条"产物文件存在性"断言**，别只信退出码 |

> **一期口径（D1′）**：这两个缺陷正好落在**视频感知链路**上——**一期就要跑视频（6 段样本视频 + YOLO），所以一期必须先处理**：
> ① **中文路径**：仓库与上游**已迁到纯英文路径**（两仓同级），根因消除；代码层 `imencode + imdecode` 作为二期加固项；
> ② **输出目录静默失败**：`run_all.py` 与演示脚本**先 `os.makedirs(..., exist_ok=True)`**，并加"产物存在性断言"——**别只信退出码**。
> 这条纪律**两条链路都照用**（孪生输出、快照文件、时序数据都会出现同类假通过）。

## 七、硬前置与上游资产（**状态已按 V2.0 更新**）

**0-1 ~ 0-3 已完成**（2026-10-09）：`.ckpt` 已生成（`yolov8n.ckpt`，12.7 MB）并通过前向数值比对（最差相对误差 2.875e-06）；环境已按 `requirements-mindspore.txt` 重建（CPython 3.11.17 + MindSpore 2.8.0）。

> **按 D1′，`.ckpt` 与 MindSpore 推理链路一期即投入使用**（视频感知链路：`demo_cli.py image / track / count` → 像素轨迹 → 透视标定 → 四项指标）；一期开工前置为 **0-6 视频链路跑通 + SUMO 安装与许可核查 + 站点范围 OSM 路网 + 表格模板下发**（见 [`docs/全流程计划.md`](../../docs/全流程计划.md) 阶段 0 与手册第 1.4 节）。

**换机器重建环境时注意**：依赖清单**未覆盖**两个包，要补装——`setuptools`（`mindyolo` 里有 `import pkg_resources`）与 `ultralytics`（`verify` 步要 `torch.load` 原 `.pt`，其 pickle 引用 ultralytics 类）。建议按流程补进上游 `requirements-mindspore.txt`。

## 八、大文件

压测日志、运行产物放 `logs/` 与 `out/`（已 gitignore）。模型权重、视频放共享盘。
