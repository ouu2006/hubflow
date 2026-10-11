<script setup lang="ts">
// 感知层 · YOLO 检测画面页(Issue #54,三层前端之一):
//   左 = 检测画面区(示例场景 + 检测框叠加演示层);右 = 感知指标快照(video/twin 双链路并排,TC-19 口径)。
// 数据来源:复用既有 mock 快照 GET /api/traffic/segments + SSE traffic_snapshot(不新增端点/事件名)。
// 口径:一期无视频流,画面为前端演示叠加层(demoPerception.ts,非契约字段);真实检测画面归二期。
//   页面不出现"实时画面/实测"表述;角标按手册 M1-7(演示数据(模拟)· 双数据源)。
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getTrafficSegments, subscribeTrafficSnapshot } from '../../api/traffic'
import { demoSegment } from '../../shared/demoNetwork'
import { DEMO_DETECTIONS, DEMO_FRAME_NOTE, type DemoDetection } from '../../shared/demoPerception'
import { isStale, levelStyle, type SegmentRecord, type TrafficSource } from '../../shared/traffic'
import LevelBadge from '../dashboard/components/LevelBadge.vue'

const segments = ref<SegmentRecord[]>([])
const live = ref(false)
const snapshotTs = ref('')

let unsubscribe: (() => void) | null = null

async function refresh(): Promise<void> {
  // 只读快照:与 dashboard 相同的端点,哪次成功用哪次
  try {
    const snap = await getTrafficSegments()
    segments.value = snap.segments
    snapshotTs.value = snap.ts
  } catch {
    /* 联调期接口层可能未起:SSE 重连后会再拉 */
  }
}

onMounted(() => {
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
})

const SOURCE_LABEL: Record<TrafficSource, string> = {
  video: '视频链路',
  twin: '孪生链路',
}

// 快照按 source 分组,双链路并排展示(同一路段两条链路各出各的,TC-19)
const videoRows = computed(() => rowsOf('video'))
const twinRows = computed(() => rowsOf('twin'))

function rowsOf(source: TrafficSource) {
  return segments.value
    .filter((seg) => seg.source === source)
    .map((seg) => ({
      seg,
      name: demoSegment(seg.segment_id)?.name ?? seg.segment_id,
      stale: isStale(seg),
      color: levelStyle(seg).color,
    }))
}

function boxStyle(d: DemoDetection): Record<string, string> {
  return {
    left: `${d.x * 100}%`,
    top: `${d.y * 100}%`,
    width: `${d.w * 100}%`,
    height: `${d.h * 100}%`,
  }
}
</script>

<template>
  <div class="perc-page">
    <header class="bar">
      <div class="bar-left">
        <span class="logo">◈</span>
        <span class="app-name">感知层 · YOLO 检测画面</span>
        <span class="badge mock">MOCK</span>
      </div>
      <div class="bar-mid">
        <span class="badge sim">演示数据(模拟)· 双数据源(视频链路 + 孪生链路)· is_simulated = true</span>
      </div>
      <div class="bar-right">
        <span class="conn" :class="live ? 'up' : 'down'">
          <i class="dot" />
          {{ live ? '快照流已连接' : '快照流未连接' }}
        </span>
        <RouterLink class="dash-link" to="/dashboard">态势大屏 ›</RouterLink>
      </div>
    </header>

    <div class="cols">
      <section class="panel video-panel">
        <div class="panel-head">检测画面(叠加层演示)</div>
        <div class="frame-wrap">
          <svg class="scene" viewBox="0 0 640 360" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
            <defs>
              <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="#0b1a30" />
                <stop offset="1" stop-color="#13294a" />
              </linearGradient>
              <linearGradient id="road" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="#1c2740" />
                <stop offset="1" stop-color="#2a3a5c" />
              </linearGradient>
            </defs>
            <rect width="640" height="150" fill="url(#sky)" />
            <!-- 远景建筑剪影 -->
            <rect x="30" y="96" width="70" height="54" fill="#16263f" />
            <rect x="120" y="82" width="52" height="68" fill="#1a2c48" />
            <rect x="196" y="104" width="88" height="46" fill="#142240" />
            <rect x="410" y="90" width="60" height="60" fill="#1a2c48" />
            <rect x="486" y="100" width="92" height="50" fill="#16263f" />
            <!-- 地面与路面(透视梯形) -->
            <rect y="150" width="640" height="210" fill="#101c31" />
            <polygon points="250,150 390,150 640,360 0,360" fill="url(#road)" />
            <!-- 车道虚线(向消失点收拢) -->
            <line x1="313" y1="150" x2="213" y2="360" stroke="#3d5378" stroke-width="3" stroke-dasharray="18 14" />
            <line x1="327" y1="150" x2="427" y2="360" stroke="#3d5378" stroke-width="3" stroke-dasharray="18 14" />
            <line x1="250" y1="150" x2="0" y2="360" stroke="#55759f" stroke-width="4" />
            <line x1="390" y1="150" x2="640" y2="360" stroke="#55759f" stroke-width="4" />
            <!-- 路缘与人行道 -->
            <polygon points="196,150 250,150 0,360 0,332" fill="#1a2a44" />
            <polygon points="390,150 444,150 640,332 640,360" fill="#1a2a44" />
          </svg>
          <!-- 检测框叠加层(演示数据,见 shared/demoPerception.ts) -->
          <div v-for="(d, i) in DEMO_DETECTIONS" :key="i" class="det-box" :style="boxStyle(d)">
            <span class="det-label">{{ d.label }} {{ d.conf.toFixed(2) }}</span>
          </div>
          <div class="frame-note">{{ DEMO_FRAME_NOTE }}</div>
        </div>
        <p class="frame-meta">
          检测链路:YOLO 检测 + 跟踪(一期跑 6 段样本视频 → 透视标定 → 四项指标);本页画面与检测框为前端演示叠加层,非契约字段。
        </p>
      </section>

      <aside class="col">
        <section class="panel link-panel">
          <div class="panel-head">视频感知链路(source = video)</div>
          <div class="seg-list">
            <div v-for="row in videoRows" :key="row.seg.segment_id" class="row" :class="{ stale: row.stale }">
              <LevelBadge :level="row.seg.level" :stale="row.stale" />
              <span class="meta">
                <span class="name">{{ row.name }}</span>
                <span class="id">{{ row.seg.segment_id }} · {{ SOURCE_LABEL[row.seg.source] }}</span>
              </span>
              <span class="metrics" :style="row.stale ? { color: '#8C8C8C' } : { color: row.color }">
                <template v-if="row.stale">不可用</template>
                <template v-else>
                  {{ row.seg.q_vph ?? '—' }} vph · {{ row.seg.v_kmh ?? '—' }} km/h · 排队
                  {{ row.seg.L_q_m ?? 0 }} m
                </template>
              </span>
            </div>
            <p v-if="videoRows.length === 0" class="empty">快照为空(接口层未起?)</p>
          </div>
        </section>

        <section class="panel link-panel">
          <div class="panel-head">孪生链路(source = twin)</div>
          <div class="seg-list">
            <div v-for="row in twinRows" :key="row.seg.segment_id" class="row" :class="{ stale: row.stale }">
              <LevelBadge :level="row.seg.level" :stale="row.stale" />
              <span class="meta">
                <span class="name">{{ row.name }}</span>
                <span class="id">{{ row.seg.segment_id }} · {{ SOURCE_LABEL[row.seg.source] }}</span>
              </span>
              <span class="metrics" :style="row.stale ? { color: '#8C8C8C' } : { color: row.color }">
                <template v-if="row.stale">不可用</template>
                <template v-else>
                  {{ row.seg.q_vph ?? '—' }} vph · {{ row.seg.v_kmh ?? '—' }} km/h · 排队
                  {{ row.seg.L_q_m ?? 0 }} m
                </template>
              </span>
            </div>
            <p v-if="twinRows.length === 0" class="empty">快照为空(接口层未起?)</p>
          </div>
        </section>
      </aside>
    </div>

    <footer class="foot">
      <span>快照时间 {{ snapshotTs || '—' }}</span>
      <span>数据来源:mock 示例快照(契约 v2.0)· 双链路 is_simulated 恒 true · 四级编码见手册 §6.2</span>
      <span>一期无视频流 · 真实检测画面归二期</span>
    </footer>
  </div>
</template>

<style scoped>
.perc-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100vh;
  padding: 16px 20px;
  box-sizing: border-box;
  background: radial-gradient(1200px 700px at 50% 38%, #0d1c33 0%, #081222 62%, #060d1a 100%);
  color: #cfe0f5;
  overflow: hidden;
}
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  height: 52px;
  padding: 0 18px;
  border: 1px solid #1d3354;
  border-radius: 10px;
  background: linear-gradient(90deg, rgba(16, 32, 58, 0.9), rgba(12, 25, 48, 0.9));
  white-space: nowrap;
}
.bar-left,
.bar-mid,
.bar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.logo {
  color: #37d6ff;
  font-size: 22px;
}
.app-name {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 2px;
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
.dash-link {
  font-size: 13px;
  color: #37d6ff;
  text-decoration: none;
  border: 1px solid #1d3354;
  border-radius: 6px;
  padding: 4px 10px;
}
.dash-link:hover {
  border-color: #2c4a78;
  background: rgba(55, 214, 255, 0.08);
}
.cols {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(360px, 1fr);
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
.link-panel {
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
.frame-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #1d3354;
  background: #0b1a30;
}
.scene {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.det-box {
  position: absolute;
  border: 1.5px solid #37d6ff;
  border-radius: 3px;
  box-shadow: 0 0 0 1px rgba(8, 18, 34, 0.6) inset;
}
.det-label {
  position: absolute;
  left: -1.5px;
  top: -20px;
  font-size: 11px;
  line-height: 18px;
  padding: 0 6px;
  border-radius: 3px 3px 3px 0;
  color: #081222;
  background: #37d6ff;
  white-space: nowrap;
}
.frame-note {
  position: absolute;
  left: 10px;
  bottom: 10px;
  font-size: 12px;
  color: #ffd479;
  background: rgba(8, 18, 34, 0.72);
  border: 1px solid #8a6d1f;
  border-radius: 4px;
  padding: 3px 9px;
}
.frame-meta {
  margin: 10px 2px 0;
  font-size: 12px;
  line-height: 1.6;
  color: #7c93b5;
}
.seg-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
  padding-right: 2px;
}
.row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  background: rgba(20, 38, 66, 0.55);
  border: 1px solid #1d3354;
  border-radius: 8px;
}
.row.stale {
  color: #8c8c8c;
}
.meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}
.name {
  font-size: 14px;
  color: #e6eefc;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.row.stale .name {
  color: #8c8c8c;
}
.id {
  font-size: 11px;
  color: #7c93b5;
}
.metrics {
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.empty {
  font-size: 12px;
  color: #5f7396;
  padding: 8px 2px;
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
@media (max-width: 1100px) {
  .cols {
    grid-template-columns: 1fr;
    overflow-y: auto;
  }
  .video-panel {
    min-height: 320px;
  }
}
</style>
