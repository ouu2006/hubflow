import { TRIPS_FIXTURE } from '../common/Fixture';
import { DemoStore } from '../common/DemoStore';
import { EmergencyCard, SectionTitle } from '../components/Common';
import { TripRecord } from '../common/Contract';
import { TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, BG_GRAY_LIGHT, STATE_ADOPTED, STATE_REJECTED } from '../common/Colors';

/** 页四：我的行程（本地会话记录，如实标注「未采纳推荐」） */
@Component
export struct HistoryPage {
  // @ObjectLink：与 Index 持有的同一个 DemoStore 实例双向同步
  // （Tabs 会缓存已创建的页签，只有 ObjectLink 这种显式链接才能保证父态一变就重绘）
  @ObjectLink store: DemoStore;


  build() {
    Scroll() {
      Column({ space: 12 }) {
        // 应急态只提示、不替换本页内容：应急停的是「路线引导」，行程记录与应急无关，仍应可读
        if (this.store.emergency) {
          Column({ space: 4 }) {
            EmergencyCard()
            Text('行程记录不受影响，仍可查看。')
              .fontSize(11)
              .fontColor(TEXT_TERTIARY)
          }
          .width('100%')
        }
        SectionTitle({ text: '我的行程（本次会话）' })

        ForEach(TRIPS_FIXTURE, (trip: TripRecord) => {
          Column({ space: 4 }) {
            Row() {
              Text(trip.session_id)
                .fontSize(13)
                .fontWeight(FontWeight.Medium)
                .fontColor(TEXT_PRIMARY)
              Blank()
              Text(trip.time_label)
                .fontSize(11)
                .fontColor(TEXT_TERTIARY)
            }
            .width('100%')
            Row() {
              Text(`路线 ${trip.path_id}`)
                .fontSize(12)
                .fontColor(TEXT_SECONDARY)
              Blank()
              Text(trip.adopted ? '已采纳推荐' : '未采纳推荐')
                .fontSize(12)
                .fontColor(trip.adopted ? STATE_ADOPTED : STATE_REJECTED)
            }
            .width('100%')
            Text(trip.note)
              .fontSize(12)
              .fontColor(TEXT_SECONDARY)
              .width('100%')
          }
          .width('100%')
          .padding(10)
          .backgroundColor(BG_GRAY_LIGHT)
          .borderRadius(8)
        }, (trip: TripRecord) => `${trip.session_id}_${trip.adopted}`)

        Text('行程记录仅保存在本机，行程结束即删除；不含车牌、身份等个人信息。')
          .fontSize(11)
          .fontColor(TEXT_TERTIARY)
          .width('100%')
      }
      .width('100%')
      .padding({ left: 14, right: 14, top: 8, bottom: 16 })
    }
    .width('100%')
    .height('100%')
  }
}
