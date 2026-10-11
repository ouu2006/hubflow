"""感知监控演示数据导出(供 /perception 监控页与感知服务使用,Issue #54)。

链路与上游 0-6 复跑一致(同一 MindSpore 检测 + ByteTrack 跟踪),区别只在输出:
不再合成标注 mp4,而是导出「原始帧 JPEG 序列 + 逐帧检测框 JSON」,
由感知服务(work/perception/server.py)出接口、前端画框——
检测框是数据而不是烤进画面的像素,这就是"YOLO 监控"页的真实数据源。

产物(输出目录整树不入库,.gitignore 已拦 work/perception/data/):
  <out>/<stream_id>/meta.json         视频与统计元信息
  <out>/<stream_id>/detections.json   逐帧检测框(归一化坐标/类别/置信度/轨迹 ID)
  <out>/<stream_id>/frames/000001.jpg 原始帧序列(浏览器不依赖 mp4 解码)

用法(必须用上游 traffic-ms311 venv;上游仓零改动,这里只 import):
  python dump_monitor_data.py --video <上游仓>/traffic-core-mindspore/video/track1.mp4 \
    --out ../data/monitor

口径:样本视频非肇庆东站现场;产物仅用于管理端演示(演示数据(模拟))。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
import time
from pathlib import Path

import cv2

# 上游仓与本仓同级(协作约定:agentic-traffic-management 必须 clone 在 hubflow 旁边);
# 这里只 import 不改动。MindSporeDetector 的权重/网络配置按其 REPO_ROOT 解析。
HUBFLOW_ROOT = Path(__file__).resolve().parents[3]  # tools → perception → work → hubflow
UPSTREAM_CORE = HUBFLOW_ROOT.parent / "agentic-traffic-management" / "traffic-core-mindspore"
sys.path.insert(0, str(UPSTREAM_CORE))

from core.mindspore_detector import MindSporeDetector  # noqa: E402
from core.tracker import ByteTracker  # noqa: E402

# COCO 交通相关白名单(0 行人 1 自行车 2 小汽车 3 摩托车 5 公交车 7 货车)。
# 不白名单会在路口段把手机/玩偶等误检类别也带进画面(0-6 实测出现过 67/74)。
CLASS_WHITELIST = (0, 1, 2, 3, 5, 7)
CLASS_NAMES_ZH = {0: "行人", 1: "自行车", 2: "小汽车", 3: "摩托车", 5: "公交车", 7: "货车"}
CONF_THRESHOLD = 0.35
IOU_THRESHOLD = 0.5
IMGSZ = 640  # 与上游 track 链路同尺寸
FRAME_MAX_WIDTH = 960  # 帧序列 JPEG 的最大宽度,超出则等比缩小
JPEG_QUALITY = 82


def _save_jpg(frame, path: Path) -> None:
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
    if not ok:
        raise IOError(f"JPEG 编码失败: {path}")
    buf.tofile(str(path))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video", required=True, help="样本视频路径")
    ap.add_argument("--out", default="../data/monitor", help="输出根目录")
    args = ap.parse_args()

    video_path = Path(args.video)
    stream_id = video_path.stem
    out_dir = Path(args.out) / stream_id
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"无法打开视频: {video_path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    src_w, src_h = int(cap.get(3)), int(cap.get(4))
    scale = min(1.0, FRAME_MAX_WIDTH / max(src_w, 1))
    out_w, out_h = round(src_w * scale), round(src_h * scale)

    # 一个 detector 实例对应一个视频(与 core.tracking 相同的 persist 语义边界);
    # _infer/ByteTracker 直接取用,是为了拿到 FrameResult 协议里没有的逐框置信度。
    detector = MindSporeDetector("yolov8n.pt")
    detector._tracker = ByteTracker()

    frames: list[dict] = []
    first_seen: dict[int, dict] = {}
    idx = 0
    t_start = time.time()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if scale < 1.0:
            frame = cv2.resize(frame, (out_w, out_h))
        _det, boxes_xyxy, _xywh, cls, confs, _masks = detector._infer(
            frame, CONF_THRESHOLD, IOU_THRESHOLD, -1, IMGSZ
        )
        keep = [i for i, c in enumerate(cls) if int(c) in CLASS_WHITELIST]
        step = detector._tracker.update(
            boxes_xyxy[keep], confs[keep], cls[keep]
        ) if keep else None

        dets = []
        if step is not None and len(step.track_ids):
            for x1, y1, x2, y2, c, cf, tid in zip(
                step.boxes_xyxy[:, 0], step.boxes_xyxy[:, 1],
                step.boxes_xyxy[:, 2], step.boxes_xyxy[:, 3],
                step.classes, step.confs, step.track_ids,
            ):
                tid = int(tid)
                dets.append([
                    round(float(x1) / out_w, 4), round(float(y1) / out_h, 4),
                    round(float(x2) / out_w, 4), round(float(y2) / out_h, 4),
                    int(c), round(float(cf), 3), tid,
                ])
                if tid not in first_seen:
                    first_seen[tid] = {"frame": idx, "class": int(c), "conf": round(float(cf), 3)}
        if dets:
            frames.append({"i": idx, "det": dets})
        _save_jpg(frame, frames_dir / f"{idx + 1:06d}.jpg")
        idx += 1
        if idx % 50 == 0:
            print(f"[{stream_id}] {idx} 帧, 累计 {len(first_seen)} 轨迹, {time.time() - t_start:.0f}s")
    cap.release()

    total = idx
    class_counts: dict[int, int] = {}
    for info in first_seen.values():
        class_counts[info["class"]] = class_counts.get(info["class"], 0) + 1

    meta = {
        "stream_id": stream_id,
        "source_file": video_path.name,
        "note": "样本视频回放(非本站现场)· 演示数据(模拟)",
        "fps": round(src_fps, 2),
        "width": out_w,
        "height": out_h,
        "total_frames": total,
        "duration_s": round(total / src_fps, 1) if src_fps else None,
        "conf_threshold": CONF_THRESHOLD,
        "iou_threshold": IOU_THRESHOLD,
        "model": "yolov8n.ckpt",
        "backend": "MindSpore 2.8.0 + MindYOLO(检测) + ByteTrack(跟踪)",
        "class_names": {str(k): v for k, v in CLASS_NAMES_ZH.items()},
        "class_counts": {str(k): v for k, v in sorted(class_counts.items())},
        "track_total": len(first_seen),
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
    }
    detections = {
        "fps": meta["fps"],
        "width": out_w,
        "height": out_h,
        "total_frames": total,
        "first_seen": {str(k): v for k, v in first_seen.items()},
        # 只存有检测的帧;前端按"≤当前帧号的最近一条"取框。
        "frames": frames,
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "detections.json").write_text(
        json.dumps(detections, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"[{stream_id}] 完成: {total} 帧, {len(first_seen)} 条轨迹, "
        f"类别计数 {meta['class_counts']}, 耗时 {time.time() - t_start:.0f}s"
    )


if __name__ == "__main__":
    main()
