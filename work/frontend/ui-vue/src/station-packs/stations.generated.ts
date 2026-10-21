// ⚠️ 本文件由脚本 `work/frontend/tools/gen_station_registry.py` 生成，**勿手改**。
//
// 内容 = 站点登记表 `work/twin/site-ranges.json` 的**前端只读副本**（Issue IKPFVN）：
// 全国地图的站点 pin、切站镜头的目标取景、顶栏切换器都读这一份，不再各自拼
// `packItems()`。加一个站 = 改登记表 + 加一个站点包 + 重跑脚本，**页面与引擎代码不动**。
//
// 字段口径：
//   · `key`         站点包键（= 登记表 `station_pack_key`，与 `PACKS` 的键一一对应）
//   · `name`        站名（登记表 `site_name`，页面展示用）
//   · `lon` / `lat` 站区锚点（登记表 `anchor_lonlat`；WGS-84，与 OSM 底图同坐标系，无需转换）
//   · `range_m`     站区范围（米，脚本推定 / 人工圈定，**不是官方划定**，页面只展示）
//   · `segment_count` 站区路网段数（登记表 `seg_target`）
//   · `pack`        对应的前端站点包模块路径（相对 `src/station-packs/`）
//
// ⚠️ 经纬度是**站区锚点**，不是站房轮廓；页面不得把它说成"实测/测绘"坐标。


/** 全国站表的一行（只读；字段含义见文件头） */
export interface StationEntry {
  key: string
  name: string
  lon: number
  lat: number
  range_m: number | null
  segment_count: number | null
  pack: string
}

/** 已接入车站（顺序 = 登记表顺序；全国地图 pin、镜头目标、切换器共用这一份） */
export const STATIONS: StationEntry[] = [
  {
    key: 'Z',
    name: '肇庆东站',
    lon: 112.6581162,
    lat: 23.2173959,
    range_m: 500,
    segment_count: 61,
    pack: './stationZ.ts',
  },
  {
    key: 'GZ',
    name: '广州南站',
    lon: 113.269,
    lat: 22.989,
    range_m: 1000,
    segment_count: 708,
    pack: './stationGZ.ts',
  },
]
