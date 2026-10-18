# work/twin · 数字孪生（开发A）

> **产出**：一个**能复现**的站前虚拟交通世界 —— 路网 + 场景 + 三类虚拟司机 + 虚拟检测器 + 因素注入，由**单进程主循环** `loop.py` 驱动。
> **消费方**：`work/perception/`（读虚拟检测器数据出指标）、`work/engine/`（读车辆真值位置做定位匹配）。**本目录只负责孪生链路**（`source: "twin"`）；**视频感知链路**（`source: "video"`）在 `work/perception/`，两条链路字段一致、共用下游，并由视频实测值标定孪生的边界（见第八节），**再由视频实测值每 60 s 回灌孪生的边界断面（数据同化，见第九节）**。
> **一期为什么要有它**：按 **D1′**，一期是**双数据源**——**视频感知链路**（YOLO，6 段真实样本视频）负责"**这条真实路段现在到底堵不堵**"，**孪生链路**负责"**如果我们这样引导，路况会怎么演化**"（**同一输入跑三遍的开关对照实验**，以及"世界会自己演化"的演示效果——这是固定录像给不了的）。没有孪生，这两件事都无从谈起，所以它仍是**一期风险最高、最关键的一环**；而且**孪生自己的边界条件要用视频链路的实测值来标定**（见第八节）。
>
> **角色简称**：开发A / 开发B / 开发C；**池·V / 池·S / 池·P / 池·Q** = 任务池四个系列（视频线 / 站点踏勘 / 参数调研 / 独立验收）的**认领者**（协作成员，无锁角色，原 N1~N4 定岗已作废）；**队长** = 7 人中 1 人兼任，**不参与认领**。

## 〇、输入 / 输出 / 关键口径（三行）

| | 内容 |
|---|---|
| **输入文件** | 真孪生：`stations/{network,points,demand,factors,scenarios,signal_plan}.json` + `stations/sumo/*.net.xml`；样例链路：`samples/*_sample.json`（`--sample` 时无上游数据也能跑）；真网断面/同化：`netpack/network_junction.json` + `site-ranges.json` + `out/latest/segments_twin.json`（W1 真孪生快照，同化基线**首选**，见第十八节）+ 视频快照 `<仓库根>/work/perception/out/latest/segments_video.json`（见第九节、第十二节） |
| **输出文件** | `out/{segments,vehicles,assimilation_state}.json` + `out/run_log.json`（`--no-sumo` 样例链路）；IKMS19 同化产物：`out/latest/assimilation/{sections_candidate,assimilation_state,assimilation_log,factors_report,segments_before,segments_after,run_log}.json`（机制示例另放 `out/latest/assimilation/mechanism_demo/`；**IKNAUN 起分目录，不再覆盖主循环 `out/latest/run_log.json`**）；**IKNAER（W1）真孪生**：`out/latest/{segments_twin,vehicles,run_log,twin_timeseries}.json`（默认 `--out work/twin/out`；另按接口层路径兼容发布 `<out>/vehicles.json`）+ 可重建路网 `out/sumo/station.net.xml`；`stations/sumo/*.net.xml` 的 OSM 管线归 `netbuild.py`，`network.json` **不是**本模块产物（归开发B 的 `map_ingest.py`） |
| **关键口径** | **只有一个时钟**：孪生仿真时钟，不读系统时间；同一场景跑两遍**逐字段一致**（M1-1 可复现）；只有 `role="boundary"` 的断面允许同化回灌，`internal` **永远** `assimilating:false`。**断面清单是候选（待签字冻结）**、**同化基线优先真孪生快照（IKNAUN）、缺失时才退回明示的空载演示基线**、**空载基线/机制示例都不得当实测或本站结论**（第十二~十八节）。**IKNAER 的真孪生主循环**（第十七节）已产出真网 SUMO 快照与 65 点时序，但需求是站点包样例/演示值（真实需求归 IKMHMX），视频侧 60 点仍归感知侧 |

## 一、负责什么

```text
站点 OSM 切片 ──netconvert──► stations/sumo/*.net.xml
                                        │
                                        ├──► stations/network.json（开发B 的 map_ingest.py 产出）
                                        │
stations/{points,demand,factors,scenarios,signal_plan}.json
                                        │
                                        ▼
                    ┌─────────── loop.py（单进程主循环）───────────┐
每 1 秒：SUMO 走一步（跟驰 / 排队 / 信号） ←TraCI→ 自研司机行为体（改路线 / 停靠 / 候客）
          ↑ 因素注入：大雨降速、违停占道、事故封道、停车场满位、列车到达放量……
每 60 秒：虚拟检测器聚合 → 交 work/perception/ 出指标与判级 → segments 快照
          车辆真值位置 → 交 work/engine/ 做定位与推荐 → routes 快照
          车辆清单 → vehicles.json（**仅一期演示用**）
                    └──────────────────────────────────────────────┘
```

| 职责 | 一句话 | 交付物 |
|---|---|---|
| **路网转换** | 把站点 OSM 用 `netconvert` 转成 SUMO 路网（**`sumo/*.net.xml` 与 `network.json` 都是本步骤的产物，但只有 `.net.xml` 归本模块交付**——见下） | `stations/sumo/*.net.xml` |
| **场景** | 按 `scenarios.json` 开关组装四个演示场景（常态 / 峰值 / 突发 / 多因素） | 可复现的场景入口 |
| **司机行为体** | 三类虚拟司机（D1 送客 / D2 接客 / D3 往返）的选择与停靠行为 | `driver.py` |
| **虚拟检测器** | 在二期摄像头将来的位置布断面，输出**路段级聚合数**（只数车、不认车） | `detector.py` → 交感知 |
| **边界标定** | 用**视频感知链路**的实测值标定孪生的边界条件与基础参数（到达流率 / `v_f` / `s₀` / 排队阈值 / 服务时长） | 标定记录 → 写进 `stations/`（见第八节） |
| **数据同化** | 把视频链路在**边界断面**测到的流量 / 车速，每 **60 s** 通过 SUMO `calibrator` **回灌**成孪生的边界来车；**站前内部路段不灌** | `calibrate.py` + 回灌日志 → 见第九节 |
| **因素注入** | 把 `factors.json` 的 14 类因素按时间窗注入孪生（改容量 / 速度 / 需求 / 车道） | `factors.py` |
| **主循环** | 仿真时钟推进 + 每 60 s 调用感知与引擎，落快照 | `loop.py` |
| **两条链路合流** | 孪生链路的检测器输出 + 视频链路的指标，**字段一致、只有 `source` 不同**，都进 `segments` 快照 | `stations/` + `work/perception/` |

> **不负责**：指标与判级（`work/perception/`——其中**判级 `level.py` 由开发B 写**，四项指标归开发A）、路线推荐与定位匹配（`work/engine/`）、接口与页面（`work/assembly/` + `work/frontend/`）。**孪生只提供"世界"，不提供"结论"。**

## 二、建议目录结构

```text
work/twin/
├─ README.md              # 本文件
├─ loop.py                # 主循环入口：--scenario / --seed / --duration
├─ netbuild.py            # OSM → netconvert → stations/sumo/*.net.xml（network.json 不在这里，见下）
├─ sumonet.py             # 真网 network_junction.json → plain nod/edg → netconvert → out/sumo/station.net.xml（IKNAER / W1，可一键重建）
├─ scenario.py            # 读 stations/scenarios.json，组装场景（开关 / 注入事件 / 种子）
├─ driver.py              # 三类司机行为体（跟驰交给 SUMO，决策走 TraCI）
├─ detector.py            # 虚拟检测器：按检测断面聚合流量 / 车速 / 排队
├─ calibrate.py           # 数据同化：边界断面实测 → traci.calibrator.setFlow（每 60 s、带门控）
├─ factors.py             # 因素注入接口（读 stations/factors.json）
├─ demand.py              # 读 stations/demand.json 生成车流（T3 列车到达 × T4 比例 → 60 s 到达流率；IKNAER 真路径）
├─ sections.py            # 真网断面角色候选自动推导（IKMS19）：network_junction.json → boundary/internal
├─ baseline.py            # 孪生基线构造（IKMS19 / IKNAUN）：**优先 W1 真孪生快照**（baseline_source=twin.latest），缺失时才空载/视频明示降级
├─ run_assimilation.py    # 同化 + 多因素一键入口（IKMS19 / IKNAUN）：--twin 接真孪生快照 + 候选清单/同化状态/日志/因素报告/before-after（产物分目录 out/latest/assimilation/）
├─ tools/                 # 自检脚本：IKMS19 的 check_assimilation.py（TC-20 + 真基线前置）/ check_factors.py（TC-16）；IKNAER 的 check_w1.py（M1-1 / M1-2 孪生侧 / TC-13）
├─ samples/               # 样例输入（无 SUMO 也能跑通判级/引擎链路）
├─ demo_y/                # Y 型**示意**路网 + 场景（SUMO 全链路可一键重建；与 OSM 真路网管线并列，见该目录 README）
└─ out/                   # 运行输出（已 gitignore；**脚本必须先建目录**）：latest/ W1 契约快照、latest/assimilation/ 同化产物、sumo/ 可重建 SUMO 路网、check_w1/ 自检运行目录
```

> **`demo_y/` 与 `netbuild.py` 的区别**：`netbuild.py` 是「**OSM 真路网**」管线（转真实切片）；
> `demo_y/` 是「**凭空造的示意路网**」（一个 Y，占位锚点、不做地理配准）。
> 两者**并列、互不覆盖**，口径完全不同 —— 详见 [`demo_y/README.md`](demo_y/README.md)。

> **`samples/` 是给别人用的**：开发B、开发C 不该等你把 SUMO 装好才能开工——把一份**最小可用样例**（几段路 + 几条车辆记录 + 一个快照）放在这里，他们就能单独跑通自己的模块。**目录名统一用 `samples/`、文件名用 `<名字>_sample.json`**（[`docs/开发规范.md`](../../docs/开发规范.md) 第 6 节），不要写成 `sample/`。

> ⚠️ **`network.json` 不在本模块的交付物里**：本模块只产出 `stations/sumo/*.net.xml`（SUMO 路网）。**统一图结构 `network.json` 由开发B 的 `map_ingest.py` 产出**（[`../engine/README.md`](../engine/README.md) 第五 / 七节、手册第 8.3 节）——本模块需要图结构时**读**它，不写它。两边都写同一个文件必然互相覆盖。

## 三、SUMO 安装与 TraCI

| 项 | 说明 |
|---|---|
| 装什么 | **SUMO**（含 `netconvert` / `netedit` / `sumo` / `sumo-gui`）与 **TraCI 的 Python 包** |
| 版本 | 团队**统一一个版本**，写进本文档并同步给开发B / 开发C（路网与快照要能互相对上） |
| 环境变量 | 安装后设 `$SUMO_HOME` 指向 SUMO 安装根目录；`$SUMO_HOME/tools` 加进 `PYTHONPATH`，`traci` 从这里导入 |
| 许可 | 阶段 0 完成 **SUMO 许可核查**（EPL 系许可，商用与分发口径由队长确认） |
| 出门条件 | **能跑通 SUMO 官方示例**（阶段 0 出门条件之一），再动本项目的路网 |

PowerShell 里设环境变量（当前会话）：

```powershell
$env:SUMO_HOME = "C:\Program Files\SUMO"     # 仅为示例值（MSI 默认位置）；本仓按 zip 装到自定的纯英文目录，按实际改
$env:PYTHONPATH = "$env:SUMO_HOME\tools;$env:PYTHONPATH"
```

**自检**（三件事都要过）：

```powershell
netconvert --version                 # 能打印版本
python -c "import traci; print(traci.__file__)"   # 能导入 TraCI
sumo --version                       # 能打印版本
```

> **路径已统一为纯英文（2026-10-10）**：本仓库现在就在纯英文路径下，**中文路径的坑已消除**（背景见 [`../assembly/现状核实.md`](../assembly/现状核实.md) 4.3）。**新同事 clone 时也要挑纯英文目录。**
> 仍要记住的经验：**任何走 OpenCV 的产物（截图、标注图）遇到「命令报成功、产物没生成」，先怀疑路径与输出目录，再怀疑代码**——`video_output/` 不存在时的静默失败是同一个毛病。

## 四、虚拟检测器布点口径（**必须与二期摄像头点位一致**）

**这是 D1′ 的命门**：一期虚拟检测器放在**二期真摄像头将来的位置**，输出**同字段**的聚合数据（`source: "twin"`）。二期换数据源时，下游一行不用改。

| 规则 | 说明 |
|---|---|
| 位置 | 直接读 `stations/points.json` 里 `detector` 类点位（池·S 按底图打的 T1 点位表），**不要在代码里另写一套坐标** |
| 输出粒度 | **路段级聚合数**：这段路**有多少车、多快、排多长**。**不输出车辆身份**（虚拟检测器同样"只数车、不认车"） |
| 输出字段 | 与**视频感知链路**（`source: "video"`）**逐字段完全一致**：流量 `q_vph`、平均车速 `v_kmh`、密度 `k_vpk`、排队长度 `L_q_m`（见 [`../../docs/数据契约.md`](../../docs/数据契约.md) 第一节）；**只有 `source` 取值不同**，下游**不得按来源分支** |
| 统计周期 | 每 **60 秒**聚合一次（主循环触发周期）；`window_sec` 可配置 |
| 车道归属 | 需要**按车道或按方向**分段时，用 `points.json` 的桩号 + 车道数确定，不要靠代码猜 |
| 禁止事项 | **不得**把"某辆车的身份 / 轨迹"塞进检测器输出——那会破坏"两条数据线不做关联"的口径 |

> **验收挂钩**：M1-2 要求**孪生链路至少 1 条路段**由虚拟检测器产出平均车速与排队长度时序，**≥ 60 个统计点**（即至少 1 小时的仿真时长），且**视频链路同样至少 1 条路段**（`source: "video"`）。
>
> ⚠️ **检测断面的角色（`boundary` / `internal`）决定它能不能被同化**：**只有边界断面允许挂 `calibrator` 回灌**，站前内部路段一个都不许挂——见第九节。

## 五、因素注入接口

读 `stations/factors.json`（池·P 填的 T5 因素表），按时间窗把因素注入孪生。**每个因素的实现方式必须是"改世界"，不是"改结论"**：

| `target` | 注入方式（孪生侧） |
|---|---|
| `c`（通行能力） | 降低对应路段 / 车道的通行能力（限速、车头时距、信号绿信比等实现） |
| `v_f`（畅通速度） | 降低路段限速（大雨、雾天、路面湿滑） |
| `demand`（需求） | 提高某方向的车流生成率（列车集中到达、大型活动散场） |
| `lanes`（车道数） | 封闭车道（违停占道、事故封道、施工） |
| `confidence`（置信度） | 降低检测置信度（能见度差、夜间）——**只影响判级的可用性门，不改变物理世界** |

**接口形状（建议，供开发B / 开发A 对齐）**：

```python
inject_factors(step, factors)   # step = 仿真步；factors = 当前生效的因素列表
                                # 返回：本步实际注入的因素（用于回写 factors_applied）
```

**三条纪律**：

1. **生效与失效都要按 `until` 精确执行**，不要"注入了就不管"；
2. **注入后必须能回写** `segments.factors_applied`——管理端与推荐理由 `why` 要引用它（TC-16 判定"受影响路段出现 `factors_applied`、未受影响路段不变"）；
3. **种子固定**：因素注入的时刻与强度不得依赖随机数，否则场景跑不出一致结果。

## 六、主循环 `loop.py`

**一期运行方式（D8）：孪生驱动的单进程主循环 + 文件快照当契约。**

```text
python work/twin/loop.py --scenario scenario_2
```

| 参数 | 含义 | 建议默认 |
|---|---|---|
| `--scenario` | 场景名（`scenario_1` 常态 / `scenario_2` 峰值 / `scenario_3` 突发 / `scenario_4` 多因素） | `scenario_1` |
| `--seed` | 随机种子，**固定才能复现** | 写进 `scenarios.json` |
| `--duration` | 仿真时长（秒 / 分钟） | 满足 M1-2 的 ≥ 60 个统计点 |
| `--out` | 输出根目录（真孪生写 `<out>/latest/`，路网写 `<out>/sumo/`） | `work/twin/out/` |
| `--no-sumo` | 用 `samples/` 样例数据跳过 SUMO，仅串链路 | 关 |

**真孪生主循环（IKNAER / W1，已实现）**：

```text
python work/twin/loop.py --duration 3900 --seed 42                 # 默认输出 out/latest/（65 个统计点）
python work/twin/loop.py --duration 3900 --seed 42 --out work/twin/out/run_b   # 第二遍对照
```

它会先调 [`sumonet.py`](sumonet.py) 从 `netpack/network_junction.json` 建 `out/sumo/station.net.xml`，再用 TraCI
**1 s 步进、每 60 s 快照**；需求读 `stations/demand.json`（样例/演示值），三类虚拟司机 D1/D2/D3 都真实跑在 SUMO 中；IKNAUH 起再加**全路段背景车流**（`background_source=demo_uniform`，每 60 s 每段 1 辆，演示假设），61 段全部有指标（大屏不再灰档）；
产物为 `out/latest/{segments_twin,vehicles,run_log,twin_timeseries}.json`。**`--no-sumo` 样例路径保留**，
四产物与改造前**逐字节一致**（回归基线）。命令 / 产物 / 实跑证据 / 边界见第十七节。

**每一步做什么**：

| 周期 | 动作 | 交给谁 |
|---|---|---|
| **1 秒** | SUMO 走一步（跟驰 / 排队 / 信号）↔ 自研司机行为体（TraCI：改路线 / 停靠 / 候客）；因素注入 | 孪生自己 |
| **60 秒** | 虚拟检测器聚合 → 四项指标 → 判级 → `segments` 快照 | 调 `work/perception/` |
| **60 秒** | **数据同化**：视频实测（**边界断面**）先落盘，再 `calibrator.setFlow` 回灌给 SUMO 边界来车（**内部路段不灌**） | 调 `calibrate.py`（见第九节） |
| **60 秒** | 时段预约表更新 + 前车再疏导 + 新请求分配 → `routes` 快照 | 调 `work/engine/` |
| **事件** | 有车进入站前围栏：真值位置 → 定位匹配 → 推荐 → 行为体决定是否采纳 | 调 `work/engine/` |
| **持续** | 车辆清单 → `vehicles.json`（仅一期演示用） | 孪生自己 |

> **只有一个时钟**：孪生的仿真时钟。所有指标、判级、推荐都按**仿真时间**打时间戳，所以**同一场景可以完整回放**（TC-13）。**不要混用系统时间。**

## 七、完成判定（一期 DoD）

| 判定项 | 内容 | 怎么证明 |
|---|---|---|
| **M1-1** | **数字孪生可复现**：站前路网 + **三类虚拟司机**在 SUMO 中运行，同一场景跑两遍**关键指标完全一致** | 两遍跑的输出逐字段比对，差异为 0 |
| **M1-2** | **孪生链路至少 1 条路段**由虚拟检测器产出**平均车速与排队长度时序**（**≥ 60 个统计点**）；**视频链路同样至少 1 条路段**（`source: "video"`） | 输出时序文件 + 点位编号；两条链路**各交一份** |
| **M1-9**（视频链路标定） | 孪生侧配合：**视频实测值已落盘并作为孪生边界输入**，到达流率 / `v_f` / `s₀` / 排队阈值 / 服务时长逐项可追溯 | 标定文件 + 孪生输入文件 + 对照记录（TC-19 的偏差部分） |
| **M1-10**（数据同化，一期） | **至少 1 个边界断面**完成数据同化回灌：视频实测经 `calibrator.setFlow` 每 60 s 回灌，**站前内部路段不灌**，**TC-20 四项判定全过** | 回灌日志（含门控触发记录）+ 开 / 关同化对照 + **内部路段仍响应推荐的对照记录**（见第九节） |
| **TC-16** | **多因素生效**：一期 14 类因素中**可模拟的每类**注入后，受影响路段 `factors_applied` 出现，且**等级 / 耗时变化方向正确**（如大雨判级不低于晴天）；**未受影响路段不变** | 逐因素注入前后对比表 |

> **M1-1 的判定标准是"两遍完全一致"，不是"能跑起来"。** 种子、因素时刻、车辆生成都要固定；任何依赖系统时间或未固定随机种子的实现，都会在这一条上翻车。

## 八、用视频链路的实测值标定孪生（**D1′ 的关键衔接，对应手册第 10.13 节**）

**为什么要这一节**：如果孪生是"凭空造出来的世界"，那它演得再好看也只是动画。**用真实视频测出的值去标定孪生的边界条件，孪生才站得住**——这也正是两条链路"互为校验"的那一半。

| 孪生参数 | 从视频链路取什么 | 怎么用 |
|---|---|---|
| 边界到达流率 | 视频断面实测 `q_vph`（分时段） | 作为 SUMO 边界车流的输入曲线，**而不是手填一个数** |
| 自由流速度 `v_f` | 视频链路实测的平峰车速 | 标定值**先落盘**，再交**开发B** 写进 `stations/thresholds.json` 的 `v_f`——**该文件唯一写手是开发B**（判级参数组 + 决策参数组），开发A 只交标定值、不写这个文件（手册第 6.6 节） |
| 饱和流率 `s₀` | 视频链路实测车头时距反推 | 写进通行能力 `c` |
| 排队阈值 | 视频链路实测的排队车头间距 | 校核默认的"约 7 m"【待标定】 |
| 服务时长分布 | 视频链路测量的落客 / 上客停留时长 | 标定落客区服务率 |

**校验（必须留证）**：同一路段、同一时段，**孪生链路输出 vs 视频链路实测**并排写进自测报告——**允许有偏差，但必须写出偏差方向和量级**，以及"**哪一侧更可信、为什么**"（**TC-19**）。

**三条纪律**：

1. **先落盘再喂**：视频链路测出来的值**先写成文件**（可追溯），再作为孪生的输入——**不许手抄一个数进去**；
2. **只标边界，不调中间输出**：只标定**边界条件与基础参数**（上表五项），**不许**用视频去"调"孪生的中间输出——那就成了对答案；
3. **写清适用性**：一期视频是**样本视频、非本站现场**，所以标定结论的适用范围必须写明；**二期用现场实时流重标**（视频源换源，重做 `calibration.json`）。

> **交付挂钩**：手册第 10 章的本章交付包含"**用视频实测标定后的边界条件与参数**"；开发A 的 W6 判定要求"**标定值先落盘再进孪生输入，可追溯**"。

## 九、数据同化：把视频实测回灌给孪生（**"给孪生接一只真实的眼睛"，对应手册第 10.14 节**）

**业主的问题**："YOLO 获得的路段拥堵情况可以反馈给 SUMO 的路段吗？就是我给 SUMO 接一个真实的眼睛，SUMO 的路段按 YOLO 的路段情况来进行模拟。"
**答案：能，SUMO 有专门机制（`<calibrator>`），而且一期就要做。**

**机制**：SUMO 的 **`<calibrator>`**（官方定位：**基于感应线圈实测数据动态调整仿真**）挂在某条 edge / lane 上，给出目标 **`vehsPerHour`（流量）+ `speed`（车速）**：

| 它做什么 | 说明 |
|---|---|
| 流量对齐 | 实测**多了就删车、少了就补车** |
| 车速对齐 | 该路段限速被调成给定 `speed`（类似可变限速） |
| 防虚假排队 | 若产生"这个流量下不该有的排队"，按 `jamThreshold` **清掉多余车辆**，防止虚假拥堵向上游扩散 |
| 可在线改 | TraCI `calibrator.setFlow(calibratorID, begin, end, vehsPerHour, speed, typeID, routeID, …)`；可用 `getPassed` / `getInserted` / `getRemoved` / `getVehsPerHour` **对账** |

### 9.1 分层原则（**最容易做错，必须写死**）

| 位置 | 灌不灌 | 为什么 |
|---|---|---|
| **围栏外 → 站前的上游边界断面**（`points.json` 里 `role: "boundary"`） | **灌**（YOLO 实测流量 + 车速） | 决定"来多少车、多快"——**"真实的眼睛"该管的事** |
| **站前内部路段**（落客通道 / 候客区 / 离站方向，`role: "internal"`） | **不灌**（一个都不许挂） | 必须让 **SUMO + 自研行为体自由演化**，**否则孪生变成录像回放、推荐再也改变不了路况，"同一输入跑三遍只切推荐"的对照实验直接失效** |

一句话：**"真实的眼睛 + 可被引导的下游"。**

### 9.2 门控与安全（**硬规则**）

1. `confidence < 0.6`【待标定】或 `data_age_s > 120 s` → **该断面停止回灌**，退回默认需求，并留日志；
2. 回灌值必须**先落盘再喂**（可追溯，**不许手算一个数**）；
3. 连续 N 次（建议 **3 次**【建议值】）回灌后偏差仍超标 → **自动关闭该断面的同化**并告警（二期熔断，**M2-9**）。

### 9.3 一期范围与怎么跑

- **范围（一期）**：至少 **1 个边界断面**（**M1-10**）；二期扩到**全部边界断面在线闭环 + 熔断**（**M2-9**）。
- **配置从哪来**：开关在 `stations/scenarios.json` 的 **`assimilation`**（`enabled` / `edges` / `period_s` / `gate`），映射在 `stations/points.json` 的 **`role` + `sumo_edge_id`**；**`edges` 里只许出现 `boundary` 断面映射出来的 edge**，写进 `internal` 的 edge 视为配置错误、脚本**报错退出**（见 [`../../docs/数据契约.md`](../../docs/数据契约.md) 第 6.1 / 6.2 节）。
- **怎么跑**：`loop.py` 每 60 s 调一次 `calibrate.py`；开 / 关对照靠 `assimilation.enabled`。

```text
视频链路边界断面实测（q_vph / v_kmh）→ 先落盘（可追溯）
   → 门控：confidence ≥ 0.6【待标定】且 data_age_s ≤ 120 s？
        ├─ 不满足 → 该断面停止回灌，退回默认需求 + 日志
        └─ 满足   → traci.calibrator.setFlow(calibratorID, begin, end, vehsPerHour, speed, …)
                      → SUMO 边界来车（只灌 boundary 断面）
```

### 9.4 完成判定

| 判定项 | 内容 |
|---|---|
| **M1-10**（一期） | 至少 **1 个边界断面**完成数据同化回灌，**TC-20 四项判定全过** |
| **M2-9**（二期） | **全部边界断面**在线闭环 + 熔断可用 |
| **TC-20①** | 被同化的边界断面：**孪生流量与视频实测偏差 ≤ 15%**【待标定】、**平均车速偏差 ≤ 20%**【待标定】 |
| **TC-20②** | **站前内部路段仍能响应推荐**（开 / 关推荐时内部路段指标出现差异）——证明没被钉死 |
| **TC-20③** | 关闭同化后回到默认需求 |
| **TC-20④** | 门控生效：把 `confidence` 压到 0.6 以下或 `data_age` 抬过 120 s，该断面**停止回灌**且日志可见 |

> **答辩口径**：可以讲"**给孪生接了一只真实的眼睛，孪生跟着现实走**"；**不得**因此把孪生的数值说成"实测"——回灌值本身来自**样本视频（非本站现场）**，孪生算出来的仍一律标"**演示数据（模拟）**"。

## 十、常见坑（**都踩过，别重复**）

| 坑 | 现象 | 对策 |
|---|---|---|
| **TraCI 步进开销** | 每步都 `traci.simulationStep()` + 频繁 `traci.*` 查询，仿真比实时还慢；加 `sumo-gui` 更慢 | ① 用**无界面** `sumo` 跑批量，`sumo-gui` 只看；② 合并查询（一次 `traci.vehicle.getIDList()` 拿全量再筛），**不要一辆车一辆车地问**；③ 检测器聚合放到 60 s 触发点，不要每秒算 |
| **种子没固定** | 同一场景跑两遍结果不一样，M1-1 直接不过 | ① `--seed` 写进 `scenarios.json`；② 车流生成、司机类型分配、因素注入**全部走同一个种子**；③ 不要在代码里用未播种的 `random` |
| **输出目录不存在 → 静默失败** | 命令**报成功**，产物文件根本没生成（上游仓已实测复现过同类缺陷） | ① `loop.py` 开头 `os.makedirs(out_dir, exist_ok=True)`；② 每次运行后**断言产物文件真的存在**，**别只信退出码**；③ 压测脚本里加"产物存在性断言" |
| 中文路径 | 走 OpenCV 的截图 / 标注图写入失败 | 见 [`../assembly/现状核实.md`](../assembly/现状核实.md) 4.3；能搬纯英文路径最好 |
| 路网与底图对不上 | SUMO 里的路与高德底图差一条街，后面全错 | 先过 **TC-15 路网核对**（T2 表逐条打勾），再写决策代码 |
| 手改 `.net.xml` | 下次重建丢改动 | 改**输入**（OSM 切片 / 补画记录）或**转换参数**，重跑 `netbuild.py` |
| **把标定值手抄进孪生** | 说不清这个数从哪来，TC-19 的偏差无法复核 | 视频链路实测值**先落盘**（写成文件）再喂孪生；**不许**用视频去"调"孪生的中间输出（手册 10.13） |
| **别把内部路段也挂上 `calibrator`** | 孪生被**钉死**——推荐再也改变不了路况，"同一输入跑三遍只切推荐"的对照实验**直接失效**，整个项目的核心结论证明不了 | **只给 `points.json` 里 `role: "boundary"` 的断面挂 `calibrator`**，`role: "internal"` 一个都不挂；**TC-20 第②项就是抓这个**（开 / 关推荐时内部路段指标必须出现差异） |
| **同化把 `confidence` / `data_age` 门控漏掉** | 数据不可用还硬灌，孪生跟着脏数据走，且事后查不出为什么 | 门控写进 `scenarios.json` 的 `assimilation.gate`（`confidence_min` = 0.6【待标定】、`data_age_max_s` = 120 s）；**每次停灌都要留日志**（TC-20 第④项） |

## 十一、大文件

- **能进仓库**：`stations/sumo/*.net.xml`（小文本、可重建）、`samples/` 里的最小样例；
- **不能进**：OSM 原始大文件、地图瓦片、仿真录屏、`out/` 运行产物 —— 放共享盘或 `.gitignore`。

---

## 十二、真网断面角色候选：从 `network_junction.json` **自动推导**（IKMS19）

> **为什么**：数据同化只能灌**边界断面**（第九节），而"哪 61 段里哪些是边界"此前只有前端 mock 候选
> （`stationZ.ts` 的 `sections`，5 boundary / 6 internal，标「候选·待冻结」）。本单把它做成
> **从真网拓扑自动推导**的清单，**不写死段号 / 坐标 / 站名** —— 换站只改 [`site-ranges.json`](site-ranges.json)。

**推导规则**（[`sections.py`](sections.py)，与生产方、引擎同口径）：

| 步 | 规则 | 依据 |
|---|---|---|
| 1 | 读站点范围登记表 → `out_json` 指向的真网产物（本站 [`netpack/network_junction.json`](netpack/network_junction.json)，61 段 / 44 节点） | 段数必须等于登记表 `seg_target`，否则**报错退出**（不在不完整路网上定断面） |
| 2 | **boundary 节点** = `nodes[].boundary == true`；标记缺失时退化为**无向度数 1**（并写明来源） | 生产脚本 `build_junction_pack.py` 的标记口径就是"度数为 1" |
| 3 | **boundary 断面** = 边两端**任一节点是 boundary 节点**；其余 **internal** | 即"围栏外 → 站前的上游边界断面"在拓扑上的落点；与 `edges[].boundary` 对账（不一致只留痕） |
| 4 | 每段写 `role` + `basis`（哪个端点是边界节点 / 两端度数），并补 `flow_direction`（inbound / outbound / bidirectional）供人工裁定参考 | `sections_candidate.json` 的 `sections[]` |

**本站推导结果**（2026-10-18 实跑）：**boundary 11 段 / internal 50 段**（boundary 段：
`SZ-001、003、004、009、015、018、019、022、026、055、056`；方向分布 inbound 3 / outbound 3 /
bidirectional 5）。产物固定 `status: "候选·待业主/队长签字冻结"`，**签字前不得宣称 M1-10 通过**
（Issue IKMS19 第五节第 1 条）。**硬规则：internal 永远不许挂 calibrator / 回灌**，由
[`tools/check_assimilation.py`](tools/check_assimilation.py) 硬断言（本单专属一）。

**与已有产物的关系（不混命名空间）**：

| 产物 | 关系 |
|---|---|
| [`netpack/network_junction.json`](netpack/network_junction.json) | 本清单**唯一数据源**（真网 `SZ-###`，几何/拓扑真值，只读） |
| 站点包 `stationZ.ts` 的 `sections`（IKM4TE mock） | 前端 mock 候选：**5 boundary**（`SZ-001/003/004/009/015`，全部落在本自动推导的 11 条内）+ **6 internal**（`SZ-018/019/022/024/054/055`）。差异：mock 把 `SZ-018/019/022/055` 按「站前/停车场内部」语义标 internal，而拓扑口径判 boundary（这 4 段都有一端是度数 1 的边界节点）→ **签字冻结时必须逐条裁定**（语义围栏 vs 拓扑边界），本单不擅自改 mock、也不宣称冻结 |
| [`../engine/realnet.py`](../engine/realnet.py) | 引擎侧同口径边界推导（OD 用）；两边都按 `nodes[].boundary` / 度数 1，**互不 import** |
| `stations/network.json` | **7 节点 / 17 边占位件**（`SEG-###` 样例网）——**真网断面不读它**，也不与 `SZ-###` 混算 |
| `stations/points.json` | `role` / `sumo_edge_id` 是**样例站点包**的占位映射（`DET-01` ↔ `E-001`），只给机制示例用（见下节） |

单独跑：`python work/twin/sections.py`（只打印计数）／`python work/twin/sections.py --write`（写
`out/latest/sections_candidate.json`）。正式入口仍是 `run_assimilation.py`（第十五节），它会把
`ts` 从视频快照派生后写同一份清单。

## 十三、运行时同化：只灌 boundary、门控 / 停灌日志 / 偏差（IKMS19）

**数据流**（[`calibrate.py`](calibrate.py) 的 `build_assimilation()` 真路径；旧样例路径
`build_state()` 保留，`loop.py --no-sumo` 的输出逐字节不变）：

```text
断面候选清单（sections.py，61 段 role）
   + 视频快照 <仓库根>/work/perception/out/latest/segments_video.json（SZ-005 / SZ-024）
   + 孪生基线（baseline.py：真孪生快照 `out/latest/segments_twin.json` 优先；缺失时才退到视频观测段照抄 + 空载网络基线，均明示演示）
   + 场景开关 stations/scenarios.json 的 assimilation（enabled / edges / period_s / gate）
        → 逐段判定：internal 永久拒绝 → 场景开关/白名单 → 有没有观测 → 门控 → 偏差
        → out/latest/assimilation/assimilation_state.json（契约第三节信封 + edges；IKNAUN 后同化产物统一分目录）
        → out/latest/assimilation/assimilation_log.json（逐段 gate 求值 / 停灌原因 / 回灌值 / calibrator 计划）
```

**门控与停灌原因码**（`gate.reason`；门控拒绝再加 `gate.cause` 说明是哪个门）：

| 情形 | `assimilating` | `gate.reason` | 备注 |
|---|---|---|---|
| 门控通过（`confidence ≥ confidence_min` 且 `data_age_s ≤ data_age_max_s`） | `true` | `null` | 有 `last_apply` + `deviation` |
| 置信度不足 / 数据过期 | `false` | `gate_rejected` | `gate.cause = confidence_low` / `data_age`（两者都不过用 `+` 连接） |
| internal 断面 | `false` | `internal_not_allowed` | **硬规则，永远**（代码写盘前再断言一遍） |
| 场景 `enabled:false` | `false` | `assimilation_disabled` | 即"退回默认需求"（TC-20 第③项） |
| 该段不在场景 `edges` 白名单 | `false` | `edge_not_enabled` | |
| 场景 `edges` 未落到本站真网段号 | `false` | `config_unresolved` | 占位件（如 `E-001`）不猜映射 |
| boundary 段没有视频/断面观测 | `false` | `no_observation` | 不编造回灌值 |

**偏差口径**：`deviation.q_pct = |obs−base|/base×100`、`v_pct` 同理（2 位小数）。基线是**空载**（`q=0`、
`v=null`）时相对偏差**未定义**，写 `null` + `note`，**不造分母**；真孪生基线接上后自动变成可比偏差。

**契约与接口**：`assimilation_state.json` 保留契约第三节的 `ts / is_simulated / edges[]`（每段
`segment_id / role / assimilating / gate / last_apply / deviation`），信封上**只增不删**地补
`enabled / period_s / mode / gate / counts / applied_count / scenario_id / note`（Issue 要的
`enabled` / 偏差 / `gate_reason` 都在里面；偏差与 `gate_reason` 用契约既有字段名
`deviation.q_pct|v_pct` 与 `gate.reason` 表达，不另造第二套）。`run_assimilation.py` 在**默认输出目录**跑时
还会把同一份状态发布到接口层读的 `work/twin/out/assimilation_state.json`（`work/assembly/traffic.py`
的 `TWIN_ASSIMILATION`）。⚠️ **接口层已知小缺口**：`traffic.py` 目前只把
`confidence_low / data_age / deviation_fuse` 映射成页面的 `gate_reason`，其余原因码会显示成「门控中」+
`reason` 字符串——精确文案归接口层（IKMS12/IKMS17 那侧）补，本单不改别人的代码。

**回灌纪律**：回灌值**先落盘**（`assimilation_log.json` 的 `applied[]`）再喂；本期只产出
`calibrator_plan[]`（`calibrator.setFlow` 的 vehsPerHour + speed 计划），**没有实际下发 SUMO**
（站点 Z 的 `stations/sumo/*.net.xml` 未构建、`loop.run_with_sumo` 仍是骨架——见第十六节阻塞），
**不假装回灌到仿真**。二期熔断（M2-9「连续 N 次偏差超标自动关闭」）需要的逐周期偏差序列，
等真孪生主循环跑起来才能累积；本单只把 `deviation` 与日志字段留好。

## 十四、多因素闭环：F01~F14 → segments → factors_applied（IKMS19）

**输入**（[`factors.py`](factors.py) + [`scenario.py`](scenario.py) 真路径）：

| 数据 | 用法 |
|---|---|
| [`../../stations/factors.json`](../../stations/factors.json) | F01~F14 登记表：名称 / `targets` / `demo_multipliers` / 来源阶段 / 实现人。**因素值不写死在代码里**；登记表 14 类必须齐全，否则报错 |
| [`../../stations/scenarios.json`](../../stations/scenarios.json) | S1~S4：`seed`、`switches`、`assimilation`（开关/edges/gate）、`factors` 注入事件（`factor_id/target/multiplier/from/until[/segment_id]`） |

**注入规则**（"改世界，不改结论"）：

| `target` | 注入到哪些段 | 改什么 | 备注 |
|---|---|---|---|
| `c` / `lanes` | 全段（带 `segment_id` 时只该段） | `c_vph = c_base_vph × ∏multiplier`（保底 `grading.factor_floor`），`x = q_vph/c_vph` | **同一因素多 target 时容量只乘一次**（防 `lanes+c` 重复折算） |
| `v_f` | 全段（可带段号） | `v_f_kmh × multiplier`；实际车速不得超过新 `v_f`（`v = min(v, v_f新)`） | 方向：`v_f↓`、畅通耗时 `L/v_f`↑、实际行程时间不降 |
| `demand` | **boundary 候选段** | 文件级**只登记注入事件**（`factors_applied` 出现），不改假的 q/v；需求效果需 SUMO 需求生成器 | 一期**如实标阻塞**，不编造需求效果 |
| `confidence` | **有指标数据的段** | `confidence × multiplier`（只影响判级可用性门，不改物理世界） | 判级由 `level.py` 的可用性门处理 |

**判级**：注入后**只调** [`../perception/level.py`](../perception/level.py) 的 `grade()`（唯一实现，
本模块 import 只读，不复制阈值/判级逻辑）；硬触发因素 F07 / F08 命中
`thresholds.grading.hard_trigger_factor_ids` → 直接跳 `hard_trigger_level=4`。

**纪律**：未生效的因素**不写进 `factors_applied`**（不写 `multiplier: 1.0` 占位）；
`factors_applied` 子字段保持契约形状（`factor_id / name / target / multiplier / until`）；
每个因素的**来源（factors.json 的 source_stage1/2 + 场景 S1~S4）与生效区间（from~until）**
写在 `factors_report.json` 的 `injections[]` 里，不往契约字段里硬塞新键。生效窗口按
**场景因素 `from` 的最晚值**派生"演示评估时刻"（不读系统时钟）；不在窗口内的因素自动失效。

**命名空间纪律**：场景里 `SEG-003` 这类**样例网段号**在真网模式下解析不到 → 记
`未落地（不猜映射、不混命名空间）`，不注入（例如 S3 的 F07）；机制示例模式（`--mode sample`）
才按样例站点包 `points.json` 把它桥到 `SEG-###`。

**产物**：`out/latest/assimilation/factors_report.json`（catalogue + 四个场景各自的生效/未落地因素 +
`segments_before.json` / `segments_after.json` 的逐因素方向校验）+ 两份 segments 快照
（before = 基线、after = 注入后，均 `is_simulated:true` + note）。

## 十五、一键命令与产物（IKMS19；IKNAUN 后路径/参数以下表 + 第十八节为准）

```powershell
# 0) 真孪生主循环（W1）：产出 out/latest/segments_twin.json（同化基线的首选来源）
python work/twin/loop.py --duration 3900 --seed 42

# 1) 真网模式（默认）：断面候选 + 同化状态/日志 + 因素报告 + before/after
#    --twin 缺省自动发现 out/latest/segments_twin.json；找不到才退回空载演示基线
python work/twin/run_assimilation.py
python work/twin/run_assimilation.py --twin work/twin/out/latest/segments_twin.json
python work/twin/run_assimilation.py --no-twin   # 强制空载基线（自检/降级演练）

# 2) 机制示例（旧 SEG-### 样例，非本站真网）：把同化/门控/因素整条机制跑通
python work/twin/run_assimilation.py --mode sample

# 3) 自检（真跑，输出 PASS/FAIL/BLOCKED）
python work/twin/tools/check_assimilation.py     # TC-20 四项 + 真基线前置 + 本单专属一/二
python work/twin/tools/check_factors.py          # TC-16 逐因素注入

# 4) 文档与契约门禁（先 git add）
python scripts/doc_gate.py
```

| 参数 | 含义 | 默认 |
|---|---|---|
| `--mode network\|sample` | 真网 `SZ-###` / 机制示例 `SEG-###`（两套产物分目录，不混命名空间） | `network` |
| `--scenario` | `S1~S4` / `scenario_1~4` / `常态~多因素`（读 `stations/scenarios.json`） | `S4` 多因素 |
| `--out` | 输出目录（**IKNAUN 起分目录**，不再覆盖主循环 `out/latest/run_log.json`） | `out/latest/assimilation`（真网）/ `out/latest/assimilation/mechanism_demo`（机制示例） |
| `--twin` | 真孪生快照路径（同化基线首选） | 自动发现 `work/twin/out/latest/segments_twin.json` |
| `--no-twin` | 强制不用真孪生快照（退回空载基线） | 关 |
| `--video` | 显式指定视频快照 | 自动：本工作树 → 同级 git 主 checkout（只读参考） |
| `--site` | 站点 id | `site-ranges.json` 的 `default_site` |
| `--eval-ts` | 因素评估时刻（覆盖派生；network / sample 都生效） | 从场景因素 `from` 派生 |
| `--obs-confidence` / `--obs-data-age-s` | **自检注入**的门控测试值（TC-20④；只改本次内存，不改输入文件） | 不覆盖 |

**真网模式实跑摘要**（IKNAUN 后，真孪生快照在场时；2026-10-18 可复现）：

```text
断面候选：61 段（boundary 11 / internal 50）· 状态：候选·待业主/队长签字冻结
基线：真孪生快照（baseline_source=twin.latest，sha=15c5a1d6…，ts=2026-01-01T01:05:00+08:00，auto:out/latest/segments_twin.json，61 段）
视频快照：在场（sibling:hubflow 的 work/perception/out/latest/segments_video.json，SZ-005/SZ-024）
同化：回灌 0 条 · boundary 11 / internal 50
同化归因：boundary 停灌原因分布：场景 edges 未落地 11 条；internal 观测被拒 2 条（SZ-005、SZ-024；internal_not_allowed 硬规则）
因素：生效 3 条（S4：F01 c、F03 demand、F10 demand）· 未生效 0 条 · 受影响段 61
阻塞：清单未签字 / 无 boundary 观测 / calibrator 未下发 / 站点包 edges 仍是占位 E-001 /
      本工作树无视频快照（只读引用同级 checkout）；真孪生基线已接入（不再是阻塞）
```

> 同化归因按 `assimilation_state` 的**实际 `enabled` / `gate.reason` 分布 / 观测角色**输出，
> 不再写死"internal 永不回灌 + 无 boundary 观测"：例如 `--scenario S3` 会归因为
> 「场景关闭同化（enabled=false → 退回默认需求）」。混合快照（boundary 已回灌 + internal 被拒）时
> 按「已回灌 N 条 / internal 观测被拒 M 条」如实写，不会再说"故回灌 0 条"。
> **真孪生基线接入见第十八节**（`--twin` / 自动发现 / `baseline_source` / 产物分目录）。

**机制示例实跑摘要**：断面 2 段（boundary 1 / internal 1）→ **回灌 1 条**（`SEG-001`，gate 通过，
`deviation` 0%/0% 因样例基线==样例声明观测）；`SEG-002` internal 观测被拒
（`internal_not_allowed`）；S3（关同化）→ 回灌 0 条。`--eval-ts` 在 sample 模式同样生效
（例如 `--eval-ts 2026-01-01T09:00:00+08:00` 会让 S4 的 3 条因素全部落在窗口外 → 生效 0 条）。
**结论只用于验机制，不是本站结果**。

**产物**（IKNAUN 起均在 `out/latest/assimilation/`，`out/` 已 gitignore，不进仓库）：

| 文件 | 内容 |
|---|---|
| `sections_candidate.json` | 61 段 role + 依据 + `status=候选·待签字冻结` + 与生产方标记对账 |
| `assimilation_state.json` | 契约第三节信封 + edges + **`baseline`（baseline_source / twin_snapshot_sha）**（接口层读；默认目录跑时同时发布到 `out/assimilation_state.json`） |
| `assimilation_log.json` | 逐段观测/基线/门控/决定/偏差；`applied[]` 回灌值；`dropped[]` 停灌原因；`calibrator_plan[]`（未下发）；`baseline` 溯源 |
| `factors_report.json` | 因素登记表 + S1~S4 注入 + 未落地原因 + `injections[].direction_checks` |
| `segments_before.json` / `segments_after.json` | 因素注入前后快照（before 含 **`baseline_source` / `twin_snapshot.sha256` / 每段 `baseline_used`**；after 含 `factors_applied` 与修正后的 `c/x/v_f/level`） |
| `run_log.json` | 计数 / **真孪生快照路径+sha** / 产物字节数 / `blockers[]`（本次运行的**真实阻塞清单**） |

**确定性**：不读系统时钟；`ts` 从视频快照 ts / **孪生快照 ts** / 样例 ts / 场景因素 `from` 派生；
所有集合按段号排序、不依赖 `set` 迭代顺序。**同输入两遍，7 个产物 sha256 全一致**
（`check_assimilation.py` 的 `DETERMINISM` 项实跑留证）。

## 十六、本单口径、自检与遗留阻塞（IKMS19）

### 16.1 口径（红线）

1. **不冒充实测**：回灌值来自**样本视频**（非本站现场）；同化后的孪生数仍是"演示数据（模拟）"。
   `is_simulated:true` 恒在，所有产物带 `note`；
2. **空载基线 != 孪生模拟结果**：`baseline.py` 造的空载网络基线逐段标
   `baseline_kind="empty_load_demo"`、`available:false / level:0（数据不可用）`，
   **不许当"畅通"上色**（TC-11 同口径），更不许说成孪生仿真的结果；
3. **不混命名空间**：真网只用 `SZ-###`（61 段），旧 7 节点样例网 `SEG-###` 只出现在
   `samples/` + 机制示例模式；两套产物分目录、`run_log.mode` 区分；`assimilation.edges` 里写
   `internal` 段号 → **报错退出**（契约 §6.2）；
4. **不宣称 M1-10 通过**：清单未签字冻结 + 真网无 boundary 观测 + 场景 `assimilation.edges` 仍是占位 →
   `assimilation_state` 只有**机制级**证据，M1-10 / TC-20① 记 **BLOCKED**（`check_assimilation.py`
   打印 BLOCKED，不当 PASS）；
5. **不编造需求效果**：`target=demand` 的 6 类因素只登记注入事件与 `factors_applied`，
   方向/等级效果记 BLOCKED（需 SUMO 需求生成器）。

### 16.2 自检实跑（2026-10-18）

| 命令 | 结果 |
|---|---|
| `python work/twin/run_assimilation.py` | exit 0；61 段候选 / 11 boundary / 回灌 0（按实际 `enabled`+`config_unresolved` 归因）/ 因素 3 条生效 |
| `python work/twin/run_assimilation.py --scenario S3` | exit 0；同化归因=「场景关闭同化（enabled=false → 退回默认需求）」（不再误写成 internal/无观测） |
| `python work/twin/run_assimilation.py --mode sample` | exit 0；2 段 / 回灌 1 条（机制示例） |
| `python work/twin/run_assimilation.py --mode sample --eval-ts 2026-01-01T09:00:00+08:00` | exit 0；`--eval-ts` 在 sample 模式生效（S4 的 3 条因素全部落到窗口外 → 生效 0 条，不再静默忽略） |
| `python work/twin/tools/check_assimilation.py` | **8 项 PASS · 1 项 BLOCKED · 0 项 FAIL**（IKMS19 当时）；**IKNAUN 后为 9 PASS/1 BLOCKED**（+ 真孪生基线前置 `TC20-1-precond`，见 18.5）；TC-20②③④ + 本单专属一/二 + 机制示例① + 真网①判据自测 PASS；真网 TC-20① 按实际数据 BLOCKED（补上 boundary 观测/放开 edges 后自动转 PASS，不翻 FAIL） |
| `python work/twin/tools/check_factors.py` | **8 项 PASS · 6 项 BLOCKED · 0 项 FAIL**；F01/F02/F04/F05/F06/F07/F08/F09 机制 PASS（F07/F08 硬触发跳 level=4）；F03/F10/F11/F12/F13/F14（demand 类）BLOCKED |
| 旧样例链路回归 `python work/twin/run.py --sample` | 产物与改造前**逐字节一致**（`segments/vehicles/assimilation_state/run_log` 四个文件 sha256 相同） |
| `python scripts/doc_gate.py` | 8/8 通过（八组门禁） |

### 16.3 遗留阻塞（如实登记，不编数）

| # | 阻塞 | 影响 | 解锁条件 |
|---|---|---|---|
| 1 | **断面清单未签字冻结** | 不得宣称 M1-10 / TC-20① 通过 | 业主/队长签字冻结 `sections_candidate.json`（含 mock 5/6 与拓扑 11/50 的逐条裁定）→ IKMHMX |
| 2 | **视频只覆盖 2 段且都是 internal**（`SZ-005`/`SZ-024`） | 真网 boundary 无观测 → 回灌 0 条；TC-20① 偏差不可核 | 上游给 **boundary 段**的视频实测或断面计数（或补摄像头到 boundary 段） |
| 3 | ~~同化侧未接真孪生基线~~ **已解锁（IKNAUN）**：`run_assimilation.py --twin` + 自动发现 + `baseline.py` 优先真孪生快照（`baseline_source=twin.latest` / `twin_snapshot_sha` / 每段 `baseline_used`），见第十八节 | 同化偏差分母已有真孪生前置；但 boundary 观测仍缺 → 回灌仍 0 条 | 已交付；剩余见第十八节遗留（boundary 观测 / 清单签字 / edges / calibrator 接线） |
| 4 | **calibrator 未实际下发** | 本单只落 `calibrator_plan`，没有 `traci.calibrator.setFlow` 实灌 | IKNAER 已具备真 SUMO 网与主循环（第十七节）；缺的是主循环内调用 `calibrator.setFlow` 的回灌实现（IKMS19 范围） |
| 5 | **站点包 `assimilation.edges` 仍是占位 `E-001`**（7 节点样例网命名空间） | 真网解析不到 → `config_unresolved`；即使有观测也不会被开白名单 | 人工把 `stations/scenarios.json` 的 `edges` 换成 boundary 候选的 `SZ-###`（本单不改 `stations/`） |
| 6 | **demand 类因素（6 类）尚未接入主循环**：IKNAER 已交 `demand.py` 真路径（T3 列车到达 × T4 比例 → 60 s 到达流率，见 17.3） | F03/F10 等因素的**需求倍率**还没注入主循环（factors 注入归 IKMS19），方向/等级效果不可验 | 同化/因素侧把 `factors_applied` 接入真孪生主循环（IKMS19） |
| 7 | **本工作树无视频快照**（`work/perception/out/` 是 gitignore 运行产物） | 只读引用**同级 git checkout** 的产物；换机器验收要先跑感知链路 | 验收机上先跑 `work/perception/run_chain.py` 生成 `segments_video.json` |
| 8 | **TC-14 / TC-13（场景三跑 / 两遍一致）** | IKNAER 已举证 **TC-13 孪生侧两遍逐字节一致**（17.4）；TC-14「同一场景三跑、只切推荐」仍需真孪生 + 引擎真网（IKMS11）联调 | W1 真孪生（已具备）+ 引擎真网联调（另单） |

> **与 `stations/network.json` 占位件的关系**：本单所有真网产物（断面 / 同化 / 因素）**只读**
> `netpack/network_junction.json`（61 段真网）；`stations/network.json` 仍是 IKLLX2 的 7 节点
> / 17 边占位件（`SEG-###`），**不参与真网链路**，也不手改它（归 `map_ingest.py` / 契约收口）。
> 机制示例模式才用 `stations/*.json` 的样例占位件（`E-001 ↔ SEG-001`），并且全程标「机制示例·非本站真网」。


---

## 十七、W1 真孪生主循环（IKNAER + IKNAUH：站点 Z 全 61 段 + D1/D2/D3 + 65 点时序）

> **一句话**：在真网 61 段上把 SUMO 真正跑起来——1 s 步进、每 60 s 一帧快照、`--duration 3900` 出 **65 个统计点**，
> 三类虚拟司机 D1 送客 / D2 接客 / D3 往返都真实运行在 SUMO 中；同一命令两遍 `segments_twin.json` /
> `twin_timeseries.json` **逐字节一致**；`--no-sumo` 样例链路四产物**逐字节不变**。
> **IKNAUH 起再加全路段背景车流**（background_source=demo_uniform，演示假设）：每 60 s 每段 1 辆，61 段全部有指标（大屏不再灰档）。
> 所有数值仍是**演示数据（模拟）**：需求/背景车流来自样例与演示假设（真实需求归 IKMHMX），不是实测。

### 17.1 一键命令

```powershell
# 0) 环境：SUMO 1.28（sumo / netconvert / traci；本机 $env:SUMO_HOME=D:\app\SUMO）
sumo --version; netconvert --version; python -c "import traci"

# 1) 建/重建 SUMO 路网（可一键重建；.net.xml 在 out/，不提交）
python work/twin/sumonet.py                        # -> work/twin/out/sumo/station.net.xml

# 2) 真孪生主循环（第 1 遍，默认 --out work/twin/out -> 产物在 out/latest/）
python work/twin/loop.py --duration 3900 --seed 42

# 3) 第 2 遍（不同 out 目录）-> 逐字节比对
python work/twin/loop.py --duration 3900 --seed 42 --out work/twin/out/run_b
certutil -hashfile work\twin\out\latest\segments_twin.json SHA256
certutil -hashfile work\twin\out\run_b\latest\segments_twin.json SHA256

# 4) 自检（实跑两遍 + 产物断言，输出 PASS/FAIL/BLOCKED）
python work/twin/tools/check_w1.py

# 5) 样例链路回归（四产物必须与改造前逐字节一致）
python work/twin/loop.py --no-sumo --out work/twin/out/sample_check
```

### 17.2 真网 -> SUMO 路网（`sumonet.py`）

| 项 | 口径 |
|---|---|
| 输入 | 只有 `netpack/network_junction.json`（44 节点 / 61 段，几何真值来自 OSM 切片）；站名/段数/路径读 `site-ranges.json` 登记表，脚本不写死站名/段号/坐标 |
| 边 id | **直接用 `SZ-###`**（与站点包 / 感知 / 引擎同一命名空间）；反向补边 `SZ-###_rev` 只参与仿真、**不新增段号**，检测器并回原段统计 |
| 双向补边 | 61 段里 `oneway=yes` 保持单向；非单向段共 **39** 条，其中 **6 条已有真实反向段（SZ-020 / SZ-045~SZ-048 / SZ-058）**，实际**补 33 条反向边**——OSM 缺 `oneway` 标记按双向理解，这是 SUMO 路网能连通（`boundary -> boundary` 可通行路线 43 条）的前提 |
| 缺值回落 | `lanes` 缺 -> 默认 2 道（标 `default:demo_lanes=2`）；`speed_limit` 61 段全为 null -> 站点包 `thresholds.grading.defaults.v_f_kmh`（标来源）；**逐条来源写进 `out/sumo/station_netmeta.json`**，汇总进 `run_log.net_build` |
| 坐标 | 真网只给 WGS-84 `lon/lat` -> 局部切平面投影成米制 `x/y`（锚点 = 全部节点均值，从数据派生，不写死坐标）；`xy_to_lonlat` 严格互逆，供 `vehicles.json` 反算 WGS-84 |
| 可重建 / 确定性 | 抹掉 netconvert 生成时间戳与本机路径回显后，**同一输入两次建网 sha256 一致**（2026-10-18 本机：`d1bb71b4ea7cea61...`，180790 B，44 节点 / 61 正向 / 33 反向） |
| 命令 | `python work/twin/sumonet.py`；换输出目录 `--out-dir`；只校验已有网 `--sumo-net` |

> `.net.xml` **不提交**（`out/` 已 gitignore，换机用 `sumonet.py` 重建；SUMO 版本差异可能影响轨迹细节，两遍一致性在本机同版本内判）。

### 17.3 主循环：需求、司机、全路段背景车流、快照口径

- **单一仿真时钟**：`ts = DEMO_BASE_TS(2026-01-01T00:00:00+08:00) + 仿真秒数`，不读系统时间；SUMO 种子 `--seed 42` 固定。
- **需求（`demand.py` 真路径）**：读 `stations/demand.json`（**样例/演示假设值**，真实需求归 IKMHMX）——
  T3 `trains[].arrivals` 按到达后 300 s（演示假设）内均匀疏散，T4 `mix.driver_type_ratio` 拆 D1/D2/D3，
  `od[].demand_vph` 只取数值作网络级背景流率。**OD 端点 `N-01` 是 7 节点样例网命名空间、与真网 `N-001` 不一致 -> 不猜映射**，
  路线改由真网 boundary 断面 + SUMO `findRoute` 生成（`demand_source` / `od_rejected` 都写进 `run_log`）。
- **三类虚拟司机**：每类都在 SUMO 里真实运行（vType 只差 `speedFactor`：D1 1.0 / D2 0.95 / D3 0.9；跟驰/排队交给 SUMO）；
  `vehicles.json` 的 `driver_type` 与 `vehicle_id` 前缀（`twin-D1-####` 等）一一对应；`guided` 恒 `false`（未接决策引擎，不伪造采纳）。
- **全路段背景车流（IKNAUH，`background_source="demo_uniform"`，演示假设）**：在 D1/D2/D3 之外，**每 60 s 窗口在每条
  `SZ-###` 段上放 1 辆背景车**（61 段 × 65 窗口 = 3965 辆），每段一条**单段直行**路线（从本段起点驶过本段后离场）；
  窗口内偏移 = `(段序号 × 17) % 45` 错开，末窗口提前到前 10 s，入口被占满时按「覆盖补投」再补投（最多 2 次，只补仍无数据的段）。
  **确定性**：固定偏移 / 固定路线 / 固定 seed，不随机、不读系统时钟；补投只看当前仿真状态，同样可复现。
  **口径**：背景车是**环境车流、不是实际需求**（真实需求归 IKMHMX）；**不进 `vehicles.json`**（契约第四节只收 D1/D2/D3），
  `run_log.background` 记录 planned / inserted / topups / pending，`segments_twin.json` / `twin_timeseries.json` 顶层带
  `background_source="demo_uniform"`。
- **1 s 步进 / 60 s 快照**：TraCI 逐秒订阅各边 `LAST_STEP_VEHICLE_ID_LIST`（统计进车流量）、`LAST_STEP_MEAN_SPEED`、
  `LAST_STEP_VEHICLE_HALTING_NUMBER`；每 60 s 聚合一次，`--duration 3900` -> **65 个统计点**。
- **指标是 60 s 窗口统计**（与契约 `window_sec` 语义一致，不是瞬时值）：窗口内确实无车时才 `v_kmh=null` 并降级；
  背景车流把每段每窗口都铺上车辆后，**61 段全部能聚合出 q/v/k/L_q/level**（大屏不再灰档）。

| 字段 | 真孪生侧口径（IKNAUH 起改为 60 s 窗口统计） |
|---|---|
| `q_vph` | 60 s 窗口内进入该段（含反向补边）的车辆数 / `window_sec` x 3600 |
| `v_kmh` | 60 s 窗口内该段车辆-时间加权平均车速（逐秒 lastStepMeanSpeed x 该步车辆数累加 / 车辆-步数）。窗口内无车 -> null（不写 0 冒充畅通） |
| `k_vpk` | 60 s 窗口内平均车辆数（逐秒车辆数累加 / 窗口秒数）/ (L_seg_m / 1000)（双向合计密度） |
| `L_q_m` | `min(L_seg_m, (窗口内逐秒 halting 车辆数最大值 / 车道数) x queue_headway_m)`，双向取较大方向（`queue_headway_m` 读站点包） |
| `T_d_min` | 排队车辆数 / (饱和流率 x 车道数) x 60（**估计量**；L_q=0 -> 0.0） |
| `x` / `c_base_vph` | `x = q/c`；`c_base_vph` = 车道数 x 2 方向 x `grading.saturation_flow_vph_per_lane`（无因素注入，`factors_applied=[]`） |
| `confidence` / `data_age_s` | `grading.defaults.confidence`（仿真无检测置信度，取基准值并标明） / 0（同一仿真步算出） |
| `level` / `level_name` / `triggered_by` / `ci` | **调 `work/perception/level.py` 的 `grade()`**（唯一判级实现，不复制逻辑）；缺指标 -> `level=0` + `available=false` + `gate_reason`，不判「畅通」 |

- **四产物**（`<out>/latest/`）：`segments_twin.json`（最后一帧 61 段契约快照 + `background_source`）、
  `vehicles.json`（当期活动车辆清单，契约第四节；只含 D1/D2/D3）、`run_log.json`（命令/种子/需求来源/车辆计数/
  背景车流/覆盖统计/路网 sha/阻塞边界/逐点车队计数）、`twin_timeseries.json`（**每段 65 点的
  `q_vph` / `v_kmh` / `k_vpk` / `L_q_m` / `T_d_min` / `level` 数组** + `point_ts` + `coverage` 覆盖率汇总 + 公式）。
- 默认输出目录下另按接口层路径**兼容发布** `<out>/vehicles.json`（`traffic.py` 的 `TWIN_VEHICLES` 读它，不改接口层代码）。

### 17.4 实跑证据（2026-10-18，本机 SUMO 1.28；IKNAER + IKNAUH）

| 项 | 结果 |
|---|---|
| 建网两遍 | `python work/twin/sumonet.py`（两次不同 `--out-dir`）-> `.net.xml` sha256 **均为 `d1bb71b4ea7cea612a06a9cb165cc0b4f2d704fdcd4b4481792547117c0f0456`**（180790 B，44 节点 / 61 正向段 / 33 反向补边） |
| 真跑 A | `python work/twin/loop.py --duration 3900 --seed 42` -> **exit 0**，约 19.4 s，**65 个快照**，D1/D2/D3 插入 **1275 / 765 / 510**（实际=计划）；**背景车流 3965/3965**（61 段 × 65 窗口），覆盖补投 24 次 |
| 真跑 B | 同上 `--out work/twin/out/run_b` -> **exit 0**，约 19.2 s，计数一致 |
| 两遍 sha256（A = B） | `segments_twin.json` `8157b9b0d447c9fbbf5cffe8854e5df1e44b0981e6c984d60322a2cddfea33c7`；`twin_timeseries.json` `af5ea1e6471ce78d1fc1076eebf3886879fb99e9a0df00e820293bedd95ded7e`；`vehicles.json` `e791674348d8ea093ba166802a2a865635a7b3d588b91ee40fff4dede803767a`（**逐字节一致**） |
| 产物体积 | `segments_twin.json` 37084 B / `vehicles.json` 40182 B / `twin_timeseries.json` 380399 B / `run_log.json` 约 26120 B（`run_log` 含运行目录路径，两遍不同目录故不要求同字节） |
| **61/61 全路段** | 最后一帧 **available 61/61、level>0 61/61、v_kmh 非空 61/61**；等级分布 **L1 55 / L2 1 / L3 3 / L4 2**（无 L0 灰档）；活动车辆 149 辆（D1 74 / D2 45 / D3 30） |
| 时序覆盖 | 每段 **65 点**；**每段最少有效点 61/65**（`SZ-061`，22.8 m 短段受路口排队影响有 4 个窗口确实无车）；**其余 60 段 65/65 全有效**；最低/最高有效点 = 61/65 与 65/65 |
| **M1-1** | 三类司机均在 SUMO 中运行（计划/插入/峰值在场：D1 1275/1275/112、D2 765/765/63、D3 510/510/51）；同一场景两遍**各段等级序列 diff 0、时序 diff 0、文件 sha256 相同** |
| **M1-2（仅孪生侧）** | 65 点 >=60；`SZ-001` 平均车速有效点 **65/65**、排队长度 **65/65**。**视频侧 >=60 点不在本单，不宣称 M1-2 整体通过**（台账状态待池·Q 复核） |
| 自检 `check_w1.py` | **PASS 22 / FAIL 0 / BLOCKED 0**，约 40 s（实跑两遍 + 两次建网 + 逐产物断言 + 61/61 覆盖断言） |
| `--no-sumo` 回归 | 四产物 sha256 与改造前基线**完全一致**：`segments.json` `4effc723...` / `vehicles.json` `17bf4ba3...` / `assimilation_state.json` `8108980f...` / `run_log.json` `39a7341b...` |
| 确定性 | 不读系统时钟；固定 seed 42；两遍关键产物逐字节一致（见上 sha）；`run_log` 仅运行目录路径不同 |

### 17.5 下游集成验证（只读；接口层代码不改）

| 下游 | 结果 |
|---|---|
| `python work/assembly/traffic.py --check` | **能读到**：`路段快照数据源：twin.latest`、`路段数 61`、`twin 链路记录 61 条`、`车辆 149 辆`（`<out>/vehicles.json` 兼容发布后）；缺失的 video / 引擎层按三层回落照旧 |
| `GET /api/traffic/overview`（临时起接口层只读验证） | `segment_total=61`、**`unavailable_count=0`**、`level_distribution` = L1 55 / L2 1 / L3 3 / L4 2 / **L0 0**、`vehicles_inbound=149` |
| `GET /api/traffic/segments` | **61 段**；`level=0（数据不可用）` **0 段**；`v_kmh` 非空 **61/61**；`ts` 取孪生快照 `2026-01-01T01:05:00+08:00`（不读墙钟） |
| `python work/twin/run_assimilation.py --twin work/twin/out/latest/segments_twin.json` | **IKNAUN 已接**：`baseline_source=twin.latest`、`twin_snapshot_sha` 可核、61 段 `baseline_used=twin.latest`；同化回灌仍 0 条（boundary 无观测 + 场景 edges 仍是占位）→ 不宣称 M1-10，见第十八节 |
| 同化产物路径冲突 | **IKNAUN 已修**：默认产物写 `out/latest/assimilation/`（主循环 `out/latest/run_log.json` 不再被覆盖）；`--out` 显式优先；实跑两套产物并存 |

### 17.6 边界与遗留（如实登记）

1. **M1-2 只证孪生侧**：视频链路 >=60 点时序归感知侧（另单）；本单不宣称 M1-2 整体通过。
2. **需求是样例/演示假设值**（1 人 1 车、列车到达后 300 s 疏散、OD 只取数值做背景流率），产物 `demand_source` 明示；真实需求归 **IKMHMX**。
3. **OD 端点不落地**：`N-01` 形式属 7 节点样例网，不猜映射；路线由真网 boundary 断面 + `findRoute` 生成。
4. **未接同化回灌 / 决策引擎**：主循环里没有 `calibrator.setFlow`，`vehicles[].guided` 恒 `false`，`factors_applied` 恒空数组。
5. **`T_d_min` / `L_q_m` 是估计量**（公式见 17.3），不是采集值；判级用 `level.py` 唯一实现。
6. **`.net.xml` 不提交**：`out/` gitignore；换机/验收先 `python work/twin/sumonet.py` 重建。两遍一致性在**本机同一 SUMO 版本**内判，验收机按同样命令复跑。
7. **`run_assimilation.py --twin`**：**已由 IKNAUN 承接并完成**（`--twin` + 自动发现 + `baseline.py` 优先真孪生快照 + 产物分目录；见第十八节）。
8. `check_w1.py --duration <3600` 时统计点 <60 -> 如实打 **BLOCKED**（不当 PASS），需按缺省 3900 s 复跑。
9. **IKNAUH 背景车流是演示假设（`demo_uniform`）**：每 60 s 每段 1 辆 + 覆盖补投，只为把 61 段铺满指标，**不是实际需求/实际车辆**；
   `SZ-061`（22.8 m 短段）受路口排队影响，65 点中 4 个窗口内确实无车 -> 如实保留 `null` / 降级，**不拿别的段数据补**；
   最后一帧 61/61 有数据（`available=true`、`level>0`）。
10. **背景车流不进 `vehicles.json`**：契约第四节 `driver_type` 取值封闭为 D1/D2/D3，背景车是环境车流，只进指标聚合与 `run_log.background`。

---

## 十八、同化侧接真孪生快照（IKNAUN：`--twin` 基线 + 产物分目录）

> **业主拍板「同化侧接真孪生」**：W1 已能产出 61 段 `segments_twin.json`（第十七节），但同化侧此前
> **没有 `--twin` 参数**、`baseline.py` 只构造空载基线，且 `run_assimilation.py` 默认写
> `out/latest/run_log.json` 会覆盖主循环同名文件。本单把这三件事收口：**真孪生快照成为同化基线首选**、
> **溯源字段可核**、**产物分目录**；仍**只灌 boundary / internal 永拒 / 无观测继续 BLOCKED**，
> **不宣称 M1-10 通过**。

### 18.1 命令

```powershell
# 1) 先跑 W1 真孪生主循环（约 20 s）→ out/latest/segments_twin.json
python work/twin/loop.py --duration 3900 --seed 42

# 2) 同化侧接真孪生快照（显式 --twin；或直接跑第 3 行自动发现同一路径）
python work/twin/run_assimilation.py --twin work/twin/out/latest/segments_twin.json
python work/twin/run_assimilation.py

# 3) 降级演练（强制空载，验"无快照也如实"）：应见 baseline_source=empty_load_demo + no_twin_baseline 阻塞
python work/twin/run_assimilation.py --no-twin

# 4) 自检（真跑，输出 PASS/FAIL/BLOCKED）
python work/twin/tools/check_assimilation.py     # TC-20 四项 + 真基线前置（TC20-1-precond）
python work/twin/tools/check_factors.py          # TC-16 逐因素注入

# 5) 文档与契约门禁（先 git add）
python scripts/doc_gate.py
```

### 18.2 基线口径（**真孪生优先 + 全程溯源**）

| 优先级 | 来源 | `baseline_source` | 口径 |
|---|---|---|---|
| 1 | `--twin` 或自动发现 `out/latest/segments_twin.json` | **`twin.latest`** | W1 `loop.py` 产物（**演示数据（模拟）**，不是实测）；61 段 `SZ-###` 全部取快照指标 |
| 2 | 无快照（或 `--no-twin`） | `empty_load_demo` | 空载构造（+ 视频观测段照抄），明示演示降级；带 `no_twin_baseline` 阻塞 |
| 3 | 机制示例模式 | `sample_segments` | `samples/segments_sample.json`（旧 `SEG-###` 样例网，非本站真网） |

**溯源字段**（`assimilation_state` / `assimilation_log` / `segments_before` / `run_log` 都可核）：

| 字段 | 位置 | 含义 |
|---|---|---|
| `baseline_source` | 上述四份产物 | `twin.latest` / `empty_load_demo` / `sample_segments` |
| `twin_snapshot.path` / `.sha256` / `.ts` / `.window_sec` / `.background_source` / `.segment_count` / `.source` | `segments_before.json`、`run_log.twin_snapshot`、`assimilation_state.baseline.twin_snapshot_sha` | 快照文件 sha256（文件字节）与来源（`cli:--twin` / `auto:out/latest/segments_twin.json` / `disabled:--no-twin`） |
| `baseline_used` | `segments_before.json` 每段 | `twin.latest` / `empty_load_demo` / `video_observation`（该段基线到底用了哪份数据） |
| `counts.from_twin` / `counts.from_empty_load` | `segments_before.json` | 真孪生段数 / 空载段数（真基线时 61 / 0） |

**校验与降级纪律**：

1. 真孪生快照的**段号集合必须与断面候选一致**（缺段/多段直接报错，**不拼凑**）；
   每段必填数值字段（`q_vph/x/c_base_vph/c_vph/L_seg_m/level`）缺失即报错，`v_kmh` 允许 `null`
   （窗口内确实无车，如实保留）；
2. 快照不在场 → `baseline_source="empty_load_demo"` + `no_twin_baseline` 阻塞可见，
   **不伪造一份"孪生结果"**；`--no-twin` 可随时强制降级（自检/演练）；
3. **偏差口径变化**：同化偏差分母改用真孪生基线（`deviation` 与观测分开记），
   **不再把视频观测值当基线**（IKMS19 空载期的局限）；观测仍只来自视频链路快照（样本视频，非本站现场）；
4. **时间派生**：`ts` 从输入派生——视频观测 ts 优先，其次孪生快照 ts，最后固定演示时刻；
   基线 `ts` 取快照 ts；因素评估时刻仍按场景因素 `from` 派生；**不读系统时钟**。

### 18.3 产物分目录（**不再覆盖主循环**）

- 真网同化产物默认写 **`work/twin/out/latest/assimilation/`**（7 份，见第十五节）；
  机制示例写 `out/latest/assimilation/mechanism_demo/`；`--out` 显式优先；
- **与主循环共存**：W1 的 `out/latest/{segments_twin,vehicles,run_log,twin_timeseries}.json`
  不再被同化覆盖——实跑同化跑两遍前后，主循环 `out/latest/run_log.json` sha256
  `87EE9566…` **不变**；
- 接口层兼容发布不变：默认目录跑时仍写 `work/twin/out/assimilation_state.json`（`traffic.py` 读它），
  只是**同化的其余产物换了目录**。

### 18.4 与 W1 主循环协作 / 边界

| 项 | 口径 |
|---|---|
| 数据方向 | **单向只读**：同化侧读 W1 快照，不写 W1 产物、不改 `loop.py` / 需求 |
| 回灌接线 | **仍未接进主循环**：主循环里没有调用 `traci.calibrator.setFlow`，同化只落 `calibrator_plan`；不假装回灌到仿真 |
| 基线性质 | 真孪生快照是 **W1 的演示数据（模拟）**：需求/背景车流是样例与演示假设（`background_source=demo_uniform`），**不是实测**，真实需求归 IKMHMX |
| M1-10 / TC-20① | 真基线只解开"偏差分母"前置；**boundary 仍无观测**（视频只覆盖 `SZ-005`/`SZ-024`，拓扑均 internal）、**断面清单未签**、**场景 `edges` 仍是占位 `E-001`** → 回灌 0 条、**继续 BLOCKED，不宣称 M1-10 通过** |
| 换机 / CI | `out/` 是 gitignore；换机先 `python work/twin/sumonet.py` + `loop.py --duration 3900 --seed 42` 生成快照，再跑同化；无快照时同化会如实降级（`empty_load_demo`） |

### 18.5 实跑证据（2026-10-18，本机 SUMO 1.28）

| 项 | 结果 |
|---|---|
| W1 主循环 | `python work/twin/loop.py --duration 3900 --seed 42` → **exit 0**；`out/latest/segments_twin.json` 37095 B，**sha256 `15c5a1d641663eb44c48f6855ef3c1bc29b8cc98574135e9893594c2b2037e91`**，ts `2026-01-01T01:05:00+08:00`，61 段 |
| 同化接真基线（两遍） | `run_assimilation.py --twin …` 跑两遍 → exit 0；**7 产物 sha256 两遍全一致**：`sections_candidate` `B50990F172807C37…` / `assimilation_state` `DCBB60ACDD2484EB…` / `assimilation_log` `D580DE87447207C2…` / `factors_report` `16ACA57CEC6512A4…` / `segments_before` `E90FA0B49B617452…` / `segments_after` `D6E277ACFCE272E3…` / `run_log` `86520E7848C9C738…`。默认自动发现（`--twin` 缺省）同参数两遍也逐字节一致；与显式 `--twin` 相比只有 **2 份产物** 因溯源字段 `twin_snapshot.source`（`auto:…` vs `cli:--twin`）不同（`segments_before` `E797BF8A…` / `run_log` `506F895E…`），其余 5 份一致——**是溯源差异，不是不确定性** |
| 基线溯源 | 61/61 段 `baseline_used=twin.latest`；`counts.from_twin=61 / from_empty_load=0`；`assimilation_state.baseline.twin_snapshot_sha` = 文件 sha256（与 `run_log.twin_snapshot.sha256` / `segments_before.twin_snapshot.sha256` 三处一致） |
| 同化结果 | **回灌 0 条**（boundary 11 / internal 50）；归因：boundary 停灌 `config_unresolved` 11 条 + internal 观测被拒 2 条（`SZ-005`/`SZ-024`，`internal_not_allowed` 硬规则）；阻塞：清单未签字 / 无 boundary 观测 / calibrator 未下发 / 场景 edges 占位 / 视频快照只读引用同级 checkout |
| 降级演练 | `--no-twin` → exit 0；`baseline_source=empty_load_demo`、`twin_snapshot_sha=null`、`no_twin_baseline` 阻塞可见（自检 `TC20-1-precond` 覆盖正/负两向） |
| `check_assimilation.py` | **9 项 PASS · 1 项 BLOCKED · 0 项 FAIL**；新增 **`TC20-1-precond` PASS**（真基线来源/sha/每段 `baseline_used` 三处一致 + `--no-twin` 降级诚实）；真网 TC-20① 仍按实际数据 **BLOCKED**（不宣称 M1-10） |
| `check_factors.py` | **8 项 PASS · 6 项 BLOCKED · 0 项 FAIL**；真孪生基线让 61/61 段都有指标数据（F01/F02/F04~F09 方向校验在真孪生数据上通过；F07/F08 硬触发跳 level=4）；demand 类 6 项仍 BLOCKED（需主循环需求生成器，不编需求效果） |
| W1 回归 | `check_w1.py` → **PASS 22 / FAIL 0 / BLOCKED 0**；`loop.py --no-sumo` 四产物与 W1 基线逐字节一致（`segments.json` `4EFFC723…` / `vehicles.json` `17BF4BA3…` / `assimilation_state.json` `8108980F…` / `run_log.json` `39A7341B…`） |
| 主循环产物不被覆盖 | 同化跑两遍前后 `out/latest/run_log.json` sha256 `87EE9566…` 不变；`out/latest/assimilation/` 与主循环 `out/latest/` 并存 |
| `python scripts/doc_gate.py` | **8/8 通过**（八组门禁） |

### 18.6 边界与遗留（如实登记）

| # | 项 | 影响 | 解锁条件 |
|---|---|---|---|
| 1 | **boundary 段仍无观测**（视频只覆盖 `SZ-005`/`SZ-024`，拓扑均为 internal） | 回灌仍 0 条；TC-20① 偏差仍不可核 | 上游给 boundary 段实测/断面计数（或补摄像头到 boundary 段） |
| 2 | **断面清单未签字冻结** | 不得宣称 M1-10 / TC-20① 通过 | 业主/队长签字冻结（含 mock 5/6 与拓扑 11/50 逐条裁定）→ IKMHMX |
| 3 | **场景 `assimilation.edges` 仍是占位 `E-001`** | 真网解析不到 → `config_unresolved` | 人工换成 boundary 候选的 `SZ-###`（本单不改 `stations/`） |
| 4 | **同化回灌未接进主循环** | 只落 `calibrator_plan`，没有 `traci.calibrator.setFlow` 实灌 | 主循环内回灌接线（后续单） |
| 5 | **真孪生快照是演示数据**（需求/背景车流为样例与演示假设） | 同化偏差、因素注入都建立在演示数据上 | 真实需求/车辆归 IKMHMX；真实观测归感知侧 |
| 6 | **`out/` 不提交**（快照/`.net.xml` 均运行产物） | 换机验收要先跑 W1（约 20 s）生成快照；无快照时同化如实降级 | 验收机复跑 `sumonet.py` + `loop.py --duration 3900 --seed 42` |
| 7 | **本工作树无视频快照**（`work/perception/out/` gitignore） | 只读引用同级 checkout 的产物 | 验收机先跑 `work/perception/run_chain.py` |

> **一句话收口**：真孪生基线**已接入并全程可核**（`twin.latest` + sha + 每段 `baseline_used`），
> 同化产物**不再覆盖主循环**；但 **M1-10 / TC-20① 仍然 BLOCKED**——缺的是 boundary 观测与
> 签字冻结，不是基线。基线接入只解决"偏差分母"，不等于通过。
