<script setup lang="ts">
// 右栏:检测详情(当前通道)。
// ① 头部(通道 + 映射路段 + 状态) ② 累计轨迹按车型分组(first_seen 口径) ③ 轨迹质量与标定(降级)
// ④ 输出字段(该路段 video 槽位) ⑤ 实测回灌孪生(同化门控)。
// 铁律:拿不到的数据一律「—」+ 注明出处;输出字段的陈旧态走灰(UNAVAILABLE),绝不显示成蓝/绿。
import { computed } from 'vue'
import type { PerceptionSummary } from '../../../api/perception'
import { UNAVAILABLE, isStale, type AssimilationSnapshotFull, type SegmentSourcePair } from '../../../shared/traffic'
import { CLASS_COLORS, type VehicleClassKey } from '../../../shared/theme'
import { CLASS_KEYS, CLASS_LABEL, cumClassCounts, fmtDur } from './channels'
import type { ChannelState } from './channels'

const props = defineProps<{
  ch: ChannelState
  summary: PerceptionSummary | null
  summaryUnavailable: boolean
  sourcePair: SegmentSourcePair | null
  assimilation: AssimilationSnapshotFull | null
}>()

const meta = computed(() => props.ch.meta)

const stateChip = computed(() =>
  meta.value ? { text: '已导出', cls: 'ok' } : { text: '未导出', cls: 'out' },
)

const resLine = computed(() => {
  const m = meta.value
  if (!m) return '样本视频未导出 · 无检测数据'
  return `${m.width}×${m.height} · ${m.fps} fps · 时长 ${fmtDur(m.duration_s)} · ${m.total_frames} 帧`
})

const classNames = computed(() => meta.value?.class_names ?? {})
const cum = computed(() => cumClassCounts(props.ch.det, classNames.value))
const classRows = computed(() =>
  CLASS_KEYS.map((k: VehicleClassKey) => ({
    key: k,
    label: CLASS_LABEL[k],
    color: CLASS_COLORS[k],
    count: cum.value.byKey.get(k) ?? 0,
  })),
)

// ---------- 轨迹质量与标定(感知服务提供;当前不可用 → 「—」) ----------
const qualityRows = computed(() => {
  const s = props.summary
  return [
    { k: 'ID 切换占比 SVR', v: s && s.id_switch_svr !== null ? s.id_switch_svr.toFixed(2) : '—' },
    { k: '轨迹质量因子 Q', v: s && s.avg_quality !== null ? s.avg_quality.toFixed(2) : '—' },
    {
      k: '标定控制点 · RANGE',
      v: s && s.calibration ? `${s.calibration.range_px} px · RMSE ${s.calibration.rmse_px} px` : '—',
    },
    { k: '有效标定帧数', v: s && s.pipeline ? String(s.pipeline.frames) : '—' },
  ]
})

// ---------- 输出字段(该路段 source === 'video' 的槽位) ----------
const videoSlot = computed(
  () => props.sourcePair?.slots.find((s) => s.source === 'video') ?? null,
)
const outRecord = computed(() => {
  const slot = videoSlot.value
  return slot && slot.available ? slot.record : null
})
const outStale = computed(() => {
  const r = outRecord.value
  return r ? isStale(r) : false
})

function num(v: number | undefined, digits: number): string {
  return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—'
}

const outRows = computed(() => {
  const r = outRecord.value
  return [
    { k: 'q_vph', u: 'veh/h', v: num(r?.q_vph, 0) },
    { k: 'v_kmh', u: 'km/h', v: num(r?.v_kmh, 1) },
    { k: 'L_q_m', u: 'm', v: num(r?.L_q_m, 0) },
    { k: 'k_vpk', u: 'veh/km/ln', v: num(r?.k_vpk, 1) },
    { k: 'confidence', u: '', v: num(r?.confidence, 2) },
    { k: 'data_age_s', u: 's', v: num(r?.data_age_s, 0) },
  ]
})

// ---------- 实测回灌孪生(同化门控:按 segment_id 找断面记录) ----------
const gate = computed(
  () => props.assimilation?.records.find((r) => r.segment_id === props.ch.def.segmentId) ?? null,
)

/** 命中断面时的展示编号(E-xx);未命中为 null */
const gatePoint = computed(() => {
  const g = gate.value
  return g ? (g.point_code ?? g.point_id) : null
})

const gateState = computed(() => {
  const g = gate.value
  if (!g) {
    return {
      enabled: false,
      point: '—',
      text: '该路段未登记断面 · 不参与回灌',
      reason: `${props.ch.def.segmentId} 在 network.sections 中无断面记录,故无同化记录`,
    }
  }
  if (g.role === 'internal') {
    return {
      enabled: false,
      point: g.point_code ?? g.point_id,
      text: 'internal_not_allowed · 内部断面不允许回灌',
      reason: g.gate_detail ?? g.reason ?? '仅 role=boundary 断面允许回灌(手册门控口径)',
    }
  }
  if (g.enabled) {
    return {
      enabled: true,
      point: g.point_code ?? g.point_id,
      text: '已回灌',
      reason: g.gate_detail ?? `role=boundary · confidence ${g.confidence ?? '—'}`,
    }
  }
  return {
    enabled: false,
    point: g.point_code ?? g.point_id,
    text: '门控未放行 · 未回灌',
    reason: g.gate_detail ?? g.reason ?? g.gate_reason ?? '门控原因未提供',
  }
})
</script>

<template>
  <section class="td-card">
    <div class="td-card-head">
      检测详情
      <span class="td-head-tag">{{ ch.def.cid }} · {{ ch.def.segmentId }}</span>
    </div>
    <div class="td-card-body detail">
      <div class="d-head">
        <div class="d-title">{{ ch.def.cid }} · {{ ch.def.source }}</div>
        <span class="td-chip" :class="stateChip.cls">{{ stateChip.text }}</span>
      </div>
      <div class="d-sub">
        {{ ch.def.segmentId }} {{ ch.def.name }}
        <template v-if="gatePoint"> · 检测断面 {{ gatePoint }}</template>
      </div>
      <div class="d-sub td-mono">{{ resLine }}</div>

      <div class="sep">本帧检测 · 按车型累计</div>
      <template v-if="ch.det">
        <table class="td-table">
          <thead>
            <tr>
              <th>车型</th>
              <th class="num">累计轨迹数</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in classRows" :key="row.key">
              <td>
                <span class="dot" :style="{ background: row.color }" />
                {{ row.label }}
              </td>
              <td class="num">{{ row.count }}</td>
            </tr>
            <tr class="tot">
              <td>总计</td>
              <td class="num">{{ cum.total }}</td>
            </tr>
          </tbody>
        </table>
        <p class="note">
          累计口径 = detections.first_seen 按类别分组(不把逐帧框数累加);非车辆类别
          {{ cum.other }} 类未计入。
        </p>
      </template>
      <p v-else class="note">该通道检测数据不可用 · 样本视频未导出(无 first_seen 可统计)。</p>
      <div class="kv">
        <span class="k">累计越线计数 cnt</span>
        <span class="v td-mono">—</span>
      </div>

      <div class="sep">轨迹质量与标定</div>
      <div class="kv" v-for="row in qualityRows" :key="row.k">
        <span class="k">{{ row.k }}</span>
        <span class="v td-mono">{{ row.v }}</span>
      </div>
      <p v-if="summaryUnavailable" class="note">
        该四项由感知服务提供,当前不可用 → 显示「—」(轨迹质量与标定是模型侧产物,前端不具备复算条件)。
      </p>

      <div class="sep">
        输出 · segments.json
        <span class="td-head-tag">source: video</span>
      </div>
      <template v-if="outRecord">
        <div class="kv" v-for="row in outRows" :key="row.k">
          <span class="k">{{ row.k }}<span v-if="row.u" class="u"> ({{ row.u }})</span></span>
          <span class="v td-mono" :style="outStale ? { color: UNAVAILABLE.color } : {}">{{ row.v }}</span>
        </div>
        <p class="note">
          该路段的视频链路槽位数据;字段与孪生链路逐字段一致,下游判级不按来源分支。
          <template v-if="outStale">当前 data_age 超限 → 该槽位按「数据不可用」(灰)展示。</template>
        </p>
      </template>
      <p v-else class="note">该路段无视频链路数据(仅孪生链路覆盖,或快照接口未起)。</p>

      <div class="sep">
        实测回灌孪生
        <span class="td-head-tag">SUMO calibrator</span>
      </div>
      <button class="td-btn primary reflow" type="button" :disabled="!gateState.enabled">
        {{ gateState.enabled ? `回灌孪生 · ${gateState.point} 已回灌` : '回灌孪生 · 当前断面不可用' }}
      </button>
      <p class="gate-line">{{ gateState.text }}</p>
      <p class="note">reason: {{ gateState.reason }}</p>
      <p class="note">仅 role = boundary 的边界断面允许视频实测回灌;站前内部断面一律不灌。</p>
    </div>
  </section>
</template>

<style scoped>
.detail {
  display: flex;
  flex-direction: column;
}
.d-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.d-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--td-brand-color);
}
.d-head .td-chip {
  margin-left: auto;
}
.d-sub {
  margin-top: 4px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}
.sep {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px 0 6px;
  padding-top: 10px;
  border-top: 1px solid var(--td-component-stroke);
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}
.sep .td-head-tag {
  margin-left: auto;
  font-size: 11px;
  font-weight: 400;
  color: var(--td-text-color-placeholder);
}
.dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 2px;
  margin-right: 6px;
  vertical-align: middle;
}
.td-table .tot td {
  font-weight: 600;
}
.kv {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 3px 0;
  font-size: 12px;
}
.kv .k {
  color: var(--td-text-color-secondary);
}
.kv .k .u {
  color: var(--td-text-color-placeholder);
}
.kv .v {
  margin-left: auto;
  color: var(--td-text-color-primary);
}
.note {
  margin: 6px 0 0;
  font-size: 11px;
  line-height: 1.5;
  color: var(--td-text-color-placeholder);
}
.reflow {
  margin-top: 6px;
  width: 100%;
  height: 30px;
}
.gate-line {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--td-text-color-primary);
}
</style>
