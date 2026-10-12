<script setup lang="ts">
// 右栏 ② · 预测 · 时域外推(设计稿 03)。
// 口径:一期只做 L0 基线,**仅时域外推**;不出现任何预测精度数字(硬性口径 1 / 手册 §11.2)。
// 数据:GET /api/traffic/predict?segment_id=&h=15|30|60,取三档同屏。
import { computed, onMounted, ref, watch } from 'vue'
import { getTrafficPredict } from '../../../api/traffic'
import type { PredictPoint } from '../../../shared/traffic'
import LevelBadge from '../../dashboard/components/LevelBadge.vue'

const props = defineProps<{ segmentId: string }>()

const points = ref<PredictPoint[]>([])

async function load(): Promise<void> {
  points.value = []
  if (!props.segmentId) return
  try {
    const [a, b, c] = await Promise.all([
      getTrafficPredict(props.segmentId, 15),
      getTrafficPredict(props.segmentId, 30),
      getTrafficPredict(props.segmentId, 60),
    ])
    // 三档去重后按 h 升序展示(h 为 15/30/60)
    const byH = new Map<number, PredictPoint>()
    for (const r of [a, b, c]) for (const p of r.points) byH.set(p.h, p)
    points.value = [15, 30, 60]
      .map((h) => byH.get(h))
      .filter((p): p is PredictPoint => p !== undefined)
  } catch {
    points.value = []
  }
}

/** ± 号:正 = 预计变差,负 = 预计缓解(中性色,不引入第四色轴) */
function signed(v: number): string {
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}`
}

const hasData = computed(() => points.value.length > 0)

onMounted(() => {
  void load()
})

watch(
  () => props.segmentId,
  () => {
    void load()
  },
)
</script>

<template>
  <section class="td-card">
    <div class="td-card-head">
      预测 · 时域外推
      <span class="td-head-tag">L0 基线</span>
    </div>
    <div class="td-card-body">
      <div v-for="p in points" :key="p.h" class="prow">
        <span class="ph td-mono">h{{ p.h }}</span>
        <span class="pl">CI</span>
        <span class="pd td-num">{{ signed(p.delta_ci) }}</span>
        <span class="pv td-num">{{ p.ci.toFixed(1) }}</span>
        <LevelBadge :level="p.level" :name="p.level_name" />
      </div>
      <p v-if="!hasData" class="empty">—</p>
      <p class="note">仅时域外推 · 一期不对外报预测精度数字</p>
    </div>
  </section>
</template>

<style scoped>
.prow {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 0;
  border-bottom: 1px solid var(--td-component-stroke);
}
.prow:last-of-type {
  border-bottom: none;
}
.ph {
  width: 30px;
  font-size: 12px;
  color: var(--td-text-color-primary);
}
.pl {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
.pd {
  width: 48px;
  text-align: right;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}
.pv {
  width: 48px;
  text-align: right;
  font-size: 12px;
  color: var(--td-text-color-primary);
}
.note {
  margin: 6px 0 0;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
.empty {
  margin: 0;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}
</style>
