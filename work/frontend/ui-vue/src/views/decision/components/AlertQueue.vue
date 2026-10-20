<script setup lang="ts">
// 左栏 · 处置队列(设计稿 03):按告警四态分组(待认领 / 处置中 / 已闭环 / 误报),组头显示条数。
// 口径纪律:
//   ① 状态 chip **不用彩色**——四态一律中性底 + 文字 + 形态符号(○ ◐ ● ✕)区分,
//      避免第三条色彩轴与 LevelBadge 的等级色混淆(硬性口径 3);
//   ② 组内行 = 告警号 + 路段名 + 等级徽章 + 时间 + 状态 chip;
//   ③ 选中行用品牌浅底 + 左侧品牌竖条 = 「已选」语义(硬性口径 4)。
import LevelBadge from '../../dashboard/components/LevelBadge.vue'
import type { AlertStatus, CongestionLevel } from '../../../shared/traffic'

interface QueueRow {
  id: string
  segId: string
  name: string
  level: CongestionLevel
  stale: boolean
  /** 时间(首次观测的快照时间,只取时分秒) */
  time: string
  /** 状态 chip 文案(终态显示回写结果,如「已缓解 / 已消除 / 误报」) */
  chip: string
  state: AlertStatus
}

interface QueueGroup {
  state: AlertStatus
  items: QueueRow[]
}

defineProps<{
  groups: QueueGroup[]
  selectedId: string | null
  total: number
  openCount: number
}>()

const emit = defineEmits<{ (e: 'select', id: string): void }>()

/** 四态形态符号(中性,不承载颜色语义) */
const GLYPH: Record<AlertStatus, string> = {
  待认领: '○',
  处置中: '◐',
  已闭环: '●',
  误报: '✕',
}
</script>

<template>
  <section class="td-card">
    <div class="td-card-head">
      处置队列
      <span class="td-head-tag">{{ total }} 条 · 未闭环 {{ openCount }} 条</span>
    </div>
    <div class="td-card-body flush">
      <template v-for="g in groups" :key="g.state">
        <div class="grp">
          <span class="grp-glyph">{{ GLYPH[g.state] }}</span>
          <span class="grp-name">{{ g.state }}</span>
          <span class="grp-cnt td-num">{{ g.items.length }}</span>
        </div>
        <button
          v-for="row in g.items"
          :key="row.id"
          type="button"
          class="td-row q-row"
          :class="{ on: row.id === selectedId }"
          @click="emit('select', row.id)"
        >
          <span class="q-top">
            <span class="td-mono q-id">{{ row.id }}</span>
            <LevelBadge :level="row.level" :stale="row.stale" />
          </span>
          <span class="q-seg">{{ row.segId }} {{ row.name }}</span>
          <span class="q-bot">
            <span class="td-num q-time">{{ row.time }}</span>
            <span class="td-chip q-chip"><i class="gt">{{ GLYPH[row.state] }}</i>{{ row.chip }}</span>
          </span>
        </button>
        <p v-if="g.items.length === 0" class="q-empty">—</p>
      </template>
    </div>
  </section>
</template>

<style scoped>
.grp {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px 5px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
  background: var(--td-bg-color-secondarycontainer);
}
.grp-glyph {
  font-size: 10px;
}
.grp-name {
  font-weight: 500;
}
.grp-cnt {
  margin-left: auto;
  color: var(--td-text-color-placeholder);
}
.q-row {
  flex-direction: column;
  align-items: stretch;
  gap: 3px;
  width: 100%;
  border: none;
  border-bottom: 1px solid var(--td-component-stroke);
  background: transparent;
  text-align: left;
  font-family: inherit;
}
.q-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.q-id {
  font-size: 12px;
  color: var(--td-text-color-primary);
}
.q-seg {
  font-size: 12px;
  color: var(--td-text-color-primary);
}
.q-bot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.q-time {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
.q-chip .gt {
  font-style: normal;
  font-size: 9px;
}
.q-empty {
  margin: 0;
  padding: 6px 12px;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}

/* ---------- 响应式（Issue IKP3EV） ---------- */
/* 队列行本身无固定宽度/nowrap,窄屏只需收紧内边距保证行高与可点面积 */
@media (max-width: 900px) {
  .grp {
    padding: 6px 10px 4px;
  }
  .q-row {
    padding: 8px 10px;
  }
  .q-empty {
    padding: 6px 10px;
  }
}
/* ≤560:路段名允许折行(长站名不挤压等级徽章 / 时间),不出现页面横向滚动 */
@media (max-width: 560px) {
  .q-seg {
    line-height: 1.5;
  }
  .q-bot {
    flex-wrap: wrap;
    gap: 2px 8px;
  }
  .grp {
    padding: 6px 8px 4px;
  }
  .q-row {
    padding: 8px;
  }
}
</style>
