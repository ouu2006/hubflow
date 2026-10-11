// 感知层检测流访问面(Issue #54):感知演示服务的只读端点,不做任何业务计算。
// 数据由 work/perception/tools/dump_monitor_data.py 离线导出(样本视频 → MindSpore YOLO
// 检测 + ByteTrack 跟踪),经 work/perception/server.py 出接口;vite 把独立前缀
// /perception-api 代理并重写到服务端 /api/perception(见 vite.config.ts,避开 traffic mock)。
// 检测框/轨迹是一期接口面新增形状,非契约 v2.0 字段;
// meta/health 响应带 is_simulated=true 信封(detections/frames 为原始载荷不含信封),
// 页面显著标注"样本视频回放 · 演示数据(模拟)"。

export interface PerceptionStreamMeta {
  stream_id: string
  source_file: string
  note: string
  fps: number
  width: number
  height: number
  total_frames: number
  duration_s: number | null
  conf_threshold: number
  iou_threshold: number
  model: string
  backend: string
  class_names: Record<string, string>
  class_counts: Record<string, number>
  track_total: number
  generated_at: string
}

// det 元素:[x1, y1, x2, y2, class_id, conf, track_id],前四项为归一化坐标(0~1)
export type Detection = [number, number, number, number, number, number, number]

export interface DetectionFrame {
  i: number
  det: Detection[]
}

export interface PerceptionDetections {
  fps: number
  width: number
  height: number
  total_frames: number
  // track_id → 首次出现帧(前端据此累计轨迹与类别计数)
  first_seen: Record<string, { frame: number; class: number; conf: number }>
  frames: DetectionFrame[]
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`)
  const body = (await res.json()) as T & { is_simulated?: boolean }
  return body
}

// GET /perception-api/streams → 全部检测通道 meta(服务端路径 /api/perception/streams)
export function getPerceptionStreams(): Promise<{ streams: PerceptionStreamMeta[] }> {
  return getJson('/perception-api/streams')
}

// GET /perception-api/streams/{sid}/detections → 逐帧检测框
export function getPerceptionDetections(streamId: string): Promise<PerceptionDetections> {
  return getJson(`/perception-api/streams/${encodeURIComponent(streamId)}/detections`)
}

// 第 n 帧 JPEG(1 起);直接作 <img>/Image src 使用
export function perceptionFrameUrl(streamId: string, frame1: number): string {
  return `/perception-api/streams/${encodeURIComponent(streamId)}/frames/${frame1}.jpg`
}
