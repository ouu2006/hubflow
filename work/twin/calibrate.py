"""数据同化:把视频链路的边界断面实测回灌给孪生(每 60 s、带门控)。

输入:视频链路实测(边界断面)+ stations/scenarios.json 的 assimilation 开关
输出:assimilation_state.json(契约第三节:带 ts 与 is_simulated 的信封 + edges 数组)
口径:**只有 role="boundary" 的断面允许回灌**;role="internal" 的断面**永远**
     assimilating=false、reason 固定 internal_not_allowed —— 这是硬规则,
     否则孪生变成"录像回放"、推荐再也改不了路况(TC-20 / M1-10)。

本文件有两条路径:

1. **`build_state()`（旧样例路径，保留）**：`loop.py --no-sumo` 用 `samples/assimilation_state_sample.json`
   过一遍硬规则再落盘；输出与改造前逐字段一致（不动旧链路的产物形状）；
2. **`build_assimilation()`（真路径，Issue IKMS19）**：读断面候选清单（`sections.py`）+ 孪生基线
   （`baseline.py`）+ 视频观测，逐段做**门控 → 偏差 → 回灌判定**，产出
   `assimilation_state.json` + `assimilation_log.json`（回灌/停灌日志，TC-20 第④项要求"日志可见"）。

## 门控与熔断（README 第 9.2 节 / 契约 §6.2）

| 情形 | `assimilating` | `gate.reason` |
|---|---|---|
| 门控通过（confidence ≥ confidence_min 且 data_age_s ≤ data_age_max_s） | `true` | `null` |
| 置信度不足 | `false` | `gate_rejected`（`gate.cause="confidence_low"`） |
| 数据过期 | `false` | `gate_rejected`（`gate.cause="data_age"`） |
| internal 断面 | `false` | `internal_not_allowed`（**硬规则，永远**） |
| 场景关同化 `enabled=false` | `false` | `assimilation_disabled`（退回默认需求） |
| 该段不在场景 `edges` 白名单 | `false` | `edge_not_enabled` |
| 场景 `edges` 未落到本站真网段号（占位件） | `false` | `config_unresolved` |
| 该 boundary 段没有视频/断面观测 | `false` | `no_observation` |

> **二期熔断（M2-9）**：连续 N 次（默认 3，`fuse_fail_streak`）回灌后偏差仍超阈值 →
> 自动关闭该断面并告警。本文件只落**判定逻辑与日志字段**（`deviation` / `fuse`），
> 真正"连续 N 次"要等真孪生主循环跑时序才有意义——一期如实标阻塞，不假装跑过。

用法:由 `run_assimilation.py` / `loop.py` 调用,不单独执行。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

#: 本文件位于 work/twin/ → 仓库根是 parents[1]
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]

#: 断面角色(契约 6.1,取值封闭)
SECTION_ROLES = ("boundary", "internal")

#: 内部断面被拒的固定原因码(契约第三节硬规则)
REASON_INTERNAL = "internal_not_allowed"

#: boundary 断面 gate 未过被拒的固定原因码(回灌周期内的门控拒绝,Sourcery #79 待办①)
REASON_GATE_REJECTED = "gate_rejected"

#: 其余停灌原因码(本单新增,全部写进 gate.reason 供页面/日志区分;不改契约字段形状)
REASON_DISABLED = "assimilation_disabled"
REASON_EDGE_NOT_ENABLED = "edge_not_enabled"
REASON_CONFIG_UNRESOLVED = "config_unresolved"
REASON_NO_OBSERVATION = "no_observation"

#: 门控拒绝的具体原因(写进 gate.cause,便于页面/日志说清是哪个门没过)
CAUSE_CONFIDENCE_LOW = "confidence_low"
CAUSE_DATA_AGE = "data_age"

#: 回灌周期(README 第六节:每 60 s 一次)
PERIOD_S = 60

#: 视频链路快照的默认相对路径(主循环上游产物;缺失时按候选列表找同级 checkout 只读参考)
VIDEO_SNAPSHOT_REL = Path("work/perception/out/latest/segments_video.json")

#: 默认门控(契约 §6.2 的【待标定】值;真值以 stations/scenarios.json 为准)
DEFAULT_GATE = {"confidence_min": 0.6, "data_age_max_s": 120}


def read_json(path: Path) -> dict[str, Any]:
    """读一个 UTF-8 JSON 文件(显式编码,换机器不乱码)。"""
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


# ============================================================================
# 输入:视频快照（同化观测的唯一来源）
# ============================================================================


def find_video_snapshot(
    repo_root: Path | str | None = None,
    override: str | Path | None = None,
    seg_prefix: str | None = None,
) -> tuple[Path | None, str, list[dict[str, Any]]]:
    """定位视频快照：返回 `(路径或 None, 来源说明, 搜索记录)`。

    **命名空间优先**：同级 checkout / 旧工作树里可能躺着**别的命名空间**的旧快照
    （例如 7 节点样例网 `SEG-###`）；本函数按本站 `seg_prefix`（如 `SZ`）过滤，
    不匹配的候选只记进搜索记录、**不采用**——避免把旧样例快照喂进真网同化（不混命名空间）。
    """
    root = Path(repo_root) if repo_root else REPO_ROOT
    searched: list[dict[str, Any]] = []
    if override:
        path = Path(override)
        if not path.is_file():
            raise SystemExit(f"--video 指向的文件不存在：{path}")
        return path, "cli:--video", [
            {"path": str(path), "status": "chosen", "source": "cli:--video"}
        ]
    pattern = re.compile(rf"^{re.escape(str(seg_prefix))}-\d{{3,}}$") if seg_prefix else None
    candidates: list[tuple[Path, str]] = [(root / VIDEO_SNAPSHOT_REL, "repo")]
    parent = root.parent
    if parent.is_dir():
        siblings: list[tuple[bool, str, Path]] = []
        for child in sorted(parent.iterdir()):
            if child == root or not child.is_dir():
                continue
            path = child / VIDEO_SNAPSHOT_REL
            if not path.is_file():
                continue
            # 主 checkout 的 .git 是目录；git worktree 的 .git 是文件 → 优先主 checkout（只读参考）
            is_worktree = (child / ".git").is_file()
            siblings.append((is_worktree, child.name, path))
        for is_worktree, name, path in sorted(siblings):
            candidates.append((path, f"sibling:{name}"))
    for path, source in candidates:
        if not path.is_file():
            searched.append({"path": str(path), "source": source, "status": "missing"})
            continue
        try:
            payload = read_json(path)
        except (OSError, ValueError) as exc:
            searched.append(
                {"path": str(path), "source": source, "status": f"unreadable:{exc}"}
            )
            continue
        segment_ids = [
            str(row.get("segment_id"))
            for row in (payload.get("segments") or [])
            if isinstance(row, dict)
        ]
        if pattern is not None and segment_ids and not all(
            pattern.match(segment_id) for segment_id in segment_ids
        ):
            searched.append(
                {
                    "path": str(path),
                    "source": source,
                    "status": f"namespace_mismatch（需要 {seg_prefix}-###，实际 {segment_ids}）",
                }
            )
            continue
        searched.append({"path": str(path), "source": source, "status": "chosen"})
        return path, source, searched
    return None, "missing", searched


def load_video_snapshot(path: Path) -> dict[str, Any]:
    """读并校验视频快照（顶层信封 + segments 数组 + ts）。"""
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise SystemExit(f"视频快照 {path} 顶层不是对象")
    ts = payload.get("ts")
    if not isinstance(ts, str) or not ts:
        raise SystemExit(f"视频快照 {path} 缺 ts（时间必须从输入 ts 派生，不读系统时钟）")
    rows = payload.get("segments")
    if not isinstance(rows, list) or not rows:
        raise SystemExit(f"视频快照 {path} 缺非空 segments 数组（契约第一节）")
    return payload


def observations_from_video(
    video_payload: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """视频快照 → 同化观测表；缺 q/v/confidence/data_age 的段留痕（不静默补 0）。"""
    observations: dict[str, dict[str, Any]] = {}
    invalid: list[dict[str, Any]] = []
    for row in video_payload.get("segments") or []:
        segment_id = row.get("segment_id")
        if not isinstance(segment_id, str) or not segment_id:
            invalid.append({"segment_id": segment_id, "missing": ["segment_id"]})
            continue
        missing = [
            key
            for key in ("q_vph", "v_kmh", "confidence", "data_age_s")
            if not isinstance(row.get(key), (int, float))
        ]
        if missing:
            invalid.append({"segment_id": segment_id, "missing": missing})
            continue
        observations[segment_id] = {
            "q_vph": float(row["q_vph"]),
            "v_kmh": float(row["v_kmh"]),
            "confidence": float(row["confidence"]),
            "data_age_s": int(row["data_age_s"]),
            "source": str(row.get("source") or "video"),
            "at": str(row.get("provenance", {}).get("metrics_at") or video_payload.get("ts")),
            "level": row.get("level"),
        }
    return observations, invalid


# ============================================================================
# 门控 / 偏差
# ============================================================================


def gate_passed(gate: dict[str, Any], config: dict[str, Any]) -> bool:
    """按门控参数判定这次回灌放不放行(置信度下限 + 数据时效上限)。"""
    if float(gate.get("confidence", 0.0)) < float(config.get("confidence_min", 0.0)):
        return False
    if int(gate.get("data_age_s", 10**9)) > int(config.get("data_age_max_s", 0)):
        return False
    return True


def evaluate_gate(
    gate: dict[str, Any], config: dict[str, Any]
) -> tuple[bool, str | None, str | None]:
    """门控求值：返回 `(是否通过, reason 码, 具体 cause)`。

    - 通过：`(True, None, None)`；
    - 置信度不足：`(False, "gate_rejected", "confidence_low")`；
    - 数据过期：`(False, "gate_rejected", "data_age")`；
    - 两个都不过：主因取置信度（`cause` 列出两者，便于日志一眼看全）。
    """
    causes: list[str] = []
    confidence = gate.get("confidence")
    data_age = gate.get("data_age_s")
    if isinstance(confidence, (int, float)) and float(confidence) < float(
        config.get("confidence_min", 0.0)
    ):
        causes.append(CAUSE_CONFIDENCE_LOW)
    if isinstance(data_age, (int, float)) and int(data_age) > int(
        config.get("data_age_max_s", 0)
    ):
        causes.append(CAUSE_DATA_AGE)
    if not causes:
        return True, None, None
    return False, REASON_GATE_REJECTED, "+".join(causes)


def compute_deviation(
    observed: dict[str, Any], base_segment: dict[str, Any]
) -> dict[str, Any]:
    """观测 vs 孪生基线的相对偏差（%）。

    - 基线流量/车速为 0 或缺失（空载基线）→ 相对偏差**未定义**，写 `null` 并留 `note`，
      **不许用一个编出来的分母**；
    - 否则 `q_pct = |obs-base| / base * 100`（四舍五入 2 位）。
    """
    deviation: dict[str, Any] = {"q_pct": None, "v_pct": None}
    notes: list[str] = []
    base_q = base_segment.get("q_vph") if base_segment else None
    base_v = base_segment.get("v_kmh") if base_segment else None
    if isinstance(base_q, (int, float)) and float(base_q) > 0:
        deviation["q_pct"] = round(
            abs(float(observed["q_vph"]) - float(base_q)) / float(base_q) * 100.0, 2
        )
    else:
        notes.append("基线 q_vph=0/缺失（空载基线），q 相对偏差未定义")
    if isinstance(base_v, (int, float)) and float(base_v) > 0:
        deviation["v_pct"] = round(
            abs(float(observed["v_kmh"]) - float(base_v)) / float(base_v) * 100.0, 2
        )
    else:
        notes.append("基线 v_kmh=null/缺失（空载基线），v 相对偏差未定义")
    if notes:
        deviation["note"] = "；".join(notes)
    return deviation


# ============================================================================
# 旧样例路径（loop.py --no-sumo 用；输出形状保持逐字段不变）
# ============================================================================


def build_state(sample_state: dict[str, Any], camera_ts: str) -> dict[str, Any]:
    """产出 assimilation_state.json,并强制 internal 断面不可回灌。

    --no-sumo:样例给的那份按硬规则过一遍再落盘(样例写错也会在这里被拦下)。
    真孪生:由 calibrate 每 60 s 生成。
    """
    edges = sample_state.get("edges")
    if not isinstance(edges, list) or not edges:
        raise ValueError("样例 edges 缺失或为空(契约第三节:顶层信封 + edges 数组)")
    checked: list[dict[str, Any]] = []
    applied = 0
    for edge in edges:
        role = edge.get("role")
        if role not in SECTION_ROLES:
            raise ValueError(f"未知断面角色 role={role!r}(仅 {SECTION_ROLES})")
        item = dict(edge)
        if role == "internal":
            # 硬规则:内部断面永不回灌,理由固定
            item["assimilating"] = False
            gate = dict(item.get("gate") or {})
            gate["passed"] = False
            gate["reason"] = REASON_INTERNAL
            item["gate"] = gate
        elif item.get("assimilating"):
            # 声称在回灌,但 gate 没过(置信度不足/数据过期)就不能算"已应用":
            # 状态改成未回灌并写明原因,否则状态快照把被拒的实测当成生效的。
            gate = dict(item.get("gate") or {})
            if gate.get("passed") is True:
                applied += 1
            else:
                item["assimilating"] = False
                gate["passed"] = False
                gate["reason"] = REASON_GATE_REJECTED
                item["gate"] = gate
        checked.append(item)
    return {
        "ts": camera_ts,
        "is_simulated": True,
        "period_s": PERIOD_S,
        "edges": checked,
        "applied_count": applied,
    }


def apply_to_sumo(edge: dict[str, Any], calibrator: Any) -> dict[str, Any]:
    """把一条边界断面的实测通过 traci.calibrator.setFlow 灌回 SUMO(骨架,TODO)。

    门控:gate.confidence < confidence_min 或 gate.data_age_s > data_age_max_s 时跳过。
    """
    raise NotImplementedError("回灌待 W1 实现:traci.calibrator.setFlow(仅边界断面)")


# ============================================================================
# 真路径:候选清单 + 基线 + 观测 → assimilation_state / 回灌日志
# ============================================================================


def build_calibrator_plan(
    applied: list[dict[str, Any]], period_s: int = PERIOD_S
) -> list[dict[str, Any]]:
    """把"该回灌哪些边界断面、灌什么值"整理成 `calibrator.setFlow` 计划（只落盘）。

    **不假装下发**：站点 Z 的 SUMO 路网（`stations/sumo/*.net.xml`）尚未构建、
    真孪生主循环 `run_with_sumo` 还是骨架，所以这里只产出计划供 W1 接入
    `traci.calibrator.setFlow(calibratorID, begin, end, vehsPerHour, speed, ...)`。
    """
    plan: list[dict[str, Any]] = []
    for item in applied:
        plan.append(
            {
                "calibrator_id": f"CAL-{item['segment_id']}",
                "segment_id": item["segment_id"],
                "begin_s": 0,
                "end_s": int(period_s),
                "vehs_per_hour": round(float(item["q_vph"]), 1),
                "speed_kmh": round(float(item["v_kmh"]), 1),
                "boundary_role": "boundary",
                "dispatched": False,
                "note": "待真孪生/SUMO 接入（本次未下发，不假装回灌到仿真）",
            }
        )
    return plan


def _check_scenario_edges(
    requested: list[str],
    boundary_ids: set[str],
    internal_ids: set[str],
) -> tuple[set[str], list[str]]:
    """校验场景 `assimilation.edges`：返回 `(解析到的 boundary 集合, 未落地的段号)`。

    **硬规则**（契约 §6.2）：`edges` 里写进 internal 断面 → 配置错误，**报错退出**。
    """
    internal_requested = sorted(set(requested) & internal_ids)
    if internal_requested:
        raise SystemExit(
            "配置错误：assimilation.edges 里出现了 internal 断面 "
            f"{internal_requested} —— internal 一律不允许挂 calibrator（契约 §6.2 / TC-20 第②项）"
        )
    resolved = {edge for edge in requested if edge in boundary_ids}
    unresolved = [edge for edge in requested if edge not in boundary_ids]
    return resolved, unresolved


def build_assimilation(
    sections_payload: dict[str, Any],
    baseline_payload: dict[str, Any],
    observations: dict[str, dict[str, Any]],
    scenario_assimilation: dict[str, Any],
    ts: str,
    mode: str = "network",
    scenario_id: str | None = None,
    video_snapshot: dict[str, Any] | None = None,
    invalid_observations: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """真路径：逐断面判定"回灌 / 停灌"，返回 `(state, log)` 两份可直接落盘的对象。

    **硬断言**（不是注释，是代码）：
      * 任何 `role="internal"` 的断面 `assimilating` 必须为 `False`，reason 固定 internal_not_allowed；
      * `applied` 集合必须 ⊆ boundary 候选集合（写盘前再查一遍）。
    """
    role_by_segment = {item["segment_id"]: item["role"] for item in sections_payload["sections"]}
    boundary_ids = {seg for seg, role in role_by_segment.items() if role == "boundary"}
    internal_ids = {seg for seg, role in role_by_segment.items() if role == "internal"}
    baseline_by_segment = {
        item["segment_id"]: item for item in baseline_payload.get("segments") or []
    }
    enabled = bool(scenario_assimilation.get("enabled"))
    requested = [str(edge) for edge in (scenario_assimilation.get("edges") or [])]
    period_s = int(scenario_assimilation.get("period_s") or PERIOD_S)
    raw_gate = scenario_assimilation.get("gate") or {}
    gate_config = {
        "confidence_min": float(raw_gate.get("confidence_min", DEFAULT_GATE["confidence_min"])),
        "data_age_max_s": int(raw_gate.get("data_age_max_s", DEFAULT_GATE["data_age_max_s"])),
    }
    resolved, unresolved = _check_scenario_edges(requested, boundary_ids, internal_ids)

    state_edges: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []

    for item in sections_payload["sections"]:
        segment_id = item["segment_id"]
        role = item["role"]
        observation = observations.get(segment_id)
        record: dict[str, Any] = {
            "segment_id": segment_id,
            "role": role,
            "observation": (
                {
                    "q_vph": observation["q_vph"],
                    "v_kmh": observation["v_kmh"],
                    "confidence": observation["confidence"],
                    "data_age_s": observation["data_age_s"],
                    "source": observation.get("source"),
                    "at": observation.get("at"),
                }
                if observation
                else None
            ),
            "baseline": (
                {
                    "q_vph": baseline_by_segment.get(segment_id, {}).get("q_vph"),
                    "v_kmh": baseline_by_segment.get(segment_id, {}).get("v_kmh"),
                    "baseline_kind": baseline_by_segment.get(segment_id, {}).get("baseline_kind"),
                }
                if baseline_by_segment
                else None
            ),
        }

        if role == "internal":
            # 硬规则：内部断面永不回灌（无论有没有观测、无论场景开不开）
            state_edges.append(
                {
                    "segment_id": segment_id,
                    "role": "internal",
                    "assimilating": False,
                    "gate": {"passed": False, "reason": REASON_INTERNAL},
                }
            )
            record.update(
                decision="rejected_internal",
                reason=REASON_INTERNAL,
                cause=None,
                gate=None,
                deviation=None,
            )
            records.append(record)
            continue

        # ---- boundary：先看场景开关 / 白名单，再看观测与门控 ----
        reason: str | None = None
        cause: str | None = None
        if not enabled:
            reason = REASON_DISABLED
        elif unresolved and not resolved:
            reason = REASON_CONFIG_UNRESOLVED
        elif segment_id not in resolved:
            reason = REASON_EDGE_NOT_ENABLED
        elif observation is None:
            reason = REASON_NO_OBSERVATION

        if reason is not None:
            gate_info = {
                "confidence": observation["confidence"] if observation else None,
                "data_age_s": observation["data_age_s"] if observation else None,
                "passed": False,
                "reason": reason,
            }
            if cause:
                gate_info["cause"] = cause
            state_edges.append(
                {
                    "segment_id": segment_id,
                    "role": "boundary",
                    "assimilating": False,
                    "gate": gate_info,
                }
            )
            record.update(decision="skipped", reason=reason, cause=cause, gate=gate_info, deviation=None)
            records.append(record)
            dropped.append({"segment_id": segment_id, "reason": reason, "cause": cause})
            continue

        # 观测存在：算门控与偏差
        gate_input = {
            "confidence": observation["confidence"],
            "data_age_s": observation["data_age_s"],
        }
        passed, gate_reason, gate_cause = evaluate_gate(gate_input, gate_config)
        deviation = compute_deviation(observation, baseline_by_segment.get(segment_id, {}))
        gate_info = {
            "confidence": gate_input["confidence"],
            "data_age_s": gate_input["data_age_s"],
            "passed": passed,
            "reason": gate_reason,
        }
        if gate_cause:
            gate_info["cause"] = gate_cause
        if not passed:
            state_edges.append(
                {
                    "segment_id": segment_id,
                    "role": "boundary",
                    "assimilating": False,
                    "gate": gate_info,
                }
            )
            record.update(
                decision="rejected_gate",
                reason=gate_reason,
                cause=gate_cause,
                gate=gate_info,
                deviation=deviation,
            )
            records.append(record)
            dropped.append({"segment_id": segment_id, "reason": gate_reason, "cause": gate_cause})
            continue

        # 门控通过：回灌（值先落盘，再交给 SUMO —— 本期 plan 只落盘）
        last_apply = {
            "at": observation.get("at") or ts,
            "q_vph": observation["q_vph"],
            "v_kmh": observation["v_kmh"],
        }
        state_edges.append(
            {
                "segment_id": segment_id,
                "role": "boundary",
                "assimilating": True,
                "gate": gate_info,
                "last_apply": last_apply,
                "deviation": deviation,
            }
        )
        record.update(
            decision="applied",
            reason=None,
            cause=None,
            gate=gate_info,
            deviation=deviation,
            last_apply=last_apply,
        )
        records.append(record)
        applied.append({"segment_id": segment_id, **last_apply})

    # ---- 硬断言（写盘前再查一遍；任何 internal 回灌都是 bug） ----
    applied_ids = {item["segment_id"] for item in applied}
    illegal = sorted(applied_ids - boundary_ids)
    if illegal:
        raise RuntimeError(f"同化硬规则被破坏：internal/未知断面被回灌 {illegal}")
    internal_state = [edge for edge in state_edges if edge["role"] == "internal"]
    for edge in internal_state:
        if edge["assimilating"] is not False or edge["gate"].get("reason") != REASON_INTERNAL:
            raise RuntimeError(f"internal 断面状态非法：{edge}")

    counts = {
        "boundary": len(boundary_ids),
        "internal": len(internal_ids),
        "applied": len(applied),
    }
    state: dict[str, Any] = {
        "ts": ts,
        "is_simulated": True,
        "enabled": enabled,
        "period_s": period_s,
        "mode": mode,
        "gate": gate_config,
        "edges": state_edges,
        "applied_count": len(applied),
        "counts": counts,
        "note": (
            "数据同化状态（演示数据（模拟））：只有 role=boundary 的断面允许回灌；"
            "internal 固定 assimilating=false / reason=internal_not_allowed（硬规则）。"
            "回灌值来自视频链路快照（样本视频回放，非本站现场），同化后的孪生数仍是演示数据，"
            "**不得说成实测**。"
        ),
    }
    if scenario_id:
        state["scenario_id"] = scenario_id
    log: dict[str, Any] = {
        "ts": ts,
        "is_simulated": True,
        "mode": mode,
        "scenario_id": scenario_id,
        "enabled": enabled,
        "period_s": period_s,
        "gate": gate_config,
        "scenario_edges": {
            "requested": requested,
            "resolved_boundary": sorted(resolved),
            "unresolved": unresolved,
        },
        "video_snapshot": video_snapshot or {"present": False},
        "invalid_observations": invalid_observations or [],
        "records": records,
        "applied": applied,
        "dropped": dropped,
        "calibrator_plan": build_calibrator_plan(applied, period_s),
        "note": (
            "回灌/停灌日志（演示数据（模拟））：每次停灌都留 reason（TC-20 第④项）。"
            "calibrator_plan 只是 setFlow 计划，**本次未接入 SUMO、未实际下发**；"
            "站点 Z 的 stations/sumo/*.net.xml 与真孪生主循环未就绪（见 README 第十六节）。"
        ),
    }
    return state, log
