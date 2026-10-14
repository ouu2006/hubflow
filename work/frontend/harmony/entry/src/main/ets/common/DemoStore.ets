/**
 * 演示态状态源（工程内模拟，非业务逻辑）。
 *
 * 【为什么不能写成 `private store() { return DemoStore.instance(); }` 再 `this.store().xxx`】
 * ArkUI 的 @Observed 只在「组件的被装饰成员变量」上读写属性时才建立订阅，
 * 依赖收集发生在 build 期间、被观察对象必须挂在 this 上。
 * 通过方法返回的临时对象读属性 → 订阅挂不上 → 点击后状态变了但界面不重绘
 * （实测：点四个开关全部无反应，就是这个原因）。
 *
 * 【正确姿势】
 * - Index 用 @State 持有单例（@State + @Observed 组合 = 深度观察，属性变化触发重绘）
 * - 四个子页用 @ObjectLink 接同一实例（双向同步，且能穿透 Tabs 的页签缓存）
 *
 * 四个开关**互斥**（同一时刻只有一个开启），点谁就自动关掉其余：
 * - emergency   应急状态：停止路线引导，替换为「请服从现场指挥」（手册 §11.1(3)，优先级高于一切推荐）
 * - unavailable 数据不可用：等级一律灰色「数据不可用」，绝不显示成蓝色（TC-11）
 * - degraded    拒绝授权降级：降级为「手动选所在道路 / 只看路况」，流程不中断（TC-05 App 侧演示）
 * - colorBlind  去色校验：抽掉颜色通道，验证图标 + 文字仍能区分四级（手册 §11.3）
 */
@Observed
export class DemoStore {
  emergency: boolean = false;
  unavailable: boolean = false;
  degraded: boolean = false;
  colorBlind: boolean = false;

  private static INSTANCE: DemoStore = new DemoStore();

  static instance(): DemoStore {
    return DemoStore.INSTANCE;
  }

  setEmergency(on: boolean): void {
    if (on) {
      // 先关掉其余三个，最后再打开自己。
      // （若先置位再统一清零，clearOthers 会把刚打开的自己一起关掉 → 点了完全没反应）
      this.unavailable = false;
      this.degraded = false;
      this.colorBlind = false;
      this.emergency = true;
    } else {
      this.emergency = false;
    }
  }

  setUnavailable(on: boolean): void {
    if (on) {
      this.emergency = false;
      this.degraded = false;
      this.colorBlind = false;
      this.unavailable = true;
    } else {
      this.unavailable = false;
    }
  }

  setDegraded(on: boolean): void {
    if (on) {
      this.emergency = false;
      this.unavailable = false;
      this.colorBlind = false;
      this.degraded = true;
    } else {
      this.degraded = false;
    }
  }

  setColorBlind(on: boolean): void {
    if (on) {
      this.emergency = false;
      this.unavailable = false;
      this.degraded = false;
      this.colorBlind = true;
    } else {
      this.colorBlind = false;
    }
  }

  /** 当前开启项的名称（页面顶栏用；'常态' 表示四态全关） */
  activeName(): string {
    if (this.emergency) {
      return '应急状态';
    }
    if (this.unavailable) {
      return '数据不可用';
    }
    if (this.degraded) {
      return '拒绝授权（降级）';
    }
    if (this.colorBlind) {
      return '去色校验';
    }
    return '常态';
  }
}