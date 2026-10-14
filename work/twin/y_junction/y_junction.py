# -*- coding: utf-8 -*-
"""
Y 型路网 平面示意图  —— 纯几何绘制，不依赖任何项目代码/数据。
几何：三条 15 m 路幅的道路（两臂与主线各夹 45°）汇聚于一处三岔口，
      沥青面 = 三条半幅走廊的并集 + 三个圆角（缘石转弯半径 R=5 m），
      标注 = 车道边线 / 双黄线 / 虚线车道分界 / 人行横道 / 停止线 / 导向箭头 / 指北针 / 比例尺。
输出：y_junction.png (300 dpi) 与 y_junction.svg (矢量，文字转路径)
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle
from matplotlib.font_manager import FontProperties

# 输出到脚本所在目录的 figures/ 子目录
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT_DIR, exist_ok=True)

# ----------------------------------------------------------------- 参数（米）
H_PAV  = 7.5      # 沥青路面半宽
H_EDGE = 7.0      # 车道边线中心至轴线的偏移
CURB_W = 0.60     # 缘石带宽度
EDGE_W = 0.22     # 白色边线宽
LANE_W = 0.15     # 车道分界线宽
YEL_W  = 0.15     # 黄线宽
YEL_OFF = 0.20    # 双黄线各自偏移
R_FIL  = 5.0      # 缘石转弯半径
XLIM = (-40.0, 40.0)
YLIM = (-44.0, 46.0)

# 标记桩号（沿线自路口中心向外的距离，米）
D_CW_A    = 11.8   # 人行横道近端
D_CW_B    = 15.3   # 人行横道远端
D_JUNC    = 16.5   # 停止线（须在人行横道外侧）
D_MARK    = 17.5   # 各类纵向标线起点
D_SOLID   = 32.0   # 进口道实线段终点
D_ARROW   = 20.5   # 导向箭头起点

C_ASPH  = "#4b4f55"
C_GREEN = "#d8e5d3"
C_CURB  = "#2b2e33"
C_WHITE = "#fbfbfb"
C_YEL   = "#f2c94c"
C_TXT   = "#2b2e33"
C_GRAY  = "#6a7076"
C_FRAME = "#c9ccc6"

plt.rcParams["font.family"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


# ----------------------------------------------------------------- 几何工具
def unit(deg):
    a = np.deg2rad(deg)
    return np.array([np.cos(a), np.sin(a)])


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


class Arm:
    """一条腿：u = 自路口中心指向外的单位方向；n = u 左侧法向。"""

    def __init__(self, name, deg):
        self.name = name
        self.deg = deg
        self.u = unit(deg)
        self.n = np.array([-self.u[1], self.u[0]])


ARM_A = Arm("A", 135.0)   # 左臂
ARM_B = Arm("B", 45.0)    # 右臂
ARM_S = Arm("S", 270.0)   # 主线（向下）
ORDER = [ARM_S, ARM_B, ARM_A]                 # 按方位角逆时针
PAIRS = list(zip(ORDER, ORDER[1:] + ORDER[:1]))  # (S,B) (B,A) (A,S)


def corner_geom(i, j, h, r):
    """相邻两腿 i(顺时针侧)、j(逆时针侧) 的阴角：交点 V、切点 T1/T2、圆弧。"""
    ui, uj, ni, nj = i.u, j.u, i.n, j.n
    M = np.array([[ui[0], -uj[0]], [ui[1], -uj[1]]])
    t1, t2 = np.linalg.solve(M, -h * (ni + nj))
    V = t1 * ui + h * ni
    th = np.degrees(np.arccos(np.clip(np.dot(ui, uj), -1.0, 1.0)))  # 夹角
    al = np.radians(th / 2.0)
    L = r / np.tan(al)                    # 切点到角点距离
    d = r / np.sin(al)                    # 圆心到角点距离
    bis = ui + uj
    bis = bis / np.linalg.norm(bis)       # 指向凹角外侧（即圆心方向）
    C = V + d * bis
    T1 = V + L * ui
    T2 = V + L * uj
    a1 = np.arctan2(T1[1] - C[1], T1[0] - C[0])
    a2 = np.arctan2(T2[1] - C[1], T2[0] - C[0])
    dth = np.radians(wrap180(np.degrees(a2 - a1)))
    ang = a1 + np.linspace(0.0, dth, 48)
    arc = np.column_stack([C[0] + r * np.cos(ang), C[1] + r * np.sin(ang)])
    return dict(V=V, T1=T1, T2=T2, C=C, arc=arc, th=th)


CORN_FILL = {(i.name, j.name): corner_geom(i, j, H_PAV, R_FIL) for i, j in PAIRS}
CORN_EDGE = {(i.name, j.name): corner_geom(i, j, H_EDGE, R_FIL) for i, j in PAIRS}
NEXT_CCW = {ORDER[k].name: ORDER[(k + 1) % 3].name for k in range(3)}
PREV_CCW = {ORDER[k].name: ORDER[(k - 1) % 3].name for k in range(3)}

# ----------------------------------------------------------------- 画布
FIG_H = 9.2
AX_FRAC = 0.955
ax_h_in = FIG_H * AX_FRAC
ax_w_in = ax_h_in * (XLIM[1] - XLIM[0]) / (YLIM[1] - YLIM[0])
FIG_W = ax_w_in / AX_FRAC
fig = plt.figure(figsize=(FIG_W, FIG_H), dpi=110, facecolor="white")
ax = fig.add_axes([(1 - AX_FRAC) / 2, (1 - AX_FRAC) / 2, AX_FRAC, AX_FRAC])
ax.set_xlim(*XLIM)
ax.set_ylim(*YLIM)
ax.set_aspect("equal")
ax.set_xticks([])
ax.set_yticks([])
for s in ax.spines.values():
    s.set_color(C_FRAME)
    s.set_linewidth(0.8)

PT_PER_M = ax_w_in * 72.0 / (XLIM[1] - XLIM[0])   # 数据米 -> 点


def lw(width_m):
    return width_m * PT_PER_M


def fill_poly(pts, color, z):
    ax.add_patch(Polygon(np.asarray(pts), closed=True, facecolor=color,
                         edgecolor="none", zorder=z))


def stroke(pts, width_m, color, z, dashes=None, cap="round"):
    pts = np.asarray(pts, float)
    kw = dict(color=color, lw=lw(width_m), solid_capstyle=cap,
              solid_joinstyle="round", zorder=z)
    if dashes is not None:
        kw["dashes"] = tuple(d * PT_PER_M for d in dashes)
        kw["dash_capstyle"] = "butt"
    ax.plot(pts[:, 0], pts[:, 1], **kw)


def arm_point(a, t, off=0.0):
    return t * a.u + off * a.n


# ============================================================ 1. 绿化带（路面被挖空）
for (i, j) in PAIRS:
    V = CORN_FILL[(i.name, j.name)]["V"]
    a1 = i.deg
    a2 = a1 + (((j.deg - i.deg) % 360.0) or 360.0)
    angs = np.radians(np.linspace(a1, a2, 30))
    fan = np.vstack([[V], V + 400.0 * np.column_stack([np.cos(angs), np.sin(angs)])])
    fill_poly(fan, C_GREEN, 1)

# ============================================================ 2. 沥青路面
for a in ORDER:                                     # 三条半幅走廊
    pts = [arm_point(a, 0.0, -H_PAV), arm_point(a, 400.0, -H_PAV),
           arm_point(a, 400.0, H_PAV), arm_point(a, 0.0, H_PAV)]
    fill_poly(pts, C_ASPH, 2)
for k in CORN_FILL.values():                        # 三个圆角补块
    fill_poly(np.vstack([[k["V"]], k["arc"], [k["T2"]]]), C_ASPH, 2.1)

# ============================================================ 3. 缘石 + 白色车道边线
for a in ORDER:
    nxt = NEXT_CCW[a.name]
    prv = PREV_CCW[a.name]
    tp = CORN_EDGE[(a.name, nxt)]["T1"]             # 本腿 +n 侧切点
    stroke([tp, tp + 400.0 * a.u], CURB_W, C_CURB, 3)
    stroke([tp, tp + 400.0 * a.u], EDGE_W, C_WHITE, 4)
    tm = CORN_EDGE[(prv, a.name)]["T2"]             # 本腿 -n 侧切点
    stroke([tm, tm + 400.0 * a.u], CURB_W, C_CURB, 3)
    stroke([tm, tm + 400.0 * a.u], EDGE_W, C_WHITE, 4)
for k in CORN_EDGE.values():
    stroke(k["arc"], CURB_W, C_CURB, 3)
    stroke(k["arc"], EDGE_W, C_WHITE, 4)

# ============================================================ 4. 人行横道
STRIPE, GAP = 0.45, 0.45
n_side = int((6.8 + STRIPE / 2) // (STRIPE + GAP))
for a in ORDER:
    for m in range(-n_side, n_side + 1):
        c = m * (STRIPE + GAP)
        if abs(c) + STRIPE / 2 > 6.9:
            continue
        pts = [arm_point(a, D_CW_A, c - STRIPE / 2), arm_point(a, D_CW_B, c - STRIPE / 2),
               arm_point(a, D_CW_B, c + STRIPE / 2), arm_point(a, D_CW_A, c + STRIPE / 2)]
        fill_poly(pts, C_WHITE, 5)

# ============================================================ 5. 停止线（进口半幅）
for a in ORDER:
    pts = [arm_point(a, D_JUNC, 0.45), arm_point(a, D_JUNC + 0.55, 0.45),
           arm_point(a, D_JUNC + 0.55, 6.75), arm_point(a, D_JUNC, 6.75)]
    fill_poly(pts, C_WHITE, 5)

# ============================================================ 6. 双黄中心线
for a in ORDER:
    for s in (+1, -1):
        stroke([arm_point(a, D_MARK, s * YEL_OFF), arm_point(a, 400.0, s * YEL_OFF)],
               YEL_W, C_YEL, 6)

# ============================================================ 7. 车道分界线：近端实线 + 远端虚线
for a in ORDER:
    for s in (+1, -1):
        stroke([arm_point(a, D_MARK, s * 3.5), arm_point(a, D_SOLID, s * 3.5)],
               LANE_W, C_WHITE, 6)
        stroke([arm_point(a, D_SOLID, s * 3.5), arm_point(a, 400.0, s * 3.5)],
               LANE_W, C_WHITE, 6, dashes=(2.0, 2.0))

# ============================================================ 8. 导向箭头（进口道：内侧左转 / 外侧右转）
LANE_IN  = 1.75     # 内侧进口道中心（靠中心线一侧 → 左转）
LANE_OUT = 5.25     # 外侧进口道中心（靠路缘一侧 → 右转）


def lane_arrow(a, off, turn, t0=D_ARROW, z=7, shaft=2.6, bend=1.00,
               w=0.20, head_l=1.25, head_hw=0.62):
    """turn=+1 向行驶方向左侧弯（左转）；turn=-1 向右弯（右转）。"""
    P0 = arm_point(a, t0, off)                 # 箭尾（远离路口）
    d = -a.u                                   # 行驶方向：驶向路口
    lv = np.array([-d[1], d[0]])               # 行驶方向的左侧
    P1 = P0 + d * shaft                        # 直杆末端
    P2 = P1 + d * 0.95 + lv * turn * bend      # 弯折末端
    ctrl = P1 + d * 0.15
    ts = np.linspace(0.0, 1.0, 48)[:, None]
    curve = (1 - ts) ** 2 * P1 + 2 * (1 - ts) * ts * ctrl + ts ** 2 * P2
    pts = np.vstack([[P0], curve])
    tg = P2 - ctrl
    tg = tg / np.linalg.norm(tg)
    nr = np.gradient(pts, axis=0)
    nr = nr / np.linalg.norm(nr, axis=1, keepdims=True)
    nr = np.column_stack([-nr[:, 1], nr[:, 0]])
    fill_poly(np.vstack([pts + w * nr, (pts - w * nr)[::-1]]), C_WHITE, z)
    tip = P2 + tg * head_l
    pn = np.array([-tg[1], tg[0]])
    fill_poly([tip, P2 + pn * head_hw - tg * 0.15, P2 - pn * head_hw - tg * 0.15],
              C_WHITE, z)


for a in ORDER:
    lane_arrow(a, LANE_IN, +1.0)    # 内侧进口道：左转（朝中心线一侧弯）
    lane_arrow(a, LANE_OUT, -1.0)   # 外侧进口道：右转（朝路缘一侧弯）

# ============================================================ 9. 夹角标注
aa = np.radians(np.linspace(-90.0, -45.0, 60))
arc = 15.0 * np.column_stack([np.cos(aa), np.sin(aa)])
stroke(arc, 0.16, C_GRAY, 8, dashes=(1.6, 1.2), cap="butt")
stroke([arm_point(ARM_S, 16.6), arm_point(ARM_S, 19.0)], 0.16, C_GRAY, 8, cap="butt")
stroke([arm_point(ARM_B, 16.6), arm_point(ARM_B, 19.0)], 0.16, C_GRAY, 8, cap="butt")
for d_ in (-90.0, -45.0):
    u = unit(d_)
    stroke([15.0 * u, 17.0 * u], 0.16, C_GRAY, 8, cap="butt")
ax.text(17.2 * np.cos(np.radians(-67.5)), 17.2 * np.sin(np.radians(-67.5)), "45°",
        fontsize=9.5, color=C_GRAY, ha="center", va="center", zorder=9)

# 主线路幅尺寸线（画在路面上，标注移到路侧草地，避免压在沥青上）
ym = -30.0
stroke([[-H_PAV, ym], [H_PAV, ym]], 0.14, C_GRAY, 8, cap="butt")
for x in (-H_PAV, H_PAV):
    stroke([[x, ym - 1.2], [x, ym + 1.2]], 0.14, C_GRAY, 8, cap="butt")
ax.text(-9.4, ym + 1.1, "路幅 15.0 m", fontsize=9.5, color=C_GRAY,
        ha="right", va="center", zorder=9)
ax.text(-9.4, ym - 2.0, "双向四车道 4×3.5 m", fontsize=8.5, color=C_GRAY,
        ha="right", va="center", zorder=9)

# 三条腿的名称
ax.text(*arm_point(ARM_S, 37.0), "主线", fontsize=11, color=C_TXT, ha="center",
        va="top", zorder=9)
ax.text(*arm_point(ARM_A, 35.0, 9.5), "支线一", fontsize=11, color=C_TXT,
        ha="center", va="center", zorder=9)
ax.text(*arm_point(ARM_B, 35.0, 9.5), "支线二", fontsize=11, color=C_TXT,
        ha="center", va="center", zorder=9)

# ============================================================ 10. 指北针
nx, ny = 30.0, -26.0
fill_poly([[nx, ny + 7.2], [nx - 1.1, ny], [nx, ny + 1.4]], C_TXT, 9)
fill_poly([[nx, ny + 7.2], [nx + 1.1, ny], [nx, ny + 1.4]], C_WHITE, 9)
stroke([[nx, ny], [nx, ny - 3.2]], 0.18, C_TXT, 9, cap="butt")
ax.text(nx, ny + 8.6, "N", fontsize=11, color=C_TXT, ha="center", va="bottom",
        fontweight="bold", zorder=9)

# ============================================================ 11. 比例尺
bx, by = -33.0, -38.5
for k in range(2):
    fill_poly([[bx + k * 10.0, by], [bx + (k + 1) * 10.0, by],
               [bx + (k + 1) * 10.0, by + 1.3], [bx + k * 10.0, by + 1.3]],
              C_TXT if k % 2 == 0 else C_WHITE, 9)
ax.add_patch(Rectangle((bx, by), 20.0, 1.3, facecolor="none", edgecolor=C_TXT,
                       linewidth=0.9, zorder=9.5))
for k in range(3):
    ax.text(bx + k * 10.0, by - 1.1, str(k * 10), fontsize=8.5, color=C_GRAY,
            ha="center", va="top", zorder=9)
ax.text(bx + 21.5, by + 0.65, "m", fontsize=8.5, color=C_GRAY, ha="left",
        va="center", zorder=9)

# ============================================================ 12. 图名
ax.text(0.0, 42.5, "Y 型交叉口 · 路网平面示意", fontsize=16, color=C_TXT,
        ha="center", va="bottom", fontweight="bold", zorder=9)
ax.text(0.0, 38.6, "三路交汇 · 两臂与主线各夹 45° · 缘石转弯半径 5.0 m",
        fontsize=9.5, color=C_GRAY, ha="center", va="bottom", zorder=9)

# ----------------------------------------------------------------- 导出
png = os.path.join(OUT_DIR, "y_junction.png")
svg = os.path.join(OUT_DIR, "y_junction.svg")
fig.savefig(png, dpi=300, facecolor="white")
plt.rcParams["svg.fonttype"] = "path"
fig.savefig(svg, facecolor="white")
print("saved:", png)
print("saved:", svg)
print("pt/m = %.3f  fig = %.3f x %.3f in" % (PT_PER_M, FIG_W, FIG_H))
