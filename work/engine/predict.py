"""预测接口(work/engine/README.md 第四节;分工表 §8.2 的 **W5**;T5 实现 L0)。

一期**只做 L0(当前值保持)**:用孪生/感知快照的当前 `q_vph` 与 `level` 外推 15/30 分钟,
**不引入任何模型、不报任何精度数字(MAPE 等一概没有)**。二期才上 L1 机器学习回归 → L2 时空图。

| 项 | 一期(L0,本文件) | 二期 |
|---|---|---|
| 输出 | `h15`/`h30` 各 `{q_vph, level}`,取当前值 | 5/15/30/60 分钟,`model="L1"/"L2"` |
| 精度 | **无精度数字**,标 `is_simulated` | 15 分钟 MAPE ≤15%、30 分钟 ≤20% |
| 消费者 | 演示链路 + 管理端"预测展示"(经 `predict_cli.py` 产文件,接口层合并) | 时段预约表 `background[seg][slot]` |
| 防失控 | — | 连续 3 天误差超标 → 自动退回 L0 并告警 |

接口形状:`GET /api/traffic/predict?segment_id=&h=15`(**端点形状一期后不变**;
合并规格见 T5 报告,由 C 落笔,本文件不接 HTTP)。

> **阶梯替换纪律**:下一级模型必须比上一级误差低 10% 以上才替换。

**T5 变更记录(2026-10-19)**:
- 原 W0 骨架的 `predict(segment_id, horizon_min)` **无任何调用方**(全仓 grep 实证),
  且 L0 的"当前值"来自调用方手里的 segment 记录——本模块不持全局状态,该签名无法
  在不引入全局状态的前提下实现。现保留公开名并**清晰报错**(见其 docstring),
  真实入口改为纯函数 `l0_record()` 与 `build_snapshot()`;
- `attach_pred()` 由骨架转为可用实现(契约第一节 `segments.pred` 形状:h15/h30 + model)。

用法:`build_snapshot()` 由 `predict_cli.py` 调用;不单独执行。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: 一期只支持这两个视界(契约第一节 pred 字段)
HORIZONS_MIN = (15, 30)

#: 一期模型版本(只 L0;L1/L2 是二期)
MODELS = ("L0", "L1", "L2")

#: L0 模型标识(写进快照顶层与 segments.pred)
L0_MODEL = "L0"

#: 快照 note(T5 卡规定的固定文案)
SNAPSHOT_NOTE = "L0=当前值保持；不报精度；供接口层合并，不写 segments.json"


def l0_record(segment: dict[str, Any]) -> dict[str, Any]:
    """一条 segment 的 L0 预测记录:**当前值保持**(纯函数,不读全局状态)。

    返回 `{"h15": {"q_vph": 当前 q_vph, "level": 当前 level}, "h30": {同左}}`。
    `q_vph` / `level` 缺字段时按 `None` 透出(不编数;消费方按契约处理缺测)。
    """
    q_vph = segment.get("q_vph")
    level = segment.get("level")
    horizon_record = {"q_vph": q_vph, "level": level}
    return {"h15": dict(horizon_record), "h30": dict(horizon_record)}


def attach_pred(segment: dict[str, Any]) -> dict[str, Any]:
    """把 L0 预测挂到一条 segment 上(契约第一节 `segments.pred` 形状,含 model)。

    返回挂上 `pred` 的 segment(**新字典,不改入参**)。
    """
    out = dict(segment)
    out["pred"] = {**l0_record(segment), "model": L0_MODEL}
    return out


def build_snapshot(segments_path: str | Path) -> dict[str, Any]:
    """读 segments 快照(`segments.json` / `segments_twin.json` 形状:`segments[]` 数组),
    产出一期 L0 预测快照(T5 卡规定的文件 schema):

    ```json
    {"ts": "<沿用输入 ts>", "is_simulated": true, "model": "L0",
     "note": "L0=当前值保持；不报精度；供接口层合并，不写 segments.json",
     "segments": [{"segment_id": "SZ-001", "h15": {...}, "h30": {...}}]}
    ```

    - `ts` 沿用输入快照的 `ts`(缺则为 None,不现编);
    - `is_simulated` 沿用输入(缺省 True——一期数据全是演示/模拟);
    - segments 按 `segment_id` 排序(**两遍跑必须逐字节一致**);
    - **不写 `segments.json`**(本函数只读产出预测文件)。
    """
    path = Path(segments_path)
    if not path.is_file():
        raise FileNotFoundError(f"segments 快照不存在: {path}(不猜默认路径)")
    with path.open(encoding="utf-8") as fh:
        payload = json.load(fh)

    segments = payload.get("segments")
    if not isinstance(segments, list):
        raise ValueError(f"{path}: 缺 `segments[]` 数组(实际 {type(segments).__name__})")

    records = []
    for segment in segments:
        if not isinstance(segment, dict) or "segment_id" not in segment:
            raise ValueError(f"{path}: segments[] 元素缺 segment_id: {segment!r}")
        record = {"segment_id": str(segment["segment_id"]), **l0_record(segment)}
        records.append(record)
    records.sort(key=lambda item: item["segment_id"])

    is_simulated = payload.get("is_simulated")
    return {
        "ts": payload.get("ts"),
        "is_simulated": True if is_simulated is None else bool(is_simulated),
        "model": L0_MODEL,
        "note": SNAPSHOT_NOTE,
        "segments": records,
    }


def predict(segment_id: str, horizon_min: int) -> dict[str, Any]:
    """⚠️ **已废弃的骨架签名,现清晰报错**(T5;保留公开名只为不破坏潜在外部引用)。

    无法在不引入全局状态的前提下实现:L0 的"当前值"来自调用方手里的 segment 记录,
    而本模块刻意不持全局状态(可回放、无隐式输入)。真实入口:
      - 单条:`l0_record(segment)`;
      - 整份快照:`build_snapshot(segments_path)`(经 `predict_cli.py` 落文件)。
    """
    raise NotImplementedError(
        "predict(segment_id, horizon_min) 是 W0 骨架签名(T5 起废弃):L0 需要该 segment 的"
        "当前值记录,而本模块不持全局状态。请改用 l0_record(segment) 或 "
        "build_snapshot(segments_path)(见 predict_cli.py)。"
    )
