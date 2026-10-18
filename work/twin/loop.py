"""孪生主循环(一期 D8:单进程主循环 + 文件快照当契约)。

输入:work/twin/samples/*_sample.json(--no-sumo);stations/*.json + SUMO 场景(真孪生)
输出:
  · `--no-sumo`(样例链路,保留):`<out>/segments.json`、`vehicles.json`、
    `assimilation_state.json`、`run_log.json` —— 与改造前**逐字节一致**(回归基线);
  · 真孪生(W1 / Issue IKNAER):`<out>/latest/segments_twin.json`、`vehicles.json`、
    `run_log.json`、`twin_timeseries.json`;SUMO 路网 `<out>/sumo/station.net.xml`。
    默认 `--out work/twin/out` → 产物落在 `work/twin/out/latest/`,与接口层
    `work/assembly/traffic.py` 读的 `TWIN_LATEST` 路径一致。
口径:只有一个时钟 —— 孪生仿真时钟。所有时间戳从固定 `DEMO_BASE_TS` 派生,不读系统时间,
     同一场景跑两遍逐字节一致(M1-1 可复现 / TC-13 可回放)。
     **所有数值都是演示数据(模拟)**:需求来自样例站点包、路况由 SUMO 仿真产生,
     不是实测、不是实时、不是现场数据。

用法:
  python work/twin/loop.py --no-sumo                        # 用 samples/ 跳过 SUMO 只串链路
  python work/twin/loop.py --duration 3900 --seed 42        # 真孪生主循环(默认输出 out/latest/)
  python work/twin/loop.py --duration 3900 --seed 42 --out work/twin/out/run_b   # 第二遍对照

模块内实现细节属"推荐"档,可自选方式;换法在 PR 的「实现方式」栏说明。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

TICK_S = 1  # 孪生推进一步 = 1 秒(README 第六节)
SNAPSHOT_EVERY_S = 60  # 每 60 s 出一次快照:指标/判级、同化回灌、预约表

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
STATIONS = REPO_ROOT / "stations"
DEFAULT_SAMPLES_DIR = HERE / "samples"
DEFAULT_OUT_DIR = HERE / "out"

#: 真孪生仿真时钟的固定起点(不读系统时钟):`ts = DEMO_BASE_TS + 仿真秒数`。
#: 选这个值是为了与站点包 `stations/demand.json` 的列车到达时刻(2026-01-01T00:..)同一坐标系。
DEMO_BASE_TS = "2026-01-01T00:00:00+08:00"

#: 真孪生产物发布子目录:接口层 `work/assembly/traffic.py` 的 `TWIN_LATEST` 读
#: `work/twin/out/latest/segments_twin.json`，所以 `--out` 是本次运行的输出根，
#: 发布产物统一写 `<out>/latest/`。
TWIN_LATEST_SUBDIR = "latest"

#: 真实路网 / SUMO 网在本次运行输出目录下的位置
SUMO_SUBDIR = "sumo"

#: 三类虚拟司机在 SUMO 里的行为参数(演示值):D1 送客最赶、D2 接客居中、D3 往返最保守。
#: 跟驰/排队/信号全部交给 SUMO;这里只定 `speedFactor`(确定性,不随机)。
DRIVER_SPEED_FACTORS = {"D1": 1.0, "D2": 0.95, "D3": 0.9}

#: 真孪生没有检测器置信度来源(仿真数据),取站点包 `grading.defaults.confidence` 作基准;
#: 站点包缺该字段时的兜底值(仍属演示值)
FALLBACK_CONFIDENCE = 0.75

#: 快照指标字段口径(写进 run_log / twin_timeseries,自描述、可复核)
METRIC_FORMULAS = {
    "q_vph": (
        "60 s 窗口内进入该段（含反向补边 SZ-###_rev）的车辆数 / window_sec × 3600；"
        "逐秒订阅 TraCI 的 LAST_STEP_VEHICLE_ID_LIST，按车辆首次出现在该边的时刻计数"
    ),
    "v_kmh": (
        "快照时刻该段上全部车辆的平均车速（SUMO edge lastStepMeanSpeed，双向按车辆数加权）× 3.6；"
        "无车 → null（不写 0 冒充畅通）"
    ),
    "k_vpk": "快照时刻该段车辆数 / (L_seg_m / 1000)（双向合计密度）",
    "L_q_m": (
        "排队长度估计 = min(L_seg_m, (halting 车辆数 / 车道数) × queue_headway_m)，双向取较大方向；"
        "queue_headway_m 来自站点包 thresholds.grading"
    ),
    "T_d_min": (
        "排队消散时间估计 = 排队车辆数 ÷ (saturation_flow_vph_per_lane × 车道数) × 60；"
        "排队车辆数 = L_q_m / queue_headway_m；L_q_m=0 → 0.0（估计量，不等同于消散时间采集值）"
    ),
    "x": "q_vph / c_vph；c_vph = c_base_vph（本次无因素注入，factors_applied 恒空数组）",
    "c_base_vph": (
        "双向段：车道数 × 2 个方向 × 站点包 grading.saturation_flow_vph_per_lane（来源写进 run_log.net_build）"
    ),
    "confidence": "站点包 grading.defaults.confidence（仿真数据无检测置信度，取基准值并标明）",
    "data_age_s": "0（指标在同一仿真步算出，没有采集/传输延迟）",
    "level": "调 work/perception/level.py 的 grade()（唯一判级实现，本模块不复制判级逻辑）",
}

#: 真孪生主循环的边界（如实写进 run_log，不冒充通过项）
TWIN_BOUNDARIES = [
    "视频链路 ≥60 点时序不在本单（感知侧另单）；本单只举证孪生侧 M1-2",
    "需求是站点包样例/演示假设值（1 人 1 车、列车到达后 300 s 疏散），真实需求归 IKMHMX",
    "OD 端点（N-01 形式）属 7 节点样例网命名空间，与真网（N-001）不一致 → 不猜映射，路线由真网 boundary 断面生成",
    "未接数据同化 calibrator 回灌、未接决策引擎（vehicles[].guided 恒 false，不伪造采纳）",
    "T_d_min / L_q_m 是估计量，不是采集值；.net.xml 不提交（out/ 已 gitignore），换机用 sumonet.py 重建",
]

SAMPLE_FILES = {
    "segments": "segments_sample.json",
    "vehicles": "vehicles_sample.json",
    "assimilation_state": "assimilation_state_sample.json",
}


@dataclass
class LoopConfig:
    """一次主循环运行的全部输入。"""

    scenario: str = "scenario_1"
    seed: int = 0
    duration_s: int = SNAPSHOT_EVERY_S
    out_dir: Path = DEFAULT_OUT_DIR
    samples_dir: Path = DEFAULT_SAMPLES_DIR
    no_sumo: bool = False
    site: str = ""  # 站点名由调用方给;脚本里不得写死具体站名/坐标(M1-1 口径)
    stations_dir: Path = STATIONS  # 站点包目录（真孪生路径读 demand/scenarios/thresholds）
    base_ts: str = DEMO_BASE_TS  # 仿真时钟固定起点（不读系统时钟）


def read_json(path: Path) -> dict[str, Any]:
    """读一个 UTF-8 JSON 文件(显式编码,换机器不乱码)。"""
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def write_json(path: Path, payload: dict[str, Any]) -> int:
    """写一个 UTF-8 JSON 文件(中文不转义),返回字节数。"""
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def ensure_out_dir(path: Path) -> None:
    """先建输出目录。

    上游实测缺陷:输出目录不存在时 track/count 会**静默假通过**
    (见 work/assembly/现状核实.md 4.3)——所以目录必须先建,且建完要断言。
    """
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise RuntimeError(f"输出目录未能建立:{path}")


def assert_artifact(path: Path) -> int:
    """产物存在性断言,返回字节数。

    **不能只查"非空"**:上游实测 `short_cross.mp4` 是 258 B 的空壳,字节数非 0
    却打不开(现状核实.md 4.4)。JSON 产物这里按"存在 + 能解析 + 顶层非空"三层查。
    """
    if not path.is_file():
        raise RuntimeError(f"产物不存在:{path}")
    size = path.stat().st_size
    if size <= 0:
        raise RuntimeError(f"产物为空:{path}")
    payload = read_json(path)
    if not isinstance(payload, dict) or not payload:
        raise RuntimeError(f"产物顶层为空或不是对象:{path}")
    return size


def load_samples(samples_dir: Path) -> dict[str, dict[str, Any]]:
    """读 --no-sumo 用的三份样例(缺失即报错,不静默降级)。"""
    samples: dict[str, dict[str, Any]] = {}
    for key, name in SAMPLE_FILES.items():
        path = samples_dir / name
        if not path.is_file():
            raise SystemExit(f"缺样例文件:{path}(--no-sumo 需要 samples/ 下三份样例)")
        samples[key] = read_json(path)
    return samples


def run_no_sumo(cfg: LoopConfig) -> int:
    """用 samples/ 走完整链路,不依赖 SUMO、不依赖上游数据。"""
    import calibrate
    import demand
    import detector
    import driver
    import factors
    import scenario

    samples = load_samples(cfg.samples_dir)
    ts = str(samples["segments"].get("ts", ""))
    if not ts:
        raise SystemExit("样例 segments 缺 ts 字段")

    ensure_out_dir(cfg.out_dir)
    calendar = _TimeCursor(ts, cfg.duration_s)

    scene = scenario.load_scenario(cfg, samples)
    applied = factors.load_station_factors(cfg, scene)
    demand_curve = demand.load_demand(cfg, scene)
    fleet = driver.load_drivers(samples["vehicles"])

    segments = detector.aggregate_snapshot(cfg, samples["segments"], applied, calendar.now())
    vehicles = driver.snapshot_fleet(samples["vehicles"], calendar.now())
    assimilation = calibrate.build_state(samples["assimilation_state"], camera_ts=calendar.now())

    written: dict[str, int] = {}
    written["segments.json"] = write_json(cfg.out_dir / "segments.json", segments)
    written["vehicles.json"] = write_json(cfg.out_dir / "vehicles.json", vehicles)
    written["assimilation_state.json"] = write_json(
        cfg.out_dir / "assimilation_state.json", assimilation
    )
    for name in ("segments.json", "vehicles.json", "assimilation_state.json"):
        assert_artifact(cfg.out_dir / name)

    log = {
        "ts": calendar.now(),
        "is_simulated": True,
        "mode": "no_sumo",
        "scenario": cfg.scenario,
        "seed": cfg.seed,
        "site": cfg.site or "(未指定)",
        "duration_s": cfg.duration_s,
        # --sample 的语义是"串通链路",不是"跑一段时间":时钟不推进,只出 1 帧快照。
        # 如实标注,免得下游把 duration_s 读成"真的跑了这么久"——这与
        # work/assembly/现状核实.md 4.3 的"静默假通过"是同一类毛病。
        "is_duration_effective": False,
        "snapshots": 1,
        "tick_s": TICK_S,
        "snapshot_every_s": SNAPSHOT_EVERY_S,
        "samples_dir": cfg.samples_dir.name,
        "segments": len(segments["segments"]),
        "vehicles": len(vehicles["vehicles"]),
        "assimilation_edges": len(assimilation["edges"]),
        "factors_applied": len(applied),
        "demand_entries": len(demand_curve),
        "drivers": len(fleet),
        "written_bytes": written,
        "note": (
            "样例链路(演示数据(模拟)):samples/ 进,out/ 出,不依赖 SUMO 与上游数据;"
            "--sample 只出 1 帧快照,时钟推进与 --duration 生效待 W1 的 run_with_sumo"
        ),
    }
    written["run_log.json"] = write_json(cfg.out_dir / "run_log.json", log)
    assert_artifact(cfg.out_dir / "run_log.json")
    return 0


def run_with_sumo(cfg: LoopConfig) -> int:
    """真孪生主循环:SUMO 1 s 步进 + TraCI 观测 + 每 60 s 快照(README 第六节 / W1)。

    链路:
      1. `sumonet.py` 从真网 `netpack/network_junction.json` 建 SUMO 路网(可一键重建);
      2. `demand.py` 读 `stations/demand.json`(T3 列车到达 × T4 比例)折成 60 s 到达流率;
      3. 每个窗口按固定顺序生成 D1 送客 / D2 接客 / D3 往返车辆,用 SUMO `findRoute` 在真网上
         生成 boundary → boundary 路线;
      4. TraCI 每 1 s 走一步、逐秒统计各边进车;每 60 s 聚合一次快照;
      5. 产物写 `<out>/latest/`:`segments_twin.json` / `vehicles.json` / `run_log.json` /
         `twin_timeseries.json`(每段 65 点时序,举证 M1-2 孪生侧)。

    **不读系统时钟、不随机**:时钟从固定 `DEMO_BASE_TS` 派生,车辆生成顺序固定,
    SUMO 种子 = `--seed`;同一命令两遍 `segments_twin.json` / `twin_timeseries.json` 逐字节一致。
    """
    _reconfigure_text_streams()
    import demand
    import scenario
    import sumonet

    scene = scenario.load_scenario(cfg, {})
    thresholds = _read_thresholds(cfg.stations_dir)
    demand_curve = demand.load_demand(cfg, scene)
    demand_meta = demand.station_demand_meta(cfg, cfg.base_ts)

    ensure_out_dir(cfg.out_dir)
    latest_dir = cfg.out_dir / TWIN_LATEST_SUBDIR
    ensure_out_dir(latest_dir)
    net_dir = cfg.out_dir / SUMO_SUBDIR
    net_build = sumonet.build_station_net(
        stations_dir=cfg.stations_dir,
        out_dir=net_dir,
    )
    net_path = net_dir / sumonet.DEFAULT_NET_NAME

    traci = _import_traci()
    command = [
        find_sumo_binary("sumo"),
        "-n",
        str(net_path),
        "--seed",
        str(cfg.seed),
        "--no-step-log",
        "true",
        "--duration-log.statistics",
        "false",
        "--begin",
        "0",
        "--end",
        str(cfg.duration_s),
        "--step-length",
        f"{float(TICK_S):.1f}",
        "--no-warnings",
        "true",
    ]
    print("[loop] SUMO 启动命令: " + " ".join(command))
    traci.start(command)
    try:
        result = _run_twin_simulation(traci, cfg, scene, demand_curve, net_build, thresholds)
    finally:
        try:
            traci.close()
        except Exception:  # noqa: BLE001 —— 关连接失败不该盖住主循环结果
            pass
    return _write_twin_artifacts(cfg, latest_dir, scene, demand_meta, net_build, result)


def _reconfigure_text_streams() -> None:
    """固定 stdout/stderr 为 UTF-8（Windows 控制台默认不是，中文提示会抛异常）。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def find_sumo_binary(name: str) -> str:
    """定位 SUMO 可执行文件：先看 `$SUMO_HOME/bin`，再看 PATH；找不到给可操作报错。"""
    sumo_home = os.environ.get("SUMO_HOME")
    if sumo_home:
        for candidate_name in (name, f"{name}.exe"):
            candidate = Path(sumo_home) / "bin" / candidate_name
            if candidate.is_file():
                return str(candidate)
    found = shutil.which(name)
    if found:
        return found
    raise SystemExit(
        f"找不到 {name}：请装 SUMO 1.28 并设 $SUMO_HOME（README 第三节），"
        "或把 sumo 放进 PATH；真孪生路径不静默跳过"
    )


def _import_traci() -> Any:
    """导入 TraCI；`import` 失败时把 `$SUMO_HOME/tools` 加进 sys.path 再试一次。"""
    try:
        import traci  # noqa: PLC0415 —— 真孪生路径才需要 TraCI，--no-sumo 不加载
        return traci
    except ImportError:
        sumo_home = os.environ.get("SUMO_HOME")
        if sumo_home:
            tools = str(Path(sumo_home) / "tools")
            if tools not in sys.path:
                sys.path.insert(0, tools)
            import traci  # noqa: PLC0415

            return traci
        raise SystemExit(
            "导入 traci 失败：请装 SUMO 并把 $SUMO_HOME/tools 加进 PYTHONPATH（README 第三节）"
        )


def _read_thresholds(stations_dir: Path | None = None) -> dict[str, Any]:
    """读站点包 `thresholds.json`（判级参数唯一出处，缺失即报错，不写死阈值）。"""
    path = Path(stations_dir or STATIONS) / "thresholds.json"
    if not path.is_file():
        raise SystemExit(f"缺站点包 {path}（真孪生判级必须读它，代码里不写死阈值）")
    payload = read_json(path)
    if not isinstance(payload.get("grading"), dict) or not payload["grading"]:
        raise SystemExit(f"{path} 缺 grading 组（判级参数组）")
    return payload


def _load_level_module() -> Any:
    """只读加载 canonical 判级模块 `work/perception/level.py`（不复制判级逻辑）。"""
    path = REPO_ROOT / "work" / "perception" / "level.py"
    if not path.is_file():
        raise SystemExit(f"缺判级唯一实现 {path}（快照判级必须调它，不复制判级逻辑）")
    spec = importlib.util.spec_from_file_location("perception_level", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"无法加载判级模块 {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sim_iso(base_ts: str, elapsed_s: int | float) -> str:
    """仿真时钟：`base_ts + elapsed_s` → ISO 时间戳（秒级）；不读系统时钟。"""
    return (datetime.fromisoformat(base_ts) + timedelta(seconds=elapsed_s)).isoformat()


def _repo_rel(path: Path) -> str:
    """尽量给仓库相对路径（写进产物可追溯）；不在仓库内给绝对路径。"""
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


#: 时序文件里每段的指标数组（自描述，供 M1-2 孪生侧举证）
TIMESERIES_FIELDS = ("q_vph", "v_kmh", "k_vpk", "L_q_m", "T_d_min", "level")


def _run_twin_simulation(
    traci: Any,
    cfg: LoopConfig,
    scene: Any,
    demand_curve: list[dict[str, Any]],
    net_build: dict[str, Any],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    """TraCI 主循环本体：1 s 步进、逐秒进车统计、每 60 s 快照。"""
    import demand
    import driver
    import sumonet

    from traci import constants as tc

    edges_meta = net_build["edge_meta"]
    edge_row = {row["edge_id"]: row for row in edges_meta}
    edges = sorted(edge_row)
    boundary_nodes = {str(node["node_id"]) for node in net_build["nodes"] if node.get("boundary")}
    entry_edges = sorted(edge for edge in edges if traci.edge.getFromJunction(edge) in boundary_nodes)
    exit_edges = sorted(edge for edge in edges if traci.edge.getToJunction(edge) in boundary_nodes)
    segment_ids = sorted({row["segment_id"] for row in edges_meta})
    seg_info: dict[str, dict[str, Any]] = {}
    for segment_id in segment_ids:
        rows = [edge_row[edge] for edge in edges if edge_row[edge]["segment_id"] == segment_id]
        seg_info[segment_id] = {
            "dirs": {row["direction"]: row for row in rows},
            "length_m": float(rows[0]["length_m"]),
            "lanes": int(rows[0]["num_lanes"]),
            "speed_kmh": float(rows[0]["speed_kmh"]),
        }

    grading = thresholds.get("grading") or {}
    defaults = grading.get("defaults") or {}
    try:
        queue_headway_m = float(grading.get("queue_headway_m"))
        saturation_vph = float(grading.get("saturation_flow_vph_per_lane"))
    except (TypeError, ValueError):
        raise SystemExit(
            "站点包 thresholds.grading 缺 queue_headway_m / saturation_flow_vph_per_lane："
            "排队长度与消散时间无参数可依，不猜"
        )
    if queue_headway_m <= 0 or saturation_vph <= 0:
        raise SystemExit("站点包 thresholds.grading 的 queue_headway_m / saturation_flow_vph_per_lane 非正")
    confidence = float(defaults.get("confidence", FALLBACK_CONFIDENCE))
    level_module = _load_level_module()

    # ---- boundary → boundary 路线（SUMO 自己算，不写死路径；不猜 OD 端点映射）
    route_pairs: list[tuple[str, str, tuple[str, ...]]] = []
    for start in entry_edges:
        for end in exit_edges:
            if start == end:
                continue
            found = traci.simulation.findRoute(start, end)
            edges_found = tuple(found.edges) if found is not None and found.edges else ()
            if not edges_found:
                continue
            route_pairs.append((start, end, edges_found))
    route_pairs.sort(key=lambda item: (item[0], item[1]))
    if not route_pairs:
        raise RuntimeError(
            "真网没有可通行的 boundary→boundary 路线：无法生成车辆（如实失败，不空跑假通过）"
        )
    route_ids: list[str] = []
    for index, (_start, _end, route) in enumerate(route_pairs):
        route_id = f"twin_route_{index:03d}"
        traci.route.add(route_id, list(route))
        route_ids.append(route_id)

    # ---- 三类虚拟司机 vType（跟驰交给 SUMO，只有速度系数体现行为差异）
    driver_types = tuple(driver.DRIVER_TYPES)
    for driver_type in driver_types:
        assert driver_type in DRIVER_SPEED_FACTORS
        traci.vehicletype.copy("DEFAULT_VEHTYPE", driver_type)
        traci.vehicletype.setSpeedFactor(driver_type, DRIVER_SPEED_FACTORS[driver_type])

    # ---- 逐秒订阅：边上的车辆列表 / 平均车速 / 停车数（合并查询，不一辆车一辆车地问）
    subscribe_vars = [
        tc.LAST_STEP_VEHICLE_ID_LIST,
        tc.LAST_STEP_MEAN_SPEED,
        tc.LAST_STEP_VEHICLE_HALTING_NUMBER,
    ]
    for edge in edges:
        traci.edge.subscribe(edge, subscribe_vars)

    prev_sets = {edge: frozenset() for edge in edges}
    entered = {edge: 0 for edge in edges}
    pending: list[tuple[int, str]] = []  # (depart_s, driver_type)
    planned = {driver_type: 0 for driver_type in driver_types}
    inserted = {driver_type: 0 for driver_type in driver_types}
    observed_max = {driver_type: 0 for driver_type in driver_types}
    counters = {driver_type: 0 for driver_type in driver_types}
    vehicles_meta: dict[str, dict[str, Any]] = {}
    insert_errors: list[dict[str, Any]] = []
    route_offsets = {
        driver_type: (index * len(route_pairs)) // max(1, len(driver_types))
        for index, driver_type in enumerate(driver_types)
    }
    route_use = {driver_type: 0 for driver_type in driver_types}

    snapshots: list[dict[str, Any]] = []
    segment_ts: list[str] = []
    timeseries = {
        segment_id: {field: [] for field in TIMESERIES_FIELDS} for segment_id in segment_ids
    }
    final_vehicles: dict[str, Any] = {"ts": "", "is_simulated": True, "vehicles": []}
    vehicles_skipped_internal = 0
    last_snapshot_step = 0

    def schedule_window(window_start: int, window_s: int) -> None:
        """按 60 s 到达流率放量：辆数 = 流率 × 窗口长 / 3600（四舍五入，确定性）。"""
        ts = _sim_iso(cfg.base_ts, window_start)
        flows = demand.flow_at(demand_curve, ts)
        for driver_type in driver_types:
            count = int(round(float(flows.get(driver_type, 0.0)) * window_s / 3600.0))
            planned[driver_type] += count
            for index in range(count):
                depart_s = window_start + (index * window_s) // max(1, count)
                pending.append((depart_s, driver_type))

    def take_snapshot(step_no: int, window_s: int, final: bool = False) -> None:
        """聚合一次快照：61 段四项指标 + 判级 + 车辆清单（最后一帧写 vehicles.json）。"""
        nonlocal vehicles_skipped_internal
        ts = _sim_iso(cfg.base_ts, step_no)
        records: list[dict[str, Any]] = []
        for segment_id in segment_ids:
            info = seg_info[segment_id]
            vehicle_count = 0
            speed_weight = 0.0
            flow_entries = 0
            queue_lengths: list[float] = []
            dissipation_minutes: list[float] = []
            for row in info["dirs"].values():
                edge = row["edge_id"]
                edge_result = results[edge]
                ids = edge_result.get(tc.LAST_STEP_VEHICLE_ID_LIST) or ()
                count = len(ids)
                vehicle_count += count
                mean_speed = edge_result.get(tc.LAST_STEP_MEAN_SPEED)
                if count > 0 and isinstance(mean_speed, (int, float)) and mean_speed >= 0:
                    speed_weight += float(mean_speed) * count
                flow_entries += entered[edge]
                halting = float(edge_result.get(tc.LAST_STEP_VEHICLE_HALTING_NUMBER) or 0)
                lanes = max(1, int(row["num_lanes"]))
                queue_m = min(float(row["length_m"]), (halting / lanes) * queue_headway_m)
                queue_lengths.append(queue_m)
                queue_vehicles = queue_m / queue_headway_m
                dissipation_minutes.append(
                    (queue_vehicles / (saturation_vph * lanes)) * 60.0 if queue_m > 0 else 0.0
                )
            v_kmh = round((speed_weight / vehicle_count) * 3.6, 2) if vehicle_count > 0 else None
            q_vph = round(flow_entries / max(1, window_s) * 3600.0, 2)
            length_km = info["length_m"] / 1000.0
            k_vpk = round(vehicle_count / length_km, 3) if length_km > 0 else None
            queue_m = round(max(queue_lengths), 1) if queue_lengths else 0.0
            t_d_min = round(max(dissipation_minutes), 2) if dissipation_minutes else 0.0
            c_base_vph = round(info["lanes"] * len(info["dirs"]) * saturation_vph, 1)
            record: dict[str, Any] = {
                "segment_id": segment_id,
                "source": "twin",
                "q_vph": q_vph,
                "v_kmh": v_kmh,
                "v_f_kmh": round(info["speed_kmh"], 2),
                "k_vpk": k_vpk,
                "L_q_m": queue_m,
                "L_seg_m": round(info["length_m"], 1),
                "T_d_min": t_d_min,
                "x": round(q_vph / c_base_vph, 4) if c_base_vph > 0 else None,
                "c_base_vph": c_base_vph,
                "c_vph": c_base_vph,
                "factors_applied": [],
                "confidence": confidence,
                "data_age_s": 0,
                "is_simulated": True,
            }
            graded = level_module.grade(record, thresholds)
            record["level"] = graded.get("level", 0)
            record["level_name"] = graded.get("level_name")
            record["triggered_by"] = list(graded.get("triggered_by") or [])
            record["available"] = bool(graded.get("available", False))
            if graded.get("gate_reason") is not None:
                record["gate_reason"] = graded["gate_reason"]
            if graded.get("ci") is not None:
                record["ci"] = graded["ci"]
            records.append(record)
            for field in TIMESERIES_FIELDS:
                timeseries[segment_id][field].append(record[field])

        active_ids = list(traci.vehicle.getIDList())
        fleet = {driver_type: 0 for driver_type in driver_types}
        for vehicle_id in active_ids:
            meta = vehicles_meta.get(vehicle_id)
            if meta is not None:
                fleet[meta["driver_type"]] += 1
        fleet["total"] = len(active_ids)
        for driver_type in driver_types:
            observed_max[driver_type] = max(observed_max[driver_type], fleet[driver_type])

        for edge in edges:
            entered[edge] = 0
        snapshots.append({"ts": ts, "step": step_no, "segments": records, "fleet": fleet})
        segment_ts.append(ts)
        if final:
            final_vehicles.update(
                _build_vehicles_payload(
                    traci,
                    ts,
                    active_ids,
                    vehicles_meta,
                    edge_row,
                    net_build["projection"],
                    sumonet,
                )
            )
            vehicles_skipped_internal = int(final_vehicles.pop("_skipped_internal", 0))

    results: dict[str, dict[int, Any]] = {}
    for step in range(1, cfg.duration_s + 1):
        current_s = step - 1  # 本步开始时的仿真时刻（0,1,2,…）
        if current_s % SNAPSHOT_EVERY_S == 0:
            window_s = min(SNAPSHOT_EVERY_S, cfg.duration_s - current_s)
            if window_s > 0:
                schedule_window(current_s, window_s)
            pending.sort()
        while pending and pending[0][0] <= current_s:
            _depart_s, driver_type = pending.pop(0)
            vehicle_id = f"twin-{driver_type}-{counters[driver_type]:04d}"
            counters[driver_type] += 1
            route_id = route_ids[(route_offsets[driver_type] + route_use[driver_type]) % len(route_ids)]
            route_use[driver_type] += 1
            try:
                traci.vehicle.add(
                    vehicle_id,
                    route_id,
                    typeID=driver_type,
                    depart="now",
                    departLane="best",
                    departSpeed="max",
                )
                inserted[driver_type] += 1
                vehicles_meta[vehicle_id] = {"driver_type": driver_type, "depart_s": current_s}
            except Exception as exc:  # noqa: BLE001 —— TraCI 插入失败如实记，不静默丢
                insert_errors.append({"at_s": current_s, "vehicle_id": vehicle_id, "error": str(exc)})
        traci.simulationStep()
        results = {edge: traci.edge.getSubscriptionResults(edge) for edge in edges}
        for edge in edges:
            current = frozenset(results[edge].get(tc.LAST_STEP_VEHICLE_ID_LIST) or ())
            entered[edge] += len(current - prev_sets[edge])
            prev_sets[edge] = current
        window_s = step - last_snapshot_step
        if window_s >= SNAPSHOT_EVERY_S or step == cfg.duration_s:
            take_snapshot(step, window_s, final=(step == cfg.duration_s))
            last_snapshot_step = step

    if not snapshots:
        raise RuntimeError("主循环没有产出任何快照（duration 过小？如实失败，不写空壳产物）")
    try:
        sumo_version = list(traci.getVersion())
    except Exception:  # noqa: BLE001 —— 版本号拿不到不影响主结果
        sumo_version = []
    final = snapshots[-1]
    observed_final = {driver_type: final["fleet"][driver_type] for driver_type in driver_types}
    return {
        "snapshots": snapshots,
        "final_segments": final["segments"],
        "final_ts": final["ts"],
        "vehicles_payload": final_vehicles,
        "timeseries": timeseries,
        "segment_ts": segment_ts,
        "fleet_history": [
            {"step": item["step"], "ts": item["ts"], "fleet": item["fleet"]} for item in snapshots
        ],
        "counts": {
            "planned": planned,
            "inserted": inserted,
            "observed_max": observed_max,
            "observed_final": observed_final,
            "insert_errors": insert_errors,
            "vehicles_skipped_internal": vehicles_skipped_internal,
        },
        "routes": {
            "entry_edges": entry_edges,
            "exit_edges": exit_edges,
            "routable_pairs": len(route_pairs),
            "route_ids": len(route_ids),
        },
        "sumo_version": sumo_version,
        "window_sec": SNAPSHOT_EVERY_S,
        "driver_speed_factors": dict(DRIVER_SPEED_FACTORS),
        "demand_curve_buckets": len(demand_curve),
    }


def _build_vehicles_payload(
    traci: Any,
    ts: str,
    active_ids: list[str],
    vehicles_meta: dict[str, dict[str, Any]],
    edge_row: dict[str, dict[str, Any]],
    projection: dict[str, Any],
    sumonet: Any,
) -> dict[str, Any]:
    """最后一帧的车辆清单（契约第四节）：位置/速度/所在段，WGS-84 由投影反算。"""
    records: list[dict[str, Any]] = []
    skipped_internal = 0
    # 演示车（App 一期绑定）：当前在途 D1 里 vehicle_id 最小的那辆（确定性选择，至多一辆）
    active_d1 = sorted(
        vehicle_id
        for vehicle_id in active_ids
        if (vehicles_meta.get(vehicle_id) or {}).get("driver_type") == "D1"
    )
    demo_bound_id = active_d1[0] if active_d1 else ""
    for vehicle_id in sorted(active_ids):
        meta = vehicles_meta.get(vehicle_id)
        if meta is None:
            continue
        road = str(traci.vehicle.getRoadID(vehicle_id))
        row = edge_row.get(road)
        on_internal_link = row is None and road.startswith(":")
        if row is None and on_internal_link:
            # 在路口内部边上：按车辆路线取它即将驶入的下一段（仍属真网段号），
            # 里程记 0（车还没进入该段起点；内部边没有段号可归属，不硬塞假段号）
            route = list(traci.vehicle.getRoute(vehicle_id))
            index = int(traci.vehicle.getRouteIndex(vehicle_id))
            if 0 <= index < len(route):
                row = edge_row.get(route[index])
        if row is None:  # 既不在真网段上、也换算不出下一段：如实跳过并计数（不编段号）
            skipped_internal += 1
            continue
        speed = float(traci.vehicle.getSpeed(vehicle_id))
        x, y = traci.vehicle.getPosition(vehicle_id)
        lon, lat = sumonet.xy_to_lonlat(float(x), float(y), projection)
        if on_internal_link:
            offset_m = 0.0
        elif row["direction"] == "forward":
            offset_m = float(traci.vehicle.getLanePosition(vehicle_id))
        else:  # 反向补边：换算回原段起点起算的里程
            offset_m = max(
                0.0, float(row["length_m"]) - float(traci.vehicle.getLanePosition(vehicle_id))
            )
        records.append(
            {
                "vehicle_id": vehicle_id,
                "driver_type": meta["driver_type"],
                "segment_id": row["segment_id"],
                "offset_m": round(offset_m, 1),
                "lon": round(lon, 7),
                "lat": round(lat, 7),
                "state": "排队" if speed < 0.1 else "行驶",
                "guided": False,  # 未接决策引擎：不伪造采纳
                "is_demo_bound": vehicle_id == demo_bound_id,
            }
        )
    return {
        "ts": ts,
        "is_simulated": True,
        "vehicles": records,
        "_skipped_internal": skipped_internal,
    }


def _write_twin_artifacts(
    cfg: LoopConfig,
    latest_dir: Path,
    scene: Any,
    demand_meta: dict[str, Any],
    net_build: dict[str, Any],
    result: dict[str, Any],
) -> int:
    """写真孪生四产物 + 断言存在可解析，并打印可复核摘要。"""
    final_ts = result["final_ts"]
    snapshots = result["snapshots"]
    segments_payload = {
        "ts": final_ts,
        "window_sec": result["window_sec"],
        "is_simulated": True,
        "source": "twin",
        "note": (
            "真孪生主循环最后一帧快照（演示数据（模拟），不是采集数据）："
            "指标由 SUMO 仿真 + 虚拟检测器聚合而来；无车路段 v_kmh=null / level=0（数据不可用），不编数"
        ),
        "segments": result["final_segments"],
    }
    timeseries_segments = []
    for segment_id in sorted(result["timeseries"]):
        points = len(result["segment_ts"])
        series = result["timeseries"][segment_id]
        timeseries_segments.append(
            {
                "segment_id": segment_id,
                "source": "twin",
                "points": points,
                **{field: series[field] for field in TIMESERIES_FIELDS},
            }
        )
    timeseries_payload = {
        "ts": final_ts,
        "base_ts": cfg.base_ts,
        "window_sec": result["window_sec"],
        "is_simulated": True,
        "kind": "twin_timeseries",
        "source": "twin",
        "note": (
            f"每段 {len(result['segment_ts'])} 点时序（演示数据（模拟））：由真孪生主循环每 60 s 快照累积，"
            "供 M1-2 孪生侧举证；视频侧 ≥60 点不在本产物内"
        ),
        "points": len(result["segment_ts"]),
        "point_ts": result["segment_ts"],
        "segments": timeseries_segments,
        "fleet": {
            "driver_types": ["D1", "D2", "D3"],
            "counts_by_point": [entry["fleet"] for entry in result["fleet_history"]],
        },
        "metric_formulas": METRIC_FORMULAS,
    }
    vehicles_payload = dict(result["vehicles_payload"])

    written: dict[str, int] = {}
    for name, payload in (
        ("segments_twin.json", segments_payload),
        ("vehicles.json", vehicles_payload),
        ("twin_timeseries.json", timeseries_payload),
    ):
        write_json(latest_dir / name, payload)
        assert_artifact(latest_dir / name)
        written[name] = (latest_dir / name).stat().st_size  # 落盘实际字节数（含换行符）

    # 兼容发布：接口层 `work/assembly/traffic.py` 的 `TWIN_VEHICLES` 读 `<out>/vehicles.json`
    # （不是 latest/ 下那份）。不改接口层代码，只把同一份车辆清单发布到它读的路径；
    # 段快照接口层已直接读 latest/segments_twin.json，不需要再发布。
    compat_vehicles = cfg.out_dir / "vehicles.json"
    write_json(compat_vehicles, vehicles_payload)
    assert_artifact(compat_vehicles)
    written["compat_vehicles.json"] = compat_vehicles.stat().st_size

    counts = result["counts"]
    run_log = {
        "ts": final_ts,
        "is_simulated": True,
        "mode": "sumo",
        "scenario": cfg.scenario,
        "scenario_id": scene.name,
        "scenario_source": scene.source_file,
        "scenario_switches": scene.switches,
        "seed": cfg.seed,
        "scenario_seed": scene.seed,
        "seed_match_scenario": int(scene.seed) == int(cfg.seed),
        "site": cfg.site or net_build.get("site_id"),
        "base_ts": cfg.base_ts,
        "tick_s": TICK_S,
        "snapshot_every_s": SNAPSHOT_EVERY_S,
        "duration_s": cfg.duration_s,
        "is_duration_effective": True,
        "snapshots": len(snapshots),
        "snapshots_expected": max(1, cfg.duration_s // SNAPSHOT_EVERY_S),
        "segments": len(result["final_segments"]),
        "vehicles_active_final": len(vehicles_payload.get("vehicles") or []),
        "sumo": {
            "version": result["sumo_version"],
            "command": [
                "sumo",
                "-n",
                _repo_rel(latest_dir.parent / SUMO_SUBDIR / "station.net.xml"),
                "--seed",
                str(cfg.seed),
                "--no-step-log",
                "true",
                "--duration-log.statistics",
                "false",
                "--begin",
                "0",
                "--end",
                str(cfg.duration_s),
                "--step-length",
                f"{float(TICK_S):.1f}",
                "--no-warnings",
                "true",
            ],
            "net_sha256": net_build["net"]["sha256"],
            "net_bytes": net_build["net"]["bytes"],
        },
        "net_build": {
            "site_id": net_build.get("site_id"),
            "network_source": net_build.get("network_source"),
            "counts": net_build.get("counts"),
            "station_defaults": net_build.get("station_defaults"),
            "inputs": net_build.get("inputs"),
            "netconvert_args": net_build["net"].get("netconvert_args"),
            "meta_path": net_build.get("meta_path"),
            "note": (
                "车道/限速缺值按站点包 defaults 回落，逐条来源见 meta_path（out/ 运行产物，不提交）；"
                "反向补边只参与仿真，不新增段号"
            ),
        },
        "demand_source": demand_meta["demand_source"],
        "demand": demand_meta,
        "demand_curve_buckets": result.get("demand_curve_buckets"),
        "routes": result["routes"],
        "drivers": {
            "classes": {
                driver_type: {
                    "speed_factor": DRIVER_SPEED_FACTORS[driver_type],
                    "planned": counts["planned"][driver_type],
                    "inserted": counts["inserted"][driver_type],
                    "observed_max": counts["observed_max"][driver_type],
                    "observed_final": counts["observed_final"][driver_type],
                }
                for driver_type in result["driver_speed_factors"]
            },
            "insert_errors": counts["insert_errors"],
            "vehicles_skipped_internal_final": counts["vehicles_skipped_internal"],
            "note": "三类司机都在 SUMO 中运行；guided 恒 false（未接决策引擎，不伪造采纳）",
        },
        "fleet_history": result["fleet_history"],
        "metric_formulas": METRIC_FORMULAS,
        "boundaries": TWIN_BOUNDARIES,
        "published_compat": {
            "vehicles_json": _repo_rel(compat_vehicles),
            "reason": "接口层 traffic.py 的 TWIN_VEHICLES 读 <out>/vehicles.json（兼容发布，不改接口层代码）",
        },
        "written_bytes": written,
        "note": (
            "真孪生主循环（演示数据（模拟））：SUMO 1 s 步进 + 每 60 s 快照；"
            "时钟从固定 base_ts 派生、不读系统时间；同命令两遍关键产物逐字节一致"
        ),
    }
    write_json(latest_dir / "run_log.json", run_log)
    assert_artifact(latest_dir / "run_log.json")
    written["run_log.json"] = (latest_dir / "run_log.json").stat().st_size

    print(
        f"[loop] 真孪生跑完：{len(snapshots)} 个快照（每 {SNAPSHOT_EVERY_S} s）· "
        f"仿真 {cfg.duration_s} s · SUMO {result['sumo_version']}"
    )
    print(
        "[loop] 车辆插入："
        + " / ".join(
            f"{driver_type} {counts['inserted'][driver_type]}/{counts['planned'][driver_type]}"
            for driver_type in result["driver_speed_factors"]
        )
        + f"（实际/计划）；可通行 boundary→boundary 路线 {result['routes']['routable_pairs']} 条"
    )
    print(
        f"[loop] 产物：{latest_dir.as_posix()} / "
        + " / ".join(f"{name} {size} B" for name, size in written.items())
    )
    return 0


class _TimeCursor:
    """孪生仿真时钟:从样例 ts 起步,只按仿真步进走,不读系统时间。"""

    def __init__(self, start_ts: str, duration_s: int) -> None:
        self._start = datetime.fromisoformat(start_ts)
        self._elapsed_s = 0
        self._duration_s = duration_s

    def now(self) -> str:
        """当前仿真时刻的 ISO 时间戳(秒级)。"""
        return (self._start + timedelta(seconds=self._elapsed_s)).isoformat()

    def advance(self, seconds: int = TICK_S) -> str:
        """把仿真时钟推进若干秒(不超过 duration),返回推进后的时刻。

        注意:--sample(--no-sumo)路径**不调用本方法**——那条路径的语义是"串通链路",
        只出 1 帧快照。步进由 W1 的 run_with_sumo 主循环驱动。
        """
        self._elapsed_s = min(self._elapsed_s + seconds, self._duration_s)
        return self.now()

    @property
    def elapsed_s(self) -> int:
        """已推进的仿真秒数。"""
        return self._elapsed_s


def parse_args(argv: list[str] | None = None) -> LoopConfig:
    parser = argparse.ArgumentParser(description="孪生主循环")
    parser.add_argument("--scenario", default="scenario_1")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--duration", type=int, default=SNAPSHOT_EVERY_S, dest="duration_s")
    parser.add_argument("--out", default=str(DEFAULT_OUT_DIR), dest="out_dir")
    parser.add_argument("--samples", default=str(DEFAULT_SAMPLES_DIR), dest="samples_dir")
    parser.add_argument("--no-sumo", action="store_true", dest="no_sumo")
    parser.add_argument("--site", default="")
    parser.add_argument("--stations", default=str(STATIONS), dest="stations_dir")
    parser.add_argument(
        "--base-ts",
        default=DEMO_BASE_TS,
        dest="base_ts",
        help="仿真时钟固定起点（默认 DEMO_BASE_TS；不读系统时钟）",
    )
    ns = parser.parse_args(argv)
    return LoopConfig(
        scenario=ns.scenario,
        seed=ns.seed,
        duration_s=ns.duration_s,
        out_dir=Path(ns.out_dir),
        samples_dir=Path(ns.samples_dir),
        no_sumo=ns.no_sumo,
        site=ns.site,
        stations_dir=Path(ns.stations_dir),
        base_ts=ns.base_ts,
    )


def main(argv: list[str] | None = None) -> int:
    cfg = parse_args(argv)
    if cfg.no_sumo:
        return run_no_sumo(cfg)
    return run_with_sumo(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
