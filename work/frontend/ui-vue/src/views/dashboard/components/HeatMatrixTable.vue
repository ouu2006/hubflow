<script setup lang="ts">
// 路段 × 时间热力矩阵:每行 = 一个路段,每列 = 一个时间桶(labels),
// 格子色 = ciColor(v)（拥堵版）/ 流量档位色（流量版, Issue IKNB9G）/ 压灰（③④ 档, IKRK8B）;
// null(该桶数据不可用 / 流量版只给当前快照)= 灰 #8B8B8B(绝不用 0 冒充)。
//
// ③④ 档（自定义路线版 / 灰底版）口径：**数值照留、一律不上色**——格子压灰 #C9CDD4；
// 那与「数据不可用」灰 #8B8B8B 是两件事（后者永远表示"没有数据"），不复用同一个色。
import { ciColor, UNAVAILABLE, type HeatMatrix } from '../../../shared/traffic'
import { flowBandOfQ, MODE_DIM_GRAY, MODE_NO_TRAFFIC_NOTE } from '../../../shared/flow'

const props = withDefaults(
  defineProps<{
    matrix: HeatMatrix | null
    /**
     * ci    = 决策拥堵版（CI 色阶）；
     * flow  = 纯车流量版（q_vph 四档蓝阶）；
     * gray  = ③④ 档（自定义路线版 / 灰底版）：数值照留、全部压灰，本档不表示路况。
     */
    mode?: 'ci' | 'flow' | 'gray'
  }>(),
  { mode: 'ci' },
)

function cellColor(v: number | null): string {
  if (v === null) return UNAVAILABLE.color
  if (props.mode === 'flow') return flowBandOfQ(v)?.color ?? UNAVAILABLE.color
  // ③④ 档：有值也不上色（#C9CDD4），看数值请切回决策拥堵版 / 纯车流量版
  if (props.mode === 'gray') return MODE_DIM_GRAY
  return ciColor(v)
}

function cellTitle(label: string, v: number | null): string {
  if (v === null) return `${label} · ${props.mode === 'flow' ? '无流量数据（该桶未提供 q）' : '数据不可用'}`
  if (props.mode === 'flow') return `${label} · q ${v.toFixed(0)} 辆/h`
  if (props.mode === 'gray') return `${label} · CI ${v.toFixed(1)}（${MODE_NO_TRAFFIC_NOTE}：压灰不上色）`
  return `${label} · CI ${v.toFixed(1)}`
}
</script>

<template>
  <div v-if="matrix" class="hm td-scroll">
    <div class="hm-row hm-head">
      <span class="hm-name">路段 \ 时间</span>
      <span class="hm-cells">
        <i v-for="(l, i) in matrix.labels" :key="i" class="hm-lab">{{ l.slice(0, 5) }}</i>
      </span>
    </div>
    <div v-for="row in matrix.rows" :key="row.segment_id" class="hm-row">
      <span class="hm-name">{{ row.name }}</span>
      <span class="hm-cells">
        <i
          v-for="(v, i) in row.buckets"
          :key="i"
          class="hm-cell"
          :style="{ background: cellColor(v) }"
          :title="cellTitle(matrix.labels[i] ?? '', v)"
        />
      </span>
    </div>
  </div>
  <p v-else class="hm-empty">加载中…</p>
</template>

<style scoped>
.hm {
  padding: 6px 10px 10px;
  max-height: 300px;
}
.hm-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 0;
}
.hm-name {
  flex: 0 0 116px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hm-cells {
  flex: 1;
  min-width: 0;
  display: flex;
  gap: 2px;
}
.hm-cell,
.hm-lab {
  flex: 1;
  min-width: 0;
  height: 13px;
  border-radius: 2px;
}
.hm-lab {
  height: auto;
  font-size: 9px;
  font-style: normal;
  color: var(--td-text-color-placeholder);
  font-family: var(--td-font-family-mono);
  overflow: hidden;
}
.hm-empty {
  margin: 0;
  padding: 12px;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}

/* ==========================================================================
   响应式（Issue IKP3EV）
   12 个时间桶在 360px 宽里会被压成 17px/格、标签糊成一片：
   窄屏改为「行保持最小宽度 + 整个矩阵内部横向滚动」，不撑破页面。
   断点与 DashboardView 一致：768 / 560。
   ========================================================================== */
@media (max-width: 768px) {
  .hm {
    /* .td-scroll 已给 overflow-y:auto，这里只补横向；内部滚动不向外传递。 */
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
  .hm-row {
    min-width: 600px;
  }
  .hm-name {
    flex: 0 0 96px;
  }
}

@media (max-width: 560px) {
  .hm {
    padding: 6px 8px 8px;
  }
  .hm-row {
    min-width: 560px;
  }
}
</style>
