r"""#61 twin_preview 桥接服务:SUMO TraCI 小仿真 → 车辆真值 + OSM 路网折线。

演示底座,不替代 #36(netbuild)/#37(map_ingest)/#38(孪生主循环)——正式路网与主循环归
work/twin/(开发A)。口径:
  - 路网:station.net.xml(Overpass OSM 切片 + netconvert,重建见 build_net.py)
  - 车辆:D1 送客(驶向落客段停驻后离开)/ D2 接客(过境),随机到发,固定种子可复现;
    状态映射 停驻→落客服务、speed<1.5→排队、其余→行驶
  - 字段:逐字对照数据契约 v2.0 vehicles 元素(vehicle_id/driver_type/segment_id/offset_m/
    lon/lat/state/guided/is_demo_bound);is_simulated 只写在信封层
  - 路段:命名主干按同名同方向连成整条链(吉庆大道/鼎湖大道各一条),站区未命名连接线取
    离站房最近的若干条;主干编号在前(SEG-001..),落客段 = 最近的站区连接线

接口(默认 127.0.0.1:8102,每个响应带 is_simulated=true):
  GET /api/twin/health     仿真时钟/车辆数/错误状态
  GET /api/twin/network    底图折线(前端入口替换示例路网用)
  GET /api/twin/vehicles   车辆真值快照(前端 traffic mock 优先拉这里,不可用回落合成车)

启动(仓库任意 python 3.10+,需 fastapi+uvicorn+pyproj;SUMO_HOME 在 PATH 且
PYTHONPATH 含 %SUMO_HOME%\tools):
  python work/frontend/tools/twin_preview/server.py
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import sumolib
import traci
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

DIR = Path(__file__).resolve().parent

# ---- 站点范围登记表（IKM4B4）：站房锚点 / 范围半径 / 路段数目标一律读 work/twin/site-ranges.json ----
ROOT = DIR.parents[3]
if str(ROOT / "work/twin") not in sys.path:
    sys.path.insert(0, str(ROOT / "work/twin"))
from site_config import DEFAULT_CONFIG_PATH, load_site  # noqa: E402

_SITE = load_site(None)

#: 默认门牌（**向后兼容**：不传参数就是原来那一套，不是给某个站加的分支）
DEFAULT_NET_FILE = DIR / "station.net.xml"
#: 默认站房锚点（经纬度）——读登记表；仅**启发式选路段**那条路用，有映射表时完全不读它
DEFAULT_STATION_LONLAT = tuple(float(v) for v in _SITE["anchor_lonlat"])
DEFAULT_SEG_COUNT = int(_SITE.get("bridge_seg_count", 10))
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8102


@dataclass
class BridgeConfig:
    """一次运行的配置 —— **全部可换**：换站 / 换网只改参数，不改代码，也不加站点分支。"""

    net_file: Path = DEFAULT_NET_FILE
    assignment_file: Path | None = None
    station_lonlat: tuple[float, float] = DEFAULT_STATION_LONLAT
    seg_count: int = DEFAULT_SEG_COUNT
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    site_name: str = ""


def load_assignment(path: Path, net) -> tuple[list[dict], str | None]:
    """读「SEG → SUMO 边链」映射表，返回 (segments, drop_segment_id)。

    **有它就不再从路网里猜路段** —— `select_segments()` 那套依赖**街名 + 站房位置**，
    换一张网（无名路、无地理配准）立刻失效。映射表形状：

        {"segments": [{"segment_id": "SEG-001", "name": "站前路", "kind": "main",
                       "edge_ids": ["E1_1", "E1_2"],
                       "coords": [[lon, lat], ...]           # 或直接给 shape_xy
                      }, ...],
         "drop_segment_id": "SEG-002"}                       # 可选

    `coords`（经纬度）会在这里换算成 `shape_xy`（供就近吸附与落客段距离用）。
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    segs = payload.get("segments")
    if not isinstance(segs, list) or not segs:
        raise SystemExit(f"映射表缺 segments 数组：{path}")
    for seg in segs:
        for key in ("segment_id", "edge_ids"):
            if not seg.get(key):
                raise SystemExit(f"映射表里有一条缺 {key}：{seg}")
        if "shape_xy" not in seg:
            coords = seg.get("coords")
            if not coords:
                raise SystemExit(f"{seg['segment_id']} 既没有 shape_xy 也没有 coords —— 两者给一个")
            seg["shape_xy"] = [tuple(net.convertLonLat2XY(lon, lat)) for lon, lat in coords]
        # name / kind 可省：name 缺就填 segment_id，kind 缺按 main（只影响展示与落客段偏好）
        seg.setdefault("name", seg["segment_id"])
        seg.setdefault("kind", "main")
    return segs, payload.get("drop_segment_id")


MAX_VEHICLES = 24
MAX_PENDING = 8
SPAWN_PROBABILITY = 0.45
STEP_S = 1.0
DROP_STOP_S = 12
QUEUE_SPEED_MPS = 1.5
#: 折线拼链的最大跳数。2026-10-15 由 8 提到 64：原值会把长路截断
#: （实测：1.9 km 的「吉庆大道」只链出 607 m、「鼎湖大道」只链出 35 m）
CHAIN_MAX_HOPS = 64
#: 无街名链的「别拐太狠」阈值（度）。无名边没有街名可依据，只能靠转角防止在路口乱拐串成假路
CHAIN_TURN_MAX_DEG = 75.0
#: 短于此长度的链视为**路口接头碎片**，不成段（实测原实现会把 3.6 m / 4.1 m 的接头当"站区连接线"）
MIN_SEG_LEN_M = 30.0
#: 只收站区范围内的链（米）。读登记表的 range_m（IKM4B4：不再写死全站共用一个常数）
STATION_RADIUS_M = float(_SITE["range_m"])
SEED = 42

app = FastAPI(title="hubflow twin preview", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


def _local_iso() -> str:
    off = datetime.now().astimezone().utcoffset()
    minutes = int(off.total_seconds() // 60) if off else 0
    sign = "+" if minutes >= 0 else "-"
    minutes = abs(minutes)
    now = datetime.now()
    return (
        f"{now:%Y-%m-%dT%H:%M:%S}"
        f"{sign}{minutes // 60:02d}:{minutes % 60:02d}"
    )


def _envelope(payload: dict) -> JSONResponse:
    body = {"is_simulated": True, **payload}
    return JSONResponse(body, headers={"Cache-Control": "no-store"})


# ---------- 路段选择与折线 ----------

def _section_key(edge_id: str) -> str:
    # 无向截面键:去方向前缀,保留 # 分段后缀(#0/#1 是不同物理段,不能合并)
    return edge_id.lstrip("-")


def _turn_deg(a, b, c) -> float:
    """a→b→c 的转角（度）。0 = 直行。"""
    v1 = (b[0] - a[0], b[1] - a[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 < 1e-9 or n2 < 1e-9:
        return 0.0
    cos = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(cos))


def _shape_len(shape) -> float:
    """折线长度（米）。"""
    return sum(math.dist(shape[i - 1], shape[i]) for i in range(1, len(shape)))


def _chain_starts(edges: list, *, same_name: bool) -> list:
    """挑「链头」= 组内没有**同向前驱**的边。

    从链中间起走会把一条路切成好几段（原实现每个街名只从"离站最近"那条边起走，
    正是把 1.9 km 的吉庆大道截成 607 m 的原因之一）。
    """
    out = []
    for e in edges:
        sign = e.getID().startswith("-")
        key = _section_key(e.getID())
        has_pred = False
        for p in e.getFromNode().getIncoming():
            if p.getID() == e.getID() or not p.allows("passenger"):
                continue
            if p.getID().startswith("-") != sign:
                continue
            if same_name and p.getName() != e.getName():
                continue
            if not same_name and p.getName():
                continue
            if _section_key(p.getID()) == key:
                continue
            has_pred = True
            break
        if not has_pred:
            out.append(e)
    return out


def _walk_chain(start, *, same_name: bool) -> tuple[list, list[str]]:
    """从 `start` 往前走，拼一条**极大链**折线，返回 (shape, edge_ids)。

    · `same_name=True`：只沿**同名、同向**边延伸（命名道路的口径）；
    · `same_name=False`：无名边没有街名可依据，改用**转角 ≤ CHAIN_TURN_MAX_DEG** 防止在路口乱拐；
    两种情况都在候选里取**转角最小**的那条（最直 = 最像同一条路的延续）。

    与 2026-10-15 前的原实现的三点不同：跳数 8→`CHAIN_MAX_HOPS`；加 `visited` 防环
    （环形路网下原实现会来回绕、把同一条边重复拼进折线）；候选从"第一条"改为"最直的一条"。
    """
    sign = start.getID().startswith("-")
    name = start.getName()
    shape = list(start.getShape())
    edge_ids = [start.getID()]
    visited = {start.getID()}
    cur = start
    for _ in range(CHAIN_MAX_HOPS):
        best = None  # (转角, edge)
        for cand in cur.getToNode().getOutgoing():
            cid = cand.getID()
            if cid == cur.getID() or cid in visited or not cand.allows("passenger"):
                continue
            if cid.startswith("-") != sign:
                continue
            pts = cand.getShape()
            if same_name:
                if cand.getName() != name:
                    continue
            else:
                # 无名边：不许接上命名道路，也不许拐太狠
                if cand.getName():
                    continue
            turn = (
                _turn_deg(shape[-2], shape[-1], pts[1])
                if len(shape) >= 2 and len(pts) >= 2
                else 0.0
            )
            if not same_name and turn > CHAIN_TURN_MAX_DEG:
                continue
            if best is None or turn < best[0]:
                best = (turn, cand)
        if best is None:
            break
        nxt = best[1]
        pts = nxt.getShape()
        shape.extend(pts[1:] if shape and shape[-1] == pts[0] else pts)
        edge_ids.append(nxt.getID())
        visited.add(nxt.getID())
        cur = nxt
    return shape, edge_ids


def _slice_shape(shape, d0: float, d1: float) -> list:
    """取折线上累计里程 [d0, d1] 的一段（两端按线性插值），用于把长路段按里程切开。"""
    out: list = []
    acc = 0.0
    for i in range(1, len(shape)):
        p0, p1 = shape[i - 1], shape[i]
        seg = math.dist(p0, p1)
        a, b = acc, acc + seg
        acc = b
        if seg <= 1e-9 or b < d0 or a > d1:
            continue
        if not out:
            if d0 <= a:
                out.append(p0)
            else:
                t = (d0 - a) / seg
                out.append((p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t))
        if d1 < b:
            t = (d1 - a) / seg
            out.append((p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t))
            break
        out.append(p1)
    return out


def _split_chain(chain: dict, edge_by_id: dict) -> list:
    """把一条链按**里程对半**切成两段。

    边的归段方式：先算出「前半段拿到几条边」的分界下标 `k`，两段各取 `edge_ids[:k]` /
    `edge_ids[k:]` —— 保证**同一条边不会同时落进两段**（`edge2seg` 是"边 → 段"的单值映射，
    重复归属会让车辆落到哪一段取决于写入顺序）。

    ⚠️ **不能按"每条边的中点各自判 `< mid` / `>= mid`"逐条筛**：折线长度与边长之和**不相等**
    —— 链在路口跳过 SUMO 内部边（`_walk_chain` 把那段空隙用直线连起来，实测每跳 +9~15 m），
    13 条边的链折线比边长之和长 169 m。于是会出现「所有边的中点都落在 mid 同一侧」，
    逐条筛就让一段**一条边都拿不到**（2026-10-15 实测：`--seg-count 12/14` 时两段共用
    完全相同的 `edge_ids`，`edge2seg` 后写覆盖先写，一半路段永远收不到车）。

    单边链（`len(edge_ids) < 2`）**不拆**：拆了必然两段共用同一条边 —— 返回空表让调用方换一条。
    """
    edge_ids = list(chain["edge_ids"])
    if len(edge_ids) < 2:
        return []
    total = chain["length_m"]
    mid = total / 2

    # 分界下标 k = 中点落在前半段的边数，夹在 [1, n-1]：两段都非空、且不重叠
    centres, acc = [], 0.0
    for eid in edge_ids:
        edge = edge_by_id.get(eid)
        elen = edge.getLength() if edge is not None else 0.0
        centres.append(acc + elen / 2)
        acc += elen
    k = sum(1 for centre in centres if centre < mid)
    k = max(1, min(len(edge_ids) - 1, k))

    parts = []
    for lo, hi, half in ((0.0, mid, edge_ids[:k]), (mid, total, edge_ids[k:])):
        sub = _slice_shape(chain["shape"], lo, hi)
        if len(sub) < 2:
            # 几何切不出来（退化链）→ 整条不拆，交给调用方换下一条；**不许**退化成"两段共用整链的边"
            return []
        parts.append(
            {
                "name": chain["name"],
                "kind": chain["kind"],
                "shape": sub,
                "edge_ids": list(half),
                "length_m": _shape_len(sub),
            }
        )
    return parts


def select_segments(net, station_lonlat: tuple[float, float], seg_count: int) -> list:
    """按**真实道路链**选段：命名道路取整条链，无街名道路按连通性拼链，再按链长择优。

    ⚠️ **这条路依赖街名与站房位置** —— 换一张无名 / 无地理配准的网就会失效。
    这类网请用 `--assignment` 直接给映射表（见 `load_assignment`）。

    口径（2026-10-15 修；**原实现会把路口接头碎片当成路段**）：
      · 原实现：每个街名只取「离站最近的那一条链」，再用**离站最近的单条无街名边**补足到
        `seg_count` —— 而离站最近的无街名边恰是路口接头。实测后果：10 条"路段"里 8 条是碎片
        （3.6 m / 4.1 m / 24 m / 28 m…），1.9 km 的「吉庆大道」被截成 607 m、
        757 m 的「鼎湖大道」被截成 35 m，全网只跨 340 m × 600 m。
      · 现实现：① 把可通行边拼成**极大链**；② **每个街名只留最长的那条链**（一条路一条段 ——
        双向车道在 SUMO 里是**两条边 ID 完全不同的独立边**，按截面键认不出，只能按街名合并；
        不合并的话「吉庆大道」会画两遍、白占两个名额）；③ 无名链按**截面键不相交**贪心去重
        （反向重复与同簇分支都会因此被剔除）；④ 剔掉 < `MIN_SEG_LEN_M` 的接头碎片与超出
        `STATION_RADIUS_M` 的链；⑤ **段数不够就把最长的段按里程对半拆**——宁可拆真实长路，
        也不再拿接头碎片凑数；拆出来的两段**不共享边**（单边链不拆，见 `_split_chain`）。

    拆段后同一路名会出现两次（如「吉庆大道」两段）：这是**同一路名的两个监测段**，靠
    `segment_id` 区分，与交通系统里"长路分段监测"是同一回事。
    """
    station_xy = net.convertLonLat2XY(*station_lonlat)

    def min_dist(shape) -> float:
        return min(math.dist(p, station_xy) for p in shape)

    passenger = [e for e in net.getEdges() if e.allows("passenger")]
    edge_by_id = {e.getID(): e for e in passenger}
    named_groups: dict[str, list] = {}
    unnamed: list = []
    for e in passenger:
        if e.getName():
            named_groups.setdefault(e.getName(), []).append(e)
        else:
            unnamed.append(e)

    # ① + ② 命名道路：每条路取**最长**的极大链（合并双向车道，一条路只留一段）
    picked: list[dict] = []
    for name, edges in named_groups.items():
        best = None
        for start in _chain_starts(edges, same_name=True):
            shape, ids = _walk_chain(start, same_name=True)
            length = _shape_len(shape)
            if best is None or length > best["length_m"]:
                best = {"name": name, "kind": "main", "shape": shape, "edge_ids": ids, "length_m": length}
        if best is not None:
            picked.append(best)

    # ③ + ④ 无名道路：极大链按长度降序贪心，截面键不相交（反向重复/同簇分支自然出局）
    candidates: list[dict] = []
    for start in _chain_starts(unnamed, same_name=False):
        shape, ids = _walk_chain(start, same_name=False)
        candidates.append(
            {"name": "", "kind": "ramp", "shape": shape, "edge_ids": ids, "length_m": _shape_len(shape)}
        )
    candidates.sort(key=lambda c: -c["length_m"])
    used: set[str] = set(_section_key(eid) for c in picked for eid in c["edge_ids"])
    for c in candidates:
        if c["length_m"] < MIN_SEG_LEN_M or min_dist(c["shape"]) > STATION_RADIUS_M:
            continue
        keys = {_section_key(eid) for eid in c["edge_ids"]}
        if keys & used:
            continue
        used |= keys
        picked.append(c)

    # ⑤ 段数不够：拆最长的段（按里程对半），直到凑够 seg_count
    # 拆不动的链（单边链 / 几何退化）记在这里，换下一条试 —— 不能 break，否则一条拆不动
    # 就把后面还能拆的全放弃了；也不能反复挑同一条，否则死循环。
    unsplittable: set[tuple] = set()
    while len(picked) < seg_count:
        if not picked:
            # 一条都没选出来（无名 / 无地理配准的网就会出现：没有街名可分组，无名链又全被
            # 长度/半径过滤掉）。这里给**可执行的报错**，不要落到 `max()` 空序列的 ValueError
            # ——那会让整条预览只报一句看不懂的错。返回空表也不行：下游
            # `pick_drop_segment()` 会对空列表 `min()`。
            raise RuntimeError(
                "启发式选段一条都没选出来：这张网既没有可用的街名分组，无名链也全部短于 "
                f"{MIN_SEG_LEN_M:.0f} m 或超出 {STATION_RADIUS_M:.0f} m。"
                "这类「无名 / 无地理配准」的网请改用 `--assignment <映射表>`（见 README）。"
            )
        cands = [c for c in picked if tuple(c["edge_ids"]) not in unsplittable]
        if not cands:
            break
        longest = max(cands, key=lambda c: c["length_m"])
        if longest["length_m"] < 2 * MIN_SEG_LEN_M:
            break  # 连对半拆都不够长，不再硬凑（少几段好过塞接头碎片）
        parts = _split_chain(longest, edge_by_id)
        if not parts:
            unsplittable.add(tuple(longest["edge_ids"]))
            continue
        picked.remove(longest)
        picked.extend(parts)

    # 主干在前，其余按长度降序
    picked.sort(key=lambda c: (0 if c["kind"] == "main" else 1, -c["length_m"]))
    picked = picked[:seg_count]

    segs = []
    letter = 0
    for i, s in enumerate(picked, start=1):
        name = s["name"]
        if not name:
            # 无名道路：沿用既有占位名。**确实拿不到真实街名，就不编一个**
            name = f"站区连接线{chr(ord('A') + letter)}"
            letter += 1
        coords = [
            [round(v, 6) for v in net.convertXY2LonLat(x, y)] for x, y in s["shape"]
        ]
        segs.append(
            {
                "segment_id": f"SEG-{i:03d}",
                "name": name,
                "kind": s["kind"],
                "coords": coords,
                "edge_ids": s["edge_ids"],
                "shape_xy": [tuple(p) for p in s["shape"]],
            }
        )
    return segs


def pick_drop_segment(net, segs: list, station_lonlat: tuple[float, float]) -> dict:
    """落客段 = 离站房最近的站区连接线(ramp);没有则取最近路段。**有映射表时整条不走**。"""
    station_xy = net.convertLonLat2XY(*station_lonlat)

    def dist(seg):
        return min(math.dist(p, station_xy) for p in seg["shape_xy"])

    ramps = [s for s in segs if s["kind"] == "ramp"]
    return min(ramps or segs, key=dist)


# ---------- 仿真线程 ----------

class SimState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.segments: list = []
        self.vehicles: list = []
        self.sim_time = 0.0
        self.error: str | None = None


def _nearest_segment(xy, segs: list) -> str:
    best, best_d = segs[0]["segment_id"], float("inf")
    for seg in segs:
        for point in seg["shape_xy"]:
            d = math.dist(xy, point)
            if d < best_d:
                best, best_d = seg["segment_id"], d
    return best


def _read_vehicles(net, edge2seg: dict, segs: list, driver_of: dict) -> list:
    out = []
    for vid in traci.vehicle.getIDList():
        try:
            xy = traci.vehicle.getPosition(vid)
            lon, lat = net.convertXY2LonLat(*xy)
            speed = traci.vehicle.getSpeed(vid)
            edge = traci.vehicle.getRoadID(vid)
            stopped = bool(traci.vehicle.getStopState(vid) & 1)
            if stopped:
                state = "落客服务"
            elif speed < QUEUE_SPEED_MPS:
                state = "排队"
            else:
                state = "行驶"
            out.append(
                {
                    "vehicle_id": vid,
                    "driver_type": driver_of.get(vid, "D2"),
                    "segment_id": edge2seg.get(edge) or _nearest_segment(xy, segs),
                    "offset_m": round(traci.vehicle.getLanePosition(vid)),
                    "lon": round(lon, 6),
                    "lat": round(lat, 6),
                    "state": state,
                    "guided": False,
                    "is_demo_bound": False,
                }
            )
        except traci.TraCIException:
            continue  # 车辆恰好离开路网
    return out


def run_sim(state: SimState, cfg: BridgeConfig) -> None:
    # 整个线程体包进 try:路网缺失/TraCI 起不动都要落 state.error(health 显式报),不让前端猜
    rng = random.Random(SEED)
    driver_of: dict[str, str] = {}
    seq = 0
    try:
        net = sumolib.net.readNet(str(cfg.net_file))
        if cfg.assignment_file:
            # **有映射表就不再从路网里猜** —— 换一张网只换这张表;代码里没有任何站点分支
            segs, drop_id = load_assignment(cfg.assignment_file, net)
            drop = next((s for s in segs if s["segment_id"] == drop_id), None)
            if drop is None:
                # **不许静默回退 segs[0]**——映射表写错一个字必须当场暴露（落 state.error,health 显式报）
                raise ValueError(
                    f"映射表里 drop_segment_id={drop_id!r} 在 segments 里找不到；"
                    f"可用的是 {[s['segment_id'] for s in segs]}"
                )
        else:
            # 老路子:靠街名 + 站房位置猜(只适用于 OSM 衍生的有名字、有地理配准的网)
            segs = select_segments(net, cfg.station_lonlat, cfg.seg_count)
            drop = pick_drop_segment(net, segs, cfg.station_lonlat)
        drop_edge = drop["edge_ids"][0]

        edge2seg: dict[str, str] = {}
        seg_edges: list[str] = []
        for seg in segs:
            for edge_id in seg["edge_ids"]:
                edge2seg[edge_id] = seg["segment_id"]
                seg_edges.append(edge_id)

        with state.lock:
            state.segments = [
                {k: seg[k] for k in ("segment_id", "name", "kind", "coords")} for seg in segs
            ]

        traci.start(
            [
                sumolib.checkBinary("sumo"),
                "-n", str(cfg.net_file),
                "--no-step-log", "1",
                "--duration-log.disable", "1",
                "--ignore-route-errors", "true",
                "--time-to-teleport", "240",
                "--seed", str(SEED),
            ]
        )
        while True:
            traci.simulation.step()
            state.sim_time = traci.simulation.getTime()

            alive = len(traci.vehicle.getIDList())
            pending = len(traci.simulation.getPendingVehicles())
            if alive + pending < MAX_VEHICLES and pending < MAX_PENDING and rng.random() < SPAWN_PROBABILITY:
                frm = rng.choice(seg_edges)
                driver = "D1" if rng.random() < 0.6 else "D2"
                to = drop_edge if driver == "D1" else rng.choice(seg_edges)
                if frm != to:
                    stage = traci.simulation.findRoute(frm, to)
                    route = list(stage.edges)
                    if route:
                        seq += 1
                        veh_id = f"twin-{seq:04d}"
                        route_id = f"r{seq:04d}"
                        traci.route.add(route_id, route)
                        traci.vehicle.add(veh_id, route_id)
                        if driver == "D1":
                            traci.vehicle.setStop(veh_id, drop_edge, duration=DROP_STOP_S)
                        driver_of[veh_id] = driver

            vehicles = _read_vehicles(net, edge2seg, segs, driver_of)
            with state.lock:
                state.vehicles = vehicles
            time.sleep(STEP_S)
    except Exception as exc:
        with state.lock:
            state.error = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            traci.close()
        except Exception:
            pass


state = SimState()
#: 运行配置 —— 由 `parse_args()` 在 `__main__` 里填；不走命令行时即默认值（**向后兼容**）
CONFIG = BridgeConfig()


@app.get("/api/twin/health")
def health() -> JSONResponse:
    with state.lock:
        return _envelope(
            {
                "status": "error" if state.error else "ok",
                "sim_time_s": round(state.sim_time, 1),
                "vehicles": len(state.vehicles),
                **({"error": state.error} if state.error else {}),
            }
        )


@app.get("/api/twin/network")
def network() -> JSONResponse:
    # note 由配置生成（站点名 / 网名都不写死在代码里 —— 手册 §8.4 / M1-1 口径）
    label = CONFIG.site_name or CONFIG.net_file.name
    with state.lock:
        return _envelope(
            {
                "note": f"{label} · SUMO 仿真演示（演示数据（模拟））· 正式路网归 #36/#37",
                "segments": state.segments,
            }
        )


@app.get("/api/twin/vehicles")
def vehicles() -> JSONResponse:
    with state.lock:
        return _envelope({"ts": _local_iso(), "vehicles": state.vehicles})


def parse_args(argv: list[str] | None = None) -> BridgeConfig:
    """命令行参数 —— **换站 / 换网只改配置或参数，不改代码，也不加任何站点分支**。"""
    parser = argparse.ArgumentParser(description="twin_preview：SUMO TraCI 小仿真 → 车辆真值")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH),
                        help="站点范围登记表（默认 work/twin/site-ranges.json）")
    parser.add_argument("--site-id", default=None,
                        help="登记表里的 site_id（缺省取 default_site）")
    parser.add_argument("--net", default=str(DEFAULT_NET_FILE), dest="net_file",
                        help="SUMO 路网 .net.xml（默认：本目录的 station.net.xml）")
    parser.add_argument("--assignment", default="", dest="assignment_file",
                        help="「SEG → SUMO 边链」映射表 JSON；**给了它就不再从路网里猜路段**"
                             "（无名路 / 无地理配准的网必须给）")
    parser.add_argument("--station-lonlat", default="",
                        dest="station_lonlat", help="站房锚点「经度,纬度」（缺省取登记表）")
    parser.add_argument("--seg-count", type=int, default=0, dest="seg_count",
                        help="不给映射表时，路段数补足到几条（缺省取登记表 bridge_seg_count）")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"默认 {DEFAULT_PORT}；二站可换 8103 好两站同时开")
    parser.add_argument("--site-name", default="", dest="site_name",
                        help="展示用站点名（缺省取登记表 site_name）")
    ns = parser.parse_args(argv)

    site = load_site(ns.site_id, Path(ns.config))
    global STATION_RADIUS_M
    STATION_RADIUS_M = float(site["range_m"])
    station_lonlat = ns.station_lonlat or ",".join(str(v) for v in site["anchor_lonlat"])
    lon, lat = (float(v) for v in str(station_lonlat).split(","))
    seg_count = ns.seg_count or int(site.get("bridge_seg_count", DEFAULT_SEG_COUNT))
    return BridgeConfig(
        net_file=Path(ns.net_file),
        assignment_file=Path(ns.assignment_file) if ns.assignment_file else None,
        station_lonlat=(lon, lat),
        seg_count=seg_count,
        host=ns.host,
        port=ns.port,
        site_name=ns.site_name or str(site.get("site_name", "")),
    )


if __name__ == "__main__":
    import uvicorn

    CONFIG = parse_args()
    print(f"[twin_preview] 路网 {CONFIG.net_file.name}"
          f"｜映射表 {CONFIG.assignment_file.name if CONFIG.assignment_file else '(无,走启发式)'}"
          f"｜{CONFIG.host}:{CONFIG.port}")
    threading.Thread(target=run_sim, args=(state, CONFIG), daemon=True).start()
    uvicorn.run(app, host=CONFIG.host, port=CONFIG.port, log_level="warning")
