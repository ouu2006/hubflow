"""work/engine 模块统一入口(开发规范 §3 / §6:每个模块一个 run.py,加 --sample 能单独跑)。

输入:`work/engine/samples/` 的样例(网络 / 现状 / OD)+ `stations/thresholds.json` 的 decision 组
输出:`work/engine/out/routes.json`(推荐 + 备选)+ `out/run_log.json`
口径:
  - `--sample` **不依赖上游、不依赖 SUMO**,读样例写 out/,**不许覆盖样例输入**;
  - **样例数据走 `samples/`,参数走 `stations/`** —— 后者是"引擎真的读了站点包"的证明点
    (改 `alpha` 一个数,产物 `eta` 跟着动);
  - `--sample` 单独跑 = 手册 §7.6 的**对照组基线("此刻最快")**:按 BPR 选对本车最快的路线,
    **不接**时段预约 / 不伤害前车 / 再疏导,因此 `reservation` 恒为 `null`,
    **绝不编一个 `passed: true` 出来**(这条基线行为被 DESIGN.md 与多条判定引用,不许改);
  - `--sample --compare` = 同一份输入跑三组对照并在 `reservation` 里给出真实预约结果:
    ① 不推荐(自由流习惯路线) ② 此刻最快(即上一条的普通导航口径) ③ 协同推荐
    (时段容量预约 + 不伤害前车约束 + 前车再疏导),输出 TC-17 三项对比数据;
    预约 / 租约 / 再疏导的机制见 reserve.py 与 reroute.py。

用法:
  python work/engine/run.py --sample              # 对照组基线(此刻最快)
  python work/engine/run.py --sample --compare    # ①不推荐 / ②此刻最快 / ③协同推荐 三组对照
  python work/engine/run.py --sample --out /tmp/x --samples ... --stations ...
  python work/engine/run.py --network real        # 真网(站点登记表:段号前缀/段数)协同推荐,写 out/real/,**不动样例 out/**
  python work/engine/run.py --network real --compare   # 真网三组对照(TC-17 数据),写 out/real/compare/
  python work/engine/run.py --network real --site-id <登记表里的 site_id> --segments <上游 segments 快照路径>
  # 站点/真网路径由 work/twin/site-ranges.json 登记表决定(不写死在代码里);换站只改登记表 + --site-id
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

import candidates
import network
import realnet
import reserve
import reroute

HERE = Path(__file__).resolve().parent
DEFAULT_SAMPLES_DIR = HERE / "samples"
DEFAULT_OUT_DIR = HERE / "out"
#: 站点包在仓库根:`work/engine/` → `work/` → 仓库根 → `stations/`
DEFAULT_STATIONS_DIR = HERE.parents[1] / "stations"
#: 真网站点范围登记表(每站一份:seg_target / seg_prefix / out_json);引擎只读不写
DEFAULT_SITE_RANGES = realnet.DEFAULT_SITE_RANGES
#: 真网产物默认输出目录:与样例 out/ **分开**,不覆盖样例基线
DEFAULT_REAL_OUT_DIR = DEFAULT_OUT_DIR / "real"
#: 真网 `--compare` 产物目录:与真网默认模式**再分开** —— 两种 mode 的 routes.json 不能共用一个路径,
#: 否则后跑覆盖前者,下游按固定路径读取时会拿到错 mode 的产物(IKMS11 独立审查发现 1)
DEFAULT_REAL_COMPARE_OUT_DIR = DEFAULT_REAL_OUT_DIR / "compare"

SAMPLE_FILES = {
    "network": "network_sample.json",
    "segments": "segments_sample.json",
    # 与 stations/demand.json 同形:OD 数组的容器键就是 od(开发规范 §6「样例就是契约的镜子」)
    "demand": "demand_sample.json",
}

#: `--sample` 产物信封说明(逐字节基线的一部分,不许改)
SAMPLE_ROUTES_SCHEMA_NOTE = (
    "每个 requests[] 元素就是 POST /api/traffic/route/recommend 的响应体形状"
    "(契约第二节);这里包一层信封是为了让 --sample 一次跑完 ≥3 个 OD 对(M1-4 前置)"
)
#: `--sample --compare` 产物信封说明(逐字节基线的一部分,不许改)
COMPARE_ROUTES_SCHEMA_NOTE = (
    "requests[] 每个元素就是 POST /api/traffic/route/recommend 的响应体形状(契约第二节);"
    "每个 OD 取一辆代表车(优先取被再疏导的车):arrival_route 是该车登记时的原始推荐,"
    "reroute 是评估期内它的最后再疏导状态。comparison 块是 --compare 的对照产物"
    "(① 不推荐 / ② 此刻最快 / ③ 协同推荐),不属于单次响应体,接口层不透出。"
)
#: `--sample --compare` 的对照场景说明(逐字节基线的一部分,不许改)
COMPARE_SCENARIO_NOTE = (
    "① 与 ② 在样例数据上路线恰好一致(自由流最短路 = BPR 快照最快),"
    "所以两组指标相同 —— 这是数据事实,不是复制粘贴;② 与 ③ 的差异才是协同机制的效果"
)
#: `--sample --compare` 的共同车辆群说明(逐字节基线的一部分,不许改)
COMPARE_GUIDED_COMMON_NOTE = (
    "只统计被引导车辆自身 ETA(不含背景车流),按 TC-17 评测协议的共同车辆群口径;"
    "样例路网上两组差异很小(被逼绕行的 OD-02 与避开的拥堵基本抵消),单列作参考"
)
#: 真网(非样例)产物信封说明（IKNC4J：段号前缀按站点登记表现取，不写死 SZ-###）
def real_routes_schema_note(seg_prefix: str, site_name: str = "") -> str:
    prefix = f"{seg_prefix}-###" if seg_prefix else "<seg_prefix>-###"
    where = f"{site_name} 真网" if site_name else "真网"
    return (
        f"{where} routes:requests[] 每个元素就是 POST /api/traffic/route/recommend 的响应体形状"
        f"(契约第二节);段号全部来自真网命名空间({prefix}),路线对象额外带 length_m 可回溯到 "
        "network.segments[] 的逐段长度;network / od_derivation / segments_source 三块是可追溯元数据,"
        "不属于单次响应体,接口层不透出"
    )
#: 真网 `--compare` 的对照场景说明
REAL_COMPARE_SCENARIO_NOTE = (
    "① 不推荐 / ② 此刻最快 / ③ 协同推荐在同一份真网拓扑、同一份 segments 输入、"
    "同一车辆群上跑;三组差异只来自推荐机制,不按数据 source 分支"
)
#: 真网 `--compare` 的共同车辆群说明
REAL_COMPARE_GUIDED_COMMON_NOTE = (
    "只统计被引导车辆自身 ETA(不含背景车流),按 TC-17 评测协议的共同车辆群口径;"
    "真网拓扑上两组路线差异见 comparison.groups"
)

#: 样例用的固定请求参数(demo;真值由接口层给)
SAMPLE_DRIVER_TYPE = "D1"
SAMPLE_PARKING_MODE = "S2"
#: 到站步行时间(demo 假设值,【待标定】)
SAMPLE_WALK_MIN = 2.0

#: 终点节点类型 → 司机类型(契约第四节 D1 送客 / D2 接客 / D3 往返)
#: 按**终点类型**推,不再一律 D1 —— 否则上客行程会被描述成落客(见 Issue #94 第②条)。
#: D3(往返)在样例里没有,不处理;终点是路口等其它类型时退回默认 D1。
DRIVER_TYPE_BY_STOP = {"dropoff": "D1", "pickup": "D2"}


def load_points(stations_dir: Path) -> list[dict[str, Any]]:
    """读站点包 `stations/points.json` 的点位表(取 `point_id` / `type` / `segment_id`)。

    引擎里**不许出现站点相关的字符串常量**(换站只换数据),所以点位一律从这里查。
    """
    path = stations_dir / "points.json"
    if not path.is_file():
        raise SystemExit(f"缺站点包点位表:{path}(--sample 要用它把终点折成点位 id)")
    payload = network.read_json(path)
    points = payload.get("points")
    if not isinstance(points, list) or not points:
        raise ValueError("points.json 缺 points 数组(契约第六节)")
    return points


def _adjacent_sections(
    graph: network.Graph,
    node_id: str,
    path: list[str],
) -> set[str]:
    """节点处的"相邻路段"口径(DESIGN.md 十二节):到达路径经过的边的 `section` +
    该节点所有出边的 `section` —— 落客/上客点可能登记在驶离该节点的那条路上。"""
    sections = {str(graph.edge(eid).get("section")) for eid in path}
    for edge_id in graph.out_edges(node_id):
        sections.add(str(graph.edge(edge_id).get("section")))
    return sections


def stop_point_of(
    points: list[dict[str, Any]],
    graph: network.Graph,
    node_id: str,
    path: list[str],
) -> dict[str, Any] | None:
    """终点节点对应的落客 / 上客点位(按 `type` + 相邻路段的 `segment_id` 查表)。

    - **不退回图节点 id**:查不到就返回 None,由调用方在 `why` 里写明"点位未在站点包登记";
    - 匹配范围是**终点节点的相邻路段**(入边 + 出边)的 `section`,不是单看最后一条边 ——
      点位可能登记在驶离该节点的那条路上(如样例的 `P-02` 挂在 `SEG-004`,而到达走的是 `SEG-003`);
    - `path` 为空或终点不是落客 / 上客型节点时返回 None。
    """
    node_type = graph.node(node_id).get("type")
    if node_type not in DRIVER_TYPE_BY_STOP:
        return None

    sections = _adjacent_sections(graph, node_id, path)
    for point in points:
        if point.get("type") == node_type and str(point.get("segment_id")) in sections:
            return point
    return None


def pickup_point_for_d3(
    points: list[dict[str, Any]],
    graph: network.Graph,
    node_id: str,
    path: list[str],
) -> dict[str, Any] | None:
    """D3 上客点(TC-12):`type == "pickup"` 的点位里,选登记在**到达终点相邻路段**上的那个。

    与 `stop_point_of()` 同一套"相邻路段"口径(`_adjacent_sections`),但不按终点节点类型
    收窄 —— D3 的到达终点可以是路口等任意类型。候选按 `point_id` 升序排序保证确定性;
    查不到返回 None(调用方跳过该 OD 的 D3 请求并留痕,不按坐标凑点)。
    """
    sections = _adjacent_sections(graph, node_id, path)
    candidates = sorted(
        (point for point in points if str(point.get("type")) == "pickup"),
        key=lambda point: str(point.get("point_id")),
    )
    for point in candidates:
        if str(point.get("segment_id")) in sections:
            return point
    return None


def load_samples(samples_dir: Path) -> dict[str, dict[str, Any]]:
    """读 --sample 用的三份样例(缺失即报错,不静默降级)。"""
    payloads: dict[str, dict[str, Any]] = {}
    for key, name in SAMPLE_FILES.items():
        path = samples_dir / name
        if not path.is_file():
            raise SystemExit(f"缺样例文件:{path}(--sample 需要 samples/ 下三份样例)")
        payloads[key] = network.read_json(path)
    return payloads


# ============================================================================
# 数据装载:--sample(7 节点样例网 SEG-###)/ --network real(站点登记表真网,段号前缀见 seg_prefix)
#
# 两套输入**只在装载这一步分流**;后面的候选生成 / 时段预约 / 不伤害 / 再疏导 / --compare
# 完全共用同一套函数(不按数据 source 分支)。dataset 把两边的差异收进元数据块,
# 保证 --sample 的计算路径与产物逐字节不变。
# ============================================================================


def _load_sample_dataset(cfg: dict[str, Any]) -> dict[str, Any]:
    """装载 --sample 输入(样例网 + 样例 segments + 样例 OD + 站点包)。"""
    samples_dir: Path = cfg["samples_dir"]
    stations_dir: Path = cfg["stations_dir"]
    payloads = load_samples(samples_dir)
    graph = network.Graph(payloads["network"])
    segments_state = network.load_segments(samples_dir / SAMPLE_FILES["segments"])
    thresholds = network.load_thresholds(stations_dir / "thresholds.json")
    params = thresholds["decision"]
    grading = thresholds["grading"]
    points = load_points(stations_dir)

    demand = payloads["demand"]
    od_pairs = demand.get("od")
    if not isinstance(od_pairs, list) or not od_pairs:
        raise ValueError("样例 demand 的 od 缺失或为空(容器键与 stations/demand.json 一致)")
    # demand.json 没有 ts,时间戳取 segments 的
    base_ts = str(payloads["segments"].get("ts") or "")
    if not base_ts:
        raise SystemExit("样例 segments 缺 ts 字段")

    return {
        "network": "sample",
        "mode": "sample",
        "graph": graph,
        "graph_payload": payloads["network"],
        "segments_state": segments_state,
        "thresholds": thresholds,
        "params": params,
        "grading": grading,
        "points": points,
        "factors_payload": _load_optional_json(stations_dir / "factors.json"),
        "demand": demand,
        "od_pairs": od_pairs,
        "segments_payload": payloads["segments"],
        "ts": base_ts,
        "schema_note": SAMPLE_ROUTES_SCHEMA_NOTE,
        "compare_schema_note": COMPARE_ROUTES_SCHEMA_NOTE,
        "log_source_fields": {"samples_dir": samples_dir.name},
        "log_extra": {},
        "network_block": None,
        "od_derivation": None,
        "segments_source": None,
        "compare_scenario_note": COMPARE_SCENARIO_NOTE,
        "compare_guided_common_note": COMPARE_GUIDED_COMMON_NOTE,
        "route_lengths": False,
        "seg_prefix": None,
    }


def _load_real_dataset(cfg: dict[str, Any]) -> dict[str, Any]:
    """装载 --network real 输入:站点登记表 → 真网统一图 → segments 映射 → 边界 OD。"""
    stations_dir: Path = cfg["stations_dir"]
    site = realnet.load_site(cfg.get("site_id"), cfg.get("site_ranges"))
    network_payload, topology_meta = realnet.load_network_payload(site)
    thresholds = network.load_thresholds(stations_dir / "thresholds.json")
    params = thresholds["decision"]
    grading = thresholds["grading"]

    graph_payload, net_meta = realnet.normalize_network(network_payload, site, grading)
    net_meta.update(topology_meta)
    graph = network.Graph(graph_payload)
    segments_state, seg_meta = realnet.build_segments_state(graph, cfg.get("segments"))
    demand_vph = float(cfg.get("demand_vph") or realnet.DEMO_DEMAND_VPH)
    if demand_vph <= 0.0:
        raise SystemExit(f"--demand-vph 必须为正（实为 {demand_vph}）：需求按辆/小时口径")
    od_pairs, od_meta = realnet.derive_od_pairs(graph, net_meta, demand_vph, params)

    snapshot_used = bool(seg_meta.get("used"))
    snapshot_ts = seg_meta.get("snapshot_ts") if snapshot_used else None
    snapshot_window = seg_meta.get("snapshot_window_sec") if snapshot_used else None
    base_ts = str(snapshot_ts or realnet.DEMO_BASE_TS)
    window_sec = float(snapshot_window or realnet.DEMO_WINDOW_SEC)

    segments_source = dict(seg_meta)
    segments_source["ts_used"] = base_ts
    segments_source["window_sec_used"] = window_sec
    segments_source["ts_origin"] = (
        "upstream_segments_snapshot"
        if snapshot_ts
        else (
            "demo_constant:realnet.DEMO_BASE_TS（不读系统时钟；快照段号不匹配时也不采用其 ts）"
            if seg_meta.get("snapshot")
            else "demo_constant:realnet.DEMO_BASE_TS（不读系统时钟）"
        )
    )
    segments_source["window_sec_origin"] = (
        "upstream_segments_snapshot"
        if snapshot_window
        else (
            "demo_constant:realnet.DEMO_WINDOW_SEC（快照段号不匹配时也不采用其 window_sec）"
            if seg_meta.get("snapshot")
            else "demo_constant:realnet.DEMO_WINDOW_SEC"
        )
    )
    compare_scenario_note = REAL_COMPARE_SCENARIO_NOTE
    if not seg_meta.get("used"):
        compare_scenario_note += (
            "；⚠ 本次没有段号匹配的上游 segments 快照：全部路段 q_vph=0（演示降级口径），"
            "三组差异只由时段预约占用产生；真网指标快照接入后重跑更有意义，**不调参数凑过**"
        )

    network_block: dict[str, Any] = {
        "site_id": net_meta["site_id"],
        "site_name": net_meta["site_name"],
        "network_file": net_meta["network_file"],
        "source": net_meta["source"],
        "crs": net_meta["crs"],
        "generated_by": net_meta["generated_by"],
        "seg_prefix": net_meta["seg_prefix"],
        "seg_target": net_meta["seg_target"],
        "segments_read": net_meta["segments_read"],
        "nodes_read": net_meta["nodes_read"],
        "graph_edges": net_meta.get("graph_edges"),
        "node_type_source": net_meta["node_type_source"],
        "boundary_source": net_meta["boundary_source"],
        "entries": net_meta["entries"],
        "exits": net_meta["exits"],
        # IKNB9H：方向/车道/U-turn/贯通性来源与统计
        "topology_source": net_meta.get("topology_source"),
        "topology_file": net_meta.get("topology_file"),
        "topology_note": net_meta.get("topology_note"),
        "directions": net_meta.get("directions"),
        "u_turn_allowed_segments": net_meta.get("u_turn_allowed_segments"),
        "left_turn_allowed_segments": net_meta.get("left_turn_allowed_segments"),
        "derived_boundaries": net_meta.get("derived_boundaries"),
        "capacity_note": net_meta.get("capacity_note"),
        "param_defaults": net_meta["param_defaults"],
        "param_source_counts": net_meta["param_source_counts"],
        "lanes_missing": net_meta["lanes_missing"],
        "speed_missing": net_meta["speed_missing"],
        "capacity_missing": net_meta["capacity_missing"],
        "origin_contract_map": network_payload.get("contract_map"),
        "segments": realnet.network_trace(graph_payload, net_meta),
    }

    return {
        "network": "real",
        "mode": "real",
        "graph": graph,
        "graph_payload": graph_payload,
        "segments_state": segments_state,
        "thresholds": thresholds,
        "params": params,
        "grading": grading,
        # 真网暂无真点点位表(点位归 IKMHMX / 池·S 踏勘);不拿样例点位硬套真网节点
        "points": [],
        "factors_payload": _load_optional_json(stations_dir / "factors.json"),
        "demand": {"od": od_pairs, "note": od_meta["rule"]},
        "od_pairs": od_pairs,
        "segments_payload": {"ts": base_ts, "window_sec": window_sec},
        "ts": base_ts,
        "schema_note": real_routes_schema_note(net_meta["seg_prefix"], net_meta["site_name"]),
        "compare_schema_note": real_routes_schema_note(net_meta["seg_prefix"], net_meta["site_name"]),
        "log_source_fields": {
            "site_id": net_meta["site_id"],
            "network_file": net_meta["network_file"],
            "segments_snapshot": seg_meta.get("snapshot"),
        },
        "log_extra": {
            "segments_source": segments_source,
            "od_derivation": od_meta,
            "od_count": len(od_pairs),
            "demand_vph_per_od": demand_vph,
            "network_param_defaults": net_meta["param_defaults"],
            "topology_source": net_meta.get("topology_source"),
            "topology_file": net_meta.get("topology_file"),
            "topology_directions": net_meta.get("directions"),
            "u_turn_allowed_segments": net_meta.get("u_turn_allowed_segments"),
        },
        "network_block": network_block,
        "od_derivation": od_meta,
        "segments_source": segments_source,
        "compare_scenario_note": compare_scenario_note,
        "compare_guided_common_note": REAL_COMPARE_GUIDED_COMMON_NOTE,
        "route_lengths": True,
        "seg_prefix": net_meta["seg_prefix"],
    }


def _load_dataset(cfg: dict[str, Any]) -> dict[str, Any]:
    """按 `cfg["network"]` 装载输入:缺省/`sample` → 样例网;`real` → 真网站点登记表。"""
    if cfg.get("network") == "real":
        return _load_real_dataset(cfg)
    return _load_sample_dataset(cfg)


def _segments_of(graph: network.Graph, path: list[str]) -> list[str]:
    """把边 id 序列折成 segment_id 序列(契约第二节 arrival_route.segments 是路段号)。"""
    return [str(graph.edge(eid).get("section")) for eid in path]


def _factors_note(
    graph: network.Graph,
    path: list[str],
    segments: dict[str, dict[str, Any]],
) -> str | None:
    """从路径经过的路段的 factors_applied 里摘出说明(契约第二节 factors_note,可空)。"""
    notes: list[str] = []
    for eid in path:
        section = str(graph.edge(eid).get("section"))
        segment = segments.get(section)
        if not segment:
            continue
        for factor in segment.get("factors_applied") or []:
            note = f"{section} {factor.get('name')}，{factor.get('target')} 按 {factor.get('multiplier')} 折减（{factor.get('factor_id')}）"
            if note not in notes:
                notes.append(note)
    return "；".join(notes) if notes else None


def build_request(
    od: dict[str, Any],
    graph: network.Graph,
    segments_state: dict[str, dict[str, Any]],
    params: dict[str, Any],
    points: list[dict[str, Any]],
    index: int,
    now_ts: str,
) -> dict[str, Any]:
    """为一个 OD 对算出 1 推荐 + 备选(契约第二节的响应体形状)。"""
    src, dst = str(od["from_node"]), str(od["to_node"])
    weight = network.make_weight_fn(graph, segments_state, params)

    picked = candidates.select_candidates(
        graph, src, dst,
        k=_search_k(params),
        max_overlap=float(params.get("max_path_overlap", 0.7)),
        weight=weight,
    )
    scored = sorted(
        ((network.path_travel_time_s(graph, p, segments_state, params), p) for p in picked),
        key=lambda item: (round(item[0], 6), item[1]),
    )

    od_id = str(od.get("od_id") or f"OD-{index:02d}")
    # 司机类型按**终点类型**推(见 DRIVER_TYPE_BY_STOP);终点是路口等其它类型时退回默认 D1
    driver_type = DRIVER_TYPE_BY_STOP.get(str(graph.node(dst).get("type")), SAMPLE_DRIVER_TYPE)
    request: dict[str, Any] = {
        "request_id": f"REQ-SAMPLE-{index:04d}",
        "session_id": f"S-sample-{index:04d}",
        "od_id": od_id,
        "driver_type": driver_type,
        "parking_mode": SAMPLE_PARKING_MODE,
        "location": {
            "segment_id": str(graph.edge(picked[0][0]).get("section")) if picked else None,
            "offset_m": 0,
            "match_confidence": 1.0,
            "source": "twin",
        },
        "pickup_route": None,
        "reroute": {"count": 0, "reason": None},
        "is_simulated": True,
    }

    if not scored:
        request["no_alternative"] = True
        request["no_alternative_reason"] = f"{src} → {dst} 之间无可行路径"
        request["arrival_route"] = None
        request["departure_route"] = None
        request["alternatives"] = []
        request["reservation"] = None
        request["why"] = "无可行路径(路网不连通),按契约第二节的 no_alternative 例外输出"
        return request

    best_eta_s, best_path = scored[0]
    stop = stop_point_of(points, graph, dst, best_path)
    # 落客点写**点位 id**(契约第二节示例是 "DROP-03"),不写图节点 id。
    # D2(接客)行程的终点是**上客点**,不写进 arrival_route.dropoff_point(Issue #94 第②条)——
    # 契约里 arrival_route 只有 dropoff_point 一个点位字段,把上客写进去就是把行程描述成落客。
    is_dropoff_stop = driver_type == "D1" and stop is not None
    request["arrival_route"] = {
        "path_id": f"{od_id}-P1",
        "segments": _segments_of(graph, best_path),
        "edges": list(best_path),
        "eta_min": round(best_eta_s / 60.0, 2),
        "dropoff_point": stop["point_id"] if is_dropoff_stop else None,
        # walk_min 跟**点位**走、不跟 dropoff_point 走:上客行程(D2)也有"从站厅走到上车点"的时间,
        # 所以 D2 下 dropoff_point 为 null 但 walk_min 仍在 —— 与改动前行为一致,不给下游制造空值。
        "walk_min": SAMPLE_WALK_MIN if stop is not None else None,
    }

    if len(scored) == 1:
        # 契约第二节硬规则:只有一条候选时按 no_alternative 例外,不为凑数返回等价路径
        request["no_alternative"] = True
        request["no_alternative_reason"] = "只有一条候选路径通过重叠度约束"
        request["alternatives"] = []
    else:
        request["alternatives"] = [
            {
                "path_id": f"{od_id}-P{i + 2}",
                "segments": _segments_of(graph, path),
                "edges": list(path),
                "eta_min": round(eta_s / 60.0, 2),
                "reason": f"比推荐多 {round((eta_s - best_eta_s) / 60.0, 2)} 分钟",
            }
            for i, (eta_s, path) in enumerate(scored[1:])
        ]

    # 离站路线:契约标它**必填**、TC-12 要求必现 —— 算不出时**不静默置 null**,
    # 把原因并进 why(Issue #94 第③条;不加新字段,省一次契约变更)。
    notes: list[str] = []
    exit_node = od.get("exit_node")
    if not exit_node:
        request["departure_route"] = None
        notes.append("离站路线未计算:od[] 缺 exit_node(契约 6.3),无法确定送完客往哪走")
    elif str(exit_node) not in graph.node_ids:
        request["departure_route"] = None
        notes.append(f"离站路线未计算:exit_node={exit_node!r} 不在路网 nodes 里")
    elif str(exit_node) == dst:
        request["departure_route"] = None
        notes.append("离站路线未计算:exit_node 与终点相同,无需离站路线")
    else:
        dep = candidates.select_candidates(graph, dst, str(exit_node), k=1, max_overlap=1.0, weight=weight)
        if dep:
            dep_eta = network.path_travel_time_s(graph, dep[0], segments_state, params)
            request["departure_route"] = {
                "path_id": f"{od_id}-D1",
                "segments": _segments_of(graph, dep[0]),
                "edges": list(dep[0]),
                "eta_min": round(dep_eta / 60.0, 2),
            }
        else:
            request["departure_route"] = None
            notes.append(f"离站路线未计算:{dst} → {exit_node} 之间无可行路径")

    # 点位登记情况也进 why:查不到**不退回图节点 id**,而是在这里说清(Issue #94 第①条)。
    # 只在**终点确是落客/上客点**时才说 —— 终点是路口这类节点时本就没有落客点位,不该报"未登记"。
    # IKP5C6:真网节点类型统一是 `intersection`,旧分支永不命中 → dropoff_point 静默 null。
    # 这里补上"不是落客/上客点"的原因,并覆盖 D2 行程 / 送客点未登记两种空值来源。
    dst_type = str(graph.node(dst).get("type"))
    if dst_type == "pickup":
        detail = f";对应点位 {stop['point_id']}" if stop else ";上客点位未在站点包登记"
        notes.append("终点是上客点,不写进 arrival_route.dropoff_point" + detail)
    elif dst_type == "dropoff" and stop is None:
        notes.append(f"落客点位未在站点包登记({dst} 的相邻路段里查不到 type=dropoff 的点位)")
    elif dst_type == "dropoff" and not is_dropoff_stop:
        notes.append(
            f"行程类型 {driver_type} 不是送客(D1),不把 {stop['point_id']} 写进 arrival_route.dropoff_point"
        )
    elif stop is None:
        notes.append(
            f"终点不是落客/上客点(节点 {dst} 的 type={dst_type}),"
            "arrival_route.dropoff_point 按契约留空;点位表未登记该段点位"
        )

    request["reservation"] = None
    request["quota"] = None
    request["factors_note"] = _factors_note(graph, best_path, segments_state)
    request["why"] = (
        f"按 BPR(t = t0·(1+α·x^β))算出的**此刻最快**,比备选少 "
        f"{round((scored[1][0] - best_eta_s) / 60.0, 2)} 分钟"
        if len(scored) > 1 else
        "按 BPR 算出的**此刻最快**;无备选(只有一条候选通过重叠度约束)"
    )
    request["why"] += (
        "。⚠️ 本输出是「此刻最快」基线(手册 7.6 的对照组口径),"
        "**不是协同推荐** —— 时段容量预约与不伤害前车约束尚未实现(W3),故 reservation 为 null。"
    )
    if notes:
        request["why"] += " " + " ".join(f"[{n}]" for n in notes)
    return request


# ============================================================================
# TC-12 / D3(--d3):往返代表请求的 pickup_route 做实
#
# 口径(契约变更 v2.4,`docs/数据契约.md` §2.2 由 C 落笔):
#   - `pickup_route` 仅 D3 出现,形状 = `arrival_route` 镜像:
#     {"path_id","segments","eta_min","pickup_point","walk_min"};
#   - 上客点 = `type=="pickup"` 点位按 `point_id` 升序、取登记在**到达终点相邻路段**
#     (`_adjacent_sections`,与 `stop_point_of()` 同口径)上的第一个;
#   - `pickup_route` 从到达终点所在路段算到点位所在路段;`departure_route` 从该路段
#     算到 `exit_node`;三段都 `walk_slots` 进预约表,`slots_reserved` 按**唯一
#     `(segment, slot)` 格子**计数,`harm_check` 对全部格子算;
#   - 默认关闭;`--compare --d3` 直接报错退出(避免扰动 TC-17 车辆群);
#   - 是否生成以 `demand.json` 的 `mix.driver_type_ratio` 中 D3 `ratio > 0` 为依据,
#     确定性、不随机;真网 `points=[]` → 跳过并在 run_log 写
#     `d3_skipped: no_pickup_point`(不按坐标映射点位、不编 `pickup_point`);
#   - **representative 口径(契约 v2.4,开发B 裁定 2026-10-19,方案 B)**:D3 是说明性
#     代表样例,请求体带 `representative: true`;`reservation.harm_check` 只作展示、
#     不作准入判据,下游不得把 `passed=false` 的 D3 当可执行推荐;
#   - **备选例外(契约 §2.2)**:上客候选仅 1 个(相邻路段 type=pickup 点位全集,数据
#     推导)时输出 `no_alternative: true` + `no_alternative_reason`,不硬凑等价备选。
# ============================================================================


def d3_ratio(demand: dict[str, Any]) -> float:
    """`demand.json` 的 `mix.driver_type_ratio` 里 D3 的占比(缺 mix / 缺 D3 → 0.0)。"""
    mix = demand.get("mix") if isinstance(demand, dict) else None
    for item in (mix or {}).get("driver_type_ratio") or []:
        if str(item.get("driver_type")) == "D3":
            return float(item.get("ratio") or 0.0)
    return 0.0


def d3_pickup_edges(
    graph: network.Graph,
    node_id: str,
    pickup_point: dict[str, Any],
    path: list[str],
) -> list[str] | None:
    """上客段的边序列:从到达终点走到上客点所在路段。

    - 点位登记在**驶离终点的边**上(样例 `OD-02`:`P-02` 挂 `SEG-004`,`E-004` 出边)→ 取该出边;
    - 点位登记在**到达路径的最后一条边**上(车此刻就在该路段上)→ 取该边;
    - 其余(点位在未走过的入边路段等,构造不出"从终点走到该路段"的边序列)→ None,
      调用方跳过该 OD 的 D3 请求并留痕,不按坐标硬凑。
    """
    target_segment = str(pickup_point.get("segment_id"))
    for edge_id in graph.out_edges(node_id):
        if str(graph.edge(edge_id).get("section")) == target_segment:
            return [edge_id]
    last_edge = path[-1] if path else None
    if last_edge is not None and str(graph.edge(last_edge).get("section")) == target_segment:
        return [last_edge]
    return None


def _build_d3_request(
    base: dict[str, Any],
    od: dict[str, Any],
    graph: network.Graph,
    segments_state: dict[str, dict[str, Any]],
    params: dict[str, Any],
    points: list[dict[str, Any]],
    index: int,
    ts: str,
    table: reserve.SlotTable,
    request_id_prefix: str,
) -> dict[str, Any] | None:
    """为一个 OD 构造 1 个 D3 代表请求;构造不出(无到达段 / 无相邻上客点)返回 None。

    `arrival_route` 照旧(沿用同 OD 普通请求的到达段);`pickup_route` /
    `departure_route` 按上方口径新算;三段合并走 `walk_slots`,唯一格子计数,
    `harm_check` 对全部格子算(约束① 同式;D3 代表流未建租约,约束② 无前车可伤)。
    """
    arrival = base.get("arrival_route")
    if not isinstance(arrival, dict):
        return None
    od_id = str(od.get("od_id") or f"OD-{index:02d}")
    dst = str(od["to_node"])
    arrival_edges = [str(edge_id) for edge_id in (arrival.get("edges") or [])]
    pickup_point = pickup_point_for_d3(points, graph, dst, arrival_edges)
    if pickup_point is None:
        return None
    pickup_edges = d3_pickup_edges(graph, dst, pickup_point, arrival_edges)
    if pickup_edges is None:
        return None

    # 上客候选数(数据推导,no_alternative 的判据):相邻路段上 type=pickup 的点位**全集**。
    # pickup_point_for_d3 用同一套相邻路段口径但只返回首个(point_id 升序);这里专为数个数。
    adjacent_sections = _adjacent_sections(graph, dst, arrival_edges)
    pickup_candidates = sorted(
        (
            point
            for point in points
            if str(point.get("type")) == "pickup"
            and str(point.get("segment_id")) in adjacent_sections
        ),
        key=lambda point: str(point.get("point_id")),
    )
    no_alternative = len(pickup_candidates) == 1
    no_alternative_reason = (
        f"D3 上客候选仅 1 个(相邻路段上 type=pickup 点位仅 "
        f"{pickup_candidates[0].get('point_id')}/{pickup_candidates[0].get('segment_id')}),"
        "无第二备选"
        if no_alternative
        else None
    )

    # 离站段:从上客点所在路段(其下游节点)算到 exit_node(复用既有"同节点 → 无需离站"口径)
    departure_edges: list[str] = []
    departure_note: str | None = None
    exit_node = od.get("exit_node")
    pickup_end_node = str(graph.edge(pickup_edges[-1]).get("to"))
    if not exit_node:
        departure_note = "离站路线未计算:od[] 缺 exit_node(契约 6.3)"
    elif str(exit_node) not in graph.node_ids:
        departure_note = f"离站路线未计算:exit_node={exit_node!r} 不在路网 nodes 里"
    elif str(exit_node) == pickup_end_node:
        departure_note = "上客路段终点即 exit_node,无需离站路线"
    else:
        weight = network.make_weight_fn(graph, segments_state, params)
        dep = candidates.select_candidates(
            graph, pickup_end_node, str(exit_node), k=1, max_overlap=1.0, weight=weight
        )
        if dep:
            departure_edges = list(dep[0])
        else:
            departure_note = f"离站路线未计算:{pickup_end_node} → {exit_node} 之间无可行路径"

    # 三段合并成一条连通边序列走 walk_slots(pickup 段首边与到达段末边相同时不重复计)
    combined_edges = list(arrival_edges)
    shared_edge = bool(combined_edges) and pickup_edges[0] == combined_edges[-1]
    if not shared_edge:
        combined_edges.extend(pickup_edges)
    combined_edges.extend(departure_edges)
    start_epoch_s = reserve.iso_to_epoch_s(ts)
    cells, _combined_eta_s, edge_times = reserve.walk_slots_detail(
        table, combined_edges, start_epoch_s, extra=1.0
    )
    # `pickup_route.eta_min` 是**上客段单段** ETA(与 `arrival_route.eta_min` 同口径,
    # 契约 v2.4 补登):从合并路径的逐边服务时间里取上客段那几条边求和;与到达段
    # 共用同一首边时该边已计入到达段,不重复计。预约格仍按三段合并路径计。
    pickup_offset = len(arrival_edges)
    pickup_edge_count = len(pickup_edges) - (1 if shared_edge else 0)
    pickup_eta_s = sum(edge_times[pickup_offset : pickup_offset + pickup_edge_count])
    unique_cells = sorted(set(cells))
    harm = reserve.harm_check(table, unique_cells, {}, params)
    table.reserve(unique_cells)

    pickup_segment = str(graph.edge(pickup_edges[-1]).get("section"))
    arrival_last_segment = str(graph.edge(arrival_edges[-1]).get("section")) if arrival_edges else None
    departure_route = None
    if departure_edges:
        dep_eta_s = reserve.walk_slots(table, departure_edges, start_epoch_s, extra=0.0)[1]
        departure_route = {
            "path_id": f"{od_id}-DK",
            "segments": _segments_of(graph, departure_edges),
            "edges": departure_edges,
            "eta_min": round(dep_eta_s / 60.0, 2),
        }

    why = (
        f"D3 往返代表请求:到达 {dst} 后接上客段 —— 上客点 {pickup_point.get('point_id')}"
        f"(挂 {pickup_segment},按相邻路段口径自 type=pickup 点位中依 point_id 选定);"
        f"pickup_route 从到达终点所在路段({arrival_last_segment})算到点位所在路段"
        f"({pickup_segment}),ETA {round(pickup_eta_s / 60.0, 2)} 分钟;"
    )
    if departure_route is not None:
        why += f"departure_route 从该路段算到 exit_node(ETA {departure_route['eta_min']} 分钟);"
    elif departure_note:
        why += departure_note + ";"
    why += (
        f"三段合计唯一预约格子 {len(unique_cells)} 个"
        f"(slots_reserved 按唯一 (segment, slot) 计),harm_check "
        f"{'通过' if harm['passed'] else '未过'}(最大时段饱和度 {harm['max_slot_x']})。"
    )
    # 契约 v2.4 裁定(开发B 2026-10-19,方案 B):D3 是 representative 说明性代表样例,
    # harm_check 只作展示、不作准入判据 —— 如实写进 why,下游不得把 passed=false 的
    # D3 请求当可执行推荐;备选不足(候选数=1,数据推导)同样如实标注,不硬凑备选。
    why += (
        "⚠️ 本请求是 representative 说明性代表样例:reservation.harm_check 只作展示、"
        "不作为准入判据,不得当可执行推荐。"
    )
    if no_alternative:
        why += f"备选不足:{no_alternative_reason}。"

    request: dict[str, Any] = {
        "request_id": f"{request_id_prefix}-D3-{index:04d}",
        "session_id": f"{base.get('session_id')}-d3",
        "od_id": od_id,
        "driver_type": "D3",
        # 契约 v2.4(开发B 裁定 2026-10-19,方案 B):D3 = representative 说明性代表样例
        "representative": True,
        "parking_mode": SAMPLE_PARKING_MODE,
        "location": dict(base.get("location") or {}),
        "pickup_route": {
            "path_id": f"{od_id}-PK",
            "segments": _segments_of(graph, pickup_edges),
            "eta_min": round(pickup_eta_s / 60.0, 2),
            "pickup_point": str(pickup_point.get("point_id")),
            "walk_min": SAMPLE_WALK_MIN,
        },
        "arrival_route": dict(arrival),
        "departure_route": departure_route,
        "alternatives": [],
        "reservation": {
            "slots_reserved": len(unique_cells),
            "lease_expire_s": int(params["lease_expire_s"]),
            "harm_check": harm,
        },
        "reroute": {"count": 0, "reason": None},
        "quota": None,
        "factors_note": base.get("factors_note"),
        "why": why,
        "is_simulated": True,
    }
    # 契约 §2.2 唯一例外:上客候选仅 1 个(数据推导)时**才**输出这两个键,不硬凑等价备选
    if no_alternative:
        request["no_alternative"] = True
        request["no_alternative_reason"] = no_alternative_reason
    return request


def append_d3_requests(
    requests: list[dict[str, Any]],
    od_pairs: list[dict[str, Any]],
    graph: network.Graph,
    segments_state: dict[str, dict[str, Any]],
    params: dict[str, Any],
    points: list[dict[str, Any]],
    ts: str,
    request_id_prefix: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """对每个 OD 追加 1 个 D3 代表请求(确定性:OD 顺序 + point_id 升序,不随机)。

    追加到 `requests` 尾部,返回 `(d3_requests, skipped_od_ids)`;个别 OD 构造不出
    (无到达段 / 相邻路段上无 type=pickup 点位)时跳过该 OD 并把 od_id 记入
    `skipped_od_ids` 留痕,不编点位。是否生成由 `d3_ratio(demand) > 0` 决定(调用方判)。
    """
    table = reserve.SlotTable(graph, segments_state, params)
    d3_requests: list[dict[str, Any]] = []
    skipped_od_ids: list[str] = []
    for index, od in enumerate(od_pairs, start=1):
        base = requests[index - 1] if index - 1 < len(requests) else None
        od_id = str(od.get("od_id") or f"OD-{index:02d}")
        d3 = (
            _build_d3_request(
                base,
                od,
                graph,
                segments_state,
                params,
                points,
                index,
                ts,
                table,
                request_id_prefix,
            )
            if isinstance(base, dict)
            else None
        )
        if d3 is not None:
            d3_requests.append(d3)
        else:
            skipped_od_ids.append(od_id)
    requests.extend(d3_requests)
    return d3_requests, skipped_od_ids


def run_sample(cfg: dict[str, Any]) -> int:
    """用 samples/ + stations/thresholds.json 走完整链路,不依赖上游、不依赖 SUMO。"""
    dataset = _load_sample_dataset(cfg)
    out_dir: Path = cfg["out_dir"]
    graph = dataset["graph"]
    segments_state = dataset["segments_state"]
    params = dataset["params"]
    # 点位表也读站点包:终点要折成**点位 id**(Issue #94 第①条),引擎里不许写站点相关的字符串常量
    points = dataset["points"]
    od_pairs = dataset["od_pairs"]
    demand = dataset["demand"]
    now_ts = dataset["ts"]

    network.ensure_out_dir(out_dir)

    requests = [
        build_request(od, graph, segments_state, params, points, i + 1, now_ts)
        for i, od in enumerate(od_pairs)
    ]
    # TC-12 / D3:默认关闭;开启后按 demand 的 D3 占比对每个 OD 追加 1 个代表请求
    d3_log: dict[str, Any] = {}
    if cfg.get("d3"):
        d3_log = {"d3_enabled": True}
        if d3_ratio(demand) > 0.0:
            d3_requests, skipped_od_ids = append_d3_requests(
                requests, od_pairs, graph, segments_state, params, points, now_ts, "REQ-SAMPLE"
            )
            d3_log["d3_requests"] = len(d3_requests)
            if skipped_od_ids:
                d3_log["d3_skipped"] = "no_adjacent_pickup_point"
                d3_log["d3_skipped_od_ids"] = skipped_od_ids
            else:
                d3_log["d3_skipped"] = None
        else:
            d3_log["d3_requests"] = 0
            d3_log["d3_skipped"] = "d3_ratio_zero"

    routes = {
        "ts": now_ts,
        "is_simulated": True,
        "mode": dataset["mode"],
        "schema_note": dataset["schema_note"],
        "requests": requests,
    }
    written: dict[str, int] = {}
    written["routes.json"] = network.write_json(out_dir / "routes.json", routes)
    network.assert_artifact(out_dir / "routes.json")

    log = {
        "ts": now_ts,
        "is_simulated": True,
        "mode": dataset["mode"],
        "scenario": cfg.get("scenario", "sample"),
        "seed": cfg.get("seed", 0),
        **dataset["log_source_fields"],
        "stations_dir": str(cfg["stations_dir"]),
        "node_count": len(graph.node_ids),
        "edge_count": len(graph._edges),  # noqa: SLF001 —— 只读计数,给日志看
        "od_count": len(od_pairs),
        **d3_log,
        "requests_with_alternative": sum(
            1 for r in requests if len(r.get("alternatives") or []) >= 2
        ),
        "is_reservation_effective": False,
        "snapshots": 1,
        "decision_params_used": {
            "alpha": params.get("alpha"),
            "beta": params.get("beta"),
            "k_candidates": params.get("k_candidates"),
            "max_path_overlap": params.get("max_path_overlap"),
        },
        "written_bytes": written,
        "note": (
            "W1 边界:只做候选路径生成 + BPR 行程时间,产出「此刻最快」基线;"
            "时段容量预约 / 不伤害前车约束 / 再疏导是 W3/W5,reservation 恒为 null"
        ),
    }
    written["run_log.json"] = network.write_json(out_dir / "run_log.json", log)
    network.assert_artifact(out_dir / "run_log.json")
    return 0


# ============================================================================
# --network real:真网(站点登记表,段号前缀/段数按站点)协同推荐入口
#
# 与 --sample 的区别只在**输入来源**:
#   · --sample  = 7 节点 SEG-### 样例网的**对照组基线**(reservation 恒为 null,不许改);
#   · --network real = 真网 61 段上的**协同推荐**(时段容量预约 + 不伤害前车),
#     这是 M1-4 的验收口径(真网 ≥3 个 OD 对出候选路线且 reservation.harm_check.passed=true)。
# 机制函数(reserve.recommend / reroute / _build_cooperative_request)与 --compare 完全共用,
# 不按数据 source 分支;两边差异只体现在装载与产物元数据。
# ============================================================================


def run_real(cfg: dict[str, Any]) -> int:
    """真网协同推荐:站点登记表 → 61 段真网 → 边界 OD → 时段预约 + 不伤害。"""
    dataset = _load_real_dataset(cfg)
    out_dir: Path = cfg["out_dir"]
    graph = dataset["graph"]
    segments_state = dataset["segments_state"]
    params = dataset["params"]
    points = dataset["points"]
    od_pairs = dataset["od_pairs"]
    now_ts = dataset["ts"]

    network.ensure_out_dir(out_dir)

    weight = network.make_weight_fn(graph, segments_state, params)
    table = reserve.SlotTable(graph, segments_state, params)
    leases: dict[str, dict[str, Any]] = {}
    requests: list[dict[str, Any]] = []
    for index, od in enumerate(od_pairs, start=1):
        od_id = str(od.get("od_id") or f"OD-R-{index:03d}")
        candidate_paths = candidates.select_candidates(
            graph,
            str(od["from_node"]),
            str(od["to_node"]),
            k=_search_k(params),
            max_overlap=float(params.get("max_path_overlap", 0.7)),
            weight=weight,
        )
        decision = reserve.recommend(
            graph,
            {"od_id": od_id, "session_id": f"S-real-{od_id}"},
            candidate_paths,
            segments_state,
            params,
            table,
            leases,
            now_ts,
        )
        if decision["status"] != "ok":
            requests.append(
                _build_shortage_request(od, graph, params, index, decision, f"REQ-REAL-{index:04d}")
            )
            continue
        # 一期口径:孪生行为体选择跟随推荐路线(手册 §7.6(5))
        decision["lease"]["confirmed"] = True
        requests.append(
            _build_cooperative_request(
                od,
                graph,
                segments_state,
                params,
                points,
                index,
                decision,
                {"count": 0, "reason": None},
                request_id_prefix="REQ-REAL",
            )
        )

    # TC-12 / D3:真网站点包 `points=[]` 是既有口径(点位归 IKMHMX / 池·S 踏勘),
    # 无上客点位即跳过并留痕,不按坐标映射点位、不编 pickup_point。
    # 现状(独立审查整改):真网 `dataset["demand"]` 只有 {"od","note"}(无 mix),
    # 且 `points` 恒空,所以下面的 append 分支**当前不可达**;保留它是为点位/需求
    # 结构补齐后复用样例同一套 `append_d3_requests` —— 同时用 `d3_note` 明示
    # "真网一期不支持 D3",不让 run_log 看起来像"真网会生成 D3"。
    d3_log: dict[str, Any] = {}
    if cfg.get("d3"):
        d3_log = {"d3_enabled": True, "d3_requests": 0}
        if not points:
            d3_log["d3_skipped"] = "no_pickup_point"
            d3_log["d3_note"] = (
                "真网一期站点包无上客点位(points=[]),D3 不支持;"
                "点位到位后走样例同一套追加逻辑"
            )
        elif d3_ratio(dataset["demand"]) > 0.0:
            d3_requests, skipped_od_ids = append_d3_requests(
                requests, od_pairs, graph, segments_state, params, points, now_ts, "REQ-REAL"
            )
            d3_log["d3_requests"] = len(d3_requests)
            if skipped_od_ids:
                d3_log["d3_skipped"] = "no_adjacent_pickup_point"
                d3_log["d3_skipped_od_ids"] = skipped_od_ids
            else:
                d3_log["d3_skipped"] = None
        else:
            d3_log["d3_skipped"] = "d3_ratio_zero"
            d3_log["d3_note"] = "真网 demand 无 mix.driver_type_ratio,D3 占比视为 0"

    # 段号命名空间硬校验 + 长度补齐 + 方向/车道 legs（真网产物专属，样例基线不做，保持逐字节不变）
    length_enriched = realnet.attach_route_lengths(requests, graph)
    topology_enriched = realnet.attach_route_topology(requests, graph)
    segment_refs_checked = realnet.assert_segment_namespace(requests, dataset["seg_prefix"])
    stats = realnet.count_route_segments(requests, dataset["seg_prefix"])
    reservation_passed = sum(
        1
        for request in requests
        if isinstance(request.get("reservation"), dict)
        and bool((request["reservation"].get("harm_check") or {}).get("passed"))
    )

    routes = {
        "ts": now_ts,
        "is_simulated": True,
        "mode": dataset["mode"],
        "network": dataset["network_block"],
        "od_derivation": dataset["od_derivation"],
        "segments_source": dataset["segments_source"],
        "schema_note": dataset["schema_note"],
        "requests": requests,
    }
    written: dict[str, int] = {}
    written["routes.json"] = network.write_json(out_dir / "routes.json", routes)
    network.assert_artifact(out_dir / "routes.json")

    log = {
        "ts": now_ts,
        "is_simulated": True,
        "mode": dataset["mode"],
        "scenario": cfg.get("scenario", "real"),
        "seed": cfg.get("seed", 0),
        **dataset["log_source_fields"],
        "stations_dir": str(cfg["stations_dir"]),
        "node_count": len(graph.node_ids),
        "edge_count": len(graph._edges),  # noqa: SLF001 —— 只读计数,给日志看
        "od_count": len(od_pairs),
        **d3_log,
        "demand_vph_per_od": float(cfg.get("demand_vph") or realnet.DEMO_DEMAND_VPH),
        "requests_with_alternative": stats["od_with_alternative"],
        "requests_with_reservation": stats["od_with_reservation"],
        "route_count": stats["route_count"],
        "segment_ref_count": stats["segment_ref_count"],
        "segment_refs_checked": segment_refs_checked,
        "length_m_enriched": length_enriched,
        "route_legs_enriched": topology_enriched,
        "is_reservation_effective": True,
        "snapshots": 1,
        "segments_source": dataset["segments_source"],
        "od_derivation": dataset["od_derivation"],
        "m1_4": {
            "od_count": len(od_pairs),
            "od_with_alternative": stats["od_with_alternative"],
            "od_with_reservation": stats["od_with_reservation"],
            "od_with_reservation_harm_passed": reservation_passed,
            "passed": bool(
                len(od_pairs) >= 3
                and stats["od_with_alternative"] >= 3
                and reservation_passed >= 3
            ),
        },
        "decision_params_used": {key: params[key] for key in sorted(params)},
        "network_param_defaults": dataset["network_block"]["param_defaults"],
        "param_source_counts": dataset["network_block"]["param_source_counts"],
        "written_bytes": written,
        "note": (
            f"真网协同推荐:段号一律 {dataset['seg_prefix']}-###"
            f"（来自站点范围登记表的 seg_prefix，本站 {dataset['network_block']['site_name']}）,"
            "routes.json 的 network.segments[] 给出逐段 length_m/from-to/param_source;"
            "segments_source 如实记录上游快照命中/降级情况;参数全部读 stations/thresholds.json"
        ),
    }
    log.update(dataset["log_extra"])
    written["run_log.json"] = network.write_json(out_dir / "run_log.json", log)
    network.assert_artifact(out_dir / "run_log.json")
    return 0


# ============================================================================
# --compare:同一份输入跑三组(① 不推荐 ② "此刻最快" ③ 协同推荐)+ TC-17 三项判据
#
# 口径(不编结果,只算):
#   ① 不推荐       = 车辆按**自由流最短路**走(没有推荐时的习惯路线);
#   ② 此刻最快     = 现有 --sample 在同一 segments 快照上算出的推荐路线(普通导航:
#                    不做时段预约、看不见后车,整批车都按同一份"此刻最快"走);
#   ③ 协同推荐     = 本单的时段容量预约 + 不伤害前车约束 + 前车再疏导。
# 三组用**同一份输入、同一个车辆群、同一个站点包参数**;判据数值一律读站点包 decision 组。
# ============================================================================

#: 橙 / 红档的等级下限(手册第 6 章的等级语义:1 畅通 / 2 缓行 / 3 拥堵=橙 / 4 严重拥堵=红)。
#: 这是"颜色 → 等级"的固定语义映射,不是可调判据;档位边界本身读 thresholds.json 的 grading 组。
ORANGE_RED_MIN_LEVEL = 3

#: "--compare 的突发再疏导演示"取评估窗口中点的时刻(demo 场景口径,不是判定数值)。
REROUTE_DEMO_WINDOW_FRACTION = 0.5

#: 候选生成的**搜索深度** K(见 `_search_k` 与 `realnet.CANDIDATE_SEARCH_K`)。
#: 契约锁的是「备选 ≥ 2 条」与 `no_alternative` 字段形状,手册明写「K 与候选生成算法属做法,
#: 可自选并申报」——所以 K 是代码常量,不是站点包可调值。
#: 取值 30 的实测依据(真网 44 节点 / 94 条有向边 / 61 段,重叠度门槛仍读站点包 0.7):
#:   · K=3  → 4 条 OD 全部 1 条(备选恒空);
#:   · K=10 → 只有 OD-R-001 出 2 条备选,OD-R-004(10 条原始候选但彼此高度重叠)仍只有 1 条;
#:   · K=30 → OD-R-001 与 OD-R-004 都能筛出 ≥2 条真不同走廊(绕行 +80~125 m,不是等价复刻);
#:   · 另外两条 OD(N-013→N-012 / N-040→N-012)在真网拓扑上是**唯一通路**
#:     (枚举简单路径各只有 1 条),任何 K 都出不来第二条 → 按契约如实 `no_alternative`,
#:     不靠放宽重叠度门槛硬凑等价路径。
CANDIDATE_SEARCH_K = 30


def _x_level_bounds(grading: dict[str, Any]) -> list[float]:
    """读 grading.level_bounds 里 `x` 的档位边界(判级契约第六节;缺了直接报错,不猜)。"""
    for item in grading.get("level_bounds") or []:
        if item.get("indicator") == "x":
            bounds = item.get("bounds")
            if isinstance(bounds, list) and bounds:
                return [float(value) for value in bounds]
    raise ValueError("thresholds.json 的 grading.level_bounds 缺 x 的档位边界(契约第六节)")


def _level_of_x(x: float, bounds: list[float]) -> int:
    """按档位边界把饱和度映射成等级 1~4(边界语义照抄站点包:小于边界落在前一档)。"""
    for index, bound in enumerate(bounds):
        if x < bound:
            return index + 1
    return len(bounds) + 1


def _scenario_vehicles(
    demand: dict[str, Any],
    segments_payload: dict[str, Any],
    base_ts: str,
) -> tuple[list[dict[str, Any]], float]:
    """按 demand 的 OD 需求铺出一批**确定性**车辆(同输入必然同一车辆群)。

    - 车辆数 = `demand_vph × window_sec / 3600`(window_sec 是 segments 的指标统计窗口);
    - 每辆车的出发时刻按 `3600 / demand_vph` 等间隔排(不引入随机数、不读系统时钟);
    - 返回 (车辆列表, 评估窗口秒数);车辆按 (出发时刻, od_id, 序号) 排序。
    """
    od_pairs = demand.get("od")
    if not isinstance(od_pairs, list) or not od_pairs:
        raise ValueError("样例 demand 的 od 缺失或为空(容器键与 stations/demand.json 一致)")
    window_s = float(segments_payload.get("window_sec") or 0.0)
    if window_s <= 0.0:
        raise SystemExit("样例 segments 缺 window_sec(评估窗口),--compare 无法铺车流")
    base_epoch = reserve.iso_to_epoch_s(base_ts)

    vehicles: list[dict[str, Any]] = []
    for od in od_pairs:
        od_id = str(od.get("od_id") or "")
        demand_vph = float(od.get("demand_vph") or 0.0)
        if demand_vph <= 0.0:
            continue
        headway_s = reserve.SECONDS_PER_HOUR / demand_vph
        count = int(round(window_s * demand_vph / reserve.SECONDS_PER_HOUR))
        for index in range(count):
            vehicles.append(
                {
                    "session_id": f"S-cmp-{od_id}-{index:04d}",
                    "od_id": od_id,
                    "seq": index,
                    "departure_epoch_s": base_epoch + index * headway_s,
                }
            )
    vehicles.sort(key=lambda item: (item["departure_epoch_s"], item["od_id"], item["seq"]))
    return vehicles, window_s


def _static_candidates(
    graph: network.Graph,
    od_pairs: list[dict[str, Any]],
    segments_state: dict[str, dict[str, Any]],
    params: dict[str, Any],
) -> dict[str, list[list[str]]]:
    """用**同一份 segments 快照**(= --sample 的输入)给每个 OD 生成候选路径。

    ② 与 ③ 共用这批候选:② 取其中"此刻最快"的第一条(等于 --sample 的推荐),
    ③ 在这批候选上叠预约与不伤害约束 —— 三组对照才是"同一份输入"。
    """
    weight = network.make_weight_fn(graph, segments_state, params)
    result: dict[str, list[list[str]]] = {}
    for od in od_pairs:
        od_id = str(od.get("od_id") or "")
        result[od_id] = candidates.select_candidates(
            graph,
            str(od["from_node"]),
            str(od["to_node"]),
            k=_search_k(params),
            max_overlap=float(params.get("max_path_overlap", 0.7)),
            weight=weight,
        )
    return result


def _fastest_path_of(
    graph: network.Graph,
    candidates_paths: list[list[str]],
    segments_state: dict[str, dict[str, Any]],
    params: dict[str, Any],
) -> list[str] | None:
    """按 BPR 行程时间挑"此刻最快"的那条(= --sample 的推荐口径)。"""
    if not candidates_paths:
        return None
    scored = sorted(
        (
            (network.path_travel_time_s(graph, path, segments_state, params), path)
            for path in candidates_paths
        ),
        key=lambda item: (round(item[0], 6), item[1]),
    )
    return list(scored[0][1])


def _habitual_path(
    graph: network.Graph,
    od: dict[str, Any],
    params: dict[str, Any],
) -> list[str] | None:
    """① 不推荐:车辆按自由流最短路走(没有推荐时的"习惯路线")。"""

    def free_flow_weight(edge_id: str) -> float:
        return network.free_flow_time_s(graph.edge(edge_id))

    picked = candidates.select_candidates(
        graph,
        str(od["from_node"]),
        str(od["to_node"]),
        k=1,
        max_overlap=float(params.get("max_path_overlap", 0.7)),
        weight=free_flow_weight,
    )
    return list(picked[0]) if picked else None


def _estimate_progress(
    table: reserve.SlotTable,
    lease: dict[str, Any],
    now_epoch_s: float,
) -> int:
    """估算这辆车到 `now_epoch_s` 已经走完几条边(给"是否还在分岔前"用)。

    优先用租约里登记时算好的**逐边计划服务时间**累计(与再疏导的 ETA 基线同一套规划);
    没有逐边时间的老租约退回"按当前预约表逐边推进"的估算。
    """
    path = list(lease.get("path") or [])
    edge_times = lease.get("edge_times_s")
    if isinstance(edge_times, list) and len(edge_times) == len(path):
        elapsed_s = float(now_epoch_s) - float(lease.get("start_epoch_s", 0.0))
        if elapsed_s <= 0.0:
            return 0
        covered_s = 0.0
        for index, edge_time in enumerate(edge_times):
            covered_s += float(edge_time)
            if covered_s > elapsed_s:
                return index
        return len(path)
    now_cursor = float(lease.get("start_epoch_s", 0.0))
    for index, edge_id in enumerate(path):
        slot_index = reserve.slot_index_of(now_cursor, table.slot_minutes)
        now_cursor += table.tt(edge_id, slot_index, extra=0.0)
        if now_cursor > float(now_epoch_s):
            return index
    return len(path)


def _compare_group_metrics(
    group_result: dict[str, Any],
    segments_state: dict[str, dict[str, Any]],
    grading: dict[str, Any],
    start_epoch_s: float,
    end_epoch_s: float,
) -> dict[str, Any]:
    """一组的统计:服务/未进入车数、前车 ETA 最大增加、总行程时间、橙红路段集合。"""
    records = group_result["records"]
    table: reserve.SlotTable = group_result["table"]
    admitted = [record for record in records if record["admitted"]]
    max_eta_increase_s = max(
        (float(record["harm"]["max_eta_increase_s"]) for record in admitted),
        default=0.0,
    )
    served = {str(record["session_id"]): float(record["eta_s"]) for record in admitted}
    total_travel_time_s = sum(served.values())
    #: 四计数的 completed / in_transit:按"预计到达时刻是否已落在评估窗口内"拆
    completed_count = sum(
        1
        for record in admitted
        if float(record["departure_epoch_s"]) + float(record["eta_s"]) <= float(end_epoch_s)
    )
    in_transit_count = len(admitted) - completed_count
    #: 全网总行程时间(辆·秒,含背景车流):TC-17 第③项的口径
    network_total_time_s = table.network_total_time_s(start_epoch_s, end_epoch_s)

    bounds = _x_level_bounds(grading)
    saturation: dict[str, float] = {}
    orange_red: list[str] = []
    for segment_id in sorted(segments_state):
        value = table.segment_max_saturation(segment_id)
        saturation[segment_id] = round(value, 4)
        if _level_of_x(value, bounds) >= ORANGE_RED_MIN_LEVEL:
            orange_red.append(segment_id)
    return {
        "group": group_result["group"],
        "group_label": group_result["group_label"],
        "attempted": len(records),
        #: 成功登记预约的车数(= completed + in_transit);不是 attempted
        "inserted": len(admitted),
        "completed": completed_count,
        "in_transit": in_transit_count,
        "not_entered": len(records) - len(admitted),
        "removed": 0,
        "max_eta_increase_s": round(max_eta_increase_s, 2),
        "total_travel_time_s": round(total_travel_time_s, 2),
        "network_total_time_s": round(network_total_time_s, 2),
        "served": served,
        "orange_red_segments": orange_red,
        "segment_max_saturation": saturation,
    }


#: 「拥堵持续时间」的过饱和判据:x >= 1.0 表示需求已达到或超过通行能力。
#: 这是"过饱和"的物理定义,**不是等级档位**——等级档位仍一律读 thresholds.json 的
#: grading.level_bounds(代码里不写死),两者不能互相顶替:
#:   - 按 x>=0.8(橙档)算,三组几乎整窗都"拥堵",没有区分度(2026-10-26 跑数对比);
#:   - 按 x>=1.0(过饱和)算,处置前后才有可比的差异。
CONGESTION_MIN_SATURATION = 1.0


def _segment_geometry(
    graph: network.Graph,
    segments_state: dict[str, dict[str, Any]],
) -> dict[str, dict[str, float]]:
    """每段的静态几何(车道数 / 路段长度),给排队长度换算用。

    车道数取统一图里的边(引擎侧只从边上读,`run.py` 不直接读 lanes 字段);
    路段长度优先用上游 segments 快照的 `L_seg_m`,缺失回退边上的 `length_m`。
    """
    geometry: dict[str, dict[str, float]] = {}
    for edge_id in sorted(graph._edges):  # noqa: SLF001 —— 只读遍历,与 realnet 同口径
        edge = graph.edge(edge_id)
        section = str(edge.get("section") or "")
        if not section or section in geometry:
            continue
        geometry[section] = {
            "lanes": float(edge.get("lanes") or 1.0),
            "length_m": float(edge.get("length_m") or 0.0),
        }
    for segment_id, geometry_row in geometry.items():
        snapshot_length = (segments_state.get(segment_id) or {}).get("L_seg_m")
        if snapshot_length is not None:
            geometry_row["length_m"] = float(snapshot_length)
    return geometry


def _treatment_side_metrics(
    table: reserve.SlotTable,
    scope: list[str],
    geometry: dict[str, dict[str, float]],
    *,
    start_slot: int,
    end_slot: int,
    slot_minutes: int,
    queue_headway_m: float,
    bounds: list[float],
) -> dict[str, Any]:
    """处置前/后单侧的三个指标:排队长度峰值、拥堵持续时间、饱和度和。

    口径(与孪生侧 `work/twin/loop.py` 的 `METRIC_FORMULAS` 同源,不另立一套):
      - 逐时段饱和度 `x_slot = table.saturation(segment_id, slot)`;
      - **排队长度** 每时段 `q_veh = max(0, x-1) × capacity_per_slot`(只有过饱和才会积压),
        `L_q = min(L_seg_m, q_veh / 车道数 × queue_headway_m)`,对 scope 内所有段所有时段取最大;
      - **拥堵持续时间** 逐时段判 `x >= 1.0`,取最长**连续**过饱和时段数 × slot_minutes;
      - **饱和度和** scope 内各段窗口内最大饱和度之和(两侧用同一个 scope,分母才可比)。
    """
    peak_queue_m = 0.0
    peak_queue_segment: str | None = None
    congested_minutes = 0
    congested_segment: str | None = None
    saturation_sum = 0.0
    per_segment: dict[str, dict[str, Any]] = {}

    for segment_id in scope:
        lanes = max(1.0, float(geometry.get(segment_id, {}).get("lanes") or 1.0))
        length_m = float(geometry.get(segment_id, {}).get("length_m") or 0.0)
        capacity_per_slot = table.capacity_per_slot(segment_id)
        slot_values = [table.saturation(segment_id, slot) for slot in range(start_slot, end_slot)]
        finite = [value for value in slot_values if math.isfinite(value)]
        max_x = max(finite) if finite else 0.0
        saturation_sum += max_x

        segment_peak = 0.0
        for value in slot_values:
            if not math.isfinite(value) or value <= CONGESTION_MIN_SATURATION:
                continue
            queued_vehicles = max(0.0, value - CONGESTION_MIN_SATURATION) * capacity_per_slot
            segment_peak = max(
                segment_peak,
                min(length_m, queued_vehicles / lanes * queue_headway_m),
            )
        run_slots = 0
        best_run = 0
        for value in slot_values:
            if math.isfinite(value) and value >= CONGESTION_MIN_SATURATION:
                run_slots += 1
                best_run = max(best_run, run_slots)
            else:
                run_slots = 0
        segment_minutes = best_run * slot_minutes

        per_segment[segment_id] = {
            "max_x": round(max_x, 4),
            "level": _level_of_x(max_x, bounds),
            "peak_queue_m": round(segment_peak, 2),
            "congested_minutes": segment_minutes,
        }
        if segment_peak > peak_queue_m:
            peak_queue_m, peak_queue_segment = segment_peak, segment_id
        if segment_minutes > congested_minutes:
            congested_minutes, congested_segment = segment_minutes, segment_id

    return {
        "peak_queue_m": round(peak_queue_m, 2),
        "peak_queue_segment": peak_queue_segment,
        "congested_minutes": congested_minutes,
        "congested_segment": congested_segment,
        "saturation_sum": round(saturation_sum, 4),
        "per_segment": per_segment,
    }


def _compare_treatment(
    group_results: dict[str, dict[str, Any]],
    group_metrics: dict[str, dict[str, Any]],
    graph: network.Graph,
    segments_state: dict[str, dict[str, Any]],
    grading: dict[str, Any],
    params: dict[str, Any],
    start_epoch_s: float,
    end_epoch_s: float,
    tz: Any,
) -> dict[str, Any]:
    """处置前后三项(手册第 17 章效果对比报表):排队长度峰值 / 拥堵持续时间 / 饱和度和差。

    **等长时间窗**:处置前 = 组①「不推荐」、处置后 = 组③「协同推荐」,两组跑**同一个评估窗口**
    (同一 base_ts、同一 window_sec、同一车辆群、同一份站点包参数),差异只来自推荐机制。
    不虚构两个时间段、不拿演示值顶替。
    """
    queue_headway_m = float(grading.get("queue_headway_m") or 0.0)
    if queue_headway_m <= 0.0:
        raise SystemExit("站点包 thresholds.grading 的 queue_headway_m 必须为正(排队长度换算要用)")
    slot_minutes = int(params["slot_minutes"])
    bounds = _x_level_bounds(grading)
    geometry = _segment_geometry(graph, segments_state)
    start_slot = reserve.slot_index_of(start_epoch_s, slot_minutes)
    end_slot = reserve.slot_index_of(end_epoch_s, slot_minutes)

    before_table: reserve.SlotTable = group_results["no_guidance"]["table"]
    after_table: reserve.SlotTable = group_results["cooperative"]["table"]
    before_orange = list(group_metrics["no_guidance"]["orange_red_segments"])
    after_orange = list(group_metrics["cooperative"]["orange_red_segments"])
    #: 两侧统一 scope:橙红路段取并集。各用各的橙红段会让分母不同,产生"假优势"。
    scope = sorted(set(before_orange) | set(after_orange))

    side_kwargs = {
        "scope": scope,
        "geometry": geometry,
        "start_slot": start_slot,
        "end_slot": end_slot,
        "slot_minutes": slot_minutes,
        "queue_headway_m": queue_headway_m,
        "bounds": bounds,
    }
    before = _treatment_side_metrics(before_table, **side_kwargs)
    after = _treatment_side_metrics(after_table, **side_kwargs)
    #: scope 为空(本窗口没有任何段进橙红档)→ 三项没有可比的段,如实标不可用。
    #: **不能输出 0 → 0 冒充"完美改善"**:那是把"没测到"说成"治好了"。
    available = bool(scope)
    unavailable_reason = (
        None
        if available
        else "本评估窗口内三组都没有橙红档路段(scope 为空),三项无对比对象;"
        "不输出 0 → 0 冒充改善,请换一个有拥堵的时间窗(更长的 window_sec 或带指标的 segments 快照)再跑。"
    )

    return {
        "window": {
            "base_ts": reserve.epoch_s_to_iso(start_epoch_s, tz),
            "start_ts": reserve.epoch_s_to_iso(start_epoch_s, tz),
            "end_ts": reserve.epoch_s_to_iso(end_epoch_s, tz),
            "window_sec": round(float(end_epoch_s) - float(start_epoch_s), 3),
            "slot_minutes": slot_minutes,
            "slots": max(0, end_slot - start_slot),
            "before_group": "no_guidance",
            "after_group": "cooperative",
            "mode": "same_window_group_compare",
            "note": (
                "等长时间窗:处置前=组①(不推荐)、处置后=组③(协同推荐),两组跑同一评估窗口"
                "(同一 base_ts / 同一 window_sec / 同一车辆群 / 同一站点包参数),"
                "差异只来自推荐机制;不虚构两个时间段。"
            ),
        },
        "scope": {
            "segment_ids": scope,
            "rule": "处置前橙红段 ∪ 处置后橙红段(两侧同一段号集合,分母可比,避免假优势)",
            "before_orange_red_segments": before_orange,
            "after_orange_red_segments": after_orange,
        },
        "available": available,
        "unavailable_reason": unavailable_reason,
        "metrics": {
            "queue": {
                "name": "排队长度峰值",
                "unit": "m",
                "before": before["peak_queue_m"] if available else None,
                "after": after["peak_queue_m"] if available else None,
                "delta": (
                    round(after["peak_queue_m"] - before["peak_queue_m"], 2)
                    if available
                    else None
                ),
                "better": "down",
                "before_segment": before["peak_queue_segment"] if available else None,
                "after_segment": after["peak_queue_segment"] if available else None,
                "formula": (
                    "逐时段 q_veh = max(0, x-1) × capacity_per_slot;"
                    "L_q = min(L_seg_m, q_veh / 车道数 × queue_headway_m);取 scope 内最大"
                ),
            },
            "duration": {
                "name": "拥堵持续时间",
                "unit": "min",
                "before": before["congested_minutes"] if available else None,
                "after": after["congested_minutes"] if available else None,
                "delta": (
                    after["congested_minutes"] - before["congested_minutes"]
                    if available
                    else None
                ),
                "better": "down",
                "before_segment": before["congested_segment"] if available else None,
                "after_segment": after["congested_segment"] if available else None,
                "formula": (
                    f"逐时段判 x >= {CONGESTION_MIN_SATURATION}(过饱和,非等级档位);"
                    "取最长连续过饱和时段数 × slot_minutes"
                ),
            },
            "saturation": {
                "name": "饱和度和",
                "unit": "Δx 合计",
                "before": before["saturation_sum"] if available else None,
                "after": after["saturation_sum"] if available else None,
                "delta": (
                    round(after["saturation_sum"] - before["saturation_sum"], 4)
                    if available
                    else None
                ),
                "better": "down",
                "formula": "scope 内各段窗口内最大饱和度之和(两侧同一 scope)",
            },
        },
        "per_segment": {"before": before["per_segment"], "after": after["per_segment"]},
        "constants": {
            "queue_headway_m": queue_headway_m,
            "saturation_flow_vph_per_lane": grading.get("saturation_flow_vph_per_lane"),
            "congestion_min_saturation": CONGESTION_MIN_SATURATION,
            "source": "stations/thresholds.json 的 grading(queue_headway_m 等);过饱和判据见 formula",
        },
        "note": (
            "三项均由本引擎在同一评估窗口上现算(不是演示值);"
            "各项口径写在 metrics.*.formula 里;"
            "饱和度和用并集 scope,若协同推荐把流量挪到别的段,和值可能不降——如实输出,不挑口径。"
        ),
    }


def _baseline_orange_red(
    segments_state: dict[str, dict[str, Any]],
    grading: dict[str, Any],
) -> list[str]:
    """初始 segments 快照里的橙 / 红路段(给"不新增"做对照留痕)。"""
    _ = grading  # 初始快照自带 level 字段,与运行时用 level_bounds 算出的等级同一口径
    return [
        segment_id
        for segment_id in sorted(segments_state)
        if int(segments_state[segment_id].get("level") or 0) >= ORANGE_RED_MIN_LEVEL
    ]


def _run_compare_group(
    group: str,
    group_label: str,
    graph: network.Graph,
    segments_state: dict[str, dict[str, Any]],
    params: dict[str, Any],
    od_by_id: dict[str, dict[str, Any]],
    vehicles: list[dict[str, Any]],
    od_candidates: dict[str, list[list[str]]],
    fastest_paths: dict[str, list[str] | None],
    habitual_paths: dict[str, list[str] | None],
    tz: Any,
) -> dict[str, Any]:
    """跑一组车流(三组用同一批车辆与同一份站点包参数)。"""
    table = reserve.SlotTable(graph, segments_state, params)
    leases: dict[str, dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    admissions_by_od: dict[str, list[dict[str, Any]]] = {od_id: [] for od_id in od_by_id}

    for vehicle in vehicles:
        od_id = vehicle["od_id"]
        od = od_by_id[od_id]
        start_epoch_s = float(vehicle["departure_epoch_s"])
        now_ts = reserve.epoch_s_to_iso(start_epoch_s, tz)

        if group == "cooperative":
            decision = reserve.recommend(
                graph,
                {
                    "od_id": od_id,
                    "session_id": vehicle["session_id"],
                },
                od_candidates.get(od_id) or [],
                segments_state,
                params,
                table,
                leases,
                now_ts,
            )
            if decision["status"] != "ok":
                records.append(
                    {
                        "session_id": vehicle["session_id"],
                        "od_id": od_id,
                        "departure_epoch_s": start_epoch_s,
                        "admitted": False,
                        "reason": decision["status"],
                        "eta_s": None,
                        "harm": None,
                    }
                )
                continue
            lease = decision["lease"]
            lease["confirmed"] = True  # 一期口径:孪生行为体选择跟随推荐路线(手册 §7.6(5))
            records.append(
                {
                    "session_id": vehicle["session_id"],
                    "od_id": od_id,
                    "departure_epoch_s": start_epoch_s,
                    "admitted": True,
                    "reason": None,
                    "eta_s": float(decision["eta_s"]),
                    "harm": decision["harm_check"],
                }
            )
            admissions_by_od[od_id].append({"vehicle": vehicle, "decision": decision})
            continue

        path = (
            habitual_paths.get(od_id)
            if group == "no_guidance"
            else fastest_paths.get(od_id)
        )
        if not path:
            records.append(
                {
                    "session_id": vehicle["session_id"],
                    "od_id": od_id,
                    "departure_epoch_s": start_epoch_s,
                    "admitted": False,
                    "reason": "no_route",
                    "eta_s": None,
                    "harm": None,
                }
            )
            continue
        cells, eta_s, edge_times = reserve.walk_slots_detail(
            table, list(path), start_epoch_s, extra=1.0
        )
        # ①② 不做约束,但**同样度量**"这辆车加入后对前车 ETA 的最大影响",给 TC-17 留对照
        harm = reserve.harm_check(table, cells, leases, params)
        table.reserve(cells)
        leases[vehicle["session_id"]] = {
            "session_id": vehicle["session_id"],
            "od_id": od_id,
            "path": list(path),
            "cells": cells,
            #: 与 ③ 的租约同形:逐边计划时间 + 通过约束的候选(本组无约束,候选即本条路径)
            "edge_times_s": [float(value) for value in edge_times],
            "feasible_candidates": [list(path)],
            "eta_s": float(eta_s),
            "start_epoch_s": start_epoch_s,
            "expire_at_epoch_s": start_epoch_s + float(params["lease_expire_s"]),
            "confirmed": True,
            "reroute_count": 0,
        }
        records.append(
            {
                "session_id": vehicle["session_id"],
                "od_id": od_id,
                "departure_epoch_s": start_epoch_s,
                "admitted": True,
                "reason": None,
                "eta_s": float(eta_s),
                "harm": harm,
            }
        )

    return {
        "group": group,
        "group_label": group_label,
        "table": table,
        "leases": leases,
        "records": records,
        "admissions_by_od": admissions_by_od,
    }


def _compare_departure_route(
    graph: network.Graph,
    segments_state: dict[str, dict[str, Any]],
    params: dict[str, Any],
    od: dict[str, Any],
    dst: str,
    od_id: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """离站路线(契约必填、TC-12 要求必现;算不出时把原因并进 why,不静默置 null)。"""
    exit_node = od.get("exit_node")
    if not exit_node:
        return None, "离站路线未计算:od[] 缺 exit_node(契约 6.3),无法确定送完客往哪走"
    if str(exit_node) not in graph.node_ids:
        return None, f"离站路线未计算:exit_node={exit_node!r} 不在路网 nodes 里"
    if str(exit_node) == dst:
        return None, "离站路线未计算:exit_node 与终点相同,无需离站路线"
    weight = network.make_weight_fn(graph, segments_state, params)
    dep = candidates.select_candidates(
        graph,
        dst,
        str(exit_node),
        k=1,
        max_overlap=float(params.get("max_path_overlap", 0.7)),
        weight=weight,
    )
    if not dep:
        return None, f"离站路线未计算:{dst} → {exit_node} 之间无可行路径"
    dep_eta_s = network.path_travel_time_s(graph, dep[0], segments_state, params)
    return (
        {
            "path_id": f"{od_id}-D1",
            "segments": _segments_of(graph, dep[0]),
            "edges": list(dep[0]),
            "eta_min": round(dep_eta_s / 60.0, 2),
        },
        None,
    )


def _path_id_plan(
    od_id: str,
    candidates_list: list[dict[str, Any]],
    chosen_path: list[str],
) -> tuple[dict[int, str], int | None]:
    """给候选排 path_id:推荐 = P1,其余按候选顺序 P2..;返回 (下标→path_id, 推荐下标)。"""
    chosen_index: int | None = None
    for index, candidate in enumerate(candidates_list):
        if list(candidate["path"]) == list(chosen_path):
            chosen_index = index
            break
    ids: dict[int, str] = {}
    next_id = 2
    for index in range(len(candidates_list)):
        if index == chosen_index:
            ids[index] = f"{od_id}-P1"
        else:
            ids[index] = f"{od_id}-P{next_id}"
            next_id += 1
    return ids, chosen_index


def _build_cooperative_request(
    od: dict[str, Any],
    graph: network.Graph,
    segments_state: dict[str, dict[str, Any]],
    params: dict[str, Any],
    points: list[dict[str, Any]],
    index: int,
    decision: dict[str, Any],
    reroute_block: dict[str, Any],
    request_id_prefix: str = "REQ-COMPARE",
) -> dict[str, Any]:
    """把一个 OD 代表车的协同推荐结果折成契约第二节的响应体(不新增契约字段)。

    `request_id_prefix` 默认 `REQ-COMPARE`(**--compare 的逐字节基线**);
    真网协同推荐入口传 `REQ-REAL`,只改请求号前缀,响应体形状不变。
    """
    od_id = str(od.get("od_id") or f"OD-{index:02d}")
    path = list(decision["path"])
    eta_s = float(decision["eta_s"])
    dst = str(od["to_node"])
    driver_type = DRIVER_TYPE_BY_STOP.get(str(graph.node(dst).get("type")), SAMPLE_DRIVER_TYPE)
    stop = stop_point_of(points, graph, dst, path)
    is_dropoff_stop = driver_type == "D1" and stop is not None
    harm = decision["harm_check"]
    candidates_list = list(decision["candidates"])
    path_ids, chosen_index = _path_id_plan(od_id, candidates_list, path)

    request: dict[str, Any] = {
        "request_id": f"{request_id_prefix}-{index:04d}",
        "session_id": str(decision["session_id"]),
        "od_id": od_id,
        "driver_type": driver_type,
        "parking_mode": SAMPLE_PARKING_MODE,
        "location": {
            "segment_id": str(graph.edge(path[0]).get("section")) if path else None,
            "offset_m": 0,
            "match_confidence": 1.0,
            "source": "twin",
        },
        "pickup_route": None,
        "arrival_route": {
            "path_id": f"{od_id}-P1",
            "segments": _segments_of(graph, path),
            "edges": path,
            "eta_min": round(eta_s / 60.0, 2),
            "dropoff_point": stop["point_id"] if is_dropoff_stop else None,
            "walk_min": SAMPLE_WALK_MIN if stop is not None else None,
        },
        "reroute": reroute_block,
        "is_simulated": True,
    }

    alternatives: list[dict[str, Any]] = []
    for candidate_index, candidate in enumerate(candidates_list):
        if candidate_index == chosen_index:
            continue
        eta_diff_min = round((float(candidate["eta_s"]) - eta_s) / 60.0, 2)
        if candidate["rejected_reason"]:
            reason = (
                f"未采用:不满足预约约束({candidate['rejected_reason']});"
                f"该路线时段最大饱和度 {candidate['harm_check']['max_slot_x']}"
            )
        else:
            reason = f"比推荐多 {eta_diff_min} 分钟"
        alternatives.append(
            {
                "path_id": path_ids[candidate_index],
                "segments": _segments_of(graph, list(candidate["path"])),
                "edges": list(candidate["path"]),
                "eta_min": round(float(candidate["eta_s"]) / 60.0, 2),
                "reason": reason,
            }
        )
    request["alternatives"] = alternatives
    if len(candidates_list) <= 1:
        request["no_alternative"] = True
        request["no_alternative_reason"] = "只有一条候选路径通过重叠度约束"

    # 离站路线:契约必填、TC-12 要求必现;算不出时把原因并进 why(不静默置 null)
    departure_route, departure_note = _compare_departure_route(
        graph, segments_state, params, od, dst, od_id
    )
    request["departure_route"] = departure_route
    notes: list[str] = []
    if departure_note:
        notes.append(departure_note)
    dst_type = str(graph.node(dst).get("type"))
    if dst_type == "pickup":
        detail = f";对应点位 {stop['point_id']}" if stop else ";上客点位未在站点包登记"
        notes.append("终点是上客点,不写进 arrival_route.dropoff_point" + detail)
    elif dst_type == "dropoff" and stop is None:
        notes.append(f"落客点位未在站点包登记({dst} 的相邻路段里查不到 type=dropoff 的点位)")
    elif dst_type == "dropoff" and not is_dropoff_stop:
        notes.append(
            f"行程类型 {driver_type} 不是送客(D1),不把 {stop['point_id']} 写进 arrival_route.dropoff_point"
        )
    elif stop is None:
        # IKP5C6:真网节点类型统一是 intersection,旧分支永不命中 → dropoff_point 静默 null。
        notes.append(
            f"终点不是落客/上客点(节点 {dst} 的 type={dst_type}),"
            "arrival_route.dropoff_point 按契约留空;点位表未登记该段点位"
        )

    quota: dict[str, int] = {}
    for candidate_index in range(len(candidates_list)):
        quota[path_ids[candidate_index]] = int(decision["quota"][candidate_index])
    request["quota"] = quota

    eps_harm_s = float(params["eps_harm_s"])
    x_safe = float(params["x_safe"])
    why = (
        "协同推荐:时段容量预约 + 不伤害前车约束下选**对本车最快**的路线"
        f"(ETA {round(eta_s / 60.0, 2)} 分钟);两条约束都过 —— "
        f"前车 ETA 最大增加 {harm['max_eta_increase_s']}s(上限 {eps_harm_s:g}s)、"
        f"本车路径最大时段饱和度 {harm['max_slot_x']}(上限 {x_safe:g})。"
    )
    if alternatives:
        slowest = max(float(candidate["eta_s"]) for candidate in candidates_list)
        why += f" 该路线比最慢候选少 {round((slowest - eta_s) / 60.0, 2)} 分钟。"
    if int(reroute_block.get("count") or 0) > 0:
        why += f" 本车已被再疏导 {reroute_block['count']} 次:{reroute_block.get('reason')}。"
    request["reservation"] = {
        "slots_reserved": len(decision["cells"]),
        "lease_expire_s": int(params["lease_expire_s"]),
        "harm_check": harm,
    }
    request["factors_note"] = _factors_note(graph, path, segments_state)
    if notes:
        why += " " + " ".join(f"[{note}]" for note in notes)
    request["why"] = why
    return request


def _build_shortage_request(
    od: dict[str, Any],
    graph: network.Graph,
    params: dict[str, Any],
    index: int,
    decision: dict[str, Any],
    request_id: str,
) -> dict[str, Any]:
    """全部候选都放不下时的响应体:输出 `capacity_shortage` + 需求侧建议,**不给路线**。"""
    od_id = str(od.get("od_id") or f"OD-{index:02d}")
    dst = str(od["to_node"])
    driver_type = DRIVER_TYPE_BY_STOP.get(str(graph.node(dst).get("type")), SAMPLE_DRIVER_TYPE)
    rejected = []
    for candidate_index, candidate in enumerate(decision["candidates"]):
        rejected.append(
            {
                "path_id": f"{od_id}-P{candidate_index + 1}",
                "segments": _segments_of(graph, list(candidate["path"])),
                "reason": candidate["rejected_reason"],
                "max_slot_x": candidate["harm_check"]["max_slot_x"],
                "max_eta_increase_s": candidate["harm_check"]["max_eta_increase_s"],
            }
        )
    return {
        "request_id": request_id,
        "session_id": str(decision["session_id"]),
        "od_id": od_id,
        "driver_type": driver_type,
        "parking_mode": SAMPLE_PARKING_MODE,
        "location": {
            "segment_id": None,
            "offset_m": 0,
            "match_confidence": 1.0,
            "source": "twin",
        },
        "pickup_route": None,
        "arrival_route": None,
        "departure_route": None,
        "alternatives": [],
        "reservation": None,
        "reroute": {"count": 0, "reason": None},
        "quota": None,
        "capacity_shortage": {
            "reason": reserve.REASON_NO_CAPACITY,
            "suggest": list(decision["suggest"]),
            "rejected_candidates": rejected,
        },
        "factors_note": None,
        "why": (
            "全部候选都不满足「任一时段饱和度 ≤ x_safe」与「不伤害前车」两条约束,"
            "按时段预约口径输出 capacity_shortage + 需求侧建议(外围等待 / 延后出发 / 换停车场),"
            "**不给任何路线**(不硬塞)。"
        ),
        "is_simulated": True,
    }


def _build_capacity_shortage_evidence(
    graph: network.Graph,
    segments_state: dict[str, dict[str, Any]],
    params: dict[str, Any],
    od_pairs: list[dict[str, Any]],
    od_candidates: dict[str, list[list[str]]],
    base_ts: str,
) -> dict[str, Any]:
    """本单专属一:**构造一个必然放不下的场景**,证明输出 capacity_shortage 而不是硬给路线。

    做法(不依赖任何随机性 / 不写死判据):
      1. 取第一个 OD 的全部候选路径;
      2. 对每条候选,按 `remaining_quota()` 算出"这条路径还能塞几辆"(瓶颈格子驱动),
         把这些车**沿该路径**登记进预约表 —— 于是每条候选的瓶颈格子都被顶到 x_safe 边界;
      3. 再请求同一辆车的推荐:每条候选的约束① 都必然失败 → 必须输出 capacity_shortage。
    """
    od = od_pairs[0]
    od_id = str(od.get("od_id") or "OD-01")
    table = reserve.SlotTable(graph, segments_state, params)
    leases: dict[str, dict[str, Any]] = {}
    start_epoch_s = reserve.iso_to_epoch_s(base_ts)
    filled: list[dict[str, Any]] = []
    for candidate_index, path in enumerate(od_candidates.get(od_id) or []):
        cells_before, _eta = reserve.walk_slots(table, list(path), start_epoch_s, extra=0.0)
        quota = reserve.remaining_quota(table, list(path), start_epoch_s, params)
        for _ in range(int(quota)):
            table.reserve(cells_before)
        filled.append(
            {
                "path_id": f"{od_id}-P{candidate_index + 1}",
                "segments": _segments_of(graph, list(path)),
                "quota_before_fill": int(quota),
                "max_slot_x_after_fill": round(
                    max(
                        (table.saturation(segment_id, slot_index) for segment_id, slot_index in cells_before),
                        default=0.0,
                    ),
                    4,
                ),
            }
        )

    decision = reserve.recommend(
        graph,
        {"od_id": od_id, "session_id": "S-compare-shortage-demo"},
        od_candidates.get(od_id) or [],
        segments_state,
        params,
        table,
        leases,
        base_ts,
    )
    request = _build_shortage_request(od, graph, params, 1, decision, "REQ-COMPARE-SHORTAGE-0001")
    return {
        "scenario": (
            f"{od_id}:把它的每条候选路径按'剩余可预约量'顶满预约表后再请求推荐 —— "
            "此时所有候选的瓶颈格子都在 x_safe 边界上,再加一辆必然超限"
        ),
        "od_id": od_id,
        "occupied_cells": table.occupied_cells(),
        "filled_candidates": filled,
        "status": decision["status"],
        "suggest": list(decision["suggest"]),
        "has_route": bool(decision["path"]),
        "request": request,
        "passed": (
            decision["status"] == reserve.REASON_NO_CAPACITY and not decision["path"]
        ),
    }


def _build_lease_release_evidence(
    graph: network.Graph,
    segments_state: dict[str, dict[str, Any]],
    params: dict[str, Any],
    od_pairs: list[dict[str, Any]],
    od_candidates: dict[str, list[list[str]]],
    base_ts: str,
) -> dict[str, Any]:
    """租约生命周期证据:登记一张**未确认采纳**的租约 → 超过 `lease_expire_s` → 释放占用归零。"""
    od = od_pairs[0]
    od_id = str(od.get("od_id") or "OD-01")
    table = reserve.SlotTable(graph, segments_state, params)
    leases: dict[str, dict[str, Any]] = {}
    decision = reserve.recommend(
        graph,
        {"od_id": od_id, "session_id": "S-compare-lease-demo"},
        od_candidates.get(od_id) or [],
        segments_state,
        params,
        table,
        leases,
        base_ts,
    )
    if decision["status"] != "ok":
        return {"passed": False, "note": "租约演示的首次推荐未通过约束,跳过(如实记录,不编造)"}
    occupied_before = table.occupied_cells()
    expire_ts = reserve.offset_iso(
        base_ts,
        float(params["lease_expire_s"]) + float(params["recompute_period_s"]),
    ).isoformat()
    released = reserve.release_expired(table, leases, expire_ts)
    occupied_after = table.occupied_cells()
    return {
        "registered_cells": len(decision["cells"]),
        "lease_expire_s": int(params["lease_expire_s"]),
        "expire_check_ts": expire_ts,
        "occupied_before": occupied_before,
        "released_sessions": released,
        "occupied_after": occupied_after,
        "passed": bool(released == ["S-compare-lease-demo"] and occupied_after == 0),
    }


def _search_k(params: dict[str, Any]) -> int:
    """候选生成的**搜索深度** K（Yen 先取 K 条原始候选，再按重叠度贪心筛）。

    为什么不再直接用 `decision.k_candidates`（站点包，写手是开发B）：
    契约 §二 / 手册 §7 锁的是「`alternatives` ≥ 2 条 + `no_alternative` 字段形状」，
    而手册明写「**K 与候选生成算法属做法，可自选并申报**」。真网只有 44 节点 / 61 段，
    按 K=3 取原始候选时，第一条最短路的近邻几乎全被重叠度 0.7 筛掉 → 四条 OD 全部
    只剩 1 条，页面备选恒为 0 条（业主 2026-10-28 反馈「先把备用线路搞定」）。

    所以搜索深度放到 `CANDIDATE_SEARCH_K`，筛完仍按重叠度取前 `k_candidates` 条——
    重叠度门槛（站点包里的裁定值）**一个不动**，不放宽「等价路径」的判定。
    """
    keep = int(params.get("k_candidates", 3))
    return max(keep, CANDIDATE_SEARCH_K)



    """从站点包 factors.json 的 demo_multipliers 里找"全封"级(倍率 ≤ 0)的因素。

    不写死因素编号:按文件顺序找第一条倍率 ≤ 0 的 demo 取值(样例里是 F07 交通事故·全封)。
    """
    for factor in factors_payload.get("factors") or []:
        for demo in factor.get("demo_multipliers") or []:
            try:
                multiplier = float(demo.get("multiplier"))
            except (TypeError, ValueError):
                continue
            if multiplier <= 0.0:
                return {
                    "factor_id": factor.get("factor_id"),
                    "name": factor.get("name"),
                    "label": demo.get("label"),
                    "multiplier": multiplier,
                }
    return None


def _run_reroute_demo(
    group_result: dict[str, Any],
    graph: network.Graph,
    params: dict[str, Any],
    factors_payload: dict[str, Any] | None,
    base_ts: str,
    window_s: float,
    tz: Any,
) -> dict[str, Any]:
    """突发场景下的前车再疏导演示(只验证机制,不参与 TC-17 三项判定)。

    1. 取评估窗口中点作为"突发发生时刻";
    2. 找出该时刻**在途**的已确认租约,按当前表估算它们已走到哪条边;
    3. 从站点包 factors.json 取"全封"级因素,把**在途车辆剩余路径里出现最多**的那条段封闭;
    4. 跑一个决策周期:三条件 + 滞回都满足的在途车辆改道,返回事件列表。
    """
    table: reserve.SlotTable = group_result["table"]
    leases: dict[str, dict[str, Any]] = group_result["leases"]
    closure = _find_closure_factor(factors_payload or {})
    if closure is None:
        return {
            "skipped": "站点包 factors.json 里没有倍率 ≤ 0 的 demo 因素,突发再疏导演示跳过",
            "events": [],
        }

    base_epoch_s = reserve.iso_to_epoch_s(base_ts)
    event_epoch_s = base_epoch_s + float(window_s) * REROUTE_DEMO_WINDOW_FRACTION
    event_ts = reserve.epoch_s_to_iso(event_epoch_s, tz)

    in_transit: dict[str, dict[str, Any]] = {}
    for session_id in sorted(leases):
        lease = leases[session_id]
        if not lease.get("confirmed"):
            continue
        start_epoch_s = float(lease["start_epoch_s"])
        if not (start_epoch_s <= event_epoch_s < start_epoch_s + float(lease["eta_s"])):
            continue
        lease["progress_edges"] = _estimate_progress(table, lease, event_epoch_s)
        remaining = list(lease["path"])[int(lease["progress_edges"]):]
        if not remaining:
            continue
        in_transit[session_id] = lease

    segment_counts: dict[str, int] = {}
    for lease in in_transit.values():
        for edge_id in list(lease["path"])[int(lease["progress_edges"]):]:
            segment_id = table.edge_segment(edge_id)
            segment_counts[segment_id] = segment_counts.get(segment_id, 0) + 1
    if not segment_counts:
        return {
            "skipped": f"突发时刻 {event_ts} 没有在途车辆,再疏导演示跳过(如实记录,不编事件)",
            "events": [],
        }
    closed_segment = sorted(segment_counts, key=lambda seg: (-segment_counts[seg], seg))[0]
    table.close_segment(closed_segment)

    events = reroute.check_and_reroute(
        table, in_transit, graph, params, event_ts, all_leases=leases
    )
    return {
        "event_ts": event_ts,
        "closure_source": closure,
        "closed_segment": closed_segment,
        "in_transit_leases": len(in_transit),
        "rerouted_count": len(events),
        "events": events,
        "note": (
            "突发注入来自站点包 factors.json 的 demo_multiplier(本例为交通事故·全封),"
            "只用于验证再疏导机制;TC-17 三项判定用突发注入前的统计口径"
        ),
    }


def _tc17_summary(
    group_metrics: dict[str, dict[str, Any]],
    baseline_orange_red: list[str],
    params: dict[str, Any],
    grading: dict[str, Any],
    guided_common_note: str | None = None,
) -> dict[str, Any]:
    """TC-17 三项判据的对比数据(③ 协同推荐 vs ② "此刻最快" 对照组)。

    `guided_common_note` 只替换"共同车辆群"那段说明文案(真网 / 样例口径不同);
    缺省用 --sample 的逐字节基线原文,保证样例产物不变。
    """
    experimental = group_metrics["cooperative"]
    control = group_metrics["fastest"]
    no_guidance = group_metrics["no_guidance"]
    eps_harm_s = float(params["eps_harm_s"])
    #: 解释口径冲突时**从站点包读实际值**,不把 demo 数值写死进产物文案
    x_safe_value = float(params["x_safe"])
    x_level_bounds = _x_level_bounds(grading)
    orange_bound = x_level_bounds[1] if len(x_level_bounds) >= 2 else None

    experimental_served: dict[str, float] = experimental["served"]
    control_served: dict[str, float] = control["served"]
    common_sessions = sorted(set(experimental_served) & set(control_served))
    common_experimental_s = sum(experimental_served[session] for session in common_sessions)
    common_control_s = sum(control_served[session] for session in common_sessions)

    new_vs_control = sorted(
        set(experimental["orange_red_segments"]) - set(control["orange_red_segments"])
    )
    new_vs_baseline = sorted(
        set(experimental["orange_red_segments"]) - set(baseline_orange_red)
    )
    if new_vs_control:
        details = "、".join(
            f"{segment_id}(实验组 x={experimental['segment_max_saturation'][segment_id]},"
            f"对照组 x={control['segment_max_saturation'][segment_id]})"
            for segment_id in new_vs_control
        )
        if orange_bound is None:
            conflict_text = "判级橙档边界缺失,无法比较 x_safe 与橙档边界"
        else:
            conflict_text = (
                f"`x_safe`({x_safe_value:g})高于判级橙档边界({orange_bound:g})"
            )
        orange_note = (
            f"判据未过:实验组相对对照组新增橙/红路段 {details}。"
            f"原因是站点包 demo 数值之间的口径冲突 —— {conflict_text},"
            "实验组在约束上限内合法登记就可能把原本黄档的路段推到橙档;"
            "**如实记录,不通过改代码常量 / 调阈值凑过**(待池·P 标定后由开发B 统一改站点包)"
        )
    else:
        orange_note = (
            "判据:实验组相对**对照组**不新增橙/红路段(拥堵没有因协同推荐被转移);"
            "相对初始快照的新增单列在 new_vs_baseline 里,如实留痕"
        )
    criteria = {
        "max_eta_increase_s": {
            "experimental": experimental["max_eta_increase_s"],
            "control": control["max_eta_increase_s"],
            "no_guidance": no_guidance["max_eta_increase_s"],
            "threshold_s": eps_harm_s,
            "passed": bool(experimental["max_eta_increase_s"] <= eps_harm_s),
            "note": (
                "实验组每一次准入都过了不伤害约束(逐次 harm_check ≤ eps_harm_s);"
                "对照组/不推荐组不做该约束,数字是同样口密度量出来的'后车会让前车慢多少'"
            ),
        },
        "no_new_orange_red_segments": {
            "experimental": experimental["orange_red_segments"],
            "control": control["orange_red_segments"],
            "no_guidance": no_guidance["orange_red_segments"],
            "baseline": baseline_orange_red,
            "experimental_count": len(experimental["orange_red_segments"]),
            "control_count": len(control["orange_red_segments"]),
            "new_vs_control": new_vs_control,
            "new_vs_baseline": new_vs_baseline,
            "passed": not new_vs_control,
            "note": orange_note,
        },
        "total_travel_time_s": {
            "metric": (
                "全网总行程时间(辆·秒)= Σ 每段每时段(背景车流 + 已预约) × 该时段服务时间;"
                "把被拖慢的背景车流也算进去,与 TC-17'全网总行程时间'的口径一致"
            ),
            "experimental": experimental["network_total_time_s"],
            "control": control["network_total_time_s"],
            "no_guidance": no_guidance["network_total_time_s"],
            "guided_common_set_s": {
                "experimental": round(common_experimental_s, 2),
                "control": round(common_control_s, 2),
                "common_vehicle_count": len(common_sessions),
                "experimental_all_s": experimental["total_travel_time_s"],
                "control_all_s": control["total_travel_time_s"],
                "note": (
                    guided_common_note
                    or (
                        "只统计被引导车辆自身 ETA(不含背景车流),按 TC-17 评测协议的共同车辆群口径;"
                        "样例路网上两组差异很小(被逼绕行的 OD-02 与避开的拥堵基本抵消),单列作参考"
                    )
                ),
            },
            "passed": bool(experimental["network_total_time_s"] < control["network_total_time_s"]),
            "note": (
                "按 TC-17 评测协议在**同一车辆群、同一评估窗口**上比较;"
                "网络口径把普通导航造成的背景车流拖慢也算进系统成本,"
                "车辆口径(guided_common_set_s)单列作对照"
            ),
        },
    }
    return {
        "criteria": criteria,
        "passed": all(bool(item["passed"]) for item in criteria.values()),
    }


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    """读一份可选输入(缺失返回 None,不静默编数据)。"""
    return network.read_json(path) if path.is_file() else None


def run_compare(cfg: dict[str, Any]) -> int:
    """--compare:同一份输入跑 ① 不推荐 / ② 此刻最快 / ③ 协同推荐,输出 TC-17 三组对比数据。

    `--network real` 时同一套机制在真网(站点登记表:段号前缀/段数按站点)上跑;数据只换装载层,机制不按 source 分支。
    """
    dataset = _load_dataset(cfg)
    out_dir: Path = cfg["out_dir"]
    stations_dir: Path = cfg["stations_dir"]

    graph = dataset["graph"]
    segments_state = dataset["segments_state"]
    thresholds = dataset["thresholds"]
    params = thresholds["decision"]
    grading = thresholds["grading"]
    points = dataset["points"]
    factors_payload = dataset["factors_payload"]

    demand = dataset["demand"]
    od_pairs = dataset["od_pairs"]
    od_by_id = {str(od.get("od_id") or f"OD-{index + 1:02d}"): od for index, od in enumerate(od_pairs)}

    base_ts = dataset["ts"]
    tz = reserve.tzinfo_of(base_ts)

    vehicles, window_s = _scenario_vehicles(demand, dataset["segments_payload"], base_ts)
    base_epoch_s = reserve.iso_to_epoch_s(base_ts)
    evaluation_end_epoch_s = base_epoch_s + float(window_s)
    od_candidates = _static_candidates(graph, od_pairs, segments_state, params)
    fastest_paths = {
        od_id: _fastest_path_of(graph, candidates_paths, segments_state, params)
        for od_id, candidates_paths in od_candidates.items()
    }
    habitual_paths = {
        od_id: _habitual_path(graph, od, params) for od_id, od in od_by_id.items()
    }

    group_defs = (
        ("no_guidance", "① 不推荐(自由流习惯路线)"),
        ("fastest", "② 此刻最快(现有 --sample 的普通导航口径)"),
        ("cooperative", "③ 协同推荐(时段预约 + 不伤害前车 + 再疏导)"),
    )
    group_results: dict[str, dict[str, Any]] = {}
    group_metrics: dict[str, dict[str, Any]] = {}
    for group, label in group_defs:
        result = _run_compare_group(
            group=group,
            group_label=label,
            graph=graph,
            segments_state=segments_state,
            params=params,
            od_by_id=od_by_id,
            vehicles=vehicles,
            od_candidates=od_candidates,
            fastest_paths=fastest_paths,
            habitual_paths=habitual_paths,
            tz=tz,
        )
        group_results[group] = result
        group_metrics[group] = _compare_group_metrics(
            result, segments_state, grading, base_epoch_s, evaluation_end_epoch_s
        )

    baseline_orange_red = _baseline_orange_red(segments_state, grading)
    treatment = _compare_treatment(
        group_results,
        group_metrics,
        graph,
        segments_state,
        grading,
        params,
        base_epoch_s,
        evaluation_end_epoch_s,
        tz,
    )
    tc17 = _tc17_summary(
        group_metrics,
        baseline_orange_red,
        params,
        grading,
        guided_common_note=dataset["compare_guided_common_note"],
    )

    reroute_demo = _run_reroute_demo(
        group_results["cooperative"], graph, params, factors_payload, base_ts, window_s, tz
    )
    rerouted_sessions = {
        str(event["session_id"]) for event in reroute_demo.get("events") or []
    }

    requests: list[dict[str, Any]] = []
    requests_without_reservation: list[str] = []
    for index, od in enumerate(od_pairs):
        od_id = str(od.get("od_id") or f"OD-{index + 1:02d}")
        admissions = group_results["cooperative"]["admissions_by_od"].get(od_id) or []
        if not admissions:
            # 该 OD 一辆都没通过约束:如实输出 capacity_shortage,不编推荐(不会出现在样例里)
            requests_without_reservation.append(od_id)
            demo_candidates = od_candidates.get(od_id) or []
            demo_table = reserve.SlotTable(graph, segments_state, params)
            shortage_decision = reserve.recommend(
                graph,
                {"od_id": od_id, "session_id": f"S-compare-{od_id}-none"},
                demo_candidates,
                segments_state,
                params,
                demo_table,
                {},
                base_ts,
            )
            requests.append(
                _build_shortage_request(
                    od,
                    graph,
                    params,
                    index + 1,
                    shortage_decision,
                    f"REQ-COMPARE-{index + 1:04d}",
                )
            )
            continue
        chosen = next(
            (
                admission
                for admission in admissions
                if str(admission["vehicle"]["session_id"]) in rerouted_sessions
            ),
            admissions[0],
        )
        lease = chosen["decision"]["lease"]
        reroute_block = {
            "count": int(lease.get("reroute_count") or 0),
            "reason": lease.get("reroute_reason") if int(lease.get("reroute_count") or 0) > 0 else None,
        }
        requests.append(
            _build_cooperative_request(
                od,
                graph,
                segments_state,
                params,
                points,
                index + 1,
                chosen["decision"],
                reroute_block,
            )
        )

    capacity_shortage_evidence = _build_capacity_shortage_evidence(
        graph, segments_state, params, od_pairs, od_candidates, base_ts
    )
    lease_release_evidence = _build_lease_release_evidence(
        graph, segments_state, params, od_pairs, od_candidates, base_ts
    )

    # 真网产物:补 length_m 可追溯 + 方向/车道 legs + 段号命名空间硬校验
    # (样例基线不做,保持逐字节不变)
    if dataset["route_lengths"]:
        realnet.attach_route_lengths(requests, graph)
        realnet.attach_route_topology(requests, graph)
        realnet.assert_segment_namespace(requests, dataset["seg_prefix"])

    network.ensure_out_dir(out_dir)

    routes: dict[str, Any] = {
        "ts": base_ts,
        "is_simulated": True,
        "mode": "compare",
    }
    if dataset["network_block"]:
        routes["network"] = dataset["network_block"]
        routes["od_derivation"] = dataset["od_derivation"]
        routes["segments_source"] = dataset["segments_source"]
    routes["schema_note"] = dataset["compare_schema_note"]
    routes["requests"] = requests
    routes["comparison"] = {
            "scenario": {
                "base_ts": base_ts,
                "window_sec": window_s,
                "vehicle_count": len(vehicles),
                "od_count": len(od_pairs),
                "group_labels": {group: label for group, label in group_defs},
                "note": dataset["compare_scenario_note"],
                "counts_note": (
                    "TC-17 评测协议四计数在本引擎侧评估里的口径:attempted=需求车辆总数;"
                    "inserted=成功登记预约的车(=completed + in_transit);not_entered=被两条约束拒绝的车;"
                    "removed=0(评估期不做在线增删)。completed 按'预计到达时刻落在评估窗口内'统计,"
                    "in_transit=窗口结束时仍未到达;四计数自洽:attempted = inserted + not_entered,"
                    "inserted = completed + in_transit;**inserted 不等于 attempted**(有未准入车时 attempted 更大)"
                ),
                "reroute_demo": reroute_demo,
            },
            "tc17": tc17,
            "treatment": treatment,
            "groups": {
                group: {
                    "group_label": group_metrics[group]["group_label"],
                    "attempted": group_metrics[group]["attempted"],
                    #: inserted = 成功登记的车(= completed + in_transit);不能直接用 attempted,
                    #: 有未准入车时那样会虚报插入数(2026-10-17 快速独立审查发现 3)
                    "inserted": group_metrics[group]["completed"] + group_metrics[group]["in_transit"],
                    "completed": group_metrics[group]["completed"],
                    "in_transit": group_metrics[group]["in_transit"],
                    "not_entered": group_metrics[group]["not_entered"],
                    "removed": group_metrics[group]["removed"],
                    "max_eta_increase_s": group_metrics[group]["max_eta_increase_s"],
                    "total_travel_time_s": group_metrics[group]["total_travel_time_s"],
                    "network_total_time_s": group_metrics[group]["network_total_time_s"],
                    "orange_red_segments": group_metrics[group]["orange_red_segments"],
                    "segment_max_saturation": group_metrics[group]["segment_max_saturation"],
                }
                for group, _label in group_defs
            },
            "capacity_shortage_evidence": capacity_shortage_evidence,
            "lease_release_evidence": lease_release_evidence,
            "requests_without_reservation": requests_without_reservation,
    }
    written: dict[str, int] = {}
    written["routes.json"] = network.write_json(out_dir / "routes.json", routes)
    network.assert_artifact(out_dir / "routes.json")

    log = {
        "ts": base_ts,
        "is_simulated": True,
        "mode": "compare",
        "scenario": cfg.get("scenario", "compare"),
        "seed": cfg.get("seed", 0),
        **dataset["log_source_fields"],
        "stations_dir": str(stations_dir),
        "node_count": len(graph.node_ids),
        "edge_count": len(graph._edges),  # noqa: SLF001 —— 只读计数,给日志看
        "od_count": len(od_pairs),
        "vehicle_count": len(vehicles),
        "window_sec": window_s,
        "is_reservation_effective": True,
        "decision_params_used": {key: params[key] for key in sorted(params)},
        "tc17": {
            "passed": tc17["passed"],
            "criteria_passed": {
                key: bool(value["passed"]) for key, value in tc17["criteria"].items()
            },
        },
        "treatment_metrics": {
            key: {
                "before": treatment["metrics"][key]["before"],
                "after": treatment["metrics"][key]["after"],
                "delta": treatment["metrics"][key]["delta"],
            }
            for key in ("queue", "duration", "saturation")
        },
        "groups": {
            group: {
                "attempted": group_metrics[group]["attempted"],
                "inserted": group_metrics[group]["inserted"],
                "completed": group_metrics[group]["completed"],
                "in_transit": group_metrics[group]["in_transit"],
                "not_entered": group_metrics[group]["not_entered"],
                "removed": group_metrics[group]["removed"],
                "max_eta_increase_s": group_metrics[group]["max_eta_increase_s"],
                "total_travel_time_s": group_metrics[group]["total_travel_time_s"],
                "network_total_time_s": group_metrics[group]["network_total_time_s"],
            }
            for group, _label in group_defs
        },
        "capacity_shortage_passed": bool(capacity_shortage_evidence["passed"]),
        "lease_release_passed": bool(lease_release_evidence["passed"]),
        "rerouted_count": int(reroute_demo.get("rerouted_count") or 0),
        "written_bytes": written,
        "note": (
            "--compare 的对照产物:① 不推荐(自由流习惯路线) ② 此刻最快(现有 --sample 口径) "
            "③ 协同推荐(时段预约 + 不伤害前车 + 再疏导);TC-17 三项判据见 routes.json 的 comparison.tc17,"
            "capacity_shortage 与租约释放的证据见 comparison 里的同名块"
        ),
    }
    log.update(dataset["log_extra"])
    written["run_log.json"] = network.write_json(out_dir / "run_log.json", log)
    network.assert_artifact(out_dir / "run_log.json")
    return 0


def parse_args(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="work/engine 模块统一入口")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="用 samples/ 的 7 节点样例网跑通链路(不依赖上游/SUMO;产物是逐字节基线)",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="三组对照:① 不推荐 ② 此刻最快 ③ 协同推荐(TC-17 举证);可与 --sample 或 --network real 同用",
    )
    parser.add_argument(
        "--d3",
        action="store_true",
        dest="d3",
        help=(
            "TC-12:对每个 OD 追加 1 个 D3(往返)代表请求,做实 pickup_route 与三段预约;"
            "默认关闭;与 --compare 互斥(避免扰动 TC-17 车辆群);真网点位缺失时跳过并留痕"
        ),
    )
    parser.add_argument(
        "--network",
        choices=("sample", "real"),
        default=None,
        help=(
            "数据来源:sample=7 节点样例网(SEG-###)/ real=站点登记表里的真网(段号前缀/段数按站点);"
            "缺省 None 时需显式 --sample 或 --network real(不改变旧行为)"
        ),
    )
    parser.add_argument(
        "--site-id",
        default=None,
        dest="site_id",
        help="真网站点 id(读 work/twin/site-ranges.json;缺省用登记表 default_site;隐含 --network real)",
    )
    parser.add_argument(
        "--site-ranges",
        default=str(DEFAULT_SITE_RANGES),
        dest="site_ranges",
        help="站点范围登记表路径(默认 work/twin/site-ranges.json)",
    )
    parser.add_argument(
        "--segments",
        default=None,
        help=(
            "真网用的上游 segments 快照路径(如 work/perception/out/latest/segments_video.json);"
            "缺省 = 无上游指标,按 q_vph=0 + 站点包 defaults 降级并留 note"
        ),
    )
    parser.add_argument(
        "--demand-vph",
        type=float,
        default=None,
        dest="demand_vph",
        help="真网每个推导 OD 的演示需求(辆/小时;缺省用 realnet.DEMO_DEMAND_VPH,属演示假设值)",
    )
    parser.add_argument(
        "--out",
        default=None,
        dest="out_dir",
        help=(
            "输出目录(缺省:样例 → work/engine/out;真网 → work/engine/out/real;"
            "真网 --compare → work/engine/out/real/compare)"
        ),
    )
    parser.add_argument("--samples", default=str(DEFAULT_SAMPLES_DIR), dest="samples_dir")
    parser.add_argument("--stations", default=str(DEFAULT_STATIONS_DIR), dest="stations_dir")
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--seed", type=int, default=0)
    ns, _extra = parser.parse_known_args(argv)

    chosen_network = ns.network
    if chosen_network is None:
        if ns.site_id or ns.segments:
            chosen_network = "real"
        elif ns.sample:
            chosen_network = "sample"
    if chosen_network == "sample" and ns.site_id:
        raise SystemExit(
            "--site-id 只用于 --network real;--sample 是 7 节点样例网(SEG-###),不读真网登记表"
        )
    if chosen_network == "real" and ns.sample:
        raise SystemExit(
            "--sample 与 --network real 互斥:样例基线(7 节点 SEG-###)与站点真网是两张网"
        )
    if ns.compare and ns.d3:
        raise SystemExit(
            "--compare 与 --d3 互斥:--compare 的三组对照(TC-17 车辆群)不注入 D3 代表请求;"
            "请单独用 --sample --d3 或 --network real --d3"
        )
    if ns.out_dir:
        # 显式传参优先:调用方要写哪就写哪(--out 的约定不变)
        out_dir = Path(ns.out_dir)
    elif chosen_network == "real":
        # 真网两种 mode 分目录:默认 → out/real/;--compare → out/real/compare/。
        # 否则后跑的会覆盖先跑的 routes.json,下游按固定路径取用时可能拿到错 mode 的产物。
        # 多站(IKNB9F):非默认站写 out/real/sites/<site_id>/,与站点 Z 的 out/real 互不覆盖;
        # 默认站(登记表 default_site)保持既有 out/real 路径不变(老路径/测试不退化)。
        base_real = DEFAULT_REAL_OUT_DIR
        if ns.site_id:
            registry = realnet.load_site_ranges(Path(ns.site_ranges))
            default_site = str(registry.get("default_site") or "")
            if default_site and ns.site_id != default_site:
                base_real = DEFAULT_REAL_OUT_DIR / "sites" / str(ns.site_id)
        out_dir = (base_real / "compare") if ns.compare else base_real
    else:
        out_dir = DEFAULT_OUT_DIR
    scenario = ns.scenario or ("real" if chosen_network == "real" else "sample")
    return {
        "network": chosen_network,
        "site_id": ns.site_id,
        "site_ranges": Path(ns.site_ranges),
        "segments": ns.segments,
        "demand_vph": ns.demand_vph,
        "sample": ns.sample,
        "compare": ns.compare,
        "d3": ns.d3,
        "out_dir": out_dir,
        "samples_dir": Path(ns.samples_dir),
        "stations_dir": Path(ns.stations_dir),
        "scenario": scenario,
        "seed": ns.seed,
    }


def main(argv: list[str] | None = None) -> int:
    cfg = parse_args(argv)
    if cfg["network"] is None:
        raise NotImplementedError(
            "请显式选择数据来源:--sample(7 节点样例网对照基线)或 --network real"
            "(站点登记表里的真网,段号前缀/段数按站点)。真网入口不再依赖 SUMO;用法见 work/engine/README.md"
        )
    if cfg["compare"]:
        return run_compare(cfg)
    if cfg["network"] == "real":
        return run_real(cfg)
    return run_sample(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
