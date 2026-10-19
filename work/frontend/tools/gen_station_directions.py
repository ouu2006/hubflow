#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读生成前端站点包的方向 / 车道 / 对向 / 贯通字段（Issue IKOQEJ）。

**只读** `work/twin/netpack/**/network_junction.enriched.json`，生成前端 TS：
  · work/frontend/ui-vue/src/station-packs/stationZ.directions.generated.ts
  · work/frontend/ui-vue/src/station-packs/stationGZ.directions.generated.ts

不改路网 / 引擎 / 数据 / 判定 / 契约 / stations；生成的只是**前端展示用**字段，
缺值保持 null（页面如实显示「—/未标定」），不宣称真实车道/方向来自实测。

用法（仓库根）：
  python work/frontend/tools/gen_station_directions.py          # 生成/覆盖
  python work/frontend/tools/gen_station_directions.py --check  # 只校验是否与 enriched 同步（CI/自检）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

# work/frontend/tools/gen_station_directions.py -> repo/work/frontend/tools
REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = Path("work/twin/netpack")
OUT_DIR = Path("work/frontend/ui-vue/src/station-packs")

#: 一个站 = 一份 enriched；GZ 的 enriched 由多站/拓扑任务（IKNC4J / IKOQEI）维护。
#: ⚠️ enriched 段数可能大于前端站点包网络（IKOQEI 把 GZ 范围 800→1000 m 后 enriched 708 段，
#:    前端 stationGZ.network.ts 仍 433 段）：生成器**只生成前端网络里存在的段**，其余等前端包同步，
#:    避免给页面不存在的段号写方向字段（方向标/详情只认当前站点包几何）。
SOURCES = [
    {
        "key": "Z",
        "enriched": SRC_DIR / "network_junction.enriched.json",
        "network": OUT_DIR / "stationZ.network.ts",
        "out": OUT_DIR / "stationZ.directions.generated.ts",
        "const": "STATION_Z_DIRECTIONS",
        "site_name": "肇庆东站",
    },
    {
        "key": "GZ",
        "enriched": SRC_DIR / "guangzhounan" / "network_junction.enriched.json",
        "network": OUT_DIR / "stationGZ.network.ts",
        "out": OUT_DIR / "stationGZ.directions.generated.ts",
        "const": "STATION_GZ_DIRECTIONS",
        "site_name": "广州南站",
    },
]


def network_segment_ids(path: Path) -> set[str]:
    """前端站点包网络里的段号（只读 .ts 生成物，用来裁掉 enriched 里前端还没有的段）。"""
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r"segment_id: '([^']+)'", text))

#: 展示需要的字段（enriched edge 字段 → 前端字段，原样拷贝，不做推算/补值）
FIELDS = [
    "direction",
    "lanes_forward",
    "lanes_backward",
    "lanes_total",
    "opposite_segment_id",
    "oneway",
    "u_turn_allowed",
]
CONTINUITY_FIELDS = [
    "head_connected",
    "tail_connected",
    "gap_to_next_m",
    "gap_to_next_node",
    "gap_to_next_segment_id",
    "chain_id",
    "chain_name",
]
#: 页面要标注"这个字段从哪来"（osm / derived / default），只保留展示需要的几项
SOURCE_KEYS = [
    "direction",
    "lanes_forward",
    "lanes_backward",
    "lanes_total",
    "opposite_segment_id",
    "continuity.head_connected",
    "continuity.tail_connected",
]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_directions(enriched_path: Path, allowed_ids: set[str] | None = None) -> tuple[dict, dict]:
    """返回 (segment_id -> direction dict, 汇总信息)。缺字段直接报错，不擅自补值。

    `allowed_ids` = 前端站点包网络里存在的段号集合；enriched 里多出来的段（前端包还没同步）
    不生成，避免页面出现"字段有、几何没有"的段。None = 不过滤。
    """
    payload = json.loads(enriched_path.read_text(encoding="utf-8"))
    edges = payload.get("edges")
    if not isinstance(edges, list) or not edges:
        raise SystemExit(f"[FAIL] {enriched_path} 没有 edges 数组")
    missing = []
    for edge in edges:
        for field in FIELDS:
            if field not in edge:
                missing.append(f"{edge.get('segment_id', '?')}.{field}")
        if not isinstance(edge.get("continuity"), dict):
            missing.append(f"{edge.get('segment_id', '?')}.continuity")
    if missing:
        # GZ enriched 由拓扑任务维护：字段没补齐时明确报错，不生成半份数据
        raise SystemExit(
            "[FAIL] enriched 缺方向/贯通字段（等拓扑任务更新后再生成）："
            + ", ".join(missing[:8])
            + (" …" if len(missing) > 8 else "")
        )

    selected = (
        edges
        if allowed_ids is None
        else [edge for edge in edges if edge["segment_id"] in allowed_ids]
    )
    if not selected:
        raise SystemExit(
            f"[FAIL] enriched 段号与前端网络无交集（{enriched_path}）：前端站点包可能待同步"
        )

    directions: dict[str, dict] = {}
    for edge in selected:
        segment_id = edge["segment_id"]
        continuity = {
            key: (edge.get("continuity") or {}).get(key) for key in CONTINUITY_FIELDS
        }
        item = {field: edge.get(field) for field in FIELDS}
        item["continuity"] = continuity
        sources = edge.get("field_sources") or {}
        picked = {key: sources.get(key) for key in SOURCE_KEYS if key in sources}
        if picked:
            item["field_sources"] = picked
        directions[segment_id] = item

    enrichment = payload.get("enrichment") or {}
    summary = {
        "site_id": enrichment.get("site_id"),
        "site_name": enrichment.get("site_name"),
        "is_simulated": payload.get("is_simulated"),
        "enriched_edges": len(edges),
        "generated": len(directions),
        "skipped": len(edges) - len(directions),
        "directions": dict(Counter(str(v.get("direction")) for v in directions.values())),
        "tail_connected": dict(
            Counter(str(v["continuity"].get("tail_connected")) for v in directions.values())
        ),
    }
    return directions, summary


def render_ts(source: dict, directions: dict, summary: dict, enriched_path: Path, repo_root: Path) -> str:
    rel = enriched_path.relative_to(repo_root).as_posix()
    # 每段一行紧凑 JSON：diff 可读（一行一段），产物体积远小于 indent=2 展开（GZ 段多）
    body_lines = [
        "  " + json.dumps(segment_id, ensure_ascii=False) + ": " + json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "," 
        for segment_id, item in directions.items()
    ]
    body = "{\n" + "\n".join(body_lines) + "\n}"
    scope_note = (
        f"//   前端网络段 {summary['generated']} / enriched {summary['enriched_edges']} 段"
        f"（跳过 {summary['skipped']} 段：前端站点包尚未同步，不能给不存在的段号写字段）"
        if summary["skipped"] > 0
        else f"//   前端网络段 {summary['generated']} / enriched {summary['enriched_edges']} 段（全部命中）"
    )
    lines = [
        "// ⚠️ 本文件由脚本 `work/frontend/tools/gen_station_directions.py` 从 enriched **只读生成**，勿手改。",
        f"// 来源：{rel}",
        f"//   site={summary['site_id']}（{summary['site_name']}）· enriched={summary['enriched_edges']} 段 · is_simulated={summary['is_simulated']}",
        scope_note,
        f"//   sha256={sha256_of(enriched_path)}",
        f"//   direction 分布：{json.dumps(summary['directions'], ensure_ascii=False)}",
        f"//   continuity.tail_connected 分布：{json.dumps(summary['tail_connected'], ensure_ascii=False)}",
        "// 口径：只是前端展示字段（非契约、不参与判级/路线）；缺值保持 null → 页面显示「—/未标定」；",
        "//       field_sources 保留 osm/derived/default 来源，页面不宣称真实车道/方向来自实测。",
        "import type { PackSegmentDirection } from './types.ts'",
        "",
        f"export const {source['const']}: Record<string, PackSegmentDirection> = " + body,
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="从 enriched 只读生成前端方向/车道/贯通字段")
    parser.add_argument("--check", action="store_true", help="只校验生成物是否与 enriched 同步")
    args = parser.parse_args()

    failures = 0
    for source in SOURCES:
        enriched_path = REPO_ROOT / source["enriched"]
        out_path = REPO_ROOT / source["out"]
        network_path = REPO_ROOT / source["network"]
        if not enriched_path.exists():
            print(f"[FAIL] 缺少 enriched：{enriched_path}", file=sys.stderr)
            failures += 1
            continue
        allowed_ids = network_segment_ids(network_path) if network_path.exists() else None
        directions, summary = build_directions(enriched_path, allowed_ids)
        content = render_ts(source, directions, summary, enriched_path, REPO_ROOT)
        if args.check:
            old = out_path.read_text(encoding="utf-8") if out_path.exists() else ""
            if old != content:
                print(f"[FAIL] {out_path.relative_to(REPO_ROOT)} 未与 enriched 同步，请重跑生成器", file=sys.stderr)
                failures += 1
            else:
                print(f"[OK] {source['key']}: {len(directions)} 段方向字段与 enriched 同步")
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8", newline="\n")
        print(
            f"[OK] {source['key']}: {len(directions)}/{summary['enriched_edges']} 段 → {out_path.relative_to(REPO_ROOT)}"
            f" · direction={summary['directions']} · tail_connected={summary['tail_connected']}"
        )
        if summary["skipped"] > 0:
            print(
                f"[WARN] {source['key']}: enriched 比前端网络多 {summary['skipped']} 段"
                f"（前端站点包待同步；本次只生成前端网络里存在的 {len(directions)} 段，不写不存在的段号）",
                file=sys.stderr,
            )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
