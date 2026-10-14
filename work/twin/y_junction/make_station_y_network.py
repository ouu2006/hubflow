# -*- coding: utf-8 -*-
"""生成站点包 Y 的 .network.ts（纯脚本产物；不要手改）。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NETWORK_OUT = ROOT.parent.parent / "frontend" / "ui-vue" / "src" / "station-packs" / "stationY.network.ts"

geom = json.loads(
    (ROOT.parent.parent / "twin" / "y_junction" / "y_junction_geometry.json")
    .read_text(encoding="utf-8")
)
segments_geom = geom["segments"]


def fmt_coords(coords):
    return ",\n          ".join("[{}, {}]".format(c[0], c[1]) for c in coords)


lines = [
    "// 站点包 Y ·「Y 型交叉口」V0 演示站（Issue IKLR30）。",
    "// 来源:手工几何（work/twin/y_junction/y_junction.py）+ 预置基线 + 默认分级。",
    "// 不依赖任何后端 / SUMO / 桥接服务。",
    "",
    "import type { PackLandmark, PackSection, PackSegment, PackSegmentBase } from './types.ts'",
    "",
    "export const STATION_Y_SEGMENTS: PackSegment[] = [",
]

# ---- segments ----
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

# ---- sections (detectors) ----
lines += [
    "export const STATION_Y_SECTIONS: PackSection[] = [",
    "  { point_id: 'DS-01', name: 'S 腿上游', segment_id: 'INT-S-CW', role: 'boundary', offset: 0.05 },",
    "  { point_id: 'DS-02', name: 'S 腿下游', segment_id: 'INT-S-CW', role: 'internal', offset: 0.95 },",
    "  { point_id: 'DS-03', name: 'S 腿外侧上游', segment_id: 'INT-S-CCW', role: 'boundary', offset: 0.05 },",
    "  { point_id: 'DS-04', name: 'S 腿外侧下游', segment_id: 'INT-S-CCW', role: 'internal', offset: 0.95 },",
    "  { point_id: 'DB-01', name: 'B 腿上游', segment_id: 'INT-B-CW', role: 'boundary', offset: 0.05 },",
    "  { point_id: 'DB-02', name: 'B 腿下游', segment_id: 'INT-B-CW', role: 'internal', offset: 0.95 },",
    "  { point_id: 'DB-03', name: 'B 腿外侧上游', segment_id: 'INT-B-CCW', role: 'boundary', offset: 0.05 },",
    "  { point_id: 'DB-04', name: 'B 腿外侧下游', segment_id: 'INT-B-CCW', role: 'internal', offset: 0.95 },",
    "  { point_id: 'DA-01', name: 'A 腿上游', segment_id: 'INT-A-CW', role: 'boundary', offset: 0.05 },",
    "  { point_id: 'DA-02', name: 'A 腿下游', segment_id: 'INT-A-CW', role: 'internal', offset: 0.95 },",
    "  { point_id: 'DA-03', name: 'A 腿外侧上游', segment_id: 'INT-A-CCW', role: 'boundary', offset: 0.05 },",
    "  { point_id: 'DA-04', name: 'A 腿外侧下游', segment_id: 'INT-A-CCW', role: 'internal', offset: 0.95 },",
    "]",
    "",
]

# ---- dropoffs / zones / stations ----
lines += [
    "export const STATION_Y_DROPOFFS: PackLandmark[] = [",
    "  { id: 'DROP-Y-01', name: '落客点(主线)', lon: 0, lat: -5 },",
    "  { id: 'DROP-Y-02', name: '落客点(右支线)', lon: 3.5, lat: 3.5 },",
    "  { id: 'DROP-Y-03', name: '落客点(左支线)', lon: -3.5, lat: 3.5 },",
    "]",
    "",
    "export const STATION_Y_ZONES: PackLandmark[] = [",
    "  { id: 'ZONE-Y-01', name: '候客区(右)', lon: 5, lat: 5 },",
    "  { id: 'ZONE-Y-02', name: '候客区(左)', lon: -5, lat: 5 },",
    "]",
    "",
    "export const STATION_Y_STATIONS: PackLandmark[] = [",
    "  { id: 'STA-Y', name: 'Y 型交叉口(演示)', lon: 0, lat: 0, sub: 'V0 演示 · 右侧拥堵/左侧通畅' },",
    "]",
    "",
]

# ---- segment bases (from y_junction_mock.json) ----
mock = json.loads(
    (ROOT.parent.parent / "twin" / "y_junction" / "y_junction_mock.json")
    .read_text(encoding="utf-8")
)

lines += [
    "export const STATION_Y_SEGMENT_BASES: PackSegmentBase[] = [",
]
for seg in mock["segments"]:
    pred = ""
    if seg.get("pred"):
        pred = (
            "    pred: {"
            " h15: { q_vph: %d, level: %d },"
            " h30: { q_vph: %d, level: %d },"
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
        "    source: 'video',",  # TrafficSource = 'video' | 'twin'
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
        "    level: {},".format(seg["level"]),
        "    triggered_by: [],",
        "    confidence: {},".format(seg["confidence"]),
        "    data_age_s: {},".format(seg["data_age_s"]),
        "    stale: false,",
        "    " + pred if pred else "",
        "  },",
    ]

lines += ["]", ""]

# ---- alerts / context / scenarios / channels ----
# 告警等级需要是字面量类型 1|2|3|4，不是 number
lines += [
    "export const STATION_Y_ALERTS = [",
    "  { alert_id: 'Y-001', segment_id: 'BND-BA', level: 4 as const, triggered_by: ['x', 'L_q'], factor_ids: ['F07'], ago_min: 3, status: '待认领' as const },",
    "  { alert_id: 'Y-002', segment_id: 'BND-BA', level: 3 as const, triggered_by: ['x', 'v'], ago_min: 12, status: '处置中' as const },",
    "  { alert_id: 'Y-003', segment_id: 'BND-AS', level: 1 as const, triggered_by: ['v'], ago_min: 45, status: '已闭环' as const },",
    "  { alert_id: 'Y-004', segment_id: 'INT-B-CW', level: 4 as const, triggered_by: ['L_q'], factor_ids: ['F03'], ago_min: 8, status: '待认领' as const },",
    "]",
    "",
    "export const STATION_Y_CONTEXT = {",
    "  weather: { condition: '多云' as const, temp_c: 26, humidity_pct: 74, visibility_km: 9, precip_mm: 0, wind: '偏东风 2 级' },",
    "  calendar: '工作日' as const,",
    "  next_train_note: '演示值 · V0 静态剧情',",
    "}",
    "",
    "export const STATION_Y_SCENARIOS = [",
    "  { key: 'baseline', name: '常态基准', note: '右侧拥堵/左侧通畅基线', factor_ids: [] },",
    "  { key: 'burst', name: '右侧突发大流量', note: 'F10 需求 ×1.4:右支线更堵', factor_ids: ['F10'] },",
    "]",
    "",
    "export const STATION_Y_CHANNELS = [",
    "  { cid: 'C-01', source: 'cam1', name: 'S 腿全景', segment_id: 'INT-S-CW' },",
    "  { cid: 'C-02', source: 'cam2', name: 'B 腿全景', segment_id: 'INT-B-CW' },",
    "  { cid: 'C-03', source: 'cam3', name: 'A 腿全景', segment_id: 'INT-A-CW' },",
    "]",
    "",
]

NETWORK_OUT.write_text("\n".join(lines), encoding="utf-8")
print("saved:", NETWORK_OUT)
