"""路网模型 + 行程时间函数(工作流第 7 章 7.2 / 手册第 7 章)。

输入:stations/network.json(统一图结构 {nodes, edges, attributes});--sample 时读 samples/network_sample.json
      stations/thresholds.json 的 decision 组(alpha / beta / k_candidates / max_path_overlap)
输出:Graph 对象(内存,不落盘)
口径:引擎只认统一图结构(手册 8.2),换站只换数据不换代码 —— 本文件里**不出现任何站点名 / 坐标 / 路名**;
     行程时间一律走 BPR:`t = t0 * (1 + alpha * x ** beta)`,`x = q / c`;
     ⚠ 量纲(手册 7.6 的硬约束):`x` 本身即无量纲饱和度,惩罚项**不得再除以 c**。

用法:由 run.py 调用,不单独执行。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable

#: 统一图结构的必填字段(手册 8.2「字段名照抄」)
REQUIRED_NODE_FIELDS = ("id", "type")
REQUIRED_EDGE_FIELDS = (
    "id", "from", "to", "lanes", "length_m", "speed_limit", "capacity_vph",
)

#: 节点类型(取值封闭,手册 8.2)
NODE_TYPES = ("intersection", "dropoff", "pickup", "holding")

KMH_TO_MPS = 1.0 / 3.6


def read_json(path: Path) -> dict[str, Any]:
    """读一个 UTF-8 JSON 文件(显式编码,换机器不乱码)。"""
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def write_json(path: Path, payload: dict[str, Any]) -> int:
    """写一个 UTF-8 JSON 文件(中文不转义),返回字节数。"""
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def ensure_out_dir(path: Path) -> None:
    """先建输出目录,建完断言。

    上游实测缺陷:输出目录不存在时命令会**静默假通过**(work/assembly/现状核实.md 4.3)。
    """
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise RuntimeError(f"输出目录未能建立:{path}")


def assert_artifact(path: Path) -> int:
    """产物存在性断言,返回字节数。

    **不能只查"非空"**(现状核实.md 4.4 的 258 B 空壳 mp4),按"存在 + 能解析 + 顶层非空"三层查。
    """
    if not path.is_file():
        raise RuntimeError(f"产物不存在:{path}")
    size = path.stat().st_size
    if size <= 0:
        raise RuntimeError(f"产物为空:{path}")
    payload = read_json(path)
    if not isinstance(payload, dict) or not payload:
        raise RuntimeError(f"产物顶层为空或不是对象:{path}")
    return size


class Graph:
    """统一图结构(手册 8.2):`{nodes, edges, attributes}`。

    只管**拓扑与静态属性**;每条边的实时现状(q / v / c)由 segments 单独给,按 `section` 对齐。
    """

    def __init__(self, payload: dict[str, Any]) -> None:
        for key in ("nodes", "edges"):
            if not isinstance(payload.get(key), list) or not payload[key]:
                raise ValueError(f"统一图结构缺 {key} 数组(手册 8.2)")
        self.attributes: dict[str, Any] = dict(payload.get("attributes") or {})
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: dict[str, dict[str, Any]] = {}
        self._out: dict[str, list[str]] = {}

        for node in payload["nodes"]:
            for field in REQUIRED_NODE_FIELDS:
                if field not in node:
                    raise ValueError(f"节点 {node.get('id')!r} 缺必填字段 {field}(手册 8.2)")
            nid = str(node["id"])
            if nid in self._nodes:
                raise ValueError(f"节点 id 重复:{nid}")
            if node["type"] not in NODE_TYPES:
                raise ValueError(f"未知节点类型 {node['type']!r}(仅 {NODE_TYPES})")
            self._nodes[nid] = dict(node)

        for edge in payload["edges"]:
            for field in REQUIRED_EDGE_FIELDS:
                if field not in edge:
                    raise ValueError(f"边 {edge.get('id')!r} 缺必填字段 {field}(手册 8.2)")
            eid = str(edge["id"])
            if eid in self._edges:
                raise ValueError(f"边 id 重复:{eid}")
            for endpoint in ("from", "to"):
                if str(edge[endpoint]) not in self._nodes:
                    raise ValueError(f"边 {eid} 的 {endpoint}={edge[endpoint]!r} 不在 nodes 里")
            self._edges[eid] = dict(edge)
            self._out.setdefault(str(edge["from"]), []).append(eid)

    @property
    def node_ids(self) -> list[str]:
        return list(self._nodes)

    def node(self, node_id: str) -> dict[str, Any]:
        return self._nodes[str(node_id)]

    def edge(self, edge_id: str) -> dict[str, Any]:
        return self._edges[str(edge_id)]

    def out_edges(self, node_id: str) -> list[str]:
        """从某个节点出发的边 id 列表。"""
        return list(self._out.get(str(node_id), ()))

    def edge_ids(self) -> list[str]:
        """所有边的 id（建图顺序）。给上层做覆盖度核对用（如"路段状态是否落在这张图上"）。"""
        return list(self._edges)

    def section_ids(self) -> set[str]:
        """这张图里出现过的路段号集合（边的 `section`，与 segments 快照的 key 同一命名空间）。"""
        return {str(edge.get("section")) for edge in self._edges.values() if edge.get("section")}


def load_graph(path: Path) -> Graph:
    """读统一图结构并校验(缺字段即报错,不静默补空)。"""
    if not path.is_file():
        raise SystemExit(f"缺路网文件:{path}")
    return Graph(read_json(path))


def load_segments(path: Path) -> dict[str, dict[str, Any]]:
    """读 segments 快照,按 segment_id 建索引(引擎按 edges[].section 对齐)。"""
    if not path.is_file():
        raise SystemExit(f"缺 segments 快照:{path}")
    payload = read_json(path)
    segments = payload.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("segments 缺失或为空(契约第一节:顶层信封 + segments 数组)")
    index: dict[str, dict[str, Any]] = {}
    for seg in segments:
        sid = seg.get("segment_id")
        if not sid:
            raise ValueError("segments 里有条目缺 segment_id")
        index[str(sid)] = seg
    return index


def load_thresholds(path: Path) -> dict[str, dict[str, Any]]:
    """读站点包 thresholds.json 的两组参数。

    **本文件是"引擎真的读了站点包"的证明点** —— 参数一律从这里取,代码里不写死
    (work/engine/README.md 第七节:判级阈值不得写死在代码里,必须读站点包)。
    """
    if not path.is_file():
        raise SystemExit(f"缺站点包阈值文件:{path}")
    payload = read_json(path)
    for group in ("grading", "decision"):
        if not isinstance(payload.get(group), dict):
            raise ValueError(
                f"thresholds.json 缺 {group} 组(契约第六节:两组顶层键名 grading / decision)"
            )
    return {"grading": payload["grading"], "decision": payload["decision"]}


def free_flow_time_s(edge: dict[str, Any]) -> float:
    """自由流通行时间 t0 = 路段长度 / 限速(秒)。"""
    speed_mps = float(edge["speed_limit"]) * KMH_TO_MPS
    if speed_mps <= 0:
        raise ValueError(f"边 {edge['id']} 的 speed_limit 必须为正")
    return float(edge["length_m"]) / speed_mps


def travel_time_s(
    edge: dict[str, Any],
    segment: dict[str, Any] | None,
    params: dict[str, Any],
    extra_vph: float = 0.0,
) -> float:
    """BPR 行程时间:`t = t0 * (1 + alpha * x ** beta)`(秒)。

    - `x = (q + extra) / c`,**本身即无量纲饱和度,惩罚项不得再除以 c**(手册 7.6 量纲约束);
    - `c` 取 segments 的 `c_vph`(**因素修正后**的通行能力),缺则退回边的 `capacity_vph`;
    - `q` 取 segments 的 `q_vph`,缺按 0(下游按 0 处理并降级,契约第一节)。
    """
    alpha = float(params.get("alpha", 0.15))
    beta = float(params.get("beta", 4.0))
    t0 = free_flow_time_s(edge)

    if segment is None:
        return t0
    capacity = float(segment.get("c_vph") or edge["capacity_vph"])
    if capacity <= 0:
        return t0
    flow = float(segment.get("q_vph", 0.0)) + float(extra_vph)
    x = flow / capacity
    return t0 * (1.0 + alpha * math.pow(x, beta))


def path_travel_time_s(
    graph: Graph,
    path: list[str],
    segments: dict[str, dict[str, Any]],
    params: dict[str, Any],
    extra_vph: float = 0.0,
) -> float:
    """沿一条边序列累加 BPR 行程时间(秒)。"""
    total = 0.0
    for edge_id in path:
        edge = graph.edge(edge_id)
        segment = segments.get(str(edge.get("section") or ""))
        total += travel_time_s(edge, segment, params, extra_vph)
    return total


def path_length_m(graph: Graph, path: list[str]) -> float:
    """一条边序列的总长度(米)。"""
    return sum(float(graph.edge(eid)["length_m"]) for eid in path)


def make_weight_fn(
    graph: Graph,
    segments: dict[str, dict[str, Any]],
    params: dict[str, Any],
    extra_vph: float = 0.0,
) -> Callable[[str], float]:
    """给最短路算法用的边权重(秒)。"""
    def weight(edge_id: str) -> float:
        edge = graph.edge(edge_id)
        segment = segments.get(str(edge.get("section") or ""))
        return travel_time_s(edge, segment, params, extra_vph)

    return weight


#: 算路权重口径的两个取值(接口层 / 产物都按这两个字符串透传,别另造词)
WEIGHT_BPR = "bpr"
WEIGHT_FREE_FLOW = "free_flow"


def weight_source_of(states: dict[str, dict[str, Any]] | None) -> str:
    """这次算路实际吃的是哪套权重:`bpr`(状态里有真流量) / `free_flow`(没状态或状态全零)。

    为什么"有记录"不够、还要看 `q_vph`(2026-10-29 lead 定)：
      BPR 是 `t0·(1+α·x^β)`,而 `x = q_vph / c_vph`。记录齐全但 `q_vph` 全是 0 时
      **数值上就等于自由流**——这种时候再标 `bpr` 就是"标着吃了拥堵、其实一个车都没算",
      业主拿它去对路段热力只会对不上。所以只要没有任何一条记录的 `q_vph > 0`,
      一律如实降级成 `free_flow`(页面据此提示"按自由流计算",不装)。
      `c_vph`/`q_vph` 非数值的脏记录**跳过不抛**：标签的目的是如实描述,不是校验数据。
    """
    if not states:
        return WEIGHT_FREE_FLOW
    for record in states.values():
        if not isinstance(record, dict):
            continue
        try:
            if float(record.get("q_vph") or 0.0) > 0.0:
                return WEIGHT_BPR
        except (TypeError, ValueError):
            continue
    return WEIGHT_FREE_FLOW


def weight_fn(
    graph: Graph,
    states: dict[str, dict[str, Any]] | None,
    params: dict[str, Any],
    extra_vph: float = 0.0,
) -> Callable[[str], float]:
    """**算路唯一入口**的边权重(秒):`states` 为空 → 自由流;有 `states` → BPR。

    口径:
      - `states` 按 **`segment_id`** 建索引(引擎按边的 `edges[].section` 对齐),record 里只需
        `q_vph` / `c_vph` —— `x` 一律由 `travel_time_s` **现算**
        (`x = (q_vph + extra_vph) / c_vph`),不吃上游预先算好的 `x`,免得同一条路出现两套 x 口径;
      - 参数键与 `travel_time_s` 同源:`alpha` / `beta`(缺省 0.15 / 4.0),
        **不再有 `bpr_alpha` / `bpr_beta` 这种第二套命名**;
      - 内部就是 `make_weight_fn` —— 本文件是全仓唯一的 BPR 实现,别的模块一律调这里,不复制公式。
    """
    return make_weight_fn(graph, states or {}, params, extra_vph)
