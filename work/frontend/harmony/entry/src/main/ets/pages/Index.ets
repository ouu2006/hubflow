import { DemoStore } from '../common/DemoStore';
import { ROUTES_FIXTURE } from '../common/Fixture';
import { RecommendPage } from './RecommendPage';
import { DropoffPage } from './DropoffPage';
import { DeparturePage } from './DeparturePage';
import { HistoryPage } from './HistoryPage';
import { SimBadge } from '../components/Common';

// 四个演示开关的专属色（各状态一色，不用统一红；未开启为浅灰）
const COLOR_ON: string = '#FFFFFF';
const ACCENT_EMERGENCY: string = '#C62828';
const ACCENT_UNAVAILABLE: string = '#5F5E5A';
const ACCENT_DEGRADED: string = '#A06A00';
const ACCENT_COLOR_BLIND: string = '#0052D9';
const COLOR_OFF_BG: string = '#F0F0F0';
const COLOR_OFF_TEXT: string = '#5F5E5A';

@Entry
@Component
struct Index {
  // 四页与按钮共享同一个状态对象：直接订阅，不再靠 @Prop 往下传
  private store(): DemoStore {
    return DemoStore.instance();
  }

  build() {
    Column() {
      // 页头：应用名 + 快照时间 + is_simulated 口径 + 当前演示态
      Column({ space: 2 }) {
        Text('hubflow 司机端')
          .fontSize(18)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1A1A1A')
        Text(`快照 ${ROUTES_FIXTURE.request_id} · is_simulated=${ROUTES_FIXTURE.is_simulated} · session ${ROUTES_FIXTURE.session_id}`)
          .fontSize(11)
          .fontColor('#8B8B8B')
        Text(`当前演示态：${this.store().activeName()}`)
          .fontSize(11)
          .fontColor('#0052D9')
      }
      .width('100%')
      .padding({ top: 10, bottom: 6, left: 14, right: 14 })
      .alignItems(HorizontalAlign.Start)

      // 演示态开关：互斥（点一个自动关其他），按钮内联写在 build 里，样式随状态即时刷新
      Row({ space: 8 }) {
        Button('应急态')
          .fontSize(11)
          .height(28)
          .backgroundColor(this.store().emergency ? ACCENT_EMERGENCY : COLOR_OFF_BG)
          .fontColor(this.store().emergency ? COLOR_ON : COLOR_OFF_TEXT)
          .onClick(() => {
            this.store().setEmergency(!this.store().emergency);
          })

        Button('数据不可用')
          .fontSize(11)
          .height(28)
          .backgroundColor(this.store().unavailable ? ACCENT_UNAVAILABLE : COLOR_OFF_BG)
          .fontColor(this.store().unavailable ? COLOR_ON : COLOR_OFF_TEXT)
          .onClick(() => {
            this.store().setUnavailable(!this.store().unavailable);
          })

        Button('拒绝授权(降级)')
          .fontSize(11)
          .height(28)
          .backgroundColor(this.store().degraded ? ACCENT_DEGRADED : COLOR_OFF_BG)
          .fontColor(this.store().degraded ? COLOR_ON : COLOR_OFF_TEXT)
          .onClick(() => {
            this.store().setDegraded(!this.store().degraded);
          })

        Button('去色校验')
          .fontSize(11)
          .height(28)
          .backgroundColor(this.store().colorBlind ? ACCENT_COLOR_BLIND : COLOR_OFF_BG)
          .fontColor(this.store().colorBlind ? COLOR_ON : COLOR_OFF_TEXT)
          .onClick(() => {
            this.store().setColorBlind(!this.store().colorBlind);
          })
      }
      .width('100%')
      .padding({ left: 14, right: 14, bottom: 4 })
      .justifyContent(FlexAlign.Start)

      Text('四个开关互斥：点一个自动关掉其余。应急态 = 停止路线引导、改为「请服从现场指挥」。')
        .fontSize(10)
        .fontColor('#8B8B8B')
        .width('100%')
        .padding({ left: 14, right: 14, bottom: 6 })

      // P0 四页
      Tabs({ barPosition: BarPosition.End }) {
        TabContent() {
          RecommendPage()
        }
        .tabBar('推荐路线')

        TabContent() {
          DropoffPage()
        }
        .tabBar('落客候客')

        TabContent() {
          DeparturePage()
        }
        .tabBar('离站路线')

        TabContent() {
          HistoryPage()
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
    .backgroundColor('#FFFFFF')
  }
}
