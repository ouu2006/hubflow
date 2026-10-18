<script setup lang="ts">
// 效果对比报表(设计稿 03 底部「效果对比 · 场景切换 (A/B/C)」)。
// 口径(硬性口径 1):三组对照全部是**仿真对照**,不得称实测;数据 is_simulated = true;
//   ② ③ 的差 = 本项目核心机制的举证口("不给每个人此刻最快的那条路",README §9.2)。
// 数据来源分两层,页面分开标注:
//   · 接口层 `GET /api/traffic/report/compare` —— 一期没有「同输入多跑对照」的报表产物,
//     响应 rows 如实为空 + note;页面把接口 note 显式展示(不静默当没有);
//   · 下方 A/B/C 三组与处置前后对比来自 `shared/demoDecision.ts` 的**前端演示脚本**,
//     在接口无报表数据时兜底展示,常驻「仿真对照 · 前端演示脚本」标注(不冒充接口数据)。
import { computed, onMounted, ref } from 'vue'
import { ACK_COMPARISON, EFFECT_SCENARIOS } from '../../../shared/demoDecision'
import { getTrafficReportCompare } from '../../../api/traffic'
import type { ReportCompare } from '../../../shared/traffic'
import { USE_MOCK } from '../../../shared/env'

const picked = ref<string>(EFFECT_SCENARIOS[0]?.key ?? 'peak')
const scenario = computed(() => EFFECT_SCENARIOS.find((s) => s.key === picked.value) ?? EFFECT_SCENARIOS[0]!)

/** 接口报表(rows 为空 = 接口层无报表产物,页面如实标注) */
const report = ref<ReportCompare | null>(null)
const reportError = ref('')
const reportRows = computed<Record<string, unknown>[]>(() => report.value?.rows ?? [])
const reportColumns = computed<string[]>(() => Object.keys(reportRows.value[0] ?? {}))

onMounted(async () => {
  // mock 模式没有 /report/compare(实测 404):不请求、不常驻告警,A/B/C 仍按"前端演示脚本"展示
  if (USE_MOCK) return
  try {
    report.value = await getTrafficReportCompare()
  } catch (e) {
    reportError.value = `效果对比报表接口未取到:${e instanceof Error ? e.message : String(e)}`
  }
})
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
      <!-- 接口报表(真接口):一期无报表产物 → rows 空 + note,如实展示；mock 模式没有该端点 -->
      <p v-if="USE_MOCK" class="src">
        mock 模式：接口层报表端点 GET /api/traffic/report/compare 未实现（404）；下方 A/B/C 为前端演示脚本，不是接口数据。
      </p>
      <p v-else-if="reportError" class="src warn">{{ reportError }}</p>
      <template v-else-if="report">
        <p class="src">
          报表来源:接口 GET /api/traffic/report/compare · rows {{ reportRows.length }} 条 · is_simulated = true
        </p>
        <p v-if="report.note" class="src warn">{{ report.note }}</p>
        <table v-if="reportRows.length > 0" class="td-table">
          <thead>
            <tr>
              <th v-for="key in reportColumns" :key="key">{{ key }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in reportRows" :key="index">
              <td v-for="key in reportColumns" :key="key">{{ row[key] }}</td>
            </tr>
          </tbody>
        </table>
      </template>
      <p v-else class="src">正在读取接口报表…</p>

      <p class="src">
        以下 A/B/C 三组与处置前后对比为<b>前端演示脚本</b>(仿真对照,非接口数据;接口报表未接入前的兜底展示)
      </p>
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
.src.warn {
  color: #a06a00;
  background: var(--td-warning-color-1);
  padding: 5px 8px;
  border-radius: 3px;
  line-height: 1.5;
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
