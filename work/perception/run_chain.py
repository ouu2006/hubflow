#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一条命令跑通视频感知链路（Issue IKMF1S；IKNAUM 增加视频侧 ≥60 点时序）：

    data/monitor/<stream>/{meta.json, detections.json, frames/}
        → 透视标定（calib.py）→ 米制轨迹 → 四项指标（metrics.py）→ 五步判级（level.py）
        → out/latest/segments_video.json（契约 segments.json 形状，source="video"）
        → out/latest/segments_video_timeseries.json（视频侧 ≥60 点时序，M1-2 视频侧证据）

**口径**：
- 三个脚本是 `archive/task-three-page-pipeline` 分支**找回的原件**（非重写），本文件是新增的串联入口；
- 通道 → 路段映射**只读** `work/perception/mapping/camera-segments.json`（IKMDKY 唯一真值来源）；
- 判级阈值一律读 `stations/thresholds.json` 的 `grading` 组；判级**不按 source 分支**；
- **确定性**：时间戳取输入 meta 的 `generated_at`（不读系统时钟），同一输入连跑 3 次逐字节一致（M1-3）；
- 样本视频**非本站现场**，所有数值 `is_simulated: true`、`source: "video"`。

**视频侧时序（IKNAUM，业主 2026-10-18「视频侧 ≥60 点时序」）**：
- 样本视频只有 road2 ≈6.6 s / track1 ≈9.3 s，远短于目标统计跨度 —— 时序点由 **detections 循环回放
  （video_reuse=true）+ 滑动窗口** 生成：窗口内所有轨迹点按 `t mod 周期` 平移到窗口，**同一段样本复用**；
- 窗口 / 步长 / 点数可配（`--ts-window` / `--ts-step` / `--ts-points`），固定输入、**不读系统时钟**；
- 时序点只出四项指标（q / v / k / L_q / T_d），**不重跑判级**（防抖需连续周期；单窗口快照已判级）；
- **明确边界**：`q_vph` 是回放等效流量（同一段短样本循环回放会把过车率抬到样本自身的重复频率），
  **不等于**现场流量，也**不宣称 M1-2 整体通过**（只证视频侧点数门槛；整体需池·Q 按台账复核）。

用法（仓库根）：
    python work/perception/run_chain.py                 # 写 segments_video.json + pipeline_status.json
                                                        #   + segments_video_timeseries.json
    python work/perception/run_chain.py --check         # 与既有产物逐字节比对（含时序，不写盘）
    python work/perception/run_chain.py --out /tmp/x.json
    python work/perception/run_chain.py --ts-window 10 --ts-step 1 --ts-points 65
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

DIR = Path(__file__).resolve().parent
ROOT = DIR.parents[1]
STATIONS = ROOT / "stations"
MONITOR = DIR / "data" / "monitor"
MAPPING = DIR / "mapping" / "camera-segments.json"
NETWORK = ROOT / "work/twin/netpack/network_junction.json"
OUT_DEFAULT = DIR / "out" / "latest"

sys.path.insert(0, str(DIR))
import calib as C  # noqa: E402
import level as L  # noqa: E402
import metrics as M  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

#: 输入缺 `generated_at` 时的固定时间戳（**不读系统时钟**，保证可复现；不是"当前时间"）
FALLBACK_TS = "2026-01-01T00:00:00+08:00"

#: 视频侧时序默认口径（M1-2 视频侧：≥60 个统计点；默认 65 点，与孪生侧 65 点对齐便于并排审阅）
TS_POINTS_DEFAULT = 65
TS_WINDOW_DEFAULT = 10.0  # 秒：约等于 1~1.5 个样本回放周期（样本 6.6 s / 9.3 s）
TS_STEP_DEFAULT = 1.0  # 秒：滑动步长；65 点 → 回放跨度 (65-1)*1 + 10 = 74 s
#: M1-2 视频侧点数门槛（手册 17.2：≥60 个统计点）
M1_2_MIN_POINTS = 60
#: 循环回放时给每轮样本的 track_id 加的偏移，避免同一车辆跨轮被当成同一轨迹（否则跨轮 y 跳变会伪造过车）
TID_STRIDE = 1_000_000
#: 时序点字段（只出指标，不重跑判级；见模块 docstring）
TS_FIELDS = ("q_vph", "v_kmh", "k_vpk", "L_q_m", "T_d_min")
#: 时序文件自描述（字段 → 单位 + 公式/口径）
METRIC_FORMULAS = {
    "q_vph": "辆/h · 窗口内越过虚拟断面的车辆数 ÷ 窗口秒数 × 3600（短样本循环回放 → 回放等效流量，不等于现场流量）",
    "v_kmh": "km/h · 窗口内有效标定带内轨迹点瞬时速度均值 × 3.6（带外不计；无样本为 null）",
    "k_vpk": "辆/km · 窗口内在测车辆数 ÷ 路段长度 × 1000",
    "L_q_m": "m · 窗口内排队车辆沿车行方向跨度（落客服务 / 候客 / 违停不计）",
    "T_d_min": "min · 排队消散时间（L_q ÷ 消散速度 ÷ 60；消散速度 = 畅通速度 60% × lanes_factor(1+min(1,q/1800))，演示口径）",
    "point_ts": "ISO 时间 · base_ts + (k × step_sec + window_sec)，k 从 0 起；回放时钟，不是采集时间",
    "video_reuse": "true = 同一段短样本视频被循环回放多次（演示复用），非实时流、非本站现场实测",
}


def load_mapping() -> list[dict]:
    if not MAPPING.is_file():
        raise SystemExit(f"缺三段映射登记表 {MAPPING}（IKMDKY 唯一真值来源）")
    data = json.loads(MAPPING.read_text(encoding="utf-8"))
    rows = []
    for v in data.get("video_streams", []):
        rows.append({"stream_id": v["stream_id"], "segment_id": v["segment_id"],
                     "cam_id": v.get("cam_id"), "cid": v.get("cid")})
    return sorted(rows, key=lambda r: r["stream_id"])


def load_thresholds() -> dict:
    p = STATIONS / "thresholds.json"
    if not p.is_file():
        raise SystemExit(f"缺 {p}（判级/参数必须读站点包）")
    th = json.loads(p.read_text(encoding="utf-8"))
    if "grading" not in th:
        raise SystemExit(f"{p} 缺 grading 组")
    return th


def grading_params(th: dict, segment_id: str) -> dict:
    """按站点包取该段的畅通速度 / 通行能力 / 置信度；取不到用 `grading.defaults` 并**按站点包降权**。"""
    g = th["grading"]
    defaults = g.get("defaults", {})
    matched = None
    for row in g.get("by_segment", []):
        if row.get("segment_id") == segment_id:
            matched = row
            break
    if matched is not None:
        return {
            "v_f_kmh": float(matched.get("v_f_kmh", defaults.get("v_f_kmh", 40))),
            "c_vph": float(matched.get("c_vph", defaults.get("c_vph", 1600))),
            "confidence": float(g.get("confidence", 0.9)),
            "param_source": "by_segment",
        }
    # 站点包硬规则（thresholds.attributes.hard_rule_by_segment）：取不到该段参数 → 用 defaults 并降 confidence
    return {
        "v_f_kmh": float(defaults.get("v_f_kmh", 40)),
        "c_vph": float(defaults.get("c_vph", 1600)),
        "confidence": float(defaults.get("confidence", 0.75)),
        "param_source": "defaults",
    }


def segment_length_m(segment_id: str) -> float:
    if not NETWORK.is_file():
        return float(500.0)
    net = json.loads(NETWORK.read_text(encoding="utf-8"))
    for e in net.get("edges", []):
        if e.get("segment_id") == segment_id and isinstance(e.get("length_m"), (int, float)):
            return float(e["length_m"])
    return float(500.0)


def input_ts(streams: list[str]) -> str:
    stamps = []
    for sid in streams:
        meta_path = MONITOR / sid / "meta.json"
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("generated_at"):
                stamps.append(str(meta["generated_at"]))
    return max(stamps) + "+08:00" if stamps else FALLBACK_TS


def load_stream_inputs(stream_id: str) -> dict | None:
    """读一路样本视频的 detections / meta / 标定 → 米制轨迹（含速度）。

    返回 None 表示该路数据不全（跳过并打印原因，**不编数据**）。快照与视频侧时序共用本函数，
    保证两条产物来自**同一份输入与同一套 calib/metrics 代码**。
    """
    det_path = MONITOR / stream_id / "detections.json"
    meta_path = MONITOR / stream_id / "meta.json"
    if not det_path.is_file() or not meta_path.is_file():
        print(f"  [{stream_id}] 缺 detections.json / meta.json，跳过（不编数据）")
        return None
    det = json.loads(det_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    cal = C.load(stream_id)
    if cal is None:
        print(f"  [{stream_id}] stations/calibration.json 里没有该路标定，跳过（不编数据）")
        return None
    frames = det.get("frames", [])
    fps = float(det.get("fps") or meta.get("fps") or 30.0)
    if frames and "t" not in frames[0]:
        for fr in frames:
            fr["t"] = round(fr.get("i", 0) / fps, 4)
    track = C.add_speed(C.to_metric_track(cal, frames, det), fps)
    return {"det": det, "meta": meta, "cal": cal, "frames": frames, "fps": fps, "track": track,
            "period_s": stream_period_s(track, fps)}


def stream_period_s(track: list[dict], fps: float) -> float:
    """一路样本视频的回放周期（秒）= 最后一个轨迹点时间 + 1 帧；用于循环回放取模。"""
    if not track:
        return max(1e-6, 1.0 / fps)
    return float(max(p.get("t") or 0.0 for p in track)) + 1.0 / fps


def run_stream(stream_id: str, segment_id: str, th: dict, window_s: float) -> dict | None:
    ctx = load_stream_inputs(stream_id)
    if ctx is None:
        return None
    det, meta, cal = ctx["det"], ctx["meta"], ctx["cal"]
    frames = ctx["frames"]
    track = ctx["track"]
    params = grading_params(th, segment_id)
    seg_len = segment_length_m(segment_id)
    m = M.compute(track, window_s=window_s, segment_length_m=seg_len,
                  v_free_kmh=params["v_f_kmh"], points_cfg=None)
    rec = {
        "segment_id": segment_id,
        "source": "video",
        "q_vph": m["q_vph"],
        "v_kmh": m["v_kmh"],
        "v_f_kmh": params["v_f_kmh"],
        "k_vpk": m["k_vpk"],
        "L_q_m": m["L_q_m"],
        "L_seg_m": round(seg_len, 1),
        "T_d_min": m["T_d_min"],
        "c_base_vph": params["c_vph"],
        "c_vph": params["c_vph"],
        "x": round((m["q_vph"] or 0.0) / params["c_vph"], 3) if params["c_vph"] else 0.0,
        "confidence": params["confidence"],
        "data_age_s": 0,
        "factors_applied": [],
    }
    verdict = L.grade(rec, th, None)  # 单次链路：不做跨周期防抖（防抖需要连续周期）
    rec.update({k: verdict[k] for k in ("level", "level_name", "triggered_by", "available", "ci") if k in verdict})
    rec["is_simulated"] = True
    rec["provenance"] = {
        "chain": "video",
        "stream_id": stream_id,
        "channel": cal.segment_id and meta.get("stream_id"),
        "frames": f"1-{len(frames)}",
        "calib_id": f"CAL-{stream_id}",
        "calib_inferred": bool(getattr(cal, "inferred", False)),
        "reprojection_error_px": round(float(getattr(cal, "reproj_px", 0.0)), 3),
        "calib_reproj_limit_px": getattr(cal, "reproj_limit_px", None),
        "calib_scale_limit_pct": getattr(cal, "scale_limit_pct", None),
        "param_source": params["param_source"],
        "window_sec": window_s,
        "speed_samples": m.get("counts", {}).get("speed_samples", 0),
        "metrics_at": meta.get("generated_at"),
        "level_at": meta.get("generated_at"),
        "note": "样本视频回放（非本站现场）· 标定控制点为演示值（inferred）",
    }
    rec["counts"] = m.get("counts", {})
    return rec


def build_output(th: dict, window_s: float) -> tuple[str, dict]:
    mapping = load_mapping()
    segs = []
    for row in mapping:
        rec = run_stream(row["stream_id"], row["segment_id"], th, window_s)
        if rec is not None:
            rec["provenance"]["cam_id"] = row.get("cam_id")
            rec["provenance"]["cid"] = row.get("cid")
            rec["provenance"]["channel"] = row.get("cid")
            segs.append(rec)
    segs.sort(key=lambda r: r["segment_id"])
    ts = input_ts([r["stream_id"] for r in mapping])
    payload = {
        "ts": ts,
        "window_sec": window_s,
        "is_simulated": True,
        "source_chain": "video",
        "note": "视频感知链路（样本视频回放，非本站现场）· 判级与孪生链路共用同一套 level.py，不按 source 分支",
        "segments": segs,
    }
    status = {
        "ts": ts,
        "is_simulated": True,
        "stages": [
            {"key": "dump", "name": "样本视频导出", "ok": len(segs), "total": len(mapping)},
            {"key": "calib", "name": "透视标定", "ok": len(segs), "total": len(mapping)},
            {"key": "metrics", "name": "四项指标", "ok": len(segs), "total": len(mapping)},
            {"key": "level", "name": "判级", "ok": len(segs), "total": len(mapping)},
            {"key": "snapshot", "name": "快照落盘", "ok": 1 if segs else 0, "total": 1},
        ],
        "chain": [
            {"stream_id": r["provenance"]["stream_id"], "status": "ok", "segment_id": r["segment_id"],
             "level": r["level"], "level_name": r["level_name"]}
            for r in segs
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n", status


# ---------------------------------------------------------------- 视频侧时序（IKNAUM）


def replay_slice(track: list[dict], period_s: float, start_s: float, end_s: float) -> list[dict]:
    """取回放时间轴 `[start_s, end_s)` 内的轨迹点（循环回放：`t_replay = t + 轮次 × 周期`）。

    · **固定输入、不读系统时钟**：轮次由窗口起止坐标算出，同一输入同一窗口永远得到同一批点；
    · 每轮给 `tid` 加 `TID_STRIDE` 偏移：同一辆车在不同轮次是不同实例，
      避免"上一轮末尾 → 下一轮开头"的 y 跳变被当成一次虚拟断面过车（那会伪造 q）。
    """
    if period_s <= 0 or end_s <= start_s:
        return []
    out: list[dict] = []
    first = int(math.floor(start_s / period_s))
    last = int(math.floor((end_s - 1e-9) / period_s))
    for cycle in range(first, last + 1):
        offset = cycle * period_s
        for p in track:
            t = float(p["t"]) + offset
            if start_s <= t < end_s:
                q = dict(p)
                q["t"] = round(t, 6)
                q["tid"] = int(p["tid"]) + cycle * TID_STRIDE
                out.append(q)
    return out


def build_timeseries(th: dict, window_s: float, step_s: float, points: int) -> tuple[str, dict]:
    """视频侧 ≥60 点时序：detections 循环回放 + 滑动窗口 → 每段 `points` 个统计点。

    返回 (JSON 文本, 摘要)。摘要里带每段有效点数与 M1-2 视频侧门槛判定（供 main 打印/断言）。
    """
    if points <= 0:
        raise SystemExit("--ts-points 必须为正整数")
    if step_s <= 0:
        raise SystemExit("--ts-step 必须为正数（秒）")
    if window_s <= 0:
        raise SystemExit("--ts-window 必须为正数（秒）")
    mapping = load_mapping()
    base_ts = input_ts([r["stream_id"] for r in mapping])
    base_dt = datetime.fromisoformat(base_ts)
    # 回放跨度：第 k 点窗口 = [k*step, k*step+window)，k = 0..points-1
    replay_span_s = round((points - 1) * step_s + window_s, 3)
    point_ts = [
        (base_dt + timedelta(seconds=round(k * step_s + window_s, 3))).isoformat()
        for k in range(points)
    ]

    seg_records = []
    for row in mapping:
        ctx = load_stream_inputs(row["stream_id"])
        if ctx is None:
            continue
        period = ctx["period_s"]
        params = grading_params(th, row["segment_id"])
        seg_len = segment_length_m(row["segment_id"])
        series: dict[str, list] = {field: [] for field in TS_FIELDS}
        for k in range(points):
            start = k * step_s
            window_track = replay_slice(ctx["track"], period, start, start + window_s)
            m = M.compute(window_track, window_s=window_s, segment_length_m=seg_len,
                          v_free_kmh=params["v_f_kmh"], points_cfg=None)
            for field in TS_FIELDS:
                series[field].append(m[field])
        valid = {
            "v_kmh": sum(1 for x in series["v_kmh"] if isinstance(x, (int, float))),
            "L_q_m": sum(1 for x in series["L_q_m"] if isinstance(x, (int, float))),
        }
        seg_records.append(
            {
                "segment_id": row["segment_id"],
                "source": "video",
                "stream_id": row["stream_id"],
                "cam_id": row.get("cam_id"),
                "cid": row.get("cid"),
                "points": points,
                "valid": valid,
                "video_reuse": True,
                "sample_duration_s": round(period, 3),
                "reuse_cycles": round(replay_span_s / period, 3) if period else None,
                **series,
            }
        )
    seg_records.sort(key=lambda r: r["segment_id"])

    m1_2_ok = any(
        r["valid"]["v_kmh"] >= M1_2_MIN_POINTS and r["valid"]["L_q_m"] >= M1_2_MIN_POINTS
        for r in seg_records
    )
    payload = {
        "ts": base_ts,
        "base_ts": base_ts,
        "window_sec": window_s,
        "step_sec": step_s,
        "is_simulated": True,
        "kind": "video_timeseries",
        "source": "video",
        "valid_note": {
            "L_q_m": "0.0 = metrics 判定的空排队（不是缺测，不算 null）；因此 L_q 有效点数恒等于统计点数，不能把 65/65 读成‘排队动态强证据’",
            "v_kmh": "仅有效标定带内、有速度样本的窗口计入；无样本窗口为 null",
        },
        "video_reuse": True,
        "points": points,
        "point_ts": point_ts,
        "note": (
            f"视频侧每段 {points} 点时序（演示数据（模拟））：样本视频只有 road2≈6.6 s / track1≈9.3 s，"
            f"按循环回放（video_reuse=true）滑动窗口生成；窗口 {window_s} s / 步长 {step_s} s / 回放跨度 "
            f"{replay_span_s} s。q_vph 是回放等效流量（同一段短样本被反复复用），不等于现场流量；"
            "非实时、非实测。只证 M1-2 视频侧点数门槛，不宣称 M1-2 整体通过（孪生侧与台账复核另由池·Q 确认）"
        ),
        "reuse": {
            "video_reuse": True,
            "reason": "样本视频短于目标统计跨度（65 点 × 步长），按 detections 循环回放（同一段样本复用）生成；非实时流、非本站现场实测",
            "replay_span_s": replay_span_s,
            "sample_duration_s": {r["stream_id"]: r["sample_duration_s"] for r in seg_records},
        },
        "metric_formulas": METRIC_FORMULAS,
        "segments": seg_records,
    }
    summary = {
        "base_ts": base_ts,
        "points": points,
        "window_sec": window_s,
        "step_sec": step_s,
        "replay_span_s": replay_span_s,
        "segments": seg_records,
        "m1_2_video_side_ok": m1_2_ok,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n", summary


def print_timeseries_summary(summary: dict) -> bool:
    """打印每段有效点数 + M1-2 视频侧门槛判定；返回门槛是否达成（不宣称整体通过）。"""
    print(
        f"[视频时序] {summary['points']} 点/段 · 窗口 {summary['window_sec']} s / 步长 {summary['step_sec']} s · "
        f"回放跨度 {summary['replay_span_s']} s · video_reuse=true（短样本循环回放，非实时/非实测）"
    )
    for rec in summary["segments"]:
        print(
            f"  {rec['segment_id']}({rec['stream_id']})：v 有效 {rec['valid']['v_kmh']}/{rec['points']} · "
            f"L_q 有效 {rec['valid']['L_q_m']}/{rec['points']} · 样本 {rec['sample_duration_s']} s / "
            f"回放 {rec['reuse_cycles']} 轮"
        )
    if summary["m1_2_video_side_ok"]:
        hit = [
            r for r in summary["segments"]
            if r["valid"]["v_kmh"] >= M1_2_MIN_POINTS and r["valid"]["L_q_m"] >= M1_2_MIN_POINTS
        ]
        names = "、".join(r["segment_id"] for r in hit)
        print(
            f"✅ 视频侧 M1-2 点数门槛达成：{names} 的 v_kmh / L_q_m 有效点均 ≥{M1_2_MIN_POINTS}"
            "（只证视频侧；M1-2 整体不宣称通过，需孪生侧 + 池·Q 按台账复核）"
        )
        return True
    print(
        f"❌ 视频侧 M1-2 点数门槛未达成：没有任何 SZ-### 段的 v_kmh / L_q_m 有效点同时 ≥{M1_2_MIN_POINTS}"
        f"（当前 --ts-points={summary['points']}；门槛按手册 17.2，不降标准）"
    )
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="视频感知链路：标定 → 四项指标 → 判级 → segments_video.json（+ 视频侧时序）")
    ap.add_argument("--out", default=str(OUT_DEFAULT / "segments_video.json"))
    ap.add_argument("--window", type=float, default=60.0, help="单窗口快照的统计窗口（秒，TC-01 可配）")
    ap.add_argument("--check", action="store_true", help="只与既有产物比对（含时序），不写盘")
    ap.add_argument("--ts-out", default=None,
                    help="视频侧时序输出路径（默认与 --out 同目录的 segments_video_timeseries.json）")
    ap.add_argument("--ts-window", type=float, default=TS_WINDOW_DEFAULT,
                    help=f"视频侧时序的滑动窗口（秒，默认 {TS_WINDOW_DEFAULT}；约 1~1.5 个样本回放周期）")
    ap.add_argument("--ts-step", type=float, default=TS_STEP_DEFAULT,
                    help=f"视频侧时序的滑动步长（秒，默认 {TS_STEP_DEFAULT}）")
    ap.add_argument("--ts-points", type=int, default=TS_POINTS_DEFAULT,
                    help=f"视频侧时序的统计点数（默认 {TS_POINTS_DEFAULT}；M1-2 门槛 ≥{M1_2_MIN_POINTS}）")
    a = ap.parse_args()

    th = load_thresholds()
    text, status = build_output(th, a.window)
    status_text = json.dumps(status, ensure_ascii=False, indent=2) + "\n"
    out_path = Path(a.out)
    ts_path = Path(a.ts_out) if a.ts_out else out_path.parent / "segments_video_timeseries.json"
    ts_text, ts_summary = build_timeseries(th, a.ts_window, a.ts_step, a.ts_points)
    gate_ok = print_timeseries_summary(ts_summary)
    targets = [(out_path, text), (out_path.parent / "pipeline_status.json", status_text), (ts_path, ts_text)]

    if a.check:
        bad = 0
        for path, want in targets:
            have = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else ""
            if have != want:
                print(f"❌ 与既有产物不一致：{path}")
                bad += 1
            else:
                print(f"✅ 一致：{path}")
        return 1 if (bad or not gate_ok) else 0

    if not gate_ok:
        # 点数门槛未达成：不写盘，避免把既有 65 点证据覆盖成失败版（审查发现）
        print("❌ 视频侧时序点数门槛未达成，未写盘（避免覆盖既有产物）", flush=True)
        return 1

    for path, want in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(want, encoding="utf-8", newline="\n")
        print(f"→ {path}")
    segs = json.loads(text)["segments"]
    print(f"通道 {len(segs)} 路 · 段号 {[s['segment_id'] for s in segs]} · "
          f"等级 {[(s['level'], s['level_name']) for s in segs]}")
    if not gate_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
