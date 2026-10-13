"""孪生主循环(一期 D8:单进程主循环 + 文件快照当契约)。

输入:work/twin/samples/*_sample.json(--no-sumo);stations/*.json + SUMO 场景(真孪生)
输出:work/twin/out/segments.json、vehicles.json、assimilation_state.json、run_log.json
口径:只有一个时钟 —— 孪生仿真时钟。所有时间戳从样例的 ts 派生,不读系统时间,
     同一场景跑两遍逐字段一致(M1-1 可复现 / TC-13 可回放)。

用法:
  python work/twin/loop.py --no-sumo            # 用 samples/ 跳过 SUMO 只串链路
  python work/twin/loop.py --scenario scenario_1 --seed 42 --duration 3600

模块内实现细节属"推荐"档,可自选方式;换法在 PR 的「实现方式」栏说明。
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

TICK_S = 1  # 孪生推进一步 = 1 秒(README 第六节)
SNAPSHOT_EVERY_S = 60  # 每 60 s 出一次快照:指标/判级、同化回灌、预约表

HERE = Path(__file__).resolve().parent
DEFAULT_SAMPLES_DIR = HERE / "samples"
DEFAULT_OUT_DIR = HERE / "out"

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
        "note": "样例链路(演示数据(模拟)):samples/ 进,out/ 出,不依赖 SUMO 与上游数据",
    }
    written["run_log.json"] = write_json(cfg.out_dir / "run_log.json", log)
    assert_artifact(cfg.out_dir / "run_log.json")
    return 0


def run_with_sumo(cfg: LoopConfig) -> int:
    """真孪生主循环:SUMO 走一步 ↔ TraCI 司机行为体(骨架,TODO)。"""
    raise NotImplementedError(
        "SUMO 主循环待 W1 实现:1 s 推进一步、60 s 出快照(README 第六节)"
    )


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
        """把仿真时钟推进若干秒(不超过 duration),返回推进后的时刻。"""
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
    ns = parser.parse_args(argv)
    return LoopConfig(
        scenario=ns.scenario,
        seed=ns.seed,
        duration_s=ns.duration_s,
        out_dir=Path(ns.out_dir),
        samples_dir=Path(ns.samples_dir),
        no_sumo=ns.no_sumo,
        site=ns.site,
    )


def main(argv: list[str] | None = None) -> int:
    cfg = parse_args(argv)
    if cfg.no_sumo:
        return run_no_sumo(cfg)
    return run_with_sumo(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
