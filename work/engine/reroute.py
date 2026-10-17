"""前车再疏导(work/engine/README.md 2.2 的③;手册 §7.6 `every_60s()` / §7.7)。

每 `recompute_period_s` 检查在途车辆:前方路段变堵时,在**下一个可分岔路口之前**给改道建议
(**每车最多 `reroute_max` 次**,**`hysteresis` 滞回**防抖);送完客的车优先引导离开落客区。

| 参数 | 来源 |
|---|---|
| `reroute_max`(每车最多改道次数) | `stations/thresholds.json` 的 `decision` 组 |
| `hysteresis`(切换滞回,收益不到就不改) | 同上 |
| `recompute_period_s`(检查周期,由 run.py 的周期调度使用) | 同上 |
| 再疏导触发阈值 `REROUTE_TH`(ETA 增加超过多少才考虑改道) | **站点包 decision 组尚无独立键**(手册标【待标定】);本实现以同组的 `eps_harm_s` 代用 —— 两者同为"ETA 增加量(秒)"阈值。待池·P 标定后由开发B 在站点包补键,本文件再改读新键 |
| `k_candidates` / `max_path_overlap`(备用路径生成) | 同上 |

三个条件**同时**满足才改:
  ① 重新沿剩余路径走的 ETA,比**登记时对同一段剩余路的计划耗时**增加超过触发阈值
     (同类口径比较:在途车只比剩余段,不拿"剩余 ETA"减"整条路径 ETA");
  ② 该车改道次数 < `reroute_max`;
  ③ 还在"下一个可分岔路口之前"(改道方案相对剩余路径的分岔点仍在车前方 —— 车还没开过)。

**改道候选必须复核约束①/②**:
  - 候选只从登记时通过约束的 `feasible_candidates` 里取(还没出发时),或从当前位置重新生成(已出发);
  - 每条候选都要复核 `max_slot_x ≤ x_safe` 与 `harm_check.max_eta_increase_s ≤ eps_harm_s`
    —— 改道同样不能落到已超饱和 / 会伤前车的路线。

**收益不到 `hysteresis` 不改**:更优路径的 ETA 改善率必须严格大于 `hysteresis`,否则维持原路线
(防"改过去又改回来"的抖动)。改道后把旧格子的占用撤掉、把新格子的占用登记进同一张预约表。

本文件**不写死任何判据数值**,全部从 `params`(站点包 decision 组)取。
用法:由 run.py 的 `--compare` 链路调用,不单独执行。
"""

from __future__ import annotations

import math
from typing import Any, Callable

import candidates
import network
import reserve


def reroute_threshold_s(params: dict[str, Any]) -> float:
    """再疏导触发阈值(秒):"ETA 增加超过多少才考虑改道"。

    ⚠️ 手册 §7.7 把 `REROUTE_TH` 标为【待标定】,但站点包 `decision` 组目前**没有这个键**。
    为了不在代码里写死一个数字(`docs/开发规范.md` 全仓铁律),这里**代用同组的
    `eps_harm_s`** —— 它同样是"ETA 增加量(秒)"口径的【待标定】阈值。站点包补键后,
    这里应改为优先读 `params["reroute_th_s"]`、缺键再回退(见 work/engine/DESIGN.md 的申报)。
    """
    return float(params["eps_harm_s"])


def _remaining_path(lease: dict[str, Any]) -> list[str]:
    """租约当前**还没走完**的路段序列(按已完成的边数 `progress_edges` 截断)。"""
    path = list(lease.get("path") or [])
    progress = int(lease.get("progress_edges", 0))
    if progress < 0:
        progress = 0
    return path[progress:]


def _remaining_eta(
    table: reserve.SlotTable,
    lease: dict[str, Any],
    now_epoch_s: float,
) -> tuple[list[str], float]:
    """按**当前**预约表重算剩余路径的 ETA(前车自己的占用已在表里,故 `extra=0`)。"""
    remaining = _remaining_path(lease)
    if not remaining:
        return [], 0.0
    _cells, eta_s = reserve.walk_slots(table, remaining, float(now_epoch_s), extra=0.0)
    return remaining, eta_s


def _planned_remaining_eta_s(lease: dict[str, Any]) -> float | None:
    """登记时对**剩余路段**的预计耗时(同类口径基线)。

    判据①要比较的是"同一位置、同一规划"下的两个剩余 ETA:
      - 登记时预计从现在起还要多久 → 用租约里逐边的计划服务时间,把还没走的那几条加起来;
      - 现在预计还要多久 → 用当前预约表重新 `walk` 剩余路径。
    **不能**拿"当前剩余 ETA"去减"登记时整条路径 ETA"——在途车已经走掉一段,差值必然为负,
    结果只有封路(+inf)才可能触发再疏导(2026-10-17 快速独立审查发现 1)。
    """
    path = list(lease.get("path") or [])
    progress = int(lease.get("progress_edges", 0))
    edge_times = lease.get("edge_times_s")
    if isinstance(edge_times, list) and len(edge_times) == len(path):
        return float(sum(float(value) for value in edge_times[progress:]))
    # 兼容没有逐边计划耗时的租约(本模块自己登记的租约都带;外部传入的旧租约按边数比例摊)
    if not path:
        return None
    if progress == 0:
        return float(lease["eta_s"])
    return float(lease["eta_s"]) * float(len(path[progress:])) / float(len(path))


def _candidate_feasible(
    table: reserve.SlotTable,
    lease: dict[str, Any],
    path: list[str],
    leases: dict[str, dict[str, Any]] | None,
    params: dict[str, Any],
    now_epoch_s: float,
) -> tuple[list[tuple[str, int]], float, list[float]] | None:
    """改道候选是否仍满足约束①(饱和度)与约束②(不伤害前车);不满足返回 None。

    做法:
      1. 先把本车**旧占用**临时撤掉,再试算候选(=`extra=1` 把这辆车算进去)并算 `max_slot_x`;
      2. 再在"当前表(含本车旧占用)"上用与 `recommend()` 相同的 `harm_check` 度量对**其他**
         前车的 ETA 伤害(`session_id` 排除本车);
      3. 撤掉的旧占用在 `finally` 里恢复 —— 本函数不改变预约表。
    拒绝时返回 None,调用方继续看下一条候选(不会落到已超 x_safe / 伤前车的路线)。
    """
    own_cells = list(lease.get("cells") or [])
    table.release(own_cells)
    try:
        cells, eta_s, edge_times = reserve.walk_slots_detail(
            table, list(path), float(now_epoch_s), extra=1.0
        )
        max_x = reserve.max_slot_x(table, cells)
    finally:
        table.reserve(own_cells)
    if not math.isfinite(max_x) or max_x > float(params["x_safe"]):
        return None
    if leases:
        others = {
            session_id: other
            for session_id, other in leases.items()
            if session_id != lease.get("session_id")
        }
        if others:
            harm = reserve.harm_check(table, cells, others, params)
            if float(harm["max_eta_increase_s"]) > float(params["eps_harm_s"]):
                return None
    return cells, eta_s, edge_times


def is_before_next_branch(
    lease: dict[str, Any],
    graph: network.Graph,
    better_path: list[str] | None = None,
) -> bool:
    """这辆车是否还在"下一个可分岔路口之前"(在分岔前给建议才来得及)。

    - 已走完全程(或没有剩余路径)→ 不在分岔前;
    - 与改道方案比较:两者的第一条不同边出现的位置就是"分岔点";
      只要**分岔点仍在剩余路径上**(车还没开过它),就还来得及改;
    - 剩余路径与改道方案完全相同时没有"分岔",不算。
    """
    path = list(lease.get("path") or [])
    progress = int(lease.get("progress_edges", 0))
    if progress >= len(path):
        return False
    remaining = path[progress:]
    if not remaining or not better_path:
        return False
    better = list(better_path)
    if better == remaining:
        return False
    common = 0
    limit = min(len(remaining), len(better))
    while common < limit and remaining[common] == better[common]:
        common += 1
    if common >= len(remaining) or common >= len(better):
        # 一条是另一条的前缀:没有可用的分岔点
        return False
    branch_from = str(graph.edge(remaining[common])["from"])
    # 分岔点必须真的有多条出边(否则"分岔"只是绕过它,不构成可分岔路口)
    return len(graph.out_edges(branch_from)) > 1


def _table_weight(
    table: reserve.SlotTable,
    now_epoch_s: float,
) -> Callable[[str], float]:
    """候选生成用的边权重(秒):按**当前时刻**的时段格子算,封闭路段为 +inf(不可选)。"""
    slot_index = reserve.slot_index_of(now_epoch_s, table.slot_minutes)

    def weight(edge_id: str) -> float:
        return table.tt(edge_id, slot_index, extra=0.0)

    return weight


def best_alternative(
    graph: network.Graph,
    lease: dict[str, Any],
    candidate_paths: list[list[str]] | None,
    params: dict[str, Any],
    table: reserve.SlotTable | None = None,
    now_epoch_s: float | None = None,
    leases: dict[str, dict[str, Any]] | None = None,
) -> list[str] | None:
    """按滞回判据挑一条更优路径;收益不到 `hysteresis` 就返回 None(防抖)。

    - 车辆还没出发(`progress_edges = 0`)时,优先复用**登记时通过两条约束的候选集**
      (`lease["feasible_candidates"]`,只含合规路线);
    - 车辆已走过部分路段时,从**当前位置**用 Yen 重新生成候选(K / 重叠度仍读站点包);
    - 每条候选都要**复核约束①(饱和度)与约束②(不伤害前车)** 才参与择优 ——
      改道同样不能落回已超 x_safe / 伤前车的路线(2026-10-17 快速独立审查发现 2);
    - 收益 = `(当前剩余 ETA - 备选 ETA) / 当前剩余 ETA`,严格大于 `hysteresis` 才改;
    - 当前路已不可通行(+inf)时,任何有限 ETA 的备选都视为 100% 收益。
    """
    if table is None or now_epoch_s is None:
        raise ValueError("best_alternative 需要 table 与 now_epoch_s(参数由 run.py 传入)")
    remaining, current_eta = _remaining_eta(table, lease, float(now_epoch_s))
    if not remaining:
        return None

    progress = int(lease.get("progress_edges", 0))
    pool: list[list[str]] = []
    if progress == 0 and candidate_paths:
        pool = [list(path) for path in candidate_paths if list(path) != remaining]
    if not pool:
        src = str(graph.edge(remaining[0])["from"])
        dst = str(graph.edge(remaining[-1])["to"])
        pool = candidates.select_candidates(
            graph,
            src,
            dst,
            k=int(params["k_candidates"]),
            max_overlap=float(params["max_path_overlap"]),
            weight=_table_weight(table, float(now_epoch_s)),
        )

    scored: list[tuple[float, tuple[str, ...], list[str]]] = []
    for path in pool:
        edge_path = list(path)
        if not edge_path or edge_path == remaining:
            continue
        checked = _candidate_feasible(
            table, lease, edge_path, leases, params, float(now_epoch_s)
        )
        if checked is None:
            continue  # 复核没过:不参与择优
        _cells, eta_s, _edge_times = checked
        if not math.isfinite(eta_s):
            continue
        scored.append((eta_s, tuple(edge_path), edge_path))
    if not scored:
        return None

    best_eta, _key, best_path = min(scored, key=lambda item: (round(item[0], 6), item[1]))
    hysteresis = float(params["hysteresis"])

    if not math.isfinite(current_eta):
        return best_path if math.isfinite(best_eta) else None
    if current_eta <= 0.0:
        return None
    if not math.isfinite(best_eta):
        return None
    improvement = (current_eta - best_eta) / current_eta
    if improvement <= hysteresis:
        return None
    return best_path


def should_reroute(
    graph: network.Graph,
    lease: dict[str, Any],
    params: dict[str, Any],
    table: reserve.SlotTable | None = None,
    now_epoch_s: float | None = None,
    candidate_paths: list[list[str]] | None = None,
    leases: dict[str, dict[str, Any]] | None = None,
) -> bool:
    """三个条件**同时**满足才返回 True(手册 §7.6 的 `if` 行)。

    ① 剩余路径重算 ETA 比**登记时对同一段剩余路的计划耗时**增加超过触发阈值
       (`_planned_remaining_eta_s`,同类口径比较,阈值 = `reroute_threshold_s(params)`);
    ② `reroute_count < reroute_max`;
    ③ 还在下一个可分岔路口之前(`is_before_next_branch`);
    并通过 `best_alternative` 的 `hysteresis` 收益判据;候选还要复核约束①/②。
    通过时把改道方案暂存到 `lease["_pending_better"]`,供 `reroute()` 取用。
    """
    if table is None or now_epoch_s is None:
        raise ValueError("should_reroute 需要 table 与 now_epoch_s(参数由 run.py 传入)")
    if int(lease.get("reroute_count", 0)) >= int(params["reroute_max"]):
        return False

    remaining, eta_now = _remaining_eta(table, lease, float(now_epoch_s))
    if not remaining:
        return False

    planned_remaining_s = _planned_remaining_eta_s(lease)
    if planned_remaining_s is None:
        return False
    increase_s = eta_now - planned_remaining_s
    threshold_s = reroute_threshold_s(params)
    # 当前 ETA 为 +inf(前方封路)时 increase 也是 +inf,必然超阈
    if not (increase_s > threshold_s):
        return False

    better = best_alternative(
        graph,
        lease,
        candidate_paths,
        params,
        table,
        now_epoch_s,
        leases=leases,
    )
    if better is None:
        return False
    if not is_before_next_branch(lease, graph, better):
        return False

    lease["_pending_better"] = [str(edge_id) for edge_id in better]
    lease["_pending_increase_s"] = increase_s
    lease["_pending_eta_now_s"] = eta_now
    return True


def reroute(
    lease: dict[str, Any],
    better_path: list[str],
    reason: str,
    table: reserve.SlotTable | None = None,
    now_epoch_s: float | None = None,
) -> dict[str, Any]:
    """执行改道并返回新的 `reroute` 段(`{count, reason}`,契约第二节)。

    - 计数 +1(`reroute_count`),并记下最近一次原因;
    - 传了 `table` / `now_epoch_s` 时**同步预约表**:撤掉旧占用的格子,把新路径的格子登记上,
      租约起点重置为改道时刻(后续"ETA 增加"从这一刻重新计);
    - 次数上限由 `should_reroute` 先判(三条件之一),本函数只做记账与回写,不再重复判。
    """
    count = int(lease.get("reroute_count", 0)) + 1
    lease["reroute_count"] = count
    lease["reroute_reason"] = str(reason)
    lease["_pending_better"] = None
    lease["_pending_increase_s"] = None
    lease["_pending_eta_now_s"] = None

    if table is not None and now_epoch_s is not None:
        table.release(list(lease.get("cells") or []))
        cells, eta_s, edge_times = reserve.walk_slots_detail(
            table, list(better_path), float(now_epoch_s), extra=1.0
        )
        table.reserve(cells)
        lease["path"] = [str(edge_id) for edge_id in better_path]
        lease["cells"] = cells
        lease["edge_times_s"] = [float(value) for value in edge_times]
        lease["eta_s"] = float(eta_s)
        lease["start_epoch_s"] = float(now_epoch_s)
        lease["expire_at_epoch_s"] = float(now_epoch_s)
        lease["progress_edges"] = 0
        # 旧候选集是"从原起点出发"的路径,改道后已不适用;清空后下次从当前位置重新生成
        lease["feasible_candidates"] = []
    else:
        lease["path"] = [str(edge_id) for edge_id in better_path]
        lease["progress_edges"] = 0

    return {"count": count, "reason": str(reason)}


def check_and_reroute(
    table: reserve.SlotTable,
    leases: dict[str, dict[str, Any]],
    graph: network.Graph,
    params: dict[str, Any],
    now_ts: str,
    all_leases: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """一个决策周期(手册 §7.6 `every_60s()` 里"前车优先"的那段)。

    - 按**进入顺序**遍历在途租约(先进入的前车优先被疏导),超过次数上限的不再处理;
    - `leases` 是本周期要检查的**在途子集**;约束②复核"会不会伤前车"时要看**全量租约**,
      由 `all_leases` 传入(缺省时退回 `leases`);
    - 返回本周期发生的改道事件列表(`{session_id, eta_before_s, eta_after_s, reroute}`),
      供 run.py 写进 `--compare` 的再疏导记录。**没有事件时返回空列表**(不编事件)。
    """
    now_epoch_s = reserve.iso_to_epoch_s(now_ts)
    harm_scope = all_leases if all_leases is not None else leases
    events: list[dict[str, Any]] = []
    ordered = sorted(
        leases,
        key=lambda session_id: (float(leases[session_id]["start_epoch_s"]), session_id),
    )
    for session_id in ordered:
        lease = leases[session_id]
        if not bool(lease.get("confirmed")):
            continue
        if int(lease.get("reroute_count", 0)) >= int(params["reroute_max"]):
            continue
        if not should_reroute(
            graph,
            lease,
            params,
            table=table,
            now_epoch_s=now_epoch_s,
            candidate_paths=list(lease.get("feasible_candidates") or []),
            leases=harm_scope,
        ):
            continue

        better = list(lease.get("_pending_better") or [])
        increase_s = float(lease.get("_pending_increase_s") or 0.0)
        eta_before_s = float(lease.get("_pending_eta_now_s") or 0.0)
        # 先执行改道(它会撤旧格、登新格并算出改道后的剩余 ETA),再按真实数字写原因
        block = reroute(lease, better, "改道原因见下", table=table, now_epoch_s=now_epoch_s)
        eta_after_s = float(lease["eta_s"])
        if math.isfinite(eta_before_s) and eta_before_s > 0.0:
            gain_pct = (eta_before_s - eta_after_s) / eta_before_s
            cost_text = f"剩余耗时 {eta_before_s:.1f}s → {eta_after_s:.1f}s(收益 {gain_pct:.1%})"
        else:
            cost_text = f"原路线已不可通行,改道后剩余耗时 {eta_after_s:.1f}s"
        segments_text = "→".join(
            str(graph.edge(edge_id).get("section") or edge_id) for edge_id in better
        )
        if math.isfinite(increase_s):
            trigger_text = f"剩余 ETA 增加 {increase_s:.1f}s"
        else:
            trigger_text = "前方路段封闭"
        reason = (
            f"前方路段变慢:{trigger_text}"
            f"(触发阈值 {reroute_threshold_s(params):.1f}s),改走 {segments_text}({cost_text})"
        )
        lease["reroute_reason"] = reason
        block["reason"] = reason
        events.append(
            {
                "session_id": session_id,
                "eta_before_s": round(eta_before_s, 2) if math.isfinite(eta_before_s) else None,
                "eta_after_s": round(eta_after_s, 2),
                "reroute": block,
            }
        )
    return events
