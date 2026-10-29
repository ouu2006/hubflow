#!/usr/bin/env python3
r"""生成「真值路网底衬」前端数据：站点 OSM 切片 → `station-packs/stationZ.roads.ts`。

## 为什么要这一层（2026-10-29 演示验收实测结论）

底图源（OpenFreeMap `planet`）的 TileJSON 是 `maxzoom: 14`，而大屏站区视角 zoom≈16.5
—— 等于把 z14 瓦片放大 2.5~3.6 倍（overzoom）。这带来两个肉眼可见的后果：

1. **z14 瓦片里没有 `service` / `track` 级道路**。本站 61 段里有 44 段是 ramp
   （停车场内部通道 / 服务道路 / 连接匝道），底图那块就是空白 + 建筑面 →
   彩色路段看起来"悬空穿过场地"，被读成"线路画错了"；
2. **z14 对分离式双向道路做过合并 / 折线简化** → 干道上彩色线与底图黄线肉眼错开 10~15 m。

已排除"几何画错"这个方向：对 61 段逐顶点 + 每条边每 5% 内插点求到实时 OSM 车道的距离，
`N>5m 0 / N>15m 0 / median 0.0 m / 最大偏差 SZ-003 = 0.2 m` —— 路网几何是**真值**。

所以修法不是改几何，而是**换底衬**：把同一份 OSM 切片里的车行道自己画一遍（浅色细线），
底图道路图层在站区档（zoom ≥ 14.5）整族关掉（见 `MapLibreViewer.vue` 的 `BASEMAP_ROAD_MAXZOOM`）。
这样"彩色路段一定长在自己画的路网上"，也与地图上那句「路网几何为真值（OSM 切片）」自洽。

## 口径

- 几何一律取 OSM 原始节点坐标，**不插值、不简化、不移动**（与 `build_junction_pack.py` 同口径）。
- 只收**车行**道路；`crossing` / `traffic_signals` / 人行道 / 台阶一律不收（它们不是路，画上去是噪声）。
- `area=yes` 的面状 way 不收（停车场铺面不是线）。
- 本脚本产物是**绘制底衬**，不参与判级 / 路线 / 任何业务计算，也没有任何指标。

用法：
    python work/frontend/scripts/gen_station_roads.py
    python work/frontend/scripts/gen_station_roads.py --osm <切片> --out <ts 路径>
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[3]

DEFAULT_OSM = ROOT / "work/frontend/tools/twin_preview/station.osm"
DEFAULT_OUT = ROOT / "work/frontend/ui-vue/src/station-packs/stationZ.roads.ts"
DEFAULT_CONST = "STATION_Z_ROADS"

#: highway 值 → 底衬分类。分类只决定线宽与色调（见 MapLibreViewer 的 `ROADS_STYLE`），无业务含义。
CLASS_BY_HIGHWAY: dict[str, str] = {
    "motorway": "arterial",
    "trunk": "arterial",
    "primary": "arterial",
    "secondary": "arterial",
    "tertiary": "arterial",
    "motorway_link": "link",
    "trunk_link": "link",
    "primary_link": "link",
    "secondary_link": "link",
    "tertiary_link": "link",
    "unclassified": "local",
    "residential": "local",
    "living_street": "local",
    "service": "local",
}

#: 明确**不收**的 highway 值：人行横道 / 信号灯 / 人行 / 台阶 / 自行车道 / 公交专用道口
SKIP_HIGHWAY = {
    "crossing", "traffic_signals", "stop", "give_way", "street_lamp", "bus_stop",
    "footway", "path", "pedestrian", "steps", "cycleway", "corridor", "elevator",
    "platform", "proposed", "construction", "raceway", "busway", "escape",
}


def load_osm(path: Path) -> tuple[dict[str, tuple[float, float]], list[tuple[str, dict, list[str]]]]:
    """读 OSM 切片：返回 (node_id → (lon, lat), [(way_id, tags, node_refs)])。

    ⚠️ 先剥掉 XML 注释再解析：切片头部的溯源注释里写了 `build_junction_pack.py --site-id …`
    这类命令行，而 XML 注释**不允许**出现 `--`（`work/twin/netpack/osm/guangzhounan.osm`
    就是这样，直接 `ET.parse` 会抛 `not well-formed (invalid token)`）。注释里没有几何。
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    root = ET.fromstring(text)
    nodes: dict[str, tuple[float, float]] = {}
    for n in root.findall("node"):
        nid = n.get("id") or ""
        lat, lon = n.get("lat"), n.get("lon")
        if not nid or lat is None or lon is None:
            continue
        nodes[nid] = (float(lon), float(lat))
    ways: list[tuple[str, dict, list[str]]] = []
    for w in root.findall("way"):
        tags = {t.get("k"): t.get("v") for t in w.findall("tag")}
        refs = [r.get("ref") or "" for r in w.findall("nd")]
        ways.append((w.get("id") or "", tags, refs))
    return nodes, ways


def classify(tags: dict) -> str | None:
    """返回底衬分类；不收的 way 返回 None。"""
    if tags.get("area") == "yes":
        return None                      # 面状 way（停车场铺面 / 广场）不是线
    hw = tags.get("highway")
    if not hw or hw in SKIP_HIGHWAY:
        return None
    if hw == "service" and tags.get("service") == "parking_aisle":
        return "aisle"                   # 停车场内部通道：本站 61 段里 44 段 ramp 大多落在这里
    return CLASS_BY_HIGHWAY.get(hw)


def fmt_num(v: float) -> str:
    """坐标统一 7 位小数（约 1 cm，远小于 OSM 精度，够用又省体积）。"""
    s = f"{v:.7f}".rstrip("0").rstrip(".")
    return s if s else "0"


def build(nodes, ways) -> tuple[list[dict], Counter]:
    out: list[dict] = []
    stat: Counter = Counter()
    seen: set[tuple] = set()
    for wid, tags, refs in ways:
        cls = classify(tags)
        if cls is None:
            stat["skipped"] += 1
            continue
        coords: list[tuple[float, float]] = []
        for r in refs:
            p = nodes.get(r)
            if p is not None:
                coords.append(p)
        if len(coords) < 2:
            stat["too_few_nodes"] += 1
            continue
        # 同一折线可能被切成两个 way（OSM 常见）：几何完全相同的只画一次
        key = (cls, tuple(coords))
        if key in seen:
            stat["dedup"] += 1
            continue
        seen.add(key)
        item: dict = {"cls": cls, "hw": tags.get("highway") or "", "coords": coords}
        name = tags.get("name")
        if name:
            item["name"] = name
        out.append(item)
        stat[cls] += 1
    return out, stat


def render(roads: list[dict], const_name: str, osm_rel: str, stat: Counter) -> str:
    lines: list[str] = []
    lines.append("// ⚠️ 本文件由脚本 `work/frontend/scripts/gen_station_roads.py` 生成，**勿手改**。")
    lines.append("//")
    lines.append("// 真值路网底衬：把本站 OSM 切片里的**车行道**按原始节点坐标画一遍，垫在彩色路段下面。")
    lines.append("// 为什么需要它：底图源 TileJSON 的 maxzoom=14，站区视角（zoom≈16.5）是 overzoom ——")
    lines.append("// z14 瓦片没有 service/track 级道路、干道也被合并简化，于是 44 段 ramp（停车场内部")
    lines.append("// 通道/服务道路/连接匝道）在底图上是空白、彩色线看起来悬空。详见生成脚本的文件头说明。")
    lines.append("//")
    lines.append(f"// 来源：`{osm_rel}`（几何取 OSM 原始节点，不插值、不简化、不移动）")
    lines.append(f"// 规模：{len(roads)} 条折线（arterial {stat['arterial']} / link {stat['link']}"
                 f" / local {stat['local']} / aisle {stat['aisle']}）")
    lines.append("// 本数据**只用于绘制底衬**，不参与判级 / 路线 / 任何业务计算，也不含任何指标。")
    lines.append("")
    lines.append("import type { PackRoadLine } from './types.ts'")
    lines.append("")
    lines.append(f"export const {const_name}: PackRoadLine[] = [")
    for r in roads:
        head = f"  {{ cls: '{r['cls']}', hw: '{r['hw']}'"
        if r.get("name"):
            name = r["name"].replace("\\", "\\\\").replace("'", "\\'")
            head += f", name: '{name}'"
        head += ", coords: ["
        coords = ", ".join(f"[{fmt_num(lon)},{fmt_num(lat)}]" for lon, lat in r["coords"])
        lines.append(head)
        lines.append(f"    {coords},")
        lines.append("  ] },")
    lines.append("]")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="站点 OSM 切片 → 真值路网底衬（前端站点包字段）")
    ap.add_argument("--osm", default=str(DEFAULT_OSM), help="OSM 切片路径")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="输出 .ts 路径")
    ap.add_argument("--const", default=DEFAULT_CONST, help="导出的常量名")
    a = ap.parse_args()

    osm = Path(a.osm)
    out = Path(a.out)
    if not osm.is_file():
        raise SystemExit(f"缺 OSM 切片：{osm}")

    nodes, ways = load_osm(osm)
    roads, stat = build(nodes, ways)
    if not roads:
        raise SystemExit("一条车行道都没解析出来 —— 检查 OSM 切片是否含 highway 标签")

    try:
        osm_rel = osm.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        osm_rel = osm.as_posix()

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(roads, a.const, osm_rel, stat), encoding="utf-8")

    print(f"OSM: {osm}（node {len(nodes)} / way {len(ways)}）")
    print(f"  收到 {len(roads)} 条：arterial {stat['arterial']} / link {stat['link']}"
          f" / local {stat['local']} / aisle {stat['aisle']}")
    print(f"  跳过 {stat['skipped']}（非车行 / 面状）/ 点不足 {stat['too_few_nodes']}"
          f" / 去重 {stat['dedup']}")
    print(f"输出: {out}（{out.stat().st_size / 1024:.1f} KB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
