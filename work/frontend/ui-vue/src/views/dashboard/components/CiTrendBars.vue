<script setup lang="ts">
// CI 走势 · 近 12 期:竖向色块(色 = ciColor),底部对齐;叠加 65 / 85 阈值虚线。
import { ciColor, type CiHistory } from '../../../shared/traffic'

defineProps<{ history: CiHistory | null }>()

function pct(ci: number): string {
  return `${Math.min(100, Math.max(2, ci))}%`
}
</script>

<template>
  <div v-if="history" class="trend">
    <template v-if="history.points.length > 0">
      <div class="plot">
        <span class="thr" :style="{ bottom: '65%' }" />
        <span class="thr" :style="{ bottom: '85%' }" />
        <div class="bars">
          <span
            v-for="(p, i) in history.points"
            :key="i"
            class="bar"
            :style="{ height: pct(p.ci), background: ciColor(p.ci) }"
            :title="`${p.ts} · CI ${p.ci}`"
          />
        </div>
      </div>
      <div class="axis">
        <span class="td-mono">min {{ history.min === null ? '—' : history.min.toFixed(1) }}</span>
        <span class="td-mono">max {{ history.max === null ? '—' : history.max.toFixed(1) }}</span>
      </div>
    </template>
    <!-- 无可用 CI（数据不可用 / 陈旧）：如实空态，不给编造走势（TC-11） -->
    <p v-else class="trend-empty">无可用 CI 走势（该段数据不可用 / 陈旧，不给编造序列）</p>
  </div>
  <p v-else class="trend-empty">加载中…</p>
</template>

<style scoped>
.trend {
  width: 100%;
}
.plot {
  position: relative;
  height: 58px;
}
.bars {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: flex-end;
  gap: 3px;
}
.bar {
  flex: 1;
  min-width: 0;
  border-radius: 2px 2px 0 0;
}
/* 阈值线:65 / 85(展示用参考线,判级以四项指标为准) */
.thr {
  position: absolute;
  left: 0;
  right: 0;
  border-top: 1px dashed var(--td-component-border);
}
.axis {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 10px;
  color: var(--td-text-color-placeholder);
}
.trend-empty {
  margin: 0;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}

/* ==========================================================================
   响应式（Issue IKP3EV）：手机宽度下把 58px 的走势图略微压低，
   给同屏的告警 / 预测留出纵向空间（柱宽自适应，不改变口径）。断点：560。
   ========================================================================== */
@media (max-width: 560px) {
  .plot {
    height: 48px;
  }
  .bar {
    border-radius: 1px 1px 0 0;
  }
}
</style>
