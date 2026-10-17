# work/perception/mapping · 摄像头 ↔ 通道 ↔ 路段 三段映射（Issue IKMDKY）

> **唯一真值来源**：`camera-segments.json`。**前端**由生成器
> `work/perception/tools/gen_station_channels.py` 产出 `cameraChannels.generated.ts`（页面只 import 生成物，不手写第二份）；
> **后端**（感知服务 meta / 接口层）读同一份登记表。对账脚本：`work/perception/tools/check_camera_map.py`。
> **本表只登记绑定关系，不存任何指标数值。**

## 一、三段是什么

| 段 | 字段 | 含义 | 例子 |
|---|---|---|---|
| 摄像头 | `cam_id` / `cid` | 站点包里的布点编号（地图图钉、页面台账都用它） | `cam-02` / `C-02` |
| 通道 | `channel_id` | 感知服务的 `stream_id`（= 样本视频文件名去扩展名） | `road2` / `track1` |
| 路段 | `segment_id` | 站点 Z 真路网段号（`SZ-###`，61 段） | `SZ-005` |

**映射纪律**：
- **一路通道只能算一条路段；一条路段可以有多路通道**（多对一，`rules` 第 1 条）；
- `has_video_source: false` **不等于**"没有摄像头"，更**不等于**"数据可用"——三件事在页面上分开说（TC-11）；
- **样本视频不是本站现场**：`video_streams[].segment_id` 是**演示映射**（依据写在各条的 `evidence`），真实摄像头接入时按 **IKMHMX** 重做标定与映射；
- 拿不到的值标 `null` / 【待核实】，**不许编段号或坐标**。

## 二、当前登记结果（2026-10-17）

| 摄像头 | 段号 | 通道 | 有视频源 |
|---|---|---|---|
| C-01 吉庆大道·西进口 | `SZ-010` | — | 否（本期留空窗） |
| C-02 吉庆大道·中段 | `SZ-005` | `road2` | 是（样本视频回放，非本站现场） |
| C-03 场区出入口 | `SZ-054` | — | 否 |
| C-04 停车场·站门口 | `SZ-019` | — | 否 |
| C-05 停车场·北支 | `SZ-024` | `track1` | 是（样本视频回放，非本站现场） |
| C-06 鼎湖大道·进场 | `SZ-015` | — | 否 |

> 6 路摄像头里 **2 路能对上样本视频**（road2/track1），其余 4 路如实标「未接入视频源」。
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
