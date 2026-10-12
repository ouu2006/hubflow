<script setup lang="ts">
// 成因拆解 · 本期生效因素:因素编号 + 名称 + 自动/人工 + 倍率。
// 人工置位口子 = F07 / F08 / F11(手册第 19 章;本页展示口径):命中即标「人工」,其余视为「自动」。
// 标记一律中性(灰/描边),不用品牌蓝、不用等级色——避免与「已选」与「路况等级」语义混淆。
import type { FactorApplied } from '../../../shared/traffic'

defineProps<{ factors: (FactorApplied & { segment_id: string })[] }>()

const MANUAL_FACTOR_IDS = new Set(['F07', 'F08', 'F11'])

function isManual(factorId: string): boolean {
  return MANUAL_FACTOR_IDS.has(factorId)
}

function multText(m: number): string {
  return `${m >= 1 ? '+' : ''}${m}`
}
</script>

<template>
  <div v-if="factors.length > 0" class="fac">
    <div v-for="f in factors" :key="f.factor_id" class="fac-row">
      <span class="fac-id td-mono">{{ f.factor_id }}</span>
      <span class="fac-name">{{ f.name }}</span>
      <span class="tag" :class="isManual(f.factor_id) ? 'manual' : 'auto'">
        {{ isManual(f.factor_id) ? '人工' : '自动' }}
      </span>
      <span class="fac-m td-mono">{{ multText(f.multiplier) }}</span>
    </div>
  </div>
  <p v-else class="fac-empty">本期无生效因素</p>
</template>

<style scoped>
.fac {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.fac-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.fac-id {
  color: var(--td-text-color-placeholder);
}
.fac-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--td-text-color-primary);
}
.tag {
  padding: 1px 7px;
  font-size: 10px;
  border-radius: var(--td-radius-sm);
  flex: 0 0 auto;
}
.tag.auto {
  color: var(--td-text-color-placeholder);
}
.tag.manual {
  color: var(--td-text-color-primary);
  border: 1px solid var(--td-component-border);
  background: var(--td-bg-color-secondarycontainer);
}
.fac-m {
  min-width: 42px;
  text-align: right;
  color: var(--td-text-color-primary);
}
.fac-empty {
  margin: 0;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}
</style>
