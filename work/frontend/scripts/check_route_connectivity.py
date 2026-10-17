#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IKMF1W 自检：大屏演示路线的**相邻性**（连通性）检查。

口径（照 Issue IKMF1W 自检 ①）：
  一条路线的相邻两段必须真的接上 —— 一段的端点落在另一段折线上（含中间顶点）≤ 25 m，
  不能只看首尾点。

数据来源（都是仓库内脚本产物 / 数据，不手抄）：
  · 几何：``work/twin/netpack/network_junction.json``（61 段，build_junction_pack.py 产物）
  · 路线：``work/frontend/ui-vue/src/station-packs/stationZ.ts`` 的 ``recommend`` 数据
    （arrival_segments / alternatives[].segments / departure_segments）

用法（仓库根目录）：
  python work/frontend/scripts/check_route_connectivity.py
退出码 0 = 全部连通；1 = 有不连通 / 悬空段号。
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

# Windows 控制台默认 GBK：中文可编码，但 ✅ / ❌ 会抛 UnicodeEncodeError，统一用 ASCII 标记。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 —— 老 Python / 被重定向时忽略
    pass

ROOT = Path(__file__).resolve().parents[3]
NET_PATH = ROOT / "work/twin/netpack/network_junction.json"
PACK_PATH = ROOT / "work/frontend/ui-vue/src/station-packs/stationZ.ts"

R_EARTH = 6371000.0
RAD = math.pi / 180.0
LAT0 = 23.214
TOL_M = 25.0


def xy(lon: float, lat: float) -> tuple[float, float]:
    return (lon * R_EARTH * RAD * math.cos(LAT0 * RAD), lat * R_EARTH * RAD)


def point_segment_distance(p, a, b) -> float:
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def adjacent(a_seg, b_seg, polys) -> bool:
    """两段是否接上：任一段的端点落在另一段折线（逐线段）≤ TOL_M。"""
    a = polys[a_seg]
    b = polys[b_seg]
    for p in (a[0], a[-1]):
        for i in range(len(b) - 1):
            if point_segment_distance(p, b[i], b[i + 1]) <= TOL_M:
                return True
    for p in (b[0], b[-1]):
        for i in range(len(a) - 1):
            if point_segment_distance(p, a[i], a[i + 1]) <= TOL_M:
                return True
    return False


def parse_routes(text: str) -> list[tuple[str, list[str]]]:
    """从站点包 TS 里抽 recommend 的三组段序列（只读，不改数据）。"""
    routes: list[tuple[str, list[str]]] = []

    def grab_array(block: str, field: str) -> list[str] | None:
        m = re.search(field + r"\s*:\s*\[(.*?)\]", block, re.S)
        if not m:
            return None
        return re.findall(r"'([^']+)'", m.group(1))

    m = re.search(r"recommend\s*:\s*\{(.*?)\n  \},", text, re.S)
    if not m:
        raise SystemExit("❌ stationZ.ts 里找不到 recommend 数据块")
    block = m.group(1)

    arrival = grab_array(block, "arrival_segments")
    departure = grab_array(block, "departure_segments")
    if arrival:
        routes.append(("推荐", arrival))
    if departure:
        routes.append(("离站", departure))

    alt_block = re.search(r"alternatives\s*:\s*\[(.*?)\n    \]", block, re.S)
    if alt_block:
        for i, segs in enumerate(
            re.findall(r"segments\s*:\s*\[(.*?)\]", alt_block.group(1), re.S), start=1
        ):
            routes.append((f"备选 {i}", re.findall(r"'([^']+)'", segs)))
    return routes


def main() -> int:
    net = json.loads(NET_PATH.read_text(encoding="utf-8"))
    polys = {
        e["segment_id"]: [xy(lon, lat) for lon, lat in e["coords"]]
        for e in net["edges"]
    }
    routes = parse_routes(PACK_PATH.read_text(encoding="utf-8"))
    print(f"路网：{len(polys)} 段（{NET_PATH.name}）；路线：{len(routes)} 条")
    if len(routes) < 3:
        print("❌ 路线数 < 3（契约要求 1 推荐 + 2 备选）")
        return 1

    failed = 0
    for name, segs in routes:
        if not segs:
            print(f"❌ {name}：段序列为空")
            failed += 1
            continue
        dangling = [s for s in segs if s not in polys]
        if dangling:
            print(f"❌ {name}：悬空段号 {dangling}（不在 61 段路网里）")
            failed += 1
            continue
        broken = [
            (segs[i], segs[i + 1])
            for i in range(len(segs) - 1)
            if not adjacent(segs[i], segs[i + 1], polys)
        ]
        if broken:
            print(f"❌ {name}：{len(broken)} 处不相邻 {broken}")
            failed += 1
        else:
            print(f"✅ {name}：{len(segs)} 段全部相邻（{' → '.join(segs)}）")

    if failed:
        print(f"\n❌ 自检失败：{failed} 条路线不连通")
        return 1
    print("\n✅ 自检通过：所有演示路线相邻段全部连通")
    return 0


if __name__ == "__main__":
    sys.exit(main())
