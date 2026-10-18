#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""孪生基线构造（Issue IKMS19 / IKNAUN）：真网 61 段 → 可注入因素的 `segments` 基线。

## 为什么需要它

同化要算「视频实测 vs 孪生基线」的偏差，因素注入要一份 before 快照。基线有三种来源，
**优先级从高到低**（IKNAUN 起接入 W1 真孪生快照）：

| 优先级 | 来源 | `baseline_source` | 口径 |
|---|---|---|---|
| 1 | **W1 真孪生快照** `out/latest/segments_twin.json`（61 段 `SZ-###`） | `twin.latest` | 孪生主循环产物（**演示数据（模拟）**，不是实测）；顶层记 `twin_snapshot_sha`，每段记 `baseline_used` |
| 2 | 视频链路快照（仅观测段）+ 空载构造（其余段） | `empty_load_demo` | **缺真孪生快照时的明示降级**；空载段不是孪生模拟结果，不许当"畅通" |
| 3 | `samples/segments_sample.json`（旧 `SEG-###` 样例） | `sample_segments` | 只给机制示例用，**不是本站真网** |

**三条纪律**：

1. 有真孪生快照时**优先用**，段号/字段不符直接报错（不拼凑两份数据）；
2. 空载段 `available=false` / `level=0`（`数据不可用`），**不许当成"畅通"**（TC-11 同口径）；
3. 基线只决定"同化偏差的分母"和"因素注入的 before"，**观测（视频）与基线分开记**——
   不许再把观测值当基线（IKMS19 空载期的局限，IKNAUN 起由真孪生快照修正）。

用法：由 `run_assimilation.py` 调用，不单独执行。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

#: 本文件位于 work/twin/ → 仓库根是 parents[1]
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
STATIONS = REPO_ROOT / "stations"

#: 基线种类（写进每段 + 顶层，供下游/页面区分"真孪生""空载演示""视频观测"）
BASELINE_TWIN = "twin.latest"
BASELINE_EMPTY_LOAD = "empty_load_demo"
BASELINE_VIDEO = "video_observation"
BASELINE_SAMPLE = "sample_segments"

#: 真孪生快照每段必须带的数值字段（缺一即报错，不静默补 0）
TWIN_REQUIRED_FIELDS = ("q_vph", "x", "c_base_vph", "c_vph", "L_seg_m", "level")

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


def load_twin_snapshot(path: Path) -> tuple[dict[str, Any], str, dict[str, Any]]:
    """读 **W1 真孪生快照**（`loop.py` 产出的 `segments_twin.json`）。

    返回 `(payload, sha256, meta)`；顶层 `ts` / `segments[]` / 每段必填数值字段缺一即报错
    （**不拼凑、不补 0**）。`sha256` 用来给 TC-20① 前置断言核"基线到底是不是这份快照"。
    """
    if not path.is_file():
        raise SystemExit(f"真孪生快照不存在：{path}（先跑 `python work/twin/loop.py --duration 3900 --seed 42`）")
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"真孪生快照 {path} 顶层不是对象")
    ts = payload.get("ts")
    if not isinstance(ts, str) or not ts:
        raise SystemExit(f"真孪生快照 {path} 缺 ts（时间必须从仿真时钟派生，不读系统时钟）")
    rows = payload.get("segments")
    if not isinstance(rows, list) or not rows:
        raise SystemExit(f"真孪生快照 {path} 缺非空 segments 数组（契约第一节）")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise SystemExit(f"真孪生快照 {path} 的 segments[] 里有非对象行")
        segment_id = row.get("segment_id")
        if not isinstance(segment_id, str) or not segment_id:
            raise SystemExit(f"真孪生快照 {path} 里有段缺 segment_id")
        if segment_id in seen:
            raise SystemExit(f"真孪生快照 {path} 段号重复：{segment_id}")
        seen.add(segment_id)
        missing = [key for key in TWIN_REQUIRED_FIELDS if not isinstance(row.get(key), (int, float))]
        if missing:
            raise SystemExit(f"真孪生快照 {path} 的段 {segment_id} 缺必填数值字段 {missing}（不补假测量值）")
        # 车速允许 null（窗口内确实无车），但字段必须存在；缺失字段与 null 是两回事
        if "v_kmh" not in row:
            raise SystemExit(f"真孪生快照 {path} 的段 {segment_id} 缺 v_kmh 键（无车应为 null，不许省键）")
    meta = {
        "path": str(path),
        "sha256": sha,
        "ts": ts,
        "window_sec": payload.get("window_sec"),
        "source": payload.get("source"),
        "background_source": payload.get("background_source"),
        "is_simulated": bool(payload.get("is_simulated")),
        "segment_count": len(rows),
        "note": payload.get("note"),
    }
    return payload, sha, meta


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
        "baseline_used": BASELINE_EMPTY_LOAD,
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
        "baseline_used": BASELINE_VIDEO,
    }
    if isinstance(observed.get("provenance"), dict):
        entry["provenance"] = dict(observed["provenance"])
    return entry


def _twin_segment(section: dict[str, Any], twin_row: dict[str, Any]) -> dict[str, Any]:
    """真孪生快照段 → 基线段（照抄 W1 的 61 段指标，逐段标 baseline_used=twin.latest）。"""
    entry = dict(twin_row)
    entry["factors_applied"] = list(twin_row.get("factors_applied") or [])
    entry["baseline_kind"] = "twin_snapshot"
    entry["baseline_used"] = BASELINE_TWIN
    return entry


def build_network_baseline(
    sections_payload: dict[str, Any],
    video_payload: dict[str, Any] | None,
    grading: dict[str, Any],
    ts: str,
    twin_payload: dict[str, Any] | None = None,
    twin_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """真网基线：**优先 W1 真孪生快照**；缺失时明示降级为空载（+ 视频观测段照抄）。

    - `twin_payload` 在场：61 段全部取真孪生快照（段号集合必须与断面候选一致），
      顶层 `baseline_source="twin.latest"`、`twin_snapshot_sha` 可核，每段 `baseline_used="twin.latest"`；
    - 不在场：`baseline_source="empty_load_demo"`，有视频观测的段照抄视频链路、其余段空载（逐段
      `baseline_used` 如实标 `video_observation` / `empty_load_demo`）。
    """
    defaults = _default_params(grading)
    sections = sections_payload["sections"]
    section_ids = {section["segment_id"] for section in sections}

    if twin_payload is not None:
        rows = twin_payload.get("segments")
        if not isinstance(rows, list) or not rows:
            raise SystemExit("真孪生快照 segments 缺失或为空（契约第一节：顶层信封 + segments 数组）")
        twin_segments: dict[str, dict[str, Any]] = {}
        for row in rows:
            segment_id = str(row.get("segment_id") or "")
            if not segment_id:
                raise SystemExit("真孪生快照里有段缺 segment_id")
            twin_segments[segment_id] = row
        twin_ids = set(twin_segments)
        if twin_ids != section_ids:
            missing = sorted(section_ids - twin_ids)
            extra = sorted(twin_ids - section_ids)
            raise SystemExit(
                "真孪生快照与断面候选段号不一致（不拼凑）："
                f"快照缺 {missing}；快照多 {extra}（快照需覆盖本站全部 {len(section_ids)} 段）"
            )
        segments = [
            _twin_segment(section, twin_segments[section["segment_id"]])
            for section in sections
        ]
        meta = dict(twin_meta or {})
        return {
            "ts": str((twin_payload.get("ts") if twin_payload else ts) or ts),
            "window_sec": int((twin_payload.get("window_sec") if twin_payload else None) or 60),
            "is_simulated": True,
            "source_chain": "twin",
            "baseline_source": BASELINE_TWIN,
            "baseline_kind": "twin_snapshot",
            "twin_snapshot": meta,
            "counts": {
                "segments": len(segments),
                "from_twin": len(segments),
                "from_empty_load": 0,
            },
            "note": (
                "孪生基线（**演示数据（模拟）**）：优先取 W1 真孪生快照 `out/latest/segments_twin.json`"
                "（61 段 SZ-###，loop.py 产物；不是实测、不是采集数据）；同化偏差以它为分母，"
                "观测值另记，不把观测当基线。真孪生快照 sha256 见 twin_snapshot.sha256。"
            ),
            "segments": segments,
        }

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
        "baseline_source": BASELINE_EMPTY_LOAD,
        "baseline_kind": "mixed(empty_load_demo + video_observation)",
        "twin_snapshot": {"present": False},
        "video_snapshot": video_meta,
        "counts": {
            "segments": len(segments),
            "video_observed": observed_count,
            "from_empty_load": len(segments) - observed_count,
        },
        "empty_load_note": EMPTY_LOAD_NOTE,
        "note": (
            "孪生基线（演示数据（模拟））：**真孪生快照缺失**，退回空载网络基线（演示，不是仿真实测，"
            "也不是孪生模拟结果）；有视频观测的段照抄视频链路快照（样本视频回放，非本站现场）。"
            "先跑 `python work/twin/loop.py --duration 3900 --seed 42` 再用 `--twin` 接真基线。"
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
        entry["baseline_used"] = BASELINE_SAMPLE
        segments.append(entry)
    return {
        "ts": str(samples_segments.get("ts", "")),
        "window_sec": int(samples_segments.get("window_sec") or 60),
        "is_simulated": True,
        "source_chain": "twin",
        "baseline_source": BASELINE_SAMPLE,
        "baseline_kind": "sample(SEG-### 机制示例)",
        "twin_snapshot": {"present": False},
        "counts": {"segments": len(segments)},
        "note": (
            "机制示例基线（演示数据（模拟））：来自 work/twin/samples/segments_sample.json，"
            "段号属 7 节点样例网 SEG-###，不是本站真网 SZ-###；只用于跑通同化/因素机制，不得当本站结果"
        ),
        "segments": segments,
    }
