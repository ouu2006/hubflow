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
import type { ReportCompare, ReportCompareRow } from '../../../shared/traffic'
import { USE_MOCK } from '../../../shared/env'

const picked = ref<string>(EFFECT_SCENARIOS[0]?.key ?? 'peak')
const scenario = computed(() => EFFECT_SCENARIOS.find((s) => s.key === picked.value) ?? EFFECT_SCENARIOS[0]!)

/** 接口报表(rows 为空 = 接口层无报表产物,页面如实标注) */
const report = ref<ReportCompare | null>(null)
const reportError = ref('')
const reportRows = computed<ReportCompareRow[]>(() => report.value?.rows ?? [])

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
      <!-- 接口报表(TC-09 已接入：端引擎 --compare 三组对照产物，只读展示) -->
      <p v-if="USE_MOCK" class="src">
        mock 模式：接口层报表端点 GET /api/traffic/report/compare 未实现（404）；下方 A/B/C 为前端演示脚本，不是接口数据。
      </p>
      <p v-else-if="reportError" class="src warn">{{ reportError }}</p>
      <template v-else-if="report">
        <p class="src">
          报表来源:接口 GET /api/traffic/report/compare
          <template v-if="report.source"> · 来源层 {{ report.source }}</template>
          · rows {{ reportRows.length }} 条 · is_simulated = true
        </p>
        <p v-if="report.source_note" class="src">{{ report.source_note }}</p>
        <p v-if="report.window" class="src">
          时间窗:基准 {{ report.window.base_ts ?? '—' }} · 窗口 {{ report.window.window_sec }} s
          · 车辆 {{ report.window.vehicle_count }} · OD {{ report.window.od_count }}
          · 种子 {{ report.window.seed }} · 站点 {{ report.window.site_id }}
        </p>
        <div v-if="reportRows.length > 0" class="tbl-wrap">
          <table class="td-table">
            <thead>
              <tr>
                <th>指标（同拓扑 · 同输入 · 同车辆群）</th>
                <th v-for="row in reportRows" :key="row.group" class="num" :class="{ hl: row.group === 'cooperative' }">
                  {{ row.label }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>需求车辆（attempted）</td>
                <td v-for="row in reportRows" :key="row.group" class="num">{{ row.attempted ?? '—' }}</td>
              </tr>
              <tr>
                <td>成功准入（inserted）</td>
                <td v-for="row in reportRows" :key="row.group" class="num">{{ row.inserted ?? '—' }}</td>
              </tr>
              <tr>
                <td>窗口内完成（completed）</td>
                <td v-for="row in reportRows" :key="row.group" class="num">{{ row.completed ?? '—' }}</td>
              </tr>
              <tr>
                <td>仍在途（in_transit）</td>
                <td v-for="row in reportRows" :key="row.group" class="num">{{ row.in_transit ?? '—' }}</td>
              </tr>
              <tr>
                <td>未准入（not_entered）</td>
                <td v-for="row in reportRows" :key="row.group" class="num">{{ row.not_entered ?? '—' }}</td>
              </tr>
              <tr>
                <td>橙 / 红路段数</td>
                <td v-for="row in reportRows" :key="row.group" class="num">{{ row.orange_red_segment_count }}</td>
              </tr>
              <tr>
                <td>车辆口径总行程（辆·秒）</td>
                <td v-for="row in reportRows" :key="row.group" class="num">{{ row.total_travel_time_s ?? '—' }}</td>
              </tr>
              <tr>
                <td>网络口径总行程（辆·秒）</td>
                <td v-for="row in reportRows" :key="row.group" class="num">{{ row.network_total_time_s ?? '—' }}</td>
              </tr>
              <tr>
                <td>最大 ETA 增量（秒）</td>
                <td v-for="row in reportRows" :key="row.group" class="num">{{ row.max_eta_increase_s ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="report.tc17" class="src">
          TC-17 三项判定（引擎侧，只读透传）：
          {{ report.tc17.passed === true ? '通过' : report.tc17.passed === false ? '未通过' : '—' }}
          · 判据数值见接口响应 criteria 字段
        </p>
        <p v-if="report.note" class="src warn">{{ report.note }}</p>
      </template>
      <p v-else class="src">正在读取接口报表…</p>

      <p v-if="reportRows.length === 0" class="src">
        以下 A/B/C 三组与处置前后对比为<b>前端演示脚本</b>(仿真对照,非接口数据;接口报表无产物时的兜底展示)
      </p>
      <template v-if="reportRows.length === 0">
      <p class="src">时间窗:{{ scenario.window }} · 来源:仿真对照 · is_simulated = true</p>
      <div class="tbl-wrap">
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
      </div>

      <div v-if="reportRows.length === 0" class="sub">处置前后对比 · {{ ACK_COMPARISON.window }}</div>
      <div v-if="reportRows.length === 0" class="tbl-wrap">
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
      </div>
      </template>

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

/* ---------- 响应式（Issue IKP3EV） ---------- */
/* 桌面(≥1181)表格仍是卡片内 100% 宽的普通表格,包一层 .tbl-wrap 不影响视觉。
   ≤768:宽表改为**容器内横向滚动**,表头 nowrap 不挤压指标列,页面无横向滚动。 */
.tbl-wrap {
  min-width: 0;
}
@media (max-width: 900px) {
  .td-card-body {
    padding: 8px 10px;
  }
  .td-card-head {
    flex-wrap: wrap;
    gap: 4px 8px;
  }
}
@media (max-width: 768px) {
  .tbl-wrap {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
  .tbl-wrap .td-table {
    min-width: 520px;
  }
  .seg {
    margin-left: 0;
  }
}
/* ≤560:对比表保持**双向滚动**(横 + 纵),指标列 / 数值列都可读,不撑破页面。 */
@media (max-width: 560px) {
  .tbl-wrap {
    overflow: auto;
    max-height: 60vh;
  }
  .tbl-wrap .td-table {
    min-width: 480px;
  }
  .td-table th,
  .td-table td {
    padding: 6px;
  }
  .sub {
    margin: 10px 0 6px;
  }
}
</style>
