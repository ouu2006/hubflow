#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键启动接口层（可选：同时起感知服务），Ctrl+C 结束、子进程一起收掉。

用法（在仓库根）：

    python work/assembly/run_all.py                    # 起接口层 :8000
    python work/assembly/run_all.py --with-perception  # 同时起感知服务 :8101（work/perception/server.py 在场时）
    python work/assembly/run_all.py --check            # 只做启动前数据源解析（转调 traffic.py --check）

> 接口层只读快照：先有产物再看不空。产物从哪来见 `work/assembly/README.md`；
> 缺产物时接口会按三层回落 / 空壳 + note 如实返回（不 500）。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Windows 控制台默认不是 UTF-8：先固定 stdout/stderr 编码，避免中文 / 符号打印直接抛异常
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
TRAFFIC = ROOT / "work" / "assembly" / "traffic.py"
PERCEPTION = ROOT / "work" / "perception" / "server.py"
PERCEPTION_PORT = 8101


def wait_http(url: str, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.3)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="hubflow 一键启动：接口层 traffic.py（可选感知服务）")
    parser.add_argument("--host", default="127.0.0.1", help="接口层监听地址（默认 127.0.0.1）")
    parser.add_argument("--port", type=int, default=8000, help="接口层端口（默认 8000）")
    parser.add_argument("--with-perception", action="store_true",
                        help=f"同时起感知服务 :{PERCEPTION_PORT}（work/perception/server.py 在场时）")
    parser.add_argument("--check", action="store_true", help="只做启动前数据源解析，不启动服务")
    args = parser.parse_args()

    if args.check:
        return subprocess.call([sys.executable, str(TRAFFIC), "--check"], cwd=str(ROOT))

    processes: list[tuple[str, subprocess.Popen]] = []
    try:
        traffic_command = [sys.executable, str(TRAFFIC), "--host", args.host, "--port", str(args.port)]
        print("→ 启动接口层：" + " ".join(traffic_command), flush=True)
        processes.append(("接口层", subprocess.Popen(traffic_command, cwd=str(ROOT))))

        if args.with_perception:
            if PERCEPTION.is_file():
                perception_command = [sys.executable, str(PERCEPTION), "--port", str(PERCEPTION_PORT)]
                print("→ 启动感知服务：" + " ".join(perception_command), flush=True)
                processes.append(("感知服务", subprocess.Popen(perception_command, cwd=str(ROOT))))
            else:
                print(f"（--with-perception：{PERCEPTION.relative_to(ROOT)} 不在场，跳过）", flush=True)

        probe_host = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
        traffic_ready = wait_http(f"http://{probe_host}:{args.port}/api/traffic/meta")
        perception_ready = None
        if args.with_perception and PERCEPTION.is_file():
            perception_ready = wait_http(f"http://127.0.0.1:{PERCEPTION_PORT}/api/perception/health")
        print()
        if traffic_ready:
            print(f"✅ 接口层就绪：http://{probe_host}:{args.port}/api/traffic/segments")
            print(f"   OpenAPI 文档：http://{probe_host}:{args.port}/docs")
        else:
            print("❌ 接口层 20s 内未就绪，请检查上面的日志")
        if perception_ready is not None:
            print(("✅" if perception_ready else "❌") +
                  f" 感知服务：http://127.0.0.1:{PERCEPTION_PORT}/api/perception/streams")
        if not traffic_ready:
            return 1
        print("\nCtrl+C 结束（两个服务会一起停）。", flush=True)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n收到 Ctrl+C，正在停止 ...", flush=True)
        return 0
    finally:
        for name, process in processes:
            process.terminate()
        for name, process in processes:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
