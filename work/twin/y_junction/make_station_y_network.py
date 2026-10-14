# -*- coding: utf-8 -*-
"""生成站点包 Y 的 .network.ts（纯脚本产物；不要手改）。

数据源：work/twin/y_junction/y_junction_geometry.json（车道级路网）
      + work/twin/y_junction/y_junction_mock.json（演示基线）。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NETWORK_OUT = (
    ROOT.parent.parent / "frontend" / "ui-vue" / "src" / "station-packs" / "stationY.network.ts"
)

geom = json.loads(
    (ROOT.parent.parent / "twin" / "y_junction" / "y_junction_geometry.json")
    .read_text(encoding="utf-8")
)
segments_geom = geom["segments"]

mock = json.loads(
    (ROOT.parent.parent / "twin" / "y_junction" / "y_junction_mock.json")
    .read_text(encoding="utf-8")
)
mock_by_id = {s["segment_id"]: s for s in mock["segments"]}


def fmt_coords(coords):
    return ",\n          ".join("[{}, {}]".format(c[0], c[1]) for c in coords)


# 断面：每条车道一条上游 boundary + 一条下游 internal
sections = []
n_s = 0
n_b = 0
for seg in segments_geom:
    sid = seg["segment_id"]
    if sid.startswith("SEG-S"):
        n_s += 1
        sections.append(
            ("DS-%02d" % n_s, "%s·上游断面" % seg["name"], sid, "boundary", 0.08)
        )
        sections.append(
            ("DS-%02d" % (n_s + 10), "%s·下游断面" % seg["name"], sid, "internal", 0.92)
        )
    else:
        n_b += 1
        sections.append(
            ("DB-%02d" % n_b, "%s·上游断面" % seg["name"], sid, "boundary", 0.08)
        )
        sections.append(
            ("DB-%02d" % (n_b + 10), "%s·下游断面" % seg["name"], sid, "internal", 0.92)
        )

section_lines = []
for pid, pname, sid, role, off in sections:
    section_lines.append(
        "  {{ point_id: '{}', name: '{}', segment_id: '{}', role: '{}', offset: {} }},".format(
            pid, pname, sid, role, off
        )
    )

lines = [
    "// 站点包 Y ·「Y 型单行道路网」V0 演示站（Issue IKLR30）。",
    "// 业主 2026-10-14 二版：真道路双车道模型——主线左/右两车道，分流后各接左/右支线车道，",
    "// 分叉处车道弧线圆滑；右支线拥堵、左支线通畅；不画车辆小球。",
    "// 来源:手工几何（work/twin/y_junction/export_geometry.py 产物）+ 预置基线，",
    "// 本文件是脚本产物（make_station_y_network.py），**勿手改**。",
    "// 不依赖任何后端 / SUMO / 桥接服务。",
    "",
    "import type { PackLandmark, PackSection, PackSegment, PackSegmentBase } from './types.ts'",
    "",
    "export const STATION_Y_SEGMENTS: PackSegment[] = [",
]

for seg in segments_geom:
    lines.append("  {")
    lines.append("    segment_id: '{}',".format(seg["segment_id"]))
    lines.append("    name: '{}',".format(seg["name"]))
    lines.append("    kind: 'main',")
    lines.append("    coords: [")
    lines.append("          {}".format(fmt_coords(seg["coords"])))
    lines.append("    ],")
    lines.append("  },")

lines += ["]", ""]

# ---- sections ----
lines += ["export const STATION_Y_SECTIONS: PackSection[] = ["] + section_lines + ["]", ""]

# ---- dropoffs / zones / stations ----
lines += [
    "export const STATION_Y_DROPOFFS: PackLandmark[] = [",
    "  { id: 'DROP-Y-01', name: '落客点(左支线)', lon: -60, lat: 120 },",
    "  { id: 'DROP-Y-02', name: '落客点(右支线)', lon: 60, lat: 120 },",
    "]",
    "",
    "export const STATION_Y_ZONES: PackLandmark[] = [",
    "  { id: 'ZONE-Y-01', name: '候客区(左支线)', lon: -90, lat: 170 },",
    "  { id: 'ZONE-Y-02', name: '候客区(右支线)', lon: 90, lat: 170 },",
    "]",
    "",
    "export const STATION_Y_STATIONS: PackLandmark[] = [",
    "  { id: 'STA-Y', name: 'Y 型汇流口(演示)', lon: 0, lat: 0, sub: 'V0 演示 · 单行道自下而上 · 右支拥堵/左支通畅' },",
    "]",
    "",
]

# ---- segment bases ----
lines += ["export const STATION_Y_SEGMENT_BASES: PackSegmentBase[] = ["]
for seg in mock["segments"]:
    base = mock_by_id[seg["segment_id"]]
    pred = ""
    if seg.get("pred"):
        pred = (
            "    pred: {"
            " h15: { q_vph: %d, level: %d as const },"
            " h30: { q_vph: %d, level: %d as const },"
            " model: '%s' },"
            % (
                seg["pred"]["h15"]["q_vph"],
                seg["pred"]["h15"]["level"],
                seg["pred"]["h30"]["q_vph"],
                seg["pred"]["h30"]["level"],
                seg["pred"]["model"],
            )
        )
    lines += [
        "  {",
        "    segment_id: '{}',".format(seg["segment_id"]),
        "    source: 'video',",
        "    q_vph: {},".format(seg["q_vph"]),
        "    v_kmh: {},".format(seg["v_kmh"]),
        "    v_f_kmh: {},".format(seg["v_f_kmh"]),
        "    k_vpk: {},".format(seg["k_vpk"]),
        "    L_q_m: {},".format(seg["L_q_m"]),
        "    L_seg_m: {},".format(seg["L_seg_m"]),
        "    T_d_min: {},".format(seg["T_d_min"]),
        "    x: {},".format(seg["x"]),
        "    c_base_vph: {},".format(seg["c_base_vph"]),
        "    c_vph: {},".format(seg["c_vph"]),
        "    factors_applied: [],",
        "    ci: {},".format(seg["ci"]),
        "    level: {} as const,".format(seg["level"]),
        "    triggered_by: [],",
        "    confidence: {},".format(seg["confidence"]),
        "    data_age_s: {},".format(seg["data_age_s"]),
        "    stale: false,",
        pred,
        "  },",
    ]
lines += ["]", ""]

# ---- alerts / context / scenarios / channels ----
# 告警只挂在右支线（拥堵侧），与基线自洽
lines += [
    "export const STATION_Y_ALERTS = [",
    "  { alert_id: 'Y-001', segment_id: 'SEG-B2', level: 4 as const, triggered_by: ['x', 'v'], factor_ids: ['F10'], ago_min: 4, status: '待认领' as const },",
    "  { alert_id: 'Y-002', segment_id: 'SEG-B', level: 4 as const, triggered_by: ['x', 'L_q'], factor_ids: ['F07'], ago_min: 11, status: '处置中' as const },",
    "  { alert_id: 'Y-003', segment_id: 'SEG-S2', level: 2 as const, triggered_by: ['v'], ago_min: 38, status: '已闭环' as const },",
    "]",
    "",
    "export const STATION_Y_CONTEXT = {",
    "  weather: { condition: '多云' as const, temp_c: 26, humidity_pct: 74, visibility_km: 9, precip_mm: 0, wind: '偏东风 2 级' },",
    "  calendar: '工作日' as const,",
    "  next_train_note: '演示值 · V0 静态剧情（无列车场景）',",
    "}",
    "",
    "export const STATION_Y_SCENARIOS = [",
    "  { key: 'baseline', name: '常态基准', note: '右支拥堵/左支通畅基线', factor_ids: [] },",
    "  { key: 'burst', name: '右支突发大流量', note: 'F10 需求 ×1.4:右支更堵', factor_ids: ['F10'] },",
    "]",
    "",
    "export const STATION_Y_CHANNELS = [",
    "  { cid: 'C-01', source: 'cam1', name: '主线入口', segment_id: 'SEG-S1' },",
    "  { cid: 'C-02', source: 'cam2', name: '左支线', segment_id: 'SEG-A' },",
    "  { cid: 'C-03', source: 'cam3', name: '右支线', segment_id: 'SEG-B' },",
    "]",
    "",
]

NETWORK_OUT.write_text("\n".join(lines), encoding="utf-8")
print("saved:", NETWORK_OUT)
print("segments:", len(segments_geom), " sections:", len(sections))
