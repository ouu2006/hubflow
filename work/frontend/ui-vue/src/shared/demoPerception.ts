// 感知画面演示数据(仅 /perception 页面壳用,Issue #54)。
// ⚠ 口径:检测框是纯前端演示叠加层,不是数据契约 v2.0 的字段(契约的感知产物是
//   segments.json 指标快照,见 docs/数据契约.md);真实检测流(视频 + 逐帧框)归二期。
//   类别名沿用上游 YOLO(COCO)车辆子集可读名,置信度为演示值,不代表任何实测。

export interface DemoDetection {
  /** COCO 类别可读名(演示) */
  label: 'car' | 'bus' | 'truck'
  /** 置信度(演示值) */
  conf: number
  /** 画面归一化坐标(0~1,左上原点);真实实现换算自像素框 */
  x: number
  y: number
  w: number
  h: number
}

export const DEMO_FRAME_NOTE = '示例画面(非实测)· 一期无视频流 · 真实检测画面归二期'

export const DEMO_DETECTIONS: DemoDetection[] = [
  { label: 'bus', conf: 0.87, x: 0.1, y: 0.4, w: 0.19, h: 0.27 },
  { label: 'car', conf: 0.91, x: 0.57, y: 0.55, w: 0.17, h: 0.14 },
  { label: 'truck', conf: 0.78, x: 0.42, y: 0.47, w: 0.1, h: 0.09 },
  { label: 'car', conf: 0.72, x: 0.53, y: 0.46, w: 0.06, h: 0.05 },
  { label: 'car', conf: 0.84, x: 0.77, y: 0.57, w: 0.15, h: 0.13 },
]
