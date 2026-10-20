<script setup lang="ts">
// 中栏下部:框与线的语义(车型框色图例 + 越线计数线语义 + 输出口径)。
// 车型框色与等级四级色解耦(手册 §6.2);画面区不出现等级色。
import { CLASS_COLORS } from '../../../shared/theme'
import { CLASS_KEYS, CLASS_LABEL, COUNT_LINE_POS } from './channels'

const legend = CLASS_KEYS.map((k) => ({ key: k, label: CLASS_LABEL[k], color: CLASS_COLORS[k] }))
const lineNote = `虚线 = 越线计数线(line_position = ${COUNT_LINE_POS},归一化画面高度)`
</script>

<template>
  <section class="td-card">
    <div class="td-card-head">
      框与线的语义
      <span class="td-head-tag">检测输出</span>
    </div>
    <div class="td-card-body">
      <div class="legend">
        <span v-for="l in legend" :key="l.key" class="lg">
          <i class="dot" :style="{ background: l.color }" />
          {{ l.label }}
        </span>
      </div>
      <p class="line">车型框色与路况等级四级色<strong>解耦</strong>;画面区不使用等级色(手册 §6.2)。</p>
      <p class="line">{{ lineNote }} · 框顶标签 = 类别 · 置信度</p>
      <p class="line">
        输出口径:检测框为<strong>抽帧</strong>结果,非实时流;越线计数由感知服务提供,当前未提供 → 格内标「未提供」。
      </p>
    </div>
  </section>
</template>

<style scoped>
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  font-size: 12px;
}
.lg {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--td-text-color-primary);
}
.dot {
  width: 9px;
  height: 9px;
  border-radius: 2px;
  display: inline-block;
}
.line {
  margin: 8px 0 0;
  font-size: 11px;
  line-height: 1.55;
  color: var(--td-text-color-secondary);
}
.line strong {
  color: var(--td-text-color-primary);
}

/* ---------- 响应式（Issue IKP3EV） ---------- */
/* ≤768：图例与长句按整宽折行，不产生横向溢出 */
@media (max-width: 768px) {
  .legend {
    gap: 10px 14px;
  }
  .line {
    overflow-wrap: anywhere;
  }
  .td-card-head {
    flex-wrap: wrap;
  }
  .td-card-head .td-head-tag {
    margin-left: 0;
  }
}
</style>
