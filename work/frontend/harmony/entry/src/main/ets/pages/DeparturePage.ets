import { DemoState } from '../common/DemoState';
import { ROUTES_FIXTURE, DISCLAIMER_TEXT } from '../common/Fixture';
import { EmergencyCard, SectionTitle } from '../components/Common';

/** 页三：离站路线（送完人之后怎么走，本项目独有；departure_route 必现 = TC-12） */
@Component
export struct DeparturePage {
  @ObjectLink demo: DemoState;

  build() {
    Scroll() {
      Column({ space: 12 }) {
        if (this.demo.emergency) {
          // 应急态：停止路线引导
          EmergencyCard()
        } else {
          SectionTitle({ text: '送完人之后怎么走（离站路线）' })

          // departure_route 必现
          Column({ space: 6 }) {
            Row() {
              Text(`离站路线 ${ROUTES_FIXTURE.departure_route.path_id}`)
                .fontSize(14)
                .fontWeight(FontWeight.Medium)
                .fontColor('#1A1A1A')
              Blank()
              Text(`约 ${ROUTES_FIXTURE.departure_route.eta_min} 分钟`)
                .fontSize(14)
                .fontColor('#1A1A1A')
            }
            .width('100%')

            Row({ space: 6 }) {
              ForEach(ROUTES_FIXTURE.departure_route.segments, (seg: string) => {
                Column({ space: 4 }) {
                  Text(seg)
                    .fontSize(12)
                    .fontColor(this.demo.unavailable ? '#8B8B8B' : '#1A1A1A')
                  Text(this.demo.unavailable ? '数据不可用' : '离站方向')
                    .fontSize(11)
                    .fontColor(this.demo.unavailable ? '#8B8B8B' : '#006C45')
                }
                .padding(6)
                .backgroundColor('#F5F5F5')
                .borderRadius(6)
                .layoutWeight(1)
              }, (seg: string) => seg)
            }
            .width('100%')
          }
          .width('100%')
          .padding(12)
          .backgroundColor('#F0F5FF')
          .borderRadius(10)
          .border({ width: 1, color: '#0052D9' })

          Text('落客完成后按此路线驶离站前区域，避免与社会车辆候客流线交叉。')
            .fontSize(12)
            .fontColor('#666666')
            .width('100%')

          Text(DISCLAIMER_TEXT)
            .fontSize(12)
            .fontColor('#8B8B8B')
            .width('100%')
        }
      }
      .width('100%')
      .padding({ left: 14, right: 14, top: 8, bottom: 16 })
    }
    .width('100%')
    .height('100%')
  }
}
