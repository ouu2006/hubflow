#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多因素自检（Issue IKMS19 · TC-16）：**真跑**逐因素注入，输出 PASS / FAIL / BLOCKED。

对 `stations/factors.json` 的 **F01~F14 逐项**构造注入（值优先取登记表的 `demo_multipliers`；
登记表没给 demo 倍率的，用**明确标注的自检夹具值**），调 `work/twin/factors.py::inject_segments`，
在真网基线上验证：

| 检查 | 判据 |
|---|---|
| 出现 | 受影响段的 `factors_applied` 出现该 `factor_id`（含正确 target / multiplier / until）；未受影响段**逐字段不变** |
| 方向 | 容量类：`c_vph` 不升、`x` 不降、判级不降；速度类：`v_f_kmh` 不升、延误不降；置信度类：`confidence` 不升 |
| 判级来源 | 注入后的 `level` 与 **canonical `work/perception/level.py` 重算结果一致**（证明没复制判级逻辑） |
| 硬触发 | F07 / F08（`grading.hard_trigger_factor_ids`）命中 → `level == hard_trigger_level`（跳档到 4） |
| 占位 | 未生效因素**不写** `multiplier=1.0` 占位；失效窗口内的注入不写进 `factors_applied` |
| 可重复 | 同一注入连跑两遍，产物 sha256 一致 |

**如实标阻塞**：`target=demand` 的 6 类因素（F03/F10/F11/F12/F13/F14）文件级不改假测量
（需要 SUMO 需求生成器 / 真孪生），只验"注入事件 + factors_applied 出现"，
方向与等级效果记 **BLOCKED**，不编造。

退出码：0 = 无 FAIL（有 BLOCKED 也返回 0，但会打印提示）；1 = 有 FAIL。
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TWIN_DIR = HERE.parent
sys.path.insert(0, str(TWIN_DIR))

import baseline  # noqa: E402
import factors  # noqa: E402
import run_assimilation as ra  # noqa: E402

#: 自检输出根目录（out/ 已 gitignore，不进仓库）
CHECK_ROOT = TWIN_DIR / "out" / "_selfcheck" / "factors"

#: 自检夹具时刻（固定，不读系统时钟）
FIXTURE_FROM = "2026-01-01T08:00:00+08:00"
FIXTURE_UNTIL = "2026-01-01T12:00:00+08:00"
EVAL_TS = "2026-01-01T09:00:00+08:00"

#: 因素表没给 demo 倍率时的**自检夹具值**（不是因素表真值；只验机制与方向）
FIXTURE_MULTIPLIER = 0.5

#: 文件级可模拟的 target（demand 需 SUMO 需求生成器 → 阻塞）
SIMULATABLE_TARGETS = ("c", "v_f", "lanes", "confidence")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fresh_dir(name: str) -> Path:
    path = CHECK_ROOT / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_base_artifacts() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """跑一次真网模式，拿断面候选 / before 基线 / 判级参数（产物必须真生成）。"""
    out_dir = fresh_dir("base")
    ra.run(["--mode", "network", "--out", str(out_dir)])
    sections = json.loads((out_dir / "sections_candidate.json").read_text(encoding="utf-8"))
    before = json.loads((out_dir / "segments_before.json").read_text(encoding="utf-8"))
    grading = baseline.load_grading()
    return sections, before, grading


def pick_multiplier(row: dict[str, Any]) -> tuple[float, str]:
    """取因素倍率：优先登记表 demo_multipliers 里**第一个不为 1.0** 的（1.0 是"昼/常态"，验不出方向）；
    没有就用夹具值（明示）。"""
    demo = row.get("demo_multipliers") or []
    for entry in demo:
        value = float(entry["multiplier"])
        if value != 1.0:
            return value, f"factors.json:demo_multipliers[{entry.get('label')}]"
    if demo:
        return 0.5, "check_fixture（登记表 demo_multipliers 全为 1.0，自检夹具值）"
    return FIXTURE_MULTIPLIER, "check_fixture（登记表无 demo 倍率，自检夹具值，非因素表真值）"


def pick_scope(
    row: dict[str, Any],
    sections_payload: dict[str, Any],
    observed_ids: set[str],
    observed_levels: dict[str, int],
    target: str,
) -> str | None:
    """受影响段的作用域：硬触发因素只打一个观测段（跳档可读），其余按 target 规则。"""
    hard_ids = {"F07", "F08"}
    if row["factor_id"] in hard_ids:
        candidates = sorted(
            observed_ids,
            key=lambda segment_id: (observed_levels.get(segment_id, 0), segment_id),
        )
        return candidates[0] if candidates else None
    return None  # demand / confidence 按注入规则落到 boundary 段 / 有数据段


def make_entry(
    row: dict[str, Any],
    target: str,
    multiplier: float,
    value_source: str,
    scope_segment: str | None,
    sections_payload: dict[str, Any],
    observed_ids: set[str],
) -> dict[str, Any]:
    """构造一条"生效因素"描述（与 scenario_injections 同形，供 inject_segments 消费）。"""
    entry = {
        "factor_id": row["factor_id"],
        "name": row.get("name") or row["factor_id"],
        "target": target,
        "multiplier": multiplier,
        "from": FIXTURE_FROM,
        "until": FIXTURE_UNTIL,
        "segment_scope": scope_segment,
        "scenario": "TC-16 自检夹具",
        "source": {
            "stage1": row.get("source_stage1"),
            "stage2": row.get("source_stage2"),
            "filler": row.get("filler"),
            "implementer": row.get("implementer"),
            "catalogue": "stations/factors.json",
            "scenario": "check_factors.py 自检注入（不是场景剧本）",
            "value_source": value_source,
        },
    }
    scope = factors.injection_scope(entry, sections_payload, observed_ids)
    entry["affected_segment_ids"] = scope["segment_ids"]
    entry["scope_resolved"] = scope["resolved"]
    entry["scope_reason"] = scope["reason"]
    return entry


def factor_applied_entries(segment: dict[str, Any], factor_id: str) -> list[dict[str, Any]]:
    return [item for item in segment.get("factors_applied") or [] if item.get("factor_id") == factor_id]


def verify_one(
    row: dict[str, Any],
    sections_payload: dict[str, Any],
    before: dict[str, Any],
    grading: dict[str, Any],
    observed_ids: set[str],
) -> dict[str, Any]:
    """注入单个因素并逐项验证（返回结果记录）。"""
    factor_id = row["factor_id"]
    catalogue_targets = list(row.get("targets") or [])
    simulatable = [target for target in catalogue_targets if target in SIMULATABLE_TARGETS]
    demand_targets = [target for target in catalogue_targets if target == "demand"]
    multiplier, value_source = pick_multiplier(row)
    observed_levels = {
        segment["segment_id"]: int(segment.get("level") or 0)
        for segment in before["segments"]
        if segment.get("confidence") is not None
    }
    result: dict[str, Any] = {
        "factor_id": factor_id,
        "name": row.get("name"),
        "targets": catalogue_targets,
        "multiplier": multiplier,
        "value_source": value_source,
        "checks": [],
        "blockers": [],
        "affected_count": 0,
        "status": "PASS",
    }
    if not simulatable and not demand_targets:
        result["status"] = "FAIL"
        result["checks"].append({"check": "因素可注入", "passed": False, "detail": "没有可识别 target"})
        return result

    entries: list[dict[str, Any]] = []
    for target in simulatable + demand_targets:
        scope_segment = pick_scope(
            row, sections_payload, observed_ids, observed_levels, target
        )
        entry = make_entry(
            row, target, multiplier, value_source, scope_segment, sections_payload, observed_ids
        )
        if entry["scope_resolved"] and entry["affected_segment_ids"]:
            entries.append(entry)

    if not entries:
        result["status"] = "BLOCKED"
        result["blockers"].append("作用范围为 0 段（例如无观测数据 / 段号未落地），无法验证注入效果")
        return result

    after_payload, records = factors.inject_segments(before, entries, grading)
    before_by_id = {segment["segment_id"]: segment for segment in before["segments"]}
    after_by_id = {segment["segment_id"]: segment for segment in after_payload["segments"]}
    affected: list[str] = []
    for entry in entries:
        for segment_id in entry["affected_segment_ids"]:
            if segment_id not in affected:
                affected.append(segment_id)
    result["affected_count"] = len(affected)

    # ---- ① factors_applied 出现（含 target / multiplier / until；按各自的受影响段查） ----
    missing: list[str] = []
    wrong: list[str] = []
    for entry in entries:
        for segment_id in entry["affected_segment_ids"]:
            segment = after_by_id[segment_id]
            applied = factor_applied_entries(segment, factor_id)
            matched = [item for item in applied if item.get("target") == entry["target"]]
            if not matched:
                missing.append(f"{segment_id}:{entry['target']}")
                continue
            for item in matched:
                if item.get("multiplier") != entry["multiplier"] or item.get("until") is None:
                    wrong.append(
                        f"{segment_id}:{entry['target']} multiplier={item.get('multiplier')} "
                        f"until={item.get('until')}"
                    )
    result["checks"].append(
        {
            "check": "受影响段 factors_applied 出现（target/multiplier/until 正确）",
            "passed": not missing and not wrong,
            "detail": f"affected {len(affected)} 段；缺 {missing[:3]}；错 {wrong[:3]}",
        }
    )

    # ---- ② 未受影响段逐字段不变 ----
    unaffected = [
        segment_id for segment_id in before_by_id if segment_id not in set(affected)
    ]
    changed_unaffected = [
        segment_id
        for segment_id in unaffected
        if before_by_id[segment_id] != after_by_id[segment_id]
    ]
    result["checks"].append(
        {
            "check": "未受影响段不变",
            "passed": not changed_unaffected,
            "detail": f"未受影响 {len(unaffected)} 段；被误改 {changed_unaffected[:3]}",
        }
    )

    # ---- ③ 方向校验（用量：容量 / 饱和度 / 速度 / 置信度 / 延误） ----
    direction_checks: list[dict[str, Any]] = []
    for record in records:
        direction_checks.extend(record.get("direction_checks") or [])
    result["checks"].append(
        {
            "check": "方向正确（容量↓/x↑/判级不降/v_f↓/畅通耗时不降/实际行程时间不降/置信度↓）",
            "passed": all(check["passed"] for check in direction_checks),
            "detail": f"{len(direction_checks)} 条方向断言，失败 "
            f"{[check for check in direction_checks if not check['passed']][:2]}",
        }
    )

    # ---- ④ 容量 / 速度按倍率折算（抽一条受影响段核对） ----
    num_checks: list[dict[str, Any]] = []
    level = factors.level_module()
    thresholds = level.load_thresholds()
    for entry in entries:
        target = entry["target"]
        if target not in ("c", "lanes", "v_f", "confidence"):
            continue
        for segment_id in entry["affected_segment_ids"][:2]:
            before_seg = before_by_id[segment_id]
            after_seg = after_by_id[segment_id]
            if target in ("c", "lanes") and isinstance(before_seg.get("c_base_vph"), (int, float)):
                expected = round(
                    float(before_seg["c_base_vph"]) * max(float(grading["factor_floor"]), entry["multiplier"]),
                    1,
                )
                num_checks.append(
                    {
                        "check": f"{segment_id} c_vph = c_base × {entry['multiplier']}",
                        "passed": abs(float(after_seg["c_vph"]) - expected) < 1e-6,
                        "detail": f"after={after_seg['c_vph']} expected={expected}",
                    }
                )
            if target == "v_f" and isinstance(before_seg.get("v_f_kmh"), (int, float)):
                expected = round(
                    float(before_seg["v_f_kmh"]) * max(float(grading["factor_floor"]), entry["multiplier"]),
                    2,
                )
                num_checks.append(
                    {
                        "check": f"{segment_id} v_f_kmh = base × {entry['multiplier']}",
                        "passed": abs(float(after_seg["v_f_kmh"]) - expected) < 1e-6,
                        "detail": f"after={after_seg['v_f_kmh']} expected={expected}",
                    }
                )
            if target == "confidence" and isinstance(before_seg.get("confidence"), (int, float)):
                expected = round(float(before_seg["confidence"]) * entry["multiplier"], 3)
                num_checks.append(
                    {
                        "check": f"{segment_id} confidence × {entry['multiplier']}",
                        "passed": abs(float(after_seg["confidence"]) - expected) < 1e-6,
                        "detail": f"after={after_seg['confidence']} expected={expected}",
                    }
                )
    if num_checks:
        result["checks"].append(
            {
                "check": "修正值与倍率一致（c / v_f / confidence）",
                "passed": all(check["passed"] for check in num_checks),
                "detail": f"{len(num_checks)} 条数值断言，失败 "
                f"{[check for check in num_checks if not check['passed']][:2]}",
            }
        )

    # ---- ⑤ 判级来自 canonical level.py（重算对账） ----
    level_mismatch: list[str] = []
    for segment_id in affected:
        recalc = level.grade(after_by_id[segment_id], thresholds)
        if recalc.get("level") != after_by_id[segment_id].get("level"):
            level_mismatch.append(segment_id)
    result["checks"].append(
        {
            "check": "判级与 work/perception/level.py 重算一致（不复制判级）",
            "passed": not level_mismatch,
            "detail": f"不一致 {level_mismatch[:3]}",
        }
    )

    # ---- ⑥ 硬触发（F07/F08）跳档 ----
    hard_ids = set(grading.get("hard_trigger_factor_ids") or [])
    if factor_id in hard_ids:
        target_level = int(grading["hard_trigger_level"])
        jump_ok = True
        details: list[str] = []
        for segment_id in affected:
            before_level = before_by_id[segment_id].get("level")
            after_level = after_by_id[segment_id].get("level")
            details.append(f"{segment_id}: {before_level} → {after_level}")
            if after_level != target_level or not isinstance(before_level, int) or before_level >= target_level:
                jump_ok = False
        result["checks"].append(
            {
                "check": f"硬触发跳档到 level={target_level}",
                "passed": jump_ok,
                "detail": "；".join(details),
            }
        )
    elif demand_targets and not simulatable:
        result["blockers"].append(
            "target=demand：文件级只登记注入事件、不改假测量；需求/等级效果需 SUMO 需求生成器（真孪生缺失）"
        )

    # ---- ⑦ 无 multiplier=1.0 占位 + 失效窗口不写 ----
    placeholder = [
        f"{segment['segment_id']}:{item.get('factor_id')}"
        for segment in after_payload["segments"]
        for item in segment.get("factors_applied") or []
        if float(item.get("multiplier", 0)) == 1.0 and item.get("factor_id") == factor_id
    ]
    expired_entry = dict(entries[0])
    expired_entry["from"] = "2030-01-01T00:00:00+08:00"
    expired_entry["until"] = "2030-01-01T01:00:00+08:00"
    filtered = factors.active_injections([expired_entry], EVAL_TS)
    expired_after, _ = factors.inject_segments(before, filtered, grading)
    expired_leak = [
        segment["segment_id"]
        for segment in expired_after["segments"]
        if factor_applied_entries(segment, factor_id)
    ]
    result["checks"].append(
        {
            "check": "无 multiplier=1.0 占位；失效窗口不注入",
            "passed": not placeholder and not expired_leak,
            "detail": f"占位 {placeholder[:3]}；失效窗口泄漏 {expired_leak[:3]}",
        }
    )

    # ---- ⑧ 可重复（同一注入连跑两遍 sha256 一致） ----
    again, _ = factors.inject_segments(before, entries, grading)
    hash_a = sha256_text(json.dumps(after_payload, ensure_ascii=False, sort_keys=True))
    hash_b = sha256_text(json.dumps(again, ensure_ascii=False, sort_keys=True))
    result["checks"].append(
        {
            "check": "同一注入两遍逐字段一致",
            "passed": hash_a == hash_b,
            "detail": f"sha={hash_a[:16]}…",
        }
    )

    if not all(check["passed"] for check in result["checks"]):
        result["status"] = "FAIL"
    elif result["blockers"]:
        result["status"] = "BLOCKED"
    return result


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    CHECK_ROOT.mkdir(parents=True, exist_ok=True)
    sections_payload, before, grading = load_base_artifacts()
    _payload, catalogue = factors.load_factor_catalogue()
    observed_ids = {
        segment["segment_id"] for segment in before["segments"] if segment.get("confidence") is not None
    }
    print("多因素自检（IKMS19 · TC-16 逐因素注入）")
    print(
        f"  基线：真网 {len(before['segments'])} 段（有指标数据的 {len(observed_ids)} 段："
        f"{'、'.join(sorted(observed_ids)) or '无'}）· 判级阈值读 stations/thresholds.json"
    )
    print(f"  硬触发因素：{grading.get('hard_trigger_factor_ids')} → level={grading.get('hard_trigger_level')}")
    print()
    results: list[dict[str, Any]] = []
    for factor_id in factors.FACTOR_IDS:
        row = catalogue[factor_id]
        result = verify_one(row, sections_payload, before, grading, observed_ids)
        results.append(result)
        checks_text = "；".join(
            f"{check['check']}={'PASS' if check['passed'] else 'FAIL'}" for check in result["checks"]
        )
        print(
            f"  {result['status']:<7} {result['factor_id']} {result['name'][:18]:<20} "
            f"targets={'/'.join(result['targets']) or '—'} mult={result['multiplier']} "
            f"affected={result['affected_count']}"
        )
        if result["status"] != "PASS":
            for blocker in result["blockers"]:
                print(f"          ↳ BLOCKED：{blocker}")
            failed = [check for check in result["checks"] if not check["passed"]]
            for check in failed:
                print(f"          ↳ FAIL：{check['check']}（{check['detail']}）")
        else:
            print(f"          ↳ {checks_text}")

    passed = [result for result in results if result["status"] == "PASS"]
    blocked = [result for result in results if result["status"] == "BLOCKED"]
    failed = [result for result in results if result["status"] == "FAIL"]
    print()
    print(f"结论：{len(passed)} 项 PASS · {len(blocked)} 项 BLOCKED · {len(failed)} 项 FAIL")
    if blocked:
        print(
            "  BLOCKED 因素："
            + "、".join(result["factor_id"] for result in blocked)
            + "（需 SUMO 需求生成器 / 真孪生，文件级不编造需求效果）"
        )
    if failed:
        print("  FAIL 因素：" + "、".join(result["factor_id"] for result in failed))
    report_path = CHECK_ROOT / "tc16_report.json"
    report = {
        "ts": EVAL_TS,
        "is_simulated": True,
        "mode": "tc16-selfcheck",
        "fixture": {
            "from": FIXTURE_FROM,
            "until": FIXTURE_UNTIL,
            "evaluation_ts": EVAL_TS,
            "fixture_multiplier": FIXTURE_MULTIPLIER,
            "note": "自检夹具：不是场景剧本，不是因素表真值；demo_multipliers 优先，缺则用夹具值",
        },
        "baseline": {
            "segments": len(before["segments"]),
            "observed_segments": sorted(observed_ids),
        },
        "factors": results,
        "summary": {
            "pass": len(passed),
            "blocked": len(blocked),
            "fail": len(failed),
        },
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"  报告：{report_path}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
