# IKMS1I 自检记录：交付包 C-4~C-7（真跑输出）

> **演示数据（模拟）**：本记录是**本机真跑**的原始输出摘要，不是性能验收 / M1-6 通过声明。
> 缺前置（感知样本导出 / 前端 dev server）的步骤**如实标阻塞**，不写「通过」。

- 生成时间：2026-10-18（Asia/Shanghai）
- 被测代码：`work/assembly/`（运行于 `origin/main` 2bb66e5 + 本单未提交改动；提交后 sha 见提交记录）
- 环境（实测）：Windows 11（10.0.26300）· AMD Ryzen 9 8945HX（16C/32T）· 15.8 GiB · Python 3.12.10 · psutil 7.2.2
- 交付文件：[`demo_all.py`](demo_all.py) / [`demo_all.ps1`](demo_all.ps1)（C-4）· [`stress_test.py`](stress_test.py) + [`压测报告.md`](压测报告.md)（C-5）· [`对外接口.md`](对外接口.md)（C-6）· [`部署与监控.md`](部署与监控.md) + [`monitor_check.py`](monitor_check.py)（C-7）· [`README.md`](README.md) §2.3 交付索引

---

## 一、C-4 一键演示：`python work/assembly/demo_all.py --rounds 3`（真跑）

命令与退出码：

```text
python work/assembly/demo_all.py --rounds 3
[demo exit=2]   # 0=全成功；2=跑完但有阻塞（如实记录，不算 M1-6 通过）；1=有失败
```

三轮结果（来自 `work/assembly/out/demo_all_report.json`，gitignored）：

| 轮次 | 状态 | 总耗时 (s) | 真网算路 | 感知链路 | 接口层 | 端点自检 | 内存（起→止 MB，采样点） |
|---|---|---|---|---|---|---|---|
| 1 | blocked | 3.54 | ✅ ok | ⛔ blocked | ✅ ok | ✅ ok（18 项 + SSE） | 55.02 → 55.88（3 点，峰值 55.88） |
| 2 | blocked | 3.44 | ✅ ok | ⛔ blocked | ✅ ok | ✅ ok | 55.22 → 56.02（3 点，峰值 56.02） |
| 3 | blocked | 3.49 | ✅ ok | ⛔ blocked | ✅ ok | ✅ ok | 55.11 → 55.92（3 点，峰值 55.92） |

**M1-6 结论：阻塞/未通过（`passed: false`）**——不是「全成功」：

- 阻塞项（每轮同一原因）：`perception-chain` = 缺 `work/perception/data/monitor/` 样本导出（gitignored，上游未提供），
  感知链路 **0 通道产出**；脚本把「命令退出码 0 但产物 0 段」判为**阻塞**（不是成功）。
- 已验证通过的部分：真网算路（`routes.json` 12 条 requests，真网 61 段 / 44 节点）、接口层启动、
  18 个关键端点 + SSE 全部 200、每轮日志/产物留存。
- 内存（仅本机 3 轮实测，**不是性能验收**）：末轮起始 55.88→56.02→55.92 MB，growth=-0.12 MB，自定阈值内 `not_continuously_growing=true`。

真网算路（每轮都重跑，产物新鲜）：`work/engine/out/real/routes.json`，`requests=12`，真网 61 段 / 44 节点（`run_log.json`）。

端点自检（每轮 18 项，均 200；节选失败表格无——全部通过）：

| 端点（第 1 轮实测） | 方法 / 路径 | 状态 | 耗时 (ms) | 数据源（响应头） |
|---|---|---|---|---|
| meta | GET /api/traffic/meta | 200 | 10.8 | stations.baseline |
| overview | GET /api/traffic/overview | 200 | 8.76 | stations.baseline |
| segments | GET /api/traffic/segments | 200 | 23.72 | stations.baseline |
| network | GET /api/traffic/network | 200 | 8.16 | stations.network |
| thresholds | GET /api/traffic/thresholds | 200 | 5.38 | stations.thresholds |
| context | GET /api/traffic/context | 200 | 12.53 | stations.baseline |
| factors | GET /api/traffic/factors | 200 | 11.23 | stations.baseline |
| assimilation | GET /api/traffic/assimilation | 200 | 7.38 | twin.assimilation |
| alerts | GET /api/traffic/alerts | 200 | 10.08 | stations.baseline |
| vehicles | GET /api/traffic/vehicles | 200 | 5.05 | twin.vehicles |
| heat-matrix | GET /api/traffic/heat-matrix | 200 | 12.27 | stations.baseline |
| plan-audit | GET /api/traffic/plan/audit | 200 | 5.41 | dispatch-store |
| segment-detail | GET /api/traffic/segments/SEG-001 | 200 | 25.02 | stations.baseline |
| segment-sources | GET /api/traffic/segments/SEG-001/sources | 200 | 11.42 | stations.baseline |
| predict | GET /api/traffic/predict | 200 | 11.42 | stations.baseline |
| ci-history | GET /api/traffic/ci-history | 200 | 10.27 | stations.baseline |
| route-recommend | POST /api/traffic/route/recommend | 200 | 30.23 | engine.routes.real |
| locate | POST /api/traffic/locate | 200 | 29.91 | engine.routes.real |
| stream(SSE) | GET /api/traffic/stream | 200 | — | event=traffic_snapshot |

**阻塞后的正确口径**：M1-6 要求「无人干预连跑 3 轮**全成功** + 日志/产物留存 + 内存不持续增长」——
感知样本导出缺失导致第一项不成立，故本记录只写「三轮真跑完成、逐轮如实记录、**M1-6 未通过**」。
补前置后可复跑：`python work/assembly/demo_all.py --rounds 3`（脚本会自己起停接口层，无需人工干预）。

---

## 二、C-5 压测：`python work/assembly/stress_test.py`（真跑）

```text
就绪：2337.3 ms
端点 14 个；每轮每端点 20 次 × 8 并发
第 1 轮：280 请求 · 1.284 s · 218.1 RPS · 错误 0 · RSS 55.11→60.16 MB
第 2 轮：280 请求 · 1.322 s · 211.8 RPS · 错误 0 · RSS 61.35→64.97 MB
第 3 轮：280 请求 · 1.396 s · 200.6 RPS · 错误 0 · RSS 62.4→65.83 MB
总请求 840 · 错误 0 · P50 36.38 ms · P95 64.41 ms
[stress exit=0]
```

- 完整报告（不可变快照）：[`压测报告.md`](压测报告.md)（每次运行会重写；本节数字与之一致）；
- 实测口径：单机回环、只读 GET 端点、客户端计时、nearest-rank 百分位；**未压写端点**（会改持久化运行态）；
- **不判定「性能达标」**：报告只陈述实测数字；手册 demo 目标值（如 route/recommend P95 ≤ 3000 ms）仅作参照，由验收方判定；
- 内存：`psutil` 采接口层进程 RSS，逐轮起止/峰值见表（**报告不对「是否持续增长」下结论**，M1-6 判定在 C-4）。

---

## 三、C-6 对外接口文档：与 `traffic.py` 逐条对照（脚本核对）

| 核对项 | 结果 |
|---|---|
| `traffic.py` 实际路由 vs [`对外接口.md`](对外接口.md) 端点表 | **27/27 条逐条出现**（`GET /plan/audit` 已标注「辅助端点，非契约」） |
| `_error(...)` 实际返回的行为错误码 vs 文档错误码表 | **16/16 条逐条出现**；`NOT_IMPLEMENTED` / `NO_DATA` 为代码预留常量、当前无端点返回，文档已注明 |
| 信封 `is_simulated` | 文档写清「**每一个**响应（含 4xx/5xx）顶层都带 `is_simulated: true`」 |
| 鉴权形状 | 文档写清「**一期无鉴权**、只绑 127.0.0.1；二期 `Authorization: Bearer <platform-key>` 形状预留、不发放真实密钥」 |
| 围栏衔接（手册第 13 章） | 文档含「围栏外导航算 / 围栏内本引擎算 / 衔接点=围栏入口 / 一期孪生边界车流代替 / 后台不代理高德」+ 进站前 `locate`、离站后 `departure_route` |
| 演示环境声明（M1-7） | 文档开头与第 9 节均有「演示数据（模拟）· 无真实用户数据 / 无真实下发通道」声明 |

核对命令（可复跑）：解析 `traffic.py` 的 `@app.get/post` 与 `对外接口.md` 文本逐条比对，结果如上（原始输出见本次会话记录）。

---

## 四、C-7 监控自检：`python work/assembly/monitor_check.py`（真跑，接口层运行中）

```text
C-7 监控自检（演示数据（模拟））· 2026-10-18T14:33:50+08:00
层    状态    监控项                   实测 / 说明
服务   ✅    接口层进程                 traffic.py 进程数=1（pid=[34560]）
服务   ✅    端口 8000               LISTEN
服务   ✅    接口可用性与时延              GET /api/traffic/meta -> 200 · 74.5 ms（本机回环，单次采样；P95 需压测脚本）
数据   ✅    数据新鲜度                 路段 17 段 · 数据源 stations.baseline · 数据年龄最大值 Nones · 陈旧(> 120s) 0 段 · 不可用 17 段
服务   ✅    端点 alerts             GET /api/traffic/alerts -> 200 · 9.4 ms
服务   ✅    告警列表                  0 条（四态见 GET /alerts）
服务   ✅    端点 plan/audit         GET /api/traffic/plan/audit?limit=5 -> 200 · 4.8 ms
服务   ✅    端点 overview           GET /api/traffic/overview -> 200 · 7.9 ms
服务   ✅    接口 5xx                本次巡检 0 次 5xx
服务   ✅    处置闭环持久化文件             work/assembly/data/dispatch.json 不存在（尚未发生下发/回写，属正常初始态；首次写入时创建）
服务   ✅    磁盘使用率                 69.5%（阈值 85%）
服务   ✅    日志体积                  out/ 下 *.log 合计 0.07 MiB（一期不自动轮转，演示前可清 out/）
范围   ✅    二期监控项（一期不做）           判级一致率 / 预测误差 / 采纳率（效果层）、备份任务、会话数据留存（合规层）、openGauss/Atlas —— 按手册 §21.2 属二期，本脚本不采集、不编造
总体：全部正常 · 结果 JSON：work/assembly/out/monitor_check.json
[monitor exit=0]
```

- 监控项按手册 §21.2 分层：**数据层**（数据新鲜度 / 置信度 / 因素缺失 / 参数版本）+ **服务层**（进程 / 端口 / 5xx / 时延 / 磁盘 / 持久化文件 / 备份）+ **效果层**（一致率 / 预测误差 / 采纳率）+ **合规层**（会话留存）；
  **一期只落地可实测的数据/服务项**，效果 / 备份 / 合规 / openGauss / Atlas 如实标「二期」，见 [`部署与监控.md`](部署与监控.md) §6。
- 部署步骤 / 端口 / 进程守护 / 日志位置 / 回滚：见 [`部署与监控.md`](部署与监控.md)（单机：8000 接口层、8101 感知可选；不含 openGauss/Atlas）。

---

## 五、仓库门禁 doc_gate

```text
门禁根目录：<repo>
受管文件：326 个（已跟踪 326 个，内容取自 git 索引）

[通过] 1/8 编码与换行（UTF-8 无 BOM / LF）（检查 256 个目标）
[通过] 2/8 大文件与禁入类型（检查 326 个目标）
[通过] 3/8 Markdown 相对链接（检查 58 个目标）
[通过] 4/8 JSON 可解析（含数据契约示例）（检查 41 个目标）
[通过] 5/8 密钥扫描（检查 256 个目标）
[通过] 6/8 契约字段命名（snake_case）（检查 15 个目标）
[通过] 7/8 填表报告台账（格式 / 产物覆盖 / 结果语义）（检查 15 个目标）
[注意] docs/填表报告.md:123  `结果` 是「占位」（**T1~T9** → `stations/network.json` / `stations/points.json` / `stations/signal_plan.json` / `stations/demand.json` / `stations/factors.json` / `stations/scenarios.json` / `stations/thresholds.json` / `stations/calibration.json` / `stations/map_source.json`）—— 登记的是「还没有表格出处」的产物（结构骨架 / 运行产物 / 基线）；它只说明**在场**，**不代表数据可用**，不要拿它当「已转」的证据
[注意] docs/填表报告.md:125  `结果` 是「占位」（T1~T9 → `stations/calibration.json`）—— 登记的是「还没有表格出处」的产物（结构骨架 / 运行产物 / 基线）；它只说明**在场**，**不代表数据可用**，不要拿它当「已转」的证据
[注意] docs/填表报告.md:126  `结果` 是「占位」（T1~T9 → `stations/thresholds.json`）—— 登记的是「还没有表格出处」的产物（结构骨架 / 运行产物 / 基线）；它只说明**在场**，**不代表数据可用**，不要拿它当「已转」的证据
[通过] 8/8 任务记录台账（格式 / 结果枚举 / 日期）（检查 120 个目标）

门禁全部通过。
```

---

## 六、遗留 / 阻塞（如实记录）

1. **感知链路阻塞**：`work/perception/data/monitor/` 样本导出缺失（gitignored，上游未提供）→ C-4 每轮感知链路 0 通道产出，
   **M1-6 不能声明通过**；补数据后 `demo_all.py --rounds 3` 可直接复跑（脚本自动起停，无需人工干预）。
2. 本机未起前端 `npm run dev:remote`：C-4 的「前端截图/录屏素材」不在脚本内（演示脚本只做链路与接口自检），
   前端联调需另行起 dev server；不影响 C-4/C-5 数字。
3. C-5 未压写端点（会改持久化运行态）与多进程/真实网络链路，报告中已写明覆盖范围；属专项/二期压测。
4. `docs/任务记录.md` 按协作约定由 Lead 统一收口留行，本单不改。
5. 所有运行产物 / 日志 / 报告 JSON 在 `work/assembly/out/`（gitignored），**未提交**；`压测报告.md` 是仓库内的实测快照。
