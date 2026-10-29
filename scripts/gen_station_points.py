#!/usr/bin/env python3
"""生成站点点位注册表 `stations/<site_id>.points.json`。

## 为什么要这张表

一期起终点只能由引擎按边界**自动推导**（`work/engine/realnet.py::derive_od_pairs`），
页面没有"选一个起点 / 选一个终点"的入口；`stations/points.json` 又是 7 节点
样例网的 `SEG-###` 点，真网用不上（`_load_real_dataset` 显式 `points: []`）。

本脚本把「可选的起点 / 终点」落成一份**真网锚定过的注册表**：
每个点都带 `node_id`（拓扑锚点）+ `segment_id` / `offset_m`（路段锚点，里程从
**行进方向的起点**算），供引擎算路（`work/engine/route_service.py`）、
接口层 `GET /api/traffic/route/points` 与前端下拉框共用。

## 数据来源（不编坐标）

| 点类型 | 几何来源 | 说明 |
|---|---|---|
| `entry` | 真网 `boundary_role == "entry"` 节点 + 该节点第一条出边 | 节点经纬度来自 OSM |
| `dropoff` / `zone` | `work/engine/inputs/station-landmarks.json`（由站点包 `dropoffs` / `zones` 生成） | 站点包坐标是**演示点**，`source=demo` / `verified=false` |

真网图与引擎**同一套**（`realnet.normalize_network` + `network.Graph`），
避免"生成器用无向边、算路用有向边"两套语义。

## 用法

    python scripts/gen_station_points.py                 # 生成全部站点（默认）
    python scripts/gen_station_points.py --site zhaoqingdong
    python scripts/gen_station_points.py --check         # 只校验已生成的表

## 校验（--check，五项）

1. `point_id` 唯一；
2. 必填字段齐（`point_id/name/kind/lon/lat/source/verified`）；
3. 锚点存在：`node_id` 在真网节点表里、`segment_id` 在真网边表里；
4. `offset_m` 落在线段长度内；
5. 点到所属线段折线的距离 ≤ 100 m（超了说明锚错边）。

退出码：0=通过 / 1=有问题（逐条打印）。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / "work" / "engine"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

import network  # noqa: E402  (work/engine/network.py)
import realnet  # noqa: E402  (work/engine/realnet.py)

SITE_RANGES = ROOT / "work" / "twin" / "site-ranges.json"
LANDMARKS = ROOT / "work" / "engine" / "inputs" / "station-landmarks.json"
POINTS_DIR = ROOT / "stations"
SCHEMA_VERSION = "1.0"
GENERATOR_VERSION = "2026-10-27"

#: 站点包没给标定参数时的兜底（仅用于补长度/速度算权重，不写进点位表）
FALLBACK_GRADING = {"defaults": {"v_f_kmh": 40.0, "c_vph": 1600.0}}

#: 点到所属线段折线的允许偏差（米）；超过视为锚错边
MAX_ANCHOR_DISTANCE_M = 100.0
#: 地标表自带 distance_m 的二次核验上限
MAX_LANDMARK_DISTANCE_M = 120.0


# ---------------------------------------------------------------- 几何工具
def _meters_per_deg(lat: float) -> tuple[float, float]:
    """WGS-84 经纬度 → 米（局部等距近似，站区 1 km 内误差可忽略）。"""
    lat_rad = math.radians(lat)
    m_per_deg_lat = 111_132.92 - 559.82 * math.cos(2 * lat_rad) + 1.175 * math.cos(4 * lat_rad)
    m_per_deg_lon = 111_412.84 * math.cos(lat_rad) - 93.5 * math.cos(3 * lat_rad)
    return m_per_deg_lon, m_per_deg_lat


def project_on_polyline(
    point: tuple[float, float],
    coords: list[list[float]],
    length_m: float | None = None,
) -> tuple[float, float]:
    """把 (lon, lat) 投影到折线，返回 (沿线里程 m, 点到折线距离 m)。

    里程从折线第一个点起算；`length_m` 给了就按折线实际长度与名义长度的比例缩放
    （真网 `length_m` 来自 OSM way，比折线直线距离略长）；没给就用折线实际长度。
    """
    lon0, lat0 = point
    mx, my = _meters_per_deg(lat0)
    pts = [((lon - lon0) * mx, (lat - lat0) * my) for lon, lat in coords]
    best_dist = float("inf")
    best_acc = 0.0
    acc = 0.0
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        dx, dy = bx - ax, by - ay
        seg_len = math.hypot(dx, dy)
        if seg_len <= 1e-9:
            continue
        t = max(0.0, min(1.0, ((-ax) * dx + (-ay) * dy) / (seg_len**2)))
        px, py = ax + t * dx, ay + t * dy
        dist = math.hypot(px, py)
        if dist < best_dist:
            best_dist = dist
            best_acc = acc + t * seg_len
        acc += seg_len
    if not math.isfinite(best_dist):
        return 0.0, float("inf")
    if length_m and acc > 0:
        return best_acc / acc * float(length_m), best_dist
    return best_acc, best_dist


# ---------------------------------------------------------------- 数据加载
def load_sites(site_id: str | None) -> list[dict[str, Any]]:
    payload = json.loads(SITE_RANGES.read_text(encoding="utf-8"))
    sites = payload.get("sites") or []
    if site_id:
        sites = [s for s in sites if s.get("site_id") == site_id]
        if not sites:
            raise SystemExit(f"站点 {site_id} 不在 {SITE_RANGES.relative_to(ROOT)}")
    return sites


def load_landmarks() -> dict[str, Any]:
    if not LANDMARKS.is_file():
        return {}
    return json.loads(LANDMARKS.read_text(encoding="utf-8"))


def load_graph(site: dict[str, Any]) -> tuple[network.Graph, dict[str, Any]]:
    payload, topo_meta = realnet.load_network_payload(site)
    graph_payload, net_meta = realnet.normalize_network(payload, site, FALLBACK_GRADING)
    return network.Graph(graph_payload), {**topo_meta, **net_meta}


# ---------------------------------------------------------------- 生成
def _entry_points(graph: network.Graph) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    entries = sorted(
        node_id
        for node_id in graph.node_ids
        if str(graph.node(node_id).get("boundary_role") or "") == "entry"
    )
    for index, node_id in enumerate(entries, start=1):
        node = graph.node(node_id)
        edge_ids = list(graph.out_edges(node_id))
        edge_ids.sort(
            key=lambda eid: (
                str(graph.edge(eid).get("kind") or "") != "main",
                -float(graph.edge(eid).get("length_m") or 0.0),
                str(graph.edge(eid).get("section") or eid),
            )
        )
        edge = graph.edge(edge_ids[0]) if edge_ids else {}
        road = str(edge.get("name_raw") or "").strip()
        name = f"外围入口 {node_id}"
        if road:
            name = f"{name} · {road}"
        out.append(
            {
                "point_id": f"ENT-{index:03d}",
                "name": name,
                "kind": "entry",
                "lon": round(float(node["lon"]), 7),
                "lat": round(float(node["lat"]), 7),
                "node_id": node_id,
                "segment_id": edge.get("section"),
                "offset_m": 0.0,
                "direction": str(edge.get("direction") or "forward"),
                "role": "boundary",
                "capacity_vph": None,
                "walk_min": None,
                "access_m": 0.0,
                "source": "osm",
                "verified": False,
                "version": GENERATOR_VERSION,
                "note": f"边界节点 boundary_role=entry；几何取自 OSM 节点 {node_id}，未现场踏勘",
            }
        )
    return out


def _nearest_directed_edge(
    graph: network.Graph, lon: float, lat: float, prefer_section: str | None = None
) -> tuple[dict[str, Any] | None, float, float]:
    """在真网**有向边**里找离该点最近的一条，返回 (边, 里程, 距离)。

    `offset_m` 从**行进方向的起点**（边的 `from` 端）算，不是从 OSM way 的起点算；
    两个方向的边各算一次，取距离更近的那条（并列时优先 `prefer_section`）。
    """
    best: tuple[float, int, dict[str, Any], float] | None = None
    for edge_id in graph._edges:  # noqa: SLF001 - 只读遍历，不修改图
        edge = graph.edge(edge_id)
        coords = edge.get("coords") or []
        if len(coords) < 2:
            continue
        offset, dist = project_on_polyline((lon, lat), coords, edge.get("length_m"))
        prefer_rank = 0 if prefer_section and str(edge.get("section")) == prefer_section else 1
        if best is None or (round(dist, 3), prefer_rank) < (best[0], best[1]):
            best = (round(dist, 3), prefer_rank, edge, offset)
    if best is None:
        return None, 0.0, float("inf")
    return best[2], best[3], best[0]


def _landmark_points(
    graph: network.Graph, landmarks: dict[str, Any], site_id: str
) -> list[dict[str, Any]]:
    station = (landmarks.get("stations") or {}).get(site_id) or {}
    rows = station.get("landmarks") or station.get("dropoffs") or []
    out: list[dict[str, Any]] = []
    for row in rows:
        lon, lat = float(row["lon"]), float(row["lat"])
        edge, offset, dist = _nearest_directed_edge(graph, lon, lat, row.get("segment_id"))
        kind = str(row.get("kind") or "dropoff")
        if kind not in ("dropoff", "zone", "pickup", "parking"):
            kind = "dropoff"
        notes = [f"站点包{'场区' if kind == 'zone' else '落客点'}（演示坐标）"]
        if edge is not None:
            notes.append(
                f"锚定到 {edge.get('section')}（{edge.get('direction')}）偏移 {offset:.1f} m，"
                f"点到折线 {dist:.1f} m"
            )
        if abs(float(row.get("distance_m") or 0.0)) > MAX_LANDMARK_DISTANCE_M:
            notes.append(f"地标表距离 {row.get('distance_m')} m 偏大，待复核")
        out.append(
            {
                "point_id": str(row.get("id") or f"DROP-{len(out) + 1:02d}"),
                "name": str(row.get("name") or "落客点（演示点）"),
                "kind": kind,
                "lon": round(lon, 7),
                "lat": round(lat, 7),
                "node_id": row.get("node_id"),
                "segment_id": (edge or {}).get("section") or row.get("segment_id"),
                "offset_m": round(offset, 1) if edge is not None else None,
                "direction": str((edge or {}).get("direction") or "forward"),
                "role": "internal",
                "capacity_vph": None,
                "walk_min": None,
                "access_m": round(float(row.get("distance_m") or 0.0), 1),
                "source": "demo",
                "verified": False,
                "version": GENERATOR_VERSION,
                "note": "；".join(notes),
            }
        )
    return out


def build_site(site: dict[str, Any], landmarks: dict[str, Any]) -> tuple[dict[str, Any], network.Graph]:
    site_id = str(site["site_id"])
    graph, _meta = load_graph(site)
    entries = _entry_points(graph)
    landmark_points = _landmark_points(graph, landmarks, site_id)
    points = entries + landmark_points
    counts: dict[str, int] = {}
    for point in points:
        counts[point["kind"]] = counts.get(point["kind"], 0) + 1
    payload = {
        "is_simulated": True,
        "schema_version": SCHEMA_VERSION,
        "site_id": site_id,
        "site_name": site.get("site_name"),
        "crs": "WGS-84",
        "generated_by": "scripts/gen_station_points.py",
        "generator_version": GENERATOR_VERSION,
        "note": "起终点注册表（演示口径）：entry 来自 OSM 边界节点；dropoff / zone 是站点包演示点。"
        "坐标未现场踏勘，source / verified 如实标注，不得对外说成实测点位。",
        "source_layers": {
            "network": str(site.get("out_json")),
            "landmarks": str(LANDMARKS.relative_to(ROOT)) if LANDMARKS.is_file() else None,
        },
        "counts": {"total": len(points), **counts},
        "points": points,
    }
    return payload, graph


# ---------------------------------------------------------------- 校验
def check_payload(payload: dict[str, Any], graph: network.Graph) -> list[str]:
    errors: list[str] = []
    sections = {str(graph.edge(eid).get("section")) for eid in graph._edges}  # noqa: SLF001
    node_ids = set(graph.node_ids)
    seen: set[str] = set()
    for point in payload.get("points") or []:
        pid = str(point.get("point_id") or "")
        label = pid or "<无 point_id>"
        if not pid:
            errors.append("存在没有 point_id 的点")
            continue
        if pid in seen:
            errors.append(f"{label}：point_id 重复")
        seen.add(pid)
        for field in ("name", "kind", "lon", "lat", "source", "verified"):
            if point.get(field) in (None, ""):
                errors.append(f"{label}：缺必填字段 {field}")
        node_id = point.get("node_id")
        if node_id and str(node_id) not in node_ids:
            errors.append(f"{label}：node_id {node_id} 不在真网节点表")
        seg_id = point.get("segment_id")
        if not seg_id:
            errors.append(f"{label}：没有 segment_id（无法算路）")
            continue
        if str(seg_id) not in sections:
            errors.append(f"{label}：segment_id {seg_id} 不在真网边表")
            continue
        edge = next(
            (graph.edge(eid) for eid in graph._edges if str(graph.edge(eid).get("section")) == str(seg_id)),
            None,
        )  # noqa: SLF001
        if edge is None:
            continue
        length = float(edge.get("length_m") or 0.0)
        offset = point.get("offset_m")
        if offset is None:
            errors.append(f"{label}：有 segment_id 但 offset_m 为空")
        elif not (0.0 <= float(offset) <= length + 0.5):
            errors.append(f"{label}：offset_m {offset} 超出线段长度 {length:.1f} m")
        coords = edge.get("coords") or []
        if len(coords) >= 2 and point.get("lon") is not None:
            _, dist = project_on_polyline((float(point["lon"]), float(point["lat"])), coords, length)
            if dist > MAX_ANCHOR_DISTANCE_M:
                errors.append(f"{label}：点到 {seg_id} 折线 {dist:.1f} m（> {MAX_ANCHOR_DISTANCE_M:.0f} m）")
    return errors


# ---------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 / 校验站点点位注册表")
    parser.add_argument("--site", default=None, help="站点 id（缺省=登记表全部站点）")
    parser.add_argument("--check", action="store_true", help="只校验，不写文件")
    parser.add_argument("--out-dir", default=str(POINTS_DIR), help="输出目录（默认 stations/）")
    args = parser.parse_args(argv)

    sites = load_sites(args.site)
    landmarks = load_landmarks()
    out_dir = Path(args.out_dir)
    failures = 0

    if args.check:
        for site in sites:
            site_id = str(site["site_id"])
            path = out_dir / f"{site_id}.points.json"
            if not path.is_file():
                print(f"[FAIL] {site_id}：{path.name} 不存在")
                failures += 1
                continue
            graph, _meta = load_graph(site)
            payload = json.loads(path.read_text(encoding="utf-8"))
            errors = check_payload(payload, graph)
            if errors:
                failures += 1
                print(f"[FAIL] {site_id}：{len(errors)} 处问题")
                for err in errors:
                    print(f"       - {err}")
            else:
                counts = payload.get("counts") or {}
                detail = " / ".join(f"{k} {v}" for k, v in counts.items() if k != "total")
                print(f"[ OK ] {site_id}：{counts.get('total')} 个点（{detail}）")
        print("校验通过。" if failures == 0 else f"校验失败：{failures} 个站点有问题。")
        return 0 if failures == 0 else 1

    out_dir.mkdir(parents=True, exist_ok=True)
    for site in sites:
        site_id = str(site["site_id"])
        payload, graph = build_site(site, landmarks)
        errors = check_payload(payload, graph)
        if errors:
            failures += 1
            print(f"[FAIL] {site_id}：生成结果未过自检")
            for err in errors:
                print(f"       - {err}")
            continue
        path = out_dir / f"{site_id}.points.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        counts = payload["counts"]
        detail = " / ".join(f"{k} {v}" for k, v in counts.items() if k != "total")
        print(f"[ OK ] 写入 {path.relative_to(ROOT)}：{counts['total']} 个点（{detail}）")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
