import { ROUTES_FIXTURE } from '../common/Fixture';
import { EmergencyCard, InfoRow, SectionTitle } from '../components/Common';

/** 页二：落客 / 候客指引（停靠点类型、位置、步行接驳时长） */
@Component
export struct DropoffPage {
  @Prop emergency: boolean = false;
  @Prop unavailable: boolean = false;
  @Prop colorBlind: boolean = false;

  build() {
    Scroll() {
      Column({ space: 12 }) {
        if (this.emergency) {
          EmergencyCard()
        } else {
          SectionTitle({ text: '落客 / 候客指引' })

          Column({ space: 6 }) {
            InfoRow({ label: '停靠点', value: ROUTES_FIXTURE.arrival_route.dropoff_point })
            InfoRow({ label: '停靠点类型', value: '即停即走（社会车辆落客区）' })
            InfoRow({ label: '步行接驳', value: `约 ${ROUTES_FIXTURE.arrival_route.walk_min} 分钟进站` })
            InfoRow({ label: '预计等待', value: '按预约时段入场，无需排队等待' })
          }
          .width('100%')
          .padding(12)
          .backgroundColor('#FAFAFA')
          .borderRadius(10)

          Column({ space: 4 }) {
            SectionTitle({ text: '提示' })
            Text('请在预约时段内到达停靠点；超时未确认将自动释放时段预约。')
              .fontSize(12)
              .fontColor('#666666')
              .width('100%')
            Text('送完乘客后请查看「离站路线」页，系统已为您规划离站方向。')
              .fontSize(12)
              .fontColor('#666666')
              .width('100%')
          }
          .width('100%')
          .padding(12)
          .backgroundColor('#F5F5F5')
          .borderRadius(10)

          if (this.unavailable) {
            // 数据不可用：灰色，绝不显示成蓝色（TC-11）
            Text('停靠点实时余量：数据不可用')
              .fontSize(13)
              .fontColor('#8B8B8B')
              .width('100%')
              .padding(10)
              .backgroundColor('#F5F5F5')
              .borderRadius(8)
          }
        }
      }
      .width('100%')
      .padding({ left: 14, right: 14, top: 8, bottom: 16 })
    }
    .width('100%')
    .height('100%')
  }
}
