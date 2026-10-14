/**
 * 演示态开关（工程内模拟，非业务状态）：
 * - emergency 应急状态：停止路线引导，替换为「请服从现场指挥」（优先级高于一切推荐，手册 §11.1(3)）
 * - unavailable 数据不可用：等级一律灰色「数据不可用」，绝不显示成蓝色（TC-11）
 * - degraded 拒绝授权降级：降级为「手动选所在道路 / 只看路况」，流程不中断（TC-05 的 App 侧演示）
 * 仅供截图 / 录屏举证触发灰档与应急态，不代表真实业务逻辑。
 */
@Observed
export class DemoState {
  emergency: boolean = false;
  unavailable: boolean = false;
  degraded: boolean = false;
  degradedRoad: string = 'SEG-002';

  toggleEmergency(): void {
    this.emergency = !this.emergency;
  }

  toggleUnavailable(): void {
    this.unavailable = !this.unavailable;
  }

  toggleDegraded(): void {
    this.degraded = !this.degraded;
  }

  pickRoad(road: string): void {
    this.degradedRoad = road;
  }
}
