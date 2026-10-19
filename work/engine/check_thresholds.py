"""阈值卫生机检(只读;T2 新增)。

对 `stations/thresholds.json` 的 decision / grading 两组做结构性检查,**不改任何文件**。
判定值全部取自 `00-公共约束.md` 与 T2 卡;本脚本只报告现状 —— **包括违规**
(当前样例站点包 `x_safe=0.85` > 判级橙档边界 0.8,这是已知的结构性矛盾,
T2 的职责是让它机检可见,不是改阈值让它变绿)。

检查项(每项 PASS / WARN / FAIL;任一 FAIL → 退出码 1):

| # | 检查 | 判据 |
|---|---|---|
| 1 | 饱和度安全阈值 vs 判级橙档 | `decision.x_safe ≤ grading.level_bounds` 中 `indicator=="x"` 的第 2 个边界(橙档上沿) |
| 2 | 再疏导触发阈值 | `decision.reroute_threshold_s` 存在且 > 0(缺键 = WARN:代码回落 `eps_harm_s` 兼容路径) |
| 3 | 时段粒度 | `decision.slot_minutes` 整除 60 |
| 4 | 不伤害前车阈值 | `decision.eps_harm_s > 0` |
| 5 | 饱和度安全阈值量纲 | `0 < decision.x_safe ≤ 1` |

用法:
    python work/engine/check_thresholds.py [--stations <dir>]

退出码: 0 = 无 FAIL(可有 WARN);1 = 有 FAIL 或文件/结构不可读。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_STATIONS_DIR = Path(__file__).resolve().parents[2] / "stations"

#: level_bounds 里 indicator=="x" 的边界语义:[绿, 橙, 红] 上沿;第 2 个 = 橙档上沿。
ORANGE_BOUND_INDEX = 1


def _load_thresholds(stations_dir: Path) -> dict:
    path = stations_dir / "thresholds.json"
    if not path.is_file():
        raise SystemExit(f"[FAIL] 找不到 {path}(--stations 指到含 thresholds.json 的目录)")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _orange_bound(grading: dict) -> float | None:
    for entry in grading.get("level_bounds") or []:
        if entry.get("indicator") == "x":
            bounds = entry.get("bounds") or []
            if len(bounds) > ORANGE_BOUND_INDEX:
                return float(bounds[ORANGE_BOUND_INDEX])
    return None


def check(stations_dir: Path) -> int:
    data = _load_thresholds(stations_dir)
    decision = data.get("decision") or {}
    grading = data.get("grading") or {}
    failures = 0

    def report(name: str, verdict: str, detail: str) -> None:
        nonlocal failures
        if verdict == "FAIL":
            failures += 1
        print(f"[{verdict}] {name}: {detail}")

    # ── 1. x_safe vs 判级橙档上沿 ──
    x_safe = decision.get("x_safe")
    orange = _orange_bound(grading)
    if x_safe is None or orange is None:
        report("x_safe vs 橙档", "FAIL",
               f"取不到判据(decision.x_safe={x_safe!r}, grading x 橙档边界={orange!r})")
    elif float(x_safe) > orange:
        report("x_safe vs 橙档", "FAIL",
               f"x_safe={x_safe} > 判级橙档上沿 {orange} —— 决策侧安全饱和度已越过判级橙档,"
               "结构性矛盾(池·P 标定时须同桌解决;本脚本只报告,不改值)")
    elif float(x_safe) == orange:
        report("x_safe vs 橙档", "WARN", f"x_safe={x_safe} 恰等于橙档上沿 {orange}(边界饱和)")
    else:
        report("x_safe vs 橙档", "PASS", f"x_safe={x_safe} ≤ 橙档上沿 {orange}")

    # ── 2. reroute_threshold_s 存在且 > 0 ──
    if "reroute_threshold_s" not in decision:
        report("reroute_threshold_s", "WARN",
               "decision 组缺键 —— reroute.py 回落 eps_harm_s(旧站点包兼容路径);"
               "新站点包应补该键(占位值 30,待池·P 标定)")
    else:
        value = decision["reroute_threshold_s"]
        try:
            ok = float(value) > 0
        except (TypeError, ValueError):
            ok = False
        report("reroute_threshold_s", "PASS" if ok else "FAIL",
               f"reroute_threshold_s={value!r}(存在且 > 0)" if ok else f"reroute_threshold_s={value!r}(须 > 0)")

    # ── 3. slot_minutes 整除 60 ──
    slot_minutes = decision.get("slot_minutes")
    try:
        slot_ok = slot_minutes is not None and int(slot_minutes) > 0 and 60 % int(slot_minutes) == 0
    except (TypeError, ValueError):
        slot_ok = False
    report("slot_minutes 整除 60", "PASS" if slot_ok else "FAIL",
           f"slot_minutes={slot_minutes!r}" + ("(60 的整数约数)" if slot_ok else "(须为 60 的正整数约数)"))

    # ── 4. eps_harm_s > 0 ──
    eps = decision.get("eps_harm_s")
    try:
        eps_ok = eps is not None and float(eps) > 0
    except (TypeError, ValueError):
        eps_ok = False
    report("eps_harm_s > 0", "PASS" if eps_ok else "FAIL",
           f"eps_harm_s={eps!r}" + ("(> 0)" if eps_ok else "(须 > 0)"))

    # ── 5. 0 < x_safe ≤ 1 ──
    try:
        range_ok = x_safe is not None and 0 < float(x_safe) <= 1
    except (TypeError, ValueError):
        range_ok = False
    report("0 < x_safe ≤ 1", "PASS" if range_ok else "FAIL",
           f"x_safe={x_safe!r}" + ("(量纲合法)" if range_ok else "(须落在 (0,1])"))

    print(f"\n结论: {'有 FAIL' if failures else '无 FAIL'}(FAIL {failures} 项)"
          f"—— stations_dir={stations_dir}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stations", default=str(DEFAULT_STATIONS_DIR), dest="stations_dir")
    ns = parser.parse_args(argv)
    return check(Path(ns.stations_dir))


if __name__ == "__main__":
    sys.exit(main())
