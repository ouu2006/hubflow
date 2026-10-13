// traffic 大屏 mock(仅 M1,Issue #52):端点与 SSE 事件名暂沿 work/assembly/README.md 第二节
// 的历史清单——2026-10-11 架构裁定后接口面待按前端页面重新规划,原实现基准 PR #51 骨架已收回,
// 字段名对照 docs/数据契约.md v2.0。口径铁律:
//   ① 所有数据 is_simulated=true,示例数据、非实测;
//   ② 只读快照、不算业务——数值是站点包给的预置基线加抖动,不是任何模型的输出;
//   ③ SSE 只新增事件名 traffic_snapshot,不改既有事件名;
//   ④ 「数据不可用」的演示路段由**站点包**指定(`pack.segmentBases[].stale`),这里不再写死 id。
//
// 2026-10-12(站点包层):本文件的站点相关内容(路段基线 / 合成车 / 断面 / 告警 / 双源覆盖 /
// 推荐骨架 / 站点元信息)全部改为**从当前站点包读**(`src/station-packs/`)。换站只换包,
// 本文件不出现任何"某个站才有的"常量——手册 §8.4 的判定标准。

import type { MockReq, MockRes } from './util.ts'
import { json, readJson, rid } from './util.ts'
import { SseWriter } from './sse-writer.ts'
import { activePack, activePackKey } from '../station-packs/index.ts'
import type { PackAlertBase, PackVehicleBase } from '../station-packs/types.ts'
import {
  DEMO_NETWORK,
  demoSegment,
  isOsmNetwork,
  networkAttribution,
  networkSourceLabel,
  pointAtOffset,
  segmentLengthM,
} from '../shared/demoNetwork.ts'
import { APP_TABS, DEMO_BADGE } from '../shared/nav.ts'
import { LEVEL_THRESHOLDS, THRESHOLD_CHANGELOG } from '../shared/demoDecision.ts'
import {
  TRAFFIC_SNAPSHOT_EVENT,
  type AlertsSnapshot,
  type AssimilationRecordV2,
  type AssimilationSnapshotFull,
  type CiHistory,
  type CongestionLevel,
  type DispatchInput,
  type DispatchReceipt,
  type FactorApplied,
  type FactorTarget,
  type HeatMatrix,
  type ManualFactorInput,
  type ManualFactorResult,
  type PredictResponse,
  type RecommendResult,
  type ScenarioInput,
  type ScenarioResult,
  type SegmentRecord,
  type SegmentSourceDelta,
  type SegmentSourcePair,
  type SegmentsSnapshot,
  type ThresholdSnapshot,
  type TimeSession,
  type TrafficAlert,
  type TrafficContext,
  type TrafficMeta,
  type TrafficNetwork,
  type TrafficOverview,
  type TrafficSnapshotPing,
  type VehicleRecord,
  type VehiclesSnapshot,
  type WeatherCondition,
  type WritebackInput,
  type WritebackReceipt,
  type WritebackResult,
} from '../shared/traffic.ts'

// ---------- 预置基线(契约 v2.0 形状;x = q_vph / c_vph) ----------
// 数值全部来自**当前站点包**(`src/station-packs/`),本文件不自带任何路段 id 与数值 ——
// "换一个站只新增 / 替换配置文件,不改引擎代码"(手册 §8.4)在管理端这一侧的落地。
// `stale` 由包声明:那条恒为数据陈旧(data_age_s > 120s)的演示灰档路段(TC-11 展示侧)。

interface SegmentBase {
  base: Omit<SegmentRecord, 'is_simulated'>
  /** 陈旧路段每轮继续累加数据年龄;正常路段限制在窗口内 */
  stale: boolean
}

const LEVEL_NAME: Record<number, string> = { 1: '畅通', 2: '缓行', 3: '拥堵', 4: '严重拥堵' }

function segmentBases(): SegmentBase[] {
  return activePack().segmentBases.map((b) => {
    // derive 是包侧的来源说明(FCD 折算 / 预置演示值),备查用,不进契约快照字段
    const { stale, derive, ...rest } = b
    void derive
    // level_name 不写在包里(包里只有 level):文案由 level 现算,免得包与文案两处各写一份再对不上
    return { stale, base: { ...rest, level_name: LEVEL_NAME[rest.level] } }
  })
}

// ---------- 孪生车辆(仅一期演示,二期 vehicles 端点下线) ----------
// 合成车基线同样取自站点包:包声明本站接不接孪生桥接服务,接不上时才用这一份。

function vehicleBases(): PackVehicleBase[] {
  return activePack().vehicleBases
}


// ---------- 注入因素(人工置位 + 环境上下文;mock 内存态) ----------
//
// 两个口子,一条重算路径:
//   · **人工置位**(Issue #59,手册 §:2222):只有 F07 / F08 / F11(事故 / 管制 / 大型活动),
//     由 `POST /api/traffic/factors` 逐路段置位,存 `manualFactors`;
//   · **环境上下文**(Issue #77):F01 天气 / F02 昼夜 / F03 列车到发 / F10 时段日历,
//     由「当前环境状态」(`scenarioState` + 站点包声明)折算,`POST /api/traffic/scenario` 只改状态。
//
// 状态门控(**默认态不碰站点包基线**,实测踩过才这么写):
//   · **未注入**(`scenarioState` 全空)→ `applyFactors` 只叠人工置位,站点包基线**逐位不动**
//     —— 包 A 的 SEG-003 / SEG-007 各自烘了一条 F01 大雨 ×0.75,`c_vph` 也已按它折算过,
//     默认态再去乘一遍会把整张基线推高一档(`x` 0.54→0.71、level 2→3),QA 基线全漂。
//     此时 `context.derived_factors` 只是**环境观测**(站点包声明的那套天气),页面必须分开标注。
//   · **已注入** → 先把包里烘入的环境因素**反算剔除**(÷倍率),再按当前环境状态乘一遍:
//     把天气切成"晴"时 SEG-003 的折减也跟着解除,同一因素绝不乘两次。

interface ManualFactor {
  segment_id: string
  factor_id: string
  name: string
  /** 作用目标口径与契约 FactorTarget 一致(c / v_f / demand / lanes / confidence) */
  target: FactorTarget
  multiplier: number
  until: string
}

const manualFactors: ManualFactor[] = []

/** 环境因素编号:剔除 / 重放只认这四个号 */
const ENV_FACTOR_IDS = new Set(['F01', 'F02', 'F03', 'F10'])

/** 该因素的作用方向(剔除时反向除回去) */
function factorAxis(target: FactorTarget): 'q' | 'c' | 'confidence' {
  if (target === 'demand') return 'q'
  if (target === 'confidence') return 'confidence'
  return 'c' // c / lanes / v_f 都折算到分母口径
}

function applyFactors(base: Omit<SegmentRecord, 'is_simulated'>): Omit<SegmentRecord, 'is_simulated'> {
  const injected = contextInjected()
  const mine = manualFactors.filter((f) => f.segment_id === base.segment_id)
  if (!injected && mine.length === 0) return base // 默认态:站点包基线逐位不动

  let q = base.q_vph ?? 0
  let c = base.c_vph ?? 0
  let conf = base.confidence ?? 0
  let keptFactors: FactorApplied[] = [...(base.factors_applied ?? [])]
  if (injected) {
    // ① 剔除包里烘入的环境因素(反算回未折减基线;非环境因素如 F06 违停保持原样)
    keptFactors = []
    for (const f of base.factors_applied ?? []) {
      if (!ENV_FACTOR_IDS.has(f.factor_id)) {
        keptFactors.push(f)
        continue
      }
      const axis = factorAxis(f.target)
      if (axis === 'q') q /= f.multiplier
      else if (axis === 'c') c /= f.multiplier
      else conf /= f.multiplier
    }
  }
  // ② 当前环境状态折算出的因素(注入态才有)+ ③ 人工置位(逐路段)
  const env = injected ? derivedFactors(new Date()) : []
  const applied = [...env, ...mine]
  for (const f of applied) {
    const axis = factorAxis(f.target)
    if (axis === 'q') q *= f.multiplier
    else if (axis === 'c') c *= f.multiplier
    else conf *= f.multiplier
  }
  const x2 = q / Math.max(1, c)
  const xLevel: CongestionLevel = x2 >= 0.9 ? 4 : x2 >= 0.7 ? 3 : x2 >= 0.5 ? 2 : 1
  const level = Math.max(base.level, xLevel) as CongestionLevel
  const baseTrig = base.triggered_by ?? []
  const triggered = xLevel > base.level && !baseTrig.includes('x') ? [...baseTrig, 'x'] : baseTrig
  const scale = base.x && base.x > 0 ? x2 / base.x : 1
  return {
    ...base,
    q_vph: Math.round(q),
    c_vph: Math.round(c),
    x: round(x2, 2),
    ci: round(Math.min(100, (base.ci ?? 0) * scale), 1),
    level,
    level_name: LEVEL_NAME[level],
    triggered_by: triggered,
    confidence: round(clamp(conf, 0, 1), 2),
    factors_applied: [...keptFactors, ...applied.map((f) => ({ ...f }))],
  }
}

// 数据同化的完整实现见下方 buildAssimilationFull()(带断面 role / 编号 / 计数)。

// ---------- 快照构造(tick 驱动抖动;数值是演示基线,不是模型输出) ----------

let tick = 0

function jitter(value: number, pct: number): number {
  return value * (1 + (Math.random() * 2 - 1) * pct)
}

function round(value: number, digits: number): number {
  const f = 10 ** digits
  return Math.round(value * f) / f
}

// 本地时区 ISO8601(契约示例带 +08:00 偏移,不用 UTC 的 Z)
function localIso(d: Date): string {
  const off = -d.getTimezoneOffset()
  const sign = off >= 0 ? '+' : '-'
  const pad = (n: number): string => String(Math.abs(n)).padStart(2, '0')
  const t = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  const date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  return `${date}T${t}${sign}${pad(Math.floor(Math.abs(off) / 60))}:${pad(Math.abs(off) % 60)}`
}

/**
 * 站点包里的预置因素 `until` 是**写死的日期**(如 `2026-10-11T23:30:00+08:00`)。
 * 演示跑到别的日子,它就变成了"早已过期却仍列在当前生效因素里"的自相矛盾。
 * 这里把日期部分归一到快照当天(该时刻已过则顺延一天),**只改日期、保留包里的时分**——
 * 于是"至 23:30"在任何一天演示都成立,数值与语义仍全部来自站点包。
 */
function normalizeUntil(until: string, now: Date): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?/.exec(until)
  if (!m) return until
  const [, , , , hh, mm, ss] = m
  const at = new Date(now.getFullYear(), now.getMonth(), now.getDate(), Number(hh), Number(mm), Number(ss ?? '0'))
  if (at.getTime() <= now.getTime()) at.setDate(at.getDate() + 1) // 当天该时刻已过 → 顺延到明天
  return localIso(at)
}

function buildSegmentsSnapshot(): SegmentsSnapshot {
  tick += 1
  const now = new Date()
  const segments: SegmentRecord[] = segmentBases().map(({ base, stale }) => {
    const src = applyFactors(base) // 注入因素(人工置位 + 场景注入)先生效,再走抖动
    const q_vph = Math.round(jitter(src.q_vph ?? 0, 0.04))
    const v_kmh = round(jitter(src.v_kmh ?? 0, 0.03), 1)
    const c_vph = src.c_vph ?? 0
    const ageBase = src.data_age_s ?? 0
    return {
      ...src,
      q_vph,
      v_kmh,
      k_vpk: round(jitter(src.k_vpk ?? 0, 0.03), 1),
      L_q_m: Math.round(jitter(src.L_q_m ?? 0, 0.06)),
      x: round(q_vph / Math.max(1, c_vph), 2),
      ci: round(jitter(src.ci ?? 0, 0.02), 1),
      data_age_s: stale ? ageBase + (tick % 30) * 2 : Math.min(ageBase + (tick % 6) * 2, 110),
      // 因素生效截止时间归一到演示当天(人工置位那批本来就是相对时间,归一后不变)
      factors_applied: (src.factors_applied ?? []).map((f) => ({ ...f, until: normalizeUntil(f.until, now) })),
      is_simulated: true,
    }
  })
  return { ts: localIso(new Date()), window_sec: 900, is_simulated: true, segments }
}

function buildVehiclesSnapshot(): VehiclesSnapshot {
  const vehicles: VehicleRecord[] = []
  for (const v of vehicleBases()) {
    const seg = demoSegment(v.segment_id)
    if (!seg) continue // 示例路网缺该路段(换路网时 id 未对齐)就不画这辆车
    const len = segmentLengthM(seg.coords)
    // 2 秒一帧:按各自速度前进,到段尾回卷(演示观感,非仿真输出)
    const offset = (v.offset_m + v.speed_mps * 2 * tick) % Math.max(50, len)
    const [lon, lat] = pointAtOffset(seg.coords, offset)
    vehicles.push({
      vehicle_id: v.vehicle_id,
      driver_type: v.driver_type,
      segment_id: v.segment_id,
      offset_m: Math.round(offset),
      lon: round(lon, 6),
      lat: round(lat, 6),
      state: v.state,
      guided: v.guided,
      is_demo_bound: v.is_demo_bound === true,
    })
  }
  return { ts: localIso(new Date()), is_simulated: true, vehicles }
}

// ---------- 孪生车辆真值接入(#61 twin_preview) ----------
// 桥接服务(work/frontend/tools/twin_preview/server.py,:8102)在跑时,vehicles 优先用
// SUMO TraCI 真值;不可用回落上方合成车基线。缓存 5 s + 在飞去重,2 s 轮询不会打满桥接。
//
// 开关与地址由**站点包**决定(`pack.bridge`):包说关就一个请求都不发。二站(自建示意路网)
// 必须关 —— twin_preview 跑的是肇庆东站的 OSM 切片,开它会把别站的车辆坐标画到本站图上。

const VEHICLE_STATES: readonly VehicleRecord['state'][] = ['行驶', '排队', '落客服务', '候客', '违停', '已离开']

let twinCache: { at: number; vehicles: VehicleRecord[] } | null = null
let twinInflight: Promise<VehicleRecord[] | null> | null = null

function toVehicleRecords(raw: unknown): VehicleRecord[] | null {
  if (!raw || typeof raw !== 'object') return null
  const env = raw as { is_simulated?: unknown; vehicles?: unknown }
  if (env.is_simulated !== true || !Array.isArray(env.vehicles)) return null
  const out: VehicleRecord[] = []
  for (const item of env.vehicles) {
    if (!item || typeof item !== 'object') return null
    const v = item as Record<string, unknown>
    if (
      typeof v.vehicle_id !== 'string' ||
      typeof v.segment_id !== 'string' ||
      typeof v.offset_m !== 'number' ||
      typeof v.lon !== 'number' ||
      typeof v.lat !== 'number' ||
      !VEHICLE_STATES.includes(v.state as VehicleRecord['state'])
    ) {
      return null // 形状不对整包拒绝,宁可用合成车也不画脏数据
    }
    out.push({
      vehicle_id: v.vehicle_id,
      driver_type: v.driver_type === 'D2' ? 'D2' : 'D1',
      segment_id: v.segment_id,
      offset_m: Math.round(v.offset_m),
      lon: v.lon,
      lat: v.lat,
      state: v.state as VehicleRecord['state'],
      guided: v.guided === true,
      is_demo_bound: v.is_demo_bound === true,
    })
  }
  return out
}

/** 桥接地址:站点包给默认值,`VITE_TWIN_API_BASE` 可临时改端口(与 vite 的 /twin-api 代理同源) */
function twinBridgeBase(): string {
  return process.env.VITE_TWIN_API_BASE || activePack().bridge.base
}

async function fetchTwinVehicles(): Promise<VehicleRecord[] | null> {
  const bridge = activePack().bridge
  // 包说本站不接桥接 → 一个请求都不发(二站正是这种:桥接跑的是别站的 OSM 切片)
  if (!bridge.enabled) return null
  const base = twinBridgeBase()
  if (!base) return null
  const now = Date.now()
  if (twinCache && now - twinCache.at < 5000) return twinCache.vehicles
  if (!twinInflight) {
    twinInflight = (async (): Promise<VehicleRecord[] | null> => {
      try {
        const res = await fetch(`${base}/api/twin/vehicles`, { signal: AbortSignal.timeout(700) })
        if (!res.ok) throw new Error(`twin bridge http ${res.status}`)
        const records = toVehicleRecords(await res.json())
        if (records && records.length > 0) twinCache = { at: Date.now(), vehicles: records }
        return records
      } catch {
        return null
      } finally {
        twinInflight = null
      }
    })()
  }
  return twinInflight
}

async function buildVehiclesSnapshotWithTwin(): Promise<VehiclesSnapshot> {
  const twin = await fetchTwinVehicles()
  // 桥接可达就信它的结果,包括空列表(仿真刚起步 genuinely 0 车)——
  // 此时回落合成车反而会造成"假车混进真仿真"的口径问题;只有不可达才回落
  if (twin) return { ts: localIso(new Date()), is_simulated: true, vehicles: twin }
  return buildVehiclesSnapshot()
}

// ---------- 推荐快照(静态演示:引擎写入 routes.json 后由接口层端出,这里按站点包骨架假造) ----------

function buildRecommend(): RecommendResult {
  const r = activePack().recommend
  return {
    request_id: rid('REQ'),
    session_id: rid('S'),
    driver_type: 'D1',
    parking_mode: 'S1',
    location: {
      segment_id: r.location_segment_id,
      offset_m: r.location_offset_m,
      match_confidence: 1.0,
      source: 'twin',
    },
    arrival_route: {
      path_id: 'P-2',
      segments: r.arrival_segments,
      eta_min: r.arrival_eta_min,
      dropoff_point: r.arrival_dropoff_point,
      walk_min: r.arrival_walk_min,
    },
    departure_route: { path_id: 'P-2-D', segments: r.departure_segments, eta_min: r.departure_eta_min },
    pickup_route: null,
    // 契约:备选 ≥2 条(包给的是演示骨架;引擎 routes.json 就绪后由接口层端出真结果)
    alternatives: r.alternatives.map((a) => ({
      path_id: a.path_id,
      eta_min: a.eta_min,
      reason: a.note,
      segments: a.segments,
    })),
    reservation: {
      slots_reserved: 9,
      lease_expire_s: 90,
      harm_check: { max_eta_increase_s: 12, max_slot_x: 0.81, passed: true },
    },
    why: r.why,
    is_simulated: true,
  }
}


// =====================================================================================
// 四页重做(Issue #78)新增端点实现
// 与既有端点同口径:只读快照 / 不做业务计算(数值为演示基线 + 抖动,不是模型输出);
// 每个响应带 is_simulated=true 信封;状态类端点(下发 / 回写)在 mock 内存态里流转,
// 供演示反复操作(刷新复位),后端实现时须落库并留痕。
// =====================================================================================

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v))
}

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

/** 'HH:mm:ss' */
function clockOf(d: Date): string {
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`
}

/** 'YYYY-MM-DD HH:mm:ss'(首次观测时间等留痕字段用) */
function stampOf(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${clockOf(d)}`
}

function nameOfSegment(id: string): string {
  return demoSegment(id)?.name ?? id
}

/** 演示基线与抖动共用的陈旧判据(与 shared/traffic.ts 的 STALE_AFTER_S = 120 对齐) */
function isStaleRec(seg: SegmentRecord): boolean {
  return (seg.data_age_s ?? 0) > 120
}

// ---------- 站点 / 数据源元信息 ----------

function buildMeta(): TrafficMeta {
  return {
    ts: localIso(new Date()),
    is_simulated: true,
    station: { ...activePack().station },
    sources: [
      { key: 'video', name: '视频链路' },
      { key: 'twin', name: '孪生链路' },
    ],
    demo_badge: DEMO_BADGE,
    tabs: APP_TABS.map((t) => ({ key: t.key, name: t.name, route: t.route })),
  }
}

// ---------- 全网 KPI(态势总览) ----------

const LEVEL_ORDER: CongestionLevel[] = [1, 2, 3, 4]
let prevAvgSpeed: number | null = null

function buildOverview(): TrafficOverview {
  const snap = buildSegmentsSnapshot()
  const segments = snap.segments
  const usable = segments.filter((s) => !isStaleRec(s))

  // 全网均速 = 按流量加权的平均车速(窗口均值口径;陈旧路段不参与,避免把"没数据"算成"很畅通")
  const qSum = usable.reduce((acc, s) => acc + (s.q_vph ?? 0), 0)
  const avg = qSum > 0 ? usable.reduce((acc, s) => acc + (s.v_kmh ?? 0) * (s.q_vph ?? 0), 0) / qSum : 0
  const avgRounded = round(avg, 1)
  const delta = prevAvgSpeed === null ? 0 : round(avgRounded - prevAvgSpeed, 1)
  prevAvgSpeed = avgRounded

  // 最堵路段:先按 level 取最高档,同档取 x(饱和度)大者
  const worst = [...segments].sort((a, b) => b.level - a.level || (b.x ?? 0) - (a.x ?? 0))[0] ?? null

  // 站前在途车辆与采纳率:演示基线(车速/流量同源抖动口径,不是仿真输出)
  const vehiclesInbound = 128 + (tick % 7) - 3
  const guidedRate = 0.742
  const guided = Math.round(vehiclesInbound * guidedRate)

  const levelDist: TrafficOverview['level_distribution'] = [
    ...LEVEL_ORDER.map((lv) => ({
      level: lv as CongestionLevel | 0,
      name: LEVEL_NAME[lv] ?? String(lv),
      count: segments.filter((s) => !isStaleRec(s) && s.level === lv).length,
    })),
    { level: 0 as CongestionLevel | 0, name: '不可用', count: segments.filter((s) => isStaleRec(s)).length },
  ]

  return {
    ts: snap.ts,
    is_simulated: true,
    window_sec: snap.window_sec,
    avg_speed_kmh: avgRounded,
    avg_speed_delta_kmh: delta,
    worst_segment: worst
      ? { segment_id: worst.segment_id, name: nameOfSegment(worst.segment_id), level: worst.level, x: worst.x ?? 0 }
      : null,
    vehicles_inbound: vehiclesInbound,
    vehicles_guided: guided,
    guided_rate: round(guided / Math.max(1, vehiclesInbound), 4),
    active_factors: segments.flatMap((s) => s.factors_applied ?? []).length,
    level_distribution: levelDist,
    segment_total: segments.length,
    unavailable_count: segments.filter((s) => isStaleRec(s)).length,
  }
}

// ---------- 路网拓扑(地图几何 + 断面 + 落客点 + 场区) ----------

// 断面目录 / 落客点 / 场区 / 站点全部由**站点包**给(几何从包里的占位坐标读):
// 边界断面允许回灌孪生,内部断面恒为 not allowed(手册门控口径);编号沿用设计稿的
// E-xx 展示编号(非契约字段),数量随包(一站 boundary 3 / internal 1,二站 boundary 5 / internal 2)。

function buildNetwork(): TrafficNetwork {
  const pack = activePack()
  const osm = isOsmNetwork()
  return {
    ts: localIso(new Date()),
    is_simulated: true,
    origin: osm ? 'osm' : 'demo',
    note: networkSourceLabel(),
    // 署名是站点包声明的展示义务(如 OSM 的 ODbL):包没声明就带 undefined,不署名
    attribution: networkAttribution(),
    segments: DEMO_NETWORK.segments.map((s) => ({
      segment_id: s.segment_id,
      name: s.name,
      kind: s.kind,
      coords: s.coords,
    })),
    sections: pack.sections.map((s) => ({
      point_id: s.point_id,
      segment_id: s.segment_id,
      name: s.name,
      role: s.role,
      offset: s.offset,
    })),
    dropoffs: pack.dropoffs.map((d) => ({ ...d })),
    zones: pack.zones.map((z) => ({ ...z })),
    stations: pack.stations.map((s) => ({ ...s })),
  }
}

// ---------- 同一路段双数据源并排(TC-19) ----------

// 一期有视频链路覆盖的路段由**站点包**声明;一站那份的 SEG-004 追加理由保留备查:
// 视频感知页的通道台账把样本视频 C-05 track1 映射到 SEG-004,该路段指标确实由视频链路产出,
// 故并排时 video 槽位必须可用。
// 取值函数而不是常量:本模块在 vite 配置里就被 import,那时包键还没注入(见 station-packs/index.ts)。
function videoCovered(): Set<string> {
  return new Set(activePack().videoCovered)
}


/** 由孪生记录派生视频记录:视频侧偏差略大(演示差值:饱和度 +0.07 / 车速 −2.6 / 排队 +42 / 消散 +0.6) */
function deriveVideoFromTwin(base: SegmentRecord): SegmentRecord {
  return {
    ...base,
    source: 'video',
    q_vph: Math.round((base.q_vph ?? 0) * 1.09),
    c_vph: base.c_vph,
    x: round(Math.min(1.4, (base.x ?? 0) * 1.083), 2),
    v_kmh: round(Math.max(0, (base.v_kmh ?? 0) - 2.6), 1),
    k_vpk: round((base.k_vpk ?? 0) * 1.06, 1),
    L_q_m: Math.round((base.L_q_m ?? 0) + 42),
    T_d_min: round((base.T_d_min ?? 0) + 0.6, 1),
    ci: round(clamp((base.ci ?? 0) * 1.05 + 2, 0, 100), 1),
    confidence: round(clamp((base.confidence ?? 0.8) - 0.04, 0, 1), 2),
  }
}

/** 由视频记录派生孪生记录(视频侧已更差时的反向派生) */
function deriveTwinFromVideo(base: SegmentRecord): SegmentRecord {
  return {
    ...base,
    source: 'twin',
    q_vph: Math.round((base.q_vph ?? 0) / 1.09),
    x: round(Math.max(0, (base.x ?? 0) / 1.083), 2),
    v_kmh: round((base.v_kmh ?? 0) + 2.6, 1),
    L_q_m: Math.max(0, Math.round((base.L_q_m ?? 0) - 42)),
    T_d_min: round(Math.max(0, (base.T_d_min ?? 0) - 0.6), 1),
    ci: round(clamp(((base.ci ?? 0) - 2) / 1.05, 0, 100), 1),
    confidence: round(clamp((base.confidence ?? 0.8) + 0.04, 0, 1), 2),
  }
}

function buildSegmentSources(segmentId: string): SegmentSourcePair | null {
  const snap = buildSegmentsSnapshot()
  const base = snap.segments.find((s) => s.segment_id === segmentId)
  if (!base) return null
  // 哪一侧是"实测基线":预置基线的 source 字段即该路段的真实来源
  const twinIsBase = base.source === 'twin'
  const twin = twinIsBase ? base : deriveTwinFromVideo(base)
  let video: SegmentRecord | null = null
  if (videoCovered().has(segmentId)) video = twinIsBase ? deriveVideoFromTwin(base) : base

  const pick = (r: SegmentRecord | null, k: keyof SegmentRecord): number | null =>
    r && typeof r[k] === 'number' ? (r[k] as number) : null
  const rows: [string, string, string, keyof SegmentRecord][] = [
    ['x', '饱和度 x', '', 'x'],
    ['v_kmh', '车速 km/h', 'km/h', 'v_kmh'],
    ['L_q_m', '排队长度 m', 'm', 'L_q_m'],
    ['T_d_min', '排队消散 min', 'min', 'T_d_min'],
    ['ci', '拥挤指数 CI', '', 'ci'],
  ]
  const deltas: SegmentSourceDelta[] = rows.map(([key, label, unit, field]) => {
    const v = pick(video, field)
    const t = pick(twin, field)
    return { key, label, unit, video: v, twin: t, delta: v !== null && t !== null ? round(v - t, 2) : null }
  })

  return {
    segment_id: segmentId,
    ts: snap.ts,
    is_simulated: true,
    slots: [
      { source: 'video', record: video, available: video !== null },
      { source: 'twin', record: twin, available: true },
    ],
    deltas,
  }
}

// ---------- 告警(四态,内存态流转) ----------

/** 告警基线的形状就是站点包里的那条(ago_min = 首次观测 = 快照时间往前推几分钟) */
type AlertBase = PackAlertBase

// 预置告警由**站点包**给(告警编号、路段、等级、四态条数都随站):待认领 2 / 处置中 1 /
// 已闭环 3 / 误报 1,与 page2「关联告警 2 条未闭环」、page3「待认领 7 条·未闭环 3」的口径自洽:
// 未闭环 = 待认领 + 处置中。
function alertBases(): PackAlertBase[] {
  return activePack().alerts
}

interface AlertRuntime {
  status?: TrafficAlert['status']
  channels?: string[]
  dispatch_at?: string
  /** 最近一次下发的分流比例(%)——与回执同源,供刷新后从 /alerts 还原下发留痕 */
  dispatch_ratio_pct?: number
  writeback?: TrafficAlert['writeback']
}

const alertRuntime = new Map<string, AlertRuntime>()

/** 结果四选一的唯一取值集(手册 §11.2);mock 侧校验用,前端展示枚举同源 */
const WRITEBACK_RESULTS: readonly WritebackResult[] = ['已消除', '已缓解', '未改善', '误报']

function isTerminal(status: TrafficAlert['status']): boolean {
  return status === '已闭环' || status === '误报'
}

/**
 * 复位到初始演示态:清运行态后重放预置下发留痕(供 POST /traffic/alerts/reset 调用)。
 * 预置留痕也来自站点包(那条「处置中」的告警 = 已下发过:渠道 / 比例 / 时间齐备,
 * 演示可直接走回写,TC-07)。
 */
function resetAlertRuntime(): void {
  alertRuntime.clear()
  firstSeenCache.clear()
  runtimeSeededFor = activePackKey()
  const now = Date.now()
  for (const [id, s] of Object.entries(activePack().seedDispatch)) {
    alertRuntime.set(id, {
      channels: [s.channel],
      dispatch_at: stampOf(new Date(now - s.dispatch_ago_min * 60_000)),
      dispatch_ratio_pct: s.ratio_pct,
    })
  }
}

// 运行态是**按包**建的:包键变了(换站)就重建一次,免得把一站的下发 / 回写留痕带到二站。
// 惰性播种而不是模块加载时播种 —— 本模块在 vite 配置里被 import,那时包键还没注入。
let runtimeSeededFor = ''
function ensureAlertRuntime(): void {
  if (runtimeSeededFor !== activePackKey()) resetAlertRuntime()
}

/** 首次观测时间只在首次出快照时算一次,此后各快照沿用同一值(审计时间不得随刷新漂移) */
const firstSeenCache = new Map<string, string>()

function firstSeenOf(a: AlertBase, now: number): string {
  const hit = firstSeenCache.get(a.alert_id)
  if (hit) return hit
  const stamp = stampOf(new Date(now - a.ago_min * 60_000))
  firstSeenCache.set(a.alert_id, stamp)
  return stamp
}

function buildAlerts(): AlertsSnapshot {
  ensureAlertRuntime()
  const now = Date.now()
  const alerts: TrafficAlert[] = alertBases().map((a) => {
    const rt = alertRuntime.get(a.alert_id) ?? {}
    return {
      alert_id: a.alert_id,
      segment_id: a.segment_id,
      segment_name: nameOfSegment(a.segment_id),
      level: a.level,
      triggered_by: a.triggered_by,
      first_seen: firstSeenOf(a, now),
      status: rt.status ?? a.status,
      factor_ids: a.factor_ids,
      channels: rt.channels,
      dispatch_at: rt.dispatch_at,
      dispatch_ratio_pct: rt.dispatch_ratio_pct,
      writeback: rt.writeback,
    }
  })
  return { ts: localIso(new Date()), is_simulated: true, alerts }
}

// ---------- 预测(一期 L0,不报精度数字) ----------

/** 演示预测档:15 / 30 / 60 分钟相对当前 CI 的变化(设计稿口径 −3.4 / −11.0 / −20.8) */
const PREDICT_PROFILE: { h: 15 | 30 | 60; delta: number }[] = [
  { h: 15, delta: -3.4 },
  { h: 30, delta: -11.0 },
  { h: 60, delta: -20.8 },
]

/** CI → 演示档位(仅供 pred 的等级展示;判级一律以四项指标为准,见 CI 硬口径) */
function demoLevelFromCi(ci: number): CongestionLevel {
  if (ci >= 85) return 4
  if (ci >= 65) return 3
  if (ci >= 40) return 2
  return 1
}

function buildPredict(segmentId: string, only?: number): PredictResponse | null {
  const rec = buildSegmentsSnapshot().segments.find((s) => s.segment_id === segmentId)
  if (!rec) return null
  const baseCi = rec.ci ?? 0
  // ?h=15|30|60 只回该档;未给或给的是别的值就回全档(调用方按需取)
  const profile = only === 15 || only === 30 || only === 60 ? PREDICT_PROFILE.filter((p) => p.h === only) : PREDICT_PROFILE
  const points = profile.map(({ h, delta }) => {
    const ci = round(clamp(baseCi + delta, 0, 100), 1)
    const level = demoLevelFromCi(ci)
    return { h, ci, delta_ci: round(ci - baseCi, 1), level, level_name: LEVEL_NAME[level] ?? String(level) }
  })
  return { segment_id: segmentId, ts: localIso(new Date()), is_simulated: true, model: 'L0', points }
}

// ---------- 阈值与 CI 权重(只读演示;真实来源 stations/thresholds.json) ----------

function buildThresholds(): ThresholdSnapshot {
  return {
    ts: localIso(new Date()),
    is_simulated: true,
    // CI 四项加权构成(设计稿口径 0.40 / 0.25 / 0.25 / 0.10,合计 1)
    ci_weights: [
      { key: 'x', label: '饱和度 x', weight: 0.4 },
      { key: 'v', label: '速度比 v/v_f', weight: 0.25 },
      { key: 'k', label: '排队比 L_q', weight: 0.25 },
      { key: 'T_d', label: '消散 T_d', weight: 0.1 },
    ],
    rows: LEVEL_THRESHOLDS.map((r) => ({ metric: r.metric, unit: r.unit, bands: r.bands })),
    changelog: THRESHOLD_CHANGELOG.map((c) => ({ ...c })),
  }
}

// ---------- 热力矩阵 / CI 走势 ----------

/**
 * `buckets` = 窗口桶数,`bucketSec` = 每桶秒数 —— 两个参数各司其职。
 * 原先只收桶数、且把秒数当桶数读(`?bucket=60` 会被夹到 24 列),页面标「最近 12 个快照」
 * 却画 24 列;改为按秒数铺桶间距后再夹上限,标注与实际才对得上。
 */
function buildHeatMatrix(buckets: number, bucketSec: number): HeatMatrix {
  const count = Math.min(24, Math.max(4, buckets))
  const stepMs = Math.max(1, bucketSec) * 1000
  const snap = buildSegmentsSnapshot()
  const now = Date.now()
  const labels = Array.from({ length: count }, (_, i) => clockOf(new Date(now - (count - 1 - i) * stepMs)))
  const rows = snap.segments.map((s) => {
    const available = !isStaleRec(s) && typeof s.ci === 'number'
    const vals: (number | null)[] = labels.map((_, i) => {
      if (!available) return null // 数据不可用 → 灰档,绝不用 0 冒充
      const wave = Math.sin((i / Math.max(1, count - 1)) * Math.PI * 1.6)
      return round(clamp((s.ci ?? 0) + wave * 14 - 8, 0, 100), 1)
    })
    return { segment_id: s.segment_id, name: nameOfSegment(s.segment_id), buckets: vals }
  })
  return { ts: snap.ts, is_simulated: true, bucket_sec: Math.max(1, Math.round(bucketSec)), buckets: count, labels, rows }
}

function buildCiHistory(segmentId: string, points: number): CiHistory | null {
  const rec = buildSegmentsSnapshot().segments.find((s) => s.segment_id === segmentId)
  if (!rec) return null
  const count = Math.min(48, Math.max(4, points))
  const base = rec.ci ?? 0
  const now = Date.now()
  const series = Array.from({ length: count }, (_, i) => {
    const t = i / Math.max(1, count - 1)
    const drift = (t - 0.5) * 10 // 近期缓慢上升的演示趋势
    const ci = round(clamp(base + drift + Math.sin(i * 0.9) * 4, 0, 100), 1)
    return { ts: clockOf(new Date(now - (count - 1 - i) * 5 * 60_000)), ci, level: demoLevelFromCi(ci) }
  })
  const values = series.map((p) => p.ci)
  return { segment_id: segmentId, is_simulated: true, points: series, min: Math.min(...values), max: Math.max(...values) }
}

// ---------- 数据同化(扩展:断面 role / 编号 / 计数) ----------

// 断面清单与每条断面的回灌状态来自**站点包**:边界断面允许回灌,内部断面恒为
// assimilating=false(不是"门控中",是**制度上不允许**,手册门控口径 + TC-20 第②项)。
// 门控阈值也由包给(一站 0.6 / 二站 0.75),不再写死,免得出现"0.62 < 0.6 却报门控"的自相矛盾。

function buildAssimilationFull(): AssimilationSnapshotFull {
  const pack = activePack()
  const now = localIso(new Date())
  const nowStamp = stampOf(new Date())
  const records: AssimilationRecordV2[] = pack.assimilation.map((a) => ({
    point_code: a.point_id,
    point_id: a.point_id,
    name: a.name,
    segment_id: a.segment_id,
    role: a.role,
    enabled: a.enabled,
    flow_dev_pct: a.flow_dev_pct,
    speed_dev_pct: a.speed_dev_pct,
    confidence: a.confidence,
    gate_reason: a.gate_reason,
    gate_detail: a.gate_detail,
    reason: a.reason,
    last_apply_at: a.enabled ? nowStamp : null,
  }))

  return {
    ts: now,
    is_simulated: true,
    gate: { ...pack.assimilationGate },
    counts: {
      boundary: records.filter((r) => r.role === 'boundary').length,
      internal: records.filter((r) => r.role === 'internal').length,
    },
    records,
  }
}


// =====================================================================================
// 环境上下文 + 场景注入(Issue #77 三页收敛)
//
// ⚠️ 口径铁律:
//   ① **天气 / 时段全部是编造的演示值**——真实气象与列车数据拿不到,页面与文档一律标
//      「演示数据(模拟)」,**不得称实测**;字段口径对齐手册第 19 章因素登记表。
//   ② **场景注入 ≠ 人工置位**:人工置位口子只有 F07 / F08 / F11(手册 §:2222);
//      本段的 F01 / F02 / F03 / F10 属**环境上下文**注入,端点分开、文案分开。
//   ③ 只影响演示基线(mock 内存态),**不触碰契约字段**。
// =====================================================================================

/** 天气 → 通行能力折减(F01 一期手填口径,手册 §:2276【demo 假设值 / 待标定】) */
const WEATHER_MULTIPLIER: Record<WeatherCondition, number> = {
  晴: 1.0,
  多云: 1.0,
  小雨: 0.9,
  大雨: 0.75,
  大雾: 0.7,
  台风: 0.6,
}

/** 天气 → 能见度 / 降水 / 湿度 / 风(展示口径演示值;只用于上下文面板,不参与判级) */
const WEATHER_PROFILE: Record<WeatherCondition, { visibility_km: number; precip_mm: number; humidity_pct: number; wind: string }> = {
  晴: { visibility_km: 20, precip_mm: 0, humidity_pct: 45, wind: '微风 1 级' },
  多云: { visibility_km: 15, precip_mm: 0, humidity_pct: 62, wind: '偏东风 2 级' },
  小雨: { visibility_km: 6.5, precip_mm: 1.2, humidity_pct: 86, wind: '东南风 3 级' },
  大雨: { visibility_km: 2.5, precip_mm: 12.5, humidity_pct: 94, wind: '东南风 5 级' },
  大雾: { visibility_km: 0.4, precip_mm: 0.2, humidity_pct: 97, wind: '静风' },
  台风: { visibility_km: 1.2, precip_mm: 38, humidity_pct: 96, wind: '旋转风 10 级' },
}

/** 时段 → 需求倍率(F10 演示值【待标定】) */
const SESSION_DEMAND_MULT: Record<TimeSession, number> = {
  早高峰: 1.2,
  平峰: 1.0,
  晚高峰: 1.15,
  夜间: 0.6,
}

const SESSION_ORDER: TimeSession[] = ['早高峰', '平峰', '晚高峰', '夜间']

/** 快照时钟 → 时段类型(展示口径划分;演示数据,不是真实客流统计) */
function sessionOfClock(hour: number): TimeSession {
  if (hour >= 6 && hour < 9) return '早高峰'
  if (hour >= 9 && hour < 16) return '平峰'
  if (hour >= 16 && hour < 20) return '晚高峰'
  return '夜间'
}

/** 下一班列车(演示值:整点 + 37 分口径;真实来源 = T3 列车时刻表,一期手填) */
function nextTrainOf(d: Date): string {
  const n = new Date(d.getTime())
  n.setMinutes(37, 0, 0)
  if (n.getTime() <= d.getTime()) n.setHours(n.getHours() + 1)
  return clockOf(n)
}

/** 场景注入当前状态(内存态;`null` = 未注入,回落站点包默认天气 / 按快照时钟推时段) */
interface ScenarioState {
  weather: WeatherCondition | null
  session: TimeSession | null
  demand_mult: number | null
}
const scenarioState: ScenarioState = { weather: null, session: null, demand_mult: null }

function contextWeather(): WeatherCondition {
  return scenarioState.weather ?? activePack().context.weather.condition
}

/** 当前时段:注入优先,否则按快照时钟推(站点包只声明日历与天气,不声明"现在几点") */
function contextSession(now: Date): TimeSession {
  return scenarioState.session ?? sessionOfClock(now.getHours())
}

/** 环境状态是否被注入改过(展示口径:区分「站点包默认环境」与「演示注入环境」) */
function contextInjected(): boolean {
  return scenarioState.weather !== null || scenarioState.session !== null || scenarioState.demand_mult !== null
}

/**
 * 当前环境(天气 / 时段)折算出的因素(F01 / F02 / F03 / F10;手册第 19 章口径)。
 *
 * 口径(实测对齐过,别改错):
 *   ① **默认态就带 F01**——站点包声明的天气就是当下天气,折算出的因素立刻生效
 *      (包 A 声明大雨 ×0.75,与它基线里烘入的 F01 大雨逐位一致:applyFactors 先剔除再重放);
 *   ② **时段本身不产生因素**:只有显式注入的 `demand_mult` 才抬 / 降需求。否则凭空给全路网
 *      乘一个时段倍率,会把站点包预置基线整体推高一档(实测踩过);
 *   ③ **F03 与 F10 由同一个总倍率拆开、乘积等于总倍率**——`applyFactors` 对每条因素各自相乘,
 *      两条同 target 的因素会被**乘两次**(独立审查发现:1.15 会变成 1.3225)。所以这里按倍率
 *      平方根拆:两半相乘 = 总倍率,既不夸大注入效果,也让"列车到发"与"时段日历"两个驱动
 *      各自出现在 `factors_applied` 里(验收要看得见是哪两类因素在起作用)。
 */
function envFactors(
  now: Date,
  weather: WeatherCondition,
  session: TimeSession,
  demandMult: number | null,
): FactorApplied[] {
  const until = localIso(new Date(now.getTime() + 60 * 60 * 1000))
  const out: FactorApplied[] = []
  const wm = WEATHER_MULTIPLIER[weather]
  if (wm < 1) {
    // F01 天气:折减通行能力(手册 §:2276 第 ① 条)
    out.push({ factor_id: 'F01', name: `天气·${weather}`, target: 'c', multiplier: wm, until })
  }
  if (weather === '大雾' || session === '夜间') {
    // F02 昼夜 / 能见度:置信度下降(手册 §:2891),页面据此标注"不做强推荐"
    out.push({ factor_id: 'F02', name: '昼夜 / 能见度', target: 'confidence', multiplier: 0.8, until })
  }
  if (typeof demandMult === 'number' && demandMult > 1) {
    // F03 列车到发 + F10 时段日历:共同抬需求,拆成两半(平方根),乘积 = 总倍率(手册 §:2892 / §:2899)
    const total = Math.min(1.6, demandMult)
    const half = round(Math.sqrt(total), 3)
    out.push({ factor_id: 'F03', name: '列车到发·需求上浮', target: 'demand', multiplier: half, until })
    out.push({ factor_id: 'F10', name: `时段·${session}`, target: 'demand', multiplier: round(total / half, 3), until })
  } else if (typeof demandMult === 'number' && demandMult < 1) {
    out.push({ factor_id: 'F10', name: `时段·${session}`, target: 'demand', multiplier: round(Math.max(0.4, demandMult), 3), until })
  }
  return out
}

/** 当前环境的折算因素(生产路径入口) */
function derivedFactors(now: Date): FactorApplied[] {
  return envFactors(now, contextWeather(), contextSession(now), scenarioState.demand_mult)
}

/** 全路段「注入因素后」的判级 / 饱和度(未抖动口径;场景注入的前后对照用) */
function levelsAfterFactors(): Map<string, { level: CongestionLevel; x: number }> {
  const out = new Map<string, { level: CongestionLevel; x: number }>()
  for (const { base } of segmentBases()) {
    const a = applyFactors(base)
    out.set(a.segment_id, { level: a.level, x: a.x ?? 0 })
  }
  return out
}

function buildContext(): TrafficContext {
  const now = new Date()
  const pack = activePack()
  const weather = contextWeather()
  const session = contextSession(now)
  const profile = WEATHER_PROFILE[weather]
  const factors = derivedFactors(now)
  const wm = WEATHER_MULTIPLIER[weather]
  const summary =
    factors.length === 0
      ? `${weather} · ${session} · 无环境因素生效(基准)`
      : `${weather} · ${session} · 生效因素 ${factors.map((f) => f.factor_id).join(' / ')}${
          wm < 1 ? `,通行能力折减 ×${wm}` : ''
        }`
  return {
    ts: localIso(now),
    is_simulated: true,
    station_id: pack.station.station_id,
    weather: {
      condition: weather,
      temp_c: pack.context.weather.temp_c,
      humidity_pct: profile.humidity_pct,
      visibility_km: profile.visibility_km,
      precip_mm: profile.precip_mm,
      wind: profile.wind,
    },
    time: {
      clock: clockOf(now),
      session,
      calendar: pack.context.calendar,
      next_train: nextTrainOf(now),
    },
    derived_factors: factors,
    injected: contextInjected(),
    summary,
    source: `站点包 ${pack.key} · ${pack.context.next_train_note}`,
  }
}

/** 场景注入:改环境状态(天气 / 时段 / 需求倍率),返回注入前后判级对照 */
function applyScenario(body: ScenarioInput, before: Map<string, { level: CongestionLevel; x: number }>): ScenarioResult {
  const now = new Date()
  if (body.weather !== undefined && body.weather in WEATHER_MULTIPLIER) scenarioState.weather = body.weather
  if (body.session !== undefined && SESSION_ORDER.includes(body.session)) {
    scenarioState.session = body.session
    // 选了时段就按 F10 的时段倍率抬 / 降需求(显式给了 demand_mult 时以显式值为准)
    if (body.demand_mult === undefined) scenarioState.demand_mult = SESSION_DEMAND_MULT[body.session]
  }
  if (typeof body.demand_mult === 'number' && Number.isFinite(body.demand_mult)) {
    scenarioState.demand_mult = Math.min(2, Math.max(0.4, body.demand_mult))
  }
  const factors = derivedFactors(now)
  const target = body.segment_id ?? '*'
  const after = levelsAfterFactors()
  const segmentIds = segmentBases().map((s) => s.base.segment_id)
  const effects = segmentIds
    .filter((id) => target === '*' || id === target)
    .map((id) => ({
      segment_id: id,
      name: nameOfSegment(id),
      level_before: before.get(id)?.level ?? 1,
      level_after: after.get(id)?.level ?? 1,
      x_before: before.get(id)?.x ?? 0,
      x_after: after.get(id)?.x ?? 0,
    }))
  return {
    applied: true,
    ts: localIso(now),
    is_simulated: true,
    factors,
    segment_ids: target === '*' ? segmentIds : [target],
    effects,
    note: '场景注入为演示口径(模拟),与「人工置位」(F07 / F08 / F11)是两个口子;复位走 POST /api/traffic/scenario/reset',
  }
}

function resetScenario(): void {
  scenarioState.weather = null
  scenarioState.session = null
  scenarioState.demand_mult = null
}


// ---------- HTTP 处理(path 不含 /api 前缀,与 mock/index.ts 的 connect 挂载一致) ----------

export async function handleTraffic(path: string, method: string, req: MockReq, res: MockRes): Promise<boolean> {
  // 查询参数(Issue #78 的 ?segment_id= / ?points= / ?window= 等);path 已由调用方去尾斜杠
  const url = new URL(req.url ?? path, 'http://mock.local')
  let m = /^\/traffic\/segments$/.exec(path)
  if (m && method === 'GET') {
    json(res, 200, buildSegmentsSnapshot())
    return true
  }

  m = /^\/traffic\/segments\/([^/]+)$/.exec(path)
  if (m && method === 'GET') {
    const id = decodeURIComponent(m[1])
    const seg = buildSegmentsSnapshot().segments.find((s) => s.segment_id === id)
    if (!seg) {
      json(res, 404, { code: 'SEGMENT_NOT_FOUND', message: `路段不存在: ${id}` })
      return true
    }
    json(res, 200, seg)
    return true
  }

  if (path === '/traffic/vehicles' && method === 'GET') {
    json(res, 200, await buildVehiclesSnapshotWithTwin())
    return true
  }

  if (path === '/traffic/route/recommend' && method === 'POST') {
    await readJson(req) // 请求体形状见契约(session_id / location);mock 不校验,原样回推荐快照
    json(res, 200, buildRecommend())
    return true
  }

  // 决策工作台(Issue #59,接口面新增):同化状态 / 人工置位因素
  if (path === '/traffic/assimilation' && method === 'GET') {
    json(res, 200, buildAssimilationFull())
    return true
  }

  // 契约 L440 预留端点的 GET:当前生效因素清单(含预置演示因素与人工置位,
  // 从 segments 快照展平——POST 置位 / reset 复位后此处随动)。
  // Issue #78:支持 ?segment_id= 过滤(拥挤度热力页的"成因拆解"按路段取)。
  if (path === '/traffic/factors' && method === 'GET') {
    const only = url.searchParams.get('segment_id')
    const factors = buildSegmentsSnapshot()
      .segments.filter((s) => !only || s.segment_id === only)
      .flatMap((s) => (s.factors_applied ?? []).map((f) => ({ ...f, segment_id: s.segment_id })))
    json(res, 200, { ts: localIso(new Date()), is_simulated: true, factors })
    return true
  }

  // ---------- Issue #78 新增端点 ----------

  if (path === '/traffic/meta' && method === 'GET') {
    json(res, 200, buildMeta())
    return true
  }

  if (path === '/traffic/overview' && method === 'GET') {
    json(res, 200, buildOverview())
    return true
  }

  if (path === '/traffic/network' && method === 'GET') {
    json(res, 200, buildNetwork())
    return true
  }

  m = /^\/traffic\/segments\/([^/]+)\/sources$/.exec(path)
  if (m && method === 'GET') {
    const pair = buildSegmentSources(decodeURIComponent(m[1]))
    if (!pair) {
      json(res, 404, { code: 'SEGMENT_NOT_FOUND', message: `路段不存在: ${decodeURIComponent(m[1])}` })
      return true
    }
    json(res, 200, pair)
    return true
  }

  if (path === '/traffic/alerts' && method === 'GET') {
    json(res, 200, buildAlerts())
    return true
  }

  // 演示复位:清空下发 / 回写运行态并重放预置留痕(与 factors/reset 同口径;
  // 状态存在服务进程内存里,刷新页面不清,要清走这里)
  if (path === '/traffic/alerts/reset' && method === 'POST') {
    resetAlertRuntime()
    json(res, 200, { reset: true, is_simulated: true })
    return true
  }

  if (path === '/traffic/plan/dispatch' && method === 'POST') {
    const body = (await readJson(req)) as Partial<DispatchInput> | null
    if (
      !body ||
      !body.alert_id ||
      !body.channel ||
      typeof body.ratio_pct !== 'number' ||
      !Number.isFinite(body.ratio_pct)
    ) {
      json(res, 400, { code: 'DISPATCH_INVALID', message: '下发参数不完整(需 alert_id/channel/ratio_pct)' })
      return true
    }
    ensureAlertRuntime()
    const alertBase = alertBases().find((a) => a.alert_id === body.alert_id)
    if (!alertBase) {
      json(res, 404, { code: 'ALERT_NOT_FOUND', message: `告警不存在: ${body.alert_id}` })
      return true
    }
    if (body.segment_id && body.segment_id !== alertBase.segment_id) {
      json(res, 400, {
        code: 'ALERT_SEGMENT_MISMATCH',
        message: `路段不匹配: ${body.alert_id} 属于 ${alertBase.segment_id},收到 ${body.segment_id}`,
      })
      return true
    }
    if (body.ratio_pct <= 0 || body.ratio_pct > 100) {
      json(res, 400, { code: 'DISPATCH_INVALID', message: `分流比例须在 (0, 100]: ${body.ratio_pct}` })
      return true
    }
    const nowStatus = alertRuntime.get(body.alert_id)?.status ?? alertBase.status
    if (isTerminal(nowStatus)) {
      json(res, 409, { code: 'ALERT_TERMINAL', message: `终态告警不可再下发: ${body.alert_id}(${nowStatus})` })
      return true
    }
    const at = stampOf(new Date())
    const rt = alertRuntime.get(body.alert_id) ?? {}
    rt.status = '处置中'
    rt.channels = [body.channel]
    rt.dispatch_at = at
    rt.dispatch_ratio_pct = body.ratio_pct
    alertRuntime.set(body.alert_id, rt)
    const receipt: DispatchReceipt = {
      alert_id: body.alert_id,
      channel: body.channel,
      ratio_pct: body.ratio_pct,
      // 一期无真实下发通道:回执是演示态(页面已标「mock 侧」)
      receipt: `${body.channel}已确认`,
      at,
      is_simulated: true,
    }
    json(res, 200, receipt)
    return true
  }

  if (path === '/traffic/plan/ack' && method === 'POST') {
    const body = (await readJson(req)) as Partial<WritebackInput> | null
    if (!body || !body.alert_id || !body.operator || !body.action || !body.result) {
      json(res, 400, { code: 'ACK_INVALID', message: '回写参数不完整(需 alert_id/operator/action/result)' })
      return true
    }
    if (!WRITEBACK_RESULTS.includes(body.result)) {
      json(res, 400, {
        code: 'ACK_INVALID',
        message: `结果须为四选一(${WRITEBACK_RESULTS.join(' / ')}): ${body.result}`,
      })
      return true
    }
    ensureAlertRuntime()
    const alertBase = alertBases().find((a) => a.alert_id === body.alert_id)
    if (!alertBase) {
      json(res, 404, { code: 'ALERT_NOT_FOUND', message: `告警不存在: ${body.alert_id}` })
      return true
    }
    if (body.segment_id && body.segment_id !== alertBase.segment_id) {
      json(res, 400, {
        code: 'ALERT_SEGMENT_MISMATCH',
        message: `路段不匹配: ${body.alert_id} 属于 ${alertBase.segment_id},收到 ${body.segment_id}`,
      })
      return true
    }
    const rt = alertRuntime.get(body.alert_id) ?? {}
    const nowStatus = rt.status ?? alertBase.status
    if (isTerminal(nowStatus)) {
      json(res, 409, { code: 'ALERT_TERMINAL', message: `终态告警不可再回写: ${body.alert_id}(${nowStatus})` })
      return true
    }
    // 闭环顺序硬口径(TC-07):回写必须有下发回执在前,不能从「待认领 / 处置中未下发」直接跳终态
    if (!rt.dispatch_at || !rt.channels || rt.channels.length === 0) {
      json(res, 409, {
        code: 'ACK_NO_DISPATCH',
        message: `告警尚未下发(无派发回执),不可回写: ${body.alert_id}`,
      })
      return true
    }
    // 结果 → 状态流转(手册 §11.2):已消除 / 已缓解 → 已闭环;未改善 → 留在处置中;误报 → 误报
    const status: TrafficAlert['status'] =
      body.result === '误报' ? '误报' : body.result === '未改善' ? '处置中' : '已闭环'
    const at = stampOf(new Date())
    rt.status = status
    rt.writeback = { operator: body.operator, action: body.action, result: body.result, at }
    alertRuntime.set(body.alert_id, rt)
    const receipt: WritebackReceipt = {
      alert_id: body.alert_id,
      status,
      result: body.result,
      at,
      is_simulated: true,
    }
    json(res, 200, receipt)
    return true
  }

  if (path === '/traffic/predict' && method === 'GET') {
    const sid = url.searchParams.get('segment_id')
    if (!sid) {
      json(res, 400, { code: 'PREDICT_INVALID', message: '缺少 segment_id' })
      return true
    }
    const hRaw = url.searchParams.get('h')
    const h = hRaw === null ? undefined : Number(hRaw)
    if (h !== undefined && !Number.isFinite(h)) {
      json(res, 400, { code: 'PREDICT_INVALID', message: `h 须为数值(15 / 30 / 60): ${hRaw}` })
      return true
    }
    const pred = buildPredict(sid, h)
    if (!pred) {
      json(res, 404, { code: 'SEGMENT_NOT_FOUND', message: `路段不存在: ${sid}` })
      return true
    }
    json(res, 200, pred)
    return true
  }

  if (path === '/traffic/thresholds' && method === 'GET') {
    json(res, 200, buildThresholds())
    return true
  }

  if (path === '/traffic/heat-matrix' && method === 'GET') {
    // `window` = 窗口桶数,`bucket` = 每桶秒数;两者互不替用(此前 `bucket ?? window` 会把秒数当桶数)
    const bucketsRaw = Number(url.searchParams.get('window') ?? '12')
    const bucketSecRaw = Number(url.searchParams.get('bucket') ?? '60')
    json(
      res,
      200,
      buildHeatMatrix(
        Number.isFinite(bucketsRaw) ? bucketsRaw : 12,
        Number.isFinite(bucketSecRaw) && bucketSecRaw > 0 ? bucketSecRaw : 60,
      ),
    )
    return true
  }

  if (path === '/traffic/ci-history' && method === 'GET') {
    const sid = url.searchParams.get('segment_id')
    if (!sid) {
      json(res, 400, { code: 'CI_HISTORY_INVALID', message: '缺少 segment_id' })
      return true
    }
    const points = Number(url.searchParams.get('points') ?? '12')
    const hist = buildCiHistory(sid, Number.isFinite(points) ? points : 12)
    if (!hist) {
      json(res, 404, { code: 'SEGMENT_NOT_FOUND', message: `路段不存在: ${sid}` })
      return true
    }
    json(res, 200, hist)
    return true
  }

  if (path === '/traffic/factors' && method === 'POST') {
    const body = (await readJson(req)) as Partial<ManualFactorInput>
    const seg = segmentBases().find((s) => s.base.segment_id === body.segment_id)
    if (!seg || !body.factor_id || !body.target || typeof body.multiplier !== 'number') {
      json(res, 400, { code: 'FACTOR_INVALID', message: '置位参数不完整(需 segment_id/factor_id/target/multiplier)' })
      return true
    }
    const until = new Date(Date.now() + 60 * 60 * 1000) // 演示:置位 60 分钟后自动过期
    manualFactors.push({
      segment_id: seg.base.segment_id,
      factor_id: body.factor_id,
      name: body.name ?? body.factor_id,
      target: body.target,
      multiplier: body.multiplier,
      until: localIso(until),
    })
    const seg0 = applyFactors(seg.base)
    const result: ManualFactorResult = {
      applied: true,
      segment_id: seg0.segment_id,
      level: seg0.level,
      level_name: seg0.level_name ?? LEVEL_NAME[seg0.level],
      factors_applied: seg0.factors_applied ?? [],
      is_simulated: true,
    }
    json(res, 200, result)
    return true
  }

  if (path === '/traffic/factors/reset' && method === 'POST') {
    manualFactors.length = 0
    json(res, 200, { reset: true, is_simulated: true })
    return true
  }

  // ---- 环境上下文 + 场景注入(Issue #77) ----
  if (path === '/traffic/context' && method === 'GET') {
    json(res, 200, buildContext())
    return true
  }

  if (path === '/traffic/scenario' && method === 'POST') {
    const body = (await readJson(req)) as ScenarioInput
    if (body.segment_id && !segmentBases().some((s) => s.base.segment_id === body.segment_id)) {
      json(res, 400, { code: 'SEGMENT_NOT_FOUND', message: `路段不存在: ${body.segment_id}` })
      return true
    }
    // 注入前的判级必须在**改环境状态之前**取(否则 before 与 after 是同一个状态,差恒为 0)
    const before = levelsAfterFactors()
    json(res, 200, applyScenario(body ?? {}, before))
    return true
  }

  if (path === '/traffic/scenario/reset' && method === 'POST') {
    resetScenario()
    json(res, 200, { reset: true, is_simulated: true })
    return true
  }

  if (path === '/traffic/stream' && method === 'GET') {
    streamSnapshots(req, res)
    return true
  }

  return false
}

// SSE 假流:每 2 秒推一次 traffic_snapshot 轻量事件,页面收到后重新拉快照(只读快照口径)。
// 清理挂 res 'close'(响应侧:连接断开或流结束都触发),配一次性护栏防止重复清理。
function streamSnapshots(req: MockReq, res: MockRes): void {
  const sse = new SseWriter(res)
  sse.open()
  const send = (): void => {
    const ping: TrafficSnapshotPing = {
      ts: localIso(new Date()),
      is_simulated: true,
      note: '示例快照刷新事件(traffic mock)',
    }
    sse.send(TRAFFIC_SNAPSHOT_EVENT, ping)
  }
  send()
  const timer = setInterval(send, 2000)
  let cleaned = false
  const cleanup = (): void => {
    if (cleaned) return
    cleaned = true
    clearInterval(timer)
    sse.close()
  }
  res.on('close', cleanup)
  req.on('error', cleanup)
}
