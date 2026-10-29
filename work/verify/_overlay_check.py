#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_overlay_check.py —— 把「测量到的屏幕几何」画回截图上，给 L3 出一张人能看的叠加图。

为什么还要这一步：cdp_measure.mjs 给出的是数字（偏移 <0.1px、旋转差 <0.001°），
但业主的诉求里有一半是「看着乱不乱」。数字对不等于人眼看到的就是箭头压在中点上、
锥尖朝着行进方向 —— 所以再裁几张局部图，把独立算出来的行进方向画成黄箭头，
和真实渲染出来的图标叠在一起看。

输入：work/verify/shots/<WxH>/measure.json（含 arrow_px / px_poly / rotate_data /
      tangent_geom_order_deg）+ 同目录 direction-pinned.png
输出：work/verify/arrow_overlay_check.png（拼图，3x 放大）

用法：python work/verify/_overlay_check.py [WxH ...]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]          # work/verify -> work
VERIFY = ROOT / "verify"
TILE = 150          # 裁图边长（CSS px）
SCALE = 2  # 3x 时 PNG 会 3 MiB，撞 doc_gate 的 2 MiB 上限
COLS = 4

KIND_COLOR = {
    "forward": (29, 95, 216),
    "backward": (180, 83, 9),
    "bidirectional": (109, 40, 217),
    "unknown": (139, 139, 139),
}


def vec(bearing_deg: float) -> tuple[float, float]:
    """屏幕向量：bearing 是「从正北顺时针」，屏幕 y 向下。"""
    r = math.radians(bearing_deg)
    return math.sin(r), -math.cos(r)


def pick(rows: list[dict], want_reverse: int = 14) -> list[dict]:
    """抽样：全部 reverse 段 + 双向段里最长的若干（双向段共 33 条，全画太挤）。"""
    by_id = {r["segment_id"]: r for r in rows}
    reverse = [r for r in rows if r["dir_kind"] == "backward"]
    bidi = sorted(
        [r for r in rows if r["dir_kind"] == "bidirectional"],
        key=lambda r: -(r.get("length_m") or 0),
    )[:5]
    # 特意带上那对重合段（反序 + 正序画在同一位置）：SZ-013 / SZ-060
    pair = [by_id[k] for k in ("SZ-013", "SZ-060") if k in by_id]
    out, seen = [], set()
    for r in reverse + bidi + pair:
        if r["segment_id"] in seen or r.get("px_poly") is None:
            continue
        seen.add(r["segment_id"])
        out.append(r)
    return out


def tile_for(img: Image.Image, row: dict) -> Image.Image:
    cx, cy = row["arrow_px"]
    box = (round(cx - TILE / 2), round(cy - TILE / 2),
           round(cx + TILE / 2), round(cy + TILE / 2))
    crop = img.crop(box).resize((TILE * SCALE, TILE * SCALE), Image.LANCZOS)
    d = ImageDraw.Draw(crop, "RGBA")

    def to_tile(p):
        return ((p[0] - box[0]) * SCALE, (p[1] - box[1]) * SCALE)

    # 1) 路段折线（独立投影，1px 灰线；它就是「路段自己」的屏幕位置）
    poly = [to_tile(p) for p in row["px_poly"]]
    if len(poly) >= 2:
        d.line(poly, fill=(0, 200, 255, 220), width=2)

    # 2) 路段中点（我按弧长 50% 独立算的）
    mid = to_tile(row["mid_px"])
    d.ellipse([mid[0] - 4, mid[1] - 4, mid[0] + 4, mid[1] + 4], outline=(255, 255, 255, 255), width=2)

    # 3) 行进方向（黄箭头，长度 46 CSS px）：反序段的 rotate = tangent+180，这里直接画 rotate
    ox, oy = to_tile(row["arrow_px"])
    dx, dy = vec(row["rotate_data"])
    L = 46 * SCALE
    d.line([(ox, oy), (ox + dx * L, oy + dy * L)], fill=(255, 214, 0, 255), width=3)
    tip = (ox + dx * L, oy + dy * L)
    left = (ox + dx * L * 0.82 - dy * 9, oy + dy * L * 0.82 + dx * 9)
    right = (ox + dx * L * 0.82 + dy * 9, oy + dy * L * 0.82 - dx * 9)
    d.polygon([tip, left, right], fill=(255, 214, 0, 255))

    # 4) 图标实测中心（红点）—— 与中点白圈重合即「落在中点上」
    d.ellipse([ox - 3, oy - 3, ox + 3, oy + 3], fill=(255, 60, 60, 255))

    # 5) 角标：段 id / 类型 / 长度 / 偏差（纯 ASCII，免得字体缺字）
    label = f"{row['segment_id']} {row['dir_kind'][:4]} {row.get('length_m') or 0:.0f}m"
    sub = f"d_pos {row['d_pos_px']:.2f}px  d_rot {row['d_rotate_deg']:.3f}deg"
    d.rectangle([0, 0, TILE * SCALE, 34], fill=(0, 0, 0, 150))
    d.text((6, 4), label, fill=(255, 255, 255, 255))
    d.text((6, 18), sub, fill=(190, 190, 190, 255))
    return crop


def main() -> int:
    names = sys.argv[1:] or ["2560x1440"]
    tiles_all: list[tuple[str, list[Image.Image]]] = []
    for name in names:
        d = VERIFY / "shots" / name
        mpath, ppath = d / "measure.json", d / "direction-pinned.png"
        if not (mpath.exists() and ppath.exists()):
            print(f"[skip] {name}: 缺 measure.json 或 direction-pinned.png")
            continue
        m = json.loads(mpath.read_text(encoding="utf-8"))
        rows = (m["passes"].get("pinned") or {}).get("rows") or []
        rows = [r for r in rows if r.get("px_poly")]
        # 容器内坐标 → 整页坐标（截图是整页的）
        rect = (m["passes"].get("pinned") or {}).get("containerRect") or {"x": 0, "y": 0}
        ox, oy = rect["x"], rect["y"]
        for r in rows:
            r["arrow_px"] = [r["arrow_px"][0] + ox, r["arrow_px"][1] + oy]
            r["mid_px"] = [r["mid_px"][0] + ox, r["mid_px"][1] + oy]
            r["px_poly"] = [[p[0] + ox, p[1] + oy] for p in r["px_poly"]]
        if not rows:
            print(f"[skip] {name}: pinned pass 没有带几何的行")
            continue
        img = Image.open(ppath).convert("RGB")
        sel = pick(rows)
        tiles = [tile_for(img, r) for r in sel]
        tiles_all.append((name, tiles))
        print(f"[ok] {name}: {len(sel)} 段 "
              f"(reverse {sum(1 for r in sel if r['dir_kind']=='backward')}, "
              f"bidi {sum(1 for r in sel if r['dir_kind']=='bidirectional')}, "
              f"forward {sum(1 for r in sel if r['dir_kind']=='forward')})")

    if not tiles_all:
        print("没有可画的视口")
        return 1

    name, tiles = tiles_all[0]
    rows_n = math.ceil(len(tiles) / COLS)
    pad = 8
    W = COLS * (TILE * SCALE + pad) + pad
    H = rows_n * (TILE * SCALE + pad) + pad
    sheet = Image.new("RGB", (W, H), (24, 24, 27))
    for i, t in enumerate(tiles):
        x = pad + (i % COLS) * (TILE * SCALE + pad)
        y = pad + (i // COLS) * (TILE * SCALE + pad)
        sheet.paste(t, (x, y))
    out = VERIFY / "arrow_overlay_check.png"
    sheet.save(out)
    print(f"[out] {out}  {sheet.width}x{sheet.height}  ({name}, {len(tiles)} 段)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
