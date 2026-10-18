// ⚠️ 本文件由 `work/perception/tools/gen_station_channels.py` 生成，**勿手改**。
// 唯一真值来源：`work/perception/mapping/camera-segments.json`（IKMDKY 三段映射登记表）。
// 页面（stationZ.ts）只 import 本文件；后端（work/perception/server.py）读同一份登记表。
// 改映射：先改登记表 JSON，再跑 `python work/perception/tools/gen_station_channels.py`。
// 行数 = 登记表 cameras 条数 N，动态（IKMS1T：0 ≤ N ≤ 路段数，默认每段最多 1 路），不写死 6。

import type { PackChannel } from './types.ts'

export const CAMERA_CHANNELS: PackChannel[] = [
  {
    cid: 'C-01',
    cam_id: 'cam-01',
    source: 'cam-01',
    name: '吉庆大道·西进口',
    segment_id: 'SZ-010',
    lon: 112.6548733,
    lat: 23.2151734,
    hasVideo: false,
  },
  {
    cid: 'C-02',
    cam_id: 'cam-02',
    source: 'road2',
    name: '吉庆大道·中段',
    segment_id: 'SZ-005',
    lon: 112.6573791,
    lat: 23.2139003,
    hasVideo: true,
  },
  {
    cid: 'C-03',
    cam_id: 'cam-03',
    source: 'cam-03',
    name: '场区出入口',
    segment_id: 'SZ-054',
    lon: 112.6570652,
    lat: 23.2140549,
    hasVideo: false,
  },
  {
    cid: 'C-04',
    cam_id: 'cam-04',
    source: 'cam-04',
    name: '停车场·站门口',
    segment_id: 'SZ-019',
    lon: 112.6577645,
    lat: 23.2156324,
    hasVideo: false,
  },
  {
    cid: 'C-05',
    cam_id: 'cam-05',
    source: 'track1',
    name: '停车场·北支',
    segment_id: 'SZ-024',
    lon: 112.6588897,
    lat: 23.2148643,
    hasVideo: true,
  },
  {
    cid: 'C-06',
    cam_id: 'cam-06',
    source: 'cam-06',
    name: '鼎湖大道·进场',
    segment_id: 'SZ-015',
    lon: 112.6535729,
    lat: 23.2150334,
    hasVideo: false,
  },
]
