/**
 * 四级等级元数据：颜色 + 图标 + 文字三重编码（手册 §11.3）。
 * 色值与 work/frontend/ui-vue 的 TDesign Light 口径一致（README 10.2）。
 * 数据不可用恒为中性灰（TC-11），绝不显示为蓝。
 *
 * 「去色校验」开关：把颜色通道整体置灰（图标与文字保留），用于举证
 * 「关掉颜色也能区分四级」——工程内演示开关，不是业务逻辑。
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

/** 去色校验开关状态（模块内共享，页面重建时读取） */
let COLOR_BLIND: boolean = false;

export function setColorBlind(enabled: boolean): void {
  COLOR_BLIND = enabled;
}

export function isColorBlind(): boolean {
  return COLOR_BLIND;
}

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
export function levelGlyphColorOf(level: number, unavailable: boolean): string {
  if (COLOR_BLIND) {
    return GRAY;
  }
  return levelMetaOf(level, unavailable).color;
}

/** 文字色：去色校验开启时统一灰（文字与图标保留，靠这两条通道区分） */
export function levelTextColorOf(level: number, unavailable: boolean): string {
  if (COLOR_BLIND) {
    return GRAY;
  }
  return levelMetaOf(level, unavailable).textColor;
}

export const LEVEL_META_LIST: LevelMeta[] = LEVELS;
export const LEVEL_UNAVAILABLE: LevelMeta = UNAVAILABLE_META;
