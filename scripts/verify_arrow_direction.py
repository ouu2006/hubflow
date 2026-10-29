#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""路段箭头标向验收工具（L2 数值快照 + L3 人眼图纸）。

对应方案：docs/方案-路段箭头方向-20261029.md 第 4 节「三层确认箭头标向」。

本脚本只做两件事，纯标准库、不依赖后端接口改造进度：

  L2  work/verify/direction_snapshot.json
      逐段 {from, to, direction, length_m, bearing_coords_order, bearing_travel}
      （另附 travel_from/travel_to/中点坐标等便于人工核对与 diff 的字段）。
      固定小数位 + 键排序 + 无时间戳 → 方向一旦被改错，git diff 立刻现形。

  L3  work/verify/direction_sheet.svg
      北向上、带指北针与各面板比例尺的图版：每个抽样段并排画
        灰线 = coords 顺序（文件里的几何顺序）
        彩色线 = 行进顺序（direction=reverse 时把几何反向）
      沿线画箭头、锥尖朝 to_node（行进终点），端点标注 from/to 节点名。

用法：
  python scripts/verify_arrow_direction.py                 # 生成快照 + 图纸
  python scripts/verify_arrow_direction.py --check         # L2 判定：与仓库快照逐字节比对
  python scripts/verify_arrow_direction.py --all           # 图纸覆盖全部 61 段（默认只覆盖反向段 + 5 条双向段）
  python scripts/verify_arrow_direction.py --list          # 只打印抽样清单与自检统计

退出码：0 = 全部自检通过；1 = 有断言失败（逐条打印段 id）；2 = 入参/来源文件问题。
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import sys

# ---------------------------------------------------------------- 常量与口径

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NETPACK_ENRICHED = os.path.join(ROOT, "work", "twin", "netpack", "network_junction.enriched.json")
NETPACK_RAW = os.path.join(ROOT, "work", "twin", "netpack", "network_junction.json")
OUT_SNAPSHOT = os.path.join(ROOT, "work", "verify", "direction_snapshot.json")
OUT_SHEET = os.path.join(ROOT, "work", "verify", "direction_sheet.svg")

R_EARTH = 6371008.8
DIRECTIONS = ("forward", "reverse", "bidirectional")

# 方案 §1.1 的容差：geometry 首末点必须等于 from/to 节点坐标
ENDPOINT_TOL_DEG = 1e-6
# 段长自算与文件声明值允许的最大差（米）：真网段长由 OSM 大圆累加而来
LENGTH_TOL_M = 0.5
# 端点相等 / 段长一致之外还要检查的浮点小数位（保证快照可 diff）
ND_BEARING = 1
ND_LEN = 1
ND_LONLAT = 7


# ------------------------------------------------------------------ 几何基础

def haversine_m(a, b):
    """两个 (lon, lat) 之间的大圆距离（米）。"""
    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    h = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    return 2.0 * R_EARTH * math.asin(min(1.0, math.sqrt(h)))


def initial_bearing_deg(a, b):
    """a → b 的初始方位角（度，正北 0，顺时针 0..360）。"""
    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def bearing_delta(a, b):
    """两个方位角的最短夹角（度，0..180）。"""
    d = abs((a - b) % 360.0)
    return min(d, 360.0 - d)


class Polyline(object):
    """按弧长定位的折线，用来取「50% 弧长点」与「局部切线方位角」。"""

    def __init__(self, pts):
        self.pts = [tuple(p) for p in pts]
        self.cum = [0.0]
        for i in range(1, len(self.pts)):
            self.cum.append(self.cum[-1] + haversine_m(self.pts[i - 1], self.pts[i]))
        self.total = self.cum[-1]

    def point_at(self, s):
        """弧长 s（米）处的点。"""
        if self.total <= 0:
            return self.pts[0]
        s = max(0.0, min(self.total, s))
        # 二分定位所在边
        lo, hi = 0, len(self.cum) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if self.cum[mid] <= s:
                lo = mid
            else:
                hi = mid
        a, b = self.pts[lo], self.pts[lo + 1]
        seg = self.cum[lo + 1] - self.cum[lo]
        t = 0.0 if seg <= 0 else (s - self.cum[lo]) / seg
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    def tangent_at(self, s, window_m):
        """弧长 s 处、取前后 window 米内的局部切线方位角（方案 §3.2 的口径）。"""
        w = max(0.5, window_m)
        p1 = self.point_at(max(0.0, s - w))
        p2 = self.point_at(min(self.total, s + w))
        if haversine_m(p1, p2) < 1e-6:  # 极短段兜底：用整段首末点
            p1, p2 = self.pts[0], self.pts[-1]
        return initial_bearing_deg(p1, p2)

    def window_m(self):
        """方案 §3.2：N = min(15 m, 1/4 段长)。"""
        return min(15.0, self.total / 4.0)


def travel_pts(coords, direction):
    """行进顺序几何：reverse 时把 coords 反序。bidirectional 按 coords 顺序（正向那支）。"""
    if direction == "reverse":
        return list(reversed(coords))
    return list(coords)


# --------------------------------------------------------------- 数据装载

def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_netpack(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def pick_source():
    """优先 enriched（唯一带 direction 字段的产物），退回 raw。"""
    if os.path.isfile(NETPACK_ENRICHED):
        d = load_netpack(NETPACK_ENRICHED)
        if all("direction" in e for e in d.get("edges", [])):
            return NETPACK_ENRICHED, d
    if os.path.isfile(NETPACK_RAW):
        d = load_netpack(NETPACK_RAW)
        # raw 没有 direction：用 oneway 推（"-1" = 与 coords 顺序相反）
        for e in d.get("edges", []):
            ow = e.get("oneway")
            e["direction"] = "reverse" if ow == "-1" else ("bidirectional" if ow in (None, "no") else "forward")
        return NETPACK_RAW, d
    raise SystemExit("找不到 netpack 来源文件：%s / %s" % (NETPACK_ENRICHED, NETPACK_RAW))


# --------------------------------------------------------------- L2 快照构建

def build_snapshot(pack, source_path):
    nodes = {n["node_id"]: n for n in pack["nodes"]}
    edges = pack["edges"]

    segments = {}
    problems = []
    stats = collections.Counter()

    for e in sorted(edges, key=lambda x: x["segment_id"]):
        sid = e["segment_id"]
        coords = e["coords"]
        frm, to = e["from"], e["to"]
        direction = e["direction"]
        stats[direction] += 1

        if direction not in DIRECTIONS:
            problems.append("%s: 非法 direction=%r" % (sid, direction))
            continue
        if frm not in nodes or to not in nodes:
            problems.append("%s: 端点节点不在 nodes 表里（from=%s to=%s）" % (sid, frm, to))
            continue

        nf = (nodes[frm]["lon"], nodes[frm]["lat"])
        nt = (nodes[to]["lon"], nodes[to]["lat"])

        # 断言 1：coords 的顺序 == 文件里的 from → to（真网产物应当全部成立）
        head_ok = max(abs(coords[0][0] - nf[0]), abs(coords[0][1] - nf[1])) <= ENDPOINT_TOL_DEG
        tail_ok = max(abs(coords[-1][0] - nt[0]), abs(coords[-1][1] - nt[1])) <= ENDPOINT_TOL_DEG
        if not (head_ok and tail_ok):
            rev_ok = (max(abs(coords[0][0] - nt[0]), abs(coords[0][1] - nt[1])) <= ENDPOINT_TOL_DEG
                      and max(abs(coords[-1][0] - nf[0]), abs(coords[-1][1] - nf[1])) <= ENDPOINT_TOL_DEG)
            problems.append(
                "%s: coords 首末点与 from/to 节点坐标不符（head_ok=%s tail_ok=%s 反向才成立=%s）"
                % (sid, head_ok, tail_ok, rev_ok))

        cp = Polyline(coords)
        tp = Polyline(travel_pts(coords, direction))
        t_from = to if direction == "reverse" else frm
        t_to = frm if direction == "reverse" else to

        # 断言 2：段长自算值与文件声明值一致（reverse 段同值，方案 §4 L1 的一条）
        len_calc = cp.total
        len_claim = float(e["length_m"])
        if abs(len_calc - len_claim) > max(LENGTH_TOL_M, len_claim * 0.01):
            problems.append("%s: 段长不符（声明 %.1f m / 自算 %.1f m）" % (sid, len_claim, len_calc))

        mid_c = cp.point_at(cp.total / 2.0)
        mid_t = tp.point_at(tp.total / 2.0)
        bc = cp.tangent_at(cp.total / 2.0, cp.window_m())
        bt = tp.tangent_at(tp.total / 2.0, tp.window_m())

        # 断言 3：行进方位角必须是 coords 序方位角（straight）或它的反向（reverse）
        expect = (bc + 180.0) % 360.0 if direction == "reverse" else bc
        if direction in ("forward", "reverse") and bearing_delta(bt, expect) > 1.0:
            problems.append("%s: 中点行进方位角 %.1f° 与 coords 序方位角 %.1f° 不符（期望 %.1f°）"
                            % (sid, bt, bc, expect))

        segments[sid] = {
            "from": frm,
            "to": to,
            "travel_from": t_from,
            "travel_to": t_to,
            "direction": direction,
            "oneway": e.get("oneway"),
            "kind": e.get("kind"),
            "boundary": e.get("boundary"),
            "length_m": round(len_claim, ND_LEN),
            "length_m_calc": round(len_calc, ND_LEN),
            # 中点（50% 弧长）处的局部切线方位角，口径见 _meta.definitions
            "bearing_coords_order": round(bc, ND_BEARING),
            "bearing_travel": round(bt, ND_BEARING),
            "midpoint_coords_order": [round(mid_c[0], ND_LONLAT), round(mid_c[1], ND_LONLAT)],
            "midpoint_travel": [round(mid_t[0], ND_LONLAT), round(mid_t[1], ND_LONLAT)],
        }

    # 反向段清单：真网 enriched 标了 14 条 —— 组成与口径见 _meta.reverse_count_note
    reverse_ids = sorted(k for k, v in segments.items() if v["direction"] == "reverse")
    bidi_ids = sorted(k for k, v in segments.items() if v["direction"] == "bidirectional")

    # 反向段里的「对向重合对」（opposite_segment_id 相互指认、几何重合）登记下来备查：
    # 适配层若把这一对合并成一条双向边，reverse 计数会少 1（14 → 13），故此处留档。
    by_id = {e["segment_id"]: e for e in edges}
    coincident_pairs = []
    seen = set()
    for sid in reverse_ids:
        opp = by_id[sid].get("opposite_segment_id")
        if opp and opp in by_id and sid not in seen and by_id[opp].get("opposite_segment_id") == sid:
            coincident_pairs.append([sid, opp])
            seen.update((sid, opp))

    # 反向段端点连通性：只用这 14 条 reverse 段构图，看端点是否连成一整片（可复现的客观事实，
    # 用来支撑「不是散布的孤例」这个结论，而不是口头断言）
    adj = collections.defaultdict(set)
    for sid in reverse_ids:
        e = by_id[sid]
        a, b = e.get("from"), e.get("to")
        if a is None or b is None:
            continue
        adj[a].add(b)
        adj[b].add(a)
    comps, seen_nodes = [], set()
    for n in sorted(adj):
        if n in seen_nodes:
            continue
        stack, comp = [n], []
        seen_nodes.add(n)
        while stack:
            x = stack.pop()
            comp.append(x)
            for y in adj[x]:
                if y not in seen_nodes:
                    seen_nodes.add(y)
                    stack.append(y)
        comps.append(sorted(comp))
    comps.sort(key=lambda c: (-len(c), c))
    reverse_total_m = sum(by_id[s]["length_m"] for s in reverse_ids)
    net_total_m = sum(e["length_m"] for e in edges)
    # 编号连续性：反向段编号里最长的连续 SZ-0NN 段
    run, best = [], []
    prev = None
    for sid in reverse_ids:
        num = int(sid.split("-")[1]) if sid.split("-")[-1].isdigit() else None
        if prev is not None and num == prev + 1:
            run.append(sid)
        else:
            run = [sid]
        prev = num
        if len(run) > len(best):
            best = list(run)
    reverse_note = (
        "enriched 产物里 direction=reverse 共 %d 条 = %s~%s 连续 %d 条 + %s（%s 不在其中，它是 forward）。"
        "这 %d 条的端点在「只由它们构成」的图上连成 %d 个连通分量（%d 个节点），"
        "即一整片对向单行路网、合计 %.1f m（占全站 %.1f m 的 %.1f%%）—— 不是散布的孤例；"
        "这正是业主「箭头很乱」的由来：一整片道路的箭头同时朝反方向。方案 §1.1 已同步为 %d 条。"
        "备注：SZ-013 与 SZ-060（forward）几何重合、opposite_segment_id 相互指认，"
        "若适配层把这对合并成一条双向边，reverse 会记 %d 条；验收按 %d 条全量核对。"
        % (len(reverse_ids), best[0], best[-1], len(best),
           ", ".join(s for s in reverse_ids if s not in best) or "无",
           "SZ-014",
           len(reverse_ids), len(comps), sum(len(c) for c in comps),
           reverse_total_m, net_total_m, 100.0 * reverse_total_m / net_total_m,
           len(reverse_ids), max(0, len(reverse_ids) - len(coincident_pairs)), len(reverse_ids))
    ) if reverse_ids else "无 reverse 段"

    snapshot = {
        "_meta": {
            "purpose": "L2 数值快照：路段 → 行进标向。diff 为空即方向未被改错。",
            "generated_by": "scripts/verify_arrow_direction.py",
            "source": os.path.relpath(source_path, ROOT).replace("\\", "/"),
            "source_sha256": _sha256(source_path),
            "source_generated_by": pack.get("generated_by"),
            "crs": pack.get("crs"),
            "site": (pack.get("site") or {}).get("name") if isinstance(pack.get("site"), dict) else pack.get("site"),
            "segments": len(segments),
            "counts": dict(sorted(stats.items())),
            "reverse_segments": reverse_ids,
            "coincident_opposite_pairs": coincident_pairs,
            "reverse_subgraph": {
                "components": len(comps),
                "component_nodes": [len(c) for c in comps],
                "nodes": sorted(seen_nodes),
                "reverse_total_m": round(reverse_total_m, ND_LEN),
                "network_total_m": round(net_total_m, ND_LEN),
                "share_of_network": round(reverse_total_m / net_total_m, 4) if net_total_m else None,
                "longest_consecutive_block": best,
            },
            "reverse_count_note": reverse_note,
            "bidirectional_segments": bidi_ids,
            "definitions": {
                "from/to": "netpack 产物里的节点；coords[0] 恒等于 from 的坐标、coords[-1] 恒等于 to（脚本断言）",
                "travel_from/travel_to": "行进口径的端点：direction=reverse 时与 from/to 互换（适配层重建边用的就是这一口径）",
                "bearing_coords_order": "50% 弧长点处、沿 coords 顺序的局部切线方位角（度，正北 0 顺时针）；窗口 = min(15 m, 1/4 段长)",
                "bearing_travel": "同一 50% 弧长点处、沿行进顺序的局部切线方位角；reverse 段应等于 bearing_coords_order + 180°",
                "bidirectional": "行进方向不唯一，bearing_travel 按 coords 顺序那一支给出；路线里必须落到确定的 forward/reverse",
            },
            "tolerances": {
                "endpoint_deg": ENDPOINT_TOL_DEG,
                "length_m": LENGTH_TOL_M,
                "bearing_deg_selfcheck": 1.0,
                "decimals": {"bearing": ND_BEARING, "length": ND_LEN, "lonlat": ND_LONLAT},
            },
        },
        "segments": segments,
    }
    return snapshot, problems, reverse_ids, bidi_ids


# --------------------------------------------------------------- L3 SVG 图纸

SVG_W = 1280
PANEL_W = 404
PANEL_H = 266
PANEL_GAP = 18
COLS = 3
MARGIN = 18
HEADER_H = 214          # 标题 + 图例 + 指北针区
SECTION_H = 50          # 章节标题带
CELL_PAD = 30           # 面板内几何留白（左右再各留 26px 给端点名）
LABEL_ROOM = 26
LINE_OFFSET_PX = 20     # 灰线与彩线的垂直并排间距（一半）
ARROW_COLOR = "#C62828"
GRAY = "#9AA0A6"
LABEL_FONT = 9.0
CHAR_W = 5.45           # 9px 等宽字体的近似字宽，用来夹取标签不出框

PALETTE = {
    "forward": "#1E6FD9",
    "reverse": "#C62828",
    "bidirectional": "#7B4FD0",
}


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def project_local(pts, lat0):
    """经纬度 → 局部平面（米，北向上）。x 向东、y 向北。"""
    kx = math.cos(math.radians(lat0)) * math.pi / 180.0 * R_EARTH
    ky = math.pi / 180.0 * R_EARTH
    return [((p[0] - pts[0][0]) * kx, (p[1] - pts[0][1]) * ky) for p in pts]


def nice_bar(max_m):
    """比例尺取整：1/2/5 × 10^n，且不超过面板可用宽度的 60%。"""
    if max_m <= 0:
        return 10.0
    for exp in range(-1, 5):
        for m in (1, 2, 5):
            v = m * (10 ** exp)
            if v >= max_m:
                return v
    return max_m


def make_panel(seg, x0, y0, w, h, label_w_origin):
    """画一个路段面板：灰线（coords 顺序）+ 彩线（行进顺序，带箭头）。"""
    coords = seg["coords"]
    direction = seg["direction"]
    tpts = travel_pts(coords, direction)

    lat0 = coords[0][1]
    loc_c = project_local(coords, lat0)
    # 行进线用同一套投影（同一起点），保证两条线形状可比
    kx = math.cos(math.radians(lat0)) * math.pi / 180.0 * R_EARTH
    ky = math.pi / 180.0 * R_EARTH
    loc_t = [((p[0] - coords[0][0]) * kx, (p[1] - coords[0][1]) * ky) for p in tpts]

    xs = [p[0] for p in loc_c] + [p[0] for p in loc_t]
    ys = [p[1] for p in loc_c] + [p[1] for p in loc_t]
    span_x = max(1e-6, max(xs) - min(xs))
    span_y = max(1e-6, max(ys) - min(ys))

    # 版面：上留标题 + 灰线标签，下留彩线标签 + 比例尺，左右各留标签位
    top_room = 48 + LINE_OFFSET_PX + 10
    bot_room = 40 + LINE_OFFSET_PX + 14
    avail_w = w - 2 * (CELL_PAD + LABEL_ROOM)
    avail_h = h - top_room - bot_room
    if span_y < 1e-9:                       # 纯东西向直线不能除零
        scale = min(avail_w / span_x, 8.0)
    else:
        scale = min(avail_w / span_x, avail_h / span_y)
    scale = max(0.15, min(scale, 8.0))      # 太短的段别放大到失真
    gw, gh = span_x * scale, span_y * scale

    def to_px(p, dy):
        ox = x0 + CELL_PAD + LABEL_ROOM + (avail_w - gw) / 2.0
        oy = y0 + top_room + (avail_h - gh) / 2.0
        return (ox + (p[0] - min(xs)) * scale,
                oy + gh - (p[1] - min(ys)) * scale + dy)

    out = []
    out.append('<g>')
    out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="6" fill="#FFFFFF" stroke="#D7DBE0"/>'
               % (x0, y0, w, h))

    # 标题行：段号 + direction + 段长 + 两个方位角
    title = "%s  %s  %.1f m" % (seg["segment_id"], direction, seg["length_m"])
    out.append('<text x="%.1f" y="%.1f" font-family="Consolas,Menlo,monospace" font-size="13" '
               'font-weight="700" fill="%s">%s</text>'
               % (x0 + 12, y0 + 20, PALETTE.get(direction, "#333333"), esc(title)))
    out.append('<text x="%.1f" y="%.1f" font-family="Consolas,Menlo,monospace" font-size="10.5" '
               'fill="#5B636B">coords 序 %s° · 行进 %s°</text>'
               % (x0 + 12, y0 + 34, ("%.1f" % seg["bearing_coords_order"]),
                  ("%.1f" % seg["bearing_travel"])))

    # 灰线：coords 顺序（向上错开）
    gray_pts = " ".join("%.1f,%.1f" % to_px(p, -LINE_OFFSET_PX) for p in loc_c)
    out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="3.2" '
               'stroke-linecap="round" stroke-linejoin="round"/>' % (gray_pts, GRAY))

    # 彩线：行进顺序（向下错开）
    col_pts = [to_px(p, LINE_OFFSET_PX) for p in loc_t]
    out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="3.2" '
               'stroke-linecap="round" stroke-linejoin="round"/>'
               % (" ".join("%.1f,%.1f" % p for p in col_pts), PALETTE.get(direction, "#333")))

    # 沿行进线画箭头：锥尖正好落在采样弧长点上，朝向该点局部切线
    tp = Polyline(tpts)
    win = tp.window_m()
    if direction == "bidirectional":
        stations = [(0.40, +1), (0.60, -1)]     # 两支：40% 正向 / 60% 反向
    else:
        stations = [(0.25, +1), (0.50, +1), (0.75, +1)]
    arrows = []
    for frac, sense in stations:
        s = tp.total * frac
        p = tp.point_at(s)
        brg = tp.tangent_at(s, win)
        if sense < 0:
            brg = (brg + 180.0) % 360.0
        # 用与折线同一投影换算（相对 coords[0]）
        px = to_px(((p[0] - coords[0][0]) * kx, (p[1] - coords[0][1]) * ky), LINE_OFFSET_PX)
        # 屏幕坐标：北向上 → 方位角 b 对应屏幕向量 (sin b, -cos b)
        rad = math.radians(brg)
        ux, uy = math.sin(rad), -math.cos(rad)
        L, HW, BL = 16.0, 5.6, 5.0
        tip = (px[0] + ux * L / 2.0, px[1] + uy * L / 2.0)
        back = (px[0] - ux * L / 2.0, px[1] - uy * L / 2.0)
        left = (back[0] - uy * HW, back[1] + ux * HW)
        right = (back[0] + uy * HW, back[1] - ux * HW)
        # 尾杆：从箭尾往后延一小段，让箭头「长在」线上
        tail = (back[0] - ux * BL, back[1] - uy * BL)
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="2.4"/>'
                   % (tail[0], tail[1], back[0], back[1], PALETTE.get(direction, "#333")))
        out.append('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s"/>'
                   % (tip[0], tip[1], left[0], left[1], right[0], right[1], ARROW_COLOR))
        arrows.append({"frac": frac, "bearing_deg": round(brg, 1), "sense": sense,
                       "tip_px": [round(tip[0], 2), round(tip[1], 2)], "s_m": round(s, 2)})

    # 端点标注：灰线两端 = from/to（文件口径）；彩线两端 = 行进起点 / 终点
    gstart = to_px(loc_c[0], -LINE_OFFSET_PX)
    gend = to_px(loc_c[-1], -LINE_OFFSET_PX)
    cstart = to_px(loc_t[0], LINE_OFFSET_PX)
    cend = to_px(loc_t[-1], LINE_OFFSET_PX)

    def put(x, y, text, color, weight="400", size=9.5, anchor="start"):
        """写标签，并按预计字宽把文字夹在面板内（不出框、不压边）。"""
        tw = len(text) * CHAR_W * (size / 9.0)
        if anchor == "start" and x + tw > x0 + w - 6:
            anchor = "end"
        elif anchor == "end" and x - tw < x0 + 6:
            anchor = "start"
        if anchor == "start":
            x = max(x0 + 6, min(x, x0 + w - 6 - tw))
        else:
            x = min(x0 + w - 6, max(x, x0 + 6 + tw))
        return ('<text x="%.1f" y="%.1f" font-family="Consolas,Menlo,monospace" font-size="%.1f" '
                'font-weight="%s" fill="%s" text-anchor="%s">%s</text>'
                % (x, y, size, weight, color, anchor, esc(text)))

    # 端点小圆点，把「标签 ↔ 线」绑起来
    out.append('<circle cx="%.1f" cy="%.1f" r="3.1" fill="%s"/>' % (gstart[0], gstart[1], GRAY))
    out.append('<circle cx="%.1f" cy="%.1f" r="3.1" fill="%s"/>' % (gend[0], gend[1], GRAY))
    out.append('<circle cx="%.1f" cy="%.1f" r="3.4" fill="%s"/>'
               % (cstart[0], cstart[1], PALETTE.get(direction, "#333")))
    out.append('<circle cx="%.1f" cy="%.1f" r="4.2" fill="none" stroke="%s" stroke-width="2.2"/>'
               % (cend[0], cend[1], ARROW_COLOR))

    # 灰线两端 = from/to（文件口径，标在灰线上方）；彩线两端 = 行进起点/终点（标在彩线下方）
    out.append(put(gstart[0], gstart[1] - 8, "from " + seg["from"], GRAY,
                   anchor="start" if gstart[0] <= x0 + w / 2 else "end"))
    out.append(put(gend[0], gend[1] - 8, "to " + seg["to"], GRAY,
                   anchor="start" if gend[0] <= x0 + w / 2 else "end"))
    out.append(put(cstart[0], cstart[1] + 15, "起点 " + seg["travel_from"],
                   PALETTE.get(direction, "#333"), "700",
                   anchor="start" if cstart[0] <= x0 + w / 2 else "end"))
    out.append(put(cend[0], cend[1] + 15, "终点 " + seg["travel_to"], ARROW_COLOR, "700",
                   anchor="start" if cend[0] <= x0 + w / 2 else "end"))

    # 面板内比例尺（每面板独立缩放，比例尺逐面板标注）
    bar_m = nice_bar(span_x / scale * 0.5 if scale > 0 else 50.0)
    bar_px = bar_m * scale
    bx, by = x0 + 12, y0 + h - 12
    out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#3B4249" stroke-width="2"/>'
               % (bx, by, bx + bar_px, by))
    out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#3B4249" stroke-width="2"/>'
               % (bx, by - 4, bx, by + 3))
    out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#3B4249" stroke-width="2"/>'
               % (bx + bar_px, by - 4, bx + bar_px, by + 3))
    out.append(put(bx + bar_px + 6, by + 4, ("%g m" % bar_m), "#3B4249", "400", 9.5))
    out.append(put(x0 + w - 12, by + 4, ("1 m = %.2f px" % scale), "#8A9099", "400", 9, anchor="end"))
    out.append('</g>')

    return "".join(out), arrows


def _disp_w(s, size):
    """近似显示宽度：CJK 算 1.0 em，其余算 0.55 em。用来把长句按像素宽度折行。"""
    return sum(size * (1.0 if ord(ch) > 0x2E80 else 0.55) for ch in s)


def wrap_to_width(text, max_px, size):
    """按像素宽度折行：CJK 逐字可断，ASCII 连续段（如 opposite_segment_id）整段不拆。"""
    tokens, cur = [], ""
    for ch in text:
        if ord(ch) > 0x2E80:            # CJK：自成一段，可断
            if cur:
                tokens.append(cur)
                cur = ""
            tokens.append(ch)
        else:
            cur += ch
            if ch == " ":               # 空格处也断开
                tokens.append(cur)
                cur = ""
    if cur:
        tokens.append(cur)

    lines, line = [], ""
    for tok in tokens:
        if not line and tok == " ":
            continue
        if line and _disp_w(line + tok, size) > max_px:
            lines.append(line.rstrip())
            line = "" if tok == " " else tok
        else:
            line += tok
    if line.strip():
        lines.append(line.rstrip())
    return lines or [""]


def compass(x, y, r=26):
    out = ['<g>']
    out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#F7F9FB" stroke="#98A2AC" stroke-width="1.4"/>'
               % (x, y, r))
    # 北：向上
    out.append('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="#C62828"/>'
               % (x, y - r + 3, x - 6.5, y + 4, x + 6.5, y + 4))
    out.append('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="#B9C2CB"/>'
               % (x, y + r - 3, x - 6.5, y + 4, x + 6.5, y + 4))
    out.append('<text x="%.1f" y="%.1f" font-family="Helvetica,Arial,sans-serif" font-size="12" '
               'font-weight="700" fill="#C62828" text-anchor="middle">N</text>' % (x, y - r - 5))
    out.append('</g>')
    return "".join(out)


def build_svg(snapshot, pack, source_rel, sheet_segments, reverse_ids, bidi_ids):
    edges = {e["segment_id"]: e for e in pack["edges"]}
    note = snapshot["_meta"]["reverse_count_note"]
    # 图例按像素宽度折行（CJK 按 1 em 计，保证不出框），页头高度随折行数自适应
    note_w = SVG_W - 2 * MARGIN - 90 - 40
    note_lines = wrap_to_width(note, note_w, 10.5)
    legend_h = 88 + 13 * len(note_lines)
    header_h = 92 + legend_h + 22

    # 章节分组：(标题, 段 id 列表)
    sections = []
    sections.append(("A · 全部 direction=reverse 段（%d 条，方案 §1.1 认定的错位来源，全量覆盖）" % len(reverse_ids),
                     reverse_ids))
    sample_bidi = bidi_ids[:5]
    sections.append(("B · 抽样 direction=bidirectional 段（%d 条 / 全站共 %d 条；图纸两支：40%% 正向、60%% 反向；UI 实际是一支双头箭头）"
                     % (len(sample_bidi), len(bidi_ids)), sample_bidi))
    rest = [s for s in sheet_segments if s not in set(reverse_ids) | set(sample_bidi)]
    if rest:
        sections.append(("C · 其余方向段补充覆盖（%d 条）" % len(rest), rest))

    rows_h = 0
    for _, ids in sections:
        nrow = (len(ids) + COLS - 1) // COLS
        rows_h += SECTION_H + nrow * (PANEL_H + PANEL_GAP)
    total_h = header_h + rows_h + 90

    out = []
    out.append('<?xml version="1.0" encoding="UTF-8"?>')
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
               'font-family="Helvetica,Arial,\'Noto Sans CJK SC\',sans-serif">'
               % (SVG_W, total_h, SVG_W, total_h))
    out.append('<rect width="100%" height="100%" fill="#FBFCFD"/>')

    # ---- 页头
    out.append('<text x="%d" y="34" font-size="21" font-weight="700" fill="#111827">'
               '路段箭头标向核对图纸（L3 · 北向上）</text>' % MARGIN)
    out.append('<text x="%d" y="56" font-size="12" fill="#4A5560">'
               'source: %s · site: %s · %d 段 · 反向 %d · 双向 %d'
               '</text>' % (MARGIN, esc(source_rel), esc(snapshot["_meta"]["site"]),
                            snapshot["_meta"]["segments"],
                            snapshot["_meta"]["counts"].get("reverse", 0),
                            snapshot["_meta"]["counts"].get("bidirectional", 0)))
    out.append('<text x="%d" y="74" font-size="11.5" fill="#6B7480">'
               '判定只看两件事：① 箭头锥尖朝 to_node（行进终点）；② 彩线与灰线在同一几何上的相对位置一致，'
               '差异只在「顺序」。</text>' % MARGIN)

    # 图例
    lx, ly = MARGIN, 92
    out.append('<rect x="%d" y="%d" width="%d" height="%d" rx="6" fill="#FFFFFF" stroke="#D7DBE0"/>'
               % (lx, ly, SVG_W - 2 * MARGIN - 90, legend_h))
    out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="3.2"/>'
               % (lx + 14, ly + 22, lx + 54, ly + 22, GRAY))
    out.append('<circle cx="%d" cy="%d" r="3.2" fill="%s"/>' % (lx + 20, ly + 22, GRAY))
    out.append('<circle cx="%d" cy="%d" r="3.2" fill="%s"/>' % (lx + 48, ly + 22, GRAY))
    out.append('<text x="%d" y="%d" font-size="11.5" fill="#3B4249">灰线 = coords 顺序（netpack 文件里的几何顺序，coords[0]→coords[-1]，两端标 from / to）</text>'
               % (lx + 62, ly + 26))
    out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#C62828" stroke-width="3.2"/>'
               % (lx + 14, ly + 46, lx + 50, ly + 46))
    out.append('<polygon points="%d,%d %d,%d %d,%d" fill="%s"/>'
               % (lx + 54, ly + 46, lx + 44, ly + 42, lx + 44, ly + 50, ARROW_COLOR))
    out.append('<text x="%d" y="%d" font-size="11.5" fill="#3B4249">'
               '彩线 = 行进顺序（reverse 段反向），箭头锥尖朝 to_node，两端标 起点 / 终点</text>'
               % (lx + 62, ly + 50))
    out.append('<text x="%d" y="%d" font-size="11" font-weight="700" fill="#8A4B00">'
               '双向段：本图纸画两支（40%% 正向 / 60%% 反向）只为看清两个方向；'
               '⚠ UI 实际渲染为一支双头箭头，落在 0.5 弧长点、零横向偏移 —— 验收以 UI 口径为准，别拿两支对图。</text>'
               % (lx + 14, ly + 72))
    for i, line in enumerate(note_lines):
        out.append('<text x="%d" y="%d" font-size="10.5" fill="#6B7480">%s</text>'
                   % (lx + 14, ly + 92 + 13 * i, esc(line)))
    out.append(compass(SVG_W - MARGIN - 46, ly + legend_h / 2.0, 26))

    # ---- 章节
    y = header_h
    all_arrows = {}
    for title, ids in sections:
        out.append('<text x="%d" y="%.1f" font-size="13.5" font-weight="700" fill="#111827">%s</text>'
                   % (MARGIN, y + 22, esc(title)))
        out.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#D7DBE0" stroke-width="1.2"/>'
                   % (MARGIN, y + 30, SVG_W - MARGIN, y + 30))
        y += SECTION_H
        for i, sid in enumerate(ids):
            seg = dict(snapshot["segments"][sid])
            seg["segment_id"] = sid
            seg["coords"] = edges[sid]["coords"]
            col = i % COLS
            row = i // COLS
            px = MARGIN + col * (PANEL_W + PANEL_GAP)
            py = y + row * (PANEL_H + PANEL_GAP)
            panel, arrows = make_panel(seg, px, py, PANEL_W, PANEL_H, MARGIN)
            all_arrows[sid] = arrows
            out.append(panel)
        y += ((len(ids) + COLS - 1) // COLS) * (PANEL_H + PANEL_GAP)

    out.append('<text x="%d" y="%.1f" font-size="10.5" fill="#6B7480">'
               '由 scripts/verify_arrow_direction.py 生成 · 不手改 · 每面板独立缩放（比例尺见面板左下角）'
               '</text>' % (MARGIN, y + 26))
    out.append('</svg>')
    return "".join(out), all_arrows


# ------------------------------------------------------------------ 自检输出

def verify_sheet_arrows(snapshot, pack, arrows_by_seg, problems):
    """图纸自检：锥尖必须落在行进口径的采样弧长点上，朝向必须等于该点局部切线。"""
    edges = {e["segment_id"]: e for e in pack["edges"]}
    for sid, arrows in sorted(arrows_by_seg.items()):
        seg = snapshot["segments"][sid]
        tpts = travel_pts(edges[sid]["coords"], seg["direction"])
        tp = Polyline(tpts)
        win = tp.window_m()
        if seg["travel_from"] != (seg["to"] if seg["direction"] == "reverse" else seg["from"]):
            problems.append("%s: travel_from 口径算错（%s）" % (sid, seg["travel_from"]))
        for a in arrows:
            s = tp.total * a["frac"]
            if abs(s - a["s_m"]) > 0.011:   # 弧长在图纸里保留 2 位小数（0.01 m）
                problems.append("%s: 箭头弧长 %.3f 与采样点 %.3f 不符" % (sid, a["s_m"], s))
            brg = tp.tangent_at(s, win)
            if a["sense"] < 0:
                brg = (brg + 180.0) % 360.0
            if bearing_delta(brg, a["bearing_deg"]) > 0.15:
                problems.append("%s: 箭头朝向 %.2f° 与局部切线 %.2f° 不符" % (sid, a["bearing_deg"], brg))
        # 锥尖必须朝行进终点：非双向段所有箭头都在「朝 to_node」那半边
        if seg["direction"] != "bidirectional":
            for a in arrows:
                if not (0.0 < a["frac"] < 1.0):
                    problems.append("%s: 箭头采样点越界" % sid)
    return problems


def dump_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(description="路段箭头标向验收：L2 数值快照 + L3 图纸")
    ap.add_argument("--check", action="store_true", help="L2 判定：重新生成并与仓库快照逐字节比对")
    ap.add_argument("--all", action="store_true", help="图纸覆盖全部路段（默认覆盖全部反向段 + 5 条双向段）")
    ap.add_argument("--list", action="store_true", help="只打印抽样清单与自检统计")
    ap.add_argument("--no-sheet", action="store_true", help="只生成快照")
    args = ap.parse_args(argv)

    source_path, pack = pick_source()
    source_rel = os.path.relpath(source_path, ROOT).replace("\\", "/")
    snapshot, problems, reverse_ids, bidi_ids = build_snapshot(pack, source_path)

    if args.list:
        print("source: %s" % source_rel)
        print("segments: %d  counts: %s" % (snapshot["_meta"]["segments"], snapshot["_meta"]["counts"]))
        print("reverse (%d): %s" % (len(reverse_ids), ", ".join(reverse_ids)))
        print("coincident opposite pairs: %s" % snapshot["_meta"]["coincident_opposite_pairs"])
        print("bidirectional (%d): %s" % (len(bidi_ids), ", ".join(bidi_ids)))
        print(snapshot["_meta"]["reverse_count_note"])
        return 0 if not problems else 1

    # L2：快照
    text = dump_json(OUT_SNAPSHOT, snapshot)
    if args.check:
        if not os.path.isfile(OUT_SNAPSHOT):
            print("✗ 快照不存在：%s" % OUT_SNAPSHOT)
            return 2
        old = open(OUT_SNAPSHOT, "r", encoding="utf-8").read()
        if old.strip() == text.strip():
            print("✅ L2 快照 diff 为空（%d 段，%s）" % (snapshot["_meta"]["segments"], source_rel))
            return 0 if not problems else 1
        # 逐段找差异，方便定位
        try:
            oldj = json.loads(old).get("segments", {})
        except Exception:
            print("✗ 仓库快照无法解析")
            return 2
        newj = snapshot["segments"]
        print("✗ L2 快照与仓库不一致，差异段：")
        for sid in sorted(set(oldj) | set(newj)):
            if oldj.get(sid) != newj.get(sid):
                print("  - %s: 旧=%s" % (sid, json.dumps(oldj.get(sid), ensure_ascii=False)[:220]))
                print("         新=%s" % json.dumps(newj.get(sid), ensure_ascii=False)[:220])
        return 1

    # L3：图纸
    if not args.no_sheet:
        if args.all:
            sheet_segments = sorted(snapshot["segments"])
        else:
            sheet_segments = list(reverse_ids) + bidi_ids[:5]
        svg, arrows = build_svg(snapshot, pack, source_rel, sheet_segments, reverse_ids, bidi_ids)
        problems = verify_sheet_arrows(snapshot, pack, arrows, problems)
        os.makedirs(os.path.dirname(OUT_SHEET), exist_ok=True)
        with open(OUT_SHEET, "w", encoding="utf-8", newline="\n") as f:
            f.write(svg)
        print("L3 图纸：%s（%d 面板）" % (os.path.relpath(OUT_SHEET, ROOT).replace("\\", "/"), len(arrows)))

    print("L2 快照：%s（%d 段）" % (os.path.relpath(OUT_SNAPSHOT, ROOT).replace("\\", "/"),
                                  snapshot["_meta"]["segments"]))
    if problems:
        print("✗ 自检失败 %d 条：" % len(problems))
        for p in problems:
            print("  - %s" % p)
        return 1
    print("✅ 自检全绿：端点/段长/方位角/箭头锥尖与朝向 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
