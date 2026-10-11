// traffic 态势大屏访问面(Issue #52):只读快照 + SSE,不做任何业务计算。
// 2026-10-11 架构裁定:harness 架构不复用,后端接口面待按前端页面重新规划
// (原实现基准 PR #51 骨架已收回,内容可在该 PR 页面回看;mock 端点暂沿 Issue #52 清单)。
// 一期 mock 演示:全部数据 is_simulated=true,页面显著标注"示例数据"。

import type {
  RecommendResult,
  SegmentRecord,
  SegmentsSnapshot,
  VehiclesSnapshot,
} from '../shared/traffic'
import { TRAFFIC_SNAPSHOT_EVENT, type TrafficSnapshotPing } from '../shared/traffic'
import { request } from './http'

// GET /api/traffic/segments → segments 快照(契约 v2.0)
export function getTrafficSegments(): Promise<SegmentsSnapshot> {
  return request<SegmentsSnapshot>('GET', '/api/traffic/segments')
}

// GET /api/traffic/segments/{id} → 单路段详情(含 factors_applied / pred),形状与列表元素一致
export function getTrafficSegment(segmentId: string): Promise<SegmentRecord> {
  return request<SegmentRecord>('GET', `/api/traffic/segments/${encodeURIComponent(segmentId)}`)
}

// GET /api/traffic/vehicles → 孪生车辆位置(仅一期演示用,二期端点下线)
export function getTrafficVehicles(): Promise<VehiclesSnapshot> {
  return request<VehiclesSnapshot>('GET', '/api/traffic/vehicles')
}

// POST /api/traffic/route/recommend → 推荐路线快照(引擎写入 routes.json,接口层只端出来)
export function postRouteRecommend(body: { session_id: string; location: { segment_id: string; offset_m: number } }): Promise<RecommendResult> {
  return request<RecommendResult>('POST', '/api/traffic/route/recommend', { body })
}

// GET /api/traffic/stream(SSE,事件 traffic_snapshot)→ 轻量刷新事件;页面收到后重新拉快照。
// EventSource 无法附带鉴权头;当前端点公开访问,鉴权方案随接口面重新规划一并定稿。
export function subscribeTrafficSnapshot(
  onPing: (ping: TrafficSnapshotPing) => void,
  onState?: (connected: boolean) => void,
): () => void {
  const es = new EventSource('/api/traffic/stream')
  es.onopen = () => onState?.(true)
  es.onerror = () => onState?.(false) // EventSource 会自动重连,状态只作展示
  es.addEventListener(TRAFFIC_SNAPSHOT_EVENT, (ev: MessageEvent) => {
    let payload: TrafficSnapshotPing = { ts: '', is_simulated: true }
    try {
      payload = JSON.parse(ev.data) as TrafficSnapshotPing
    } catch {
      /* 非 JSON 帧:按空载荷处理,只当刷新信号 */
    }
    onPing(payload)
  })
  return () => es.close()
}
