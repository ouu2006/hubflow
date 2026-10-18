#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IKMS1H 自检：处置闭环持久化（真跑 + 重启证据 + 审计 + 门禁）。

跑法（仓库根 / 本工作树根）：

    python work/assembly/selfcheck_ikms1h.py

它真跑一条完整处置闭环，并把**真实输出**写进 `work/assembly/自检记录-IKMS1H.md`：

1. **起服务**（默认端口 8000；被占则 8010，不改任何配置）→ `GET /alerts` 取派生告警；
2. **顺序校验**：无下发回执先回写 → 409 `ACK_NO_DISPATCH`（TC-07 闭环顺序）；
3. **下发 + 幂等**：POST dispatch → 200 回执；同告警同渠道同比例重复下发 → `idempotent:true`，
   回执时间不变、审计不重复；
4. **停服务 → 重启 → GET /alerts 状态仍在**（处置中 / 渠道 / 比例 / 操作者 / 审计 seq 都对得上）；
5. **回写**：已缓解 → 已闭环；四项留痕齐全；审计 seq 递增；
6. **终态约束**：终态后再下发 / 换结果回写 → 409 `ALERT_TERMINAL`；同内容重复回写 → 幂等回放；
7. **再重启**：已闭环 + 回写留痕 + 审计仍在（持久化不是只活一次）；
8. **复位**：POST /alerts/reset → 回「待认领」、运行态文件清空、reset 留审计；重启后仍是复位态；
9. **复位命令**：`traffic.py --reset-state` 真跑一次，重启后状态仍为复位态；
10. **审计可重建**：`GET /plan/audit` 能按序读出 dispatch / ack / reset / reset 四条记录与字段；
11. **隔离**：`--state-path` 指向 `out/` 下临时文件时只写临时文件，默认运行态文件哈希不变；
12. **跨页同源（API 层）**：连续两次 `GET /alerts` 完全一致（大屏 / 决策页读同一后端状态），
    并引用前端两个页面调用同一套 `api/traffic.ts` 函数的源码行；
13. **不提交运行态**：`git check-ignore` 证明 `work/assembly/data/dispatch.json` 被忽略、不在 git 索引；
14. **锁内不变量（独立审查修复）**：子进程真线程打 `DispatchStore`——已闭环后并发「未改善回写（会把状态改回
    处置中）」+「再下发」必须全部 409 冲突，终态不被翻转、审计不增；无回执回写在锁内被拒；
15. **审计 limit 语义**：`?limit=1000` 生效上限 1000，`total` 是过滤后**未截断**总数（不是截断后的条数）；
16. **`--state-path` 安全校验**：误传已跟踪文件 / 非 .json / 白名单外路径 → 退出码 2 且目标文件不被改动；
17. **仓库门禁**：`python scripts/doc_gate.py` 8/8。

隔离与可重复：脚本运行前把现有 `work/assembly/data/dispatch.json` 备份到 `out/`（gitignored），
结束时还原；本机没有运行产物时，在 `work/perception/out/latest/`（gitignored）生成**最小 fixture**
（一段 level 3 的 video 产物，仅自检用）并在结束时删除——不编造任何进入仓库的业务数据。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# Windows 控制台默认不是 UTF-8：先固定 stdout/stderr 编码，避免中文 / 符号打印直接抛异常
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
ASSEMBLY = ROOT / "work" / "assembly"
TRAFFIC = ASSEMBLY / "traffic.py"
OUT_DIR = ASSEMBLY / "out"  # gitignore 的 out/
DEFAULT_STATE = ASSEMBLY / "data" / "dispatch.json"
BACKUP_STATE = OUT_DIR / "ikms1h_backup_dispatch.json"
CUSTOM_STATE_REL = "work/assembly/out/ikms1h_selfcheck/custom_dispatch.json"
CUSTOM_STATE = ROOT / CUSTOM_STATE_REL
EVIDENCE_MD = ASSEMBLY / "自检记录-IKMS1H.md"
FIXTURE_VIDEO = ROOT / "work" / "perception" / "out" / "latest" / "segments_video.json"
FIXTURE_TWIN = ROOT / "work" / "twin" / "out" / "latest" / "segments_twin.json"
FIXTURE_CREATED: list[Path] = []
#: 锁内不变量探针：跑在 out/（gitignored）下的独立状态文件，不污染演示运行态
STORE_PROBE_SCRIPT = OUT_DIR / "ikms1h_selfcheck" / "store_invariant_probe.py"
PROBE_STATE = OUT_DIR / "ikms1h_selfcheck" / "invariant_probe_state.json"

STATE_DEFAULT_REL = DEFAULT_STATE.relative_to(ROOT).as_posix()

RESULTS: list[dict[str, Any]] = []
EVIDENCE: dict[str, Any] = {}

PORT = 0
BASE = ""
PROCESS: subprocess.Popen | None = None


# ---------------------------------------------------------------- HTTP / 服务生命周期


def http_call(method: str, path: str, body: dict | None = None,
              timeout: float = 10.0) -> tuple[int, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, _decode(response.read())
    except urllib.error.HTTPError as error:
        return error.code, _decode(error.read())
    except (urllib.error.URLError, OSError) as error:
        return 0, {"error": str(error)}


def _decode(raw: bytes) -> Any:
    text = raw.decode("utf-8", "replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text[:400]}


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def choose_port() -> int:
    for port in (8000, 8010):
        if _port_free(port):
            return port
    raise RuntimeError("8000 / 8010 都被占用：先停掉其它接口层实例再跑自检")


def wait_ready(timeout: float = 25.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if PROCESS is not None and PROCESS.poll() is not None:
            return False
        status, payload = http_call("GET", "/api/traffic/meta", timeout=2)
        if status == 200 and isinstance(payload, dict) and payload.get("is_simulated") is True:
            return True
        time.sleep(0.3)
    return False


def start_server(extra_args: list[str] | None = None) -> None:
    global PROCESS
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = OUT_DIR / "traffic_server.log"
    log = log_path.open("a", encoding="utf-8", newline="\n")
    command = [sys.executable, str(TRAFFIC), "--port", str(PORT)] + (extra_args or [])
    print("  启动：" + " ".join(command[1:]), flush=True)
    PROCESS = subprocess.Popen(command, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT)
    if not wait_ready():
        raise RuntimeError(f"traffic.py 起不来（日志见 {log_path.relative_to(ROOT)}）")


def stop_server() -> None:
    global PROCESS
    if PROCESS is None:
        return
    PROCESS.terminate()
    try:
        PROCESS.wait(timeout=10)
    except subprocess.TimeoutExpired:
        PROCESS.kill()
        PROCESS.wait(timeout=5)
    PROCESS = None
    deadline = time.time() + 10
    while time.time() < deadline and not _port_free(PORT):
        time.sleep(0.2)


def restart(extra_args: list[str] | None = None) -> None:
    stop_server()
    time.sleep(0.2)
    start_server(extra_args)


# ---------------------------------------------------------------- 运行态文件 / 断言


def read_state(path: Path = DEFAULT_STATE) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def state_digest(path: Path = DEFAULT_STATE) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def check(name: str, condition: Any, expected: Any, actual: Any, detail: str = "") -> bool:
    passed = bool(condition)
    RESULTS.append({
        "name": name,
        "passed": passed,
        "expected": expected,
        "actual": actual,
        "detail": detail,
    })
    print(f"  [{'通过' if passed else '失败'}] {name}｜期望：{expected}｜实际：{actual}", flush=True)
    return passed


def alerts_payload() -> dict[str, Any]:
    status, payload = http_call("GET", "/api/traffic/alerts")
    return payload if status == 200 and isinstance(payload, dict) else {}


def target_alert(alert_id: str) -> dict[str, Any] | None:
    for alert in alerts_payload().get("alerts") or []:
        if alert.get("alert_id") == alert_id:
            return alert
    return None


def audit_payload(limit: int = 50) -> dict[str, Any]:
    status, payload = http_call("GET", f"/api/traffic/plan/audit?limit={limit}")
    return payload if status == 200 and isinstance(payload, dict) else {}


def audit_total() -> int | None:
    value = audit_payload().get("audit_total")
    return value if isinstance(value, int) else None


def dispatch(alert_id: str, segment_id: str, channel: str = "情报板", ratio_pct: float = 30,
             operator: str = "值班员A") -> tuple[int, dict[str, Any]]:
    status, payload = http_call("POST", "/api/traffic/plan/dispatch", {
        "alert_id": alert_id,
        "segment_id": segment_id,
        "channel": channel,
        "ratio_pct": ratio_pct,
        "operator": operator,
    })
    return status, payload if isinstance(payload, dict) else {}


def ack(alert_id: str, segment_id: str, operator: str = "值班员A", action: str = "分流",
        result: str = "已缓解") -> tuple[int, dict[str, Any]]:
    status, payload = http_call("POST", "/api/traffic/plan/ack", {
        "alert_id": alert_id,
        "segment_id": segment_id,
        "operator": operator,
        "action": action,
        "result": result,
    })
    return status, payload if isinstance(payload, dict) else {}


# ---------------------------------------------------------------- fixture / 备份


def ensure_fixture() -> str:
    """工作树没有运行产物时生成最小 fixture（gitignored，仅自检用）。"""
    if FIXTURE_VIDEO.is_file() or FIXTURE_TWIN.is_file():
        return "使用工作树现有运行产物（不生成 fixture）"
    network = json.loads((ROOT / "stations/network.json").read_text(encoding="utf-8"))
    segments = [edge.get("section") for edge in network.get("edges") or [] if edge.get("section")]
    if not segments:
        raise RuntimeError("站点包 network.json 没有 edges[].section，无法生成自检 fixture")
    segment_id = str(segments[0])
    fixture = {
        "ts": "2026-01-01T00:00:00+08:00",
        "window_sec": 60,
        "is_simulated": True,
        "source_chain": "video",
        "note": "IKMS1H 自检 fixture（仅用于验证处置闭环持久化端点；不是业务产物）",
        "segments": [{
            "segment_id": segment_id,
            "source": "video",
            "q_vph": 900.0,
            "v_kmh": 10.0,
            "v_f_kmh": 40.0,
            "k_vpk": 60.0,
            "L_q_m": 150.0,
            "T_seg_m": None,
            "T_d_min": 6.0,
            "x": 0.75,
            "c_base_vph": 1200.0,
            "c_vph": 1200.0,
            "factors_applied": [],
            "ci": 70.0,
            "level": 3,
            "level_name": "拥堵",
            "triggered_by": ["x", "v"],
            "confidence": 0.9,
            "data_age_s": 5,
            "is_simulated": True,
        }],
    }
    FIXTURE_VIDEO.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_VIDEO.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    FIXTURE_CREATED.append(FIXTURE_VIDEO)
    return f"工作树没有运行产物 → 生成最小 fixture（段 {segment_id} / level 3，仅自检用，结束删除）"


def backup_default_state() -> str:
    if not DEFAULT_STATE.is_file():
        return "默认运行态文件不存在（测试结束后清理）"
    BACKUP_STATE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DEFAULT_STATE, BACKUP_STATE)
    return "已备份现有默认运行态文件（测试结束后还原）"


def restore_default_state() -> None:
    DEFAULT_STATE.unlink(missing_ok=True)
    if BACKUP_STATE.is_file():
        shutil.copy2(BACKUP_STATE, DEFAULT_STATE)
        BACKUP_STATE.unlink(missing_ok=True)
    for path in FIXTURE_CREATED:
        try:
            path.unlink()
            parent = path.parent
            while parent.name != "out" and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
        except OSError:
            pass


# ---------------------------------------------------------------- 跨页同源（前端源码引用）


def frontend_same_source_lines() -> list[str]:
    patterns = ("postPlanDispatch", "postPlanAck", "getTrafficAlerts", "subscribeTrafficSnapshot")
    lines: list[str] = []
    views = ROOT / "work/frontend/ui-vue/src"
    if not views.is_dir():
        return lines
    for path in sorted(views.rglob("*.vue")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if any(pattern in line for pattern in patterns):
                lines.append(f"`{path.relative_to(ROOT).as_posix()}`：`{line.strip()}`")
    return lines[:10]


# ---------------------------------------------------------------- 独立审查修复验证（锁内不变量 / 路径安全）

_STORE_PROBE_CODE = """# -*- coding: utf-8 -*-
import json
import sys
import threading

sys.path.insert(0, sys.argv[2])
import traffic

traffic.configure_dispatch_store(sys.argv[1])
store = traffic.get_dispatch_store()
store.record_dispatch("AL-INVARIANT", None, "情报板", 30, "值班员A")
store.record_ack("AL-INVARIANT", None, "值班员A", "分流", "已缓解", "已闭环")

outcomes = []
lock = threading.Lock()


def worker(index):
    ack_result = store.record_ack("AL-INVARIANT", None, "审查员%d" % index, "清障", "未改善", "处置中")
    dispatch_result = store.record_dispatch("AL-INVARIANT", None, "广播", 10, "审查员%d" % index)
    with lock:
        outcomes.append({
            "ack": ack_result.get("conflict"),
            "dispatch": dispatch_result.get("conflict"),
            "ack_ok": ack_result.get("ok"),
            "dispatch_ok": dispatch_result.get("ok"),
        })


threads = [threading.Thread(target=worker, args=(index,)) for index in range(16)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()

replay = store.record_ack("AL-INVARIANT", None, "值班员A", "分流", "已缓解", "已闭环")
fresh = store.record_ack("AL-FRESH", None, "审查员", "分流", "已缓解", "已闭环")
print(json.dumps({
    "outcomes": outcomes,
    "final_status": store.get_alert("AL-INVARIANT").get("status"),
    "audit_total": store.audit_total(),
    "idempotent_replay": {"ok": replay.get("ok"), "idempotent": replay.get("idempotent")},
    "fresh_conflict": fresh.get("conflict"),
}, ensure_ascii=False))
"""


def _run_store_invariant_probe() -> dict[str, Any]:
    """子进程导入 traffic.py，用真线程打持久化层锁内不变量（绕过端点层锁外校验）。

    已闭环告警上并发「未改善回写（会把状态改回处置中）」+「再下发」：锁内复查必须全部 409 冲突，
    终态不被翻转、审计不增加；同时验证终态幂等回放与无回执回写的锁内拒绝。
    """
    STORE_PROBE_SCRIPT.parent.mkdir(parents=True, exist_ok=True)
    STORE_PROBE_SCRIPT.write_text(_STORE_PROBE_CODE, encoding="utf-8", newline="\n")
    PROBE_STATE.unlink(missing_ok=True)
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.run(
        [sys.executable, str(STORE_PROBE_SCRIPT), str(PROBE_STATE), str(ASSEMBLY)],
        cwd=str(ROOT), capture_output=True, env=environment, timeout=120,
    )
    STORE_PROBE_SCRIPT.unlink(missing_ok=True)
    PROBE_STATE.unlink(missing_ok=True)
    stdout = process.stdout.decode("utf-8", "replace").strip()
    stderr = process.stderr.decode("utf-8", "replace").strip()
    payload: dict[str, Any] = {}
    if stdout:
        try:
            payload = json.loads(stdout.splitlines()[-1])
        except json.JSONDecodeError:
            payload = {}
    payload["exit_code"] = process.returncode
    if process.returncode != 0 and stderr:
        payload["stderr_tail"] = stderr[-400:]
    return payload


def _run_cli(args: list[str]) -> tuple[int, str]:
    """跑一次 traffic.py CLI（--check / --reset-state ...），返回 (退出码, 输出首行合集)。"""
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.run(
        [sys.executable, str(TRAFFIC), *args],
        cwd=str(ROOT), capture_output=True, env=environment, timeout=120,
    )
    stdout = process.stdout.decode("utf-8", "replace")
    stderr = process.stderr.decode("utf-8", "replace")
    return process.returncode, (stderr or stdout).strip()


# ---------------------------------------------------------------- doc_gate


def run_doc_gate() -> dict[str, Any]:
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.run(
        [sys.executable, "scripts/doc_gate.py"],
        cwd=str(ROOT),
        capture_output=True,
        env=environment,
        timeout=180,
    )
    repo_text = str(ROOT)
    stdout = process.stdout.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
    stderr = process.stderr.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
    # 业主红线（开发规范 §13.6）：记录里不写本机路径
    stdout = stdout.replace(repo_text, "<repo>").replace(repo_text.replace("\\", "/"), "<repo>")
    stderr = stderr.replace(repo_text, "<repo>").replace(repo_text.replace("\\", "/"), "<repo>")
    return {"exit_code": process.returncode, "stdout": stdout, "stderr": stderr}


# ---------------------------------------------------------------- 主流程


def run() -> None:
    fixture_note = ensure_fixture()
    backup_note = backup_default_state()
    if DEFAULT_STATE.is_file():
        DEFAULT_STATE.unlink()  # 从「干净初始态」开跑，避免上一轮运行态干扰断言
    CUSTOM_STATE.parent.mkdir(parents=True, exist_ok=True)
    CUSTOM_STATE.unlink(missing_ok=True)
    EVIDENCE["fixture_note"] = fixture_note
    EVIDENCE["backup_note"] = backup_note
    EVIDENCE["port"] = PORT

    print("[1/9] 起服务 + 初始告警 ...", flush=True)
    start_server()
    payload = alerts_payload()
    alerts = payload.get("alerts") or []
    check("GET /alerts 返回 200 且带信封", payload.get("is_simulated") is True,
          "is_simulated=true", payload.get("is_simulated"))
    check("告警信封带演示态 / 持久化 note", "持久化" in str(payload.get("note", "")),
          "note 含「持久化」", str(payload.get("note", ""))[:80])
    check("当前快照有可测的派生告警", len(alerts) >= 1, "≥1 条告警", f"{len(alerts)} 条")
    if not alerts:
        raise RuntimeError("没有派生告警（level≥3 的路段）：先跑感知链路产物或检查 fixture")
    alert = alerts[0]
    alert_id = str(alert.get("alert_id"))
    segment_id = str(alert.get("segment_id"))
    initial_alert = dict(alert)
    check("初始告警状态=待认领", alert.get("status") == "待认领", "待认领", alert.get("status"))
    check("初始运行态未落盘（干净起点）", not (read_state() or {}).get("alerts"),
          "alerts 为空", (read_state() or {}).get("alerts"))
    EVIDENCE["alert_id"] = alert_id
    EVIDENCE["segment_id"] = segment_id
    EVIDENCE["initial_alert"] = initial_alert

    print("\n[2/9] 顺序校验：无下发回执先回写 ...", flush=True)
    status, body = ack(alert_id, segment_id, operator="值班员A", action="分流", result="已缓解")
    check("无回执回写被拒（TC-07 顺序）", status == 409 and body.get("code") == "ACK_NO_DISPATCH",
          "409 ACK_NO_DISPATCH", f"{status} {body.get('code')}")
    check("被拒后运行态未变", not (read_state() or {}).get("alerts"),
          "alerts 为空", (read_state() or {}).get("alerts"))

    print("\n[3/9] 下发 + 重复下发幂等 ...", flush=True)
    status, receipt = dispatch(alert_id, segment_id, channel="情报板", ratio_pct=30, operator="值班员A")
    check("下发返回 200 回执", status == 200, 200, status)
    check("回执 persisted=true（已落盘）", receipt.get("persisted") is True, True, receipt.get("persisted"))
    check("首次下发 idempotent=false", receipt.get("idempotent") is False, False, receipt.get("idempotent"))
    check("首次下发审计 seq=1", receipt.get("audit_seq") == 1, 1, receipt.get("audit_seq"))
    state = read_state() or {}
    runtime = (state.get("alerts") or {}).get(alert_id) or {}
    check("运行态文件：状态=处置中", runtime.get("status") == "处置中", "处置中", runtime.get("status"))
    check(
        "运行态文件：渠道 / 比例 / 时间 / 操作者齐全",
        runtime.get("channels") == ["情报板"] and runtime.get("dispatch_ratio_pct") == 30
        and bool(runtime.get("dispatch_at")) and runtime.get("dispatch_operator") == "值班员A",
        "channels/ratio/dispatch_at/operator 齐全",
        {key: runtime.get(key) for key in ("channels", "dispatch_ratio_pct", "dispatch_at", "dispatch_operator")},
    )
    first_dispatch_at = receipt.get("at")
    status, repeat = dispatch(alert_id, segment_id, channel="情报板", ratio_pct=30, operator="值班员A")
    check("重复下发返回 200 且 idempotent=true", status == 200 and repeat.get("idempotent") is True,
          "200 idempotent=true", f"{status} idempotent={repeat.get('idempotent')}")
    check("重复下发沿用首次回执时间（不重复落盘）", repeat.get("at") == first_dispatch_at,
          first_dispatch_at, repeat.get("at"))
    check("重复下发不重复写审计", audit_total() == 1, 1, audit_total())
    EVIDENCE["dispatch_receipt"] = receipt
    EVIDENCE["dispatch_repeat"] = repeat
    EVIDENCE["alerts_after_dispatch"] = target_alert(alert_id)

    print("\n[4/9] 停服务 → 重启 → GET /alerts 状态仍在 ...", flush=True)
    restart()
    alert_after_restart = target_alert(alert_id) or {}
    check("重启后状态仍在=处置中", alert_after_restart.get("status") == "处置中",
          "处置中", alert_after_restart.get("status"))
    check(
        "重启后渠道 / 比例 / 操作者 / 回执时间仍在",
        alert_after_restart.get("channels") == ["情报板"]
        and alert_after_restart.get("dispatch_ratio_pct") == 30
        and alert_after_restart.get("dispatch_operator") == "值班员A"
        and alert_after_restart.get("dispatch_at") == first_dispatch_at,
        "渠道=情报板 / 比例=30 / 操作者=值班员A / 时间不变",
        {key: alert_after_restart.get(key) for key in (
            "channels", "dispatch_ratio_pct", "dispatch_operator", "dispatch_at")},
    )
    check("重启后审计仍在（audit_total=1）", audit_total() == 1, 1, audit_total())
    check("重启后运行态文件仍含该告警",
          bool(((read_state() or {}).get("alerts") or {}).get(alert_id)),
          "运行态含 AL", list(((read_state() or {}).get("alerts") or {}).keys()))
    EVIDENCE["alert_after_restart_1"] = alert_after_restart

    print("\n[5/9] 回写（四项留痕） ...", flush=True)
    status, ack_receipt = ack(alert_id, segment_id, operator="值班员A", action="分流", result="已缓解")
    check("回写返回 200 且状态=已闭环", status == 200 and ack_receipt.get("status") == "已闭环",
          "200 已闭环", f"{status} {ack_receipt.get('status')}")
    check("回执四项留痕：谁 / 何时 / 做了什么 / 结果",
          ack_receipt.get("operator") == "值班员A" and ack_receipt.get("operator_action") == "分流"
          and ack_receipt.get("result") == "已缓解" and bool(ack_receipt.get("at")),
          "operator/action/result/at 齐全",
          {key: ack_receipt.get(key) for key in ("operator", "operator_action", "result", "at")})
    check("回写后审计总数=2", audit_total() == 2, 2, audit_total())
    EVIDENCE["ack_receipt"] = ack_receipt
    EVIDENCE["alerts_after_ack"] = target_alert(alert_id)

    print("\n[6/9] 终态约束 + 幂等回放 ...", flush=True)
    status, body = dispatch(alert_id, segment_id, channel="情报板", ratio_pct=40)
    check("终态告警不可再下发", status == 409 and body.get("code") == "ALERT_TERMINAL",
          "409 ALERT_TERMINAL", f"{status} {body.get('code')}")
    status, body = ack(alert_id, segment_id, operator="值班员B", action="清障", result="未改善")
    check("终态告警不可翻转（换结果回写被拒）", status == 409 and body.get("code") == "ALERT_TERMINAL",
          "409 ALERT_TERMINAL", f"{status} {body.get('code')}")
    status, replay = ack(alert_id, segment_id, operator="值班员A", action="分流", result="已缓解")
    check("同内容重复回写按幂等回放（200）", status == 200 and replay.get("idempotent") is True,
          "200 idempotent=true", f"{status} idempotent={replay.get('idempotent')}")
    check("幂等回放不写新审计（仍为 2）", audit_total() == 2, 2, audit_total())

    print("\n[7/9] 再重启：终态 + 回写留痕持久化 ...", flush=True)
    restart()
    alert_final = target_alert(alert_id) or {}
    writeback = alert_final.get("writeback") if isinstance(alert_final.get("writeback"), dict) else {}
    check("重启后状态仍在=已闭环", alert_final.get("status") == "已闭环", "已闭环", alert_final.get("status"))
    check(
        "重启后回写留痕仍在（谁/何时/动作/结果）",
        writeback.get("operator") == "值班员A" and writeback.get("action") == "分流"
        and writeback.get("result") == "已缓解" and bool(writeback.get("at")),
        "writeback 四项齐全",
        writeback,
    )
    check("重启后审计总数=2", audit_total() == 2, 2, audit_total())
    status, body = dispatch(alert_id, segment_id, channel="导航软件推送", ratio_pct=20)
    check("重启后终态仍不可下发", status == 409 and body.get("code") == "ALERT_TERMINAL",
          "409 ALERT_TERMINAL", f"{status} {body.get('code')}")
    EVIDENCE["alert_after_restart_2"] = alert_final

    print("\n[8/9] 复位 + 复位持久化 + 复位命令 ...", flush=True)
    status, reset_receipt = http_call("POST", "/api/traffic/alerts/reset")
    reset_receipt = reset_receipt if isinstance(reset_receipt, dict) else {}
    check("POST /alerts/reset 返回 200 reset=true", status == 200 and reset_receipt.get("reset") is True,
          "200 reset=true", f"{status} reset={reset_receipt.get('reset')}")
    check(
        "复位结果：清掉 1 条 / seed 0 条 / reset_count=1 / audit_seq=3",
        reset_receipt.get("cleared_alerts") == 1 and reset_receipt.get("seed_alerts") == 0
        and reset_receipt.get("reset_count") == 1 and reset_receipt.get("audit_seq") == 3,
        "cleared=1 seed=0 reset_count=1 audit_seq=3",
        {key: reset_receipt.get(key) for key in ("cleared_alerts", "seed_alerts", "reset_count", "audit_seq")},
    )
    alert_reset = target_alert(alert_id) or {}
    check("复位后 GET /alerts 回「待认领」", alert_reset.get("status") == "待认领",
          "待认领", alert_reset.get("status"))
    check("复位后运行态文件清空", not (read_state() or {}).get("alerts"),
          "alerts 为空", (read_state() or {}).get("alerts"))
    audit_records = audit_payload().get("records") or []
    check("复位已留审计（最后一条 action=reset）",
          bool(audit_records) and audit_records[-1].get("action") == "reset",
          "末尾 action=reset", audit_records[-1].get("action") if audit_records else None)
    EVIDENCE["reset_receipt"] = reset_receipt

    restart()
    alert_after_reset_restart = target_alert(alert_id) or {}
    check("重启后仍是复位态（待认领）", alert_after_reset_restart.get("status") == "待认领",
          "待认领", alert_after_reset_restart.get("status"))
    check("重启后 reset_count=1 / 审计总数=3",
          audit_payload().get("reset_count") == 1 and audit_total() == 3,
          "reset_count=1 audit_total=3",
          {"reset_count": audit_payload().get("reset_count"), "audit_total": audit_total()})
    EVIDENCE["alert_after_reset_restart"] = alert_after_reset_restart
    EVIDENCE["state_after_reset"] = read_state()

    print("\n  复位命令（traffic.py --reset-state）...", flush=True)
    stop_server()
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    cli = subprocess.run(
        [sys.executable, str(TRAFFIC), "--reset-state"],
        cwd=str(ROOT), capture_output=True, env=environment, timeout=60,
    )
    cli_output = cli.stdout.decode("utf-8", "replace").replace("\r\n", "\n")
    cli_output = cli_output.replace(str(ROOT), "<repo>")
    check("CLI --reset-state 退出码 0", cli.returncode == 0, 0, cli.returncode)
    check("CLI 复位留痕（reset_count=2 / audit_seq=4）",
          "reset_count=2" in cli_output and "audit_seq=4" in cli_output,
          "输出含 reset_count=2 / audit_seq=4", cli_output.strip().replace("\n", " / ")[:160])
    start_server()
    alert_after_cli = target_alert(alert_id) or {}
    check("CLI 复位后仍是复位态（待认领）", alert_after_cli.get("status") == "待认领",
          "待认领", alert_after_cli.get("status"))
    check("CLI 复位后审计总数=4", audit_total() == 4, 4, audit_total())
    EVIDENCE["cli_reset_output"] = cli_output.strip()

    print("\n[9/9] 审计可重建 / 隔离 / 跨页同源 / 不提交运行态 ...", flush=True)
    audit = audit_payload(limit=50)
    records = audit.get("records") or []
    actions = [record.get("action") for record in records]
    check("审计按序可重建：dispatch → ack → reset → reset",
          actions == ["dispatch", "ack", "reset", "reset"], "['dispatch','ack','reset','reset']", actions)
    required_audit_fields = {"seq", "at", "action", "alert_id", "channel", "ratio_pct", "operator", "result"}
    check("审计记录字段齐全（alert_id/动作/渠道/比例/操作者/时间/结果）",
          all(required_audit_fields <= set(record) for record in records),
          "每条都含必需字段", [sorted(set(record)) for record in records[:1]])
    check("审计 store_path 指向默认运行态文件", audit.get("store_path") == STATE_DEFAULT_REL,
          STATE_DEFAULT_REL, audit.get("store_path"))
    EVIDENCE["audit"] = audit

    print("\n  [审查修复] 审计 limit 语义 / 锁内不变量 / --state-path 安全校验 ...", flush=True)
    limited_1000 = audit_payload(limit=1000)
    check("审计 limit=1000：生效 limit=1000 且 total 为未截断总数",
          limited_1000.get("limit") == 1000 and limited_1000.get("total") == 4
          and limited_1000.get("returned") == 4,
          "limit=1000 / total=4 / returned=4",
          {key: limited_1000.get(key) for key in ("limit", "total", "returned")})
    limited_2 = audit_payload(limit=2)
    check("审计 limit=2：returned=2 但 total 仍为未截断 4",
          limited_2.get("returned") == 2 and limited_2.get("total") == 4,
          "returned=2 / total=4",
          {key: limited_2.get(key) for key in ("limit", "total", "returned")})
    EVIDENCE["audit_limit"] = {
        "limit_1000": {key: limited_1000.get(key) for key in ("limit", "total", "returned", "audit_total")},
        "limit_2": {key: limited_2.get(key) for key in ("limit", "total", "returned", "audit_total")},
    }

    probe = _run_store_invariant_probe()
    EVIDENCE["store_invariant"] = probe
    outcomes = probe.get("outcomes") or []
    all_conflict = bool(outcomes) and all(
        item.get("ack") == "ALERT_TERMINAL" and item.get("dispatch") == "ALERT_TERMINAL"
        and item.get("ack_ok") is False and item.get("dispatch_ok") is False
        for item in outcomes
    )
    check("持久化层锁内不变量：并发 16 线程终态回写 / 下发全部 409 冲突",
          all_conflict and probe.get("exit_code") == 0,
          "16/16 均为 ALERT_TERMINAL 冲突", f"{len(outcomes)} 条结果，exit={probe.get('exit_code')}")
    check("持久化层锁内不变量：并发后终态未被翻转（已闭环）且审计不增（=2）",
          probe.get("final_status") == "已闭环" and probe.get("audit_total") == 2,
          "已闭环 / audit_total=2",
          {"final_status": probe.get("final_status"), "audit_total": probe.get("audit_total")})
    check("持久化层锁内不变量：终态同人同动作同结果仍可幂等回放",
          (probe.get("idempotent_replay") or {}).get("ok") is True
          and (probe.get("idempotent_replay") or {}).get("idempotent") is True,
          "ok=true idempotent=true", probe.get("idempotent_replay"))
    check("持久化层锁内不变量：无回执回写（锁内复查）→ ACK_NO_DISPATCH",
          probe.get("fresh_conflict") == "ACK_NO_DISPATCH", "ACK_NO_DISPATCH", probe.get("fresh_conflict"))

    readme_path = ASSEMBLY / "README.md"
    readme_digest_before = state_digest(readme_path)
    invalid_paths = [
        "work/assembly/README.md",          # 已跟踪文件（非 .json）
        "work/assembly/traffic.py",         # 已跟踪文件（非 .json）
        "work/assembly/out/state.txt",      # 非 .json
        "work/assembly/not_allowed.json",   # .json 但不在白名单目录
        "docs/数据契约.md",                  # 其它目录（非 .json）
    ]
    invalid_records = []
    for bad_path in invalid_paths:
        code, output = _run_cli(["--check", "--state-path", bad_path])
        invalid_records.append({
            "state_path": bad_path,
            "exit_code": code,
            "output_first_line": output.splitlines()[0][:160] if output else "",
        })
    check("--state-path 误传已跟踪文件 / 非 .json / 白名单外路径 → 退出码 2",
          all(record["exit_code"] == 2 for record in invalid_records),
          "5/5 退出码 2", [record["exit_code"] for record in invalid_records])
    check("--state-path 拒绝时目标文件未被改动（README 哈希不变）",
          state_digest(readme_path) == readme_digest_before, "哈希不变",
          "不变" if state_digest(readme_path) == readme_digest_before else "变化")
    valid_code, _valid_output = _run_cli([
        "--check", "--state-path", "work/assembly/out/ikms1h_selfcheck/ok_state.json",
    ])
    check("--state-path 白名单内 .json 仍可用（--check 退出码 0）", valid_code == 0, 0, valid_code)
    EVIDENCE["state_path_safety"] = {
        "invalid": invalid_records,
        "readme_unchanged": state_digest(readme_path) == readme_digest_before,
        "valid_out_json_exit": valid_code,
    }

    default_digest_before = state_digest()
    stop_server()
    CUSTOM_STATE.parent.mkdir(parents=True, exist_ok=True)
    CUSTOM_STATE.unlink(missing_ok=True)
    start_server(["--state-path", CUSTOM_STATE_REL])
    status, custom_receipt = dispatch(
        alert_id, segment_id, channel="广播", ratio_pct=15, operator="值班员C"
    )
    custom_state = read_state(CUSTOM_STATE)
    check("--state-path 自定义路径：下发写自定义文件", status == 200
          and custom_receipt.get("store_path") == CUSTOM_STATE_REL and bool(custom_state),
          f"store_path={CUSTOM_STATE_REL} 且文件存在",
          {"status": status, "store_path": custom_receipt.get("store_path"), "file_exists": bool(custom_state)})
    stop_server()
    check("自定义路径测试不影响默认运行态文件（哈希不变）",
          state_digest() == default_digest_before, "哈希不变", "哈希变化" if state_digest() != default_digest_before else "不变")
    CUSTOM_STATE.unlink(missing_ok=True)

    start_server()
    first_read = alerts_payload()
    second_read = alerts_payload()
    check("跨页同源（API 层）：大屏 / 决策页两次 GET /alerts 完全一致",
          json.dumps(first_read, ensure_ascii=False, sort_keys=True)
          == json.dumps(second_read, ensure_ascii=False, sort_keys=True),
          "两次响应逐字段一致",
          "一致" if first_read == second_read else "不一致")
    EVIDENCE["cross_page"] = {
        "two_reads_identical": first_read == second_read,
        "frontend_lines": frontend_same_source_lines(),
    }

    ignored = subprocess.run(
        ["git", "check-ignore", "-v", DEFAULT_STATE.relative_to(ROOT).as_posix()],
        cwd=str(ROOT), capture_output=True, env=environment, timeout=30,
    )
    check("运行态文件被 gitignore 拦截", ignored.returncode == 0,
          "git check-ignore 退出码 0", ignored.returncode)
    tracked = subprocess.run(
        ["git", "ls-files", DEFAULT_STATE.relative_to(ROOT).as_posix()],
        cwd=str(ROOT), capture_output=True, env=environment, timeout=30,
    )
    check("运行态文件不在 git 索引", tracked.stdout.decode("utf-8", "replace").strip() == "",
          "git ls-files 输出为空", tracked.stdout.decode("utf-8", "replace").strip() or "(空)")
    EVIDENCE["git_ignore"] = {
        "check_ignore": ignored.stdout.decode("utf-8", "replace").strip(),
        "hidden": not tracked.stdout.decode("utf-8", "replace").strip(),
    }

    check_run = subprocess.run(
        [sys.executable, str(TRAFFIC), "--check"],
        cwd=str(ROOT), capture_output=True, env=environment, timeout=120,
    )
    check_output = check_run.stdout.decode("utf-8", "replace")
    check("--check 能读出持久化运行态", "处置闭环运行态（持久化）" in check_output
          and STATE_DEFAULT_REL in check_output,
          "输出含「处置闭环运行态（持久化）」+ 默认路径", "输出已包含" if "处置闭环运行态（持久化）" in check_output else "未包含")
    EVIDENCE["check_output_tail"] = "\n".join(check_output.strip().splitlines()[-8:]).replace(str(ROOT), "<repo>")

    stop_server()


# ---------------------------------------------------------------- 证据文档


def _json_block(value: Any, limit: int = 2600) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2)
    if len(text) > limit:
        text = text[:limit] + "\n…（截断）"
    return "```json\n" + text + "\n```"


def write_evidence(doc_gate: dict[str, Any], doc_gate_recheck: dict[str, Any] | None = None) -> None:
    passed = sum(1 for item in RESULTS if item["passed"])
    total = len(RESULTS)
    lines: list[str] = []
    lines.append("# IKMS1H 自检记录：处置闭环持久化（真跑输出）\n")
    lines.append(f"- 生成时间：{time.strftime('%Y-%m-%dT%H:%M:%S%z')}")
    lines.append(f"- Python：{sys.version.split()[0]}；服务端口：**{PORT}**（默认 8000；被占才用 8010）")
    lines.append(f"- 运行态文件（默认）：`{STATE_DEFAULT_REL}`（gitignored；见 [data/.gitignore](data/.gitignore)）")
    lines.append(f"- 代码：[traffic.py](traffic.py) · [README.md](README.md) · [selfcheck_ikms1h.py](selfcheck_ikms1h.py)")
    lines.append(f"- 运行产物：{EVIDENCE.get('fixture_note', '')}")
    lines.append(f"- 隔离：{EVIDENCE.get('backup_note', '')}；`--state-path` 用 `out/` 临时文件单独验过")
    lines.append("")
    lines.append("## 一、断言汇总\n")
    lines.append(f"**{passed}/{total} 条断言通过**" + (" ✅" if passed == total else " ❌"))
    lines.append("")
    lines.append("| # | 场景 | 期望 | 实际 | 结果 |")
    lines.append("|---|---|---|---|---|")
    for index, item in enumerate(RESULTS, 1):
        expected = str(item["expected"]).replace("|", "\\|")[:90]
        actual = str(item["actual"]).replace("|", "\\|")[:120]
        lines.append(
            f"| {index} | {item['name']} | {expected} | {actual} | {'✅' if item['passed'] else '❌'} |"
        )
    lines.append("")
    lines.append("## 二、重启持久化证据（停服务 → 重启 → 再读）\n")
    lines.append(f"- 被测告警：`{EVIDENCE.get('alert_id')}`（路段 `{EVIDENCE.get('segment_id')}`）；自检从干净初始态开跑。")
    lines.append("")
    lines.append("### 2.1 第一次重启前：下发回执（POST /plan/dispatch，200）\n")
    lines.append(_json_block(EVIDENCE.get("dispatch_receipt")))
    lines.append("")
    lines.append("### 2.2 第一次重启后：GET /alerts 读到的同一条告警（状态仍在=处置中）\n")
    lines.append(_json_block(EVIDENCE.get("alert_after_restart_1")))
    lines.append("")
    lines.append("### 2.3 回写后再次重启：GET /alerts 读到终态 + 回写留痕\n")
    lines.append(_json_block(EVIDENCE.get("alert_after_restart_2")))
    lines.append("")
    lines.append("### 2.4 复位（POST /alerts/reset）→ 重启后仍为复位态\n")
    lines.append("复位回执：")
    lines.append("")
    lines.append(_json_block(EVIDENCE.get("reset_receipt")))
    lines.append("")
    lines.append("复位并重启后的告警：")
    lines.append("")
    lines.append(_json_block(EVIDENCE.get("alert_after_reset_restart")))
    lines.append("")
    lines.append("复位后运行态文件（alerts 已清空、reset 审计保留）：")
    lines.append("")
    lines.append(_json_block(EVIDENCE.get("state_after_reset")))
    lines.append("")
    lines.append("### 2.5 复位命令 `traffic.py --reset-state` 输出\n")
    lines.append("```text")
    lines.append(str(EVIDENCE.get("cli_reset_output", "")))
    lines.append("```")
    lines.append("")
    lines.append("## 三、幂等 / 顺序 / 终态 / 审计专项\n")
    lines.append("- **幂等**：同告警 + 同渠道 + 同比例重复下发 → `idempotent:true`，沿用首次回执时间，审计不重复；")
    lines.append("  同人同动作同结果重复回写 → `idempotent:true` 回放既有回执，审计不重复。")
    lines.append("- **顺序**：无下发回执先回写 → 409 `ACK_NO_DISPATCH`（TC-07 闭环顺序）；")
    lines.append("  终态（已闭环 / 误报）再下发或换结果回写 → 409 `ALERT_TERMINAL`，不可翻转。")
    lines.append("- **审计**：每条记录含 seq / at / action / alert_id / segment_id / channel / ratio_pct / operator / "
                 "result / status_after；ack 另有 operator_action；reset 另有 cleared_alerts / seed_alerts。")
    lines.append("")
    lines.append("审计全量（GET /plan/audit）：")
    lines.append("")
    lines.append(_json_block(EVIDENCE.get("audit")))
    lines.append("")
    lines.append("## 四、独立审查修复验证（锁内不变量 / 审计 limit / 路径安全）\n")
    lines.append("> 对应独立审查 3 条非阻断发现：终态并发不变量、`audit limit` 截断语义、`--state-path` 目标路径校验。")
    lines.append("")
    lines.append("### 4.1 持久化层锁内不变量（真线程：16 并发 × ack/dispatch）\n")
    lines.append("已闭环告警上并发 16 线程「未改善回写（会把状态改回处置中）」+「再下发」；"
                 "锁内复查必须全部 409 冲突、终态不被翻转、审计不增：")
    lines.append("")
    lines.append(_json_block(EVIDENCE.get("store_invariant"), 2600))
    lines.append("")
    lines.append("### 4.2 审计 limit 语义（`total` = 过滤后未截断总数）\n")
    lines.append(_json_block(EVIDENCE.get("audit_limit"), 1400))
    lines.append("")
    lines.append("### 4.3 `--state-path` 安全校验（误传已跟踪文件不会改名覆盖）\n")
    lines.append(_json_block(EVIDENCE.get("state_path_safety"), 2200))
    lines.append("")
    lines.append("## 五、跨页同源（大屏 / 决策页读同一后端状态）\n")
    cross = EVIDENCE.get("cross_page") or {}
    lines.append(f"- API 层：连续两次 `GET /api/traffic/alerts` 逐字段一致："
                 f"**{'✅ 是' if cross.get('two_reads_identical') else '❌ 否'}**")
    lines.append("- 前端源码（只读引用）：两个页面调同一套 `src/api/traffic.ts` 函数（同一个后端状态，页面刷新 / 切换不丢）：")
    for line in cross.get("frontend_lines") or []:
        lines.append(f"  - {line}")
    lines.append("- 说明：本机未起 `npm run dev:remote`（前端 dev server），故以同一后端接口的两次独立读取 + 源码同源引用"
                 "证明「同一份状态」；重启持久化证据见第二节。")
    lines.append("")
    lines.append("## 六、运行态文件不提交（gitignore / git 索引）\n")
    git_info = EVIDENCE.get("git_ignore") or {}
    lines.append(f"- `git check-ignore -v`：`{git_info.get('check_ignore')}`")
    lines.append(f"- `git ls-files` 命中运行态文件：{'否 ✅' if git_info.get('hidden') else '是 ❌'}")
    lines.append("")
    lines.append("## 七、`--check` 读持久化运行态（输出尾部）\n")
    lines.append("```text")
    lines.append(str(EVIDENCE.get("check_output_tail", "")))
    lines.append("```")
    lines.append("")
    lines.append("## 八、仓库门禁 doc_gate\n")
    lines.append("- 命令：`python scripts/doc_gate.py`（8 组）")
    lines.append(f"- 首次运行：退出码 **{doc_gate['exit_code']}**")
    if doc_gate_recheck is not None:
        lines.append(f"- 复检（本记录写全后）：退出码 **{doc_gate_recheck['exit_code']}**"
                     f"{' ✅ 8/8 通过' if doc_gate_recheck['exit_code'] == 0 else ' ❌ 未通过'}")
        shown = doc_gate_recheck
    else:
        shown = doc_gate
    lines.append("")
    lines.append("```text")
    lines.append((shown["stdout"].strip() or "(无输出)")[-4000:])
    lines.append("```")
    lines.append("")
    lines.append("## 九、结论与遗留\n")
    lines.append(f"- 本单完成判定：TC-07（状态可推进 + 四项留痕 + 重启仍在）/ 顺序校验 / 终态不可翻转 / "
                 f"幂等 / 复位可留痕 / 审计可重建 / 跨页同源（API 层）—— 自检 **{passed}/{total}** 通过。")
    lines.append("- 独立审查 3 条非阻断发现（终态并发不变量 / 审计 limit 截断语义 / `--state-path` 目标路径校验）"
                 "已修复并纳入断言（见第四节）。")
    lines.append("- 遗留：① 运行态是**一进程一文件仓**（JSON，单 worker），多 worker / 并发写库场景留给二期 openGauss；"
                 "② 大屏 / 决策页真实浏览器联调未在本机跑（无前端 dev server），以 API 层同源 + 源码引用为证；"
                 "③ `work/frontend/README.md` 的处置闭环章节按 Issue 原文应同步，但本单写入范围限定 `work/assembly/**`，"
                 "留给前端 owner / 文档 owner 收口。")
    lines.append("")
    EVIDENCE_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- main


def main() -> int:
    global PORT, BASE
    PORT = choose_port()
    BASE = f"http://127.0.0.1:{PORT}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"IKMS1H 自检：处置闭环持久化（端口 {PORT}，运行态默认 {STATE_DEFAULT_REL}）", flush=True)
    try:
        run()
    finally:
        stop_server()
        CUSTOM_STATE.unlink(missing_ok=True)
        restore_default_state()

    print("\n生成自检记录（先占位，再跑门禁，最后写全）...", flush=True)
    placeholder = {"exit_code": -1, "stdout": "（见下方复检）", "stderr": ""}
    write_evidence(placeholder)
    doc_gate = run_doc_gate()
    write_evidence(doc_gate)
    doc_gate_recheck = run_doc_gate()
    write_evidence(doc_gate, doc_gate_recheck)

    passed = sum(1 for item in RESULTS if item["passed"])
    total = len(RESULTS)
    failed = [item["name"] for item in RESULTS if not item["passed"]]
    print()
    print(f"断言：{passed}/{total} 通过" + (" ✅" if not failed else " ❌"))
    for name in failed:
        print(f"  失败：{name}")
    print(f"doc_gate：首次 {doc_gate['exit_code']} / 复检 {doc_gate_recheck['exit_code']}"
          + (" ✅ 8/8" if doc_gate_recheck["exit_code"] == 0 else " ❌"))
    print(f"自检记录：{EVIDENCE_MD.relative_to(ROOT)}")
    return 0 if (not failed and doc_gate_recheck["exit_code"] == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
