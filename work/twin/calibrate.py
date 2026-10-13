"""数据同化:把视频链路的边界断面实测回灌给孪生(每 60 s、带门控)。

输入:视频链路实测(边界断面)+ stations/scenarios.json 的 assimilation 开关
输出:assimilation_state.json(契约第三节:带 ts 与 is_simulated 的信封 + edges 数组)
口径:**只有 role="boundary" 的断面允许回灌**;role="internal" 的断面**永远**
     assimilating=false、reason 固定 internal_not_allowed —— 这是硬规则,
     否则孪生变成"录像回放"、推荐再也改变不了路况(TC-20 / M1-10)。

用法:由 loop.py 调用,不单独执行。
"""

from __future__ import annotations

from typing import Any

#: 断面角色(契约 6.1,取值封闭)
SECTION_ROLES = ("boundary", "internal")

#: 内部断面被拒的固定原因码(契约第三节硬规则)
REASON_INTERNAL = "internal_not_allowed"

#: 回灌周期(README 第六节:每 60 s 一次)
PERIOD_S = 60


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
            applied += 1
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


def gate_passed(gate: dict[str, Any], config: dict[str, Any]) -> bool:
    """按门控参数判定这次回灌放不放行(置信度下限 + 数据时效上限)。"""
    if float(gate.get("confidence", 0.0)) < float(config.get("confidence_min", 0.0)):
        return False
    if int(gate.get("data_age_s", 10**9)) > int(config.get("data_age_max_s", 0)):
        return False
    return True
