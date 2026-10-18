"""需求生成:读站点包的列车时刻表与需求比例,产出按时段的到达流率。

输入:stations/demand.json(T3 列车时刻表 + T4 需求比例);samples/(--no-sumo 时的样例)
输出:按时段的到达流率曲线(list,内存对象,不落盘)
口径:列车到达 → 放量;数值是**演示假设值**,不是实测值,对外标"演示数据(模拟)"。

本文件有两条路径:

1. **样例路径（保留）**：`loop.py --no-sumo` 时返回空曲线——站点包未接入，不编造一条假的；
   输出形状与改造前一致（这条路径的产物必须逐字节不变，见 README 第六节）；
2. **真孪生路径（Issue IKNAER / W1）**：读 `stations/demand.json`，把 T3 列车到达量按
   T4 司机类型比例折成**逐 60 s 时段的到达流率**（辆/小时，按 D1/D2/D3 分列），供
   `loop.py run_with_sumo` 每 60 s 一次放量。**数值全部是站点包的样例/演示假设值**，
   真实需求归 IKMHMX；产物里必须带 `demand_source` 标明来源。

## T3 / T4 怎么用（以及哪一项用不了）

| 站点包字段 | 用法 | 口径 |
|---|---|---|
| `trains[].arrive_ts / arrivals / delay_min` | 列车到达后 `DEMO_TRAIN_RELEASE_S` 秒内均匀疏散 `arrivals` 人次＝车辆数（演示假设：1 人 1 车） | 样例占位值，非 12306 实测 |
| `mix.driver_type_ratio` | D1 送客 / D2 接客 / D3 往返三类司机的车辆数比例 | 样例值，加总须为 1（否则按比例归一并在 meta 标明） |
| `od[].demand_vph` | **只取数值**作网络级背景流率（合计 vph），按三类司机比例分列 | 样例占位值 |
| `od[].from_node / to_node` | **不落地**：站点包 OD 端点是 7 节点样例网命名空间（`N-01` 形式），真网节点是 `N-001` 形式；**不猜映射**（与 factors.py 的 `SEG-###` 命名空间纪律同口径） | 路线由真网 boundary 断面 + SUMO `findRoute` 生成（见 loop.py），不由 OD 端点决定 |

`flow_at()` 的语义保持不变：取 `now_ts` 所在时段最后一个不晚于它的时段的流率（辆/小时）。

用法:由 loop.py 调用,不单独执行。
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

#: 三类司机对应的需求(与 driver.DRIVER_TYPES 对齐)
DEMAND_CLASSES = ("D1", "D2", "D3")

#: 列车到达后用于疏散的窗口（秒）——**演示假设值**（一期没有现场疏散速度可依，待标定）
DEMO_TRAIN_RELEASE_S = 300

#: 站点包 `is_simulated` 之外的来源标记（写进 run_log 的 demand_source）
DEMAND_SOURCE_STATION = (
    "stations/demand.json（样例/演示假设值：T3 列车到达量 × T4 driver_type_ratio 折成 60 s 到达流率）"
)
DEMAND_SOURCE_FALLBACK = (
    "demo_fallback：显式标 demo 的确定性车辆计划"
    "（stations/demand.json 缺失或没有有效 T3/T4 数据时启用，按固定演示流率生成，不是采集值）"
)

#: 站点包缺 T3/T4 时的演示背景流率（辆/小时，按 D1/D2/D3）——**显式演示值**，不是实测
DEMO_FALLBACK_VPH = {"D1": 600.0, "D2": 360.0, "D3": 240.0}

#: 时段长度（秒）：曲线按 60 s 分桶，与主循环快照周期一致
BUCKET_S = 60


def read_json(path: Path) -> dict[str, Any]:
    """读一个 UTF-8 JSON 文件（显式编码，换机器不乱码）。"""
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _stations_dir(cfg: Any) -> Path:
    """站点包目录：优先 cfg.stations_dir，缺省仓库内 stations/。"""
    custom = getattr(cfg, "stations_dir", None)
    return Path(custom) if custom else STATIONS


def _load_payload(cfg: Any) -> tuple[dict[str, Any] | None, Path | None, str]:
    """读站点包 demand.json；缺失/不可解析时返回 `(None, path, reason)`（走演示降级）。"""
    path = _stations_dir(cfg) / "demand.json"
    if not path.is_file():
        return None, path, f"缺站点包 {path}"
    try:
        payload = read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return None, path, f"站点包 {path} 不可解析：{exc}"
    if not isinstance(payload, dict):
        return None, path, f"站点包 {path} 顶层不是对象"
    return payload, path, ""


def _driver_ratios(payload: dict[str, Any]) -> tuple[dict[str, float], str]:
    """取 T4 司机类型比例；缺失/非法时用演示缺省并标来源。"""
    rows = ((payload.get("mix") or {}).get("driver_type_ratio")) or []
    ratios: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        driver_type = str(row.get("driver_type") or "")
        try:
            ratio = float(row.get("ratio"))
        except (TypeError, ValueError):
            continue
        if driver_type in DEMAND_CLASSES and ratio >= 0:
            ratios[driver_type] = ratio
    valid = all(cls in ratios for cls in DEMAND_CLASSES) and abs(
        sum(ratios.values()) - 1.0
    ) <= 1e-6
    if valid:
        return ratios, "stations/demand.json 的 mix.driver_type_ratio（样例值）"
    # 非法/缺失：退回演示缺省比例（D1 0.5 / D2 0.3 / D3 0.2），并标明不是站点包真值
    fallback = {"D1": 0.5, "D2": 0.3, "D3": 0.2}
    if ratios and sum(ratios.values()) > 0:
        total = sum(ratios.values())
        scaled = {cls: round(ratios.get(cls, 0.0) / total, 6) for cls in DEMAND_CLASSES}
        return scaled, "stations/demand.json 的 mix.driver_type_ratio 加总≠1，按比例归一（演示值）"
    return fallback, "demo_fallback：driver_type_ratio 缺失/非法，用演示缺省比例 D1 0.5 / D2 0.3 / D3 0.2"


def _parse_ts(text: Any) -> datetime | None:
    """ISO 时间戳 → datetime；非法/缺失返回 None（不猜时间）。"""
    try:
        return datetime.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None


def _split_counts(total: int, ratios: dict[str, float]) -> dict[str, int]:
    """把整数总辆数按比例拆成三类司机（最大余数法，整数加总严格 = total）。"""
    if total <= 0:
        return dict.fromkeys(DEMAND_CLASSES, 0)
    raw = {cls: float(total) * float(ratios.get(cls, 0.0)) for cls in DEMAND_CLASSES}
    counts = {cls: int(raw[cls]) for cls in DEMAND_CLASSES}
    remainder = total - sum(counts.values())
    order = sorted(DEMAND_CLASSES, key=lambda cls: (raw[cls] - counts[cls], cls), reverse=True)
    for index in range(max(0, remainder)):
        counts[order[index % len(order)]] += 1
    return counts


def _base_rows(cfg: Any, base_ts: str) -> list[dict[str, Any]]:
    """按 60 s 分桶建曲线骨架（每桶先放 0），时间从固定 base_ts 派生，不读系统时钟。"""
    base = _parse_ts(base_ts)
    if base is None:
        raise SystemExit(f"base_ts 非法：{base_ts!r}（仿真时间必须从固定 DEMO_BASE_TS 派生）")
    duration = max(BUCKET_S, int(getattr(cfg, "duration_s", BUCKET_S)))
    buckets = max(1, duration // BUCKET_S)
    return [
        {
            "time": (base + timedelta(seconds=index * BUCKET_S)).isoformat(),
            "bucket_index": index,
            **dict.fromkeys(DEMAND_CLASSES, 0.0),
        }
        for index in range(buckets + 1)  # +1：最后一桶之后边界也要能取到流率
    ]


def load_demand(cfg: Any, scene: Any) -> list[dict[str, Any]]:
    """装载需求曲线。

    --no-sumo:站点包未接入,返回空曲线(不是编造一条假的)。
    真孪生:读 stations/demand.json,把列车到发折成逐 60 s 时段的到达流率(辆/小时)。
    """
    if cfg.no_sumo:
        return []
    payload, path, reason = _load_payload(cfg)
    base_ts = str(getattr(cfg, "base_ts", "") or "")
    if not base_ts:
        raise SystemExit("真孪生需求曲线需要 cfg.base_ts（固定 DEMO_BASE_TS），缺省不猜时间")
    rows = _base_rows(cfg, base_ts)
    if payload is None:
        # 站点包缺失/坏了：**不返回空**（会让主循环静默不出车），走明示演示降级
        for row in rows:
            for cls in DEMAND_CLASSES:
                row[cls] = DEMO_FALLBACK_VPH[cls]
        return rows

    ratios, _ratio_source = _driver_ratios(payload)
    od_rows = [row for row in (payload.get("od") or []) if isinstance(row, dict)]
    od_total = 0.0
    for row in od_rows:
        try:
            od_total += max(0.0, float(row.get("demand_vph") or 0.0))
        except (TypeError, ValueError):
            continue
    # 背景流率：T4 的 od[].demand_vph 是样例占位值，只取数值作网络级流率（端点不落地）
    for row in rows:
        for cls in DEMAND_CLASSES:
            row[cls] = round(od_total * ratios[cls], 2)

    base = _parse_ts(base_ts)
    assert base is not None  # _base_rows 已校验
    for train in payload.get("trains") or []:
        if not isinstance(train, dict):
            continue
        arrive = _parse_ts(train.get("arrive_ts"))
        if arrive is None:
            continue
        try:
            total = int(train.get("arrivals") or 0)
            delay_s = int(float(train.get("delay_min") or 0) * 60)
        except (TypeError, ValueError):
            continue
        if total <= 0:
            continue
        start_s = (arrive - base).total_seconds() + delay_s
        counts = _split_counts(total, ratios)
        for cls in DEMAND_CLASSES:
            m = counts[cls]
            if m <= 0:
                continue
            # 均匀释放在 [start_s, start_s+DEMO_TRAIN_RELEASE_S) 内，按桶覆盖比例折成 vph
            for row in rows:
                bucket_start = float(row["bucket_index"] * BUCKET_S)
                overlap = max(
                    0.0,
                    min(bucket_start + BUCKET_S, start_s + DEMO_TRAIN_RELEASE_S)
                    - max(bucket_start, start_s),
                )
                if overlap <= 0:
                    continue
                row[cls] = round(float(row[cls]) + m * (overlap / DEMO_TRAIN_RELEASE_S) * 3600.0 / BUCKET_S, 2)
    return rows


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


def station_demand_meta(cfg: Any, base_ts: str) -> dict[str, Any]:
    """真孪生运行用的需求元数据（写进 run_log，供复核"需求从哪来、哪些没用上"）。"""
    payload, path, reason = _load_payload(cfg)
    meta: dict[str, Any] = {
        "base_ts": base_ts,
        "is_sample_or_demo": True,
        "stations_dir": str(_stations_dir(cfg)),
        "demand_source": DEMAND_SOURCE_FALLBACK if payload is None else DEMAND_SOURCE_STATION,
        "source_file": str(path) if path and path.is_file() else None,
        "release_window_s": DEMO_TRAIN_RELEASE_S,
        "bucket_s": BUCKET_S,
        "rejected": [],
        "note": (
            "需求是站点包样例/演示假设值（不是采集值、不是路侧接入数据）：列车到达量与 OD 流率均为占位值，"
            "真实需求归 IKMHMX；三类司机比例按 T4 样例值；1 人 1 车为演示假设"
        ),
    }
    if payload is None:
        meta["fallback_reason"] = reason
        meta["fallback_vph"] = dict(DEMO_FALLBACK_VPH)
        return meta

    ratios, ratio_source = _driver_ratios(payload)
    meta["driver_type_ratio"] = {cls: ratios[cls] for cls in DEMAND_CLASSES}
    meta["driver_type_ratio_source"] = ratio_source

    trains = []
    for train in payload.get("trains") or []:
        if not isinstance(train, dict):
            continue
        arrive = _parse_ts(train.get("arrive_ts"))
        if arrive is None:
            continue
        try:
            total = int(train.get("arrivals") or 0)
        except (TypeError, ValueError):
            total = 0
        trains.append(
            {
                "train_no": train.get("train_no"),
                "arrive_ts": train.get("arrive_ts"),
                "arrivals": total,
                "delay_min": train.get("delay_min"),
                "planned_vehicles_by_class": _split_counts(total, ratios) if total > 0 else dict.fromkeys(DEMAND_CLASSES, 0),
            }
        )
    meta["trains"] = trains

    od_rows = [row for row in (payload.get("od") or []) if isinstance(row, dict)]
    od_total = 0.0
    for row in od_rows:
        try:
            od_total += max(0.0, float(row.get("demand_vph") or 0.0))
        except (TypeError, ValueError):
            continue
    meta["od"] = {
        "od_ids": [row.get("od_id") for row in od_rows],
        "demand_vph_total": round(od_total, 2),
        "used_as": "网络级背景到达流率（只取数值，按三类司机比例分列）",
    }
    if od_rows:
        meta["rejected"].append(
            {
                "field": "od[].from_node / od[].to_node",
                "reason": (
                    "OD 端点是 7 节点样例网命名空间（N-01 形式），真网节点是 N-001 形式；"
                    "不猜映射（与 SEG-### 命名空间纪律同口径），路线改由真网 boundary 断面 + "
                    "SUMO findRoute 生成"
                ),
            }
        )
    return meta
