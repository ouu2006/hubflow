import { ROUTES_FIXTURE, VEHICLES_FIXTURE, DEMO_VEHICLE_ID, DISCLAIMER_TEXT } from '../common/Fixture';
import { DemoStore } from '../common/DemoStore';
import { EmergencyCard, InfoRow, SectionTitle, LevelLegend, SegmentBar } from '../components/Common';
import { Vehicle } from '../common/Contract';
import { TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, BG_GRAY_LIGHT, BG_GRAY_LIGHTER, BG_HIGHLIGHT, ACCENT_COLOR_BLIND, ACCENT_DEGRADED, BORDER_ACCENT } from '../common/Colors';
import { NavActionBar, RouteStripCard, NavActionRow } from '../components/NavBar';
import { RoadNetMap } from '../components/RoadNetMap';
import { RouteOptionRow } from '../components/RouteOptionRow';
import { DegradedBanner } from '../components/DegradedBanner';
import { StateTopBar } from '../components/StateTopBar';

/**
 * 绑定的演示车（C-3）。
 *
 * 【为什么是模块级常量而不是 @State】
 * fixture 是工程内静态数据，全程不变；@State 只能声明在 struct 内（ArkTS 不允许修饰模块级变量），
 * 且它不是响应式状态，没有重绘需求，所以直接用模块级常量。
 */
const DEMO_VEHICLE_CACHE: Vehicle = (() => {
  for (let i = 0; i < VEHICLES_FIXTURE.vehicles.length; i++) {
    if (VEHICLES_FIXTURE.vehicles[i].vehicle_id === DEMO_VEHICLE_ID) {
      return VEHICLES_FIXTURE.vehicles[i];
    }
  }
  return VEHICLES_FIXTURE.vehicles[0];
})();

/**
 * 页一：导航（高德式排版）
 *
 * 【本页面被返工四轮才对，最终结构见 build 里的注释】
 * 用户要求逐轮收紧：
 *   ① 地图要能过流程（Y 字转向决策点）
 *   ② 路线方案改成横排方块卡（路线一/二/三）
 *   ③ 变道要循环切换，不能是累加计数
 *   ④ 「一进来除了上面和下面的就一整个画面都是地图，往下拉才看到文字」
 *   ⑤ 地图左右要对称
 */
@Component
export struct RecommendPage {
  // @ObjectLink：与 Index 持有的同一个 DemoStore 实例双向同步
  // （Tabs 会缓存已创建的页签，@ObjectLink 才能保证父态一变就重绘）
  @ObjectLink store: DemoStore;

  /**
   * 切 Tab 回调：空态指引按钮用它跳去「落客 / 离站」页选路。
   * 由 Index 通过属性注入（TabsController.changeIndex）。
   * 【注意】ArkTS V1 不允许 @Prop 装饰函数类型，故用普通成员（回调不需要响应式）。
   */
  switchTab: (idx: number) => void = () => {};

  @State pickedRoad: string = 'SEG-002';

  /**
   * 当前选中方案的路段构成（按 navMode 取 arrival / departure 方案，与地图同源）。
   *
   * 【为什么不能直接用 ROUTES_FIXTURE.arrival_route.segments】
   * 那是推荐方案的路段。用户切到备选后，地图画的是备选、卡片显示的是备选，
   * 只有这一段还是推荐方案的，三处对不上。统一走 navPlan() 后，
   * 这一段与地图、卡片读的是同一份结果，且离站导航也走离站方案。
   */
  private pickedSegments(): string[] {
    return this.store.navPlan().segments;
  }

  /** 当前选中方案的展示序号（0/1/2，按 navMode 选到站/离站方案） */
  private pickedIndex(): number {
    return this.store.navPlan().index;
  }

  /** 当前是否离站导航（navMode='departure'）—— build 内不能直接写 const，故抽成方法 */
  private isDepNav(): boolean {
    return this.store.navMode === 'departure';
  }

  /** 当前生效方案的 path_id（按 navMode 选到站/离站，与地图同源） */
  private activePathId(): string {
    return this.store.navPlan().pathId;
  }

  build() {
    Column() {
      if (this.store.navMode === 'empty') {
        /**
         * 空态：原生空地图（不标任何东西）+ 指引按钮，引导去落客/离站选路。
         * 【应急态（用户本轮要求）】空态也要有应急提示：顶部红条（Scroll 之外，第一眼可见）
         * + 滚动区里的红色应急大卡；两个指引按钮**变灰禁用** —— 应急 = 停止路线引导，
         * 此时不能再引导司机去选路。提示只叠加，正文（地图/指引卡）照常保留。
         */
        StateTopBar({ store: this.store, scene: '导航' })

        Scroll() {
          Column({ space: 12 }) {
            RoadNetMap({
              unavailable: this.store.unavailable,
              colorBlind: this.store.colorBlind,
              routeMode: 'arrival',
              /**
               * 【空态地图同样 470 —— 用户要求「地图一打开是占整个页面的，往下滑才能看到文字」】
               * 之前这里为了「指引卡首屏可见」缩到 340，把用户的原始要求改掉了。
               * 现在与导航态、落客页、离站页**三页四态统一 470**：
               * 一进来整屏只有地图，往下拉才逐段露出文字。
               * 指引卡与两个跳转按钮在地图下方，滑动即可看到 —— 用户要的正是这个下拉式布局。
               */
              mapHeight: 470,
              pickedIndex: 0,
              pickedPathId: '',
              repaintEpoch: this.store.routeEpoch,
              blank: true,
              selection: false
            })

            Column({ space: 10 }) {
              SectionTitle({ text: '请选择路线开始导航' })
              Text('当前尚未选定路线，地图为原生空图。请前往「落客」或「离站」页选择一条路线，'
                + '选定后再次点击该路线框即可回到这里、按该路线导航。')
                .fontSize(13)
                .fontColor(TEXT_SECONDARY)
                .width('100%')
              Button('去落客页选路线')
                .width('100%')
                .height(48)
                // 应急态：按钮变灰禁用（应急 = 停止路线引导，不再引导选路）
                /**
                 * 【禁止态：按钮变灰禁用 —— 用户明确要求「不可以点，无法跳转」】
                 * 原来只有 emergency 会禁用，数据不可用时按钮照常可点，
                 * 于是拿不到路况时司机仍能跳去选路 —— 与需求相反。
                 * 现在统一按 store.routeLocked() 判：应急 + 数据不可用都禁用。
                 * 【但按钮不删除】用户明确要求过「只叠加、不删正文」；
                 * 禁用（变灰）而非删掉，数据恢复后自动可用。
                 */
                .backgroundColor(this.store.routeLocked() ? '#C3CDD4' : '#1E88E5')
                .opacity(this.store.routeLocked() ? 0.6 : 1)
                .enabled(!this.store.routeLocked())
                .onClick(() => {
                  this.switchTab(1);
                })
              Button('去离站页选路线')
                .width('100%')
                .height(48)
                .backgroundColor(this.store.routeLocked() ? '#C3CDD4' : '#1E88E5')
                .opacity(this.store.routeLocked() ? 0.6 : 1)
                .enabled(!this.store.routeLocked())
                .onClick(() => {
                  this.switchTab(2);
                })
              // 禁止态补一句原因说明：按钮变灰必须告诉司机为什么，否则像坏了
              if (this.store.routeLocked()) {
                Text(this.store.emergency
                  ? '应急处置中：路线引导已停止，请服从现场指挥，恢复后再选择路线'
                  : '数据不可用：暂不可选择路线，数据恢复后自动继续')
                  .fontSize(11)
                  .fontColor(ACCENT_DEGRADED)
                  .width('100%')
              }
            }
            .width('100%')
            .padding(12)
            .backgroundColor(BG_GRAY_LIGHTER)
            .borderRadius(10)
          }
          .width('100%')
          // 空态没有底部操作条，不需要让出 88；留 16 足够，按钮首屏可见
          .padding({ left: 14, right: 14, top: 0, bottom: 16 })
        }
        .layoutWeight(1)
        .width('100%')
        .scrollBar(BarState.Auto)
      } else {
        // 到站 / 离站导航：内容与改版前一致，仅按 navMode 决定画哪条路线、方案卡用哪套数据
        // 导航条：应急态时自动变成深红「请服从现场指挥」（优先级高于一切推荐）
        NavActionBar({ store: this.store })

      /**
       * 【整页一个 Scroll，地图排在最上面 —— 用户第 4、5 轮明确要求】
       *
       * 用户原话：
       *   「我不要只是下面那一半有字的可以拉……我要的是视频那种
       *     整页可以拉的拉动的后面的也是，不要只是下面那一节能拉」
       *   「我想要的是一进来除了上面和下面的就一整个画面都是地图，
       *     等到我们往下拉的时候才看到文字」
       *
       * 【前几版错在哪，务必不要改回去】
       * v1：地图放进 Scroll → 一滚动地图就滚走，只剩「半截地图」。
       * v2：地图移出 Scroll 固定在顶部 → 地图完整了，但**上半屏被四层占满**
       *     （顶栏 / 导航条 / 地图 / 操作条），留给信息区的可视高度只剩一小条，
       *     白卡最后一行被切掉、方案卡的小字和余位完全露不出来
       *     —— 用户说的「导航那一页下面那个字，根本看不到」。
       *     而且信息区内容远高于那一小条，滚动范围被压得很短，滑动几乎没反应。
       * v3：地图放回 Scroll 但只给 250vp → 首屏露出白卡和方案卡，
       *     但用户要的是「整个画面都是地图」，还是不对。
       * v4（本版）：地图给 **470vp**，**大于首屏可视高度**——
       *     所以一进来整屏只有地图，下方信息一行都不露；
       *     往上滑地图整体上移，白卡 → 方案卡 → 路段 → 协同 → why → 图例 → 演示车
       *     → 告知文案逐段露出，一直能拉到最下面。
       *
       * 【470 是怎么定的】
       * 实测（Pura 90，1320×2856，3.5 px/vp）：
       *   顶栏 250（压扁后）+ tabBar 196 + 角标 137 = 583，
       *   Tabs 内容区 ≈ 2733 - 583 = 2150；
       *   里面 导航条 373 + Scroll + 操作条 197 → Scroll 视口 ≈ 1580px ≈ 451vp。
       * 地图 470vp(1645px) > 视口 451vp → 首屏只能看见地图，符合要求。
       *
       * 【为什么 mapHeight 写死而不用 layoutWeight】
       * 实测给 RoadNetMap 加 layoutWeight 后，它内部 Stack 的高度算不出来，
       * Scroll 会盖到地图上（卡片浮在地图上）。写死高度最稳。
       */
      Scroll() {
        Column({ space: 12 }) {
          /**
           * 【应急提示必须放在滚动区最上面 —— 与落客/离站页同一修法】
           *
           * 【实测到的现象】
           * 原来这张红卡排在方案卡之后（页面下半段），而本页首屏被深色导航条 + 470vp 地图占满，
           * 红卡落在屏幕外；实测截图中「已停止路线引导，恢复后自动继续。」
           * 这行被底部固定操作条压掉一半 —— 而它正是完成判定「告知文案必现」要的那句。
           * Scroll 的 padding.bottom 只在滚到底时生效，刚点亮应急态时用户还在页面顶部，压根看不到。
           *
           * 【与 StateTopBar / NavBar 的关系是叠加，不是替换】
           * 页顶窄条（StateTopBar）给第一眼信号、下面这张大卡给完整说明，导航页原本就是三处都有，
           * 一个都不删。本页顶部另有固定深色导航条（NavBar），它讲的是「下一步怎么走」，与此不冲突。
           */
          if (this.store.emergency) {
            EmergencyCard()
          }

          RoadNetMap({
            unavailable: this.store.unavailable,
            colorBlind: this.store.colorBlind,
            routeMode: this.isDepNav() ? 'departure' : 'arrival',
            mapHeight: 470,
            pickedIndex: this.isDepNav() ? 0 : this.store.pickedIndex,
            pickedPathId: this.activePathId(),
            repaintEpoch: this.store.routeEpoch,
            driveRatio: this.store.driveRatio,
            // 离站导航的终点是离站点，不能沿用落客点标签（否则地图角标显示 DROP-03）
            dropLabel: this.isDepNav() ? '离站出口' : ROUTES_FIXTURE.arrival_route.dropoff_point,
            // 应急态停止路线引导、地图不再画推荐路线（降级态不锁，流程须不中断）
            stopGuidance: this.store.emergency
          })

          // ---- 路线信息横卡（当前方案的路径号 / 耗时 / 落客点） ----
          RouteStripCard({ unavailable: this.store.unavailable, colorBlind: this.store.colorBlind, store: this.store })

          // ---- 路线方案横排方块卡（高德式：路线一/二/三，关键差异标在卡片小字上） ----
          RouteOptionRow({
            picked: this.activePathId(),
            mode: this.isDepNav() ? 'departure' : 'arrival',
            store: this.store,
            colorBlind: this.store.colorBlind,
            unavailable: this.store.unavailable
          })

          if (this.store.degraded) {
            /**
             * 【降级态改成叠加，不吃掉下面所有内容】
             * 初版这里用 else 把推荐卡/协同说明/备选/why/图例全 else 掉了，
             * 点「拒绝授权」后只剩两行字 —— 违背 TC-05「流程不中断」。
             * 现在：上方路线方案卡与地图照常显示，这里只追加一条降级提示
             * 和手动确认所在道路的选择器。
             */
            Column({ space: 8 }) {
              DegradedBanner({ scene: '导航' })

              SectionTitle({ text: '手动确认所在道路' })
              Text('未授权自动定位，请点选你当前所在的路段，后续引导以该段为起点。')
                .fontSize(12)
                .fontColor(TEXT_SECONDARY)
                .width('100%')
/**
               * 【为什么这里也必须读 pickedSegments()而不是 ROUTES_FIXTURE】
               * 初版降级分支直接列arrival_route.segments，于是离站导航时
               * 「手动确认所在道路」列的仍全是到站路段，与本页其余部分矛盾。
               * 同源之后，地图、卡片、图例、手动选路读的都是当前方案。
               */
              ForEach(this.pickedSegments(), (road: string) => {
                Row() {
                  Text(road).fontSize(13).fontColor(TEXT_PRIMARY)
                  Blank()
                  Text(this.pickedRoad === road ? '已选' : '未选')
                    .fontSize(12)
                    .fontColor(this.pickedRoad === road ? ACCENT_COLOR_BLIND : TEXT_TERTIARY)
                }
                .width('100%')
                .padding(10)
                .backgroundColor(this.pickedRoad === road ? BG_HIGHLIGHT : BG_GRAY_LIGHTER)
                .border(this.pickedRoad === road ? { width: 1, color: BORDER_ACCENT } : { width: 0 })
                .borderRadius(8)
                .onClick(() => {
                  this.pickedRoad = road;
                })
              }, (road: string) => `${road}_${this.pickedRoad}`)
            }
            .width('100%')
          } else {
            /**
             * 【路段条跟着「当前选中方案」走，而不是永远显示推荐方案的路段】
             * 初版这里写死 ROUTES_FIXTURE.arrival_route.segments，
             * 于是切到路线二/三后，卡片区显示的是路线二的等级，
             * 下面这段却还是路线一的 SEG-001/004/007 —— 又是「图文不一致」。
             * 现在统一读当前方案的路段构成，与地图着色、卡片色点同源。
             */
            SectionTitle({
              text: this.pickedIndex() === 0 ? '推荐路线路段' : `当前方案（${this.store.navPlan().pathId}）路段`
            })
            Row({ space: 6 }) {
              ForEach(this.pickedSegments(), (seg: string) => {
                SegmentBar({ segmentId: seg, unavailable: this.store.unavailable, colorBlind: this.store.colorBlind })
              }, (seg: string) => `${seg}_${this.store.unavailable}_${this.store.colorBlind}`)
            }
            .width('100%')

            // 前后车协同说明（reservation.harm_check）—— 精简为两行，长句归并
            Column({ space: 4 }) {
              SectionTitle({ text: '前后车协同' })
              Text(`已预约 ${ROUTES_FIXTURE.reservation.slots_reserved} 个路段时段格子，租约 ${ROUTES_FIXTURE.reservation.lease_expire_s} 秒。`)
                .fontSize(12)
                .fontColor(TEXT_SECONDARY)
                .width('100%')
              Text(`前车耗时最多增加 ${ROUTES_FIXTURE.reservation.harm_check.max_eta_increase_s} 秒，路径最大饱和度 ${ROUTES_FIXTURE.reservation.harm_check.max_slot_x}，均在上限内。`)
                .fontSize(12)
                .fontColor(TEXT_SECONDARY)
                .width('100%')
            }
            .width('100%')
            .padding(12)
            .backgroundColor(BG_GRAY_LIGHT)
            .borderRadius(10)

            // why 与因素说明
            Column({ space: 4 }) {
              SectionTitle({ text: '为什么推荐这条' })
              Text(ROUTES_FIXTURE.why)
                .fontSize(12)
                .fontColor(TEXT_SECONDARY)
                .width('100%')
              if (ROUTES_FIXTURE.factors_note !== null) {
                Text(ROUTES_FIXTURE.factors_note)
                  .fontSize(12)
                  .fontColor(ACCENT_DEGRADED)
                  .width('100%')
              }
            }
            .width('100%')
            .padding(12)
            .backgroundColor(BG_GRAY_LIGHT)
            .borderRadius(10)

            // 四级图例（三重编码 §11.3）
            LevelLegend({ colorBlind: this.store.colorBlind, unavailable: this.store.unavailable })
          }

          // 绑定演示车（C-3）
          Column({ space: 4 }) {
            SectionTitle({ text: '绑定的演示车' })
            InfoRow({ label: 'vehicle_id', value: DEMO_VEHICLE_CACHE.vehicle_id })
            InfoRow({ label: '所在路段', value: `${DEMO_VEHICLE_CACHE.segment_id} · ${DEMO_VEHICLE_CACHE.offset_m} m` })
            InfoRow({ label: '状态 / 已引导', value: `${DEMO_VEHICLE_CACHE.state} / ${DEMO_VEHICLE_CACHE.guided ? '是' : '否'}` })
            InfoRow({ label: '位置来源', value: `${ROUTES_FIXTURE.location.source}（一期孪生真值，非真实定位）` })
          }
          .width('100%')
          .padding(12)
          .backgroundColor(BG_GRAY_LIGHTER)
          .borderRadius(10)

          // 告知文案（必现）
          Text(DISCLAIMER_TEXT)
            .fontSize(12)
            .fontColor(TEXT_TERTIARY)
            .width('100%')
            .textAlign(TextAlign.Start)
        }
        .width('100%')
/**
         * 【底部留 88 —— 不是 32】
         * 操作条固定在 Scroll 之外（实测 y≈2229 起、高 197px ≈ 56vp），
         * 原来的 32vp 不够避让：实测方案卡新增「路况构成」那一行正好落在
         * 操作条覆盖区里，被压得只露出上半截（用户能看到卡片但看不到路况）。
         * 留 88vp 能完整露出卡片的最后一行。
         */
        .padding({ left: 14, right: 14, top: 0, bottom: 88 })
      }
      // 整个下半屏就是一个 Scroll —— 地图 + 全部信息一起，可整屏大幅下拉
      .layoutWeight(1)
      .width('100%')
      .scrollBar(BarState.Auto)

      // ---- 导航操作条固定在底部（滚动区之外），这是高德/百度导航的标准位置 ----
      NavActionRow({ store: this.store })
      }
    }
    .width('100%')
    .height('100%')
  }
}
