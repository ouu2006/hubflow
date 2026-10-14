import { DemoState } from '../common/DemoState';
import { ROUTES_FIXTURE, VEHICLES_FIXTURE } from '../common/Fixture';
import { RecommendPage } from './RecommendPage';
import { DropoffPage } from './DropoffPage';
import { DeparturePage } from './DeparturePage';
import { HistoryPage } from './HistoryPage';
import { SimBadge } from '../components/Common';

@Entry
@Component
struct Index {
  @State demo: DemoState = new DemoState();

  @Builder
  demoButton(label: string, active: boolean, onTap: () => void) {
    Button(label)
      .fontSize(11)
      .height(28)
      .backgroundColor(active ? '#D54941' : '#E8E8E8')
      .fontColor(active ? '#FFFFFF' : '#666666')
      .onClick(onTap)
  }

  build() {
    Column() {
      // 页头：应用名 + 快照时间 + is_simulated 口径
      Column({ space: 2 }) {
        Text('hubflow 司机端')
          .fontSize(18)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1A1A1A')
        Text(`快照 ${ROUTES_FIXTURE.request_id} · is_simulated=${ROUTES_FIXTURE.is_simulated} · session ${ROUTES_FIXTURE.session_id}`)
          .fontSize(11)
          .fontColor('#8B8B8B')
      }
      .width('100%')
      .padding({ top: 10, bottom: 6, left: 14, right: 14 })
      .alignItems(HorizontalAlign.Start)

      // 演示态开关：用于触发应急态 / 数据不可用 / 降级态截图举证
      Row({ space: 8 }) {
        this.demoButton('应急态', this.demo.emergency, () => {
          this.demo.toggleEmergency();
        })
        this.demoButton('数据不可用', this.demo.unavailable, () => {
          this.demo.toggleUnavailable();
        })
        this.demoButton('拒绝授权(降级)', this.demo.degraded, () => {
          this.demo.toggleDegraded();
        })
      }
      .width('100%')
      .padding({ left: 14, right: 14, bottom: 6 })
      .justifyContent(FlexAlign.Start)

      // P0 四页
      Tabs({ barPosition: BarPosition.End }) {
        TabContent() {
          RecommendPage({ demo: this.demo })
        }
        .tabBar('推荐路线')

        TabContent() {
          DropoffPage({ demo: this.demo })
        }
        .tabBar('落客候客')

        TabContent() {
          DeparturePage({ demo: this.demo })
        }
        .tabBar('离站路线')

        TabContent() {
          HistoryPage({ demo: this.demo })
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
