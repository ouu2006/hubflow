// 摄像头 ↔ 路段（Issue IKLX5Y）。
//
// 业主 2026-10-15 口径：
//   ① 大屏**新增摄像头位置**，点击直接跳到感知层对应摄像头的画面；
//   ② **只有摄像头监控下的路段才显示颜色（拥堵情况）**，其余只画灰色路网轮廓。
//
// 单一真值来源 = **站点包的 `channels`**：`segment_id` 说它监控哪条路，`lon`/`lat` 说它画在哪。
// 摄像头数是**现算的**（`channels` 里命中该段的条数），不在包里另存一份数字——
// 存两份迟早对不上（一条通道改段，数字忘了改，图上就撒谎）。
//
// ⚠️ 口径纪律：
//   · 摄像头**没有视频源**（`hasVideo: false`）不等于"没有摄像头"，更不等于"数据可用"——
//     三件事在页面上要分开说（见 `views/perception/`）；
//   · 上色策略来自包（`colorPolicy`），**默认 `'all'` 是既有行为**，本站才用 `'camera-covered'`
//     —— 当年是为了不让这一单的规则外溢到 A / B / Y 三个既有包（三者已随 IKM4KP / IKM4XX 删除）；
//     将来加站仍按"上色策略由包声明"这条办。

import { activePack } from '../station-packs/index.ts'
import type { PackChannel, PackColorPolicy } from '../station-packs/types.ts'

/** 画在图上的摄像头（只有带了坐标的通道才上图画） */
export interface CameraPin {
  cid: string
  /** 与感知服务 stream_id 对齐；深链参数也用它 */
  source: string
  name: string
  segment_id: string
  lon: number
  lat: number
  /** 是否有视频源；`false` = 留空窗（业主：视频样本先不弄） */
  hasVideo: boolean
}

function hasCoords(c: PackChannel): c is PackChannel & { lon: number; lat: number } {
  return typeof c.lon === 'number' && typeof c.lat === 'number'
}

/** 当前包的摄像头布点（按 `channels` 顺序；没坐标的不上图） */
export function cameraPins(): CameraPin[] {
  return activePack()
    .channels.filter(hasCoords)
    .map((c) => ({
      cid: c.cid,
      source: c.source,
      name: c.name,
      segment_id: c.segment_id,
      lon: c.lon,
      lat: c.lat,
      hasVideo: c.hasVideo !== false,
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
 * 某段登记的摄像头（全量：含未上图 / 无坐标项；动态 N，0 = 该段无摄像头）。
 * 大屏「关联摄像头」卡用：`hasVideo` 说有没有视频源，`source` 与感知服务 stream_id 同键。
 */
export function camerasOfSegment(segmentId: string): PackChannel[] {
  return activePack().channels.filter((channel) => channel.segment_id === segmentId)
}

/** 某段的摄像头数（0 = 该段没监控） */
export function cameraCountOf(segmentId: string): number {
  return activePack().channels.filter((c) => c.segment_id === segmentId).length
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
