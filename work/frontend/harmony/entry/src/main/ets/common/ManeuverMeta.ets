/**
 * 转向提示的「显示层」映射：转向类型 → 图标 / 导航条文案。
 *
 * 【这个文件为什么从 YRouteMap.ets 里独立出来】
 * 初版这两个函数寄居在 `YRouteMap.ets`（那份虚构 Y 字示意路网）里，
 * 而真实路网早就是 `RealNet.ets` 了 —— Y 字数据 400 行全部零引用，
 * 只有这两个纯字符串映射函数还被 NavBar 用着。
 * 于是形成一种很难解释的结构：真实导航条的字取自一份**废弃的示意数据**文件，
 * 评审翻代码时极易误判「Y 字路线还在生效」。
 * 现把仅存的两处映射迁到本文件，YRouteMap.ets 整份删除。
 *
 * 改这两个函数只需看本文件，不必去翻路网数据。
 */

/** 转向类型 → 导航条上的图标（与手册 §11.3 三重编码里的「图标」通道对应） */
export function maneuverGlyph(type: string): string {
    if (type === 'depart')
        return '⬆';
    if (type === 'fork_right')
        return '↱';
    if (type === 'fork_left')
        return '↰';
    if (type === 'left')
        return '←';
    if (type === 'right')
        return '→';
    if (type === 'arrive')
        return '◎';
    return '⬆';
}

/** 转向类型 → 导航条文案
 *
 * 【为什么 arrive 要由调用方传场景，不能写死「到达落客点」】
 * 离站导航的最后一个转向点同样是 `arrive`，但司机是**离站**不是落客 ——
 * 写死「到达落客点」会让离站导航条显示「到达落客点」，语义完全错。
 * （实跑验证截图抓到的真实回归：离站页点已选卡进导航，顶部写「到达落客点」。）
 * 故由调用方按 isDeparture 传场景词进来，两条导航各自正确。
 */
export function maneuverText(type: string, isDeparture: boolean): string {
    if (type === 'depart')
        return '直行进入';
    if (type === 'fork_right')
        return '靠右进入支路';
    if (type === 'fork_left')
        return '靠左进入支路';
    if (type === 'left')
        return '左转';
    if (type === 'right')
        return '右转';
    if (type === 'arrive')
        return isDeparture ? '到达离站点' : '到达落客点';
    return '继续行驶';
}