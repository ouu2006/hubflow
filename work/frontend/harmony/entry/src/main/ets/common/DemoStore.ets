import { ROUTES_FIXTURE } from './Fixture';
import { PlanMeta, arrivalPlans, buildPlanRoute, departurePlans, planAt, planOf, levelAtRatio } from './RoutePlan';
import { RoutePath } from './MapPort';
import { REAL_ROUTE_TOTAL_M } from './RealNet';
import { levelSpeedFactorOf } from './LevelMeta';

/** 自动巡航：每帧间隔(ms) 与单帧基础推进量(ratio/帧，等级1流畅时)。调这两个值可改总时长。 */
const CRUISE_TICK_MS: number = 40;
const CRUISE_BASE_STEP: number = 0.006;

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
 * - degraded    拒绝授权降级：叠加降级提示条，路线与路况照常给，流程不中断（TC-05）
 * - colorBlind  去色校验：抽掉颜色通道，验证图标 + 文字仍能区分四级（手册 §11.3）
 */
@Observed
export class DemoStore {
  emergency: boolean = false;
  unavailable: boolean = false;
  degraded: boolean = false;
  colorBlind: boolean = false;

  /**
   * 当前选中的路线方案序号：0 = 路线一（推荐）, 1 = 路线二, 2 = 路线三。
   * 点底部「变道」在三条方案间**循环切换**（2 → 回到 0）。
   * 方案卡高亮、地图路线臂、转向条文案与图标、路段构成四处都读这个值，整屏联动。
   */
  pickedIndex: number = 0;

  /**
   * 当前选中的路径号（契约 path_id）。随 pickedIndex 同步，
   * 供需要按 path_id 取数据的地方（路段构成等）使用。
   */
  pickedPathId: string = ROUTES_FIXTURE.arrival_route.path_id;

  /**
   * 当前选中的**离站**方案 path_id。
   *
   * 【为什么要和到站的 pickedPathId 分开】
   * 契约里 `arrival_route` 与 `departure_route` 是两个独立字段，
   * 备选方案也各不相同。用户要求「离站也要能选择」，
   * 那离站页就得有自己的选中态 —— 复用同一个 pickedPathId 会出现：
   * 在导航页选了 P-3，切到离站页发现离站方案被同步切成 P-3，
   * 而离站根本没这条路线。
   */
  departurePathId: string = ROUTES_FIXTURE.departure_route.path_id;

  /**
   * 导航页「当前在导哪条路线」的上下文（见 setNavMode）。
   * 'empty'    = 刚进导航、还没选路线（显示原生空地图 + 指引按钮）
   * 'arrival'  = 从落客页选了到站路线（导航按到站路线行驶）
   * 'departure' = 从离站页选了离站路线（导航按离站路线行驶）
   * 落客/离站页「再次点击已选路线框」→ setNavMode(...) + 跳回导航。
   */
  navMode: string = 'empty';

  /** 选中某个离站方案 */
  pickDeparturePath(pathId: string): void {
    // 数据不可用 / 应急态：禁止选路线（见 routeLocked 的注释）
    if (this.routeLocked()) {
      return;
    }
    this.departurePathId = planOf(departurePlans(), pathId).pathId;
    this.bumpEpoch();
  }

  /**
   * 锁定导航页要导的路线上下文，并让车从起点开始（resetDrive）。
   * 落客页点已选路线框 → setNavMode('arrival')；离站页 → setNavMode('departure')。
   *
   * 【这里加锁是用户明确要求的】
   * 「应急态导航页面始终保持空态」「数据不可用的时候，落客页和离站页也不可以跳转到导航」
   * —— 所以禁止态下调用它必须**什么都不做**，而不是照样切进导航态。
   * 只在 UI 层把按钮置灰是不够的：UI 漏一处就能点进来，
   * 数据层再挡一道才是真的封死。
   */
  setNavMode(mode: string): void {
    if (this.routeLocked()) {
      // 应急 / 不可用 → 强制停在空态，绝不进导航
      this.navMode = 'empty';
      this.resetDrive();
      this.bumpEpoch();
      return;
    }
    this.navMode = mode;
    this.resetDrive();
    this.bumpEpoch();
  }

  /** 离站方案的转向总数（与到站 maneuverTotal 同理，别写死） */
  departureManeuverTotal(): number {
    const plan: PlanMeta = planOf(departurePlans(), this.departurePathId);
    return buildPlanRoute(plan, true).maneuvers.length;
  }

  /** 导航页当前上下文下的转向总数（按 navMode 选数据源） */
  navManeuverTotal(): number {
    return this.navMode === 'departure' ? this.departureManeuverTotal() : this.maneuverTotal();
  }

  /** 导航页「当前生效的方案」：离站走离站列表，到站走到站列表 */
  navPlan(): PlanMeta {
    return this.navMode === 'departure'
      ? planOf(departurePlans(), this.departurePathId)
      : planOf(arrivalPlans(), this.pickedPathId);
  }

  /** 导航页「当前生效的转向序列」：与地图几何同源 */
  navManeuvers() {
    return buildPlanRoute(this.navPlan(), this.navMode === 'departure').maneuvers;
  }

  /**
   * 自动巡航：点一次「开始导航」后，车标沿当前路线**平滑行驶到终点**后停下
   * （到站后的状态与原「已到达」完全一致）。这是本轮需求：把「一点一动」改成「一点自动到终点」。
   *
   * 速度按当前路段等级变化：流畅(1) 最快 → 缓行(2) → 拥堵(3) → 严重拥堵(4) 最慢，
   * 不再「一下子跳到终点」。每帧推进 driveRatio 并 bumpEpoch() 触发地图重画
   * （双 Canvas 翻转重建节点），于是车标、引导红线、已走灰线都跟着动。
   *
   * 【用户投诉：「我只是选了地图，它就自己开始导航了」—— 这里加显式门闸】
   * 唯一的启动入口是底部「开始导航」按钮 → startCruise()，它把 navStarted 置 true。
   * cruiseTick 每帧再校验一次 navStarted，任何其他路径（选路线 / 变道 / 切演示态 /
   * 切页签 / 组件重建）都不可能让车自己走起来 —— 即便将来有人漏写 stopCruise，
   * 定时器也只会空转，不会推动车标。
   */
  startCruise(): void {
    if (this.cruising) {
      return; // 已在巡航，忽略重复点击
    }
    if (this.driveRatio >= 1) {
      return; // 已到终点，此刻按钮应显示「重走」
    }
    // 数据不可用 / 应急态：不允许启动导航（UI 已置灰，这里再挡一道）
    if (this.routeLocked()) {
      return;
    }
    this.navStarted = true;
    this.cruising = true;
    const plan: PlanMeta = this.navPlan();
    const isDep: boolean = this.navMode === 'departure';
    const route: RoutePath = buildPlanRoute(plan, isDep);
    const self: DemoStore = this;
    this.cruiseTimer = setInterval(() => {
      self.cruiseTick(route, isDep);
    }, CRUISE_TICK_MS);
  }

  /** 巡航每帧：按「当前所在路段等级」快慢推进 driveRatio，到终点即停 */
  private cruiseTick(route: RoutePath, isDep: boolean): void {
    /**
     * 【门闸：没按过「开始导航」就一步都不许走】
     * 用户原话「这个继续这个按钮我都没有点，我只是选了地图，
     * 它就自己自己在那里动，自己在那里行走了」。
     * 所以推进前先校验：必须是显式启动过、且仍在巡航中，才动 driveRatio。
     */
    if (!this.navStarted || !this.cruising) {
      return;
    }
    const lvl: number = levelAtRatio(route, this.driveRatio);
    const factor = levelSpeedFactorOf(lvl);
    this.driveRatio += CRUISE_BASE_STEP * factor;
    if (this.driveRatio >= 1) {
      this.driveRatio = 1;
      this.maneuverIndex = route.maneuvers.length - 1;
      this.stopCruise();
      this.bumpEpoch();
      return;
    }
    // 同步「附近已过的转向序号」，顶部转向条文案随车推进
    this.maneuverIndex = this.maneuverIndexAtRatioIn(route);
    this.bumpEpoch();
  }

  /** 停止巡航并清定时器（切演示态 / 变道 / 退出 / 重走 都会调用，避免定时器泄漏） */
  stopCruise(): void {
    if (this.cruiseTimer !== 0) {
      clearInterval(this.cruiseTimer);
      this.cruiseTimer = 0;
    }
    this.cruising = false;
  }

  /** 由 driveRatio 反推「附近已过的转向序号」，保持转向条文案与车标进度同步 */
  private maneuverIndexAtRatioIn(route: RoutePath): number {
    const list = route.maneuvers;
    if (list.length === 0) {
      return 0;
    }
    let idx: number = 0;
    for (let i = 0; i < list.length; i++) {
      if (list[i].distM / REAL_ROUTE_TOTAL_M <= this.driveRatio + 1e-6) {
        idx = i;
      } else {
        break;
      }
    }
    return idx;
  }

  /** 导航页「重走」：归零 */
  restartNav(): void {
    this.stopCruise();
    this.navStarted = false;
    this.maneuverIndex = 0;
    this.driveRatio = 0;
    this.bumpEpoch();
  }

  /** 导航页「变道」：按当前上下文切换方案（到站切到站、离站切离站） */
  navChangeLane(): void {
    if (this.navMode === 'departure') {
      this.changeDepartureLane();
    } else {
      this.changeLane();
    }
  }

  /**
   * 已推进的转向序号（底部「继续」按钮驱动）。
   *
   * 【初值 0 = 车在起点】
   * 用户明确要求：① 导航页一进来车标（蓝圈+白环+三角）要压在起点，
   * 点「继续」才沿路线一步步走；② 起点不能「留下一个蓝色小圆圈」。
   * 所以初值设为 0（maneuver[0] 即出发点，distM=0）：车标与起点重合，
   * 且不再画独立起点圆点，开动后也不会在起点留蓝圈。
   * 顶部导航条在 idx=0 显示「出发 / 前方 420 米」，与车在起点相互印证。
   *
   * 【上限不能再写死】初版写死「最多 2 个」，那是因为虚构 Y 字路网只有 3 个转向。
   * 换成真实路网后有 12 个转向，写死 2 会导致点两下就直接「已到达」。
   * 现在上限由 maneuverTotal() 按当前方案的真实转向数算。
   */
  maneuverIndex: number = 0;

  /**
   * 连续行驶进度（0..1）：「继续」一次后车标沿当前路线**平滑滑到终点**，不再一格一格跳。
   * 0 = 起点，1 = 终点。
   * 车标位置、顶部导航条的距离/进度都读它；`maneuverIndex` 作为「附近已过的转向序号」同步跟随，
   * 保证转向条文案与车标位置始终一致。
   */
  driveRatio: number = 0;

  /** 是否正在自动巡航中（防止重复点「开始导航」开多个定时器） */
  cruising: boolean = false;

  /**
   * 导航是否已被**显式启动**（点过底部「开始导航」）。
   *
   * 【为什么单独一个字段，而不复用 cruising】
   * `cruising` 只表示定时器在跑，而定时器一旦建起来就不代表「司机想让它跑」——
   * 页面重建、切页签都会让它继续跑。用户明确要求：
   * 「应该是我点继续之后它才开始导航」（原话是要把那个按钮改成「开始导航」）。
   * 所以把「司机的意图」单独记一个字段：只有 startCruise()（= 按钮 onClick）能置 true，
   * resetDrive()（选路线 / 变道 / 切演示态 / 退出）一律置回 false。
   */
  navStarted: boolean = false;

  /** 巡航定时器句柄（setInterval 返回值），停止时清掉 */
  private cruiseTimer: number = 0;

  /**
   * 地图重绘代号（epoch）。
   *
   * 【为什么需要它 —— 这是一个很难看出来的心坑，本轮真踩了】
   * Canvas 的 onReady 只在组件挂载时触发一次，改 @Prop 不会重画。
   * 所以要用「双节点 if/else 切换」强制重挂（见 RoadNetMap 的注释）。
   * 但这个条件必须**在每次变化时翻转**，否则 ArkUI 认为还是同一个节点，
   * onReady 不重跑，地图就停在旧画面。
   *
   * 我第一版把条件写成 `pickedPathId !== ''` —— 初值就是 'P-2'，恒为 true，
   * 于是两个分支永远走同一支，节点从不重建。
   * 实测症状：卡片高亮、导航条、路段条全切到 P-1 了，**地图还画着 P-2**
   *（截图确认：按钮写「路线二」但地图蓝线没动）。
   *
   * 现在改为：每次状态变化 epoch 自增，条件用 `epoch % 2` 的奇偶。
   * 自增 → 奇偶必翻转 → 节点必重建 → onReady 必重跑。
   * 它只关心「变没变」，不关心「变成了什么」，所以任何状态都覆盖得到。
   */
  routeEpoch: number = 0;

  /** 状态变化时调用：强制地图重画 */
  bumpEpoch(): void {
    this.routeEpoch = this.routeEpoch + 1;
  }

  /**
   * 当前是否**禁止路线选择与导航跳转**。
   *
   * 【用户明确要求（两轮都提过，不能再忘）】
   * ① 数据不可用时：「导航这里是不可以选择路线的吗，要变成灰色，而且不可以点，无法跳转，
   *    而且数据不可用的时候，落客页和离站页也不可以跳转到导航。」
   * ② 应急态时：「应急态导航页面始终保持空态。落客和离站页面要无法跳转导航，
   *    因为他要服从现场指挥，它要停止路线指引，所以点路线框的时候是无法跳转到导航那里的。」
   *
   * 【为什么收敛成一个方法，而不是在四个页面各写一遍 if】
   * 这条规则横跨导航 / 落客 / 离站三页、每页还各有卡片与按钮两个入口。
   * 分散写必然漏一处 —— 而漏掉的那一处正好是评审最容易点出来的
   *（"应急态下还能点进导航，跟'停止路线引导'自相矛盾"）。
   * 集中在 store 一处判定，三页统一读它，改一次全生效。
   *
   * 【为什么应急态也算进来】
   * 应急 = 停止路线引导、服从现场指挥。此时如果还能点路线框跳进导航页，
   * 那就等于「一边说要停止引导，一边还能启动导航」，语义自相矛盾。
   * 所以应急态必须同时：① 导航页锁空态；② 两页禁止跳转。
   *
   * 【注意：降级（degraded）不在此列】
   * 降级 = 没定位但流程不中断（TC-05），路线照常能选、照常能导航。
   * 三档语义必须分清：应急=禁止、降级=放行、不可用=禁止。
   */
  routeLocked(): boolean {
    return this.unavailable || this.emergency;
  }

  /** 当前方案的转向总数（真实路网 12 个，随方案变化；别写死） */
  maneuverTotal(): number {
    const plan: PlanMeta = planOf(arrivalPlans(), this.pickedPathId);
    return buildPlanRoute(plan, false).maneuvers.length;
  }

  private static INSTANCE: DemoStore = new DemoStore();

  static instance(): DemoStore {
    return DemoStore.INSTANCE;
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
    this.resetDrive();
    /**
     * 【应急态：导航页必须回到空态 —— 用户明确要求「应急态导航页面始终保持空态」】
     * 应急 = 停止路线引导、服从现场指挥。此时若还停在导航页，
     * 屏幕上仍有转向条、方案卡、车标在跑 —— 与「已停止引导」自相矛盾。
     * 所以一开应急立刻退回空态（原生空地图 + 顶部红条 + 红色大卡）。
     * 关掉应急时不自动恢复原路线 —— 应急结束要走一次正常的选路流程更安全。
     */
    if (this.emergency) {
      this.navMode = 'empty';
    }
    this.bumpEpoch();
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
    this.resetDrive();
    /**
     * 【数据不可用：同样退回空态】
     * 与应急同一个理由 —— 拿不到路况数据时不该继续显示在导航引导里，
     * 而且用户明确要求「数据不可用的时候导航这里不可以选择路线」。
     * 空态页顶部有灰色「数据不可用」提示条（StateTopBar 的第三个分支），
     * 司机第一眼就知道为什么导航停了。
     */
    if (this.unavailable) {
      this.navMode = 'empty';
    }
    this.bumpEpoch();
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
    this.resetDrive();
    this.bumpEpoch();
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
    this.resetDrive();
    /**
     * 【这一行是本轮补的真修复 —— 漏了它「去色校验」对地图完全无效】
     * setEmergency / setUnavailable / setDegraded 三个 setter 都有 bumpEpoch()，
     * 只有 setColorBlind 漏了。于是：
     *   图例文字是 @Prop 绑定 → 父组件重渲染 → 立刻变成「畅通(灰)」；
     *   而地图是 Canvas，onReady 只在节点挂载时跑一次，epoch 不变 → 节点不重建
     *   → 地图里的路线仍然是彩色。
     * 截图证据：开去色校验后图例已灰、地图仍绿橙。
     * 与「点变道地图不动」是**同一个根因**（epoch 不翻转 → 节点不重建），
     * 所以四个 setter 现在一律 bumpEpoch()。
     */
    this.bumpEpoch();
  }

  /**
   * 按序号选方案（0/1/2），同步 path_id 并把行驶进度归位。
   *
   * 【这一版修掉的真 bug —— 用户投诉「选着线路与方框选择对应错位」的根因】
   * 初版反查 path_id 时用的是 `ROUTES_FIXTURE.alternatives[i - 1]`，
   * 即**契约数组的原始顺序**。而卡片那一侧（RouteOptionRow）已经改成
   * 按路况排序后的顺序了。两边顺序一旦不同，就会出现：
   *   点「路线二」→ pickedIndex=1 → pickedPathId 取到契约里的第 1 个备选，
   *   但卡片高亮的是**排序后**的第 1 个备选 → 两张卡指向不同 path_id。
   * 现在反查统一走 `arrivalPlans()`，与卡片、地图读的是同一份列表。
   */
  pickIndex(idx: number): void {
    // 数据不可用 / 应急态：路线卡置灰不可点，数据层也拦一道
    if (this.routeLocked()) {
      return;
    }
    const plans: PlanMeta[] = arrivalPlans();
    let i: number = idx;
    if (i < 0) {
      i = 0;
    }
    // 上界随方案列表长度走，不写死
    const maxIdx: number = plans.length - 1;
    if (i > maxIdx) {
      i = maxIdx;
    }
    const plan: PlanMeta = planAt(plans, i);
    this.pickedIndex = plan.index;
    this.pickedPathId = plan.pathId;
    this.resetDrive();
    this.bumpEpoch();
  }

  /** 选中某个路线方案（路线一/二/三 卡片点击，按 path_id 反查序号） */
  pickPath(pathId: string): void {
    const plan: PlanMeta = planOf(arrivalPlans(), pathId);
    this.pickIndex(plan.index);
  }

    /**
   * 变道（底部「变道」）：**在三条路线方案间循环切换**。
   * 0 → 1 → 2 → 0 → …
   * 切换后地图路线、转向条文案与图标、路段构成、方案卡高亮四处同时变，
   * 这才叫「变道有效果」。
   *
   * 【不要再做成「无限累加计数」】初版只让计数器++，
   * 结果连点就出现「变道 10」这种无意义数字，看着像坏了。
   * 计数在这里没有任何信息量，有意义的是**当前选的是哪条路线**。
   */
  changeLane(): void {
    this.pickIndex((this.pickedIndex + 1) % arrivalPlans().length);
  }

  /**
   * 离站方案循环切换 —— 离站页底部操作条的「路线一/路线二」按钮。
   *
   * 【为什么必须和 changeLane 分开写】
   * 离站页的方案是**另一套**：departurePlans() = 主选 P-5 + 备选 P-1，
   * 选中状态存在 departurePathId 里，与到站的 pickedPathId 是两个字段。
   * 若图省事复用 changeLane()，点一下会把**到站**方案切了，
   * 而离站地图读的是 departurePathId —— 表现为「按钮动了、地图没动」，
   * 正是本轮修掉过的那类错位。
   */
  changeDepartureLane(): void {
    const plans: PlanMeta[] = departurePlans();
    const cur: PlanMeta = planOf(plans, this.departurePathId);
    const next: PlanMeta = planAt(plans, (cur.index + 1) % plans.length);
    this.pickDeparturePath(next.pathId);
    this.resetDrive();
  }

  /**
   * 切换演示态时只重置**行驶进度**，不动用户选的路线方案。
   *
   * 【踩过的坑】初版这里顺手调了 `pickIndex(0)`，
   * 结果点一下任何演示开关，用户选的方案就被强行拉回路线一——
   * 用户反馈「按退出键就换路线二，这两者不应该有关联」。
   * 选路线和切演示态是**两件互不相干的事**，这里只管行驶进度。
   */
  resetDrive(): void {
    // 切演示态 / 选路线 / 变道 只把行驶进度重置回起点（idx=0 / ratio=0），不动用户选的路线方案
    this.stopCruise();
    // 门闸复位：没点过「开始导航」就回到「待启动」，车不许自己走
    this.navStarted = false;
    this.maneuverIndex = 0;
    this.driveRatio = 0;
  }
}
