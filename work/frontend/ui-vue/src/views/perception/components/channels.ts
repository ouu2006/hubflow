// 视频感知页重做(Issue #78)本地通道目录与显示口径辅助(仅本页使用)。
//
// ⚠️ 本文件只放「通道目录 / 枚举映射 / 纯函数」,**不写任何样本数值**:
//   分辨率 / 帧率 / 时长 / 帧数 / 轨迹数 / 类别计数一律从 /perception-api/streams 的 meta 取;
//   服务里没有的字段(越线计数 / 轨迹质量 SVR / 标定 RANGE-RMSE / 平均 Q)一律显示「—」,
//   绝不用前端推算值或设计稿示例值冒充。
//
// 2026-10-12(站点包层):**通道 ↔ 路段映射**从当前站点包读(`src/station-packs/`)——
// "这一路画面算到哪条路段上"取决于这个站有哪些路,属于包的内容。通道目录本身(cid、源文件名)
// 是公开样本视频的属性,与站点无关,留在这里。
// **IKMS1T(2026-10-18)去固定 6 路**:通道条数 N 随登记表动态(0 ≤ N ≤ 路段数,默认每段最多 1 路;
// 0 路合法),本文件不再假设"永远 6 路",页面按 `activePack().channels` 的长度渲染。
import type { Detection, PerceptionDetections, PerceptionStreamMeta } from '../../../api/perception'
import { activePack } from '../../../station-packs/index'
import { CLASS_COLORS, type VehicleClassKey } from '../../../shared/theme'

/** 通道目录(与设计稿 04 一致;`source` 与感知服务 stream_id 对齐) */
export interface ChannelDef {
  /** 展示编号 C-01 …（Z 包演示层接在源台账后续编至 C-61；GZ 包 C-01…C-708） */
  cid: string
  /** 源文件名(不含扩展名)= 感知服务 stream_id = 前端帧/检测端点入参 */
  source: string
  /** 摄像头编号：源台账 cam-xx / 演示层 CAM-Z-xxx·CAM-GZ-xxx；台账与监控墙标题行优先显示它 */
  camId?: string
  /** 中文路段名(设计稿展示口径) */
  name: string
  /** 映射路段(设计稿 04;回灌门控按它查 network.sections 与同化记录) */
  segmentId: string
  /**
   * 该通道当前是否**有视频源**(Issue IKLX5Y)。
   * `false` = 摄像头已布点、**视频留空窗**(业主 2026-10-15:视频样本先不弄)。
   * ⚠️ 与"`meta === null`(样本视频未导出)"是**两件事**:
   *   · 未接入视频源 = 本路还没接视频,将来接上就有;
   *   · 样本视频未导出 = 有这一段样本视频,只是服务端还没处理它。
   * 页面上必须分开说,否则"还没接"会被读成"处理失败"。
   */
  hasVideo: boolean
  /** 演示层摄像头（业主 2026-10-25：N 段 = N 摄像头 = N 视频落页面；`demo: true` 非源台账登记） */
  demo?: boolean
  /** 演示复用的样本视频 stream_id（road2/track1）；画面与检测框从它取，必须标「演示复用」 */
  reuseOf?: string
}

/**
 * 当前站点包的通道映射。
 * 取值函数而不是常量:本模块在 `import` 阶段就被求值,而包键是入口在挂载前注入的。
 * 2026-10-25 起 `channels` = 源台账生成物 + 演示层生成物合并（一段最多 1 路，源台账优先）。
 * 演示复用覆盖**全部无自有源摄像头**：演示层带 `reuseOf`；源台账未接源的 4 路（老口径
 * 「本期留空」）按同式 hash 现算 `reuseOf` —— 业主 2026-10-25「路段有多少摄像头，
 * 监控墙就要有多少画面」，与大屏路段卡（IKNAUI）对无源段的既有行为一致。
 */
export function channels(): ChannelDef[] {
  return activePack().channels.map((c) => {
    const hasVideo = c.hasVideo !== false
    return {
      cid: c.cid,
      source: c.source,
      camId: c.cam_id,
      name: c.name,
      segmentId: c.segment_id,
      hasVideo,
      demo: c.demo === true,
      reuseOf: c.reuseOf ?? (hasVideo ? undefined : reuseSourceOf(c.segment_id)),
    }
  })
}

/** 与大屏 SegmentCameraCard.reuseSourceOf 同式的确定性复用挑选（uint32 hash 二选一） */
const REUSE_SOURCES = ['road2', 'track1'] as const
function reuseSourceOf(segmentId: string): string {
  let hash = 0
  for (const ch of segmentId) hash = (hash * 31 + (ch.codePointAt(0) ?? 0)) >>> 0
  return REUSE_SOURCES[hash % REUSE_SOURCES.length]!
}

/**
 * 画面/检测取数用的 stream_id：自有视频源用 `source`；
 * 无自有源但有 `reuseOf`（演示层 / 源台账未接源）用复用流——画面与检测框都从它取。
 */
export function feedSourceOf(def: ChannelDef): string {
  return def.hasVideo ? def.source : (def.reuseOf ?? def.source)
}

/** 与复用挑选同式的确定性 hash（uint32；演示层相位偏移用，不是数据口径） */
export function hashOf(text: string): number {
  let h = 0
  for (const ch of text) h = (h * 31 + (ch.codePointAt(0) ?? 0)) >>> 0
  return h
}

/** 越线计数线位置(归一化画面高度;手册/设计稿口径 line_position = 0.62) */
export const COUNT_LINE_POS = 0.62

/**
 * 通道"画面从哪来"的五分口径(IKLX5Y 三分 → IKLX5Y 加一档四分 → 2026-10-25 演示层再加一档)。
 *
 * ⚠️ `reuse` 必须与"未导出"分开 —— 演示复用是**有画面**（取公开样本视频确定性复用，
 * 明确标「演示复用·非本站现场」）；「未导出」是自有源样本视频服务端还没处理，没有画面。
 */
export type ChannelFeed = 'ok' | 'reuse' | 'no-source' | 'unexported' | 'failed'

/** 五分的文字 + 样式类(全页同口径:台账 / 监控墙 / 详情 / 供给对照共用) */
export const FEED_TEXT: Record<ChannelFeed, { text: string; cls: string }> = {
  ok: { text: '已导出', cls: 'ok' },
  reuse: { text: '演示复用', cls: 'warn' },
  'no-source': { text: '未接入视频源', cls: 'out' },
  unexported: { text: '未导出', cls: 'out' },
  failed: { text: '检测读取失败', cls: 'err' },
}

/**
 * 判定顺序:自有源看服务端实际返回(未导出 / 读取失败 / 已导出);
 * 无自有源但有 `reuseOf` → 演示复用(有画面);无自有源也无复用(老包) → 未接入视频源。
 */
export function feedOf(c: ChannelState): ChannelFeed {
  if (!c.def.hasVideo) return c.def.reuseOf ? 'reuse' : 'no-source'
  if (c.meta === null) return 'unexported'
  if (c.detFailed) return 'failed'
  return 'ok'
}

/** 四分的文字(便捷取用) */
export function feedText(c: ChannelState): { text: string; cls: string } {
  return FEED_TEXT[feedOf(c)]
}

/** 通道 + 服务端实际返回的联合视图;meta 为 null = 该路样本视频未导出(未处理) */
export interface ChannelState {
  def: ChannelDef
  meta: PerceptionStreamMeta | null
  det: PerceptionDetections | null
  /** 逐帧检测框总数(真实数据累计);det 缺失为 null */
  detTotal: number | null
  /**
   * 该通道 detections 请求是否失败(meta 在、检测取不到)。
   * 硬口径:接口失败**不得**与"这一路样本本来就没检出目标"混同——
   * 失败要报「检测读取失败」,绝不静默成"本帧无检出"。
   */
  detFailed: boolean
}

/** 车型槽位短名(画面区/图例用,与 DESIGN 的四槽口径一致) */
export const CLASS_SHORT: Record<VehicleClassKey, string> = {
  car: 'car',
  van: 'van',
  bus: 'bus',
  truck: 'truck',
}

/** 图例全名(设计稿 04:car 私家车 / van 面包车 / bus 大巴 / truck 货车) */
export const CLASS_LABEL: Record<VehicleClassKey, string> = {
  car: 'car 私家车',
  van: 'van 面包车',
  bus: 'bus 大巴',
  truck: 'truck 货车',
}

export const CLASS_KEYS: VehicleClassKey[] = ['car', 'van', 'bus', 'truck']

/**
 * 类别 → 车型槽位(class_names 语义映射;行人等非车辆返回 null)。
 * 口径:小汽车=car / 货车=truck / 公交车=bus / 摩托车·自行车=van(设计稿四槽)。
 */
export function vehicleKeyOf(classId: number, className: string): VehicleClassKey | null {
  if (classId === 2 || className.includes('小汽车')) return 'car'
  if (classId === 7 || className.includes('货车')) return 'truck'
  if (classId === 5 || className.includes('公交车')) return 'bus'
  if (classId === 1 || classId === 3 || className.includes('摩托') || className.includes('自行车')) {
    return 'van'
  }
  return null
}

/** 检测框颜色:车辆类别取车型色;非车辆类别交中性灰(不借车型色,也不使用等级四级色) */
export function classColorOf(classId: number, className: string): string {
  const key = vehicleKeyOf(classId, className)
  return key ? CLASS_COLORS[key] : '#9E9E9E'
}

/** ≤ i 的最近检测帧(二分;与旧页同口径,回退 / 跳转 / 抽帧都稳) */
export function frameAt(det: PerceptionDetections | null, i: number): Detection[] | null {
  if (!det || det.frames.length === 0) return null
  const arr = det.frames
  let lo = 0
  let hi = arr.length - 1
  let ans = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    const el = arr[mid]
    if (el && el.i <= i) {
      ans = mid
      lo = mid + 1
    } else {
      hi = mid - 1
    }
  }
  if (ans < 0) return null
  return arr[ans]?.det ?? null
}

/** 当前帧按车型分组计数(只出四个车型槽;非车辆类别单独计) */
export function classCountsOf(
  dets: Detection[] | null,
  classNames: Record<string, string>,
): { key: VehicleClassKey; short: string; count: number }[] {
  const acc = new Map<VehicleClassKey, number>()
  if (dets) {
    for (const d of dets) {
      const cls = d[4] ?? 0
      const name = classNames[String(cls)] ?? `类${cls}`
      const key = vehicleKeyOf(cls, name)
      if (key) acc.set(key, (acc.get(key) ?? 0) + 1)
    }
  }
  return CLASS_KEYS.filter((k) => (acc.get(k) ?? 0) > 0).map((k) => ({
    key: k,
    short: CLASS_SHORT[k],
    count: acc.get(k) ?? 0,
  }))
}

/** 当前帧轨迹数(不重复 track_id) */
export function trackCountOf(dets: Detection[] | null): number {
  if (!dets) return 0
  const ids = new Set<number>()
  for (const d of dets) ids.add(d[6])
  return ids.size
}

/**
 * 累计轨迹按车型分组 —— 口径取自 detections.first_seen 的 class 字段(旧页成熟口径),
 * 不是把逐帧框数累加(那会把同一辆车的多帧重复计数)。
 */
export function cumClassCounts(
  det: PerceptionDetections | null,
  classNames: Record<string, string>,
): { byKey: Map<VehicleClassKey, number>; other: number; total: number } {
  const byKey = new Map<VehicleClassKey, number>()
  let other = 0
  let total = 0
  if (det) {
    for (const v of Object.values(det.first_seen)) {
      total += 1
      const name = classNames[String(v.class)] ?? `类${v.class}`
      const key = vehicleKeyOf(v.class, name)
      if (key) byKey.set(key, (byKey.get(key) ?? 0) + 1)
      else other += 1
    }
  }
  return { byKey, other, total }
}

/** 秒 → mm:ss(mm:ss 时长展示,不引入任何示例数值) */
export function fmtDur(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return '—'
  const s = Math.max(0, Math.round(seconds))
  const m = Math.floor(s / 60)
  return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

/** 分辨率 + 帧率 + 时长 + 轨迹/检测(全部来自 meta;该路未导出则统计列显示「—」) */
export function metaLine(meta: PerceptionStreamMeta | null, detTotal: number | null): string {
  if (!meta) return '—'
  const parts = [
    `${meta.width}×${meta.height}`,
    `${meta.fps} fps`,
    fmtDur(meta.duration_s),
    `轨迹 ${meta.track_total}`,
    `检测 ${detTotal === null ? '—' : detTotal}`,
  ]
  return parts.join(' · ')
}
