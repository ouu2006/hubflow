"""容量模型:按路型标定单车道饱和流率,再乘时段运营系数,给出"这一刻的有效通行能力"。

## 为什么另立一张表

原口径(`loop.py` 的 `c_base_vph = 每方向车道数 × 方向数 × saturation_flow_vph_per_lane`)
对所有段用同一个 1800 辆/(h·车道),于是 61 段里 44 段 ramp(停车场内部通道/服务道路/连接匝道)
也被算成 7200 辆/h —— 一条 44 m 长的停车场通道拿到四车道主干道的通行能力,
饱和度 x 被系统性压低(0.14 让"严重拥堵"看起来自相矛盾)。

本模块把容量拆成两截:

1. **路型基数**:`lane_saturation_vph_by_class`(arterial 1800 / service 620 / parking_aisle 420 …),
   段的路型由 `segment_kind`(main / ramp,来自 `work/twin/netpack/network_junction.enriched.json`)
   经 `class_by_kind` 映射;每方向车道数按 `lanes_cap_per_direction_by_class` 取上限,
   兜住 OSM `lanes` 标签的明显异常(存在"5 车道 / 33 m 段"这类记录)。
2. **时段运营系数**:`phase_capacity_factor`(早高峰 0.80 / 平峰 1.00 / 晚高峰 0.75 / 夜间 0.92)。
   物理含义是信号周期与绿信比、站前落客占道、停车场闸机排队带来的**有效**通行能力折减,
   上限仍是路型基数。**这是演示标定,不是实测标定**,上生产需用信号配时与占道数据替换。

## 时段从哪来

仿真时钟只有一个(`DEMO_BASE_TS` 起跑,约 65 min 全程落在夜间),按钟点取阶段永远看不到变化。
所以 `demo_phase_mode` 给两个口径:

- `clock`:按 `base_ts + 仿真秒数` 的钟点落 `phase_clock_windows`(真实口径);
- `cycle`(**演示默认**):每 `demo_phase_cycle_s` 秒轮转一个运营阶段
  (早高峰→平峰→晚高峰→夜间),让容量在演示里随阶段变化。

两条口径都写进每条记录的 `capacity_phase*` 字段,溯源清楚。

## 表放在哪

`work/twin/capacity-model.json`(**与本模块同目录**),不放 `stations/`:`stations/*.json` 是
**表格转换产物**,受数据契约的字段命名(`scripts/doc_gate.py` 第 6 组)与填表报告台账
(第 7 组)约束 —— 段号 `SZ-001`、阶段名 `早高峰` 这类**领域键**过不了 snake_case 门禁。
本表是孪生侧的**演示标定参数**(跟 `capacity.py`、`thresholds` 的消费逻辑一起走),
不是任何 T1~T9 表格转出来的东西,故与代码同目录、由代码维护。

用法:由 `loop.py` 调用;`work/assembly/traffic.py` 也读同一张表做接口侧折算,不复制系数。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

#: 本文件位于 work/twin/ → 仓库根是 parents[1]
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
STATIONS = REPO_ROOT / "stations"

#: 容量模型路径:与模块同目录(见文件头「表放在哪」)。不要挪回 `stations/`——
#: 那是表格产物目录,`SZ-001` / `早高峰` 这类领域键会被 doc_gate 第 6 组判 snake_case 违规。
MODEL_PATH = HERE / "capacity-model.json"

#: 运营阶段顺序(与前端 TimeSession / 接口层 SESSION_ORDER 同集合,别改名)
PHASE_ORDER = ("早高峰", "平峰", "晚高峰", "夜间")

#: 缺省路型(段号不在 segment_kind 表里时按主干道算,并在 meta 里标 fallback)
DEFAULT_KIND = "main"


def load(model_path: Path | str | None = None) -> dict[str, Any]:
    """读 `work/twin/capacity-model.json` 并校验必需键(缺键直接报错,不猜默认值)。

    只接**模型文件路径**:容量模型不再住在 `stations/` 里,站点包目录对它没有意义,
    留着 `stations_dir` 参数只会让调用方以为"每个站一份模型"。
    """
    path = Path(model_path) if model_path else MODEL_PATH
    if not path.is_file():
        raise SystemExit(f"缺容量模型 {path}（容量标定是 c_base_vph 的唯一出处）")
    with path.open("r", encoding="utf-8") as fp:
        model = json.load(fp)
    required = (
        "class_by_kind",
        "lane_saturation_vph_by_class",
        "lanes_cap_per_direction_by_class",
        "segment_kind",
        "phase_capacity_factor",
    )
    missing = [key for key in required if key not in model]
    if missing:
        raise SystemExit(f"{path} 缺必需键 {missing}")
    for phase in PHASE_ORDER:
        if phase not in model["phase_capacity_factor"]:
            raise SystemExit(f"{path} 的 phase_capacity_factor 缺阶段 {phase}")
    return model


def class_of(model: dict[str, Any], segment_id: str) -> tuple[str, str]:
    """段 → `(路型 class, kind)`;段号不在表里时回落 DEFAULT_KIND。"""
    kind = str(model["segment_kind"].get(str(segment_id)) or DEFAULT_KIND)
    cls = str(model["class_by_kind"].get(kind) or model["class_by_kind"][DEFAULT_KIND])
    return cls, kind


def base_capacity(
    model: dict[str, Any],
    segment_id: str,
    lanes_per_direction: int,
    direction_count: int,
) -> tuple[float, dict[str, Any]]:
    """基期通行能力(辆/h)= 有效每方向车道数 × 方向数 × 路型单车道饱和流率。

    返回 `(c_base_vph, meta)`;meta 里逐项写清车道数取上限前后的值,便于审计"为什么是这个数"。
    """
    cls, kind = class_of(model, segment_id)
    saturation = float(model["lane_saturation_vph_by_class"].get(cls) or 0.0)
    if saturation <= 0:
        raise SystemExit(f"容量模型的路型 {cls} 缺正的单车道饱和流率")
    cap = int(model["lanes_cap_per_direction_by_class"].get(cls) or 1)
    lanes_raw = max(1, int(lanes_per_direction or 1))
    lanes = min(lanes_raw, cap) if cap > 0 else lanes_raw
    dirs = max(1, int(direction_count or 1))
    c_base = round(float(lanes * dirs) * saturation, 1)
    return c_base, {
        "class": cls,
        "kind": kind,
        "lanes_per_direction": lanes,
        "lanes_raw": lanes_raw,
        "lanes_capped": lanes != lanes_raw,
        "direction_count": dirs,
        "lane_saturation_vph": saturation,
    }


def _minutes(hhmm: str) -> int:
    """'06:00' → 360(分钟)。"""
    parts = str(hhmm).split(":")
    if len(parts) != 2:
        raise SystemExit(f"时段窗口时刻 {hhmm!r} 不是 HH:MM")
    return int(parts[0]) * 60 + int(parts[1])


def phase_by_clock(model: dict[str, Any], moment: datetime) -> dict[str, Any]:
    """按钟点落阶段(夜间跨零点:"20:00"-"06:00" 视为 [1200, 1440) ∪ [0, 360))。"""
    windows = model.get("phase_clock_windows") or {}
    if not windows:
        raise SystemExit("容量模型缺 phase_clock_windows（clock 模式无窗口可依,不猜）")
    minutes = moment.hour * 60 + moment.minute
    for phase in PHASE_ORDER:
        window = windows.get(phase)
        if not window or len(window) != 2:
            continue
        start, until = _minutes(window[0]), _minutes(window[1])
        if start <= until:
            if start <= minutes < until:
                return _phase(model, phase, "clock")
        elif minutes >= start or minutes < until:
            return _phase(model, phase, "clock")
    fallback = PHASE_ORDER[1]
    return _phase(model, fallback, "clock-fallback")


def phase_by_cycle(model: dict[str, Any], elapsed_s: int) -> dict[str, Any]:
    """演示时间轴压缩:每 `demo_phase_cycle_s` 秒轮转一个运营阶段。"""
    cycle = int(model.get("demo_phase_cycle_s") or 0)
    if cycle <= 0:
        raise SystemExit("容量模型 demo_phase_mode=cycle 但 demo_phase_cycle_s 非正")
    index = (max(0, int(elapsed_s)) // cycle) % len(PHASE_ORDER)
    return _phase(model, PHASE_ORDER[index], "cycle")


def _phase(model: dict[str, Any], phase: str, source: str) -> dict[str, Any]:
    factor = float(model["phase_capacity_factor"][phase])
    if not (0 < factor <= 1.0):
        raise SystemExit(f"容量模型阶段 {phase} 的系数 {factor} 不在 (0,1]")
    return {
        "phase_id": phase,
        "phase_label": phase,
        "phase_factor": round(factor, 4),
        "phase_source": source,
    }


def phase_at(
    model: dict[str, Any], base_ts: str, elapsed_s: int
) -> dict[str, Any]:
    """当前生效的运营阶段:按 `demo_phase_mode` 选 clock / cycle。"""
    mode = str(model.get("demo_phase_mode") or "cycle")
    if mode == "clock":
        moment = datetime.fromisoformat(str(base_ts)) + timedelta(seconds=int(elapsed_s))
        return phase_by_clock(model, moment)
    return phase_by_cycle(model, elapsed_s)


def phase_for_session(model: dict[str, Any], session: str | None) -> dict[str, Any]:
    """接口层"时段"注入 → 对应阶段(不认识的值原样报错,不静默忽略)。"""
    if not session:
        return {}
    if session not in model["phase_capacity_factor"]:
        raise SystemExit(f"时段 {session!r} 不在容量模型阶段表 {PHASE_ORDER} 内")
    return _phase(model, session, "session-injected")
