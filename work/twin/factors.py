"""因素注入:按站点包的因素表与场景注入事件,给出"这一刻实际生效"的因素清单。

输入:stations/factors.json(T5)+ 场景注入事件(stations/scenarios.json)
输出:生效因素列表(最终写进 segments 的 factors_applied,契约 1.1)、注入后的 segments 快照、
     逐因素注入报告(来源 / 生效区间 / 受影响段 / 方向校验)
口径:未生效的因素**不写进数组**(不写 multiplier=1.0 占位);
     各因素对 c / v_f 分别相乘,合成后不低于原值的 40%【待标定】。

## 本单（IKMS19）补的"真路径"

1. `load_factor_catalogue()`：读 `stations/factors.json` 的 F01~F14 登记表（名称 / target /
   demo 倍率 / 来源阶段 / 实现人）——**因素值不在代码里写死**；
2. `scenario_injections()`：把场景剧本里的注入事件（`factor_id` / `target` / `multiplier` /
   `from` / `until` / 可选 `segment_id`）与登记表合并，做成"生效因素描述"；
3. `inject_segments()`：按 `target` 把因素**注入到段**（改 `c_vph` / `x` / `v_f_kmh` /
   `confidence`；`demand` 只登记不改假测量），重算 `factors_applied` 与判级
   （判级**只调** `work/perception/level.py` 的 `grade`，**不复制判级逻辑**），产出 before/after；
4. **命名空间纪律**：`segment_id` 不在本站真网段号集合内（例如 7 节点样例网的 `SEG-003`）
   → 记为**未落地**（不猜映射、不混命名空间），因素不注入。

## 因素作用的段（target → 受影响段）

| `target` | 注入到哪些段 | 为什么 |
|---|---|---|
| `c` / `lanes` / `v_f` | 全段；带 `segment_id` 时只注入该段 | 天气/事故/施工影响物理通行能力与限速 |
| `confidence` | **有指标数据的段**（confidence 非空） | 只影响判级可用性门，不改物理世界 |
| `demand` | **boundary 候选段** | 需求改变的是边界来车；站内段不直接改（需 SUMO 需求生成器，一期阻塞） |

用法:由 `run_assimilation.py` / `loop.py` 调用,不单独执行。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

#: 本文件位于 work/twin/ → 仓库根是 parents[1]
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
STATIONS = REPO_ROOT / "stations"

#: 因素能作用的量(契约 1.1:取值封闭,新增要改契约)
FACTOR_TARGETS = ("c", "v_f", "demand", "lanes", "confidence")

#: 合成下限:各因素连乘后不低于原值的这个比例(契约 1.1 / 手册,【待标定】)
FLOOR_RATIO = 0.4  # 【待标定】

#: 一期的14类因素编号（只用于校验登记表完整；值一律从 factors.json 读）
FACTOR_IDS = tuple(f"F{index:02d}" for index in range(1, 15))

#: 判级模块（唯一实现：work/perception/level.py；本模块只读 import，不复制逻辑）
_LEVEL_MODULE: Any = None


def read_json(path: Path) -> dict[str, Any]:
    """读一个 UTF-8 JSON 文件(显式编码,换机器不乱码)。"""
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def level_module() -> Any:
    """只读加载 canonical 判级模块 `work/perception/level.py`（缺失/导入失败直接报错）。"""
    global _LEVEL_MODULE
    if _LEVEL_MODULE is not None:
        return _LEVEL_MODULE
    path = REPO_ROOT / "work" / "perception" / "level.py"
    if not path.is_file():
        raise SystemExit(f"缺判级唯一实现 {path}（因素注入后判级必须调它，不复制判级逻辑）")
    spec = importlib.util.spec_from_file_location("perception_level", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"无法加载判级模块 {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _LEVEL_MODULE = module
    return module


# ============================================================================
# 因素登记表 / 场景注入事件
# ============================================================================


def load_factor_catalogue(
    stations_dir: Path | str | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """读 `stations/factors.json`：返回 `(payload, factor_id → 登记行)`，并校验 F01~F14 齐全。"""
    path = Path(stations_dir or STATIONS) / "factors.json"
    if not path.is_file():
        raise SystemExit(f"缺站点包 {path}（因素表是因素值的唯一出处）")
    payload = read_json(path)
    rows = payload.get("factors")
    if not isinstance(rows, list) or not rows:
        raise SystemExit(f"{path} 缺非空 factors 数组")
    catalogue: dict[str, dict[str, Any]] = {}
    for row in rows:
        factor_id = str(row.get("factor_id") or "")
        if not factor_id:
            raise SystemExit(f"{path} 的 factors[] 里有因素缺 factor_id")
        if factor_id in catalogue:
            raise SystemExit(f"{path} 的 factors[] 因素编号重复：{factor_id}")
        targets = row.get("targets") or []
        bad = [target for target in targets if target not in FACTOR_TARGETS]
        if bad:
            raise SystemExit(
                f"{path} 的因素 {factor_id} 有非法 target {bad}（只允许 {FACTOR_TARGETS}）"
            )
        catalogue[factor_id] = dict(row)
    missing = [factor_id for factor_id in FACTOR_IDS if factor_id not in catalogue]
    if missing:
        raise SystemExit(f"{path} 缺因素登记 {missing}（一期 14 类逐条登记）")
    return payload, catalogue


def _merge_one(
    catalogue: dict[str, dict[str, Any]], injection: dict[str, Any], scenario_id: str
) -> dict[str, Any]:
    """一条场景注入事件 + 登记表 → 归一后的"生效因素"描述（值来源逐项写清）。"""
    factor_id = str(injection.get("factor_id") or "")
    if not factor_id:
        raise SystemExit(f"场景 {scenario_id} 的 factors[] 里有注入事件缺 factor_id")
    row = catalogue.get(factor_id)
    if row is None:
        raise SystemExit(f"场景 {scenario_id} 注入了未登记的因素 {factor_id}（先补 stations/factors.json）")
    target = injection.get("target")
    if target not in FACTOR_TARGETS:
        raise SystemExit(
            f"场景 {scenario_id} 的因素 {factor_id} 的 target={target!r} 非法（只允许 {FACTOR_TARGETS}）"
        )
    allowed_targets = row.get("targets") or []
    if target not in allowed_targets:
        raise SystemExit(
            f"场景 {scenario_id} 的因素 {factor_id} 的 target={target!r} 不在登记表 targets "
            f"{allowed_targets} 内（不擅自给因素加作用量）"
        )
    multiplier = injection.get("multiplier")
    if not isinstance(multiplier, (int, float)) or isinstance(multiplier, bool):
        raise SystemExit(f"场景 {scenario_id} 的因素 {factor_id} 缺数值 multiplier")
    return {
        "factor_id": factor_id,
        "name": str(row.get("name") or factor_id),
        "target": str(target),
        "multiplier": round(float(multiplier), 4),
        "from": injection.get("from"),
        "until": injection.get("until"),
        "segment_scope": injection.get("segment_id"),
        "scenario": scenario_id,
        "source": {
            "stage1": row.get("source_stage1"),
            "stage2": row.get("source_stage2"),
            "filler": row.get("filler"),
            "implementer": row.get("implementer"),
            "catalogue": "stations/factors.json",
            "scenario": f"stations/scenarios.json（{scenario_id}）",
        },
    }


def scenario_injections(
    catalogue: dict[str, dict[str, Any]],
    scenario_row: dict[str, Any],
) -> list[dict[str, Any]]:
    """场景记录 → 生效因素描述列表（按场景剧本顺序，确定性）。"""
    scenario_id = str(scenario_row.get("scenario_id") or "?")
    injected = scenario_row.get("factors") or []
    if not isinstance(injected, list):
        raise SystemExit(f"场景 {scenario_id} 的 factors 不是数组")
    return [_merge_one(catalogue, dict(item), scenario_id) for item in injected]


def derive_evaluation_ts(injections: list[dict[str, Any]], fallback_ts: str) -> tuple[str, str]:
    """从因素生效窗口派生"演示评估时刻"（不读系统时钟）。

    规则：取所有 `from` 里最晚的一个——这样同场景的多个因素都处在各自的生效区间内；
    没有 `from` 时用输入快照的 ts。返回 `(ts, 依据说明)`。
    """
    starts = [str(item["from"]) for item in injections if item.get("from")]
    if not starts:
        return fallback_ts, "fallback:输入快照 ts（场景因素无 from）"
    latest = max(starts)
    return latest, "derived:场景因素 from 的最晚值（保证同场景因素在各自生效区间内）"


def factor_is_active(factor: dict[str, Any], now_ts: str) -> bool:
    """该因素在 now_ts 是否还在生效(按 from / until 判定)。

    口径:until 到了就自动失效(手册);长期因素给远期时间,不留空。
    `from` 缺失视为"早已生效"；`until` 缺失视为"长期有效"。
    """
    start = factor.get("from")
    if start and str(now_ts) < str(start):
        return False
    until = factor.get("until")
    if not until:
        return True
    return str(now_ts) <= str(until)


def active_injections(
    injections: list[dict[str, Any]], now_ts: str
) -> list[dict[str, Any]]:
    """过滤出 now_ts 时刻实际生效的因素（失效的不写进 factors_applied）。"""
    return [item for item in injections if factor_is_active(item, now_ts)]


# ============================================================================
# 因素 → 段（作用范围）
# ============================================================================


def injection_scope(
    injection: dict[str, Any],
    sections_payload: dict[str, Any],
    observed_ids: set[str],
) -> dict[str, Any]:
    """算一条因素注入的受影响段集合；段号不在本站段号内 → 未落地（不猜映射）。"""
    all_ids = [item["segment_id"] for item in sections_payload["sections"]]
    all_set = set(all_ids)
    boundary_ids = [
        item["segment_id"] for item in sections_payload["sections"] if item["role"] == "boundary"
    ]
    scope = injection.get("segment_scope")
    if scope is not None:
        if str(scope) not in all_set:
            return {
                "resolved": False,
                "segment_ids": [],
                "reason": (
                    f"段号 {scope!r} 不在本站段号集合内（疑似 7 节点样例网 SEG-### / 占位件），"
                    "不猜映射、不混命名空间"
                ),
            }
        return {"resolved": True, "segment_ids": [str(scope)], "reason": None}
    target = injection["target"]
    if target in ("c", "v_f", "lanes"):
        return {"resolved": True, "segment_ids": list(all_ids), "reason": None}
    if target == "confidence":
        affected = [segment_id for segment_id in all_ids if segment_id in observed_ids]
        return {
            "resolved": True,
            "segment_ids": affected,
            "reason": None if affected else "无有指标数据的段（confidence 作用在数据可用性门上）",
        }
    if target == "demand":
        return {"resolved": True, "segment_ids": list(boundary_ids), "reason": None}
    raise SystemExit(f"未知因素 target={target!r}")


def prepare_injections(
    catalogue: dict[str, dict[str, Any]],
    scenario_row: dict[str, Any],
    sections_payload: dict[str, Any],
    observed_ids: set[str],
    now_ts: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """场景注入 → （生效且可注入的因素, 未生效/未落地因素）。

    每条因素补 `affected_segment_ids` 与 `scope_reason`；**未生效不占位**（不进生效清单）。
    """
    active: list[dict[str, Any]] = []
    inactive: list[dict[str, Any]] = []
    for injection in scenario_injections(catalogue, scenario_row):
        if not factor_is_active(injection, now_ts):
            inactive.append({**injection, "reason": "不在生效区间（from/until）"})
            continue
        scope = injection_scope(injection, sections_payload, observed_ids)
        enriched = {
            **injection,
            "affected_segment_ids": scope["segment_ids"],
            "scope_resolved": scope["resolved"],
            "scope_reason": scope["reason"],
        }
        if not scope["resolved"] or not scope["segment_ids"]:
            inactive.append({**enriched, "reason": scope["reason"] or "作用范围为 0 段"})
            continue
        active.append(enriched)
    return active, inactive


# ============================================================================
# 注入（改世界，不改结论）
# ============================================================================


def compose(base_c: float, base_v_f: float, applied: list[dict[str, Any]]) -> dict[str, float]:
    """把生效因素合成到通行能力与畅通速度上。

    返回 {"c": ..., "v_f": ...};合成结果按 FLOOR_RATIO 保底,不允许打到 0 以下。
    """
    c, v_f = base_c, base_v_f
    for factor in applied:
        target = factor.get("target")
        if target not in FACTOR_TARGETS:
            raise ValueError(f"未知因素作用量 target={target!r}")
        multiplier = float(factor.get("multiplier", 1.0))
        if target in ("c", "lanes"):
            c *= multiplier
        elif target == "v_f":
            v_f *= multiplier
    return {
        "c": max(c, base_c * FLOOR_RATIO),
        "v_f": max(v_f, base_v_f * FLOOR_RATIO),
    }


def travel_delay_s(segment: dict[str, Any]) -> float | None:
    """段内行驶延误（秒）= 实际行程时间 − 自由流行程时间；缺 v/v_f 时返回 None（不编数）。"""
    length = segment.get("L_seg_m")
    v = segment.get("v_kmh")
    v_f = segment.get("v_f_kmh")
    if not isinstance(length, (int, float)) or float(length) <= 0:
        return None
    if not isinstance(v, (int, float)) or float(v) <= 0:
        return None
    if not isinstance(v_f, (int, float)) or float(v_f) <= 0:
        return None
    actual_s = float(length) / (float(v) / 3.6)
    free_s = float(length) / (float(v_f) / 3.6)
    return round(actual_s - free_s, 2)


def _apply_to_segment(
    segment: dict[str, Any],
    entries_by_target: dict[str, list[dict[str, Any]]],
    grading: dict[str, Any],
    level: Any,
    thresholds: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, float]]:
    """把一条段上的因素注入进去，返回 `(改后的段, 关键量 before→after)`。"""
    after = dict(segment)
    before_snapshot = {
        "c_vph": segment.get("c_vph"),
        "x": segment.get("x"),
        "v_f_kmh": segment.get("v_f_kmh"),
        "v_kmh": segment.get("v_kmh"),
        "confidence": segment.get("confidence"),
        "level": segment.get("level"),
        "delay_s": travel_delay_s(segment),
    }
    factors_applied: list[dict[str, Any]] = list(segment.get("factors_applied") or [])
    for target in ("c", "lanes", "v_f", "demand", "confidence"):
        for entry in entries_by_target.get(target, []):
            factors_applied.append(
                {
                    "factor_id": entry["factor_id"],
                    "name": entry["name"],
                    "target": entry["target"],
                    "multiplier": entry["multiplier"],
                    "until": entry["until"],
                }
            )
    # 同一因素多 target 时 factors_applied 会有多条（factor_id 相同、target 不同）——契约允许逐项写明。
    after["factors_applied"] = factors_applied

    # ① 容量（target ∈ c / lanes）：c = c_base × ∏multiplier，保底 factor_floor。
    #    **同一因素多 target 时只乘一次**（例如 F06 targets=[lanes,c]，若两条各乘一次会重复折算）。
    c_multipliers = _dedup_multipliers(entries_by_target, ("c", "lanes"))
    base_c = segment.get("c_base_vph")
    if c_multipliers and isinstance(base_c, (int, float)) and float(base_c) > 0:
        floor = float(grading.get("factor_floor", FLOOR_RATIO))
        coeff = max(floor, _product(c_multipliers))
        after["c_vph"] = round(float(base_c) * coeff, 1)
        q = after.get("q_vph")
        if isinstance(q, (int, float)):
            after["x"] = round(float(q) / after["c_vph"], 3) if after["c_vph"] else after.get("x")

    # ② 畅通速度（target = v_f）：v_f × ∏multiplier；实际车速不得超过新 v_f
    v_f_multipliers = _dedup_multipliers(entries_by_target, ("v_f",))
    base_v_f = segment.get("v_f_kmh")
    if v_f_multipliers and isinstance(base_v_f, (int, float)) and float(base_v_f) > 0:
        floor = float(grading.get("factor_floor", FLOOR_RATIO))
        v_f = float(base_v_f) * max(floor, _product(v_f_multipliers))
        after["v_f_kmh"] = round(v_f, 2)
        v = after.get("v_kmh")
        if isinstance(v, (int, float)) and float(v) > after["v_f_kmh"]:
            after["v_kmh"] = after["v_f_kmh"]

    # ③ 检测置信度（target = confidence）：只影响判级可用性门，不改物理世界
    confidence_multipliers = _dedup_multipliers(entries_by_target, ("confidence",))
    confidence = segment.get("confidence")
    if confidence_multipliers and isinstance(confidence, (int, float)):
        after["confidence"] = round(
            float(confidence) * _product(confidence_multipliers), 3
        )

    # ④ 需求（target = demand）：文件级只登记注入事件；真值要等 SUMO 需求生成器（一期阻塞）
    after["_demand_injected"] = bool(entries_by_target.get("demand"))

    # ⑤ 判级：只调 canonical level.py（不复制判级逻辑）
    graded = level.grade(after, thresholds)
    after["level"] = graded.get("level", after.get("level"))
    after["level_name"] = graded.get("level_name", after.get("level_name"))
    if graded.get("triggered_by") is not None:
        after["triggered_by"] = graded["triggered_by"]
    if graded.get("available") is not None:
        after["available"] = graded["available"]
    if "ci" in graded:
        after["ci"] = graded["ci"]
    if graded.get("available") is False and graded.get("gate_reason"):
        after["gate_reason"] = graded["gate_reason"]
    elif "gate_reason" in after and graded.get("available") is not False:
        after.pop("gate_reason", None)

    after_snapshot = {
        "c_vph": after.get("c_vph"),
        "x": after.get("x"),
        "v_f_kmh": after.get("v_f_kmh"),
        "v_kmh": after.get("v_kmh"),
        "confidence": after.get("confidence"),
        "level": after.get("level"),
        "delay_s": travel_delay_s(after),
    }
    return after, {"before": before_snapshot, "after": after_snapshot}


def _product(values: list[float]) -> float:
    result = 1.0
    for value in values:
        result *= float(value)
    return result


def _dedup_multipliers(
    entries_by_target: dict[str, list[dict[str, Any]]], targets: tuple[str, ...]
) -> list[float]:
    """同一因素的多个 target 只取一次倍率（避免 F06 targets=[lanes,c] 被重复折算）。"""
    per_factor: dict[str, float] = {}
    for target in targets:
        for entry in entries_by_target.get(target, []):
            factor_id = str(entry.get("factor_id"))
            if factor_id not in per_factor:
                per_factor[factor_id] = float(entry["multiplier"])
    return list(per_factor.values())


def inject_segments(
    segments_payload: dict[str, Any],
    active: list[dict[str, Any]],
    grading: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """把生效因素注入 segments（before → after），返回 `(after_payload, 逐因素记录)`。

    只改**受影响段**；未受影响段逐字段不变（TC-16「未受影响路段不变」）。
    """
    level = level_module()
    thresholds = level.load_thresholds()
    entries_by_segment: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for entry in active:
        for segment_id in entry["affected_segment_ids"]:
            entries_by_segment.setdefault(segment_id, {}).setdefault(entry["target"], []).append(
                entry
            )
    after_segments: list[dict[str, Any]] = []
    comparisons: dict[str, dict[str, Any]] = {}
    for segment in segments_payload["segments"]:
        segment_id = segment["segment_id"]
        entries = entries_by_segment.get(segment_id)
        if not entries:
            after_segments.append(dict(segment))
            continue
        after, comparison = _apply_to_segment(segment, entries, grading, level, thresholds)
        after.pop("_demand_injected", None)
        after_segments.append(after)
        comparisons[segment_id] = comparison

    # 逐因素记录：受影响段 / 未落地 / 方向校验
    records: list[dict[str, Any]] = []
    for entry in active:
        affected = [
            segment_id
            for segment_id in entry["affected_segment_ids"]
            if segment_id in comparisons
        ]
        checks: list[dict[str, Any]] = []
        target = entry["target"]
        multiplier = float(entry["multiplier"])
        for segment_id in affected:
            comparison = comparisons[segment_id]
            before, after = comparison["before"], comparison["after"]
            if target in ("c", "lanes"):
                if isinstance(before["c_vph"], (int, float)) and isinstance(
                    after["c_vph"], (int, float)
                ):
                    checks.append(
                        {
                            "segment_id": segment_id,
                            "check": "c_vph 不升（容量被压缩）",
                            "before": before["c_vph"],
                            "after": after["c_vph"],
                            "passed": after["c_vph"] <= before["c_vph"] if multiplier < 1 else True,
                        }
                    )
                if isinstance(before["x"], (int, float)) and isinstance(after["x"], (int, float)):
                    checks.append(
                        {
                            "segment_id": segment_id,
                            "check": "x 不降（饱和度不降）",
                            "before": before["x"],
                            "after": after["x"],
                            "passed": after["x"] >= before["x"] if multiplier < 1 else True,
                        }
                    )
            elif target == "v_f":
                if isinstance(before["v_f_kmh"], (int, float)) and isinstance(
                    after["v_f_kmh"], (int, float)
                ):
                    checks.append(
                        {
                            "segment_id": segment_id,
                            "check": "v_f 不升（畅通速度被压缩）",
                            "before": before["v_f_kmh"],
                            "after": after["v_f_kmh"],
                            "passed": (
                                after["v_f_kmh"] <= before["v_f_kmh"] if multiplier < 1 else True
                            ),
                        }
                    )
                    # 畅通耗时（L/v_f）方向：限速被压 → 自由流耗时增加
                    length = after.get("L_seg_m")
                    if isinstance(length, (int, float)) and float(length) > 0:
                        free_before = round(float(length) / (float(before["v_f_kmh"]) / 3.6), 2)
                        free_after = round(float(length) / (float(after["v_f_kmh"]) / 3.6), 2)
                        checks.append(
                            {
                                "segment_id": segment_id,
                                "check": "畅通耗时（L/v_f）不降",
                                "before": free_before,
                                "after": free_after,
                                "passed": free_after >= free_before if multiplier < 1 else True,
                            }
                        )
                if isinstance(before["v_kmh"], (int, float)) and isinstance(
                    after["v_kmh"], (int, float)
                ):
                    checks.append(
                        {
                            "segment_id": segment_id,
                            "check": "实际车速不升（v ≤ v_f 上限）",
                            "before": before["v_kmh"],
                            "after": after["v_kmh"],
                            "passed": (
                                after["v_kmh"] <= before["v_kmh"] if multiplier < 1 else True
                            ),
                        }
                    )
                    length = after.get("L_seg_m")
                    if isinstance(length, (int, float)) and float(length) > 0:
                        travel_before = round(float(length) / (float(before["v_kmh"]) / 3.6), 2)
                        travel_after = round(float(length) / (float(after["v_kmh"]) / 3.6), 2)
                        checks.append(
                            {
                                "segment_id": segment_id,
                                "check": "实际行程时间不降",
                                "before": travel_before,
                                "after": travel_after,
                                "passed": travel_after >= travel_before if multiplier < 1 else True,
                            }
                        )
            elif target == "confidence":
                if isinstance(before["confidence"], (int, float)) and isinstance(
                    after["confidence"], (int, float)
                ):
                    checks.append(
                        {
                            "segment_id": segment_id,
                            "check": "confidence 不升（可用性门收紧）",
                            "before": before["confidence"],
                            "after": after["confidence"],
                            "passed": (
                                after["confidence"] <= before["confidence"]
                                if multiplier < 1
                                else True
                            ),
                        }
                    )
            # 等级方向：只有"改世界"的因素（c / lanes / v_f）才要求判级不降；
            # demand 文件级不改假测量（需 SUMO 需求生成器）；confidence 只影响可用性门，不参与等级方向。
            if target in ("c", "lanes", "v_f") and isinstance(
                before["level"], (int, float)
            ) and isinstance(after["level"], (int, float)):
                checks.append(
                    {
                        "segment_id": segment_id,
                        "check": "判级不降（等级方向正确）",
                        "before": before["level"],
                        "after": after["level"],
                        "passed": after["level"] >= before["level"],
                    }
                )
        records.append(
            {
                "factor_id": entry["factor_id"],
                "name": entry["name"],
                "target": target,
                "multiplier": multiplier,
                "from": entry.get("from"),
                "until": entry.get("until"),
                "segment_scope": entry.get("segment_scope"),
                "affected_segment_ids": affected,
                "affected_count": len(affected),
                "unaffected_count": len(segments_payload["segments"]) - len(affected),
                "source": entry["source"],
                "effects": (
                    "recorded_only：需求类因素需 SUMO 需求生成器，文件级不改假测量"
                    if target == "demand"
                    else "segments_corrected"
                ),
                "direction_checks": checks,
                "direction_passed": all(check["passed"] for check in checks) if checks else None,
            }
        )
    after_payload = {
        "ts": segments_payload.get("ts"),
        "window_sec": segments_payload.get("window_sec"),
        "is_simulated": True,
        "source_chain": segments_payload.get("source_chain"),
        "baseline_kind": segments_payload.get("baseline_kind"),
        "note": (
            "因素注入后的孪生段快照（演示数据（模拟））：只改受影响段；"
            "判级调用 work/perception/level.py 唯一实现，未复制判级逻辑。"
        ),
        "segments": after_segments,
    }
    return after_payload, records


# ============================================================================
# 旧接口（loop.py 用；样例路径行为不变）
# ============================================================================


def load_station_factors(cfg: Any, scene: Any) -> list[dict[str, Any]]:
    """装载站点包的因素表并解析出注入事件。

    --no-sumo:站点包未到位,返回空清单(样例的 factors_applied 已烘在样例里)。
    真孪生:读 stations/factors.json(T5),合并 scenario 的注入事件。
    """
    if cfg.no_sumo:
        return []
    catalogue_payload, catalogue = load_factor_catalogue(getattr(cfg, "stations_dir", None))
    del catalogue_payload
    scenario_id = str(getattr(scene, "name", ""))
    row = {"scenario_id": scenario_id, "factors": list(getattr(scene, "injected", []))}
    injections = scenario_injections(catalogue, row)
    now_ts = getattr(scene, "evaluation_ts", None)
    if now_ts:
        return active_injections(injections, str(now_ts))
    return injections
