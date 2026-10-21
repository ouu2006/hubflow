#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hubflow 环境自检：三个进程齐了没有（Issue IKP58M）。

为什么要有：页面报「连接不上」时，第一步该回答的不是「前端哪里写错了」，而是
「8000 / 8101 / 5173 到底有没有在跑」。本脚本只做这一件事——逐项打勾/打叉，
**缺哪项直接把该敲的命令打出来**，退出码区分「全绿」与「有缺」。

用法（在仓库根执行）：

    python scripts/env_check.py                 # 人类可读：✓ / ✗ + 该敲的命令
    python scripts/env_check.py --json          # 机器可读：JSON（便于脚本/CI 判断）
    python scripts/env_check.py --self-test     # 反向自测：错端口必须判失败、临时服务必须判通过
    python scripts/env_check.py --traffic-port 8010   # 临时改端口探（自测/排障用）

退出码：0 = 三项全通；1 = 有缺；2 = 参数错误（argparse 自己给）。

口径：只探本机回环 127.0.0.1，不碰外网；纯标准库，Windows / Linux 都能跑。
「端口有 HTTP 200」才算通过——端口被别的服务占着同样会让本仓库的前端连不上，
所以这里不把「端口有人听」当成「服务对了」。
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

# Windows 控制台默认不是 UTF-8：先固定 stdout/stderr 编码，避免 ✓ / ✗ / 中文提示直接抛异常
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]

#: 显式绕开系统代理：有些机器把 HTTP_PROXY 配成全局代理，连 127.0.0.1 都会被转出去，
#: 结果「本机服务明明起着」却探成超时。自检只探回环，必须直连。
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@dataclass
class Check:
    """一项端口检查。`command` 是失败时给使用者直接照抄的命令。"""

    key: str
    label: str
    url: str
    command: str
    ok: bool = False
    detail: str = ""


def probe(url: str, timeout: float = 1.5) -> tuple[bool, str]:
    """GET 一个本机 URL：**HTTP 200 才算通过**。

    返回 (ok, 可读细节)。连接失败 / 超时 / 非 200 都算失败——端口被别的进程占着
    与「服务没起」对使用者的后果相同（页面照样连不上），不能打勾。
    """
    try:
        with _OPENER.open(url, timeout=timeout) as response:
            status = response.status
            response.read(256)  # 只读一小段，够确认响应体不是空壳即可
        if status == 200:
            return True, "HTTP 200"
        return False, f"端口有响应但不是预期服务（HTTP {status}）"
    except urllib.error.HTTPError as exc:
        return False, f"端口有响应但不是预期服务（HTTP {exc.code}）"
    except urllib.error.URLError as exc:
        return False, f"连接失败：{exc.reason}"
    except (TimeoutError, socket.timeout):
        return False, f"连接超时（{timeout:.1f}s）"
    except OSError as exc:
        return False, f"连接失败：{exc}"


def build_checks(host: str, traffic_port: int, perception_port: int, frontend_port: int) -> list[Check]:
    """三项检查：接口层 / 感知服务 / 前端 dev server。命令一律按「仓库根执行」写。"""
    return [
        Check(
            key="traffic",
            label="接口层 traffic.py",
            url=f"http://{host}:{traffic_port}/api/traffic/health",
            command=f"python work/assembly/traffic.py --port {traffic_port}",
        ),
        Check(
            key="perception",
            label="感知演示服务",
            url=f"http://{host}:{perception_port}/api/perception/health",
            command=f"python work/perception/server.py --port {perception_port}",
        ),
        Check(
            key="frontend",
            label="前端 dev server",
            url=f"http://{host}:{frontend_port}/",
            command=(
                f"cd work/frontend/ui-vue && npm run dev"
                f"（mock；要连后端用 npm run dev:remote；固定端口 {frontend_port}）"
            ),
        ),
    ]


def run_checks(checks: list[Check], timeout: float) -> list[Check]:
    for check in checks:
        ok, detail = probe(check.url, timeout=timeout)
        check.ok = ok
        check.detail = detail
    return checks


def exit_code(checks: list[Check]) -> int:
    return 0 if all(check.ok for check in checks) else 1


def print_human(checks: list[Check], host: str) -> None:
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"hubflow 环境自检 · {host} · {stamp}")
    for check in checks:
        mark = "✓" if check.ok else "✗"
        print(f"  [{mark}] {check.label:<14} {check.url}  {check.detail}")
        if not check.ok:
            print(f"       ↳ 起它：{check.command}")
    passed = sum(1 for check in checks if check.ok)
    print()
    if passed == len(checks):
        print(f"结果：{passed}/{len(checks)} 全绿（前端与两个后端都在）。")
    else:
        print(f"结果：{passed}/{len(checks)} 通过，{len(checks) - passed} 项缺失。按上面 ↳ 的命令补齐。")
        print("      只起前端（mock 模式）时 8000 / 8101 打叉是预期行为；remote 模式必须两项都起。")


def self_test() -> int:
    """反向自测：错端口必须失败，真服务必须通过，失败项必须让退出码非 0。"""
    failures: list[str] = []

    # ① 找一个当前没人监听的端口（先 bind 拿到系统分配的端口，再马上关掉）
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        closed_port = sock.getsockname()[1]
    ok, detail = probe(f"http://127.0.0.1:{closed_port}/", timeout=0.8)
    if ok:
        failures.append(f"① 关闭端口 {closed_port} 竟被判为通过（{detail}）")
    print(f"[{'✓' if not ok else '✗'}] 自测①：关闭端口必须判失败（{detail}）")

    # ② 临时起一个最小 HTTP 服务，必须判通过（证明探测不是一律返回失败）
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Thread

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler 的约定名
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):  # noqa: ANN002 - 静音访问日志
            pass

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        ok_live, detail_live = probe(f"http://127.0.0.1:{server.server_port}/", timeout=2.0)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    if not ok_live:
        failures.append(f"② 临时 HTTP 服务未通过探测（{detail_live}）")
    print(f"[{'✓' if ok_live else '✗'}] 自测②：临时 HTTP 服务必须判通过（{detail_live}）")

    # ③ 失败项必须让退出码非 0（错端口的检查项）
    fake = [Check("fake", "故意打错端口", f"http://127.0.0.1:{closed_port}/", "echo 不该执行", ok=False, detail="自测")]
    if exit_code(fake) == 0:
        failures.append("③ 有失败项时退出码仍是 0")
    print(f"[{'✓' if exit_code(fake) != 0 else '✗'}] 自测③：有失败项时退出码必须非 0")

    if failures:
        print()
        for item in failures:
            print(f"自测失败：{item}")
        return 1
    print()
    print("自测全过：错端口会失败、真服务会通过、失败会体现在退出码。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="hubflow 环境自检：探 8000 / 8101 / 5173")
    parser.add_argument("--host", default="127.0.0.1", help="探测地址（默认 127.0.0.1）")
    parser.add_argument("--traffic-port", type=int, default=8000, help="接口层端口（默认 8000）")
    parser.add_argument("--perception-port", type=int, default=8101, help="感知服务端口（默认 8101）")
    parser.add_argument("--frontend-port", type=int, default=5173, help="前端 dev server 端口（默认 5173）")
    parser.add_argument("--timeout", type=float, default=1.5, help="单次探测超时秒数（默认 1.5）")
    parser.add_argument("--json", action="store_true", help="输出 JSON（机器可读）")
    parser.add_argument("--self-test", action="store_true", help="反向自测：错端口必须判失败")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    checks = run_checks(
        build_checks(args.host, args.traffic_port, args.perception_port, args.frontend_port),
        timeout=args.timeout,
    )
    if args.json:
        print(json.dumps(
            {
                "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
                "ok": exit_code(checks) == 0,
                "host": args.host,
                "checks": [asdict(check) for check in checks],
                "missing": [check.key for check in checks if not check.ok],
            },
            ensure_ascii=False,
            indent=2,
        ))
    else:
        print_human(checks, args.host)
    return exit_code(checks)


if __name__ == "__main__":
    raise SystemExit(main())
