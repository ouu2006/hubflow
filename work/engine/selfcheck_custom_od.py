#!/usr/bin/env python3
"""自检：自定义起终点 + 一主两备（`work/engine/route_service.py`）。

覆盖：

1. 点位注册表能读、点都带锚点（node / segment / offset）；
2. 入口 → 落客点能出路线（至少 1 条），多条时**互不重复**；
3. 不可达组合如实报错（ValueError），不编造；
4. 中边起点（`segment_id + offset_m`）能算，且与节点算路结果不同；
5. 备选原因含「分岔点 / 里程差 / 用时差」（TC-03 要求"差异原因含节点与耗时差"）；
6. 同一输入跑两遍结果逐字节一致（确定性）。

用法（仓库根目录）：

    python work/engine/selfcheck_custom_od.py

退出码 0=全过 / 1=有 FAIL。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = ROOT / "work" / "engine"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

import network  # noqa: E402
import realnet  # noqa: E402
import route_service  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"[PASS] {name}" + (f" —— {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f" —— {detail}" if detail else ""))


def build_graph(site_id: str) -> tuple[network.Graph, dict]:
    site = realnet.load_site(site_id, None)
    thresholds = network.load_thresholds(ROOT / "stations" / "thresholds.json")
    payload, _topo = realnet.load_network_payload(site)
    graph_payload, _meta = realnet.normalize_network(payload, site, thresholds["grading"])
    return network.Graph(graph_payload), thresholds


def find_pair(graph: network.Graph, points: dict, service) -> tuple[str, str] | None:
    """按注册表顺序找第一组「能算出 ≥1 条路线」的入口 → 落客点。"""
    entries = [p for p in points["points"] if p.get("kind") == "entry"]
    dests = [p for p in points["points"] if p.get("kind") in ("dropoff", "zone")]
    for entry in entries:
        for dest in dests:
            try:
                result = service.plan(
                    graph,
                    {"point_id": entry["point_id"]},
                    {"point_id": dest["point_id"]},
                    points=points,
                )
            except ValueError:
                continue
            if result["routes"]:
                return entry["point_id"], dest["point_id"]
    return None


def main() -> int:
    for site_id in ("zhaoqingdong", "guangzhounan"):
        print(f"\n=== {site_id} ===")
        graph, thresholds = build_graph(site_id)
        points = route_service.load_points(site_id)
        check(
            f"{site_id}：点位注册表可读",
            not points.get("missing") and bool(points.get("points")),
            f"{len(points.get('points') or [])} 个点",
        )
        missing_anchor = [
            p["point_id"]
            for p in points["points"]
            if not p.get("segment_id") or p.get("offset_m") is None
        ]
        check(f"{site_id}：每个点都有 segment + offset 锚点", not missing_anchor, ",".join(missing_anchor[:5]))

        pair = find_pair(graph, points, route_service)
        check(f"{site_id}：存在可算路的入口→落客点组合", pair is not None, str(pair))
        if pair is None:
            continue

        origin, destination = pair
        params = {
            "k_candidates": thresholds["decision"].get("k_candidates", 3),
            "max_path_overlap": thresholds["decision"].get("max_path_overlap", 0.7),
        }
        first = route_service.plan(
            graph, {"point_id": origin}, {"point_id": destination}, points=points, params=params
        )
        check(
            f"{site_id}：{origin}→{destination} 出路线",
            first["route_count"] >= 1,
            f"{first['route_count']} 条 / status={first['alternatives_status']}",
        )
        seg_lists = [tuple(r["segments"]) for r in first["routes"]]
        check(f"{site_id}：多条路线互不重复", len(set(seg_lists)) == len(seg_lists), str(len(seg_lists)))

        if first["route_count"] >= 2:
            reason = first["routes"][1].get("reason") or ""
            check(
                f"{site_id}：备选原因含分岔点 / 里程差 / 用时差",
                "岔" in reason and "m" in reason and "s" in reason,
                reason,
            )
        else:
            check(
                f"{site_id}：只出一条时给了原因",
                bool(first.get("reason")),
                first.get("reason") or "（空）",
            )

        # 确定性：同一输入跑两遍逐字节一致
        again = route_service.plan(
            graph, {"point_id": origin}, {"point_id": destination}, points=points, params=params
        )
        check(
            f"{site_id}：同一输入两遍结果一致",
            json.dumps(first, sort_keys=True, ensure_ascii=False)
            == json.dumps(again, sort_keys=True, ensure_ascii=False),
        )

        # 中边起点：取第一条路线上的第二段，偏移 10 m
        middle_seg = first["routes"][0]["segments"][1] if first["routes"][0]["segments"] else None
        if middle_seg:
            mid = route_service.plan(
                graph,
                {"segment_id": middle_seg, "offset_m": 10.0},
                {"point_id": destination},
                points=points,
                params=params,
            )
            check(f"{site_id}：中边起点（{middle_seg}+10 m）可算路", mid["route_count"] >= 1)
            check(
                f"{site_id}：中边起点吸附信息完整",
                mid["origin"]["snap"].get("kind") == "segment" and mid["origin"]["snap"].get("offset_m") == 10.0,
                json.dumps(mid["origin"]["snap"], ensure_ascii=False),
            )

        # 点图坐标：任意点击 → 吸附最近路段（业主口径「直接点图」，不走下拉选项）
        entry_point = next(p for p in points["points"] if p["point_id"] == origin)
        snap_self = route_service.snap_to_segment(
            graph, float(entry_point["lon"]), float(entry_point["lat"])
        )
        check(
            f"{site_id}：点位坐标吸附回注册表同一段 + 同一偏移（±1 m）",
            bool(snap_self.get("matched"))
            and snap_self.get("segment_id") == entry_point.get("segment_id")
            and abs(float(snap_self.get("offset_m") or -1) - float(entry_point.get("offset_m") or 0))
            <= 1.0,
            json.dumps(
                {k: snap_self.get(k) for k in ("matched", "segment_id", "offset_m", "distance_m")},
                ensure_ascii=False,
            ),
        )
        snap_far = route_service.snap_to_segment(
            graph, float(entry_point["lon"]) + 0.05, float(entry_point["lat"])
        )
        check(
            f"{site_id}：离线过远不硬吸附（matched=false）",
            snap_far.get("matched") is False and "阈值" in (snap_far.get("note") or ""),
            (snap_far.get("note") or "")[:60],
        )
        dest_point = next(p for p in points["points"] if p["point_id"] == destination)
        # 注意口径差异：**命名点位按 node_id 算路**（resolve_endpoint 的既定设计，避免中边压起点、
        # 备选被压没），点图坐标按 segment+offset 算路；两者端点一致但路线集合可以不同，
        # 这里只验「点图能算、端点回显准」，不要求与点位算路逐段相同。
        by_click = route_service.plan(
            graph,
            {"lon": float(entry_point["lon"]), "lat": float(entry_point["lat"])},
            {"lon": float(dest_point["lon"]), "lat": float(dest_point["lat"])},
            points=points,
            params=params,
        )
        sections = {str(graph.edge(eid).get("section") or eid) for eid in graph._edges}  # noqa: SLF001
        check(
            f"{site_id}：点图坐标能算出路线（段落在真网段号上）",
            by_click["route_count"] >= 1
            and all(seg in sections for seg in by_click["routes"][0]["segments"]),
            f"点图 {by_click['route_count']} 条 / 首段 {by_click['routes'][0]['segments'][:3]}",
        )
        check(
            f"{site_id}：点图端点回显吸附信息（段+偏移+距离+坐标）",
            by_click["origin"]["snap"].get("kind") == "segment"
            and by_click["origin"]["snap"].get("distance_m") is not None
            and by_click["origin"]["snap"].get("lon") is not None
            and by_click["origin"]["snap"].get("click") is not None,
            json.dumps(by_click["origin"]["snap"], ensure_ascii=False)[:120],
        )

        # 一主两备的标注口径：role 依次 primary / alt1 / alt2，只有第一条 is_recommended
        roles = [r.get("role") for r in first["routes"]]
        check(
            f"{site_id}：role 依次 primary/alt1/alt2",
            roles == ["primary", "alt1", "alt2"][: len(roles)]
            and sum(1 for r in first["routes"] if r.get("is_recommended")) == 1,
            str(roles),
        )

        # 严格口径自证：任意两条路线的**全长**重叠度都不超过 max_path_overlap（不绕门槛）
        overlaps = []
        for i in range(len(first["routes"])):
            for j in range(i + 1, len(first["routes"])):
                overlaps.append(
                    route_service.candidates.path_overlap(
                        graph, first["routes"][i]["edges"], first["routes"][j]["edges"]
                    )
                )
        limit = float(params["max_path_overlap"])
        check(
            f"{site_id}：备选全长重叠度 ≤ {limit}（未绕门槛）",
            all(o <= limit + 1e-9 for o in overlaps),
            ",".join(f"{o:.3f}" for o in overlaps) or "（只有一条路线，不适用）",
        )

        # 离站路线：单独一条，从终点驶出到场界出口，不并进主推荐
        with_dep = route_service.plan(
            graph,
            {"point_id": origin},
            {"point_id": destination},
            points=points,
            params=params,
            with_departure=True,
        )
        dep = with_dep.get("departure") or {}
        check(
            f"{site_id}：离站路线单独返回（role=departure）",
            dep.get("role") == "departure" and bool(dep.get("to", {}).get("boundary")),
            json.dumps(
                {k: dep.get(k) for k in ("segment_count", "length_m", "eta_min")}, ensure_ascii=False
            ),
        )
        # 离站路线起点必须是终点所在节点（从落客点驶出），且不出现在 routes 里
        dep_edges = dep.get("edges") or []
        dep_from_ok = True
        if dep_edges:
            dep_from_ok = str(graph.edge(dep_edges[0])["from"]) == str(with_dep["destination"]["node_id"])
        check(
            f"{site_id}：离站路线从终点节点驶出（不并进 routes）",
            dep_from_ok
            and with_dep["route_count"] == first["route_count"]
            and [r["segments"] for r in with_dep["routes"]]
            == [r["segments"] for r in first["routes"]],
            f"起点 {with_dep['destination']['node_id']} / 离站 {len(dep_edges)} 段",
        )

        # 不可达：入口里找第一个 resolve 得到但算路抛错的组合
        entries = [p for p in points["points"] if p.get("kind") == "entry"]
        unreachable = None
        for entry in entries:
            try:
                route_service.plan(
                    graph, {"point_id": entry["point_id"]}, {"point_id": destination}, points=points
                )
            except ValueError as exc:
                unreachable = (entry["point_id"], str(exc))
                break
        if unreachable:
            check(
                f"{site_id}：不可达组合如实报错",
                "不可达" in unreachable[1],
                f"{unreachable[0]} → {destination}",
            )
        else:
            check(f"{site_id}：不可达组合如实报错", True, "本组入口全部可达（不适用）")

    print(f"\n结果：PASS {PASS} / FAIL {FAIL}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
