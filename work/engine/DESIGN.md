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
| **`run.py --network real`** | ✅ **真网 61 段算路**（IKMS11） | 读站点范围登记表 → 真网产物 → 统一图；边界推导 OD；预约 / 不伤害 / 再疏导 / `--compare` 全在真网跑，写 `out/real/`（默认）/ `out/real/compare/`（`--compare`）；`--sample` 基线逐字节不变。见文末「IKMS11 真网接入」 |
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
5. **`run.py` 不带 `--sample` / `--network real` 会抛 `NotImplementedError`**（默认安全：不显式选数据来源就不跑）。真链路已不再依赖 SUMO：真网入口 `--network real` 读站点范围登记表指向的真网产物（IKMS11，见文末）；`stations/network.json` 仍是 7 节点占位件，真值化归 IKMHMX。

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

---

# 附：IKMS11 真网接入（站点 Z 61 段 · `--network real`）

> Issue：**IKMS11 真网算路**。本件把决策引擎从 7 节点样例网（`SEG-###`）切到站点 Z 的
> **61 段真路网（`SZ-###`）**；`--sample` 仍是**逐字节基线**，一个字节没动。

## 二十一、改了什么

| 文件 | 改动 | 为什么 |
|---|---|---|
| **`realnet.py`（新增）** | 站点范围登记表读取 / 真网产物 → 统一图（校验段数·段号命名空间·端点·长度）/ 边界 OD 推导 / 上游 `segments` 快照按 `segment_id` 映射 / 逐段 `param_source` / 段号硬校验 / 路线补 `length_m` | 真网接入全部收在这一个模块，`run.py` 只做装载分流；**引擎代码不出现站点名 / 节点 id / 段号 / 坐标** |
| `run.py` | 新增 `--network {sample,real}`、`--site-id`、`--site-ranges`、`--segments`、`--demand-vph`；新增 `run_real()`；`run_compare()` 的装载层抽成 `_load_dataset()`（样例 / 真网各自装载，机制完全共用）；真网产物**按 mode 分目录**：默认 `out/real/`、`--compare` `out/real/compare/` | 保留 `--sample` 行为不变；真网入口默认写独立目录；两种 mode 的 `routes.json` **不共用路径**，避免后跑覆盖前者；`--out` 可覆盖 |
| `reserve.py` | `walk_slots_detail()` 增加 `+inf` 守卫：前方路段被"突发"封闭后，后续路段的时段格沿用最后一个有限时段 | 真网路径更长：封闭段不在路径末段时，原实现会把 `+inf` 喂给 `slot_index_of()` 抛 `OverflowError`（样例网没暴露）。样例产物零变化（只在 `+inf` 分支生效） |
| `README.md` / `DESIGN.md` | 新增「真网算路」章节 / 本记录 | 命令、OD 规则、产物路径、与 `stations/network.json` 的关系、降级口径 |

### 独立审查整改（发现 1：真网两种 mode 共用一个 `routes.json`）

**问题**：改造初版让 `--network real`（默认）与 `--network real --compare` 都写 `out/real/routes.json`，
后跑的会覆盖先跑的（实测 compare 85973 B 覆盖默认 71036 B）；下游若按固定路径读取，会拿到**错 mode** 的产物。

**整改**：输出目录按 mode 分开（`--out` 显式传参仍然优先，`run_log.json` 随 `routes.json` 同目录）：

| 模式 | 默认输出目录 |
|---|---|
| `--sample` / `--sample --compare` | `work/engine/out/`（样例逐字节基线，**不变**） |
| `--network real` | `work/engine/out/real/` |
| `--network real --compare` | `work/engine/out/real/compare/` |

**验证**：两模式各连跑两遍 —— 产物分目录、互不覆盖；默认模式两遍 sha 一致、`--compare` 两遍 sha 一致；
`--sample` 基线 sha 不变（见第二十三节 ⑥⑦⑧⑭）。

## 二十二、四处需要申报的做法

### ① 装载层分流、机制层不分流（`--sample` 逐字节不变的做法）

`--sample` 的逐字节基线是用**最小侵入**保住的，不是"重写后碰巧一致"：

1. 只把 **数据装载** 抽成 `_load_sample_dataset()` / `_load_real_dataset()`；候选生成、时段预约、不伤害、
   再疏导、`--compare` 三组对照的代码**一行未改**（共用同一套函数，不按 `source` 分支）；
2. 两处会写进产物的**样例专属文案**参数化（`compare_scenario_note` / `guided_common_note`），缺省值就是
   改造前的原文 —— 样例路径取缺省，真网路径覆盖；
3. 真网专属的后处理（补 `length_m`、段号硬校验、网络元数据块）**只在 `dataset["route_lengths"]` 为真时执行**，
   样例产物不经过这些代码；
4. `--sample` 的日志键名 / 顺序 / 取值位置与改造前完全一致（`samples_dir` 由 `**dataset["log_source_fields"]`
   原位展开），模块 docstring / help 文案变化不进产物。

→ 实测：`--sample` 两遍逐字节一致，且与改造前基线 sha256 **完全相同**（见第二十三节 ①）。

### ② 真网缺字段：不编数，逐边标 `param_source`

真网产物里 `speed_limit` / `capacity_vph` **全为 null**、`lanes` 只有 10/61 段有值（真值等 T2 核对表补）。
引擎口径：**长度缺失报错**；限速缺 → 站点包 `grading.defaults.v_f_kmh`；容量缺 → 有车道数按
`lanes × grading.saturation_flow_vph_per_lane`，否则 `grading.defaults.c_vph`；车道数缺**保留 null 不补**。
每条边/每段都写 `param_source`，产物 `network.param_source_counts` 汇总（本站：限速 61 段全部回落、
容量 51 段用 defaults + 10 段按车道数推、车道数 51 段缺）。

### ③ OD 规则：边界推导（不手写段号），并为「备选 ≥2」保留可验 OD

真网是有向图（`oneway=yes` 的段只保留 from→to 方向），边界按**方向**分成 4 个进场边界（只有出边）与
7 个离场边界（只有入边）。原始"进场边界 → 离场边界"对的候选路线数最多只有 2 条（多数只有 1 条），
达不到 M1-4 的「备选 ≥2」；因此规则改为：

1. 每个进场边界遍历**全部内部节点**当候选终点，按（候选路线数降序, 自由流耗时升序, 节点 id）取前 3 个；
2. 终点是内部节点、`exit_node` 是它自由流最快的**可达离场边界** → 两者必不同，`departure_route` 可算（TC-12）；
3. 不可达组合跳过留痕（`od_derivation.skipped`），不顺延硬凑；
4. 本站结果：**12 个 OD 对**，其中 3 个 OD 的备选 = 2 条（M1-4 要求 ≥3 个 OD 对，达标）。

> 为什么"候选路线数"不是循环论证：它是**真网拓扑 + 站点包 `k_candidates` / `max_path_overlap`** 的直接函数，
> 只用来**挑终点**（挑能体现 K 候选的 OD），不是判据、不是阈值；OD 数与规则都写进 README，换站换网自动重推。

### ④ 真网两种 mode 的输出目录分开（独立审查发现 1）

- **做法**：默认 `--network real` 写 `work/engine/out/real/`，`--network real --compare` 写
  `work/engine/out/real/compare/`；`--out` 显式传参优先；`routes.json` 与 `run_log.json` 始终写同一目录。
- **为什么**：两种 mode 的 `routes.json` 形状不同（默认是单次协同推荐信封；`--compare` 多 `comparison` 块），
  同一个路径必然互相覆盖 —— 下游按固定路径读取时会拿到**错 mode** 的产物（实测 compare 85973 B 覆盖默认 71036 B）。
- **口径不变**：只改**文件落盘位置**，不新增 / 不改契约字段；样例基线仍写 `work/engine/out/`（不变）。

## 二十三、自检（真跑；日志见 `_scratch/ikms11-selfcheck.log`，本文件只摘数字）

| # | 验证了什么 | 命令 | 真实结果 |
|---|---|---|---|
| ① | `--sample` 基线逐字节不变 | `run.py --sample` / `--sample --compare` | sha256 **与改造前完全相同**：`routes.json` `c375d902…814c`（8310 B）/ `run_log.json` `6c27bfc1…6bfb`（730 B）；compare `c194bddc…0339`（22366 B）/ `ba047513…def1`（2277 B） |
| ② | 样例连跑两遍 | 同一命令跑两遍 | `routes.json`/`run_log.json` 逐字节一致 |
| ③ | 真网 61 段全读到 | `run.py --network real`（写 `out/real/`） | `network.segments_read=61` / `nodes_read=44` / `seg_target=61`；`network.segments[]` 61 条逐段带 `length_m`/from-to/`param_source` |
| ④ | 真网 OD / 备选 / 不伤害（M1-4） | 同上 | **12 个 OD**；**3 个 OD 备选 = 2 条**；12/12 `reservation.harm_check.passed=true`；`run_log.m1_4.passed=true` |
| ⑤ | 真网段号命名空间 | 同上 | 响应共 177 处段号引用，全部 `SZ-###`（`realnet.assert_segment_namespace()` 硬校验，非自述）；路线共 38 条，`length_m` 全部补齐 |
| ⑥ | 真网默认模式连跑两遍 | `run.py --network real` 跑两遍（写 `out/real/`） | `routes.json` `c933bc43…8eee`（71036 B）/ `run_log.json` `fb125b44…504b`（3855 B），两遍逐字节一致 |
| ⑦ | 真网 `--compare`（TC-17 三项） | `run.py --network real --compare`（写 `out/real/compare/`） | 车辆群 **1800**（12 OD × 600 vph × 900 s）；**TC-17 三项全过**：① 前车 ETA 最大增加 实验组 4.88 s ≤ 30 s（对照组 16.34 s）；② 实验组橙/红 4 段 vs 对照组 9 段，**相对对照组不新增**；③ 全网总行程时间 60861.35 < 91384.47 辆·秒。`capacity_shortage_evidence.passed=true`、`lease_release_evidence.passed=true` |
| ⑧ | 真网 compare 连跑两遍 | `run.py --network real --compare` 跑两遍（写 `out/real/compare/`） | `routes.json` `8c6d1fb9…c792`（85973 B）/ `run_log.json` `4f29b0fd…addb`（4444 B），两遍逐字节一致 |
| ⑨ | 上游快照对接 | `--segments work/perception/out/latest/segments_video.json` | 命中 **2/61** 段（SZ-005/SZ-024），其余降级；采用快照 `ts=2026-10-11T13:29:56+08:00` / `window_sec=60` |
| ⑩ | 段号对不上如实降级 | `--segments work/assembly/out/latest/segments.json`（旧 SEG-### 快照） | 命中 **0/61**，10 个 `SEG-###` 段号进 `ignored_segment_ids`、**不入响应**，`ts` 不采用不匹配快照的；不混算 |
| ⑪ | 再疏导在真网可触发（默认 0 事件 ≠ 复用失效） | `--network real --compare --demand-vph 1200` | **默认 600 vph 时该演示 `events=[] / rerouted_count=0`**：不是机制没用上，是该需求水平下突发时刻没有"改道收益过滞回"的在途车（如实返回 0，不编事件）。需求调到 1200 vph：突发时刻在途 85 辆，封 `SZ-002` → **改道 1 辆走 `SZ-054`**，事件在 `comparison.scenario.reroute_demo.events`（与样例 `--compare` 是同一套 `reroute.py`，不按 source 分支） |
| ⑫ | 语法 / 硬编码 | `py_compile` 七个 `.py`；`grep 肇庆|23\.21|112\.65|吉庆` | 全过；`work/engine/*.py` 无站点名 / 坐标 / 路名硬编码 |
| ⑬ | `doc_gate` | `python scripts/doc_gate.py` | **8/8 通过** |
| ⑭ | 两种真网模式产物互不覆盖（独立审查整改） | 先跑 `--network real`、再跑 `--network real --compare`、再跑默认模式 | 默认产物在 `out/real/`（71036 B）、compare 产物在 `out/real/compare/`（85973 B），**互不覆盖**；两者各自两遍 sha 一致（见 ⑥⑧）；`--out` 显式传参优先 |

## 二十四、遗留与风险（不粉饰）

1. **真网没有段号匹配的上游指标快照**：默认 `--network real` 的 61 段 `q_vph` 全为 0（降级口径），
   `--compare` 的三组差异只由**时段预约占用**产生；上游（感知/孪生）按 `SZ-###` 出数后，用
   `--segments` 接入即可，引擎代码不用改。当前感知产物只有 2 段 `SZ-###`，属上游进度，不归本单。
2. **真网缺 `speed_limit` / `capacity_vph` 真值**：本单按站点包 defaults / 车道数推（逐边 `param_source` 留痕）；
   真值等 T2 路段属性核对表补录（`stations/network.json` 真值化归 IKMHMX）。
3. **真网节点无 `type` / 无点位表**：统一按 `intersection`，`dropoff_point` 为 `null`（不编点位）；
   真网点位归 IKMHMX / 池·S 踏勘。
4. **OD 需求是演示假设值**：`DEMO_DEMAND_VPH=600` 辆/小时/OD（与样例 OD 同量级），产物标 `demand_source`；
   真值等上游需求快照（`demand.json` 真网版）。
5. **接口层未切真网**：`work/assembly/traffic.py` 仍读 `work/engine/out/routes.json`（样例产物）；
   真网产物在 `work/engine/out/real/`（默认）与 `work/engine/out/real/compare/`（`--compare`）；
   切换属前端/接口单（IKMS17/18），**本单不碰 `work/assembly/`**。
6. **`TC-17` 的通过依赖演示需求**：600 vph 时三项全过；需求再低（如 120 vph）时三组趋同、第③项会 FAIL——
   这是"没有背景车流/需求不足"的数据事实，**不调参数凑过**，README / 产物 note 均写明口径。
7. **`reserve.py` 的 `+inf` 守卫**只影响"突发封路"演示路径，常规推荐/预约/对照数值不变（样例 sha 可证）。



# 附：决策线收尾实现记录（T1–T7，2026-10-19；由 Agent E 集成时归并）

> 集成分支 `feat/engine-closeout`：merge commit `8a88019`（A）→ `6b77f95`（C）→ `8a45c21`（B），
> 全部 `--no-ff`、零冲突。相对 T0_SHA `fe4f915` 共 10 文件 +2002/−40。
> 逐任务证据见 本批交接目录下的 T1/T2/T3/T3-fix/T4/T5/T7 报告与 `t*-verify/`（交接目录未随 PR 入库）。

## 二十五、逐任务实现记录

### T2 阈值卫生与标定预案（commit `cc856f9`，分支 feat/engine-a）

- **改了什么**：`stations/thresholds.json` decision 组新增 `reroute_threshold_s: 30`
  （**占位值，待池·P 标定**，与 `eps_harm_s` 同量级）+ `param_version` 升 `v0-demo.1`；
  `reroute.py` 的 `reroute_threshold_s(params)` 改为优先读新键、缺键回落 `eps_harm_s`
  （docstring 写明"站点包补键后不再回落"）；新增只读机检 `check_thresholds.py` 与
  扫描器 `calibration_scan.py`。
- **口径**：不改任何判定值（`x_safe`/`eps_harm_s`/`level_bounds`/`alpha`/`beta` 一字未动）。
- **真实证据数字**：`check_thresholds.py` 如实报 `x_safe=0.85 > 判级橙档 0.8`（FAIL，
  退出码 1，**预期红**）；`calibration_scan.py` 4 组网格（`x_safe∈{0.80,0.85} ×
  eps∈{30,45}`）× sample/real 双跑 8 行全真跑——结论：**0.80 三项判据全过；0.85 在
  sample 网第 2 项（无新增橙/红）必过不了**（新增 SEG-001），真网上 0.85 能过；
  **eps 30→45 对三项判据无影响**（样例/真网两组内 eps 变化判据全同）。
  基线：`routes.json` 双信封逐字节不变；`run_log` 仅 `decision_params_used` 增
  `reroute_threshold_s` 键与 `param_version` 值变化（+33 B，卡片预见例外）。
- **遗留**：`x_safe` 与判级橙档的结构性矛盾留池·P（IKMHMX）标定同桌解决；
  `reroute_threshold_s=30` 为占位值；契约 §6.3 补键名待 C 落笔（Issue 草稿见 T2 报告 §4）。

### T3 TC-12 D3 pickup_route + T3 修复（commit `77aa20e` + `94cba2e`，分支 feat/engine-b）

- **改了什么**：`run.py` 新增 `--d3`（默认关）为每个 OD 构造 1 个 D3 往返代表请求
  （`pickup_route`/`departure_route` 三段走 `walk_slots`）；T3 修复在
  `_build_d3_request()` 加 `representative: true`、候选数=1 时输出
  `no_alternative: true` + `no_alternative_reason`，`why` 如实写明代表性与备选不足。
- **口径（开发B 裁定，方案 B）**：D3 是 **representative 说明性代表样例**，
  `reservation.harm_check` 只作展示、**不作准入判据**——下游不得把 `passed=false`
  的 D3 请求当可执行推荐（契约 v2.4 待 C 落笔，原文见 T3-fix 报告 §4）。
  `no_alternative` 的候选数**由数据推导**（相邻路段 `type=pickup` 点位全集计数），
  不写死字符串。
- **真实证据数字**：样例 D3 请求 `pickup_point="P-02"`（真点位 id）、`slots_reserved=3`、
  `harm_check.passed=false`（`max_slot_x=0.9333`，失败格子在到达段 SEG-003——数据事实，
  不绕开）；`--sample --d3` 两遍 sha 一致（`b2043b09…`/`b91d6b48…`）；
  `--compare --d3` 互斥拒绝（exit 1）；真网 `points=[]` → `d3_skipped: no_pickup_point`
  （`d3_requests: 0`，不编点位）；默认路径 `--d3` 关闭零执行（基线四产物逐字节不变）。
- **遗留**：契约 v2.4 落笔（C）；D3 候选 ≥2 时的备选生成（二期，由 representative 口径兜底）。

### T4 locate TC-18（commit `87dd59c`，分支 feat/engine-c）

- **改了什么**：`locate.py` 从 W0 空壳变为可运行实现（真值直读 + σ 噪声 HMM-lite 匹配，
  +591/−11）；新增校验入口 `locate_check.py`（+546）。**未接入 `run.py` 主链**
  （`grep locate run.py` 零命中），合入对基线零影响（合并后实测四产物不变）。
- **口径**：不编坐标（样例图无锚点 → σ 档 `unavailable/geometry_frame_mismatch`，
  不当 0 分）；不得用样例 3/3 或自造夹具冒充 TC-18 验收证据。
- **真实证据数字**：样例口径 ① `truth_match_rate=1.0`（3/3，仅证链路通）；
  dev-debug 口径（自造夹具，61 车）① 61/61、② σ=10 m 0.8398 / σ=20 m **0.7901** /
  σ=30 m 0.7624（均 < 0.90 门槛）。
- **阻塞（如实记录）**：TC-18 **无验收证据**——`work/twin/out/latest/vehicles.json`
  不存在、SUMO/TraCI 不可用、统一图无 WGS-84 几何（`map_ingest.py` Issue #37 未做）。
  解除条件：装 SUMO 1.28 → `loop.py --duration 3900 --seed 42` → `map_ingest #37`
  → 重跑 `locate_check.py --network real`（责任：开发A/开发B，见 Issue 草稿 d）。

### T5 predict L0（commit `3ac593b`，分支 feat/engine-a）

- **改了什么**：`predict.py` 实现纯函数 `l0_record(segment)`（`h15=h30={q_vph 当前值,
  level 当前值}`）与 `build_snapshot(segments_path)`（读 `segments[]` 快照、沿用输入
  `ts`/`is_simulated`、按 `segment_id` 排序、**不写 `segments.json`**）；原 W0 骨架
  `predict(segment_id, horizon_min)` 零调用方且无法离全局状态实现，保留公开名**清晰报错**
  并指向新入口（docstring 已说明）；`attach_pred` 转可用实现（契约第一节
  `segments.pred` 形状，签名变更已在 T5 报告申报）。新增 `predict_cli.py`
  （`--segments` 必填、不存在即退出不猜路径；`--out` 默认 `out/latest/predict.json`）。
- **口径**：L0=当前值保持；**不引入模型、不报任何精度数字**。
- **真实证据数字**：`predict_cli.py` 两遍 sha 一致（`ff247819…`，17 segments）；
  字段机检：段键恰 `h15/h30/segment_id`、顶层恰五键、零精度字段；缺文件 exit 2；
  基线四产物不变。
- **遗留**：`predict.json` 是 gitignore 运行产物（CI/演示需先跑 CLI 生成）；
  HTTP 合并规格已给 C（T5 报告 §4），端点不归本线。

### T1 GZ 708 冒烟（Agent D 只读，零提交；分支 feat/engine-d 停在 T0_SHA）

- **结论**：`python work/engine/run.py --network real --site-id guangzhounan` **可跑**
  （两遍 sha 一致；退出码 0；无崩溃/超时）。产物落 `out/real/sites/guangzhounan/`。
- **真实证据数字**：`segments_read=708`（=登记表 `seg_target`）/ 453 节点 / 91 OD /
  备选 ≥2 的 OD 46 / 带预约请求 91（`harm_check.passed` 91/91）/ `od_derivation.skipped=4`
  （全部"进场边界不可达"，有原因）；段号命名空间纯 `GZ-###`（0 个 `SZ-###`）；
  需求来源 `demo_assumption`（`DEMO_DEMAND_VPH=600`，非实测）。
- **遗留/发现**：① TC-17② 在 GZ 上同样 FAIL（新增 8 个橙/红段 GZ-016/213/220/388/
  461/474/534/552）——根因与样例一致（`x_safe=0.85` > 橙档 0.8），**跨站一致的结构性
  冲突，非 GZ 特有 bug**；② 拓扑 7 项 FAIL（`exit_without_entry` 1 / `node_cannot_reach_exit`
  2 / `segment_uncovered` 4；非法路线 0；段覆盖 704/708）属真网几何质量，找 IKMHMX/池·S；
  ③ 限速 708/708 回落 defaults、车道数仅 16 段有值（692 段 null）、容量 692 段回落
  defaults——全部逐边登记 `param_source`，真值等 T2 核对表/IKMHMX。

### T7 TC-14 接口草案（Agent D 只写，零提交）

- **交付**：TC-14 接口一页纸（交接目录，未随 PR 入库） 一页纸九节（目标三组/模式开关 none·fastest·
  cooperative/每拍输入文件快照/引擎输出信封/注入点 TraCI `setRoute`/节奏 SUMO 1s·决策
  60s/确定性固定 seed/分工/开放问题）。**只写约定，不接闭环**。
- **遗留**：开放问题（快照原子性、暂停恢复、失败回退、三组世界重置）需 A/队长拍板，
  不能由引擎侧单方面决定。

## 二十六、集成侧记录（Agent E）

- 合并顺序 a→c→b 全部 `--no-ff`、零冲突（C 的 `docs/任务记录.md` 台账 1 行无冲突方，
  直接进入）；每步 `py_compile`/`--sample`（routes `c375d902…` 逐字节不变）/`doc_gate`
  8/8 当场验证通过。
- 合并后基线复核：routes 双信封与 T0 逐字节一致；run_log 剔除 `stations_dir` 后仅
  T2 预见的两处（`reroute_threshold_s` 新键 + `param_version` 值），其余零差异。
- 验收矩阵 12 条与已知红灯（check_thresholds 预期 exit 1、TC-17② 样例/GZ 均 FAIL、
  TC-18 证据阻塞）见 本批 T6 集成报告（交接目录，未随 PR 入库）。
