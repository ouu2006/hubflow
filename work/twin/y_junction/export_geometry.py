# -*- coding: utf-8 -*-
"""导出 Y 型路网几何为 JSON（对齐 stationB.network.ts 的 segments[] 形状）。"""
import os, json, math
import numpy as np

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(OUT_DIR, "y_junction_geometry.json")

H_PAV  = 7.5
H_EDGE = 7.0
R_FIL  = 5.0
ARM_A_DEG = 135.0
ARM_B_DEG = 45.0
ARM_S_DEG = 270.0

def unit(deg):
    a = math.radians(deg)
    return np.array([math.cos(a), math.sin(a)])

class Arm:
    def __init__(self, name, deg):
        self.name = name
        self.deg = deg
        self.u = unit(deg)
        self.n = np.array([-self.u[1], self.u[0]])

ARM_A = Arm("A", ARM_A_DEG)
ARM_B = Arm("B", ARM_B_DEG)
ARM_S = Arm("S", ARM_S_DEG)
ORDER = [ARM_S, ARM_B, ARM_A]
PAIRS = list(zip(ORDER, ORDER[1:] + ORDER[:1]))
NEXT_CCW = {ORDER[k].name: ORDER[(k + 1) % 3].name for k in range(3)}
PREV_CCW = {ORDER[k].name: ORDER[(k - 1) % 3].name for k in range(3)}

def corner_geom(i, j, h, r):
    ui, uj, ni, nj = i.u, j.u, i.n, j.n
    M = np.array([[ui[0], -uj[0]], [ui[1], -uj[1]]])
    t1, t2 = np.linalg.solve(M, -h * (ni + nj))
    V = t1 * ui + h * ni
    th = np.degrees(math.acos(np.clip(np.dot(ui, uj), -1.0, 1.0)))
    al = math.radians(th / 2.0)
    L = r / math.tan(al)
    d = r / math.sin(al)
    bis = ui + uj
    bis = bis / np.linalg.norm(bis)
    C = V + d * bis
    T1 = V + L * ui
    T2 = V + L * uj
    a1 = math.atan2(T1[1] - C[1], T1[0] - C[0])
    a2 = math.atan2(T2[1] - C[1], T2[0] - C[0])
    dth = math.radians(((a2 - a1 + math.pi) % (2*math.pi)) - math.pi)
    ang = a1 + np.linspace(0.0, dth, 48)
    arc = np.column_stack([C[0] + r * np.cos(ang), C[1] + r * np.sin(ang)])
    return dict(V=V, T1=T1, T2=T2, C=C, arc=arc)

# CORN[(leg_cw, leg_ccw)] = corner geometry
CORN  = {(i.name, j.name): corner_geom(i, j, H_PAV,  R_FIL) for i, j in PAIRS}
CORN_E = {(i.name, j.name): corner_geom(i, j, H_EDGE, R_FIL) for i, j in PAIRS}


def make_boundary_segment(seg_id, name, leg_name, corner_pair):
    """
    corner_pair = (cw_leg, ccw_leg) — 这条 boundary 属于该 corner。
    几何：从 corner_pair[0] 腿的 T1 → corner arc → corner_pair[1] 腿的 T2 → 直延伸。
    """
    c = CORN[corner_pair]
    c_e = CORN_E[corner_pair]
    arm_i = {"A": ARM_A, "B": ARM_B, "S": ARM_S}[corner_pair[0]]
    arm_j = {"A": ARM_A, "B": ARM_B, "S": ARM_S}[corner_pair[1]]

    pts = []
    # 从 corner_pair[0] 腿的 +n 侧切点 T1 出发
    pts.append(c["T1"].tolist())
    pts.extend(c["arc"].tolist())
    pts.append(c["T2"].tolist())
    # 沿 corner_pair[1] 腿直行
    pts.append((c["T2"] + 400.0 * arm_j.u).tolist())
    # 沿 corner_pair[0] 腿反向（从 T1 往回）—— 补全成一个闭环的一半
    pts_rev = [(c_e["T1"] - 80.0 * arm_i.u).tolist()]
    pts_rev.extend(c_e["arc"][::-1].tolist())
    pts_rev.append(c_e["T2"].tolist())

    full = pts + pts_rev
    # 简化采样
    if len(full) > 120:
        idx = np.linspace(0, len(full) - 1, 120).astype(int)
        full = [full[i] for i in idx]
    return {
        "segment_id": seg_id,
        "name": name,
        "role": "boundary",
        "coords": [[round(float(p[0]), 3), round(float(p[1]), 3)] for p in full],
    }


def make_internal_segment(seg_id, name, arm_name, offset_sign, t_start, t_end, n_pts=60):
    a = {"A": ARM_A, "B": ARM_B, "S": ARM_S}[arm_name]
    ts = np.linspace(t_start, t_end, n_pts)
    pts = []
    for t in ts:
        p = t * a.u + offset_sign * 0.5 * a.n
        pts.append([round(float(p[0]), 3), round(float(p[1]), 3)])
    return {
        "segment_id": seg_id,
        "name": name,
        "role": "internal",
        "coords": pts,
    }


def make_road_segment(seg_id, name, arm_name, offset, t_start, t_end, n_pts=80):
    a = {"A": ARM_A, "B": ARM_B, "S": ARM_S}[arm_name]
    ts = np.linspace(t_start, t_end, n_pts)
    pts = []
    for t in ts:
        p = t * a.u + offset * a.n
        pts.append([round(float(p[0]), 3), round(float(p[1]), 3)])
    return {
        "segment_id": seg_id,
        "name": name,
        "role": "road",
        "coords": pts,
    }


# ---- 构建 segments ----
segments = []

# 边界 segment：6 个 corner，顺时针顺序 (S,B) (B,A) (A,S)
boundary_defs = [
    ("BND-SB", "S-B 转角缘石", ("S", "B")),
    ("BND-BA", "B-A 转角缘石", ("B", "A")),
    ("BND-AS", "A-S 转角缘石", ("A", "S")),
]
for sid, sname, cpair in boundary_defs:
    segments.append(make_boundary_segment(sid, sname, cpair[0], cpair))

# 内部参考线（每条腿 2 条 = 6 条）
internal_defs = [
    ("INT-S-CW",  "S 腿内侧参考线(+n)", "S", +1, 1.0, 34.0),
    ("INT-S-CCW", "S 腿外侧参考线(-n)", "S", -1, 1.0, 34.0),
    ("INT-B-CW",  "B 腿内侧参考线(+n)", "B", +1, 1.0, 34.0),
    ("INT-B-CCW", "B 腿外侧参考线(-n)", "B", -1, 1.0, 34.0),
    ("INT-A-CW",  "A 腿内侧参考线(+n)", "A", +1, 1.0, 34.0),
    ("INT-A-CCW", "A 腿外侧参考线(-n)", "A", -1, 1.0, 34.0),
]
for sid, sname, arm, sgn, t0, t1 in internal_defs:
    segments.append(make_internal_segment(sid, sname, arm, sgn, t0, t1))

# 路面中心线（road）
road_defs = [
    ("RD-S", "S 腿路面中心线", "S",  0.0, 0.5, 35.0),
    ("RD-B", "B 腿路面中心线", "B",  0.0, 0.5, 35.0),
    ("RD-A", "A 腿路面中心线", "A",  0.0, 0.5, 35.0),
]
for sid, sname, arm, off, t0, t1 in road_defs:
    segments.append(make_road_segment(sid, sname, arm, off, t0, t1))

# ---- 默认 congestion 分级 ----
# 业主口径：右侧(B)拥堵、左侧(A)畅通、主线(S)缓行
default_congestion = {
    "BND-SB":  1,   # S↔B 转角 = 右上方 → 缓行
    "BND-BA":  3,   # B↔A 转角 = 右上方更重 → 严重拥堵
    "BND-AS":  0,   # A↔S 转角 = 左侧 → 畅通
    "INT-S-CW":  1,
    "INT-S-CCW": 0,
    "INT-B-CW":  3,
    "INT-B-CCW": 0,
    "INT-A-CW":  0,
    "INT-A-CCW": 0,
    "RD-S": 1,
    "RD-B": 3,
    "RD-A": 0,
}

for seg in segments:
    seg["congestion_level"] = default_congestion.get(seg["segment_id"], 0)

# ---- 输出 ----
with open(OUT, "w", encoding="utf-8") as f:
    json.dump({
        "description": "Y 型路网几何（手工生成，对齐 stationB.network.ts segments[] 结构）",
        "segments": segments,
    }, f, ensure_ascii=False, indent=2)

print("saved:", OUT)
print("total segments:", len(segments))
print("segment ids:", [s["segment_id"] for s in segments])
