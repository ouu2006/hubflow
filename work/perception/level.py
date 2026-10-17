r"""五步判级：四项指标 → 路段拥堵等级（`level.py`，**写手：开发B**）。

> **两次入库**：文件从 `archive/task-three-page-pipeline` 分支**找回原件**（IKMF1S「先找回再重写」），
> 本版只做两处适配：① 阈值读当前 `stations/thresholds.json` 的 **`grading` 组**（旧结构是 `grade`）；
> ② 补 CI 四项加权与 self-test 口径。判级**一套代码两条链路共用，不按 `source` 分支**。

五步（手册 §6.3，顺序不能换）：
| 步 | 做什么 |
|---|---|
| ① 可用性门 | `data_age_s > grading.data_freshness_s` 或 `confidence < grading.confidence_min` → 灰色「数据不可用」 |
| ② 硬触发 | `grading.hard_trigger_factor_ids` 命中 → 直接 `grading.hard_trigger_level`（不看四项） |
| ③ 四项并列取最高 | x / v / k / L_q 各算一档，**取最高档**（不做平均）；边界读 `grading.level_bounds` |
| ④ 因素修正 | 按 `factors_applied` 合成容量；合成后不低于 `grading.factor_floor` |
| ⑤ 时间维防抖 | 升档立即、降档需连续 `grading.hysteresis_periods` 个周期 |

**铁律**：阈值一律读 `stations/thresholds.json`，代码里不写死判级数字；同一输入连跑 3 次一致（M1-3）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DIR = Path(__file__).resolve().parent
ROOT = DIR.parents[1]
STATIONS = ROOT / "stations"

LEVEL_NAME = {1: "畅通", 2: "缓行", 3: "拥堵", 4: "严重拥堵"}
#: 指标名 → 记录字段（v 用速度比；见 four_metrics_level 的 v 分支）
INDICATOR_FIELDS = {"x": "x", "v": "v_kmh", "k": "k_vpk", "L_q": "L_q_m", "T_d": "T_d_min"}


def load_thresholds() -> dict:
    p = STATIONS / "thresholds.json"
    if not p.is_file():
        raise SystemExit(f"缺 {p}（判级阈值必须读站点包，代码里不写死）")
    th = json.loads(p.read_text(encoding="utf-8"))
    if "grading" not in th:
        raise SystemExit(f"{p} 缺 grading 组（判级参数组）")
    return th


def _grading(th: dict) -> dict:
    return th["grading"]


def availability_gate(rec: dict, grading: dict) -> tuple[bool, str | None]:
    """① 可用性门：数据过旧 / 置信度不足 → 数据不可用（灰档）。"""
    age = rec.get("data_age_s")
    max_age = grading.get("data_freshness_s")
    if isinstance(age, (int, float)) and isinstance(max_age, (int, float)) and age > max_age:
        return False, "数据过旧"
    conf = rec.get("confidence")
    conf_min = grading.get("confidence_min")
    if isinstance(conf, (int, float)) and isinstance(conf_min, (int, float)) and conf < conf_min:
        return False, "置信度不足"
    return True, None


def hard_trigger(rec: dict, grading: dict) -> int | None:
    """② 硬触发：事故封道 / 临时管制直接触发高档（因素编号来自站点包，不写死）。"""
    ids = set(grading["hard_trigger_factor_ids"])
    applied = {f.get("factor_id") for f in rec.get("factors_applied", [])}
    if ids & applied:
        return int(grading["hard_trigger_level"])
    return None


def _indicator_level(value: float, bounds: list[float]) -> int:
    """按指标边界算档：升序（x/k/L_q）与降序（v）都按「比几个边界更差」计数。"""
    if len(bounds) < 3:
        raise SystemExit("level_bounds 每条指标必须给 3 个边界（四档）")
    if bounds[0] < bounds[-1]:          # 升序：越大越堵
        return min(4, 1 + sum(1 for b in bounds if value >= b))
    return min(4, 1 + sum(1 for b in bounds if value < b))  # 降序：越小越堵（v 速度）


def four_metrics_level(rec: dict, grading: dict) -> tuple[int, dict]:
    """③ 四项并列取最高（不做平均）。

    `grading.level_bounds` 里每个指标的 `bounds` 单位就是该指标自己的单位
    （x 无量纲 / v 为 km/h / k 为辆·km⁻¹ / L_q 为 m），升序降序由 `_indicator_level` 判方向——
    **不在代码里换算成速度比**（旧实现误按 v/v_f 算，已随 IKMF1S 审查整改）。
    """
    per: dict[str, int] = {}
    for item in grading.get("level_bounds", []):
        ind = item.get("indicator")
        field = INDICATOR_FIELDS.get(ind)
        if field is None:
            continue
        val = rec.get(field)
        if not isinstance(val, (int, float)):
            continue
        per[ind] = _indicator_level(float(val), [float(b) for b in item.get("bounds", [])])
    level = max(per.values()) if per else 1
    return level, per


def factor_correction(rec: dict, grading: dict) -> tuple[dict, float]:
    """④ 因素修正：合成系数（相乘），合成后不低于 factor_floor；只改容量，再回灌 ③。"""
    floor = float(grading["factor_floor"])
    coeff = 1.0
    applied = rec.get("factors_applied") or []
    for f in applied:
        mult = f.get("multiplier")
        if isinstance(mult, (int, float)) and f.get("target") in ("c", "lanes"):
            coeff *= float(mult)
    coeff = max(floor, coeff) if applied else 1.0
    fixed = dict(rec)
    base_c = rec.get("c_base_vph")
    if coeff != 1.0 and isinstance(base_c, (int, float)):
        fixed["c_vph"] = round(float(base_c) * coeff, 1)
        q = rec.get("q_vph")
        if isinstance(q, (int, float)) and fixed["c_vph"]:
            fixed["x"] = round(float(q) / fixed["c_vph"], 3)
    return fixed, coeff


def congestion_index(rec: dict, grading: dict) -> float:
    """CI = 四项加权（只展示、不判级；手册 §6.5 第 1 条）。权重与参考值读站点包。"""
    ref = grading.get("ref", {})
    weights = {w.get("indicator"): float(w.get("w", 0)) for w in grading.get("weights", [])}
    queue_ref = 0.0
    for item in grading.get("level_bounds", []):
        if item.get("indicator") == "L_q":
            bounds = item.get("bounds") or []
            queue_ref = float(bounds[-1]) if bounds else 0.0
    norms: dict[str, float] = {}
    x = rec.get("x")
    if isinstance(x, (int, float)) and ref.get("x_ref"):
        norms["x"] = min(1.0, max(0.0, float(x) / float(ref["x_ref"])))
    v = rec.get("v_kmh")
    if isinstance(v, (int, float)) and ref.get("v_jam_kmh"):
        norms["v"] = min(1.0, max(0.0, float(ref["v_jam_kmh"]) / max(1e-6, float(v))))
    lq = rec.get("L_q_m")
    if isinstance(lq, (int, float)) and queue_ref > 0:
        norms["L_q"] = min(1.0, max(0.0, float(lq) / queue_ref))
    td = rec.get("T_d_min")
    if isinstance(td, (int, float)) and ref.get("T_ref_min"):
        norms["T_d"] = min(1.0, max(0.0, float(td) / float(ref["T_ref_min"])))
    ci = sum(weights.get(k, 0.0) * norms.get(k, 0.0) for k in weights) * 100.0
    return round(ci, 1)


class Debouncer:
    """⑤ 时间维防抖：升档立即、降档需连续 N 个统计周期（N 读站点包）。"""

    def __init__(self, periods: int):
        self.periods = max(1, int(periods))
        self.state: dict[str, dict] = {}

    def apply(self, seg_id: str, raw_level: int) -> int:
        st = self.state.setdefault(seg_id, {"level": raw_level, "pending": None, "count": 0})
        cur = st["level"]
        if raw_level > cur:
            st.update(level=raw_level, pending=None, count=0)
            return raw_level
        if raw_level == cur:
            st.update(pending=None, count=0)
            return cur
        if st["pending"] == raw_level:
            st["count"] += 1
        else:
            st.update(pending=raw_level, count=1)
        if st["count"] >= self.periods:
            st.update(level=raw_level, pending=None, count=0)
            return raw_level
        return cur


def grade(rec: dict, th: dict, debouncer: Debouncer | None = None) -> dict:
    """对一个路段快照跑完五步，返回判级结果（字段对齐 segments.json 契约）。"""
    grading = _grading(th)
    rec = dict(rec)
    # x 可由 q/c 推出（契约口径 x = q_vph / c_vph）；两条链路都不要求上游重复填 x
    if not isinstance(rec.get("x"), (int, float)):
        q, c = rec.get("q_vph"), rec.get("c_vph")
        if isinstance(q, (int, float)) and isinstance(c, (int, float)) and c > 0:
            rec["x"] = round(float(q) / float(c), 3)
    seg = rec.get("segment_id", "?")
    out: dict = {"segment_id": seg}
    ok, why = availability_gate(rec, grading)
    if not ok:
        out.update(available=False, level=0, level_name="数据不可用", gate_reason=why, triggered_by=[])
        return out

    # ①' 指标缺失门：**缺指标不能判成"畅通"**（TC-11 同口径；孪生/视频共用时防止静默漏判）
    required = [it.get("indicator") for it in grading.get("level_bounds", [])]
    missing = [ind for ind in required if not isinstance(rec.get(INDICATOR_FIELDS.get(ind, "")), (int, float))]
    if missing:
        out.update(available=False, level=0, level_name="数据不可用",
                   gate_reason=f"指标缺失：{','.join(missing)}", triggered_by=[])
        return out

    hard = hard_trigger(rec, grading)
    if hard is not None:
        final = debouncer.apply(seg, hard) if debouncer else hard
        out.update(available=True, level=final, level_name=LEVEL_NAME[final],
                   triggered_by=["hard_factor"], hard_trigger=True)
        return out

    fixed, coeff = factor_correction(rec, grading)
    raw_level, per = four_metrics_level(fixed, grading)
    final = debouncer.apply(seg, raw_level) if debouncer else raw_level
    focused = [k for k, v in per.items() if v == raw_level]
    out.update(
        available=True,
        level=final,
        level_name=LEVEL_NAME[final],
        raw_level=raw_level,
        per_metric=per,
        triggered_by=focused,
        factor_coefficient=round(coeff, 3),
        x_corrected=fixed.get("x", rec.get("x")),
        c_corrected=fixed.get("c_vph", rec.get("c_vph")),
        ci=congestion_index(fixed, grading),
    )
    return out


def self_test() -> int:
    """自检：同一输入连跑 3 次一致（M1-3）+ 覆盖 ≥2 档 + 降档防抖。"""
    th = load_thresholds()
    grading = _grading(th)
    cases = [
        {"segment_id": "T-畅通", "source": "video", "q_vph": 500, "v_kmh": 38, "v_f_kmh": 40,
         "k_vpk": 8, "L_q_m": 0, "T_d_min": 0.0, "c_base_vph": 1600, "c_vph": 1600,
         "confidence": 0.9, "data_age_s": 5, "factors_applied": []},
        {"segment_id": "T-拥堵", "source": "video", "q_vph": 1500, "v_kmh": 12, "v_f_kmh": 40,
         "k_vpk": 60, "L_q_m": 260, "T_d_min": 9.0, "c_base_vph": 1600, "c_vph": 1600,
         "confidence": 0.9, "data_age_s": 5, "factors_applied": []},
        {"segment_id": "T-不可用", "source": "twin", "q_vph": 800, "v_kmh": 20, "v_f_kmh": 40,
         "k_vpk": 30, "L_q_m": 40, "T_d_min": 1.0, "c_base_vph": 1600, "c_vph": 1600,
         "confidence": 0.3, "data_age_s": 200, "factors_applied": []},
        {"segment_id": "T-硬触发", "source": "twin", "q_vph": 300, "v_kmh": 35, "v_f_kmh": 40,
         "k_vpk": 10, "L_q_m": 0, "T_d_min": 0.0, "c_base_vph": 1600, "c_vph": 1600,
         "confidence": 0.9, "data_age_s": 5,
         "factors_applied": [{"factor_id": "F07", "target": "c", "multiplier": 0.4}]},
    ]
    runs = []
    for _ in range(3):
        d = Debouncer(int(grading["hysteresis_periods"]))
        runs.append([grade(c, th, d) for c in cases])
    ok = True
    for i, case in enumerate(cases):
        levels = [r[i]["level"] for r in runs]
        same = len(set(levels)) == 1
        print(f"  {case['segment_id']:<8} 3 次判级 = {levels} {runs[0][i]['level_name']} "
              f"{'一致' if same else '**不一致**'}")
        ok = ok and same
    covered = {r["level"] for r in runs[0] if r["level"] > 0}
    print(f"  覆盖档数 = {len(covered)}（{sorted(covered)}）{'≥2 档 OK' if len(covered) >= 2 else '**不足 2 档**'}")
    ok = ok and len(covered) >= 2
    # 降档防抖（同一 segment_id 连续周期）
    d = Debouncer(2)
    hi = {**cases[1], "segment_id": "T-防抖"}
    lo = {**cases[0], "segment_id": "T-防抖"}
    l1, l2, l3 = grade(hi, th, d)["level"], grade(lo, th, d)["level"], grade(lo, th, d)["level"]
    deb_ok = l2 == l1 and l3 < l1
    print(f"  防抖：拥堵 {l1} → 首次降档仍 {l2} → 第 2 周期 {l3} "
          f"{'OK（升档立即、降档需 2 周期）' if deb_ok else '**未生效**'}")
    ok = ok and deb_ok
    print("自检" + ("通过。" if ok else "**未通过**。"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    raise SystemExit("要 --self-test（判级本体由 run_chain.py 调用）")


if __name__ == "__main__":
    raise SystemExit(main())
