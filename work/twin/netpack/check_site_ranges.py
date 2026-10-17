#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IKM4B4 自检：站点范围登记表 ↔ 路网产物 ↔ 前端站点包 三方对账。

跑（仓库根）：
    python work/twin/netpack/check_site_ranges.py
退出码 0 = 全过；1 = 有对不上的项。

检查项：
  ① 登记表必填字段 / 来源枚举 / site_id 唯一（由 site_config 校验）；
  ② `network_junction.json` 的 site / stats.range_m / stats.segments /
     stats.anchor_lonlat 与登记表一致；
  ③ `stationZ.network.ts` 的段数 = seg_target；
  ④ `stationZ.ts` 的 station.range_m / range_source / segment_count 与登记表一致，
     且 subtitle 里能读到「范围 + 段数」（大屏/接口可查）；
  ⑤ OSM 切片的实际 bbox 覆盖登记表的 `pull_bbox`。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "work/twin") not in sys.path:
    sys.path.insert(0, str(ROOT / "work/twin"))
from site_config import load_site_ranges, repo_path  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass


def check_site(site: dict) -> list[str]:
    errors: list[str] = []
    sid = site["site_id"]
    seg_target = int(site["seg_target"])
    range_m = float(site["range_m"])

    # ② 路网产物对账
    out_json = repo_path(site["out_json"]) if site.get("out_json") else None
    if out_json is None or not out_json.exists():
        errors.append(f"{sid}: 产物不存在 {out_json}")
    else:
        net = json.loads(out_json.read_text(encoding="utf-8"))
        stats = net.get("stats", {})
        if net.get("site") != site["site_name"]:
            errors.append(f"{sid}: network_junction.site={net.get('site')} ≠ {site['site_name']}")
        if float(stats.get("range_m", -1)) != range_m:
            errors.append(f"{sid}: stats.range_m={stats.get('range_m')} ≠ {range_m}")
        if int(stats.get("segments", -1)) != seg_target:
            errors.append(f"{sid}: stats.segments={stats.get('segments')} ≠ seg_target {seg_target}")
        if [round(float(v), 7) for v in (stats.get("anchor_lonlat") or [])] != [
            round(float(v), 7) for v in site["anchor_lonlat"]
        ]:
            errors.append(f"{sid}: stats.anchor_lonlat={stats.get('anchor_lonlat')} ≠ {site['anchor_lonlat']}")

    # ③ 前端几何段数
    pack_net = site.get("station_pack_ts")
    if pack_net:
        p = repo_path(pack_net)
        if not p.exists():
            errors.append(f"{sid}: 前端几何不存在 {p}")
        else:
            n = len(re.findall(r"segment_id:\s*'", p.read_text(encoding="utf-8")))
            if n != seg_target:
                errors.append(f"{sid}: stationZ.network.ts 段数 {n} ≠ seg_target {seg_target}")

    # ④ 前端站点元信息（大屏/接口可查的"本站范围 X m · 路段 N 条"）
    meta_ts = site.get("station_pack_meta_ts")
    if meta_ts:
        p = repo_path(meta_ts)
        if not p.exists():
            errors.append(f"{sid}: 站点包元信息不存在 {p}")
        else:
            text = p.read_text(encoding="utf-8")
            m = re.search(r"station:\s*\{(.*?)\n  \},", text, re.S)
            block = m.group(1) if m else ""
            if not re.search(rf"range_m:\s*{int(range_m)}\b", block):
                errors.append(f"{sid}: station.range_m 与登记表不一致（应为 {int(range_m)}）")
            if not re.search(rf"segment_count:\s*{seg_target}\b", block):
                errors.append(f"{sid}: station.segment_count 与登记表不一致（应为 {seg_target}）")
            if f"range_source: '{site['range_source']}'" not in block:
                errors.append(f"{sid}: station.range_source 与登记表不一致（应为 {site['range_source']}）")
            if f"{int(range_m)} m" not in block or f"{seg_target} 段" not in block:
                errors.append(f"{sid}: station.subtitle 里读不到「{int(range_m)} m / {seg_target} 段」")

    # ⑤ OSM 切片覆盖 pull_bbox
    osm = repo_path(site["osm_file"])
    if not osm.exists():
        errors.append(f"{sid}: OSM 切片不存在 {osm}")
    else:
        text = osm.read_text(encoding="utf-8", errors="replace")
        lons = [float(x) for x in re.findall(r'lon="([\d.]+)"', text)]
        lats = [float(x) for x in re.findall(r'lat="([\d.]+)"', text)]
        if not lons or not lats:
            errors.append(f"{sid}: OSM 切片里没有节点坐标")
        else:
            w, s, e, n = (float(v) for v in site["pull_bbox"])
            eps = 1e-6
            if min(lons) > w + eps or min(lats) > s + eps or max(lons) < e - eps or max(lats) < n - eps:
                errors.append(
                    f"{sid}: 切片 bbox ({min(lons):.7f},{min(lats):.7f},{max(lons):.7f},{max(lats):.7f}) "
                    f"未覆盖 pull_bbox ({w},{s},{e},{n})"
                )
    return errors


def main() -> int:
    data = load_site_ranges()
    all_errors: list[str] = []
    for site in data["sites"]:
        errs = check_site(site)
        all_errors.extend(errs)
        status = "OK" if not errs else "FAIL"
        print(
            f"[{status}] {site['site_id']}（{site['site_name']}）· 范围 {site['range_m']} m"
            f"（{site['range_source']}）· 段数目标 {site['seg_target']}"
        )
        for e in errs:
            print(f"   ❌ {e}")

    if all_errors:
        print(f"\n❌ 对账失败：{len(all_errors)} 项")
        return 1
    print("\n✅ 登记表 ↔ 路网产物 ↔ 前端站点包 三方一致；切片覆盖拉取 bbox")
    return 0


if __name__ == "__main__":
    sys.exit(main())
