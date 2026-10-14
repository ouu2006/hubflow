#!/usr/bin/env python3
r"""生成「SEG → SUMO 边链」映射表 —— 让桥接服务**不再从路网里猜路段**。

**为什么需要它**：`server.py` 的老路子（`select_segments()`）靠**街名 + 站房位置**分组，
只适用于「OSM 衍生的、有名字、有地理配准」的网。换一张网（无名路 / 无地理配准）就失效。
给它一份映射表，`server.py --assignment <表>` 就直接照着走 —— **换网只换这张表，代码不动**。

    python make_assignment.py --net station.net.xml -o assignment.json
    python server.py --net station.net.xml --assignment assignment.json

**自检口径**：同一张网分别跑「启发式」与「表驱动」两条路，`/api/twin/network` 的
`segments` 应当**逐字一致** —— 一致才说明这张表没抽错。

⚠️ 本脚本用的是**老路子那把尺子**（街名 + 站房锚点），所以它**只适用于能跑通启发式的网**。
换到无名 / 无地理配准的网时，映射表要**按该网的 SEG 划分手写**（或由该网自己的划分脚本产出，
如 `work/twin/` 侧的一支），本脚本帮不上 —— 这一点别混。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main(argv: list[str] | None = None) -> int:
    import sumolib

    from server import DEFAULT_SEG_COUNT, DEFAULT_STATION_LONLAT, pick_drop_segment, select_segments

    parser = argparse.ArgumentParser(description="生成 SEG → SUMO 边链 映射表（老路子那把尺子）")
    parser.add_argument("--net", required=True, dest="net_file", help="SUMO 路网 .net.xml")
    parser.add_argument("--station-lonlat", default=",".join(map(str, DEFAULT_STATION_LONLAT)),
                        dest="station_lonlat", help="站房锚点「经度,纬度」")
    parser.add_argument("--seg-count", type=int, default=DEFAULT_SEG_COUNT, dest="seg_count")
    parser.add_argument("-o", "--out", required=True, dest="out", help="输出映射表 JSON")
    ns = parser.parse_args(argv)

    net_path = Path(ns.net_file)
    if not net_path.is_file():
        raise SystemExit(f"路网不存在：{net_path}")
    lon, lat = (float(v) for v in str(ns.station_lonlat).split(","))

    net = sumolib.net.readNet(str(net_path))
    segs = select_segments(net, (lon, lat), ns.seg_count)
    drop = pick_drop_segment(net, segs, (lon, lat))

    payload = {
        "note": (
            "SEG → SUMO 边链 映射表（由 make_assignment.py 从老路子的启发式抽出来固化）。"
            "桥接服务 --assignment 给这份表后，就不再从路网里猜路段。"
        ),
        "net_file": net_path.name,
        "drop_segment_id": drop["segment_id"],
        "segments": [
            {k: seg[k] for k in ("segment_id", "name", "kind", "edge_ids", "coords")}
            for seg in segs
        ],
    }
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    edges = sum(len(s["edge_ids"]) for s in payload["segments"])
    print(f"[make_assignment] {len(payload['segments'])} 条 SEG / {edges} 条边"
          f"｜落客段 {payload['drop_segment_id']}｜已写入 {out}"
          f"（{out.stat().st_size / 1024:.1f} KB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
