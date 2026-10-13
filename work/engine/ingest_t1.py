"""T1 点位表 → `stations/points.json`(开发规范第 7 节、表格模板说明第三 / 十二节)。

输入:`T1 点位表` 导出的 CSV(表头 = 模板里的列名,**逐字对齐**,行顺序无关)
输出:`stations/points.json`(结构由 Issue #39 定稿,见 `docs/数据契约.md` 第六节)

口径(三条"不许猜"):
  - **必填列缺失 / 单元格空白 → 报错退出并指出行号**,不许用默认值悄悄补上;
  - `role` 只取 `boundary` / `internal`;`type` 只取五类,越界即报错;
  - `detector` 类点位**必须**带 `detector_role` 与 `sumo_edge_id`。

幂等:输出按 `point_id` 排序后再落盘 —— 同一份表格跑两次**逐字节一致**,
      且**行顺序无关**(表格里换个行序,产物不变)。产物里**不写墙钟时间**
      (否则重跑必然 diff);来源记录只留「表格文件名 + 版本 + 表内 date 列」。

用法:
  python work/engine/ingest_t1.py --in samples/T1_sample.csv --out stations/points.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

#: T1 的列定义(表格模板说明第三节,列名逐字对齐,**不许自己改名**)
T1_COLUMNS = (
    "point_id", "name", "type", "lon", "lat", "segment_id", "offset_m", "direction",
    "capacity_vph", "role", "sumo_edge_id", "detector_role", "source", "verified",
    "filler", "date",
)

#: 所有点位都必填的列
REQUIRED_ALWAYS = (
    "point_id", "name", "type", "lon", "lat", "segment_id", "offset_m", "direction",
    "role", "source", "verified", "filler", "date",
)

#: 按点位类型追加的必填列
REQUIRED_BY_TYPE: dict[str, tuple[str, ...]] = {
    "dropoff": ("capacity_vph",),
    "pickup": ("capacity_vph",),
    "waiting": ("capacity_vph",),
    "detector": ("detector_role", "sumo_edge_id"),
    "junction": (),
}

#: 点位类型(五选一,封闭取值)
POINT_TYPES = ("dropoff", "pickup", "waiting", "detector", "junction")

#: 点位角色(封闭取值;只有 boundary 允许数据同化回灌)
SECTION_ROLES = ("boundary", "internal")


class ConvertError(SystemExit):
    """转换失败 —— 带行号退出,不用默认值悄悄补上。"""


def read_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """读 CSV,返回 (逐行 dict + 文件行号, 表头列名)。表头缺列即报错。"""
    if not path.is_file():
        raise ConvertError(f"表格文件不存在:{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        header = list(reader.fieldnames or [])
        missing = [c for c in T1_COLUMNS if c not in header]
        if missing:
            raise ConvertError(
                f"T1 表头缺列:{'、'.join(missing)}\n"
                f"  表头列名必须与模板逐字对齐(表格模板说明第三节)\n"
                f"  实际表头:{header}"
            )
        extra = [c for c in header if c not in T1_COLUMNS]
        rows: list[dict[str, Any]] = []
        for raw in reader:
            rows.append({"__line__": reader.line_num, **raw})
        if extra:
            print(f"[ingest_t1] 提示:表头有模板外的列,已忽略:{'、'.join(extra)}")
    return rows, header


def _cell(row: dict[str, Any], column: str) -> str:
    return str(row.get(column) or "").strip()


def validate_row(row: dict[str, Any]) -> None:
    """逐行校验;任一条不过就带行号报错退出。"""
    line = row["__line__"]
    point_type = _cell(row, "type")
    if point_type not in POINT_TYPES:
        raise ConvertError(
            f"第 {line} 行:type={point_type!r} 不在封闭取值内(仅 {' / '.join(POINT_TYPES)})"
        )
    required = REQUIRED_ALWAYS + REQUIRED_BY_TYPE[point_type]
    for column in required:
        if not _cell(row, column):
            raise ConvertError(f"第 {line} 行:{column} 为空(必填列不许空白,不许用默认值补)")
    role = _cell(row, "role")
    if role not in SECTION_ROLES:
        raise ConvertError(
            f"第 {line} 行:role={role!r} 不在封闭取值内(仅 {' / '.join(SECTION_ROLES)})"
        )
    for column in ("lon", "lat", "offset_m"):
        try:
            float(_cell(row, column))
        except ValueError:
            raise ConvertError(f"第 {line} 行:{column}={_cell(row, column)!r} 不是数值") from None


def _to_point(row: dict[str, Any]) -> dict[str, Any]:
    """把一行折成一个 point 对象(字段名与 #39 定稿的 points.json 一致)。"""
    def num(column: str) -> float:
        return float(_cell(row, column))

    def opt_num(column: str) -> float | None:
        value = _cell(row, column)
        return float(value) if value else None

    def opt_str(column: str) -> str | None:
        return _cell(row, column) or None

    return {
        "point_id": _cell(row, "point_id"),
        "name": _cell(row, "name"),
        "type": _cell(row, "type"),
        "lon": num("lon"),
        "lat": num("lat"),
        "segment_id": _cell(row, "segment_id"),
        "offset_m": num("offset_m"),
        "direction": _cell(row, "direction"),
        "capacity_vph": opt_num("capacity_vph"),
        "role": _cell(row, "role"),
        "sumo_edge_id": opt_str("sumo_edge_id"),
        "detector_role": opt_str("detector_role"),
        "source": _cell(row, "source"),
        "verified": _cell(row, "verified"),
        "filler": _cell(row, "filler"),
        "date": _cell(row, "date"),
    }


def table_version_from_name(path: Path) -> str:
    """从表格文件名里取版本号(约定形如 `T1_点位表_20261013_v1.csv`);取不到填 `无（基线）`。"""
    stem = path.stem
    for part in reversed(stem.split("_")):
        if part.lower().startswith("v") and part[1:].isdigit():
            return part
    return "无（基线）"


def convert(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """读表 → 校验 → 组装 points.json。返回 (产物, 逐行 dict)。"""
    rows, _header = read_rows(path)
    if not rows:
        raise ConvertError(f"表格里一行都没有:{path}(至少要有表头 + 一行数据)")

    for row in rows:
        validate_row(row)

    points = sorted((_to_point(row) for row in rows), key=lambda p: p["point_id"])

    dates = sorted({p["date"] for p in points})
    payload = {
        "is_simulated": True,
        "schema_version": "1.0",
        "crs": "WGS-84",
        "note": (
            f"由 T1 点位表转换生成(表格模板说明第三节);"
            f"表内 date 列 {dates[0] if len(dates) == 1 else ' / '.join(dates)}。"
            "本文件**不许手改** —— 要改就改表格、升版本号、重跑 work/engine/ingest_t1.py"
        ),
        "source": {
            "table_file": path.name,
            "table_version": table_version_from_name(path),
            "converter": "work/engine/ingest_t1.py",
            "rows": len(rows),
        },
        "points": points,
    }
    return payload, rows


def report(rows: list[dict[str, Any]], points: list[dict[str, Any]]) -> None:
    """报数:读了多少行、生成多少条、跳过几行(跳过要写原因)。"""
    by_type: dict[str, int] = {}
    for point in points:
        by_type[point["type"]] = by_type.get(point["type"], 0) + 1
    print(f"[ingest_t1] 读入 {len(rows)} 行,生成 {len(points)} 条,跳过 0 行(无跳过:条数必须等于行数)")
    print("[ingest_t1] 五类点位覆盖:" + " / ".join(
        f"{t}={by_type.get(t, 0)}" for t in POINT_TYPES
    ))
    missing_types = [t for t in POINT_TYPES if by_type.get(t, 0) == 0]
    if missing_types:
        print(
            f"[ingest_t1] ⚠️ 提示(不报错):以下点位类型在本次表格里一条都没有 "
            f"{' / '.join(missing_types)} —— 填表纪律要求五类各至少 1 条(W1 判定)",
            file=sys.stderr,
        )
    boundaries = [p["point_id"] for p in points if p["type"] == "detector" and p["role"] == "boundary"]
    print(f"[ingest_t1] boundary 断面 {len(boundaries)} 个:{'、'.join(boundaries) or '(无)'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="T1 点位表 → stations/points.json")
    parser.add_argument("--in", required=True, dest="src", help="T1 导出的 CSV")
    parser.add_argument("--out", required=True, dest="dst", help="输出 points.json 路径")
    parser.add_argument("--dry-run", action="store_true", help="只校验不落盘")
    ns = parser.parse_args(argv)

    payload, rows = convert(Path(ns.src))
    report(rows, payload["points"])

    if ns.dry_run:
        print("[ingest_t1] --dry-run:校验通过,未落盘")
        return 0

    dst = Path(ns.dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    dst.write_text(text, encoding="utf-8")
    if not dst.is_file() or dst.stat().st_size <= 0:
        raise ConvertError(f"产物未生成:{dst}")
    print(f"[ingest_t1] 已写入 {dst}({len(text.encode('utf-8'))} 字节)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
