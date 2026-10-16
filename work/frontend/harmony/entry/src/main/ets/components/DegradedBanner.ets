import { TEXT_WHITE, BG_DEGRADED_BAR, TEXT_ON_DEGRADED } from '../common/Colors';

/**
 * 降级提示条（拒绝授权后叠加显示）。
 *
 * 【关键设计：叠加而非替换 —— 这是修掉的一个真 bug】
 * 初版四页都写成 `if 应急 / else if 降级 / else 常态` 的三选一，
 * 降级分支里只有两行字，**地图、路线卡、图例全被 else 掉了**，
 * 实跑验证点「拒绝授权」后整页一片空白。
 *
 * 那违背 TC-05「拒绝授权后流程不中断」——
 * 降级的含义是「没有自动定位，但路线和路况照样能看，由司机手动确认在哪条路」，
 * 不是「什么都不给看」。所以现在这个组件是**叠在页面内容之上/之下的一条提示**，
 * 常态内容始终渲染，页面结构不动。
 *
 * 口径红线：页面文案不出现「实测 / 实时 / 现场」。
 */
@Component
export struct DegradedBanner {
  /** 场景名（导航 / 落客 / 离站），让司机知道当前在看哪一段的路线 */
  @Prop scene: string = '导航';

  build() {
    Column({ space: 3 }) {
      Row({ space: 6 }) {
        Text('⚠')
          .fontSize(16)
          .fontColor(TEXT_WHITE)
        Text(`已降级 · ${this.scene}仍可查看路线与路况`)
          .fontSize(14)
          .fontWeight(FontWeight.Bold)
          .fontColor(TEXT_WHITE)
      }
      .width('100%')
      Text('未授权自动定位，请手动确认当前所在道路后继续按图行驶（流程不中断）。')
        .fontSize(11)
        .fontColor(TEXT_ON_DEGRADED)
        .width('100%')
    }
    .padding({ top: 10, bottom: 10, left: 14, right: 14 })
    .width('100%')
    .backgroundColor(BG_DEGRADED_BAR)
    .borderRadius(8)
  }
}
