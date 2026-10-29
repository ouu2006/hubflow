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


def _u_turn_blocked(graph: Graph, previous_edge_id: str, edge_id: str) -> bool:
    """连续两条边是否构成**被禁止的**原地掉头。

    判定只看图上的拓扑字段（真网 enriched 图带）：
    - 同 `section`、方向相反 → 掉头；
    - 前一条边的 `u_turn_allowed=false` → 禁止。
    样例网边没有 direction 字段，两条边的 direction 都是 None，不会误判。
    """
    previous = graph.edge(previous_edge_id)
    current = graph.edge(edge_id)
    if str(previous.get("section")) != str(current.get("section")):
        return False
    if previous.get("direction") == current.get("direction"):
        return False
    return not bool(previous.get("u_turn_allowed"))


def dijkstra(
    graph: Graph,
    src: str,
    dst: str,
    weight: Callable[[str], float],
    banned_edges: set[str] | None = None,
    banned_nodes: set[str] | None = None,
    forbid_u_turn: bool = False,
) -> list[str] | None:
    """单源最短路,返回**边 id 序列**(找不到返回 None)。

    比较键是 `(累计代价, 路径元组)`,保证同一输入结果可复现。
    `forbid_u_turn=True` 时用**边状态** Dijkstra：状态 = (节点, 上一条边)，
    从而能真正执行"同段反向立即掉头且 u_turn_allowed=false 则禁止"。
    """
    banned_edges = banned_edges or set()
    banned_nodes = banned_nodes or set()
    if src in banned_nodes or dst in banned_nodes:
        return None

    if not forbid_u_turn:
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

    # 边状态版本（只在真网这类有 U-turn 约束的图上启用；样例网走上面的旧路径）
    best_state: dict[tuple[str, str | None], float] = {(src, None): 0.0}
    state_heap: list[tuple[float, tuple[str, ...], str, str | None]] = [(0.0, (), src, None)]
    while state_heap:
        cost, path, node, previous = heapq.heappop(state_heap)
        if node == dst:
            return list(path)
        if cost > best_state.get((node, previous), float("inf")):
            continue
        for edge_id in graph.out_edges(node):
            if edge_id in banned_edges:
                continue
            if previous is not None and _u_turn_blocked(graph, previous, edge_id):
                continue
            nxt = str(graph.edge(edge_id)["to"])
            if nxt in banned_nodes:
                continue
            new_cost = cost + weight(edge_id)
            key = (nxt, edge_id)
            if new_cost < best_state.get(key, float("inf")):
                best_state[key] = new_cost
                heapq.heappush(state_heap, (new_cost, path + (edge_id,), nxt, edge_id))
    return None


def k_shortest_paths(
    graph: Graph,
    src: str,
    dst: str,
    k: int,
    weight: Callable[[str], float],
    weight_override: Callable[[list[str]], float] | None = None,
    forbid_u_turn: bool = False,
) -> list[list[str]]:
    """Yen 的 K 最短路,返回按代价升序的边 id 序列(可能少于 k 条)。

    `weight_override` 给"整条路径的代价"用;不给就按边权重累加。
    `forbid_u_turn` 透传给 dijkstra（真网禁非法掉头）。
    """
    def path_cost(path: list[str]) -> float:
        if weight_override is not None:
            return weight_override(path)
        return sum(weight(eid) for eid in path)

    first = dijkstra(graph, src, dst, weight, forbid_u_turn=forbid_u_turn)
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

            spur = dijkstra(
                graph,
                spur_node,
                dst,
                weight,
                banned_edges,
                banned_nodes,
                forbid_u_turn=forbid_u_turn,
            )
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
    forbid_u_turn: bool | None = None,
    k_generate: int | None = None,
) -> list[list[str]]:
    """按 Yen 取候选,再按重叠度筛掉"等价路径"。

    贪心:按代价升序逐个看,与**已选中**的任一条重叠度超过 `max_overlap` 就丢弃。
    `forbid_u_turn=None` 时读图属性 `attributes.forbid_u_turn`（真网 enriched 图为 true；
    样例图没有该属性 → 保持旧行为逐字节不变）。

    `k_generate`：**只放大候选池的搜索深度**（先把 Yen 的 K 放到 N 条，再按同一个
    `max_overlap` 筛到 `k` 条）；默认 `None` = 旧行为（池深 = k）。重叠度口径一个不动：
    仍然按**全长**共线比例算，绝不去掉公共首尾（业主 2026-10-28 裁定：那是绕过门槛凑数）。
    """
    if forbid_u_turn is None:
        forbid_u_turn = bool(graph.attributes.get("forbid_u_turn"))
    pool = max(int(k_generate or k), int(k))
    picked: list[list[str]] = []
    for path in k_shortest_paths(graph, src, dst, pool, weight, forbid_u_turn=forbid_u_turn):
        if all(path_overlap(graph, path, kept) <= max_overlap for kept in picked):
            picked.append(path)
        if len(picked) >= k:
            break
    return picked
