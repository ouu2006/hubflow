#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""summarize_measure.py —— 把各视口 `measure.json` 收成验收报告要的两张表。

为什么单独一支：三档视口的原始量尺在 `work/verify/shots/<WxH>/measure.json`（每档 61 段 ×
3 个相机），验收报告要的是「同一条段在不同分辨率下偏多少」——跨视口比对必须用同一个脚本算，
不然数字没法互相印证（也就没法回答业主那句「不同分辨率会错位」）。

口径：
- `d_pos_px`：箭头图标屏幕位置 − 行进 50% 弧长点投影（CSS px）
- `ratio`：`d_pos_px / span_px`（段在屏上的长度，px）——**分辨率无关**的偏位度量
- `d_rotate_deg`：要素 `icon-rotate` − 行进切线方位角（度）
- `d_screen_bearing_deg`：锥尖屏幕向量 − 行进方位屏幕投影（度），这条才直接回答「头朝哪」

用法：python work/verify/summarize_measure.py [WxH ...]（默认 1280x720 1440x900 1920x1080 2560x1440 375x812）
输出：终端 markdown + work/verify/measure_summary.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "work/verify/shots"
OUT = ROOT / "work/verify/measure_summary.json"
DEFAULT = ("1280x720", "1440x900", "1920x1080", "2560x1440", "375x812")
KEY_SEGS = ("SZ-004", "SZ-005", "SZ-023", "SZ-013", "SZ-060")
PASSES = ("natural", "pinned", "rotated")


def load(vp: str) -> dict:
    return json.loads((SHOTS / vp / "measure.json").read_text(encoding="utf-8"))


def summarize(vp: str, data: dict) -> dict:
    out: dict = {"viewport": vp, "passes": {}}
    for name in PASSES:
        p = (data.get("passes") or {}).get(name)
        if not p or not p.get("ok"):
            out["passes"][name] = {"ok": False}
            continue
        rows = p.get("rows") or []
        cam = p.get("cam") or {}
        ratios = [r["d_pos_px"] / r["span_px"] for r in rows if r.get("span_px")]
        lay = p.get("layout") or {}
        out["passes"][name] = {
            "ok": True,
            # —— 以下四个字段是"这组数是在什么条件下测的"自解释头，看数的人不必翻代码 ——
            "viewport": f"{cam.get('inner', [0, 0])[0]}x{cam.get('inner', [0, 0])[1]}",
            "canvas": cam.get("canvas"),
            "zoom": round(float(cam.get("zoom") or 0), 4),
            "center": [round(float(v), 7) for v in (cam.get("center") or [])],
            "bearing": cam.get("bearing"),
            # 方向层在这一 zoom 下的实得样式（opacity=0 ⇒ 箭头全透明，业主看到的"没有箭头"）
            "icon_opacity_at_zoom": (None if lay.get("iconOpacityAtZoom") is None
                                     else round(float(lay["iconOpacityAtZoom"]), 4)),
            "icon_size_at_zoom": (None if lay.get("iconSizeAtZoom") is None
                                  else round(float(lay["iconSizeAtZoom"]), 4)),
            "counts": p.get("counts"),
            "segments_measured": len(rows),
            "max_d_pos_px": round(max(r["d_pos_px"] for r in rows), 4),
            "max_ratio": round(max(ratios), 6),
            "max_d_rotate_deg": round(max(abs(r["d_rotate_deg"]) for r in rows), 6),
            "max_d_screen_bearing_deg": round(max(abs(r["d_screen_bearing_deg"]) for r in rows), 6),
            "key": {r["segment_id"]: {
                "arrow_px": [round(v, 2) for v in r["arrow_px"]],
                "d_pos_px": round(r["d_pos_px"], 4),
                "ratio": round(r["d_pos_px"] / r["span_px"], 6) if r.get("span_px") else None,
                "d_rotate_deg": round(r["d_rotate_deg"], 4),
                "d_screen_bearing_deg": round(r["d_screen_bearing_deg"], 4),
                "dir_kind": r["dir_kind"],
                "span_px": round(r.get("span_px") or 0, 2),
            } for r in rows if r["segment_id"] in KEY_SEGS},
        }
    return out


def cross(allv: dict[str, dict]) -> dict:
    """同一条段在各视口之间的 ratio / rotate 一致性（分辨率无关的强证据）。"""
    per: dict[str, dict[str, tuple[float, float]]] = {}
    for vp, data in allv.items():
        p = (data.get("passes") or {}).get("pinned") or {}
        for r in p.get("rows") or []:
            if r["segment_id"] in KEY_SEGS and r.get("span_px"):
                per.setdefault(r["segment_id"], {})[vp] = (
                    r["d_pos_px"] / r["span_px"], r["d_rotate_deg"])
    out = {}
    for sid, m in per.items():
        ratios = [v[0] for v in m.values()]
        rots = [v[1] for v in m.values()]
        out[sid] = {
            "viewports": sorted(m),
            "ratio_min": round(min(ratios), 6), "ratio_max": round(max(ratios), 6),
            "ratio_spread": round(max(ratios) - min(ratios), 6),
            "rotate_min": round(min(rots), 4), "rotate_max": round(max(rots), 4),
            "rotate_spread_deg": round(max(rots) - min(rots), 4),
        }
    return out


def main() -> int:
    try:                      # Windows 控制台默认 GBK，遇到 ↔ / − 会炸；统一按 UTF-8 输出
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    vps = sys.argv[1:] or list(DEFAULT)
    allv = {vp: load(vp) for vp in vps}
    payload = {
        "_meta": {
            "purpose": "三档/四档视口箭头落点与朝向的跨分辨率汇总（验收报告 5.4 主证据）",
            "generated_by": "work/verify/summarize_measure.py",
            "source": "work/verify/shots/<WxH>/measure.json（cdp_measure.mjs 产出）",
            "criterion": {"pos_px": 0.5, "ratio": 0.01, "rotate_deg": 0.5, "screen_bearing_deg": 1.0},
        },
        "viewports": {vp: summarize(vp, allv[vp]) for vp in vps},
        # 每档的"测什么条件"一行说清：视口 / 画布 / zoom / 中心
        "conditions": {
            vp: {
                "viewport": f"{allv[vp].get('meta', {}).get('width')}x{allv[vp].get('meta', {}).get('height')}",
                "canvas": ((allv[vp].get("passes", {}).get("pinned", {}).get("cam") or {}).get("canvas")),
                "pinned_zoom": round(float(((allv[vp].get("passes", {}).get("pinned", {}).get("cam") or {}).get("zoom") or 0)), 4),
                "pinned_center": [round(float(v), 7) for v in (((allv[vp].get("passes", {}).get("pinned", {}).get("cam") or {}).get("center")) or [])],
                "natural_zoom": round(float(((allv[vp].get("passes", {}).get("natural", {}).get("cam") or {}).get("zoom") or 0)), 4)
                if (allv[vp].get("passes", {}).get("natural", {}) or {}).get("ok") else None,
                "note": ("pinned = 钉死相机（中心=站点包几何中位数，zoom 见 pinned_zoom，bearing 0），"
                         "用于跨分辨率比对；natural = 应用自己 fitBounds 的取景，用于看「看不看得见箭头」。"),
            } for vp in vps
        },
        "cross_viewport": cross(allv),
        "canvas": {vp: (allv[vp].get("passes", {}).get("pinned", {}).get("cam") or {}).get("canvas")
                   for vp in vps},
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8", newline="\n")

    print("## 各视口（pinned 相机，direction 层）")
    print()
    print("| 视口 | canvas(CSS px) | zoom | 要素 | 最大 \\|d_pos\\| px | 最大 \\|d_pos\\|/段长 | 最大 \\|d_rotate\\| ° | 最大 \\|d_bearing\\| ° |")
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for vp in vps:
        p = payload["viewports"][vp]["passes"].get("pinned") or {}
        if not p.get("ok"):
            print(f"| {vp} | — | — | 未取到（pinned 未通过） | — | — | — | — |")
            continue
        print("| {vp} | {c} | {z} | {n} | {dp} | {rt} | {dr} | {db} |".format(
            vp=vp, c="×".join(str(x) for x in p["canvas"]), z=p["zoom"],
            n=p["segments_measured"], dp=p["max_d_pos_px"], rt=p["max_ratio"],
            dr=p["max_d_rotate_deg"], db=p["max_d_screen_bearing_deg"]))
    print()
    print("## 跨视口一致性（同段不同分辨率）")
    print()
    print("| 段 | 视口数 | ratio 区间 | ratio 极差 | rotate 区间 ° | rotate 极差 ° |")
    print("| --- | ---: | --- | ---: | --- | ---: |")
    for sid, m in payload["cross_viewport"].items():
        print(f"| {sid} | {len(m['viewports'])} | {m['ratio_min']}–{m['ratio_max']} | "
              f"{m['ratio_spread']} | {m['rotate_min']}–{m['rotate_max']} | {m['rotate_spread_deg']} |")
    print()
    print("写盘", OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
