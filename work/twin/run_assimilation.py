#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同化 + 多因素一键入口（Issue IKMS19）。

一条命令产出（默认**真网模式**，写 `work/twin/out/latest/`）：

| 产物 | 内容 | 谁消费 |
|---|---|---|
| `sections_candidate.json` | 61 段 `boundary` / `internal` **候选**（自动推导，每段 role+依据，状态=候选·待签字冻结） | 业主/队长签字、IKMHMX 冻结、接口层透出 |
| `assimilation_state.json` | 契约 §三信封 + `edges`（只灌 boundary；internal 固定 `internal_not_allowed`） | 接口层 `GET /api/traffic/assimilation`（`work/assembly/traffic.py` 读 `work/twin/out/assimilation_state.json`） |
| `assimilation_log.json` | 回灌/停灌日志（逐段 gate 求值、偏差、calibrator 计划） | 验收（TC-20 第④项「日志可见」）、W1 真孪生接入 |
| `factors_report.json` | 因素登记表 + S1~S4 场景注入 + 未落地原因 + 逐因素方向校验 | 验收（TC-16）、决策页「为什么堵」 |
| `segments_before.json` / `segments_after.json` | 因素注入前后的孪生段快照（before = 基线，after = 注入后） | 决策/前端对照、TC-16 |
| `run_log.json` | 本次运行摘要（计数 / 产物字节数 / 阻塞项） | 自检、交接 |

**两条模式，段号命名空间严格分开**：

* `--mode network`（默认）：本站真网 `SZ-###`（61 段，`work/twin/netpack/network_junction.json`）。
  真孪生基线缺失 → 用**空载网络基线**（明确标注"空载基线/演示，不是仿真实测"）；
  视频快照只覆盖 `SZ-005`/`SZ-024`（拓扑均为 internal）→ 硬规则禁止回灌，真实回灌数 0；
* `--mode sample`：旧 7 节点样例网 `SEG-###`（`work/twin/samples/`）——**机制示例**，
  用来把「boundary 回灌 / internal 拒绝 / 门控拒绝 / 关闭同化 / 两遍一致」整条机制跑通并自检。
  **不得**把样例结果当本站结论，也不得和 `SZ-###` 混写进同一份产物。

**确定性**：不读系统时钟；`ts` 一律从输入（视频快照 ts / 样例 ts / 场景因素 `from`）派生；
同一输入两遍，所有产物逐字节一致（`本单专属二`）。

用法：
    python work/twin/run_assimilation.py                      # 真网模式，默认场景 S4（多因素）
    python work/twin/run_assimilation.py --scenario S3        # 关同化的场景（TC-20 第③项）
    python work/twin/run_assimilation.py --mode sample        # 机制示例（SEG-###）
    python work/twin/run_assimilation.py --video <快照路径>   # 显式指定视频快照
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import baseline
import calibrate
import factors
import scenario
import sections

#: 本文件位于 work/twin/ → 仓库根是 parents[1]
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]

#: 默认输出目录（gitignore：out/）
DEFAULT_OUT = HERE / "out" / "latest"
#: 机制示例（SEG-###）的默认输出目录——与真网产物分目录，不混命名空间
DEFAULT_SAMPLE_OUT = DEFAULT_OUT / "mechanism_demo"
#: 样例输入目录（机制示例用；**只读**，绝不改写）
SAMPLES_DIR = HERE / "samples"

#: 视频快照缺失时用的**固定演示时刻**（不读系统时钟；与 work/engine/realnet.py 同口径）
DEMO_BASE_TS = "2026-10-18T08:00:00+08:00"

#: 真网模式产物清单（自检按它断言产物在场）
NETWORK_ARTIFACTS = (
    "sections_candidate.json",
    "assimilation_state.json",
    "assimilation_log.json",
    "factors_report.json",
    "segments_before.json",
    "segments_after.json",
    "run_log.json",
)

#: 机制示例产物清单
SAMPLE_ARTIFACTS = NETWORK_ARTIFACTS


def read_json(path: Path) -> dict[str, Any]:
    """读一个 UTF-8 JSON 文件（显式编码，换机器不乱码）。"""
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def write_json(path: Path, payload: dict[str, Any]) -> int:
    """写一个 UTF-8 JSON 文件（中文不转义），返回字节数。"""
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def ensure_out_dir(path: Path) -> None:
    """先建输出目录，建完断言（不许"报成功、产物没生成"）。"""
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise RuntimeError(f"输出目录未能建立：{path}")


def assert_artifact(path: Path) -> int:
    """产物存在性断言（存在 + 非空 + 能解析 + 顶层是对象）。"""
    if not path.is_file():
        raise RuntimeError(f"产物不存在：{path}")
    size = path.stat().st_size
    if size <= 0:
        raise RuntimeError(f"产物为空：{path}")
    payload = read_json(path)
    if not isinstance(payload, dict) or not payload:
        raise RuntimeError(f"产物顶层为空或不是对象：{path}")
    return size


def repo_rel(path: Path) -> str:
    """尽量给仓库相对路径；不在仓库内给绝对路径（只读引用主工作区时用）。"""
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


#: 停灌原因码 → 人读文案（归因用；不参与契约字段）
REASON_LABELS = {
    calibrate.REASON_INTERNAL: "internal 永不回灌（硬规则）",
    calibrate.REASON_GATE_REJECTED: "门控拒绝",
    calibrate.REASON_DISABLED: "场景关闭同化（退回默认需求）",
    calibrate.REASON_CONFIG_UNRESOLVED: "场景 edges 未落地",
    calibrate.REASON_EDGE_NOT_ENABLED: "不在场景 edges 白名单",
    calibrate.REASON_NO_OBSERVATION: "无观测",
}


def build_assimilation_detail(state: dict[str, Any], log: dict[str, Any]) -> dict[str, Any]:
    """从同化状态/日志派生**真实归因**（供摘要 / run_log / 自检用；不写盘、不猜）。

    区分三件事，避免"回灌 0 条"时一律归因成 internal：
      * 场景开关（`enabled=false` → 退回默认需求）；
      * boundary 断面各自的停灌原因分布（无观测 / 门控拒绝 / edges 未落地 / 不在白名单）；
      * internal 观测被拒条数（硬规则，单独列）。
    """
    stopped_by_reason: dict[str, int] = {}
    for edge in state.get("edges") or []:
        if edge.get("assimilating") is True or edge.get("role") == "internal":
            continue
        reason = str((edge.get("gate") or {}).get("reason") or "unknown")
        stopped_by_reason[reason] = stopped_by_reason.get(reason, 0) + 1
    records = log.get("records") or []
    return {
        "enabled": state.get("enabled"),
        "applied_count": int(state.get("applied_count") or 0),
        "applied_ids": [
            edge["segment_id"] for edge in state.get("edges") or [] if edge.get("assimilating") is True
        ],
        "boundary_stopped_by_reason": dict(sorted(stopped_by_reason.items())),
        "internal_sections": sum(
            1 for edge in state.get("edges") or [] if edge.get("role") == "internal"
        ),
        "internal_observations_rejected": sorted(
            record["segment_id"]
            for record in records
            if record.get("role") == "internal" and record.get("observation")
        ),
        "boundary_observations": sorted(
            record["segment_id"]
            for record in records
            if record.get("role") == "boundary" and record.get("observation")
        ),
        "scenario_edges": dict(log.get("scenario_edges") or {}),
    }


def attribution_text(detail: dict[str, Any]) -> str:
    """把归因 dict 拼成一句人读文案（真网 / 机制示例共用）。"""
    parts: list[str] = []
    if detail.get("enabled") is False:
        parts.append("场景关闭同化（enabled=false → 退回默认需求）")
    applied = int(detail.get("applied_count") or 0)
    if applied:
        parts.append(f"已回灌 {applied} 条（{'、'.join(detail.get('applied_ids') or [])}）")
    stopped = dict(detail.get("boundary_stopped_by_reason") or {})
    if detail.get("enabled") is False:
        # 场景关闭时所有 boundary 都是同一个原因，已在上一句说明，不重复列分布
        stopped.pop(calibrate.REASON_DISABLED, None)
    if stopped:
        text = "；".join(
            f"{REASON_LABELS.get(reason, reason)} {count} 条" for reason, count in stopped.items()
        )
        parts.append(("boundary 停灌原因分布：" if not applied else "其余 boundary 停灌：") + text)
    internal_rejected = detail.get("internal_observations_rejected") or []
    if internal_rejected:
        parts.append(
            f"internal 观测被拒 {len(internal_rejected)} 条"
            f"（{'、'.join(internal_rejected)}；internal_not_allowed 硬规则）"
        )
    if not parts:
        parts.append("无 boundary 候选可灌（如实）")
    return "；".join(parts)


# ============================================================================
# 观测覆盖（自检用：压 confidence / 抬 data_age，TC-20 第④项）
# ============================================================================


def apply_observation_overrides(
    observations: dict[str, dict[str, Any]],
    confidence: float | None,
    data_age_s: int | None,
) -> dict[str, dict[str, Any]]:
    """把测试注入的门控值覆盖到观测上（**只写进本次运行内存，不改任何输入文件**）。"""
    if confidence is None and data_age_s is None:
        return observations
    overridden: dict[str, dict[str, Any]] = {}
    for segment_id, observation in observations.items():
        item = dict(observation)
        if confidence is not None:
            item["confidence"] = float(confidence)
        if data_age_s is not None:
            item["data_age_s"] = int(data_age_s)
        overridden[segment_id] = item
    return overridden


# ============================================================================
# 真网模式（SZ-###）
# ============================================================================


def _network_blockers(
    sections_payload: dict[str, Any],
    observations: dict[str, dict[str, Any]],
    state: dict[str, Any],
    video_source: str,
    scenario_edges: dict[str, Any],
    detail: dict[str, Any],
) -> list[dict[str, str]]:
    """把真网模式当前的**真实阻塞**列出来（不编造通过；归因按实际状态，不写死）。"""
    blockers: list[dict[str, str]] = []
    blockers.append(
        {
            "code": "sections_not_frozen",
            "detail": (
                "boundary/internal 清单是自动推导的【候选】"
                f"（{sections_payload['counts']['boundary']} boundary / "
                f"{sections_payload['counts']['internal']} internal），"
                "**未经业主/队长签字冻结**；签字前不得宣称 M1-10 通过（Issue IKMS19 第五节第 1 条）"
            ),
        }
    )
    roles = {item["segment_id"]: item["role"] for item in sections_payload["sections"]}
    observed_internal = sorted(
        segment_id for segment_id in observations if roles.get(segment_id) == "internal"
    )
    observed_boundary = sorted(
        segment_id for segment_id in observations if roles.get(segment_id) == "boundary"
    )
    applied_count = int(detail.get("applied_count") or 0)
    # 「观测都在 internal、因此回灌 0 条」只在**确实没有 boundary 可用观测**时才成立；
    # 混合快照（boundary 已回灌 > 0）时不能再说"故回灌 0 条"（否则与状态自相矛盾）。
    if observed_internal and applied_count == 0 and not observed_boundary:
        blockers.append(
            {
                "code": "observations_are_internal",
                "detail": (
                    f"视频/断面观测段 {observed_internal} 在真网拓扑里都是 internal（端点不是 boundary 节点）"
                    "→ 硬规则禁止回灌；再加上 boundary 候选段没有任何观测，故本次回灌 0 条。"
                    "这不是 bug，是 'internal 永不回灌' 在起作用"
                ),
            }
        )
    if observed_boundary:
        # 有 boundary 观测：按实际回灌/门控结果如实写（不再报"无 boundary 观测"）
        rejected = [
            segment_id
            for segment_id in observed_boundary
            if segment_id not in (detail.get("applied_ids") or [])
        ]
        if rejected:
            blockers.append(
                {
                    "code": "boundary_observation_rejected",
                    "detail": (
                        f"boundary 观测段 {observed_boundary}，其中 {rejected} 未回灌"
                        "（原因见 assimilation_state 的 gate / assimilation_log 的 dropped；"
                        "例如门控拒绝 / edges 未落地），已回灌 "
                        f"{applied_count} 条"
                    ),
                }
            )
    else:
        blockers.append(
            {
                "code": "no_boundary_observation",
                "detail": (
                    f"boundary 候选段没有任何视频/断面观测（观测段 {sorted(observations) or '无'}，"
                    f"其中 internal {observed_internal or '无'}）"
                    "→ TC-20 第①项的「边界流量/车速偏差」无法核；需上游给 boundary 段的实测或断面计数"
                ),
            }
        )
    blockers.append(
        {
            "code": "no_twin_baseline",
            "detail": (
                "真孪生基线缺失：`stations/sumo/*.net.xml` 未构建、`loop.run_with_sumo` 仍是骨架"
                "→ 本单只能用空载网络基线（演示，不是仿真实测）；真孪生跑起来后必须换真基线"
            ),
        }
    )
    blockers.append(
        {
            "code": "calibrator_not_dispatched",
            "detail": (
                f"本次回灌 {state['applied_count']} 条；即使有可灌的值，也只落 `calibrator_plan`，"
                "**没有实际下发 SUMO**（无真 SUMO 路网/主循环，不假装回灌到仿真）"
            ),
        }
    )
    if scenario_edges.get("unresolved"):
        blockers.append(
            {
                "code": "scenario_edges_unresolved",
                "detail": (
                    f"站点包 scenarios.json 的 assimilation.edges={scenario_edges['requested']} "
                    f"在真网段号里解析不到（未落地：{scenario_edges['unresolved']}，属 7 节点样例网占位件）"
                    "→ 无人为它开白名单；需人工把 edges 换成 boundary 候选的 SZ 段号（stations/ 不归本单改）"
                ),
            }
        )
    if video_source == "missing":
        blockers.append(
            {
                "code": "video_snapshot_missing",
                "detail": (
                    "找不到 `work/perception/out/latest/segments_video.json`（本工作树与同级 checkout 都没有）"
                    "→ 观测为空壳，不编数"
                ),
            }
        )
    elif video_source.startswith("sibling:"):
        blockers.append(
            {
                "code": "video_snapshot_external",
                "detail": (
                    f"本工作树无视频快照，只读引用同级 checkout `{video_source}` 的产物；"
                    "验收在别的机器上重跑时需先跑 `work/perception/run_chain.py` 生成该快照"
                ),
            }
        )
    return blockers


def run_network(args: argparse.Namespace) -> dict[str, Any]:
    """真网模式：真网断面候选 + 空载基线 + 视频观测 + 场景因素 → 全套产物。"""
    grading = baseline.load_grading()
    site, network, network_path = sections.load_site_network(args.site or None)
    video_path, video_source, video_searched = calibrate.find_video_snapshot(
        override=args.video or None, seg_prefix=str(site["seg_prefix"])
    )
    video_payload: dict[str, Any] | None = None
    if video_path is not None:
        video_payload = calibrate.load_video_snapshot(video_path)
    ts = str(video_payload.get("ts")) if video_payload else DEMO_BASE_TS

    sections_payload = sections.build_candidate_payload(site, network, network_path, ts)
    baseline_payload = baseline.build_network_baseline(
        sections_payload, video_payload, grading, ts
    )
    observations, invalid_observations = (
        calibrate.observations_from_video(video_payload) if video_payload else ({}, [])
    )
    if video_payload is None:
        invalid_observations = [{"segment_id": None, "missing": ["video_snapshot"]}]
    observations = apply_observation_overrides(
        observations, args.obs_confidence, args.obs_data_age_s
    )
    roles = {item["segment_id"]: item["role"] for item in sections_payload["sections"]}
    unmatched = sorted(set(observations) - set(roles))
    if unmatched:
        raise SystemExit(
            f"视频快照段号不在本站真网段号内：{unmatched}（疑似命名空间混用，先对账 IKMDKY 映射）"
        )

    # 场景：S1~S4（seed / assimilation / factors 注入）
    scenarios_payload = scenario.load_station_scenarios()
    scene = scenario.scenario_from_station(
        scenarios_payload, args.scenario, source_file="stations/scenarios.json"
    )
    scenario_row = scenario.find_scenario(scenarios_payload, args.scenario)
    catalogue_payload, catalogue = factors.load_factor_catalogue()
    del catalogue_payload
    observed_ids = {
        row["segment_id"] for row in baseline_payload["segments"] if row.get("confidence") is not None
    }
    raw_injections = factors.scenario_injections(catalogue, scenario_row)
    if args.eval_ts:
        eval_ts = str(args.eval_ts)
        eval_ts_source = "cli:--eval-ts"
    else:
        eval_ts, eval_ts_source = factors.derive_evaluation_ts(raw_injections, ts)
    scene.evaluation_ts = eval_ts
    active, inactive = factors.prepare_injections(
        catalogue, scenario_row, sections_payload, observed_ids, eval_ts
    )

    state, assimilation_log = calibrate.build_assimilation(
        sections_payload,
        baseline_payload,
        observations,
        scene.assimilation,
        ts=ts,
        mode="network",
        scenario_id=scene.name,
        video_snapshot={
            "present": video_payload is not None,
            "path": repo_rel(video_path) if video_path else None,
            "source": video_source,
            "ts": video_payload.get("ts") if video_payload else None,
            "segment_ids": sorted(observations),
            "searched": video_searched,
            "note": (video_payload or {}).get("note") if video_payload else None,
        },
        invalid_observations=invalid_observations,
    )
    if args.obs_confidence is not None or args.obs_data_age_s is not None:
        assimilation_log["observation_overrides"] = {
            "confidence": args.obs_confidence,
            "data_age_s": args.obs_data_age_s,
            "note": "自检注入的门控测试值（只用于 TC-20 第④项，不是输入数据）",
        }

    before_payload = baseline_payload
    after_payload, injection_records = factors.inject_segments(before_payload, active, grading)
    scenario_rows = list(scenarios_payload["scenarios"])
    scenario_reports: list[dict[str, Any]] = []
    for row in scenario_rows:
        # 每个场景各自派生评估时刻（不跨场景借时间）
        row_raw = factors.scenario_injections(catalogue, row)
        row_ts, row_ts_source = factors.derive_evaluation_ts(row_raw, ts)
        row_active, row_inactive = factors.prepare_injections(
            catalogue,
            row,
            sections_payload,
            observed_ids,
            row_ts,
        )
        scenario_reports.append(
            {
                "scenario_id": row.get("scenario_id"),
                "name": row.get("name"),
                "seed": row.get("seed"),
                "assimilation": {
                    "enabled": bool((row.get("assimilation") or {}).get("enabled")),
                    "edges": list((row.get("assimilation") or {}).get("edges") or []),
                },
                "evaluation_ts": row_ts,
                "evaluation_ts_source": row_ts_source,
                "active_factors": [
                    {
                        "factor_id": item["factor_id"],
                        "name": item["name"],
                        "target": item["target"],
                        "multiplier": item["multiplier"],
                        "from": item.get("from"),
                        "until": item.get("until"),
                        "affected_count": len(item["affected_segment_ids"]),
                        "effects": (
                            "recorded_only（需求类因素需 SUMO 需求生成器）"
                            if item["target"] == "demand"
                            else "segments_corrected"
                        ),
                    }
                    for item in row_active
                ],
                "inactive_factors": [
                    {
                        "factor_id": item["factor_id"],
                        "target": item["target"],
                        "reason": item.get("reason"),
                        "segment_scope": item.get("segment_scope"),
                    }
                    for item in row_inactive
                ],
            }
        )

    assimilation_detail = build_assimilation_detail(state, assimilation_log)
    blockers = _network_blockers(
        sections_payload,
        observations,
        state,
        video_source,
        assimilation_log["scenario_edges"],
        assimilation_detail,
    )
    blockers.extend(
        {
            "code": "factors_unresolved",
            "detail": f"S1~S4 里有因素未生效/未落地：{item['factor_id']}（{item.get('reason')}）",
        }
        for item in inactive
    )
    changed_ids: list[str] = []
    for record in injection_records:
        for segment_id in record["affected_segment_ids"]:
            if segment_id not in changed_ids:
                changed_ids.append(segment_id)
    factors_report = {
        "ts": eval_ts,
        "is_simulated": True,
        "mode": "network",
        "site_id": str(site["site_id"]),
        "scenario_id": scene.name,
        "scenario_name": (scenario.find_scenario(scenarios_payload, args.scenario)).get("name"),
        "seed": scene.seed,
        "evaluation_ts": eval_ts,
        "evaluation_ts_source": eval_ts_source,
        "assimilation": {
            "enabled": bool(scene.assimilation.get("enabled")),
            "edges": list(scene.assimilation.get("edges") or []),
            "gate": dict(scene.assimilation.get("gate") or {}),
        },
        "catalogue": {
            "path": "stations/factors.json",
            "factor_count": len(catalogue),
            "factors": [
                {
                    "factor_id": factor_id,
                    "name": item.get("name"),
                    "targets": list(item.get("targets") or []),
                    "active": bool(item.get("active")),
                    "multiplier": item.get("multiplier"),
                    "implementer": item.get("implementer"),
                    "filler": item.get("filler"),
                    "source_stage1": item.get("source_stage1"),
                    "source_stage2": item.get("source_stage2"),
                }
                for factor_id, item in sorted(catalogue.items())
            ],
        },
        "injections": injection_records,
        "inactive_injections": [
            {
                "factor_id": item.get("factor_id"),
                "name": item.get("name"),
                "target": item.get("target"),
                "multiplier": item.get("multiplier"),
                "segment_scope": item.get("segment_scope"),
                "reason": item.get("reason"),
            }
            for item in inactive
        ],
        "segments": {
            "total": len(before_payload["segments"]),
            "changed": len(changed_ids),
            "unchanged": len(before_payload["segments"]) - len(changed_ids),
            "changed_segment_ids": changed_ids,
        },
        "scenarios": scenario_reports,
        "blockers": blockers,
        "note": (
            "多因素注入报告（演示数据（模拟））：因素值读 stations/factors.json、注入事件读 "
            "stations/scenarios.json 的 S1~S4；判级调 work/perception/level.py 唯一实现；"
            "未生效因素不写 multiplier=1.0 占位。demand 类因素是'只登记不改假测量'"
            "（需 SUMO 需求生成器，真孪生缺失，见 blockers）。"
        ),
    }

    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    ensure_out_dir(out_dir)
    written: dict[str, int] = {}
    written["sections_candidate.json"] = write_json(
        out_dir / "sections_candidate.json", sections_payload
    )
    written["assimilation_state.json"] = write_json(
        out_dir / "assimilation_state.json", state
    )
    written["assimilation_log.json"] = write_json(
        out_dir / "assimilation_log.json", assimilation_log
    )
    written["factors_report.json"] = write_json(
        out_dir / "factors_report.json", factors_report
    )
    written["segments_before.json"] = write_json(out_dir / "segments_before.json", before_payload)
    written["segments_after.json"] = write_json(out_dir / "segments_after.json", after_payload)
    run_log = {
        "ts": ts,
        "is_simulated": True,
        "mode": "network",
        "site_id": str(site["site_id"]),
        "network_file": repo_rel(network_path),
        "scenario_id": scene.name,
        "seed": scene.seed,
        "evaluation_ts": eval_ts,
        "video_snapshot": assimilation_log["video_snapshot"],
        "observation_overrides": assimilation_log.get("observation_overrides"),
        "assimilation_detail": assimilation_detail,
        "observation_summary": {
            "video_observed_segments": sorted(observations),
            "observed_roles": {
                segment_id: roles[segment_id]
                for segment_id in sorted(observations)
                if segment_id in roles
            },
            "internal_observations_rejected": assimilation_detail[
                "internal_observations_rejected"
            ],
            "boundary_observations": assimilation_detail["boundary_observations"],
            "applied_count": assimilation_detail["applied_count"],
            "summary_text": attribution_text(assimilation_detail),
        },
        "counts": {
            "sections": sections_payload["counts"],
            "assimilation": state["counts"],
            "factors": {
                "active": len(active),
                "inactive": len(inactive),
                "changed_segments": len(changed_ids),
            },
        },
        "artifacts": written,
        "blockers": blockers,
        "note": (
            "同化 + 多因素一键入口（真网模式，演示数据（模拟））：不读系统时钟；"
            "internal 永不回灌；真孪生/真实断面数据缺失处如实标阻塞，不编造指标"
        ),
    }
    written["run_log.json"] = write_json(out_dir / "run_log.json", run_log)
    for name in NETWORK_ARTIFACTS:
        assert_artifact(out_dir / name)

    # 接口层读 work/twin/out/assimilation_state.json：只有默认输出目录才发布（自检临时目录不外溢）
    published: str | None = None
    if out_dir.resolve() == DEFAULT_OUT.resolve():
        interface_path = HERE / "out" / "assimilation_state.json"
        write_json(interface_path, state)
        assert_artifact(interface_path)
        published = repo_rel(interface_path)

    return {
        "mode": "network",
        "out_dir": str(out_dir),
        "written": written,
        "published": published,
        "ts": ts,
        "sections": sections_payload["counts"],
        "assimilation": state["counts"],
        "applied": state["applied_count"],
        "assimilation_detail": assimilation_detail,
        "factors": {
            "active": len(active),
            "inactive": len(inactive),
            "changed_segments": len(changed_ids),
        },
        "blockers": blockers,
        "video_snapshot": assimilation_log["video_snapshot"],
    }


# ============================================================================
# 机制示例模式（SEG-###，旧样例）
# ============================================================================


def _sample_sections_payload(
    state_sample: dict[str, Any], ts: str
) -> dict[str, Any]:
    """从 `samples/assimilation_state_sample.json` 的声明 role 造机制示例断面清单。"""
    rows = state_sample.get("edges")
    if not isinstance(rows, list) or not rows:
        raise SystemExit("样例 assimilation_state 缺非空 edges 数组（机制示例需要 role 声明）")
    sections_rows: list[dict[str, Any]] = []
    for edge in rows:
        segment_id = str(edge.get("segment_id") or "")
        role = edge.get("role")
        if not segment_id or role not in ("boundary", "internal"):
            raise SystemExit(f"样例断面缺 segment_id / 非法 role：{edge!r}")
        sections_rows.append(
            {
                "segment_id": segment_id,
                "role": role,
                "name": None,
                "from_node": None,
                "to_node": None,
                "flow_direction": None,
                "basis": f"样例声明 role={role}（机制示例，**不是**真网拓扑推导）",
            }
        )
    sections_rows.sort(key=lambda item: item["segment_id"])
    boundary_ids = [item["segment_id"] for item in sections_rows if item["role"] == "boundary"]
    internal_ids = [item["segment_id"] for item in sections_rows if item["role"] == "internal"]
    return {
        "ts": ts,
        "is_simulated": True,
        "mode": "sample",
        "site_id": "sample-7node",
        "site_name": "7 节点样例网（机制示例）",
        "network_file": "work/twin/samples/segments_sample.json",
        "status": "机制示例·非本站真网（SEG-### 旧样例）",
        "role_source": "samples/assimilation_state_sample.json 的 role（样例声明）",
        "rule": "机制示例：role 来自样例声明，不参与真网签字；internal 同样永远不许回灌",
        "hard_rule": calibrate.REASON_INTERNAL + "（硬规则）",
        "counts": {
            "total": len(sections_rows),
            "boundary": len(boundary_ids),
            "internal": len(internal_ids),
            "boundary_direction_counts": {},
        },
        "boundary_segment_ids": boundary_ids,
        "internal_segment_ids": internal_ids,
        "sections": sections_rows,
        "note": (
            "机制示例断面清单（演示数据（模拟））：SEG-### 属 7 节点样例网，**不是本站真网 SZ-###**；"
            "只用于把同化/门控/因素机制跑通，结果不得当本站结论，也不得与真网产物混写"
        ),
    }


def _sample_observations(
    segments_sample: dict[str, Any], state_sample: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """机制示例观测：boundary 用样例声明的 last_apply，internal 用样例视频段（证明禁止回灌）。"""
    observations: dict[str, dict[str, Any]] = {}
    declared_ts = str(state_sample.get("ts") or segments_sample.get("ts") or "")
    for edge in state_sample.get("edges") or []:
        segment_id = str(edge.get("segment_id"))
        last_apply = edge.get("last_apply") or {}
        gate = edge.get("gate") or {}
        if edge.get("role") == "boundary" and last_apply:
            if not isinstance(last_apply.get("q_vph"), (int, float)) or not isinstance(
                last_apply.get("v_kmh"), (int, float)
            ):
                continue
            observations[segment_id] = {
                "q_vph": float(last_apply["q_vph"]),
                "v_kmh": float(last_apply["v_kmh"]),
                "confidence": float(gate.get("confidence", 0.0)),
                "data_age_s": int(gate.get("data_age_s", 10**9)),
                "source": "sample_video_declared",
                "at": str(last_apply.get("at") or declared_ts),
                "level": None,
            }
    for row in segments_sample.get("segments") or []:
        segment_id = str(row.get("segment_id"))
        if segment_id in observations:
            continue
        if not isinstance(row.get("q_vph"), (int, float)) or not isinstance(
            row.get("v_kmh"), (int, float)
        ):
            continue
        observations[segment_id] = {
            "q_vph": float(row["q_vph"]),
            "v_kmh": float(row["v_kmh"]),
            "confidence": float(row.get("confidence", 0.0)),
            "data_age_s": int(row.get("data_age_s", 10**9)),
            "source": f"sample_segments({row.get('source')})",
            "at": str(segments_sample.get("ts") or declared_ts),
            "level": row.get("level"),
        }
    return observations


def _sample_edge_bridge(stations_dir: Path | str | None = None) -> dict[str, str]:
    """样例站点包 `points.json`：SUMO edge id → 样例段号（`E-001` → `SEG-001`）。

    只对**机制示例**生效；真网模式**不读**这张表（不混命名空间）。
    """
    path = Path(stations_dir or baseline.STATIONS) / "points.json"
    if not path.is_file():
        return {}
    payload = read_json(path)
    bridge: dict[str, str] = {}
    for point in payload.get("points") or []:
        if point.get("type") != "detector" or point.get("role") not in ("boundary", "internal"):
            continue
        sumo_edge_id = point.get("sumo_edge_id")
        segment_id = point.get("segment_id")
        if isinstance(sumo_edge_id, str) and isinstance(segment_id, str):
            bridge[sumo_edge_id] = segment_id
    return bridge


def run_sample(args: argparse.Namespace) -> dict[str, Any]:
    """机制示例：`samples/`（SEG-###）+ 站点包场景 → 同化/门控/因素机制全套产物。"""
    grading = baseline.load_grading()
    segments_sample = read_json(SAMPLES_DIR / "segments_sample.json")
    state_sample = read_json(SAMPLES_DIR / "assimilation_state_sample.json")
    ts = str(state_sample.get("ts") or segments_sample.get("ts") or "")
    if not ts:
        raise SystemExit("样例缺 ts（时间必须从输入派生，不读系统时钟）")

    sections_payload = _sample_sections_payload(state_sample, ts)
    baseline_payload = baseline.build_sample_baseline(segments_sample, grading)
    observations = apply_observation_overrides(
        _sample_observations(segments_sample, state_sample),
        args.obs_confidence,
        args.obs_data_age_s,
    )

    scenarios_payload = scenario.load_station_scenarios()
    scene = scenario.scenario_from_station(
        scenarios_payload, args.scenario, source_file="stations/scenarios.json"
    )
    # 场景 edges 是样例站点包的 SUMO edge id（E-###）：用 points.json 的映射桥到 SEG-###
    bridge = _sample_edge_bridge()
    scenario_assimilation = dict(scene.assimilation)
    scenario_assimilation["edges"] = [
        bridge.get(str(edge), str(edge)) for edge in (scene.assimilation.get("edges") or [])
    ]
    state, assimilation_log = calibrate.build_assimilation(
        sections_payload,
        baseline_payload,
        observations,
        scenario_assimilation,
        ts=ts,
        mode="sample",
        scenario_id=scene.name,
        video_snapshot={
            "present": True,
            "path": "work/twin/samples/assimilation_state_sample.json",
            "source": "samples",
            "ts": ts,
            "segment_ids": sorted(observations),
            "note": "机制示例：观测取样例声明的 last_apply / 样例视频段（演示数据（模拟），非实测）",
        },
        invalid_observations=[],
    )
    assimilation_log["edge_bridge"] = {
        "source": "stations/points.json",
        "mapping": bridge,
        "note": "样例站点包的 SUMO edge id → 样例段号；真网模式不读此表",
    }
    if args.obs_confidence is not None or args.obs_data_age_s is not None:
        assimilation_log["observation_overrides"] = {
            "confidence": args.obs_confidence,
            "data_age_s": args.obs_data_age_s,
            "note": "自检注入的门控测试值（只用于 TC-20 第④项，不是输入数据）",
        }
    assimilation_detail = build_assimilation_detail(state, assimilation_log)

    catalogue_payload, catalogue = factors.load_factor_catalogue()
    del catalogue_payload
    scenario_row = scenario.find_scenario(scenarios_payload, args.scenario)
    raw_injections = factors.scenario_injections(catalogue, scenario_row)
    # --eval-ts 两种模式都生效（此前 sample 模式静默忽略，属缺陷；现在按 CLI 覆盖派生）
    if args.eval_ts:
        eval_ts = str(args.eval_ts)
        eval_ts_source = "cli:--eval-ts"
    else:
        eval_ts, eval_ts_source = factors.derive_evaluation_ts(raw_injections, ts)
    observed_ids = {
        segment["segment_id"] for segment in baseline_payload["segments"]
        if segment.get("confidence") is not None
    }
    active, inactive = factors.prepare_injections(
        catalogue, scenario_row, sections_payload, observed_ids, eval_ts
    )
    before_payload = baseline_payload
    after_payload, injection_records = factors.inject_segments(before_payload, active, grading)

    scenario_reports: list[dict[str, Any]] = []
    for row in scenarios_payload["scenarios"]:
        row_injections = factors.scenario_injections(catalogue, row)
        if args.eval_ts and str(row.get("scenario_id")) == scene.name:
            # 被选中场景用 CLI 覆盖的评估时刻；其它场景各自按因素窗口派生（不跨场景借时间）
            row_ts, row_ts_source = eval_ts, eval_ts_source
        else:
            row_ts, row_ts_source = factors.derive_evaluation_ts(row_injections, ts)
        row_active, row_inactive = factors.prepare_injections(
            catalogue, row, sections_payload, observed_ids, row_ts
        )
        scenario_reports.append(
            {
                "scenario_id": row.get("scenario_id"),
                "name": row.get("name"),
                "seed": row.get("seed"),
                "assimilation": {
                    "enabled": bool((row.get("assimilation") or {}).get("enabled")),
                    "edges": list((row.get("assimilation") or {}).get("edges") or []),
                },
                "evaluation_ts": row_ts,
                "evaluation_ts_source": row_ts_source,
                "active_factors": [
                    {
                        "factor_id": item["factor_id"],
                        "target": item["target"],
                        "multiplier": item["multiplier"],
                        "affected_count": len(item["affected_segment_ids"]),
                    }
                    for item in row_active
                ],
                "inactive_factors": [
                    {
                        "factor_id": item["factor_id"],
                        "target": item["target"],
                        "reason": item.get("reason"),
                        "segment_scope": item.get("segment_scope"),
                    }
                    for item in row_inactive
                ],
            }
        )
    changed_ids: list[str] = []
    for record in injection_records:
        for segment_id in record["affected_segment_ids"]:
            if segment_id not in changed_ids:
                changed_ids.append(segment_id)
    blockers = [
        {
            "code": "mechanism_demo_only",
            "detail": (
                "机制示例：SEG-### 属 7 节点样例网（stations/*.json 占位件），**不是本站真网**；"
                "观测取样例声明值，不是实测；结果不得当本站结论"
            ),
        },
        {
            "code": "calibrator_not_dispatched",
            "detail": f"本次回灌 {state['applied_count']} 条，只落 calibrator_plan，未实际下发 SUMO（不假装）",
        },
    ]
    blockers.extend(
        {
            "code": "factors_unresolved",
            "detail": f"场景 {scene.name} 有因素未生效/未落地：{item['factor_id']}（{item.get('reason')}）",
        }
        for item in inactive
    )
    factors_report = {
        "ts": eval_ts,
        "is_simulated": True,
        "mode": "sample",
        "scenario_id": scene.name,
        "scenario_name": scenario_row.get("name"),
        "seed": scene.seed,
        "evaluation_ts": eval_ts,
        "evaluation_ts_source": eval_ts_source,
        "assimilation": {
            "enabled": bool(scenario_assimilation.get("enabled")),
            "edges": list(scenario_assimilation.get("edges") or []),
            "gate": dict(scene.assimilation.get("gate") or {}),
        },
        "catalogue": {
            "path": "stations/factors.json",
            "factor_count": len(catalogue),
            "factors": [
                {
                    "factor_id": factor_id,
                    "name": item.get("name"),
                    "targets": list(item.get("targets") or []),
                    "active": bool(item.get("active")),
                    "implementer": item.get("implementer"),
                }
                for factor_id, item in sorted(catalogue.items())
            ],
        },
        "injections": injection_records,
        "inactive_injections": [
            {
                "factor_id": item.get("factor_id"),
                "name": item.get("name"),
                "target": item.get("target"),
                "multiplier": item.get("multiplier"),
                "segment_scope": item.get("segment_scope"),
                "reason": item.get("reason"),
            }
            for item in inactive
        ],
        "segments": {
            "total": len(before_payload["segments"]),
            "changed": len(changed_ids),
            "unchanged": len(before_payload["segments"]) - len(changed_ids),
            "changed_segment_ids": changed_ids,
        },
        "scenarios": scenario_reports,
        "blockers": blockers,
        "note": (
            "机制示例的多因素报告（演示数据（模拟））：SEG-### 样例网，非本站真网；"
            "因素值读 stations/factors.json、注入事件读 scenarios.json；判级调 level.py"
        ),
    }

    out_dir = Path(args.out) if args.out else DEFAULT_SAMPLE_OUT
    ensure_out_dir(out_dir)
    written: dict[str, int] = {}
    written["sections_candidate.json"] = write_json(
        out_dir / "sections_candidate.json", sections_payload
    )
    written["assimilation_state.json"] = write_json(out_dir / "assimilation_state.json", state)
    written["assimilation_log.json"] = write_json(
        out_dir / "assimilation_log.json", assimilation_log
    )
    written["factors_report.json"] = write_json(out_dir / "factors_report.json", factors_report)
    written["segments_before.json"] = write_json(out_dir / "segments_before.json", before_payload)
    written["segments_after.json"] = write_json(out_dir / "segments_after.json", after_payload)
    run_log = {
        "ts": ts,
        "is_simulated": True,
        "mode": "sample",
        "site_id": "sample-7node",
        "scenario_id": scene.name,
        "seed": scene.seed,
        "evaluation_ts": eval_ts,
        "video_snapshot": assimilation_log["video_snapshot"],
        "edge_bridge": assimilation_log["edge_bridge"],
        "observation_overrides": assimilation_log.get("observation_overrides"),
        "assimilation_detail": assimilation_detail,
        "observation_summary": {
            "video_observed_segments": sorted(observations),
            "internal_observations_rejected": assimilation_detail[
                "internal_observations_rejected"
            ],
            "boundary_observations": assimilation_detail["boundary_observations"],
            "applied_count": assimilation_detail["applied_count"],
            "summary_text": attribution_text(assimilation_detail),
        },
        "counts": {
            "sections": sections_payload["counts"],
            "assimilation": state["counts"],
            "factors": {
                "active": len(active),
                "inactive": len(inactive),
                "changed_segments": len(changed_ids),
            },
        },
        "artifacts": written,
        "blockers": blockers,
        "note": (
            "机制示例（SEG-###，演示数据（模拟））：只用于跑通同化/门控/因素机制；"
            "不是本站真网、不是实测"
        ),
    }
    written["run_log.json"] = write_json(out_dir / "run_log.json", run_log)
    for name in SAMPLE_ARTIFACTS:
        assert_artifact(out_dir / name)
    return {
        "mode": "sample",
        "out_dir": str(out_dir),
        "written": written,
        "ts": ts,
        "sections": sections_payload["counts"],
        "assimilation": state["counts"],
        "applied": state["applied_count"],
        "assimilation_detail": assimilation_detail,
        "factors": {
            "active": len(active),
            "inactive": len(inactive),
            "changed_segments": len(changed_ids),
        },
        "blockers": blockers,
        "video_snapshot": assimilation_log["video_snapshot"],
    }


# ============================================================================
# CLI
# ============================================================================


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="同化 + 多因素一键入口（Issue IKMS19）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--mode", choices=("network", "sample"), default="network")
    parser.add_argument(
        "--scenario",
        default="S4",
        help="场景：S1~S4 / scenario_1~4 / 常态~多因素（默认 S4 多因素）",
    )
    parser.add_argument("--out", default="", help="输出目录（默认 out/latest 或 out/latest/mechanism_demo）")
    parser.add_argument("--site", default="", help="站点 id（缺省用 site-ranges.json 的 default_site）")
    parser.add_argument("--video", default="", help="视频快照路径（缺省自动找）")
    parser.add_argument(
        "--eval-ts",
        default="",
        dest="eval_ts",
        help="因素评估时刻（缺省从场景因素派生；network / sample 两种模式都生效）",
    )
    parser.add_argument(
        "--obs-confidence",
        type=float,
        default=None,
        dest="obs_confidence",
        help="自检注入：覆盖观测 confidence（TC-20 第④项，不改输入文件）",
    )
    parser.add_argument(
        "--obs-data-age-s",
        type=int,
        default=None,
        dest="obs_data_age_s",
        help="自检注入：覆盖观测 data_age_s（TC-20 第④项，不改输入文件）",
    )
    return parser


def run(argv: list[str] | None = None) -> dict[str, Any]:
    """执行一次（不打印），返回摘要 dict —— 自检工具直接调它。"""
    args = build_parser().parse_args(argv)
    if args.mode == "sample":
        return run_sample(args)
    return run_network(args)


def print_summary(summary: dict[str, Any]) -> None:
    """打印人读摘要（真跑输出，供 self-check 留证）。"""
    mode = summary["mode"]
    sections_counts = summary["sections"]
    assimilation = summary["assimilation"]
    factors_counts = summary["factors"]
    title = "真网模式（SZ-###）" if mode == "network" else "机制示例（SEG-###，非本站真网）"
    print(f"[同化+多因素] {title}")
    print(
        f"  断面候选：{sections_counts['total']} 段"
        f"（boundary {sections_counts['boundary']} / internal {sections_counts['internal']}）"
    )
    video = summary.get("video_snapshot") or {}
    print(
        f"  视频快照：{'在场' if video.get('present') else '缺失'}"
        f"（{video.get('path') or '—'}，来源 {video.get('source')}，段 {len(video.get('segment_ids') or [])}）"
    )
    print(
        f"  同化：回灌 {assimilation['applied']} 条 · boundary {assimilation['boundary']} / "
        f"internal {assimilation['internal']}"
    )
    detail = summary.get("assimilation_detail") or {}
    if detail:
        print(f"  同化归因：{attribution_text(detail)}")
    print(
        f"  因素：生效 {factors_counts['active']} 条 · 未生效/未落地 {factors_counts['inactive']} 条 · "
        f"受影响段 {factors_counts['changed_segments']}"
    )
    print(f"  产物：{summary['out_dir']}")
    for blocker in summary.get("blockers") or []:
        print(f"  阻塞[{blocker['code']}]：{blocker['detail']}")
    if int(detail.get("applied_count") or 0) == 0:
        print("  注意：本次回灌 0 条已按上面的实际原因归因；不宣称 M1-10 通过（签字冻结/真孪生/边界观测见 blockers）。")
    elif mode == "network":
        print("  注意：有回灌但仍不得把同化后的数说成实测；M1-10 是否可宣称仍看签字冻结与真孪生。")


def main(argv: list[str] | None = None) -> int:
    try:  # Windows 控制台编码兜底（中文输出不乱码）
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    summary = run(argv)
    print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
