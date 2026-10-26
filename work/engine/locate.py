"""定位与地图匹配(work/engine/README.md 第三节;分工表 §8.2 的 **W4**)。

两期用**同一个函数形状**,一期只换输入:

    locate(session_id, position, heading, ts) -> {
        segment_id, offset_m, direction, route_progress, match_confidence
    }

| 项 | 一期(当前) | 二期 |
|---|---|---|
| 输入 | 孪生真值(TraCI:所在路段 / 车道 / 距路段起点多少米) | App 定位(北斗 / GNSS),进围栏后每 5–10 s 上报 |
| 算法 | 真值直读,`match_confidence = 1.0` | 隐马尔可夫地图匹配(HMM) |
| 低置信度 | 不适用 | `match_confidence < 0.6` 时不用于重新规划,提示"定位不稳定" |

⚠️ **本文件是 W0 骨架,函数边界先定、实现待 W4**(一期要为二期做的准备:用孪生真值加
   σ = 10–30 m 噪声生成假定位,提前把地图匹配模块测出来 —— TC-18)。

隐私口径(硬):`session_id` 是**匿名会话号**,不含身份;行程结束即删;不与摄像头 /
虚拟检测器数据关联;用户拒绝定位时降级为"手动选所在道路 / 只看路况",流程不中断。

用法:由 run.py 调用,不单独执行。**T4 未接入 run.py 主链** —— 匹配器由
`locate_check.py` 单独驱动(TC-18 证据),`locate()` 的一期直读路径与主链解耦。
"""

from __future__ import annotations

import math
import random
from typing import Any, Sequence

import network

#: 低于此值不用于重新规划(契约第二节 location.match_confidence)【待标定】
MATCH_CONFIDENCE_MIN = 0.6

#: 位置来源(封闭取值;一期 twin,二期 app_gnss)
LOCATION_SOURCES = ("twin", "app_gnss")

#: WGS-84 一度纬度对应的米数 —— 与任务卡 §3 的噪声公式同一个常量
METERS_PER_DEG_LAT = 111320.0

#: 八方位罗盘(取值与 stations/points.json 的 `direction` 一致)
_COMPASS_POINTS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")

#: 匹配器发射分布的宽度(米)。**固定常量,不随被测 σ 变化** —— 否则"知道噪声多大"
#: 本身就成了提示,测出来的正确率会虚高(任务卡 §4 的打分只列距离/航向/连续性)。
EMISSION_SIGMA_M = 20.0

#: 起点前看窗口的点数(结构参数,非打分常量):起点没有 previous 上下文,平行路单点
#: 易错;用前 K 个点**联合打分**选第一条边(K 点同边转移免罚),是 Viterbi 起点惯例。
#: 取 3 = 「本点 + 下两点」:足够分辨 13.8 m 间距的平行通道,又不至于在轨迹本身
#: 换段的场景里把窗口拉得过长(窗口内换段时联合得分自然低,退化为单点贪心)。
LOOKAHEAD_POINTS = 3

#: 航向发射分布的宽度(度)。点没有 heading 时该项整个跳过。
EMISSION_HEADING_SIGMA_DEG = 45.0

#: 状态转移的备选惩罚:非"停留 / 下游"的转移按 1/TRANSITION_ALT 折损。
#: 取 0.2 → 换边要额外付出约 1.6 个对数单位,足以压住噪声、又不至于永远切不过去。
TRANSITION_ALT = 0.2

#: `route_progress` 超出 [0, 1] 时的门控理由(输入 offset 与图长不一致,不裁剪、不编)
PROGRESS_OUT_OF_RANGE = "offset_m_out_of_segment_length"


# --------------------------------------------------------------------- 坐标系


def to_wgs84(lon: float, lat: float, source_crs: str) -> tuple[float, float]:
    """坐标系互转:站点包统一存 WGS-84;高德 GCJ-02、百度 BD-09 的互转**离线内置**。

    一期只认 WGS-84:原样返回。其余 CRS **抛 NotImplementedError 并说明"二期实现"** ——
    三套坐标系并存,这一步错了后面全错(位置会整体偏几十到几百米),所以**不写未验证的
    转换公式**(任务卡 §6)。
    """
    if str(source_crs) == "WGS-84":
        return float(lon), float(lat)
    raise NotImplementedError(
        f"source_crs={source_crs!r} → WGS-84 的互转属二期实现(GCJ-02 / BD-09 离线内置);"
        "一期不写未验证的转换公式,调用方应先把坐标转到 WGS-84 再进本模块"
    )


def _cos_lat(lat: float) -> float:
    """cos(lat),极区退化时给 0(调用方据此跳过 dlon,不给天文数字)。"""
    value = math.cos(math.radians(float(lat)))
    return value if abs(value) > 1e-9 else 0.0


def lonlat_to_local(
    lon: float, lat: float, anchor_lon: float, anchor_lat: float
) -> tuple[float, float]:
    """WGS-84 → 局部米制平面(x 东 / y 北),锚点由**数据给出**,不写死。

    这是任务卡 §3 噪声公式(`dlat = dy/111320`、`dlon = dx/(111320*cos(lat))`)的
    **严格逆运算**,所以加噪再投影回同一锚点是无损的。锚点必须来自输入数据
    (例如 `network_junction.json` 的 `params.anchor_lonlat`);**取不到锚点就不转**,
    由调用方按"无法建立坐标系"降级,不猜一个原点。
    """
    cos_lat = _cos_lat(anchor_lat)
    east = (float(lon) - float(anchor_lon)) * METERS_PER_DEG_LAT * cos_lat
    north = (float(lat) - float(anchor_lat)) * METERS_PER_DEG_LAT
    return east, north


def local_to_lonlat(
    east: float, north: float, anchor_lon: float, anchor_lat: float
) -> tuple[float, float]:
    """局部米制平面 → WGS-84,`lonlat_to_local` 的严格互逆(供反算/留痕)。"""
    cos_lat = _cos_lat(anchor_lat)
    lon = float(anchor_lon) + (east / (METERS_PER_DEG_LAT * cos_lat) if cos_lat else 0.0)
    lat = float(anchor_lat) + north / METERS_PER_DEG_LAT
    return lon, lat


def bearing_deg(ax: float, ay: float, bx: float, by: float) -> float:
    """方位角:0 = 正北,顺时针递增(局部平面里 x 东 / y 北)。"""
    return math.degrees(math.atan2(bx - ax, by - ay)) % 360.0


def heading_diff_deg(a: float, b: float) -> float:
    """两个方位角的较小夹角(0~180)。"""
    delta = abs((float(a) - float(b)) % 360.0)
    return min(delta, 360.0 - delta)


def compass_of(bearing: float) -> str:
    """方位角 → 八方位罗盘字母。"""
    index = int((float(bearing) + 22.5) // 45.0) % 8
    return _COMPASS_POINTS[index]


# --------------------------------------------------------------------- 一期:真值直读


def locate(
    session_id: str,
    position: dict[str, Any],
    heading: float | None,
    ts: str,
    graph: network.Graph | None = None,
) -> dict[str, Any]:
    """返回 `{segment_id, offset_m, direction, route_progress, match_confidence}`。

    一期**真值直读**:`position` 就是孪生真值(`segment_id` / `offset_m`),所以
    `match_confidence = 1.0`,不做任何匹配。二期把 `position` 换成 App 定位、
    内部改走 `match_sequence()` 的 HMM-lite,**函数形状不变**。

    - `route_progress = offset_m / 路段长度`,路段长度取**统一图**(同一 `section` 下
      所有边 `length_m` 之和);图没给或长度非正 → `null`,**不编**;
    - `direction` 优先用传入的 `heading`(度,0 = 正北),没有则用统一图里该路段的
      几何方位(节点 x/y 推),再没有 → `null`。输出八方位罗盘字母;
    - **不返回身份信息**:只按匿名 `session_id` 算,不回带 `vehicle_id` 之类。

    降级路径(缺 `segment_id` / 缺 `offset_m`):`match_confidence = 0.0` 并带
    `gate_reason` 说明缺什么 —— 一律降级留痕,不猜路段(任务卡铁律 5)。
    """
    segment_id = position.get("segment_id")
    offset_m = position.get("offset_m")

    if segment_id is None:
        return {
            "segment_id": None,
            "offset_m": None,
            "direction": None,
            "route_progress": None,
            "match_confidence": 0.0,
            "gate_reason": "truth_missing_segment_id",
        }
    if offset_m is None:
        return {
            "segment_id": str(segment_id),
            "offset_m": None,
            "direction": None,
            "route_progress": None,
            "match_confidence": 0.0,
            "gate_reason": "truth_missing_offset_m",
        }

    segment_id = str(segment_id)
    offset_value = float(offset_m)
    length_m = _segment_length_m(graph, segment_id)

    route_progress: float | None = None
    gate_reason: str | None = None
    if length_m is None or length_m <= 0:
        gate_reason = "segment_length_unavailable"
    else:
        route_progress = offset_value / length_m
        if route_progress < 0.0 or route_progress > 1.0:
            # 输入 offset 与图长不一致(样例数据里就有 offset 300 落在 150 m 段上)。
            # **不裁剪成 1.0** —— 那是改数据;如实给出比值并留门控理由。
            gate_reason = PROGRESS_OUT_OF_RANGE

    return {
        "segment_id": segment_id,
        "offset_m": offset_value,
        "direction": _direction_of(graph, segment_id, heading),
        "route_progress": route_progress,
        "match_confidence": 1.0,
        "gate_reason": gate_reason,
    }


def _segment_edges(graph: network.Graph | None, segment_id: str) -> list[str]:
    """统一图里属于同一 `section`(= segment_id)的边 id,按 id 排序保证确定性。"""
    if graph is None:
        return []
    return sorted(
        edge_id
        for edge_id in graph._edges  # noqa: SLF001 —— Graph 没有公开的"全部边"遍历口
        if str(graph.edge(edge_id).get("section")) == segment_id
    )


def _segment_length_m(graph: network.Graph | None, segment_id: str) -> float | None:
    """路段长度 = 同一 `section` 下所有边 `length_m` 之和;取不到给 `None`。"""
    total = 0.0
    found = False
    for edge_id in _segment_edges(graph, segment_id):
        length = graph.edge(edge_id).get("length_m")  # type: ignore[union-attr]
        if length is None:
            continue
        total += float(length)
        found = True
    return total if found else None


def _direction_of(
    graph: network.Graph | None, segment_id: str, heading: float | None
) -> str | None:
    """行驶方向:优先 `heading`,其次由图几何推,再没有给 `None`(不编)。"""
    if heading is not None:
        return compass_of(heading)
    if graph is None:
        return None
    bearings: list[float] = []
    for edge_id in _segment_edges(graph, segment_id):
        edge = graph.edge(edge_id)
        tail = _node_xy(graph, edge["from"])
        head = _node_xy(graph, edge["to"])
        if tail is None or head is None:
            continue
        bearings.append(bearing_deg(*tail, *head))
    if not bearings:
        return None
    # 多条边同 section 时取向量平均方位(避免 350° 与 10° 平均成 180°)
    sx = sum(math.sin(math.radians(b)) for b in bearings)
    sy = sum(math.cos(math.radians(b)) for b in bearings)
    if abs(sx) < 1e-12 and abs(sy) < 1e-12:
        return None
    return compass_of(math.degrees(math.atan2(sx, sy)) % 360.0)


def _node_xy(graph: network.Graph, node_id: str) -> tuple[float, float] | None:
    """节点平面坐标(米);只有 x/y 的图才给,否则 `None`。"""
    node = graph.node(str(node_id))
    if node.get("x") is None or node.get("y") is None:
        return None
    return float(node["x"]), float(node["y"])


# --------------------------------------------------------------------- 一期:噪声假定位


def add_gnss_noise(
    position: dict[str, Any], sigma_m: float, seed: int
) -> dict[str, Any]:
    """对孪生真值加 σ 米高斯噪声,生成假定位(一期为二期做的准备,TC-18 第②项)。

    - **固定种子** `random.Random(seed)`,同一 (position, σ, seed) 结果逐字节可复现;
    - σ 米 → 经纬度偏移:`dlat = dy/111320`、`dlon = dx/(111320*cos(lat))`
      (与 `lonlat_to_local` 严格互逆,所以投影回局部平面后偏移正好是 σ 米量级);
    - **保留原字段,只改 `lon` / `lat`** —— `segment_id` / `offset_m` / `heading`
      等一律原样带回,匹配器**不得**把它们当真值读(见 `locate_check.py` 的协议);
    - 极区 `cos(lat) → 0` 时 `dlon` 会爆炸:按退化处理(只给 `dlat`),不给天文数字。
    """
    sigma = float(sigma_m)
    if sigma < 0:
        raise ValueError(f"sigma_m 不能为负:{sigma_m!r}")
    lon = position.get("lon")
    lat = position.get("lat")
    if lon is None or lat is None:
        raise KeyError("position 缺 lon / lat —— 孪生真值必须是 WGS-84(契约第四节)")

    rng = random.Random(seed)
    dx = rng.gauss(0.0, sigma)
    dy = rng.gauss(0.0, sigma)
    cos_lat = _cos_lat(lat)

    noisy = dict(position)
    noisy["lon"] = float(lon) + (dx / (METERS_PER_DEG_LAT * cos_lat) if cos_lat else 0.0)
    noisy["lat"] = float(lat) + dy / METERS_PER_DEG_LAT
    return noisy


# --------------------------------------------------------------------- 二期:HMM-lite 匹配器


class EdgeGeometry:
    """一条边的可匹配几何:局部平面折线 + 拓扑 + 长度。

    `points` 一律是**局部米制平面**坐标(匹配在这种平面里算距离,σ 才是米)。
    经纬度折线由 `build_geometry()` 负责投影进来;投影不出来的边根本不进候选集
    (任务卡:图没有几何、无法算距离 → 停,不编坐标)。
    """

    __slots__ = ("edge_id", "section", "from_node", "to_node", "points", "length_m")

    def __init__(
        self,
        edge_id: str,
        section: str | None,
        from_node: str | None,
        to_node: str | None,
        points: list[tuple[float, float]],
        length_m: float | None,
    ) -> None:
        self.edge_id = edge_id
        self.section = section
        self.from_node = from_node
        self.to_node = to_node
        self.points = points
        self.length_m = length_m

    def bearing_at(self, along_m: float) -> float | None:
        """折线上里程 `along_m` 处的切线方位;折线只有一个点或长度为 0 时 `None`。"""
        if len(self.points) < 2 or not self.length_m:
            return None
        remaining = max(0.0, min(float(along_m), float(self.length_m)))
        for (ax, ay), (bx, by) in zip(self.points, self.points[1:]):
            span = math.hypot(bx - ax, by - ay)
            if span <= 0:
                continue
            if remaining <= span:
                return bearing_deg(ax, ay, bx, by)
            remaining -= span
        (ax, ay), (bx, by) = self.points[-2], self.points[-1]
        return bearing_deg(ax, ay, bx, by)


def point_segment_distance(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> tuple[float, float]:
    """点到线段的最短距离,以及投影参数 t(已夹到 [0, 1])。"""
    dx, dy = bx - ax, by - ay
    span2 = dx * dx + dy * dy
    if span2 <= 0.0:
        return math.hypot(px - ax, py - ay), 0.0
    t = ((px - ax) * dx + (py - ay) * dy) / span2
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy), t


def distance_to_polyline(
    px: float, py: float, polyline: Sequence[tuple[float, float]]
) -> tuple[float, float]:
    """点到折线的最短距离,以及投影点沿折线的累计里程(米)。"""
    best_distance = math.inf
    best_along = 0.0
    travelled = 0.0
    for (ax, ay), (bx, by) in zip(polyline, polyline[1:]):
        distance, t = point_segment_distance(px, py, ax, ay, bx, by)
        if distance < best_distance:
            best_distance = distance
            best_along = travelled + t * math.hypot(bx - ax, by - ay)
        travelled += math.hypot(bx - ax, by - ay)
    if best_distance is math.inf:  # 折线只有一个点
        (ax, ay) = polyline[0]
        return math.hypot(px - ax, py - ay), 0.0
    return best_distance, best_along


def build_geometry(payload: dict[str, Any]) -> list[EdgeGeometry]:
    """把一份带几何的网络描述转成候选边几何(局部米制平面)。

    认三种输入(按优先级):

    1. `edges[].coords` —— 经纬度折线(`work/twin/netpack/network_junction.json` 的
       形状)。必须同时给 `anchor_lonlat`(数据里记的那个锚点)才能投影;
    2. `nodes[].lon / .lat` + `edges[].from / .to` —— 经纬度节点,折线退化为
       **端点直线**(任务卡 §4:没有折线坐标就用端点直线,报告注明);
    3. `nodes[].x / .y` —— 局部米制节点,**且调用方喂进来的点也必须是同一平面**,
       否则根本对不上(见 `locate_check.py` 的帧校验)。

    没有几何的边直接**不进候选集**,不补坐标。
    """
    anchor = payload.get("anchor_lonlat")
    anchor_lon = anchor_lat = None
    if anchor:
        anchor_lon, anchor_lat = float(anchor[0]), float(anchor[1])

    nodes = {str(n.get("id")): n for n in payload.get("nodes") or []}
    edges = payload.get("edges") or []

    def to_plane(lon: float, lat: float) -> tuple[float, float]:
        if anchor_lon is None:
            raise ValueError("经纬度几何缺 anchor_lonlat,无法投影到局部平面")
        return lonlat_to_local(lon, lat, anchor_lon, anchor_lat)

    geometry: list[EdgeGeometry] = []
    for edge in edges:
        edge_id = str(edge.get("id") or edge.get("edge_id") or "")
        if not edge_id:
            continue
        # section = 统一图的「路段号」语义（locate_check 判分用它对齐 vehicles 的 segment_id）。
        # 真网 network_junction.json 的边没有 `section` 键、只有 `segment_id` —— 两者语义相同
        # （build_junction_pack.py 生成时 segment_id 就是路段号），这里取不到 section 就回退
        # segment_id，判分字段与真网结构对上；两个都没有才落 None（该边不参与判分）。
        section = edge.get("section")
        if section is None:
            section = edge.get("segment_id")
        section = str(section) if section is not None else None
        from_node = edge.get("from")
        to_node = edge.get("to")
        length_m = edge.get("length_m")

        coords = edge.get("coords")
        points: list[tuple[float, float]] = []
        if coords:
            try:
                points = [to_plane(float(c[0]), float(c[1])) for c in coords]
            except ValueError:
                points = []
        if not points and from_node is not None and to_node is not None:
            head = nodes.get(str(from_node))
            tail = nodes.get(str(to_node))
            pair = []
            for node in (head, tail):
                if node is None:
                    pair = []
                    break
                if node.get("lon") is not None and node.get("lat") is not None:
                    pair.append(to_plane(float(node["lon"]), float(node["lat"])))
                elif node.get("x") is not None and node.get("y") is not None:
                    pair.append((float(node["x"]), float(node["y"])))
                else:
                    pair = []
                    break
            points = pair
        if len(points) < 1:
            continue
        geometry.append(
            EdgeGeometry(
                edge_id=edge_id,
                section=section,
                from_node=str(from_node) if from_node is not None else None,
                to_node=str(to_node) if to_node is not None else None,
                points=points,
                length_m=float(length_m) if length_m is not None else None,
            )
        )
    return geometry


def _emission_logp(
    distance_m: float, heading: float | None, edge_bearing: float | None
) -> float:
    """发射项对数概率:距离(必给) + 航向差(点有 heading 且边有方位才算)。"""
    sigma = EMISSION_SIGMA_M
    if sigma <= 0:
        raise ValueError("EMISSION_SIGMA_M 必须为正")
    logp = -0.5 * (distance_m / sigma) ** 2
    if heading is not None and edge_bearing is not None:
        diff = heading_diff_deg(heading, edge_bearing)
        logp -= 0.5 * (diff / EMISSION_HEADING_SIGMA_DEG) ** 2
    return logp


def _transition_logp(previous: EdgeGeometry | None, candidate: EdgeGeometry) -> float:
    """转移项对数概率:停留 / 下游免费,同段折损,其余按 TRANSITION_ALT 折损。

    "路口优先保持当前路线"就落在这里 —— 留在原边不收惩罚,换边要另付代价,
    所以只有在距离/航向证据足够强时才会切过去。
    """
    if previous is None:
        return 0.0
    if previous.edge_id == candidate.edge_id:
        return 0.0
    if previous.to_node is not None and previous.to_node == candidate.from_node:
        return 0.0
    if previous.section is not None and previous.section == candidate.section:
        return math.log(TRANSITION_ALT)
    return math.log(TRANSITION_ALT)


def _sequence_emission_logp(
    edges: Sequence[EdgeGeometry],
    points: Sequence[dict[str, Any]],
) -> float:
    """一条「候选边序列」对前 K 个点的联合发射+转移得分（前看窗口用）。

    只加各点的发射项与相邻边的转移项 —— 与逐点贪心同一套打分函数，
    不引入任何新常量：窗口内「停在原边」由 transition 免罚表达。
    """
    logp = 0.0
    prev: EdgeGeometry | None = None
    for point, edge in zip(points, edges):
        distance, _ = distance_to_polyline(float(point["x"]), float(point["y"]), edge.points)
        heading = point.get("heading")
        heading = float(heading) if heading is not None else None
        logp += _emission_logp(distance, heading, edge.bearing_at(_))
        logp += _transition_logp(prev, edge)
        prev = edge
    return logp


def _seed_first_edge(
    points: Sequence[dict[str, Any]],
    geometry: Sequence[EdgeGeometry],
) -> EdgeGeometry | None:
    """前看窗口选起点边：用前 K 个点联合打分选「整窗最优」的第一条边。

    为什么需要它：起点没有 `previous` 上下文，纯靠单点距离/航向在平行路
    （如停车场两条 13.8 m 间距的通道）上必然有一半概率选错，之后贪心链被
    带偏整条。给前 K 点联合打分 = 用「接下来几个点也贴着它走」的证据定起点，
    这是 Viterbi 的惯例起点处理（前几步延迟决策），**不是调参**：
    打分函数与常量原封未动。
    """
    K = LOOKAHEAD_POINTS
    if K <= 1 or len(points) == 0:
        return None
    window = list(points[:K])
    if len(window) < 2:
        return None
    best: EdgeGeometry | None = None
    best_logp = -math.inf
    for edge in geometry:
        # 起点候选：整窗都贴同一条边的得分（K 点同边转移免罚）
        logp = _sequence_emission_logp([edge] * len(window), window)
        if logp > best_logp:
            best, best_logp = edge, logp
    return best


def match_sequence(
    points: Sequence[dict[str, Any]],
    geometry: Sequence[EdgeGeometry],
    *,
    first_edge_id: str | None = None,
) -> list[dict[str, Any]]:
    """HMM-lite:把一个点串顺序吸附到 `geometry`(逐点贪心 + 上一时刻转移先验,无 Viterbi 回溯;只用标准库)。

    每个点给 `{x, y, heading?}`(局部米制平面)。返回与点串等长的结果列表:

        {edge_id, section, offset_m, distance_m, score, match_confidence, previous_edge_id}

    - 打分 = 距离 + 航向差 + **上一时刻匹配段连续性**(同段 / 下游边加分);
    - **起点前看窗口**:第一条边用前 `LOOKAHEAD_POINTS` 个点联合打分选定
      (起点没有 previous 上下文,平行路单点易错;详见 `_seed_first_edge`);
    - **低分不丢弃**:只把 `match_confidence` 压下去(指数衰减后夹到 [0, 1]),
      由上游按 `MATCH_CONFIDENCE_MIN` 决定要不要用;
    - 不读任何真值字段 —— 点串里除了 x/y/heading 以外的键一律忽略。

    候选集为空时**不猜**:整条序列按"无几何可用"降级返回,`match_confidence = 0.0`。
    """
    if not geometry:
        return [
            {
                "edge_id": None,
                "section": None,
                "offset_m": None,
                "distance_m": None,
                "score": None,
                "match_confidence": 0.0,
                "previous_edge_id": None,
                "gate_reason": "no_candidate_geometry",
            }
            for _ in points
        ]

    by_id = {edge.edge_id: edge for edge in geometry}
    previous: EdgeGeometry | None = by_id.get(str(first_edge_id)) if first_edge_id else None
    # 起点前看（调用方显式给了 first_edge_id 就尊重它,否则窗口选边）
    if previous is None:
        previous = _seed_first_edge(points, geometry)

    results: list[dict[str, Any]] = []
    for point in points:
        px = float(point["x"])
        py = float(point["y"])
        heading = point.get("heading")
        heading = float(heading) if heading is not None else None

        best: EdgeGeometry | None = None
        best_logp = -math.inf
        best_distance = math.inf
        best_along = 0.0
        for edge in geometry:
            distance, along = distance_to_polyline(px, py, edge.points)
            logp = _emission_logp(distance, heading, edge.bearing_at(along))
            logp += _transition_logp(previous, edge)
            if logp > best_logp:
                best, best_logp = edge, logp
                best_distance, best_along = distance, along

        if best is None:  # geometry 非空时不会走到;真为空就降级,不返回半成品
            results.append(
                {
                    "edge_id": None,
                    "section": None,
                    "offset_m": None,
                    "distance_m": None,
                    "score": None,
                    "match_confidence": 0.0,
                    "previous_edge_id": previous.edge_id if previous else None,
                    "gate_reason": "no_candidate_geometry",
                }
            )
            continue
        score = -best_logp
        confidence = math.exp(-0.5 * (best_distance / EMISSION_SIGMA_M) ** 2)
        confidence = max(0.0, min(1.0, confidence))

        results.append(
            {
                "edge_id": best.edge_id,
                "section": best.section,
                "offset_m": round(best_along, 3),
                "distance_m": round(best_distance, 3),
                "score": round(score, 6),
                "match_confidence": round(confidence, 6),
                "previous_edge_id": previous.edge_id if previous else None,
                "gate_reason": None,
            }
        )
        previous = best
    return results


def match_point(
    point: dict[str, Any],
    geometry: Sequence[EdgeGeometry],
    *,
    previous: EdgeGeometry | None = None,
) -> dict[str, Any]:
    """单点匹配(不带上文连续性)。`match_sequence` 的内部步骤,单独暴露便于调试。"""
    return _match_single(point, geometry, previous)


def _match_single(
    point: dict[str, Any],
    geometry: Sequence[EdgeGeometry],
    previous: EdgeGeometry | None,
) -> dict[str, Any]:
    if not geometry:
        return {
            "edge_id": None,
            "section": None,
            "offset_m": None,
            "distance_m": None,
            "score": None,
            "match_confidence": 0.0,
            "previous_edge_id": previous.edge_id if previous else None,
            "gate_reason": "no_candidate_geometry",
        }
    px = float(point["x"])
    py = float(point["y"])
    heading = point.get("heading")
    heading = float(heading) if heading is not None else None

    best: EdgeGeometry | None = None
    best_logp = -math.inf
    best_distance = math.inf
    best_along = 0.0
    for edge in geometry:
        distance, along = distance_to_polyline(px, py, edge.points)
        logp = _emission_logp(distance, heading, edge.bearing_at(along))
        logp += _transition_logp(previous, edge)
        if logp > best_logp:
            best, best_logp = edge, logp
            best_distance, best_along = distance, along

    if best is None:  # geometry 非空时不会走到;真为空就降级,不返回半成品
        return {
            "edge_id": None,
            "section": None,
            "offset_m": None,
            "distance_m": None,
            "score": None,
            "match_confidence": 0.0,
            "previous_edge_id": previous.edge_id if previous else None,
            "gate_reason": "no_candidate_geometry",
        }
    confidence = max(0.0, min(1.0, math.exp(-0.5 * (best_distance / EMISSION_SIGMA_M) ** 2)))
    return {
        "edge_id": best.edge_id,
        "section": best.section,
        "offset_m": round(best_along, 3),
        "distance_m": round(best_distance, 3),
        "score": round(-best_logp, 6),
        "match_confidence": round(confidence, 6),
        "previous_edge_id": previous.edge_id if previous else None,
        "gate_reason": None,
    }
