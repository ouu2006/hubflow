#!/usr/bin/env python3
"""Y 型演示场景：出车流 → `duarouter` 不需要（路线直接写死）→ 跑 SUMO → FCD / tripinfo。

**场景怎么设计的**：Y 型路网共 4 条通行路线，车流按 `--demand-scale` 倍率放大：
  主干 → 臂 A ／ 主干 → 臂 B ／ 臂 A → 主干 ／ 臂 B → 主干
（臂 A ↔ 臂 B 之间要穿过交汇点，本演示不设这条转向，免得把三岔口变成四岔口。）

**产物分层**：
  - `sim/demo_y.rou.xml` / `sim/demo_y.sumocfg` —— 场景输入，**小文本，可入库**；
  - `out/fcd.xml` / `out/tripinfo.xml` —— **几十 MB 的大件，不进仓库**（`.gitignore` 拦 `out/`）。

**可复现**：随机种子写进 `sumocfg` 的 `<random_number><seed>`（**不读系统时间**），
同一份输入连跑两遍，`tripinfo` 应逐字节一致。

用法：
  export SUMO_HOME=/path/to/sumo
  python3 build_scenario.py                     # 默认倍率 1
  python3 build_scenario.py --demand-scale 5    # 峰值工况
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from sumo_common import normalize_artifacts, sumo_binary

HERE = Path(__file__).resolve().parent
NET = HERE / "network" / "demo_y.net.xml"
SIM_DIR = HERE / "sim"
OUT_DIR = HERE / "out"

#: 固定随机种子（**写进场景输入文件**，不读系统时间）—— 同一输入跑两遍必须一致
SEED = 42

#: 仿真区间（秒）
BEGIN, END = 0, 600

#: 四类车流：车流 id、路线 id、基础发车率（辆/小时）—— 车型在 `vType id="car"` 里统一给，不随车流变
FLOWS = [
    ("flow_stem_to_a", "r_stem_to_a", 600),
    ("flow_stem_to_b", "r_stem_to_b", 600),
    ("flow_a_to_stem", "r_a_to_stem", 400),
    ("flow_b_to_stem", "r_b_to_stem", 400),
]

ROUTES = [
    ("r_stem_to_a", "e_stem_in e_arm_a_in"),
    ("r_stem_to_b", "e_stem_in e_arm_b_in"),
    ("r_a_to_stem", "e_arm_a_out e_stem_out"),
    ("r_b_to_stem", "e_arm_b_out e_stem_out"),
]


def _write(path: Path, root_tag: str, children: list[tuple[str, dict[str, str]]]) -> None:
    root = ET.Element(root_tag)
    for tag, attrs in children:
        ET.SubElement(root, tag, attrs)
    ET.indent(root, space="    ")
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n",
        encoding="utf-8",
    )


def write_inputs(demand_scale: float) -> tuple[Path, Path]:
    """写 `rou.xml` 与 `sumocfg`（把种子、起止时间、输入输出全写死在文件里）。"""
    SIM_DIR.mkdir(parents=True, exist_ok=True)
    rou = SIM_DIR / "demo_y.rou.xml"
    cfg = SIM_DIR / "demo_y.sumocfg"

    veh_per_hour = lambda base: round(base * demand_scale)  # noqa: E731
    root = ET.Element("routes")
    ET.SubElement(root, "vType", {
        "id": "car", "vClass": "passenger", "accel": "2.6", "decel": "4.5",
        "length": "5", "minGap": "2.5", "maxSpeed": "16.67",
    })
    for rid, edges in ROUTES:
        ET.SubElement(root, "route", {"id": rid, "edges": edges})
    for fid, rid, base in FLOWS:
        ET.SubElement(root, "flow", {
            "id": fid, "route": rid, "begin": str(BEGIN), "end": str(END),
            "vehsPerHour": str(veh_per_hour(base)),
        })
    ET.indent(root, space="    ")
    rou.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n",
                   encoding="utf-8")

    # sumocfg 的形状是 `<section><option value="..."/></section>` —— 选项是**子元素**，不是 section 的属性
    cfg_root = ET.Element("configuration")
    sections = [
        ("input", [
            ("net-file", f"../network/{NET.name}"),
            ("route-files", rou.name),
        ]),
        ("time", [("begin", str(BEGIN)), ("end", str(END))]),
        ("processing", [("time-to-teleport", "-1")]),
        ("random_number", [("seed", str(SEED))]),
        ("output", [
            ("fcd-output", "../out/fcd.xml"),
            ("tripinfo-output", "../out/tripinfo.xml"),
        ]),
        ("report", [("no-step-log", "true"), ("duration-log.statistics", "true")]),
    ]
    for section_name, options in sections:
        section = ET.SubElement(cfg_root, section_name)
        for name, value in options:
            ET.SubElement(section, name, {"value": value})
    ET.indent(cfg_root, space="    ")
    cfg.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(cfg_root, encoding="unicode") + "\n",
                   encoding="utf-8")
    return rou, cfg


def run_sumo(cfg: Path) -> str:
    """跑 SUMO（工作目录设在 `sim/`，好让 cfg 里的相对路径成立）。非 0 退出即报错。"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [sumo_binary("sumo"), "-c", cfg.name]
    print(f"[build_scenario] cd {SIM_DIR} && " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(SIM_DIR), capture_output=True, text=True, check=False)
    out = (result.stdout or "")
    for line in out.strip().splitlines()[-8:]:
        print(f"[sumo] {line}")
    if result.returncode != 0:
        for line in (result.stderr or "").strip().splitlines()[-10:]:
            print(f"    {line}", file=sys.stderr)
        raise SystemExit(f"sumo 退出码 {result.returncode}")
    return out


def check_artifacts() -> dict[str, int]:
    """产物存在性断言：**不能只查"非空"** —— tripinfo 还必须有收尾标签（半成品就是缺它）。"""
    sizes: dict[str, int] = {}
    for name in ("fcd.xml", "tripinfo.xml"):
        path = OUT_DIR / name
        if not path.is_file():
            raise SystemExit(f"产物不存在：{path}")
        size = path.stat().st_size
        if size <= 0:
            raise SystemExit(f"产物为空：{path}")
        sizes[name] = size
    tail = (OUT_DIR / "tripinfo.xml").read_text(encoding="utf-8").rstrip()
    if not tail.endswith("</tripinfos>"):
        raise SystemExit("tripinfo.xml 没有收尾标签 —— 这是**跑到一半被中断的半成品**，不认这次结果")
    return sizes


def trip_stats() -> dict[str, float]:
    """从 tripinfo 里折出行程数、平均行程时间、平均等待时间。"""
    tree = ET.parse(OUT_DIR / "tripinfo.xml")
    trips = tree.getroot().findall("tripinfo")
    if not trips:
        raise SystemExit("tripinfo 里一条 trip 都没有 —— 场景没跑出车")
    n = len(trips)
    dur = sum(float(t.get("duration", 0)) for t in trips)
    wait = sum(float(t.get("waitingTime", 0)) for t in trips)
    return {"trips": n, "avg_duration_s": dur / n, "avg_waiting_s": wait / n}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Y 型演示场景：出车流 → 跑 SUMO → FCD / tripinfo")
    parser.add_argument("--demand-scale", type=float, default=1.0, help="需求倍率（峰值工况常用 5）")
    parser.add_argument("--clean", action="store_true", help="先删 sim/ 与 out/ 再跑")
    parser.add_argument("--keep-timestamp", action="store_true",
                        help="保留 SUMO 写进产物头的生成时间戳（默认抹掉，好让重跑无 diff）")
    ns = parser.parse_args(argv)

    if not NET.is_file():
        raise SystemExit(f"没有路网：{NET}\n  先跑：python3 build_network.py")
    if ns.clean:
        for d in (SIM_DIR, OUT_DIR):
            if d.exists():
                shutil.rmtree(d)
                print(f"[build_scenario] 已删除 {d}")

    rou, cfg = write_inputs(ns.demand_scale)
    print(f"[build_scenario] 已生成 {rou.name} / {cfg.name}（种子 seed={SEED}，区间 {BEGIN}–{END}s）")
    run_sumo(cfg)

    sizes = check_artifacts()
    if not ns.keep_timestamp:
        normalize_artifacts([OUT_DIR / "fcd.xml", OUT_DIR / "tripinfo.xml"])
    stats = trip_stats()
    for name, size in sizes.items():
        print(f"[build_scenario] {name}: {size / 1024 / 1024:.2f} MB")
    print(f"[build_scenario] 行程 {stats['trips']} 次 | 平均行程 {stats['avg_duration_s']:.1f}s | "
          f"平均等待 {stats['avg_waiting_s']:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
