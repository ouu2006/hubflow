<script setup lang="ts">
// 场景注入面板(Issue #77 决策层「决策可视化」的可调控段之一)。
//
// 口径铁律(违反即不通过):
//   ① **场景注入 ≠ 人工置位**。手册 §:2222 规定管理端人工置位的口子只有 F07 / F08 / F11
//      (交通事故 / 施工管制 / 大型活动);天气(F01)、昼夜(F02)、列车到发(F03)、时段日历(F10)
//      是**环境上下文**,走 `POST /api/traffic/scenario` 这个独立口子。本面板必须写明这一点,
//      不得把两者混称。
//   ② 天气 / 时段为**编造的演示值**,面板头常驻「演示数据(模拟)」。
//   ③ 注入后判级 / CI / 建议 / 预测随之重算(服务端同一条重算路径),面板显示注入前后对照,
//      对照数值来自服务端返回,前端不自己算。
import { computed, ref } from 'vue'
import { postTrafficScenario, postTrafficScenarioReset } from '../../../api/traffic'
import type { ScenarioResult, TimeSession, TrafficContext, WeatherCondition } from '../../../shared/traffic'

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
    result.value = await postTrafficScenario({
      ...(weather.value ? { weather: weather.value } : {}),
      ...(session.value ? { session: session.value } : {}),
      demand_mult: demandMult.value,
      segment_id: props.segmentId || undefined,
    })
    msg.value = '已注入(服务端重算判级 / CI,演示口径)'
    emit('changed')
  } catch (e) {
    msg.value = `注入失败:${e instanceof Error ? e.message : String(e)}`
  } finally {
    busy.value = false
  }
}

async function applyPreset(key: string): Promise<void> {
  const map: Record<string, { weather?: WeatherCondition; session?: TimeSession; demand_mult: number }> = {
    baseline: { weather: '晴', session: '平峰', demand_mult: 1.0 },
    'rain-peak': { weather: '大雨', session: '晚高峰', demand_mult: 1.15 },
    'fog-night': { weather: '大雾', session: '夜间', demand_mult: 1.0 },
    'train-burst': { weather: '多云', session: '平峰', demand_mult: 1.35 },
    'accident-loop': { weather: '多云', session: '早高峰', demand_mult: 1.2 },
  }
  const p = map[key]
  if (!p) return
  weather.value = p.weather ?? null
  session.value = p.session ?? null
  demandMult.value = p.demand_mult
  await apply()
}

async function reset(): Promise<void> {
  if (busy.value) return
  busy.value = true
  try {
    await postTrafficScenarioReset()
    weather.value = null
    session.value = null
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
      <input v-model.number="demandMult" class="range" type="range" min="0.4" max="2" step="0.05" />
      <span class="ctl-v td-num">×{{ demandMult.toFixed(2) }}</span>
    </div>

    <div class="btn-row">
      <button type="button" class="td-btn primary" :disabled="busy" @click="apply">注入并重算</button>
      <button type="button" class="td-btn" :disabled="busy" @click="reset">复位环境</button>
      <span class="note inline">
        当前环境:{{ ctx ? `${ctx.weather.condition} · ${ctx.time.session}` : '—' }}
        <template v-if="ctx">（{{ ctx.injected ? '已注入' : '站点包默认' }}）</template>
      </span>
    </div>

    <!-- 注入前后对照(服务端返回,前端不算) -->
    <div v-if="effect" class="cmp">
      <span class="cmp-k">本路段对照(基线口径,不含快照抖动)</span>
      <span class="cmp-v">
        判级 <b>{{ effect.level_before }} → {{ effect.level_after }}</b>
        <span class="sep">·</span>
        饱和度 <b class="td-num">{{ effect.x_before }} → {{ effect.x_after }}</b>
      </span>
    </div>
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
</style>
