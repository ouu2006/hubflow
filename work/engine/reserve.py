"""时段容量预约 + 不伤害前车约束 + 租约(work/engine/README.md 2.2 的①与②;手册 §7.6 伪代码)。

输入:`network.Graph` + `segments` 现状(按 `segment_id` 取 `q_vph` / `c_vph`)+
      `stations/thresholds.json` 的 `decision` 组参数
      (`slot_minutes` / `alpha` / `beta` / `x_safe` / `eps_harm_s` / `lease_expire_s`)
输出:预约表 `SlotTable` + 租约 `leases`(内存,不单独落盘);由 run.py 折进
      `routes.json` 的 `reservation` / `quota` 字段
口径(契约第二节):
  - 每条路段按 `slot_minutes` 切时段;推荐一辆车时,在它将经过的
    **每段路 × 每个时段**上各登记一个占用;
  - **约束①**:任一格子的饱和度 `(背景 + 已预约 + 本车) / 通行能力` 不得超 `x_safe`;
  - **约束②**:加入本车后,已登记前车 ETA 的最大增加量不得超 `eps_harm_s`;
  - 两条约束都通过的候选里选**对本车最快**的;全候选被丢弃 → `capacity_shortage`
    + 需求侧建议,**不硬塞**;
  - 租约 `lease_expire_s` 秒未确认采纳即释放。
量纲(手册 §7.6 硬约束):格子按 **辆/分钟** 计;**`x` 本身即无量纲饱和度,
  惩罚项不得再除以 c** —— 所以 `tt()` 统一走 `network.travel_time_s`(全仓唯一 BPR 实现),
  只把"辆/分钟"换算成"辆/小时"喂它的 `extra_vph`,不再复制一份 BPR 公式。

参数一律从 `params`(站点包 decision 组)取,本文件**不写死任何判据数值**。
用法:由 run.py 调用,不单独执行。
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, tzinfo
from typing import Any

import network

#: 没通过约束时的固定原因码(契约第二节;两个名字照抄,不许改名)
REASON_NO_CAPACITY = "capacity_shortage"
REASON_HARM_EXCEEDED = "harm_exceeded"

#: 全部候选都放不下时给需求侧的建议(手册 §7.6(7):外围等待 / 延后 N 分钟 / 换停车场)
CAPACITY_SHORTAGE_SUGGESTIONS = ("外围等待", "延后出发", "换停车场")

#: 单位换算常数(不是判据数值):辆/小时 ↔ 辆/分钟
SECONDS_PER_MINUTE = 60.0
SECONDS_PER_HOUR = 3600.0


def iso_to_epoch_s(ts: str) -> float:
    """ISO-8601 时间戳(带时区)→ epoch 秒。

    **不读系统时钟**:输入是什么时刻就返回什么时刻,同一输入连跑结果一致(确定性硬约束)。
    不带时区的时间戳直接报错 —— 否则 `.timestamp()` 会跟随本机时区,换机器结果就变。
    """
    parsed = datetime.fromisoformat(ts)
    if parsed.tzinfo is None:
        raise ValueError(f"时间戳必须带时区(开发规范第 2 节:ISO-8601 带时区),实为 {ts!r}")
    return parsed.timestamp()


def tzinfo_of(ts: str) -> tzinfo:
    """取一个 ISO-8601 时间戳自带的时区,供"以它为起点生成的车流时刻"格式化用。"""
    parsed = datetime.fromisoformat(ts)
    if parsed.tzinfo is None:
        raise ValueError(f"时间戳必须带时区(开发规范第 2 节:ISO-8601 带时区),实为 {ts!r}")
    return parsed.tzinfo


def epoch_s_to_iso(epoch_s: float, tz: tzinfo) -> str:
    """epoch 秒 → 带时区的 ISO-8601。"""
    return datetime.fromtimestamp(float(epoch_s), tz).isoformat()


def offset_iso(ts: str, seconds: float) -> str:
    """把一个 ISO-8601 时间戳往后推 `seconds` 秒,保持同一时区。"""
    return datetime.fromisoformat(ts) + timedelta(seconds=float(seconds))


def slot_index_of(epoch_s: float, slot_minutes: int) -> int:
    """时刻 → 时段序号(向下取整的绝对分钟格;负数时刻也按 floor 处理)。"""
    width_s = float(slot_minutes) * SECONDS_PER_MINUTE
    if width_s <= 0.0:
        raise ValueError("slot_minutes 必须为正(站点包 decision 组)")
    return int(math.floor(float(epoch_s) / width_s))


class SlotTable:
    """时段预约表:`(segment_id, slot_index) -> 已预约车辆数`。

    同时缓存每段的 `t0`(经 `network.free_flow_time_s`)与"每时段"的背景流 / 通行能力,
    这样 `tt()` 只做一次除法 + 一次 BPR 调用,不会在热路径里反复查图。
    """

    def __init__(
        self,
        graph: network.Graph,
        segments_state: dict[str, dict[str, Any]],
        params: dict[str, Any],
    ) -> None:
        self.graph = graph
        self.segments_state = segments_state
        self.params = params
        self.slot_minutes = int(params["slot_minutes"])
        self._slots_per_hour = SECONDS_PER_HOUR / (float(self.slot_minutes) * SECONDS_PER_MINUTE)
        self._cells: dict[tuple[str, int], int] = {}
        self._edge_segment: dict[str, str] = {}
        self._cap_per_slot: dict[str, float] = {}
        self._background_per_slot: dict[str, float] = {}
        #: '突发'演示用:被临时封闭的路段(tt 返回 +inf,车不会选进候选)
        self._closed_segments: set[str] = set()

        for edge_id in graph._edges:  # noqa: SLF001 —— 只遍历拓扑,与 run.py 的写法一致
            edge = graph.edge(edge_id)
            segment_id = str(edge.get("section") or "")
            if not segment_id:
                # 无 section 的边不参与时段预约(样例路网全部有 section;真网由 map_ingest 保证)
                continue
            self._edge_segment[edge_id] = segment_id
            if segment_id in self._cap_per_slot:
                continue
            segment = segments_state.get(segment_id)
            #: 通行能力取 segments 的 c_vph(因素修正后);缺则退回边的 capacity_vph(契约第一节)
            capacity_vph = float(
                (segment or {}).get("c_vph") or edge["capacity_vph"]
            )
            flow_vph = float((segment or {}).get("q_vph", 0.0))
            cap_per_slot = capacity_vph / self._slots_per_hour
            self._cap_per_slot[segment_id] = cap_per_slot
            self._background_per_slot[segment_id] = flow_vph / self._slots_per_hour

    # ---------------------------------------------------------------- 查询

    def edge_segment(self, edge_id: str) -> str:
        """边 id → segment_id(边没有 section 时返回空串)。"""
        return self._edge_segment.get(str(edge_id), "")

    def capacity_per_slot(self, segment_id: str) -> float:
        """该路段每个时段的通行能力(辆/时段);≤0 表示封闭。"""
        return self._cap_per_slot.get(str(segment_id), 0.0)

    def background_per_slot(self, segment_id: str) -> float:
        """该路段每个时段的背景车流(辆/时段)。"""
        return self._background_per_slot.get(str(segment_id), 0.0)

    def reserved(self, segment_id: str, slot_index: int) -> int:
        """某个格子上已预约的车辆数。"""
        return self._cells.get((str(segment_id), int(slot_index)), 0)

    def occupied_cells(self) -> int:
        """已被占用的格子总数(只数非空格子)。"""
        return len(self._cells)

    def is_closed(self, segment_id: str) -> bool:
        """该路段是否被"突发"演示临时封闭。"""
        return str(segment_id) in self._closed_segments

    def close_segment(self, segment_id: str) -> None:
        """把路段标记为封闭(`tt` 返回 +inf)。**只给"突发再疏导"演示用,不影响常规推荐**。"""
        self._closed_segments.add(str(segment_id))

    # ---------------------------------------------------------------- 行程时间

    def tt(self, edge_id: str, slot_index: int, extra: float = 0.0) -> float:
        """路段在该时段的服务时间(秒):`t = t0·(1 + α·x^β)`。

        - `x = (背景 + 已预约 + extra) / 该时段通行能力`,三者都是"辆/时段";
        - BPR 本身复用 `network.travel_time_s`(全仓唯一实现),只把格子里的车数
          换算成 `extra_vph` 喂进去 —— 同一份公式,不复制、不写死 α/β;
        - 路段被临时封闭 → `+inf`(选路时该边不可用)。
        """
        segment_id = self.edge_segment(edge_id)
        edge = self.graph.edge(edge_id)
        if self.is_closed(segment_id):
            return math.inf
        capacity = self.capacity_per_slot(segment_id)
        if capacity <= 0.0:
            return math.inf
        reserved = self.reserved(segment_id, slot_index)
        extra_vph = (float(reserved) + float(extra)) * self._slots_per_hour
        segment = self.segments_state.get(segment_id)
        return network.travel_time_s(edge, segment, self.params, extra_vph=extra_vph)

    def saturation(self, segment_id: str, slot_index: int, extra: float = 0.0) -> float:
        """某个格子的饱和度 `(背景 + 已预约 + extra) / 通行能力`(+inf 表示封闭)。"""
        capacity = self.capacity_per_slot(segment_id)
        if capacity <= 0.0:
            return math.inf
        flow = self.background_per_slot(segment_id) + float(
            self.reserved(segment_id, slot_index)
        ) + float(extra)
        return flow / capacity

    def segment_max_saturation(self, segment_id: str) -> float:
        """某路段在**已预约时段**上的最大饱和度(没被预约的时段按背景算)。"""
        peak = self.saturation(segment_id, -1)  # 空槽位:只有背景流
        for (cell_segment, slot), _count in self._cells.items():
            if cell_segment != str(segment_id):
                continue
            value = self.saturation(segment_id, slot)
            if value > peak:
                peak = value
        return peak

    def network_total_time_s(self, start_epoch_s: float, end_epoch_s: float) -> float:
        """全网总行程时间(辆·秒):Σ 每段每时段 `(背景 + 已预约) × 该时段服务时间`。

        - **把背景车流也算进去**:普通导航把路段压过安全线时,被拖慢的不只是被引导车辆,
          这正是 TC-17"全网总行程时间"要度量的系统代价(背景车流 = 没装 App 的车);
        - 一个格子里的车辆数就是该时段通过该路段的车数(辆/时段),乘以该时段服务时间即
          该时段全车流的总行程时间;评估窗口内的所有时段都算。
        """
        start_slot = slot_index_of(start_epoch_s, self.slot_minutes)
        end_slot = slot_index_of(end_epoch_s, self.slot_minutes)
        first_edge: dict[str, str] = {}
        for edge_id in sorted(self._edge_segment):
            first_edge.setdefault(self._edge_segment[edge_id], edge_id)
        total = 0.0
        for slot_index in range(start_slot, end_slot):
            for segment_id in sorted(first_edge):
                flow = self.background_per_slot(segment_id) + float(
                    self.reserved(segment_id, slot_index)
                )
                if flow <= 0.0:
                    continue
                total += flow * self.tt(first_edge[segment_id], slot_index, extra=0.0)
        return total

    # ---------------------------------------------------------------- 登记 / 释放

    def reserve(self, cells: list[tuple[str, int]]) -> None:
        """把一辆车的占用登记进表格(每格 +1)。"""
        for segment_id, slot_index in cells:
            key = (str(segment_id), int(slot_index))
            self._cells[key] = self._cells.get(key, 0) + 1

    def release(self, cells: list[tuple[str, int]]) -> None:
        """把一辆车的占用从表格里撤掉(每格 -1;减到 0 的格子删除)。"""
        for segment_id, slot_index in cells:
            key = (str(segment_id), int(slot_index))
            count = self._cells.get(key, 0)
            if count <= 1:
                self._cells.pop(key, None)
            else:
                self._cells[key] = count - 1


def _max_slot_x(table: SlotTable, cells: list[tuple[str, int]]) -> float:
    """路径上所有时段格子的最大饱和度(含本车 `extra=1`;没有格子时为 0)。"""
    return max_slot_x(table, cells, extra=1.0)


def max_slot_x(
    table: SlotTable,
    cells: list[tuple[str, int]],
    extra: float = 1.0,
) -> float:
    """公开的"路径最大时段饱和度"口径:再疏导复核约束①时复用,与 `harm_check` 同一算式。"""
    peak = 0.0
    for segment_id, slot_index in cells:
        value = table.saturation(segment_id, slot_index, extra=float(extra))
        if value > peak:
            peak = value
    return peak


def walk_slots_detail(
    table: SlotTable,
    path: list[str],
    start_epoch_s: float,
    extra: float = 1.0,
) -> tuple[list[tuple[str, int]], float, list[float]]:
    """`walk_slots()` 的详细版:额外返回**逐边**服务时间(秒)。

    逐边时间供再疏导使用:判断"这辆车现在还要多久"时,必须拿**同一辆车、同一位置、
    同一套规划**下的剩余 ETA 做同类比较 —— 不能拿"从当前时刻算的剩余 ETA"去减
    "登记时整条路径的 ETA",那样在途车会永远差出已走过的那一段(见 DESIGN.md「审查整改」)。
    """
    cells: list[tuple[str, int]] = []
    edge_times: list[float] = []
    start_epoch_s = float(start_epoch_s)
    elapsed_s = 0.0
    for edge_id in path:
        segment_id = table.edge_segment(edge_id)
        slot_index = slot_index_of(start_epoch_s + elapsed_s, table.slot_minutes)
        cells.append((segment_id, slot_index))
        segment_time = table.tt(edge_id, slot_index, extra)
        edge_times.append(segment_time)
        elapsed_s += segment_time
    #: ETA 用"从 0 累加"的小数算,不拿 epoch 大数累加(否则浮点精度会丢到 1e-7 秒量级)
    return cells, elapsed_s, edge_times


def walk_slots(
    table: SlotTable,
    path: list[str],
    start_epoch_s: float,
    extra: float = 1.0,
) -> tuple[list[tuple[str, int]], float]:
    """沿路径按时段推进,返回经过的 `(segment_id, 时段序号)` 格子与 ETA(秒)。

    对应手册 §7.6 的 `walk(path, t_start, extra)`:
      - 每段先用**当前时刻**定位时段 → 记一个占用格 → 再累加该时段的服务时间;
      - `extra=1` 表示"把这辆新车自己算进去"(试算用);已登记前车复算时传 `extra=0`,
        因为前车自己的占用已经在 `reserved` 里了。
    """
    cells, eta_s, _edge_times = walk_slots_detail(table, path, start_epoch_s, extra)
    return cells, eta_s


def harm_check(
    table: SlotTable,
    slots: list[tuple[str, int]],
    leases: dict[str, dict[str, Any]],
    params: dict[str, Any],
) -> dict[str, Any]:
    """约束②:算加入本车后,已登记前车 ETA 的最大增加量(契约第二节的 `harm_check`)。

    - **约束①** 也在同一次试算里判:`max_slot_x` = 本车路径所有时段的最大饱和度(含本车);
    - 做法:先把本车占用**临时**登记进表,再对"与本车时段格子有重叠"的每条租约,
      用同一张表重算它的 ETA(前车自身占用已在表里,故 `extra=0`),取最大增量;
      最后把临时登记撤掉 —— 本函数**无副作用**(除短暂的表状态)。
    - 返回**只有契约规定的三个子字段**:`max_eta_increase_s` / `max_slot_x` / `passed`。

    空路径(没有格子)视为通过:没有占用就伤不到任何前车、也不制造饱和度。
    """
    x_safe = float(params["x_safe"])
    eps_harm_s = float(params["eps_harm_s"])

    max_slot_x = _max_slot_x(table, slots)

    max_eta_increase_s = 0.0
    cell_set = set(slots)
    overlapping: list[dict[str, Any]] = []
    for session_id in sorted(leases):
        lease = leases[session_id]
        if cell_set.isdisjoint(lease["cells"]):
            continue
        overlapping.append(lease)

    if overlapping:
        table.reserve(list(slots))
        try:
            for lease in overlapping:
                _cells, eta_after = walk_slots(
                    table, lease["path"], lease["start_epoch_s"], extra=0.0
                )
                increase = eta_after - float(lease["eta_s"])
                if increase > max_eta_increase_s:
                    max_eta_increase_s = increase
        finally:
            table.release(list(slots))

    passed = bool(max_eta_increase_s <= eps_harm_s and max_slot_x <= x_safe)
    return {
        "max_eta_increase_s": round(max_eta_increase_s, 2),
        "max_slot_x": round(max_slot_x, 4),
        "passed": passed,
    }


def remaining_quota(
    table: SlotTable,
    path: list[str],
    start_epoch_s: float,
    params: dict[str, Any],
) -> int:
    """一条路径的"剩余可预约量"(契约第二节 `quota` 的新口径)。

    对路径经过的每个格子算"再塞几辆还能保持饱和度 ≤ `x_safe`",取**最紧的那一格**;
    负值截到 0(已经超了就是 0 辆)。这里只做整数估算,不登记任何占用。
    """
    x_safe = float(params["x_safe"])
    cells, _eta = walk_slots(table, path, start_epoch_s, extra=0.0)
    quota = None
    for segment_id, slot_index in cells:
        capacity = table.capacity_per_slot(segment_id)
        if capacity <= 0.0:
            return 0
        headroom = x_safe * capacity - table.background_per_slot(segment_id) - float(
            table.reserved(segment_id, slot_index)
        )
        count = int(math.floor(headroom))
        if count < 0:
            count = 0
        if quota is None or count < quota:
            quota = count
    return int(quota or 0)


def recommend(
    graph: network.Graph,
    od: dict[str, Any],
    candidate_paths: list[list[str]],
    segments: dict[str, dict[str, Any]],
    params: dict[str, Any],
    table: SlotTable,
    leases: dict[str, dict[str, Any]],
    now_ts: str,
) -> dict[str, Any]:
    """在通过两个约束的候选里选"对本车最快"的那条,并登记预约 + 租约。

    对应手册 §7.6 的 `recommend(req)`;返回的是**决策结果**(不是契约响应体,
    契约字段由 run.py 按 `docs/数据契约.md` 第二节拼装):

    ```
    {
      "status": "ok" | "capacity_shortage",
      "path": 边 id 序列, "cells": [(segment_id, slot), …] 或 [[seg, slot], …],
      "eta_s": 预计行程时间(秒), "harm_check": {max_eta_increase_s, max_slot_x, passed},
      "candidates": [{path, eta_s, harm_check, rejected_reason}, …],
      "quota": [每条候选的剩余可预约量, 与 candidate_paths 同序],
      "suggest": [需求侧建议…](仅 capacity_shortage 时非空),
      "lease": 已登记的租约(仅 ok 时),
    }
    ```

    全部候选被两条约束丢弃 → `status = capacity_shortage`,**不返回任何路线**。

    登记出的租约额外带 `edge_times_s`(逐边服务时间)与 `feasible_candidates`
    (只含**通过两条约束**的候选路径):reroute.py 用前者做"这辆车现在还要多久"的同类口径基线,
    用后者保证再疏导不会落回登记时已被拒的路线。
    """
    start_epoch_s = iso_to_epoch_s(now_ts)
    session_id = str(od.get("session_id") or od.get("od_id") or "S-unknown")
    x_safe = float(params["x_safe"])

    candidates: list[dict[str, Any]] = []
    #: (eta, 路径元组, 路径, 格子, harm_check, 逐边服务时间)
    ok_candidates: list[
        tuple[float, tuple[str, ...], list[str], list[tuple[str, int]], dict[str, Any], list[float]]
    ] = []
    rejected: list[dict[str, Any]] = []

    for path in candidate_paths:
        edge_path = list(path)
        cells, eta_s, edge_times = walk_slots_detail(
            table, edge_path, start_epoch_s, extra=1.0
        )
        harm = harm_check(table, cells, leases, params)
        reason = None
        if not harm["passed"]:
            # 哪一个约束没过:先用**未取整**的饱和度判约束①,再看前车伤害(约束②)
            reason = (
                REASON_NO_CAPACITY
                if _max_slot_x(table, cells) > x_safe
                else REASON_HARM_EXCEEDED
            )
            rejected.append({"path": edge_path, "reason": reason, "harm_check": harm})
        else:
            ok_candidates.append((eta_s, tuple(edge_path), edge_path, cells, harm, edge_times))
        candidates.append(
            {
                "path": edge_path,
                "eta_s": eta_s,
                "harm_check": harm,
                "rejected_reason": reason,
            }
        )

    quota = [remaining_quota(table, list(path), start_epoch_s, params) for path in candidate_paths]

    if not ok_candidates:
        return {
            "status": REASON_NO_CAPACITY,
            "session_id": session_id,
            "path": None,
            "cells": [],
            "eta_s": None,
            "harm_check": None,
            "candidates": candidates,
            "rejected": rejected,
            "quota": quota,
            "suggest": list(CAPACITY_SHORTAGE_SUGGESTIONS),
            "lease": None,
        }

    eta_s, _key, edge_path, cells, harm, edge_times = min(
        ok_candidates, key=lambda item: (round(item[0], 6), item[1])
    )
    table.reserve(cells)
    lease: dict[str, Any] = {
        "session_id": session_id,
        "od_id": str(od.get("od_id") or ""),
        "path": list(edge_path),
        "cells": cells,
        #: 逐边服务时间:再疏导判断"这辆车现在还要多久"时用同类口径做基线(见 reroute.py)
        "edge_times_s": list(edge_times),
        "eta_s": float(eta_s),
        "start_epoch_s": start_epoch_s,
        "expire_at_epoch_s": start_epoch_s + float(params["lease_expire_s"]),
        "confirmed": False,
        "reroute_count": 0,
        #: 只有**通过两条约束**的候选才进这里 —— 再疏导不能落到登记时已被拒的路线
        "feasible_candidates": [list(item[2]) for item in ok_candidates],
    }
    leases[session_id] = lease

    return {
        "status": "ok",
        "session_id": session_id,
        "path": list(edge_path),
        "cells": cells,
        "eta_s": float(eta_s),
        "harm_check": harm,
        "candidates": candidates,
        "rejected": rejected,
        "quota": quota,
        "suggest": [],
        "lease": lease,
    }


def release_expired(
    table: SlotTable,
    leases: dict[str, dict[str, Any]],
    now_ts: str,
) -> list[str]:
    """释放 `lease_expire_s` 秒内**未确认采纳**的租约,返回被释放的 session_id 列表。

    对应手册 §7.6 的 `release(expired_unconfirmed_leases)`:
      - 只有 `confirmed = False` 的租约会被释放(确认采纳的车视为真的上路了,占用保留);
      - 释放时把该租约登记的格子从预约表里撤掉,避免"发了没人走"虚占容量;
      - 按 session_id 排序处理,返回顺序确定(确定性硬约束)。
    """
    now_epoch_s = iso_to_epoch_s(now_ts)
    released: list[str] = []
    for session_id in sorted(leases):
        lease = leases[session_id]
        if bool(lease.get("confirmed")):
            continue
        if float(lease.get("expire_at_epoch_s", 0.0)) > now_epoch_s:
            continue
        table.release(list(lease["cells"]))
        leases.pop(session_id)
        released.append(session_id)
    return released
