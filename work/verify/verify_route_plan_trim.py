#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_route_plan_trim.py —— 打 `/api/traffic/route/plan` 的 `trim_head_m` / `trim_tail_m` 口径洞。

为什么单独一支：起终点落在**段中间**时，`trim_head_m` / `trim_tail_m` 表示「首末段各有
多少米不在本次行程内」。它一旦按 `coords` 顺序而不是**行进顺序**折，反向段就会把
裁剪量算到另一头（起点标在段另一端），前端再怎么渲染都错。这是接口层的事，与前端无关。

矩阵（lead 定，2026-10-29）：
  段：`SZ-004`（direction=reverse，120.7 m） + `SZ-023`（forward 口径，63.4 m）
  每个段 3 个中点 offset（0.25 / 0.5 / 0.75 × length，避开 0 与 length）
  两种落点：A 起点在段中（终点取行进远端节点） / B 终点在段中（起点取行进近端节点）

断言（全部容差来自 _meta.tolerances 同量级）：
  1) |trim_head_m - dist(start_point, steps[0].geometry[0])|        < 1.0 m
  2) |trim_tail_m - dist(destination_point, steps[-1].geometry[-1])| < 1.0 m
  3) |length_m - (sum(steps.length_m) - trim_head_m - trim_tail_m)|  < 0.5 m
  4) 语义对照（这条才抓得住倒置）：trim_head_m ≈ 起点 offset_travel_m，
     trim_tail_m ≈ 段长 - 终点 offset_travel_m

用法：python work/verify/verify_route_plan_trim.py [--api http://127.0.0.1:8001]
输出：work/verify/route_plan_trim.json（逐条数值）+ 终端 markdown 表
"""
from __future__ import annotations

import argparse
import json
import sys
import math
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # work/verify -> 仓库根
SNAP = ROOT / "work/verify/direction_snapshot.json"
NETPACK = ROOT / "work/twin/netpack/network_junction.json"
OUT = ROOT / "work/verify/route_plan_trim.json"

SEGS = (("SZ-004", "reverse"), ("SZ-023", "forward"))
FRACTIONS = (0.25, 0.5, 0.75)
TOL_HEAD_TAIL_M = 1.0
TOL_LENGTH_M = 0.5

R_EARTH = 6371008.8


def dist_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """(lon, lat) 两点等距圆柱近似——与仓库其它脚本同量级（<1 km 误差可忽略）。"""
    lon1, lat1 = a[0], a[1]
    lon2, lat2 = b[0], b[1]
    lat0 = math.radians((lat1 + lat2) / 2.0)
    dx = math.radians(lon2 - lon1) * math.cos(lat0) * R_EARTH
    dy = math.radians(lat2 - lat1) * R_EARTH
    return math.hypot(dx, dy)


def point_at_offset(coords: list[list[float]], offset_m: float) -> list[float]:
    """coords 顺序上折 offset_m（口径同前端 pointAtOffset / 后端 origin 回显）。"""
    if offset_m <= 0:
        return list(coords[0])
    rest = offset_m
    for i in range(1, len(coords)):
        seg = dist_m(coords[i - 1], coords[i])
        if rest <= seg:
            t = rest / seg if seg > 0 else 0.0
            return [coords[i - 1][0] + (coords[i][0] - coords[i - 1][0]) * t,
                    coords[i - 1][1] + (coords[i][1] - coords[i - 1][1]) * t]
        rest -= seg
    return list(coords[-1])


def post(api: str, body: dict) -> dict:
    req = urllib.request.Request(
        api.rstrip("/") + "/api/traffic/route/plan",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        return json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as exc:                      # 400/500 也算一条实测
        return {"_http_error": exc.code, "_body": exc.read().decode("utf-8", "replace")[:400]}
    except urllib.error.URLError as exc:
        return {"_net_error": str(exc)}


def main() -> int:
    try:                      # Windows 控制台默认 GBK，遇到 ↔ / − 会炸；统一按 UTF-8 输出
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8001")
    args = ap.parse_args()

    snap = json.loads(SNAP.read_text(encoding="utf-8"))["segments"]
    net = json.loads(NETPACK.read_text(encoding="utf-8"))
    coords_by_id = {e["segment_id"]: e["coords"] for e in net["edges"]}

    rows: list[dict] = []
    for sid, caliber in SEGS:
        meta = snap[sid]
        coords = coords_by_id[sid]
        length_m = float(meta["length_m"])
        travel_from, travel_to = meta["travel_from"], meta["travel_to"]
        for frac in FRACTIONS:
            off = round(length_m * frac, 2)          # coords 顺序 offset
            # ---- A：起点落在段中；终点取行进远端节点（行程就是「这里 → 段尾」）
            a = post(args.api, {
                "origin": {"segment_id": sid, "offset_m": off},
                "destination": {"node_id": travel_to},
                "with_departure": False,
            })
            rows.append(eval_case("A 起点在段中", sid, caliber, length_m, off, coords,
                                  travel_from, travel_to, a))
            # ---- B：终点落在段中；起点取行进近端节点
            b = post(args.api, {
                "origin": {"node_id": travel_from},
                "destination": {"segment_id": sid, "offset_m": off},
                "with_departure": False,
            })
            rows.append(eval_case("B 终点在段中", sid, caliber, length_m, off, coords,
                                  travel_from, travel_to, b))

    payload = {
        "_meta": {
            "purpose": "POST /api/traffic/route/plan 的 trim_head_m / trim_tail_m 口径验收（起终点落在段中）",
            "generated_by": "work/verify/verify_route_plan_trim.py",
            "api": args.api,
            "at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
            "matrix": {"segments": [s for s, _ in SEGS], "fractions": list(FRACTIONS),
                       "cases": ["A 起点在段中", "B 终点在段中"]},
            "tolerances": {"head_tail_m": TOL_HEAD_TAIL_M, "length_m": TOL_LENGTH_M},
            "caliber_note": (
                "trim_head_m/trim_tail_m = 首末段各有多少米不在行程内；起点/终点的 offset_m 是 coords 顺序，"
                "offset_travel_m 是行进顺序。反向段二者互补（L - offset_m），倒置即本次缺陷。"
            ),
        },
        "counts": {},
        "rows": rows,
    }
    payload["counts"] = {
        "rows": len(rows),
        "pass": sum(1 for r in rows if r["ok"]),
        "fail": sum(1 for r in rows if not r["ok"]),
        "assert_fail": {k: sum(1 for r in rows if r["checks"].get(k) is False)
                        for k in ("trim_head_vs_geom0", "trim_tail_vs_geom_last",
                                  "length_vs_steps", "trim_head_semantic", "trim_tail_semantic",
                                  "route_level_trim_present")},
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8", newline="\n")

    print(f"写盘 {OUT.relative_to(ROOT)}  | {payload['counts']['pass']}/{len(rows)} 条全通过")
    print()
    print("| 用例 | 段 | 方向 | offset_m | trim_head_m | dist(start,geom0) | trim_tail_m | dist(dest,geomN) | length_m | 结论 |")
    print("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for r in rows:
        print("| {case} | {sid} | {caliber} | {off:.2f} | {th} | {d0} | {tt} | {dn} | {len} | {verdict} |".format(
            case=r["case"], sid=r["segment_id"], caliber=r["caliber"], off=r["offset_m"],
            th=fmt(r["trim_head_m"]), d0=fmt(r["dist_start_geom0_m"]),
            tt=fmt(r["trim_tail_m"]), dn=fmt(r["dist_dest_geom_last_m"]),
            len=fmt(r["route_length_m"]), verdict="PASS" if r["ok"] else "FAIL",
        ))
    print()
    print("断言失败计数：", payload["counts"]["assert_fail"])
    for r in rows:
        if not r["ok"]:
            print(f"  - {r['case']} {r['segment_id']} off={r['offset_m']}: " +
                  "; ".join(f"{k}={v}" for k, v in r["checks"].items() if v is False) +
                  (f" | 备注 {r['note']}" if r.get("note") else ""))
    return 0 if payload["counts"]["fail"] == 0 else 1


def fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:.2f}"


def eval_case(case: str, sid: str, caliber: str, length_m: float, off: float,
              coords: list[list[float]], travel_from: str, travel_to: str,
              resp: dict) -> dict:
    row: dict = {"case": case, "segment_id": sid, "caliber": caliber,
                 "length_m": length_m, "offset_m": off,
                 "travel_from": travel_from, "travel_to": travel_to,
                 "checks": {}, "ok": False, "note": None}
    if "_http_error" in resp or "_net_error" in resp:
        row["note"] = resp.get("_body") or resp.get("_net_error")
        row["http_error"] = resp.get("_http_error")
        row["checks"] = {"trim_head_vs_geom0": False, "trim_tail_vs_geom_last": False,
                         "length_vs_steps": False, "trim_head_semantic": False,
                         "trim_tail_semantic": False}
        return row
    routes = resp.get("routes") or []
    row["reachable"] = bool(resp.get("reachable"))
    if not routes:
        row["note"] = f"reachable=false: {str(resp.get('reason'))[:80]}"
        row["checks"] = {"trim_head_vs_geom0": False, "trim_tail_vs_geom_last": False,
                         "length_vs_steps": False, "trim_head_semantic": False,
                         "trim_tail_semantic": False}
        return row
    route = routes[0]
    steps = route.get("steps") or []
    route_trim_head = route.get("trim_head_m")
    route_trim_tail = route.get("trim_tail_m")
    # 逐段裁剪量（steps[].trim_head_m / trim_tail_m）才是画线要用的；routes[] 级是汇总。
    step_head = steps[0].get("trim_head_m") if steps else None
    step_tail = steps[-1].get("trim_tail_m") if steps else None
    trim_head = step_head if step_head is not None else route_trim_head
    trim_tail = step_tail if step_tail is not None else route_trim_tail
    route_len = route.get("length_m")
    start = resp.get("start_point") or {}
    dest = resp.get("destination") or {}
    start_ll = (start.get("lon"), start.get("lat")) if start.get("lon") is not None else None
    # destination_point：接口没给 lon/lat 时按「offset_m 是 coords 顺序」自己折（文档 §2 口径）
    dest_off = dest.get("offset_m")
    dest_ll = ((dest.get("lon"), dest.get("lat")) if dest.get("lon") is not None
               else (tuple(point_at_offset(coords, float(dest_off))) if dest_off is not None else None))
    geom0 = (steps[0].get("geometry") or [None])[0] if steps else None
    geom_last = (steps[-1].get("geometry") or [None])[-1] if steps else None

    d_start_geom0 = (dist_m(start_ll, tuple(geom0))
                     if start_ll and start_ll[0] is not None and geom0 else None)
    d_dest_geom_last = (dist_m(tuple(dest_ll), tuple(geom_last))
                        if dest_ll and geom_last else None)
    steps_sum = sum(float(s.get("length_m") or 0.0) for s in steps)

    checks: dict[str, bool] = {}
    if case.startswith("A"):
        checks["trim_head_vs_geom0"] = (trim_head is not None and d_start_geom0 is not None
                                        and abs(trim_head - d_start_geom0) < TOL_HEAD_TAIL_M)
        expect_head = start.get("offset_travel_m")
        checks["trim_head_semantic"] = (trim_head is not None and expect_head is not None
                                       and abs(trim_head - float(expect_head)) < TOL_HEAD_TAIL_M)
        checks["trim_tail_vs_geom_last"] = True          # 终点在节点上，不适用
        checks["trim_tail_semantic"] = True
        row["expected_trim_head_m"] = expect_head
    else:
        checks["trim_tail_vs_geom_last"] = (trim_tail is not None and d_dest_geom_last is not None
                                           and abs(trim_tail - d_dest_geom_last) < TOL_HEAD_TAIL_M)
        expect_tail = (length_m - float(dest.get("offset_travel_m"))) if dest.get("offset_travel_m") is not None else None
        checks["trim_tail_semantic"] = (trim_tail is not None and expect_tail is not None
                                       and abs(trim_tail - expect_tail) < TOL_HEAD_TAIL_M)
        checks["trim_head_vs_geom0"] = True
        checks["trim_head_semantic"] = True
        row["expected_trim_tail_m"] = expect_tail
    if trim_head is not None and trim_tail is not None and route_len is not None:
        checks["length_vs_steps"] = abs(route_len - (steps_sum - trim_head - trim_tail)) < TOL_LENGTH_M
    else:
        checks["length_vs_steps"] = False
        row["note"] = "trim_head_m/trim_tail_m 为 null（未给裁剪量，前端无法裁）"
    # routes[] 级汇总裁剪量在不在（lead 断言看的是这一级；缺了前端只好自己从 steps 汇总）
    checks["route_level_trim_present"] = (route_trim_head is not None and route_trim_tail is not None)
    if not checks["route_level_trim_present"]:
        row["note"] = "routes[].trim_head_m/trim_tail_m 为 null；逐段 steps[].trim_* 有值"

    row.update({
        "trim_head_m": trim_head,
        "trim_tail_m": trim_tail,
        "route_length_m": route_len,
        "steps_length_sum_m": round(steps_sum, 3),
        "step_count": len(steps),
        "start_offset_travel_m": start.get("offset_travel_m"),
        "dest_offset_travel_m": dest.get("offset_travel_m"),
        "start_lonlat": list(start_ll) if start_ll and start_ll[0] is not None else None,
        "dest_lonlat": list(dest_ll) if dest_ll else None,
        "route_trim_head_m": route_trim_head,
        "route_trim_tail_m": route_trim_tail,
        "step0_trim_head_m": step_head,
        "step_last_trim_tail_m": step_tail,
        "step0_geometry0": geom0,
        "step_last_geometry_last": geom_last,
        "dist_start_geom0_m": d_start_geom0,
        "dist_dest_geom_last_m": d_dest_geom_last,
        "checks": checks,
    })
    row["ok"] = all(checks.values())
    return row


if __name__ == "__main__":
    raise SystemExit(main())
