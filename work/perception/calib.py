r"""透视标定：像素轨迹 → 米制轨迹（`stations/calibration.json` → H 矩阵）。

**这一步为什么必须有**：YOLO 出来的是**像素**，判级要的是**米/秒**。
没有标定，"视频识别正在算路段拥堵"这句话就不成立（M1-9）。

口径（手册 §5.2）：
    · 单应矩阵用 OpenCV `findHomography`（DLT + RANSAC）；
    · 控制点 ≥ 4 组（推荐 6–8 组），由池·V 拾取；本版是**按标准车道宽 3.5 m 推算**的
      初始点（`calibration.json` 里 `inferred: true`），够跑通链路，精度不是它的强项；
    · 精度留证：**重投影误差 ≤ 3 px**【demo 目标值】、尺度误差 ≤ 3%【demo 目标值】；
    · **有效标定带**：远边界取"1 像素对应实际距离 ≤ 0.5 m"。超带的目标**只计车辆数
      （流量 / 密度），不计入速度统计** —— 远处 1 px 就是好几米，速度算出来是假的。

用法：
    python work/perception/calib.py --stream track1          # 单路
    python work/perception/calib.py --all                    # calibration.json 里全部
    python work/perception/calib.py --all --out out/calib    # 落盘报告
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DIR = Path(__file__).resolve().parent
ROOT = DIR.parents[1]                      # work/perception -> work -> hubflow
STATIONS = ROOT / "stations"
MONITOR = DIR / "data" / "monitor"

# 有效标定带的判据：1 像素对应的实际距离上限（米）。手册 §5.2 的 demo 口径。
PX_TO_M_MAX = 0.5


class Calibration:
    """一路视频的标定结果：H 矩阵 + 误差存证 + 有效标定带。"""

    def __init__(self, stream_id: str, H: np.ndarray, image: dict,
                 reproj_px: float, scale_err_pct: float,
                 band_near_y: float, band_far_y: float, inferred: bool,
                 reproj_limit_px: float = 3.0, scale_limit_pct: float = 3.0):
        self.stream_id = stream_id
        self.H = H
        self.image = image
        self.reproj_px = reproj_px
        self.scale_err_pct = scale_err_pct
        # 有效标定带：画面 y 坐标（像素）的可用区间。y 越大离镜头越近。
        self.band_near_y = band_near_y
        self.band_far_y = band_far_y
        self.inferred = inferred
        # 判据阈值来自 stations/calibration.json（load() 读入，不写死）
        self.reproj_limit_px = float(reproj_limit_px)
        self.scale_limit_pct = float(scale_limit_pct)

    def to_world(self, px: float, py: float) -> tuple[float, float]:
        """像素 → 世界米（车行方向 +Y、左侧 +X，见 calibration.json 的 world_note）。"""
        v = self.H @ np.array([px, py, 1.0])
        if abs(v[2]) < 1e-12:
            return (float("nan"), float("nan"))
        return (float(v[0] / v[2]), float(v[1] / v[2]))

    def in_valid_band(self, py: float) -> bool:
        """是否落在有效标定带内（带外只计车辆数，不计速度）。"""
        return self.band_far_y <= py <= self.band_near_y

    def summary(self) -> dict:
        return {
            "stream_id": self.stream_id,
            "inferred": self.inferred,
            "reprojection_error_px": round(self.reproj_px, 3),
            "reprojection_ok": self.reproj_px <= self.reproj_limit_px,
            "scale_error_pct": round(self.scale_err_pct, 3),
            "scale_ok": self.scale_err_pct <= self.scale_limit_pct,
            "valid_band_px": [round(self.band_far_y, 1), round(self.band_near_y, 1)],
            "H": [[round(float(x), 8) for x in row] for row in self.H],
        }


def solve(points: list[dict], image: dict) -> Calibration:
    """控制点 → 单应矩阵 + 误差存证。

    **精度怎么留证**（关键）：控制点全用来解 H 的话，重投影误差必然接近 0——
    那是"自己考自己"，说明不了任何问题。所以这里做 **留一交叉验证**（leave-one-out）：
    每次去掉一个控制点、用剩下的解 H，量被去掉那个点的重投影误差，取最大值。
    这个数才是"标定能不能用"的真实凭据（M1-9 的 ≤3 px 判据量的是它）。
    """
    import cv2

    src = np.array([p["px"] for p in points], dtype=np.float64)
    dst = np.array([p["world"] for p in points], dtype=np.float64)
    if len(src) < 4:
        raise SystemExit(f"控制点只有 {len(src)} 组，至少 4 组（手册 §5.2）")

    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
    if H is None:
        raise SystemExit("findHomography 求解失败：控制点可能共线")

    # ---- 留一交叉验证：真正的精度留证 ----
    loo_errs: list[float] = []
    for k in range(len(src)):
        keep = [i for i in range(len(src)) if i != k]
        Hk, _ = cv2.findHomography(src[keep], dst[keep], 0)     # 不用 RANSAC，纯 DLT
        if Hk is None:
            continue
        wx, wy = _apply(Hk, float(src[k][0]), float(src[k][1]))
        # 世界坐标误差 → 用该点邻域的米/像素比折回像素
        local = _px_scale(Hk, float(src[k][0]), float(src[k][1]))
        if local > 1e-9:
            loo_errs.append(float(np.hypot(wx - dst[k][0], wy - dst[k][1])) / local)
    reproj = max(loo_errs) if loo_errs else 0.0

    # ---- 尺度误差：**用 H 从像素反算已知长度，与真实长度比** ----
    # 手册说的"尺度误差 ≤ 3%"就是这个意思：图上量一段已知的真实距离（车道宽 3.5 m、
    # 停止线长度…），误差是多少。不是量"投影的非线性程度"（那必然很大，说明不了问题）。
    scale_errs: list[float] = []
    for i in range(len(src)):
        for j in range(i + 1, len(src)):
            d_world = float(np.hypot(*(dst[i] - dst[j])))
            if d_world < 1e-6:
                continue
            # 从**像素**经 H 反算世界坐标，再量距离
            wi = _apply(H, float(src[i][0]), float(src[i][1]))
            wj = _apply(H, float(src[j][0]), float(src[j][1]))
            d_est = float(np.hypot(wi[0] - wj[0], wi[1] - wj[1]))
            if d_est > 1e-6:
                scale_errs.append(abs(d_est - d_world) / d_world)
    scale_err = max(scale_errs) * 100.0 if scale_errs else 0.0

    # ---- 有效标定带：**不得超过控制点覆盖的范围**（外推区没有标定依据）----
    h = float(image.get("height") or 540)
    w = float(image.get("width") or 960)
    cx = w / 2.0
    ctrl_far_y = max(float(p["px"][1]) for p in points)   # 最远控制点的 y（最小 y 值）
    ctrl_far_y = min(float(p["px"][1]) for p in points)
    ctrl_near_y = max(float(p["px"][1]) for p in points)
    step = 4.0
    far_y = ctrl_far_y
    prev = None
    y = ctrl_near_y
    while y > ctrl_far_y:
        wx, wy = _apply(H, cx, y)
        if prev is not None:
            d = float(np.hypot(wx - prev[0], wy - prev[1]))
            if d / step > PX_TO_M_MAX:
                far_y = y
                break
        prev = (wx, wy)
        y -= step
    return Calibration(
        stream_id="", H=H, image=image,
        reproj_px=reproj, scale_err_pct=scale_err,
        band_near_y=ctrl_near_y, band_far_y=max(ctrl_far_y, far_y), inferred=False,
    )


def _px_scale(H: np.ndarray, px: float, py: float, eps: float = 2.0) -> float:
    """某像素点处的局部米/像素比（用 H 在 ±eps 像素上做差）。"""
    x0, y0 = _apply(H, px - eps, py)
    x1, y1 = _apply(H, px + eps, py)
    return float(np.hypot(x1 - x0, y1 - y0)) / (2 * eps)


def _apply(H: np.ndarray, px: float, py: float) -> tuple[float, float]:
    v = H @ np.array([px, py, 1.0])
    if abs(v[2]) < 1e-12:
        return (float("nan"), float("nan"))
    return (float(v[0] / v[2]), float(v[1] / v[2]))


def load(stream_id: str) -> Calibration | None:
    """从 `stations/calibration.json` 读一路的标定并解出 H。"""
    path = STATIONS / "calibration.json"
    if not path.is_file():
        return None
    cfg = json.loads(path.read_text(encoding="utf-8"))
    reproj_limit = float(cfg.get("reprojection_threshold_px", 3.0))
    scale_limit = float(cfg.get("scale_error_target_pct", 3.0))
    for s in cfg.get("streams", []):
        if s["stream_id"] != stream_id:
            continue
        cal = solve(s["control_points"], s["image"])
        cal.stream_id = stream_id
        cal.inferred = bool(s.get("inferred", False))
        cal.lane_count = int(s.get("lane_count", 2))
        cal.segment_id = s.get("segment_id", "")
        cal.reproj_limit_px = reproj_limit
        cal.scale_limit_pct = scale_limit
        return cal
    return None


def to_metric_track(cal: Calibration, frames: list[dict], detections: dict) -> list[dict]:
    """逐帧检测框 → 米制轨迹点。

    输入 `frames`：`[{i, t, det: [[x1,y1,x2,y2,cls,conf,tid], …]}]`（归一化 0–1）
    输出：`[{t, tid, cls, conf, x, y, speed_ms, in_band}, …]`
    """
    w = float(detections.get("width") or cal.image.get("width") or 960)
    h = float(detections.get("height") or cal.image.get("height") or 540)
    out: list[dict] = []
    for fr in frames:
        t = fr.get("t")
        for x1, y1, x2, y2, cls, conf, tid in fr["det"]:
            # 取框底边中点当"车轮着地点"——透视标定用的是路面点，不是框中心
            px = (x1 + x2) / 2.0 * w
            py = y2 * h
            mx, my = cal.to_world(px, py)
            out.append({
                "t": t, "tid": int(tid), "cls": int(cls), "conf": float(conf),
                "x": round(mx, 3), "y": round(my, 3),
                "in_band": cal.in_valid_band(py),
                "py": round(py, 1),
            })
    return out


def add_speed(track: list[dict], fps: float) -> list[dict]:
    """按轨迹 id 排序后算相邻点的瞬时速度（m/s）。**只用带内的点**。"""
    by_tid: dict[int, list[dict]] = {}
    for p in track:
        by_tid.setdefault(p["tid"], []).append(p)
    out: list[dict] = []
    for tid, pts in by_tid.items():
        pts.sort(key=lambda p: (p["t"] if p["t"] is not None else 0))
        prev = None
        for p in pts:
            p = dict(p)
            if prev is not None and p["t"] is not None and prev["t"] is not None:
                dt = p["t"] - prev["t"]
                if dt > 1e-6 and p["in_band"] and prev["in_band"]:
                    d = float(np.hypot(p["x"] - prev["x"], p["y"] - prev["y"]))
                    p["speed_ms"] = round(d / dt, 3)
                else:
                    p["speed_ms"] = None      # 带外或时间戳缺失 → 不计速度
            else:
                p["speed_ms"] = None
            out.append(p)
            prev = p
    out.sort(key=lambda p: (p["t"] if p["t"] is not None else 0, p["tid"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", help="单路 stream_id")
    ap.add_argument("--all", action="store_true", help="calibration.json 里全部")
    ap.add_argument("--out", default=None, help="报告输出目录")
    args = ap.parse_args()

    if args.all:
        cfg = json.loads((STATIONS / "calibration.json").read_text(encoding="utf-8"))
        ids = [s["stream_id"] for s in cfg.get("streams", [])]
    elif args.stream:
        ids = [args.stream]
    else:
        raise SystemExit("要 --stream <id> 或 --all")

    report = []
    for sid in ids:
        cal = load(sid)
        if cal is None:
            print(f"[{sid}] 标定缺失（stations/calibration.json 里没有这一路）")
            continue
        s = cal.summary()
        report.append(s)
        flag = "OK" if (s["reprojection_ok"] and s["scale_ok"]) else "**超门限**"
        print(f"[{sid}] 重投影 {s['reprojection_error_px']} px（≤3 判据）· "
              f"尺度误差 {s['scale_error_pct']}% · 有效标定带 y∈{s['valid_band_px']} "
              f"· inferred={s['inferred']} → {flag}")

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "calib_report.json").write_text(
            json.dumps({"is_simulated": True, "streams": report},
                       ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        print(f"报告：{out / 'calib_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
