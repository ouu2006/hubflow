#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真网全 OD / 可达性批量检查（Issue IKNB9H）：任意两个可达节点/段能算完整路径，或如实 unreachable。

## 做什么

1. 用 `realnet.load_network_payload` 读**同一份 enriched 图**（引擎 `--network real` 用的那份）；
2. 用 `candidates.dijkstra`（`forbid_u_turn=true` 的边状态图）算：
   - 全部 **boundary 入场 → 离场** 对（9×8，去掉同一个节点）：完整路径 + 方向 legs + 长度；
   - 全部 **节点对**（44×43）：只记可达性与边数（`--include-all-paths` 才存全路径）；
   - 每个段的**双向覆盖**：正向/反向是否在"入场→离场"有向路径上；
   - 每个节点从任意入场是否可达、到任意离场是否可达；
3. 每条算出的路线都用 `realnet_topology.validate_route` 复核（连续/边存在/无非法掉头），
   任何一条非法 → non-zero；
4. 报告写 `work/engine/route_matrix.json`，**不读系统时钟、不用随机数**，同一输入两遍逐字节一致。

## 单点即时算路

```bash
# 节点 → 节点
python work/engine/topology_check.py --from N-001 --to N-005

# 段 → 段（段号取该段的行车起点/终点；双向段默认取正向）
python work/engine/topology_check.py --from SZ-003 --to SZ-010
```

输出 JSON（`reachable=false` 时 `edges` 为 null，如实说不可达）。

## 退出码

0 = 检查通过；1 = 有非法路线 / 段没覆盖 / 边界对缺失；2 = 参数错误。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import candidates
import network
import realnet
import realnet_topology

#: 本文件位于 work/engine/ → 仓库根是 parents[1]
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
DEFAULT_REPORT = HERE / "route_matrix.json"


def build_dataset(site_id: str | None) -> dict[str, Any]:
    """读站点真网 + 站点包参数，建统一图（与 run.py --network real 同一条装载链）。"""
    site = realnet.load_site(site_id)
    payload, topology_meta = realnet.load_network_payload(site)
    thresholds = network.load_thresholds(REPO_ROOT / "stations" / "thresholds.json")
    graph_payload, net_meta = realnet.normalize_network(payload, site, thresholds["grading"])
    net_meta.update(topology_meta)
    graph = network.Graph(graph_payload)
    return {
        "site": site,
        "payload": payload,
        "topology_meta": topology_meta,
        "net_meta": net_meta,
        "graph": graph,
        "graph_payload": graph_payload,
        "params": thresholds["decision"],
    }


def _segments_of(graph: network.Graph, path: list[str]) -> list[str]:
    return [str(graph.edge(edge_id)["section"]) for edge_id in path]


def _directions_of(graph: network.Graph, path: list[str]) -> list[str]:
    return [str(graph.edge(edge_id).get("direction")) for edge_id in path]


def segment_endpoints(graph: network.Graph, segment_id: str) -> tuple[str, str]:
    edges = [
        edge_id
        for edge_id in sorted(graph._edges)  # noqa: SLF001
        if str(graph.edge(edge_id).get("section")) == segment_id
    ]
    forward = [eid for eid in edges if graph.edge(eid).get("direction") == "forward"]
    edge = graph.edge(forward[0] if forward else edges[0])
    return str(edge["from"]), str(edge["to"])


def compute_pair(graph: network.Graph, source: str, target: str) -> dict[str, Any]:
    weight = network.make_weight_fn(graph, {}, {})
    forbid_u_turn = bool(graph.attributes.get("forbid_u_turn"))
    path = candidates.dijkstra(
        graph, source, target, weight, forbid_u_turn=forbid_u_turn
    )
    if path is None:
        return {
            "from_node": source,
            "to_node": target,
            "reachable": False,
            "edges": None,
            "segments": None,
            "directions": None,
            "length_m": None,
            "violations": [],
        }
    violations = realnet_topology.validate_route(graph, path)
    return {
        "from_node": source,
        "to_node": target,
        "reachable": True,
        "edges": path,
        "segments": _segments_of(graph, path),
        "directions": _directions_of(graph, path),
        "length_m": round(network.path_length_m(graph, path), 1),
        "violations": violations,
    }


def compute_reachability(graph: network.Graph, entries: list[str], exits: list[str]) -> dict[str, Any]:
    """节点级可达/共可达集合（用 candidates.dijkstra 的有向图，禁非法掉头）。"""
    nodes = sorted(graph.node_ids)
    weight = network.make_weight_fn(graph, {}, {})
    forbid_u_turn = bool(graph.attributes.get("forbid_u_turn"))

    reachable: dict[str, set[str]] = {}
    for entry in entries:
        seen = {entry}
        for node_id in nodes:
            if node_id == entry:
                continue
            path = candidates.dijkstra(
                graph, entry, node_id, weight, forbid_u_turn=forbid_u_turn
            )
            if path is not None:
                seen.add(node_id)
        reachable[entry] = seen

    coreachable: dict[str, set[str]] = {}
    for exit_node in exits:
        seen = {exit_node}
        for node_id in nodes:
            if node_id == exit_node:
                continue
            path = candidates.dijkstra(
                graph, node_id, exit_node, weight, forbid_u_turn=forbid_u_turn
            )
            if path is not None:
                seen.add(node_id)
        coreachable[exit_node] = seen

    reachable_union: set[str] = set()
    for nodes_set in reachable.values():
        reachable_union |= nodes_set
    coreachable_union: set[str] = set()
    for nodes_set in coreachable.values():
        coreachable_union |= nodes_set
    return {
        "from_entries": reachable,
        "to_exits": coreachable,
        "nodes_reachable": sorted(reachable_union),
        "nodes_coreachable": sorted(coreachable_union),
    }


def segment_coverage(
    graph: network.Graph,
    reachable_union: set[str],
    coreachable_union: set[str],
) -> list[dict[str, Any]]:
    """每个段的正/反向遍历边是否落在"可达起点 → 可到出口"上。"""
    by_section: dict[str, list[dict[str, Any]]] = {}
    for edge_id in sorted(graph._edges):  # noqa: SLF001
        edge = graph.edge(edge_id)
        by_section.setdefault(str(edge["section"]), []).append(edge)
    result: list[dict[str, Any]] = []
    for section in sorted(by_section):
        directions: list[str] = []
        covered_directions: list[str] = []
        for edge in by_section[section]:
            directions.append(str(edge.get("direction")))
            if str(edge["from"]) in reachable_union and str(edge["to"]) in coreachable_union:
                covered_directions.append(str(edge.get("direction")))
        result.append(
            {
                "segment_id": section,
                "directions": sorted(set(directions)),
                "covered_directions": sorted(set(covered_directions)),
                "covered": bool(covered_directions),
            }
        )
    return result


def build_report(dataset: dict[str, Any], include_all_paths: bool = False) -> dict[str, Any]:
    graph = dataset["graph"]
    net_meta = dataset["net_meta"]
    entries = list(net_meta.get("entries") or [])
    exits = list(net_meta.get("exits") or [])
    nodes = sorted(graph.node_ids)

    # 1) 边界 OD（完整路径）
    boundary_od: list[dict[str, Any]] = []
    for source in entries:
        for target in exits:
            if source == target:
                continue
            boundary_od.append(compute_pair(graph, source, target))

    # 2) 全节点对（默认只留可达性 + 边数；--include-all-paths 才留全路径）
    node_pairs: list[dict[str, Any]] = []
    unreachable_pairs: list[dict[str, Any]] = []
    invalid_paths: list[dict[str, Any]] = []
    for source in nodes:
        for target in nodes:
            if source == target:
                continue
            pair = compute_pair(graph, source, target)
            if pair["violations"]:
                invalid_paths.append(pair)
            if not pair["reachable"]:
                unreachable_pairs.append(
                    {"from_node": source, "to_node": target, "reason": "unreachable（有向图 + 禁非法掉头）"}
                )
                node_pairs.append({"from_node": source, "to_node": target, "reachable": False})
            elif include_all_paths:
                node_pairs.append(pair)
            else:
                node_pairs.append(
                    {
                        "from_node": source,
                        "to_node": target,
                        "reachable": True,
                        "edge_count": len(pair["edges"] or []),
                    }
                )

    # 3) 节点/段覆盖
    reachability = compute_reachability(graph, entries, exits)
    reachable_union = set(reachability["nodes_reachable"])
    coreachable_union = set(reachability["nodes_coreachable"])
    coverage = segment_coverage(graph, reachable_union, coreachable_union)
    uncovered_segments = [item["segment_id"] for item in coverage if not item["covered"]]
    unreachable_nodes = [node_id for node_id in nodes if node_id not in reachable_union]
    not_coreachable_nodes = [node_id for node_id in nodes if node_id not in coreachable_union]

    # 4) 边界出入口完整性（每个入至少 1 个出、每个出至少 1 个入）
    entry_without_exit = [
        entry
        for entry in entries
        if not any(
            row["reachable"] and row["from_node"] == entry and row["to_node"] != entry
            for row in boundary_od
        )
    ]
    exit_without_entry = [
        exit_node
        for exit_node in exits
        if not any(
            row["reachable"] and row["to_node"] == exit_node and row["from_node"] != exit_node
            for row in boundary_od
        )
    ]

    failures: list[dict[str, Any]] = []
    for path in invalid_paths:
        failures.append(
            {
                "code": "invalid_route",
                "message": f"{path['from_node']}→{path['to_node']} 算出的路线非法：{path['violations'][:3]}",
            }
        )
    for entry in entry_without_exit:
        failures.append(
            {"code": "entry_without_exit", "message": f"进场边界 {entry} 到任何离场边界都不可达"}
        )
    for exit_node in exit_without_entry:
        failures.append(
            {"code": "exit_without_entry", "message": f"离场边界 {exit_node} 从任何进场边界都不可达"}
        )
    for node_id in unreachable_nodes:
        failures.append({"code": "node_unreachable", "message": f"节点 {node_id} 从任何进场边界不可达"})
    for node_id in not_coreachable_nodes:
        failures.append(
            {"code": "node_cannot_reach_exit", "message": f"节点 {node_id} 到任何离场边界不可达"}
        )
    for segment_id in uncovered_segments:
        failures.append(
            {"code": "segment_uncovered", "message": f"段 {segment_id} 不在任何『入→出』有向路径上"}
        )

    pairs_reachable = sum(1 for item in node_pairs if item["reachable"])
    boundary_reachable = sum(1 for item in boundary_od if item["reachable"])
    summary = {
        "nodes": len(nodes),
        "segments": len(coverage),
        "graph_edges": len(graph._edges),  # noqa: SLF001
        "entries": entries,
        "exits": exits,
        "boundary_od_pairs": len(boundary_od),
        "boundary_od_reachable": boundary_reachable,
        "boundary_od_unreachable": len(boundary_od) - boundary_reachable,
        "node_pairs": len(node_pairs),
        "node_pairs_reachable": pairs_reachable,
        "node_pairs_unreachable": len(node_pairs) - pairs_reachable,
        "segments_covered": len(coverage) - len(uncovered_segments),
        "segments_uncovered": uncovered_segments,
        "invalid_routes": len(invalid_paths),
        "failures": len(failures),
        "passed": not failures,
        "exit_code": 0 if not failures else 1,
        "unreachable_node_pairs": len(unreachable_pairs),
    }
    return {
        "schema_version": "1.0",
        "is_simulated": True,
        "generated_by": "work/engine/topology_check.py",
        "note": (
            "全路网有向可达性 / 全 OD 批量检查（Issue IKNB9H）："
            "用与 --network real 同一份 enriched 图 + 同一套 U-turn 约束算路；"
            "不可达的节点对如实列出（单向/边界方向决定的合法不可达），"
            "但每个边界入/出、每个节点、每个段必须有完整有向路径覆盖。"
        ),
        "inputs": {
            "site_id": net_meta.get("site_id"),
            "site_name": net_meta.get("site_name"),
            "topology_source": net_meta.get("topology_source"),
            "topology_file": net_meta.get("topology_file"),
            "enriched_source_sha256": net_meta.get("enriched_source_sha256"),
            "directions": net_meta.get("directions"),
            "u_turn_allowed_segments": net_meta.get("u_turn_allowed_segments"),
            "boundary_source": net_meta.get("boundary_source"),
        },
        "summary": summary,
        "failures": failures,
        "boundary_od": boundary_od,
        "node_pairs": node_pairs,
        "unreachable_node_pairs": unreachable_pairs,
        "segment_coverage": coverage,
        "reachability": {
            "nodes_reachable": reachability["nodes_reachable"],
            "nodes_coreachable": reachability["nodes_coreachable"],
            "unreachable_nodes": unreachable_nodes,
            "not_coreachable_nodes": not_coreachable_nodes,
        },
    }


def write_report(report: dict[str, Any], output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    output.write_text(text, encoding="utf-8", newline="\n")
    return output.stat().st_size


def print_summary(report: dict[str, Any], output: Path) -> None:
    summary = report["summary"]
    print(
        f"全 OD/可达性：{summary['nodes']} 节点 / {summary['segments']} 段 · "
        f"边界对 {summary['boundary_od_reachable']}/{summary['boundary_od_pairs']} 可达 · "
        f"节点对 {summary['node_pairs_reachable']}/{summary['node_pairs']} 可达 · "
        f"FAIL {summary['failures']}"
    )
    print(
        f"  段覆盖 {summary['segments_covered']}/{summary['segments']} · "
        f"非法路线 {summary['invalid_routes']} · "
        f"有向不可达节点对 {summary['unreachable_node_pairs']}（如实列出，不是错）"
    )
    print(f"→ {topology_rel(output)}")
    for failure in report["failures"][:10]:
        print(f"  ❌ [{failure['code']}] {failure['message']}")


def topology_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def run_single(dataset: dict[str, Any], source_arg: str, target_arg: str) -> int:
    graph = dataset["graph"]
    source_type = "node"
    target_type = "node"
    source = source_arg
    target = target_arg
    if source not in graph.node_ids:
        source_type = "segment"
        source, _ = segment_endpoints(graph, source)
    if target not in graph.node_ids:
        target_type = "segment"
        _, target = segment_endpoints(graph, target)
    result = compute_pair(graph, source, target)
    result["requested"] = {
        "from": {"value": source_arg, "type": source_type, "node_id": source},
        "to": {"value": target_arg, "type": target_type, "node_id": target},
    }
    result["is_simulated"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["reachable"] else 3


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(
        description=(
            "真网全 OD / 可达性批量检查（Issue IKNB9H）：任意节点/段能算完整有向路径，"
            "或如实 unreachable；报告写 work/engine/route_matrix.json"
        )
    )
    parser.add_argument("--site-id", default=None, help="站点登记表 site_id（缺省 default_site）")
    parser.add_argument("--from", dest="source", default=None, help="单点算路起点（节点 id 或段号）")
    parser.add_argument("--to", dest="target", default=None, help="单点算路终点（节点 id 或段号）")
    parser.add_argument("--json-out", default=None, help=f"报告路径（缺省 {topology_rel(DEFAULT_REPORT)}）")
    parser.add_argument("--include-all-paths", action="store_true", help="节点对也存完整路径（报告更大）")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    if bool(args.source) != bool(args.target):
        print("❌ --from 与 --to 必须同时给")
        return 2

    dataset = build_dataset(args.site_id)
    if args.source and args.target:
        return run_single(dataset, args.source, args.target)

    report = build_report(dataset, include_all_paths=args.include_all_paths)
    output = Path(args.json_out) if args.json_out else DEFAULT_REPORT
    write_report(report, output)
    if not args.quiet:
        print_summary(report, output)
    return int(report["summary"]["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
