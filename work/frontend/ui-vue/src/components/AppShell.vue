<script setup lang="ts">
// 四页共用的应用壳(TDesign Light):顶栏(品牌 + 页签 + 站点 + 数据源 + 快照时间 + 演示角标)+ 页头 + 主体 + 页脚。
// 顶栏骨架在 4 张设计稿里完全一致,抽成一处以免四页各写一套(改一次四处生效)。
// 语义纪律:页签「当前页」与数据源「已选」一律用品牌蓝;等级色不得出现在壳层。
import { computed, onBeforeUnmount, onMounted, ref, useSlots } from 'vue'
import { RouterLink } from 'vue-router'
import { backendReachable } from '../api/http'
import { APP_TABS, DEMO_BADGE, SOURCE_ITEMS, type AppTabKey, type SourceMode } from '../shared/nav'
import { USE_MOCK } from '../shared/env'
import {
  basemapEnabled,
  directionsVisible,
  setBasemapEnabled,
  setDirectionsVisible,
} from '../shared/settings'
import { formatStamp } from '../shared/traffic'
import { TD } from '../shared/theme'
import { activePack, activePackKey, onPackChange, packItems } from '../station-packs/index'
import { switchStation } from '../shared/stationSwitch'

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

/** 包键代号：切站时 +1，给"读 activePack() 的 computed"补一个响应式依赖（IKPFR4） */
const packTick = ref(0)

/**
 * 顶栏站点 chip。缺省从**当前站点包**取 —— 注意不能把 `activePack().station.name`
 * 写进 `withDefaults` 的默认值:那个表达式在**模块求值期**就跑了,早于入口
 * (`main.ts` / vite 配置)注入包键,会恒定取到默认包(而不是入口注入的那个)。所以这里惰性取。
 *
 * ⚠️ Issue IKPFR4：`activePack()` 读的是模块级变量，computed 不知道它变了 ——
 *    所以显式读一次 `packTick`（切站时由 `onPackChange` 更新），兜底站名才会跟着换。
 */
const stationName = computed(() => {
  if (props.station !== undefined) return props.station
  void packTick.value // 显式依赖：切站时 packTick 变化 → 这里重算，取到新包的站名
  return activePack().station.name
})

/**
 * 顶栏「运行模式」chip（Issue IKP58M）。
 * 与「数据源（视频链路 / 孪生链路 / 并排）」不是一回事：那个切的是同一页看哪条链路，
 * 这个回答「页面现在吃的是 vite mock 还是 traffic.py」。remote 且请求已确认不可达时
 * 转警示色，并把该敲的命令写进 title —— 使用者不用再从 502 里猜。
 */
interface ModeChip {
  label: string
  note: string
  warn: boolean
}
const modeChip = computed<ModeChip>(() => {
  if (USE_MOCK) {
    return {
      label: 'mock',
      note: 'mock：/api 由 vite mock 中间件回答，不需要 traffic.py（npm run dev）',
      warn: false,
    }
  }
  if (backendReachable.value === false) {
    return {
      label: 'remote · 后端不可达',
      note: 'remote：/api 走 vite 代理到 127.0.0.1:8000，请先起接口层：python work/assembly/traffic.py --port 8000',
      warn: true,
    }
  }
  return {
    label: 'remote',
    note: 'remote：/api 走 vite 代理到 traffic.py（127.0.0.1:8000）',
    warn: false,
  }
})

// ---- 线路图切换器(业主 2026-10-14):顶栏直接选包,选完即换整套路网/基线 ----
// 2026-10-17(IKMDKY 子单①):切包器恢复显示；2026-10-21(IKP5D3):Z21 过渡包已删除，
// 现为 Z(61 段)/ GZ(708 段)两个站包 —— 切包键必须都在后端站点登记表里，否则切过去全站 404。
// 只有一个包时仍不渲染(留一个只有单项的下拉就是死控件)。
const packList = packItems()
const packKey = ref<string>(activePackKey())
const packOpen = ref(false)
// 包键是模块级变量、不参与响应式 —— 订阅一次把它同步成 ref，
// 这样在大屏工具条上切的站，顶栏这里的标签也跟着变（两个入口一个真相）。
const offPackSync = onPackChange(() => {
  packKey.value = activePackKey()
  packTick.value += 1
})
onBeforeUnmount(offPackSync)

/**
 * 换站。**不再整页刷新**（Issue IKPFR4）：统一走 `switchStation()` ——
 * 切包 → 重建路网几何 → 站内状态重置 → 缓存优先渲染首屏 → 后台补拉 → 同步 URL。
 * 详情见 `shared/stationSwitch.ts` 头部注释与 `work/frontend/README.md` 第二十四节。
 */
function choosePack(key: string): void {
  packOpen.value = false
  if (key === packKey.value) return
  // 立即回写一次，让"点了就变"；`onPackChange` 那条订阅是同一份数据的同步，
  // 两处都写是幂等的（键相同不会再触发流程）。返回 false = 键没换（非法键 / 已经是该站）
  if (switchStation(key)) packKey.value = key
}

// ---- 设置（业主 2026-10-16 / Issue IKP5BD）：大屏地图的**底图开关 + 方向标记开关** ----
// 底图：开 = 矢量底图（OpenFreeMap，OSM 数据）+ 描出的路网；关 = **只画路网**（原来「示例路网」那个观感），
// 一个底图请求都不发。底图那一层挂掉也不影响路网（见 `MapLibreViewer.vue`：本地兜底样式建图）。
// 方向标记：开 = 画方向箭头；关 = 一支都不画（图例同步写「已隐藏方向标记」）。
const settingsOpen = ref(false)

// ---- 弹出层（线路图切换器 / 设置）的关闭规则 ----
// ⚠️ 2026-10-17 修 bug：原来靠 `@mouseleave` 收起，而菜单与按钮之间有 4px 空隙 ——
//    鼠标一往下移就离开 wrapper，菜单先收起、指针根本到不了里面的开关（"老是点不着"）。
//    现在改成：点按钮开/关 + 点外部关闭 + Esc 关闭，菜单不再跟着鼠标走。
const packRoot = ref<HTMLElement | null>(null)
const settingsRoot = ref<HTMLElement | null>(null)

function onDocPointerDown(e: PointerEvent): void {
  const t = e.target as Node
  if (packRoot.value && !packRoot.value.contains(t)) packOpen.value = false
  if (settingsRoot.value && !settingsRoot.value.contains(t)) settingsOpen.value = false
}
function onDocKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape') {
    packOpen.value = false
    settingsOpen.value = false
  }
}
onMounted(() => {
  document.addEventListener('pointerdown', onDocPointerDown)
  document.addEventListener('keydown', onDocKeydown)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocPointerDown)
  document.removeEventListener('keydown', onDocKeydown)
})
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
        <span v-if="packList.length > 1" ref="packRoot" class="net-switch">
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
        <!-- 运行模式 chip（IKP58M）：与「数据源」分段控件区分——那个切链路，这个切 mock/remote -->
        <span
          class="td-mode-chip"
          :class="{ warn: modeChip.warn }"
          :title="modeChip.note"
          :aria-label="`运行模式：${modeChip.label}。${modeChip.note}`"
        >
          <span class="td-mode-prefix">运行</span>{{ modeChip.label }}
        </span>
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
        <!-- 设置：底图开关（业主 2026-10-16）。交互：点按钮开/关，点外部或 Esc 关闭 -->
        <span ref="settingsRoot" class="td-settings">
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
            <!-- 方向标记开关（Issue IKP5BD）：默认开；关掉后地图一支箭头都不画，图例写「已隐藏方向标记」 -->
            <div class="td-set-row td-set-row-gap">
              <span class="td-set-main">
                <span class="td-set-name">方向标记</span>
                <span class="td-set-note">
                  开：路段上画方向箭头（双向段中点画一支双头箭头；短于 25 m 的双向段改画中性圆点，
                  因为这么短的段上双头箭头挤成一团、朝向也无意义）<br>
                  关：一支都不画，图例标注「已隐藏方向标记」
                </span>
              </span>
              <button
                type="button"
                class="td-switch"
                :class="{ on: directionsVisible }"
                role="switch"
                :aria-checked="directionsVisible"
                aria-label="方向标记开关"
                @click="setDirectionsVisible(!directionsVisible)"
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
/* 第二项起与前一项用细线隔开（Issue IKP5BD），与菜单底部「td-set-foot」的分隔线同族 */
.td-set-row-gap {
  margin-top: 9px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
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

/* ---- 运行模式 chip（顶栏，Issue IKP58M）----
   中性灰 = 说明性状态；remote 不可达时转警示色（琥珀），不用等级色、不抢品牌蓝。
   title 里带「该敲哪条命令」——502 本身不告诉使用者下一步做什么。 */
.td-mode-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 9px;
  border: 1px solid #d9dce1;
  border-radius: 999px;
  background: #f7f8fa;
  color: #4b5563;
  font-size: 11px;
  line-height: 18px;
  white-space: nowrap;
}
.td-mode-chip.warn {
  border-color: #e0a800;
  background: #fff7e0;
  color: #8a5b00;
  font-weight: 600;
}
.td-mode-prefix {
  color: #999999;
  font-weight: 400;
}
.td-mode-chip.warn .td-mode-prefix {
  color: #b07a00;
}

/* ---------- 响应式（Issue IKP3EV，2026-10-20）----------
   壳层在窄屏的职责只有两件：
   ① ≤1180 时放开主体高度（原 flex:1 + min-height:0 会把整页锁成一屏，
      导致单列后内容被裁）；② 顶栏两个弹出层在手机上不超出视口。
   顶栏本身的换行 / 页签横滑规则在 `src/style.css` 的≤1080 断点里（.td-top 是全局类）。 */
@media (max-width: 1180px) {
  .td-main {
    flex: 0 0 auto;
  }
}
@media (max-width: 1080px) {
  .net-switch-menu {
    min-width: min(260px, calc(100vw - 24px));
  }
  .td-settings-menu {
    width: min(320px, calc(100vw - 24px));
  }
}
@media (max-width: 768px) {
  .net-switch-label {
    max-width: 132px;
  }
  .net-switch-btn,
  .td-settings-btn {
    padding: 6px 10px;
  }
  .net-switch-menu,
  .td-settings-menu {
    max-height: 70vh;
    overflow-y: auto;
  }
}
@media (max-width: 560px) {
  .td-settings-menu {
    padding: 8px 10px;
  }
  .td-set-note {
    font-size: 10px;
  }
}
</style>
