"""预测接口(work/engine/README.md 第四节;分工表 §8.2 的 **W5**)。

一期**只做接口 + L0 保底实现**,用孪生数据跑通链路;二期上 L1 机器学习回归 → L2 时空图。

| 项 | 一期 | 二期 |
|---|---|---|
| 输出 | 每条路段未来 **15 / 30 分钟**的流量与等级,写进 `segments.pred`,`model = "L0"` | 5 / 15 / 30 / 60 分钟,`model = "L1"` / `"L2"` |
| 精度 | **不报任何精度数字**,标 `is_simulated` | 15 分钟 MAPE ≤ 15%、30 分钟 ≤ 20% |
| 喂给谁 | 演示链路 + 管理端"预测展示" | 填进时段预约表的 `background[seg][slot]` |
| 防失控 | — | 连续 3 天误差超标 → 自动退回 L0 并告警;模型版本可回滚 |

接口形状:`GET /api/traffic/predict?segment_id=&h=15`(一期 L0;二期 L1/L2,**端点形状不变**)。

> **阶梯替换纪律**:下一级模型**必须比上一级误差低 10% 以上**才替换。

⚠️ **本文件是 W0 骨架,函数边界先定、实现待 W5**。`segments.pred` 的字段形状已由
   契约第一节冻结(`{"h15": {"q_vph": …, "level": …}, "h30": {…}, "model": "L0"}`),
   实现时照抄,不另起名字。

用法:由 run.py 调用,不单独执行。
"""

from __future__ import annotations

from typing import Any

#: 一期只支持这两个视界(契约第一节 pred 字段)
HORIZONS_MIN = (15, 30)

#: 一期模型版本(只 L0;L1/L2 是二期)
MODELS = ("L0", "L1", "L2")


def predict(segment_id: str, horizon_min: int) -> dict[str, Any]:
    """返回 `{"h15": {...}, "h30": {...}, "model": "L0"}`,写进 `segments.pred`。

    骨架,TODO(W5):一期 L0 保底(可用当前值直接外推),**不报任何精度数字**,标 `is_simulated`。
    """
    raise NotImplementedError("预测待 W5 实现:一期 L0 保底,输出 h15 / h30,model = \"L0\"")


def attach_pred(segment: dict[str, Any], horizon_values: dict[str, Any]) -> dict[str, Any]:
    """把 pred 挂到一条 segment 上(契约第一节的字段形状照抄)。骨架,TODO(W5)。"""
    raise NotImplementedError("pred 挂载待 W5 实现:字段形状照契约第一节")
