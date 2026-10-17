r"""twin_preview 路网重建脚本（可选）：Overpass 下载**站点范围** OSM → netconvert 转网。

产物 `station.osm` / `station.net.xml` 已随本目录入库；常规演示不需要重跑本脚本。
**换站 / 换范围只改 `work/twin/site-ranges.json`**（拉取范围 `pull_bbox` 从登记表读），
脚本一行不改（IKM4B4；手册 §8.4）。

用法（仓库任意 python 3.10+，需 SUMO_HOME 且 netconvert 在 PATH）：
  python work/frontend/tools/twin_preview/build_net.py --site-id zhaoqingdong          # 下载 + netconvert
  python work/frontend/tools/twin_preview/build_net.py --site-id zhaoqingdong --print-query   # 只打印 Overpass 查询（不联网）
  python work/frontend/tools/twin_preview/build_net.py --bbox 112.64,23.20,112.67,23.23       # 显式覆盖拉取 bbox
环境变量：
  OVERPASS_PROXY  可选，形如 http://127.0.0.1:7897（本机直连 Overpass 不通时）
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DIR = Path(__file__).resolve().parent

#: 仓库根与本脚本要用到的站点范围登记表（work/twin/site-ranges.json）
ROOT = DIR.parents[3]
if str(ROOT / "work/twin") not in sys.path:
    sys.path.insert(0, str(ROOT / "work/twin"))
from site_config import DEFAULT_CONFIG_PATH, bbox_wsn, load_site  # noqa: E402

#: 拉取范围→ Overpass 查询：bbox 顺序必须是 (west, south, east, north)
HIGHWAY_RE = (
    "^(motorway|trunk|primary|secondary|tertiary|residential|unclassified"
    "|living_street|service|motorway_link|trunk_link|primary_link|secondary_link"
    "|tertiary_link)$"
)


def overpass_query(bbox_wsen: tuple[float, float, float, float]) -> str:
    west, south, east, north = bbox_wsen
    return (
        "[out:xml][timeout:60];"
        f'(way["highway"~"{HIGHWAY_RE}"]({south},{west},{north},{east}););(._;>;);out body;'
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="按站点登记表的 pull_bbox 拉 OSM 切片并转 SUMO 路网（换站只改配置）"
    )
    ap.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="站点范围登记表")
    ap.add_argument("--site-id", default=None, help="登记表里的 site_id（缺省取 default_site）")
    ap.add_argument("--bbox", default=None,
                    help="显式覆盖拉取范围 \"west,south,east,north\"（缺省取配置 pull_bbox）")
    ap.add_argument("--out-dir", default=str(DIR), help="切片/路网输出目录（缺省本目录）")
    ap.add_argument("--print-query", action="store_true", help="只打印 Overpass 查询，不联网")
    a = ap.parse_args()

    if a.bbox:
        parts = [float(x) for x in a.bbox.split(",")]
        if len(parts) != 4:
            print("❌ --bbox 必须是 west,south,east,north 四个数")
            return 2
        bbox = (parts[0], parts[1], parts[2], parts[3])
    else:
        site = load_site(a.site_id, Path(a.config))
        bbox = bbox_wsn(site["pull_bbox"])
        print(f"站点：{site['site_name']}（{site['site_id']}）· 拉取 bbox={bbox}")

    query = overpass_query(bbox)
    if a.print_query:
        print(query)
        return 0

    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    url = "https://overpass-api.de/api/interpreter"
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"User-Agent": "hubflow-twin-preview/0.1 (demo)"})
    proxy = os.environ.get("OVERPASS_PROXY")
    handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})
    osm = urllib.request.build_opener(handler).open(req, timeout=90).read()
    (out_dir / "station.osm").write_bytes(osm)
    print(f"station.osm: {len(osm)} bytes")
    subprocess.run(
        [
            "netconvert",
            "--osm-files", "station.osm",
            "-o", "station.net.xml",
            "--remove-edges.isolated",
            "--junctions.join",
            "--output.street-names",
        ],
        cwd=out_dir,
        check=True,
    )
    print("station.net.xml written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
