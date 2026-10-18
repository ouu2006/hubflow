<script setup lang="ts">
// 路段指数排行:仅 ciAvailable 为真者参与「按 CI 降序」排序并显示数值;
// 不可用路段恒灰、排最后、显示「不可用」(TC-11:缺 CI 或数据陈旧绝不落进通配色)。
// 列表底部标注 CI 免责口径(手册 §6.5 第 1 条:页脚 / 图例 / 列表三处必现)。
import { CI_DISCLAIMER, type CongestionLevel } from '../../../shared/traffic'
import LevelBadge from './LevelBadge.vue'

defineProps<{
  items: {
    id: string
    name: string
    ci: number | null
    level: CongestionLevel | 0
    available: boolean
  }[]
  selectedId: string | null
}>()

const emit = defineEmits<{ (e: 'select', id: string): void }>()
</script>

<template>
  <div class="rank">
    <div
      v-for="it in items"
      :key="it.id"
      class="td-row rank-row"
      :class="{ on: it.id === selectedId }"
      role="button"
      @click="emit('select', it.id)"
    >
      <span class="rank-name">{{ it.name }}</span>
      <template v-if="it.available && it.ci !== null">
        <span class="rank-ci td-num">{{ (it.ci ?? 0).toFixed(1) }}</span>
        <LevelBadge :level="it.level" />
      </template>
      <span v-else class="rank-out">不可用</span>
    </div>
    <p class="rank-note">{{ CI_DISCLAIMER }}</p>
  </div>
</template>

<style scoped>
.rank {
  display: flex;
  flex-direction: column;
}
.rank-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--td-text-color-primary);
}
.rank-ci {
  font-size: 14px;
  font-weight: 600;
  color: var(--td-text-color-primary);
  min-width: 46px;
  text-align: right;
}
/* 不可用 = 数据不可用灰(非等级色) */
.rank-out {
  font-size: 12px;
  color: #8b8b8b;
  min-width: 46px;
  text-align: right;
}
.rank-note {
  margin: 0;
  padding: 7px 12px;
  font-size: 10px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder);
  background: var(--td-bg-color-secondarycontainer);
  border-top: 1px solid var(--td-component-stroke);
}
</style>
