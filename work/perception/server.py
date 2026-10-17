"""感知层演示服务(Issue #54,一期感知页的真实数据源)。

只做文件服务,不做推理——检测数据由 tools/dump_monitor_data.py 离线导出
(同一 MindSpore 检测 + ByteTrack 跟踪链路),本服务把「帧序列 + 逐帧检测框」
出成接口给 /perception 监控页。

启动(仓库任意 python 3.10+,需 fastapi+uvicorn):
  python work/perception/server.py                # 默认端口 8101,数据目录 ../data/monitor

接口(字段 snake_case;meta/health 端点响应带 is_simulated=true 信封,
  detections/frames 为原始检测载荷直接流式回、不含信封,演示数据(模拟)):
  GET /api/perception/health
  GET /api/perception/streams                          全部检测通道的 meta 列表
  GET /api/perception/streams/{sid}/meta               单通道元信息
  GET /api/perception/streams/{sid}/detections         逐帧检测框 JSON
  GET /api/perception/streams/{sid}/frames/{n}.jpg     第 n 帧(1 起)原始 JPEG

口径:样本视频非本站现场;本服务是一期接口面新增(感知面),不改冻结的 traffic 契约。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="hubflow perception demo", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

DATA_DIR = Path(__file__).resolve().parent / "data" / "monitor"

# ---- 摄像头 ↔ 通道 ↔ 路段 三段映射（Issue IKMDKY，唯一真值来源）----
# 数据文件 `data/monitor/*/meta.json` 不带 segment_id；本服务在**响应层**按登记表补
# `segment_id` / `cam_id` / `mapping_status`，**不改数据文件**（数据文件是导出产物）。
ROOT = Path(__file__).resolve().parents[2]
MAPPING_PATH = ROOT / "work/perception/mapping/camera-segments.json"


def _load_mapping() -> dict:
    if not MAPPING_PATH.is_file():
        return {}
    try:
        return json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


MAPPING = _load_mapping()
#: stream_id → 该通道绑定的登记信息（cam_id / segment_id / status / note）
STREAM_MAP: dict[str, dict] = {}
for _v in MAPPING.get("video_streams", []):
    STREAM_MAP[str(_v.get("stream_id"))] = {
        "cam_id": _v.get("cam_id"),
        "segment_id": _v.get("segment_id"),
        "mapping_status": _v.get("status", "demo-mapped"),
        "mapping_note": _v.get("note", ""),
    }
CAM_MAP: dict[str, dict] = {str(c.get("cam_id")): c for c in MAPPING.get("cameras", [])}


def _enrich_meta(meta: dict) -> dict:
    """按登记表给通道 meta 补三段映射字段（只读登记表；不编造）。"""
    sid = str(meta.get("stream_id", ""))
    hit = STREAM_MAP.get(sid)
    if hit is None:
        return {
            **meta,
            "segment_id": None,
            "cam_id": None,
            "cid": None,
            "mapping_status": "unmapped",
            "mapping_note": "该通道未在 work/perception/mapping/camera-segments.json 登记",
        }
    cam = CAM_MAP.get(str(hit.get("cam_id"))) or {}
    return {
        **meta,
        "segment_id": hit.get("segment_id"),
        "cam_id": hit.get("cam_id"),
        "cid": cam.get("cid"),
        "mapping_status": hit.get("mapping_status"),
        "mapping_note": hit.get("mapping_note", ""),
    }



def _envelope(payload: dict) -> JSONResponse:
    body = {"is_simulated": True, **payload}
    return JSONResponse(body, headers={"Cache-Control": "no-store"})


def _stream_dir(stream_id: str) -> Path:
    # stream_id 只允许简单标识符,防路径穿越
    if not stream_id.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(400, "非法 stream_id")
    d = DATA_DIR / stream_id
    if not d.is_dir():
        raise HTTPException(404, f"通道不存在: {stream_id}")
    return d


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise HTTPException(404, f"数据文件缺失: {path.name}(先跑 dump_monitor_data.py)")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/perception/health")
def health() -> JSONResponse:
    streams = sorted(p.name for p in DATA_DIR.iterdir() if p.is_dir()) if DATA_DIR.is_dir() else []
    return _envelope(
        {
            "status": "ok" if streams else "empty",
            "streams": streams,
            "data_dir": str(DATA_DIR),
            "mapping_registry": str(MAPPING_PATH.relative_to(ROOT)) if MAPPING else None,
            "mapping_cameras": len(MAPPING.get("cameras", [])),
            "mapping_video_streams": len(STREAM_MAP),
        }
    )


@app.get("/api/perception/streams")
def streams() -> JSONResponse:
    if not DATA_DIR.is_dir():
        return _envelope({"streams": []})
    items = []
    for d in sorted(DATA_DIR.iterdir()):
        meta_path = d / "meta.json"
        if d.is_dir() and meta_path.is_file():
            items.append(_enrich_meta(_read_json(meta_path)))
    return _envelope({"streams": items})


@app.get("/api/perception/streams/{sid}/meta")
def stream_meta(sid: str) -> JSONResponse:
    return _envelope(_enrich_meta(_read_json(_stream_dir(sid) / "meta.json")))


@app.get("/api/perception/streams/{sid}/detections")
def stream_detections(sid: str) -> FileResponse:
    # detections.json 可能数 MB,交给 FileResponse 直接流式回(浏览器侧自行缓存)
    path = _stream_dir(sid) / "detections.json"
    if not path.is_file():
        raise HTTPException(404, "detections.json 缺失(先跑 dump_monitor_data.py)")
    return FileResponse(path, media_type="application/json")


@app.get("/api/perception/streams/{sid}/frames/{idx}.jpg")
def stream_frame(sid: str, idx: int) -> FileResponse:
    if idx < 1:
        raise HTTPException(400, "帧号从 1 开始")
    path = _stream_dir(sid) / "frames" / f"{idx:06d}.jpg"
    if not path.is_file():
        raise HTTPException(404, "帧不存在")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


def main() -> None:
    global DATA_DIR
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8101)
    ap.add_argument("--data", default=None, help="检测数据目录(默认 <本文件目录>/data/monitor)")
    args = ap.parse_args()
    if args.data:
        DATA_DIR = Path(args.data).resolve()
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
