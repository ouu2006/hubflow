#!/usr/bin/env python3
"""读 `.net.xml` → 画**线路图** PNG（两版：深色演示版 / `--light` 打印版）。

**画的是什么**：节点（路口）、边（路段，按方向错开画，双向路段看得出是两条）、
每条边的**车道数**与**限速**。**这是一张示意图**，不是地理配准图 ——
路网本身是凭空造的占位锚点（见 `build_network.py` 的口径）。

**为什么不直接用 `sumo-gui` 截图**：那是**单 3**的活（要 XQuartz，本机还没装）。
本脚本是**画**，不是截 —— 两者不能互相替代，README 里会写清这层区别。

用法：
  python3 draw_network.py                 # 两版都出，写进 figures/
  python3 draw_network.py --light-only
"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
NET = HERE / "network" / "demo_y.net.xml"
FIG_DIR = HERE / "figures"

#: 画布与留白
W, H, PAD = 1400, 900, 110

THEMES = {
    "dark": {"bg": (17, 24, 39), "edge": (96, 165, 250), "node": (248, 113, 113),
             "text": (226, 232, 240), "sub": (148, 163, 184), "title": "Y 型演示路网 · 深色演示版"},
    "light": {"bg": (255, 255, 255), "edge": (37, 99, 235), "node": (220, 38, 38),
              "text": (15, 23, 42), "sub": (100, 116, 139), "title": "Y 型演示路网 · 打印版"},
}


def font(size: int):
    for name in ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                 "/System/Library/Fonts/Helvetica.ttc",
                 "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if Path(name).is_file():
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
    return ImageFont.load_default()


def read_net() -> tuple[dict[str, tuple[float, float]], list[tuple[str, str, str, int, float]]]:
    root = ET.parse(NET).getroot()
    nodes = {}
    for j in root.findall("junction"):
        if j.get("type") == "internal":
            continue
        nodes[j.get("id")] = (float(j.get("x")), float(j.get("y")))
    edges = []
    for e in root.findall("edge"):
        if e.get("id", "").startswith(":"):        # 内部连接边不画
            continue
        lanes = e.findall("lane")
        speed = float(lanes[0].get("speed", 0)) if lanes else 0.0
        edges.append((e.get("id"), e.get("from"), e.get("to"), len(lanes), speed))
    return nodes, edges


def draw(theme_name: str) -> Path:
    theme = THEMES[theme_name]
    nodes, edges = read_net()
    xs = [p[0] for p in nodes.values()]
    ys = [p[1] for p in nodes.values()]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)

    def to_px(x: float, y: float) -> tuple[float, float]:
        sx = (W - 2 * PAD) / max(maxx - minx, 1)
        sy = (H - 2 * PAD) / max(maxy - miny, 1)
        return (PAD + (x - minx) * sx, H - PAD - (y - miny) * sy)

    img = Image.new("RGB", (W, H), theme["bg"])
    d = ImageDraw.Draw(img)
    f_title, f_node, f_edge = font(30), font(20), font(17)

    d.text((PAD, 34), theme["title"], fill=theme["text"], font=f_title)
    d.text((PAD, 76), "凭空造的示意路网（占位锚点，不做地理配准）·  双向路段画成两条平行线",
           fill=theme["sub"], font=f_edge)

    # 边：按方向错开 6px，双向就看得出是两条
    for eid, src, dst, lanes, speed in edges:
        p1, p2 = to_px(*nodes[src]), to_px(*nodes[dst])
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        n = (dx * dx + dy * dy) ** 0.5 or 1
        ox, oy = -dy / n * 6, dx / n * 6
        width = max(2, lanes * 2)
        d.line([(p1[0] + ox, p1[1] + oy), (p2[0] + ox, p2[1] + oy)],
               fill=theme["edge"], width=width)
        mx, my = (p1[0] + p2[0]) / 2 + ox * 2.2, (p1[1] + p2[1]) / 2 + oy * 2.2
        d.text((mx, my), f"{eid}\n{lanes}车道 {speed * 3.6:.0f}km/h",
               fill=theme["sub"], font=f_edge, anchor="mm")

    # 节点
    for nid, (x, y) in nodes.items():
        px, py = to_px(x, y)
        r = 10
        d.ellipse([px - r, py - r, px + r, py + r], fill=theme["node"])
        d.text((px, py - 26), nid, fill=theme["text"], font=f_node, anchor="mm")

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / f"demo_y_{theme_name}.png"
    img.save(out)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="读 net.xml → 画线路图 PNG")
    parser.add_argument("--light-only", action="store_true", help="只出打印版")
    ns = parser.parse_args(argv)
    if not NET.is_file():
        raise SystemExit(f"没有路网：{NET}\n  先跑：python3 build_network.py")

    names = ["light"] if ns.light_only else ["dark", "light"]
    for name in names:
        out = draw(name)
        print(f"[draw_network] 已生成 {out.relative_to(HERE)}（{out.stat().st_size / 1024:.0f} KB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
