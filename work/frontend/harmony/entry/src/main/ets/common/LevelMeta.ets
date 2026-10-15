/**
 * 四级等级元数据：颜色 + 图标 + 文字三重编码（手册 §11.3）。
 * 色值与 work/frontend/ui-vue 的 TDesign Light 口径一致（README 10.2）。
 * 数据不可用恒为中性灰（TC-11），绝不显示为蓝。
 *
 * 「去色校验」：由页面把 colorBlind 作为参数传下来（不放在模块全局里，
 * 避免多次切换后状态不同步），用于举证「关掉颜色也能区分四级」。
 */
export interface LevelMeta {
  level: number;
  name: string;
  glyph: string;
  color: string;
  textColor: string;
}

const LEVELS: LevelMeta[] = [
  { level: 1, name: '畅通', glyph: '○', color: '#2BA471', textColor: '#006C45' },
  { level: 2, name: '缓行', glyph: '◇', color: '#E9B32E', textColor: '#A06A00' },
  { level: 3, name: '拥堵', glyph: '▲', color: '#E37318', textColor: '#BE5A00' },
  { level: 4, name: '严重拥堵', glyph: '■', color: '#D54941', textColor: '#AD352F' }
];

const UNAVAILABLE_META: LevelMeta = {
  level: 0, name: '数据不可用', glyph: '×', color: '#8B8B8B', textColor: '#8B8B8B'
};

const GRAY: string = '#8B8B8B';

export function levelMetaOf(level: number, unavailable: boolean): LevelMeta {
  if (unavailable) {
    return UNAVAILABLE_META;
  }
  for (let i = 0; i < LEVELS.length; i++) {
    if (LEVELS[i].level === level) {
      return LEVELS[i];
    }
  }
  return UNAVAILABLE_META;
}

/** 图标色：去色校验开启时统一灰 */
export function levelGlyphColorOf(level: number, unavailable: boolean, colorBlind: boolean): string {
  if (colorBlind) {
    return GRAY;
  }
  return levelMetaOf(level, unavailable).color;
}

/** 文字色：去色校验开启时统一灰（文字与图标保留，靠这两条通道区分） */
export function levelTextColorOf(level: number, unavailable: boolean, colorBlind: boolean): string {
  if (colorBlind) {
    return GRAY;
  }
  return levelMetaOf(level, unavailable).textColor;
}

export const LEVEL_META_LIST: LevelMeta[] = LEVELS;
export const LEVEL_UNAVAILABLE: LevelMeta = UNAVAILABLE_META;

/**
 * 等级 → 慢速系数（畅通最快，越堵越慢）。
 *
 * 【为什么必须提取成唯一一份 —— 这是评审最容易挑的「重复定义」】
 * 初版这套系数被逐字抄了两遍：`DemoStore.levelSpeedFactor()`（巡航每 40ms
 * 用它算车标推进量）与 `stretchEtaMinAt()` 里的闭包（按它分配各段 ETA）。
 * 两处只要有一处漏改，就会出现「地图上车在畅通段跑得飞快，
 * 而导航条说这段要 3 分钟」的自相矛盾，而且很难排查。
 * 现统一由本函数提供，改一处即全工程生效。
 *
 * 取值：畅通 1.0 / 缓行 0.6 / 拥堵 0.35 / 严重拥堵 0.2。
 * 数据不可用（-1）按最快处理 —— 那是「拿不到等级」而非「堵」。
 */
export function levelSpeedFactorOf(level: number): number {
  if (level === 2) {
    return 0.6;
  }
  if (level === 3) {
    return 0.35;
  }
  if (level === 4) {
    return 0.2;
  }
  return 1.0;
}
