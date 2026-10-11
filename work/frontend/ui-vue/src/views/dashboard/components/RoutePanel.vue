<script setup lang="ts">
// 左栏·线路方案:推荐 / 备选 / 离站路线(契约 routes.json 形状,备选 ≥2 条)。
// 点击行切换地图上的高亮路线;why(推荐理由)原样展示。
import { computed } from 'vue'
import type { AlternativePath, RecommendResult, RoutePath } from '../../../shared/traffic'

const props = defineProps<{
  plan: RecommendResult | null
  activePathId: string | null
}>()

const emit = defineEmits<{ (e: 'select', pathId: string): void }>()

interface Row {
  path: RoutePath | AlternativePath
  tag: string
  why?: string
}

const rows = computed<Row[]>(() => {
  const p = props.plan
  if (!p) return []
  const list: Row[] = [{ path: p.arrival_route, tag: '推荐', why: p.why }]
  for (const alt of p.alternatives) list.push({ path: alt, tag: '备选', why: alt.reason })
  if (p.departure_route) list.push({ path: p.departure_route, tag: '离站' })
  return list
})
</script>

<template>
  <div class="route-list">
    <template v-if="rows.length">
      <button
        v-for="row in rows"
        :key="row.path.path_id"
        class="row"
        :class="{ active: props.activePathId === row.path.path_id }"
        type="button"
        @click="emit('select', row.path.path_id)"
      >
        <div class="head">
          <span class="tag" :data-tag="row.tag">{{ row.tag }}</span>
          <span class="pid">{{ row.path.path_id }}</span>
          <span class="eta">{{ row.path.eta_min }} 分钟</span>
        </div>
        <div class="sub">
          {{ row.path.segments?.join(' → ') ?? '路段组成待引擎返回' }}
          <template v-if="row.path.dropoff_point"> · 落客 {{ row.path.dropoff_point }}</template>
          <template v-if="row.path.walk_min !== undefined"> · 步行 {{ row.path.walk_min }} 分钟</template>
        </div>
        <div v-if="row.why" class="why">{{ row.why }}</div>
      </button>
    </template>
    <div v-else class="empty">暂无推荐路线(等待快照…)</div>
  </div>
</template>

<style scoped>
.route-list {
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
  flex-direction: column;
  gap: 4px;
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
  border-color: #37d6ff;
  background: rgba(30, 66, 110, 0.55);
}
.head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tag {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 4px;
  border: 1px solid;
}
.tag[data-tag='推荐'] {
  color: #7fe7ff;
  border-color: #2a7f9e;
  background: rgba(55, 214, 255, 0.12);
}
.tag[data-tag='备选'] {
  color: #b7c8e3;
  border-color: #37507a;
}
.tag[data-tag='离站'] {
  color: #c9b3ff;
  border-color: #5b4a8f;
}
.pid {
  font-size: 13px;
  color: #e6eefc;
  font-weight: 600;
}
.eta {
  margin-left: auto;
  font-size: 13px;
  color: #ffd479;
  font-weight: 600;
}
.sub {
  font-size: 11px;
  color: #8fa8cc;
  word-break: break-all;
}
.why {
  font-size: 11px;
  line-height: 1.5;
  color: #9fb6d9;
  border-top: 1px dashed #24406b;
  padding-top: 4px;
}
.empty {
  color: #7c93b5;
  font-size: 12px;
  padding: 12px 2px;
}
</style>
