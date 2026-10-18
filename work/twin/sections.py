#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真网断面角色候选推导（Issue IKMS19）：`network_junction.json` → 61 段 boundary / internal 候选。

**一句话**：同化只能灌边界断面，所以先得有一份**从真网拓扑自动推导**的断面角色清单；
本模块只做这件事——**不写死段号、不写死坐标、不写死站点名**，换站只换登记表。

## 推导规则（与生产方、引擎口径一致）

1. 数据源：`work/twin/site-ranges.json` 的站点记录 → `out_json` 指向的真网产物
   （本站 = `work/twin/netpack/network_junction.json`，61 段 / 44 节点）；段数与登记表
   `seg_target` 对不上直接报错（不在不完整路网上定断面）；
2. **boundary 节点**：`nodes[].boundary == true`。生产脚本 `build_junction_pack.py` 的标记口径是
   **无向度数 = 1**；标记缺失时退化为"度数 1"并在产物里写明来源（与 `work/engine/realnet.py` 同口径）；
3. **boundary 断面** = 边两端**任一节点是 boundary 节点**（车从围栏外进来的那条边）；
   **internal 断面** = 两端都是内部节点。这正是生产方 `edges[].boundary` 的写法，
   本模块用**节点列表重新推一遍**并对账生产方的 `edges[].boundary`，不一致就记进 `mismatches`；
4. 每条断面写 **role + 依据**（哪个端点是 boundary 节点 / 两端度数多少），并补
   `flow_direction`（inbound / outbound / bidirectional，仅对 boundary 有意义，供人工裁定时参考）；
5. **本清单是候选**：`status` 固定「候选·待业主/队长签字冻结」。**签字冻结前不得宣称 M1-10 通过**；
   **硬规则：internal 永远不许挂 calibrator / 回灌**（契约 §三 / §6.1，TC-20 第②项）。

## 与已有产物的关系

| 产物 | 关系 |
|---|---|
| `work/twin/netpack/network_junction.json` | **本模块唯一数据源**（几何/拓扑真值，OSM 切片）；本模块只读 |
| `work/engine/realnet.py` | 引擎侧同口径的边界推导（OD 用），两边都按 `nodes[].boundary` / 度数 1，**互不 import** |
| 站点包 `stationZ.ts` 的 `sections` | IKM4TE 的 **mock 候选**（5 boundary / 6 internal，含"站前/停车场内部"的语义判断）；与本拓扑口径的差异见 `work/twin/README.md` 第十二节，**签字时逐条裁定** |
| `stations/points.json` | 7 节点样例网占位件（`SEG-###` / `E-###`），**不是本站真网**；真网断面不读它（不混命名空间） |

用法（由 `run_assimilation.py` 调用，也可单独跑）：
    python work/twin/sections.py            # 只推导并打印候选计数（不写盘）
    python work/twin/sections.py --write    # 写 work/twin/out/latest/sections_candidate.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import site_config

#: 本文件位于 work/twin/ → 仓库根是 parents[1]
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]

#: 断面角色（契约 §6.1，取值封闭）
SECTION_ROLES = ("boundary", "internal")

#: 候选状态固定文案（Issue IKMS19：「拿不到签字就先用候选清单并全程标候选·待冻结」）
STATUS_CANDIDATE = "候选·待业主/队长签字冻结"

#: 硬规则文案（写进产物，给验收和代码硬校验看）
HARD_RULE = (
    "internal 断面一律不允许挂 calibrator / 回灌（契约 §三 / §6.1，TC-20 第②项）；"
    "boundary 断面才允许回灌"
)

#: 角色依据的两种来源
ROLE_SOURCE_NODE_FLAG = "nodes[].boundary（生产脚本按无向度数 1 标记）"
ROLE_SOURCE_DEGREE_FALLBACK = "fallback:nodes[].boundary 缺失，按无向度数 1 推"


def read_json(path: Path) -> dict[str, Any]:
    """读一个 UTF-8 JSON 文件（显式编码，换机器不乱码）。"""
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def repo_rel(path: Path) -> str:
    """尽量给仓库相对路径（日志/产物可追溯）；不在仓库内则给绝对路径。"""
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def load_site_network(
    site_id: str | None = None,
    site_ranges_path: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    """按站点范围登记表定位真网产物：返回 `(site, network_payload, network_path)`。

    站点名 / 段号前缀 / 段数 / 产物路径**全部来自登记表**，本模块不写死任何站名或坐标。
    """
    site = site_config.load_site(site_id, site_ranges_path)
    network_path = site_config.repo_path(str(site["out_json"]))
    if not network_path.is_file():
        raise SystemExit(
            f"缺真网产物：{network_path}（先按 netpack/README.md 跑 build_junction_pack.py）"
        )
    return site, read_json(network_path), network_path


def _validate_network(payload: dict[str, Any], site: dict[str, Any], network_path: Path) -> None:
    """校验真网产物的最低结构（缺字段/自相矛盾一律报错，不静默补）。"""
    if not isinstance(payload, dict):
        raise SystemExit(f"真网产物 {network_path} 顶层不是对象")
    nodes = payload.get("nodes")
    edges = payload.get("edges")
    if not isinstance(nodes, list) or not nodes:
        raise SystemExit(f"真网产物 {network_path} 缺非空 nodes 数组")
    if not isinstance(edges, list) or not edges:
        raise SystemExit(f"真网产物 {network_path} 缺非空 edges 数组")
    stats = payload.get("stats") or {}
    if int(stats.get("nodes") or len(nodes)) != len(nodes):
        raise SystemExit(
            f"真网产物自相矛盾：stats.nodes={stats.get('nodes')} 但 nodes[]={len(nodes)}"
        )
    if int(stats.get("segments") or len(edges)) != len(edges):
        raise SystemExit(
            f"真网产物自相矛盾：stats.segments={stats.get('segments')} 但 edges[]={len(edges)}"
        )
    seg_target = int(site["seg_target"])
    if len(edges) != seg_target:
        raise SystemExit(
            f"真网段数 {len(edges)} ≠ 登记表 seg_target={seg_target}"
            f"（{site.get('site_id')}）：缺边/多边一律报错，不在不完整路网上定断面"
        )


def _node_map(nodes: list[dict[str, Any]], network_path: Path) -> dict[str, dict[str, Any]]:
    """节点 id → 节点记录；id 重复 / 缺 id 一律报错。"""
    mapped: dict[str, dict[str, Any]] = {}
    for node in nodes:
        node_id = node.get("node_id") or node.get("id")
        if not node_id:
            raise SystemExit(f"真网产物 {network_path} 的 nodes[] 里有节点缺 node_id / id")
        node_id = str(node_id)
        if node_id in mapped:
            raise SystemExit(f"真网产物 {network_path} 的 nodes[] 节点 id 重复：{node_id}")
        mapped[node_id] = node
    return mapped


def _undirected_degree(node_id: str, edges: list[dict[str, Any]]) -> int:
    """无向度数（nodes[].degree 缺失时的退化口径）。"""
    return sum(
        1 for edge in edges if str(edge.get("from")) == node_id or str(edge.get("to")) == node_id
    )


def derive_boundary_nodes(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> tuple[list[str], str]:
    """推 boundary 节点：优先 `nodes[].boundary`，标记缺失时退化为无向度数 1。"""
    flagged = sorted(str(node.get("node_id") or node.get("id")) for node in nodes if node.get("boundary"))
    if flagged:
        return flagged, ROLE_SOURCE_NODE_FLAG
    fallback = sorted(
        str(node.get("node_id") or node.get("id"))
        for node in nodes
        if _undirected_degree(str(node.get("node_id") or node.get("id")), edges) == 1
    )
    if not fallback:
        raise SystemExit("真网里找不到边界节点（nodes[].boundary 缺失且无度数 1 节点）：无法定断面")
    return fallback, ROLE_SOURCE_DEGREE_FALLBACK


def _flow_direction(from_boundary: bool, to_boundary: bool, oneway: Any) -> str:
    """边界断面的车流方向（仅供人工裁定时参考，不参与 role 判定）。"""
    if from_boundary and to_boundary:
        return "boundary_boundary"
    if oneway is None:  # 双向边：进出都可能
        return "bidirectional"
    return "inbound" if from_boundary else "outbound"


def derive_sections(
    payload: dict[str, Any], site: dict[str, Any], network_path: str | Path | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """真网产物 → 61 条断面角色候选（`sections` 列表 + `meta`）。

    纯函数（不写盘、不读系统时钟）：输入相同，输出逐字段相同。
    """
    raw_path = Path(network_path) if network_path else Path(str(site["out_json"]))
    _validate_network(payload, site, raw_path)
    nodes = payload["nodes"]
    edges = payload["edges"]
    node_map = _node_map(nodes, raw_path)
    boundary_nodes, role_source = derive_boundary_nodes(nodes, edges)
    boundary_set = set(boundary_nodes)
    if not boundary_set:
        raise SystemExit("boundary 节点为空：无法推导 boundary 断面（不硬凑）")

    sections: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for edge in edges:
        segment_id = str(edge.get("segment_id") or edge.get("id") or "")
        if not segment_id:
            raise SystemExit(f"真网产物 {raw_path} 的 edges[] 里有边缺 segment_id / id")
        if segment_id in seen:
            raise SystemExit(f"真网产物 {raw_path} 的 edges[] 段号重复：{segment_id}")
        seen.add(segment_id)
        from_node = str(edge.get("from"))
        to_node = str(edge.get("to"))
        for node_id in (from_node, to_node):
            if node_id not in node_map:
                raise SystemExit(f"边 {segment_id} 引用了不存在的节点 {node_id}（拓扑不完整）")
        from_boundary = from_node in boundary_set
        to_boundary = to_node in boundary_set
        role = "boundary" if (from_boundary or to_boundary) else "internal"
        from_degree = node_map[from_node].get("degree")
        to_degree = node_map[to_node].get("degree")
        if from_degree is None:
            from_degree = _undirected_degree(from_node, edges)
        if to_degree is None:
            to_degree = _undirected_degree(to_node, edges)
        if role == "boundary":
            endpoints = []
            if from_boundary:
                endpoints.append(f"{from_node}（度数 {from_degree}）")
            if to_boundary:
                endpoints.append(f"{to_node}（度数 {to_degree}）")
            basis = "边界节点作为端点：" + "、".join(endpoints)
        else:
            basis = (
                f"两端点均为内部节点（{from_node} 度数 {from_degree} / "
                f"{to_node} 度数 {to_degree}）"
            )
        # 与生产方标记对账（不一致不改 role，只留痕：role 以节点清单推导为准）
        producer_flag = bool(edge.get("boundary"))
        if producer_flag != (role == "boundary"):
            mismatches.append(
                {
                    "segment_id": segment_id,
                    "derived_role": role,
                    "producer_boundary_flag": producer_flag,
                    "basis": basis,
                }
            )
        sections.append(
            {
                "segment_id": segment_id,
                "role": role,
                "name": edge.get("name"),
                "from_node": from_node,
                "to_node": to_node,
                "from_degree": int(from_degree),
                "to_degree": int(to_degree),
                "from_boundary": from_boundary,
                "to_boundary": to_boundary,
                "producer_boundary_flag": producer_flag,
                "flow_direction": (
                    _flow_direction(from_boundary, to_boundary, edge.get("oneway"))
                    if role == "boundary"
                    else None
                ),
                "basis": basis,
                "length_m": edge.get("length_m"),
                "lanes": edge.get("lanes"),
                "oneway": edge.get("oneway"),
                "speed_limit": edge.get("speed_limit"),
                "capacity_vph": edge.get("capacity_vph"),
                "kind": edge.get("kind"),
            }
        )

    sections.sort(key=lambda item: item["segment_id"])
    boundary_ids = [item["segment_id"] for item in sections if item["role"] == "boundary"]
    internal_ids = [item["segment_id"] for item in sections if item["role"] == "internal"]
    direction_counts: dict[str, int] = {}
    for item in sections:
        if item["role"] == "boundary":
            direction_counts[item["flow_direction"]] = (
                direction_counts.get(item["flow_direction"], 0) + 1
            )
    meta = {
        "role_source": role_source,
        "boundary_node_ids": boundary_nodes,
        "boundary_node_count": len(boundary_nodes),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "boundary_count": len(boundary_ids),
        "internal_count": len(internal_ids),
        "boundary_direction_counts": dict(sorted(direction_counts.items())),
        "boundary_segment_ids": boundary_ids,
        "internal_segment_ids": internal_ids,
        "producer_mismatches": mismatches,
        "producer_flag_consistent": not mismatches,
    }
    return sections, meta


def build_candidate_payload(
    site: dict[str, Any],
    payload: dict[str, Any],
    network_path: str | Path,
    ts: str,
) -> dict[str, Any]:
    """组装 `sections_candidate.json` 的完整内容（候选状态 + 每段 role/依据 + 统计）。"""
    sections, meta = derive_sections(payload, site, network_path)
    return {
        "ts": ts,
        "is_simulated": True,
        "site_id": str(site["site_id"]),
        "site_name": site.get("site_name"),
        "network_file": repo_rel(Path(network_path)),
        "network_source": payload.get("source"),
        "crs": payload.get("crs"),
        "seg_prefix": str(site["seg_prefix"]),
        "seg_target": int(site["seg_target"]),
        "status": STATUS_CANDIDATE,
        "role_source": meta["role_source"],
        "rule": (
            "boundary 断面 = 边两端任一节点为 nodes[].boundary=true 的边界节点；"
            "其余为 internal；不写死段号 / 坐标 / 站名（换站只改 site-ranges.json）"
        ),
        "hard_rule": HARD_RULE,
        "counts": {
            "total": meta["edge_count"],
            "boundary": meta["boundary_count"],
            "internal": meta["internal_count"],
            "boundary_direction_counts": meta["boundary_direction_counts"],
        },
        "boundary_nodes": [str(node) for node in meta["boundary_node_ids"]],
        "boundary_segment_ids": meta["boundary_segment_ids"],
        "internal_segment_ids": meta["internal_segment_ids"],
        "producer_flag_consistent": meta["producer_flag_consistent"],
        "producer_mismatches": meta["producer_mismatches"],
        "sections": sections,
        "note": (
            "断面角色候选（演示数据（模拟））：由真网产物 nodes[].boundary 自动推导，"
            "未写死段号/坐标；**未经业主/队长签字冻结**，不得据此宣称 M1-10 通过。"
            "与站点包 mock 候选（IKM4TE：5 boundary / 6 internal，含「站前/停车场内部」语义判断）"
            "存在差异（拓扑口径边界段多于 mock 边界段），逐条差异见 work/twin/README.md 第十二节；"
            "签字时需逐条裁定（语义围栏 vs 拓扑边界）。"
        ),
    }


def load_sections_candidate(
    site_id: str | None = None,
    site_ranges_path: str | Path | None = None,
    ts: str = "",
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    """一步到位：登记表 → 真网 → 候选清单（返回 payload / site / network_path）。"""
    site, network, network_path = load_site_network(site_id, site_ranges_path)
    return build_candidate_payload(site, network, network_path, ts), site, network_path


def role_map(sections_payload: dict[str, Any]) -> dict[str, str]:
    """段号 → role（供同化/因素模块按清单判定，避免各处重解析）。"""
    return {item["segment_id"]: item["role"] for item in sections_payload["sections"]}


def segment_ids(sections_payload: dict[str, Any]) -> list[str]:
    """全部段号（按清单顺序，已排序）。"""
    return [item["segment_id"] for item in sections_payload["sections"]]


def boundary_segment_ids(sections_payload: dict[str, Any]) -> list[str]:
    """boundary 候选段号（唯一允许回灌的集合）。"""
    return [
        item["segment_id"] for item in sections_payload["sections"] if item["role"] == "boundary"
    ]


def internal_segment_ids(sections_payload: dict[str, Any]) -> list[str]:
    """internal 段号（**永远不许回灌**）。"""
    return [
        item["segment_id"] for item in sections_payload["sections"] if item["role"] == "internal"
    ]


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="真网断面角色候选推导（Issue IKMS19）")
    parser.add_argument("--site-id", default="", help="站点 id（缺省用登记表 default_site）")
    parser.add_argument("--ts", default="2026-10-18T08:00:00+08:00", help="产物时间戳（不读系统时钟）")
    parser.add_argument("--write", action="store_true", help="写 out/latest/sections_candidate.json")
    parser.add_argument("--out", default=str(HERE / "out" / "latest"), help="输出目录")
    ns = parser.parse_args(argv)
    payload, _site, _network_path = load_sections_candidate(ns.site_id or None, ts=ns.ts)
    counts = payload["counts"]
    print(
        f"断面候选：{counts['total']} 段（boundary {counts['boundary']} / "
        f"internal {counts['internal']}）· 状态：{payload['status']}"
    )
    print(f"boundary 段：{'、'.join(payload['boundary_segment_ids'])}")
    if not payload["producer_flag_consistent"]:
        print(f"⚠️ 生产方 edges[].boundary 与本推导有 {len(payload['producer_mismatches'])} 处不一致（已留痕）")
    if ns.write:
        out_path = Path(ns.out) / "sections_candidate.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"已写：{out_path}（{out_path.stat().st_size} B）")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
