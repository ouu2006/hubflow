#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从站点包 / 真路网生成一期摄像头布点规划（Issue IKP5DM）。

输入（全部是仓库内可重跑的只读文件）：
  · 真路网：`work/twin/netpack/network_junction.json`（Z，61 段）
            `work/twin/netpack/guangzhounan/network_junction.json`（GZ，708 段）
  · 站点包：`work/frontend/ui-vue/src/station-packs/stationZ.ts` / `stationGZ.ts`
            （只取 sections / dropoffs / zones / 站点名；几何以 JSON 路网为准）
  · 源台账：`work/perception/mapping/camera-segments.json`（6 条，仅源台账/初始映射）

输出：
  · `work/perception/mapping/camera-plan.json`（机器可读；行数 Z 61 / GZ 708）
  · `work/perception/mapping/camera-plan.md`（人读版；按站分表）

口径（为什么这样分两层）：
  · 一期展示口径是 **N 段 = N 演示摄像头 = N 视频（mock 复用）**，所以每一行都有
    `demo_camera_id`；它只是演示层编号，不代表真实点位，也不写进 `points.json`。
  · `planned` 是**规划层**：边界断面、主进场干道、场区出入口、落客/候客区所在段
    优先布点；场内支路 / 服务道路 / 连接匝道与 <20 m 的切分短段不单独布点——否则
    同一条车流会被相邻短段重复计数。
  · 视频源只有 `road2` / `track1` 两路可复用；`needs_video_source` 只对源台账里有
    这两路视频源的摄像头为 true，其余一律演示复用，不新增、不伪造视频流。

用法（仓库根）：
    python work/perception/tools/gen_camera_plan.py            # 生成 / 覆盖 JSON + MD
    python work/perception/tools/gen_camera_plan.py --check    # 只比对，不写盘；不一致非 0 退出

可重复生成：不写当前时间戳、不读系统时钟；同一批输入重跑逐字节一致。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN_JSON = ROOT / "work/perception/mapping/camera-plan.json"
PLAN_MD = ROOT / "work/perception/mapping/camera-plan.md"
LEDGER_PATH = ROOT / "work/perception/mapping/camera-segments.json"
POINTS_PATH = ROOT / "stations/points.json"

STATIONS = [
    {
        "key": "Z",
        "name_fallback": "肇庆东站",
        "network": ROOT / "work/twin/netpack/network_junction.json",
        "pack": ROOT / "work/frontend/ui-vue/src/station-packs/stationZ.ts",
        "pack_network": ROOT / "work/frontend/ui-vue/src/station-packs/stationZ.network.ts",
    },
    {
        "key": "GZ",
        "name_fallback": "广州南站",
        "network": ROOT / "work/twin/netpack/guangzhounan/network_junction.json",
        "pack": ROOT / "work/frontend/ui-vue/src/station-packs/stationGZ.ts",
        "pack_network": ROOT / "work/frontend/ui-vue/src/station-packs/stationGZ.network.ts",
    },
]

#: 低于这个长度的路段多为交叉口 / 折点切分产物，单独设断面会把同一股车流重复计数。
MIN_PLAN_LENGTH_M = 20.0

#: 固定版本号（不写生成时间，保证重跑无 diff）。
PLAN_VERSION = "2026-10-21"

SECTION_RE = re.compile(
    r"point_id:\s*'([^']+)'\s*,\s*segment_id:\s*'([^']+)'\s*,\s*name:\s*'([^']+)'\s*,\s*role:\s*'([^']+)'",
    re.S,
)
POINT_RE = re.compile(
    r"\{\s*id:\s*'([^']+)'\s*,\s*name:\s*'([^']+)'\s*,\s*lon:\s*([\d.]+)\s*,\s*lat:\s*([\d.]+)\s*,?\s*\}",
    re.S,
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_array(text: str, key: str) -> str:
    """取 `key: [ ... ]` 的数组正文（按方括号配对，跳过字符串里的括号）。"""
    match = re.search(r"\b" + re.escape(key) + r":\s*\[", text)
    if not match:
        return ""
    start = match.end()
    depth = 1
    quote: str | None = None
    index = start
    while index < len(text) and depth > 0:
        char = text[index]
        if quote is not None:
            if char == quote:
                quote = None
        elif char in "'\"":
            quote = char
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
        index += 1
    return text[start : index - 1]


def _parse_points(text: str, key: str) -> list[dict]:
    block = _extract_array(text, key)
    return [
        {"id": point_id, "name": name, "lon": float(lon), "lat": float(lat)}
        for point_id, name, lon, lat in POINT_RE.findall(block)
    ]


def _parse_sections(text: str) -> list[dict]:
    # Z 的 sections 是内联数组，GZ 的 sections 指向 BOUNDARY_SECTIONS；直接扫全文件的
    # `point_id + segment_id + name + role` 四元组即可，避免依赖 TS 的两种写法。
    return [
        {"point_id": point_id, "segment_id": segment_id, "name": name, "role": role}
        for point_id, segment_id, name, role in SECTION_RE.findall(text)
    ]


def load_pack(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    station_match = re.search(r"station:\s*\{.*?\bname:\s*'([^']+)'", text, re.S)
    return {
        "station_name": station_match.group(1) if station_match else "",
        "sections": _parse_sections(text),
        "dropoffs": _parse_points(text, "dropoffs"),
        "zones": _parse_points(text, "zones"),
    }


def load_edges(path: Path) -> list[dict]:
    payload = _read_json(path)
    edges = payload.get("edges")
    if not isinstance(edges, list) or not edges:
        raise ValueError(f"{path} 里读不到 edges")
    return edges


def _local_xy(point: tuple[float, float], origin: tuple[float, float]) -> tuple[float, float]:
    """以 origin 为原点的局部平面近似（米）；站点尺度 <1 km，误差可忽略。"""
    lat0 = math.radians(origin[1])
    return (
        (point[0] - origin[0]) * 111_320.0 * math.cos(lat0),
        (point[1] - origin[1]) * 110_540.0,
    )


def project_to_polyline(point: tuple[float, float], coords: list[list[float]]) -> tuple[float, float]:
    """点到折线的最近距离与沿线偏移（米）。用于把 dropoff / zone 落到段内合理点位。"""
    best_distance = math.inf
    best_offset = 0.0
    offset = 0.0
    for index in range(len(coords) - 1):
        start = (coords[index][0], coords[index][1])
        end = (coords[index + 1][0], coords[index + 1][1])
        distance, t = _segment_projection(point, start, end)
        if distance < best_distance:
            best_distance = distance
            best_offset = offset + t * _segment_length(start, end)
        offset += _segment_length(start, end)
    return best_distance, best_offset


def _segment_length(start: tuple[float, float], end: tuple[float, float]) -> float:
    x1, y1 = _local_xy(start, start)
    x2, y2 = _local_xy(end, start)
    return math.hypot(x2 - x1, y2 - y1)


def _segment_projection(
    point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]
) -> tuple[float, float]:
    px, py = _local_xy(point, start)
    ex, ey = _local_xy(end, start)
    if ex == 0 and ey == 0:
        return math.hypot(px, py), 0.0
    t = max(0.0, min(1.0, (px * ex + py * ey) / (ex * ex + ey * ey)))
    return math.hypot(px - t * ex, py - t * ey), t


def nearest_segment(point: dict, edges: list[dict]) -> tuple[float, str, float]:
    best: tuple[float, str, float] | None = None
    for edge in edges:
        distance, offset = project_to_polyline((point["lon"], point["lat"]), edge["coords"])
        if best is None or distance < best[0]:
            best = (distance, edge["segment_id"], offset)
    assert best is not None
    return best


def _names(items: list[dict], limit: int = 2) -> str:
    names = [item["name"] for item in items]
    if len(names) <= limit:
        return "、".join(names)
    return "、".join(names[:limit]) + "等"


def _boundary_offset(edge: dict, nodes: dict[str, dict]) -> float:
    """边界段取靠近站区范围边界那一端；两端都在边界时取中点。"""
    from_boundary = bool(nodes.get(edge["from"], {}).get("boundary"))
    to_boundary = bool(nodes.get(edge["to"], {}).get("boundary"))
    if from_boundary and not to_boundary:
        return 0.0
    if to_boundary and not from_boundary:
        return round(float(edge["length_m"]), 1)
    return round(float(edge["length_m"]) / 2.0, 1)


def _reason_for(
    edge: dict,
    *,
    boundary_section: dict | None,
    internal_section: dict | None,
    zones: list[dict],
    dropoffs: list[dict],
) -> tuple[bool, str]:
    """返回 (是否规划布点, 具体理由)。理由必须能独立解释这一段的取舍。"""
    segment_id = edge["segment_id"]
    name = edge["name"]
    kind = edge.get("kind") or "unknown"
    length = float(edge["length_m"])
    internal_note = "；站点包标注为内部断面（禁止同化，仅布点监测）" if internal_section else ""

    if edge.get("boundary"):
        if kind == "main":
            section_note = (
                f"；候选边界断面 {boundary_section['point_id']}（待 IKMHMX 签字冻结）"
                if boundary_section
                else ""
            )
            return True, (
                f"路网范围边界段（主进场干道外围端点）：{name} 是站区范围边界，"
                f"一期布点用于边界监测与后续同化，点位取边界端点{section_note}{internal_note}"
            )
        return True, (
            f"路网范围裁剪边界段（kind=ramp）：{name} 位于站区范围边界，"
            f"一期布点用于边界/出入监测，断面角色待 IKMHMX 冻结{internal_note}"
        )

    if zones or dropoffs:
        parts = []
        if zones:
            parts.append(f"场区出入口/候客区所在段（{_names(zones)}）")
        if dropoffs:
            parts.append(f"落客区所在段（{_names(dropoffs)}）")
        return True, (
            "；".join(parts)
            + f"：一期布点监测上下客、进出场与候客排队，点位取该点沿线投影{internal_note}"
        )

    if kind == "main":
        if length >= MIN_PLAN_LENGTH_M:
            return True, (
                f"主进场干道（kind=main）常规监测段：{name}，承担站前到发车流，"
                f"一期按路段设 1 个断面{internal_note}"
            )
        return False, (
            f"主路在交叉口/折点切分出的极短段（{length:.1f} m < {MIN_PLAN_LENGTH_M:.0f} m），"
            "不单独布点：同一股车流会被相邻段重复计数，由相邻段规划断面覆盖；"
            "演示层仍按 N 段 N 路给演示摄像头"
        )

    if "停车场" in name:
        return False, (
            f"场区内部支路（kind={kind}）：{name} 一期不进入判定口径，不单独布点，"
            f"由相邻主路段断面覆盖；演示层仍按 N 段 N 路给演示摄像头"
        )
    return False, (
        f"匝道/服务道路（kind={kind}）：{name} 不单独设断面，由相邻主路段断面覆盖；"
        f"演示层仍按 N 段 N 路给演示摄像头"
    )


def build_station(
    station: dict,
    edges: list[dict],
    pack: dict,
    ledger_cams_by_segment: dict[str, dict],
    video_streams: dict[str, dict],
) -> dict:
    nodes = {}
    network_payload = _read_json(station["network"])
    for node in network_payload.get("nodes") or []:
        nodes[node["node_id"]] = node

    sections_by_segment: dict[str, list[dict]] = {}
    for section in pack["sections"]:
        sections_by_segment.setdefault(section["segment_id"], []).append(section)

    zones_by_segment: dict[str, list[dict]] = {}
    for zone in pack["zones"]:
        _, segment_id, _ = nearest_segment(zone, edges)
        zones_by_segment.setdefault(segment_id, []).append(zone)
    dropoffs_by_segment: dict[str, list[dict]] = {}
    for dropoff in pack["dropoffs"]:
        _, segment_id, _ = nearest_segment(dropoff, edges)
        dropoffs_by_segment.setdefault(segment_id, []).append(dropoff)

    rows = []
    planned_index = 0
    for index, edge in enumerate(edges, 1):
        segment_id = edge["segment_id"]
        sections = sections_by_segment.get(segment_id, [])
        boundary_section = next((item for item in sections if item["role"] == "boundary"), None)
        internal_section = next((item for item in sections if item["role"] == "internal"), None)
        zones = zones_by_segment.get(segment_id, [])
        dropoffs = dropoffs_by_segment.get(segment_id, [])
        planned, reason = _reason_for(
            edge,
            boundary_section=boundary_section,
            internal_section=internal_section,
            zones=zones,
            dropoffs=dropoffs,
        )

        if edge.get("boundary"):
            offset_m = _boundary_offset(edge, nodes)
        elif zones or dropoffs:
            hit = (zones or dropoffs)[0]
            _, offset_m = project_to_polyline((hit["lon"], hit["lat"]), edge["coords"])
        else:
            offset_m = float(edge["length_m"]) / 2.0
        offset_m = round(max(0.0, min(float(edge["length_m"]), offset_m)), 1)

        camera = ledger_cams_by_segment.get(segment_id)
        source_ledger_cam_id = camera["cam_id"] if camera else None
        needs_video_source = bool(camera and camera.get("has_video_source"))
        if needs_video_source:
            stream = video_streams.get(camera.get("channel_id") or "")
            stream_id = stream["stream_id"] if stream else (camera.get("channel_id") or "")
            video_source_note = f"复用 {stream_id} 样本视频（源台账 {camera['cam_id']}；演示映射，不新增视频流）"
        else:
            video_source_note = "演示复用：按 N 段 N 路复用现有 2 路样本视频（mock），不新增视频流"

        if planned:
            planned_index += 1
            detector_id = f"DET-PLAN-{station['key']}-{planned_index:03d}"
        else:
            detector_id = None

        rows.append(
            {
                "segment_id": segment_id,
                "name": edge["name"],
                "kind": edge.get("kind") or "unknown",
                "length_m": round(float(edge["length_m"]), 1),
                "boundary": bool(edge.get("boundary")),
                "planned": planned,
                "offset_m": offset_m,
                "reason": reason,
                "demo_camera_id": f"CAM-{station['key']}-{index:03d}",
                "detector_id": detector_id,
                "source_ledger_cam_id": source_ledger_cam_id,
                "needs_video_source": needs_video_source,
                "video_source_note": video_source_note,
            }
        )

    planned_count = sum(1 for row in rows if row["planned"])
    return {
        "station_key": station["key"],
        "station_name": pack["station_name"] or station["name_fallback"],
        "segment_count": len(rows),
        "planned_count": planned_count,
        "not_planned_count": len(rows) - planned_count,
        "segments": rows,
    }


def build_plan() -> dict:
    ledger = _read_json(LEDGER_PATH)
    ledger_cams_by_segment: dict[str, dict] = {}
    for camera in ledger.get("cameras") or []:
        if isinstance(camera, dict) and camera.get("segment_id"):
            ledger_cams_by_segment[camera["segment_id"]] = camera
    video_streams = {
        stream["stream_id"]: stream
        for stream in ledger.get("video_streams") or []
        if isinstance(stream, dict) and stream.get("stream_id")
    }

    stations = []
    for station in STATIONS:
        edges = load_edges(station["network"])
        pack = load_pack(station["pack"])
        stations.append(build_station(station, edges, pack, ledger_cams_by_segment, video_streams))

    planned_total = sum(item["planned_count"] for item in stations)
    points = _read_json(POINTS_PATH)
    existing_detectors = [
        point
        for point in points.get("points") or []
        if isinstance(point, dict) and point.get("type") == "detector"
    ]
    network_ids = {
        edge["segment_id"] for item in STATIONS for edge in load_edges(item["network"])
    }
    real_network_detector_count = sum(
        1 for point in existing_detectors if point.get("segment_id") in network_ids
    )
    sample_network_detector_count = len(existing_detectors) - real_network_detector_count

    return {
        "is_simulated": True,
        "kind": "camera_plan",
        "plan_version": PLAN_VERSION,
        "note": (
            "一期摄像头布点规划（Issue IKP5DM）。planned=规划层布点（对应未来 points.json 的 detector），"
            "demo_camera_id=演示层 N 段 N 路编号；两者不是一回事：演示摄像头不新增视频源、不写 points.json。"
        ),
        "detector_id_note": "DET-PLAN-* 是规划编号，尚未登记 / 尚未接入；待 IKMHMX 落到 stations/points.json。",
        "generated_from": {
            "method": "work/perception/tools/gen_camera_plan.py（纯标准库；不写时间戳，重跑逐字节一致）",
            "networks": {item["key"]: item["network"].relative_to(ROOT).as_posix() for item in STATIONS},
            "station_packs": {item["key"]: item["pack"].relative_to(ROOT).as_posix() for item in STATIONS},
            "station_pack_networks": {
                item["key"]: item["pack_network"].relative_to(ROOT).as_posix() for item in STATIONS
            },
            "source_ledger": LEDGER_PATH.relative_to(ROOT).as_posix(),
            "points": POINTS_PATH.relative_to(ROOT).as_posix(),
        },
        "planning_rules": {
            "min_plan_length_m": MIN_PLAN_LENGTH_M,
            "planned_priority": [
                "路网范围边界段（边界断面优先；同化只允许边界段）",
                "场区出入口 / 候客区所在段（站点包 zones）",
                "落客区所在段（站点包 dropoffs）",
                "主进场干道（kind=main）且段长 ≥ 20 m 的常规监测段",
            ],
            "not_planned": [
                "场内支路（停车场内部通道）一期不进入判定口径，不单独布点",
                "服务道路 / 连接匝道不单独设断面，由相邻主路段断面覆盖",
                "主路切分出的 <20 m 极短段不单独布点，由相邻段断面覆盖",
            ],
            "demo_layer": (
                "每一行都有 demo_camera_id：一期展示口径 N 段 = N 演示摄像头 = N 视频（mock 复用）；"
                "不因 planned=false 而少给演示摄像头，也不把演示编号当成真实点位"
            ),
        },
        "points_json_mapping": {
            "note": (
                f"stations/points.json 现有 {len(existing_detectors)} 个 detector（真网段号 {real_network_detector_count} 个 / "
                f"样例网 {sample_network_detector_count} 个）；样例网条目用 SEG-###，不是本站 SZ-### / GZ-### 真网段号，"
                "不能直接对到本表任何一行。本表规划编号 DET-PLAN-<站>-### 只是规划占位，落 points.json 归 IKMHMX。"
            ),
            "existing_detectors": [
                {
                    "detector_id": point.get("point_id"),
                    "segment_id": point.get("segment_id"),
                    "status": (
                        "真网段号（本表可对照）"
                        if point.get("segment_id") in network_ids
                        else "样例网（SEG-###），不对应本表任何一行"
                    ),
                }
                for point in existing_detectors
            ],
            "real_network_detector_count": real_network_detector_count,
            "planned_detector_count": planned_total,
            "planned_detector_id_pattern": "DET-PLAN-{Z|GZ}-###",
        },
        "stations": stations,
    }


# ---------------------------------------------------------------- Markdown


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def _table(rows: list[dict]) -> list[str]:
    lines = [
        "| segment_id | 路段名 | 规划 | offset_m | 布点理由 | demo_camera_id | detector_id | source_ledger_cam_id | needs_video_source |",
        "|---|---|---|---:|---|---|---|---|---|",
    ]
    for row in rows:
        plan_mark = "布点" if row["planned"] else "不布点"
        detector = row["detector_id"] or "—"
        ledger_cam = row["source_ledger_cam_id"] or "—"
        video = "是（复用源）" if row["needs_video_source"] else "否（演示复用）"
        lines.append(
            "| {segment_id} | {name} | {plan} | {offset:.1f} | {reason} | {demo} | {detector} | {ledger} | {video} |".format(
                segment_id=row["segment_id"],
                name=_cell(row["name"]),
                plan=plan_mark,
                offset=row["offset_m"],
                reason=_cell(row["reason"]),
                demo=row["demo_camera_id"],
                detector=detector,
                ledger=ledger_cam,
                video=video,
            )
        )
    return lines


def render_md(plan: dict) -> str:
    stations = plan["stations"]
    lines = [
        "# 一期摄像头布点规划（Issue IKP5DM）",
        "",
        "> 机器可读版本：[camera-plan.json](camera-plan.json)；生成器：`work/perception/tools/gen_camera_plan.py`（`--check` 只校验不写盘）。",
        "> 本文只回答「该布多少、布在哪、现在差在哪」：**planned=true 是规划层布点**（未来 `stations/points.json` 的 detector）；",
        "> **每一行的 demo_camera_id 是演示层编号**——一期展示口径 **N 段 = N 演示摄像头 = N 视频（mock 复用）**，不因不布点而少给演示摄像头，",
        "> 也不把演示编号当成真实点位。",
        "",
        "## 一、口径（先分清三层）",
        "",
        "| 层 | 是什么 | 不是什么 |",
        "|---|---|---|",
        "| 源台账 `camera-segments.json` | 6 条初始映射（`cam-01`…`cam-06`），`video_streams` 只有 `road2` / `track1` 两路 | 不是一期摄像头总数；不是真实接入清单 |",
        "| 规划层 `planned=true` | 规划布点：边界断面、主进场干道、场区出入口、落客/候客区所在段优先 | 不是已落到 `points.json` 的 detector；规划编号 `DET-PLAN-*` 只是占位 |",
        "| 演示层 `demo_camera_id` | 每段 1 路演示摄像头（N 段 N 路），画面为 2 路样本视频的 mock 复用 | 不是新增视频流；不是真实摄像头；不写 `points.json` |",
        "",
        "布点判定顺序（同一条路段命中即取先命中的理由）：",
        "",
        "1. 路网范围边界段（`boundary=true`）——边界断面优先，同化只允许边界段；",
        "2. 场区出入口 / 候客区所在段（站点包 `zones`）；",
        "3. 落客区所在段（站点包 `dropoffs`）；",
        f"4. 主进场干道（`kind=main`）且段长 ≥ {plan['planning_rules']['min_plan_length_m']:.0f} m 的常规监测段。",
        "",
        f"**不布点**：场区内部支路（停车场内部通道）一期不进入判定口径；服务道路 / 连接匝道不单独设断面，由相邻主路段断面覆盖；主路切分出的 <{plan['planning_rules']['min_plan_length_m']:.0f} m 极短段不单独布点。三类都仍保留演示摄像头。",
        "",
        "## 二、统计",
        "",
        "| 站 | 路段数 | 规划布点 | 不布点 | 演示摄像头 | 源台账登记 | 有视频源 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for station in stations:
        ledger_rows = [row for row in station["segments"] if row["source_ledger_cam_id"]]
        video_rows = [row for row in station["segments"] if row["needs_video_source"]]
        lines.append(
            f"| {station['station_name']}（{station['station_key']}） | {station['segment_count']} | "
            f"{station['planned_count']} | {station['not_planned_count']} | {station['segment_count']} | "
            f"{len(ledger_rows)} | {len(video_rows)} |"
        )
    lines += [
        "",
        "## 三、站点 Z · 逐段规划（61 行）",
        "",
    ]
    lines += _table(stations[0]["segments"])
    lines += [
        "",
        "## 四、站点 GZ · 逐段规划（708 行）",
        "",
        "<details>",
        "<summary>点开 GZ 全表（708 行）</summary>",
        "",
    ]
    lines += _table(stations[1]["segments"])
    lines += [
        "",
        "</details>",
        "",
        "## 五、detector ↔ cam ↔ segment 三列对照",
        "",
        "每行的 `detector_id` / `demo_camera_id` / `segment_id` 三列就是对照关系；规划 detector 按站内布点顺序编号。",
        "源台账 6 条与规划行的双向关系如下（`plan_ref` 从登记表指向本表，`source_ledger_cam_id` 从本表回指登记表）：",
        "",
        "| cam_id | cid | segment_id | 规划表行 | detector_id | 视频源 |",
        "|---|---|---|---|---|---|",
    ]
    ledger = _read_json(LEDGER_PATH)
    row_by_segment = {
        row["segment_id"]: row for station in stations for row in station["segments"]
    }
    for camera in ledger.get("cameras") or []:
        segment_id = camera.get("segment_id")
        row = row_by_segment.get(segment_id)
        detector = (row or {}).get("detector_id") or "—"
        video = "—"
        if camera.get("has_video_source"):
            for stream in ledger.get("video_streams") or []:
                if stream.get("cam_id") == camera.get("cam_id"):
                    video = stream.get("stream_id") or "—"
        lines.append(
            f"| {camera.get('cam_id')} | {camera.get('cid')} | {segment_id} | {segment_id or '—'} | {detector} | {video} |"
        )
    lines += [
        "",
        "`stations/points.json` 现状：",
        "",
        "| detector_id | segment_id | 与本表的关系 |",
        "|---|---|---|",
        "| DET-01 | SEG-001 | 7 节点样例网，不对应本表任何一行 |",
        "| DET-02 | SEG-003 | 7 节点样例网，不对应本表任何一行 |",
        "",
        f"现有 detector 共 2 个（数量口径 2/61），但都在 `SEG-###` 样例网；对本站 Z 真网 `SZ-###` 的对应是 **0/61**。本表规划编号 `DET-PLAN-Z-###` / `DET-PLAN-GZ-###` 只是规划占位，落 `points.json` 归 IKMHMX。",
        "",
        "## 六、缺口（现在差在哪）",
        "",
        f"- **规划布点合计 {sum(station['planned_count'] for station in stations)} 路**：Z {stations[0]['planned_count']} 路、GZ {stations[1]['planned_count']} 路；对应 {sum(station['planned_count'] for station in stations)} 个规划 detector，`points.json` 尚未落位（归 IKMHMX）。",
        "- **`points.json` 现有 2 个 detector 都在样例网**：Z 真网 detector 0/61，且无 `lanes_covered` 类字段；本单不改 `points.json`。",
        "- **视频源只有 2 路**（`road2` / `track1`）：规划表的 `needs_video_source=true` 只出现在源台账 `cam-02` / `cam-05` 两行；其余全部是演示复用（N 段 N 路 mock），不新增视频流、不伪造视频源。",
        "- **演示层不缺口**：Z 61/61、GZ 708/708 段都有 `demo_camera_id`，但这只是演示编号，不是真实接入。",
        "",
        "## 七、与 `camera-segments.json` 的关系",
        "",
        "- 登记表仍是**唯一源台账**：6 条 `cameras` + 2 条 `video_streams`，本单**不扩**到 61/708 条（避免与 `docs/口径裁定-20261018.md` §十一「登记表是否长期维持 6 条源台账」的待拍板项冲突）。",
        "- 登记表每条 camera 新增 `plan_ref` / `plan_version`，指向本表对应行；本表每行用 `source_ledger_cam_id` 回指登记表 cam_id——**双向可查**。",
        "- 演示层的 `demo_camera_id` 只存在于本表，不写进登记表；登记表 6 条仍不是一期摄像头总数。",
        "",
        "## 八、生成与校验",
        "",
        "```bash",
        "python work/perception/tools/gen_camera_plan.py            # 生成 / 覆盖",
        "python work/perception/tools/gen_camera_plan.py --check    # 只校验，不写盘",
        "python work/perception/tools/check_camera_map.py           # 登记表 / 生成物 / 规划表三方对账",
        "```",
        "",
        "> 产物是**演示规划**：不声称摄像头已经接入；真实点位、视频源与标定归 IKMHMX。",
        "",
    ]
    return "\n".join(lines)


def render_json(plan: dict) -> str:
    return json.dumps(plan, ensure_ascii=False, indent=2) + "\n"


def _compare(path: Path, want: str) -> bool:
    have = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else ""
    if have == want:
        print(f"✅ 一致：{path.relative_to(ROOT).as_posix()}")
        return True
    print(f"❌ 与生成器不一致：{path.relative_to(ROOT).as_posix()}（重跑 gen_camera_plan.py）")
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="一期摄像头布点规划生成器（Issue IKP5DM）")
    parser.add_argument("--check", action="store_true", help="只比对，不写盘（逐字节一致才算通过）")
    args = parser.parse_args(argv)

    plan = build_plan()
    json_text = render_json(plan)
    md_text = render_md(plan)

    if args.check:
        ok = _compare(PLAN_JSON, json_text)
        ok = _compare(PLAN_MD, md_text) and ok
        return 0 if ok else 1

    PLAN_JSON.parent.mkdir(parents=True, exist_ok=True)
    PLAN_JSON.write_text(json_text, encoding="utf-8", newline="\n")
    PLAN_MD.write_text(md_text, encoding="utf-8", newline="\n")
    for station in plan["stations"]:
        print(
            f"→ {station['station_key']}：{station['segment_count']} 行（布点 {station['planned_count']} / "
            f"不布点 {station['not_planned_count']}）"
        )
    print(f"→ {PLAN_JSON.relative_to(ROOT).as_posix()}")
    print(f"→ {PLAN_MD.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main())
