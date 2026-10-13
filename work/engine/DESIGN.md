# work/engine · 设计说明（DESIGN.md）

> 本文是 `work/engine/` 模块的**设计说明与做法申报**，按 [`docs/开发规范.md`](../../docs/开发规范.md) 文首总原则：
> 换了推荐做法、或动了框架层，就写在这里，并在 Issue / PR 的「实现方式」栏同步申报，保持模块内一致。
>
> **本文只记"为什么这么做"**；模块**负责什么、机制是什么**见 [`README.md`](README.md)，不在此重复。

## 一、本任务（W0 骨架 · Issue #39）做到哪一步

| 层 | 状态 | 说明 |
|---|---|---|
| **`stations/` 九件结构** | ✅ **定稿并冻结** | 见第二节；两组顶层键名写进 [`docs/数据契约.md`](../../docs/数据契约.md) 第六节 6.3 |
| **`run.py --sample`** | ✅ 可跑 | 不依赖上游、不依赖 SUMO，读 `samples/` + `stations/thresholds.json` 写 `out/` |
| **`network.py`（路网 + BPR）** | ✅ **实做**（W1 交付项） | 统一图结构载入与校验、`t = t0·(1+α·x^β)` |
| **`candidates.py`（K 最短路）** | ✅ **实做**（W1 交付项） | Yen 算法 + 路径重叠度 ≤ 0.7 筛选 |
| `reserve.py`（时段容量预约 + 不伤害） | ⬜ 空壳 | W3 |
| `locate.py`（定位匹配） | ⬜ 空壳 | W4 |
| `reroute.py`（前车再疏导） | ⬜ 空壳 | W5 |
| `predict.py`（预测 L0） | ⬜ 空壳 | W5 |
| `map_ingest.py` / `ingest_t1.py` / `ingest_t2.py` | ⛔ **不在本任务** | 分别归 Issue #37 / #41 |

**四个空壳的实现体一律抛 `NotImplementedError`**，不返回编造的结果。W0 骨架的哲学是"**骨架即隐性契约**"：先把函数边界与输入输出类型定下来，让下游能照着对接。

## 二、站点包九件：结构与归属

九件全部按 [`stations/README.md`](../../stations/README.md) 与手册 8.1 建立，字段名**照抄**（手册 8.2 / 数据契约 6.1 / 6.2 / 6.3），不另起名字。

⚠️ **一处与仓库既有归属说明的出入，特意在此申报**：

- `stations/README.md` 与数据契约第六节写明：`demand.json` / `factors.json` 的**脚本**归开发A，`calibration.json` 归开发A；
- 而 Issue #39 的「输出样例」与「完成判定」都要求**九个文件字段齐全并冻结**，区域 owner 也把本任务定为"**你（开发B）定结构**"。

**本任务照 Issue 原文做：九件全建。** A 侧三件的结构由本任务一并定下，**A 侧若要改动，按契约第八节提 Issue 找开发B 裁定**（反过来也成立：本任务定下的结构若与 A 侧实现冲突，以契约第六节为准并走变更流程）。

## 三、三处需要申报的做法

### ① 样例走 `samples/`，参数走 `stations/`

- **用了什么**：`network_sample.json` / `segments_sample.json` / `od_sample.json` 放 `work/engine/samples/`（开发规范 §6 的硬约定）；BPR 与候选生成的参数从 `stations/thresholds.json` 的 `decision` 组读。
- **为什么不只用 `samples/`**：只读 `samples/` 的话，"**站点包能被引擎读**"这件事就没有任何实证 —— 而"九件字段齐全并冻结"正是本任务的完成判定。两头都读，同一条命令同时证掉两件事。
- **契约与判定不变的证明**：`stations/thresholds.json` 的 `decision.k_candidates` 由 3 改为 1，`out/routes.json` 里各 OD 的备选条数由 2 条变 0 条（见第五节 ②）。参数**没有写死在代码里**，符合 README 第七节"判级阈值不得写死在代码里，必须读站点包"。
- **影响面**：只动 `work/engine/`，未动契约字段。

### ② `stations/` 的 ID 类 / 中文标签一律写成数组，不写成对象键

- **用了什么**：`thresholds.json` 的 `by_segment` 写成 `[{"segment_id": "SEG-001", …}]`；`factors.json` 的 `demo_multipliers` 写成 `[{"label": "大雨", "multiplier": 0.75}]`；`demand.json` 的比例写成 `[{"driver_type": "D1", "ratio": 0.5}]`。
- **为什么不用更自然的形式**（`{"SEG-001": {…}}`、`{"D1": 0.5}`、`{"大雨": 0.75}`）：`doc_gate` 第 6 组对 `stations/*.json` 与 `work/*/samples/*.json` **逐键**检查 snake_case —— 前面三份自然写法实测**共 13 个键被判违规**（`SEG-001`、`D1`、`小雨` 这类 ID 键与中文键）。
- **为什么不改门禁**：本任务是 W0 骨架，动 `/scripts/`（队长的准入线）应当单独走流程；而"数组 + `*_id` 字段"本来就是这个仓库的既有风格（`nodes[]` / `edges[]` / `points[]` / `segments[]` 全是这个形状），改过去反而更一致。
- **契约与判定不变的证明**：字段**语义**一个没变，只是编码形式从"对象键"变成"数组元素"；契约字段未增删改名。
- **影响面**：**只影响本任务新建的九件与三份样例**。若队长认为门禁应当放行 ID 键 / 中文键，那是 `/scripts/doc_gate.py` 的一次独立改动，本任务不夹带。

### ③ `run.py --sample` 产出的是"此刻最快"基线，**不是协同推荐**

- **用了什么**：`--sample` 只做①候选生成、②BPR 行程时间、⑤选对本车最快的那条，产出 `out/routes.json`。
- **为什么不接预约与不伤害约束**：那是 W3（`reserve.py`）。Issue #39 的「边界」写着"本任务只定结构与骨架"。
- **⚠️ 由此产生的两点必须说清**：
  1. **本输出等于手册 7.6 的「对照组」**（"此刻最快"，普通导航做法），**不是实验组**。真正让实验组区别于对照组的是时段容量预约与不伤害前车约束。
  2. `routes.json` 的 `reservation` **恒为 `null`**。契约第二节把 `reservation` 列为必填，这里**如实置空**，**不编一个 `harm_check.passed = true` 出来** —— 编出来正是 issue 反复强调的"静默假通过"。`out/run_log.json` 里另记 `is_reservation_effective: false`。
- **影响面**：`out/` 是运行产物、已 gitignore，不进仓库。

## 四、`out/routes.json` 的信封形状（**一处需要下游知晓的约定**）

契约第二节定义的是 `POST /api/traffic/route/recommend` 的**单次响应体**。`--sample` 要一次跑完 ≥3 个 OD 对（M1-4 前置），所以外面包了一层：

```json
{ "ts": …, "is_simulated": true, "mode": "sample",
  "requests": [ { /* ← 这里每个元素就是契约第二节那份响应体 */ } ] }
```

**每个 `requests[]` 元素照契约第二节逐字段**；多出来的 `od_id` / `arrival_route.edges` / `no_alternative_reason` 是产物自用的辅助字段，**接口层不应把它们透出去**。

## 五、怎么跑、怎么验

```bash
cd work/engine
python3 run.py --sample      # 读 samples/ + ../stations/thresholds.json，写 out/
ls -l out/                   # routes.json + run_log.json
```

| # | 验证了什么 | 结果 |
|---|---|---|
| ① | 可复现 | 连跑两遍，`routes.json` / `run_log.json` **逐字节一致**（Yen 与 Dijkstra 的比较键都带路径元组，无随机、无系统时间） |
| ② | **站点包真的被读** | `decision.k_candidates` 3 → 1，各 OD 备选条数 **2 → 0** |
| ③ | 反向用例 | 挪走一份样例 → 退出码 **1**，报"缺样例文件"，不静默降级 |
| ④ | 语法 | 七个 `.py` `py_compile` 全过 |
| ⑤ | 空壳不假装成功 | 四个空壳模块的实现体抛 `NotImplementedError` |
| ⑥ | M1-4 前置 | **4/4** 个 OD 对产出「1 推荐 + ≥2 备选」（要求 ≥3 个 OD 对） |
| ⑦ | 无站点硬编码 | `grep -nE "肇庆\|肇庆东\|23\.21\|112\.65" work/engine/*.py` 无命中 |

## 六、已知偏差与卡点（**不粉饰**）

1. **样例路网是为演示"造"出来的**：`network_sample.json` / `stations/network.json` 的 7 节点 / 17 边都是一个最小玩具图，只保证 M1-4 的"≥3 个 OD 对出候选"能演示。**它不是肇庆东站的真实路网** —— 真值待 Issue #37（`map_ingest.py`）产出。
2. **`stations/` 九件全是占位值**：列车时刻、点位经纬度、标定控制点等均为"一眼能看出是样例"的整数/占位值，**不是实测数据**，对外材料一律按"演示数据（模拟）"口径。
3. **`od[].exit_node` 是本次新加的字段**（见数据契约 6.3）：`routes.json` 的 `departure_route` 必填，但"送完人之后去哪"此前无处安放。已写进契约；`demand.json` 的脚本归开发A，**开发A 若要改名请提 Issue**。
4. **`--sample` 不接预约/不伤害/再疏导**（见第三节 ③），因此 `quota` 也恒为 `null`。
5. **`run.py` 不带 `--sample` 会抛 `NotImplementedError`** —— 真链路要 SUMO 孪生数据（`work/twin`）与站点包路网（`network.json`，Issue #37），两者都还没到位。
