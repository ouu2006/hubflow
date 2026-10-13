"""K 最短路候选生成(手册 7.3 步骤①:K=3、路径重叠度 ≤ 0.7)。

输入:network.Graph + 边权重函数(通常是 BPR 秒数)
输出:边 id 序列的列表(内存,不落盘)
口径:
  - `K = 3`(1 推荐 + 2 备选,契约第二节「备选 ≥2」);
  - **路径重叠度 = 两条路径的共线长度 / 其中较短者的长度**,超过 `max_path_overlap` 的候选**丢弃**
    —— 这是"不为凑数返回等价路径"的实现(契约第二节两条硬规则之一);
  - **确定性**:所有比较都带 (代价, 路径元组) 的二次排序,同一输入连跑结果一致(M1-1)。

算法:Yen 的 K 最短路(在 Dijkstra 上做偏离),样本路网规模小,不必上更重的实现。

用法:由 run.py 调用,不单独执行。
"""

from __future__ import annotations

import heapq
import itertools
from typing import Callable

from network import Graph, path_length_m


def dijkstra(
    graph: Graph,
    src: str,
    dst: str,
    weight: Callable[[str], float],
    banned_edges: set[str] | None = None,
    banned_nodes: set[str] | None = None,
) -> list[str] | None:
    """单源最短路,返回**边 id 序列**(找不到返回 None)。

    比较键是 `(累计代价, 路径元组)`,保证同一输入结果可复现。
    """
    banned_edges = banned_edges or set()
    banned_nodes = banned_nodes or set()
    if src in banned_nodes or dst in banned_nodes:
        return None

    best: dict[str, float] = {src: 0.0}
    heap: list[tuple[float, tuple[str, ...], str]] = [(0.0, (), src)]

    while heap:
        cost, path, node = heapq.heappop(heap)
        if node == dst:
            return list(path)
        if cost > best.get(node, float("inf")):
            continue
        for edge_id in graph.out_edges(node):
            if edge_id in banned_edges:
                continue
            nxt = str(graph.edge(edge_id)["to"])
            if nxt in banned_nodes:
                continue
            new_cost = cost + weight(edge_id)
            if new_cost < best.get(nxt, float("inf")):
                best[nxt] = new_cost
                heapq.heappush(heap, (new_cost, path + (edge_id,), nxt))
    return None


def k_shortest_paths(
    graph: Graph,
    src: str,
    dst: str,
    k: int,
    weight: Callable[[str], float],
    weight_override: Callable[[list[str]], float] | None = None,
) -> list[list[str]]:
    """Yen 的 K 最短路,返回按代价升序的边 id 序列(可能少于 k 条)。

    `weight_override` 给"整条路径的代价"用;不给就按边权重累加。
    """
    def path_cost(path: list[str]) -> float:
        if weight_override is not None:
            return weight_override(path)
        return sum(weight(eid) for eid in path)

    first = dijkstra(graph, src, dst, weight)
    if first is None:
        return []

    accepted: list[list[str]] = [first]
    accepted_keys = {tuple(first)}
    candidates: list[tuple[float, int, list[str]]] = []
    counter = itertools.count()

    while len(accepted) < k:
        prev = accepted[-1]
        # 偏离点从**起点本身**开始(i = -1,root 为空),再到 prev 上除终点外的每个节点。
        # 漏掉 i = -1 会生成不出"换一条起步边"的走廊 —— 这是本实现最容易写错的一处。
        for i in range(-1, len(prev) - 1):
            root_path = prev[: i + 1]
            spur_node = src if i < 0 else str(graph.edge(prev[i])["to"])

            banned_edges: set[str] = set()
            for path in accepted:
                if path[: i + 1] == root_path and len(path) > i + 1:
                    banned_edges.add(path[i + 1])
            banned_nodes = {str(graph.edge(eid)["from"]) for eid in root_path}

            spur = dijkstra(graph, spur_node, dst, weight, banned_edges, banned_nodes)
            if spur is None:
                continue
            total = root_path + spur
            key = tuple(total)
            if key in accepted_keys:
                continue
            accepted_keys.add(key)
            heapq.heappush(candidates, (path_cost(total), next(counter), total))

        if not candidates:
            break
        _, _, nxt = heapq.heappop(candidates)
        accepted.append(nxt)

    return accepted


def path_overlap(graph: Graph, path_a: list[str], path_b: list[str]) -> float:
    """路径重叠度 = 共线长度 / 较短者长度(0~1)。两条空路径视为不重叠。"""
    len_a = path_length_m(graph, path_a)
    len_b = path_length_m(graph, path_b)
    shorter = min(len_a, len_b)
    if shorter <= 0:
        return 0.0
    shared = sum(float(graph.edge(eid)["length_m"]) for eid in set(path_a) & set(path_b))
    return shared / shorter


def select_candidates(
    graph: Graph,
    src: str,
    dst: str,
    k: int,
    max_overlap: float,
    weight: Callable[[str], float],
) -> list[list[str]]:
    """按 Yen 取候选,再按重叠度筛掉"等价路径"。

    贪心:按代价升序逐个看,与**已选中**的任一条重叠度超过 `max_overlap` 就丢弃。
    """
    picked: list[list[str]] = []
    for path in k_shortest_paths(graph, src, dst, k, weight):
        if all(path_overlap(graph, path, kept) <= max_overlap for kept in picked):
            picked.append(path)
        if len(picked) >= k:
            break
    return picked
