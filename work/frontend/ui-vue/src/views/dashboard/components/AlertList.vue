<script setup lang="ts">
// 关联告警:已过滤为「本路段 + 未闭环(待认领 / 处置中)」。
// 行 = 告警号 + 等级徽章(三重编码) + 路段名 + 首次观测时间(取快照 ts,不另取浏览器时间)。
import type { AlertStatus, TrafficAlert } from '../../../shared/traffic'
import LevelBadge from './LevelBadge.vue'

defineProps<{ alerts: TrafficAlert[] }>()

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
        <LevelBadge :level="a.level" />
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
</style>
