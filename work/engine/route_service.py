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


# ---------------------------------------------------------------- 方向口径（★ 2026-10-29 统一）
#: ## 为什么需要这一层
#: 真网 61 段里有 14 条 `direction="reverse"`（另有全部 33 条双向段的 `_rev` 遍历边）：
#: `realnet_topology.traversal_specs()`（`work/engine/realnet_topology.py:174-216`）按**行进方向**
#: 重建 `from` / `to`——`direction=="reverse"` 的段，遍历边 `from=几何 to`、`to=几何 from`，
#: **但 `coords` 原样透传**（仍与几何 from/to 同序）。于是对反向段：
#: `edge["from"]` 的坐标 == `coords[-1]`，`edge["to"]` 的坐标 == `coords[0]`。
#:
#: ## twin 真值是哪个口径：**coords 顺序**（不是行进方向）
#: 取三条可复现证据（写在这里，脚本侧同一套断言见
#: `work/engine/tools/audit_segment_direction.py --prove-offset`）：
#:
#: 1. **孪生真值**：`work/twin/loop.py:1066-1071` —— SUMO 的 `getLanePosition()` 从**车道起点**
#:    （= 遍历边 `from`）量起，反向补边时显式换算回**原段起点**：
#:    `offset_m = length_m - getLanePosition()`（该行注释原文「反向补边：换算回原段起点起算的里程」）。
#:    即孪生输出的 `offset_m` 一律从 `coords[0]`（几何 from）量起 ⇒ **coords 顺序**。契约端点
#:    `/api/traffic/locate`（`work/assembly/traffic.py:3528`）把这个值原样透出，前端
#:    `DashboardView.pointAtOffset(coords, offset_m)` 也是沿 `coords` 顺序插值 ⇒ 端到端已经是
#:    coords 顺序，改成行进口径会打断业主契约链路。
#: 1b. **SUMO 车道 shape 就是 `coords` 顺序**（上一条的前提，`work/twin/sumonet.py`）：
#:    `:344` 建正向边 `shape = _edge_shape_xy(edge, proj, reverse=False)`（该函数 `:285-287`
#:    只把 `edge["coords"]` 顺序投影，`reverse=True` 才倒序）；`:348-355` 该边
#:    `from=edge["from"]`、`to=edge["to"]`；`:358-364` `edge_meta` 里 `"direction": "forward"`。
#:    **它不看 `oneway`**：像 SZ-004 这种 `oneway="-1"` / `direction="reverse"` 的段，twin 照样按
#:    `coords` 正序建一条 forward 边（单行语义只活在 enriched 字段里，`sumonet.py:374-376` 因此也
#:    不补 `_rev` 边）⇒ `getLanePosition()` 的零点只能是 `coords[0]`。实测 61/61 段，SUMO 边 shape
#:    首点到 `from` 节点坐标偏差 **0.000000 m**（`audit_segment_direction.py --prove-offset` 的
#:    `sumo_edge_shape` 段，逐段现场调用 `sumonet` 复算）。
#: 2. **点位注册表**：`scripts/gen_station_points.py:202` 的 `project_on_polyline((lon,lat), coords, length)`
#:    拿的是**原序 `coords`** 算弧长（该函数 docstring 第 193 行写「从行进方向的起点算」与实际代码
#:    矛盾，真正落盘的是 coords 顺序）。实测 `stations/guangzhounan.points.json` 的唯一一条落在
#:    反向段中段的点 `GZ-ZONE-03`：`offset_m=288.2`，按 coords 序算得 288.2 m、按行进序算得 15.2 m
#:    ⇒ 实测吻合 coords 序。
#: 3. **业主 bug 复现**：`SZ-004`（from=N-022 / to=N-040 / direction=reverse，
#:    `coords[0]`=N-022 … `coords[-1]`=N-040）。真值 `offset_m=0` 时车在 `coords[0]`=N-022；
#:    修复前 `_start_from()` 按行进序把 0 读成「行进起点」= `edge["from"]`=N-040（段末尾），
#:    于是行程从 `coords` 末点出发、还把整段当成「还没走过的前缀」画进行程；前端按真值把起点
#:    标在 `coords[0]`（正确），落点就正好在这条画出来的线的**尾巴**上 —— 与前端标记相差整段
#:    120.7 m，这就是业主看到的「起点标在 SZ-004 段末尾」。
#:
#: ## 结论与不变式
#: - **对外一律 coords 顺序**：`offset_m` = 从 `coords[0]`（几何 `from`）起算的米数。快照、注册表、
#:   前端、契约 `location.offset_m` 全部不动。
#: - **对内一律行进顺序**：`_start_from()` / `_end_at()` 只吃 `offset_travel_m`，由本层换算，
#:   反向段 `offset_travel_m = length_m - offset_m`（两侧同一公式，互为反函数）。
#: - 因此页面/接口给的 `offset_m` 与 `origin.offset_m` 回显可以**原样回灌**，不丢方向、不镜像。
def segment_direction(edge: dict[str, Any]) -> str:
    """遍历边相对 `coords` 顺序的行进方向：`"forward"`（同序）/ `"reverse"`（反序）。

    取值只有这两个（`realnet_topology.traversal_specs()` 给每条遍历边定的就是二者之一）；
    样例网老边没有 `direction` 字段时按同序处理，不猜。
    """
    return "reverse" if str(edge.get("direction") or "").strip().lower() == "reverse" else "forward"


def coords_offset_to_travel(edge: dict[str, Any], offset_m: float) -> float:
    """`coords` 顺序里程 → 行进顺序里程（反向段翻转，正反同式，互为反函数）。"""
    length = float(edge.get("length_m") or 0.0)
    offset = max(0.0, min(length, float(offset_m)))
    return length - offset if segment_direction(edge) == "reverse" else offset


def travel_offset_to_coords(edge: dict[str, Any], offset_m: float) -> float:
    """行进顺序里程 → `coords` 顺序里程（与 `coords_offset_to_travel` 同式互逆）。"""
    return coords_offset_to_travel(edge, offset_m)


def edge_geometry_travel(edge: dict[str, Any]) -> list[list[float]]:
    """该遍历边的几何，**按行进顺序**排列（反向段取 `coords` 的逆序）。

    返回的首点等于 `from` 节点坐标、末点等于 `to` 节点坐标（真网 61 段实测误差 < 1e-6 m，
    由 `work/engine/tools/audit_segment_direction.py` 逐段断言）。
    """
    coords = [[float(point[0]), float(point[1])] for point in (edge.get("coords") or []) if len(point) >= 2]
    return list(reversed(coords)) if segment_direction(edge) == "reverse" else coords


def point_at_travel_offset(edge: dict[str, Any], offset_m: float) -> tuple[float | None, float | None]:
    """沿**行进顺序**几何取 `offset_m` 处的坐标（线性插值，缺几何返回 `(None, None)`）。

    与前端 `pointAtOffset(coords, offset)` 同一套等距圆柱近似，保证两侧插值结果同源可比。
    """
    geometry = edge_geometry_travel(edge)
    if len(geometry) < 2:
        return (None, None)
    length = float(edge.get("length_m") or 0.0)
    if length <= 0:
        return (geometry[0][0], geometry[0][1])
    target = max(0.0, min(length, float(offset_m)))
    lon0, lat0 = geometry[0]
    pieces = [
        math.hypot(*_local_xy(geometry[i + 1][0], geometry[i + 1][1], geometry[i][0], geometry[i][1]))
        for i in range(len(geometry) - 1)
    ]
    total = sum(pieces)
    if total <= 0:
        return (geometry[0][0], geometry[0][1])
    remaining = target * total / length  # 名义里程 → 几何弧长（同一比例，几何即真值）
    for index, piece in enumerate(pieces):
        if remaining <= piece or index == len(pieces) - 1:
            ratio = 0.0 if piece <= 0 else max(0.0, min(1.0, remaining / piece))
            start, end = geometry[index], geometry[index + 1]
            return (
                round(start[0] + ratio * (end[0] - start[0]), 7),
                round(start[1] + ratio * (end[1] - start[1]), 7),
            )
        remaining -= piece
    return (geometry[-1][0], geometry[-1][1])


def route_steps(
    graph: network.Graph,
    edge_ids: list[str],
    *,
    trim_head_m: float = 0.0,
    trim_tail_m: float = 0.0,
) -> list[dict[str, Any]]:
    """一条路线的**逐段几何**：`geometry` 已按行进顺序，前端不许再猜方向。

    契约（方案 §2 规则 1/3）：`geometry` 首点 == `from_node` 坐标、末点 == `to_node` 坐标；
    相邻 `steps[i].to_node == steps[i+1].from_node`。**几何给整段不裁**（首末点必须落在节点上），
    起终点在段中时用 `trim_head_m` / `trim_tail_m` 告诉前端这两端各有多少米不该画。

    `trim_head_m` / `trim_tail_m` 的**量法跟着 `geometry` 走，一律行进顺序**：
    `trim_head_m` 从 `geometry[0]` 沿行进方向量（= 位置的行进里程 `offset_travel_m`），
    `trim_tail_m` 从 `geometry[-1]` 往回量（= `length_m - offset_travel_m`）。
    反向段上 `offset_m` 与 `offset_travel_m` 互补，**把 coords 口径的 `offset_m` 当裁剪量就会整段裁反**
    （dev-B / 队长 2026-10-29 实测：SZ-004 `offset_m=10` 时起点标记离裁后首点 100.8 m）；
    audit H 项（`work/engine/tools/audit_segment_direction.py`）就是钉这条的守卫。
    """
    steps: list[dict[str, Any]] = []
    for edge_id in edge_ids:
        edge = graph.edge(edge_id)
        steps.append(
            {
                "segment_id": str(edge.get("section") or edge_id),
                "edge_id": str(edge_id),
                "direction": segment_direction(edge),
                "from_node": str(edge.get("from")),
                "to_node": str(edge.get("to")),
                "length_m": round(float(edge.get("length_m") or 0.0), 1),
                "geometry": edge_geometry_travel(edge),
                "trim_head_m": 0.0,
                "trim_tail_m": 0.0,
            }
        )
    if steps:
        steps[0]["trim_head_m"] = round(float(trim_head_m), 1)
        steps[-1]["trim_tail_m"] = round(float(trim_tail_m), 1)
    return steps


def start_point_of(graph: network.Graph, origin: dict[str, Any]) -> dict[str, Any]:
    """把起点端点折算成**真实位置**（方案 §2 `start_point`），按行进口径定位。

    `offset_m` 仍是 coords 顺序（与页面/快照/注册表同口径，可原样回灌），
    另给 `offset_travel_m` 说明它在行进顺序上的位置；`lon`/`lat` 就是真值点，
    前端直接画标记即可，不必自己折 `offset_m`。
    """
    if origin.get("kind") == "node":
        node = graph.node(origin["node"])
        return {
            "node_id": str(origin["node"]),
            "segment_id": origin.get("segment_id"),
            "edge_id": None,
            "offset_m": 0.0,
            "offset_travel_m": 0.0,
            "direction": None,
            "lon": node.get("lon"),
            "lat": node.get("lat"),
        }
    edge = origin["edge"]
    edge_id = str(edge.get("id"))
    travel_m = float(origin.get("offset_travel_m") or 0.0)
    lon, lat = point_at_travel_offset(edge, travel_m)
    return {
        # 位置派生：`offset_travel_m≈length` 的起点（反向段 `offset_m=0` 就是这种）回显行进**终点**节点，
        # 与 `lon/lat` 同一处；改造前恒回显 `edge["from"]`，于是坐标在段尾、节点说段头，业主看到的镜像即此。
        "node_id": travel_anchor_node(edge, travel_m),
        "segment_id": str(edge.get("section") or edge_id),
        "edge_id": edge_id,
        "offset_m": round(float(origin.get("offset_m") or 0.0), 1),
        "offset_travel_m": round(travel_m, 1),
        "direction": segment_direction(edge),
        "lon": lon,
        "lat": lat,
    }


def start_point_for_location(graph: network.Graph, location: dict[str, Any]) -> dict[str, Any] | None:
    """由快照 `location`（`segment_id` + `offset_m`，**coords 顺序**）算 `start_point`。

    用途：`work/engine/run.py` 给 `routes.json` 的 `arrival_route` 补 `start_point`，以及接口层
    非契约只读端点 `GET /api/traffic/route/{request_id}/steps` 把它端给前端（大屏画起点标记）。

    刻意复用 `resolve_endpoint()` + `start_point_of()`，与 `/api/traffic/route/plan` 的
    `start_point` **同源同口径** —— 产物里不能再长出一份「自己按 offset_m 反推坐标」的实现，
    那正是这次镜像 bug 的分叉点。解析不出来就如实返回 `None`（缺字段/段不存在/无几何），
    绝不编坐标。
    """
    try:
        resolved = resolve_endpoint(graph, location)
    except (KeyError, TypeError, ValueError):
        return None
    try:
        start_point = start_point_of(graph, resolved)
    except (KeyError, TypeError, ValueError):
        return None
    if start_point.get("lon") is None or start_point.get("lat") is None:
        return None
    return start_point


def route_endpoint_points(graph: network.Graph, steps: list[dict[str, Any]]) -> dict[str, Any]:
    """由一条路线的 `steps[]`（行进顺序、已裁切）折算**两端真值标记点**。

    用途：非契约只读端点 `GET /api/traffic/route/{request_id}/steps` 给每条 route 补
    `start_point` / `destination_point`（大屏画两端标记用），字段与 `/route/plan` 逐字同构。

    刻意**只调用 `start_point_of()`**（`/route/plan` 用的同一个生成器，`route_service.py:1009` 附近），
    这里不做任何「按 `offset_m` 折 `coords`」的二次折算 —— 两份实现就是下一个镜像 bug。
    首段位置 = `trim_head_m`（从 `geometry[0]` 沿行进量到的里程），
    末段位置 = `length_m - trim_tail_m`，与 `point_at_travel_offset()` 口径一致。
    拿不到（段不在图里 / 边无几何）就如实返回 `None`，绝不编坐标。
    """
    empty: dict[str, Any] = {"start_point": None, "destination_point": None}
    if not steps:
        return empty

    def at(edge_id: str, travel_m: float) -> dict[str, Any] | None:
        try:
            edge = graph.edge(str(edge_id))
        except (KeyError, TypeError, ValueError):
            return None
        length = float(edge.get("length_m") or 0.0)
        travel = max(0.0, min(length, float(travel_m or 0.0)))
        try:
            point = start_point_of(
                graph,
                {
                    "kind": "edge",
                    "edge": edge,
                    "offset_m": travel_offset_to_coords(edge, travel),
                    "offset_travel_m": travel,
                    "segment_id": str(edge.get("section") or edge.get("id")),
                },
            )
        except (KeyError, TypeError, ValueError):
            return None
        if point.get("lon") is None or point.get("lat") is None:
            return None
        return point

    first, last = steps[0], steps[-1]
    last_edge_id = str(last.get("edge_id"))
    try:
        last_length = float(graph.edge(last_edge_id).get("length_m") or 0.0)
    except (KeyError, TypeError, ValueError):
        return empty
    return {
        "start_point": at(str(first.get("edge_id")), float(first.get("trim_head_m") or 0.0)),
        "destination_point": at(
            last_edge_id, last_length - float(last.get("trim_tail_m") or 0.0)
        ),
    }


def snap_to_segment(
    graph: network.Graph,
    lon: float,
    lat: float,
    *,
    max_distance_m: float = 60.0,
) -> dict[str, Any]:
    """任意坐标 → **最近路段 + 沿线偏移**（页面「点图选起终点」用）。

    返回 `{matched, segment_id, offset_m, offset_travel_m, length_m, distance_m, lon, lat,
    node_id, direction, direction_raw, edge_id, note}`：
    - `offset_m` 按该段 `length_m` 的比例还原，**沿 `coords` 顺序**（与快照/注册表/契约同一口径，
      可直接回灌 `{"segment_id": …, "offset_m": …}` 算路）；`offset_travel_m` 是同一位置在
      **行进顺序**上的里程，两者对 `direction=="reverse"` 的段互补（`offset_travel_m = length_m - offset_m`）；
    - `direction` 是归一后的行进方向（`forward` / `reverse`，相对 `coords` 顺序），`direction_raw`
      保留边上的原始取值；`node_id` 是**该边的行进起点**（`edge["from"]`），后端内部口径用，
      页面要画起点标记请用 `/route/plan` 的 `start_point.lon/lat`；
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
                offset_m = round(ratio * length_m, 1)
                best = {
                    "_dist": dist,
                    "distance_m": dist,
                    "offset_m": offset_m,
                    "offset_travel_m": round(coords_offset_to_travel(edge, offset_m), 1),
                    "length_m": round(length_m, 1),
                    # 投影点按经纬度线性插值回真实坐标（页面画标记用）
                    "lon": round(lon1 + t * (lon2 - lon1), 7),
                    "lat": round(lat1 + t * (lat2 - lat1), 7),
                    "segment_id": str(edge.get("section") or edge_id),
                    "direction": segment_direction(edge),
                    "direction_raw": edge.get("direction"),
                    "edge_id": str(edge_id),
                    "node_id": str(edge.get("from")),
                }
            along_m += pieces[index]
    if best is None:
        return {
            "matched": False,
            "segment_id": None,
            "offset_m": None,
            "offset_travel_m": None,
            "length_m": None,
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


def travel_anchor_node(edge: dict[str, Any], offset_travel_m: float) -> str:
    """该位置**在行进顺序上**贴着的端点节点（回显 `node_id` 用，位置派生、不改算路）。

    端点位置取真端点（`offset_travel_m≈0` → 行进起点 `from`，`≈length` → 行进终点 `to`）；
    段中位置仍回显行进起点 `from`（与改造前一致），真实位置以 `start_point.lon/lat` 为准。

    改造前这里恒取 `edge["from"]`，于是 `direction=="reverse"` 且 `offset_m=0` 的起点
    回显成行进起点、坐标却在行进终点 —— 与业主的镜像现象同源，故一并按里程取端点。
    """
    length = float(edge.get("length_m") or 0.0)
    if float(offset_travel_m) <= 0.5:
        return str(edge["from"])
    if length - float(offset_travel_m) <= 0.5:
        return str(edge["to"])
    return str(edge["from"])


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
    # 同一位置的行进顺序里程：`_start_from` / `_end_at` 只吃这个（见文件头「方向口径」）
    offset_travel = coords_offset_to_travel(edge, offset)
    node_id = spec.get("node_id") or travel_anchor_node(edge, offset_travel)
    # 由点击坐标吸附来的端点：把吸附距离 / 投影点一并回显（页面要标「吸附到哪」）
    raw_snap = spec.get("_snap") or {}
    snap = {
        "kind": "segment",
        "segment_id": str(edge.get("section")),
        "offset_m": round(offset, 1),
        "offset_travel_m": round(offset_travel, 1),
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
        "offset_travel_m": round(offset_travel, 1),
        "direction": segment_direction(edge),
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


def _no_trim() -> dict[str, float]:
    """端点正好落在节点上时的三个里程量（全 0），与 `_start_from` / `_end_at` 的字段集合保持一致。"""
    return {"trim_m": 0.0, "undriven_m": 0.0, "driven_m": 0.0}


def _start_from(origin: dict[str, Any]) -> dict[str, Any]:
    """起点 → (起始节点, 需要补在前面的边, 补的长度)。

    里程口径**只看 `offset_travel_m`**（沿该遍历边 `from → to` 量），不再读 `offset_m`：
    `offset_m` 是给页面/快照/契约的 `coords` 顺序口径，反向段上两者互补，
    拿它直接判「离行进起点多远」正是业主这个 bug 的成因。
    """
    if origin["kind"] == "node":
        return {"node": origin["node"], "edges": [], "first_edge": None, **_no_trim()}
    edge = origin["edge"]
    length = origin["length_m"]
    offset = origin.get("offset_travel_m")
    if offset is None:  # 兼容旧调用方：自己换算，不假设口径
        offset = coords_offset_to_travel(edge, origin["offset_m"])
    if offset <= 0.5:
        return {"node": str(edge["from"]), "edges": [], "first_edge": None, **_no_trim()}
    remaining = length - offset
    if remaining <= 0.5:
        # 正好落在行进终点（反向段 `offset_m=0` 就落这里）：不补零长度前缀边，
        # 否则 steps[0] 会把整段反向边画进行程、线从段尾一路画到车后面（业主看到的镜像就是这么来的）
        return {"node": str(edge["to"]), "edges": [], "first_edge": None, **_no_trim()}
    return {
        "node": str(edge["to"]),
        "edges": [str(edge["id"])],
        "first_edge": str(edge["id"]),
        # 三个量必须分清（2026-10-29 dev-B/队长实测的口径倒置 bug 就在这）：
        #   trim_m    —— 该边在**行进顺序上、车后方**还没画的那一段 = offset_travel（首段裁剪量）；
        #                 `steps[].geometry` 是行进顺序，所以裁剪量也是行进顺序，别再拿 offset_m。
        #   undriven_m—— 车**前方**还没走的里程 = length - offset_travel（算 ETA 用）。
        #   driven_m  —— 实际要走过的里程 = undriven_m，同一值，给读代码的人留个明白名。
        "trim_m": float(offset),
        "undriven_m": float(remaining),
        "driven_m": float(remaining),
    }


def _end_at(destination: dict[str, Any]) -> dict[str, Any]:
    """终点 → (结束节点, 需要补在后面的边, 补的长度)。里程口径同 `_start_from`。"""
    if destination["kind"] == "node":
        return {"node": destination["node"], "edges": [], "last_edge": None, **_no_trim()}
    edge = destination["edge"]
    length = destination["length_m"]
    offset = destination.get("offset_travel_m")
    if offset is None:
        offset = coords_offset_to_travel(edge, destination["offset_m"])
    if offset >= length - 0.5:
        return {"node": str(edge["to"]), "edges": [], "last_edge": None, **_no_trim()}
    if offset <= 0.5:
        return {"node": str(edge["from"]), "edges": [], "last_edge": None, **_no_trim()}
    remaining = length - offset
    return {
        "node": str(edge["from"]),
        "edges": [str(edge["id"])],
        "last_edge": str(edge["id"]),
        # 终点与起点**正好互为倒置**：末段裁掉的是车开过去之后剩下的尾段 = length - offset_travel；
        # ETA 要扣的「没走的那截」= offset_travel（这一段确实要开）。两个量别再混用同一个 "m"。
        "trim_m": float(remaining),
        "undriven_m": float(offset),
        "driven_m": float(offset),
    }


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
        # 离站路线从终点节点起算、不扣任何一截，路线级裁切量如实给 0（形状与主推荐 routes[] 对齐）
        "trim_head_m": 0.0,
        "trim_tail_m": 0.0,
        "eta_min": round(max(0.0, eta_s) / 60.0, 2),
        "steps": route_steps(graph, edges),
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

    返回值里两个**真值标记点**（2026-10-29 起两端对称）：
    - `start_point`：起点真实位置，字段 `{node_id, segment_id, edge_id, offset_m,
      offset_travel_m, direction, lon, lat}`；
    - `destination_point`：终点真实位置，字段与 `start_point` **逐字同构**；
    页面两端都直接用 `lon/lat` 画标记，不要自己按 `offset_m` 折坐标（那正是镜像 bug 的分叉点）。
    `routes[]` 另带路线级裁切量 `trim_head_m` / `trim_tail_m`（= 首/末段的裁切量，
    `length_m == Σsteps.length_m - trim_head_m - trim_tail_m` 自洽）。
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
        trim_head = start["trim_m"] if edges and edges[0] == start["first_edge"] else 0.0
        trim_tail = end["trim_m"] if edges and edges[-1] == end["last_edge"] else 0.0
        length_m = _route_length_m(graph, edges, trim_head, trim_tail)
        eta_s = sum(weight(eid) for eid in edges)
        # 扣掉「没画/没走」的那截（`trim_*` 就是这截，口径同 `steps[].trim_head_m` / `trim_tail_m`）。
        # 别再用 undriven_m 扣：那是车前方要走的那截，扣了就正好扣反（2026-10-29 修的口径倒置）。
        if edges and start["edges"] and edges[0] == start["first_edge"]:
            eta_s -= weight(start["first_edge"]) * (
                trim_head / max(1e-6, float(graph.edge(start["first_edge"]).get("length_m") or 1.0))
            )
        if edges and end["edges"] and edges[-1] == end["last_edge"]:
            eta_s -= weight(end["last_edge"]) * (
                trim_tail / max(1e-6, float(graph.edge(end["last_edge"]).get("length_m") or 1.0))
            )
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
            # 路线级裁切量（2026-10-29 补）：`trim_head_m` = 首段被裁掉的米数、`trim_tail_m` = 末段被裁掉的米数，
            # 与 `length_m` 自洽（`length_m == Σsteps.length_m - trim_head_m - trim_tail_m`）。
            # 前端画图取 `steps[].trim_*`（逐段），这两个是给验收/台账做**路线级**汇总断言用的，免得住外自己加。
            "trim_head_m": round(trim_head, 1),
            "trim_tail_m": round(trim_tail, 1),
            "eta_min": round(eta_min, 2),
            # 逐段几何（已按行进顺序）；前端只认 geometry + direction，不许自己折 coords
            "steps": route_steps(graph, edges, trim_head_m=trim_head, trim_tail_m=trim_tail),
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

    start_point = start_point_of(graph, origin_r)
    if start_point.get("lon") is None and routes and routes[0].get("steps"):
        # 节点端点或节点缺坐标时兜底：用第一条路线的首点（geometry 首点 == 行进起点节点）
        first = routes[0]["steps"][0]["geometry"]
        if first:
            start_point["lon"], start_point["lat"] = first[0][0], first[0][1]
            start_point["note"] = "节点无坐标，取首段几何首点"

    # 终点真实位置（与 `start_point` 完全同构，2026-10-29 补）：
    # 前端画起点有权威坐标，画终点却要自己折 `offset_m` —— 那正是刚修掉的镜像口径风险的另一半，
    # 所以终点也端真值点，两个标记走同一条 `start_point_of()`（改名不改语义：它算的是「端点 → 位置」）。
    destination_point = start_point_of(graph, dest_r)
    if destination_point.get("lon") is None and routes and routes[0].get("steps"):
        # 节点端点或节点缺坐标时兜底：用第一条路线的末点（geometry 末点 == 行进终点节点）
        last = routes[0]["steps"][-1]["geometry"]
        if last:
            destination_point["lon"], destination_point["lat"] = last[-1][0], last[-1][1]
            destination_point["note"] = "节点无坐标，取末段几何末点"

    return {
        "is_simulated": True,
        "site_id": (points or {}).get("site_id"),
        # 能算到路线就是 reachable；不可达在函数开头已抛 UnreachableError
        "reachable": True,
        # 起点真实位置（页面画标记用这个，不要用 coords[0] 折 offset_m）
        "start_point": start_point,
        # 终点真实位置（字段与 `start_point` 逐字同构，两端的标记都别自己折 offset_m）
        "destination_point": destination_point,
        "origin": {
            "label": origin_r["label"],
            "node_id": origin_r.get("node"),
            "segment_id": origin_r.get("segment_id"),
            "offset_m": origin_r.get("offset_m"),
            # 同一位置的行进顺序里程（`offset_m` 是 coords 顺序口径，反向段两者互补）
            "offset_travel_m": origin_r.get("offset_travel_m"),
            "direction": origin_r.get("direction"),
            "snap": origin_r["snap"],
        },
        "destination": {
            "label": dest_r["label"],
            "node_id": dest_r.get("node"),
            "segment_id": dest_r.get("segment_id"),
            "offset_m": dest_r.get("offset_m"),
            "offset_travel_m": dest_r.get("offset_travel_m"),
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
