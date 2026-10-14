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

- **用了什么**：`network_sample.json` / `segments_sample.json` / `demand_sample.json` 放 `work/engine/samples/`（开发规范 §6 的硬约定，**文件名与所镜像的契约文件一一对应**：`network.json` / `segments.json` / `demand.json`）；BPR 与候选生成的参数从 `stations/thresholds.json` 的 `decision` 组读。
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

---

# 附：`--sample` 输出口径修正（Issue #94 / Gitee #IKLLXT）

PR #82 兜底审留了五项，本件是它落地的记录。四项在代码、一项在登记口径。

## 十一、改了什么

| # | 位置 | 改法 |
|---|---|---|
| ① | `run.py` `stop_point_of()` | `arrival_route.dropoff_point` 改写真**点位 id**（查 `stations/points.json`），**不写图节点 id**；查不到给 `null`，原因写进 `why` |
| ② | `run.py` `DRIVER_TYPE_BY_STOP` | `driver_type` 按**终点类型**推（`pickup` → `D2`），不再一律 `D1`（否则上客行程被描述成落客） |
| ③ | `run.py` 离站路线分支 | `departure_route` 的四个 `null` 分支各给诊断，**并进现有 `why` 字符串**（不加新字段） |
| ④ | `docs/填表报告.md` | #82 那行的 `结果`：`已核对` → `占位` |
| ⑤ | `docs/数据契约.md` | 版本 `v2.0` → **`v2.1`**，并把两处变更写进第九节的版本行 |

## 十二、需要申报的一处：点位匹配范围比归档建议的宽

⭐ **这是本件唯一偏离"推荐改法"的地方，按开发规范文首总原则申报。**

- **归档建议的做法**（PR #82 评论，存档在 `docs/历史台账/pr-归档.md`）：按 `graph.edge(dep_or_arr_last)["section"]` 匹配点位 —— 也就是**只看到达路径的最后一条边**。
- **实际那么做会查不到点位。** 样例 `OD-02`（终点 `N-04`，`type=pickup`）到达走的是 `E-003`（`section=SEG-003`），而站点包里上客点 `P-02` 登记在 **`SEG-004`**（驶离 `N-04` 的那条路）——按"最后一条边"匹配会返回 `None`，点位 id 就永远出不来。
- **改用了什么**：匹配范围放宽到**终点节点的相邻路段**（到达路径经过的边 + 该节点的所有出边）的 `section` 集合。
- **为什么这样更对**：点位表说的是"这个点**落在哪条路段**"，而一个位于节点处的落客/上客点，**相邻的任一条路段都是它的合法落点**（样例里它就登记在驶离那条）。按单边匹配等于把"点位登记在哪条边"这个自由度压成了 0，站点包一换位置就失配。
- **契约与判定不变的证明**：`routes.json` 的字段形状与必填清单一字未改；`points.json` 的 `segment_id` 语义没动；匹配不到时仍是 `null` + `why` 说明（与归档要求一致）。用样例实测：`OD-02` 能查到 `P-02`；临时插一条终点为落客点 `N-02` 的 OD，`dropoff_point` 输出 **`"P-01"`**（真点位 id）。
- **影响面**：只影响 `stop_point_of()` 的查找范围，未改任何契约字段、未改站点包。

## 十三、`D2` 的上客点位 id 放哪（**本件的一处取舍**）

契约里 `arrival_route` 只有 `dropoff_point` 一个点位字段，而 `pickup_route` 明确**只有 `D3` 才有**。所以 `D2`（接客）行程面临一个没处放的点位 id。三条路：

| | 做法 | 结论 |
|---|---|---|
| **A（采用）** | `dropoff_point` 置 `null`，点位 id 写进 `why`（`对应点位 P-02`） | ✅ 不动契约形状，`dropoff_point` 语义不被污染 |
| B | 给 `arrival_route` 加 `pickup_point` 字段 | ✗ 要改契约字段形状，与本件"不动形状"的口径冲突 |
| C | 照旧把上客点位写进 `dropoff_point` | ✗ 就是本件要修的毛病 |

**选 A 的代价说清楚**：点位 id 落在 `why` 这种自由文本里，下游要解析才能拿到。**W3 接口层如果真需要结构化地拿"上客点"，那时再走契约流程加字段**——本件不替它决定。
