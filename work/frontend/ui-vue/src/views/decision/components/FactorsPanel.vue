<script setup lang="ts">
// 右栏 ① · 因素与预测(人工置位段)。
// 依据:手册第 19 章「管理端人工置位口子」= F07 事故/故障车、F08 施工/临时管制、F11 大型活动,
//   与 shared/demoDecision.ts 的 MANUAL_FACTOR_PRESETS 同一份清单(三行)。
// 口径:置位走 POST /api/traffic/factors;mock 模式在 mock 内存态里生效并重算判级(演示行为),
//   真接口模式(traffic.py)只登记因素状态、**不重算判级**(判级由感知层统一重算)——
//   两种模式的文案必须分开说,不能把"已登记"说成"判级已变";
//   当前是否已置位以 GET /api/traffic/factors?segment_id= 为准(不靠纯本地态,免得刷新后说假话);
//   "已置位"开关用**品牌蓝**(「当前生效」语义)——不用成功绿,避免与等级色(畅通绿 #2BA471)撞车(硬性口径 4)。
import { onMounted, reactive, ref, watch } from 'vue'
import { getTrafficFactors, postTrafficFactor, postTrafficFactorReset } from '../../../api/traffic'
import { MANUAL_FACTOR_PRESETS } from '../../../shared/demoDecision'
import { MEMORY_STATE_LABEL, USE_MOCK } from '../../../shared/env'

const props = defineProps<{ segmentId: string }>()
const emit = defineEmits<{ (e: 'changed'): void }>()

const placed = reactive<Record<string, boolean>>({})
const msg = ref('')
const busy = ref(false)

/** 合成下限(设计稿注):展示口径,阈值真源见 stations/thresholds.json */
const SYNTH_FLOOR = '合成下限 40%'

async function load(): Promise<void> {
  for (const p of MANUAL_FACTOR_PRESETS) placed[p.factor_id] = false
  if (!props.segmentId) return
  try {
    const res = await getTrafficFactors(props.segmentId)
    const ids = new Set(res.factors.map((f) => f.factor_id))
    for (const p of MANUAL_FACTOR_PRESETS) placed[p.factor_id] = ids.has(p.factor_id)
  } catch {
    /* 接口层未起:保持未置位,不编造 */
  }
}

async function apply(factorId: string): Promise<void> {
  const preset = MANUAL_FACTOR_PRESETS.find((p) => p.factor_id === factorId)
  if (!preset || !props.segmentId || busy.value) return
  busy.value = true
  try {
    const r = await postTrafficFactor({
      segment_id: props.segmentId,
      factor_id: preset.factor_id,
      name: preset.name,
      target: preset.target,
      multiplier: preset.multiplier,
    })
    msg.value =
      r.level_recomputed === false
        ? `已置位 ${preset.factor_id} → ${props.segmentId}（接口层内存态，重启复位）；只登记因素状态，判级由感知层统一重算、接口层不重算`
        : `已置位 ${preset.factor_id} → ${props.segmentId} 判级「${r.level_name}」(${MEMORY_STATE_LABEL},60 分钟后自动过期)`
    emit('changed')
    await load()
  } catch {
    msg.value = USE_MOCK ? '置位失败(mock 中间件未起?)' : '置位失败(接口层未起? 先启动 traffic.py)'
  } finally {
    busy.value = false
  }
}

function toggle(factorId: string): void {
  if (placed[factorId]) {
    msg.value = '单条撤销请用下方「复位」（当前只提供整体复位口子）'
    return
  }
  void apply(factorId)
}

async function reset(): Promise<void> {
  if (busy.value) return
  busy.value = true
  try {
    await postTrafficFactorReset()
    msg.value = '已清空全部人工置位'
    emit('changed')
    await load()
  } catch {
    msg.value = '复位失败(接口层未起?)'
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  void load()
})

watch(
  () => props.segmentId,
  () => {
    msg.value = ''
    void load()
  },
)
</script>

<template>
  <section class="td-card">
    <div class="td-card-head">
      因素与预测
      <span class="td-head-tag td-mono">{{ segmentId || '—' }}</span>
    </div>
    <div class="td-card-body">
      <div class="sub">
        <span>人工置位 · 可置位</span>
        <span class="dim">{{ SYNTH_FLOOR }}</span>
      </div>
      <div class="rows">
        <div v-for="p in MANUAL_FACTOR_PRESETS" :key="p.factor_id" class="frow" :title="`${p.name} · ${p.note}`">
          <span class="fid td-mono">{{ p.factor_id }}</span>
          <span class="fname">{{ p.name }}</span>
          <button
            type="button"
            class="sw"
            :class="{ on: placed[p.factor_id] }"
            :disabled="busy || !segmentId"
            @click="toggle(p.factor_id)"
          >
            {{ placed[p.factor_id] ? '已置位' : '未置位' }}
          </button>
        </div>
      </div>
      <div class="foot-row">
        <button type="button" class="td-btn sm" :disabled="busy || !segmentId" @click="reset">复位</button>
        <span class="dim">{{ MEMORY_STATE_LABEL }}</span>
      </div>
      <p v-if="msg" class="msg">{{ msg }}</p>
    </div>
  </section>
</template>

<style scoped>
.sub {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: var(--td-text-color-secondary);
  margin-bottom: 6px;
}
.rows {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.frow {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.fid {
  color: var(--td-text-color-placeholder);
}
.fname {
  flex: 1;
  min-width: 0;
  color: var(--td-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 开关:未置位中性;已置位 = 品牌蓝实心 + 反白文字(硬约束①) */
.sw {
  height: 22px;
  padding: 0 9px;
  font-size: 11px;
  border-radius: var(--td-radius-sm);
  border: 1px solid var(--td-component-border);
  background: var(--td-bg-color-secondarycontainer);
  color: var(--td-text-color-secondary);
  cursor: pointer;
  white-space: nowrap;
}
.sw.on {
  background: var(--td-brand-color);
  border-color: var(--td-brand-color);
  color: var(--td-text-color-anti);
}
.sw:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.foot-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}
.dim {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
.msg {
  margin: 6px 0 0;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
</style>
