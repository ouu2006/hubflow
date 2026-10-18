#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""孪生基线构造（Issue IKMS19）：真网 61 段 → 可注入因素的 `segments` 基线。

## 为什么需要它

同化要算「视频实测 vs 孪生基线」的偏差，因素注入要一份 before 快照。但**站点 Z 的真孪生
基线快照目前不存在**（`stations/sumo/*.net.xml` 未构建、`run_with_sumo` 仍是骨架，见
`work/twin/README.md` 第十节阻塞）——所以本模块允许构造一份**空载网络基线**顶上：

| 段 | 来源 | 内容 | 口径 |
|---|---|---|---|
| 有视频观测的段（本站 `SZ-005` / `SZ-024`） | `work/perception/out/latest/segments_video.json` | 视频链路的四项指标（`source: "video"`），逐字段带 `provenance` | **不是本站实测**：样本视频回放（非本站现场） |
| 其余段 | 真网产物 + 站点包 `thresholds.json` 的 `grading.defaults` | **空载**：`q_vph=0`、`v_kmh=null`（无车流就没有平均车速）、`x=0`；`v_f_kmh` / `c_base_vph` 按站点包 defaults 回落 | **空载基线 / 演示，不是仿真实测**，更不是孪生模拟结果；每段标 `baseline_kind="empty_load_demo"` + `param_source` |

**三条纪律**：

1. 空载段 `available=false` / `level=0`（`数据不可用`），**不许当成"畅通"**（TC-11 同口径）；
2. 视频段有真实字段就照抄、缺字段就报错——**不补假测量值**；
3. 真孪生基线一旦生成（W1 的 SUMO 主循环），优先用它，本模块只作缺数据时的**明示降级**。

用法：由 `run_assimilation.py` 调用，不单独执行。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: 本文件位于 work/twin/ → 仓库根是 parents[1]
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
STATIONS = REPO_ROOT / "stations"

#: 基线种类（写进每段 + 顶层，供下游/页面区分"空载演示"与"视频观测"）
BASELINE_VIDEO = "video_observation"
BASELINE_EMPTY_LOAD = "empty_load_demo"

#: 空载基线固定 note（口径文案，不许改成"实测/仿真结果"）
EMPTY_LOAD_NOTE = (
    "空载网络基线（演示，不是仿真实测，也不是孪生模拟结果）：站点 Z 的真孪生基线快照缺失，"
    "这里按真网 61 段 + 站点包 grading.defaults 造一份无车流基线，只用于跑通同化偏差 / 因素注入机制；"
    "真孪生跑起来后必须换成真孪生快照"
)

#: 视频段必须带的数值字段（缺一即报错，不静默补 0）
VIDEO_REQUIRED_FIELDS = (
    "q_vph",
    "v_kmh",
    "v_f_kmh",
    "k_vpk",
    "L_q_m",
    "L_seg_m",
    "T_d_min",
    "c_base_vph",
    "c_vph",
    "x",
    "confidence",
    "data_age_s",
)


def read_json(path: Path) -> dict[str, Any]:
    """读一个 UTF-8 JSON 文件（显式编码，换机器不乱码）。"""
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def load_grading(stations_dir: Path | str | None = None) -> dict[str, Any]:
    """读站点包 `thresholds.json` 的 `grading` 组（判级/回落参数的唯一出处）。"""
    path = Path(stations_dir or STATIONS) / "thresholds.json"
    if not path.is_file():
        raise SystemExit(f"缺站点包 {path}（判级参数必须读站点包，代码里不写死）")
    payload = read_json(path)
    grading = payload.get("grading")
    if not isinstance(grading, dict) or not grading:
        raise SystemExit(f"{path} 缺 grading 组（判级参数组）")
    return grading


def _positive_number(value: Any) -> float | None:
    """数值规整成"正数或 None"（缺失不猜、0/负数当缺失）。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0.0:
        return None
    return number


def _default_params(grading: dict[str, Any]) -> dict[str, Any]:
    """站点包缺省参数（缺字段直接报错，不编数）。"""
    defaults = grading.get("defaults") or {}
    v_f = _positive_number(defaults.get("v_f_kmh"))
    c_default = _positive_number(defaults.get("c_vph"))
    saturation = _positive_number(grading.get("saturation_flow_vph_per_lane"))
    if v_f is None:
        raise SystemExit("站点包 thresholds.json 的 grading.defaults.v_f_kmh 缺失：空载基线无 v_f 可回落")
    if c_default is None and saturation is None:
        raise SystemExit(
            "站点包 thresholds.json 既无 grading.defaults.c_vph 也无 "
            "saturation_flow_vph_per_lane：空载基线无容量可回落"
        )
    return {
        "v_f_kmh": v_f,
        "v_f_source": "station_pack:thresholds.grading.defaults.v_f_kmh",
        "c_vph": c_default,
        "c_source": "station_pack:thresholds.grading.defaults.c_vph",
        "saturation_flow_vph_per_lane": saturation,
    }


def _empty_load_segment(
    section: dict[str, Any], defaults: dict[str, Any], ts: str
) -> dict[str, Any]:
    """造一条空载基线段（无车流 → 无车速 → 判级为「数据不可用」，不是「畅通」）。"""
    speed_limit = _positive_number(section.get("speed_limit"))
    v_f = speed_limit if speed_limit is not None else defaults["v_f_kmh"]
    v_f_source = "network:edges[].speed_limit" if speed_limit is not None else defaults["v_f_source"]
    capacity = _positive_number(section.get("capacity_vph"))
    lanes = _positive_number(section.get("lanes"))
    saturation = defaults["saturation_flow_vph_per_lane"]
    if capacity is not None:
        c_base = capacity
        c_source = "network:edges[].capacity_vph"
    elif lanes is not None and saturation is not None:
        c_base = round(lanes * saturation, 1)
        c_source = "network:lanes × station_pack:grading.saturation_flow_vph_per_lane"
    else:
        c_base = float(defaults["c_vph"])
        c_source = defaults["c_source"]
    length = _positive_number(section.get("length_m"))
    if length is None:
        raise SystemExit(f"段 {section['segment_id']} 缺 length_m（几何真值缺失，不编数）")
    return {
        "segment_id": section["segment_id"],
        "source": "twin",  # 契约取值封闭（video/twin）；空载基线归孪生侧，且下面有 is_simulated/baseline_note
        "q_vph": 0.0,
        "v_kmh": None,  # 空载：无车流就没有平均车速（不写 0，不冒充畅通）
        "v_f_kmh": round(float(v_f), 2),
        "k_vpk": 0.0,
        "L_q_m": 0.0,
        "L_seg_m": round(float(length), 1),
        "T_d_min": 0.0,
        "x": 0.0,
        "c_base_vph": round(float(c_base), 1),
        "c_vph": round(float(c_base), 1),
        "factors_applied": [],
        "confidence": None,
        "data_age_s": None,
        "available": False,
        "level": 0,
        "level_name": "数据不可用",
        "gate_reason": "指标缺失：v（空载基线无车流）",
        "triggered_by": [],
        "is_simulated": True,
        "baseline_kind": BASELINE_EMPTY_LOAD,
        "param_source": {"v_f_kmh": v_f_source, "c_base_vph": c_source},
    }


def _video_segment(
    section: dict[str, Any], observed: dict[str, Any], ts: str
) -> dict[str, Any]:
    """视频观测段照抄视频链路字段（缺必填字段报错，不补假测量值）。"""
    segment_id = section["segment_id"]
    missing = [key for key in VIDEO_REQUIRED_FIELDS if not isinstance(observed.get(key), (int, float))]
    if missing:
        raise SystemExit(
            f"视频快照的段 {segment_id} 缺必填数值字段 {missing}（不补假测量值，先修上游）"
        )
    for key in ("level", "source"):
        if key not in observed:
            raise SystemExit(f"视频快照的段 {segment_id} 缺 {key}（不在本模块补判级/补来源）")
    entry: dict[str, Any] = {
        "segment_id": segment_id,
        "source": observed["source"],
        "q_vph": float(observed["q_vph"]),
        "v_kmh": float(observed["v_kmh"]),
        "v_f_kmh": float(observed["v_f_kmh"]),
        "k_vpk": float(observed["k_vpk"]),
        "L_q_m": float(observed["L_q_m"]),
        "L_seg_m": float(observed["L_seg_m"]),
        "T_d_min": float(observed["T_d_min"]),
        "x": float(observed["x"]),
        "c_base_vph": float(observed["c_base_vph"]),
        "c_vph": float(observed["c_vph"]),
        "factors_applied": [],
        "confidence": float(observed["confidence"]),
        "data_age_s": int(observed["data_age_s"]),
        "level": int(observed["level"]),
        "level_name": observed.get("level_name"),
        "triggered_by": list(observed.get("triggered_by") or []),
        "ci": observed.get("ci"),
        "available": bool(observed.get("available", True)),
        "is_simulated": True,
        "baseline_kind": BASELINE_VIDEO,
    }
    if isinstance(observed.get("provenance"), dict):
        entry["provenance"] = dict(observed["provenance"])
    return entry


def build_network_baseline(
    sections_payload: dict[str, Any],
    video_payload: dict[str, Any] | None,
    grading: dict[str, Any],
    ts: str,
) -> dict[str, Any]:
    """真网基线：61 段 = 视频观测段（照抄）+ 其余空载段（明示降级）。"""
    defaults = _default_params(grading)
    sections = sections_payload["sections"]
    video_segments: dict[str, dict[str, Any]] = {}
    video_meta: dict[str, Any] = {"present": False}
    if video_payload:
        rows = video_payload.get("segments")
        if not isinstance(rows, list) or not rows:
            raise SystemExit("视频快照 segments 缺失或为空（契约第一节：顶层信封 + segments 数组）")
        for row in rows:
            segment_id = str(row.get("segment_id") or "")
            if not segment_id:
                raise SystemExit("视频快照里有段缺 segment_id")
            video_segments[segment_id] = row
        video_meta = {
            "present": True,
            "ts": video_payload.get("ts"),
            "window_sec": video_payload.get("window_sec"),
            "note": video_payload.get("note"),
            "segment_ids": sorted(video_segments),
        }
    section_ids = {section["segment_id"] for section in sections}
    unmatched = sorted(set(video_segments) - section_ids)
    if unmatched:
        raise SystemExit(
            f"视频快照段号不在本站真网段号内：{unmatched}（疑似命名空间混用，先对账 IKMDKY 映射）"
        )

    segments: list[dict[str, Any]] = []
    for section in sections:
        segment_id = section["segment_id"]
        observed = video_segments.get(segment_id)
        if observed is not None:
            segments.append(_video_segment(section, observed, ts))
        else:
            segments.append(_empty_load_segment(section, defaults, ts))
    observed_count = len(video_segments)
    return {
        "ts": ts,
        "window_sec": int(video_meta.get("window_sec") or 60),
        "is_simulated": True,
        "source_chain": "twin",
        "baseline_kind": "mixed(empty_load_demo + video_observation)",
        "video_snapshot": video_meta,
        "counts": {
            "segments": len(segments),
            "video_observed": observed_count,
            "empty_load": len(segments) - observed_count,
        },
        "empty_load_note": EMPTY_LOAD_NOTE,
        "note": (
            "孪生基线（演示数据（模拟））：有视频观测的段照抄视频链路快照（样本视频回放，非本站现场）；"
            "其余段是空载网络基线（演示，不是仿真实测，也不是孪生模拟结果），只用于跑通同化/因素机制。"
            "真孪生基线快照缺失，见 work/twin/README.md 第十六节阻塞。"
        ),
        "segments": segments,
    }


def build_sample_baseline(
    samples_segments: dict[str, Any],
    grading: dict[str, Any],
) -> dict[str, Any]:
    """机制示例基线（旧 `SEG-###` 样例命名空间）：照抄 `samples/segments_sample.json`。

    **只用于机制示例**：`SEG-###` 属 7 节点样例网，不是本站真网，**不得与 `SZ-###` 混用**。
    """
    rows = samples_segments.get("segments")
    if not isinstance(rows, list) or not rows:
        raise SystemExit("样例 segments 缺失或为空（机制示例需要 samples/segments_sample.json）")
    segments: list[dict[str, Any]] = []
    for row in rows:
        entry = dict(row)
        entry.setdefault("factors_applied", [])
        entry["baseline_kind"] = BASELINE_VIDEO if entry.get("source") == "video" else "sample_segments"
        segments.append(entry)
    return {
        "ts": str(samples_segments.get("ts", "")),
        "window_sec": int(samples_segments.get("window_sec") or 60),
        "is_simulated": True,
        "source_chain": "twin",
        "baseline_kind": "sample(SEG-### 机制示例)",
        "counts": {"segments": len(segments)},
        "note": (
            "机制示例基线（演示数据（模拟））：来自 work/twin/samples/segments_sample.json，"
            "段号属 7 节点样例网 SEG-###，不是本站真网 SZ-###；只用于跑通同化/因素机制，不得当本站结果"
        ),
        "segments": segments,
    }
