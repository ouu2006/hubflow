<script setup lang="ts">
// 关联告警:已过滤为「本路段 + 未闭环(待认领 / 处置中)」。
// 行 = 告警号 + 等级徽章(三重编码) + 路段名 + 首次观测时间(取快照 ts,不另取浏览器时间)。
//
// ⚠️ 等级**不由本组件决定**:`levelOf` 是**必需** prop(Issue IKLLXG)——
//   告警自带的 `level` 是派生时的记录值,与当前路段快照可能不同步;
//   直接渲染 `a.level` 会让本卡与同页的路段列表 / 底部告警条自相矛盾。
//   做成**必需**是为了下次页面迁移时漏传会被 `vue-tsc` 当场拦下(这句口径曾在 #77 迁移时被漏搬)。
import type { AlertStatus, CongestionLevel, TrafficAlert } from '../../../shared/traffic'
import LevelBadge from './LevelBadge.vue'

defineProps<{
  alerts: TrafficAlert[]
  /** 该告警在当前路段快照下的等级(口径见 `shared/traffic.ts` 的 `alertLevelOf`) */
  levelOf: (a: TrafficAlert) => CongestionLevel
}>()

// 未闭环 = 待认领 / 处置中(已闭环 / 误报为终态)
const OPEN_STATUS: AlertStatus[] = ['待认领', '处置中']

function statusClass(s: AlertStatus): string {
  return OPEN_STATUS.includes(s) ? 'open' : 'closed'
}
</script>

<template>
  <div v-if="alerts.length > 0" class="al">
    <div v-for="a in alerts" :key="a.alert_id" class="al-row">
      <div class="al-line1">
        <span class="al-id td-mono">{{ a.alert_id }}</span>
        <LevelBadge :level="levelOf(a)" />
        <span class="al-status" :class="statusClass(a.status)">{{ a.status }}</span>
      </div>
      <div class="al-line2">
        <span>{{ a.segment_name }}</span>
        <span class="al-time td-mono">首次观测 {{ a.first_seen }}</span>
      </div>
    </div>
  </div>
  <p v-else class="al-empty">本路段无未闭环告警</p>
</template>

<style scoped>
.al {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.al-row {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--td-component-stroke);
}
.al-row:last-child {
  padding-bottom: 0;
  border-bottom: none;
}
.al-line1 {
  display: flex;
  align-items: center;
  gap: 8px;
}
.al-id {
  font-size: 12px;
  color: var(--td-text-color-primary);
}
/* 状态标签中性色:避免与等级色/品牌蓝混淆 */
.al-status {
  margin-left: auto;
  font-size: 10px;
  padding: 1px 7px;
  border-radius: var(--td-radius-sm);
}
.al-status.open {
  color: var(--td-text-color-primary);
  border: 1px solid var(--td-component-border);
  background: var(--td-bg-color-secondarycontainer);
}
.al-status.closed {
  color: var(--td-text-color-placeholder);
}
.al-line2 {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.al-time {
  color: var(--td-text-color-placeholder);
}
.al-empty {
  margin: 0;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}

/* ==========================================================================
   响应式（Issue IKP3EV）：手机宽度下告警号 / 等级 / 状态会挤成一行，
   改为允许换行（文案不动）。断点与 DashboardView 一致：560。
   ========================================================================== */
@media (max-width: 560px) {
  .al-row {
    gap: 4px;
  }
  .al-line1,
  .al-line2 {
    flex-wrap: wrap;
    gap: 2px 8px;
  }
  .al-status {
    margin-left: 0;
  }
}
</style>
