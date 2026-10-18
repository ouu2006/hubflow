"""场景组装:读站点包的 scenarios.json,给出本次运行用哪个场景、开哪些开关。

输入:stations/scenarios.json(真孪生);samples/(--no-sumo 时的样例场景)
输出:ScenarioState(内存对象,不落盘)
口径:scenarios.json 的 assimilation 开关是"同化回灌开 / 关"的唯一出处,
     场景二拿它做对照(TC-20);站点包未到位时降级为样例场景并写明,不编造站点参数。

本文件有两条路径:

1. **样例路径（保留）**：`loop.py --no-sumo` 时返回样例场景（assimilation 用契约默认值，
   断面清单为空）——输出形状与改造前一致；
2. **真路径（Issue IKMS19）**：读 `stations/scenarios.json` 的 S1~S4（`seed` / `assimilation`
   开关与 `edges` / `gate` / `period_s` / `switches` / `factors` 注入事件），
   并做**命名空间校验**：`assimilation.edges` 里的段号必须在**本站真网段号集合**内；
   写进 `internal` 的 edge 是配置错误（契约 §6.2，脚本报错退出）。

用法:由 `run_assimilation.py` / `loop.py` 调用,不单独执行。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: 本文件位于 work/twin/ → 仓库根是 parents[1]
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
STATIONS = REPO_ROOT / "stations"

#: 一期四个场景(README 第六节:场景名固定,取值封闭)
SCENARIOS = ("scenario_1", "scenario_2", "scenario_3", "scenario_4")
SCENARIO_NAMES_ZH = {
    "scenario_1": "常态",
    "scenario_2": "峰值",
    "scenario_3": "突发",
    "scenario_4": "多因素",
}

#: `stations/scenarios.json` 里的场景 id（顺序与 SCENARIOS 一一对应）
SCENARIO_IDS = ("S1", "S2", "S3", "S4")

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
    switches: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    source_file: str | None = None
    evaluation_ts: str | None = None


def read_json(path: Path) -> dict[str, Any]:
    """读一个 UTF-8 JSON 文件(显式编码,换机器不乱码)。"""
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def load_station_scenarios(stations_dir: Path | str | None = None) -> dict[str, Any]:
    """读站点包 `scenarios.json`（缺文件/缺 scenarios 数组直接报错，不降级编数）。"""
    path = Path(stations_dir or STATIONS) / "scenarios.json"
    if not path.is_file():
        raise SystemExit(f"缺站点包 {path}（真路径需要 scenarios.json 的场景开关）")
    payload = read_json(path)
    rows = payload.get("scenarios")
    if not isinstance(rows, list) or not rows:
        raise SystemExit(f"{path} 缺非空 scenarios 数组")
    for row in rows:
        if not isinstance(row, dict) or not row.get("scenario_id"):
            raise SystemExit(f"{path} 的 scenarios[] 里有场景缺 scenario_id")
    return payload


def normalize_scenario_key(key: str) -> str:
    """场景键归一：`S4` / `scenario_4` / `多因素` → `S4`；认不出报错（不静默用默认场景）。"""
    text = str(key or "").strip()
    if text in SCENARIO_IDS:
        return text
    if text in SCENARIOS:
        return SCENARIO_IDS[SCENARIOS.index(text)]
    for scenario_id, name in zip(SCENARIO_IDS, SCENARIO_NAMES_ZH.values()):
        if text == name:
            return scenario_id
    raise SystemExit(f"未知场景 {key!r}（可用：{' / '.join(SCENARIO_IDS)}，或 scenario_1~4 / 常态~多因素）")


def find_scenario(payload: dict[str, Any], key: str) -> dict[str, Any]:
    """在 `scenarios[]` 里按归一后的场景 id 找记录（找不到报错，不静默回落）。"""
    scenario_id = normalize_scenario_key(key)
    for row in payload["scenarios"]:
        if str(row.get("scenario_id")) == scenario_id:
            return dict(row)
    raise SystemExit(f"站点包 scenarios.json 里没有场景 {scenario_id}（不静默用别的场景顶替）")


def scenario_from_station(
    payload: dict[str, Any],
    key: str,
    source_file: Path | str | None = None,
) -> ScenarioState:
    """`stations/scenarios.json` 的一条场景记录 → `ScenarioState`（开关/注入事件/种子照抄）。"""
    row = find_scenario(payload, key)
    assimilation = row.get("assimilation") or {}
    merged = dict(DEFAULT_ASSIMILATION)
    merged.update(
        {
            "enabled": bool(assimilation.get("enabled", DEFAULT_ASSIMILATION["enabled"])),
            "edges": tuple(str(edge) for edge in (assimilation.get("edges") or [])),
            "period_s": int(assimilation.get("period_s") or DEFAULT_ASSIMILATION["period_s"]),
            "gate": dict(DEFAULT_ASSIMILATION["gate"])
            | dict(assimilation.get("gate") or {}),
        }
    )
    factors = row.get("factors") or []
    if not isinstance(factors, list):
        raise SystemExit(f"场景 {row.get('scenario_id')} 的 factors 不是数组")
    return ScenarioState(
        name=str(row["scenario_id"]),
        seed=int(row.get("seed", 0)),
        is_sample=False,
        assimilation=merged,
        injected=[dict(item) for item in factors],
        switches=dict(row.get("switches") or {}),
        notes=[
            f"场景来自 stations/scenarios.json：{row.get('scenario_id')}（{row.get('name')}）",
            "assimilation.edges 必须在真网段号集合内；internal 段号写进来视为配置错误（契约 §6.2）",
        ],
        source_file=str(source_file) if source_file else None,
    )


def load_scenario(cfg: Any, samples: dict[str, dict[str, Any]]) -> ScenarioState:
    """组装场景。

    --no-sumo:返回样例场景(assimilation 按契约默认开,断面清单为空,
    真正的边界断面清单来自 stations/points.json —— 站点包未到位)。
    真孪生:读 stations/scenarios.json 的对应场景,注入事件与种子照抄(种子必须固定才能复现)。
    """
    # 场景名取值封闭(README 第六节);拼错的场景名照跑照记,下游会当成"跑过了 scenario_x"
    if cfg.scenario not in SCENARIOS and cfg.scenario not in SCENARIO_IDS:
        raise ValueError(f"未知场景:{cfg.scenario!r}(仅 {SCENARIOS} 或 {SCENARIO_IDS})")
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
    payload = load_station_scenarios(getattr(cfg, "stations_dir", None))
    return scenario_from_station(payload, cfg.scenario)


def assimilation_enabled(scene: ScenarioState) -> bool:
    """本次运行是否开数据同化回灌(场景二拿它做开 / 关对照)。"""
    return bool(scene.assimilation.get("enabled", False))


def boundary_edges(scene: ScenarioState) -> tuple[str, ...]:
    """允许回灌的边界断面(只有 role="boundary" 才允许,内部路段永不回灌)。"""
    return tuple(scene.assimilation.get("edges", ()))
