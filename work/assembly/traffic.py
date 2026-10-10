"""work/assembly/traffic.py · 接口层骨架（Issue #40，W0，2026-10-11）。

定位：演示前最后一步——把已落盘的快照文件包成 HTTP 接口给双端调用。
纪律（见 work/assembly/README.md 第二、四节）：
  1. 只读快照、不写快照：本层不产生任何业务数据，禁止在这里算指标 / 判级 / 推荐；
  2. 每个响应都带 ``is_simulated``（一期恒为 true）；
  3. SSE 只新增事件名（``traffic_*``），不改既有事件名；
  4. 既有 8 端点零改动（C-1）：本文件是独立应用，不碰上游 ``host-fastapi``，
     上游 ``app/main.py`` 的 diff 只允许出现"新增注册"。

快照来源（``docs/数据契约.md`` v2.0）：``segments.json`` / ``routes.json`` /
``vehicles.json``，默认目录 ``work/assembly/out/<run_ts>/``（由 run_all.py 产出），
用环境变量 ``HUBFLOW_SNAPSHOT_DIR`` 覆盖。快照不存在时返回 503——不造数。

骨架状态：直接映射快照文件的端点已可用；需要引擎逻辑的端点返回 501 并标注
归属（判级 / 推荐归开发B，指标归开发A）。前端接入前按契约对齐响应形状。

运行：``python work/assembly/traffic.py``（默认 127.0.0.1:8090）
依赖：``pip install fastapi uvicorn``（换机需补装，见 README 第七节）。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse, StreamingResponse
except ImportError as exc:  # pragma: no cover - 环境缺依赖时的可读报错
    raise SystemExit(
        "traffic.py 需要 fastapi 与 uvicorn：pip install fastapi uvicorn"
    ) from exc

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNAPSHOT_DIR = Path(__file__).resolve().parent / "out"
SNAPSHOT_FILES = {
    "segments": "segments.json",
    "routes": "routes.json",
    "vehicles": "vehicles.json",
    "assimilation": "assimilation_state.json",
}

app = FastAPI(title="hubflow traffic api（骨架）", version="0.1.0")


def snapshot_dir() -> Path:
    return Path(os.environ.get("HUBFLOW_SNAPSHOT_DIR", DEFAULT_SNAPSHOT_DIR))


def load_snapshot(name: str) -> dict | list:
    """读一份快照文件。只读；缺失时 503，绝不返回编造的数据。"""
    path = snapshot_dir() / SNAPSHOT_FILES[name]
    if not path.is_file():
        raise HTTPException(
            status_code=503,
            detail=f"快照不存在：{path}。请先运行一键脚本生成快照（run_all.py）。",
        )
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def enveloped(data: object) -> dict:
    """统一响应壳：一期所有响应都显式携带 is_simulated。"""
    return {"is_simulated": True, "data": data}


# ---------- 直接映射快照的端点（骨架已可用） ----------


@app.get("/api/traffic/segments")
def api_segments(source: str | None = None) -> dict:
    """路段级指标与等级列表。?source=video|twin 过滤（TC-19 并排展示）。"""
    segments = load_snapshot("segments")
    if isinstance(segments, dict):
        segments = segments.get("segments", segments)
    if source:
        segments = [s for s in segments if s.get("source") == source]
    return enveloped(segments)


@app.get("/api/traffic/segments/{segment_id}")
def api_segment_detail(segment_id: str) -> dict:
    """单路段详情，含 factors_applied / pred。"""
    segments = load_snapshot("segments")
    if isinstance(segments, dict):
        segments = segments.get("segments", segments)
    for seg in segments:
        if seg.get("segment_id") == segment_id or seg.get("id") == segment_id:
            return enveloped(seg)
    raise HTTPException(status_code=404, detail=f"路段不存在：{segment_id}")


@app.get("/api/traffic/vehicles")
def api_vehicles() -> dict:
    """一期演示：孪生车辆位置（读 vehicles.json）。二期下线。"""
    return enveloped(load_snapshot("vehicles"))


@app.get("/api/traffic/assimilation")
def api_assimilation() -> dict:
    """数据同化状态：只读 assimilation_state.json，不改 segments.json 形状。"""
    return enveloped(load_snapshot("assimilation"))


@app.get("/api/traffic/factors")
def api_factors() -> dict:
    """当前生效因素清单：从各路段 factors_applied 展平汇总（不重算）。"""
    segments = load_snapshot("segments")
    if isinstance(segments, dict):
        segments = segments.get("segments", segments)
    factors = []
    for seg in segments:
        for factor in seg.get("factors_applied", []):
            factors.append({"segment_id": seg.get("segment_id", seg.get("id")), **factor})
    return enveloped(factors)


# ---------- 需要引擎逻辑的端点（骨架：501 + 归属标注） ----------


@app.post("/api/traffic/route/recommend")
def api_route_recommend() -> JSONResponse:
    """推荐结果由引擎写进 routes.json 快照；本层只负责端出去，不做选择计算。"""
    raise HTTPException(
        status_code=501,
        detail="骨架未接入：推荐快照的消费逻辑待前端接入时对齐（归属：开发B 决策）。",
    )


@app.post("/api/traffic/locate")
def api_locate() -> JSONResponse:
    """定位 → 路段。一期由孪生真值调用，二期由 App 调用。归属：开发B locate.py。"""
    raise HTTPException(status_code=501, detail="骨架未接入：定位匹配归开发B（locate.py）。")


@app.get("/api/traffic/predict")
def api_predict(segment_id: str | None = None, h: int = 15) -> dict:
    """预测：一期 L0。pred 字段已在快照里，本层只按参数取用，不自己算。"""
    segments = load_snapshot("segments")
    if isinstance(segments, dict):
        segments = segments.get("segments", segments)
    for seg in segments:
        if seg.get("segment_id") == segment_id and "pred" in seg:
            return enveloped({"segment_id": segment_id, "h": h, "pred": seg["pred"]})
    raise HTTPException(
        status_code=501,
        detail="骨架未取到该路段的 pred 快照字段（归属：开发A 指标层 / 开发B 判级）。",
    )


@app.get("/api/traffic/alerts")
def api_alerts() -> dict:
    """告警列表：待契约补 alerts 快照形态后接入（triggered_by 归档见契约 v2.0）。"""
    raise HTTPException(status_code=501, detail="骨架未接入：告警快照形态待契约侧确认。")


@app.post("/api/traffic/plan/dispatch")
def api_plan_dispatch() -> JSONResponse:
    raise HTTPException(status_code=501, detail="骨架未接入：分流方案下发（一期走快照回写流程）。")


@app.post("/api/traffic/plan/ack")
def api_plan_ack() -> JSONResponse:
    raise HTTPException(status_code=501, detail="骨架未接入：处置回写（一期走快照回写流程）。")


@app.get("/api/traffic/report/compare")
def api_report_compare() -> JSONResponse:
    raise HTTPException(status_code=501, detail="骨架未接入：效果对比报表（TC-14 / TC-17 对照数据）。")


# ---------- SSE（只新增事件名 traffic_*，不改既有事件名） ----------


@app.get("/api/traffic/stream")
async def api_stream() -> StreamingResponse:
    """快照刷新事件流。复用上游 SSE 形状，事件名是新增的 traffic_snapshot。"""

    async def events():
        yield "event: traffic_snapshot\ndata: {\"is_simulated\": true, \"note\": \"骨架：快照刷新事件\"}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


if __name__ == "__main__":  # pragma: no cover - 进程入口
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("HUBFLOW_TRAFFIC_PORT", "8090")))
