#!/usr/bin/env python3
"""抓 `sumo-gui` 的一帧 —— 单 3「SUMO 真实画面接大屏」的**技术可行性验证**。

**验证什么**：用 TraCI 驱动 `sumo-gui`，把**渲染出来的画面**存成图片。这是单 3 的命门 ——
单 3 交付的是**像素**（`sumo-gui` 窗口里那幅图），**不是** SVG 重画。

## 本机实测出来的四条（**坑都在这儿，别再踩**）

| # | 踩到什么 | 结论 |
|---|---|---|
| 1 | macOS 上 `sumo-gui` 链的是 **`libFOX` + `libX11`**，是 **X11 程序** | **必须装 XQuartz**（`brew install --cask xquartz`），否则 `FXApp::openDisplay: unable to open display :0.0`。装完 `open -a XQuartz` 即可，**实测不用注销重登**；然后 `export DISPLAY=:0` |
| 2 | TraCI 握手**超时 40 s**，卡在 `getVersion` | ⭐ **必须给 `sumo-gui` 加 `--start`**。GUI 模式默认**等你点界面上那个"播放"按钮**才动 —— 不加 `--start`，它端口在 LISTEN，但第一个命令就没回音 |
| 3 | `Fontconfig error: Cannot load default config file` | XQuartz 的 `fonts.conf` 在 `/opt/X11/etc/X11/fontconfig/`，标准位置没有。**把 `FONTCONFIG_PATH` 指过去**（不指也能出画面，但日志一直刷这条） |
| 4 | `traci.close()` **永远不返回** | GUI 进程不退出，`close()` 会一直等 → 用 `os._exit(0)` 收尾 |

**另两条（issue 里记的，本次一并复现）**：
  - `traci.gui.screenshot` **只是"登记一次请求"，必须再走一次 `simulationStep` 文件才落盘** ——
    少这一步就得到"命令成功、文件没有"的假通过；
  - 取景只能靠 `gui.setBoundary`（`gui-settings-file` 里的 `<viewport>` 会被载入的路网覆盖）。

## 非空白判据（**用几何，不用数颜色**）

`work/assembly/技术栈.md` 里那条「458 种颜色」是**在一张 OSM 大网上**量的（街名文字抗锯齿会产生几百种颜色）。
**本 Y 网只有 4 个节点 / 6 条边，实测只有 5 种颜色** —— 拿"颜色种数 ≥ 30"当门槛会**误判成空白**。

改用**几何判据**：非白像素占比 + 非白像素包围盒的跨度。实测：

| 图 | 非白占比 | 非白包围盒跨度 | 判定 |
|---|---|---|---|
| 真画面（本 Y 网，1390×714） | 1.8% | 1136×651（≈82%×91%） | ✅ 是路网 |
| 窗口还没画出来（590×156） | — | 很窄 | ❌ |

用法：
  export SUMO_HOME=/path/to/sumo          # 该目录下应有 bin/ 与 tools/
  export DISPLAY=:0                        # XQuartz 起好之后
  python3 capture_screen.py                # 抓一帧，打印判据结果
  python3 capture_screen.py --warmup 200 --delay 150
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NET = HERE / "network" / "demo_y.net.xml"
CFG = HERE / "sim" / "demo_y.sumocfg"
SHOT_DIR = HERE / "out" / "shots"

#: 非白像素占比下限 —— 一张真画面至少占这么多
MIN_NONWHITE_RATIO = 0.005
#: 非白像素包围盒跨度下限（占画布宽/高的比例）—— 空白图过不了这条
MIN_BBOX_SPAN = 0.5
#: 取景范围：路网 convBoundary 是 0,0 → 900,600，四周留点余量
BOUNDARY = (-60.0, -60.0, 960.0, 660.0)


def sumo_gui_binary() -> str:
    from sumo_common import sumo_binary
    return sumo_binary("sumo-gui")


def analyze(path: Path) -> dict:
    """量一帧：尺寸、非白像素占比、非白像素包围盒跨度。

    **全走 PIL 的 C 实现**（`getcolors` / `ImageChops.getbbox`）—— 逐像素 Python 循环在
    1390×714 上要几十秒，慢到能把整个脚本拖死。
    """
    from PIL import Image, ImageChops

    with Image.open(path) as img:
        rgb = img.convert("RGB")
        w, h = rgb.size
        white = Image.new("RGB", (w, h), (255, 255, 255))
        bbox = ImageChops.difference(rgb, white).getbbox()
        colors = rgb.getcolors(maxcolors=1 << 24) or []
    nonwhite = sum(count for count, col in colors if col != (255, 255, 255))
    if not bbox or nonwhite == 0:
        return {"size": (w, h), "ratio": 0.0, "span_x": 0.0, "span_y": 0.0, "colors": len(colors)}
    x0, y0, x1, y1 = bbox
    return {
        "size": (w, h),
        "ratio": nonwhite / (w * h),
        "span_x": (x1 - x0) / w,
        "span_y": (y1 - y0) / h,
        "colors": len(colors),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抓 sumo-gui 的一帧（单 3 可行性验证）")
    parser.add_argument("--out", default=str(SHOT_DIR / "frame.png"), dest="out")
    parser.add_argument("--delay", type=int, default=100, help="GUI 每步延时 ms（0 易截到全白）")
    parser.add_argument("--warmup", type=int, default=120, help="先空推几步让画面真的画出来")
    parser.add_argument("--window-size", default="1400,900", dest="window_size")
    ns = parser.parse_args(argv)

    if not NET.is_file() or not CFG.is_file():
        raise SystemExit(f"缺路网或场景：{NET} / {CFG}\n  先跑 build_network.py 与 build_scenario.py")
    if not os.environ.get("DISPLAY"):
        raise SystemExit(
            "没设 DISPLAY —— `sumo-gui` 在 macOS 上是 **X11 程序**，要 XQuartz：\n"
            "  brew install --cask xquartz && open -a XQuartz && export DISPLAY=:0"
        )

    import traci  # 需要 $SUMO_HOME/tools 在 PYTHONPATH 上

    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    sumo_home = os.environ.get("SUMO_HOME", "")
    os.environ["PATH"] = f"{sumo_home}/bin:" + os.environ.get("PATH", "")
    os.environ.setdefault("FONTCONFIG_PATH", "/opt/X11/etc/X11/fontconfig")
    os.chdir(HERE / "sim")

    print(f"[capture] 启动 sumo-gui（delay={ns.delay}ms, warmup={ns.warmup} 步）")
    # ⭐ `--start` 是**必须的**：不加它 GUI 等你在界面上点"播放"，TraCI 连上了端口也不回话
    traci.start([
        sumo_gui_binary(), "-c", CFG.name,
        "--delay", str(ns.delay), "--start",
        "--window-size", ns.window_size,
    ])

    views = [v for v in traci.gui.getIDList() if v.startswith("View")]
    if not views:
        raise SystemExit("找不到 gui view —— sumo-gui 没起来？")
    view = views[0]

    traci.gui.setBoundary(view, *BOUNDARY)
    for i in range(ns.warmup):
        traci.simulationStep()
        if (i + 1) % 40 == 0:
            print(f"[capture]   {i + 1} 步  t={traci.simulation.getTime():.0f}s  "
                  f"车={len(traci.vehicle.getIDList())}")

    traci.gui.screenshot(view, str(out))
    traci.simulationStep()   # ⭐ 关键：不 step，文件不落盘

    if not out.is_file() or out.stat().st_size <= 0:
        raise SystemExit(
            f"❌ 截图没落盘：{out}\n"
            f"   典型原因：`gui.screenshot` 之后**没有**再走一次 `simulationStep`"
        )

    stats = analyze(out)
    w, h = stats["size"]
    print(f"[capture] 产物 {out.name}：{w}×{h}，{out.stat().st_size / 1024:.1f} KB")
    print(f"[capture] 非白占比 {stats['ratio'] * 100:.2f}%"
          f"｜非白包围盒跨度 {stats['span_x'] * 100:.0f}%×{stats['span_y'] * 100:.0f}%")

    if stats["ratio"] < MIN_NONWHITE_RATIO or max(stats["span_x"], stats["span_y"]) < MIN_BBOX_SPAN:
        raise SystemExit(
            f"❌ 判为空白 / 未渲染（非白占比 {stats['ratio'] * 100:.2f}%，"
            f"包围盒跨度 {max(stats['span_x'], stats['span_y']) * 100:.0f}%）"
            f"—— 加大 --warmup / --delay 再试"
        )
    print("✅ 非空白，且是**路网画面**（不是窗口占位）—— sumo-gui 的真实像素拿到手了")

    # ⚠️ 不要调 traci.close()：GUI 进程不退出，close() 会一直等下去。直接走人。
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
