#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""接口层快照性能自检：8 个刷新端点 × 两站的墙钟与字节数（Issue IKPFR4）。

为什么要有这个脚本：

`/api/traffic/*` 是「只读快照」接口层，前端大屏一轮刷新会**并发**打 8 个端点。
IKPFR4 之前，接口层每判断一条记录是否陈旧就重读一次 `stations/thresholds.json`
（广州南 708 段 × 3 轮 ≈ 2124 次文件读），`/overview` 实测 4 s 级、`/heat-matrix` 2 s 级，
而页面只等几百毫秒 —— 于是「数据没问题、页面就是转圈」。修复（文件读按 mtime+size
记忆化 / 每请求只装配一次快照 / 循环外取阈值 / 启动预热两站）是否真的落地，只看
「有没有改代码」是看不出来的：**必须有一组能重复跑、能卡阈值的数字**。

本脚本就做这一件事：打一遍，把每个端点的墙钟与字节数、每站一轮的总墙钟打出来；
`--assert` 时按验收线判达标（退出码非 0 = 未达标）。

用法（在仓库根执行）：

    python scripts/perf_snapshot.py                       # 探 http://127.0.0.1:8000
    python scripts/perf_snapshot.py --base-url http://127.0.0.1:8010 --assert
    python scripts/perf_snapshot.py --json                # 机器可读（便于对比两次提交）
    python scripts/perf_snapshot.py --rounds 5            # 多跑几轮取中位数（默认 3）

端点组（与前端 `DashboardView.refresh()` 同一组）：

    overview / segments / vehicles / alerts / factors / meta /
    heat-matrix?window=12&bucket=60 / thresholds

站点用请求头 `X-Station-Pack` 指定（Z / GZ，见 `work/twin/site-ranges.json`）。

两种计法，别混着看：

  · **单独墙钟**（端点一次只被一个请求打着）——回答「这个端点自己要多久」，
    单端点阈值卡的就是它；
  · **并发轮内**（8 个端点同时发，与页面一轮刷新同形）——回答「页面这一轮要等多久」，
    整轮阈值卡的是它。并发下单线程接口层要排队，同一个端点的「并发轮内」一定比
    「单独墙钟」大，这不是回归。

每站先跑一轮**预热**（不进统计）：接口层启动后有文件读缓存，第一次请求是冷身，
把它算进统计会让「有没有预热」盖住真正的回归。

--assert 阈值（IKPFR4 验收线，取各轮中位数）：

  · GZ `/overview` 单独墙钟    ≤ 0.30 s
  · GZ `/heat-matrix` 单独墙钟 ≤ 0.30 s
  · GZ 一轮 8 端点并发         ≤ 1.50 s
  · Z  一轮 8 端点并发         ≤ 0.92 s（不退化；Z 段数少，改前就在 0.3 s 级）

退出码：0 = 达标；1 = 未达标（或端点非 200）；2 = 参数错误（argparse 自己给）。

口径：只探本机回环，不碰外网；纯标准库；**只读**（全部 GET，不改任何数据 / 运行态）。
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

# Windows 控制台默认不是 UTF-8：先固定 stdout/stderr 编码，避免中文提示直接抛异常
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]

#: 显式绕开系统代理：有些机器把 HTTP_PROXY 配成全局代理，连 127.0.0.1 都被转出去，
#: 结果「本机服务明明起着」却探成超时。自检只探回环，必须直连。
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

STATION_HEADER = "X-Station-Pack"

#: 与前端 `DashboardView.refresh()` 同一组 8 个端点（顺序只影响打印，不影响并发）。
ENDPOINTS: tuple[tuple[str, str], ...] = (
    ("overview", "/api/traffic/overview"),
    ("segments", "/api/traffic/segments"),
    ("vehicles", "/api/traffic/vehicles"),
    ("alerts", "/api/traffic/alerts"),
    ("factors", "/api/traffic/factors"),
    ("meta", "/api/traffic/meta"),
    ("heat-matrix", "/api/traffic/heat-matrix?window=12&bucket=60"),
    ("thresholds", "/api/traffic/thresholds"),
)

#: 验收阈值（秒）。端点键卡「单独墙钟」；`round` 卡「一轮 8 端点并发」的墙钟。
LIMITS: dict[str, dict[str, float]] = {
    "GZ": {"overview": 0.30, "heat-matrix": 0.30, "round": 1.50},
    "Z": {"round": 0.92},
}

MODE_SOLO = "solo"
MODE_CONCURRENT = "concurrent"


@dataclass
class Sample:
    """一次请求的结果：墙钟 / 字节数 / HTTP 状态（`mode` 区分单独打还是并发轮里打）。"""

    key: str
    path: str
    mode: str
    seconds: float = 0.0
    bytes: int = 0
    status: int = 0
    error: str = ""


@dataclass
class StationResult:
    """一个站点的统计结果：两种计法的样本 + 每轮总墙钟。"""

    station: str
    round_seconds: list[float] = field(default_factory=list)
    solo: list[Sample] = field(default_factory=list)
    concurrent: list[Sample] = field(default_factory=list)

    @property
    def round_median(self) -> float:
        return statistics.median(self.round_seconds) if self.round_seconds else 0.0

    def samples(self) -> list[Sample]:
        return self.solo + self.concurrent

    def _median(self, key: str, mode: str, attr: str) -> float | int | None:
        values = [
            getattr(sample, attr) for sample in self.samples()
            if sample.key == key and sample.mode == mode and not sample.error
        ]
        if not values:
            return None
        median = statistics.median(values)
        return int(median) if attr == "bytes" else median

    def solo_seconds(self, key: str) -> float | None:
        return self._median(key, MODE_SOLO, "seconds")  # type: ignore[return-value]

    def concurrent_seconds(self, key: str) -> float | None:
        return self._median(key, MODE_CONCURRENT, "seconds")  # type: ignore[return-value]

    def bytes_median(self, key: str) -> int | None:
        return self._median(key, MODE_SOLO, "bytes")  # type: ignore[return-value]

    def failures(self) -> list[str]:
        problems: list[str] = []
        seen: set[str] = set()
        for sample in self.samples():
            if not sample.error or sample.key in seen:
                continue
            seen.add(sample.key)
            problems.append(f"/{sample.key}（{sample.mode}）{sample.error}")
        return problems


def fetch(base_url: str, station: str, key: str, path: str, timeout: float, mode: str) -> Sample:
    """GET 一个端点：返回墙钟 / 字节数 / 状态；4xx-5xx 与连接失败都记进 Sample，不抛。"""
    url = f"{base_url.rstrip('/')}{path}"
    request = urllib.request.Request(url, headers={STATION_HEADER: station})
    sample = Sample(key=key, path=path, mode=mode)
    started = time.perf_counter()
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            body = response.read()
            sample.seconds = time.perf_counter() - started
            sample.bytes = len(body)
            sample.status = response.status
    except urllib.error.HTTPError as exc:
        sample.seconds = time.perf_counter() - started
        sample.status = exc.code
        sample.error = f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        sample.seconds = time.perf_counter() - started
        sample.error = f"连接失败：{getattr(exc, 'reason', exc)}"
    return sample


def run_concurrent_round(base_url: str, station: str, timeout: float) -> tuple[float, list[Sample]]:
    """并发打一轮 8 个端点（与页面一轮刷新同形），返回 (整轮墙钟, 各端点样本)。"""
    with ThreadPoolExecutor(max_workers=len(ENDPOINTS)) as pool:
        started = time.perf_counter()
        samples = list(pool.map(
            lambda item: fetch(base_url, station, item[0], item[1], timeout, MODE_CONCURRENT),
            ENDPOINTS,
        ))
        return time.perf_counter() - started, samples


def run_solo_round(base_url: str, station: str, timeout: float) -> list[Sample]:
    """串行打一遍 8 个端点（一次只打一个）：量的是端点自己要多快。"""
    return [
        fetch(base_url, station, key, path, timeout, MODE_SOLO)
        for key, path in ENDPOINTS
    ]


def measure_station(
    base_url: str, station: str, rounds: int, timeout: float, warmup: bool,
) -> StationResult:
    """跑一个站点：预热（不进统计）→ rounds 轮（串行 + 并发各一遍）。"""
    result = StationResult(station=station)
    if warmup:
        run_solo_round(base_url, station, timeout)
        run_concurrent_round(base_url, station, timeout)
    for _ in range(max(1, rounds)):
        result.solo.extend(run_solo_round(base_url, station, timeout))
        elapsed, samples = run_concurrent_round(base_url, station, timeout)
        result.round_seconds.append(round(elapsed, 4))
        result.concurrent.extend(samples)
    return result


def evaluate(results: list[StationResult]) -> list[str]:
    """按 LIMITS 判定；返回未达标说明（空列表 = 全部达标）。"""
    problems: list[str] = []
    for result in results:
        limits = LIMITS.get(result.station)
        if limits is None:
            continue
        for key, limit in limits.items():
            if key == "round":
                if result.round_median > limit:
                    problems.append(
                        f"{result.station} 一轮 8 端点并发 {result.round_median:.3f} s > {limit:.2f} s"
                    )
                continue
            value = result.solo_seconds(key)
            if value is None:
                problems.append(f"{result.station} /{key} 没有拿到样本（请求失败）")
            elif value > limit:
                problems.append(
                    f"{result.station} /{key} 单独墙钟 {value:.3f} s > {limit:.2f} s"
                )
        problems.extend(f"{result.station} 请求失败 —— {item}" for item in result.failures())
    return problems


def render_text(results: list[StationResult], rounds: int) -> None:
    for result in results:
        print(f"站点 {result.station}（{STATION_HEADER}: {result.station}），{rounds} 轮中位数：")
        print(f"  {'端点':<14}{'单独墙钟':>11}{'并发轮内':>11}{'字节':>12}")
        for key, path in ENDPOINTS:
            solo = result.solo_seconds(key)
            concurrent = result.concurrent_seconds(key)
            size = result.bytes_median(key)
            if solo is None:
                print(f"  {key:<14}{'失败':>11}{'-':>11}{'-':>12}   {path}")
                continue
            concurrent_text = f"{concurrent:.3f}s" if concurrent is not None else "-"
            size_text = f"{size:,}" if size is not None else "-"
            print(f"  {key:<14}{solo:>10.3f}s{concurrent_text:>11}{size_text:>12}   {path}")
        totals = " / ".join(f"{value:.3f}" for value in result.round_seconds)
        print(f"  整轮 8 端点并发：{result.round_median:.3f} s（每轮 {totals}）")
        print()


def render_json(results: list[StationResult]) -> None:
    stations: dict[str, dict[str, object]] = {}
    for result in results:
        endpoints: dict[str, dict[str, object]] = {}
        for key, _path in ENDPOINTS:
            solo = result.solo_seconds(key)
            concurrent = result.concurrent_seconds(key)
            endpoints[key] = {
                "solo_seconds_median": None if solo is None else round(solo, 4),
                "concurrent_seconds_median": None if concurrent is None else round(concurrent, 4),
                "bytes_median": result.bytes_median(key),
            }
        stations[result.station] = {
            "round_seconds": result.round_seconds,
            "round_median_s": round(result.round_median, 4),
            "endpoints": endpoints,
            "failures": result.failures(),
        }
    print(json.dumps({
        "endpoints": [key for key, _path in ENDPOINTS],
        "limits": LIMITS,
        "stations": stations,
    }, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="接口层快照性能自检：8 个刷新端点 × 两站（Issue IKPFR4）"
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000",
                        help="接口层地址（默认 http://127.0.0.1:8000）")
    parser.add_argument("--stations", default="Z,GZ",
                        help="要测的站点包键（逗号分隔，默认 Z,GZ）")
    parser.add_argument("--rounds", type=int, default=3,
                        help="每站统计轮数（默认 3，取中位数）")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="单请求超时秒数（默认 30；改前 4 s 级慢端点也能测出来）")
    parser.add_argument("--no-warmup", action="store_true",
                        help="跳过统计前的预热（默认预热：把冷启动那一次排除在统计外）")
    parser.add_argument("--assert", dest="assert_limits", action="store_true",
                        help="按验收阈值判定，未达标返回码 1")
    parser.add_argument("--json", action="store_true", help="输出 JSON（便于对比两次提交）")
    args = parser.parse_args()

    stations = [item.strip().upper() for item in args.stations.split(",") if item.strip()]
    if not stations:
        print("参数错误：--stations 不能为空", file=sys.stderr)
        return 2

    results = [
        measure_station(args.base_url, station, args.rounds, args.timeout, not args.no_warmup)
        for station in stations
    ]

    if args.json:
        render_json(results)
    else:
        print(
            f"接口层：{args.base_url}（每轮 8 端点：先串行一遍量单端点，再并发一遍量整轮；"
            f"预热{'已跳过' if args.no_warmup else '已跑'}）"
        )
        print()
        render_text(results, args.rounds)

    problems = evaluate(results)
    if not args.assert_limits:
        return 0
    if problems:
        print("未达标：", file=sys.stderr)
        for problem in problems:
            print(f"  ✗ {problem}", file=sys.stderr)
        return 1
    print("达标：GZ /overview 与 /heat-matrix 单独墙钟、两站一轮 8 端点并发均在阈值内")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
