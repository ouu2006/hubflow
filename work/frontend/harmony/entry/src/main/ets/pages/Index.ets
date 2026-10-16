import { DemoStore } from '../common/DemoStore';
import { ROUTES_FIXTURE } from '../common/Fixture';
import { RecommendPage } from './RecommendPage';
import { DropoffPage } from './DropoffPage';
import { DeparturePage } from './DeparturePage';
import { HistoryPage } from './HistoryPage';
import { SimBadge } from '../components/Common';
import { TEXT_PRIMARY, TEXT_WHITE, ACCENT_EMERGENCY, ACCENT_UNAVAILABLE, ACCENT_DEGRADED, ACCENT_COLOR_BLIND, BG_BASE, BG_GRAY_OFF, BG_TAB_ACTIVE, TEXT_TERTIARY } from '../common/Colors';

// 四个演示开关的专属色（各状态一色；未开启为浅灰）
const COLOR_ON: string = TEXT_WHITE;
const COLOR_OFF_BG: string = BG_GRAY_OFF;
const COLOR_OFF_TEXT: string = TEXT_TERTIARY;

@Entry
@Component
struct Index {
  // @State + @Observed 组合 = 深度观察：store.emergency 等属性变化会触发本页重绘。
  // 注意必须挂在被装饰的成员变量上，不能用方法返回临时对象，否则订阅挂不上（点了没反应）。
  @State store: DemoStore = DemoStore.instance();

  /**
   * 当前可见页签序号（changeIndex 语义：0=导航 / 1=落客 / 2=离站 / 3=行程）。
   * 仅用于把「本页是否可见」传给各页的 RoadNetMap，切页时立刻重画当前演示态，
   * 修「演示态切换时落客/离站地图慢一拍」；不参与任何业务逻辑，也不改变选中态。
   */
  @State activeTab: number = 0;

  /**
   * 页签控制器：落客/离站页「再次点击已选路线框」要跳回导航页，
   * 导航页空态的指引按钮要跳到落客/离站页 —— 都靠它切 Tab。
   * changeIndex(0)=导航 / 1=落客 / 2=离站 / 3=行程。
   */
  private tabsController: TabsController = new TabsController();

  /** 切换到指定页签（落客/离站跳导航、导航指引跳落客/离站都走它） */
  private switchTab(idx: number): void {
    this.tabsController.changeIndex(idx);
  }

  build() {
    Column() {
      // 页头：应用名 + 快照时间 + is_simulated 口径 + 当前演示态
      // 【为什么要压扁】用户要求「一进来除了上面和下面的就一整个画面都是地图」，
      // 而这一块原先占 400px（标题 + 三行文字 + 开关行 + 两行提示）。
      // 现在标题 16、两行文字 10、开关 26、提示缩成一行、上下内边距收到 4，
      // 整块压到约 250px，省下的 150px 全给地图。
      Column({ space: 1 }) {
        Row() {
          Text('hubflow 司机端')
            .fontSize(16)
            .fontWeight(FontWeight.Bold)
            .fontColor(TEXT_PRIMARY)
          Blank()
          Text('导航')
            .fontSize(11)
            .fontColor(ACCENT_COLOR_BLIND)
            .padding({ top: 1, bottom: 1, left: 8, right: 8 })
            .backgroundColor(BG_TAB_ACTIVE)
            .borderRadius(4)
        }
        .width('100%')

        Text(`快照 ${ROUTES_FIXTURE.request_id} · is_simulated=${ROUTES_FIXTURE.is_simulated}`)
          .fontSize(10)
          .fontColor(TEXT_TERTIARY)
        Text(`当前演示态：${this.store.activeName()}`)
          .fontSize(10)
          .fontColor(ACCENT_COLOR_BLIND)
      }
      .width('100%')
      .padding({ top: 4, bottom: 3, left: 14, right: 14 })
      .alignItems(HorizontalAlign.Start)

      // 演示态开关：互斥（点一个自动关其他）；按钮内联写在 build 里，样式随状态即时刷新
      Row({ space: 6 }) {
        Button('应急态')
          .fontSize(11)
          .height(26)
          .backgroundColor(this.store.emergency ? ACCENT_EMERGENCY : COLOR_OFF_BG)
          .fontColor(this.store.emergency ? COLOR_ON : COLOR_OFF_TEXT)
          .onClick(() => {
            this.store.setEmergency(!this.store.emergency);
          })

        Button('数据不可用')
          .fontSize(11)
          .height(26)
          .backgroundColor(this.store.unavailable ? ACCENT_UNAVAILABLE : COLOR_OFF_BG)
          .fontColor(this.store.unavailable ? COLOR_ON : COLOR_OFF_TEXT)
          .onClick(() => {
            this.store.setUnavailable(!this.store.unavailable);
          })

        Button('拒绝授权(降级)')
          .fontSize(11)
          .height(26)
          .backgroundColor(this.store.degraded ? ACCENT_DEGRADED : COLOR_OFF_BG)
          .fontColor(this.store.degraded ? COLOR_ON : COLOR_OFF_TEXT)
          .onClick(() => {
            this.store.setDegraded(!this.store.degraded);
          })

        Button('去色校验')
          .fontSize(11)
          .height(26)
          .backgroundColor(this.store.colorBlind ? ACCENT_COLOR_BLIND : COLOR_OFF_BG)
          .fontColor(this.store.colorBlind ? COLOR_ON : COLOR_OFF_TEXT)
          .onClick(() => {
            this.store.setColorBlind(!this.store.colorBlind);
          })
      }
      .width('100%')
      .padding({ left: 14, right: 14, bottom: 3 })
      .justifyContent(FlexAlign.Start)

      // 这行是给验收人看的操作提示：录屏举证时评审需要知道四个开关互斥、应急态的语义。
      // 【为什么缩成一行】原来两行占了 62px，现在一行 28px ——
      // 信息量不减，只压排版，把高度让给地图。
      Text('演示开关·互斥，再点取消；应急态 = 停止引导，改为「请服从现场指挥」')
        .fontSize(10)
        .fontColor(TEXT_TERTIARY)
        .width('100%')
        .padding({ left: 14, right: 14, bottom: 3 })

      // P0 四页：@ObjectLink 双向同步同一实例，能穿透 Tabs 页签缓存
      // 页签名按导航 App 语义命名（队长要求「app 最少做 4 到 5 个」）
      Tabs({ barPosition: BarPosition.End, controller: this.tabsController }) {
        TabContent() {
          RecommendPage({ store: this.store, active: this.activeTab === 0, switchTab: (idx: number): void => { this.switchTab(idx); } })
        }
        .tabBar('导航')

        TabContent() {
          DropoffPage({ store: this.store, active: this.activeTab === 1, switchTab: (idx: number): void => { this.switchTab(idx); } })
        }
        .tabBar('落客')

        TabContent() {
          DeparturePage({ store: this.store, active: this.activeTab === 2, switchTab: (idx: number): void => { this.switchTab(idx); } })
        }
        .tabBar('离站')

        TabContent() {
          HistoryPage({ store: this.store })
        }
        .tabBar('行程')
      }
      .onChange((idx: number) => {
        this.activeTab = idx;
      })
      .layoutWeight(1)
      .width('100%')

      // 数据来源角标：每页必现（M1-7）
      Column() {
        SimBadge()
      }
      .padding({ left: 14, right: 14, bottom: 8, top: 4 })
      .width('100%')
    }
    .width('100%')
    .height('100%')
    .backgroundColor(BG_BASE)
  }
}
