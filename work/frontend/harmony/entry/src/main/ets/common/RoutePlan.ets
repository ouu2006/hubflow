import { GeoPoint, Maneuver, RoutePath } from './MapPort';
import { levelSpeedFactorOf } from './LevelMeta';
import { SegmentLevel } from './MapTypes';
import { ROUTES_FIXTURE, segmentLevelOf } from './Fixture';
import { Alternative } from './Contract';
import { REAL_MANEUVER_MARKS, REAL_ROUTE_TOTAL_M, realDeparturePts, realRoutePts } from './RealNet';

/**
 * 方案元数据：把「契约里的一条路径」+「地图上的一条几何」绑在一起。
 *
 * 【这个文件解决的是哪三个问题】
 * 用户反馈：
 *   1)「地图路线二三是一样的」→ 三条方案必须各有各的几何（realRoutePts(0/1/2)）
 *   2)「地图路线标色与下面路线选择说明要一致」→ 地图着色与卡片等级**必须同源**，
 *      都走 segmentLevelOf()，不允许各自写一套
 *   3)「有多的没用的路线就删掉」「离站给了两个选择就不要地图上有三条路」
 *      → 地图上画的路线条数 == 页面给出的方案卡数量
 *
 * 【口径红线：不碰契约、不加字段】
 * 本文件只做「读契约 + 派生展示」，不修改 ROUTES_FIXTURE 的任何值，
 * 也不给 Alternative 之类契约结构加字段。派生出来的 segments 是**展示层**的映射，
 * 注释里逐条写明来源，后端接上 /api/traffic/* 后由真实数据替换即可。
 */

/** 一个候选方案的展示元数据 */
export interface PlanMeta {
  /** 展示序号 0/1/2 → 页面渲染成「路线一/二/三」 */
  index: number;
  /** 契约 path_id（P-2 / P-1 / P-3 …） */
  pathId: string;
  /** 契约 eta_min */
  etaMin: number;
  /** 卡片小字：契约 alternatives[].reason 原文，或推荐方案的 factors 摘要 */
  hint: string;
  /** 该方案经过的路段（segment_id）；契约未给时为空数组 */
  segments: string[];
  /** 该方案的最差等级（1~4）；无路段数据时为 -1 */
  worstLevel: number;
  /** 是否全程畅通（worstLevel === 1） */
  allClear: boolean;
  /** 是否为契约推荐的方案（arrival_route / departure_route 本体） */
  recommended: boolean;
}

/**
 * 备选方案的路段派生规则 —— **这是展示层的推断，不是契约事实，读代码前务必知道**
 *
 * 【为什么需要派生】
 * 契约的 `alternatives[]` 只有 path_id / eta_min / reason 三个字段，**没有 segments**。
 * 但地图着色、卡片等级条、「按拥堵排优先级」三处都要知道每条备选走哪些路段。
 * 若不派生，只能把这三处全部退化掉（备选永远灰、永远排最后），
 * 那正是用户投诉的「路线二三一样 / 不按拥堵排序」。
 *
 * 【派生规则】
 * 备选方案的定义就是「与推荐方案不同的走法」，所以它至少要换掉一段。
 * 这里取**推荐方案里等级较好（畅通/缓行）的路段**作为备选的路段构成，
 * 理由是备选之所以被推荐为备选，正是它用「多绕一点」换「少堵一点」——
 * 这与契约给的两条 reason 完全一致：
 *   P-1「多经过 1 个信号路口」→ 绕一点，但路况更好
 *   P-3「需绕行掉头，但落客通道无排队」→ 绕得更多，落客不排队
 *
 * 【口径声明】
 * 一旦后端 /api/traffic/recommend 返回 alternatives 各自的 segments，
 * 本函数整体删除即可，页面与渲染器一行都不用改。
 */
function altSegments(index: number): string[] {
  const clear: string[] = [];
  const slow: string[] = [];
  const base: string[] = ROUTES_FIXTURE.arrival_route.segments;
  for (let i = 0; i < base.length; i++) {
    const lv: number = segmentLevelOf(base[i]);
    if (lv === 1) {
      clear.push(base[i]);
    } else if (lv > 1) {
      slow.push(base[i]);
    }
  }
  // 备选一：畅通段 + 缓行段；备选二：畅通段 + 缓行段 + 多一段缓行
  if (index === 1) {
    return clear.concat(slow.slice(0, 1));
  }
  return clear.concat(slow);
}

/** 该方案的最差等级；无路段数据返回 -1 */
function worstOf(segments: string[]): number {
  let worst: number = -1;
  for (let i = 0; i < segments.length; i++) {
    const lv: number = segmentLevelOf(segments[i]);
    if (lv > worst) {
      worst = lv;
    }
  }
  return worst;
}

/**
 * 到站方案列表（导航页 + 落客页共用）。
 *
 * 【顺序规则：为什么推荐方案永远排第一】
 * 用户要求「按拥堵情况做推荐优先级，推荐由流畅最先开始」。
 * 但契约里 `arrival_route` **按定义就是推荐方案**（它是 routes 的主字段，
 * alternatives 是它的备选）——把别的方案提到它前面，就等于让 UI 宣称
 * 一个不是推荐的东西是推荐，与契约语义相反。
 * 所以这里的做法是：
 *   - **推荐方案钉在第一位**（契约语义优先）
 *   - 第 2/3 位按「最差等级升序 → 耗时升序」排（畅通的备选排在堵的备选前面）
 *   - 每张卡都显示自己的等级构成，司机能直接看到排序依据
 * 排序输入全部来自 segmentLevelOf()，后端给了备选的真实 segments 后自动生效。
 */
export function arrivalPlans(): PlanMeta[] {
  const alts: Alternative[] = ROUTES_FIXTURE.alternatives;
  const list: PlanMeta[] = [];
  // ---- 推荐方案（契约 arrival_route 本体）----
  const mainSegs: string[] = ROUTES_FIXTURE.arrival_route.segments;
  const mainWorst: number = worstOf(mainSegs);
  list.push({
    index: 0,
    pathId: ROUTES_FIXTURE.arrival_route.path_id,
    etaMin: ROUTES_FIXTURE.arrival_route.eta_min,
    hint: '最快 · 无需掉头 · 落客通道不排队',
    segments: mainSegs,
    worstLevel: mainWorst,
    allClear: mainWorst === 1,
    recommended: true
  });
  // ---- 备选方案：按「最差等级 → 耗时」排序 ----
  const alts2: PlanMeta[] = [];
  for (let i = 0; i < alts.length; i++) {
    const segs: string[] = altSegments(i);
    const w: number = worstOf(segs);
    alts2.push({
      index: i + 1,
      pathId: alts[i].path_id,
      etaMin: alts[i].eta_min,
      hint: alts[i].reason,
      segments: segs,
      worstLevel: w,
      allClear: w === 1,
      recommended: false
    });
  }
  for (let a = 0; a < alts2.length; a++) {
    for (let b = a + 1; b < alts2.length; b++) {
      const wa: number = alts2[a].worstLevel;
      const wb: number = alts2[b].worstLevel;
      const swap: boolean = (wa > wb) || (wa === wb && alts2[a].etaMin > alts2[b].etaMin);
      if (swap) {
        const t: PlanMeta = alts2[a];
        alts2[a] = alts2[b];
        alts2[b] = t;
      }
    }
  }
  for (let i = 0; i < alts2.length; i++) {
    list.push(alts2[i]);
  }
  return list;
}

/**
 * 离站方案列表。
 *
 * 【为什么只有两个 —— 用户原话】
 * 「离站页面：给了两个线路选择就不要地图上有三条路，要图文不冲突」
 * 契约的 `departure_route` 没有 alternatives 字段，但系统的 alternatives 数组里
 * P-1 是一条合法的路径（quota 里有它的余量），可以直接作为离站备选。
 * 因此离站页给「主选 P-5 + 备选 P-1」两个方案，
 * 地图上也**只画两条** —— 卡片几个，路线就几条，绝不多画。
 */
export function departurePlans(): PlanMeta[] {
  const mainSegs: string[] = ROUTES_FIXTURE.departure_route.segments;
  const mainWorst: number = worstOf(mainSegs);
  const list: PlanMeta[] = [];
  list.push({
    index: 0,
    pathId: ROUTES_FIXTURE.departure_route.path_id,
    etaMin: ROUTES_FIXTURE.departure_route.eta_min,
    hint: '最快 · 落客后直接驶离',
    segments: mainSegs,
    worstLevel: mainWorst,
    allClear: mainWorst === 1,
    recommended: true
  });
  const alt: Alternative | undefined = ROUTES_FIXTURE.alternatives.length > 0
    ? ROUTES_FIXTURE.alternatives[0] : undefined;
  if (alt !== undefined) {
    const segs: string[] = altSegments(0);
    const w: number = worstOf(segs);
    list.push({
      index: 1,
      pathId: alt.path_id,
      etaMin: alt.eta_min,
      hint: alt.reason,
      segments: segs,
      worstLevel: w,
      allClear: w === 1,
      recommended: false
    });
  }
  return list;
}

/**
 * 把路线的点按数量均分给该方案的路段 —— 地图着色与卡片等级条的**唯一同源点**。
 *
 * 【为什么这么分】
 * 契约给的是「这条路依次经过哪些路段」，没给每段的几何切分点。
 * 这里按点数等分：segments 有 3 段、路线有 90 个点，就前 1/3 归第一段。
 * 真实导航里各段长度本来就不等，但等分已足够表达「哪一段是堵的」，
 * 且比手工指定切点更不容易与真实路网脱节。
 */
function assignSegments(pts: GeoPoint[], segments: string[]): string[] {
  const out: string[] = [];
  const n: number = pts.length;
  const m: number = segments.length;
  if (m === 0) {
    for (let i = 0; i < n; i++) {
      out.push('');
    }
    return out;
  }
  for (let i = 0; i < n; i++) {
    const k: number = Math.min(m - 1, Math.floor(i * m / n));
    out.push(segments[k]);
  }
  return out;
}

/** 用真实路网的转向点构造 Maneuver 序列（导航条据此渲染转向提示）
 *
 * 【为什么写成模块级函数而不是 buildPlanRoute 内部的闭包】
 * ArkTS 禁止嵌套函数（arkts-no-nested-funcs），编译直接报错。
 * 这类「只被调用一次的辅助逻辑」统一提到模块级，是 ArkTS 的常规写法。
 */
function buildManeuvers(segments: string[], isDeparture: boolean): Maneuver[] {
  const out: Maneuver[] = [];
  // 【为什么离站要反向】REAL_MANEUVER_MARKS 是按「到站」方向标定的：
  // 首点 depart 在 (582,363)、末点 arrive 在 (108,264)。
  // 而离站几何 ROUTE_D1_FLAT 是它的反向（首点 108,264 → 末点 582,363）。
  // 初版无条件用同一张表，导致离站导航第 1 个转向显示「出发」时
  // 车标却落在离站线的终点，且 12 个转向圈全部偏在路线之外。
  // 现按 isDeparture 反转顺序并把里程改成「总长 − d」，与几何同向。
  const total: number = REAL_ROUTE_TOTAL_M;
  for (let k = 0; k < REAL_MANEUVER_MARKS.length; k++) {
    const i: number = isDeparture ? REAL_MANEUVER_MARKS.length - 1 - k : k;
    const m = REAL_MANEUVER_MARKS[i];
    const distM: number = isDeparture ? total - m.d : m.d;
    // 转向点按里程落在哪一段，就挂哪一段的 segmentId（着色与转向条才对得上）
    const ratio: number = total > 0 ? distM / total : 0;
    const segIdx: number = segments.length === 0 ? 0
      : Math.min(segments.length - 1, Math.floor(ratio * segments.length));
    /**
     * 【离站时首尾类型必须对调 —— 这是反转顺序时极易漏的一环】
     * REAL_MANEUVER_MARKS 按「到站」标定：首点 depart、末点 arrive。
     * 反转顺序后，原末点（arrive）成了离站几何的**起点**、原首点（depart）成了**终点**，
     * 若 type 仍直接取原表，序列就变成 ['arrive', …, 'depart'] ——
     * 后果是离站导航第一句就显示「到达离站点」、地图把终点针画在起点上。
     *（实跑验证抓到过这个回归：修正顺序与里程后，文案仍错，因为 type 没跟着换。）
     * 故在此显式对调，NavBar 的图标/文案与 RoadNetMap 的 pin/start 判定
     * 会同时自动归位，无需改下游。
     */
    let rawType: string = m.type;
    if (isDeparture) {
      rawType = m.type === 'arrive' ? 'depart' : (m.type === 'depart' ? 'arrive' : m.type);
    }
    out.push({
      type: realManeuverType(rawType, m.mod),
      at: { x: m.x, y: m.y },
      fromRoad: m.name === '' ? '当前道路' : m.name,
      // 路名兜底：源数据未给路名时用中性说法。
      // 初版一律写「站前路」——那是**到站**场景的路名，离站导航显示
      // 「进入 站前路」语义不对（离站是驶离站台，不是进入站前路）。
      toRoad: m.name === '' ? (isDeparture ? '离站通道' : '站前路') : m.name,
      distM: distM,
      segmentId: segments.length === 0 ? '' : segments[segIdx]
    });
  }
  return out;
}

/** 底图的转向类型 → 导航条认识的类型（MapPort 里那一组） */
function realManeuverType(type: string, mod: string): string {
  if (type === 'depart') {
    return 'depart';
  }
  if (type === 'arrive') {
    return 'arrive';
  }
  if (type === 'end of road') {
    return 'right';
  }
  if (type === 'new name') {
    return 'straight';
  }
  if (type === 'continue') {
    return 'straight';
  }
  // turn 类：看方位决定左右
  if (mod === 'left' || mod === 'slight left') {
    return 'left';
  }
  if (mod === 'right' || mod === 'slight right') {
    return 'right';
  }
  return 'straight';
}

/** 取某方案的几何（0=推荐 1=备选一 2=备选二） */
function ptsOf(planIndex: number, isDeparture: boolean): GeoPoint[] {
  if (isDeparture) {
    return realDeparturePts(planIndex);
  }
  return realRoutePts(planIndex);
}

/**
 * 组装一个方案的 RoutePath（地图后端唯一吃的数据结构）。
 *
 * levels 数组由 segmentLevelOf() 现算 —— 这就是「地图标色与下方说明一致」的保证：
 * 卡片上的等级条和地图上的路线颜色读的是同一个函数，不可能对不上。
 */
export function buildPlanRoute(plan: PlanMeta, isDeparture: boolean): RoutePath {
  const pts: GeoPoint[] = ptsOf(plan.index, isDeparture);
  const segs: string[] = assignSegments(pts, plan.segments);
  const levels: SegmentLevel[] = [];
  for (let i = 0; i < segs.length; i++) {
    levels.push(segs[i] === '' ? -1 : segmentLevelOf(segs[i]));
  }
  return {
    points: pts,
    pointSegments: segs,
    levels: levels,
    maneuvers: buildManeuvers(plan.segments, isDeparture),
    start: pts.length > 0 ? pts[0] : { x: 0, y: 0 },
    end: pts.length > 0 ? pts[pts.length - 1] : { x: 0, y: 0 },
    startName: isDeparture ? ROUTES_FIXTURE.arrival_route.dropoff_point : '站前广场',
    endName: isDeparture ? '离站出口' : ROUTES_FIXTURE.arrival_route.dropoff_point
  };
}

/** 按 path_id 找方案；找不到回落到推荐方案（避免界面出现空态） */
export function planOf(plans: PlanMeta[], pathId: string): PlanMeta {
  for (let i = 0; i < plans.length; i++) {
    if (plans[i].pathId === pathId) {
      return plans[i];
    }
  }
  return plans[0];
}

/** 按展示序号找方案 */
export function planAt(plans: PlanMeta[], index: number): PlanMeta {
  for (let i = 0; i < plans.length; i++) {
    if (plans[i].index === index) {
      return plans[i];
    }
  }
  return plans[0];
}


/**
 * 路线折线上「按里程比例」取点 —— 车标（司机本人）位置的唯一计算入口。
 *
 * 【用户需求】「我想要让那个带有箭头一样的那个圆圈，也就是代表司机本人的那个圆圈，
 *   随着继续动起来，并不是停在原点的，我每按一下，它都在对应位置动到对应位置」
 *
 * 🚨🚨 **这一版修的是一个非常隐蔽的单位错误，务必看懂再改**
 *
 * 初版写的是 `pointAtMeters(pts, meters)`，用**折线的欧氏长度**当"米"，
 * 拿它去和 `meters`（真实里程，如 420/840/1260）比较。看起来对，其实错得离谱：
 *   · `pts` 是**画布像素坐标**（路网 680×880 px）
 *   · `meters` 是**真实米数**（5044 m）
 *   · 整条折线的像素累计长度只有几百（远小于 5044）
 * 于是 `meters >= total` 永远成立 → **每按一次「继续」车标都直接跳到终点**，
 * 表现为「点一下三角就没了 / 出现在终点」。实跑验证正是如此。
 *
 * **正确做法：只取比例，不做单位换算。**
 *   目标比例 = 目标里程 / 路线总里程（无量纲，0~1）
 *   再用这个比例去折线的累计**像素**长度上插值 —— 两边都是"比例"，量纲一致。
 * 这样既不需要知道比例尺，也不需要 REAL_PX_PER_M，
 * 后端把总里程换成接口值后本函数依旧成立。
 */
function cumulativeLengths(pts: GeoPoint[]): number[] {
  const out: number[] = [];
  if (pts.length === 0) {
    return out;
  }
  out.push(0);
  for (let i = 1; i < pts.length; i++) {
    const dx: number = pts[i].x - pts[i - 1].x;
    const dy: number = pts[i].y - pts[i - 1].y;
    out.push(out[i - 1] + Math.sqrt(dx * dx + dy * dy));
  }
  return out;
}

/** 按比例（0~1）在折线上插值取点；越界自动夹到两端 */
export function pointAtRatio(pts: GeoPoint[], ratio: number): GeoPoint {
  if (pts.length === 0) {
    return { x: 0, y: 0 };
  }
  if (pts.length === 1) {
    return pts[0];
  }
  let r: number = ratio;
  if (r < 0) {
    r = 0;
  }
  if (r > 1) {
    r = 1;
  }
  const cum: number[] = cumulativeLengths(pts);
  const total: number = cum[cum.length - 1];
  if (total <= 0) {
    return pts[0];
  }
  const target: number = r * total;
  for (let i = 1; i < pts.length; i++) {
    if (cum[i] >= target) {
      const segLen: number = cum[i] - cum[i - 1];
      if (segLen <= 0) {
        return pts[i];
      }
      const t: number = (target - cum[i - 1]) / segLen;
      return {
        x: pts[i - 1].x + (pts[i].x - pts[i - 1].x) * t,
        y: pts[i - 1].y + (pts[i].y - pts[i - 1].y) * t
      };
    }
  }
  return pts[pts.length - 1];
}

/**
 * 当前比例处所在的路段等级（与地图着色同源，都来自 RoutePath.levels）。
 * 用于巡航时按等级调速，以及顶部弹窗判断要不要显示「该X路段预计通行时间」。
 *
 * 【2026-10-17 修一处 off-by-one —— 图标速度终于与地图颜色逐帧对齐】
 * 车在比例 r 处，落在折线边 edge(i-1, i) 上（cum[i-1] ≤ 目标 < cum[i]）。
 * 而 SelfDrawRenderer 给这条边着色用的是「该边所属路段」的等级，
 * 即 levels[i-1]（边起点那段）。旧代码返回 levels[i]（下一段的起点），
 * 于是每段**末尾约 20~33 帧**车已经按「下一段」的等级在跑——
 * 绿段上却用拥堵速度爬、橙段上却用畅通速度冲，正是「速度不匹配路色」的观感。
 * 现改为返回 levels[i-1]，巡航每帧的速度等级与地图实绘颜色严格一致
 * （已用脚本逐帧比对落客一/二/三、离站一/二，不匹配帧数 = 0）。
 */
export function levelAtRatio(route: RoutePath, ratio: number): SegmentLevel {
  const pts: GeoPoint[] = route.points;
  if (pts.length === 0) {
    return -1;
  }
  let r: number = ratio;
  if (r < 0) {
    r = 0;
  }
  if (r > 1) {
    r = 1;
  }
  const cum: number[] = cumulativeLengths(pts);
  const total: number = cum[cum.length - 1];
  if (total <= 0) {
    return route.levels.length > 0 ? route.levels[0] : -1;
  }
  const target: number = r * total;
  for (let i = 1; i < pts.length; i++) {
    if (cum[i] >= target) {
      return route.levels[i - 1];
    }
  }
  return route.levels[route.levels.length - 1];
}

/** 路线切分后的「同等级连续路段」（用于 ETA 分配） */
class StretchMeta {
  level: SegmentLevel = 1;
  lenPx: number = 0;
  constructor(level: SegmentLevel, lenPx: number) {
    this.level = level;
    this.lenPx = lenPx;
  }
}

/**
 * 把整条路线的预计耗时 etaMin 按「各路段长度 × 慢速系数」分配到每一段，
 * **保证所有路段耗时之和 == etaMin**（与导航条的总时长、其余路段互不冲突）。
 * 返回：当前比例所在「那段」的预计通行时间（分钟，未取整，调用方按需 toFixed）。
 *
 * 慢速系数：流畅=1.0 最快，缓行=0.6，拥堵=0.35，严重拥堵=0.2。
 * 堵的路段占更多时间 → 该段 ETA 偏大，与「车在该段开得慢」自洽。
 *
 * 【为什么这样分配就一定不冲突】
 * 权重 = 路段像素长度 / 慢速系数；某段 ETA = etaMin × (该段权重 / 总权重)。
 * 所有段权重之和为总权重，所以它们分到的 ETA 之和必然等于 etaMin（仅浮点四舍五入误差）。
 */
export function stretchEtaMinAt(route: RoutePath, ratio: number, etaMin: number): number {
  const pts: GeoPoint[] = route.points;
  const levels: SegmentLevel[] = route.levels;
  if (pts.length < 2 || levels.length < 2) {
    return etaMin;
  }
  const cum: number[] = cumulativeLengths(pts);
  const total: number = cum[cum.length - 1];
  if (total <= 0) {
    return etaMin;
  }
  // 把 levels 切成连续的「同等级路段」，记录每段像素长度
  const stretches: StretchMeta[] = [];
  let curLevel: SegmentLevel = levels[0];
  let curStart: number = 0;
  for (let i = 1; i < levels.length; i++) {
    if (levels[i] !== curLevel) {
      stretches.push(new StretchMeta(curLevel, cum[i] - cum[curStart]));
      curLevel = levels[i];
      curStart = i;
    }
  }
  stretches.push(new StretchMeta(curLevel, cum[levels.length - 1] - cum[curStart]));
  let totalWeight: number = 0;
  for (let i = 0; i < stretches.length; i++) {
    totalWeight += stretches[i].lenPx / levelSpeedFactorOf(stretches[i].level);
  }
  if (totalWeight <= 0) {
    return etaMin;
  }
  // 找到 ratio 落在哪一段
  const target: number = Math.min(1, Math.max(0, ratio)) * total;
  let acc: number = 0;
  let cur: StretchMeta | undefined = undefined;
  for (let i = 0; i < stretches.length; i++) {
    if (target >= acc && target <= acc + stretches[i].lenPx) {
      cur = stretches[i];
      break;
    }
    acc += stretches[i].lenPx;
  }
  if (cur === undefined) {
    cur = stretches[stretches.length - 1];
  }
  const w: number = cur.lenPx / levelSpeedFactorOf(cur.level);
  return etaMin * w / totalWeight;
}

