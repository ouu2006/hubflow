<script setup lang="ts">
// CI 色阶条(展示档位):色标复用四级色阶(ciGradientCss),刻度 = CI_BANDS(0/25/50/75/100)。
// 灰 #8B8B8B 不参与色阶——灰只表示「数据不可用」,由父级另起一行说明(手册 §6.2 语义分工)。
import { CI_BANDS, ciGradientCss } from '../../../shared/traffic'
</script>

<template>
  <div class="ci-scale">
    <div class="ramp" :style="{ background: ciGradientCss() }" />
    <div class="ticks">
      <span v-for="b in CI_BANDS" :key="b" class="tick">{{ b }}</span>
    </div>
  </div>
</template>

<style scoped>
.ci-scale {
  width: 100%;
}
.ramp {
  height: 12px;
  border-radius: var(--td-radius-sm);
  border: 1px solid var(--td-component-stroke);
}
.ticks {
  display: flex;
  justify-content: space-between;
  margin-top: 3px;
  font-size: 10px;
  color: var(--td-text-color-placeholder);
  font-family: var(--td-font-family-mono);
}
</style>
