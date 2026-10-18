"""真网统一图接入（Issue IKMS11）：站点范围登记表 → 61 段真路网 → 统一图 + OD 推导 + segments 映射。

## 为什么有这个文件

决策引擎原来只读 `work/engine/samples/network_sample.json`（7 节点 `SEG-###` 样例网）；
站点 Z 的**真路网**（OSM 几何 + 拓扑，61 段 / 44 节点）此前只进展示层。本文件把真网接进引擎，
且**不写死任何站点名 / 节点 id / 段号 / 坐标**——一律从下面三份数据推：

| 数据 | 位置 | 用途 |
|---|---|---|
| 站点范围登记表 | `work/twin/site-ranges.json` | `site_id` / `seg_target` / `seg_prefix` / `out_json`（每站一条记录，换站只换数据） |
| 真网产物 | 登记表 `out_json` 指向的文件（本站 = `work/twin/netpack/network_junction.json`） | 61 段 `edges[]`（from/to/length_m/lanes/…）+ 44 节点 `nodes[]` |
| 站点包参数 | `stations/thresholds.json` 的 `grading` 组 | 缺字段时的缺省：`defaults.v_f_kmh` / `defaults.c_vph` / `saturation_flow_vph_per_lane` |

## 口径（硬）

1. **真网几何是真值**（OSM 切片）；`lanes` / `speed_limit` / `capacity_vph` 真网产物里大量为
   `null`——**缺就用站点包 defaults 并逐边写 `param_source` 标明来源**，不静默补、不编造；
2. **段数对账**：真网段数必须等于登记表 `seg_target`（本站 61）；缺边 / 多边**直接报错退出**，
   不在不完整路网上算路；
3. **段号命名空间**：真网只用登记表的 `seg_prefix`（本站 `SZ-`）三位以上段号；其它命名空间
   （`SEG-###` 样例网 / 前端旧几何）一律不进真网响应——段号对不上就**降级并留 note**，不混用；
4. **OD 从边界推导**（见 `derive_od_pairs`）：不手写节点 / 段号，规则写进 `work/engine/README.md`；
5. **确定性**：不读系统时钟、不用随机数；需要"演示时刻"时用固定常量 `DEMO_BASE_TS`，
   同一输入两遍结果逐字节一致。

用法：由 `run.py --network real` 调用，不单独执行。
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import candidates
import network

#: 本文件位于 work/engine/ → 仓库根是 parents[1]
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]

#: 站点范围登记表（唯一载体；引擎只读不写）
DEFAULT_SITE_RANGES = REPO_ROOT / "work" / "twin" / "site-ranges.json"

#: 真网统一图的节点类型：真网产物没有 type 字段（点位归站点包 points.json），
#: 本单不编落客/上客点位，统一按路口处理（写进 attributes 说明）。
DERIVED_NODE_TYPE = "intersection"

#: 无上游 segments 快照时用的**演示基准时刻**（固定常量，不读系统时钟）。
DEMO_BASE_TS = "2026-10-18T08:00:00+08:00"

#: 无上游 segments 快照时用的**演示评估窗口**（秒，与 --sample 的 window_sec 同量级）。
DEMO_WINDOW_SEC = 900.0

#: 无上游需求快照时，推导出的每个 OD 的**演示需求**（辆/小时）。
#: ⚠ 这是演示假设值（模拟），不是实测；取值与 `--sample` 的样例 OD 需求同量级（300–600 辆/小时），
#: 让真网 `--compare` 的预约/不伤害约束真的被压到、TC-17 三项对比有可读差异。
#: 真值等上游需求快照接入后从站点包/上游读（可用 --demand-vph 覆盖）。
DEMO_DEMAND_VPH = 600.0

#: M1-4 要求真网至少 3 个 OD 对；不足说明边界数据有问题，如实报错而不是硬凑。
MIN_OD_PAIRS = 3

#: 每个进场边界推导几个行程终点（演示 OD 覆盖广度，不是判据数值）。
#: 取值理由：真网每个进场方向取"候选路线最丰富"的 3 个可达内部节点，
#: 既覆盖不同方向的到达流量，又能让 K=3 候选 / 路径重叠度约束在真网可验（M1-4 备选 ≥2）。
OD_DESTINATIONS_PER_ENTRY = 3

#: segments 快照里允许透传到引擎的字段（契约第一节；引擎只消费这些）
SEGMENT_FIELDS = (
    "source",
    "q_vph",
    "v_kmh",
    "v_f_kmh",
    "k_vpk",
    "L_q_m",
    "L_seg_m",
    "T_d_min",
    "x",
    "c_base_vph",
    "c_vph",
    "factors_applied",
    "ci",
    "level",
    "level_name",
    "triggered_by",
    "confidence",
    "data_age_s",
    "pred",
    "is_simulated",
)


def read_json(path: Path) -> dict[str, Any]:
    """读一个 UTF-8 JSON 文件（显式编码，换机器不乱码）。"""
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def repo_rel(path: Path) -> str:
    """尽量给仓库相对路径（日志/产物可追溯）；不在仓库内则给绝对路径。"""
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(Path(path))


# ============================================================================
# 站点范围登记表
# ============================================================================


def load_site_ranges(config_path: Path | str | None = None) -> dict[str, Any]:
    """读站点范围登记表（`work/twin/site-ranges.json`），校验必需字段。"""
    path = Path(config_path) if config_path else DEFAULT_SITE_RANGES
    if not path.is_file():
        raise SystemExit(f"缺站点范围登记表:{path}（--network real 需要它定位真网数据）")
    payload = read_json(path)
    sites = payload.get("sites")
    if not isinstance(sites, list) or not sites:
        raise SystemExit(f"站点范围登记表 {path} 缺非空 sites 数组")
    for site in sites:
        for key in ("site_id", "site_name", "seg_target", "seg_prefix", "out_json"):
            if key not in site:
                raise SystemExit(
                    f"站点范围登记表 {path} 的站点 {site.get('site_id') or '?'} 缺字段 {key}"
                )
    default_site = payload.get("default_site")
    site_ids = [str(site["site_id"]) for site in sites]
    if default_site and str(default_site) not in site_ids:
        raise SystemExit(f"站点范围登记表 default_site={default_site!r} 不在 sites 里")
    return payload


def load_site(
    site_id: str | None = None,
    config_path: Path | str | None = None,
) -> dict[str, Any]:
    """按 `site_id` 取一条站点记录；缺省用登记表的 `default_site`。

    换站 = 往登记表加一条记录 + `--site-id`，**本模块一行不改**（手册 §8.4 / M1-1）。
    """
    payload = load_site_ranges(config_path)
    sites = payload["sites"]
    wanted = str(site_id or payload.get("default_site") or sites[0]["site_id"])
    for site in sites:
        if str(site["site_id"]) == wanted:
            return dict(site)
    known = "、".join(str(site["site_id"]) for site in sites)
    raise SystemExit(f"站点范围登记表里没有 site_id={wanted!r}（现有：{known}）")


def site_network_path(site: dict[str, Any]) -> Path:
    """登记表里的 `out_json` 是相对仓库根的路径 → 绝对路径。"""
    return (REPO_ROOT / str(site["out_json"])).resolve()


# ============================================================================
# 真网产物 → 统一图结构
# ============================================================================


def _positive_number(value: Any) -> float | None:
    """把可能是 null / 字符串 / 负数的数值规整成"正数或 None"（缺失不猜）。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0.0:
        return None
    return number


def _segment_pattern(seg_prefix: str) -> re.Pattern[str]:
    """段号命名空间：`<seg_prefix>-###`（三位以上数字；站点登记表给前缀）。"""
    return re.compile(rf"^{re.escape(str(seg_prefix))}-\d{{3,}}$")


def normalize_network(
    payload: dict[str, Any],
    site: dict[str, Any],
    grading: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """把真网产物规整成统一图结构 `{nodes, edges, attributes}`（手册 8.2）。

    返回 `(graph_payload, meta)`：
      - `graph_payload` 直接喂 `network.Graph`；
      - `meta` 留存"读了多少段 / 缺字段怎么回落 / param_source 汇总"，供产物与日志可追溯。

    缺字段口径（不编数）：
      - `length_m` 必须有（几何真值）；缺失直接报错；
      - `speed_limit` 缺失 → 站点包 `grading.defaults.v_f_kmh`（BPR 的自由流速度）；
      - `capacity_vph` 缺失 → 有 `lanes` 时按 `lanes × saturation_flow_vph_per_lane` 推，
        否则用 `grading.defaults.c_vph`；
      - `lanes` 真网抽不到就保留 `null`（**不补一个假车道数**），只影响追溯展示。
    """
    seg_prefix = str(site["seg_prefix"])
    seg_target = int(site["seg_target"])
    pattern = _segment_pattern(seg_prefix)

    if not isinstance(payload, dict):
        raise SystemExit(f"真网产物 {site['out_json']} 顶层不是对象")
    nodes = payload.get("nodes")
    edges = payload.get("edges")
    if not isinstance(nodes, list) or not nodes:
        raise SystemExit(f"真网产物 {site['out_json']} 缺非空 nodes 数组")
    if not isinstance(edges, list) or not edges:
        raise SystemExit(f"真网产物 {site['out_json']} 缺非空 edges 数组")

    stats = payload.get("stats") or {}
    stats_segments = stats.get("segments")
    if isinstance(stats_segments, int) and stats_segments != len(edges):
        raise SystemExit(
            f"真网产物自相矛盾：stats.segments={stats_segments} 但 edges[]={len(edges)} 条"
        )
    if len(edges) != seg_target:
        raise SystemExit(
            f"真网段数 {len(edges)} ≠ 登记表 seg_target={seg_target}（{site['site_id']}）："
            "缺边/多边一律报错，引擎不在不完整路网上算路（不静默补段）"
        )
    if len(nodes) != int(stats.get("nodes") or len(nodes)):
        raise SystemExit(
            f"真网产物自相矛盾：stats.nodes={stats.get('nodes')} 但 nodes[]={len(nodes)} 个"
        )

    grading_defaults = grading.get("defaults") or {}
    speed_default = _positive_number(grading_defaults.get("v_f_kmh"))
    capacity_default = _positive_number(grading_defaults.get("c_vph"))
    saturation_flow = _positive_number(grading.get("saturation_flow_vph_per_lane"))
    if speed_default is None:
        raise SystemExit("站点包 thresholds.json 的 grading.defaults.v_f_kmh 缺失：缺限速无法回落")
    if capacity_default is None and saturation_flow is None:
        raise SystemExit(
            "站点包 thresholds.json 既无 grading.defaults.c_vph 也无 saturation_flow_vph_per_lane："
            "缺容量无法回落"
        )

    seen_nodes: dict[str, dict[str, Any]] = {}
    node_id_list: list[str] = []
    boundary_flag_nodes = 0
    for node in nodes:
        node_id = str(node.get("node_id") or node.get("id") or "")
        if not node_id:
            raise SystemExit("真网产物 nodes[] 里有节点缺 node_id / id")
        if node_id in seen_nodes:
            raise SystemExit(f"真网产物 nodes[] 节点 id 重复:{node_id}")
        boundary = bool(node.get("boundary"))
        if boundary:
            boundary_flag_nodes += 1
        seen_nodes[node_id] = {
            "id": node_id,
            "type": DERIVED_NODE_TYPE,
            "lon": node.get("lon"),
            "lat": node.get("lat"),
            "degree": node.get("degree"),
            "boundary": boundary,
            "node_type_source": "derived:真网产物无 nodes[].type,统一按路口(DERIVED_NODE_TYPE)",
        }
        node_id_list.append(node_id)

    param_source_counts: dict[str, int] = {}
    lanes_missing = 0
    speed_missing = 0
    capacity_missing = 0
    edge_payloads: list[dict[str, Any]] = []
    seen_edges: set[str] = set()
    for edge in edges:
        segment_id = str(edge.get("segment_id") or edge.get("id") or "")
        if not segment_id:
            raise SystemExit("真网产物 edges[] 里有边缺 segment_id / id")
        if not pattern.match(segment_id):
            raise SystemExit(
                f"真网产物段号 {segment_id!r} 不符合登记表命名空间 {seg_prefix}-###"
                "（命名空间混用一律报错，不混算）"
            )
        if segment_id in seen_edges:
            raise SystemExit(f"真网产物段号重复:{segment_id}")
        seen_edges.add(segment_id)

        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        if src not in seen_nodes:
            raise SystemExit(f"真网段 {segment_id} 的 from={src!r} 不在 nodes 里")
        if dst not in seen_nodes:
            raise SystemExit(f"真网段 {segment_id} 的 to={dst!r} 不在 nodes 里")
        length_m = _positive_number(edge.get("length_m"))
        if length_m is None:
            raise SystemExit(f"真网段 {segment_id} 缺 length_m（几何真值缺失，不猜）")

        lanes_raw = edge.get("lanes")
        lanes = _positive_number(lanes_raw)
        if lanes_raw is None or lanes is None:
            lanes_missing += 1

        speed_raw = _positive_number(edge.get("speed_limit"))
        if speed_raw is None:
            speed = speed_default
            speed_source = "station_pack:thresholds.grading.defaults.v_f_kmh"
            speed_missing += 1
        else:
            speed = speed_raw
            speed_source = "network_junction"

        capacity_raw = _positive_number(edge.get("capacity_vph"))
        if capacity_raw is not None:
            capacity = capacity_raw
            capacity_source = "network_junction"
        elif lanes is not None and saturation_flow is not None:
            capacity = lanes * saturation_flow
            capacity_source = (
                "derived:lanes×thresholds.grading.saturation_flow_vph_per_lane"
            )
            capacity_missing += 1
        else:
            capacity = capacity_default
            capacity_source = "station_pack:thresholds.grading.defaults.c_vph"
            capacity_missing += 1

        param_source = {
            "length_m": "network_junction",
            "lanes": "network_junction" if lanes is not None else "missing(真网未抽到,保留 null)",
            "speed_limit": speed_source,
            "capacity_vph": capacity_source,
        }
        for source_value in param_source.values():
            param_source_counts[source_value] = param_source_counts.get(source_value, 0) + 1

        edge_payloads.append(
            {
                "id": segment_id,
                "section": segment_id,
                "from": src,
                "to": dst,
                "length_m": length_m,
                "lanes": lanes,
                "speed_limit": speed,
                "capacity_vph": capacity,
                "param_source": param_source,
                # 以下为真网产物自带、供可追溯展示（Graph 允许附加字段）
                "name": edge.get("name"),
                "name_raw": edge.get("name_raw"),
                "kind": edge.get("kind"),
                "oneway": edge.get("oneway"),
                "boundary": bool(edge.get("boundary")),
                "coords": edge.get("coords"),
                "way_ids": edge.get("way_ids"),
            }
        )

    graph_payload: dict[str, Any] = {
        "nodes": [seen_nodes[node_id] for node_id in node_id_list],
        "edges": edge_payloads,
        "attributes": {
            "is_simulated": True,
            "schema_version": "1.0",
            "crs": payload.get("crs"),
            "source": payload.get("source"),
            "generated_by": payload.get("generated_by"),
            "note": (
                "真网统一图（演示数据（模拟））：几何/拓扑来自站点真网产物（OSM 真值）；"
                "lanes/speed_limit/capacity_vph 缺失按站点包 defaults 回落后逐边标 param_source"
            ),
            "section_is_segment": "edges[].section = 段号 = segments 的 segment_id（真网 SZ-###）",
            "node_type_source": (
                "真网产物无 nodes[].type：统一按 intersection；落客/上客点位归站点包 points.json，"
                "本单不编点位"
            ),
            "origin_contract_map": payload.get("contract_map"),
        },
    }

    meta: dict[str, Any] = {
        "site_id": str(site["site_id"]),
        "site_name": site.get("site_name"),
        "network_file": repo_rel(site_network_path(site)),
        "source": payload.get("source"),
        "crs": payload.get("crs"),
        "generated_by": payload.get("generated_by"),
        "seg_prefix": seg_prefix,
        "seg_target": seg_target,
        "segments_read": len(edge_payloads),
        "nodes_read": len(node_id_list),
        "stats": stats,
        "node_type_source": ("derived:真网产物无 nodes[].type,统一按 intersection"),
        "boundary_source": (
            "nodes[].boundary（真网产物由脚本按无向度数 1 标记）"
            if boundary_flag_nodes
            else "fallback:无 boundary 标记时按无向度数 1 推"
        ),
        "degenerate_boundary_flag": boundary_flag_nodes == 0,
        "param_defaults": {
            "speed_limit": speed_default,
            "speed_source": "station_pack:thresholds.grading.defaults.v_f_kmh",
            "capacity_default": capacity_default,
            "capacity_source": "station_pack:thresholds.grading.defaults.c_vph",
            "saturation_flow_vph_per_lane": saturation_flow,
            "capacity_rule": (
                "有 lanes 且站点包给 saturation_flow_vph_per_lane 时 capacity = lanes × 每车道饱和流率；"
                "否则用 grading.defaults.c_vph"
            ),
        },
        "param_source_counts": param_source_counts,
        "lanes_missing": lanes_missing,
        "speed_missing": speed_missing,
        "capacity_missing": capacity_missing,
    }
    return graph_payload, meta


# ============================================================================
# OD 推导（真网边界 → OD 对）
# ============================================================================


def _undirected_degree(graph: network.Graph, node_id: str) -> int:
    """无向度数（真网产物没有 boundary 标记时的退化口径）。"""
    count = 0
    for edge_id in graph._edges:  # noqa: SLF001 —— 只读拓扑计数
        edge = graph.edge(edge_id)
        if str(edge["from"]) == node_id or str(edge["to"]) == node_id:
            count += 1
    return count


def derive_od_pairs(
    graph: network.Graph,
    meta: dict[str, Any],
    demand_vph: float,
    params: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """从真网**边界**推导 OD 对（不写死任何节点 id / 段号）。

    ## 规则（README 同文；改规则要同步 README）

    1. **边界节点**：真网产物 `nodes[].boundary=true`（脚本按无向度数 1 标记）；
       万一边界标记缺失，退化为"无向度数 1 的节点"并在 `derivation.boundary_source` 说明；
    2. **进场边界** = 只有出边、没有入边的边界节点（车从围栏外进来）；
       **离场边界** = 只有入边、没有出边的边界节点（车离开围栏）；
    3. 对每个进场边界：遍历全部**内部节点**（非边界）作为候选行程终点，按
       （**候选路线数降序**, 自由流耗时升序, 节点 id）排序，取前
       `OD_DESTINATIONS_PER_ENTRY`（3）个作为该入口的 OD 终点。
       候选路线数 = `select_candidates(K / 重叠度均读站点包 decision 组)` 在**当前真网拓扑**上
       算出的条数——它是真网拓扑 + 站点包参数的直接函数，**不是手写 OD**；
       取"候选最丰富"的终点是为了让 K=3 候选 / 路径重叠度约束在真网可验（M1-4 备选 ≥2），
       同时覆盖不同进场方向的到达流量；
    4. 每个 OD 的 `exit_node` = 从该行程终点可达的离场边界里**自由流最快**的那个
       （并列按节点 id）；终点是内部节点、出口是边界节点，两者必不相同，
       `departure_route` 才是"从落客点驶出围栏"的真实离场路线（TC-12 必现）；
    5. 不可达 / 找不到离场出口的组合**跳过并留痕**（`skipped`），不顺延硬凑；
    6. OD 顺序：进场边界 id 字典序 + 入口内第 3 步排序；`od_id = OD-R-001…`；
    7. `demand_vph` 来自上游需求快照；没有上游时用 `DEMO_DEMAND_VPH`
       （**演示假设值，不是实测**，写进 `demand_source`）。

    返回 `(od_pairs, derivation_meta)`；OD 对少于 `MIN_OD_PAIRS`（3）时**报错退出**
    （M1-4 要求 ≥3 个 OD 对；数据不够就说数据不够，不硬凑）。
    """
    node_ids = sorted(graph.node_ids)
    boundary_nodes = [
        node_id for node_id in node_ids if bool(graph.node(node_id).get("boundary"))
    ]
    boundary_source = "nodes[].boundary"
    if not boundary_nodes:
        boundary_source = "fallback:undirected_degree==1"
        boundary_nodes = [
            node_id for node_id in node_ids if _undirected_degree(graph, node_id) == 1
        ]
    if not boundary_nodes:
        raise SystemExit("真网里找不到边界节点（nodes[].boundary 缺失且无度数 1 节点）：无法推导 OD")

    entries: list[str] = []
    exits: list[str] = []
    for node_id in boundary_nodes:
        has_out = bool(graph.out_edges(node_id))
        has_in = any(
            str(graph.edge(edge_id)["to"]) == node_id for edge_id in graph._edges  # noqa: SLF001
        )
        if has_out and not has_in:
            entries.append(node_id)
        elif has_in and not has_out:
            exits.append(node_id)
    if not entries or not exits:
        raise SystemExit(
            f"真网边界方向不足：进场边界 {entries or '无'} / 离场边界 {exits or '无'}；"
            "无法推导「进场→离场」OD（不硬凑）"
        )
    boundary_set = set(boundary_nodes)
    internal_nodes = [node_id for node_id in node_ids if node_id not in boundary_set]
    if not internal_nodes:
        raise SystemExit("真网没有内部节点（全部是边界节点）：无法推导 OD")

    def free_flow_weight(edge_id: str) -> float:
        return network.free_flow_time_s(graph.edge(edge_id))

    def free_flow_eta(path: list[str]) -> float:
        return network.path_travel_time_s(graph, path, {}, params)

    weight = free_flow_weight
    k = int(params.get("k_candidates", 3))
    max_overlap = float(params.get("max_path_overlap", 0.7))

    exit_choice_cache: dict[str, tuple[float, str] | None] = {}

    def fastest_reachable_exit(from_node: str) -> tuple[float, str] | None:
        """从某个内部节点出发、自由流最快的离场边界（并列按节点 id）。"""
        if from_node in exit_choice_cache:
            return exit_choice_cache[from_node]
        best: tuple[float, str] | None = None
        for exit_node in exits:
            path = candidates.dijkstra(graph, from_node, exit_node, weight)
            if not path:
                continue
            eta_s = free_flow_eta(path)
            if best is None or (round(eta_s, 6), exit_node) < (round(best[0], 6), best[1]):
                best = (eta_s, exit_node)
        exit_choice_cache[from_node] = best
        return best

    od_pairs: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for entry in entries:
        ranked: list[tuple[int, float, str, int]] = []
        for dst in internal_nodes:
            paths = candidates.select_candidates(
                graph, entry, dst, k=k, max_overlap=max_overlap, weight=weight
            )
            if not paths:
                continue
            eta_s = free_flow_eta(paths[0])
            ranked.append((-(len(paths)), eta_s, dst, len(paths)))
        ranked.sort(key=lambda item: (item[0], round(item[1], 6), item[2]))
        picked = ranked[:OD_DESTINATIONS_PER_ENTRY]
        if not picked:
            skipped.append(
                {"entry_boundary": entry, "reason": "该进场边界到任何内部节点均不可达"}
            )
            continue
        for _neg_count, free_flow_s, dst, candidate_count in picked:
            choice = fastest_reachable_exit(dst)
            if choice is None:
                skipped.append(
                    {
                        "entry_boundary": entry,
                        "to_node": dst,
                        "reason": "行程终点到任何离场边界均不可达（算不出 departure_route）",
                    }
                )
                continue
            exit_eta_s, exit_node = choice
            od_pairs.append(
                {
                    "od_id": f"OD-R-{len(od_pairs) + 1:03d}",
                    "from_node": entry,
                    "to_node": dst,
                    "exit_node": exit_node,
                    "direction": "进场→站内节点→离场边界（边界推导）",
                    "demand_vph": float(demand_vph),
                    "derivation": {
                        "entry_boundary": entry,
                        "exit_boundary": exit_node,
                        "to_node_rule": (
                            f"该进场边界可达内部节点中候选路线数最多者（取前 "
                            f"{OD_DESTINATIONS_PER_ENTRY} 个；并列按自由流耗时 / 节点 id）"
                        ),
                        "candidate_count": candidate_count,
                        "free_flow_s": round(free_flow_s, 2),
                        "exit_free_flow_s": round(exit_eta_s, 2),
                    },
                }
            )

    if len(od_pairs) < MIN_OD_PAIRS:
        raise SystemExit(
            f"真网边界推导出的 OD 对只有 {len(od_pairs)} 个（<{MIN_OD_PAIRS}）："
            "M1-4 要求 ≥3；请核对真网边界数据，不硬凑 OD"
        )

    multi_candidate_od_count = sum(
        1 for od in od_pairs if int(od["derivation"]["candidate_count"]) >= 3
    )
    derivation = {
        "rule": (
            "边界推导：进场边界（只有出边）→ 站内候选终点（非边界节点中候选路线数最多的前 "
            f"{OD_DESTINATIONS_PER_ENTRY} 个；候选数由 K/重叠度在当前拓扑上算出）→ "
            "离场边界（该终点自由流最快的可达入口）；行程终点与离场出口不同，"
            "保证 departure_route 可算；按进场边界 id 字典序编号"
        ),
        "boundary_source": boundary_source,
        "entries": list(entries),
        "exits": list(exits),
        "destinations_per_entry": OD_DESTINATIONS_PER_ENTRY,
        "reachable_od_count": len(od_pairs),
        "multi_candidate_od_count": multi_candidate_od_count,
        "skipped": skipped,
        "demand_vph": float(demand_vph),
        "demand_source": (
            "demo_assumption:无上游真网需求快照，按 DEMO_DEMAND_VPH 演示假设值"
            "（演示数据（模拟），不是实测）"
        ),
    }
    meta["entries"] = list(entries)
    meta["exits"] = list(exits)
    meta["od_derivation"] = derivation
    return od_pairs, derivation


# ============================================================================
# segments（现状指标）映射：上游快照 → 真网段号
# ============================================================================


def _default_segment_state(edge: dict[str, Any]) -> dict[str, Any]:
    """没有上游指标时的单段降级状态：`q_vph=0`，容量/速度取统一图回落后的值。"""
    return {
        "segment_id": str(edge["section"]),
        "source": None,
        "q_vph": 0.0,
        "v_f_kmh": float(edge["speed_limit"]),
        "c_vph": float(edge["capacity_vph"]),
        "factors_applied": [],
        "data_quality": "degraded:无该段上游指标→q_vph=0",
        "param_source": {
            "q_vph": "missing:无该段上游指标→按 0 降级(契约第一节)",
            "c_vph": edge["param_source"]["capacity_vph"],
            "v_f_kmh": edge["param_source"]["speed_limit"],
        },
        "is_simulated": True,
    }


def build_segments_state(
    graph: network.Graph,
    snapshot_path: Path | str | None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """把上游 `segments` 快照按 `segment_id` 接到真网边上（契约第一节）。

    口径：
      - **只按段号精确匹配**；上游快照里属于别的命名空间（如 `SEG-###` 样例网）的条目
        **一律不用**，只留痕在 `ignored_segment_ids`——**绝不把两套段号混进同一份真网响应**；
      - 快照里没有的段 → `q_vph=0` + 站点包 defaults 降级，逐段写 `param_source`；
      - 快照的 `ts` / `window_sec` 若存在，作为真网运行的**基准时刻 / 评估窗口**（与
        `--sample` "时间戳取 segments 的"同一口径）；缺失则用固定演示常量。
    """
    sections = [str(edge["section"]) for edge in graph._edges.values()]  # noqa: SLF001
    edge_by_section = {
        str(edge["section"]): edge for edge in graph._edges.values()  # noqa: SLF001
    }
    state: dict[str, dict[str, Any]] = {
        section: _default_segment_state(edge_by_section[section]) for section in sorted(sections)
    }

    meta: dict[str, Any] = {
        "snapshot": None,
        "snapshot_ts": None,
        "snapshot_window_sec": None,
        "graph_segment_count": len(sections),
        "matched_count": 0,
        "ignored_segment_ids": [],
        "used": False,
        "notes": [],
    }
    if not snapshot_path:
        meta["notes"].append(
            "未提供上游 segments 快照（--segments）：全部路段 q_vph=0、容量/速度按站点包 defaults"
            "（演示数据（模拟）降级口径）"
        )
        return state, meta

    path = Path(snapshot_path)
    if not path.is_file():
        raise SystemExit(f"缺上游 segments 快照:{path}")
    payload = read_json(path)
    segments = payload.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError(f"上游 segments 快照 {path} 缺 segments 数组或为空（契约第一节）")
    index: dict[str, dict[str, Any]] = {}
    for segment in segments:
        segment_id = str(segment.get("segment_id") or "")
        if not segment_id:
            raise ValueError(f"上游 segments 快照 {path} 里有条目缺 segment_id")
        index[segment_id] = segment

    matched: list[str] = []
    for section in sorted(sections):
        upstream = index.get(section)
        if upstream is None:
            continue
        matched.append(section)
        entry = _default_segment_state(edge_by_section[section])
        for field in SEGMENT_FIELDS:
            if field in upstream:
                entry[field] = upstream[field]
        if _positive_number(entry.get("q_vph")) is None:
            entry["q_vph"] = 0.0
        if _positive_number(entry.get("c_vph")) is None:
            entry["c_vph"] = float(edge_by_section[section]["capacity_vph"])
        entry["data_quality"] = "upstream:segments_snapshot"
        entry["param_source"] = {
            "q_vph": f"upstream:{repo_rel(path)}",
            "c_vph": (
                f"upstream:{repo_rel(path)}"
                if _positive_number(upstream.get("c_vph")) is not None
                else edge_by_section[section]["param_source"]["capacity_vph"]
            ),
            "v_f_kmh": (
                f"upstream:{repo_rel(path)}"
                if _positive_number(upstream.get("v_f_kmh")) is not None
                else edge_by_section[section]["param_source"]["speed_limit"]
            ),
        }
        state[section] = entry

    ignored = sorted(sid for sid in index if sid not in edge_by_section)
    meta.update(
        {
            "snapshot": repo_rel(path),
            "snapshot_ts": payload.get("ts"),
            "snapshot_window_sec": payload.get("window_sec"),
            "matched_count": len(matched),
            "ignored_segment_ids": ignored,
            "used": bool(matched),
        }
    )
    if not matched:
        meta["notes"].append(
            f"上游快照段号与本真网不匹配（0/{len(sections)} 段命中）："
            "不吃快照指标、全部按 q_vph=0 + 站点包 defaults 降级；"
            "其它命名空间的段号（如 SEG-###）不混进真网响应"
        )
    elif len(matched) < len(sections):
        meta["notes"].append(
            f"上游快照覆盖 {len(matched)}/{len(sections)} 段；未覆盖段按 q_vph=0 + "
            "站点包 defaults 降级（逐段 param_source 可查）"
        )
    if ignored:
        meta["notes"].append(
            f"上游快照有 {len(ignored)} 个段号不属于本真网命名空间，已忽略（不入响应）"
        )
    return state, meta


# ============================================================================
# 可追溯输出
# ============================================================================


def network_trace(graph_payload: dict[str, Any], meta: dict[str, Any]) -> list[dict[str, Any]]:
    """逐段可追溯清单（段号 / from-to / 长度 / param_source），写进真网 routes.json。"""
    trace: list[dict[str, Any]] = []
    for edge in sorted(graph_payload["edges"], key=lambda item: str(item["id"])):
        trace.append(
            {
                "segment_id": edge["id"],
                "from_node": edge["from"],
                "to_node": edge["to"],
                "length_m": edge["length_m"],
                "lanes": edge["lanes"],
                "speed_limit": edge["speed_limit"],
                "capacity_vph": edge["capacity_vph"],
                "param_source": edge["param_source"],
                "name": edge.get("name"),
                "kind": edge.get("kind"),
            }
        )
    _ = meta  # 保留签名，便于将来把 meta 里的分段统计并进追踪块
    return trace


def _route_total_length_m(graph: network.Graph, route: dict[str, Any]) -> float:
    edges = route.get("edges") or []
    return round(sum(float(graph.edge(str(edge_id))["length_m"]) for edge_id in edges), 1)


def attach_route_lengths(requests: list[dict[str, Any]], graph: network.Graph) -> int:
    """给真网响应的每条路线补 `length_m`（米），让段号 + 长度可回溯到真网产物。

    `--sample` 产物**不做**这一步（保持基线逐字节不变）；只对真网产物加字段。
    返回补了多少条路线。
    """
    enriched = 0
    for request in requests:
        routes: list[dict[str, Any]] = []
        for key in ("arrival_route", "departure_route"):
            route = request.get(key)
            if isinstance(route, dict):
                routes.append(route)
        for route in request.get("alternatives") or []:
            if isinstance(route, dict):
                routes.append(route)
        for route in routes:
            route["length_m"] = _route_total_length_m(graph, route)
            enriched += 1
    return enriched


def assert_segment_namespace(requests: list[dict[str, Any]], seg_prefix: str) -> int:
    """硬校验：真网响应里出现的**所有段号**都必须是本真网命名空间（如 `SZ-###`）。"""
    pattern = _segment_pattern(seg_prefix)
    checked = 0
    seen: set[str] = set()
    for request in requests:
        locations = [request.get("location") or {}]
        routes = [request.get("arrival_route"), request.get("departure_route")]
        routes.extend(request.get("alternatives") or [])
        rejected = ((request.get("capacity_shortage") or {}).get("rejected_candidates")) or []
        routes.extend(rejected)
        for route in routes:
            if not isinstance(route, dict):
                continue
            for segment_id in route.get("segments") or []:
                checked += 1
                seen.add(str(segment_id))
                if not pattern.match(str(segment_id)):
                    raise SystemExit(
                        f"真网响应出现非本命名空间段号 {segment_id!r}（期望 {seg_prefix}-###）："
                        "拒绝输出混用段号的响应"
                    )
        for location in locations:
            segment_id = location.get("segment_id")
            if segment_id:
                checked += 1
                seen.add(str(segment_id))
                if not pattern.match(str(segment_id)):
                    raise SystemExit(
                        f"真网响应的 location.segment_id={segment_id!r} 不属于 {seg_prefix}-###"
                    )
    return checked


def count_route_segments(requests: list[dict[str, Any]], seg_prefix: str) -> dict[str, int]:
    """统计真网响应里的路线条数 / 段号个数（自检与日志用）。"""
    pattern = _segment_pattern(seg_prefix)
    route_count = 0
    segment_count = 0
    od_with_alternative = 0
    od_with_reservation = 0
    for request in requests:
        routes = [request.get("arrival_route"), request.get("departure_route")]
        alternatives = request.get("alternatives") or []
        routes.extend(alternatives)
        for route in routes:
            if not isinstance(route, dict):
                continue
            route_count += 1
            for segment_id in route.get("segments") or []:
                if pattern.match(str(segment_id)):
                    segment_count += 1
        if len(alternatives) >= 2:
            od_with_alternative += 1
        if isinstance(request.get("reservation"), dict):
            od_with_reservation += 1
    return {
        "request_count": len(requests),
        "route_count": route_count,
        "segment_ref_count": segment_count,
        "od_with_alternative": od_with_alternative,
        "od_with_reservation": od_with_reservation,
    }
