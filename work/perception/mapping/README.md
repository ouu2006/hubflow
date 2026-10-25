# work/perception/mapping · 摄像头 ↔ 通道 ↔ 路段 三段映射（Issue IKMDKY；IKMS1T 起 N 路动态）

> **唯一真值来源**：`camera-segments.json`。**前端**由生成器
> `work/perception/tools/gen_station_channels.py` 产出 `cameraChannels.generated.ts`（页面只 import 生成物，不手写第二份）；
> **后端**（感知服务 meta / 接口层）读同一份登记表。对账脚本：`work/perception/tools/check_camera_map.py`
> （含 `--self-test`：0 / 1 / 61 路放行 + 非法用例拦截，**内存 fixture、不污染正式登记表**）。
> **本表只登记绑定关系，不存任何指标数值。**

## 一、三段是什么

| 段 | 字段 | 含义 | 例子 |
|---|---|---|---|
| 摄像头 | `cam_id` / `cid` | 站点包里的布点编号（地图图钉、页面台账都用它）；条数 N 动态（0 ≤ N ≤ 路段数） | `cam-02` / `C-02` |
| 通道 | `channel_id` | 感知服务的 `stream_id`（= 样本视频文件名去扩展名） | `road2` / `track1` |
| 路段 | `segment_id` | 站点 Z 真路网段号（`SZ-###`，61 段） | `SZ-005` |

**映射纪律（IKMS1T 业主 2026-10-17 口径）**：

- **摄像头总数 N = `cameras` 条数，动态：0 ≤ N ≤ 本站路段数（61）**；**0 路合法**；`has_video_source:false` 仍计入 N；
- **默认一段最多 1 路**（"有多少段路配多少个摄像头"）；同一条路段多路摄像头**本单不启用**，需另开扩展单；
- **一路通道只算一条路段**；`video_streams` 是「有视频源」摄像头的**子集**，**条数任意（0..N）**，不再要求 2 条；
- **摄像头数量 ≠ 样本视频段数**：样本视频仍只有 `road2` / `track1` 两路（本机现状），**不伪造视频流**；
- `has_video_source: false` **不等于**"没有摄像头"，更**不等于**"数据可用"——三件事在页面上分开说（TC-11）；
- **样本视频不是本站现场**：`video_streams[].segment_id` 是**演示映射**（依据写在各条的 `evidence`），真实摄像头接入时按 **IKMHMX** 重做标定与映射；
- 拿不到的值标 `null` / 【待核实】，**不许编段号或坐标**。

## 二、当前登记结果（2026-10-18；6 路为**合法示例**，不是固定值）

| 摄像头 | 段号 | 通道 | 有视频源 |
|---|---|---|---|
| C-01 吉庆大道·西进口 | `SZ-010` | — | 否（本期留空窗） |
| C-02 吉庆大道·中段 | `SZ-005` | `road2` | 是（样本视频回放，非本站现场） |
| C-03 场区出入口 | `SZ-054` | — | 否 |
| C-04 停车场·站门口 | `SZ-019` | — | 否 |
| C-05 停车场·北支 | `SZ-024` | `track1` | 是（样本视频回放，非本站现场） |
| C-06 鼎湖大道·进场 | `SZ-015` | — | 否 |

> 当前 N = 6（≤ 路段数 61），**2 路能对上样本视频**（road2 / track1），其余 4 路如实标「未接入视频源」。
> 换站 / 加摄像头时**只改本表**：N 可以是 0（新站未布点）、1、61（每段 1 路）等任意 0..路段数 的值，
> 生成物行数与页面台账/监控墙都跟着 N 走，代码零改动。
> 依据：`work/perception/out/latest/segments_video.json` 的 `provenance.channel` 记 `road2→C-02`、`track1→C-05`（2026-10-13 运行产物）；
> 该产物里的 `SEG-003 / SEG-004` 属 **7 节点样例网**，不是本站段号，本表不沿用。

## 三、段号命名空间（为什么还有 `SEG-###`）

| 命名空间 | 用在哪 | 状态 |
|---|---|---|
| **`SZ-###`（3 位）** | 站点 Z 真 OSM 路网（61 段）：大屏、接口层、感知映射 | **现役唯一本站段号** |
| `SEG-###` | 7 节点**样例网**：`stations/network.json` 占位件、`work/engine/samples/`、鸿蒙 App fixture | 样例数据专用，**不是本站真网**；保留不改名，避免把样例冒充本站 |
| `SZ-##`（2 位） | 旧 21 段对照包 `stationZ21.*` | 只用于顶栏切换对照，按 netpack README 定稿后删除 |

`check_camera_map.py` 会把 `SEG-###` 的**活跃引用**逐条列出来：允许清单之外的引用即判失败。

## 四、怎么改

1. 先改 `camera-segments.json`（唯一入口）；
2. 跑 `python work/perception/tools/gen_station_channels.py` 重新生成前端通道表（**不要手改生成物**）；
3. 跑 `python work/perception/tools/check_camera_map.py` + `python scripts/doc_gate.py`；
4. 感知服务重启后 `/api/perception/streams` 的每条 meta 会带 `segment_id` / `cam_id` / `cid` / `mapping_status` / `mapping_note`（由 `server.py` 从本表补，不改 `data/monitor/*/meta.json` 数据文件）。

## 五、一期布点规划（Issue IKP5DM）

> 规划表：[camera-plan.json](camera-plan.json) / [camera-plan.md](camera-plan.md)，生成器 `work/perception/tools/gen_camera_plan.py`（`--check` 只校验不写盘）。
> 本登记表 6 条 source ledger 每条都有 `plan_ref` / `plan_version` 指向规划行；规划行用 `source_ledger_cam_id` 回指本表，双向可查。
> 规划表区分两层：`planned=true` 是规划层布点（未来 `points.json` 的 detector，归 IKMHMX），`demo_camera_id` 是演示层 N 段 N 路编号；
> 本表**不扩**到 61/708 条，`video_streams` 仍只有 `road2` / `track1` 两路。

## 六、演示层落页面（2026-10-25 业主口径：路段有多少摄像头，图上/台账/监控墙就有多少）

> 业主 2026-10-25 口径把 §五 的「演示层只编号不上页面」推进为**落页面**：
> **N 段 = N 摄像头 = N 视频**——图钉、感知台账、监控墙都按「源台账 + 演示层」全量渲染。
>
> - **本表（camera-segments.json）仍只有 6 条**：它是**源台账**，不再扩；
> - **演示层**来自 [camera-plan.json](camera-plan.json) 每段一行的 `demo_camera_id`，
>   由 `gen_station_channels.py` 生成 `work/frontend/ui-vue/src/station-packs/demoCameraChannels.generated.ts`
>   （Z 55 条 + GZ 708 条；源台账已登记的段不重复生成，一段最多 1 路）；
> - **点位** = 该段折线上 `offset_m` 处（与 `gen_camera_plan.py` 同一套投影算法，演示布点非踏勘点位）；
> - **画面** = 演示复用：`reuseOf` 按 segment_id 确定性二选一（road2 / track1，规则与前端
>   `SegmentCameraCard.reuseSourceOf` 同式）——是公开样本视频复用，**不是该摄像头自己的视频**；
> - 页面状态五分：`已导出`（自有源）/ `演示复用`（有画面，复用样本）/ `未导出` / `读取失败` /
>   `未接入视频源`（老包无复用）；
> - 真实摄像头 / 真实视频接入仍归 IKMHMX，本表与演示层都不冒充实测。
>
> 自检：`gen_station_channels.py --check`（两份生成物逐字节比对）+ `check_station_data.py`
> （第 ⑨ 项核对「源台账 + 演示层 = 路段数」与段号零悬空）。
