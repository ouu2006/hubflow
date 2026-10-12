<script setup lang="ts">
// 拥挤度热力(Issue #66,手册 §11.2 第 2 行 / 判定 C-2):
//   四级色 + 图例 + 更新时间戳,可切**拥挤指数视图**。
// 硬口径(手册 §6.5 第 1 条):CI 是四项加权合成的 0~100 分,**只用于热力展示与辅助排序**,
//   不得作为判级依据;CI 与四项指标冲突时一律以四项指标为准——所以两种视图必须能在同页互证。
// 数据:契约 v2.0 mock 快照(GET /api/traffic/segments)+ SSE traffic_snapshot;
//   一期无真实快照,页面不出现"实时/实测"表述。
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getTrafficSegments, getTrafficVehicles, subscribeTrafficSnapshot } from '../../api/traffic'
import { networkSourceLabel } from '../../shared/demoNetwork'
import {
  CI_DISCLAIMER,
  ciAvailable,
  type CongestionViewMode,
  type SegmentRecord,
  type VehicleRecord,
} from '../../shared/traffic'
import NetMap from '../dashboard/components/NetMap.vue'
import SegmentListPanel from '../dashboard/components/SegmentListPanel.vue'

const mode = ref<CongestionViewMode>('level')
const segments = ref<SegmentRecord[]>([])
const vehicles = ref<VehicleRecord[]>([])
// 选中态:列表与地图互通(与 /dashboard 行为一致;此前传 null + 空函数,点击无反馈)
const selectedId = ref<string | null>(null)
const snapshotTs = ref('')
const live = ref(false)
const sourceLabel = networkSourceLabel()

let unsubscribe: (() => void) | null = null

async function refresh(): Promise<void> {
  const [seg, veh] = await Promise.allSettled([getTrafficSegments(), getTrafficVehicles()])
  if (seg.status === 'fulfilled') {
    segments.value = seg.value.segments
    snapshotTs.value = seg.value.ts
  }
  if (veh.status === 'fulfilled') vehicles.value = veh.value.vehicles
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

/** 指数视图下"最拥挤的几条"用于辅助排序举证(只展示,不改判级) */
const topByCi = computed(() =>
  [...segments.value]
    // 与地图/左栏**同一口径**:陈旧或 ci 非有限的一律不进榜——
    // 否则会出现"地图画灰、左栏写不可用、Top3 却有它"的同页自相矛盾(手册:缺 ci 或超限一律灰)
    .filter((s) => ciAvailable(s))
    .sort((a, b) => (b.ci ?? 0) - (a.ci ?? 0))
    .slice(0, 3),
)

/** ci 上屏文案:取色按 [0, 100] 夹取,文案同样夹取,避免越界值(如抖动后的 102)与图例刻度不符 */
function ciText(s: SegmentRecord): string {
  return `ci ${Math.min(100, Math.max(0, s.ci as number))}`
}
</script>

<template>
  <div class="heat-page">
    <header class="bar">
      <div class="bar-left">
        <span class="logo">◈</span>
        <span class="app-name">拥挤度热力</span>
        <span class="badge sim">演示数据(模拟)· is_simulated = true</span>
      </div>
      <div class="bar-mid">
        <span class="seg-toggle" role="group" aria-label="视图切换">
          <button
            type="button"
            class="tg"
            :class="{ on: mode === 'level' }"
            :aria-pressed="mode === 'level'"
            @click="mode = 'level'"
          >
            四级视图
          </button>
          <button
            type="button"
            class="tg"
            :class="{ on: mode === 'index' }"
            :aria-pressed="mode === 'index'"
            @click="mode = 'index'"
          >
            拥挤指数视图
          </button>
        </span>
        <span class="ts">更新时间戳(快照时间) {{ snapshotTs || '—' }}</span>
      </div>
      <div class="bar-right">
        <span class="conn" :class="live ? 'up' : 'down'">
          <i class="dot" />
          {{ live ? '快照流已连接' : '快照流未连接' }}
        </span>
        <RouterLink class="nav-link" to="/dashboard">态势大屏 ›</RouterLink>
        <RouterLink class="nav-link" to="/perception">感知层 ›</RouterLink>
        <RouterLink class="nav-link" to="/decision">决策工作台 ›</RouterLink>
      </div>
    </header>

    <div class="main">
      <section class="panel list-panel">
        <div class="panel-head">
          路段监测({{ mode === 'index' ? '按拥挤指数辅助排序' : '按等级排序' }})
        </div>
        <SegmentListPanel
          :segments="segments"
          :selected-id="selectedId"
          :mode="mode"
          @select="selectedId = $event"
        />
      </section>

      <section class="panel map-panel">
        <div class="panel-head">
          路网{{ mode === 'index' ? '拥挤指数' : '四级色' }}热力
          <span class="head-note">
            图例见左下 · 更新 {{ snapshotTs || '—' }}
          </span>
        </div>
        <div class="map-body">
          <NetMap
            :segments="segments"
            :vehicles="vehicles"
            :selected-id="selectedId"
            :route-segments="[]"
            :mode="mode"
            :ts="snapshotTs"
            @select="selectedId = $event"
          />
        </div>
      </section>

      <aside class="panel side-panel">
        <div class="panel-head">{{ mode === 'index' ? '拥挤指数 Top 3(辅助排序)' : '四级视图说明' }}</div>
        <template v-if="mode === 'index'">
          <div v-for="s in topByCi" :key="s.segment_id" class="top-row">
            <span class="top-id">{{ s.segment_id }}</span>
            <span class="top-ci">{{ ciText(s) }}</span>
            <span class="top-lv">判级 {{ s.level_name ?? s.level }}</span>
          </div>
          <p v-if="topByCi.length === 0" class="empty">当前快照无可用 ci(接口层未起?)</p>
          <p class="note strong">{{ CI_DISCLAIMER }}</p>
          <p class="note">
            指数色阶锚点复用手册 §6.2 四级色值;热力仅做「路段级色块 + 强度晕染」,不做断面间无标注内插。
          </p>
        </template>
        <template v-else>
          <p class="note">
            四级色 = 判级产出(`level` / `level_name`),颜色 + 竖条图标 + 文字三重编码同时出现,关掉颜色也能区分四级。
          </p>
          <p class="note">数据陈旧或等级不可用时显示灰色「数据不可用」(TC-11),绝不显示成蓝色。</p>
          <p class="note">切到「拥挤指数视图」可看 `ci` 色阶;两种视图同页互证,冲突时以四级为准。</p>
        </template>
      </aside>
    </div>

    <footer class="foot">
      <span>快照时间 {{ snapshotTs || '—' }}</span>
      <span>数据来源:mock 示例快照(契约 v2.0)· is_simulated = true · {{ sourceLabel }}</span>
      <span>CI 只用于展示与辅助排序,不作为判级依据(手册 §6.5 第 1 条)</span>
    </footer>
  </div>
</template>

<style scoped>
.heat-page {
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
  flex: 0 0 auto;
  padding: 0 16px;
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
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 3px;
  color: #e6eefc;
}
.badge {
  font-size: 11px;
  padding: 2px 9px;
  border-radius: 4px;
  border: 1px solid #2a7f9e;
  color: #7fe7ff;
  background: rgba(55, 214, 255, 0.08);
}
.seg-toggle {
  display: inline-flex;
  border: 1px solid #1d3354;
  border-radius: 6px;
  overflow: hidden;
}
.tg {
  font: inherit;
  font-size: 13px;
  padding: 5px 14px;
  background: transparent;
  color: #9fb6d9;
  border: none;
  cursor: pointer;
}
.tg.on {
  background: rgba(55, 214, 255, 0.16);
  color: #8feaff;
  font-weight: 600;
}
.ts {
  font-size: 12px;
  color: #9fb6d9;
  font-variant-numeric: tabular-nums;
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
}
.conn.down .dot {
  background: #e0564f;
}
.nav-link {
  font-size: 13px;
  color: #37d6ff;
  text-decoration: none;
  border: 1px solid #1d3354;
  border-radius: 6px;
  padding: 4px 10px;
}
.nav-link:hover {
  border-color: #2c4a78;
  background: rgba(55, 214, 255, 0.08);
}
.main {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(280px, 0.85fr) minmax(0, 2.4fr) minmax(260px, 0.85fr);
  gap: 14px;
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
.panel-head {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 1px;
  color: #9fb6d9;
  margin-bottom: 10px;
  padding-left: 8px;
  border-left: 3px solid #37d6ff;
  line-height: 1.3;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.head-note {
  font-size: 11px;
  font-weight: 400;
  color: #7c93b5;
  font-variant-numeric: tabular-nums;
}
.map-panel {
  padding: 8px;
}
.map-body {
  flex: 1;
  min-height: 0;
}
.side-panel {
  overflow-y: auto;
}
.top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  margin-bottom: 6px;
  border: 1px solid #1d3354;
  border-radius: 8px;
  background: rgba(20, 38, 66, 0.55);
  font-size: 12px;
}
.top-id {
  color: #7c93b5;
}
.top-ci {
  color: #ffd479;
  font-weight: 600;
}
.top-lv {
  color: #d9e4f5;
}
.note {
  font-size: 11px;
  line-height: 1.6;
  color: #7c93b5;
  margin: 8px 0 0;
}
.note.strong {
  color: #ffd479;
}
.empty {
  font-size: 12px;
  color: #7c93b5;
}
.foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 30px;
  flex: 0 0 auto;
  font-size: 12px;
  color: #5f7396;
  white-space: nowrap;
}
@media (max-width: 1100px) {
  .heat-page {
    overflow: auto;
    height: auto;
  }
  .main {
    grid-template-columns: 1fr;
  }
  .bar {
    flex-wrap: wrap;
    height: auto;
    padding: 10px 16px;
  }
  .foot {
    flex-wrap: wrap;
    height: auto;
    white-space: normal;
  }
}
</style>
