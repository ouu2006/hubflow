// 大屏双色模式（Issue IKNB9G，业主 2026-10-18）：**纯车流量**配色（按 q_vph 分档）的单一配置源。
//
// 口径铁律：
//   ① 这里的配色**只用于展示**，不参与任何判级 / 拥堵结论（判级唯一实现是感知层 level.py；
//      接口层与前端都不重算 level）。流量版页面必须标注「纯车流量（演示识别）· 仅按 q 分档，
//      不代表拥堵结论」；**按 2026-10-18 口径（IKNB9I）**：6 路视频全 mock、**YOLO 仅为项目代号、
//      一期不实装模型**——不得宣称「真实 YOLO 识别 / 模型已实装」、不得写实测 / 实时 / 现场；
//   ② 分档阈值**集中在本文件**，页面 / 地图 / 图例 / 热力 / 列表全部从这里取，不散落魔法数；
//   ③ 缺 q（字段缺失 / 非数值）或数据陈旧（data_age_s > 阈值）→ 如实灰档，不硬填空值。
//
// 阈值依据（一期展示口径，待标定；不参与判级）：
//   · 本站 W1 演示数据 61 段 q_vph 分布：P50 = 120、P75 = 540、P90 = 780 辆/h（范围 60~1320）；
//   · 站区默认通行能力 c = 1600 辆/h（`stations/thresholds.json` 的 grading.defaults.c_vph）；
//   · 取 240 / 540 / 900 辆/h ≈ 0.15c / 0.34c / 0.56c 作四档边界：低 / 中低 / 中高 / 高流量；
//   · 颜色用**蓝阶**（深蓝=高流量），与拥堵等级色（绿/黄/橙/红）语义分离，一眼区分两个版本。
//   真实标定另开单；这里只是演示口径，页面与 README 都如实标注。

import { isStale, UNAVAILABLE, type SegmentRecord } from './traffic.ts'

/** 大屏颜色模式：congestion = 决策拥堵（level 四级）；flow = 纯车流量（q_vph 四档，仅展示） */
export type ColorMode = 'congestion' | 'flow'

export interface FlowBand {
  band: 1 | 2 | 3 | 4
  name: string
  /** 上界（辆/h，含）；null = 最高档无上界 */
  max_q_vph: number | null
  /** 档位图形色（地图 / 色块 / 图例） */
  color: string
  /** 深色底上的文字色（列表角标） */
  textColor: string
}

export const FLOW_BANDS: readonly FlowBand[] = [
  { band: 1, name: '低流量', max_q_vph: 240, color: '#D6E4FF', textColor: '#1D39C4' },
  { band: 2, name: '中低流量', max_q_vph: 540, color: '#85A5FF', textColor: '#10239E' },
  { band: 3, name: '中高流量', max_q_vph: 900, color: '#2F54EB', textColor: '#FFFFFF' },
  { band: 4, name: '高流量', max_q_vph: null, color: '#10239E', textColor: '#FFFFFF' },
]

/** 流量版页头/图例固定文案（业主口径；按 IKNB9I 口径写明 YOLO 仅为代号、不实装模型） */
export const FLOW_MODE_LABEL = '纯车流量（演示识别 · 一期 YOLO 仅为项目代号、不实装模型）'
export const FLOW_MODE_NOTE = '仅按 q 分档，不代表拥堵结论'
/** 两套色的语义分离说明（图例 / README 共用） */
export const FLOW_COLOR_NOTE =
  '流量色阶（蓝）与拥堵等级色（绿/黄/橙/红）语义不同：颜色只表示车流量大小，不表示拥堵等级'

/** 颜色模式持久化键（localStorage；`?color=flow|congestion` 深链可覆盖一次） */
export const COLOR_MODE_STORAGE_KEY = 'hubflow.dashboard.colorMode'
export const COLOR_MODE_QUERY_KEY = 'color'

export function parseColorMode(value: unknown): ColorMode | null {
  return value === 'flow' || value === 'congestion' ? value : null
}

export function readStoredColorMode(): ColorMode | null {
  try {
    return parseColorMode(localStorage.getItem(COLOR_MODE_STORAGE_KEY))
  } catch {
    return null
  }
}

export function storeColorMode(mode: ColorMode): void {
  try {
    localStorage.setItem(COLOR_MODE_STORAGE_KEY, mode)
  } catch {
    /* localStorage 不可用（隐私模式等）时只影响“刷新后记不记得”，不影响本次切换 */
  }
}

/** 该段是否有可展示的纯流量值（有 q 且不陈旧；陈旧按数据不可用处理，不硬填） */
export function flowAvailable(seg: SegmentRecord | null | undefined): boolean {
  if (!seg) return false
  const q = seg.q_vph
  return typeof q === 'number' && Number.isFinite(q) && q >= 0 && !isStale(seg)
}

/** q → 档位（含边界：q = 240 属第 1 档；null/非法值返回 null） */
export function flowBandOfQ(q: number | null | undefined): FlowBand | null {
  if (typeof q !== 'number' || !Number.isFinite(q) || q < 0) return null
  return FLOW_BANDS.find((band) => band.max_q_vph === null || q <= band.max_q_vph) ?? null
}

/** 路段 → 流量档位；缺 q / 陈旧 → null（页面按灰档展示） */
export function flowBandOf(seg: SegmentRecord | null | undefined): FlowBand | null {
  return flowAvailable(seg) ? flowBandOfQ(seg!.q_vph) : null
}

/** 路段 → 流量颜色；不可用 → UNAVAILABLE 灰（绝不落进拥堵等级色） */
export function flowColorOf(seg: SegmentRecord | null | undefined): string {
  return flowBandOf(seg)?.color ?? UNAVAILABLE.color
}

/** 档位区间文案（图例 / 分布卡用） */
export function flowRangeLabel(band: FlowBand): string {
  if (band.max_q_vph !== null) return `≤ ${band.max_q_vph} 辆/h`
  const prev = FLOW_BANDS[FLOW_BANDS.length - 2]?.max_q_vph
  return prev === undefined ? '> 最高档边界' : `> ${prev} 辆/h`
}

/** 流量版的“无数据”标签（与拥堵版「不可用」区分） */
export const FLOW_UNAVAILABLE_LABEL = '无流量数据'
