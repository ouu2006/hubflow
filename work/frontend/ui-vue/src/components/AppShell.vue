<script setup lang="ts">
// 四页共用的应用壳(TDesign Light):顶栏(品牌 + 页签 + 站点 + 数据源 + 快照时间 + 演示角标)+ 页头 + 主体 + 页脚。
// 顶栏骨架在 4 张设计稿里完全一致,抽成一处以免四页各写一套(改一次四处生效)。
// 语义纪律:页签「当前页」与数据源「已选」一律用品牌蓝;等级色不得出现在壳层。
import { computed, ref, useSlots } from 'vue'
import { RouterLink } from 'vue-router'
import { APP_TABS, DEMO_BADGE, SOURCE_ITEMS, type AppTabKey, type SourceMode } from '../shared/nav'
import { basemapEnabled, setBasemapEnabled } from '../shared/settings'
import { formatStamp } from '../shared/traffic'
import { TD } from '../shared/theme'
import { activePack, activePackKey, packItems, switchPack } from '../station-packs/index'

const props = withDefaults(
  defineProps<{
    /** 当前页签 */
    active: AppTabKey
    /** 站点名(顶栏站点 chip);缺省取当前站点包 —— 页面拿到 meta 后传 meta.station.name 覆盖 */
    station?: string
    /** 快照时间(顶栏「快照 …」) */
    ts?: string
    /** 数据源视图:视频链路 / 孪生链路 / 并排(TC-19 展示侧)。
     *  **不传(null)= 本页不渲染该控件** —— 只有真按它切换口径的页才给值,
     *  免得出现「点得动、页面一字不变」的死控件(视频感知页本身即视频链路,不给)。 */
    sourceMode?: SourceMode | null
    /** 页头标题;为空且无 headRight 插槽时不渲染页头(态势总览用 KPI 条代替页头) */
    title?: string
    /** 页头副题 */
    subtitle?: string
  }>(),
  { ts: '', sourceMode: null, title: '', subtitle: '' },
)

const emit = defineEmits<{ (e: 'update:sourceMode', mode: SourceMode): void }>()

const slots = useSlots()
const showHead = computed(() => props.title !== '' || !!slots.headRight)

/**
 * 顶栏站点 chip。缺省从**当前站点包**取 —— 注意不能把 `activePack().station.name`
 * 写进 `withDefaults` 的默认值:那个表达式在**模块求值期**就跑了,早于入口
 * (`main.ts` / vite 配置)注入包键,会恒定取到默认包(而不是入口注入的那个)。所以这里惰性取。
 */
const stationName = computed(() => props.station ?? activePack().station.name)

// ---- 线路图切换器(业主 2026-10-14):顶栏直接选包,选完即换整套路网/基线 ----
// ⚠️ 2026-10-16(IKM4XX):本站点包只剩 Z —— **只有一个包时整个控件不渲染**
//    (留一个只有单项的下拉就是死控件)。将来加站(包多起来)它自动回来。
const packList = packItems()
const packKey = ref<string>(activePackKey())
const packOpen = ref(false)

function choosePack(key: string): void {
  packOpen.value = false
  if (key === packKey.value) return
  switchPack(key)
  packKey.value = key
  // 站点包是惰性读的,但页面里不少值(mock 缓存、快照状态)是模块级常量,
  // 最稳妥的演示行为就是整页刷新一次 —— 路网、基线、告警全部从新包现取。
  window.location.reload()
}

// ---- 设置（业主 2026-10-16）：大屏地图的**底图开关** ----
// 开 = 矢量底图（OpenFreeMap，OSM 数据）+ 描出的路网；关 = **只画路网**（原来「示例路网」那个观感），
// 一个底图请求都不发。底图那一层挂掉也不影响路网（见 `MapLibreViewer.vue`：本地兜底样式建图）。
// 与线路图切换器同一套交互：鼠标移出即收起。
const settingsOpen = ref(false)
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
        <!-- 线路图切换器(业主 2026-10-14):选包即换路网,与站点 chip 同源。
             只有一个包时不渲染(IKM4XX)—— 别留只有单项的死控件 -->
        <span v-if="packList.length > 1" class="net-switch" @mouseleave="packOpen = false">
          <button
            type="button"
            class="net-switch-btn"
            :aria-expanded="packOpen"
            aria-haspopup="listbox"
            @click="packOpen = !packOpen"
          >
            <span class="net-switch-label">{{ packList.find((p) => p.key === packKey)?.name ?? stationName }}</span>
            <span class="net-switch-caret">▾</span>
          </button>
          <span v-if="packOpen" class="net-switch-menu" role="listbox" aria-label="切换线路图">
            <button
              v-for="p in packList"
              :key="p.key"
              type="button"
              class="net-switch-item"
              :class="{ on: p.key === packKey }"
              role="option"
              :aria-selected="p.key === packKey"
              @click="choosePack(p.key)"
            >
              <span class="net-switch-name">{{ p.name }}</span>
              <span class="net-switch-note">{{ p.note }}</span>
            </button>
          </span>
        </span>
        <span class="td-chip">{{ stationName }}</span>
        <span v-if="sourceMode !== null && sourceMode !== undefined" class="td-seg" role="group" aria-label="数据源视图">
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
        <!-- 设置：底图开关（业主 2026-10-16）。交互与线路图切换器同款：鼠标移出收起 -->
        <span class="td-settings" @mouseleave="settingsOpen = false">
          <button
            type="button"
            class="td-settings-btn"
            :class="{ on: settingsOpen }"
            :aria-expanded="settingsOpen"
            aria-haspopup="dialog"
            @click="settingsOpen = !settingsOpen"
          >
            设置
          </button>
          <div v-if="settingsOpen" class="td-settings-menu" role="dialog" aria-label="设置">
            <div class="td-set-row">
              <span class="td-set-main">
                <span class="td-set-name">矢量底图</span>
                <span class="td-set-note">
                  开：底图来自 OpenFreeMap（OpenStreetMap 数据）<br>
                  关：只画路网（＝原来的「示例路网」），不发任何底图请求
                </span>
              </span>
              <button
                type="button"
                class="td-switch"
                :class="{ on: basemapEnabled }"
                role="switch"
                :aria-checked="basemapEnabled"
                aria-label="矢量底图开关"
                @click="setBasemapEnabled(!basemapEnabled)"
              >
                <span class="td-switch-knob" />
              </button>
            </div>
            <div class="td-set-foot">底图拉不出来时路网照画，地图内会给「重试」；断网演示可以直接关掉。</div>
          </div>
        </span>
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

/* ---- 线路图切换器(顶栏) ----
   口径:品牌蓝只表示「当前/已选/可操作」(手册 §6.2),菜单项选中态用品牌蓝,
   不引入第二套蓝;等色不出现。 */
.net-switch {
  position: relative;
  display: inline-flex;
}
.net-switch-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: #ffffff;
  border: 1px solid #d9dce1;
  border-radius: 4px;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  color: #1a1a1a;
}
.net-switch-btn:hover {
  border-color: #b9bec6;
}
.net-switch-label {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.net-switch-caret {
  font-size: 9px;
  color: #999999;
}
.net-switch-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  min-width: 260px;
  background: #ffffff;
  border: 1px solid #e3e5e8;
  border-radius: 6px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  padding: 4px;
  z-index: 30;
}
.net-switch-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 7px 10px;
  background: transparent;
  border: 0;
  border-radius: 4px;
  cursor: pointer;
  text-align: left;
  font: inherit;
}
.net-switch-item:hover {
  background: #f2f6ff;
}
.net-switch-item.on {
  background: #eef4ff;
  box-shadow: inset 2px 0 0 v-bind('TD.brand');
}
.net-switch-name {
  font-size: 12px;
  font-weight: 600;
  color: #1a1a1a;
}
.net-switch-item.on .net-switch-name {
  color: v-bind('TD.brand');
}
.net-switch-note {
  font-size: 11px;
  color: #999999;
  line-height: 1.4;
}

/* ---- 设置（顶栏）：目前只有**矢量底图开关**一项 ----
   口径：开关的开态用品牌蓝（「生效中」语义），不引入第二套色；等色不出现。 */
.td-settings {
  position: relative;
  display: inline-flex;
}
.td-settings-btn {
  padding: 4px 10px;
  background: #ffffff;
  border: 1px solid #d9dce1;
  border-radius: 4px;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  color: #1a1a1a;
}
.td-settings-btn:hover {
  border-color: #b9bec6;
}
.td-settings-btn.on {
  border-color: v-bind('TD.brand');
  color: v-bind('TD.brand');
}
.td-settings-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  width: 320px;
  background: #ffffff;
  border: 1px solid #e3e5e8;
  border-radius: 6px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.12);
  padding: 10px 12px;
  z-index: 30;
}
.td-set-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.td-set-main {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.td-set-name {
  font-size: 12px;
  font-weight: 600;
  color: #1a1a1a;
}
.td-set-note {
  font-size: 11px;
  color: #999999;
  line-height: 1.5;
}
.td-set-foot {
  margin-top: 9px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
  font-size: 11px;
  color: #999999;
  line-height: 1.5;
}
/* 开关本体：32×18 的小滑块，开态品牌蓝 */
.td-switch {
  flex: 0 0 auto;
  width: 34px;
  height: 18px;
  padding: 0;
  border: 1px solid #d9dce1;
  border-radius: 9px;
  background: #f0f1f3;
  cursor: pointer;
  position: relative;
  transition: background 0.15s ease, border-color 0.15s ease;
}
.td-switch.on {
  background: v-bind('TD.brand');
  border-color: v-bind('TD.brand');
}
.td-switch-knob {
  position: absolute;
  top: 1px;
  left: 1px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
  transition: left 0.15s ease;
}
.td-switch.on .td-switch-knob {
  left: 17px;
}
</style>
