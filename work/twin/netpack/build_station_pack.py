# -*- coding: utf-8 -*-
"""站点 OSM 切片 → 站点包 Z 的路网（Issue IKLX5Y）。

输入：一份 OSM 切片（`.osm`，Overpass 导出，带 node / way / tag）。
输出：
  ① `network.json` —— 机器可读的路网真值（每段带组成它的 OSM way id，可追溯）；
  ② `stationZ.network.ts` —— 前端站点包的几何部分（纯脚本产物，勿手改）。

## 路段粒度（业主 2026-10-15 裁定：按路名归并）

1. **归并键**：有名用 `name`；无名按 `service`；再退 `highway`。
2. **串链**：同组内共享 OSM 节点的 way 首尾相接成一串。
3. **并片**：串完还剩下的"片"，若**端点相距 ≤ SNAP_M 米**就算同一个路口的两侧，接起来。
   （OSM 在路口处常常各 way 各用一个独立节点，不并片会把一个路口切成好几截。）
4. **剔碎**：不足 MIN_SEG_M 米的片丢弃（都是路口连接的小碎段，画在图上只是噪点）。
5. 同一归并键最终仍是多片的，名字加方位后缀（如「吉庆大道·由北向南第2片」）以示区分。

## 两条硬口径

· 脚本里**不出现任何站点名与坐标**（手册 §8.4：换站只改参数）——站点名走 `--site`；
· 产物只由脚本生成，**不许手改**；`--check` 重跑一遍与既有产物逐字节比对。

用法（仓库根）：

    python work/twin/netpack/build_station_pack.py \
        --osm work/frontend/tools/twin_preview/station.osm \
        --site 肇庆东站 \
        --out-json work/twin/netpack/network.json \
        --out-ts work/frontend/ui-vue/src/station-packs/stationZ.network.ts

    python work/twin/netpack/build_station_pack.py ... --check   # 只比对，不写
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

RAD = math.pi / 180
R = 6371000.0

#: 端点多近算"同一个路口"（米）。OSM 各 way 在路口各自建节点，间距一般几米到几十米。
SNAP_M = 30.0
#: 不足这么长的片丢弃（路口连接碎段）。
MIN_SEG_M = 60.0
#: 车行主干类（决定包里 kind = main / ramp）
MAIN_HIGHWAYS = ("primary", "secondary", "tertiary", "residential", "unclassified")
#: 不进路网的 highway 类型（步行 / 自行车 / 施工 / 拟建）
SKIP_HIGHWAYS = ("footway", "path", "cycleway", "steps", "pedestrian", "track",
                 "construction", "proposed", "bridleway", "corridor", "platform")

#: 无名路段的中文名（按 OSM 标签翻译；这是**通用标签译名**，与站点无关）
LABEL_ZH = {
    "service:parking_aisle": "停车场内部通道",
    "service:driveway": "场区出入道",
    "service": "服务道路",
    "primary_link": "连接匝道",
    "secondary_link": "连接匝道",
    "tertiary_link": "连接匝道",
    "primary": "主干道",
    "secondary": "次干道",
    "tertiary": "支路",
    "residential": "生活性道路",
    "unclassified": "未分级道路",
}


def dm(a, b) -> float:
    """两点球面近似距离（米）。a / b = (lon, lat)。"""
    dx = (b[0] - a[0]) * math.cos((a[1] + b[1]) / 2 * RAD)
    dy = b[1] - a[1]
    return math.hypot(dx, dy) * RAD * R


def line_len(line) -> float:
    return sum(dm(line[i], line[i + 1]) for i in range(len(line) - 1))


def parse_osm(path: Path):
    """返回 (nodes: {id: (lon, lat)}, ways: [{way_id, nds, pts, tags, len_m}])。"""
    txt = path.read_text(encoding="utf-8", errors="replace")

    nodes: dict[str, tuple[float, float]] = {}
    for m in re.finditer(r'<node id="(\d+)"[^>]*lat="(-?[\d.]+)"[^>]*lon="(-?[\d.]+)"', txt):
        nodes[m.group(1)] = (float(m.group(3)), float(m.group(2)))

    ways = []
    cur, tags, nds = None, [], []
    for line in txt.splitlines():
        line = line.strip()
        m = re.match(r'<way id="(\d+)"', line)
        if m:
            cur, tags, nds = m.group(1), [], []
            continue
        m = re.match(r'<nd ref="(\d+)"', line)
        if m and cur is not None:
            nds.append(m.group(1))
            continue
        m = re.match(r'<tag k="([^"]+)" v="([^"]+)"', line)
        if m and cur is not None:
            tags.append((m.group(1), m.group(2)))
            continue
        if line.startswith("</way>") and cur is not None:
            d = dict(tags)
            kept = [n for n in nds if n in nodes]
            pts = [nodes[n] for n in kept]
            if len(pts) >= 2:
                ways.append({
                    "way_id": cur,
                    "nds": kept,
                    "pts": pts,
                    "tags": d,
                    "len_m": line_len(pts),
                })
            cur, tags, nds = None, [], []
    return nodes, ways


def car_ways(ways):
    """只留车行道路（步行 / 自行车 / 铁路 / 施工 / 无 highway 又无 service 的都不进路网）。"""
    out = []
    for w in ways:
        t = w["tags"]
        hw = t.get("highway", "")
        if hw in SKIP_HIGHWAYS:
            continue
        if t.get("railway") or t.get("route"):
            continue
        if not hw and not t.get("service"):
            continue
        out.append(w)
    return out


def group_key(w) -> str:
    """归并键：有名用名；无名按 service；再退 highway。"""
    t = w["tags"]
    if t.get("name"):
        return t["name"]
    if t.get("service"):
        return "service:" + t["service"]
    return t.get("highway") or "未分类"


def kind_of(w) -> str:
    """包里的 kind：主干类 = main，其余（含 service / *_link）= ramp。"""
    return "main" if w["tags"].get("highway") in MAIN_HIGHWAYS else "ramp"


def chain(ways):
    """组内按共享 OSM 节点串成长折线；串不动的另一摊就新起一条。

    返回 `[(line, [way_id, ...]), ...]` —— way 清单是**逐片**记的（一片可能只用了
    组里的一部分 way），这样 network.json 里的 `way_ids` 才是真溯源。
    """
    remaining = list(ways)
    out: list[tuple[list, list]] = []
    while remaining:
        head = remaining.pop(0)
        line = list(head["pts"])
        used = [head["way_id"]]
        tail = head["nds"][-1]
        extended = True
        while extended:
            extended = False
            for i, w in enumerate(remaining):
                if w["nds"][0] == tail:
                    line += w["pts"][1:]
                    tail = w["nds"][-1]
                elif w["nds"][-1] == tail:
                    line += w["pts"][::-1][1:]
                    tail = w["nds"][0]
                else:
                    continue
                used.append(w["way_id"])
                remaining.pop(i)
                extended = True
                break
        out.append((dedup(line), sorted(used)))
    return out


def dedup(line):
    """去掉连续重复点（距离 < 5 cm）。"""
    keep = [line[0]]
    for p in line[1:]:
        if dm(keep[-1], p) > 0.05:
            keep.append(p)
    return keep


def snap_merge(pieces, tol=SNAP_M):
    """端点相距 ≤ tol 的两片接起来（反复做，直到接不动）。每片是 `(line, way_ids)`。

    这一条是路上"路口两侧各是一条 way、各自建节点"的对策——不并片会把一个路口
    切成好几截，图上全是断口。
    """
    pieces = [(list(p), list(w)) for p, w in pieces]
    changed = True
    while changed:
        changed = False
        for i in range(len(pieces)):
            for j in range(i + 1, len(pieces)):
                (a, wa), (b, wb) = pieces[i], pieces[j]
                how, d = min(
                    (("hh", dm(a[0], b[0])), ("ht", dm(a[0], b[-1])),
                     ("th", dm(a[-1], b[0])), ("tt", dm(a[-1], b[-1]))),
                    key=lambda x: x[1],
                )
                if d > tol:
                    continue
                if how == "hh":
                    new = a[::-1] + b
                elif how == "ht":
                    new = a[::-1] + b[::-1]
                elif how == "th":
                    new = a + b
                else:
                    new = a + b[::-1]
                merged = (dedup(new), sorted(set(wa) | set(wb)))
                pieces = [p for k, p in enumerate(pieces) if k not in (i, j)] + [merged]
                changed = True
                break
            if changed:
                break
    return pieces


def build(ways):
    """归并 → 串链 → 并片 → 剔碎 → 编号。返回稳定的段落清单（按长度降序）。"""
    groups = defaultdict(list)
    for w in car_ways(ways):
        groups[group_key(w)].append(w)

    raw = []
    for key, ws in groups.items():
        pieces = [(p, ids) for p, ids in snap_merge(chain(ws)) if line_len(p) >= MIN_SEG_M]
        for line, ids in pieces:
            raw.append({
                "name": key,
                "kind": "main" if any(kind_of(w) == "main" for w in ws) else "ramp",
                "way_ids": ids,
                "length_m": line_len(line),
                "coords": line,
            })

    # 无名路段译成中文名（有 `name` 的路保持 OSM 原名，**不改**）
    for r in raw:
        if r["name"] in LABEL_ZH:
            r["name"] = LABEL_ZH[r["name"]]

    # 同名多片 → 加方位后缀，免得两条同名的段分不清
    by_name = defaultdict(list)
    for r in raw:
        by_name[r["name"]].append(r)
    for name, items in by_name.items():
        if len(items) == 1:
            continue
        lats = [sum(c[1] for c in it["coords"]) / len(it["coords"]) for it in items]
        lons = [sum(c[0] for c in it["coords"]) / len(it["coords"]) for it in items]
        by_lat = (max(lats) - min(lats)) >= (max(lons) - min(lons))
        vals = lats if by_lat else lons
        order = sorted(range(len(items)), key=lambda i: vals[i], reverse=by_lat)
        rule = "由北向南" if by_lat else "由西向东"
        for rank, idx in enumerate(order, start=1):
            items[idx]["name"] = f"{name}·{rule}第{rank}片"

    raw.sort(key=lambda r: (-round(r["length_m"], 3), r["name"]))
    for i, r in enumerate(raw, start=1):
        r["segment_id"] = f"SZ-{i:02d}"
    return raw


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


def fmt_ts(site: str, segs, osm_name: str) -> str:
    """生成 stationZ.network.ts（几何部分）。"""
    lines = [
        "// 站点包 Z ·「站点 OSM 真路网」演示站（Issue IKLX5Y）。",
        "//",
        f"// 来源：{osm_name} 切片经 build_station_pack.py 归并（按路名合并 → 路口并片 → 剔碎段）。",
        "// **几何取自 OSM（真值）**；路况指标一律为**演示数据（模拟）**，且只有挂摄像头的路段才上色。",
        "// 本文件是脚本产物（work/twin/netpack/build_station_pack.py），**勿手改**。",
        "// 不依赖任何后端 / SUMO / 桥接服务。",
        "",
        "import type { PackSegment } from './types.ts'",
        "",
        "export const STATION_Z_SEGMENTS: PackSegment[] = [",
    ]
    for s in segs:
        lines.append("  {")
        lines.append(f"    segment_id: '{s['segment_id']}',")
        lines.append(f"    name: '{esc(s['name'])}',")
        lines.append(f"    kind: '{s['kind']}',")
        lines.append("    coords: [")
        coords = ",\n          ".join(f"[{c[0]:.7f}, {c[1]:.7f}]" for c in s["coords"])
        lines.append(f"          {coords}")
        lines.append("    ],")
        lines.append("  },")
    lines += ["]", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--osm", required=True, help="OSM 切片路径")
    ap.add_argument("--site", required=True, help="站点名（写进 network.json；脚本里不硬编码）")
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-ts", required=True)
    ap.add_argument("--check", action="store_true", help="只比对既有产物，不写")
    a = ap.parse_args()

    nodes, ways = parse_osm(Path(a.osm))
    segs = build(ways)
    osm_name = Path(a.osm).name

    net = {
        "is_simulated": True,
        "note": "几何取自 OpenStreetMap 切片（真值）；路况指标一律为演示数据（模拟），本文件不含任何指标",
        "site": a.site,
        "crs": "WGS-84",
        "source": "OpenStreetMap (ODbL 1.0)",
        "generated_by": "work/twin/netpack/build_station_pack.py",
        "way_grouping": "按路名归并；路口端点相距 ≤ %g m 并片；不足 %g m 的碎段剔除" % (SNAP_M, MIN_SEG_M),
        "segments": [
            {
                "segment_id": s["segment_id"],
                "name": s["name"],
                "kind": s["kind"],
                "way_ids": s["way_ids"],
                "length_m": round(s["length_m"], 1),
                "coords": [[round(c[0], 7), round(c[1], 7)] for c in s["coords"]],
            }
            for s in segs
        ],
    }

    json_text = json.dumps(net, ensure_ascii=False, indent=2) + "\n"
    ts_text = fmt_ts(a.site, segs, osm_name)

    if a.check:
        bad = 0
        for path, want in ((Path(a.out_json), json_text), (Path(a.out_ts), ts_text)):
            # 比对前把换行归一:门禁要求 LF,但既有产物可能是早先 CRLF 版本写的,
            # 那种差异不算"内容不一致"(重新生成会自动落成 LF)。
            have = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else ""
            if have != want:
                print(f"❌ 与既有产物不一致：{path}")
                bad += 1
            else:
                print(f"✅ 一致：{path}")
        print(f"\n{len(segs)} 段；总长 {sum(s['length_m'] for s in segs):.0f} m")
        return 1 if bad else 0

    Path(a.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out_ts).parent.mkdir(parents=True, exist_ok=True)
    # newline="\n":仓库统一 LF(.gitattributes 强制),Windows 上不写这一句会吐 CRLF,门禁第 1 组不过
    Path(a.out_json).write_text(json_text, encoding="utf-8", newline="\n")
    Path(a.out_ts).write_text(ts_text, encoding="utf-8", newline="\n")

    print(f"站点：{a.site}   way {len(ways)} 条（车行 {len(car_ways(ways))}）→ 路段 {len(segs)} 段")
    for s in segs:
        print(f"  {s['segment_id']:<7}{s['kind']:<6}{s['name']:<30}"
              f"{s['length_m']:>7.0f} m  {len(s['coords']):>3} 点  way {len(s['way_ids'])} 条")
    print(f"\n总长 {sum(s['length_m'] for s in segs):.0f} m")
    print(f"→ {a.out_json}")
    print(f"→ {a.out_ts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
