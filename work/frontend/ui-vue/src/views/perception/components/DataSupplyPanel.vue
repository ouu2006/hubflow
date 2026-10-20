<script setup lang="ts">
// 数据供给 ↔ 需求对照带(Issue #77 三页收敛 · 感知层)。
//
// 业主口径:「感知层 yolo 获取图像数据,将**能获取的数据**和**要用到的数据**都出现在这个感知层上面来」。
// 本卡就是把这两列并排摆出来,中间标出**映射关系与缺口**:
//   · 左列「能获取的数据」= 感知链路实际产出的东西(逐帧检测框 / 轨迹 / 透视标定 / 四项指标);
//   · 右列「要用到的数据」= 下游(判级 / 决策 / 大屏)真正消费的字段(路段级 q / v / k / L_q / x / ci / level);
//   · 中间 = 一条通道 → 一条路段的映射,以及**缺什么、缺在哪一步**。
//
// ⚠️ 口径铁律(违反即不通过):
//   ① 拿不到的字段一律「—」并注明出处,**绝不用前端推算值或设计稿示例值冒充**;
//   ② 三分口径沿用感知页既有纪律:「未导出(服务端无该路)」「读取失败(接口报错)」「无检出(数据为空)」
//      分开显示,失败不得静默成"无检出";
//   ③ 全部 `is_simulated = true`,页面不出现「实测 / 实时 / 现场」。
import { computed } from 'vue'
import { UNAVAILABLE, isStale, type SegmentRecord, type SegmentSourcePair } from '../../../shared/traffic'
import { fmtDur, type ChannelDef, type ChannelState } from './channels'

const props = defineProps<{
  channels: ChannelState[]
  current: ChannelDef
  sourcePair: SegmentSourcePair | null
}>()

/** 当前通道状态 */
const ch = computed<ChannelState | null>(
  () => props.channels.find((c) => c.def.source === props.current.source) ?? null,
)

/** 该通道映射路段的 video 槽位(判级链路真正吃进去的那一份) */
const videoSlot = computed(
  () => props.sourcePair?.slots.find((s) => s.source === 'video')?.record ?? null,
)

/** 状态四分的文字(未接入视频源 / 未导出 / 读取失败 / 已导出),与通道台账同口径 */
const exportState = computed(() => {
  const c = ch.value
  if (!c) return { text: '—', cls: 'out' }
  if (!c.def.hasVideo) return { text: '未接入视频源', cls: 'out' }
  if (c.meta === null) return { text: '未导出', cls: 'out' }
  if (c.detFailed) return { text: '读取失败', cls: 'err' }
  return { text: '已导出', cls: 'ok' }
})

/** 左列:能获取的数据(逐项 + 缺口说明) */
interface SupplyRow {
  name: string
  value: string
  /** 该项是否就绪;false 时 `gap` 说清缺在哪 */
  ok: boolean
  gap?: string
}

const supplyRows = computed<SupplyRow[]>(() => {
  const c = ch.value
  const m = c?.meta ?? null
  const det = c?.det ?? null
  if (c && !c.def.hasVideo) {
    // 未接入视频源(Issue IKLX5Y):不是"未导出"——本路压根还没接视频,四行全空且缺口写清
    return [
      { name: '样本视频帧', value: '—', ok: false, gap: '该通道未接入视频源（路网上已布点，本期留空）' },
      { name: '逐帧检测框 / 轨迹', value: '—', ok: false, gap: '无源可处理' },
      { name: '透视标定(RANGE / RMSE)', value: '—', ok: false, gap: '无源可标定' },
      { name: '四项指标 q / v / k / L_q', value: '—', ok: false, gap: '依赖上三项，当前不可用' },
    ]
  }
  if (!m) {
    return [
      { name: '样本视频帧', value: '—', ok: false, gap: '该通道未导出(服务端无此路)' },
      { name: '逐帧检测框 / 轨迹', value: '—', ok: false, gap: '该通道未导出' },
      { name: '透视标定(RANGE / RMSE)', value: '—', ok: false, gap: '由感知服务 /summary 提供,当前未实现' },
      { name: '四项指标 q / v / k / L_q', value: '—', ok: false, gap: '依赖上两项,当前不可用' },
    ]
  }
  const detTotal = c?.detTotal ?? null
  return [
    {
      name: '样本视频帧',
      value: `${m.width}×${m.height} · ${m.fps} fps · 时长 ${fmtDur(m.duration_s)} · ${m.total_frames} 帧`,
      ok: true,
    },
    {
      name: '逐帧检测框 / 轨迹',
      value: c?.detFailed
        ? '—'
        : `轨迹 ${m.track_total} · 检测框 ${detTotal === null ? '—' : detTotal}`,
      ok: !c?.detFailed,
      gap: c?.detFailed ? 'detections 接口报错(是接口故障,不是"无检出")' : undefined,
    },
    {
      name: '目标检测 / 跟踪模型',
      value: `${m.model} · ${m.backend} · conf ${m.conf_threshold}`,
      ok: true,
    },
    {
      name: '透视标定(RANGE / RMSE)',
      value: '—',
      ok: false,
      gap: '由感知服务 /summary 提供,当前未实现(前端无复算条件)',
    },
    {
      name: '四项指标 q / v / k / L_q',
      value: det ? '经标定折算后进入路段指标(见右列)' : '—',
      ok: false,
      gap: '标定不可用时四项指标不可用;当前右列取自站点包演示基线',
    },
  ]
})

/** 右列:下游要用到的数据(路段级字段;缺失一律「—」) */
interface DemandRow {
  name: string
  unit: string
  value: string
  /** 该字段是否由感知链路直接产出(否则注明实际来源) */
  fromVideo: boolean
  note?: string
}

const slot = computed<SegmentRecord | null>(() => videoSlot.value)

function num(v: number | undefined, digits = 2): string {
  return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—'
}

const demandRows = computed<DemandRow[]>(() => {
  const r = slot.value
  if (!r) {
    return [
      { name: '饱和度 x', unit: '', value: '—', fromVideo: false, note: '该路段无视频链路槽位' },
      { name: '车速 v', unit: 'km/h', value: '—', fromVideo: false },
      { name: '流量 q', unit: '辆/h', value: '—', fromVideo: false },
      { name: '密度 k', unit: '辆/km', value: '—', fromVideo: false },
      { name: '排队长度 L_q', unit: 'm', value: '—', fromVideo: false },
      { name: '拥堵等级 level', unit: '', value: '—', fromVideo: false },
      { name: '拥挤指数 ci', unit: '', value: '—', fromVideo: false },
    ]
  }
  const stale = isStale(r)
  return [
    { name: '饱和度 x', unit: '', value: num(r.x), fromVideo: true },
    { name: '车速 v', unit: 'km/h', value: num(r.v_kmh, 1), fromVideo: true },
    { name: '流量 q', unit: '辆/h', value: num(r.q_vph, 0), fromVideo: true },
    { name: '密度 k', unit: '辆/km', value: num(r.k_vpk, 1), fromVideo: true },
    { name: '排队长度 L_q', unit: 'm', value: num(r.L_q_m, 0), fromVideo: true },
    {
      name: '拥堵等级 level',
      unit: '',
      value: stale ? UNAVAILABLE.name : String(r.level),
      fromVideo: true,
      note: stale ? '数据陈旧(data_age_s > 120s)' : undefined,
    },
    { name: '拥挤指数 ci', unit: '', value: num(r.ci, 1), fromVideo: true },
  ]
})

/** 缺口汇总(两侧一比,说清"缺什么"而不是"缺几项") */
const gaps = computed<string[]>(() => {
  const out: string[] = []
  const c = ch.value
  if (c && !c.def.hasVideo) {
    out.push('该通道未接入视频源(路网上已布点、本期视频留空):检测框 / 轨迹 / 标定 / 四项指标全部不可用')
  } else if (!c?.meta) {
    out.push('该通道样本视频未导出:检测框 / 轨迹 / 标定 / 四项指标全部不可用')
  } else if (c.detFailed) {
    out.push('detections 接口报错:该路检测框不可用(接口故障,非"无检出")')
  }
  if (c?.meta) out.push('透视标定与轨迹质量(SVR / Q / RANGE-RMSE)由感知服务 /summary 提供,当前未实现')
  out.push('路段级四项指标当前取自**站点包演示基线**(预置值 + 抖动),不是感知链路的实测产出')
  return out
})
</script>

<template>
  <section class="td-card supply-card">
    <div class="td-card-head">
      数据供给 ↔ 需求对照 · 通道 {{ current.cid }}（{{ current.source }}）
      <span class="td-head-tag">
        <span class="td-chip" :class="exportState.cls">{{ exportState.text }}</span>
        <span class="td-chip warn">演示数据(模拟)</span>
      </span>
    </div>
    <div class="td-card-body supply-body">
      <!-- 左:能获取的数据 -->
      <div class="sup-col">
        <div class="col-title">能获取的数据 · YOLO 感知链路产出</div>
        <div v-for="r in supplyRows" :key="r.name" class="sup-row" :class="{ bad: !r.ok }">
          <span class="s-name">{{ r.name }}</span>
          <span class="s-val td-mono">{{ r.value }}</span>
          <span v-if="r.gap" class="s-gap">缺:{{ r.gap }}</span>
        </div>
      </div>

      <!-- 中:映射 -->
      <div class="sup-mid">
        <div class="arrow">→</div>
        <div class="map-note">
          通道 {{ current.cid }} → 路段
          <b class="td-mono">{{ current.segmentId }}</b>
          <br />
          {{ current.name }}
        </div>
        <div class="arrow">→</div>
      </div>

      <!-- 右:要用到的数据 -->
      <div class="sup-col">
        <div class="col-title">要用到的数据 · 下游(判级 / 决策 / 大屏)消费字段</div>
        <div v-for="r in demandRows" :key="r.name" class="sup-row">
          <span class="s-name">{{ r.name }}<span v-if="r.unit" class="unit">({{ r.unit }})</span></span>
          <span class="s-val td-num">{{ r.value }}</span>
          <span class="s-tag" :class="r.fromVideo ? 'ok' : 'out'">
            {{ r.fromVideo ? '视频链路槽位' : '无此槽位' }}
          </span>
          <span v-if="r.note" class="s-gap">{{ r.note }}</span>
        </div>
      </div>
    </div>

    <div class="gap-band">
      <span class="gap-title">缺口(如实列出,不用推算值补):</span>
      <span v-for="(g, i) in gaps" :key="i" class="gap-item">{{ g }}</span>
    </div>
  </section>
</template>

<style scoped>
.supply-card {
  flex: 0 0 auto;
  margin: 10px 16px 0;
}
.supply-body {
  display: flex;
  gap: 14px;
  align-items: stretch;
}
.sup-col {
  flex: 1 1 0;
  min-width: 0;
}
.col-title {
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}
.sup-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 3px 0;
  font-size: 11px;
  line-height: 1.7;
  border-bottom: 1px dashed var(--td-component-stroke);
}
.sup-row:last-child {
  border-bottom: none;
}
.s-name {
  flex: 0 0 148px;
  color: var(--td-text-color-secondary);
}
.unit {
  margin-left: 3px;
  font-size: 10px;
  color: var(--td-text-color-placeholder);
}
.s-val {
  flex: 1;
  min-width: 0;
  color: var(--td-text-color-primary);
  word-break: break-word;
}
.sup-row.bad .s-val {
  color: var(--td-text-color-placeholder);
}
.s-gap {
  flex: 0 0 auto;
  max-width: 46%;
  font-size: 10px;
  color: #a06a00;
}
.s-tag {
  flex: 0 0 auto;
  padding: 0 5px;
  border-radius: var(--td-radius-sm);
  font-size: 10px;
}
.s-tag.ok {
  background: var(--td-success-color-1);
  color: #006c45;
}
.s-tag.out {
  background: var(--td-bg-color-secondarycontainer);
  color: var(--td-text-color-placeholder);
}
.sup-mid {
  flex: 0 0 168px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  text-align: center;
}
.arrow {
  font-size: 16px;
  color: var(--td-brand-color);
}
.map-note {
  font-size: 11px;
  line-height: 1.7;
  color: var(--td-text-color-secondary);
}
.gap-band {
  flex: 0 0 auto;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  padding: 7px 12px;
  border-top: 1px solid var(--td-component-stroke);
  font-size: 10px;
  line-height: 1.6;
  color: var(--td-text-color-placeholder);
}
.gap-title {
  color: var(--td-text-color-secondary);
}
.gap-item::before {
  content: '· ';
}

/* ---------- 响应式（Issue IKP3EV） ---------- */
/* ≤900：两侧对照列按整宽折行，中间映射区改成横向一行，不再被压成窄条 */
@media (max-width: 900px) {
  .supply-body {
    flex-wrap: wrap;
    gap: 10px 12px;
  }
  .sup-col {
    flex: 1 1 320px;
  }
  .sup-mid {
    flex: 0 0 100%;
    flex-direction: row;
    justify-content: center;
    gap: 10px;
    text-align: left;
  }
  .td-card-head {
    flex-wrap: wrap;
    row-gap: 2px;
  }
  .td-card-head .td-head-tag {
    margin-left: 0;
  }
}
/* ≤768：缺口说明由 max-width:46% 改为整行（原来半宽会把长缺口挤成竖条） */
@media (max-width: 768px) {
  .s-gap {
    max-width: 100%;
    flex-basis: 100%;
  }
  .sup-row {
    flex-wrap: wrap;
    row-gap: 2px;
  }
  .s-name {
    flex-basis: 120px;
  }
}
/* ≤560：左右两列各占整行；映射区回到纵向，不横向溢出 */
@media (max-width: 560px) {
  .supply-card {
    margin: 10px 10px 0;
  }
  .sup-col {
    flex-basis: 100%;
  }
  .sup-mid {
    flex-direction: column;
    text-align: center;
  }
  .s-name {
    flex: 0 0 108px;
  }
  .s-val {
    flex: 1 1 auto;
  }
  .gap-band {
    padding: 7px 10px;
  }
}
</style>
