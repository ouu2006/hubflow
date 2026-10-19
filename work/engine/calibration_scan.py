"""标定扫描(T2 新增):网格扫 `x_safe × eps_harm_s`,产出 TC-17 三项判据对照表。

**这不是标定结论** —— 它只是把"数据一到就能跑"的扫描机制备好(IKMHMX 标定预案):
每组参数在**临时站点包**上跑 sample 与 real 两种网络,记录 TC-17 三项判据的实测值。
真正的标定结论要等池·P 的真实数据到位后由开发B 拍板,本脚本不代替该判断。

安全约束(硬):
  - **绝不写 `stations/` 真文件** —— 参数只改临时副本;
  - 每组输出只进临时目录(`--out` 指向临时路径),不碰 `work/engine/out/` 的基线产物;
  - 最终 CSV/Markdown 表落 `work/engine/out/calibration_scan/`(gitignore 范围,非基线)。

用法:
    python work/engine/calibration_scan.py [--grid "0.80,0.85:30,45"] [--out-dir <dir>]
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATIONS_DIR = REPO_ROOT / "stations"
DEFAULT_OUT_DIR = REPO_ROOT / "work" / "engine" / "out" / "calibration_scan"
DEFAULT_GRID = "0.80,0.85:30,45"

#: TC-17 三项判据在产物 comparison.tc17.criteria 下的键(结构以实际产物为准;
#: 解析时先打印键结构核对,缺键则该行记 None 并在表内注明,不猜)。
CRITERION_KEYS = (
    "max_eta_increase_s",
    "no_new_orange_red_segments",
    "total_travel_time_s",
)


def _parse_grid(text: str) -> list[tuple[float, float]]:
    """`"0.80,0.85:30,45"` → [(0.80,30),(0.80,45),(0.85,30),(0.85,45)]。"""
    left, right = text.split(":")
    xs = [float(v) for v in left.split(",") if v.strip()]
    eps = [float(v) for v in right.split(",") if v.strip()]
    if not xs or not eps:
        raise SystemExit(f"网格解析失败: {text!r}(形如 0.80,0.85:30,45)")
    return [(x, e) for x in xs for e in eps]


def _make_temp_stations(src: Path, dst: Path) -> None:
    """复制 src 下**只含 JSON** 的文件到 dst(不复制 sumo/ 子目录与非 JSON 文件)。"""
    dst.mkdir(parents=True, exist_ok=True)
    for item in sorted(src.iterdir()):
        if item.is_file() and item.suffix == ".json":
            shutil.copy2(item, dst / item.name)


def _patch_thresholds(stations_dir: Path, x_safe: float, eps_harm_s: float) -> None:
    """在临时站点包上改 decision 组两键(只动临时副本)。"""
    path = stations_dir / "thresholds.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    decision = data["decision"]
    decision["x_safe"] = x_safe
    decision["eps_harm_s"] = eps_harm_s
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_engine(mode: str, stations_dir: Path, out_dir: Path) -> Path:
    """跑一组 `--compare`(sample 或 real),返回产物 routes.json 路径。"""
    cmd = [
        sys.executable,
        str(REPO_ROOT / "work" / "engine" / "run.py"),
        *(["--sample"] if mode == "sample" else ["--network", "real"]),
        "--compare",
        "--stations",
        str(stations_dir),
        "--out",
        str(out_dir),
    ]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"run.py({mode}) 退出码 {proc.returncode}: {proc.stderr.strip()[-400:]}"
        )
    routes = out_dir / "routes.json"
    if not routes.is_file():
        raise RuntimeError(f"run.py({mode}) 未产出 {routes}")
    return routes


def _parse_tc17(routes_path: Path, *, print_structure: bool) -> dict:
    """从产物解析三项判据;键结构不符预期时如实记 None(不猜、不崩)。"""
    routes = json.loads(routes_path.read_text(encoding="utf-8"))
    tc17 = ((routes.get("comparison") or {}).get("tc17") or {})
    criteria = tc17.get("criteria") or {}
    if print_structure:
        print(f"    tc17.criteria 键结构: {sorted(criteria)}")
    out: dict = {}
    for key in CRITERION_KEYS:
        entry = criteria.get(key)
        if not isinstance(entry, dict):
            out[key] = None
            continue
        if key == "no_new_orange_red_segments":
            value = len(entry.get("new_vs_control") or [])
        elif key == "total_travel_time_s":
            value = entry.get("experimental")
        else:
            value = entry.get("experimental")
        out[key] = {"value": value, "passed": entry.get("passed")}
    return out


def _row(x_safe: float, eps_harm_s: float, mode: str, tc: dict) -> dict:
    """按卡片列名组一行:x_safe, eps_harm_s, tc17_1/2/3, pass_1/2/3, total_time, new_orange。"""
    c1, c2, c3 = (tc.get(k) for k in CRITERION_KEYS)

    def val(entry):
        return entry["value"] if entry else None

    def ok(entry):
        return entry["passed"] if entry else None

    return {
        "x_safe": x_safe,
        "eps_harm_s": eps_harm_s,
        "mode": mode,
        "tc17_1_max_eta_increase_s": val(c1),
        "pass_1": ok(c1),
        "tc17_2_new_orange_count": val(c2),
        "pass_2": ok(c2),
        "tc17_3_total_time_s": val(c3),
        "pass_3": ok(c3),
        "total_time": val(c3),
        "new_orange": val(c2),
    }


def _write_reports(rows: list[dict], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "calibration_scan.csv"
    md_path = out_dir / "calibration_scan.md"
    fields = list(rows[0].keys())
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# 标定扫描表(T2 · calibration_scan)",
        "",
        "> **本表不是标定结论**——只是网格扫描的实测记录。标定结论须待池·P 真实数据",
        "> 到位后由开发B 拍板。每组在**临时站点包**上跑(stations/ 真文件零改动),",
        "> sample 与 real 两种网络各一行。",
        "",
        "列口径:tc17_1 = `max_eta_increase_s.experimental`(先入车不恶化判据的实验组值);",
        "tc17_2 = `no_new_orange_red_segments` 的 `new_vs_control` 条数(无新增橙/红判据);",
        "tc17_3 = `total_travel_time_s.experimental`(总耗时判据的实验组值);",
        "pass_1/2/3 = 三项判据的 `passed`;total_time 同 tc17_3、new_orange 同 tc17_2(卡片列名照录)。",
        "",
        "| x_safe | eps_harm_s | mode | tc17_1(s) | pass_1 | tc17_2(new) | pass_2 | tc17_3(s) | pass_3 | total_time | new_orange |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['x_safe']} | {r['eps_harm_s']} | {r['mode']} "
            f"| {r['tc17_1_max_eta_increase_s']} | {r['pass_1']} "
            f"| {r['tc17_2_new_orange_count']} | {r['pass_2']} "
            f"| {r['tc17_3_total_time_s']} | {r['pass_3']} "
            f"| {r['total_time']} | {r['new_orange']} |"
        )
    lines += ["", "注:判据结构以产物 `comparison.tc17.criteria` 实际键为准;若键缺失,该格为 None(不猜值)。"]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--grid", default=DEFAULT_GRID,
                        help='形如 "0.80,0.85:30,45"(x_safe 集合:eps_harm_s 集合)')
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    ns = parser.parse_args(argv)

    grid = _parse_grid(ns.grid)
    print(f"[scan] 网格 {len(grid)} 组 × 2 网络(sample/real)= {len(grid) * 2} 行")
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="hubflow-calib-") as tmp:
        tmp_dir = Path(tmp)
        stations_tmp = tmp_dir / "stations"
        _make_temp_stations(DEFAULT_STATIONS_DIR, stations_tmp)
        copied = sorted(p.name for p in stations_tmp.iterdir())
        print(f"[scan] 临时站点包(只含 JSON,不含 sumo/): {copied}")

        for idx, (x_safe, eps_harm_s) in enumerate(grid):
            _patch_thresholds(stations_tmp, x_safe, eps_harm_s)
            for mode in ("sample", "real"):
                tag = f"g{idx}_{mode}"
                out_dir = tmp_dir / f"out_{tag}"
                try:
                    routes = _run_engine(mode, stations_tmp, out_dir)
                    tc = _parse_tc17(routes, print_structure=(idx == 0 and mode == "sample"))
                    row = _row(x_safe, eps_harm_s, mode, tc)
                    print(f"[scan] x_safe={x_safe} eps={eps_harm_s} {mode:6s} "
                          f"pass=({row['pass_1']},{row['pass_2']},{row['pass_3']})")
                except RuntimeError as exc:
                    print(f"[scan] x_safe={x_safe} eps={eps_harm_s} {mode:6s} 失败: {exc}")
                    row = _row(x_safe, eps_harm_s, mode, {})
                    row["mode"] = f"{mode}(FAILED)"
                rows.append(row)

    csv_path, md_path = _write_reports(rows, Path(ns.out_dir))
    print(f"[scan] 表已落盘: {csv_path} / {md_path}")
    print("[scan] 再次声明:本表是扫描记录,不是标定结论。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
