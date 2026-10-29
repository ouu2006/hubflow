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

/**
 * 列表里显示的路段名（2026-10-29 演示验收）。
 *
 * 原先名称单行 `nowrap + ellipsis`，而左栏只有 230 px —— 站区里"停车场内部通道（N-014→N-016）"
 * 这种名字被截成 **「停…」**，一屏三行全是同一个"停…"，只能靠别处去猜，演示时根本没法
 * 指着某一行说"看这段"。所以两处一起改：
 *   ① 去掉名字尾部的括注 `（N-014→N-016）`——那是路网节点编号，对观众没有意义，
 *      而它占掉的宽度正好是"停车场内部通道"这七个字；
 *   ② 允许最多两行（`-webkit-line-clamp`），段号单独一行小字常显。
 * 段号必须留着：它是页面上唯一能把这一行和地图、和决策页对上的钥匙。
 */
function shortName(name: string): string {
  const trimmed = name.replace(/（[^）]*）\s*$/, '').trim()
  return trimmed || name
}
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
      <span class="rank-name">
        <span class="rank-id">{{ it.id }}</span>
        <span class="rank-text">{{ shortName(it.name) }}</span>
      </span>
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
  display: flex;
  flex-direction: column;
  gap: 1px;
}
/* 段号：唯一能和地图 / 决策页对上的钥匙，必须常显（原来只藏在名字的括注里） */
.rank-id {
  font-size: 11px;
  line-height: 1.2;
  letter-spacing: 0.03em;
  color: var(--td-text-color-placeholder);
  font-variant-numeric: tabular-nums;
}
/* 名称最多两行：宁可换行也不截成「停…」（左栏 230 px 放不下站区这些长名） */
.rank-text {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
  line-height: 1.25;
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

/* ==========================================================================
   响应式（Issue IKP3EV）：手机宽度下名称列让出更多空间给 CI 数值 / 徽章。
   断点与 DashboardView 一致：560。
   ========================================================================== */
@media (max-width: 560px) {
  .rank-ci,
  .rank-out {
    min-width: 40px;
  }
  .rank-ci {
    font-size: 13px;
  }
  .rank-note {
    padding: 6px 8px;
  }
}
</style>
