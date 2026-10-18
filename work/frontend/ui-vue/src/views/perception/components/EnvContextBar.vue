<script setup lang="ts">
// 环境上下文条(Issue #77 三页收敛 · 感知层第一层)。
//
// 为什么放在感知层:业主口径——感知层放「能获取的数据」,天气 / 时间 / 因地制宜的路况正是环境侧的
// 可获取输入(手册第 19 章因素登记表 F01 天气 / F02 昼夜 / F03 列车到发 / F10 时段日历)。
//
// ⚠️ 口径铁律(违反即不通过):
//   ① **全部是编造的演示值**(真实气象与列车数据拿不到),卡片头必须常驻「演示数据(模拟)」;
//   ② 页面**不出现**「实测 / 实时 / 现场」表述;
//   ③ `derived_factors` 是**当前真实生效**的环境因素(默认态 = 站点包声明的那套环境,
//      `injected = false`;被场景注入改过则 `injected = true`)——两种状态分开显示,
//      不得把"站点包默认环境"说成"注入的"、也不得把观测值说成"未生效"。
import { UNAVAILABLE, type TrafficContext } from '../../../shared/traffic'

defineProps<{
  ctx: TrafficContext | null
  /** 接口未取到时的如实提示(不编造) */
  error?: string
}>()

const TARGET_LABEL: Record<string, string> = {
  c: '通行能力',
  v_f: '畅通速度',
  demand: '需求',
  lanes: '车道数',
  confidence: '检测置信度',
}

function multText(m: number): string {
  return `×${Number.isFinite(m) ? Number(m.toFixed(2)) : '—'}`
}

/** 观测值缺失 → 「—」（不显示成 "null" / 空单位；真接口模式天气观测量本就没有数据源） */
function unitText(value: number | null | undefined, unit: string): string {
  return typeof value === 'number' && Number.isFinite(value) ? `${value} ${unit}` : '—'
}
</script>

<template>
  <section class="td-card env-bar">
    <div class="td-card-head">
      环境上下文 · 天气 / 时间 / 因地制宜的路况因子
      <span class="td-head-tag">
        <span class="td-chip warn">演示数据(模拟)</span>
      </span>
    </div>
    <div class="td-card-body env-body">
      <p v-if="error" class="env-err">{{ error }}</p>
      <template v-else-if="ctx">
        <!-- 天气 -->
        <div class="env-block">
          <div class="env-title">天气</div>
          <div class="env-kv">
            <span class="k">状况</span><span class="v">{{ ctx.weather.condition ?? '—' }}</span>
          </div>
          <div class="env-kv">
            <span class="k">气温</span><span class="v td-num">{{ unitText(ctx.weather.temp_c, '℃') }}</span>
          </div>
          <div class="env-kv">
            <span class="k">湿度</span><span class="v td-num">{{ unitText(ctx.weather.humidity_pct, '%') }}</span>
          </div>
          <div class="env-kv">
            <span class="k">能见度</span><span class="v td-num">{{ unitText(ctx.weather.visibility_km, 'km') }}</span>
          </div>
          <div class="env-kv">
            <span class="k">降水</span><span class="v td-num">{{ unitText(ctx.weather.precip_mm, 'mm') }}</span>
          </div>
          <div class="env-kv">
            <span class="k">风</span><span class="v">{{ ctx.weather.wind ?? '—' }}</span>
          </div>
        </div>

        <!-- 时间 -->
        <div class="env-block">
          <div class="env-title">时间</div>
          <div class="env-kv">
            <span class="k">时刻</span><span class="v td-mono">{{ ctx.time.clock }}</span>
          </div>
          <div class="env-kv">
            <span class="k">时段</span><span class="v">{{ ctx.time.session }}</span>
          </div>
          <div class="env-kv">
            <span class="k">日历</span><span class="v">{{ ctx.time.calendar }}</span>
          </div>
          <div class="env-kv">
            <span class="k">下一班列车</span>
            <span class="v td-mono">{{ ctx.time.next_train ?? '—' }}</span>
          </div>
        </div>

        <!-- 因地制宜:由环境折算出的因素 -->
        <div class="env-block grow">
          <div class="env-title">
            因地制宜的路况因子 · 由上面环境按因素登记表折算
            <span class="td-chip" :class="ctx.injected ? 'ok' : ''">
              {{ ctx.injected ? '已按演示场景注入' : '站点包默认环境' }}
            </span>
          </div>
          <div v-if="ctx.derived_factors.length > 0" class="fac-row">
            <span v-for="f in ctx.derived_factors" :key="f.factor_id" class="fac">
              <b>{{ f.factor_id }}</b> {{ f.name }}
              <span class="sep">·</span>作用{{ TARGET_LABEL[f.target] ?? f.target }}
              <span class="sep">·</span>{{ multText(f.multiplier) }}
            </span>
          </div>
          <p v-else class="env-none">当前环境无折算因素(基准)</p>
          <p v-if="ctx.injected" class="env-none">
            注入的是环境上下文与折算因素；<b>接口层不重算判级 / CI</b>，等级以感知层统一重算结果为准。
          </p>
          <p class="env-sum">{{ ctx.summary }}</p>
        </div>
      </template>
      <p v-else class="env-none">环境上下文加载中…</p>
    </div>
    <div class="env-note">
      天气 / 时段为演示值(模拟),真实来源二期接入(气象接口 / 日出日落 / 铁路部门数据);
      折减系数口径见手册第 19 章因素登记表(F01 天气 / F02 昼夜 / F03 列车到发 / F10 时段日历)。
      <span v-if="ctx"> · {{ ctx.source }}</span>
      <span v-if="ctx && !ctx.injected"> · 数据不可用色 <i class="sw" :style="{ background: UNAVAILABLE.color }" /> 仅表示缺数,不参与本卡</span>
    </div>
  </section>
</template>

<style scoped>
.env-bar {
  flex: 0 0 auto;
  margin: 10px 16px 0;
}
.env-body {
  display: flex;
  gap: 20px;
  align-items: flex-start;
  padding: 8px 12px;
}
.env-block {
  min-width: 0;
}
.env-block.grow {
  flex: 1;
}
.env-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}
/* 天气 / 时间两块各排成两列,把六行压成三行 —— 感知层主体(监控墙)需要竖向空间 */
.env-block:not(.grow) {
  display: grid;
  grid-template-columns: auto auto;
  grid-auto-flow: column;
  grid-template-rows: auto auto auto;
  column-gap: 14px;
  align-content: start;
}
.env-block:not(.grow) .env-title {
  grid-column: 1 / -1;
}
.env-kv {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 11px;
  line-height: 1.7;
}
.env-kv .k {
  color: var(--td-text-color-placeholder);
  min-width: 56px;
}
.env-kv .v {
  color: var(--td-text-color-primary);
}
.fac-row {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.fac {
  padding: 3px 8px;
  border: 1px solid var(--td-component-stroke);
  border-radius: var(--td-radius-sm);
  background: var(--td-bg-color-secondarycontainer);
  font-size: 11px;
  color: var(--td-text-color-primary);
}
.sep {
  color: var(--td-text-color-placeholder);
}
.env-none {
  margin: 0;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
.env-sum {
  margin: 5px 0 0;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.env-err {
  margin: 0;
  font-size: 12px;
  color: #a06a00;
}
.env-note {
  flex: 0 0 auto;
  padding: 5px 12px;
  border-top: 1px solid var(--td-component-stroke);
  font-size: 10px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder);
}
.sw {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  vertical-align: -1px;
}
</style>
