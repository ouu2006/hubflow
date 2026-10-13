"""work/twin 模块统一入口(开发规范 §3 / §6:每个模块一个 run.py,加 --sample 能单独跑)。

输入:work/twin/samples/*_sample.json(--sample)
输出:work/twin/out/ 下的快照(segments / vehicles / assimilation_state / run_log)
口径:--sample 委托 loop.py --no-sumo —— 不依赖 SUMO、不依赖上游数据;
     读 samples/ 写 out/,**不许覆盖样例输入**。

用法:
  python work/twin/run.py --sample
  python work/twin/run.py --scenario scenario_1 --seed 42 --duration 3600   # 真孪生(需 SUMO)
"""

from __future__ import annotations

import argparse

import loop


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="work/twin 模块统一入口")
    parser.add_argument("--sample", action="store_true", help="用 samples/ 跑通链路(跳过 SUMO)")
    parser.add_argument("--scenario", default="scenario_1")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--duration", type=int, default=loop.SNAPSHOT_EVERY_S, dest="duration_s")
    parser.add_argument("--out", default=str(loop.DEFAULT_OUT_DIR), dest="out_dir")
    parser.add_argument("--site", default="")
    ns, _extra = parser.parse_known_args(argv)

    forward = [
        "--scenario", ns.scenario,
        "--seed", str(ns.seed),
        "--duration", str(ns.duration_s),
        "--out", ns.out_dir,
        "--site", ns.site,
    ]
    if ns.sample:
        forward.append("--no-sumo")
    return loop.main(forward)


if __name__ == "__main__":
    raise SystemExit(main())
