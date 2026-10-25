#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从三段映射登记表生成前端站点包通道表（Issue IKMDKY / IKMS1T 去固定化）。

生成物有两份（**都不写时间戳，重跑逐字节一致**）：

① `cameraChannels.generated.ts` —— **源台账**通道表。
   唯一真值来源：`work/perception/mapping/camera-segments.json`（IKMDKY 三段映射登记表）。
   页面（stationZ.ts）只 import 生成物 —— **不再手写第二份通道表**。
   条数动态：行数 = 登记表 `cameras` 条数 N（IKMS1T 起 0 ≤ N ≤ 路段数，不再固定 6）。

② `demoCameraChannels.generated.ts` —— **演示层**摄像头表（业主 2026-10-25 口径：
   N 段 = N 摄像头 = N 视频，落到图钉 / 台账 / 监控墙）。
   来源 = `work/perception/mapping/camera-plan.json` 每段一行的 `demo_camera_id` 演示层；
   点位 = 该段折线上 `offset_m` 处（投影算法与 gen_camera_plan 同一套）；
   已被源台账登记的段**不再重复生成**（一段最多 1 路，源台账优先）；
   画面 = `reuseOf`（road2 / track1 按 segment_id 确定性二选一，规则与前端
   `SegmentCameraCard.reuseSourceOf` 同式）。

用法（仓库根）：
    python work/perception/tools/gen_station_channels.py                        # 生成 / 覆盖（两份产物）
    python work/perception/tools/gen_station_channels.py --check                # 只比对，不一致非 0 退出
    python work/perception/tools/gen_station_channels.py --mapping <json> --out <ts>
                                                                                # fixture（演示 / 自检用；只作用于源台账表）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAPPING_PATH = ROOT / "work/perception/mapping/camera-segments.json"
OUT_PATH = ROOT / "work/frontend/ui-vue/src/station-packs/cameraChannels.generated.ts"
PLAN_PATH = ROOT / "work/perception/mapping/camera-plan.json"
DEMO_OUT_PATH = ROOT / "work/frontend/ui-vue/src/station-packs/demoCameraChannels.generated.ts"

# 站点键 → 段号前缀（与 camera-plan.json 的 station_key / netpack 路径约定一致）
STATION_PREFIX = {"Z": "SZ-", "GZ": "GZ-"}

# 与前端 SegmentCameraCard.REUSE_SOURCES / reuseSourceOf 同式（确定性二选一）
REUSE_SOURCES = ["road2", "track1"]


def _js_hash(text: str) -> int:
    """与前端 reuseSourceOf 的 hash 完全同式（uint32 溢出截断），保证两端挑中同一路。"""
    h = 0
    for ch in text:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def _reuse_of(segment_id: str) -> str:
    return REUSE_SOURCES[_js_hash(segment_id) % len(REUSE_SOURCES)]


def _load_demo_geometry() -> dict[str, dict[str, list[list[float]]]]:
    """站点键 → {segment_id: 折线}。折线来自 netpack network_junction.json（WGS-84 [lon,lat]）。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import gen_camera_plan as gcp  # noqa: PLC0415 —— 复用同一套投影/折线算法，保证点位口径一致

    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    networks: dict[str, str] = plan.get("generated_from", {}).get("networks", {})
    out: dict[str, dict[str, list[list[float]]]] = {}
    for key, rel in networks.items():
        edges = gcp.load_edges(ROOT / rel)
        out[str(key)] = {str(e["segment_id"]): e["coords"] for e in edges}
    return out


def _point_at(coords: list[list[float]], offset_m: float) -> tuple[float, float]:
    """折线上距起点 offset_m 处的点（米制局部平面量长，与 gen_camera_plan._segment_length 同式）。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import gen_camera_plan as gcp  # noqa: PLC0415

    offset = 0.0
    for i in range(len(coords) - 1):
        start = (coords[i][0], coords[i][1])
        end = (coords[i + 1][0], coords[i + 1][1])
        seg_len = gcp._segment_length(start, end)  # noqa: SLF001 —— 同目录工具互引，算法必须同一套
        if offset + seg_len >= offset_m and seg_len > 0:
            t = (offset_m - offset) / seg_len
            return (
                start[0] + (end[0] - start[0]) * t,
                start[1] + (end[1] - start[1]) * t,
            )
        offset += seg_len
    return (coords[-1][0], coords[-1][1])


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


def render_demo(mapping: dict) -> str:
    """演示层 N 段 N 路（业主 2026-10-25）：camera-plan 每段一行 → PackChannel（demo: true）。"""
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    geometry = _load_demo_geometry()
    # 源台账已登记的段不再生成演示摄像头（一段最多 1 路，源台账优先）
    ledger_segments: dict[str, set[str]] = {k: set() for k in STATION_PREFIX}
    ledger_count: dict[str, int] = {k: 0 for k in STATION_PREFIX}
    for c in mapping.get("cameras") or []:
        seg = str(c.get("segment_id", ""))
        for key, prefix in STATION_PREFIX.items():
            if seg.startswith(prefix):
                ledger_segments[key].add(seg)
                ledger_count[key] += 1

    lines = [
        "// ⚠️ 本文件由 `work/perception/tools/gen_station_channels.py` 生成，**勿手改**。",
        "// 来源：`work/perception/mapping/camera-plan.json` 演示层（每段一行 demo_camera_id）",
        "//       + netpack `network_junction.json` 折线（点位 = 该段 offset_m 处，与 gen_camera_plan 同一套投影）。",
        "// 口径（业主 2026-10-25）：**N 段 = N 摄像头 = N 视频（演示）**——图钉 / 台账 / 监控墙按",
        "//       「源台账生成物 + 本文件」合并渲染；源台账已登记的段不重复生成（一段最多 1 路）。",
        "// `demo: true` 的条目画面走 `reuseOf`（road2 / track1 按 segment_id 确定性二选一，",
        "//       规则与前端 SegmentCameraCard.reuseSourceOf 同式）——是演示复用，不是该摄像头自己的视频。",
        "// 点位是演示布点（路段折线上的示意点），不是路测点、也不是踏勘点位；真实接入归 IKMHMX。",
        "",
        "import type { PackChannel } from './types.ts'",
        "",
        "export const DEMO_CAMERA_CHANNELS: Record<'Z' | 'GZ', PackChannel[]> = {",
    ]
    for st in plan.get("stations", []):
        key = str(st.get("station_key"))
        rows = [r for r in st.get("segments", []) if str(r.get("segment_id")) not in ledger_segments[key]]
        seg_lines = geometry.get(key, {})
        lines.append(f"  {key}: [")
        seq = ledger_count[key] + 1  # cid 接在源台账之后续编（Z：C-07 起；GZ：源台账 0 路 → C-01 起）
        for row in rows:
            seg = str(row["segment_id"])
            coords = seg_lines.get(seg)
            if coords is None:
                raise SystemExit(f"❌ 演示层生成失败：{key} 站折线缺 {seg}（netpack 与 camera-plan 不同步？）")
            offset = min(max(float(row.get("offset_m") or 0.0), 0.0), float(row.get("length_m") or 0.0))
            lon, lat = _point_at(coords, offset)
            cam = str(row["demo_camera_id"])
            name = str(row["name"]).replace("'", "\\'")
            lines.append(
                f"  {{ cid: 'C-{seq:02d}', cam_id: '{cam}', source: '{cam}', name: '{name}', "
                f"segment_id: '{seg}', lon: {round(lon, 7)}, lat: {round(lat, 7)}, "
                f"hasVideo: false, demo: true, reuseOf: '{_reuse_of(seg)}' }},"
            )
            seq += 1
        lines.append("  ],")
    lines += ["}", ""]
    return "\n".join(lines)


def resolve(raw: str | None, default: Path) -> Path:
    if raw is None:
        return default
    p = Path(raw)
    return p if p.is_absolute() else (ROOT / p)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="登记表 → 前端通道表生成器（IKMDKY；N 路动态，Issue IKMS1T；+ 演示层 2026-10-25）")
    ap.add_argument("--check", action="store_true", help="只比对，不写盘（逐字节一致才算通过；两份产物都查）")
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
    # 演示层产物：fixture 模式（--mapping 指到别处）不生成——它依赖仓库内 camera-plan / netpack
    want_demo: str | None = None
    if mapping_path == MAPPING_PATH and PLAN_PATH.is_file():
        want_demo = render_demo(mapping)

    if a.check:
        ok = True
        have = out_path.read_text(encoding="utf-8").replace("\r\n", "\n") if out_path.exists() else ""
        if have != want:
            print(f"❌ 与登记表不一致：{out_path}（登记表 {n} 路摄像头）")
            ok = False
        else:
            print(f"✅ 一致：{out_path}（{n} 路摄像头，条数跟随登记表）")
        if want_demo is not None:
            have_demo = DEMO_OUT_PATH.read_text(encoding="utf-8").replace("\r\n", "\n") if DEMO_OUT_PATH.exists() else ""
            if have_demo != want_demo:
                print(f"❌ 与演示层不一致：{DEMO_OUT_PATH}（camera-plan / netpack / 源台账有变动？）")
                ok = False
            else:
                import re

                rows = len(re.findall(r"cid: 'C-", have_demo))
                print(f"✅ 一致：{DEMO_OUT_PATH}（演示层 {rows} 路，Z+GZ）")
        return 0 if ok else 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(want, encoding="utf-8", newline="\n")
    print(f"→ {out_path}（{n} 路摄像头；条数由登记表决定，不写死）")
    if want_demo is not None:
        DEMO_OUT_PATH.write_text(want_demo, encoding="utf-8", newline="\n")
        import re

        rows = len(re.findall(r"cid: 'C-", want_demo))
        print(f"→ {DEMO_OUT_PATH}（演示层 {rows} 路 = 两站路段数 − 源台账已登记段数）")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main())
