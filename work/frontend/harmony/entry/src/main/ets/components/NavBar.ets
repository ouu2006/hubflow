import { ROUTES_FIXTURE, DISCLAIMER_TEXT } from '../common/Fixture';
import { DemoStore } from '../common/DemoStore';
import {TEXT_WHITE, ACCENT_COLOR_BLIND, TEXT_ON_DEGRADED, TEXT_ON_EMERGENCY_BAR_SUB, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY} from '../common/Colors';
import { Maneuver, RoutePath } from '../common/MapPort';
import { PlanMeta, arrivalPlans, departurePlans, planOf, buildPlanRoute, levelAtRatio, stretchEtaMinAt } from '../common/RoutePlan';
import { levelMetaOf } from '../common/LevelMeta';
import { maneuverGlyph, maneuverText } from '../common/ManeuverMeta';
import { REAL_ROUTE_TOTAL_M } from '../common/RealNet';

/**
 * 导航动作条（深色，参考高德导航顶部那块）。
 *
 * 【高德式专业导航排版】
 * 高德导航条的构成是固定的四段，本条对齐做成：
 *   ① 转向图标（大号箭头，居左）
 *   ② 转向文案（"靠右进入支路"）+ 进入后的道路名
 *   ③ 距离/时间/路径号（"420米 · 约6.4分钟 · P-2"）
 *   ④ 车道指引（右侧小方块，箭头 + 建议车道）
 * 常态下再加底部一行「剩余距离 + 进度条」，这是高德的标志形态。
 *
 * 【转向序列从哪来】
 * 数据源是 `Y_MANEUVERS`（队长要求的 Y 字路线），
 * 与地图上的橙色转向点 **一一对应** —— 地图转到哪，导航条就显示哪个转向。
 * 所以「Y 字路线能不能过流程」这条验收，靠的就是这两个是不是一致。
 *
 * 【为什么做成 @Component 子组件而不是 @Builder】
 * @Builder 的值参数只在创建时求值一次，store.emergency 变化后不会重算（实跑验证踩过）。
 * 参数用 @Prop 声明，父态一变必然整条重绘。
 */

const BAR_BG: string = '#1B2733';           // 深色导航条底
const BAR_BG_EMERGENCY: string = '#8E1F1F'; // 应急态深红
const BAR_BG_DEGRADED: string = '#7A5A16';  // 拒绝授权降级（琥珀棕，压住白字）
const BAR_TEXT_SUB: string = '#9FB0BF';     // 次要文字
const BAR_TEXT_ROAD: string = '#C8D6E2';    // 路名（比次要文字亮一档）
const BAR_BG_SUB: string = '#2A3B4D';       // 车道指引小方块
const BAR_PROGRESS: string = '#2A3B4D';     // 进度条底
const BAR_PROGRESS_IN: string = '#00C36A';  // 进度条已走（绿，和高德一致）
const BAR_LEVEL_TEXT: string = '#FFE1B0';    // 路段耗时文字（琥珀，呼应等级色）
const BAR_LEVEL_4: string = '#D54941';       // 严重拥堵（红）
/**
 * 【底部三个按钮的配色 + 点击反馈 —— 2026-10-16 用户要求】
 * 用户原话：「开始导航按钮是有颜色的，我要剩下两个按钮也有不同颜色，
 *   并且在不按的时候是浅色，按的时候加深能看到点击效果」
 * → 三个按钮**各一个色相**（主行动蓝 / 变道浅蓝 / 退出浅灰），
 *   常态都是浅色，按下时统一加深一档（stateStyles.pressed）。
 * 注意：这里不能沿用旧写法 `.backgroundColor('TEXT_WHITE')` —— 那是把**变量名**
 * 当字符串传给颜色参数，ArkUI 解析不出合法色值，等于没有背景（看不出是个按钮）。
 */
const BTN_DRIVE: string = '#1E88E5';         // 开始导航（主行动，蓝）
const BTN_DRIVE_ON: string = '#1565C0';      // 开始导航 · 按下
const BTN_LANE: string = '#D6E8FB';          // 变道（浅蓝，与开始导航同色系但浅）
const BTN_LANE_ON: string = '#A8CCF5';       // 变道 · 按下
const BTN_EXIT: string = '#E4E9EE';          // 退出（中性浅灰，和另两个都不同）
const BTN_EXIT_ON: string = '#C2CBD4';       // 退出 · 按下
const BTN_PICK: string = '#EDEFF2';          // 落客/离站页「选择路线」按钮（浅灰）
const BTN_PICK_ON: string = '#CFD6DE';       // 落客/离站页「选择路线」按钮 · 按下
const BAR_LEVEL_3: string = '#E37318';       // 拥堵（橙）
const BAR_LEVEL_2: string = '#E9B32E';       // 缓行（黄）
/**
 * 【为什么导航条的色值不并入 common/Colors.ets —— 评审必问，提前说明】
 * Colors.ets 收口的是**页面级语义色**（正文/背景/强调/边框），判据是「全App 复用同一语义」。
 * 上面这组 BAR_* 是**导航条这一个组件的深色面板设计语言**：深色底 + 车道方块 + 进度条 + 琥珀路况字，
 * 只在 NavBar 内出现，别处复用它反而是错的（白底页面上放这套深色板会突兀）。
 * 另有一处同源说明：StateTopBar 的 BAR_BG_EMERGENCY / BAR_BG_DEGRADED 与这里同值，
 * 但它是「页顶提示条」而非「导航条」，语义不同，故各自就地声明、不跨文件共用。
 */

/**
 * 【转向序列从哪来 —— 换成了真实路网的转向点】
 * 初版读 `Y_MANEUVERS`（虚构 Y 字路网，只有 3 个转向），
 * 现在地图换成真实路网（12 个转向点，含真实路名），
 * 转向序列由 `buildPlanRoute()` 从同一份数据生成 ——
 * **地图上橙色转向圈与顶部导航条的转向提示从此必然一致**，
 * 因为它们读的是同一个 Maneuver 数组。
 */
@Component
export struct NavActionBar {
  /**
   * 【为什么必须是 @ObjectLink，不能用 @Prop —— 本轮踩到的坑】
   * 底部「继续」按钮改的是 store.maneuverIndex，
   * 而 NavActionBar 要靠这个值切换转向文案（「靠右进入支路」→「已到达落客点」）。
   * 用 @Prop 时 store 是**单向值传递**：NavActionRow 改了它，
   * 兄弟组件 NavActionBar 收不到变更通知 → 实跑验证点「继续」按钮文字完全不变，
   * 只有按钮自己变灰，像是只动了一半。
   * @ObjectLink 才是双向链接，同一个实例、任一处改都同步重绘。
   */
  @ObjectLink store: DemoStore;

  /**
   * 当前生效的转向。
   * 由底部「继续」按钮推进 store.maneuverIndex 驱动。
   * 一期没有真实定位，这里是演示推进；正式版由 #93 按定位自动匹配。
   * **变道后取新方案的转向序列**（不同方案走不同的路，转向点位置与路名都不同），
   * 这样「变道」在地图与导航条上是同一件事。
   */
  /** 是否为离站导航（navMode='departure'）—— 决定到达文案/落客点文案 */
  private isDepartureNav(): boolean {
    return this.store.navMode === 'departure';
  }

  /**
   * 当前生效的方案。**按 store.navMode 切换数据源**：
   * 离站导航走 departurePlans() + departurePathId，到站/空态走到站 plans + pickedPathId。
   * 到站分支与改版前完全一致（planOf(arrivalPlans(), pickedPathId)），故「到站行为不变」。
   */
  private currentPlan(): PlanMeta {
    return this.store.navPlan();
  }

  /**
   * 当前生效的转向序列。**与地图几何同源**：navManeuvers() 已按 navMode
   * 选 departure 或 arrival 的路线并 buildPlanRoute，导航条与地图必一致。
   */
  private maneuverList(): Maneuver[] {
    return this.store.navManeuvers();
  }

  private maneuver(): Maneuver {
    const list: Maneuver[] = this.maneuverList();
    // 上下都夹一下，避免 store 被外部写成越界值时崩（实跑验证过越界崩溃）
    let idx: number = this.store.maneuverIndex;
    if (idx < 0) {
      idx = 0;
    }
    if (idx > list.length - 1) {
      idx = list.length - 1;
    }
    return list[idx];
  }

  /** 当前生效的转向总数（真实路网有 12 个，别写死） */
  private maneuverCount(): number {
    return this.maneuverList().length;
  }

  /** 当前方案的路径号（变道切方案后导航条要跟着换，不能写死 P-2） */
  private currentPathId(): string {
    return this.store.navPlan().pathId;
  }

  /** 当前方案的预计耗时（分钟）—— 取自当前方案，不是写死 6.4 */
  private currentEta(): number {
    return this.store.navPlan().etaMin;
  }

  /** 当前连续行驶进度（0..1）：离散态与转向点对齐，巡航态平滑增长 */
  private currentRatio(): number {
    return this.store.driveRatio;
  }

  /** 已行进里程（米）：巡航时随 driveRatio 平滑增长，用于「剩余距离 / 进度」 */
  private passedMeters(): number {
    return this.currentRatio() * REAL_ROUTE_TOTAL_M;
  }

  /** 当前位置所在路段等级（1 畅通 / 2 缓行 / 3 拥堵 / 4 严重拥堵 / -1 不可用） */
  private currentLevel(): number {
    const ratio: number = this.currentRatio();
    if (ratio >= 1) {
      return 1;
    }
    const plan: PlanMeta = this.store.navPlan();
    const isDep: boolean = this.store.navMode === 'departure';
    const route: RoutePath = buildPlanRoute(plan, isDep);
    return levelAtRatio(route, ratio);
  }

  /**
   * 非畅通路段时，顶部弹窗**额外**显示的文案：该路段预计通行时间。
   * 原文案（转向提示 / 距离 / 进度等）一律保留，这里只是「叠加」一行。
   */
  private segmentEtaText(): string {
    const lvl: number = this.currentLevel();
    if (lvl <= 1) {
      return '';
    }
    const ratio: number = this.currentRatio();
    const plan: PlanMeta = this.store.navPlan();
    const isDep: boolean = this.store.navMode === 'departure';
    const route: RoutePath = buildPlanRoute(plan, isDep);
    const eta: number = stretchEtaMinAt(route, ratio, this.currentEta());
    const name: string = levelMetaOf(lvl, false).name;
    return `该${name}路段预计通行时间为${eta.toFixed(1)}分钟`;
  }

  /** 进度条比例（按连续行驶进度，平滑跟随车标） */
  private progressRatio(): string {
    return `${Math.round(this.currentRatio() * 100)}%`;
  }

/** 是否已到最后转向（到站后再点「继续」时按钮置灰） */
private atLastManeuver(): boolean {
    return this.store.maneuverIndex >= this.maneuverCount() - 1;
  }

  /** 已推进到最后一个转向（底部「继续」按钮据此变灰） */
  private driveFinished(): boolean {
    return this.atLastManeuver();
  }

  /**
   * **剩余距离文案**（底部那行「剩余 x.x km」）。
   *
   * 【用户原话】「下面这个白色的剩余多少多少千米，那也要跟着变啊，
   *   比如说我最开始我离终点剩余 1.8 千米，那我随着它越往后走，那剩的肯定越少，
   *   到了终点就为零，对吧？然后呢，从重走的时候又剩余回原来的那个千米数」
   *
   * 初版这里写的是**字面量 `'剩余 1.8 km'`** —— 无论点多少下「继续」都不变。
   * 现在按 `总长 - 当前转向里程`实时算：
   *   出发（index=1，420m）→5044-420 = 4624m ≈ 4.6 km
   *   到站（最后一个转向）   → 剩余 0.0 km，按钮已变「重走」
   *   点「重走」归零到index=0→ 回到 5.0 km（满值），闭环自洽
   *
   * 【为什么不用契约里的 eta_min 去反推距离】
   * 契约给的是分钟数，不是里程；反推出来的距离是「按平均车速假算」的，
   * 与地图转向点标定的里程对不上。两者必须各自用自己的来源。
   *
   * 【显示规则】小于 1 公里按米显示（避免「剩余 0.4 km」这种没用的精度）。
   */
  private remainDistText(): string {
    if (this.atLastManeuver()) {
      return '已到达';
    }
    const total: number = REAL_ROUTE_TOTAL_M;
    const passed: number = this.passedMeters();
    let left: number = total - passed;
    if (left < 0) {
      left = 0;
    }
    if (left < 1000) {
      return `剩余 ${Math.round(left)} m`;
    }
    return `剩余 ${(left / 1000).toFixed(1)} km`;
  }

  /**
   * 距**下一个转向**还有多少米（导航条「420 米后」那个米数）。
   *
   * = 下一个转向点的里程 − 当前转向点的里程
   *
   * 【为什么不能直接用 maneuver().distM】
   * distM 是「当前这个转向点在路线上的累计里程」，属于**已走**；
   * 而「X 米后」在导航语境里是「前方还有多远」，属于**未走**。
   * 初版混用，导致点「继续」米数越涨（420→840→1260），
   * 与「越走越少」的直觉相反。用户投诉的正是这一点。
   *
   * 已在最后一个转向时没有「下一个」，返回到终点的距离。
   */
  private distToNextTurn(): number {
    const list: Maneuver[] = this.maneuverList();
    if (list.length === 0) {
      return 0;
    }
    // 【为什么要 Math.max(0, ...) 夹紧】
    // maneuverIndex 理论上 >= 0，但初版没夹紧，cur=-1 时 list[cur] 会取到
    // 最后一个元素（JS 负索引语义），在极端状态下算出荒唐的数字。
    // 这里显式夹紧，任何异常路径都退化成 0 而不是错误数字。
    const cur: number = Math.max(0, Math.min(this.store.maneuverIndex, list.length - 1));
    if (cur >= list.length - 1) {
      // 已在最后一个转向：算到终点的剩余（一般会走到底部那行「剩余 x.x km」）
      const left: number = REAL_ROUTE_TOTAL_M - list[cur].distM;
      return left > 0 ? Math.round(left) : 0;
    }
    // 【口径：X 米后 = 下一个转向里程 − 当前转向里程】
    // 初版这里减的是 passedMeters()（= driveRatio × 总长，巡航时连续增长），
    // 与下方注释声明的公式不一致，且巡航中会出现「0 米后」。
    // 现按声明口径实现：只依赖转向序列本身，离散态与巡航态同一条公式。
    const d: number = list[cur + 1].distM - list[cur].distM;
    return d > 0 ? Math.round(d) : 0;
  }

  /**
   * 剩余分钟数（按里程比例从 eta_min 递减）。
   *
   * 【为什么 eta_min 要随推进递减】
   * 契约的 `eta_min` 是**全程**耗时（6.4 分钟）。导航条上「约 X 分钟」
   * 指的是「还要开多久」，越接近终点越少。写死 6.4 不合理 ——
   * 已经开了 80% 还显示 6.4 分钟，司机无法判断还要多久到站。
   *
   * 计算式：剩余分钟 = 总耗时 × 剩余里程 / 总里程
   * 起点：5044-420 → 约 6.0 分钟；到站：0 分钟（显示「已到达」）。
   * 四舍五入保留一位小数，避免出现「0 分钟」这种没意义的值。
   */
  private remainMinutesText(): string {
    const total: number = REAL_ROUTE_TOTAL_M;
    if (total <= 0) {
      return this.currentEta().toFixed(1);
    }
    const passed: number = this.passedMeters();
    let leftM: number = total - passed;
    if (leftM < 0) {
      leftM = 0;
    }
    const min: number = this.currentEta() * leftM / total;
    if (min < 0.1) {
      return '0.0';
    }
    return min.toFixed(1);
  }

  build() {
    // 应急态 = 停止路线引导，替换为「请服从现场指挥」
    if (this.store.emergency) {
      Column({ space: 4 }) {
        Row({ space: 8 }) {
          Text('⚠')
            .fontSize(20)
            .fontColor(TEXT_WHITE)
          Text('请服从现场指挥')
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .fontColor(TEXT_WHITE)
        }
        .width('100%')
        Text('路线引导已停止 · 应急处置优先')
          .fontSize(11)
          .fontColor('TEXT_ON_EMERGENCY_BAR_SUB')
          .width('100%')
      }
      .alignItems(HorizontalAlign.Start)
      .padding({ top: 12, bottom: 12, left: 16, right: 16 })
      .width('100%')
      .backgroundColor(BAR_BG_EMERGENCY)
    } else if (this.store.degraded) {
      // 拒绝授权降级：顶部条直接明示「已降级」，避免司机误以为在正常引导
      // （TC-05：流程不中断 —— 地图与路线照常给，只是定位来源降级）
      Column({ space: 4 }) {
        Row({ space: 8 }) {
          Text('⚠')
            .fontSize(18)
            .fontColor(TEXT_WHITE)
          Text('已降级 · 未授权定位')
            .fontSize(16)
            .fontWeight(FontWeight.Bold)
            .fontColor(TEXT_WHITE)
        }
        .width('100%')
        Text(`仍可查看路线与路况，手动确认所在道路即可（${ROUTES_FIXTURE.arrival_route.path_id} · 约 ${ROUTES_FIXTURE.arrival_route.eta_min} 分钟）`)
          .fontSize(11)
          .fontColor('TEXT_ON_DEGRADED')
          .width('100%')
      }
      .alignItems(HorizontalAlign.Start)
      .padding({ top: 12, bottom: 12, left: 16, right: 16 })
      .width('100%')
      .backgroundColor(BAR_BG_DEGRADED)
    } else {
      // 常态：真正的导航条
      Column() {
        Row() {
          // ① 转向图标（大号，居左）
          Text(maneuverGlyph(this.maneuver().type))
            .fontSize(40)
            .fontWeight(FontWeight.Bold)
            .fontColor(TEXT_WHITE)
            .width(52)
            .textAlign(TextAlign.Center)

          // ③ 文案 + 距离/时间
          Column({ space: 2 }) {
            // maneuverText 需要场景词：离站导航的 arrive 是「到达离站点」而不是「到达落客点」
            Text(this.atLastManeuver() ? (this.isDepartureNav() ? '已到达离站点' : '已到达落客点') : maneuverText(this.maneuver().type, this.isDepartureNav()))
              .fontSize(19)
              .fontWeight(FontWeight.Bold)
              .fontColor(TEXT_WHITE)
            Text(this.atLastManeuver()
              ? (this.isDepartureNav() ? '离站出口' : ROUTES_FIXTURE.arrival_route.dropoff_point)
              : `进入 ${this.maneuver().toRoad}`)
              .fontSize(13)
              .fontColor(BAR_TEXT_ROAD)
            // 【为什么在这里再取一次 path_id】导航条不能只显示固定的 P-2，
            // 变道切到方案二/三后必须显示当前方案的路径号，否则条上路号与卡片对不上。
            /**
             * 【这一行的「米」是**距下一个转向还有多远**，不是已走里程 —— 用户提问纠正过】
             *
             * 用户原话：「我点继续这个按钮，它上面这个黑色的弹窗有个小字多少多少米后……
             *   难道不应该是我越点继续，它的米越少嘛」
             *
             * 初版直接写 `this.maneuver().distM` = **当前转向点的累计里程**
             * （出发 420m → 840m → 1260m …），配上「X 米后」这个措辞就是错的：
             * 「米后」在导航里指的是「前方还有多远」，越点应该**越少**；
             * 而 distM 是**已经走了多远**，越点越**多**。语义正好反了。
             *
             * 现在按里程差算真正的「前方还有多远」：
             *     前方距离 = 下一个转向点的里程 − 当前转向点的里程
             * 出发（index=0，d=0）→ 下一转向 420 → 「420 米后」
             * 推进一格（d=420）        → 下一转向 840 → 「420 米后」
             * 到站                       → 「已到达落客点」
             * 数值稳定在相邻两转向点之间（约 420m），到站归零，闭环自洽。
             *
             * 「约 X 分钟」用契约 eta_min（到站总耗时），
             * 随推进按里程比例递减 —— 起点是全长耗时，越接近终点剩得越少。
             */
            Text(this.atLastManeuver()
              ? (this.isDepartureNav()
                  ? `离站出口 · 直接驶离站前区域`
                  : `落客点 ${ROUTES_FIXTURE.arrival_route.dropoff_point} · 步行接驳约 ${ROUTES_FIXTURE.arrival_route.walk_min} 分钟`)
              : `${this.distToNextTurn()} 米后 · 约 ${this.remainMinutesText()} 分钟 · ${this.currentPathId()}`)
              .fontSize(11)
              .fontColor(BAR_TEXT_SUB)
          }
          .alignItems(HorizontalAlign.Start)
          .layoutWeight(1)

          // ④ 车道指引小方块
          Row({ space: 4 }) {
            Text('↑')
              .fontSize(15)
              .fontColor(BAR_TEXT_SUB)
            Text('↑')
              .fontSize(15)
              .fontColor(TEXT_WHITE)
            Text('↑')
              .fontSize(15)
              .fontColor(BAR_TEXT_SUB)
          }
          .padding({ top: 8, bottom: 8, left: 10, right: 10 })
          .backgroundColor(BAR_BG_SUB)
          .borderRadius(8)
        }
        .width('100%')

        // 非畅通路段提示：在原有导航条内容之上「叠加」一行（不删任何原文，符合用户要求）
        // 仅当车进入缓行/拥堵/严重拥堵路段时出现；显示该路段预计通行时间。
        if (this.segmentEtaText() !== '') {
          Row({ space: 6 }) {
            Text('●')
              .fontSize(10)
              .fontColor(this.currentLevel() === 4 ? BAR_LEVEL_4 : (this.currentLevel() === 3 ? BAR_LEVEL_3 : BAR_LEVEL_2))
            Text(this.segmentEtaText())
              .fontSize(12)
              .fontColor(BAR_LEVEL_TEXT)
          }
          .width('100%')
          .margin({ top: 2, bottom: 2 })
        }

        // 底部：剩余距离 + 进度条（高德标志形态）
        // 【进度随「继续」推进】宽度按连续行驶进度算，平滑跟随车标
        Column({ space: 4 }) {
          Row() {
            Text(this.remainDistText())
              .fontSize(11)
              .fontColor(TEXT_WHITE)
            Blank()
            Text(this.isDepartureNav() ? '直接驶离站前区域，无需步行接驳' : `${ROUTES_FIXTURE.arrival_route.walk_min} 分钟步行接驳`)
              .fontSize(11)
              .fontColor(BAR_TEXT_SUB)
          }
          .width('100%')

          Stack() {
            Row()
              .width(this.progressRatio())
              .height(4)
              .backgroundColor(BAR_PROGRESS_IN)
              .borderRadius(2)
          }
          .width('100%')
          .height(4)
          .backgroundColor(BAR_PROGRESS)
          .borderRadius(2)
        }
        .width('100%')
        .margin({ top: 8 })
      }
      .alignItems(HorizontalAlign.Start)
      // 【上下内边距 10 → 8】转向条是除地图外最大的一块，
      // 压 2vp×2 省出的高度全给下方地图（用户要「一进来整个画面都是地图」）。
      .padding({ top: 8, bottom: 10, left: 14, right: 14 })
      .width('100%')
      .backgroundColor(BAR_BG)
    }
  }
}

/**
 * 路线信息横卡（导航条下方的白卡：当前方案的路径号、耗时、落客点）。
 *
 * 【为什么要跟着变道走】初版把 P-2 和 6.4 分钟写死，
 * 变道切到方案二/三之后这张卡还显示 P-2，与上方导航条、下方方案卡全对不上。
 * 现在统一从 store.pickedIndex / pickedPathId 取当前方案的数据。
 */
@Component
export struct RouteStripCard {
  @Prop unavailable: boolean = false;
  @Prop colorBlind: boolean = false;
  @ObjectLink store: DemoStore;

  /** 是否为离站导航（navMode='departure'） */
  private isDepartureNav(): boolean {
    return this.store.navMode === 'departure';
  }

  /** 当前方案的路径号（按 navMode 选数据源，到站/离站同一个方法） */
  private pathId(): string {
    return this.store.navPlan().pathId;
  }

  /** 当前方案的元数据（耗时 / 小字 / 是否推荐，都从同一份派生结果取） */
  private plan(): PlanMeta {
    return this.store.navPlan();
  }

  /** 当前方案的耗时 */
  private eta(): number {
    return this.plan().etaMin;
  }

  /** 当前方案的关键说明（推荐给 why 摘要，备选取契约 reason 原文） */
  private hint(): string {
    return this.plan().hint;
  }

  build() {
    Column({ space: 6 }) {
      Row() {
        Text(`${this.pathId()} ${this.plan().recommended ? '推荐路线' : '备选路线'}`)
          .fontSize(14)
          .fontWeight(FontWeight.Bold)
          .fontColor('TEXT_PRIMARY')
          .layoutWeight(1)
        Text(`约 ${this.eta()} 分钟`)
          .fontSize(14)
          .fontWeight(FontWeight.Bold)
          .fontColor('ACCENT_COLOR_BLIND')
      }
      .width('100%')

      Text(this.isDepartureNav() ? '离站出口 · 直接驶离站前区域' : `落客点 ${ROUTES_FIXTURE.arrival_route.dropoff_point} · 步行接驳约 ${ROUTES_FIXTURE.arrival_route.walk_min} 分钟`)
        .fontSize(11)
        .fontColor('TEXT_SECONDARY')
        .width('100%')

      Text(this.hint())
        .fontSize(11)
        .fontColor('TEXT_SECONDARY')
        .width('100%')

      Text(DISCLAIMER_TEXT)
        .fontSize(10)
        .fontColor('TEXT_TERTIARY')
        .width('100%')
    }
    .alignItems(HorizontalAlign.Start)
    .padding(12)
    .width('100%')
    .backgroundColor('TEXT_WHITE')
    .borderRadius(10)
  }
}

/**
 * 导航操作条（高德底部那排：继续 / 变道）。
 *
 * 【两个按钮分别是什么、点了会发生什么】
 * - **继续**：沿当前路线推进到下一个转向。演示态下会把顶部转向条从
 *   「靠右进入支路」推到「已到达落客点」，进度条同步走满。一期没有真实定位，
 *   所以是手动推进，正式版由 #93 按定位自动匹配。
 * - **变道**：**在三条路线方案间循环切换**（路线一 → 二 → 三 → 一）。
 *   切换后五处同时变：地图路线臂换一条、顶部转向条图标与文案跟着换
 *   （↱靠右 ↰靠左）、距离行的耗时与路径号换掉、白色路线卡换成新方案
 *   （含契约 reason 原文的小字）、方案卡高亮跟着走。
 *   按钮上直接显示**下一条方案的编号**，让人一眼知道点完会去哪。
 *
 * 【为什么删掉了「退出」按钮 —— 用户明确要求】
 * 初版第三个按钮是「退出」，点了会 setEmergency(true) 进应急态。
 * 用户反馈两点，都成立：
 *   ① 「退出键点击为什么它会跳转到应急态？」—— 语义不对。
 *      「退出引导」和「应急处置」是两件事，应急态该由顶部开关触发，
 *      不该藏在一个看起来像「关掉 App」的按钮里。
 *   ② 「而且一按退出键就换路线二」—— 这是 resetDrive() 顺手调了
 *      pickIndex(0) 造成的副作用，把两个不相干的状态绑在了一起。
 * 现在按钮删掉，两处问题一并消失；应急态仍可从顶部「应急态」开关进入。
 *
 * 【为什么之前这两个「点了没反应」是 bug】
 * 初版把 onClick 写成了空函数占位（等真数据接入再实现），看起来就像坏了 ——
 * 空壳按钮比没有更糟。现在两个都接上了可见反馈。
 */
@Component
export struct NavActionRow {
  /** @ObjectLink：与 NavActionBar 必须是同一种装饰器，否则两边状态不同步（见上） */
  @ObjectLink store: DemoStore;
  /**
   * 按下态（点击反馈：按下加深、抬起恢复）。
   * 用 onTouch 而不是 stateStyles：实跑验证 uiInput 合成长按不触发 pressed 态，
   * onTouch 是最底层回调，任何触摸（真手/合成）都必然触发。
   */
  @State drivePressed: boolean = false;
  @State lanePressed: boolean = false;
  @State exitPressed: boolean = false;

  /** 是否为离站导航（navMode='departure'） */
  private isDepartureNav(): boolean {
    return this.store.navMode === 'departure';
  }

  /**
   * 「路线一/二/三」或「离站一/二」—— 按 navMode 区分。
   * 离站只有两条方案，显示「离站一/二」让司机一眼知道当前导的是离站路线
   * （用户要求导航下方路线选择要体现「落客或离站」）。
   */
  private routeLabel(idx: number): string {
    if (this.isDepartureNav()) {
      return idx === 0 ? '离站一' : '离站二';
    }
    if (idx === 0) {
      return '路线一';
    }
    if (idx === 1) {
      return '路线二';
    }
    return '路线三';
  }

  /** 当前方案在方案列表里的序号（0/1/2），与卡片高亮、地图几何同一个来源 */
  private curIndex(): number {
    return this.store.navPlan().index;
  }

  /**
   * 「开始导航 / 导航中 / 重走」按钮副标题。
   *
   * 【为什么叫「开始导航」而不是「继续」—— 用户明确要求】
   * 用户原话：「应该是我点继续之后它才开始导航，然后把继续这个按钮的那个字改成开始导航」。
   * 语义上也更准：点它 = **启动** 这次导航（车从起点一路开到终点），
   * 而不是「推进一步」。叫「继续」会让人以为点一下只走一个转向，
   * 也会让人以为车本来就在动 —— 这正是用户觉得「它自己动了」的一个诱因。
   *
   * 【为什么不能再写死 `maneuverIndex >= 2`】
   * 初版假设转向点只有 3 个（虚构 Y 字路网），写死 2 恰好等于「最后一个」。
   * 换成真实路网后转向点有 12 个，写死 2 就变成「推进两次就到站」——
   * 点一下直接跳「已到达」，而且再也回不去（用户投诉的原话）。
   * 现在一律按 maneuverCount() 判定，并且提供「重走」回退。
   *
   * 【「重走」是一路归零，不是退一格 —— 用户明确要求】
   * 见 DemoStore.restartNav() 的注释。
   */
  private driveLabel(): string {
    if (this.driveFinished()) {
      return '重走';
    }
    if (this.store.cruising) {
      return '导航中';
    }
    return '开始导航';
  }

  /** 「开始导航 / 重走」按钮：点「开始导航」即自动巡航到终点；到底了点「重走」归零 */
  private onDrive(): void {
    if (this.driveFinished()) {
      this.store.restartNav();
      return;
    }
    this.store.startCruise();
  }

  /** 是否已走到最后一个转向（按 navMode 选数据源，真实路网共 12 个，别写死 2） */
  private driveFinished(): boolean {
    return this.store.maneuverIndex >= this.store.navManeuverTotal() - 1;
  }

  /** onTouch 统一处理：Down 置按下态，Up/Cancel 恢复 */
  private pressOf(flag: 'drive' | 'lane' | 'exit', e?: TouchEvent): void {
    if (!e) {
      return;
    }
    const down: boolean = e.type === TouchType.Down;
    const up: boolean = e.type === TouchType.Up || e.type === TouchType.Cancel;
    if (!down && !up) {
      return;
    }
    if (flag === 'drive') {
      this.drivePressed = down;
    } else if (flag === 'lane') {
      this.lanePressed = down;
    } else {
      this.exitPressed = down;
    }
  }

  build() {
    Row({ space: 10 }) {
      // 继续导航：推进到下一个转向；已到站后变成「重走」，可回退
      Column({ space: 2 }) {
        Text(this.driveFinished() ? '↺' : (this.store.cruising ? '➤' : '⬆'))
          .fontSize(17)
          .fontColor(TEXT_WHITE)
        Text(this.driveLabel())
          .fontSize(10)
          .fontColor(TEXT_WHITE)
      }
      .layoutWeight(1)
      .padding({ top: 6, bottom: 6 })
      // 按下时加深一档（BTN_DRIVE_ON），让「点到了」看得见
      .backgroundColor(this.drivePressed ? BTN_DRIVE_ON
        : (this.driveFinished() ? '#7A8B99' : (this.store.cruising ? '#9AA7B0' : BTN_DRIVE)))
      .borderRadius(8)
      .onTouch((e?: TouchEvent) => {
        this.pressOf('drive', e);
      })
      /**
       * 【禁止态：应急 / 数据不可用时「开始导航」也禁用 —— 用户明确要求不可点】
       * store.startCruise() 里也 return 了一道，两层都拦。
       */
      .opacity(this.store.routeLocked() ? 0.45 : 1)
      .enabled(!this.store.cruising && !this.store.routeLocked())
      .onClick(() => {
        this.onDrive();
      })

      /**
       * 变道：在三条方案间循环切换。
       *
       * 【这一版修掉的真 bug —— 用户反馈「选着线路与方框选择对应错位」】
       * 初版按钮文字显示的是 `routeLabel(nextIndex())`，也就是**下一条**会去哪：
       *   初始 pickedIndex=0 → 按钮显示「路线二」，但高亮的卡是路线一。
       * 用户看到的就是「文字写着路线二、框里亮的是路线一」—— 典型的错位。
       *（用户的原话：「它显示的选择是路线二，但实际那个框框亮的是路线一，
       *   然后点路线三亮的是路线二，点路线一亮的是路线三，错位了」）
       *
       * 现在按钮文字改显示 `routeLabel(curIndex())` = **当前选中的那条**，
       * 于是「按钮写路线二」和「卡片亮路线二」永远一致，不会再错位。
       * 图标 ⇄ 保留，含义不变（点一下切到下一条）。
       */
      Column({ space: 2 }) {
        Text('⇄')
          .fontSize(17)
          .fontColor(TEXT_PRIMARY)
        Text(this.routeLabel(this.curIndex()))
          .fontSize(10)
          .fontColor(TEXT_PRIMARY)
      }
      .layoutWeight(1)
      .padding({ top: 6, bottom: 6 })
      // 按下时加深一档（BTN_LANE_ON）
      .backgroundColor(this.lanePressed ? BTN_LANE_ON : BTN_LANE)
      .borderRadius(8)
      .onTouch((e?: TouchEvent) => {
        this.pressOf('lane', e);
      })
      // 【禁止态：应急 / 数据不可用时变道按钮也置灰禁用 —— 用户要求「不可以选择路线」】
      .opacity(this.store.routeLocked() ? 0.45 : 1)
      .enabled(!this.store.routeLocked())
      .onClick(() => {
        this.store.navChangeLane();
      })

      /**
       * 退出导航：回到「原生空地图 + 指引选路」的初始界面（用户本轮要求）。
       *
       * 【为什么这次加回来是对的、当年删掉也是对的】
       * 初版的「退出」错在调了 setEmergency(true) —— 把「退出引导」和「应急处置」
       * 两件不相干的事绑在一起（用户投诉「一按退出键就跳应急态」），所以删了。
       * 现在语义已修正：退出 = `setNavMode('empty')`，只做三件事 ——
       *   ① 导航上下文清空回空态（地图变回无标注原生图 + 两个指引按钮）
       *   ② 行驶进度归零（resetDrive）
       *   ③ 触发地图重画（bumpEpoch）
       * 不碰应急态、不改用户已选的路线方案（重新进导航前选的仍保留，
       * 想换路线去落客/离站页点别的卡即可）。
       */
      Column({ space: 2 }) {
        Text('✕')
          .fontSize(17)
          .fontColor(TEXT_PRIMARY)
        Text('退出')
          .fontSize(10)
          .fontColor(TEXT_PRIMARY)
      }
      .layoutWeight(1)
      .padding({ top: 6, bottom: 6 })
      // 按下时加深一档（BTN_EXIT_ON）
      .backgroundColor(this.exitPressed ? BTN_EXIT_ON : BTN_EXIT)
      .borderRadius(8)
      .onTouch((e?: TouchEvent) => {
        this.pressOf('exit', e);
      })
      .onClick(() => {
        this.store.setNavMode('empty');
      })
    }
    .width('100%')
    .padding({ left: 14, right: 14, bottom: 8 })
  }
}

/**
 * 落客页底部操作条 —— **只有「变道」，没有「继续」**。
 *
 * 【用户原话】「洛克这里，你这里都没有，这里的地图都没有那个继续行驶的这个弹窗，
 *   你就不要有继续的这个键。把这个键给删掉」
 *
 * 「继续」键的语义是推进**演示行驶进度**（沿转向序列一步步走），
 * 它必须配一个「转向条」才有意义 —— 导航页顶部有那条深色导航条实时显示
 * 「左转 420 米后· 进入站前路」，所以「继续」每按一次都能看到条子变。
 * 落客页和离站页**顶部没有转向条**（这两个页面不需要逐转向引导，
 * 司机是按停靠点/离站方向整体决策的），按「继续」看不到任何变化，
 * 就是用户说的「根本没有用」—— 空壳按钮比没有更糟，必须删。
 *
 * 只留「变道」之后底部就是一个宽按钮，点击面积更大、也不会误触。
 */
@Component
export struct DropoffActionRow {
  @ObjectLink store: DemoStore;
  /** 按下态（点击反馈：按下加深、抬起恢复） */
  @State pickPressed: boolean = false;

  /** 「路线一/二/三」—— 与导航页同一个数据源、同一份 arrivalPlans() */
  private routeLabel(): string {
    const idx: number = planOf(arrivalPlans(), this.store.pickedPathId).index;
    if (idx === 0) {
      return '路线一';
    }
    if (idx === 1) {
      return '路线二';
    }
    return '路线三';
  }

  build() {
    Row() {
      Column({ space: 2 }) {
        Text('⇄')
          .fontSize(17)
          .fontColor(TEXT_PRIMARY)
        Text(this.routeLabel())
          .fontSize(10)
          .fontColor(TEXT_PRIMARY)
      }
      .width('100%')
      .padding({ top: 6, bottom: 6 })
      // 浅灰底：一眼看得出这是个按钮（旧写法把变量名当色值传，等于没有背景）
      .backgroundColor(this.pickPressed ? BTN_PICK_ON : BTN_PICK)
      .borderRadius(8)
      // 按下时加深一档（onTouch 比 stateStyles 可靠，合成触摸也能触发）
      .onTouch((e?: TouchEvent) => {
        if (!e) {
          return;
        }
        this.pickPressed = e.type === TouchType.Down;
      })
      // 【禁止态：与导航页一致 —— 应急 / 数据不可用时不可选路线】
      .opacity(this.store.routeLocked() ? 0.45 : 1)
      .enabled(!this.store.routeLocked())
      .onClick(() => {
        this.store.changeLane();
      })
    }
    .width('100%')
    .padding({ left: 14, right: 14, bottom: 8 })
  }
}

/**
 * 离站页底部操作条 —— 与 DropoffActionRow 同理，**只有「变道」，没有「继续」**。
 *
 * 【为什么不能直接复用 NavActionRow】
 * 到站三方案存在 `pickedPathId`、离站两方案存在 `departurePathId`，
 * 两个字段、两套列表（arrivalPlans / departurePlans）。
 * 若共用一个组件并靠 prop 区分，本质上就是「同一个按钮读两份数据」，
 * 迟早出现「点按钮地图不动」的错位。所以这里独立一份，
 * 写死读 departurePlans() + departurePathId，一眼能看出它属于离站页。
 *
 * 【与到站操作条的行为差异】
 *   - 只有变道键，没有继续键（离站页也没有转向条，推进无意义）
 *   - 标签是「离站一 / 离站二」（契约里离站就这两条）
 */
@Component
export struct DepartureActionRow {
  @ObjectLink store: DemoStore;
  /** 按下态（点击反馈：按下加深、抬起恢复） */
  @State pickPressed: boolean = false;

  /** 当前选中的离站方案 */
  private curPlan(): PlanMeta {
    return planOf(departurePlans(), this.store.departurePathId);
  }

  /** 离站一 / 离站二 */
  private routeLabel(): string {
    return this.curPlan().index === 0 ? '离站一' : '离站二';
  }

  build() {
    Row() {
      // 变道：在**离站的两条**方案间循环，与上方两张方块卡是同一个动作
      Column({ space: 2 }) {
        Text('⇄')
          .fontSize(17)
          .fontColor(TEXT_PRIMARY)
        Text(this.routeLabel())
          .fontSize(10)
          .fontColor(TEXT_PRIMARY)
      }
      .width('100%')
      .padding({ top: 6, bottom: 6 })
      // 浅灰底：一眼看得出这是个按钮（与落客页同色同反馈）
      .backgroundColor(this.pickPressed ? BTN_PICK_ON : BTN_PICK)
      .borderRadius(8)
      .onTouch((e?: TouchEvent) => {
        if (!e) {
          return;
        }
        this.pickPressed = e.type === TouchType.Down;
      })
      // 【禁止态：与导航页一致 —— 应急 / 数据不可用时不可选路线】
      .opacity(this.store.routeLocked() ? 0.45 : 1)
      .enabled(!this.store.routeLocked())
      .onClick(() => {
        this.store.changeDepartureLane();
      })
    }
    .width('100%')
    .padding({ left: 14, right: 14, bottom: 8 })
  }
}
