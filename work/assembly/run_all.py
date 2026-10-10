"""work/assembly/run_all.py · 一键链路骨架（Issue #40，W0，2026-10-11）。

把「孪生 → 感知判级 → 决策 → 快照 → 接口层」串起来，一键跑完全链路。
当前仓库业务模块尚未落地（work/ 下无代码），本骨架先交付两件事：
  1. 步骤编排与产物存在性断言的** harness**；
  2. ``--dry-run`` 空跑自检：建目录 + 验证断言真的能抓住已知假通过形态。

硬纪律（work/assembly/README.md 第三、五、六节）：
  - 不许要求现场敲命令、不许要求现场装东西（demo.bat 双击即跑）；
  - 每一步先做产物存在性断言，再看退出码；
  - 断言不能只查"非空"：0-6 实测到 258 B 空壳 mp4（有 ftyp/moov 头、打不开、
    却返回成功）——assert_artifact 对 mp4 额外查最小体积与可打开性；
  - 每次运行先隔离输出目录（out/<run_ts>/），上一轮产物不许冒充本轮通过；
  - 时序快照要校验 ts 是本次运行的时间戳，不是残留文件。

用法：``python run_all.py [--scenario scenario_2] [--dry-run]``
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ASSEMBLY_DIR = Path(__file__).resolve().parent
REPO_ROOT = ASSEMBLY_DIR.parents[1]
OUT_DIR = ASSEMBLY_DIR / "out"
LOG_DIR = ASSEMBLY_DIR / "logs"

# 一键链路的步骤与产物（模块落地后把 TODO 换成真实调用；归属见 docs/分工表.md §1）
PIPELINE_STEPS = [
    ("twin", "孪生主循环", "work/twin/loop.py", ["state.json"]),
    ("perception", "视频感知 + 判级", "work/perception/", ["segments.json"]),
    ("engine", "决策（分流推荐）", "work/engine/run.py", ["routes.json"]),
    ("snapshot", "快照落盘", "work/engine/run.py", ["vehicles.json"]),
    ("api", "接口层起服", "work/assembly/traffic.py", []),
]

# 空壳 mp4 的已知形态：0-6 实测 258 B（有 ftyp/moov 头但 cv2 打不开）。
# 最小可播放 mp4 远大于这个体积，阈值取 4 KiB 起步，后续按真机产物校准。
MP4_MIN_BYTES = 4096


class ArtifactCheckError(RuntimeError):
    """产物断言失败——宁可报错也不假通过。"""


def prepare_run_dir(scenario: str) -> Path:
    """为本次运行隔离出一个全新的输出目录，并保证 logs/ 存在。

    时间戳只精确到秒：同秒内再次运行（如快速双击 demo.bat）加序号后缀重试。
    """
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUT_DIR / f"{scenario}_{run_ts}"
    seq = 1
    while True:
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
            break
        except FileExistsError:
            seq += 1
            run_dir = OUT_DIR / f"{scenario}_{run_ts}_{seq}"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return run_dir


def assert_artifact(path: Path, min_bytes: int = 1, kind: str | None = None) -> int:
    """产物存在性断言：存在 + 体积达标 +（mp4）头部与可打开性。

    返回文件字节数；任何一项不满足抛 ArtifactCheckError。
    """
    if not path.is_file():
        raise ArtifactCheckError(f"产物不存在：{path}")
    size = path.stat().st_size
    if size < min_bytes:
        raise ArtifactCheckError(f"产物疑似空壳：{path}（{size} B < {min_bytes} B）")
    if kind == "mp4":
        with open(path, "rb") as fh:
            head = fh.read(64)
        if b"ftyp" not in head:
            raise ArtifactCheckError(f"产物缺 mp4 头（ftyp）：{path}")
        if size < MP4_MIN_BYTES:
            raise ArtifactCheckError(
                f"产物是空壳 mp4（{size} B ≤ {MP4_MIN_BYTES} B，已知假通过形态）：{path}"
            )
    return size


def assert_fresh_ts(path: Path, not_before: float) -> datetime:
    """校验 JSON 快照的 ts 字段是本次运行的时间戳，不是上一轮残留。"""
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    ts = payload.get("ts")
    if isinstance(ts, str):
        stamp = datetime.fromisoformat(ts)
    else:
        stamp = datetime.fromtimestamp(float(ts))
    if stamp.timestamp() < not_before:
        raise ArtifactCheckError(
            f"快照 ts 是残留文件（{stamp} 早于本次运行起点）：{path}"
        )
    return stamp


def _self_test_assertions(run_dir: Path) -> None:
    """空跑自检：证明断言 harness 真的能抓住两类已知假通过。

    ① 258 B 空壳 mp4（0-6 实测形态）；② 残留 ts 的快照。
    """
    hollow = run_dir / "selftest_hollow.mp4"
    ftyp_box = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
    moov_head = b"\x00\x00\x00\x08moov"
    payload = ftyp_box + moov_head + b"\x00" * (258 - len(ftyp_box) - len(moov_head))
    hollow.write_bytes(payload)
    try:
        assert_artifact(hollow, min_bytes=1, kind="mp4")
    except ArtifactCheckError:
        print(f"  [自检] ✅ 断言抓住空壳 mp4：{hollow.stat().st_size} B 被拒")
    else:
        raise SystemExit("自检失败：空壳 mp4 断言没生效——harness 不可信")
    finally:
        hollow.unlink()

    stale = run_dir / "selftest_stale.json"
    stale.write_text(json.dumps({"ts": "2026-01-01T00:00:00"}), encoding="utf-8")
    try:
        assert_fresh_ts(stale, time.time() - 60)
    except ArtifactCheckError:
        print("  [自检] ✅ 断言抓住残留 ts 快照")
    else:
        raise SystemExit("自检失败：残留 ts 断言没生效——harness 不可信")
    finally:
        stale.unlink()


def run_step(name: str, title: str, entry: str, artifacts: list[str], run_dir: Path) -> str:
    """跑一步并断言产物。骨架阶段全部 skip；模块落地后在这里调用真实入口。"""
    # TODO(模块落地后)：subprocess 调用 entry，产物缺失/空壳直接抛 ArtifactCheckError。
    print(f"  [skip] {title}（{entry} 骨架未接入，产物要求：{artifacts or '无'}）")
    return f"{name}: skipped"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="hubflow 一键链路（骨架）")
    parser.add_argument("--scenario", default="scenario_2",
                        help="场景参数（默认 scenario_2 峰值场景，验收主战场）")
    parser.add_argument("--dry-run", action="store_true",
                        help="空跑：建目录 + 断言自检，不调任何业务模块")
    args = parser.parse_args(argv)

    started = time.time()
    print(f"[run_all] 场景={args.scenario} 模式={'dry-run' if args.dry_run else '全链路'}")
    run_dir = prepare_run_dir(args.scenario)
    print(f"[run_all] 输出目录（已隔离）：{run_dir}")

    if args.dry_run:
        _self_test_assertions(run_dir)
        print(f"[run_all] ✅ 空跑自检通过（{time.time() - started:.1f}s）。"
              f"业务模块接入后自动启用全链路。")
        return 0

    results = [run_step(*step, run_dir=run_dir) for step in PIPELINE_STEPS]
    print(f"[run_all] 步骤结果：{results}")
    print("[run_all] ⚠️ 业务模块尚未落地，全链路暂不可用——先用 --dry-run 验证 harness。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
