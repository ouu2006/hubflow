import { ROUTES_FIXTURE, DISCLAIMER_TEXT, segmentLevelOf } from '../common/Fixture';
import { DemoStore } from '../common/DemoStore';
import { EmergencyCard, SectionTitle, SegmentBar, LevelLegend } from '../components/Common';
import { StateTopBar } from '../components/StateTopBar';
import { DepartureActionRow } from '../components/NavBar';
import { DegradedBanner } from '../components/DegradedBanner';
import {
  TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, TEXT_WHITE, BG_GRAY_LIGHT, BG_GRAY_LIGHTER,
  BORDER_ACCENT, ACCENT_COLOR_BLIND, BG_SELECTED } from '../common/Colors';
import { RoadNetMap } from '../components/RoadNetMap';
import { PlanMeta, departurePlans, planOf } from '../common/RoutePlan';
import { levelMetaOf } from '../common/LevelMeta';

/**
 * 页三：离站路线（送完人之后怎么走，本项目独有；departure_route 必现 = TC-12）
 *
 * 【结构与导航页/落客页完全一致，见 RecommendPage.build 的详细说明】
 * 地图排在 Scroll 最前面、mapHeight 统一 470vp，
 * 一进来整屏是地图，往下拉才看到离站路线信息。
 */
@Component
export struct DeparturePage {
  // @ObjectLink：与 Index 持有的同一个 DemoStore 实例双向同步
  // （Tabs 会缓存已创建的页签，只有 ObjectLink 这种显式链接才能保证父态一变就重绘）
  @ObjectLink store: DemoStore;

  /**
   * 切 Tab 回调：再次点击「已选中的」离站路线框 → setNavMode('departure') + 跳回导航页（index 0）。
   * 由 Index 通过属性注入（TabsController.changeIndex）。
   * 【注意】ArkTS V1 不允许 @Prop 装饰函数类型，故用普通成员（回调不需要响应式）。
   */
  switchTab: (idx: number) => void = () => {};

  /**
   * 本页当前是否可见（由 Index 的 Tabs.onChange 注入）。
   * 切到本页时由 true 触发 RoadNetMap 立即重画当前演示态，修「慢一拍」。
   * 仅作重画触发信号，不改变任何业务内容。
   */
  @Prop active: boolean = true;

  /**
   * 当前选中的离站方案。
   *
   * 【为什么离站页也要能选方案 —— 用户原话】
   * 「离站页面：给了两个线路选择就不要地图上有三条路，要图文不冲突，
   *   且也要能选择，要与下方框里标的流畅、缓行等不冲突」
   *
   * 拆成三件事，这一版逐条对上：
   *   ① 「给了两个线路选择」→ 本页给两张方案卡（主选 P-5 + 备选 P-1）
   *   ② 「不要地图上有三条路」→ RoadNetMap 只画departurePlans() 的方案数（本页 2 条），
   *      卡片几个路线就几条，绝不多画
   *   ③ 「要与下方框里标的流畅、缓行等不冲突」→ 下方路段条读的是**当前方案**的路段，
   *      与地图着色、卡片色点同一个来源
   *
   * 【本轮补的两处 —— 用户原话】
   * 「应急态导航页面的上方是有个红的警告弹窗，然后呢落客这里上方就没有，
   *   只能滑到下面看才能看到红色应急状态。离站这里也是」
   *   → 页顶挂 StateTopBar（与导航页同组件），应急红条 / 降级琥珀条第一眼可见。
   * 「就跟前面的都不一样，前面导航和落客都有三条，只有两条」
   *   → 用户在问「为什么离站只有两条」。理由见 departurePlans() 的注释：
   *     契约的 departure_route 没有 alternatives 字段，只有一条离站主选；
   *     备选只能从系统 alternatives 里取一条合法路径（P-1，quota 里有余量）。
   *     **宁少不多**：多画一条就是编造契约里不存在的路线。
   *   → 底部操作条相应地只显示两个方案位，用 DepartureActionRow（不是到站那套）。
   */
  private plan(): PlanMeta {
    return planOf(departurePlans(), this.store.departurePathId);
  }

  private pickPlan(pathId: string): void {
    this.store.pickDeparturePath(pathId);
  }

  /** 某离站方案的路段等级数组（卡片色点用，与地图着色同一个来源） */
  private planLevels(p: PlanMeta): number[] {
    const out: number[] = [];
    for (let i = 0; i < p.segments.length; i++) {
      out.push(segmentLevelOf(p.segments[i]));
    }
    return out;
  }

  /** 某离站方案的路况构成文字（如「畅通 · 缓行」） */
  private planLevelsText(p: PlanMeta): string {
    if (p.segments.length === 0) {
      return '等级待接入';
    }
    let s: string = '';
    for (let i = 0; i < p.segments.length; i++) {
      const lv: number = segmentLevelOf(p.segments[i]);
      if (i > 0) {
        s += ' · ';
      }
      s += lv < 1 ? '不可用' : levelMetaOf(lv, false).name;
    }
    return s;
  }

  /**
   * 【禁止态下的「有效选中态」= 永远 false —— 与到站页 RouteOptionCard 同一口径】
   *
   * 【为什么离站卡也要单独做一遍，而不是抽公共组件】
   * 离站方案是另一套（主选 P-5 + 备选 P-1，见下方注释），数据源不同没法直接复用
   * RouteOptionRow；但「禁止态不许亮蓝」是同一条铁律（手册 TC-11），
   * 两处必须同时改，只改一处就会出现「落客页变灰了、离站页还是蓝的」。
   *
   * 录屏实跑验证：应急态下离站页同样是「离站一」蓝底 + P-5 蓝字 + 蓝对勾 + 蓝框，
   * 而此时已停止引导，不该再告诉司机「你选的是这条」。.opacity(0.45) 只是淡化，蓝色还在。
   */
  /**
   * 【为什么是普通方法而不是 get 访问器 —— 本轮编译踩过】
   * ArkTS 不允许 get 访问器带参数，编译报「A 'get' accessor cannot have parameters」；
   * 而这里必须按 pathId 逐卡判断（离站两张卡各算各的），所以只能写成方法。
   */
  private isPickedOf(pathId: string): boolean {
    return this.store.departurePathId === pathId && !this.store.routeLocked();
  }

  /** 选中态底色：禁止态一律灰 */
  private pickBgOf(pathId: string): string {
    return this.isPickedOf(pathId) ? BG_SELECTED : BG_GRAY_LIGHTER;
  }

  /** 选中态边框色：禁止态一律灰 */
  private pickBorderOf(pathId: string): string {
    return this.isPickedOf(pathId) ? ACCENT_COLOR_BLIND : BORDER_ACCENT;
  }

  build() {
    Column() {
      /** 页顶应急/降级条（与导航页、落客页同一个组件，常态 0 高度不占位） */
      StateTopBar({ store: this.store, scene: '离站' })

      Scroll() {
        Column({ space: 12 }) {
          /**
           * 【应急 / 降级提示：必须放在滚动区最上面，而不是页面末尾 —— 本轮实跑修掉】
           *
           * 【为什么挪到最前】
           * 原来这段在 Scroll 的**最后**（方案卡之后），于是：
           *   常态页面很长（地图 470vp 占满上半屏），红卡被推到屏幕外下沿，
           *   实跑验证截图里「已停止路线引导，恢复后自动继续。」这行被底部固定操作条压掉一半，
           *   而这行正是完成判定里「告知文案必现」要的那句 —— 等于判定被打折。
           * Scroll 的 padding.bottom 只在**滚到底**时才起避让作用，
           * 而应急态是「刚点亮、用户还在页面顶部」的时刻，此时根本看不到末尾。
           *
           * 【挪前后的双重效果】
           *   ① 红卡在第一屏顶部，不必滚动即可看到完整告知；
           *   ② 即使底部被压，也只会压到最后的辅助信息，不会压掉安全告知。
           * 注意这与 StateTopBar（页顶窄条）是**叠加**关系，两个都保留：
           * 顶部窄条给第一眼信号、下面大卡给完整说明，与导航页同构。
           */
          /**
           * 【2026-10-16 用户指令：应急红大卡挪到地图下方、路线选择框上方】
           * 顶部窄条（StateTopBar）仍在页顶负责第一眼安全信号，不在此列。
           * 降级琥珀条位置不变（用户只提了红卡）。
           */
          if (this.store.degraded) {
            DegradedBanner({ scene: '离站' })
          }

          RoadNetMap({
            unavailable: this.store.unavailable,
            colorBlind: this.store.colorBlind,
            routeMode: 'departure',
            mapHeight: 470,
            dropLabel: `${this.plan().pathId} 离站`,
            pickedIndex: 0,
            pickedPathId: this.store.departurePathId,
            repaintEpoch: this.store.routeEpoch,
            // 选路页红线强调：让「连接司机标识与终点的红线」在选路地图也清晰可见
            selection: true,
            // 应急态停止路线引导、地图不再画推荐路线（与导航页同口径）
            stopGuidance: this.store.emergency,
            // 切到本页（Tabs.onChange）时 active 由 false→true，触发 repaintNow() 就地重画最新演示态，
            // 解决「演示态切换慢一拍」：单 Canvas 不重建、不 bumpEpoch、杜绝多地图叠加
            active: this.active
          })

          // 应急红大卡：地图正下方、路线选择框正上方（用户指定位置）
          if (this.store.emergency) {
            EmergencyCard()
          }

          /**
           * 【应急 = 顶部加一条红条，**下面一个字都不能少** —— 用户明确纠正过】
           * 用户原话：「应急态的时候离站这个页面下面的字怎么全没了？给我恢复啊，
           *   下面依旧有字啊，我只是让你应急态的时候上面多一个弹框，并没有让你删任何的东西」
           *
           * 我上一轮的错：把下面的内容整块包进 `if (!this.store.emergency)`，
           * 本意是「应急时别显示路线选择」，实际效果是**应急一亮整页只剩一条红条**，
           * 卡片、路段、图例全没了 —— 与导航页的行为完全不一致。
           * 现在改成恒成立（`if (true)`），只保留块内结构与缩进不变，
           * 免得大段重排引入新错误。
           *
           * 【红色大框 EmergencyCard 是「保留」而不是「替换」】
           * 用户原话：「洛克这里原本下面它是有个红色大框的，跟导航页面下面那个一样，
           *   有个红色大框也是写应急状态的，你现在加了红色弹窗，又把我下面的大框给删掉了，
           *   我没有让你删东西」
           * → 所以应急态下：顶部红条（StateTopBar）+ 下面红色大框（EmergencyCard）**两个都要**。
           *   顶部那个负责「第一眼可见」，下面那个是导航页同款的内容卡。
           */
          SectionTitle({ text: '送完人之后怎么走（离站路线）' })

          /**
           * 【离站方案卡：两个，可点选 —— 用户要求「给了两个线路选择」「也要能选择」】
           *
           * 这一段是本轮新加的。初版本页只有一条离站路线、一个只读卡片，
           * 于是：① 地图上却按到站的三条方案画线（图文冲突）
           * ② 用户想换一条离站走法也没处换。
           * 现在：departurePlans() 给两条，卡片两条、地图两条，一一对应。
           *
           * 【为什么用两个横排小块而不是复用 RouteOptionRow】
           * RouteOptionRow 的入参写死了 arrivalPlans()（到站方案）。
           * 离站方案是另一套（主选 P-5 + 备选 P-1），强行复用会显示成到站的路段，
           * 反而更乱。这里独立写两个小块，结构对齐、数据源不同，注释写清即可。
           */
          Row({ space: 8 }) {
            ForEach(departurePlans(), (p: PlanMeta) => {
              Column({ space: 4 }) {
                Row({ space: 4 }) {
                  Text(p.index === 0 ? '离站一' : '离站二')
                    .fontSize(12)
                    .fontWeight(FontWeight.Bold)
                    .fontColor(this.isPickedOf(p.pathId) ? TEXT_WHITE : '#33404A')
                    .padding({ top: 2, bottom: 2, left: 6, right: 6 })
                    .backgroundColor(this.isPickedOf(p.pathId) ? ACCENT_COLOR_BLIND : '#D5DEE4')
                    .borderRadius(4)
                  Text(p.recommended ? '推荐' : '')
                    .fontSize(9)
                    .fontColor(TEXT_TERTIARY)
                  Blank()
                  Text('✓')
                    .fontSize(12)
                    .fontWeight(FontWeight.Bold)
                    .fontColor(this.isPickedOf(p.pathId) ? ACCENT_COLOR_BLIND : '#C3CDD4')
                }
                .width('100%')

                Text(p.pathId)
                  .fontSize(20)
                  .fontWeight(FontWeight.Bold)
                  .fontColor(this.isPickedOf(p.pathId) ? ACCENT_COLOR_BLIND : TEXT_PRIMARY)
                  .maxLines(1)

                Text(`约 ${p.etaMin} 分钟`)
                  .fontSize(11)
                  .fontColor(TEXT_PRIMARY)
                  .maxLines(1)

                /**
                 * 路况构成小字 —— 与地图着色同源（segmentLevelOf），
                 * 用户可以逐段核对地图上那段颜色对应的是哪个等级。
                 */
                Row({ space: 3 }) {
                  ForEach(this.planLevels(p), (lv: number) => {
                    Text('●')
                      .fontSize(8)
                      .fontColor(this.store.colorBlind || this.store.unavailable || lv < 1
                        ? '#8B8B8B' : levelMetaOf(lv, false).color)
                  }, (lv: number, idx: number) => `dlv_${idx}_${lv}`)
                  Text(this.planLevelsText(p))
                    .fontSize(9)
                    .fontColor(TEXT_SECONDARY)
                    .maxLines(1)
                    .textOverflow({ overflow: TextOverflow.Ellipsis })
                    .layoutWeight(1)
                }
                .width('100%')

                Text(p.hint)
                  .fontSize(10)
                  .fontColor(TEXT_TERTIARY)
                  .maxLines(2)
                  .textOverflow({ overflow: TextOverflow.Ellipsis })
                  .width('100%')
              }
              .alignItems(HorizontalAlign.Start)
              .padding(10)
              .width('48%')
              .constraintSize({ maxWidth: '47%' })
              // 与到站页的方案卡同高（140），两页视觉一致
              .height(140)
              .backgroundColor(this.pickBgOf(p.pathId))
              .borderRadius(10)
              .border({
                width: this.isPickedOf(p.pathId) ? 2 : 1,
                color: this.pickBorderOf(p.pathId)
              })
              /**
               * 【禁止态：卡片变灰且不可点 —— 用户明确要求】
               * 「数据不可用的时候，落客页和离站页也不可以跳转到导航」
               * 「应急态落客和离站页面要无法跳转导航，因为他要服从现场指挥，
               *   它要停止路线指引，所以点路线框的时候是无法跳转到导航那里的」
               * → 这里 return；store.pickDeparturePath / setNavMode 里也各挡一道。
               */
              .opacity(this.store.routeLocked() ? 0.45 : 1)
              .enabled(!this.store.routeLocked())
              .onClick(() => {
                /**
                 * 【再次点击已选路线框 → 跳回导航页并导航该离站路线（用户本次新增需求）】
                 * 当前卡片已选中（departurePathId === p.pathId）→ setNavMode('departure')
                 * 锁定离站上下文、车归起点，再 switchTab(0) 回导航页按该路线导航。
                 * 否则只是切换离站方案（写 store.departurePathId）。
                 */
                if (this.store.routeLocked()) {
                  return;
                }
                if (this.store.departurePathId === p.pathId) {
                  this.store.setNavMode('departure');
                  this.switchTab(0);
                } else {
                  this.pickPlan(p.pathId);
                }
              })
            }, (p: PlanMeta) =>
            /**
             * 缓存键必须带全部影响渲染的状态：path_id + 选中态 + 两个抽色开关。
             * 少一个就会出现「点了卡片但高亮不动」/「开了去色校验卡片颜色不变」。
             */
              `${p.pathId}_${this.store.departurePathId}_${this.store.colorBlind}_${this.store.unavailable}_${this.store.routeLocked()}`)
          }
          .width('100%')

          // departure_route 必现（TC-12），且路段随当前选中方案走
          Column({ space: 6 }) {
            Row() {
              Text(`离站路线 ${this.plan().pathId}${this.plan().recommended ? '（推荐）' : ''}`)
                .fontSize(14)
                .fontWeight(FontWeight.Medium)
                .fontColor(TEXT_PRIMARY)
              Blank()
              Text(`约 ${this.plan().etaMin} 分钟`)
                .fontSize(14)
                .fontColor(TEXT_PRIMARY)
            }
            .width('100%')

            /**
             * 【路段条读当前方案，不是写死 departure_route】
             * 初版写死 ROUTES_FIXTURE.departure_route.segments，
             * 切到备选后卡片是备选、这段还是主选的路段 —— 图文不一致。
             */
            Row({ space: 6 }) {
              ForEach(this.plan().segments, (seg: string) => {
                SegmentBar({ segmentId: seg, unavailable: this.store.unavailable, colorBlind: this.store.colorBlind })
              }, (seg: string) => `${seg}_${this.store.unavailable}_${this.store.colorBlind}_${this.store.departurePathId}`)
            }
            .width('100%')

            Text(this.plan().hint)
              .fontSize(11)
              .fontColor(TEXT_SECONDARY)
              .width('100%')
          }
          .width('100%')
          .padding(12)
          .backgroundColor(BG_GRAY_LIGHT)
          .borderRadius(10)
          .border({ width: 1, color: BORDER_ACCENT })

          Text('落客完成后按此路线驶离站前区域，避免与社会车辆候客流线交叉。')
            .fontSize(12)
            .fontColor(TEXT_SECONDARY)
            .width('100%')

          LevelLegend({ colorBlind: this.store.colorBlind, unavailable: this.store.unavailable })

          Text(DISCLAIMER_TEXT)
            .fontSize(12)
            .fontColor(TEXT_TERTIARY)
            .width('100%')
        }
        .width('100%')
        // 底部留 88 避让固定操作条（与导航页/落客页同值）
        .padding({ left: 14, right: 14, top: 0, bottom: 88 })
      }
      .layoutWeight(1)
      .width('100%')
      .scrollBar(BarState.Auto)

      /**
       * 底部固定操作条（滚动区之外）。
       * 用 DepartureActionRow 而不是到站那套 NavActionRow ——
       * 离站只有两条方案、选中态存在 departurePathId 里，
       * 复用会导致「按钮动了、地图没动」。
       */
      DepartureActionRow({ store: this.store })
    }
    .width('100%')
    .height('100%')
  }
}
