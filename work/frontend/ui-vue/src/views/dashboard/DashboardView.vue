<script setup lang="ts">
// 交通态势大屏(态势总览,Issue #52 · 分工表 §8 W1②/W2):
//   左栏 = 路段监测 + 线路方案;中央 = 路网四级染色 + 车辆动点 + 路线高亮;右栏 = 路段详情。
// 数据来源:mock 快照(契约 v2.0 形状,traffic.py 端点);SSE traffic_snapshot 收到即重新拉快照。
// 口径:一期全部 is_simulated=true 示例数据,不含视频画面;页面不出现"实时/实测"表述。
// 1920×1080 设计稿等比缩放(scale),适配投屏与窗口。
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  getTrafficSegments,
  getTrafficVehicles,
  postRouteRecommend,
  subscribeTrafficSnapshot,
} from '../../api/traffic'
import type { RecommendResult, RoutePath, SegmentRecord, VehicleRecord } from '../../shared/traffic'
import NetMap from './components/NetMap.vue'
import RoutePanel from './components/RoutePanel.vue'
import SegmentDetailPanel from './components/SegmentDetailPanel.vue'
import SegmentListPanel from './components/SegmentListPanel.vue'

const segments = ref<SegmentRecord[]>([])
const vehicles = ref<VehicleRecord[]>([])
const plan = ref<RecommendResult | null>(null)
const selectedId = ref<string | null>(null)
const activePathId = ref<string | null>(null)
const live = ref(false)
const snapshotTs = ref('')
const clock = ref('')

let unsubscribe: (() => void) | null = null
let clockTimer: number | undefined

async function refresh(): Promise<void> {
  // 只读快照:三个接口并行拉,哪个成功用哪个(联调期接口层可能只起一部分)
  const [seg, veh, rec] = await Promise.allSettled([
    getTrafficSegments(),
    getTrafficVehicles(),
    postRouteRecommend({ session_id: 'dashboard-demo', location: { segment_id: 'SEG-001', offset_m: 85 } }),
  ])
  if (seg.status === 'fulfilled') {
    segments.value = seg.value.segments
    snapshotTs.value = seg.value.ts
  }
  if (veh.status === 'fulfilled') vehicles.value = veh.value.vehicles
  if (rec.status === 'fulfilled') {
    const first = plan.value === null
    plan.value = rec.value
    if (first) activePathId.value = rec.value.arrival_route.path_id
  }
}

function tickClock(): void {
  const d = new Date()
  const pad = (n: number): string => String(n).padStart(2, '0')
  clock.value = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

onMounted(() => {
  tickClock()
  clockTimer = window.setInterval(tickClock, 1000)
  onResize()
  window.addEventListener('resize', onResize)
  void refresh()
  unsubscribe = subscribeTrafficSnapshot(
    () => {
      void refresh()
    },
    (connected) => {
      live.value = connected
    },
  )
})

onUnmounted(() => {
  unsubscribe?.()
  window.removeEventListener('resize', onResize)
  if (clockTimer !== undefined) window.clearInterval(clockTimer)
})

// ---- 选中与高亮 ----

const selected = computed<SegmentRecord | null>(
  () => segments.value.find((s) => s.segment_id === selectedId.value) ?? null,
)

const routeSegments = computed<string[]>(() => {
  const p = plan.value
  if (!p || !activePathId.value) return []
  const all: RoutePath[] = [p.arrival_route, ...p.alternatives]
  if (p.departure_route) all.push(p.departure_route)
  return all.find((r) => r.path_id === activePathId.value)?.segments ?? []
})

// ---- 1920×1080 等比缩放 ----

const scale = ref(1)

function onResize(): void {
  scale.value = Math.min(window.innerWidth / 1920, window.innerHeight / 1080)
}

const stageStyle = computed(() => ({
  transform: `translate(-50%, -50%) scale(${scale.value})`,
}))
</script>

<template>
  <div class="dash-viewport">
    <div class="dash-stage" :style="stageStyle">
      <header class="bar">
        <div class="bar-left">
          <span class="logo">◈</span>
          <span class="app-name">枢纽交通态势大屏</span>
          <span class="badge mock">MOCK</span>
        </div>
        <div class="bar-mid">
          <span class="scenario">演示场景 · 峰值(scenario_2)</span>
          <span class="badge sim">is_simulated = true · 示例数据</span>
        </div>
        <div class="bar-right">
          <span class="conn" :class="live ? 'up' : 'down'">
            <i class="dot" />
            {{ live ? '快照流已连接' : '快照流未连接' }}
          </span>
          <span class="clock">{{ clock }}</span>
        </div>
      </header>

      <div class="cols">
        <aside class="col col-left">
          <section class="panel seg-panel">
            <div class="panel-head">路段监测</div>
            <SegmentListPanel
              :segments="segments"
              :selected-id="selectedId"
              @select="selectedId = $event"
            />
          </section>
          <section class="panel route-panel">
            <div class="panel-head">线路方案(推荐 + 备选)</div>
            <RoutePanel :plan="plan" :active-path-id="activePathId" @select="activePathId = $event" />
          </section>
        </aside>

        <main class="panel map-panel">
          <NetMap
            :segments="segments"
            :vehicles="vehicles"
            :selected-id="selectedId"
            :route-segments="routeSegments"
            @select="selectedId = $event"
          />
        </main>

        <aside class="col col-right">
          <section class="panel detail-panel">
            <div class="panel-head">路段详情</div>
            <SegmentDetailPanel :segment="selected" />
          </section>
        </aside>
      </div>

      <footer class="foot">
        <span>快照时间 {{ snapshotTs || '—' }}</span>
        <span>数据来源:mock 示例快照(契约 v2.0)· is_simulated = true · 示例路网非实测</span>
        <span>一期无视频画面,检测画面归二期 · 指令下发 / 回写归 W4</span>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.dash-viewport {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: radial-gradient(1200px 700px at 50% 38%, #0d1c33 0%, #081222 62%, #060d1a 100%);
}
.dash-stage {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 1920px;
  height: 1080px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px 22px;
  transform-origin: center center;
}
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 52px;
  padding: 0 18px;
  border: 1px solid #1d3354;
  border-radius: 10px;
  background: linear-gradient(90deg, rgba(16, 32, 58, 0.9), rgba(12, 25, 48, 0.9));
}
.bar-left,
.bar-mid,
.bar-right {
  display: flex;
  align-items: center;
  gap: 12px;
  white-space: nowrap;
}
.logo {
  color: #37d6ff;
  font-size: 22px;
}
.app-name {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 3px;
  color: #e6eefc;
}
.badge {
  font-size: 11px;
  padding: 2px 9px;
  border-radius: 4px;
  border: 1px solid;
}
.badge.mock {
  color: #ffd479;
  border-color: #8a6d1f;
  background: rgba(255, 212, 121, 0.1);
}
.badge.sim {
  color: #7fe7ff;
  border-color: #2a7f9e;
  background: rgba(55, 214, 255, 0.08);
}
.scenario {
  color: #9fb6d9;
  font-size: 14px;
  letter-spacing: 1px;
}
.conn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #7c93b5;
}
.conn .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.conn.up .dot {
  background: #35d08c;
  box-shadow: 0 0 0 3px rgba(53, 208, 140, 0.18);
}
.conn.down .dot {
  background: #e0564f;
  box-shadow: 0 0 0 3px rgba(224, 86, 79, 0.18);
}
.clock {
  font-size: 20px;
  font-weight: 700;
  color: #d9e4f5;
  font-variant-numeric: tabular-nums;
  min-width: 96px;
  text-align: right;
}
.cols {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 360px 1fr 400px;
  gap: 14px;
}
.col {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
}
.panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 14px;
  border: 1px solid #1d3354;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(16, 32, 58, 0.75), rgba(11, 23, 43, 0.85));
}
.seg-panel {
  flex: 11;
}
.route-panel {
  flex: 9;
}
.detail-panel {
  flex: 1;
}
.panel-head {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 2px;
  color: #9fb6d9;
  margin-bottom: 10px;
  padding-left: 8px;
  border-left: 3px solid #37d6ff;
  line-height: 1.2;
}
.map-panel {
  padding: 8px;
}
.foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 30px;
  font-size: 12px;
  color: #5f7396;
  white-space: nowrap;
}
</style>
