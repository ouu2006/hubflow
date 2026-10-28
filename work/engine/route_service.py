"""任意起点 / 终点算路：一主 + ≤2 备选（TC-03 / M1-4）。

## 为什么单独一个模块

`work/engine/run.py` 是**批量产物生成器**：OD 由边界推导（`realnet.derive_od_pairs`），
一次跑出整份 `routes.json`；接口层只读产物。页面要"自己选起点终点"时，
既不能每次改 OD 重跑批量，也不该在接口层复制一份 Dijkstra。

本模块把「给两个端点算 1 主 + 2 备选」抽成纯函数：

- 端点三种形态：`{"point_id": ...}` / `{"segment_id": ..., "offset_m": ...}` / `{"node_id": ...}`；
- **中边起终点**：起点在边中段时，先走完该边剩余长度再从边终点算；终点同理，补上偏移段；
- 备选：**只放大候选池的搜索深度**（`K_GENERATE=30`，与 `realnet.CANDIDATE_SEARCH_K` 同值），
  再按 `max_path_overlap=0.7` 的**全长重叠度**筛到 3 条。重叠度口径一个字节不动 ——
  业主 2026-10-28 裁定：去掉公共首尾再比是绕过门槛凑等价路径，本模块**不做**；
- 不足 3 条时如实返回 `alternatives_status`（`single_path` / `no_diverse_path`）+ 原因，
  **不凑等价路线**（契约第二节）。

口径：
- 不读系统时钟、不用随机数，同一输入结果一致；
- 权重默认自由流（`length_m / speed`），传 `states` 时用 BPR（与 `run.py` 同一套参数）；
- 所有输出标 `is_simulated: True`（一期全是演示数据）。

用法：

    from route_service import plan, load_points
    result = plan(graph, {"point_id": "ENT-004"}, {"point_id": "DROP-01"}, points=points)
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable

import candidates
import network

ROOT = Path(__file__).resolve().parents[2]
POINTS_DIR = ROOT / "stations"

#: 候选池的搜索深度：Yen 先生成 30 条原始候选，再按 `max_path_overlap` 全长重叠度筛到 3 条。
#: 与 `work/engine/realnet.py` 的 `CANDIDATE_SEARCH_K = 30` 同值同口径（!87 的做法）：
#: 真网只有 44 节点 / 61 段，池深 = 3 时第一条最短路的近邻几乎全被 0.7 筛掉 → 备选恒为 0。
#: **门槛本身（`decision.max_path_overlap`）不在这里，也不因本常量放宽。**
K_GENERATE = 30
#: 最多返回的路线数（1 主 + 2 备）
K_ROUTES = 3
#: 缺省参数（与 stations/thresholds.json 的 decision 组同口径，读不到就用这组演示值）
DEFAULT_PARAMS = {
    "k_candidates": K_ROUTES,
    "max_path_overlap": 0.7,
    "eps_harm_s": 30.0,
    "free_flow_speed_kmh": 40.0,
    "bpr_alpha": 0.15,
    "bpr_beta": 4.0,
}

STATUS_OK = "ok"
STATUS_PARTIAL = "partial"
STATUS_SINGLE = "single_path"
STATUS_NO_DIVERSE = "no_diverse_path"
STATUS_UNREACHABLE = "unreachable"


class UnreachableError(ValueError):
    """起点到终点在有向路网上不可达。

    单独一个类型（仍是 `ValueError` 的子类，旧调用方不受影响）是为了让接口层能区分
    「参数不合法（400）」与「路网如实不可达（200 + reachable=false + note）」。
    """


# ---------------------------------------------------------------- 任意坐标吸路段
#: 把经纬度差换成米用的两个近似系数（站区尺度 ~1 km，足够；不是测绘精度）
_M_PER_DEG_LAT = 110540.0
_M_PER_DEG_LON_EQ = 111320.0


def _local_xy(lon: float, lat: float, lon0: float, lat0: float) -> tuple[float, float]:
    """以 (lon0, lat0) 为原点的等距圆柱近似：返回 (东向米, 北向米)。"""
    return (
        (lon - lon0) * _M_PER_DEG_LON_EQ * math.cos(math.radians(lat0)),
        (lat - lat0) * _M_PER_DEG_LAT,
    )


def snap_to_segment(
    graph: network.Graph,
    lon: float,
    lat: float,
    *,
    max_distance_m: float = 60.0,
) -> dict[str, Any]:
    """任意坐标 → **最近路段 + 沿线偏移**（页面「点图选起终点」用）。

    返回 `{matched, segment_id, offset_m, distance_m, lon, lat, node_id, direction, edge_id, note}`：
    - `offset_m` 按该段 `length_m` 的比例还原（与 `resolve_endpoint` 的 offset 同一口径，
      可直接回灌 `{"segment_id": …, "offset_m": …}` 算路）；
    - `lon/lat` 是**投影到路段上**的那个点（不是原始点击点），页面拿它画标记才对得上线；
    - `distance_m > max_distance_m` → `matched=False` + note，页面如实提示「点得离线太远」，
      绝不硬吸到几十米外的路段上当作选中。
    """
    lon = float(lon)
    lat = float(lat)
    best: dict[str, Any] | None = None
    for edge_id in graph._edges:  # noqa: SLF001 - 只读遍历，顺序即插入序（确定性）
        edge = graph.edge(edge_id)
        coords = edge.get("coords") or []
        if len(coords) < 2:
            continue
        length_m = float(edge.get("length_m") or 0.0)
        if length_m <= 0:
            continue
        # 折线各小段的平面长度（米），用来把「离小段起点多远」换算成「离整段起点多远」
        pieces: list[float] = []
        along_m = 0.0
        for index in range(len(coords) - 1):
            a = _local_xy(float(coords[index][0]), float(coords[index][1]), lon, lat)
            b = _local_xy(float(coords[index + 1][0]), float(coords[index + 1][1]), lon, lat)
            pieces.append(math.hypot(b[0] - a[0], b[1] - a[1]))
        total_pieces = sum(pieces)
        if total_pieces <= 0:
            continue
        for index in range(len(coords) - 1):
            lon1, lat1 = float(coords[index][0]), float(coords[index][1])
            lon2, lat2 = float(coords[index + 1][0]), float(coords[index + 1][1])
            ax, ay = _local_xy(lon1, lat1, lon, lat)
            bx, by = _local_xy(lon2, lat2, lon, lat)
            dx, dy = bx - ax, by - ay
            seg2 = dx * dx + dy * dy
            t = 0.0 if seg2 <= 0 else max(0.0, min(1.0, (-ax * dx - ay * dy) / seg2))
            px, py = ax + t * dx, ay + t * dy
            dist = math.hypot(px, py)
            if best is None or dist < best["_dist"]:
                ratio = (along_m + t * pieces[index]) / total_pieces
                best = {
                    "_dist": dist,
                    "distance_m": dist,
                    "offset_m": round(ratio * length_m, 1),
                    # 投影点按经纬度线性插值回真实坐标（页面画标记用）
                    "lon": round(lon1 + t * (lon2 - lon1), 7),
                    "lat": round(lat1 + t * (lat2 - lat1), 7),
                    "segment_id": str(edge.get("section") or edge_id),
                    "direction": edge.get("direction"),
                    "edge_id": str(edge_id),
                    "node_id": str(edge.get("from")),
                }
            along_m += pieces[index]
    if best is None:
        return {
            "matched": False,
            "segment_id": None,
            "offset_m": None,
            "distance_m": None,
            "lon": round(lon, 7),
            "lat": round(lat, 7),
            "node_id": None,
            "direction": None,
            "note": "该坐标附近没有带几何的真网路段",
        }
    dist = best.pop("_dist")
    best["distance_m"] = round(dist, 1)
    best["matched"] = dist <= float(max_distance_m)
    if not best["matched"]:
        best["note"] = (
            f"离最近路段 {dist:.0f} m（超过 {max_distance_m:.0f} m 吸附阈值）："
            "不硬吸附，请点得靠近路网一些"
        )
    else:
        best["note"] = None
    return best


# ---------------------------------------------------------------- 点位注册表
def points_path(site_id: str, directory: Path | None = None) -> Path:
    return (directory or POINTS_DIR) / f"{site_id}.points.json"


def load_points(site_id: str, directory: Path | None = None) -> dict[str, Any]:
    """读 `stations/<site_id>.points.json`；缺文件返回空表（调用方如实降级）。"""
    path = points_path(site_id, directory)
    if not path.is_file():
        return {"site_id": site_id, "points": [], "missing": True, "path": str(path)}
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["missing"] = False
    payload["path"] = str(path)
    return payload


def point_index(points: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(p.get("point_id")): p for p in (points.get("points") or []) if p.get("point_id")}


# ---------------------------------------------------------------- 端点解析
def _edges_of_section(graph: network.Graph, section: str) -> list[dict[str, Any]]:
    out = []
    for edge_id in graph._edges:  # noqa: SLF001 - 只读遍历
        edge = graph.edge(edge_id)
        if str(edge.get("section")) == str(section):
            out.append(edge)
    return out


def _pick_edge(graph: network.Graph, section: str, direction: str | None) -> dict[str, Any] | None:
    edges = _edges_of_section(graph, section)
    if not edges:
        return None
    if direction:
        for edge in edges:
            if str(edge.get("direction")) == str(direction):
                return edge
    # 没有方向提示时优先正向，再退回第一条（确定性排序）
    edges.sort(key=lambda e: (str(e.get("direction")) != "forward", str(e.get("id"))))
    return edges[0]


def resolve_endpoint(
    graph: network.Graph,
    spec: dict[str, Any],
    points: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """把端点形态统一成 `{node, segment_id, offset_m, prefix_m, suffix_m, ...}`。

    支持四种形态：`{lon, lat}`（页面点图选的任意坐标，先吸附最近路段）/
    `{point_id}` / `{segment_id, offset_m}` / `{node_id}`。

    - 起点：`prefix` = 从中边位置走到该边终点的那一段（在路线前面补上）；
    - 终点：`suffix` = 从该边起点走到目标位置的那一段（在路线后面补上）。

    解析失败抛 `ValueError`，调用方转成 400 / `note`（不编造路线）。
    """
    spec = spec or {}
    # 地图点选的任意坐标：先吸附到最近路段，再按「段 + 偏移」算路（吸附结果回显给页面）
    if spec.get("lon") is not None and spec.get("lat") is not None and not spec.get("segment_id"):
        snap = snap_to_segment(graph, float(spec["lon"]), float(spec["lat"]))
        if not snap.get("matched"):
            raise ValueError(
                snap.get("note") or "该坐标附近没有可吸附的真网路段（点得离线太远）"
            )
        spec = {
            "segment_id": snap["segment_id"],
            "offset_m": snap["offset_m"],
            "direction": snap.get("direction"),
            "node_id": snap.get("node_id"),
            "label": f"{snap['segment_id']} @ {snap['offset_m']:.0f} m",
            "_snap": snap,
            "_click": {"lon": float(spec["lon"]), "lat": float(spec["lat"])},
        }
    index = point_index(points or {})
    if spec.get("point_id"):
        point = index.get(str(spec["point_id"]))
        if point is None:
            raise ValueError(f"点位 {spec['point_id']} 不在注册表")
        # 命名点位（落客点 / 场区 / 入口）**按 node_id 算路**：
        # 点的 segment+offset 只用于地图定位与展示，若按"中边"算路，会把终点硬压到
        # 该边的起点节点，实测真网只剩 1 条可行路径（备选全没）。
        node_id = point.get("node_id")
        if node_id and str(node_id) in set(graph.node_ids):
            return {
                "kind": "node",
                "routing": "node",
                "node": str(node_id),
                "segment_id": point.get("segment_id"),
                "offset_m": point.get("offset_m"),
                "direction": point.get("direction"),
                "prefix_m": 0.0,
                "suffix_m": 0.0,
                "prefix_edges": [],
                "suffix_edges": [],
                "label": point.get("name") or point.get("point_id"),
                "access_m": point.get("access_m"),
                "point_id": point.get("point_id"),
                "snap": {
                    "kind": "node",
                    "node_id": str(node_id),
                    "segment_id": point.get("segment_id"),
                    "offset_m": point.get("offset_m"),
                    "access_m": point.get("access_m"),
                },
            }
        spec = {
            "segment_id": point.get("segment_id"),
            "offset_m": point.get("offset_m"),
            "direction": point.get("direction"),
            "node_id": point.get("node_id"),
            "label": point.get("name"),
            "point_id": point.get("point_id"),
        }
    elif spec.get("segment_id") is None and spec.get("node_id"):
        node_id = str(spec["node_id"])
        if node_id not in set(graph.node_ids):
            raise ValueError(f"节点 {node_id} 不在真网")
        return {
            "kind": "node",
            "node": node_id,
            "segment_id": None,
            "offset_m": None,
            "direction": None,
            "prefix_m": 0.0,
            "suffix_m": 0.0,
            "prefix_edges": [],
            "suffix_edges": [],
            "label": spec.get("label") or node_id,
            "snap": {"kind": "node", "node_id": node_id},
        }

    section = spec.get("segment_id")
    if not section:
        raise ValueError("端点必须给 point_id / segment_id(+offset_m) / node_id 之一")
    edge = _pick_edge(graph, str(section), spec.get("direction"))
    if edge is None:
        raise ValueError(f"路段 {section} 不在真网")
    length = float(edge.get("length_m") or 0.0)
    offset = spec.get("offset_m")
    offset = 0.0 if offset is None else float(offset)
    if offset < -0.5 or offset > length + 0.5:
        raise ValueError(f"路段 {section} 的 offset_m={offset} 超出 0~{length:.1f} m")
    offset = max(0.0, min(length, offset))
    node_id = spec.get("node_id") or str(edge["from"])
    # 由点击坐标吸附来的端点：把吸附距离 / 投影点一并回显（页面要标「吸附到哪」）
    raw_snap = spec.get("_snap") or {}
    snap = {
        "kind": "segment",
        "segment_id": str(edge.get("section")),
        "offset_m": round(offset, 1),
    }
    if raw_snap:
        snap.update(
            {
                "matched": True,
                "distance_m": raw_snap.get("distance_m"),
                "lon": raw_snap.get("lon"),
                "lat": raw_snap.get("lat"),
            }
        )
        if spec.get("_click"):
            snap["click"] = spec["_click"]
    return {
        "kind": "segment",
        "node": node_id,
        "segment_id": str(edge.get("section")),
        "offset_m": round(offset, 1),
        "direction": str(edge.get("direction")),
        "edge_id": str(edge.get("id")),
        "edge": edge,
        "length_m": length,
        "prefix_m": 0.0,
        "suffix_m": 0.0,
        "prefix_edges": [],
        "suffix_edges": [],
        "label": spec.get("label") or str(edge.get("name") or edge.get("section")),
        "snap": snap,
    }


def _start_from(origin: dict[str, Any]) -> dict[str, Any]:
    """起点 → (起始节点, 需要补在前面的边, 补的长度)。"""
    if origin["kind"] == "node":
        return {"node": origin["node"], "edges": [], "m": 0.0, "first_edge": None}
    edge = origin["edge"]
    length = origin["length_m"]
    offset = origin["offset_m"]
    if offset <= 0.5:
        return {"node": str(edge["from"]), "edges": [], "m": 0.0, "first_edge": None}
    remaining = length - offset
    return {"node": str(edge["to"]), "edges": [str(edge["id"])], "m": remaining, "first_edge": str(edge["id"])}


def _end_at(destination: dict[str, Any]) -> dict[str, Any]:
    """终点 → (结束节点, 需要补在后面的边, 补的长度)。"""
    if destination["kind"] == "node":
        return {"node": destination["node"], "edges": [], "m": 0.0, "last_edge": None}
    edge = destination["edge"]
    length = destination["length_m"]
    offset = destination["offset_m"]
    if offset >= length - 0.5:
        return {"node": str(edge["to"]), "edges": [], "m": 0.0, "last_edge": None}
    if offset <= 0.5:
        return {"node": str(edge["from"]), "edges": [], "m": 0.0, "last_edge": None}
    return {"node": str(edge["from"]), "edges": [str(edge["id"])], "m": offset, "last_edge": str(edge["id"])}


# ---------------------------------------------------------------- 权重
def free_flow_weight(graph: network.Graph, params: dict[str, Any]) -> Callable[[str], float]:
    speed_kmh = float(params.get("free_flow_speed_kmh") or DEFAULT_PARAMS["free_flow_speed_kmh"])
    speed_ms = max(0.1, speed_kmh / 3.6)

    def weight(edge_id: str) -> float:
        edge = graph.edge(edge_id)
        limit = edge.get("speed_limit") or speed_kmh
        return float(edge.get("length_m") or 0.0) / max(0.1, float(limit) / 3.6)

    return weight


def bpr_weight(
    graph: network.Graph, states: dict[str, dict[str, Any]], params: dict[str, Any]
) -> Callable[[str], float]:
    """BPR 权重（与 run.py 同口径）：t = t0 * (1 + α·x^β)，x 取 `section` 对齐的状态。"""
    alpha = float(params.get("bpr_alpha") or DEFAULT_PARAMS["bpr_alpha"])
    beta = float(params.get("bpr_beta") or DEFAULT_PARAMS["bpr_beta"])
    base = free_flow_weight(graph, params)

    def weight(edge_id: str) -> float:
        edge = graph.edge(edge_id)
        state = states.get(str(edge.get("section"))) or {}
        x = state.get("x")
        try:
            x = float(x) if x is not None else 0.0
        except (TypeError, ValueError):
            x = 0.0
        return base(edge_id) * (1.0 + alpha * max(0.0, x) ** beta)

    return weight


# ---------------------------------------------------------------- 算路
def _edge_sections(graph: network.Graph, edge_ids: list[str]) -> list[str]:
    out: list[str] = []
    for edge_id in edge_ids:
        section = str(graph.edge(edge_id).get("section") or edge_id)
        if not out or out[-1] != section:
            out.append(section)
    return out


def _route_length_m(graph: network.Graph, edge_ids: list[str], trim_head_m: float, trim_tail_m: float) -> float:
    total = sum(float(graph.edge(eid).get("length_m") or 0.0) for eid in edge_ids)
    return max(0.0, total - trim_head_m - trim_tail_m)


def _route_reason(
    graph: network.Graph,
    base: list[str],
    other: list[str],
    eta_min: float,
    base_eta: float,
    base_length_m: float,
    length_m: float,
) -> str:
    """备选与推荐路线的差异：**分岔节点 + 差异段数 + 里程差 + 用时差**（TC-03 口径）。"""
    diff_edges = sorted(set(other) ^ set(base))
    diverge = ""
    for index, edge_id in enumerate(other):
        if index >= len(base) or base[index] != edge_id:
            diverge = str(graph.edge(edge_id).get("from"))
            break
    delta_m = length_m - base_length_m
    delta_s = (eta_min - base_eta) * 60.0
    parts = [f"差异 {len(diff_edges)} 段"]
    if diverge:
        parts.append(f"分岔点 {diverge}")
    parts.append(f"里程 {delta_m:+.1f} m")
    parts.append(f"用时 {delta_s:+.1f} s")
    return " · ".join(parts)


def _dedupe_edges(edges: list[str]) -> list[str]:
    out: list[str] = []
    for edge in edges:
        if not out or out[-1] != edge:
            out.append(edge)
    return out


def plan_departure(
    graph: network.Graph,
    destination: dict[str, Any],
    *,
    params: dict[str, Any] | None = None,
    states: dict[str, dict[str, Any]] | None = None,
    points: dict[str, Any] | None = None,
    exit_node: str | None = None,
) -> dict[str, Any] | None:
    """**离站路线**：从终点（落客区）驶出站区到场界出口，单独算、单独返回。

    业主 2026-10-28 口径「离站另外计算」——它不并进主/备选，本函数自成一个结果块。

    出口选取（`exit_node` 缺省时）：在**从终点可达**的边界节点里取自由流最快的一个，
    与 `realnet.derive_od_pairs` 给引擎 OD 定 `exit_node` 的口径一致；
    同代价时按 `node_id` 排序，保证同一输入结果稳定。
    算不出就返回 `None`（页面如实空窗），**不编造一段假出口**。
    """
    params = {**DEFAULT_PARAMS, **(params or {})}
    dest_r = resolve_endpoint(graph, destination, points)
    end = _end_at(dest_r)
    src = end["node"]
    weight = bpr_weight(graph, states, params) if states else free_flow_weight(graph, params)
    forbid_u_turn = bool(graph.attributes.get("forbid_u_turn"))

    candidates_out: list[str] = []
    if exit_node:
        if str(exit_node) not in set(graph.node_ids):
            return None
        candidates_out = [str(exit_node)]
    else:
        for node_id in graph.node_ids:
            node = graph.node(node_id)
            if bool(node.get("boundary")) or bool(node.get("boundary_effective")):
                candidates_out.append(str(node_id))
        candidates_out.sort()
    if not candidates_out:
        return None

    picked: tuple[float, str] | None = None
    picked_path: list[str] | None = None
    for node_id in candidates_out:
        if node_id == src:
            picked, picked_path = (0.0, node_id), []
            break
        path = candidates.dijkstra(graph, src, node_id, weight, forbid_u_turn=forbid_u_turn)
        if path is None:
            continue
        # dijkstra 返回边序列，代价按同一权重函数累加（与选路口径一致）
        key = (round(sum(weight(eid) for eid in path), 6), node_id)
        if picked is None or key < picked:
            picked, picked_path = key, path
    if picked is None:
        return None

    target = picked[1]
    if target == src:
        return {
            "role": "departure",
            "edges": [],
            "segments": [],
            "segment_count": 0,
            "length_m": 0.0,
            "eta_min": 0.0,
            "from": {
                "node_id": src,
                "segment_id": dest_r.get("segment_id"),
                "label": dest_r["label"],
            },
            "to": {"node_id": target, "boundary": True},
            "note": "终点本身就在场界出口节点上，离站段为 0 m（如实空窗，不凑一段）",
        }

    # 出口路径就在上面挑出口时算出来了（同一权重、同一禁掉头口径），不重复搜索
    if not picked_path:
        return None
    edges = _dedupe_edges(list(picked_path))
    length_m = _route_length_m(graph, edges, 0.0, 0.0)
    eta_s = sum(weight(eid) for eid in edges)
    return {
        "role": "departure",
        "edges": edges,
        "segments": _edge_sections(graph, edges),
        "segment_count": len(_edge_sections(graph, edges)),
        "length_m": round(length_m, 1),
        "eta_min": round(max(0.0, eta_s) / 60.0, 2),
        "from": {
            "node_id": src,
            "segment_id": dest_r.get("segment_id"),
            "label": dest_r["label"],
        },
        "to": {"node_id": target, "boundary": True},
        "note": "离站路线：从终点所在路段驶出站区到场界出口，单独计算，不与主推荐合并",
    }


def plan(
    graph: network.Graph,
    origin: dict[str, Any],
    destination: dict[str, Any],
    *,
    params: dict[str, Any] | None = None,
    states: dict[str, dict[str, Any]] | None = None,
    points: dict[str, Any] | None = None,
    with_departure: bool = False,
    exit_node: str | None = None,
) -> dict[str, Any]:
    """给任意两个端点算 1 主 + ≤2 备选。

    `with_departure=True` 时**另外**算一条离站路线（从终点驶出站区到场界出口），
    放在 `departure` 里单独返回 —— 业主口径「离站另外计算」，不与主推荐混在一条里。
    不可达抛 `UnreachableError`（接口层转成 200 + `reachable=false`），不编造路线。
    """
    params = {**DEFAULT_PARAMS, **(params or {})}
    origin_r = resolve_endpoint(graph, origin, points)
    dest_r = resolve_endpoint(graph, destination, points)
    start = _start_from(origin_r)
    end = _end_at(dest_r)
    weight = bpr_weight(graph, states, params) if states else free_flow_weight(graph, params)
    forbid_u_turn = bool(graph.attributes.get("forbid_u_turn"))

    if start["node"] == end["node"]:
        prefix = list(start["edges"])
        suffix = list(end["edges"])
        edges = _dedupe_edges(prefix + suffix)
        paths = [edges] if edges else [[]]
        status = STATUS_SINGLE
        reason = "起点与终点在同一节点/同一段上，只有一条直连路径"
    else:
        paths = candidates.select_candidates(
            graph,
            start["node"],
            end["node"],
            int(params["k_candidates"]),
            float(params["max_path_overlap"]),
            weight,
            forbid_u_turn=forbid_u_turn,
            k_generate=K_GENERATE,
        )
        if not paths:
            raise UnreachableError(
                f"起点 {origin_r['label']} 到终点 {dest_r['label']} 在有向路网上不可达"
                "（单行 / 断头 / 片区不连通）；不编造路线"
            )
        status = STATUS_OK if len(paths) >= K_ROUTES else STATUS_PARTIAL
        if len(paths) == 1:
            # 区分「路网只有一条路径」与「候选很多但都被重叠度筛掉」——页面文案不同
            raw = candidates.k_shortest_paths(
                graph, start["node"], end["node"], 2, weight, forbid_u_turn=forbid_u_turn
            )
            status = STATUS_NO_DIVERSE if len(raw) > 1 else STATUS_SINGLE
        reason = ""

    routes: list[dict[str, Any]] = []
    base_eta: float | None = None
    base_length_m: float = 0.0
    for index, path in enumerate(paths[:K_ROUTES]):
        edges = _dedupe_edges(list(start["edges"]) + list(path) + list(end["edges"]))
        trim_head = start["m"] if edges and edges[0] == start["first_edge"] else 0.0
        trim_tail = end["m"] if edges and edges[-1] == end["last_edge"] else 0.0
        length_m = _route_length_m(graph, edges, trim_head, trim_tail)
        eta_s = sum(weight(eid) for eid in edges)
        if edges and start["edges"] and edges[0] == start["first_edge"]:
            eta_s -= weight(start["first_edge"]) * (start["m"] / max(1e-6, float(graph.edge(start["first_edge"]).get("length_m") or 1.0)))
        if edges and end["edges"] and edges[-1] == end["last_edge"]:
            eta_s -= weight(end["last_edge"]) * (1.0 - end["m"] / max(1e-6, float(graph.edge(end["last_edge"]).get("length_m") or 1.0)))
        eta_min = max(0.0, eta_s) / 60.0
        if base_eta is None:
            base_eta = eta_min
            base_length_m = length_m
        route = {
            "path_id": f"OD-C-{index + 1:02d}",
            # 页面直接按 role 标「主推荐 / 备用1 / 备用2」（契约外的前端展示字段）
            "role": "primary" if index == 0 else f"alt{index}",
            "is_recommended": index == 0,
            "edges": edges,
            "segments": _edge_sections(graph, edges),
            "segment_count": len(_edge_sections(graph, edges)),
            "length_m": round(length_m, 1),
            "eta_min": round(eta_min, 2),
            "reason": "主推荐（自由流代价最小）"
            if index == 0
            else _route_reason(
                graph,
                paths[0],
                path,
                eta_min,
                base_eta or eta_min,
                base_length_m or length_m,
                length_m,
            ),
        }
        routes.append(route)

    if status == STATUS_NO_DIVERSE:
        reason = (
            f"该 OD 在路网上只有 {len(paths)} 条可行路径"
            f"（候选池 {K_GENERATE} 条，其余与推荐路线重叠度 > {params['max_path_overlap']}）"
            if paths
            else "无可行路径"
        )
    elif status == STATUS_SINGLE and len(paths) == 1 and start["node"] != end["node"]:
        reason = "候选池里只有一条路径能走通（拓扑限制）"

    departure: dict[str, Any] | None = None
    departure_note = ""
    if with_departure:
        departure = plan_departure(
            graph,
            destination,
            params=params,
            states=states,
            points=points,
            exit_node=exit_node,
        )
        if departure is None:
            departure_note = (
                "离站路线未计算：终点到场界出口之间无可行路径（如实空窗，不凑假出口）"
            )

    return {
        "is_simulated": True,
        "site_id": (points or {}).get("site_id"),
        # 能算到路线就是 reachable；不可达在函数开头已抛 UnreachableError
        "reachable": True,
        "origin": {
            "label": origin_r["label"],
            "node_id": origin_r.get("node"),
            "segment_id": origin_r.get("segment_id"),
            "offset_m": origin_r.get("offset_m"),
            "direction": origin_r.get("direction"),
            "snap": origin_r["snap"],
        },
        "destination": {
            "label": dest_r["label"],
            "node_id": dest_r.get("node"),
            "segment_id": dest_r.get("segment_id"),
            "offset_m": dest_r.get("offset_m"),
            "direction": dest_r.get("direction"),
            "snap": dest_r["snap"],
        },
        "routes": routes,
        "route_count": len(routes),
        "alternatives_status": status,
        "reason": reason or None,
        "departure": departure,
        "departure_note": departure_note or None,
        "params": {
            "k_candidates": int(params["k_candidates"]),
            "k_generate": K_GENERATE,
            "max_path_overlap": float(params["max_path_overlap"]),
            # 重叠度按**全长**共线比例（业主 2026-10-28 裁定：不去公共首尾，不绕门槛）
            "overlap_panel": "full_path",
            "weight": "bpr" if states else "free_flow",
        },
        "note": "演示数据（模拟）：点位与路网来自站点包 / OSM，未现场踏勘；ETA 为模型值，不是实测。",
    }
