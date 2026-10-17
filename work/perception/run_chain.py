#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一条命令跑通视频感知链路（Issue IKMF1S）：

    data/monitor/<stream>/{meta.json, detections.json, frames/}
        → 透视标定（calib.py）→ 米制轨迹 → 四项指标（metrics.py）→ 五步判级（level.py）
        → out/latest/segments_video.json（契约 segments.json 形状，source="video"）

**口径**：
- 三个脚本是 `archive/task-three-page-pipeline` 分支**找回的原件**（非重写），本文件是新增的串联入口；
- 通道 → 路段映射**只读** `work/perception/mapping/camera-segments.json`（IKMDKY 唯一真值来源）；
- 判级阈值一律读 `stations/thresholds.json` 的 `grading` 组；判级**不按 source 分支**；
- **确定性**：时间戳取输入 meta 的 `generated_at`（不读系统时钟），同一输入连跑 3 次逐字节一致（M1-3）；
- 样本视频**非本站现场**，所有数值 `is_simulated: true`、`source: "video"`。

用法（仓库根）：
    python work/perception/run_chain.py                 # 写 out/latest/segments_video.json
    python work/perception/run_chain.py --check         # 与既有产物逐字节比对（不写盘）
    python work/perception/run_chain.py --out /tmp/x.json
"""

from __future__ import annotations

import argparse
import json
import sys
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


def run_stream(stream_id: str, segment_id: str, th: dict, window_s: float) -> dict | None:
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
    if frames and "t" not in frames[0]:
        fps0 = float(det.get("fps") or meta.get("fps") or 30.0)
        for fr in frames:
            fr["t"] = round(fr.get("i", 0) / fps0, 4)
    fps = float(det.get("fps") or meta.get("fps") or 30.0)
    track = C.add_speed(C.to_metric_track(cal, frames, det), fps)
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


def main() -> int:
    ap = argparse.ArgumentParser(description="视频感知链路：标定 → 四项指标 → 判级 → segments_video.json")
    ap.add_argument("--out", default=str(OUT_DEFAULT / "segments_video.json"))
    ap.add_argument("--window", type=float, default=60.0, help="统计窗口（秒，TC-01 可配）")
    ap.add_argument("--check", action="store_true", help="只与既有产物比对，不写盘")
    a = ap.parse_args()

    th = load_thresholds()
    text, status = build_output(th, a.window)
    status_text = json.dumps(status, ensure_ascii=False, indent=2) + "\n"
    targets = [(Path(a.out), text), (Path(a.out).parent / "pipeline_status.json", status_text)]

    if a.check:
        bad = 0
        for path, want in targets:
            have = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else ""
            if have != want:
                print(f"❌ 与既有产物不一致：{path}")
                bad += 1
            else:
                print(f"✅ 一致：{path}")
        return 1 if bad else 0

    for path, want in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(want, encoding="utf-8", newline="\n")
        print(f"→ {path}")
    segs = json.loads(text)["segments"]
    print(f"通道 {len(segs)} 路 · 段号 {[s['segment_id'] for s in segs]} · "
          f"等级 {[(s['level'], s['level_name']) for s in segs]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
