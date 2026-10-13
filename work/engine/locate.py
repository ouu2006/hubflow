"""定位与地图匹配(work/engine/README.md 第三节;分工表 §8.2 的 **W4**)。

两期用**同一个函数形状**,一期只换输入:

    locate(session_id, position, heading, ts) -> {
        segment_id, offset_m, direction, route_progress, match_confidence
    }

| 项 | 一期(当前) | 二期 |
|---|---|---|
| 输入 | 孪生真值(TraCI:所在路段 / 车道 / 距路段起点多少米) | App 定位(北斗 / GNSS),进围栏后每 5–10 s 上报 |
| 算法 | 真值直读,`match_confidence = 1.0` | 隐马尔可夫地图匹配(HMM) |
| 低置信度 | 不适用 | `match_confidence < 0.6` 时不用于重新规划,提示"定位不稳定" |

⚠️ **本文件是 W0 骨架,函数边界先定、实现待 W4**(一期要为二期做的准备:用孪生真值加
   σ = 10–30 m 噪声生成假定位,提前把地图匹配模块测出来 —— TC-18)。

隐私口径(硬):`session_id` 是**匿名会话号**,不含身份;行程结束即删;不与摄像头 /
虚拟检测器数据关联;用户拒绝定位时降级为"手动选所在道路 / 只看路况",流程不中断。

用法:由 run.py 调用,不单独执行。
"""

from __future__ import annotations

from typing import Any

#: 低于此值不用于重新规划(契约第二节 location.match_confidence)【待标定】
MATCH_CONFIDENCE_MIN = 0.6

#: 位置来源(封闭取值;一期 twin,二期 app_gnss)
LOCATION_SOURCES = ("twin", "app_gnss")


def locate(
    session_id: str,
    position: dict[str, Any],
    heading: float | None,
    ts: str,
) -> dict[str, Any]:
    """返回 `{segment_id, offset_m, direction, route_progress, match_confidence}`。

    骨架,TODO(W4):一期真值直读(`match_confidence = 1.0`);二期 HMM + WGS-84 坐标转换。
    """
    raise NotImplementedError("定位匹配待 W4 实现:一期真值直读,二期 HMM(TC-18)")


def add_gnss_noise(position: dict[str, Any], sigma_m: float, seed: int) -> dict[str, Any]:
    """对孪生真值加 σ 米高斯噪声,生成假定位(一期为二期做的准备,TC-18 第②项)。

    骨架,TODO(W4):σ 取 10 / 20 / 30 m 各跑一遍,路段匹配正确率 ≥ 90%【demo 目标值】。
    """
    raise NotImplementedError("噪声假定位待 W4 实现:σ = 10/20/30 m,种子固定才可复现")


def to_wgs84(lon: float, lat: float, source_crs: str) -> tuple[float, float]:
    """坐标系互转:站点包统一存 WGS-84;高德 GCJ-02、百度 BD-09 的互转**离线内置**。

    骨架,TODO(W4):三套坐标系并存,这一步错了后面全错(位置会整体偏几十到几百米)。
    """
    raise NotImplementedError("坐标系互转待 W4 实现:WGS-84 ↔ GCJ-02 ↔ BD-09(离线内置)")
