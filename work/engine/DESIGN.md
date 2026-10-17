# work/engine · 设计说明（DESIGN.md）

> 本文是 `work/engine/` 模块的**设计说明与做法申报**，按 [`docs/开发规范.md`](../../docs/开发规范.md) 文首总原则：
> 换了推荐做法、或动了框架层，就写在这里，并在 Issue / PR 的「实现方式」栏同步申报，保持模块内一致。
>
> **本文只记"为什么这么做"**；模块**负责什么、机制是什么**见 [`README.md`](README.md)，不在此重复。

## 一、本任务（W0 骨架 · Issue #39）做到哪一步

| 层 | 状态 | 说明 |
|---|---|---|
| **`stations/` 九件结构** | ✅ **定稿并冻结** | 见第二节；两组顶层键名写进 [`docs/数据契约.md`](../../docs/数据契约.md) 第六节 6.3 |
| **`run.py --sample`** | ✅ 可跑（对照组基线）；`--sample --compare` 已接三组对照 | 不依赖上游、不依赖 SUMO，读 `samples/` + `stations/thresholds.json` 写 `out/`；`--compare` 见文末「IKMF1V 实现记录」 |
| **`network.py`（路网 + BPR）** | ✅ **实做**（W1 交付项） | 统一图结构载入与校验、`t = t0·(1+α·x^β)` |
| **`candidates.py`（K 最短路）** | ✅ **实做**（W1 交付项） | Yen 算法 + 路径重叠度 ≤ 0.7 筛选 |
| **`reserve.py`（时段容量预约 + 不伤害）** | ✅ **实做**（W3；IKMF1V） | `SlotTable` / `walk_slots()` / `harm_check()` / `recommend()` / `release_expired()`，见文末实现记录 |
| `locate.py`（定位匹配） | ⬜ 空壳 | W4 |
| **`reroute.py`（前车再疏导）** | ✅ **实做**（W5；IKMF1V） | 三条件 + `hysteresis` 滞回 + 每车最多改道次数，见文末实现记录 |
| `predict.py`（预测 L0） | ⬜ 空壳 | W5 |
| `map_ingest.py` / `ingest_t1.py` / `ingest_t2.py` | ⛔ **不在本任务** | 分别归 Issue #37 / #41 |

**仍为空壳的 `locate.py` / `predict.py` 实现体一律抛 `NotImplementedError`**，不返回编造的结果。W0 骨架的哲学是"**骨架即隐性契约**"：先把函数边界与输入输出类型定下来，让下游能照着对接。


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
- **IKMF1V 之后**：`--sample` **仍保持**上面这条"此刻最快基线"口径（判定引用它，不许改）；协同推荐走 `--sample --compare` 的 ③ 组，见文末「IKMF1V 实现记录」。

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
4. **`--sample` 不接预约/不伤害/再疏导**（见第三节 ③），因此 `quota` 也恒为 `null`（`--compare` 的 ③ 协同链路里 `reservation` / `quota` / `reroute` 都有值，见文末「IKMF1V 实现记录」）。
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

---

# 附：IKMF1V 实现记录（W3 时段容量预约 + W5 前车再疏导 + `--compare` 三组对照）

> 本件把 `[reserve.py](reserve.py)` / `[reroute.py](reroute.py)` 两个空壳做实，并给 `[run.py](run.py)` 加 `--compare`。
> 口径：**`--sample` 的现有行为一字未动**（它是对照组基线，被 `DESIGN.md` 与多条判定引用），新增全部走 `--sample --compare`。

## 十四、交付

| 文件 | 内容 | 对着哪条判定 |
|---|---|---|
| `reserve.py` | `SlotTable`（时段预约表 + 每段 t0 / 背景流 / 通行能力缓存）、`walk_slots()`（沿路径按 `slot_minutes` 推进）、`harm_check()`（约束②，只返回契约三字段）、`remaining_quota()`（`quota` 新口径）、`recommend()`（约束①+②、登记预约与租约、全候选被丢弃 → `capacity_shortage`）、`release_expired()` | M1-4 / 契约 §二 / 本单专属一、二 |
| `reroute.py` | `is_before_next_branch()` / `best_alternative()`（`hysteresis` 滞回）/ `should_reroute()`（三条件同时满足）/ `reroute()`（回写 `{count, reason}`，每车最多改道次数读站点包）/ `check_and_reroute()`（一个决策周期） | W5 / 契约 §二 `reroute` |
| `run.py` | 新增 `--compare`：① 不推荐 ② 此刻最快 ③ 协同推荐；输出 TC-17 三项对比数据 + `capacity_shortage` / 租约释放 / 突发再疏导证据；`run_log.is_reservation_effective = true` | TC-17 / 契约 §二 |
| `DESIGN.md` | 本记录 | [`开发规范.md`](../../docs/开发规范.md) 总原则④ |

## 十五、需要申报的六处做法

### ① 模块内部签名按"显式传状态"扩展（跨模块契约签名未变）

手册 §7.6 的伪代码是**模块级全局状态**（`background` / `reserved` / `leases` 挂在模块上）。本实现把状态收进 `SlotTable` 并显式传参，例如：

```text
walk_slots(table, path, start_epoch_s, extra=1)   # 手册的 walk(path, t_start, extra)
harm_check(table, cells, leases, params)          # 手册的 max_eta_increase(...)
recommend(graph, od, candidate_paths, segments, params, table, leases, now_ts)
release_expired(table, leases, now_ts)            # 多一个 table:释放时要把格子撤掉
```

理由：**确定性 + 可测**（同一输入不依赖模块全局残留）。**跨模块契约签名未变**——接口层的决策入口仍是"给请求 → 出契约响应体"，`routes.json` 字段一个没动。

### ② 格子量纲 = 辆/时段；BPR 复用 `network.travel_time_s`，不复制公式

- 手册 §7.6 写明 `background` / `reserved` / `cap` 都是**辆/分钟**，`extra=1` 是"把这辆新车算进去"；
  所以格子里按 **辆/时段** 计数，`cap` 由 `segments.c_vph` 换算成"辆/时段"（`slot_minutes` 从站点包读）。
- `SlotTable.tt()` **不另写一份 BPR**：把格子里车数换算成 `extra_vph` 喂给
  `network.travel_time_s`（全仓唯一 BPR 实现）。`x` 本身即无量纲饱和度，**惩罚项不再除以 c**
  （与 `network.py` 顶部量纲注释一致）；改站点包 `alpha` / `beta` / `slot_minutes`，产物跟着动。

### ③ `quota` 按 v2.0 新口径实现

`remaining_quota()` = 这条路径**各格子"再塞几辆仍能保持饱和度 ≤ x_safe"的最小值**（整数），
不是 v1.0 的"配额发号计数"。`recommend()` 对每条候选各算一个，`run.py` 折成
`{"<path_id>": 剩余可预约量}`。

### ④ `REROUTE_TH` 在站点包 decision 组**没有独立键**（缺口申报）

手册 §7.7 把"再疏导触发阈值 `REROUTE_TH`"标为【待标定】，但
`stations/thresholds.json` 的 `decision` 组**没有这个键**。**不在代码里写死一个数字**：
`reroute_threshold_s(params)` 暂代用同组的 `eps_harm_s`（两者同为"ETA 增加量（秒）"阈值），
并在函数 docstring 写明"站点包补键后改读新键"。
**本单不碰 `stations/`**（跨目录禁区），补键由后续站点包变动统一做。

### ⑤ `--compare` 的三组口径（TC-17 对照实验）

- **车辆群**：每 OD `demand_vph × segments.window_sec / 3600` 辆，按 `3600 / demand_vph` 等间隔出发
  —— 固定车辆群、无随机数、不读系统时钟（确定性）。
- **① 不推荐**：自由流最短路（没有推荐时的驾驶员习惯路线）。
- **② 此刻最快**：用**同一份 segments 快照**算出 `--sample` 的推荐 + 备选，整批车辆跟着这条
  "普通导航"推荐走（不做时段预约、看不见后车）。
- **③ 协同推荐**：在同一批候选上叠时段容量预约 + 不伤害前车约束 + 前车再疏导。
- 三组**同一份输入、同一批车辆、同一套站点包参数**。样例数据上 ① 与 ② 的路线恰好相同
  （自由流最短路与 BPR 快照的最快路径一致），产物里如实并列，**不硬造差异**。
- **全网总行程时间口径**：`Σ 每段每时段 (背景车流 + 已预约) × 该时段服务时间`（辆·秒，
  **把被拖慢的背景车流也算进去**，对应 TC-17 的"全网"）；另列"被引导车辆共同车辆群"口径作参考
  （TC-17 评测协议口径，两者都写进产物，不挑好看的报）。

### ⑥ 演示事件从站点包数据推、不写死常量

- **突发再疏导**：从 `stations/factors.json` 的 `demo_multipliers` 里取**第一条倍率 ≤ 0** 的
  demo 取值（样例是 F07 交通事故·全封）作为封路注入；封哪条路段 = 突发时刻在途车辆**剩余路径里
  出现最多**的那条段（并列按段号；数据驱动，不写死段号）。
- **`capacity_shortage`**：取第一个 OD 的每条候选，按 `remaining_quota()` 把预约表顶满，使"再加一辆
  必然超约束①"；再请求推荐必须返回 `capacity_shortage` 且无路线（**不硬塞**）。
- **租约释放**：登记一张未确认采纳的租约 → 时钟推进 `lease_expire_s + recompute_period_s`
  → `release_expired()` 后占用格子归零。

## 十六、自检（真实跑过，输出摘要）

| 命令 | 结果 |
|---|---|
| `python work/engine/run.py --sample` | 退出 0；`out/routes.json` 8310 B / `run_log.json` 730 B，与改动前基线**逐字节一致** |
| `python work/engine/run.py --sample --compare` | 退出 0；`requests=4`、`reservation=null 条数=0`、4 个 OD 的 `harm_check.passed` 全 `true`、每 OD `alternatives=2`；`run_log.is_reservation_effective=true` |
| `--compare` 连跑两遍逐字节比对 | `routes.json` 22366 B / `run_log.json` 2277 B **两次完全一致** |
| 参数写死检查（issue 原文 `grep -nE "0\.85\|30(\.0)?\b\|90(\.0)?\b\|0\.10"`） | `reserve.py` / `reroute.py` **0 命中** |
| `python scripts/doc_gate.py` | 代码与契约相关 **1–7 组全过**；第 8 组（任务记录台账）本次交付时因 `docs/任务记录.md` 的台账行格式失败 —— 属 `docs/` 范围，本单按纪律不碰（已报 Lead），与 `work/engine/` 改动无关 |

## 十七、TC-17 三项结论（**如实记录，不粉饰**）

| 判据 | 结果 | 数字 |
|---|---|---|
| ① 前车 ETA 最大增加 ≤ `eps_harm_s` | ✅ | ③ **1.1 s** ≤ 30 s（② 用同样口密度出来 6.14 s） |
| ② 不新增橙 / 红路段 | ❌ | ③ 新增 `SEG-001`（x=0.8125）；② 同段 x=0.625 |
| ③ 全网总行程时间低于对照组 | ✅ | ③ **60073.79** < ② **61072.84**（辆·秒，含背景车流） |

**② 为什么不过 —— 站点包 demo 数值口径冲突，不是实现编造：**

1. `x_safe = 0.85`【待标定】**高于**判级橙档边界 `0.8`（`thresholds.grading.level_bounds` 的 x 档）；
2. OD-02 的唯一可行备选是 `SEG-001 → SEG-015`（另两条候选经过 `SEG-003`，其背景饱和度已
   0.833，+1 辆即超 `x_safe`，属约束①合法拒绝）；
3. OD-02 需求 5 辆/分钟 → 实验组合法登记后 `SEG-001` 的 x = 0.625 + 5/26.67 = **0.8125**，达橙档；
4. 对照组（普通导航）走 `SEG-011 → SEG-003`、不经过 `SEG-001`，所以这是"实验组新增的橙档"。

**没有为了让判据变绿去改代码常量或调阈值**（issue 第六节点名的造假红线）；
待池·P 标定后由开发B 统一改站点包（`x_safe` 与档位二选一或都调），本单不碰 `stations/`。
补充留痕：③ 的"被引导车辆共同车辆群"口径总耗时 15964.71 vs ② 15957.31（③ 高 0.05%），
原因是 OD-02 被约束逼到自由流更慢的备选、而 ② 的拥堵惩罚很小，两者基本抵消；
产物里单列，**没有拿车辆口径当判据凑过**。

## 十八、`capacity_shortage` 证据（本单专属一）

`comparison.capacity_shortage_evidence`：OD-01 的三条候选按剩余可预约量顶满预约表后，三个候选的
瓶颈格子饱和度分别为 0.825 / 0.8333 / 0.8333（上限 0.85）；再请求一次 → 每条候选都超 `x_safe`
（0.8625 / 0.8667 / 0.8667），输出 `status = capacity_shortage`、`has_route = false`、
`suggest = 外围等待 / 延后出发 / 换停车场`，**没有硬给一条路线**。

## 十九、边界与遗留风险

- **只改 `work/engine/`**：未动 `docs/` / `stations/` / 其它 `work/` 目录（`git status` 可查）。
- **`--sample` 现有行为未改**：改动前后 `out/routes.json` / `run_log.json` 逐字节一致。
- **遗留 1**：`REROUTE_TH` 缺口（见 ④）—— 站点包补键后改读新键。
- **遗留 2**：TC-17 ② 的 demo 数值冲突（见 十七）—— 需池·P 标定或站点包调整，**本单不能改站点包**。
- **遗留 3**：样例 7 节点只是为了跑通机制，**不是真网**；不要拿本产物数字当性能 / 效果结论
  （真网算路在 IKMDKY ③' 之后）。
- **遗留 4**：`--compare` 是引擎侧对照实验（固定车辆群、确定性），不是 SUMO 闭环对照；
  孪生侧闭环实验仍归后续 issue。

## 二十、快速独立审查整改（2026-10-17，4 条逐条处置）

> 背景：Lead 用全新上下文只读 diff 做了一次快速独立审查，提 4 条发现。
> **逐条复核结论：4 条全部成立，全部已修**；`--sample` 输出仍逐字节未变。

| # | 审查发现 | 复核 | 整改 |
|---|---|---|---|
| 1 | `reroute.py` 判据①用「当前时刻算的剩余 ETA − 登记时整条路径 ETA」，在途车（`progress_edges>0`）差值为负，几乎只有封路 `+inf` 能触发 | **成立** | 租约新增 `edge_times_s`（逐边计划服务时间，由 `reserve.walk_slots_detail()` 产出）；判据①改为「当前剩余 ETA − **登记时对同一段剩余路**的计划耗时」（`_planned_remaining_eta_s()`）：`progress=0` 时仍等于整条路径 ETA（口径不变），在途车只比剩余段、不再差出已走过那段。 |
| 2 | `reroute.py` `progress=0` 时复用含被拒候选的 `lease["candidates"]`；`reroute()` 改道后不复核约束①/②，可能落到已判超 `x_safe` / 伤前车的路线 | **成立** | ① 租约只保存 `feasible_candidates`（**登记时通过两条约束**的候选），不再存全部候选；② `best_alternative()` 对每条候选复核 `max_slot_x ≤ x_safe`（`reserve.max_slot_x()`；先把本车旧占用临时撤掉再试算，`finally` 恢复）与 `harm_check.max_eta_increase_s ≤ eps_harm_s`（排除本车、对**全量租约**算），不合规候选不参与择优；`reroute()` 只登记复核过的路径。 |
| 3 | `run.py` 的 `inserted` 直接等于 `attempted`，有未准入车时虚报插入数 | **成立** | 四计数改为自洽：`attempted = inserted + not_entered`、`inserted = completed + in_transit`；`completed` 按「预计到达时刻是否落在评估窗口内」拆出 `in_transit`。`comparison.groups.*` 与 `run_log.groups.*` 同步，并加 `counts_note` 说明口径。 |
| 4 | 写入产物的 TC-17 说明硬编码 `x_safe=0.85` / 橙档边界 `0.8`，站点包标定后文案与实参不符 | **成立** | `_tc17_summary()` 改为**从站点包读**：`x_safe` 取 `params["x_safe"]`，橙档边界取 `grading.level_bounds` 里 `x` 的第 2 个边界，文案用这两个实参格式化。 |

**定向验证（临时脚本，不进仓库，见报告）**：
- #1：`progress=0` 基线 = 整条路径 ETA；`progress=1` 基线 = 剩余边计划时间之和（不再为负）；**无封路、只人为加塞**即可 `should_reroute()=True`。
- #2：OD-02 租约的 `feasible_candidates` 与登记时被拒候选**不相交**（1 条可行 / 2 条被拒）；人为把某候选路径顶到 `x_safe` 以上 → `_candidate_feasible()` 返回 `None`（拒绝改道）。
- #3：三组车辆均满足 `attempted = inserted + not_entered`、`inserted = completed + in_transit`（450 = 450 + 0；450 = 433/434 + 16/17）。
- #4：把 `x_safe` 改 0.7、橙档边界改 0.9 后，产物文案随之变成「`x_safe`(0.7)高于判级橙档边界(0.9)」，不再出现 0.85 / 0.8。

**整改后的产物数字（真跑）**：`--sample` 与基线逐字节一致（8310 B / 730 B）；`--sample --compare` 两遍逐字节一致（`routes.json` 22366 B / `run_log.json` 2277 B）；TC-17 三项数字不变（① 1.1 s ≤ 30 s ✅；② 仍如实 FAIL；③ 60073.79 < 61072.84 ✅）；突发再疏导：突发时刻在途 20 辆，改道 **3** 辆（其余候选被复核出的约束①拒绝，属预期行为），`routes.json` 的 OD-01 代表车 `reroute={count:1, reason:…}` 仍有值。

**复核口径说明（避免误读）**：
- 判据①的基线仍来自**登记那一刻**的规划 —— 差值语义是「相对登记时计划变慢了多少」，与手册 §7.6 `eta - l.eta` 一致；不是「相对上一次周期」。
- 再疏导演示仍用「全封」（`factors.json` 里第一条倍率 ≤ 0 的 demo 值）：样例路网上半幅封闭（×0.5）造成的 ETA 增量达不到 `eps_harm_s` 触发阈，**有限变慢能触发**这条由上面 #1 的定向验证覆盖。
- `--sample` 的冻结基线文案（`why` 里仍写「W3 尚未实现」）保持原样：它是被判定引用的对照组基线，改一个字就破坏逐字节一致。


