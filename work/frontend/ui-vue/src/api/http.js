// REST 访问面:统一 fetch 封装(三页 + 感知页共用)。
//
// 路径一律**同源相对路径**(`/api/traffic/*` / `/perception-api/*`),由 vite 代理到真实服务:
//   · `npm run dev`(VITE_USE_MOCK=1)→ `/api` 由 mock 中间件处理(无后端也能演示);
//   · `npm run dev:remote`(VITE_USE_MOCK=0)→ `/api` 代理到 traffic.py(默认 127.0.0.1:8000),
//     `/perception-api` 代理到感知演示服务(默认 127.0.0.1:8101);
//   · build 产物由后端同源托管,仍是相对路径。
// 浏览器端**不读** `VITE_API_BASE`(该变量只是 vite 的代理目标)——避免三页各自拼绝对地址 /
// 绕开代理吃 CORS,也保证 mock / 真接口切换时页面形状不变。
//
// 失败必须可读:网络不可达 / 请求超时 / 后端错误码 三类分开报,页面据此显式降级(TC-06/TC-11)。
import { ref } from 'vue';
import { activePackKey } from '../station-packs/index';
import { USE_MOCK } from '../shared/env';
export class ApiError extends Error {
    status;
    code;
    /** 是否为客户端超时(区别于后端返回的错误) */
    timeout;
    constructor(status, code, message, timeout = false) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.code = code;
        this.timeout = timeout;
    }
}
/** 默认超时(毫秒):接口层只读快照,正常 < 1s;10s 还没回按失败处理(不无限转圈) */
export const REQUEST_TIMEOUT_MS = 10_000;
/**
 * 后端可达性(顶栏「运行模式」chip 用,Issue IKP58M)。
 *
 * - `null` = 本次会话还没发出过请求 —— 不臆断「能连上」,也不先报红;
 * - `true` / `false` = 最近一次**真实请求**的结论。
 *
 * 只在 remote 模式更新:mock 模式的 `/api` 由 vite 中间件回答,它成功不代表 traffic.py 活着。
 * 不新造轮询 —— 页面每次取数、每次重试、SSE 重连都会经过 `request()`,状态自然跟着刷新;
 * 单开一个 setInterval 探活只会多一份要维护的假数据源。
 */
export const backendReachable = ref(null);
/** 后端不可达时的可读提示(按当前运行模式给排障指向,不笼统说"网络错误") */
export function networkHint() {
    return USE_MOCK
        ? '后端不可达:mock 模式下请确认 vite dev server 在跑(不依赖 traffic.py)'
        : '后端不可达:remote 模式请确认 traffic.py 已启动(python work/assembly/traffic.py --port 8000)且 vite 代理在跑';
}
export async function request(method, path, opts = {}) {
    const headers = {};
    if (opts.body !== undefined)
        headers['Content-Type'] = 'application/json';
    // 顶栏「线路图切换器」选的是**浏览器侧**的包键,而 mock 中间件跑在 vite 的 Node 进程里,
    // 天生拿不到浏览器状态 —— 所以每个请求把当前包键带上,mock 按它现取包。
    // 真接口 traffic.py（IKNB9F 起）同样按这个头切站；并用查询参数 `station` 兜底
    // （某些浏览器/代理对自定义请求头不友好时仍能按站取数；mock 侧只认头，两条通道不冲突）。
    const stationKey = opts.station ?? activePackKey();
    headers['X-Station-Pack'] = stationKey;
    const requestPath = USE_MOCK
        ? path
        : `${path}${path.includes('?') ? '&' : '?'}station=${encodeURIComponent(stationKey)}`;
    const controller = new AbortController();
    const timeoutMs = opts.timeoutMs ?? REQUEST_TIMEOUT_MS;
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    let onOuterAbort = null;
    if (opts.signal) {
        onOuterAbort = () => controller.abort();
        if (opts.signal.aborted)
            controller.abort();
        else
            opts.signal.addEventListener('abort', onOuterAbort, { once: true });
    }
    try {
        const res = await fetch(requestPath, {
            method,
            headers,
            body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
            signal: controller.signal,
        });
        // 502/503/504 是 vite 代理「后端没起」的固定表现（见下方错误分支）：先按不可达记；
        // 其余 HTTP 状态说明后端至少回了话，可达性为真（端点级错误由 ApiError 继续抛）。
        if (!USE_MOCK) {
            backendReachable.value = !(res.status === 502 || res.status === 503 || res.status === 504);
        }
        if (!res.ok) {
            let code = `HTTP_${res.status}`;
            let message = res.statusText || `请求失败(${res.status})`;
            try {
                const data = (await res.json());
                if (typeof data.code === 'string')
                    code = data.code;
                if (typeof data.message === 'string')
                    message = data.message;
                else if (typeof data.error?.message === 'string')
                    message = data.error.message;
                // 接口层的 note 是"为什么没有 + 降级口径",带进错误里便于页面提示(不丢诊断信息)
                if (typeof data.note === 'string' && data.note)
                    message = `${message}（${data.note}）`;
            }
            catch {
                /* 非 JSON 错误体:用状态文本 */
            }
            // vite 代理在后端未起 / 断开时回 502(Bad Gateway):这是"数据不可用"的主场景,
            // 给可读提示(而不是把 "Bad Gateway" 直接抛给页面)。
            if (res.status === 502 || res.status === 503 || res.status === 504) {
                throw new ApiError(res.status, 'BACKEND_UNAVAILABLE', `后端不可用(网关 ${res.status}):${networkHint()}`);
            }
            if (res.status === 404)
                message = `${message}(端点不存在或服务未就绪:${method} ${path})`;
            throw new ApiError(res.status, code, message);
        }
        if (res.status === 204)
            return undefined;
        // ⚠️ 超时定时器要覆盖 **读 body**(res.json),不能只覆盖到响应头：
        // 大包/半开连接时响应头先到、body 卡住,旧实现在 finally 里已 clearTimeout,会把 10s 超时变成无限等。
        return (await res.json());
    }
    catch (e) {
        // 调用方主动取消(切页 / 丢弃过期响应):原样抛出,页面按 AbortError 处理
        if (e instanceof ApiError)
            throw e;
        if (opts.signal?.aborted)
            throw e;
        // 走到这里的只剩「请求没拿到任何 HTTP 响应」:网络不可达 / 超时 —— 顶栏 chip 据此转警示色
        if (!USE_MOCK)
            backendReachable.value = false;
        if (e instanceof DOMException && e.name === 'AbortError') {
            throw new ApiError(0, 'TIMEOUT', `请求超时(${timeoutMs}ms):${method} ${path} —— ${networkHint()}`, true);
        }
        throw new ApiError(0, 'NETWORK', `网络错误:${method} ${path} —— ${networkHint()}`, true);
    }
    finally {
        clearTimeout(timer);
        if (opts.signal && onOuterAbort)
            opts.signal.removeEventListener('abort', onOuterAbort);
    }
}
