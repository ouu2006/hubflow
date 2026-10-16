"""把 realmap2.json 转成工程内的 common/RealNet.ets（ArkTS）。

【输出格式为什么是扁平 number[]】
ArkTS 里几百个 { x: 112, y: 234 } 对象字面量既占体积又拖慢编译。
这里输出 x0,y0,x1,y1,… 的扁平数组，运行期用 toPts() 展开成 GeoPoint。

【数据来源口径】
坐标来自队长提供的自绘底图（团队自绘，非第三方瓦片），
按地图条款走「自绘图」档，不落盘瓦片、不调第三方在线地图接口。
"""
import json
import os

SRC = r"C:\dev\hubflow\.tmp-y\realmap2.json"
DST = r"C:\dev\hubflow\work\frontend\harmony\entry\src\main\ets\common\RealNet.ets"


def fmt_lines(name, arrs, indent="    "):
    out = [f"const {name}: number[][] = ["]
    for a in arrs:
        out.append(indent + "[" + ",".join(str(v) for v in a) + "],")
    out.append("];")
    return "\n".join(out)


def fmt_flat(name, flat, indent="    "):
    body = ", ".join(str(v) for v in flat)
    # 每行最多 ~110 字符，可读又不至于超长
    chunks = []
    cur = ""
    for tok in body.split(", "):
        if len(cur) + len(tok) + 2 > 108:
            chunks.append(cur.rstrip())
            cur = indent + tok + ", "
        else:
            cur += tok + ", "
    if cur.strip():
        chunks.append(cur.rstrip().rstrip(","))
    out = [f"const {name}: number[] = ["]
    out.extend("    " + c for c in chunks)
    out.append("];")
    return "\n".join(out)


def main():
    d = json.load(open(SRC, encoding="utf-8"))
    org = d["origin"]
    parts = []
    parts.append("""import { GeoPoint, MapLabel, Maneuver, RoadNetwork } from './MapPort';

/**
 * 真实路网数据（一次期自绘档底图）。
 *
 * 【数据来源与口径 —— 评审必问「这地图哪来的」，写在这里】
 * 坐标取自团队自绘的站前路网底图（`hubflow-nosearch` 自绘稿），
 * 按地图条款走**自绘图**档：不接第三方在线地图接口、不缓存、不落盘瓦片。
 * 后续要接可动地图时，实现 `MapRenderer` 另写一档即可，本文件不用动。
 *
 * 【投影 —— 为什么坐标是整数而不是经纬度】
 * 源数据是经纬度（WGS84）。自绘档直接当画布像素用，所以这里预先做了：
 *   1) 等距圆柱投影（x 乘 cos(中心纬度) 做等比，两轴同一比例尺，不变形）
 *   2) 以**路线包围盒**为基准定比例尺（而不是全图层）——
 *      路线只占路网中间约一半，按全图层定标会让路线细得看不清走向
 *   3) 抽稀（RDP）后取整，减小文件体积与绘制开销
 * 原点（把像素还原成经纬度的基准点）与比例尺见下方常量。
 */

/** 画布坐标空间宽高（与 MapTypes 的 MAP_NET_W/H 一致） */
export const REAL_W: number = %d;
export const REAL_H: number = %d;
/** 像素→经纬度的还原基准（评审/接手人要把图接回真地图时用得上） */
export const REAL_ORIGIN_LNG: number = %.7f;
export const REAL_ORIGIN_LAT: number = %.7f;
/** 比例尺：米 → 像素 */
export const REAL_PX_PER_M: number = %.8f;
/** 路线总长（米，取自底图自带的里程累计） */
export const REAL_ROUTE_TOTAL_M: number = %d;
""" % (d["W"], d["H"], org["lng"], org["lat"], org["scale_px_per_m"], d["total_m"]))

    parts.append("/** 展开扁平数组 → 折线（运行期用，避免源文件里全是对象字面量） */")
    parts.append("""function toPts(flat: number[]): GeoPoint[] {
    const out: GeoPoint[] = [];
    for (let i = 0; i + 1 < flat.length; i += 2) {
        out.push({ x: flat[i], y: flat[i + 1] });
    }
    return out;
}

/** 展开一组扁平数组 → 多条折线 */
function toLines(flats: number[][]): GeoPoint[][] {
    const out: GeoPoint[][] = [];
    for (let i = 0; i < flats.length; i++) {
        out.push(toPts(flats[i]));
    }
    return out;
}

/** 展开多边形（首尾点自动闭合，避免源数据少一个重复点导致不闭合） */
function toPolys(flats: number[][]): GeoPoint[][] {
    const out: GeoPoint[][] = [];
    for (let i = 0; i < flats.length; i++) {
        const p: GeoPoint[] = toPts(flats[i]);
        if (p.length >= 3) {
            p.push({ x: p[0].x, y: p[0].y });
            out.push(p);
        }
    }
    return out;
}
""")

    parts.append("/** 主干道（真实路网 major） */")
    parts.append(fmt_lines("MAJORS_FLAT", d["majors"]))
    parts.append("/** 次要路（真实路网 minor） */")
    parts.append(fmt_lines("MINORS_FLAT", d["minors"]))
    parts.append("/** 水域 */")
    parts.append(fmt_lines("WATERS_FLAT", d["waters"]))
    parts.append("/** 绿地 */")
    parts.append(fmt_lines("GREENS_FLAT", d["greens"]))

    parts.append("/** 路线几何：R1 推荐（真实路线）/ R2 / R3 两条平行备选 */")
    for k in ("R1", "R2", "R3", "D1", "D2"):
        parts.append(fmt_flat("ROUTE_%s_FLAT" % k, d["routes"][k]))

    # 转向点
    parts.append("""/**
 * 真实转向点（源数据只给里程 d，按里程在路线折线上插值定位得到坐标）。
 * 字段：d = 距起点里程(米)，type/mod 为底图的转向类型与方位，name 为路名。
 */
export interface RealManeuverMark {
d: number;
    type: string;
    mod: string;
    name: string;
    x: number;
    y: number;
}
""")
    lines = ["export const REAL_MANEUVER_MARKS: RealManeuverMark[] = ["]
    for mv in d["maneuvers"]:
        lines.append("    { d: %d, type: '%s', mod: '%s', name: '%s', x: %d, y: %d },"
                     % (mv["d"], mv["type"], mv["mod"], mv["name"], mv["x"], mv["y"]))
    lines.append("];")
    parts.append("\n".join(lines))

    parts.append("""/** 真实路网（交给渲染后端；blocks 留空——真实底图自带地块，不需要虚构方块） */
export const REAL_ROAD_NETWORK: RoadNetwork = {
    minorRoads: toLines(MINORS_FLAT),
    arterys: toLines(MAJORS_FLAT),
    blocks: [],
    greens: toPolys(GREENS_FLAT),
    waters: toPolys(WATERS_FLAT),
    labels: [] as MapLabel[]
};

/** 取一条路线几何（0=推荐 1=备选一 2=备选二） */
export function realRoutePts(idx: number): GeoPoint[] {
    if (idx === 1) {
        return toPts(ROUTE_R2_FLAT);
    }
    if (idx === 2) {
        return toPts(ROUTE_R3_FLAT);
    }
    return toPts(ROUTE_R1_FLAT);
}

/** 取离站路线几何（0=主选 1=备选） */
export function realDeparturePts(idx: number): GeoPoint[] {
    if (idx === 1) {
        return toPts(ROUTE_D2_FLAT);
    }
    return toPts(ROUTE_D1_FLAT);
}

/** 路线上的转向点（按方案给对应的一条） */
export function realManeuvers(): Maneuver[] {
    const out: Maneuver[] = [];
    for (let i = 0; i < REAL_MANEUVER_MARKS.length; i++) {
        const m: RealManeuverMark = REAL_MANEUVER_MARKS[i];
        out.push({
            type: m.type,
            at: { x: m.x, y: m.y },
            fromRoad: m.name,
            toRoad: m.name,
            distM: m.d,
            segmentId: ''
        });
    }
    return out;
}
""")

    text = "\n".join(parts) + "\n"
    text = text.replace("\r\n", "\n")
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    open(DST, "w", encoding="utf-8", newline="\n").write(text)
    print("written", DST, len(text), "bytes", text.count("\n"), "lines")


if __name__ == "__main__":
    main()
