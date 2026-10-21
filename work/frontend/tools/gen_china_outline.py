#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 `src/assets/geo/china-outline.geojson`：全国视角的底图兜底轮廓（Issue IKPFVN）。

为什么要有这个文件：大屏全国视角只画两个已接入车站的 pin，底图（OpenFreeMap 在线矢量瓦片）
一旦拉不到，画面就只剩两个点 —— 等于白屏。这份**本地**轮廓让"底图不可用"时仍有中国范围可看，
并且和站点 pin 一起把"这两个站在哪儿"讲清楚。

数据与许可：Natural Earth 1:110m admin-0 countries（**公有领域 / public domain**，
https://www.naturalearthdata.com/about/terms-of-use/ ）。本脚本只做三件事：
① 取 `ADMIN == "China"` 的那个 feature；② Douglas–Peucker 抽稀；③ 坐标保留 3 位小数。
**不做任何边界推断**：轮廓完全来自 Natural Earth 的现成几何，抽稀后可能偏移数百米，
故本文件只作**示意**，页面必须标注"轮廓简化、仅作定位参考、不代表边界主张"。

用法（仓库根）：

    python work/frontend/tools/gen_china_outline.py --source ne_110m_admin_0_countries.geojson
    python work/frontend/tools/gen_china_outline.py --source <上面那个文件> --check   # 只校验现有产物

源文件不进仓库（1 MB 级原始地理数据）：需要重生成时按上面 URL 自行下载。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work/frontend/ui-vue/src/assets/geo/china-outline.geojson"

#: 抽稀容差（度）。110m 源数据本身只有 ~240 个点，抽稀只去掉几何重复点，基本不做删减
TOLERANCE_DEG = 0.02
#: 坐标保留几位小数（3 位 ≈ 100 m，足够全国视角；再多只是白涨体积）
DIGITS = 3
#: 面积过小的环直接丢掉（漏掉的海岛在全国视角里看不见，留着只涨体积）
MIN_RING_POINTS = 6


def _perpendicular_distance(point, start, end) -> float:
    (px, py), (sx, sy), (ex, ey) = point, start, end
    dx, dy = ex - sx, ey - sy
    if dx == 0 and dy == 0:
        return ((px - sx) ** 2 + (py - sy) ** 2) ** 0.5
    return abs(dy * px - dx * py + ex * sy - ey * sx) / ((dx * dx + dy * dy) ** 0.5)


def simplify(points: list[list[float]], tolerance: float) -> list[list[float]]:
    """Douglas–Peucker（迭代版，避免长折线递归过深）。"""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        worst, worst_index = 0.0, -1
        for index in range(first + 1, last):
            distance = _perpendicular_distance(points[index], points[first], points[last])
            if distance > worst:
                worst, worst_index = distance, index
        if worst_index >= 0 and worst > tolerance:
            keep[worst_index] = True
            stack.append((first, worst_index))
            stack.append((worst_index, last))
    return [point for point, kept in zip(points, keep) if kept]


def round_ring(ring: list[list[float]]) -> list[list[float]]:
    out: list[list[float]] = []
    for lon, lat in ((float(p[0]), float(p[1])) for p in ring):
        point = [round(lon, DIGITS), round(lat, DIGITS)]
        if not out or out[-1] != point:
            out.append(point)
    if out and out[0] != out[-1]:
        out.append(out[0])
    return out


def build(source: Path) -> dict:
    payload = json.loads(source.read_text(encoding="utf-8"))
    feature = None
    for item in payload.get("features") or []:
        if (item.get("properties") or {}).get("ADMIN") == "China":
            feature = item
            break
    if feature is None:
        raise SystemExit(f"{source} 里没有 ADMIN == 'China' 的 feature")

    geometry = feature["geometry"]
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    rings: list[list[list[float]]] = []
    for polygon in polygons:
        outer = polygon[0] if polygon else []
        simplified = round_ring(simplify([[float(p[0]), float(p[1])] for p in outer], TOLERANCE_DEG))
        if len(simplified) >= MIN_RING_POINTS:
            rings.append(simplified)
    if not rings:
        raise SystemExit("抽稀后没有剩下任何环：容差是不是调太大了？")

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": "中国范围示意（Natural Earth 1:110m 简化轮廓）",
                    "source": "Natural Earth 1:110m admin-0 countries（public domain）",
                    "source_url": "https://www.naturalearthdata.com/about/terms-of-use/",
                    "simplify_tolerance_deg": TOLERANCE_DEG,
                    "note": (
                        "仅作全国视角的底图兜底：轮廓由 Natural Earth 现成几何抽稀而来，"
                        "不是测绘成果、不代表边界主张、不得用于判读距离与范围。"
                    ),
                },
                "geometry": {"type": "MultiPolygon", "coordinates": [[ring] for ring in rings]},
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成全国视角的底图兜底轮廓（Issue IKPFVN）")
    parser.add_argument("--source", type=Path, help="Natural Earth ne_110m_admin_0_countries.geojson 路径")
    parser.add_argument("--out", type=Path, default=OUT, help=f"输出路径（默认 {OUT.relative_to(ROOT)}）")
    parser.add_argument("--check", action="store_true", help="只校验现有产物可解析、含 1 个 feature")
    args = parser.parse_args()

    if args.check:
        if not args.out.is_file():
            print(f"[失败] 缺少产物：{args.out}")
            return 1
        payload = json.loads(args.out.read_text(encoding="utf-8"))
        features = payload.get("features") or []
        size_kb = args.out.stat().st_size / 1024
        ok = payload.get("type") == "FeatureCollection" and len(features) == 1
        print(f"[{'通过' if ok else '失败'}] {args.out.relative_to(ROOT)}：{len(features)} 个 feature，{size_kb:.1f} KB")
        return 0 if ok else 1

    if not args.source:
        parser.error("非 --check 时必须给 --source")
    result = build(args.source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    size_kb = args.out.stat().st_size / 1024
    points = sum(len(ring[0]) for ring in result["features"][0]["geometry"]["coordinates"])
    print(f"[完成] {args.out.relative_to(ROOT)}：{size_kb:.1f} KB，{points} 个点")
    return 0


if __name__ == "__main__":
    sys.exit(main())
