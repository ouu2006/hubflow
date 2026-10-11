r"""#61 twin_preview 路网重建脚本(可选):Overpass 下载站点周边 OSM → netconvert 转网。

产物 station.osm / station.net.xml 已随本目录入库,常规演示不需要重跑本脚本;
仅当要换 bbox 或刷新路网数据时使用。

用法(仓库任意 python 3.10+,需 SUMO_HOME 且 netconvert 在 PATH):
  python work/frontend/tools/twin_preview/build_net.py
环境变量:
  OVERPASS_PROXY  可选,形如 http://127.0.0.1:7897(本机直连 Overpass 不通时)
"""
from __future__ import annotations

import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DIR = Path(__file__).resolve().parent

# 肇庆东站(贵广高铁,鼎湖区永安镇,OSM way 407489593)周边约 1.3 km:
# (南, 西, 北, 东)
BBOX = (23.2105, 112.6485, 23.2229, 112.6618)

QUERY = (
    "[out:xml][timeout:60];"
    '(way["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential|unclassified'
    '|living_street|service|motorway_link|trunk_link|primary_link|secondary_link'
    f'|tertiary_link)$\"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]}););(._;>;);out body;'
)


def main() -> int:
    url = "https://overpass-api.de/api/interpreter"
    data = urllib.parse.urlencode({"data": QUERY}).encode()
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "hubflow-twin-preview/0.1 (demo)"})
    proxy = os.environ.get("OVERPASS_PROXY")
    handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})
    osm = urllib.request.build_opener(handler).open(req, timeout=90).read()
    (DIR / "station.osm").write_bytes(osm)
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
        cwd=DIR,
        check=True,
    )
    print("station.net.xml written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
