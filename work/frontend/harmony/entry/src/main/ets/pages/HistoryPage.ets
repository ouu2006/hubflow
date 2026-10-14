import { TRIPS_FIXTURE } from '../common/Fixture';
import { EmergencyCard, SectionTitle } from '../components/Common';
import { TripRecord } from '../common/Contract';

/** 页四：我的行程（本地会话记录，如实标注「未采纳推荐」） */
@Component
export struct HistoryPage {
  @Prop emergency: boolean = false;

  build() {
    Scroll() {
      Column({ space: 12 }) {
        if (this.emergency) {
          EmergencyCard()
        }
        SectionTitle({ text: '我的行程（本次会话）' })

        ForEach(TRIPS_FIXTURE, (trip: TripRecord) => {
          Column({ space: 4 }) {
            Row() {
              Text(trip.session_id)
                .fontSize(13)
                .fontWeight(FontWeight.Medium)
                .fontColor('#1A1A1A')
              Blank()
              Text(trip.time_label)
                .fontSize(11)
                .fontColor('#8B8B8B')
            }
            .width('100%')
            Row() {
              Text(`路线 ${trip.path_id}`)
                .fontSize(12)
                .fontColor('#666666')
              Blank()
              Text(trip.adopted ? '已采纳推荐' : '未采纳推荐')
                .fontSize(12)
                .fontColor(trip.adopted ? '#006C45' : '#A06A00')
            }
            .width('100%')
            Text(trip.note)
              .fontSize(12)
              .fontColor('#666666')
              .width('100%')
          }
          .width('100%')
          .padding(10)
          .backgroundColor('#FAFAFA')
          .borderRadius(8)
        }, (trip: TripRecord) => trip.session_id)

        Text('行程记录仅保存在本机，行程结束即删除；不含车牌、身份等个人信息。')
          .fontSize(11)
          .fontColor('#8B8B8B')
          .width('100%')
      }
      .width('100%')
      .padding({ left: 14, right: 14, top: 8, bottom: 16 })
    }
    .width('100%')
    .height('100%')
  }
}
