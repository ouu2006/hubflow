<script setup lang="ts">
// 右栏 ③ · 数据同化 · 断面门控(设计稿 03)。
// 口径:门控铁律 = **仅 role=boundary(边界)断面允许视频实测回灌孪生**;
//   内部断面恒为 assimilating=false(reason = internal_not_allowed),不是"门控中",是制度上不允许。
// 数据:GET /api/traffic/assimilation(AssimilationSnapshotFull,带 role / 断面编号 / 计数)。
import { computed, onMounted, ref } from 'vue'
import { getTrafficAssimilationFull } from '../../../api/traffic'
import type { AssimilationRecordV2, AssimilationSnapshotFull } from '../../../shared/traffic'

const snap = ref<AssimilationSnapshotFull | null>(null)

async function load(): Promise<void> {
  try {
    snap.value = await getTrafficAssimilationFull()
  } catch {
    snap.value = null // 显式空态:接口未起,显示「—」不编造
  }
}

type GateState = '已回灌' | '门控中' | '不回灌'

const GLYPH: Record<GateState, string> = { 已回灌: '●', 门控中: '◐', 不回灌: '○' }

function stateOf(r: AssimilationRecordV2): GateState {
  if (r.enabled) return '已回灌'
  if (r.role === 'internal' || r.reason === 'internal_not_allowed') return '不回灌'
  return '门控中'
}

function descOf(r: AssimilationRecordV2): string {
  if (r.enabled) {
    const f = r.flow_dev_pct
    const s = r.speed_dev_pct
    return `视频实测回灌孪生 · dev ${f ?? '—'}% / ${s ?? '—'}%`
  }
  if (stateOf(r) === '不回灌') return `${r.reason ?? 'internal_not_allowed'} · 因为 assimilating=false`
  return r.gate_detail ?? '—'
}

const counts = computed(() => snap.value?.counts ?? { boundary: 0, internal: 0 })

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="td-card">
    <div class="td-card-head">
      数据同化 · 断面门控
      <span class="td-head-tag td-num">边界 {{ counts.boundary }} / 内部 {{ counts.internal }}</span>
    </div>
    <div class="td-card-body">
      <div v-for="r in snap?.records ?? []" :key="r.point_id" class="arow">
        <div class="atop">
          <span class="acode td-mono">{{ r.point_code ?? r.point_id }}</span>
          <span class="aname">{{ r.name ?? r.segment_id }}</span>
          <span class="td-chip astate"><i class="gt">{{ GLYPH[stateOf(r)] }}</i>{{ stateOf(r) }}</span>
        </div>
        <div class="adesc">{{ descOf(r) }}</div>
      </div>
      <p v-if="!snap" class="empty">—</p>
      <p class="note">仅 role=boundary(边界)断面允许视频实测回灌孪生</p>
    </div>
  </section>
</template>

<style scoped>
.arow {
  padding: 5px 0;
  border-bottom: 1px solid var(--td-component-stroke);
}
.arow:last-of-type {
  border-bottom: none;
}
.atop {
  display: flex;
  align-items: center;
  gap: 8px;
}
.acode {
  font-size: 12px;
  color: var(--td-text-color-primary);
}
.aname {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  color: var(--td-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.astate .gt {
  font-style: normal;
  font-size: 9px;
}
.adesc {
  margin-top: 2px;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
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
