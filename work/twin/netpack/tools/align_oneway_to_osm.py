#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 OSM way 节点顺序校正真网 `oneway` 方向（Issue IKP5C6 追加，业主 2026-10-21）。

根因：`build_junction_pack.py` 把同名多条 OSM way 串成一条路时为端点吸附会反转几何朝向，
但 `oneway=yes` 仍按原 tag 原样写入 → 「几何 from→to」与真实单行方向相反。
本脚本只改 `oneway`（yes ↔ -1），不改几何 / 段号 / 节点；`--site-id` 指定站点（默认只 Z，
避免一次性改动 GZ 708 段的方向数据；GZ 待单独核）。

用法：
    python work/twin/netpack/tools/align_oneway_to_osm.py --site-id zhaoqingdong
    python work/twin/netpack/tools/align_oneway_to_osm.py --site-id zhaoqingdong --check
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SITE_RANGES = ROOT / "work/twin/site-ranges.json"
M = 111_320.0
TOL = 20.0

#: 现场口径覆盖（业主 2026-10-21 复查）：吉庆大道按「东→西单行」贯通，SZ-002/SZ-003 的
#: OSM way 顺序与整条路相反（该两段的 way_ids 混用了对向 way），自动检测无法判定；
#: 按现场口径统一为反向单行（travel 与几何 from→to 相反）。只影响方向，不改几何/段号。
SITE_OVERRIDES = {"zhaoqingdong": {"SZ-002", "SZ-003"}}


def parse_osm(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    nodes = {}
    for m in re.finditer(r'<node id="(\d+)"[^>]*lat="([\d.]+)"[^>]*lon="([\d.]+)"', text):
        nodes[m.group(1)] = (float(m.group(3)), float(m.group(2)))
    for m in re.finditer(r'<node id="(\d+)"[^>]*lon="([\d.]+)"[^>]*lat="([\d.]+)"', text):
        nodes.setdefault(m.group(1), (float(m.group(2)), float(m.group(3))))
    ways = {}
    for m in re.finditer(r'<way id="(\d+)"(.*?)</way>', text, re.S):
        refs = re.findall(r'<nd ref="(\d+)"', m.group(2))
        pts = [nodes[r] for r in refs if r in nodes]
        if len(pts) >= 2:
            ways[m.group(1)] = pts
    return ways


def dist(a, b):
    return math.hypot((a[0] - b[0]) * M * math.cos(math.radians(a[1])), (a[1] - b[1]) * M)


def reversed_vs_osm(edge, ways) -> bool:
    start, end = edge["coords"][0], edge["coords"][-1]
    votes = []
    for wid in edge.get("way_ids") or []:
        pts = ways.get(str(wid)) or []
        if len(pts) < 2:
            continue
        i = min(range(len(pts)), key=lambda k: dist(start, pts[k]))
        j = min(range(len(pts)), key=lambda k: dist(end, pts[k]))
        if dist(start, pts[i]) > TOL or dist(end, pts[j]) > TOL:
            continue
        votes.append(1 if i < j else -1)
    return sum(1 for v in votes if v < 0) > sum(1 for v in votes if v > 0)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-id", default="zhaoqingdong")
    parser.add_argument("--check", action="store_true")
    ns = parser.parse_args(argv)
    registry = json.loads(SITE_RANGES.read_text(encoding="utf-8"))
    site = next((s for s in registry["sites"] if s["site_id"] == ns.site_id), None)
    if site is None:
        print(f"[FAIL] 登记表没有 site_id={ns.site_id}")
        return 1
    net_path = ROOT / site["out_json"]
    osm_path = ROOT / site["osm_file"]
    net = json.loads(net_path.read_text(encoding="utf-8"))
    ways = parse_osm(osm_path)
    flipped = []
    for edge in net.get("edges") or []:
        if edge.get("oneway") not in ("yes", "-1"):
            continue
        desired = "-1" if reversed_vs_osm(edge, ways) else "yes"
        if edge["segment_id"] in SITE_OVERRIDES.get(ns.site_id, set()):
            desired = "-1"
        if edge.get("oneway") == desired:
            continue
        old = edge["oneway"]
        edge["oneway"] = desired
        flipped.append({"segment_id": edge["segment_id"], "name": edge.get("name"), "from": old, "to": edge["oneway"]})
    net.setdefault("direction_alignment", {}).update(
        {
            "site_id": ns.site_id,
            "flipped": len(flipped),
            "segments": len(net.get("edges") or []),
            "note": (
                "oneway 已按 OSM way 节点顺序对齐（build_junction_pack 串 way 时可能反转几何但未翻转 oneway）；"
                "只改 oneway，不改几何 / 段号 / 节点。"
            ),
        }
    )
    if ns.check:
        ok = not flipped
        print(f"[{'OK' if ok else 'FAIL'}] {ns.site_id}：{'已对齐' if ok else f'仍有 {len(flipped)} 段未对齐'}")
        return 0 if ok else 1
    net_path.write_text(json.dumps(net, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"[OK] {ns.site_id}：翻转 {len(flipped)} 段（共 {len(net['edges'])} 段）")
    for row in flipped:
        print("  ", row["segment_id"], row["name"], row["from"], "→", row["to"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
