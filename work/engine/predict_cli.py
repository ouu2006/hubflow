"""一期 L0 预测 CLI(T5):读 segments 快照 → 产 `predict.json`(当前值保持)。

用法:
    python work/engine/predict_cli.py --segments <path> [--out <path>]

- `--segments` **必填**;文件不存在直接报错退出(**不猜默认路径**——猜路径是编数据);
- `--out` 默认 `work/engine/out/latest/predict.json`(out/ 属 gitignore,非基线产物);
- 输出 schema 与字段语义见 `predict.py::build_snapshot` 的 docstring(T5 卡照录):
  segments 按 `segment_id` 排序 → **同一输入两遍跑逐字节一致**;
- **不写 `segments.json`**:本 CLI 只读快照、只写预测文件;
- 给 C 的合并规格(端点如何消费本文件)见 T5 报告,本文件不接 HTTP。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 直跑时 import 同目录 predict

from predict import build_snapshot  # noqa: E402

#: 默认输出:`work/engine/out/latest/predict.json`(__file__ 在 work/engine/ 下)
DEFAULT_OUT = Path(__file__).resolve().parents[0] / "out" / "latest" / "predict.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--segments", required=True,
                        help="segments 快照路径(segments.json / segments_twin.json 形状)")
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                        help="输出 predict.json 路径(默认 work/engine/out/latest/predict.json)")
    ns = parser.parse_args(argv)

    segments_path = Path(ns.segments)
    if not segments_path.is_file():
        print(f"[predict_cli] --segments 文件不存在: {segments_path}(不猜默认路径,退出)",
              file=sys.stderr)
        return 2

    try:
        snapshot = build_snapshot(segments_path)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"[predict_cli] 输入不合法: {exc}", file=sys.stderr)
        return 2

    out_path = Path(ns.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(snapshot, ensure_ascii=False, indent=1) + "\n"
    out_path.write_text(text, encoding="utf-8")
    print(f"[predict_cli] 已写出 {out_path}"
          f"({len(snapshot['segments'])} segments,model={snapshot['model']},"
          f"ts={snapshot['ts']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
