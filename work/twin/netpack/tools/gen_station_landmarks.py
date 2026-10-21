#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""站点包落客点 → 真网节点映射生成器（Issue IKP5C6 追加，业主 2026-10-21）。

为什么需要：业主口径是「外围大道最外侧路段 = 起点，停车场落客点 = 终点」。引擎做 OD 推导时
只认真网节点，读不到前端站点包的 `dropoffs`（那是演示点，不是 `stations/points.json` 的 T1 真表）。
本脚本把站点包 `dropoffs` 的坐标映射到**最近的真网节点**，产出 `work/engine/inputs/station-landmarks.json`，
供 `realnet.derive_od_pairs()` 优先作为行程终点；映射不上就如实留空，不猜。

口径：
- 只读站点包（`station_pack_ts`）与真网产物（`out_json`），不写回、不改 `stations/*.json`；
- 坐标是站点包里的**演示点**，不是踏勘点位；输出 `is_simulated: true`；
- 每次生成结果确定性（同一输入 → 同一输出），可直接 `--check`。

用法（仓库根）：
    python work/twin/netpack/tools/gen_station_landmarks.py
    python work/twin/netpack/tools/gen_station_landmarks.py --check
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
OUT = ROOT / "work/engine/inputs/station-landmarks.json"
METERS_PER_DEG = 111_320.0

DROP_RE = re.compile(
    r"\{\s*id:\s*'([^']+)',\s*name:\s*'([^']+)',\s*lon:\s*([\d.]+),\s*lat:\s*([\d.]+),?\s*\}",
    re.S,
)


def meters(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    dx = (lon1 - lon2) * METERS_PER_DEG * math.cos(math.radians(lat1))
    dy = (lat1 - lat2) * METERS_PER_DEG
    return math.hypot(dx, dy)


def parse_dropoffs(pack_path: Path) -> list[dict]:
    text = pack_path.read_text(encoding="utf-8")
    start = text.find("dropoffs:")
    if start < 0:
        return []
    end = text.find("zones:", start)
    block = text[start : end if end > 0 else len(text)]
    out = []
    for pid, name, lon, lat in DROP_RE.findall(block):
        out.append({"id": pid, "name": name, "lon": float(lon), "lat": float(lat)})
    return out


def nearest_node(net: dict, lon: float, lat: float) -> tuple[str | None, float | None]:
    best = (None, None)
    for node in net.get("nodes") or []:
        d = meters(lon, lat, float(node["lon"]), float(node["lat"]))
        if best[1] is None or d < best[1]:
            best = (str(node["node_id"]), d)
    return best


def nearest_segment(net: dict, lon: float, lat: float) -> str | None:
    best = (None, None)
    for edge in net.get("edges") or []:
        for c in edge.get("coords") or []:
            d = meters(lon, lat, float(c[0]), float(c[1]))
            if best[1] is None or d < best[1]:
                best = (str(edge["segment_id"]), d)
    return best[0]


def build() -> dict:
    registry = json.loads(SITE_RANGES.read_text(encoding="utf-8"))
    stations: dict[str, dict] = {}
    for site in registry.get("sites") or []:
        site_id = str(site["site_id"])
        pack_path = ROOT / str(site.get("station_pack_meta_ts") or site["station_pack_ts"])
        net_path = ROOT / str(site["out_json"])
        if not pack_path.exists() or not net_path.exists():
            continue
        net = json.loads(net_path.read_text(encoding="utf-8"))
        dropoffs = parse_dropoffs(pack_path)
        rows = []
        for point in dropoffs:
            node_id, distance = nearest_node(net, point["lon"], point["lat"])
            rows.append(
                {
                    "id": point["id"],
                    "name": point["name"],
                    "lon": point["lon"],
                    "lat": point["lat"],
                    "node_id": node_id,
                    "segment_id": nearest_segment(net, point["lon"], point["lat"]),
                    "distance_m": None if distance is None else round(distance, 1),
                }
            )
        stations[site_id] = {"dropoffs": rows}
    return {
        "is_simulated": True,
        "kind": "station_landmarks",
        "note": (
            "站点包落客点（演示点）→ 真网最近节点映射，供引擎 OD 推导把行程终点优先落在停车场落客点；"
            "坐标不是踏勘点位，不参与判级 / 契约字段。生成器：work/twin/netpack/tools/gen_station_landmarks.py。"
        ),
        "stations": stations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成站点包落客点 → 真网节点映射")
    parser.add_argument("--check", action="store_true", help="只校验现有文件是否与生成结果一致")
    ns = parser.parse_args(argv)
    payload = build()
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if ns.check:
        if not OUT.exists():
            print(f"[FAIL] 缺少 {OUT.relative_to(ROOT)}")
            return 1
        if OUT.read_text(encoding="utf-8") != text:
            print(f"[FAIL] {OUT.relative_to(ROOT)} 与生成结果不一致，请重新生成")
            return 1
        print(f"[OK] {OUT.relative_to(ROOT)} 一致")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"[OK] 写出 {OUT.relative_to(ROOT)}（{sum(len(v['dropoffs']) for v in payload['stations'].values())} 个落客点）")
    return 0


if __name__ == "__main__":
    sys.exit(main())


