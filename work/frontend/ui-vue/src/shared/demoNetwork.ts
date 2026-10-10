// 示例路网(非实测,仅 mock 演示用):真路网由 #36 netbuild.py → sumo/*.net.xml、
// #37 map_ingest.py → network.json 提供,二者落地后由本文件替换为站点包产物。
// 坐标框架与契约 vehicles 示例一致(经纬度,肇庆东站一带的占位几何,不代表真实站位)。

export interface DemoSegment {
  segment_id: string
  name: string
  kind: 'main' | 'ramp'
  /** [lon, lat] 折线,单位度 */
  coords: [number, number][]
}

export const DEMO_NETWORK = {
  note: '示例路网(非实测),仅联调演示;来源:#36/#37 站点包落地后替换',
  segments: [
    {
      segment_id: 'SEG-001',
      name: '北进站路',
      kind: 'main',
      coords: [
        [112.4296, 23.0654],
        [112.4301, 23.0641],
        [112.4305, 23.0632],
        [112.4309, 23.0626],
      ],
    },
    {
      segment_id: 'SEG-002',
      name: '出发层环道·东',
      kind: 'main',
      coords: [
        [112.4309, 23.0626],
        [112.4318, 23.0623],
        [112.4326, 23.0621],
        [112.4333, 23.0618],
      ],
    },
    {
      segment_id: 'SEG-003',
      name: '落客平台',
      kind: 'main',
      coords: [
        [112.4333, 23.0618],
        [112.4331, 23.0610],
        [112.4326, 23.0605],
      ],
    },
    {
      segment_id: 'SEG-004',
      name: '出发层环道·南',
      kind: 'main',
      coords: [
        [112.4326, 23.0605],
        [112.4318, 23.0602],
        [112.4310, 23.0601],
        [112.4303, 23.0603],
      ],
    },
    {
      segment_id: 'SEG-005',
      name: '南进站路',
      kind: 'main',
      coords: [
        [112.4293, 23.0582],
        [112.4297, 23.0591],
        [112.4303, 23.0603],
      ],
    },
    {
      segment_id: 'SEG-006',
      name: '北出站疏解路',
      kind: 'ramp',
      coords: [
        [112.4309, 23.0626],
        [112.4297, 23.0631],
        [112.4288, 23.0636],
      ],
    },
    {
      segment_id: 'SEG-007',
      name: '社会停车场联络线',
      kind: 'ramp',
      coords: [
        [112.4326, 23.0621],
        [112.4339, 23.0626],
        [112.4346, 23.0630],
      ],
    },
    {
      segment_id: 'SEG-008',
      name: '网约车蓄车场通道',
      kind: 'ramp',
      coords: [
        [112.4326, 23.0605],
        [112.4338, 23.0599],
        [112.4344, 23.0594],
      ],
    },
    {
      segment_id: 'SEG-009',
      name: '到达层通道',
      kind: 'main',
      coords: [
        [112.4310, 23.0601],
        [112.4312, 23.0612],
        [112.4309, 23.0622],
      ],
    },
    {
      segment_id: 'SEG-010',
      name: '西出站疏解路',
      kind: 'ramp',
      coords: [
        [112.4303, 23.0603],
        [112.4292, 23.0600],
        [112.4284, 23.0596],
      ],
    },
  ] as DemoSegment[],
}

const SEGMENT_MAP = new Map(DEMO_NETWORK.segments.map((s) => [s.segment_id, s]))

export function demoSegment(id: string): DemoSegment | undefined {
  return SEGMENT_MAP.get(id)
}

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
