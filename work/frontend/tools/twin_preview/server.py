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

#: 默认门牌（**向后兼容**：不传参数就是原来那一套，不是给某个站加的分支）
DEFAULT_NET_FILE = DIR / "station.net.xml"
#: 默认站房锚点（经纬度）——仅**启发式选路段**那条路用；有映射表时完全不读它
DEFAULT_STATION_LONLAT = (112.6551321, 23.2166791)
DEFAULT_SEG_COUNT = 10
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
CHAIN_MAX_HOPS = 8
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


def _chain_shape(edge) -> tuple[list, list[str]]:
    """沿同名、同方向、可通行的截面链延伸,拼出整条路折线(限跳数防岔路失控)。"""
    sign = edge.getID().startswith("-")
    name = edge.getName()
    shape = list(edge.getShape())
    edge_ids = [edge.getID()]
    cur = edge
    for _ in range(CHAIN_MAX_HOPS):
        nxt = None
        for cand in cur.getToNode().getOutgoing():
            if cand.getID() == cur.getID() or not cand.allows("passenger"):
                continue
            if cand.getName() != name or cand.getID().startswith("-") != sign:
                continue
            nxt = cand
            break
        if nxt is None:
            break
        pts = nxt.getShape()
        shape.extend(pts[1:] if shape and shape[-1] == pts[0] else pts)
        edge_ids.append(nxt.getID())
        cur = nxt
    return shape, edge_ids


def select_segments(net, station_lonlat: tuple[float, float], seg_count: int) -> list:
    """主干每条路取一条方向链(离站最近),站区未命名连接线按到站距离补足到 seg_count。

    ⚠️ **这条路依赖街名与站房位置** —— 换一张无名 / 无地理配准的网就会失效。
    这类网请用 `--assignment` 直接给映射表（见 `load_assignment`）。
    """
    station_xy = net.convertLonLat2XY(*station_lonlat)

    def min_dist(shape) -> float:
        return min(math.dist(p, station_xy) for p in shape)

    picked: list[dict] = []  # {name, kind, shape, edge_ids}
    used_keys: set[str] = set()

    named: dict[str, list] = {}
    for e in net.getEdges():
        if e.allows("passenger") and e.getName():
            named.setdefault(e.getName(), []).append(e)
    for name, edges in named.items():
        best = None
        for e in edges:
            shape, ids = _chain_shape(e)
            d = min_dist(shape)
            if best is None or d < best[0]:
                best = (d, {"name": name, "kind": "main", "shape": shape, "edge_ids": ids})
        if best:
            picked.append(best[1])
            for eid in best[1]["edge_ids"]:
                used_keys.add(_section_key(eid))

    ramps: list[tuple[float, object]] = []
    for e in net.getEdges():
        if e.allows("passenger") and not e.getName() and _section_key(e.getID()) not in used_keys:
            ramps.append((min_dist(e.getShape()), e))
    ramps.sort(key=lambda t: t[0])
    letter = 0
    for _, e in ramps:
        if len(picked) >= seg_count:
            break
        key = _section_key(e.getID())
        if key in used_keys:
            continue
        used_keys.add(key)
        picked.append(
            {
                "name": f"站区连接线{chr(ord('A') + letter)}",
                "kind": "ramp",
                "shape": list(e.getShape()),
                "edge_ids": [e.getID()],
            }
        )
        letter += 1

    picked = picked[:seg_count]
    picked.sort(key=lambda s: 0 if s["kind"] == "main" else 1)

    segs = []
    for i, s in enumerate(picked, start=1):
        coords = [
            [round(v, 6) for v in net.convertXY2LonLat(x, y)] for x, y in s["shape"]
        ]
        segs.append(
            {
                "segment_id": f"SEG-{i:03d}",
                "name": s["name"],
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
    """命令行参数 —— **换站 / 换网只改参数，不改代码，也不加任何站点分支**。"""
    parser = argparse.ArgumentParser(description="twin_preview：SUMO TraCI 小仿真 → 车辆真值")
    parser.add_argument("--net", default=str(DEFAULT_NET_FILE), dest="net_file",
                        help="SUMO 路网 .net.xml（默认：本目录的 station.net.xml）")
    parser.add_argument("--assignment", default="", dest="assignment_file",
                        help="「SEG → SUMO 边链」映射表 JSON；**给了它就不再从路网里猜路段**"
                             "（无名路 / 无地理配准的网必须给）")
    parser.add_argument("--station-lonlat", default=",".join(map(str, DEFAULT_STATION_LONLAT)),
                        dest="station_lonlat", help="站房锚点「经度,纬度」——只在不给映射表时用于挑路段")
    parser.add_argument("--seg-count", type=int, default=DEFAULT_SEG_COUNT, dest="seg_count",
                        help="不给映射表时，路段数补足到几条")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"默认 {DEFAULT_PORT}；二站可换 8103 好两站同时开")
    parser.add_argument("--site-name", default="", dest="site_name",
                        help="展示用站点名（可空；不填就用路网文件名）")
    ns = parser.parse_args(argv)
    lon, lat = (float(v) for v in str(ns.station_lonlat).split(","))
    return BridgeConfig(
        net_file=Path(ns.net_file),
        assignment_file=Path(ns.assignment_file) if ns.assignment_file else None,
        station_lonlat=(lon, lat),
        seg_count=ns.seg_count,
        host=ns.host,
        port=ns.port,
        site_name=ns.site_name,
    )


if __name__ == "__main__":
    import uvicorn

    CONFIG = parse_args()
    print(f"[twin_preview] 路网 {CONFIG.net_file.name}"
          f"｜映射表 {CONFIG.assignment_file.name if CONFIG.assignment_file else '(无,走启发式)'}"
          f"｜{CONFIG.host}:{CONFIG.port}")
    threading.Thread(target=run_sim, args=(state, CONFIG), daemon=True).start()
    uvicorn.run(app, host=CONFIG.host, port=CONFIG.port, log_level="warning")
