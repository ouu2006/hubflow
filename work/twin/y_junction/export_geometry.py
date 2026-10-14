# -*- coding: utf-8 -*-
"""
导出 Y 型单行道路网几何为 JSON（对齐站点包 PackSegment 契约）。

口径（业主 2026-10-14）：
  · 单行道：车辆自下方主线驶入，经汇流口后向左/右两条支线分流出去；
  · 真正的「路」：不是一根细线——每条走廊按**车道双线**建模，
    主线 2 条车道（左/右），左右支线各 1 条车道；车道即前端渲染的路段 polyline；
  · 车道线 = 中心线沿法向偏移，分流段用车道弧线圆滑转弯（二次贝塞尔），
    车道之间只在汇流口前共享、分流后各走各的，不互相重叠；
  · 坐标为局部平面坐标（米），原点 = 汇流口中心，不做地理配准。

布局（坐标 y 向上，x 向右）：
                 A2                 B2
                ／                     ＼
             A1(左车道)             B1(右车道)
                ＼    ↖ 分流口 ↗    ／
                 S2 —— S1 —— 主线入口(南)
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "y_junction_geometry.json"

# ---- 几何参数（米）----
LANE_OFF = 4.0        # 车道中心线相对走廊中心线的横向偏移（半幅）
MAIN_BOT = -300.0     # 主线南端（入口）
MAIN_MID = -140.0     # 主线近岔段 / 分流段分界
JUNC = (0.0, 0.0)     # 汇流口中心

# 支线走廊：贝塞尔（起点=汇流口，控制点决定出射角，终点=远端）
BR_CTRL_L = (-45.0, 130.0)
BR_END_L = (-240.0, 230.0)
BR_CTRL_R = (45.0, 130.0)
BR_END_R = (240.0, 230.0)

N_LINE = 64  # 每条曲线采样点数


def bez(p0, p1, p2, n=N_LINE):
    """二次贝塞尔采样。"""
    return [
        (
            (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
            (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1],
        )
        for t in (i / (n - 1) for i in range(n))
    ]


def lin(p0, p1, n):
    return [
        (p0[0] + (p1[0] - p0[0]) * i / (n - 1), p0[1] + (p1[1] - p0[1]) * i / (n - 1))
        for i in range(n)
    ]


def offset_line(pts, off):
    """折线沿左法向（行进方向左侧）偏移 off。"""
    n = len(pts)
    out = []
    for i, (x, y) in enumerate(pts):
        if i == 0:
            dx, dy = pts[1][0] - x, pts[1][1] - y
        elif i == n - 1:
            dx, dy = x - pts[i - 1][0], y - pts[i - 1][1]
        else:
            dx, dy = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        L = math.hypot(dx, dy) or 1.0
        # 左法向 = (-dy, dx) / L
        out.append((x - dy / L * off, y + dx / L * off))
    return out


def make_segment(seg_id, name, pts):
    return {
        "segment_id": seg_id,
        "name": name,
        "kind": "main",
        "coords": [[round(x, 2), round(y, 2)] for x, y in pts],
    }


segments = []

# ---- 主线走廊：中心线从南端到汇流口 ----
# 路段划分（业主 2026-10-14 五版口径，共 3 条；站前服务段已裁掉、
# 左右支线各合并为整条走廊一段）：
#   ① 主线整条 = 1 条路段（黑框：从南端入口到汇流口）
#   ② 左支线整条 = 1 条路段（汇流口→远端）
#   ③ 右支线整条 = 1 条路段
# 每条走廊双向合并画，「分左回右去」的语义由断面/指标承载，几何上不拆车道。
main_center = lin((0.0, MAIN_BOT), JUNC, N_LINE)

# ① 主线整条 = 1 条路段
segments.append(make_segment("SEG-01", "主线（南入口→汇流口）", main_center))

# ② 左支线整条
segments.append(make_segment("SEG-02", "左支线（汇流口→远端）", bez(JUNC, BR_CTRL_L, BR_END_L)))

# ③ 右支线整条
segments.append(make_segment("SEG-03", "右支线（汇流口→远端）", bez(JUNC, BR_CTRL_R, BR_END_R)))

# ---- 输出 ----
data = {
    "description": (
        "Y 型单行道演示路网（业主 2026-10-14 五版：3 路段口径——"
        "①主线整条 1 条(南入口→汇流口)；②左支线整条 1 条；③右支线整条 1 条；"
        "站前服务段已裁掉、左右支线不再分段；每条走廊双向合并画，"
        "「分左回右去」的语义由断面与指标承载，几何上不拆车道）；"
        "坐标为局部平面坐标(米)，原点=汇流口，非任何真实地点。"
        "生成脚本：work/twin/y_junction/export_geometry.py（勿手改产物）。"
    ),
    "segments": segments,
}
OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("saved:", OUT)
for s in segments:
    print(s["segment_id"], s["name"], len(s["coords"]), "pts")
