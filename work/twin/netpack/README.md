# work/twin/netpack · 站点 OSM 切片 → **路线** → **路段**（含拓扑）

> ### ⚠️ 两代口径并存（2026-10-17）
>
> | | 脚本 | 切法 | 段数 | 状态 |
> |---|---|---|---|---|
> | **第一代（旧）** | `build_station_pack.py` | 按**路名归并** | **21 段**，只出几何 | **已被取代、21 段退役**（业主 2026-10-17 裁定「大屏也切新段」）。现仅作前端切换完成前的**过渡几何**，切换后删除 |
> | **第二代（现行）** | `build_junction_pack.py` | **先获取路线 → 再分段 → 再打标签** | **97 段**（全量）/ **61 段**（站区 500 m 内），出**几何 + 拓扑** | ✅ **定稿**（IKMERX） |
>
> **别再按第一代口径改东西**：新代码、新数据一律用第二代；第一代只许删、不许加。

---

## 一、第二代口径（**现行**）：三步，顺序不能反

> 业主 2026-10-17 原话：「**先获取路线，路线获取好后再进行分段，分段打标签；路线都获取不好，所以分段也是错的。**」

| 步 | 做什么 | 关键纪律 |
|---|---|---|
| **① 获取路线** | 按路名归并 + 沿共享 OSM 节点串成整条路 + 端点相距 ≤ `--snap-m`(30 m) 的两片接起来 | **顶点一个都不改**（几何就是 OSM 原始折线） |
| **② 分段** | 找**路口顶点**：同一位置同时落在 ≥2 条不同路线上（容差 `--junction-tol-m`，默认 2 m，用空间聚类实现）→ 在路线**自身的路口顶点**处切开 | **不插值、不移动任何点**；段的两端就是路口，`from`/`to` 直接得出（**拓扑是副产品**） |
| **③ 打标签** | 段名 = `路名`，**同名多段时才**加 `（起路口→止路口）` 后缀；`kind` / `way_ids`（按点溯源）/ `lanes` / `oneway` 从 OSM 抽 | **没有真实路名就沿用通用译名，绝不编造**；抽不到的属性就是 `null` |

### 四项裁定（**IKMERX 定稿，业主 2026-10-17 验收**）

| # | 项 | 定稿 | 依据 |
|---|---|---|---|
| ① | **范围** | **圆心 = 站点 OSM 坐标**；**半径自动推** = 站区车道（`service=parking_aisle`/`driveway`/`amenity=parking`）最远点 **× 1.2**，四舍五入到 **50 m**；该站没画站区车道时回落「全部路网最远点 × 0.45」 | 每站大小不同，**不能全靠人量**；肇庆东验算：429 m ×1.2 = 515 → **500 m**，与业主口述一致 |
| ② | **粒度** | **按交叉口之间一段** | 路口天然带拓扑；每段有自己的车道/限速/容量，BPR 才有落点 |
| ③ | **无名路** | 段名 = 路名；同名多段才加后缀；无真实路名沿用**通用译名** | **不许编造路名** |
| ④ | **段数** | **97 段**（切片全量）/ **61 段**（500 m 范围内） | 由 ② 的粒度 + ① 的范围共同决定；**范围一变要重跑**；每站的段数目标登记在 `work/twin/site-ranges.json` 的 `seg_target`（不是靠 `--seg-count` 拆长路凑数） |

### 硬约束：几何保真自检

> **产出的每一个顶点都必须在 OSM 原始节点坐标集合里**；违反即**退出码 2**，且**在写盘之前**判失败（不落坏产物）。

**为什么有这条**：第一版跳过了「路线」这一步，直接对 way 做**节点吸附**再切段 —— 吸附会把端点坐标**替换**成另一个点，折线被拉扯变形：停车场里 16~19 m 的车位排被横着连起来，图上出现**横穿车位排的假线**（业主肉眼发现的）。有了这条自检，这类错误**结构上不可能再出现**。

### 一键复现（**全部默认值来自站点范围登记表**）

```bash
# 在仓库根执行：默认读 work/twin/site-ranges.json 的 zhaoqingdong 记录
python work/twin/netpack/build_junction_pack.py --site-id zhaoqingdong

# 只校验：重跑一遍与既有产物**逐字节**比对（不写盘，不一致非 0 退出）
python work/twin/netpack/build_junction_pack.py --site-id zhaoqingdong --check

# 三方对账：登记表 ↔ 路网产物 ↔ 前端站点包 / 切片 bbox
python work/twin/netpack/check_site_ranges.py
```

**输出两件**：
- `network_junction.json` —— **几何 + 拓扑 + 属性占位**（`nodes[]` / `edges[]` / `stats` / `range_reason` / `contract_map`）；
- `stationZ_junction.network.ts` —— 前端站点包几何（**切换前端时才用**）。

### 站点范围登记表（Issue IKM4B4，**每站一份**）

**唯一载体**：`work/twin/site-ranges.json`。脚本的参数 / 路径 / 范围 / 段数目标全部从它读；**脚本从不写这张表**（改配置只能人工编辑）。

| 字段 | 含义 |
|---|---|
| `site_id` / `site_name` | 站标识 / 展示名（脚本里不出现任何站点名） |
| `anchor_lonlat` | 站点锚点 `[lon, lat]`（圆心；来自 OSM 站点坐标） |
| `range_m` | **演示范围半径**（米）。肇庆东 = 500 m（业主 2026-10-17 口径） |
| `pull_bbox` | **拉取范围** `[min_lon, min_lat, max_lon, max_lat]`——比演示范围放大一圈，留 `role: "boundary"` 的上游断面（M1-10）；**与 range_m 分开登记，不混成一个** |
| `seg_target` | 该站**路段数目标**（人工确认）；与 `range_m` 成对登记 |
| `seg_prefix` / `snap_m` / `junction_tol_m` / `min_seg_m` / `min_coverage_pct` | 该站分段参数 |
| `osm_file` / `out_json` / `out_ts` | 该站切片与产物路径（相对仓库根） |
| `station_pack_ts` / `station_pack_meta_ts` | 前端站点包几何 / 元信息路径（供对账脚本用） |
| `range_source` | `manual`（人工圈定）/ `script`（脚本推定）/ `ai-assisted`（AI 候选 + 人工确认） |
| `decided_by` / `date` / `evidence` | 谁定的、哪天、凭什么（脚本推定的写清依据）——**范围不许"没来由"** |

**来源规则（脚本 / AI 只出候选，人工确认才生效）**：
- `script` 站：`build_junction_pack.py` 每次用**同一算法复算**范围并与登记表对账（不一致 → 退出码 2，**脚本不自动改登记表**）；
- `manual` 站：直接用 `range_m`，不自动推；
- `ai-assisted`：AI / 脚本只出**候选**（依据：路网密度、边界断面位置、OD 覆盖），**必须人工确认后**才写进表；
- 范围不是官方划定、**不报精度数字**；几何真值来自 OSM。

**大屏 / 接口可查**：登记表的 `range_m` / `range_source` / `seg_target` 落进站点包 `station` 字段（`range_m` / `range_source` / `segment_count` + `subtitle`），
大屏页脚显示「本站范围 X m（来源）· 路段 N 条」；`GET /api/traffic/meta` 的 `station` 直接带这三个字段。

### 换一个站要改什么

**只往 `work/twin/site-ranges.json` 加一条记录**，然后 `--site-id <新站>` 跑脚本 —— **脚本一行不改**（手册 §8.4 / IKM4B4 专属一）。
加记录后用 `check_site_ranges.py` 对账；`--auto-range` 只打印**候选范围**并提示"确认后人工改登记表"，不写配置。

> ⚠️ `stations/map_source.json` 仍是 **IKLLX2 的 7 节点占位件**（`bbox` 与本目录切片无关）。
> 本目录的拉取范围已登记在 `site-ranges.json` 的 `pull_bbox` + 切片本身；`stations/map_source.json`
> 的真值重建归 `map_ingest.py` / 数据契约收口，**本单不手改 `stations/` 下 JSON**（开发规范第 7 节）。

### 与 `stations/network.json` 的关系（**待开发B 裁定**）

本目录产出的 `network_junction.json` 与引擎读的 `stations/network.json` **同义不同形**：

- `stations/network.json` 至今仍是 **7 节点 / 17 边占位件**（它自己的 `attributes.note` 写着「待 `map_ingest.py` 产出真值」）；
- 本节产物是**站点包 Z 真路网**的图结构，字段用 `contract_map` 记录与契约的对应，并补了同值别名 `nodes[].id` / `edges[].id`；
- `nodes[].x / .y` 因契约写「x/y 单位 m」与「站点包统一存 WGS-84」冲突，**本产物不输出**，列为 `_missing_by_contract`，**等开发B 裁定**。

---

## 二、第一代口径（**将退役**）：按路名归并

`build_station_pack.py`（2026-10-15，业主口径「按路名归并」）：

1. **归并键**：有名用 `name`；无名按 `service`；再退 `highway`；
2. **串链**：同组内共享 OSM 节点首尾相接成一串；
3. **并片**：端点相距 ≤ `SNAP_M`（30 m）就算同一路口的两侧，接起来；
4. **剔碎**：不足 `MIN_SEG_M`（60 m）的片丢弃。

产物：`network.json`（21 段，带 OSM `way_ids`）+ `stationZ.network.ts`（前端几何）。

**为什么退役**：它把「一条路」当成「一条路段」，**没有路口分段、也没有拓扑** —— 决策层算不了路。
业主 2026-10-17 已裁定：**大屏也切新段，21 段退役**。切换动作归 **IKMDKY 子单①（段号冻结）**：新段号是 3 位（`SZ-001…`），现役是 2 位（`SZ-01…`），前端要连带改段号格式。

> **第一代产物现在的定位**：前端切换完成前的过渡几何，**只许删、不许加**。

---

## 三、不做什么

- **不装 SUMO、不跑 `netconvert`、不碰后端** —— 本目录只出「可点击 / 可算路的路段」，仿真链路是另一条线；
- **不判定主干 / 分支** —— 业主明说先不定；走廊落位另开单（`kind` 的 `main`/`ramp` 只是**路型**，不是"主干裁定"）；
- **不带任何指标** —— `length_m` 等几何量是真值；`lanes`/`oneway` 从 OSM 抽（抽不到即 null）；`speed_limit` / `capacity_vph` / `t0` **一律 null**，等 **T2 路段属性核对表**补，**绝不编造**。

---

## 四、一处需要留意的坑

**图必须建在折线顶点级**：干道是一条长折线，场区通道挂在它的**中间顶点**上。
只用首尾点建边会把场区判成不连通 —— 本项目已经因此踩过三次。
第二代的口径是「**路口顶点处切**」，天生就在顶点级，不会再踩；但**不要**改成「只按首尾点建边」。

---

## 五、方向 / 车道 / 贯通性 + 自动拓扑校验（Issue IKNB9H）

> **业主 2026-10-18**：道路是**有来有回的双向车道**、还有左右车道；单向车道必须**贯通**
> （有头有尾，不能到头只能原地掉头/消失）；路线方向不能只靠人看，要**自动判别**。

### 5.1 为什么是「后处理」而不是改构建脚本

`network_junction.json` 由 `build_junction_pack.py`（IKMERX / 多站单 IKNB9F）产出，正在被别的单改。
本单**不重写构建脚本**：`topology.py` 读原产物 → 补方向/车道/贯通字段 → **另写**
`network_junction.enriched.json`，**原文件保持不变**（W1/SUMO 仍读原文件）。

### 5.2 产物与命令

```bash
# 1) 方向/车道/贯通性后处理（默认站；换站加 --site-id）
python work/twin/netpack/topology.py
python work/twin/netpack/topology.py --check        # 重算与既有 enriched 逐字节比对，不写盘

# 2) 自动拓扑校验（不靠人看图；失败 non-zero，报告 topology_report.json）
python work/twin/netpack/tools/check_topology.py
python work/twin/netpack/tools/check_topology.py --routes work/engine/out/real/routes.json   # 复核引擎路线
python work/twin/netpack/tools/check_topology.py --self-test   # 正常 PASS / 人为断头 FAIL / 非法掉头 FAIL

# 3) 全链路自检（真跑，证据写 topology_selftest.json）
python work/twin/netpack/tools/selftest_topology.py
```

| 产物 | 内容 |
|---|---|
| `network_junction.enriched.json` | **Z 站 61 段** / **GZ 站 433 段**（`guangzhounan/`）全量方向/车道/贯通性 + `field_sources`；**不覆盖原 JSON** |
| `topology_report.json` | schema / 边界角色 / 单向贯通 / 双向配对 / 主干道截断 / 有向可达性 / U-turn 逐项判据与失败明细 |
| `topology_selftest.json` | 自检证据：Z 站全量、两个反例 FAIL、引擎两遍一致、样例/W1/接口只读不退化、doc_gate 8/8 |

### 5.3 新增字段（每个 `edge` 至少这些；全部标 `field_sources`）

| 字段 | 取值 / 来源 |
|---|---|
| `direction` | `forward`（`oneway=yes`）/ `reverse`（`oneway=-1`）/ `bidirectional`（`oneway=no`；**未标注按 OSM 缺省双向**，标 `default`） |
| `lanes_forward` / `lanes_backward` / `lanes_total` | 只认原产物 OSM `lanes` 总数：单向段按方向落位、另一向 0（derived）；**双向段没有 `lanes:forward/backward` → 前/后向留 `null`，不拆分、不编造** |
| `opposite_segment_id` | 端点完全互逆的**显式段号**；双向单几何段不虚构配对，反向走 `_rev` 语义 |
| `u_turn_allowed` | 仅**双向段 + 端点无向度数 1（断头）**允许；其余 false（OSM 切片没有掉头限制数据，derived） |
| `left_turn_allowed` / `left_turn_allowed_reverse` | 按相邻段转向角几何推导（左转 = 有向角 ∈ [-150°, -30°]）；没有坐标 → false + `default` |
| `continuity` | `head_connected` / `tail_connected` / `chain_id` / `chain_name` / `is_main_road` / `gap_to_next_m` / 最近候选连接点 |
| `field_sources` | 每个字段来源只能是 `osm` / `derived` / `default`；另有 `notes` 写清推导口径 |

**一条重要修正：边界不能只按无向度数 1 判。** 肇庆东的 `N-006`（鼎湖大道南向起点 + 连接匝道，
两条边都朝外）无向度数 2 → 原 `nodes[].boundary=false`，但有向**入度为 0**，实际是进场边界。
只按原 boundary 判可达性会把 `SZ-014` / `SZ-059` 误判为不可达。`topology.py` 因此按**有向出入度**
补 `nodes[].boundary_role`（entry / exit / both / through / dead_end），并单独登记派生边界
（`enrichment.findings.derived_boundaries`，含距锚点距离）；**原文件不改**，人工可复核。

### 5.4 校验判据（`check_topology.py`）

- **单向段贯通**：非边界单向段的**行车末端必须有可通行后继**，否则 `oneway_tail_without_successor` → **FAIL**；
- **双向配对**：双向段必须有 `_rev` 反向遍历；有 `opposite_segment_id` 的段必须端点互逆；
- **主干道截断**：同名主干道按共享节点串链，非边界端点报 `main_road_gap`——孤立断头 FAIL，
  落在路口（可能真实终点/命名截断）WARN + 最近同名候选；
- **有向可达性**：每个进场边界至少 1 条完整路径到离场边界、每个离场边界至少被 1 个进场到达；
  所有节点/段必须在某条「入→出」路径上；不可达段可列白名单（须给理由）；
- **非法掉头**：每段做「正→反」探针，`u_turn_allowed=false` 必须判非法；`--routes` 复核真实路线；
- **连接候选**：断头/主干道端点按 ≤200 m 找最近候选，**只进报告，绝不自动写图、不手改 JSON**。

### 5.5 本轮 Z 站结果（2026-10-18 真跑）

- 61 段（33 双向 / 28 单向）+ 44 节点；`lanes` 总数已知 10 段 / 缺 51 段（缺的保持 `null`）；
- 9 个进场边界 / 8 个离场边界（含派生边界 `N-006`）；所有 44 节点、61 段都在有向「入→出」路径上；
- `topology_report.json`：**FAIL 0 / WARN 2**（鼎湖大道两处路口终止，待人工核对，不作为 FAIL）；
- 反例：人为把 `SZ-010` 改反向 → `oneway_tail_without_successor` FAIL；构造 `SZ-021 → SZ-021_rev`
  非法掉头路线 → `illegal_u_turn` FAIL；
- 桥梁：`selftest_topology.py` 同时锁住引擎两遍一致、`--sample` 逐字节基线、`sumonet` 只读输入链。

### 5.6 范围与遗留

- **广州南站（IKNB9F）已补跑（IKNC4J）**：GZ 真网 433 段 →
  `topology.py --site-id guangzhounan` 产出 `guangzhounan/network_junction.enriched.json`（433 段 / 290 节点；`--check` 与重算逐字节一致）；
  `tools/check_topology.py --site-id guangzhounan` 产出 `guangzhounan/topology_report.json`（entries 34 / exits 30）。
  ⚠️ **GZ 报告 FAIL 36 / WARN 72**：10 处 `oneway_tail_without_successor`（5 个非边界断头 N-010 / N-102 / N-151 / N-236 / N-254）+ 26 条 `reachability`（9 节点 + 17 段不可达），全部落在 **800 m 演示范围裁剪边界**（单向路在范围边界被截断、裁剪后 raw `boundary` 未重标）——**如实登记为已知数据边界，不改判据、不造假**；修法随 IKNAUQ 范围/边界口径强化（裁剪后重算 boundary）或放宽范围后复验。Z 站 enriched/report 不受影响（仍 FAIL 0 / WARN 2、逐字节不变）。
  引擎 `--site-id guangzhounan` 已优先读 enriched（`topology_source=enriched`）。
- `left_turn_allowed` 目前只做**字段与报告**，不参与算路（OSM 切片没有 turn restriction 数据，
  强行禁左会引入无依据的断连）；U-turn 已真正参与引擎算路。
- 本目录所有 JSON 都是**脚本产物**，不许手改；改规则就改 `topology.py` 再重跑。
