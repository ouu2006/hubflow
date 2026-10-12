<script setup lang="ts">
// 效果对比报表(设计稿 03 底部「效果对比 · 场景切换 (A/B/C)」)。
// 口径(硬性口径 1):三组对照全部是**仿真对照**,不得称实测;数据 is_simulated = true;
//   ② ③ 的差 = 本项目核心机制的举证口("不给每个人此刻最快的那条路",README §9.2)。
// 数据:shared/demoDecision.ts 的 EFFECT_SCENARIOS(三场景)+ ACK_COMPARISON(处置前后三项)。
import { computed, ref } from 'vue'
import { ACK_COMPARISON, EFFECT_SCENARIOS } from '../../../shared/demoDecision'

const picked = ref<string>(EFFECT_SCENARIOS[0]?.key ?? 'peak')
const scenario = computed(() => EFFECT_SCENARIOS.find((s) => s.key === picked.value) ?? EFFECT_SCENARIOS[0]!)
</script>

<template>
  <section class="td-card">
    <div class="td-card-head">
      效果对比 · 场景切换
      <span class="td-seg seg">
        <span
          v-for="s in EFFECT_SCENARIOS"
          :key="s.key"
          class="td-seg-item"
          :class="{ on: s.key === picked }"
          role="button"
          :aria-pressed="s.key === picked"
          @click="picked = s.key"
        >
          {{ s.name }}
        </span>
      </span>
    </div>
    <div class="td-card-body">
      <p class="src">时间窗:{{ scenario.window }} · 来源:仿真对照 · is_simulated = true</p>
      <table class="td-table">
        <thead>
          <tr>
            <th>指标（同场景 · 同时段）</th>
            <th class="num">A · 不推荐</th>
            <th class="num">B · 此刻最快</th>
            <th class="num hl">C · 协同推荐(本方案)</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in scenario.metrics" :key="m.name">
            <td>
              {{ m.name }}<span v-if="m.unit" class="unit">({{ m.unit }})</span>
            </td>
            <td class="num">{{ m.no_guide }}</td>
            <td class="num">{{ m.fastest }}</td>
            <td class="num hl">{{ m.cooperative }}</td>
          </tr>
        </tbody>
      </table>

      <div class="sub">处置前后对比 · {{ ACK_COMPARISON.window }}</div>
      <table class="td-table">
        <thead>
          <tr>
            <th>指标（同场景 · 同时段）</th>
            <th class="num">处置前</th>
            <th class="num hl">处置后</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in ACK_COMPARISON.rows" :key="r.name">
            <td>
              {{ r.name }}<span v-if="r.unit" class="unit">({{ r.unit }})</span>
            </td>
            <td class="num">{{ r.before }}</td>
            <td class="num hl">{{ r.after }}</td>
          </tr>
        </tbody>
      </table>

      <p class="note">演示数据（模拟）· 同一需求输入 · 三组对照 · 效果对比属仿真对照，不得称实测</p>
    </div>
  </section>
</template>

<style scoped>
.seg {
  margin-left: auto;
}
.src {
  margin: 0 0 8px;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
.unit {
  margin-left: 2px;
  color: var(--td-text-color-placeholder);
}
/* 高亮「本方案」列:品牌浅底 = 「当前/已选」语义(硬性口径 4) */
.td-table .hl {
  background: var(--td-brand-color-1);
}
.sub {
  margin: 12px 0 8px;
  padding-left: 8px;
  border-left: 3px solid var(--td-component-border);
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}
.note {
  margin: 10px 0 0;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
</style>
