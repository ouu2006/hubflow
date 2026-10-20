<script setup lang="ts">
// 场景注入面板(Issue #77 决策层「决策可视化」的可调控段之一)。
//
// 口径铁律(违反即不通过):
//   ① **场景注入 ≠ 人工置位**。手册 §:2222 规定管理端人工置位的口子只有 F07 / F08 / F11
//      (交通事故 / 施工管制 / 大型活动);天气(F01)、昼夜(F02)、列车到发(F03)、时段日历(F10)
//      是**环境上下文**,走 `POST /api/traffic/scenario` 这个独立口子。本面板必须写明这一点,
//      不得把两者混称。
//   ② 天气 / 时段为**编造的演示值**,面板头常驻「演示数据(模拟)」。
//   ③ mock 模式:注入后判级 / CI / 建议 / 预测随之重算,面板显示注入前后对照;
//      **真接口模式(traffic.py)**:接口层只更新环境上下文与 derived_factors、**不重算判级 / ci**,
//      所以 effects 如实为空 —— 面板只显示「已注入 / 折算因素」，不伪造等级变化(判级由感知层统一重算)。
import { computed, ref } from 'vue'
import { postTrafficScenario, postTrafficScenarioReset } from '../../../api/traffic'
import type { ScenarioResult, TimeSession, TrafficContext, WeatherCondition } from '../../../shared/traffic'
import { USE_MOCK } from '../../../shared/env'

const props = defineProps<{
  ctx: TrafficContext | null
  segmentId: string
  /** 该站点包的场景预设档(站点包给,一键应用) */
  presets: { key: string; name: string; note: string; factor_ids: string[] }[]
}>()

const emit = defineEmits<{ (e: 'changed'): void }>()

const WEATHERS: WeatherCondition[] = ['晴', '多云', '小雨', '大雨', '大雾', '台风']
const SESSIONS: TimeSession[] = ['早高峰', '平峰', '晚高峰', '夜间']

const weather = ref<WeatherCondition | null>(null)
const session = ref<TimeSession | null>(null)
const demandMult = ref(1.0)
/**
 * 需求倍率是否**被显式调过**。
 * 没调过就**不发** `demand_mult` —— 服务端只在收到该字段时才用它,否则按所选时段的
 * F10 倍率折算(独立审查发现:恒发 `demand_mult: 1.0` 会让「时段」单独点选对判级零效果)。
 */
const demandTouched = ref(false)
const result = ref<ScenarioResult | null>(null)
const msg = ref('')
const busy = ref(false)

/** 当前选中路段在注入前后的判级对照(服务端返回的 effects 里取) */
const effect = computed(() => {
  const e = result.value?.effects.find((x) => x.segment_id === props.segmentId)
  return e ?? null
})

async function apply(): Promise<void> {
  if (busy.value) return
  busy.value = true
  msg.value = ''
  try {
    // 取消选中的芯片发**显式 null**(= 清除该项),不是省略——省略会被服务端当作"不改",
    // 页面显示"没选"而旧值仍在生效(独立审查 Sourcery 提出的口径漏洞)。
    result.value = await postTrafficScenario({
      weather: weather.value,
      session: session.value,
      demand_mult: demandTouched.value ? demandMult.value : undefined,
      segment_id: props.segmentId || undefined,
    })
    msg.value = USE_MOCK
      ? '已注入(服务端重算判级 / CI,演示口径)'
      : '已注入（接口层只更新环境上下文与折算因素；判级由感知层统一重算，接口层不重算；接口层内存态，重启复位）'
    emit('changed')
  } catch (e) {
    msg.value = `注入失败:${e instanceof Error ? e.message : String(e)}`
  } finally {
    busy.value = false
  }
}
async function applyPreset(key: string): Promise<void> {
  // `demand` = 该档要显式注入的需求倍率;不给就是"按所选时段的 F10 倍率折算"(服务端算)
  const map: Record<string, { weather?: WeatherCondition; session?: TimeSession; demand?: number }> = {
    baseline: { weather: '晴', session: '平峰' },
    'rain-peak': { weather: '大雨', session: '晚高峰' },
    'fog-night': { weather: '大雾', session: '夜间' },
    'train-burst': { weather: '多云', session: '平峰', demand: 1.35 },
    'accident-loop': { weather: '多云', session: '早高峰', demand: 1.2 },
  }
  const p = map[key]
  if (!p) return
  weather.value = p.weather ?? null
  session.value = p.session ?? null
  demandTouched.value = p.demand !== undefined
  demandMult.value = p.demand ?? 1.0
  await apply()
}

async function reset(): Promise<void> {
  if (busy.value) return
  busy.value = true
  try {
    await postTrafficScenarioReset()
    weather.value = null
    session.value = null
    demandTouched.value = false
    demandMult.value = 1.0
    result.value = null
    msg.value = '已复位到站点包默认环境'
    emit('changed')
  } catch (e) {
    msg.value = `复位失败:${e instanceof Error ? e.message : String(e)}`
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="sec">
    <div class="sec-head">
      可调控 · 场景注入(环境侧)
      <span class="td-chip warn">演示数据(模拟)</span>
      <span class="sec-tag">与「人工置位」是两个口子</span>
    </div>

    <p class="note">
      注入的是**环境上下文**(F01 天气 / F02 昼夜 / F03 列车到发 / F10 时段日历);
      事故 / 管制 / 大型活动(F07 / F08 / F11)走「处置队列」视图里的人工置位口子。
    </p>

    <!-- 预设档(站点包给) -->
    <div class="chips">
      <span
        v-for="p in presets"
        :key="p.key"
        class="td-chip pick"
        role="button"
        :title="p.note"
        @click="applyPreset(p.key)"
      >
        {{ p.name }}
        <template v-if="p.factor_ids.length > 0">（{{ p.factor_ids.join('+') }}）</template>
      </span>
    </div>

    <!-- 逐项调 -->
    <div class="ctl-row">
      <span class="ctl-k">天气</span>
      <span class="chips">
        <span
          v-for="w in WEATHERS"
          :key="w"
          class="td-chip pick"
          :class="{ on: weather === w }"
          role="button"
          :aria-pressed="weather === w"
          @click="weather = weather === w ? null : w"
        >
          {{ w }}
        </span>
      </span>
    </div>
    <div class="ctl-row">
      <span class="ctl-k">时段</span>
      <span class="chips">
        <span
          v-for="s in SESSIONS"
          :key="s"
          class="td-chip pick"
          :class="{ on: session === s }"
          role="button"
          :aria-pressed="session === s"
          @click="session = session === s ? null : s"
        >
          {{ s }}
        </span>
      </span>
    </div>
    <div class="ctl-row">
      <span class="ctl-k">需求倍率</span>
      <input
        v-model.number="demandMult"
        class="range"
        type="range"
        min="0.4"
        max="2"
        step="0.05"
        @input="demandTouched = true"
      />
      <span class="ctl-v td-num">×{{ demandMult.toFixed(2) }}</span>
      <span class="ctl-tag" :class="{ on: demandTouched }">
        {{ demandTouched ? '已手动指定' : '跟随所选时段' }}
      </span>
    </div>

    <div class="btn-row">
      <button type="button" class="td-btn primary" :disabled="busy" @click="apply">
        {{ USE_MOCK ? '注入并重算' : '注入环境上下文' }}
      </button>
      <button type="button" class="td-btn" :disabled="busy" @click="reset">复位环境</button>
      <span class="note inline">
        当前环境:{{ ctx ? `${ctx.weather.condition ?? '天气未接入'} · ${ctx.time.session}` : '—' }}
        <template v-if="ctx">（{{ ctx.injected ? '已注入' : '站点包默认' }}）</template>
      </span>
    </div>

    <!-- 注入前后对照(服务端返回,前端不算);真接口模式 effects 如实为空 → 只显示折算因素 -->
    <div v-if="effect" class="cmp">
      <span class="cmp-k">本路段对照(基线口径,不含快照抖动)</span>
      <span class="cmp-v">
        判级 <b>{{ effect.level_before }} → {{ effect.level_after }}</b>
        <span class="sep">·</span>
        饱和度 <b class="td-num">{{ effect.x_before }} → {{ effect.x_after }}</b>
      </span>
    </div>
    <p v-else-if="result" class="note msg">
      {{ result.effects_note ?? '接口层未返回注入前后判级对照（判级由感知层统一重算，前端不自己算）' }}
    </p>
    <p v-if="result" class="note msg">
      折算环境因素:
      <b>{{ result.factors.map((f) => `${f.factor_id} ${f.name} ×${f.multiplier}`).join('；') || '无（当前环境不产生 F01/F02/F03/F10）' }}</b>
    </p>
    <p v-if="msg" class="note msg">{{ msg }}</p>
  </section>
</template>

<style scoped>
.sec {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 0;
  border-bottom: 1px solid var(--td-component-stroke);
}
.sec-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}
.sec-tag {
  margin-left: auto;
  font-size: 11px;
  font-weight: 400;
  color: var(--td-text-color-placeholder);
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.pick {
  cursor: pointer;
}
.ctl-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ctl-k {
  flex: 0 0 60px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.ctl-v {
  font-size: 11px;
  color: var(--td-text-color-primary);
  min-width: 52px;
}
/* 需求倍率的来源标签:未手动指定 = 跟随所选时段的 F10 倍率(服务端折算) */
.ctl-tag {
  padding: 0 5px;
  border-radius: var(--td-radius-sm);
  font-size: 10px;
  white-space: nowrap;
  background: var(--td-bg-color-secondarycontainer);
  color: var(--td-text-color-placeholder);
}
.ctl-tag.on {
  background: var(--td-brand-color-1);
  color: var(--td-brand-color);
}
.range {
  flex: 1;
  min-width: 0;
  accent-color: var(--td-brand-color);
}
.btn-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.note {
  margin: 0;
  font-size: 11px;
  line-height: 1.6;
  color: var(--td-text-color-placeholder);
}
.note.inline {
  flex: 1;
  min-width: 0;
}
.msg {
  color: var(--td-text-color-secondary);
}
.cmp {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 6px 9px;
  border-radius: var(--td-radius-sm);
  background: var(--td-brand-color-1);
  font-size: 11px;
}
.cmp-k {
  color: var(--td-text-color-secondary);
}
.cmp-v {
  color: var(--td-text-color-primary);
}
.sep {
  color: var(--td-text-color-placeholder);
}

/* ---------- 响应式（Issue IKP3EV） ---------- */
/* ≤900:逐项调控行(天气 / 时段 / 需求倍率)允许换行,滑杆独占一行;
   注入前后对照条同样换行,不撑破卡片 */
@media (max-width: 900px) {
  .ctl-row {
    flex-wrap: wrap;
    gap: 6px;
  }
  .ctl-k {
    flex: 0 0 56px;
  }
  .ctl-row .range {
    flex: 1 1 100%;
  }
  .cmp {
    flex-wrap: wrap;
    gap: 4px 8px;
  }
  .sec-tag {
    margin-left: 0;
  }
}
/* ≤560:按钮触摸高度 32px;来源标签 / 当前环境说明整行换行 */
@media (max-width: 560px) {
  .sec-head {
    font-size: 11px;
  }
  .btn-row .td-btn {
    height: 32px;
  }
  .ctl-k {
    flex: 0 0 48px;
  }
  .note.inline {
    flex: 1 1 100%;
  }
  .range {
    width: 100%;
  }
}
</style>
