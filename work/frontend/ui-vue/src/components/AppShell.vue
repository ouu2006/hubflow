<script setup lang="ts">
// 四页共用的应用壳(TDesign Light):顶栏(品牌 + 页签 + 站点 + 数据源 + 快照时间 + 演示角标)+ 页头 + 主体 + 页脚。
// 顶栏骨架在 4 张设计稿里完全一致,抽成一处以免四页各写一套(改一次四处生效)。
// 语义纪律:页签「当前页」与数据源「已选」一律用品牌蓝;等级色不得出现在壳层。
import { computed, useSlots } from 'vue'
import { RouterLink } from 'vue-router'
import { APP_TABS, DEMO_BADGE, SOURCE_ITEMS, type AppTabKey, type SourceMode } from '../shared/nav'
import { formatStamp } from '../shared/traffic'

const props = withDefaults(
  defineProps<{
    /** 当前页签 */
    active: AppTabKey
    /** 站点名(顶栏站点 chip) */
    station?: string
    /** 快照时间(顶栏「快照 …」) */
    ts?: string
    /** 数据源视图:视频链路 / 孪生链路 / 并排(TC-19 展示侧) */
    sourceMode?: SourceMode
    /** 页头标题;为空且无 headRight 插槽时不渲染页头(态势总览用 KPI 条代替页头) */
    title?: string
    /** 页头副题 */
    subtitle?: string
  }>(),
  { station: '肇庆东站', ts: '', sourceMode: 'both', title: '', subtitle: '' },
)

const emit = defineEmits<{ (e: 'update:sourceMode', mode: SourceMode): void }>()

const slots = useSlots()
const showHead = computed(() => props.title !== '' || !!slots.headRight)
</script>

<template>
  <div class="td-page">
    <header class="td-top">
      <div class="td-brand">
        <span class="td-logo">枢</span>
        <span>hubflow</span>
        <span class="td-brand-sub">高铁站外交通疏导智能平台</span>
      </div>
      <nav class="td-tabs">
        <RouterLink
          v-for="t in APP_TABS"
          :key="t.key"
          class="td-tab"
          :class="{ on: t.key === active }"
          :to="t.route"
        >
          {{ t.name }}
        </RouterLink>
      </nav>
      <div class="td-top-right">
        <span class="td-chip">{{ station }}</span>
        <span class="td-seg" role="group" aria-label="数据源视图">
          <span
            v-for="s in SOURCE_ITEMS"
            :key="s.key"
            class="td-seg-item"
            :class="{ on: s.key === sourceMode }"
            :aria-pressed="s.key === sourceMode"
            role="button"
            @click="emit('update:sourceMode', s.key)"
          >
            {{ s.name }}
          </span>
        </span>
        <span class="td-mono" style="font-size: 11px; color: #666">快照 {{ ts ? formatStamp(ts) : '—' }}</span>
        <span class="td-badge-demo">{{ DEMO_BADGE }}</span>
      </div>
    </header>

    <div v-if="showHead" class="td-head">
      <div>
        <div v-if="title" class="td-head-title">{{ title }}</div>
        <div v-if="subtitle" class="td-head-sub">{{ subtitle }}</div>
        <slot name="headExtra" />
      </div>
      <div class="td-head-right">
        <slot name="headRight" />
      </div>
    </div>

    <div class="td-main">
      <slot />
    </div>

    <footer class="td-foot">
      <slot name="foot" />
    </footer>
  </div>
</template>

<style scoped>
.td-main {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
</style>
