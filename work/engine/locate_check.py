#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TC-18 定位与地图匹配验收驱动(T4 任务卡 §5)。

**这个文件不接 run.py 主链** —— 它只是把 `locate.py` 的一期直读与二期匹配器
按 TC-18 口径跑成可复核的数字。孪生真值快照从 `--vehicles` 进,图几何从
`--network` / `--geometry` 进。

TC-18 两项判定(work/engine/README.md 第三节):

| 项 | 口径 |
|---|---|
| ① `truth_match_rate` | 无噪声逐车直读,`locate()` 返回的 `segment_id` 与真值一致率 **== 1.0** |
| ② `noise_accuracy` | 对真值加 **σ = 20 m** 噪声后,路段匹配正确率 **≥ 0.90**【demo 目标值】 |

测试协议(任务卡 §5,写在这里以便复核):

1. **无噪声**:逐车直读 —— `locate()` 读 `segment_id` / `offset_m`,与真值逐字段比;
2. **有噪声**:为每辆车**沿其真值路段**造一条短轨迹(offset `0 → L`,步长
   `--step-m`),轨迹点只由真值 + 图几何算出;再对每个点 `add_gnss_noise()`
   (σ 与种子都固定);然后**顺序匹配**(用上一匹配结果做连续性);
3. **匹配器不读真值**:喂给 `match_sequence()` 的点串只带 `x` / `y` / `heading`,
   `segment_id` / `offset_m` 等真值键**一律剥掉**;
4. 每档 σ 单独统计,输出 JSON + stdout 摘要。

用法:

    python work/engine/locate_check.py --vehicles <path> --network sample \
        --sigmas 10,20,30 --seed 42 --out <json>

    # 有几何时(带 WGS-84 折线 + 数据自带的 anchor_lonlat)才能跑第②项:
    python work/engine/locate_check.py --vehicles <path> --network real \
        --geometry <path.json> --sigmas 10,20,30 --seed 42 --out <json>

⚠️ **坐标系前置**:第②项要把点投影到**同一个局部米制平面**才能算距离。投影锚点
   必须来自输入数据(`anchor_lonlat`);图只有米制 `x/y`、又没有记锚点时,**不猜原点**,
   第②项按"无法建立坐标系"降级留痕(见 `gate_reason`),不编坐标。
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import locate
import network

#: 轨迹步长默认 30 m(任务卡 §5:步长 20–50 m)
DEFAULT_STEP_M = 30.0


# --------------------------------------------------------------------- 输入装载


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"缺输入文件:{path}")
    with path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    if not isinstance(payload, dict) or not payload:
        raise SystemExit(f"输入顶层为空或不是对象:{path}")
    return payload


def load_vehicles(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """读 `vehicles.json` 信封(契约第四节:顶层 `ts` / `is_simulated` + `vehicles` 数组)。"""
    payload = read_json(path)
    vehicles = payload.get("vehicles")
    if not isinstance(vehicles, list):
        raise SystemExit(f"{path} 缺 vehicles 数组(契约第四节:不要写成裸数组)")
    return payload, vehicles


def load_network_payload(root: Path, which: str) -> dict[str, Any]:
    """`--network sample|real` → 引擎自己的统一图。"""
    if which == "sample":
        path = root / "work" / "engine" / "samples" / "network_sample.json"
    elif which == "real":
        path = root / "stations" / "network.json"
    else:  # argparse 的 choices 已经挡过,这里只是别静默放行
        raise SystemExit(f"--network 只认 sample / real,收到 {which!r}")
    return read_json(path)


def try_build_graph(payload: dict[str, Any]) -> network.Graph | None:
    """尽量把统一图建成 `network.Graph`;建不成就给 `None`(调用方照实降级)。

    非引擎图形状的输入(例如孪生 netpack)建不起来是正常的 —— 那时
    `locate()` 的 `route_progress` 如实给 `null`,不拿别的东西顶。
    """
    try:
        return network.Graph(payload)
    except Exception:
        return None


def network_frame(payload: dict[str, Any]) -> str:
    """判定统一图给的几何是什么坐标系。

    - 边带 `coords` / 节点带 `lon`+`lat` → `lonlat`(投影后可用);
    - 只有节点 `x`/`y` → `xy`(局部米制,**与车辆 lon/lat 对不上**);
    - 什么都没有 → `none`。

    判据只看**数据里有什么字段**,不看注释 —— 样例图的 `attributes.crs` 写着
    `WGS-84` 却又给 `node_xy_unit: m`,两者矛盾,不能拿来当坐标系用。
    """
    edges = payload.get("edges") or []
    if any(edge.get("coords") for edge in edges):
        return "lonlat"
    nodes = payload.get("nodes") or []
    if any(n.get("lon") is not None and n.get("lat") is not None for n in nodes):
        return "lonlat"
    if any(n.get("x") is not None and n.get("y") is not None for n in nodes):
        return "xy"
    return "none"


def anchor_of(payload: dict[str, Any]) -> tuple[float, float] | None:
    """投影锚点:只认数据里显式记录的 `anchor_lonlat`,不猜。"""
    for candidate in (
        payload.get("anchor_lonlat"),
        (payload.get("attributes") or {}).get("anchor_lonlat"),
        (payload.get("params") or {}).get("anchor_lonlat"),
    ):
        if candidate:
            return float(candidate[0]), float(candidate[1])
    return None


def segment_edges(payload: dict[str, Any], segment_id: str) -> list[dict[str, Any]]:
    return [
        edge
        for edge in payload.get("edges") or []
        if str(edge.get("section") or edge.get("segment_id") or "") == segment_id
    ]


# --------------------------------------------------------------------- 轨迹生成(只用真值造输入)


def trajectory_along_segment(
    edges: list[dict[str, Any]],
    anchor: tuple[float, float],
    step_m: float,
) -> list[dict[str, Any]]:
    """沿一条(可能多边拼接的)路段造 offset 0→L 的轨迹点。

    点只由**真值路段 + 图几何**算出:折线在局部米制平面里等里程采样,再把采样点
    反算回经纬度(`local_to_lonlat` 是 `lonlat_to_local` 的严格互逆,所以这一趟
    往返无损),方位取该处切线方向。多边同 section 时按边顺序首尾相接;接不上的
    边跳过(不编坐标)。
    """
    polylines: list[list[tuple[float, float]]] = []
    for edge in edges:
        coords = edge.get("coords")
        if not coords:
            continue
        polylines.append(
            [
                locate.lonlat_to_local(float(c[0]), float(c[1]), anchor[0], anchor[1])
                for c in coords
            ]
        )
    polylines = [p for p in polylines if len(p) >= 2]
    if not polylines:
        return []

    chain: list[tuple[float, float]] = []
    for polyline in polylines:
        if not chain:
            chain = list(polyline)
            continue
        gap = math.hypot(polyline[0][0] - chain[-1][0], polyline[0][1] - chain[-1][1])
        chain.extend(polyline if gap > 1.0 else polyline[1:])  # 1 m 容差
    if len(chain) < 2:
        return []

    cumulative = [0.0]
    for (ax, ay), (bx, by) in zip(chain, chain[1:]):
        cumulative.append(cumulative[-1] + math.hypot(bx - ax, by - ay))
    total = cumulative[-1]
    if total <= 0:
        return []

    points: list[dict[str, Any]] = []
    offset = 0.0
    while offset <= total + 1e-9:
        index = 0
        while index + 1 < len(cumulative) and cumulative[index + 1] < offset:
            index += 1
        span = cumulative[index + 1] - cumulative[index] if index + 1 < len(cumulative) else 0.0
        ratio = (offset - cumulative[index]) / span if span > 0 else 0.0
        (ax, ay) = chain[index]
        (bx, by) = chain[min(index + 1, len(chain) - 1)]
        px = ax + ratio * (bx - ax)
        py = ay + ratio * (by - ay)
        lon, lat = locate.local_to_lonlat(px, py, anchor[0], anchor[1])
        points.append(
            {
                "lon": lon,
                "lat": lat,
                "x": px,
                "y": py,
                "heading": locate.bearing_deg(ax, ay, bx, by),
                "offset_m": round(offset, 3),
            }
        )
        offset += step_m
    return points


# --------------------------------------------------------------------- 两项统计


def run_direct_read(
    vehicles: list[dict[str, Any]], graph: network.Graph | None
) -> dict[str, Any]:
    """TC-18①:无噪声逐车直读。

    比 `segment_id` / `offset_m` 与真值是否一致;另外如实统计 `route_progress`
    算不算得出来(图给不出路段长度时是 `null`,不当 0、也不编)。
    """
    checked = 0
    matched = 0
    out_of_range = 0
    progress_available = 0
    mismatches: list[dict[str, Any]] = []

    for vehicle in vehicles:
        position = {
            "segment_id": vehicle.get("segment_id"),
            "offset_m": vehicle.get("offset_m"),
            "lon": vehicle.get("lon"),
            "lat": vehicle.get("lat"),
        }
        result = locate.locate(
            session_id="tc18-direct-read",
            position=position,
            heading=vehicle.get("heading"),
            ts="1970-01-01T00:00:00+08:00",
            graph=graph,
        )
        truth_segment = vehicle.get("segment_id")
        truth_offset = vehicle.get("offset_m")
        checked += 1
        ok = result.get("segment_id") == truth_segment and result.get("offset_m") == (
            float(truth_offset) if truth_offset is not None else None
        )
        if ok:
            matched += 1
        else:
            mismatches.append(
                {
                    "vehicle_id": vehicle.get("vehicle_id"),
                    "truth_segment_id": truth_segment,
                    "truth_offset_m": truth_offset,
                    "locate_segment_id": result.get("segment_id"),
                    "locate_offset_m": result.get("offset_m"),
                }
            )
        if result.get("route_progress") is not None:
            progress_available += 1
        if result.get("gate_reason") == locate.PROGRESS_OUT_OF_RANGE:
            out_of_range += 1

    return {
        "checked": checked,
        "matched": matched,
        "truth_match_rate": (matched / checked) if checked else None,
        "route_progress_available": progress_available,
        "progress_out_of_range": out_of_range,
        "mismatches": mismatches,
        "gate_reason": None if checked else "no_vehicles",
    }


def run_noise(
    vehicles: list[dict[str, Any]],
    network_payload: dict[str, Any],
    sigmas: list[float],
    seed: int,
    step_m: float,
) -> dict[str, Any]:
    """TC-18②:各 σ 的路段匹配正确率。

    轨迹生成只用真值造输入;匹配器只拿到 `x` / `y` / `heading`,**不读真值字段**。
    """
    anchor = anchor_of(network_payload)
    frame = network_frame(network_payload)
    if frame != "lonlat" or anchor is None:
        return {
            "status": "unavailable",
            "gate_reason": "geometry_not_projectable" if frame == "none" else "geometry_frame_mismatch",
            "detail": (
                f"图几何坐标系={frame},anchor_lonlat={'有' if anchor else '无'}。"
                "第②项要把车辆 lon/lat 与图几何投到同一局部米制平面才能算距离;"
                "缺锚点不猜原点(任务卡:图没有几何、无法算距离 → 停,不编坐标)。"
                "引擎统一图样例只有米制 x/y 且不记锚点,与车辆 lon/lat 对不上。"
            ),
            "sigmas": {},
        }

    geometry = locate.build_geometry(network_payload)
    if not geometry:
        return {
            "status": "unavailable",
            "gate_reason": "no_candidate_geometry",
            "detail": "统一图里没有一条边能投影出折线,候选集为空。",
            "sigmas": {},
        }

    per_vehicle: list[dict[str, Any]] = []
    for vehicle in vehicles:
        segment_id = vehicle.get("segment_id")
        edges = segment_edges(network_payload, str(segment_id))
        points = trajectory_along_segment(edges, anchor, step_m)
        if not points:
            per_vehicle.append(
                {
                    "vehicle_id": vehicle.get("vehicle_id"),
                    "segment_id": segment_id,
                    "status": "unavailable",
                    "gate_reason": "truth_segment_has_no_geometry",
                    "points": 0,
                }
            )
            continue
        per_vehicle.append(
            {
                "vehicle_id": vehicle.get("vehicle_id"),
                "segment_id": segment_id,
                "status": "ok",
                "gate_reason": None,
                "points": len(points),
                "trajectory": points,
            }
        )

    results: dict[str, Any] = {}
    for sigma in sigmas:
        total = 0
        correct = 0
        trajectories_full = 0
        trajectories_counted = 0
        wrong: list[dict[str, Any]] = []
        for entry in per_vehicle:
            if entry["status"] != "ok":
                continue
            # 逐点加噪:每点种子 = seed + 轨迹内序号(确定性派生,连跑两遍逐字节一致);
            # 加噪在经纬度上做(任务卡 §3 的公式),再投回同一局部平面喂匹配器。
            noisy_points = []
            for index, point in enumerate(entry["trajectory"]):
                noisy = locate.add_gnss_noise(
                    {"lon": point["lon"], "lat": point["lat"], "heading": point["heading"]},
                    sigma,
                    seed + index,
                )
                east, north = locate.lonlat_to_local(
                    noisy["lon"], noisy["lat"], anchor[0], anchor[1]
                )
                # 剥掉真值字段:匹配器只准看 x / y / heading
                noisy_points.append({"x": east, "y": north, "heading": point["heading"]})
            matched = locate.match_sequence(noisy_points, geometry)
            for point, result in zip(entry["trajectory"], matched):
                total += 1
                if str(result.get("section")) == str(entry["segment_id"]):
                    correct += 1
                elif len(wrong) < 20:
                    wrong.append(
                        {
                            "vehicle_id": entry["vehicle_id"],
                            "truth_segment_id": entry["segment_id"],
                            "truth_offset_m": point["offset_m"],
                            "matched_section": result.get("section"),
                            "matched_edge_id": result.get("edge_id"),
                            "distance_m": result.get("distance_m"),
                            "match_confidence": result.get("match_confidence"),
                        }
                    )
            trajectories_counted += 1
            if all(str(r.get("section")) == str(entry["segment_id"]) for r in matched):
                trajectories_full += 1
        results[f"{sigma:g}"] = {
            "sigma_m": sigma,
            "status": "ok" if total else "unavailable",
            "points_total": total,
            "points_correct": correct,
            "noise_accuracy": (correct / total) if total else None,
            "trajectories": trajectories_counted,
            "trajectories_all_correct": trajectories_full,
            "trajectory_accuracy": (trajectories_full / trajectories_counted)
            if trajectories_counted
            else None,
            "wrong_examples": wrong,
            "gate_reason": None if total else "no_points",
        }

    return {
        "status": "ok",
        "gate_reason": None,
        "geometry_frame": frame,
        "anchor_lonlat": list(anchor),
        "candidate_edges": len(geometry),
        "step_m": step_m,
        "seed": seed,
        "emission_sigma_m": locate.EMISSION_SIGMA_M,
        "vehicles_with_geometry": sum(1 for e in per_vehicle if e["status"] == "ok"),
        "vehicles_total": len(per_vehicle),
        "sigmas": results,
    }


# --------------------------------------------------------------------- CLI


def parse_sigmas(text: str) -> list[float]:
    values = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        value = float(chunk)
        if value < 0:
            raise argparse.ArgumentTypeError(f"σ 不能为负:{chunk}")
        values.append(value)
    if not values:
        raise argparse.ArgumentTypeError("--sigmas 不能为空(例:10,20,30)")
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="TC-18 定位/地图匹配验收驱动(T4;不接 run.py 主链)"
    )
    parser.add_argument("--vehicles", required=True, help="vehicles.json 路径(契约第四节信封)")
    parser.add_argument(
        "--network",
        choices=("sample", "real"),
        default="sample",
        help="统一图来源:sample=work/engine/samples/network_sample.json,"
        "real=stations/network.json(默认 sample)",
    )
    parser.add_argument("--site-id", default="", help="站点号(只进报告留痕,不参与判定)")
    parser.add_argument("--sigmas", default="10,20,30", help="逗号分隔的 σ(米),默认 10,20,30")
    parser.add_argument("--seed", type=int, default=42, help="噪声种子,默认 42")
    parser.add_argument("--step-m", type=float, default=DEFAULT_STEP_M, help="轨迹步长(米),默认 30")
    parser.add_argument("--out", default="", help="结果 JSON 输出路径(不给只打 stdout)")
    parser.add_argument(
        "--geometry",
        default="",
        help="带 WGS-84 折线 + anchor_lonlat 的几何文件(跑第②项用);"
        "不给则只用 --network 的图,缺几何就如实降级",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sigmas = parse_sigmas(args.sigmas)
    root = Path(__file__).resolve().parents[2]

    vehicles_payload, vehicles = load_vehicles(Path(args.vehicles))
    network_payload = load_network_payload(root, args.network)
    if args.geometry:
        # 显式几何优先:它带 WGS-84 折线,是第②项唯一可算距离的来源
        network_payload = read_json(Path(args.geometry))
    graph = try_build_graph(network_payload)

    direct = run_direct_read(vehicles, graph)
    noise = run_noise(vehicles, network_payload, sigmas, args.seed, args.step_m)

    verdict_direct = direct["truth_match_rate"] == 1.0
    sigma20 = noise.get("sigmas", {}).get("20", {})
    verdict_noise = sigma20.get("noise_accuracy")
    verdict_noise_ok = verdict_noise is not None and verdict_noise >= 0.90

    report = {
        "task": "T4",
        "test": "TC-18",
        "site_id": args.site_id,
        "vehicles_file": str(Path(args.vehicles)),
        "vehicles_ts": vehicles_payload.get("ts"),
        "vehicles_is_simulated": vehicles_payload.get("is_simulated"),
        "vehicle_count": len(vehicles),
        "network": args.network,
        "geometry_file": args.geometry or None,
        "geometry_frame": network_frame(network_payload),
        "unified_graph_loaded": graph is not None,
        "sigmas": sigmas,
        "seed": args.seed,
        "step_m": args.step_m,
        "direct_read": direct,
        "noise": noise,
        "verdict": {
            "tc18_1_truth_match_rate_eq_1": verdict_direct,
            "tc18_2_sigma20_noise_accuracy_ge_0_90": verdict_noise_ok,
            "tc18_2_noise_accuracy": verdict_noise,
            "tc18_2_status": noise.get("status"),
            "note": (
                "第②项 status != ok 时 accuracy 为 null —— 缺几何/缺锚点按降级留痕,"
                "不当 0 分,也不拿样例图硬算。"
            ),
        },
        "protocol": {
            "direct_read": "无噪声逐车直读,比 segment_id / offset_m",
            "noise": "沿真值路段 offset 0→L 等里程造轨迹 → 逐点加噪 → 顺序匹配;"
            "匹配器只拿 x/y/heading,不读真值字段",
            "accuracy_unit": "按轨迹点计(另报按轨迹计)",
            "determinism": "随机数种子固定;每点种子 = seed + 轨迹内序号",
        },
    }

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
        print(f"已写出:{out_path}({len(text.encode('utf-8')) + 1} B)")

    rate = direct["truth_match_rate"]
    print("TC-18 摘要")
    print(f"  车辆数             : {len(vehicles)}")
    print(
        f"  ① truth_match_rate : {rate if rate is not None else 'null'}"
        f"  ({direct['matched']}/{direct['checked']})"
        f"  → {'PASS' if verdict_direct else 'FAIL'}"
    )
    for key, entry in noise.get("sigmas", {}).items():
        accuracy = entry.get("noise_accuracy")
        shown = f"{accuracy:.4f}" if accuracy is not None else "null"
        print(
            f"  ② σ={key:>3} m         : {shown}"
            f"  ({entry.get('points_correct')}/{entry.get('points_total')})"
        )
    if noise.get("status") != "ok":
        print(f"  ② 状态             : {noise.get('status')} / {noise.get('gate_reason')}")
        print(f"    原因             : {noise.get('detail')}")
    print(f"  ② σ=20 m ≥ 0.90    : {'PASS' if verdict_noise_ok else 'FAIL / 未测'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
