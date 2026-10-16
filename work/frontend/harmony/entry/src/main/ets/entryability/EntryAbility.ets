import { AbilityConstant, UIAbility, Want } from '@kit.AbilityKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { window } from '@kit.ArkUI';
import { DemoStore } from '../common/DemoStore';

const TAG: string = 'HubflowDriver';
const DOMAIN: number = 0x0000;

export default class EntryAbility extends UIAbility {
  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    hilog.info(DOMAIN, TAG, '%{public}s', 'EntryAbility onCreate');
  }

  onDestroy(): void {
    hilog.info(DOMAIN, TAG, '%{public}s', 'EntryAbility onDestroy');
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    windowStage.loadContent('pages/Index', (err) => {
      if (err.code) {
        hilog.error(DOMAIN, TAG, '%{public}s', `loadContent failed: ${JSON.stringify(err)}`);
        return;
      }
      hilog.info(DOMAIN, TAG, '%{public}s', 'loadContent succeed');
    });
  }

  onWindowStageDestroy(): void {
  }

  onForeground(): void {
  }

  /**
   * 退到后台时必须停掉巡航定时器。
   *
   * 【为什么这是必须修的资源泄漏】
   * DemoStore 是静态单例，它的 setInterval（40ms 一帧）不随页面销毁而停。
   * App 切后台后浏览器/系统仍会让定时器跑，于是后台持续 bumpEpoch()，
   * 白耗电；更糟的是切回来时 driveRatio 已经推进了一大截，
   * 用户看到的是「我没动，车自己跑了一段」—— 正是之前修过的那个投诉。
   */
  onBackground(): void {
    DemoStore.instance().stopCruise();
  }
}
