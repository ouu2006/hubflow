import { ROUTES_FIXTURE, segmentLevelOf } from '../common/Fixture';
import { DemoStore } from '../common/DemoStore';
import { PlanMeta, arrivalPlans, departurePlans } from '../common/RoutePlan';
import { levelMetaOf } from '../common/LevelMeta';
import {
  TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, TEXT_WHITE, BG_GRAY_LIGHTER, BG_SELECTED, BORDER_ACCENT, ACCENT_COLOR_BLIND
} from '../common/Colors';

/**
 * 路线方案方块卡（参考高德导航「路线方案」那排横向卡片）。
 *
 * 【为什么改成方块卡而不是纵向长列表】
 * 原来推荐 + 备选是纵向排列的长条目，一条一条往下堆，要滑很久才能看完三个方案，
 * 且每条只有「路径号 + 时间 + 原因」三行字，横着对比看不出差别。
 * 高德的做法是把候选方案并成横向卡片，一屏能同时看到全部方案，
 * 每张卡下方用小字标出**关键差异点**（几个信号口 / 要不要掉头 / 有没有排队），
 * 司机横向扫一眼就能选。所以这里照这个结构做。
 *
 * 【数据来源：全部取自fixture，不新增字段】
 * - 推荐 = arrival_route（path_id / eta_min）
 * - 备选 = alternatives（path_id / eta_min / reason）
 * - 小字里的「几个信号口 / 要不要掉头」是从 alternatives[].reason 原样取，
 *   reason 本身就是契约里的自然语言原因（如「多经过 1 个信号路口」「需绕行掉头」），
 *   直接展示即可，不做二次编造，也不动契约。
 * - 剩余预约量取自 quota（契约 §2.1 数组口径）。
 *
 * 【为什么用 @Component 而不是 @Builder】
 * @Builder 的值参数只在创建时求值一次（实跑验证点开关后卡片不刷新），
 * 所以做成子组件 + @Prop 入参，父态一变必然整卡重绘。
 */

/** 单张方案卡的入参 */
@Component
export struct RouteOptionCard {
  /** 展示序号，如「路线一」 */
  @Prop title: string = '';
  @Prop pathId: string = '';
  @Prop etaMin: number = 0;
  /** 关键信息小字（多信号口 / 需掉头 / 无排队…），取自契约 reason */
  @Prop hint: string = '';
  /** 剩余可预约量；-1 表示 fixture 未给 */
  @Prop remaining: number = -1;
  /** 是否为当前推荐 */
  @Prop recommended: boolean = false;
  /** 是否为当前选中的方案 */
  @Prop selected: boolean = false;
  /**
   * 该方案的路况构成小字（如「畅通 · 拥堵 · 畅通」）。
   *
   * 【为什么必须有这一行 —— 用户投诉「不要乱标」】
   * 用户看到地图上一段红一段黄，但下面卡片没写这是哪一段拥堵，
   * 就会怀疑颜色是乱标的。把这条方案的路段等级直接写出来，
   * 司机自己就能核对地图上那段红对应的是哪个路段。
   * 这一行与地图着色读的是**同一个** segmentLevelOf()，不可能对不上。
   */
  @Prop levelsText: string = '';
  /** 路况等级色点（与地图上该方案的主色调一致） */
  @Prop levelDots: number[] = [];
  @Prop colorBlind: boolean = false;
  @Prop unavailable: boolean = false;
  /**
   * 是否处于「禁止选路线」状态（应急态 / 数据不可用，由父组件 RouteOptionRow 判定后传入）。
   *
   * 【为什么必须由父组件传，而不是卡片自己读 store】
   * RouteOptionCard 是纯展示组件、不持有 @ObjectLink store（它只有一组 @Prop），
   * 直接写 this.store.emergary 编译不过（Property 'store' does not exist）。
   * 而且这样分层更干净：**判定集中在一处**（父组件读 routeLocked），
   * 卡片只负责「按locked 把视觉变灰 + 禁用」，不再各自判断规则。
   */
  @Prop locked: boolean = false;

  /**
   * 【禁止态下的「有效选中态」= false —— 应急 / 数据不可用一律退灰（TC-11）】
   *
   * 【为什么必须这样，而不能只靠 .opacity(0.45)】
   * 只加透明度时，屏幕上仍是「路线一」蓝底白字 + P-2 蓝字 + ✓ 蓝对勾 +
   * 2px 蓝边框 + 淡蓝卡底 —— 一整套「已选中」信号。而数据都拿不到 /
   * 已停止引导时，**根本不存在「选中的路线」这回事**，继续亮蓝等于骗司机。
   * .opacity() 只是淡化，蓝色仍在，直接违反 TC-11。
   *
   * 【⚠️ 为什么这个判定不能写成 private get —— 本轮实跑验证的第二个坑】
   * 初版写成 `private get isPicked(): boolean { return this.selected && !this.locked; }`
   * 结果**常态下选中态整套视觉全部失效**（诊断文本 sel=true lock=false，
   * 但标题底色/边框/对勾全是未选中分支），像素统计卡片区蓝像素 = 0。
   * 原因：ArkUI 的响应式只跟踪「被装饰成员被直接读取」的位置，
   * **`get` 访问器不是响应式上下文**，其返回值会被当成与状态无关的常量。
   * 修法：改成 `build()` 里的普通局部变量，每次渲染现算。
   *
   * 【双重保险】视觉退灰（下面三个方法）+ 交互禁用（.enabled +
   * onClick 里 routeLocked() return），两条通道同时封死。
   *
   * 【最终形态：普通方法，不是 get，也不是 build 里的 const】
   * 试过三种写法，两种都编译不过：
   *   ① private get isPicked() —— 能编译，但**运行时取值失效**（本轮实跑验证，见上）
   *   ② build() 开头 const —— 报「build 只能有一个根节点」
   *   ③ Column 内 const —— 报「这里只能写 UI 组件语法」
   * 只有**普通方法**可行：ArkUI 每次渲染都会重新调用它，值一定最新。
   * 离站页 DeparturePage 的 isPickedOf() 一直是这个写法，两页现在一致。
   */
  private isPickedNow(): boolean {
    return this.selected && !this.locked;
  }

  /** 选中态底色：禁止态一律灰（TC-11），不得出现任何蓝色 */
  private pickBgNow(): string {
    return this.isPickedNow() ? BG_SELECTED : BG_GRAY_LIGHTER;
  }

  /** 选中态边框色：禁止态一律灰 */
  private pickBorderNow(): string {
    return this.isPickedNow() ? ACCENT_COLOR_BLIND : BORDER_ACCENT;
  }
  build() {
    Column({ space: 3 }) {
      // 顶部：方案名 + 选中标记
      /**
       * 【这一版修掉的真 bug —— 用户反馈「选择哪个亮哪个」】
       * 初版：标题底色由 `this.recommended` 决定，
       * 而 recommended 是**写死**的（路线一 true、路线二/三 false）。
       * 于是不管点哪张卡，永远只有「路线一」三个字是蓝底 —— 用户的原话：
       *   「路线一方框内线路一三字用蓝色标亮，但选择其他线路后仍旧是那三个字标亮，
       *     我要让他选择哪个亮哪个」
       * 现在：底色/字色一律由 **`this.selected`** 驱动 ——
       * 选路线二就是「路线二」蓝底白字，路线一和路线三都退回灰底。
       * recommended 只用来在标题后面挂一个「推荐」小字，不再控制颜色。
       */
      Row({ space: 4 }) {
        Text(this.title)
          .fontSize(12)
          .fontWeight(FontWeight.Bold)
          .fontColor(this.isPickedNow() ? TEXT_WHITE : '#33404A')
          .padding({ top: 2, bottom: 2, left: 6, right: 6 })
          .backgroundColor(this.isPickedNow() ? ACCENT_COLOR_BLIND : '#D5DEE4')
          .borderRadius(4)
        // 「推荐」是**独立的小字标记**，跟颜色解耦。
        // 这样「推荐」和「当前选中」是两件事：默认选中路线一（它就是推荐），
        // 切到路线二时，路线一仍保留「推荐」字样但底色变灰 —— 语义正确。
        Text(this.recommended ? '推荐' : '')
          .fontSize(9)
          .fontColor(TEXT_TERTIARY)
        Blank()
        // 【✓ 也无条件渲染】初版写成 `if (this.recommended)`，
        // 推荐卡多一个对勾行 → 高度比另两张多一行，三卡参差不齐。
        // 现在恒定输出，只是颜色随选中与否变化，**保证三卡等高**。
        Text('✓')
          .fontSize(12)
          .fontWeight(FontWeight.Bold)
          .fontColor(this.isPickedNow() ? ACCENT_COLOR_BLIND : '#C3CDD4')
      }
      .width('100%')
      // 【Row 必须限宽，否则卡内子元素会按内容撑开】
      // 实跑验证「路线三」的长小字把卡片顶到屏幕右边界外。
      .constraintSize({ maxWidth: '100%' })

      // 路径号 + 时间
      Text(this.pathId)
        .fontSize(20)
        .fontWeight(FontWeight.Bold)
        .fontColor(this.isPickedNow() ? ACCENT_COLOR_BLIND : TEXT_PRIMARY)
        .maxLines(1)

      Text(`约 ${this.etaMin} 分钟`)
        .fontSize(11)
        .fontColor(TEXT_PRIMARY)
        .maxLines(1)

      /**
       * 【路况构成：色点 + 等级名】
       *
       * 这是本轮新加的一行，对应用户投诉「地图路线标色与下面路线选择说明要一致」。
     * 色点画的是**该方案真实经过的路段等级**，与地图上那一段的颜色同一个来源
     * （都来自 segmentLevelOf），所以司机可以逐段核对，不存在「乱标」。
     * 去色校验开启时色点统一灰，但等级名（畅通/缓行/拥堵）仍保留 ——
     * 手册 §11.3 要求颜色之外还有文字通道，这就是那个通道。
       */
      Row({ space: 3 }) {
        ForEach(this.levelDots, (lv: number) => {
          Text('●')
            .fontSize(8)
            .fontColor(this.colorBlind || this.unavailable || lv < 1
              ? '#8B8B8B'
              : levelMetaOf(lv, false).color)
        }, (lv: number, idx: number) => `dot_${this.pathId}_${idx}_${lv}`)
        Text(this.levelsText)
          .fontSize(9)
          .fontColor(TEXT_SECONDARY)
          .maxLines(1)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
          .layoutWeight(1)
      }
      .width('100%')

      // 关键信息小字 —— 高德卡片的重点就是这一行
      // 【为什么要 maxLines(2) + 省略号】卡片只有 33% 宽，
      // 「需绕行掉头，但落客通道无排队」这类长文案会撑出卡片（实跑验证 P-3 的小字
      // 越过了屏幕右边界）。限两行 + 省略号，完整原因在下方白卡里仍有。
      Text(this.hint)
        .fontSize(10)
        .fontColor(TEXT_TERTIARY)
        .maxLines(2)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
        .width('100%')

      /**
       * 【余位为什么不用 if 条件渲染】
       * 初版写 `if (this.remaining >= 0)` —— P-3 在契约quota 里没有条目，
       * 于是这张卡少一行、高度比另外两张矮，三张卡参差不齐（用户反馈「方框大小不一」）。
       * 现在无条件渲染，没有数据时显示「余位 —」，**三卡保证等高**。
       */
      Text(this.remaining >= 0 ? `余位 ${this.remaining}` : '余位 —')
        .fontSize(9)
        .fontColor(TEXT_TERTIARY)
        .width('100%')
    }
    .alignItems(HorizontalAlign.Start)
    .padding(10)
    // 【为什么用 width('33%') 而不是 layoutWeight(1)】
    // 实跑验证 layoutWeight 放在 ForEach 生成的自定义组件上不生效：卡片会被内容撑到整行宽，
    // 后面的路线二/三被挤出屏幕外（截图里只看到路线一横跨一整行）。
    // 固定 33% 宽度才能保证三张卡并排，交互上点哪张都一样，不会误触。
    .width('33%')
    // 三张卡 + 两个间距 = 100%，留2% 余量给小字，绝不越出屏幕
    .constraintSize({ maxWidth: '32%' })
    // 【写死高度 = 三卡严格等高】内容行数已经统一（标题/路径号/时间/路况构成/小字/余位
    // 全部无条件渲染），再写死高度做双保险，任何情况下三张卡都不会参差不齐。
    // 高度 140是实跑验证配比：多了一行路况构成，六行内容仍能完整显示。
    .height(140)
    // 【选中态的第二个视觉通道】背景也随 selected 变，
    // 这样即使司机色觉差异（去色校验），仍能靠「底色深浅 + 边框粗细 + ✓」三条通道分辨
    // —— 手册 §11.3 三重编码的落地。
    .backgroundColor(this.pickBgNow())
    .borderRadius(10)
    .border({
      width: this.isPickedNow() ? 2 : 1,
      color: this.pickBorderNow()
    })
    /**
     * 【数据不可用 / 应急态：卡片变灰且不可点 —— 用户明确要求】
     * 「要变成灰色，而且不可以点，无法跳转」
     *
     * 【为什么是灰而不是别的色】手册 TC-11：不可用一律灰，绝不显示成蓝色。
     * 蓝色（ACCENT_COLOR_BLIND）在本 App 里的含义是「这是当前选中的路线」，
     * 数据都拿不到还显示蓝色选中态 = 骗司机，必须一起去掉。
     *应急态同理：已停止引导，还让卡片亮着选中态会误导。
     */
    .opacity(this.locked ? 0.45 : 1)
    .enabled(!this.locked)
  }
}

/** 从 quota 数组里取某路径的剩余量，取不到返回 -1 */
function remainingOf(pathId: string): number {
  for (let i = 0; i < ROUTES_FIXTURE.quota.length; i++) {
    if (ROUTES_FIXTURE.quota[i].path_id === pathId) {
      return ROUTES_FIXTURE.quota[i].remaining;
    }
  }
  return -1;
}

/** 「路线一/二/三」标题 */
function titleOf(index: number): string {
  if (index === 0) {
    return '路线一';
  }
  if (index === 1) {
    return '路线二';
  }
  return '路线三';
}

/** 某方案的路况构成：等级数组 + 「畅通 · 拥堵 · 畅通」这样的文字 */
function levelsOf(plan: PlanMeta): number[] {
  const out: number[] = [];
  for (let i = 0; i < plan.segments.length; i++) {
    out.push(segmentLevelOf(plan.segments[i]));
  }
  return out;
}

function levelsTextOf(plan: PlanMeta): string {
  if (plan.segments.length === 0) {
    return '等级待接入';
  }
  let s: string = '';
  for (let i = 0; i < plan.segments.length; i++) {
    const lv: number = segmentLevelOf(plan.segments[i]);
    const nm: string = lv < 1 ? '不可用' : levelMetaOf(lv, false).name;
    if (i > 0) {
      s += ' · ';
    }
    s += nm;
  }
  return s;
}

/**
 * 路线方案横排卡片组：路线一（推荐）+ 路线二 + 路线三。
 * 横向一屏展示全部候选，点击切换选中方案（只改演示态，不做任何真实控制）。
 *
 * 【这一版的数据源换成了 arrivalPlans() —— 用户投诉「不要乱标」「按拥堵排序」的修法】
 * 初版直接读 ROUTES_FIXTURE.alternatives，问题是：
 *   ① 卡片顺序 = 契约数组顺序，与路况无关（用户要「按拥堵情况做推荐优先级」）
 *   ② 卡片上没有任何路况信息，地图上着色是「无中生有」，用户无从核对
 * 现在统一走 arrivalPlans()：排序依据、路况构成、地图几何三处共用同一份派生结果，
 * 卡片与地图不可能再对不上。
 */
@Component
export struct RouteOptionRow {
  /** 当前选中的路径号（到站 = store.pickedPathId，离站 = store.departurePathId） */
  @Prop picked: string = '';
  /**
   * 方案数据源：'arrival' = 到站方案（arrivalPlans），'departure' = 离站方案（departurePlans）。
   * 导航页按 store.navMode 切换：到站导航显示到站方案、离站导航显示离站方案
   * （用户要求「导航下方路线选择要展示的是落客或离站的」）。落客页恒为 'arrival'。
   */
  @Prop mode: string = 'arrival';
  /**
   * 再次点击「已选中的」路线框时触发（落客/离站页用它回跳导航页并导航该路线）。
   * 导航页不传（默认空操作）：导航页点已选路线框只是保持选中，不回跳。
   * 【注意】ArkTS V1 不允许 @Prop 装饰函数类型，故用普通成员（回调不需要响应式）。
   */
  onActivate: () => void = () => {};
  @Prop colorBlind: boolean = false;
  @Prop unavailable: boolean = false;

  /**
   * 【为什么用 @ObjectLink 而不是 @Prop】
   * 卡片点击要把选中项写回 store.pickedPathId，
   * 而选中态又由 store 决定高亮哪个卡片 —— 必须双向同步。
   * 用 @Prop 时点卡片只有高亮变化，其他按 store.pickedPathId 渲染的地方不跟着变。
   */
  @ObjectLink store: DemoStore;

  build() {
    Column({ space: 6 }) {
      Row({ space: 8 }) {
        // 数据源随 mode 切换：到站用 arrivalPlans()，离站用 departurePlans()
        ForEach(this.mode === 'departure' ? departurePlans() : arrivalPlans(), (plan: PlanMeta) => {
          RouteOptionCard({
            title: titleOf(plan.index),
            pathId: plan.pathId,
            etaMin: plan.etaMin,
            hint: plan.hint,
            remaining: remainingOf(plan.pathId),
            recommended: plan.recommended,
            selected: this.picked === plan.pathId,
            levelsText: levelsTextOf(plan),
            levelDots: levelsOf(plan),
            colorBlind: this.colorBlind,
            unavailable: this.unavailable,
            // 禁止态统一由 store.routeLocked()（应急 / 数据不可用）判定，三页一致
            locked: this.store.routeLocked()
          })
          .onClick(() => {
            /**
             * 【再次点击已选路线框 → 跳回导航页并导航该路线（用户本次新增需求）】
             * 落客/离站页：点「已高亮的」那张卡 = 已经选好路线、现在要去导航 → onActivate()。
             *   导航页在 onActivate 里 setNavMode(对应上下文) + switchTab(0)，
             *   回来就是「原生空地图 → 选定路线 → 按该路线导航」的闭环。
             * 点「未选中的」卡 = 切换方案（到站走 pickPath，离站走 pickDeparturePath）。
             *
             * 【数据不可用 / 应急态：整段直接不响应 —— 用户明确要求】
             * 「数据不可用的时候，导航这里是不可以选择路线的吗，要变成灰色，
             *   而且不可以点，无法跳转」「应急态落客和离站页面要无法跳转导航」
             * → 这里 return 掉；卡片视觉置灰见下面 `.enabled(...)` 与不透明度。
             * store.pickPath / setNavMode 里也各挡了一道，两层都不许通过。
             */
            if (this.store.routeLocked()) {
              return;
            }
            if (this.picked === plan.pathId) {
              this.onActivate();
            } else if (this.mode === 'departure') {
              this.store.pickDeparturePath(plan.pathId);
            } else {
              this.store.pickPath(plan.pathId);
            }
          })
        }, (plan: PlanMeta) =>
        /**
         * 【ForEach 缓存键必须带全部影响渲染的状态 —— ArkTS 硬约定】
         * 键只写 path_id 时，点选后 picked 变了但键没变，
         * ArkUI 会复用上一次的节点 → 卡片底色/对勾不更新（实跑验证「点了没反应」）。
         * 键里必须把 picked 与两个抽色开关都带上（mode 固定，不必进键）。
         */
          // locked 也要进键：禁止态下卡片要变灰禁用，键不变会复用旧节点导致「点了没反应」
          `${plan.pathId}_${this.picked}_${this.colorBlind}_${this.unavailable}_${this.store.routeLocked()}`)
      }
      .width('100%')
    }
    .width('100%')
  }
}
