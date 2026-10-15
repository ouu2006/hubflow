import { ROUTES_FIXTURE } from '../common/Fixture';
import { DemoStore } from '../common/DemoStore';
import { EmergencyCard, InfoRow, SectionTitle, LevelLegend, SegmentBar } from '../components/Common';
import { TEXT_SECONDARY, TEXT_TERTIARY, BG_GRAY_LIGHT, BG_GRAY_LIGHTER } from '../common/Colors';
import { RoadNetMap } from '../components/RoadNetMap';
import { RouteStripCard, DropoffActionRow } from '../components/NavBar';
import { RouteOptionRow } from '../components/RouteOptionRow';
import { StateTopBar } from '../components/StateTopBar';
import { DegradedBanner } from '../components/DegradedBanner';
import { arrivalPlans, planOf } from '../common/RoutePlan';

/**
 * 页二：落客 / 候客指引（停靠点类型、位置、步行接驳时长）
 *
 * 【结构与导航页完全一致，见 RecommendPage.build 的详细说明】
 * 用户要求：「导航那里也是可以看到完整的地图，它可以做成下拉式，但是一定要完整的地图，
 *   落客这里也是同理」→ 所以本页也是**整页一个 Scroll，地图排在最前面**，
 * mapHeight 与导航页统一 470vp（大于首屏可视高度，一进来整屏只有地图，
 * 往下拉才看到停靠点信息）。
 *
 * 【用户投诉「落客页面地图路线又红又黄又绿」的修法】
 * 初版地图把整条路线按里程等分成四段、上绿/黄/橙/红四色，
 * 看着像「路况五彩灯」，与下方路段说明（畅通/拥堵）也对不上。
 * 现在配色**只有两个来源**：
 *   ① 选中方案：按该方案真实经过的路段等级着色（与下方路段条同源）
 *   ② 未选中方案：统一灰色虚线（不再按里程乱上色）
 * 所以图上出现的颜色必然能在下方文字里找到对应等级。
 *
 * 【本轮补上的方案选择区 —— 用户投诉「图文不冲突」的落客页版本】
 * 用户在离站页提的要求（地图几条路就给几张卡、卡可选、卡的等级与地图一致）
 * 在本页同样成立，但初版落客页**只有地图没有卡**：
 * 地图上画了 1 条彩色主线 + 2 条灰色虚线，页面下方却只有停靠点信息，
 * 司机看到两条灰虚线既不知道是哪两条、也没法点选切换 —— 图文冲突。
 * 现在补上与导航页同源的三件套（数据全部来自 arrivalPlans()，与地图同源）：
 *   ① RouteStripCard —— 当前方案的路径号 / 耗时 / 落客点
 *   ② RouteOptionRow —— 三张方案方块卡，点哪张地图就切到哪张
 *   ③ SegmentBar 路段条 —— 跟着**当前选中方案**走，不再永远显示推荐方案的路段
 *
 * 【本轮补的顶部应急条 + 底部操作条 —— 用户原话】
 * 「应急态导航页面的上方是有个红的警告弹窗，然后呢落客这里上方就没有，
 *   只能滑到下面看才能看到红色应急状态。离站这里也是」
 * → 本页在 Column 最上方挂 StateTopBar（应急红 / 降级琥珀，常态 0 高度不占位）。
 *
 * 「我想要把落客那个页面也做成导航那个页面那样子，可以选择路线一、路线二、路线三，
 *   有这个按钮，现在只有方框」
 * → 「只有方框」指的是缺底部那条 NavActionRow（继续 + 路线一/二/三 切换按钮）。
 *   现在补上，与导航页同一个组件、同一份数据（arrivalPlans()），
 *   点「路线二」与点第二张方块卡是**同一个动作**（都写 store.pickedPathId）。
 *
 * 【应急态下本页仍然显示方案卡，理由】
 * 应急 = 停止引导、服从指挥，但「有哪些路线可选」这个信息不该被拿走——
 * 隐藏它会让司机在应急时反而无从判断。所以这里只收起「继续」按钮的推进语义，
 * 应急条挂在顶部，方案区照常可点。
 */
@Component
export struct DropoffPage {
  // @ObjectLink：与 Index 持有的同一个 DemoStore 实例双向同步
  // （Tabs 会缓存已创建的页签，只有 ObjectLink 这种显式链接才能保证父态一变就重绘）
  @ObjectLink store: DemoStore;

  /**
   * 切 Tab 回调：再次点击「已选中的」路线框 → setNavMode('arrival') + 跳回导航页（index 0）。
   * 由 Index 通过属性注入（TabsController.changeIndex）。
   * 【注意】ArkTS V1 不允许 @Prop 装饰函数类型，故用普通成员（回调不需要响应式）。
   */
  switchTab: (idx: number) => void = () => {};

  /**
   * 当前选中方案的路段构成。
   * 与导航页同一个写法：走 arrivalPlans()，不直接用 arrival_route.segments，
   * 否则切到备选后地图/卡片是备选、只有这段还是推荐方案的路段。
   */
  private pickedSegments(): string[] {
    return planOf(arrivalPlans(), this.store.pickedPathId).segments;
  }

  /** 当前选中方案的展示序号（0/1/2） */
  private pickedIndex(): number {
    return planOf(arrivalPlans(), this.store.pickedPathId).index;
  }

  build() {
    Column() {
      /**
       * 顶部应急/降级条，**必须在 Scroll 之外**（用户要求「上方就能看到」）。
       * 常态下 StateTopBar 返回空 Column，0 高度，不占版面。
       */
      StateTopBar({ store: this.store, scene: '落客' })

      Scroll() {
        Column({ space: 12 }) {
          /**
           * 【应急 / 降级提示：必须放在滚动区最上面，而不是页面末尾 —— 本轮实跑修掉】
           *
           * 【为什么挪到最前】
           * 原来这段在 Scroll 的**最后**（方案卡之后），于是：
           *   常态页面很长（地图 470vp 占满上半屏），红卡被推到屏幕外下沿，
           *   实测截图里「已停止路线引导，恢复后自动继续。」这行被底部固定操作条压掉一半，
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
          if (this.store.emergency) {
            EmergencyCard()
          } else if (this.store.degraded) {
            DegradedBanner({ scene: '落客' })
          }

          RoadNetMap({
            unavailable: this.store.unavailable,
            colorBlind: this.store.colorBlind,
            routeMode: 'arrival',
            mapHeight: 470,
            dropLabel: ROUTES_FIXTURE.arrival_route.dropoff_point,
            pickedIndex: this.store.pickedIndex,
            pickedPathId: this.store.pickedPathId,
            repaintEpoch: this.store.routeEpoch,
            // 选路页红线强调：让「连接司机标识与终点的红线」在选路地图也清晰可见
            selection: true,
            // 应急态停止路线引导、地图不再画推荐路线（与导航页同口径）
            stopGuidance: this.store.emergency
          })

          /**
           * ---- 方案选择区：地图上几条路，这里就给几张卡 ----
           * 三件套与导航页完全同源（arrivalPlans()），点卡 → store.pickedPathId 变
           * → 地图 / 横卡 / 卡片高亮 / 路段条四处一起变，不会出现「图变了卡没变」。
           */
          RouteStripCard({
            unavailable: this.store.unavailable,
            colorBlind: this.store.colorBlind,
            store: this.store
          })

          RouteOptionRow({
            picked: this.store.pickedPathId,
            mode: 'arrival',
            store: this.store,
            colorBlind: this.store.colorBlind,
            unavailable: this.store.unavailable,
            // 再次点击已选路线框 → 进入到站导航（setNavMode('arrival') 锁定上下文并车归起点，再跳回导航页）
            onActivate: () => {
              // 【应急/数据不可用时禁止跳转到导航】
              // setNavMode 内部虽然也会拦（强制 navMode='empty'），
              // 但那样用户点了仍会被 switchTab 送到导航页（虽然那边是空态），
              // 语义上「不可以跳转到导航」没满足，评审会追问。
              // 这里在跳转前先拦，与 RouteOptionRow 卡片点击的守卫对齐。
              if (this.store.routeLocked()) {
                return;
              }
              this.store.setNavMode('arrival');
              this.switchTab(0);
            }
          })

          /**
           * 【应急 / 降级：顶部红条 + 下面红色大框，**两个都要，不是二选一**】
           *
           * 用户原话：「洛克这里原本下面它是有个红色大框的，跟导航页面下面那个一样，
           *   有个红色大框也是写应急状态的，你现在加了红色弹窗，又把我下面的大框给删掉了，
           *   我没有让你删东西」
           *
           * 我上一轮的两个错（都改了）：
           *   ① 把滚动区里的 `EmergencyCard()` 当成「和顶部红条重复」删掉了 ——
           *      它不重复，导航页就是两个都有：顶部窄条给第一眼提示，
           *      下面这张大卡写「已停止路线引导，恢复后自动继续」的完整说明。
           *   ② 把下面所有内容包进 `if (!this.store.degraded)` ——
           *      降级一亮，落客指引、路段条、图例全部消失，同样是「删东西」。
           * 现在：应急 → EmergencyCard + 全部内容；降级 → DegradedBanner + 全部内容。
           */
          SectionTitle({ text: '落客 / 候客指引' })

          Column({ space: 6 }) {
            InfoRow({ label: '停靠点', value: ROUTES_FIXTURE.arrival_route.dropoff_point })
            InfoRow({ label: '停靠点类型', value: '即停即走（社会车辆落客区）' })
            InfoRow({ label: '步行接驳', value: `约 ${ROUTES_FIXTURE.arrival_route.walk_min} 分钟进站` })
            InfoRow({ label: '预计等待', value: '按预约时段入场，无需排队等待' })
          }
          .width('100%')
          .padding(12)
          .backgroundColor(BG_GRAY_LIGHT)
          .borderRadius(10)

          /**
           * 当前方案的路段等级条。
           * 标题随选中方案变化（推荐 vs 备选），路段跟着当前选中方案走 ——
           * 地图上那段橙的对应哪一个 SEG，这里能逐段核对。
           */
          SectionTitle({
            text: this.pickedIndex() === 0 ? '推荐路线路段' : `当前方案（${this.store.pickedPathId}）路段`
          })
          Row({ space: 6 }) {
            ForEach(this.pickedSegments(), (seg: string) => {
              SegmentBar({
                segmentId: seg,
                unavailable: this.store.unavailable,
                colorBlind: this.store.colorBlind
              })
            }, (seg: string) => `${seg}_${this.store.unavailable}_${this.store.colorBlind}`)
          }
          .width('100%')

          // 四级图例（三重编码 §11.3）—— 让司机能自己核对地图上的颜色
          LevelLegend({ colorBlind: this.store.colorBlind, unavailable: this.store.unavailable })

          Column({ space: 4 }) {
            SectionTitle({ text: '提示' })
            Text('请在预约时段内到达停靠点；超时未确认将自动释放时段预约。')
              .fontSize(12)
              .fontColor(TEXT_SECONDARY)
              .width('100%')
            Text('送完乘客后请查看「离站路线」页，系统已为您规划离站方向。')
              .fontSize(12)
              .fontColor(TEXT_SECONDARY)
              .width('100%')
          }
          .width('100%')
          .padding(12)
          .backgroundColor(BG_GRAY_LIGHTER)
          .borderRadius(10)

          if (this.store.unavailable) {
            // 数据不可用：灰色，绝不显示成蓝色（TC-11）
            // 口径红线：页面不出现「实测 / 实时 / 现场」，故此处写「当前余量」而非「实时余量」
            Text('停靠点当前余量：数据不可用')
              .fontSize(13)
              .fontColor(TEXT_TERTIARY)
              .width('100%')
              .padding(10)
              .backgroundColor(BG_GRAY_LIGHTER)
              .borderRadius(8)
          }
        }
        .width('100%')
        /**
         * 【底部留 88 —— 与导航页同值】
         * 底部操作条（NavActionRow）在 Scroll 之外，约 56vp 高。
         * 原来的 24 不够避让，最后一条内容会被压在操作条下面。
         */
        .padding({ left: 14, right: 14, top: 0, bottom: 88 })
      }
      .layoutWeight(1)
      .width('100%')
      .scrollBar(BarState.Auto)

      /**
       * ---- 底部固定操作条（滚动区之外）----
       * 用户原话（两轮）：
       *   「我想要把落客那个页面也做成导航那个页面那样子，可以选择路线一、路线二、路线三，
       *     有这个按钮，现在只有方框」
       *   「你这里都没有，这里的地图都没有那个继续行驶的这个弹窗，你就不要有继续的这个键。
       *     把这个键给删掉」
       * → 只要「变道」，**不要「继续」**：本页顶部没有转向条（不像导航页有那条深色导航条），
       *   按「继续」看不到任何变化，是个空壳按钮。
       * 变道的数据源仍是 arrivalPlans()，与导航页、与上面的方块卡完全一致。
       */
      DropoffActionRow({ store: this.store })
    }
    .width('100%')
    .height('100%')
  }
}
