#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""接口层 traffic.py：把已落盘的快照文件端成 `/api/traffic/*`（契约 §七）。

## 定位（docs/数据契约.md §七）

**只读快照，不写快照**。本文件不跑感知 / 孪生 / 决策，也不做抖动、tick、SSE 假流这类
前端演示逻辑——它只做三件事：读文件、按契约字段归一、把「没有数据」如实说出来。

## 数据源（三层回落，优先级从高到低）

| 层 | 文件 | 用途 |
|---|---|---|
| ① 视频链路 | `work/perception/out/latest/segments_video.json` | 路段指标（source=video） |
| ② 孪生链路 | `work/twin/out/latest/segments_twin.json` | 路段指标（source=twin） |
| ②' 孪生快照 | `work/twin/out/segments.json` | ② 缺失时的契约形状兜底 |
| ③ 引擎路线·真网 | `work/engine/out/real/routes.json` | `route/recommend` / `locate`（**优先**，IKMS11 真网 SZ-###） |
| ③' 引擎路线·样例 | `work/engine/out/routes.json` | 真网产物缺失时回退（样例网 SEG-###） |
| ④ 站点包 | `stations/*.json` | 静态基线（路网 / 点位 / 阈值 / 场景 / 列车） |

路线响应的 `data_source` 与响应头 `X-Traffic-Data-Source` 标来源；两层段号命名空间不同，
不把两层请求拼在一起、不把路线 ETA 与路段快照指标混算（`segments_not_in_snapshot` 如实列出差异段）。

## 写端点

| 端点 | 语义 | 持久化 |
|---|---|---|
| `POST /api/traffic/plan/dispatch` | 下发分流方案（渠道 + 比例）→ 回执 | **JSON 文件仓**（IKMS1H）：启动加载、写后落盘、**重启不复位** |
| `POST /api/traffic/plan/ack` | 处置回写（认领人 / 动作 / 结果四选一）→ 状态流转 | 同上（回写留痕 / 审计） |
| `POST /api/traffic/alerts/reset` | 清运行态并重放 seed、写一条 reset 审计 | 同上 |
| `GET /api/traffic/alerts` | 告警四态（读持久化后的运行态） | 同上 |
| `GET /api/traffic/plan/audit` | 处置闭环审计（只读辅助端点，非契约端点） | 同上 |
| `POST /api/traffic/factors`、`/factors/reset`、`/scenario`、`/scenario/reset` | 人工置位 / 场景注入 | 进程内存（重启复位；不重算判级） |

处置闭环运行态落盘在 `work/assembly/data/dispatch.json`（**gitignored**，见
`work/assembly/data/.gitignore`）：schema 版本 + 每条告警的 `status / channels / dispatch_at /
dispatch_ratio_pct / writeback` + 追加式审计（上限 1000 条，`audit_total` 仍单调累计）。
写操作**幂等**（同告警 + 同渠道 + 同比例重复下发、同人同动作同结果重复回写 → 返回首次回执 +
`idempotent: true`，不重复记审计）；**无下发回执不可回写、终态不可再翻转**（409）。
**演示态、无真实下发通道**——渠道只是展示枚举，不得说成已通知到司机 / 情报板。

其它只读数据：`work/twin/out/vehicles.json`（车辆）、`work/twin/out/assimilation_state.json`
（同化状态）、`work/twin/site-ranges.json`（站点范围登记表）。

**文件不在就回落**：任何一层缺失 / 不可解析都只触发下一层或空壳 + `note`，**不报 500、不编数**。

## 口径红线

1. 每个响应恒带 `is_simulated: true`；未实现 / 无数据的端点如实 404 或空壳 + `note`；
2. **段号一律从数据读**：本文件不出现任何段号字面量（换站只换数据 / 配置）；
3. 上游未判级的链路（孪生指标）只按 `stations/thresholds.json` 的 `grading` 组做**形状补全**，
   不重复实现感知层判级模型；上游已带 `level` 时一律透传，不重算；
4. 响应信封用数据快照的 `ts`（不读墙钟）——同一份数据两次请求结构一致（时间戳除外）。

## 运行

```text
python work/assembly/traffic.py --port 8000     # 默认 127.0.0.1:8000
python work/assembly/traffic.py --check         # 只打印数据源解析结果，不起服务
```
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import math
import os
import re
import sys
import threading
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

import uvicorn

# Windows 控制台默认不是 UTF-8：先固定 stdout/stderr 编码，避免中文提示打印直接抛异常
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------- 路径与常量

ROOT = Path(__file__).resolve().parents[2]

PERCEPTION_VIDEO = ROOT / "work" / "perception" / "out" / "latest" / "segments_video.json"
TWIN_LATEST = ROOT / "work" / "twin" / "out" / "latest" / "segments_twin.json"
TWIN_SNAPSHOT = ROOT / "work" / "twin" / "out" / "segments.json"
TWIN_VEHICLES = ROOT / "work" / "twin" / "out" / "vehicles.json"
TWIN_ASSIMILATION = ROOT / "work" / "twin" / "out" / "assimilation_state.json"
# 引擎路线：真网产物（IKMS11，SZ-###）优先，回退样例产物（SEG-###）。两者都只读、不混算。
ENGINE_ROUTES_REAL = ROOT / "work" / "engine" / "out" / "real" / "routes.json"
ENGINE_ROUTES_SAMPLE = ROOT / "work" / "engine" / "out" / "routes.json"
#: 兼容旧名（自检 / 文档里按「引擎路线」引用的是样例产物路径，保留指向低优先级层）
ENGINE_ROUTES = ENGINE_ROUTES_SAMPLE
SITE_RANGES = ROOT / "work" / "twin" / "site-ranges.json"
STATIONS_DIR = ROOT / "stations"

LEVEL_NAMES = {1: "畅通", 2: "缓行", 3: "拥堵", 4: "严重拥堵"}
LEVEL_NAME_FALLBACK = "数据不可用"
LEVEL_ORDER = [1, 2, 3, 4]

# 口径角标 / 页签：与 docs/数据契约.md §八、work/frontend/ui-vue/src/shared/{nav,traffic}.ts 同源
DEMO_BADGE = "演示数据(模拟)· 双数据源(视频链路 + 孪生链路)"
SOURCE_ITEMS = [{"key": "video", "name": "视频链路"}, {"key": "twin", "name": "孪生链路"}]
APP_TABS = [
    {"key": "perception", "name": "感知层", "route": "/perception"},
    {"key": "decision", "name": "决策层", "route": "/decision"},
    {"key": "dashboard", "name": "监控大屏", "route": "/dashboard"},
]

#: SSE 事件名（契约约定：只新增、不改既有事件名）——与前端 shared/traffic.ts 同源
TRAFFIC_SNAPSHOT_EVENT = "traffic_snapshot"
#: SSE 心跳周期（秒）。只做「快照已刷新」提示，页面收到后重新拉快照
SSE_PERIOD_S = 2.0
#: 陈旧判据（展示口径，shared/traffic.ts 的 STALE_AFTER_S；站点包给了 data_freshness_s 时以包为准）
STALE_AFTER_S = 120.0
#: 未实现端点（写端点 / 只读快照定位不符）如实返回的统一 code
CODE_NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
CODE_NO_DATA = "NO_DATA"
CODE_SEGMENT_NOT_FOUND = "SEGMENT_NOT_FOUND"
CODE_ALERT_NOT_FOUND = "ALERT_NOT_FOUND"
CODE_ROUTE_UNAVAILABLE = "ROUTE_UNAVAILABLE"
#: 写端点参数不合法（人工置位 / 场景注入）
CODE_FACTOR_INVALID = "FACTOR_INVALID"
CODE_SCENARIO_INVALID = "SCENARIO_INVALID"

# 告警派生：接口层没有告警产物，按既有口径从 segments 快照派生（work/frontend/README.md §告警）
ALERT_LEVEL_FLOOR = 3
ALERT_STATUS_INITIAL = "待认领"
WRITEBACK_RESULTS = ("已消除", "已缓解", "未改善", "误报")
TERMINAL_ALERT_STATUS = ("已闭环", "误报")

# ---------------------------------------------------------------- 处置闭环持久化（IKMS1H）
#: 运行态 JSON 文件仓（同目录 .gitignore 只放行它自己；dispatch.json 是演示运行态，不入库）
DISPATCH_STORE_DEFAULT = ROOT / "work" / "assembly" / "data" / "dispatch.json"
DISPATCH_SCHEMA_VERSION = 1
#: 审计记录上限（超出只保留最近 N 条；audit_total 仍单调累计，便于「审计可重建」对账）
DISPATCH_AUDIT_MAX = 1000
#: 写端点统一口径：每一条下发 / 回写 / 复位响应都要写清「演示态、无真实下发通道」
DEMO_DISPATCH_NOTE = "演示态、无真实下发通道"
#: 初始 seed：接口层没有站点包预置下发剧本（mock 的 seedDispatch 在前端站点包 TS 里，
#: 搬到后端等于伪造一张回执）。需要预置演示态时可在状态文件的 seed_dispatch 里声明，
#: 再由 POST /api/traffic/alerts/reset 重放——这就是「复位即回到明确初始态」的口径。
_ALERT_RUNTIME_SEED: dict[str, dict[str, Any]] = {}
_STATE_PATH: Path = DISPATCH_STORE_DEFAULT
_DISPATCH_STORE: "DispatchStore | None" = None

# ---------------------------------------------------------------- 写端点内存态（一期）
#
# 两个口子、一条口径（与 mock 同语义，写端点只在**进程内存**里留演示态，重启复位）：
#   · **人工置位**（手册第 19 章）：只有 F07 / F08 / F11（事故 / 管制 / 大型活动），
#     `POST /api/traffic/factors` 逐路段登记；`POST /api/traffic/factors/reset` 清空。
#   · **环境上下文 / 场景注入**（F01 天气 / F02 昼夜 / F03 列车到发 / F10 时段日历）：
#     `POST /api/traffic/scenario` 只改环境状态（null = 清除、缺省 = 不改），
#     `POST /api/traffic/scenario/reset` 复位；GET /context 的 derived_factors 随它折算。
#
# ⚠️ 口径红线：接口层**不重算 level / ci**（判级唯一实现是感知层 level.py）。
# 写端点只更新 context / derived_factors / 因素状态；等级字段一律取当前快照原值透传，
# 并在响应 `note` / `level_recomputed: false` 里写明「判级由感知层统一重算、接口层不重算」。

#: 人工置位口子（手册 §:2222：只有这三类有人工置位权）
MANUAL_FACTOR_IDS = ("F07", "F08", "F11")
#: 契约 §19 的五个 target（只允许改这五样）
FACTOR_TARGETS = ("c", "v_f", "demand", "lanes", "confidence")
#: 环境侧因素编号（场景注入折算的只有这四个）
ENV_FACTOR_IDS = ("F01", "F02", "F03", "F10")
WEATHERS = ("晴", "多云", "小雨", "大雨", "大雾", "台风")
SESSION_ORDER = ("早高峰", "平峰", "晚高峰", "夜间")
#: 时段 → 需求倍率（F10，演示值【待标定】，与前端 mock 同源）
SESSION_DEMAND_MULT = {"早高峰": 1.2, "平峰": 1.0, "晚高峰": 1.15, "夜间": 0.6}
#: 天气 → 通行能力折减（F01，演示值；优先从 stations/factors.json 的 demo_multipliers 读，读不到用兜底）
WEATHER_MULTIPLIER_FALLBACK = {"晴": 1.0, "多云": 1.0, "小雨": 0.9, "大雨": 0.75, "大雾": 0.7, "台风": 0.6}
#: 场景注入时 F02 的置信度折减（演示值，与 mock 同源）
F02_CONFIDENCE_MULTIPLIER = 0.8

#: 人工置位内存态：[{segment_id, factor_id, name, target, multiplier, until, injected_at}]（重启复位）
_MANUAL_FACTORS: list[dict[str, Any]] = []
#: 场景注入内存态：None = 未注入 / 已清除（GET /context 回落「无数据源」的如实口径）
_SCENARIO_STATE: dict[str, Any] = {"weather": None, "session": None, "demand_mult": None}
#: 「请求体没带这个键」的哨兵（缺省 = 不改该项；显式 null = 清除该项）
_UNSET = object()



# ---------------------------------------------------------------- 基础工具


def _warn(message: str) -> None:
    """数据文件异常只记日志、不中断服务（回落下一层）。"""
    print(f"[traffic.py][warn] {message}", file=sys.stderr, flush=True)


def read_json(path: Path) -> dict[str, Any] | None:
    """读一个 JSON 文件；不存在 / 不可解析都返回 None（由调用方回落），不抛异常。"""
    try:
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _warn(f"读取 {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path} 失败：{exc}")
        return None
    if not isinstance(payload, dict):
        _warn(f"{path} 顶层不是对象，按缺失处理")
        return None
    return payload


def _num(value: Any) -> float | None:
    """数值透传（bool 不算数；NaN / Inf 不算数）。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _int(value: Any) -> int | None:
    number = _num(value)
    return int(number) if number is not None else None


def _round(value: float | None, digits: int = 2) -> float | None:
    return round(value, digits) if value is not None else None


def _now() -> datetime:
    return datetime.now().astimezone()


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds")


def _now_stamp() -> str:
    return _now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_iso(text: Any) -> datetime | None:
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        return datetime.fromisoformat(text.strip())
    except ValueError:
        return None


def _format_stamp(moment: datetime | None) -> str:
    return (moment or _now()).strftime("%Y-%m-%d %H:%M:%S")


def _format_clock(moment: datetime | None) -> str:
    return (moment or _now()).strftime("%H:%M:%S")


def _valid_level(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and LEVEL_NAMES.get(value) is not None


def _level_name(level: int | None, fallback: Any = None) -> str:
    if isinstance(fallback, str) and fallback:
        return fallback
    return LEVEL_NAMES.get(level or 0, LEVEL_NAME_FALLBACK)


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


# ---------------------------------------------------------------- 处置闭环持久化仓储（IKMS1H）
#
# 一期最小持久化：**JSON 文件仓**（不是 SQLite），理由：
#   · 单进程演示后端（uvicorn 单 worker），没有并发写库需求；stdlib 零依赖、文件可读可 diff；
#   · 状态量级小（几条告警 + 审计上限 1000 条），一次全量读写 < 1 ms，不需要事务 / 索引；
#   · 原子落盘 = 临时文件 + os.replace，进程崩溃不会留下半截文件；
#   · 二期换 openGauss / SQLite 时只替换本类，端点形状与审计字段不变（README §2.2 写明迁移口径）。


class DispatchStore:
    """处置闭环运行态：{alerts: {alert_id: runtime}, audit: [...], seed_dispatch, 计数}。

    读写都在同一把线程锁内：写端点既有 `async def`（事件循环线程）也有 `def`（线程池），
    必须保证「读-改-写-落盘」不交错；落盘失败返回 ok=False，调用方如实 500 + note，不静默吞。
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self.state = self._load()

    # ---------- 生命周期

    def _empty_state(self) -> dict[str, Any]:
        return {
            "schema_version": DISPATCH_SCHEMA_VERSION,
            "is_simulated": True,
            "note": DEMO_DISPATCH_NOTE + "；运行态随本文件持久化（重启不复位）",
            "updated_at": _now_iso(),
            "alerts": copy.deepcopy(_ALERT_RUNTIME_SEED),
            "seed_dispatch": copy.deepcopy(_ALERT_RUNTIME_SEED),
            "audit": [],
            "audit_seq": 0,
            "audit_total": 0,
            "reset_count": 0,
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return self._empty_state()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self._quarantine(f"读取处置运行态失败：{exc}")
            return self._empty_state()
        if not isinstance(payload, dict) or payload.get("schema_version") != DISPATCH_SCHEMA_VERSION:
            self._quarantine(
                f"处置运行态 schema_version 不是 {DISPATCH_SCHEMA_VERSION}（旧版 / 被手改坏）"
            )
            return self._empty_state()
        state = self._empty_state()
        for key in ("alerts", "seed_dispatch"):
            value = payload.get(key)
            if isinstance(value, dict):
                state[key] = {
                    str(alert_id): copy.deepcopy(runtime)
                    for alert_id, runtime in value.items()
                    if isinstance(runtime, dict)
                }
        audit = payload.get("audit")
        if isinstance(audit, list):
            state["audit"] = [record for record in audit if isinstance(record, dict)][-DISPATCH_AUDIT_MAX:]
        for key in ("audit_seq", "audit_total", "reset_count"):
            value = payload.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                state[key] = value
        if isinstance(payload.get("updated_at"), str):
            state["updated_at"] = payload["updated_at"]
        return state

    def _quarantine(self, reason: str) -> None:
        """坏文件改名留证后按初始态启动（不静默覆盖，审计可追溯）。"""
        backup = self.path.with_name(self.path.name + ".corrupt-" + _now().strftime("%Y%m%d-%H%M%S"))
        try:
            self.path.replace(backup)
            shown = backup.relative_to(ROOT) if backup.is_relative_to(ROOT) else backup.name
            _warn(f"{reason}；已改名留证 {shown}，按初始态启动")
        except OSError as exc:
            _warn(f"{reason}；且无法改名留证（{exc}），按初始态启动")

    def _commit(self, state: dict[str, Any]) -> bool:
        """先原子落盘、成功后才替换内存态（写失败时内存与磁盘都保持旧状态）。"""
        state["updated_at"] = _now_iso()
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(state, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        except OSError as exc:
            _warn(f"处置运行态落盘失败：{exc}")
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            return False
        self.state = state
        return True

    # ---------- 读

    def relative_path(self) -> str:
        try:
            return self.path.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            return self.path.name

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self.state)

    def get_alert(self, alert_id: str) -> dict[str, Any]:
        with self._lock:
            runtime = (self.state.get("alerts") or {}).get(alert_id)
            return copy.deepcopy(runtime) if isinstance(runtime, dict) else {}

    def all_alerts(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self.state.get("alerts") or {})

    def audit_total(self) -> int:
        with self._lock:
            return int(self.state.get("audit_total") or 0)

    def reset_count(self) -> int:
        with self._lock:
            return int(self.state.get("reset_count") or 0)

    def audit_records(self, limit: int = 50, alert_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            records = [record for record in (self.state.get("audit") or []) if isinstance(record, dict)]
        if alert_id:
            records = [record for record in records if record.get("alert_id") == alert_id]
        limit = max(1, min(500, int(limit)))
        return copy.deepcopy(records[-limit:])

    # ---------- 写（全部走「拷贝 → 改 → 落盘 → 替换」）

    def _append_audit(self, state: dict[str, Any], record: dict[str, Any]) -> int:
        seq = int(state.get("audit_seq") or 0) + 1
        state["audit_seq"] = seq
        state["audit_total"] = int(state.get("audit_total") or 0) + 1
        audit = state.setdefault("audit", [])
        audit.append({"seq": seq, "at": _now_stamp(), **record})
        if len(audit) > DISPATCH_AUDIT_MAX:
            state["audit"] = audit[-DISPATCH_AUDIT_MAX:]
        return seq

    def record_dispatch(self, alert_id: str, segment_id: str | None, channel: str,
                        ratio_pct: float, operator: str | None) -> dict[str, Any]:
        with self._lock:
            state = copy.deepcopy(self.state)
            alerts = state.setdefault("alerts", {})
            runtime = alerts.get(alert_id) if isinstance(alerts.get(alert_id), dict) else {}
            # 幂等窗口 = 下发后、回写前：同告警 + 同渠道 + 同比例重复下发 → 回首次回执，不重复审计
            same_dispatch = (
                runtime.get("status") == "处置中"
                and runtime.get("channels") == [channel]
                and _num(runtime.get("dispatch_ratio_pct")) == ratio_pct
                and bool(runtime.get("dispatch_at"))
                and not runtime.get("writeback")
            )
            if same_dispatch:
                return {
                    "ok": True,
                    "idempotent": True,
                    "runtime": copy.deepcopy(runtime),
                    "audit_seq": runtime.get("dispatch_audit_seq"),
                }
            seq = self._append_audit(state, {
                "action": "dispatch",
                "alert_id": alert_id,
                "segment_id": segment_id,
                "channel": channel,
                "ratio_pct": ratio_pct,
                "operator": operator,
                "result": None,
                "status_after": "处置中",
            })
            runtime.update({
                "alert_id": alert_id,
                "segment_id": segment_id,
                "status": "处置中",
                "channels": [channel],
                "dispatch_at": _now_stamp(),
                "dispatch_ratio_pct": ratio_pct,
                "dispatch_operator": operator,
                "dispatch_audit_seq": seq,
            })
            alerts[alert_id] = runtime
            if not self._commit(state):
                return {"ok": False, "error": "落盘失败"}
            return {"ok": True, "idempotent": False, "runtime": copy.deepcopy(runtime), "audit_seq": seq}

    def record_ack(self, alert_id: str, segment_id: str | None, operator: str, action: str,
                   result: str, new_status: str) -> dict[str, Any]:
        with self._lock:
            state = copy.deepcopy(self.state)
            alerts = state.setdefault("alerts", {})
            runtime = alerts.get(alert_id) if isinstance(alerts.get(alert_id), dict) else {}
            writeback = runtime.get("writeback") if isinstance(runtime.get("writeback"), dict) else {}
            # 幂等回放：回写内容（人 / 动作 / 结果）完全一致 → 回既有回执，不重复审计
            if (
                writeback
                and writeback.get("operator") == operator
                and writeback.get("action") == action
                and writeback.get("result") == result
                and bool(writeback.get("at"))
            ):
                return {
                    "ok": True,
                    "idempotent": True,
                    "runtime": copy.deepcopy(runtime),
                    "audit_seq": writeback.get("audit_seq"),
                }
            seq = self._append_audit(state, {
                "action": "ack",
                "alert_id": alert_id,
                "segment_id": segment_id,
                "channel": None,
                "ratio_pct": None,
                "operator": operator,
                "operator_action": action,
                "result": result,
                "status_after": new_status,
            })
            runtime.update({
                "alert_id": alert_id,
                "segment_id": segment_id,
                "status": new_status,
                "writeback": {
                    "operator": operator,
                    "action": action,
                    "result": result,
                    "at": _now_stamp(),
                    "audit_seq": seq,
                },
            })
            alerts[alert_id] = runtime
            if not self._commit(state):
                return {"ok": False, "error": "落盘失败"}
            return {"ok": True, "idempotent": False, "runtime": copy.deepcopy(runtime), "audit_seq": seq}

    def reset(self) -> dict[str, Any]:
        with self._lock:
            state = copy.deepcopy(self.state)
            alerts = state.get("alerts") if isinstance(state.get("alerts"), dict) else {}
            cleared = len(alerts)
            seed = state.get("seed_dispatch") if isinstance(state.get("seed_dispatch"), dict) else {}
            state["alerts"] = copy.deepcopy(seed)
            seq = self._append_audit(state, {
                "action": "reset",
                "alert_id": None,
                "segment_id": None,
                "channel": None,
                "ratio_pct": None,
                "operator": None,
                "result": None,
                "status_after": "initial",
                "cleared_alerts": cleared,
                "seed_alerts": len(seed),
            })
            state["reset_count"] = int(state.get("reset_count") or 0) + 1
            if not self._commit(state):
                return {"ok": False, "error": "落盘失败"}
            return {
                "ok": True,
                "cleared_alerts": cleared,
                "seed_alerts": len(seed),
                "reset_count": state["reset_count"],
                "audit_seq": seq,
            }


def configure_dispatch_store(path: Path | str) -> None:
    """切换运行态文件路径（CLI / 自检用；默认 work/assembly/data/dispatch.json）。"""
    global _STATE_PATH, _DISPATCH_STORE
    candidate = Path(path)
    _STATE_PATH = candidate if candidate.is_absolute() else (ROOT / candidate)
    _DISPATCH_STORE = None


def get_dispatch_store() -> DispatchStore:
    """懒加载单例：第一次读写时加载状态文件（main / --check 会显式预热，等于「启动时加载」）。"""
    global _DISPATCH_STORE
    if _DISPATCH_STORE is None:
        _DISPATCH_STORE = DispatchStore(_STATE_PATH)
    return _DISPATCH_STORE


# ---------------------------------------------------------------- 站点包（stations/*.json）


def station_json(name: str) -> dict[str, Any] | None:
    """读站点包里的一个文件（文件名固定，换站只换文件内容）。"""
    return read_json(STATIONS_DIR / name)


def _grading() -> dict[str, Any]:
    payload = station_json("thresholds.json") or {}
    grading = payload.get("grading")
    return grading if isinstance(grading, dict) else {}


def _network_edges_by_segment() -> dict[str, dict[str, Any]]:
    """站点包 network.json：edges[].section 即 segment_id（契约 §六）。"""
    network = station_json("network.json") or {}
    out: dict[str, dict[str, Any]] = {}
    for edge in network.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        segment_id = edge.get("section")
        if isinstance(segment_id, str) and segment_id and segment_id not in out:
            out[segment_id] = edge
    return out


def _segment_display_names() -> dict[str, str]:
    """路段展示名。站点包没给 edges[].name（network.attributes.missing_fields 已登记），
    用「起点节点→终点节点」拼一个可追溯的展示名，不编路名。"""
    network = station_json("network.json") or {}
    names: dict[str, str] = {}
    for edge in network.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        segment_id = edge.get("section")
        if not isinstance(segment_id, str) or not segment_id or segment_id in names:
            continue
        name = edge.get("name")
        if not isinstance(name, str) or not name:
            start, end = edge.get("from"), edge.get("to")
            name = f"{start}→{end}" if start and end else segment_id
        names[segment_id] = name
    return names


def _segment_name(segment_id: str, names: dict[str, str] | None = None) -> str:
    return (names or _segment_display_names()).get(segment_id, segment_id)


def _site_ranges() -> dict[str, Any]:
    return read_json(SITE_RANGES) or {}


def _site_meta() -> dict[str, Any]:
    """当前站点登记（work/twin/site-ranges.json 的 default_site）；缺文件返回空对象。"""
    registry = _site_ranges()
    sites = [s for s in (registry.get("sites") or []) if isinstance(s, dict)]
    default_id = registry.get("default_site")
    if isinstance(default_id, str) and default_id:
        matched = [s for s in sites if s.get("site_id") == default_id]
        if matched:
            return matched[0]
    return sites[0] if sites else {}


def _site_landmarks() -> list[dict[str, Any]]:
    site = _site_meta()
    anchor = site.get("anchor_lonlat")
    if not isinstance(anchor, list) or len(anchor) != 2:
        return []
    lon, lat = _num(anchor[0]), _num(anchor[1])
    if lon is None or lat is None:
        return []
    return [{
        "id": site.get("site_id"),
        "name": site.get("site_name"),
        "lon": lon,
        "lat": lat,
        # 站点块副标是站点包声明项；当前站点包没给，保留键、值为 null（不编文案）
        "sub": None,
    }]


def _assimilation_gate() -> dict[str, Any]:
    """同化门控阈值来自站点包 scenarios.json 的场景开关（契约 §6.2）。"""
    scenarios = station_json("scenarios.json") or {}
    rows = [s for s in (scenarios.get("scenarios") or []) if isinstance(s, dict)]
    if not rows:
        return {"confidence_min": None, "data_age_max_s": None}
    gate = ((rows[0].get("assimilation") or {}).get("gate")) or {}
    return {
        "confidence_min": _num(gate.get("confidence_min")),
        "data_age_max_s": _num(gate.get("data_age_max_s")),
    }


def _latest_data_ts() -> str:
    """数据快照时间（取在场运行产物的最大 ts；都没有才用当前时间，保证可复现）。"""
    stamps: list[str] = []
    for path in (PERCEPTION_VIDEO, TWIN_LATEST, TWIN_SNAPSHOT):
        payload = read_json(path)
        ts = payload.get("ts") if payload else None
        if isinstance(ts, str) and ts:
            stamps.append(ts)
    return max(stamps) if stamps else _now_iso()


# ---------------------------------------------------------------- 判级形状补全


def _grading_by_segment(grading: dict[str, Any], segment_id: str | None) -> dict[str, float | None]:
    """按 segment_id 取站点包参数，取不到用 defaults（手册 6.6：判级代码不写死阈值）。"""
    defaults = grading.get("defaults") or {}
    out: dict[str, float | None] = {
        "v_f_kmh": _num(defaults.get("v_f_kmh")),
        "c_vph": _num(defaults.get("c_vph")),
    }
    for row in grading.get("by_segment") or []:
        if isinstance(row, dict) and row.get("segment_id") == segment_id:
            if _num(row.get("v_f_kmh")) is not None:
                out["v_f_kmh"] = _num(row.get("v_f_kmh"))
            if _num(row.get("c_vph")) is not None:
                out["c_vph"] = _num(row.get("c_vph"))
            break
    return out


def _factors_applied(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _c_vph_with_factors(c_base: float | None, factors: list[dict[str, Any]], grading: dict[str, Any]) -> float | None:
    """契约 §1.1 合成规则：c 与 lanes 的倍率相乘，合成后不低于 factor_floor（待标定）。"""
    if c_base is None:
        return None
    coefficient = 1.0
    for factor in factors:
        if factor.get("target") not in ("c", "lanes"):
            continue
        multiplier = _num(factor.get("multiplier"))
        if multiplier is not None:
            coefficient *= multiplier
    if factors:
        floor = _num(grading.get("factor_floor"))
        if floor is not None:
            coefficient = max(floor, coefficient)
    return round(c_base * coefficient, 1)


# ---------------------------------------------------------------- 路段快照（三层回落）


_NUMERIC_SEGMENT_FIELDS = (
    "q_vph", "v_kmh", "v_f_kmh", "k_vpk", "L_q_m", "L_seg_m", "T_d_min",
    "x", "c_base_vph", "c_vph", "ci", "confidence", "data_age_s",
)


def _normalize_segment(raw: dict[str, Any], grading: dict[str, Any],
                        network_by_segment: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """把上游记录归一成契约 §一 的 SegmentRecord 形状（附加字段不并入契约响应）。"""
    segment_id = raw.get("segment_id")
    source = raw.get("source")
    if source not in ("video", "twin"):
        source = None
    record: dict[str, Any] = {"segment_id": segment_id, "source": source}
    for field in _NUMERIC_SEGMENT_FIELDS:
        if field in raw:
            record[field] = _num(raw.get(field))

    factors = _factors_applied(raw.get("factors_applied"))
    record["factors_applied"] = factors

    # 静态基线补全：c_base_vph 来自 stations/network.json（契约 §1.1）；v_f / 默认容量来自 grading 组
    edge = network_by_segment.get(str(segment_id)) if isinstance(segment_id, str) else None
    by_segment = _grading_by_segment(grading, str(segment_id) if isinstance(segment_id, str) else None)
    if record.get("L_seg_m") is None:
        record["L_seg_m"] = _num((edge or {}).get("length_m"))
    if record.get("v_f_kmh") is None:
        record["v_f_kmh"] = by_segment["v_f_kmh"]
    if record.get("c_base_vph") is None:
        record["c_base_vph"] = _num((edge or {}).get("capacity_vph")) if edge else by_segment["c_vph"]
    # 因素修正后的容量：上游给了就透传，没给才按 factors_applied 合成（契约 §1.1）
    if record.get("c_vph") is None:
        record["c_vph"] = _c_vph_with_factors(record.get("c_base_vph"), factors, grading)
    if record.get("x") is None:
        q_vph, c_vph = _num(record.get("q_vph")), _num(record.get("c_vph"))
        record["x"] = round(q_vph / c_vph, 3) if q_vph is not None and c_vph else None

    # 上游已判级 → 透传；**未判级 → 不做任何判级重算**（判级唯一实现是感知层 level.py）。
    # 接口层只做形状层：level=0 + 「数据不可用」，绝不把"没判级"兜底成"畅通"（TC-11 同口径）。
    if _valid_level(raw.get("level")):
        record["level"] = raw["level"]
        record["level_name"] = _level_name(raw["level"], raw.get("level_name"))
        triggered = raw.get("triggered_by")
        record["triggered_by"] = [str(item) for item in triggered] if isinstance(triggered, list) else []
    else:
        record["level"] = 0
        record["level_name"] = LEVEL_NAME_FALLBACK
        record["triggered_by"] = []
        record["level_source"] = "upstream_missing"

    record["is_simulated"] = True
    # pred 是可选字段：上游没有就不写这个键（契约 §1.1）
    if isinstance(raw.get("pred"), dict):
        record["pred"] = raw["pred"]
    return record


def _raw_segment_layers() -> list[tuple[str, str, dict[str, Any]]]:
    """按优先级返回在场的链路产物：(数据源标签, 链路, payload)。"""
    layers: list[tuple[str, str, dict[str, Any]]] = []
    video = read_json(PERCEPTION_VIDEO)
    if video and isinstance(video.get("segments"), list):
        layers.append(("perception.video", "video", video))
    twin_latest = read_json(TWIN_LATEST)
    if twin_latest and isinstance(twin_latest.get("segments"), list):
        layers.append(("twin.latest", "twin", twin_latest))
    else:
        twin_snapshot = read_json(TWIN_SNAPSHOT)
        if twin_snapshot and isinstance(twin_snapshot.get("segments"), list):
            layers.append(("twin.snapshot", "twin", twin_snapshot))
    return layers


def _station_baseline_segments() -> tuple[list[dict[str, Any]], str]:
    """运行产物全缺时的站点包静态基线：只有配置量，没有运行指标（不编数）。"""
    network = station_json("network.json") or {}
    segments: list[dict[str, Any]] = []
    for edge in network.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        segment_id = edge.get("section")
        if not isinstance(segment_id, str) or not segment_id:
            continue
        capacity = _num(edge.get("capacity_vph"))
        segments.append({
            "segment_id": segment_id,
            # 站点包静态基线不是任何一条链路的运行产物；按站点包基线口径标 twin（并在 note 说明）
            "source": "twin",
            "q_vph": None,
            "v_kmh": None,
            "v_f_kmh": _num(edge.get("speed_limit")),
            "k_vpk": None,
            "L_q_m": None,
            "L_seg_m": _num(edge.get("length_m")),
            "T_d_min": None,
            "x": None,
            "c_base_vph": capacity,
            "c_vph": capacity,
            "factors_applied": [],
            "ci": None,
            "level": 0,
            "level_name": LEVEL_NAME_FALLBACK,
            "triggered_by": [],
            "confidence": None,
            "data_age_s": None,
            "is_simulated": True,
        })
    note = (
        "运行产物缺失（work/perception/out、work/twin/out、work/engine/out 均不可读）："
        "已回落 stations/*.json 静态基线。基线只含站点包配置（v_f / 通行能力 / 路段长度），"
        "没有运行指标，故 q_vph / v_kmh / level 等字段为 null 或 0（契约：缺失按 0 处理并降级），"
        "不做任何编造。"
    )
    return segments, note


def build_segments_snapshot() -> dict[str, Any]:
    """当前路段快照。返回 payload / 数据源标签 / 降级说明 / 两条链路各自的记录。"""
    grading = _grading()
    network_by_segment = _network_edges_by_segment()
    channels: dict[str, dict[str, dict[str, Any]]] = {"video": {}, "twin": {}}
    merged: dict[str, dict[str, Any]] = {}
    labels: list[str] = []
    stamps: list[str] = []
    windows: list[float] = []

    for label, _chain, payload in _raw_segment_layers():
        labels.append(label)
        ts = payload.get("ts")
        if isinstance(ts, str) and ts:
            stamps.append(ts)
        window = _num(payload.get("window_sec"))
        if window is not None:
            windows.append(window)
        for raw in payload.get("segments") or []:
            if not isinstance(raw, dict):
                continue
            segment_id = raw.get("segment_id")
            if not isinstance(segment_id, str) or not segment_id:
                continue
            record = _normalize_segment(raw, grading, network_by_segment)
            record_source = record.get("source")
            if record_source in channels:
                channels[record_source].setdefault(segment_id, record)
            if segment_id not in merged:
                merged[segment_id] = record

    if merged:
        payload = {
            "ts": max(stamps) if stamps else _now_iso(),
            "window_sec": max(windows) if windows else 0,
            "is_simulated": True,
            "segments": list(merged.values()),
        }
        return _attach_runtime_state({
            "payload": payload,
            "source": "+".join(labels),
            "note": None,
            "channels": channels,
            "records": merged,
        })

    segments, note = _station_baseline_segments()
    records = {segment["segment_id"]: segment for segment in segments}
    payload = {
        "ts": _now_iso(),
        "window_sec": 0,
        "is_simulated": True,
        "segments": segments,
        "note": note,
    }
    return _attach_runtime_state({
        "payload": payload,
        "source": "stations.baseline",
        "note": note,
        "channels": channels,
        "records": records,
    })


def _is_stale(record: dict[str, Any]) -> bool:
    age = _num(record.get("data_age_s"))
    if age is None:
        return True
    limit = _num(_grading().get("data_freshness_s")) or STALE_AFTER_S
    return age > limit


def _usable_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if not _is_stale(record)]


# ---------------------------------------------------------------- 各端点数据装配


def build_meta(snapshot: dict[str, Any]) -> dict[str, Any]:
    site = _site_meta()
    segments = snapshot["payload"]["segments"]
    range_m = _num(site.get("range_m"))
    range_source = site.get("range_source")
    subtitle_parts: list[str] = []
    if range_m is not None:
        subtitle_parts.append(f"站区 {range_m:g} m" + (f"（{range_source}）" if isinstance(range_source, str) else ""))
    subtitle_parts.append(f"{len(segments)} 段")
    subtitle_parts.append(f"数据源 {snapshot['source']}")
    payload: dict[str, Any] = {
        "ts": snapshot["payload"]["ts"],
        "is_simulated": True,
        "station": {
            "station_id": site.get("site_id") or "demo-station",
            "name": site.get("site_name") or "演示站点",
            "subtitle": " · ".join(subtitle_parts),
            "range_m": range_m,
            "range_source": range_source if isinstance(range_source, str) else None,
            "segment_count": len(segments),
        },
        "sources": SOURCE_ITEMS,
        "demo_badge": DEMO_BADGE,
        "tabs": APP_TABS,
    }
    if snapshot["note"]:
        payload["note"] = snapshot["note"]
    # 数据源角标（三页共用）：segments 来自哪条链路 / 路线来自真网还是样例 / 写端点内存态是否在生效
    routes_layers = _routes_layers()
    payload["data_sources"] = {
        "segments": snapshot["source"],
        "routes": f"engine.routes.{routes_layers[0][0]}" if routes_layers else None,
        "routes_note": (
            ROUTE_LAYER_NOTES.get(routes_layers[0][0]) if routes_layers
            else "引擎路线产物缺失（route/recommend 与 locate 会如实 404）"
        ),
        "routes_fallback_layers": [f"engine.routes.{key}" for key, _payload in routes_layers],
        "write_endpoints_memory_state": True,
        "scenario_injected": _scenario_injected(),
        "manual_factors": len(_MANUAL_FACTORS),
    }
    return payload


def build_segment_detail(segment_id: str) -> dict[str, Any] | None:
    return build_segments_snapshot()["records"].get(segment_id)


def build_segment_sources(segment_id: str) -> dict[str, Any] | None:
    snapshot = build_segments_snapshot()
    channels = snapshot["channels"]
    video = channels["video"].get(segment_id)
    twin = channels["twin"].get(segment_id)
    if video is None and twin is None:
        if segment_id not in snapshot["records"]:
            return None
        # 站点包基线里的段：两条链路都没有产出，如实给空槽
        video = twin = None
    rows: list[tuple[str, str, str, str]] = [
        ("x", "饱和度 x", "", "x"),
        ("v_kmh", "车速 km/h", "km/h", "v_kmh"),
        ("L_q_m", "排队长度 m", "m", "L_q_m"),
        ("T_d_min", "排队消散 min", "min", "T_d_min"),
        ("ci", "拥挤指数 CI", "", "ci"),
    ]
    deltas: list[dict[str, Any]] = []
    for key, label, unit, field in rows:
        video_value = _num(video.get(field)) if video else None
        twin_value = _num(twin.get(field)) if twin else None
        deltas.append({
            "key": key,
            "label": label,
            "unit": unit,
            "video": video_value,
            "twin": twin_value,
            "delta": round(video_value - twin_value, 2)
            if video_value is not None and twin_value is not None else None,
        })
    return {
        "segment_id": segment_id,
        "ts": snapshot["payload"]["ts"],
        "is_simulated": True,
        "slots": [
            {"source": "video", "record": video, "available": video is not None},
            {"source": "twin", "record": twin, "available": twin is not None},
        ],
        "deltas": deltas,
    }


def _vehicle_records() -> list[dict[str, Any]]:
    payload = read_json(TWIN_VEHICLES)
    if not payload or not isinstance(payload.get("vehicles"), list):
        return []
    valid_states = {"行驶", "排队", "落客服务", "候客", "违停", "已离开"}
    records: list[dict[str, Any]] = []
    for item in payload["vehicles"]:
        if not isinstance(item, dict):
            continue
        state = item.get("state")
        if state not in valid_states:
            continue  # state 取值集合是封闭的（契约 §四），形状不对的整条丢掉
        offset = _num(item.get("offset_m"))
        lon, lat = _num(item.get("lon")), _num(item.get("lat"))
        records.append({
            "vehicle_id": item.get("vehicle_id"),
            "driver_type": item.get("driver_type"),
            "segment_id": item.get("segment_id"),
            "offset_m": int(offset) if offset is not None else None,
            "lon": lon,
            "lat": lat,
            "state": state,
            "guided": item.get("guided") is True,
            "is_demo_bound": item.get("is_demo_bound") is True,
        })
    return records


def build_vehicles() -> dict[str, Any]:
    payload = read_json(TWIN_VEHICLES)
    vehicles = _vehicle_records()
    ts = payload.get("ts") if payload and isinstance(payload.get("ts"), str) else None
    result: dict[str, Any] = {
        "ts": ts or _latest_data_ts(),
        "is_simulated": True,
        "vehicles": vehicles,
    }
    if not vehicles:
        result["note"] = (
            "孪生车辆产物缺失或为空（work/twin/out/vehicles.json，契约 §四）：接口层如实返回空列表，"
            "不用合成车冒充孪生真值；该端点二期下线。"
        )
    return result


def build_overview(snapshot: dict[str, Any]) -> dict[str, Any]:
    segments = snapshot["payload"]["segments"]
    usable = _usable_records(segments)

    q_sum = 0.0
    weighted_speed = 0.0
    for record in usable:
        q_vph = _num(record.get("q_vph"))
        v_kmh = _num(record.get("v_kmh"))
        if q_vph is None or v_kmh is None:
            continue  # 缺车速不当 0 参与平均（0 是编数），排除该段
        q_sum += q_vph
        weighted_speed += v_kmh * q_vph
    avg_speed = weighted_speed / q_sum if q_sum > 0 else 0.0

    names = _segment_display_names()
    ranked = sorted(
        segments,
        key=lambda r: (int(r.get("level") or 0) if isinstance(r.get("level"), int) else 0,
                       _num(r.get("x")) or 0.0),
        reverse=True,
    )
    worst = None
    if ranked and (isinstance(ranked[0].get("level"), int) and ranked[0].get("level") in LEVEL_NAMES):
        top = ranked[0]
        worst = {
            "segment_id": top.get("segment_id"),
            "name": _segment_name(str(top.get("segment_id")), names),
            "level": top.get("level"),
            "x": _num(top.get("x")) or 0.0,
        }

    vehicles = _vehicle_records()
    inbound = sum(1 for vehicle in vehicles if vehicle.get("state") != "已离开")
    guided = sum(1 for vehicle in vehicles if vehicle.get("guided") is True)
    vehicles_available = bool(read_json(TWIN_VEHICLES))

    level_distribution = [
        {
            "level": level,
            "name": LEVEL_NAMES[level],
            "count": sum(1 for record in usable if record.get("level") == level),
        }
        for level in LEVEL_ORDER
    ]
    unavailable_count = sum(1 for record in segments if _is_stale(record) or not _valid_level(record.get("level")))
    level_distribution.append({"level": 0, "name": LEVEL_NAME_FALLBACK, "count": unavailable_count})

    # 无可用运行指标 → avg_speed/delta 给 null（不是 0.0：0 会被读成"实测均速 0"）
    has_speed = q_sum > 0
    factor_ids = {
        str(f.get("factor_id"))
        for record in segments
        for f in (record.get("factors_applied") or [])
        if isinstance(f, dict) and f.get("factor_id")
    }
    payload: dict[str, Any] = {
        "ts": snapshot["payload"]["ts"],
        "is_simulated": True,
        "window_sec": snapshot["payload"]["window_sec"],
        "avg_speed_kmh": round(avg_speed, 1) if has_speed else None,
        # 接口层无状态、没有上一版快照：环比一律 null（不拿 0 冒充"持平"）
        "avg_speed_delta_kmh": None,
        "worst_segment": worst,
        "vehicles_inbound": inbound if vehicles_available else None,
        "vehicles_guided": guided if vehicles_available else None,
        "guided_rate": round(guided / inbound, 4) if vehicles_available and inbound > 0 else None,
        # 活跃因素 = **不同 factor_id 的个数**（不是各段 factors_applied 条数求和）
        "active_factors": len(factor_ids),
        "level_distribution": level_distribution,
        "segment_total": len(segments),
        "unavailable_count": unavailable_count,
    }
    notes = [snapshot["note"]] if snapshot["note"] else []
    if not has_speed:
        notes.append("无可用运行指标：avg_speed_kmh / avg_speed_delta_kmh 为 null（不是实测 0）")
    if notes:
        payload["note"] = "；".join(notes)
    return payload


def build_network() -> dict[str, Any]:
    network = station_json("network.json") or {}
    points_payload = station_json("points.json") or {}
    names = _segment_display_names()
    edges = [edge for edge in (network.get("edges") or []) if isinstance(edge, dict)]

    lengths: dict[str, float | None] = {}
    segments: list[dict[str, Any]] = []
    for edge in edges:
        segment_id = edge.get("section")
        if not isinstance(segment_id, str) or not segment_id:
            continue
        lengths[segment_id] = _num(edge.get("length_m"))
        segments.append({
            "segment_id": segment_id,
            "name": _segment_name(segment_id, names),
            "kind": "main",
            # 站点包网络只给了节点占位坐标（无经纬度），不编几何：给空折线由页面降级
            "coords": [],
        })

    sections: list[dict[str, Any]] = []
    dropoffs: list[dict[str, Any]] = []
    zones: list[dict[str, Any]] = []
    for point in points_payload.get("points") or []:
        if not isinstance(point, dict):
            continue
        point_type = point.get("type")
        point_id = point.get("point_id")
        lon, lat = _num(point.get("lon")), _num(point.get("lat"))
        if point_type == "detector":
            segment_id, role = point.get("segment_id"), point.get("role")
            if not isinstance(segment_id, str) or role not in ("boundary", "internal"):
                continue
            length = lengths.get(segment_id)
            offset_m = _num(point.get("offset_m"))
            relative = _clamp(offset_m / length, 0.0, 1.0) if length and offset_m is not None else 0.0
            sections.append({
                "point_id": point_id,
                "segment_id": segment_id,
                "name": point.get("name") or point_id,
                "role": role,
                "offset": round(relative, 3),
            })
        elif point_type == "dropoff" and lon is not None and lat is not None:
            dropoffs.append({"id": point_id, "name": point.get("name") or point_id, "lon": lon, "lat": lat})
        elif point_type in ("waiting", "pickup") and lon is not None and lat is not None:
            zones.append({"id": point_id, "name": point.get("name") or point_id, "lon": lon, "lat": lat})

    node_count = len([node for node in (network.get("nodes") or []) if isinstance(node, dict)])
    return {
        "ts": _latest_data_ts(),
        "is_simulated": True,
        "origin": "demo",
        "note": (
            f"站点包网络（{node_count} 节点 / {len(segments)} 段）：几何为站点包占位节点坐标"
            "（network.json 未给经纬度），不含实测几何；指标为演示数据（模拟）"
        ),
        "attribution": None,
        "segments": segments,
        "sections": sections,
        "dropoffs": dropoffs,
        "zones": zones,
        "stations": _site_landmarks(),
    }


def build_thresholds() -> dict[str, Any]:
    payload = station_json("thresholds.json") or {}
    grading = payload.get("grading")
    grading = grading if isinstance(grading, dict) else {}
    ci_labels = {"x": "饱和度 x", "v": "速度比 v/v_f", "k": "密度 k", "L_q": "排队比 L_q", "T_d": "消散 T_d"}
    metric_labels = {"x": "饱和度 x", "v": "速度 v", "k": "密度 k", "L_q": "排队长度 L_q", "T_d": "排队消散 T_d"}
    units = {"x": "", "v": "km/h", "k": "辆/公里", "L_q": "m", "T_d": "min"}

    ci_weights: list[dict[str, Any]] = []
    for item in grading.get("weights") or []:
        if not isinstance(item, dict):
            continue
        indicator = str(item.get("indicator"))
        ci_weights.append({
            "key": indicator,
            "label": ci_labels.get(indicator, indicator),
            "weight": _num(item.get("w")),
        })

    rows: list[dict[str, Any]] = []
    for item in grading.get("level_bounds") or []:
        if not isinstance(item, dict):
            continue
        indicator = str(item.get("indicator"))
        bounds = [_num(b) for b in (item.get("bounds") or [])]
        bounds = [b for b in bounds if b is not None]
        if len(bounds) < 3:
            continue
        bands = [{"level": level, "max": bounds[level - 1]} for level in (1, 2, 3)]
        bands.append({"level": 4, "max": 999})
        rows.append({
            "metric": metric_labels.get(indicator, indicator),
            "unit": units.get(indicator, ""),
            "bands": bands,
        })

    changelog = [item for item in (payload.get("changelog") or []) if isinstance(item, dict)]
    return {
        "ts": _latest_data_ts(),
        "is_simulated": True,
        "ci_weights": ci_weights,
        "rows": rows,
        "changelog": changelog,
    }


def build_factors(segment_id: str | None = None) -> dict[str, Any]:
    """当前因素清单：上游快照 factors_applied + 写端点内存态（人工置位 / 场景注入折算）。

    写端点登记的因素带 `injected: true, pending_recompute: true`：只表示**已登记**、
    判级待感知层统一重算 —— 接口层不改 level / ci（口径红线）。
    """
    snapshot = build_segments_snapshot()
    factors: list[dict[str, Any]] = []
    for record in snapshot["payload"]["segments"]:
        if segment_id and record.get("segment_id") != segment_id:
            continue
        for factor in record.get("factors_applied") or []:
            if isinstance(factor, dict):
                factors.append({**factor, "segment_id": record.get("segment_id"), "source": "snapshot"})
    manual = _manual_factor_rows(segment_id)
    for factor in manual:
        factors.append({**factor, "source": "manual"})
    env = _derived_env_factors()
    if env:
        targets = (
            [segment_id] if segment_id
            else [str(record.get("segment_id")) for record in snapshot["payload"]["segments"]]
        )
        for target in targets:
            for factor in env:
                factors.append({**factor, "segment_id": target, "source": "scenario"})
    counts = {
        "snapshot": sum(1 for item in factors if item.get("source") == "snapshot"),
        "manual": len(manual),
        "scenario": len(factors) - sum(1 for item in factors if item.get("source") == "snapshot") - len(manual),
    }
    payload: dict[str, Any] = {
        "ts": snapshot["payload"]["ts"],
        "is_simulated": True,
        "factors": factors,
        "counts": counts,
        "injected": {
            "manual_factors": len(_MANUAL_FACTORS),
            "scenario": _scenario_public_state(),
        },
    }
    if counts["manual"] or counts["scenario"]:
        payload["note"] = (
            "factors 里 injected=true 的是写端点登记的演示态（接口层内存态，重启复位）："
            "source=manual 为人工置位（F07/F08/F11）、source=scenario 为场景注入折算（F01/F02/F03/F10）；"
            "pending_recompute=true 表示判级待感知层统一重算 —— 接口层不重算 level / ci。"
            "source=snapshot 的是上游快照里已生效的因素。"
        )
    return payload


def build_assimilation() -> dict[str, Any]:
    state = read_json(TWIN_ASSIMILATION)
    scenarios = station_json("scenarios.json") or {}
    points_payload = station_json("points.json") or {}
    gate = _assimilation_gate()
    detector_points: dict[str, dict[str, Any]] = {}
    for point in points_payload.get("points") or []:
        if isinstance(point, dict) and point.get("type") == "detector":
            segment_id = point.get("segment_id")
            if isinstance(segment_id, str) and segment_id and segment_id not in detector_points:
                detector_points[segment_id] = point

    records: list[dict[str, Any]] = []
    ts = state.get("ts") if state and isinstance(state.get("ts"), str) else None
    edges = [edge for edge in ((state or {}).get("edges") or []) if isinstance(edge, dict)]
    if edges:
        for edge in edges:
            point = detector_points.get(str(edge.get("segment_id"))) or {}
            gate_info = edge.get("gate") if isinstance(edge.get("gate"), dict) else {}
            reason_code = gate_info.get("reason")
            gate_reason = reason_code if reason_code in ("confidence_low", "data_age", "deviation_fuse") else None
            deviation = edge.get("deviation") if isinstance(edge.get("deviation"), dict) else {}
            last_apply = edge.get("last_apply") if isinstance(edge.get("last_apply"), dict) else {}
            records.append({
                "point_code": point.get("point_id"),
                "point_id": point.get("point_id"),
                "name": point.get("name"),
                "segment_id": edge.get("segment_id"),
                "role": edge.get("role") or point.get("role"),
                "enabled": edge.get("assimilating") is True,
                "flow_dev_pct": _num(deviation.get("q_pct")),
                "speed_dev_pct": _num(deviation.get("v_pct")),
                "confidence": _num(gate_info.get("confidence")),
                "gate_reason": gate_reason,
                "gate_detail": None,
                "reason": reason_code if isinstance(reason_code, str) else None,
                "last_apply_at": last_apply.get("at") if isinstance(last_apply.get("at"), str) else None,
            })
        note = None
    else:
        # 无同化状态快照 → 按站点包「场景开关 + 断面 role」如实拼出配置态（不是回灌结果）
        rows = [s for s in (scenarios.get("scenarios") or []) if isinstance(s, dict)]
        assimilation = (rows[0].get("assimilation") or {}) if rows else {}
        enabled_edges = {str(edge) for edge in (assimilation.get("edges") or [])}
        enabled_scenario = assimilation.get("enabled") is True
        for segment_id, point in sorted(detector_points.items()):
            role = point.get("role")
            if role not in ("boundary", "internal"):
                continue
            if role == "internal":
                enabled, reason = False, "internal_not_allowed"
            else:
                enabled = enabled_scenario and str(point.get("sumo_edge_id")) in enabled_edges
                reason = None
            records.append({
                "point_code": point.get("point_id"),
                "point_id": point.get("point_id"),
                "name": point.get("name"),
                "segment_id": segment_id,
                "role": role,
                "enabled": enabled,
                "flow_dev_pct": None,
                "speed_dev_pct": None,
                "confidence": None,
                "gate_reason": None,
                "gate_detail": None,
                "reason": reason,
                "last_apply_at": None,
            })
        note = (
            "无同化状态快照（work/twin/out/assimilation_state.json 缺失）：records 由站点包"
            "「scenarios.json 的 assimilation 开关 + points.json 的断面 role」如实拼出配置态，"
            "不是回灌结果；偏差 / 置信度留 null，不编数。"
        )

    counts = {
        "boundary": sum(1 for record in records if record.get("role") == "boundary"),
        "internal": sum(1 for record in records if record.get("role") == "internal"),
    }
    payload: dict[str, Any] = {
        "ts": ts or _latest_data_ts(),
        "is_simulated": True,
        "gate": gate,
        "counts": counts,
        "records": records,
    }
    if note:
        payload["note"] = note
    return payload


def _derive_alerts(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """告警从当前 segments 快照派生（level ≥ 3；判级取路段快照，不用告警自带记录值）。"""
    names = _segment_display_names()
    alerts: list[dict[str, Any]] = []
    for record in snapshot["payload"]["segments"]:
        level = record.get("level")
        if not _valid_level(level) or int(level) < ALERT_LEVEL_FLOOR:
            continue
        segment_id = str(record.get("segment_id"))
        alert_id = f"AL-{segment_id}"
        runtime = get_dispatch_store().get_alert(alert_id)
        alert: dict[str, Any] = {
            "alert_id": alert_id,
            "segment_id": segment_id,
            "segment_name": _segment_name(segment_id, names),
            "level": level,
            "triggered_by": list(record.get("triggered_by") or []),
            "first_seen": _format_stamp(_parse_iso(snapshot["payload"].get("ts"))),
            "status": runtime.get("status") or ALERT_STATUS_INITIAL,
            "factor_ids": [
                str(factor.get("factor_id"))
                for factor in record.get("factors_applied") or []
                if isinstance(factor, dict) and factor.get("factor_id")
            ],
        }
        for optional in ("channels", "dispatch_at", "dispatch_ratio_pct", "dispatch_operator", "writeback"):
            if runtime.get(optional) is not None:
                alert[optional] = runtime[optional]
        alerts.append(alert)
    alerts.sort(key=lambda item: (-int(item.get("level") or 0), str(item.get("segment_id"))))
    return alerts


def build_alerts(snapshot: dict[str, Any]) -> dict[str, Any]:
    alerts = _derive_alerts(snapshot)
    store = get_dispatch_store()
    note = (
        f"告警运行态持久化在 {store.relative_path()}（{DEMO_DISPATCH_NOTE}；重启不复位）；"
        "复位走 POST /api/traffic/alerts/reset（重放 seed_dispatch 并写一条 reset 审计）。"
    )
    if not alerts:
        note += (
            " 当前快照没有达到告警档（level ≥ 3）的路段：告警由 segments 快照派生，"
            "接口层不编造告警记录 / 首次观测时间。"
        )
    return {
        "ts": snapshot["payload"]["ts"],
        "is_simulated": True,
        "alerts": alerts,
        "note": note,
    }


def _find_alert(alert_id: str) -> dict[str, Any] | None:
    snapshot = build_segments_snapshot()
    for alert in _derive_alerts(snapshot):
        if alert.get("alert_id") == alert_id:
            return alert
    return None


def build_heat_matrix(window: int, bucket: int) -> dict[str, Any]:
    count = min(24, max(4, int(window)))
    bucket_sec = max(1, int(bucket))
    snapshot = build_segments_snapshot()
    base_time = _parse_iso(snapshot["payload"].get("ts")) or _now()
    labels = [
        _format_clock(base_time - timedelta(seconds=(count - 1 - index) * bucket_sec))
        for index in range(count)
    ]
    names = _segment_display_names()
    rows: list[dict[str, Any]] = []
    for record in snapshot["payload"]["segments"]:
        ci = _num(record.get("ci"))
        current = None if _is_stale(record) or ci is None else ci
        # 接口层没有时序历史：只回当前快照这一个桶，其余桶给 null（灰格），不用 0 冒充
        buckets: list[float | None] = [None] * (count - 1) + [current]
        segment_id = str(record.get("segment_id"))
        rows.append({
            "segment_id": segment_id,
            "name": _segment_name(segment_id, names),
            "buckets": buckets,
        })
    payload: dict[str, Any] = {
        "ts": snapshot["payload"]["ts"],
        "is_simulated": True,
        "bucket_sec": bucket_sec,
        "buckets": count,
        "labels": labels,
        "rows": rows,
        "note": (
            "接口层只读快照、没有时序历史：热力矩阵仅最后一个桶（当前快照）有 CI，"
            "其余桶为 null（页面按「数据不可用」灰格展示），不用 0 或波形冒充历史。"
        ),
    }
    if snapshot["note"]:
        payload["note"] = snapshot["note"] + payload["note"]
    return payload


def build_ci_history(segment_id: str, points: int) -> dict[str, Any] | None:
    del points  # 无时序历史：点数参数只做入参校验，不倒推编造序列
    snapshot = build_segments_snapshot()
    record = snapshot["records"].get(segment_id)
    if record is None:
        return None
    ci = _num(record.get("ci"))
    series: list[dict[str, Any]] = []
    if ci is not None and not _is_stale(record) and _valid_level(record.get("level")):
        series.append({
            "ts": _format_clock(_parse_iso(snapshot["payload"].get("ts"))),
            "ci": ci,
            "level": record.get("level"),
        })
    values = [point["ci"] for point in series]
    payload: dict[str, Any] = {
        "segment_id": segment_id,
        "is_simulated": True,
        "points": series,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "note": (
            "接口层没有 CI 时序历史，只回当前快照单点（点数为 1）；"
            "不按正弦 / 随机数拼造走势。"
        ),
    }
    if snapshot["note"]:
        payload["note"] = snapshot["note"] + payload["note"]
    return payload


def build_predict(segment_id: str | None, horizon: int | None) -> dict[str, Any] | str:
    """返回预测响应；`segment_id` 缺失时返回错误 code（由端点转 400）。"""
    if not segment_id:
        return "PREDICT_INVALID"
    del horizon  # 一期 L0 只有 15 / 30 分钟两档；接口层不代算预测值
    snapshot = build_segments_snapshot()
    record = snapshot["records"].get(segment_id)
    if record is None:
        return "SEGMENT_NOT_FOUND"
    payload: dict[str, Any] = {
        "segment_id": segment_id,
        "ts": snapshot["payload"]["ts"],
        "is_simulated": True,
        "model": "L0",
        "points": [],
        "note": (
            "上游 segments 快照未带 pred（一期 L0 预测产物未接入接口层）：预测点如实为空；"
            "契约 §一 的 pred 字段（h15 / h30）若上游提供，会原样出现在 /segments 元素里，"
            "接口层不代算预测数字、不报精度。"
        ),
    }
    if snapshot["note"]:
        payload["note"] = snapshot["note"] + payload["note"]
    return payload


def _session_of_clock(hour: int) -> str:
    """F10 时段口径（手册第 19 章；与前端 context 的展示口径一致）。"""
    if 6 <= hour < 9:
        return "早高峰"
    if 9 <= hour < 16:
        return "平峰"
    if 16 <= hour < 20:
        return "晚高峰"
    return "夜间"


def _next_train(clock: str) -> str | None:
    """按站点包 demand.json 的列车时刻表取下一班（取时分秒；不编车次）。"""
    demand = station_json("demand.json") or {}
    times: list[str] = []
    for train in demand.get("trains") or []:
        if not isinstance(train, dict):
            continue
        arrive = _parse_iso(train.get("arrive_ts"))
        if arrive is not None:
            times.append(arrive.strftime("%H:%M:%S"))
    if not times:
        return None
    later = sorted(time for time in times if time > clock)
    # 末班车之后没有"今天下一班"→ 如实 null；不回绕到当日首班（那会给出早于 clock 的时刻）
    return later[0] if later else None


# ---------------------------------------------------------------- 写端点内存态（人工置位 / 场景注入）
#
# 与 mock 同语义的**演示态**：只存在进程内存里，重启复位；不落库、不写快照、不重算判级。
# 写端点只做三件事：校验入参 → 更新内存态 → 把「已登记 / 待感知层重算」如实说清楚。


def _manual_factor_rows(segment_id: str | None = None) -> list[dict[str, Any]]:
    """人工置位内存态（可按路段过滤）；返回副本，调用方改不坏内存态。"""
    rows = [
        dict(factor) for factor in _MANUAL_FACTORS
        if segment_id is None or factor.get("segment_id") == segment_id
    ]
    for row in rows:
        row["injected"] = True
        row["pending_recompute"] = True
    return rows


def _manual_factors_by_segment() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for factor in _manual_factor_rows():
        out.setdefault(str(factor.get("segment_id")), []).append(factor)
    return out


def _scenario_injected() -> bool:
    return any(_SCENARIO_STATE.get(key) is not None for key in ("weather", "session", "demand_mult"))


def _scenario_public_state() -> dict[str, Any]:
    return {
        "weather": _SCENARIO_STATE.get("weather"),
        "session": _SCENARIO_STATE.get("session"),
        "demand_mult": _SCENARIO_STATE.get("demand_mult"),
        "injected": _scenario_injected(),
    }


def _factor_until() -> str:
    """写端点演示态有效期：与 mock 同口径 60 分钟（展示字段；接口层不自动清理内存态）。"""
    return (_now() + timedelta(hours=1)).isoformat(timespec="seconds")


def _weather_multiplier(weather: str) -> float:
    """F01 天气折减倍率：优先站点包 factors.json 的 demo_multipliers（换站只换数据）。"""
    factors_payload = station_json("factors.json") or {}
    for factor in factors_payload.get("factors") or []:
        if not isinstance(factor, dict) or factor.get("factor_id") != "F01":
            continue
        for demo in factor.get("demo_multipliers") or []:
            if isinstance(demo, dict) and demo.get("label") == weather:
                multiplier = _num(demo.get("multiplier"))
                if multiplier is not None:
                    return multiplier
    return WEATHER_MULTIPLIER_FALLBACK.get(weather, 1.0)


def _env_factor(factor_id: str, name: str, target: str, multiplier: float, until: str) -> dict[str, Any]:
    return {
        "factor_id": factor_id,
        "name": name,
        "target": target,
        "multiplier": round(float(multiplier), 3),
        "until": until,
        "injected": True,
        "pending_recompute": True,
    }


def _derived_env_factors(moment: datetime | None = None) -> list[dict[str, Any]]:
    """当前环境状态折算出的因素（F01 / F02 / F03 / F10，只做环境侧折算、不判级）。

    演示口径（与前端 mock 同语义，实测对齐过，别改错）：
      · 天气：F01 折减通行能力（倍率 < 1 才产生因素）；大雾额外产生 F02 置信度折减；
      · 时段：仅注入「夜间」时产生 F02 置信度折减 —— **时段本身不抬需求**；
      · 需求倍率：> 1 拆成 F03 + F10（平方根拆分，乘积 = 总倍率，避免同 target 乘两次）；
        < 1 只产生 F10。未注入（全 null）时如实返回空清单。
    """
    if not _scenario_injected():
        return []
    now = moment or _now()
    session = _SCENARIO_STATE.get("session") or _session_of_clock(now.hour)
    demand = _SCENARIO_STATE.get("demand_mult")
    until = _factor_until()
    factors: list[dict[str, Any]] = []
    weather = _SCENARIO_STATE.get("weather")
    if isinstance(weather, str):
        multiplier = _weather_multiplier(weather)
        if multiplier < 1:
            factors.append(_env_factor("F01", f"天气·{weather}", "c", multiplier, until))
        if weather == "大雾":
            factors.append(_env_factor("F02", "昼夜 / 能见度", "confidence", F02_CONFIDENCE_MULTIPLIER, until))
    if session == "夜间" and not any(item["factor_id"] == "F02" for item in factors):
        factors.append(_env_factor("F02", "昼夜 / 能见度", "confidence", F02_CONFIDENCE_MULTIPLIER, until))
    if isinstance(demand, (int, float)) and not isinstance(demand, bool):
        if demand > 1:
            total = min(1.6, float(demand))
            half = round(math.sqrt(total), 3)
            factors.append(_env_factor("F03", "列车到发·需求上浮", "demand", half, until))
            factors.append(_env_factor("F10", f"时段·{session}", "demand", round(total / half, 3), until))
        elif demand < 1:
            factors.append(_env_factor("F10", f"时段·{session}", "demand", max(0.4, float(demand)), until))
    return factors


_ENV_FACTOR_NOTE = (
    "场景注入为演示口径（模拟）：接口层只更新环境上下文与 derived_factors（F01/F02/F03/F10），"
    "不重算 level / ci —— 判级由感知层统一重算、接口层不重算；接口层内存态，重启复位。"
)


def _attach_runtime_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    """把写端点内存态挂到 segments 快照上（只加字段，不改任何上游数值 / 判级）。"""
    by_segment = _manual_factors_by_segment()
    for record in snapshot["payload"]["segments"]:
        mine = by_segment.get(str(record.get("segment_id")))
        if not mine:
            continue
        record["factors_injected"] = [dict(factor) for factor in mine]
        record["pending_recompute"] = True
        record["injected_note"] = "人工置位已登记（接口层内存态）；level / ci 未重算，由感知层统一重算。"
    if by_segment or _scenario_injected():
        snapshot["payload"]["injected_state"] = {
            "manual_factors": len(_MANUAL_FACTORS),
            "scenario": _scenario_public_state(),
        }
        note = snapshot["payload"].get("note")
        extra = "写端点内存态：人工置位 / 场景注入只改因素状态与环境上下文，接口层不重算 level / ci。"
        snapshot["payload"]["note"] = (note + "；" if isinstance(note, str) and note else "") + extra
    return snapshot


def build_context() -> dict[str, Any]:
    snapshot = build_segments_snapshot()
    moment = _parse_iso(snapshot["payload"].get("ts")) or _now()
    clock = _format_clock(moment)
    session = _SCENARIO_STATE.get("session") or _session_of_clock(moment.hour)
    calendar = "工作日" if moment.weekday() < 5 else "周末"
    factors_payload = station_json("factors.json") or {}
    active_factors = [
        factor for factor in (factors_payload.get("factors") or [])
        if isinstance(factor, dict) and factor.get("active") is True
    ]
    scenario = _scenario_public_state()
    injected = _scenario_injected()
    derived = _derived_env_factors(moment)
    weather = _SCENARIO_STATE.get("weather")
    weather_condition = weather if isinstance(weather, str) else None
    if injected:
        factor_ids = " / ".join(str(item.get("factor_id")) for item in derived) or "无环境因素"
        summary = (
            f"环境已注入（演示数据（模拟））：{weather_condition or '天气未注入'} · {session} · "
            f"折算环境因素 {factor_ids}（待感知层重算，接口层不重算判级）"
        )
        source = "接口层内存态（POST /api/traffic/scenario，重启复位）· 演示数据（模拟）"
    else:
        summary = (
            f"天气源未接入 · {session} · "
            + ("站点包无已激活因素（基准）" if not active_factors
               else f"站点包已激活因素 {len(active_factors)} 项")
        )
        source = "stations/factors.json + stations/demand.json（演示数据（模拟））"
    payload: dict[str, Any] = {
        "ts": snapshot["payload"]["ts"],
        "is_simulated": True,
        "station_id": (_site_meta().get("site_id") or "demo-station"),
        # 天气 / 气温 / 能见度没有数据源：未注入时字段留 null，不编造演示天气冒充现场；
        # 场景注入后 `condition` 只是**注入的演示值**（响应 is_simulated + 页面角标），其余观测量仍不编。
        "weather": {
            "condition": weather_condition,
            "temp_c": None,
            "humidity_pct": None,
            "visibility_km": None,
            "precip_mm": None,
            "wind": None,
        },
        "time": {
            "clock": clock,
            "session": session,
            "calendar": calendar,
            "next_train": _next_train(clock),
        },
        "derived_factors": derived,
        "injected": injected,
        "scenario": scenario,
        "station_active_factors": len(active_factors),
        "summary": summary,
        "source": source,
        "note": (
            "环境上下文的一期口径是演示数据（模拟）：接口层拿不到真实天气 / 列车实时数据，"
            "derived_factors 只反映**场景注入**折算出的 F01/F02/F03/F10（或站点包 active 项，当前全部未激活）；"
            "**接口层不重算 level / ci** —— 场景注入只更新环境上下文与因素状态，判级由感知层统一重算。"
        ),
    }
    if injected:
        payload["note"] = payload["note"] + _ENV_FACTOR_NOTE
    if snapshot["note"]:
        payload["note"] = snapshot["note"] + payload["note"]
    return payload


def build_report_compare() -> dict[str, Any]:
    return {
        "ts": _latest_data_ts(),
        "is_simulated": True,
        "rows": [],
        "note": (
            "效果对比报表未接入：接口层没有「同输入多跑对照」的报表产物，"
            "不编造总行程时间 / 排队峰值等对比数字；报表数据请以决策链路产物为准。"
        ),
    }


# ---------------------------------------------------------------- 引擎路线（route/recommend · locate）
#
# 数据源优先级（只读产物、不代算、不混算）：
#   ① `work/engine/out/real/routes.json`  —— IKMS11 真网算路产物（段号 SZ-###），优先；
#   ② `work/engine/out/routes.json`       —— 7 节点样例网产物（段号 SEG-###），①缺失时回退；
# 响应体 `data_source` + 响应头 `X-Traffic-Data-Source` 标来源；两层的段号命名空间不同，
# 绝不把两层请求 / 路线拼在一起，也不把路线 ETA 与当前路段快照的指标混算。

#: 路线数据源层（优先级从高到低）
ROUTE_LAYERS: tuple[tuple[str, Path], ...] = (
    ("real", ENGINE_ROUTES_REAL),
    ("sample", ENGINE_ROUTES_SAMPLE),
)
#: 层 → 人话来源（响应体 data_source_note）
ROUTE_LAYER_NOTES = {
    "real": "真网产物（work/engine/out/real/routes.json，IKMS11 真网算路）",
    "sample": "样例产物（work/engine/out/routes.json，7 节点样例网，非本站真网）",
}
_SEGMENT_NAMESPACE_PATTERN = re.compile(r"^([A-Za-z]+)-")


def _routes_layers() -> list[tuple[str, dict[str, Any]]]:
    """在场的引擎路线层（real 优先，sample 回退）；顶层无 requests 的按缺失处理。"""
    layers: list[tuple[str, dict[str, Any]]] = []
    for key, path in ROUTE_LAYERS:
        payload = read_json(path)
        if payload and isinstance(payload.get("requests"), list) and payload["requests"]:
            layers.append((key, payload))
    return layers


def _route_request_segment_ids(request: dict[str, Any]) -> set[str]:
    """一条引擎请求里引用到的全部路段号（location / pickup / arrival / departure / alternatives）。"""
    out: set[str] = set()
    location = request.get("location")
    if isinstance(location, dict) and isinstance(location.get("segment_id"), str):
        out.add(location["segment_id"])
    for key in ("pickup_route", "arrival_route", "departure_route"):
        route = request.get(key)
        if isinstance(route, dict):
            for segment_id in route.get("segments") or []:
                if isinstance(segment_id, str) and segment_id:
                    out.add(segment_id)
    for alternative in request.get("alternatives") or []:
        if isinstance(alternative, dict):
            for segment_id in alternative.get("segments") or []:
                if isinstance(segment_id, str) and segment_id:
                    out.add(segment_id)
    return out


def _routes_namespaces(payload: dict[str, Any]) -> list[str]:
    """产物里出现的段号命名空间前缀（如 SZ / SEG）——只从数据推导，不写死段号。"""
    prefixes: set[str] = set()
    for request in payload.get("requests") or []:
        if not isinstance(request, dict):
            continue
        for segment_id in _route_request_segment_ids(request):
            match = _SEGMENT_NAMESPACE_PATTERN.match(segment_id)
            if match:
                prefixes.add(match.group(1))
    return sorted(prefixes)


def _select_route_request(
    body: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None, dict[str, Any] | None, dict[str, Any]]:
    """按数据源优先级选一条引擎请求。

    返回 `(request, layer_key, payload, match_meta)`：
      · 给了 session_id：**逐层严格匹配**（真网优先、样例回退），绝不拿别的车的请求冒充匹配；
      · 全层都没有该 session：端出最高优先级产物的首条请求作**演示路线**，match_meta 标
        `demonstration_fallback=true`（响应体 note 会写明「非该车会话」）；
      · 没给 session_id：取最高优先级产物首条请求。
    """
    layers = _routes_layers()
    raw_session = body.get("session_id")
    requested = raw_session if isinstance(raw_session, str) and raw_session else None
    if requested is not None:
        for key, payload in layers:
            for request in payload["requests"]:
                if isinstance(request, dict) and request.get("session_id") == requested:
                    return request, key, payload, {
                        "session_matched": True,
                        "requested_session_id": requested,
                        "demonstration_fallback": False,
                    }
    if layers:
        key, payload = layers[0]
        requests = [request for request in payload["requests"] if isinstance(request, dict)]
        if requests:
            return requests[0], key, payload, {
                "session_matched": requested is None,
                "requested_session_id": requested,
                "demonstration_fallback": requested is not None,
            }
    return None, None, None, {"session_matched": False, "requested_session_id": requested,
                             "demonstration_fallback": False}


def _route_response_meta(
    layer_key: str,
    payload: dict[str, Any],
    match_meta: dict[str, Any],
) -> dict[str, Any]:
    """路线响应的来源 / 段号口径说明（附加字段，不改引擎契约字段）。"""
    snapshot = build_segments_snapshot()
    snapshot_ids = set(snapshot["records"])
    route_ids: set[str] = set()
    for request in payload.get("requests") or []:
        if isinstance(request, dict):
            route_ids |= _route_request_segment_ids(request)
    snapshotted = sorted(route_ids & snapshot_ids)
    missing = sorted(route_ids - snapshot_ids)
    namespaces = _routes_namespaces(payload)
    snapshot_namespaces = sorted({
        match.group(1)
        for segment_id in snapshot_ids
        if (match := _SEGMENT_NAMESPACE_PATTERN.match(str(segment_id)))
    })
    notes: list[str] = []
    if match_meta.get("demonstration_fallback"):
        notes.append(
            f"请求的 session_id（{match_meta.get('requested_session_id')}）不在引擎产物里："
            "端出产物首条请求作为演示路线（非该车行程），ETA / 路线字段原样透传、不代算"
        )
    if namespaces:
        notes.append("路线段号命名空间：" + " / ".join(f"{prefix}-###" for prefix in namespaces))
    if missing:
        notes.append(
            f"路线引用的 {len(missing)} 段不在当前路段快照里"
            f"（快照数据源 {snapshot['source']}，命名空间 {' / '.join(snapshot_namespaces) or '未知'}）："
            "不并入路段指标、不混算；地图只画站点包里存在的段"
        )
    return {
        "ts": payload.get("ts") if isinstance(payload.get("ts"), str) else _latest_data_ts(),
        "data_source": f"engine.routes.{layer_key}",
        "data_source_note": ROUTE_LAYER_NOTES.get(layer_key, layer_key),
        "session_matched": bool(match_meta.get("session_matched")),
        "requested_session_id": match_meta.get("requested_session_id"),
        "segment_namespaces": namespaces,
        "segments_not_in_snapshot": missing,
        "segments_in_snapshot": len(snapshotted),
        "note": ("；".join(notes) + "。") if notes else None,
    }


def _decorate_route_response(
    request: dict[str, Any],
    layer_key: str,
    payload: dict[str, Any],
    match_meta: dict[str, Any],
) -> dict[str, Any]:
    """契约请求体 + 来源/口径附加字段；note 与引擎自带 note 合并（不覆盖）。"""
    body = dict(request)
    meta = _route_response_meta(layer_key, payload, match_meta)
    note = meta.pop("note", None)
    body.update(meta)
    existing = body.get("note")
    if note:
        body["note"] = (existing + "；" if isinstance(existing, str) and existing else "") + note
    body["is_simulated"] = True
    return body


def _routes_payload() -> dict[str, Any] | None:
    """兼容旧调用：返回最高优先级（真网优先）路线产物。"""
    layers = _routes_layers()
    return layers[0][1] if layers else None



# ---------------------------------------------------------------- FastAPI 应用

app = FastAPI(
    title="hubflow 接口层 /api/traffic/*",
    description=(
        "只读快照（契约 §七）；所有响应 is_simulated=true；数据源三层回落；"
        "处置闭环（下发 / 回执 / 回写）运行态持久化在 work/assembly/data/dispatch.json（重启不复位）；"
        "人工置位 / 场景注入为进程内存态、不重算判级。"
    ),
    version="1.2",
)


def _json(payload: dict[str, Any], status: int = 200, source: str = "") -> JSONResponse:
    """统一信封：is_simulated 恒 true；数据源写进响应头，JSON 形状不被诊断字段污染。"""
    body = dict(payload)
    body.setdefault("is_simulated", True)
    headers = {"Cache-Control": "no-store"}
    if source:
        headers["X-Traffic-Data-Source"] = source
    return JSONResponse(body, status_code=status, headers=headers)


def _error(status: int, code: str, message: str, note: str | None = None,
           source: str = "") -> JSONResponse:
    payload: dict[str, Any] = {"code": code, "message": message, "is_simulated": True}
    if note:
        payload["note"] = note
    return _json(payload, status, source)


async def _read_body(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001 - 请求体不是合法 JSON → 交给调用方按参数不完整处理
        return {}
    return payload if isinstance(payload, dict) else {}


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # 照搬 mock 的纪律：未匹配路径 / 未注册方法一律 404（不许静默吞路径），并保 is_simulated 信封
    if exc.status_code in (404, 405):
        return _error(404, "NOT_FOUND", f"端点不存在或方法不匹配: {request.method} {request.url.path}")
    return _error(exc.status_code, "HTTP_ERROR", str(exc.detail))


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """参数校验失败也走统一信封（契约 §七：每一个响应都带 is_simulated）。"""
    return _error(422, "BAD_REQUEST", "参数校验失败", "请求参数不合法，未做任何计算（演示接口）")


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    traceback.print_exc()
    return _error(500, "INTERNAL_ERROR", "接口层内部错误（详见服务端日志）")


@app.get("/api/traffic/meta")
def api_meta() -> JSONResponse:
    snapshot = build_segments_snapshot()
    return _json(build_meta(snapshot), source=snapshot["source"])


@app.get("/api/traffic/overview")
def api_overview() -> JSONResponse:
    snapshot = build_segments_snapshot()
    return _json(build_overview(snapshot), source=snapshot["source"])


@app.get("/api/traffic/segments")
def api_segments() -> JSONResponse:
    snapshot = build_segments_snapshot()
    return _json(snapshot["payload"], source=snapshot["source"])


@app.get("/api/traffic/segments/{segment_id}/sources")
def api_segment_sources(segment_id: str) -> JSONResponse:
    snapshot = build_segments_snapshot()
    payload = build_segment_sources(segment_id)
    if payload is None:
        return _error(404, CODE_SEGMENT_NOT_FOUND, f"路段不存在: {segment_id}", source=snapshot["source"])
    return _json(payload, source=snapshot["source"])


@app.get("/api/traffic/segments/{segment_id}")
def api_segment_detail(segment_id: str) -> JSONResponse:
    snapshot = build_segments_snapshot()
    payload = snapshot["records"].get(segment_id)
    if payload is None:
        return _error(404, CODE_SEGMENT_NOT_FOUND, f"路段不存在: {segment_id}", source=snapshot["source"])
    return _json(payload, source=snapshot["source"])


@app.get("/api/traffic/vehicles")
def api_vehicles() -> JSONResponse:
    return _json(build_vehicles(), source="twin.vehicles")


@app.get("/api/traffic/network")
def api_network() -> JSONResponse:
    return _json(build_network(), source="stations.network")


@app.get("/api/traffic/thresholds")
def api_thresholds() -> JSONResponse:
    return _json(build_thresholds(), source="stations.thresholds")


@app.get("/api/traffic/factors")
def api_factors(segment_id: str | None = Query(default=None)) -> JSONResponse:
    snapshot = build_segments_snapshot()
    return _json(build_factors(segment_id), source=snapshot["source"])


@app.get("/api/traffic/assimilation")
def api_assimilation() -> JSONResponse:
    payload = build_assimilation()
    return _json(payload, source="twin.assimilation")


@app.get("/api/traffic/alerts")
def api_alerts() -> JSONResponse:
    snapshot = build_segments_snapshot()
    return _json(build_alerts(snapshot), source=snapshot["source"])


@app.get("/api/traffic/predict")
def api_predict(segment_id: str | None = Query(default=None),
                h: str | None = Query(default=None)) -> JSONResponse:
    horizon: int | None = None
    if h is not None:
        try:
            horizon = int(float(h))
        except ValueError:
            return _error(400, "PREDICT_INVALID", f"h 须为数值(15 / 30 / 60): {h}")
    payload = build_predict(segment_id, horizon)
    if payload == "PREDICT_INVALID":
        return _error(400, "PREDICT_INVALID", "缺少 segment_id")
    if payload == "SEGMENT_NOT_FOUND":
        return _error(404, CODE_SEGMENT_NOT_FOUND, f"路段不存在: {segment_id}")
    snapshot = build_segments_snapshot()
    return _json(payload, source=snapshot["source"])


@app.get("/api/traffic/heat-matrix")
def api_heat_matrix(window: int = Query(default=12), bucket: int = Query(default=60)) -> JSONResponse:
    snapshot = build_segments_snapshot()
    return _json(build_heat_matrix(window, bucket), source=snapshot["source"])


@app.get("/api/traffic/ci-history")
def api_ci_history(segment_id: str | None = Query(default=None),
                   points: int = Query(default=12)) -> JSONResponse:
    if not segment_id:
        return _error(400, "CI_HISTORY_INVALID", "缺少 segment_id")
    snapshot = build_segments_snapshot()
    payload = build_ci_history(segment_id, points)
    if payload is None:
        return _error(404, CODE_SEGMENT_NOT_FOUND, f"路段不存在: {segment_id}", source=snapshot["source"])
    return _json(payload, source=snapshot["source"])


@app.get("/api/traffic/context")
def api_context() -> JSONResponse:
    snapshot = build_segments_snapshot()
    return _json(build_context(), source=snapshot["source"])


@app.get("/api/traffic/report/compare")
def api_report_compare() -> JSONResponse:
    return _json(build_report_compare(), source="none")


@app.post("/api/traffic/route/recommend")
async def api_route_recommend(request: Request) -> JSONResponse:
    body = await _read_body(request)
    route_request, layer_key, payload, match_meta = _select_route_request(body)
    if route_request is None or layer_key is None or payload is None:
        return _error(
            404,
            CODE_ROUTE_UNAVAILABLE,
            "推荐路线不可用：work/engine/out/real/routes.json 与 work/engine/out/routes.json 均缺失或无 requests",
            note=(
                "接口层只端引擎产物（真网产物优先、样例产物回退），不代算推荐路线与 ETA"
                "（编造数字违反口径红线）。"
            ),
            source="engine.routes.none",
        )
    return _json(
        _decorate_route_response(route_request, layer_key, payload, match_meta),
        source=f"engine.routes.{layer_key}",
    )


@app.post("/api/traffic/locate")
async def api_locate(request: Request) -> JSONResponse:
    body = await _read_body(request)
    route_request, layer_key, payload, match_meta = _select_route_request(body)
    if route_request is None or layer_key is None or payload is None:
        return _error(
            404,
            CODE_ROUTE_UNAVAILABLE,
            "定位不可用：work/engine/out/real/routes.json 与 work/engine/out/routes.json 均缺失或无 requests",
            note="一期定位取孪生真值（引擎产物 requests[].location）；缺产物时不编造定位结果。",
            source="engine.routes.none",
        )
    location = route_request.get("location") if isinstance(route_request.get("location"), dict) else {}
    meta = _route_response_meta(layer_key, payload, match_meta)
    note = meta.pop("note", None)
    result: dict[str, Any] = {
        "segment_id": location.get("segment_id"),
        "offset_m": _num(location.get("offset_m")),
        "match_confidence": _num(location.get("match_confidence")),
        "source": location.get("source") or "twin",
        "data_source": meta["data_source"],
        "data_source_note": meta["data_source_note"],
        "session_matched": meta["session_matched"],
        "requested_session_id": meta["requested_session_id"],
        "is_simulated": True,
        "note": "一期定位取孪生真值（引擎产物的 requests[].location），接口层不做地图匹配。",
    }
    if note:
        result["note"] = result["note"] + note
    return _json(result, source=f"engine.routes.{layer_key}")



@app.post("/api/traffic/plan/dispatch")
async def api_plan_dispatch(request: Request) -> JSONResponse:
    """下发分流方案 → 回执（演示态、无真实下发通道）；回执持久化，重启不复位。"""
    body = await _read_body(request)
    alert_id = body.get("alert_id")
    channel = body.get("channel")
    ratio_pct = _num(body.get("ratio_pct"))
    if not isinstance(alert_id, str) or not alert_id or not isinstance(channel, str) or not channel \
            or ratio_pct is None:
        return _error(400, "DISPATCH_INVALID", "下发参数不完整(需 alert_id/channel/ratio_pct)",
                      note=DEMO_DISPATCH_NOTE)
    alert = _find_alert(alert_id)
    if alert is None:
        return _error(404, CODE_ALERT_NOT_FOUND, f"告警不存在: {alert_id}", note=DEMO_DISPATCH_NOTE)
    segment_id = body.get("segment_id")
    if isinstance(segment_id, str) and segment_id and segment_id != alert.get("segment_id"):
        return _error(
            400, "ALERT_SEGMENT_MISMATCH",
            f"路段不匹配: {alert_id} 属于 {alert.get('segment_id')},收到 {segment_id}",
            note=DEMO_DISPATCH_NOTE,
        )
    if ratio_pct <= 0 or ratio_pct > 100:
        return _error(400, "DISPATCH_INVALID", f"分流比例须在 (0, 100]: {ratio_pct:g}",
                      note=DEMO_DISPATCH_NOTE)
    if alert.get("status") in TERMINAL_ALERT_STATUS:
        return _error(
            409, "ALERT_TERMINAL",
            f"终态告警不可再下发: {alert_id}({alert.get('status')})",
            note="终态（已闭环 / 误报）不允许再改写；如需重新处置请先 POST /api/traffic/alerts/reset 复位演示态。"
                 + DEMO_DISPATCH_NOTE,
        )
    operator = body.get("operator") if isinstance(body.get("operator"), str) and body.get("operator") else None
    store = get_dispatch_store()
    result = store.record_dispatch(alert_id, alert.get("segment_id") or segment_id, channel, ratio_pct, operator)
    if not result.get("ok"):
        return _error(
            500, "PERSIST_FAILED",
            "处置回执落盘失败：检查 work/assembly/data/ 是否可写",
            note="本次下发未生效（内存态与磁盘均保持原状）。" + DEMO_DISPATCH_NOTE,
        )
    runtime = result["runtime"]
    idempotent = bool(result.get("idempotent"))
    receipt = {
        "alert_id": alert_id,
        # 回执字段与前端 DispatchReceipt 同形；persisted / idempotent / audit_seq / store_path 是诊断附加字段
        "channel": (runtime.get("channels") or [channel])[0],
        "ratio_pct": _num(runtime.get("dispatch_ratio_pct")),
        "receipt": f"{channel}已确认",
        "at": runtime.get("dispatch_at"),
        "is_simulated": True,
        "persisted": True,
        "idempotent": idempotent,
        "dispatch_operator": runtime.get("dispatch_operator"),
        "audit_seq": result.get("audit_seq"),
        "store_path": store.relative_path(),
        "note": (
            ("重复下发（同告警、同渠道、同比例）：按幂等返回首次回执，不重复写审计。" if idempotent
             else "回执已写入持久化运行态（重启不复位）。")
            + DEMO_DISPATCH_NOTE + "。"
        ),
    }
    return _json(receipt, source="dispatch-store")


@app.post("/api/traffic/plan/ack")
async def api_plan_ack(request: Request) -> JSONResponse:
    """处置回写（认领人 / 动作 / 结果四选一）→ 状态流转；留痕持久化，重启不复位。"""
    body = await _read_body(request)
    alert_id = body.get("alert_id")
    operator = body.get("operator")
    action = body.get("action")
    result = body.get("result")
    if not isinstance(alert_id, str) or not alert_id or not isinstance(operator, str) or not operator \
            or not isinstance(action, str) or not action or not isinstance(result, str) or not result:
        return _error(400, "ACK_INVALID", "回写参数不完整(需 alert_id/operator/action/result)",
                      note=DEMO_DISPATCH_NOTE)
    if result not in WRITEBACK_RESULTS:
        return _error(400, "ACK_INVALID",
                      f"结果须为四选一({' / '.join(WRITEBACK_RESULTS)}): {result}",
                      note=DEMO_DISPATCH_NOTE)
    alert = _find_alert(alert_id)
    if alert is None:
        return _error(404, CODE_ALERT_NOT_FOUND, f"告警不存在: {alert_id}", note=DEMO_DISPATCH_NOTE)
    segment_id = body.get("segment_id")
    if isinstance(segment_id, str) and segment_id and segment_id != alert.get("segment_id"):
        return _error(
            400, "ALERT_SEGMENT_MISMATCH",
            f"路段不匹配: {alert_id} 属于 {alert.get('segment_id')},收到 {segment_id}",
            note=DEMO_DISPATCH_NOTE,
        )
    store = get_dispatch_store()
    runtime = store.get_alert(alert_id)
    status = runtime.get("status") or alert.get("status")
    writeback = runtime.get("writeback") if isinstance(runtime.get("writeback"), dict) else {}
    duplicate = bool(
        writeback
        and writeback.get("operator") == operator
        and writeback.get("action") == action
        and writeback.get("result") == result
    )
    # TC-07 顺序硬约束：终态不可再翻转；无下发回执不可回写。幂等回放优先于终态拒绝（重复提交同一回写不算「翻转」）。
    if status in TERMINAL_ALERT_STATUS and not duplicate:
        return _error(
            409, "ALERT_TERMINAL",
            f"终态告警不可再回写: {alert_id}({status})",
            note="终态（已闭环 / 误报）不可翻转；如需重新处置请先 POST /api/traffic/alerts/reset 复位演示态。"
                 + DEMO_DISPATCH_NOTE,
        )
    if not runtime.get("dispatch_at") or not runtime.get("channels"):
        return _error(
            409, "ACK_NO_DISPATCH",
            f"告警尚未下发(无派发回执),不可回写: {alert_id}",
            note="TC-07 闭环顺序：必须先有下发回执，才能回写处置结果。" + DEMO_DISPATCH_NOTE,
        )
    if result == "误报":
        new_status = "误报"
    elif result == "未改善":
        new_status = "处置中"
    else:
        new_status = "已闭环"
    store_result = store.record_ack(
        alert_id, alert.get("segment_id") or segment_id, operator, action, result, new_status
    )
    if not store_result.get("ok"):
        return _error(
            500, "PERSIST_FAILED",
            "回写留痕落盘失败：检查 work/assembly/data/ 是否可写",
            note="本次回写未生效（内存态与磁盘均保持原状）。" + DEMO_DISPATCH_NOTE,
        )
    final_runtime = store_result["runtime"]
    final_writeback = final_runtime.get("writeback") if isinstance(final_runtime.get("writeback"), dict) else {}
    idempotent = bool(store_result.get("idempotent"))
    receipt = {
        "alert_id": alert_id,
        "status": final_runtime.get("status"),
        "result": final_writeback.get("result", result),
        "at": final_writeback.get("at"),
        "is_simulated": True,
        "persisted": True,
        "idempotent": idempotent,
        "operator": final_writeback.get("operator"),
        "operator_action": final_writeback.get("action"),
        "audit_seq": store_result.get("audit_seq"),
        "store_path": store.relative_path(),
        "note": (
            ("重复回写（同人、同动作、同结果）：按幂等返回既有回执，不重复写审计。" if idempotent
             else "回写留痕已写入持久化运行态（谁 / 何时 / 做了什么 / 结果齐全；重启不复位）。")
            + DEMO_DISPATCH_NOTE + "。"
        ),
    }
    return _json(receipt, source="dispatch-store")


@app.post("/api/traffic/alerts/reset")
def api_alerts_reset() -> JSONResponse:
    """清空处置运行态并重放 seed_dispatch，写一条 reset 审计（演示复位，可重复调用）。"""
    store = get_dispatch_store()
    result = store.reset()
    if not result.get("ok"):
        return _error(
            500, "PERSIST_FAILED",
            "复位落盘失败：检查 work/assembly/data/ 是否可写",
            note="本次复位未生效（内存态与磁盘均保持原状）。" + DEMO_DISPATCH_NOTE,
        )
    payload = {
        "reset": True,
        "is_simulated": True,
        "cleared_alerts": result["cleared_alerts"],
        "seed_alerts": result["seed_alerts"],
        "reset_count": result["reset_count"],
        "audit_seq": result["audit_seq"],
        "persisted": True,
        "store_path": store.relative_path(),
        "note": (
            "已清空处置闭环运行态并重放 seed_dispatch（接口层默认 seed 为空 → 所有派生告警回「待认领」）；"
            "本次 reset 已写入审计留痕。" + DEMO_DISPATCH_NOTE + "；"
            "持久化文件重启不复位，需要再 reset 才会清。"
        ),
    }
    return _json(payload, source="dispatch-store")


@app.get("/api/traffic/plan/audit")
def api_plan_audit(limit: int = Query(default=50),
                   alert_id: str | None = Query(default=None)) -> JSONResponse:
    """处置闭环审计（只读辅助端点，非契约端点）：每次 dispatch / ack / reset 追加一条。"""
    store = get_dispatch_store()
    records = store.audit_records(limit=limit, alert_id=alert_id)
    payload = {
        "ts": _now_iso(),
        "is_simulated": True,
        "records": records,
        "total": len(records),
        "audit_total": store.audit_total(),
        "reset_count": store.reset_count(),
        "store_path": store.relative_path(),
        "note": (
            "处置闭环审计（只读辅助端点，非契约端点）：每条记录含 alert_id / action / channel / "
            "ratio_pct / operator / result / at；" + DEMO_DISPATCH_NOTE + "。"
        ),
    }
    return _json(payload, source="dispatch-store")


@app.post("/api/traffic/factors/reset")
def api_factors_reset() -> JSONResponse:
    """清空人工置位内存态（演示复位；幂等）。"""
    cleared = len(_MANUAL_FACTORS)
    _MANUAL_FACTORS.clear()
    return _json(
        {
            "reset": True,
            "is_simulated": True,
            "cleared": cleared,
            "note": "已清空人工置位（接口层内存态，重启亦复位）；判级由感知层按重算结果更新，接口层不重算。",
        },
        source="demo-runtime.manual-factor",
    )


@app.post("/api/traffic/factors")
async def api_factors_post(request: Request) -> JSONResponse:
    """人工置位（管理端口子 F07 / F08 / F11）：只登记因素状态，不重算判级。"""
    body = await _read_body(request)
    segment_id = body.get("segment_id")
    factor_id = body.get("factor_id")
    target = body.get("target")
    multiplier = _num(body.get("multiplier"))
    if not isinstance(segment_id, str) or not segment_id or not isinstance(factor_id, str) \
            or not isinstance(target, str) or multiplier is None:
        return _error(
            400,
            CODE_FACTOR_INVALID,
            "置位参数不完整（需 segment_id / factor_id / target / multiplier）",
            note="形状对齐 mock：{segment_id, factor_id, name?, target, multiplier}；未做任何写入。",
        )
    snapshot = build_segments_snapshot()
    record = snapshot["records"].get(segment_id)
    if record is None:
        return _error(
            404,
            CODE_SEGMENT_NOT_FOUND,
            f"路段不存在: {segment_id}",
            note="接口层只接受当前路段快照里的段号；换站 / 换网后先看 GET /api/traffic/segments。",
        )
    if factor_id not in MANUAL_FACTOR_IDS:
        return _error(
            400,
            CODE_FACTOR_INVALID,
            f"人工置位口子只有 {' / '.join(MANUAL_FACTOR_IDS)}（事故 / 管制 / 大型活动）: {factor_id}",
            note="天气 / 昼夜 / 列车到发 / 时段日历属环境侧，请用 POST /api/traffic/scenario（两个口子不混用）。",
        )
    if target not in FACTOR_TARGETS:
        return _error(
            400,
            CODE_FACTOR_INVALID,
            f"target 须为契约五选一（{' / '.join(FACTOR_TARGETS)}）: {target}",
        )
    if multiplier < 0 or multiplier > 2:
        return _error(400, CODE_FACTOR_INVALID, f"multiplier 须在 [0, 2]: {multiplier:g}")
    name = body.get("name") if isinstance(body.get("name"), str) and body.get("name") else factor_id
    factor = {
        "segment_id": segment_id,
        "factor_id": factor_id,
        "name": name,
        "target": target,
        "multiplier": round(multiplier, 3),
        "until": _factor_until(),
        "injected_at": _now_iso(),
    }
    # 同路段同因素重复置位 → 覆盖（同一请求重复可复现，不堆叠出两份）
    _MANUAL_FACTORS[:] = [
        existing for existing in _MANUAL_FACTORS
        if not (existing.get("segment_id") == segment_id and existing.get("factor_id") == factor_id)
    ]
    _MANUAL_FACTORS.append(factor)
    level = record.get("level") if _valid_level(record.get("level")) else 0
    payload: dict[str, Any] = {
        "applied": True,
        "segment_id": segment_id,
        "factor_id": factor_id,
        "name": name,
        "target": target,
        "multiplier": factor["multiplier"],
        "until": factor["until"],
        # 形状对齐 mock 的 ManualFactorResult；数值是**当前快照原值**，不是注入后重算结果
        "level": level,
        "level_name": _level_name(level, record.get("level_name")),
        "level_recomputed": False,
        "factors_applied": [
            factor_item for factor_item in (record.get("factors_applied") or [])
            if isinstance(factor_item, dict)
        ],
        "injected_factors": _manual_factor_rows(segment_id),
        "is_simulated": True,
        "note": (
            "人工置位已登记（接口层内存态，重启复位）：**只更新因素状态、不重算判级** —— "
            "判级由感知层统一重算、接口层不重算；level / level_name 为当前快照原值（注入前），"
            "不得当作注入后判级。已登记因素见 GET /api/traffic/factors?segment_id=；"
            "复位 POST /api/traffic/factors/reset。"
        ),
    }
    return _json(payload, source="demo-runtime.manual-factor")


@app.post("/api/traffic/scenario")
async def api_scenario_post(request: Request) -> JSONResponse:
    """场景注入（环境侧 F01 / F02 / F03 / F10）：只改环境状态与 derived_factors。"""
    body = await _read_body(request)
    snapshot = build_segments_snapshot()
    segment_id = body.get("segment_id")
    if segment_id is not None and (
        not isinstance(segment_id, str) or segment_id not in snapshot["records"]
    ):
        return _error(
            404,
            CODE_SEGMENT_NOT_FOUND,
            f"路段不存在: {segment_id}",
            note="场景注入只接受当前路段快照里的段号（缺省 = 全路网）；未做任何写入。",
        )
    weather = body.get("weather", _UNSET)
    if weather is not _UNSET and weather is not None and weather not in WEATHERS:
        return _error(
            400, CODE_SCENARIO_INVALID,
            f"weather 须为 {' / '.join(WEATHERS)} 或 null: {weather!r}",
        )
    session = body.get("session", _UNSET)
    if session is not _UNSET and session is not None and session not in SESSION_ORDER:
        return _error(
            400, CODE_SCENARIO_INVALID,
            f"session 须为 {' / '.join(SESSION_ORDER)} 或 null: {session!r}",
        )
    demand_raw = body.get("demand_mult", _UNSET)
    demand_mult: float | None = None
    if demand_raw is not _UNSET and demand_raw is not None:
        raw_value = _num(demand_raw)
        if raw_value is None:
            return _error(
                400, CODE_SCENARIO_INVALID,
                f"demand_mult 须为数值（0.4 ~ 2）或 null: {demand_raw!r}",
            )
        demand_mult = _clamp(raw_value, 0.4, 2.0)

    # 字段语义（与 mock 同口径，别改错）：缺省 = 不改该项；显式 null = 清除该项。
    if weather is not _UNSET:
        _SCENARIO_STATE["weather"] = weather
    if session is not _UNSET:
        _SCENARIO_STATE["session"] = session
        if demand_raw is _UNSET:
            _SCENARIO_STATE["demand_mult"] = None if session is None else SESSION_DEMAND_MULT.get(session)
    if demand_raw is not _UNSET:
        _SCENARIO_STATE["demand_mult"] = demand_mult

    moment = _parse_iso(snapshot["payload"].get("ts")) or _now()
    factors = _derived_env_factors(moment)
    target_ids = (
        [segment_id] if isinstance(segment_id, str)
        else [str(record.get("segment_id")) for record in snapshot["payload"]["segments"]]
    )
    payload: dict[str, Any] = {
        "applied": True,
        "ts": snapshot["payload"]["ts"],
        "is_simulated": True,
        "factors": factors,
        "segment_ids": target_ids,
        # 契约 ScenarioResult 的 effects：注入前后判级对照必须由**感知层重算**后才存在，
        # 接口层不重算 → 如实给空清单 + note，绝不伪造「等级变化」。
        "effects": [],
        "effects_note": "接口层不重算 level / ci：effects 如实为空（判级对照需感知层统一重算后从 /segments 读取）。",
        "recomputed": False,
        "scenario": _scenario_public_state(),
        "note": _ENV_FACTOR_NOTE,
    }
    if not factors:
        payload["note"] = (
            "场景状态已更新，但按演示口径当前未产生 F01/F02/F03/F10 因素"
            "（如天气未注入 / 时段非夜间 / 需求倍率 = 1.0）；" + payload["note"]
        )
    return _json(payload, source="demo-runtime.scenario")


@app.post("/api/traffic/scenario/reset")
def api_scenario_reset() -> JSONResponse:
    """清空场景注入内存态（演示复位；幂等）。"""
    was_injected = _scenario_injected()
    _SCENARIO_STATE.update({"weather": None, "session": None, "demand_mult": None})
    return _json(
        {
            "reset": True,
            "is_simulated": True,
            "was_injected": was_injected,
            "note": (
                "场景注入已复位到「未注入」（接口层内存态，重启亦复位）："
                "环境上下文回落如实口径（天气无数据源），接口层不重算判级。"
            ),
        },
        source="demo-runtime.scenario",
    )



@app.get("/api/traffic/stream")
async def api_stream() -> StreamingResponse:
    async def event_stream():
        while True:
            ping = {
                "ts": _latest_data_ts(),
                "is_simulated": True,
                "note": "快照刷新事件（接口层只读快照）；收到后请重新拉取快照",
            }
            yield f"event: {TRAFFIC_SNAPSHOT_EVENT}\ndata: {json.dumps(ping, ensure_ascii=False)}\n\n"
            await asyncio.sleep(SSE_PERIOD_S)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Traffic-Data-Source": "snapshot-ping",
        },
    )


# ---------------------------------------------------------------- CLI


def print_data_check() -> int:
    """--check：把「每个数据文件在不在、回落到哪一层」打印出来（不起服务）。"""
    print(f"仓库根目录：{ROOT}")
    files = [
        ("视频链路路段产物", PERCEPTION_VIDEO),
        ("孪生链路路段产物", TWIN_LATEST),
        ("孪生契约形状快照", TWIN_SNAPSHOT),
        ("孪生车辆", TWIN_VEHICLES),
        ("同化状态", TWIN_ASSIMILATION),
        ("引擎路线·真网优先", ENGINE_ROUTES_REAL),
        ("引擎路线·样例回退", ENGINE_ROUTES_SAMPLE),
        ("站点范围登记", SITE_RANGES),
        ("站点包 network", STATIONS_DIR / "network.json"),
        ("站点包 points", STATIONS_DIR / "points.json"),
        ("站点包 thresholds", STATIONS_DIR / "thresholds.json"),
        ("站点包 scenarios", STATIONS_DIR / "scenarios.json"),
        ("站点包 factors", STATIONS_DIR / "factors.json"),
        ("站点包 demand", STATIONS_DIR / "demand.json"),
    ]
    for label, path in files:
        state = "存在" if path.is_file() else "缺失"
        print(f"  [{state}] {label:<18} {path.relative_to(ROOT)}")

    snapshot = build_segments_snapshot()
    print()
    print(f"路段快照数据源：{snapshot['source']}")
    print(f"路段数：{len(snapshot['payload']['segments'])}；ts：{snapshot['payload']['ts']}")
    for chain, records in snapshot["channels"].items():
        print(f"  {chain} 链路记录：{len(records)} 条")
    if snapshot["note"]:
        print(f"  降级说明：{snapshot['note']}")

    layers = _routes_layers()
    if layers:
        detail = "；".join(
            f"{key}（{ROUTE_LAYER_NOTES.get(key, key)}）requests {len(payload['requests'])} 条"
            f" · 段号命名空间 {' / '.join(f'{prefix}-###' for prefix in _routes_namespaces(payload)) or '未知'}"
            for key, payload in layers
        )
        print(f"推荐路线数据源优先级：{detail}")
        print(f"  实际使用层：engine.routes.{layers[0][0]}（真网优先，缺失时回退样例）")
    else:
        print("推荐路线数据源：缺失（route/recommend 与 locate 将如实 404，不代算 ETA）")
    print(f"车辆：{len(_vehicle_records())} 辆")
    assimilation = build_assimilation()
    print(f"同化断面：{len(assimilation['records'])} 条（boundary {assimilation['counts']['boundary']} / internal {assimilation['counts']['internal']}）")
    print(f"告警（从快照派生）：{len(build_alerts(snapshot)['alerts'])} 条")
    store = get_dispatch_store()
    state_exists = "存在" if store.path.is_file() else "尚未创建（首次写入时生成）"
    print(f"处置闭环运行态（持久化）：{store.relative_path()}（{state_exists}）")
    print(
        f"  已落盘告警运行态 {len(store.all_alerts())} 条 · 审计 {store.audit_total()} 条"
        f"（保留最近 {DISPATCH_AUDIT_MAX} 条）· 复位 {store.reset_count()} 次"
    )
    for alert_id, runtime in list(store.all_alerts().items())[:6]:
        print(
            f"  - {alert_id}: {runtime.get('status')} · 渠道 {runtime.get('channels')} · "
            f"比例 {runtime.get('dispatch_ratio_pct')} · 回写 {bool(runtime.get('writeback'))}"
        )
    print(
        "写端点内存态（factors / scenario 仍是进程内存；--check 是新进程，恒为空）："
        f"人工置位 {len(_MANUAL_FACTORS)} 条 · 场景注入 {'已注入' if _scenario_injected() else '未注入'}"
    )
    print()
    print("检查完成：缺失的数据源会按三层回落 / 空壳 + note 处理，不报 500。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="hubflow 接口层：/api/traffic/*（只读快照 + 处置闭环持久化，契约 §七）"
    )
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1）")
    parser.add_argument("--port", type=int, default=8000, help="端口（默认 8000，前端 VITE_API_BASE 指向这里）")
    parser.add_argument("--log-level", default="info", help="uvicorn 日志级别")
    parser.add_argument("--check", action="store_true",
                        help="只打印数据源 / 处置运行态解析结果，不启动服务")
    parser.add_argument(
        "--state-path",
        default=DISPATCH_STORE_DEFAULT.relative_to(ROOT).as_posix(),
        help="处置闭环运行态 JSON 路径（默认 work/assembly/data/dispatch.json；相对路径按仓库根解析）",
    )
    parser.add_argument("--reset-state", action="store_true",
                        help="复位处置运行态（重放 seed_dispatch）并写一条 reset 审计后退出（不起服务）")
    args = parser.parse_args()

    state_path = Path(args.state_path)
    configure_dispatch_store(state_path if state_path.is_absolute() else ROOT / state_path)
    store = get_dispatch_store()  # 启动时加载：坏文件改名留证、按初始态启动

    if args.reset_state:
        result = store.reset()
        if not result.get("ok"):
            print("复位失败：处置运行态落盘失败（检查 work/assembly/data/ 是否可写）", file=sys.stderr)
            return 1
        print(f"已复位处置闭环运行态：{store.relative_path()}")
        print(
            f"  cleared_alerts={result['cleared_alerts']} · seed_alerts={result['seed_alerts']} · "
            f"reset_count={result['reset_count']} · audit_seq={result['audit_seq']}"
        )
        print(f"  审计总数 {store.audit_total()} 条（reset 已留痕）；{DEMO_DISPATCH_NOTE}")
        return 0
    if args.check:
        return print_data_check()

    print(f"接口层 traffic.py → http://{args.host}:{args.port}", flush=True)
    print("  口径：只读快照 / 所有响应 is_simulated=true / 数据源三层回落（缺文件不 500）", flush=True)
    print("  路线：真网产物 out/real/routes.json 优先，缺失回退样例 out/routes.json", flush=True)
    print(
        f"  处置闭环（持久化）：{store.relative_path()} 已加载 {len(store.all_alerts())} 条告警运行态"
        f" / {store.audit_total()} 条审计（重启不复位）",
        flush=True,
    )
    print("  写端点：factors / scenario 为进程内存态（重启复位），接口层不重算判级", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
