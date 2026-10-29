#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""before_after.py —— 「修前 / 修后」同视口对照图（进站看不清箭头那条缺陷的收口证据）。

背景：1440×900 / 375×812 这类矮地图容器，进站自然取景只到 zoom 13.02 / 13.49，
低于方向层淡出阈 `DIR_ZOOM_FADE = 15.0` ⇒ `icon-opacity ≈ 0`，箭头**全透明**。
dev-B 的修法 = 进站 `fitStationCamera()` 加缩放下限 `minZoom = DIR_ZOOM_FULL (15.5)`。

输入：
  work/verify/shots/_before/<WxH>/direction-natural.png   修前（minZoom 落地前的那一版）
  work/verify/shots/<WxH>/direction-natural.png          修后
  work/verify/shots/<WxH>/measure.json                   取 containerRect / 相机值做题注

输出：work/verify/before_after_<WxH>.png  —— 左=修前、右=修后，各带题注（zoom / opacity）。
      工作树里没有 Pillow 之外的新依赖。

用法：python work/verify/before_after.py
"""
from __future__ import annotations

import json
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHOTS = ROOT / "work" / "verify" / "shots"
VIEWPORTS = ["1440x900", "375x812", "1280x720"]
PAD = 6
CAP_H = 58
FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
]


def font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        if pathlib.Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def before_conditions() -> dict:
    """修前那一轮的 zoom/opacity 冻结值（measure.json 已被后一轮覆盖，见该文件 _note）。"""
    p = SHOTS / "_before" / "before_conditions.json"
    if not p.exists():
        return {}
    return (json.loads(p.read_text(encoding="utf-8")) or {}).get("viewports") or {}


def opacity_at(measure_path: pathlib.Path) -> tuple[float | None, float | None]:
    """返回 (natural zoom, 该 zoom 下的 icon-opacity)；老 measure.json 没有 opacity 字段时给 None。"""
    if not measure_path.exists():
        return None, None
    d = json.loads(measure_path.read_text(encoding="utf-8"))
    nat = (d.get("passes") or {}).get("natural") or {}
    cam = nat.get("cam") or {}
    lay = nat.get("layout") or {}
    op = lay.get("iconOpacityAtZoom")
    return (cam.get("zoom"), (None if op is None else float(op)))


def crop_map(img: Image.Image, measure_path: pathlib.Path) -> Image.Image:
    """裁到地图容器（箭头全在容器里）；容器信息缺了就退回整图。"""
    rect = None
    if measure_path.exists():
        d = json.loads(measure_path.read_text(encoding="utf-8"))
        rect = ((d.get("passes") or {}).get("natural") or {}).get("containerRect")
    if not rect:
        return img
    x, y = int(rect["x"]), int(rect["y"])
    w, h = int(rect["w"]), int(rect["h"])
    box = (max(0, x - PAD), max(0, y - PAD),
           min(img.width, x + w + PAD), min(img.height, y + h + PAD))
    if box[2] - box[0] < 20 or box[3] - box[1] < 20:
        # 容器整块落在截图之外（375×812 修前那张：地图在首屏下方）——退回整图，别切出空图
        return img
    return img.crop(box)


def one(vp: str) -> pathlib.Path | None:
    before = SHOTS / "_before" / vp / "direction-natural.png"
    after = SHOTS / vp / "direction-natural.png"
    if not before.exists() or not after.exists():
        print(f"[跳过] {vp}：缺 {'修前' if not before.exists() else '修后'} 截图")
        return None

    mpath = SHOTS / vp / "measure.json"
    zb, ob = opacity_at(SHOTS / "_before" / vp / "measure.json")
    cond = before_conditions().get(vp) or {}
    if zb is None and cond.get("natural_zoom") is not None:
        zb, ob = cond["natural_zoom"], cond.get("icon_opacity")
    za, oa = opacity_at(mpath)
    # 修前那轮的 measure.json 我覆盖过（没有 opacity 字段）——用淡出表达式在同一 zoom 上直接算
    if ob is None and zb:
        ob = 0.0 if zb < 15.0 else 1.0

    ib = crop_map(Image.open(before).convert("RGB"), mpath)
    ia = crop_map(Image.open(after).convert("RGB"), mpath)
    hh = max(ib.height, ia.height)

    def fit_h(im: Image.Image, h: int) -> Image.Image:
        if im.height == h:
            return im
        w = int(round(im.width * h / im.height))
        return im.resize((w, h), Image.LANCZOS)

    ib, ia = fit_h(ib, hh), fit_h(ia, hh)
    canvas = Image.new("RGB", (ib.width + ia.width + 18, hh + CAP_H * 2), "white")
    d = ImageDraw.Draw(canvas)
    f = font(20)
    f2 = font(16)
    xb, xa = 0, ib.width + 18
    canvas.paste(ib, (xb, CAP_H))
    canvas.paste(ia, (xa, CAP_H))
    d.text((xb + 4, 6), f"修前 · {vp}", fill=(150, 20, 20), font=f)
    d.text((xb + 4, 32),
           f"进站自然取景 zoom={zb:.2f} · 方向层 opacity={ob:.2f}（<15.0 全透明）"
           if zb else "修前（相机参数不可得）",
           fill=(90, 90, 90), font=f2)
    d.text((xa + 4, 6), f"修后 · {vp}", fill=(20, 110, 40), font=f)
    d.text((xa + 4, 32),
           f"进站自然取景 zoom={za:.2f} · 箭头 opacity={oa:.2f} ⇒ 可见" if za else "修后",
           fill=(90, 90, 90), font=f2)
    d.line([(xa - 9, 0), (xa - 9, canvas.height)], fill=(210, 210, 210), width=1)
    out = ROOT / "work" / "verify" / f"before_after_{vp}.png"
    canvas.save(out, optimize=True)
    print(f"{vp}: {'×'.join(map(str, ib.size))} + {'×'.join(map(str, ia.size))} → {out.name} "
          f"({out.stat().st_size / 1024:.0f} KiB) zoom {zb}→{za} opacity {ob}→{oa}")
    return out


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    done = [p for p in (one(vp) for vp in VIEWPORTS) if p]
    print(f"共 {len(done)} 张")
    return 0 if done else 1


if __name__ == "__main__":
    raise SystemExit(main())
