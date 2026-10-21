#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全国站表对账（Issue IKPFVN A）：`stations.generated.ts` ↔ 站点登记 ↔ 站点包，三方一致才算过。

为什么需要它：全国地图的 pin 位置与切站镜头的目标取景都读 `src/station-packs/stations.generated.ts`，
而那份文件是从 `work/twin/site-ranges.json` **生成**的、经纬度又要和站点包 `stations[0]` 对得上。
这三处任意一处漂移，观众看到的就是「pin 钉在 A 处、镜头飞到 B 处、路网长在 C 处」——
这种错很像"地图坏了"，实际是配置没对齐。所以本脚本把三处钉在一起（**三方都读**）：

  ① **键必须一一对应**：`PACKS` 里每个键都要在站表里、站表里每个键都要在 `PACKS` 里
     （加了站点包却忘了登记表 → 切过去后端 404；登记了却没包 → 全国图多一个点不出来）；
  ② **锚点必须逐位对齐**：登记表 `anchor_lonlat` 与站点包 `stations[0]` 的经纬度**容差 1 m**；
  ③ **不许缺字段 / 不许重复 key**：缺字段的 pin 画不出来，而画出来的错 pin 比不画更糟；
  ④ （附加）`pack` 指向的文件真的在、`segment_count` 与该包真实段数一致；
  ⑤ **登记表 ↔ 生成物逐字段对齐**：`name / anchor_lonlat / range_m / seg_target` 与生成物一致
     —— 生成物是"抄"登记表的，抄错 / 手改生成物 / 登记表改了没重跑脚本，都在这里露出来。

> 为什么 ⑤ 必须真的读 `site-ranges.json`：只比「生成物 ↔ 站点包」的话，登记表被改、
> 生成物没重跑这种漂移**根本看不出来**（两边都对得上，可它们已经和真值源脱钩了）。
> `gen_station_registry.py --check` 也能抓，但那是一个脚本的自洽，这里是独立判据。

用法（仓库根）：

    python scripts/check_station_registry.py             # 对账
    python scripts/check_station_registry.py --self-test # 反向自测：故意造错必须报错

退出码：0 通过；1 有对不上的项；2 参数错误。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
PACKS_DIR = ROOT / "work/frontend/ui-vue/src/station-packs"
GENERATED = PACKS_DIR / "stations.generated.ts"
INDEX_TS = PACKS_DIR / "index.ts"
REGISTRY = ROOT / "work/twin/site-ranges.json"

#: 锚点容差（米）。1 m：两处坐标本应逐位相同，留 1 m 只为吃掉浮点写法差异
ANCHOR_TOLERANCE_M = 1.0
LAT_M_PER_DEG = 111_320.0


@dataclass
class StationRow:
    key: str
    name: str
    lon: float
    lat: float
    range_m: float | None
    segment_count: int | None
    pack: str


def _read(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"缺少文件：{path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def _num_field(block: str, field: str) -> float | None:
    match = re.search(rf"{field}:\s*(-?\d+(?:\.\d+)?)\s*,", block)
    return float(match.group(1)) if match else None


def _str_field(block: str, field: str) -> str | None:
    match = re.search(rf"{field}:\s*'([^']*)'\s*,", block)
    return match.group(1) if match else None


def parse_pack_keys() -> list[str]:
    """`PACKS` 里的站点包键（形如 `  Z: STATION_Z,`）。"""
    text = _read(INDEX_TS)
    block = re.search(r"export const PACKS[^=]*=\s*\{(.*?)\n\}", text, re.S)
    if not block:
        raise SystemExit("index.ts 里找不到 PACKS 字面量（生成方式变了？请同步改本脚本）")
    return re.findall(r"^\s{2}(\w+):\s*STATION_\w+\s*,", block.group(1), re.M)


def parse_stations() -> list[StationRow]:
    """`STATIONS` 的每一行。"""
    text = _read(GENERATED)
    block = re.search(r"export const STATIONS:\s*StationEntry\[\]\s*=\s*\[(.*)\n\]", text, re.S)
    if not block:
        raise SystemExit("stations.generated.ts 里找不到 STATIONS 字面量（先跑 gen_station_registry.py）")
    rows: list[StationRow] = []
    for chunk in re.findall(r"\{\s*(.*?)\s*\}", block.group(1), re.S):
        rows.append(
            StationRow(
                key=_str_field(chunk, "key") or "",
                name=_str_field(chunk, "name") or "",
                lon=_num_field(chunk, "lon") if _num_field(chunk, "lon") is not None else float("nan"),
                lat=_num_field(chunk, "lat") if _num_field(chunk, "lat") is not None else float("nan"),
                range_m=_num_field(chunk, "range_m"),
                segment_count=(
                    int(_num_field(chunk, "segment_count"))
                    if _num_field(chunk, "segment_count") is not None
                    else None
                ),
                pack=_str_field(chunk, "pack") or "",
            )
        )
    return rows


def parse_pack_station_anchor(pack_rel: str) -> tuple[float, float] | None:
    """站点包 `stations[0]` 的经纬度（`stations: [ { id, name, lon, lat, sub } ]`）。"""
    path = PACKS_DIR / Path(pack_rel).name
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    block = re.search(r"stations:\s*\[(.*?)\n\s*\],", text, re.S)
    if not block:
        return None
    first = re.search(r"\{\s*id:[^}]*\}", block.group(1), re.S)
    if not first:
        return None
    lon = _num_field(first.group(0), "lon")
    lat = _num_field(first.group(0), "lat")
    if lon is None or lat is None:
        return None
    return lon, lat


def count_pack_segments(key: str) -> int | None:
    """站点包 network ts 里的真实段数（`segment_id: 'SZ-001'` 去重计数）。"""
    path = PACKS_DIR / f"station{key}.network.ts"
    if not path.is_file():
        return None
    ids = set(re.findall(r"segment_id:\s*'([^']+)'", path.read_text(encoding="utf-8")))
    return len(ids)


def parse_registry_sites() -> dict[str, dict]:
    """站点登记表 `work/twin/site-ranges.json` 的每站关键字段（按站点包键索引）。"""
    payload = json.loads(_read(REGISTRY))
    sites = payload.get("sites")
    if not isinstance(sites, list):
        raise SystemExit(f"{REGISTRY.relative_to(ROOT)} 里没有 sites[]")
    out: dict[str, dict] = {}
    for site in sites:
        if not isinstance(site, dict):
            continue
        key = site.get("station_pack_key")
        if isinstance(key, str) and key:
            out[key] = site
    return out


def distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """两点距离（米，近似平面）：1 m 级比较不需要大地线公式。"""
    (lon1, lat1), (lon2, lat2) = a, b
    dx = (lon2 - lon1) * LAT_M_PER_DEG * math.cos(math.radians((lat1 + lat2) / 2))
    dy = (lat2 - lat1) * LAT_M_PER_DEG
    return math.hypot(dx, dy)


def find_duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    dups: list[str] = []
    for value in values:
        if value in seen and value not in dups:
            dups.append(value)
        seen.add(value)
    return dups


def missing_fields(row: StationRow) -> list[str]:
    missing: list[str] = []
    if not row.key:
        missing.append("key")
    if not row.name:
        missing.append("name")
    if not row.pack:
        missing.append("pack")
    if math.isnan(row.lon) or math.isnan(row.lat):
        missing.append("lon/lat")
    return missing


def run_checks(verbose: bool = True) -> list[str]:
    """返回问题清单（空 = 通过）。"""
    problems: list[str] = []
    pack_keys = parse_pack_keys()
    stations = parse_stations()

    def say(text: str) -> None:
        if verbose:
            print(text)

    # ③ 缺字段 / 重复 key
    for row in stations:
        missing = missing_fields(row)
        if missing:
            problems.append(f"站表行 {row.key or '(无 key)'} 缺字段：{', '.join(missing)}")
    for key in find_duplicates([row.key for row in stations]):
        problems.append(f"站表里站点包键 {key!r} 重复")
    for key in find_duplicates(pack_keys):
        problems.append(f"index.ts 的 PACKS 里键 {key!r} 重复")

    # ① 键一一对应
    station_keys = [row.key for row in stations if row.key]
    for key in pack_keys:
        if key not in station_keys:
            problems.append(f"PACKS 有 {key!r}，但站表里没有它（全国图会少一个站，切站也没镜头目标）")
    for key in station_keys:
        if key not in pack_keys:
            problems.append(f"站表有 {key!r}，但 PACKS 里没有它（顶栏/全国图会指向一个不存在的包）")

    # ⑤ 登记表 ↔ 生成物逐字段（真值源 → 抄写件）
    registry = parse_registry_sites()
    for key in registry:
        if key not in station_keys:
            problems.append(f"登记表有 {key!r}，但生成物站表里没有它（改完 site-ranges.json 要重跑 gen_station_registry.py）")
    for row in stations:
        site = registry.get(row.key)
        if site is None:
            if row.key:
                problems.append(f"生成物站表有 {row.key!r}，但 {REGISTRY.relative_to(ROOT)} 里没有这个站")
            continue
        if isinstance(site.get("site_name"), str) and row.name != site["site_name"]:
            problems.append(f"{row.key}：name 与登记表不一致（站表 {row.name!r} / 登记表 {site['site_name']!r}）")
        anchor = site.get("anchor_lonlat")
        if isinstance(anchor, list) and len(anchor) == 2:
            if abs(row.lon - float(anchor[0])) > 1e-9 or abs(row.lat - float(anchor[1])) > 1e-9:
                problems.append(
                    f"{row.key}：anchor 与登记表不一致（站表 {row.lon},{row.lat} / 登记表 {anchor[0]},{anchor[1]}）"
                )
        else:
            problems.append(f"{row.key}：登记表缺 anchor_lonlat")
        if isinstance(site.get("range_m"), (int, float)) and row.range_m is not None:
            if int(site["range_m"]) != int(row.range_m):
                problems.append(f"{row.key}：range_m 与登记表不一致（站表 {int(row.range_m)} / 登记表 {int(site['range_m'])}）")
        if isinstance(site.get("seg_target"), (int, float)) and row.segment_count is not None:
            if int(site["seg_target"]) != int(row.segment_count):
                problems.append(
                    f"{row.key}：segment_count 与登记表 seg_target 不一致"
                    f"（站表 {row.segment_count} / 登记表 {site['seg_target']}）"
                )

    # ② 锚点对齐 + ④ pack 存在 / 段数一致
    for row in stations:
        if not row.pack:
            continue
        anchor = parse_pack_station_anchor(row.pack)
        if anchor is None:
            problems.append(f"{row.key}：站点包 {row.pack} 读不出 stations[0] 的经纬度（文件不在或格式变了）")
        else:
            gap = distance_m((row.lon, row.lat), anchor)
            if gap > ANCHOR_TOLERANCE_M:
                problems.append(
                    f"{row.key}：锚点与站点包 stations[0] 差 {gap:.1f} m（容差 {ANCHOR_TOLERANCE_M:g} m）"
                    f"—— pin 会和站区错位"
                )
        actual = count_pack_segments(row.key)
        if actual is None:
            problems.append(f"{row.key}：找不到 station{row.key}.network.ts，无法核对段数")
        elif row.segment_count is not None and actual != row.segment_count:
            problems.append(f"{row.key}：站表 segment_count={row.segment_count}，站点包实际 {actual} 段")

    if verbose:
        rows = "；".join(
            f"{row.key}={row.name}({row.lon:.6f},{row.lat:.6f}) {row.segment_count} 段"
            for row in stations
        )
        say(f"[信息] 登记表 {REGISTRY.relative_to(ROOT)}：{len(stations)} 个站 → {rows}")
        say(f"[信息] PACKS 键：{', '.join(pack_keys) or '(空)'}")
    return problems


def self_test() -> int:
    """反向自测：把每一条判定都喂一个"错的输入"，必须都能判出来。"""
    failures: list[str] = []

    def expect(condition: bool, label: str) -> None:
        if not condition:
            failures.append(label)

    expect(distance_m((112.6581162, 23.2173959), (112.6581162, 23.2173959)) < 0.001, "同点距离应为 0")
    expect(distance_m((112.6581162, 23.2173959), (112.6581262, 23.2173959)) > ANCHOR_TOLERANCE_M,
           "经度差 1e-5°（≈1 m 以上）应判为超容差")
    expect(distance_m((112.6581162, 23.2173959), (112.6581166, 23.2173961)) < ANCHOR_TOLERANCE_M,
           "亚米级抖动应判为容差内")
    expect(find_duplicates(["Z", "GZ", "Z"]) == ["Z"], "重复 key 应被识别")
    expect(find_duplicates(["Z", "GZ"]) == [], "无重复时不该报重复")
    expect(
        missing_fields(StationRow(key="", name="", lon=float("nan"), lat=float("nan"),
                                  range_m=None, segment_count=None, pack="")) ==
        ["key", "name", "pack", "lon/lat"],
        "缺字段应被逐项识别",
    )
    expect(
        missing_fields(StationRow(key="Z", name="肇庆东站", lon=112.6, lat=23.2,
                                  range_m=500, segment_count=61, pack="./stationZ.ts")) == [],
        "完整行不该报缺字段",
    )

    registry = parse_registry_sites()
    expect(set(registry) == {"Z", "GZ"}, "登记表应解析出 Z / GZ 两个站（三方比对的输入不能空）")
    expect(registry["Z"]["station_pack_key"] == "Z", "登记表按站点包键索引")

    # 真实数据也必须过（自测顺带当一次全量对账）
    real = run_checks(verbose=False)
    expect(not real, "自测里对真实仓库跑对账应通过：" + "；".join(real))

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if failures:
        print(f"[失败] 自测 {len(failures)} 项未过（{stamp}）")
        for item in failures:
            print(f"  · {item}")
        return 1
    print(f"[通过] 自测全部符合预期（含登记表解析 2 项），且真实仓库三方对账通过（{stamp}）")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="全国站表对账（Issue IKPFVN A）")
    parser.add_argument("--self-test", action="store_true", help="反向自测：故意造错必须判出来")
    args = parser.parse_args()
    if args.self_test:
        return self_test()

    problems = run_checks()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if problems:
        print(f"[失败] 站表对账 {len(problems)} 项不一致（{stamp}）")
        for item in problems:
            print(f"  · {item}")
        print("提示：改过 site-ranges.json 就重跑 "
              "`python work/frontend/tools/gen_station_registry.py`，再跑本脚本。")
        return 1
    print(f"[通过] 站表对账通过：键一一对应、锚点容差内、字段齐全、段数一致（{stamp}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
