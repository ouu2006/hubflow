#!/usr/bin/env python3
"""抓 `sumo-gui` 的一帧 —— 单 3「SUMO 真实画面接大屏」的**技术可行性验证**。

**验证什么**：这台机器上，用 TraCI 驱动 `sumo-gui`，能不能把**渲染出来的画面**存成图片。
这是单 3 的命门 —— 单 3 交付的是**像素**（`sumo-gui` 窗口里那幅图），不是 SVG 重画。

**三条已知坑**（先在别的机器上踩过，本脚本要把它们在这台机器上重crash一遍）：
  1. **`traci.gui.screenshot` 只是「登记一次请求」，必须再走一次 `simulationStep` 文件才落盘**
     —— 少这一步就得到"命令成功、文件没有"的假通过；
  2. `gui-settings-file` 里的 `<viewport>` 在较新 SUMO 上会被载入的路网覆盖，
     程序化取景**只能靠 `gui.setBoundary`**；
  3. `--delay 0` 可能截到全白 —— 因此**不能用"文件存在"当判据**，要数颜色。

**非空白判据**（沿用 `work/assembly/技术栈.md` 的既有口径）：**颜色种数要够多**。
一张全白/全黑图只有 1 种颜色；真实路网画面有几百种。

用法：
  export SUMO_HOME=/path/to/sumo
  python3 capture_screen.py                 # 抓一帧，打印判据结果
  python3 capture_screen.py --out shot.png
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
NET = HERE / "network" / "demo_y.net.xml"
CFG = HERE / "sim" / "demo_y.sumocfg"
SHOT_DIR = HERE / "out" / "shots"

#: 「非空白」的最低颜色种数门槛。全白/全黑 = 1 种；真实路网画面实测几百种。
MIN_COLORS = 30

#: `sumo-gui` 起来后先空推几步，让画面有东西可看再截
WARMUP_STEPS = 40


def sumo_gui_binary() -> str:
    from sumo_common import sumo_binary
    return sumo_binary("sumo-gui")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抓 sumo-gui 的一帧（单 3 可行性验证）")
    parser.add_argument("--out", default=str(SHOT_DIR / "frame.png"), dest="out")
    parser.add_argument("--delay", type=int, default=50, help="GUI 每步延时 ms（0 易截到全白）")
    ns = parser.parse_args(argv)

    if not NET.is_file() or not CFG.is_file():
        raise SystemExit(f"缺路网或场景：{NET} / {CFG}\n  先跑 build_network.py 与 build_scenario.py")

    import traci  # 需要 $SUMO_HOME/tools 在 PYTHONPATH 上

    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    sumo_home = os.environ.get("SUMO_HOME", "")
    os.environ["PATH"] = f"{sumo_home}/bin:" + os.environ.get("PATH", "")

    # traci.start 没有 cwd 参数 —— 自己切到 sim/，好让 cfg 里的相对路径成立
    os.chdir(HERE / "sim")

    print(f"[capture] 启动 sumo-gui（delay={ns.delay}ms，工作目录 sim/）")
    traci.start([sumo_gui_binary(), "-c", CFG.name, "--delay", str(ns.delay)])

    # ① 先空推，让画面里真有车、有路网
    for _ in range(WARMUP_STEPS):
        traci.simulationStep()

    views = [v for v in traci.gui.getIDList() if v.startswith("View")]
    if not views:
        raise SystemExit("找不到 gui view —— sumo-gui 没起来？")
    view = views[0]

    # ② 程序化取景：用 setBoundary（gui-settings 里的 viewport 会被路网覆盖）
    #    取景范围按路网的外接矩形留点余量（路网 convBoundary 是 0,0 → 900,600）
    traci.gui.setBoundary(view, -60.0, -60.0, 960.0, 660.0)
    traci.simulationStep()

    # ③ 登记截图请求
    traci.gui.screenshot(view, str(out))
    # ④ **关键**：再走一步，文件才真的落盘
    traci.simulationStep()
    traci.close()

    if not out.is_file() or out.stat().st_size <= 0:
        raise SystemExit(
            f"❌ 截图没落盘：{out}\n"
            f"   典型原因：`gui.screenshot` 之后**没有**再走一次 `simulationStep`"
        )

    from PIL import Image
    with Image.open(out) as img:
        colors = len(img.convert("RGB").getcolors(maxcolors=1 << 24) or [])
        size = img.size

    print(f"[capture] 产物 {out.name}：{size[0]}×{size[1]}，"
          f"{out.stat().st_size / 1024:.0f} KB，**{colors} 种颜色**")
    if colors < MIN_COLORS:
        raise SystemExit(f"❌ 只有 {colors} 种颜色（门槛 {MIN_COLORS}）—— 这是**空白/纯色图**，不认")
    print(f"✅ 非空白（颜色种数 {colors} ≥ {MIN_COLORS}）—— **sumo-gui 的真实画面拿到手了**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
