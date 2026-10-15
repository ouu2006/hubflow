import { GeoPoint, MapCamera, MapRenderer, RenderRequest } from './MapPort';
import { MAP_NET_W, MAP_NET_H } from './MapTypes';
import { SegmentLevel } from './MapTypes';
import { LEVEL_META_LIST } from './LevelMeta';
/**
 * 路网数据的**固定坐标空间**。
 * RealNet 里所有图元的 x/y 都落在这个范围内，
 * 渲染时按画布尺寸等比缩放（见 draw 里的 scale 计算），
 * 这样页面给多高的画布都不会裁掉地图。
 */
const NET_W: number = MAP_NET_W;
const NET_H: number = MAP_NET_H;
/**
 * 自绘图渲染后端（MapRenderer 的默认实现）。
 *
 * 【这个类的意义】
 * 它只是 `MapRenderer` 接口的**一个实现**，页面组件不依赖它本身、只依赖接口。
 * 后续接手的人要接真地图（高德/百度/OSM瓦片），**另写一个类实现同一接口**即可，
 * 页面一行都不用改。这就是「可插拔」的落地方式。
 *
 * 【配色集中在这里】
 * 后面的实现若要换成真地图，直接用自己的图层样式，本文件不用碰。
 */
/** 底色与地物 */
const C_BG: string = '#EAF2E0'; // 地图底（淡绿）
const C_BLOCK_FILL: string = '#E8EDF0'; // 街区
const C_BLOCK_STROKE: string = '#D5DDE2';
const C_MINOR: string = '#FFFFFF'; // 次要路
const C_ARTERY: string = '#FFF6D8'; // 主干道（高德观感）
const C_ARTERY_EDGE: string = '#E3C97A';
const C_GREEN: string = '#C7E3B0';
const C_WATER: string = '#C5DCF0';
const C_LABEL: string = '#5A6B72';
/** 路线 */
const C_ROUTE: string = '#1E88E5'; // 导航蓝
const C_ROUTE_EDGE: string = '#0D5FB4';
const C_CAR: string = '#1E88E5';
const C_PIN: string = '#E53935'; // 落客点红
const C_MANEUVER: string = '#FF8A00'; // 转向点橙（重点转向标）
const C_ALT: string = '#8C9AA3'; // 备选方案（灰，虚线）

/** 一次绘制的内容包围盒（数据坐标系） */
interface FitBox {
    minX: number;
    minY: number;
    maxX: number;
    maxY: number;
}

/** 把一组折线并进包围盒 */
function growLine(b: FitBox, line: GeoPoint[]): void {
    for (let i = 0; i < line.length; i++) {
        if (line[i].x < b.minX) {
            b.minX = line[i].x;
        }
        if (line[i].x > b.maxX) {
            b.maxX = line[i].x;
        }
        if (line[i].y < b.minY) {
            b.minY = line[i].y;
        }
        if (line[i].y > b.maxY) {
            b.maxY = line[i].y;
        }
    }
}

/**
 * 算出这次绘制**真正会画出来的内容**的包围盒。
 *
 * 【为什么不能用固定的 NET_W/NET_H 居中 —— 用户投诉「左右留空不对称」】
 * 数据坐标空间是 680×880，但实测路网内容的真实范围是 x ∈ [−533, 725]，
 * 内容中心在 x≈96，离坐标空间中心(340) 差了 244。
 * 按坐标空间居中 = 按"看不见的虚拟框"居中，内容自然偏在一侧。
 * 所以必须扫真实图元算出盒子，再按盒子居中。
 *
 * 【为什么要把路网各层都算进去】
 * 只算路线几何的话，空白处会被路网填满而内容偏移；
 * 把主干道/次干道/绿地/水域都算上，取景框才与司机眼睛看到的边界一致。
 *
 * 【留白余量】盒子外扩 PAD，避免路线正好压在画布边缘上。
 */
const FIT_PAD: number = 24;

function fitBoxOf(req: RenderRequest): FitBox {
    let b: FitBox = {
        minX: Number.MAX_SAFE_INTEGER, minY: Number.MAX_SAFE_INTEGER,
        maxX: -Number.MAX_SAFE_INTEGER, maxY: -Number.MAX_SAFE_INTEGER
    };
    /**
     * 【路线优先 —— 用户投诉「路线太小」】
     * 路线几何只有 x[98,582] y[264,616]（宽 484、高 352），
     * 而主干道是 x[−533,725] y[−547,879]（宽 1258、高 1426），大了约 3 倍。
     * 若按主干道定框来保证"整幅路网完整"，路线就只占画面的很小一块 ——
     * 实测截图正是如此：路网铺满整屏，但蓝色路线细得几乎看不清。
     *
     * 导航 App 的取景逻辑本来就是**跟随路线**：把司机要走的那条路放到画面主体，
     * 周围留出街干作参照。先按路线+标记定框，再向外扩一定余量把路网带上，
     * 最后整框等比缩放居中 —— 路线够大、四周也不失衡。
     */
    const rb: FitBox = {
        minX: Number.MAX_SAFE_INTEGER, minY: Number.MAX_SAFE_INTEGER,
        maxX: -Number.MAX_SAFE_INTEGER, maxY: -Number.MAX_SAFE_INTEGER
    };
    growLine(rb, req.route.points);
    for (let i = 0; i < req.altRoutes.length; i++) {
        growLine(rb, req.altRoutes[i].points);
    }
    for (let i = 0; i < req.marks.length; i++) {
        growLine(rb, [req.marks[i].at]);
    }
    growLine(rb, [req.car]);
    if (rb.minX <= rb.maxX) {
        b = rb;
    } else {
        /**
         * 【空态（未选路线）：没有路线可跟随，退回按主干道定框】
         * 空态地图画的是「原生空图」，没有主角，参照系就是街干本身。
         * 若这时还按空盒子算，会退化成无穷大（NaN）导致整幅图不渲染。
         */
        for (let i = 0; i < req.network.arterys.length; i++) {
            growLine(b, req.network.arterys[i]);
        }
        b.minX -= FIT_PAD;
        b.minY -= FIT_PAD;
        b.maxX += FIT_PAD;
        b.maxY += FIT_PAD;
        return b;
    }
    /**
     * 【余量取路网的固定一半再上下放宽】
     * 左右外扩 ROUTE_PAD_X：保证路线两侧能看到相邻街干（判断该往哪转）。
     * 上下外扩 ROUTE_PAD_Y 比左右更多：路线本身是竖向走的（高 352 > 宽 484 但接近方形），
     * 而画布是 340×470 的竖长条 —— 若上下不额外放宽，路线会被压到很扁很小。
     */
    b.minX -= ROUTE_PAD_X;
    b.maxX += ROUTE_PAD_X;
    b.minY -= ROUTE_PAD_Y;
    b.maxY += ROUTE_PAD_Y;
    return b;
}

/** 路线取景的外扩余量（数据坐标单位）—— 左右少、上下多，适配竖长画布 */
const ROUTE_PAD_X: number = 110;
const ROUTE_PAD_Y: number = 190;

const C_CLOSED: string = '#5F5E5A'; // 抽色后的统一灰
/** 路线主色（高德式「红线」：整条路线先画一道粗红线作描边，等级色叠在上面、两侧露红线） */
const C_ROUTE_CASE: string = '#E53935';
/** 已走过路段（车标之前）：灰，形成「剩余红线 / 已过灰线」的导航进度观感 */
const C_TRAVELED: string = '#9AA7B0';
const C_TRAVELED_EDGE: string = '#C2CBD2';
/**
 * 起点不再单独画圆点 —— 车标（蓝圈+白环+三角）初始就压在起点上，
 * 一旦开动会在起点「留下一个蓝色小圆圈」（用户明确要求不要），
 * 所以这里不画独立起点标记，起点由静止态的车标本身表示。
 * 终点圆点（drawEndDot）保留：用户要求三页统一有落客/终点标记。
 */

/** 终点圆点 —— 起点同款 + 深蓝内芯（用户要求三页统一） */
function drawEndDot(ctx: CanvasRenderingContext2D,
                   end: GeoPoint,
                   u: boolean,
                   cb: boolean): void {
    ctx.fillStyle = degrade(C_ROUTE, u, cb);
    ctx.strokeStyle = '#FFFFFF';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(end.x, end.y, 7.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = degrade(C_ROUTE_EDGE, u, cb);
    ctx.beginPath();
    ctx.arc(end.x, end.y, 2.6, 0, Math.PI * 2);
    ctx.fill();
}

/**
 * 车标 —— 蓝圈 + 白环 + 白色方向三角（高德/百度式当前位置箭头）。
 *
 * 【用户原话】「那个代表司机本人的圆圈加三角……圆圈外它外面白色那个小圆圈」
 * 所以标记必须是「蓝圆 + 白色外环 + 三角」，不是当初那个孤零零的三角。
 *
 * 【方向怎么算】
 * 把车标投影到折线上最近的线段，取该段方向、三角指向前进方向。
 * 比「找第一个更远的点」稳：相邻点密集时旧算法方向会抖；
 * 投影到最近线段后，弯道处方向随路线平滑变化。
 */
function drawCar(ctx: CanvasRenderingContext2D,
                car: GeoPoint,
                pts: GeoPoint[],
                u: boolean,
                cb: boolean): void {
    let ang: number = -Math.PI / 2; // 默认朝上（北）
    const n: number = pts.length;
    if (n >= 2) {
        // 投影到最近线段，取该段方向
        let bestI: number = 0;
        let bestD: number = Infinity;
        for (let i = 0; i < n - 1; i++) {
            const ax: number = pts[i].x;
            const ay: number = pts[i].y;
            const bx: number = pts[i + 1].x;
            const by: number = pts[i + 1].y;
            const dx: number = bx - ax;
            const dy: number = by - ay;
            const len2: number = dx * dx + dy * dy;
            let t: number = len2 > 0 ? ((car.x - ax) * dx + (car.y - ay) * dy) / len2 : 0;
            if (t < 0) {
                t = 0;
            }
            if (t > 1) {
                t = 1;
            }
            const px: number = ax + dx * t;
            const py: number = ay + dy * t;
            const d: number = (px - car.x) * (px - car.x) + (py - car.y) * (py - car.y);
            if (d < bestD) {
                bestD = d;
                bestI = i;
            }
        }
        const dx: number = pts[bestI + 1].x - pts[bestI].x;
        const dy: number = pts[bestI + 1].y - pts[bestI].y;
        ang = Math.atan2(dy, dx) + Math.PI / 2;
    }
    ctx.save();
    ctx.translate(car.x, car.y);
    ctx.rotate(ang);
    // 白色外环
    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.arc(0, 0, 13, 0, Math.PI * 2);
    ctx.fill();
    // 蓝色圆（司机本人）
    ctx.fillStyle = degrade(C_CAR, u, cb);
    ctx.beginPath();
    ctx.arc(0, 0, 10, 0, Math.PI * 2);
    ctx.fill();
    // 白色方向三角（指向前方）
    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.moveTo(0, -6);
    ctx.lineTo(5.5, 6);
    ctx.lineTo(-5.5, 6);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
}

/**
 * 已走过路段：从路线起点到车标当前位置的一段折线。
 * 车标在折线上（由 pointAtRatio 算出），投影到最近线段后插入车标点。
 * 返回空/单点时调用方不画灰（车在起点时退化为零长）。
 */
function traveledPolyline(pts: GeoPoint[], car: GeoPoint): GeoPoint[] {
    if (pts.length < 2) {
        return [];
    }
    let bestI: number = 0;
    let bestT: number = 0;
    let bestD: number = Infinity;
    for (let i = 0; i < pts.length - 1; i++) {
        const ax: number = pts[i].x;
        const ay: number = pts[i].y;
        const bx: number = pts[i + 1].x;
        const by: number = pts[i + 1].y;
        const dx: number = bx - ax;
        const dy: number = by - ay;
        const len2: number = dx * dx + dy * dy;
        let t: number = len2 > 0 ? ((car.x - ax) * dx + (car.y - ay) * dy) / len2 : 0;
        if (t < 0) {
            t = 0;
        }
        if (t > 1) {
            t = 1;
        }
        const px: number = ax + dx * t;
        const py: number = ay + dy * t;
        const d: number = (px - car.x) * (px - car.x) + (py - car.y) * (py - car.y);
        if (d < bestD) {
            bestD = d;
            bestI = i;
            bestT = t;
        }
    }
    const out: GeoPoint[] = [];
    for (let i = 0; i <= bestI; i++) {
        out.push(pts[i]);
    }
    const ax: number = pts[bestI].x;
    const ay: number = pts[bestI].y;
    const bx: number = pts[bestI + 1].x;
    const by: number = pts[bestI + 1].y;
    out.push({ x: ax + (bx - ax) * bestT, y: ay + (by - ay) * bestT });
    return out;
}

/** 抽色映射：颜色 → 抽色后的样子 */
function degrade(c: string, unavailable: boolean, colorBlind: boolean): string {
    if (!unavailable && !colorBlind)
        return c;
    if (c === C_BG)
        return '#EFEFEF';
    if (c === C_GREEN)
        return '#E4E9E4';
    if (c === C_WATER)
        return '#E4EAF0';
    if (c === C_BLOCK_FILL)
        return '#F1F3F4';
    if (c === C_BLOCK_STROKE)
        return '#E2E6E9';
    if (c === C_MINOR)
        return '#F7F7F7';
    if (c === C_ARTERY)
        return '#F5F0DC';
    if (c === C_ARTERY_EDGE)
        return '#E0DCBC';
    if (c === C_ROUTE || c === C_ROUTE_EDGE)
        return C_CLOSED;
    if (c === C_MANEUVER)
        return C_CLOSED;
    if (c === C_ALT)
        return '#A6A6A3';
    if (c === C_PIN)
        return C_CLOSED;
    // 四级路色与其文字色一并抽灰
    for (let i = 0; i < LEVEL_META_LIST.length; i++) {
        if (c === LEVEL_META_LIST[i].color || c === LEVEL_META_LIST[i].textColor)
            return C_CLOSED;
    }
    // 【兜底为什么保留原色而不是抽灰】
    // 能走到这里的都是**非语义色**（纯装饰：白边、阴影、网格线），
    // 它们承载不了任何路况信息，抽灰反而会让画面变得脏。
    // 所有承载语义的颜色（底图/ 水系 / 路网 / 路线 / 四级等级 / 标记）
    // 都已在上方逐条登记，不会漏到这里。
    return c;
}
/** 等级 → 路色
 *
 * 【TC-11：数据不可用必须显示灰色，绝不显示成蓝色】
 * level < 1 即「数据不可用（-1）」或「该路段无等级数据」。
 * 初版这里 return C_ROUTE_EDGE（#0D5FB4 导航蓝），导致同一页上
 * 地图里画出一段蓝线、而下方图例写「数据不可用」—— 图文冲突且撞 TC-11。
 * 现统一走 C_CLOSED 灰，与 LevelMeta.UNAVAILABLE_META（#8B8B8B）同源。
 */
function levelColor(level: SegmentLevel): string {
    if (level < 1)
        return C_CLOSED;
    const m = LEVEL_META_LIST[Math.min(level, LEVEL_META_LIST.length) - 1];
    return m.color;
}
/** 自绘后端：所有绘制都走 Canvas 2D 上下文 */
export class SelfDrawRenderer implements MapRenderer {
    readonly name: string = 'self-draw';
    private ctx: CanvasRenderingContext2D | null = null;
    setup(): void {
        // 自绘档没有外部资源要初始化
    }
    /** 绑定 2D 上下文（由组件在 onReady 时调用；真地图档这里换成 SDK 初始化） */
    attach(ctx: CanvasRenderingContext2D): void {
        this.ctx = ctx;
    }
    /**
     * 本次绘制的画布真实尺寸（vp）—— 首次绘制后由 dc.size 校正。
     *
     * 【为什么必须校正 —— 用户截图报「地图偏在右下、左上大片空白，全页都有」】
     * 初版直接用 `defaultCamera(VIEW_W=340, mapHeight)` 里的 340 当画布宽，
     * 但组件上写的是 `.width('100%')` —— 实际画布宽是屏幕宽（约 360vp+），
     * 340 只是个写死的常量，与真实宽度对不上。
     * 于是缩放比与居中偏移全部算错：
     *   ① scale = min(340/框宽, h/框高) —— 偏小，路线被缩得比应更小
     *   ② offX = (340 − 框宽×scale)/2 —— 按 340 居中，画到 360 宽的画布上就整体右移
     * 两项叠加，正是截图里「内容挤在右下、左上留一大片空」的现象。
     *
     * 正解：`DrawingRenderingContext.size`（since 12）能拿到画布真实宽高，
     * 首次onReady 时读一次存下来，之后每次绘制都用真实值算缩放与居中。
     */
    private realW: number = 0;
    private realH: number = 0;

    /** 由组件在onReady 时把dc.size 传进来（真实画布尺寸） */
    setCanvasSize(w: number, h: number): void {
        this.realW = w;
        this.realH = h;
    }

    draw(req: RenderRequest): void {
        const ctx = this.ctx;
        if (ctx === null)
            return;
        const cam: MapCamera = req.camera;
        /**
         * 画布宽高：优先用 dc.size 量到的真实值，
         * 拿不到才退回 camera 里的标称值（首次绘制前）。
         */
        const w: number = this.realW > 0 ? this.realW : cam.viewWidth;
        const h: number = this.realH > 0 ? this.realH : cam.viewHeight;
        const u: boolean = req.unavailable;
        const cb: boolean = req.colorBlind;
        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = degrade(C_BG, u, cb);
        ctx.fillRect(0, 0, w, h);
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        /**
         * 【等比缩放 + 按「实际内容包围盒」居中 —— 用户投诉「地图左右两边留空不对称，排版要居中」的修法】
         *
         * 初版按固定的数据坐标空间 NET_W × NET_H 居中：
         *   scale = min(画布宽/680, 画布高/880)，offX = (画布宽 − 680×scale)/2。
         * 看起来是「居中」，但那是**坐标空间的中心**，不是**画出来的内容的中心**。
         * 实测本项目路网数据的实际范围是 x ∈ [−533, 725]，内容中心在 x≈96，
         * 而坐标空间中心是 340 —— 两者差 244，于是：
         *   内容整体偏左 → 右侧一大片空白、左侧被挤出去 → 视觉上「左右不对称」。
         *
         * 修法：先扫一遍真正要画的东西（路网各层 + 路线几何 + 标记）算出包围盒，
         * 再用**这个盒子**做等比缩放与居中。这样不管数据偏向哪边，
         * 画出来的内容永远居中，且四周留白对称。
         */
        const box: FitBox = fitBoxOf(req);
        const bw: number = box.maxX - box.minX;
        const bh: number = box.maxY - box.minY;
        const scale: number = Math.min(w / bw, h / bh);
        const offX: number = (w - bw * scale) / 2 - box.minX * scale;
        const offY: number = (h - bh * scale) / 2 - box.minY * scale;
        ctx.translate(offX, offY);
        ctx.scale(scale, scale);
        // ---- 绿地 / 水域 ----
        for (let i = 0; i < req.network.greens.length; i++) {
            this.fillPoly(ctx, req.network.greens[i], degrade(C_GREEN, u, cb));
        }
        for (let i = 0; i < req.network.waters.length; i++) {
            this.fillPoly(ctx, req.network.waters[i], degrade(C_WATER, u, cb));
        }
        // ---- 街区地块（描边矩形） ----
        ctx.strokeStyle = degrade(C_BLOCK_STROKE, u, cb);
        ctx.lineWidth = 1;
        for (let i = 0; i < req.network.blocks.length; i++) {
            const b: GeoPoint[] = req.network.blocks[i];
            ctx.fillStyle = degrade(C_BLOCK_FILL, u, cb);
            ctx.beginPath();
            ctx.moveTo(b[0].x, b[0].y);
            for (let k = 1; k < b.length; k++) {
                ctx.lineTo(b[k].x, b[k].y);
            }
            ctx.closePath();
            ctx.fill();
            ctx.stroke();
        }
        // ---- 次要路 ----
        ctx.strokeStyle = degrade(C_MINOR, u, cb);
        ctx.lineWidth = 7;
        for (let i = 0; i < req.network.minorRoads.length; i++) {
            const r: GeoPoint[] = req.network.minorRoads[i];
            ctx.beginPath();
            ctx.moveTo(r[0].x, r[0].y);
            for (let k = 1; k < r.length; k++) {
                ctx.lineTo(r[k].x, r[k].y);
            }
            ctx.stroke();
        }
        // ---- 主干道（Y 字的三条臂，描边 + 主体） ----
        ctx.strokeStyle = degrade(C_ARTERY_EDGE, u, cb);
        ctx.lineWidth = 19;
        for (let i = 0; i < req.network.arterys.length; i++) {
            const a: GeoPoint[] = req.network.arterys[i];
            ctx.beginPath();
            ctx.moveTo(a[0].x, a[0].y);
            for (let k = 1; k < a.length; k++) {
                ctx.lineTo(a[k].x, a[k].y);
            }
            ctx.stroke();
        }
        ctx.strokeStyle = degrade(C_ARTERY, u, cb);
        ctx.lineWidth = 16;
        for (let i = 0; i < req.network.arterys.length; i++) {
            const a: GeoPoint[] = req.network.arterys[i];
            ctx.beginPath();
            ctx.moveTo(a[0].x, a[0].y);
            for (let k = 1; k < a.length; k++) {
                ctx.lineTo(a[k].x, a[k].y);
            }
            ctx.stroke();
        }
        /**
         * 【空白原生地图：只画底图，到此为止】
         * req.blank = true（导航页「还没选路线」初态）：底图路网已画完，
         * 不画路线 / 车标 / 转向点 / 落客点 / 地名 —— 一个没有标任何东西的原生地图。
         */
        if (req.blank) {
            return;
        }
        /**
         * 【备选方案：灰色虚线，画在主线之前】
         * 高德导航的观感是「选中方案彩色实线 + 其余方案灰色细虚线」，
         * 司机一眼能看出有几条候选、哪条是自己选的。
         * 初版只画选中的那条 → 地图上永远只有一条线，
         * 用户反馈「路线二三是一样的」时根本无从判断（其实三条长得一样，
         * 且看不出是三个方案）。所以现在必须把未选中的方案也画出来。
         *
         * 【线宽与虚线间距：实测调出来的，别随手改】
         * · lineWidth 9 / dash[13,11]：两条备选叠在一起后虚线密到看不清底图，
         *   主线反被灰色淹没。
         * · lineWidth 5.5 / dash[16,14]：备选退到背景，但**又太弱**——
         *   实测截图上几乎看不出还有别的路（用户会问「另外两条呢」）。
         * 现在 7 / dash[15,13]，加一条 2.2px 的浅色外描边。
         * 外描边的作用：备选与主线**共用起点和终点**（同一个 OD 对），
         * 端点处三者重叠，没有描边的话虚线会被主线整个盖住。
         *
         * 【为什么用 setLineDash 而不是逐段画】
         * 逐段画要为每条折线算 dash 相位，代码长且容易在拐点处出现接缝；
         * Canvas 2D 的 setLineDash 由上下文自己处理相位，一步到位。
         * 注意：**必须每次重新设置**，因为下面画主线时不会再设 dash。
         */
        for (let a = 0; a < req.altRoutes.length; a++) {
            const ap: GeoPoint[] = req.altRoutes[a].points;
            if (ap.length < 2) {
                continue;
            }
            // 外描边（浅色）：让备选在端点重叠处也能被看见
            ctx.setLineDash([]);
            ctx.strokeStyle = degrade('#C6CFD4', u, cb);
            ctx.lineWidth = 10;
            ctx.beginPath();
            ctx.moveTo(ap[0].x, ap[0].y);
            for (let k = 1; k < ap.length; k++) {
                ctx.lineTo(ap[k].x, ap[k].y);
            }
            ctx.stroke();
            // 虚线主体
            ctx.setLineDash([15, 13]);
            ctx.strokeStyle = degrade(C_ALT, u, cb);
            ctx.lineWidth = 7;
            ctx.stroke();
        }
        ctx.setLineDash([]);

        // ---- 导航路线：高德式「红线」+ 等级分段 + 已走灰色 ----
        const pts: GeoPoint[] = req.route.points;
        if (pts.length >= 2) {
            /**
             * 【高德式「红线」—— 用户明确要的观感】
             * 先整条画一道粗红线（C_ROUTE_CASE）作描边，等级色叠在上面、两侧露出红线边，
             * 像高德/百度导航那样「一条醒目的主色路线」。
             * 抽色/降级时 degrade() 把红线也压成统一灰，符合 §11 口径。
             */
            ctx.strokeStyle = degrade(C_ROUTE_CASE, u, cb);
            ctx.lineWidth = req.selection ? 21 : 17;
            ctx.beginPath();
            ctx.moveTo(pts[0].x, pts[0].y);
            for (let i = 1; i < pts.length; i++) {
                ctx.lineTo(pts[i].x, pts[i].y);
            }
            ctx.stroke();
            /**
             * 等级分段叠色（与下方路段条、图例同源；红线作描边露在两侧）。
             * 沿折线逐点描，保证弯道与路线重合（拉弦会画出「毛毛虫」的坑已踩过）。
             */
            ctx.lineWidth = req.selection ? 13 : 11;
            let i: number = 0;
            while (i < pts.length - 1) {
                const seg: string = req.route.pointSegments[i];
                let j: number = i + 1;
                while (j < pts.length && req.route.pointSegments[j] === seg) {
                    j++;
                }
                const endIdx: number = (j >= pts.length) ? pts.length - 1 : j;
                const lv: SegmentLevel = req.route.levels[i];
                ctx.strokeStyle = degrade(levelColor(lv), u, cb);
                ctx.beginPath();
                ctx.moveTo(pts[i].x, pts[i].y);
                for (let k = i + 1; k <= endIdx; k++) {
                    ctx.lineTo(pts[k].x, pts[k].y);
                }
                ctx.stroke();
                i = j;
            }
            /**
             * 【导航进度：已走过路段画灰】
             * 车标之前的部分覆盖成灰，车标之后保持红线+等级色，
             * 形成「剩余红线 / 已过灰线」的推进观感（高德/Google 通用做法）。
             * 车在起点时 traveled 退化为零长，不画灰；到站时整条变灰。
             */
            const traveled: GeoPoint[] = traveledPolyline(pts, req.car);
            if (traveled.length >= 2) {
                ctx.strokeStyle = degrade(C_TRAVELED_EDGE, u, cb);
                ctx.lineWidth = req.selection ? 21 : 17;
                ctx.beginPath();
                ctx.moveTo(traveled[0].x, traveled[0].y);
                for (let i = 1; i < traveled.length; i++) {
                    ctx.lineTo(traveled[i].x, traveled[i].y);
                }
                ctx.stroke();
                ctx.strokeStyle = degrade(C_TRAVELED, u, cb);
                ctx.lineWidth = req.selection ? 13 : 11;
                ctx.beginPath();
                ctx.moveTo(traveled[0].x, traveled[0].y);
                for (let i = 1; i < traveled.length; i++) {
                    ctx.lineTo(traveled[i].x, traveled[i].y);
                }
                ctx.stroke();
            }
        }
        // ---- 转向点标记 ----
        for (let k = 0; k < req.marks.length; k++) {
            const mk = req.marks[k];
            if (mk.kind === 'maneuver') {
                /**
                 * 【为什么转向点画成小空心圈，不再是实心橙饼】
                 * 真实路网有 12 个转向点（初版只标 3 个，是虚构路网）。
                 * 12 个直径 18px 的实心橙饼会把整张地图糊成一片，
                 * 司机反而看不出主线在哪。改成白心橙环（外圈橙 + 内白），
                 * 保留「这里有个转向点」的提示，又不遮路。
                 */
                ctx.strokeStyle = degrade(C_MANEUVER, u, cb);
                ctx.lineWidth = 2.6;
                ctx.beginPath();
                ctx.arc(mk.at.x, mk.at.y, 5.5, 0, Math.PI * 2);
                ctx.stroke();
                ctx.fillStyle = '#FFFFFF';
                ctx.beginPath();
                ctx.arc(mk.at.x, mk.at.y, 2.2, 0, Math.PI * 2);
                ctx.fill();
            }
            else if (mk.kind === 'pin') {
                // 落客点：红旗
                ctx.fillStyle = degrade(C_PIN, u, cb);
                ctx.strokeStyle = '#FFFFFF';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(mk.at.x, mk.at.y);
                ctx.lineTo(mk.at.x - 9, mk.at.y - 12);
                ctx.lineTo(mk.at.x + 9, mk.at.y - 12);
                ctx.closePath();
                ctx.fill();
                ctx.stroke();
                ctx.fillStyle = '#FFFFFF';
                ctx.fillRect(mk.at.x - 3, mk.at.y - 9, 6, 6);
            }
            else {
                /**
                 * `depart` 标记如果走到这里说明 RoadNetMap 传错了 kind，
                 * 起点已由车标表示、不在此画点，什么都不画比画一个位置不准的点好。
                 */
            }
        }

        /**
         * 【引导红线：车标 → 终点蓝点的直连线（用户参考高德截图明确要求）】
         * 参考图（高德导航）：一条细红直线从「车标当前位置」直连「目的地」，
         * 常规导航 App 都有 —— 让司机不看路线也知道目标方向。
         * 三页统一生效：导航页 / 落客页 / 离站页的地图都走这里（非 blank 即画）。
         * 【随车标移动】线的起点是 req.car（车标由 maneuverIndex 算出），
         * 点「继续」→ maneuverIndex 变 + bumpEpoch → 节点重建重画 → 红线跟着车标走，
         * 车到哪红线就从哪出发，到站时收敛到终点蓝点上（长度归零）。
         * 画在路线/转向点之后、车标与终点圆点之前：被车标压住端头，观感与高德一致。
         * 抽色（unavailable/colorBlind）时与路线描边同一映射，压成统一灰（§11.3）。
         */
        ctx.setLineDash([]);
        ctx.strokeStyle = degrade(C_ROUTE_CASE, u, cb);
        ctx.lineWidth = 5;
        ctx.globalAlpha = 0.9;
        ctx.beginPath();
        ctx.moveTo(req.car.x, req.car.y);
        ctx.lineTo(req.route.end.x, req.route.end.y);
        ctx.stroke();
        ctx.globalAlpha = 1.0;

        // ---- 起点不再画独立圆点：车标初始压在起点，开动后不留蓝圈 ----
        // ---- 终点圆点（用户要求三页一致：导航/落客页也要有蓝色终点） ----
        drawEndDot(ctx, req.route.end, u, cb);

                // ---- 车标（蓝圈+白环+方向三角；位置随「继续」沿路线移动，落客/离站页恒在起点） ----
        drawCar(ctx, req.car, req.route.points, u, cb);
        // ---- 地名标注 ----
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = degrade(C_LABEL, u, cb);
        for (let i = 0; i < req.network.labels.length; i++) {
            ctx.fillText(req.network.labels[i].text, req.network.labels[i].at.x, req.network.labels[i].at.y);
        }
    }
    focusOn(target: GeoPoint, zoom?: number): void {
        // 自绘档是静态图，相机对视觉无影响；真地图档在这里平移/缩放到 target
    }
    hitTest(x: number, y: number): string {
        // 自绘档不做命中测试（当前无点击选路段需求）；真地图档可返回该点所属 segment_id
        return '';
    }
    dispose(): void {
        this.ctx = null;
    }
    private fillPoly(ctx: CanvasRenderingContext2D, p: GeoPoint[], color: string): void {
        if (p.length < 3)
            return;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.moveTo(p[0].x, p[0].y);
        for (let i = 1; i < p.length; i++) {
            ctx.lineTo(p[i].x, p[i].y);
        }
        ctx.closePath();
        ctx.fill();
    }
}
