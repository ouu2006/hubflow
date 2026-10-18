#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IKMDKY 自检：摄像头 ↔ 通道 ↔ 路段 三段映射对账（IKMS1T 起 **N 路动态口径**）。

跑（仓库根）：
    python work/perception/tools/check_camera_map.py                 # 正式登记表 / 生成物全量对账
    python work/perception/tools/check_camera_map.py --self-test     # 0 / 1 / 61 路与非法用例自检
    python work/perception/tools/check_camera_map.py --mapping <json> --generated <ts> [--net <json>]
                                                                     # fixture 模式（只对账给定文件，跳过仓库级扫描）
退出码 0 = 全过；1 = 有对不上的项。

口径（IKMS1T，业主 2026-10-17「摄像头不再固定 6 个」）：
  · 摄像头总数 **N = 登记表 `cameras` 条数**，动态：**0 ≤ N ≤ 当前站点路段数**（肇庆东 61）；
  · **默认一段最多 1 路**；同段多路需另开扩展单；**0 路合法**；
  · `has_video_source:false` 的摄像头**仍计入 N**；
  · `video_streams` 是「有视频源」摄像头的**子集**，条数任意（0..N），不得要求固定条数；
  · **摄像头数量 ≠ 样本视频段数**：样本视频仍只有 road2 / track1 两路，不伪造视频流。

检查项：
  ① 字段齐 / cam_id·cid 唯一 / 有视频源才可写 channel_id / has_video_source 为布尔；
  ② N ≤ 路段数、N ≥ 0、段号零悬空、默认每段最多 1 路；
  ③ video_streams ⊆ 有视频源摄像头，stream_id 唯一，段号 / cid 与摄像头登记一致；
  ④ 前端生成物**行数 == 登记表条数**，且逐字段一致（条数不再固定 6）；
  ⑤ 活跃路径 `SEG-###` 引用允许清单（仓库级）；
  ⑥ 站点包 `stationZ.ts` 只 import 生成物、不手写第二份通道表（仓库级）；
  ⑦ `--self-test`：内存构造 fixture（**不落盘、不碰正式登记表**）验证 0/1/61 路放行、非法用例拦截。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = Path(__file__).resolve().parent
MAPPING_PATH = ROOT / "work/perception/mapping/camera-segments.json"
NET_JUNCTION = ROOT / "work/twin/netpack/network_junction.json"
PACK_NET_TS = ROOT / "work/frontend/ui-vue/src/station-packs/stationZ.network.ts"
PACK_TS = ROOT / "work/frontend/ui-vue/src/station-packs/stationZ.ts"
GENERATED_TS = ROOT / "work/frontend/ui-vue/src/station-packs/cameraChannels.generated.ts"
PACK21_NET_TS = ROOT / "work/frontend/ui-vue/src/station-packs/stationZ21.network.ts"

#: 摄像头字段（IKMDKY 定形；本单不改字段形状）
CAMERA_FIELDS = ("cam_id", "cid", "name", "segment_id", "has_video_source", "mapping_evidence")
#: 视频流字段
STREAM_FIELDS = ("stream_id", "cam_id", "segment_id", "status", "evidence")

#: 61 段真路网段号池（自检 fixture 用；正式数据从 network_junction.json 读）
SEG_POOL = [f"SZ-{i:03d}" for i in range(1, 62)]

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
    # 接口层自检 / 对照快照里引用 7 节点样例网段号作对照（IKMF1T 合入的产物；不是本站段号）
    "work/assembly/selfcheck_ikmf1t.py",
    "work/assembly/对照快照.json",
    # 契约示例与历史台账（示例用 SEG；历史原文不改）
    "docs/",
]
SCAN_DIRS = ["work", "stations", "docs"]
SCAN_SUFFIXES = {".py", ".ts", ".vue", ".ets", ".json", ".html"}
SKIP_DIR_NAMES = {".git", "node_modules", "__pycache__", "dist", "out", "data", ".vite"}


def parse_generated_channels(text: str) -> list[dict]:
    """从生成物 cameraChannels.generated.ts 抽通道行（cid/cam_id/source/name/segment_id/lon/lat/hasVideo）。"""
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


def evaluate(mapping: dict, generated_text: str | None, net_ids: set[str]) -> tuple[list[str], dict]:
    """登记表 + 生成物 + 真路网 三方对账（纯函数：不打印、不写盘，自检也走它）。

    返回 (错误清单, 统计)。错误清单为空 = 通过。
    """
    errors: list[str] = []
    stats: dict = {"n": 0, "with_video": 0, "without": 0, "videos": 0, "generated_rows": 0}

    cams = mapping.get("cameras")
    videos = mapping.get("video_streams")
    if not isinstance(cams, list):
        errors.append("cameras 必须是数组（0..路段数；可以是空数组）")
        cams = []
    if not isinstance(videos, list):
        errors.append("video_streams 必须是数组（0..N；可以是空数组）")
        videos = []

    n = len(cams)
    stats["n"] = n
    if n > len(net_ids):
        errors.append(f"摄像头数 N={n} 超过本站路段数 {len(net_ids)}（口径：0 ≤ N ≤ 路段数；同段多路需另开扩展单）")

    cam_ids: list = []
    cids: list = []
    seg_counts: dict[str, int] = {}
    video_cam_ids: set = set()
    cam_by_id: dict = {}
    for i, c in enumerate(cams):
        if not isinstance(c, dict):
            errors.append(f"cameras[{i}] 不是对象")
            continue
        label = c.get("cam_id") or c.get("cid") or f"cameras[{i}]"
        for key in CAMERA_FIELDS:
            if key not in c:
                errors.append(f"摄像头 {label} 缺字段 {key}")
        cam_id = c.get("cam_id")
        cid = c.get("cid")
        seg = c.get("segment_id")
        if cam_id in cam_ids:
            errors.append(f"cam_id 重复：{cam_id}")
        if cid in cids:
            errors.append(f"cid 重复：{cid}")
        cam_ids.append(cam_id)
        cids.append(cid)
        cam_by_id[cam_id] = c
        if not isinstance(seg, str) or not seg:
            errors.append(f"摄像头 {label} 的 segment_id 非法：{seg!r}")
        else:
            seg_counts[seg] = seg_counts.get(seg, 0) + 1
            if seg not in net_ids:
                errors.append(f"摄像头 {label} 的段号 {seg} 在 {len(net_ids)} 段真路网里找不到（悬空）")
        has_video = c.get("has_video_source")
        if has_video is True:
            video_cam_ids.add(cam_id)
            if not c.get("channel_id"):
                errors.append(f"{label} 有视频源但没有 channel_id（无视频源时 channel_id 必须为 null）")
        elif has_video is False:
            if c.get("channel_id") is not None:
                errors.append(f"{label} 无视频源却登记了 channel_id={c.get('channel_id')}")
        else:
            errors.append(f"{label} 的 has_video_source 必须是 true / false，实际 {has_video!r}")

    stats["with_video"] = sum(1 for c in cams if isinstance(c, dict) and c.get("has_video_source") is True)
    stats["without"] = sum(1 for c in cams if isinstance(c, dict) and c.get("has_video_source") is False)

    # 默认一条路段最多 1 路摄像头（业主口径「有多少段路配多少摄像头」）
    dup_segs = sorted(s for s, k in seg_counts.items() if k > 1)
    if dup_segs:
        detail = " / ".join(f"{s}×{seg_counts[s]}" for s in dup_segs)
        errors.append(f"默认一段最多 1 路摄像头，但这些段登记了多路：{detail}（同段多路需另开扩展单）")

    # video_streams ⊆ 有视频源摄像头；条数任意（0..N）；每个摄像头最多绑一条流
    stream_ids: list = []
    stream_cam_ids: set = set()
    for i, v in enumerate(videos):
        if not isinstance(v, dict):
            errors.append(f"video_streams[{i}] 不是对象")
            continue
        label = v.get("stream_id") or f"video_streams[{i}]"
        for key in STREAM_FIELDS:
            if key not in v:
                errors.append(f"视频通道 {label} 缺字段 {key}")
        sid = v.get("stream_id")
        if sid in stream_ids:
            errors.append(f"video_streams 的 stream_id 重复：{sid}")
        stream_ids.append(sid)
        cam_id = v.get("cam_id")
        if cam_id in stream_cam_ids:
            errors.append(f"{label} 绑定的 {cam_id} 重复出现（一个摄像头最多绑一条 video_stream）")
        stream_cam_ids.add(cam_id)
        if cam_id not in video_cam_ids:
            errors.append(f"{label} 绑定的 {cam_id} 不在「有视频源」的摄像头里（video_streams 必须是 cameras 子集）")
        cam = cam_by_id.get(cam_id)
        if cam is not None and cam.get("segment_id") != v.get("segment_id"):
            errors.append(f"{label} 的 segment_id 与摄像头 {cam_id} 登记的段号不一致")
        if v.get("cid") is not None and cam is not None and v.get("cid") != cam.get("cid"):
            errors.append(f"{label} 的 cid={v.get('cid')} 与摄像头 {cam_id} 的 cid={cam.get('cid')} 不一致")
    stats["videos"] = len(videos)

    # 前端生成物：行数 == 登记表条数（N 动态），且逐字段一致
    if generated_text is None:
        errors.append("找不到前端生成物 cameraChannels.generated.ts（先跑 gen_station_channels.py）")
    else:
        rows = parse_generated_channels(generated_text)
        stats["generated_rows"] = len(rows)
        if len(rows) != n:
            errors.append(f"生成物行数 {len(rows)} ≠ 登记表 cameras 条数 {n}（生成物必须由登记表生成，条数跟随 N）")
        by_cid: dict = {}
        for r in rows:
            if r["cid"] in by_cid:
                errors.append(f"生成物 cid 重复：{r['cid']}")
            by_cid[r["cid"]] = r
        for c in cams:
            if not isinstance(c, dict):
                continue
            cid = c.get("cid")
            row = by_cid.get(cid)
            if row is None:
                errors.append(f"生成物缺摄像头 {cid}")
                continue
            want_source = c.get("channel_id") or c.get("cam_id")
            if row.get("cam_id") != c.get("cam_id"):
                errors.append(f"{cid} cam_id={row.get('cam_id')} ≠ 登记表 {c.get('cam_id')}")
            if row.get("source") != want_source:
                errors.append(f"{cid} source={row.get('source')} ≠ 期望 {want_source}（通道优先，无通道用 cam_id）")
            if row.get("name") != c.get("name"):
                errors.append(f"{cid} name={row.get('name')} ≠ 登记表 {c.get('name')}")
            if row.get("segment_id") != c.get("segment_id"):
                errors.append(f"{cid} segment_id={row.get('segment_id')} ≠ 登记表 {c.get('segment_id')}")
            if bool(row.get("hasVideo")) != bool(c.get("has_video_source")):
                errors.append(f"{cid} hasVideo={row.get('hasVideo')} ≠ 登记表 {c.get('has_video_source')}")
            if abs(float(row.get("lon", 0)) - float(c.get("lon", 0))) > 1e-9 or abs(
                float(row.get("lat", 0)) - float(c.get("lat", 0))
            ) > 1e-9:
                errors.append(f"{cid} 坐标与登记表不一致")
        extra = sorted(set(by_cid) - {c.get("cid") for c in cams if isinstance(c, dict)})
        if extra:
            errors.append(f"生成物有登记表里没有的 cid：{extra}")

    return errors, stats


# ---------------------------------------------------------------- 仓库级检查（正式登记表才跑）


def check_repo(mapping: dict, net_ids: set[str], errors: list[str]) -> None:
    """站点包几何 / stationZ.ts 引用 / 旧 21 段对照包 / SEG-### 活跃引用清单。"""
    cams = [c for c in mapping.get("cameras") or [] if isinstance(c, dict)]

    # 前端站点包几何：真路网段号必须全部出现在 stationZ.network.ts（脚本产物）
    if PACK_NET_TS.exists():
        pack_ids = set(re.findall(r"segment_id:\s*'(SZ-\d+)'", PACK_NET_TS.read_text(encoding="utf-8")))
        if not pack_ids:
            errors.append("stationZ.network.ts 里读不到 SZ-### 段号")
        else:
            print(f"[段号] 前端站点包几何：{len(pack_ids)} 段")
            if not net_ids.issubset(pack_ids):
                errors.append("61 段真路网的段号没有全部出现在 stationZ.network.ts 里")
    else:
        errors.append(f"找不到前端站点包几何 {PACK_NET_TS}")

    # stationZ.ts：只 import 生成物，不再手写第二份通道表
    if PACK_TS.exists():
        pack_text = PACK_TS.read_text(encoding="utf-8")
        if "from './cameraChannels.generated.ts'" not in pack_text or "channels: CAMERA_CHANNELS" not in pack_text:
            errors.append("stationZ.ts 没有引用生成物 CAMERA_CHANNELS（页面与登记表可能双写）")
        if re.search(r"const CHANNELS", pack_text):
            errors.append("stationZ.ts 里仍有手写 CHANNELS 数组（应只 import 生成物）")
    else:
        errors.append(f"找不到站点包 {PACK_TS}")

    # 旧 21 段对照包仍在：其段号只在本包几何里（退役对照，非现役）
    if PACK21_NET_TS.exists():
        old_ids = set(re.findall(r"segment_id:\s*'(SZ-\d\d)'", PACK21_NET_TS.read_text(encoding="utf-8")))
        print(f"[段号] Z21 对照包：{len(old_ids)} 段（退役对照，非现役）")

    # 登记表里所有摄像头段号都在真路网里 → 已在 evaluate 里判；这里只确认没有漏网
    dangling = [c.get("segment_id") for c in cams if c.get("segment_id") not in net_ids]
    if dangling:
        errors.append(f"登记表段号悬空：{dangling}")

    # SEG-### 活跃引用清单（允许清单外即失败）
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
    if outside:
        for rel, i, line in outside:
            errors.append(f"允许清单外的 SEG-### 引用：{rel}:{i} {line}")
    elif hits:
        print("   ✅ 全部落在允许清单内（stations 占位件 / engine samples / App fixture / docs 示例）")


# ---------------------------------------------------------------- 自检 fixture（内存构造，不落盘）


def fixture_mapping(
    n: int,
    *,
    dup_segment: bool = False,
    dangling: bool = False,
    dup_cid: bool = False,
    dup_cam: bool = False,
    beyond: bool = False,
) -> dict:
    """构造 n 路摄像头登记表 fixture。第 1 路有视频源（road2），n ≥ 1 时 video_streams 为 1 条。

    `beyond=True` 时第 n 路用 `SZ-{n:03d}`（n=62 → SZ-062，超出现役 61 段）。
    """
    cams = []
    for i in range(n):
        seg = f"SZ-{i + 1:03d}" if beyond else SEG_POOL[i % len(SEG_POOL)]
        if dup_segment and i > 0:
            seg = SEG_POOL[0]
        if dangling and i == n - 1:
            seg = "SZ-999"
        cam_id = "cam-01" if (dup_cam and i == n - 1) else f"cam-{i + 1:02d}"
        cid = "C-01" if (dup_cid and i == n - 1) else f"C-{i + 1:02d}"
        has_video = i == 0
        cams.append(
            {
                "cam_id": cam_id,
                "cid": cid,
                "name": f"演示摄像头 {i + 1}",
                "segment_id": seg,
                "channel_id": "road2" if has_video else None,
                "has_video_source": has_video,
                "mapping_evidence": "自检 fixture（演示值；不落盘、不碰正式登记表）",
                "lon": 112.65 + i * 1e-5,
                "lat": 23.21 + i * 1e-5,
            }
        )
    videos = []
    if n >= 1:
        videos.append(
            {
                "stream_id": "road2",
                "source_file": "road2.mp4",
                "cam_id": cams[0]["cam_id"],
                "cid": cams[0]["cid"],
                "segment_id": cams[0]["segment_id"],
                "status": "demo-mapped",
                "evidence": "自检 fixture（样本视频非本站现场，仅演示映射）",
                "note": "演示数据（模拟）",
            }
        )
    return {"is_simulated": True, "registry_version": "fixture", "cameras": cams, "video_streams": videos}


def self_test() -> int:
    """0 / 1 / 61 路放行；重复段 / 超路段数 / 悬空段号 / 重复 cid / 生成物不符 等非法用例拦截。"""
    try:
        sys.path.insert(0, str(TOOLS_DIR))
        import gen_station_channels as gen  # noqa: PLC0415  （同目录生成器，验证「生成物随登记表」）
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 无法导入生成器 gen_station_channels.py：{exc}")
        return 1

    net_ids = set(SEG_POOL)
    cases: list[tuple[str, dict, str, bool, str | None]] = []

    def add(
        name: str,
        mapping: dict,
        *,
        generated_from: dict | None = None,
        expect_ok: bool = True,
        want: str | None = None,
    ) -> None:
        cases.append((name, mapping, gen.render(generated_from if generated_from is not None else mapping), expect_ok, want))

    add("0 路（空登记表，合法）", fixture_mapping(0))
    add("1 路（1 路有视频源，合法）", fixture_mapping(1))
    add("61 路（= 路段数上限，合法）", fixture_mapping(61))
    add("非法 · 重复段（同段 2 路）", fixture_mapping(3, dup_segment=True), expect_ok=False, want="一段最多 1 路")
    add("非法 · 超路段数（62 > 61）", fixture_mapping(62, beyond=True), expect_ok=False, want="超过本站路段数")
    add("非法 · 悬空段号（SZ-999）", fixture_mapping(3, dangling=True), expect_ok=False, want="找不到")
    add("非法 · 重复 cid", fixture_mapping(3, dup_cid=True), expect_ok=False, want="cid 重复")
    add("非法 · 重复 cam_id", fixture_mapping(3, dup_cam=True), expect_ok=False, want="cam_id 重复")
    add(
        "非法 · 生成物行数与登记表不符",
        fixture_mapping(2),
        generated_from=fixture_mapping(1),
        expect_ok=False,
        want="生成物行数",
    )

    bad_video = fixture_mapping(2)
    bad_video["video_streams"][0]["cam_id"] = bad_video["cameras"][1]["cam_id"]
    bad_video["video_streams"][0]["cid"] = bad_video["cameras"][1]["cid"]
    bad_video["video_streams"][0]["segment_id"] = bad_video["cameras"][1]["segment_id"]
    add("非法 · 视频流绑到无视频源摄像头", bad_video, expect_ok=False, want="有视频源")

    no_channel = fixture_mapping(2)
    no_channel["cameras"][0]["channel_id"] = None
    add("非法 · 有视频源但没有 channel_id", no_channel, expect_ok=False, want="没有 channel_id")

    print("[自检] fixture 在内存里构造，不落盘、不碰正式登记表\n")
    all_ok = True
    for name, mapping, generated_text, expect_ok, want in cases:
        errors, stats = evaluate(mapping, generated_text, net_ids)
        if expect_ok:
            passed = not errors
            line = (
                f"   {'✅' if passed else '❌'} {name}：N={stats['n']} 路 · 有视频源 {stats['with_video']}"
                f" / 无视频源 {stats['without']} · 生成物 {stats['generated_rows']} 行 · 放行"
            )
        else:
            hit = [e for e in errors if want and want in e]
            passed = bool(errors) and bool(hit)
            line = (
                f"   {'✅' if passed else '❌'} {name}：N={stats['n']} 路 · 拦截 {len(errors)} 项"
                + (f"（含「{want}」）" if hit else f"（未命中期望「{want}」）")
            )
        print(line)
        if not passed:
            all_ok = False
            for e in errors:
                print(f"      - {e}")

    if not all_ok:
        print(f"\n❌ 自检失败：{len(cases)} 个用例里有不符合预期的")
        return 1
    print(f"\n✅ 自检通过：{len(cases)} 个用例（0 / 1 / 61 三档放行；重复段 / 超路段数 / 悬空段号 / 重复 cid·cam_id / 生成物不符 / 视频流越界 均拦截）")
    return 0


# ---------------------------------------------------------------- 命令行


def _resolve(raw: str | None, default: Path) -> Path:
    if raw is None:
        return default
    p = Path(raw)
    return p if p.is_absolute() else (ROOT / p)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="摄像头 ↔ 通道 ↔ 路段 三段映射对账（N 路动态口径，Issue IKMDKY / IKMS1T）")
    ap.add_argument("--mapping", default=None, help="登记表路径（默认 work/perception/mapping/camera-segments.json）")
    ap.add_argument("--generated", default=None, help="前端生成物路径（默认 station-packs/cameraChannels.generated.ts）")
    ap.add_argument("--net", default=None, help="61 段真路网路径（默认 work/twin/netpack/network_junction.json）")
    ap.add_argument("--self-test", action="store_true", help="跑 0/1/61 路与非法用例自检（内存 fixture，不写正式登记表）")
    a = ap.parse_args(argv)

    if a.self_test:
        return self_test()

    fixture_mode = bool(a.mapping or a.generated or a.net)
    mapping_path = _resolve(a.mapping, MAPPING_PATH)
    generated_path = _resolve(a.generated, GENERATED_TS)
    net_path = _resolve(a.net, NET_JUNCTION)

    if not mapping_path.is_file():
        print(f"❌ 找不到映射登记表 {mapping_path}")
        return 1
    if not net_path.is_file():
        print(f"❌ 找不到真路网 {net_path}（段号零悬空校验需要它）")
        return 1
    net = json.loads(net_path.read_text(encoding="utf-8"))
    net_ids = {e["segment_id"] for e in net.get("edges", [])}
    if not net_ids:
        print(f"❌ {net_path} 里读不到任何段号")
        return 1
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    generated_text = generated_path.read_text(encoding="utf-8") if generated_path.is_file() else None

    try:
        rel_mapping = mapping_path.relative_to(ROOT).as_posix()
    except ValueError:
        rel_mapping = str(mapping_path)
    print(f"映射登记表：{rel_mapping}（{mapping.get('registry_version')}）")
    print(f"[口径] 摄像头数 N = cameras 条数，动态 0 ≤ N ≤ 路段数（{len(net_ids)} 段）；默认每段最多 1 路")

    errors, stats = evaluate(mapping, generated_text, net_ids)
    for e in errors:
        print(f"   ❌ {e}")

    print(
        f"[登记表] N = {stats['n']} 路摄像头（0 ≤ N ≤ {len(net_ids)}）· 有视频源 {stats['with_video']} 路"
        f" · 无视频源 {stats['without']} 路"
    )
    print(
        f"[视频流] video_streams {stats['videos']} 路（⊆ 有视频源摄像头；条数任意 0..N）"
        " · 样本视频只有 road2 / track1，不伪造视频流"
    )
    try:
        rel_generated = generated_path.relative_to(ROOT).as_posix()
    except ValueError:
        rel_generated = str(generated_path)
    print(f"[前端生成物] {rel_generated}：{stats['generated_rows']} 行（== 登记表 {stats['n']} 路）")

    if fixture_mode:
        print("[fixture 模式] 跳过站点包 / SEG-### 扫描（只对账 --mapping / --generated / --net 给定文件）")
    else:
        before = len(errors)
        check_repo(mapping, net_ids, errors)
        for e in errors[before:]:
            print(f"   ❌ {e}")

    if errors:
        print(f"\n❌ 对账失败：{len(errors)} 项")
        return 1
    print(
        f"\n✅ 三段映射对账通过：N = {stats['n']} 路摄像头（有视频源 {stats['with_video']} / 无视频源"
        f" {stats['without']}）· 0 ≤ N ≤ {len(net_ids)} · 段号零悬空 · 默认每段最多 1 路"
        f" · 生成物 {stats['generated_rows']} 行 · 站点包与登记表一致"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main())
