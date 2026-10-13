// 路网几何与底图口径 —— **不再自带数据**,一律从当前站点包取(`src/station-packs/`)。
//
// 为什么要改成这样:手册 §8.4 的判定标准是"**换一个站只新增 / 替换配置文件,不改引擎代码**"。
// 本文件此前把站名、几何、路段 id 全部写死,是"一份包";现在它退化成一个**只读门面**:
// 页面与 mock 继续按原来的函数名调用,换站时改的是包,不是这里。
//
// 坐标口径:包里的坐标是 `[lon, lat]` 度(契约形状);自建示意路网是**占位锚点**,
// 不做地理配准,图上任何一点都不是真实地点(见 `station-packs/stationB.ts` 头部说明)。
//
// ⚠️ 这里**故意不在模块初始化时读包**:模块在 `import` 阶段就被求值,而包键是入口
// (`main.ts` / vite 配置)在挂载前才注入的。所以几何统一走 `ensureInit()` 惰性构建 ——
// 谁先用到谁触发,触发时包键一定已经就位。

import { activePack } from '../station-packs/index.ts'
import type { PackSegment } from '../station-packs/types.ts'

export interface DemoSegment {
  segment_id: string
  name: string
  kind: 'main' | 'ramp'
  /** [lon, lat] 折线,单位度 */
  coords: [number, number][]
}

const state: { note: string; segments: DemoSegment[] } = { note: '', segments: [] }
const SEGMENT_MAP = new Map<string, DemoSegment>()
let inited = false

/** 深拷贝包里的路段:`applyNetworkOverride()` 会**原地**替换这份副本,包里的常量不能被改 */
function cloneSegments(src: PackSegment[]): DemoSegment[] {
  return src.map((s) => ({
    segment_id: s.segment_id,
    name: s.name,
    kind: s.kind,
    coords: s.coords.map((c) => [c[0], c[1]] as [number, number]),
  }))
}

function ensureInit(): void {
  if (inited) return
  inited = true
  const pack = activePack()
  state.note = pack.source.label
  state.segments = cloneSegments(pack.segments)
  SEGMENT_MAP.clear()
  for (const s of state.segments) SEGMENT_MAP.set(s.segment_id, s)
}

/** 当前包的路网(惰性初始化;`applyNetworkOverride()` 原地改的就是这里的 segments) */
export const DEMO_NETWORK = {
  get note(): string {
    ensureInit()
    return state.note
  },
  set note(v: string) {
    state.note = v
  },
  get segments(): DemoSegment[] {
    ensureInit()
    return state.segments
  },
}

export function demoSegment(id: string): DemoSegment | undefined {
  ensureInit()
  return SEGMENT_MAP.get(id)
}

// ---- 真路网覆盖(#61 twin_preview):入口在挂载前拉 /twin-api/network 原地替换,
// NetMap / 两个面板 / mock 的静态读取统一生效;桥接服务不可用则保持站点包路网不变。
// 二站(自建示意路网)关掉桥接(`pack.bridge.enabled === false`),入口不拉,也就不会覆盖。
const NETWORK_SOURCE = { twin: false }

export function applyNetworkOverride(segments: DemoSegment[], note: string): void {
  if (segments.length === 0) return
  ensureInit()
  state.segments.splice(0, state.segments.length, ...segments)
  state.note = note
  SEGMENT_MAP.clear()
  for (const s of state.segments) SEGMENT_MAP.set(s.segment_id, s)
  NETWORK_SOURCE.twin = true
}

/** 底图来源短文案(页面水印/页脚口径用):桥接覆盖过就是真路网,否则报包自己的口径 */
export function networkSourceLabel(): string {
  return NETWORK_SOURCE.twin ? 'OSM 真路网 · SUMO 仿真演示' : activePack().source.label
}

/** 当前底图是否为真 OSM 路网(桥接覆盖或包自己声明)——OSM 署名义务随之触发 */
export function isOsmNetwork(): boolean {
  return NETWORK_SOURCE.twin || activePack().source.osm
}

/** 底图署名(有则给,如 OSM 的 ODbL);站点包没声明就不署名 */
export function networkAttribution(): string | undefined {
  return NETWORK_SOURCE.twin ? OSM_ATTRIBUTION : activePack().source.attribution
}

/** OSM 署名(ODbL 要求;条款核实 §2.1:对外展示 OSM 数据须署名并给超链接) */
export const OSM_ATTRIBUTION = '地图数据 © OpenStreetMap 贡献者,依 ODbL 许可'
export const OSM_COPYRIGHT_URL = 'https://www.openstreetmap.org/copyright'

const LAT_M_PER_DEG = 111_320

function lonMPerDeg(lat: number): number {
  return LAT_M_PER_DEG * Math.cos((lat * Math.PI) / 180)
}

/** 折线累计长度(米,近似) */
export function segmentLengthM(coords: [number, number][]): number {
  let total = 0
  for (let i = 1; i < coords.length; i++) {
    const dLon = coords[i][0] - coords[i - 1][0]
    const dLat = coords[i][1] - coords[i - 1][1]
    const mx = dLon * lonMPerDeg(coords[i][1])
    const my = dLat * LAT_M_PER_DEG
    total += Math.hypot(mx, my)
  }
  return total
}

/** 路段内偏移(米)→ 经纬度;offset 超长时取终点 */
export function pointAtOffset(coords: [number, number][], offsetM: number): [number, number] {
  let remain = Math.max(0, offsetM)
  for (let i = 1; i < coords.length; i++) {
    const dLon = coords[i][0] - coords[i - 1][0]
    const dLat = coords[i][1] - coords[i - 1][1]
    const mx = dLon * lonMPerDeg(coords[i][1])
    const my = dLat * LAT_M_PER_DEG
    const len = Math.hypot(mx, my)
    if (len <= 0) continue
    if (remain <= len) {
      const t = remain / len
      return [coords[i - 1][0] + dLon * t, coords[i - 1][1] + dLat * t]
    }
    remain -= len
  }
  return coords[coords.length - 1]
}
