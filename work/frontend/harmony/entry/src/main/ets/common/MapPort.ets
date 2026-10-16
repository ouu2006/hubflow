import { SegmentLevel } from './MapTypes';
/** 地理点：自绘档当画布像素，真地图档当经纬度 */
export interface GeoPoint {
    x: number;
    y: number;
}
/** 相机：视图中心 + 缩放 + 旋转。真地图档可忽略旋转（多数 SDK 才有） */
export interface MapCamera {
    /** 视口宽（vp / px） */
    viewWidth: number;
    /** 视口高 */
    viewHeight: number;
    /** 相机中心（自绘档 = 画布坐标） */
    centerX: number;
    centerY: number;
    /** 缩放倍率，1 = 原始比例 */
    zoom: number;
    /** 屏幕旋转角度（度），真地图档可忽略 */
    rotation: number;
}
/** 路线上的一次转向（Y 字口的「右转/左转/直行继续」就靠它驱动转向条） */
export interface Maneuver {
    /** 转向类型：straight / left / right / fork_left / fork_right / arrive / depart */
    type: string;
    /** 转向发生的路网节点坐标 */
    at: GeoPoint;
    /** 转向前的道路名 */
    fromRoad: string;
    /** 转向后的道路名 */
    toRoad: string;
    /** 距离该转向还有多少米（导航条上「前方 300 米右转」用） */
    distM: number;
    /** 该转向对应的路段id（用于按等级着色 + 演示态联动） */
    segmentId: string;
}
/**
 * 路线：一串带等级的折线 + 转向序列。
 * 这是地图后端唯一需要知道的东西 —— 换地图不影响这个结构。
 */
export interface RoutePath {
    /** 路线总点数（自绘折线用） */
    points: GeoPoint[];
    /** 每个点所属路段id（与 points 等长） */
    pointSegments: string[];
    /** 该路段的等级（1~4，取不到为 -1） */
    levels: SegmentLevel[];
    /** 转向序列（导航条据此渲染「前方 N 米右转」） */
    maneuvers: Maneuver[];
    /** 起终点 */
    start: GeoPoint;
    end: GeoPoint;
    /** 起终点名称（导航条底部用） */
    startName: string;
    endName: string;
}
/** 地图标注（地名等）。必须具名 —— ArkTS 不允许对象字面量当类型 */
export interface MapLabel {
    text: string;
    at: GeoPoint;
}
/** 地图上的点位标记 */
export interface MapMark {
    text: string;
    at: GeoPoint;
    /** start / maneuver / pin —— 决定渲染后端画什么形状 */
    kind: string;
}
/** 路网（自绘档用；真地图档可忽略这个参数，自己有底图） */
export interface RoadNetwork {
    /** 次要路（白色细线） */
    minorRoads: GeoPoint[][];
    /** 主干道（淡黄加描边，高德观感） */
    arterys: GeoPoint[][];
    /** 街区地块（多边形四角） */
    blocks: GeoPoint[][];
    /** 绿地块 */
    greens: GeoPoint[][];
    /** 水域多边形 */
    waters: GeoPoint[][];
    /** 地名标注 */
    labels: MapLabel[];
}
/** 地图上的一条备选路线（未被选中的方案） */
export interface AltRoute {
    /** 路线折线 */
    points: GeoPoint[];
    /** 该方案序号（0/1/2），用于日志与「当前选中」对照 */
    planIndex: number;
}
/** 渲染参数：由组件每一帧/每次状态变化组装好交给后端 */
export interface RenderRequest {
    camera: MapCamera;
    route: RoutePath;
    network: RoadNetwork;
    /**
     * 其它候选方案的几何（未选中的）。
     * 【为什么要单独一个字段而不是都塞进 route】
     * 高德导航的观感是：**选中方案高亮彩色实线，其余方案灰色细虚线**。
     * 如果只给一条 route，后端就画不出「另外两条备选」，
     * 用户看到的地图就只有一条线，看不出这是个多方案对比。
     * 真地图档同样适用（画成两条灰色 polyline）。
     */
    altRoutes: AltRoute[];
    /** 车标位置（自绘档 = 画布坐标） */
    car: GeoPoint;
    /** 地图上要显示的标注（落客点、转向点等） */
    marks: MapMark[];
    /** 抽色态：数据不可用 / 去色校验（后端内需据此抽色） */
    unavailable: boolean;
    colorBlind: boolean;
    /**
     * 空白原生地图：true 时只画底图（路网），不画路线 / 车标 / 标记 / 终点。
     * 导航页「还没选路线」的初态用：一个没有标任何东西的原生地图。
     */
    blank?: boolean;
    /**
     * 选路页红线强调：true 时（落客/离站选路地图）把选中路线红线描边加宽，
     * 让「连接司机与终点的红线」在选路页也清晰可见（常规导航都有的观感）。
     */
    selection?: boolean;
}
/**
 * 地图渲染后端（Map Renderer Port）。
 *
 * 实现者只需实现这 5 个方法，页面组件完全不感知具体地图技术。
 */
export interface MapRenderer {
    /** 唯一标识，日志与「当前地图档位」展示用 */
    readonly name: string;
    /** 初始化（真地图档在这里创建 SDK 地图对象；自绘档留空） */
    setup(): void;
    /** 渲染一帧。自绘档 = 往 Canvas 画；真地图档 = 更新 SDK 图层 */
    draw(req: RenderRequest): void;
    /** 把相机对准某个点（导航时跟随车标、点击选路段都用） */
    focusOn(target: GeoPoint, zoom?: number): void;
    /** 命中测试：屏幕坐标 → 该点的路段id（点击路网选路段 / 降级态手动选路用） */
    hitTest(x: number, y: number): string;
    /** 释放资源（真地图档销毁 SDK 对象；切页时调用避免泄漏） */
    dispose(): void;
}
/** 相机默认参数（自绘档；视口 340 x mapHeight） */
export function defaultCamera(viewWidth: number, viewHeight: number): MapCamera {
    return {
        viewWidth: viewWidth,
        viewHeight: viewHeight,
        centerX: viewWidth / 2,
        centerY: viewHeight / 2,
        zoom: 1,
        rotation: 0
    };
}
