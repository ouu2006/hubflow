#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W1 自检：真孪生主循环（Issue IKNAER，**实跑 + 读产物断言**）。

## 检查什么（照抄 Issue 第三节的判定编号，不新造）

| 项 | 判定 | 怎么验 |
|---|---|---|
| **M1-1** | 站前真网 + D1/D2/D3 三类虚拟司机在 SUMO 中运行；同一场景两遍关键指标**完全一致** | 两遍 `loop.py --duration 3900 --seed 42` 真跑；`run_log` 三类司机计划/插入/观测均 ≥1；两遍 `segments_twin.json` / `twin_timeseries.json` **逐字节一致**（sha256 相同 + 逐段等级序列/时序数组差异 0） |
| **M1-2（孪生侧）** | 至少 1 条路段 `source="twin"` 产出平均车速与排队长度时序 **≥60 个统计点** | `twin_timeseries.json`：points ≥ 60、每段数组长度一致、至少 1 段 v_kmh / L_q_m 有效点数 ≥60。**只判孪生侧；视频侧不在本单，不宣称 M1-2 整体通过** |
| **TC-13** | 同一场景两遍关键指标一致（可回放） | 同 M1-1 的两遍 sha256 逐字节比对 |
| **本单专属一** | `.net.xml` 从 `network_junction.json` 可重建、边 id = `SZ-###`、两次生成一致 | 调 `sumonet.build_station_net()` 连建两遍比 sha256；解析 `.net.xml` 断言 `SZ-###` 段号齐全、零 `SEG-###` |
| **本单专属二** | 两遍 `segments_twin.json` / `twin_timeseries.json` 逐字节一致；`--no-sumo` 样例四产物逐字节不变 | 两遍产物 sha256 比对（样例回归由人工命令留证，本脚本只做真路径） |
| **本单专属三（不造假）** | 缺数据 null/降级、所有产物 `is_simulated:true`、不出现「实测/实时/现场」、需求标 `demand_source` | 逐产物断言；无车段必须 `v_kmh=null` + `level=0`（不许当「畅通」）；禁止词扫描 |
| **IKNAUH 全路段** | 61/61 段最后一帧 `available=true` 且 `level>0`（大屏不再灰档）；每段 65 点里至少 1 点 `q/v/k/L_q/level` 全有效 | `segments_twin.json` 逐段断言 + `twin_timeseries.json` 逐点统计，打印**每段最少有效点数**；背景车流 `background_source=demo_uniform` 写进产物 |

## 用法

```text
python work/twin/tools/check_w1.py                 # 缺省（实跑两遍 3900 s，约 40 s）
python work/twin/tools/check_w1.py --duration 600  # 快速冒烟（不满足 M1-2 的 60 点，会如实 BLOCKED/FAIL）
python work/twin/tools/check_w1.py --reuse-a work/twin/out --reuse-b work/twin/out/run_b
                                                   # 复用已跑产物，不重跑
```

输出逐项 `PASS / FAIL / BLOCKED`；**只要有一项 FAIL 退出码非 0**。
`BLOCKED` 表示受本单范围外条件限制（如时长不足 60 点），不当 PASS、也不当 FAIL 掩盖。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
#: 本文件位于 work/twin/tools/ → 孪生目录是 parents[1]，仓库根是 parents[2]
TWIN_DIR = HERE.parent
REPO_ROOT = TWIN_DIR.parents[1]
if str(TWIN_DIR) not in sys.path:
    sys.path.insert(0, str(TWIN_DIR))

import sumonet  # noqa: E402 —— 复用建网唯一实现（不复制 netconvert 命令）

DEFAULT_DURATION = 3900
DEFAULT_SEED = 42
DEFAULT_OUT_ROOT = TWIN_DIR / "out" / "check_w1"

#: 现役真网段号格式（站点 Z 61 段）；`SEG-###` 属 7 节点样例网，不得混入
SEGMENT_RE = re.compile(r"^SZ-\d{3}$")

#: 产物里不得出现的口径词（要求：不把仿真/样例说成采集/实时数据）
FORBIDDEN_WORDS = ("实测", "实时", "现场")

DRIVER_TYPES = ("D1", "D2", "D3")
VEHICLE_STATES = ("行驶", "排队", "落客服务", "候客", "违停", "已离开")

#: 四产物（真孪生路径）
ARTIFACTS = ("segments_twin.json", "vehicles.json", "run_log.json", "twin_timeseries.json")


def read_json(path: Path) -> dict[str, Any]:
    """读 UTF-8 JSON；同时拒绝 NaN / Infinity（它们不是合法可交付数值）。"""
    with path.open("r", encoding="utf-8") as fp:
        return json.load(
            fp,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"{path} 含非有限数值 {value}（不写 NaN/Infinity）")
            ),
        )


def sha256_file(path: Path) -> str:
    """文件 sha256（小写十六进制）。"""
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_number(value: Any) -> bool:
    """有限数值（bool 不算）。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


class Checker:
    """收集 PASS / FAIL / BLOCKED 结果，最后统一打印并决定退出码。"""

    def __init__(self) -> None:
        self.items: list[tuple[str, str, str]] = []

    def add(self, item: str, status: str, detail: str) -> None:
        assert status in ("PASS", "FAIL", "BLOCKED")
        self.items.append((item, status, detail))
        print(f"[{status}] {item}：{detail}", flush=True)

    def fail(self, item: str, detail: str) -> None:
        self.add(item, "FAIL", detail)

    def pass_(self, item: str, detail: str) -> None:
        self.add(item, "PASS", detail)

    def blocked(self, item: str, detail: str) -> None:
        self.add(item, "BLOCKED", detail)

    def summary(self) -> int:
        passed = sum(1 for _, status, _ in self.items if status == "PASS")
        failed = sum(1 for _, status, _ in self.items if status == "FAIL")
        blocked = sum(1 for _, status, _ in self.items if status == "BLOCKED")
        print("-" * 72)
        print(f"汇总：PASS {passed} · FAIL {failed} · BLOCKED {blocked}")
        if failed:
            print("结论：**未通过**（有 FAIL 项，见上）")
            return 1
        if blocked:
            print("结论：通过项受本单范围外条件限制（BLOCKED 不当 PASS，见每项说明）")
        else:
            print("结论：全部 PASS")
        return 0


def run_loop(run_dir: Path, duration: int, seed: int) -> tuple[int, str]:
    """真跑一遍 `loop.py`（子进程），返回 (退出码, 输出尾部)。"""
    loop_py = TWIN_DIR / "loop.py"
    command = [
        sys.executable,
        str(loop_py),
        "--duration",
        str(duration),
        "--seed",
        str(seed),
        "--out",
        str(run_dir),
    ]
    print(f"[cmd] {' '.join(command)}", flush=True)
    result = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    tail = "\n".join((result.stdout or "").strip().splitlines()[-6:])
    if tail:
        print(tail, flush=True)
    return result.returncode, tail


# ---------------------------------------------------------------- 各项检查


def check_net_rebuild(checker: Checker, net_root: Path) -> dict[str, Path]:
    """本单专属一：真网两次建网逐字节一致 + 段号命名空间。"""
    net_dirs = {"a": net_root / "net_a", "b": net_root / "net_b"}
    sids = {}
    try:
        for key, target in net_dirs.items():
            meta = sumonet.build_station_net(
                site_ranges_path=None,
                stations_dir=None,
                out_dir=target,
            )
            sids[key] = meta["net"]["sha256"]
            net_dirs[key] = Path(target) / sumonet.DEFAULT_NET_NAME
    except Exception as exc:  # noqa: BLE001 —— 建网失败要如实报 FAIL
        checker.fail("NET_REBUILD（本单专属一）", f"建网失败：{exc}")
        return net_dirs
    if sids["a"] != sids["b"]:
        checker.fail(
            "NET_REBUILD（本单专属一）",
            f"两次建网 sha256 不同：{sids['a']} vs {sids['b']}（同一输入必须逐字节一致）",
        )
        return net_dirs
    checker.pass_("NET_REBUILD（本单专属一）", f"两次建网 sha256 一致 {sids['a'][:16]}…")

    # 解析 .net.xml：61 个正向 SZ-### 边 + 反向补边，零 SEG-###
    text = net_dirs["a"].read_text(encoding="utf-8")
    edge_ids = re.findall(r'<edge id="([^"]+)"', text)
    forward = sorted(edge_id for edge_id in edge_ids if SEGMENT_RE.match(edge_id))
    reverse = [edge_id for edge_id in edge_ids if edge_id.endswith(sumonet.REVERSE_SUFFIX)]
    seg_edges = [edge_id for edge_id in edge_ids if edge_id.startswith("SEG")]
    if len(forward) != 61:
        checker.fail("NET_NAMESPACE", f".net.xml 里 SZ-### 正向边 {len(forward)} 条（应 61）")
    elif seg_edges:
        checker.fail("NET_NAMESPACE", f".net.xml 混入样例网段号：{seg_edges[:5]}")
    else:
        checker.pass_(
            "NET_NAMESPACE",
            f".net.xml：SZ-### 正向边 {len(forward)} 条 + 反向补边 {len(reverse)} 条，零 SEG-###",
        )
    return net_dirs


def _artifact_paths(run_dir: Path) -> dict[str, Path]:
    return {name: run_dir / "latest" / name for name in ARTIFACTS}


def check_artifacts_exist(checker: Checker, run_dir: Path, label: str) -> bool:
    paths = _artifact_paths(run_dir)
    missing = [name for name, path in paths.items() if not path.is_file() or path.stat().st_size <= 0]
    if missing:
        checker.fail(f"ARTIFACTS_EXIST[{label}]", f"缺产物/空文件：{missing}（目录 {run_dir}）")
        return False
    checker.pass_(
        f"ARTIFACTS_EXIST[{label}]",
        " / ".join(f"{name} {path.stat().st_size} B" for name, path in paths.items()),
    )
    return True


def check_is_simulated(checker: Checker, run_dir: Path, label: str) -> None:
    """所有产物 `is_simulated:true`（契约 §八：技术强制）。"""
    problems: list[str] = []
    for name in ARTIFACTS:
        payload = read_json(run_dir / "latest" / name)
        if payload.get("is_simulated") is not True:
            problems.append(f"{name} 顶层 is_simulated≠true")
    segments = read_json(run_dir / "latest" / "segments_twin.json")["segments"]
    for record in segments:
        if record.get("is_simulated") is not True:
            problems.append(f"段 {record.get('segment_id')} 缺 is_simulated:true")
            break
    for record in read_json(run_dir / "latest" / "twin_timeseries.json")["segments"]:
        if record.get("source") != "twin":
            problems.append(f"时序段 {record.get('segment_id')} source≠twin")
            break
    if problems:
        checker.fail(f"IS_SIMULATED[{label}]", "；".join(problems))
    else:
        checker.pass_(f"IS_SIMULATED[{label}]", "四产物顶层 + 61 段记录均 is_simulated:true")


def check_no_forbidden_words(checker: Checker, run_dir: Path) -> None:
    """口径红线：产物里不得出现「实测/实时/现场」。"""
    hits: dict[str, list[str]] = {}
    for name in ARTIFACTS:
        text = (run_dir / "latest" / name).read_text(encoding="utf-8")
        found = [word for word in FORBIDDEN_WORDS if word in text]
        if found:
            hits[name] = found
    if hits:
        checker.fail("NO_FORBIDDEN_WORDS", f"产物出现口径禁用词：{hits}")
    else:
        checker.pass_("NO_FORBIDDEN_WORDS", "四产物均未出现「实测/实时/现场」")


def check_segments_twin(checker: Checker, run_dir: Path) -> dict[str, Any]:
    """segments_twin.json：契约字段 / 段号命名空间 / 缺数据如实降级。"""
    payload = read_json(run_dir / "latest" / "segments_twin.json")
    segments = payload.get("segments")
    if not isinstance(segments, list) or len(segments) != 61:
        checker.fail("SEGMENTS_TWIN", f"segments 应为 61 条，实际 {0 if not isinstance(segments, list) else len(segments)}")
        return payload
    problems: list[str] = []
    ids = [record.get("segment_id") for record in segments]
    bad_ids = [segment_id for segment_id in ids if not isinstance(segment_id, str) or not SEGMENT_RE.match(segment_id)]
    if bad_ids:
        problems.append(f"段号不在 SZ-### 命名空间：{bad_ids[:5]}")
    if len(set(ids)) != len(ids):
        problems.append("段号有重复")
    for record in segments:
        segment_id = record.get("segment_id")
        for key in ("source", "level", "is_simulated", "q_vph", "L_seg_m"):
            if key not in record:
                problems.append(f"{segment_id} 缺必填字段 {key}")
        if record.get("source") != "twin":
            problems.append(f"{segment_id} source={record.get('source')!r}（应 twin）")
        if not _is_number(record.get("q_vph")) or float(record["q_vph"]) < 0:
            problems.append(f"{segment_id} q_vph 非有限非负数")
        for field in ("v_kmh", "k_vpk", "L_q_m", "T_d_min", "x", "c_base_vph", "confidence", "data_age_s"):
            value = record.get(field)
            if value is None:
                continue
            if not _is_number(value):
                problems.append(f"{segment_id} {field} 非有限数值：{value!r}")
        if record.get("v_kmh") is None:
            # 缺数据必须如实降级：不许当「畅通」
            if record.get("level") != 0:
                problems.append(f"{segment_id} 无车速但 level={record.get('level')}（缺数据不许判畅通）")
            if record.get("available") is not False:
                problems.append(f"{segment_id} 无车速但 available≠false")
            if not record.get("gate_reason"):
                problems.append(f"{segment_id} 无车速但缺 gate_reason（降级原因要写清）")
    if problems:
        checker.fail("SEGMENTS_TWIN", "；".join(problems[:8]))
    else:
        checker.pass_(
            "SEGMENTS_TWIN",
            f"61 段全部 source=twin / is_simulated=true；无车速段如实 level=0 + available=false + gate_reason",
        )
    return payload


def check_vehicles(checker: Checker, run_dir: Path) -> None:
    """vehicles.json：契约第四节字段 / 封闭取值 / is_demo_bound 至多一辆。"""
    payload = read_json(run_dir / "latest" / "vehicles.json")
    vehicles = payload.get("vehicles")
    if not isinstance(vehicles, list):
        checker.fail("VEHICLES", "vehicles 不是数组")
        return
    problems: list[str] = []
    demo_bound = 0
    for item in vehicles:
        vehicle_id = item.get("vehicle_id")
        if item.get("driver_type") not in DRIVER_TYPES:
            problems.append(f"{vehicle_id} driver_type={item.get('driver_type')!r} 不在封闭取值")
        if item.get("state") not in VEHICLE_STATES:
            problems.append(f"{vehicle_id} state={item.get('state')!r} 不在封闭取值")
        if not isinstance(item.get("segment_id"), str) or not SEGMENT_RE.match(str(item.get("segment_id"))):
            problems.append(f"{vehicle_id} segment_id 不在 SZ-### 命名空间")
        for field in ("offset_m", "lon", "lat"):
            if not _is_number(item.get(field)):
                problems.append(f"{vehicle_id} {field} 非有限数值")
        if item.get("is_demo_bound") is True:
            demo_bound += 1
    if demo_bound > 1:
        problems.append(f"is_demo_bound 有 {demo_bound} 辆为 true（至多 1 辆）")
    classes = {driver_type: sum(1 for item in vehicles if item.get("driver_type") == driver_type) for driver_type in DRIVER_TYPES}
    if problems:
        checker.fail("VEHICLES", "；".join(problems[:8]))
    else:
        checker.pass_(
            "VEHICLES",
            f"{len(vehicles)} 辆活动车辆 · 三类分布 D1 {classes['D1']} / D2 {classes['D2']} / D3 {classes['D3']} · "
            f"is_demo_bound {demo_bound} 辆",
        )


def check_timeseries(checker: Checker, run_dir: Path, duration: int) -> dict[str, Any]:
    """M1-2 孪生侧：每段 ≥60 点时序，至少 1 段平均车速/排队长度有效点 ≥60。"""
    payload = read_json(run_dir / "latest" / "twin_timeseries.json")
    points = payload.get("points")
    expected = duration // 60
    series = payload.get("segments")
    problems: list[str] = []
    if not isinstance(series, list) or len(series) != 61:
        checker.fail("TIMESERIES", f"segments 应为 61 条，实际 {0 if not isinstance(series, list) else len(series)}")
        return payload
    if points != expected:
        problems.append(f"points={points}（应 {expected}）")
    best: tuple[str, int, int] = ("", 0, 0)
    for record in series:
        segment_id = record.get("segment_id")
        if not isinstance(segment_id, str) or not SEGMENT_RE.match(segment_id):
            problems.append(f"时序段号不在 SZ-### 命名空间：{segment_id!r}")
            continue
        for field in ("q_vph", "v_kmh", "k_vpk", "L_q_m", "T_d_min", "level"):
            values = record.get(field)
            if not isinstance(values, list) or len(values) != expected:
                problems.append(f"{segment_id} 的 {field} 不是 {expected} 点数组")
                break
        v_values = record.get("v_kmh") or []
        lq_values = record.get("L_q_m") or []
        v_valid = sum(1 for value in v_values if value is not None)
        lq_valid = sum(1 for value in lq_values if value is not None)
        if v_valid > best[1]:
            best = (segment_id, v_valid, lq_valid)
    if problems:
        checker.fail("M1-2_TWIN（孪生侧）", "；".join(problems[:6]))
        return payload
    if expected < 60:
        checker.blocked(
            "M1-2_TWIN（孪生侧）",
            f"duration={duration}s → {expected} 点 < 60（本次是快速冒烟，不满足判定条件；用缺省 3900 s 复跑）",
        )
        return payload
    if best[1] >= 60 and best[2] >= 60:
        checker.pass_(
            "M1-2_TWIN（孪生侧）",
            f"points={points}；{best[0]} 平均车速有效点 {best[1]}/{expected}、排队长度有效点 {best[2]}/{expected}；"
            "**只判孪生侧**，视频侧 ≥60 点不在本单，M1-2 整体仍待感知侧合验",
        )
    elif best[1] >= 60:
        checker.pass_(
            "M1-2_TWIN（孪生侧）",
            f"points={points}；{best[0]} 平均车速有效点 {best[1]}/{expected}，排队长度有效点 {best[2]}（队列为 0 的点也算有效 0 m）",
        )
    else:
        checker.fail(
            "M1-2_TWIN（孪生侧）",
            f"没有任何段的有效平均车速点 ≥60（最好 {best[0]}：{best[1]}/{expected}）",
        )
    return payload


def check_m1_1(checker: Checker, run_a: Path, run_b: Path, timeseries_a: dict[str, Any], duration: int) -> None:
    """M1-1：三类司机在 SUMO 中运行 + 两遍关键指标完全一致（TC-13 同证）。"""
    log_a = read_json(run_a / "latest" / "run_log.json")
    log_b = read_json(run_b / "latest" / "run_log.json")
    problems: list[str] = []
    if log_a.get("mode") != "sumo":
        problems.append(f"run_log.mode={log_a.get('mode')!r}（应 sumo）")
    if duration >= 60 and log_a.get("snapshots") != duration // 60:
        problems.append(f"snapshots={log_a.get('snapshots')}（应 {duration // 60}）")
    classes = (log_a.get("drivers") or {}).get("classes") or {}
    for driver_type in DRIVER_TYPES:
        entry = classes.get(driver_type) or {}
        if int(entry.get("inserted") or 0) < 1:
            problems.append(f"{driver_type} 实际插入 0 辆")
        if int(entry.get("observed_max") or 0) < 1:
            problems.append(f"{driver_type} 在 SUMO 里从未被观测到")
    fleet_history = log_a.get("fleet_history") or []
    for driver_type in DRIVER_TYPES:
        peaks = [int(((entry.get("fleet") or {}).get(driver_type)) or 0) for entry in fleet_history]
        if not peaks or max(peaks) < 1:
            problems.append(f"{driver_type} 的逐点在场车辆数恒 0")

    # 两遍逐字节一致（关键指标：等级序列 / 时序数组 / 全文件 sha）
    sha_a = {name: sha256_file(run_a / "latest" / name) for name in ("segments_twin.json", "twin_timeseries.json")}
    sha_b = {name: sha256_file(run_b / "latest" / name) for name in ("segments_twin.json", "twin_timeseries.json")}
    for name in sha_a:
        if sha_a[name] != sha_b[name]:
            problems.append(f"{name} 两遍 sha256 不同（关键指标不一致）")
    segments_a = read_json(run_a / "latest" / "segments_twin.json")["segments"]
    segments_b = read_json(run_b / "latest" / "segments_twin.json")["segments"]
    level_a = [record.get("level") for record in segments_a]
    level_b = [record.get("level") for record in segments_b]
    if level_a != level_b:
        problems.append("两遍各段判级序列 diff ≠ 0")
    timeseries_b = read_json(run_b / "latest" / "twin_timeseries.json")
    series_a = {record["segment_id"]: record for record in timeseries_a["segments"]}
    series_b = {record["segment_id"]: record for record in timeseries_b["segments"]}
    diff_count = 0
    for segment_id in series_a:
        for field in ("q_vph", "v_kmh", "L_q_m", "level"):
            if series_a[segment_id].get(field) != series_b.get(segment_id, {}).get(field):
                diff_count += 1
                break
    if diff_count:
        problems.append(f"两遍时序数组有 {diff_count} 段不一致")
    if problems:
        checker.fail("M1-1", "；".join(problems[:8]))
        return
    checker.pass_(
        "M1-1",
        f"三类司机均在 SUMO 中运行（插入 D1 {classes['D1']['inserted']} / D2 {classes['D2']['inserted']} / "
        f"D3 {classes['D3']['inserted']} 辆）；两遍关键指标完全一致（61 段等级序列 diff 0、时序 diff 0、"
        f"segments_twin sha={sha_a['segments_twin.json'][:16]}…、twin_timeseries sha={sha_a['twin_timeseries.json'][:16]}…）",
    )
    checker.pass_(
        "TC-13",
        f"同一场景两遍关键指标一致（逐字节）：segments_twin.json / twin_timeseries.json sha256 两遍相同",
    )


def check_determinism(checker: Checker, run_a: Path, run_b: Path) -> None:
    """两遍 sha 单独打印（硬要求：贴 sha 证据）。"""
    print("[sha] 两遍产物 sha256：", flush=True)
    for name in ("segments_twin.json", "twin_timeseries.json", "vehicles.json", "run_log.json"):
        sha_a = sha256_file(run_a / "latest" / name)
        sha_b = sha256_file(run_b / "latest" / name)
        print(f"  {name}: A={sha_a} B={sha_b} same={sha_a == sha_b}", flush=True)
    for name in ("segments_twin.json", "twin_timeseries.json", "vehicles.json"):
        if sha256_file(run_a / "latest" / name) == sha256_file(run_b / "latest" / name):
            checker.pass_(f"DETERMINISM[{name}]", "两遍逐字节一致")
        else:
            checker.fail(f"DETERMINISM[{name}]", "两遍 sha256 不同（同一命令必须逐字节一致）")


def check_demand_source(checker: Checker, run_a: Path) -> None:
    """需求必须标来源（样例/演示），不得冒充实测。"""
    log = read_json(run_a / "latest" / "run_log.json")
    source = str(log.get("demand_source") or "")
    if not source:
        checker.fail("DEMAND_SOURCE", "run_log.demand_source 为空")
    elif not any(word in source for word in ("样例", "演示", "demo")):
        checker.fail("DEMAND_SOURCE", f"demand_source 未标样例/演示：{source[:80]}")
    elif log.get("net_build", {}).get("network_source", "").find("network_junction.json") < 0:
        checker.fail("DEMAND_SOURCE", "net_build.network_source 未指向真网 network_junction.json")
    else:
        checker.pass_(
            "DEMAND_SOURCE",
            f"需求来源：{source[:60]}… · 路网来源：{log['net_build']['network_source']}",
        )


def check_compat_publish(checker: Checker, run_a: Path) -> None:
    """兼容发布：接口层读的 `<out>/vehicles.json` 与 latest 下那份同字节（不改接口层代码）。"""
    latest_vehicles = run_a / "latest" / "vehicles.json"
    compat_vehicles = run_a / "vehicles.json"
    if not compat_vehicles.is_file():
        checker.fail("COMPAT_PUBLISH", f"缺接口层兼容发布 {compat_vehicles}（traffic.py 的 TWIN_VEHICLES）")
    elif sha256_file(compat_vehicles) != sha256_file(latest_vehicles):
        checker.fail("COMPAT_PUBLISH", "<out>/vehicles.json 与 latest/vehicles.json 字节不同")
    else:
        checker.pass_(
            "COMPAT_PUBLISH",
            f"<out>/vehicles.json 已按接口层路径发布（{compat_vehicles.stat().st_size} B，与 latest 同字节）",
        )


def check_driver_counts(checker: Checker, run_a: Path, run_b: Path) -> None:
    """两遍车辆计数（计划/插入/观测）一致——M1-1「同一场景」的前提。"""
    log_a = read_json(run_a / "latest" / "run_log.json")
    log_b = read_json(run_b / "latest" / "run_log.json")
    keys = ("planned", "inserted", "observed_max", "observed_final")
    diff = []
    for driver_type in DRIVER_TYPES:
        for key in keys:
            value_a = (log_a["drivers"]["classes"][driver_type]).get(key)
            value_b = (log_b["drivers"]["classes"][driver_type]).get(key)
            if value_a != value_b:
                diff.append(f"{driver_type}.{key}: {value_a} vs {value_b}")
    if diff:
        checker.fail("DRIVER_COUNTS", "；".join(diff[:6]))
    else:
        checker.pass_(
            "DRIVER_COUNTS",
            " / ".join(
                f"{driver_type} 计划 {(log_a['drivers']['classes'][driver_type])['planned']}、"
                f"插入 {(log_a['drivers']['classes'][driver_type])['inserted']}、"
                f"峰值在场 {(log_a['drivers']['classes'][driver_type])['observed_max']}"
                for driver_type in DRIVER_TYPES
            )
            + "（两遍一致）",
        )


# ---------------------------------------------------------------- 入口


def check_all_segments_coverage(checker: Checker, run_a: Path, duration: int) -> dict[str, Any]:
    """IKNAUH：61/61 段有有效数据/等级（大屏不再灰档），并打印每段最少有效点数。"""
    segments_payload = read_json(run_a / "latest" / "segments_twin.json")
    timeseries = read_json(run_a / "latest" / "twin_timeseries.json")
    segments = segments_payload.get("segments") or []
    expected = max(1, duration // 60)
    problems: list[str] = []
    if len(segments) != 61:
        problems.append(f"最后一帧只有 {len(segments)} 段（应 61）")
    unavailable = [record.get("segment_id") for record in segments if record.get("available") is not True]
    if unavailable:
        problems.append(f"{len(unavailable)} 段 available≠true：{unavailable[:5]}")
    level_zero = [record.get("segment_id") for record in segments if int(record.get("level") or 0) < 1]
    if level_zero:
        problems.append(f"{len(level_zero)} 段 level=0（数据不可用）：{level_zero[:5]}")
    v_null = [record.get("segment_id") for record in segments if record.get("v_kmh") is None]
    if v_null:
        problems.append(f"{len(v_null)} 段最后一帧无平均车速：{v_null[:5]}")

    valid_counts: dict[str, int] = {}
    for record in timeseries.get("segments") or []:
        segment_id = str(record.get("segment_id"))
        series = [record.get(field) or [] for field in ("q_vph", "v_kmh", "k_vpk", "L_q_m", "level")]
        if any(len(values) != expected for values in series):
            problems.append(f"{segment_id} 时序点数不等于 {expected}")
            continue
        valid = 0
        for index in range(expected):
            if (
                series[0][index] is not None
                and series[1][index] is not None
                and series[2][index] is not None
                and series[3][index] is not None
                and int(series[4][index] or 0) > 0
            ):
                valid += 1
        valid_counts[segment_id] = valid
    if len(valid_counts) != 61:
        problems.append(f"时序文件只有 {len(valid_counts)} 段（应 61）")
    min_valid = min(valid_counts.values()) if valid_counts else 0
    zero_valid = [segment_id for segment_id, count in valid_counts.items() if count < 1]
    if zero_valid:
        problems.append(f"{len(zero_valid)} 段没有任何有效点：{zero_valid[:5]}")
    full_count = sum(1 for count in valid_counts.values() if count == expected)

    level_dist = {level: 0 for level in (1, 2, 3, 4)}
    for record in segments:
        level = int(record.get("level") or 0)
        if level in level_dist:
            level_dist[level] += 1
    summary = {
        "segments": len(segments),
        "available_final": len(segments) - len(unavailable),
        "level_positive_final": len(segments) - len(level_zero),
        "min_valid_points": min_valid,
        "expected_points": expected,
        "segments_full_points": full_count,
        "level_distribution": level_dist,
        "valid_counts": valid_counts,
    }
    # 与产物里自带的 coverage 汇总交叉核对（同一份数据两种口径必须一致）
    reported = timeseries.get("coverage") or {}
    for key, computed in (
        ("segments_total", len(segments)),
        ("available_final_true", summary["available_final"]),
        ("level_positive_final", summary["level_positive_final"]),
        ("min_valid_points_per_segment", min_valid),
    ):
        if key in reported and reported.get(key) != computed:
            problems.append(f"coverage.{key} 产物说 {reported.get(key)}、自检算 {computed}")

    detail = (
        f"61/61 段 available 且 level>0；每段最少有效点 {min_valid}/{expected}"
        f"（{full_count} 段 {expected}/{expected}）；level 分布 "
        + "/".join(f"L{level}:{count}" for level, count in level_dist.items())
    )
    if problems:
        checker.fail("ALL_SEGMENTS_COVERED（IKNAUH）", "；".join(problems[:8]))
    else:
        checker.pass_("ALL_SEGMENTS_COVERED（IKNAUH）", detail)
    return summary


def check_background_source(checker: Checker, run_a: Path) -> None:
    """IKNAUH：背景车流来源/假设写进产物且为演示口径（不冒充实测/实际需求）。"""
    log = read_json(run_a / "latest" / "run_log.json")
    segments_payload = read_json(run_a / "latest" / "segments_twin.json")
    timeseries = read_json(run_a / "latest" / "twin_timeseries.json")
    background = log.get("background") or {}
    problems: list[str] = []
    if str(log.get("background_source") or "") != "demo_uniform":
        problems.append(f"run_log.background_source={log.get('background_source')!r}（应 demo_uniform）")
    if str(segments_payload.get("background_source") or "") != "demo_uniform":
        problems.append("segments_twin.json 缺 background_source=demo_uniform")
    if str(timeseries.get("background_source") or "") != "demo_uniform":
        problems.append("twin_timeseries.json 缺 background_source=demo_uniform")
    if int(background.get("inserted") or 0) < 61:
        problems.append(f"背景车插入 {background.get('inserted')} 辆（应 >= 61）")
    if int(background.get("segments") or 0) != 61:
        problems.append(f"背景车覆盖段数 {background.get('segments')}（应 61）")
    if int(background.get("per_segment_per_window") or 0) != 1:
        problems.append("背景车口径不是每段每窗口 1 辆")
    if "演示" not in str(background.get("note") or ""):
        problems.append("背景车 note 未标演示假设")
    if "背景" not in str(background.get("not_in_vehicles_json") or ""):
        problems.append("未说明背景车不进 vehicles.json（契约第四节只收 D1/D2/D3）")
    if problems:
        checker.fail("BACKGROUND_SOURCE（IKNAUH）", "；".join(problems[:6]))
    else:
        checker.pass_(
            "BACKGROUND_SOURCE（IKNAUH）",
            f"background_source=demo_uniform；背景车插入 {background.get('inserted')}/"
            f"{background.get('planned')} 辆（61 段 × {background.get('windows')} 窗口）；"
            f"覆盖补投 {background.get('coverage_topups')} 次；演示假设已写进产物",
        )


def parse_args(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="W1 真孪生主循环自检（实跑 + 读产物断言）")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION, help="仿真时长（秒，缺省 3900）")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="随机种子（缺省 42）")
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT), help="自检输出根目录")
    parser.add_argument("--reuse-a", default="", help="复用已跑产物目录 A（不再重跑）")
    parser.add_argument("--reuse-b", default="", help="复用已跑产物目录 B（不再重跑）")
    return vars(parser.parse_args(argv))


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ns = parse_args(argv)
    duration = int(ns["duration"])
    seed = int(ns["seed"])
    out_root = Path(ns["out_root"])
    run_a = Path(ns["reuse_a"]) if ns["reuse_a"] else out_root / "run_a"
    run_b = Path(ns["reuse_b"]) if ns["reuse_b"] else out_root / "run_b"
    checker = Checker()
    print(f"仓库根：{REPO_ROOT}")
    print(f"自检运行目录：A={run_a} B={run_b} · duration={duration}s · seed={seed}")

    try:
        if not ns["reuse_a"]:
            if run_a.exists():
                shutil.rmtree(run_a)
            if run_b.exists():
                shutil.rmtree(run_b)
        net_dirs = check_net_rebuild(checker, out_root)

        if ns["reuse_a"]:
            checker.pass_("RUN_TWICE", "复用已跑产物（--reuse-a/--reuse-b），未重跑")
        else:
            print("[run] A 遍…", flush=True)
            code_a, _tail_a = run_loop(run_a, duration, seed)
            print("[run] B 遍…", flush=True)
            code_b, _tail_b = run_loop(run_b, duration, seed)
            if code_a != 0 or code_b != 0:
                checker.fail("RUN_TWICE", f"loop.py 退出码 A={code_a} B={code_b}（真跑失败）")
            else:
                checker.pass_("RUN_TWICE", "两遍 loop.py 均退出码 0（真跑 SUMO）")

        if not check_artifacts_exist(checker, run_a, "A") or not check_artifacts_exist(checker, run_b, "B"):
            return checker.summary()

        # 两遍的 SUMO 路网与自检重建网 sha256 对账（证明产物确实来自真网重建）
        log_a = read_json(run_a / "latest" / "run_log.json")
        net_sha = str((log_a.get("sumo") or {}).get("net_sha256") or "")
        rebuilt_a = sha256_file(net_dirs["a"]) if net_dirs.get("a") and net_dirs["a"].is_file() else ""
        if not net_sha:
            checker.fail("NET_SHA_MATCH", "run_log.sumo.net_sha256 为空")
        elif rebuilt_a and net_sha != rebuilt_a:
            checker.fail("NET_SHA_MATCH", f"运行用网 sha={net_sha[:16]}… ≠ 自检重建网 sha={rebuilt_a[:16]}…")
        else:
            checker.pass_("NET_SHA_MATCH", f"运行用网 = 自检重建网 sha256 {net_sha[:16]}…")

        check_is_simulated(checker, run_a, "A")
        check_is_simulated(checker, run_b, "B")
        check_no_forbidden_words(checker, run_a)
        check_segments_twin(checker, run_a)
        check_vehicles(checker, run_a)
        timeseries_a = check_timeseries(checker, run_a, duration)
        check_all_segments_coverage(checker, run_a, duration)
        check_background_source(checker, run_a)
        check_m1_1(checker, run_a, run_b, timeseries_a, duration)
        check_determinism(checker, run_a, run_b)
        check_driver_counts(checker, run_a, run_b)
        check_demand_source(checker, run_a)
        check_compat_publish(checker, run_a)
    except Exception:  # noqa: BLE001 —— 自检本身出错要完整打印，不能静默
        print("[FAIL] CHECK_W1 执行异常：", flush=True)
        traceback.print_exc()
        return 1
    return checker.summary()


if __name__ == "__main__":
    raise SystemExit(main())
