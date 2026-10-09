# hubflow · 高铁站外交通疏导智能平台

用 AI 视频识别看清高铁站站外的拥堵情况，**先把车流按每条路还剩多少容量分匀，再在配额内给每位司机一条说得通、走得快的路线**。

> 一期用虚拟数据把整套东西演一遍，二期到现场用真实数据再演一遍。**两期功能完全相同**，差别只有两件事：数据是虚拟还是真实，场景在单机上演还是在现场演。

## 这是什么

三个部分，共用**同一套数据**：

- **一个能力** —— 可被日常导航软件调用的站外疏导能力（不做"又一个要司机专门下载的 App"）；
- **一个 App** —— 给司机用的鸿蒙 App：推荐路线 + 至少两条备选 + **送完人之后怎么走**（离站路线）+ 停在哪里；
- **一个平台** —— 给管理者的可视化监控平台：路网四级色、拥挤度热力、告警、方案下发、处置回写、效果对比。

**核心机制**：不是"给每个人此刻最快的那条路"（那条路会被自己的推荐压垮），而是**按路段的剩余容量发号**——号发完了，下一位自动换下一条。系统不记录你是谁、你开什么车、你的车牌。

## 技术栈

**全栈华为（基础设施与 AI）+ 通用应用框架**

| 层 | 选型 |
|---|---|
| 服务器 / 操作系统 | 华为服务器 · openEuler（欧拉） |
| AI 框架 / 视觉模型 | MindSpore · MindYOLO |
| 边缘部署 / 推理硬件 | MindSpore Lite / Atlas · 昇腾 |
| 数据库 | openGauss（一期 demo 用本地文件 / SQLite） |
| 后端 | FastAPI（REST + SSE） |
| 前端 | Vue 3 + Vite + Element Plus |
| 司机端 | 鸿蒙（ArkTS / DevEco Studio） |
| 地图 | 高德 + 百度开放平台 API |
| 数字孪生 | SUMO + 自研司机行为体 |

> **一期与硬件的边界**：一期是单机演示，**在 CPU 上跑通 MindSpore 链路即可**，不依赖 Atlas 加速卡，也不需要服务器与 openGauss 实例——这三项二期部署时落地。

## 目录约定（一人一块）

| 目录 | 负责 | 端到端产出 |
|---|---|---|
| [`work/perception/`](work/perception/) | 感知线 | `segments.json` |
| [`work/engine/`](work/engine/) | 决策线 | `routes.json` |
| [`work/frontend/`](work/frontend/) | 前端 | 管理端页面 + 鸿蒙 App |
| [`work/assembly/`](work/assembly/) | 后端 | `run_all.py` + 接口层 |
| [`stations/`](stations/) | 站点配置（点位标签、路网、阈值、配时） | 换站只改配置 |
| [`docs/`](docs/) | 技术手册、数据契约、协作规范、**开发规范** | — |

> **规则：每个人只改自己目录里的东西。** 需要跨目录的改动，先开 Issue 说一声。

**开工前先读三份文档**：本文件下方「怎么开始」→ [`docs/协作规范.md`](docs/协作规范.md)（怎么不打架）+ [`docs/开发规范.md`](docs/开发规范.md)（代码长什么样、Key 怎么放）+ [`docs/分工表.md`](docs/分工表.md)（我这一周做什么、交什么文件）。

> **每次提交自动审查**：静态门禁（禁入文件 / 密钥 / 目录越界 / 跨目录 import / JSON）不通过会挡住合并；AI 审查会贴一份口径意见。说明见 [`docs/自动审查.md`](docs/自动审查.md)。**推之前先自查**：`python tools/ci/review.py --base origin/main --head HEAD --no-ai`

**当前进度**：仓库骨架已建，**代码量仍为 0**。**第 0 步硬前置已完成**（`.ckpt` 已生成并通过前向数值比对，Python 环境已重建）——实测台账见 [`work/assembly/现状核实.md`](work/assembly/现状核实.md)。**四个技术位置可以开工。**

## 怎么开始

```bash
git clone https://github.com/ouu2006/hubflow.git
cd hubflow
```

本项目**依赖上游代码仓库**（视频识别与跟踪的代码链路、FastAPI 宿主、Vue 管理后台）。把它 clone 到**与本仓库同级的位置**：

```bash
git clone https://github.com/YONEK0/agentic-traffic-management.git ../agentic-traffic-management
```

> **第 0 步硬前置**：上游仓库里 `weights/mindyolo/` 下**没有 `.ckpt` 权重**，而识别代码默认走 MindSpore 后端，缺权重会直接报错。先跑权重转换：
> ```bash
> python tools/convert_pt_to_ckpt.py all --model yolov8n
> ```
> 环境暂不具备时可先走旁路 `TRAFFIC_BACKEND=ultralytics`，但**旁路跑通不等于 MindSpore 链路已验证**，结论必须分开表述。

## 协作方式

只教四条命令，够用：

```bash
git checkout 自己的分支     # 开工前先切回自己的分支
git pull                    # 拉最新
git add . && git commit -m "说明"
git push
```

- 合并走 **Pull Request**，由后端或队长 Review 后合并，**不要自己点合并**；
- `main` 分支有保护，**不允许直接推**；
- 遇到冲突**停下来找队长，不要瞎点**；
- 详细规范见 [docs/协作规范.md](docs/协作规范.md)。

## 大文件不进仓库

**视频、模型权重、图片数据集一律不提交**（`.gitignore` 已经拦住）。这些放共享盘，路径写在各自目录的 README 里。

原因：GitHub 有单文件与仓库大小限制，几百兆的视频权重传上去之后 clone 会变得很慢。

## 数据声明

一期全部路况、指标、等待时长与告警数值**均为演示数据（模拟）**，由样本视频与数字孪生虚拟司机生成，**不代表任何真实时段的实测值**。一期尚未取得任何真实数据授权。

演示物料中**不涉及车牌、人脸、个人定位轨迹**。
