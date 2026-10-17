// 站点包选择器 —— 浏览器与 vite mock 中间件**共用同一份**(mock 也从这个图里取包)。
//
// 为什么需要"选择器"这一层:站点包讲的是"一份包 = 一个站",而运行时要回答的问题是
// "现在这份前端跑的是哪个站"。答案只能有一个来源,否则会出现"页面画一个站的路网、
// mock 端另一个站的基线"这种对不上的画面。两个入口各注入一次、共用这一个键:
//   · 浏览器:`main.ts` 读构建期的 `import.meta.env.VITE_STATION_PACK`(`.env.z` 里写),
//     在挂载前注入 —— 之后所有组件与模块读到的都是同一份包;
//   · vite mock:`vite.config.ts` 用 `loadEnv` 读同一个变量,经 `mockApiPlugin({ pack })` 注入。
// **本仓现有两个包,同站不同代几何**:
//   · `Z`   = 现行几何(61 段,站区 500 m,IKMERX 三步管线产物 / IKMDKY 切新段后)
//   · `Z21` = 旧 21 段过渡几何(按路名归并)——**只用于切换对照**,定稿后按 netpack README 删除。
// 顶栏「线路图切换器」与监控大屏工具条各有一个入口;取不到就落默认包 Z。
//
// ⚠️ **选择器这一层一个字不删**:手册 §8.4「换一个站只改配置、不改引擎代码」靠它成立 ——
//    将来加站还是"加一个包 + 一行 env",页面与 mock 各自读同一个键这件事不变。

import { STATION_Z } from './stationZ.ts'
import { STATION_Z21 } from './stationZ21.ts'
import type { StationPack } from './types.ts'

export const PACKS: Record<string, StationPack> = {
  Z: STATION_Z,
  Z21: STATION_Z21,
}

export const DEFAULT_PACK_KEY = 'Z'

let injectedKey: string | null = null

/** 记忆用户选过的线路图(顶部栏切换器)。键名带项目前缀,不与别的页串味 */
const PACK_MEM_KEY = 'hubflow.stationPack'

/** 由入口注入当前包键(浏览器在挂载前、mock 在插件装配时各调一次) */
export function setActivePackKey(key: string): void {
  injectedKey = key
}

/**
 * 启动时读回用户上次选过的包(`switchPack` 写的那份)。
 *
 * 为什么需要:顶部栏切换器选完会 `window.location.reload()`(见 `AppShell.choosePack`),
 * 而 `injectedKey` 是模块级变量、刷新即丢 —— 没有这一步,切换器**选完就退回默认包**,
 * 等于坏的。读不到 / 读坏了就落回注入值(构建期的 `VITE_STATION_PACK`)。
 * Node 侧(mock 中间件)没有 `localStorage`,靠 try/catch 静默落回注入值。
 *
 * ⚠️ 老浏览器里可能残留**已删除的包键**(`'A'` / `'B'` / `'Y'`,分别随 IKM4XX / IKM4KP 删除):
 *    `PACKS[k]` 这一关就是为它设的 —— 未知键一律落回注入值,不白屏。
 */
export function restorePackKey(fallback: string): string {
  try {
    const k = localStorage.getItem(PACK_MEM_KEY)
    if (k && PACKS[k]) return k
  } catch {
    /* localStorage 不可用(隐私模式 / Node 侧):用注入值 */
  }
  return fallback
}

/**
 * 运行时切换站点包(顶部栏线路图切换器,业主 2026-10-14)。
 * 只改浏览器侧的键:几何(demoNetwork 惰性读包)与 mock(每次请求读包)都从
 * `activePack()` 现取,所以下一次拉快照起,页面路网/基线/告警整套跟着换;
 * 同时落一份 localStorage,好让 `choosePack()` 的整页刷新之后仍然生效。
 *
 * 现在有两个包(Z 61 段 / Z21 旧 21 段),顶栏切换器与大屏工具条按钮都调这一支。
 */
export function switchPack(key: string): void {
  if (!PACKS[key]) return
  injectedKey = key
  try {
    localStorage.setItem(PACK_MEM_KEY, key)
  } catch {
    /* 隐私模式等写不进去:不影响本次会话内切换,只是刷新后不记忆 */
  }
}

/**
 * 当前生效的包键。
 * 键不存在时落默认包(不抛错):演示站多起来以后,"包里没有这个键"要表现得像"走默认站",
 * 而不是整页白屏;但键写错这件事要在页脚可见(见 `packNote()` 会同时打出键与包名)。
 */
export function activePackKey(): string {
  const key = injectedKey ?? DEFAULT_PACK_KEY
  return PACKS[key] ? key : DEFAULT_PACK_KEY
}

/** 当前生效的站点包 */
export function activePack(): StationPack {
  return PACKS[activePackKey()] ?? STATION_Z
}

/** 包自检说明(页脚展示用):包键 + 这个包是什么 */
export function packNote(): string {
  const p = activePack()
  return `站点包 ${p.key} · ${p.note}`
}

/** 可选线路清单(顶部栏切换器 / 大屏按钮用):键 + 短标签(缺省站名) + 一句话口径 */
export function packItems(): { key: string; name: string; note: string }[] {
  return Object.values(PACKS).map((p) => ({
    key: p.key,
    name: p.label ?? p.station.name,
    note: p.note,
  }))
}
