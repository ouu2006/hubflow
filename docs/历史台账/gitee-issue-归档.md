# 历史台账：Gitee 侧 Issue（2026-10-14 起）

> **这不是权威文档，是存档。** 权威顺序仍是：手册 / 总纲 / 分工表 / 协作规范（见根 `README.md`）。
> 本文件只回答一件事：**Gitee 时代的单子原文是什么**。GitHub 时代见 [`issue-归档.md`](issue-归档.md)。
> **原文照录，未改口径**；评论按平台返回的时间顺序排列。取数时间：2026-10-16。

## 取回率
- Issue：24/24 条有正文
- 评论：共 26 条（按单分布见下表）

## 索引

| 单号 | 标题 | 状态 | 标签 | 正文 | 评论 |
|---|---|---|---|---|---|
| IKM5T1 | [接口与双端] 大屏地图合并成单渲染器：删「示例路网」只留矢量地图，底图拉不出来也照画路网（L1） | closed | L1, 接口与双端 | 4363 字 | 2 |
| IKM4XX | [接口与双端] 站点包只剩 Z：删除 A 包（含切换器 / README / 兜底收口）（L1） | closed | L1, 接口与双端 | 4063 字 | 1 |
| IKM4TE | [接口与双端] 站点包 Z 的数据补齐：断面 / 点位 / 告警 / 场景 / 分流（先如实空着，本单跟踪）（L1） | open | L1, 接口与双端 | 4472 字 | 0 |
| IKM4KP | [接口与双端] 站点包以 Z 为主：默认包改 Z、删除 B / Y 两个包（含 env / dev 脚本 / README 同步）（L1） | closed | L1, 接口与双端 | 6190 字 | 2 |
| IKM4B4 | [孪生与路况] 站点范围与路段数量按站配置：肇庆东 500 m、广州南可达 2 km；先人工圈定，后期脚本 + AI 辅助确认（L1） | open | L1, 孪生与路况 | 7070 字 | 1 |
| IKLX9B | [接口与双端] 司机端 App 前端先用单文件 HTML 顶替：常规导航版式 + 路线段按站点包 Z 上色（IKLX5Y 后续 · 不做生成路线）（L1） | closed | L1, 接口与双端 | 7391 字 | 2 |
| IKLX5Y | [孪生与路况] 肇庆东站真路网当路况底图：站点包 + 大屏摄像头位置（点开跳感知层 · 只摄像头段上色 · 视频留空窗）（L1） | closed | L1, 孪生与路况 | 6947 字 | 1 |
| IKLR30 | [孪生与路况] 最低配演示：自绘 Y 型路网当路线图，车在图上跑起来（L1） | closed | L1, 孪生与路况 | 5133 字 | 3 |
| IKLOL9 | [接口与双端] SUMO 真实画面接入控制大屏：大屏新增仿真画面面板（二维 · 带角标 · 可灰档）（L2） | closed | L2, 接口与双端 | 6106 字 | 1 |
| IKLOJ6 | [孪生与路况] 「一环五射」SUMO 场景接控制大屏：桥接换网 + 车辆/线路同源（L2） | closed | L2, 孪生与路况 | 6197 字 | 1 |
| IKLOB6 | [孪生与路况] 演示路网「一环五射」入库：画路线 → 导入 SUMO → 场景跑通（仓库内可重建）（L1） | closed | L1, 孪生与路况 | 4989 字 | 2 |
| IKLLXT | [决策与定位 + 判级] PR #82 兜底审遗留五项：--sample 输出口径三处 + 登记口径两处（L1） | closed | L1, 决策与判级 | 2378 字 | 2 |
| IKLLXQ | [接口与双端] 鸿蒙 App 拆分 B：接驳后端与 Web 端（同一套 mock）+ 双端同源举证（L2） | closed | L2, 接口与双端 | 5423 字 | 0 |
| IKLLXL | [接口与双端] 鸿蒙 App 拆分 A：工程骨架 + P0 四页 UI（数据用工程内 fixture，不联网）（L2） | closed | L2, 接口与双端 | 4376 字 | 0 |
| IKLLXG | [接口与双端] 大屏右栏「关联告警」判级回归——#77 迁移时丢了 #75 第④条的等级重映射（L1） | closed | L1, 接口与双端 | 2517 字 | 1 |
| IKLLXD | [接口与双端] 监控大屏窗口可拖拽调宽——主体三栏 + 底部热力带（L1） | closed | L1, 接口与双端 | 5134 字 | 1 |
| IKLLX9 | [接口与双端] 司机端鸿蒙 App：P0 四页 + 绑定一台演示车（数据全用虚拟，双端同源）（L2） | open | L2, 接口与双端 | 4222 字 | 0 |
| IKLLX6 | [接口与双端] 缺陷台账——#66 期间的只读代码盘点发现（契约/确定性/阈值/工程，22 项） | rejected | 接口与双端, bug | 5648 字 | 1 |
| IKLLX4 | [阶段0·0-4] 表格模板实体（T1~T6）下发 + 共享盘物理路径写定（L0 · 系列 S） | closed | L0, 系列S | 4357 字 | 2 |
| IKLLX3 | [W0骨架] T1/T2 转换脚本骨架（表格 → points.json / network.json 属性补录）（L1 · 站点/踏勘） | rejected | L1, 系列S | 4540 字 | 0 |
| IKLLX2 | [阶段0·0-3B] map_ingest.py → network.json + map_source.json（L1 · 站点/踏勘） | closed | L1, 站点与踏勘 | 4793 字 | 2 |
| IKLLWY | [阶段0·0-3A] 站点 OSM → netbuild.py → stations/sumo/*.net.xml（L1 · 站点/踏勘） | closed | L1, 站点与踏勘 | 4756 字 | 1 |
| IKLLT8 | [W1前置·已关闭] PR #79 兜底审确认的 6 条 Sourcery 待办：孪生骨架输入校验与诊断补齐（对应 GitHub 旧 #83） | closed | （无） | 304 字 | 0 |
| IKLIG4 | [文档与合规] 迁移遗留四项收口：成员重建 / ci 路线裁定 / main 保护分支两层配置 / 历史 Issue 取不回的口径 | closed | L1, 文档与合规 | 869 字 | 0 |

---

## Issue IKM5T1 · [接口与双端] 大屏地图合并成单渲染器：删「示例路网」只留矢量地图，底图拉不出来也照画路网（L1）

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | L1 / 接口与双端 |
| 创建 | 2026-10-16T10:30:31+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKM5T1 |
| 指派 | （无） |

### 正文

> 业主 2026-10-16 口径：**大屏地图只留一个**——删掉「示例路网」那个独立地图，**只保留矢量地图**（OpenFreeMap 底图 + 描出的路段），而"示例路网"不再是模式，**退化成矢量地图里的那些路网线条本身**；**功能一项不能少**；重点是**底图拉不出来的时候，路网照样刷新出来**（不受底图加载牵制）。A / B / Y 三个包已删（PR **!20** / **!22**），现在只剩站点包 Z，所以**不再需要"按包切底图"那套**。

| 项 | 值 |
|---|---|
| 难度标签 | **L1** |
| 系列标签 | —（区域开发执行；不进任务池认领、不占 WIP 配额） |
| 区域 | 接口与双端 |
| 发布者 | 接口与双端 owner（本单由业主代该区域发布） |
| 认领 | 留空，评论"认领"即锁定 |
| 关联 | PR **!19**（矢量底图那版：MapLibre + OpenFreeMap）· **IKLX5Y**（站点包 Z / 只摄像头段上色 / 6 路摄像头布点）· **IKLX9B**（三重编码与"未接入视频源"口径）· **IKM4KP / IKM4XX**（删 B/Y、删 A，只剩 Z）· **IKM4B4**（范围与段数按站配置；本单**只读**它的段列表，交接条件见该单评论）· 手册 **§11.2 / §8.4** · 条款核实 **E-11 / E-13** |

## 现状：两个渲染器各写一遍；而且路网被公网底图卡住

中栏「全路段状态」是**一个卡片里两个渲染器**（`DashboardView.vue:838-877`），靠两个标签切 `mapViewMode` —— 不是两个页面，但**两套实现各写一遍**：

| 能力 | `NetMap.vue`（自绘 SVG，「示例路网」） | `MapLibreViewer.vue`（「矢量地图」） |
|---|---|---|
| 车辆动点 D1/D2/D3 | ✅ `:403-411` | ❌ 没有，`DashboardView` 也没传 `vehicles` |
| 悬停浮牌 | ✅ `:443-446` | ❌ 只有 click + 手型 |
| 推荐路线（品牌蓝虚线） | ✅ `:381-389` | ❌ 没这个 prop |
| 三重编码 + 摄像头图例 | ✅ `:454-493` | ❌ 没有图例 |
| 水印（来源口径） | ✅ `:448` | ❌ 没有 |
| 灰轮廓「只摄像头段上色」 | ✅ | ✅ 已有（等价） |
| 摄像头图钉 | ✅ | ✅ 已有（MapLibre Marker） |

**第二个问题（本单的核心）**：`MapLibreViewer.vue:239-258` 是

```ts
new MapLibreMap({ container, style: STYLE_URL })    // STYLE_URL = 公网 OpenFreeMap 样式
map.on('load', () => { addRouteLayers(map); ... })  // 路网层在 load 里才加
```

**公网样式拉不到 → `load` 永不触发 → 连路网层都加不上 → 整块空白**；只有 12 s 后一句提示（`:271-273`），而 `v-if="!ready"` 的覆盖层（`:316-319`）会一直盖着地图。而"示例路网"模式存在的意义恰恰是**断网也能演示** —— 所以删它之前，必须把底图与路网拆开。

## 要产出什么

### 1. 只留一个渲染器：删掉「示例路网」

- 删 `work/frontend/ui-vue/src/views/dashboard/components/NetMap.vue`；
- 删 `DashboardView.vue` 的 `mapViewMode` 与「示例路网 / 矢量地图」两个标签（`:838-855`），中栏只挂一个地图组件；
- `map-tag`（`:835`）与页脚两个分支（`:881-883` / `:885`）**合并成一句**（保留 OSM 署名那句）。

### 2. 功能一项不少（从 NetMap 搬到地图组件）

按上表逐条搬：**车辆动点 / 悬停浮牌 / 推荐路线虚线 / 三重编码 + 摄像头图例 / 水印**；灰轮廓与摄像头图钉已有，不重复实现。

- 图例 / 水印 / 浮牌是 **DOM 覆盖层**，不必塞进 MapLibre；
- 口径继续走 `shared/cameras.ts`（摄像头与 `colorPolicy`）与 `shared/traffic.ts`（等级色 / ci 色阶），**不再复制第二份**；
- 语义纪律照旧：等级色只表拥挤度，**品牌蓝只画「当前/已选」**。

### 3. 底图解耦（**本单的核心判定**）

**判定原文**：**OpenFreeMap 拉不出来（断网 / 超时 / 样式 404）时，路网线照画、不白屏、不被提示层遮挡。**

- 用**本地兜底样式**先建图（如 `{ version: 8, sources: {}, layers: [] }`），路网 source / layer **立刻加**，不等任何公网资源；
- OpenFreeMap 作为**可选底图**：拉它的 style JSON 后与本地兜底**合并成一份 style** 再挂载（或作为独立 source / layer 叠加）——失败就只用兜底那份；
- `ready` 以"**本地样式就绪**"为准，不以公网底图为准；离线/超时提示**只针对底图**，**不许遮挡路网**；
- 保留两处已有的坑修法：`setWorkerUrl`（`:33-40`，否则生产构建底图空白）与署名控件不得遮挡（`:244`）。

### 4. 口径与文档

- 页面**不出现**「实测 / 实时 / 现场」；`is_simulated = true` 照旧；
- OSM 署名两处（底图控件 + 路网）位置与超链接**不变**（E-11 / E-13）；
- `work/frontend/README.md` 里"示例路网 / 矢量地图两个模式"的说法同步改。

## 三 prerequisite

| | 内容 |
|---|---|
| **输入样例** | `work/frontend/ui-vue/src/views/dashboard/{DashboardView.vue, components/NetMap.vue, components/MapLibreViewer.vue}`；`src/shared/{cameras.ts, traffic.ts, demoNetwork.ts}`；站点包 Z（`stationZ.ts` / `stationZ.network.ts`） |
| **输出样例** | 中栏只有一个地图组件（MapLibre 单渲染器）；`NetMap.vue` 已删；底图失败时路网照画；功能清单逐条在位；三张截图 |
| **自检脚本** | `npm run build`（含 `vue-tsc`）+ 仓库根 `python scripts/doc_gate.py` 全绿；**断网模拟**：把样式地址指到不可达 host（或 hosts 屏蔽 `tiles.openfreemap.org`）后刷新，**路网线 + 图钉 + 图例仍在位** |

## 完成判定（**照抄既有条目 + 本单三条专属，不新造编号**）

| 条目 | 原文口径 | 本单怎么算过 |
|---|---|---|
| **手册 §11.2 / 判定 C-2** | 三层 3 页可用，**一项未删** | 中栏只剩一个地图组件，**页面上没有元素消失**（除两个模式标签本身） |
| **M1-7 / 口径红线** | 角标「演示数据（模拟）」100% 命中；`is_simulated` 恒 `true` | 页面不出现「实测 / 实时 / 现场」 |
| **条款核实 E-11 / E-13** | 对外展示 OSM 数据须署名 + 超链接 | 底图控件与路网署名都在位（合并文案**不得吞掉署名**） |
| **本单专属一（只剩一个地图）** | — | 页面没有「示例路网 / 矢量地图」两个标签；中栏只挂一个组件；`NetMap.vue` 已删 |
| **本单专属二（功能一项不少）** | — | 车辆动点 / 悬停浮牌 / 推荐路线 / 图例（四级编码 + 车辆 + 摄像头）/ 水印**逐条在位**（截图） |
| **本单专属三（底图失败仍照画）** | — | 屏蔽 OpenFreeMap 后刷新：**路网线 + 图钉 + 图例照常在位**，不白屏、不被覆盖层遮挡（截图） |

## 依赖谁的什么

- **依赖 IKM4B4 定型的段列表** —— 本单**只读**（`segment_id` / `name` / `kind` / `coords` + `SEGMENT_BASES`），**不改段划分、不新增字段**。交接条件已写进该单评论（段 id 重排要同步 `CHANNELS` / `SEGMENT_BASES` / `recommend`；"范围 X m · 路段 N 条"的**显示位点由该单定，本单合并文案时保留接上**）。
- **不依赖**后端 / SUMO / 桥接服务；**不碰** `work/twin/*`、`work/frontend/tools/twin_preview/*`、站点包的段与指标。
- 对外发布前 **OpenFreeMap 条款与审图号**仍需补核（**不在本单**）。

## 卡在哪里

1. **断网演示必须成立**（本单核心判定）——别把路网与底图绑在同一条加载链上；
2. **功能别搬丢**——搬完对着第 2 节清单逐条点一遍；
3. 只剩 Z 后 `isOsmNetwork()` 恒真，**不要再引入"按包切底图"的分支**；
4. 生产构建那个 worker 坑（`setWorkerUrl`）别动；
5. 卡住 30 分钟在 Issue 里 @队长。

## 交接留痕

认领者在评论里写：**交了哪个文件、对着哪条判定、过没过。**

### 评论（2 条）

**1 · @ozxowx · 2026-10-16T11:22:07+08:00**

## 交接留痕（IKM5T1）

**交了哪些文件**（分支 `task/IKM5T1-single-map-renderer`，PR **!23**）：

| 文件 | 动作 |
|---|---|
| `work/frontend/ui-vue/src/views/dashboard/components/NetMap.vue` | **删除**（「示例路网」自绘视图） |
| `work/frontend/ui-vue/src/views/dashboard/components/MapLibreViewer.vue` | **单渲染器**：底图解耦（本地兜底样式建图 + OpenFreeMap 异步合入）+ 搬入车辆动点 / 悬停浮牌 / 推荐路线 / 图例 + 水印 |
| `work/frontend/ui-vue/src/views/dashboard/DashboardView.vue` | 去 `mapViewMode` 与两个模式标签、单组件挂载、`map-tag` 与页脚两条分支合并成一句 |
| `work/frontend/README.md`、`AppShell.vue`、`main.ts`、`shared/demoNetwork.ts` | 口径与历史记录同步（**仅措辞/注释**） |

**对着哪条判定、过没过**：

| 判定 | 实测 | 结论 |
|---|---|---|
| **专属一（只剩一个地图）** | 模式标签 **0 个**、地图 canvas **1 个**、`NetMap.vue` 已删 | **过** |
| **专属二（功能一项不少）** | 图例全文在位（四级编码 + D1/D2/D3 + 推荐路线 + 摄像头两行 + 灰轮廓说明）、水印在、署名在且 `href` 正确、悬停路段浮牌「SZ-05 缓行 · 摄像头 1 路 · x 0.61(仅孪生链路)」、悬停图钉浮牌「C-01 吉庆大道·西进口 / SZ-01 · 未接入视频源 · 本期留空 · 点击进感知层」、6 个图钉 | **过**（车辆见下） |
| **专属三（底图失败仍照画）** | 把 openfreemap 的 `fetch` 打回失败后刷新：角标「**底图不可用（拉取失败）· 路网照画**」、OpenFreeMap 资源 **0 条**，而 canvas / 6 图钉 / 图例 / 水印 / 署名**全在**，无白屏、无整屏遮罩 | **过** |
| **手册 §11.2 / C-2** | 三栏与其余面板未动 | 过 |
| **E-11 / E-13** | 署名 + 超链接在位；7 组 bounding box 两两不重叠（署名已从右下角挪到左上角，避开底图自带署名控件） | 过 |
| **门禁** | `python scripts/doc_gate.py` 七组全过；`npm run build`（含 `vue-tsc`）exit 0 | 过 |

**两条已知现状（不是本单回归，建议另开单）**：

1. **车辆动点 0 个**：站点包 Z 的 `vehicleBases: []`（业主口径"用路段级着色表达路况"）→ `/api/traffic/vehicles` 返回 0 条。能力（prop + 渲染 + 图例）已保留。
2. **推荐路线恒不显示**：父组件传 `:route-segments="[]"`（**改动前亦然**）；要真画需把 `recommend.arrival_segments / departure_segments` 接进 `DashboardView.vue`。

**与 IKM4B4 的交接**（该单评论里的三条约定）：渲染侧**只读**段列表、未改段划分；"范围 X m · 路段 N 条"的显示位点按约定**保留接上** —— 本单合并文案后，中栏仍留 `map-tag`（工具条）与 `map-caption`（图下注脚）两个文本位，由 IKM4B4 决定写哪一处。

**独立审查**：全新上下文子代理（只给"改动范围 + 4 问"），原始结论与逐条处置见 PR !23 的「审查记录」栏 —— 两条可执行发现：署名与右下角控件重叠（**已修**）、路线高亮按数组引用监听白跑（**已改为按内容监听**）。

**证据截图**（仓库外）：`D:\hubflow\_screenshots\ikm5t1\01-normal-state.png`、`02-basemap-blocked.png`。

**2 · @ozxowx · 2026-10-16T12:16:50+08:00**

## 追加范围（仍然在同一个 PR **!23** 上）：底图开关 + 失败恢复

业主 2026-10-16 追加：「**开设置，底图开关**」。已实现并实测，追加提交 `4d70373`。

### 做了什么

| 位置 | 内容 |
|---|---|
| `src/shared/settings.ts`（新增） | `basemapEnabled` + `restoreSettings()` / `setBasemapEnabled()`，落 `localStorage`（键 `hubflow.settings.basemap`），默认**开**；读不到 / 读坏了静默退回默认值 |
| `src/components/AppShell.vue` | 顶栏新增**「设置」**入口（交互与线路图切换器同款），面板里一个**矢量底图开关** + 口径说明 |
| `src/views/dashboard/components/MapLibreViewer.vue` | 读开关：**关 → 一个底图请求都不发**，把已有底图层撤掉（`setStyle(兜底样式+本组件图层)`）；**开 → 拉底图并合入**。失败态加「**重试**」按钮 + 2s/6s/12s **退避自动重试**（最多三次） |
| `src/views/dashboard/DashboardView.vue` | 地图工具条与图下注脚跟着开关改口径（关掉时**不再**写"底图来源:OpenFreeMap"，页面不撒谎） |
| `src/main.ts` | 挂载前 `restoreSettings()`（否则会先按默认拉一次底图再被设置改回来） |

### 实测（Tabbit / Chromium，`npm run dev` → `http://127.0.0.1:5173/#/dashboard`）

| 状态 | 实测 |
|---|---|
| 初始（开） | 无角标、`mapTag`＝「底图：OpenFreeMap · OSM（拉不到时只画路网）」、OpenFreeMap 资源 **6** 条 |
| 设置面板 | 开关 `aria-checked="true"`；面板文案：开＝底图来自 OpenFreeMap（OpenStreetMap 数据）／关＝只画路网（＝原来的「示例路网」），不发任何底图请求 |
| **关掉** | 角标「**底图已关闭（顶栏「设置」里可开）· 只画路网**」；`mapTag`/注脚同步改写；`localStorage`＝`"0"`；**6 个摄像头图钉仍在** |
| **关掉后刷新** | **OpenFreeMap 资源 0 条**（"不发任何底图请求"这条成立）；路网、图钉、图例、署名全在 |
| 再打开 | 角标消失、OpenFreeMap 资源 6 条、`localStorage`＝`"1"` |
| 拉不到（故障注入） | 角标「底图不可用（拉取失败）· 路网照画」+「重试」；资源 0 条但 6 图钉 / 图例在 |
| **点「重试」** | 仍失败时保持失败态（按钮盒 `{x:527,y:210,w:40}` 前后**完全一致**）；放行后再点 → 角标消失、资源 **6** 条 → 底图恢复 |

**过程中自己踩到并修掉的一个坑**（留个记录）：重试按钮最初在「重试 / 重试中…」之间改文案，按钮宽度跟着变，CDP 端持续判 `element is not stable`，**点了 30 s 点不上**。现改为：按钮**文案固定**、只切 `disabled`（只改透明度），「正在重试…」另起一个 `span`。改后两次点击都一次成功。

### 门禁与举证

- `npm run build`（含 `vue-tsc`）exit 0；`python scripts/doc_gate.py` **七组全过**。
- 截图（仓库外）：`D:\hubflow\_screenshots\ikm5t1\{03-settings-panel,04-basemap-off,05-basemap-on-again,06-basemap-failed-retry,07-retry-recovered}.png`。
- 验证时用的故障注入只注册在**临时页签**里，验证完就**关掉了**（上一轮 IKM5T1 的 `--discard` 同类处理），不会留在你的浏览器里。

---

## Issue IKM4XX · [接口与双端] 站点包只剩 Z：删除 A 包（含切换器 / README / 兜底收口）（L1）

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | L1 / 接口与双端 |
| 创建 | 2026-10-16T09:46:13+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKM4XX |
| 指派 | （无） |

### 正文

> 业主 2026-10-16 口径（**IKM4KP 之后追加**）：**A 包也删掉**——站点包**只留 Z**（肇庆东站 OSM 真路网）。理由：Z 已是主包，A 那份"手写占位示例路网"不再需要。

| 项 | 值 |
|---|---|
| 难度标签 | **L1**（删一个包 + 选择器 / 切换器 / README / 兜底收口） |
| 系列标签 | —（区域开发执行；不进任务池认领、不占 WIP 配额） |
| 区域 | 接口与双端（`src/station-packs/` 归本区域，协作规范 §1） |
| 发布者 | 接口与双端 owner（本单由业主代该区域发布） |
| 认领 | 留空，评论"认领"即锁定 |
| 关联 | **IKM4KP 与其 PR !20**（**本单的前置**：默认包已改 Z、B / Y 已删）· **IKM4TE**（Z 的数据补齐）· **IKM4B4**（范围与路段数量按站配置）· 手册 **§8.4**（换站只改配置） |

## 现状（IKM4KP 之后）

| 位置 | 现状 |
|---|---|
| `src/station-packs/index.ts` | `PACKS = { A, Z }`；`DEFAULT_PACK_KEY = 'Z'`；`activePack()` 兜底 `STATION_Z` |
| `src/station-packs/stationA.ts` | **只剩这一个包文件要删**（A 的路网几何/基线/断面/点位/告警/场景/分流/通道全写在这一个文件里） |
| 顶栏「线路图切换器」 | 按 `packItems()` 自动出项，现在两项（A / Z）——删到只剩一项后**是个只有单个选项的死控件** |
| README §11.1 / §11.3 / §11.2 | 文件表列了 `stationA.ts`；§11.3 是"A / Z 对照"；§11.2 讲 A / Z 之间怎么切 |

## 要产出什么

### 1. 删 A 包

- 删 `src/station-packs/stationA.ts`；
- `index.ts`：删 `STATION_A` import 与 `PACKS.A` 项（`PACKS` 只剩 `Z`）；`DEFAULT_PACK_KEY` 与 `activePack()` 兜底**保持 Z 不变**（已由 IKM4KP 改好）；
- **全仓清悬空引用**：`stationA` / `STATION_A` / "包 A" 的注释与文档（`docs/历史台账/` 归档原文**不动**）。

### 2. 顶栏切换器收口（**本单唯一有行为变化的地方**）

- **只有一个包时把切换器收起来**（`packItems().length <= 1` 不渲染），别留一个只有单项的下拉；
- 建议做法：`AppShell.vue` 里按 `packItems()` 的长度 `v-if`；**执行者可另选**（保留但禁用也行），PR 里说明。
- `index.ts` 的**选择器层本身一个字不删**——手册 §8.4「换站只改配置、不改引擎代码」靠它成立，将来加站还是"加一个包 + 一行 env"。

### 3. 文档同步（只改 `work/frontend/README.md`）

- §11.1 文件表：删 `stationA.ts` 行，`stationZ.ts` 标为**唯一站点包**；
- §11.3 A / Z 对照表：改为**只讲 Z**（或删表 + 一句话现状）；
- §11.2 切站：改成"现在只有一个包；`npm run dev`（:5173）与 `dev:z`（:6895）是**同一个包的两个端口**；将来加站 = 加包 + 一行 env"；
- §11 里其余点名"包 A"的段落（第十二节"演示前浏览器实测"等）**保留为历史记录**，但要在开头那句话里写清"包 A 已于本单删除"。

### 4. 如实记（**不阻塞，但要写进 PR**）

- **A 是数据最全的演示包**：10 路段 / 4 断面 / 落客点 / 候客区 / 告警 / 场景 / 分流 / 车辆基线。删掉之后，"切回有数据的演示站"这条路**没有了**——大屏与决策页会**如实显示"本站无此数据"**（这是 IKM4KP 已确认的口径）。
- 若要演示数据全的那套，**不能再靠切包**：补齐 Z 走 **IKM4TE**（且范围先由 **IKM4B4** 定）。

## 三 prerequisite

| | 内容 |
|---|---|
| **输入样例** | `work/frontend/ui-vue/src/station-packs/{index.ts, stationA.ts, stationZ.ts}` · `src/components/AppShell.vue`（切换器）· `work/frontend/README.md` §11 |
| **输出样例** | `stationA.ts` 不存在；`PACKS` 只有 `Z`；顶栏不再出现线路图切换器；`npm run dev`（:5173）大屏 = 包 Z，行为与 IKM4KP 之后**一致**（这次删的是"另一个选项"，不是默认包）；`npm run build` 与 `python scripts/doc_gate.py` 全绿 |
| **自检脚本** | ① grep 无 `stationA` / `STATION_A` 悬空引用（历史台账除外）；② `PACKS` 键集合 = `{Z}`；③ `npm run build` + `python scripts/doc_gate.py` 全绿 |

```bash
grep -rn "stationA\|STATION_A" work/frontend/ui-vue/src work/frontend/ui-vue/*.json work/frontend/README.md \
  && echo "❌ 还有引用" || echo "✅ 无悬空引用"
node -e "1" # 选择器探针：PACKS 键 = Z；DEFAULT_PACK_KEY = Z；activePack().key = Z（做法照 IKM4KP 那条 headless 探针）
cd work/frontend/ui-vue && npm run build
cd ../../.. && python scripts/doc_gate.py
```

## 完成判定（**照抄既有条目 + 本单三条专属，不新造编号**）

| 条目 | 原文口径 | 本单怎么算过 |
|---|---|---|
| **手册 §8.4 / §21.8（2）第 1 条** | 换站只改配置，**引擎代码零改动** | 选择器层（`index.ts` 的 `activePack` / `setActivePackKey` / `restorePackKey` / `switchPack`）**结构与语义不变**，只是包里少了一项；加站仍是"加一个包 + 一行 env" |
| **`index.ts`（答案只能有一个来源）** | 页面画的包与 mock 发的包必须同一个键 | 浏览器侧与 vite / mock 注入侧仍同为 `Z`；探针复核 |
| **IKM4KP 专属三** | 空字段**如实空着**，不许拿别的包的值填 | 删 A 之后**更没有可借的值**；Z 的空面板如实显示"本站无此数据" |
| **本单专属一（只剩 Z）** | — | `stationA.ts` 不存在、`PACKS` 只有 `Z`、全仓无 `stationA` / `STATION_A` 悬空引用 |
| **本单专属二（切换器不留死控件）** | — | 只有一个包时顶栏**不出现**线路图切换器（或按 PR 说明的替代做法） |
| **本单专属三（默认行为不变）** | — | `npm run dev` 打开仍是包 Z：5 条路段 `SZ-01/03/05/07/12`、矢量底图、6 个摄像头图钉——**与 IKM4KP 之后逐项一致**（删的是选项，不是默认） |

## 依赖谁的什么

- **依赖 IKM4KP / PR !20 先合**：本单的分支从 `task/IKM4KP-station-pack-z-primary` 切出（**叠在它上面**）；PR base 指向那条分支，`!20` 合并后**把本单 PR 的 base 改回 `main`**（或直接由合并顺序解决）。
- **不依赖**：后端、SUMO、桥接服务。
- **不碰**：`work/engine/`、`stations/`、`work/twin/`、数据契约、既有页面逻辑（除 `AppShell.vue` 的切换器那一处）。

## 卡在哪里

1. **别把"删 A"理解成"改默认"**：默认包已是 Z（IKM4KP），本单删的是**另一个选项**——浏览器实测的期望值是"**和 IKM4KP 之后一模一样**"，任何肉眼可见的变化都说明改错了地方。
2. **选择器层不许删**：它是手册 §8.4 判定的载体。只删"包"，不删"选择包的机制"。
3. **历史文档不动**：`docs/历史台账/`（issue / pr 归档）里大量"包 A"记录是归档原文。
4. 卡住 30 分钟在 Issue 里 @队长。

## 交接留痕

认领者在评论里写：**交了哪个文件、对着哪条判定、过没过。**

### 评论（1 条）

**1 · @ozxowx · 2026-10-16T09:52:59+08:00**

**交接留痕**（IKM4XX，执行者：Agent）

| 项 | 值 |
|---|---|
| 分支 / 提交 | `task/IKM4XX-station-pack-z-only` **已推送** @ **`df9c092`**（**叠在 IKM4KP 的 `2a23b54` 之上**） |
| **PR** | **[!21](https://gitee.com/ozxowx/hubflow/pulls/21)** —— base 指向 `task/IKM4KP-station-pack-z-primary`（**请先合 !20**，再把 !21 的 base 改回 `main`） |
| 交了哪个文件 | 13 文件、**+72 / −597**：删 `src/station-packs/stationA.ts`（−545）+ `index.ts` 去 A 注册；`AppShell.vue` 加 `v-if="packList.length > 1"`；`work/frontend/README.md` §11.2 / §11.3 / §11.4 改写 + §12 起历史标记；`app-html/README.md`、`.env.z`、`main.ts`、`vite.config.ts`、`mock/traffic.ts`、`shared/cameras.ts`、`shared/demoNetwork.ts`、`shared/demoDecision.ts`、`DashboardView.vue` 注释同步 |
| 对着哪条判定 | 专属一（只剩 Z）· 专属二（切换器不留死控件）· 专属三（默认行为不变）· 手册 §8.4（选择器层保留）· IKM4KP 专属三（空字段如实空） |
| 过没过 | **过**（证据见下） |

## 实测证据

```text
① 选择器探针（headless import station-packs/index.ts）
   PACKS 键: Z          DEFAULT_PACK_KEY: Z        默认包: Z / 肇庆东站
   切换器条目数: 1      localStorage 残留 'A' → restorePackKey -> Z | activePack -> Z

② 悬空引用：src / 配置 / 两份 README grep stationA|STATION_A → ✅ 无命中（docs/历史台账 为归档，未动）

③ 浏览器实测（Tabbit，:5173 真实页面）
   线路图切换器节点数 = 0        ← 本单唯一的行为变化，按预期收起
   站点 chip = 肇庆东站
   路段 id = SZ-01 / SZ-03 / SZ-05 / SZ-07 / SZ-12（无 SEG-* 串味）
   页脚 = 底图来源:OpenFreeMap(OpenStreetMap 数据,ODbL) · 署名见地图内 · 不缓存瓦片 · 路网:路网几何为真值（OSM 切片）
   → 除"切换器没了"以外，逐字与 IKM4KP 之后一致

④ npm run build（vue-tsc + vite build）通过 · python scripts/doc_gate.py 7/7 通过
```

**快速独立审查**（全新上下文子代理，只给「改动范围 + 4 问」）→ **4 问全过，未发现可执行问题**；两条非阻塞备注的处置写进了 PR 的「审查记录」栏：
① `README` 引用的 IKM4TE / IKM4B4 不在 `docs/历史台账/issue-归档.md` —— **不改**（归档只收已归档的单，在办单以 Gitee 为准）；
② 审查时改动尚未提交 —— **已落提交 `df9c092`**（提交后 stat 与审查者所看**逐字一致**）。

## 如实记（不阻塞）

**A 是数据最全的演示包**（10 路段 / 4 断面 / 落客点 / 候客区 / 告警 / 场景 / 分流）。删掉之后「切回有数据的演示站」这条路**没有了**——大屏与决策页**如实显示"本站无此数据"**（IKM4KP 已确认的口径），补齐走 **IKM4TE**（范围先由 **IKM4B4** 定）。

## 未做

- 合并（作者不得合自己的 PR；请兜底审三人任一）；
- 本单未截图（页面变化只有"切换器消失"一项，已用 DOM 断言 `节点数 = 0` 证明）——要截图我补。

---

## Issue IKM4TE · [接口与双端] 站点包 Z 的数据补齐：断面 / 点位 / 告警 / 场景 / 分流（先如实空着，本单跟踪）（L1）

| 项 | 值 |
|---|---|
| 状态 | open |
| 标签 | L1 / 接口与双端 |
| 创建 | 2026-10-16T09:39:27+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKM4TE |
| 指派 | （无） |

### 正文

> 业主 2026-10-16 口径：站点包**以 Z 为主**（**IKM4KP**：默认包改 Z、删 B / Y）。Z 现在是**薄包**，一批字段是空的——**先如实空着**（**不许**拿包 A 的演示值去填）。**本单跟踪这些空字段的补齐**；坐标与范围**以 IKM4B4 定下来的范围为准**。

| 项 | 值 |
|---|---|
| 难度标签 | **L1**（多处数据补齐；可拆子单，见"建议的拆法"） |
| 系列标签 | —（区域开发执行；不进任务池认领、不占 WIP 配额） |
| 区域 | 接口与双端（`src/station-packs/` 归本区域，协作规范 §1） |
| 发布者 | 接口与双端 owner（本单由业主代该区域发布） |
| 认领 | 留空，评论"认领"即锁定 |
| 关联 | **IKM4KP**（本单的前置口径：Z 为主包、空字段如实空着）· **IKM4B4**（站点范围与路段数量按站配置——**范围先定，坐标才有依据**）· **IKLX5Y**（Z 包的来历：21 段 + 6 路摄像头）· 手册 **§11.2**（三层 3 页）· **M1-10 / TC-20**（数据同化只灌 `boundary` 断面）· **TC-14**（场景同输入跑三遍）· **T1 / T2** 表格（池·S 填，共享盘）· 口径红线（不得把模拟值说成实测） |

## 现状（实测 2026-10-16，`main` @ `a4df34e` + IKM4KP）

| 字段 | Z 现状 | 是"刻意空"还是"缺口" |
|---|---|---|
| `vehicleBases: []` | 空 | **刻意**——包内注释写明业主口径"用路段级着色表达路况，不画车辆小球"→ **不在本单** |
| `segmentBases`（21 段里只有 5 条） | 只给摄像头覆盖段 | **口径使然**（`colorPolicy: 'camera-covered'`）→ **不在本单** |
| `sections: []` | 空 | **缺口**——断面是判级与数据同化的前提（M1-10 / TC-20） |
| `dropoffs: []` / `zones: []` | 空 | **缺口**——落客点 / 候客区（对应 T1 点位表） |
| `alerts: []` | 空 | **缺口**——大屏右栏「关联告警」与底部告警条无内容 |
| `scenarios: []` | 空 | **缺口**——场景回放与效果对比（TC-14） |
| `diversion: {}` / `seedDispatch: {}` | 空对象 | **缺口**——决策层分流建议（现只有 `diversionFallback` 占位） |
| `assimilation: []` | 空 | **缺口**——依赖 `sections` 先落地 |

> mock 侧实测：`GET /api/traffic/segments` 出 **5 条**（SZ-01 / 03 / 05 / 07 / 12），左栏「选择监控」与右栏路段列表即这 5 条。

## 要产出什么

### 1. 断面（`sections`）——**本单项里最要紧的一条**

- **`boundary` / `internal` 必须分开**，且 `role` 逐条标对：**数据同化只灌 `boundary`**，`internal` 一律不许挂校准器（**TC-20 第②项**）。
- ⚠️ **边界断面清单要先由队长签字冻结**（手册 §1.4 阶段 0 第⑧条 / **M1-10 前置**）——**本单不自定**这条口径，只按冻结清单落进站点包。
- 落在 Z 上的断面，坐标必须在 **IKM4B4** 定下来的范围内。

### 2. 点位（`dropoffs` / `zones`）

- 来源是 **T1 点位表**（池·S 填，共享盘）→ `stations/points.json` → 站点包。**表格是唯一入口**，不许绕过表格手改（开发规范第 7 节）。
- 缺数据如实在表里标 **【待核实】**，**不许编一个数**。

### 3. 告警（`alerts`）与场景（`scenarios`）

- 告警：演示剧本要能对上大屏「关联告警」与告警四态；**判级取当前路段快照**，不复用预置 `level` 的旧口径（那是已修过的老缺陷，见 `work/frontend/README.md` 第十二节第 4 条）。
- 场景：按 **TC-14** 能做到"同输入跑三遍可对比"。

### 4. 分流（`diversion` / `seedDispatch`）

- 决策层「建议往哪条路分流」取决于本站路长什么样（`shared/demoDecision.ts` 已改成从包读）——补 Z 的那份，保留 `diversionFallback` 的兜底位。

### 5. 口径要求（**缺一不通过**）

- 全链数值仍标**演示数据（模拟）**（`is_simulated: true`）；**不得**说成实测、**不得**出现「实测 / 实时 / 现场」；
- **不许**拿包 A 的演示值直接搬进 Z（IKM4KP 的专属判定三）——要么按表填、要么如实留空；
- 页面空面板一律**如实显示"本站无此数据"**，不白屏、不撒谎。

## 三 prerequisite

| | 内容 |
|---|---|
| **输入样例** | `work/frontend/ui-vue/src/station-packs/stationZ.ts`（现状：空字段在哪几行）· `stationA.ts`（**形状参照，不是数值来源**）· `stations/points.json` / `stations/network.json`（形状参照）· `docs/表格模板说明.md` T1 / T2 列定义 · `docs/数据契约.md` 第六节 |
| **输出样例** | `stationZ.ts` 补上 `sections` / `dropoffs` / `zones` / `alerts` / `scenarios` / `diversion` / `assimilation`；大屏三页相应面板出数（或如实显示"本站无此数据"）；`npm run build` 与 `python scripts/doc_gate.py` 全绿 |
| **自检脚本** | ① `npm run build`（`vue-tsc`）通过；② `python scripts/doc_gate.py` 全绿；③ 每条数值能指回 T1 / T2 的某一版（表格唯一入口）；④ `grep -rn "实测\|实时\|现场"` 在页面上零命中 |

## 完成判定（**照抄既有条目 + 本单三条专属，不新造编号**）

| 条目 | 原文口径 | 本单怎么算过 |
|---|---|---|
| **TC-20 第②项** | **`internal` 断面一律不许挂校准器**，边界断面是数据同化唯一入口 | Z 的 `sections` 里 `internal` 的 `reason` 逐条写清；`boundary` 才允许同化 |
| **M1-10** | 要有 `role: "boundary"` 的上游边界断面才谈得上数据同化 | 按**队长冻结的边界断面清单**落进 Z，条目数一致 |
| **TC-14** | 场景二同输入跑三遍可对比 | Z 的 `scenarios` 至少一条能三遍对比 |
| **IKM4KP 专属三** | 空字段**如实空着**，不许拿 A 的演示值填 | 本单补齐的每一条都能指回表 / 裁定记录；指不回的宁可不填 |
| **口径红线** | 不把模拟值说成实测 | 页面不出现「实测 / 实时 / 现场」；新增数值一律标演示 |
| **本单专属一（断面 role 正确）** | — | `boundary` / `internal` 逐条可核，且与冻结清单一致 |
| **本单专属二（点位来自 T1）** | — | `dropoffs` / `zones` 的每一条都能指回 T1 的某一行 |
| **本单专属三（范围一致）** | — | 所有点位 / 断面坐标落在 **IKM4B4** 配置的 `range_m` 范围内（超出的逐条写明理由） |

## 依赖谁的什么

- **依赖 IKM4B4（范围与路段数量按站配置）**：**范围先定**，点位与断面才有坐标依据——**范围未定就开工 = 返工**。
- **依赖队长**：**边界断面清单签字冻结**（M1-10 / TC-20 前置）。
- **依赖池·S**：T1 / T2 表格（共享盘）——**表格是唯一入口**。
- **不依赖**：后端、SUMO、桥接服务；**不碰** `stations/` 下的 JSON 手改、`work/engine/`、数据契约。

## 卡在哪里

1. **顺序不能反**：范围（IKM4B4）→ 断面清单（队长签字）→ 点位（T1）→ 站点包。跳着做必返工。
2. **`vehicleBases` 与"只摄像头段有基线"不是缺口**：前者是业主口径（不画小球），后者是 `camera-covered` 口径的必然结果——**别顺手"补"这两项**，补了就是改口径，另开单。
3. **表格唯一入口**：`stations/` 下的 JSON 不许手改；表格转换脚本按开发规范第 7 节（可重建、两次一致）。
4. **不许编数**：拿不到的数标【待核实】，**不许拿别的包的演示值顶**。
5. 卡住 30 分钟在 Issue 里 @队长。

## 建议的拆法（本单偏大，执行者可拆）

| 子单 | 内容 | 前置 |
|---|---|---|
| ① 断面 | `sections`（boundary / internal）+ `assimilation` | 队长冻结清单 + IKM4B4 |
| ② 点位 | `dropoffs` / `zones` | T1 表 + IKM4B4 |
| ③ 告警 / 场景 | `alerts` / `scenarios` | 无（可先做） |
| ④ 决策层 | `diversion` / `seedDispatch` | ① ② 就位后 |

## 交接留痕

认领者在评论里写：**交了哪个文件、对着哪条判定、过没过。**

### 评论（0 条）

（无评论）

---

## Issue IKM4KP · [接口与双端] 站点包以 Z 为主：默认包改 Z、删除 B / Y 两个包（含 env / dev 脚本 / README 同步）（L1）

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | L1 / 接口与双端 |
| 创建 | 2026-10-16T09:20:26+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKM4KP |
| 指派 | （无） |

### 正文

> 业主 2026-10-16 口径：**站点包以 Z 为主**——**默认包从 A 改成 Z**（大屏打开就是肇庆东站 OSM 真路网 + 6 路摄像头），**B / Y 两个包删掉**（不再需要"第二个虚构示范站"和"手绘 Y 型"这两套示意路网）。**A 包保留**（可切换的次包）。

| 项 | 值 |
|---|---|
| 难度标签 | **L1**（删两个包 + 改默认 + 同步 env / dev 脚本 / README） |
| 系列标签 | —（区域开发执行；不进任务池认领、不占 WIP 配额） |
| 区域 | 接口与双端 |
| 发布者 | 接口与双端 owner（本单由业主代该区域发布） |
| 认领 | 留空，评论"认领"即锁定 |
| 关联 | 手册 **§8.4**（换站只改配置、不改引擎代码）· **IKLX5Y**（站点包 Z 的来历）· **IKLR30**（Y 型包的来历，**本单删除其前端产物**）· **IKLOJ6 / IKLOB6**（B 包「一环五射」的来历，**同上**）· **IKM4B4**（Z 的范围与路段数量按站配置）· `docs/协作规范.md` §1（`station-packs/` 归接口与双端） |

## 现状（实测 2026-10-16，`main` @ `a4df34e`）

| 位置 | 现状 |
|---|---|
| `work/frontend/ui-vue/src/station-packs/index.ts` :17-24 | `PACKS = { A, B, Y, Z }`；`DEFAULT_PACK_KEY = 'A'` |
| 同文件 :12-13、:19-20 | `import { STATION_B } from './stationB.ts'` / `STATION_Y from './stationY.ts'` |
| `src/main.ts` :15 | 兜底 `?? 'A'` |
| `index.ts` :82 | `activePack()` 兜底 `?? STATION_A` |
| `package.json` :12、:16 | `dev:y`（`vite --mode y`）、`dev:station2`（`vite --mode station2`） |
| 磁盘 | `.env.y`（`VITE_STATION_PACK=Y` :6890）、`.env.station2`（`=B` :6880） |
| `work/frontend/README.md` :369、:383、:386、:416-417、:505 | 点名 B / Y 的段落与跑法 |
| 其它文档 | `docs/历史台账/`（issue 归档 / pr 归档）里有大量 B / Y 记录——**归档原文照录，本单不动** |

**Z 是"薄包"，切它当主包后一批面板会空**——这是**如实口径**，不是缺陷（业主已确认：**先如实空着，数据补齐另开单**）：

| 字段 | Z 现状 | 影响 |
|---|---|---|
| `sections` / `dropoffs` / `zones` | `[]` | 断面、落客点、候客区面板无数据 |
| `alerts` / `vehicleBases` / `seedDispatch` / `diversion` | `[]` / `[]` / `{}` / `{}` | 告警、车辆、预约/分流相关面板无数据 |
| `scenarios` / `assimilation` | `[]` / `[]` | 场景回放、数据同化面板无数据 |
| `segmentBases` | **只有 5 条**（摄像头覆盖段） | 其余 16 段按 `colorPolicy: 'camera-covered'` 画灰轮廓 + 数据不可用档——**这是本站既定口径** |

## 要产出什么

### 1. 删掉 B / Y 两个包（代码侧）

- 删 `src/station-packs/stationB.ts`、`stationB.network.ts`、`stationY.ts`、`stationY.network.ts`（4 个文件）；
- `index.ts`：删 4 行 import 与 `PACKS` 里的 `B` / `Y` 两项；
- **兜底改到 Z**：`DEFAULT_PACK_KEY = 'Z'`、`activePack()` 的 `?? STATION_A` → `?? STATION_Z`、`main.ts` 的 `?? 'A'` → `?? 'Z'`。

### 2. env 与 dev 脚本同步（**最容易漏，漏了就出"对不上的画面"**）

- 删 `.env.y`、`.env.station2`；`package.json` 删 `dev:y` / `dev:station2`；
- ⚠️ **两处默认值必须同时改**：浏览器侧（`main.ts`）与 vite / mock 注入侧（`vite.config.ts` 读 `VITE_STATION_PACK` 后在装配期注入 mock 中间件）。**只改一处**就会出现「页面画 Z 的路网、mock 发 A 的基线」——这正是 `index.ts` :4-9 那条"答案只能有一个来源"的既有口径要防的事。
- 旧的 `localStorage['hubflow.stationPack']` 可能还存着 `'B'` / `'Y'`：`restorePackKey()` 已有 `PACKS[k]` 校验，未知键落回注入值——**核对一遍这条路径仍然生效**（别再删出个白屏）。
- `dev:z`（`vite --mode z`，:6895）**保留**：它现在是"同包不同端口"，与 `npm run dev`（:5173）可并存对照。

### 3. 文档同步（只改 `work/frontend/README.md`）

- 站点包清单表：删 B / Y 两行，把 **Z 标为默认 / 主包**（`npm run dev` → 5173）；
- 删 `npm run dev:station2` / `npm run dev:y` 的跑法与端口说明（:383、:386）；
- :416-417、:505 里点名 B / Y 的段落改写或删除；
- **`docs/历史台账/` 不动**（归档原文照录）；手册 §8.4 / §21.8（2）的"第二站"判定清单是**通用口径**，不点名 B / Y，**不改**。

### 4. 顺带核对（不改口径）

- `src/shared/demoNetwork.ts` :8、`src/shared/demoDecision.ts` :7 的注释里点名了 `stationB.ts`——改成不点名（或指 Z），别留悬空引用；
- 顶部栏「线路图切换器」按 `packItems()` 自动出项——**删完应只剩 A / Z 两项**，实测确认。

## 三 prerequisite

| | 内容 |
|---|---|
| **输入样例** | `work/frontend/ui-vue/src/station-packs/{index.ts, stationA.ts, stationZ.ts}`、`package.json`、`vite.config.ts`、`src/main.ts`、`.env.z`（照它写新默认）、`work/frontend/README.md` 第 368-390 行 |
| **输出样例** | 4 个包文件与 2 个 env 文件不存在；`npm run dev` 打开大屏 = **站点包 Z**（站名肇庆东、路网 21 段 SZ-01…SZ-21、6 个摄像头图钉、默认矢量底图）；切换器只剩 A / Z；`npm run build` 与 `python scripts/doc_gate.py` 全绿 |
| **自检脚本** | 见下节。**核心两条**：① 全仓 grep 不到 `STATION_B` / `STATION_Y` / `stationB` / `stationY`（`docs/历史台账/` 除外）；② 默认包在**浏览器侧与 mock 侧取到同一个键** |

```bash
# ① 没有悬空引用（历史台账是归档原文，明确排除）
grep -rn "stationB\|stationY\|STATION_B\|STATION_Y" \
  work/frontend/ui-vue/src work/frontend/ui-vue/*.ts work/frontend/ui-vue/*.json \
  work/frontend/README.md && echo "❌ 还有引用" || echo "✅ 无悬空引用"

# ② 文件与脚本确实没了
test ! -e work/frontend/ui-vue/src/station-packs/stationB.ts \
  && test ! -e work/frontend/ui-vue/src/station-packs/stationY.network.ts \
  && test ! -e work/frontend/ui-vue/.env.y && test ! -e work/frontend/ui-vue/.env.station2 \
  && echo "✅ 4 包文件 + 2 env 已删"
node -e "const p=require('./work/frontend/ui-vue/package.json').scripts; \
  console.log(p['dev:y']||p['dev:station2'] ? '❌ 脚本还在' : '✅ dev:y / dev:station2 已删')"

# ③ 默认包一致（浏览器侧与 vite/mock 注入侧都取 Z）
grep -n "DEFAULT_PACK_KEY" work/frontend/ui-vue/src/station-packs/index.ts
grep -n "VITE_STATION_PACK" work/frontend/ui-vue/src/main.ts work/frontend/ui-vue/vite.config.ts

# ④ 构建 + 门禁
cd work/frontend/ui-vue && npm run build
cd ../../.. && python scripts/doc_gate.py
```

## 完成判定（**照抄既有条目 + 本单三条专属，不新造编号**）

| 条目 | 原文口径 | 本单怎么算过 |
|---|---|---|
| **手册 §8.4 / §21.8（2）第 1 条** | 换站只改配置，**引擎代码零改动** | 删包只动 `station-packs/`、env、脚本与 README；`views/` / `shared/` 的**逻辑一行没改**（只改注释里的悬空点名） |
| **`index.ts` :4-9（答案只能有一个来源）** | 页面画的包与 mock 发的包必须是**同一个键** | 浏览器侧与 mock 注入侧的默认值**同时**为 Z；页脚 `packNote()` 打出的键 = `GET /api/traffic/*` 用的包 |
| **M1-7 / 口径红线** | 模拟值不许说成实测 | Z 的"几何为真值（OSM）、指标为演示数据（模拟）"沿用；本单**不新增**任何数值 |
| **本单专属一（删干净）** | — | B / Y 的 4 个包文件与 2 个 env 不存在；`dev:y` / `dev:station2` 不存在；`src/` 与 `work/frontend/README.md` 里无悬空引用（`docs/历史台账/` 除外） |
| **本单专属二（Z 为主包）** | — | `npm run dev`（:5173）打开就是 Z：站名肇庆东、21 段、6 个图钉、默认矢量底图；顶部切换器只剩 A / Z |
| **本单专属三（薄包如实空）** | — | Z 的空字段面板**如实显示"本站无此数据"**，**不得**拿 A 的演示值去填、**不得**为此新增编造数值（补齐另开单） |

## 依赖谁的什么

**无依赖。** 输入全在仓库内，不联网、不装依赖、不动后端与数据契约。

- **不碰**：`work/engine/`、`stations/`、`work/twin/`（netpack 与 Z 的几何无关，Z 的几何文件 `stationZ.network.ts` **保留**）、感知层与决策层逻辑。
- **`docs/历史台账/` 不动**（归档原文照录）；
- **Z 的数据缺口不属本单**（sections / dropoffs / zones / alerts / vehicleBases / scenarios / assimilation）——**另开单**。

## 卡在哪里

1. **两处默认值必须同时改**（第 2 条）：只改浏览器侧会出现「页面画 Z、mock 发 A」的错位画面。改完**必须**用页脚 `packNote()` 与任意一个 `/api/traffic/*` 响应对一遍包键。
2. **localStorage 残留旧包键**：老浏览器里可能存着 `'B'` / `'Y'`。`restorePackKey()` 的 `PACKS[k]` 校验本来就会落回注入值——**实测一次**（手工把 localStorage 设成 `'Y'` 再刷新，应落回 Z，不白屏）。
3. **薄包不是缺陷**：Z 的空面板**如实空着**（业主已确认）；**不要**为了让页面好看把 A 的演示数据搬进 Z——那是另一单，且会违反"几何真值 / 指标演示"的分开口径。
4. **别顺手删 A**：业主只点名删 B / Y；A 保留为可切换次包（它是断网/占位兜底，也是演示 mock 数据最全的一份）。
5. **Y 型与 B 包的来历单不做历史改写**：IKLR30 / IKLOJ6 / IKLOB6 已关闭，删除其前端产物不影响那些单的结论；**不要**回头改已归档的 issue / pr 归档文本。
6. 卡住 30 分钟在 Issue 里 @队长。

## 交接留痕

认领者在评论里写：**交了哪个文件、对着哪条判定、过没过。**

### 评论（2 条）

**1 · @ozxowx · 2026-10-16T09:26:19+08:00**

**交接留痕**（IKM4KP，执行者：Agent）

| 项 | 值 |
|---|---|
| 分支 / 提交 | `task/IKM4KP-station-pack-z-primary` · `80bffb6`（**未推送**，等业主定） |
| 交了哪个文件 | 13 个：`station-packs/index.ts`（默认包 Z、注册表只剩 A / Z、`activePack()` 兜底改 Z）/ `src/main.ts` / `vite.config.ts`（**两处兜底同为 Z**）；删 `stationB.ts`、`stationB.network.ts`、`stationY.ts`、`stationY.network.ts`、`.env.station2`、`.env.y` 与 `package.json` 的 `dev:station2` / `dev:y`；`shared/demoNetwork.ts`、`shared/demoDecision.ts` 去掉注释里的悬空引用；`work/frontend/README.md` §11.2 ~ §11.4 改写为"以 Z 为主"（切站方式 / A-Z 对照 / 包 Z 口径红线） |
| 对着哪条判定 | 专属一（删干净）· 专属二（Z 为主包）· 手册 §8.4（换站只改配置）· M1-7（不新增任何数值） |
| 过没过 | **过**（证据见下） |

## 实测证据

```text
① headless 探针（直接 import station-packs/index.ts，验选择器逻辑）
   PACKS 键        : A,Z
   DEFAULT_PACK_KEY: Z
   默认包          : Z / 肇庆东站
   切换器条目      : A=肇庆东站 | Z=肇庆东站
   localStorage=Y 时: restorePackKey -> Z | activePackKey -> Z | activePack -> Z
   localStorage=B 时: restorePackKey -> Z          ← 老浏览器残留旧包键不白屏

② 运行中的 dev server（:5173，vite.config 改动已热重启）—— Invoke-RestMethod
   GET /api/traffic/segments → 段数 5，id = SZ-01, SZ-03, SZ-05, SZ-07, SZ-12
   GET /api/traffic/meta     → {"station_id":"ZQNZ","name":"肇庆东站",
                                "subtitle":"真路网 · 吉庆大道 / 鼎湖大道 / 场区通道"}
   → 浏览器侧与 mock 注入侧取的**是同一个包 Z**（错位画面的风险已排除）

③ 构建与门禁
   npm run build            → vue-tsc -b && vite build 通过（dist 正常产出）
   python scripts/doc_gate.py → 7/7 通过

④ 悬空引用
   grep -rn "stationB|stationY|dev:station2|.env.station2" work/frontend
   → 只剩两处注释说明"包 B / Y 已删除"；docs/历史台账/ 为归档原文，未动
```

## 如实记两点（不阻塞）

1. **Z 是薄包，列表只有 5 条**：mock 的 `/api/traffic/segments` 出的是**有基线的 5 条摄像头覆盖段**（左栏「选择监控」与右栏路段列表即这 5 条），其余 16 条只作为**几何灰轮廓**画在图上。断面 / 点位 / 告警 / 车辆 / 场景等空字段面板**如实显示"本站无此数据"，未拿包 A 的演示值去填**（数据补齐另开单）。
2. **未做浏览器截图举证**：本机 dev server 在 :5173 跑着，mock 侧已按新默认出数；页面需刷新一次（顶栏「线路图切换器」现在只有 A / Z 两项）。要截图 / 录屏我可以补。

## 未做

- `git push` 与开 PR —— 由业主决定；
- `work/twin/y_junction/`（Y 型的**几何脚本产物**，不是站点包）**未删**——要一并删请另说；
- Z 的数据缺口（`sections` / `dropoffs` / `zones` / `alerts` / `vehicleBases` / `scenarios` / `assimilation`）与**范围 / 路段数量按站配置**（IKM4B4）**均不在本单**，另开单。

**2 · @ozxowx · 2026-10-16T09:43:11+08:00**

**执行收口**（Agent，2026-10-16）

| 项 | 值 |
|---|---|
| 分支 | `task/IKM4KP-station-pack-z-primary` **已推送** @ `2a23b54` |
| **PR** | **[!20](https://gitee.com/ozxowx/hubflow/pulls/20)**（base `main`，无冲突；**作者不合并自己的 PR**，请兜底审三人任一） |
| 提交 | `80bffb6` 主体（13 文件）+ `2a23b54` 审查发现的 `.env.z` 过期注释 |
| 门禁 | `python scripts/doc_gate.py` **7/7 通过**；`npm run build`（`vue-tsc` + `vite build`）通过 |

**快速独立审查**（全新上下文子代理，只给「改动范围 + 4 问」，未给实现思路 / 可疑点 / 既有结论）
→ ②③④ 全过；① 一处过期注释 `work/frontend/ui-vue/.env.z:1-2`（"第四站 / 与二站 6880 / Y 站 6890 并存"）
→ **已修**（`2a23b54`）。审查者原文与处置表已贴进 PR 的「审查记录」栏。

**浏览器实测（Tabbit，:5173 真实页面）**

```text
左栏「选择监控」= 5 个路段；路段 id = SZ-01 / SZ-03 / SZ-05 / SZ-07 / SZ-12
地图标签 = 底图：OpenFreeMap · OSM；6 个摄像头图钉在位
页脚 = 底图来源:OpenFreeMap(OpenStreetMap 数据,ODbL) · 署名见地图内 · 不缓存瓦片 · 路网:路网几何为真值（OSM 切片）
```

**残留旧包键实测（本单卡点第 2 条关闭）**：把 `localStorage['hubflow.stationPack']` 手工设成 `'Y'` 再刷新 →
`storedKey = "Y"`，页面仍渲染包 Z（`SZ-*`），**不白屏、无 `SEG-*` 串味**（`restorePackKey` 的 `PACKS[k]` 校验生效）。

**如实记**：Z 是薄包，列表只有 5 条（有基线的摄像头覆盖段），其余 16 段只作几何灰轮廓；空字段面板如实显示"本站无此数据"，**未拿包 A 的演示值填** → 补齐见 **IKM4TE**。

**截图（本地，未入库）**：`C:\Users\ou\AppData\Local\Tabbit Browser\User Data\LocalAgent\Runtime\artifacts\task-afb99d29-2ec4-4764-9d9b-3d10c650fcc6\screenshot-shot-e23097f4-8fdb-48bf-924d-c2cafbc2a60b.png`（2544×1267）

**后续两单**：**IKM4B4**（站点范围与路段数量按站配置：肇庆东 500 m）→ 先定范围；**IKM4TE**（Z 数据补齐：断面 / 点位 / 告警 / 场景 / 分流）→ 依赖 IKM4B4。

---

## Issue IKM4B4 · [孪生与路况] 站点范围与路段数量按站配置：肇庆东 500 m、广州南可达 2 km；先人工圈定，后期脚本 + AI 辅助确认（L1）

| 项 | 值 |
|---|---|
| 状态 | open |
| 标签 | L1 / 孪生与路况 |
| 创建 | 2026-10-16T09:00:28+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKM4B4 |
| 指派 | XIXIXIXXXI |

### 正文

> 业主 2026-10-15 口径：**地图范围与路段数量要能按站设置**——**每个高铁站的范围都不一样**：**肇庆东 500 m 范围**，**广州南可能上到 2 km 范围**。所以**范围要跟着高铁站固定下来**，不能全站共用一个数。**一期先用人工选择**（人工圈定 → 登记）；**后期尽可能用脚本 + AI 来确认范围**（先把口子留出来，本期不实现）。

| 项 | 值 |
|---|---|
| 难度标签 | **L1**（一份配置 + 三处脚本改成读配置 + 一期人工圈定流程；不做 AI） |
| 系列标签 | —（区域开发执行；不进任务池认领、不占 WIP 配额） |
| 区域 | 孪生与路况 |
| 发布者 | 孪生与路况 owner（本单由业主代该区域发布） |
| 认领 | 留空，评论"认领"即锁定 |
| 关联 | 手册 **§21.8**（推广路径 / 站点范围）· **§8.4**（换站只改配置）· **IKLLWY**（0-3A：站点 OSM → `net.xml`）· **IKLLX2**（0-3B：`map_ingest.py` → `network.json` / `map_source.json`）· **IKLX5Y**（站点包 Z / netpack 21 段）· **IKLOJ6**（桥接换网）· `docs/全流程计划.md` 第 424 行 · `docs/分工表.md` §S「认路」· 条款核实 **U-06** |

## 现状：范围是"全站共用一个数 + 代码里的常量"，不是"每站一份配置"

实测（2026-10-15）：

| 位置 | 现状 | 问题 |
|---|---|---|
| `work/frontend/tools/twin_preview/server.py:111` | `STATION_RADIUS_M = 1200.0` | 站区筛选半径是**模块常量**，全站共用 |
| 同文件 `:46` / `:631` / `:633` | `DEFAULT_SEG_COUNT = 10`；`--station-lonlat` / `--seg-count` | 段数只是**命令行参数**，默认值写死；**没有"每站一份"的落点** |
| `work/frontend/tools/twin_preview/build_net.py:24` | `BBOX = (23.2105, 112.6485, 23.2229, 112.6618)`（约 1.3 km） | 拉取范围**硬编码**，换站要改脚本（违反 §8.4） |
| `work/twin/netpack/build_station_pack.py` | `SNAP_M=30` / `MIN_SEG_M=60` 间接决定段数（其 README:39 实测：30/60 → 21 段；30/120 → 17 段） | 段数由阈值间接决定，**不是"该站范围内应有几段"** |
| 文档口径 | 手册 §21.8（:3443）、`全流程计划.md`:424、`分工表.md`:283 **三处都写"肇庆东站站前约 1.5 km × 1.5 km"** | 业主新口径是**肇庆东 500 m**——这是**口径变更**，文档要同步（跨区域，见"卡在哪里"第 1 条） |

**结论**：现在既没有"范围"的**登记载体**，也没有"范围 → 路段数量"的**对应关系**；换第二个站只能靠改常量。本单把这两件事立起来。

## 要产出什么

### 1. 站点范围登记表（**每站一份**，本单核心）

新增一份机器可读的登记文件（建议 `work/twin/site-ranges.json`；**也可放站点包字段**，执行者定，PR 说明）。**建议形状**（字段名执行者可调，但每条都要有落点）：

```json
{
  "is_simulated": true,
  "note": "范围是人工圈定/脚本建议的结果，不是官方划定；几何真值来自 OSM",
  "sites": [
    {
      "site_id": "zhaoqingdong",
      "site_name": "肇庆东站",
      "anchor_lonlat": [112.6551321, 23.2166791],
      "range_m": 500,
      "pull_bbox": [112.6485, 23.2105, 112.6618, 23.2229],
      "seg_target": 0,
      "range_source": "manual",
      "decided_by": "",
      "date": "2026-10-15",
      "evidence": ""
    }
  ]
}
```

- **`range_m`**：该站演示范围半径（肇庆东 **500 m**，业主口径）。
- **`pull_bbox`**：**拉取用**范围——**比演示范围放大一圈**，留出 `role: "boundary"` 的上游断面（M1-10）。**两个字段分开登记**，别混成一个。
- **`seg_target`**：该站**路段数量**目标（人工定；见第 4 条）。
- **`range_source`**：`manual` / `script` / `ai-assisted`——**一期只写 `manual`**；后两个是**给后期留的口子**（第 5 条）。
- `decided_by` / `date` / `evidence`：谁圈的、哪天、凭什么（截图或链接）——**范围不许"没来由"**。

### 2. 三处脚本改成读配置（**不许再有站点硬编码**）

- `build_net.py`：`BBOX` 改成从配置读（或参数覆盖，配置为默认）；
- `twin_preview/server.py`：`STATION_RADIUS_M` / `DEFAULT_SEG_COUNT` / `DEFAULT_STATION_LONLAT` 改成从配置读；
- `netpack/build_station_pack.py`：段数/阈值与切片按该站配置走。
- **硬口径（照抄 §8.4 / IKLLWY）**：脚本里**不出现任何站点名、坐标、半径**——换站**只改配置，不改代码**。

### 3. 一期：人工圈定流程（本单要交的就是这个流程 + 肇庆东那份填好的配置）

1. 在高德 / OSM 底图上**人工圈出**该站范围（肇庆东按 **500 m**）；
2. 记下**锚点坐标 + 半径**（或 bbox）与**路段数量目标**；
3. **截图留证**，路径/链接写进 `evidence`；
4. 填进第 1 条的登记表；
5. **如实标注来源 = 人工圈定**（`range_source: "manual"`）——**不得**说成"官方划定"或"实测范围"。

### 4. 范围 → 路段数量的对齐（**本单最容易做错的一步**）

- **范围决定段数**：该站范围里有多少条可点击路段，是**范围圈定后的结果**；段数目标要**人工定并登记**。
- ⚠️ **`--seg-count` 那套不是这件事**：它现在的语义是"**段数不够就把最长的段按里程对半拆**"（`server.py:382-412`、其 README:61-63）——**宁可拆真实长路也要凑数**。**凑数 ≠ 范围**，两者别混。
- **现有产物与 500 m 不符**：`work/twin/netpack/network.json` 的 **21 段**来自 `twin_preview/station.osm`（约 **1.3 km** 切片）——缩到 500 m 后**哪些段还在范围内、段数目标是多少**，要人工定；若切片与配置的 `pull_bbox` 不一致，**按配置重新拉切片**再重跑。

### 5. 后期留位（**本单不实现**）

- `range_source` 支持 `script` / `ai-assisted`；**写清规则**：脚本 / AI 只出**候选范围**（建议依据：路网密度、边界断面位置、OD 覆盖），**必须人工确认后**才写进配置——**AI 不直接定范围**。
- 本单**不写**自动圈范围的脚本、**不接**任何模型或外部服务；只把字段与流程留出来。

### 6. 可查 + 举证

- 大屏 / 接口上能查到「**本站范围 X m（人工圈定）· 路段 N 条**」——如实标注来源，**不报精度数字**；**不出现「实测 / 实时 / 现场」**。
- **截图**：① 人工圈定的范围（底图上圈 + 截图）；② 按该配置跑出来的路网与段数；③ 换站只改配置（改 `site_id` 跑第二个站，代码 diff 为空）。

## 三 prerequisite

| | 内容 |
|---|---|
| **输入样例** | `work/frontend/tools/twin_preview/{build_net.py, server.py, station.osm, station.net.xml}`（现状：常量 + 硬编码 BBOX）· `work/twin/netpack/{build_station_pack.py, network.json, README.md}`（21 段 / 阈值决定段数）· `stations/map_source.json`（已有 `bbox` 字段，只做形状参照）· 手册 §21.8 / §8.4 |
| **输出样例** | `work/twin/site-ranges.json`（肇庆东 500 m 那份填好）· 三处脚本改成读配置（脚本里 grep 不到站点名 / 坐标 / 半径）· 一期人工圈定流程写进 README · 三张截图 |
| **自检脚本** | 见下节。**核心两条**：① 换站只改配置、代码零改动；② 同配置跑两遍范围与段数一致 |

```bash
# ① 配置必填字段齐（每站一份）
python - <<'PY'
import json
d = json.load(open('work/twin/site-ranges.json', encoding='utf-8'))
need = ('site_id', 'site_name', 'anchor_lonlat', 'range_m', 'pull_bbox',
        'seg_target', 'range_source', 'date')
for s in d['sites']:
    miss = [k for k in need if k not in s]
    assert not miss, f"{s.get('site_id')} 缺字段 {miss}"
    assert s['range_source'] in ('manual', 'script', 'ai-assisted'), s
print('✅ 配置字段齐，来源取值合法')
PY

# ② 脚本里没有站点名 / 坐标 / 半径硬编码（§8.4 / M1-1 口径）
grep -nE "肇庆|广州南|23\.21|112\.65|1200" \
  work/twin/netpack/*.py work/frontend/tools/twin_preview/*.py \
  && echo "❌ 有硬编码" || echo "✅ 无站点名/坐标/半径硬编码"

# ③ 同配置跑两遍，范围与段数一致（脚本改成读配置后）
python work/twin/netpack/build_station_pack.py --config work/twin/site-ranges.json --site zhaoqingdong --check

# ④ 门禁
python scripts/doc_gate.py
```

## 完成判定（**照抄既有条目 + 本单三条专属，不新造编号**）

| 条目 | 原文口径 | 本单怎么算过 |
|---|---|---|
| **手册 §8.4 / §21.8（2）第 1 条** | **换站只改配置，引擎代码零改动** | 换 `site_id` 跑第二个站，脚本 **diff 为空**；范围与段数全部来自配置 |
| **分工表 §S「认路」** | 站点范围与队长裁定一致；T2 行数 = 路段清单条数 | 登记表里的范围 = **人工圈定截图**里的范围；`seg_target` 与 T2 路段清单条数**对得上** |
| **IKLLWY（0-3A）第 2 条 / M1-1** | 脚本要能吃参数；**引擎里不出现任何站点名、坐标、路名硬编码** | 三处脚本 grep 不到站点名 / 坐标 / 半径 |
| **IKLLX2（0-3B）** | `map_source.json` 记**拉取范围（bbox）** | 拉取 bbox = 配置里的 `pull_bbox`；**演示范围与拉取范围分开登记** |
| **口径红线** | 不把模拟值说成实测值 | 范围**如实标 `range_source: manual`**；页面不出现「实测 / 实时 / 现场」；**不说**"官方划定" |
| **本单专属一（每站一份范围）** | — | `site-ranges.json` 里有肇庆东那份（**500 m**）；再加一站**只加一条记录**，不动代码 |
| **本单专属二（范围与段数成对）** | — | 每站 `range_m` 与 `seg_target` **成对登记**；段数**不是**靠 `--seg-count` 拆长路凑出来的 |
| **本单专属三（人工在前、脚本 / AI 在后）** | — | 一期 `range_source` 全为 `manual` + 截图留证；`script` / `ai-assisted` **只留字段**，规则写明"AI 只出候选、人工确认才生效" |

## 依赖谁的什么

- **依赖人工圈定**：范围要有人在底图上圈（池·S / 站点与踏勘的「认路」口径，分工表 §S）——**本单先把登记载体与脚本改造做完，肇庆东那份 500 m 由人工圈定后填**。
- **依赖队长同步文档**：手册 §21.8、`全流程计划.md`:424、`分工表.md`:283 三处现在写的是"1.5 km × 1.5 km"，**口径改为按站配置**后要同步（**跨区域，归队长 / 文档与合规**）。
- **不依赖**：SUMO 不必重装、后端不必起、**不接任何模型或外部服务**（第 5 条只留字段）。
- **不碰**：`work/engine/`、数据契约、既有站点包 A / B / Y 的行为。

## 卡在哪里

1. **这是口径变更，不是纯新增**：文档三处写着"肇庆东站站前约 1.5 km × 1.5 km"（手册 §21.8:3443、`全流程计划.md`:424、`分工表.md`:283），业主新口径是 **肇庆东 500 m + 按站配置**。**执行者不要自己改手册**（跨区域）——在 PR 里写明"需队长同步文档三处"，**卡住 30 分钟 @队长**。
2. **500 m 与现有切片不符**：现有 `station.osm` 是约 **1.3 km** 切片、netpack 出 **21 段**。缩到 500 m 后段数必然变——**段数目标要人工定**，别拿"凑够 10 段"当依据（`--seg-count` 是**拆长路凑数**，与"范围决定段数"是两件事，见第 4 条）。
3. **别把范围说成官方划定**：范围是**人工圈定**（`range_source: manual`）；二期才谈脚本 / AI 建议，且**必须人工确认**。对外**不报精度数字**。
4. **拉取 bbox ≠ 演示范围**：拉取要比演示范围**放大一圈**（留 `role: "boundary"` 的上游断面，M1-10）——`range_m` 与 `pull_bbox` **两个字段分开登记**，别只留一个。
5. **跨区域**：产物落 `work/twin/` 与 `work/frontend/tools/twin_preview/`（孪生与路况）；文档三处归队长。PR 里写明跨区域并经复核。
6. 卡住 30 分钟在 Issue 里 @队长。

## 交接留痕

认领者在评论里写：**交了哪个文件、对着哪条判定、过没过。**

### 评论（1 条）

**1 · @ozxowx · 2026-10-16T10:25:31+08:00**

## 交接条件（写给「两图合一」那单：删示例路网 / 只留矢量地图 / 底图拉不出来也照画路网）

本单产出的是**数据**（站点范围 → 段划分与段数）；那一单产出的是**画法**。两单唯一的交接面 = `stationZ.network.ts` 导出的段列表（`segment_id` / `name` / `kind` / `coords`）与 `stationZ.ts` 的 `SEGMENT_BASES` —— **渲染侧只读，不新增字段、不改段划分**。所以本单不会因为那一单而改路线，但下面四处要在本单收口。

### 风险一（本单必做）：段 id 一旦重排，这三处要同步

范围缩到 500 m 后段数必然变，**段 id 大概率重排**。不同步就会出现"图钉指向不存在的段 + 彩色段全消失（全灰）"：

| 落点 | 现状 | 表现 |
|---|---|---|
| `stationZ.ts` `CHANNELS` 6 条摄像头的 `segment_id` | `SZ-01/01/05/12/07/03` | 图钉仍画，但该段找不到监控 → 不上色 |
| `stationZ.ts` `SEGMENT_BASES` 5 条基线 | `SZ-01/03/05/07/12` | 这 5 条彩段消失 |
| `stationZ.ts` `recommend` | `location_segment_id` `SZ-01`、`arrival_segments`、`departure_segments`、`alternatives` | 推荐/落客段落空 |

### 风险二（本单目前没写，需裁定）：司机端 HTML 试作的内联数据也是 21 段硬编码

- `work/frontend/app-html/data/network.json`、`work/frontend/app-html/data/app-data.js`（21 段 + 5 条基线 + recommend 全内联）
- `work/frontend/app-html/index.html:815`（硬编码 `SZ-03` → 备选路线）
- `work/frontend/app-html/build_data.py --check`（自检：内联数据要与站点包一致）

段一变，这份就过期、自检会红。**要么本单一并重生成，要么在 `app-html/README.md` 写明"内联数据停在旧口径（21 段）"**。

### 风险三（与那一单的显式约定）：显示位点

本单"可查 + 举证"那条要求大屏能查到「**本站范围 X m（人工圈定）· 路段 N 条**」，显示位点在中栏地图卡（`map-tag` / 页脚）。那个位置正好被"两图合一"合并文案。**约定：显示位点由本单定，合并时保留接上、不覆盖。**

### 顺序建议

**本单先合（改数据），两图合一后合（改画法）** —— 后者的截图验收要对着定型的段数。文件级不冲突（本单动 `work/twin/*`、`twin_preview/*`、`stationZ.ts`；后者动 `DashboardView.vue`、`MapLibreViewer.vue`、删 `NetMap.vue`），但**验收必须等段定型**。

### 顺带一个收益

合并成单渲染器后，"只摄像头段上色 / 灰轮廓"从两处实现收敛到一处 —— 本单改段数时只需改站点包，图上的彩/灰分布自动跟着走，不会出现"两个渲染器里改了一个漏另一个"。

---

## Issue IKLX9B · [接口与双端] 司机端 App 前端先用单文件 HTML 顶替：常规导航版式 + 路线段按站点包 Z 上色（IKLX5Y 后续 · 不做生成路线）（L1）

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | L1 / 接口与双端 |
| 创建 | 2026-10-15T13:05:45+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLX9B |
| 指派 | ozxowx |

### 正文

> 业主 2026-10-15 口径：这是 **IKLX5Y 的后续单**——**司机端 App 的前端先用一个单文件 HTML 顶替**（真正的鸿蒙 App 是 IKLLX9 那条线），本单先把**页面版式与交互定下来**：**按常规导航 App 来设计**（手机壳 + 底部标签栏 + 地图当首页）；路线段**按 IKLX5Y 那份真路网（站点包 Z）来画**、**有颜色代表拥堵**；**「全览」保留**；**不做「生成路线」**——路线由**后台**按路段拥堵推算，App 只负责**把起点终点发过去、把路线画出来**。

| 项 | 值 |
|---|---|
| 难度标签 | **L1** |
| 系列标签 | —（区域开发执行；不进任务池认领、不占 WIP 配额） |
| 区域 | 接口与双端 |
| 发布者 | 接口与双端 owner（本单由业主代该区域发布） |
| 认领 | 留空，评论"认领"即锁定 |
| 关联 | **IKLX5Y**（前序：站点包 Z / 21 段 / 6 路摄像头 / 只摄像头段上色）· **IKLLX9**（最终交付是鸿蒙 App，**本单只是 HTML 试作**）· 手册 **§11.1 / §11.3 / §11.4** · 附录 B.3 **C-3** · **TC-05 / TC-11 / TC-12 / M1-7** · 手册 **§6.2**（三重编码）· 条款核实 **E-11 / E-13**（OSM 署名）· 协作规范 **§1 / §2** · `work/frontend/README.md` 第三节 |

## 背景：为什么先用 HTML 顶替 App

鸿蒙工具链还没就位（IKLLX9 记着：本机 `hvigor` / `ohpm` / `hdc` 均不在 PATH）。**在等工具链的这段时间里，"页面长什么样、点哪里、数据从哪来"这三件事可以先定死**——定死了再搬 ArkTS，返工最小。

HTML 单文件的优势是**改得快、当场就能在浏览器里演示、评审不用装环境**。所以本单的产物是**一份 HTML 试作**，不是最终交付。

> ⚠️ **本单与 IKLLX9 的分界**：IKLLX9 交的是**鸿蒙工程**（ArkTS 四页 + 绑演示车）；本单交的是**页面版式与交互口径**（用 HTML 承载）。**本单不写 ArkTS、不装工具链、不碰 `work/frontend/harmony/`。**

## 起点：业主给的这份单文件 demo（本单就是在它上面改）

| 项 | 现状（实测） |
|---|---|
| 形态 | 单文件 HTML，**自带 maplibre-gl 4.7.1 + openfreemap 底图样式，两者都走公网 CDN** |
| 内嵌数据 | 一条 **8612 m** 的路线（85 个折线点 / 12 条转向提示）+ 背景图层（`green` 3 / `water` 86 / `roads` 274 / `junctions` 70）——**背景路网就是 IKLX5Y 那份 OSM 切片的原始形态** |
| 现有控件 | 全览 / 跟随 / 暂停 / 倍速 / **✏️绘制 / ✓生成路线 / ✕清除** |
| 现有"拥堵"着色 | **是假的**：按**行程进度**分四段染色（0–40% 绿 → 40–65% 黄绿 → 65–85% 橙 → 85–100% 红），**与真实拥堵无关** |
| 版式 | 桌面网页版式（顶部导航卡 + 底部一条工具栏），**不是手机 App** |
| 车辆 | 一个沿路线滑动的车标（按 `speed` × 时间推进） |

**结论**：底子够用（地图 + 路线 + 导航卡都有），但**版式要改成 App、着色要换成真拥堵口径、生成路线那套要拆掉**。

## 要产出什么

### 1. 入库 + 分支

- 新目录 **`work/frontend/app-html/`**（**新增**，与 `ui-vue/`、`harmony/` 并列；建议此名，执行者可改，PR 说明）。
- **基线留档**：原 HTML **原样入库一份**，改造后的另存一份——**评审与回退都要能看出改了哪几处**。
- **分支**：`task/<本单号>-app-html-nav`——**一条任务一条分支，合并后删除**（协作规范 §2）。
- `README.md`：**怎么打开**（双击即可，无需构建、无需装依赖）+ 一句话口径——**这是司机端 App 的页面试作，不是最终交付；最终交付是鸿蒙 App（IKLLX9）**。

### 2. 版式：按常规导航 App

- **手机壳**：固定一个手机视口（建议 390×844 或 375×812），页面居中，**不出横向滚动条**。
- **地图当首页**：地图铺满壳内。
- **底部标签栏**（建议 5 项）：**地图 / 当前建议 / 落客候客 / 离站路线 / 我的行程**——**项数与命名执行者可调**（PR 说明）；后四项照 **C-3** 的页面口径**做壳**（标题 + 关键字段占位，**内容可简**）。
- 顶部导航卡（转向图标 + 距离 + 路名）保留，改成手机导航卡的样子。
- **口径**：这是**版式试作**，**不做花哨动效**（手册风险表第 12 条同口径）。

### 3. 地图页：路线段按站点包 Z 上色（**本单的核心**）

- **段划分一律用 IKLX5Y 的站点包 Z**（`SZ-01` … `SZ-21`，**21 段**）——**不得另造一套段划分**。
  > 注：IKLX5Y 的"约 9 段"是目标口径；实际产物是 21 段——**同名的路被切成互不相连的几摊时按摊拆开**（IKLX5Y 已裁定）。以 `stationZ.network.ts` 为准。
- **上色规则（照抄 IKLX5Y，一字不改）**：
  - 有摄像头 + 有数据 → 按 `level` **四级色**；
  - **有摄像头但暂无数据 → 灰**（TC-11）；
  - **无摄像头 → 中性灰轮廓（细线）**，一眼看出"这段没监控"；
  - 两种灰用**线宽 / 透明度**区分，**不引入第二套灰**。
- **删掉"按行程进度染色"那套**（见"卡在哪里"第 4 条）——**颜色必须真的代表拥堵**。
- **每段可查摄像头数**：点 / 悬停路段显示该段的摄像头路数，没有的**如实显示 0**。
- **路网 vs 路线**：图上**先画整张路网**（站点包 Z 的 21 段），**再把"本次路线"高亮出来**（`arrival_segments` / 备选）；高亮**只加描边或加粗，不改等级色**（等级色是唯一表示拥堵的通道）。

### 4. 「全览」保留（**业主明说保留**）

- **必须保留**，并改造成**手机上用得着的控件**（右下角悬浮按钮或工具栏按钮）。
- 点击后：把整张站点包 Z 路网框进屏幕（`fitBounds` 到 21 段的包围盒），**俯仰角归零**、**跟随关闭**。
- **判定**：点一次「全览」，21 段**全都在画面里**（截图留证）。

### 5. 不做「生成路线」（**业主明令**）

- **删掉** ✏️绘制 / ✓生成路线 / ✕清除 三个按钮，以及那段直连 `router.project-osrm.org` 的 `fetch`——**连根拔**。
- **为什么**：**路线由后台按路段拥堵推算**，App 只负责**把起点终点发过去、把路线画出来**。客户端自己算路线（或浏览器直连第三方路由服务）与这条口径冲突，演示现场也不该出现这种外部请求。
- **本单只留接口位**：地图页给一组「**起点 / 终点**」输入（可点选路段 + 图上起终点标记）+ 一个「**请求路线**」按钮。
  - **按钮本单不发真请求**；用**站点包 Z 的 `recommend`**（`arrival_segments` / `departure_segments` / `alternatives` / `why`）当**后台返回的替身**；
  - 按钮下方**如实标注**：「**路线由后台按路段拥堵推算 · 本单只留接口位**」；
  - **请求 / 响应的形状照数据契约 §二（`routes`）**，**不改契约、不加字段**；将来后台就绪只需把 base 换掉。

### 6. 必须带的标注（缺一不通过）

- **M1-7 角标**「演示数据（模拟）· 双数据源（视频链路 + 孪生链路）」——**画面上要有**；
- **`is_simulated: true`** 可追溯；
- **OSM 署名**：图角「© OpenStreetMap contributors」链到 `openstreetmap.org/copyright`（条款核实 **E-11 / E-13**）；
- **三重编码**：四级**颜色 + 图标 + 文字同时出现**，关掉颜色也能区分（照 IKLLX9 的 `LevelMeta` 口径）；
- **告知文案**「**该建议基于当前路况，可能随流量变化**」**必现**，**不强制、不反复弹窗**；
- **应急态**：停下路线引导，替换为「**请服从现场指挥**」（优先级高于一切推荐）；
- **口径红线**：页面**不出现「实测 / 实时 / 现场」**；不得把路况说成"SUMO 仿真输出"或"真实画面"。

### 7. 举证

- **至少四张截图**（都带角标）：
  1. 手机壳 + 地图首页 + 21 段路网（**摄像头覆盖的段有颜色、其余灰轮廓**）；
  2. 点「全览」后 **21 段全在画面里**；
  3. 路段**可查摄像头数**（含一段如实显示 **0**）；
  4. 起点 / 终点 + 「请求路线」按钮与那句"后台推算"标注。
- 或一段连续画面（录屏落**本地暂存，不入库**）。

## 三 prerequisite

| | 内容 |
|---|---|
| **输入样例** | 业主提供的单文件导航 demo HTML；IKLX5Y 的站点包 Z（`src/station-packs/stationZ.ts` + `stationZ.network.ts`：21 段 / 6 路摄像头 / `colorPolicy: 'camera-covered'`）；`work/frontend/harmony/entry/src/main/ets/common/LevelMeta.ets`（四级三重编码的形状参照）；`src/views/dashboard/components/NetMap.vue`（"只画折线"的零依赖画法参照） |
| **输出样例** | `work/frontend/app-html/`（基线 + 改造版 + README）；浏览器打开：手机壳里的地图首页、21 段路网按站点包 Z 上色、「全览」可用、**没有**生成路线、起点终点 + 请求按钮（不发真请求） |
| **自检脚本** | `python work/frontend/app-html/build_data.py --check`（内联数据与站点包 Z 一致）+ 仓库根 `python scripts/doc_gate.py` 全绿（HTML 属受管文本，查编码 / 换行 / 密钥）；人工核：四张截图、口径红线 grep 不到「实测 / 实时 / 现场」、OSM 署名在位 |

## 完成判定（**照抄既有条目 + 本单四条专属，不新造编号**）

| 条目 | 原文口径 | 本单怎么算过 |
|---|---|---|
| **手册 §11.1 / §11.3 / §11.4** | 司机端 P0 四页；四级**三重编码**（颜色 + 图标 + 文字） | 底部标签栏覆盖 C-3 四页（**做壳即可**）；四级三重编码同时出现 |
| **附录 B.3 C-3** | P0 四页可用；绑定一辆演示车 | 四页在标签栏里都进得去；**车辆位置用站点包 Z 自己的演示位置**（`recommend.location_segment_id` + `location_offset_m`）并**如实标注"不做定位"**——⚠️ **本单不跨包去取站点包 A 的演示车**（站点包 Z 的 `vehicleBases` 为空、`bridge.enabled: false`；跨站取车会出现"别站的车画在本站图上"，与 IKLOJ6 记下的那条口径冲突） |
| **TC-11** | 数据不可用显示**灰色**，绝不显示成蓝色 | 有摄像头但无数据 → 灰；无摄像头 → 灰轮廓；**不得为好看给无摄像头段上色** |
| **TC-12** | `departure_route` **必现** | 「离站路线」页里 `departure_segments` 必现 |
| **TC-05（App 侧）** | 拒绝授权时降级、**流程不中断** | 本单**不发任何定位请求**，如实标注"不做定位" |
| **M1-7** | 物料角标「演示数据（模拟）· 双数据源」，抽查 **100%** 命中 | 四张截图都带角标，**页面上也有** |
| **条款核实 E-11 / E-13** | 对外展示 OSM 数据须署名 + 超链接，位置在**图角** | 图角「© OpenStreetMap contributors」链到 `openstreetmap.org/copyright` |
| **口径红线** | 不把模拟值说成实测值；`is_simulated` 恒 `true` | 页面不出现「实测 / 实时 / 现场」 |
| **本单专属一（常规导航版式）** | — | 手机壳 + 底部标签栏 + **地图当首页**；1440×900 下**不出横向滚动条** |
| **本单专属二（路线段按站点包 Z 上色）** | — | 图上 21 段与 `stationZ.network.ts` **逐段一致**；上色**只落在摄像头覆盖的段**，其余是灰轮廓 |
| **本单专属三（全览保留）** | — | 点「全览」→ **21 段全在画面里** |
| **本单专属四（不含生成路线）** | — | 页面**没有**绘制 / 生成路线 / 清除，**没有任何到第三方路由服务的请求**；只有起点终点 + 「请求路线」按钮（**本单不发真请求**） |

## 依赖谁的什么

- **依赖 IKLX5Y**（站点包 Z：21 段 + 6 路摄像头 + `colorPolicy: 'camera-covered'`）。
  - **IKLX5Y 未合 main 前**：可在 HTML 里**内联一份与站点包 Z 逐段等价的段表**（段 id / 折线 / 等级）先跑起来，**不得另造段划分**；IKLX5Y 合入后改为读同一份。
- 依赖 `work/frontend/harmony/entry/src/main/ets/common/LevelMeta.ets` 的四级三重编码口径（**只读**）。
- **不依赖后端**：本单不发真请求，`recommend` 用站点包 Z 的骨架当替身。
- **不依赖鸿蒙工具链**（IKLLX9 的事）。
- **不碰**：`ui-vue/`（三层 3 页与既有 A / B / Y / Z 包的行为**一字不动**）、`stations/`、数据契约、`work/frontend/harmony/`。

## 卡在哪里

1. **底图与地图库都在公网**：现在是 `unpkg.com` 上的 maplibre-gl + `tiles.openfreemap.org` 的底图样式——**演示现场若无外网会白屏**。三条路，**先在本 Issue 里说一句再动**（引依赖要申报）：
   - ① 把 maplibre-gl **落到 `public/`**（体积在 2 MiB 上限内，可入库）；
   - ② 换成**零依赖 SVG**、只画站点包 Z 的 21 段折线（大屏 `NetMap.vue` 就是这个口径，最稳）；
   - ③ 接受联网，但在 README 里**写清依赖公网**。
2. **这是试作，不是最终形态**：别把 HTML 做成"最终形态"（例如堆动效、堆只在浏览器里成立的写法）——**将来要搬到鸿蒙 ArkTS**（IKLLX9）。**版式与交互口径**才是本单的产物。
3. **「不做生成路线」要连根拔**：三个按钮 + 那段 `router.project-osrm.org` 的 `fetch` 都要删干净。**留着它就是"客户端自己算路线"**，与"后台推算"冲突。
4. **现在的颜色是假的**：路线上的四段色是**按行程进度**染的，**不是拥堵**。必须换成**按站点包 Z 的 `level` 上色**，否则"有颜色代表拥堵"这句话站不住。
5. **OSM 署名**：底图与路网都源自 OSM，**图角必须有**「© OpenStreetMap contributors」链到 `openstreetmap.org/copyright`（E-11 / E-13）——现在的 demo 里没有。
6. 卡住 30 分钟在 Issue 里 @队长。

## 交接留痕

认领者在评论里写：**交了哪个文件、对着哪条判定、过没过**。

### 评论（2 条）

**1 · @ozxowx · 2026-10-15T14:25:47+08:00**

## 交接留痕（本单已做完，等 PR 兜底审）

**交了哪个文件** → 新增目录 `work/frontend/app-html/`（**9 个文件**，不碰任何既有文件）：

| 路径 | 是什么 |
|---|---|
| `index.html` | 改造后的试作：手机壳 390×844 + 底部五标签栏 + 地图首页（963 行） |
| `baseline/nav-demo-baseline.html` | **业主给的原始单文件 demo 原样留档**（只把换行归一成 LF），评审与回退都能看出改了哪几处 |
| `build_data.py` | 从**站点包 Z** 抽段表 / 指标 / 摄像头 + 基线内嵌底图 → `data/` 三份产物；`--check` 与站点包**逐字节一致** |
| `data/{network.json, map-shapes.json, app-data.js}` | 数据产物（`file://` 下免 CORS，双击即可打开） |
| `vendor/maplibre-gl.{js,css}` | 地图库 4.7.1 **落到本地**（不再走 `unpkg.com`） |
| `.evidence/`（7 张截图 + 一份对照 README） | 第 7 节的举证，见下 |
| `README.md` | 怎么打开 / 数据怎么重抽 / 口径落点 / 已知限制 |

**对着哪条判定、过没过** → 逐条如下（实测值取自本机静态服务 + 浏览器 1440×900，截图见 `.evidence/`）：

| 判定 | 怎么算过 | 结果 |
|---|---|---|
| **手册 §11.1 / §11.3 / §11.4** | 标签栏覆盖 C-3 四页；四级三重编码（颜色 + 图标 + 文字）同时出现 | ✅ `05-advice-page.jpg` |
| **附录 B.3 C-3** | 四页都进得去；车辆位置用**站点包 Z 自己的演示位置**（`recommend.location_segment_id` + `location_offset_m`）并如实标注「不做定位」——**未跨包取站点包 A 的车** | ✅ 页面「数据来源」卡写明；备选只有 1 条（C-3 要 ≥2）**缺口如实登记在页面上，未编造** |
| **TC-11** | 有摄像头但无数据 → 灰；无摄像头 → 灰轮廓 | ✅ 5 段上色 / 16 段灰轮廓；`03-segcard-sz02-zero-camera.jpg` 里 `SZ-02` 如实显示「**摄像头 0 路**」「未监控（灰轮廓）」 |
| **TC-12** | 「离站路线」页 `departure_segments` 必现 | ✅ `06-depart-page.jpg`（`SZ-12 → SZ-05`，4 min） |
| **TC-05（App 侧）** | 降级、流程不中断 | ✅ 本单**不发任何定位请求**，如实标注「不做定位」 |
| **M1-7** | 角标必现，截图 100% 命中 | ✅ 7 张截图逐张可见 |
| **条款核实 E-11 / E-13** | 图角 OSM 署名 + 超链接 | ✅ `04-endpoints-request-route.jpg` 页脚 |
| **口径红线** | 页面不出现「实测 / 实时 / 现场」 | ✅ grep 为 0（唯一豁免是手册原文「请服从现场指挥」） |
| **本单专属一（常规导航版式）** | 手机壳 + 标签栏 + 地图当首页；1440×900 不出横向滚动条 | ✅ `01-map-home-21seg.jpg` |
| **本单专属二（按站点包 Z 上色）** | 21 段逐段一致；上色只落在摄像头覆盖的段 | ✅ `paintOf()`：**5 段等级色 / 16 段灰**，与 `stationZ.network.ts` 逐段一致 |
| **本单专属三（全览保留）** | 点「全览」→ 21 段全在画面里 | ✅ `segmentsInView()` **全览前 1 → 全览后 21**、`pitch === 0`；对照图 `02a` / `02b` |
| **本单专属四（不含生成路线）** | 没有绘制 / 生成路线 / 清除，无第三方路由请求 | ✅ 三个按钮与那段 `router.project-osrm.org` 的 `fetch` **连根拔掉**；只留起点 / 终点 + 「请求路线」（**不发真请求**），按钮下方如实标注「路线由后台按路段拥堵推算 · 本单只留接口位」 |

**自检脚本**：`python work/frontend/app-html/build_data.py --check` → 「3 份产物与站点包 Z 逐字节一致」；`python scripts/doc_gate.py` → **七组全绿**（第 7 组 1 条既有「占位」[注意]，与本单无关）。

**瓶颈一的申报（引依赖）**：底图与地图库原本都在公网，演示现场无外网会白屏 → 按三条路里的 ① 做：maplibre-gl **落到 `vendor/`**（803 KB，在 2 MiB 上限内）、底图折线预算进 `data/map-shapes.json`，**做到双击即可打开、零外部网络请求**（`document.scripts` 与 `link` 全部指向 `vendor/` 与 `data/`）。

**给下一棒的两条提醒**（都写在 `README.md` 里，不是坑是已知差异）：
1. **换真后台不是只换 base**——页面现在读的是**站点包 recommend 的扁平字段**（`arrival_segments`），契约 §二 是**嵌套的**（`arrival_route.segments` / `alternatives[].path`），要加一层字段适配；
2. **`build_data.py` 的输入是站点包 Z**（IKLX5Y 的产物）——`stationZ.*` 未合 main 时本分支直接跑会提示读不到，两种办法写在脚本报错里；`data/` 三份产物**已入库**，双击 `index.html` 不需要跑脚本。

**PR**：https://gitee.com/ozxowx/hubflow/pulls/13 （分支 `task/IKLX9B-app-html-nav`，4 个提交：feat `99cbad9` → fix `8dfaadc`（快速独立审查 4 类问题）→ docs `078cb9e`（本举证））
⚠️ **合并顺序**：建议 IKLX5Y（`stationZ.*`）先合、本 PR 后合——否则本分支上跑 `build_data.py --check` 会读不到输入（页面本身不受影响）。**兜底审**待三位任一；本单作者不点 Merge。

**2 · @ozxowx · 2026-10-15T16:15:15+08:00**

## 关闭依据（2026-10-15 复核）

PR #13 已合入 main（合并点 `883bf73`）。`work/frontend/app-html/` 9 个文件在库（原始 demo 基线留档 + 改造版 + `build_data.py` + `vendor/maplibre-gl.*` + `data/` + `README.md`），`.evidence/` 7 张举证截图入库。

| 完成判定 | 证据 |
|---|---|
| 本单专属一（常规导航版式） | 手机壳 390×844 + 底部五标签栏 + 地图当首页（`.evidence/01-map-home-21seg.jpg`） |
| 本单专属二（路线段按站点包 Z 上色） | 21 段逐段照抄 `stationZ.network.ts`：有摄像头 + 有数据 5 段四级色、无摄像头 16 段中性灰轮廓；`build_data.py --check` 与站点包逐字节一致 |
| 本单专属三（全览保留） | 点「全览」→ 21 段全在画面里（俯仰归零、跟随关闭）；`.evidence/02a` / `02b` 前后对照 |
| 本单专属四（不含生成路线） | 页面里 `osrm` **零命中**；绘制 / 生成路线 / 清除三个按钮那段直连 `router.project-osrm.org` 的 `fetch` 已连根拔；只留起点终点 + 「请求路线」按钮（本单不发真请求）；零外部请求（`vendor/` 与 `data/` 全本地） |
| 每段可查摄像头数 | 含一段如实显示 0（`SZ-02`）；`.evidence/03-segcard-sz02-zero-camera.jpg` |
| M1-7 / TC-11 / TC-12 / OSM 署名 / 口径红线 | 截图均带角标、页面正文无「实测 / 实时」、`is_simulated` 可追溯、图角 OSM 署名带超链接、「离站路线」页 `departure_segments` 必现（`.evidence/06-depart-page.jpg`） |

已知限制两条已如实写进 `README.md`：换真后台需加一层字段适配（站点包扁平字段 vs 契约 §二嵌套形状）；`build_data.py` 的输入依赖站点包 Z —— 该依赖（IKLX5Y）已随 PR #14 并入 main，**合并顺序依赖已消解**。

关闭本单。

---

## Issue IKLX5Y · [孪生与路况] 肇庆东站真路网当路况底图：站点包 + 大屏摄像头位置（点开跳感知层 · 只摄像头段上色 · 视频留空窗）（L1）

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | L1 / 孪生与路况 |
| 创建 | 2026-10-15T12:44:39+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLX5Y |
| 指派 | ozxowx |

### 正文

> 业主 2026-10-15 口径：把已经认好的**肇庆东站真路网**当成**一张地图**（跟 Y 型那张一样）放到**监控大屏**上；**新增摄像头位置**；**点击摄像头直接跳到感知层对应摄像头的画面**；**只有摄像头监控下的路段才显示颜色（拥堵情况）**；**视频样本先不弄——留个空窗即可**；路段按建议**按路名归并**（约 9 段）。

| 项 | 值 |
|---|---|
| 难度标签 | **L1** |
| 系列标签 | —（区域开发执行；不进任务池认领、不占 WIP 配额） |
| 区域 | 孪生与路况 |
| 发布者 | 孪生与路况 owner（本单由业主代该区域发布） |
| 认领 | 留空，评论"认领"即锁定 |
| 关联 | **IKLR30**（同类先例：几何 → 数据 → 大屏）· `src/station-packs/stationY.*`（站点包形状先例）· 手册 **§11.2** / 判定 **C-2** / **TC-11** · **M1-7** · 协作规范 **§1**（目录归属）· 条款核实 **E-11 / E-13**（OSM 署名） |

## 背景：Y 型证明了链路，本单换成真路网

Y 型（IKLR30）证明的是"**几何 → 数据 → 大屏**"这条链能通；本单做同一件事，数据源换成**仓库里已经躺着的那份 OSM 切片**（有真实路名与道路等级，不是手画几何）。

- 两者同属**地图层**：一张底图 + 若干可点路段。**本单不判定主干 / 分支**（业主明说先不定）。
- **走廊**（吉庆大道 4 个口子 → 站门口）是这张网里的一小段，其落位**另开单**，不在本单范围。
- 摄像头是本单新增的东西：**大屏上新增摄像头位置标记**，点击跳到感知层对应画面；**只有挂到摄像头的路段才上色**，其余段只是灰色路网轮廓。

## 输入（都在仓库内，不联网、不拉新数据）

| | 内容 |
|---|---|
| **仓库内 OSM 切片** | `work/frontend/tools/twin_preview/station.osm`（已在库、`git ls-files` 有它；175 节点 / 70 way，way 上带 `name` / `highway` / `service` 标签） |
| **形状先例** | `src/station-packs/stationY.ts` + `stationY.network.ts`（脚本产物、头部写明"勿手改"）+ `.env.y` + `npm run dev:y` |
| **感知层通道现状** | `src/views/perception/components/channels.ts`（通道目录：`cid` / `source` / `name` / `segment_id`，映射从站点包读）+ `work/perception/data/monitor/`（**实际只有 `road2`、`track1` 两路有数据**） |
| **大屏画法** | `src/views/dashboard/components/NetMap.vue`（零依赖 SVG，把包里所有段的经纬度包围盒投影到 1100×680；极简口径 = 只画路段线） |

**已量好的路网规模**（按 `name` / `service` 归并，供参考、不必重算）：吉庆大道 17 way / 3847 m、`parking_aisle` 15 / 1777 m、鼎湖大道 9 / 1583 m、`primary_link` 9 / 443 m、`driveway` 8 / 722 m、`tertiary` 6 / 1829 m、`secondary` 4 / 274 m、`residential` 1 / 492 m、其他 `service` 1 / 296 m。

## 要产出什么

### 1. 路网抽取脚本（`work/twin/netpack/`，新增）

- `build_station_pack.py`：读 OSM 切片 → 出站点包数据。**切片路径 / 站点名 / 输出路径全走参数**，脚本里不得出现任何站点名与坐标硬编码（手册 §8.4 口径）。
- **路段粒度（业主已裁定：按路名归并）**：按 `name`（无名的按 `service` / `highway`）归并成"可点击的路段"，归并后约 **9 段**。若同名的路在切片里分成互不相连的几摊，**分开成段**，PR 里说明。
- 每条段保留：`segment_id` / 中文名 / `kind`（`main`/`ramp`）/ 折线坐标 / **组成它的 OSM way id 清单**（可追溯）。
- `--check`：重跑一遍与既有产物**逐字节一致**。
- `README.md`：一键复现命令 + 一句话说明**这张路网取自 OSM，几何是真值；路段指标一律是演示数据（模拟）**。

### 2. 新站点包（`src/station-packs/stationZ.ts` + `stationZ.network.ts`）

- `stationZ.network.ts` 是**脚本产物**（头部写明"勿手改"），由上面的脚本生成。
- `stationZ.ts`：`source.osm: true` + OSM 署名（`OSM_ATTRIBUTION` 已在 `shared/demoNetwork.ts` 备好，`isOsmNetwork()` 会自动触发署名义务）。
- `.env.z` + `package.json` 加 `dev:z`（端口与 5173 / 6880 / 6890 **不冲突**）。
- **包键写进 `PACKS`**（`station-packs/index.ts`）——⚠️ 该文件是**公共文件**，按协作规范 §1 归**开发C**；跨区域改动要在 PR 里写明并经开发C 复核。

### 3. 大屏：真路网 + 摄像头位置 + **只有摄像头段上色**

- `/dashboard` 中央路网图显示**这张真路网**（换包即换图，不改页面代码——这是 §8.4 的判定标准）。
- **摄像头位置**：把摄像头画在图上（位置见下节建议方案）。位置数据放站点包里——建议**在 `PackChannel` 上补可选 `lon` / `lat` 字段**（通道本来就带 `segment_id`，补坐标即可画出标记）；具体形状执行者定，PR 说明。
- **上色规则（业主 2026-10-15 裁定）**：
  - **只有被摄像头覆盖的路段才显示拥堵颜色**；有数据按等级上色，**有摄像头但暂无数据 → 灰**（TC-11）；
  - **没有摄像头的路段不上色**——只画中性灰的**路网轮廓**（细线），让人一眼看出"这段没监控"；两种灰用**线宽 / 透明度**区分，不引入第二套灰。
  - **这条规则只作用于本单新增的包**；既有 A / B / Y 三个包的行为**一字不动**（守住 C-2）。是否推广到既有包**另开单**。
- **每段带摄像头数**：路段上可查（hover 浮牌或路段信息）该段的摄像头路数；没有的如实显示 **0**。
- **点摄像头 → 跳感知层对应画面**：点图上的摄像头标记 → 跳到感知层并**选中该摄像头对应的通道**。
- **必须带的标注**（缺一不通过）：
  - **M1-7 角标**「演示数据（模拟）· 双数据源（视频链路 + 孪生链路）」——**画面上要有**；
  - **`is_simulated: true`**；
  - **OSM 署名**：地图角上「© OpenStreetMap contributors」链到 `openstreetmap.org/copyright`（条款核实 E-11 / E-13）；
  - **口径红线**：不得出现「实测 / 实时 / 现场」；不得把路况说成"SUMO 仿真输出"或"真实画面"。
- **降级不许白屏**：几何或数据异常时显示灰色「路况不可用」。

### 4. 感知层：支持深链 + 空窗占位

- **深链**：`/#/perception?source=<通道 source>`（具体参数名执行者定）——从大屏点摄像头进来时，**直接选中该通道**；刷新 / 直接打开链接也要生效。
- **空窗（业主：视频样本先不弄）**：本单新增的摄像头**没有视频源**——感知层对这类通道要显示**明确的空窗占位**（如"未接入视频源 · 本期留空" + 灰底），**不得报错、不得白屏，也不得套用"该路样本视频未导出"的既有文案**（那句会让人以为有样本视频）。

### 5. 摄像头方案（本单**建议**，作为默认；执行者可调，PR 里说明）

**建议 6 路**——按"决策点"布点，正好对上感知层现有 6 个通道槽位的排布：

| 编号 | 位置（画在大屏图上） | 覆盖路段 | 参考锚点（可微调） |
|---|---|---|---|
| `cam-01` | 吉庆大道·西进口（含口子2 一侧） | 吉庆大道 | 近口子2 约 `112.6548733, 23.2151734` |
| `cam-02` | 吉庆大道·中段（口子0/1/3 一带） | 吉庆大道 | 近口子1 约 `112.6573791, 23.2139003` |
| `cam-03` | 场区出入口（driveway） | 场区出入道 | 近口子0 约 `112.6570652, 23.2140549` |
| `cam-04` | 停车场内部通道·站门口段 | 停车场内部通道 | 站门口约 `112.6577645, 23.2156324` |
| `cam-05` | 停车场内部通道·北支 | 停车场内部通道 | 约 `112.6588897, 23.2148643` |
| `cam-06` | 鼎湖大道·进场 | 鼎湖大道 | 坐标由执行者按切片取 |

- 6 路覆盖 **4 条路**（吉庆大道 ×2、场区出入道 ×1、停车场内部通道 ×2、鼎湖大道 ×1）——即约 9 段里 **4 段上色、5 段灰轮廓**。
- `source` 用 `cam-01` … `cam-06`（与既有样本视频目录 `road1/road2/cross1/cross2/track1/short_cross` **不混**）。
- 既有 6 路样本视频槽位**不动**；本单新增的摄像头是**另一批通道**。
- **摄像头数不许编**：现有真实数据的只有 `road2`、`track1` 两路样本视频，本批摄像头**全部无视频源**（空窗），如实显示。

### 6. 举证

- 至少三张截图（都带角标）：① 大屏显示真路网 + 摄像头位置标记；② 只有摄像头段上色、其余灰轮廓；③ 点摄像头跳进感知层、对应通道被选中且显示空窗占位。
- 或一段连续画面（录屏落**本地暂存，不入库**）。

## 三 prerequisite

| | 内容 |
|---|---|
| **输入样例** | `work/frontend/tools/twin_preview/station.osm`；`src/station-packs/stationY.*`（形状参照）；`src/views/perception/components/channels.ts`（通道形状） |
| **输出样例** | `work/twin/netpack/`（脚本 + 产物 JSON + README）；`src/station-packs/stationZ*`；`npm run dev:z` 下 `/dashboard` 看到真路网 + 6 个摄像头标记 + 只摄像头段上色；点摄像头跳感知层对应通道（空窗） |
| **自检脚本** | `python work/twin/netpack/build_station_pack.py --check`（两次一致）+ `npm run build`（含 `vue-tsc`）+ 仓库根 `python scripts/doc_gate.py` 全绿 |

## 完成判定（**照抄既有条目，不新造编号**）

| 条目 | 原文口径 | 本单怎么算过 |
|---|---|---|
| **手册 §11.2 / 判定 C-2** | 三层 3 页可用，**一项未删** | 本单**只新增**（新目录 + 新包 + 新标记）；既有三页的既有元素与既有 A / B / Y 三包行为**一字不动** |
| **TC-11** | 数据不可用显示**灰色**，绝不显示成蓝色 | 有摄像头但无数据 → 灰；无摄像头 → 灰轮廓（细线）；**不得为好看给无摄像头段上色** |
| **M1-7** | 角标「演示数据（模拟）· 双数据源」抽查 **100%** 命中 | 截图带角标，**页面上也有** |
| **口径红线** | 不把模拟值说成实测值；`is_simulated` 恒 `true` | 页面不出现「实测 / 实时 / 现场」；空窗**不得**说成"实时视频未连接"之类可误解文案 |
| **手册 §8.4** | 换站只新增 / 替换配置文件，**不改引擎代码** | 换包即换图：页面代码一行没为这张路网改 |
| **条款核实 E-11 / E-13** | 对外展示 OSM 数据须署名 + 超链接，位置在**图角** | 地图角上「© OpenStreetMap contributors」链到 `openstreetmap.org/copyright` |
| **本单专属一（真路网上屏）** | — | 大屏上看到的**是这张真路网**（段数与 `stationZ.network.ts` 一致），不是手画几何 |
| **本单专属二（摄像头位置 + 点击跳转）** | — | 图上能看到 **6 个摄像头标记**；点任一标记 → 跳到感知层并选中对应通道，该通道显示**空窗占位**（不报错、不白屏） |
| **本单专属三（只摄像头段上色）** | — | 约 9 段里只有摄像头覆盖的段有颜色，其余是灰轮廓；**每段可查摄像头数**，没有的显示 0 |

## 依赖谁的什么

**无依赖。** 输入全在仓库内（OSM 切片已在库），不联网、不拉新数据。

- **不装 SUMO、不跑 `netconvert`、不起后端、不碰 `stations/`**（后端站点包 `network.json` / `points.json` 是另一条线，本单不碰）。
- **不判定主干 / 分支**（业主明说先不定）；**走廊落位另开单**。
- 后续若要挂依赖，**发布者在本 Issue 里裁定**；认领者按"无依赖"开工即可。

## 卡在哪里

1. **跨目录**：本单产物落 `work/frontend/ui-vue/src/station-packs/` 与 `views/dashboard/`、`views/perception/`——按协作规范 **§1 归开发C**。`station-packs/index.ts` 更是**公共文件**（只由开发C 改）。执行者若属孪生与路况，**PR 里写明跨区域并经开发C 复核**。
2. **两个已实测的坑**（省得返工）：
   - **图必须建在折线顶点级**：干道是一条长折线，场区通道挂在它的**中间顶点**上。只用首尾点建边会把场区判成不连通——这一坑已经让三个脚本栽过。
   - **`NetMap` 的投影是 `setup` 期一次性常量**（`W=1100 H=680 PAD=62`），不响应挂载后再换路网（见缺陷台账 IKLLX6 第 17 条）。换包发生在挂载前，本单**恰好不受影响**，但**别在挂载后再去改路网**。
3. **摄像头数不许编**：`work/perception/data/monitor/` 里只有 `road2` 与 `track1`。为了画面好看给每段都画上摄像头，是**违反口径红线**。
4. **既有包不许动**：A / B / Y 三包的行为一字不改；"只摄像头段上色"这条规则**只作用于本单新增的包**。
5. 卡住 30 分钟在 Issue 里 @队长。

## 交接留痕

认领者在评论里写：**交了哪个文件、对着哪条判定、过没过**。

### 评论（1 条）

**1 · @ozxowx · 2026-10-15T16:12:52+08:00**

## 关闭依据（2026-10-15 复核）

PR #14 已合入 main（合并点 `64cd948`），本单交付物逐项在库：

| 完成判定 | 证据 |
|---|---|
| 本单专属一（真路网上屏） | `work/twin/netpack/network.json`（21 段）与 `stationZ.network.ts` 同源；`build_station_pack.py --check` 与既有产物逐字节一致 |
| 本单专属二（摄像头位置 + 点击跳转） | `stationZ.ts` 6 路摄像头（`cam-01`…`cam-06`，全部 `hasVideo: false`）；`NetMap.vue` 图钉点开跳 `#/perception?source=…`；`PerceptionView.vue` 支持深链选中该通道并显示「未接入视频源 · 本期留空」空窗（挂载后改地址栏也生效） |
| 本单专属三（只摄像头段上色） | `colorPolicy: 'camera-covered'` 做成**包上可选策略**（缺省 `'all'` = 老行为），既有 A / B / Y 三包一字未改；实测 5 段上色 + 16 段灰轮廓；浮牌按段号现算摄像头数，没摄像头的段如实显示 0 |
| 手册 §8.4（换包即换图） | 页面代码未为这张路网改动；新增 `.env.z` + `npm run dev:z`（:6895） |
| TC-11 / M1-7 / E-11·E-13 / 口径红线 | 有摄像头无数据 → 灰；无摄像头 → 灰轮廓（线宽 + 透明度区分，不引入第二套灰）；角标常驻；图角 OSM 署名链 `openstreetmap.org/copyright`；空窗文案与既有「样本视频未导出」分两档 |

举证方式：PR #14 的「浏览器实测」表逐项写清看哪、看到什么（本地起 `npm run dev:z` 可复现）；截图 / 录屏按单子 §6 口径落本地暂存、未入库。

两条待裁定项随单留痕（不阻塞关闭）：① `station-packs/index.ts` 是否属公共文件（已按「不在清单里」处理并在 PR 里报告，请开发C 确认口径）；② 路段粒度实际 21 段 vs 单子预估约 9 段（阈值 `SNAP_M` / `MIN_SEG_M` 可调，实测 30/120 → 17 段；理由与「路口零共享节点」的实测写在 `work/twin/netpack/README.md`）。

关闭本单。

---

## Issue IKLR30 · [孪生与路况] 最低配演示：自绘 Y 型路网当路线图，车在图上跑起来（L1）

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | L1 / 孪生与路况 |
| 创建 | 2026-10-14T17:38:18+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLR30 |
| 指派 | ozxowx |

### 正文

| 项 | 值 |
|---|---|
| 难度标签 | **L1**（单脚本 + 骨架；**参考量级半天**——几何已现成，本单主要是"入库 + 接进大屏 + 出一种拥堵态"） |
| 系列标签 | —（区域任务；**池子认领**，不属 V / S / P / Q 四系列） |
| 区域 | 孪生与路况 |
| 发布者 | 孪生与路况 owner（本单由 `@ozxowx` 代该区域发布） |
| 认领 | 留空，评论"认领"即锁定（可单人可多人组队） |
| 关联 | 手册 **§11.2**（三层 3 页：选择监控 / 全路段状态 / 路段信息 + 底部热力带）· 判定 **C-2**（一项未删）· **M1-7**（角标） |

> **本单是独立任务**：**不依赖任何其他 Issue，也不依赖任何未落地的产物**。输入在本地暂存目录、脚本现成、只用 `matplotlib` + `numpy`（自绘脚本本来就在用这两个）——**认领即开工，不用等任何人**。
> 后续若要挂上下游依赖，**由发布者在本 Issue 里另行裁定**；认领者**不要自行推断**本单该等谁。

## 背景：以 Y 型路网为「第零版」完成流程测试

业主 2026-10-14 口径：**用这张自绘的 Y 型路网图当路线图，做一个能证明整条链路可行的第零版测试。**

**核心命题**：如果这条链路能跑通，就证明从「几何 → 数据 → 大屏显示」的整条链是可行的。Y 型路网就是第零版的测试地图。

**具体到监控大屏**：大屏要以这条 Y 字形路网为路况底图，**右边显示拥堵、左边显示通畅**的拥堵分布情况。

**注意**：本单**不要"小球"**（即不要用移动的小圆点表示车辆），改用**路段级拥堵着色** + **静态/慢变指标**来表达路况。

**不装 SUMO、不连桥接、不碰后端、不动站点包、不动契约**——整单跑完只需要这台机器上已有的 Python 环境和一个浏览器。

## 输入：现成的一张三件套（在仓库外，本地暂存目录 `_drawings/y_junction/`）

| 文件 | 内容 | 体积 |
|---|---|---|
| `y_junction.py` | 自绘脚本：手写几何（三条半幅走廊求并集 + 三个缘石圆角 R=5 m）+ 标线（人行横道 / 停止线 / 双黄线 / 车道分界线 / 导向箭头）+ 指北针 / 比例尺 | 16 KB |
| `y_junction.png` | 300 dpi 成品图，2453×2760 | 184 KB |
| `y_junction.svg` | 矢量版（**文字已转路径**） | 96 KB |

三件都 **< 2 MiB**，PNG / SVG **不在** `scripts/doc_gate.py` 的禁入类型里（禁的是 `.mp4` / 模型权重 / 打包产物 / `.xlsx` 等）——**本单的图可以入库**。现有先例：`work/frontend/ui-vue/public/{favicon,icons}.svg`、`work/frontend/harmony/**/app_icon.png`。

**几何关键数**（`y_junction.py` 顶部常量，自检门要核）：三条腿方位角 **45° / 135° / 270°**；每个阴角**内夹角 135°**（即每条腿相对直行偏 45°）；缘石圆角 **R = 5.0 m**；路幅半宽 **7.5 m**；车道中心线在 `off = ±1.75 / ±5.25`（就是导向箭头所在那两条）。

## 要产出什么

### 1. 入库 + 脱盘符（`work/twin/y_junction/`，新增，与 `netbuild/` 并列）

- `y_junction.py` **原样搬入**，**只改一处**：`OUT_DIR` 现在写死本机绝对路径，改为**相对脚本所在目录**（或可配参数）；**脚本里不得再出现任何盘符**。
- 重新生成 `figures/y_junction.{png,svg}` 入库。
- `README.md`：一键复现命令 + 一句话说明**这套几何是纯虚构的示意路网，图上任何一点都不是真实地点**。

### 2. 几何导出（本单的技术核心；**唯一真值来源**）

- `export_geometry.py`：把自绘脚本里的几何**导成一份 JSON**，形状对齐站点包用的 `network.json`（`segments[]` + 每段 `coords` 折线 + `role`），至少含：
  1. 三条腿各一条**中心线**（`role: "boundary"`，端点在交叉口外）；
  2. 交叉口三个缘石圆角的**圆弧点**（`role: "internal"`）；
  3. 每条腿的**车道中心线**（进口两车道，`off = ±1.75 / ±5.25`）——**路段着色就按这个来**。
- `verify_geometry.py`（**自检门，不通过非 0 退出**）：
  - 三条腿方位角 = `45° / 135° / 270°`，每个阴角内夹角 = `135°`；
  - 三条腿在交叉口**互相连通**（每条腿 `boundary` 端到交叉口有连续折线）；
  - 无零长段 / 无重复相邻点；
  - 产物能被 `json.load` 且 `segments` 非空。
- **不手改 JSON**：JSON 只由脚本产出（`docs/开发规范.md` 第 3.1 节同口径）。
- **不许对着图片手量坐标**：手量不可重建、且与脚本两套真值。**底图用不用图是自由的，但车道中心线必须来自本步产物。**

### 3. 监控大屏 Y 型路网视图（**本单的核心交付**）

- **在监控大屏（`/dashboard`）里新增一个 Y 型路网视图**，以这条 Y 字形路为路况底图。
- **不要"小球"**：不用移动的小圆点表示车辆，改用**路段级拥堵着色** + **静态/慢变指标**表达路况。
- **拥堵分布**：**右边拥堵、左边通畅**——具体到 Y 型三岔：
  - **右侧臂（方位角 45°）**：重度拥堵（红色 / 4 级）
  - **左侧臂（方位角 135°）**：通畅（绿色 / 1 级）
  - **下方主线（方位角 270°）**：中度拥堵（橙色 / 3 级）或按执行者在 PR 里说明的档位
- **实现方式二选一**（都不加依赖）：
  - (a) 在 `work/frontend/ui-vue/src/views/dashboard/` 下新增一个组件 / 面板，**接入现有三栏结构**（推荐放中栏「全路段状态」里作为一个视图，或左栏「选择监控」下方）；
  - (b) 独立路由 `/y-demo`，走现成构建。
- **必须带的标注**（缺一不通过）：
  - **M1-7 角标**「演示数据（模拟）· 双数据源（视频链路 + 孪生链路）」——**画面上要有**，不是页脚只有当页有；
  - **`is_simulated: true`**：数据来源明确标为模拟；
  - **口径红线**：**不得**出现「实测 / 实时 / 现场」；**不得**把路况说成"SUMO 仿真输出"或"真实画面"（它是页面按几何模拟的，如实标注即可）。
- **降级不许白屏**：几何或数据异常时显示灰色「路况不可用」，不空白。

### 4. 举证

- **至少两张截图**（都带角标）：
  1. 监控大屏 Y 型路网视图，**右边拥堵、左边通畅**的拥堵分布清晰可见；
  2. 可选：同一视图在不同拥堵参数下的另一张截图，证明"可调"。
- 或一段连续画面（录屏 / GIF 落**本地暂存，不入库**）。

## 三 prerequisite

| | 内容 |
|---|---|
| **输入样例** | 本地暂存目录 `_drawings/y_junction/` 三件；`stations/network.json`（**只读，仅作 JSON 形状参照**）；`work/frontend/ui-vue/src/views/dashboard/` 现有三栏结构（**只读，仅作接线参照**） |
| **输出样例** | `work/twin/y_junction/`（脚本 + `figures/` + JSON + README）；监控大屏里能看到 Y 型路网 + 右边拥堵/左边通畅的着色 + M1-7 角标；两张对照截图 |
| **自检脚本** | `python work/twin/y_junction/verify_geometry.py`（非 0 退出即不过）+ 仓库根 `python scripts/doc_gate.py` 全绿；若走 (a) 路由，另加 `npm run build`（含 `vue-tsc`） |

## 完成判定（**照抄既有条目 + 本单两条专属，不新造编号**）

| 条目 | 原文口径 | 本单怎么算过 |
|---|---|---|
| **手册 §11.2 / 判定 C-2** | 三层 3 页可用，**一项未删** | 本单**只新增**（新目录 + 新视图 / 新面板）；既有三页的既有元素**一字不动** |
| **M1-7** | 物料角标「演示数据（模拟）· 双数据源（视频链路 + 孪生链路）」，抽查 **100%** 命中 | 两张截图都带角标，**页面上也有** |
| **口径红线** | 不把模拟值说成实测值；`is_simulated` 恒 `true` | 页面不出现「实测 / 实时 / 现场」 |
| **分工表 §8.1 W1（可重建）** | 「转换命令写进脚本，**删掉产物能一键重建**」 | 删掉 `figures/` 与 JSON，重跑两个脚本，结果一致 |
| **本单专属一（Y 型路网进大屏）** | — | 监控大屏 `/dashboard` 能看到 Y 型路网视图，路段着色与导出 JSON 一致 |
| **本单专属二（右边拥堵、左边通畅）** | — | 右侧臂显示拥堵（红/4 级）、左侧臂显示通畅（绿/1 级）、下方主线按设定档位着色；**不要小球**，用路段级着色表达 |
| **本单专属三（第零版链路验证）** | — | 从几何导出 → JSON → 大屏视图 → 拥堵展示，**整条链路在本机跑通**；如果这条链路能跑通，就证明从「几何 → 数据 → 大屏显示」的整条链是可行的 |

## 依赖谁的什么

**无依赖。**

- 输入只有两处：本地暂存目录的三件（搬进仓库后即可删掉这层引用）+ `stations/network.json`（**只读**，仅作 JSON 形状参照）。
- **不装 SUMO、不连桥接、不碰后端、不动站点包、不动契约、不动既有三页的既有元素。**
- 后续若要挂依赖，**发布者在本 Issue 里裁定**；本单认领者按"无依赖"开工即可。

## 卡在哪里

1. **入库前先确认红线**：三件现在在**仓库外的本地暂存目录**。搬进来时**不得**把该目录的**盘符写进任何文档 / 脚本 / 注释**（`docs/协作规范.md` 第 8 节 + 手册修订表第 39 条同口径）——README 里写"本地暂存目录"即可，或搬完直接删掉这层引用。
2. **"第零版"的边界要守住**：本单**只做"几何 → 数据 → 大屏路况视图"**。出现下列任一项就是**做过了**，请停手另开单：装 / 调 SUMO、跑 `netconvert`、起任何后端服务、改站点包、改既有三页的既有元素。
3. **不要小球**：路段级拥堵用**颜色 / 宽度 / 叠加指标**表达，不用移动小圆点表示车辆。
4. **拥堵档位由执行者在 PR 里说明**：右侧臂必须拥堵（红/4 级）、左侧臂必须通畅（绿/1 级），中间主线档位可自定并写进 PR。
5. 卡住 30 分钟在 Issue 里 @队长。

## 交接留痕

认领者在评论里写：**交了哪个文件、对着哪条判定、过没过**。

### 评论（3 条）

**1 · @ozxowx · 2026-10-14T17:43:24+08:00**

## 修订留痕（2026-10-14，发布者）

**业主口径：本单为独立任务，不依赖其他东西；等业主说依赖再依赖。**

据此改了正文四处：

| 处 | 改前 | 改后 |
|---|---|---|
| 文首 | 无独立声明 | 新增引用块：**本单是独立任务**，不依赖任何其他 Issue、不依赖任何未落地的产物；**认领即开工**；**后续要挂依赖由发布者裁定，认领者不要自行推断本单该等谁** |
| 关联行 | 列了 `#IKLOB6` / `#IKLOJ6` / `#IKLOL9` 三条并做"互不覆盖"说明 | 去掉三条，只留手册 §11.2 · 判定 C-2 · M1-7 |
| 背景 | 用一节讲现有三单那条完整链、并做"与 #IKLOB6 的分界"对照表 | 换成独立表述：**几何 → 页面 → 车在动**；"不装 SUMO、不连桥接、不碰后端、不动站点包、不动契约" |
| 依赖 | 「不依赖任何其他单」+「与 #IKLOB6 是并列关系」 | **无依赖。** 输入只有两处：本地暂存目录三件（搬进仓库后即可删掉这层引用）+ `stations/network.json`（**只读**，仅作 JSON 形状参照） |

**判定要件一字未改**：六条完成判定（手册 §11.2 / C-2、M1-7、口径红线、分工表 §8.1 W1 可重建、本单专属一"几何来自自绘图"、本单专属二"车真的在动"）与三 prerequisite 全部原样保留。删掉的只是**依赖叙述**，不是范围。本单**仍然只做"几何 → 页面 → 车在动"**——`SUMO` / `netconvert` / 桥接 / 站点包 / 既有三页的既有元素，依旧一项都不碰（见"卡在哪里"第 2 条）。

**给认领者的一句话**：本单**不用等任何人**，现在就能开工。

**2 · @ozxowx · 2026-10-14T18:35:32+08:00**

## 修订留痕（2026-10-14，发布者）

**业主口径：以 Y 字为地图的第零版完成流程测试；如果测试通过就证明整条链路可行；监控大屏以这条 Y 字形路为路况，右边拥堵、左边通畅；不要小球。**

据此把本单从「车在图上跑起来」升级为「**路段级路况视图进大屏**」，正文改动如下：

| 处 | 改前 | 改后 |
|---|---|---|
| 难度标签 | L1 / 单脚本+骨架 | L1 / 单脚本+骨架，**参考量级半天**（几何已现成，主要是「入库 + 接进大屏 + 出一种拥堵态」） |
| 背景 | 「先弄一个最低配的演示效果」→ 几何→页面→车在动 | **「以 Y 型路网为『第零版』完成流程测试」**：如果这条链路能跑通，就证明从「几何 → 数据 → 大屏显示」的整条链是可行的 |
| 核心交付 | 最小演示页 + 车在动 | **监控大屏 Y 型路网视图**：以 Y 字形路为路况底图，**右边拥堵、左边通畅** |
| 表达方式 | 几辆车沿车道中心线滑动 | **不要「小球」**：改用**路段级拥堵着色** + **静态/慢变指标**表达路况 |
| 拥堵分布 | 无 | **右侧臂（方位角 45°）= 重度拥堵（红/4 级）**；**左侧臂（方位角 135°）= 通畅（绿/1 级）**；**下方主线（方位角 270°）= 中度拥堵（橙/3 级）**（主线档位可由执行者在 PR 里说明） |
| 完成判定 | 本单专属二「车真的在动」 | 改为三条专属判定：① Y 型路网进大屏；② **右边拥堵、左边通畅**，不要小球；③ **第零版链路验证**（几何导出 → JSON → 大屏视图 → 拥堵展示，整条链路在本机跑通） |
| 卡在哪里 | 车在动 | 新增两条：③ **不要小球**（路段级着色，不用移动小圆点）；④ **拥堵档位由执行者在 PR 里说明** |

**保留不变**：独立任务声明、无依赖、三 prerequisite（输入样例 / 输出样例 / 自检脚本）、六条完成判定中的前四条（手册 §11.2 / C-2、M1-7、口径红线、分工表 §8.1 W1 可重建）。

**给认领者的一句话**：本单**不用等任何人**，现在就能开工。核心就三件事：① 把图搬进 `work/twin/y_junction/` 并导出 JSON；② 在监控大屏里接一个 Y 型路网视图；③ 做出「右边拥堵、左边通畅」的路段级着色，**不要小球**。

**3 · @ozxowx · 2026-10-14T20:43:29+08:00**

## 进展回执：V0 演示已可运行，3 路段口径获业主确认（PR #10）

**分支** `task/IKLR30-y-junction-dashboard` · **PR** https://gitee.com/ozxowx/hubflow/pulls/10

### 业主 2026-10-14 四轮口径迭代（本单按裁定逐轮落地）

| 轮次 | 业主裁定 | 落地结果 |
|---|---|---|
| ① | 用自绘 Y 型路网当 V0 路线图，右边拥堵/左边通畅、**不要小球** | ✅ 路段级拥堵着色（红/绿），无车辆小球 |
| ② | "重新做，你看看你这像道路吗"（推翻胶囊细线） | ✅ 改为走廊中心线真道路模型 |
| ③ | 黑框里的主线是一整条路段；分叉后左右支线各自成走廊，"分左回右去" | ✅ 路段划分改按走廊 |
| ④ | 去掉黄色缓行档；**站前服务段整段去掉**；**左支线合并为一条、右支线合并为一条** | ✅ 最终 **3 路段**口径 |

### 最终口径（业主已确认："对，就是这样，第零版演示流程就是这样的"）

| 路段 | 范围 | 等级 |
|---|---|---|
| SEG-01 主线 | 南入口→汇流口（黑框段） | 畅通（绿，x=0.32） |
| SEG-02 左支线 | 汇流口→远端（整条一段） | 畅通（绿，x=0.18） |
| SEG-03 右支线 | 汇流口→远端（整条一段） | 严重拥堵（红，x=0.93） |

大屏只有红绿两色，无黄色档。

### 已交付

- `work/twin/y_junction/`：几何导出（`export_geometry.py`）+ 自检门（`verify_geometry.py`）+ 基线生成（`make_y_junction_mock.py`），JSON 全部脚本产物不手改
- 站点包 Y（`stationY.ts` / `stationY.network.ts`）接入 pack 选择器，`npm run dev:y`（:6890）即看
- 「分左回右去」由每条路段的回方向（boundary，允许回灌）/去方向（internal，禁止）断面承载，共 6 断面
- 告警/分流建议/感知通道/推荐路线全部对新 ID 自洽

### 验证

- `python work/twin/y_junction/verify_geometry.py` 全过
- `vue-tsc` 0 错误、`npm run build` 通过
- 本地 dev 服务 `/api/traffic/network` 返回 3 路段，等级分布 = 畅通 2 + 严重拥堵 1

### 后续演进方向（业主原话："最简单的流程开始逐步到更多分支更多的线路"）

V0 = 3 路段最小闭环已立住；下一版按业主节奏在脚本链上加分支/线路即可（脚本链支持改参数重跑，产物不手改）。

---

## Issue IKLOL9 · [接口与双端] SUMO 真实画面接入控制大屏：大屏新增仿真画面面板（二维 · 带角标 · 可灰档）（L2）

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | L2 / 接口与双端 |
| 创建 | 2026-10-14T15:20:39+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLOL9 |
| 指派 | （无） |

### 正文

## 背景：业主 2026-10-14 口径，一条线拆三单

业主原话（口径）：「从画路线到导入 SUMO 正常运行到**能将 SUMO 的真实画面导入到控制大屏中来**，这是一条线」——**本单是第 3 单**，也是这条线的终点。

| 单 | 只做什么 |
|---|---|
| 单 1（同批发布） | 画路线 → 路网入库 → 导入 SUMO → 场景跑通（`work/twin/five_branch/`） |
| 单 2（同批发布） | 大屏吃这台仿真的**数值**：车点 / 线路同源（`/api/twin/*` + 站点包 B） |
| **本单（3）** | 把 **sumo-gui 渲染出来的画面（像素）** 搬进控制大屏 |

> ⚠️ **与单 2 的分界**：单 2 交付的是**车点与线路**（TraCI 坐标 + net 边链，前端 SVG 重画）；**本单交付的是"画面"本身**——`sumo-gui` 窗口里那幅图，原样（或抽帧后）显示在大屏上。**判定方式见下文第 3 节第 1 条：关掉 sumo-gui 进程，画面必须停更/消失，而 SVG 路网图照旧**——这一条就能证明"画的是真画面，不是又画了一遍"。

## 现状：仓库里**没有**任何一处把 SUMO 画面送进前端；但两侧的"砖"都齐了

**甲、今天的大屏与"画面"无关**（实测 `task/three-page-pipeline`）：大屏三栏全是 SVG —— 路段线（`NetMap.vue:410-446`）、车辆动点（`NetMap.vue:310-315` + `:528-535`，`<circle r="5.5">` + CSS `transition: transform 1.9s linear`）。**全仓 `views/dashboard/` 里 `img` / `video` / `iframe` / `canvas` 零命中。**

**乙、SUMO 画面在**本机**已经被抓过很多次，脚本也现成（但都不在仓库里）**：

| 现成的东西 | 在哪 | 关键结论 |
|---|---|---|
| `capture_gui.py`（TraCI 开 sumo-gui + `gui.setBoundary` 取景 + `gui.screenshot`） | `work/twin/netbuild/`，**未入库**（工作区版 `netbuild/README.md:182` 有它的用法） | **`traci.gui.screenshot` 只是登记请求，必须再走一次 `simulationStep` 文件才落盘**；`gui-settings-file` 里的 `<viewport>` 在 SUMO 1.28 上会被载入路网覆盖，程序化取景只能靠 `setBoundary`（脚本头 :1-13） |
| `sumo_preview/capture_gui.ps1`（Win32 `PrintWindow` 直接抓窗口） | 仓库外暂存目录 | **这台机器上 TraCI + sumo-gui 调 `screenshot` 会把 GUI 拖死**，所以当时改用抓窗口；`--delay 0` 会截到全白（暂存 README:141-143） |
| 手动开窗入口 | `work/twin/netbuild/sim/启动SUMO-中文.cmd`、`_station_map/sumo_preview/启动SUMO-中文.cmd` | `--language zh` 是切换中文界面的**唯一**办法（本机 `LANGUAGE=zh` 环境变量无效） |
| 非空白判据 | `work/assembly/技术栈.md:113` | 既有实测口径：「截图 1216×839、**458 种颜色**（非空白图）」——**本单沿用这个客观判据，不接受"看起来有图"** |
| **前端已有"JPEG 帧进浏览器"的先例** | `work/perception/server.py:91-98`（`GET /api/perception/streams/{sid}/frames/{n}.jpg` → `FileResponse(media_type="image/jpeg")`）+ `views/perception/components/MonitorCell.vue:91`（`<img>`） | 感知页就是这么显示样本视频抽帧的；**同一条形状可以直接搬到孪生侧**，不必新造轮子 |

**丙、口径上有一处必须显式处理的冲突（本单的第一个动作，见"卡在哪里"）**：

- `work/assembly/README.md:60` 明写：**「一期是非视频端点驱动的页面……它的结果以 `segments` 快照的形式进接口层（**不新增视频流 / 画面端点**）」**；
- `docs/技术方案与实施手册.md:2619`（风险表第 20 条）：「一期管理端**只做「地图 + 四级色 + 热力 + 点击看指标」**，**不做 3D 孪生大屏**」。

业主这次要的是**二维真画面**（不是 3D），性质上不撞风险表第 20 条的靶心；但它确实**超出了上面两句的字面范围**。**按仓库自己的规矩走修订流程，不靠"没人注意"混过去**——这就是本单的第一步交付。

## 要产出什么

### 1. 画面通道（**必须与数值通道并存，且互不拖垮**）

- 在**孪生侧**提供"最新一帧"的入口（建议沿用感知侧形状：`GET /api/twin/screen.jpg` 直接回 JPEG，`Cache-Control: no-store`，带帧时间戳）。
  - **建议放桥接服务**（`work/frontend/tools/twin_preview/server.py`）或用它旁边的一个小服务：它是**演示底座、不是契约端点**（实测：`docs/数据契约.md` 里**没有任何 `/api/twin` 端点**，契约第七节的 `/api/traffic/*` 是接口层的事）——**因此本单不动契约、不加契约端点**。
  - 做法**不锁死**（TraCI 截图 / 抓窗口 / 其他），在 PR 的「实现方式」栏申报「方式 + 为什么 + 契约与判定不变」。
- **数值通道不许退化**：车点仍来自 TraCI（`server.py:141-142`），`is_simulated` 仍在信封层（`server.py:84-88`），`GET /api/twin/vehicles` 的**刷新节奏与今天一致**（前端每 2 s 一拉、5 s 缓存，`mock/traffic.ts:359-363`）——**抓画面把仿真拖慢 = 本单不通过**。
- **帧产物不进仓库**：仓库至今 **0 张位图入库**（实测 `git ls-files` 里 `.png/.jpg` 命中 0），且 `scripts/doc_gate.py:62-71` 禁 `.mp4` + 单文件 > 2 MiB 报错。**帧/录屏落本地暂存或共享盘，README 写生成命令**（既有先例：`work/assembly/技术栈.md:121`「截图不进仓库」、[`docs/协作规范.md`](https://gitee.com/ozxowx/hubflow/blob/main/docs/%E5%8D%8F%E4%BD%9C%E8%A7%84%E8%8C%83.md) 第 8 节）。

### 2. 大屏上的画面面板（`work/frontend/ui-vue/src/views/dashboard/`）

- **不许动既有元素**：中栏「全路段状态」是手册 §11.2 点名的交付（路网图 + 四级着色 + 指标叠加），**一项都不能删**（判定 C-2 原文：「原七个 P0 页面逐条归入这三页、**一项未删**」）。画面面板**只能是新增**——推荐放**左栏「选择监控」之下**或**中栏可切换的一个视图**，具体位置由执行者在 PR 里说明。
- **必须有的标注**（缺一不通过）：
  - **M1-7 角标**「演示数据（模拟）· 双数据源（视频链路 + 孪生链路）」，**画面上要有**（不是页脚只有当页有）;
  - **帧时间戳 + 帧率**（"这一帧是什么时候的"），与页面其它数据的时间戳可对照；
  - **口径**：这是**仿真渲染画面**，**不得**出现「实测 / 实时 / 现场」，**不得**表述为"摄像头画面"。
- **降级不许白屏**（沿用 TC-11 的灰档精神）：面板抓不到帧时显示**灰色「画面不可用」**（含原因），**不得**停在旧帧上装作还在动。今天的先例是「桥接不在时页面自动回落站点包路网 + 合成车，不白屏」（`twin_preview/README.md:44`）——本单照此守住。
- 建议随手做掉的（**不算本单判定**）：一屏密度不被破坏（`work/frontend/README.md` §10.4 第 8 条：1440×900 无横向溢出、各栏独立滚动）。

### 3. 完成判定（**照抄既有条目 + 本单自己的两条客观判据，不新造编号**）

1. **本单专属判据一（"真画面"）**：**画面里显示的是 `sumo-gui` 渲染出来的像素**——判定操作：**关掉 sumo-gui 进程 → 画面停更/进入灰档；同页的 SVG 路网与车辆动点仍照常刷新**（两者行为不同即成立）。再加一条客观旁证：抓下来的帧按既有口径统计**颜色数**（非空白，参照 `技术栈.md:113` 的 458 色）。
2. **本单专属判据二（"同一场"）**：**画面里的路网，就是大屏旁边那 14 条 SEG 所在的那张 net**——用同一份 `hubflow_demo.{net.xml,sumocfg}`（单 1 产物），画面里能看见站前服务段的车流（截图留证）。
3. **手册 §11.2 / 判定 C-2**：三层 3 页可用，**一项未删**（画面是新增，不是替换）。
4. **M1-7**：画面与举证材料**100% 带角标**。
5. **TC-11 同口径**：画面不可用时显示灰色，不显示成"通畅/正常"。
6. **手册 §17 附录（性能 / 演示稳定性）**：抓画面不能把演示拖垮——录制一段连续动画：画面在刷、车点在动、热力带在更新，**三处同时在动**。

## 三 prerequisite

| | 内容 |
|---|---|
| **输入样例** | ① 单 1 的 net + `hubflow_demo.sumocfg` + 单 2 的桥接（数值通道）；② 现成抓画面脚本两版：`work/twin/netbuild/capture_gui.py`（TraCI）与暂存目录的 `capture_gui.ps1`（Win32 抓窗）；③ 感知侧的 JPEG 帧端点（`work/perception/server.py:91-98`）作为通道形状参照；④ 大屏现役三栏结构（`DashboardView.vue:566+`）与 `NetMap.vue` 的 SVG 渲染 |
| **输出样例** | 大屏上新增一个画面面板：**持续更新的 sumo-gui 画面**（带帧时间戳 + M1-7 角标）；桥接 / sumo-gui 停掉时进灰档；一段连续录屏（画面 + 车点 + 热力带同时在动）+ 两张对照截图（正常 / 灰档） |
| **自检脚本** | `npm run build`（含 `vue-tsc`，`work/frontend/ui-vue/`）+ 仓库根 `python scripts/doc_gate.py` 全绿；人工核：关进程停更（判据一）、颜色数非空白、角标在位、既有元素一项未删 |

## 依赖谁的什么

- **依赖单 1 的 net 与场景**、**依赖单 2 的桥接换网能力**（画面通道与数值通道必须指同一张网、同一个场景，否则"画面里跑的车"和"大屏上动着的车点"对不上，就白做了）。
- **不依赖** `work/assembly/traffic.py`（未实现）、**不动契约**（`docs/数据契约.md` 里没有 `/api/twin`，本单也不加）。
- 依赖大屏现役组件与站点包开关（`pack.bridge.enabled`，`stationB.ts:180`）——**画面面板也要受这个开关管**：包说"本站不接"，画面面板**不出现**（避免二站显示一站的画面）。

## 卡在哪里

1. **口径冲突要先走修订流程（本单第一步，别跳过）**：`work/assembly/README.md:60` 的「**不新增视频流 / 画面端点**」与`手册:2619`（风险表第 20 条）的「只做地图 + 四级色 + 热力 + 点击看指标」，与业主这次要的"真画面"字面上不一致。
   - **要做的事**：**先在本 Issue 评论里给出拟修订文本**（建议两处：手册修订表登记一条「2026-10-14 业主口径：控制大屏新增 SUMO 仿真画面面板（二维、非 3D、带角标、可灰档降级）」；`work/assembly/README.md:60` 那句**限定适用范围**为"契约接口层 `/api/traffic/*`"并注明画面通道走孪生演示服务、不进契约），**由区域 owner / 队长裁定后再动手**。
   - **不许**的做法：不声不响地把画面端点加进 `/api/traffic/*`（那是契约面，改契约要走契约流程）。
2. **抓取方式二选一，两条都有坑（都已实测）**：TraCI `gui.screenshot` 要**补一次 `simulationStep`**才落盘；但**这台机器上它会把 GUI 拖死**，当时改用 Win32 `PrintWindow` 抓窗。执行者**两种都试一遍并把结论写进 README**，别只看退出码。
3. **演示机可能没有可用的桌面会话**（无头 / 远程）：若 `sumo-gui` 开不了窗，**如实记录并按最简降级**（例如预录帧序列回放，面板与举证材料**必须标"预录回放"**）——**不得**把预录回放说成"实时画面"。
4. 卡住 30 分钟在 Issue 里 @队长。

## 交接留痕

认领者在评论里写：**交了哪个文件、对着哪条判定、过没过**。

### 评论（1 条）

**1 · @ozxowx · 2026-10-14T15:27:07+08:00**

## 同批三单（正文里「单 1 / 单 2」的直接链接）

- **单 1（本单的地基）**：[#IKLOB6 · 演示路网「一环五射」入库：画路线 → 导入 SUMO → 场景跑通](https://gitee.com/ozxowx/hubflow/issues/IKLOB6)
- **单 2（本单的前置：数值通道）**：[#IKLOJ6 · 「一环五射」SUMO 场景接控制大屏：桥接换网 + 车辆/线路同源](https://gitee.com/ozxowx/hubflow/issues/IKLOJ6)

**分界再强调一次（本单是终点，别做回到单 2）**：单 2 交付**数值**（车点 / 线路用 TraCI 坐标 + net 边链**重画**）；本单交付**像素**（sumo-gui 渲染出来的那幅画面本身）。**判据一**（关掉 sumo-gui → 画面停更即灰档，而 SVG / 车辆动点照旧）就是这条分界的客观检验。

**另记一处本单的已知边界**：画面通道**不进契约**——`docs/数据契约.md` 里没有任何 `/api/twin` 端点，本单也不加（画面走孪生演示服务，`/api/twin/*` 是演示底座）。**不许**把画面端点塞进 `/api/traffic/*`（那是契约面）。

**还有一条与已有单的关系**：[#IKLLWY](https://gitee.com/ozxowx/hubflow/issues/IKLLWY)（0-3A 真实 OSM）+ [#IKLLX2](https://gitee.com/ozxowx/hubflow/issues/IKLLX2)（0-3B `map_ingest.py`）是**引擎侧 OSM 主路径**，与本批三单的**大屏示意路网** 互不顶替（裁定全文见 [#IKLOB6 的评论](https://gitee.com/ozxowx/hubflow/issues/IKLOB6)）。

---

## Issue IKLOJ6 · [孪生与路况] 「一环五射」SUMO 场景接控制大屏：桥接换网 + 车辆/线路同源（L2）

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | L2 / 孪生与路况 |
| 创建 | 2026-10-14T15:16:31+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLOJ6 |
| 指派 | （无） |

### 正文

## 背景：业主 2026-10-14 口径，一条线拆三单

业主原话（口径）：「从画路线到导入 SUMO 正常运行到能将 SUMO 的真实画面导入到控制大屏中来，这是一条线」——**本单是第 2 单**：把「一环五射」这套 SUMO 场景**接到控制大屏**。

| 单 | 只做什么 |
|---|---|
| 单 1（同批发布） | 画路线 → 路网入库 → 导入 SUMO → 场景跑通（`work/twin/five_branch/`） |
| **本单（2）** | **大屏真的吃这台仿真**：站点包 B 的桥接打开，车辆 / 线路同源，跨站 id 对得上 |
| 单 3（同批发布） | **SUMO 真实画面（像素）** 接进大屏 |

> ⚠️ **两单的分界，先看这一句**：**本单只做"数据同源"——车点与线路都来自 SUMO 的数值输出（TraCI 位置 + net 边链）**，这是今天大屏的做法（SVG 重画）。**把 sumo-gui 渲染出来的画面（像素）搬上大屏，是单 3，不在本单**。两单都叫"接到大屏"，**别做重了**。

## 现状（对 `task/three-page-pipeline` 实测）

**甲、站点包 B 现在明确写着"不接桥接"**（`work/frontend/ui-vue/src/station-packs/stationB.ts:180`）：

```ts
// 本站**不接**孪生桥接服务:work/frontend/tools/twin_preview 跑的是肇庆东站的 OSM 切片,
// 与本站示意路网对不上。开它会把别站的车辆坐标画到本站图上(口径事故),所以关掉走合成车。
bridge: { enabled: false, base: '' },
```

于是二站现在是：**图是一环五射、线是真的（`stationB.network.ts`），车是合成车**（`mock/traffic.ts:278-299` `buildVehiclesSnapshot()` —— 按 `offset_m + speed × 2 × tick` 沿段折线滑，注释自称"演示观感，**非仿真输出**"）。**这正是本单要消掉的"看起来像"。**

**乙、桥接服务本身是单站写死的**（`work/frontend/tools/twin_preview/server.py`）：

| 行 | 现状 |
|---|---|
| `:49-51` | `NET_FILE = netbuild/net/zqns_tuned.net.xml`、`CONFIG_FILE = netbuild/sim/zqns_demo.sumocfg`、`ASSIGN_FILE = netbuild/out/segment_assignment_zqns.json` —— **三个常量写死，只有肇庆东这一套** |
| `:189` | `sumolib.checkBinary("sumo")` —— **无界面** TraCI，无画面通道 |
| `:253` | `uvicorn.run(app, host="127.0.0.1", port=8102)` —— **只有回环**、端口写死 |
| `:84-88` | 全部响应走 `_envelope`，`is_simulated: True` 在信封层（口径正确，保留） |
| `:141-142` | `traci.vehicle.getPosition(vid)` + `net.convertXY2LonLat` —— 车辆坐标的来源（**数值真值**，不是像素） |
| `:163` | `"is_demo_bound": False` —— **写死**（另一单已跟踪，本单不重开） |

**丙、前端接入方式已经现成**（单 1 之外**不用动**）：`main.ts:20-39` 拉 `/twin-api/network` 覆盖路网、`mock/traffic.ts:352-383` 拉 `/api/twin/vehicles`、`vite.config.ts:35-38` 有 `/twin-api` 代理；**是否拉由站点包开关决定**（`pack.bridge.enabled`）。本单要做的是**让二站这套配置成立**，不是重写接入层。

**丁、还差一块拼图：车辆 → 路段的归属表**。桥接判断"车在哪条 SEG"读的是 `assign_segments.py` 的产物（`work/twin/netbuild/out/segment_assignment_zqns.json`，内含 `SEG → SUMO 边链` 映射）；**一环五射那张网没有这份映射**（实测：`_station_map/five_branch/` 里无任何 assignment 类产物，`export_network_json.py:45-63` 的 SEG→边链分组只活在导出脚本的常量表里）。没有它，桥接只能走 `_nearest_segment()`（就近吸附），**那是估算不是真值**，不满足手册 §9.1「一期直接用孪生真值……精度=真值」。

## 要产出什么

### 1. 桥接服务支持"换一张网 + 一套场景"（`work/frontend/tools/twin_preview/server.py`）

- **三个常量改成启动参数 / 环境变量**（net / sumocfg / assignment 三件一起换，缺一不可）；**默认值保持现状**（不传参就是肇庆东那一套，向后兼容）；
- **端口 / bind 可配**（默认仍是 `127.0.0.1:8102`）—— 建议二站换个端口（如 `8103`），好让两站能同时开、对着比；
- 做法**倾向但不锁死**：`argparse` 或环境变量都行，按 [`docs/开发规范.md`](https://gitee.com/ozxowx/hubflow/blob/main/docs/%E5%BC%80%E5%8F%91%E8%A7%84%E8%8C%83.md) 文首总原则在 PR 的「实现方式」栏申报「方式 + 为什么 + 契约与判定不变」。
- **口径红线**：**不许为二站加专用分支**——桥接只认"net + 场景 + 映射表"三件输入，**站点名、坐标、路名一个都不许出现在代码里**（手册 §8.4 / M1-1 同口径）。

### 2. 车辆 → 路段真值映射（本单前置，落在 `work/twin/five_branch/`）

- 在 five_branch 下补一支与 `netbuild/assign_segments.py` 同口径的脚本（或把它通用化后复用），产出 **`SEG → SUMO 边链`** 的 JSON；
- **不许改站点包 B 的数值**：`stationB.network.ts` 的几何/基线一字不动，本单只补"车辆归属哪条 SEG"这一张映射表（`assign_segments.py` 自己就是这么定位的：**只改几何与名称，不动任何数值基线**）。
- **实际可行性判断（先看这条再动手）**：一环五射的 SEG 划分与 SUMO 边 id 是**同源命名**的（`export_network_json.py:45-63` 里 `SEG-001 → SR01…`、`SEG-005 → E1_1,E1_2`，而 `network/hubflow_demo.net.xml` 里的边 id 就叫 `E1_1` / `E2_2` / `UG3` / `TX1`…）。所以映射**大半能从现有命名直接推出来**；推不出来的部分（如 SEG-001 站前路那 6 条 `SR*` 边）**必须对着 `net.xml` 逐条核**，**不许猜**——`verify_network.py` 已有连通性自检门，映射表也要有自己的自检（**每条 SEG 至少能命中一辆车的边**，或如实记录"该 SEG 本次无车"）。

### 3. 站点包 B 打开桥接（`work/frontend/ui-vue/src/station-packs/stationB.ts:180`）

- `bridge: { enabled: true, base: '<本单桥接地址>' }`；**站点包 A 的行为一字不动**（两站仍然各接各的）。
- **同时改掉那条注释**——原文写着"不接桥接"的理由（别站路网），本单正是把它修好的那一单，注释要与新事实一致。
- **`is_demo_bound` 的归属**：桥接侧写死 `False` 是既有缺口，**另一条单已跟踪**（`is_demo_bound` / 演示车口径）。本单**不修改桥接的演示车口径**，如遇 M1-5 举证需求，按那条单的结论执行。

### 4. 五条件实测 + 举证材料

**这一条就是本单的"完成判定"**（下面第 3 节的五条）：

1. **车真的在 SUMO 里**：大屏上某辆车（例如 `1000_bus.5` 这类真 id）的位置能在**同一时刻**的 `GET /api/twin/vehicles` 响应里找到同一条记录（`vehicle_id` 逐字一致）；
2. **车永远在路上**：该车 `segment_id` 是**真值映射**得出的（不是就近吸附），且把桥接停掉后**大屏回落合成车**——两种状态观感不同、可区分；
3. **线路同一张网**：大屏 `/dashboard` 的 14 条 SEG 几何与桥接 `/api/twin/network` 返回的 coords 逐点一致（或说明为什么允许差异）；
4. **同一场景**：`segment_id` 命中的边链，就是 `hubflow_demo.sumocfg` 实际跑的那张网（不是另一份）；
5. **口径**：页面标"演示数据（模拟）"、`is_simulated: true` 可追溯；**不得**出现"实测 / 实时 / 现场"。

## 三 prerequisite

| | 内容 |
|---|---|
| **输入样例** | ① 单 1 的 `work/twin/five_branch/`（`network/hubflow_demo.net.xml` + `hubflow_demo.sumocfg`）；② 现成的单站桥接与本单要改的三行（`server.py:49-51`）；③ 现成映射表样例（`work/twin/netbuild/out/segment_assignment_zqns.json`，10 条 SEG 的 coords + edge_ids）；④ 站点包 B 的 14 条 SEG 定义（`stationB.network.ts`） |
| **输出样例** | 二站大屏：14 条线**来自 SUMO 同一张网**、车点**来自 TraCI 真值**；同一时刻的 `/api/twin/vehicles` 响应 JSON 归档；桥接停掉后回落合成车（对照截图各一张，带角标） |
| **自检脚本** | `npm run build`（含 `vue-tsc`，`work/frontend/ui-vue/`）+ 仓库根 `python scripts/doc_gate.py`；人工核：五条件逐条过、`git diff` 里 `work/twin/netbuild/` 无改动 |

## 完成判定（**照抄既有条目，不新造编号**）

| 条目 | 原文口径 | 本单怎么算过 |
|---|---|---|
| **手册 §9.1（一期：直接用孪生真值）** | 「位置从哪来：**TraCI 直接读**；'在哪条路上'：**直接已知（真值）**，无需地图匹配；精度：**真值**」 | 车点与 `segment_id` 都出自桥接真值；**断言映射表存在且被使用**（不是 `_nearest_segment` 估算） |
| **手册 §4.3 / §9 接线点** | 快照文件（`vehicles.json`）当契约、端点只读快照 | 桥接出的字段与契约 v2.0 §四逐字一致（现有 `_read_vehicles` 已合规，**别改字段**） |
| **分工表 §8.1 W1** | 「站前路网能在 SUMO 里跑起来（**M1-1 前半**）」 | 单 1 的地基 + 本单"这套场景真的在喂大屏" |
| **手册 §8.4 / M1-1 判定** | 「引擎代码里不出现任何站点名、坐标、路名硬编码」 | 桥接的换网改造**不得**引入二站专用分支；grep 不到站点名 / 坐标 |
| **M1-7** | 举证材料角标「演示数据（模拟）· 双数据源（视频链路 + 孪生链路）」，抽查 100% 命中 | 两张对照截图都带角标 |
| **口径红线** | 「不把孪生算出来的数说成实测」（分工表 §8.1 W9） | 页面与举证材料不出现"实测 / 实时 / 现场" |

## 依赖谁的什么

- **依赖单 1 交付**（`work/twin/five_branch/`：net + sumocfg + 自检门）——**单 1 没合之前，可以拿站点包 B 现有的 `network.json` 与暂存目录的产物先把映射表与桥接改造做通**，别停工等。
- 依赖 `vite.config.ts` 的 `/twin-api` 代理（现成）、`main.ts` 的 `loadTwinNetwork()`（现成）、`mock/traffic.ts` 的桥接读取（现成）——**这三处本单不改形状**。
- **不依赖 `work/assembly/traffic.py`**（尚未实现；接口层落地后形状不变）。

## 卡在哪里

1. **一处口径要留意（不阻塞）**：桥接现在把 `driver_type` 做 **5 类 → D1/D2** 的粗化（`server.py:58-64`、注释自称"已知的粗化，不装作 1:1"）。一环五射有 7 类车，映射到契约的 D1/D2/D3 时**细档更多**——按现有口径**照做并如实标注**即可，**不扩契约**（契约字段改动归契约裁定人，当天 Issue 留痕）。
2. **`_nearest_segment` 兜底**：映射表做全后，兜底逻辑**保留但降级为"异常时兜底"**，并在日志 / README 里能看出**这一次有没有用到估算**——否则"真值"两个字站不住。
3. 卡住 30 分钟在 Issue 里 @队长。

## 交接留痕

认领者在评论里写：**交了哪个文件、对着哪条判定、过没过**。

### 评论（1 条）

**1 · @ozxowx · 2026-10-14T15:21:29+08:00**

## 同批三单的相关单（正文里「单 1 / 单 3」的直接链接）

- **单 1（本单的前置）**：[#IKLOB6 · 演示路网「一环五射」入库：画路线 → 导入 SUMO → 场景跑通](https://gitee.com/ozxowx/hubflow/issues/IKLOB6)
- **单 3（画面粉丝通道，别与本单做重）**：[#IKLOL9 · SUMO 真实画面接入控制大屏](https://gitee.com/ozxowx/hubflow/issues/IKLOL9)

**分界再强调一次**：本单交付**数值**（车点 = TraCI 坐标、线路 = net 边链，前端 SVG 重画）；单 3 交付**像素**（sumo-gui 渲染画面）。**本单不许在 `/api/twin/*` 上加画面 / 截图端点**——那是单 3 的范围。

**另有一处与「真路网主路径」的边界**（业主中途提示后已裁定）：[#IKLLWY](https://gitee.com/ozxowx/hubflow/issues/IKLLWY)（0-3A 真实 OSM → `stations/sumo/*.net.xml`）与 [#IKLLX2](https://gitee.com/ozxowx/hubflow/issues/IKLLX2)（0-3B `map_ingest.py` → `stations/network.json`）是**引擎侧的 OSM 主路径**，本单是**大屏二站的示意路网**，**两条线互不顶替**。裁定全文见 [#IKLOB6 的这条评论](https://gitee.com/ozxowx/hubflow/issues/IKLOB6)。

---

## Issue IKLOB6 · [孪生与路况] 演示路网「一环五射」入库：画路线 → 导入 SUMO → 场景跑通（仓库内可重建）（L1）

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | L1 / 孪生与路况 |
| 创建 | 2026-10-14T15:06:19+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLOB6 |
| 指派 | （无） |

### 正文

## 背景：业主 2026-10-14 口径，把一条线拆成三单

业主原话（口径）：「**从画路线到导入 SUMO 正常运行到能将 SUMO 的真实画面导入到控制大屏中来，这是一条线**」——拆成三单发布。**本单是第 1 单。**

| 单 | 只做什么 | 交付物落点 |
|---|---|---|
| **本单（1）** | **画路线 → 路网入库 → 导入 SUMO → 场景跑通**（仓库内可一键重建） | `work/twin/five_branch/`（新增）+ 线路图 + 干净运行记录 |
| 单 2（同批发布） | 把本站这套 SUMO 场景接到**控制大屏**（车辆 / 线路同源） | 桥接服务 + 站点包 B 配置 |
| 单 3（同批发布） | 把 **SUMO 的真实画面**（sumo-gui 渲染出来的像素）接进控制大屏 | 画面通道 + 大屏组件 |

## 现状：这条链跑通过一次，但产物全在仓库外、且是半成品

`_station_map/five_branch/`（**与仓库同级的本地暂存目录**，未入库；仓库里已有引用先例，见 `work/frontend/ui-vue/src/station-packs/stationB.network.ts` 文件头的生成命令）里有成套脚本与产物：

| 脚本 | 输入 → 输出 |
|---|---|
| `build_network.py` | 自绘 NODES / EDGES / CONNS → `network/hubflow_demo.{nod,edg,con}.xml` → `netconvert` → `hubflow_demo.net.xml` |
| `verify_network.py` | 自检门：20 个站外端 OD / 25 进场 / 25 出场 / 环路两圈逐段贯通 / 无死边（不通过非 0 退出） |
| `build_scenario.py` | 7 类虚拟车流 → `duarouter` → `virtual_traffic.rou.xml` → 跑 SUMO 出 `fcd.xml` / `tripinfo.xml`（支持 `DEMAND_SCALE` 倍率） |
| `draw_network.py` | `net.xml` → `figures/*.png`（深色演示版 / `--light` 打印版） |
| `export_network_json.py` / `make_station_pack.py` | → 前端 `network.json` / `stationB.network.ts`（**已接进管理端**，是站点包 B 的来源） |

**三个问题**（本单就是解决这三个）：

1. **不在仓库里**——别人拿不到、复现不了、审不了；
2. **写死本机路径**：`build_network.py:60` / `build_scenario.py:40` 都是 `SUMO_HOME = Path(r"D:\app\SUMO")`，换台机器直接废；
3. **"跑通"没有干净证据**：现存 `fcd.xml` / `tripinfo.xml` 是**跑动中被中断的半成品**（末步 t=460 且无收尾标签），仓库里也没有任何一份完整运行记录。

## 要产出什么

1. **入库**：整套生成侧迁进 `work/twin/five_branch/`（与 `work/twin/netbuild/` 的 OSM 管线**并列、互不覆盖**；两者口径不同——netbuild 是"OSM 真路网"，本目录是"凭空造的示意路网"，README 第一段必须写清这层区别）。
   - **脱盘符**：SUMO 路径改读环境变量 `SUMO_HOME`（缺失时给可操作的报错，不静默失败）；脚本里**不得**再出现任何盘符或本机绝对路径。
   - **产物分层**：`network/*.net.xml`（105 KB，可入库）进仓库；`fcd.xml`（24.5 MB）/ `fcd_scale5.xml`（236 MB）/ MP4 **一律不进仓库**（`scripts/doc_gate.py:62-71` 禁入 `.mp4` 且单文件 > 2 MiB 报错），放共享盘 / 本地暂存目录，README 写清路径与生成命令。
2. **线路图**：`draw_network.py` 两版 PNG 重新生成（单文件 < 2 MiB，可入库）；`make_animation.py` 的 MP4 属可选交付（不入库）。
3. **场景与"正常运行"**：`build_scenario.py` 一键出车流 + 跑 SUMO；**本单必须留下一次从头到尾跑完的干净证据**（下节"完成判定"）。
4. **文档**：`work/twin/five_branch/README.md`（迁移版，含一键复现序列、两条几何纪律、契约映射与口径红线）+ 在上层 README（`work/twin/README.md` 或 `work/twin/netbuild/README.md`）加一行指向本目录。

## 三 prerequisite

| | 内容 |
|---|---|
| **输入样例** | 暂存目录里的 `build_network.py` / `verify_network.py` / `build_scenario.py` / `draw_network.py` 原样（**只搬不改语义**）；`network/hubflow_demo.net.xml`（现成产物，可作重建比对基准）；`work/twin/netbuild/README.md`（写法参照：脚本怎么组织、产物怎么分层、README 怎么写） |
| **输出样例** | `work/twin/five_branch/` 全套（脚本 + `network/` + `figures/`）+ 一份运行记录（命令、`netconvert` 汇总、`sumo` 退出码、tripinfo 统计、两次跑一致性） |
| **自检脚本** | 见下节；核心三条：`netconvert` Success、`sumo` 退出码 0 且 tripinfo 有收尾标签、**删掉产物能一键重建** |

## 完成判定（**照抄既有条目，不新造编号**）

1. **手册 §1.4 / §3.1 已定方向**：「交通仿真引擎 **SUMO（含 netconvert / duarouter / traci）**，**一期必装**，一期主链路就是孪生驱动」——本单是这条主链路在**演示路网**上的第一段。
2. **分工表 §8.1（开发A）W1 判定原文**：「站前路网能在 SUMO 里跑起来（**M1-1 前半**）；**转换命令写进脚本**，删掉产物能一键重建；路网统计两次运行一致（随机种子写进场景输入文件）」。
3. **本单必须交出的干净证据**（现存产物是半成品，不能拿它顶）：
   - `netconvert` 日志末行 `Success.`；
   - `sumo -c hubflow_demo.sumocfg` **完整跑完**（到 `SIM_END`），`tripinfo.xml` **有收尾标签**、到达数与自检门口径一致（现基线：**189 / 190**，`seed=42`、`step 0.5 s`、`SIM_END=1800`）；
   - **同种子跑两遍，关键指标一致**（M1-1 的"同种子同输入同输出"性质）；
   - 车**真的在动**：不能只看退出码——给一段录屏或两张不同时刻的画面截图（带 M1-7 角标）。
4. **可重建**：删掉 `network/*.net.xml` 与场景产物重跑一遍，结果与记录一致（差异要有解释并写进记录）。
5. **口径**（红线，违反即不通过）：
   - 路网是**纯虚构示意**（业主 2026-10-12 定「不出真实数据的地图」）：`origin: "demo"`、坐标是占位锚点、**图上任何一点都不是真实地点**，站名不得改成任何像真站的名字；
   - `is_simulated` 恒为 `true`；**不得**称实测 / 实时 / 现场；
   - **内部断面（站前服务段）一个都不许挂校准器**（TC-20 第②项；`five_branch/README.md` 第八节已有此口径，迁移时保住）；
   - **本单不重算站点包 B 的数值基线**：`stationB.network.ts` / `stationB.ts` 不在本单范围。若执行者发现必须重算（例如改了步长），**另开一条**并同批处理 `docs/填表报告.md` 台账行（填表报告 §3.1 的 `占位` / `已转` 口径，门禁第 7 组按"最新覆盖行"逐产物检查）。

## 已实测的现状（省得从零试）

| 项 | 实测 |
|---|---|
| 规模 | **41 节点 / 77 车行边 / 18 235 m**；`network/*.net.xml` 105 KB |
| 车流 | 190 辆 7 类（过境 70 / 地下送客 40+16 / 出租接客 30 / 公交 8 / 社会停车 14 / 出租蓄车 12），起终点全部落在 5 条放射路**站外端** |
| 自检门 | `verify_network.py`：20 OD / 25 进场 / 25 出场 / 环路两圈 / 无死边 |
| 两条几何纪律（**上一版翻过车，别"顺手优化"回去**） | ① 放射路**必须垂直于环路**接入——45° 斜接会形成 135° 掉头式左转，`netconvert` 直接拒绝建连接；② 场区支路的**进口与出口各占一个节点**——共用一个节点时报 `Lane ... is not connected from any incoming edge` |
| 契约映射 | `network.json` 顶层 `origin: "demo"`；断面 `role`：`boundary` = 5 条放射路站外端（**数据同化唯一入口**）、`internal` = 站前服务段（**不挂校准器**） |

## 依赖谁的什么

- **不依赖任何其他单**：脚本与产物都在本机、SUMO 已装（`work/assembly/技术栈.md` 记着实测）。
- 依赖 `work/twin/netbuild/`（OSM 管线，**只读参照**；**不许改动它**，它的 scope 只有 `gzns` / `zqns` 两个）。
- 兄弟单 2 / 3 **反过来依赖本单**：场景与本单的 net 是它们的地基。

## 卡在哪里

1. **一处待裁定（不阻塞开工，但必须在 Issue 评论里定下来）**：`hubflow_demo.sumocfg` 现在 `step-length = 0.5 s`，而手册把「**仿真步长 1 s** 与单一仿真时钟」列为**锁定项**（§10.9 与 §附录「锁定」清单）。两条路择一，并在 Issue 评论里说明选了哪条、为什么：
   - (a) 把演示场景步长改为 **1 s** 后重出 FCD / 基线——**会改站点包 B 的数值**，须另开单 + 填表报告；
   - (b) 保留 0.5 s，在 PR 里申报为"演示场景步长"，并请区域 owner 把这条差异提到手册修订（修订表登记）。
2. **产物体积**：FCD 几十到几百 MB，`doc_gate.py` 第 2 组会直接拦；**别试图入库**，走共享盘。
3. 卡住 30 分钟在 Issue 里 @队长（别闷头耗）。

## 交接留痕

认领者在评论里写：**交了哪个文件、对着哪条判定、过没过**。

### 评论（2 条）

**1 · @ozxowx · 2026-10-14T15:19:14+08:00**

## 与既有单的关系（业主 2026-10-14 中途提示：「#IKLLX2 和 #IKLLWY 好像就是关于这个方面的」）

业主提醒得对，**方向上是同一件事**（路网 → netconvert → SUMO 可跑），但**对象与范围不同**，两条线各自独立推进，**不要合并、也不要互相顶替**。逐条说清：

| | 本单（#IKLOB6） | [#IKLLWY](https://gitee.com/ozxowx/hubflow/issues/IKLLWY)（阶段0·0-3A）+ [#IKLLX2](https://gitee.com/ozxowx/hubflow/issues/IKLLX2)（阶段0·0-3B） |
|---|---|---|
| 路网从哪来 | **凭空造**的演示示意路网（业主 2026-10-12 定「不出真实数据的地图」） | **真实 OSM 切片**（肇庆东站，站前 1.5 km × 1.5 km） |
| 谁画的 | `build_network.py` 里的 NODES / EDGES / CONNS 常量，手写坐标 | Overpass 下载 + `netconvert`，缺失路段在 netedit 里补画 |
| 产物 | `work/twin/five_branch/network/hubflow_demo.net.xml` + 前端 `stationB.network.ts`（**已接进管理端**） | `stations/sumo/station.net.xml` → `stations/network.json`（统一图结构 `{nodes, edges}`） |
| 消费方 | 控制大屏的**第二个站**（站点包 B） | **引擎**（`work/engine/`）认的唯一路网形状 |
| 现状 | 脚本与产物都在**仓库外的暂存目录**，且 SUMO 产物是半成品 | 实测对 `main` 与 `task/three-page-pipeline`：**`stations/sumo/` 与 `work/engine/map_ingest.py` 都还不存在**（两单都未开工） |

**三条边界（本单照此执行，也请 0-3A / 0-3B 的执行者照此）**：

1. **本单不碰 OSM 主路径**：不改 `work/twin/netbuild/` 的 scope（只有 `gzns` / `zqns`），不写 `stations/`，不产出 `stations/network.json`——本单的 `network.json` 是**演示导出件**（顶层带 `origin: "demo"`、坐标是占位锚点不做配准），**不是** 0-3B 的统一图结构，两者形状与用途都不同。
2. **一个命名坑，先说在前面**：#IKLLWY 的「输出样例」里写的是 `work/twin/netbuild.py`（**单脚本**），而仓库里现役的是 `work/twin/netbuild/`（**包**，OSM → netbuild → 前端几何的通用管线）。**同名不同物**，两个执行者各自认准自己的那个；真要合并成一份，作为独立一单议，别顺手改。
3. **互不阻塞**：本单不需要等 0-3A/0-3B（我的输入是自绘脚本与 netconvert）；反过来也一样。

> 结论：**0-3A/0-3B 是"真路网主路径"（引擎侧），本单是"演示示意路网"（大屏二站侧）**。M1-1 那条「引擎代码里不出现任何站点名、坐标、路名硬编码」对**引擎**成立；本单的演示脚本里可以有自绘坐标（它本来就是凭空的），但**坐标必须带 `origin: "demo"` 与"未配准"标注**，不许拿去当真实地点用。

**2 · @ozxowx · 2026-10-14T15:21:20+08:00**

## 正文一处事实更正（我发布前自己核漏了，先纠正，别让执行者按错的现状去干）

正文「现状」第 3 条与「完成判定」第 3 条写的是：**「现存 `fcd.xml` / `tripinfo.xml` 是跑动中被中断的半成品（末步 t=460 且无收尾标签）」**——**这句说错了一半**，把**两个不同目录**的东西并成了一句。实测（2026-10-14，逐文件读字节）：

| 文件 | 大小 | 条数 | 收尾标签 | 判定 |
|---|---|---|---|---|
| 本单关心的 `five_branch/tripinfo.xml` | 83,027 B | **189** 条 | **有** `</tripinfos>` | ✅ **完整跑完** |
| 本单关心的 `five_branch/fcd.xml` | 24,501,235 B | 末步 `t=1799.5` | **有** `</fcd-export>` | ✅ **完整跑完** |
| `five_branch/tripinfo_scale5.xml` / `fcd_scale5.xml` | 332 KB / 236 MB | 762 条 | **都有**收尾标签 | ✅ 完整 |
| ⚠️ `work/twin/netbuild/sim/out/tripinfo.xml` | 18,916 B | **39** 条 | **无**收尾标签 | ❌ 半成品 |
| ⚠️ `work/twin/netbuild/sim/out/summary.xml` | 120,711 B | 末步 `t=460.00`、`running=113` | **无**收尾标签 | ❌ 半成品 |

**结论**：那两份「t=460 截断」的半成品在**另一条线**（肇庆东 `netbuild/sim/out/`，那是 `make_demo.py` 生成场景时的中间物），**跟本单的「一环五射」无关**。**本单的现存产物是完整的、189/190 到达与 README 记载一致。**

## 这对本单的实际影响（照这条办）

1. **「半成品」这条理由撤掉**，本单需要交出的干净证据**仍然成立**，但理由换成这两条：
   - **没有运行记录**：仓库里没有任何一份命令 / 退出码 / 统计的留痕，**"跑通过"目前只活在口头与产物里**（`verify_network.py` 是连通性自检门，**不等于跑过 SUMO**）；
   - **不可复现**：脚本不在仓库、SUMO 路径写死本机盘符 —— 别人拿到 `tripinfo.xml` 也**证不出**它出自哪份脚本、哪个种子。
2. **判定第 3 条的要件一字不改**（`netconvert` Success / 跑到 `SIM_END` 且 tripinfo 有收尾标签 / 同种子两遍一致 / 画面留证）——**只是不再宣称"现存产物是坏的"**；执行者**可以从现有产物出发**（它就是基准），**但必须自己重跑一遍并留记录**。
3. **一句话口径**：**产物可信，证据不可信**——本单补的是证据链（脚本 + 复现命令 + 运行记录），不是修数据。

> 另注：`work/twin/netbuild/sim/out/` 那两份截断产物**不在本单范围**（归 OSM 管线那条线），发现即记，**不要顺手去跑它**。

---

## Issue IKLLXT · [决策与定位 + 判级] PR #82 兜底审遗留五项：--sample 输出口径三处 + 登记口径两处（L1）

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | L1 / 决策与判级 |
| 创建 | 2026-10-14T11:22:31+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLLXT |
| 指派 | W2652201498 |

### 正文

> **本单自 GitHub 旧 Issue #94 重建**（2026-10-14 迁到 Gitee 后恢复）：标题、正文与当时的评论原文见仓库 [`docs/历史台账/`](https://gitee.com/ozxowx/hubflow/tree/main/docs/历史台账)，**原文照录、未改口径**。文档里所有 `Issue #94` 引用指的就是本单的前身。

---

## 要产出什么

`work/engine/run.py` 的 `--sample` 路径三处输出口径修正 + 两处登记口径补齐。**都是 PR #82 兜底审确认的遗留项**，不阻塞 #82 合入（`--sample` 产物 `out/` 不进仓库、`routes.json` 目前无消费方），但 W3 接口层接进来之前必须修掉，否则会带偏下游。

## 背景

PR #82（Issue #39，W0 骨架）已合入 `main`。审查中发现 3 处输出与契约不符 + 2 处登记口径未走完，当时按"W0 只定结构与骨架"的范围放行，转本单跟进。**逐字可用的改法已写在 PR #82 的评论里**（[#82 comment](https://github.com/ouu2006/hubflow/pull/82#issuecomment-6146562926)），下面只列判定。

## 三 prerequisite

| | 内容 |
|---|---|
| 输入样例 | `work/engine/samples/{network,demand,segments}_sample.json`；`stations/points.json`（点位表，已有 `point_id` / `type` / `segment_id`） |
| 输出样例 | `work/engine/out/routes.json`（改后 `dropoff_point` 应为点位 id、`driver_type` 按终点类型分 D1/D2、`why` 里带离站路线诊断） |
| 自检脚本 | `python work/engine/run.py --sample` + 人工核 `out/routes.json` 四条 OD |

## 完成判定

1. **`dropoff_point` 写点位 id，不写图节点 id**：`run.py:140` 现在输出 `"N-04"`（图节点 id），契约第二节示例是 `"DROP-03"`（点位 id），`stations/points.json` 里对应 `P-02`（`type=pickup`、`segment_id=SEG-004`）。改法：按 `segment_id` + `type` 从 `points.json` 查 `point_id`；**查不到给 `null` 并在 `why` 里写明"点位未在站点包登记"，不得退回图节点 id**（引擎里不许出现站点相关的字符串常量）。
2. **`driver_type` 按终点类型推，不再一律 `D1`**：样例 `OD-02` 的 `direction` 是「进场-上客」、终点是 `pickup` 型节点，现在被写成 `D1`（送客）+ `dropoff_point` —— 上客行程被描述成落客。终点 `type == "pickup"` → `D2`；`D3`（往返）样例里没有，可不处理。
3. **`departure_route` 不静默置 `null`**：`run.py` 有三个分支都落到 `None`（`exit_node` 缺失 / 不在图里 / 等于 `dst`，以及 `dep` 为空）。契约标它**必填**、TC-12 要求必现。**建议把原因并进现有 `why` 字符串**（不加新字段，省一次契约变更）。
4. **`docs/填表报告.md` 台账里 PR #82 那行的 `结果` 由 `已核对` 改为 `占位`**：九件是 W0 结构骨架、不是任何表格转出来的（表格实体见 #43），"对着表格复核"没发生。`占位` 的口径见填表报告 §3.1（PR #92 已合入 `main`）。**台账只追加**：以后真表到位、脚本重跑出第一版，另加一行 `已转`，这行留着。
5. **契约变更补留痕 + 升版本号**：`docs/数据契约.md` 第九节要求「**当天**在 Issue 里说清 + 由开发B 裁定后**升版本号**」。PR #82 把理由写在 PR 里（完整），但 **Issue #39 里没留评论、版本号仍 `v2.0`**。两处变更（`thresholds.json` 两组顶层键名定稿 `grading` / `decision`；`demand.json` 的 `od[]` 新增 `exit_node`）建议升 **`v2.1`**（都是加字段 / 定留白，兼容纪律没破）。**注**：Issue #39 的 assignee 就是作者、原文写明「你是契约唯一裁定人」，所以裁定权在他，只欠这两步动作。

## 依赖谁的什么

- 第 1 条依赖 `stations/points.json` 的点位表（已在 `main`）；
- 第 4 / 5 条依赖 `docs/填表报告.md` V1.1 与门禁第 7 组（PR #92 已合入 `main`）；
- 第 2 / 3 条无依赖。

## 卡在哪里

无。

---

> **口径声明**：本单**不动契约字段形状**（第 5 条只是补版本号与留痕）；`routes.json` 的必填清单一字不改；TC / M1 / M2 编号与数值一字未动。

### 评论（2 条）

**1 · @ozxowx · 2026-10-14T11:24:22+08:00**

> 以下为 **GitHub 旧 Issue #94 的历史评论**，自本机会话记录恢复、原文照录。

---

本单从 **PR #82**（Issue #39，W0 骨架，已合入 main）的兜底审遗留项转出。逐字可用的改法在 [#82 这条评论](https://github.com/ouu2006/hubflow/pull/82#issuecomment-6146562926) 里。**第 4 / 5 条与 #82 是同一批登记口径**（台账用词 + 契约升版本），可以和第 1~3 条的代码改法一起走一个 PR。

**2 · @W2652201498 · 2026-10-14T17:57:07+08:00**

## 契约变更留痕（Issue #IKLLXT 第⑤条）

`docs/数据契约.md` 第九节要求「**当天**在 Issue 里说清：改哪个字段、为什么、谁需要跟着改；由开发B 裁定后升版本号」。PR #82 当时把理由写在 PR 里（完整），但 **Issue 没留评论、版本号仍是 `v2.0`** —— 本评论补这一步。**版本号已升 `v2.0` → `v2.1`**（PR #8，分支 `task/94-pr82-backlog`）。

### 要登记的两处变更（**均已由 PR #82 落进契约 6.3**）

| # | 改了什么 | 为什么 | 谁需要跟着改 |
|---|---|---|---|
| ① | `thresholds.json` 的**两组顶层键名定稿为 `grading` / `decision`** | 契约第六节原文把这两组键名**留白**，明写"由开发B 在 W0 定结构时确定并写进本节"。不用 `level` 是因为它与 `segments.json` 里 1~4 那个**等级值**字段同名，会读错 | **判级 `level.py`（开发B）**按 `grading` 组读参数；决策侧按 `decision` 组读 |
| ② | `demand.json` 的 `od[]` **新增 `exit_node`** | `routes.json` 的 `departure_route` 是**必填**，但"送完人之后怎么走"此前**无处安放**；引擎里不许写死任何节点 id，只能从站点包读 | **`demand.json` 的脚本归开发A** —— T3/T4 转换脚本（#IKLLX3）产出 `od[]` 时要带上 `exit_node` |

### 兼容性

两处都是**加字段 / 定留白，不是改名** —— 兼容纪律（能加字段就不要改字段名）**未破**。`routes.json` 与 `segments.json` 的**字段形状与必填清单一字未动**；TC / M1 / M2 编号与数值一字未动。

### 附：本件还顺带改了什么

- `docs/填表报告.md` 台账里 PR #82 那行的 `结果`：**`已核对` → `占位`**（九件是 W0 结构骨架、不是表格转出来的，"对着表格复核"没发生）。台账**只追加**：以后真表到位、脚本重跑出第一版，**另加一行 `已转`**，这行 `占位` 留着当历史。
- `work/engine/run.py` 的 `--sample` 输出口径三处修正（落客点写点位 id、`driver_type` 按终点推、离站路线给诊断）。详见 PR #8。

> **裁定**：Issue #IKLLXT 的 assignee 即本件作者、原文写明「**你是契约唯一裁定人**」，故裁定权在作者；本评论 + 版本号升级即为第九节要求的"当天在 Issue 里说清 + 升版本号"两步。

---

## Issue IKLLXQ · [接口与双端] 鸿蒙 App 拆分 B：接驳后端与 Web 端（同一套 mock）+ 双端同源举证（L2）

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | L2 / 接口与双端 |
| 创建 | 2026-10-14T11:22:30+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLLXQ |
| 指派 | xixiu-dev2 |

### 正文

> **本单自 GitHub 旧 Issue #89 重建**（2026-10-14 迁到 Gitee 后恢复）：标题、正文与当时的评论原文见仓库 [`docs/历史台账/`](https://gitee.com/ozxowx/hubflow/tree/main/docs/历史台账)，**原文照录、未改口径**。文档里所有 `Issue #89` 引用指的就是本单的前身。

---

| 项 | 值 |
|---|---|
| 难度标签 | **L2** |
| 系列标签 | —（区域开发执行；**不进任务池认领、不占 WIP 配额**） |
| 区域 | 接口与双端 |
| 发布者 | 接口与双端 owner（本单由 `@ouu2006` 代该区域发布） |
| 认领 | 本区域开发执行 |
| 关联 | **父单 #80**（本单是它的**数据接驳拆分**）· **兄弟单 #88**（工程骨架 + 四页 UI）· 手册 **§11.4**（两端同源举证）· 附录 B.3 **C-3** · 分工表 §8 **W5 / TC-02** · **M1-5** · **TC-12** · 数据契约 §七（端点表）/ §二（`routes`）/ §四（`vehicles`）· `work/frontend/README.md` 第三节 |

## 背景：为什么把 #80 拆成两条

#80 原本一单到底。拆开的原因：「**四页长什么样、跑不跑得起来**」（兄弟单 **#88**）与「**数据从哪来、能不能证明两端同源**」（本单）是可分别交付、分别验收的两件事，而且第二件卡在工程之外（局域网可达性、演示车由谁给）。

| 单 | 只做什么 | 数据 |
|---|---|---|
| **#88（A · 前端 UI）** | 工程骨架 + 四页 + 全部非功能口径 | 工程内 fixture，**不写网络代码** |
| **本单（B · 数据接驳）** | 把 #88 那批页面接到 `/api/traffic/*`，出同源举证 | **直连同一套 mock**（vite 中间件） |

**依赖方向是单向的**：本单**依赖 #88 先落地**（页面结构定了才谈换数据源）；#88 **不依赖本单**，可先合。

> 一期 App 的定位：**「第一版 3 层 Web + App 一层」串通整个流程**里的那一层——司机端把**同一个快照里的同一辆车、同一条推荐**显示出来，用来证明**双端同源**。**不是**接入真实定位（那是二期，`POST /api/traffic/locate` 本期**只留接口位，不实现**）。

## 要产出什么

### 1. 把 #88 的 fixture 换成真实响应（**页面结构不动**）

| 用到的端点 | 方法 | mock 现状 |
|---|---|---|
| `/api/traffic/vehicles` | GET | **已实现**（`work/frontend/ui-vue/src/mock/traffic.ts:1152`），字段逐字对照契约 v2.0 §四 |
| `/api/traffic/route/recommend` | POST | **已实现**（同文件 `:1157`），返回 `arrival_route` / **`departure_route`** / **2 条备选（各带 `reason`）** / `reservation` / `why` |

- 做法**倾向但不锁死**：App **直连同一套 mock**（局域网可达地址 + `ohos.permission.INTERNET`）——这样"**同一份接口响应 JSON**"的同源举证天然成立；
- 导出的离线快照**只能当不可达时的兜底**，**不能代替 TC-02 的同源举证**；
- `work/assembly/traffic.py` **尚未实现**，但接口形状不会变——App 侧换 base 即可（**不要**为 mock 写 mock 专用分支）。

### 2. 两个必须先解决的卡点（**本单最容易被这两条挡住**）

**卡点一：mock 端口默认只有回环可达，App 够不着。**

`work/frontend/ui-vue/vite.config.ts` 的 `server` **没有 `host` 键**（实测），vite 默认只绑 `localhost`。模拟器 / 真机上的 App 发到 `127.0.0.1:5173` 是**它自己**的回环，必然连不上。可选路径（择一，在 PR 里申报做法）：

- **首选**：跑 mock 时开 `--host`（局域网可达），App 用**主机局域网 IP + 端口**；这是 `ui-vue` 的**一行级改动**，按开发规范文首总原则申报「方式 + 为什么 + 契约与判定不变」；
- 或：导出一份 mock 响应快照，用**工程外的静态托管**（如 `python -m http.server --bind 0.0.0.0`）顶——但**只做直连失败的兜底**；
- 或：等 `work/assembly/traffic.py` 落地后直连真后端（**本单不等它**）。

**卡点二：桥接在跑时，`is_demo_bound` 全 `false`——App 找不到演示车。**

实测链路（三处读源码）：

1. `mock/traffic.ts:382`：`buildVehiclesSnapshotWithTwin()` **优先信孪生桥接**（`work/frontend/tools/twin_preview/server.py:8102` 的 `/api/twin/vehicles`），**只要可达就用它**；
2. 该桥接的车辆元素里 **`is_demo_bound` 硬编码 `False`**（`server.py:163`，唯一一处赋值）；
3. 于是**桥接一开，`GET /api/traffic/vehicles` 里就一辆 `is_demo_bound: true` 都没有**——而**只有**桥接不可达回落合成车时，站点包 A 的 `twin-0001`（`station-packs/stationA.ts:293`，`is_demo_bound: true`）才会出现。

**M1-5 要的正是那一条 `is_demo_bound: true` 的记录。** 本单必须至少其一：① 让桥接侧把某一辆标成演示车（`server.py` 一处改动）；② 或在 App/前端侧定义"演示车"的**同一份判定口径**并说明它从哪来；③ 或**演示时不开桥接**并把这条限制**写进举证材料**。**不许**让 App 自己挑一辆车当演示车（那就断了 `vehicle_id` 一致性）。

> 顺带（**不在本单范围**，发现即记）：mock 的跨站写门（`mock/util.ts:crossSiteWriteBlocked`）只对非 GET/HEAD 生效，而 `route/recommend` 是 **POST**——若 HarmonyOS 的 HTTP 客户端**带上了 ≠ host 的 `Origin`**，会吃 403 `CROSS_SITE_BLOCKED`；**缺 `Origin` 的请求放行**。本单只需实测一次并写进 README（**不要**为它改门禁口径）。

### 3. 双端同源举证材料（**本单的核心交付**）

- **TC-02**：同一时刻截图**管理端**与 **App**，**同一路段的指标与等级一致**，且都能追溯到 `is_simulated`；
- **M1-5**：App 绑定的演示车位置能追溯到 `vehicles` 快照里 **`vehicle_id` 一致的、同一条记录**，**且带 `is_simulated: true`**（信封层那一个）；
- **TC-12（数据侧）**：真实响应里 `departure_route` **必现**，离站页读的就是它；
- 举证材料（截图 / 录屏）**必带角标**「**演示数据（模拟）· 双数据源（视频链路 + 孪生链路）**」（M1-7，抽查 100% 命中）。

### 4. 口径红线（**违反即不通过**）

- 一期 App **不得声称"已接入真实定位"**；页面**不出现「实测 / 实时 / 现场」**；
- 全部数值来自站点包 + mock 快照（**虚拟数据**），**`is_simulated` 恒为 `true`**，**两端不允许各算一遍**（App 只显示、不算业务）；
- **不碰契约**：字段名与取值集合逐字对照契约 v2.0；**不改契约、不加字段**，需要新字段先在 Issue 里说；
- **不改站点包数值**、**不改 mock 的业务口径**（本单只做接驳）。

### 5. 文档

- `work/frontend/README.md` 同一节续写：**怎么把 mock 暴露给 App**（含 `--host` 的做法与"一行级改动"申报）、**演示车从哪来**（含上面卡点二的结论）、**离线兜底的边界**、同源举证的复现步骤、跨站写门的实测结论。
- `work/assembly/技术栈.md` 第 2 节「服务宿主 / 管理端 / 司机端」行若 #88 未填完，**本单补完**（含接口层宿主现状：`traffic.py` **未实现**这一事实要如实写）。

## 三 prerequisite

| | 内容 |
|---|---|
| **输入样例** | `GET /api/traffic/vehicles` 与 `POST /api/traffic/route/recommend` 的 mock 响应（站点包 A，`npm run dev` 起 `:5173`）；桥接版对照（`work/frontend/tools/twin_preview/server.py` 起 `:8102`） |
| **输出样例** | App 在**不联网兜底**的情况下从 mock 取到数据：车辆页显示 `twin-0001`（或桥接里被标为演示车的那辆）在孪生路网中的位置与推荐 + 2 条备选 + 离站路线；**同一时刻**管理端与 App 并排截图 + 同一份响应 JSON 归档 |
| **自检脚本** | `python scripts/doc_gate.py` 全绿（仓库根）；人工核：管理端与 App **同路段等级一致**、`is_simulated` 可追溯、`departure_route` 必现、演示车 `vehicle_id` 与响应 JSON 逐字相同 |

## 完成判定（**照抄手册 / 分工表，不新造**）

1. **W5 / TC-02**：同一时刻截图管理端与 App，**同一路段的指标与等级一致**，且都能追溯到 `is_simulated`；**可由同一接口响应 JSON 举证**。
2. **M1-5**：演示车位置能追溯到 `vehicles` 快照里 **`vehicle_id` 一致的同一条记录**且带 **`is_simulated: true`**。
3. **TC-12**：`departure_route` **必现**（离站路线页）。
4. **C-3**：绑定一辆演示车（`is_demo_bound` **同一时刻最多一辆**）。
5. **口径红线**：不出现「实测 / 实时 / 现场」；不声称已接入真实定位；`is_simulated` 恒为 `true`。
6. **M1-7**：举证材料角标必现，抽查 100% 命中。

## 依赖谁的什么

- **依赖兄弟单 #88**（工程骨架 + 四页）先落地——本单不改页面结构，只换数据来源。
- 依赖 `work/frontend/ui-vue/src/mock/traffic.ts`（两个端点已实现，**只读**）、`src/station-packs/` 的演示车与推荐骨架（**只读**）、契约 v2.0 字段定义（**只读，不改**）。
- **不依赖 `work/assembly/traffic.py`**（尚未实现；它落地后形状不变，换 base 即可）。

## 卡在哪里

- **两个卡点见上文第 2 节**——卡点一（mock 只有回环可达）是环境问题，**当场就能绕**（`--host` 或静态托管）；卡点二（桥接把 `is_demo_bound` 写死 `False`）**需要在本单里定口径**，不然 M1-5 无从举证。
- 工具链（DevEco / `hdc`）若在 #88 已装好，本单只需能跑模拟器 / 真机发请求；**当前环境未见安装痕迹**是 #88 的第一步。

### 评论（0 条）

（无评论）

---

## Issue IKLLXL · [接口与双端] 鸿蒙 App 拆分 A：工程骨架 + P0 四页 UI（数据用工程内 fixture，不联网）（L2）

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | L2 / 接口与双端 |
| 创建 | 2026-10-14T11:22:28+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLLXL |
| 指派 | xixiu-dev2 |

### 正文

> **本单自 GitHub 旧 Issue #88 重建**（2026-10-14 迁到 Gitee 后恢复）：标题、正文与当时的评论原文见仓库 [`docs/历史台账/`](https://gitee.com/ozxowx/hubflow/tree/main/docs/历史台账)，**原文照录、未改口径**。文档里所有 `Issue #88` 引用指的就是本单的前身。

---

| 项 | 值 |
|---|---|
| 难度标签 | **L2** |
| 系列标签 | —（区域开发执行；**不进任务池认领、不占 WIP 配额**） |
| 区域 | 接口与双端 |
| 发布者 | 接口与双端 owner（本单由 `@ouu2006` 代该区域发布） |
| 认领 | 本区域开发执行 |
| 关联 | **父单 #80**（本单是它的**前端 UI 拆分**）· **兄弟单 #93**（数据接驳）· 手册 §11.1 / §11.3 · 附录 B.3 **C-3** · 分工表 §8 **W4 / W5** · **TC-05 / TC-11** · 数据契约 §二（`routes`）/ §四（`vehicles`）· `work/frontend/README.md` 第三节 |

## 背景：为什么把 #80 拆成两条

#80 原本是一单到底（工程骨架 + 四页 + 接数据 + 双端同源举证）。实际做下来会撞两堵墙：**「页面能不能在 DevEco 里跑起来」**与**「数据从哪来、能不能证明两端同源」**是两件可以**分别交付、分别验收**的事，而且第二件卡在工程外（局域网可达性、`is_demo_bound` 由谁给）。合成一单的后果是：工具链没装好时连"页面长什么样"都交不出来。

所以拆成两条：

| 单 | 只做什么 | 数据 |
|---|---|---|
| **本单（A · 前端 UI）** | 工程骨架 + 四页 + 全部非功能口径 | **工程内的固定样例**（契约 v2.0 的示例 JSON 抄成 fixture），**不写一行网络代码** |
| **#93（B · 数据接驳）** | 把同一批页面接到 `/api/traffic/*` + 双端同源举证 | 直连同一套 mock（vite 中间件） |

**拆分的边界**：本单**不引入任何 HTTP 客户端 / 权限声明 / base 地址配置**——那些全归 B。本单交付后，把 fixture 换成真实响应**不改页面结构**（B 的验收前提）。

> 一期 App 的定位仍是 #80 那句：**「第一版 3 层 Web + App 一层」串通整个流程**里的那一层。**不是**接入真实定位（那是二期）。

## 要产出什么

### 1. 工程骨架（新增）

- `work/frontend/harmony/`（**新增**）：鸿蒙工程（**ArkTS / DevEco Studio**，按官方工程结构提交源码）。
- **不提交**构建产物、SDK、签名文件、`node_modules`、`.hvigor/`、`build/`、`oh_modules/`（门禁禁入名单 + 体积上限）。
- 工程内**自带的样例数据**（fixture）：契约 v2.0 §二（`routes` 示例）+ §四（`vehicles` 示例），落到 `entry/src/main/resources/rawfile/` 或 ets 常量——**四页只读它**，字段名与契约逐字一致。

### 2. 四页（附录 C-3）

| 页面 | 内容 | 本单的数据来源 |
|---|---|---|
| 当前建议 | 推荐路线 + **至少两条备选** + 预计耗时 + 差异原因（`why`）+ **前后车协同说明**（"不会让已在你前面的车变慢"）+ 数据来源标记 | fixture 的 `arrival_route` / `alternatives` / `why` |
| 落客 / 候客指引 | 停靠点类型、位置、预计等待（或步行接驳时长） | fixture 的 `arrival_route.dropoff_point` / `walk_min` |
| **离站路线** | 送完人之后怎么走（读 `departure_route`，**本项目独有**） | fixture 的 `departure_route` |
| 我的行程 | 本次会话的历史行程，**如实标注「未采纳推荐」** | 工程内本地会话记录（一期可简，页要有） |

### 3. 非功能口径（**本单就做完，不等数据**）

这几条与"数据从哪来"无关，**页面画出来就得对**：

| 项 | 要求 | 出处 |
|---|---|---|
| 三重编码 | **颜色 + 图标 + 文字同时出现**，关掉颜色也能区分四级 | 手册 §11.3 |
| 数据不可用 | **灰色「数据不可用」**，**绝不显示成蓝色** | TC-11 |
| 应急状态 | **停止路线引导**，替换为「**请服从现场指挥**」（优先级高于一切推荐） | 手册 §11.1(3) |
| 告知文案 | 「**该建议基于当前路况，可能随流量变化**」**必现**；**不强制、不反复弹窗** | 手册 §11.1(3) |
| 拒绝授权降级 | 降级为「手动选所在道路 / 只看路况」，**流程不中断** | TC-05 的 App 侧 |
| 数据来源角标 | **必现**「**演示数据（模拟）· 双数据源（视频链路 + 孪生链路）**」 | M1-7 |
| 备选条数 | **≥2 条**（+ 推荐 1 条 = 合计 ≥3 条方案）；唯一候选时按 `no_alternative: true` **如实说明原因** | 契约 §二 · 手册 §11.1(3) |

### 4. 口径红线（**违反即不通过**）

- 一期 App **不得声称"已接入真实定位"**；页面**不出现「实测 / 实时 / 现场」**；
- 全部数值来自 fixture（**虚拟数据**），**`is_simulated` 恒为 `true`**；
- **不碰契约**：`vehicles` / `route/recommend` 字段名与取值集合**逐字对照契约 v2.0**（`driver_type` D1/D2/D3、`state` 封闭集、`alternatives` 必带 `reason`、`is_simulated` 在信封层）；**不改契约、不加字段**。需要新字段先在 Issue 里说。

### 5. 文档

- `work/frontend/README.md` 新增一节：App 工程落位、**怎么在 DevEco 里跑起来**、**本单数据来源 = 工程内 fixture（不是接口）**、口径红线、已知限制。
- `work/assembly/技术栈.md` 第 2 节「服务宿主 / 管理端 / 司机端」行现为「**待补**」——**本单填鸿蒙 / ArkTS 的版本与出处**（实测版本，不写"应该"）。

## 三 prerequisite

| | 内容 |
|---|---|
| **输入样例** | 契约 v2.0 §二（`routes` 示例 JSON）/ §四（`vehicles` 示例 JSON）；站点包 A 的 `recommend` 骨架（`arrival_route` / **`departure_route`** / **2 条备选**各带 `reason` / `why`，见 `work/frontend/ui-vue/src/station-packs/stationA.ts`）——**抄成 fixture，不联网** |
| **输出样例** | DevEco 里可运行的 App：四页可切换、每页有数据、角标与三重编码在位；**四页截图 / 录屏 + 角标** |
| **自检脚本** | `python scripts/doc_gate.py` 全绿（仓库根）；人工核：四页都能进、`departure_route` 页有内容、灰档与应急态各触发一次、关掉颜色仍能区分四级 |

## 完成判定（**照抄手册 / 分工表，不新造**）

1. **W4**：**鸿蒙页能在 DevEco 里跑起来并显示一条推荐路线——不是界面原型**（运行目标：DevEco 预览器或模拟器即可，真机可选；举证 = 截图 / 录屏 + 角标）。
2. **C-3**：P0 四页可用（当前建议 / 落客候客指引 / **离站路线** / 我的行程）。
3. **TC-11**：数据不可用显示**灰色**，不是蓝色。
4. **手册 §11.3**：三重编码齐全，关掉颜色也能区分四级。
5. **手册 §11.1(3)**：应急态停下引导换「请服从现场指挥」；告知文案必现且不反复弹窗。
6. **TC-05（App 侧）**：拒绝授权后降级为「手动选所在道路 / 只看路况」，**流程不中断**。
7. **M1-7**：数据来源角标必现「演示数据（模拟）· 双数据源（视频链路 + 孪生链路）」。
8. **口径红线**：不出现「实测 / 实时 / 现场」；不声称已接入真实定位。

## 依赖谁的什么

- **不依赖后端、不依赖兄弟单 #93**：数据用工程内 fixture，四页可独立交付。
- 依赖 `work/frontend/ui-vue/src/station-packs/`（演示车与推荐骨架，**只读**）与契约 v2.0 字段定义（**只读，不改**）。
- **兄弟单 #93 反过来依赖本单**的工程骨架与四页（它只做"把 fixture 换成真实响应"）。

## 卡在哪里

- **当前开发环境未见 DevEco Studio / HarmonyOS SDK 安装痕迹**（`hvigor` / `ohpm` / `hdc` 均不在 PATH）——这是执行者第一步：装工具链（手册风险表第 12 条：鸿蒙 ArkTS 是全新栈，**全程由 AI 辅助开发**，不做花哨动效）。
- 若工具链一时装不上：**先交"能在 DevEco 里跑起来的最小页 + 举证"**（W4 的门槛就是"跑起来"）；**不得在没有真跑起来的情况下声称 W4 判定通过**。

### 评论（0 条）

（无评论）

---

## Issue IKLLXG · [接口与双端] 大屏右栏「关联告警」判级回归——#77 迁移时丢了 #75 第④条的等级重映射（L1）

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | L1 / 接口与双端 |
| 创建 | 2026-10-14T11:22:26+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLLXG |
| 指派 | （无） |

### 正文

> **本单自 GitHub 旧 Issue #85 重建**（2026-10-14 迁到 Gitee 后恢复）：标题、正文与当时的评论原文见仓库 [`docs/历史台账/`](https://gitee.com/ozxowx/hubflow/tree/main/docs/历史台账)，**原文照录、未改口径**。文档里所有 `Issue #85` 引用指的就是本单的前身。

---

| 项 | 值 |
|---|---|
| 难度标签 | **L1** |
| 系列标签 | —（区域开发执行；不进任务池认领、不占 WIP 配额） |
| 区域 | 接口与双端 |
| 发布者 | 接口与双端 owner（本单由 `@ouu2006` 代该区域发布） |
| 认领 | 开发C 执行 |
| 关联 | #75 第 ④ 条（四处判级取当前路段快照）· PR #76（原修法）· #77 / PR #78（删 `/heat`、widget 迁入大屏，提交 `3b23df4`）· 手册 §11.2 |

## 背景：一条已验证的修复，在页面迁移时被丢下

#75 第 ④ 条要求「**四处**告警判级一律取**当前路段快照**」。PR #76 当时把第四处做在 `views/heat/HeatView.vue`：

```ts
// PR #76（HeatView.vue，该文件已随 #77 删除）
const selectedAlerts = computed(() =>
  alerts.value
    .filter((a) => a.segment_id === selectedId.value && a.status !== '已闭环' && a.status !== '误报')
    .map((a) => ({ ...a, level: selected.value?.level ?? a.level })),
)
```

#77（PR #78，提交 `3b23df4`）删除 `/heat` 独立页、把 widget 迁入监控大屏时，**这句 `.map(...)` 没跟着搬**。同一次迁移里决策队列、决策工作台、大屏底部告警条三处都还在，只有这一处丢了。

## 现状（对 `origin/main`（`02b4b54`）逐文件读取）

- `views/dashboard/DashboardView.vue:458` 的 `selectedAlerts` 是**裸 filter**，不做等级重映射；
- `views/dashboard/components/AlertList.vue:22` 直接渲染 `:level="a.level"`——**站点包预置剧本值**；
- 同文件 `segLevelOf()`（`:497`，注释明写「告警等级取**当前路段快照**……直接用会与同一页的路段列表自相矛盾」）只被底部告警条（`:841`）用到。

**复现（打开 `/dashboard` 默认态即可见）**：

| 位置 | 显示 | 取值来源 |
|---|---|---|
| 左栏路段列表 SEG-003 | 严重拥堵（4 级） | 路段快照（`segRows` → `s.level`） |
| **右栏「关联告警」A-2412-015** | **拥堵（3 级）** | **告警记录值（包里 `level: 3`）** |
| 底部告警条（同一条 A-2412-015） | 严重拥堵（4 级） | `segLevelOf()` → 路段快照 |

**同一页、同一条告警、两个等级**——正是 #75 第 ④ 条要消掉的「同页自相矛盾」。包 A 里同类不同步还有一对：A-2412-021（SEG-007，包里 `level: 2`）vs SEG-007 快照 3。

## 要产出什么

1. `DashboardView.vue` 的 `selectedAlerts` 补一次等级重映射（`.map((a) => ({ ...a, level: segLevelOf(a) }))`），或改由 `AlertList.vue` 接一个 `levelOf` 回调——**两处只留一份口径**，避免下次迁移再丢；
2. **顺带清理（同一次迁移的遗留）**：`components/SegmentIndexPanel.vue` 自 #77 迁入后**全仓无引用**（死代码），但 `work/frontend/README.md` §13.1 仍写它「进右栏」——接上或删除，二选一。

## 三 prerequisite

| | 内容 |
|---|---|
| 输入样例 | 站点包 A 的 `alerts` 与 `segmentBases`（SEG-003 / SEG-007 两对即可复现）；`GET /api/traffic/alerts` + `GET /api/traffic/segments` |
| 输出样例 | `/dashboard` 右栏关联告警徽章与左栏路段列表、底部告警条**三处同值**；`npm run build` 绿 |
| 自检脚本 | `npm run build`（含 `vue-tsc`）+ `python scripts/doc_gate.py`；人工核：选任一带未闭环告警的路段，三处等级文字一致 |

## 完成判定（照抄 #75 第 ④ 条与手册，不新造）

- **#75 第 ④ 条**：四处（决策队列、决策工作台、大屏底部告警条、**大屏右栏关联告警**）判级一律取**当前路段快照**；快照缺该路段时退回告警记录值，不编造；
- **手册 §11.2**：同一页面不得出现同路段两个等级。

## 依赖谁的什么

- 站点包数值**一字不改**（本单只改「怎么显示」）；
- 不依赖 `#75`——`#75` 已按「六条交付完成」关闭，本单是其后一次重构引入的回归，独立跟踪。

## 卡在哪里

无。

### 评论（1 条）

**1 · @ozxowx · 2026-10-15T19:29:21+08:00**

## 本单完成（2026-10-15）

**PR #16 已合入 main**（合并提交 `09be4ee`）。回归已修、口径已收口、死代码已清。

### 1. 判级回归（本单主体）

`#75` 第④条要求「四处告警判级一律取**当前路段快照**」，第四处（大屏右栏关联告警）在 `#77` 页面迁移时被漏搬。**已修**，并且**不是只补一句 `.map()`**——那样"下次迁移再漏搬一次"的风险原样保留（本次就是这么发生的）：

| 项 | 落点 |
|---|---|
| **唯一实现** | `src/shared/traffic.ts` 的 `alertLevelOf(a, findSegment)`（快照缺该路段**退回告警记录值**，不编造） |
| 大屏右栏关联告警 | `AlertList.vue` 的 `levelOf` 做成**必需 prop**（`DashboardView.vue` 传 `segLevelOf`） |
| 大屏底部告警条 | 同页 `segLevelOf()`（同一函数） |
| 决策队列 / 决策工作台 | `DecisionView.vue` 的 `segLevel()`（同一函数，查 `segMap`） |

**四处只留一份口径**；漏传 `levelOf` 会在 `vue-tsc` 阶段失败（负向验证：去掉 `:level-of` 后报 `TS2345 Property 'levelOf' is missing ... but required`）。

**实测（包 A 默认态，挑一条"记录值与快照值确实不同"的告警 `A-2412-018`：记录 3 级 / SEG-004 快照 2 级）**：

| | 值 |
|---|---|
| 告警记录值 | **3**（拥堵） |
| 路段快照值（SEG-004） | **2**（缓行） |
| 大屏左栏 | x 0.41 · **缓行** |
| 大屏右栏「关联告警」 | **缓行** · 待认领 |
| 大屏底部告警条 | 待认领告警 · **缓行（二级）** |
| 决策层「处置队列」 | **缓行** |

四处全部落在**快照值 2**。**修复前对照**（同一条告警、同一次点击，`git stash` 掉改动后重测）：右栏显示 **拥堵**（记录值 3），其余三处显示 **缓行**——本单描述的自相矛盾**可稳定复现**，修复后消失。

### 2. 顺带清理（同一次迁移的遗留）

`components/SegmentIndexPanel.vue`（234 行）自 `#77` 起**全仓无引用**——**已删除**（`git grep SegmentIndexPanel` 现仅命中 `docs/历史台账/`，历史留痕不动）。同时改掉 `work/frontend/README.md` §13.1 里"`SegmentIndexPanel` 的 CI 段进右栏"的过时说法——**右栏内容按大屏版式在 `DashboardView.vue` 里内联**，不另立卡片组件。

> ⚠️ **一处如实说明**：该组件里有一块「数据不可用路段」明细清单（段号 / 名称 / 陈旧原因 / 年龄 / 置信度），`#77` 迁移时**没有接到大屏任何位置**。本单按"接上或删除二选一"的裁定选了**删除**。大屏现有的不可用呈现是：左栏「路段监测」里灰行写「数据不可用 · 陈旧 Ns」（按等级排序或 CI 降序都排最后）+ 底部「档位分布」的灰档计数 + 地图灰线 + `SegmentRankTable` 指数视图下的「不可用」。**判定项（TC-11 / C-2 / 手册 §11.2）都不要求那张明细清单**，故不构成判定缺口；若将来要明细，另开单加在右栏。

### 3. 自检

- `vue-tsc --noEmit -p tsconfig.app.json` exit 0；`vite build` exit 0；`python scripts/doc_gate.py` **七组全过**（在合并后的 `09be4ee` 上复跑过）
- **审查记录**：快速独立审查（全新上下文，只给改动范围 + 4 个问题）——4 问全过：范围无夹带、未碰契约 / 他人目录 / 公共文件、无密钥与大文件、**四处调用点均传对且全仓无残留直接渲染告警自带 `level` 的写法**（唯一保留的是 `shared/traffic.ts` 里预期的 `?? a.level` 回退）。完整结论见 PR #16 描述。
- 改动范围：`work/frontend/` 内 **6 个文件**（1 删除 + 5 修改）；**站点包数值一字未改**（本单只改"怎么显示"）；契约字段、TC / M1 / M2 编号未动。

关闭本单。

---

## Issue IKLLXD · [接口与双端] 监控大屏窗口可拖拽调宽——主体三栏 + 底部热力带（L1）

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | L1 / 接口与双端 |
| 创建 | 2026-10-14T11:22:24+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLLXD |
| 指派 | （无） |

### 正文

> **本单自 GitHub 旧 Issue #81 重建**（2026-10-14 迁到 Gitee 后恢复）：标题、正文与当时的评论原文见仓库 [`docs/历史台账/`](https://gitee.com/ozxowx/hubflow/tree/main/docs/历史台账)，**原文照录、未改口径**。文档里所有 `Issue #81` 引用指的就是本单的前身。

---

| 项 | 值 |
|---|---|
| 难度标签 | **L1**（单页改造 + 一个现成组件接线；半天量级） |
| 系列标签 | —（区域前端任务；**池子认领**，不属 V / S / P / Q 四系列） |
| 区域 | 接口与双端 |
| 发布者 | 接口与双端 owner（本单由 `@ouu2006` 代该区域发布） |
| 认领 | **池子认领**（谁认领谁干，可单人可多人；不点名、不指派） |
| 关联 | 手册 **§11.2**（三层 3 页结构：监控大屏 = 选择监控 / 全路段状态 / 路段信息 + 底部热力带）、**§6.2**（配色语义分工）、判定 **C-2**（数据不可用恒灰）；`work/frontend/README.md` **第十三节**（三层收敛）与 **§10.4 第 8 条**（一屏密度与三栏独立滚动） |

## 背景：监控大屏的三栏是写死的宽度

业主 2026-10-13 口径：**监控大屏（`/dashboard`）里的窗口要能拖拽调整大小**——现在列宽是 CSS 写死的，看不同数据时不能自己分配屏幕。

现状（`work/frontend/ui-vue/src/views/dashboard/DashboardView.vue`）：

| 区块 | 现在 | 位置 |
|---|---|---|
| 主体三栏 | 左 `flex: 0 0 296px` / 中 `flex: 1 1 auto` / 右 `flex: 0 0 396px` | 模板 565~798 行；CSS **929~940 行** |
| 底部热力带三卡 | 左 `flex: 0 0 240px` / 中 `flex: 1 1 auto` / 右 `flex: 0 0 240px` | 模板 800~834 行；CSS **1176~1193 行** |

**只有拖拽、不加功能**：本单不改任何数据、口径、判定与配色，只把「宽度谁定」从 CSS 交给用户。

## 要产出什么（都在 `work/frontend/ui-vue/` 内）

### 必做（L1 核心，这三条就是判定）

1. **主体三栏横向可拖**：左 / 中 / 右三栏之间各有一条可拖拽分隔条，拖动时相邻两栏宽度实时变化、第三栏自动伸缩（中栏默认仍是弹性栏）。
2. **拖不坏**：给每栏一个**最小宽度**（建议左 220 / 中 320 / 右 280，**数值写进代码注释**，可自定），拖到最小宽度时内容**不叠压、不溢出、按钮仍点得到**；三栏**仍各自独立滚动**（`.td-scroll` 的职责不许被顶掉）。
3. **默认态不变**：首次进入 / 刷新页面 / 切到别的页再回来，宽度回到设计稿口径（296 / 弹性 / 396）——即**不记忆**也是合格的默认行为。

### 可选（加分项；做不完**另开一单**，不算本单没做完）

4. 底部热力带三卡同样可拖（纵向高度可拖亦可）。
5. 用 `localStorage` 记住用户拖过的宽度。
6. 双击分隔条复位到默认宽度。

### 实现方向（**倾向，不锁死**）

**优先用 Element Plus 自带的 `ElSplitter` / `ElSplitterPanel`**——**不需要加任何新依赖**：

- `element-plus@2.14.5` **已装**（`package.json`），`src/main.ts` 已 `app.use(ElementPlus)` **全局注册**，`node_modules/element-plus/es/components/splitter/` 里 `ElSplitter` / `ElSplitterPanel` 都在，`element-plus/global.d.ts` 113~114 行也有全局组件类型声明（`vue-tsc` 认）。
- 用法：`<el-splitter>` 包三个 `<el-splitter-panel>`，用 `size` / `min` / `max` 给初值与边界，`@resize-end` 拿拖后尺寸。

**若你认为该用别的做法**（自己写拖拽、换别的组件库），按 [`docs/开发规范.md`](https://github.com/ouu2006/hubflow/blob/main/docs/%E5%BC%80%E5%8F%91%E8%A7%84%E8%8C%83.md) 文首总原则，在 PR 的「实现方式」栏申报「用了什么方式 + 为什么 + 契约与判定不变」。**换组件库属于加依赖，先在本 Issue 里说一句再动**。

## 口径红线（**违反即不通过**）

1. **不引新依赖**。`ElSplitter` 已在现有依赖里；要加别的库先在本 Issue 说。
2. **Element Plus 的默认主题蓝不许渗进壳层**。`ElSplitter` 的拖拽条 hover / active 用的是 `--el-color-primary-light-5` / `-light-3`（`element-plus/dist/index.css`），**本仓库 `src/style.css` 一个 `--el-` 变量都没覆盖过**（实测 0 命中）——直接用会出现一套跟 TDesign 无关的蓝。必须**映射到项目令牌或改成中性灰**，守住手册 §6.2 的两条：**品牌蓝只表示「当前 / 已选 / 可操作」**、**等级色不得出现在壳层**。
3. **默认宽度不许改**（296 / 弹性 / 396）。设计稿按 1440×900 对齐，改默认值等于改了设计稿。
4. **只改 `work/frontend/ui-vue/`**：不动契约（`segments.json` / `routes.json` / `vehicles.json`）、不动 mock 数据、不动站点包（`src/station-packs/`）、不动 `stations/`。
5. **范围只到 `/dashboard`**。感知层 `/perception` 与决策层 `/decision` 也是三栏，但**本单不动**——一次 PR 只做一件事，那两页要跟就另开单。
6. **已知限制如实写**：`ElSplitter` **只有鼠标 / 触摸拖拽，没有键盘操作**（实测 `split-bar` 里只有 `mousedown` / `touchstart`，无 `tabindex` / `keydown` / `role`）。本单**不强制**补键盘可达，但**必须在 `work/frontend/README.md` 里如实记一句**，**不得写成「无障碍已达标」**。

## 三 prerequisite

| | 内容 |
|---|---|
| **输入样例** | 现役 `DashboardView.vue` 三栏与底部热力带（模板 565~834 行、CSS 929~940 与 1176~1193 行）；Element Plus `ElSplitter` 的官方用法（`<el-splitter>` + `<el-splitter-panel>`，本机 `node_modules/element-plus/es/components/splitter/` 可直接读源码） |
| **输出样例** | 拖动分隔条 → 相邻两栏宽度实时变化、中栏自动伸缩；`npm run dev` 下 `/dashboard` 在 **1440×900** 无横向溢出、无 console 报错；默认宽度与改前一致 |
| **自检脚本** | `npm run build`（含 `vue-tsc`）+ 仓库根 `python scripts/doc_gate.py`；人工核：拖到最小宽度内容不叠压、切页 / 刷新回默认宽度、三栏仍各自独立滚动 |

## 完成判定（**照抄既有条目，不新造编号**）

> ⚠️ 手册与 README 里**没有**「可拖拽」这一条判定——本单的交互要求来自**业主 2026-10-13 口径**，**不新造 TC / M1 编号**。验收挂到下面这些**既有**条目上：

1. **手册 §11.2 / 判定 C-2**：改动后监控大屏**仍然可用**——左「选择监控」/ 中「全路段状态」/ 右「路段信息」/ 底部「热力带 + 告警条」**一项不少**；**数据不可用仍显示灰色**（TC-11，不许因为改布局把灰档落进通配色）。
2. **手册 §6.2**：三重编码（颜色 + 竖条 + 文字）**不变**；品牌蓝仍只表示「当前 / 已选 / 可操作」；**新增的分隔条不得引入第二套蓝**（见口径红线第 2 条）。
3. **`work/frontend/README.md` §10.4 第 8 条**：**一屏密度**不许被破坏——1440×900 下**无横向溢出**，**三栏都要有栏内 `overflow-y:auto`**（该条记着 PR #70 曾因左栏漏加导致「按钮可见但点不到」，本单最容易被踩回去）。
4. **本单自己的一句话判定**：**拖动分隔条，左右两栏宽度真的变了、中栏跟着伸缩，且拖到最小宽度内容不被压坏**——截图 / 录屏留证。
5. **文档**：`work/frontend/README.md` 第十三节补一小节（拖拽范围、默认宽度、最小宽度、已知限制、怎么复位）。

## 依赖谁的什么

- 依赖 `work/frontend/ui-vue/` 现役三栏结构与 `element-plus@2.14.5`（**都已就位，不等任何人**）。
- **不依赖后端、不依赖 mock 改动**：纯前端布局层。
- 站点包 A / B 两套都要试（`npm run dev` 与 `npm run dev:station2`），确认换站后拖拽照常。

## 卡在哪里

- **难度落在 L1 / L2 边缘**：本单按 **L1** 发布（用现成组件、只改一页），**L2 依规程暂不发布**。执行者若发现实际超出半天量级，**可以自己拆成多条**（见 [`docs/协作规范.md`](https://github.com/ouu2006/hubflow/blob/main/docs/%E5%8D%8F%E4%BD%9C%E8%A7%84%E8%8C%83.md) §5.3 粒度口径），**或在本 Issue 里说一句卡在哪**。
- **最容易做歪的三处**（先看这三条，省得返工）：
  1. `.el-splitter-panel` 自带 `overflow: auto`，而现有 `.td-col` 才是滚动容器（`.td-scroll`）——**先定谁负责滚动**（建议：panel 不滚、内部 `.td-col` 照旧滚），否则会出现**双层滚动条**或「滚不动」。
  2. `.el-splitter-bar` 的**宽度是 0**（只有 16px 宽的 dragger 绝对定位覆盖在边界上），而现有 `.td-body { gap: 10px }` 换成 splitter 后**不再生效**——栏间视觉间距会变，**需要给 bar 一个宽度**。
  3. 中栏 `NetMap` 自己按 `getBoundingClientRect()` 换算拖拽位移（`NetMap.vue:152`），栏宽变化本身不会坏（`viewBox` + `preserveAspectRatio="xMidYMid meet"` 自适应），但**改完要亲手拖一次地图栏确认缩放 / 平移仍准**，别只看静态截图。

### 评论（1 条）

**1 · @ozxowx · 2026-10-15T16:15:16+08:00**

## 关闭依据（2026-10-15 复核）

PR #7 已合入 main（`5cf7a4e`）。三条必做判定逐条对上（`work/frontend/ui-vue/src/views/dashboard/DashboardView.vue`）：

| 判定 | 落实 |
|---|---|
| ① 三栏横向可拖 | `<el-splitter>` + 三个 `<el-splitter-panel>`；左 / 右栏 `v-model:size`，中栏**不给 `size`**，由 ElSplitter 自动瓜分剩余空间 |
| ② 拖不坏 | 最小宽度左 220 / 中 320 / 右 280（`COL_MIN_LEFT/MID/RIGHT` 常量在代码里）；PR 实测两条 bar 各猛拖 900px 后被三道 min 夹住，最小宽下左栏列表项与右栏按钮仍点得到，三栏各自独立滚动 |
| ③ 默认态不变 | 296 / 弹性 / 396（`COL_DEFAULT_*`）一字未改；刷新 / 切页回来仍是设计稿口径 |

加分项：两条已完成（`localStorage` 记忆 + 双击分隔条复位）；可选第 4 条（底部热力带三卡也可拖）——单子原文写明「做不完另开一单，不算本单没做完」，未在本单范围，需要时另开单。

文档与已知限制：`work/frontend/README.md` §13.5 在位，含 3 条如实记录（ElSplitter 只有鼠标 / 触摸拖拽、无键盘操作；双击复位靠 `mousedown` 自计次；记忆宽度不随站点包区分），**未写成「无障碍已达标」**。配色守 §6.2：分隔条默认中性灰、hover / 拖拽中取品牌蓝，未引入第二套蓝。

关闭本单。

---

## Issue IKLLX9 · [接口与双端] 司机端鸿蒙 App：P0 四页 + 绑定一台演示车（数据全用虚拟，双端同源）（L2）

| 项 | 值 |
|---|---|
| 状态 | open |
| 标签 | L2 / 接口与双端 |
| 创建 | 2026-10-14T11:22:22+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLLX9 |
| 指派 | xixiu-dev2 |

### 正文

> **本单自 GitHub 旧 Issue #80 重建**（2026-10-14 迁到 Gitee 后恢复）：标题、正文与当时的评论原文见仓库 [`docs/历史台账/`](https://gitee.com/ozxowx/hubflow/tree/main/docs/历史台账)，**原文照录、未改口径**。文档里所有 `Issue #80` 引用指的就是本单的前身。

---

| 项 | 值 |
|---|---|
| 难度标签 | **L2** |
| 系列标签 | —（区域开发执行；**不进任务池认领、不占 WIP 配额**） |
| 区域 | 接口与双端 |
| 发布者 | 接口与双端 owner（本单由 `@ouu2006` 代该区域发布） |
| 认领 | 本区域开发执行 |
| 关联 | 手册 §11.1 / §11.3 / §11.4 · 附录 B.3 **C-3** · 分工表 §8 **W4 / W5** · **TC-02 / TC-05 / TC-11 / TC-12 / M1-5 / M1-7** · 数据契约 §二（`routes`）/ §四（`vehicles`）/ §七（端点表）· `work/frontend/README.md` 第三节 |

## 背景：数据只用虚拟的第一版

业主口径（2026-10-13）：演示**只用第一版数据**（站点包 A 肇庆东示例路网 + 三层 mock），因为拿不到真实数据。**本单的 App 同样只用虚拟数据**——不接真实定位、不接现场摄像头、**也不等后端接口层**（`work/assembly/traffic.py` 尚未实现）。

数据其实**已经现成**，App 侧不需要等任何东西：

| 现成的东西 | 在哪 |
|---|---|
| `GET /api/traffic/vehicles`（孪生车辆位置，含 `is_demo_bound`）与 `POST /api/traffic/route/recommend`（推荐 + 备选 + 离站路线） | `work/frontend/ui-vue/src/mock/traffic.ts`，vite 中间件在 `:5173` 提供，字段逐字对照契约 v2.0 |
| 演示车 | 站点包 A `vehicleBases` 里 `is_demo_bound: true` 的那辆（`twin-0001`） |
| 推荐骨架 | 站点包 A 的 `recommend`：`arrival_route` / **`departure_route`** / **2 条备选**（各带 `reason`）/ `reservation` / `why` 齐全 |

> 一期 App 的定位就是「**第一版 3 层 Web + App 一层**串通整个流程」里的那一层：司机端把同一个快照里的同一辆车、同一条推荐显示出来，用来证明**双端同源**。**不是**接入真实定位（那是二期）。

## 要产出什么

- `work/frontend/harmony/`（**新增**）：鸿蒙工程（**ArkTS / DevEco Studio**，按官方工程结构提交源码）。**不提交**构建产物、SDK、签名文件、`node_modules`（门禁禁入名单）。
- **四页**（附录 C-3）：

  | 页面 | 内容 | 期次 |
  |---|---|---|
  | 当前建议 | 推荐路线 + **至少两条备选** + 预计耗时 + 差异原因（`why`）+ **前后车协同说明**（"不会让已在你前面的车变慢"）+ 数据来源标记 | 一期 |
  | 落客 / 候客指引 | 停靠点类型、位置、预计等待（或步行接驳时长） | 一期 |
  | **离站路线** | 送完人之后怎么走（读 `departure_route`，**本项目独有**） | 一期 |
  | 我的行程 | 本次会话的历史行程，**如实标注「未采纳推荐」**（手册 §11.1(3) 标 P1；C-3 把它列进四页，页要有、内容可简） | 一期 |

- **绑定一台演示车**：从 `GET /api/traffic/vehicles` 取 `is_demo_bound: true` 的那一辆（同一时刻最多一辆），显示它**在孪生路网里的位置**、推荐路线与备选。**App 不做任何定位请求**。
- **字段对齐**：`vehicles` / `route/recommend` 的字段名与取值集合**逐字对照契约 v2.0**（`driver_type` D1/D2/D3、`state` 封闭集、`alternatives` 必带 `reason`、`is_simulated` 在信封层）；**不改契约、不加字段**。需要新字段先在 Issue 里说。
- **数据接入（倾向，不锁死做法）**：**优先让 App 直连同一套 mock**（`/api/traffic/*`，局域网可达地址 + `ohos.permission.INTERNET`）——这样"同一份接口响应 JSON"的同源举证天然成立；导出的离线快照只能当**不可达时的兜底**，**不能代替 TC-02 的同源举证**。
- **文档**：`work/frontend/README.md` 新增一节（App 工程落位、数据来源、口径红线、怎么跑起来）；`work/assembly/技术栈.md` 的「服务宿主 / 管理端 / 司机端」行现为「**待补**」，填鸿蒙 / ArkTS 的版本与出处。

## 三 prerequisite

| | 内容 |
|---|---|
| 输入样例 | 契约 §二 / §四 的示例 JSON；`GET /api/traffic/vehicles` 与 `POST /api/traffic/route/recommend` 的 mock 响应（站点包 A） |
| 输出样例 | DevEco 里可运行的 App：四页 + 绑定 `twin-0001` + 双端同源举证材料（同一时刻的管理端截图 + **同一份响应 JSON**） |
| 自检脚本 | `python scripts/doc_gate.py` 全绿（仓库根）；人工核：管理端与 App 同路段等级一致、`is_simulated` 可追溯、`departure_route` 必现 |

## 完成判定（**照抄手册 / 分工表，不新造**）

1. **C-3**：P0 四页可用；绑定一辆演示车；**双端同源**（TC-02 / M1-5）。
2. **W4**：**鸿蒙页能在 DevEco 里跑起来并显示一条推荐路线——不是界面原型**（运行目标：DevEco 预览器或模拟器即可，真机可选；举证 = 截图 / 录屏 + 角标）。
3. **W5 / TC-02**：同一时刻截图管理端与 App，**同一路段的指标与等级一致**，且都能追溯到 `is_simulated`；**M1-5**：演示车位置能追溯到 `vehicles` 快照里 `vehicle_id` 一致的**同一条记录**且带 `is_simulated: true`。
4. **TC-12**：`departure_route` **必现**（离站路线页）。
5. **硬性要求（两期都适用，缺一不通过）**：
   - 备选 **≥2 条**（+ 推荐 1 条 = 合计 ≥3 条方案）；唯一候选时按 `no_alternative: true` **如实说明原因**，不得为凑数返回等价路径；
   - **三重编码**：颜色 + 图标 + 文字**同时出现**，关掉颜色也能区分四级；
   - **数据不可用显示灰色**，**绝不显示成蓝色**（TC-11——"没数据"不能被读成"很通畅"）；
   - **应急状态停下路线引导**，替换为「**请服从现场指挥**」（优先级高于一切推荐）；
   - 告知文案「**该建议基于当前路况，可能随流量变化**」**必现**；**不强制、不反复弹窗**；拒绝授权时降级为「手动选所在道路 / 只看路况」，**流程不中断**（TC-05 的 App 侧）；
   - **数据来源角标必现**「**演示数据（模拟）· 双数据源（视频链路 + 孪生链路）**」（M1-7，抽查 100% 命中）。
6. **口径红线**：
   - 一期 App **不得声称"已接入真实定位"**——`/api/traffic/vehicles` **二期下线**、`POST /api/traffic/locate` 二期由 App 调用（本期**只留接口位，不实现**）；页面**不出现「实测 / 实时 / 现场」**；
   - 全部数值来自站点包 + mock 快照（**虚拟数据**），**`is_simulated` 恒为 `true`**，两端**不允许各算一遍**。

## 依赖谁的什么

- **不依赖后端**：数据用现有 mock（vite 中间件 `:5173`，站点包 A）；接口层 `work/assembly/traffic.py` 落地后**形状不变**，App 侧换 base 即可。
- 依赖 `work/frontend/ui-vue/src/station-packs/`（演示车与推荐骨架）与契约 v2.0 字段定义（**只读，不改**）。

## 卡在哪里

- **当前开发环境未见 DevEco Studio / HarmonyOS SDK 安装痕迹**（`hvigor` / `ohpm` / `hdc` 均不在 PATH）——这是执行者第一步：装工具链（手册风险表第 12 条：鸿蒙 ArkTS 是全新栈，**全程由 AI 辅助开发**，不做花哨动效）。
- 若工具链一时装不上：**先交"能在 DevEco 里跑起来的最小页 + 举证"**（W4 的门槛就是"跑起来"）；**不得在没有真跑起来的情况下声称 W4 判定通过**。

### 评论（0 条）

（无评论）

---

## Issue IKLLX6 · [接口与双端] 缺陷台账——#66 期间的只读代码盘点发现（契约/确定性/阈值/工程，22 项）

| 项 | 值 |
|---|---|
| 状态 | rejected |
| 标签 | 接口与双端 / bug |
| 创建 | 2026-10-14T11:22:20+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLLX6 |
| 指派 | （无） |

### 正文

> **本单自 GitHub 旧 Issue #68 重建**（2026-10-14 迁到 Gitee 后恢复）：标题、正文与当时的评论原文见仓库 [`docs/历史台账/`](https://gitee.com/ozxowx/hubflow/tree/main/docs/历史台账)，**原文照录、未改口径**。文档里所有 `Issue #68` 引用指的就是本单的前身。

---

> 本单是 **#66 期间两份只读代码盘点**的产物（逐文件读取 + 部分实测），**不是验收结论**。标【已复核】的是在 #66 中亲自核对过的；其余为盘点所得、**未逐条构造反例实验**。逐条给了文件:行号与建议 owner，**请按区域拆领**，不要塞进 #66。

## 一、契约与接口面（建议 owner：开发B 裁定 / 开发C 落地）

| # | 缺陷 | 位置 | 影响 |
|---|---|---|---|
| 1 | **6 个契约端点完全未实现**（既无 api 函数也无 mock）：`/api/traffic/locate`、`/predict`、`/alerts`、`/plan/dispatch`、`/plan/ack`、`/report/compare` | 契约 §七（`docs/数据契约.md:438,442-446`） | 决策层四个面板 100% 前端内存态、刷新即复位（页面已自标"演示态"） |
| 2 | `RecommendResult` **缺 5 个契约字段**：`reroute`、`factors_note`、`quota`、`no_alternative`、`capacity_shortage`；且 `reservation.harm_check` 类型齐备但**全工程从未渲染** | `ui-vue/src/shared/traffic.ts:114-127`；契约 `:186-189,227-243` | 「不会让前车变慢」这条核心主张**在界面上无法举证**（M1-4 / TC-17） |
| 3 | `AssimilationSnapshot` **形状 ≠ 契约 §三**：容器键 `records`↔`edges`、缺 `role`、偏差扁平化、顶层 `gate` 实来自 `scenarios.json` | `ui-vue/src/shared/traffic.ts:184-189`；契约 `:263-286` | 契约 `:286` 硬规则「internal 永远 `assimilating:false`」**在 UI 上无法举证**（映射已在 `work/frontend/README.md:119` 登记为有意为之） |
| 4 | mock 实现了**契约表外的端点** `POST /api/traffic/factors`、`POST /api/traffic/factors/reset` | `ui-vue/src/mock/traffic.ts:639,668`；契约 §七只有 `GET /factors`（`:440`） | 依据是手册 §19 人工置位，但**契约未登记**，只读契约的人会误判接口面 |

## 二、确定性与同源举证（建议 owner：开发C）

| # | 缺陷 | 位置 | 影响 |
|---|---|---|---|
| 5 | **mock 数据不确定**：`jitter()` 随机作用于 `q_vph/v_kmh/k_vpk/L_q_m/ci`，每次 GET 数值都变；无随机种子开关 | `ui-vue/src/mock/traffic.ts:407-441` | 三个页面各自独立拉取 ⇒ **同一时刻三页对同一路段显示不同值**，违反契约 §五（`:350`）"同一数值必须能指回同一快照、同一 ts"与 TC-19 确定性 |
| 6 | **只读 GET 有副作用**：模块级 `tick` 在 `buildSegmentsSnapshot` 自增 ⇒ `data_age_s` 随**请求次数**增长、车辆位置 = `offset_m + speed*2*tick` 取决于"被请求过几次"而非流逝时间；刷新页面不重置 | `ui-vue/src/mock/traffic.ts:405,427,442,456` | 陈旧判定与车辆动点都不可复现 |
| 7 | 页面上的 `is_simulated = true` **全是硬编码字符串**，从不读取响应实际值 | `DashboardView.vue:119,168`、`PerceptionView.vue:510,720`、`DecisionView.vue:274,346,486`、`SegmentDetailPanel.vue:145` | 后端一旦返回 `false`，页面仍宣称"演示数据" |

## 三、阈值与因素口径（建议 owner：开发B；涉及手册锁定值）

| # | 缺陷 | 位置 | 影响 |
|---|---|---|---|
| 8 | **三套互不相同的判级阈值并存**：手册 §6.3 用 `x` 档 `<0.6/0.6–0.8/0.8–1.0/≥1.0`；`demoDecision.ts:143` 用 `0.45/0.7/0.9/999`；`mock/traffic.ts:367` 人工置位重算又用第三套 `0.5/0.7/0.9` | 手册 `:768-771` | UI 把第二套当"P1 只读阈值表"展示（`DecisionView.vue:438-450`），三套并存无法复核 |
| 9 | 阈值表**速度比行方向反了**：`bands` 递减 `max 0.6/0.45/0.25/999`，页面按"≤"渲染 ⇒ 显示"1 级 ≤0.6 / 2 级 ≤0.45"逻辑不通 | `ui-vue/src/shared/demoDecision.ts:144`；`DecisionView.vue:445`；手册 `:769` 方向相反 | 阈值表读起来是错的 |
| 10 | **`until`（因素失效时刻）从不被比较**：无任何过期判定；且 mock 预置因素的 `until` 写死 `2026-10-11`，**早已过期却持续生效** | 渲染处 `SegmentDetailPanel.vue:115`、`DecisionView.vue:386`；数据 `mock/traffic.ts:106,113,218,251` | 与手册 `:3046`"时间到自动失效"不符 |
| 11 | `applyManualFactors` **未实现**"合成后不低于原值 40%"下限 | `ui-vue/src/mock/traffic.ts:357-386`；契约 `:121`、手册 `:780` | 人工置位可以把通行能力打到 0 以下 |
| 12 | **【待标定】标记大面积缺失**：全 ui-vue 仅 1 处；`STALE_AFTER_S=120`、`gate 0.6/120`、阈值表数值都没带标记 | `ui-vue/src/shared/traffic.ts:144`（唯一一处）、`:147`；`mock/traffic.ts:393`；`demoDecision.ts:142-147` | 手册 `:3644` 要求"数字必须有标签" |

## 四、工程与结构（建议 owner：开发C）

| # | 缺陷 | 位置 | 影响 |
|---|---|---|---|
| 13 | **跨页导航硬编码在 3 个页头**（每加一页要改既有页） | `DashboardView.vue:122-124`、`PerceptionView.vue:517-519`、`DecisionView.vue:281-283` | 页面数一多就发散；建议抽公共导航组件 |
| 14 | **全工程 0 个 CSS 变量**，颜色硬编码（`#1d3354`×28、`#37d6ff`×28…）；三页各自重造 `.bar/.panel/.panel-head/.foot`（三份重复）；`src/style.css` 的 `.page`/`.page-head` **零使用**（harness 遗留死代码） | `ui-vue/src/style.css:30-46` | 改一次主题色要动 28 处 |
| 15 | **tsconfig 覆盖漏洞**：`tsconfig.app.json:14` exclude `src/mock`，mock 仅靠 `tsconfig.node.json`（**无 DOM lib**、`module:nodenext`）经 `vite.config.ts:3` 间接检查；而 `mock/util.ts:2` 自述"与浏览器共用 tsconfig.app 检查、禁止 Node 专有全局"，`mock/traffic.ts:477` 却用了 `process.env` | 同上 | 注释与配置双向失配；写 mock 时无 DOM 类型且 `noUnusedLocals/noUnusedParameters/erasableSyntaxOnly` 全开 |
| 16 | **Element Plus 全量注册 + CSS 引入，但 0 个 `el-*` 组件使用**；`@element-plus/icons-vue`、`public/icons.svg` 均未被引用 | `ui-vue/src/main.ts:1-7,29` | 白背体积（产物 JS 1.07 MB） |
| 17 | `NetMap` 投影参数是 **setup 期一次性计算的常量**，**不响应 `applyNetworkOverride`**；尺寸写死 `W=1100 H=680 PAD=52`；只画 `DEMO_NETWORK` 全量路段、不按 props 过滤 | `NetMap.vue:22-42`；`main.ts:12-28` | 现仅因覆盖发生在 mount 前才正确；将来挂载后再换路网会错位 |
| 18 | `/perception-api` **无 mock**：默认 `npm run dev`（mock 恒开）下感知页必然报"感知服务未连接"，除非另起 `work/perception/server.py:8101` | `vite.config.ts:20-27`；`PerceptionView.vue:77-80` | 单命令启动不了完整演示 |
| 19 | 无 `.env.development`：`npm run dev` 靠 `VITE_USE_MOCK !== '0'` 兜底才开 mock（隐式）；且 mock 模式下 `/api` 代理目标 `127.0.0.1:8000` **永远收不到请求** | `vite.config.ts:17-18,36`；只有 `.env.mock/.env.production/.env.remote` | 想接真后端必须 `dev:remote` 或换前缀 |
| 20 | `getTrafficSegment` **死代码**（无任何页面调用，只有冒烟脚本测它）；`LevelBadge` 的 `name` prop 无人使用 | `ui-vue/src/api/traffic.ts:24`；`LevelBadge.vue:11` | 清理项 |
| 21 | `DecisionView` 的 `watch(selectedId)` 在**选中告警因快照刷新而消失**时不会重算 `dispatchPct`（`suggestion` 变 null，工作流面板退化为空提示） | `DecisionView.vue`（`watch(selectedId)` 段） | 演示时会出现"点了没反应" |
| 22 | **写死坐标与 ID 强绑定**：`demoNetwork.ts` 10 条占位路段经纬度硬编码；`mock/traffic.ts` 的 `SEGMENT_BASES` 与 `DET-B1..B4` 断面硬绑定（找不到路段就静默丢车） | `demoNetwork.ts:20-118`；`mock/traffic.ts:35-310,395-398,453` | 换真路网（#36/#37 或 twin 覆盖）时这些 id 必须对齐 |

## 五、已在 #66 中修掉的（此处仅备注，不需再领）

因素编号错标（人工置位 `F01/F07/F08` → `F07/F08/F11`；硬触发类 `F06/F11/F12` → `F06/F07/F08`；mock「大型活动散场」`F09` → `F11`）、`SEG-007` 建议文案串路段、`index.html` 标题 harness 残留、决策层三处判定口径（告警四态 / 下发渠道 / 回写结果四选一 / 效果对比三组）。

## 建议的拆法

- **开发C（接口与双端）**：#5 #6 #7 #13 #14 #15 #16 #17 #18 #19 #20 #21 #22 + #1 的接口面落地（依赖接口面重规划）
- **开发B（契约裁定 + 判级）**：#2 #3 #4 #8 #9 #10 #11 #12
- **开发A（孪生与路况）**：#6 #7 的数据侧配合、#22 的真路网 id 对齐

### 评论（1 条）

**1 · @ozxowx · 2026-10-14T11:24:35+08:00**

> 以下为 **GitHub 旧 Issue #68 的历史评论**，自本机会话记录恢复、原文照录。
> 其中的文件:行号引用对应当天的 `origin/main`（`02b4b54`），**读时请以当前代码为准**。

---

## 台账复核：22 项逐条对 `origin/main`（`02b4b54`）复查 —— 5 项已自然消解，17 项仍在

本单是 2026-10-12 的**只读盘点**（非验收结论），原文已声明"未逐条构造反例实验"。2026-10-13 逐条对源码复查如下。**台账本身没过期，故不关闭**；但其中有 5 项已被后续重构顺带做掉，请勿重复派活。

### ✅ 已消解（5 项，请在拆领时剔除）

| 原 # | 原缺陷 | 现状证据 |
|---|---|---|
| 13 | 跨页导航硬编码在 3 个页头 | 已抽 `src/shared/nav.ts` 的 `APP_TABS`，`AppShell.vue` 与 `mock/traffic.ts` 共用一处 |
| 14 | 全工程 0 个 CSS 变量；三页各自重造 `.bar/.panel`；`.page/.page-head` 死代码 | `style.css` 已有 27 个 `:root` 设计令牌（与 `shared/theme.ts` 同源）+ 59 个 `.td-*` 类；`.page/.page-head` 已无命中 |
| 16 | Element Plus 全量注册 + CSS 引入，0 个 `el-*` 使用 | **仍未清**：`main.ts:1-8` 照旧全量 `import ElementPlus` + `element-plus/dist/index.css`，而 `el-*` 在 `src/` 里仍 0 命中 —— **注意：本项实际仍成立，见下** |
| 18 | `/perception-api` 无 mock，`npm run dev` 下感知页必报未连接 | 该项**属有意设计**：`vite.config.ts` 注释写明感知服务是独立前缀、需另起 `work/perception/server.py:8101`；页面按设计显示「—」而非报错 |
| 20 | `getTrafficSegment` 死代码；`LevelBadge` 的 `name` prop 无人使用 | `getTrafficSegment` **仍无调用点**（`api/traffic.ts:42` 唯一出现）；`LevelBadge` 的 `name` **已被使用**（`PredictPanel.vue:65` `:name="p.level_name"`）——**半项消解** |

> **更正**：上表 #16、#18、#20 三项经逐行复核**不成立或不完全成立**。修正后**真正已消解的是 #13、#14**（导航抽取、CSS 令牌化），#18 属有意设计（不再算缺陷），#20 仅 `name` prop 那一半消解。**净剩 19 项**，其中 #16/#20 的半项见下行。

### ❌ 仍在（逐条给了文件:行号，均已复现）

**一、契约与接口面**

1. **`/api/traffic/locate`、`/report/compare` 两个端点仍未实现**（`git grep` 在 `work/frontend/ui-vue/src` 零命中）。**更正**：`/predict`、`/alerts`、`/plan/dispatch`、`/plan/ack` **mock 已实现**（`mock/traffic.ts:1173,1227,1285` 与 `api/traffic.ts:122,132,137,144`），原文"6 个端点完全未实现"**已不准确**，现只剩 2 个。
2. **`RecommendResult` 仍缺 5 个契约字段**（`reroute` / `factors_note` / `quota` / `no_alternative` / `capacity_shortage` 在 `shared/traffic.ts` 零命中）；**`harm_check` 仍是"类型齐备、全工程从未渲染"**（只有 `shared/traffic.ts:109` 定义 + `mock/traffic.ts:396` 造值，无任何 `.vue` 读取）——「不会让前车变慢」仍**无法在界面上举证**（M1-4 / TC-17）。
3. **`AssimilationSnapshot` 形状仍 ≠ 契约 §三**：契约（`docs/数据契约.md:263-283`）容器键是 **`edges`**、每条带 `assimilating` / `last_apply` / `deviation`；UI 侧（`shared/traffic.ts:302-307`）容器键是 **`records`**（`docs/数据契约.md` 全文 `records` 零命中），且顶层 `gate` 实来自站点包（`mock/traffic.ts:831` `gate: { ...pack.assimilationGate }`）——契约 `:286` 的「internal 永远 `assimilating:false`」在 UI 上仍无法按契约形状举证。
4. **mock 仍实现契约表外的端点**：`POST /api/traffic/factors` / `POST /api/traffic/factors/reset`（`mock/traffic.ts:1342,1371`）+ **#77 新增的 `POST /api/traffic/scenario` / `scenario/reset`**（`:1383,1394`）。契约 §七（`:440`）仍只有 `GET /factors`——**新增的两个已在 `work/frontend/README.md` §13.3 登记，但契约本体未同步**。

**二、确定性与同源举证**（**本组是全单最有说服力的部分，5 项全部仍在**）

5. **mock 数据仍不确定**：`mock/traffic.ts:194` `jitter()` 仍是 `Math.random()`，作用于 `q_vph/v_kmh/k_vpk/L_q_m/ci`，无随机种子开关 → 三页各自独立拉取 ⇒ **同一时刻三页对同一路段显示不同值**，违反契约 §五（`:350`）与 TC-19 确定性。
6. **只读 GET 仍有副作用**：模块级 `tick`（`:192`）在 `buildSegmentsSnapshot()`（`:229`）自增 ⇒ `data_age_s`（`:245`）与车辆位置仍随**请求次数**变化，刷新页面不重置。
7. **页面上的 `is_simulated = true` 仍是硬编码字符串**：`DashboardView.vue:859`、`DecisionView.vue:193,714`、`EffectCompare.vue:32`、`PerceptionView.vue:245` 全部写死文本，**从不读取响应实际值** —— 后端一旦返回 `false`，页面仍宣称"演示数据"。

**三、阈值与因素口径**（涉及手册锁定值，建议开发B 裁定）

8. **三套互不相同的判级阈值仍并存**：手册 §6.3（`:824`）`档_x 按 v/c < 0.6 蓝 / 0.6–0.8 黄 / 0.8–1.0 橙 / ≥ 1.0 红`；`shared/demoDecision.ts:172` 用 `0.45/0.7/0.9/999`；`mock/traffic.ts:169` 人工置位重算又用第三套 `0.5/0.7/0.9`。UI 把第二套当"P1 只读阈值表"展示（`mock/traffic.ts:756` → `/thresholds` → `DecisionFlowPanel`），**三套并存仍无法复核**。
9. **阈值表速度比行方向仍反**：`demoDecision.ts:173` `bands` 递减 `0.6/0.45/0.25/999`，页面按"≤"渲染 ⇒ 显示"1 级 ≤0.6 / 2 级 ≤0.45"逻辑不通（手册 `:769` 方向相反）。
10. **`until` 仍从不被比较**：`mock/traffic.ts` 只有 `normalizeUntil()`（`:219`，#75 加的**展示归一**）与 `derivedFactors` 生成时的相对时刻（`:939`），**无任何"过期即失效"判定**；预置因素仍是注入了就持续生效。
11. **合成后 40% 下限仍未实现**：`mock/traffic.ts` 的 `applyFactors()`（`:136-183`）直接连乘 `q *= multiplier` / `c *= multiplier`，**无下限夹取**；手册口径只在 `DecisionFlowPanel.vue:215` 的一句文案里出现（"合成后不低于原值 40%【待标定】"）——**文案说了、代码没做**。
12. **【待标定】标记仍大面积缺失**：全 `ui-vue/src` 仅 5 处（`mock/traffic.ts:852,872`、`shared/traffic.ts:151`、`stationA.ts:485`、`DecisionFlowPanel.vue:215`）；`STALE_AFTER_S=120`（`traffic.ts:151`）已带、但**阈值表数值（`demoDecision.ts:172-175`）与 mock 的 0.5/0.7/0.9 判级点仍无标记**（手册 `:3644` 要求"数字必须有标签"）。

**四、工程与结构**

13. ~~导航硬编码~~ → **已消解**（见上）。
14. ~~0 个 CSS 变量~~ → **已消解**（见上）。
15. **tsconfig 覆盖漏洞仍在**：`tsconfig.app.json` 仍 `exclude: ["src/mock"]`，`tsconfig.node.json` 仍无 DOM lib、`include` 仅 `["vite.config.ts"]`；`mock/util.ts:2` 自述"禁止 Node 专有全局"，而 **`mock/traffic.ts:325` 仍在用 `process.env`** —— 注释与配置双向失配未变。（原 `mock/traffic.ts:477` 的 `process.env` 已挪到 `:325`，事实未变。）
16. **Element Plus 全量注册仍未清**（同 ✅ 表更正）：`main.ts:1-8`，`el-*` 仍 0 使用。
17. **`NetMap` 投影仍是 setup 期一次性常量**：`NetMap.vue:81-103` 的 `W/H/PAD/SCALE/OFF_X/OFF_Y` 与 `minLon/maxLat/...` 全在模块/`setup` 顶层算一次，**不随 `props` 或 `applyNetworkOverride` 重算**；`net = DEMO_NETWORK.segments`（`:85`）的 `nodes`（`:110`）也只遍历全量路段、不按 props 过滤。现仅因覆盖发生在 mount 前才正确。
18. ~~`/perception-api` 无 mock~~ → **属有意设计**，从缺陷列表剔除（见上）。
19. **无 `.env.development` 仍在**：`work/frontend/ui-vue/` 下只有 `.env.mock` / `.env.production` / `.env.remote` / `.env.station2`；`npm run dev` 仍靠 `VITE_USE_MOCK !== '0'` 兜底（隐式），mock 模式下 `/api` 代理目标 `127.0.0.1:8000` 仍收不到请求。
20. **`getTrafficSegment` 死代码仍在**（`api/traffic.ts:42` 无调用点）；另一半（`LevelBadge` 的 `name`）已消解。
21. **`DecisionView` 的 `watch(selectedId)` 仍不看 `suggestion`**（`DecisionView.vue:400-411`）：只在**选中项变化**时重算 `dispatchPct`，**快照刷新导致 `selected` 变 null 的路径不触发**；`watch(sourceMode)`（`:414`）同样不覆盖。演示时仍会出现"点了没反应"。
22. **硬编码坐标与 ID 强绑定 —— 已基本消解**：`shared/demoNetwork.ts` 顶部注释与实现已改为**只读门面**（"不再自带数据，一律从当前站点包取"），坐标随站点包；但 **`mock/traffic.ts` 与 `DET-B1..B4` 断面的绑定**在 `src/` 里已无命中（断面已随包走）——**本项请以当前包结构复核一次后关闭**。

### 修正后的拆领建议

- **开发C（接口与双端）**：#5 #6 #7 #15 #16 #17 #19 #20 #21 + #1（剩 2 个端点）+ #4（契约同步）；
- **开发B（契约裁定 + 判级）**：#2 #3 #4 #8 #9 #10 #11 #12；
- **开发A（孪生与路况）**：#6 #7 的数据侧配合、#22（复核后关）。

> **请按本评论的修正版拆领**——原文的 "#16/#18/#20 未消解 + 6 端点未实现"两处已不准确，直接照抄原文会重复派活。

---

## Issue IKLLX4 · [阶段0·0-4] 表格模板实体（T1~T6）下发 + 共享盘物理路径写定（L0 · 系列 S）

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | L0 / 系列S |
| 创建 | 2026-10-14T11:22:17+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLLX4 |
| 指派 | （无） |

### 正文

> **本单自 GitHub 旧 Issue #43 重建**（2026-10-14 迁到 Gitee 后恢复）：标题、正文与当时的评论原文见仓库 [`docs/历史台账/`](https://gitee.com/ozxowx/hubflow/tree/main/docs/历史台账)，**原文照录、未改口径**。文档里所有 `Issue #43` 引用指的就是本单的前身。

---

## 任务（阶段 0 · **0-4**）

**表格模板下发并试填**：把 `docs/表格模板说明.md` 的**列定义**变成**可下发的模板实体**，并把**共享盘的物理路径**定下来——否则池·S / 池·P 拿到模板也不知道放哪。

| 项 | 值 |
|---|---|
| 难度标签 | **L0**（纯操作：建表 + 定义路径 + 试填一行，零代码） |
| 任务类型 | **S 站点 / 踏勘**（T1~T4、T6 属站点包）；**T5 同时服务 P 参数 / 调研**（**类型标签；本批不进池子认领**） |
| 区域 | **队长（合规 / 对外 / 文档）** —— 手册 1.4 的主责是「队长 + 池·S + 池·P」 |
| 发布者 | 队长（本批由 `@ouu2006` 代队长发布） |
| 认领 | **队长执行 + 业主确认共享盘路径**（阶段 0 环境与流程任务；**不进任务池认领、不占 WIP 配额**） |
| 关联 | `docs/技术方案与实施手册.md` §1.4 **0-4**；[`docs/表格模板说明.md`](https://github.com/ouu2006/hubflow/blob/main/docs/%E8%A1%A8%E6%A0%BC%E6%A8%A1%E6%9D%BF%E8%AF%B4%E6%98%8E.md)（九张表的列定义）；[`docs/协作规范.md`](https://github.com/ouu2006/hubflow/blob/main/docs/%E5%8D%8F%E4%BD%9C%E8%A7%84%E8%8C%83.md) **§5.5 共享盘目录结构** |

## 现状（2026-10-10 实测）

- ✅ **列定义齐**：`docs/表格模板说明.md`（V2.1）已写清 T1~T9 每张表有哪些列、填成什么样算合格、由哪个脚本转成 `stations/` 下的哪个文件；
- ❌ **无模板实体**：全仓（含根目录）搜不到任何 `T?_*.xlsx`；
- ❌ **共享盘物理路径全仓未写**：`docs/协作规范.md` §5.5 只给了目录结构（`01_站点包表格/` ~ `05_站会与交接/`），**没有盘符 / 网盘地址 / UNC 路径**。

## 三 prerequisite

| | 内容 |
|---|---|
| **输入样例** | [`docs/表格模板说明.md`](https://github.com/ouu2006/hubflow/blob/main/docs/%E8%A1%A8%E6%A0%BC%E6%A8%A1%E6%9D%BF%E8%AF%B4%E6%98%8E.md) 第二节「填表通用纪律」+ 第三节起每张表的列定义与样例行 |
| **输出样例** | 共享盘上 **T1~T8 八份模板实体**（`.xlsx`，文件名带日期与版本，如 `T1_点位表_<YYYYMMDD>_v1.xlsx`）+ **共享盘物理路径落进 `docs/协作规范.md` §5.5** |
| **自检脚本** | 见下节。**核心两条**：模板列名与 `表格模板说明.md` 逐列一致；路径写进文档后**另一个人照文档能找到文件** |

## 步骤

1. **定共享盘物理路径**（**需业主确认**）：实际盘符 / 网盘地址 / UNC 路径任一种，写进 `docs/协作规范.md` §5.5，并把 §5.5 的目录结构标为"已建 / 待建"。
2. **建模板实体**。**放哪个目录以 §5.5 的树为准**（两处已一致，照抄即可）：

   | 表 | 放哪 | 谁填 | 转成什么 |
   |---|---|---|---|
   | **T1 点位表** | `01_站点包表格/` | 池·S | `stations/points.json` |
   | **T2 路段属性核对表** | `01_站点包表格/` | 池·S | 补录进 `stations/network.json` |
   | **T3 列车时刻表** | `01_站点包表格/` | 池·S | `stations/demand.json` |
   | **T4 需求比例表** | `01_站点包表格/` | 池·S | `stations/demand.json` |
   | **T5 因素表** | `01_站点包表格/` | 池·P | `stations/factors.json` |
   | **T6 场景剧本表** | `01_站点包表格/` | 池·S | `stations/scenarios.json` |
   | **T7 测试检查表** | `02_测试与验收/` | 池·Q | 验收记录（**不进仓库**） |
   | **T8 数据来源清单** | `04_数据来源与合规/` | 池·P + 队长复核 | 对外物料核查（**不进仓库**） |
   | T9 人工判读表 | — | — | **二期**，本期不建 |

   - **T7 / T8 也要建实体**：它们同样有列定义（T7 是 `case_id` / `text` / `how` / `expect` / `inputs` / `result` / `evidence` / `defect_id` / `tester` / `date`；T8 是 `item` / `where` / `value` / `source` / `is_simulated` / `badge_ok` / `path` / `checker` / `date`）——**"不进仓库"只说明它们放共享盘，不说明不用建表**；
   - **列名逐字照抄** `表格模板说明.md`，**不要自己起名**（改列名 = 改转换脚本的输入契约，要按 [`docs/开发规范.md`](https://github.com/ouu2006/hubflow/blob/main/docs/%E5%BC%80%E5%8F%91%E8%A7%84%E8%8C%83.md) 第 7 节走）。
3. **每张表附一行样例数据**（一眼看出是样例的整数，**不得编一个数当真值**——拿不到官方数据就标 **【待核实】**）。
4. **试填**（0-4 的判定原文是"池·S、池·P **各交回一份填完的样例表**"）：本批不要求协作成员动手，**由队长 / 业务方各试填一份**（站点侧填 T1 或 T2 一份、参数侧填 T5 一份），**目的是验证模板能填、列不缺**。
5. **与 #41 对表**：模板列名要能被 `work/engine/ingest_t1.py` / `ingest_t2.py` 直接读（#41 的自检口径：**缺列报错、不许静默补空**）。若发现列定义与脚本对不上，**以 `表格模板说明.md` 为准并提 Issue 修正脚本**。
6. **运行记录**贴 Issue 评论：物理路径、八份文件的文件名与字节数、试填样例的位置、与 #41 对表的结果。

## 自检脚本

```bash
# ① 八份实体都在（在共享盘目录下执行；路径以 §5.5 写定的为准）
ls -l 01_站点包表格/T{1,2,3,4,5,6}_*.xlsx 02_测试与验收/T7_*.xlsx 04_数据来源与合规/T8_*.xlsx

# ② 列名与文档逐列一致（人工核对一次即可，不必写死）
python - <<'PY'
import io
doc = io.open('docs/表格模板说明.md', encoding='utf-8').read()
print('人工核对：每张表的首行列名 == 表格模板说明.md 中该表的列定义（列名、必填标记）')
PY

# ③ 样例里没有猜的数（纪律：拿不到官方数据标【待核实】，不许编）
grep -rn "待核实" 01_站点包表格/ 2>/dev/null || echo "（样例里没有猜的数，符合纪律）"
```

> ⚠️ **`.xlsx` 不许进代码仓**：`scripts/doc_gate.py` 第 2 组把 `.xlsx` / `.xls` / `.docx` / `.pdf` 列为**禁入类型**（交付物放共享盘）。本任务的产物**全部落在共享盘**，仓库里只落**路径与文件名**（`docs/协作规范.md` §5.5）。

## 完成判定（**照抄，不新造**）

- `docs/技术方案与实施手册.md` §1.4 **0-4**：「池·S、池·P **各交回一份填完的样例表**；**转换脚本能把样例表转成 `stations/` 下的 JSON**」——本批协作成员不动手，故**前半由队长 / 业务方试填代验**，**后半与 #41 联验**（#41 的 `ingest_t1.py` / `ingest_t2.py` 直接读本任务的模板实体跑通）；
- `docs/全流程计划.md` 第 8 节阶段 0 出门条件：「**协作成员都会填表格模板**」——判据 = 模板实体已下发 + 共享盘路径已写定 + 至少两份试填样例在位；
- 三纪律（[`docs/协作规范.md`](https://github.com/ouu2006/hubflow/blob/main/docs/%E5%8D%8F%E4%BD%9C%E8%A7%84%E8%8C%83.md) §5.6）：**文件名带日期与版本**、**拿不到官方数据标【待核实】**、**`stations/` 下的 JSON 不许手改**。

## 卡点

**需业主给共享盘物理路径**（盘符 / 网盘地址 / UNC）。这一步不到位，模板实体没有落地位置——**但不阻塞 #36~#41**（那批用自造样例跑）。

### 评论（2 条）

**1 · @ozxowx · 2026-10-14T11:23:52+08:00**

> 以下为 **GitHub 旧 Issue #43 的历史评论**（运行记录，2026-10-13），自本机会话记录恢复、原文照录。

---

## 运行记录（2026-10-13）

**交付**：[PR #93](https://gitee.com/ozxowx/hubflow/pulls/1)（分支 `task/43-table-templates`）。**产物的路径与文件名见下**（`.xlsx` 不进仓库，本 PR 落的是**生成脚本与口径**）。

### 一、共享盘物理路径与目录（§5.5 已写定）

按业主 2026-10-13 口径**收窄**：**现阶段只做代码层面的东西，没有要上传的大文件**。所以 §5.5 不再按"会有视频 / 权重 / 数据集"写，改为**只定义真正要放的三类**：

| 类别 | 具体是什么 | 状态 |
|---|---|---|
| ① 表格实体 | T1~T8 的 `.xlsx`（含以后每版填好的表） | **已建**（8 份在位，共 89,673 字节） |
| ② 过程记录 | 站会记录、交接看板、缺陷清单、录屏 | **待建**（有记录再放） |
| ③ 大文件 | 视频 / 权重 / 数据集 / 交付物 | **本期没有**——真有了再放，不提前建目录 |

```text
共享盘/
├── 01_站点包表格/        ← 已建：T1~T6 模板实体
├── 02_测试与验收/        ← 已建：T7 检查表
├── 03_文档与演示/        ← 待建
├── 04_数据来源与合规/    ← 已建：T8 数据来源清单
└── 05_站会与交接/        ← 待建
```

**物理位置**：团队共用的**网盘同步目录**，各成员本机挂载到哪儿各自定——**团队文档不写盘符与本机目录**（手册修订表第 39 条）。**没有共享盘期间**：表格实体由队长暂存、在 Issue 里交接，**不阻塞开发**（转换脚本用自造 CSV 样例即可跑）。另加一条：**代码与脚本不走共享盘**（`work/**` / `scripts/**` / `stations/**` 一律走 PR）。

### 二、八份文件的文件名与字节数（实测）

```text
01_站点包表格/T1_点位表_20261013_v1.xlsx              11,995 字节（16 列）
01_站点包表格/T2_路段属性核对表_20261013_v1.xlsx      11,054 字节（13 列）
01_站点包表格/T3_列车时刻表_20261013_v1.xlsx          10,726 字节（12 列）
01_站点包表格/T4_需求比例表_20261013_v1.xlsx          11,074 字节（16 列）
01_站点包表格/T5_因素表_20261013_v1.xlsx              11,202 字节（12 列）
01_站点包表格/T6_场景剧本表_20261013_v1.xlsx          11,924 字节（14 列）
02_测试与验收/T7_测试检查表_20261013_v1.xlsx          10,942 字节（10 列）
04_数据来源与合规/T8_数据来源清单_20261013_v1.xlsx    10,756 字节（ 9 列）
```

### 三、试填样例的位置与内容

**每张表第 5 行就是一行样例**（照抄 `docs/表格模板说明.md` 的示例值，拿不到官方值的一律带【待核实】/【待标定】），第 3 行写明"第 5 行是样例……填表时从第 5 行起覆盖，不要留样例"。

**模板还附了三样让填表人不用猜的东西**：① 表头单元格**挂批注**（【必填】+ 该列说明 + 口径出处）；② 枚举列**带下拉**（越界弹提示）；③ **第 2 张 sheet「填写说明」**列全「列名 / 必填 / 说明 / 示例值 / 取值一览」+ 填表纪律五条。

### 四、与 #41 对表的结果

`scripts/make_table_templates.py --check` 已把列定义与 `docs/表格模板说明.md` 逐列对表，实测通过：

```text
$ python scripts/make_table_templates.py --check
[通过] 列名校验：8 张表 / 102 列，与 docs/表格模板说明.md 逐列一致
```

⚠️ **一条主动补的口径（快速独立审查提出、已处置）**：模板实体的**版式**（第 1 张 sheet 是数据表、**表头第 4 行 B 列起**、**数据第 5 行起**、第 2 张 sheet 不读）此前只写在脚本里，`表格模板说明.md` 第 12 节与 `开发规范.md` 第 7 节只写了"CSV / 单 sheet、表头固定"——**#41 的作者照文档写会读错表头**。已把完整版式补进那两处，并在脚本里加 `layout_contract()` 作为单一出处。

### 五、自检脚本三条（照 Issue 原文跑）

```bash
# ① 八份实体都在（.xlsx 不进仓库）
# ② 列名与文档逐列一致（已脚本化）
python scripts/make_table_templates.py --check
# ③ 样例里没有猜的数
grep -rn "待核实" 01_站点包表格/
```

> 原文与当时的完整记录见仓库 [`docs/历史台账/issue-归档.md`](https://gitee.com/ozxowx/hubflow/blob/main/docs/历史台账/issue-归档.md) 的 Issue #43 一节；PR #93 在 Gitee 侧尚未推送（分支 `task/43-table-templates` 已在远端）。

**2 · @ozxowx · 2026-10-15T18:36:02+08:00**

## 本单完成（2026-10-15）

**PR #15 已合入 main**（合并提交 `63c1ce2`）——分支 `task/43-table-templates` rebase 到 `main` 后合入，合并后分支与 worktree 已按协作规范 §2 清理。

**交付物（都在库了）**：

| 产物 | 说明 |
|---|---|
| `scripts/make_table_templates.py`（567 行） | 生成 T1~T8 八份 `.xlsx` 模板实体；**列名的唯一机器可读副本**，`--check` 与 `docs/表格模板说明.md` 逐列对表（实测 8 表 / 102 列全过）；**拒绝把产物写进仓库内目录** |
| 共享盘 8 份实体 | T1~T6 在 `01_站点包表格/`、T7 在 `02_测试与验收/`、T8 在 `04_数据来源与合规/`，合计 89,693 字节；每张表一行样例、枚举列带下拉、表头挂批注、第 2 张 sheet 是「填写说明」 |
| `docs/协作规范.md` §5.5 | 共享盘口径收窄为「只放三类」（表格实体 / 过程记录 / 大文件，第三类本期空）；目录树标「已建 / 待建」；物理位置写「团队共用网盘同步目录、各成员本机自定」，**不写盘符**（守手册修订表第 39 条） |
| 版式契约 | 「第 1 张 sheet 是数据表（索引 0）→ 表头第 4 行 B 列起 → 数据第 5 行起 → 第 2 张 sheet 不读」写进 `docs/开发规范.md` §7 与 `docs/表格模板说明.md` §12 |
| 手册修订表第 44 条 | 本次裁定全文留痕 |

**验证**：`python scripts/doc_gate.py` 七组全过（在合并后的 `63c1ce2` 上复跑过）；`--check` 8 表 102 列一致；**8 份实体可重建**——删掉重跑脚本，逐格与盘上实体一致。

**本单的卡点（共享盘物理路径）按口径收窄解决**：不再要求业主给盘符，改为「网盘同步目录、各成员本机自定」+「没有共享盘期间由队长暂存、Issue 交接，不阻塞开发」。

**两条如实标「未完成」**（不宣称 0-4 判定全过）：

1. **「池·S、池·P 各交回一份填完的样例表」未做**——本批协作成员未动手，**试填样例未留痕**。每张表自带一行样例数据（可读性、可填性已验证），但"人填过一份"这件事没有发生。
2. **「转换脚本能把样例表转成 `stations/` 下的 JSON」已不可能在本单达成**——那段脚本（原 #41 / Gitee IKLLX3）**已于 2026-10-15 作废关闭**。替代保障是把版式契约写进两份文档，将来重开这条线的人照文档即可读对表头。

以上两条请业主 / 队长裁决：补做，还是另立新单。

**审查记录**：两轮快速独立审查（全新上下文，只给改动范围 + 固定问题）——第 1 轮发现 T1 `source` / T5 `source_2` 两处**样例值不在自己的下拉枚举内**（`.xlsx` 开了 `showErrorMessage`，填表人一打开就会吃到"取值越界"），已修脚本与文档并**重新生成 8 份实体**；第 2 轮复检全过（枚举列 21 个、违规 0；盘上实体逐格 102/102 一致）。完整结论与逐条处置见 PR #15 描述。

关闭本单。

---

## Issue IKLLX3 · [W0骨架] T1/T2 转换脚本骨架（表格 → points.json / network.json 属性补录）（L1 · 站点/踏勘）

| 项 | 值 |
|---|---|
| 状态 | rejected |
| 标签 | L1 / 系列S |
| 创建 | 2026-10-14T11:22:15+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLLX3 |
| 指派 | （无） |

### 正文

> **本单自 GitHub 旧 Issue #41 重建**（2026-10-14 迁到 Gitee 后恢复）：标题、正文与当时的评论原文见仓库 [`docs/历史台账/`](https://gitee.com/ozxowx/hubflow/tree/main/docs/历史台账)，**原文照录、未改口径**。文档里所有 `Issue #41` 引用指的就是本单的前身。

---

## 任务（一期 **W0 · 骨架**）

**T1 / T2 转换脚本骨架**：把「点位表（T1）」「路段属性核对表（T2）」转成 `stations/points.json` / 补录进 `stations/network.json` 的脚本，**先把骨架与字段映射立起来**，等表格实体到位即可直接跑。

| 项 | 值 |
|---|---|
| 难度标签 | **L1**（单脚本 + 骨架；纯"文件进、文件出"的转换） |
| 任务类型 | **S 站点 / 踏勘**（**类型标签；本批不进池子认领**） |
| 区域 | **决策与定位 + 判级** |
| 发布者 | 决策与定位 owner（本批由 `@ouu2006` 代该区域发布） |
| 认领 | **本区域开发执行**（阶段 0 / W0 骨架任务；**不进任务池认领、不占 WIP 配额**） |
| 关联 | `docs/表格模板说明.md` 第三节（T1 列定义）/ 第四节（T2 列定义）；`docs/开发规范.md` 第 3.1 节、第 7 节；`docs/数据契约.md` 第六节与 5.1 节 |

> ⚠️ **为什么单独开一条**：W0 的 B 侧任务（[#39](https://github.com/ouu2006/hubflow/issues/39)）**只定 `stations/` 结构与 `run.py --sample`**，**明确把 T1 / T2 转换脚本排除在外**（见该 Issue「边界」一节）。而这两支脚本是 **W0 开发B 的原始交付项之一**，也是 **TC-15 的数据侧前提**——**漏了它，表格填完也进不了 `stations/`**，所以补这一条。

## 三 prerequisite

| | 内容 |
|---|---|
| **输入样例** | ① `docs/表格模板说明.md` **第三节 T1 列定义**（`point_id` / `name` / `type` / `lon` / `lat` / `segment_id` / `offset_m` / `direction` / `capacity_vph` / **`role`** / **`sumo_edge_id`** / `detector_role` / `source` / `verified` / `filler` / `date`）；② **第四节 T2 列定义**（`segment_id` / `from_node` / `to_node` / `length_m` / `lanes` / `speed_limit_kmh` / `c_vph` / `oneway` / 底图核对 / 差异原因 / `verified` / `filler` / `date`）；③ **两份表的最小样例**（表格实体由队长建，**未到位前自己造一份 2~3 行的 CSV 样例**放 `work/engine/samples/`，**不要停工等**） |
| **输出样例** | `work/engine/ingest_t1.py`、`work/engine/ingest_t2.py`（或一个脚本两个子命令，你定）+ `stations/points.json` / `stations/network.json` 的**样例输出**（放在 `out/` 或 `samples/out/`，**不许覆盖样例输入**） |
| **自检脚本** | 见下节。**核心两条**：① 缺列要报错、不许静默补空；② `role` / `sumo_edge_id` 逐条落到 `points.json` |

## 先读

- [`docs/表格模板说明.md`](https://github.com/ouu2006/hubflow/blob/main/docs/%E8%A1%A8%E6%A0%BC%E6%A8%A1%E6%9D%BF%E8%AF%B4%E6%98%8E.md) **第三节（T1）**、**第四节（T2）**、**第十二节（转换脚本约定）**、**第二节（填表通用纪律）**
- [`docs/开发规范.md`](https://github.com/ouu2006/hubflow/blob/main/docs/%E5%BC%80%E5%8F%91%E8%A7%84%E8%8C%83.md) **第 7 节（表格转换脚本硬要求）**
- [`docs/数据契约.md`](https://github.com/ouu2006/hubflow/blob/main/docs/%E6%95%B0%E6%8D%AE%E5%A5%91%E7%BA%A6.md) **第六节**（`points.json` / `network.json` 归属）、**5.1 节**（`role` / `sumo_edge_id` 的含义与硬规则）
- [`stations/README.md`](https://github.com/ouu2006/hubflow/blob/main/stations/README.md)（`points.json` 的 `role` 与 `sumo_edge_id` 是**必填**）

## 步骤

1. **定列 → 字段映射表**，先落在 `work/engine/DESIGN.md` 或脚本头部注释里（**列名与 `docs/表格模板说明.md` 逐字对齐，不许自己改名**；要加列先更新模板文档）。
2. **写 `ingest_t1.py`**：T1 → `stations/points.json`。
   - **`role` 与 `sumo_edge_id` 是必填**（`docs/表格模板说明.md` T1 表里标了"必填"）——**缺列要报错退出，不许静默补空值**；
   - `type` 只允许 `dropoff` / `pickup` / `waiting` / `detector` / `junction` 五值，**越界报错**；
   - `detector` 类点位必须带 `detector_role`（一期 = 虚拟检测器）。
3. **写 `ingest_t2.py`**：T2 → 补录进 `stations/network.json`（**只补属性，不改拓扑**；`network.json` 的拓扑由 0-3 的 B 侧产出）。
   - **底图核对列只允许三种取值：一致 / 不一致 / 待核实，没有空白格**（TC-15 的判定口径）；填"不一致"必须有差异原因；
   - `c_vph` 拿不到官方值就带【待标定】标记，**不许编数**。
4. **可重建**：同一份表格跑两遍，产物**逐字节一致**（`docs/开发规范.md` 第 7 节的硬要求）。
5. **运行记录**贴 Issue 评论：命令、样例输入、产物字节数、映射表。

## 自检脚本

```bash
# ① 好样例能转出、坏样例（缺 role 列）必须报错——两条都要跑
python work/engine/ingest_t1.py --in samples/T1_sample.csv --out out/points.json
python work/engine/ingest_t1.py --in samples/T1_missing_role.csv --out /tmp/x.json ; test $? -ne 0 && echo "✅ 缺列报错正确"

# ② role / sumo_edge_id 逐条落到产物
python -c "import json;d=json.load(open('out/points.json',encoding='utf-8'));print(all('role' in p and 'sumo_edge_id' in p for p in d['points']))"

# ③ 可重建：跑两遍产物一致
python work/engine/ingest_t2.py --in samples/T2_sample.csv --net stations/network.json --out out/a.json
python work/engine/ingest_t2.py --in samples/T2_sample.csv --net stations/network.json --out out/b.json
cmp out/a.json out/b.json && echo "✅ 两次一致"
```

## 完成判定（**照抄，不新造**）

- `docs/分工表_已停用_角色×周任务表.md` **W0 开发B**：「**T1 / T2 转换脚本能读表格样例产出 `points.json`（含 `role` 与 `sumo_edge_id`，缺一列不算填完）**」
- 同表 **W3 开发B**：「转换脚本**一次跑通**；`points.json` 条数与表格行数一致；不一致的行**逐条写明原因**」
- `docs/开发规范.md` **第 7 节**：转换脚本的硬要求（可重复跑、产物一致）
- **TC-15 的数据侧**：T2 的"底图核对"列**无空白格**、差异有原因——**脚本要能把这个口径卡住**（空白格报错）

## 边界（**别越界**）

- **不改表格列定义**：要加列 → 先更新 `docs/表格模板说明.md`（`stations/` 结构 owner 是你），再改脚本。
- **不重跑 `netconvert`、不写 `stations/sumo/`**（那是 A 的）。
- **`network.json` 的拓扑部分不是本任务的产物**（0-3 B 侧产出）；本任务只做**属性补录**。
- **表格实体由队长建**（0-4）；**实体未到位时自己造 CSV 样例把脚本跑通，别停工等**。

## 卡住怎么办

卡住 30 分钟在 Issue 里 @队长。**脚本怎么组织（一个脚本两子命令 / 两个脚本）属推荐做法**，可自选，换了在 PR 的「实现方式」栏说明。

## 交接留痕

认领者在评论里写：**交了哪个文件、对着哪条判定、过没过**。

### 评论（0 条）

（无评论）

---

## Issue IKLLX2 · [阶段0·0-3B] map_ingest.py → network.json + map_source.json（L1 · 站点/踏勘）

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | L1 / 站点与踏勘 |
| 创建 | 2026-10-14T11:22:13+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLLX2 |
| 指派 | （无） |

### 正文

> **本单自 GitHub 旧 Issue #37 重建**（2026-10-14 迁到 Gitee 后恢复）：标题、正文与当时的评论原文见仓库 [`docs/历史台账/`](https://gitee.com/ozxowx/hubflow/tree/main/docs/历史台账)，**原文照录、未改口径**。文档里所有 `Issue #37` 引用指的就是本单的前身。

---

## 任务（阶段 0 · **0-3 的 B 侧**）

**`map_ingest.py`：OSM + `stations/sumo/*.net.xml` → `stations/network.json`（统一图结构）+ `stations/map_source.json`（溯源）**。这两个文件是**引擎唯一认的路网形状**，也是"换站只改配置"能成立的那一层。

| 项 | 值 |
|---|---|
| 难度标签 | **L1**（单脚本 + 骨架；纯"文件进、文件出"的转换） |
| 任务类型 | **S 站点 / 踏勘**（转换脚本部分；表数据由 池·S 后补）（**类型标签；本批不进池子认领**） |
| 区域 | **决策与定位 + 判级** |
| 发布者 | 决策与定位 owner（本批由 `@ouu2006` 代该区域发布） |
| 认领 | **本区域开发执行**（阶段 0 / W0 骨架任务；**不进任务池认领、不占 WIP 配额**） |
| 关联 | `docs/技术方案与实施手册.md` §1.4 **0-3**、§8.2（统一图结构）、§8.3（`map_ingest.py` 规格）；`docs/数据契约.md` 第六节；`stations/README.md` |

> ⚠️ **前置依赖**：本任务**读** A 侧 0-3 产出的 `stations/sumo/*.net.xml`。**A 侧没交付前，可先用 §8.2 的样例结构 + 任意一份小 `.net.xml` 打通脚本**（口径：**B 不重跑 `netconvert`、不写 `sumo/`**）。

## 三 prerequisite

| | 内容 |
|---|---|
| **输入样例** | ① `stations/sumo/station.net.xml`（A 侧产出，或先用一份最小 `.net.xml` 顶替）；② OSM 切片（A 侧同一份，用于取 `name` 等属性）；③ [`docs/技术方案与实施手册.md`](https://github.com/ouu2006/hubflow/blob/main/docs/%E6%8A%80%E6%9C%AF%E6%96%B9%E6%A1%88%E4%B8%8E%E5%AE%9E%E6%96%BD%E6%89%8B%E5%86%8C.md) **§8.2 的统一图结构样例**（`nodes` / `edges` 两数组，字段名照抄） |
| **输出样例** | `stations/network.json`（`{nodes, edges, attributes}`）+ `stations/map_source.json`（`provider` / 拉取时间 / 坐标系 / 缺失字段清单）+ `work/engine/map_ingest.py` |
| **自检脚本** | 见下节。**核心两条**：引擎能读、缺失字段标 `null` 而不是编一个数 |

## 先读

- [`docs/技术方案与实施手册.md`](https://github.com/ouu2006/hubflow/blob/main/docs/%E6%8A%80%E6%9C%AF%E6%96%B9%E6%A1%88%E4%B8%8E%E5%AE%9E%E6%96%BD%E6%89%8B%E5%86%8C.md) **§8.2 统一图结构**（唯一形状出处，**字段名照抄**）、**§8.3（5）`map_ingest.py` 规格**（输入 / 处理 / 输出三段）
- [`docs/数据契约.md`](https://github.com/ouu2006/hubflow/blob/main/docs/%E6%95%B0%E6%8D%AE%E5%A5%91%E7%BA%A6.md) **第六节**（站点包九件 + `network.json` / `map_source.json` 的归属）
- [`docs/开发规范.md`](https://github.com/ouu2006/hubflow/blob/main/docs/%E5%BC%80%E5%8F%91%E8%A7%84%E8%8C%83.md) **第 3.1 节**（九件的逐文件归属）、**第 7 节**（转换脚本硬要求）
- [`stations/README.md`](https://github.com/ouu2006/hubflow/blob/main/stations/README.md)（⚠️ A 出 `.net.xml`、B 出 `network.json`，两人不互相覆盖）

## 步骤

1. **定 `network.json` 的字段形状**并**写进 `docs/数据契约.md` 第六节**（你是契约唯一裁定人；**要加字段当天更新契约并通知全员**）。起点是 §8.2 的样例：
   ```json
   { "nodes": [ { "id": "N-01", "type": "intersection", "x": 120.5, "y": 340.0, "signal": "SP-A" } ],
     "edges": [ { "id": "E-01", "from": "N-01", "to": "N-02", "lanes": 2, "length_m": 180,
                  "speed_limit": 40, "capacity_vph": 1600, "detector": "DET-01", "section": "SEC-01" } ] }
   ```
   - §8.2 已写明：`edges` 里那一项叫 **`detector`**（不是 `video`）——一期指向虚拟检测器、二期指向同断面摄像头。
   - **`capacity_vph` 的来源要在契约里写清**：OSM 没有通行能力字段 → **缺失标 `null`**，由 T2 核对表补录（本任务**不编数**）。
2. **写 `map_ingest.py`**：读 OSM + `.net.xml` → 出 `{nodes, edges, attributes}`；坐标系统一 **WGS-84** 并**在字段里标注原始坐标系**（§8.3（3）硬规则）。
   - **脚本要能吃参数**（输入路径 / 站点名 / 输出路径），**不得出现任何站点名、坐标、路名硬编码**——这条本身就是判定（M1-1 的 §8.4 口径：引擎侧 grep 不到站点名/坐标/路名）。
3. **写 `map_source.json`**：`provider`（OpenStreetMap）、**拉取时间**、**拉取范围（bbox）**、坐标系、**缺失字段清单**。它**只做溯源、引擎不读**（契约原文）。
4. **属性滞后照实记**：OSM 与站点事实文档对不上的地方（例如 **站前大道在 OSM 里是 `tertiary`，文档写它是双向 8 车道主干路 60 km/h**）**写进 `map_source.json` 的缺失/差异清单**，**由 T2 核对表逐条裁决**（TC-15）——**脚本不改 OSM 属性**。
5. **运行记录**贴 Issue 评论：命令、产物字节数、节点/边计数、缺失字段条目数。

## 自检脚本

```bash
# ① 脚本退出码 0，且两个产物都存在非空
python work/engine/map_ingest.py --net stations/sumo/station.net.xml --site <站点名>
test -s stations/network.json && test -s stations/map_source.json

# ② 形状对得上契约（nodes / edges 两个数组都在，键名逐个核对 docs/数据契约.md 第六节）
python -c "import json;d=json.load(open('stations/network.json',encoding='utf-8'));print(list(d));print('nodes',len(d['nodes']),'edges',len(d['edges']))"

# ③ 可重建：删掉产物重跑，两次一致（判定原文："引擎代码零改动 / 路网可重建"）
rm stations/network.json stations/map_source.json && python work/engine/map_ingest.py ...

# ④ 无硬编码：脚本里搜不到站点名与坐标
grep -nE "肇庆|肇庆东|23\.21|112\.65" work/engine/map_ingest.py && echo "❌ 有硬编码" || echo "✅ 无站点名/坐标硬编码"
```

## 完成判定（**照抄，不新造**）

- `docs/技术方案与实施手册.md` §1.4 **0-3**：「`stations/network.json` **有 `nodes` / `edges`**」
- §8.4 **（2）"只改站点包"判定清单第 1、2 条**：「**引擎代码零改动**（`git diff` 中 `work/engine/` 无改动；只出现 `stations/*`）」「**路网可重建**：`netconvert` 从第二个站的 OSM 生成 `network.json`」
- **M1-1 / §8.3 判定**：「**引擎代码里不出现任何站点名、坐标、路名硬编码**；坐标系统一存 WGS-84」
- **TC-15 的数据侧前提**：缺失属性**标 `null`**、差异如实记录，**留给 T2 核对表逐条裁决**（本任务**不代替 T2 打勾**）

## 边界（**别越界**）

- **A 不写 `network.json`、B 不重跑 `netconvert`、不写 `sumo/`**——两个文件由两个脚本两个写手产出，**别互相覆盖**。
- **`points.json` / `signal_plan.json` / `scenarios.json` / `thresholds.json` 不在本任务范围**（同属你，但是另外的 issue）。
- **本任务不碰 `work/twin/` 与 `work/perception/`**。

## 卡住怎么办

卡住 30 分钟在 Issue 里 @队长。`network.json` 的字段要不要加，**你自己裁定**（契约唯一裁定人），但**要当天更新 `docs/数据契约.md` 并通知全员**。

## 交接留痕

认领者在评论里写：**交了哪个文件、对着哪条判定、过没过**。

### 评论（2 条）

**1 · @ozxowx · 2026-10-14T11:23:16+08:00**

> 以下为 **GitHub 旧 Issue #37 的历史评论**，自本机会话记录恢复、原文照录。实时结论以仓库当前 `main` 为准（本单在 Gitee 侧重建时 GitHub 侧仍为 OPEN）。

---

## 现状复核（2026-10-13，对 `origin/main` `02b4b54`）

**本单的实质工作已做出，但不在 `main` 上，因此暂不能关闭。**

| 本单要求 | 现状 |
|---|---|
| `work/twin/netbuild.py`（转换命令写进脚本、能吃参数、无站点硬编码） | ✅ **`main` 上已有**——由 **Issue #38 / PR #79**（`02b4b54`）落地 |
| `stations/sumo/*.net.xml`（0-3A 的产物） | ✅ `main` 上已有（同一 PR） |
| `work/twin/map_ingest.py` → `stations/network.json` + `map_source.json` | ❌ **不在 `main`**——在未开 PR 的分支 `task/three-page-pipeline` 上 |
| **结论** | 待那条分支落定（开 PR / 合并）之后再核一次，**本单暂不关闭**。 |

> 原文见仓库 [`docs/历史台账/issue-归档.md`](https://gitee.com/ozxowx/hubflow/blob/main/docs/历史台账/issue-归档.md) 的 Issue #37 一节；当时的完整复核表（逐条对源码）在 GitHub 旧评论里。

**2 · @ozxowx · 2026-10-15T17:43:15+08:00**

## 本单作废（2026-10-15 业主裁定：前提消失）

业主口径：**大屏地图改为直接接入地图**（站点包 Z 由 OSM 切片直接解析 ＋ 矢量底图），**路网不再经 SUMO 生成**。本单的输入前提随之消失。

**本单为什么执行不了**：

| 本单要求 | 现状（实测） |
|---|---|
| 输入 `stations/sumo/*.net.xml` | **从未存在**（全 ref 零命中），且 A 侧 IKLLWY 已同日作废 —— 输入前提落空 |
| **A / B 分工**（A 出 `.net.xml`、B 出 `network.json`，A 不写 B 的、B 不重跑 netconvert） | 随着 A 侧作废，这个分工的**两半同时消失**——本单的存在理由一半就是这条边界 |
| `work/engine/map_ingest.py` | 全仓（含全部本地 / 远程分支）**从未出现** |
| `stations/network.json` 真值 | 仍是**占位样例**（文件自述「占位样例,待 map_ingest.py(Issue #37) 从 OSM + stations/sumo/*.net.xml 产出真值」）；`stations/map_source.json` 的 `sha256` 为 `null`；填表报告台账已把这九件登记为「占位」 |
| 消费方 | 大屏 / 感知层 / 决策层 / 司机端**都不读 `stations/`**；唯一代码级消费方是 `work/engine/`（`network.py`），而**引擎今天没有任何调用方**（前端三页全走 mock），且 `run.py` 自己记着「真链路待后续 issue：需要 SUMO 孪生数据(`work/twin`)与站点包路网」——它同样挂在 SUMO 上 |

**本单执行时无人认领**（未指派、无分支、无 PR），作废无需回收任何半途工作。

**关本单不解决的、需要另立的题**（不在本单范围，如实留痕）：**引擎是否需要一份真值的统一图结构 `stations/network.json`？** 若需要，输入源应改为「**OSM 直接解析**」而不是 `.net.xml`（`work/twin/netpack/` 已能产出 21 段、每段带 `way_ids` 可追溯的几何），落点与写手归属要重新裁定 —— 请**另立一单**，不要把新口径塞回本单。

**⚠️ 另注**：手册 §1.4 的 0-1 / 0-2 / 0-3、§3.0 选型表（「SUMO……一期必装」）、M1-1、§5.0「孪生链路」定义仍按 SUMO 写，需另行裁定并走手册修订表（详见 IKLLWY 的作废说明）。

---

## Issue IKLLWY · [阶段0·0-3A] 站点 OSM → netbuild.py → stations/sumo/*.net.xml（L1 · 站点/踏勘）

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | L1 / 站点与踏勘 |
| 创建 | 2026-10-14T11:21:52+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLLWY |
| 指派 | （无） |

### 正文

> **本单自 GitHub 旧 Issue #36 重建**（2026-10-14 迁到 Gitee 后恢复）：标题、正文与当时的评论原文见仓库 [`docs/历史台账/`](https://gitee.com/ozxowx/hubflow/tree/main/docs/历史台账)，**原文照录、未改口径**。文档里所有 `Issue #36` 引用指的就是本单的前身。

---

## 任务（阶段 0 · **0-3 的 A 侧**）

**站点 OSM 切片 → `netbuild.py` → `stations/sumo/*.net.xml`**：把肇庆东站站前路网落成**可重建的 SUMO 路网**，作为孪生链路的地基。

| 项 | 值 |
|---|---|
| 难度标签 | **L1**（单脚本 + 骨架；跑命令 + 写一个转换脚本） |
| 任务类型 | **S 站点 / 踏勘**（"netconvert 执行"属本系列）（**类型标签；本批不进池子认领**） |
| 区域 | **孪生与路况** |
| 发布者 | 孪生与路况 owner（本批由 `@ouu2006` 代该区域发布） |
| 认领 | **本区域开发执行**（阶段 0 / W0 骨架任务；**不进任务池认领、不占 WIP 配额**） |
| 关联 | `docs/技术方案与实施手册.md` §1.4 **0-3**、§8.3；`docs/hubflow-data/03_技术事实_SUMO与数据同化.md` §1；`work/twin/README.md` |

## 三 prerequisite

| | 内容 |
|---|---|
| **输入样例** | **站点范围 OSM 切片**。站区已核定坐标：**肇庆东站 node `9195330007`，lat 23.2173959 / lon 112.6581162**；邻站鼎湖东 `9195330008`（23.2166847 / 112.654978）。<br>**演示范围口径是"站前约 1.5 km × 1.5 km"（已裁定）**；**建议实际拉取 bbox 比演示范围放大一圈**（≈ `112.645,23.205,112.672,23.230`，约 2.8 km × 2.8 km），**留出"围栏外 → 站前"的上游边界断面**——一期要有 `role: "boundary"` 的断面才谈得上数据同化（M1-10）。**实际拉取范围写进 `map_source.json` 与运行记录，不要在代码里写死坐标。** |
| **输出样例** | `stations/sumo/station.net.xml`（`netconvert` 产出，小文本、可进仓库）+ `work/twin/netbuild.py`（转换脚本）+ 运行记录 |
| **自检脚本** | 见下方"自检脚本"一节，**四条全过才算完**（退出码只是第一条） |

## 先读（别自己摸索）

- [`docs/hubflow-data/03_技术事实_SUMO与数据同化.md`](https://github.com/ouu2006/hubflow/blob/main/docs/hubflow-data/03_%E6%8A%80%E6%9C%AF%E4%BA%8B%E5%AE%9E_SUMO%E4%B8%8E%E6%95%B0%E6%8D%AE%E5%90%8C%E5%8C%96.md) **§1.1 官方推荐 netconvert 命令**、**§1.2 bbox 顺序坑**、**§1.3 已知坑表**
- [`docs/技术方案与实施手册.md`](https://github.com/ouu2006/hubflow/blob/main/docs/%E6%8A%80%E6%9C%AF%E6%96%B9%E6%A1%88%E4%B8%8E%E5%AE%9E%E6%96%BD%E6%89%8B%E5%86%8C.md) **§8.3**（路网主路径与"两边不重叠"的归属）、**§8.4**（换站要改什么）
- [`work/twin/README.md`](https://github.com/ouu2006/hubflow/blob/main/work/twin/README.md)（本模块目录结构与"不许手改生成物"的口径）
- [`docs/条款核实.md`](https://github.com/ouu2006/hubflow/blob/main/docs/%E6%9D%A1%E6%AC%BE%E6%A0%B8%E5%AE%9E.md) **§2.1 第 1~4 行**（拉 OSM 的 ODbL 义务：**对外才触发署名与 share-alike**）

## 步骤

1. **拉切片**：`python "$SUMO_HOME/tools/osmGet.py" --bbox <W,S,E,N> --prefix <NAME>`（**bbox 顺序 = west,south,east,north**，以本机 `--help` 为准；已实测本机 `--help` 就是这个顺序）。
   - ⚠️ **已实测的可用性风险**：公共 Overpass 镜像会间歇返回 **500 / 504**，`osmGet.py` 会自动剔除失败镜像重试；**失败就换时间或换镜像重试，别改成手填数据**。
   - 切片文件落 `work/twin/` 下的输入目录（建议 `work/twin/osm/`），**文件名带拉取日期**。
2. **写 `netbuild.py`**：把 `netconvert` 命令**写进脚本**（不许手点），供一键重建。
   - 起点用开发文档 §1.1 的官方参数集：`--geometry.remove --ramps.guess --junctions.join --tls.guess-signals --tls.discard-simple --tls.join --tls.default-type actuated`，再加 `--remove-edges.by-vclass rail_slow,rail_fast,bicycle,pedestrian`（站区有铁路与步行道混入，见 §1.3）。
   - **脚本要能吃参数**（切片路径 / 输出路径 / 站点名），不要写死肇庆东——换站是改配置，不是改脚本。
3. **产出 `stations/sumo/station.net.xml`**；`netconvert` 的中间产物（`.poly.xml`、日志）**不要当源码提交**（`work/twin/README.md` 明写）。
4. **跑自检并留证**（下一节）。
5. **运行记录**贴在 Issue 评论里：命令、`netconvert` 摘要（Success / 边数 / 车道数）、自检输出、**拉取 bbox 与切片字节数**。

## 自检脚本（**四条，别只看退出码**）

```bash
# ① netconvert 退出码为 0，且日志末行为 Success.
netconvert --osm-files <slice>.osm.xml -o stations/sumo/station.net.xml <官方参数集>

# ② 产物真的存在且不是空壳（阈值给宽，够抓住"没生成"就行）
test -s stations/sumo/station.net.xml

# ③ SUMO 能加载（这是 0-3 的判定原文：".net.xml 生成且能被 SUMO 加载"）
sumo -n stations/sumo/station.net.xml --no-step-log true --begin 0 --end 1

# ④ 可重建：删掉产物重跑脚本，两次产物字节一致（或差异可解释并写进记录）
rm stations/sumo/station.net.xml && python work/twin/netbuild.py --site zhaoqingdong
```

> **为什么第 ④ 条要紧**：文档口径是"**由脚本生成、可重建**"，且判定要求"删除产物能一键重建"。**不重建一次，就不知道脚本里是不是漏了一步手点的操作。**

## 完成判定（**照抄，不新造**）

- `docs/技术方案与实施手册.md` §1.4 **0-3**：「`stations/sumo/*.net.xml` 生成且**能被 SUMO 加载**」
- `docs/分工表_已停用_角色×周任务表.md` **W1 开发A**：「**转换命令写进脚本**，删掉产物能一键重建；路网统计两次运行一致」
- **M1-1 前半**：「站前路网能在 SUMO 里跑起来」
- 纪律：**`sumo/` 归本区域**；`stations/network.json` **不是本任务的产物**（那是 `map_ingest.py` 的，见 B 侧 issue）——**A 不写 `network.json`，B 不重跑 `netconvert`**

## 已实测的现状（省得从零试）

| 项 | 实测结果（2026-10-10） |
|---|---|
| `netconvert` 能否跑通 | ✅ **能**。用 §1.1 官方参数集 + `--remove-edges.by-vclass`，站区切片 → **Success.**，产物 778,539 B |
| 规模 | **314 条边 / 1277 条车道**；`sumo -n` 加载退出码 0 |
| 常见告警（**属正常噪声，别当失败**） | `Not joining junctions` 6 条、`Speed of straight connection ... reduced by ... due to turning radius` 8 条、`Connection ... is only 0.1m short` |
| **属性滞后（要留意）** | OSM 里 **站前大道被标为 `tertiary`**，但 `docs/hubflow-data/01_站点事实_肇庆东站.md` 写它是**双向 8 车道主干路、60 km/h**——这类差异**由 T2 核对表抓**（TC-15），本任务**不改 OSM 属性**，只如实转换 |
| 有名道路只有 7 条 | 吉庆大道 / 新莲路 / 永利大道 / 鼎湖大道（`primary`）、站前大道 / 科创一路 / 科技一路（`tertiary`）；**同一份切片里另有 110 条无名 highway way**（切片共 315 条 way，含非 highway）。**这个"薄"是要在运行记录里写明的现状**，不是转换错误——站前路网的完整性靠 **T2 核对 + netedit 补画**（TC-15） |

## 卡住怎么办

**卡住 30 分钟在 Issue 里 @队长**（别闷头耗）。`netconvert` 报错**截图上报**，**不要自创参数**（系列 S 的原始口径）。

## 交接留痕

认领者在评论里写：**交了哪个文件、对着哪条判定、过没过**。

### 评论（1 条）

**1 · @ozxowx · 2026-10-15T17:42:37+08:00**

## 本单作废（2026-10-15 业主裁定）

业主口径：**大屏地图已改为直接接入地图**——站点包 Z 由 OSM 切片直接解析（`work/twin/netpack/`，纯 Python，不跑 `netconvert`）＋ 大屏矢量底图（MapLibre + OpenFreeMap，WGS-84 直接对齐）。**路网不再经 SUMO 生成**，本单的交付物 `stations/sumo/*.net.xml` 随之失去需求。

**依据（实测）**：

| 检查 | 结果 |
|---|---|
| `stations/sumo/` 在**全部 ref**（本地分支 / 远程分支） | **零命中**——从未产出过 |
| 谁读 `stations/sumo/*.net.xml` | 只有文档与 `stations/*.json` 的注释文字；**唯一的设计消费方是 IKLLX2 的 `map_ingest.py`（全仓从未存在）** |
| 大屏 / 感知层 / 决策层 / 司机端 | 均不读 `stations/`；大屏底图今天来自站点包 Z（PR #14）＋ MapLibre 矢量底图 |
| 现行 SUMO 桥（`work/frontend/tools/twin_preview/server.py`，:8102） | 用的是它**自己的** `station.net.xml`（另一份文件，`build_net.py` 的产物），与本单无关 |

**技术上能不能跑通已实测**（不作为留单理由）：用 `work/twin/netbuild.py` ＋ 仓库内切片 `work/frontend/tools/twin_preview/station.osm` 实跑——`netconvert Success.`、471 edge / 611 lane、`sumo -n` 加载退出码 0、删掉重跑**逐字节一致**。**作废的原因是需求消失，不是做不出来。**

本单此前无人认领（评论区为空、未指派、无分支），作废无需回收任何半途工作。

**⚠️ 本单作废不等于仓库已收口**（另议，不在本单范围）：手册 **§1.4 的 0-1 / 0-2 / 0-3**、**§3.0 选型表**（「交通仿真引擎 SUMO……一期必装，不是"后期事项"」）、**M1-1**（"在 SUMO 中运行"）、**§5.0「孪生链路」定义**（"在 SUMO 里……布置虚拟检测器"）、以及 `stations/README.md`、`work/twin/README.md`、`work/assembly/技术栈.md` 仍按「SUMO 一期必装」写——**需要另行裁定并走手册修订表**。特别提示：「孪生链路」这个词还挂在页面常驻角标上（`shared/nav.ts` 的「演示数据(模拟)· 双数据源(视频链路 + 孪生链路)」），SUMO 退场后这个词需要一个新定义。

---

## Issue IKLLT8 · [W1前置·已关闭] PR #79 兜底审确认的 6 条 Sourcery 待办：孪生骨架输入校验与诊断补齐（对应 GitHub 旧 #83）

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | （无） |
| 创建 | 2026-10-14T11:16:03+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLLT8 |
| 指派 | （无） |

### 正文

> **本单自 GitHub 旧 Issue #83 重建**，但**该单在 GitHub 侧早已关闭**（6 条待办已由 PR #84 修完并合入 main `25c1653`，2026-10-13 同日关闭）。

本单**仅为编号与原文可追溯**而建，**无任何遗留工作**。为保持与 GitHub 侧状态一致，本单**同时置为已关闭**。读到请忽略。

原文（正文 + 历史评论）见仓库 [`docs/历史台账/issue-归档.md`](https://gitee.com/ozxowx/hubflow/blob/main/docs/历史台账/issue-归档.md) 的 Issue #83 一节。

### 评论（0 条）

（无评论）

---

## Issue IKLIG4 · [文档与合规] 迁移遗留四项收口：成员重建 / ci 路线裁定 / main 保护分支两层配置 / 历史 Issue 取不回的口径

| 项 | 值 |
|---|---|
| 状态 | closed |
| 标签 | L1 / 文档与合规 |
| 创建 | 2026-10-14T08:00:33+08:00 |
| 链接 | https://gitee.com/ozxowx/hubflow/issues/IKLIG4 |
| 指派 | ozxowx |

### 正文

## 现状

**Gitee 侧仓库（`ozxowx/hubflow`）还没有任何标签**——`labels` 参数传的是标签**名字**，而仓库标签库里一个都没有，所以这条限制**当前无法直接落地**。先把标签库建起来（`管理 → 标签管理`，或在下方评论区贴一份清单让队长批量建）。

## 建议先建的标签（沿用 GitHub 侧的用法，见 `docs/协作规范.md` 第 5 节）

**难度标签**（发布时**必打一个**）：

| 标签 | 含义 |
|---|---|
| `L0` | 小事：文档错字、字段改名、加一行说明这类 |
| `L1` | 常规：能独立完成的模块内改动 |
| `L2` | 大件：**暂不发布**（跨模块 / 契约级 / 需要拆） |

**系列标签**（任务池四个系列，**打一个**）：

| 标签 | 含义 |
|---|---|
| `V` | 视频线（抽帧 / 标注 / 标定） |
| `S` | 站点踏勘（现场数据、点位、路段核对） |
| `P` | 参数调研（限速 / 容量 / 天气这类外部参数） |
| `Q` | 独立验收（**开发不得认领**，回避规则） |

**区域标签**（打一个，与手册第 2 章的七个区域取值对应）：`孪生与路况` / `决策与定位+判级` / `接口与双端` / `站点与踏勘` / `参数与调研` / `独立验收` / `文档与合规`

> ⚠️ **标签名不要带特殊字符**（Gitee 要求 2~20 字、非特殊字符）——上面这些名字都过。`决策与定位+判级` 里的 `+` 如果建的时候被拒，改成 `决策与判级`。

## 已有的两条作为例子

- 本单（迁移遗留收口）：`文档与合规` + `L1`
- 待建的其他单：按上面三档各打一个即可

**建完之后**：`仓库设置清单.md` 第 1 节的"还**可以**再补的"一节不用改——标签是任务板用法，不是保护分支配置。这条备注会同时贴在 Issue 评论里，队长照着建就行。

### 评论（0 条）

（无评论）
