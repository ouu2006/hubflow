#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IKMDKY 自检：摄像头 ↔ 通道 ↔ 路段 三段映射对账。

跑（仓库根）：
    python work/perception/tools/check_camera_map.py
退出码 0 = 全过；1 = 有对不上的项。

检查项（对应 Issue IKMDKY「自检脚本」四条）：
  ① 映射登记表字段齐 / 枚举合法 / cam_id·cid 不重复；
  ② 段 id 零悬空：登记表与站点包用到的 `SZ-###` 都能在 61 段真路网里找到；
  ③ 6 路摄像头逐条对得上「有 / 无视频源」（2 有视频、4 无视频）；
  ④ 活跃路径里 `SEG-###` 只剩允许清单内的样例 / 占位 / 归档引用（逐条列出）。
另外对账前端站点包 `stationZ.ts` 的 channels 与登记表一致（同一份键）。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAPPING_PATH = ROOT / "work/perception/mapping/camera-segments.json"
NET_JUNCTION = ROOT / "work/twin/netpack/network_junction.json"
PACK_NET_TS = ROOT / "work/frontend/ui-vue/src/station-packs/stationZ.network.ts"
PACK_TS = ROOT / "work/frontend/ui-vue/src/station-packs/stationZ.ts"
GENERATED_TS = ROOT / "work/frontend/ui-vue/src/station-packs/cameraChannels.generated.ts"
PACK21_NET_TS = ROOT / "work/frontend/ui-vue/src/station-packs/stationZ21.network.ts"

#: `SEG-###` 允许出现的活跃引用（各自理由；逐条打印）
SEG_ALLOWED = [
    # 7 节点样例网占位件（待 map_ingest 产出真值；不是本站真网）
    "stations/network.json",
    "stations/points.json",
    "stations/scenarios.json",
    "stations/thresholds.json",
    "stations/calibration.json",
    # 引擎样例数据 / 口径注释（--sample 用的 7 节点样例网）
    "work/engine/run.py",
    "work/engine/samples/",
    # 孪生内置样例 / 桥接服务口径注释（7 节点样例网，不是本站真网）
    "work/twin/samples/",
    "work/frontend/tools/twin_preview/server.py",
    # 鸿蒙 App 工程内 fixture / App HTML 演示数据（司机端，样例数据）
    "work/frontend/harmony/",
    "work/frontend/app-html/",
    # 本登记表自己记录 legacy_product_segment_id（明确标注"不是本站段号"）
    "work/perception/mapping/camera-segments.json",
    # 本自检脚本自身的检测字符串
    "work/perception/tools/check_camera_map.py",
    # 契约示例与历史台账（示例用 SEG；历史原文不改）
    "docs/",
]
SCAN_DIRS = ["work", "stations", "docs"]
SCAN_SUFFIXES = {".py", ".ts", ".vue", ".ets", ".json", ".html"}
SKIP_DIR_NAMES = {".git", "node_modules", "__pycache__", "dist", "out", "data", ".vite"}


def fail(errors: list[str], msg: str) -> None:
    errors.append(msg)
    print(f"   ❌ {msg}")


def parse_generated_channels(text: str) -> list[dict]:
    """从生成物 cameraChannels.generated.ts 抽 6 条（cid/cam_id/source/name/segment_id/lon/lat/hasVideo）。"""
    rows = []
    for m in re.finditer(
        r"\{\s*cid: '([^']+)',\s*cam_id: '([^']+)',\s*source: '([^']+)',\s*name: '([^']+)',"
        r"\s*segment_id: '([^']+)',\s*lon: ([\d.]+),\s*lat: ([\d.]+),\s*hasVideo: (true|false),",
        text,
        re.S,
    ):
        rows.append(
            {
                "cid": m.group(1),
                "cam_id": m.group(2),
                "source": m.group(3),
                "name": m.group(4),
                "segment_id": m.group(5),
                "lon": float(m.group(6)),
                "lat": float(m.group(7)),
                "hasVideo": m.group(8) == "true",
            }
        )
    return rows


def check_mapping(mapping: dict, errors: list[str]) -> None:
    cams = mapping.get("cameras")
    videos = mapping.get("video_streams")
    if not isinstance(cams, list) or len(cams) != 6:
        fail(errors, f"cameras 必须是 6 条，实际 {len(cams) if isinstance(cams, list) else '非数组'}")
        return
    if not isinstance(videos, list) or len(videos) != 2:
        fail(errors, f"video_streams 必须是 2 条，实际 {len(videos) if isinstance(videos, list) else '非数组'}")

    cam_ids, cids = set(), set()
    video_cams = set()
    for c in cams:
        for key in ("cam_id", "cid", "name", "segment_id", "has_video_source", "mapping_evidence"):
            if key not in c:
                fail(errors, f"摄像头 {c.get('cam_id') or c.get('cid') or '?'} 缺字段 {key}")
                continue
        if c.get("cam_id") in cam_ids:
            fail(errors, f"cam_id 重复：{c.get('cam_id')}")
        if c.get("cid") in cids:
            fail(errors, f"cid 重复：{c.get('cid')}")
        cam_ids.add(c.get("cam_id"))
        cids.add(c.get("cid"))
        if c.get("has_video_source"):
            video_cams.add(c.get("cam_id"))
            if not c.get("channel_id"):
                fail(errors, f"{c.get('cam_id')} 有视频源但没有 channel_id")
        elif c.get("channel_id") is not None:
            fail(errors, f"{c.get('cam_id')} 无视频源却登记了 channel_id={c.get('channel_id')}")
    cams_with_video = [c for c in cams if c.get("has_video_source") is True]
    cams_without = [c for c in cams if c.get("has_video_source") is False]
    print(f"[共 6 路] 有视频源 {len(cams_with_video)} 路 · 无视频源 {len(cams_without)} 路")
    if len(cams_with_video) != 2:
        fail(errors, f"有视频源的摄像头应为 2 路（road2/track1），实际 {len(cams_with_video)}")

    seg_of_cam = {c["cam_id"]: c["segment_id"] for c in cams}
    stream_ids = [v.get("stream_id") for v in videos]
    if len(set(stream_ids)) != len(stream_ids):
        fail(errors, "video_streams 的 stream_id 有重复")
    for v in videos:
        for key in ("stream_id", "cam_id", "segment_id", "status", "evidence"):
            if key not in v:
                fail(errors, f"视频通道 {v.get('stream_id') or '?'} 缺字段 {key}")
                continue
        if v.get("cam_id") not in video_cams:
            fail(errors, f"{v.get('stream_id')} 绑定的 {v.get('cam_id')} 不在有视频源的摄像头里")
        if seg_of_cam.get(v.get("cam_id")) != v.get("segment_id"):
            fail(errors, f"{v.get('stream_id')} 的 segment_id 与摄像头登记的段号不一致")


def main() -> int:
    if not MAPPING_PATH.exists():
        print(f"❌ 找不到映射登记表 {MAPPING_PATH}")
        return 1
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    errors: list[str] = []
    print(f"映射登记表：{MAPPING_PATH.relative_to(ROOT)}（{mapping.get('registry_version')}）")
    check_mapping(mapping, errors)
    cams = mapping.get("cameras") or []

    # ② 段 id 零悬空：61 段真路网
    if not NET_JUNCTION.exists():
        fail(errors, f"找不到 61 段路网 {NET_JUNCTION}")
        net_ids = set()
    else:
        net = json.loads(NET_JUNCTION.read_text(encoding="utf-8"))
        net_ids = {e["segment_id"] for e in net.get("edges", [])}
        print(f"[段号] 61 段真路网：{len(net_ids)} 段")
        bad = [c["segment_id"] for c in cams if c.get("segment_id") not in net_ids]
        if bad:
            fail(errors, f"映射里的段号在 61 段真路网里找不到：{bad}")
        if PACK_NET_TS.exists():
            pack_ids = set(re.findall(r"segment_id:\s*'(SZ-\d+)'", PACK_NET_TS.read_text(encoding="utf-8")))
            if not pack_ids:
                fail(errors, "stationZ.network.ts 里读不到 SZ-### 段号")
            else:
                print(f"[段号] 前端站点包几何：{len(pack_ids)} 段")
                if not net_ids.issubset(pack_ids):
                    fail(errors, "61 段真路网的段号没有全部出现在 stationZ.network.ts 里")

    # ③ 生成物 ↔ 登记表 ↔ 站点包引用
    if not GENERATED_TS.exists():
        fail(errors, f"找不到生成物 {GENERATED_TS}（先跑 gen_station_channels.py）")
    else:
        rows = parse_generated_channels(GENERATED_TS.read_text(encoding="utf-8"))
        print(f"[前端生成物] cameraChannels.generated.ts：{len(rows)} 条")
        if len(rows) != 6:
            fail(errors, f"生成物应为 6 条摄像头，实际 {len(rows)}")
        by_cid = {r.get("cid"): r for r in rows}
        for c in cams:
            row = by_cid.get(c.get("cid"))
            if row is None:
                fail(errors, f"生成物缺摄像头 {c.get('cid')}")
                continue
            want_source = c.get("channel_id") or c.get("cam_id")
            if row.get("cam_id") != c.get("cam_id"):
                fail(errors, f"{c['cid']} cam_id={row.get('cam_id')} ≠ 登记表 {c.get('cam_id')}")
            if row.get("source") != want_source:
                fail(errors, f"{c['cid']} source={row.get('source')} ≠ 期望 {want_source}（通道优先，无通道用 cam_id）")
            if row.get("name") != c.get("name"):
                fail(errors, f"{c['cid']} name={row.get('name')} ≠ 登记表 {c.get('name')}")
            if row.get("segment_id") != c.get("segment_id"):
                fail(errors, f"{c['cid']} segment_id={row.get('segment_id')} ≠ 登记表 {c.get('segment_id')}")
            if bool(row.get("hasVideo")) != bool(c.get("has_video_source")):
                fail(errors, f"{c['cid']} hasVideo={row.get('hasVideo')} ≠ 登记表 {c.get('has_video_source')}")
            if abs(float(row.get("lon", 0)) - float(c.get("lon", 0))) > 1e-9 or abs(
                float(row.get("lat", 0)) - float(c.get("lat", 0))
            ) > 1e-9:
                fail(errors, f"{c['cid']} 坐标与登记表不一致")
        if PACK_TS.exists():
            pack_text = PACK_TS.read_text(encoding="utf-8")
            if "from './cameraChannels.generated.ts'" not in pack_text or "channels: CAMERA_CHANNELS" not in pack_text:
                fail(errors, "stationZ.ts 没有引用生成物 CAMERA_CHANNELS（页面与登记表可能双写）")
            if re.search(r"const CHANNELS", pack_text):
                fail(errors, "stationZ.ts 里仍有手写 CHANNELS 数组（应只 import 生成物）")
        # 旧 21 段对照包仍在：其段号只在本包几何里
        if PACK21_NET_TS.exists():
            old_ids = set(re.findall(r"segment_id:\s*'(SZ-\d\d)'", PACK21_NET_TS.read_text(encoding="utf-8")))
            print(f"[段号] Z21 对照包：{len(old_ids)} 段（退役对照，非现役）")

    # ④ SEG-### 活跃引用清单（允许清单外即失败）
    hits: list[tuple[str, int, str]] = []
    for base in SCAN_DIRS:
        for path in (ROOT / base).rglob("*"):
            if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = path.relative_to(ROOT).as_posix()
            for i, line in enumerate(text.splitlines(), 1):
                if "SEG-00" in line:
                    hits.append((rel, i, line.strip()[:120]))
    print(f"[SEG-###] 活跃引用 {len(hits)} 处；允许清单按文件前缀匹配")
    outside = [h for h in hits if not any(h[0] == a or h[0].startswith(a) for a in SEG_ALLOWED)]
    for rel, i, line in outside:
        fail(errors, f"允许清单外的 SEG-### 引用：{rel}:{i} {line}")
    if hits and not outside:
        print(f"   ✅ 全部落在允许清单内（stations 占位件 / engine samples / App fixture / docs 示例）")

    if errors:
        print(f"\n❌ 对账失败：{len(errors)} 项")
        return 1
    print("\n✅ 三段映射对账通过：6 路摄像头（2 有视频 / 4 无视频）· 段号零悬空 · 站点包与登记表一致")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main())
