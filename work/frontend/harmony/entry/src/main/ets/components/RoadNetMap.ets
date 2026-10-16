import {
  AltRoute, MapCamera, MapMark, MapRenderer, Maneuver, RenderRequest, defaultCamera, RoutePath
} from '../common/MapPort';
import { SelfDrawRenderer } from '../common/SelfDrawRenderer';
import { PlanMeta, arrivalPlans, buildPlanRoute, departurePlans, planOf, planAt, pointAtRatio } from '../common/RoutePlan';
import { REAL_ROAD_NETWORK } from '../common/RealNet';
import { LevelMeta, LEVEL_META_LIST } from '../common/LevelMeta';
import { TEXT_WHITE, BG_MAP_TAG, BG_MAP_TAG_EMERGENCY, BG_MAP_TAG_SUB, TEXT_MAP_FOOT, TEXT_MAP_LABEL, TEXT_MAP_LABEL_SUB } from '../common/Colors';
import { MAP_BACKEND_DESC } from '../common/MapTypes';

/**
 * 地图区组件（导航 App 主视图）。
 *
 * 【组件与地图技术解耦 —— 这是本轮最重要的结构性改动】
 * 组件**只依赖 `MapRenderer` 接口**，不依赖任何具体地图实现。
 * 一期用 `SelfDrawRenderer`（自绘，受地图条款限制）；
 * 后续接手的人接真实可动地图时，只要新写一个实现 `MapRenderer` 的类
 * 并在 `createRenderer()` 里换一行，**本组件及其所有调用页面都不用改**。
 *
 * 【API 24 Canvas 正确用法（踩过 5 轮才对，不要凭直觉改）】
 *   - 构造器用 `Canvas({})`（API 23+ 的对象式参数，不是 new，不是老的 RenderingContextSettings）
 *   - `onReady((dc?: DrawingRenderingContext) => {})` —— dc 可能是 undefined，必须判空
 *   - 2D 上下文取自**静态方法** `CanvasRenderingContext2D.getContext2DFromDrawingContext(dc)`
 *   - 样式是**属性赋值**（ctx.strokeStyle = '#fff'），没有 setStrokeStyle 这类方法
 *   - **`onReady` 只在首次挂载触发一次**，改 @Prop 不会重画 → 用双 Canvas if/else 切换强制重挂
 */

/**
 * 视图宽（画布逻辑宽，后面真地图档也用这个做视口）。
 * 【注意与路网坐标空间区分】这里是视口宽 340vp，
 * 而路网数据的坐标空间是 MAP_NET_W = 680（见 MapTypes），两套东西别混。
 */
const VIEW_W: number = 340;

/** 创建渲染后端 —— 换地图档位只改这一行 */
function createRenderer(): MapRenderer {
  // 后续接真地图：return new AmapRenderer(token);  / return new OsmTileRenderer();
  return new SelfDrawRenderer();
}

/**
 * 把构件上的状态组装成渲染请求（所有后端统一吃这个结构）。
 *
 * 【route 与 altRoutes 的分工 —— 用户投诉「地图路线二三是一样的」的修法】
 * 高德的做法是：选中的方案画高亮粗线，其余方案画灰色细虚线，一眼看出有几条候选。
 * 初版只给一条 route，所以地图上永远只有一条线，既看不出是三个方案，
 * 切方案时也像什么都没发生。现在：
 *   route    = 当前选中的方案（彩色、按等级分段着色）
 *   altRoutes = 其余方案（灰色虚线）
 * 离站页只给两个方案 → altRoutes 里就只有一条，**卡片几个路线就几条，不多画**。
 */
function buildRequest(
  unavailable: boolean,
  colorBlind: boolean,
  mapHeight: number,
  route: RoutePath,
  plans: PlanMeta[],
  picked: PlanMeta,
  isDeparture: boolean,
  blank: boolean,
  selection: boolean,
  driveRatio: number
): RenderRequest {
  const cam: MapCamera = defaultCamera(VIEW_W, mapHeight);
  const marks: MapMark[] = [];
  for (let i = 0; i < route.maneuvers.length; i++) {
    const mv: Maneuver = route.maneuvers[i];
    // 只标关键转向（转向 / 到站），避免 12 个橙点把地图糊住
    const kind: string = mv.type === 'arrive' ? 'pin'
      : (mv.type === 'depart' ? 'start' : 'maneuver');
    marks.push({ text: mv.toRoad, at: mv.at, kind: kind });
  }
  const alts: AltRoute[] = [];
  for (let i = 0; i < plans.length; i++) {
    const p: PlanMeta = plans[i];
    if (p.index === picked.index) {
      continue;
    }
    // 【这里必须传 isDeparture，不能写死 false】
    // 写死 false 时 buildPlanRoute 取的是**到站**备选几何（ROUTE_R2/R3，582,363→108,264），
    // 而离站主选是 D1/D2（108,264→582,363）—— 于是离站地图上会多出一条
    // 方向相反的到站路线，评审必然追问「离站页为什么有条反方向的线」。
    // 同时这会让上面那个 isDeparture 形参变成纯死参数（ArkTS 下也是 lint 噪音）。
    const altRoute: RoutePath = buildPlanRoute(p, isDeparture);
    alts.push({ points: altRoute.points, planIndex: p.index });
  }
  return {
    camera: cam,
    route: route,
    network: REAL_ROAD_NETWORK,
    altRoutes: alts,
    /**
     * 车标位置 —— 由连续进度 driveRatio 在折线上插值得到，沿路线平滑移动。
     *
     * 用户本轮要求：点一下「继续」车就自己沿地图路线滑到终点，不要一格一格跳。
     * 所以位置不再是「整数转向点」，而是 driveRatio(0~1) 在路线折线上的插值点。
     * 引导红线（车标→终点）与「已走灰线」都读这个 car，于是车一动它们一起动。
     * 选路页（落客/离站）不传 driveRatio，默认 0 → 车压在起点，红线从起点连到终点。
     */
    car: pointAtRatio(route.points, driveRatio),
    marks: marks,
    unavailable: unavailable,
    colorBlind: colorBlind,
    blank: blank,
    selection: selection
  };
}

@Component
export struct RoadNetMap {
  /** 当前演示态的两个抽色开关 */
  @Prop @Watch('onRepaintChange') unavailable: boolean = false;
  @Prop @Watch('onRepaintChange') colorBlind: boolean = false;
  /** 要画亮的路线（导航页传 arrival_route，离站页传 departure_route） */
  /** 要画亮的路线（导航页传 arrival_route，离站页传 departure_route）
   * 【评审修复】routeMode 也要挂 @Watch：导航页 arrival↔departure 切换时不能只等
   * repaintEpoch 兜底，否则又回到「切了但地图慢一拍」 */
  @Prop @Watch('onRepaintChange') routeMode: string = 'arrival';
  /** 图幅高度（vp）；三页统一 470vp —— 大于首屏可视高度，所以一进来整屏是地图 */
  /** 图幅高度（vp）；三页统一 470vp
   * 【评审修复】同 routeMode：高度变化时同步重画，保证画布尺寸落定后再画 */
  @Prop @Watch('onRepaintChange') mapHeight: number = 470;
  /** 落客点标识（取自 fixture，不硬编码） */
  /** 落客点标识（取自 fixture，不硬编码）
   * 【评审修复】同 routeMode：离站导航「离站出口」↔「DROP-03」切换时即时重画 */
  @Prop @Watch('onRepaintChange') dropLabel: string = 'DROP-03';
  /** 当前方案序号（0 = 路线一推荐, 1 = 路线二, 2 = 路线三），决定画哪条路线臂 */
  @Prop @Watch('onRepaintChange') pickedIndex: number = 0;
  /**
   * 当前选中的 path_id（'P-2' / 'P-1' / 'P-3'）。
   * 【为什么加这个入参】卡片点选写进 store 的是 path_id，不是序号。
   * 地图只按序号对齐就会出现「卡片亮路线二、地图画的是路线三」这种错位，
   * 所以地图也按 path_id 对齐，序号仅作兜底。
   */
  @Prop @Watch('onRepaintChange') pickedPathId: string = '';
  /**
   * 重绘代号（来自 store.routeEpoch，每次状态变化自增）。
   *
   * 【铁律：Canvas 必须单节点】本组件**曾经**用 `epoch % 2` 双 Canvas if/else 翻转
   * 强制节点重建来触发重画，实跑代价（2026-10-15/16 两轮用户截图 + 视频举证）：
   *   ① 旧 Canvas 节点销毁不及时 → 两幅地图叠在同一位置（用户：「不要这么多地图叠加」）；
   *   ② 新节点 onReady 时布局未落定，dc.size 只有约半个宽 → 左上角叠出一张缩小版路线图；
   *   ③ 巡航每帧 bumpEpoch → 每帧销毁重建节点 → 卡顿、闪屏。
   * 现在改为：**单 Canvas + 所有影响绘制的 prop 挂 @Watch → repaintNow()**
   * （缓存 dc + invalidate，节点不重建）。epoch 只回答「变没变」，不回答「变成了什么」，
   * 所以仍保留作兜底触发器。
   */
  @Prop @Watch('onRepaintChange') repaintEpoch: number = 0;

  /**
   * 【为什么没有 maneuverIndex 这个 prop —— 留着会误导接手人】
   * 初版车标按「整数转向序号」定位，所以三页都要把 store.maneuverIndex 传进来。
   * 但改成 driveRatio 沿折线插值后，repaint() 根本不再读它 ——
   * prop 留着会让评审以为「地图仍在按转向序号定位车标」，
   * 而实际上 @Watch('onDriveRatioChange') 才是唯一驱动。
   * 落客/离站页传它也只是为了「车标钉在起点」，那本来就是 driveRatio=0 的语义。
   */

  /**
   * 连续行驶进度（0..1）：车标沿路线平滑滑到终点的依据。
   *
   * 【为什么加这个 @Prop】
   * 原来车标只在整数转向点之间跳（按 maneuverIndex 定位），
   * 自动巡航要求车标连续移动，所以位置改由 driveRatio 在折线��插值得到。
   * 地图组件仍不持有 store（保持「渲染器不知道业务状态」分界），由页面把
   * store.driveRatio 传进来；余震/离站选路页不传时默认 0（车在起点）。
   *
   * 【@Watch 的作用 —— 用户投诉「车卡住了，到最后跳到终点去」的修法】
   * 巡航每 40ms 改一次这个值。若只等 ArkUI 自己 diff 重画，高频下 diff 跟不上，
   * 画面会停在原地（看着像卡住），直到最后一帧才「跳」到终点。
   *挂 @Watch 后每次变化立刻走 repaintNow()：用缓存的 dc 直接重画 + invalidate，
   * 不销毁 Canvas 节点，逐帧跟得上车标。
   */
  @Prop @Watch('onDriveRatioChange') driveRatio: number = 0;

  /** driveRatio 变化 → 立刻重画（高频路径，见上面注释） */
  private onDriveRatioChange(): void {
    this.repaintNow();
  }

  /**
   * 就地重画：复用已挂载 Canvas 的绘制上下文，不重建节点。
   *
   * 【为什么必须有它】双Canvas if/else 翻转（见 build 里的说明）对低频状态切换有效，
   * 但巡航是每 40ms 一次，节点销毁重建跟不上 → 「卡住→跳终点」。
   * 这里走 SDK 的 `dc.invalidate()`（since 12，正规重画方式），高频也跟得上。
   */
  private repaintNow(): void {
    if (this.dc === undefined) {
      return;
    }
    this.repaint(this.dc);
    this.dc.invalidate();
  }

  /** 空白原生地图：true 时只画底图，不画路线/车标/标记（导航页未选路线初态） */
  @Prop @Watch('onRepaintChange') blank: boolean = false;

  /** 选路页红线强调：true 时红线描边加宽（落客/离站选路地图） */
  /** 选路页红线强调：true 时红线描边加宽（落客/离站选路地图）
   * 【评审修复】一并收口：所有影响绘制的 prop 全部挂 @Watch，不留隐式兜底依赖 */
  @Prop @Watch('onRepaintChange') selection: boolean = false;

  /**
   * 【停止引导闸门 —— 应急态 / 数据不可用时必须为 true】
   *
   * 【为什么需要这个 prop】
   * 应急态的语义是「停止路线引导，改为请服从现场指挥」，可初版三页里
   * 落客页与离站页的地图仍照常画彩色路线 + 红色引导线 + 车标 + 终点蓝点，
   * 只有导航页因为 navMode 被置空才走了 blank 分支。
   * 于是评审会问：「说好了停止引导，为什么落客页地图上还在推荐路线？」
   *
   * 修法选在组件内合成 blank（而不是让三页各写一遍 `blank: emergency || unavailable`）：
   * 一处生效、三个页面都覆盖，且将来新增调用方不会漏。
   * 注意**不含 degraded** —— 降级是「无定位但流程不中断」，路线必须继续显示。
   */
  @Prop @Watch('onRepaintChange') stopGuidance: boolean = false;

  /**
   * 【切到本页时强制重画 —— 修「演示态切换慢一拍」】
   * Tabs 会缓存非激活页签；隐藏页的 @Watch(repaintEpoch) 重画可能被 ArkUI 推迟，
   * 于是切到该页时画布先显示上一帧（旧演示态），要等下一次状态变化才刷新 → 「慢一拍」。
   * 这里把「本页是否当前可见」作为 prop 传进来：切到本页时 active 由 false→true，
   * 立刻用缓存 dc + invalidate 就地重画一次（单 Canvas、不重建节点、不 bumpEpoch），
   * 直接画当前最新状态，切换即丝滑。绝不动双 Canvas / 重建节点（否则会回到多地图叠加）。
   */
  @Prop @Watch('onActiveChange') active: boolean = true;

  /** 低频状态变化（开关 / 变道 / epoch）→ 就地重画，与 driveRatio 同一条路（不重建节点） */
  private onRepaintChange(): void {
    this.repaintNow();
  }

  /** 本页变为可见时（切 Tab 切回来）→ 立刻重画当前最新演示态，消除「慢一拍」 */
  private onActiveChange(): void {
    if (this.active) {
      this.repaintNow();
    }
  }

  private render(): MapRenderer {
    return createRenderer();
  }

  /**
   * 当前挂载 Canvas 的绘制上下文（onReady 时缓存下来）。
   *
   * 【为什么加它 —— 用户投诉「车卡住了，到最后跳到终点去」的根因】
   * 原先靠「双Canvas if/else 翻转重建节点」来触发重画。这招对**低频**状态切换
   * （点变道、开去色校验）有效，但自动巡航是**每 40ms 一次**的高频重画 ——
   * 节点销毁再重建根本跟不上，画面停在原地（看着像卡住），
   * 直到最后 driveRatio 到 1 那一帧节点终于重建成功 →「一下子跳到终点」。
   *
   * SDK 里有正规解法：`DrawingRenderingContext.invalidate()`（since 12），
   * 它会让组件重新渲染，**不需要销毁重建节点**。
   * 所以 onReady 把 dc 存下来，之后每次重画直接拿它 invalidate 一次即可，
   * 双 Canvas 翻转保留作兜底（onReady 首次挂载那条路仍走它）。
   */
  private dc: DrawingRenderingContext | undefined = undefined;

  /**
   * 渲染后端实例（缓存复用，不是每帧新建）。
   *
   * 【为什么必须缓存 —— 一个真实的性能与生命周期问题】
   * 初版 `repaint()` 里直接 `const r = this.render()`，而 `render()` 每次
   * `new SelfDrawRenderer()` + `r.setup()`。巡航是每 40ms 一帧，
   * 于是每帧都新建一个渲染器对象并重复 setup，而 `dispose()` 从没被调用过
   * —— 对象一轮接一轮被丢弃，真接了地图 SDK（要持原生句柄）必然泄漏。
   * 现改成「首次创建后复用」，组件消失时统一 dispose。
   */
  private renderer: MapRenderer | undefined = undefined;

  aboutToDisappear(): void {
    // 页面在 Tabs 里被销毁时释放后端，避免真地图档位的原生资源泄漏
    if (this.renderer !== undefined) {
      this.renderer.dispose();
      this.renderer = undefined;
    }
    this.dc = undefined;
  }

  private repaint(dc?: DrawingRenderingContext): void {
    if (dc === undefined) {
      return;
    }
    this.dc = dc;
    const ctx: CanvasRenderingContext2D = CanvasRenderingContext2D.getContext2DFromDrawingContext(dc);
    if (ctx === null) {
      return;
    }
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'center';

    // 后端初始化（真地图档在这里建SDK 对象）—— 实例复用，只在首次创建时 setup
    if (this.renderer === undefined) {
      this.renderer = this.render();
      this.renderer.setup();
    }
    const r: MapRenderer = this.renderer;
    if (r instanceof SelfDrawRenderer) {
      r.attach(ctx);
      /**
       * 【把画布真实尺寸喂给渲染器 —— 修「地图偏右下、左上留大片空白」】
       * 组件上写的是 `.width('100%')`，实际画布宽 ≈ 屏幕宽（360vp+），
       * 而渲染器之前拿的是写死的 VIEW_W=340 当画布宽 —— 缩放比与居中偏移全算错。
       * `dc.size`（since 12）能量到真实宽高，这里读一次交给渲染器。
       * 读不到（宽或高为 0）就不喂，渲染器会退回标称值，不会算成 NaN。
       */
      const sz = dc.size;
      if (sz !== undefined && sz.width > 0 && sz.height > 0) {
        r.setCanvasSize(sz.width, sz.height);
      }
    }

    /**
     * 【路线从哪来 —— 真实路网 + 契约路段】
     * 初版这里画的是虚构的「Y 字」示意路网，三条臂靠手写坐标拼出来，
     * 于是：① 路线二三画的是同一条（用户投诉「路线二三是一样的」）
     *       ② 着色跟契约路段等级对不上（用户投诉「不要乱标」）
     * 现在几何来自真实路网数据（RealNet），着色来自契约等级（RoutePlan），
     * 两者由 buildPlanRoute 一处组装，页面不参与拼装。
     */
    const isDep: boolean = this.routeMode === 'departure';
    const plans: PlanMeta[] = isDep ? departurePlans() : arrivalPlans();
    //优先按 path_id 对齐（与卡片同源），path_id 为空才回落到序号
    const picked: PlanMeta = this.pickedPathId === ''
      ? planAt(plans, this.pickedIndex)
      : planOf(plans, this.pickedPathId);
    const route: RoutePath = buildPlanRoute(picked, isDep);
    const req: RenderRequest =
      buildRequest(this.unavailable, this.colorBlind, this.mapHeight, route, plans, picked,
        isDep, this.blank || this.stopGuidance, this.selection, this.driveRatio);
    r.draw(req);
  }

  build() {
    Column() {
      Stack({ alignContent: Alignment.TopStart }) {
        /**
       * 【铁律：Canvas 必须单节点，绝不允许 if/else 翻转 / 双分支（2026-10-15/16 两轮实跑教训）】
       * 曾经用 `repaintEpoch % 2` 双 Canvas 翻转「强制节点重建」来触发重画，实跑三大代价：
       *   ① 旧节点销毁不及时 → 两幅地图叠在同一位置（用户：「不要这么多地图叠加」）；
       *   ② 新节点 onReady 时布局未落定，dc.size 只有约半个宽 → 左上角叠出缩小版路线图；
       *   ③ 巡航每帧翻转 → 每帧销毁重建 → 卡顿、闪屏。
       * 现在：单 Canvas。首画靠 onReady；之后所有重画走 @Watch → repaintNow()
       * （缓存 dc + invalidate），节点从不重建。
       */
        Canvas({})
          .width('100%')
          .height(this.mapHeight)
          .onReady((dc?: DrawingRenderingContext) => {
            this.repaint(dc);
          })
          .onAreaChange((_o: Area, _n: Area) => {
            // 布局落定（首次挂载 onReady 可能早于布局完成）：就地重画一次，保证尺寸正确
            this.repaintNow();
          })

        // 左上角：落客点徽标
        // 【y 从 8 挪到 30】顶部中间加了「地图档位说明」，同一行会重叠，
        // 徽标（左）/ 档位说明（中）统一排在 y=30 这一行；图例（右）下移到 y=50，
        // 放进「档位说明」与路线图之间的空档，避免压住路线（2026-10-16 13:14 用户指令）。
        // 空白原生地图（blank）不画任何标注，只留底图。
        if (!this.blank) {
        Row({ space: 4 }) {
          Text('●')
            .fontSize(9)
            .fontColor(TEXT_WHITE)
          Text(this.dropLabel)
            .fontSize(10)
            .fontWeight(FontWeight.Medium)
            .fontColor(TEXT_WHITE)
        }
        .padding({ top: 4, bottom: 4, left: 7, right: 7 })
        .backgroundColor(BG_MAP_TAG_EMERGENCY)
        .borderRadius(5)
        .margin({ top: 30, left: 8 })

        // 右上角：四级图例（三重编码 §11.3）
        // 【为什么用 .position 而不是 .align】Stack 的 alignContent 会覆盖子组件的 .align()，
        // 实跑验证两个角标会叠在左上；.position 是绝对定位，不受 Stack 对齐影响。
        Column({ space: 2 }) {
          Text('路况图例')
            .fontSize(9)
            .fontWeight(FontWeight.Medium)
            .fontColor(TEXT_MAP_LABEL)
          ForEach(LEVEL_META_LIST, (m: LevelMeta) => {
            Row({ space: 4 }) {
              Text(m.glyph)
                .fontSize(10)
                .fontColor(this.colorBlind ? '#5F5E5A' : m.textColor)
              Text(this.colorBlind ? `${m.name}(灰)` : m.name)
                .fontSize(9)
                .fontColor(TEXT_MAP_LABEL_SUB)
            }
          }, (m: LevelMeta) => `${m.name}_${this.unavailable}_${this.colorBlind}`)
        }
        .padding(6)
        .backgroundColor(BG_MAP_TAG)
        .borderRadius(6)
        // 用户 13:14 指令：图例紧贴「自绘OSM 路网图」这行字下方一点点，
        // 放进它和路线图之间的空档，不要压到路线（y:150 实测压到路线，故回收到 y:50）
        .position({ x: 246, y: 50 })

        // 地图档位说明（评审会问「这地图哪来的」，写清在图上）
        // 【为什么放顶部居中而不是底部】
        // 地图现在是 470vp（大于首屏视口，见 RecommendPage 的说明），
        // 贴底的位置落在**首屏看不到的地方**、还被底部操作条压住 —— 实跑验证被遮了一截。
        // 改放顶部居中：首屏一定看得见，且不与路线重叠。
        Row({ space: 4 }) {
          Text('▨')
            .fontSize(8)
            .fontColor(TEXT_MAP_FOOT)
          Text(MAP_BACKEND_DESC)
            .fontSize(8)
            .fontColor(TEXT_MAP_FOOT)
        }
        .padding({ top: 2, bottom: 2, left: 5, right: 5 })
        .backgroundColor(BG_MAP_TAG_SUB)
        .borderRadius(4)
        .position({ x: 158, y: 30 })
        }
      }
      .width('100%')
    }
  }
}
