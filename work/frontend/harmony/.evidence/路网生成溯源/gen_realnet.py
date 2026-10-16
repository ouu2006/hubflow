"""
把队长给的真实地图 hubflow-nosearch(1).html 里的 DATA 转成 ArkTS 路网文件。

【投影 —— 为什么用等距圆柱且保持地理等比】
地图条款禁止落盘 OSM/高德数据，但**演示用的自绘图必须不变形**。
经纬度直接线性映射到 680x880 会把图拉扁（当地 1° lng ≈ 0.919 × 1° lat），
所以 x 方向乘 cos(中心纬度) 做等比缩放，两个方向用**同一个比例尺**，
再居中放进画布 —— 这样路网形状与真实地理一致，图不会被横向拉伸。

【输出用扁平数组 —— 为什么不用 {x,y} 对象字面量】
ArkTS 里，几百个 { x: 112, y: 234 } 对象字面量既占体积又拖慢编译。
改成扁平 number[]（x0,y0,x1,y1,…），运行期再用 toPts() 展开成 GeoPoint。
"""
import json
import math
import re
import os

SRC_HTML = r"C:\Users\ylz27\Documents\xwechat_files\wxid_jqli0ucw294r22_b11e\msg\file\2026-10\hubflow-nosearch(1).html"
PATHS_JSON = r"C:\dev\hubflow\.tmp-y\paths.json"
OUT_JSON = r"C:\dev\hubflow\.tmp-y\realmap2.json"
OUT_ETS = r"C:\dev\hubflow\.tmp-y\RealNet.ets"

W, H = 680, 880
M_PER_DEG_LAT = 111320.0


def load_data():
    html = open(SRC_HTML, encoding="utf-8").read()
    m = re.search(r"const\s+DATA\s*=\s*\{", html)
    if not m:
        raise SystemExit("no DATA")
    # 花括号配平
    i = m.end() - 1
    depth = 0
    for j in range(i, len(html)):
        if html[j] == "{":
            depth += 1
        elif html[j] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(html[i:j + 1])
    raise SystemExit("unbalanced")


def collect_polys(items):
    """layers.roads 的元素是 dict{coordinates, cls}；water/green 的元素是 [[lon,lat],…]"""
    out = []
    for it in items:
        if isinstance(it, dict):
            pts = it.get("coordinates") or []
        elif isinstance(it, list) and it:
            if isinstance(it[0], list):
                pts = it
            else:
                pts = [it]
        else:
            continue
        pts = [p for p in pts if isinstance(p, list) and len(p) >= 2]
        if len(pts) >= 2:
            out.append(pts)
    return out


def rdp(pts, eps):
    """抽稀：道格拉斯-普克，保留形状"""
    if len(pts) < 3:
        return pts
    x1, y1 = pts[0]
    x2, y2 = pts[-1]
    dx, dy = x2 - x1, y2 - y1
    den = math.hypot(dx, dy)
    best, bi = -1.0, 0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        if den < 1e-9:
            d = math.hypot(px - x1, py - y1)
        else:
            d = abs(dy * px - dx * py + x2 * y1 - y2 * x1) / den
        if d > best:
            best, bi = d, i
    if best > eps:
        return rdp(pts[:bi + 1], eps)[:-1] + rdp(pts[bi:], eps)
    return [pts[0], pts[-1]]


def project(bbox_route, polys_list, pad=16, zoom_out=0.34):
    """等距圆柱投影 + 等比 + 居中。返回 (proj_fn, meta)

    【x/y 都用「米」，但基准不同 —— 这是本函数最容易写错的地方】
      mx = (lon - lng0) * kx * M_PER_DEG_LAT
      my = (lat - lat0) * M_PER_DEG_LAT
    所以 y 反转时必须用 base_y - my*scale（base_y 已含 y_min 基准），
    不能直接拿绝对纬度乘 M —— 初版就这么写错，路线 y 全变成 -24xxxx。

    【缩放以「路线包围盒」为基准，不是全图层 —— 为什么】
    数据里路网整体约 5.5km × 6.5km，而路线只在其中 2.9km × 3.0km 的方框里绕。
    若按全图层定缩放，路线只占画面中间不到一半，一进来根本看不清走向。
    真实导航就是这样：**以路线为基准定比例尺，底图向四周延伸、超出部分裁掉**。
    zoom_out=0.34 表示路线框外再放 34% 余量，让路线占画面主体又不至于贴边。
    """
    lng0, lat0 = bbox_route[0], bbox_route[1]
    lat_c = 23.2
    kx = math.cos(math.radians(lat_c))
    # 路线包围盒（米，相对基准点）
    rb = []
    for lon, lat in bbox_route[2]:
        rb.append(((lon - lng0) * kx * M_PER_DEG_LAT, (lat - lat0) * M_PER_DEG_LAT))
    rx0, rx1 = min(m[0] for m in rb), max(m[0] for m in rb)
    ry0, ry1 = min(m[1] for m in rb), max(m[1] for m in rb)
    span_x = (rx1 - rx0) * (1 + zoom_out)
    span_y = (ry1 - ry0) * (1 + zoom_out)
    cx = (rx0 + rx1) / 2.0
    cy = (ry0 + ry1) / 2.0
    scale = min((W - 2 * pad) / span_x, (H - 2 * pad) / span_y)
    # 底图原点挪到视图中心对应的经纬（保证路线居中）
    ox_lng = lng0 + cx / (kx * M_PER_DEG_LAT)
    oy_lat = lat0 + cy / M_PER_DEG_LAT

    def proj(lon, lat):
        mx = (lon - ox_lng) * kx * M_PER_DEG_LAT
        my = (lat - oy_lat) * M_PER_DEG_LAT
        return (mx * scale + W / 2.0, H / 2.0 - my * scale)

    meta = {"scale": scale, "kx": kx, "ox_lng": ox_lng, "oy_lat": oy_lat,
            "route_span_x_m": rx1 - rx0, "route_span_y_m": ry1 - ry0}
    return proj, meta


def perp_offset_ll(pts_ll, max_off_deg, sign, end_drift_deg=0.0):
    """在**经纬度空间**沿法向做 sin 形偏移。

    【为什么在经纬度里做，而不在像素里做】
    初版在投影后的像素坐标里偏移，问题有两个：
      ① 偏移出来的线不落在任何路上，横穿街区与水面
      ② 经纬度直接当米用，x/y 比例失真
    现在先在经纬度里偏移（x 方向除以 cos(lat) 保持等比），
    再吸附到真实主干道 —— 出来的线就是「旁边那条平行路」。
    端点重合是对的（同一个 OD 对），中段必须明显分开。
    """
    lat_c = 23.2
    kx = math.cos(math.radians(lat_c))
    out = []
    n = len(pts_ll)
    for i, (lon, lat) in enumerate(pts_ll):
        t = i / (n - 1)
        j0 = max(0, i - 1)
        j1 = min(n - 1, i + 1)
        # 切向（先做等比换算，否则法向会歪）
        tx = (pts_ll[j1][0] - pts_ll[j0][0]) * kx
        ty = pts_ll[j1][1] - pts_ll[j0][1]
        L = math.hypot(tx, ty) or 1e-9
        nx, ny = -ty / L, tx / L
        d = (max_off_deg * math.sin(math.pi * t) + end_drift_deg) * sign
        out.append((lon + nx * d / kx, lat + ny * d))
    return out


def build_road_index(major_ll, k):
    """把主干道所有顶点做成网格索引，供吸附查询用。"""
    buckets = {}
    for poly in major_ll:
        for p in poly:
            gx = int(p[0] * k)
            gy = int(p[1] * k)
            buckets.setdefault((gx, gy), []).append(p)
    return buckets


def snap_to_roads(pt, buckets, k, radius_cells=1):
    """把一个投影后的点吸附到最近的主干道顶点。

    【为什么必须吸附 —— 用户看得出「路」和「随便画的线」的区别】
    初版的三条备选路线是沿法向做 sin 形偏移得到的，偏移后整条线会横穿街区、
    压过水面，看着不像路网里的路。吸附到最近的主干道顶点后，
    备选路线会「骑」在真实的黄色主干道上，和推荐路线一样是路。
    """
    gx, gy = int(pt[0] * k), int(pt[1] * k)
    best = None
    best_d = None
    for dx in range(-radius_cells, radius_cells + 1):
        for dy in range(-radius_cells, radius_cells + 1):
            for p in buckets.get((gx + dx, gy + dy), ()):
                d = (p[0] - pt[0]) ** 2 + (p[1] - pt[1]) ** 2
                if best_d is None or d < best_d:
                    best_d = d
                    best = p
    if best is None:
        return pt
    return best


def dedupe(pts, min_step=3.0):
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) >= min_step or abs(p[1] - out[-1][1]) >= min_step:
            out.append(p)
    return out


def flatten(pts):
    v = []
    for x, y in pts:
        v.append(int(round(x)))
        v.append(int(round(y)))
    return v


def main():
    data = load_data()
    roads = data["layers"]["roads"]
    majors = collect_polys([r for r in roads if r.get("cls") == "major"])
    minors = collect_polys([r for r in roads if r.get("cls") == "minor"])
    waters = collect_polys(data["layers"]["water"])
    greens = collect_polys(data["layers"]["green"])
    route_ll = data["coords"]
    man = data["maneuvers"]

    all_ll = majors + minors + waters + greens
    # 缩放以「规划出来的三条路线的并集包围盒」为基准
    #（见 project 的注释）：路线是主角，底图向四周延伸、超出裁掉
    _paths_early = json.load(open(PATHS_JSON, encoding="utf-8"))
    _route_box_ll = [pt for k in ("R1", "R2", "R3") for pt in _paths_early[k]]
    proj, meta = project((_route_box_ll[0][0], _route_box_ll[0][1], _route_box_ll), all_ll)
    kx_m = meta["kx"] * M_PER_DEG_LAT

    def conv(poly, eps, min_pts):
        pts = [proj(p[0], p[1]) for p in poly]
        pts = rdp(pts, eps) if len(pts) > 4 else pts
        # 去重
        ded = [pts[0]]
        for p in pts[1:]:
            if abs(p[0] - ded[-1][0]) >= 1 or abs(p[1] - ded[-1][1]) >= 1:
                ded.append(p)
        return ded if len(ded) >= min_pts else None

    def conv_all(lst, eps, min_pts):
        out = []
        for poly in lst:
            c = conv(poly, eps, min_pts)
            if c:
                out.append(c)
        return out

    M = conv_all(majors, 2.4, 2)
    N = conv_all(minors, 2.4, 2)
    WA = conv_all(waters, 3.0, 3)
    # 绿地很小（源数据每片只有 6~7 点），抽稀阈值必须小，否则整片被压成 1 点而丢掉
    G = conv_all(greens, 1.2, 3)
    R = [proj(p[0], p[1]) for p in route_ll]
    # 路线抽稀到 ~1.6px：85 点里有大量共线点，保留足够密度让弯道顺滑
    R = rdp(R, 1.6)

    # 三条到站路线几何：来自 paths.json（在真实路网上跑出来的三条不同的路）
    #
    # 【为什么是「路网路径规划」而不是「法向偏移 + 吸附」—— 试了两版才定下来】
    # v1 法向偏移：直线横穿街区、压过水面，一眼就看出不是路。
    # v2 偏移 + 吸附到主干道顶点：线落在路上了，但每个点独立吸附 → 锯齿；
    #    而且 R2/R3 经常吸到同一条路，重合成一条（又回到「路线二三一样」）。
    # v3（在路网上跑最短路，gen_routes_dijkstra.py）：三条路都真的沿路网走，
    #    长度递增（5044 → 5059 → 5120m）、路口数递增（17 → 20 → 23），
    #    与契约 alternatives[].reason 描述的差别一一对应。
    paths = json.load(open(PATHS_JSON, encoding="utf-8"))
    R1 = rdp([proj(p[0], p[1]) for p in paths["R1"]], 1.6)
    R2 = rdp([proj(p[0], p[1]) for p in paths["R2"]], 1.6)
    R3 = rdp([proj(p[0], p[1]) for p in paths["R3"]], 1.6)

    # 离站：到站路线倒过来走（起点=落客点，终点=出发侧）
    D1 = list(reversed(R1))
    D2 = list(reversed(R2))

    # 转向点：**在规划出来的路线上按里程取点**，不再用底图给的 12 个转向
    #
    # 【为什么必须重算 —— 踩过的坑】
    # 底图 coords 自带的 maneuvers 是按它自己那条路线算的里程。
    # 我们用 Dijkstra 规划的路线几何不同、长度也不同（5044m vs 底图 8612m），
    # 沿用旧里程会让转向点飘到路线外面去 —— 截图上橙色圈散落在地图各处，
    # 有几个干脆落在空白地上。
    # 现在：从规划路径累计里程，按「每 ~450m 一个转向点」重新生成。
    # 转向方位取该点前后切向的夹角（真的从几何算，不是猜的）。
    def build_turns(pts_ll, every_m=450.0):
        kx = math.cos(math.radians(23.2))

        def seg_m(a, b):
            return math.hypot((b[0] - a[0]) * kx * 111320.0, (b[1] - a[1]) * 111320.0)

        cum = [0.0]
        for i in range(1, len(pts_ll)):
            cum.append(cum[-1] + seg_m(pts_ll[i - 1], pts_ll[i]))
        total = cum[-1]
        n = max(2, int(total / every_m))
        out = []
        for k in range(n + 1):
            dist = total * k / n
            # 定位到具体线段
            lo = 0
            while lo + 1 < len(cum) and cum[lo + 1] < dist:
                lo += 1
            lo = min(lo, len(pts_ll) - 2)
            span = cum[lo + 1] - cum[lo]
            f = 0.0 if span < 1e-9 else (dist - cum[lo]) / span
            a, b = pts_ll[lo], pts_ll[lo + 1]
            lon = a[0] + (b[0] - a[0]) * f
            lat = a[1] + (b[1] - a[1]) * f
            # 切向夹角：0=直行，正=右转，负=左转
            i0 = max(0, lo - 1)
            i1 = min(len(pts_ll) - 1, lo + 2)
            t1x = (pts_ll[lo][0] - pts_ll[i0][0]) * kx
            t1y = pts_ll[lo][1] - pts_ll[i0][1]
            t2x = (pts_ll[i1][0] - pts_ll[lo][0]) * kx
            t2y = pts_ll[i1][1] - pts_ll[lo][1]
            L1 = math.hypot(t1x, t1y) or 1e-9
            L2 = math.hypot(t2x, t2y) or 1e-9
            cross = (t1x * t2y - t1y * t2x) / (L1 * L2)
            dot = (t1x * t2x + t1y * t2y) / (L1 * L2)
            ang = math.degrees(math.atan2(cross, dot))
            out.append({"dist": dist, "lon": lon, "lat": lat, "ang": ang})
        return out

    turns1 = build_turns(paths["R1"], 420.0)
    turns2 = build_turns(paths["R2"], 420.0)
    turns3 = build_turns(paths["R3"], 420.0)

    # 真实转向点：坐标由路线几何算出，里程也用重算后的
    def marks_of(turns):
        r = []
        for i, t in enumerate(turns):
            ax, ay = proj(t["lon"], t["lat"])
            a = t["ang"]
            if i == 0:
                mt, mod = "depart", "right"
            elif i == len(turns) - 1:
                mt, mod = "arrive", ""
            elif a > 38:
                mt, mod = "turn", "right"
            elif a < -38:
                mt, mod = "turn", "left"
            elif a > 15:
                mt, mod = "turn", "slight right"
            elif a < -15:
                mt, mod = "turn", "slight left"
            else:
                mt, mod = "continue", "straight"
            r.append({"d": int(t["dist"]), "type": mt, "mod": mod, "name": "",
                      "x": int(round(ax)), "y": int(round(ay))})
        return r

    marks = marks_of(turns1)
    print("R1 转向点", len(marks), "R2", len(turns2), "R3", len(turns3))

    out = {
        "W": W, "H": H, "meta": {k: (round(v, 8) if isinstance(v, float) else v) for k, v in meta.items()},
        "origin": {"lng": round(meta["ox_lng"], 7), "lat": round(meta["oy_lat"], 7),
                   "scale_px_per_m": round(meta["scale"], 8), "kx": round(meta["kx"], 6)},
        "majors": [flatten(p) for p in M],
        "minors": [flatten(p) for p in N],
        "waters": [flatten(p) for p in WA],
        "greens": [flatten(p) for p in G],
        "routes": {"R1": flatten(R1), "R2": flatten(R2), "R3": flatten(R3),
                   "D1": flatten(D1), "D2": flatten(D2)},
        "maneuvers": marks,
        "total_m": data["total"],
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False)

    print("major", len(out["majors"]), "pts", sum(len(r) // 2 for r in out["majors"]))
    print("minor", len(out["minors"]), "pts", sum(len(r) // 2 for r in out["minors"]))
    print("water", len(out["waters"]), "pts", sum(len(r) // 2 for r in out["waters"]))
    print("green", len(out["greens"]), "pts", sum(len(r) // 2 for r in out["greens"]))
    for k, v in out["routes"].items():
        print("route", k, len(v) // 2, "pts  start", v[:2], " end", v[-2:])
    print("maneuvers", len(marks))
    print("total pts", sum(len(r) // 2 for r in out["majors"] + out["minors"] + out["waters"] + out["greens"])
          + sum(len(v) // 2 for v in out["routes"].values()))
    print("scale(m->px)", round(meta["scale"], 6), "kx", round(meta["kx"], 6))


if __name__ == "__main__":
    main()
