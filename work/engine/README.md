# work/engine · 决策与定位 + 判级（开发B）

> **产出**：`routes.json` —— 推荐路线、备选、离站路线、时段预约与不伤害判定
> **消费方**：前端（管理端 + 司机端）
> **同时负责**：`stations/` 站点包**结构**、**数据契约（`segments` / `routes` / `vehicles` 字段）唯一裁定人**、OSM 路网导入与站点包转换脚本、**判级 `work/perception/level.py`**、**`stations/thresholds.json` 的判级参数组 + 决策参数组（唯一写手）**
>
> **角色简称**：开发A / 开发B / 开发C；**池·V / 池·S / 池·P / 池·Q** = 任务池四个系列（视频线 / 站点踏勘 / 参数调研 / 独立验收）的**认领者**（协作成员，无锁角色，原 N1~N4 定岗已作废）；**队长** = 7 人中 1 人兼任，**不参与认领**。

## 一、负责什么

```text
读 segments.json（实测/孪生指标 + 因素）
   → 路网 + 行程时间函数 → K 条候选路径
   → ① 时段容量预约  ② 不伤害前车约束  ③ 前车再疏导
   → routes.json
```

## 二、核心机制：**时段容量预约 + 不伤害前车约束 + 前车再疏导**

### 2.1 要解决的问题（大白话）

普通导航：A 路最快 → 告诉所有人走 A 路 → 前几辆车很快，后面的车涌进去，A 路堵死，**前车也被后车拖慢**。

旧方案的"配额发号"解决了"别都往一条路挤"，但**只按路线计数**：没考虑"前车什么时候到哪一段"，也没有"前车遇堵再疏导"。

### 2.2 三件事一起做

| 机制 | 做什么 | 效果 |
|---|---|---|
| **① 时段容量预约** | 把每条路段按 **1 分钟**切成时段；推荐一辆车时，按它的**预计到达时间**，在它将经过的**每段路 × 每个时段**上各登记一个占用 | 后车看到的是"前车将来会在哪"，不是只看"现在哪条路空" |
| **② 不伤害前车约束** | 新车只能放进"加上它之后，**所有已登记车辆的预计耗时增加都不超过 30 秒**【待标定】、**任何路段时段饱和度不超过 0.85**【待标定】"的路线；在满足约束的路线里选**对它自己最快**的 | 后车进来不会把前车拖慢；后车自动分流到其他道路 |
| **③ 前车再疏导** | 每 **60 秒**检查在途车辆：前方路段变堵时，在**下一个可分岔路口前**给出改道建议（**每车最多改 2 次**，**10% 滞回**防抖）；送完客的车优先引导离开落客区 | 前车被及时疏散，给后车腾容量 |

**都放不下时**：输出 `capacity_shortage`，建议"外围等待 / 延后 N 分钟 / 换停车场"，**不硬塞**。

**没装 App 的车**：它们是"**背景车流**"，由检测器（一期虚拟、二期摄像头）测出、由预测模型（二期）推到未来时段；**预约表在背景车流之上再叠加 App 用户的预约**。

### 2.3 步骤表（`recommend()` 的执行顺序）

| 步 | 做什么 | 判定 / 失败处理 |
|---|---|---|
| ① | 生成候选：K 最短路（路径重叠度 ≤ 0.7） | `K = 3` |
| ② | 沿候选路径**按时段推进**，算出它经过的 `(路段, 时段)` 格子与 ETA | 行程时间用 BPR 函数（见 2.4） |
| ③ | **约束①**：任一格子的饱和度 `(背景车流 + 已预约 + 本车) / 通行能力` 不得超过 `X_SAFE` | 超了就**丢弃这条候选** |
| ④ | **约束②**：算加入本车后**已登记前车**的 ETA 最大增加量 | 超过 `EPS_HARM` 就**丢弃这条候选** |
| ⑤ | 在**通过两个约束**的候选里，选**对本车最快**的那条 | — |
| ⑥ | **登记预约**：写入时段格子，生成租约（`lease_expire_s = 90`） | 90 s 未确认采纳 → 释放 |
| ⑦ | 输出推荐 + 备选 ≥2 + `why` + `reservation.harm_check` | 全部候选被丢弃 → `capacity_shortage` |

### 2.4 关键参数表（**demo 假设值，不得对外当承诺**）

| 参数 | 符号 | 值 | 说明 |
|---|---|---|---|
| **时段粒度** | — | **1 分钟** | 每条路段按 1 分钟切时段 |
| **预约租约** | `T_lease` | **90 s** | 未确认采纳即释放 |
| **周期重算** | `ΔT` | **60 s** | 用**实测流量**（不是发放量）刷新预约表 |
| **不伤害上限** | `EPS_HARM` | **30 s**【待标定】 | 前车 ETA 允许被后车增加的上限 |
| **再疏导触发阈值** | `REROUTE_TH` | **30 s**【待标定】 | ETA 增加超过多少才考虑改道；站点包 decision 组独立键 `reroute_threshold_s`（T2 补键，占位值待池·P 标定；`reroute.py` 优先读它、缺键回落 `eps_harm_s`） |
| **时段饱和度上限** | `X_SAFE` | **0.85**【待标定】 | 任一 `(路段, 时段)` 的饱和度上限 |
| **切换滞回** | `h` | **10%** | 改道收益不到 10% 就不改，防抖 |
| **每车最多改道次数** | — | **2 次** | 超过不再改道 |
| **行程时间函数** | `α` / `β` | **0.15** / **4.0**【待标定】 | `t = t⁰ · [1 + α·(x)^β]`，`x` 为饱和度 |
| **路径重叠度上限** | — | **0.7** | 候选生成时用 |
| **候选条数** | `K` | **3** | 1 推荐 + 2 备选 |

**确认采纳怎么算**：**一期 = 孪生行为体选择跟随推荐路线**；二期 = 地图匹配显示车辆已进入推荐路线首段。

### 2.5 伪代码（可直接投喂 AI；与手册第 7.6 节一致）

```text
# 状态
background[seg][slot]  # 背景车流（辆/分钟）：一期 = 虚拟检测器实测外推；二期 = 预测模型
reserved[seg][slot]    # 已预约的被引导车辆数
cap[seg][slot]         # 通行能力（辆/分钟）× 因素合成系数
leases[session] = {path, slots, eta, confirmed, expire_at, reroute_count}

def tt(seg, slot, extra=0):                    # 路段行程时间
    x = (background[seg][slot] + reserved[seg][slot] + extra) / cap[seg][slot]
    return t0[seg] * (1 + ALPHA * x ** BETA)

def walk(path, t_start, extra=0):              # 沿路径按时段推进
    slots, t = [], t_start
    for seg in path:
        slot = minute(t); slots.append((seg, slot)); t += tt(seg, slot, extra)
    return slots, t - t_start

def recommend(req):
    cands = k_shortest(req.origin, req.dest, K=3, max_overlap=0.7)
    ok = []
    for p in cands:
        slots, eta = walk(p, now, extra=1)
        if any((background[s][k] + reserved[s][k] + 1) / cap[s][k] > X_SAFE for s, k in slots):
            continue                                   # 约束①：任何时段饱和度不超 X_SAFE=0.85【待标定】
        harm = max_eta_increase(leases_overlapping(slots), extra_on=slots)
        if harm > EPS_HARM:
            continue                                   # 约束②：前车耗时增加不超 EPS_HARM=30s【待标定】
        ok.append((eta, p, slots, harm))
    if not ok:
        return capacity_shortage(suggest=["外围等待", "延后出发", "换停车场"])
    eta, p, slots, harm = min(ok)                     # 满足约束后对本车最快
    reserve(slots); leases[req.session] = lease(p, slots, eta, expire=now + 90)
    return route(p, eta, alternatives=others(cands), why=explain(...), harm_check=harm)

def every_60s():
    release(expired_unconfirmed_leases)               # 90 s 未确认采纳 → 释放
    refresh(background, cap)                          # 实测/预测 + 因素
    for l in sorted(leases, key=entry_time):          # 前车优先
        slots, eta = walk(l.remaining_path, now)
        if eta - l.eta > REROUTE_TH and l.reroute_count < 2 and before_next_branch(l):
            better = best_alternative(l, hysteresis=0.10)
            if better: reroute(l, better)             # 前车再疏导，给后车腾容量
```

### 2.6 占比上限（**附加安全约束，保留**）

时段预约是主机制，**占比上限作为兜底的安全约束**保留：

| 层级 | 上限 |
|---|---|
| 路径级 | K ≥ 3 取 **0.5**；K = 2 取 **0.7**（且两候选耗时差 ≥ 2 min） |
| 路段级 | **0.75** |

> **怎么证明做到了**（TC-17，演示场景二的核心画面）：同一份输入跑对照组（"此刻最快"，普通导航做法）与实验组（预约 + 不伤害 + 再疏导）——
> 实验组中**先进入车辆的到达时间因后车进入而增加 ≤ 30 s**（前车不受影响）；**不新增橙 / 红路段**（拥堵没被转移）；**全网总行程时间低于对照组**。

## 三、定位与地图匹配（`locate.py`）

**实现状态（2026-10-26 更新）**：TC-18 的两个前置（W1 快照在场、真网 WGS-84 几何带显式锚点）
已全部解开，两项判定**真跑**：

- **① 真值直读一致率 1.0（38/38）PASS**；
- **② σ=20 m 噪声匹配正确率 0.8997（260/289）**，未达 90%【demo 目标值】，
  **如实登记 FAIL**——差值全部来自 SZ-018/019 这对**间距 10~13 m 的平行停车场通道**
  （150–210 m 段 17 个错配点；该区单点错配的数学期望约 32%，σ=20 m 噪声下属于
  在线贪心（任务卡原文「HMM-lite、无 Viterbi 回溯」）的**固有局限**，非代码缺陷）。
  相比 dev-debug 时期的 0.7901 已提升 11 个点；继续追需要换全局解码（Viterbi），
  超出任务卡算法范围，按口径纪律不硬凑。

**本轮改动（均不碰打分常量）**：

1. **判分字段对齐真网结构**：`build_geometry` 的 `section` 取不到时回退 `segment_id`
   （真网 `network_junction.json` 的边只有 `segment_id`，两者语义相同——修复后判分
   才真正生效；改前 `matched_section` 恒 None、②项恒 0 分是**判分 bug**）；
2. **起点前看窗口（`LOOKAHEAD_POINTS = 3`）**：起点没有 previous 上下文，平行路单点
   易错（历史上 0-120 m 段 8 个起点错配）；用前 3 个点联合打分选第一条边
   （Viterbi 起点惯例的延迟决策，打分函数与常量原封未动）→ 起点段错配**清零**；
3. **锚点几何产物**：`work/engine/out/real/network_junction_with_anchor.json`
   （真网几何 + `anchor_lonlat` = 本图第一节点真值坐标，非外猜原点；锚点仅作
   局部平面投影原点、纯平移，匹配结果与锚点选取无关）。

**复跑**：
`python work/engine/locate_check.py --vehicles work/twin/out/latest/vehicles.json --network real --geometry work/engine/out/real/network_junction_with_anchor.json --sigmas 10,20,30 --seed 42`
（产物 `out/real/tc18_final.json`；`run.py --sample` 逐字节基线不受影响，已复核）。

**历史留痕（2026-10-19 T4 状态，供追溯）**：样例口径 3/3 只证明链路通、dev-debug 口径
σ=20 m = 0.7901（自造夹具），当时均不得当验收；解除条件见 T4 验收记录 §5。
校验入口：`python work/engine/locate_check.py --vehicles <快照> --network sample --sigmas 10,20,30 --seed 42`。

**两期用同一个函数形状，一期只换输入。**

```text
locate(session_id, position, heading, ts) → {
    segment_id, offset_m, direction, route_progress, match_confidence
}
```

| 项 | **一期（当前）** | **二期** |
|---|---|---|
| 输入 | **孪生真值**（TraCI：所在路段、车道、离路段起点多少米） | **App 定位**（北斗 / GNSS），进围栏后每 5–10 秒上报 |
| 算法 | 真值直读，`match_confidence = 1.0` | **隐马尔可夫地图匹配（HMM）**：把定位点串吸附到路网，得出路段 + 路段内位置 + 行驶方向 |
| 坐标系 | 孪生内部米制坐标，可换算 **WGS-84** | 统一转 **WGS-84**；与高德 GCJ-02、百度 BD-09 的互转**离线内置** |
| 低置信度处理 | 不适用 | `match_confidence < 0.6`【待标定】时**不用于重新规划**，提示"定位不稳定，请确认所在道路" |

**一期要为二期做的准备**：用孪生真值**加噪声**（σ = 10–30 m）生成假定位，**提前把地图匹配模块测出来**。

**验收（TC-18）**：

- 一期 `locate()` 用孪生真值返回的路段与孪生真值**一致率 100%**；
- 对真值加 **σ = 20 m** 噪声后，**路段匹配正确率 ≥ 90%**【demo 目标值】。

**隐私口径（硬）**：`session_id` 是**匿名会话号**，不含身份；**行程结束即删**；App 定位**只服务用户本人本次行程**，**不与摄像头 / 虚拟检测器数据关联**，不给其他司机看。用户拒绝定位时**降级为"手动选所在道路 / 只看路况"，流程不中断**。

## 四、预测接口（`predict.py`，一期 **L0**）

| 项 | 一期 | 二期 |
|---|---|---|
| 做什么 | **L0 已实现（T5，2026-10-19）**：`predict.py` 纯函数 `l0_record`/`build_snapshot` + `predict_cli.py` 产 `out/latest/predict.json`（gitignore 产物，两遍 sha 一致；不写 `segments.json`、不报精度） | L1 机器学习回归（数据满 4 周）→ L2 时空图（数据满 3 个月） |
| 输出 | 每条路段未来 **15 / 30 分钟**的流量与等级，写进 `segments.pred`，`model = "L0"` | 5 / 15 / 30 / 60 分钟，`model = "L1"` / `"L2"` |
| 精度 | **不报任何精度数字**，标 `is_simulated` | 15 分钟 MAPE ≤ 15%、30 分钟 ≤ 20%、预测等级一致率 ≥ 80%【待标定】 |
| 喂给谁 | 演示链路 + 管理端"预测展示" | **填进时段预约表的 `background[seg][slot]`** ——"前后车都不受影响"在真实场景里靠它 |
| 防失控 | — | 连续 3 天误差超标 → 自动退回 L0 并告警；模型版本可回滚 |

**接口形状**：`GET /api/traffic/predict?segment_id=&h=15`（一期 L0；二期 L1/L2，**端点形状不变**）。

> **阶梯替换纪律**：下一级模型**必须比上一级误差低 10% 以上**才替换。

## 五、地图与路网接入（**OSM 拉路网 + 高德底图核对**）

**口径（D7）**：路网拓扑走 **OSM + `netconvert`**；**高德**开放平台（**一期只申请这一家**，2026-10-13 裁定）**只用于底图、POI 与在线人工核对**——它**一般不提供可下载的车道级路网拓扑**，且条款**已明文限制**存储 / 缓存 / **截图** / 衍生数据（[`../../docs/条款核实.md`](../../docs/条款核实.md)：高德 3.5、4.12.3、4.12.7；百度 3.3.2、3.3.3、3.3.4 **同构，一期不启用**）。**核对时不缓存、不落盘、不截图。**

| 事项 | 做法 |
|---|---|
| 路网拓扑 | **OSM 站点切片 → `netconvert`**：**`netconvert` 与 `netedit` 补画归开发A**（产出 `stations/sumo/*.net.xml`）；**本模块只负责 `map_ingest.py`——把 OSM 与 `sumo/*.net.xml` 转成统一图结构 `stations/network.json`（`{nodes, edges, attributes}`）**，并在 T2 补录后写回。**两边不重叠：A 不写 `network.json`，B 不重跑 `netconvert`、不写 `sumo/`** |
| 人工核对 | 池·S 拿**高德底图**逐条比对补录（T2 路段属性核对表），过 **TC-15** |
| 管理端渲染 | **一期大屏不挂第三方底图层**（2026-10-13 起自绘 OSM 路网、ODbL 署名）；池·S 核对用底图**只在线看**。若将来恢复底图层：在线调用 + **保留审图号与「高德地图」标识**（高德 7.7） |
| 坐标系 | 站点包统一存 **WGS-84**；与高德转 GCJ-02、与百度转 BD-09（经 GCJ-02 中转）。**不转的话车的位置会整体偏一条街** |
| 转换算法 | **离线内置**，不要每次调在线接口 |
| 拉取结果 | **必须落盘**（`map_source.json` 溯源），不要每次运行都调 API |
| 主备 | **一期只用高德一家**（2026-10-13 裁定，见下表）；二期若启用第二家：**主用一家 + 另一家交叉校验**，**不要两家同时在线取数**（道路等级与车道数口径会打架） |

### Key 申请进度（**本表由开发B 维护，每周更新**）

> ⚠️ `hubflow` 是 **public 仓库**，Key **绝对不能**写进这里或任何提交的文件。
> Key 只放本地 `.env`（`cp .env.example .env`），规则见 [`docs/开发规范.md`](../../docs/开发规范.md) 第 11 节。
>
> **用途已按 V2.0 收窄**：这些 Key **只用于底图核对与管理端渲染**，**不用于提取路网拓扑**（路网走 OSM）。

| 供应商 | Key 类型 | 用途 | 申请日期 | 状态 | 配额 / 到期 |
|---|---|---|---|---|---|
| 高德（主用） | Web 服务 Key | **底图 / POI 核对**（池·S 打点位与核对路段属性） | 2026-10-11 | **已申请，实测可用**（地理编码 / 静态地图接口通过；Key 只在本地 `.env`） | **【待核实】**（控制台账号类型与配额未核对；一期为人工核对用法，用量远低于免费额度） |
| 高德（主用） | JS API Key | **管理端底图渲染**（一期大屏已改自绘 OSM，留作底图层备用） | 2026-10-11 | **已申请，实测可用**（JS API 2.0 + 安全密钥，本地页面渲染通过） | 同上 |
| 百度（备用 + 校验） | Web 服务 Key | 交叉校验（不用于提取拓扑） | — | **一期不申请（2026-10-13 裁定）**：见下「为什么一期不用百度」 | — |
| 百度（备用 + 校验） | JS API Key | 备用底图渲染 | — | **一期不申请（2026-10-13 裁定）**：同上 | — |

**Key 的安全设置（2026-10-13 记录，Issue #44）**：

| 项 | 现状 | 说明 |
|---|---|---|
| 高德 Web 服务 **IP 白名单** | **未设定**（控制台留空） | 核对是**人工在浏览器 / 本机做**，出口 IP 随机器与网络变动；写死具体 IP 会挡住队友与演示机（高德 `10005 INVALID_USER_IP`），也属于「把某台机器的现状写进团队记录」。**留空唯一代价**是 `10010 IP_QUERY_OVER_LIMIT`（单 IP 超量被暂停），而一期用量被条款锁在「人工逐条核对」量级，摸不到该阈值。**不写任何 IP 值** |
| 高德 Web 服务 **数字签名（`sig`）** | **未启用** | 它是「Key 泄露后别人也用不了」的正解，但每次调用都要算签名——一期是**人工在浏览器里看底图**，启用后自己就没法手工调。防盗改由既有两条防线承担：**Key 只进本地 `.env`** + **public 仓库红线与 `doc_gate` 第 5 组密钥扫描** |
| 高德 JS API **安全密钥** | **已启用** | 2021-12-02 后申请的 JS API Key 必须配合安全密钥使用；已实测通过（本地页面加载 JS API 2.0 成功） |

**为什么一期不用百度**（2026-10-13 裁定，Issue #44；理由原文见该 Issue 运行记录）：

1. **没有消费方**：全仓代码搜不到任何百度 Key 的读取点；两家 Key 在一期的定位本来就是**给人眼看的**（池·S 叠图核对），不是给代码调的——「第二家」只多一双眼睛。
2. **一期已转向自绘 OSM**：大屏 2026-10-13 起不挂第三方底图层，演示站也换成纯 OSM 站区路网；底图核对链路缩到 **T2 一处**，而 T2 的核对列只有「一致 / 不一致 / 待核实」三个取值，**明令不得把底图数据写进任何字段**——交叉校验的产物是一句「不一致 + 原因」，不是数据。
3. **多一家 = 多一份负债**：百度 B-02（商业目的须先付费）/ B-03（禁缓存 / 截图）/ B-05（禁「生成或用于数据库」）/ B-11（不可转授权）与高德 A-03 / A-06 / A-07 / A-04 同构；`条款核实.md` 第 21 条还要求停止使用某家时清理（百度 9.3）并建「地图内容台账」逐处登记。
4. **白名单是纯摩擦**：百度服务端 AK 申请时**强制二选一**——IP 校验（团队无固定出口 IP，只能填 `0.0.0.0/0`，等于没白名单）或 SN 校验（每次调用都要签名，人工核对更麻烦）。两条都不产生任何一期产物。
5. **换供应商解决不了 U-02 / T-04**：若一期被认定为「项目投标 / 后台管理系统」，**两家都得先买技术服务许可**；高德 14.2 的资质排除风险（U-03）百度侧同样存在付费门槛。该风险的正解是队长线下问高德，不是备一把百度的 Key。

> **百度留作二期备选**：二期接外围路况或需要第二来源交叉校验时，按 `docs/条款核实.md` 的 B-01~B-11 与 T-09 重新评估后再申请。

**另有两条支撑信息必须一并落实**（第一周，责任人：队长）：

- [x] **离线与缓存：已核实为「不允许」**（高德 3.5 禁存储 / 缓存 / 抓取；百度 3.3.3 禁脱离服务单独使用或展示；**截图也被明文禁止**）。一期做法：**现场保证联网**；断网时管理端切**自绘 OSM 路网图**。结论与依据见 [`../../docs/条款核实.md`](../../docs/条款核实.md)。
- [x] **兜底**：授权未到位期间用**样例路网 JSON** 占位开发，**不阻塞**。**2026-10-13 收口**：高德（唯一申请方）2026-10-11 已批并实测可用，**不需要启动该兜底**；「两家并行申请，哪家先批用哪家」的表述随「一期只用高德」裁定作废（见上）。

> **本文档 §五 的收口状态（2026-10-13）**：Issue #44（阶段 0 · 0-5）据此关闭——高德两把 Key 在位并实测、`.env` 与密钥扫描门禁通过、进度表四行状态已定、白名单 / 数字签名 / 安全密钥三项设置已记录。**唯一残留**：控制台账号类型与配额未核对（表中标 **【待核实】**），归队长，**不阻塞任何开发**。

### 5.1 真网算路（`--network real`，Issue IKMS11）

> **一句话**：决策引擎不再只跑 7 节点样例网——`--network real` 从**站点范围登记表**读出站点 Z 的
> **61 段真路网（`SZ-###`）**，段长 / 邻接 / 车道 / 限速 / 容量、OD、候选、时段预约、不伤害前车、
> 再疏导、`--compare` 全部在真网上跑；`--sample` 原样保留为**逐字节基线**（一点没动）。

**命令**

```text
# 真网协同推荐(时段容量预约 + 不伤害前车):写 out/real/routes.json,不覆盖样例 out/
python work/engine/run.py --network real
# 真网三组对照(① 不推荐 ② 此刻最快 ③ 协同推荐)+ TC-17 三项对比数据:写 out/real/compare/
python work/engine/run.py --network real --compare
# 接上游 segments 快照(只按 SZ-### 精确匹配;段号对不上就降级并留 note)
python work/engine/run.py --network real --segments work/perception/out/latest/segments_video.json
# 换站:登记表加一条记录 + --site-id,引擎代码一行不改(手册 §8.4 / M1-1)
python work/engine/run.py --network real --site-id <登记表里的 site_id>
# 样例基线(逐字节不变,对照/演示用)
python work/engine/run.py --sample
python work/engine/run.py --sample --compare
# D3 往返代表请求(仅样例;真网 points=[] 时跳过并留痕 d3_skipped: no_pickup_point)
python work/engine/run.py --sample --d3
# 阈值卫生机检(只读;当前站点包预期退出码 1 —— x_safe=0.85 > 判级橙档 0.8,如实报违规)
python work/engine/check_thresholds.py
# 一期 L0 预测(当前值保持):读 segments 快照 → out/latest/predict.json(不写 segments.json)
python work/engine/predict_cli.py --segments work/engine/samples/segments_sample.json
```

> **GZ 冒烟结论（T1，2026-10-19）**：`python work/engine/run.py --network real --site-id guangzhounan`
> 可跑（两遍 sha 一致；`segments_read=708` / 453 节点 / 91 OD；产物落
> `out/real/sites/guangzhounan/`）。TC-17② 在 GZ 上同样 FAIL（新增 8 个橙/红段），
> 根因与样例一致（`x_safe=0.85` > 橙档 0.8），属已知结构性冲突，见 Issue（阈值标定）。

> **真网两种 mode 的产物目录是分开的**（IKMS11 独立审查整改）：默认模式 → `out/real/`，
> `--compare` → `out/real/compare/`。**不能共用同一个 `routes.json` 路径**——否则后跑覆盖前者，
> 下游按固定路径读取时会拿到错 mode 的产物。`--out` 显式传参仍然优先，`run_log.json` 与
> `routes.json` 始终写在同一目录。

**数据从哪来（不写死站点名 / 节点 / 段号 / 坐标）**

| 层 | 文件 | 引擎怎么用 |
|---|---|---|
| 站点范围登记表 | [`work/twin/site-ranges.json`](../twin/site-ranges.json) | 按 `--site-id`（缺省 `default_site`）取 `seg_target`（=61）、`seg_prefix`（=`SZ`）、`out_json`（真网产物路径） |
| 真网产物 | 登记表 `out_json` 指向的 [`network_junction.json`](../twin/netpack/network_junction.json) | 读 `nodes[]`（44）+ `edges[]`（61，含 from/to/length_m/lanes/coords）；校验段数、段号命名空间、端点、长度后建统一图 |
| 方向/车道/贯通性（IKNB9H） | [`network_junction.enriched.json`](../twin/netpack/network_junction.enriched.json)（由 `netpack/topology.py` 生成，**不覆盖原 JSON**） | 优先读；用 `enrichment.source_sha256` 与 raw 对账，**过期直接报错**；缺 enriched 时按 oneway 现推并标 `derived_from_raw` |
| 站点包参数 | [`stations/thresholds.json`](../../stations/thresholds.json) 的 `grading` 组 | 缺字段回落：`speed_limit` → `grading.defaults.v_f_kmh`；`capacity_vph` → 有 `lanes` 按 `lanes × grading.saturation_flow_vph_per_lane`，否则 `grading.defaults.c_vph` |
| 上游指标（可选） | `--segments` 指定的 segments 快照 | 只按 `segment_id` 精确匹配 `SZ-###`；未覆盖的段 `q_vph=0` + defaults 降级；别的命名空间条目**不入响应** |

> **与 `stations/network.json` 的关系**：它仍是 **7 节点 / 17 边 `SEG-###` 占位件**（真值重建归 IKMHMX，
> **本单不手改 `stations/`**）。真网入口读的是登记表指向的真网产物，**不是**这个占位件；占位件继续只服务
> 样例/占位链路。命名空间纪律：**`SZ-###` 只属真网，`SEG-###` 只属样例**——两份产物分开目录，
> 真网产物写出前还有**段号硬校验**，绝不混在一份响应里。

**参数来源逐边可追溯**：真网产物的 `speed_limit` / `capacity_vph` 大量为 `null`（真值等 T2 路段属性核对表补），
引擎**逐边写 `param_source`**，不静默补数：

| 字段 | 真网有值 | 缺失时 |
|---|---|---|
| `length_m` | `network_junction`（几何真值） | **直接报错**（不猜长度） |
| `lanes` | `network_junction` | 保留 `null`（**不补假车道数**，只影响展示） |
| `speed_limit` | `network_junction` | `station_pack:thresholds.grading.defaults.v_f_kmh` |
| `capacity_vph` | `network_junction` | 有车道数 → `derived:lanes×grading.saturation_flow_vph_per_lane`；否则 `station_pack:grading.defaults.c_vph` |

**OD 从真网边界推导**（不手写段号；规则即实现，数据来自真网产物的 `nodes[].boundary_role`）：

1. **边界节点** = `nodes[].boundary_role`（有向出入度：`entry` / `exit` / `both`；含 `topology.py`
   派生的、原 boundary 漏掉的边界，如本站 `N-006`）；没有该字段时退回有向出入度，不再用无向度数 1
   （多出边的边界节点会被无向度数漏掉）；
2. **进场边界** = `entry`（本站 4 个：`N-001`/`N-006`/`N-013`/`N-038`，对应段 `SZ-003`/`SZ-059`/`SZ-055`/`SZ-001`）；
   **离场边界** = `exit`（本站 `N-002`/`N-003`/`N-040`）。`both` 是范围裁剪后**场区内部通道 / 服务道路**的断头
   （如 `N-016`/`N-018`/`N-024`/`N-026`/`N-044`），**不算外围入口**——业主 2026-10-21 口径：
   「那些大道最外面的路段就是起点」；只有整站没有纯 `entry` / `exit` 时才退回 `both`（老图兼容）；
3. 对每个进场边界，行程终点优先级 = ①**站点包落客点映射到的真网节点**
   （`work/engine/inputs/station-landmarks.json`，由 `work/twin/netpack/tools/gen_station_landmarks.py`
   从站点包 `dropoffs` 生成；如 Z 站 `DROP-02` → `N-028`）→ ②**场区内部节点**（所有相邻边 `kind=ramp`）
   → ③全部内部节点（兼容回退）。候选取「**候选路线数最多**」的前 3 个（并列按自由流耗时、节点 id）——
   业主 2026-10-21 口径：「停车场落客点是终点」；候选路线数由真网拓扑 + 站点包
   `max_path_overlap` 与**代码内搜索深度 `CANDIDATE_SEARCH_K`** 算出，所以这是**数据 + 参数推出来的 OD**，
   不是手写；取 3 个是演示 OD
   的覆盖广度（常量 `realnet.OD_DESTINATIONS_PER_ENTRY`，不是判据数值），目的是覆盖各进场方向、并让
   「备选 ≥2」的 OD 对存在（M1-4）；
4. 每个 OD 的 `exit_node` = 从行程终点出发**自由流最快的可达离场边界**——终点是内部节点、出口是边界节点，
   两者必不相同，`departure_route` 才是真实离场路线（TC-12 必现）；
5. 不可达 / 找不到出口的组合**跳过并留痕**（`od_derivation.skipped`），不顺延硬凑；
6. 本站推导结果（2026-10-21 规则 + 方向校正后）：**4 个 OD 对**；默认第一条 **OD-R-001 = `SZ-004`（`N-040` 东侧外围入口）→ `SZ-036` 末端 `N-028`**（`SZ-036` / `SZ-024` 交界，对应站点包 `DROP-02` 停车场北支落客区），其余 3 条为 `SZ-004` / `SZ-055` 到 `N-028` / `N-014` / `N-037`。每个 OD 的需求用 `DEMO_DEMAND_VPH`（=600 辆/小时）**演示假设值**（无上游需求快照，产物标 `demand_source`，**不是实测**）。GZ 站同一规则 + 同批方向校正（367 段）：54 个 OD。
7. **方向校正（2026-10-21，业主复查）**：`build_junction_pack.py` 串同名 way 时会为端点吸附反转几何，但
   `oneway=yes` 未同步翻转，导致吉庆大道整条路单行方向反了（OSM way `1090740692` 实际是 `N-040 → N-022 →
   N-015` 东→西）。`work/twin/netpack/tools/align_oneway_to_osm.py --site-id zhaoqingdong` 按 OSM 节点顺序
   把 14 段（12+2）`oneway` 由 `yes` 改为 `-1`（只改方向，不改几何/段号），进/出口随之变为
   `N-040`/`N-002` 进、`N-001`/`N-003`/`N-038` 出；Z 站方向分布 forward 14 / reverse 14 / bidirectional 33。
   GZ 同批校正 367 段（`--site-id guangzhounan`），方向 forward 297 / reverse 367 / bidirectional 44；GZ 引擎产物 54 条 OD。

**产物（独立目录，不覆盖样例）**

| 文件 | 内容 |
|---|---|
| `work/engine/out/real/routes.json` | **默认模式**：真网协同推荐。`requests[]` 为契约第二节响应体（段号 `SZ-###`，路线额外带 `length_m`）；`network`（**61 段逐段** `length_m` / from-to / `param_source`）、`od_derivation`（OD 规则 / 入口 / 出口 / 跳过）、`segments_source`（上游快照命中与降级）三块可追溯元数据 |
| `work/engine/out/real/run_log.json` | **默认模式**日志：真网统计（61 段 / 44 节点 / OD 数 / 备选数 / reservation 数 / M1-4 自检标志）、参数来源、可复现所需输入 |
| `work/engine/out/real/compare/routes.json` | **`--compare` 模式**：真网三组对照（① 不推荐 ② 此刻最快 ③ 协同推荐）+ `comparison.tc17` 三项数据 + `comparison.treatment` 处置前后三项（TC-09，见下节）+ `capacity_shortage` / 租约释放 / 突发再疏导证据；`network` / `od_derivation` / `segments_source` 同默认模式 |
| `work/engine/out/real/compare/run_log.json` | **`--compare` 模式**日志（三组计数 / TC-17 判据 / `treatment_metrics` 三项摘要 / 再疏导计数） |
| `work/engine/out/routes.json` | **样例基线产物，保持原样**（`--sample` / `--sample --compare` 写这里，逐字节基线） |

> `--out` 可另指目录（**显式传参优先于上面的默认目录**）；`routes.json` 与 `run_log.json` 写同一目录。
> **真网产物不覆盖样例 `work/engine/out/routes.json`**，默认模式与 `--compare` 模式也**互不覆盖**；
> 接口层（`work/assembly/`）要不要切真网数据源是后续前端/接口单的事，**本单不碰 `work/assembly/`**。

**降级与不编数（一律如实记录）**

- 没有 `--segments` 上游快照：全部路段 `q_vph=0` + 站点包 defaults（`segments_source.notes` 写明），
  `--compare` 三组差异只由时段预约占用产生（不调参凑过）；
- 上游快照段号对不上（例如只有旧 `SEG-###` 产物）：**0 命中 → 全量降级**，并列出被忽略的段号
  （`ignored_segment_ids`），**绝不把两套段号混进同一份真网响应**；
- 真网节点没有 `type` 字段：统一按 `intersection`（`network.node_type_source` 注明）；落客/上客点位归
  站点包 `points.json`（真网点位归 IKMHMX / 池·S 踏勘），本单**不编点位**：真网 `points=[]` →
  `arrival_route.dropoff_point` 恒为 `null`（`walk_min` 同为 `null`），**下游按 null 处理，不补假点位**；
- 演示时刻 / 窗口：无上游 `ts` 时用固定常量 `realnet.DEMO_BASE_TS` / `DEMO_WINDOW_SEC`，**不读系统时钟**；
  同一输入连跑两遍 `routes.json` 逐字节一致（确定性硬约束）；
- 口径恒为「**演示数据（模拟）**」：几何来自 OSM 真值，但指标 / 需求 / 时刻都是演示假设值。

**处置前后三项（TC-09，`comparison.treatment`，2026-10-26）**

手册第 17 章要求的效果对比报表 = 三组对照 **+ 处置前后三项**（排队长度峰值 / 拥堵持续时间 /
饱和度和差）。三项**由本引擎在同一评估窗口上现算**——算的是**模拟对照值**（`is_simulated` 恒 `true`，
既**不是**现场实测，也**不是**写死的演示常量）：

- **等长时间窗**：处置前 = 组①（不推荐）、处置后 = 组③（协同推荐），两组跑**同一个**评估窗口
  （同一 `base_ts` / `window_sec` / 车辆群 / 站点包参数），差异只来自推荐机制。**不虚构两个时间段**。
- **对比范围（scope）** = 处置前橙红段 ∪ 处置后橙红段——两侧同一段号集合，分母可比，避免
  「协同推荐把车挪走、自己那边没有橙红段」造成的假优势。
- **三项口径**（原文写在 `comparison.treatment.metrics.*.formula`，下游照抄不改写）：
  - 排队长度峰值：逐时段 `q_veh = max(0, x-1) × capacity_per_slot`；
    `L_q = min(L_seg_m, q_veh / 车道数 × queue_headway_m)`，取 scope 内最大；
  - 拥堵持续时间：逐时段判 `x >= 1.0`（**过饱和的物理定义，不是等级档位**；按等级橙档 x≥0.8 判
    三组整窗都"拥堵"、没有区分度），取最长连续过饱和时段数 × `slot_minutes`；
  - 饱和度和：scope 内各段窗口内最大饱和度之和。
  - `queue_headway_m` 读 `stations/thresholds.json` 的 `grading`（与孪生侧 `METRIC_FORMULAS` 同一出处），
    非正数直接 `SystemExit`，**代码里不写死**。
- **没有对比对象时如实标不可用**：`treatment.available = false` + `unavailable_reason`，三项的
  `before/after/delta` 一律 `null`（**不输出 0 → 0 冒充"完美改善"**）。典型场景：用只有 1 个时段的
  上游快照跑（`--segments work/twin/out/latest/segments_twin.json` 的 `window_sec=60`、1 个 slot），
  窗口内没有任何段进橙红档。
- 真跑（2026-10-26，`--network real --compare`）：`scope = ['SZ-004']`，
  排队峰值 **23.33 → 0.0 m**、拥堵持续时间 **15 → 0 min**、饱和度和 **1.125 → 0.825**；
  样例（`--sample --compare`）：`scope = ['SEG-001','SEG-003','SEG-011']`，
  **23.33 → 0.0 m** / **15 → 0 min** / **2.8958 → 2.3958**。

**再疏导在真网的证据（默认 0 事件 ≠ 复用失效）**

`--network real --compare` **默认**（`DEMO_DEMAND_VPH=600`）的突发再疏导演示是 `events=[] / rerouted_count=0`
——**不是"再疏导没有复用"**，而是该需求水平下突发时刻没有"改道收益超过 `hysteresis`"的在途车：机制照常跑完
一个决策周期、如实返回 0 事件（不编事件）。把需求调高即可看到改道：

```text
$ python work/engine/run.py --network real --compare --demand-vph 1200
exit=0；突发时刻在途 85 辆，封 SZ-002 → 改道 1 辆走 SZ-054
事件在 routes.json 的 comparison.scenario.reroute_demo.events:
  {"session_id":"S-cmp-OD-R-001-0141","eta_before_s":null,"eta_after_s":52.43,
   "reroute":{"count":1,"reason":"前方路段变慢:前方路段封闭(触发阈值 30.0s),改走 SZ-054(原路线已不可通行,改道后剩余耗时 52.4s)"}}
```

> 机制代码与样例 `--sample --compare` 的再疏导**完全同一套**（`reroute.py`，不按 source 分支）；
> 差别只在真网默认需求低、封路时段没有可改道的在途车。TC-17 三项判定用**突发注入前**的统计口径。

**真网自检（真跑摘要，详细记录见 [`DESIGN.md`](DESIGN.md) 第二十一节）**

```text
$ python work/engine/run.py --network real
exit=0；写 out/real/routes.json（约 309 KB）+ run_log.json；读入 61 段 / 44 节点；
4 个 OD（4 个外围进场边界 × 落客点终点 N-028；2026-10-21 规则修正后）；reservation.harm_check.passed=true 4 条；
响应段号全部 SZ-###（硬校验通过）；每条路线带 legs[]（方向/车道/U-turn）

$ python work/engine/run.py --network real --compare
exit=0；写 out/real/compare/routes.json（约 324 KB）+ run_log.json；两种 mode 产物互不覆盖；
TC-17 三项（前车不受影响 / 不新增橙红 / 全网总行程时间下降）全过；
capacity_shortage 与租约释放证据 passed=true；再疏导证据见上一节 --demand-vph 1200

$ python work/engine/run.py --sample / --sample --compare
两次连跑逐字节一致；routes.json 的 sha256 与改造前基线**完全一致**
（IKNB9H 自检锁定：routes c375d902… / run_log 819f297f…）

# 两种真网模式各跑两遍：同一输入两遍 routes.json / run_log.json 逐字节一致
# （IKNB9H 自检 04_engine_real_two_pass 记录 sha256；真网产物因双向段 + 派生边界 OD 数变多，
#  旧 IKMS11 的 12 OD 基线数字已被本轮替换，样例 --sample 基线不受影响）
```

### 5.2 方向 / 车道 / U-turn（IKNB9H，真网路线消费 enriched 图）

**一句话**：路段数据层（`work/twin/netpack/topology.py` → `network_junction.enriched.json`）带
`direction` / 车道三件套 / `u_turn_allowed` / `continuity`；引擎用这张图建**有向遍历边**——
双向段展开正向 + `_rev`，单向段只展开一个方向，掉头只在 `u_turn_allowed=true` 处放行。

| 项 | 口径 |
|---|---|
| 装载 | `realnet.load_network_payload(site)` 优先读 enriched，并用 `enrichment.source_sha256` 与 raw 对账；**过期直接报错**，不拿旧方向算路 |
| 建图 | 双向段：`SZ-###`（forward）+ `SZ-###_rev`（reverse），`section` 仍是 `SZ-###`；单向段只一条；`attributes.forbid_u_turn=true` |
| 算路 | `candidates.dijkstra` 用**边状态** Dijkstra（状态 = 节点 + 上一条边），执行"同段反向立即掉头且 `u_turn_allowed=false` 则禁止"；Yen K 短路同样透传 |
| 路线输出 | `arrival_route` / `departure_route` / `alternatives` 新增 `legs[]`（逐段 `direction` / `lanes` / `u_turn_allowed`）与 `direction_counts`；`segments[]` 仍只有 `SZ-###`（反向边折回 section，不出现 `_rev`） |
| 硬校验 | `realnet.attach_route_topology()` 逐条路线查连续 / 边存在 / 非法掉头；不合法直接 `SystemExit`，不输出错路线 |
| 缺 enriched 时 | 按 oneway + 显式反向对现推方向（`topology_source=derived_from_raw`），不静默假装有数据；GZ 站生成 enriched 后自动切回 |
| 范围 | **只在 `--network real` 生效**；`--sample` 走旧图结构，产物逐字节不变（自检锁定） |
| 全 OD / 可达性 | `python work/engine/topology_check.py` 批量算全部边界 OD + 全部节点对，写 `work/engine/route_matrix.json`；单点算路 `--from N-001 --to N-005`（节点或段号均可） |

**本轮 Z 站结果（2026-10-18 真跑；IKNB9H 时点）**：61 段（33 双向 / 28 单向）、94 条遍历边、9 个进场边界 / 8 个离场边界；
27 个 OD；`route_matrix.json` 覆盖 61/61 段、0 条非法路线；边界 OD 67 对里 48 对可达，19 对如实 `unreachable`
> 2026-10-21 业主口径修正后：进场边界只认 `entry`（4 个）、终点优先落客点映射节点（Z 站 N-028）→ **4 个 OD**；上表的 9/27 为 IKNB9H 历史值。
（单向/边界方向决定的合法不可达，不是错）；样例基线仍逐字节一致。

> **契约口径**：`legs[]` / `direction_counts` 是**追加字段**（不改既有字段、不改 `--sample` 产物）；
> 契约字段裁定人是开发B，前端/接口按需消费，未消费也不影响旧字段。`docs/数据契约.md` 本单不改。

### 5.3 备选路线为什么以前恒为 0：搜索深度 K（2026-10-28）

**业主口径**：「先帮我把备用线路搞定」——页面上四条 OD 的备选常年 0 条，看着像没做。

**根因不在重叠度门槛，在搜索深度**。`stations/thresholds.json` 的 `decision.max_path_overlap = 0.7`
是对「两条路线必须真不一样」的门槛（`candidates.path_overlap` = 共线长度 ÷ 较短者长度）。
真网 Z 站只有 **44 节点 / 94 条有向边 / 61 段**，Yen 取 K=3 时前三条最短路的近邻互相重叠 0.77~0.94，
**全部被这道门槛筛掉**，`len(scored)==1` → 如实写 `no_alternative: true`。

**改法（属"做法"，不改契约、不改站点包）**：手册 §「备选条数」锁定的是「`alternatives ≥ 2` + `no_alternative`
字段形状」，明写「**K 与候选生成算法属做法，可自选并申报**」。因此新增代码常量
`CANDIDATE_SEARCH_K = 30`（`realnet.py` / `run.py` 各一份），实际取值 = `max(站点包 k_candidates, 30)`：

| 搜索深度 | 真网 4 条 OD 里有备选的条数 | 备注 |
|---|---|---|
| K = 3（原样） | **0 条** | 全部 `no_alternative` |
| K = 10 | 1 条（OD-R-001） | OD-R-004 仍被 0.7 门槛筛掉 |
| **K = 30（现值）** | **2 条**（OD-R-001 / OD-R-004） | 备选较推荐绕行 +80~125 m，是真不同走廊 |

- **重叠度门槛没有放宽**，仍是站点包里的 0.7；站点包（`thresholds.json`）一个字节没动。
- OD-R-002（`N-013→N-012`）与 OD-R-003（`N-040→N-012`）在真网拓扑上**唯一通路**（枚举简单路径各只有 1 条），
  任何 K 都出不来 → 按契约如实 `no_alternative: true` + `no_alternative_reason`，
  **不为凑数返回等价路径**（`docs/数据契约.md` 明文禁止）。
- 副作用（已复核，属预期行为变化）：`--sample` 样例网的路由产物中
  `REQ-SAMPLE-0001` 备选 2→6 条、`REQ-SAMPLE-0004` 备选 2→3 条，`--sample` 产物因此**不再逐字节等于改动前**；
  `od_derivation` 与其它字段不变。这是「K 变大」的直接结果，不是回归。
- 复跑：`python work/engine/run.py --network real`（看 `od_derivation.multi_candidate_od_count`，现值 **2**）。


## 六、交付标准

- 引擎代码里**不出现任何站点名、坐标、路名硬编码**；
- **M1-4**：**≥ 3 个 OD 对**出候选路线（**备选 ≥ 2**）并满足**占比约束与不伤害约束**；
- 同一组起终点**连续请求多次，推荐不集中在单一路线**；
- **备选 ≥2 条**（+ 推荐 1 条 = 合计 ≥3 条方案，与 K=3 一致；口径见 [`docs/数据契约.md`](../../docs/数据契约.md)）；
- 只有一条候选时输出 `no_alternative: true` + 原因，**不得为凑数返回等价路径**；
- **TC-17** 三项判定全过（前车不受影响 / 拥堵不转移 / 全网总行程时间下降）。

## 七、站点包与数据契约的归属

**站点包用仓库根目录 `stations/`**，不是 `work/engine/station/`。

理由：站点包是**跨模块共享的配置**——感知与判级要读 `thresholds.json`，前端要读 `points.json`（点位渲染），孪生要读 `points.json` / `demand.json` / `factors.json` / `scenarios.json`。放在 `work/engine/` 下会让其他位置都得跨目录取，与"每个人只改自己目录"的规则冲突。

**你（开发B）定结构，池·S / 池·P 认领填数据。** 结构一旦定下来就是**冻结件**，改要提 Issue。

**判级与阈值也归你**：判级 `work/perception/level.py` 由**开发B** 写（该目录的唯一例外，开发A 不碰）；`stations/thresholds.json` 的**判级参数组 + 决策参数组都由你写**——**这是全仓唯一的"一个文件两组参数"，但只有一个写手**，不存在"两个写手共写一个文件"的情况。判级阈值不得写死在代码里，必须读站点包。

**数据契约**：`segments` / `routes` / `vehicles` 的**字段裁定人是你**。别人要加字段，**当天在 Issue 里说**，由你裁定后升版本号（见 [`docs/数据契约.md`](../../docs/数据契约.md) 第八节）。

## 八、大文件

地图拉取的原始数据放共享盘；**转好的站点配置是小文本，进仓库**（`stations/`）。
