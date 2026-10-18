# work/assembly · 接口与总装（开发C）

> ⚠️ **2026-10-11 业主裁定（推翻前述接口规划）**：web 端整体推翻 harness 架构，后端接口面改为**根据前端页面重新规划**后再落地。本文件第二节的端点清单、"既有 8 个端点零改动"边界与"PR #51 实现基准"**作废待重订**（PR #51 已收回，traffic.py 骨架可在该 PR 页面回看）；重订前第二节仅作历史参考。

> **产出**：接口层 `traffic.py` + 一键演示脚本（Windows `.bat` + `run_all.py`）+ 压测脚本
> **同时负责**：**公共文件的唯一修改人**（根 `README.md`、`.gitignore`、`.gitee/`、`docs/数据契约.md`、路由注册）
> **注意**：这里登记的是**公共文件由开发C 改、队长复核**，不是"开发C 想怎么改就怎么改"。

## 一、负责什么

1. **接口层** `traffic.py`：演示前最后一步，把快照文件（`segments.json` / `routes.json` / `vehicles.json`）包成 HTTP 接口给双端调用；
2. **一键演示脚本**：**Windows 下双击 `.bat` 就能跑**（现场演示不允许"先教我敲命令"）；
3. **公共文件**：根目录 `README.md`、`.gitignore`、`.gitee/`、`docs/数据契约.md`、`app/main.py` 注册与路由表 —— **只由你一人改，队长复核**；
4. **压力测试**：按算力预算跑，以"**无人干预连跑 3 轮不出问题**"为验收口径（M1-6）。

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
| `/api/traffic/alerts` | GET | 告警列表（四态 + `triggered_by` + 首次观测时间 + 回执 / 回写留痕） | **已实现**（IKMF1T；由快照派生） |
| `/api/traffic/plan/dispatch` | POST | 下发分流方案（渠道 + 比例）→ 回执 | 已实现（**内存态**；正式落库留痕待二期） |
| `/api/traffic/plan/ack` | POST | 处置回写（认领人 / 动作 / 结果四选一）→ 状态流转 | 已实现（**内存态**；正式落库留痕待二期） |
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

**写接口的留痕要求（新增，后端实现时照此）**：`plan/dispatch` 与 `plan/ack` 是本次接口面里**仅有的两个状态写入**，
前端已按「回执 + 回写留痕」展示（渠道、比例、认领人、动作、结果四选一、时间）。mock 里是内存态（刷新复位，页面已标「演示态」），
**后端实现必须落库**，否则决策层的「处置闭环」无法举证。

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

**写端点（一期：进程内存态，重启复位；不落库、不写快照、不重算判级）**：

| 端点 | 入参（与 mock 同形） | 行为 | 响应口径 |
|---|---|---|---|
| `POST /api/traffic/factors` | `{segment_id, factor_id, name?, target, multiplier}`，`factor_id` 限 **F07 / F08 / F11** | 校验路段/因素/目标/倍率 → 覆盖式登记到内存 | `applied:true` + `level_recomputed:false` + `note`；`level/level_name` 是**当前快照原值（注入前）**，不是注入后判级 |
| `POST /api/traffic/factors/reset` | — | 清空人工置位（幂等） | `{reset:true, cleared:N, note}` |
| `POST /api/traffic/scenario` | `{weather?, session?, demand_mult?, segment_id?}`；**缺省 = 不改，显式 null = 清除** | 只更新环境状态 → 折算 F01/F02/F03/F10 | `applied:true` + `factors` + `effects:[]` + `recomputed:false` + `note`（接口层不伪造注入前后判级对照） |
| `POST /api/traffic/scenario/reset` | — | 清空场景注入（幂等） | `{reset:true, was_injected:bool, note}` |

- **两个口子不混用**：人工置位只有 F07/F08/F11；F01/F02/F03/F10 属环境侧，只走 `/scenario`。
- **接口层不重算 level / ci**（判级唯一实现是感知层 `level.py`）：写端点只更新 `context` /
  `derived_factors` / 因素状态；`GET /factors`、`GET /segments` 里登记的因素带
  `injected:true, pending_recompute:true`，**不伪造等级变化**。复位方式：三个 `POST *reset`，或重启进程。
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
python work/assembly/traffic.py --check            # 数据源 / 路线优先级 / 写端点内存态(新进程恒空)
curl -s http://127.0.0.1:8000/api/traffic/meta     # 响应头 X-Traffic-Data-Source
curl -s -X POST http://127.0.0.1:8000/api/traffic/factors -H "Content-Type: application/json" \
     -d '{"segment_id":"SZ-005","factor_id":"F07","name":"交通事故 / 故障车","target":"c","multiplier":0.5}'
curl -s -X POST http://127.0.0.1:8000/api/traffic/scenario -H "Content-Type: application/json" \
     -d '{"weather":"大雨","session":"晚高峰"}'
curl -s -X POST http://127.0.0.1:8000/api/traffic/scenario/reset
```

> 注：本单不改 `selfcheck_ikmf1t.py`。该脚本仍按 IKMF1T 当时的口径断言
> `POST /factors`、`/scenario`、`/scenario/reset` 是 404（"unimplemented"）；IKMS17 已把它们实现为
> 内存态端点，**这三条断言已过时**，脚本其余检查仍可作回归参考（跑该脚本会覆写 `对照快照.*` /
> `自检记录.md`，这三份是 IKMF1T 的交付物，本单不重写）。

## 三、一键演示脚本

```text
双击 demo.bat                    # 现场演示就按这一个
python run_all.py                # 等价命令行入口
python run_all.py --stress       # 压力测试：连续 3 轮
```

| 脚本 | 干什么 | 纪律 |
|---|---|---|
| `demo.bat` | **双击即跑**：建目录 → 启动孪生主循环（`work/twin/loop.py`）→ 跑全链路 → 起接口层 → 打开管理端 | **不许要求现场敲命令、不许要求现场装东西** |
| `run_all.py` | 把**孪生 → 感知判级 → 决策 → 快照 → 接口层**串起来，一键跑完全链路 | 每一步都做**产物存在性断言**（见第五节） |
| `stress.py` | 连续 3 轮 + 日志留存 + 内存观察 | 判定标准：**3 轮全成功、日志留存、内存不持续增长** |

**场景参数**：`--scenario scenario_2`（峰值场景，验收主战场：同一输入跑 ①不推荐 ②"此刻最快" ③协同推荐，同屏对比）。

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
