<script setup lang="ts">
// 左栏·路段监测列表:四级徽章(颜色+竖条+文字)+ 路段名 + 车速 + 链路来源。
// 数据陈旧的路段整行灰显"数据不可用"(TC-11 展示侧)。
import { computed } from 'vue'
import { demoSegment } from '../../../shared/demoNetwork'
import { isStale, levelStyle, type SegmentRecord, type TrafficSource } from '../../../shared/traffic'
import LevelBadge from './LevelBadge.vue'

const props = defineProps<{
  segments: SegmentRecord[]
  selectedId: string | null
}>()

const emit = defineEmits<{ (e: 'select', segmentId: string): void }>()

const rows = computed(() =>
  props.segments.map((seg) => ({
    seg,
    name: demoSegment(seg.segment_id)?.name ?? seg.segment_id,
    stale: isStale(seg),
    color: levelStyle(seg).color,
  })),
)

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
      <span class="speed" :style="{ color: row.stale ? '#8C8C8C' : row.color }">
        {{ row.stale ? '不可用' : `${row.seg.v_kmh ?? '—'} km/h` }}
      </span>
    </button>
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
</style>
