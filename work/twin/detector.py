"""虚拟检测器:按检测断面聚合流量 / 车速 / 排队,产出 segments 快照。

输入:检测断面的过车记录(真孪生);samples/segments_sample.json(--no-sumo)
输出:segments.json(契约第一节:带 ts 与 is_simulated 的信封 + segments 数组)
口径:断面布点必须与二期摄像头点位一致(README 第四节);
     孪生链路每段的 source 取 "twin",视频链路取 "video",两条链路字段逐字段一致。

用法:由 loop.py 调用,不单独执行。
"""

from __future__ import annotations

from typing import Any

#: 两条数据源(契约 1.1,取值封闭)
SOURCES = ("video", "twin")

#: 拥堵等级名(契约:level 1~4)
LEVEL_NAMES = {1: "畅通", 2: "缓行", 3: "拥堵", 4: "严重拥堵"}


def aggregate_snapshot(
    cfg: Any, sample_segments: dict[str, Any], applied: list[dict[str, Any]], ts: str
) -> dict[str, Any]:
    """产出这一段仿真时刻的 segments 快照。

    --no-sumo:样例直接把路段带过来,这里只做三件事 —— 换仿真时间戳、
    校验字段与取值、按清单补上生效因素。**不编造任何测量值。**
    真孪生:由断面过车记录聚合出四项指标与判级(调 work/perception/)。
    """
    if not cfg.no_sumo:
        raise NotImplementedError(
            "断面聚合待 W1 实现:过车记录 → 四项指标 → 判级(调 work/perception/)"
        )
    segments = _validate_segments(sample_segments)
    for segment in segments:
        if applied:
            segment["factors_applied"] = [dict(f) for f in applied]
    return {
        "ts": ts,
        "window_sec": int(sample_segments.get("window_sec", 900)),
        "is_simulated": True,
        "segments": segments,
    }


def _validate_segments(sample_segments: dict[str, Any]) -> list[dict[str, Any]]:
    """逐段校验契约字段(必填字段缺一即报错,不静默补空)。"""
    segments = sample_segments.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("样例 segments 缺失或为空(契约第一节:顶层信封 + segments 数组)")
    for segment in segments:
        for key in ("segment_id", "level", "source", "is_simulated"):
            if key not in segment:
                raise ValueError(f"路段 {segment.get('segment_id')!r} 缺必填字段 {key}")
        if segment["source"] not in SOURCES:
            raise ValueError(f"未知数据源 source={segment['source']!r}(仅 {SOURCES})")
        if int(segment["level"]) not in LEVEL_NAMES:
            raise ValueError(f"等级越界 level={segment['level']!r}(仅 1~4)")
    return [dict(segment) for segment in segments]


def four_metrics(detections: list[dict[str, Any]], window_sec: int) -> dict[str, float]:
    """由断面过车记录聚合出四项指标(骨架,TODO)。

    返回 {"q_vph": 流量, "v_kmh": 平均车速, "k_vpk": 密度, "L_q_m": 排队长度};
    判级不在这里做 —— 判级归 work/perception/ 的 level.py(开发B)。
    """
    raise NotImplementedError("四项指标待 W1 实现:断面过车记录 → 流量/车速/密度/排队")
