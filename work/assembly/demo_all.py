#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C-4 一键演示脚本（IKMS1I）：检查环境 → 跑真网算路 → 跑感知链路 → 起接口层 → 端点自检 → 收尾。

**演示数据（模拟）**：本脚本只编排链路，不产生任何真实数据；每一轮的结果如实记录，缺前置就标
「阻塞」，**不写通过、不隐藏失败**。

跑法（在仓库根；Windows 也可双击/运行 `work/assembly/demo_all.ps1`）：

    python work/assembly/demo_all.py                     # 1 轮（默认）
    python work/assembly/demo_all.py --rounds 3          # M1-6：无人干预连跑 3 轮
    python work/assembly/demo_all.py --rounds 3 --with-perception-server
    python work/assembly/demo_all.py --skip-engine --skip-perception   # 只验接口层
    python work/assembly/demo_all.py --rounds 3 --json-report work/assembly/out/my_report.json

每一轮做（顺序固定、失败即停；阻塞项继续做后续不受影响的步骤并如实记录）：

    ① 环境检查      Python / psutil / 端口 8000 空闲 / 真网产物与感知样本数据是否在场
    ② 真网算路      python work/engine/run.py --network real  → work/engine/out/real/routes.json
    ③ 感知链路      python work/perception/run_chain.py       → work/perception/out/latest/segments_video.json
    ④ 起接口层      python work/assembly/traffic.py --port 8000（等 /api/traffic/meta 就绪）
    ⑤ 端点自检      关键 GET 200 / route/recommend 200 / plan/audit / SSE /（有告警时演示下发→回写→复位）
    ⑥ 收尾          停进程、采样内存、清点本轮日志与关键产物

每轮产物：`work/assembly/out/demo/round-<n>/`（各步骤日志 + 命令）；
汇总报告：`work/assembly/out/demo_all_report.json`（**gitignored**，不提交）。

**数据前置（gitignored，不在仓库）**：感知链路需要 `work/perception/data/monitor/<stream>/{meta.json,detections.json}`
（上游样本视频导出产物；视频 / 导出数据不进仓库，放共享盘或本机，按 work/assembly/README.md §三 放置）。
数据不在场时本脚本把感知链路**如实标 blocked**、不声明 M1-6 通过；数据在场时 `--rounds 3` 可跑出
**M1-6 通过**（实测见 work/assembly/自检记录-IKMS1I.md §一 1.2）。

**M1-6 判定的必需步骤 = 真网算路 + 感知链路 + 接口层 + 端点自检**。用 `--skip-engine` / `--skip-perception`
跳过任一必需步骤时，本次只算「接口层自检」，M1-6 判「**未评估（不适用）**」（`m1_6.passed=false`、
`m1_6.evaluated=false`），**不得当通过**；退出码仍可为 0（接口层自检成功）。

退出码：0 = 全部步骤成功；2 = 跑完但有阻塞项（如实记录，**不算 M1-6 通过**）；1 = 有失败 / 异常。
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

# Windows 控制台默认不是 UTF-8：先固定 stdout/stderr 编码，避免中文 / 符号打印直接抛异常
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

try:
    import psutil  # 内存采样用；缺失时如实标注「psutil 不可用」，不编数字
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[2]
ASSEMBLY = ROOT / "work" / "assembly"
TRAFFIC = ASSEMBLY / "traffic.py"
ENGINE_RUN = ROOT / "work" / "engine" / "run.py"
ENGINE_REAL_ROUTES = ROOT / "work" / "engine" / "out" / "real" / "routes.json"
ENGINE_REAL_LOG = ROOT / "work" / "engine" / "out" / "real" / "run_log.json"
PERCEPTION_CHAIN = ROOT / "work" / "perception" / "run_chain.py"
PERCEPTION_VIDEO = ROOT / "work" / "perception" / "out" / "latest" / "segments_video.json"
PERCEPTION_SERVER = ROOT / "work" / "perception" / "server.py"
PERCEPTION_DATA = ROOT / "work" / "perception" / "data" / "monitor"
NETWORK_JUNCTION = ROOT / "work" / "twin" / "netpack" / "network_junction.json"
SITE_RANGES = ROOT / "work" / "twin" / "site-ranges.json"
DISPATCH_STATE = ASSEMBLY / "data" / "dispatch.json"
OUT_ROOT = ASSEMBLY / "out" / "demo"
DEFAULT_REPORT = ASSEMBLY / "out" / "demo_all_report.json"

STALE_AFTER_S = 120.0
MEMORY_GROWTH_MIN_BYTES = 20 * 1024 * 1024
MEMORY_GROWTH_RATIO = 0.10

#: 端点自检清单（只读；写端点在有派生告警时额外演示，见 run_endpoint_checks）
GET_ENDPOINTS = [
    ("meta", "/api/traffic/meta"),
    ("overview", "/api/traffic/overview"),
    ("segments", "/api/traffic/segments"),
    ("network", "/api/traffic/network"),
    ("thresholds", "/api/traffic/thresholds"),
    ("context", "/api/traffic/context"),
    ("factors", "/api/traffic/factors"),
    ("assimilation", "/api/traffic/assimilation"),
    ("alerts", "/api/traffic/alerts"),
    ("vehicles", "/api/traffic/vehicles"),
    ("heat-matrix", "/api/traffic/heat-matrix?window=12&bucket=60"),
    ("plan-audit", "/api/traffic/plan/audit?limit=20"),
]


# ---------------------------------------------------------------- 基础工具


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def log(message: str) -> None:
    print(message, flush=True)


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def http_call(url: str, method: str = "GET", body: dict | None = None,
              timeout: float = 10.0) -> tuple[int, Any, dict[str, str], float]:
    """返回 (状态码, JSON/文本, 响应头(小写键), 耗时 ms)。网络错误返回状态码 0。"""
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            headers_out = {str(key).lower(): str(value) for key, value in dict(response.headers).items()}
            return response.status, decode(raw), headers_out, round((time.perf_counter() - started) * 1000, 2)
    except urllib.error.HTTPError as error:
        headers_out = {str(key).lower(): str(value) for key, value in dict(error.headers).items()}
        return error.code, decode(error.read()), headers_out, round((time.perf_counter() - started) * 1000, 2)
    except (urllib.error.URLError, OSError) as error:
        return 0, {"error": str(error)}, {}, round((time.perf_counter() - started) * 1000, 2)


def decode(raw: bytes) -> Any:
    text = raw.decode("utf-8", "replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text[:300]}


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def file_info(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except OSError:
        return {"path": relative(path), "exists": False, "size_bytes": None, "mtime_iso": None}
    return {
        "path": relative(path),
        "exists": True,
        "size_bytes": stat.st_size,
        "mtime_iso": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
        "mtime_ns": stat.st_mtime_ns,
    }


def environment_snapshot() -> dict[str, Any]:
    cpu = platform.processor() or ""
    memory_total = None
    if psutil is not None:
        try:
            memory_total = psutil.virtual_memory().total
            cpu = cpu or (psutil.cpu_count(logical=False) and f"{psutil.cpu_count(logical=False)} cores")
        except Exception:  # noqa: BLE001 - 环境信息读不到就留空，不编
            pass
    return {
        "is_simulated": True,
        "os": platform.platform(),
        "machine": platform.machine(),
        "processor": cpu,
        "cpu_logical": os.cpu_count(),
        "memory_total_bytes": memory_total,
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "psutil": getattr(psutil, "__version__", None),
        "sumo_home": os.environ.get("SUMO_HOME"),
        "git_commit": git_output("rev-parse", "--short", "HEAD"),
        "git_branch": git_output("rev-parse", "--abbrev-ref", "HEAD"),
    }


def git_output(*args: str) -> str | None:
    try:
        process = subprocess.run(
            ["git", *args], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (process.stdout or "").strip()
    return text or None


def disk_free_gb(path: Path = ROOT) -> float | None:
    try:
        usage = os.statvfs(path)  # type: ignore[attr-defined]
        return round(usage.f_bavail * usage.f_frsize / (1024 ** 3), 2)
    except AttributeError:
        pass
    except OSError:
        return None
    if psutil is None:
        return None
    try:
        return round(psutil.disk_usage(str(path)).free / (1024 ** 3), 2)
    except OSError:
        return None


# ---------------------------------------------------------------- 前置检查


def preflight(port: int, with_perception_server: bool) -> dict[str, Any]:
    """环境检查：返回 {"blockers": [...], "checks": {...}}；不在这里中断。"""
    checks: dict[str, Any] = {
        "python_ok": sys.version_info >= (3, 10),
        "psutil_available": psutil is not None,
        "traffic_port": port,
        "traffic_port_free": port_free(port),
        "engine_real_data": {
            "network_junction": file_info(NETWORK_JUNCTION)["exists"],
            "site_ranges": file_info(SITE_RANGES)["exists"],
        },
        "perception_data": perception_data_status(),
        "dispatch_state": file_info(DISPATCH_STATE),
        "disk_free_gb": disk_free_gb(),
    }
    blockers: list[str] = []
    if not checks["python_ok"]:
        blockers.append("Python 版本过低（需 ≥3.10）")
    if not checks["traffic_port_free"]:
        blockers.append(f"端口 {port} 被占用（先停掉其它接口层实例）")
    if not (checks["engine_real_data"]["network_junction"] and checks["engine_real_data"]["site_ranges"]):
        blockers.append("真网算路前置缺失（work/twin/netpack/network_junction.json 或 site-ranges.json）")
    if not checks["perception_data"]["ready"]:
        blockers.append(checks["perception_data"]["reason"])
    if with_perception_server and not PERCEPTION_SERVER.is_file():
        blockers.append("work/perception/server.py 不在场，无法起感知服务")
    checks["blockers"] = blockers
    return checks


def perception_data_status() -> dict[str, Any]:
    """感知链路前置：work/perception/data/monitor/<stream>/{meta.json,detections.json}（gitignored）。"""
    if not PERCEPTION_DATA.is_dir():
        return {
            "ready": False,
            "streams": [],
            "reason": "缺感知样本导出 work/perception/data/monitor/（gitignored；上游样本视频导出产物，放置路径与来源见 work/assembly/README.md §三）→ 感知链路会 0 通道产出",
        }
    streams = []
    for stream_dir in sorted(path for path in PERCEPTION_DATA.iterdir() if path.is_dir()):
        has_data = (stream_dir / "meta.json").is_file() and (stream_dir / "detections.json").is_file()
        streams.append({"stream": stream_dir.name, "has_data": has_data})
    ready = any(item["has_data"] for item in streams)
    return {
        "ready": ready,
        "streams": streams,
        "reason": None if ready else "work/perception/data/monitor/ 存在但没有 meta.json + detections.json → 感知链路会 0 通道产出",
    }


# ---------------------------------------------------------------- 进程 / 内存


class ProcessMemorySampler(threading.Thread):
    """采样某个子进程的 RSS（psutil 可用时）；不可用时 samples 为空、报告如实写 null。"""

    def __init__(self, pid: int, interval_s: float = 0.25) -> None:
        super().__init__(daemon=True)
        self.pid = pid
        self.interval_s = interval_s
        self.samples: list[dict[str, Any]] = []
        # 注意：不能叫 _stop —— 会覆盖 threading.Thread._stop()，join() 时抛 TypeError
        self._stop_event = threading.Event()

    def run(self) -> None:  # pragma: no cover - 采样线程
        if psutil is None:
            return
        try:
            process = psutil.Process(self.pid)
        except Exception:  # noqa: BLE001 - 进程可能已退出
            return
        started = time.perf_counter()
        while not self._stop_event.is_set():
            try:
                rss = process.memory_info().rss
                self.samples.append({
                    "t": round(time.perf_counter() - started, 2),
                    "rss_mb": round(rss / (1024 * 1024), 2),
                })
            except Exception:  # noqa: BLE001
                break
            self._stop_event.wait(self.interval_s)

    def stop(self) -> list[dict[str, Any]]:
        self._stop_event.set()
        self.join(timeout=3)
        return self.samples


def memory_summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {
            "samples": 0,
            "start_mb": None,
            "end_mb": None,
            "max_mb": None,
            "growth_mb": None,
            "note": "psutil 不可用或采样失败：内存未测量（不编数字）",
        }
    start = samples[0]["rss_mb"]
    end = samples[-1]["rss_mb"]
    return {
        "samples": len(samples),
        "start_mb": start,
        "end_mb": end,
        "max_mb": max(item["rss_mb"] for item in samples),
        "growth_mb": round(end - start, 2),
    }


# ---------------------------------------------------------------- 单轮执行


class DemoRound:
    def __init__(self, index: int, args: argparse.Namespace, preflight_result: dict[str, Any]) -> None:
        self.index = index
        self.args = args
        self.preflight = preflight_result
        self.round_dir = OUT_ROOT / f"round-{index:02d}"
        self.round_dir.mkdir(parents=True, exist_ok=True)
        self.stages: list[dict[str, Any]] = []
        self.started_at = now_iso()
        self.started = time.perf_counter()
        self.traffic_process: subprocess.Popen | None = None
        self.perception_process: subprocess.Popen | None = None
        self.sampler: ProcessMemorySampler | None = None
        self.memory_samples: list[dict[str, Any]] = []
        self.memory: dict[str, Any] = {}
        self.endpoint_checks: list[dict[str, Any]] = []
        self.ssE: dict[str, Any] = {}

    # ---- 阶段记录

    def stage(self, name: str, status: str, reason: str | None = None, **detail: Any) -> dict[str, Any]:
        item: dict[str, Any] = {
            "stage": name,
            "status": status,  # ok / blocked / failed / skipped
            "reason": reason,
            **detail,
        }
        self.stages.append(item)
        log(f"    [{status.upper():7s}] {name}" + (f"：{reason}" if reason else ""))
        return item

    def run_command(self, name: str, command: list[str], timeout: float,
                    blocked_reason: str | None = None) -> dict[str, Any]:
        if blocked_reason:
            return self.stage(name, "blocked", blocked_reason, command=command)
        log_file = self.round_dir / f"{name}.log"
        started = time.perf_counter()
        with log_file.open("w", encoding="utf-8", newline="\n") as handler:
            handler.write(f"$ {' '.join(command)}\n# cwd={relative(ROOT)} started_at={now_iso()}\n\n")
            handler.flush()
            try:
                process = subprocess.run(
                    command, cwd=str(ROOT), capture_output=True, timeout=timeout,
                )
                stdout = process.stdout.decode("utf-8", "replace")
                stderr = process.stderr.decode("utf-8", "replace")
                handler.write(stdout)
                if stderr:
                    handler.write("\n[stderr]\n" + stderr)
                handler.write(f"\n# exit_code={process.returncode}\n")
                duration = round((time.perf_counter() - started) * 1000, 1)
                if process.returncode == 0:
                    return self.stage(name, "ok", None, duration_ms=duration,
                                      command=command, log=relative(log_file))
                return self.stage(
                    name, "failed", f"命令退出码 {process.returncode}（详见 {relative(log_file)}）",
                    duration_ms=duration, command=command, log=relative(log_file),
                    stderr_tail=stderr.strip().splitlines()[-3:],
                )
            except subprocess.TimeoutExpired:
                handler.write(f"\n# TIMEOUT after {timeout}s\n")
                duration = round((time.perf_counter() - started) * 1000, 1)
                return self.stage(name, "failed", f"命令超时（{timeout:g}s）",
                                  duration_ms=duration, command=command, log=relative(log_file))
            except OSError as error:
                duration = round((time.perf_counter() - started) * 1000, 1)
                return self.stage(name, "failed", f"命令无法启动：{error}",
                                  duration_ms=duration, command=command, log=relative(log_file))

    # ---- 各阶段

    def stage_engine(self) -> dict[str, Any]:
        if self.args.skip_engine:
            return self.stage("engine-real", "skipped", "--skip-engine")
        if not (NETWORK_JUNCTION.is_file() and SITE_RANGES.is_file()):
            return self.stage("engine-real", "blocked", "真网前置缺失（network_junction.json / site-ranges.json）")
        before = file_info(ENGINE_REAL_ROUTES)
        started_ns = time.time_ns()
        result = self.run_command(
            "engine-real",
            [sys.executable, str(ENGINE_RUN), "--network", "real"],
            timeout=self.args.timeout_engine,
        )
        after = file_info(ENGINE_REAL_ROUTES)
        if result["status"] == "ok":
            run_log = read_json(ENGINE_REAL_LOG) or {}
            routes = read_json(ENGINE_REAL_ROUTES) or {}
            # 严格新鲜度：mtime 必须**严格大于**运行前、且不早于本次阶段开始，产物才算「本轮生成」；
            # 仅 >= 会把「命令退出 0 但根本没重写」的旧产物当新鲜（独立审查发现）。
            before_ns = before.get("mtime_ns") or 0
            after_ns = after.get("mtime_ns") or 0
            fresh = bool(after["exists"]) and after_ns > before_ns and after_ns >= started_ns
            requests = routes.get("requests") if isinstance(routes.get("requests"), list) else []
            if not fresh:
                result.update(
                    status="failed",
                    reason="命令退出码 0 但产物未由本轮重写（mtime 未前进 / 早于阶段开始，可能是旧产物）",
                    detail={
                        "before_mtime_ns": before_ns or None,
                        "after_mtime_ns": after_ns or None,
                        "stage_started_ns": started_ns,
                    },
                )
            elif not requests:
                result.update(status="failed", reason="routes.json 无 requests")
            else:
                result.update(
                    status="ok",
                    artifacts=[after],
                    detail={
                        "requests": len(requests),
                        "node_count": run_log.get("node_count"),
                        "edge_count": run_log.get("edge_count"),
                        "requests_with_reservation": run_log.get("requests_with_reservation"),
                        "segment_namespace": "SZ",
                        "routes_ts": routes.get("ts"),
                        # 新鲜度证据：产物 mtime 由本轮生成（严格 > 运行前，且不早于阶段开始）
                        "before_mtime_ns": before_ns or None,
                        "artifact_mtime_ns": after_ns,
                        "stage_started_ns": started_ns,
                        "freshness_rule": "mtime 严格大于运行前且不早于阶段开始",
                    },
                )
                log(f"      真网产物：{relative(ENGINE_REAL_ROUTES)}（requests={len(requests)}）")
                self.stages[-1] = result
        return result

    def stage_perception(self) -> dict[str, Any]:
        if self.args.skip_perception:
            return self.stage("perception-chain", "skipped", "--skip-perception")
        blocked = None
        status = perception_data_status()
        if not status["ready"]:
            blocked = status["reason"]
        before_video = file_info(PERCEPTION_VIDEO)
        started_ns = time.time_ns()
        result = self.run_command(
            "perception-chain",
            [sys.executable, str(PERCEPTION_CHAIN)],
            timeout=self.args.timeout_perception,
            blocked_reason=blocked,
        )
        video = read_json(PERCEPTION_VIDEO) or {}
        segments = video.get("segments") if isinstance(video.get("segments"), list) else []
        artifact = file_info(PERCEPTION_VIDEO)
        if result["status"] == "ok":
            if not artifact["exists"]:
                result.update(status="failed", reason="感知链路退出码 0 但产物不存在")
            elif not ((artifact.get("mtime_ns") or 0) > (before_video.get("mtime_ns") or 0)
                      and (artifact.get("mtime_ns") or 0) >= started_ns):
                result.update(
                    status="failed",
                    reason="感知链路退出码 0 但产物未由本轮重写（mtime 未前进 / 早于阶段开始，可能是旧产物）",
                    detail={
                        "before_mtime_ns": before_video.get("mtime_ns"),
                        "after_mtime_ns": artifact.get("mtime_ns"),
                        "stage_started_ns": started_ns,
                    },
                )
            elif len(segments) == 0:
                # 关键：run_chain 在缺样本数据时也会以 0 退出并写空数组——这里必须判「阻塞」而不是「成功」
                result.update(
                    status="blocked",
                    reason="感知链路 0 通道产出（缺 work/perception/data/monitor 样本导出；脚本如实跳过，不编数据）",
                    artifacts=[artifact],
                    detail={"segments": 0, "channels": status.get("streams")},
                )
                self.stages[-1] = result
            else:
                result.update(artifacts=[artifact],
                              detail={"segments": len(segments),
                                      "segment_ids": [item.get("segment_id") for item in segments]})
                self.stages[-1] = result
        elif result["status"] == "failed" and artifact["exists"] and len(segments) == 0:
            result["detail"] = {"segments": 0}
        return result

    def stage_traffic_start(self) -> dict[str, Any]:
        if not self.preflight["traffic_port_free"]:
            return self.stage("traffic-start", "failed", f"端口 {self.args.port} 被占用")
        log_file = self.round_dir / "traffic-server.log"
        handler = log_file.open("w", encoding="utf-8", newline="\n")
        started = time.perf_counter()
        command = [sys.executable, str(TRAFFIC), "--port", str(self.args.port)]
        self.traffic_process = subprocess.Popen(
            command, cwd=str(ROOT), stdout=handler, stderr=subprocess.STDOUT,
        )
        ready = False
        deadline = time.time() + self.args.timeout_startup
        while time.time() < deadline:
            if self.traffic_process.poll() is not None:
                break
            status, payload, _, _ = http_call(
                f"http://127.0.0.1:{self.args.port}/api/traffic/meta", timeout=2,
            )
            if status == 200 and isinstance(payload, dict) and payload.get("is_simulated") is True:
                ready = True
                break
            time.sleep(0.3)
        startup_ms = round((time.perf_counter() - started) * 1000, 1)
        if not ready:
            return self.stage(
                "traffic-start", "failed",
                f"接口层 {self.args.timeout_startup:g}s 内未就绪（日志 {relative(log_file)}）",
                command=command, log=relative(log_file), startup_ms=startup_ms,
            )
        self.sampler = ProcessMemorySampler(self.traffic_process.pid)
        self.sampler.start()
        self.perception_process = None
        if self.args.with_perception_server:
            status = perception_data_status()
            if not status["ready"]:
                self.stage("perception-server", "blocked", status["reason"])
            else:
                perception_log = self.round_dir / "perception-server.log"
                perception_handler = perception_log.open("w", encoding="utf-8", newline="\n")
                self.perception_process = subprocess.Popen(
                    [sys.executable, str(PERCEPTION_SERVER), "--port", str(self.args.perception_port)],
                    cwd=str(ROOT), stdout=perception_handler, stderr=subprocess.STDOUT,
                )
                perception_ready = False
                deadline = time.time() + 20
                while time.time() < deadline:
                    code, _, _, _ = http_call(
                        f"http://127.0.0.1:{self.args.perception_port}/api/perception/health", timeout=2,
                    )
                    if code == 200:
                        perception_ready = True
                        break
                    if self.perception_process.poll() is not None:
                        break
                    time.sleep(0.3)
                self.stage(
                    "perception-server", "ok" if perception_ready else "failed",
                    None if perception_ready else "感知服务 20s 内未就绪",
                    command=[sys.executable, str(PERCEPTION_SERVER), "--port", str(self.args.perception_port)],
                    log=relative(perception_log), startup_ms=round((time.perf_counter() - started) * 1000, 1),
                )
        return self.stage("traffic-start", "ok", None, command=command, log=relative(log_file),
                          startup_ms=startup_ms)

    # ---- 端点自检

    def endpoint(self, name: str, method: str, path: str, body: dict | None = None,
                 expect: int = 200, required: bool = True) -> dict[str, Any]:
        status, payload, headers, elapsed = http_call(
            f"http://127.0.0.1:{self.args.port}{path}", method=method, body=body, timeout=self.args.timeout_http,
        )
        ok = status == expect
        item = {
            "name": name,
            "method": method,
            "path": path,
            "status": status,
            "expected": expect,
            "required": required,
            "elapsed_ms": elapsed,
            "ok": ok,
            "data_source": headers.get("x-traffic-data-source"),
            "top_keys": sorted(payload) if isinstance(payload, dict) else None,
            "is_simulated": payload.get("is_simulated") if isinstance(payload, dict) else None,
            "note": payload.get("note") if isinstance(payload, dict) else None,
        }
        self.endpoint_checks.append(item)
        return item

    def stage_endpoints(self) -> dict[str, Any]:
        log("      端点自检 ...")
        failures: list[str] = []
        for name, path in GET_ENDPOINTS:
            item = self.endpoint(name, "GET", path)
            log(f"        {name:14s} -> {item['status']}  ({item['elapsed_ms']} ms, "
                f"source={item['data_source']})")
            if not item["ok"]:
                failures.append(f"{name}={item['status']}")
        segments_payload = next((item for item in self.endpoint_checks if item["name"] == "segments"), None)
        segment_id = None
        segments_response = http_call(
            f"http://127.0.0.1:{self.args.port}/api/traffic/segments", timeout=self.args.timeout_http,
        )[1]
        if isinstance(segments_response, dict) and segments_response.get("segments"):
            segment_id = str(segments_response["segments"][0].get("segment_id"))
        if segment_id:
            for name, path in [
                ("segment-detail", f"/api/traffic/segments/{segment_id}"),
                ("segment-sources", f"/api/traffic/segments/{segment_id}/sources"),
                ("predict", f"/api/traffic/predict?segment_id={segment_id}&h=15"),
                ("ci-history", f"/api/traffic/ci-history?segment_id={segment_id}&points=6"),
            ]:
                item = self.endpoint(name, "GET", path)
                log(f"        {name:14s} -> {item['status']}  ({item['elapsed_ms']} ms)")
                if not item["ok"]:
                    failures.append(f"{name}={item['status']}")

        # POST /route/recommend：真网产物在场才要求 200
        engine_stage = next((stage for stage in self.stages if stage["stage"] == "engine-real"), None)
        engine_ok = bool(engine_stage and engine_stage["status"] == "ok")
        location_segment = segment_id or "SZ-001"
        route_item = self.endpoint(
            "route-recommend", "POST", "/api/traffic/route/recommend",
            body={"session_id": "S-demo-all", "location": {"segment_id": location_segment, "offset_m": 0}},
            expect=200, required=engine_ok,
        )
        log(f"        {'route-recommend':14s} -> {route_item['status']}  ({route_item['elapsed_ms']} ms)")
        if engine_ok and not route_item["ok"]:
            failures.append(f"route-recommend={route_item['status']}")
        locate_item = self.endpoint(
            "locate", "POST", "/api/traffic/locate", body={"session_id": "S-demo-all"},
            expect=200, required=engine_ok,
        )
        log(f"        {'locate':14s} -> {locate_item['status']}  ({locate_item['elapsed_ms']} ms)")
        if engine_ok and not locate_item["ok"]:
            failures.append(f"locate={locate_item['status']}")

        # 处置闭环写端点：只有当前快照派生出了告警才演示（否则如实跳过，不造假）
        alerts_response = http_call(
            f"http://127.0.0.1:{self.args.port}/api/traffic/alerts", timeout=self.args.timeout_http,
        )[1]
        alerts = alerts_response.get("alerts") if isinstance(alerts_response, dict) else None
        if alerts:
            alert = alerts[0]
            dispatch_item = self.endpoint(
                "plan-dispatch", "POST", "/api/traffic/plan/dispatch",
                body={"alert_id": alert["alert_id"], "channel": "情报板", "ratio_pct": 30, "operator": "演示脚本"},
            )
            ack_item = self.endpoint(
                "plan-ack", "POST", "/api/traffic/plan/ack",
                body={"alert_id": alert["alert_id"], "operator": "演示脚本", "action": "分流", "result": "已缓解"},
            )
            for item in (dispatch_item, ack_item):
                log(f"        {item['name']:14s} -> {item['status']}  ({item['elapsed_ms']} ms)")
                if not item["ok"]:
                    failures.append(f"{item['name']}={item['status']}")
            reset_item = self.endpoint("alerts-reset", "POST", "/api/traffic/alerts/reset")
            log(f"        {'alerts-reset':14s} -> {reset_item['status']}（演示后复位）")
        else:
            self.stage(
                "write-endpoints", "skipped",
                "当前快照没有 level≥3 的派生告警（缺感知/孪生运行指标），处置闭环写端点未演示（如实跳过）",
            )

        # SSE：读第一帧
        sse = {"ok": False, "event": None, "data_keys": []}
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{self.args.port}/api/traffic/stream",
                headers={"Accept": "text/event-stream"},
            )
            with urllib.request.urlopen(request, timeout=self.args.timeout_http) as response:
                for _ in range(6):
                    line = response.readline().decode("utf-8", "replace").rstrip("\r\n")
                    if line.startswith("event:"):
                        sse["event"] = line.split(":", 1)[1].strip()
                    elif line.startswith("data:"):
                        try:
                            sse["data_keys"] = sorted(json.loads(line.split(":", 1)[1].strip()))
                        except json.JSONDecodeError:
                            sse["data_keys"] = []
                    if sse["event"] and sse["data_keys"]:
                        break
            sse["ok"] = sse["event"] == "traffic_snapshot" and "is_simulated" in sse["data_keys"]
        except (urllib.error.URLError, OSError, ValueError) as error:
            sse["error"] = str(error)
        self.sse = sse
        if not sse["ok"]:
            failures.append("sse")
        log(f"        {'stream(SSE)':14s} -> {'200' if sse['ok'] else 'FAIL'}  event={sse.get('event')}")

        if failures:
            return self.stage("endpoint-check", "failed", "失败端点：" + "、".join(failures),
                              endpoints=len(self.endpoint_checks), failures=failures)
        return self.stage("endpoint-check", "ok", None,
                          endpoints=len(self.endpoint_checks),
                          segment_id=segment_id,
                          data_sources=sorted({item["data_source"] for item in self.endpoint_checks
                                               if item.get("data_source")}))

    # ---- 收尾

    def stop(self) -> None:
        # 先停采样再停进程：进程退出过程会回收工作集，退出瞬间的 RSS 不能当末值
        if self.sampler is not None:
            self.memory_samples = self.sampler.stop()
            self.sampler = None
        for name, process in (("traffic", self.traffic_process), ("perception", self.perception_process)):
            if process is None or process.poll() is not None:
                continue
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            log(f"        已停止 {name} 进程（pid={process.pid}）")
        self.traffic_process = None
        self.perception_process = None
        deadline = time.time() + 10
        while time.time() < deadline and not port_free(self.args.port):
            time.sleep(0.2)

    def finish(self) -> dict[str, Any]:
        duration = round(time.perf_counter() - self.started, 2)
        if self.sampler is not None:
            self.memory_samples = self.sampler.stop()
            self.sampler = None
        self.memory = memory_summary(self.memory_samples)
        artifacts = [
            file_info(ENGINE_REAL_ROUTES),
            file_info(ENGINE_REAL_LOG),
            file_info(PERCEPTION_VIDEO),
            file_info(DISPATCH_STATE),
        ]
        artifacts.extend(file_info(path) for path in sorted(self.round_dir.glob("*")))
        statuses = [stage["status"] for stage in self.stages]
        if "failed" in statuses:
            overall = "failed"
        elif "blocked" in statuses:
            overall = "blocked"
        else:
            overall = "ok"
        return {
            "round": self.index,
            "started_at": self.started_at,
            "finished_at": now_iso(),
            "duration_s": duration,
            "status": overall,
            "stages": self.stages,
            "endpoints": self.endpoint_checks,
            "sse": self.sse,
            "memory": self.memory,
            "artifacts": artifacts,
            "logs_dir": relative(self.round_dir),
        }


# ---------------------------------------------------------------- 汇总报告


def summarize(rounds: list[dict[str, Any]], args: argparse.Namespace,
              environment: dict[str, Any], preflight_result: dict[str, Any]) -> dict[str, Any]:
    # 本轮流程的必需步骤（跳过的不算失败；但 M1-6 判定另有完整清单，见下）
    required = []
    if not args.skip_engine:
        required.append("engine-real")
    if not args.skip_perception:
        required.append("perception-chain")
    required.extend(["traffic-start", "endpoint-check"])
    # M1-6 的完整必需步骤：跳过任一 → 本次只算接口层自检，M1-6 判「未评估」而非通过
    m1_6_steps = ["engine-real", "perception-chain", "traffic-start", "endpoint-check"]
    skipped_required = [
        name for name in m1_6_steps
        if (name == "engine-real" and args.skip_engine)
        or (name == "perception-chain" and args.skip_perception)
    ]

    blockers: list[str] = []
    round_rows = []
    for record in rounds:
        stage_map = {stage["stage"]: stage for stage in record["stages"]}
        # 必需阶段缺失（例如接口层没起来，端点自检根本没执行）也算失败，不能静默漏掉
        failed = [name for name in required
                  if stage_map.get(name, {}).get("status") not in ("ok", "skipped", "blocked")]
        blocked = [name for name in required
                   if stage_map.get(name, {}).get("status") == "blocked"]
        if failed:
            blockers.append(f"第 {record['round']} 轮失败：{'、'.join(failed)}")
        for name in blocked:
            reason = (stage_map.get(name) or {}).get("reason")
            blockers.append(f"第 {record['round']} 轮阻塞：{name}（{reason}）")
        round_rows.append({
            "round": record["round"],
            "status": record["status"],
            "duration_s": record["duration_s"],
            "failed": failed,
            "blocked": blocked,
            "memory": record["memory"],
        })

    memory_ends = [record["memory"].get("end_mb") for record in rounds]
    measured = [value for value in memory_ends if isinstance(value, (int, float))]
    memory_trend: dict[str, Any] = {"measured_rounds": len(measured), "end_mb_per_round": memory_ends}
    if len(measured) >= 2:
        growth = measured[-1] - measured[0]
        allowed = max(MEMORY_GROWTH_MIN_BYTES / (1024 * 1024), measured[0] * MEMORY_GROWTH_RATIO)
        memory_trend.update(
            growth_mb=round(growth, 2),
            allowed_growth_mb=round(allowed, 2),
            not_continuously_growing=growth <= allowed,
            rule="末轮起始 RSS − 首轮末 RSS ≤ max(20 MiB, 首轮末 RSS × 10%)；仅本机实测，不是性能验收",
        )
    else:
        memory_trend.update(not_continuously_growing=None,
                            note="内存样本不足（psutil 不可用或轮数不足），不判断趋势")

    all_m1_6_steps_ok = all(
        all(({stage["stage"]: stage for stage in record["stages"]}).get(name, {}).get("status") == "ok"
            for name in m1_6_steps)
        for record in rounds
    ) if rounds else False
    completed = len(rounds) == args.rounds
    memory_ok = memory_trend.get("not_continuously_growing")
    m1_6_evaluated = not skipped_required
    if skipped_required:
        # 独立审查修复：跳过 M1-6 必需步骤时只能判「未评估」，绝不能因为剩余步骤 ok 就 passed=true
        m1_6_passed = False
        verdict = "未评估（不适用）"
        reason = ("本次用 --skip-* 跳过了 M1-6 必需步骤：" + "、".join(skipped_required)
                  + "；这些参数只用于接口层自检，M1-6 要按完整链路（真网算路 + 感知链路 + 接口层 + 端点自检）判定")
    elif completed and all_m1_6_steps_ok and memory_ok is True:
        m1_6_passed = True
        verdict = "通过"
        reason = f"无人干预连跑 {len(rounds)} 轮全部必需步骤成功；内存未持续增长（实测见 memory_trend）"
    elif not completed:
        m1_6_passed = False
        verdict = "失败"
        reason = f"只完成 {len(rounds)}/{args.rounds} 轮"
    elif all_m1_6_steps_ok and memory_ok is None:
        m1_6_passed = False
        verdict = "未判定"
        reason = "步骤全部成功但内存无法测量（psutil 不可用），M1-6 要求「内存不持续增长」缺实测记录"
    elif all_m1_6_steps_ok:
        m1_6_passed = False
        verdict = "未通过"
        reason = f"步骤全部成功但内存趋势超出自定阈值（实测 {memory_trend.get('growth_mb')} MB）"
    else:
        m1_6_passed = False
        verdict = "阻塞/未通过"
        reason = "存在失败或阻塞步骤（见 blockers）"

    return {
        "schema_version": 1,
        "is_simulated": True,
        "note": "一键演示（C-4）自检报告：演示数据（模拟），只记录本次真跑结果，不是性能验收",
        "generated_at": now_iso(),
        "issue": "IKMS1I",
        "arguments": {
            "rounds": args.rounds,
            "skip_engine": args.skip_engine,
            "skip_perception": args.skip_perception,
            "with_perception_server": args.with_perception_server,
            "port": args.port,
        },
        "environment": environment,
        "preflight": preflight_result,
        "rounds": rounds,
        "round_summary": round_rows,
        "required_stages": required,
        "memory_trend": memory_trend,
        "blockers": sorted(set(blockers)),
        "m1_6": {
            "passed": m1_6_passed,
            "evaluated": m1_6_evaluated,
            "skipped": bool(skipped_required),
            "skipped_stages": skipped_required,
            "required_stages": m1_6_steps,
            "verdict": verdict,
            "reason": reason,
        },
        "exit_codes": {"0": "全部步骤成功", "2": "有阻塞项（如实记录，不算 M1-6 通过）",
                       "1": "有失败 / 异常"},
    }


def print_summary(report: dict[str, Any]) -> None:
    log("")
    log("=" * 100)
    log("一键演示（C-4）汇总")
    log("=" * 100)
    log(f"{'轮次':<6}{'状态':<10}{'总耗时(s)':<12}{'真网算路':<12}{'感知链路':<12}{'接口层':<10}{'端点自检':<10}内存(起→止 MB)")
    for record in report["rounds"]:
        stage_map = {stage["stage"]: stage for stage in record["stages"]}
        memory = record.get("memory") or {}
        log(
            f"{record['round']:<6}{record['status']:<10}{record['duration_s']:<12}"
            f"{(stage_map.get('engine-real') or {}).get('status', '-'):<12}"
            f"{(stage_map.get('perception-chain') or {}).get('status', '-'):<12}"
            f"{(stage_map.get('traffic-start') or {}).get('status', '-'):<10}"
            f"{(stage_map.get('endpoint-check') or {}).get('status', '-'):<10}"
            f"{memory.get('start_mb')}→{memory.get('end_mb')}"
        )
    log("")
    trend = report["memory_trend"]
    if trend.get("measured_rounds", 0) >= 2:
        log(f"内存趋势：{trend['end_mb_per_round']}，growth={trend.get('growth_mb')} MB，"
            f"not_continuously_growing={trend.get('not_continuously_growing')}")
    else:
        log(f"内存趋势：{trend.get('note') or '样本不足'}")
    for blocker in report["blockers"]:
        log(f"  ⚠ 阻塞/失败：{blocker}")
    log("")
    log(f"M1-6 结论：{report['m1_6']['verdict']} —— {report['m1_6']['reason']}")
    log(f"报告：{report.get('_report_path') or relative(DEFAULT_REPORT)}")
    log("口径：演示数据（模拟）；仅记录本次实测，缺前置如实标阻塞，不写「通过」。")


# ---------------------------------------------------------------- main


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="C-4 一键演示：环境检查 → 真网算路 → 感知链路 → 起接口层 → 端点自检 → 收尾",
        epilog=(
            "数据前置（gitignored，不在仓库）：感知链路需要 "
            "work/perception/data/monitor/<stream>/{meta.json,detections.json}（上游样本视频导出产物；"
            "放置路径与来源见 work/assembly/README.md §三）。数据不在场时感知链路如实标 blocked、"
            "不声明 M1-6 通过；数据在场时 --rounds 3 可跑出 M1-6 通过。"
        ),
    )
    parser.add_argument("--rounds", type=int, default=1,
                        help="连跑轮数（默认 1；M1-6 用 --rounds 3 无人干预连跑）")
    parser.add_argument("--port", type=int, default=8000, help="接口层端口（默认 8000）")
    parser.add_argument("--perception-port", type=int, default=8101, help="感知服务端口（默认 8101）")
    parser.add_argument("--with-perception-server", action="store_true",
                        help="额外起感知服务（work/perception/server.py，样本数据在场时）")
    parser.add_argument("--skip-engine", action="store_true",
                        help="跳过真网算路（只验接口层；跳过 M1-6 必需步骤 → M1-6 判「未评估」）")
    parser.add_argument("--skip-perception", action="store_true",
                        help="跳过感知链路（跳过 M1-6 必需步骤 → M1-6 判「未评估」）")
    parser.add_argument("--timeout-engine", type=float, default=180.0, help="真网算路超时（秒）")
    parser.add_argument("--timeout-perception", type=float, default=300.0, help="感知链路超时（秒）")
    parser.add_argument("--timeout-startup", type=float, default=25.0, help="接口层启动等待（秒）")
    parser.add_argument("--timeout-http", type=float, default=15.0, help="单次 HTTP 超时（秒）")
    parser.add_argument("--json-report", default=str(DEFAULT_REPORT),
                        help="汇总报告路径（默认 work/assembly/out/demo_all_report.json，gitignored）")
    parser.add_argument("--keep-going", action="store_true",
                        help="某轮失败后仍继续跑完剩余轮次（默认失败即停，不隐藏失败）")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.rounds < 1:
        log("参数错误：--rounds 必须 ≥ 1")
        return 2
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    log("=" * 100)
    log("C-4 一键演示（IKMS1I）· 演示数据（模拟）")
    log("=" * 100)
    environment = environment_snapshot()
    log(f"环境：{environment['os']} · Python {environment['python']} · "
        f"psutil={environment['psutil']} · git={environment['git_commit']}")
    preflight_result = preflight(args.port, args.with_perception_server)
    log(f"前置检查：{'通过' if not preflight_result['blockers'] else '有阻塞'}")
    for blocker in preflight_result["blockers"]:
        log(f"  ⚠ {blocker}")

    rounds: list[dict[str, Any]] = []
    for index in range(1, args.rounds + 1):
        log("")
        log(f"—— 第 {index}/{args.rounds} 轮 ——")
        demo = DemoRound(index, args, preflight_result)
        try:
            demo.stage_engine()
            demo.stage_perception()
            demo.stage_traffic_start()
            if demo.traffic_process is not None:
                demo.stage_endpoints()
                # 观察窗口：让内存采样在服务存活期间至少落几个点（演示脚本本身不判定达标）
                time.sleep(0.4)
        except Exception as error:  # noqa: BLE001 - 未预期异常也要如实落盘、不能假装成功
            demo.stage("unexpected-error", "failed", f"{type(error).__name__}: {error}")
        finally:
            demo.stop()
        record = demo.finish()
        rounds.append(record)
        log(f"  第 {index} 轮：{record['status']} · {record['duration_s']} s · 日志 {record['logs_dir']}")
        if record["status"] == "failed" and not args.keep_going:
            log("  本轮失败，按「失败即停」停止后续轮次（--keep-going 可继续跑完）")
            break

    report = summarize(rounds, args, environment, preflight_result)
    report_path = Path(args.json_report)
    if not report_path.is_absolute():
        report_path = ROOT / report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
    report["_report_path"] = relative(report_path)
    print_summary(report)

    failed = any(record["status"] == "failed" for record in rounds) or len(rounds) < args.rounds
    blocked = any(record["status"] == "blocked" for record in rounds)
    if failed:
        return 1
    if blocked or report["blockers"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
