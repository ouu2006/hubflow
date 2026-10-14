import { ROUTES_FIXTURE, DISCLAIMER_TEXT } from '../common/Fixture';
import { DemoStore } from '../common/DemoStore';
import { EmergencyCard, SectionTitle, SegmentBar, LevelLegend } from '../components/Common';
import {TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, BG_GRAY_LIGHT, BORDER_ACCENT} from '../common/Colors';

/** 页三：离站路线（送完人之后怎么走，本项目独有；departure_route 必现 = TC-12） */
@Component
export struct DeparturePage {
  // @ObjectLink：与 Index 持有的同一个 DemoStore 实例双向同步
  // （Tabs 会缓存已创建的页签，只有 ObjectLink 这种显式链接才能保证父态一变就重绘）
  @ObjectLink store: DemoStore;


  build() {
    Scroll() {
      Column({ space: 12 }) {
        if (this.store.emergency) {
          // 应急态：停止路线引导
          EmergencyCard()
        } else if (this.store.degraded) {
          SectionTitle({ text: '已降级：手动确认离站方向 / 只看路况' })
          Text('未授权定位时仍可查看离站路线与路况，流程不中断（TC-05）。')
            .fontSize(12)
            .fontColor(TEXT_SECONDARY)
            .width('100%')
        } else {
          SectionTitle({ text: '送完人之后怎么走（离站路线）' })

          // departure_route 必现
          Column({ space: 6 }) {
            Row() {
              Text(`离站路线 ${ROUTES_FIXTURE.departure_route.path_id}`)
                .fontSize(14)
                .fontWeight(FontWeight.Medium)
                .fontColor(TEXT_PRIMARY)
              Blank()
              Text(`约 ${ROUTES_FIXTURE.departure_route.eta_min} 分钟`)
                .fontSize(14)
                .fontColor(TEXT_PRIMARY)
            }
            .width('100%')

            Row({ space: 6 }) {
              ForEach(ROUTES_FIXTURE.departure_route.segments, (seg: string) => {
                SegmentBar({ segmentId: seg, unavailable: this.store.unavailable, colorBlind: this.store.colorBlind })
              }, (seg: string) => `${seg}_${this.store.unavailable}_${this.store.colorBlind}`)
            }
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
      }
      .width('100%')
      .padding({ left: 14, right: 14, top: 8, bottom: 16 })
    }
    .width('100%')
    .height('100%')
  }
}
