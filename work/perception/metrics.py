r"""四项指标：米制轨迹 → 流量 / 车速 / 密度 / 排队长度（`metrics.py`）。

**这一段是"图像 → 决策"的正中间**：上游是 `calib.py` 给的米制轨迹，下游是判级 `level.py`。
两条链路（视频 / 孪生）**共用这一套公式**，只有输入不同 —— 判级与决策**不得按 source 分支**。

四项指标（手册 §2.2）：

| 指标 | 字段 | 怎么算 |
|---|---|---|
| 流量 | `q_vph` | 窗口内通过**虚拟断面**的车辆数 ÷ 窗口秒数 × 3600 |
| 平均车速 | `v_kmh` | 窗口内带内轨迹点的瞬时速度均值（**超有效标定带的不计**） |
| 密度 | `k_vpk` | 窗口内在测车辆数 ÷ 路段长度 × 1000 |
| 排队长度 | `L_q_m` | 排队车辆沿车行方向的跨度（**只算"排队"那一类停车**）+ 消散时间 `T_d_min` |

**停车三类拆分**（手册点名的易错项，必须做）：

| 类别 | 判据 | 计入 |
|---|---|---|
| **排队** | 速度 < `QUEUE_SPEED_MS` 且**在车行道范围内**、不在落客/停车区 | **算拥堵**（进 L_q） |
| **落客服务** | 停在落客点邻域内 | **不算拥堵** |
| **违停** | 停下但**在车行道范围外**（路肩 / 非停车区） | **算事件**（进 `triggered_by`） |

**饱和口径是相对口径**：判级用"实测速度 ÷ 这条路的畅通速度"，不拿主干道标准量落客通道。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DIR = Path(__file__).resolve().parent
ROOT = DIR.parents[1]
STATIONS = ROOT / "stations"

# 排队判定：速度低于这个值视为"停下/缓行"（m/s）。约 5.4 km/h。
QUEUE_SPEED_MS = 1.5
# 落客点邻域半径（米）：圈内的停车算"落客服务"，不算拥堵。
DROPOFF_RADIUS_M = 15.0
# 停车/候客区邻域半径（米）。
ZONE_RADIUS_M = 25.0


def _load_points() -> dict:
    p = STATIONS / "points.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def classify_stops(track: list[dict], points_cfg: dict | None = None) -> list[dict]:
    """给每个轨迹点打停车分类标签：`moving` / `queue` / `dropoff_service` / `waiting` / `illegal`。

    判据全部在**世界米制坐标**里做（落客点、停车区、车道范围都是已知的世界坐标）：

    | 标签 | 判据 | 计不计拥堵 |
    |---|---|---|
    | `moving` | 速度 ≥ `QUEUE_SPEED_MS` | — |
    | `dropoff_service` | 停下且在落客点邻域内 | **不算** |
    | `waiting` | 停下且在候客/停车区邻域内 | **不算** |
    | `queue` | 停下、**在车行道范围内**、且不在上面两处 | **算**（进 L_q） |
    | `illegal` | 停下、**在车行道范围外**（路肩/非停车区） | 算事件（不进 L_q） |
    """
    cfg = points_cfg or {}
    dropoffs = cfg.get("_dropoff_xy") or []
    zones = cfg.get("_zone_xy") or []
    half_w = float(cfg.get("_lane_half_width_m") or 5.25)

    out: list[dict] = []
    for p in track:
        p = dict(p)
        sp = p.get("speed_ms")
        if sp is None or sp >= QUEUE_SPEED_MS:
            p["stop_class"] = "moving"
        else:
            x, y = p.get("x", 0.0), p.get("y", 0.0)
            if _within(x, y, dropoffs, DROPOFF_RADIUS_M):
                p["stop_class"] = "dropoff_service"     # 落客服务：不算拥堵
            elif _within(x, y, zones, ZONE_RADIUS_M):
                p["stop_class"] = "waiting"             # 候客/停车区：不算拥堵
            elif abs(x) <= half_w:
                p["stop_class"] = "queue"               # 车行道里排队：**算拥堵**
            else:
                p["stop_class"] = "illegal"             # 车行道外违停：算事件
        out.append(p)
    return out


def _within(x: float, y: float, pts: list, radius: float) -> bool:
    for px, py in pts:
        if (x - px) ** 2 + (y - py) ** 2 <= radius * radius:
            return True
    return False


def queue_length_m(track: list[dict]) -> float:
    """排队长度：**连续**排队车辆沿车行方向（y）的跨度。

    只算 `stop_class == "queue"`（**排队**）—— 落客服务与候客区停车**不进**这个数，
    违停也不进（它走事件）。
    """
    q = [p for p in track if p.get("stop_class") == "queue"]
    if len(q) < 2:
        return 0.0
    ys = [p.get("y", 0.0) for p in q]
    return round(max(ys) - min(ys), 1)


def dissipation_min(L_q: float, v_free_kmh: float, q_vph: float) -> float:
    """排队消散时间（min）：L_q 除以"消散流率的等效速度"。

    演示口径：消散速度取畅通速度的 60%（停车波 vs 启动波的经验比例），
    流率越大消散越快（更多车道在放行）。
    """
    if L_q <= 0:
        return 0.0
    v_ms = max(1.0, v_free_kmh * 0.6 / 3.6)
    lanes_factor = 1.0 + min(1.0, q_vph / 1800.0)
    return round(L_q / (v_ms * lanes_factor) / 60.0, 2)


def compute(
    track: list[dict],
    *,
    window_s: float = 60.0,
    segment_length_m: float = 500.0,
    section_y: float | None = None,
    v_free_kmh: float = 40.0,
    points_cfg: dict | None = None,
) -> dict:
    """米制轨迹 → 四项指标（**这个函数两条链路共用**）。

    参数
        track             `calib.to_metric_track()` + `add_speed()` 的产物
        window_s          统计窗口（秒，可配 → TC-01）
        segment_length_m  路段长度（密度用）
        section_y         虚拟断面的 y 坐标（米）；None 时取窗口内 y 的中位数
        v_free_kmh        本条路的畅通速度
    """
    tagged = classify_stops(track, points_cfg)
    if not tagged:
        return {
            "q_vph": 0.0, "v_kmh": None, "k_vpk": 0.0,
            "L_q_m": 0.0, "T_d_min": 0.0,
            "counts": {"total": 0, "in_band": 0, "queue": 0, "dropoff_service": 0,
                       "waiting": 0, "illegal": 0},
        }

    # ---- ① 流量：车辆越过虚拟断面的次数 ----
    ys = sorted(p.get("y", 0.0) for p in tagged if p.get("in_band"))
    cut = section_y if section_y is not None else (ys[len(ys) // 2] if ys else 0.0)
    by_tid: dict[int, list[dict]] = {}
    for p in tagged:
        by_tid.setdefault(int(p["tid"]), []).append(p)
    crossed = 0
    for pts in by_tid.values():
        pts.sort(key=lambda p: (p.get("t") or 0))
        for a, b in zip(pts, pts[1:]):
            if (a.get("y", 0.0) - cut) * (b.get("y", 0.0) - cut) < 0:
                crossed += 1
                break
    q_vph = round(crossed / max(1e-6, window_s) * 3600.0, 1)

    # ---- ② 车速：**只用带内的点**（带外 1 px 好几米，速度算出来是假的）----
    speeds = [p["speed_ms"] for p in tagged
              if p.get("in_band") and isinstance(p.get("speed_ms"), (int, float))]
    v_kmh = round(sum(speeds) / len(speeds) * 3.6, 1) if speeds else None

    # ---- ③ 密度：在测车辆数 / 路段长度 ----
    present = {int(p["tid"]) for p in tagged if p.get("in_band")}
    k_vpk = round(len(present) / max(1.0, segment_length_m) * 1000.0, 1)

    # ---- ④ 排队长度（只算"排队"那一类停车）----
    L_q = queue_length_m(tagged)

    counts = {
        "total": len({int(p["tid"]) for p in tagged}),
        "in_band": len(present),
        "queue": len({int(p["tid"]) for p in tagged if p.get("stop_class") == "queue"}),
        "dropoff_service": len({int(p["tid"]) for p in tagged
                                if p.get("stop_class") == "dropoff_service"}),
        "waiting": len({int(p["tid"]) for p in tagged if p.get("stop_class") == "waiting"}),
        "illegal": len({int(p["tid"]) for p in tagged if p.get("stop_class") == "illegal"}),
        "section_y": round(cut, 2),
        "speed_samples": len(speeds),
    }

    return {
        "q_vph": q_vph,
        "v_kmh": v_kmh,
        "k_vpk": k_vpk,
        "L_q_m": L_q,
        "T_d_min": dissipation_min(L_q, v_free_kmh, q_vph),
        "counts": counts,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", default="track1")
    ap.add_argument("--window", type=float, default=60.0, help="统计窗口（秒，TC-01 可配）")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    sys.path.insert(0, str(DIR))
    import calib as C  # noqa: E402

    det_path = DIR / "data" / "monitor" / args.stream / "detections.json"
    if not det_path.is_file():
        raise SystemExit(f"missing {det_path}（先跑 tools/dump_monitor_data.py）")
    det = json.loads(det_path.read_text(encoding="utf-8"))

    cal = C.load(args.stream)
    if cal is None:
        raise SystemExit(f"{args.stream} 没有标定（stations/calibration.json）")

    track = C.add_speed(C.to_metric_track(cal, det["frames"], det),
                        float(det.get("fps") or 30.0))
    m = compute(track, window_s=args.window,
                segment_length_m=float(det.get("width") or 960) / 2.0)
    print(f"[{args.stream}] q={m['q_vph']} 辆/h · v={m['v_kmh']} km/h · "
          f"k={m['k_vpk']} 辆/km · L_q={m['L_q_m']} m · T_d={m['T_d_min']} min")
    print(f"          停车分类：排队 {m['counts']['queue']} / 落客服务 "
          f"{m['counts']['dropoff_service']} / 候客 {m['counts']['waiting']} / "
          f"违停 {m['counts']['illegal']}")
    print(f"          速度样本 {m['counts']['speed_samples']}（带外不计速度）· "
          f"断面 y={m['counts']['section_y']}")

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"metrics_{args.stream}.json").write_text(
            json.dumps({"is_simulated": True, "stream_id": args.stream,
                        "window_s": args.window, **m},
                       ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        print(f"报告：{out / f'metrics_{args.stream}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
