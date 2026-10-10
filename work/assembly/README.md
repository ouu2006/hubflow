# work/assembly · 接口与总装（开发C）

> **产出**：接口层 `traffic.py` + 一键演示脚本（Windows `.bat` + `run_all.py`）+ 压测脚本
> **同时负责**：**公共文件的唯一修改人**（根 `README.md`、`.gitignore`、`.github/`、`docs/数据契约.md`、路由注册）
> **注意**：这里登记的是**公共文件由开发C 改、队长复核**，不是"开发C 想怎么改就怎么改"。

## 一、负责什么

1. **接口层** `traffic.py`：演示前最后一步，把快照文件（`segments.json` / `routes.json` / `vehicles.json`）包成 HTTP 接口给双端调用；
2. **一键演示脚本**：**Windows 下双击 `.bat` 就能跑**（现场演示不允许"先教我敲命令"）；
3. **公共文件**：根目录 `README.md`、`.gitignore`、`.github/`、`docs/数据契约.md`、`app/main.py` 注册与路由表 —— **只由你一人改，队长复核**；
4. **压力测试**：按算力预算跑，以"**无人干预连跑 3 轮不出问题**"为验收口径（M1-6）。

## 二、接口层（演示前最后一步）

**一期主链路不依赖 HTTP**（文件快照当契约）。这一层**只读快照，不写快照**——它不产生任何数据，只把已经落盘的结果端出去。

| 端点 | 方法 | 用途 | 期次 |
|---|---|---|---|
| `/api/traffic/segments` | GET | 路段级指标与等级列表 | 一期 |
| `/api/traffic/segments/{id}` | GET | 单路段详情（含 `factors_applied` / `pred`） | 一期 |
| `/api/traffic/route/recommend` | POST | 请求推荐（请求体含 `session_id` / `location`） | 一期 |
| **`/api/traffic/locate`** | POST | **定位 → 路段**。一期由孪生真值调用，二期由 App 调用 | 一期 |
| **`/api/traffic/vehicles`** | GET | **一期演示：孪生车辆位置**（读 `vehicles.json`）。**二期下线** | 一期 |
| **`/api/traffic/factors`** | GET | 当前生效因素清单（从各路段 `factors_applied` 汇总） | 一期 |
| **`/api/traffic/predict`** | GET | 预测：`?segment_id=&h=15`。一期 **L0**，二期 L1/L2 | 一期 |
| `/api/traffic/alerts` | GET | 告警列表 | 一期 |
| `/api/traffic/plan/dispatch` | POST | 下发分流方案 | 一期 |
| `/api/traffic/plan/ack` | POST | 处置回写 | 一期 |
| `/api/traffic/report/compare` | GET | 效果对比报表 | 一期 |
| **`/api/traffic/assimilation`** | GET | **数据同化状态**：每个断面"是否在灌 / 门控原因 / 最近一次回灌值"；只读 `assimilation_state.json`（**不改 `segments.json` 形状**） | 一期 |

**约定**：`is_simulated` 字段在**每一个**响应里出现；事件流复用现有 SSE 形状，**新增**事件名，**不改既有事件名**；**一期是非视频端点驱动的页面**——**视频感知链路**（YOLO 跑样本视频，`source: "video"`）**一期就在跑**，但它的结果以 `segments` 快照的形式进接口层（**不新增视频流 / 画面端点**，"检测画面"页归二期）。`/api/traffic/segments` 与 `/segments/{id}` 必须能按 `source` **并排返回 `video` / `twin` 两个来源**（**TC-19 的展示侧**）。

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

理由：上游仓已实测复现过"**命令报成功、产物根本没生成**"的假通过——**验收时看不出来，比报错更危险**。

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
| 1 | **OpenCV 不支持中文绝对路径**——`cv2.imwrite` / `cv2.imread` 传中文绝对路径直接失败，而 `image` 模式的输出目录由 `REPO_ROOT` 拼出，**必为中文绝对路径** | ① 把两个仓库放到纯英文路径（如 `D:\work\`，**推荐**，根因消除）；或 ② 写出改 `cv2.imencode` + `open(...,'wb')`、读入改 `np.fromfile` + `cv2.imdecode` |
| 2 | **`track` / `count` 的输出目录不存在时静默失败**——`_write_frames()` 既不 `makedirs` 也不检查 `isOpened()`，**命令照样打印"轨迹条数: 9"但视频文件根本没生成** | `run_all.py` 里先 `os.makedirs(..., exist_ok=True)`；**压测脚本里加一条"产物文件存在性"断言**，别只信退出码 |

> **一期口径（D1′）**：这两个缺陷正好落在**视频感知链路**上——**一期就要跑视频（6 段样本视频 + YOLO），所以一期必须先处理**：
> ① **中文路径**：仓库与上游**已迁到纯英文路径**（`D:\work\hubflow` / `D:\work\agentic-traffic-management`），根因消除；代码层 `imencode + imdecode` 作为二期加固项；
> ② **输出目录静默失败**：`run_all.py` 与演示脚本**先 `os.makedirs(..., exist_ok=True)`**，并加"产物存在性断言"——**别只信退出码**。
> 这条纪律**两条链路都照用**（孪生输出、快照文件、时序数据都会出现同类假通过）。

## 七、硬前置与上游资产（**状态已按 V2.0 更新**）

**0-1 ~ 0-3 已完成**（2026-10-09）：`.ckpt` 已生成（`yolov8n.ckpt`，12.7 MB）并通过前向数值比对（最差相对误差 2.875e-06）；环境已按 `requirements-mindspore.txt` 重建（CPython 3.11.17 + MindSpore 2.8.0）。

> **按 D1′，`.ckpt` 与 MindSpore 推理链路一期即投入使用**（视频感知链路：`demo_cli.py image / track / count` → 像素轨迹 → 透视标定 → 四项指标）；一期开工前置为 **0-6 视频链路跑通 + SUMO 安装与许可核查 + 站点范围 OSM 路网 + 表格模板下发**（见 [`docs/全流程计划.md`](../../docs/全流程计划.md) 阶段 0 与手册第 1.4 节）。

**换机器重建环境时注意**：依赖清单**未覆盖**两个包，要补装——`setuptools`（`mindyolo` 里有 `import pkg_resources`）与 `ultralytics`（`verify` 步要 `torch.load` 原 `.pt`，其 pickle 引用 ultralytics 类）。建议按流程补进上游 `requirements-mindspore.txt`。

## 八、大文件

压测日志、运行产物放 `logs/` 与 `out/`（已 gitignore）。模型权重、视频放共享盘。
