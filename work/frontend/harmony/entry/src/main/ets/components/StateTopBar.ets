import { DemoStore } from '../common/DemoStore';
import { TEXT_ON_DEGRADED, TEXT_ON_EMERGENCY_BAR_SUB, TEXT_ON_UNAVAILABLE_BAR_SUB, TEXT_WHITE } from '../common/Colors';

/**
 * 应急 / 降级 / 数据不可用 顶部提示条 —— 四个页面共用，
 * **固定在页面最上方、滚动区之外**。
 *
 * 【为什么抽成独立组件而不是复用 NavActionBar 的分支】
 * 用户原话：「应急态导航页面的上方是有个红的警告弹窗，
 *   然后呢落客这里上方就没有，只能滑到下面看才能看到红色应急状态，离站这里也是」
 * 初版只有 NavActionBar 里那三个分支（导航条本体 / 应急红条 / 降级琥珀条），
 * 而 NavActionBar 只有导航页挂了。另外两页的应急提示是
 * Scroll 里的 `EmergencyCard()` —— 在地图**下面**，不滚动就看不见。
 * 应急提示必须第一眼可见（安全相关），所以这里单独抽一个「贴在页顶」的条，
 * 三个页面（导航 / 落客 / 离站）统一挂在 Column 的第一个子节点。
 *
 * 【为什么不能是 @Builder】
 * @Builder 的值参数只在创建时求值一次，store.emergency 变化后不重算（已踩过）。
 * @ObjectLink 指向同一个 DemoStore 实例，父态一变整条必然重绘。
 *
 * 【口径】
 * 「请服从现场指挥」是手册 §11.1(3) 的固定措辞，属于「现场」二字的唯一例外，
 * 不可改写、不可替换成别的说法。
 */
const BAR_BG_EMERGENCY: string = '#8E1F1F';   // 应急态深红（与导航条同一色）
const BAR_BG_DEGRADED: string = '#7A5A16';    // 拒绝授权降级（琥珀棕，压住白字）
const BAR_BG_UNAVAILABLE: string = '#5A6570'; // 数据不可用（灰蓝，压住白字）

@Component
export struct StateTopBar {
  /** @ObjectLink：与页面持有的必须是同一个 DemoStore 实例 */
  @ObjectLink store: DemoStore;
  /** 降级提示的场景名（导航 / 落客 / 离站），只用于让司机知道是哪一步降级了 */
  @Prop scene: string = '';

  build() {
    /**
     * 【常态不渲染任何东西】
     * 用 if/else 三选一而不是 `if (emergency) {...}` + 外面包一层：
     * 常态下返回空 Column 占位，Column 有 0 高度，不占版面也不留缝。
     */
    if (this.store.emergency) {
      Column({ space: 4 }) {
        Row({ space: 8 }) {
          Text('⚠')
            .fontSize(20)
            .fontColor('TEXT_WHITE')
          Text('请服从现场指挥')
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .fontColor('TEXT_WHITE')
        }
        .width('100%')
        Text(this.scene.length > 0 ? `${this.scene}路线引导已停止 · 应急处置优先` : '路线引导已停止 · 应急处置优先')
          .fontSize(11)
          .fontColor('TEXT_ON_EMERGENCY_BAR_SUB')
          .width('100%')
      }
      .alignItems(HorizontalAlign.Start)
      .padding({ top: 12, bottom: 12, left: 16, right: 16 })
      .width('100%')
      .backgroundColor(BAR_BG_EMERGENCY)
    } else if (this.store.degraded) {
      /**
       * 【降级态：琥珀色，不是红色】
       * 降级的含义是「没有自动定位，但路线和路况照样能看，由司机手动确认在哪条路」
       * （TC-05 流程不中断）。若也用红色，司机会把「还能继续开」误判成「出事了停下车」。
       * 红色只留给真正的应急（引导已停止）。
       */
      Column({ space: 4 }) {
        Row({ space: 8 }) {
          Text('⚠')
            .fontSize(18)
            .fontColor('TEXT_WHITE')
          Text(this.scene.length > 0 ? `${this.scene}已降级 · 未授权定位` : '已降级 · 未授权定位')
            .fontSize(16)
            .fontWeight(FontWeight.Bold)
            .fontColor('TEXT_WHITE')
        }
        .width('100%')
        Text('仍可查看路线与路况，手动确认所在道路即可')
          .fontSize(11)
          .fontColor('TEXT_ON_DEGRADED')
          .width('100%')
      }
      .alignItems(HorizontalAlign.Start)
      .padding({ top: 12, bottom: 12, left: 16, right: 16 })
      .width('100%')
      .backgroundColor(BAR_BG_DEGRADED)
    } else if (this.store.unavailable) {
      /**
       * 【数据不可用：灰色条 —— 与应急/降级同一套版式，用户明确要求「也要这种弹窗」】
       * 用户给的三张参考截图（应急红条、离站降级条、落客降级条）都是同一个版式：
       *   左一个⚠ 图标 + 粗体标题 + 下面一行小字说明，色块铺满页顶。
       * 数据不可用沿用同一版式，只换颜色为灰 —— 三档状态长得一样、只靠颜色区分，
       * 司机不用重新学版式；颜色语义也与前两档严格对齐（红=应急、琥珀=降级、灰=不可用）。
       *
       * 【为什么灰不是红】
       * 手册 TC-11：不可用一律灰、绝不显示成蓝色（蓝色在本App 里=「有数据」）。
       * 若也用红色，司机会把「只是拿不到数据」误判成「出事停车」，反而更危险。
       */
      Column({ space: 4 }) {
        Row({ space: 8 }) {
          Text('⚠')
            .fontSize(18)
            .fontColor('TEXT_WHITE')
          Text(this.scene.length > 0 ? `${this.scene}数据不可用` : '数据不可用')
            .fontSize(16)
            .fontWeight(FontWeight.Bold)
            .fontColor('TEXT_WHITE')
        }
        .width('100%')
        Text('暂不可选择路线，数据恢复后自动继续')
          .fontSize(11)
          .fontColor('TEXT_ON_UNAVAILABLE_BAR_SUB')
          .width('100%')
      }
      .alignItems(HorizontalAlign.Start)
      .padding({ top: 12, bottom: 12, left: 16, right: 16 })
      .width('100%')
      .backgroundColor(BAR_BG_UNAVAILABLE)
    }
  }
}