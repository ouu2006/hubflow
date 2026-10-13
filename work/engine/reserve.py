"""时段容量预约 + 不伤害前车约束 + 租约(手册 7.6 伪代码;分工表 §8.2 的 **W3**)。

输入:segments 现状 + decision 组参数(x_safe / eps_harm_s / lease_expire_s / slot_minutes)
输出:预约表 + 租约(内存);挂到 routes.json 的 `reservation` / `quota` 字段
口径(契约第二节):
  - 每条路段按 **1 分钟**切时段;推荐一辆车时在它将经过的**每段路 × 每个时段**登记一个占用;
  - **约束①**:任一格子的饱和度 `(背景 + 已预约 + 本车) / 通行能力` 不得超 `x_safe`;
  - **约束②**:加入本车后,已登记前车 ETA 的最大增加量不得超 `eps_harm_s`;
  - **两条约束都通过才允许推荐**(`harm_check.passed == true`);
  - 租约 `lease_expire_s` 秒未确认采纳即释放。

⚠️ **本文件是 W0 骨架,函数边界先定、实现待 W3**。所有实现体抛 NotImplementedError,
   不返回编造的预约结果 —— 编一个 `passed: true` 出来正是 issue 点名的"静默假通过"。

用法:由 run.py 调用;`--sample` 路径下只会拿到 NotImplementedError(见 run.py 的说明)。
"""

from __future__ import annotations

from typing import Any

#: 没通过约束时的固定原因码(契约第二节)
REASON_NO_CAPACITY = "capacity_shortage"
REASON_HARM_EXCEEDED = "harm_exceeded"


class SlotTable:
    """时段预约表:`(segment_id, slot_index) -> 已预约车辆数`。"""

    def __init__(self, slot_minutes: int = 1) -> None:
        self.slot_minutes = int(slot_minutes)
        self._cells: dict[tuple[str, int], int] = {}

    def reserved(self, segment_id: str, slot_index: int) -> int:
        """某个格子上已预约的车辆数。"""
        return self._cells.get((segment_id, slot_index), 0)

    def occupied_cells(self) -> int:
        """已被占用的格子总数。"""
        return len(self._cells)


def walk_slots(
    segments: list[str],
    start_ts: str,
    params: dict[str, Any],
) -> list[tuple[str, int]]:
    """沿路径按时段推进,算出它经过的 `(segment_id, 时段序号)` 格子与 ETA。

    骨架,TODO(W3):行程时间要用 network.path_travel_time_s 逐段累加。
    """
    raise NotImplementedError("时段推进待 W3 实现:沿路径按 1 分钟粒度推进(手册 7.6 的 walk())")


def harm_check(
    table: SlotTable,
    slots: list[tuple[str, int]],
    leases: dict[str, dict[str, Any]],
    params: dict[str, Any],
) -> dict[str, Any]:
    """约束②:算加入本车后已登记前车 ETA 的最大增加量。

    返回 `{"max_eta_increase_s": float, "max_slot_x": float, "passed": bool}`(契约第二节)。
    骨架,TODO(W3)。
    """
    raise NotImplementedError("不伤害前车约束待 W3 实现:max_eta_increase(leases, slots)(手册 7.6)")


def recommend(
    graph: Any,
    od: dict[str, Any],
    candidate_paths: list[list[str]],
    segments: dict[str, dict[str, Any]],
    params: dict[str, Any],
    table: SlotTable,
    leases: dict[str, dict[str, Any]],
    now_ts: str,
) -> dict[str, Any]:
    """在通过两个约束的候选里选"对本车最快"的那条,并登记预约。

    骨架,TODO(W3):全候选被丢弃时返回 `capacity_shortage` + 建议,**不硬塞**(契约第二节)。
    """
    raise NotImplementedError("时段容量预约 + 不伤害约束待 W3 实现(手册 7.6 的 recommend())")


def release_expired(leases: dict[str, dict[str, Any]], now_ts: str) -> list[str]:
    """释放 `lease_expire_s` 秒内未确认采纳的租约,返回被释放的 session_id 列表。

    骨架,TODO(W3)。
    """
    raise NotImplementedError("租约释放待 W3 实现:90 s 未确认采纳即释放(契约第二节)")
