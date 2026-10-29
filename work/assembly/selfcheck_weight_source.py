#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""权重口径自检：算路只剩一份权重实现，且「路段状态」真的进了算路。

跑法（仓库根）：

    python work/assembly/selfcheck_weight_source.py              # 纯引擎，不起服务
    python work/assembly/selfcheck_weight_source.py --api-base http://127.0.0.1:8001
                                                                # 额外核对三个端点的口径一致性

## 为什么要这个脚本

改前全仓有 3 份重复的 BPR 实现（`network.make_weight_fn` / `route_service.bpr_weight` /
`route_service.free_flow_weight`），参数还是两套命名（`alpha,beta` vs `bpr_alpha,bpr_beta`）；
更要紧的是 `/api/traffic/route/plan` 调 `route_service.plan()` 时**没传 `states`**，
于是"自定义起终点"永远按自由流算，和同一时刻的路段热力自相矛盾。
本脚本把这两件事钉成可复跑的断言。

## 检查项

| 项 | 内容 |
| --- | --- |
| A | 静态门禁：`work/engine` 里 `def free_flow_weight` / `def bpr_weight` **0 处**；引擎代码不再从参数里读 `bpr_alpha` / `bpr_beta` |
| B1 | 同一 OD + 同一站点包：低饱和（全段 x≈0.1）vs 主干堵（主干 x≈0.9）→ **主路的物理路径必须换一条**，两次 `weight_source` 都是 `bpr` |
| B2 | 负对照（口径说明用）：全段 x≈0.1 vs 全段 x≈0.9 → 物理主路**必须相同** |
| C | `states=None` → 仍然出路线，`weight_source=free_flow` |
| D | 参数键唯一：传 `bpr_alpha` 必须当场报错，不许静默回落到缺省值 |
| E | 数据前置：站点包里每条边 `speed_limit` / `capacity_vph` 都 > 0（`route_service` 已取消 `free_flow_speed_kmh` 兜底，靠这条保证不会 500） |
| F | （需服务）`/route/plan`、`/route/recommend`、`/route/{id}/steps` 同一 OD 的 `eta_min` / `weight_source` 口径一致 |

**关于 B2（口径冲突，必须说清楚）**：均匀饱和**不可能**换路 —— BPR 是对每条边乘同一个
系数 `(1 + alpha*x^beta)`，`x` 处处相同就等于把整张图的权重等比缩放，argmin 不变。
所以"把全站都设成 x=0.9 看主路变不变"是测不出毛病的写法；能测出状态是否真进算路的，
是 **B1 那种"只堵主干"** 的写法。B2 保留成负对照，防止有人把 B1 又改回均匀饱和。

退出码：全部通过 `0`；有 FAIL 返回 `1`（SKIP 不影响退出码）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "work" / "engine"
DEFAULT_API_BASE = "http://127.0.0.1:8001"
API_BASE_ENV = "HUBFLOW_API_BASE"

#: B1/B2 用的站点包与 OD：选 guangzhounan 是因为它有多条 ETA 接近的平行路线
#: （主路与备选差 < 1%），"只堵主干"能真的把主路挤到另一条上；
#: zhaoqingdong 那条网太窄（ENT-004→DROP-01 只有一条可行主路，备选 ETA 完全相同），换不动。
SITE_ID = "guangzhounan"
ORIGIN = {"point_id": "ENT-014"}
DESTINATION = {"point_id": "GZ-ZONE-01"}
LOW_X = 0.1
JAM_X = 0.9

#: F1 用的一对端点：落在**引擎产物同一站点**（default_site = zhaoqingdong，段号 SZ-###），
#: 这样"实时算路"和"读产物"才是同一个时空口径，能直接对 ETA / weight_source。
LIVE_ORIGIN = {"point_id": "ENT-004"}
LIVE_DESTINATION = {"point_id": "DROP-01"}

_RESULTS: list[tuple[str, str, str]] = []  # (项, PASS/FAIL/SKIP, 说明)


def _record(item: str, verdict: str, detail: str) -> None:
    _RESULTS.append((item, verdict, detail))
    print(f"[{verdict}] {item}: {detail}")


def _ok(item: str, detail: str) -> None:
    _record(item, "PASS", detail)


def _fail(item: str, detail: str) -> None:
    _record(item, "FAIL", detail)


def _skip(item: str, detail: str) -> None:
    _record(item, "SKIP", detail)


# ---------------------------------------------------------------- 引擎装配


def _engine_modules() -> tuple[Any, Any, Any]:
    if str(ENGINE) not in sys.path:
        sys.path.insert(0, str(ENGINE))
    import network as engine_network  # noqa: PLC0415
    import realnet as engine_realnet  # noqa: PLC0415
    import route_service as engine_route_service  # noqa: PLC0415

    return engine_network, engine_realnet, engine_route_service


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _site_entry(site_id: str) -> dict[str, Any]:
    ranges = _read_json(ROOT / "work" / "twin" / "site-ranges.json")
    for site in ranges.get("sites") or []:
        if isinstance(site, dict) and str(site.get("site_id")) == site_id:
            return site
    raise SystemExit(f"站点 {site_id} 不在 work/twin/site-ranges.json")


def _station_params() -> dict[str, Any]:
    """算路参数照站点包 decision 组取（与 /route/plan 的 `_route_decision_params()` 同源）。"""
    thresholds = _read_json(ROOT / "stations" / "thresholds.json")
    decision = thresholds.get("decision") or {}
    params: dict[str, Any] = {
        "k_candidates": decision.get("k_candidates", 3),
        "max_path_overlap": decision.get("max_path_overlap", 0.7),
        "alpha": decision.get("alpha", 0.15),
        "beta": decision.get("beta", 4.0),
    }
    if decision.get("eps_harm_s") is not None:
        params["eps_harm_s"] = decision.get("eps_harm_s")
    return params


def _build_graph() -> tuple[Any, dict[str, float], dict[str, Any], Any]:
    """返回 (graph, segment→capacity_vph, points, route_service)。"""
    engine_network, engine_realnet, engine_route_service = _engine_modules()
    thresholds = _read_json(ROOT / "stations" / "thresholds.json")
    site = _site_entry(SITE_ID)
    payload, _topo = engine_realnet.load_network_payload(site)
    graph_payload, _meta = engine_realnet.normalize_network(
        payload, site, thresholds.get("grading") or {}
    )
    graph = engine_network.Graph(graph_payload)
    capacity = {}
    for edge in graph_payload.get("edges") or []:
        section = str(edge.get("section") or "")
        if section and section not in capacity:
            capacity[section] = float(edge.get("capacity_vph") or 0.0)
    points = engine_route_service.load_points(SITE_ID)
    return graph, capacity, points, engine_route_service


def _states(capacity: dict[str, float], x: float, jam: set[str] | None = None,
            base_x: float = LOW_X) -> dict[str, dict[str, Any]]:
    """造决策层状态：`q_vph = x * c_vph`（x 精确可控，引擎再按 q/c 现算同一个 x）。"""
    states: dict[str, dict[str, Any]] = {}
    for segment_id, cap in capacity.items():
        value = x if (jam is None or segment_id in jam) else base_x
        states[segment_id] = {"q_vph": value * cap, "c_vph": cap}
    return states


def _primary(result: dict[str, Any]) -> dict[str, Any]:
    routes = result.get("routes") or []
    if not routes:
        raise SystemExit("plan 没返回任何路线（自检前提被破坏）")
    return routes[0]


# ---------------------------------------------------------------- A 静态门禁


def check_single_implementation() -> None:
    """A：权重实现只剩 network 一份 + 参数键不再有第二套命名。"""
    pattern = re.compile(r"def\s+(free_flow_weight|bpr_weight)\b")
    hits: list[str] = []
    for path in sorted(ENGINE.rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{lineno}")
    if hits:
        _fail("A1 单一份权重实现", "仍有独立权重实现：" + ", ".join(hits))
    else:
        _ok("A1 单一份权重实现", "work/engine/** 里 `def free_flow_weight` / `def bpr_weight` 共 0 处")

    # 参数键：不许有任何代码**读** bpr_alpha / bpr_beta（route_service 里只剩报错用的键名常量）
    readers = re.compile(r"""(params|decision)\s*(\.get\(|\[\s*)["']bpr_(alpha|beta)["']""")
    bad: list[str] = []
    for path in sorted(ENGINE.rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#") or readers.search(line) is None:
                continue
            bad.append(f"{path.relative_to(ROOT)}:{lineno}")
    if bad:
        _fail("A2 参数键唯一", "仍在读 bpr_alpha / bpr_beta：" + ", ".join(bad))
    else:
        _ok("A2 参数键唯一", "没有任何代码从 params 里读 bpr_alpha / bpr_beta（只有 alpha / beta）")


# ---------------------------------------------------------------- E 数据前置


def check_edge_fields(capacity: dict[str, float]) -> None:
    engine_modules = _engine_modules()
    engine_network = engine_modules[0]
    thresholds = _read_json(ROOT / "stations" / "thresholds.json")
    site = _site_entry(SITE_ID)
    payload, _topo = engine_modules[1].load_network_payload(site)
    graph_payload, _meta = engine_modules[1].normalize_network(
        payload, site, thresholds.get("grading") or {}
    )
    missing = [
        str(edge.get("id"))
        for edge in graph_payload.get("edges") or []
        if float(edge.get("speed_limit") or 0) <= 0 or float(edge.get("capacity_vph") or 0) <= 0
    ]
    required = set(engine_network.REQUIRED_EDGE_FIELDS)
    if not {"speed_limit", "capacity_vph"} <= required:
        _fail("E1 边必备字段", f"REQUIRED_EDGE_FIELDS 不含 speed_limit / capacity_vph：{sorted(required)}")
        return
    if missing:
        _fail("E2 speed/capacity 为正", f"{len(missing)} 条边缺正的速度或通行能力：{missing[:5]}")
        return
    _ok(
        "E1/E2 边必备字段",
        f"{SITE_ID} 全 {len(graph_payload.get('edges') or [])} 条边 speed_limit / capacity_vph 均为正"
        f"（自由流 t0 不再有 free_flow_speed_kmh 兜底，靠这条不会 500）；"
        f"状态覆盖 {len(capacity)} 个 segment",
    )


# ---------------------------------------------------------------- B / C / D


def check_state_reaches_routing() -> None:
    graph, capacity, points, route_service = _build_graph()
    params = _station_params()

    low = route_service.plan(
        graph, ORIGIN, DESTINATION, points=points, params=params, states=_states(capacity, LOW_X)
    )
    low_primary = _primary(low)
    corridor = {str(segment_id) for segment_id in low_primary.get("segments") or []}
    jam = route_service.plan(
        graph, ORIGIN, DESTINATION, points=points, params=params,
        states=_states(capacity, JAM_X, jam=corridor),
    )
    jam_primary = _primary(jam)

    # B1：低饱和 vs 主干堵 —— 物理主路必须换
    if low.get("params", {}).get("weight_source") != "bpr" or jam.get("params", {}).get("weight_source") != "bpr":
        _fail(
            "B1 状态进算路",
            f"两次都该报 weight_source=bpr，实际 low={low.get('params', {}).get('weight_source')} "
            f"jam={jam.get('params', {}).get('weight_source')}",
        )
    elif list(low_primary.get("segments") or []) == list(jam_primary.get("segments") or []):
        _fail(
            "B1 状态进算路",
            f"主干（{len(corridor)} 段）饱和度 0.1→0.9 后主路居然没变：{low_primary.get('segments')}",
        )
    else:
        _ok(
            "B1 状态进算路",
            f"{SITE_ID} {ORIGIN['point_id']}→{DESTINATION['point_id']}：主干 {len(corridor)} 段 x 0.1→0.9，"
            f"主路 {low_primary.get('path_id')} 的物理路径换了一条，"
            f"eta {low_primary.get('eta_min')}→{jam_primary.get('eta_min')} 分钟，两次 weight_source 均为 bpr",
        )

    # 附：换掉之后的主路确实避开了被堵的主干
    jam_segments = set(jam_primary.get("segments") or [])
    shared = corridor & jam_segments
    if shared:
        _skip(
            "B1b 避开被堵段",
            f"新主路仍与旧主干共线 {len(shared)} 段（绕行需要共享出入口，属正常；仅记录）",
        )
    else:
        _ok("B1b 避开被堵段", "新主路完全不经过被堵主干")

    # B2：负对照 —— 均匀饱和换不了路（口径说明，防有人把 B1 改回均匀饱和）
    uniform_low = route_service.plan(
        graph, ORIGIN, DESTINATION, points=points, params=params, states=_states(capacity, LOW_X)
    )
    uniform_high = route_service.plan(
        graph, ORIGIN, DESTINATION, points=points, params=params, states=_states(capacity, JAM_X)
    )
    if list(_primary(uniform_low).get("segments") or []) == list(_primary(uniform_high).get("segments") or []):
        _ok(
            "B2 负对照（均匀饱和不换路）",
            "全段 x 0.1→0.9 主路不变 —— BPR 对每条边乘同一系数，argmin 守恒；"
            "所以测「状态是否进算路」必须用 B1 的只堵主干写法",
        )
    else:
        _fail(
            "B2 负对照（均匀饱和不换路）",
            "均匀饱和居然换了主路：要么 BPR 实现不是全长统一系数，要么另有扰动",
        )

    # C：无状态 → 自由流
    free = route_service.plan(graph, ORIGIN, DESTINATION, points=points, params=params, states=None)
    if free.get("params", {}).get("weight_source") != "free_flow":
        _fail(
            "C 降级为自由流",
            f"states=None 时应报 weight_source=free_flow，实际 {free.get('params', {}).get('weight_source')}",
        )
    elif not free.get("routes"):
        _fail("C 降级为自由流", "states=None 时没出路线（应仍按自由流给出路线）")
    else:
        _ok(
            "C 降级为自由流",
            f"states=None 仍出 {len(free['routes'])} 条路线，weight_source=free_flow，"
            f"主路 eta {_primary(free).get('eta_min')} 分钟",
        )

    # D：老键名必须报错
    try:
        route_service.plan(
            graph, ORIGIN, DESTINATION, points=points,
            params={**params, "bpr_alpha": 0.3, "bpr_beta": 4.0},
        )
    except ValueError as exc:
        if "alpha" in str(exc):
            _ok("D 参数键唯一（拒绝 bpr_alpha）", f"传 bpr_alpha 当场 ValueError：{str(exc)[:60]}…")
        else:
            _fail("D 参数键唯一（拒绝 bpr_alpha）", f"报错文案没提 alpha/beta：{exc}")
    else:
        _fail("D 参数键唯一（拒绝 bpr_alpha）", "传 bpr_alpha 没报错（会静默回落缺省值，正是本次要消灭的分叉）")


# ---------------------------------------------------------------- F 端点一致性


def _http(url: str, payload: dict[str, Any] | None = None, timeout: float = 20.0) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - 本机自检
        return json.loads(response.read().decode("utf-8"))


def check_endpoints(api_base: str) -> None:
    base = api_base.rstrip("/")
    try:
        options = _http(f"{base}/api/traffic/route/options")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        _skip("F 端点一致性", f"{base} 不可达（{exc}）；本项需先起 traffic.py")
        return

    # F1：与产物**同站**的实时算路（产物是 default_site，即 zhaoqingdong）
    live = _http(
        f"{base}/api/traffic/route/plan",
        {"origin": LIVE_ORIGIN, "destination": LIVE_DESTINATION},
    )
    if live.get("reachable") is False:
        _fail("F1 同站实时算路", f"/route/plan 判不可达：{live.get('status') or live.get('reason')}")
        return
    live_source = live.get("weight_source")
    live_eta = (live.get("routes") or [{}])[0].get("eta_min")

    picked = next(
        (item for item in options.get("options") or []
         if isinstance(item, dict) and item.get("session_id")),
        None,
    )
    if picked is None:
        _skip("F 端点一致性", "route/options 没有可选 session（缺引擎产物）")
        return
    recommend = _http(
        f"{base}/api/traffic/route/recommend", {"session_id": picked.get("session_id")}
    )
    arrival = recommend.get("arrival_route") if isinstance(recommend.get("arrival_route"), dict) else {}
    steps = _http(f"{base}/api/traffic/route/{picked.get('request_id')}/steps")
    steps_arrival = (steps.get("routes") or {}).get("arrival_route") or {}

    sources = {
        "plan": live_source,
        "recommend": recommend.get("weight_source"),
        "options": picked.get("weight_source"),
        "steps": steps.get("weight_source"),
    }
    unknown = [name for name, value in sources.items() if value not in ("bpr", "free_flow")]
    if unknown:
        _fail(
            "F1 weight_source 三端点同词",
            f"{unknown} 上没有 weight_source（产物是否由改后的 run.py 重跑过？）：{sources}",
        )
    else:
        _ok("F1 weight_source 三端点同词", f"plan/recommend/options/steps 均给 bpr|free_flow：{sources}")

    if arrival.get("eta_min") is None or steps_arrival.get("eta_min") is None:
        _fail("F2 ETA 同源", f"recommend={arrival.get('eta_min')} steps={steps_arrival.get('eta_min')}")
    elif float(arrival.get("eta_min")) != float(steps_arrival.get("eta_min")):
        _fail(
            "F2 ETA 同源",
            f"recommend eta_min={arrival.get('eta_min')} 与 steps eta_min={steps_arrival.get('eta_min')} 不一致",
        )
    else:
        _ok(
            "F2 ETA 同源",
            f"recommend/steps 同一产物：arrival eta_min={arrival.get('eta_min')} 一致；"
            f"（/route/plan 是实时算路，eta_min={live_eta}，口径随当前路段状态而非产物）",
        )

    # F3：跨站必须**如实降级**，不许标着 bpr 却全是自由流
    cross = _http(
        f"{base}/api/traffic/route/plan",
        {"site_id": SITE_ID, "origin": ORIGIN, "destination": DESTINATION},
    )
    if cross.get("reachable") is False:
        _skip("F3 跨站不冒充 bpr", f"{SITE_ID} 在当前站快照下不可达：{cross.get('reason')}")
    elif cross.get("weight_source") != "free_flow":
        _fail(
            "F3 跨站不冒充 bpr",
            f"跨站算路（快照属于另一站点）却报 weight_source={cross.get('weight_source')}："
            "段号命名空间对不上时不能按有状态算路",
        )
    else:
        _ok(
            "F3 跨站不冒充 bpr",
            f"{SITE_ID} 与当前站点快照段号命名空间不一致时如实降级 free_flow"
            f"（附 weight_source_note：{str(cross.get('weight_source_note'))[:28]}…）",
        )


# ---------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description="权重口径自检（算路单一口径 + 状态进算路）")
    parser.add_argument(
        "--api-base",
        default=(os.environ.get(API_BASE_ENV) or "").strip() or None,
        help=f"traffic.py 地址（默认读 {API_BASE_ENV}，都没有就跳过端点检查）",
    )
    args = parser.parse_args()

    print("== 权重口径自检（work/assembly/selfcheck_weight_source.py）==")
    check_single_implementation()
    graph, capacity, _points, _service = _build_graph()
    check_edge_fields(capacity)
    check_state_reaches_routing()
    check_endpoints(args.api_base or DEFAULT_API_BASE)

    failed = [item for item, verdict, _detail in _RESULTS if verdict == "FAIL"]
    passed = [item for item, verdict, _detail in _RESULTS if verdict == "PASS"]
    skipped = [item for item, verdict, _detail in _RESULTS if verdict == "SKIP"]
    print(
        f"\n== 汇总：PASS {len(passed)} / FAIL {len(failed)} / SKIP {len(skipped)} =="
    )
    if failed:
        print("FAIL 项：" + "；".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
