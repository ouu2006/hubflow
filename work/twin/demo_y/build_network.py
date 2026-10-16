#!/usr/bin/env python3
"""Y 型演示路网：自绘 NODES / EDGES / CONNS → `netconvert` → `.net.xml`（可一键重建）。

**这是什么**：一个**凭空造的示意路网**（不是真实地点、不做地理配准），形状是一个 **Y**——
一条主干 + 在交汇点分出的两条臂。用来把「路网 → 导入 SUMO → 场景跑通」这条链立起来。

**产物分层**（按仓库口径）：
  - `network/demo_y.nod.xml` / `.edg.xml` / `.con.xml` —— 手写侧输入，**小文本，可入库**；
  - `network/demo_y.net.xml` —— `netconvert` 产物，**小文本，可入库**；
  - `fcd.xml` / `tripinfo.xml` / 动画 —— **几十 MB 的大件，不进仓库**，跑场景时按需生成。

**两条硬纪律**：
  1. **脚本里不得出现任何盘符或本机绝对路径** —— SUMO 位置一律读环境变量 `SUMO_HOME`，
     缺失时给**可操作的报错**，不静默失败；
  2. **可一键重建** —— 删掉 `network/` 再跑本脚本，产物应能重新生成。

用法：
  export SUMO_HOME=/path/to/sumo          # 必填
  python3 build_network.py                # 建网（幂等，可重跑）
  python3 build_network.py --clean        # 先删产物再建（验证"一键重建"）
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from sumo_common import sanitize_net, sumo_binary

HERE = Path(__file__).resolve().parent
NET_DIR = HERE / "network"

#: Y 型的几何（占位锚点，米制局部坐标；**不做地理配准**）
#:   n_stem ──── n_junction ──┬── n_arm_a
#:                            └── n_arm_b
NODES = [
    ("n_stem", 0.0, 0.0, "priority"),
    ("n_junction", 500.0, 0.0, "priority"),
    ("n_arm_a", 900.0, 300.0, "priority"),
    ("n_arm_b", 900.0, -300.0, "priority"),
]

#: 边：主干 2 车道、两条臂各 2 车道；每段都双向（`_in` 进 / `_out` 出，便于场景用同一张网跑双向车流）
#:   (id, from, to, 车道数, 限速 km/h)
EDGES = [
    ("e_stem_in", "n_stem", "n_junction", 2, 60),
    ("e_stem_out", "n_junction", "n_stem", 2, 60),
    ("e_arm_a_in", "n_junction", "n_arm_a", 2, 50),
    ("e_arm_a_out", "n_arm_a", "n_junction", 2, 50),
    ("e_arm_b_in", "n_junction", "n_arm_b", 2, 50),
    ("e_arm_b_out", "n_arm_b", "n_junction", 2, 50),
]

#: 交汇点的转向（`from` 的末段 → `to` 的首段）。三岔口：主干进来可以拐向任一条臂，两条臂都汇回主干。
CONNECTIONS = [
    ("e_stem_in", "e_arm_a_in"),
    ("e_stem_in", "e_arm_b_in"),
    ("e_arm_a_out", "e_stem_out"),
    ("e_arm_b_out", "e_stem_out"),
]


def _write_xml(path: Path, root_tag: str, children: list[tuple[str, dict[str, str]]]) -> None:
    root = ET.Element(root_tag)
    for tag, attrs in children:
        ET.SubElement(root, tag, attrs)
    ET.indent(root, space="    ")
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n",
        encoding="utf-8",
    )


def build_inputs() -> dict[str, Path]:
    """写出 `.nod.xml` / `.edg.xml` / `.con.xml` 三个手写侧输入。"""
    NET_DIR.mkdir(parents=True, exist_ok=True)
    nod = NET_DIR / "demo_y.nod.xml"
    edg = NET_DIR / "demo_y.edg.xml"
    con = NET_DIR / "demo_y.con.xml"

    _write_xml(nod, "nodes", [
        ("node", {"id": nid, "x": f"{x:.2f}", "y": f"{y:.2f}", "type": ntype})
        for nid, x, y, ntype in NODES
    ])
    _write_xml(edg, "edges", [
        ("edge", {
            "id": eid, "from": src, "to": dst,
            "numLanes": str(lanes), "speed": f"{speed_kmh / 3.6:.2f}",
        })
        for eid, src, dst, lanes, speed_kmh in EDGES
    ])
    _write_xml(con, "connections", [
        ("connection", {"from": edge_from, "to": edge_to})
        for edge_from, edge_to in CONNECTIONS
    ])
    return {"nod": nod, "edg": edg, "con": con}


def build_net(inputs: dict[str, Path]) -> Path:
    """调 `netconvert` 出 `.net.xml`；非 0 退出即报错，并检查产物真的落盘。"""
    net = NET_DIR / "demo_y.net.xml"
    cmd = [
        sumo_binary("netconvert"),
        "--node-files", str(inputs["nod"]),
        "--edge-files", str(inputs["edg"]),
        "--connection-files", str(inputs["con"]),
        "-o", str(net),
    ]
    print("[build_network] " + " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    tail = (result.stdout or "").strip().splitlines()
    for line in tail[-6:]:
        print(f"[netconvert] {line}")
    if result.returncode != 0:
        print("[netconvert] stderr 尾部：", file=sys.stderr)
        for line in (result.stderr or "").strip().splitlines()[-10:]:
            print(f"    {line}", file=sys.stderr)
        raise SystemExit(f"netconvert 退出码 {result.returncode}")
    if not net.is_file() or net.stat().st_size <= 0:
        raise SystemExit(f"产物未生成或为空：{net}")
    if "Success" not in (result.stdout or ""):
        raise SystemExit("netconvert 没报 Success —— 不认这次结果")
    return net


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Y 型演示路网：自绘 xml → netconvert → .net.xml")
    parser.add_argument("--clean", action="store_true", help="先删掉 network/ 再建（验证一键重建）")
    parser.add_argument("--keep-timestamp", action="store_true",
                        help="保留 netconvert 的生成时间戳（默认抹掉，好让重跑无 diff）")
    ns = parser.parse_args(argv)

    if ns.clean and NET_DIR.exists():
        shutil.rmtree(NET_DIR)
        print(f"[build_network] 已删除 {NET_DIR}")

    inputs = build_inputs()
    net = build_net(inputs)
    if not ns.keep_timestamp:
        sanitize_net(net)

    print(f"[build_network] 节点 {len(NODES)} 个 / 边 {len(EDGES)} 条 / 转向 {len(CONNECTIONS)} 条")
    print(f"[build_network] 已生成 {net.name}（{net.stat().st_size} 字节）")
    print("[build_network] 形状：n_stem ── n_junction ─┬─ n_arm_a / └─ n_arm_b（Y 型，双向，共 6 段）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
