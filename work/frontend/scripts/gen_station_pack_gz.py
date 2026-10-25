#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成广州南站站点包元信息 `stationGZ.ts`（Issue IKNB9F；脚本产物，勿手改）。

## 为什么需要它

前端站点包 = 「一包一站」：几何（`stationGZ.network.ts`，由 `build_junction_pack.py` 生成）
+ 元信息/演示基线/摄像头通道（本文件生成）。GZ 站没有手写站点包，所以元信息也由脚本
从**真网产物 + 站点登记表**派生，保证换站/重跑路网后整包可重新生成、不靠手改。

口径（与 stationZ.ts 一致）：

- **几何是 OSM 真值**；路况指标一律是**演示数据（模拟）**，不是实测；
- **落客点 / 候客区**语义取自广州南站公开资料（政府官网 / 铁路官方 / 主流媒体，整理时点
  2026-10），坐标取真网对应路段折线上的**演示点**，每条名称标「（演示点）」；
  真实踏勘点位归 IKMHMX，本包不冒充实测；
- 全段确定性演示基线：每段 level ∈ 1~4（**不出现灰档**），数值由段序号/段长确定性派生，
  同一输入重跑逐字节一致；标 `derive` 说明来源；
- GZ 源台账无摄像头登记 → `channels` 取**演示层生成物** `DEMO_CAMERA_CHANNELS.GZ`（业主
  2026-10-25 口径：N 段 = N 摄像头 = N 视频，落到图钉 / 台账 / 监控墙；`demo: true`、
  画面 `reuseOf` 演示复用）；`colorPolicy: 'all'`（全段按等级上色，不是只有摄像头段）；
- 站点元信息（range_m / segment_count / range_source / subtitle）与 `site-ranges.json` 对齐，
  供 `work/twin/netpack/check_site_ranges.py` 三方对账。

## 用法（仓库根）

    python work/frontend/scripts/gen_station_pack_gz.py          # 生成 stationGZ.ts
    python work/frontend/scripts/gen_station_pack_gz.py --check  # 只比对，不一致非 0 退出
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "work/twin") not in sys.path:
    sys.path.insert(0, str(ROOT / "work/twin"))

from site_config import load_site, repo_path  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

SITE_ID = "guangzhounan"
PACK_KEY = "GZ"
#: 站点包里的路况基线档位（演示数据；与站点包 Z 的展示口径一致：level 1~4 四档均有）
LEVEL_CYCLE = (1, 2, 1, 3, 2, 1, 2, 4, 1, 2, 3, 1)
LEVEL_V_KMH = {1: 34, 2: 22, 3: 13, 4: 7}
LEVEL_Q_VPH = {1: 320, 2: 900, 3: 1800, 4: 2600}
LEVEL_LQ_M = {1: 0, 2: 40, 3: 120, 4: 240}
LEVEL_TD_MIN = {1: 0.0, 2: 1.2, 3: 4.5, 4: 9.0}
LEVEL_TRIGGERED = {1: ["x"], 2: ["x", "v"], 3: ["x", "L_q"], 4: ["v", "L_q"]}
LEVEL_CI = {1: 34, 2: 55, 3: 73, 4: 88}
DEMO_DERIVE = "演示基线（确定性派生，不是实测；GZ 站点包演示数据）"

# ---- 落客点 / 候客区（语义取自广州南站公开资料；坐标取真网折线演示点，不是踏勘点位）----
#
# 语义来源：广州南站停车接客点 / 候车点公开资料（政府官网、铁路官方、主流媒体；整理时点
# 2026-10）。该资料给的是**功能与方位描述**（哪个停车场是快速接送区、哪个是网约车上客区、
# 出哪个门最近），**不含任何经纬度**；而 OSM 切片里没有 `amenity=parking` 面、也没有站房
# 轮廓，所以坐标只能照站点包 Z 的既有口径「取对应路段折线上的演示点」。
#
# 每条 = (id, 名称, 所在真网段, 段内弧长占比)。名称一律带「（演示点）」：
# 真实踏勘点位归 IKMHMX，本包不冒充实测。
#
# 名称里的停车场编号（P1/P3/P5/P8/P9-P10）与「快速接送区 / 网约车上客区 / 出租车上客区 /
# 旅游大巴上客点」的对应关系来自公开资料；**公开资料给出的桥柱锚点（南4/南10/北10/北4）
# 未提供可换算的坐标**，故本表只按「所在道路」落线，不宣称精确到某根桥柱。
LANDMARKS: list[tuple[str, str, str, float]] = [
    # 落客点（送客下车）—— 手册 §「送客 = 起点 → 落客点 → 离站段」
    # 东/西出发平台：公开资料写「二层只有东平台落客、三层只有西平台落客，均即停即走」，
    # 但该条在第三方多维验证报告里判为【待核实】—— 两轮核验均未在政府/铁路官方原文中
    # 直接搜到「二层=东、三层=西」的层位对应关系（间接佐证只到「东西两个平台都存在」）。
    # 故点位名称里**不带层位**（免得界面把未核实结论当事实展示），层位只在本注释与
    # work/frontend/README.md 第 21.3 节记录。
    ("GZ-DROP-01", "东出发平台落客区（演示点）", "GZ-041", 0.55),
    ("GZ-DROP-02", "西出发平台落客区（演示点）", "GZ-451", 0.50),
    # 快速接送区 —— 注意「快速接送区 / 快速接客区」两种叫法并存，不要写成「已统一更名」：
    # 2025-06 收费复函用「快速接送区」，番禺区 2025-07 答复的措辞是「**计划**将『快速接客区』
    # 统一更名」，并协调高德/滴滴改定位名 —— 更名是进行中动作。
    # 名单取**收费口径 P1/P3/P5**（复函只列这三个）；2024 媒体「即停即走」口径是
    # P1/P3/P5/P7 四个，本包不取 P7（收费复函名单里没有，避免口径混用）。
    ("GZ-DROP-03", "P3 快速接送区落客点·南站南路（演示点）", "GZ-076", 0.50),
    ("GZ-DROP-04", "P1 快速接送区落客点·南站南路（演示点）", "GZ-075", 0.72),
    ("GZ-DROP-05", "P5 快速接送区落客点·南站北路（演示点）", "GZ-053", 0.50),
    # 候客区 / 蓄车区 / 上客点（接客不做在站口，而在候客区/蓄车区）
    # 网约车 2026-10-15 新规：须先进 P9–P10 蓄车听单，接单后凭订单 30 分钟内到东广场上客区
    ("GZ-ZONE-01", "东广场网约车上客区（演示点·荣诚西四街折线）", "GZ-557", 0.50),
    # 公开资料给的官方地址是「东广场荣诚西三街」，但本 OSM 切片只有荣诚西一/四/五街，
    # 无「荣诚西三街」——坐标取最近可用的荣诚西四街折线，名称里如实标出来，不写成西三街。
    ("GZ-ZONE-02", "东广场出租车场上客区（演示点）", "GZ-556", 0.50),
    ("GZ-ZONE-03", "P9–P10 网约车蓄车听单区（演示点·南站南路西段）", "GZ-076", 0.95),
    ("GZ-ZONE-04", "P8 停车场 C 区·旅游大巴上客点（演示点·南站北路）", "GZ-058", 0.50),
]

#: 推荐路线的落客点（送客默认落在东出发平台；须是上面 LANDMARKS 里的落客点 id）
RECOMMEND_DROPOFF = "GZ-DROP-01"


def _ts_str(value: str) -> str:
    """TS 单引号字符串（转义反斜杠/单引号）。"""
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _num(value: float, digits: int = 1) -> str:
    """数值 → TS 字面量（确定性、无多余小数）。"""
    rounded = round(float(value), digits)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.{digits}f}".rstrip("0").rstrip(".")


def _point_on_edge(edge: dict, frac: float) -> tuple[float, float]:
    """在真网路段折线上按弧长占比取一点（返回 WGS-84 经纬度）。

    只做**折线上的线性插值**，不把点移出折线：站点包 Z 的既有口径就是「坐标取对应路段
    折线上的演示点」。用平面近似算弧长（公里级范围内足够）：经度 1° ≈ 111320 m × cos(纬度)
    （111320 m 是赤道处每度经度长度），纬度 1° ≈ 111000 m。插值结果必然落在折线上。
    """
    coords = [tuple(map(float, pair)) for pair in (edge.get("coords") or [])]
    if len(coords) < 2:
        raise SystemExit(
            f"路段 {edge.get('segment_id')} 的 coords 少于 2 点，无法取演示点位（不编造坐标）"
        )
    ratio = min(1.0, max(0.0, float(frac)))
    seg_len: list[float] = []
    total = 0.0
    for index in range(len(coords) - 1):
        (lon1, lat1), (lon2, lat2) = coords[index], coords[index + 1]
        dx = (lon2 - lon1) * 111320.0 * math.cos(math.radians((lat1 + lat2) / 2.0))
        dy = (lat2 - lat1) * 111000.0
        step = math.hypot(dx, dy)
        seg_len.append(step)
        total += step
    target = total * ratio
    walked = 0.0
    for index, step in enumerate(seg_len):
        if walked + step >= target or index == len(seg_len) - 1:
            local = 0.0 if step <= 0 else (target - walked) / step
            local = min(1.0, max(0.0, local))
            (lon1, lat1), (lon2, lat2) = coords[index], coords[index + 1]
            return (lon1 + (lon2 - lon1) * local, lat1 + (lat2 - lat1) * local)
        walked += step
    return coords[-1]


def build_ts(site: dict, network: dict) -> str:
    """由站点登记表 + GZ 真网产物生成 stationGZ.ts 文本（纯函数，确定性）。"""
    edges = network["edges"]
    nodes = network["nodes"]
    seg_count = len(edges)
    range_m = int(round(float(site["range_m"])))
    site_name = str(site["site_name"])
    node_boundary = {
        str(node.get("node_id") or node.get("id")): bool(node.get("boundary")) for node in nodes
    }
    boundary_edges = [
        edge
        for edge in edges
        if node_boundary.get(str(edge.get("from"))) or node_boundary.get(str(edge.get("to")))
    ]

    # ---- 落客点 / 候客区：把 LANDMARKS 解析成带坐标的记录（段不存在就直接退出，不猜）----
    edges_by_segment = {str(edge.get("segment_id")): edge for edge in edges}
    marks: list[dict[str, Any]] = []
    for mark_id, mark_name, segment_id, frac in LANDMARKS:
        mark_edge = edges_by_segment.get(segment_id)
        if mark_edge is None:
            raise SystemExit(
                f"落客点/候客区 {mark_id} 指向的真网段 {segment_id} 不存在于 GZ 真网产物："
                "不生成站点包（换段请改 LANDMARKS 并重跑 build_junction_pack.py）"
            )
        lon, lat = _point_on_edge(mark_edge, frac)
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            raise SystemExit(f"落客点/候客区 {mark_id} 取到非法经纬度：不生成站点包")
        marks.append(
            {"id": mark_id, "name": mark_name, "segment_id": segment_id, "lon": lon, "lat": lat}
        )
    dropoff_marks = [mark for mark in marks if mark["id"].startswith("GZ-DROP-")]
    zone_marks = [mark for mark in marks if mark["id"].startswith("GZ-ZONE-")]
    if not any(mark["id"] == RECOMMEND_DROPOFF for mark in dropoff_marks):
        raise SystemExit(
            f"RECOMMEND_DROPOFF={RECOMMEND_DROPOFF} 不在落客点清单里：推荐路线会指向不存在的点位"
        )

    lines: list[str] = []
    lines.append(f"// 站点包 {PACK_KEY} ·「{site_name} · OSM 真路网」演示站（Issue IKNB9F）")
    lines.append("//")
    lines.append(f"// 来源：{Path(str(site['osm_file'])).name} 切片经 work/twin/netpack/build_junction_pack.py")
    lines.append(f"//   （① 获取路线 → ② 路口切分 → ③ 打标签）生成 {seg_count} 段 GZ-### 真网几何。")
    lines.append("// **几何取自 OSM（真值）**；路况指标 / 摄像头 / 推荐一律为**演示数据（模拟）**，不是实测。")
    lines.append("// 本文件由 work/frontend/scripts/gen_station_pack_gz.py 生成，**勿手改**；")
    lines.append("// 全段确定性演示基线（每段 level>=1，不灰档）；摄像头 = 演示层 708 路（N 段 = N 摄像头 =")
    lines.append("// N 视频，业主 2026-10-25 口径；GZ 源台账无登记，channels 取 demoCameraChannels.generated.ts）。")
    lines.append("")
    lines.append("import { STATION_GZ_SEGMENTS } from './stationGZ.network.ts'")
    # IKOQEJ：方向/车道/对向/贯通字段（只读 enriched 生成物；不改判级/契约）
    lines.append("import { STATION_GZ_DIRECTIONS } from './stationGZ.directions.generated.ts'")
    # 演示层摄像头（业主 2026-10-25）：由 gen_station_channels.py 从 camera-plan.json 生成
    lines.append("import { DEMO_CAMERA_CHANNELS } from './demoCameraChannels.generated.ts'")
    lines.append(
        "import type { PackAlertBase, PackDiversion, PackRecommend, PackSection, "
        "PackSegmentBase, StationPack } from './types.ts'"
    )
    lines.append("")
    lines.append("const LEVEL_CYCLE = [1, 2, 1, 3, 2, 1, 2, 4, 1, 2, 3, 1] as const")
    lines.append("const LEVEL_V_KMH = { 1: 34, 2: 22, 3: 13, 4: 7 } as const")
    lines.append("const LEVEL_Q_VPH = { 1: 320, 2: 900, 3: 1800, 4: 2600 } as const")
    lines.append("const LEVEL_LQ_M = { 1: 0, 2: 40, 3: 120, 4: 240 } as const")
    lines.append("const LEVEL_TD_MIN = { 1: 0, 2: 1.2, 3: 4.5, 4: 9 } as const")
    lines.append("const LEVEL_CI = { 1: 34, 2: 55, 3: 73, 4: 88 } as const")
    lines.append("const LEVEL_TRIGGERED: Record<number, string[]> = {")
    for level in (1, 2, 3, 4):
        lines.append(f"  {level}: {json.dumps(LEVEL_TRIGGERED[level], ensure_ascii=False)},")
    lines.append("}")
    lines.append("")
    lines.append("// 段长 / 车道数（来自真网产物；缺失则按演示默认 100 m / 2 道，并标 derive）")
    lines.append("const SEGMENT_META: Record<string, { length_m: number; lanes: number }> = {")
    for edge in edges:
        segment_id = str(edge["segment_id"])
        length_m = _num(edge.get("length_m") or 100.0)
        lanes = int(edge.get("lanes") or 2)
        lines.append(f"  {_ts_str(segment_id)}: {{ length_m: {length_m}, lanes: {lanes} }},")
    lines.append("}")
    lines.append("")
    lines.append("// 边界断面（站点包 contract：role=boundary 才允许同化回灌；GZ 暂无观测，仅做展示/占位）")
    lines.append("const BOUNDARY_SECTIONS: PackSection[] = [")
    for index, edge in enumerate(boundary_edges):
        segment_id = str(edge["segment_id"])
        name = str(edge.get("name") or segment_id)
        lines.append("  {")
        lines.append(f"    point_id: {_ts_str(f'GZ-DET-{index + 1:03d}')},")
        lines.append(f"    segment_id: {_ts_str(segment_id)},")
        lines.append(f"    name: {_ts_str(name + ' · 边界断面')},")
        lines.append("    role: 'boundary',")
        lines.append("    offset: 0.5,")
        lines.append(f"    sumo_edge_id: {_ts_str(segment_id)},")
        lines.append("  },")
    lines.append("]")
    lines.append("")
    lines.append(
        "// 全段演示基线：由段序号 / 段长确定性派生（演示数据；不是实测，四档均有、无灰档）"
    )
    lines.append("const SEGMENT_BASES: PackSegmentBase[] = STATION_GZ_SEGMENTS.map((seg, index) => {")
    lines.append("  const level = LEVEL_CYCLE[index % LEVEL_CYCLE.length]")
    lines.append("  const meta = SEGMENT_META[seg.segment_id] ?? { length_m: 100, lanes: 2 }")
    lines.append("  const v = LEVEL_V_KMH[level] + ((index * 3) % 5) - 2")
    lines.append("  const q = LEVEL_Q_VPH[level] + ((index * 37) % 120)")
    lines.append("  const cBase = meta.lanes * 2 * 1800")
    lines.append("  const lq = Math.min(meta.length_m, LEVEL_LQ_M[level])")
    lines.append("  return {")
    lines.append("    segment_id: seg.segment_id,")
    lines.append("    source: 'twin',")
    lines.append("    q_vph: q,")
    lines.append("    v_kmh: v,")
    lines.append("    v_f_kmh: 40,")
    lines.append("    k_vpk: Math.round((q / v) * 10) / 10,")
    lines.append("    L_q_m: lq,")
    lines.append("    L_seg_m: meta.length_m,")
    lines.append("    T_d_min: LEVEL_TD_MIN[level],")
    lines.append("    x: Math.round((q / cBase) * 100) / 100,")
    lines.append("    c_base_vph: cBase,")
    lines.append("    c_vph: cBase,")
    lines.append("    factors_applied: [],")
    lines.append("    ci: LEVEL_CI[level],")
    lines.append("    level,")
    lines.append("    triggered_by: LEVEL_TRIGGERED[level],")
    lines.append("    confidence: 0.8,")
    lines.append("    data_age_s: 6,")
    lines.append("    stale: false,")
    lines.append(f"    derive: {_ts_str(DEMO_DERIVE)},")
    lines.append("  }")
    lines.append("})")
    lines.append("")
    lines.append("const ALERTS: PackAlertBase[] = SEGMENT_BASES.filter((base) => base.level >= 3)")
    lines.append("  .slice(0, 3)")
    lines.append("  .map((base, index): PackAlertBase => ({")
    lines.append("    alert_id: `GZ-ALERT-${String(index + 1).padStart(2, '0')}`,")
    lines.append("    segment_id: base.segment_id,")
    lines.append("    level: base.level as 3 | 4,")
    lines.append("    triggered_by: base.triggered_by,")
    lines.append("    factor_ids: index === 0 ? ['F03'] : [],")
    lines.append("    ago_min: 8 + index * 4,")
    lines.append("    status: index === 0 ? '待认领' : '处置中',")
    lines.append("  }))")
    lines.append("")
    lines.append("const DIVERSION_FALLBACK: PackDiversion = {")
    lines.append("  segment_id: STATION_GZ_SEGMENTS[0].segment_id,")
    lines.append("  target_segment_id: STATION_GZ_SEGMENTS[1].segment_id,")
    lines.append(f"  target_name: {_ts_str('演示分流目标（非实测）')},")
    lines.append("  base_pct: 20,")
    lines.append("  min_pct: 5,")
    lines.append("  max_pct: 40,")
    lines.append(f"  expect: {_ts_str('演示数据（模拟）：分流后等待时间变化不做精度承诺')},")
    lines.append(f"  why: {_ts_str('GZ 暂无真实分流方案产物；本卡为演示占位，不冒充引擎结果')},")
    lines.append("}")
    lines.append("")
    lines.append("const RECOMMEND: PackRecommend = {")
    lines.append("  location_segment_id: STATION_GZ_SEGMENTS[0].segment_id,")
    lines.append("  location_offset_m: 80,")
    lines.append("  arrival_segments: [")
    lines.append("    STATION_GZ_SEGMENTS[0].segment_id,")
    lines.append("    STATION_GZ_SEGMENTS[1].segment_id,")
    lines.append("  ],")
    lines.append("  arrival_eta_min: 4.2,")
    lines.append(f"  arrival_dropoff_point: {_ts_str(RECOMMEND_DROPOFF)},")
    lines.append("  arrival_walk_min: 1.6,")
    lines.append("  departure_segments: [STATION_GZ_SEGMENTS[2].segment_id],")
    lines.append("  departure_eta_min: 3.1,")
    lines.append("  alternatives: [")
    lines.append("    {")
    lines.append("      path_id: 'P-2',")
    lines.append("      segments: [STATION_GZ_SEGMENTS[1].segment_id],")
    lines.append("      eta_min: 5.0,")
    lines.append(f"      note: {_ts_str('演示备选（模拟）')} ,")
    lines.append("    },")
    lines.append("    {")
    lines.append("      path_id: 'P-3',")
    lines.append("      segments: [STATION_GZ_SEGMENTS[2].segment_id],")
    lines.append("      eta_min: 5.6,")
    lines.append(f"      note: {_ts_str('演示备选（模拟）')} ,")
    lines.append("    },")
    lines.append("  ],")
    lines.append(
        f"  why: {_ts_str('演示数据（模拟）：广州南站站点包内的演示推荐，未接决策引擎真网路线产物')} ,"
    )
    lines.append("}")
    lines.append("")
    lines.append("export const STATION_GZ: StationPack = {")
    lines.append(f"  key: {_ts_str(PACK_KEY)},")
    lines.append(f"  label: {_ts_str(f'{site_name} · {seg_count} 段')},")
    lines.append(
        f"  note: {_ts_str(f'{site_name} OSM 真路网 {seg_count} 段（演示范围 {range_m} m）· 几何为真值（OSM）· 全段确定性演示基线（不是实测）· 未接摄像头登记')} ,"
    )
    lines.append("  station: {")
    lines.append(f"    station_id: {_ts_str(str(site['site_id']))},")
    lines.append(f"    name: {_ts_str(site_name)},")
    lines.append(
        f"    subtitle: {_ts_str(f'广东广州 · 站区 {range_m} m · {seg_count} 段（几何 OSM 真值 · 演示数据（模拟））')},"
    )
    lines.append(f"    range_m: {range_m},")
    lines.append(f"    range_source: '{site['range_source']}',")
    lines.append(f"    segment_count: {seg_count},")
    lines.append("  },")
    lines.append("  segments: STATION_GZ_SEGMENTS,")
    # IKOQEJ：enriched 只读生成的方向/车道/贯通字段（路由网展示用，非契约）
    lines.append("  segmentDirections: STATION_GZ_DIRECTIONS,")
    lines.append("  source: {")
    lines.append("    osm: true,")
    lines.append(f"    label: {_ts_str(f'{site_name} OSM 真路网（Overpass 切片，演示范围 {range_m} m）')},")
    lines.append(f"    attribution: {_ts_str('© OpenStreetMap contributors · ODbL 1.0')},")
    lines.append("  },")
    lines.append("  sections: BOUNDARY_SECTIONS,")
    lines.append("  // 落客点 / 候客区（语义取自广州南站公开资料；坐标取真网路段折线上的演示点，")
    lines.append("  // 不是踏勘点位。真实点位归 IKMHMX）")
    lines.append("  dropoffs: [")
    for mark in dropoff_marks:
        lines.append("    {")
        lines.append(f"      id: {_ts_str(mark['id'])},")
        lines.append(f"      name: {_ts_str(mark['name'])},")
        lines.append(f"      lon: {_num(mark['lon'], 7)},")
        lines.append(f"      lat: {_num(mark['lat'], 7)},")
        lines.append("    },")
    lines.append("  ],")
    lines.append("  zones: [")
    for mark in zone_marks:
        lines.append("    {")
        lines.append(f"      id: {_ts_str(mark['id'])},")
        lines.append(f"      name: {_ts_str(mark['name'])},")
        lines.append(f"      lon: {_num(mark['lon'], 7)},")
        lines.append(f"      lat: {_num(mark['lat'], 7)},")
        lines.append("    },")
    lines.append("  ],")
    lines.append("  stations: [")
    lines.append("    {")
    lines.append(f"      id: {_ts_str(str(site['site_id']))},")
    lines.append(f"      name: {_ts_str(site_name)},")
    lines.append(f"      lon: {_num(float(site['anchor_lonlat'][0]), 7)},")
    lines.append(f"      lat: {_num(float(site['anchor_lonlat'][1]), 7)},")
    lines.append("      sub: 'GZ',")
    lines.append("    },")
    lines.append("  ],")
    lines.append("  segmentBases: SEGMENT_BASES,")
    lines.append("  vehicleBases: [")
    lines.append("    {")
    lines.append("      vehicle_id: 'twin-GZ-D1-0001',")
    lines.append("      driver_type: 'D1',")
    lines.append("      segment_id: STATION_GZ_SEGMENTS[0].segment_id,")
    lines.append("      offset_m: 40,")
    lines.append("      speed_mps: 8.5,")
    lines.append("      state: '行驶',")
    lines.append("      guided: false,")
    lines.append("    },")
    lines.append("    {")
    lines.append("      vehicle_id: 'twin-GZ-D2-0001',")
    lines.append("      driver_type: 'D2',")
    lines.append("      segment_id: STATION_GZ_SEGMENTS[1].segment_id,")
    lines.append("      offset_m: 120,")
    lines.append("      speed_mps: 3.2,")
    lines.append("      state: '候客',")
    lines.append("      guided: false,")
    lines.append("      is_demo_bound: true,")
    lines.append("    },")
    lines.append("  ],")
    lines.append("  alerts: ALERTS,")
    lines.append("  seedDispatch: {},")
    lines.append("  diversion: {},")
    lines.append("  diversionFallback: DIVERSION_FALLBACK,")
    lines.append("  channels: DEMO_CAMERA_CHANNELS.GZ,")
    lines.append("  videoCovered: [],")
    lines.append("  colorPolicy: 'all',")
    lines.append("  assimilation: [],")
    lines.append("  assimilationGate: { confidence_min: 0.75, data_age_max_s: 120 },")
    lines.append("  recommend: RECOMMEND,")
    lines.append("  context: {")
    lines.append("    weather: {")
    lines.append("      condition: '晴',")
    lines.append("      temp_c: 26,")
    lines.append("      humidity_pct: 62,")
    lines.append("      visibility_km: 12,")
    lines.append("      precip_mm: 0,")
    lines.append("      wind: '东南风 2 级',")
    lines.append("    },")
    lines.append("    calendar: '工作日',")
    lines.append(
        f"    next_train_note: {_ts_str('演示数据（模拟）：GZ 列车时刻未接入（真实时刻表归 IKMHMX），不展示到发时刻')} ,"
    )
    lines.append("  },")
    lines.append("  scenarios: [")
    for key, name, note, factor_ids in (
        ("S1", "常态", "演示：无额外因素", []),
        ("S2", "峰值", "演示：列车集中到达 / 需求放大（F03）", ["F03"]),
        ("S3", "突发", "演示：事故封道（F07）", ["F07"]),
        ("S4", "多因素", "演示：大雨 + 需求 + 时段（F01/F03/F10）", ["F01", "F03", "F10"]),
    ):
        lines.append("    {")
        lines.append(f"      key: {_ts_str(key)},")
        lines.append(f"      name: {_ts_str(name)},")
        lines.append(f"      note: {_ts_str(note)},")
        lines.append(f"      factor_ids: {json.dumps(factor_ids, ensure_ascii=False)},")
        lines.append("    },")
    lines.append("  ],")
    lines.append("  bridge: { enabled: false, base: '' },")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成/比对广州南站站点包 stationGZ.ts（脚本产物）")
    parser.add_argument("--check", action="store_true", help="只比对既有产物，不写盘")
    ns = parser.parse_args(argv)

    site = load_site(SITE_ID)
    network_path = repo_path(str(site["out_json"]))
    if not network_path.is_file():
        raise SystemExit(
            f"缺 GZ 真网产物 {network_path}（先跑 build_junction_pack.py --site-id {SITE_ID}）"
        )
    network = json.loads(network_path.read_text(encoding="utf-8"))
    seg_target = int(site["seg_target"])
    if len(network.get("edges") or []) != seg_target:
        raise SystemExit(
            f"真网段数 {len(network.get('edges') or [])} ≠ 登记表 seg_target {seg_target}：不生成站点包"
        )
    out_path = repo_path(str(site["station_pack_meta_ts"]))
    text = build_ts(site, network)

    if ns.check:
        have = out_path.read_text(encoding="utf-8").replace("\r\n", "\n") if out_path.exists() else ""
        if have != text:
            print(f"❌ 与既有产物不一致：{out_path}")
            return 1
        print(f"✅ 一致：{out_path}")
        return 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    print(f"→ {out_path}")
    print(f"站点包 {PACK_KEY}：{seg_target} 段（{site['site_name']}）· 范围 {site['range_m']} m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
