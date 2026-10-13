"""三类司机行为体:跟驰交给 SUMO,决策(是否采纳推荐)走 TraCI。

输入:vehicles 样例(--no-sumo);SUMO 里每辆车的当前状态(真孪生)
输出:车辆清单快照(vehicles.json,契约第四节)+ 逐车决策
口径:D1 送客 / D2 接客 / D3 往返,取值**封闭**(契约第四节,新增要改契约);
     is_demo_bound 同一时刻**最多一辆为 true**(一期 App 只绑一辆演示车)。

用法:由 loop.py 调用,不单独执行。
"""

from __future__ import annotations

from typing import Any

#: 三类虚拟司机行为体(契约第四节,取值封闭)
DRIVER_TYPES = ("D1", "D2", "D3")
DRIVER_NAMES_ZH = {"D1": "送客", "D2": "接客", "D3": "往返"}

#: 车辆状态取值集合(契约第四节,取值封闭)
VEHICLE_STATES = ("行驶", "排队", "落客服务", "候客", "违停", "已离开")


def load_drivers(vehicles_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """从车辆清单里取出车辆,并校验 driver_type / state 是否在封闭取值内。

    --no-sumo 时这就是样例里的那几条;真孪生时来自 SUMO 车辆状态。
    """
    vehicles = vehicles_payload.get("vehicles", [])
    if not isinstance(vehicles, list):
        raise ValueError("vehicles 应为数组(契约第四节:顶层信封 + vehicles 数组)")
    demo_bound = 0
    for vehicle in vehicles:
        driver_type = vehicle.get("driver_type")
        if driver_type not in DRIVER_TYPES:
            raise ValueError(f"未知司机类型:{driver_type!r}(仅 {DRIVER_TYPES})")
        state = vehicle.get("state")
        if state not in VEHICLE_STATES:
            raise ValueError(f"未知车辆状态:{state!r}(仅 {VEHICLE_STATES})")
        if vehicle.get("is_demo_bound"):
            demo_bound += 1
    if demo_bound > 1:
        raise ValueError(f"is_demo_bound 至多一辆为 true,实际 {demo_bound} 辆")
    return list(vehicles)


def snapshot_fleet(vehicles_payload: dict[str, Any], ts: str) -> dict[str, Any]:
    """产出 vehicles.json:带 ts 与 is_simulated 的信封,车辆放 vehicles 数组。"""
    fleet = load_drivers(vehicles_payload)
    return {"ts": ts, "is_simulated": True, "vehicles": fleet}


def decide(vehicle: dict[str, Any], recommendation: dict[str, Any] | None, seed: int) -> dict[str, Any]:
    """决定这辆车采不采纳推荐(骨架,TODO)。

    返回 {"vehicle_id": ..., "accepted": bool, "reason": str};
    真孪生:按司机类型的采纳倾向 + 固定种子决定,种子固定才能复现(M1-1)。
    """
    raise NotImplementedError("司机决策待 W1 实现:采纳倾向 + 固定种子,保证可复现")
