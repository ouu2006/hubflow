"""OSM 切片 → netconvert → SUMO 路网 `stations/sumo/*.net.xml`。

输入:站点范围的 OSM 切片(--osm)
输出:SUMO 路网(--out);中间产物(.poly.xml / 日志)不当源码提交
口径:netconvert 命令**写进脚本**,不许手点;删掉产物能一键重建;
     **脚本里不出现任何站点名 / 坐标 / 路名** —— 换站只改参数,不改脚本(手册 §8.4)。
     本模块**只出 .net.xml**;统一图结构 network.json 由开发B 的 map_ingest.py 产出。

用法:
  python work/twin/netbuild.py --osm <切片>.osm.xml --out stations/sumo/station.net.xml
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

#: netconvert 官方推荐参数集(手册 §1.1);按 vclass 剔除铁路与步行道(站区有混入,§1.3)
NETCONVERT_ARGS = (
    "--geometry.remove",
    "--ramps.guess",
    "--junctions.join",
    "--tls.guess-signals",
    "--tls.discard-simple",
    "--tls.join",
    "--tls.default-type",
    "actuated",
    "--remove-edges.by-vclass",
    "rail_slow,rail_fast,bicycle,pedestrian",
)

#: 已知的正常噪声告警:出现这些不代表失败(手册 §1.3)
BENIGN_WARNINGS = (
    "Not joining junctions",
    "reduced by",
    "is only",
)


def find_netconvert() -> str:
    """定位 netconvert:先看 PATH,再看 $SUMO_HOME/bin。找不到就明确失败。"""
    found = shutil.which("netconvert")
    if found:
        return found
    sumo_home = os.environ.get("SUMO_HOME")
    if sumo_home:
        candidate = Path(sumo_home) / "bin" / "netconvert"
        if candidate.is_file():
            return str(candidate)
    raise SystemExit("找不到 netconvert:请装 SUMO 并设 $SUMO_HOME(见 work/twin/README.md 第三节)")


def build_net(osm_path: Path, out_path: Path, site: str = "", netconvert: str | None = None) -> Path:
    """把一份 OSM 切片转成 .net.xml。

    site 只用于日志与产物说明 —— **不参与命令拼装**,站点差异全部来自切片本身。
    """
    if not osm_path.is_file():
        raise SystemExit(f"OSM 切片不存在:{osm_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        netconvert or find_netconvert(),
        "--osm-files",
        str(osm_path),
        "-o",
        str(out_path),
        *NETCONVERT_ARGS,
    ]
    print(f"[netbuild] site={site or '(未指定)'} → {out_path}")
    print("[netbuild] " + " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    tail = (result.stdout or "").strip().splitlines()[-1:] or [""]
    for line in tail:
        print(f"[netconvert] {line}")
    if result.returncode != 0:
        raise SystemExit(f"netconvert 退出码 {result.returncode}(报错原文见上)")
    if not out_path.is_file() or out_path.stat().st_size <= 0:
        raise SystemExit(f"产物未生成:{out_path}")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OSM → netconvert → .net.xml")
    parser.add_argument("--osm", required=True, help="OSM 切片路径(.osm.xml)")
    parser.add_argument("--out", required=True, help="输出 .net.xml 路径")
    parser.add_argument("--site", default="", help="站点名,仅用于日志")
    ns = parser.parse_args(argv)
    build_net(Path(ns.osm), Path(ns.out), site=ns.site)
    return 0


if __name__ == "__main__":
    sys.exit(main())
