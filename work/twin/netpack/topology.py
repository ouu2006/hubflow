#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路段方向 / 车道 / 贯通性 schema 的后处理（Issue IKNB9H）。

## 为什么单独一个模块（不改 `build_junction_pack.py`）

`network_junction.json` 由 `build_junction_pack.py`（IKMERX）产出，当前正被
IKNB9F（多站）同时改。本模块只做**后处理**：读原产物 → 补方向/车道/贯通字段 →
另写 `network_junction.enriched.json`，**不覆盖原文件、不改构建脚本**，从而与
多站单零冲突。换站只换 `--input/--output`（或站点范围登记表里的记录）。

## 补什么（每个 edge 至少这些字段）

| 字段 | 取值 / 来源 |
|---|---|
| `direction` | `forward`（`oneway=yes`）/ `reverse`（`oneway=-1`）/ `bidirectional`（`oneway=no` 或**未标注**；未标注按 OSM 缺省双向，标 `default`） |
| `lanes_forward` / `lanes_backward` / `lanes_total` | 只认 OSM 已抽到的 `lanes`（总数）；单向段：前向=总数、后向=0；双向段：**不拆分**（OSM 切片没有 `lanes:forward/backward`），前/后向留 `null` —— **不编真实车道数** |
| `opposite_segment_id` | 端点完全互逆的独立段号（双向配对）；没有就 `null`；双向单几何段的反向通行用 `_rev` 语义，不虚构配对 |
| `u_turn_allowed` | 规则推导：仅**双向段 + 端点是无向度数 1 的断头**才允许原地掉头；单向段一律 false（OSM 切片无掉头限制数据） |
| `left_turn_allowed` / `left_turn_allowed_reverse` | 按转向角几何推导（左转 = 有向角 ∈ [-150°, -30°]）；没有坐标就是 false + `default` |
| `continuity` | `head_connected` / `tail_connected` / `chain_id` / `chain_name` / `is_main_road` / `gap_to_next_m` / 最近候选节点 |
| `field_sources` | 每个字段的来源：`osm` / `derived` / `default`（值只有这三种） |

## 边界判定：无向度数 1 会漏（本单发现的真实问题）

原产物用**无向度数 1** 标 `nodes[].boundary`。肇庆东的 `N-006`（鼎湖大道南向起点 +
连接匝道，两条边都朝外）无向度数 2 → 没被标成边界，但有向**入度为 0**，实际是
"车从围栏外进来"的进场边界。只按原 boundary 判可达性会把 `SZ-014` / `SZ-059`
误判为不可达。本模块按**有向出入度**派生 `nodes[].boundary_role`：

- `entry`：入度 0、出度 >0（含原 boundary 进场节点 + 派生边界 N-006）；
- `exit`：出度 0、入度 >0；
- `both`：原 boundary 且进出都有（双向边界段）；
- `through`：内部节点（进出都有）。

派生边界单独标 `boundary_role_source=derived:directed_in_degree_zero`，**不改原文件**，
并在 `enrichment.findings` 里留痕，供人工核对。

## 用法

```bash
# 默认站（站点范围登记表 default_site）：读 out_json，写同名 .enriched.json
python work/twin/netpack/topology.py

# 只校验：把 enrich 结果与既有 enriched 文件逐字节比对（不写盘，不一致非 0 退出）
python work/twin/netpack/topology.py --check

# 换站 / 换文件
python work/twin/netpack/topology.py --site-id <site_id>
python work/twin/netpack/topology.py --input <raw.json> --output <enriched.json>
```

**不读系统时钟、不用随机数**：同一输入两遍输出逐字节一致（M1-1）。
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

#: 本文件位于 work/twin/netpack/ → 仓库根是 parents[2]
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
DEFAULT_SITE_RANGES = REPO_ROOT / "work" / "twin" / "site-ranges.json"

#: enriched 产物后缀（原文件保持不变）
ENRICHED_SUFFIX = ".enriched.json"

#: schema 版本；字段口径变化时递增，并在 README 记一条
SCHEMA_VERSION = "1.0"

#: 字段来源只允许这三种取值（Issue 明确要求）
FIELD_SOURCES = ("osm", "derived", "default")

#: `oneway` 取值归类（OSM tag）
ONEWAY_FORWARD = {"yes", "true", "1"}
ONEWAY_REVERSE = {"-1", "reverse"}
ONEWAY_BIDIRECTIONAL = {"no", "false", "0"}

#: 每个 edge 必须带的方向/车道/贯通字段（缺一个就 schema FAIL）
EDGE_TOPOLOGY_FIELDS = (
    "direction",
    "lanes_forward",
    "lanes_backward",
    "lanes_total",
    "opposite_segment_id",
    "u_turn_allowed",
    "left_turn_allowed",
    "continuity",
    "field_sources",
)

#: `continuity` 必须带的子字段
CONTINUITY_FIELDS = (
    "head_connected",
    "tail_connected",
    "chain_id",
    "is_main_road",
    "gap_to_next_m",
)

#: 左转判定角度（有向角，正 = 右转；-150°~-30° 视为左转）
LEFT_TURN_MIN_DEG = -150.0
LEFT_TURN_MAX_DEG = -30.0

#: "最近候选连接"的搜索上限（米）。只进报告，**绝不自动写图**
CANDIDATE_TOL_M = 200.0

#: 地球平均半径（米），与 sumonet.py 局部投影口径一致
EARTH_RADIUS_M = 6371008.8


# ============================================================================
# 基础 I/O / 地理
# ============================================================================


def read_json(path: Path | str) -> dict[str, Any]:
    """读 UTF-8 JSON（显式编码，换机器不乱码）。"""
    with Path(path).open("r", encoding="utf-8") as fp:
        return json.load(fp)


def json_text(payload: dict[str, Any]) -> str:
    """统一序列化：中文不转义、缩进 2、LF 结尾（与仓库其它产物一致）。"""
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def write_json(path: Path | str, payload: dict[str, Any]) -> int:
    """写 UTF-8 JSON（LF），返回字节数。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json_text(payload)
    target.write_text(text, encoding="utf-8", newline="\n")
    return len(text.encode("utf-8"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | str) -> str:
    return sha256_bytes(Path(path).read_bytes())


def repo_rel(path: Path | str) -> str:
    """尽量给仓库相对路径（日志可追溯）；不在仓库内则给绝对路径。"""
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(Path(path))


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """两点 WGS-84 球面距离（米）。"""
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = p2 - p1
    dlam = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_M * math.asin(math.sqrt(max(0.0, min(1.0, a))))


def bearing_deg(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """起点 → 终点的方位角（0°=正北，90°=正东）。"""
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dl = math.radians(float(lon2) - float(lon1))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(y, x)) % 360.0


def signed_turn_deg(in_bearing: float, out_bearing: float) -> float:
    """有向转向角 ∈ (-180°, 180°]；正 = 右转，负 = 左转。"""
    return (float(out_bearing) - float(in_bearing) + 540.0) % 360.0 - 180.0


# ============================================================================
# 站点范围登记表
# ============================================================================


def load_site_ranges(config_path: Path | str | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else DEFAULT_SITE_RANGES
    if not path.is_file():
        raise SystemExit(f"缺站点范围登记表:{path}")
    return read_json(path)


def pick_site(
    site_id: str | None = None,
    config_path: Path | str | None = None,
) -> dict[str, Any]:
    """按 site_id 取一条站点记录；缺省 default_site。"""
    payload = load_site_ranges(config_path)
    sites = payload.get("sites") or []
    if not sites:
        raise SystemExit("站点范围登记表缺 sites 数组")
    wanted = str(site_id or payload.get("default_site") or sites[0].get("site_id"))
    for site in sites:
        if str(site.get("site_id")) == wanted:
            return dict(site)
    known = "、".join(str(site.get("site_id")) for site in sites)
    raise SystemExit(f"站点登记表没有 site_id={wanted!r}（现有：{known}）")


def raw_network_path(site: dict[str, Any]) -> Path:
    raw = site.get("out_json")
    if not raw:
        raise SystemExit(f"站点 {site.get('site_id')} 缺 out_json")
    return (REPO_ROOT / str(raw)).resolve()


def enriched_path_for(raw_path: Path | str) -> Path:
    """`network_junction.json` → `network_junction.enriched.json`。"""
    path = Path(raw_path)
    return path.with_name(path.stem + ENRICHED_SUFFIX)


# ============================================================================
# 字段推导
# ============================================================================


def normalise_oneway(value: Any) -> tuple[str, str, str]:
    """`oneway` → `(direction, source, note)`。

    - 明确 yes / -1 / no → source = osm；
    - null / 空 / 未知值 → 按 OSM 缺省**双向**理解，source = default（不编成单向）。
    """
    text = "" if value is None else str(value).strip().lower()
    if text in ONEWAY_FORWARD:
        return "forward", "osm", f"OSM oneway={value!r} → 正向单行"
    if text in ONEWAY_REVERSE:
        return "reverse", "osm", f"OSM oneway={value!r} → 反向单行（几何 from/to 与行车方向相反）"
    if text in ONEWAY_BIDIRECTIONAL:
        return "bidirectional", "osm", f"OSM oneway={value!r} → 双向"
    return (
        "bidirectional",
        "default",
        "OSM 未标注 oneway → 按 OSM 缺省双向理解（source=default，非实测）",
    )


def parse_lanes(value: Any) -> int | None:
    """OSM `lanes` 总数 → 正整数或 None（缺失不猜）。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def derive_lanes(direction: str, lanes_total: int | None) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    """按方向推车道三件套；**双向不拆分**（没有 OSM 分向车道数就不编）。"""
    values: dict[str, Any] = {
        "lanes_forward": None,
        "lanes_backward": None,
        "lanes_total": lanes_total,
    }
    sources = {
        "lanes_forward": "osm" if lanes_total is not None else "default",
        "lanes_backward": "default",
        "lanes_total": "osm" if lanes_total is not None else "default",
    }
    notes: list[str] = []
    if direction == "forward":
        values["lanes_forward"] = lanes_total
        values["lanes_backward"] = 0
        sources["lanes_backward"] = "derived"
        notes.append(
            "单向正向：后向 0（derived）；前向车道数 = OSM lanes 总数"
            if lanes_total is not None
            else "单向正向：后向 0（derived）；OSM 未抽到 lanes 总数 → 前向留 null，不编造"
        )
        return values, sources, notes
    if direction == "reverse":
        values["lanes_forward"] = 0
        values["lanes_backward"] = lanes_total
        sources["lanes_forward"] = "derived"
        notes.append(
            "单向反向：前向 0（derived）；后向车道数 = OSM lanes 总数"
            if lanes_total is not None
            else "单向反向：前向 0（derived）；OSM 未抽到 lanes 总数 → 后向留 null，不编造"
        )
        return values, sources, notes
    if lanes_total is None:
        notes.append("OSM 未抽到 lanes（总数也缺）→ 车道数一律 null，不编造（引擎按站点包 defaults 回落）")
    else:
        notes.append(
            "双向段：OSM 只给 lanes 总数，切片里没有 lanes:forward / lanes:backward → "
            "前/后向留 null（不拆分、不编造），只保留 lanes_total"
        )
    return values, sources, notes


def sequence_coords(edge: dict[str, Any], reverse: bool = False) -> list[list[float]]:
    """取段坐标序列；reverse=True 时倒序（用于反向行车的转向角）。"""
    coords = edge.get("coords") or []
    points = [
        [float(point[0]), float(point[1])]
        for point in coords
        if isinstance(point, (list, tuple)) and len(point) >= 2
    ]
    return list(reversed(points)) if reverse else points


def travel_endpoints(edge: dict[str, Any], direction: str) -> tuple[str, str]:
    """按声明方向给 (行车起点, 行车终点)。"""
    if direction == "reverse":
        return str(edge["to"]), str(edge["from"])
    return str(edge["from"]), str(edge["to"])


def build_explicit_opposites(edges: list[dict[str, Any]]) -> dict[str, str]:
    """端点完全互逆的段号配对（只看显式段，不按几何猜）。"""
    by_endpoints: dict[tuple[str, str], list[str]] = defaultdict(list)
    for edge in edges:
        by_endpoints[(str(edge["from"]), str(edge["to"]))].append(str(edge["segment_id"]))
    pairs: dict[str, str] = {}
    for edge in edges:
        segment_id = str(edge["segment_id"])
        candidates = sorted(by_endpoints.get((str(edge["to"]), str(edge["from"])), []))
        candidates = [item for item in candidates if item != segment_id]
        if candidates:
            pairs[segment_id] = candidates[0]
    return pairs


def build_chains(edges: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """同名且共享节点的段归一条 chain（按路名 + 无向连通分量）。

    返回 `segment_id -> {chain_id, chain_name, nodes}`。`chain_id` 按
    （chain_name, 最小段号）排序后编号，保证同一输入稳定。
    """
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        by_name[str(edge.get("name_raw") or edge.get("name") or "未命名")].append(edge)

    groups: list[tuple[str, list[dict[str, Any]]]] = []
    for name in sorted(by_name):
        members = by_name[name]
        by_id = {str(edge["segment_id"]): edge for edge in members}
        seen: set[str] = set()
        for edge in sorted(members, key=lambda item: str(item["segment_id"])):
            start = str(edge["segment_id"])
            if start in seen:
                continue
            stack = [start]
            component: list[str] = []
            while stack:
                segment_id = stack.pop()
                if segment_id in seen:
                    continue
                seen.add(segment_id)
                component.append(segment_id)
                current = by_id[segment_id]
                for other_id, other in by_id.items():
                    if other_id in seen:
                        continue
                    if {str(current["from"]), str(current["to"])} & {
                        str(other["from"]),
                        str(other["to"]),
                    }:
                        stack.append(other_id)
            groups.append((name, [by_id[item] for item in sorted(component)]))

    groups.sort(key=lambda item: (item[0], str(item[1][0]["segment_id"])))
    index: dict[str, dict[str, Any]] = {}
    for number, (name, members) in enumerate(groups, start=1):
        chain_id = f"CH-{number:03d}"
        nodes: set[str] = set()
        for edge in members:
            nodes.add(str(edge["from"]))
            nodes.add(str(edge["to"]))
        for edge in members:
            index[str(edge["segment_id"])] = {
                "chain_id": chain_id,
                "chain_name": name,
                "chain_nodes": sorted(nodes),
                "chain_segments": [str(item["segment_id"]) for item in members],
            }
    return index


def _edge_degrees(traversal: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, int]]:
    """有向出入度（按可通行遍历边计，不是按原始 from/to）。"""
    incoming: dict[str, int] = defaultdict(int)
    outgoing: dict[str, int] = defaultdict(int)
    for item in traversal:
        outgoing[item["from"]] += 1
        incoming[item["to"]] += 1
    return dict(incoming), dict(outgoing)


def derive_node_roles(
    nodes: list[dict[str, Any]],
    traversal: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """按有向出入度派生 boundary_role（含原 boundary 未覆盖的派生边界）。"""
    incoming, outgoing = _edge_degrees(traversal)
    roles: dict[str, dict[str, Any]] = {}
    for node in nodes:
        node_id = str(node.get("node_id") or node.get("id"))
        in_deg = int(incoming.get(node_id, 0))
        out_deg = int(outgoing.get(node_id, 0))
        raw_boundary = bool(node.get("boundary"))
        if in_deg == 0 and out_deg == 0:
            role = "isolated"
            source = "derived:无任何可通行边（非边界；check_topology 会报不可达）"
        elif in_deg == 0:
            role = "entry"
            source = (
                "raw_boundary+directed:入度 0"
                if raw_boundary
                else "derived:directed_in_degree_zero（原 boundary=false，无向度数判据漏掉多出边的边界节点）"
            )
        elif out_deg == 0:
            if raw_boundary:
                role = "exit"
                source = "raw_boundary+directed:出度 0"
            else:
                # 非边界出度 0 = 断头，**不能**当边界放行，否则"单向段尾部无后继"永远查不出来
                role = "dead_end"
                source = "derived:non_boundary_out_degree_zero（非边界断头，check_topology 会判 FAIL）"
        elif raw_boundary:
            role = "both"
            source = "raw_boundary+directed:进出都有（双向边界段）"
        else:
            role = "through"
            source = "derived:内部节点（进出都有）"
        roles[node_id] = {
            "in_degree": in_deg,
            "out_degree": out_deg,
            "boundary": raw_boundary,
            "boundary_effective": role in ("entry", "exit", "both"),
            "boundary_role": role,
            "boundary_role_source": source,
        }
    return roles



def classify_boundary_nodes(
    nodes: list[dict[str, Any]],
    roles: dict[str, dict[str, Any]],
    site: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """范围裁剪站点的边界断头/孤立支路分类（Issue IKOQEI，仅 ``range_clipped`` 站点启用）。

    只做**分类与证据**，不改变 ``boundary_role``（校验口径仍按有向出入度）：
    - 非边界出度 0 且距锚点 >= 90% 登记半径 → ``crop_boundary``（裁剪边界，道路可能在范围外延续）；
    - 非边界出度 0 且位于站区内部 → ``terminal_dead_end``（OSM 内无延续车行 way，疑为场区/内部道路终端
      或未合并连接；给出最近连接候选，需人工核对，不白名单放行）；
    - 无任何可通行边的节点 → ``isolated_component``。
    返回 ``node_id -> 分类证据``；未启用（如 Z 站）返回空字典，保证既有产物逐字节不变。
    """
    mode = str((site or {}).get("topology_boundary_mode") or "")
    if mode != "range_clipped":
        return {}
    anchor = (site or {}).get("anchor_lonlat")
    range_m = (site or {}).get("range_m")
    nodes_by_id = {str(n.get("node_id") or n.get("id")): n for n in nodes}
    classified: dict[str, dict[str, Any]] = {}
    for node_id, role in roles.items():
        if role.get("boundary_role") not in ("dead_end", "isolated"):
            continue
        node = nodes_by_id.get(node_id) or {}
        distance_m: float | None = None
        if (
            anchor
            and node.get("lon") is not None
            and node.get("lat") is not None
            and len(anchor) >= 2
        ):
            distance_m = round(
                haversine_m(float(anchor[0]), float(anchor[1]), float(node["lon"]), float(node["lat"])),
                1,
            )
        near_fence = (
            None if distance_m is None or not range_m else bool(distance_m >= float(range_m) * 0.9)
        )
        if role.get("boundary_role") == "dead_end" and near_fence:
            classification = "crop_boundary"
            reason = (
                f"非边界断头节点距锚点 {distance_m} m，位于登记半径 {range_m} m 的 90% 外："
                "该单向路在范围边界被截断、道路可能在范围外继续；按边界断头分类（需扩范围或人工核对），"
                "不作为 oneway_successor FAIL"
            )
            range_expandable = True
        elif role.get("boundary_role") == "dead_end":
            classification = "terminal_dead_end"
            reason = (
                f"非边界断头节点距锚点 {distance_m} m，位于站区内部：该节点在任何车行方向都没有可通行后继"
                "（OSM 切片内无延续车行 way，疑为场区/内部道路终端或近邻节点未合并）；"
                "按边界断头分类并保留最近连接候选，需人工核对（内部道路数据归 IKMHMX），不作为 FAIL"
            )
            range_expandable = False
        else:
            classification = "isolated_component"
            reason = (
                f"节点距锚点 {distance_m} m 且没有任何可通行遍历边（isolated）："
                "范围裁剪或 OSM 连接缺失导致的孤立支路；按孤立支路分类登记，需核对上游连接"
            )
            range_expandable = bool(near_fence)
        candidates: list[dict[str, Any]] = []
        if node.get("lon") is not None and node.get("lat") is not None:
            for other_id, other in nodes_by_id.items():
                if other_id == node_id or other.get("lon") is None or other.get("lat") is None:
                    continue
                distance = haversine_m(
                    float(node["lon"]), float(node["lat"]), float(other["lon"]), float(other["lat"])
                )
                if distance > 300:
                    continue
                other_role = roles.get(other_id, {})
                if not (
                    other_role.get("boundary_effective")
                    or int(other_role.get("in_degree") or 0) > 0
                    and int(other_role.get("out_degree") or 0) > 0
                ):
                    continue
                candidates.append(
                    {
                        "node_id": other_id,
                        "distance_m": round(distance, 1),
                        "boundary_role": other_role.get("boundary_role"),
                    }
                )
            candidates.sort(key=lambda item: (item["distance_m"], item["node_id"]))
        classified[node_id] = {
            "classification": classification,
            "reason": reason,
            "boundary_role": role.get("boundary_role"),
            "in_degree": role.get("in_degree"),
            "out_degree": role.get("out_degree"),
            "distance_to_anchor_m": distance_m,
            "near_registered_range": near_fence,
            "range_expandable": range_expandable,
            "nearest_connection_candidates": candidates[:3],
            "lon": node.get("lon"),
            "lat": node.get("lat"),
        }
    return classified


def _traversal_record(
    edge: dict[str, Any],
    *,
    edge_id: str,
    direction: str,
    from_node: str,
    to_node: str,
    lanes: Any,
    left_turn_allowed: Any,
) -> dict[str, Any]:
    """一条可通行遍历边的统一形状。"""
    return {
        "edge_id": edge_id,
        "segment_id": str(edge["segment_id"]),
        "from": from_node,
        "to": to_node,
        "direction": direction,
        "lanes": lanes,
        "length_m": edge.get("length_m"),
        "name": edge.get("name"),
        "name_raw": edge.get("name_raw"),
        "kind": edge.get("kind"),
        "boundary": bool(edge.get("boundary")),
        "u_turn_allowed": bool(edge.get("u_turn_allowed")),
        "left_turn_allowed": bool(left_turn_allowed),
    }


def derive_traversal(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 direction 展开可通行遍历边（双向段展开正向 + `_rev`）。"""
    traversal: list[dict[str, Any]] = []
    for edge in sorted(edges, key=lambda item: str(item["segment_id"])):
        segment_id = str(edge["segment_id"])
        direction = str(edge.get("direction") or "forward")
        lanes_forward = edge.get("lanes_forward", edge.get("lanes_total"))
        lanes_backward = edge.get("lanes_backward", edge.get("lanes_total"))
        if direction in ("forward", "bidirectional"):
            traversal.append(
                _traversal_record(
                    edge,
                    edge_id=segment_id,
                    direction="forward",
                    from_node=str(edge["from"]),
                    to_node=str(edge["to"]),
                    lanes=lanes_forward,
                    left_turn_allowed=edge.get("left_turn_allowed"),
                )
            )
        if direction == "bidirectional":
            traversal.append(
                _traversal_record(
                    edge,
                    edge_id=f"{segment_id}_rev",
                    direction="reverse",
                    from_node=str(edge["to"]),
                    to_node=str(edge["from"]),
                    lanes=lanes_backward,
                    left_turn_allowed=edge.get(
                        "left_turn_allowed_reverse", edge.get("left_turn_allowed")
                    ),
                )
            )
        elif direction == "reverse":
            traversal.append(
                _traversal_record(
                    edge,
                    edge_id=segment_id,
                    direction="reverse",
                    from_node=str(edge["to"]),
                    to_node=str(edge["from"]),
                    lanes=lanes_backward,
                    left_turn_allowed=edge.get("left_turn_allowed"),
                )
            )
    return traversal


def _left_turn_from_geometry(
    edge: dict[str, Any],
    reverse: bool,
    edges_by_id: dict[str, dict[str, Any]],
    traversal: list[dict[str, Any]],
) -> tuple[bool, str]:
    """更完整的左转推导：遍历所有从行车末端出发的遍历边，用各自坐标算转向角。"""
    coords = sequence_coords(edge, reverse=reverse)
    if len(coords) < 2:
        return False, "default"
    tail_node = str(edge["from"]) if reverse else str(edge["to"])
    in_bearing = bearing_deg(coords[-2][0], coords[-2][1], coords[-1][0], coords[-1][1])
    for item in traversal:
        if item["from"] != tail_node or item["segment_id"] == str(edge["segment_id"]):
            continue
        other = edges_by_id.get(item["segment_id"])
        if other is None:
            continue
        other_coords = sequence_coords(other, reverse=bool(item["direction"] == "reverse"))
        if len(other_coords) < 2:
            continue
        out_bearing = bearing_deg(
            other_coords[0][0],
            other_coords[0][1],
            other_coords[1][0],
            other_coords[1][1],
        )
        turn = signed_turn_deg(in_bearing, out_bearing)
        if LEFT_TURN_MIN_DEG <= turn <= LEFT_TURN_MAX_DEG:
            return True, "derived"
    return False, "derived"


def _nearest_candidate(
    node_id: str,
    nodes: dict[str, dict[str, Any]],
    starts: list[tuple[str, str]],
    exclude_segments: set[str],
    tol_m: float,
) -> tuple[str, str, float] | None:
    """离 node 最近的候选连接点（只出候选，不写图）。"""
    origin = nodes.get(node_id)
    if not origin or origin.get("lon") is None or origin.get("lat") is None:
        return None
    best: tuple[str, str, float] | None = None
    best_key: tuple[float, str, str] | None = None
    for segment_id, candidate_node_id in starts:
        if segment_id in exclude_segments:
            continue
        candidate = nodes.get(candidate_node_id)
        if not candidate or candidate.get("lon") is None or candidate.get("lat") is None:
            continue
        distance = haversine_m(
            float(origin["lon"]),
            float(origin["lat"]),
            float(candidate["lon"]),
            float(candidate["lat"]),
        )
        if distance > tol_m:
            continue
        key = (round(distance, 3), segment_id, candidate_node_id)
        if best_key is None or key < best_key:
            best_key = key
            best = (segment_id, candidate_node_id, distance)
    return best


# ============================================================================
# 主 enrich
# ============================================================================


def enrich(
    payload: dict[str, Any],
    *,
    site: dict[str, Any] | None = None,
    source_path: Path | str | None = None,
    source_sha256: str | None = None,
) -> dict[str, Any]:
    """在原产物上补方向 / 车道 / 贯通字段，返回新 payload（不修改入参）。"""
    if not isinstance(payload, dict):
        raise SystemExit("路网产物顶层不是对象")
    nodes_raw = payload.get("nodes")
    edges_raw = payload.get("edges")
    if not isinstance(nodes_raw, list) or not nodes_raw:
        raise SystemExit("路网产物缺非空 nodes 数组")
    if not isinstance(edges_raw, list) or not edges_raw:
        raise SystemExit("路网产物缺非空 edges 数组")

    nodes = {str(node.get("node_id") or node.get("id")): dict(node) for node in nodes_raw}
    edges: list[dict[str, Any]] = []
    for raw_edge in edges_raw:
        edge = dict(raw_edge)
        segment_id = str(edge.get("segment_id") or edge.get("id") or "")
        if not segment_id:
            raise SystemExit("edges[] 里有段缺 segment_id / id")
        edge["segment_id"] = segment_id
        edge["id"] = str(edge.get("id") or segment_id)
        edges.append(edge)

    nodes_by_id = {str(item["node_id"]): item for item in nodes.values()}
    edges_by_id = {str(item["segment_id"]): item for item in edges}

    # 无向度数（判断断头；按原始 from/to 计）
    undirected_degree: dict[str, int] = defaultdict(int)
    for edge in edges:
        undirected_degree[str(edge["from"])] += 1
        undirected_degree[str(edge["to"])] += 1

    opposites = build_explicit_opposites(edges)
    chains = build_chains(edges)

    # 第一遍：方向 / 车道 / 配对 / 掉头 / 贯通骨架（链 & 连接性先用方向展开的遍历图）
    provisional: list[dict[str, Any]] = []
    for edge in edges:
        direction, direction_source, direction_note = normalise_oneway(edge.get("oneway"))
        segment_id = str(edge["segment_id"])
        if direction_source == "default" and segment_id in opposites:
            # OSM 未标 oneway，但存在端点互逆的独立段号：按"对向单行"处理
            # （与 sumonet.py 的补边口径一致；否则两条几何会被重复当成双向，容量翻倍）
            direction = "forward"
            direction_source = "derived"
            direction_note = (
                "OSM 未标 oneway，但存在端点互逆的独立段号 "
                f"{opposites[segment_id]} → 按对向单行处理（derived，与 sumonet 补边口径一致）"
            )
        lanes_total = parse_lanes(edge.get("lanes"))
        lanes, lane_sources, lane_notes = derive_lanes(direction, lanes_total)
        start_node, end_node = travel_endpoints(edge, direction)
        u_turn_allowed = bool(
            direction == "bidirectional"
            and (
                undirected_degree.get(str(edge["from"]), 0) == 1
                or undirected_degree.get(str(edge["to"]), 0) == 1
            )
        )
        provisional.append(
            {
                **edge,
                "direction": direction,
                "lanes_forward": lanes["lanes_forward"],
                "lanes_backward": lanes["lanes_backward"],
                "lanes_total": lanes["lanes_total"],
                "opposite_segment_id": opposites.get(segment_id),
                "u_turn_allowed": u_turn_allowed,
                "travel_from": start_node,
                "travel_to": end_node,
                "_direction_source": direction_source,
                "_direction_note": direction_note,
                "_lane_sources": lane_sources,
                "_lane_notes": lane_notes,
            }
        )

    # 遍历图（用 provisional 的 direction）；边界角色也按同一张有向图派生
    traversal = derive_traversal(provisional)
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in traversal:
        outgoing[item["from"]].append(item)
        incoming[item["to"]].append(item)
    roles = derive_node_roles(list(nodes.values()), traversal)

    # 第二遍：贯通性 / 左转 / 来源
    starts = sorted({(item["segment_id"], item["from"]) for item in traversal})

    main_gap_candidates: list[dict[str, Any]] = []
    enriched_edges: list[dict[str, Any]] = []
    for edge in provisional:
        segment_id = str(edge["segment_id"])
        direction = str(edge["direction"])
        start_node, end_node = str(edge["travel_from"]), str(edge["travel_to"])
        own_ids = {segment_id} | ({f"{segment_id}_rev"} if direction == "bidirectional" else set())
        successors = [
            item for item in outgoing.get(end_node, []) if item["edge_id"] not in own_ids
        ]
        predecessors = [
            item for item in incoming.get(start_node, []) if item["edge_id"] not in own_ids
        ]
        head_connected = bool(successors)
        tail_connected = bool(predecessors)

        gap_to_next_m: float | None = None
        gap_node: str | None = None
        gap_segment: str | None = None
        tail_effective_boundary = bool(
            roles.get(end_node, {}).get("boundary_effective")
        )
        if head_connected:
            gap_to_next_m = 0.0
        elif not tail_effective_boundary:
            candidate = _nearest_candidate(
                end_node,
                nodes_by_id,
                starts,
                exclude_segments={segment_id},
                tol_m=CANDIDATE_TOL_M,
            )
            if candidate is not None:
                gap_segment, gap_node, gap_to_next_m = candidate
                gap_to_next_m = round(gap_to_next_m, 1)

        chain = chains.get(segment_id, {})
        continuity = {
            "head_connected": head_connected,
            "tail_connected": tail_connected,
            "chain_id": chain.get("chain_id"),
            "chain_name": chain.get("chain_name"),
            "is_main_road": str(edge.get("kind") or "") == "main",
            "gap_to_next_m": gap_to_next_m,
            "gap_to_next_node": gap_node,
            "gap_to_next_segment_id": gap_segment,
        }

        left_forward, left_forward_source = _left_turn_from_geometry(
            edge, False, edges_by_id, traversal
        )
        left_reverse_source = "default"
        left_reverse: bool | None = None
        if direction == "bidirectional":
            left_reverse, left_reverse_source = _left_turn_from_geometry(
                edge, True, edges_by_id, traversal
            )
        elif direction == "reverse":
            left_forward, left_forward_source = _left_turn_from_geometry(
                edge, True, edges_by_id, traversal
            )

        sources = {
            "direction": str(edge["_direction_source"]),
            "lanes_forward": str(edge["_lane_sources"]["lanes_forward"]),
            "lanes_backward": str(edge["_lane_sources"]["lanes_backward"]),
            "lanes_total": str(edge["_lane_sources"]["lanes_total"]),
            "opposite_segment_id": "derived",
            "u_turn_allowed": "derived",
            "left_turn_allowed": left_forward_source,
            "left_turn_allowed_reverse": left_reverse_source,
            "continuity.head_connected": "derived",
            "continuity.tail_connected": "derived",
            "continuity.chain_id": "derived",
            "continuity.is_main_road": "derived",
            "continuity.gap_to_next_m": "derived",
        }
        notes = [str(edge["_direction_note"]), *[str(item) for item in edge["_lane_notes"]]]
        if not head_connected:
            if tail_effective_boundary:
                notes.append("行车末端是边界/断头：无后继属正常，gap_to_next_m=null")
            else:
                notes.append("⚠ 非边界单行段行车末端无后继：check_topology 会判 FAIL")

        enriched_edge = {
            key: value
            for key, value in edge.items()
            if not key.startswith("_") and key not in ("travel_from", "travel_to")
        }
        enriched_edge.update(
            {
                "direction": direction,
                "lanes_forward": edge["lanes_forward"],
                "lanes_backward": edge["lanes_backward"],
                "lanes_total": edge["lanes_total"],
                "opposite_segment_id": edge["opposite_segment_id"],
                "u_turn_allowed": edge["u_turn_allowed"],
                "left_turn_allowed": left_forward,
                "left_turn_allowed_reverse": left_reverse,
                "continuity": continuity,
                "field_sources": sources,
                "field_source_notes": {
                    "direction": edge["_direction_note"],
                    "lanes": "；".join(edge["_lane_notes"]),
                    "u_turn_allowed": (
                        "规则：仅双向段 + 无向度数 1 的断头端点允许掉头；"
                        "OSM 切片没有掉头限制数据（derived，不冒充实测）"
                    ),
                    "left_turn_allowed": (
                        "按相邻段转向角几何推导（左转 = 有向角 ∈ [-150°, -30°]）；"
                        "OSM 切片没有 turn restriction 数据（derived）"
                    ),
                },
                "notes": notes,
            }
        )
        enriched_edges.append(enriched_edge)

        if continuity["is_main_road"] and not head_connected and not tail_effective_boundary:
            main_gap_candidates.append(
                {
                    "segment_id": segment_id,
                    "chain_id": continuity["chain_id"],
                    "tail_node": end_node,
                    "gap_to_next_m": gap_to_next_m,
                    "gap_to_next_node": gap_node,
                    "gap_to_next_segment_id": gap_segment,
                }
            )

    # 节点补 boundary_role（有向出入度；roles 与第二遍用的是同一张遍历图）
    anchor = (site or {}).get("anchor_lonlat")
    range_m = (site or {}).get("range_m")
    enriched_nodes: list[dict[str, Any]] = []
    for node in nodes.values():
        enriched = dict(node)
        node_id = str(enriched.get("node_id") or enriched.get("id"))
        enriched.update(roles[node_id])
        if not bool(enriched.get("boundary")) and enriched["boundary_role"] in (
            "entry",
            "exit",
            "both",
        ):
            distance_m: float | None = None
            if anchor and enriched.get("lon") is not None and enriched.get("lat") is not None:
                distance_m = round(
                    haversine_m(
                        float(anchor[0]),
                        float(anchor[1]),
                        float(enriched["lon"]),
                        float(enriched["lat"]),
                    ),
                    1,
                )
            near_fence = (
                None
                if distance_m is None or not range_m
                else bool(float(distance_m) >= float(range_m) * 0.9)
            )
            enriched["boundary_distance_m"] = distance_m
            enriched["boundary_near_fence"] = near_fence
            if near_fence is False:
                enriched["boundary_role_source"] += (
                    "；⚠ 距锚点 "
                    f"{distance_m} m < 站区范围 {range_m} m 的 90%，可能是缺失上游段而非边界，请核对"
                )
        enriched_nodes.append(enriched)

    # 统计
    direction_counts: dict[str, int] = defaultdict(int)
    source_counts: dict[str, int] = defaultdict(int)
    for edge in enriched_edges:
        direction_counts[str(edge["direction"])] += 1
        for source in edge["field_sources"].values():
            source_counts[str(source)] += 1
    role_counts: dict[str, int] = defaultdict(int)
    for node in enriched_nodes:
        role_counts[str(node["boundary_role"])] += 1
    derived_boundaries = [
        {
            "node_id": str(node.get("node_id")),
            "boundary_role": node["boundary_role"],
            "in_degree": node["in_degree"],
            "out_degree": node["out_degree"],
            "source": node["boundary_role_source"],
            "distance_to_anchor_m": node.get("boundary_distance_m"),
            "near_registered_range": node.get("boundary_near_fence"),
            "lon": node.get("lon"),
            "lat": node.get("lat"),
        }
        for node in enriched_nodes
        if not bool(node.get("boundary")) and node["boundary_role"] in ("entry", "exit", "both")
    ]

    # 范围裁剪站点的边界断头/孤立支路分类（Issue IKOQEI；只对 range_clipped 站点启用）
    boundary_classifications: list[dict[str, Any]] = []
    boundary_mode = str((site or {}).get("topology_boundary_mode") or "")
    if boundary_mode == "range_clipped":
        classified_nodes = classify_boundary_nodes(enriched_nodes, roles, site)
        for node in enriched_nodes:
            node_id = str(node.get("node_id") or node.get("id"))
            info = classified_nodes.get(node_id)
            if not info:
                continue
            node["boundary_classification"] = info["classification"]
            node["boundary_classification_reason"] = info["reason"]
            node["boundary_distance_m"] = info["distance_to_anchor_m"]
            node["boundary_near_fence"] = info["near_registered_range"]
            node["nearest_connection_candidates"] = info["nearest_connection_candidates"]
            boundary_classifications.append({"node_id": node_id, **info})

    total_lanes_known = sum(1 for edge in enriched_edges if edge["lanes_total"] is not None)
    payload_out = {
        key: value for key, value in payload.items() if key not in ("nodes", "edges")
    }
    payload_out["nodes"] = sorted(enriched_nodes, key=lambda item: str(item.get("node_id")))
    payload_out["edges"] = sorted(enriched_edges, key=lambda item: str(item["segment_id"]))
    payload_out["enrichment"] = {
        "schema_version": SCHEMA_VERSION,
        "is_simulated": True,
        "note": (
            "方向/车道/贯通性后处理产物（Issue IKNB9H）：**不覆盖原 network_junction.json**；"
            "几何/拓扑/oneway/lanes 原样保留，只补派生字段并逐字段标 field_sources。"
            "缺 OSM 字段一律标 default/derived，不编真实车道数；本文件是脚本产物，勿手改。"
        ),
        "generated_by": "work/twin/netpack/topology.py",
        "source_file": repo_rel(source_path) if source_path else None,
        "source_sha256": source_sha256,
        "site_id": site.get("site_id") if site else None,
        "site_name": site.get("site_name") if site else None,
        "rules": {
            "direction": (
                "oneway=yes → forward；oneway=-1 → reverse；oneway=no → bidirectional(osm)；"
                "oneway 缺失/未知 → bidirectional(default，OSM 缺省)"
            ),
            "lanes": (
                "只认原产物 OSM lanes 总数；单向段前/后向按方向落位、另一向 0(derived)；"
                "双向段没有 lanes:forward/backward → 前后向 null（不拆分、不编造）"
            ),
            "opposite_segment_id": "端点完全互逆的显式段号；双向单几何段不虚构配对，反向走 _rev 语义",
            "u_turn_allowed": "仅双向段 + 端点无向度数 1（断头）允许；其余 false",
            "left_turn_allowed": "按相邻段转向角几何推导（左转 = 有向角 [-150°,-30°]）",
            "continuity": (
                "head/tail connected 按可通行遍历边算（排除自身反向）；"
                "chain = 同名且共享节点的无向连通分量；gap_to_next_m 在无后继时给最近候选连接点距离"
            ),
            "boundary_role": (
                "有向出入度：入度 0 → entry；出度 0 → exit；原 boundary 且进出都有 → both；"
                "其余内部节点 → through。原 boundary 用无向度数 1，会漏掉多出边的边界节点（本单 N-006）"
            ),
            "candidate_connections": "只出候选（最近起终点，≤200 m），不自动写图、不手改 JSON",
        },
        "field_sources_vocabulary": {
            "osm": "原产物从 OSM tag 抽到的值（lanes / oneway）",
            "derived": "由拓扑/几何/方向规则推导，无 OSM 直接字段",
            "default": "缺失时的缺省假设（如 oneway 未标注按双向），不是实测",
        },
        "counts": {
            "segments": len(enriched_edges),
            "nodes": len(enriched_nodes),
            "directions": {key: direction_counts[key] for key in sorted(direction_counts)},
            "boundary_roles": {key: role_counts[key] for key in sorted(role_counts)},
            "lanes_total_known": total_lanes_known,
            "lanes_total_missing": len(enriched_edges) - total_lanes_known,
            "u_turn_allowed": sum(1 for edge in enriched_edges if edge["u_turn_allowed"]),
            "left_turn_allowed": sum(1 for edge in enriched_edges if edge["left_turn_allowed"]),
            "explicit_opposite_pairs": sum(
                1 for edge in enriched_edges if edge["opposite_segment_id"]
            )
            // 2,
            "main_road_gap_candidates": len(main_gap_candidates),
            "derived_boundaries": len(derived_boundaries),
            "field_source_values": {key: source_counts[key] for key in sorted(source_counts)},
        },
        "findings": {
            "derived_boundaries": derived_boundaries,
            "main_road_gap_candidates": main_gap_candidates,
        },
    }
    if boundary_classifications:
        # 仅 range_clipped 站点追加（Z 站无该字段，产物逐字节不变）
        enrichment = payload_out["enrichment"]
        enrichment["boundary_mode"] = boundary_mode
        enrichment["counts"]["boundary_classifications"] = len(boundary_classifications)
        enrichment["findings"]["boundary_classifications"] = boundary_classifications
    return payload_out


# ============================================================================
# 遍历图 / 算路 / 校验（check_topology.py 与自检复用）
# ============================================================================


def build_traversal(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """从 enriched（或至少带 direction 的）payload 建可通行遍历边。"""
    edges = payload.get("edges") or []
    normalized: list[dict[str, Any]] = []
    for item in edges:
        edge = dict(item)
        if "direction" not in edge:
            edge["direction"] = normalise_oneway(edge.get("oneway"))[0]
        normalized.append(edge)
    return derive_traversal(normalized)


def node_roles(payload: dict[str, Any], traversal: list[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    """优先读 enriched 里已写的 boundary_role，缺失则现推。"""
    trav = traversal if traversal is not None else build_traversal(payload)
    computed = derive_node_roles(payload.get("nodes") or [], trav)
    roles: dict[str, dict[str, Any]] = {}
    for node in payload.get("nodes") or []:
        node_id = str(node.get("node_id") or node.get("id"))
        role = dict(computed[node_id])
        for key in ("boundary_role", "boundary_role_source"):
            if key in node:
                role[key] = node[key]
        roles[node_id] = role
    return roles


def build_adjacency(traversal: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_id: dict[str, dict[str, Any]] = {}
    for item in traversal:
        by_id[item["edge_id"]] = item
        outgoing[item["from"]].append(item)
        incoming[item["to"]].append(item)
    return outgoing, by_id


def _reverse_of(by_id: dict[str, dict[str, Any]], edge_id: str) -> str | None:
    """同一段号、相反方向的那条遍历边（没有则 None）。"""
    item = by_id[edge_id]
    for candidate_id, candidate in by_id.items():
        if (
            candidate["segment_id"] == item["segment_id"]
            and candidate["direction"] != item["direction"]
        ):
            return candidate_id
    return None


def is_u_turn(by_id: dict[str, dict[str, Any]], previous: str, current: str) -> bool:
    """连续两条遍历边是否构成原地掉头（同段号、方向相反）。"""
    prev = by_id[previous]
    cur = by_id[current]
    return prev["segment_id"] == cur["segment_id"] and prev["direction"] != cur["direction"]


def find_path(
    traversal: list[dict[str, Any]],
    source: str,
    target: str,
    *,
    forbid_u_turn: bool = True,
    weight_key: str = "length_m",
) -> list[str] | None:
    """有向最短路（边状态 Dijkstra），返回遍历边 id 序列；不可达返回 None。

    `forbid_u_turn=True` 时，**只禁止**同一段"正向→反向"立即掉头且该段
    `u_turn_allowed=false`；其它转向不受限（左转限制只做字段，不参与算路）。
    """
    if source == target:
        return []
    outgoing, by_id = build_adjacency(traversal)
    start: tuple[float, tuple[str, ...], str, str | None] = (0.0, (), source, None)
    best: dict[tuple[str, str | None], float] = {(source, None): 0.0}
    heap = [start]
    while heap:
        cost, path, node, previous = heapq.heappop(heap)
        if node == target:
            return list(path)
        if cost > best.get((node, previous), float("inf")):
            continue
        for item in outgoing.get(node, []):
            edge_id = item["edge_id"]
            if (
                forbid_u_turn
                and previous is not None
                and is_u_turn(by_id, previous, edge_id)
                and not by_id[previous]["u_turn_allowed"]
            ):
                continue
            try:
                weight = float(item.get(weight_key) or 0.0)
            except (TypeError, ValueError):
                weight = 0.0
            new_cost = cost + max(weight, 0.0)
            key = (item["to"], edge_id)
            if new_cost < best.get(key, float("inf")):
                best[key] = new_cost
                heapq.heappush(heap, (new_cost, path + (edge_id,), item["to"], edge_id))
    return None


def validate_path(
    traversal: list[dict[str, Any]],
    path: Iterable[str],
    *,
    source: str | None = None,
    target: str | None = None,
) -> dict[str, Any]:
    """校验一条路线：连续、可通行、无非法掉头；返回 violations + legs。"""
    outgoing, by_id = build_adjacency(traversal)
    route = [str(item) for item in path]
    violations: list[dict[str, Any]] = []
    legs: list[dict[str, Any]] = []
    if source is not None and route:
        first = by_id.get(route[0])
        if first is None or first["from"] != source:
            violations.append({"code": "path_not_contiguous", "detail": f"首边不在 {source}"})
    for index, edge_id in enumerate(route):
        item = by_id.get(edge_id)
        if item is None:
            violations.append({"code": "edge_not_found", "edge_id": edge_id})
            continue
        if index:
            previous = by_id.get(route[index - 1])
            if previous is not None and previous["to"] != item["from"]:
                violations.append(
                    {
                        "code": "path_not_contiguous",
                        "detail": f"{route[index - 1]} 终点 {previous['to']} ≠ {edge_id} 起点 {item['from']}",
                    }
                )
            if previous is not None and is_u_turn(by_id, route[index - 1], edge_id):
                if not previous["u_turn_allowed"]:
                    violations.append(
                        {
                            "code": "illegal_u_turn",
                            "detail": (
                                f"在 {previous['to']} 从 {route[index - 1]} 原地掉头到 {edge_id}，"
                                "该段 u_turn_allowed=false"
                            ),
                        }
                    )
        legs.append(
            {
                "edge_id": item["edge_id"],
                "segment_id": item["segment_id"],
                "direction": item["direction"],
                "from_node": item["from"],
                "to_node": item["to"],
                "lanes": item["lanes"],
                "u_turn_allowed": item["u_turn_allowed"],
                "left_turn_allowed": item["left_turn_allowed"],
            }
        )
    if target is not None:
        if route:
            last = by_id.get(route[-1])
            if last is not None and last["to"] != target:
                violations.append({"code": "path_not_contiguous", "detail": f"末边不在 {target}"})
        elif source != target:
            violations.append({"code": "path_not_contiguous", "detail": "空路径不是有效行程"})
    return {
        "edge_ids": route,
        "legs": legs,
        "violations": violations,
        "valid": not violations,
    }


def entry_exit_nodes(roles: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    entries = sorted(
        node_id for node_id, role in roles.items() if role["boundary_role"] in ("entry", "both")
    )
    exits = sorted(
        node_id for node_id, role in roles.items() if role["boundary_role"] in ("exit", "both")
    )
    return entries, exits


def reachable_nodes(
    traversal: list[dict[str, Any]],
    source: str,
    *,
    forbid_u_turn: bool = True,
) -> set[str]:
    """从 source 出发的有向可达节点集合（含 source）。"""
    outgoing, by_id = build_adjacency(traversal)
    seen: set[str] = {source}
    best: dict[tuple[str, str | None], float] = {(source, None): 0.0}
    heap: list[tuple[float, str, str | None]] = [(0.0, source, None)]
    while heap:
        cost, node, previous = heapq.heappop(heap)
        if cost > best.get((node, previous), float("inf")):
            continue
        for item in outgoing.get(node, []):
            edge_id = item["edge_id"]
            if (
                forbid_u_turn
                and previous is not None
                and is_u_turn(by_id, previous, edge_id)
                and not by_id[previous]["u_turn_allowed"]
            ):
                continue
            new_cost = cost + max(float(item.get("length_m") or 0.0), 0.0)
            key = (item["to"], edge_id)
            if new_cost < best.get(key, float("inf")):
                best[key] = new_cost
                seen.add(item["to"])
                heapq.heappush(heap, (new_cost, item["to"], edge_id))
    return seen


def reverse_traversal(traversal: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """反转遍历图（用于"能否到达某个 exit"的检查）；U-turn 语义保持对称。"""
    result: list[dict[str, Any]] = []
    for item in traversal:
        flipped = dict(item)
        flipped["from"], flipped["to"] = item["to"], item["from"]
        result.append(flipped)
    return result


# ============================================================================
# 文件级入口
# ============================================================================


def enrich_file(
    raw_path: Path | str,
    output_path: Path | str | None = None,
    *,
    site: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """读原产物 → enrich → 写 enriched（不覆盖原文件）。"""
    path = Path(raw_path)
    if not path.is_file():
        raise SystemExit(f"缺路网原产物:{path}")
    raw_bytes = path.read_bytes()
    payload = read_json(path)
    result = enrich(
        payload,
        site=site,
        source_path=path,
        source_sha256=sha256_bytes(raw_bytes),
    )
    target = Path(output_path) if output_path else enriched_path_for(path)
    write_json(target, result)
    return result


def main(argv: list[str] | None = None) -> int:
    # Windows 控制台默认 GBK 编不了 ✅/❌；本进程显式改 UTF-8（不改仓库文件编码）。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(
        description=(
            "路段方向/车道/贯通性后处理：读 network_junction.json，写 "
            "network_junction.enriched.json（不覆盖原文件；不读系统时钟）"
        )
    )
    parser.add_argument("--site-id", default=None, help="站点登记表里的 site_id（缺省 default_site）")
    parser.add_argument("--config", default=str(DEFAULT_SITE_RANGES), help="站点范围登记表路径")
    parser.add_argument("--input", default=None, help="原始路网 JSON（缺省取登记表 out_json）")
    parser.add_argument("--output", default=None, help="enriched 输出路径（缺省原文件同名 .enriched.json）")
    parser.add_argument(
        "--check",
        action="store_true",
        help="只校验：重算 enrich 并与既有 enriched 逐字节比对（不写盘，不一致非 0 退出）",
    )
    args = parser.parse_args(argv)

    site = pick_site(args.site_id, args.config) if not args.input else None
    raw_path = Path(args.input) if args.input else raw_network_path(site)
    output_path = Path(args.output) if args.output else enriched_path_for(raw_path)
    if not raw_path.is_file():
        print(f"❌ 缺原始路网:{raw_path}")
        return 2

    raw_bytes = raw_path.read_bytes()
    payload = read_json(raw_path)
    result = enrich(
        payload,
        site=site,
        source_path=raw_path,
        source_sha256=sha256_bytes(raw_bytes),
    )
    text = json_text(result)

    if args.check:
        have = output_path.read_text(encoding="utf-8") if output_path.is_file() else ""
        if have != text:
            print(f"❌ enriched 与重算结果不一致:{output_path}")
            print("   先重跑 `python work/twin/netpack/topology.py` 再提交")
            return 1
        print(f"✅ enriched 与重算逐字节一致:{repo_rel(output_path)}")
        counts = result["enrichment"]["counts"]
        print(
            f"   {counts['segments']} 段 / {counts['nodes']} 节点 · "
            f"方向 {counts['directions']} · 来源 {counts['field_source_values']}"
        )
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8", newline="\n")
    counts = result["enrichment"]["counts"]
    print(f"→ {repo_rel(output_path)}")
    print(
        f"   {counts['segments']} 段 / {counts['nodes']} 节点 · "
        f"方向 {counts['directions']} · 派生边界 {counts['derived_boundaries']} 个 · "
        f"主干道候选 gap {counts['main_road_gap_candidates']} 处"
    )
    print(f"   字段来源 {counts['field_source_values']}")
    print(
        f"   lanes 总数已知 {counts['lanes_total_known']} 段 / 缺 "
        f"{counts['lanes_total_missing']} 段（缺的保持 null，不编造）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
