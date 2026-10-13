"""前车再疏导(work/engine/README.md 2.2 第③件事;分工表 §8.2 的 **W5**)。

每 **60 秒**检查在途车辆:前方路段变堵时,在**下一个可分岔路口前**给出改道建议:

| 参数 | 值 | 出处 |
|---|---|---|
| 检查周期 | **60 s** | README 2.4 |
| 每车最多改道 | **2 次** | README 2.3 步骤⑥ / 契约第二节 `reroute.count` |
| 切换滞回 | **10%** | 改道收益不到 10% 就不改,防抖 |
| 时机 | **下一个可分岔路口前** | README 2.2 |

口径:改道**只为给后车腾容量** —— 前车被及时疏散,后车才有位置(TC-17 第①项)。
输出回写到 `routes.json` 的 `reroute: {count, reason}`(契约第二节)。

⚠️ **本文件是 W0 骨架,函数边界先定、实现待 W5**。手册建议先在**3 条路的小路网上**验证
   (`work/engine/samples/network_sample.json` 的 N-01 → N-05 恰好有 3 条走廊)。

用法:由 run.py 调用,不单独执行。
"""

from __future__ import annotations

from typing import Any

#: 检查周期(秒)
CHECK_PERIOD_S = 60

#: 每车最多改道次数(超过不再改)
REROUTE_MAX = 2


def is_before_next_branch(lease: dict[str, Any], graph: Any) -> bool:
    """这辆车是否还在"下一个可分岔路口之前"(在分岔前给建议才来得及)。骨架,TODO(W5)。"""
    raise NotImplementedError("分岔判断待 W5 实现:在下一个可分岔路口前才给改道建议")


def best_alternative(
    graph: Any,
    lease: dict[str, Any],
    candidate_paths: list[list[str]],
    params: dict[str, Any],
) -> list[str] | None:
    """按滞回判据挑一条更优路径;收益不到 `hysteresis` 就返回 None(防抖)。骨架,TODO(W5)。"""
    raise NotImplementedError("改道择优待 W5 实现:hysteresis = 0.10 才换路")


def should_reroute(graph: Any, lease: dict[str, Any], params: dict[str, Any]) -> bool:
    """三个条件同时满足才改:ETA 增加超阈、未超次数上限、还在分岔前。骨架,TODO(W5)。"""
    raise NotImplementedError("改道判定待 W5 实现(手册 7.7)")


def reroute(lease: dict[str, Any], better_path: list[str], reason: str) -> dict[str, Any]:
    """执行改道并返回新的 `reroute` 段(`{count, reason}`,契约第二节)。骨架,TODO(W5)。"""
    raise NotImplementedError("再疏导回写待 W5 实现:每车最多改 2 次")
