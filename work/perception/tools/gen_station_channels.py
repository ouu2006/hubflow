#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从三段映射登记表生成前端站点包通道表（Issue IKMDKY）。

**唯一真值来源**：`work/perception/mapping/camera-segments.json`。
本脚本把它生成到 `work/frontend/ui-vue/src/station-packs/cameraChannels.generated.ts`，
页面（stationZ.ts）只 import 生成物 —— **不再手写第二份通道表**。

用法（仓库根）：
    python work/perception/tools/gen_station_channels.py            # 生成 / 覆盖
    python work/perception/tools/gen_station_channels.py --check    # 只比对，不一致非 0 退出
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAPPING_PATH = ROOT / "work/perception/mapping/camera-segments.json"
OUT_PATH = ROOT / "work/frontend/ui-vue/src/station-packs/cameraChannels.generated.ts"


def render(mapping: dict) -> str:
    cams = mapping.get("cameras") or []
    lines = [
        "// ⚠️ 本文件由 `work/perception/tools/gen_station_channels.py` 生成，**勿手改**。",
        "// 唯一真值来源：`work/perception/mapping/camera-segments.json`（IKMDKY 三段映射登记表）。",
        "// 页面（stationZ.ts）只 import 本文件；后端（work/perception/server.py）读同一份登记表。",
        "// 改映射：先改登记表 JSON，再跑 `python work/perception/tools/gen_station_channels.py`。",
        "",
        "import type { PackChannel } from './types.ts'",
        "",
        "export const CAMERA_CHANNELS: PackChannel[] = [",
    ]
    for c in cams:
        lines.append("  {")
        lines.append(f"    cid: '{c['cid']}',")
        lines.append(f"    cam_id: '{c['cam_id']}',")
        lines.append(f"    source: '{c.get('channel_id') or c['cam_id']}',")
        lines.append(f"    name: '{c['name']}',")
        lines.append(f"    segment_id: '{c['segment_id']}',")
        lines.append(f"    lon: {float(c['lon'])},")
        lines.append(f"    lat: {float(c['lat'])},")
        lines.append(f"    hasVideo: {'true' if c.get('has_video_source') else 'false'},")
        lines.append("  },")
    lines += ["]", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="登记表 → 前端通道表生成器（IKMDKY）")
    ap.add_argument("--check", action="store_true", help="只比对，不写盘（逐字节一致才算通过）")
    a = ap.parse_args()

    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    want = render(mapping)
    if a.check:
        have = OUT_PATH.read_text(encoding="utf-8").replace("\r\n", "\n") if OUT_PATH.exists() else ""
        if have != want:
            print(f"❌ 与登记表不一致：{OUT_PATH}")
            return 1
        print(f"✅ 一致：{OUT_PATH}")
        return 0
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(want, encoding="utf-8", newline="\n")
    print(f"→ {OUT_PATH}（{len(mapping.get('cameras') or [])} 路摄像头）")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main())
