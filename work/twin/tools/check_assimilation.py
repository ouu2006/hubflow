#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同化自检（Issue IKMS19 · TC-20 四项 + 本单专属一/二）：**真跑**，输出 PASS / FAIL / BLOCKED。

跑什么（全部调 `work/twin/run_assimilation.py` 的 `run()`，不是空口断言）：

| 项 | 判据 | 数据 |
|---|---|---|
| **TC-20①** | 被同化的边界断面确实回灌（有 `last_apply` + 偏差） | **机制示例**（旧 `SEG-###` 样例）可验 → PASS；**真网**当前无 boundary 观测 → BLOCKED（如实标，不编数） |
| **TC-20②** | `internal` 断面**永远** `assimilating=false` 且 reason=`internal_not_allowed`（硬断言） | 真网 + 机制示例两套产物都查；另查日志里 internal 观测被拒 |
| **TC-20③** | 关闭同化（场景 S3 `enabled=false`）→ 回灌 0 条、boundary 全部停灌、reason 可见 | 两个模式各跑一遍 S3 |
| **TC-20④** | 压 `confidence` / 抬 `data_age` → 门控拒绝，`gate.reason=gate_rejected` + `cause` 可见，日志留痕 | 机制示例跑 `--obs-confidence 0.2` / `--obs-data-age-s 999` |
| **本单专属一** | 只灌 boundary：回灌集合 ⊆ boundary 清单；状态/清单角色与条数一致；把 internal 段号写进 `assimilation.edges` → **配置错误、报错退出** | 两套产物 + 直接调 `build_assimilation` 验报错 |
| **本单专属二** | 同输入两遍，所有产物**逐字节一致** | 两个模式各跑两遍比对 sha256 |

退出码：0 = 无 FAIL（有 BLOCKED 也返回 0，但会打印「M1-10 不得宣称通过」）；1 = 有 FAIL。
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

import calibrate  # noqa: E402
import run_assimilation as ra  # noqa: E402

#: 自检输出根目录（out/ 已 gitignore，不进仓库）
CHECK_ROOT = TWIN_DIR / "out" / "_selfcheck" / "assimilation"

#: 真网模式/机制示例产物清单
ARTIFACTS = ra.NETWORK_ARTIFACTS


class Item:
    """一条自检结果。"""

    def __init__(self, key: str, title: str, status: str, detail: str) -> None:
        self.key = key
        self.title = title
        self.status = status
        self.detail = detail

    def __str__(self) -> str:
        return f"  {self.status:<7} {self.title}：{self.detail}"


def sha256(path: Path) -> str:
    """文件 sha256（两遍一致比对用）。"""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def fresh_dir(name: str) -> Path:
    """清空并重建一个自检输出目录（每次自检从零开始，避免旧产物蒙混）。"""
    path = CHECK_ROOT / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_artifacts(out_dir: Path) -> dict[str, Any]:
    """读一套产物（缺文件直接抛错——自检不能"跳过"。）"""
    payload: dict[str, Any] = {}
    for name in ARTIFACTS:
        path = out_dir / name
        if not path.is_file():
            raise SystemExit(f"自检失败：产物缺失 {path}")
        payload[name] = json.loads(path.read_text(encoding="utf-8"))
    return payload


def run_case(name: str, argv: list[str]) -> Path:
    """跑一次 run_assimilation（进程内），返回输出目录。"""
    out_dir = fresh_dir(name)
    ra.run(argv + ["--out", str(out_dir)])
    load_artifacts(out_dir)  # 产物存在性/可解析断言
    return out_dir


def _roles(sections_payload: dict[str, Any]) -> dict[str, str]:
    return {item["segment_id"]: item["role"] for item in sections_payload["sections"]}


def _internal_ok(
    state: dict[str, Any], log: dict[str, Any], sections_payload: dict[str, Any]
) -> tuple[bool, str]:
    """internal 硬规则：状态 + 日志两处都不许出现 internal 回灌。"""
    problems: list[str] = []
    roles = _roles(sections_payload)
    internal_ids = {seg for seg, role in roles.items() if role == "internal"}
    internal_edges = [edge for edge in state["edges"] if edge.get("role") == "internal"]
    if not internal_edges:
        problems.append("状态里没有 internal 断面（清单缺失？）")
    if {edge.get("segment_id") for edge in internal_edges} != internal_ids:
        problems.append("状态里的 internal 段集合 ≠ 候选清单的 internal 段集合")
    for edge in internal_edges:
        if edge.get("assimilating") is not False:
            problems.append(f"{edge.get('segment_id')} internal 被标 assimilating=true")
        if (edge.get("gate") or {}).get("reason") != calibrate.REASON_INTERNAL:
            problems.append(
                f"{edge.get('segment_id')} internal reason="
                f"{(edge.get('gate') or {}).get('reason')!r}（应为 {calibrate.REASON_INTERNAL}）"
            )
    for record in log.get("records") or []:
        if record.get("role") == "internal" and record.get("decision") != "rejected_internal":
            problems.append(f"{record.get('segment_id')} internal 日志决定={record.get('decision')!r}")
    for item in log.get("applied") or []:
        segment_id = item.get("segment_id")
        if segment_id in internal_ids:
            problems.append(f"{segment_id} internal 出现在 applied 里")
    return (not problems), "；".join(problems) if problems else f"{len(internal_edges)} 条 internal 全部拒绝"


def _applied_subset_boundary(
    state: dict[str, Any], sections_payload: dict[str, Any], log: dict[str, Any]
) -> tuple[bool, str]:
    """回灌集合 ⊆ boundary 清单；状态/清单的角色与条数一致。"""
    roles = _roles(sections_payload)
    boundary_ids = {seg for seg, role in roles.items() if role == "boundary"}
    internal_ids = {seg for seg, role in roles.items() if role == "internal"}
    problems: list[str] = []
    applied = [item.get("segment_id") for item in log.get("applied") or []]
    illegal = sorted(set(applied) - boundary_ids)
    if illegal:
        problems.append(f"回灌段不在 boundary 清单：{illegal}")
    if set(applied) & internal_ids:
        problems.append(f"回灌段包含 internal：{sorted(set(applied) & internal_ids)}")
    state_ids = [edge.get("segment_id") for edge in state["edges"]]
    if len(state_ids) != len(sections_payload["sections"]):
        problems.append(
            f"状态/{len(state_ids)} 条 ≠ 候选清单 {len(sections_payload['sections'])} 条"
        )
    if len(set(state_ids)) != len(state_ids):
        problems.append("状态里段号有重复")
    missing = sorted(set(roles) - set(state_ids))
    if missing:
        problems.append(f"候选清单里这些段在状态中缺失：{missing}")
    role_mismatch = [
        edge.get("segment_id")
        for edge in state["edges"]
        if roles.get(edge.get("segment_id")) != edge.get("role")
    ]
    if role_mismatch:
        problems.append(f"状态 role 与候选清单不一致：{role_mismatch}")
    state_boundary = sum(1 for edge in state["edges"] if edge.get("role") == "boundary")
    if state_boundary != len(boundary_ids):
        problems.append(f"boundary 条数 {state_boundary} ≠ 清单 {len(boundary_ids)}")
    applied_flag = sum(1 for edge in state["edges"] if edge.get("assimilating") is True)
    if applied_flag != len(applied):
        problems.append(f"assimilating=true 条数 {applied_flag} ≠ 日志 applied {len(applied)}")
    return (not problems), "；".join(problems) if problems else (
        f"applied {len(applied)} ⊆ boundary {len(boundary_ids)}；状态 {len(state_ids)} 段与清单一致"
    )


def _assert_config_error_raised(out_dir: Path) -> tuple[bool, str]:
    """把 internal 段号写进 assimilation.edges → 必须报错退出（契约 §6.2 硬规则）。"""
    artifacts = load_artifacts(out_dir)
    sections_payload = artifacts["sections_candidate.json"]
    baseline_payload = artifacts["segments_before.json"]
    roles = _roles(sections_payload)
    internal_ids = [seg for seg, role in roles.items() if role == "internal"]
    if not internal_ids:
        return False, "没有 internal 段可用于配置错误测试（清单异常）"
    scenario_assim = {
        "enabled": True,
        "edges": [internal_ids[0]],
        "period_s": 60,
        "gate": {"confidence_min": 0.6, "data_age_max_s": 120},
    }
    try:
        calibrate.build_assimilation(
            sections_payload,
            baseline_payload,
            {},
            scenario_assim,
            ts=str(artifacts["assimilation_state.json"]["ts"]),
        )
    except SystemExit as exc:
        text = str(exc)
        if "internal" in text:
            return True, f"internal 段号 {internal_ids[0]} 写进 edges → 报错退出（{text[:80]}…）"
        return False, f"报错信息没提 internal：{text[:120]}"
    except Exception as exc:  # noqa: BLE001 —— 任何异常都算"没按配置错误退出"
        return False, f"抛了非 SystemExit 异常：{type(exc).__name__}: {exc}"
    return False, "没有报错退出（配置错误被静默接受）"


def determinism_case(name: str, argv: list[str]) -> tuple[bool, str, dict[str, str]]:
    """同输入跑两遍（两个目录）→ 逐文件 sha256 比对。"""
    dir_a = run_case(name + "_a", argv)
    dir_b = run_case(name + "_b", argv)
    hashes: dict[str, str] = {}
    problems: list[str] = []
    for artifact in ARTIFACTS:
        hash_a = sha256(dir_a / artifact)
        hash_b = sha256(dir_b / artifact)
        hashes[artifact] = hash_a
        if hash_a != hash_b:
            problems.append(f"{artifact} 两遍不一致")
    detail = "；".join(problems) if problems else f"{len(ARTIFACTS)} 个产物 sha256 全一致"
    return (not problems), detail, hashes


def gate_case() -> tuple[bool, str]:
    """TC-20④：分别压 confidence / 抬 data_age，查拒绝原因与日志。"""
    problems: list[str] = []
    details: list[str] = []
    for label, argv, cause in (
        ("压 confidence=0.2", ["--mode", "sample", "--obs-confidence", "0.2"], "confidence_low"),
        ("抬 data_age=999", ["--mode", "sample", "--obs-data-age-s", "999"], "data_age"),
    ):
        out_dir = run_case("gate_" + cause, argv)
        state = json.loads((out_dir / "assimilation_state.json").read_text(encoding="utf-8"))
        log = json.loads((out_dir / "assimilation_log.json").read_text(encoding="utf-8"))
        boundary = [edge for edge in state["edges"] if edge["role"] == "boundary"]
        rejected = [
            edge
            for edge in boundary
            if edge.get("assimilating") is False
            and (edge.get("gate") or {}).get("reason") == calibrate.REASON_GATE_REJECTED
            and (edge.get("gate") or {}).get("cause") == cause
        ]
        if not rejected:
            problems.append(f"{label}：没有 boundary 断面被判 gate_rejected/{cause}")
        else:
            details.append(f"{label} → {rejected[0]['segment_id']} gate_rejected/{cause}")
        dropped = [
            item for item in log.get("dropped") or [] if item.get("reason") == calibrate.REASON_GATE_REJECTED
        ]
        if not dropped:
            problems.append(f"{label}：日志 dropped 里没有 gate_rejected（日志不可见）")
        if log.get("applied"):
            problems.append(f"{label}：被拒后仍有 applied={log['applied']}")
    return (not problems), "；".join(problems) if problems else "；".join(details)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    items: list[Item] = []

    # ---- 真网模式：断面候选 + 同化状态（默认场景 S4） ----
    network_out = run_case("network_s4", ["--mode", "network"])
    network = load_artifacts(network_out)
    sections_payload = network["sections_candidate.json"]
    state = network["assimilation_state.json"]
    log = network["assimilation_log.json"]
    counts = sections_payload["counts"]

    # 断面候选清单本身的自洽性（自动推导，不是写死）
    basis_ok = all(
        item.get("role") in ("boundary", "internal") and item.get("basis")
        for item in sections_payload["sections"]
    )
    status_ok = "候选" in str(sections_payload.get("status", ""))
    boundary_derived = all(
        (item["from_boundary"] or item["to_boundary"]) if item["role"] == "boundary" else True
        for item in sections_payload["sections"]
    )
    items.append(
        Item(
            "SECTIONS",
            "断面候选清单（自动推导 + 候选状态）",
            "PASS"
            if (
                basis_ok
                and status_ok
                and boundary_derived
                and counts["total"] == int(sections_payload["seg_target"])
            )
            else "FAIL",
            (
                f"{counts['total']} 段（boundary {counts['boundary']} / internal {counts['internal']}）"
                f"· 状态={sections_payload.get('status')} · 每段 role+依据={basis_ok} · "
                f"boundary 都由边界节点推出={boundary_derived}"
            ),
        )
    )

    # ---- TC-20② internal 永不回灌（真网 + 机制示例两套都查） ----
    network_internal_ok, network_internal_detail = _internal_ok(state, log, sections_payload)
    sample_out = run_case("sample_s4", ["--mode", "sample"])
    sample = load_artifacts(sample_out)
    sample_internal_ok, sample_internal_detail = _internal_ok(
        sample["assimilation_state.json"],
        sample["assimilation_log.json"],
        sample["sections_candidate.json"],
    )
    observed_internal = [
        record["segment_id"]
        for record in log.get("records") or []
        if record.get("role") == "internal" and record.get("observation")
    ]
    items.append(
        Item(
            "TC20-2",
            "TC-20② internal 永不回灌（硬断言）",
            "PASS" if (network_internal_ok and sample_internal_ok) else "FAIL",
            f"真网：{network_internal_detail}；机制示例：{sample_internal_detail}；"
            f"真网被拒的 internal 观测={observed_internal}",
        )
    )

    # ---- TC-20③ 关闭同化 → 无回灌 / 回默认需求 ----
    s3_network = load_artifacts(run_case("network_s3", ["--mode", "network", "--scenario", "S3"]))[
        "assimilation_state.json"
    ]
    s3_sample = load_artifacts(run_case("sample_s3", ["--mode", "sample", "--scenario", "S3"]))[
        "assimilation_state.json"
    ]
    s3_problems: list[str] = []
    for label, payload in (("真网", s3_network), ("机制示例", s3_sample)):
        if payload.get("enabled") is not False:
            s3_problems.append(f"{label} 场景 S3 的 enabled 不是 false")
        if payload.get("applied_count") != 0:
            s3_problems.append(f"{label} 关闭后仍回灌 {payload.get('applied_count')} 条")
        for edge in payload["edges"]:
            if edge.get("assimilating") is True:
                s3_problems.append(f"{label} {edge.get('segment_id')} 关闭后仍 assimilating=true")
            if "last_apply" in edge:
                s3_problems.append(f"{label} {edge.get('segment_id')} 关闭后仍有 last_apply")
            reason = (edge.get("gate") or {}).get("reason")
            if edge.get("role") == "boundary" and reason not in (
                calibrate.REASON_DISABLED,
                calibrate.REASON_CONFIG_UNRESOLVED,
            ):
                s3_problems.append(f"{label} {edge.get('segment_id')} boundary 停灌原因={reason!r} 不可见")
    s4_applied = sample["assimilation_state.json"].get("applied_count")
    if s4_applied != 1:
        s3_problems.append(f"机制示例 S4 开同化应回灌 1 条，实际 {s4_applied}")
    items.append(
        Item(
            "TC20-3",
            "TC-20③ 关闭同化 → 回灌 0 条 / 退回默认需求",
            "PASS" if not s3_problems else "FAIL",
            (
                f"S3 enabled=false：真网 applied {s3_network.get('applied_count')}、"
                f"机制示例 applied {s3_sample.get('applied_count')}（S4 开同化={s4_applied} 条，对照成立）"
                if not s3_problems
                else "；".join(s3_problems)
            ),
        )
    )

    # ---- TC-20④ 门控拒绝可见 ----
    gate_ok, gate_detail = gate_case()
    items.append(
        Item("TC20-4", "TC-20④ 门控（压 confidence / 抬 data_age）拒绝且日志可见", "PASS" if gate_ok else "FAIL", gate_detail)
    )

    # ---- TC-20① 机制示例：boundary 有回灌 ----
    sample_state = sample["assimilation_state.json"]
    sample_roles = _roles(sample["sections_candidate.json"])
    boundary_ids = [seg for seg, role in sample_roles.items() if role == "boundary"]
    applied_edges = [
        edge for edge in sample_state["edges"] if edge.get("assimilating") is True
    ]
    mech_ok = (
        sample_state.get("applied_count") == 1
        and len(applied_edges) == 1
        and applied_edges[0]["segment_id"] in boundary_ids
        and isinstance(applied_edges[0].get("last_apply"), dict)
        and isinstance(applied_edges[0].get("deviation"), dict)
    )
    items.append(
        Item(
            "TC20-1-mech",
            "TC-20①（机制示例，SEG-###）boundary 有回灌 + 偏差",
            "PASS" if mech_ok else "FAIL",
            (
                f"{applied_edges[0]['segment_id'] if applied_edges else '—'} 回灌 "
                f"q={applied_edges[0].get('last_apply', {}).get('q_vph') if applied_edges else '—'}"
                f" v={applied_edges[0].get('last_apply', {}).get('v_kmh') if applied_edges else '—'}"
                f" deviation={applied_edges[0].get('deviation') if applied_edges else '—'}"
                "（偏差 0% 因样例基线==样例声明观测；**不是**真网偏差结论）"
            ),
        )
    )

    # ---- TC-20① 真网：无 boundary 观测 → 如实 BLOCKED ----
    network_boundary = [edge for edge in state["edges"] if edge.get("role") == "boundary"]
    network_applied = state.get("applied_count")
    blocker_codes = [blocker.get("code") for blocker in network["run_log.json"].get("blockers") or []]
    blocked_ok = network_applied == 0 and "no_boundary_observation" in blocker_codes
    items.append(
        Item(
            "TC20-1-net",
            "TC-20①（真网，SZ-###）M1-10 boundary 回灌",
            "BLOCKED" if blocked_ok else "FAIL",
            (
                f"boundary 候选 {len(network_boundary)} 条、真网回灌 {network_applied} 条；"
                "阻塞原因：视频快照两段（SZ-005/SZ-024）拓扑均为 internal（硬规则禁止回灌）+ "
                "无 boundary 观测 + 真孪生基线缺失 + 清单未签字（见 run_log.blockers）"
            ),
        )
    )

    # ---- 本单专属一：只灌 boundary + 清单一致性 + 配置错误报错 ----
    net_sub_ok, net_sub_detail = _applied_subset_boundary(state, sections_payload, log)
    smp_sub_ok, smp_sub_detail = _applied_subset_boundary(
        sample["assimilation_state.json"], sample["sections_candidate.json"], sample["assimilation_log.json"]
    )
    config_err_ok, config_err_detail = _assert_config_error_raised(network_out)
    items.append(
        Item(
            "ONLY-BOUNDARY",
            "本单专属一 只灌 boundary + 清单一致 + internal 配置报错",
            "PASS" if (net_sub_ok and smp_sub_ok and config_err_ok) else "FAIL",
            f"真网：{net_sub_detail}；机制示例：{smp_sub_detail}；配置错误：{config_err_detail}",
        )
    )

    # ---- 本单专属二：同输入两遍逐字节一致 ----
    net_det_ok, net_det_detail, net_hashes = determinism_case("network_det", ["--mode", "network"])
    smp_det_ok, smp_det_detail, smp_hashes = determinism_case("sample_det", ["--mode", "sample"])
    items.append(
        Item(
            "DETERMINISM",
            "本单专属二 同输入两遍逐字节一致",
            "PASS" if (net_det_ok and smp_det_ok) else "FAIL",
            f"真网：{net_det_detail}；机制示例：{smp_det_detail}；"
            f"assimilation_state 两遍 sha={net_hashes['assimilation_state.json'][:16]}…",
        )
    )

    # ---- 汇总 ----
    fails = [item for item in items if item.status == "FAIL"]
    blocked = [item for item in items if item.status == "BLOCKED"]
    print("同化自检（IKMS19 · TC-20 四项 + 本单专属一/二）")
    print(f"  自检产物目录：{CHECK_ROOT}")
    for item in items:
        print(str(item))
    print()
    print(
        f"结论：{len(items) - len(fails) - len(blocked)} 项 PASS"
        f" · {len(blocked)} 项 BLOCKED · {len(fails)} 项 FAIL"
    )
    if blocked:
        print("  ⚠️ 真网 M1-10 / TC-20① 记 BLOCKED：**不得宣称 M1-10 通过**（缺 boundary 观测 + 真孪生基线 + 签字冻结）")
    print("  M1-10 阻塞清单见 work/twin/out/latest/run_log.json 的 blockers 与 README 第十六节。")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
