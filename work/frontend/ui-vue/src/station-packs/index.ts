// 站点包选择器 —— 浏览器与 vite mock 中间件**共用同一份**(mock 也从这个图里取包)。
//
// 为什么需要"选择器"这一层:站点包讲的是"一份包 = 一个站",而运行时要回答的问题是
// "现在这份前端跑的是哪个站"。答案只能有一个来源,否则会出现"页面画二站路网、
// mock 端一站基线"这种对不上的画面。两个入口各注入一次、共用这一个键:
//   · 浏览器:`main.ts` 读构建期的 `import.meta.env.VITE_STATION_PACK`(`.env.station2` 里写),
//     在挂载前注入 —— 之后所有组件与模块读到的都是同一份包;
//   · vite mock:`vite.config.ts` 用 `loadEnv` 读同一个变量,经 `mockApiPlugin({ pack })` 注入。
// 取不到就落默认包 A(肇庆东站示例路网),保证 `npm run dev` 的行为与接包之前完全一致。

import { STATION_A } from './stationA.ts'
import { STATION_B } from './stationB.ts'
import { STATION_Y } from './stationY.ts'
import type { StationPack } from './types.ts'

export const PACKS: Record<string, StationPack> = {
  A: STATION_A,
  B: STATION_B,
  Y: STATION_Y,
}

export const DEFAULT_PACK_KEY = 'A'

let injectedKey: string | null = null

/** 由入口注入当前包键(浏览器在挂载前、mock 在插件装配时各调一次) */
export function setActivePackKey(key: string): void {
  injectedKey = key
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
  return PACKS[activePackKey()] ?? STATION_A
}

/** 包自检说明(页脚展示用):包键 + 这个包是什么 */
export function packNote(): string {
  const p = activePack()
  return `站点包 ${p.key} · ${p.note}`
}
