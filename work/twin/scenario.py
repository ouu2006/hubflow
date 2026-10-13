"""场景组装:读站点包的 scenarios.json,给出本次运行用哪个场景、开哪些开关。

输入:stations/scenarios.json(真孪生);samples/(--no-sumo 时的样例场景)
输出:ScenarioState(内存对象,不落盘)
口径:scenarios.json 的 assimilation 开关是"同化回灌开 / 关"的唯一出处,
     场景二拿它做对照(TC-20);站点包未到位时降级为样例场景并写明,不编造站点参数。

用法:由 loop.py 调用,不单独执行。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: 一期四个场景(README 第六节:场景名固定,取值封闭)
SCENARIOS = ("scenario_1", "scenario_2", "scenario_3", "scenario_4")
SCENARIO_NAMES_ZH = {
    "scenario_1": "常态",
    "scenario_2": "峰值",
    "scenario_3": "突发",
    "scenario_4": "多因素",
}

#: stations/scenarios.json 的 assimilation 开关默认值(契约 6.2)
DEFAULT_ASSIMILATION = {
    "enabled": True,
    "edges": (),
    "period_s": 60,
    "gate": {"confidence_min": 0.6, "data_age_max_s": 120},  # 【待标定】
}


@dataclass
class ScenarioState:
    """一次运行用的场景状态。"""

    name: str
    seed: int
    is_sample: bool = False
    assimilation: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_ASSIMILATION))
    injected: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def load_scenario(cfg: Any, samples: dict[str, dict[str, Any]]) -> ScenarioState:
    """组装场景。

    --no-sumo:返回样例场景(assimilation 按契约默认开,断面清单为空,
    真正的边界断面清单来自 stations/points.json —— 站点包未到位)。
    真孪生:读 stations/scenarios.json 的对应场景,注入事件与种子照抄(种子必须固定才能复现)。
    """
    if cfg.no_sumo:
        return ScenarioState(
            name=cfg.scenario,
            seed=cfg.seed,
            is_sample=True,
            notes=[
                "样例场景:samples/ 驱动,未读 stations/scenarios.json",
                "assimilation 用契约默认值,真实断面清单待 stations/points.json(T1)",
            ],
        )
    raise NotImplementedError(
        "真孪生场景待 W1 实现:读 stations/scenarios.json(开关 / 注入事件 / 种子)"
    )


def assimilation_enabled(scene: ScenarioState) -> bool:
    """本次运行是否开数据同化回灌(场景二拿它做开 / 关对照)。"""
    return bool(scene.assimilation.get("enabled", False))


def boundary_edges(scene: ScenarioState) -> tuple[str, ...]:
    """允许回灌的边界断面(只有 role="boundary" 才允许,内部路段永不回灌)。"""
    return tuple(scene.assimilation.get("edges", ()))
