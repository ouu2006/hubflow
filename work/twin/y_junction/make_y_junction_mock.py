# -*- coding: utf-8 -*-
"""
生成 Y 型路网演示用 mock 数据（JSON 格式，供 DashboardView 直接读取）。
生成后直接写入前端可引用的位置，不走 API。
"""
import json, math, random, os
from datetime import datetime, timedelta
from pathlib import Path

random.seed(2026)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "y_junction_mock.json"

# ---- 加载几何 ----
geom = json.loads((ROOT / "y_junction_geometry.json").read_text(encoding="utf-8"))
segments_geom = geom["segments"]

# ---- 指标基线（预置演示值）----
# 业主口径：右侧(B)拥堵(level 3/2)、左侧(A)畅通(level 0/1)、主线(S)缓行(level 1/2)
BASELINES = {
    # boundary
    "BND-SB":  {"q_vph": 3200, "v_kmh": 28, "v_f_kmh": 60, "k_vpk": 114, "L_q_m": 180, "L_seg_m": 2100, "T_d_min": 4.2,  "x": 0.72, "c_base_vph": 4200, "c_vph": 3900},
    "BND-BA":  {"q_vph": 3600, "v_kmh": 22, "v_f_kmh": 60, "k_vpk": 164, "L_q_m": 280, "L_seg_m": 2300, "T_d_min": 5.8,  "x": 0.85, "c_base_vph": 4200, "c_vph": 3600},
    "BND-AS":  {"q_vph": 2100, "v_kmh": 45, "v_f_kmh": 60, "k_vpk": 47,  "L_q_m": 60,  "L_seg_m": 2000, "T_d_min": 2.1,  "x": 0.42, "c_base_vph": 4200, "c_vph": 4000},
    # internal
    "INT-S-CW":  {"q_vph": 2400, "v_kmh": 40, "v_f_kmh": 60, "k_vpk": 60,  "L_q_m": 70,  "L_seg_m": 1800, "T_d_min": 2.4,  "x": 0.48, "c_base_vph": 4200, "c_vph": 3900},
    "INT-S-CCW": {"q_vph": 1800, "v_kmh": 52, "v_f_kmh": 60, "k_vpk": 35,  "L_q_m": 40,  "L_seg_m": 1800, "T_d_min": 1.5,  "x": 0.32, "c_base_vph": 4200, "c_vph": 4100},
    "INT-B-CW":  {"q_vph": 3400, "v_kmh": 18, "v_f_kmh": 60, "k_vpk": 189, "L_q_m": 310, "L_seg_m": 1700, "T_d_min": 6.5,  "x": 0.91, "c_base_vph": 3800, "c_vph": 3000},
    "INT-B-CCW": {"q_vph": 800,  "v_kmh": 55, "v_f_kmh": 60, "k_vpk": 15,  "L_q_m": 15,  "L_seg_m": 1700, "T_d_min": 0.8,  "x": 0.15, "c_base_vph": 3800, "c_vph": 3700},
    "INT-A-CW":  {"q_vph": 900,  "v_kmh": 54, "v_f_kmh": 60, "k_vpk": 17,  "L_q_m": 18,  "L_seg_m": 1600, "T_d_min": 0.9,  "x": 0.16, "c_base_vph": 3800, "c_vph": 3700},
    "INT-A-CCW": {"q_vph": 600,  "v_kmh": 58, "v_f_kmh": 60, "k_vpk": 10,  "L_q_m": 10,  "L_seg_m": 1600, "T_d_min": 0.6,  "x": 0.10, "c_base_vph": 3800, "c_vph": 3750},
    # road
    "RD-S": {"q_vph": 4500, "v_kmh": 35, "v_f_kmh": 60, "k_vpk": 129, "L_q_m": 120, "L_seg_m": 5000, "T_d_min": 3.5,  "x": 0.60, "c_base_vph": 7500, "c_vph": 6800},
    "RD-B": {"q_vph": 3800, "v_kmh": 20, "v_f_kmh": 60, "k_vpk": 190, "L_q_m": 350, "L_seg_m": 4500, "T_d_min": 7.0,  "x": 0.88, "c_base_vph": 5000, "c_vph": 3800},
    "RD-A": {"q_vph": 1500, "v_kmh": 55, "v_f_kmh": 60, "k_vpk": 27,  "L_q_m": 30,  "L_seg_m": 4200, "T_d_min": 1.4,  "x": 0.25, "c_base_vph": 5000, "c_vph": 4800},
}

# ---- 判级（基于饱和度 x）----
# 注意：CongestionLevel 类型是 1|2|3|4，不是 0|1|2|3
# 0 保留给「数据不可用」(stale)，不在判级里使用
def level_from_x(x):
    if x >= 0.85: return 4  # 严重拥堵
    if x >= 0.70: return 3  # 拥堵
    if x >= 0.45: return 2  # 缓行
    return 1                # 畅通

# ---- 生成 segment 记录 ----
segments = []
for sg in segments_geom:
    sid = sg["segment_id"]
    base = BASELINES.get(sid, {})
    x = base.get("x", 0.5)
    # 加少量随机抖动（演示用）
    x = max(0.0, min(1.0, x + random.uniform(-0.03, 0.03)))
    level = level_from_x(x)
    segments.append({
        "segment_id": sid,
        "name": sg["name"],
        "source": "demo",
        "q_vph": base.get("q_vph", 1000),
        "v_kmh": base.get("v_kmh", 50),
        "v_f_kmh": base.get("v_f_kmh", 60),
        "k_vpk": base.get("k_vpk", 50),
        "L_q_m": base.get("L_q_m", 50),
        "L_seg_m": base.get("L_seg_m", 1000),
        "T_d_min": base.get("T_d_min", 2.0),
        "x": round(x, 2),
        "c_base_vph": base.get("c_base_vph", 4000),
        "c_vph": base.get("c_vph", 3500),
        "factors_applied": [],
        "ci": round(x * 100, 1),
        "level": level,
        "level_name": {1: "畅通", 2: "缓行", 3: "拥堵", 4: "严重拥堵"}[level],
        "triggered_by": [],
        "confidence": 0.95,
        "data_age_s": 5,
        "stale": False,
        "pred": {
            "h15": {"q_vph": int(base.get("q_vph", 1000) * 1.1), "level": min(4, level + 1)},
            "h30": {"q_vph": int(base.get("q_vph", 1000) * 1.2), "level": min(4, level + 1)},
            "model": "L0"
        }
    })

# ---- 生成车辆（演示绑定车，不画小球）----
# 为了展示"有车辆数据但不画小球"，生成少量车辆记录
vehicles = []
for i, sg in enumerate(segments_geom[:6]):  # 前 6 条路段各放 2 辆车
    for j in range(2):
        vehicles.append({
            "vehicle_id": f"VEH-{i*2+j+1:03d}",
            "segment_id": sg["segment_id"],
            "state": "parked" if j == 0 else "moving",
            "driver_type": "D1",
            "speed_kmh": 0.0 if j == 0 else 25.0,
            "offset": 0.5,
            "is_demo_bound": True,
        })

# ---- 生成 overview ----
level_dist = []
for lv in range(4):
    count = sum(1 for s in segments if s["level"] == lv)
    if count > 0:
        level_dist.append({
            "level": lv,
            "name": {0: "畅通", 1: "缓行", 2: "拥堵", 3: "严重拥堵"}[lv],
            "count": count,
            "color": {0: "#4caf50", 1: "#ffeb3b", 2: "#ff9800", 3: "#f44336"}[lv]
        })

overview = {
    "station_id": "YJ-001",
    "station_name": "Y 型交叉口（V0 演示）",
    "updated_at": (datetime.now() - timedelta(seconds=5)).isoformat(),
    "vehicles_inbound": 42,
    "vehicles_outbound": 38,
    "vehicles_guided": 15,
    "guided_rate": 0.35,
    "level_distribution": level_dist,
    "worst_segment": max(segments, key=lambda s: s["x"]),
}

# ---- 输出 ----
output = {
    "segments": segments,
    "vehicles": vehicles,
    "overview": overview,
    "meta": {
        "station_id": "YJ-001",
        "network_source": "y_junction_geometry.json",
        "generated_at": datetime.now().isoformat(),
        "note": "Y 型路网 V0 演示数据（右侧拥堵/左侧通畅/无小球）"
    }
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"saved: {OUT}")
print(f"segments: {len(segments)}")
print(f"vehicles: {len(vehicles)}")
print(f"level distribution:", {r["name"]: r["count"] for r in level_dist})
