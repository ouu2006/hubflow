// 摄像头 ↔ 路段（Issue IKLX5Y；2026-10-25 演示层 N 段 N 路落图）。
//
// 业主 2026-10-15 口径：
//   ① 大屏**新增摄像头位置**，点击直接跳到感知层对应摄像头的画面；
//   ② **只有摄像头监控下的路段才显示颜色（拥堵情况）**，其余只画灰色路网轮廓。
// 业主 2026-10-25 口径：**路段有多少摄像头，图上/台账/监控墙就有多少**——
//   N 段 = N 摄像头 = N 视频（演示）落到图钉：`cameraPins()` 返回站点包 `channels` 全量
//   （源台账 6 + 演示层 55 = Z 61 路；GZ 708 路），每段一路、一段最多 1 路。
//
// 单一真值来源 = **站点包的 `channels`**（两份生成物合并，生成器
// `work/perception/tools/gen_station_channels.py`）：`segment_id` 说它监控哪条路，
// `lon`/`lat` 说它画在哪（演示层取 camera-plan 每段 offset_m 落折线）。
// 摄像头数是**现算的**（`channels` 里命中该段的条数），不在包里另存一份数字——
// 存两份迟早对不上（一条通道改段，数字忘了改，图上就撒谎）。
//
// ⚠️ 口径纪律：
//   · `demo: true` = 演示布点（camera-plan 演示层），画面走 `reuseOf` 演示复用——
//     **不是**该摄像头自己的视频，也不是踏勘点位；
//   · 摄像头**没有自有视频源**（`hasVideo: false`）不等于"没有摄像头"，更不等于"数据可用"——
//     三件事在页面上要分开说（见 `views/perception/`）；
//   · 上色策略来自包（`colorPolicy`），默认 `'all'`（Z/GZ 现行：全段按等级上色）。

import { activePack } from '../station-packs/index'
import type { PackChannel, PackColorPolicy } from '../station-packs/types.ts'

/** 画在图上的摄像头（只有带了坐标的通道才上图画） */
export interface CameraPin {
  cid: string
  /** 与感知服务 stream_id 对齐；深链参数也用它（演示层 = CAM-Z-xxx / CAM-GZ-xxx） */
  source: string
  /** 摄像头编号：源台账 cam-xx / 演示层 CAM-*；浮牌与 title 优先显示 */
  camId?: string
  name: string
  segment_id: string
  lon: number
  lat: number
  /** 是否有自有视频源；`false` = 演示复用（有画面，取 reuseOf 公开样本视频）或留空窗 */
  hasVideo: boolean
  /** 演示层摄像头（camera-plan 演示层生成；非源台账登记） */
  demo: boolean
  /** 演示复用的样本视频 stream_id（road2 / track1） */
  reuseOf?: string
}

function hasCoords(c: PackChannel): c is PackChannel & { lon: number; lat: number } {
  return typeof c.lon === 'number' && typeof c.lat === 'number'
}

/** 与 SegmentCameraCard.reuseSourceOf / 感知 channels.ts 同式的确定性复用挑选 */
const REUSE_SOURCES = ['road2', 'track1'] as const
function reuseSourceOf(segmentId: string): string {
  let hash = 0
  for (const ch of segmentId) hash = (hash * 31 + (ch.codePointAt(0) ?? 0)) >>> 0
  return REUSE_SOURCES[hash % REUSE_SOURCES.length]!
}

/** 无自有视频源的摄像头按 segment_id 确定性复用 road2/track1（与感知页 / 路段卡同式） */
function reuseOfChannel(c: PackChannel): string | undefined {
  return c.reuseOf ?? (c.hasVideo === false ? reuseSourceOf(c.segment_id) : undefined)
}

/** 当前包的摄像头布点（按 `channels` 顺序；没坐标的不上图；2026-10-25 起为全量 N 段 N 路） */
export function cameraPins(): CameraPin[] {
  return activePack()
    .channels.filter(hasCoords)
    .map((c) => ({
      cid: c.cid,
      source: c.source,
      camId: c.cam_id,
      name: c.name,
      segment_id: c.segment_id,
      lon: c.lon,
      lat: c.lat,
      hasVideo: c.hasVideo !== false,
      demo: c.demo === true,
      reuseOf: reuseOfChannel(c),
    }))
}

/** 路段 → 监控它的摄像头（可能多条） */
export function camerasBySegment(): Map<string, CameraPin[]> {
  const out = new Map<string, CameraPin[]>()
  for (const p of cameraPins()) {
    const list = out.get(p.segment_id)
    if (list) list.push(p)
    else out.set(p.segment_id, [p])
  }
  return out
}

/**
 * 某段源台账登记的摄像头（2026-10-25 起 = 全量通道；每段一路、一段最多 1 路）。
 * ⚠️ 2026-10-25 口径（业主）：**N 段 = N 摄像头 = N 视频（演示）落页面**——
 * 每段都有 1 路摄像头（源台账或演示层）；`demo: true` 的画面走 `reuseOf` 演示复用。
 */
export function camerasOfSegment(segmentId: string): PackChannel[] {
  return activePack().channels.filter((channel) => channel.segment_id === segmentId)
}

/** 路段摄像头数（= 该段在 channels 里命中的条数；现行包每段 1 路） */
export function cameraCountOf(segmentId: string): number {
  return activePack().channels.filter((c) => c.segment_id === segmentId).length
}

/**
 * 一期演示口径的摄像头总数：**N 段 = N 摄像头 = N 视频（mock 复用）**。
 * 返回当前站点包的路段数（Z=61 / GZ=433）；大屏/感知页用它标注"演示摄像头 N 路"，
 * 与源台账（`channels` 条数，仅初始映射）分开说，不拿源台账当一期总数。
 */
export function demoCameraCount(): number {
  return activePack().segments.length
}

/** 当前包的上色策略（不写 = `'all'`，既有行为） */
export function packColorPolicy(): PackColorPolicy {
  return activePack().colorPolicy ?? 'all'
}

/**
 * 该段是否在"只摄像头段上色"的范围内。
 * 策略为 `'all'` 时恒 true（不改变既有包的画法）。
 */
export function isCameraCovered(segmentId: string): boolean {
  if (packColorPolicy() !== 'camera-covered') return true
  return cameraCountOf(segmentId) > 0
}

/** 深链地址：大屏点摄像头 → 感知层该通道（`?source=` 与感知服务 stream_id 同值） */
export function perceptionHref(source: string): string {
  return `#/perception?source=${encodeURIComponent(source)}`
}
