#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离站回程（?view=departure）三方对照：静态方向层 / 路线箭头（steps 行进序）/ 后端 steps 几何。

判据分两类（lead 2026-10-29 明确）：
  A. 正向段（edge_id 无 _rev 后缀，如 SZ-005）：静态 rotate 与 steps 行进序方位**应当逐度相等** —— 硬判据。
  B. 双向段（edge_id 形如 SZ-036_rev）：静态层是共轴双头，rotate 只是轴、没有正反 ——
     只能证明「轴一致」（|Δ mod 180| ≈ 0）；方向对不对只看 steps 几何本身 + 端点标记。

routeRotate / staticRotate 来自 work/verify/_departure_rows.json（在 1440×900 的浏览器里从
map 的 route-arrow 源与 direction 源 features 原样读出来的，不在本脚本里重算）。

输出：work/verify/departure_check.json + stdout 表格。
"""
from __future__ import annotations

import json
import math
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.join(ROOT, "work", "verify")
NETPACK = os.path.join(ROOT, "work", "twin", "netpack", "network_junction.json")
ROWS = os.path.join(HERE, "_departure_rows.json")
API = os.path.join(HERE, "api")
SNAPSHOT = os.path.join(HERE, "direction_snapshot.json")
OUT = os.path.join(HERE, "departure_check.json")


def load_edges() -> dict[str, dict]:
    net = json.load(open(NETPACK, encoding="utf-8"))
    return {e["segment_id"]: e for e in net["edges"]}


def travel_coords(edge: dict, from_node: str) -> list[list[float]]:
    """行进序 coords：以 steps 声明的 from_node 为准决定是否反序。

    不能只看 edge_id 有没有 `_rev` 后缀：反向单行段（oneway=-1，edge_id 不带后缀）也是反序行进。
    """
    coords = [list(p) for p in edge["coords"]]
    return coords[::-1] if from_node and from_node != edge["from"] else coords


def arc_len(coords: list[list[float]]) -> tuple[list[float], float, float]:
    lon_scale = 111_320 * math.cos(coords[0][1] * math.pi / 180)
    lens: list[float] = []
    total = 0.0
    for i in range(1, len(coords)):
        dx = (coords[i][0] - coords[i - 1][0]) * lon_scale
        dy = (coords[i][1] - coords[i - 1][1]) * 111_320
        length = math.hypot(dx, dy)
        lens.append(length)
        total += length
    return lens, total, lon_scale


def point_at(coords: list[list[float]], s: float) -> list[float]:
    lens, total, _ = arc_len(coords)
    remain = min(total, max(0.0, s))
    for i, length in enumerate(lens):
        if remain <= length or i == len(lens) - 1:
            t = 0.0 if length <= 0 else remain / length
            x = coords[i][0] + (coords[i + 1][0] - coords[i][0]) * t
            y = coords[i][1] + (coords[i + 1][1] - coords[i][1]) * t
            return [x, y]
        remain -= length
    return list(coords[-1])


def tangent_bearing(coords: list[list[float]], fraction: float = 0.5, span_m: float = 15.0) -> float:
    """与前端 shared/directions.ts:280 tangentBearingAt 同式：按弧长取 ±half 两点求方位角。"""
    _, total, lon_scale = arc_len(coords)
    if total <= 0:
        return 0.0
    half = min(span_m, total / 4)
    mid = max(0.0, min(total, fraction * total))
    a = point_at(coords, mid - half)
    b = point_at(coords, mid + half)
    dx = (b[0] - a[0]) * lon_scale
    dy = (b[1] - a[1]) * 111_320
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return 0.0
    return math.degrees(math.atan2(dx, dy)) % 360


def dist_m(a: list[float], b: list[float]) -> float:
    lon_scale = 111_320 * math.cos(a[1] * math.pi / 180)
    return math.hypot((b[0] - a[0]) * lon_scale, (b[1] - a[1]) * 111_320)


def ang_delta(a: float, b: float) -> float:
    d = abs((a - b) % 360)
    return min(d, 360 - d)


def find_departure_route(want: set[str]) -> tuple[str, str, dict]:
    for req in ("0001", "0002", "0003", "0004"):
        path = os.path.join(API, f"steps-REQ-REAL-{req}.json")
        if not os.path.exists(path):
            continue
        doc = json.load(open(path, encoding="utf-8"))
        routes = doc.get("routes") or {}
        cands: list[tuple[str, dict]] = []
        dep = routes.get("departure_route")
        if isinstance(dep, dict):
            cands.append(("departure_route", dep))
        for i, alt in enumerate(routes.get("alternatives") or []):
            if isinstance(alt, dict):
                cands.append((f"alternatives[{i}]", alt))
        for name, route in cands:
            edges = {s.get("edge_id") for s in (route.get("steps") or [])}
            # 浏览器 queryRenderedFeatures 只返回视野内的箭头（实测 10/16 支），所以用超集匹配
            if want <= edges:
                return f"REQ-REAL-{req}", name, route
    raise SystemExit("找不到与离站截图边集合一致的路线")


SNAPSHOT_SEGMENTS: dict[str, dict] = {}


def main() -> int:
    edges = load_edges()
    snap = json.load(open(SNAPSHOT, encoding="utf-8"))
    SNAPSHOT_SEGMENTS.update(snap.get("segments") or {})
    rows_doc = json.load(open(ROWS, encoding="utf-8"))
    rows = {r["edge_id"]: r for r in rows_doc["rows"]}
    want = set(rows)
    req_id, route_name, route = find_departure_route(want)

    print(f"路线来源：GET /api/traffic/route/{req_id}/steps → routes.{route_name}"
          f"（{len(route.get('steps') or [])} steps，length_m={route.get('length_m')}）")
    sp = route.get("start_point") or {}
    dp = route.get("destination_point") or {}
    print(f"start_point={json.dumps(sp, ensure_ascii=False)}")
    print(f"destination_point={json.dumps(dp, ensure_ascii=False)}")
    print()

    head = ("段", "edge_id", "类", "route°", "static°", "steps行进°", "Δroute", "Δstatic", "轴Δ", "起点距m", "终点距m")
    print(" | ".join(head))
    nodes = {n["node_id"]: [n["lon"], n["lat"]] for n in json.load(open(NETPACK, encoding="utf-8"))["nodes"]}
    items = []
    for step in route.get("steps") or []:
        edge_id = step.get("edge_id") or ""
        seg = step.get("segment_id") or edge_id.replace("_rev", "")
        row = rows.get(edge_id)
        edge = edges[seg]
        coords = travel_coords(edge, step.get("from_node"))
        bearing_net = tangent_bearing(coords)
        geom = [list(p) for p in (step.get("geometry") or [])]
        bearing_geom = tangent_bearing(geom) if len(geom) >= 2 else None
        # 类别按「这段有没有正向反两义」判定：L2 快照的 direction 字段是唯一口径
        snap_dir = SNAPSHOT_SEGMENTS.get(seg, {}).get("direction")
        is_bidi = snap_dir == "bidirectional"
        # 端点标记：steps 声明的 from_node/to_node 与「行进序几何」首末点是否同一个节点
        d_from = dist_m(geom[0], nodes[step["from_node"]]) if geom and step.get("from_node") in nodes else None
        d_to = dist_m(geom[-1], nodes[step["to_node"]]) if geom and step.get("to_node") in nodes else None
        static = float(row["staticRotate"]) if row else None
        route_rot = float(row["routeRotate"]) if row else None
        d_route = ang_delta(route_rot, bearing_net) if row else None
        d_static = ang_delta(static, bearing_net) if row else None
        axis = min(d_static, abs(180 - d_static)) if row else None
        items.append({
            "segment_id": seg,
            "edge_id": edge_id,
            "class": "双向段" if is_bidi else f"单向段({snap_dir})",
            "route_rotate_deg": route_rot,
            "static_rotate_deg": static,
            "steps_travel_bearing_deg": round(bearing_net, 3),
            "steps_geometry_bearing_deg": None if bearing_geom is None else round(bearing_geom, 3),
            "netpack_vs_geometry_bearing_deg": None if bearing_geom is None else round(ang_delta(bearing_net, bearing_geom), 3),
            "delta_route_deg": None if d_route is None else round(d_route, 3),
            "delta_static_deg": None if d_static is None else round(d_static, 3),
            "axis_delta_deg": None if axis is None else round(axis, 3),
            "step_from_node": step.get("from_node"),
            "step_to_node": step.get("to_node"),
            "geometry_start_is_from_node_m": None if d_from is None else round(d_from, 3),
            "geometry_end_is_to_node_m": None if d_to is None else round(d_to, 3),
            "in_viewport": bool(row),
            "screen": (row or {}).get("screen"),
        })
        fmt = lambda v, n=1: "—" if v is None else f"{v:.{n}f}"
        print(f"{seg} | {edge_id} | {items[-1]['class']} | {fmt(route_rot)} | {fmt(static)} | "
              f"{bearing_net:.1f} | {fmt(d_route,2)} | {fmt(d_static,2)} | {fmt(axis,2)} | "
              f"{fmt(d_from,2)} | {fmt(d_to,2)} | {'是' if row else '视野外'}")

    inview = [x for x in items if x["in_viewport"]]
    one_way = [x for x in inview if not x["class"] == "双向段"]
    bidi = [x for x in inview if x["class"] == "双向段"]
    max_route = max((x["delta_route_deg"] for x in inview), default=None)
    max_static_one_way = max((x["delta_static_deg"] for x in one_way), default=None)
    max_axis_bidi = max((x["axis_delta_deg"] for x in bidi), default=None)
    max_net_vs_geom = max((x["netpack_vs_geometry_bearing_deg"] for x in items
                           if x["netpack_vs_geometry_bearing_deg"] is not None), default=None)
    max_from = max((x["geometry_start_is_from_node_m"] for x in items if x["geometry_start_is_from_node_m"] is not None), default=None)
    max_to = max((x["geometry_end_is_to_node_m"] for x in items if x["geometry_end_is_to_node_m"] is not None), default=None)
    print()
    print(f"单向段 {len(one_way)} 条：Δ(静态-行进) 最大 {max_static_one_way:.3f}°  ← 硬判据（限 0.5°）")
    print(f"双向段 {len(bidi)} 条：轴Δ 最大 {max_axis_bidi:.3f}°  ← 只证共轴（限 0.5°）")
    print(f"全部 {len(inview)} 条（视野内）：Δ(路线箭头-行进) 最大 {max_route:.3f}°  ← 路线箭头必须严格同向（限 0.5°）")
    print(f"netpack 反推方位 vs 后端 geometry 方位：最大 {max_net_vs_geom:.3f}°（两份独立几何必须一致，限 0.5°）")
    print(f"端点标记：{len(items)} 步中 geometry 首点距 from_node 最大 {max_from:.3f} m、"
          f"末点距 to_node 最大 {max_to:.3f} m  ← 行进序端点（限 0.5 m）")

    out = {
        "check": "departure_three_way",
        "request_id": req_id,
        "route_section": f"routes.{route_name}",
        "note": "routeRotate/staticRotate 由浏览器从 map features 原样读出；steps_travel_bearing_deg 由本脚本按 "
                "shared/directions.ts:280 同式独立重算；二者独立来源，任一为真即可互证。",
        "viewport_note": "截图 work/verify/shots/shot_departure_1440.png（1440×900，zoom 16.33）。"
                         "该图底图瓦片离线，画面里的灰色折线是前端自绘的站区几何，不是真实底图。",
        "pass": {
            "one_way_static_equals_travel": {"max_delta_deg": max_static_one_way, "limit_deg": 0.5,
                                             "ok": max_static_one_way is not None and max_static_one_way <= 0.5},
            "bidirectional_axis_aligned": {"max_axis_delta_deg": max_axis_bidi, "limit_deg": 0.5,
                                           "ok": max_axis_bidi is not None and max_axis_bidi <= 0.5},
            "route_arrow_matches_travel": {"max_delta_deg": max_route, "limit_deg": 0.5,
                                           "ok": max_route is not None and max_route <= 0.5},
            "netpack_agrees_with_steps_geometry": {"max_delta_deg": max_net_vs_geom, "limit_deg": 0.5,
                                                   "ok": max_net_vs_geom is not None and max_net_vs_geom <= 0.5},
            "endpoint_markers_travel_order": {"max_from_node_m": max_from, "max_to_node_m": max_to,
                                              "limit_m": 0.5,
                                              "ok": max_from is not None and max_to is not None
                                                    and max_from <= 0.5 and max_to <= 0.5},
        },
        "start_point": sp,
        "destination_point": dp,
        "rows": items,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"\n写入 {OUT}")
    return 0 if all(v["ok"] for v in out["pass"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
