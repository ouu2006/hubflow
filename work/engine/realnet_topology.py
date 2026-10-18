#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真网方向/车道/U-turn 拓扑助手（Issue IKNB9H）：给 `realnet.py` / `run.py` 消费 enriched 图。

## 分层

- **数据层**：`work/twin/netpack/topology.py` 生成 `network_junction.enriched.json`，
  每个段带 `direction` / 车道三件套 / `u_turn_allowed` / `continuity` / `field_sources`；
- **引擎层**（本文件）：把"一个段"展开成"可通行遍历边"——双向段展开正向 + `_rev`，
  单向段只展开一个方向；路线校验与 `legs`（方向/车道）也在这里，保证
  `run.py` 与 `routes.json` 不把单向段当双向、不在禁止处掉头。

## 为什么单独一个模块

`realnet.py` 已经很大（统一图 / OD / segments 映射），把"方向展开 + 路线校验"
放这里，`--sample` 路径完全不经本文件（样例网没有 direction，仍走旧逻辑逐字节不变）。

## 口径

1. 段号命名空间不变：正向边 id = `SZ-###`，反向遍历边 id = `SZ-###_rev`，
   `section` 始终是 `SZ-###`（`run.py` 的 `_segments_of()` / 接口层只认 section）；
2. **单向段不展开反向**；双向段两个方向都展开；`oneway=-1` 的段只展开 `to→from`；
3. U-turn：同一 section、方向相反的两条遍历边连续出现 = 原地掉头；只有
   `u_turn_allowed=true` 才放行（`candidates.dijkstra` 用边状态图执行）；
4. 缺 enriched 时**不静默瞎猜**：direction 按 oneway + 显式反向对推导，标
   `topology_source=derived_from_raw`，并在引擎 meta 里留痕；有 enriched 时以它为准。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ENRICHED_SUFFIX = ".enriched.json"

TOPOLOGY_ENRICHED = "enriched"
TOPOLOGY_DERIVED = "derived_from_raw"

ONEWAY_FORWARD = {"yes", "true", "1"}
ONEWAY_REVERSE = {"-1", "reverse"}
ONEWAY_BIDIRECTIONAL = {"no", "false", "0"}


def enriched_path(raw_path: Path | str) -> Path:
    path = Path(raw_path)
    return path.with_name(path.stem + ENRICHED_SUFFIX)


def normalise_oneway(value: Any) -> tuple[str, str]:
    """`oneway` → (direction, source)。缺失按 OSM 缺省双向（source=default）。"""
    text = "" if value is None else str(value).strip().lower()
    if text in ONEWAY_FORWARD:
        return "forward", "osm"
    if text in ONEWAY_REVERSE:
        return "reverse", "osm"
    if text in ONEWAY_BIDIRECTIONAL:
        return "bidirectional", "osm"
    return "bidirectional", "default"


def parse_lanes(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value) if value > 0 else None
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def derive_opposites(edges: list[dict[str, Any]]) -> dict[str, str]:
    """端点完全互逆的显式段号配对（与 netpack/topology.py 同规则）。"""
    by_endpoints: dict[tuple[str, str], list[str]] = {}
    for edge in edges:
        key = (str(edge["from"]), str(edge["to"]))
        by_endpoints.setdefault(key, []).append(str(edge.get("segment_id") or edge.get("id")))
    pairs: dict[str, str] = {}
    for edge in edges:
        segment_id = str(edge.get("segment_id") or edge.get("id"))
        candidates = sorted(
            item
            for item in by_endpoints.get((str(edge["to"]), str(edge["from"])), [])
            if item != segment_id
        )
        if candidates:
            pairs[segment_id] = candidates[0]
    return pairs


def base_topology(
    edge: dict[str, Any],
    *,
    opposites: dict[str, str],
    undirected_degree: dict[str, int],
    enriched: bool,
) -> dict[str, Any]:
    """取一个段的拓扑字段：enriched 直接读；raw 按同一套规则现推（标 derived_from_raw）。"""
    segment_id = str(edge.get("segment_id") or edge.get("id"))
    if enriched and edge.get("direction") in ("forward", "reverse", "bidirectional"):
        return {
            "direction": str(edge["direction"]),
            "lanes_forward": edge.get("lanes_forward"),
            "lanes_backward": edge.get("lanes_backward"),
            "lanes_total": edge.get("lanes_total"),
            "opposite_segment_id": edge.get("opposite_segment_id"),
            "u_turn_allowed": bool(edge.get("u_turn_allowed")),
            "left_turn_allowed": bool(edge.get("left_turn_allowed")),
            "left_turn_allowed_reverse": edge.get("left_turn_allowed_reverse"),
            "continuity": edge.get("continuity"),
            "field_sources": edge.get("field_sources"),
            "topology_source": TOPOLOGY_ENRICHED,
        }

    direction, oneway_source = normalise_oneway(edge.get("oneway"))
    if oneway_source == "default" and segment_id in opposites:
        # OSM 未标 oneway，但有端点互逆的独立段号 → 对向单行（与 SUMONET 补边口径一致）
        direction = "forward"
        oneway_source = "derived"
    lanes_total = parse_lanes(edge.get("lanes"))
    lanes_forward: int | None
    lanes_backward: int | None
    if direction == "forward":
        lanes_forward, lanes_backward = lanes_total, 0
    elif direction == "reverse":
        lanes_forward, lanes_backward = 0, lanes_total
    else:
        lanes_forward, lanes_backward = None, None
    u_turn_allowed = bool(
        direction == "bidirectional"
        and (
            undirected_degree.get(str(edge["from"]), 0) == 1
            or undirected_degree.get(str(edge["to"]), 0) == 1
        )
    )
    return {
        "direction": direction,
        "lanes_forward": lanes_forward,
        "lanes_backward": lanes_backward,
        "lanes_total": lanes_total,
        "opposite_segment_id": opposites.get(segment_id),
        "u_turn_allowed": u_turn_allowed,
        "left_turn_allowed": False,
        "left_turn_allowed_reverse": None,
        "continuity": {
            "head_connected": None,
            "tail_connected": None,
            "chain_id": None,
            "is_main_road": str(edge.get("kind") or "") == "main",
            "gap_to_next_m": None,
            "source": "derived_from_raw（未生成 enriched 图，贯通性字段不参与算路）",
        },
        "field_sources": {
            "direction": oneway_source,
            "lanes_forward": "osm" if lanes_total is not None and direction != "bidirectional" else "default",
            "lanes_backward": "derived" if direction in ("forward", "reverse") else "default",
            "lanes_total": "osm" if lanes_total is not None else "default",
            "opposite_segment_id": "derived",
            "u_turn_allowed": "derived",
            "left_turn_allowed": "default",
            "left_turn_allowed_reverse": "default",
            "continuity.head_connected": "default",
            "continuity.tail_connected": "default",
            "continuity.chain_id": "default",
            "continuity.is_main_road": "derived",
            "continuity.gap_to_next_m": "default",
        },
        "topology_source": TOPOLOGY_DERIVED,
    }


def traversal_specs(edge: dict[str, Any], topology: dict[str, Any]) -> list[dict[str, Any]]:
    """把一个段展开成 1~2 条遍历边规格（真实边由 realnet 补速度/容量）。"""
    segment_id = str(edge["segment_id"])
    direction = str(topology["direction"])
    specs: list[dict[str, Any]] = []
    if direction in ("forward", "bidirectional"):
        specs.append(
            {
                "edge_id": segment_id,
                "direction": "forward",
                "from": str(edge["from"]),
                "to": str(edge["to"]),
                "lanes": topology.get("lanes_forward"),
                "left_turn_allowed": bool(topology.get("left_turn_allowed")),
            }
        )
    if direction == "bidirectional":
        specs.append(
            {
                "edge_id": f"{segment_id}_rev",
                "direction": "reverse",
                "from": str(edge["to"]),
                "to": str(edge["from"]),
                "lanes": topology.get("lanes_backward"),
                "left_turn_allowed": bool(
                    topology.get("left_turn_allowed_reverse")
                    if topology.get("left_turn_allowed_reverse") is not None
                    else topology.get("left_turn_allowed")
                ),
            }
        )
    elif direction == "reverse":
        specs.append(
            {
                "edge_id": segment_id,
                "direction": "reverse",
                "from": str(edge["to"]),
                "to": str(edge["from"]),
                "lanes": topology.get("lanes_backward"),
                "left_turn_allowed": bool(topology.get("left_turn_allowed")),
            }
        )
    return specs


def derive_roles(
    nodes: list[dict[str, Any]],
    traversal: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """按遍历边有向出入度派生边界角色（非边界出度 0 → dead_end，不当边界放行）。"""
    incoming: dict[str, int] = {}
    outgoing: dict[str, int] = {}
    for item in traversal:
        outgoing[item["from"]] = outgoing.get(item["from"], 0) + 1
        incoming[item["to"]] = incoming.get(item["to"], 0) + 1
    roles: dict[str, dict[str, Any]] = {}
    for node in nodes:
        node_id = str(node.get("node_id") or node.get("id"))
        in_deg = int(incoming.get(node_id, 0))
        out_deg = int(outgoing.get(node_id, 0))
        raw_boundary = bool(node.get("boundary"))
        if in_deg == 0 and out_deg == 0:
            role, source = "isolated", "derived:无任何可通行边"
        elif in_deg == 0:
            role = "entry"
            source = (
                "raw_boundary+directed:入度 0"
                if raw_boundary
                else "derived:directed_in_degree_zero（无向度数判据漏掉多出边的边界节点）"
            )
        elif out_deg == 0:
            if raw_boundary:
                role, source = "exit", "raw_boundary+directed:出度 0"
            else:
                role, source = "dead_end", "derived:non_boundary_out_degree_zero（非边界断头）"
        elif raw_boundary:
            role, source = "both", "raw_boundary+directed:进出都有（双向边界段）"
        else:
            role, source = "through", "derived:内部节点（进出都有）"
        roles[node_id] = {
            "in_degree": in_deg,
            "out_degree": out_deg,
            "boundary": raw_boundary,
            "boundary_effective": role in ("entry", "exit", "both"),
            "boundary_role": role,
            "boundary_role_source": source,
        }
    return roles


def route_legs(graph: Any, path: list[str]) -> list[dict[str, Any]]:
    """把边 id 序列折成方向/车道 legs（front-end 路线卡可区分正/反向/双向）。"""
    legs: list[dict[str, Any]] = []
    for edge_id in path:
        edge = graph.edge(str(edge_id))
        legs.append(
            {
                "edge_id": str(edge_id),
                "segment_id": str(edge.get("section")),
                "direction": edge.get("direction"),
                "from_node": str(edge["from"]),
                "to_node": str(edge["to"]),
                "lanes": edge.get("lanes"),
                "lanes_forward": edge.get("lanes_forward"),
                "lanes_backward": edge.get("lanes_backward"),
                "lanes_total": edge.get("lanes_total"),
                "u_turn_allowed": bool(edge.get("u_turn_allowed")),
                "left_turn_allowed": bool(edge.get("left_turn_allowed")),
            }
        )
    return legs


def validate_route(graph: Any, path: list[str]) -> list[dict[str, Any]]:
    """校验一条边 id 路线：连续、边存在、不非法掉头。"""
    violations: list[dict[str, Any]] = []
    for index, edge_id in enumerate(path):
        edge_id = str(edge_id)
        try:
            edge = graph.edge(edge_id)
        except KeyError:
            violations.append({"code": "edge_not_found", "edge_id": edge_id})
            continue
        if index == 0:
            continue
        previous_id = str(path[index - 1])
        try:
            previous = graph.edge(previous_id)
        except KeyError:
            continue
        if str(previous["to"]) != str(edge["from"]):
            violations.append(
                {
                    "code": "path_not_contiguous",
                    "detail": f"{previous_id} 终点 {previous['to']} ≠ {edge_id} 起点 {edge['from']}",
                }
            )
        if (
            str(previous.get("section")) == str(edge.get("section"))
            and previous.get("direction") != edge.get("direction")
            and not bool(previous.get("u_turn_allowed"))
        ):
            violations.append(
                {
                    "code": "illegal_u_turn",
                    "detail": (
                        f"在 {previous['to']} 从 {previous_id} 原地掉头到 {edge_id}，"
                        "该段 u_turn_allowed=false"
                    ),
                }
            )
    return violations


def attach_route_topology(requests: list[dict[str, Any]], graph: Any) -> int:
    """给真网响应的每条路线补 `legs`（方向/车道），并硬校验路线合法性。

    - 只处理带 `edges` 的路线；`segments` 与 legs 的 section 必须一致；
    - 出现非法掉头 / 断链直接 `SystemExit`：宁可报错，不输出错路线；
    - 返回补齐的路线条数（日志用）。
    """
    enriched = 0
    for request in requests:
        request_id = str(request.get("request_id") or request.get("od_id") or "?")
        routes: list[tuple[str, dict[str, Any]]] = []
        for key in ("arrival_route", "departure_route", "pickup_route"):
            route = request.get(key)
            if isinstance(route, dict):
                routes.append((key, route))
        for index, route in enumerate(request.get("alternatives") or []):
            if isinstance(route, dict):
                routes.append((f"alternatives[{index}]", route))
        for index, route in enumerate(
            (request.get("capacity_shortage") or {}).get("rejected_candidates") or []
        ):
            if isinstance(route, dict):
                routes.append((f"rejected_candidates[{index}]", route))
        for key, route in routes:
            edges = route.get("edges")
            if not isinstance(edges, list) or not edges:
                continue
            path = [str(item) for item in edges]
            violations = validate_route(graph, path)
            if violations:
                detail = "；".join(item.get("detail") or item["code"] for item in violations[:3])
                raise SystemExit(
                    f"真网路线非法（{request_id} 的 {key}）：{detail} —— 拒绝输出方向/掉头错误的响应"
                )
            legs = route_legs(graph, path)
            segments = [leg["segment_id"] for leg in legs]
            if isinstance(route.get("segments"), list) and [
                str(item) for item in route["segments"]
            ] != segments:
                raise SystemExit(
                    f"真网路线段号与遍历边不一致（{request_id} 的 {key}）："
                    f"segments={route['segments']} / legs={segments}"
                )
            route["segments"] = segments
            route["legs"] = legs
            route["direction_counts"] = {
                "forward": sum(1 for leg in legs if leg["direction"] == "forward"),
                "reverse": sum(1 for leg in legs if leg["direction"] == "reverse"),
            }
            enriched += 1
    return enriched


def read_json(path: Path | str) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fp:
        return json.load(fp)
