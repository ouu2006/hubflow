"""因素注入:按站点包的因素表与场景注入事件,给出"这一刻实际生效"的因素清单。

输入:stations/factors.json(T5)+ 场景注入事件
输出:生效因素列表(最终写进 segments 的 factors_applied,契约 1.1)
口径:未生效的因素**不写进数组**(不写 multiplier=1.0 占位);
     各因素对 c / v_f 分别相乘,合成后不低于原值的 40%【待标定】。

用法:由 loop.py 调用,不单独执行。
"""

from __future__ import annotations

from typing import Any

#: 因素能作用的量(契约 1.1:取值封闭,新增要改契约)
FACTOR_TARGETS = ("c", "v_f", "demand", "lanes", "confidence")

#: 合成下限:各因素连乘后不低于原值的这个比例(契约 1.1 / 手册,【待标定】)
FLOOR_RATIO = 0.4  # 【待标定】


def load_station_factors(cfg: Any, scene: Any) -> list[dict[str, Any]]:
    """装载站点包的因素表并解析出注入事件。

    --no-sumo:站点包未到位,返回空清单(样例的 factors_applied 已烘在样例里)。
    真孪生:读 stations/factors.json(T5),合并 scenario 的注入事件。
    """
    if cfg.no_sumo:
        return []
    raise NotImplementedError("因素表装载待 W1 实现:读 stations/factors.json(T5)")


def compose(base_c: float, base_v_f: float, applied: list[dict[str, Any]]) -> dict[str, float]:
    """把生效因素合成到通行能力与畅通速度上。

    返回 {"c": ..., "v_f": ...};合成结果按 FLOOR_RATIO 保底,不允许打到 0 以下。
    """
    c, v_f = base_c, base_v_f
    for factor in applied:
        target = factor.get("target")
        if target not in FACTOR_TARGETS:
            raise ValueError(f"未知因素作用量 target={target!r}")
        multiplier = float(factor.get("multiplier", 1.0))
        if target in ("c", "lanes"):
            c *= multiplier
        elif target == "v_f":
            v_f *= multiplier
    return {
        "c": max(c, base_c * FLOOR_RATIO),
        "v_f": max(v_f, base_v_f * FLOOR_RATIO),
    }


def factor_is_active(factor: dict[str, Any], now_ts: str) -> bool:
    """该因素在 now_ts 是否还在生效(按 until 判定)。

    口径:until 到了就自动失效(手册);长期因素给远期时间,不留空。
    """
    until = factor.get("until")
    if not until:
        return True
    return str(now_ts) <= str(until)
