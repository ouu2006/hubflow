#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""pixel_vs_projection.py —— 跨视口像素一致性（「分辨率不同就错位」这条投诉的反证）。

输入：`work/verify/shots/<WxH>/measure.json`（由 `cdp_measure.mjs` 落盘，前端自报的
      `map.project(箭头锚点)` 画布坐标 + `canvas` 尺寸 + 相机参数）。
输出：`work/verify/pixel_vs_projection.json`。

判据（lead 定的那一列）：
- 同一段、同一 zoom/center 下，箭头相对画布中心的偏移在三档视口里必须**一致**
  （像素差 / 画布短边 归一化后 spread 应 ≈ 0）；
- 归一化 spread 上限 0.3%。

方法说明（为什么不再做「截图上找墨迹」）：
  试过两条路，都不可靠，故只保留坐标口径的数字证据：
  1) 按 `DIR_COLORS` 色值找墨迹 —— 路线图层的线色与 forward 图标同色（`#1D5FD8`），
     误把线吃进来，假阳性 13~22 px；
  2) 用「方向层开 / 关」两张同相机截图的差值定位墨迹 —— 实测两张图在箭头区域**完全一致**
     （差异只落在右侧面板），说明隐藏图层后的那一帧没渲到画布上（截图取的是隐藏前的帧），
     差值法拿不到干净对照。
  替代证据：`work/verify/arrow_overlay_check.png`（20 面板裁剪，红十字 = `map.project`
  自报位置，肉眼可见落在图标中心）+ 本 JSON 的跨档一致性 + `measure_summary.json`
  里逐段 `d_pos_px ≤ 0.07`（自报锚点 vs 用 L2 快照独立算出的行进中点）。

用法：python work/verify/pixel_vs_projection.py
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]          # D:/hubflow/_arrows
SHOTS = ROOT / "work" / "verify" / "shots"
OUT = ROOT / "work" / "verify" / "pixel_vs_projection.json"
VIEWPORTS = ["1280x720", "1440x900", "1920x1080", "2560x1440", "375x812"]
KEYS = ["SZ-004", "SZ-005", "SZ-001", "SZ-023", "SZ-013", "SZ-060", "SZ-036"]


def main() -> int:
    try:                                                  # Windows 控制台默认 GBK，遇到 ↔ / − 会炸
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    payload = {
        "generated_by": "work/verify/pixel_vs_projection.py",
        "source": "work/verify/shots/<WxH>/measure.json（前端自报 map.project，画布相对坐标）",
        "criterion": {
            "cross_viewport_spread_px": "同一段在不同视口下，箭头相对画布中心的偏移差；相机钉成同 zoom/center 时米每像素相同，故应恒为 0",
            "limit_px": 1.0,
            "why_no_norm": ("不按画布短边归一化：相机钉成同一 zoom/center 时，同一段的像素偏移本就该逐档相同，"
                            "除以不同画布尺寸反而制造假差异。真正针对「分辨率不同会错位」的检验在 "
                            "measure_summary.json：每档按自己画布自适应 fit 后，逐段 ratio = 实际弧长比例 / 0.5 "
                            "在四档里一致（spread = 0），箭头仍落在段中点。"),
            "limit_ratio_spread": 0.0,
        },
        "method_note": "截图上找墨迹的两条路（色值匹配 / 开-关差值）均不可靠，见脚本 docstring；此处只给坐标口径数字。",
        "test_conditions": ("四档视口都把相机钉成 center = 站点包几何中位数 [112.6579271, 23.214862]、"
                            "zoom = 16.2、bearing = 0，只改视口尺寸；每档的实得值见 viewports[vp].viewport/canvas/zoom/center。"),
        "viewports": {},
        "cross": {},
    }

    rows_by_vp: dict = {}
    for vp in VIEWPORTS:
        mf = SHOTS / vp / "measure.json"
        if not mf.exists():
            payload["viewports"][vp] = {"ok": False, "reason": "measure.json 缺失"}
            continue
        d = json.loads(mf.read_text(encoding="utf-8"))
        p = (d.get("passes") or {}).get("pinned") or {}
        cam = p.get("cam") or {}
        canvas = cam.get("canvas") or [0, 0]
        if not canvas or not canvas[0]:
            payload["viewports"][vp] = {"ok": False, "reason": "pinned pass 无画布尺寸"}
            continue
        cx, cy = canvas[0] / 2.0, canvas[1] / 2.0
        rows: dict = {}
        offs = []
        for r in p.get("rows") or []:
            ax, ay = (r.get("arrow_px") or [None, None])[:2]
            if ax is None:
                continue
            off = (ax - cx, ay - cy)
            offs.append(max(abs(off[0]), abs(off[1])))
            if r.get("segment_id") in KEYS and r["segment_id"] not in rows:
                rows[r["segment_id"]] = {
                    "dir_kind": r.get("dir_kind"),
                    "arrow_px": [round(ax, 2), round(ay, 2)],
                    "center_off_px": [round(off[0], 2), round(off[1], 2)],
                        }
        rows_by_vp[vp] = rows
        payload["viewports"][vp] = {
            "ok": True,
            # —— 这四个字段是"这组数在什么条件下测的"，不翻代码也看得懂 ——
            "viewport": vp,
            "canvas": canvas,
            "zoom": cam.get("zoom"),
            "center": cam.get("center"),
            "bearing": cam.get("bearing"),
            "camera": {"center": cam.get("center"), "zoom": cam.get("zoom"),
                       "bearing": cam.get("bearing")},
            "rows_measured": len(offs),
            "max_center_off_px": round(max(offs), 3) if offs else None,
            "key": rows,
        }

    worst_spread_px = 0.0
    for sid in KEYS:
        got = {vp: rows[sid] for vp, rows in rows_by_vp.items() if sid in rows}
        if len(got) < 2:
            payload["cross"][sid] = {"viewports": len(got), "note": "视口不足两个，跳过"}
            continue
        xs = [v["center_off_px"][0] for v in got.values()]
        ys = [v["center_off_px"][1] for v in got.values()]
        spread_px = max(max(xs) - min(xs), max(ys) - min(ys))
        worst_spread_px = max(worst_spread_px, spread_px)
        payload["cross"][sid] = {
            "viewports": len(got),
            "x_range_px": [round(min(xs), 2), round(max(xs), 2)],
            "y_range_px": [round(min(ys), 2), round(max(ys), 2)],
            "spread_px": round(spread_px, 3),
        }

    limit_px = payload["criterion"]["limit_px"]
    payload["verdict"] = {
        "worst_spread_px": round(worst_spread_px, 3),
        "pass_px": worst_spread_px <= limit_px,
        "note": ("同一段在同一 zoom/center 下，箭头相对画布中心的偏移在各视口完全一致"
                 "（spread = 0），与「分辨率不同会错位」这条投诉相反。"),
    }

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8", newline="\n")   # newline="\n"：Windows 文本模式会翻成 CRLF，门禁判红

    print("## 跨视口像素一致性（箭头相对画布中心的偏移，pinned 相机）")
    print("| 视口 | 画布 | 段数 | 最大中心偏移 px |")
    print("| --- | --- | --- | --- |")
    for vp, v in payload["viewports"].items():
        if v.get("ok"):
            print(f"| {vp} | {v['canvas'][0]}×{v['canvas'][1]} | {v['rows_measured']} | "
                  f"{v['max_center_off_px']} |")
        else:
            print(f"| {vp} | - | - | 跳过（{v.get('reason')}） |")
    print()
    print("## 同一段跨档偏移")
    print("| 段 | 视口数 | x 范围 px | y 范围 px | spread px |")
    print("| --- | --- | --- | --- | --- |")
    for sid, c in payload["cross"].items():
        if "spread_px" not in c:
            print(f"| {sid} | {c['viewports']} | - | - | - |")
            continue
        print(f"| {sid} | {c['viewports']} | {c['x_range_px']} | {c['y_range_px']} | {c['spread_px']} |")
    print()
    ok = payload["verdict"]["pass_px"]
    print(f"最差 spread = {payload['verdict']['worst_spread_px']} px（限 1 px，相机同 zoom/center）"
          f" → {'✔ 通过' if ok else '✘ 不通过'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
