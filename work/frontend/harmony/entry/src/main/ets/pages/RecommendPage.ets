import { ROUTES_FIXTURE, VEHICLES_FIXTURE, DEMO_VEHICLE_ID, DISCLAIMER_TEXT } from '../common/Fixture';
import { DemoStore } from '../common/DemoStore';
import { EmergencyCard, InfoRow, SectionTitle, LevelLegend, SegmentBar } from '../components/Common';
import { Vehicle, Alternative } from '../common/Contract';

function demoVehicle(): Vehicle {
  for (let i = 0; i < VEHICLES_FIXTURE.vehicles.length; i++) {
    if (VEHICLES_FIXTURE.vehicles[i].vehicle_id === DEMO_VEHICLE_ID) {
      return VEHICLES_FIXTURE.vehicles[i];
    }
  }
  return VEHICLES_FIXTURE.vehicles[0];
}

/** 页一：当前建议（推荐路线 + ≥2 条备选 + why + 前后车协同说明） */
@Component
export struct RecommendPage {
  private store(): DemoStore {
    return DemoStore.instance();
  }

  @State pickedRoad: string = 'SEG-002';

  @Builder
  routeCard(pathId: string, etaMin: number, segments: string[], highlight: boolean) {
    Column({ space: 6 }) {
      Row() {
        Text(highlight ? '推荐' : '备选')
          .fontSize(11)
          .fontColor(highlight ? '#FFFFFF' : '#666666')
          .padding({ top: 2, bottom: 2, left: 6, right: 6 })
          .backgroundColor(highlight ? '#0052D9' : '#E8E8E8')
          .borderRadius(4)
        Text(pathId)
          .fontSize(14)
          .fontWeight(FontWeight.Medium)
          .fontColor('#1A1A1A')
          .margin({ left: 8 })
        Blank()
        Text(`约 ${etaMin} 分钟`)
          .fontSize(14)
          .fontColor('#1A1A1A')
      }
      .width('100%')

      Row({ space: 6 }) {
        ForEach(segments, (seg: string) => {
          SegmentBar({ segmentId: seg, unavailable: this.store().unavailable, colorBlind: this.store().colorBlind })
        }, (seg: string) => seg)
      }
      .width('100%')
    }
    .width('100%')
    .padding(12)
    .backgroundColor(highlight ? '#F0F5FF' : '#FAFAFA')
    .borderRadius(10)
    .border(highlight ? { width: 1, color: '#0052D9' } : { width: 0 })
  }

  build() {
    Scroll() {
      Column({ space: 12 }) {
        if (this.store().emergency) {
          // 应急态：停止路线引导，替换为「请服从现场指挥」
          EmergencyCard()
        } else if (this.store().degraded) {
          // 拒绝授权降级：手动选所在道路 / 只看路况，流程不中断
          Column({ space: 8 }) {
            SectionTitle({ text: '已降级：手动选所在道路 / 只看路况' })
            Text('未授权定位时仍可查看推荐与路况，流程不中断（TC-05）。')
              .fontSize(12)
              .fontColor('#666666')
            ForEach(['SEG-001', 'SEG-002', 'SEG-004'], (road: string) => {
              Row() {
                Text(road).fontSize(13).fontColor('#1A1A1A')
                Blank()
                Text(this.pickedRoad === road ? '已选' : '')
                  .fontSize(12)
                  .fontColor('#0052D9')
              }
              .width('100%')
              .padding(10)
              .backgroundColor(this.pickedRoad === road ? '#F0F5FF' : '#F5F5F5')
              .borderRadius(8)
              .onClick(() => {
                this.pickedRoad = road;
              })
            }, (road: string) => road)
          }
          .width('100%')
          .padding(12)
          .backgroundColor('#FAFAFA')
          .borderRadius(10)
        } else {
          // 推荐路线（arrival_route）
          this.routeCard(ROUTES_FIXTURE.arrival_route.path_id, ROUTES_FIXTURE.arrival_route.eta_min,
            ROUTES_FIXTURE.arrival_route.segments, true)
          InfoRow({
            label: '落客点',
            value: `${ROUTES_FIXTURE.arrival_route.dropoff_point} · 步行接驳约 ${ROUTES_FIXTURE.arrival_route.walk_min} 分钟`
          })

          // 前后车协同说明（reservation.harm_check）
          Column({ space: 4 }) {
            SectionTitle({ text: '前后车协同说明' })
            Text(`已为本次行程预约 ${ROUTES_FIXTURE.reservation.slots_reserved} 个路段时段格子，租约 ${ROUTES_FIXTURE.reservation.lease_expire_s} 秒。`)
              .fontSize(12)
              .fontColor('#666666')
              .width('100%')
            Text(`您的进入不会让已登记的前车变慢（前车耗时最大增加 ${ROUTES_FIXTURE.reservation.harm_check.max_eta_increase_s} 秒，上限 30 秒【待标定】）；路径最大饱和度 ${ROUTES_FIXTURE.reservation.harm_check.max_slot_x}（上限 0.85【待标定】）。`)
              .fontSize(12)
              .fontColor('#666666')
              .width('100%')
          }
          .width('100%')
          .padding(12)
          .backgroundColor('#FAFAFA')
          .borderRadius(10)

          // 备选（≥2 条，各带 reason）
          SectionTitle({ text: `备选路线（${ROUTES_FIXTURE.alternatives.length} 条）` })
          ForEach(ROUTES_FIXTURE.alternatives, (alt: Alternative) => {
            Column({ space: 4 }) {
              Row() {
                Text(alt.path_id).fontSize(13).fontWeight(FontWeight.Medium).fontColor('#1A1A1A')
                Blank()
                Text(`约 ${alt.eta_min} 分钟`).fontSize(13).fontColor('#1A1A1A')
              }
              .width('100%')
              Text(`原因：${alt.reason}`)
                .fontSize(12)
                .fontColor('#666666')
                .width('100%')
            }
            .width('100%')
            .padding(10)
            .backgroundColor('#FAFAFA')
            .borderRadius(8)
          }, (alt: Alternative) => alt.path_id)

          // why 与因素说明
          Column({ space: 4 }) {
            SectionTitle({ text: '为什么推荐这条' })
            Text(ROUTES_FIXTURE.why)
              .fontSize(12)
              .fontColor('#666666')
              .width('100%')
            if (ROUTES_FIXTURE.factors_note !== null) {
              Text(ROUTES_FIXTURE.factors_note)
                .fontSize(12)
                .fontColor('#A06A00')
                .width('100%')
            }
          }
          .width('100%')
          .padding(12)
          .backgroundColor('#FAFAFA')
          .borderRadius(10)

          // 告知文案（必现）
          Text(DISCLAIMER_TEXT)
            .fontSize(12)
            .fontColor('#8B8B8B')
            .width('100%')
            .textAlign(TextAlign.Start)

          // 四级图例（三重编码）
          LevelLegend({ colorBlind: this.store().colorBlind })
        }

        // 绑定演示车（C-3）
        Column({ space: 4 }) {
          SectionTitle({ text: '绑定的演示车' })
          InfoRow({ label: 'vehicle_id', value: demoVehicle().vehicle_id })
          InfoRow({ label: '所在路段', value: `${demoVehicle().segment_id} · ${demoVehicle().offset_m} m` })
          InfoRow({ label: '状态 / 已引导', value: `${demoVehicle().state} / ${demoVehicle().guided ? '是' : '否'}` })
          InfoRow({ label: '位置来源', value: `${ROUTES_FIXTURE.location.source}（一期孪生真值，非真实定位）` })
        }
        .width('100%')
        .padding(12)
        .backgroundColor('#F5F5F5')
        .borderRadius(10)
      }
      .width('100%')
      .padding({ left: 14, right: 14, top: 8, bottom: 16 })
    }
    .width('100%')
    .height('100%')
  }
}
