#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从三段映射登记表生成前端站点包通道表（Issue IKMDKY / IKMS1T 去固定化）。

**唯一真值来源**：`work/perception/mapping/camera-segments.json`。
本脚本把它生成到 `work/frontend/ui-vue/src/station-packs/cameraChannels.generated.ts`，
页面（stationZ.ts）只 import 生成物 —— **不再手写第二份通道表**。

**条数动态**：生成物行数 = 登记表 `cameras` 条数 N（IKMS1T 起 0 ≤ N ≤ 路段数，不再固定 6），
本脚本不写死任何数量。

用法（仓库根）：
    python work/perception/tools/gen_station_channels.py                        # 生成 / 覆盖（正式登记表）
    python work/perception/tools/gen_station_channels.py --check                # 只比对，不一致非 0 退出
    python work/perception/tools/gen_station_channels.py --mapping <json> --out <ts>
                                                                                # fixture（演示 / 自检用）
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
        "// 行数 = 登记表 cameras 条数 N，动态（IKMS1T：0 ≤ N ≤ 路段数，默认每段最多 1 路），不写死 6。",
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


def resolve(raw: str | None, default: Path) -> Path:
    if raw is None:
        return default
    p = Path(raw)
    return p if p.is_absolute() else (ROOT / p)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="登记表 → 前端通道表生成器（IKMDKY；N 路动态，Issue IKMS1T）")
    ap.add_argument("--check", action="store_true", help="只比对，不写盘（逐字节一致才算通过）")
    ap.add_argument("--mapping", default=None, help="登记表路径（默认 work/perception/mapping/camera-segments.json）")
    ap.add_argument("--out", default=None, help="生成物路径（默认 station-packs/cameraChannels.generated.ts）")
    a = ap.parse_args(argv)

    mapping_path = resolve(a.mapping, MAPPING_PATH)
    out_path = resolve(a.out, OUT_PATH)
    if not mapping_path.is_file():
        print(f"❌ 找不到登记表 {mapping_path}")
        return 1

    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    cams = mapping.get("cameras") or []
    if not isinstance(cams, list):
        print(f"❌ 登记表 cameras 必须是数组（{mapping_path}）")
        return 1
    want = render(mapping)
    n = len(cams)

    if a.check:
        have = out_path.read_text(encoding="utf-8").replace("\r\n", "\n") if out_path.exists() else ""
        if have != want:
            print(f"❌ 与登记表不一致：{out_path}（登记表 {n} 路摄像头）")
            return 1
        print(f"✅ 一致：{out_path}（{n} 路摄像头，条数跟随登记表）")
        return 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(want, encoding="utf-8", newline="\n")
    print(f"→ {out_path}（{n} 路摄像头；条数由登记表决定，不写死）")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main())
