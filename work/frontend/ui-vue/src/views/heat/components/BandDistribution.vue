<script setup lang="ts">
// 档位分布 · 当前时刻:按 CI_BANDS 四档统计路段数 + 等级色方块;
// 不可用单独成档——灰虚线框 + 斜杠符号(手册 §6.2「档位分布用灰虚线框 + 斜杠」),绝不用蓝/绿。
import { LEVELS, type CongestionLevel } from '../../../shared/traffic'

defineProps<{
  rows: { level: CongestionLevel; name: string; count: number }[]
  unavailable: number
}>()
</script>

<template>
  <div class="dist">
    <div v-for="r in rows" :key="r.level" class="dist-row">
      <span class="swatch" :style="{ background: LEVELS[r.level].color }" />
      <span class="dist-name">{{ r.name }}</span>
      <span class="dist-count td-num">{{ r.count }}</span>
    </div>
    <div class="dist-row">
      <span class="unbox"><i /></span>
      <span class="dist-name">不可用</span>
      <span class="dist-count td-num">{{ unavailable }}</span>
    </div>
  </div>
</template>

<style scoped>
.dist {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.dist-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.swatch {
  width: 14px;
  height: 14px;
  border-radius: 2px;
  flex: 0 0 auto;
}
/* 不可用:灰虚线框 + 斜杠(不是实心方块) */
.unbox {
  position: relative;
  width: 14px;
  height: 14px;
  border: 1px dashed #8b8b8b;
  border-radius: 2px;
  flex: 0 0 auto;
}
.unbox i {
  position: absolute;
  left: 1px;
  top: 6px;
  width: 12px;
  height: 1.5px;
  background: #8b8b8b;
  transform: rotate(-45deg);
}
.dist-name {
  flex: 1;
  min-width: 0;
  color: var(--td-text-color-primary);
}
.dist-count {
  font-weight: 600;
  color: var(--td-text-color-primary);
  min-width: 24px;
  text-align: right;
}
</style>
