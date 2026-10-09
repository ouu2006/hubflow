# 后端

> **产出**：`run_all.py`（一键全链路）+ 接口层 `traffic.py`
> **同时负责**：**公共文件的唯一修改人**

## 负责什么

1. **总装脚本** `run_all.py`：把感知线 → 决策线 → 前端三步串起来，一键跑完全链路；
2. **接口层**：演示前最后一步，把 `segments.json` / `routes.json` 包成 HTTP 接口给双端调用；
3. **公共文件**：根目录 `README.md`、`.gitignore`、`docs/数据契约.md`、`main.py` 注册、路由表 —— **只由你一人改**；
4. **压力测试**：按算力预算跑，以"**无人干预连跑 3 轮不出问题**"为验收口径。

## 接口层（演示前最后一步）

| 端点 | 方法 | 用途 |
|---|---|---|
| `/api/traffic/segments` | GET | 路段级指标与等级列表 |
| `/api/traffic/segments/{id}` | GET | 单路段详情 |
| `/api/traffic/route/recommend` | POST | 请求推荐 |
| `/api/traffic/alerts` | GET | 告警列表 |
| `/api/traffic/plan/dispatch` | POST | 下发分流方案 |
| `/api/traffic/plan/ack` | POST | 处置回写 |
| `/api/traffic/report/compare` | GET | 效果对比报表 |

**约定**：`is_simulated` 字段在**每一个**响应里出现；事件流复用现有 SSE 形状，**新增**事件名，**不改既有事件名**。

## 总装脚本要做的

```bash
python run_all.py            # 一键跑完全链路
python run_all.py --stress   # 压力测试：连续 3 轮
```

**判定标准**：3 轮全成功、日志留存、内存不持续增长。

## 硬性边界

- **既有 8 个端点零改动**：`app/main.py` 的 diff 只包含"新增注册"；
- 公共文件只你改，其他人只提 Issue；
- 视频、权重、数据集**不进仓库**。

## 大文件

压测日志放 `logs/`（已 gitignore）。模型权重放共享盘。

## ⚠️ 两个已知缺陷（**演示脚本必须先绕过**）

2026-10-09 执行 0-1~0-4 时发现，详见 [`现状核实.md`](现状核实.md) 第 4.3 节：

| # | 缺陷 | 绕过办法 |
|---|---|---|
| 1 | **OpenCV 不支持中文绝对路径**——`cv2.imwrite` / `cv2.imread` 传中文绝对路径直接失败，而 `image` 模式的输出目录由 `REPO_ROOT` 拼出，**必为中文绝对路径** | ① 把两个仓库放到纯英文路径（如 `D:\work\`，**推荐**，根因消除）；或 ② 写出改 `cv2.imencode` + `open(...,'wb')`、读入改 `np.fromfile` + `cv2.imdecode` |
| 2 | **`track` / `count` 的输出目录不存在时静默失败**——`_write_frames()` 既不 `makedirs` 也不检查 `isOpened()`，**命令照样打印"轨迹条数: 9"但视频文件根本没生成** | `run_all.py` 里先 `os.makedirs("video_output", exist_ok=True)`；**压测脚本里加一条"产物文件存在性"断言**，别只信退出码 |

> 缺陷 2 是"**假通过**"——比报错更危险，因为验收时看不出来。写 `run_all.py` 时**必须**对每一步产出的文件做存在性检查。

## 硬前置状态（2026-10-09）

**0-1 ~ 0-3 已完成**：`.ckpt` 已生成（`yolov8n.ckpt`，12.7 MB）并通过前向数值比对（最差相对误差 2.875e-06）；环境已按 `requirements-mindspore.txt` 重建（CPython 3.11.17 + MindSpore 2.8.0）。

**执行环境时注意**：依赖清单**未覆盖**两个包，换机器要补装——`setuptools`（`mindyolo` 里有 `import pkg_resources`）与 `ultralytics`（`verify` 步要 `torch.load` 原 `.pt`，其 pickle 引用 ultralytics 类）。建议按流程补进上游 `requirements-mindspore.txt`。
