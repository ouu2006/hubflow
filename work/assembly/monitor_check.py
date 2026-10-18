#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C-7 监控自检脚本（IKMS1I）：一条命令核对一期单机部署的监控项。

按手册 §21.2「监控分三层（数据 / 服务 / 效果）+ 每项都有可执行动作」落最小可执行版：
一期单机只做**数据 / 服务**两层里能实测的项；效果类（判级一致率 / 预测误差 / 采纳率）与备份、
合规留存属二期，不在本脚本假装监控。

监控项（每项给 ok / warn / fail 与动作建议）：

    服务  接口层进程是否在跑、端口 8000 是否 LISTEN
    服务  接口可用性与时延（GET /api/traffic/meta 等；记录 5xx 数、P 值不测）
    数据  路段快照数据陈旧（data_age_s > 阈值的路段数）
    数据  数据源与降级（响应头 X-Traffic-Data-Source、空壳 note）
    服务  处置闭环持久化文件（是否存在 / 可解析 / 审计条数 / 复位次数）
    服务  磁盘使用率（> 85% 警告）与日志目录体积
    服务  感知服务端口（可选，--with-perception）

跑法（在仓库根）：

    python work/assembly/monitor_check.py                 # 只看接口层 :8000
    python work/assembly/monitor_check.py --with-perception
    python work/assembly/monitor_check.py --json work/assembly/out/monitor_check.json

退出码：0 = 全部正常；1 = 有警告；2 = 有关键故障（接口不可用 / 出现 5xx）。
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[2]
DISPATCH_STATE = ROOT / "work" / "assembly" / "data" / "dispatch.json"
LOG_DIRS = [ROOT / "work" / "assembly" / "out", ROOT / "work" / "engine" / "out", ROOT / "work" / "perception" / "out"]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def decode(raw: bytes) -> Any:
    text = raw.decode("utf-8", "replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text[:200]}


def http_call(url: str, timeout: float = 5.0) -> tuple[int, Any, dict[str, str], float]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            headers = {str(key).lower(): str(value) for key, value in dict(response.headers).items()}
            return response.status, decode(response.read()), headers, round(
                (time.perf_counter() - started) * 1000, 1)
    except urllib.error.HTTPError as error:
        headers = {str(key).lower(): str(value) for key, value in dict(error.headers).items()}
        return error.code, decode(error.read()), headers, round((time.perf_counter() - started) * 1000, 1)
    except (urllib.error.URLError, OSError) as error:
        return 0, {"error": str(error)}, {}, round((time.perf_counter() - started) * 1000, 1)


def listening(port: int) -> bool:
    if psutil is not None:
        try:
            for conn in psutil.net_connections(kind="tcp"):
                if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port:
                    return True
            return False
        except Exception:  # noqa: BLE001 - 权限受限时退回 socket 探测
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def traffic_process() -> dict[str, Any]:
    if psutil is None:
        return {"available": False, "count": None, "pids": []}
    pids: list[int] = []
    try:
        for process in psutil.process_iter(["pid", "name", "cmdline"]):
            # 只认 python 解释器，且参数里确实有 work/assembly/traffic.py（排除包装脚本 / 命令行里
            # 恰好含这串字符的其它进程——实测会被 IDE / Harness 的包装进程误匹配）
            name = (process.info.get("name") or "").lower()
            if not name.startswith("python"):
                continue
            arguments = [str(item).replace("\\", "/") for item in (process.info.get("cmdline") or [])]
            if any(argument.endswith("work/assembly/traffic.py") for argument in arguments):
                if process.info["pid"] != os.getpid():
                    pids.append(process.info["pid"])
    except Exception:  # noqa: BLE001
        return {"available": False, "count": None, "pids": []}
    return {"available": True, "count": len(pids), "pids": pids}


class Monitor:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []

    def add(self, layer: str, name: str, status: str, detail: Any, action: str = "") -> None:
        self.checks.append({"layer": layer, "name": name, "status": status, "detail": detail, "action": action})

    @property
    def status(self) -> str:
        statuses = {check["status"] for check in self.checks}
        if "fail" in statuses:
            return "fail"
        if "warn" in statuses:
            return "warn"
        return "ok"


def collect(port: int, perception_port: int | None, stale_threshold: float,
            disk_warn: float) -> dict[str, Any]:
    monitor = Monitor()
    base = f"http://127.0.0.1:{port}"

    # ---- 服务：进程 / 端口
    process = traffic_process()
    if process["available"]:
        monitor.add("服务", "接口层进程", "ok" if process["count"] else "fail",
                    f"traffic.py 进程数={process['count']}（pid={process['pids']}）",
                    "" if process["count"] else "启动 python work/assembly/traffic.py --port 8000")
    else:
        monitor.add("服务", "接口层进程", "warn", "psutil 不可用，未检查进程（端口检查继续）",
                    "pip install psutil 或人工确认进程")
    port_listening = listening(port)
    monitor.add("服务", f"端口 {port}", "ok" if port_listening else "fail",
                "LISTEN" if port_listening else "未监听", "" if port_listening else "启动接口层或检查端口冲突")

    meta_status, meta_payload, meta_headers, meta_ms = http_call(base + "/api/traffic/meta")
    if meta_status != 200:
        monitor.add("服务", "接口可用性", "fail", f"GET /api/traffic/meta -> {meta_status}", "检查接口层日志")
    else:
        latency = meta_ms
        status = "ok" if latency <= 3000 else "warn"
        monitor.add("服务", "接口可用性与时延", status,
                    f"GET /api/traffic/meta -> 200 · {latency} ms（本机回环，单次采样；P95 需压测脚本）",
                    "" if status == "ok" else "看 stress_test.py 报告 / 排查机器负载")

    # ---- 数据：路段陈旧 / 数据源
    status_5xx = 0
    segments_status, segments_payload, segments_headers, segments_ms = http_call(base + "/api/traffic/segments")
    if segments_status >= 500:
        status_5xx += 1
    source = segments_headers.get("x-traffic-data-source") or "unknown"
    if segments_status != 200:
        monitor.add("数据", "路段快照", "fail", f"GET /api/traffic/segments -> {segments_status}", "检查数据源文件 / 接口日志")
        stale_count = unavailable_count = segment_total = None
    else:
        segments = segments_payload.get("segments") if isinstance(segments_payload, dict) else []
        segment_total = len(segments or [])
        stale_count = 0
        unavailable_count = 0
        max_age = None
        for record in segments or []:
            age = record.get("data_age_s")
            if isinstance(age, (int, float)):
                max_age = age if max_age is None else max(max_age, age)
                if age > stale_threshold:
                    stale_count += 1
            if not isinstance(record.get("level"), int) or record.get("level") == 0:
                unavailable_count += 1
        status = "ok" if stale_count == 0 else "warn"
        detail = (f"路段 {segment_total} 段 · 数据源 {source} · 数据年龄最大值 {max_age}s · "
                  f"陈旧(> {stale_threshold:g}s) {stale_count} 段 · 不可用 {unavailable_count} 段")
        action = "" if status == "ok" else "按手册 §21.2：标「陈旧」、不进入推荐计算，只展示；检查上游是否停更"
        monitor.add("数据", "数据新鲜度", status, detail, action)

    # ---- 服务：5xx 统计（继续打关键端点）
    for name, path in (
        ("alerts", "/api/traffic/alerts"),
        ("plan/audit", "/api/traffic/plan/audit?limit=5"),
        ("overview", "/api/traffic/overview"),
    ):
        code, payload, headers, elapsed = http_call(base + path)
        if code >= 500:
            status_5xx += 1
        level = "ok" if code == 200 else ("fail" if code >= 500 else "warn")
        monitor.add("服务", f"端点 {name}", level, f"GET {path} -> {code} · {elapsed} ms",
                    "" if code == 200 else "查看接口层日志与数据源")
        if name == "alerts" and code == 200 and isinstance(payload, dict):
            alerts = payload.get("alerts") or []
            monitor.add("服务", "告警列表", "ok", f"{len(alerts)} 条（四态见 GET /alerts）")

    if status_5xx:
        monitor.add("服务", "接口 5xx", "fail", f"本次巡检出现 {status_5xx} 次 5xx", "立即看日志；按 §21.5 P1 处置")
    else:
        monitor.add("服务", "接口 5xx", "ok", "本次巡检 0 次 5xx")

    # ---- 服务：处置闭环持久化文件
    if DISPATCH_STATE.is_file():
        try:
            state = json.loads(DISPATCH_STATE.read_text(encoding="utf-8"))
            monitor.add("服务", "处置闭环持久化文件", "ok",
                        f"{relative(DISPATCH_STATE)} · schema={state.get('schema_version')} · "
                        f"告警运行态 {len(state.get('alerts') or {})} 条 · 审计 {state.get('audit_total')} 条 · "
                        f"复位 {state.get('reset_count')} 次 · 更新于 {state.get('updated_at')}", "")
        except (OSError, ValueError) as error:
            monitor.add("服务", "处置闭环持久化文件", "fail", f"{relative(DISPATCH_STATE)} 不可解析：{error}",
                        "停止写入后按 README §2.2 处理坏文件（改名留证后按初始态启动）")
    else:
        monitor.add("服务", "处置闭环持久化文件", "ok",
                    f"{relative(DISPATCH_STATE)} 不存在（尚未发生下发/回写，属正常初始态；首次写入时创建）", "")

    # ---- 服务：磁盘 / 日志
    disk_percent = None
    if psutil is not None:
        try:
            usage = psutil.disk_usage(str(ROOT))
            disk_percent = usage.percent
        except OSError:
            pass
    if disk_percent is None:
        monitor.add("服务", "磁盘使用率", "warn", "psutil 不可用，磁盘未测", "python -c \"import psutil\" 或人工查看")
    else:
        level = "warn" if disk_percent > disk_warn else "ok"
        monitor.add("服务", "磁盘使用率", level, f"{disk_percent:.1f}%（阈值 {disk_warn:g}%）",
                    "" if level == "ok" else "清理 out/ 日志与旧产物；归档后重跑")
    log_bytes = 0
    for directory in LOG_DIRS:
        for path in directory.rglob("*.log") if directory.is_dir() else []:
            try:
                log_bytes += path.stat().st_size
            except OSError:
                pass
    monitor.add("服务", "日志体积", "ok", f"out/ 下 *.log 合计 {round(log_bytes / (1024 * 1024), 2)} MiB"
                "（一期不自动轮转，演示前可清 out/）")

    # ---- 服务：感知服务（可选）
    if perception_port is not None:
        perception_ok = listening(perception_port)
        monitor.add("服务", f"感知服务端口 {perception_port}", "ok" if perception_ok else "warn",
                    "LISTEN" if perception_ok else "未监听（感知页视频不可用，业务接口不受影响）",
                    "" if perception_ok else "需要感知页时：python work/perception/server.py --port 8101")

    # ---- 一期范围说明（不假装监控的项）
    monitor.add("范围", "二期监控项（一期不做）", "ok",
                "判级一致率 / 预测误差 / 采纳率（效果层）、备份任务、会话数据留存（合规层）、openGauss/Atlas —— "
                "按手册 §21.2 属二期，本脚本不采集、不编造", "")

    return {
        "schema_version": 1,
        "is_simulated": True,
        "generated_at": now_iso(),
        "port": port,
        "perception_port": perception_port,
        "status": monitor.status,
        "checks": monitor.checks,
        "note": "一期单机监控自检（演示数据（模拟））：只采集数据/服务两层中可实测的项；"
                "效果层与备份/合规留存属二期，不在此假装监控。",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="C-7 监控自检：进程 / 端口 / 数据新鲜度 / 5xx / 磁盘 / 持久化文件")
    parser.add_argument("--port", type=int, default=8000, help="接口层端口（默认 8000）")
    parser.add_argument("--perception-port", type=int, default=None,
                        help="可选：同时检查感知服务端口（如 8101）")
    parser.add_argument("--with-perception", action="store_true", help="等价于 --perception-port 8101")
    parser.add_argument("--stale-threshold", type=float, default=120.0,
                        help="数据陈旧阈值秒（默认 120，手册 §21.2【待标定】）")
    parser.add_argument("--disk-warn", type=float, default=85.0, help="磁盘使用率告警阈值（默认 85%）")
    parser.add_argument("--json", default=str(ROOT / "work" / "assembly" / "out" / "monitor_check.json"),
                        help="巡检结果 JSON 路径（默认 out/monitor_check.json，gitignored）")
    args = parser.parse_args()
    perception_port = 8101 if args.with_perception else args.perception_port

    report = collect(args.port, perception_port, args.stale_threshold, args.disk_warn)
    json_path = Path(args.json)
    if not json_path.is_absolute():
        json_path = ROOT / json_path
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8", newline="\n")

    print(f"C-7 监控自检（演示数据（模拟））· {report['generated_at']}")
    print(f"{'层':<5}{'状态':<6}{'监控项':<22}{'实测 / 说明'}")
    icons = {"ok": "✅", "warn": "⚠", "fail": "❌"}
    for check in report["checks"]:
        print(f"{check['layer']:<5}{icons[check['status']]:<5}{check['name']:<22}{check['detail']}")
        if check["action"] and check["status"] != "ok":
            print(f"       → 动作：{check['action']}")
    print()
    print(f"总体：{ {'ok': '全部正常', 'warn': '有警告', 'fail': '有关键故障'}[report['status']] }"
          f" · 结果 JSON：{relative(json_path)}")
    return {"ok": 0, "warn": 1, "fail": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
