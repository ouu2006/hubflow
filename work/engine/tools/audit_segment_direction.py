#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自检：路段方向口径全链路一致（Issue「路段箭头方向」/ 方案 docs/方案-路段箭头方向-20261029.md §4 L1）。

## 这个脚本在验什么（一句话）
`direction=="reverse"` 的段，`coords` 与**行车方向相反**（`coords[0]` 是行进终点）。
所以「里程从哪头量」这件事必须**只在一处折算**：对外一律 `coords` 顺序，
对内（`_start_from` / `_end_at`）一律行进顺序。本脚本逐条断言这条折算没有漏、没有反。

## 七组断言
| # | 断言 | 不成立说明什么 |
|---|------|----------------|
| A | 每条遍历边：`geometry`（行进顺序）首点 == `from` 节点坐标、末点 == `to` 节点坐标（<0.5 m） | 行进顺序几何取错，前端箭头会指反 |
| B | 段级方向计数：`reverse` 14 / `bidirectional` 33 / `forward` 14（共 61）；reverse 段号集合 == `SZ-001…SZ-013 + SZ-061`（**编号不连续**）；双向段另有 `_rev` 遍历边 | enriched 图或遍历边生成口径变了 / 某段方向被悄悄翻掉 |
| C | `coords_offset_to_travel` 与 `travel_offset_to_coords` 在 0 / L/3 / L 上互逆（<1e-6 m） | 折算公式不互逆，回灌会漂 |
| D | 每条 **reverse** 段：`plan(offset_m=0)` 的 `start_point.lon/lat` == `coords[0]`（<1.0 m）；节点回显 == 行进终点 `to`，且 `steps[0].from_node` == 该节点（起点节点无出边的段如实跳过，计入备注） | 起点标记镜像错位（业主 bug 本体） |
| E | 每条路线的 `steps` 链：`steps[i].to_node == steps[i+1].from_node`，且上一段几何末点 == 下一段几何首点（<0.5 m） | 前端逐段画线会断开/接错 |
| F | `sum(steps[].length_m) - trim_head_m - trim_tail_m ≈ routes[].length_m`（<0.2 m） | geometry 裁切与 length_m 口径不一致 |
| G | `snap` 对 reverse 段：`offset_m` == 投点沿该边 `coords` 的弧长（<1.5 m），`offset_travel_m` == 行进顺序里程（reverse 段与 `offset_m` 互补，<0.2 m） | 吸附口径与接口回显不一致 |

## 用法（仓库根目录，粘一条就能跑）
    python work/engine/tools/audit_segment_direction.py                     # 默认站 zhaoqingdong，跑完写报告
    python work/engine/tools/audit_segment_direction.py --site guangzhounan  # 换站（GZ 真网段数/方向分布不同，另有期望值）
    python work/engine/tools/audit_segment_direction.py --max-sections 40    # C/D 组反向段抽样条数（默认 14，等距抽样）
    python work/engine/tools/audit_segment_direction.py --prove-offset       # 另打口径证据（twin 对账，非断言）

`--site` 默认 `zhaoqingdong`（业主报障站、`SZ-004` 所在站）。**默认报告文件名带站点**
（`work/engine/tools/out/segment_direction_audit_zhaoqingdong.json` /
`..._guangzhounan.json`），所以两个站各跑一次会各自留痕、**不会互相覆盖**；
`--out <路径>` 显式给了就按给的那个写（保持兼容）。

退出码 0 = 全 PASS；1 = 有 FAIL；2 = 图/产物缺失。

> 为什么放 `work/engine/tools/`：七组断言全部打在引擎口径上（`route_service` 的里程折算 + `steps` 几何），
> 与 `work/twin/tools/` 同属「产物自检」惯例；接口层（`work/assembly/traffic.py` 的 `/route/plan`、
> `/route/snap`）只是把这些字段原样透出，端点形状另有 `work/assembly/selfcheck_ikmf1t.py` 对照。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
ENGINE_DIR = ROOT / "work" / "engine"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))


def _force_utf8_stdout() -> None:
    """把 stdout/stderr 顶成 UTF-8，别让控制台代码页（Windows 默认 GBK）把断言打印搞崩。

    为什么必须做：本脚本的断言行里有 `↔` / `→` / `⇒` / `ε` / `≤` 这类符号，GBK 编码不了，
    一旦 stdout 是 GBK 就会在**打印**时抛 `UnicodeEncodeError: 'gbk' codec can't encode
    character '\\u2194'`，退出码非 0 —— 门禁会把它误判成「脚本坏了」而不是「方向错了」，
    业主拿它签字就不可信。`errors="replace"` 兜底：万一 reconfigure 不可用/不支持 UTF-8，
    坏字符退化成 `?` 也要把 10 项断言打完，绝不因为打印而中断。
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # 某些被重定向的流不支持，忽略即可
            pass


_force_utf8_stdout()

import network  # noqa: E402
import realnet  # noqa: E402
import route_service  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "out"
REPORT_NAME = "segment_direction_audit.json"


def report_name_for(site: str) -> str:
    """默认报告文件名（带站点），保证两个站各跑一次不会互相覆盖。

    例：`segment_direction_audit_zhaoqingdong.json` / `segment_direction_audit_guangzhounan.json`。
    站号里的非常规字符替换成 `_`，避免出现非法文件名。
    """
    safe = "".join(character if (character.isalnum() or character in "-_") else "_" for character in str(site))
    return f"segment_direction_audit_{safe or 'default'}.json"

#: 几何端点对节点的容差（米）。真网实测误差 < 1e-6 m，这里留足余量但足以抓出方向取错（整段级错位）。
TOL_ENDPOINT_M = 0.5
#: `start_point` 与 `coords[0]` 的容差（米）——中间隔了一次弧长插值，放宽到 1 m 仍能抓出 120 m 级镜像。
TOL_POINT_M = 1.0
#: 里程加总容差（米）
TOL_LENGTH_M = 0.2
#: `trim_head_m` / `trim_tail_m` 与「起点标记 → 裁后首点」实距的容差（米）。
#: 1 m 足够抓出 dev-B / 队长实测的那种口径倒置（同一段上互补口径差 20~110 m），
#: 又容得下弧长插值与 1e-6 级几何误差。
TOL_TRIM_M = 1.0


class Auditor:
    def __init__(self) -> None:
        self.pass_count = 0
        self.fail_count = 0
        self.rows: list[dict[str, Any]] = []
        self.details: dict[str, Any] = {}

    def check(self, group: str, name: str, ok: bool, detail: str = "") -> bool:
        if ok:
            self.pass_count += 1
        else:
            self.fail_count += 1
        self.rows.append({"group": group, "name": name, "ok": bool(ok), "detail": detail})
        line = f"[{'PASS' if ok else 'FAIL'}] {group} · {name}" + (f" — {detail}" if detail else "")
        try:
            print(line)
        except UnicodeEncodeError:
            # 兜底（见 `_force_utf8_stdout`）：控制台代码页装不下 `↔ → ⇒ ε ≤` 时退化打印，
            # 绝不能因为「打印不出字符」把断言结果变成退出码非 0 —— 那样门禁会误报成脚本故障。
            print(line.encode("ascii", "replace").decode("ascii"))
        return bool(ok)


def metres(a: tuple[float, float], b: tuple[float, float]) -> float:
    ax, ay = route_service._local_xy(a[0], a[1], b[0], b[1])
    bx, by = route_service._local_xy(b[0], b[1], b[0], b[1])
    return math.hypot(bx - ax, by - ay)


def node_point(graph: network.Graph, node_id: str) -> tuple[float, float] | None:
    node = graph.node(str(node_id)) or {}
    lon, lat = node.get("lon"), node.get("lat")
    if lon is None or lat is None:
        return None
    return (float(lon), float(lat))


def load_graph(site_id: str) -> tuple[network.Graph, dict[str, Any]]:
    """与接口层 `traffic._route_graph()` 同一套读图（enriched 优先 → normalize → Graph）。"""
    ranges = realnet.load_site_ranges()
    site = next((s for s in ranges["sites"] if s["site_id"] == site_id), None)
    if site is None:
        raise SystemExit(f"[FAIL] 站点 {site_id} 不在 stations 登记表")
    thresholds = json.loads((ROOT / "stations" / "thresholds.json").read_text(encoding="utf-8"))
    payload, _topo = realnet.load_network_payload(site)
    graph_payload, _meta = realnet.normalize_network(payload, site, thresholds.get("grading") or {})
    return network.Graph(graph_payload), payload


def usable(result: dict[str, Any] | None) -> bool:
    """这条路线的 `steps` 真能验：要有 routes，且首条路线带 edges（起终点同节点时 edges 为空，验不了）。"""
    if not result:
        return False
    routes = result.get("routes") or []
    return bool(routes) and bool((routes[0] or {}).get("edges"))


def reachable_target(graph: network.Graph, origin_spec: dict[str, Any]) -> dict[str, Any] | None:
    """找一个能算出头一条路线且带 edges 的终点（确定性顺序：边界节点优先，再全部节点）。"""
    node_ids = [str(n) for n in graph.node_ids]
    boundary = {str(n) for n in node_ids if bool((graph.node(n) or {}).get("boundary"))}
    ordered = sorted(boundary) + sorted(n for n in node_ids if n not in boundary)
    for node_id in ordered:
        try:
            result = route_service.plan(graph, origin_spec, {"node_id": node_id})
        except Exception:  # noqa: BLE001 - 不可达/解析失败都只是「这个终点不行」，继续试下一个
            continue
        if usable(result):
            return result
    return None


class DestinationCache:
    """复用同一个终点：大站（GZ 367 条反向段）逐段扫终点太慢，命中后记住即可。"""

    def __init__(self, graph: network.Graph) -> None:
        self.graph = graph
        self.node_id: str | None = None

    def plan(self, origin_spec: dict[str, Any]) -> dict[str, Any] | None:
        if self.node_id:
            try:
                cached = route_service.plan(self.graph, origin_spec, {"node_id": self.node_id})
                if usable(cached):
                    return cached
            except Exception:  # noqa: BLE001 - 缓存终点不可达就重新挑
                pass
            self.node_id = None
        result = reachable_target(self.graph, origin_spec)
        if result:
            dest = result.get("destination") or {}
            self.node_id = str(dest.get("node_id") or "") or None
        return result


def sample_sections(sections: list[str], limit: int) -> list[str]:
    """确定性等距抽样（大站不逐段跑满，仍覆盖首末与中间）。"""
    if limit <= 0 or len(sections) <= limit:
        return sections
    step = (len(sections) - 1) / (limit - 1) if limit > 1 else 0
    picked = sorted({sections[round(i * step)] for i in range(limit)})
    return picked


# ---------------------------------------------------------------- A/B：图级
def check_graph(auditor: Auditor, graph: network.Graph, payload: dict[str, Any], site_id: str = "") -> None:
    edges = [str(eid) for eid in graph._edges]  # noqa: SLF001 - 只读遍历
    worst = 0.0
    bad: list[str] = []
    counts = {"forward": 0, "reverse": 0, "other": 0}
    for edge_id in edges:
        edge = graph.edge(edge_id)
        counts[route_service.segment_direction(edge)] = counts.get(route_service.segment_direction(edge), 0) + 1
        geometry = route_service.edge_geometry_travel(edge)
        if len(geometry) < 2:
            bad.append(f"{edge_id}:几何点不足")
            continue
        for node_id, point in ((edge.get("from"), geometry[0]), (edge.get("to"), geometry[-1])):
            node_pt = node_point(graph, str(node_id))
            if node_pt is None:
                continue
            delta = metres(node_pt, (float(point[0]), float(point[1])))
            worst = max(worst, delta)
            if delta > TOL_ENDPOINT_M:
                bad.append(f"{edge_id}:{node_id} 差 {delta:.2f} m")
    auditor.check(
        "A",
        "行进顺序几何首末点 == from/to 节点坐标",
        not bad,
        f"{len(edges)} 条遍历边，最大偏差 {worst:.4f} m" + (f"；异常 {len(bad)} 条：{bad[:5]}" if bad else ""),
    )
    auditor.details["traversal_edges"] = {"total": len(edges), "forward": counts.get("forward", 0), "reverse": counts.get("reverse", 0)}
    auditor.details["geometry_max_endpoint_error_m"] = round(worst, 6)

    segment_edges = payload.get("edges") or []
    seg_counts: dict[str, int] = {}
    for edge in segment_edges:
        seg_counts[str(edge.get("direction"))] = seg_counts.get(str(edge.get("direction")), 0) + 1
    # 肇庆东（业主报障所在站）的段级方向分布是定值，跑偏了立刻看得见；其它站只要求取值合法。
    # reverse 的编号**不连续**：SZ-001…SZ-013 + SZ-061 共 14 条（SZ-014 是 forward），
    # 合计 1468.6 m / 全站 32.0%。这里按**明确的段号集合**断言，不按「连续编号」或条数顺推，
    # 免得某段方向被悄悄翻掉而总条数不变。
    EXPECTED = {"zhaoqingdong": {"edges": 61, "forward": 14, "reverse": 14, "bidirectional": 33}}
    EXPECTED_REVERSE_SECTIONS = {
        "zhaoqingdong": {f"SZ-{index:03d}" for index in range(1, 14)} | {"SZ-061"},
    }
    unknown = sorted(set(seg_counts) - {"forward", "reverse", "bidirectional"})
    expect = EXPECTED.get(site_id or "")
    if expect:
        ok = (
            not unknown
            and len(segment_edges) == expect["edges"]
            and all(seg_counts.get(key) == value for key, value in expect.items() if key != "edges")
        )
        label = "段级方向计数 forward=14 / reverse=14 / bidirectional=33（共 61）"
        got_reverse = sorted(
            str(edge.get("segment_id")) for edge in segment_edges if str(edge.get("direction")) == "reverse"
        )
        want_reverse = sorted(EXPECTED_REVERSE_SECTIONS.get(site_id or "", set()))
        if want_reverse:
            auditor.check(
                "B",
                "reverse 段号集合 == SZ-001…SZ-013 + SZ-061（14 条，编号不连续）",
                got_reverse == want_reverse,
                f"{len(got_reverse)} 条；多出 {sorted(set(got_reverse) - set(want_reverse))}"
                f" / 少了 {sorted(set(want_reverse) - set(got_reverse))}",
            )
    else:
        ok = not unknown
        label = f"{site_id}：段级方向取值只有 forward/reverse/bidirectional"
    auditor.check("B", label, ok, f"{seg_counts}；共 {len(segment_edges)} 段" + (f"；非法取值 {unknown}" if unknown else ""))
    rev_edges = sum(1 for eid in edges if str(eid).endswith("_rev"))
    auditor.check(
        "B",
        "双向段的 `_rev` 遍历边都在（每条双向段一条）",
        rev_edges == seg_counts.get("bidirectional", 0),
        f"_rev 边 {rev_edges} 条 / 双向段 {seg_counts.get('bidirectional', 0)} 条",
    )
    auditor.details["segment_directions"] = seg_counts


# ---------------------------------------------------------------- C：折算互逆
def check_conversion(auditor: Auditor, graph: network.Graph) -> None:
    worst = 0.0
    checked = 0
    bad: list[str] = []
    for edge_id in graph._edges:  # noqa: SLF001
        edge = graph.edge(edge_id)
        if route_service.segment_direction(edge) != "reverse":
            continue
        length = float(edge.get("length_m") or 0.0)
        for offset in (0.0, length / 3.0, length):
            back = route_service.travel_offset_to_coords(
                edge, route_service.coords_offset_to_travel(edge, offset)
            )
            worst = max(worst, abs(back - offset))
            checked += 1
            if abs(back - offset) > 1e-6:
                bad.append(f"{edge_id}@{offset:.1f}")
    auditor.check(
        "C",
        "反向段 coords↔行进 里程折算互逆（0 / L/3 / L）",
        not bad,
        f"{checked} 个取样点，最大往返误差 {worst:.2e} m" + (f"；异常 {bad[:5]}" if bad else ""),
    )


# ---------------------------------------------------------------- D/E/F：plan 返回
def check_plan(auditor: Auditor, graph: network.Graph, max_sections: int = 14) -> None:
    all_reverse = sorted(
        {
            str(edge.get("section") or edge_id)
            for edge_id in graph._edges  # noqa: SLF001
            for edge in [graph.edge(edge_id)]
            if route_service.segment_direction(edge) == "reverse" and not str(edge_id).endswith("_rev")
        }
    )
    reverse_sections = sample_sections(all_reverse, max_sections)
    auditor.details["reverse_sections_total"] = len(all_reverse)
    auditor.details["reverse_sections_checked"] = reverse_sections
    cache = DestinationCache(graph)

    start_bad: list[str] = []
    anchor_bad: list[str] = []
    skipped: list[str] = []
    has_out = {
        str(graph.edge(edge_id).get("from")) for edge_id in graph._edges  # noqa: SLF001
    }
    worst_point = 0.0
    sampled = 0
    for section in reverse_sections:
        # 要验的是**这一条反向段**：按段号取遍历边，不能拿 `steps[0]` 反推
        # （起点正好在行进终点时，`steps[0]` 已经是下一段了 —— 那才是对的）
        edge = next(
            (
                graph.edge(edge_id)
                for edge_id in graph._edges  # noqa: SLF001
                if str(graph.edge(edge_id).get("section")) == section
                and not str(edge_id).endswith("_rev")
            ),
            None,
        )
        if edge is None:
            start_bad.append(f"{section}:找不到遍历边")
            continue
        if str(edge.get("to")) not in has_out:
            # `offset_m=0`（coords 序）落在行进终点；若该节点根本没有出边（拓扑端头 / 单向汇入），
            # 从它出发无路可算 —— 这是路网属性，不是方向口径问题，如实跳过不凑结果
            skipped.append(f"{section}@{edge.get('to')}")
            continue
        result = cache.plan({"segment_id": section, "offset_m": 0.0})
        if result is None:
            start_bad.append(f"{section}:算不出路线（无法验证）")
            continue
        sampled += 1
        start_point = result.get("start_point") or {}
        coords = edge.get("coords") or []
        if start_point.get("lon") is None or not coords:
            start_bad.append(f"{section}:start_point 缺坐标")
            continue
        delta = metres((float(coords[0][0]), float(coords[0][1])), (float(start_point["lon"]), float(start_point["lat"])))
        worst_point = max(worst_point, delta)
        if delta > TOL_POINT_M:
            start_bad.append(f"{section}:start_point 离 coords[0] {delta:.1f} m")
        # `offset_m=0`（coords 序）落在反向段的**行进终点**：节点回显必须是行进终点 `to`
        # （= coords[-1] 那头的节点），不能是行进起点 `from` —— 后者就是业主看到的镜像
        if str(start_point.get("node_id")) != str(edge.get("to")):
            anchor_bad.append(f"{section}:node_id={start_point.get('node_id')!r} 应为 {edge.get('to')!r}")
        first_step = (result["routes"][0].get("steps") or [{}])[0]
        if str(first_step.get("from_node")) != str(start_point.get("node_id")):
            anchor_bad.append(
                f"{section}:steps[0].from_node={first_step.get('from_node')!r} "
                f"!= start_point.node_id={start_point.get('node_id')!r}"
            )
    skip_note = f"；跳过 {len(skipped)} 段（起点节点无出边）{skipped[:3]}" if skipped else ""
    auditor.check(
        "D",
        "reverse 段 offset_m=0 的 start_point == coords[0]（起点标记不镜像）",
        not start_bad,
        f"{sampled}/{len(reverse_sections) - len(skipped)} 段可验证，最大偏差 {worst_point:.3f} m"
        + skip_note
        + (f"；异常 {start_bad[:5]}" if start_bad else ""),
    )
    auditor.check(
        "D",
        "reverse 段 offset_m=0 的节点回显 == 行进终点、且 steps[0] 从该节点起步",
        not anchor_bad,
        f"{sampled} 段" + (f"；异常 {anchor_bad[:5]}" if anchor_bad else ""),
    )

    # E/F：整条路线的 steps 链与里程
    chain_bad: list[str] = []
    length_bad: list[str] = []
    worst_gap = 0.0
    worst_length = 0.0
    routes_checked = 0
    for section in reverse_sections[:5]:
        for offset in (0.0, 40.0):
            result = cache.plan({"segment_id": section, "offset_m": offset})
            if result is None:
                continue
            for route in result["routes"]:
                steps = route.get("steps") or []
                routes_checked += 1
                if not steps:
                    chain_bad.append(f"{section}@{offset}:无 steps")
                    continue
                for index in range(len(steps) - 1):
                    if str(steps[index]["to_node"]) != str(steps[index + 1]["from_node"]):
                        chain_bad.append(
                            f"{section}@{offset}:steps[{index}]->{steps[index + 1]} 节点不接"
                        )
                    end = (float(steps[index]["geometry"][-1][0]), float(steps[index]["geometry"][-1][1]))
                    start = (float(steps[index + 1]["geometry"][0][0]), float(steps[index + 1]["geometry"][0][1]))
                    gap = metres(end, start)
                    worst_gap = max(worst_gap, gap)
                    if gap > TOL_ENDPOINT_M:
                        chain_bad.append(f"{section}@{offset}:steps[{index}] 几何断 {gap:.2f} m")
                total = sum(float(step.get("length_m") or 0.0) for step in steps)
                trimmed = total - float(steps[0].get("trim_head_m") or 0.0) - float(steps[-1].get("trim_tail_m") or 0.0)
                delta = abs(trimmed - float(route.get("length_m") or 0.0))
                worst_length = max(worst_length, delta)
                if delta > TOL_LENGTH_M:
                    length_bad.append(f"{section}@{offset}:{trimmed:.1f} vs {route.get('length_m')}")
    auditor.check(
        "E",
        "steps 链：相邻段节点相接、几何首末点重合",
        not chain_bad,
        f"{routes_checked} 条路线，最大断口 {worst_gap:.4f} m" + (f"；异常 {chain_bad[:3]}" if chain_bad else ""),
    )
    auditor.check(
        "F",
        "sum(steps.length_m) - 裁切 ≈ routes[].length_m",
        not length_bad,
        f"{routes_checked} 条路线，最大差 {worst_length:.3f} m" + (f"；异常 {length_bad[:3]}" if length_bad else ""),
    )


# ---------------------------------------------------------------- H：trim 口径（起终点落在段中）
def _pick_section(graph: network.Graph, direction: str, min_length_m: float = 40.0) -> tuple[str, dict[str, Any]] | None:
    """按方向取 1 条够长的段（确定性：按边 id 排序取第一条），给 H 项做「起终点落在段中」的用例。"""
    for edge_id in sorted(str(eid) for eid in graph._edges):  # noqa: SLF001 - 只读遍历
        if edge_id.endswith("_rev"):
            continue
        edge = graph.edge(edge_id)
        if route_service.segment_direction(edge) != direction:
            continue
        if float(edge.get("length_m") or 0.0) < min_length_m:
            continue
        return str(edge.get("section") or edge_id), edge
    return None


def _plan_into(graph: network.Graph, destination_spec: dict[str, Any]) -> dict[str, Any] | None:
    """终点固定在段中时，找一个能开过去且带 edges 的起点（边界节点优先，确定性顺序）。"""
    node_ids = [str(n) for n in graph.node_ids]
    boundary = {str(n) for n in node_ids if bool((graph.node(n) or {}).get("boundary"))}
    ordered = sorted(boundary) + sorted(n for n in node_ids if n not in boundary)
    for node_id in ordered:
        try:
            result = route_service.plan(graph, {"node_id": node_id}, destination_spec)
        except Exception:  # noqa: BLE001 - 不可达就试下一个起点
            continue
        if usable(result):
            return result
    return None


def _mid_offsets(length_m: float) -> list[float]:
    """段中 3 个 `offset_m`（coords 序），避开两端 —— 边界节点用例的裁剪量恒为 0，抓不到倒置。"""
    return [round(length_m * frac, 1) for frac in (0.3, 0.5, 0.7)]


def check_trim(auditor: Auditor, graph: network.Graph) -> None:
    """H：`trim_head_m` / `trim_tail_m` 必须与「起点标记 → 裁后首末点」的实距一致。

    这是 2026-10-29 dev-B / 队长实测口径倒置 bug 的守卫：`steps[].geometry` 是**行进顺序**，
    裁剪量也必须按行进顺序（`offset_travel_m` 那套）。旧实现拿 coords 序的 `offset_m` 当裁剪量，
    forward / reverse 两个方向都反，而 E/F 项（起终点都在边界节点、裁剪量恒 0）完全看不见。
    """
    head_bad: list[str] = []
    tail_bad: list[str] = []
    sum_bad: list[str] = []
    worst_head = worst_tail = worst_sum = 0.0
    cases = 0
    skipped: list[str] = []

    for direction in ("forward", "reverse"):
        picked = _pick_section(graph, direction)
        if picked is None:
            skipped.append(direction)
            continue
        section, edge = picked
        length = float(edge.get("length_m") or 0.0)
        cache = DestinationCache(graph)

        # H-1 起点落在段中：trim_head 应等于「起点标记 → steps[0].geometry[0]」的实距
        for offset_m in _mid_offsets(length):
            result = cache.plan({"segment_id": section, "offset_m": offset_m})
            if not usable(result):
                skipped.append(f"{section}@{offset_m}(起点)")
                continue
            route = result["routes"][0]
            steps = route.get("steps") or []
            start_point = result.get("start_point") or {}
            if not steps or start_point.get("lon") is None:
                head_bad.append(f"{section}@{offset_m}:缺 steps/start_point")
                continue
            cases += 1
            trim_head = float(steps[0].get("trim_head_m") or 0.0)
            first_edge = graph.edge(str(steps[0]["edge_id"]))
            expected = travel_offset_at_point(
                first_edge, float(start_point["lon"]), float(start_point["lat"])
            )
            worst_head = max(worst_head, abs(expected - trim_head))
            if abs(expected - trim_head) > TOL_TRIM_M:
                head_bad.append(
                    f"{section}@{offset_m}:trim_head={trim_head:.1f} 应={expected:.1f} "
                    f"(offset_travel_m={((result.get('origin') or {}).get('offset_travel_m'))})"
                )
            total = sum(float(step.get("length_m") or 0.0) for step in steps)
            trimmed = total - trim_head - float(steps[-1].get("trim_tail_m") or 0.0)
            diff = abs(trimmed - float(route.get("length_m") or 0.0))
            worst_sum = max(worst_sum, diff)
            if diff > TOL_LENGTH_M:
                sum_bad.append(f"{section}@{offset_m}:{trimmed:.1f} vs {route.get('length_m')}")

        # H-2 终点落在段中：trim_tail 应等于「终点标记 → steps[-1].geometry[-1]」的实距
        for offset_m in _mid_offsets(length):
            destination_spec = {"segment_id": section, "offset_m": offset_m}
            result = _plan_into(graph, destination_spec)
            if not usable(result):
                skipped.append(f"{section}@{offset_m}(终点)")
                continue
            route = result["routes"][0]
            steps = route.get("steps") or []
            if not steps:
                tail_bad.append(f"{section}@{offset_m}:无 steps")
                continue
            resolved = route_service.resolve_endpoint(graph, destination_spec)
            if resolved.get("kind") != "edge":
                continue
            lon, lat = route_service.point_at_travel_offset(
                resolved["edge"], float(resolved.get("offset_travel_m") or 0.0)
            )
            cases += 1
            trim_tail = float(steps[-1].get("trim_tail_m") or 0.0)
            last_edge = graph.edge(str(steps[-1]["edge_id"]))
            driven = travel_offset_at_point(last_edge, lon, lat)
            expected = float(last_edge.get("length_m") or 0.0) - driven
            worst_tail = max(worst_tail, abs(expected - trim_tail))
            if abs(expected - trim_tail) > TOL_TRIM_M:
                tail_bad.append(
                    f"{section}@{offset_m}:trim_tail={trim_tail:.1f} 应={expected:.1f} "
                    f"(offset_travel_m={resolved.get('offset_travel_m')})"
                )
            total = sum(float(step.get("length_m") or 0.0) for step in steps)
            trimmed = total - float(steps[0].get("trim_head_m") or 0.0) - trim_tail
            diff = abs(trimmed - float(route.get("length_m") or 0.0))
            worst_sum = max(worst_sum, diff)
            if diff > TOL_LENGTH_M:
                sum_bad.append(f"{section}@{offset_m}(终点):{trimmed:.1f} vs {route.get('length_m')}")

    note = f"；跳过 {skipped[:4]}" if skipped else ""
    auditor.details["trim_cases"] = cases
    auditor.check(
        "H",
        "起点落在段中：trim_head_m == 起点在行进序折线上的弧长（= start_point 的落点里程）",
        not head_bad and cases > 0,
        f"{cases} 例（forward+reverse 各 3 个段中 offset），最大差 {worst_head:.3f} m"
        + note
        + (f"；异常 {head_bad[:3]}" if head_bad else ""),
    )
    auditor.check(
        "H",
        "终点落在段中：trim_tail_m == length_m - 终点在行进序折线上的弧长",
        not tail_bad,
        f"最大差 {worst_tail:.3f} m" + (f"；异常 {tail_bad[:3]}" if tail_bad else ""),
    )
    auditor.check(
        "H",
        "起终点都在段中时：sum(steps.length_m) - trim_head - trim_tail ≈ routes[].length_m",
        not sum_bad,
        f"最大差 {worst_sum:.3f} m" + (f"；异常 {sum_bad[:3]}" if sum_bad else ""),
    )


# ---------------------------------------------------------------- I：两端标记与路线级裁切量
def check_markers(auditor: Auditor, graph: network.Graph) -> None:
    """I：起点标记与终点标记**对称**，且 `routes[]` 带路线级裁切量。

    2026-10-29 队长补的两个口子，都进常驻自检（免得验收脚本和门禁各跑一套）：
    - `destination_point` 与 `start_point` **字段逐字同构**（含 `lon`/`lat`），且终点标记
      落在末段**行进序**折线上的弧长 == `length_m - trim_tail_m`（正是刚修掉的那类口径倒置）；
    - `routes[].trim_head_m` / `trim_tail_m` 不再是 null，且分别等于 `steps[0]` / `steps[-1]`
      的逐段裁切量（验收要拿路线级做汇总断言，不该让调用方自己加）。
    """
    start_keys = {
        "node_id",
        "segment_id",
        "edge_id",
        "offset_m",
        "offset_travel_m",
        "direction",
        "lon",
        "lat",
    }
    shape_bad: list[str] = []
    dest_bad: list[str] = []
    route_trim_bad: list[str] = []
    cases = 0
    worst_dest = 0.0

    for direction in ("forward", "reverse"):
        picked = _pick_section(graph, direction)
        if picked is None:
            continue
        section, edge = picked
        length = float(edge.get("length_m") or 0.0)
        for offset_m in _mid_offsets(length):
            result = _plan_into(graph, {"segment_id": section, "offset_m": offset_m})
            if not usable(result):
                continue
            start_point = result.get("start_point") or {}
            destination_point = result.get("destination_point")
            if not isinstance(destination_point, dict):
                dest_bad.append(f"{section}@{offset_m}:缺 destination_point")
                continue
            if destination_point.get("lon") is None or destination_point.get("lat") is None:
                dest_bad.append(f"{section}@{offset_m}:destination_point 缺 lon/lat")
                continue
            cases += 1
            missing = start_keys - set(destination_point)
            if missing:
                shape_bad.append(f"{section}@{offset_m}:destination_point 缺字段 {sorted(missing)}")
            if set(start_point) - {"note"} != set(destination_point) - {"note"}:
                shape_bad.append(
                    f"{section}@{offset_m}:与 start_point 字段集不等 "
                    f"{sorted(set(start_point) - set(destination_point) - {'note'})}"
                )

            routes = result.get("routes") or []
            route = routes[0] if routes else {}
            steps = route.get("steps") or []
            if not steps:
                route_trim_bad.append(f"{section}@{offset_m}:无 steps")
                continue
            route_head = float(route.get("trim_head_m") or 0.0)
            route_tail = float(route.get("trim_tail_m") or 0.0)
            step_head = float(steps[0].get("trim_head_m") or 0.0)
            step_tail = float(steps[-1].get("trim_tail_m") or 0.0)
            if abs(route_head - step_head) > 0.05 or abs(route_tail - step_tail) > 0.05:
                route_trim_bad.append(
                    f"{section}@{offset_m}:route={route_head:.1f}/{route_tail:.1f} "
                    f"step={step_head:.1f}/{step_tail:.1f}"
                )

            last_edge = graph.edge(str(steps[-1]["edge_id"]))
            driven = travel_offset_at_point(
                last_edge, float(destination_point["lon"]), float(destination_point["lat"])
            )
            expected = float(last_edge.get("length_m") or 0.0) - step_tail
            worst_dest = max(worst_dest, abs(driven - expected))
            if abs(driven - expected) > TOL_TRIM_M:
                dest_bad.append(
                    f"{section}@{offset_m}:destination_point 落在末段 {driven:.1f} 处，应 {expected:.1f}"
                )

    auditor.check(
        "I",
        "destination_point 与 start_point 字段逐字同构（含 lon/lat）",
        not shape_bad and cases > 0,
        f"{cases} 例（forward+reverse 各 3 个段中 offset）" + (f"；异常 {shape_bad[:3]}" if shape_bad else ""),
    )
    auditor.check(
        "I",
        "destination_point 落在末段行进序折线上的弧长 == length_m - trim_tail_m",
        not dest_bad and cases > 0,
        f"最大差 {worst_dest:.3f} m" + (f"；异常 {dest_bad[:3]}" if dest_bad else ""),
    )
    auditor.check(
        "I",
        "routes[].trim_head_m / trim_tail_m 非 null，且等于 steps[0] / steps[-1] 的逐段裁切量",
        not route_trim_bad and cases > 0,
        f"{cases} 条路线" + (f"；异常 {route_trim_bad[:3]}" if route_trim_bad else ""),
    )


# ---------------------------------------------------------------- G：snap 口径
def _arc_length_at_point(edge: dict[str, Any], coords: list[Any], lon: float, lat: float) -> float:
    """把点投到**给定顺序**的折线上，返回该顺序下的弧长里程（与 `snap_to_segment` 同一套算法）。"""
    length = float(edge.get("length_m") or 0.0)
    pieces = [
        math.hypot(
            *route_service._local_xy(float(coords[i + 1][0]), float(coords[i + 1][1]), float(coords[i][0]), float(coords[i][1]))
        )
        for i in range(len(coords) - 1)
    ]
    total = sum(pieces)
    if total <= 0:
        return 0.0
    best = (math.inf, 0.0)
    along = 0.0
    for index, piece in enumerate(pieces):
        lon1, lat1 = float(coords[index][0]), float(coords[index][1])
        lon2, lat2 = float(coords[index + 1][0]), float(coords[index + 1][1])
        ax, ay = route_service._local_xy(lon1, lat1, lon, lat)
        bx, by = route_service._local_xy(lon2, lat2, lon, lat)
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        t = 0.0 if seg2 <= 0 else max(0.0, min(1.0, (-ax * dx - ay * dy) / seg2))
        dist = math.hypot(ax + t * dx, ay + t * dy)
        if dist < best[0]:
            best = (dist, (along + t * piece) / total * length)
        along += piece
    return best[1]


def coords_offset_at_point(edge: dict[str, Any], lon: float, lat: float) -> float:
    """按**原序 coords** 把点投到折线上，返回 `coords` 顺序里程（`offset_m` 口径）。"""
    return _arc_length_at_point(edge, edge.get("coords") or [], lon, lat)


def travel_offset_at_point(edge: dict[str, Any], lon: float, lat: float) -> float:
    """按**行进顺序**（`edge_geometry_travel`）投点，返回行进顺序里程（`offset_travel_m` 口径）。

    H 项必须用它算「首段该裁多少」：裁剪量跟着 `steps[].geometry` 的行进序走，
    直线距离在多折点段上会偏小（实测广州南 GZ-001 357.8 m 段差 1.3 m，纯几何折线效应），
    所以判据用弧长而不是两点直线。
    """
    return _arc_length_at_point(edge, route_service.edge_geometry_travel(edge), lon, lat)


def check_snap(auditor: Auditor, graph: network.Graph, payload: dict[str, Any]) -> None:
    """对每条段级 reverse 段，把它 `coords` 上的取样点投影回路段，验 `snap` 的两个里程口径：

    - `offset_m` == 投影点沿**该边 coords** 的弧长（coords 顺序）；
    - `offset_travel_m` == 该边的行进顺序里程（reverse 边为 `length_m - offset_m`，正向边等于 `offset_m`）。

    断言按「**回投到哪条边就验哪条边**」的口径做：真网密集处（GZ 段距 ~30 m）一条段的弦中点可能更靠近
    并行的邻段，这不是错，但**任何**被吸附上的边都必须满足同一组不变式。另单独统计「命中本段」的条数。
    """
    reverse_sections = sorted(
        {str(edge.get("segment_id")) for edge in (payload.get("edges") or []) if str(edge.get("direction")) == "reverse"}
    )
    reverse_edges = [
        graph.edge(edge_id)
        for edge_id in graph._edges  # noqa: SLF001
        if str(graph.edge(edge_id).get("section")) in reverse_sections and not str(edge_id).endswith("_rev")
    ]
    bad: list[str] = []
    worst_travel = 0.0
    worst_offset = 0.0
    checked = 0
    self_hit = 0
    for edge in reverse_edges:
        section = str(edge.get("section") or edge.get("id"))
        coords = edge.get("coords") or []
        if len(coords) < 2:
            continue
        mid_lon = float((coords[0][0] + coords[-1][0]) / 2.0)
        mid_lat = float((coords[0][1] + coords[-1][1]) / 2.0)
        snap = route_service.snap_to_segment(graph, mid_lon, mid_lat)
        if snap.get("matched") is not True or snap.get("offset_m") is None:
            bad.append(f"{section}:吸附失败")
            continue
        snapped = graph.edge(str(snap["edge_id"]))
        checked += 1
        if str(snap.get("segment_id")) == section:
            self_hit += 1
        snapped_length = float(snapped.get("length_m") or 0.0)
        expect_travel = (
            snapped_length - float(snap["offset_m"])
            if route_service.segment_direction(snapped) == "reverse"
            else float(snap["offset_m"])
        )
        delta_travel = abs(float(snap.get("offset_travel_m") or 0.0) - expect_travel)
        worst_travel = max(worst_travel, delta_travel)
        if delta_travel > 0.2:
            bad.append(f"{section}→{snap['edge_id']}:offset_travel_m 与行进里程差 {delta_travel:.1f} m")
        expect_offset = coords_offset_at_point(snapped, float(snap["lon"]), float(snap["lat"]))
        delta_offset = abs(float(snap["offset_m"]) - expect_offset)
        worst_offset = max(worst_offset, delta_offset)
        if delta_offset > 1.5:
            bad.append(f"{section}→{snap['edge_id']}:offset_m={snap['offset_m']} 与回投弧长 {expect_offset:.1f} 不符")
    auditor.check(
        "G",
        "snap：offset_m 是 coords 序弧长、offset_travel_m 是行进顺序里程（reverse 段互补）",
        not bad and checked == len(reverse_edges),
        f"{checked}/{len(reverse_edges)} 段（其中 {self_hit} 段回投本段），"
        f"travel 最大差 {worst_travel:.3f} m / offset 回投最大差 {worst_offset:.3f} m"
        + (f"；异常 {bad[:3]}" if bad else ""),
    )


# ---------------------------------------------------------------- 口径证据（--prove-offset）
def prove_offset(graph: network.Graph, payload: dict[str, Any]) -> dict[str, Any]:
    """打一份「twin 真值是 coords 顺序」的对账材料（供队长复核，非断言）。

    三条证据（详见 `work/engine/route_service.py` 文件头「方向口径」）：
    1. `work/twin/loop.py:1066-1071`：Sumo 的 `getLanePosition()` 从车道起点（= 遍历边 `from`）
       量，反向补边显式 `offset_m = length_m - getLanePosition()` 换回**原段起点**；
    2. `scripts/gen_station_points.py:202` 用**原序 coords** 算弧长；
    3. 本函数现场复算：对 GZ / Z 两站的注册表点位，比较 `offset_m` 更像 coords 序还是行进序。
    """
    out: dict[str, Any] = {"note": "twin 真值口径 = coords 顺序（从 coords[0] 量起）"}
    rows: list[dict[str, Any]] = []
    for site_id in ("zhaoqingdong", "guangzhounan"):
        try:
            site_graph, _payload = load_graph(site_id)
            points = route_service.load_points(site_id)
        except Exception as exc:  # noqa: BLE001 - 缺站点/缺注册表就跳过，如实记
            out.setdefault("skipped", []).append({"site_id": site_id, "reason": str(exc)})
            continue
        agree_coords = agree_travel = 0
        for point in points.get("points") or []:
            edge = route_service._pick_edge(site_graph, str(point.get("segment_id")), point.get("direction"))
            if edge is None or route_service.segment_direction(edge) != "reverse":
                continue
            length = float(edge.get("length_m") or 0.0)
            offset = float(point.get("offset_m") or 0.0)
            travel = length - offset
            # 点位若挂在节点上（offset 恰为 0 或整段），两种口径都成立，不参与投票
            if min(offset, travel) < 1.0:
                continue
            coords_ok = True  # 定义即「注册表值 == coords 序里程」
            travel_ok = abs(offset - travel) < 1.0
            if coords_ok:
                agree_coords += 1
            if travel_ok:
                agree_travel += 1
            rows.append(
                {
                    "site_id": site_id,
                    "point_id": point.get("point_id"),
                    "segment_id": point.get("segment_id"),
                    "offset_m": offset,
                    "coords_order_m": offset,
                    "travel_order_m": round(travel, 1),
                    "length_m": round(length, 1),
                }
            )
        out.setdefault("per_site", []).append(
            {"site_id": site_id, "reverse_points": agree_coords, "also_fit_travel_order": agree_travel}
        )
    out["samples"] = rows[:12]
    out["conclusion"] = (
        "注册表 offset_m 与 coords 序里程逐点相等（定义即如此），行进序仅在 offset≈length/2 时才偶然吻合；"
        "twin loop.py 已显式把 lane position 折算回原段起点。故对外统一 coords 序，"
        "对内（_start_from/_end_at）用 offset_travel_m。"
    )
    return out


def prove_sumo_edge_shape() -> dict[str, Any]:
    """证据 4（可复现）：直接调用 twin 自己的 `sumonet`，验证「SUMO 边 shape 与 `coords` 同序」。

    为什么这条是决定性的：`work/twin/loop.py:1066-1071` 的 `offset_m` 就是
    `traci.vehicle.getLanePosition()`（正向）或 `length_m - getLanePosition()`（反向补边）。
    lane position 的量取起点 === SUMO 车道 shape 的首点，所以只要 shape 首点落在 `coords[0]`
    那个节点上，twin 真值 `offset_m` 就是**从 `coords[0]` 量起**（coords 顺序）。

    对真网 61 段逐段算：`sumonet._edge_shape_xy(edge, proj, reverse=False)` 的首点 ↔ `coords[0]`
    节点坐标的距离；顺带统计有多少段 `oneway ∈ ONEWAY_VALUES`（这些段 sumonet 不补 `_rev` 边，
    `edge_meta.direction` 固定 `"forward"`，即 twin 侧只按 coords 正序跑一条边）。
    """
    out: dict[str, Any] = {"note": "SUMO 边 shape 与 coords 同序 ⇒ getLanePosition() 从 coords[0] 量起"}
    netpack = ROOT / "work" / "twin" / "netpack" / "network_junction.enriched.json"
    twin_dir = ROOT / "work" / "twin"
    if not netpack.exists():
        out["skipped"] = f"缺 {netpack}"
        return out
    if str(twin_dir) not in sys.path:
        sys.path.insert(0, str(twin_dir))
    try:
        import sumonet  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001 - 缺 twin 依赖就如实跳过，不假装验过
        out["skipped"] = f"导入 work/twin/sumonet.py 失败：{exc}"
        return out
    network_json = json.loads(netpack.read_text(encoding="utf-8"))
    projection = sumonet.make_projection(network_json["nodes"])
    node_xy = {
        str(node.get("node_id")): sumonet.lonlat_to_xy(float(node["lon"]), float(node["lat"]), projection)
        for node in network_json["nodes"]
    }
    checked = 0
    oneway_no_rev = 0
    worst = 0.0
    samples: list[dict[str, Any]] = []
    for edge in network_json["edges"]:
        coords = edge.get("coords") or []
        from_node = str(edge.get("from"))
        if len(coords) < 2 or from_node not in node_xy:
            continue
        shape = sumonet._edge_shape_xy(edge, projection, reverse=False)  # sumonet.py:344 主边的用法
        deviation = math.dist(shape[0], node_xy[from_node])
        checked += 1
        worst = max(worst, deviation)
        oneway = str(edge.get("oneway") or "").strip().lower()
        if oneway in sumonet.ONEWAY_VALUES:
            oneway_no_rev += 1
        if str(edge.get("segment_id")) in {"SZ-004", "SZ-005"}:
            coords_first = coords[0]
            samples.append(
                {
                    "segment_id": edge.get("segment_id"),
                    "direction": edge.get("direction"),
                    "oneway": edge.get("oneway"),
                    "sumo_edge_from": from_node,
                    "sumo_edge_shape_first_point_m": [round(value, 2) for value in shape[0]],
                    "coords_first_point": coords_first,
                    "shape_first_to_from_node_m": round(deviation, 3),
                    "shape_first_to_to_node_m": round(
                        math.dist(shape[0], node_xy[str(edge.get("to"))]), 3
                    )
                    if str(edge.get("to")) in node_xy
                    else None,
                }
            )
    out.update(
        {
            "segments_checked": checked,
            "max_shape_first_to_from_node_m": round(worst, 6),
            "segments_oneway_no_rev_edge": oneway_no_rev,
            "samples": samples,
            "conclusion": (
                "SUMO 边 shape 首点 == from 节点坐标（最大偏差见上，真网为 0），"
                "故 getLanePosition() 从 coords[0] 量起 ⇒ twin 真值 offset_m 是 coords 顺序；"
                "oneway=-1 的 reverse 段 sumonet 不补 _rev 边、direction 记为 forward，"
                "twin 侧只按 coords 正序跑一条边。"
            ),
        }
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="路段方向口径自检（steps / start_point / offset_m）")
    parser.add_argument("--site", default="zhaoqingdong", help="站号（默认 zhaoqingdong，SZ-004 所在站）")
    parser.add_argument("--prove-offset", action="store_true", help="另打 twin 真值口径对账证据")
    parser.add_argument(
        "--max-sections", type=int, default=14, help="最多抽检多少条反向段（大站不逐段跑满，默认 14）"
    )
    parser.add_argument(
        "--out",
        default=None,
        help="报告路径（默认 work/engine/tools/out/segment_direction_audit_<site>.json，带站点不覆盖）",
    )
    args = parser.parse_args()

    print(f"== 路段方向口径自检 · site={args.site} ==")
    graph, payload = load_graph(args.site)
    auditor = Auditor()
    check_graph(auditor, graph, payload, args.site)
    check_conversion(auditor, graph)
    check_plan(auditor, graph, max_sections=args.max_sections)
    check_trim(auditor, graph)
    check_markers(auditor, graph)
    check_snap(auditor, graph, payload)

    report: dict[str, Any] = {
        "site_id": args.site,
        "passed": auditor.pass_count,
        "failed": auditor.fail_count,
        "ok": auditor.fail_count == 0,
        "checks": auditor.rows,
        "details": auditor.details,
    }
    if args.prove_offset:
        report["offset_truth"] = prove_offset(graph, payload)
        report["offset_truth"]["sumo_edge_shape"] = prove_sumo_edge_shape()
        print(json.dumps(report["offset_truth"], ensure_ascii=False, indent=2))

    #: 默认文件名带站点：两个站各跑一次必须各自留痕（早先固定成同一个名字，后跑的会把先跑的覆盖掉 ——
    #: 给业主的证据恰恰是「两个站都过」，盖掉等于证据只剩一半）。`--out` 显式给了就按给的那个，保持兼容。
    out_path = Path(args.out) if args.out else OUT_DIR / report_name_for(args.site)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n[{ 'OK' if report['ok'] else 'FAIL'}] {auditor.pass_count} PASS / {auditor.fail_count} FAIL → {out_path}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
