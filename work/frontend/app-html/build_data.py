# -*- coding: utf-8 -*-
"""司机端 App 页面试作的数据产物生成（Issue IKLX9B）。

把**已经在库的三份真值**抽成 App 能直接读的 JSON —— App 自己不造段划分、不造指标：

    ① 路段几何        ← src/station-packs/stationZ.network.ts （IKLX5Y 的脚本产物）
    ② 路段基线指标 + 摄像头 ← src/station-packs/stationZ.ts       （IKLX5Y 的演示值）
    ③ 脱网底图（水系 / 绿地 / 背景路 / 路口） ← baseline/nav-demo-baseline.html 里内嵌的那份

产物（**纯脚本产物，勿手改**）：

    data/network.json    路段几何 + 指标 + 摄像头（21 段逐段可对）
    data/map-shapes.json 脱网底图的折线（演示现场没有外网也能画底图）
    data/app-data.js     上面两份的合并包装（HTML 用 `<script src>` 直接读，file:// 免 CORS）

**本脚本不改任何口径**：段 id / 折线 / 等级 / 摄像头全部照抄站点包 Z；
本脚本只做「抽取 + 打包」。

用法（仓库根）：

    python work/frontend/app-html/build_data.py
    python work/frontend/app-html/build_data.py --check   # 只比对，不写
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- 常量

#: 站点包 Z 的两份真值来源（仓库内相对路径，均由 IKLX5Y 维护）
DEFAULT_NETWORK_TS = "work/frontend/ui-vue/src/station-packs/stationZ.network.ts"
DEFAULT_PACK_TS = "work/frontend/ui-vue/src/station-packs/stationZ.ts"
#: 业主提供的单文件 demo（内嵌了这份 OSM 切片的原始形态：水系 / 绿地 / 274 条路 / 路口）
DEFAULT_BASELINE_HTML = "work/frontend/app-html/baseline/nav-demo-baseline.html"
DEFAULT_OUT_DIR = "work/frontend/app-html/data"

#: 四边形坐标保留的小数位（1e-5 度 ≈ 1.1 m，够画图）
COORD_ND = 5

#: 底图配色（只是画布配色，不是等级色；等级色见站点包）
SHAPE_STYLE = {
    "green": {"color": "#d8ebc8", "width": 0.0},
    "water": {"color": "#a9cfe8", "width": 2.2},
    "roads": {"color": "#c9cdd4", "width": 2.0},
    "junctions": {"color": "#b4bac2", "radius": 2.2},
}


# ---------------------------------------------------------------- 解析

TS_SEG_RE = re.compile(
    r"segment_id:\s*'(SZ-\d+)',\s*\n"
    r"\s*name:\s*'([^']*)',\s*\n"
    r"\s*kind:\s*'([^']*)',\s*\n"
    r"\s*coords:\s*\[(.*?)\n\s*\],",
    re.S,
)
TS_BASE_RE = re.compile(
    r"segment_id:\s*'(SZ-\d+)',(.*?)\n  \},",
    re.S,
)
TS_CHANNEL_RE = re.compile(
    r"\{\s*cid:\s*'([^']*)',\s*source:\s*'([^']*)',\s*name:\s*'([^']*)',"
    r"\s*segment_id:\s*'([^']*)',\s*lon:\s*([-\d.]+),\s*lat:\s*([-\d.]+),"
    r"\s*hasVideo:\s*(true|false)\s*\}",
    re.S,
)
TS_RECOMMEND_RE = re.compile(r"recommend:\s*\{(.*?)\n  \},", re.S)
DATA_RE = re.compile(r"const DATA = (\{.*?\});\nconst L = ", re.S)


def _read(path: Path) -> str:
    if not path.exists():
        raise SystemExit(
            f"读不到 {path}\n"
            "  本脚本的输入是**站点包 Z**（IKLX5Y 的产物），它不在 main 上 —— 请先切到含 "
            "stationZ.* 的分支 / 等 IKLX5Y 合入，或用 --network-ts / --pack-ts 指到实际路径。"
        )
    return path.read_text(encoding="utf-8")


def _num(value: str) -> float | int:
    f = float(value)
    return int(f) if f.is_integer() else f


def parse_network_ts(text: str) -> list[dict]:
    """stationZ.network.ts → 段列表（段 id / 名 / kind / 折线）。"""
    segments = []
    for m in TS_SEG_RE.finditer(text):
        sid, name, kind, body = m.group(1), m.group(2), m.group(3), m.group(4)
        coords = [
            [round(float(lon), COORD_ND), round(float(lat), COORD_ND)]
            for lon, lat in re.findall(r"\[([\d.]+),\s*([\d.]+)\]", body)
        ]
        if len(coords) < 2:
            raise SystemExit(f"{sid}: 折线不足 2 点，解析失败")
        segments.append({"segment_id": sid, "name": name, "kind": kind, "coords": coords})
    if not segments:
        raise SystemExit("没有解析到任何路段 —— stationZ.network.ts 的形状变了？")
    return segments


def extract_block(text: str, marker: str) -> str:
    """取出 `marker = [ ... ]` 这种顶层数组的字面量内容（按行首 `]` 收尾）。

    先切块再逐条解析 —— 否则「通道行里也有 segment_id」会被基线的正则误吃。
    """
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f"stationZ.ts 里找不到 {marker} —— 形状变了？")
    body = text[start + len(marker):]
    end = body.find("\n]")
    if end < 0:
        raise SystemExit(f"{marker} 没有找到收尾的 `]` —— 形状变了？")
    return body[:end]


def parse_pack_ts(text: str) -> tuple[dict, dict, list[dict], dict]:
    """stationZ.ts → (指标基线, 摄像头, 推荐路线骨架, 站点信息)。"""
    bases: dict[str, dict] = {}
    for m in TS_BASE_RE.finditer(extract_block(text, "const SEGMENT_BASES: PackSegmentBase[] = [")):
        sid, body = m.group(1), m.group(2)
        level = re.search(r"\blevel:\s*(\d+)", body)
        ci = re.search(r"\bci:\s*([\d.]+)", body)
        source = re.search(r"\bsource:\s*'([^']*)'", body)
        derive = re.search(r"\bderive:\s*'([^']*)'", body)
        if not (level and ci):
            raise SystemExit(f"{sid}: 基线里没有 level / ci —— stationZ.ts 的形状变了？")
        bases[sid] = {
            "level": int(level.group(1)),
            "ci": _num(ci.group(1)),
            "source": source.group(1) if source else "",
            "derive": derive.group(1) if derive else "",
        }

    channels = []
    for m in TS_CHANNEL_RE.finditer(extract_block(text, "const CHANNELS: PackChannel[] = [")):
        cid, source, name, sid, lon, lat, has_video = m.groups()
        channels.append({
            "cid": cid,
            "source": source,
            "name": name,
            "segment_id": sid,
            "lon": round(float(lon), 7),
            "lat": round(float(lat), 7),
            "hasVideo": has_video == "true",
        })
    if not channels:
        raise SystemExit("没有解析到任何摄像头 —— stationZ.ts 的形状变了？")

    rm = TS_RECOMMEND_RE.search(text)
    if not rm:
        raise SystemExit("没有解析到 recommend —— stationZ.ts 的形状变了？")
    body = rm.group(1)

    def str_list(key: str) -> list[str]:
        mm = re.search(rf"{key}:\s*\[([^\]]*)\]", body, re.S)
        return re.findall(r"'([^']*)'", mm.group(1)) if mm else []

    def str_one(key: str) -> str:
        mm = re.search(rf"{key}:\s*'([^']*)'", body)
        return mm.group(1) if mm else ""

    def num_one(key: str) -> float | int:
        mm = re.search(rf"{key}:\s*([\d.]+)", body)
        return _num(mm.group(1)) if mm else 0

    alts = []
    alt_block = re.search(r"alternatives:\s*\[(.*?)\n    \]", body, re.S)
    if alt_block:
        for am in re.finditer(
            r"path_id:\s*'([^']*)',\s*segments:\s*\[([^\]]*)\],\s*eta_min:\s*([\d.]+),\s*note:\s*'([^']*)'",
            alt_block.group(1),
        ):
            alts.append({
                "path_id": am.group(1),
                "segments": re.findall(r"'([^']*)'", am.group(2)),
                "eta_min": _num(am.group(3)),
                "note": am.group(4),
            })

    recommend = {
        "location_segment_id": str_one("location_segment_id"),
        "location_offset_m": num_one("location_offset_m"),
        "arrival_segments": str_list("arrival_segments"),
        "arrival_eta_min": num_one("arrival_eta_min"),
        "arrival_walk_min": num_one("arrival_walk_min"),
        "departure_segments": str_list("departure_segments"),
        "departure_eta_min": num_one("departure_eta_min"),
        "alternatives": alts,
        "why": str_one("why"),
    }

    def one_in(block: str, key: str) -> str:
        mm = re.search(rf"{key}:\s*'([^']*)'", block)
        return mm.group(1) if mm else ""

    st_block = re.search(r"station:\s*\{(.*?)\n  \},", text, re.S)
    src_block = re.search(r"source:\s*\{(.*?)\n  \},", text, re.S)
    station = {
        "station_id": one_in(st_block.group(1), "station_id") if st_block else "",
        "name": one_in(st_block.group(1), "name") if st_block else "",
        "subtitle": one_in(st_block.group(1), "subtitle") if st_block else "",
        "attribution": one_in(src_block.group(1), "attribution") if src_block else "",
        "note": one_in(text, "note"),
    }
    return bases, station, channels, recommend


def parse_baseline_shapes(text: str) -> dict:
    """baseline HTML 内嵌的脱网底图（水系 / 绿地 / 背景路 / 路口）。"""
    m = DATA_RE.search(text)
    if not m:
        raise SystemExit("基线 HTML 里没有找到内嵌的 DATA —— 换基线了？")
    data = json.loads(m.group(1))
    layers = data.get("layers") or {}
    shapes: dict[str, list] = {}
    for key in ("green", "water", "roads", "junctions"):
        raw = layers.get(key) or []
        out = []
        for item in raw:
            if isinstance(item, dict):          # roads 带属性，折线在 coordinates 里
                coords = item.get("coordinates")
            else:                                # water / green 是折线，junctions 是单点
                coords = item
            if not coords:
                continue
            if isinstance(coords[0], (int, float)):      # 单点 [lon, lat]
                out.append([round(float(coords[0]), COORD_ND), round(float(coords[1]), COORD_ND)])
            else:                                        # 折线 [[lon, lat], ...]
                out.append([
                    [round(float(c[0]), COORD_ND), round(float(c[1]), COORD_ND)]
                    for c in coords
                ])
        shapes[key] = out
    return shapes


# ---------------------------------------------------------------- 组装

def build(segments: list[dict], bases: dict, channels: list[dict], recommend: dict,
          station: dict, shapes: dict) -> tuple[dict, dict]:
    cam_count: dict[str, int] = {}
    for c in channels:
        cam_count[c["segment_id"]] = cam_count.get(c["segment_id"], 0) + 1

    nets = []
    for seg in segments:
        sid = seg["segment_id"]
        base = bases.get(sid)
        cams = [c for c in channels if c["segment_id"] == sid]
        nets.append({
            "segment_id": sid,
            "name": seg["name"],
            "kind": seg["kind"],
            "coords": seg["coords"],
            "camera_count": cam_count.get(sid, 0),
            "camera_sources": [c["source"] for c in cams],
            # 没有基线的段**不给 level**——按 IKLX5Y 的口径，这些段只画灰轮廓
            "level": base["level"] if base else None,
            "ci": base["ci"] if base else None,
            "source": base["source"] if base else "",
            "derive": base["derive"] if base else "",
        })

    network = {
        "is_simulated": True,
        "note": "几何取自 OSM（真值）；等级 / 指数一律为演示数据（模拟）—— 只摄像头覆盖的段才有等级",
        "station": station,
        "cameraPolicy": "camera-covered",
        "recommend": recommend,
        "cameras": channels,
        "segments": nets,
    }
    maps = {
        "is_simulated": True,
        "note": "背景底图（水系 / 绿地 / 道路 / 路口）为 OSM 数据，仅作画布；路况口径见 network.json",
        "attribution": "© OpenStreetMap contributors",
        "style": SHAPE_STYLE,
        "shapes": shapes,
    }
    return network, maps


def _dump(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def _js_wrapper(network: dict, maps: dict, script_name: str) -> str:
    head = (
        "// 司机端 App 页面试作的运行数据（Issue IKLX9B）。**本文件是脚本产物，勿手改。**\n"
        f"// 生成：python {script_name}\n"
        "// 来源：stationZ.network.ts（几何）+ stationZ.ts（演示指标 / 摄像头）"
        "+ 基线 HTML 内嵌底图。\n"
        "// 口径：几何是真值（OSM）；等级与指数是演示数据（模拟），只有摄像头覆盖的段才有等级。\n"
        "window.HUBFLOW_APP_DATA = {\n"
        "  network: "
    )
    body = json.dumps(network, ensure_ascii=False, indent=2)
    mid = ",\n  maps: "
    body2 = json.dumps(maps, ensure_ascii=False, indent=2)
    tail = ",\n  generated_by: " + json.dumps(script_name) + "\n};\n"
    return head + body + mid + body2 + tail


# ---------------------------------------------------------------- 主流程

def main() -> int:
    parser = argparse.ArgumentParser(description="司机端 App 页面试作的数据产物生成（IKLX9B）")
    parser.add_argument("--repo", default=".", help="仓库根（默认当前目录）")
    parser.add_argument("--network-ts", default=DEFAULT_NETWORK_TS)
    parser.add_argument("--pack-ts", default=DEFAULT_PACK_TS)
    parser.add_argument("--baseline", default=DEFAULT_BASELINE_HTML)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--check", action="store_true", help="只比对既有产物，不写")
    args = parser.parse_args()

    root = Path(args.repo).resolve()
    segments = parse_network_ts(_read(root / args.network_ts))
    bases, station, channels, recommend = parse_pack_ts(_read(root / args.pack_ts))
    shapes = parse_baseline_shapes(_read(root / args.baseline))
    network, maps = build(segments, bases, channels, recommend, station, shapes)

    out_dir = root / args.out_dir
    produced = {
        "network.json": _dump(network),
        "map-shapes.json": _dump(maps),
        "app-data.js": _js_wrapper(network, maps, "work/frontend/app-html/build_data.py"),
    }

    if args.check:
        bad = 0
        for name, text in produced.items():
            path = out_dir / name
            if not path.exists():
                print(f"[缺] {path}")
                bad += 1
                continue
            old = path.read_text(encoding="utf-8")
            if old != text:
                print(f"[不一致] {path}")
                bad += 1
        if bad:
            print(f"--check 失败：{bad} 份产物与站点包 Z 不一致")
            return 1
        print(f"--check 通过：{len(produced)} 份产物与站点包 Z 逐字节一致")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in produced.items():
        (out_dir / name).write_text(text, encoding="utf-8", newline="\n")
    levels = {s["segment_id"]: s["level"] for s in network["segments"] if s["level"]}
    gray = [s["segment_id"] for s in network["segments"] if not s["level"]]
    print(f"写入 {len(produced)} 份产物 → {out_dir}")
    print(f"  路段 {len(network['segments'])} 段；摄像头 {len(channels)} 路；上色段 {len(levels)} 段："
          + "、".join(f"{k}({v} 级)" for k, v in levels.items()))
    print(f"  灰轮廓 {len(gray)} 段：" + "、".join(gray))
    return 0


if __name__ == "__main__":
    sys.exit(main())
