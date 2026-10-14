import { ROUTES_FIXTURE, DISCLAIMER_TEXT } from '../common/Fixture';
import { DemoStore } from '../common/DemoStore';
import { EmergencyCard, SectionTitle, SegmentBar, LevelLegend } from '../components/Common';

/** 页三：离站路线（送完人之后怎么走，本项目独有；departure_route 必现 = TC-12） */
@Component
export struct DeparturePage {
  private store(): DemoStore {
    return DemoStore.instance();
  }


  build() {
    Scroll() {
      Column({ space: 12 }) {
        if (this.store().emergency) {
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
                SegmentBar({ segmentId: seg, unavailable: this.store().unavailable, colorBlind: this.store().colorBlind })
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

          LevelLegend({ colorBlind: this.store().colorBlind })

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
