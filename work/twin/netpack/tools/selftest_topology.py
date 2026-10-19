#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IKNB9H 自检（真跑，不靠人工看图）：Z 站全量 + 反例 FAIL + 引擎两遍一致 + W1/样例不退化 + doc_gate。

## 跑什么（每一步都是子进程真跑，输出/哈希写进证据 JSON）

| # | 项 | 判据 |
|---|---|---|
| 1 | enriched 图与重算逐字节一致 | `topology.py --check` 退出 0 |
| 2 | 拓扑校验 Z 站通过 | `check_topology.py` 退出 0；61 段全量、FAIL 0 |
| 3 | 反例必须 FAIL | `check_topology.py --self-test` 退出 0；人为断头命中 `oneway_tail_without_successor`、非法掉头命中 `illegal_u_turn` |
| 4 | 引擎真网两遍一致 | `run.py --network real` 两遍 `routes.json` / `run_log.json` sha256 相同；27 OD、80 条路线带 legs、有反向 legs、`segments` 只有规范段号 |
| 5 | 全 OD/可达性两遍一致 | `topology_check.py` 两遍报告 sha256 相同；61/61 段覆盖、0 非法路线 |
| 6 | 校验器复核引擎路线 | `check_topology.py --routes <引擎 routes>` 退出 0 |
| 7 | 样例基线不退化 | `run.py --sample` 产物 sha256 = 冻结基线 |
| 8 | W1 输入链只读不退化 | `sumonet.build_plain_inputs()` 仍能建 61 正向边 + 反向补边；raw / sumonet 无 git diff |
| 9 | 仓库门禁 | `python scripts/doc_gate.py` 退出 0（8/8） |

## 备注

- 广州南站（IKNB9F）的 enriched 图/报告已由 IKNC4J 补齐（见 netpack/README §5.6）；本脚本仍以
  Z 站为主站自检，GZ 用同一套命令单独跑 `topology.py --site-id guangzhounan` +
  `tools/check_topology.py --site-id guangzhounan`（本脚本只认站点登记表，换站不改代码）。
- 自检证据写 `work/twin/netpack/topology_selftest.json`（脚本产物，不含时间戳）。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
NETPACK = HERE.parent
REPO_ROOT = NETPACK.parents[2]
sys.path.insert(0, str(NETPACK))

import topology  # noqa: E402

PYTHON = sys.executable
EVIDENCE = NETPACK / "topology_selftest.json"

#: `run.py --sample` 的冻结基线（2026-10-18 改动前捕获；本单不得改变样例逐字节输出）
SAMPLE_ROUTES_SHA256 = "c375d90255703de9d531879854894e8d544e516a3b377493d7596a4cfd13814c"
SAMPLE_RUN_LOG_SHA256 = "819f297fd06fd817c616a0e6ccd5b1a04919f88e00473961951ebabf09f36ddc"

#: 关键反例码
REQUIRED_CODES = {
    "counterexample_broken_chain": "oneway_tail_without_successor",
    "counterexample_illegal_u_turn": "illegal_u_turn",
}


def sha256_file(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )


def scrub(text: str) -> str:
    """把本机绝对路径替换成 <abs>（仓库纪律：记录里不写本机路径）。"""
    cleaned = re.sub(r"[A-Za-z]:\\[^\s\"'<>]+", "<abs>", text or "")
    cleaned = re.sub(r"/(?:home|Users|tmp|var/folders)/[^\s\"'<>]+", "<abs>", cleaned)
    return cleaned


def tail(text: str, lines: int = 8) -> list[str]:
    return [scrub(line) for line in (text or "").strip().splitlines()[-lines:] if line.strip()]


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    def record(name: str, ok: bool, detail: dict[str, Any]) -> None:
        checks.append({"name": name, "passed": bool(ok), "detail": detail})
        if not ok:
            failures.append(name)

    with tempfile.TemporaryDirectory(prefix="iknb9h-selftest-") as scratch_raw:
        scratch = Path(scratch_raw)

        # 1) enriched 与重算逐字节一致
        result = run([PYTHON, "work/twin/netpack/topology.py", "--check"])
        record(
            "01_enriched_check",
            result.returncode == 0,
            {"exit_code": result.returncode, "output": tail(result.stdout + result.stderr)},
        )

        # 2) Z 站拓扑校验通过
        report_path = scratch / "topology_report.json"
        result = run([PYTHON, "work/twin/netpack/tools/check_topology.py", "--out", str(report_path)])
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
        summary = report.get("summary") or {}
        checks_detail = report.get("checks") or {}
        schema_checked = (checks_detail.get("schema") or {}).get("details", {}).get("segments_checked")
        record(
            "02_topology_check_z",
            result.returncode == 0
            and summary.get("segments") == 61
            and summary.get("failures") == 0
            and schema_checked == 61
            and all(
                name in checks_detail
                for name in (
                    "schema",
                    "boundary_roles",
                    "oneway_successor",
                    "bidirectional_pairing",
                    "main_road_gap",
                    "reachability",
                    "u_turn",
                )
            ),
            {
                "exit_code": result.returncode,
                "summary": summary,
                "schema_segments_checked": schema_checked,
                "oneway_checked": (checks_detail.get("oneway_successor") or {})
                .get("details", {})
                .get("oneway_segments_checked"),
                "report_sha256": sha256_file(report_path) if report_path.is_file() else None,
                "output": tail(result.stdout + result.stderr),
            },
        )

        # 3) 反例必须 FAIL
        ce_out = scratch / "counterexample_selftest.json"
        result = run(
            [
                PYTHON,
                "work/twin/netpack/tools/check_topology.py",
                "--self-test",
                "--self-test-out",
                str(ce_out),
            ]
        )
        verdict = json.loads(ce_out.read_text(encoding="utf-8")) if ce_out.is_file() else {}
        cases = {case["case"]: case for case in verdict.get("cases") or []}
        codes: dict[str, list[str]] = {}
        counterexample_ok = True
        for case_name, required_code in REQUIRED_CODES.items():
            case = cases.get(case_name) or {}
            case_codes = list(case.get("failure_codes") or [])
            codes[case_name] = case_codes
            if case.get("summary", {}).get("passed") is not False or required_code not in case_codes:
                counterexample_ok = False
        normal_case = cases.get("z_network_normal") or {}
        counterexample_ok = counterexample_ok and bool(normal_case.get("summary", {}).get("passed"))
        record(
            "03_counterexamples_fail",
            result.returncode == 0 and counterexample_ok,
            {"exit_code": result.returncode, "cases": codes, "verdict_passed": verdict.get("passed")},
        )

        # 4) 引擎真网两遍一致
        real_a = scratch / "real_a"
        real_b = scratch / "real_b"
        run_a = run([PYTHON, "work/engine/run.py", "--network", "real", "--out", str(real_a)])
        run_b = run([PYTHON, "work/engine/run.py", "--network", "real", "--out", str(real_b)])
        routes_a = real_a / "routes.json"
        routes_b = real_b / "routes.json"
        log_a = real_a / "run_log.json"
        log_b = real_b / "run_log.json"
        engine_ok = (
            run_a.returncode == 0
            and run_b.returncode == 0
            and routes_a.is_file()
            and routes_b.is_file()
            and sha256_file(routes_a) == sha256_file(routes_b)
            and log_a.is_file()
            and log_b.is_file()
            and sha256_file(log_a) == sha256_file(log_b)
        )
        routes = json.loads(routes_a.read_text(encoding="utf-8")) if routes_a.is_file() else {}
        requests = routes.get("requests") or []
        legs_total = 0
        reverse_legs = 0
        segments_bad = []
        for request in requests:
            route_objects = [request.get("arrival_route"), request.get("departure_route")]
            route_objects.extend(request.get("alternatives") or [])
            for route in route_objects:
                if not isinstance(route, dict):
                    continue
                legs = route.get("legs") or []
                legs_total += len(legs)
                reverse_legs += sum(1 for leg in legs if leg.get("direction") == "reverse")
                for segment_id in route.get("segments") or []:
                    if not str(segment_id).startswith("SZ-") or str(segment_id).endswith("_rev"):
                        segments_bad.append(str(segment_id))
        engine_log = json.loads(log_a.read_text(encoding="utf-8")) if log_a.is_file() else {}
        engine_ok = (
            engine_ok
            and len(requests) == 27
            and len((routes.get("network") or {}).get("segments") or []) == 61
            and legs_total > 0
            and reverse_legs > 0
            and not segments_bad
            and (routes.get("network") or {}).get("topology_source") == "enriched"
            and bool((engine_log.get("m1_4") or {}).get("passed"))
        )
        record(
            "04_engine_real_two_pass",
            engine_ok,
            {
                "exit_codes": [run_a.returncode, run_b.returncode],
                "routes_sha256": sha256_file(routes_a) if routes_a.is_file() else None,
                "run_log_sha256": sha256_file(log_a) if log_a.is_file() else None,
                "two_pass_identical": bool(
                    routes_a.is_file()
                    and routes_b.is_file()
                    and sha256_file(routes_a) == sha256_file(routes_b)
                ),
                "requests": len(requests),
                "routes_with_legs_total": legs_total,
                "reverse_legs": reverse_legs,
                "m1_4": engine_log.get("m1_4"),
                "output": tail(run_a.stdout + run_a.stderr),
            },
        )

        # 5) 全 OD / 可达性两遍一致
        matrix_a = scratch / "route_matrix_a.json"
        matrix_b = scratch / "route_matrix_b.json"
        matrix_run_a = run(
            [PYTHON, "work/engine/topology_check.py", "--json-out", str(matrix_a)]
        )
        matrix_run_b = run(
            [PYTHON, "work/engine/topology_check.py", "--json-out", str(matrix_b)]
        )
        matrix = json.loads(matrix_a.read_text(encoding="utf-8")) if matrix_a.is_file() else {}
        matrix_summary = matrix.get("summary") or {}
        matrix_ok = (
            matrix_run_a.returncode == 0
            and matrix_run_b.returncode == 0
            and matrix_a.is_file()
            and matrix_b.is_file()
            and sha256_file(matrix_a) == sha256_file(matrix_b)
            and matrix_summary.get("segments_covered") == 61
            and matrix_summary.get("invalid_routes") == 0
            and matrix_summary.get("failures") == 0
            and not matrix_summary.get("segments_uncovered")
        )
        # 边界对里所有 reachable=true 的都必须有完整边序列
        boundary_ok = all(
            row.get("reachable") is False or bool(row.get("edges"))
            for row in matrix.get("boundary_od") or []
        )
        record(
            "05_route_matrix_two_pass",
            matrix_ok and boundary_ok,
            {
                "exit_codes": [matrix_run_a.returncode, matrix_run_b.returncode],
                "report_sha256": sha256_file(matrix_a) if matrix_a.is_file() else None,
                "two_pass_identical": bool(
                    matrix_a.is_file()
                    and matrix_b.is_file()
                    and sha256_file(matrix_a) == sha256_file(matrix_b)
                ),
                "summary": matrix_summary,
                "boundary_paths_complete": boundary_ok,
                "output": tail(matrix_run_a.stdout + matrix_run_a.stderr),
            },
        )

        # 6) 校验器复核引擎路线
        routes_report = scratch / "report_with_engine_routes.json"
        result = run(
            [
                PYTHON,
                "work/twin/netpack/tools/check_topology.py",
                "--routes",
                str(routes_a),
                "--out",
                str(routes_report),
            ]
        )
        route_report = (
            json.loads(routes_report.read_text(encoding="utf-8")) if routes_report.is_file() else {}
        )
        routes_checked = (
            (route_report.get("checks") or {}).get("routes") or {}
        ).get("details", {}).get("routes_checked")
        record(
            "06_checker_validates_engine_routes",
            result.returncode == 0 and bool(routes_checked),
            {
                "exit_code": result.returncode,
                "routes_checked": routes_checked,
                "summary": route_report.get("summary"),
                "output": tail(result.stdout + result.stderr),
            },
        )

        # 7) 样例基线不退化（逐字节）
        sample_dir = scratch / "sample"
        result = run([PYTHON, "work/engine/run.py", "--sample", "--out", str(sample_dir)])
        sample_routes = sample_dir / "routes.json"
        sample_log = sample_dir / "run_log.json"
        sample_ok = (
            result.returncode == 0
            and sample_routes.is_file()
            and sample_log.is_file()
            and sha256_file(sample_routes) == SAMPLE_ROUTES_SHA256
            and sha256_file(sample_log) == SAMPLE_RUN_LOG_SHA256
        )
        record(
            "07_sample_baseline_unchanged",
            sample_ok,
            {
                "exit_code": result.returncode,
                "routes_sha256": sha256_file(sample_routes) if sample_routes.is_file() else None,
                "expected_routes_sha256": SAMPLE_ROUTES_SHA256,
                "run_log_sha256": sha256_file(sample_log) if sample_log.is_file() else None,
                "expected_run_log_sha256": SAMPLE_RUN_LOG_SHA256,
            },
        )

        # 8) W1 / sumonet 输入链只读不退化
        sys.path.insert(0, str(REPO_ROOT / "work" / "twin"))
        import sumonet  # noqa: E402  （只读：导入并调用，不改文件）

        raw_path = REPO_ROOT / "work" / "twin" / "netpack" / "network_junction.json"
        raw_payload = topology.read_json(raw_path)
        site = topology.pick_site()
        defaults = sumonet.load_station_defaults()
        plain = sumonet.build_plain_inputs(raw_payload, site, scratch / "sumo", defaults)
        git_diff = run(
            [
                "git",
                "diff",
                "--quiet",
                "--",
                "work/twin/netpack/network_junction.json",
                "work/twin/netpack/stationZ_junction.network.ts",
                "work/twin/sumonet.py",
            ]
        )
        w1_ok = (
            plain["forward_edges"] == 61
            and plain["reverse_edges"] > 0
            and len(plain["node_meta"]) == 44
            and git_diff.returncode == 0
        )
        record(
            "08_w1_sumonet_readonly",
            w1_ok,
            {
                "forward_edges": plain["forward_edges"],
                "reverse_edges": plain["reverse_edges"],
                "nodes": len(plain["node_meta"]),
                "git_diff_exit_code": git_diff.returncode,
                "raw_sha256": sha256_file(raw_path),
                "note": "sumonet 仍读原 network_junction.json；enriched 是旁路产物，W1 零改动",
            },
        )

        # 9) 接口层只读 smoke（不改 work/assembly；只验证新增 legs 不影响旧字段消费）
        interface_detail: dict[str, Any] = {"imported": False}
        interface_ok = True
        sys.path.insert(0, str(REPO_ROOT / "work" / "assembly"))
        try:
            import traffic  # noqa: E402  （只读导入，不改接口层代码）

            interface_detail["imported"] = True
            first_request = (routes.get("requests") or [{}])[0]
            summary = traffic._route_option_summary(first_request)
            prefixes = traffic._routes_namespaces(routes)
            arrival = summary.get("arrival_route") or {}
            expected_segments = (first_request.get("arrival_route") or {}).get("segments")
            interface_ok = (
                "legs" not in arrival
                and "legs" not in summary
                and arrival.get("segments") == expected_segments
                and prefixes == ["SZ"]
            )
            interface_detail.update(
                {
                    "arrival_segments": arrival.get("segments"),
                    "legs_ignored": "legs" not in arrival,
                    "namespace_prefixes": prefixes,
                    "note": "接口层只读契约字段（path_id/segments/eta_min…），新增 legs 被忽略，不退化",
                }
            )
        except ImportError as exc:  # 依赖未装的机器：如实记 skipped，不伪装通过
            interface_detail["skipped"] = f"ImportError: {exc}"
        except Exception as exc:  # noqa: BLE001 —— 接口层 smoke 失败要如实记录，不拖垮自检
            interface_ok = False
            interface_detail["error"] = f"{type(exc).__name__}: {exc}"
        record("09_interface_readonly", interface_ok, interface_detail)

        # 10) doc_gate（先跑一次；证据写完再跑一次）
        doc_gate_first = run([PYTHON, "scripts/doc_gate.py"])
        record(
            "10_doc_gate_8_of_8",
            doc_gate_first.returncode == 0,
            {
                "exit_code": doc_gate_first.returncode,
                "output": tail(doc_gate_first.stdout + doc_gate_first.stderr, 12),
            },
        )

    # 证据（不含时间戳；temp 路径只留文件名）
    evidence = {
        "schema_version": "1.0",
        "is_simulated": True,
        "generated_by": "work/twin/netpack/tools/selftest_topology.py",
        "scope": {
            "site": "肇庆东站（Z，61 段）",
            "enriched": "work/twin/netpack/network_junction.enriched.json",
            "report": "work/twin/netpack/topology_report.json",
            "engine_routes": "work/engine/out/real/routes.json",
            "od_matrix": "work/engine/route_matrix.json",
        },
        "checks": checks,
        "failures": failures,
        "passed": not failures,
        "notes": [
            "全部检查真实调用脚本 / 引擎 / 校验器，不靠人工看图；证据为脚本产物。",
            "广州南站（IKNB9F）enriched 图与报告已由 IKNC4J 补齐（433 段）；GZ 用同一套命令 "
            "`topology.py --site-id guangzhounan` + `check_topology.py --site-id guangzhounan` 单独跑。",
            "样例基线 sha256 是改动前冻结值，用来证明 --sample 逐字节不变。",
        ],
    }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    # 证据写全后再跑一次门禁（doc_gate 会扫这个新 JSON）
    doc_gate_second = run([PYTHON, "scripts/doc_gate.py"])
    if doc_gate_second.returncode != 0:
        failures.append("10_doc_gate_8_of_8_recheck")
        evidence["checks"].append(
            {
                "name": "10_doc_gate_8_of_8_recheck",
                "passed": False,
                "detail": {
                    "exit_code": doc_gate_second.returncode,
                    "output": tail(doc_gate_second.stdout + doc_gate_second.stderr, 12),
                },
            }
        )
        evidence["failures"] = failures
        evidence["passed"] = False
        EVIDENCE.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    print(f"自检证据 → {topology.repo_rel(EVIDENCE)}")
    for check in evidence["checks"]:
        print(f"  {'✅' if check['passed'] else '❌'} {check['name']}")
    if failures:
        print("❌ 自检失败：" + "、".join(failures))
        return 1
    print("✅ 自检通过：Z 站全量 PASS；人为断头 / 非法掉头反例 FAIL；引擎两遍一致；样例/W1 不退化；doc_gate 8/8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
