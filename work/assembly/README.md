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
