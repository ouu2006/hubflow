#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动拓扑校验（Issue IKNB9H）：不靠人看图，FAIL 必须 non-zero。

## 它检查什么（每条都可机器复现）

| 检查 | 判据 | 失败/告警 |
|---|---|---|
| `schema` | 61 段每段都有 direction / 车道三件套 / opposite / u_turn / left_turn / continuity / field_sources；来源值只能是 osm / derived / default；**不编车道数** | 缺字段 / 类型错 / 来源非法 / 车道与 raw `lanes` 矛盾 → FAIL |
| `boundary_roles` | 有向出入度派生的 `boundary_role` 与遍历图一致；无入边/无出边的非 boundary 节点必须登记为派生边界 | 不一致 → FAIL |
| `oneway_successor` | **每个非边界的单向段**，行车末端必须有可通行后继（排除自身反向）；有向边界节点除外 | 无后继 → **FAIL** |
| `bidirectional_pairing` | 双向段必须有 `_rev` 反向遍历；有 `opposite_segment_id` 的段必须端点互逆、方向相反 | 配对断裂 → FAIL |
| `main_road_gap` | 同名主干道按共享节点串链；链路端点在非边界路口/断头要报 `main_road_gap`；孤立断头（总度数 1）FAIL，路口终止为待核对告警 | 断头 FAIL / 路口终止 WARN |
| `reachability` | 每个 boundary 入至少到 1 个出、每个出至少被 1 个入到达；所有节点/段都在"入→出"有向路径上；不可达段可列白名单（须给理由） | 不可达 → FAIL（白名单内降级 WARN） |
| `u_turn` | 每段做"正→反"探针：`u_turn_allowed=false` 必须判非法掉头、`true` 必须放行；可选 `--routes` 校验真实路线；`--all-pairs` 全节点对自洽 | 探针不符 → FAIL |
| `connection_candidates` | 断头/主干道链路端点按 ≤200 m 找最近候选连接，**只出报告，绝不自动写图** | 只记录，不改图 |

## 用法

```bash
# 默认站：读 network_junction.enriched.json，写 topology_report.json；失败 non-zero
python work/twin/netpack/tools/check_topology.py

# 校验引擎产物里的路线（含方向/非法掉头）
python work/twin/netpack/tools/check_topology.py --routes work/engine/out/real/routes.json

# 全节点对掉头自洽（更慢）
python work/twin/netpack/tools/check_topology.py --all-pairs

# 人为反例自检：正常图 PASS、人为断头 FAIL、非法掉头路线 FAIL
python work/twin/netpack/tools/check_topology.py --self-test
```

## 反例（自检真的构造并断言 FAIL）

1. **人为断头**：把一条单向段的 direction 从 forward 改成 reverse，使其上游段
   的行车末端失去后继 → `oneway_successor` 必须 FAIL；
2. **非法掉头**：构造一条 `SZ-021 → SZ-021_rev`（该段 `u_turn_allowed=false`）
   的路线 → `u_turn` 必须 FAIL，且报 `illegal_u_turn`。

退出码：0 = 通过；1 = 有 FAIL；2 = 输入/参数错误。
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

#: 本文件位于 work/twin/netpack/tools/ → netpack 在 parents[1]
HERE = Path(__file__).resolve().parent
NETPACK = HERE.parent
REPO_ROOT = NETPACK.parents[2]
sys.path.insert(0, str(NETPACK))

import topology  # noqa: E402  （同目录模块，显式加 sys.path）

DEFAULT_REPORT_NAME = "topology_report.json"

#: 检查项顺序（报告也按这个顺序）
CHECK_ORDER = (
    "schema",
    "boundary_roles",
    "oneway_successor",
    "bidirectional_pairing",
    "main_road_gap",
    "reachability",
    "u_turn",
    "routes",
)

SEVERITY_FAIL = "fail"
SEVERITY_WARN = "warn"


def _finding(code: str, message: str, **extra: Any) -> dict[str, Any]:
    item = {"code": code, "message": message}
    item.update(extra)
    return item


def _result(name: str, failures: list[dict[str, Any]], warnings: list[dict[str, Any]], details: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "passed": not failures,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        "warnings": warnings,
        "details": details,
    }


# ============================================================================
# 输入
# ============================================================================


def default_paths(site_id: str | None, config: str | None) -> tuple[Path, Path]:
    site = topology.pick_site(site_id, config)
    raw = topology.raw_network_path(site)
    enriched = topology.enriched_path_for(raw)
    return enriched, raw


def load_graph(graph_path: Path) -> dict[str, Any]:
    if not graph_path.is_file():
        raise SystemExit(f"缺校验图:{graph_path}（先跑 work/twin/netpack/topology.py）")
    return topology.read_json(graph_path)


def load_allow_unreachable(path: str | None) -> tuple[dict[str, Any], Path | None]:
    if not path:
        return {"nodes": [], "segments": [], "reason": None, "file": None}, None
    target = Path(path)
    if not target.is_file():
        raise SystemExit(f"缺不可达白名单:{target}")
    payload = topology.read_json(target)
    return {
        "nodes": [str(item) for item in (payload.get("nodes") or [])],
        "segments": [str(item) for item in (payload.get("segments") or [])],
        "reason": payload.get("reason"),
        "file": topology.repo_rel(target),
    }, target


# ============================================================================
# 1) schema
# ============================================================================


def check_schema(payload: dict[str, Any], traversal: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    edges = payload.get("edges") or []
    by_id = {str(edge.get("segment_id")): edge for edge in edges}
    outgoing, traversal_by_id = topology.build_adjacency(traversal)
    expected_sources = {
        "direction",
        "lanes_forward",
        "lanes_backward",
        "lanes_total",
        "opposite_segment_id",
        "u_turn_allowed",
        "left_turn_allowed",
        "left_turn_allowed_reverse",
        "continuity.head_connected",
        "continuity.tail_connected",
        "continuity.chain_id",
        "continuity.is_main_road",
        "continuity.gap_to_next_m",
    }
    counts = defaultdict(int)

    for edge in edges:
        segment_id = str(edge.get("segment_id") or "?")
        missing = [field for field in topology.EDGE_TOPOLOGY_FIELDS if field not in edge]
        if missing:
            failures.append(
                _finding("schema_missing_field", f"{segment_id} 缺字段 {missing}", segment_id=segment_id)
            )
            continue
        direction = edge.get("direction")
        if direction not in ("forward", "reverse", "bidirectional"):
            failures.append(
                _finding("schema_bad_direction", f"{segment_id} direction={direction!r}", segment_id=segment_id)
            )
            continue
        continuity = edge.get("continuity")
        if not isinstance(continuity, dict):
            failures.append(
                _finding("schema_bad_continuity", f"{segment_id} continuity 不是对象", segment_id=segment_id)
            )
            continue
        missing_continuity = [field for field in topology.CONTINUITY_FIELDS if field not in continuity]
        if missing_continuity:
            failures.append(
                _finding(
                    "schema_missing_continuity_field",
                    f"{segment_id} continuity 缺 {missing_continuity}",
                    segment_id=segment_id,
                )
            )
            continue

        sources = edge.get("field_sources")
        if not isinstance(sources, dict):
            failures.append(
                _finding("schema_missing_sources", f"{segment_id} 缺 field_sources", segment_id=segment_id)
            )
            continue
        missing_sources = sorted(expected_sources - set(sources))
        if missing_sources:
            failures.append(
                _finding(
                    "schema_missing_source_field",
                    f"{segment_id} field_sources 缺 {missing_sources}",
                    segment_id=segment_id,
                )
            )
        bad_sources = sorted(
            {str(value) for value in sources.values()} - set(topology.FIELD_SOURCES)
        )
        if bad_sources:
            failures.append(
                _finding(
                    "schema_bad_source_value",
                    f"{segment_id} field_sources 出现非法来源 {bad_sources}（只允许 osm/derived/default）",
                    segment_id=segment_id,
                )
            )

        # 车道数与 raw OSM lanes 对账：不编真实车道数
        raw_lanes = topology.parse_lanes(edge.get("lanes"))
        lanes_total = edge.get("lanes_total")
        lanes_forward = edge.get("lanes_forward")
        lanes_backward = edge.get("lanes_backward")
        for name, value in (
            ("lanes_forward", lanes_forward),
            ("lanes_backward", lanes_backward),
            ("lanes_total", lanes_total),
        ):
            if value is not None and (not isinstance(value, int) or value < 0):
                failures.append(
                    _finding("schema_bad_lanes", f"{segment_id} {name}={value!r} 必须是非负整数或 null", segment_id=segment_id)
                )
        if lanes_total != raw_lanes:
            failures.append(
                _finding(
                    "schema_lanes_total_mismatch",
                    f"{segment_id} lanes_total={lanes_total!r} ≠ raw OSM lanes={raw_lanes!r}（不编/不改真实车道数）",
                    segment_id=segment_id,
                )
            )
        if direction == "forward":
            if lanes_backward != 0:
                failures.append(
                    _finding(
                        "schema_oneway_backward_lanes",
                        f"{segment_id} 单向正向 lanes_backward={lanes_backward!r}，应为 0（derived）",
                        segment_id=segment_id,
                    )
                )
            if raw_lanes is not None and lanes_forward != raw_lanes:
                failures.append(
                    _finding(
                        "schema_oneway_forward_lanes",
                        f"{segment_id} 单向正向 lanes_forward={lanes_forward!r} ≠ raw lanes={raw_lanes}",
                        segment_id=segment_id,
                    )
                )
        elif direction == "reverse":
            if lanes_forward != 0:
                failures.append(
                    _finding(
                        "schema_oneway_forward_lanes",
                        f"{segment_id} 单向反向 lanes_forward={lanes_forward!r}，应为 0（derived）",
                        segment_id=segment_id,
                    )
                )
            if raw_lanes is not None and lanes_backward != raw_lanes:
                failures.append(
                    _finding(
                        "schema_oneway_backward_lanes",
                        f"{segment_id} 单向反向 lanes_backward={lanes_backward!r} ≠ raw lanes={raw_lanes}",
                        segment_id=segment_id,
                    )
                )
        else:
            if lanes_forward is not None or lanes_backward is not None:
                if sources.get("lanes_forward") != "osm" or sources.get("lanes_backward") != "osm":
                    failures.append(
                        _finding(
                            "schema_bidirectional_lanes_invented",
                            f"{segment_id} 双向段没有 OSM 分向车道数，却给了 lanes_forward/backward（不编造）",
                            segment_id=segment_id,
                        )
                    )

        # 配对
        opposite_id = edge.get("opposite_segment_id")
        if opposite_id is not None:
            other = by_id.get(str(opposite_id))
            if other is None:
                failures.append(
                    _finding(
                        "schema_opposite_missing",
                        f"{segment_id} opposite_segment_id={opposite_id!r} 不在 edges[] 里",
                        segment_id=segment_id,
                    )
                )
            else:
                if (str(other.get("from")), str(other.get("to"))) != (
                    str(edge.get("to")),
                    str(edge.get("from")),
                ):
                    failures.append(
                        _finding(
                            "schema_opposite_endpoints",
                            f"{segment_id} 与 {opposite_id} 端点不互逆",
                            segment_id=segment_id,
                        )
                    )
                if str(other.get("direction")) == "bidirectional" and direction == "bidirectional":
                    warnings.append(
                        _finding(
                            "schema_opposite_both_bidirectional",
                            f"{segment_id} 与 {opposite_id} 都标双向，反向配对语义重复",
                            segment_id=segment_id,
                        )
                    )

        # 贯通字段与遍历图对账
        own = [item for item in traversal if item["segment_id"] == segment_id]
        if direction == "bidirectional":
            expected_head = bool(
                [item for item in outgoing.get(str(edge["to"]), []) if item["segment_id"] != segment_id]
            )
            expected_tail = bool(
                [
                    item
                    for item in traversal
                    if item["to"] == str(edge["from"]) and item["segment_id"] != segment_id
                ]
            )
        else:
            item = next((entry for entry in own if entry["edge_id"] == segment_id), None)
            expected_head = bool(
                [
                    candidate
                    for candidate in outgoing.get(item["to"] if item else "", [])
                    if candidate["segment_id"] != segment_id
                ]
            )
            expected_tail = bool(
                [
                    candidate
                    for candidate in traversal
                    if item is not None
                    and candidate["to"] == item["from"]
                    and candidate["segment_id"] != segment_id
                ]
            )
        if bool(continuity.get("head_connected")) != expected_head:
            failures.append(
                _finding(
                    "schema_continuity_stale",
                    f"{segment_id} continuity.head_connected={continuity.get('head_connected')} "
                    f"与遍历图算出的 {expected_head} 不一致",
                    segment_id=segment_id,
                )
            )
        if bool(continuity.get("tail_connected")) != expected_tail:
            failures.append(
                _finding(
                    "schema_continuity_stale",
                    f"{segment_id} continuity.tail_connected={continuity.get('tail_connected')} "
                    f"与遍历图算出的 {expected_tail} 不一致",
                    segment_id=segment_id,
                )
            )
        if bool(continuity.get("is_main_road")) != (str(edge.get("kind")) == "main"):
            failures.append(
                _finding(
                    "schema_main_road_flag",
                    f"{segment_id} continuity.is_main_road 与 kind={edge.get('kind')!r} 不一致",
                    segment_id=segment_id,
                )
            )
        if not continuity.get("chain_id"):
            failures.append(
                _finding("schema_missing_chain", f"{segment_id} 缺 chain_id", segment_id=segment_id)
            )
        counts["segments_checked"] += 1

    details = {
        "segments": len(edges),
        "segments_checked": counts["segments_checked"],
        "field_sources_allowed": list(topology.FIELD_SOURCES),
    }
    return _result("schema", failures, warnings, details)


# ============================================================================
# 2) boundary roles
# ============================================================================


def check_boundary_roles(payload: dict[str, Any], traversal: list[dict[str, Any]], roles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    computed = topology.derive_node_roles(payload.get("nodes") or [], traversal)
    derived_registered = {
        str(item.get("node_id"))
        for item in ((payload.get("enrichment") or {}).get("findings") or {}).get(
            "derived_boundaries", []
        )
    }
    for node in payload.get("nodes") or []:
        node_id = str(node.get("node_id") or node.get("id"))
        expected = computed[node_id]
        for key in ("boundary_role", "boundary_effective", "in_degree", "out_degree"):
            if node.get(key) != expected.get(key):
                failures.append(
                    _finding(
                        "boundary_role_mismatch",
                        f"{node_id} {key}={node.get(key)!r} ≠ 有向图算出 {expected.get(key)!r}",
                        node_id=node_id,
                    )
                )
        if node.get("boundary_role") in ("entry", "exit", "both") and not bool(node.get("boundary")):
            if node_id not in derived_registered:
                failures.append(
                    _finding(
                        "derived_boundary_unregistered",
                        f"{node_id} 是有向派生边界，但 enrichment.findings.derived_boundaries 没登记",
                        node_id=node_id,
                    )
                )
            if node.get("boundary_near_fence") is False:
                warnings.append(
                    _finding(
                        "derived_boundary_not_near_fence",
                        f"{node_id} 是派生边界，但距锚点 {node.get('boundary_distance_m')} m "
                        "不在登记范围边缘（≥90% 半径）；可能是缺失上游段，请核对（不是 FAIL）",
                        node_id=node_id,
                    )
                )
    details = {
        "roles": {
            role: sorted(node_id for node_id, item in roles.items() if item["boundary_role"] == role)
            for role in ("entry", "exit", "both", "through", "isolated")
            if any(item["boundary_role"] == role for item in roles.values())
        },
        "derived_boundaries": sorted(derived_registered),
    }
    return _result("boundary_roles", failures, warnings, details)


# ============================================================================
# 3) one-way successor（核心 FAIL 规则）
# ============================================================================


def check_oneway_successor(
    payload: dict[str, Any],
    traversal: list[dict[str, Any]],
    roles: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    outgoing, by_id = topology.build_adjacency(traversal)
    checked = 0
    boundary_terminated = 0
    for edge in payload.get("edges") or []:
        direction = str(edge.get("direction"))
        if direction not in ("forward", "reverse"):
            continue
        segment_id = str(edge["segment_id"])
        item = by_id[segment_id]
        checked += 1
        tail = item["to"]
        if roles.get(tail, {}).get("boundary_effective"):
            boundary_terminated += 1
            continue
        successors = [
            candidate
            for candidate in outgoing.get(tail, [])
            if candidate["segment_id"] != segment_id
        ]
        if not successors:
            failures.append(
                _finding(
                    "oneway_tail_without_successor",
                    f"{segment_id}（{direction}）行车末端 {tail} 没有任何可通行后继，且不是边界",
                    segment_id=segment_id,
                    tail_node=tail,
                    direction=direction,
                )
            )
    details = {
        "oneway_segments_checked": checked,
        "boundary_terminated": boundary_terminated,
        "rule": "非边界单向段的行车末端必须有可通行后继（排除自身反向）；边界/派生边界除外",
    }
    return _result("oneway_successor", failures, warnings, details)


# ============================================================================
# 4) bidirectional pairing
# ============================================================================


def check_bidirectional_pairing(payload: dict[str, Any], traversal: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    _, by_id = topology.build_adjacency(traversal)
    bidirectional = 0
    explicit_pairs = 0
    for edge in payload.get("edges") or []:
        segment_id = str(edge["segment_id"])
        direction = str(edge.get("direction"))
        if direction == "bidirectional":
            bidirectional += 1
            forward = by_id.get(segment_id)
            reverse = by_id.get(f"{segment_id}_rev")
            if forward is None or reverse is None:
                failures.append(
                    _finding(
                        "bidirectional_reverse_missing",
                        f"{segment_id} 是双向段，但遍历图缺正向或 _rev 反向",
                        segment_id=segment_id,
                    )
                )
            elif (forward["from"], forward["to"]) != (reverse["to"], reverse["from"]):
                failures.append(
                    _finding(
                        "bidirectional_reverse_endpoints",
                        f"{segment_id} 的 _rev 端点不是正向的反向",
                        segment_id=segment_id,
                    )
                )
        opposite_id = edge.get("opposite_segment_id")
        if opposite_id:
            explicit_pairs += 1
            other = next(
                (item for item in payload.get("edges") or [] if str(item["segment_id"]) == str(opposite_id)),
                None,
            )
            if other is None:
                failures.append(
                    _finding(
                        "opposite_missing",
                        f"{segment_id} opposite_segment_id={opposite_id!r} 不存在",
                        segment_id=segment_id,
                    )
                )
            elif (str(other["from"]), str(other["to"])) != (str(edge["to"]), str(edge["from"])):
                failures.append(
                    _finding(
                        "opposite_endpoints",
                        f"{segment_id} 与 {opposite_id} 端点不互逆",
                        segment_id=segment_id,
                    )
                )
            elif other.get("direction") == direction and direction == "bidirectional":
                warnings.append(
                    _finding(
                        "opposite_both_bidirectional",
                        f"{segment_id} 与 {opposite_id} 都标双向，反向配对语义重复",
                        segment_id=segment_id,
                    )
                )

    # 同起终点、同方向多条 → 可疑重复（只告警）
    seen: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for item in traversal:
        seen[(item["from"], item["to"], item["direction"])].append(item["segment_id"])
    duplicates = {
        key: sorted(set(value)) for key, value in seen.items() if len(set(value)) > 1
    }
    for (_from, _to, _direction), segment_ids in sorted(duplicates.items()):
        warnings.append(
            _finding(
                "duplicate_direction_segments",
                f"{_from}→{_to}（{_direction}）有多个段同时可走：{segment_ids}",
                segment_ids=segment_ids,
            )
        )

    details = {
        "bidirectional_segments": bidirectional,
        "explicit_opposite_directions": explicit_pairs,
        "duplicate_direction_groups": len(duplicates),
    }
    return _result("bidirectional_pairing", failures, warnings, details)


# ============================================================================
# 5) main road gap + 连接候选
# ============================================================================


def check_main_road_gap(
    payload: dict[str, Any],
    traversal: list[dict[str, Any]],
    roles: dict[str, dict[str, Any]],
    candidate_tol_m: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    edges = payload.get("edges") or []
    chains = topology.build_chains(edges)
    by_chain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        chain = chains.get(str(edge["segment_id"]))
        if chain:
            by_chain[str(chain["chain_id"])].append(edge)

    nodes = {
        str(node.get("node_id") or node.get("id")): node for node in payload.get("nodes") or []
    }
    starts = sorted({(item["segment_id"], item["from"], item["name_raw"]) for item in traversal})
    undirected: dict[str, int] = defaultdict(int)
    for edge in edges:
        undirected[str(edge["from"])] += 1
        undirected[str(edge["to"])] += 1

    candidates: list[dict[str, Any]] = []
    gap_count = 0
    terminus_count = 0
    for chain_id in sorted(by_chain):
        members = by_chain[chain_id]
        name = str(members[0].get("name_raw"))
        is_main = str(members[0].get("kind")) == "main"
        local_degree: dict[str, int] = defaultdict(int)
        for edge in members:
            local_degree[str(edge["from"])] += 1
            local_degree[str(edge["to"])] += 1
        endpoints = sorted(node_id for node_id, degree in local_degree.items() if degree == 1)
        if not is_main:
            continue
        for node_id in endpoints:
            role = roles.get(node_id, {})
            if role.get("boundary_effective"):
                continue
            if role.get("boundary_role") == "isolated":
                failures.append(
                    _finding(
                        "main_road_gap",
                        f"主干道链 {chain_id}（{name}）端点 {node_id} 是孤立节点（度数 0）",
                        chain_id=chain_id,
                        node_id=node_id,
                        severity=SEVERITY_FAIL,
                    )
                )
                gap_count += 1
                continue
            if undirected.get(node_id, 0) <= 1:
                failures.append(
                    _finding(
                        "main_road_gap",
                        f"主干道链 {chain_id}（{name}）在内部断头 {node_id}（总度数 {undirected.get(node_id, 0)}）",
                        chain_id=chain_id,
                        node_id=node_id,
                        severity=SEVERITY_FAIL,
                    )
                )
                gap_count += 1
                continue
            # 路口终止：可能是真实终点，也可能是同名主干道没画全 → 待核对告警
            terminus_count += 1
            nearest = _nearest_same_name_start(
                node_id, name, starts, nodes, {str(item["segment_id"]) for item in members}, candidate_tol_m
            )
            warning = _finding(
                "main_road_gap",
                (
                    f"主干道链 {chain_id}（{name}）在路口 {node_id} 终止，未接同名主干道"
                    + (f"；最近同名校验候选 {nearest['segment_id']}（{nearest['distance_m']:.1f} m）" if nearest else "")
                    + "；可能是真实终点或切片/命名截断，待人工核对（不作为 FAIL）"
                ),
                chain_id=chain_id,
                node_id=node_id,
                severity=SEVERITY_WARN,
            )
            if nearest:
                warning["candidate"] = nearest
                candidates.append(
                    {
                        "kind": "main_road_same_name",
                        "chain_id": chain_id,
                        "chain_name": name,
                        "node_id": node_id,
                        "candidate_segment_id": nearest["segment_id"],
                        "candidate_node_id": nearest["node_id"],
                        "distance_m": nearest["distance_m"],
                    }
                )
            warnings.append(warning)

    # 单向段死胡同也给候选（本数据集应为空；换站/坏数据时有用）
    outgoing, by_id = topology.build_adjacency(traversal)
    for edge in edges:
        if edge.get("direction") not in ("forward", "reverse"):
            continue
        segment_id = str(edge["segment_id"])
        item = by_id[segment_id]
        if roles.get(item["to"], {}).get("boundary_effective"):
            continue
        successors = [
            candidate
            for candidate in outgoing.get(item["to"], [])
            if candidate["segment_id"] != segment_id
        ]
        if successors:
            continue
        nearest = _nearest_start(
            item["to"], starts, nodes, {segment_id}, candidate_tol_m
        )
        if nearest:
            candidates.append(
                {
                    "kind": "oneway_dead_end",
                    "segment_id": segment_id,
                    "node_id": item["to"],
                    "candidate_segment_id": nearest["segment_id"],
                    "candidate_node_id": nearest["node_id"],
                    "distance_m": nearest["distance_m"],
                }
            )

    details = {
        "main_chains": sum(
            1 for chain_id in by_chain if str(by_chain[chain_id][0].get("kind")) == "main"
        ),
        "main_road_gaps_fail": gap_count,
        "main_road_terminus_warnings": terminus_count,
        "connection_candidates": len(candidates),
        "rule": (
            "主干道按同名 + 共享节点串链；端点非边界且总度数 1 → FAIL(main_road_gap)；"
            "端点落在路口 → WARN（可能是真实终点/命名截断）+ 最近同名候选；"
            "候选只报告，绝不自动写图"
        ),
    }
    return _result("main_road_gap", failures, warnings, details), candidates


def _nearest_same_name_start(
    node_id: str,
    name: str,
    starts: list[tuple[str, str, str]],
    nodes: dict[str, dict[str, Any]],
    exclude_segments: set[str],
    tol_m: float,
) -> dict[str, Any] | None:
    origin = nodes.get(node_id)
    if not origin or origin.get("lon") is None:
        return None
    best: dict[str, Any] | None = None
    for segment_id, start_node, start_name in starts:
        if segment_id in exclude_segments or start_name != name:
            continue
        candidate = nodes.get(start_node)
        if not candidate or candidate.get("lon") is None:
            continue
        distance = topology.haversine_m(
            float(origin["lon"]), float(origin["lat"]), float(candidate["lon"]), float(candidate["lat"])
        )
        if distance > tol_m:
            continue
        if best is None or (round(distance, 3), segment_id) < (
            round(best["distance_m"], 3),
            best["segment_id"],
        ):
            best = {
                "segment_id": segment_id,
                "node_id": start_node,
                "distance_m": round(distance, 1),
            }
    return best


def _nearest_start(
    node_id: str,
    starts: list[tuple[str, str, str]],
    nodes: dict[str, dict[str, Any]],
    exclude_segments: set[str],
    tol_m: float,
) -> dict[str, Any] | None:
    origin = nodes.get(node_id)
    if not origin or origin.get("lon") is None:
        return None
    best: dict[str, Any] | None = None
    for segment_id, start_node, _name in starts:
        if segment_id in exclude_segments:
            continue
        candidate = nodes.get(start_node)
        if not candidate or candidate.get("lon") is None:
            continue
        distance = topology.haversine_m(
            float(origin["lon"]), float(origin["lat"]), float(candidate["lon"]), float(candidate["lat"])
        )
        if distance > tol_m:
            continue
        if best is None or (round(distance, 3), segment_id) < (
            round(best["distance_m"], 3),
            best["segment_id"],
        ):
            best = {
                "segment_id": segment_id,
                "node_id": start_node,
                "distance_m": round(distance, 1),
            }
    return best


# ============================================================================
# 6) 有向可达性
# ============================================================================


def check_reachability(
    payload: dict[str, Any],
    traversal: list[dict[str, Any]],
    roles: dict[str, dict[str, Any]],
    allow: dict[str, Any],
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    entries, exits = topology.entry_exit_nodes(roles)
    if not entries:
        failures.append(_finding("no_entry", "没有 boundary 入（entry）节点，无法校验可达性"))
    if not exits:
        failures.append(_finding("no_exit", "没有 boundary 出（exit）节点，无法校验可达性"))
    if not entries or not exits:
        return _result("reachability", failures, warnings, {})

    reachable = {entry: topology.reachable_nodes(traversal, entry) for entry in entries}
    reversed_traversal = topology.reverse_traversal(traversal)
    coreachable = {exit_node: topology.reachable_nodes(reversed_traversal, exit_node) for exit_node in exits}
    reachable_union: set[str] = set()
    for nodes in reachable.values():
        reachable_union |= nodes
    coreachable_union: set[str] = set()
    for nodes in coreachable.values():
        coreachable_union |= nodes

    node_ids = [str(node.get("node_id") or node.get("id")) for node in payload.get("nodes") or []]
    allowed_nodes = set(allow.get("nodes") or [])
    allowed_segments = set(allow.get("segments") or [])

    for entry in entries:
        targets = [
            exit_node
            for exit_node in exits
            if exit_node != entry and exit_node in reachable[entry]
        ]
        if not targets:
            failures.append(
                _finding(
                    "entry_without_exit",
                    f"进场边界 {entry} 到任何离场边界都没有完整有向路径",
                    node_id=entry,
                )
            )
    for exit_node in exits:
        sources = [
            entry for entry in entries if entry != exit_node and exit_node in reachable[entry]
        ]
        if not sources:
            failures.append(
                _finding(
                    "exit_unreachable",
                    f"离场边界 {exit_node} 从任何进场边界都不可达",
                    node_id=exit_node,
                )
            )

    unreachable_nodes = [node_id for node_id in node_ids if node_id not in reachable_union]
    not_coreachable_nodes = [node_id for node_id in node_ids if node_id not in coreachable_union]
    for node_id in unreachable_nodes:
        finding = _finding(
            "node_unreachable",
            f"节点 {node_id} 从任何进场边界都不可达",
            node_id=node_id,
        )
        if node_id in allowed_nodes:
            finding["whitelisted"] = allow.get("file")
            warnings.append(finding)
        else:
            failures.append(finding)
    for node_id in not_coreachable_nodes:
        finding = _finding(
            "node_cannot_reach_exit",
            f"节点 {node_id} 到任何离场边界都不可达",
            node_id=node_id,
        )
        if node_id in allowed_nodes:
            finding["whitelisted"] = allow.get("file")
            warnings.append(finding)
        else:
            failures.append(finding)

    uncovered_segments: list[str] = []
    for edge in payload.get("edges") or []:
        segment_id = str(edge["segment_id"])
        covered = any(
            item["segment_id"] == segment_id
            and item["from"] in reachable_union
            and item["to"] in coreachable_union
            for item in traversal
        )
        if not covered:
            uncovered_segments.append(segment_id)
            finding = _finding(
                "segment_unreachable",
                f"段 {segment_id} 不在任何『进场边界 → 离场边界』的有向路径上",
                segment_id=segment_id,
            )
            if segment_id in allowed_segments:
                finding["whitelisted"] = allow.get("file")
                warnings.append(finding)
            else:
                failures.append(finding)

    matrix: list[dict[str, Any]] = []
    reachable_pairs = 0
    _, traversal_by_id = topology.build_adjacency(traversal)
    for entry in entries:
        for exit_node in exits:
            if entry == exit_node:
                continue
            path = topology.find_path(traversal, entry, exit_node, forbid_u_turn=True)
            if path is None:
                matrix.append(
                    {
                        "from_node": entry,
                        "to_node": exit_node,
                        "reachable": False,
                        "edges": None,
                        "segments": None,
                    }
                )
                continue
            reachable_pairs += 1
            matrix.append(
                {
                    "from_node": entry,
                    "to_node": exit_node,
                    "reachable": True,
                    "edges": path,
                    "segments": [traversal_by_id[item]["segment_id"] for item in path],
                }
            )

    unused_allow = sorted((allowed_nodes | allowed_segments) - set(unreachable_nodes) - set(not_coreachable_nodes) - set(uncovered_segments))
    if unused_allow:
        warnings.append(
            _finding(
                "unused_whitelist_entry",
                f"白名单里有条目实际可达/已覆盖：{unused_allow}",
                whitelist=allow.get("file"),
            )
        )

    details = {
        "entries": entries,
        "exits": exits,
        "entry_exit_pairs": len(entries) * len(exits),
        "pairs_compared": len(matrix),
        "pairs_reachable": reachable_pairs,
        "pairs_unreachable": len(matrix) - reachable_pairs,
        "nodes": len(node_ids),
        "nodes_reachable": len(node_ids) - len(unreachable_nodes),
        "nodes_coreachable": len(node_ids) - len(not_coreachable_nodes),
        "segments": len(payload.get("edges") or []),
        "segments_uncovered": uncovered_segments,
        "whitelist": allow.get("file"),
        "whitelisted_nodes": sorted(allowed_nodes),
        "whitelisted_segments": sorted(allowed_segments),
        "rule": (
            "入场 boundary → 离场 boundary 用有向图 + 禁非法掉头算路；"
            "每个入至少 1 个可达出、每个出至少 1 个可达入；"
            "所有节点/段必须在某条『入→出』路径上，否则 FAIL（可列白名单，须给理由）"
        ),
    }
    return _result("reachability", failures, warnings, {**details, "matrix": matrix})


# ============================================================================
# 7) U-turn
# ============================================================================


def check_u_turn(
    payload: dict[str, Any],
    traversal: list[dict[str, Any]],
    *,
    all_pairs: bool,
    reachability_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    _, by_id = topology.build_adjacency(traversal)

    probes = 0
    for edge in payload.get("edges") or []:
        if edge.get("direction") != "bidirectional":
            continue
        segment_id = str(edge["segment_id"])
        reverse_id = f"{segment_id}_rev"
        if segment_id not in by_id or reverse_id not in by_id:
            continue
        probes += 1
        result = topology.validate_path(traversal, [segment_id, reverse_id])
        expected_valid = bool(edge.get("u_turn_allowed"))
        if result["valid"] != expected_valid:
            failures.append(
                _finding(
                    "u_turn_policy_broken",
                    f"{segment_id} u_turn_allowed={expected_valid} 与『正→反』探针结果 "
                    f"{result['valid']} 不一致",
                    segment_id=segment_id,
                )
            )
        elif not expected_valid and not any(
            item["code"] == "illegal_u_turn" for item in result["violations"]
        ):
            failures.append(
                _finding(
                    "u_turn_policy_broken",
                    f"{segment_id} 应判非法掉头但没报 illegal_u_turn",
                    segment_id=segment_id,
                )
            )

    # 真实路线单独由 check_routes 校验（见下），这里只做探针 / 全节点对 / 边界路线。
    # 全节点对自洽（可选，慢但彻底）
    all_pairs_checked = 0
    if all_pairs:
        node_ids = sorted(str(node.get("node_id") or node.get("id")) for node in payload.get("nodes") or [])
        for source in node_ids:
            for target in node_ids:
                if source == target:
                    continue
                path = topology.find_path(traversal, source, target, forbid_u_turn=True)
                if path is None:
                    continue
                all_pairs_checked += 1
                result = topology.validate_path(traversal, path, source=source, target=target)
                if not result["valid"]:
                    failures.append(
                        _finding(
                            "route_invalid_all_pairs",
                            f"{source}→{target} 的算路结果非法：{result['violations'][:3]}",
                            source=source,
                            target=target,
                        )
                    )

    # 进→出矩阵里的路线也校验一遍（这些是真实要跑的路线）
    matrix_checked = 0
    if reachability_result:
        for row in (reachability_result.get("details") or {}).get("matrix") or []:
            if not row.get("reachable") or not row.get("edges"):
                continue
            matrix_checked += 1
            result = topology.validate_path(
                traversal, row["edges"], source=row["from_node"], target=row["to_node"]
            )
            if not result["valid"]:
                failures.append(
                    _finding(
                        "boundary_route_invalid",
                        f"{row['from_node']}→{row['to_node']} 的边界路线非法：{result['violations'][:3]}",
                        from_node=row["from_node"],
                        to_node=row["to_node"],
                    )
                )

    details = {
        "bidirectional_probes": probes,
        "boundary_routes_checked": matrix_checked,
        "all_pairs_checked": all_pairs_checked,
        "rule": (
            "非法掉头 = 同段号、相反方向、且前一条遍历边 u_turn_allowed=false；"
            "u_turn_allowed 只在双向断头端点允许（无 OSM 掉头限制数据）"
        ),
    }
    return _result("u_turn", failures, warnings, details)


def check_routes(
    payload: dict[str, Any],
    traversal: list[dict[str, Any]],
    routes_path: Path,
) -> dict[str, Any]:
    """校验引擎 / 反例路线文件里的每条路线（方向、连续、非法掉头）。"""
    checked, failures = _validate_routes_file(payload, traversal, routes_path)
    warnings: list[dict[str, Any]] = []
    if not checked:
        warnings.append(
            _finding("routes_empty", f"路线文件 {routes_path} 里没有可校验的 edges 路线")
        )
    return _result(
        "routes",
        failures,
        warnings,
        {"file": topology.repo_rel(routes_path), "routes_checked": checked},
    )


def _route_paths(request: dict[str, Any]) -> list[tuple[str, list[str], str | None]]:
    """从一条 request 里摘出所有路线：key, edges, segments 校验用。"""
    found: list[tuple[str, list[str], str | None]] = []
    for key in ("arrival_route", "departure_route", "pickup_route"):
        route = request.get(key)
        if isinstance(route, dict):
            edges = route.get("edges")
            if isinstance(edges, list) and edges:
                found.append((key, [str(item) for item in edges], None))
    for index, route in enumerate(request.get("alternatives") or []):
        if isinstance(route, dict):
            edges = route.get("edges")
            if isinstance(edges, list) and edges:
                found.append((f"alternatives[{index}]", [str(item) for item in edges], None))
    for index, route in enumerate((request.get("capacity_shortage") or {}).get("rejected_candidates") or []):
        if isinstance(route, dict):
            edges = route.get("edges")
            if isinstance(edges, list) and edges:
                found.append((f"rejected_candidates[{index}]", [str(item) for item in edges], None))
    return found


def _validate_routes_file(
    payload: dict[str, Any],
    traversal: list[dict[str, Any]],
    routes_path: Path,
) -> tuple[int, list[dict[str, Any]]]:
    if not routes_path.is_file():
        raise SystemExit(f"缺路线文件:{routes_path}")
    data = topology.read_json(routes_path)
    requests = data.get("requests")
    if not isinstance(requests, list):
        # 反例夹具也接受 {"routes": [{"edges": [...]}]} 形状
        routes = data.get("routes")
        if isinstance(routes, list):
            requests = [{"request_id": f"CE-{index}", "arrival_route": route} for index, route in enumerate(routes)]
        else:
            requests = []
    failures: list[dict[str, Any]] = []
    checked = 0
    _, by_id = topology.build_adjacency(traversal)
    for request in requests:
        request_id = str(request.get("request_id") or request.get("od_id") or "?")
        for key, edges, _segments in _route_paths(request):
            checked += 1
            result = topology.validate_path(traversal, edges)
            for violation in result["violations"]:
                failures.append(
                    _finding(
                        "illegal_u_turn"
                        if violation["code"] == "illegal_u_turn"
                        else "route_invalid",
                        f"{request_id} 的 {key} 路线非法：{violation['detail']}",
                        request_id=request_id,
                        route=key,
                        violation=violation["code"],
                    )
                )
            for edge_id in edges:
                item = by_id.get(edge_id)
                if item is None:
                    failures.append(
                        _finding(
                            "route_edge_not_found",
                            f"{request_id} 的 {key} 路线引用不存在的遍历边 {edge_id}",
                            request_id=request_id,
                            route=key,
                        )
                    )
    return checked, failures


# ============================================================================
# 主流程
# ============================================================================


def run_checks(
    payload: dict[str, Any],
    *,
    graph_path: Path | None,
    raw_path: Path | None,
    routes_path: Path | None,
    allow: dict[str, Any],
    all_pairs: bool,
    candidate_tol_m: float,
    check_freshness: bool = True,
) -> dict[str, Any]:
    traversal = topology.build_traversal(payload)
    # 校验一律用**从遍历图重算**的角色，不信任 enriched 里可能过期的 boundary_role；
    # 存储值与重算值是否一致由 boundary_roles 检查单独判。
    roles = topology.derive_node_roles(payload.get("nodes") or [], traversal)

    checks: dict[str, Any] = {}
    checks["schema"] = check_schema(payload, traversal)
    if check_freshness:
        checks["schema"] = _with_freshness(checks["schema"], payload, raw_path)
    checks["boundary_roles"] = check_boundary_roles(payload, traversal, roles)
    checks["oneway_successor"] = check_oneway_successor(payload, traversal, roles)
    checks["bidirectional_pairing"] = check_bidirectional_pairing(payload, traversal)
    main_result, candidates = check_main_road_gap(payload, traversal, roles, candidate_tol_m)
    checks["main_road_gap"] = main_result
    checks["reachability"] = check_reachability(payload, traversal, roles, allow)
    checks["u_turn"] = check_u_turn(
        payload,
        traversal,
        all_pairs=all_pairs,
        reachability_result=checks["reachability"],
    )
    if routes_path is not None:
        checks["routes"] = check_routes(payload, traversal, routes_path)

    failures = 0
    warnings = 0
    findings: list[dict[str, Any]] = []
    for name in CHECK_ORDER:
        result = checks.get(name)
        if not result:
            continue
        failures += int(result["failure_count"])
        warnings += int(result["warning_count"])
        for item in result["failures"]:
            findings.append({**item, "check": name, "severity": SEVERITY_FAIL})
        for item in result["warnings"]:
            findings.append({**item, "check": name, "severity": SEVERITY_WARN})

    summary = {
        "segments": len(payload.get("edges") or []),
        "nodes": len(payload.get("nodes") or []),
        "entries": len((checks["reachability"].get("details") or {}).get("entries") or []),
        "exits": len((checks["reachability"].get("details") or {}).get("exits") or []),
        "checks": len([name for name in CHECK_ORDER if name in checks]),
        "failures": failures,
        "warnings": warnings,
        "passed": failures == 0,
        "exit_code": 0 if failures == 0 else 1,
    }
    return {
        "schema_version": "1.0",
        "is_simulated": True,
        "generated_by": "work/twin/netpack/tools/check_topology.py",
        "note": (
            "自动拓扑校验报告（Issue IKNB9H）：全部判据可机器复现，不靠人工看图。"
            "main_road_gap 的路口终止是 WARN（真实终点/切片截断待核对）；"
            "单向段无后继、可达性缺失、非法掉头才是 FAIL。"
        ),
        "inputs": {
            "graph": topology.repo_rel(graph_path) if graph_path else None,
            "graph_sha256": topology.sha256_file(graph_path) if graph_path and graph_path.is_file() else None,
            "raw": topology.repo_rel(raw_path) if raw_path else None,
            "raw_sha256": topology.sha256_file(raw_path) if raw_path and raw_path.is_file() else None,
            "routes": topology.repo_rel(routes_path) if routes_path else None,
            "graph_source": (payload.get("enrichment") or {}).get("source_file"),
            "graph_source_sha256": (payload.get("enrichment") or {}).get("source_sha256"),
        },
        "summary": summary,
        "checks": checks,
        "findings": findings,
        "connection_candidates": candidates,
    }


def _with_freshness(result: dict[str, Any], payload: dict[str, Any], raw_path: Path | None) -> dict[str, Any]:
    """把 enriched 与原始产物的 sha 对账，防止拿旧 enriched 掩盖拓扑变化。"""
    enrichment = payload.get("enrichment") or {}
    if not enrichment:
        result["failures"].append(
            _finding("not_enriched", "图没有 enrichment 块：先跑 work/twin/netpack/topology.py")
        )
        result["passed"] = False
        result["failure_count"] = len(result["failures"])
        return result
    source_file = enrichment.get("source_file")
    recorded = enrichment.get("source_sha256")
    if not source_file or not recorded:
        result["failures"].append(
            _finding("enrichment_no_source", "enrichment 缺 source_file / source_sha256，无法追溯")
        )
    else:
        candidate = Path(source_file)
        if not candidate.is_absolute():
            candidate = topology.REPO_ROOT / candidate
        if not candidate.is_file():
            result["failures"].append(
                _finding("enrichment_source_missing", f"enrichment 记录的原始产物不存在：{source_file}")
            )
        else:
            actual = topology.sha256_file(candidate)
            if actual != recorded:
                result["failures"].append(
                    _finding(
                        "stale_enriched",
                        f"enriched 已过期：原始产物 sha={actual[:12]}… ≠ 记录 {str(recorded)[:12]}…；"
                        "先重跑 topology.py",
                    )
                )
    if raw_path is not None and raw_path.is_file() and source_file:
        if Path(source_file).name != raw_path.name:
            result["failures"].append(
                _finding(
                    "enrichment_source_mismatch",
                    f"enrichment 记录的源文件 {source_file} ≠ 本次 --raw {topology.repo_rel(raw_path)}",
                )
            )
    result["passed"] = not result["failures"]
    result["failure_count"] = len(result["failures"])
    return result


def write_report(report: dict[str, Any], output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(topology.json_text(report), encoding="utf-8", newline="\n")
    return output.stat().st_size


def print_summary(report: dict[str, Any], output: Path) -> None:
    summary = report["summary"]
    print(
        f"拓扑校验：{summary['segments']} 段 / {summary['nodes']} 节点 · "
        f"入 {summary['entries']} / 出 {summary['exits']} · "
        f"FAIL {summary['failures']} / WARN {summary['warnings']}"
    )
    for name in CHECK_ORDER:
        result = report["checks"].get(name)
        if not result:
            continue
        mark = "✅" if result["passed"] else "❌"
        print(
            f"  {mark} {name}: FAIL {result['failure_count']} / WARN {result['warning_count']}"
        )
    print(f"→ {topology.repo_rel(output)}")
    for finding in report["findings"]:
        if finding["severity"] == SEVERITY_FAIL:
            print(f"  ❌ [{finding['check']}] {finding['message']}")


# ============================================================================
# 自检：正常 PASS + 人为断头 FAIL + 非法掉头 FAIL
# ============================================================================


def _mutate_broken_chain(payload: dict[str, Any], segment_id: str = "SZ-010") -> dict[str, Any]:
    """人为断头：把一条单向段改成反向，使其上游段末端失去后继。"""
    mutated = copy.deepcopy(payload)
    target = next(
        (edge for edge in mutated.get("edges") or [] if str(edge["segment_id"]) == segment_id),
        None,
    )
    if target is None:
        raise SystemExit(f"反例构造失败：找不到 {segment_id}")
    target["direction"] = "reverse"
    # 车道随方向翻转，避免 schema 先因车道不一致失败（要验的是 successor 规则）
    target["lanes_forward"], target["lanes_backward"] = (
        target.get("lanes_backward", 0),
        target.get("lanes_forward", 0),
    )
    target["field_sources"]["lanes_forward"] = "derived"
    target["field_sources"]["lanes_backward"] = "osm" if target.get("lanes_total") else "default"
    return mutated


def run_self_test(args: argparse.Namespace) -> int:
    enriched_path, raw_path = default_paths(args.site_id, args.config)
    payload = load_graph(enriched_path)
    allow, _ = load_allow_unreachable(args.allow_unreachable)
    results: list[dict[str, Any]] = []
    failures: list[str] = []

    # 1) 正常图必须 PASS
    normal = run_checks(
        payload,
        graph_path=enriched_path,
        raw_path=raw_path,
        routes_path=None,
        allow=allow,
        all_pairs=False,
        candidate_tol_m=args.candidate_tol_m,
        check_freshness=True,
    )
    results.append({"case": "z_network_normal", "expect": "pass", "summary": normal["summary"]})
    if not normal["summary"]["passed"]:
        failures.append("正常图未通过：" + str([item["message"] for item in normal["findings"] if item["severity"] == "fail"][:3]))

    # 2) 人为断头必须 FAIL（且命中 oneway_successor）
    broken = _mutate_broken_chain(payload)
    broken_report = run_checks(
        broken,
        graph_path=None,
        raw_path=None,
        routes_path=None,
        allow=allow,
        all_pairs=False,
        candidate_tol_m=args.candidate_tol_m,
        check_freshness=False,
    )
    codes = {
        item["code"]
        for item in broken_report["findings"]
        if item["severity"] == "fail"
    }
    results.append(
        {
            "case": "counterexample_broken_chain",
            "expect": "fail",
            "passed_as_expected": not broken_report["summary"]["passed"],
            "failure_codes": sorted(codes),
            "summary": broken_report["summary"],
        }
    )
    if broken_report["summary"]["passed"]:
        failures.append("人为断头反例没有 FAIL")
    if "oneway_tail_without_successor" not in codes:
        failures.append("人为断头反例没有命中 oneway_tail_without_successor")

    # 3) 非法掉头路线必须 FAIL
    with tempfile.TemporaryDirectory(prefix="iknb9h-uturn-") as scratch:
        fixture = Path(scratch) / "counterexample_uturn.json"
        fixture.write_text(
            topology.json_text(
                {
                    "is_simulated": True,
                    "requests": [
                        {
                            "request_id": "CE-UTURN-001",
                            "arrival_route": {
                                "path_id": "CE-U1",
                                "edges": ["SZ-021", "SZ-021_rev"],
                                "segments": ["SZ-021", "SZ-021"],
                            },
                        }
                    ],
                    "note": "反例：SZ-021 u_turn_allowed=false，正→反是非法掉头；check_topology 必须 FAIL",
                }
            ),
            encoding="utf-8",
        )
        uturn_report = run_checks(
            payload,
            graph_path=enriched_path,
            raw_path=raw_path,
            routes_path=fixture,
            allow=allow,
            all_pairs=False,
            candidate_tol_m=args.candidate_tol_m,
            check_freshness=True,
        )
    codes = {
        item["code"]
        for item in uturn_report["findings"]
        if item["severity"] == "fail"
    }
    results.append(
        {
            "case": "counterexample_illegal_u_turn",
            "expect": "fail",
            "passed_as_expected": not uturn_report["summary"]["passed"],
            "failure_codes": sorted(codes),
            "summary": uturn_report["summary"],
        }
    )
    if uturn_report["summary"]["passed"]:
        failures.append("非法掉头反例没有 FAIL")
    if "illegal_u_turn" not in codes:
        failures.append("非法掉头反例没有命中 illegal_u_turn")

    verdict = {
        "schema_version": "1.0",
        "is_simulated": True,
        "generated_by": "work/twin/netpack/tools/check_topology.py --self-test",
        "input": topology.repo_rel(enriched_path),
        "cases": results,
        "failures": failures,
        "passed": not failures,
    }
    if args.self_test_out:
        output = Path(args.self_test_out)
        write_report(verdict, output)
        print(f"→ {topology.repo_rel(output)}")
    for case in results:
        expected_pass = case["expect"] == "pass"
        ok = case["summary"]["passed"] if expected_pass else bool(case.get("passed_as_expected"))
        mark = "✅" if ok else "❌"
        print(f"  {mark} {case['case']}（期望 {case['expect']}）")
    if failures:
        for item in failures:
            print(f"  ❌ {item}")
        return 1
    print("✅ 自检通过：正常图 PASS；人为断头 / 非法掉头两个反例都按预期 FAIL")
    return 0


# ============================================================================
# CLI
# ============================================================================


def main(argv: list[str] | None = None) -> int:
    # Windows 控制台默认 GBK 编不了 ✅/❌；本进程显式改 UTF-8（不改仓库文件编码）。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(
        description=(
            "自动拓扑校验（Issue IKNB9H）：方向/车道 schema、单向贯通、双向配对、"
            "主干道截断、有向可达性、非法掉头；失败 non-zero 并写 topology_report.json"
        )
    )
    parser.add_argument("--site-id", default=None, help="站点登记表里的 site_id（缺省 default_site）")
    parser.add_argument("--config", default=None, help="站点范围登记表路径（可省略）")
    parser.add_argument("--graph", default=None, help="enriched 图路径（缺省取登记表对应 .enriched.json）")
    parser.add_argument("--raw", default=None, help="原始路网 JSON（用于 sha 对账；缺省随站点推导）")
    parser.add_argument(
        "--out",
        default=None,
        help=(
            f"报告输出路径（缺省：enriched 图同目录的 {DEFAULT_REPORT_NAME}；"
            "Z 站 = work/twin/netpack/，GZ 站 = work/twin/netpack/guangzhounan/）"
        ),
    )
    parser.add_argument("--routes", default=None, help="引擎 routes.json（校验路线方向/非法掉头）")
    parser.add_argument("--allow-unreachable", default=None, help="不可达白名单 JSON（nodes/segments/reason）")
    parser.add_argument("--candidate-tol-m", type=float, default=topology.CANDIDATE_TOL_M)
    parser.add_argument("--all-pairs", action="store_true", help="全节点对算路自洽（慢）")
    parser.add_argument("--self-test", action="store_true", help="跑反例自检：正常 PASS / 断头 FAIL / 非法掉头 FAIL")
    parser.add_argument("--self-test-out", default=None, help="反例自检结果 JSON（可选）")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    config = args.config or None
    if args.self_test:
        return run_self_test(args)

    if args.graph:
        graph_path = Path(args.graph)
        raw_path = Path(args.raw) if args.raw else None
    else:
        graph_path, raw_path = default_paths(args.site_id, config)
    if args.out:
        output = Path(args.out)
    else:
        # 按站放报告（IKNC4J）：默认 = enriched 同目录，Z/ GZ 各一份、互不覆盖
        output = graph_path.parent / DEFAULT_REPORT_NAME
    allow, _ = load_allow_unreachable(args.allow_unreachable)
    payload = load_graph(graph_path)
    report = run_checks(
        payload,
        graph_path=graph_path,
        raw_path=raw_path,
        routes_path=Path(args.routes) if args.routes else None,
        allow=allow,
        all_pairs=args.all_pairs,
        candidate_tol_m=args.candidate_tol_m,
        check_freshness=bool(args.graph is None or args.raw),
    )
    write_report(report, output)
    if not args.quiet:
        print_summary(report, output)
    return int(report["summary"]["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
