<script setup lang="ts">
// 档位分布 · 当前时刻:按档位统计路段数 + 色块;
//   拥堵版 = CI 四档（沿用既有口径，色取等级色）；
//   流量版（Issue IKNB9G）= q_vph 四档（色由调用方按 shared/flow.ts 配置传入）。
// 不可用单独成档——灰虚线框 + 斜杠符号(手册 §6.2「档位分布用灰虚线框 + 斜杠」),绝不用蓝/绿。
import { LEVELS, type CongestionLevel } from '../../../shared/traffic'

const props = withDefaults(
  defineProps<{
    rows: { level: CongestionLevel; name: string; count: number; color?: string }[]
    unavailable: number
    /** 不可用档的名称（拥堵版=不可用；流量版=无流量数据） */
    unavailableLabel?: string
  }>(),
  { unavailableLabel: '不可用' },
)

function rowColor(level: CongestionLevel, color?: string): string {
  return color ?? LEVELS[level]?.color ?? '#8B8B8B'
}
</script>

<template>
  <div class="dist">
    <div v-for="r in props.rows" :key="r.level" class="dist-row">
      <span class="swatch" :style="{ background: rowColor(r.level, r.color) }" />
      <span class="dist-name">{{ r.name }}</span>
      <span class="dist-count td-num">{{ r.count }}</span>
    </div>
    <div class="dist-row">
      <span class="unbox"><i /></span>
      <span class="dist-name">{{ props.unavailableLabel }}</span>
      <span class="dist-count td-num">{{ props.unavailable }}</span>
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

/* ==========================================================================
   响应式（Issue IKP3EV）：手机宽度下档位行略收紧，保证色块 + 档名 + 数量
   在 340px 宽内一行放得下。断点与 DashboardView 一致：560。
   ========================================================================== */
@media (max-width: 560px) {
  .dist-row {
    gap: 6px;
    font-size: 11.5px;
  }
  .dist-count {
    min-width: 20px;
  }
}
</style>
