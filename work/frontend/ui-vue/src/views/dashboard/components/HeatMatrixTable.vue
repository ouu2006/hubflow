<script setup lang="ts">
// 路段 × 时间热力矩阵:每行 = 一个路段,每列 = 一个时间桶(labels),
// 格子色 = ciColor(v);null(该桶数据不可用)= 灰 #8B8B8B(绝不用 0 冒充)。
import { ciColor, UNAVAILABLE, type HeatMatrix } from '../../../shared/traffic'

defineProps<{ matrix: HeatMatrix | null }>()

function cellTitle(label: string, v: number | null): string {
  return v === null ? `${label} · 数据不可用` : `${label} · CI ${v.toFixed(1)}`
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
          :style="{ background: v === null ? UNAVAILABLE.color : ciColor(v) }"
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
</style>
