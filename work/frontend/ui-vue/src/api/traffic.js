// traffic 态势大屏访问面(Issue #52):只读快照 + SSE,不做任何业务计算。
// 2026-10-11 架构裁定:harness 架构不复用,后端接口面待按前端页面重新规划
// (原实现基准 PR #51 骨架已收回,内容可在该 PR 页面回看;mock 端点暂沿 Issue #52 清单)。
// 一期 mock 演示:全部数据 is_simulated=true,页面显著标注"示例数据"。
import { TRAFFIC_SNAPSHOT_EVENT } from '../shared/traffic';
import { request } from './http';
// GET /api/traffic/segments → segments 快照(契约 v2.0)
export function getTrafficSegments(opts = {}) {
    return request('GET', '/api/traffic/segments', opts);
}
// GET /api/traffic/segments/{id} → 单路段详情(含 factors_applied / pred),形状与列表元素一致
export function getTrafficSegment(segmentId) {
    return request('GET', `/api/traffic/segments/${encodeURIComponent(segmentId)}`);
}
// GET /api/traffic/vehicles → 孪生车辆位置(仅一期演示用,二期端点下线)
export function getTrafficVehicles(opts = {}) {
    return request('GET', '/api/traffic/vehicles', opts);
}
// POST /api/traffic/route/recommend → 推荐路线快照(引擎写入 routes.json,接口层只端出来)
export function postRouteRecommend(body) {
    return request('POST', '/api/traffic/route/recommend', { body });
}
// GET /api/traffic/route/options → 引擎路线产物的 OD/session 摘要列表（Issue IKNAUI，非契约辅助端点）
// 供大屏「整条路线规划」选择器；缺产物时接口层如实 404，页面按空窗 + note 降级（不编 ETA）。
export function getTrafficRouteOptions() {
    return request('GET', '/api/traffic/route/options');
}
export function postTrafficLocate(body = {}) {
    return request('POST', '/api/traffic/locate', { body });
}
// GET /api/traffic/stream(SSE,事件 traffic_snapshot)→ 轻量刷新事件;页面收到后重新拉快照。
// EventSource 无法附带鉴权头;当前端点公开访问,鉴权方案随接口面重新规划一并定稿。
export function subscribeTrafficSnapshot(onPing, onState) {
    const es = new EventSource('/api/traffic/stream');
    es.onopen = () => onState?.(true);
    es.onerror = () => onState?.(false); // EventSource 会自动重连,状态只作展示
    es.addEventListener(TRAFFIC_SNAPSHOT_EVENT, (ev) => {
        let payload = { ts: '', is_simulated: true };
        try {
            payload = JSON.parse(ev.data);
        }
        catch {
            /* 非 JSON 帧:按空载荷处理,只当刷新信号 */
        }
        onPing(payload);
    });
    return () => es.close();
}
// ---------- 决策工作台(Issue #59,接口面新增) ----------
// GET /api/traffic/assimilation → 数据同化状态(哪些边界断面在回灌、门控原因)
export function getTrafficAssimilation() {
    return request('GET', '/api/traffic/assimilation');
}
// POST /api/traffic/factors → 人工置位因素(管理端口子;mock 侧生效并重算判级,演示行为)
export function postTrafficFactor(body) {
    return request('POST', '/api/traffic/factors', { body });
}
// POST /api/traffic/factors/reset → 清空人工置位(演示复位)
export function postTrafficFactorReset() {
    return request('POST', '/api/traffic/factors/reset');
}
// =====================================================================================
// 四页重做(Issue #78):按 4 张设计稿重新规划出的接口面
// 约定沿用:同源相对路径;每个响应带 is_simulated 信封;只读快照、不做业务计算。
// 后端尚未实现,当前全部由 src/mock/traffic.ts 端出(未匹配路径一律 404)。
// =====================================================================================
// GET /api/traffic/meta → 站点 / 数据源 / 顶栏页签 / 口径角标
export function getTrafficMeta(opts = {}) {
    return request('GET', '/api/traffic/meta', opts);
}
// GET /api/traffic/overview → 全网 KPI(均速与环比 / 最堵路段 / 在途与采纳率 / 生效因素数 / 等级分布)
export function getTrafficOverview(opts = {}) {
    return request('GET', '/api/traffic/overview', opts);
}
// GET /api/traffic/network → 路网几何 + 断面(边界/内部) + 落客点 + 场区(地图底图)
export function getTrafficNetwork() {
    return request('GET', '/api/traffic/network');
}
// GET /api/traffic/segments/{id}/sources → 同一路段 video / twin 并排 + 差值(TC-19 展示侧)
export function getTrafficSegmentSources(segmentId, opts = {}) {
    return request('GET', `/api/traffic/segments/${encodeURIComponent(segmentId)}/sources`, opts);
}
// GET /api/traffic/alerts → 告警列表(四态 + 指标依据 + 首次观测时间)
export function getTrafficAlerts(opts = {}) {
    return request('GET', '/api/traffic/alerts', opts);
}
// POST /api/traffic/alerts/reset → 复位告警下发 / 回写演示态(mock 侧内存态;刷新页面不清,要清走这里)
export function postTrafficAlertsReset() {
    return request('POST', '/api/traffic/alerts/reset');
}
// POST /api/traffic/plan/dispatch → 下发分流方案(渠道 + 分流比例),返回回执
export function postPlanDispatch(body) {
    return request('POST', '/api/traffic/plan/dispatch', { body });
}
// POST /api/traffic/plan/ack → 处置回写(认领人 / 动作 / 结果四选一)
export function postPlanAck(body) {
    return request('POST', '/api/traffic/plan/ack', { body });
}
// GET /api/traffic/predict?segment_id=&h=15 → 预测(一期 L0,不报精度数字)
export function getTrafficPredict(segmentId, h) {
    return request('GET', `/api/traffic/predict?segment_id=${encodeURIComponent(segmentId)}&h=${h}`);
}
// GET /api/traffic/thresholds → 判级阈值 + CI 加权构成 + 变更留痕(只读,P1)
export function getTrafficThresholds(opts = {}) {
    return request('GET', '/api/traffic/thresholds', opts);
}
// GET /api/traffic/heat-matrix?window=&bucket= → 路段 × 时间热力矩阵(近 window 个桶)
export function getTrafficHeatMatrix(buckets = 12, bucketSec = 60, opts = {}) {
    return request('GET', `/api/traffic/heat-matrix?window=${buckets}&bucket=${bucketSec}`, opts);
}
// GET /api/traffic/ci-history?segment_id=&points=12 → 单路段 CI 走势
export function getTrafficCiHistory(segmentId, points = 12, opts = {}) {
    return request('GET', `/api/traffic/ci-history?segment_id=${encodeURIComponent(segmentId)}&points=${points}`, opts);
}
// GET /api/traffic/factors?segment_id= → 当前生效因素清单(可选按路段过滤)
/** 生效因素清单。`segmentId` 省略 = 全网(各路段展平);`opts` 见 `SnapshotFetchOptions` */
export function getTrafficFactors(segmentId, opts = {}) {
    const q = segmentId ? `?segment_id=${encodeURIComponent(segmentId)}` : '';
    return request('GET', `/api/traffic/factors${q}`, opts);
}
// GET /api/traffic/assimilation → 数据同化状态(含断面 role:仅 role=boundary 允许回灌)
export function getTrafficAssimilationFull() {
    return request('GET', '/api/traffic/assimilation');
}
// =====================================================================================
// 三页收敛(Issue #77):环境上下文 + 场景注入
// 口径:天气 / 时段是**编造的演示值**(拿不到真实数据),一律标「演示数据(模拟)」;
// 场景注入与「人工置位」(F07 / F08 / F11)是两个口子,不得混称。
// =====================================================================================
// GET /api/traffic/context → 环境上下文(天气 / 时间 + 折算出的因素 F01/F02/F03/F10)
export function getTrafficContext() {
    return request('GET', '/api/traffic/context');
}
// GET /api/traffic/report/compare → 效果对比报表(接口层无报表产物时 rows 为空 + note,页面如实降级)
export function getTrafficReportCompare() {
    return request('GET', '/api/traffic/report/compare');
}
// POST /api/traffic/scenario → 场景注入(天气 / 时段 / 需求倍率 → 因素),返回判级前后对照
export function postTrafficScenario(body) {
    return request('POST', '/api/traffic/scenario', { body });
}
// POST /api/traffic/scenario/reset → 清场景注入(演示复位,与 factors/reset 同口径)
export function postTrafficScenarioReset() {
    return request('POST', '/api/traffic/scenario/reset');
}
