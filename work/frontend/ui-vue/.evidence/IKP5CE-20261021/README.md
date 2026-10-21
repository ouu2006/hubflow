# IKP5CE · 决策层路线规划视图 · 渲染截图

> 截图环境：1440 × 900 浏览器视口，`/#/decision` → 页头「路线规划」。
> remote 列接本地 `traffic.py`（引擎产物 `engine.routes.real`）；mock 列走 vite mock 中间件。
> 截图是页面渲染留证；所有路线均为 `is_simulated = true` 的演示产物。

| 文件 | 对应判定 | 看什么 |
|---|---|---|
| `01-two-session-compare.png` | 变化可见 / 一主二备 | 左 A 列 = 选项第 1 条 session（OD-R-001，到达 0.82 min、离站 0.36 min），右 B 列 = 第 2 条（OD-R-002，到达 0.87 min、离站 0.31 min）；两列各自一条链路（起点 → 落客 → 终点 → 离站），底部差异结论写明「推荐段序列不同；到达 ETA 差 +0.05 min；离站路线不同；备选均 1 条」。两列数据来自两次 `POST /route/recommend`，不是前端造的差异。 |
| `02-no-alternative.png` | 备选不足不凑数 | 当前 session 切到 OD-R-010（`alternatives` 为 0）：页面显示「引擎标记 no_alternative = true：只有一条候选路径通过重叠度约束（本 OD 备选 0 条，按产物如实展示，不凑数）」，并保留「产物未给备选路径（不补造等价路线）」；没有补画第二条备选。 |
| `03-mock-fallback.png` | mock 降级 | mock 模式无 `GET /api/traffic/route/options`（404）：页面跳过该请求并显示「mock 无该辅助端点」，回退站点包演示会话路线；同时标注「mock 站点包演示骨架（非引擎产物）」与「演示数据（模拟）」，不冒充引擎 OD 列表。 |

复核命令见 [`../../../README.md`](../../../README.md) 第二十三节（本目录不重复抄）。
