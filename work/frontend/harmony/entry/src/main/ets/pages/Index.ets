import { DemoStore } from '../common/DemoStore';
import { ROUTES_FIXTURE } from '../common/Fixture';
import { RecommendPage } from './RecommendPage';
import { DropoffPage } from './DropoffPage';
import { DeparturePage } from './DeparturePage';
import { HistoryPage } from './HistoryPage';
import { SimBadge } from '../components/Common';
import { TEXT_PRIMARY, TEXT_WHITE, ACCENT_EMERGENCY, ACCENT_UNAVAILABLE, ACCENT_DEGRADED, ACCENT_COLOR_BLIND, BG_BASE, BG_GRAY_OFF, TEXT_TERTIARY } from '../common/Colors';

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

  build() {
    Column() {
      // 页头：应用名 + 快照时间 + is_simulated 口径 + 当前演示态
      Column({ space: 2 }) {
        Text('hubflow 司机端')
          .fontSize(18)
          .fontWeight(FontWeight.Bold)
          .fontColor(TEXT_PRIMARY)
        Text(`快照 ${ROUTES_FIXTURE.request_id} · is_simulated=${ROUTES_FIXTURE.is_simulated} · session ${ROUTES_FIXTURE.session_id}`)
          .fontSize(11)
          .fontColor(TEXT_TERTIARY)
        Text(`当前演示态：${this.store.activeName()}`)
          .fontSize(11)
          .fontColor(ACCENT_COLOR_BLIND)
      }
      .width('100%')
      .padding({ top: 10, bottom: 6, left: 14, right: 14 })
      .alignItems(HorizontalAlign.Start)

      // 演示态开关：互斥（点一个自动关其他）；按钮内联写在 build 里，样式随状态即时刷新
      Row({ space: 8 }) {
        Button('应急态')
          .fontSize(11)
          .height(28)
          .backgroundColor(this.store.emergency ? ACCENT_EMERGENCY : COLOR_OFF_BG)
          .fontColor(this.store.emergency ? COLOR_ON : COLOR_OFF_TEXT)
          .onClick(() => {
            this.store.setEmergency(!this.store.emergency);
          })

        Button('数据不可用')
          .fontSize(11)
          .height(28)
          .backgroundColor(this.store.unavailable ? ACCENT_UNAVAILABLE : COLOR_OFF_BG)
          .fontColor(this.store.unavailable ? COLOR_ON : COLOR_OFF_TEXT)
          .onClick(() => {
            this.store.setUnavailable(!this.store.unavailable);
          })

        Button('拒绝授权(降级)')
          .fontSize(11)
          .height(28)
          .backgroundColor(this.store.degraded ? ACCENT_DEGRADED : COLOR_OFF_BG)
          .fontColor(this.store.degraded ? COLOR_ON : COLOR_OFF_TEXT)
          .onClick(() => {
            this.store.setDegraded(!this.store.degraded);
          })

        Button('去色校验')
          .fontSize(11)
          .height(28)
          .backgroundColor(this.store.colorBlind ? ACCENT_COLOR_BLIND : COLOR_OFF_BG)
          .fontColor(this.store.colorBlind ? COLOR_ON : COLOR_OFF_TEXT)
          .onClick(() => {
            this.store.setColorBlind(!this.store.colorBlind);
          })
      }
      .width('100%')
      .padding({ left: 14, right: 14, bottom: 4 })
      .justifyContent(FlexAlign.Start)

      // 这行是给验收人看的操作提示：录屏举证时评审需要知道四个开关互斥、应急态的语义。
      // 措辞已精简（原来两句话太啰嗦）；正式 App 交付时由 #93 接真实数据后移除。
      Text('演示开关·互斥，再点取消。应急态 = 停止路线引导，改为「请服从现场指挥」')
        .fontSize(10)
        .fontColor(TEXT_TERTIARY)
        .width('100%')
        .padding({ left: 14, right: 14, bottom: 6 })

      // P0 四页：@ObjectLink 双向同步同一实例，能穿透 Tabs 页签缓存
      Tabs({ barPosition: BarPosition.End }) {
        TabContent() {
          RecommendPage({ store: this.store })
        }
        .tabBar('推荐路线')

        TabContent() {
          DropoffPage({ store: this.store })
        }
        .tabBar('落客候客')

        TabContent() {
          DeparturePage({ store: this.store })
        }
        .tabBar('离站路线')

        TabContent() {
          HistoryPage({ store: this.store })
        }
        .tabBar('我的行程')
      }
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