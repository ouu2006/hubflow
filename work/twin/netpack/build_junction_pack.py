#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""站点 OSM 切片 → **先获取路线 → 再分段 → 再打标签**（含拓扑）。

## 三步，顺序不能反（业主 2026-10-17 口径）

> 「先获取路线，路线获取好后再进行分段，分段打标签；
>   路线都获取不好，所以分段也是错的。」

### 第 1 步 · 获取路线（road）
- 只留车行 way（步行 / 自行车 / 铁路 / 施工 不进路网）；
- 按路名归并（有名用 
ame`；无名按 `service`；再退 `highway`）→ **沿共享 OSM 节点串成整条路**；
- 端点相距 ≤ `--snap-m` 的两片接起来（路口两侧各一条 way 的情况）；
- **这一步的折线顶点全部是 OSM 原始节点坐标，一个都不改。**

### 第 2 步 · 分段（segment）
- 找出**路口点**：同一个坐标（误差 ≤ `--junction-tol-m`）同时落在**两条以上不同路线**上；
- 在路线**自身的这些顶点**处切开 —— **切点是原始顶点，不插值、不移动任何点**；
- 结果：每段两端就是路口，`from` / `to` 直接得到（**拓扑是副产品**）。

### 第 3 步 · 打标签
- 段名 = 路名；**同名路段超过一条时**才加 `（起路口→止路口）` 后缀（避免一条路几十段全带长后缀）；**没有真实路名就沿用通用译名，绝不编造**；
- `kind` = main / ramp；`way_ids` = 这一段实际覆盖的 OSM way（按点溯源）；
- `lanes` / `oneway` 从 OSM tag 抽（抽不到即 
ull`）；
- `speed_limit` / `capacity_vph` / `t0` **一律 null**（等 T2 路段属性核对表补）。

## 为什么必须"先路线、再分段"（踩过的坑，别重犯）

第一版跳过了"路线"这一步，直接对 way 做**节点吸附**再切段：吸附会把端点坐标**替换**成另一个点，
折线被拉扯变形 —— 停车场里 16~19 m 的车位排被横着连起来，屏幕上出现**横穿车位排的斜线**。
现在的口径是「串成整条路（顶点不动）→ 只在真实路口切」，几何零改动。

产物里带 `fidelity` 自检：**每个输出顶点都必须能在 OSM 原始节点坐标集合里找到**。

## 用法（仓库根）

    # 默认读 work/twin/site-ranges.json（每站一份：范围 / 拉取 bbox / 段数目标 / 切片与产物路径）
    python work/twin/netpack/build_junction_pack.py --site-id zhaoqingdong

    # 只比对：重跑一遍与既有产物**逐字节**比对（不写盘，不一致非 0 退出）
    python work/twin/netpack/build_junction_pack.py --site-id zhaoqingdong --check

    # 给新站做「候选范围」：只打印候选、不自动写配置（人工确认后往 site-ranges.json 加一条记录）
    python work/twin/netpack/build_junction_pack.py \
        --osm <切片> --site <站名> --out-json <产物> \
        --anchor-lonlat <lon,lat> --auto-range

    # 可覆盖项：--snap-m / --seg-prefix / --min-coverage-pct / --out-ts（空串=不输出）/ --no-merge-coincident

## 硬口径

- 脚本里**不出现任何站点名与坐标**（手册 §8.4：换站只改配置）；
- 范围 / 段数目标一律读 `work/twin/site-ranges.json`（IKM4B4 登记表），**不在代码里写死**；
- 产物只由脚本生成、**不许手改**；
- **不编造数据**：抽不到的属性就是 `null`；
- 几何取自 OSM（真值）；`is_simulated: true`，属性一期为演示占位。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

#: 站点范围登记表读取器在 work/twin/site_config.py（换站只改 JSON，脚本零改动）
_TWIN_DIR = Path(__file__).resolve().parent.parent
if str(_TWIN_DIR) not in sys.path:
    sys.path.insert(0, str(_TWIN_DIR))
from site_config import DEFAULT_CONFIG_PATH, load_site, repo_path  # noqa: E402

RAD = math.pi / 180
R = 6371000.0

# Windows 控制台默认 GBK：中文可编码，但 ✅/❌ 会抛 UnicodeEncodeError；统一 UTF-8 输出。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 —— 老 Python / 被重定向时忽略
    pass

#: 路线阶段：端点相距多近算"同一路口的两侧"（米，只用于把两片路接起来，**不移动顶点**）
DEFAULT_SNAP_M = 30.0
#: 分段阶段：两个顶点坐标差多近算"同一个路口点"（米）
DEFAULT_JUNCTION_TOL_M = 2.0
#: 不足这么长的段丢弃
DEFAULT_MIN_SEG_M = 20.0
#: 段号前缀
DEFAULT_SEG_PREFIX = "SZ"

#: 车行主干类（决定 kind = main / ramp）
MAIN_HIGHWAYS = ("primary", "secondary", "tertiary", "residential", "unclassified")
#: 不进路网的 highway 类型
SKIP_HIGHWAYS = (
    "footway", "path", "cycleway", "steps", "pedestrian", "track",
    "construction", "proposed", "bridleway", "corridor", "platform",
)
#: 无名路段的通用译名（按 OSM 标签翻译；**通用译名，与站点无关**）
LABEL_ZH = {
    "service:parking_aisle": "停车场内部通道",
    "service:driveway": "场区出入道",
    "service": "服务道路",
    "primary_link": "连接匝道",
    "secondary_link": "连接匝道",
    "tertiary_link": "连接匝道",
    "primary": "主干道",
    "secondary": "次干道",
    "tertiary": "支路",
    "residential": "生活性道路",
    "unclassified": "未分级道路",
}
GENERIC_NAMES = set(LABEL_ZH.values())


# ---------------------------------------------------------------- 几何

def dm(a, b) -> float:
    """两点球面近似距离（米）。a / b = (lon, lat)。"""
    dx = (b[0] - a[0]) * math.cos((a[1] + b[1]) / 2 * RAD)
    dy = b[1] - a[1]
    return math.hypot(dx, dy) * RAD * R


def line_len(line) -> float:
    return sum(dm(line[i], line[i + 1]) for i in range(len(line) - 1))


def pt_key(p) -> tuple[float, float]:
    """坐标的"路口点"归一化键（1e-5 度 ≈ 1.1 m，用来判同一个路口）。"""
    return (round(p[0], 5), round(p[1], 5))


def auto_range_m(car_list, nodes_ll, anchor, margin: float = 1.2, round_to: float = 50.0):
    """**自动推站点范围半径**（业主 2026-10-17：每站大小不同，不能全靠人量）。

    判据（可复现、可解释、可审计 —— **不是让 AI 看图拍脑袋**）：

      1. 「站区车道」= OSM 里 `service=parking_aisle` / `service=driveway` /
         `amenity=parking` 这些**停车场与场区内部道路**；
      2. 取**离锚点最远**的站区车道点到锚点的直线距离 `d_site`；
      3. 半径 = `d_site × margin`（默认 ×1.2，覆盖进出主路），再**四舍五入到 50 m**。

    为什么是这套判据：站前"围栏内"能走的道路，本质上就是**停车场 + 场区道**；
    它们铺到哪，站区就多大。这个量有 OSM 数据支撑，换站能自动算出，人只做确认。

    回落：该站 OSM 里没有站区车道（部分小站不画）时，用「全部路网最远点 × 0.45」。

    返回 `(range_m, reason_dict)`。
    """
    d_site = 0.0
    d_all = 0.0
    for w in car_list:
        t = w["tags"]
        is_site = (t.get("service") in ("parking_aisle", "driveway")
                   or t.get("amenity") == "parking")
        for n in w["nds"]:
            d = dm(anchor, nodes_ll[n])
            d_all = max(d_all, d)
            if is_site:
                d_site = max(d_site, d)

    if d_site > 0:
        raw = d_site * margin
        basis = f"站区车道最远点 {d_site:.0f} m × {margin}"
        src = "site_roads"
    else:
        raw = d_all * 0.45
        basis = f"（该站未画站区车道，回落）全部路网最远点 {d_all:.0f} m × 0.45"
        src = "fallback_all_roads"

    r = round(raw / round_to) * round_to if raw > 0 else 0
    reason = {
        "auto_range": True, "basis": basis, "source": src,
        "raw_m": round(raw, 1), "rounded_to": round_to, "margin": margin,
        "d_site_m": round(d_site, 1), "d_all_roads_m": round(d_all, 1),
    }
    return r, reason


def inside_fraction(pts, anchor, range_m: float, samples_per_edge: int = 20) -> float:
    """折线有多少比例的**里程**落在「以 anchor 为圆心、range_m 为半径」的圈内（0~1）。"""
    total = inside = 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        seg = dm(a, b)
        if seg <= 1e-9:
            continue
        total += seg
        k = samples_per_edge
        hit = 0
        for j in range(k):
            t = (j + 0.5) / k
            p = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            if dm(p, anchor) <= range_m:
                hit += 1
        inside += seg * hit / k
    return inside / total if total > 0 else 0.0


# ---------------------------------------------------------------- 读 OSM

def parse_osm(path: Path):
    txt = path.read_text(encoding="utf-8", errors="replace")
    nodes: dict[str, tuple[float, float]] = {}
    for m in re.finditer(r'<node id="(\d+)"[^>]*lat="(-?[\d.]+)"[^>]*lon="(-?[\d.]+)"', txt):
        nodes[m.group(1)] = (float(m.group(3)), float(m.group(2)))

    ways = []
    cur, tags, nds = None, [], []
    for line in txt.splitlines():
        s = line.strip()
        m = re.match(r'<way id="(\d+)"', s)
        if m:
            cur, tags, nds = m.group(1), [], []
            continue
        m = re.match(r'<nd ref="(\d+)"', s)
        if m and cur is not None:
            nds.append(m.group(1))
            continue
        m = re.match(r'<tag k="([^"]+)" v="([^"]+)"', s)
        if m and cur is not None:
            tags.append((m.group(1), m.group(2)))
            continue
        if s.startswith("</way>") and cur is not None:
            d = dict(tags)
            kept = [n for n in nds if n in nodes]
            pts = [nodes[n] for n in kept]
            if len(pts) >= 2:
                ways.append({"way_id": cur, "nds": kept, "pts": pts, "tags": d})
            cur, tags, nds = None, [], []
    return nodes, ways


def car_ways(ways):
    out = []
    for w in ways:
        t = w["tags"]
        hw = t.get("highway", "")
        if hw in SKIP_HIGHWAYS:
            continue
        if t.get("railway") or t.get("route"):
            continue
        if not hw and not t.get("service"):
            continue
        out.append(w)
    return out


def group_key(w) -> str:
    t = w["tags"]
    if t.get("name"):
        return t["name"]
    if t.get("service"):
        return "service:" + t["service"]
    return t.get("highway") or "未分类"


def kind_of(w) -> str:
    return "main" if w["tags"].get("highway") in MAIN_HIGHWAYS else "ramp"


def label_of(w) -> str:
    t = w["tags"]
    if t.get("name"):
        return t["name"]
    key = group_key(w)
    return LABEL_ZH.get(key, key)


# ---------------------------------------------------------------- 第 1 步：获取路线

def chain_ways(ways):
    """组内按**共享 OSM 节点**串成长折线。返回 [(pts, nds, src_way_id_per_pt), ...]。

    顶点一个都不改：新点只从原始 way 的点里取，并记录它来自哪个 way（供第 3 步溯源）。
    """
    remaining = list(ways)
    out = []
    while remaining:
        head = remaining.pop(0)
        pts = list(head["pts"])
        nds = list(head["nds"])
        src = [head["way_id"]] * len(pts)
        tail = nds[-1]
        extended = True
        while extended:
            extended = False
            for i, w in enumerate(remaining):
                if w["nds"][0] == tail:
                    new_pts, new_nds = w["pts"][1:], w["nds"][1:]
                elif w["nds"][-1] == tail:
                    new_pts, new_nds = w["pts"][::-1][1:], w["nds"][::-1][1:]
                else:
                    continue
                pts.extend(new_pts)
                nds.extend(new_nds)
                src.extend([w["way_id"]] * len(new_pts))
                tail = nds[-1]
                remaining.pop(i)
                extended = True
                break
        out.append((pts, nds, src))
    return out


def snap_merge(pieces, tol: float):
    """把端点相距 ≤ tol 的两片接起来（**只做端点对接，不动中间顶点**）。"""
    pieces = [(list(p), list(n), list(s)) for p, n, s in pieces]
    changed = True
    while changed:
        changed = False
        for i in range(len(pieces)):
            for j in range(i + 1, len(pieces)):
                a, na, sa = pieces[i]
                b, nb, sb = pieces[j]
                how, d = min(
                    (("hh", dm(a[0], b[0])), ("ht", dm(a[0], b[-1])),
                     ("th", dm(a[-1], b[0])), ("tt", dm(a[-1], b[-1]))),
                    key=lambda x: x[1],
                )
                if d > tol:
                    continue
                if how == "hh":
                    newp, newn, news = a[::-1] + b, na[::-1] + nb, sa[::-1] + sb
                elif how == "ht":
                    newp, newn, news = a[::-1] + b[::-1], na[::-1] + nb[::-1], sa[::-1] + sb[::-1]
                elif how == "th":
                    newp, newn, news = a + b, na + nb, sa + sb
                else:
                    newp, newn, news = a + b[::-1], na + nb[::-1], sa + sb[::-1]
                # 接缝处若两点几乎重合，去掉重复的那一个（仍只删点，不改坐标）
                if newp[0] and len(newp) > 1 and dm(newp[0], newp[1]) < 0.05:
                    newp, newn, news = newp[1:], newn[1:], news[1:]
                pieces = [p for k, p in enumerate(pieces) if k not in (i, j)] + [(newp, newn, news)]
                changed = True
                break
            if changed:
                break
    return pieces


def build_roads(car_list, snap_m: float, min_road_m: float):
    """第 1 步：把 way 串成整条路（几何零改动）。"""
    groups: dict[str, list] = defaultdict(list)
    for w in car_list:
        groups[group_key(w)].append(w)

    roads = []
    for key, ws in groups.items():
        pieces = snap_merge(chain_ways(ws), snap_m)
        for pts, nds, src in pieces:
            L = line_len(pts)
            if L < max(min_road_m, 1.0):
                continue
            roads.append({
                "name": LABEL_ZH.get(key, key) if not any(x["tags"].get("name") for x in ws) else key,
                "name_raw": key,
                "kind": "main" if any(kind_of(x) == "main" for x in ws) else "ramp",
                "pts": pts,
                "nds": nds,
                "src": src,
                "length_m": L,
            })
    roads.sort(key=lambda r: (0 if r["kind"] == "main" else 1, r["name_raw"], -round(r["length_m"], 3)))
    return roads


# ---------------------------------------------------------------- 第 2 步：分段

def find_junction_flags(roads, tol_m: float):
    """找出**路口顶点**：该顶点所在的"容差簇"里出现了 ≥2 条**不同路线**的顶点。

    ⚠️ 容差 `tol_m` 必须真的用上（早先声明了 `--junction-tol-m` 却用固定网格键，
       等于参数是死的 —— 快速独立审查抓到的）。这里按 `tol_m` 做空间聚类：
       · 用格哈希把点分桶（格边长 = tol_m），只在 3×3 邻域里比距离；
       · **同一条路线内部的点不聚**（聚了会把折线压扁），只跨路线聚；
       · 代表取簇内最小下标，确定性。

    返回 `{road_idx: {point_idx, ...}}`。
    """
    tol = max(tol_m, 0.5)
    pts_m: list[tuple[int, int, float, float]] = []      # (road_idx, pt_idx, x_m, y_m)
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    for ri, r in enumerate(roads):
        for pi, p in enumerate(r["pts"]):
            x, y = p[0] * 102000.0, p[1] * 111000.0      # 近似米（本地小范围够用）
            grid[(int(x // tol), int(y // tol))].append(len(pts_m))
            pts_m.append((ri, pi, x, y))

    parent = list(range(len(pts_m)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if ra <= rb:
            parent[rb] = ra
        else:
            parent[ra] = rb

    for (cx, cy), idxs in grid.items():
        neigh: list[int] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                neigh.extend(grid.get((cx + dx, cy + dy), ()))
        for i in idxs:
            ri, _pi, x, y = pts_m[i]
            for j in neigh:
                rj, _pj, x2, y2 = pts_m[j]
                if ri == rj:
                    continue                     # 同一条路线内部不聚
                if math.hypot(x - x2, y - y2) <= tol:
                    union(i, j)

    cluster_roads: dict[int, set[int]] = defaultdict(set)
    for i, (ri, _pi, _x, _y) in enumerate(pts_m):
        cluster_roads[find(i)].add(ri)
    flags: dict[int, set[int]] = defaultdict(set)
    for i, (ri, pi, _x, _y) in enumerate(pts_m):
        if len(cluster_roads[find(i)]) >= 2:
            flags[ri].add(pi)
    return flags


def cut_roads(roads, flags):
    """第 2 步：在路线**自身的路口顶点**处切开。返回原始段列表（几何仍是原始顶点）。"""
    pieces = []
    for idx, r in enumerate(roads):
        pts, nds, src = r["pts"], r["nds"], r["src"]
        cut = [0]
        for i in range(1, len(pts) - 1):
            if i in flags.get(idx, ()):
                cut.append(i)
        cut.append(len(pts) - 1)
        for a, b in zip(cut, cut[1:]):
            if b <= a:
                continue
            sub_pts = pts[a:b + 1]
            sub_nds = nds[a:b + 1]
            sub_src = src[a:b + 1]
            L = line_len(sub_pts)
            if L <= 0.5:
                continue
            pieces.append({
                "road_idx": idx,
                "name_raw": r["name"],
                "kind": r["kind"],
                "pts": sub_pts,
                "nds": sub_nds,
                "way_ids": sorted(set(sub_src)),
                "length_m": L,
            })
    return pieces


# ---------------------------------------------------------------- 第 3 步：打标签

def _is_generic(name: str) -> bool:
    return name in GENERIC_NAMES


def _same_geometry(a, b, tol_m: float = 1.0) -> bool:
    """两段是不是**同一条几何**（同向或反向都算）。"""
    if abs(a["length_m"] - b["length_m"]) > max(tol_m * 2, 1.0):
        return False
    pa, pb = a["pts"], b["pts"]
    if len(pa) != len(pb):
        return False
    if all(dm(x, y) <= tol_m for x, y in zip(pa, pb)):
        return True
    return all(dm(x, y) <= tol_m for x, y in zip(pa, reversed(pb)))


def merge_coincident(pieces, tol_m: float = 1.0):
    """合并**同向且几何重合**的段（OSM 里主路与辅路/匝道共用同一条中心线）。

    ⚠️ 只按「起止节点相同」分组是不够的 —— 起止点相同但**走法不同**的两条路径
       会被错误并掉（快速独立审查抓到的）。这里必须**逐点校验几何重合**
       （`_same_geometry`：点数一致 + 逐点距离 ≤ tol_m，同向或反向）。

    只合并同向；反向成对（A→B 与 B→A）保留为两条有向边（有向图要方向，单行限制靠它）。
    """
    groups: dict[tuple, list] = defaultdict(list)
    for s in pieces:
        groups[(pt_key(s["pts"][0]), pt_key(s["pts"][-1]))].append(s)

    out = []
    for _key, group in groups.items():
        if len(group) == 1:
            out.append(group[0])
            continue
        group.sort(key=lambda s: (
            0 if s["kind"] == "main" else 1,
            0 if not _is_generic(s["name_raw"]) else 1,
            -round(s["length_m"], 3),
        ))
        used = [False] * len(group)
        for i, s in enumerate(group):
            if used[i]:
                continue
            merged = [s]
            used[i] = True
            for j in range(i + 1, len(group)):
                if used[j]:
                    continue
                if _same_geometry(s, group[j], tol_m):
                    merged.append(group[j])
                    used[j] = True
            if len(merged) == 1:
                out.append(s)                 # 起止点相同但几何不同 → 各自保留
                continue
            head = dict(merged[0])
            head["way_ids"] = sorted({w for m in merged for w in m["way_ids"]})
            head["merged_ways"] = len(merged)
            head["merged_from"] = [m["name_raw"] for m in merged[1:]]
            out.append(head)
    return out


# ---------------------------------------------------------------- 组装成图结构

def build(car_list, nodes_ll, snap_m: float, junction_tol_m: float, min_seg_m: float,
          seg_prefix: str, merge_coincident_on: bool = True,
          range_m: float = 0.0, anchor=None, min_coverage_pct: float = 0.0):
    # 第 1 步
    roads = build_roads(car_list, snap_m, min_seg_m)
    # 第 2 步
    junction_flags = find_junction_flags(roads, junction_tol_m)
    pieces = [s for s in cut_roads(roads, junction_flags)]

    # 第 3 步前的合并（几何重合的重复段）
    before = len(pieces)
    if merge_coincident_on:
        pieces = merge_coincident(pieces, tol_m=1.0)
    merged_coincident = before - len(pieces)

    # ③' 范围过滤（业主 2026-10-17：只保留站点红线圈内的路线，圈外不要）
    before_range = len(pieces)
    if range_m > 0 and anchor is not None:
        kept = []
        for s in pieces:
            frac = inside_fraction(s["pts"], anchor, range_m)
            if frac * 100.0 >= min_coverage_pct:
                s["inside_pct"] = round(frac * 100.0, 1)
                kept.append(s)
        pieces = kept

    # 节点：每个切点（坐标键）→ 稳定短编号 N-001…（按经纬度排序，确定性）
    keys = sorted({pt_key(s["pts"][0]) for s in pieces} | {pt_key(s["pts"][-1]) for s in pieces})
    nid = {k: f"N-{i:03d}" for i, k in enumerate(keys, start=1)}
    key_of = {v: k for k, v in nid.items()}

    # 节点坐标取该键第一次出现时的原始点（**原样，不取平均**）
    node_ll = {}
    for s in pieces:
        for p in (s["pts"][0], s["pts"][-1]):
            node_ll.setdefault(pt_key(p), p)

    deg = defaultdict(int)
    for s in pieces:
        deg[nid[pt_key(s["pts"][0])]] += 1
        deg[nid[pt_key(s["pts"][-1])]] += 1

    # 排序：主干在前 → 路名 → 长度降序 → 起止节点（全程确定性）
    pieces.sort(key=lambda s: (
        0 if s["kind"] == "main" else 1, s["name_raw"], -round(s["length_m"], 3),
        nid[pt_key(s["pts"][0])], nid[pt_key(s["pts"][-1])],
    ))
    name_count = defaultdict(int)
    for s in pieces:
        name_count[s["name_raw"]] += 1

    edges = []
    for i, s in enumerate(pieces, start=1):
        f = nid[pt_key(s["pts"][0])]
        t = nid[pt_key(s["pts"][-1])]
        name = f"{s['name_raw']}（{f}→{t}）" if name_count[s["name_raw"]] > 1 else s["name_raw"]
        edges.append({
            "segment_id": f"{seg_prefix}-{i:03d}",
            "id": f"{seg_prefix}-{i:03d}",   # 契约 edges[].id 的兼容别名（与 segment_id 同值）
            "name": name,
            "name_raw": s["name_raw"],
            "kind": s["kind"],
            "from": f,
            "to": t,
            "length_m": round(s["length_m"], 1),
            "way_ids": s["way_ids"],
            **({"merged_ways": s["merged_ways"]} if "merged_ways" in s else {}),
            **({"merged_from": s["merged_from"]} if "merged_from" in s else {}),
            "lanes": next((car[0] for car in [s.get("_lanes") or (None,)] if car[0] is not None), None),
            "oneway": None,
            "speed_limit": None,
            "capacity_vph": None,
            "t0": None,
            "boundary": deg[f] == 1 or deg[t] == 1,
            "coords": [[round(c[0], 7), round(c[1], 7)] for c in s["pts"]],
        })

    # 从 OSM tag 抽 lanes / oneway（按 way_ids 溯源；抽不到就 null）
    tag_of = {w["way_id"]: w["tags"] for w in car_list}
    for e in edges:
        for wid in e["way_ids"]:
            t = tag_of.get(wid, {})
            if e["lanes"] is None and str(t.get("lanes", "")).isdigit():
                e["lanes"] = int(t["lanes"])
            if e["oneway"] is None and t.get("oneway") in ("yes", "no", "-1"):
                e["oneway"] = t["oneway"]

    nodes = []
    for nidv in sorted(nid.values(), key=lambda x: int(x.split("-")[1])):
        k = key_of[nidv]
        lon, lat = node_ll[k]
        nodes.append({
            "node_id": nidv,
            "id": nidv,                      # 契约 nodes[].id 的兼容别名（与 node_id 同值）
            "lon": round(lon, 7), "lat": round(lat, 7),
            "degree": deg[nidv], "boundary": deg[nidv] == 1,
        })

    # 连通分量 + 几何保真自检
    adj = defaultdict(set)
    for e in edges:
        adj[e["from"]].add(e["to"])
        adj[e["to"]].add(e["from"])
    seen: set[str] = set()
    components = []
    for e in edges:
        if e["from"] in seen:
            continue
        stack, comp = [e["from"]], 0
        while stack:
            u = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            comp += 1
            stack.extend(adj[u])
        components.append(comp)

    orig_pts = {pt_key(p) for p in nodes_ll.values()}
    bad_pts = 0
    for e in edges:
        for c in e["coords"]:
            if pt_key(c) not in orig_pts:
                bad_pts += 1

    stats = {
        "roads": len(roads),
        "segments_before_range": before_range,
        "segments": len(edges),
        "range_m": range_m,
        "anchor_lonlat": list(anchor) if anchor else None,
        "min_coverage_pct": min_coverage_pct,
        "junction_points": sum(len(v) for v in junction_flags.values()),
        "segments": len(edges),
        "nodes": len(nodes),
        "total_length_m": round(sum(e["length_m"] for e in edges), 1),
        "boundary_segments": sum(1 for e in edges if e["boundary"]),
        "components": len(components),
        "largest_component_nodes": max(components) if components else 0,
        "lanes_available": sum(1 for e in edges if e["lanes"] is not None),
        "oneway_available": sum(1 for e in edges if e["oneway"] is not None),
        "merged_coincident": merged_coincident,
        "fidelity_bad_points": bad_pts,
    }
    return nodes, edges, stats


# ---------------------------------------------------------------- 落盘

def make_payload(nodes, edges, stats, site, osm_name, snap_m, junction_tol_m, min_seg_m,
                 seg_prefix, range_m=0.0, anchor=None, min_coverage_pct=0.0) -> dict:
    return {
        "is_simulated": True,
        "note": (
            "几何取自 OpenStreetMap 切片（真值）。三步口径（业主 2026-10-17）："
            "① 先获取路线（按路名归并 + 共享节点串链，**顶点零改动**）；"
            "② 再分段（只在**真实路口顶点**处切开，不插值不移动）；"
            "③ 再打标签（段名 = 路名；同名多段时加（起路口→止路口）后缀；无名路沿用通用译名，不编造）。"
            "lanes / oneway 从 OSM tag 抽（抽不到即 null）；"
            "speed_limit / capacity_vph / t0 一律 null —— 等 T2 路段属性核对表补。"
            "本文件是脚本产物（work/twin/netpack/build_junction_pack.py），勿手改。"
        ),
        "site": site, "crs": "WGS-84",
        "source": "OpenStreetMap (ODbL 1.0)",
        "generated_by": "work/twin/netpack/build_junction_pack.py",
        "osm_file": osm_name, "split_mode": "route_then_segment",
        "params": {"snap_m": snap_m, "junction_tol_m": junction_tol_m,
                   "min_seg_m": min_seg_m, "seg_prefix": seg_prefix,
                   "range_m": range_m,
                   "anchor_lonlat": list(anchor) if anchor else None,
                   "min_coverage_pct": min_coverage_pct,
                   "naming": "<name_raw>，同名多段时再补（<from>→<to>）"},
        "stats": stats,
        "contract_map": {
            "_说明": "与 docs/数据契约.md 第六节 stations/network.json 的字段对应；不新增契约字段。",
            "nodes[].id": "nodes[].node_id",
            "nodes[].x / .y": "**本文件不输出**（契约写 x/y 单位 m，与「站点包统一存 WGS-84」冲突 → 待开发B 裁定；要用坐标请读 lon/lat）",
            "edges[].id": "edges[].segment_id",
            "edges[].section": "edges[].segment_id（与 segments 的 segment_id 一一对应）",
            "edges[].detector": "null（检测器点位在 points.json，不在本文件）",
            "edges[].lanes / .length_m / .speed_limit / .capacity_vph": "同名直通",
            "_missing_by_contract": ["nodes[].x", "nodes[].y"],
            "_新增字段（本文件自用，接口层不应透出）": [
                "name", "name_raw", "kind", "boundary", "way_ids", "oneway", "t0",
                "merged_ways", "merged_from", "coords", "stats", "contract_map",
            ],
        },
        "nodes": nodes, "edges": edges,
    }


def fmt_ts(edges, osm_name: str, export_name: str = "STATION_Z_SEGMENTS") -> str:
    lines = [
        "// 站点包 ·「站点 OSM 真路网 · 先路线后分段」演示站",
        "//",
        f"// 来源：{osm_name} 切片经 build_junction_pack.py（① 获取路线 → ② 路口切分 → ③ 打标签）。",
        "// **几何取自 OSM（真值）**；路况指标一律为**演示数据（模拟）**。",
        "// 本文件是脚本产物（work/twin/netpack/build_junction_pack.py），**勿手改**。",
        "",
        "import type { PackSegment } from './types.ts'",
        "",
        f"export const {export_name}: PackSegment[] = [",
    ]
    for s in edges:
        lines.append("  {")
        lines.append(f"    segment_id: '{s['segment_id']}',")
        safe = s["name"].replace("\\", "\\\\").replace("'", "\\'")
        lines.append(f"    name: '{safe}',")
        lines.append(f"    kind: '{s['kind']}',")
        lines.append("    coords: [")
        coords = ",\n          ".join(f"[{c[0]:.7f}, {c[1]:.7f}]" for c in s["coords"])
        lines.append(f"          {coords}")
        lines.append("    ],")
        lines.append("  },")
    lines += ["]", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="先获取路线，再分段，再打标签（含拓扑）。默认参数与路径读 work/twin/site-ranges.json（每站一份）"
    )
    ap.add_argument("--config", default=str(DEFAULT_CONFIG_PATH),
                    help="站点范围登记表（默认 work/twin/site-ranges.json）")
    ap.add_argument("--site-id", default=None,
                    help="登记表里的 site_id（缺省取 default_site）；换站只加一条记录、脚本不改")
    ap.add_argument("--osm", default=None, help="OSM 切片路径（缺省取配置 osm_file）")
    ap.add_argument("--site", default=None, help="站点显示名（缺省取配置 site_name）")
    ap.add_argument("--out-json", default=None, help="产物 JSON（缺省取配置 out_json）")
    ap.add_argument("--out-ts", default=None,
                    help="前端几何 TS（缺省取配置 out_ts；传空串表示不输出）")
    ap.add_argument("--snap-m", type=float, default=None)
    ap.add_argument("--junction-tol-m", type=float, default=None)
    ap.add_argument("--min-seg-m", type=float, default=None)
    ap.add_argument("--seg-prefix", default=None)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--anchor-lonlat", default=None,
                    help="站点锚点 \"lon,lat\"（缺省取配置 anchor_lonlat）")
    ap.add_argument("--range-m", type=float, default=None,
                    help="范围半径（米）；缺省取配置 range_m；0 = 不过滤")
    ap.add_argument("--auto-range", action="store_true",
                    help="按站区车道最远点×1.2 推**候选**半径（只打印候选，不自动写配置）")
    ap.add_argument("--min-coverage-pct", type=float, default=None,
                    help="段落在圈内的里程占比低于此值就丢掉（缺省取配置，默认 10%%）")
    ap.add_argument("--no-merge-coincident", dest="merge_coincident",
                    action="store_false", help="不合并几何重合的段（复现合并前段数）")
    a = ap.parse_args()

    # ---- 参数解析：登记表为默认，CLI 可覆盖；换站只改配置、脚本零改动 ----
    cfg_path = Path(a.config)
    site = load_site(a.site_id, cfg_path) if cfg_path.exists() else None
    if site is None and not (a.osm and a.site and a.out_json):
        print("❌ 找不到站点范围登记表（--config），且未给全 --osm / --site / --out-json")
        return 2

    def pick(key: str, cli_value, fallback=None):
        if cli_value is not None and cli_value != "":
            return cli_value
        if site is not None and key in site:
            return site[key]
        return fallback

    site_name = pick("site_name", a.site, "")
    osm_raw = pick("osm_file", a.osm)
    out_json_raw = pick("out_json", a.out_json)
    if not site_name or not osm_raw or not out_json_raw:
        print("❌ 站点名 / OSM 切片 / 产物路径三者不全（配置或 CLI 补）")
        return 2
    osm_path = repo_path(osm_raw) if not Path(osm_raw).is_absolute() else Path(osm_raw)
    if not osm_path.exists():
        print(f"❌ OSM 切片不存在：{osm_path}")
        return 2
    out_json = repo_path(out_json_raw) if not Path(out_json_raw).is_absolute() else Path(out_json_raw)
    out_ts_raw = a.out_ts if a.out_ts is not None else pick("out_ts", None)
    out_ts = repo_path(out_ts_raw) if out_ts_raw else None

    snap_m = float(pick("snap_m", a.snap_m, DEFAULT_SNAP_M))
    junction_tol_m = float(pick("junction_tol_m", a.junction_tol_m, DEFAULT_JUNCTION_TOL_M))
    min_seg_m = float(pick("min_seg_m", a.min_seg_m, DEFAULT_MIN_SEG_M))
    seg_prefix = str(pick("seg_prefix", a.seg_prefix, DEFAULT_SEG_PREFIX))
    # 前端几何 TS 的导出名：Z 沿用历史名（保证既有产物逐字节不变）；新站由登记表给（如 STATION_GZ_SEGMENTS）
    ts_export = str(pick("ts_export", None, "STATION_Z_SEGMENTS"))
    min_coverage_pct = float(pick("min_coverage_pct", a.min_coverage_pct, 10.0))

    anchor = None
    if a.anchor_lonlat:
        parts = [float(x) for x in a.anchor_lonlat.split(",")]
        anchor = (parts[0], parts[1])
    elif site is not None and site.get("anchor_lonlat"):
        anchor = tuple(float(v) for v in site["anchor_lonlat"])

    range_m = float(a.range_m) if a.range_m is not None else (float(site["range_m"]) if site else 0.0)

    nodes_ll, ways = parse_osm(osm_path)
    car = car_ways(ways)
    osm_name = osm_path.name

    auto_reason = None
    # `range_source=script` 的站（当前口径：脚本自动推）默认用**同一算法复算**并与登记表对账；
    # manual 站直接用登记值，不自动改。脚本**从不写登记表**（改配置只能人工编辑）。
    use_auto = a.auto_range or (
        site is not None and site.get("range_source") == "script" and a.range_m is None
    )
    if use_auto:
        if anchor is None:
            print("❌ 自动推范围需要站点锚点（--anchor-lonlat 或配置 anchor_lonlat）")
            return 2
        computed, auto_reason = auto_range_m(car, nodes_ll, anchor)
        if a.auto_range:
            print(f"范围候选（**仅候选，不自动写配置**）：{auto_reason['basis']} → **{computed:.0f} m**")
        if site is not None and abs(computed - float(site["range_m"])) > 1e-6:
            print(f"❌ 配置 range_m={site['range_m']} 与脚本复算 {computed:.0f} m 不一致；"
                  "请人工确认后改 work/twin/site-ranges.json（脚本不自动改登记表）")
            return 2
        range_m = computed

    r_nodes, r_edges, stats = build(car, nodes_ll, snap_m, junction_tol_m,
                                    min_seg_m, seg_prefix, a.merge_coincident,
                                    range_m, anchor, min_coverage_pct)
    stats["range_reason"] = auto_reason

    # 范围 → 段数目标对账：seg_target 是人工定的目标，脚本不自动改（范围一变要人工重定）
    if site is not None and int(site.get("seg_target", 0)) and stats["segments"] != int(site["seg_target"]):
        print(f"❌ 段数 {stats['segments']} ≠ 配置 seg_target {site['seg_target']}："
              "范围/阈值变了要人工重定段数目标，**未写盘**")
        return 2

    # ⚠️ 几何保真自检必须在**写盘之前**跑：失败时不能把坏产物落盘
    #    （快速独立审查抓到的顺序问题 —— 早先是先写盘再自检，退出码 2 时坏文件已经在仓库里了）
    if stats["fidelity_bad_points"]:
        print(f"❌ 几何保真自检失败：{stats['fidelity_bad_points']} 个输出顶点不在 OSM 原始节点集里"
              " —— **未写盘**，先修算法")
        return 2

    payload = make_payload(r_nodes, r_edges, stats, site_name, osm_name, snap_m,
                           junction_tol_m, min_seg_m, seg_prefix,
                           range_m, anchor, min_coverage_pct)
    json_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    targets = [(out_json, json_text)]
    if out_ts is not None:
        targets.append((out_ts, fmt_ts(r_edges, osm_name, ts_export)))

    if a.check:
        bad = 0
        for path, want in targets:
            have = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else ""
            if have != want:
                print(f"❌ 与既有产物不一致：{path}")
                bad += 1
            else:
                print(f"✅ 一致：{path}")
        print(f"\n{stats['segments']} 段 / {stats['nodes']} 节点 / 总长 {stats['total_length_m']:.0f} m")
        return 1 if bad else 0

    for path, text in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")   # 仓库统一 LF
        print(f"→ {path}")

    print(f"\n站点：{site_name}   way {len(ways)} 条（车行 {len(car)}）")
    print(f"第1步 获取路线：{stats['roads']} 条")
    print(f"第2步 分段：路口点 {stats['junction_points']} 个 → {stats['segments']} 段 / "
          f"{stats['nodes']} 节点 / 总长 {stats['total_length_m']:.0f} m"
          + (f"（合并重合段 {stats['merged_coincident']} 条）" if stats["merged_coincident"] else ""))
    if stats["range_m"]:
        print(f"   ↳ 范围过滤：锚点 {stats['anchor_lonlat']} 半径 {stats['range_m']:.0f} m，"
              f"覆盖率阈值 {stats['min_coverage_pct']:.0f}% → "
              f"{stats['segments_before_range']} 段筛到 {stats['segments']} 段")
    print(f"第3步 打标签：lanes {stats['lanes_available']}/{stats['segments']} 段 · "
          f"oneway {stats['oneway_available']}/{stats['segments']} 段；"
          "speed_limit / capacity_vph / t0 全 null（等 T2，不编造）")
    print(f"连通分量 {stats['components']} 个（最大含 {stats['largest_component_nodes']} 节点）"
          f" · 边界段 {stats['boundary_segments']} 条")
    print("✅ 几何保真自检通过（写盘前已校验）：每个输出顶点都是 OSM 原始节点坐标")
    return 0


if __name__ == "__main__":
    sys.exit(main())
