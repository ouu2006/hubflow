/**
 * 演示态单例（工程内模拟，非业务逻辑；四页共用一个对象，靠 @Observed 订阅刷新）。
 *
 * 为什么用单例而不是 @Prop 从父页往下传：Tabs 会缓存已创建的页签内容，
 * 父组件状态变化时缓存里的子页不保证重绘（实测「按钮亮了但页面没变 / 点一下没反应」），
 * 让每页直接订阅同一个 @Observed 对象最稳，且订阅粒度到属性级、更省渲染。
 *
 * 四个开关**互斥**（同一时刻只有一个状态），点谁就自动关掉其余：
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
    this.emergency = on;
    if (on) {
      this.clearOthers();
    }
  }

  setUnavailable(on: boolean): void {
    this.unavailable = on;
    if (on) {
      this.clearOthers();
    }
  }

  setDegraded(on: boolean): void {
    this.degraded = on;
    if (on) {
      this.clearOthers();
    }
  }

  setColorBlind(on: boolean): void {
    this.colorBlind = on;
    if (on) {
      this.clearOthers();
    }
  }

  private clearOthers(): void {
    this.emergency = false;
    this.unavailable = false;
    this.degraded = false;
    this.colorBlind = false;
  }

  /** 当前开启项的名称（页面顶栏用；空串表示常态） */
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
