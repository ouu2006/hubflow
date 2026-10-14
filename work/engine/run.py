"""work/engine 模块统一入口(开发规范 §3 / §6:每个模块一个 run.py,加 --sample 能单独跑)。

输入:`work/engine/samples/` 的样例(网络 / 现状 / OD)+ `stations/thresholds.json` 的 decision 组
输出:`work/engine/out/routes.json`(推荐 + 备选)+ `out/run_log.json`
口径:
  - `--sample` **不依赖上游、不依赖 SUMO**,读样例写 out/,**不许覆盖样例输入**;
  - **样例数据走 `samples/`,参数走 `stations/`** —— 后者是"引擎真的读了站点包"的证明点
    (改 `alpha` 一个数,产物 `eta` 跟着动);
  - ⚠️ **W0/W1 边界**:本入口产出的是按 BPR 算出的**"此刻最快"**(即手册 7.6 的**对照组口径**),
    **不是协同推荐** —— 时段容量预约与不伤害前车约束是 W3 的活,见 reserve.py。
    因此 `reservation` 恒为 `null`,**绝不编一个 `passed: true` 出来**。

用法:
  python work/engine/run.py --sample
  python work/engine/run.py --sample --out /tmp/x --samples ... --stations ...
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import candidates
import network
import reserve

HERE = Path(__file__).resolve().parent
DEFAULT_SAMPLES_DIR = HERE / "samples"
DEFAULT_OUT_DIR = HERE / "out"
#: 站点包在仓库根:`work/engine/` → `work/` → 仓库根 → `stations/`
DEFAULT_STATIONS_DIR = HERE.parents[1] / "stations"

SAMPLE_FILES = {
    "network": "network_sample.json",
    "segments": "segments_sample.json",
    # 与 stations/demand.json 同形:OD 数组的容器键就是 od(开发规范 §6「样例就是契约的镜子」)
    "demand": "demand_sample.json",
}

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

    sections = {str(graph.edge(eid).get("section")) for eid in path}
    for edge_id in graph.out_edges(node_id):
        sections.add(str(graph.edge(edge_id).get("section")))
    for point in points:
        if point.get("type") == node_type and str(point.get("segment_id")) in sections:
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
        k=int(params.get("k_candidates", 3)),
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
    dst_type = str(graph.node(dst).get("type"))
    if dst_type == "pickup":
        detail = f";对应点位 {stop['point_id']}" if stop else ";上客点位未在站点包登记"
        notes.append("终点是上客点,不写进 arrival_route.dropoff_point" + detail)
    elif dst_type == "dropoff" and stop is None:
        notes.append(f"落客点位未在站点包登记({dst} 的相邻路段里查不到 type=dropoff 的点位)")

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


def run_sample(cfg: dict[str, Any]) -> int:
    """用 samples/ + stations/thresholds.json 走完整链路,不依赖上游、不依赖 SUMO。"""
    samples_dir: Path = cfg["samples_dir"]
    out_dir: Path = cfg["out_dir"]

    payloads = load_samples(samples_dir)
    graph = network.Graph(payloads["network"])
    segments_state = network.load_segments(samples_dir / SAMPLE_FILES["segments"])
    thresholds = network.load_thresholds(cfg["stations_dir"] / "thresholds.json")
    params = thresholds["decision"]
    # 点位表也读站点包:终点要折成**点位 id**(Issue #94 第①条),引擎里不许写站点相关的字符串常量
    points = load_points(cfg["stations_dir"])

    od_pairs = payloads["demand"].get("od")
    if not isinstance(od_pairs, list) or not od_pairs:
        raise ValueError("样例 demand 的 od 缺失或为空(容器键与 stations/demand.json 一致)")

    # demand.json 没有 ts,时间戳取 segments 的
    now_ts = str(payloads["segments"].get("ts") or "")
    if not now_ts:
        raise SystemExit("样例 segments 缺 ts 字段")

    network.ensure_out_dir(out_dir)

    requests = [
        build_request(od, graph, segments_state, params, points, i + 1, now_ts)
        for i, od in enumerate(od_pairs)
    ]

    routes = {
        "ts": now_ts,
        "is_simulated": True,
        "mode": "sample",
        "schema_note": (
            "每个 requests[] 元素就是 POST /api/traffic/route/recommend 的响应体形状"
            "(契约第二节);这里包一层信封是为了让 --sample 一次跑完 ≥3 个 OD 对(M1-4 前置)"
        ),
        "requests": requests,
    }
    written: dict[str, int] = {}
    written["routes.json"] = network.write_json(out_dir / "routes.json", routes)
    network.assert_artifact(out_dir / "routes.json")

    log = {
        "ts": now_ts,
        "is_simulated": True,
        "mode": "sample",
        "scenario": cfg.get("scenario", "sample"),
        "seed": cfg.get("seed", 0),
        "samples_dir": samples_dir.name,
        "stations_dir": str(cfg["stations_dir"]),
        "node_count": len(graph.node_ids),
        "edge_count": len(graph._edges),  # noqa: SLF001 —— 只读计数,给日志看
        "od_count": len(od_pairs),
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


def parse_args(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="work/engine 模块统一入口")
    parser.add_argument("--sample", action="store_true", help="用 samples/ 跑通链路(不依赖上游/SUMO)")
    parser.add_argument("--out", default=str(DEFAULT_OUT_DIR), dest="out_dir")
    parser.add_argument("--samples", default=str(DEFAULT_SAMPLES_DIR), dest="samples_dir")
    parser.add_argument("--stations", default=str(DEFAULT_STATIONS_DIR), dest="stations_dir")
    parser.add_argument("--scenario", default="sample")
    parser.add_argument("--seed", type=int, default=0)
    ns, _extra = parser.parse_known_args(argv)
    return {
        "sample": ns.sample,
        "out_dir": Path(ns.out_dir),
        "samples_dir": Path(ns.samples_dir),
        "stations_dir": Path(ns.stations_dir),
        "scenario": ns.scenario,
        "seed": ns.seed,
    }


def main(argv: list[str] | None = None) -> int:
    cfg = parse_args(argv)
    if not cfg["sample"]:
        raise NotImplementedError(
            "真链路待后续 issue:需要 SUMO 孪生数据(work/twin)与站点包路网(network.json,Issue #37)"
        )
    return run_sample(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
