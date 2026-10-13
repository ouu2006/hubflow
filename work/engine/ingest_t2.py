"""T2 路段属性核对表 → **补录**进 `stations/network.json`(开发规范第 7 节、表格模板说明第四 / 十二节)。

输入:T2 导出的 CSV(表头 = 模板里的列名,逐字对齐,行顺序无关)+ `stations/network.json`
输出:`stations/network.json`(**只补属性,不改拓扑**)+ `stations/map_source.json`(核对痕迹)

口径:
  - **只补属性**:`length_m` / `lanes` / `speed_limit_kmh`→`speed_limit` / `c_vph`→`capacity_vph`;
    节点 / 边的**拓扑一个都不动**(拓扑是 Issue #37 的 `map_ingest.py` 产的);
  - **底图核对列只许 `一致` / `不一致` / `待核实`,没有空白格**;填 `不一致` 必须写差异原因;
  - **`c_vph` 拿不到官方值就标【待标定】**,脚本剥掉标记取值并把"待标定"记进 `map_source.json` —— **不编数**;
  - `oneway` / 底图核对 / 差异原因 / `verified` / `filler` / `date` 都是**核对痕迹,不是引擎要读的属性**
    → 写进 `map_source.json`(开发规范第 7 节:network.json 的来源记录写在 map_source.json)。

幂等:同一份表格跑两次产物**逐字节一致**;`t2_audit` 按 `segment_id` 排序,
      产物里**不写墙钟时间**。

用法:
  python work/engine/ingest_t2.py --in samples/T2_sample.csv \\
      --net stations/network.json --map-source stations/map_source.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

#: T2 的列定义(表格模板说明第四节,列名逐字对齐,**不许自己改名**)
T2_COLUMNS = (
    "segment_id", "from_node", "to_node", "length_m", "lanes", "speed_limit_kmh",
    "c_vph", "oneway", "底图核对", "差异原因", "verified", "filler", "date",
)

#: T2 列 → network.json 的边字段(**两处改名,见 DESIGN.md 第七节**)
COLUMN_TO_EDGE_FIELD = {
    "length_m": "length_m",
    "lanes": "lanes",
    "speed_limit_kmh": "speed_limit",   # 手册 8.2 的边字段名是 speed_limit
    "c_vph": "capacity_vph",            # 手册 8.2 用 capacity_vph(≠ segments.json 的 c_vph,后者是因素修正后)
}

#: 底图核对列只许这三种取值(TC-15 判定口径,**没有空白格**)
BASEMAP_CHECK_VALUES = ("一致", "不一致", "待核实")

#: 【待标定】标记 —— 池·S 拿不到官方值时写的
PENDING_MARK = "【待标定】"
_NUMBER = re.compile(r"^-?\d+(?:\.\d+)?")


class ConvertError(SystemExit):
    """转换失败 —— 带行号退出,不用默认值悄悄补上。"""


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def read_rows(path: Path) -> list[dict[str, Any]]:
    """读 CSV,逐行带文件行号。表头缺列即报错。"""
    if not path.is_file():
        raise ConvertError(f"表格文件不存在:{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        header = list(reader.fieldnames or [])
        missing = [c for c in T2_COLUMNS if c not in header]
        if missing:
            raise ConvertError(
                f"T2 表头缺列:{'、'.join(missing)}\n"
                f"  表头列名必须与模板逐字对齐(表格模板说明第四节)\n"
                f"  实际表头:{header}"
            )
        extra = [c for c in header if c not in T2_COLUMNS]
        rows = [{"__line__": reader.line_num, **raw} for raw in reader]
        if extra:
            print(f"[ingest_t2] 提示:表头有模板外的列,已忽略:{'、'.join(extra)}")
    return rows


def _cell(row: dict[str, Any], column: str) -> str:
    return str(row.get(column) or "").strip()


def parse_number(raw: str, line: int, column: str) -> tuple[float, bool]:
    """解析数值单元格。返回 (数值, 是否带【待标定】)。

    **不许编数**:拿不到官方值就带【待标定】,这里剥标记取值并把"待标定"如实记下来。
    """
    pending = PENDING_MARK in raw
    cleaned = raw.replace(PENDING_MARK, "").strip()
    matched = _NUMBER.match(cleaned)
    if not matched:
        raise ConvertError(f"第 {line} 行:{column}={raw!r} 解析不出数值")
    return float(matched.group(0)), pending


def validate_row(row: dict[str, Any]) -> None:
    line = row["__line__"]
    for column in T2_COLUMNS:
        if not _cell(row, column) and column != "差异原因":
            raise ConvertError(f"第 {line} 行:{column} 为空(必填列不许空白,不许用默认值补)")
    check = _cell(row, "底图核对")
    if check not in BASEMAP_CHECK_VALUES:
        raise ConvertError(
            f"第 {line} 行:底图核对={check!r} 不在 {' / '.join(BASEMAP_CHECK_VALUES)} 内"
            "(TC-15:没有空白格,不确定就写「待核实」)"
        )
    if check == "不一致" and not _cell(row, "差异原因"):
        raise ConvertError(f"第 {line} 行:底图核对=不一致,必须写差异原因(TC-15)")


def table_version_from_name(path: Path) -> str:
    """从表格文件名里取版本号;取不到填 `无（基线）`。"""
    for part in reversed(path.stem.split("_")):
        if part.lower().startswith("v") and part[1:].isdigit():
            return part
    return "无（基线）"


def apply_to_network(
    net: dict[str, Any],
    rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """把 T2 的属性补录进 network.json 的边。**拓扑字段一个都不碰。**"""
    edges = net.get("edges")
    if not isinstance(edges, list) or not edges:
        raise ConvertError("network.json 缺 edges 数组(统一图结构,手册 8.2)")
    by_section = {str(e.get("section")): e for e in edges}

    audit: list[dict[str, Any]] = []
    for row in rows:
        validate_row(row)
        line = row["__line__"]
        segment_id = _cell(row, "segment_id")
        edge = by_section.get(segment_id)
        if edge is None:
            raise ConvertError(
                f"第 {line} 行:segment_id={segment_id!r} 在 network.json 的 edges[].section 里找不到"
                "(T1/T2 的 segment_id 与边的 section 一一对应;找不到说明这条没填完)"
            )
        # 拓扑一致性:表里的起终点必须与路网的 from / to 对得上 —— 对不上说明表与路网不同源
        for column, field in (("from_node", "from"), ("to_node", "to")):
            if _cell(row, column) != str(edge.get(field)):
                raise ConvertError(
                    f"第 {line} 行:{column}={_cell(row, column)!r} 与 network.json 里 "
                    f"{edge.get('id')} 的 {field}={edge.get(field)!r} 不一致"
                    "(本脚本只补属性、不改拓扑;拓扑归 map_ingest.py,Issue #37)"
                )

        pending_fields: list[str] = []
        for column, field in COLUMN_TO_EDGE_FIELD.items():
            value, pending = parse_number(_cell(row, column), line, column)
            edge[field] = int(value) if value.is_integer() else value
            if pending:
                pending_fields.append(column)

        audit.append({
            "segment_id": segment_id,
            "sumo_edge_id": str(edge.get("id")),
            "basemap_check": _cell(row, "底图核对"),
            "diff_reason": _cell(row, "差异原因") or None,
            "oneway": _cell(row, "oneway"),
            "pending_fields": pending_fields,
            "verified": _cell(row, "verified"),
            "filler": _cell(row, "filler"),
            "date": _cell(row, "date"),
        })

    audit.sort(key=lambda item: item["segment_id"])
    return net, audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="T2 路段属性核对表 → 补录进 stations/network.json")
    parser.add_argument("--in", required=True, dest="src", help="T2 导出的 CSV")
    parser.add_argument("--net", required=True, dest="net", help="stations/network.json")
    parser.add_argument("--map-source", default="", dest="map_source",
                        help="stations/map_source.json(核对痕迹写这里;留空则只更新 network.json)")
    parser.add_argument("--out", default="", dest="out_net",
                        help="输出 network.json 路径;留空则就地覆盖 --net")
    parser.add_argument("--dry-run", action="store_true", help="只校验不落盘")
    ns = parser.parse_args(argv)

    src = Path(ns.src)
    net_path = Path(ns.net)
    if not net_path.is_file():
        raise ConvertError(f"network.json 不存在:{net_path}(先跑 Issue #37 的 map_ingest.py)")

    rows = read_rows(src)
    if not rows:
        raise ConvertError(f"表格里一行都没有:{src}(至少要有表头 + 一行数据)")

    net, audit = apply_to_network(read_json(net_path), rows)

    attributes = net.setdefault("attributes", {})
    attributes["t2_source"] = {
        "table_file": src.name,
        "table_version": table_version_from_name(src),
        "converter": "work/engine/ingest_t2.py",
        "rows": len(rows),
    }

    by_check: dict[str, int] = {}
    for item in audit:
        by_check[item["basemap_check"]] = by_check.get(item["basemap_check"], 0) + 1
    touched = [item["segment_id"] for item in audit]
    pending = sorted({f for item in audit for f in item["pending_fields"]})
    print(f"[ingest_t2] 读入 {len(rows)} 行,补录 {len(audit)} 条路段,跳过 0 行")
    print("[ingest_t2] 底图核对分布:" + " / ".join(
        f"{k}={by_check.get(k, 0)}" for k in BASEMAP_CHECK_VALUES
    ))
    print(f"[ingest_t2] 覆盖路段:{'、'.join(touched)}")
    if pending:
        print(f"[ingest_t2] ⚠️ 带【待标定】的列(已记进 map_source.json):{'、'.join(pending)}",
              file=sys.stderr)

    if ns.dry_run:
        print("[ingest_t2] --dry-run:校验通过,未落盘")
        return 0

    out_net = Path(ns.out_net) if ns.out_net else net_path
    out_net.parent.mkdir(parents=True, exist_ok=True)
    net_text = json.dumps(net, ensure_ascii=False, indent=2) + "\n"
    out_net.write_text(net_text, encoding="utf-8")
    print(f"[ingest_t2] 已写入 {out_net}({len(net_text.encode('utf-8'))} 字节)")

    if ns.map_source:
        map_path = Path(ns.map_source)
        if not map_path.is_file():
            raise ConvertError(f"map_source.json 不存在:{map_path}(来源记录要写在这里)")
        payload = read_json(map_path)
        payload["t2_audit"] = audit
        map_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        map_path.write_text(map_text, encoding="utf-8")
        print(f"[ingest_t2] 已写入 {map_path}({len(map_text.encode('utf-8'))} 字节,{len(audit)} 条核对痕迹)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
