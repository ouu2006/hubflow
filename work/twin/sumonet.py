#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""站点 Z 真网（`netpack/network_junction.json`）→ SUMO 路网（plain XML → netconvert）。

## 这是什么

把**真网统一图**（44 节点 / 61 段 `SZ-###`，几何真值来自 OSM 切片）转成 SUMO 能跑的
`station.net.xml`，供 `loop.py` 的**真孪生主循环**（W1）用。整条链路可一键重建，产物在
`work/twin/out/sumo/`（`out/` 已 gitignore，换机重跑即可，不提交 `.net.xml`）。

## 三条硬口径（与 Issue IKNAER / README 第六节一致）

1. **边 id 直接用 `SZ-###`**：与站点包 / 感知 / 引擎同一命名空间；检测器按段号聚合，不另起一套。
   反向补边命名 `SZ-###_rev`（见下），**不新增段号**，检测器把它并回同一个 `SZ-###`。
2. **缺失属性按站点包 defaults 回落并标来源**：`lanes` 缺 → 默认 2 道（标 `default:demo_lanes=2`）；
   `speed_limit` 缺 → 站点包 `thresholds.json` 的 `grading.defaults.v_f_kmh`（标来源路径）。
   车道 / 限速**来源逐条写进 `out/sumo/station_netmeta.json`**，再汇总进 `loop.py` 的 `run_log.json`；
   脚本里**不写死站名 / 段号 / 坐标**（站名、段数、产物路径全部读 `site-ranges.json` 登记表）。
3. **同一输入两次生成 `.net.xml` 逐字节一致**：`netconvert` 每次都会写生成时间戳与本机绝对路径，
   这里在产物上做**只改注释、不改内容**的规整（`_sanitize_net`），否则两遍 sha256 不可能一致。

## 双向补边（为什么必须有）

`network_junction.json` 的 61 段是**有向**的（`from`/`to`），其中 `oneway` 标记只有 22 段是明确的
`yes`，其余 39 段 `null`（OSM 抽不到 tag）。只按有向边建网时，44 节点的有向图连通性极差
（实测只有 4 对互逆段，绝大多数节点不可达）——**车辆无法从边界进、从边界出**，孪生主循环跑不起来。

因此：**`oneway` 明确为 `yes` 的段保持单向；其余段在“反向段已作为独立段号存在”时不重复补，
否则补一条 `SZ-###_rev` 反向边**（方向 = 原段 `to → from`，几何 = 原坐标倒序）。这是 OSM 缺
`oneway` 标记的常规默认（按双向理解），也是 SUMO 路网可连通的前提；**它不是新段号**，
`segments_twin.json` / `twin_timeseries.json` 只输出 61 个 `SZ-###`，反向边并入原段统计。

## 坐标

`network_junction.json` 只给 WGS-84 `lon/lat`（契约明确 `nodes[].x/y` 不输出）。这里用**局部切平面
投影**转米制 `x/y`：锚点 = 全部节点经纬度均值（**从数据派生，不写死站点坐标**），
半径用 WGS-84 长半轴；500 m 范围内几何误差可忽略。反变换 `xy_to_lonlat()` 供
`vehicles.json` 把车辆位置反算回 WGS-84。

## 用法

```text
python work/twin/sumonet.py                              # 默认建到 work/twin/out/sumo/station.net.xml
python work/twin/sumonet.py --out-dir <目录>             # 换输出目录（仍然 station.net.xml）
python work/twin/sumonet.py --keep-timestamps            # 不规整 netconvert 时间戳（仅调试用）
python work/twin/sumonet.py --sumo-net <已有.net.xml>    # 只校验/复用已有网，不重建
```

`loop.py --duration ...` 真路径会先调本模块建网（或复用 `--sumo-net` 指定网），再起 TraCI。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import site_config

#: 本文件位于 work/twin/ → 仓库根是 parents[1]
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
DEFAULT_OUT_DIR = HERE / "out" / "sumo"
DEFAULT_NET_NAME = "station.net.xml"

#: 反向补边后缀（不是段号命名空间的一部分；检测器并回原段）
REVERSE_SUFFIX = "_rev"

#: `lanes` 缺值时的默认车道数（演示值，来源写进 netmeta）
DEFAULT_LANES = 2
LANES_SOURCE_DEFAULT = f"default:demo_lanes={DEFAULT_LANES}"

#: 明确单向的 oneway 取值（OSM tag）
ONEWAY_VALUES = {"yes", "true", "1", "-1"}

#: 生成时间戳（netconvert 每次都会写）
_GENERATED_ON = re.compile(r"<!-- generated on [^ ]+ by ")
#: netconvert 回显的选项块（含本机绝对路径；只是选项回显，运行时不读）
_CONFIGURE_BLOCK = re.compile(
    r"\n[ \t]*<netconvertConfiguration\b.*?</netconvertConfiguration>[ \t]*\n", re.S
)

#: netconvert 参数（写进脚本，不许手点）。
#: 1.28 没有 `--connections.guess`（给了连接文件才用，不给则 netconvert 自动按几何猜连接）；
#: 双向补边已经让每个节点有“对向边”，这里只关掉掉头连接（防止车辆在路段中间掉头）。
#: `--junctions.join` / `--tls.guess` 本来就是默认关，不重复传（1.28 传了反而解析歧义）。
NETCONVERT_ARGS = ("--no-turnarounds",)


def read_json(path: Path) -> dict[str, Any]:
    """读一个 UTF-8 JSON 文件（显式编码，换机器不乱码）。"""
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def write_json(path: Path, payload: dict[str, Any]) -> int:
    """写一个 UTF-8 JSON 文件（中文不转义），返回字节数。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return len(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    """文件 sha256（小写十六进制）。"""
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_rel(path: Path) -> str:
    """尽量给仓库相对路径（日志可追溯）；不在仓库内给绝对路径。"""
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


# ---------------------------------------------------------------- 站点/真网定位


def load_network(
    site_id: str | None = None,
    site_ranges_path: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    """按站点范围登记表定位真网产物：返回 `(site, network_payload, network_path)`。

    站名 / 段数 / 段号前缀 / 产物路径**全部来自登记表**，本模块不写死任何站名或坐标。
    """
    site = site_config.load_site(site_id, site_ranges_path)
    network_path = site_config.repo_path(str(site["out_json"]))
    if not network_path.is_file():
        raise SystemExit(f"缺真网产物：{network_path}（先按 netpack/README.md 建真网）")
    payload = read_json(network_path)
    validate_network(payload, site, network_path)
    return site, payload, network_path


def validate_network(
    payload: dict[str, Any], site: dict[str, Any], network_path: Path
) -> None:
    """校验真网产物最低结构（缺字段 / 自相矛盾一律报错，不静默补）。"""
    nodes = payload.get("nodes")
    edges = payload.get("edges")
    if not isinstance(nodes, list) or not nodes:
        raise SystemExit(f"真网产物 {network_path} 缺非空 nodes 数组")
    if not isinstance(edges, list) or not edges:
        raise SystemExit(f"真网产物 {network_path} 缺非空 edges 数组")
    seg_target = int(site["seg_target"])
    if len(edges) != seg_target:
        raise SystemExit(
            f"真网段数 {len(edges)} ≠ 登记表 seg_target={seg_target}"
            f"（{site.get('site_id')}）：不在不完整路网上建 SUMO 网"
        )
    node_ids: set[str] = set()
    for node in nodes:
        node_id = str(node.get("node_id") or node.get("id") or "")
        if not node_id:
            raise SystemExit(f"真网产物 {network_path} 的 nodes[] 里有节点缺 id")
        if node_id in node_ids:
            raise SystemExit(f"真网产物 {network_path} 的节点 id 重复：{node_id}")
        node_ids.add(node_id)
        if not isinstance(node.get("lon"), (int, float)) or not isinstance(node.get("lat"), (int, float)):
            raise SystemExit(f"节点 {node_id} 缺 WGS-84 lon/lat（几何真值缺失，不编坐标）")
    edge_ids: set[str] = set()
    for edge in edges:
        edge_id = str(edge.get("segment_id") or edge.get("id") or "")
        if not edge_id:
            raise SystemExit(f"真网产物 {network_path} 的 edges[] 里有段缺 id")
        if edge_id in edge_ids:
            raise SystemExit(f"真网产物 {network_path} 的段 id 重复：{edge_id}")
        edge_ids.add(edge_id)
        if str(edge.get("from")) not in node_ids or str(edge.get("to")) not in node_ids:
            raise SystemExit(f"段 {edge_id} 的 from/to 不在 nodes 里（拓扑真值缺失）")
        length = edge.get("length_m")
        if not isinstance(length, (int, float)) or float(length) <= 0:
            raise SystemExit(f"段 {edge_id} 缺有效 length_m（几何真值缺失，不编长度）")


# ---------------------------------------------------------------- 局部投影


def make_projection(nodes: list[dict[str, Any]]) -> dict[str, float]:
    """由全部节点经纬度均值派生切平面锚点（**不写死站点坐标**）。"""
    lons = [float(node["lon"]) for node in nodes]
    lats = [float(node["lat"]) for node in nodes]
    # WGS-84 长半轴；500 m 尺度的球面近似误差可忽略
    return {
        "lon0": sum(lons) / len(lons),
        "lat0": sum(lats) / len(lats),
        "r_m": 6378137.0,
    }


def lonlat_to_xy(lon: float, lat: float, proj: dict[str, float]) -> tuple[float, float]:
    """WGS-84 → 局部切平面米制坐标（等距圆柱近似）。"""
    rad = math.pi / 180.0
    x = (float(lon) - proj["lon0"]) * math.cos(proj["lat0"] * rad) * proj["r_m"] * rad
    y = (float(lat) - proj["lat0"]) * proj["r_m"] * rad
    return x, y


def xy_to_lonlat(x: float, y: float, proj: dict[str, float]) -> tuple[float, float]:
    """局部切平面米制坐标 → WGS-84（与 `lonlat_to_xy` 严格互逆）。"""
    rad = math.pi / 180.0
    lon = proj["lon0"] + float(x) / (math.cos(proj["lat0"] * rad) * proj["r_m"] * rad)
    lat = proj["lat0"] + float(y) / (proj["r_m"] * rad)
    return lon, lat


# ---------------------------------------------------------------- 站点包缺省值


def load_station_defaults(stations_dir: Path | str | None = None) -> dict[str, Any]:
    """读站点包 `thresholds.json` 的 `grading.defaults`（限速缺值回落用）。"""
    path = Path(stations_dir or (REPO_ROOT / "stations")) / "thresholds.json"
    if not path.is_file():
        raise SystemExit(f"缺站点包 {path}（限速缺值必须按站点包 defaults 回落，不写死）")
    payload = read_json(path)
    grading = payload.get("grading") or {}
    defaults = grading.get("defaults") or {}
    v_f = defaults.get("v_f_kmh")
    if not isinstance(v_f, (int, float)) or float(v_f) <= 0:
        raise SystemExit(
            "站点包 thresholds.json 的 grading.defaults.v_f_kmh 缺失/非正："
            "真网 61 段 speed_limit 全为 null，没有限速可回落"
        )
    return {
        "v_f_kmh": float(v_f),
        "v_f_source": "station_pack:thresholds.grading.defaults.v_f_kmh",
        "path": repo_rel(path),
    }


# ---------------------------------------------------------------- plain XML 生成


def _write_xml(path: Path, root_tag: str, children: list[tuple[str, dict[str, str]]]) -> int:
    """写 SUMO plain XML（固定缩进 / 固定标签顺序 → 逐字节可复现）。"""
    root = ET.Element(root_tag)
    for tag, attrs in children:
        ET.SubElement(root, tag, attrs)
    ET.indent(root, space="    ")
    text = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        root, encoding="unicode"
    ) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return len(text.encode("utf-8"))


def _edge_speed_and_lanes(
    edge: dict[str, Any], defaults: dict[str, Any]
) -> tuple[int, str, float, str]:
    """取 (车道数, 车道来源, 限速 m/s, 限速来源)；缺值按站点包 defaults 并标来源。"""
    lanes = edge.get("lanes")
    if isinstance(lanes, (int, float)) and int(lanes) > 0:
        num_lanes, lanes_source = int(lanes), "network:edges[].lanes"
    else:
        num_lanes, lanes_source = DEFAULT_LANES, LANES_SOURCE_DEFAULT
    speed_limit = edge.get("speed_limit")
    if isinstance(speed_limit, (int, float)) and float(speed_limit) > 0:
        speed_kmh, speed_source = float(speed_limit), "network:edges[].speed_limit"
    else:
        speed_kmh, speed_source = float(defaults["v_f_kmh"]), defaults["v_f_source"]
    return num_lanes, lanes_source, speed_kmh / 3.6, speed_source


def _edge_shape_xy(edge: dict[str, Any], proj: dict[str, float], reverse: bool) -> list[tuple[float, float]]:
    """段几何（WGS-84 coords）→ 米制 shape；reverse=True 时倒序。"""
    coords = edge.get("coords") or []
    if not isinstance(coords, list) or len(coords) < 2:
        raise SystemExit(f"段 {edge.get('segment_id') or edge.get('id')} 缺 >=2 个 coords（几何真值缺失）")
    points = [lonlat_to_xy(pair[0], pair[1], proj) for pair in coords]
    if reverse:
        points.reverse()
    return points


def _fmt(value: float) -> str:
    """米制坐标固定 2 位小数（确定性）。"""
    return f"{value:.2f}"


def build_plain_inputs(
    network: dict[str, Any],
    site: dict[str, Any],
    out_dir: Path,
    defaults: dict[str, Any],
) -> dict[str, Any]:
    """写真网 plain `.nod.xml` / `.edg.xml`，返回路径与逐边元数据。

    - 节点：44 个，边界节点 `type="dead_end"`（让 netconvert 知道这里是尽头），其余 `priority`；
    - 边：61 条 `SZ-###` 正向 + 需要时补 `SZ-###_rev` 反向（规则见模块 docstring）；
    - 属性缺值来源逐条记进 `edge_meta[]`。
    """
    nodes = network["nodes"]
    edges = network["edges"]
    proj = make_projection(nodes)
    node_xy = {
        str(node.get("node_id") or node.get("id")): lonlat_to_xy(node["lon"], node["lat"], proj)
        for node in nodes
    }
    existing_direction = {(str(edge["from"]), str(edge["to"])) for edge in edges}

    node_rows: list[tuple[str, dict[str, str]]] = []
    node_meta: list[dict[str, Any]] = []
    for node in sorted(nodes, key=lambda item: str(item.get("node_id") or item.get("id"))):
        node_id = str(node.get("node_id") or node.get("id"))
        x, y = node_xy[node_id]
        node_type = "dead_end" if node.get("boundary") else "priority"
        node_rows.append(
            ("node", {"id": node_id, "x": _fmt(x), "y": _fmt(y), "type": node_type})
        )
        node_meta.append(
            {
                "node_id": node_id,
                "x": float(_fmt(x)),
                "y": float(_fmt(y)),
                "lon": float(node["lon"]),
                "lat": float(node["lat"]),
                "boundary": bool(node.get("boundary")),
                "netconvert_type": node_type,
            }
        )

    edge_rows: list[tuple[str, dict[str, str]]] = []
    edge_meta: list[dict[str, Any]] = []
    for edge in sorted(edges, key=lambda item: str(item.get("segment_id") or item.get("id"))):
        segment_id = str(edge.get("segment_id") or edge.get("id"))
        from_node, to_node = str(edge["from"]), str(edge["to"])
        num_lanes, lanes_source, speed_ms, speed_source = _edge_speed_and_lanes(edge, defaults)
        shape = _edge_shape_xy(edge, proj, reverse=False)
        edge_rows.append(
            (
                "edge",
                {
                    "id": segment_id,
                    "from": from_node,
                    "to": to_node,
                    "numLanes": str(num_lanes),
                    "speed": f"{speed_ms:.2f}",
                    "shape": " ".join(f"{_fmt(px)},{_fmt(py)}" for px, py in shape),
                },
            )
        )
        edge_meta.append(
            {
                "edge_id": segment_id,
                "segment_id": segment_id,
                "direction": "forward",
                "from": from_node,
                "to": to_node,
                "num_lanes": num_lanes,
                "lanes_source": lanes_source,
                "speed_ms": round(speed_ms, 3),
                "speed_kmh": round(speed_ms * 3.6, 2),
                "speed_source": speed_source,
                "length_m": float(edge["length_m"]),
                "oneway": edge.get("oneway"),
            }
        )
        oneway = str(edge.get("oneway") or "").strip().lower()
        if oneway in ONEWAY_VALUES:
            continue  # 明确单向：不补反向
        if (to_node, from_node) in existing_direction:
            continue  # 反向已作为独立段号存在：不重复补
        reverse_shape = _edge_shape_xy(edge, proj, reverse=True)
        reverse_id = f"{segment_id}{REVERSE_SUFFIX}"
        edge_rows.append(
            (
                "edge",
                {
                    "id": reverse_id,
                    "from": to_node,
                    "to": from_node,
                    "numLanes": str(num_lanes),
                    "speed": f"{speed_ms:.2f}",
                    "shape": " ".join(f"{_fmt(px)},{_fmt(py)}" for px, py in reverse_shape),
                },
            )
        )
        edge_meta.append(
            {
                "edge_id": reverse_id,
                "segment_id": segment_id,
                "direction": "reverse",
                "from": to_node,
                "to": from_node,
                "num_lanes": num_lanes,
                "lanes_source": lanes_source,
                "speed_ms": round(speed_ms, 3),
                "speed_kmh": round(speed_ms * 3.6, 2),
                "speed_source": speed_source,
                "length_m": float(edge["length_m"]),
                "oneway": edge.get("oneway"),
            }
        )

    nod_path = out_dir / "station.nod.xml"
    edg_path = out_dir / "station.edg.xml"
    node_bytes = _write_xml(nod_path, "nodes", node_rows)
    edge_bytes = _write_xml(edg_path, "edges", edge_rows)
    return {
        "proj": proj,
        "nod_path": nod_path,
        "edg_path": edg_path,
        "node_bytes": node_bytes,
        "edge_bytes": edge_bytes,
        "node_meta": node_meta,
        "edge_meta": edge_meta,
        "forward_edges": sum(1 for row in edge_meta if row["direction"] == "forward"),
        "reverse_edges": sum(1 for row in edge_meta if row["direction"] == "reverse"),
    }


# ---------------------------------------------------------------- netconvert


def find_netconvert() -> str:
    """定位 netconvert：先看 PATH，再看 `$SUMO_HOME/bin`；找不到给可操作报错。"""
    found = shutil.which("netconvert")
    if found:
        return found
    sumo_home = os.environ.get("SUMO_HOME")
    if sumo_home:
        for name in ("netconvert", "netconvert.exe"):
            candidate = Path(sumo_home) / "bin" / name
            if candidate.is_file():
                return str(candidate)
    raise SystemExit(
        "找不到 netconvert：请装 SUMO 并设 $SUMO_HOME（README 第三节），"
        "或把 netconvert 放进 PATH；不静默跳过"
    )


def _sanitize_net(path: Path) -> None:
    """抹掉 netconvert 的生成时间戳与本机绝对路径块（只改注释/选项回显，不改路网内容）。

    不规整的话：① 两遍生成的 sha256 永远不同（时间戳）；② 本机绝对路径泄进产物。
    """
    text = path.read_text(encoding="utf-8")
    text, count_ts = _GENERATED_ON.subn("<!-- generated by ", text, count=1)
    text, count_cfg = _CONFIGURE_BLOCK.subn("", text, count=1)
    stripped = text.rstrip() + "\n"
    path.write_text(stripped, encoding="utf-8", newline="\n")
    if not count_ts and not count_cfg:
        print("[sumonet] 注意：.net.xml 里没找到时间戳/配置块，未做规整（不静默失败）")
    else:
        print(
            f"[sumonet] 已规整 .net.xml：时间戳 {int(bool(count_ts))} 处 / "
            f"本机路径块 {int(bool(count_cfg))} 处（只改注释，内容未动）"
        )


def build_net_file(
    plain: dict[str, Any],
    out_net: Path,
    netconvert: str | None = None,
    keep_timestamps: bool = False,
) -> Path:
    """调 `netconvert` 出 `.net.xml`；非 0 退出 / 产物缺失一律报错，不静默降级。"""
    out_net.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        netconvert or find_netconvert(),
        "--node-files",
        str(plain["nod_path"]),
        "--edge-files",
        str(plain["edg_path"]),
        "-o",
        str(out_net),
        *NETCONVERT_ARGS,
    ]
    print("[sumonet] " + " ".join(cmd))
    # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
    # list 参数、shell=False；元素只来自 SUMO 探测结果、本模块生成的本地路径与固定参数元组，
    # 无外部可控输入，不构成注入面。
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    for line in (result.stdout or "").strip().splitlines()[-8:]:
        print(f"[netconvert] {line}")
    if result.returncode != 0:
        for line in (result.stderr or "").strip().splitlines()[-15:]:
            print(f"[netconvert][stderr] {line}")
        raise SystemExit(f"netconvert 退出码 {result.returncode}（stderr 诊断见上）")
    if not out_net.is_file() or out_net.stat().st_size <= 0:
        raise SystemExit(f"路网产物未生成或为空：{out_net}")
    if not keep_timestamps:
        _sanitize_net(out_net)
    return out_net


# ---------------------------------------------------------------- 一站式构建


def build_station_net(
    site_id: str | None = None,
    site_ranges_path: str | Path | None = None,
    stations_dir: Path | str | None = None,
    out_dir: Path | str | None = None,
    netconvert: str | None = None,
    keep_timestamps: bool = False,
) -> dict[str, Any]:
    """真网 → plain XML → netconvert → `.net.xml`，返回可写进 run_log 的摘要（含两文件 sha256）。"""
    site, network, network_path = load_network(site_id, site_ranges_path)
    defaults = load_station_defaults(stations_dir)
    target_dir = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    plain = build_plain_inputs(network, site, target_dir, defaults)
    net_path = target_dir / DEFAULT_NET_NAME
    build_net_file(plain, net_path, netconvert=netconvert, keep_timestamps=keep_timestamps)

    meta = {
        "is_simulated": True,
        "kind": "sumo_net_build",
        "note": (
            "站点真网 → SUMO 路网的构建元数据（演示数据（模拟））：几何真值来自 OSM 切片；"
            "车道/限速缺值按站点包 defaults 回落，逐条在 edge_meta[] 标来源；"
            "反向补边 SZ-###_rev 只参与仿真，不新增段号（检测器并回原段）"
        ),
        "site_id": site.get("site_id"),
        "site_name": site.get("site_name"),
        "network_source": repo_rel(network_path),
        "seg_target": int(site["seg_target"]),
        "station_defaults": defaults,
        "projection": {
            "kind": "local_tangent_plane",
            "lon0": plain["proj"]["lon0"],
            "lat0": plain["proj"]["lat0"],
            "r_m": plain["proj"]["r_m"],
            "note": "锚点/坐标从真网节点派生，不写死站点坐标；xy_to_lonlat 严格互逆",
        },
        "counts": {
            "nodes": len(plain["node_meta"]),
            "forward_edges": plain["forward_edges"],
            "reverse_edges": plain["reverse_edges"],
            "su_edges": len(plain["edge_meta"]),
            "oneway_edges": sum(
                1
                for edge in network["edges"]
                if str(edge.get("oneway") or "").strip().lower() in ONEWAY_VALUES
            ),
            "lanes_missing_fallback": sum(
                1 for row in plain["edge_meta"] if row["lanes_source"] == LANES_SOURCE_DEFAULT
            ),
            "speed_missing_fallback": sum(
                1 for row in plain["edge_meta"] if row["speed_source"] == defaults["v_f_source"]
            ),
        },
        "inputs": {
            "nod_xml": repo_rel(plain["nod_path"]),
            "edg_xml": repo_rel(plain["edg_path"]),
            "nod_sha256": sha256_file(plain["nod_path"]),
            "edg_sha256": sha256_file(plain["edg_path"]),
        },
        "net": {
            "path": repo_rel(net_path),
            "bytes": net_path.stat().st_size,
            "sha256": sha256_file(net_path),
            "netconvert_args": list(NETCONVERT_ARGS),
        },
        "nodes": plain["node_meta"],
        "edge_meta": plain["edge_meta"],
    }
    meta_path = target_dir / "station_netmeta.json"
    write_json(meta_path, meta)
    meta["meta_path"] = repo_rel(meta_path)
    meta["meta_sha256"] = sha256_file(meta_path)
    print(
        f"[sumonet] 已生成 {net_path.name}（{meta['net']['bytes']} 字节，"
        f"{meta['counts']['nodes']} 节点 / {meta['counts']['forward_edges']} 正向段 / "
        f"{meta['counts']['reverse_edges']} 反向补边）sha256={meta['net']['sha256'][:16]}…"
    )
    return meta


def parse_args(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="站点真网 → SUMO 路网（plain XML → netconvert）")
    parser.add_argument("--site", default="", help="站点 id（缺省用 site-ranges.json 的 default_site）")
    parser.add_argument("--site-ranges", default="", help="站点范围登记表路径（缺省用仓库内那份）")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="输出目录")
    parser.add_argument("--keep-timestamps", action="store_true", help="不规整 netconvert 时间戳（仅调试）")
    parser.add_argument("--sumo-net", default="", help="只校验/复用已有 .net.xml，不重建")
    ns = parser.parse_args(argv)
    return vars(ns)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ns = parse_args(argv)
    if ns["sumo_net"]:
        net_path = Path(ns["sumo_net"])
        if not net_path.is_file():
            raise SystemExit(f"指定的 .net.xml 不存在：{net_path}")
        print(f"[sumonet] 复用已有路网：{repo_rel(net_path)} sha256={sha256_file(net_path)}")
        return 0
    meta = build_station_net(
        site_id=ns["site"] or None,
        site_ranges_path=ns["site_ranges"] or None,
        out_dir=Path(ns["out_dir"]),
        keep_timestamps=bool(ns["keep_timestamps"]),
    )
    counts = meta["counts"]
    print(
        f"[sumonet] 段号命名空间：{meta['seg_target']} 段 SZ-###（正向）；"
        f"反向补边 {counts['reverse_edges']} 条并入原段；"
        f"缺值回落：lanes {counts['lanes_missing_fallback']} / speed {counts['speed_missing_fallback']}"
    )
    print(f"[sumonet] 元数据：{meta['meta_path']}")
    print(f"[sumonet] 两遍一致性：重跑同命令，.net.xml sha256 应相同（当前 {meta['net']['sha256']}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
