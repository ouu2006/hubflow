import { ROUTES_FIXTURE, VEHICLES_FIXTURE, DEMO_VEHICLE_ID, DISCLAIMER_TEXT } from '../common/Fixture';
import { DemoStore } from '../common/DemoStore';
import { EmergencyCard, InfoRow, SectionTitle, LevelLegend, SegmentBar } from '../components/Common';
import { Vehicle, Alternative } from '../common/Contract';
import { TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, BG_GRAY_LIGHT, BG_GRAY_OFF, BG_GRAY_LIGHTER, ACCENT_COLOR_BLIND, BORDER_ACCENT, STATE_ADOPTED, STATE_REJECTED } from '../common/Colors';

@State private demoVehicleCache: Vehicle = (() => {
  for (let i = 0; i < VEHICLES_FIXTURE.vehicles.length; i++) {
    if (VEHICLES_FIXTURE.vehicles[i].vehicle_id === DEMO_VEHICLE_ID) {
      return VEHICLES_FIXTURE.vehicles[i];
    }
  }
  return VEHICLES_FIXTURE.vehicles[0];
})();

/**
 * 路线卡（推荐 / 备选通用）。
 *
 * 【为什么做成子组件而不是 @Builder】
 * @Builder 的值参数只在创建时求值一次，其内部对状态属性的读取不保证随状态重算
 * （实测：点开关后卡片不变）。做成 @Component 子组件、参数用 @Prop 声明后，
 * 父态一变必然整卡重绘。
 */
@Component
export struct RouteCard {
  @Prop pathId: string = '';
  @Prop etaMin: number = 0;
  @Prop segments: string[] = [];
  @Prop highlight: boolean = false;
  @Prop unavailable: boolean = false;
  @Prop colorBlind: boolean = false;

  build() {
    Column({ space: 6 }) {
      Row() {
        Text(this.highlight ? '推荐' : '备选')
          .fontSize(11)
          .fontColor(this.highlight ? TEXT_WHITE : TEXT_SECONDARY)
          .padding({ top: 2, bottom: 2, left: 6, right: 6 })
          .backgroundColor(this.highlight ? ACCENT_COLOR_BLIND : BORDER_ACCENT)
          .borderRadius(4)
        Text(this.pathId)
          .fontSize(14)
          .fontWeight(FontWeight.Medium)
          .fontColor(TEXT_PRIMARY)
          .margin({ left: 8 })
        Blank()
        Text(`约 ${this.etaMin} 分钟`)
          .fontSize(14)
          .fontColor(TEXT_PRIMARY)
      }
      .width('100%')

      Row({ space: 6 }) {
        ForEach(this.segments, (seg: string) => {
          SegmentBar({ segmentId: seg, unavailable: this.unavailable, colorBlind: this.colorBlind })
        }, (seg: string) => `${seg}_${this.unavailable}_${this.colorBlind}`)
      }
      .width('100%')
    }
    .width('100%')
    .padding(12)
    .backgroundColor(this.highlight ? BG_HIGHLIGHT : BG_GRAY_LIGHT)
    .borderRadius(10)
    .border(this.highlight ? { width: 1, color: BORDER_ACCENT } : { width: 0 })
  }
}

/** 页一：当前建议（推荐路线 + ≥2 条备选 + why + 前后车协同说明） */
@Component
export struct RecommendPage {
  // @ObjectLink：与 Index 持有的同一个 DemoStore 实例双向同步
  // （Tabs 会缓存已创建的页签，@ObjectLink 才能保证父态一变就重绘）
  @ObjectLink store: DemoStore;

  @State pickedRoad: string = 'SEG-002';

  build() {
    Scroll() {
      Column({ space: 12 }) {
        if (this.store.emergency) {
          // 应急态：停止路线引导，替换为「请服从现场指挥」
          EmergencyCard()
        } else if (this.store.degraded) {
          // 拒绝授权降级：手动选所在道路 / 只看路况，流程不中断
          Column({ space: 8 }) {
            SectionTitle({ text: '已降级：手动选所在道路 / 只看路况' })
            Text('未授权定位时仍可查看推荐与路况，流程不中断（TC-05）。')
              .fontSize(12)
              .fontColor(TEXT_SECONDARY)
            ForEach(['SEG-001', 'SEG-002', 'SEG-004'], (road: string) => {
              Row() {
                Text(road).fontSize(13).fontColor(TEXT_PRIMARY)
                Blank()
                Text(this.pickedRoad === road ? '已选' : '未选')
                  .fontSize(12)
                  .fontColor(this.pickedRoad === road ? ACCENT_COLOR_BLIND : TEXT_TERTIARY)
              }
              .width('100%')
              .padding(10)
              .backgroundColor(this.pickedRoad === road ? BG_HIGHLIGHT : BG_GRAY_LIGHTER)
              .border(this.pickedRoad === road ? { width: 1, color: BORDER_ACCENT } : { width: 0 })
              .borderRadius(8)
              .onClick(() => {
                this.pickedRoad = road;
              })
            }, (road: string) => `${road}_${this.pickedRoad}`)
          }
          .width('100%')
          .padding(12)
          .backgroundColor(BG_GRAY_LIGHT)
          .borderRadius(10)
        } else {
          // 推荐路线（arrival_route）
          RouteCard({
            pathId: ROUTES_FIXTURE.arrival_route.path_id,
            etaMin: ROUTES_FIXTURE.arrival_route.eta_min,
            segments: ROUTES_FIXTURE.arrival_route.segments,
            highlight: true,
            unavailable: this.store.unavailable,
            colorBlind: this.store.colorBlind
          })
          InfoRow({
            label: '落客点',
            value: `${ROUTES_FIXTURE.arrival_route.dropoff_point} · 步行接驳约 ${ROUTES_FIXTURE.arrival_route.walk_min} 分钟`
          })

          // 前后车协同说明（reservation.harm_check）
          Column({ space: 4 }) {
            SectionTitle({ text: '前后车协同说明' })
            Text(`已为本次行程预约 ${ROUTES_FIXTURE.reservation.slots_reserved} 个路段时段格子，租约 ${ROUTES_FIXTURE.reservation.lease_expire_s} 秒。`)
              .fontSize(12)
              .fontColor(TEXT_SECONDARY)
              .width('100%')
            Text(`您的进入不会让已登记的前车变慢（前车耗时最大增加 ${ROUTES_FIXTURE.reservation.harm_check.max_eta_increase_s} 秒，上限 ${ROUTES_FIXTURE.reservation.harm_check.max_eta_increase_s} 秒）；路径最大饱和度 ${ROUTES_FIXTURE.reservation.harm_check.max_slot_x}（上限 ${ROUTES_FIXTURE.reservation.harm_check.max_slot_x}）。`)
              .fontSize(12)
              .fontColor(TEXT_SECONDARY)
              .width('100%')
          }
          .width('100%')
          .padding(12)
          .backgroundColor(BG_GRAY_LIGHT)
          .borderRadius(10)

          // 备选（≥2 条，各带 reason）
          SectionTitle({ text: `备选路线（${ROUTES_FIXTURE.alternatives.length} 条）` })
          ForEach(ROUTES_FIXTURE.alternatives, (alt: Alternative) => {
            Column({ space: 4 }) {
              Row() {
                Text(alt.path_id).fontSize(13).fontWeight(FontWeight.Medium).fontColor(TEXT_PRIMARY)
                Blank()
                Text(`约 ${alt.eta_min} 分钟`).fontSize(13).fontColor(TEXT_PRIMARY)
              }
              .width('100%')
              Text(`原因：${alt.reason}`)
                .fontSize(12)
                .fontColor(TEXT_SECONDARY)
                .width('100%')
            }
            .width('100%')
            .padding(10)
            .backgroundColor(BG_GRAY_LIGHT)
            .borderRadius(8)
          }, (alt: Alternative) => alt.path_id)

          // why 与因素说明
          Column({ space: 4 }) {
            SectionTitle({ text: '为什么推荐这条' })
            Text(ROUTES_FIXTURE.why)
              .fontSize(12)
              .fontColor(TEXT_SECONDARY)
              .width('100%')
            if (ROUTES_FIXTURE.factors_note !== null) {
              Text(ROUTES_FIXTURE.factors_note)
                .fontSize(12)
                .fontColor(ACCENT_DEGRADED)
                .width('100%')
            }
          }
          .width('100%')
          .padding(12)
          .backgroundColor(BG_GRAY_LIGHT)
          .borderRadius(10)

          // 告知文案（必现）
          Text(DISCLAIMER_TEXT)
            .fontSize(12)
            .fontColor(TEXT_TERTIARY)
            .width('100%')
            .textAlign(TextAlign.Start)

          // 四级图例（三重编码）
          LevelLegend({ colorBlind: this.store.colorBlind, unavailable: this.store.unavailable })
        }

        // 绑定演示车（C-3）
        Column({ space: 4 }) {
          SectionTitle({ text: '绑定的演示车' })
          InfoRow({ label: 'vehicle_id', value: this.demoVehicleCache.vehicle_id })
          InfoRow({ label: '所在路段', value: `${this.demoVehicleCache.segment_id} · ${this.demoVehicleCache.offset_m} m` })
          InfoRow({ label: '状态 / 已引导', value: `${this.demoVehicleCache.state} / ${this.demoVehicleCache.guided ? '是' : '否'}` })
          InfoRow({ label: '位置来源', value: `${ROUTES_FIXTURE.location.source}（一期孪生真值，非真实定位）` })
        }
        .width('100%')
        .padding(12)
        .backgroundColor(BG_GRAY_LIGHTER)
        .borderRadius(10)
      }
      .width('100%')
      .padding({ left: 14, right: 14, top: 8, bottom: 16 })
    }
    .width('100%')
    .height('100%')
  }
}