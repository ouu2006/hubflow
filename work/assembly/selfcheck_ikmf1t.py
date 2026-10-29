#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IKMF1T 自检 + 与 mock 的响应形状对照快照生成器（可重复跑）。

跑法（在仓库根）：

    python work/assembly/selfcheck_ikmf1t.py

它做六件事，并把**真实输出**写进 `work/assembly/自检记录.md`：

1. **端点全绿**：起 traffic.py（默认端口 **8001** = 本工作树；`--api-base` / `HUBFLOW_API_BASE`
   可覆盖。**别指 8000** —— 那是主工作树 D:/hubflow/hubflow 的旧实例，新端点会 404），
   逐条请求契约 §七 / mock 路由表里的 GET / POST / SSE 端点；
2. **三层回落**：把 `work/*/out/` 临时挪开 → 端点仍 200 且回落站点包静态基线（不 500、不空指针）→ 还原；
3. **段号写死扫描**：正则扫 `traffic.py`，`SZ-数字` / `SEG-数字` 必须 0 命中；
4. **可复现**：同一请求两次，除时间戳外响应逐字段一致；
5. **与 mock 形状对照**：同一路径分别打 vite mock（:5173）与 traffic.py（同 1 的端口），
   比对顶格键与嵌套键集；结果写 `work/assembly/对照快照.json` + `对照快照.md`；
   mock 不可达时如实注明「未做实时对照」及静态提取方法；
6. **仓库门禁**：`python scripts/doc_gate.py`（8 组）真实跑一遍并记录输出。

只读 + 只动 `work/assembly/out/`（gitignore）与临时挪开的 `work/*/out/`（finally 还原）。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Windows 控制台默认不是 UTF-8：先固定 stdout/stderr 编码，避免中文 / 符号打印直接抛异常
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
ASSEMBLY = ROOT / "work" / "assembly"
TRAFFIC = ASSEMBLY / "traffic.py"
OUT_DIR = ASSEMBLY / "out"  # gitignore 的 out/，放日志与回落备份
BACKUP_DIR = OUT_DIR / "fallback_backup"
# 后端地址：默认钉在**本工作树**的 8001（2026-10-29 队长要求）。
# 8000 常被主工作树（D:/hubflow/hubflow）的旧实例占着，而本脚本发现地址可达就会**复用**已有服务 ——
# 复用到旧进程会让本轮改动（如 /route/{id}/steps、destination_point）被误判为缺失（实测 404 就是这么来的）。
# 覆盖优先级：`--api-base` > 环境变量 `HUBFLOW_API_BASE` > 默认 http://127.0.0.1:8001。
# 兼容旧用法：环境变量 `TRAFFIC_PORT` 仍可只改端口（早先的联调脚本就是这么调的）。
DEFAULT_API_BASE = "http://127.0.0.1:8001"
API_BASE_ENV = "HUBFLOW_API_BASE"


def _initial_api_base() -> str:
    base = (os.environ.get(API_BASE_ENV) or "").strip()
    if base:
        return base.rstrip("/")
    port = (os.environ.get("TRAFFIC_PORT") or "").strip()
    if port:
        return f"http://127.0.0.1:{port}"
    return DEFAULT_API_BASE


def _port_of(base: str) -> int:
    tail = base.rsplit("/", 1)[-1]
    port = tail.rsplit(":", 1)[-1]
    try:
        return int(port)
    except ValueError:
        return 8001


SERVER_URL = _initial_api_base()
SERVER_PORT = _port_of(SERVER_URL)
MOCK_URL = "http://127.0.0.1:5173"

DROP_ENDPOINTS = ["work/perception/out", "work/twin/out", "work/engine/out"]

SNAPSHOT_JSON = ASSEMBLY / "对照快照.json"
SNAPSHOT_MD = ASSEMBLY / "对照快照.md"
CHECKLOG_MD = ASSEMBLY / "自检记录.md"


# ---------------------------------------------------------------- HTTP


def http_call(method: str, url: str, body: dict | None = None,
              timeout: float = 10.0) -> tuple[int, object, dict[str, str]]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, _decode(raw), _lower_headers(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, _decode(error.read()), _lower_headers(error.headers)
    except (urllib.error.URLError, OSError) as error:
        return 0, {"error": str(error)}, {}


def _lower_headers(headers) -> dict[str, str]:
    """HTTP 头名大小写不敏感（uvicorn 发的是小写），统一成小写键再取值。"""
    return {str(key).lower(): str(value) for key, value in dict(headers).items()}


def _decode(raw: bytes) -> object:
    text = raw.decode("utf-8", "replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text[:400]}


def _top_keys(payload: object) -> list[str]:
    return sorted(payload.keys()) if isinstance(payload, dict) else []


# ---------------------------------------------------------------- 形状比对（键集，不看取值）


def _merge_shapes(values: list) -> dict | None:
    """数组元素形状取并集：全是对象 → 合并键；全是数组 → 摊平再合并；其余（标量 / null）不参与。"""
    dicts = [value for value in values if isinstance(value, dict)]
    if dicts and len(dicts) == len(values):
        merged: dict[str, list] = {}
        for item in dicts:
            for key, value in item.items():
                merged.setdefault(key, []).append(value)
        return {key: _merge_shapes(items) for key, items in merged.items()}
    lists = [value for value in values if isinstance(value, list)]
    if lists and len(lists) == len(values):
        flat = [item for items in lists for item in items]
        return _merge_shapes(flat) if flat else None
    return None


def _shape_diff(mock: object, ours: object, path: str, diffs: list[dict]) -> None:
    """只比键集；null / 标量 / 空数组视为「无从比较」，跳过（数据可用性差异另行说明）。"""
    if mock is None or ours is None:
        return
    if isinstance(mock, dict) and isinstance(ours, dict):
        only_mock = sorted(set(mock) - set(ours))
        only_ours = sorted(set(ours) - set(mock))
        if only_mock or only_ours:
            diffs.append({"path": path, "only_mock": only_mock, "only_ours": only_ours})
        for key in sorted(set(mock) & set(ours)):
            _shape_diff(mock[key], ours[key], f"{path}.{key}", diffs)
        return
    if isinstance(mock, list) or isinstance(ours, list):
        left = _merge_shapes(mock) if isinstance(mock, list) else mock
        right = _merge_shapes(ours) if isinstance(ours, list) else ours
        if isinstance(left, dict) and isinstance(right, dict):
            _shape_diff(left, right, f"{path}[]", diffs)


def _strip_ts(value: object) -> object:
    """去掉所有 ts 键，用于「除时间戳外一致」的复现性比对。"""
    if isinstance(value, dict):
        return {key: _strip_ts(item) for key, item in value.items() if key != "ts"}
    if isinstance(value, list):
        return [_strip_ts(item) for item in value]
    return value


# ---------------------------------------------------------------- 服务生命周期


def server_reachable(base: str) -> bool:
    status, _, _ = http_call("GET", f"{base}/api/traffic/meta", timeout=2)
    return status == 200


def start_server() -> tuple[subprocess.Popen | None, bool]:
    """返回 (进程, 是否复用已有服务)。"""
    if server_reachable(SERVER_URL):
        return None, True
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = OUT_DIR / "traffic_server.log"
    log_file = log_path.open("w", encoding="utf-8", newline="\n")
    process = subprocess.Popen(
        [sys.executable, str(TRAFFIC), "--port", str(SERVER_PORT)],
        cwd=str(ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"traffic.py 启动失败，日志见 {log_path}")
        if server_reachable(SERVER_URL):
            return process, False
        time.sleep(0.3)
    process.terminate()
    raise RuntimeError(f"traffic.py 启动超时（20s），日志见 {log_path}")


def stop_server(process: subprocess.Popen | None) -> None:
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()


# ---------------------------------------------------------------- 端点清单


def _quote(segment_id: str) -> str:
    return urllib.parse.quote(segment_id, safe="")


def _engine_sample_ids() -> tuple[str | None, str | None]:
    """从引擎产物里取「真实存在的」session_id / 段号，供 route/recommend·locate 形状对照。

    traffic.py 对 session_id 做**严格匹配**（给了但产物里没有 → 404，不拿 requests[0] 顶包），
    所以形状对照必须用产物里真实有的 session，而不是自造一个。
    """
    path = ROOT / "work" / "engine" / "out" / "routes.json"
    if not path.is_file():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    for request in payload.get("requests") or []:
        if not isinstance(request, dict):
            continue
        session_id = request.get("session_id")
        location = request.get("location") if isinstance(request.get("location"), dict) else {}
        if isinstance(session_id, str) and session_id:
            return session_id, location.get("segment_id")
    return None, None


def endpoint_specs(side: str, segment_id: str, alert_id: str | None) -> list[dict]:
    """同一份端点清单，按各自服务的数据（段号 / 告警号）实例化。

    顺序有讲究：`alerts(下发后)` 排在 `plan/ack` 之后，用来对照「可选留痕字段」的形状是否也一致
    （两边都在前面真的做了一次下发 + 回写）；`alerts/reset` 在最后把演示态复位。
    """
    specs: list[tuple[str, str, str, dict | None, str]] = [
        ("meta", "GET", "/api/traffic/meta", None, "required-get"),
        ("overview", "GET", "/api/traffic/overview", None, "required-get"),
        ("segments", "GET", "/api/traffic/segments", None, "required-get"),
        ("segments/{id}", "GET", f"/api/traffic/segments/{_quote(segment_id)}", None, "required-get"),
        ("segments/{id}/sources", "GET",
         f"/api/traffic/segments/{_quote(segment_id)}/sources", None, "required-get"),
        ("vehicles", "GET", "/api/traffic/vehicles", None, "required-get"),
        ("network", "GET", "/api/traffic/network", None, "required-get"),
        ("thresholds", "GET", "/api/traffic/thresholds", None, "required-get"),
        ("factors", "GET", "/api/traffic/factors", None, "required-get"),
        ("assimilation", "GET", "/api/traffic/assimilation", None, "required-get"),
        ("alerts", "GET", "/api/traffic/alerts", None, "required-get"),
        ("predict", "GET", f"/api/traffic/predict?segment_id={_quote(segment_id)}&h=15", None, "required-get"),
        ("heat-matrix", "GET", "/api/traffic/heat-matrix?window=12&bucket=60", None, "required-get"),
        ("ci-history", "GET", f"/api/traffic/ci-history?segment_id={_quote(segment_id)}&points=12", None,
         "required-get"),
        ("context", "GET", "/api/traffic/context", None, "required-get"),
        ("report/compare", "GET", "/api/traffic/report/compare", None, "required-get"),
    ]
    # route/recommend / locate 用引擎产物里**真实存在的** session_id 做形状对照；
    # 引擎产物缺失时这两项不列入「必须 200」清单（回落阶段会单独验证如实 404）。
    engine_session, engine_segment = _engine_sample_ids()
    if engine_session:
        specs.extend([
            ("route/recommend", "POST", "/api/traffic/route/recommend",
             {"session_id": engine_session, "location": {"segment_id": engine_segment or segment_id, "offset_m": 0}},
             "required-post"),
            ("locate", "POST", "/api/traffic/locate", {"session_id": engine_session}, "required-post"),
        ])
    if alert_id:
        specs.extend([
            ("plan/dispatch", "POST", "/api/traffic/plan/dispatch",
             {"alert_id": alert_id, "channel": "短信", "ratio_pct": 30}, "required-post"),
            ("plan/ack", "POST", "/api/traffic/plan/ack",
             {"alert_id": alert_id, "operator": "selfcheck", "action": "分流", "result": "已缓解"},
             "required-post"),
            ("alerts(下发后)", "GET", "/api/traffic/alerts", None, "required-get"),
        ])
    specs.extend([
        ("alerts/reset", "POST", "/api/traffic/alerts/reset", None, "required-post"),
        ("factors/reset", "POST", "/api/traffic/factors/reset", None, "required-post"),
        ("factors(POST)", "POST", "/api/traffic/factors",
         {"segment_id": segment_id, "factor_id": "F07", "name": "交通事故", "target": "c", "multiplier": 0.5},
         "unimplemented"),
        ("scenario", "POST", "/api/traffic/scenario", {"weather": "小雨"}, "unimplemented"),
        ("scenario/reset", "POST", "/api/traffic/scenario/reset", None, "unimplemented"),
    ])
    return [
        {"name": name, "method": method, "path": path, "body": body,
         "category": category, "side": side}
        for name, method, path, body, category in specs
    ]


def cleanup_runtime_states(mock_reachable: bool) -> list[str]:
    """对照会真的下发 / 回写 / 置位，结束后把两边的演示态复位，避免污染后续演示与下一次自检。"""
    actions: list[str] = []
    targets = [(SERVER_URL, "traffic.py")]
    if mock_reachable:
        targets.append((MOCK_URL, "mock"))
    for base, label in targets:
        for path in ("/api/traffic/alerts/reset", "/api/traffic/factors/reset", "/api/traffic/scenario/reset"):
            status, _, _ = http_call("POST", base + path)
            actions.append(f"{label} {path} -> {status}")
    return actions


# ---------------------------------------------------------------- 数据源状态


def resolve_ids(base: str) -> tuple[str, str | None, dict]:
    """取对侧服务的路段号 / 告警号（各自数据命名空间不同，按各服务自己的快照取）。"""
    status, segments, _ = http_call("GET", f"{base}/api/traffic/segments")
    segment_id = ""
    if status == 200 and isinstance(segments, dict) and segments.get("segments"):
        segment_id = str(segments["segments"][0].get("segment_id") or "")
    alert_id = None
    status, alerts, _ = http_call("GET", f"{base}/api/traffic/alerts")
    if status == 200 and isinstance(alerts, dict) and alerts.get("alerts"):
        alert_id = str(alerts["alerts"][0].get("alert_id") or "") or None
    return segment_id, alert_id, {"segments": segments, "alerts": alerts}


# ---------------------------------------------------------------- 1) 端点全绿


def check_endpoints(ours_specs: list[dict], mock_reachable: bool,
                    mock_specs: list[dict]) -> tuple[list[dict], list[dict]]:
    """逐端点请求 traffic.py（mock 可达时也请求一份做形状对照）。"""
    results: list[dict] = []
    comparisons: list[dict] = []
    for index, spec in enumerate(ours_specs):
        path = spec["path"]
        status, payload, headers = http_call(spec["method"], SERVER_URL + path, spec["body"])
        result = {
            "side": "traffic.py",
            "name": spec["name"],
            "method": spec["method"],
            "path_template": _template_path(spec["name"]),
            "path": path,
            "category": spec["category"],
            "status": status,
            "is_simulated": isinstance(payload, dict) and payload.get("is_simulated") is True,
            "top_keys": _top_keys(payload),
            "data_source": headers.get("x-traffic-data-source"),
            "payload": payload,
        }
        results.append(result)

        if not mock_reachable:
            continue
        mock_spec = mock_specs[index] if index < len(mock_specs) else None
        if mock_spec is None:
            comparisons.append({
                "name": spec["name"], "method": spec["method"],
                "path_template": result["path_template"], "our_path": path, "mock_path": None,
                "mock_status": None, "ours_status": status, "top_keys_equal": None,
                "mock_top_keys": [], "ours_top_keys": _top_keys(payload), "key_diffs": [],
            })
            continue
        mock_status, mock_payload, _ = http_call(mock_spec["method"], MOCK_URL + mock_spec["path"],
                                                 mock_spec["body"])
        comparison = {
            "name": spec["name"],
            "method": spec["method"],
            "path_template": result["path_template"],
            "our_path": path,
            "mock_path": mock_spec["path"],
            "mock_status": mock_status,
            "ours_status": status,
            "top_keys_equal": _top_keys(mock_payload) == _top_keys(payload) if status == 200 and mock_status == 200 else None,
            "mock_top_keys": _top_keys(mock_payload),
            "ours_top_keys": _top_keys(payload),
            "key_diffs": [],
        }
        if status == 200 and mock_status == 200:
            diffs: list[dict] = []
            _shape_diff(mock_payload, payload, "$", diffs)
            comparison["key_diffs"] = diffs
        comparisons.append(comparison)
    return results, comparisons


def _template_path(name: str) -> str:
    if name == "segments/{id}":
        return "/api/traffic/segments/{id}"
    if name == "segments/{id}/sources":
        return "/api/traffic/segments/{id}/sources"
    return name


# ---------------------------------------------------------------- 2) SSE


def check_sse() -> dict:
    result = {"ok": False, "event": None, "data_keys": [], "mock_event": None, "mock_data_keys": []}

    def read_events(base: str) -> tuple[str | None, list[str]]:
        request = urllib.request.Request(base + "/api/traffic/stream",
                                         headers={"Accept": "text/event-stream"})
        event_name = None
        data_keys: list[str] = []
        with urllib.request.urlopen(request, timeout=8) as response:
            while event_name is None or len(data_keys) < 1:
                line = response.readline().decode("utf-8", "replace").rstrip("\r\n")
                if not line:
                    continue
                if line.startswith("event:"):
                    event_name = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    raw = line.split(":", 1)[1].strip()
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        payload = {}
                    data_keys = _top_keys(payload)
                if event_name and data_keys:
                    break
        return event_name, data_keys

    try:
        result["event"], result["data_keys"] = read_events(SERVER_URL)
        result["ok"] = result["event"] == "traffic_snapshot" and "is_simulated" in result["data_keys"]
    except (urllib.error.URLError, OSError) as error:
        result["error"] = str(error)
    if mock_server_reachable():
        try:
            result["mock_event"], result["mock_data_keys"] = read_events(MOCK_URL)
        except (urllib.error.URLError, OSError) as error:
            result["mock_error"] = str(error)
    return result


def mock_server_reachable() -> bool:
    status, _, _ = http_call("GET", f"{MOCK_URL}/api/traffic/meta", timeout=2)
    return status == 200


# ---------------------------------------------------------------- 3) 三层回落


def check_fallback(our_segment_id: str) -> list[dict]:
    """把 work/*/out 临时挪开 → 逐端点请求 → 断言 200 / 不 500 / 回落站点包基线 → 还原。"""
    probes: list[dict] = []
    moved: list[tuple[Path, Path]] = []
    try:
        for relative in DROP_ENDPOINTS:
            source = ROOT / relative
            if not source.exists():
                continue
            target = BACKUP_DIR / relative.replace("/", "__")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(source), str(target))
            moved.append((source, target))

        def probe(name: str, method: str, path: str, body: dict | None = None) -> object:
            status, payload, headers = http_call(method, SERVER_URL + path, body)
            note = payload.get("note") if isinstance(payload, dict) else None
            probes.append({
                "name": name,
                "method": method,
                "path": path,
                "status": status,
                "is_simulated": isinstance(payload, dict) and payload.get("is_simulated") is True,
                "data_source": headers.get("x-traffic-data-source"),
                "note_excerpt": (note[:160] + "…") if isinstance(note, str) and len(note) > 160 else note,
                "top_keys": _top_keys(payload),
            })
            return payload

        segments = probe("segments", "GET", "/api/traffic/segments")
        fallback_id = our_segment_id
        if isinstance(segments, dict) and segments.get("segments"):
            fallback_id = str(segments["segments"][0].get("segment_id") or our_segment_id)
        probe("segments/{id}", "GET", f"/api/traffic/segments/{_quote(fallback_id)}")
        probe("segments/{id}/sources", "GET", f"/api/traffic/segments/{_quote(fallback_id)}/sources")
        probe("vehicles", "GET", "/api/traffic/vehicles")
        probe("overview", "GET", "/api/traffic/overview")
        probe("network", "GET", "/api/traffic/network")
        probe("meta", "GET", "/api/traffic/meta")
        probe("thresholds", "GET", "/api/traffic/thresholds")
        probe("factors", "GET", "/api/traffic/factors")
        probe("assimilation", "GET", "/api/traffic/assimilation")
        probe("alerts", "GET", "/api/traffic/alerts")
        probe("predict", "GET", f"/api/traffic/predict?segment_id={_quote(fallback_id)}&h=15")
        probe("ci-history", "GET", f"/api/traffic/ci-history?segment_id={_quote(fallback_id)}&points=12")
        probe("heat-matrix", "GET", "/api/traffic/heat-matrix?window=12&bucket=60")
        probe("context", "GET", "/api/traffic/context")
        probe("report/compare", "GET", "/api/traffic/report/compare")
        # 引擎路线缺失：推荐 / 定位如实 404（不编 ETA），此处记录状态而不强求 200
        probe("route/recommend", "POST", "/api/traffic/route/recommend",
              {"session_id": "S-fallback", "location": {"segment_id": fallback_id, "offset_m": 0}})
        probe("locate", "POST", "/api/traffic/locate", {"session_id": "S-fallback"})

        total = len([probe for probe in probes if probe["method"] == "GET"])
        ok = all(probe["status"] == 200 for probe in probes
                 if probe["method"] == "GET" and probe["name"] != "route/recommend")
        probes.insert(0, {
            "name": "_断言",
            "method": "ASSERT",
            "path": f"GET 端点全部 200（{total} 条）",
            "status": 200 if ok else 500,
            "details": {
                "get_all_200": ok,
                "any_500": any(probe["status"] == 500 for probe in probes),
                "fallback_segments": len((segments or {}).get("segments") or []) if isinstance(segments, dict) else 0,
                "fallback_source": "stations.baseline",
            },
        })
    finally:
        for source, target in reversed(moved):
            if target.exists():
                shutil.move(str(target), str(source))
    return probes


# ---------------------------------------------------------------- 4) 段号写死 / 复现性


def check_no_hardcoded_segment_ids() -> dict:
    text = TRAFFIC.read_text(encoding="utf-8")
    pattern = re.compile(r"SZ-[0-9]|SEG-[0-9]")
    hits = [
        {"line": number, "text": line.strip()}
        for number, line in enumerate(text.splitlines(), 1)
        if pattern.search(line)
    ]
    return {"pattern": pattern.pattern, "hits": hits, "passed": not hits}


def check_repeatability() -> list[dict]:
    checks: list[dict] = []
    for path in ("/api/traffic/segments", "/api/traffic/overview", "/api/traffic/network",
                 "/api/traffic/alerts", "/api/traffic/assimilation", "/api/traffic/thresholds"):
        _, first, _ = http_call("GET", SERVER_URL + path)
        _, second, _ = http_call("GET", SERVER_URL + path)
        same = _strip_ts(first) == _strip_ts(second)
        checks.append({"path": path, "identical_except_ts": same})
    return checks


# ---------------------------------------------------------------- 5) doc_gate


def _project_polyline_m(lon: float, lat: float, geometry: list) -> tuple[float, float]:
    """点到折线的（最短距离 m, 投影处弧长 m）；等距圆柱近似，与前端 `pointAtOffset` 同一套。

    只用于断言「标记点确实落在自己那条 `steps[].geometry` 的正确里程上」：
    只比距离不够 —— 整段几何只有两个端点时，**错的那一端距离也是 0**（镜像 bug 就这么漏过去），
    所以必须再比弧长（`trim_head_m` / `length_m - trim_tail_m`）。
    """
    if not geometry:
        return float("inf"), float("nan")
    lon = float(lon)
    lat = float(lat)
    kx = 111320.0 * math.cos(math.radians(lat))
    ky = 110540.0
    points = [
        ((float(point[0]) - lon) * kx, (float(point[1]) - lat) * ky)
        for point in geometry
        if len(point) >= 2
    ]
    if not points:
        return float("inf"), float("nan")
    if len(points) == 1:
        return math.hypot(points[0][0], points[0][1]), 0.0
    best_dist = float("inf")
    best_arc = 0.0
    walked = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        dx, dy = x2 - x1, y2 - y1
        span = math.hypot(dx, dy)
        ratio = 0.0 if span == 0 else max(0.0, min(1.0, -(x1 * dx + y1 * dy) / (span * span)))
        dist = math.hypot(x1 + ratio * dx, y1 + ratio * dy)
        if dist < best_dist:
            best_dist = dist
            best_arc = walked + ratio * span
        walked += span
    return best_dist, best_arc


def _point_to_polyline_m(lon: float, lat: float, geometry: list) -> float:
    """点到折线的最短距离（米），只取 `_project_polyline_m` 的距离分量（报告展示用）。"""
    return _project_polyline_m(lon, lat, geometry)[0]


def check_route_contract_shape() -> dict:
    """箭头方向专项硬断言：**契约 `/route/recommend` 的响应里不得出现 `steps` / `start_point`**。

    为什么要有这条闸门（方案 §2 补充 / IKNAUI 箭头方向）：
    引擎产物 `work/engine/out/real/routes.json` 的每条路线都带 `steps[]`（逐段行进几何）与
    `arrival_route.start_point`，用于前端画箭头、标起点；但**契约 §七 的路线对象是白名单形状**
    （`path_id` / `segments` / `eta_min` / `length_m` / `dropoff_point` / `walk_min`）。
    `/route/recommend` 的实现是 `_decorate_route_response()` 整包透传引擎请求，
    只要有人把 `_route_body_without_steps()` 那一步删了/绕过，产物里的几何就会瞬间漏进契约响应 ——
    所以这里实调一次端点，按字段集合比对，发现即判失败（与「段号无写死」同等重要的防回归闸门）。
    权威几何的正路是非契约只读端点 `GET /api/traffic/route/{request_id}/steps`，在这里顺带做正向验证。
    """
    forbidden = ("steps", "start_point")
    route_keys = ("arrival_route", "departure_route", "pickup_route")
    result: dict = {
        "passed": True,
        "forbidden_fields": list(forbidden),
        "findings": [],
        "options_status": None,
        "recommend_status": None,
        "steps_endpoint": None,
        "steps_routes": [],
        "contract_trim": {},
        "plan_markers": None,
        "request_id": None,
        "skipped": None,
    }
    status, options, _ = http_call("GET", SERVER_URL + "/api/traffic/route/options")
    result["options_status"] = status
    if status != 200 or not isinstance(options, dict) or not options.get("options"):
        result["skipped"] = f"路线产物缺失（/route/options → {status}），无法实调 recommend"
        return result
    first = options["options"][0]
    result["request_id"] = first.get("request_id")
    body = {
        "session_id": first.get("session_id"),
        "od_id": first.get("od_id"),
        "driver_type": first.get("driver_type"),
    }
    status, recommend, _ = http_call("POST", SERVER_URL + "/api/traffic/route/recommend", body)
    result["recommend_status"] = status
    if status != 200 or not isinstance(recommend, dict):
        result["passed"] = False
        result["findings"].append(f"/route/recommend 未 200（{status}），无法验证契约形状")
        return result
    containers = [("arrival_route", recommend.get("arrival_route")),
                  ("departure_route", recommend.get("departure_route")),
                  ("pickup_route", recommend.get("pickup_route"))]
    containers += [(f"alternatives[{index}]", item)
                   for index, item in enumerate(recommend.get("alternatives") or [])]
    checked = 0
    for name, route in containers:
        if not isinstance(route, dict):
            continue
        checked += 1
        leaked = [key for key in forbidden if key in route]
        if leaked:
            result["findings"].append(f"/route/recommend 的 {name} 出现了契约外字段：{'、'.join(leaked)}")
    result["routes_checked"] = checked
    if not checked:
        result["findings"].append("/route/recommend 没端出任何路线对象，断言空转")
    # 断言 2（2026-10-29 队长收口要求）：**剥字段不能剥多了** ——
    # 大屏裁剪箭头靠的就是契约 `arrival_route.trim_head_m / trim_tail_m`（它们和 `steps` 同在
    # 一份引擎路线上，被 `_route_body_without_steps()` 一起剥掉的风险是真实存在的）。
    # 剥多了前端不报错，只会把箭头画进被裁掉的区段 —— 典型静默劣化，必须由后端门禁守住。
    trim_info: dict = {"present": None, "trim_head_m": None, "trim_tail_m": None, "length_m": None}
    arrival_contract = recommend.get("arrival_route")
    if isinstance(arrival_contract, dict):
        trim_head = arrival_contract.get("trim_head_m")
        trim_tail = arrival_contract.get("trim_tail_m")
        length_m = arrival_contract.get("length_m")
        trim_info.update(
            present=[key for key in ("trim_head_m", "trim_tail_m") if key in arrival_contract] or None,
            trim_head_m=trim_head,
            trim_tail_m=trim_tail,
            length_m=length_m,
        )
        missing = [key for key in ("trim_head_m", "trim_tail_m") if key not in arrival_contract]
        if missing:
            result["findings"].append(
                f"契约 arrival_route 缺 {'、'.join(missing)}（剥 steps 时剥多了：大屏裁剪箭头靠这两个值）"
            )
        elif trim_head is None or trim_tail is None:
            result["findings"].append(
                f"契约 arrival_route 的 trim_head_m / trim_tail_m 是 null（{trim_head} / {trim_tail}）"
            )
        elif isinstance(length_m, (int, float)):
            summed = float(trim_head) + float(trim_tail)
            trim_info["trim_sum_m"] = round(summed, 3)
            if not summed < float(length_m):
                result["findings"].append(
                    f"契约 arrival_route 的 trim_head_m + trim_tail_m = {summed:.1f} m 不小于 "
                    f"length_m = {float(length_m):.1f} m（箭头会被裁进无路段区）"
                )
    result["contract_trim"] = trim_info
    # 正向对照：权威几何必须能从非契约端点拿到（否则前端又得自己猜方向）
    if result["request_id"]:
        status, steps_payload, _ = http_call(
            "GET", f"{SERVER_URL}/api/traffic/route/{result['request_id']}/steps"
        )
        steps_info = {"status": status}
        if status == 200 and isinstance(steps_payload, dict):
            arrival = (steps_payload.get("routes") or {}).get("arrival_route") or {}
            steps_info["arrival_step_count"] = arrival.get("step_count") or len(arrival.get("steps") or [])
            steps_info["has_geometry"] = bool((arrival.get("steps") or [{}])[0].get("geometry"))
        result["steps_endpoint"] = steps_info
        if steps_info.get("status") != 200 or not steps_info.get("arrival_step_count"):
            result["findings"].append(
                f"/route/{{request_id}}/steps 拿不到权威几何（status={steps_info.get('status')}）"
            )
        # 正向对照 2（2026-10-29 队长补的两个口子，一起进闸门）：
        # ① `/route/plan` 的 `destination_point` 与 `start_point` 字段逐字同构（终点标记有权威坐标，
        #   前端不必自己折 `offset_m`）；② `routes[].trim_head_m` / `trim_tail_m` 不是 null。
        arrival_steps = (steps_payload.get("routes") or {}).get("arrival_route", {}).get("steps") or []
        if len(arrival_steps) >= 2:
            head = arrival_steps[0]
            tail = arrival_steps[-1]
            origin_spec = {
                "segment_id": head.get("segment_id"),
                "offset_m": round(float(head.get("length_m") or 0.0) * 0.4, 1),
            }
            destination_spec = {
                "segment_id": tail.get("segment_id"),
                "offset_m": round(float(tail.get("length_m") or 0.0) * 0.4, 1),
            }
            status, plan, _ = http_call(
                "POST",
                SERVER_URL + "/api/traffic/route/plan",
                {"origin": origin_spec, "destination": destination_spec},
            )
            markers = {"status": status, "origin": origin_spec, "destination": destination_spec}
            if status == 200 and isinstance(plan, dict) and plan.get("routes"):
                first_plan = plan.get("routes")[0]
                start_marker = plan.get("start_point") or {}
                dest_marker = plan.get("destination_point") or {}
                markers["destination_point_keys"] = sorted(dest_marker)
                markers["symmetric"] = (set(start_marker) - {"note"}) == (set(dest_marker) - {"note"})
                markers["destination_lonlat"] = [dest_marker.get("lon"), dest_marker.get("lat")]
                markers["route_trim"] = [first_plan.get("trim_head_m"), first_plan.get("trim_tail_m")]
                if not markers["symmetric"]:
                    result["findings"].append(
                        "/route/plan 的 destination_point 与 start_point 字段不同构："
                        f"{markers['destination_point_keys']}"
                    )
                if dest_marker.get("lon") is None or dest_marker.get("lat") is None:
                    result["findings"].append("/route/plan 的 destination_point 缺 lon/lat")
                if markers["route_trim"] == [None, None]:
                    result["findings"].append("/route/plan 的 routes[].trim_head_m / trim_tail_m 是 null")
            else:
                markers["skipped"] = f"/route/plan → {status}（本条不阻断，形状闸门以 recommend 为准）"
            result["plan_markers"] = markers
        # 断言 3（2026-10-29 队长最后一轮）：steps 端点**每条 route** 的 `start_point` /
        # `destination_point` 必须非空，且 `lon/lat` 落在 `steps[0]` / `steps[-1]` 的 geometry 折线上
        # （偏差 < 1 m）。理由：这两个字段是「前端不必再按 offset_m 折 coords」的唯一正路，
        # 一旦哪天被悄悄置回 null，镜像画法就会复发 —— 所以必须有人守着。
        routes_map = (steps_payload.get("routes") if isinstance(steps_payload, dict) else None) or {}
        steps_routes: list[dict] = []
        route_entries: list[tuple[str, Any]] = []
        for key_name, value in routes_map.items():
            if isinstance(value, list):  # alternatives[]：每条备选路也要有两端标记
                route_entries.extend(
                    (f"{key_name}[{index}]", item) for index, item in enumerate(value)
                )
            else:
                route_entries.append((str(key_name), value))
        for route_name, route_obj in route_entries:
            if not isinstance(route_obj, dict):
                continue
            route_steps = route_obj.get("steps") or []
            start_marker = route_obj.get("start_point") or {}
            dest_marker = route_obj.get("destination_point") or {}
            item = {
                "route": route_name,
                "step_count": len(route_steps),
                "start_lonlat": [start_marker.get("lon"), start_marker.get("lat")],
                "destination_lonlat": [dest_marker.get("lon"), dest_marker.get("lat")],
                "start_dev_m": None,
                "destination_dev_m": None,
                "start_arc_m": None,
                "destination_arc_m": None,
            }
            if not route_steps:
                item["note"] = "无 steps（该 route 未算，不判）"
                steps_routes.append(item)
                continue
            if start_marker.get("lon") is None or start_marker.get("lat") is None:
                result["findings"].append(f"steps 端点 {route_name} 的 start_point 缺 lon/lat（被悄悄置空）")
                steps_routes.append(item)
                continue
            head_step = route_steps[0]
            start_dev, start_arc = _project_polyline_m(
                start_marker["lon"], start_marker["lat"], head_step.get("geometry") or []
            )
            item["start_dev_m"] = round(start_dev, 3)
            item["start_arc_m"] = round(start_arc, 3)
            expect_start_arc = float(head_step.get("trim_head_m") or 0.0)
            if item["start_dev_m"] > 1.0:
                result["findings"].append(
                    f"steps 端点 {route_name} 的 start_point 偏离 steps[0] 折线 {item['start_dev_m']} m（> 1 m）"
                )
            elif abs(start_arc - expect_start_arc) > 1.0:
                result["findings"].append(
                    f"steps 端点 {route_name} 的 start_point 落在 steps[0] 折线弧长 {start_arc:.1f} m 处，"
                    f"应为 {expect_start_arc:.1f} m（≈ trim_head_m）—— 位置镜像了"
                )
            if dest_marker.get("lon") is None or dest_marker.get("lat") is None:
                result["findings"].append(f"steps 端点 {route_name} 的 destination_point 缺 lon/lat（被悄悄置空）")
            else:
                tail_step = route_steps[-1]
                dest_dev, dest_arc = _project_polyline_m(
                    dest_marker["lon"], dest_marker["lat"], tail_step.get("geometry") or []
                )
                item["destination_dev_m"] = round(dest_dev, 3)
                item["destination_arc_m"] = round(dest_arc, 3)
                expect_dest_arc = float(tail_step.get("length_m") or 0.0) - float(
                    tail_step.get("trim_tail_m") or 0.0
                )
                if item["destination_dev_m"] > 1.0:
                    result["findings"].append(
                        f"steps 端点 {route_name} 的 destination_point 偏离 steps[-1] 折线 "
                        f"{item['destination_dev_m']} m（> 1 m）"
                    )
                elif abs(dest_arc - expect_dest_arc) > 1.0:
                    result["findings"].append(
                        f"steps 端点 {route_name} 的 destination_point 落在 steps[-1] 折线弧长 {dest_arc:.1f} m 处，"
                        f"应为 {expect_dest_arc:.1f} m（≈ length_m - trim_tail_m）—— 位置镜像了"
                    )
            steps_routes.append(item)
        result["steps_routes"] = steps_routes
        if not steps_routes:
            result["findings"].append("steps 端点没端出任何 route（两端标记断言空转）")
    result["passed"] = not result["findings"]
    return result


def run_doc_gate() -> dict:
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.run(
        [sys.executable, "scripts/doc_gate.py"],
        cwd=str(ROOT),
        capture_output=True,
        env=environment,
        timeout=180,
    )
    stdout = process.stdout.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
    stderr = process.stderr.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
    # 业主红线（开发规范 §13.6）：记录里不写本机路径 —— 报告里统一脱敏成 <repo>
    repo_text = str(ROOT)
    stdout = stdout.replace(repo_text, "<repo>").replace(repo_text.replace("\\", "/"), "<repo>")
    stderr = stderr.replace(repo_text, "<repo>").replace(repo_text.replace("\\", "/"), "<repo>")
    return {"exit_code": process.returncode, "stdout": stdout, "stderr": stderr}


# ---------------------------------------------------------------- 报告（对照快照 + 自检记录）

EXPECTED_VALUE_DIFFERENCES = [
    ("数据源不同", "mock 取前端站点包（站点 Z 的 SZ 段 / 61 段真 OSM 路网占位基线 + 演示抖动）；"
                   "traffic.py 取运行产物（感知 / 孪生 / 引擎 / 站点包），段号、条数、取值本就不同。"
                   "**形状对照只比键集，不比取值。**"),
    ("三层回落的层次职责", "engine routes.json 是**路线产物**（没有路段指标字段），所以 `/segments` 的回落链是"
                          " video → twin → stations 基线；engine routes 用于 route/recommend 与 locate，"
                          "缺产物时这两端点如实 404 + note（不代算 ETA）。这不是跳过一层，是该层本来就没有路段指标。"),
    ("route/recommend", "traffic.py 按契约 §二 端出引擎产物（含 od_id / reroute / quota / factors_note，"
                        "arrival_route / alternatives 带 edges）；mock 是前端站点包的演示骨架（无上述契约字段）。"
                        "以契约 §二 为准，差异已登记。"),
    ("network", "mock 有真 OSM 几何 coords；traffic.py 的站点包 network.json 只有占位节点坐标（无经纬度），"
                "如实给空折线 coords: []，不编几何。"),
    ("上游产物自身的口径问题（如实透传，不改数）", "运行产物里 video 链路的 ci=0 却给出 level=4（上游指标 / "
                                                  "判级口径不一致），traffic.py 按「只端数据」原样透出，"
                                                  "不替上游改数；并排时 SEG-003 的 delta 会体现该差异。"),
    ("站点身份与运行产物的命名空间", "meta / network 的站点身份取 `work/twin/site-ranges.json` 的 default_site"
                                    "（zhaoqingdong / 肇庆东站），而当前运行产物是样例网的段号命名空间——"
                                    "两者不一致是数据管线现状，接口层不硬编站点名、也不改数据。"),
    ("vehicles", "`work/twin/out/vehicles.json` 是样例值（ts=2026-01-01、经纬度为占位），接口层如实透传，"
                 "不拿合成车顶替；该端点二期下线。"),
    ("heat-matrix / ci-history / predict", "接口层没有时序历史 / CI 预测产物：heat-matrix 只有当前桶有值、"
                                           "ci-history 只回当前单点、predict 点集为空；三者都带 note 说明，"
                                           "顶格键因此比 mock 多一个 note。"),
    ("context", "天气 / 气温 / 能见度没有数据源：字段保留、值为 null 并在 note 说明；"
                "mock 的天气是站点包演示值。"),
    ("alerts", "接口层没有预置告警剧本，按既有口径从 segments 快照派生（level ≥ 3）；"
               "mock 的 4 条四态告警来自站点包演示剧本。告警元素的可选留痕字段（channels / dispatch_at / "
               "dispatch_ratio_pct / writeback）在真正下发 / 回写后同样出现——对照表里的「alerts(下发后)」"
               "一行就是两边各做一次下发 + 回写后的形状比对。"),
    ("thresholds", "ci_weights 的 key 用站点包 grading.weights 的指标名（x / v / L_q / T_d），"
                   "mock 前端展示口径把排队项写成 k；rows 的刻度用站点包 level_bounds（v 是 km/h，mock 是速度比）。"),
    ("unimplemented", "POST /factors、POST /scenario、POST /scenario/reset 是写快照端点：接口层只读快照，"
                      "按本单口径如实 404 + note（不假装成功）。mock 侧是演示内存态。"),
    ("写端点演示态", "plan/dispatch / plan/ack / alerts/reset / factors/reset 已实现，但演示态存在服务进程内存里"
                     "（重启复位，与 mock 同性质）；README §二 要求正式落库留痕，属后续落库单。"),
    ("未匹配方法", "照搬 mock 的纪律：未匹配路径 / 未注册方法一律 404（FastAPI 默认 405 已统一改 404），"
                   "GET 打 POST-only 端点返回 404 而不是 405。"),
    ("locate / report/compare", "契约 §七 列了这两个端点、mock 路由表没有：traffic.py 已实现（locate 取引擎"
                                "孪生真值；report 无报表产物 → 空壳 + note），mock 侧 404。"),
]


def _md_escape(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def write_snapshot_report(mock_reachable: bool, comparisons: list[dict],
                          sse: dict, results: list[dict]) -> None:
    required_three = ["segments", "overview", "network"]
    top_equal = {comparison["name"]: comparison["top_keys_equal"] for comparison in comparisons}
    three_ok = all(top_equal.get(name) is True for name in required_three)
    comparable = [comparison for comparison in comparisons
                  if comparison["ours_status"] == 200 and comparison["mock_status"] == 200]
    all_top_equal = all(comparison["top_keys_equal"] for comparison in comparable) if comparable else False

    payload = {
        "issue": "IKMF1T",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "method": (
            "实跑对照：同一路径分别请求 vite mock（http://127.0.0.1:5173）与接口层 traffic.py"
            f"（{SERVER_URL}），比对顶格键与嵌套键集；取值不参与比对（数据源不同）。"
        ),
        "mock_reachable": mock_reachable,
        "required_three_top_level_equal": three_ok,
        "comparable_endpoint_count": len(comparable),
        "all_comparable_top_level_equal": all_top_equal,
        "endpoints": [
            {
                "name": comparison["name"],
                "method": comparison["method"],
                "path": comparison["path_template"],
                "mock_status": comparison["mock_status"],
                "ours_status": comparison["ours_status"],
                "top_keys_equal": comparison["top_keys_equal"],
                "mock_top_keys": comparison["mock_top_keys"],
                "ours_top_keys": comparison["ours_top_keys"],
                "key_diffs": comparison["key_diffs"],
            }
            for comparison in comparisons
        ],
        "sse": sse,
        "value_differences": [{"title": title, "detail": detail}
                              for title, detail in EXPECTED_VALUE_DIFFERENCES],
        "traffic_endpoint_status": [
            {"name": result["name"], "method": result["method"],
             "category": result["category"], "status": result["status"]}
            for result in results
        ],
    }
    SNAPSHOT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )

    lines: list[str] = []
    lines.append("# 与 mock 的响应形状对照快照（IKMF1T）\n")
    lines.append(f"- 生成时间：{payload['generated_at']}")
    lines.append(f"- 对照方法：{payload['method']}")
    lines.append(f"- mock 可达：{'是' if mock_reachable else '否（未做实时对照）'}")
    lines.append("- 代码：[traffic.py](traffic.py)")
    lines.append("")
    lines.append("## 一、结论\n")
    if mock_reachable:
        lines.append(f"- 自检要求的 3 个形状对照端点顶格键一致（segments / overview / network）："
                     f"**{'✅ 一致' if three_ok else '❌ 不一致'}**")
        differing = [comparison["name"] for comparison in comparable
                     if comparison["top_keys_equal"] is False]
        lines.append(f"- 两边都 200 的 {len(comparable)} 个可对照端点中，顶格键与 mock 一致的有 "
                     f"{len(comparable) - len(differing)} 个；有差异的是："
                     + ("**无**" if not differing else "、".join(differing) + "（差异均已逐条登记，见第四节）"))
    else:
        lines.append("- vite mock 未启动，未做实时对照。静态提取方法：读 "
                     "`work/frontend/ui-vue/src/mock/traffic.ts` 的 `handleTraffic()` 路由表与各 `build*()` "
                     "返回对象，逐端点取顶格键（等价于本脚本对 mock 响应做 `sorted(payload.keys())`）。")
    lines.append("")
    lines.append("## 二、逐端点对照表\n")
    lines.append("| 端点 | 方法 | mock 状态 | traffic.py 状态 | 顶格键一致 | 键级差异 |")
    lines.append("|---|---|---|---|---|---|")
    for comparison in comparisons:
        if comparison["mock_status"] == 0:
            continue
        diff_text = "无"
        if comparison["key_diffs"]:
            diff_text = "<br>".join(
                f"`{diff['path']}`"
                + (f" 仅 mock: {', '.join(diff['only_mock'])}" if diff["only_mock"] else "")
                + (f" 仅 traffic.py: {', '.join(diff['only_ours'])}" if diff["only_ours"] else "")
                for diff in comparison["key_diffs"]
            )
        same = "—" if comparison["top_keys_equal"] is None else ("✅" if comparison["top_keys_equal"] else "❌")
        lines.append(
            f"| {comparison['name']} | {comparison['method']} | {comparison['mock_status']} | "
            f"{comparison['ours_status']} | {same} | {_md_escape(diff_text)} |"
        )
    lines.append("")
    lines.append("### 三个必对端点的顶格键\n")
    for name in required_three:
        matched = next((comparison for comparison in comparisons if comparison["name"] == name), None)
        if matched is None:
            continue
        lines.append(f"- **{name}**")
        lines.append(f"  - mock：`{matched['mock_top_keys']}`")
        lines.append(f"  - traffic.py：`{matched['ours_top_keys']}`")
    lines.append("")
    lines.append("## 三、SSE\n")
    lines.append(f"- traffic.py：event=`{sse.get('event')}`，data 顶格键 `{sse.get('data_keys')}`")
    lines.append(f"- mock：event=`{sse.get('mock_event')}`，data 顶格键 `{sse.get('mock_data_keys')}`")
    lines.append("")
    lines.append("## 四、形状 / 取值差异说明（数据源不同，逐条登记）\n")
    for title, detail in EXPECTED_VALUE_DIFFERENCES:
        lines.append(f"- **{title}**：{detail}")
    lines.append("")
    lines.append("## 五、traffic.py 端点状态汇总\n")
    lines.append("| 端点 | 方法 | 分类 | 状态 |")
    lines.append("|---|---|---|---|")
    for result in results:
        lines.append(f"| {result['name']} | {result['method']} | {result['category']} | {result['status']} |")
    lines.append("")
    SNAPSHOT_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_check_log(server: dict, results: list[dict], sse: dict, fallback: list[dict],
                    hardcoded: dict, repeatability: list[dict], doc_gate: dict,
                    mock_reachable: bool, cleanup_actions: list[str],
                    doc_gate_recheck: dict | None = None,
                    contract_shape: dict | None = None) -> None:
    required = [result for result in results if result["category"] in ("required-get", "required-post")]
    ok = [result for result in required if result["status"] == 200]
    unimplemented = [result for result in results if result["category"] == "unimplemented"]
    all_simulated = all(result["is_simulated"] for result in results if result["status"] == 200)
    any_500 = [result for result in results if result["status"] == 500]

    lines: list[str] = []
    lines.append("# IKMF1T 自检记录（真跑输出）\n")
    lines.append(f"- 生成时间：{time.strftime('%Y-%m-%dT%H:%M:%S%z')}")
    lines.append(f"- Python：{sys.version.split()[0]}")
    lines.append(f"- 服务：{server['mode']}（{SERVER_URL}）")
    lines.append(f"- 形状对照：[对照快照.md](对照快照.md) / [对照快照.json](对照快照.json)")
    lines.append("")
    lines.append("## 〇、交接信息：本工作树后端启动命令与端口（2026-10-29）\n")
    lines.append(
        "- **本工作树（D:/hubflow/_arrows）后端端口固定 8001**，启动命令：\n"
        f"  `python work/assembly/traffic.py --port {SERVER_PORT}`"
        "（工作目录必须是本工作树根，traffic.py 按相对路径读 `work/*/out/` 产物）"
    )
    lines.append(
        "- 自检/联调一律用 `python work/assembly/selfcheck_ikmf1t.py`（默认就是 8001），"
        "或显式 `--api-base http://127.0.0.1:8001` / `HUBFLOW_API_BASE=http://127.0.0.1:8001`。"
    )
    lines.append(
        "- **别指 8000**：那是主工作树（D:/hubflow/hubflow）的实例，代码是旧的 —— "
        "新端点（`/route/{request_id}/steps`、`/route/plan` 的 `destination_point`）会在那里 404，"
        "本轮 dev-B / dev-C 都因此误判过「实现缺失」。"
    )
    lines.append(
        "- 复现旧坑的判断方法：`/api/traffic/route/REQ-REAL-0001/steps` 应返回 200（8000 上是 404）。"
    )
    lines.append(
        "- **重启机器后 8001 不会自己起来**：先按上面的命令手动拉起，再跑自检"
        "（脚本发现端口可达会复用，不可达才自己起）。"
    )
    lines.append(
        "- 路段方向口径自检（与接口层无关，可单独跑）："
        "`python work/engine/tools/audit_segment_direction.py --site zhaoqingdong`、"
        "`--site guangzhounan`；默认报告名带站点（`work/engine/tools/out/segment_direction_audit_<site>.json`），"
        "两个站各跑一次**不会互相覆盖**。注意参数是 `--site`，没有 `--station`。"
    )
    lines.append("")
    lines.append("## 一、端点全绿\n")
    lines.append(f"- 必需端点（契约 §七 + mock 路由表）：**{len(ok)}/{len(required)} 状态 200**"
                 f"{' ✅' if len(ok) == len(required) else ' ❌'}")
    lines.append(f"- 所有 200 响应 `is_simulated=true`：{'✅ 是' if all_simulated else '❌ 否'}")
    lines.append(f"- 出现 500 的端点：{'无 ✅' if not any_500 else '、'.join(item['name'] for item in any_500) + ' ❌'}")
    if unimplemented:
        lines.append("- 未实现写端点（如实 404 + note，不假装成功）："
                     + "、".join(f"`POST {item['name']}` → {item['status']}" for item in unimplemented))
    if cleanup_actions:
        lines.append("- 对照后复位演示态：" + "；".join(f"`{action}`" for action in cleanup_actions))
    lines.append("")
    lines.append("| 端点 | 方法 | 分类 | 状态 | 数据源（响应头） | 顶格键 |")
    lines.append("|---|---|---|---|---|---|")
    for result in results:
        lines.append(
            f"| {result['name']} | {result['method']} | {result['category']} | {result['status']} | "
            f"{_md_escape(result['data_source'] or '—')} | {_md_escape(', '.join(result['top_keys']))} |"
        )
    lines.append("")
    lines.append("## 二、三层回落（把 work/*/out 挪开后实测）\n")
    lines.append(f"- 挪开的产物目录：{'、'.join(f'`{item}`' for item in DROP_ENDPOINTS)}")
    lines.append("- 断言：GET 端点仍全部 200；不得出现 500；`/segments` 回落站点包静态基线（source=null / level=0 / 带 note）")
    lines.append("")
    lines.append("| 步骤 | 方法 | 路径 | 状态 | 数据源（响应头） | note（截断） |")
    lines.append("|---|---|---|---|---|---|")
    for probe in fallback:
        if probe.get("method") == "ASSERT":
            details = probe.get("details") or {}
            lines.append(
                f"| {probe['name']} | — | {probe['path']} | {'✅' if probe['status'] == 200 else '❌'} | — | "
                f"GET 全 200={details.get('get_all_200')}，任何 500={details.get('any_500')}，"
                f"回落段数={details.get('fallback_segments')} |"
            )
            continue
        lines.append(
            f"| {probe['name']} | {probe['method']} | {_md_escape(probe['path'])} | {probe['status']} | "
            f"{_md_escape(probe['data_source'] or '—')} | {_md_escape(probe['note_excerpt'] or '—')} |"
        )
    lines.append("")
    lines.append("## 三、段号写死扫描\n")
    lines.append(f"- 正则：`{hardcoded['pattern']}`，扫描 `work/assembly/traffic.py`")
    lines.append(f"- 命中数：**{len(hardcoded['hits'])}**"
                 f"{' ✅ 无写死段号' if hardcoded['passed'] else ' ❌ 有写死段号'}")
    if hardcoded["hits"]:
        for hit in hardcoded["hits"]:
            lines.append(f"  - 第 {hit['line']} 行：`{hit['text']}`")
    lines.append("")
    lines.append("## 三点五、契约响应不得出现 `steps` / `start_point`（箭头方向专项）\n")
    if contract_shape is None:
        lines.append("- （本次运行未采集该断言）")
    elif contract_shape.get("skipped"):
        lines.append(f"- 跳过：{contract_shape['skipped']}")
    else:
        verdict = "✅ 通过" if contract_shape["passed"] else "❌ 失败"
        lines.append(
            f"- 断言：`POST /route/recommend`（status={contract_shape['recommend_status']}，"
            f"实检 {contract_shape.get('routes_checked', 0)} 条路线对象）的响应里**不得**出现 "
            f"`{'` / `'.join(contract_shape['forbidden_fields'])}` —— {verdict}"
        )
        steps_info = contract_shape.get("steps_endpoint") or {}
        lines.append(
            f"- 正向对照：`GET /api/traffic/route/{contract_shape.get('request_id')}/steps` → "
            f"status={steps_info.get('status')}，arrival_route 段数={steps_info.get('arrival_step_count')}，"
            f"首段带几何={steps_info.get('has_geometry')}"
        )
        if contract_shape["findings"]:
            for finding in contract_shape["findings"]:
                lines.append(f"  - ❌ {finding}")
        else:
            lines.append(
                "- 理由：契约 §七 的路线对象是白名单形状，几何只能走非契约只读端点；"
                "`_decorate_route_response()` 整包透传引擎请求，一旦有人删掉剥字段那一步就会漏。"
            )
        trim_info = contract_shape.get("contract_trim") or {}
        if trim_info.get("present") is not None:
            lines.append(
                f"- 契约裁切字段断言（`arrival_route` 必须含 `trim_head_m`/`trim_tail_m` 且非 null，"
                f"且两者之和 < `length_m`）：trim_head_m={trim_info.get('trim_head_m')} + "
                f"trim_tail_m={trim_info.get('trim_tail_m')} = {trim_info.get('trim_sum_m')} m "
                f"< length_m={trim_info.get('length_m')} m"
            )
        steps_routes = contract_shape.get("steps_routes") or []
        if steps_routes:
            described = "；".join(
                f"{item['route']}: steps={item['step_count']}, "
                f"start={item['start_lonlat']}→折线偏差 {item['start_dev_m']} m / 弧长 {item['start_arc_m']} m, "
                f"destination={item['destination_lonlat']}→折线偏差 {item['destination_dev_m']} m / "
                f"弧长 {item['destination_arc_m']} m"
                for item in steps_routes
            )
            lines.append(
                f"- 两端标记断言（每条 route 的 `start_point`/`destination_point` 非空、落在"
                f"`steps` 首末折线上且弧长等于 `trim_head_m` / `length_m - trim_tail_m`，阈值 1 m）：{described}"
            )
    lines.append("")
    lines.append("## 四、可复现（同一请求两次，除时间戳外一致）\n")
    for item in repeatability:
        lines.append(f"- `{item['path']}`：{'✅ 一致' if item['identical_except_ts'] else '❌ 不一致'}")
    lines.append("")
    lines.append("## 五、与 mock 的形状对照\n")
    if mock_reachable:
        lines.append("- mock 可达：已对同一批路径做实时逐端点对照，结论与差异清单见 [对照快照.md](对照快照.md)。")
    else:
        lines.append("- mock 不可达：未做实时对照；静态提取方法（读 mock 路由表与 build*() 返回对象的顶格键）"
                     "见 [对照快照.md](对照快照.md) 第一节。")
    lines.append("")
    lines.append("## 六、SSE\n")
    lines.append(f"- traffic.py：event=`{sse.get('event')}`，data 顶格键 `{sse.get('data_keys')}`"
                 f"（{'✅' if sse.get('ok') else '❌'} 事件名与信封）")
    if mock_reachable:
        lines.append(f"- mock：event=`{sse.get('mock_event')}`，data 顶格键 `{sse.get('mock_data_keys')}`")
    lines.append("")
    lines.append("## 七、仓库门禁 doc_gate\n")
    lines.append("- 命令：`python scripts/doc_gate.py`（8 组）")
    lines.append(f"- 首次运行（对照快照 / 自检记录尚未写全时）：退出码 **{doc_gate['exit_code']}**")
    if doc_gate_recheck is not None:
        lines.append(f"- 复检（全部交付文件就位后）：退出码 **{doc_gate_recheck['exit_code']}**"
                     f"{' ✅ 8/8 通过' if doc_gate_recheck['exit_code'] == 0 else ' ❌ 未通过'}")
        shown = doc_gate_recheck
    else:
        shown = doc_gate
    lines.append("")
    lines.append("```text")
    lines.append((shown["stdout"].strip() or "(无输出)")[-4000:])
    lines.append("```")
    if shown["stderr"].strip():
        lines.append("")
        lines.append("```text")
        lines.append(shown["stderr"].strip()[-800:])
        lines.append("```")
    lines.append("")
    CHECKLOG_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description="IKMF1T 自检 + mock 形状对照")
    parser.add_argument("--skip-fallback", action="store_true", help="跳落三层回落实测")
    parser.add_argument(
        "--api-base",
        default=None,
        help=(
            "接口层地址（默认 http://127.0.0.1:8001 = 本工作树；也可用环境变量 HUBFLOW_API_BASE）。"
            "主工作树（D:/hubflow/hubflow）的实例在 8000 —— 指错端口就会复用到旧进程，"
            "把新端点误判成 404。"
        ),
    )
    args = parser.parse_args()
    if args.api_base:
        global SERVER_URL, SERVER_PORT
        SERVER_URL = args.api_base.rstrip("/")
        SERVER_PORT = _port_of(SERVER_URL)
    print(f"     接口层地址：{SERVER_URL}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[1/6] 启动 / 复用接口层服务 ...")
    process, reused = start_server()
    server = {
        "mode": (
            f"复用已在跑的 {SERVER_URL} 服务"
            if reused
            else f"本脚本拉起 traffic.py（端口 {SERVER_PORT}）"
        ),
        "api_base": SERVER_URL,
    }
    try:
        mock_reachable = mock_server_reachable()
        print(f"     mock(vite) 可达：{mock_reachable}")

        our_segment_id, our_alert_id, _ = resolve_ids(SERVER_URL)
        print(f"     traffic.py 首段={our_segment_id!r} 首告警={our_alert_id!r}")
        ours_specs = endpoint_specs("ours", our_segment_id, our_alert_id)
        mock_specs: list[dict] = []
        if mock_reachable:
            mock_segment_id, mock_alert_id, _ = resolve_ids(MOCK_URL)
            print(f"     mock 首段={mock_segment_id!r} 首告警={mock_alert_id!r}")
            mock_specs = endpoint_specs("mock", mock_segment_id, mock_alert_id)
            # 两边端点顺序对齐（告警是否存在会影响插入位置，按 name 重排）
            by_name = {spec["name"]: spec for spec in mock_specs}
            mock_specs = [by_name.get(spec["name"], spec) for spec in ours_specs]

        print("[2/6] 端点全绿 + mock 形状对照 ...")
        results, comparisons = check_endpoints(ours_specs, mock_reachable, mock_specs)
        cleanup_actions = cleanup_runtime_states(mock_reachable)
        print("     演示态复位：" + "；".join(cleanup_actions))
        print("[3/6] SSE ...")
        sse = check_sse()
        print("[4/6] 三层回落实测 ...")
        fallback = [] if args.skip_fallback else check_fallback(our_segment_id)
        print("[5/6] 段号写死扫描 + 可复现 + 契约形状 ...")
        hardcoded = check_no_hardcoded_segment_ids()
        repeatability = check_repeatability()
        contract_shape = check_route_contract_shape()
        print("[6/6] 生成报告 + 仓库门禁 doc_gate ...")
        write_snapshot_report(mock_reachable, comparisons, sse, results)
        # 先把报告写出来（doc_gate 要扫这些交付文件），再跑门禁；拿到真实输出后把自检记录写全再复检一次
        write_check_log(server, results, sse, fallback, hardcoded, repeatability,
                        {"exit_code": -1, "stdout": "（首次运行结果见下方复检）", "stderr": ""},
                        mock_reachable, cleanup_actions, contract_shape=contract_shape)
        doc_gate = run_doc_gate()
        write_check_log(server, results, sse, fallback, hardcoded, repeatability,
                        doc_gate, mock_reachable, cleanup_actions, contract_shape=contract_shape)
        doc_gate_recheck = run_doc_gate()
        write_check_log(server, results, sse, fallback, hardcoded, repeatability,
                        doc_gate, mock_reachable, cleanup_actions, doc_gate_recheck,
                        contract_shape=contract_shape)

        required = [result for result in results if result["category"] in ("required-get", "required-post")]
        non_200 = [result for result in required if result["status"] != 200]
        fallback_ok = all(probe.get("status") == 200 for probe in fallback
                          if probe.get("method") in ("GET", "ASSERT"))
        checks = {
            "端点全绿": not non_200,
            "SSE": bool(sse.get("ok")),
            "三层回落": fallback_ok if fallback else True,
            "段号无写死": hardcoded["passed"],
            "可复现": all(item["identical_except_ts"] for item in repeatability),
            "契约响应不透传 steps（防整包回退）": bool(contract_shape.get("passed", True)),
            "doc_gate": doc_gate_recheck["exit_code"] == 0,
        }
        print()
        for name, passed in checks.items():
            print(f"  [{'通过' if passed else '失败'}] {name}")
        print(f"\n报告：{SNAPSHOT_MD.relative_to(ROOT)} / {SNAPSHOT_JSON.relative_to(ROOT)} / "
              f"{CHECKLOG_MD.relative_to(ROOT)}")
        if non_200:
            print("未 200 的必需端点：" + "、".join(f"{item['name']}({item['status']})" for item in non_200))
        if contract_shape.get("findings"):
            print("契约形状问题：" + "；".join(contract_shape["findings"]))
        if contract_shape.get("plan_markers"):
            print("两端标记 / 路线级裁切：" + json.dumps(
                contract_shape["plan_markers"], ensure_ascii=False
            ))
        return 0 if all(checks.values()) else 1
    finally:
        stop_server(process)


if __name__ == "__main__":
    raise SystemExit(main())
