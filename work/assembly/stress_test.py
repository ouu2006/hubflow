#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C-5 压测脚本（IKMS1I）：起接口层 → 多并发打只读端点 → 3 轮统计 → 生成实测报告。

**口径（不造假）**：
- 只记录本次在本机真跑的实测数字（启动耗时 / 各端点 P50·P95 / 错误数 / 进程内存曲线）；
- **不判定「性能达标」**：报告只给实测值 + 复现命令；是否达标由验收方按手册目标值判定；
- 失败 / 超时如实计数并列明细，不删日志、不隐藏错误。

跑法（在仓库根；先 `git add` 再提交报告前请自行确认）：

    python work/assembly/stress_test.py                      # 3 轮 × 14 端点 × 20 次 × 8 并发
    python work/assembly/stress_test.py --rounds 3 --concurrency 8 --requests-per-endpoint 20
    python work/assembly/stress_test.py --port 8000 --markdown work/assembly/压测报告.md

输出：
- `work/assembly/out/stress_test_report.json`（原始数据，gitignored，不提交）
- `work/assembly/压测报告.md`（实测报告；本脚本每次运行会**重写**它）

退出码：0 = 本次运行无错误；1 = 有错误 / 超时（如实记录后退出，不伪装通过）；2 = 环境阻塞（起不来服务 / 端口被占）。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import socket
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

# Windows 控制台默认不是 UTF-8：先固定 stdout/stderr 编码
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[2]
ASSEMBLY = ROOT / "work" / "assembly"
TRAFFIC = ASSEMBLY / "traffic.py"
DEFAULT_MARKDOWN = ASSEMBLY / "压测报告.md"
DEFAULT_JSON = ASSEMBLY / "out" / "stress_test_report.json"
STALE_AFTER_S = 120.0

#: 只读端点清单（写端点会改持久化运行态，本报告不压写端点，见报告「覆盖范围」）
ENDPOINTS = [
    ("meta", "/api/traffic/meta"),
    ("overview", "/api/traffic/overview"),
    ("segments", "/api/traffic/segments"),
    ("segment-detail", "/api/traffic/segments/{sid}"),
    ("segment-sources", "/api/traffic/segments/{sid}/sources"),
    ("network", "/api/traffic/network"),
    ("thresholds", "/api/traffic/thresholds"),
    ("context", "/api/traffic/context"),
    ("factors", "/api/traffic/factors"),
    ("assimilation", "/api/traffic/assimilation"),
    ("alerts", "/api/traffic/alerts"),
    ("heat-matrix", "/api/traffic/heat-matrix?window=12&bucket=60"),
    ("plan-audit", "/api/traffic/plan/audit?limit=50"),
    ("vehicles", "/api/traffic/vehicles"),
]


def log(message: str) -> None:
    print(message, flush=True)


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


def http_call(base: str, path: str, timeout: float = 15.0) -> dict[str, Any]:
    """单次 GET；返回 {status, latency_ms, error, is_simulated, data_source}。"""
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(base + path, timeout=timeout) as response:
            payload = decode(response.read())
            headers = {str(key).lower(): str(value) for key, value in dict(response.headers).items()}
            return {
                "status": response.status,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "error": None,
                "is_simulated": payload.get("is_simulated") if isinstance(payload, dict) else None,
                "data_source": headers.get("x-traffic-data-source"),
            }
    except urllib.error.HTTPError as error:
        return {
            "status": error.code,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": f"HTTP {error.code}",
        }
    except (urllib.error.URLError, OSError, TimeoutError) as error:
        return {
            "status": 0,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": str(error),
        }


def percentile(values: list[float], pct: float) -> float | None:
    """nearest-rank 百分位（样本少时也稳定，不插值编点）。"""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, math.ceil(pct / 100 * len(ordered)) - 1))
    return round(ordered[rank], 2)


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def git_output(*args: str) -> str | None:
    try:
        process = subprocess.run(
            ["git", *args], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (process.stdout or "").strip() or None


def cpu_model() -> str:
    text = platform.processor() or ""
    if not text and os.name == "nt":
        try:
            output = subprocess.run(
                ["wmic", "cpu", "get", "name"], capture_output=True, text=True, encoding="utf-8", timeout=15,
            ).stdout
            lines = [line.strip() for line in output.splitlines() if line.strip() and line.strip() != "Name"]
            text = lines[0] if lines else text
        except (OSError, subprocess.TimeoutExpired):
            pass
    return text or platform.machine()


class MemorySampler(threading.Thread):
    """采样接口层进程 RSS（psutil 可用时）；不可用时 samples 为空并在报告里写明。"""

    def __init__(self, pid: int, interval_s: float = 0.2) -> None:
        super().__init__(daemon=True)
        self.pid = pid
        self.interval_s = interval_s
        self.samples: list[float] = []
        # 不能叫 _stop（覆盖 Thread._stop()）
        self._stop_event = threading.Event()

    def run(self) -> None:  # pragma: no cover
        if psutil is None:
            return
        try:
            process = psutil.Process(self.pid)
        except Exception:  # noqa: BLE001
            return
        while not self._stop_event.is_set():
            try:
                self.samples.append(round(process.memory_info().rss / (1024 * 1024), 2))
            except Exception:  # noqa: BLE001
                break
            self._stop_event.wait(self.interval_s)

    def stop(self) -> list[float]:
        self._stop_event.set()
        self.join(timeout=3)
        return self.samples


def start_traffic(port: int, log_path: Path) -> tuple[subprocess.Popen, float]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = log_path.open("w", encoding="utf-8", newline="\n")
    command = [sys.executable, str(TRAFFIC), "--port", str(port)]
    started = time.perf_counter()
    process = subprocess.Popen(command, cwd=str(ROOT), stdout=handler, stderr=subprocess.STDOUT)
    deadline = time.time() + 25
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"traffic.py 启动即退出（日志 {relative(log_path)}）")
        result = http_call(f"http://127.0.0.1:{port}", "/api/traffic/meta", timeout=2)
        if result["status"] == 200:
            return process, round((time.perf_counter() - started) * 1000, 1)
        time.sleep(0.2)
    process.terminate()
    raise RuntimeError(f"traffic.py 25s 内未就绪（日志 {relative(log_path)}）")


def resolve_segment_id(base: str) -> str | None:
    result = http_call(base, "/api/traffic/segments")
    if result["status"] != 200:
        return None
    # 重新取一次 payload（http_call 只回状态摘要，这里单独读）
    try:
        with urllib.request.urlopen(base + "/api/traffic/segments", timeout=15) as response:
            payload = decode(response.read())
    except (urllib.error.URLError, OSError):
        return None
    segments = payload.get("segments") if isinstance(payload, dict) else None
    return str(segments[0]["segment_id"]) if segments else None


def run_round(round_index: int, base: str, paths: list[tuple[str, str]], concurrency: int,
              requests_per_endpoint: int, port: int, lock: threading.Lock,
              pid: int) -> dict[str, Any]:
    sampler = MemorySampler(pid)
    sampler.start()
    lock.acquire()
    try:
        time.sleep(0.1)  # 让采样至少落一个起点
    finally:
        lock.release()
    tasks = [(name, path) for name, path in paths for _ in range(requests_per_endpoint)]
    records: list[dict[str, Any]] = []
    round_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(http_call, base, path): (name, path) for name, path in tasks}
        for future in as_completed(futures):
            name, path = futures[future]
            try:
                result = future.result()
            except Exception as error:  # noqa: BLE001 - 未预期异常也算错误，不吞
                result = {"status": 0, "latency_ms": None, "error": f"{type(error).__name__}: {error}"}
            result.update({"endpoint": name, "path": path})
            records.append(result)
    duration = round(time.perf_counter() - round_started, 3)
    memory = sampler.stop()
    rss_start = memory[0] if memory else None
    rss_end = memory[-1] if memory else None
    return {
        "round": round_index,
        "requests": len(records),
        "duration_s": duration,
        "rps": round(len(records) / duration, 1) if duration > 0 else None,
        "errors": sum(1 for record in records if record.get("error") or record.get("status") != 200),
        "memory": {
            "samples": len(memory),
            "start_mb": rss_start,
            "end_mb": rss_end,
            "max_mb": round(max(memory), 2) if memory else None,
            "growth_mb": round(rss_end - rss_start, 2) if memory and rss_end is not None else None,
            "note": None if memory else "psutil 不可用或采样失败：内存未测量（不编数字）",
        },
        "records": records,
    }


def endpoint_statistics(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(record["endpoint"], []).append(record)
    rows = []
    for name, items in grouped.items():
        latencies = [item["latency_ms"] for item in items if isinstance(item.get("latency_ms"), (int, float))]
        errors = sum(1 for item in items if item.get("error") or item.get("status") != 200)
        rows.append({
            "endpoint": name,
            "path": items[0]["path"],
            "requests": len(items),
            "errors": errors,
            "p50_ms": percentile(latencies, 50),
            "p95_ms": percentile(latencies, 95),
            "min_ms": round(min(latencies), 2) if latencies else None,
            "max_ms": round(max(latencies), 2) if latencies else None,
            "mean_ms": round(statistics.fmean(latencies), 2) if latencies else None,
            "data_sources": sorted({str(item.get("data_source")) for item in items if item.get("data_source")}),
        })
    rows.sort(key=lambda row: (-(row["p95_ms"] or 0), row["endpoint"]))
    return rows


def environment_block() -> dict[str, Any]:
    memory_total = None
    if psutil is not None:
        try:
            memory_total = psutil.virtual_memory().total
        except Exception:  # noqa: BLE001
            pass
    return {
        "is_simulated": True,
        "os": platform.platform(),
        "machine": platform.machine(),
        "cpu": cpu_model(),
        "cpu_logical": os.cpu_count(),
        "memory_total_bytes": memory_total,
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "psutil": getattr(psutil, "__version__", None),
        "git_commit": git_output("rev-parse", "--short", "HEAD"),
        "git_branch": git_output("rev-parse", "--abbrev-ref", "HEAD"),
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines: list[str] = []
    lines.append("# 压测报告（C-5 · IKMS1I）\n")
    lines.append("> **演示数据（模拟）**：本报告是**本机实测**记录，不是性能验收结论；"
                 "被测接口返回的全部是演示数据（`is_simulated: true`）。\n")
    lines.append(f"- 生成时间：{report['generated_at']}")
    lines.append(f"- 命令：`{report['command']}`")
    lines.append(f"- 原始数据：`{report['json_path']}`（gitignored，不入库）")
    lines.append("")
    lines.append("## 一、被测环境（实测）\n")
    environment = report["environment"]
    lines.append("| 项 | 实测值 |")
    lines.append("|---|---|")
    lines.append(f"| 操作系统 | {environment['os']} |")
    lines.append(f"| CPU | {environment['cpu']}（逻辑核 {environment['cpu_logical']}） |")
    memory_total = environment.get("memory_total_bytes")
    lines.append(f"| 内存 | {round(memory_total / (1024 ** 3), 1) if memory_total else '未测得'} GiB |")
    lines.append(f"| Python | {environment['python']}（psutil {environment['psutil']}） |")
    lines.append(f"| 代码版本 | `{environment['git_commit']}`（`{environment['git_branch']}`） |")
    lines.append(f"| 接口层 | `work/assembly/traffic.py --port {report['port']}` |")
    lines.append("")
    lines.append("## 二、压测方法\n")
    method = report["method"]
    lines.append(f"- 轮次：**{method['rounds']} 轮**；每轮每个端点 **{method['requests_per_endpoint']}** 次请求；"
                 f"并发 **{method['concurrency']}**；单请求超时 {method['timeout_s']} s。")
    lines.append(f"- 每轮请求数：{method['requests_per_round']}；总请求数：{method['requests_total']}。")
    lines.append("- 端点：只读 GET（写端点会改 `work/assembly/data/dispatch.json` 持久化运行态，本报告不压写端点，"
                 "写端点的演示验证见 `自检记录-IKMS1H.md`）。")
    lines.append("- 时延口径：单次 HTTP 请求的端到端耗时（客户端计时，含连接 / 序列化）；"
                 "P50 / P95 用 nearest-rank 百分位（不插值、不补点）。")
    lines.append("- 内存：`psutil` 采接口层进程 RSS（约 0.2 s 一次）；内存曲线见第五节，**未做持续增长判定**。")
    lines.append("")
    lines.append("## 三、启动耗时（实测）\n")
    lines.append(f"- 接口层启动到 `/api/traffic/meta` 首次 200：**{report['startup_ms']} ms**"
                 f"（计一次；含 Python 进程拉起 + uvicorn 就绪）")
    lines.append("")
    lines.append("## 四、各端点实测时延（全部轮次合并统计）\n")
    lines.append("| 端点 | 请求数 | 错误数 | P50 (ms) | P95 (ms) | min (ms) | max (ms) | 均值 (ms) | 数据源（响应头） |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for row in report["endpoints"]:
        lines.append(
            f"| `{row['endpoint']}` | {row['requests']} | {row['errors']} | {row['p50_ms']} | {row['p95_ms']} | "
            f"{row['min_ms']} | {row['max_ms']} | {row['mean_ms']} | "
            f"{', '.join(row['data_sources']) or '—'} |"
        )
    lines.append("")
    lines.append("整体：")
    lines.append(f"- 总请求 **{report['totals']['requests']}**，错误 **{report['totals']['errors']}**，"
                 f"错误率 **{report['totals']['error_rate_pct']}%**")
    lines.append(f"- 全端点合并 P50 **{report['totals']['p50_ms']} ms** / P95 **{report['totals']['p95_ms']} ms**"
                 f"（客户端计时，本机回环）")
    lines.append("")
    lines.append("## 五、每轮汇总与内存记录\n")
    lines.append("| 轮次 | 请求数 | 错误数 | 耗时 (s) | RPS | RSS 起始 (MB) | RSS 结束 (MB) | RSS 峰值 (MB) | 采样点 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for row in report["rounds"]:
        memory = row["memory"]
        lines.append(
            f"| {row['round']} | {row['requests']} | {row['errors']} | {row['duration_s']} | {row['rps']} | "
            f"{memory['start_mb']} | {memory['end_mb']} | {memory['max_mb']} | {memory['samples']} |"
        )
    lines.append("")
    memory_notes = [row["memory"]["note"] for row in report["rounds"] if row["memory"].get("note")]
    if memory_notes:
        lines.append(f"- 内存口径说明：{memory_notes[0]}")
    else:
        lines.append("- 内存口径：接口层进程 RSS（psutil），采自每轮压测期间；"
                     "轮内起止差与跨轮峰值见上表，**本报告不对「是否持续增长」下结论**，"
                     "M1-6 的判定由一键演示脚本 `demo_all.py` 的 3 轮记录承担。")
    lines.append("")
    lines.append("## 六、错误明细\n")
    errors = report["error_samples"]
    if not errors:
        lines.append("- 本次运行 **0 个错误 / 超时**（如实记录：无）。")
    else:
        lines.append(f"- 共 **{report['totals']['errors']}** 个错误 / 超时；明细（最多列 20 条，全部见原始 JSON）：")
        lines.append("")
        lines.append("| # | 端点 | 状态 | 耗时 (ms) | 错误 |")
        lines.append("|---|---|---|---|---|")
        for index, item in enumerate(errors[:20], 1):
            lines.append(f"| {index} | `{item['endpoint']}` | {item['status']} | {item['latency_ms']} | "
                         f"{str(item['error'])[:120]} |")
    lines.append("")
    lines.append("## 七、结论边界（**不越界**）\n")
    lines.append("- 本报告只陈述**本次实测数字**，**不判定「性能达标 / 不达标」**；"
                 "验收方如需判定，按手册 13.3 的 demo 目标值（如 `route/recommend` P95 ≤ 3000 ms【demo 目标值】）"
                 "自行比对，并注意本次是**单机回环、只读端点、演示数据**的测量。")
    lines.append("- 未覆盖：写端点（dispatch / ack / factors / scenario）的并发写入；多进程 / 多 worker；"
                 "真实网络链路；前端渲染性能。上述属二期或专项压测范围。")
    lines.append("- 本机数字随硬件、系统负载、运行轮次变化，不构成对外承诺。")
    lines.append("")
    lines.append("## 八、复现\n")
    lines.append("```bash")
    lines.append(report["command"])
    lines.append("```")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="C-5 压测：起接口层 → 多并发只读端点 → 3 轮实测报告")
    parser.add_argument("--rounds", type=int, default=3, help="轮数（默认 3）")
    parser.add_argument("--concurrency", type=int, default=8, help="并发线程数（默认 8）")
    parser.add_argument("--requests-per-endpoint", type=int, default=20,
                        help="每轮每个端点请求次数（默认 20）")
    parser.add_argument("--timeout", type=float, default=15.0, help="单请求超时秒（默认 15）")
    parser.add_argument("--port", type=int, default=8000, help="接口层端口（默认 8000）")
    parser.add_argument("--markdown", default=str(DEFAULT_MARKDOWN),
                        help="报告路径（默认 work/assembly/压测报告.md）")
    parser.add_argument("--json", default=str(DEFAULT_JSON),
                        help="原始 JSON 路径（默认 work/assembly/out/stress_test_report.json）")
    args = parser.parse_args()
    if args.rounds < 1 or args.concurrency < 1 or args.requests_per_endpoint < 1:
        print("参数错误：rounds / concurrency / requests-per-endpoint 都必须 ≥ 1", file=sys.stderr)
        return 2
    if not port_free(args.port):
        print(f"环境阻塞：端口 {args.port} 被占用，先停掉其它接口层实例", file=sys.stderr)
        return 2

    markdown_path = Path(args.markdown)
    if not markdown_path.is_absolute():
        markdown_path = ROOT / markdown_path
    json_path = Path(args.json)
    if not json_path.is_absolute():
        json_path = ROOT / json_path
    json_path.parent.mkdir(parents=True, exist_ok=True)

    command = ("python work/assembly/stress_test.py "
               f"--rounds {args.rounds} --concurrency {args.concurrency} "
               f"--requests-per-endpoint {args.requests_per_endpoint} --port {args.port}")
    log(f"C-5 压测（演示数据（模拟））· {command}")
    base = f"http://127.0.0.1:{args.port}"
    environment = environment_block()
    log(f"环境：{environment['os']} · {environment['cpu']} · Python {environment['python']} · "
        f"git={environment['git_commit']}")

    log("启动接口层 ...")
    try:
        process, startup_ms = start_traffic(args.port, ROOT / "work/assembly/out" / "stress_traffic.log")
    except RuntimeError as error:
        print(f"环境阻塞：{error}", file=sys.stderr)
        return 2
    log(f"  就绪：{startup_ms} ms")
    lock = threading.Lock()
    try:
        segment_id = resolve_segment_id(base)
        paths = [(name, path.replace("{sid}", segment_id or "")) for name, path in ENDPOINTS if
                 "{sid}" not in path or segment_id]
        if segment_id is None:
            log("  警告：拿不到路段号，跳过 segments/{id} 类端点（如实记录，不补数据）")
        log(f"端点 {len(paths)} 个；每轮每端点 {args.requests_per_endpoint} 次 × {args.concurrency} 并发")
        rounds: list[dict[str, Any]] = []
        all_records: list[dict[str, Any]] = []
        for index in range(1, args.rounds + 1):
            record = run_round(index, base, paths, args.concurrency, args.requests_per_endpoint,
                               args.port, lock, process.pid)
            all_records.extend(record["records"])
            del record["records"]
            rounds.append(record)
            log(f"  第 {index} 轮：{record['requests']} 请求 · {record['duration_s']} s · "
                f"{record['rps']} RPS · 错误 {record['errors']} · "
                f"RSS {record['memory']['start_mb']}→{record['memory']['end_mb']} MB")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        log("接口层已停止")

    statistics_rows = endpoint_statistics(all_records)
    latencies = [item["latency_ms"] for item in all_records if isinstance(item.get("latency_ms"), (int, float))]
    errors = [item for item in all_records if item.get("error") or item.get("status") != 200]
    total_requests = len(all_records)
    report = {
        "schema_version": 1,
        "is_simulated": True,
        "issue": "IKMS1I",
        "generated_at": now_iso(),
        "command": command,
        "port": args.port,
        "json_path": relative(json_path),
        "environment": environment,
        "method": {
            "rounds": args.rounds,
            "concurrency": args.concurrency,
            "requests_per_endpoint": args.requests_per_endpoint,
            "requests_per_round": len(paths) * args.requests_per_endpoint,
            "requests_total": total_requests,
            "timeout_s": args.timeout,
            "percentile": "nearest-rank（不插值）",
            "endpoints": [{"name": name, "path": path} for name, path in paths],
        },
        "startup_ms": startup_ms,
        "endpoints": statistics_rows,
        "totals": {
            "requests": total_requests,
            "errors": len(errors),
            "error_rate_pct": round(len(errors) / total_requests * 100, 3) if total_requests else None,
            "p50_ms": percentile(latencies, 50),
            "p95_ms": percentile(latencies, 95),
        },
        "rounds": rounds,
        "error_samples": [
            {"endpoint": item["endpoint"], "path": item["path"], "status": item["status"],
             "latency_ms": item["latency_ms"], "error": item.get("error")}
            for item in errors[:50]
        ],
        "notes": [
            "本报告只记录本机实测数字，不判定性能达标；是否达标由验收方按手册目标值判定。",
            "只压只读 GET 端点；写端点会改持久化运行态，未纳入本报告。",
            "所有被测响应 is_simulated=true，不是真实业务数据。",
        ],
    }
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8", newline="\n")
    write_markdown(report, markdown_path)
    log(f"报告：{relative(markdown_path)}")
    log(f"原始数据：{relative(json_path)}")
    log(f"总请求 {total_requests} · 错误 {len(errors)} · P50 {report['totals']['p50_ms']} ms · "
        f"P95 {report['totals']['p95_ms']} ms")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
