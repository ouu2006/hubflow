<script setup lang="ts">
// 左栏·路段监测列表:四级徽章(颜色+竖条+文字)+ 路段名 + 车速/拥挤指数 + 链路来源。
// 数据陈旧的路段整行灰显"数据不可用"(TC-11 展示侧)。
// mode = 'index' 时:取值列改显 `ci`,并按 ci 降序(手册 §6.5 第 1 条:CI 可用于辅助排序)。
import { computed } from 'vue'
import { demoSegment } from '../../../shared/demoNetwork'
import {
  ciAvailable,
  CI_DISCLAIMER,
  ciStyleColor,
  isStale,
  levelStyle,
  type CongestionViewMode,
  type SegmentRecord,
  type TrafficSource,
} from '../../../shared/traffic'
import LevelBadge from './LevelBadge.vue'

const props = withDefaults(
  defineProps<{
    segments: SegmentRecord[]
    selectedId: string | null
    /** 'level' = 四级视图(默认) · 'index' = 拥挤指数视图(按 ci 辅助排序) */
    mode?: CongestionViewMode
  }>(),
  { mode: 'level' },
)

const emit = defineEmits<{ (e: 'select', segmentId: string): void }>()

const isIndex = computed(() => props.mode === 'index')

const rows = computed(() => {
  const mapped = props.segments.map((seg) => ({
    seg,
    name: demoSegment(seg.segment_id)?.name ?? seg.segment_id,
    stale: isStale(seg),
    color: levelStyle(seg).color,
    ciOk: ciAvailable(seg),
    value: isIndex.value
      ? ciAvailable(seg)
        ? `ci ${seg.ci}`
        : '不可用'
      : isStale(seg)
        ? '不可用'
        : `${seg.v_kmh ?? '—'} km/h`,
    valueColor: isStale(seg) || (isIndex.value && !ciAvailable(seg)) ? '#8C8C8C' : isIndex.value ? ciStyleColor(seg) : levelStyle(seg).color,
  }))
  // 辅助排序**只对指数视图**生效(手册 §6.5 第 1 条:CI 可用于辅助排序)。
  // 四级视图保持调用方传入的原序——不改既有调用方(/dashboard 路段监测列表)的顺序。
  // 指数视图:可用 ci 的在前按 ci 降序,**缺 ci / 陈旧的排最后**——陈旧 ci 不可信,
  // 不参与辅助排序(与 HeatView Top3 同口径;否则一条 `不可用` 的陈旧段会因 ci 高排在第 1 位)。
  return isIndex.value
    ? [...mapped].sort(
        (a, b) => (a.ciOk ? 0 : 1) - (b.ciOk ? 0 : 1) || (b.seg.ci ?? -1) - (a.seg.ci ?? -1),
      )
    : mapped
})

const SOURCE_LABEL: Record<TrafficSource, string> = {
  video: '视频链路',
  twin: '孪生链路',
}
</script>

<template>
  <div class="seg-list">
    <button
      v-for="row in rows"
      :key="row.seg.segment_id"
      class="row"
      :class="{ active: props.selectedId === row.seg.segment_id, stale: row.stale }"
      type="button"
      @click="emit('select', row.seg.segment_id)"
    >
      <LevelBadge :level="row.seg.level" :stale="row.stale" />
      <span class="meta">
        <span class="name">{{ row.name }}</span>
        <span class="id">{{ row.seg.segment_id }} · {{ SOURCE_LABEL[row.seg.source] }}</span>
      </span>
      <span class="speed" :style="{ color: row.valueColor }">
        {{ row.value }}
      </span>
    </button>
    <p v-if="isIndex" class="list-note">{{ CI_DISCLAIMER }}</p>
  </div>
</template>

<style scoped>
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
  width: 100%;
  padding: 9px 10px;
  background: rgba(20, 38, 66, 0.55);
  border: 1px solid #1d3354;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  color: inherit;
  font: inherit;
}
.row:hover {
  border-color: #2c4a78;
}
.row.active {
  border-color: #3fd2ff;
  background: rgba(30, 66, 110, 0.55);
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
.speed {
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}
.list-note {
  margin: 6px 0 0;
  font-size: 10px;
  line-height: 1.5;
  color: #ffd479;
}
</style>
