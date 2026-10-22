// 感知层检测流访问面(Issue #54):感知演示服务的只读端点,不做任何业务计算。
// 数据由 work/perception/tools/dump_monitor_data.py 离线导出(样本视频 → MindSpore YOLO
// 检测 + ByteTrack 跟踪),经 work/perception/server.py 出接口;vite 把独立前缀
// /perception-api 代理并重写到服务端 /api/perception(见 vite.config.ts,避开 traffic mock)。
// 检测框/轨迹是一期接口面新增形状,非契约 v2.0 字段;
// meta/health 响应带 is_simulated=true 信封(detections/frames 为原始载荷不含信封),
// 页面显著标注"样本视频回放 · 演示数据(模拟)"。
//
// 请求统一走 `api/http.ts` 的 request()(超时 / 可读错误 / 相对路径同一套),不各自拼路径。
import { request } from './http';
// 检测载荷可能数 MB:放宽到 20s(服务未起时也会在超时后给出可读错误,不无限转圈)
async function getJson(path) {
    return request('GET', path, { timeoutMs: 20_000 });
}
// GET /perception-api/streams → 全部检测通道 meta(服务端路径 /api/perception/streams)
export function getPerceptionStreams() {
    return getJson('/perception-api/streams');
}
// GET /perception-api/streams/{sid}/detections → 逐帧检测框
export function getPerceptionDetections(streamId) {
    return getJson(`/perception-api/streams/${encodeURIComponent(streamId)}/detections`);
}
// 第 n 帧 JPEG(1 起);直接作 <img>/Image src 使用
export function perceptionFrameUrl(streamId, frame1) {
    return `/perception-api/streams/${encodeURIComponent(streamId)}/frames/${frame1}.jpg`;
}
// GET /perception-api/streams/{sid}/summary → 通道汇总(分车型 / 轨迹质量与标定 / 输出字段 / 处理口径)
export function getPerceptionSummary(streamId) {
    return getJson(`/perception-api/streams/${encodeURIComponent(streamId)}/summary`);
}
