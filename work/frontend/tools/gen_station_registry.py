#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 `src/station-packs/stations.generated.ts` —— 大屏全国视角用的**全国站表**（Issue IKPFVN A）。

为什么要有这份生成物：全国地图要回答三个问题 ——「一共接入了哪几个站」「每个站在哪（经纬度）」
「点它之后镜头该飞多近（站区范围 / 段数）」。这三个答案的唯一真值源是**站点登记表**
`work/twin/site-ranges.json`（IKM4B4 起每站一份：锚点 / 范围 / 段数 / 段号前缀）。
在此之前前端**没有**一份给地图用的站表：`station-packs/index.ts` 的 `packItems()` 只有
`key/name/note`，没有经纬度也没有站区范围 —— 地图根本不知道「另一个站在哪、该飞多近」，
只能把取景写死在肇庆东的 `center/zoom`。

**加一个站只改配置**（手册 §8.4）：改 `site-ranges.json` + 加一个站点包 → 重跑本脚本 →
全国图上自动多一个 pin，切站镜头也有目标了；引擎 / 页面代码一行不用动。

用法（仓库根）：

    python work/frontend/tools/gen_station_registry.py            # 生成 / 覆盖
    python work/frontend/tools/gen_station_registry.py --check    # 只校验现有产物是否与配置一致

退出码：0 正常；1 `--check` 发现不一致（说明有人改了登记表却没重跑本脚本）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "work/twin/site-ranges.json"
PACKS_DIR = ROOT / "work/frontend/ui-vue/src/station-packs"
OUT = PACKS_DIR / "stations.generated.ts"

#: 产物头注释（门禁第 1 组要求 UTF-8 无 BOM、LF；本脚本以 newline="\n" 写出）
HEADER = """// ⚠️ 本文件由脚本 `work/frontend/tools/gen_station_registry.py` 生成，**勿手改**。
//
// 内容 = 站点登记表 `work/twin/site-ranges.json` 的**前端只读副本**（Issue IKPFVN）：
// 全国地图的站点 pin、切站镜头的目标取景、顶栏切换器都读这一份，不再各自拼
// `packItems()`。加一个站 = 改登记表 + 加一个站点包 + 重跑脚本，**页面与引擎代码不动**。
//
// 字段口径：
//   · `key`         站点包键（= 登记表 `station_pack_key`，与 `PACKS` 的键一一对应）
//   · `name`        站名（登记表 `site_name`，页面展示用）
//   · `lon` / `lat` 站区锚点（登记表 `anchor_lonlat`；WGS-84，与 OSM 底图同坐标系，无需转换）
//   · `range_m`     站区范围（米，脚本推定 / 人工圈定，**不是官方划定**，页面只展示）
//   · `segment_count` 站区路网段数（登记表 `seg_target`）
//   · `pack`        对应的前端站点包模块路径（相对 `src/station-packs/`）
//
// ⚠️ 经纬度是**站区锚点**，不是站房轮廓；页面不得把它说成"实测/测绘"坐标。
"""


def _site_rows() -> list[dict]:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    sites = payload.get("sites")
    if not isinstance(sites, list) or not sites:
        raise SystemExit(f"{REGISTRY} 里没有 sites[]：站表无法生成")
    rows: list[dict] = []
    seen: set[str] = set()
    for site in sites:
        if not isinstance(site, dict):
            raise SystemExit(f"{REGISTRY} 的 sites[] 里有非对象条目")
        key = site.get("station_pack_key")
        name = site.get("site_name")
        anchor = site.get("anchor_lonlat")
        if not isinstance(key, str) or not key:
            raise SystemExit(f"{REGISTRY}：站点 {site.get('site_id')!r} 缺 station_pack_key")
        if key in seen:
            raise SystemExit(f"{REGISTRY}：站点包键 {key!r} 重复登记")
        seen.add(key)
        if not isinstance(name, str) or not name:
            raise SystemExit(f"{REGISTRY}：站点 {key} 缺 site_name")
        if not isinstance(anchor, list) or len(anchor) != 2:
            raise SystemExit(f"{REGISTRY}：站点 {key} 的 anchor_lonlat 不是 [lon, lat]")
        try:
            lon, lat = float(anchor[0]), float(anchor[1])
        except (TypeError, ValueError):
            raise SystemExit(f"{REGISTRY}：站点 {key} 的 anchor_lonlat 不是数值")
        range_m = site.get("range_m")
        seg_target = site.get("seg_target")
        rows.append(
            {
                "key": key,
                "name": name,
                "lon": lon,
                "lat": lat,
                "range_m": int(range_m) if isinstance(range_m, (int, float)) else None,
                "segment_count": int(seg_target) if isinstance(seg_target, (int, float)) else None,
                "pack": f"./station{key}.ts",
                "prefix": site.get("seg_prefix"),
            }
        )
    return rows


def _q(text: str) -> str:
    """输出单引号字符串（与仓库其余 TS 源码风格一致；站名/键里不含单引号与反斜杠）。"""
    if "'" in text or "\\" in text:
        raise SystemExit(f"站名/包键里出现单引号或反斜杠，请改用 json.dumps：{text!r}")
    return f"'{text}'"


def _render(rows: list[dict]) -> str:
    lines: list[str] = [HEADER, ""]
    lines.append("/** 全国站表的一行（只读；字段含义见文件头） */")
    lines.append("export interface StationEntry {")
    lines.append("  key: string")
    lines.append("  name: string")
    lines.append("  lon: number")
    lines.append("  lat: number")
    lines.append("  range_m: number | null")
    lines.append("  segment_count: number | null")
    lines.append("  pack: string")
    lines.append("}")
    lines.append("")
    lines.append("/** 已接入车站（顺序 = 登记表顺序；全国地图 pin、镜头目标、切换器共用这一份） */")
    lines.append("export const STATIONS: StationEntry[] = [")
    for row in rows:
        lines.append("  {")
        lines.append(f"    key: {_q(row['key'])},")
        lines.append(f"    name: {_q(row['name'])},")
        lines.append(f"    lon: {row['lon']},")
        lines.append(f"    lat: {row['lat']},")
        lines.append(f"    range_m: {row['range_m']},")
        lines.append(f"    segment_count: {row['segment_count']},")
        lines.append(f"    pack: {_q(row['pack'])},")
        lines.append("  },")
    lines.append("]")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成全国站表 stations.generated.ts（Issue IKPFVN）")
    parser.add_argument("--check", action="store_true", help="只校验现有产物与登记表一致（不写文件）")
    args = parser.parse_args()

    rendered = _render(_site_rows())
    if args.check:
        if not OUT.is_file():
            print(f"[失败] 缺少产物：{OUT.relative_to(ROOT)}（先跑一次本脚本）")
            return 1
        current = OUT.read_text(encoding="utf-8")
        if current != rendered:
            print(f"[失败] {OUT.relative_to(ROOT)} 与 {REGISTRY.relative_to(ROOT)} 不一致：登记表改过但没重跑本脚本")
            return 1
        print(f"[通过] {OUT.relative_to(ROOT)} 与登记表一致")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(rendered, encoding="utf-8", newline="\n")
    keys = re.findall(r"^    key: '([^']+)',$", rendered, flags=re.M)
    print(f"[完成] {OUT.relative_to(ROOT)}：{len(keys)} 个站（{', '.join(keys)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
