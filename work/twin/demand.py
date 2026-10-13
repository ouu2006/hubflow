"""需求生成:读站点包的列车时刻表与需求比例,产出按时段的到达流率。

输入:stations/demand.json(T3 列车时刻表 + T4 需求比例)
输出:按时段的到达流率曲线(list,内存对象,不落盘)
口径:列车到达 → 放量;数值是**演示假设值**,不是实测值,对外标"演示数据(模拟)"。

用法:由 loop.py 调用,不单独执行。
"""

from __future__ import annotations

from typing import Any

#: 三类司机对应的需求(与 driver.DRIVER_TYPES 对齐)
DEMAND_CLASSES = ("D1", "D2", "D3")


def load_demand(cfg: Any, scene: Any) -> list[dict[str, Any]]:
    """装载需求曲线。

    --no-sumo:站点包未到位,返回空曲线(不是编造一条假的)。
    真孪生:读 stations/demand.json,把列车到发折成逐时段的到达流率。
    """
    if cfg.no_sumo:
        return []
    raise NotImplementedError("需求装载待 W1 实现:读 stations/demand.json(T3 / T4)")


def flow_at(curve: list[dict[str, Any]], now_ts: str) -> dict[str, float]:
    """取 now_ts 所在时段的到达流率(辆/小时,按三类司机分列)。"""
    if not curve:
        return dict.fromkeys(DEMAND_CLASSES, 0.0)
    # 曲线按 time 升序;取最后一个不晚于 now_ts 的时段。
    # 早于首时段时还没有任何需求生效,必须给 0——回落到 curve[0] 会把未来时段的
    # 流率提前套到仿真一开始(Sourcery #79 待办②)。
    candidates = [row for row in curve if str(row.get("time", "")) <= str(now_ts)]
    if not candidates:
        return dict.fromkeys(DEMAND_CLASSES, 0.0)
    row = candidates[-1]
    return {key: float(row.get(key, 0.0)) for key in DEMAND_CLASSES}
