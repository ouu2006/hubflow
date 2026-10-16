# 历史台账：Gitee 侧 PR（2026-10-14 起）

> **这不是权威文档，是存档。** 权威顺序仍是：手册 / 总纲 / 分工表 / 协作规范（见根 `README.md`）。
> 本文件只回答一件事：**Gitee 时代的 PR 原文是什么**。GitHub 时代见 [`pr-归档.md`](pr-归档.md)。
> **原文照录，未改口径**。PR 正文来源见每节的「来源」行（平台接口不返回 body，正文取自本机会话存档）。
> 本机绝对路径按本目录既有归档口径写作「（本机路径已隐去）」；PR 号一律写作 `!NN`。
> 取数时间：2026-10-16。

## 取回率

- PR：7/26 条有正文（其余本机无记录）
- 评论：共 12 条

## 索引

| PR | 标题 | 状态 | 源分支 | 目标分支 | 创建 | 合并 | 正文 | 评论 |
|---|---|---|---|---|---|---|---|---|
| !26 | 大屏：底图只出底色层 —— dev/preview 加同源直通 + 瓦片真就绪才算 ok | merged | task/basemap-dev-proxy | main | 2026-10-16 | 2026-10-16 | 本机无记录 | 1 |
| !25 | [demo_y] sumo-gui 截图通道修正：非空白判据改几何量 + 技术栈台账口径同步（!9 遗留提交） | merged | fix/demo-y-capture-blank-criterion | main | 2026-10-16 | 2026-10-16 | `create_pull` | 0 |
| !24 | [#88] 鸿蒙 App 拆分 A：真实路网导航版 + 提交前审查修 19 处 + 13 张实跑举证（补 PR：!6 之后的 4 个提交） | merged | task/88-harmony-app-skeleton | main | 2026-10-16 | 2026-10-16 | `update_pull`（后续补充版） | 0 |
| !23 | IKM5T1 大屏地图合并成单渲染器：删示例路网、底图与路网解耦（底图拉不出来也照画路网） | merged | task/IKM5T1-single-map-renderer | main | 2026-10-16 | 2026-10-16 | `update_pull`（后续补充版） | 0 |
| !22 | feat(packs): 站点包只剩 Z：删除 A 包，单包时收起切换器（IKM4XX） | merged | task/IKM4KP-station-pack-z-primary | main | 2026-10-16 | 2026-10-16 | 本机无记录 | 0 |
| !21 | [IKM4XX] 站点包只剩 Z：删除 A 包，单包时收起切换器（叠在 !20 之上）（L1） | merged | task/IKM4XX-station-pack-z-only | task/IKM4KP-station-pack-z-primary | 2026-10-16 | 2026-10-16 | `create_pull` | 0 |
| !20 | [IKM4KP] 站点包以 Z 为主：默认包改 Z、删除 B / Y 两个包（含 env / dev 脚本 / README 同步）（L1） | merged | task/IKM4KP-station-pack-z-primary | main | 2026-10-16 | 2026-10-16 | `create_pull` | 1 |
| !19 | web端监控大屏的底图采用OpenFreeMap+osm+描绘线路网组成的路段监控画面 | merged | task/dashboard-openfreemap-basemap | main | 2026-10-15 | 2026-10-15 | `create_pull` | 1 |
| !18 | fix(twin_preview): 启发式选段改按真实道路链——修掉「拿路口接头当路段」与「截断长路」 | merged | task/twin-preview-roadchain | main | 2026-10-15 | 2026-10-15 | `create_pull` | 1 |
| !17 | 文档：总纲新增 D10「一期前 · 前端完善」阶段（前端先行、不含后端）——一期范围不变 | merged | docs/frontend-phase-d10 | main | 2026-10-15 | 2026-10-15 | 本机无记录 | 1 |
| !16 | IKLLXG 大屏右栏关联告警判级取路段快照：四处收口唯一实现 + 清死代码 | merged | task/IKLLXG-alert-level | main | 2026-10-15 | 2026-10-15 | 本机无记录 | 0 |
| !15 | IKLLX4 表格模板实体 T1~T8 下发 + 共享盘口径收窄为「只放表格与记录」 | merged | task/43-table-templates | main | 2026-10-15 | 2026-10-15 | 本机无记录 | 0 |
| !14 | 孪生：肇庆东站真路网入站点包 Z（OSM 21 段 + 大屏摄像头布点，只摄像头段上色）（IKLX5Y） | merged | task/IKLX5Y-station-z-roadmap | main | 2026-10-15 | 2026-10-15 | 本机无记录 | 0 |
| !13 | IKLX9B 司机端 App 前端先用单文件 HTML 顶替：站点 Z 上色 + 保留全览 + 不做生成路线 | merged | task/IKLX9B-app-html-nav | main | 2026-10-15 | 2026-10-15 | 本机无记录 | 0 |
| !12 | feat: 顶栏线路图切换器——选包即换路网（A/B/Y 三站） | merged | task/topbar-network-switcher | main | 2026-10-14 | 2026-10-14 | 本机无记录 | 0 |
| !11 | 接口：twin_preview 桥接服务参数化——换网不再靠猜路段（#IKLOJ6 第 1 条） | merged | task/bridge-swap-net | main | 2026-10-14 | 2026-10-14 | 本机无记录 | 0 |
| !10 | feat: Issue IKLR30 Y型交叉口V0演示（几何→数据→大屏全链路） | merged | task/IKLR30-y-junction-dashboard | main | 2026-10-14 | 2026-10-14 | 本机无记录 | 0 |
| !9 | 孪生：Y 型示意路网 + SUMO 场景全链路（演示底座，非 #IKLOB6 交付） | merged | task/demo-y-sumo-chain | main | 2026-10-14 | 2026-10-14 | 本机无记录 | 1 |
| !8 | 决策：--sample 输出口径三处修正 + 登记口径两处（Issue #IKLLXT / 旧 #94） | merged | task/94-pr82-backlog | main | 2026-10-14 | 2026-10-14 | 本机无记录 | 0 |
| !7 | !81 大屏三栏可横向拖拽：/dashboard 主体三栏改 ElSplitter | merged | task/81-dashboard-col-resize | main | 2026-10-14 | 2026-10-14 | 本机无记录 | 0 |
| !6 | [接口与双端] 鸿蒙 App 拆分 A：工程骨架 + P0 四页 UI（数据用工程内 fixture，不联网） | merged | task/88-harmony-app-skeleton | main | 2026-10-14 | 2026-10-14 | 本机无记录 | 3 |
| !5 | 文档：历史台账状态校正——早期 8 条「每条线 W1」单按缺席证据判为 CLOSED | merged | docs/ledger-state-fix | main | 2026-10-14 | 2026-10-14 | 本机无记录 | 1 |
| !4 | 文档：重建 GitHub 侧历史 Issue / PR 台账（39 条 Issue + 56 条 PR 的正文与评论） | merged | docs/history-ledger | main | 2026-10-14 | 2026-10-14 | 本机无记录 | 1 |
| !3 | 设置清单补记：成员清理 / 保护规则实测值 / 历史重写全过程（含临时摘保护的操作记录） | merged | docs/settings-after-rewrite | main | 2026-10-14 | 2026-10-14 | 本机无记录 | 0 |
| !2 | 去掉流水线（ci）+ 切断外部仓库依赖：门禁改本地跑，仓库自包含 | merged | chore/no-ci-no-upstream | main | 2026-10-14 | 2026-10-14 | 本机无记录 | 1 |
| !1 | 仓库迁到 Gitee：历史搬迁 + 模板/流水线配置改写 + 设置清单重写（迁移落地单） | merged | chore/migrate-to-gitee | main | 2026-10-14 | 2026-10-14 | 本机无记录 | 0 |

---

## PR !26 · 大屏：底图只出底色层 —— dev/preview 加同源直通 + 瓦片真就绪才算 ok

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/basemap-dev-proxy` → `main` |
| 创建 / 合并 | 2026-10-16T22:05:22+08:00 / 2026-10-16T22:08:06+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/26 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（1 条）

**1 · @ozxowx · 2026-10-16T22:09:32+08:00**

**合并留痕（补在合并之后，如实写）**：本 PR 由**提交者本人**（`嚄u`）合并，**未走兜底审** —— 依据是业主 **2026-10-16** 明确指示「自己合」。三道关实际执行：① 自查 + AI 预审 + `doc_gate.py` **已做**（意见原文在「审查记录」栏）；② 全新上下文 4 问独立审查 **已做**（原文在「审查记录」栏，唯一发现已修在 `5fa8642`）；③ 兜底审 **未做**（业主授权跳过）。⚠️ 这不是先例：`docs/协作规范.md` 第 4 节「不要自己点合并 / 作者不许合并自己的 PR」仍然有效。合并后核对：`main` = `1ccbf68`，`doc_gate.py` 七组全过 + `frontend_gate.py` 11/11 全绿；分支本地与远端均已删。

---

## PR !25 · [demo_y] sumo-gui 截图通道修正：非空白判据改几何量 + 技术栈台账口径同步（!9 遗留提交）

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `fix/demo-y-capture-blank-criterion` → `main` |
| 创建 / 合并 | 2026-10-16T21:24:30+08:00 / 2026-10-16T21:39:42+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/25 |
| 正文来源 | 本机会话存档 `mcp__gitee__create_pull` |

### 正文

## 这是什么

`task/demo-y-sumo-chain` 分支上 **PR !9 之后还留了 1 个提交没合**。本 PR 把它（+ 台账口径同步）补上。

!9 于 2026-10-14 19:39 合入了前 2 个提交（head `0593c271`）；之后作者在 21:25 又推了 `10785d3`，**一直没开 PR**。

---

## 为什么值得合：`main` 上那份脚本对**它自己的目标输入**必然误报失败

| | 判据 |
|---|---|
| `main` 的 `capture_screen.py` | `MIN_COLORS = 30`，注释写「颜色种数要够多……真实路网画面有几百种」 |
| 实测 | `work/twin/demo_y/` 的示意路网只有 **4 节点 / 6 边 → 真画面只有 5 种颜色** |
| 后果 | `5 < 30` → 打印「❌ 只有 5 种颜色（门槛 30）—— 这是**空白/纯色图**，不认」并**非 0 退出** |

而这个脚本**就是为 Y 网写的**（就在 `demo_y/` 目录下）。所以任何人现在跑它截 Y 网的真画面，都会得到一个「截图通道没跑通」的**假结论**。

更要紧的是 `技术栈.md` 的现行口径：

> 截图前要 `gui.setBoundary()` 把视图对准路网，否则截出来是空白画布（**实测只 2~4 种颜色**）

**空白 2~4 色 vs 真画面 5 色 —— 只差 1~3 色。** 任何「颜色种数 ≥ N」的阈值在这张网上都是脆的；几何判据是严格更好的做法。

---

## 本 PR 内容（3 个文件）

### 1. `work/twin/demo_y/capture_screen.py`（原提交 `10785d3`，原作者保留）

- **非空白判据由「数颜色」改为「几何」**：非白像素占比 + 非白像素包围盒跨度（实测真画面 1.8% / 82%×91%）
- 补 4 条实测坑：
  - macOS 上 `sumo-gui` 链 `libFOX`+`libX11`，是 X11 程序 → 需 XQuartz（实测**不用注销重登**）
  - **必须给 `sumo-gui` 加 `--start`** —— 否则 GUI 等你点界面上的"播放"，TraCI 端口在 LISTEN 却不回话，握手超时 40 s
  - `FONTCONFIG_PATH` 要指到 `/opt/X11/etc/X11/fontconfig`
  - **`traci.close()` 永不返回**（GUI 进程不退）→ 用 `os._exit(0)` 收尾
- 文档串同步改写

### 2. `work/twin/demo_y/README.md`（同提交）

- 「**本机跑不通**」→ 装好 XQuartz 后的完整用法
- 新增一条：**非空白判据用「几何」不用「数颜色」**

### 3. `work/assembly/技术栈.md`（本 PR 新增）

- 第 1.3 节「四个坑」第 2 条补：颜色种数**随路网规模走**，示意路网真画面 5 色 / 空白 2~4 色，阈值会误判 → 指向几何判据
- 第 1.5 节 9 号项：给「**458 种颜色**」补注 —— 那是**该示例网的数字，不是通用阈值**

---

## 如实说明（供评审裁量）

- **XQuartz / `FONTCONFIG_PATH` 是 macOS 专属**，而 `技术栈.md` 记录的 SUMO 环境是 **Windows**（`%SUMO_HOME%` / `sumo.exe` / 便携包）。这部分**当历史备案看**，不是当前环境的必需步骤。
- **跨平台有效**的是：`--start`、`os._exit`、以及**几何判据** —— 后者在 Windows 上同样能复现那个误报。
- `capture_screen.py` 自称服务「单 3「SUMO 真实画面接大屏」」，而该方向已按**手册风险表第 20 条**否决（**不嵌 sumo-gui 画面**，见 `work/frontend/README.md` 与 `twin_preview/README.md`）。所以这个脚本现在的用途是**工具链可行性留证**，不是产品功能。

## 验证

```
python scripts/doc_gate.py  → 7/7 全绿
```

`capture_screen.py` 需要 SUMO + GUI 窗口，本机未实跑；判据改动的依据是原提交的实测记录（真画面 1.8% / 82%×91%，空白 2~4 色）。

## 关联

- 前置 PR **!9**（`孪生：Y 型示意路网 + SUMO 场景全链路（演示底座）`）—— 本 PR 是它遗留的第 3 个提交
- **IKLR30**（`自绘 Y 型路网当路线图`，已 `closed`）
- **合入后 `task/demo-y-sumo-chain` 分支即可删除**（其内容全部落地）

### 评论（0 条）

无评论（平台 `list_comments` 返回空数组）。

---

## PR !24 · [#88] 鸿蒙 App 拆分 A：真实路网导航版 + 提交前审查修 19 处 + 13 张实跑举证（补 PR：!6 之后的 4 个提交）

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/88-harmony-app-skeleton` → `main` |
| 创建 / 合并 | 2026-10-16T20:30:12+08:00 / 2026-10-16T21:10:57+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/24 |
| 正文来源 | 本机会话存档 `mcp__gitee__update_pull`（后续补充版；同一 PR 另有 `create_pull` 版正文） |

### 正文

> 正文来自 `update_pull`（后续补充版）。

## 这是什么

`task/88-harmony-app-skeleton` 分支上 **PR !6 之后又推了 4 个提交，一直没开 PR** —— 也就是说 Issue #88（鸿蒙 App 拆分 A）**真正的交付物至今没进 `main`**。本 PR 把这 4 个提交补上来。

!6 只合了早期的「工程骨架 + 四页 fixture 版」（head `29d95696`）；之后 xixiu-dev 在 10-14 ~ 10-15 继续在同一分支上做完了「真实路网导航版 + 评审自查」。

| 提交 | 内容 |
|---|---|
| `7097696` | review-fix：@Observed / degraded 分支 / Colors.ets 抽取 / 缓存演示车 / 对齐 |
| `3a7ce0b` | 修掉 Colors.ets 重构带来的 12 个编译错误 + 清理 9 个未使用导入 |
| `e70ffeb` | **真实路网导航版** + 提交前全量审查修 19 处问题 |
| `03cd131` | 评审资料 + 实跑举证截图 + README 第十四节 |

---

## ✅ 2026-10-16 更新：6 处冲突已解决

`main` 已并入本分支，合并提交 **`6b0e1ce`**（双亲 `03cd131` + `9f5fbdb`）。现在 `main` 是本分支的祖先，**可直接合并，无冲突**。

**冲突成因**：`main` 侧这 6 个文件的**唯一一次改动**来自 `29d9569`（队长那版「把硬编码色值抽成 `Colors.ets`」的 review-fix），而那版**编译不过**（`RecommendPage` 把 `@State` 写在模块顶层、多处漏 import）。本分支的 `3a7ce0b` 正是对同一处的就地修正，`e70ffeb` 又在其上做了真实路网导航改造 —— 故 `main` 侧为中间坏态，**取本分支版本即超集**。

> ⚠️ **更正**：初版正文里建议的 `git checkout --theirs` **写反了**。合并方向是「`main` → 本分支」，所以分支版本是 **`--ours`**、`main` 是 `--theirs`。实际执行用的是 `--ours`。

逐条核对：

| 文件 | 依据 |
|---|---|
| `components/Common.ets` · `pages/HistoryPage.ets` | 两边只差 import 一行；本分支少导入的 `TEXT_WHITE` / `ACCENT_EMERGENCY` / `BG_GRAY_LIGHTER` 经 grep 确认**使用次数为 0** |
| `pages/DropoffPage.ets` · `pages/DeparturePage.ets` | `main` 的 `else if (degraded)` 内联分支 → 本分支改为贴顶 `StateTopBar` + `DegradedBanner`（有意重设计：应急提示须第一眼可见） |
| `pages/RecommendPage.ets` | `main` 的 `@State demoVehicleCache` → 本分支改为模块级常量 `DEMO_VEHICLE_CACHE`（ArkTS 不允许 `@State` 修饰 struct 外变量，即 `3a7ce0b` 修的编译错误） |

**合并后验证：**

```
python scripts/doc_gate.py        → 7/7 全绿
python scripts/frontend_gate.py   → 11/11 全绿（扫描 23 个源文件）
冲突标记残留                       → 无
相对 main 的改动                   → 37 个文件，全部在 harmony/ + frontend_gate.py + README
harmony 侧丢失的 main 文件          → 0
```

**顺带修掉一处阻断验证的缺陷**（超出那 6 个冲突，供评审裁量）：`scripts/frontend_gate.py` 原为硬编码绝对路径 `ROOT = r"（本机路径已隐去）"`，换机器即 `FileNotFoundError`（会「扫描 0 个源文件」后崩溃，这正是它声称 11/11 却无法复现的原因）。已改为按 `__file__` 相对仓库定位。

---

## 交付内容

### 1. 真实路网导航（替换 fixture 示意版）

- `common/RealNet.ets`（534 行）：真实路网落盘（RDP 抽稀）
- `common/RoutePlan.ets`（535 行）：**唯一同源派生层** —— 排序 / 路段 / 几何 / 转向只此一处
- `common/SelfDrawRenderer.ets`（705 行）：自绘渲染后端，走 `DrawingRenderingContext.invalidate()`
- `common/MapPort.ets` / `MapTypes.ets` / `ManeuverMeta.ets`
- 三条方案由 Dijkstra k 最短路在真实路网上算出：**R1 / R2 / R3 = 5044 / 5059 / 5120 m**，与契约 `reason` 一一对应

### 2. 组件化

`NavBar.ets`(829) · `RoadNetMap.ets`(411) · `RouteOptionRow.ets`(353) · `StateTopBar.ets`(123) · `DegradedBanner.ets`(45) · `Common.ets` 改造

### 3. 提交前全量审查修掉的 3 处硬伤

1. **数据不可用时地图画成蓝色**（`levelColor` 对 `level<1` 返回导航蓝 `#0D5FB4`）—— 与图例「数据不可用」自相矛盾且撞 TC-11 → 改走灰色
2. **应急态下落客 / 离站页地图仍在画推荐路线** —— 与「停止引导」自相矛盾 → 新增 `RoadNetMap.stopGuidance` 闸门，三页统一生效
3. **离站转向序列与地图几何反向** —— 反转顺序时除里程外还须**对调首尾 `type`**，否则图标与地图 pin/start 一起装反

### 4. 其余修复（共 19 处，逐条见评审资料）

离站地图画错备选路线 / 离站文案全错 / 「X 米后」实现与注释不符且巡航中会算出 0 米 / 应急态下点已选卡片仍会跳导航 / 退后台后 40ms 巡航定时器不停 / 离站角标仍写死 P-5 / ForEach 键漏 `routeLocked` / 降级态直读 fixture 绕开同源层 / 渲染后端每帧 new 且从不 dispose …

### 5. 代码卫生

- 删除 `YRouteMap.ets` 整份（413 行里约 380 行零引用）
- 慢速系数 `1.0/0.6/0.35/0.2` 两处逐字重复 → 提取 `LevelMeta.levelSpeedFactorOf()`
- 清理约 400 行死代码；两处 `if (true)` 恒真残留去壳

### 6. 门禁与举证

- **新增 `scripts/frontend_gate.py`（391 行 / 11 项）** —— **11/11 全绿**
- `python scripts/doc_gate.py` **7/7**
- `BUILD SUCCESSFUL`，零 error 零 warning
- `work/frontend/harmony/.evidence/` **13 张模拟器实跑举证截图**（本轮新增 4 张：`06b` / `09` / `10` / `11`），逐张标注对应判定项
- 评审入口：`work/frontend/harmony/评审资料-Issue88.md`

## 完成判定对照（Issue #88）

见 `评审资料-Issue88.md` 第一节：C-3 四页 / TC-11 不可用显灰 / TC-12 `departure_route` 必现 / TC-05 拒绝授权降级 / M1-7 角标 / 手册 §11.1(3) 应急态 / §11.3 三重编码，逐条对照。

---

## 影响面（供评审确认）

**只动鸿蒙司机端**：全部改动落在 `work/frontend/harmony/**` + `scripts/frontend_gate.py` + `work/frontend/README.md`。

- **不碰 web 端**：`work/frontend/ui-vue/**` 零改动，与大屏地图（`MapLibreViewer.vue` / OpenFreeMap 单渲染器）**无交叉、无冲突**。两端地图是**同一业务命题的两套独立实现**（web 用 MapLibre + 公网瓦片；鸿蒙受条款限制用自绘 Canvas，见 `MapTypes.ets`）
- **不碰后端**：`work/engine/`、`work/twin/`、`work/perception/`、`work/assembly/` 零改动
- **不碰契约**：不加字段、不改字段名

## 口径

- 全部数值来自工程内 fixture（虚拟数据），`is_simulated` 恒为 `true`
- 页面不出现「实测 / 实时 / 现场」（唯一例外是手册 §11.1(3) 固定措辞「请服从现场指挥」）
- 不声称已接入真实定位
- 未在真机上验证，仅模拟器（Pura 90 / API 24）；W4 判定以 DevEco 预览器或模拟器跑起来为准

## 关联

- **Issue #88**（鸿蒙 App 拆分 A，GitHub 旧单；Gitee 侧已并入总单 **IKLLX9**）
- 前置 PR **!6**（工程骨架 + 四页 fixture 版）
- 兄弟单 **#89**（数据接驳 + 双端同源举证，尚未落地）

### 评论（0 条）

无评论（平台 `list_comments` 返回空数组）。

---

## PR !23 · IKM5T1 大屏地图合并成单渲染器：删示例路网、底图与路网解耦（底图拉不出来也照画路网）

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/IKM5T1-single-map-renderer` → `main` |
| 创建 / 合并 | 2026-10-16T11:21:11+08:00 / 2026-10-16T12:46:57+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/23 |
| 正文来源 | 本机会话存档 `mcp__gitee__update_pull`（后续补充版；同一 PR 另有 `create_pull` 版正文） |

### 正文

> 正文来自 `update_pull`（后续补充版）。

## 改了什么

大屏中栏地图**合并成一个渲染器**：删掉「示例路网 / 矢量地图」两个模式标签与自绘视图 `components/NetMap.vue`，只留 MapLibre（矢量底图 + 描出的路网）；把自绘视图的四件事（车辆动点 / 悬停浮牌 / 推荐路线 / 图例 + 水印）搬进 `components/MapLibreViewer.vue`；**底图与路网解耦** —— 地图先用本地兜底样式建起来、路网立刻画，OpenFreeMap 样式随后异步合入，**拉不到只丢底图、路网照画**。

**追加（业主 2026-10-16）**：顶栏新增「**设置**」，里面放一个**底图开关** —— 开＝矢量底图 + 描出的路网；关＝**只画路网**（＝原「示例路网」观感），**一个底图请求都不发**。同时给底图拉不到的情况补上「**重试**」按钮与 2s / 6s / 12s **退避自动重试**。

关联：Issue **IKM5T1**。

## 填表报告（**动了 `stations/*.json` 或表格转换脚本就必填；都没动就勾下面的"本次不涉及"**）

- 台账行（表 / 表版本 / 产物 / 依据 / 结果 / 日期）：不适用
- 重跑证据（命令 + 读了多少行 → 生成多少条 + 产物 diff 位置）：不适用

- [ ] 已按 `docs/填表报告.md` 第五节在台账末尾**加了一行**
- [ ] 表格是**唯一入口**
- [x] **本次不涉及**填表报告（没动 `stations/*.json`、也没动表格转换脚本）

## 实现方式

- **用了什么方式**：① 地图以**本地兜底样式** `{ version: 8, sources: {}, layers: [] }` 建图，路网 source/layer 在 `load` 里**立刻**加并 `fitBounds`；② 随后 `fetch` OpenFreeMap 样式，成功后与**本组件自己的图层规格**合成一份 style 再 `map.setStyle(merged, { diff: false })`，失败就只用兜底那份；③ 底图开关（`src/shared/settings.ts`，落 `localStorage` 键 `hubflow.settings.basemap`）关掉时：**abort 在途请求 + 换回兜底样式**，一个底图请求都不发；④ 拉不到时角标给原因 + 「重试」，并按 2s / 6s / 12s 退避自动重试（最多三次）；⑤ 悬停浮牌 / 车辆 / 图例 / 水印走 DOM 覆盖层，不进图层栈；⑥ 原有 `setWorkerUrl`（生产构建 worker 那个坑）与 MapLibre 署名控件**保留不动**。
- **为什么不用默认推荐**：原实现是 `style: STYLE_URL` + `map.on('load')` 里加路网层 —— 公网样式拉不到时 `load` 不触发，**连路网层都加不上，整块空白**（只有 12 s 后一句提示盖在上面）。业主 2026-10-16 口径要求"底图拉不出来时路网照样刷新出来"+"底图这一层要能开关"，所以必须把两者的加载链拆开，并把底图做成可选层。
- **契约与判定不变的证明**：未新增 / 未改名字段；组件仍只读 `segment_id` / `name` / `kind` / `coords` 与 `SEGMENT_BASES`（IKM4B4 的交接条件：渲染侧只读）；`colorPolicy: 'camera-covered'` 的灰轮廓口径、四级 / ci 配色、品牌蓝语义照旧；OSM 署名义务（E-11 / E-13）照旧，且**与底图开关无关**（见下）。

## 怎么验证的

- [x] 本地门禁过了：`python scripts/doc_gate.py` —— **七组全过**
- [x] **第 7 组（填表报告台账）是 `[通过]`**
- [x] 我这个模块能单独跑通：`npm run build`（`vue-tsc -b && vite build`）**exit 0**；产物 `dist/assets/maplibre-gl-worker-*.mjs 508.31 kB` / `index-*.css 493.51 kB` / `index-*.js 2,194.25 kB`
- [x] 输出 JSON 字段名对照契约：本次未动任何 JSON 产物
- [x] 产物存在性断言：`dist/` 三个产物非空、时间戳为本次构建
- [ ] 同一输入连续跑 3 次 —— **不适用**（纯前端渲染改动，无判级、无随机）
- [ ] CI 已跑完且全绿 —— **本仓库不挂流水线**（门禁本地跑，见 `docs/仓库设置清单.md` 第 3 节）

**浏览器实测**（Tabbit / Chromium，整窗 2544×1267，站点包 Z `npm run dev` → `http://127.0.0.1:5173/#/dashboard`）：

1. **正常态**：模式标签 **0 个**、地图 canvas **1 个**、摄像头图钉 **6 个**、图例（四级编码 + D1/D2/D3 + 推荐路线 + 摄像头两行 + "未挂摄像头的路段只画灰轮廓"）在、水印「OSM 真路网 · 几何为真值 · 指标为演示数据（模拟）」在、署名「地图数据 © OpenStreetMap 贡献者,依 ODbL 许可」在且 `href = https://www.openstreetmap.org/copyright`；OpenFreeMap 资源 **6** 条。
2. **交互**：悬停路段出浮牌「`SZ-05 缓行 · 摄像头 1 路 · x 0.61(仅孪生链路)`」；悬停图钉出浮牌「`C-01 吉庆大道·西进口 / SZ-01 · 未接入视频源 · 本期留空 · 点击进感知层`」。
3. **底图失败（核心判定）**：把页面里 openfreemap 的 `fetch` 打回失败后刷新 —— 角标「**底图不可用（拉取失败）· 路网照画**」出现，OpenFreeMap 资源 **0 条**，而 **canvas / 6 个图钉 / 图例 / 水印 / 署名全在**，**无白屏、无整屏遮罩**。
4. **底图开关**：设置面板（`aria-checked` 正确）→ 关掉：角标「**底图已关闭（顶栏「设置」里可开）· 只画路网**」、`mapTag`/注脚同步改写、`localStorage="0"`、6 图钉仍在；**关掉后刷新 OpenFreeMap 资源 0 条**；再打开：角标消失、资源 6 条、`localStorage="1"`。
5. **失败恢复**：失败态给「重试」；仍失败时点击保持失败态（按钮盒 `{x:527,y:210,w:40}` 前后一致）；放行后再点 → 角标消失、资源 6 条 → 底图恢复。
6. **署名与开关无关（实测）**：关态下 `.attribution` 仍在图上且可见（box `337,230`、`href` 正确）—— 那是**路网**的 OSM 署名；跟着底图消失的只有 MapLibre 自带署名控件（关态只剩「MapLibre」，开态是「MapLibre | OpenFreeMap © OpenMapTiles Data from OpenStreetMap」）。
7. **角标与控制两两不重叠**（bounding box 判定，7 组全 `false`）：路网署名 × 底图署名控件 / 比例尺 / 图例 / 水印 / 状态角标；图例 × 比例尺；状态角标 × 水印。

截图落在仓库外：`（本机路径已隐去）`。

## 审查记录（**必填**）

### （1）AI 预审（作者自查）

- 预审意见原文：按 `docs/开发规范.md` 第 11 节四条自查 —— ① 契约字段未动（`api/`、`assembly/` 未碰）；② 目录只在 `work/frontend/**`；③ 无密钥 / 无大文件（截图落仓库外）；④ 口径未出现「实测 / 实时 / 现场」，`is_simulated` 语义照旧。

### （2）快速独立审查（**全新上下文，目标 ≤ 5 分钟**）

**第 1 轮**（改动范围 `git diff d22a8eb..HEAD`）

- 审查者（全新上下文，写清工具 / 模型）：**子代理（全新上下文，只给"改动范围 + 4 个问题"）**
- 我只提供了：改动范围 + 那 4 个问题（未提供实现思路、可疑点、既有结论）
- **4 问结论**（≤ 10 行）：① 一致、无无关夹带；② 未碰契约字段与别人目录（`work/frontend/README.md` 属公共文档，改动限于本单口径与历史记录）；③ 无密钥 / 无二进制大文件，口径上一条需自证；④ 两条可执行（署名与右下角控件重叠风险、`route-segments` 恒空）。
- **审查者原始结论原文**：

```
① 一致：7 文件全在本单范围内（MapLibreViewer 重写 / NetMap 删除 / DashboardView 去模式标签
   + README·AppShell·main·demoNetwork 措辞同步），无无关夹带。
② 未碰契约字段（api 契约、assembly 清单未动）；demoNetwork.ts:71、main.ts:20、AppShell.vue:56 仅注释；
   只有 work/frontend/README.md 属公共文档，改动限于本单口径。
③ 无真实密钥、无二进制/大文件。口径一条：README.md:117 把"底图为示例路网(非实测)"改写成
   "站点包 Z 几何是 OSM 真值 / 底图为 OSM 矢量底图"，diff 内无法自证。
④ MapLibreViewer.vue:753（.attribution bottom:24px）与同次挪到 bottom-right 的 ScaleControl
   及自带署名控件同角，重叠风险、与文件头"不得遮挡控件"冲突，需实机确认。
④ DashboardView.vue:831 `:route-segments="[]"` 恒空，而 MapLibreViewer.vue:599 新增的 routeSegments
   watch 与图例"推荐路线(当前)"都指着它 → 该功能在新组件里恒不显示（内联 `[]` 还会每次渲染触发该 watch）。
其余（兜底样式建图、异步合入、失败只丢底图、浮牌/车辆/图钉搬迁）逻辑自洽，未发现会挡住下游的字段不一致。
```

| # | 发现 | 处置（已修 / 不改 + 理由，附文件与行号） |
|---|---|---|
| 1 | `.attribution` 与右下角 ScaleControl / 自带署名控件同角，重叠风险 | **成立，已修**：署名挪到**左上角**（`top: 34px; left: 12px`）；改后实测 7 组 bounding box 两两不重叠（原来 `attribOverlapsCtrl = true`，重叠 10 px） |
| 2 | `:route-segments="[]"` 恒空 + 内联数组每次渲染触发 watch | **watch 部分成立，已修**：改为按**内容**（`join` 后的键）监听；**"恒不显示"是改动前就有的现状**（自绘视图收的也是 `[]`），本单只保留能力、不改父组件行为，已在「卡点」记为待接线 |
| 3 | README:117 的"几何是 OSM 真值"是断言，diff 内无法自证 | **不改**：自证在 diff 之外 —— `stationZ.ts` 的 `source.osm = true` 与 `stationZ.network.ts` 由 `work/twin/netpack/build_station_pack.py` 从**未改动的** OSM 切片生成；本单未碰这些文件 |

**第 2 轮**（改动范围 `git diff 99adc14..HEAD`，即底图开关 + 重试那次增量）

- 审查者：**另一个子代理（全新上下文，只给"改动范围 + 4 个问题"）**
- **4 问结论**：① 一致、5 文件全在「底图开关 + 重试/退避」范围内；② 未碰契约字段（`basemap` 为组件私有 ref，仅加 `'off'`，未导出）、未碰 API/mock/nav/theme；③ 无密钥 / 无大文件；④ 未发现挡下游问题（`disposed` + `!basemapEnabled` 双保险、`retryTimer` 三处清理、无悬空定时器、`restoreSettings` 早于 mount、`mergedStyle(FALLBACK_STYLE)` 安全）。
- **审查者原始结论原文**：

```
① 一致，无夹带：AppShell 设置入口、main.ts restoreSettings、新增 shared/settings.ts、DashboardView 口径标签、
   MapLibreViewer 底图状态机+重试，全部落在"底图开关+重试/退避"范围内。
② 无契约字段改动（basemap 是组件内私有 ref，类型加 'off'，未导出）；未碰 API/mock/nav/theme；
   新增共享文件 src/shared/settings.ts + 新 localStorage 键 hubflow.settings.basemap（与 station-packs 键风格一致）。
③ 无密钥、无大文件。
   - DashboardView.vue:206：底图关掉时仍写「OSM 署名见地图内」，而关态样式里已没有任何底图/署名图层
     —— 署名指向不存在的东西（ODbL 口径，建议改为"底图已关闭，无 OSM 署名"）。
   - MapLibreViewer.vue:507 的 fetch 在关闭开关时不会被 abort（只丢弃结果），所以"关＝一个请求都不发"
     只在冷启动成立；页面已加载后关闭仍会走完在途那一次。属文案口径，非缺陷。
④ 未发现会挡下游的问题：off 时确认零请求（全仓仅 MapLibreViewer.vue:507 一处底图 fetch）；
   成功/失败分支都有 disposed 与 !basemapEnabled 双保险；retryTimer 在 dropBasemap 顶部、applyBasemap 顶部、
   onUnmounted:713 三处清理，且无地图重建路径（routeKey watcher 只改 filter），不存在对已 remove 地图 setStyle
   的悬空定时器；restoreSettings 在 main.ts:23，早于 mount(:49)，且地图 basemap 初值取自同一 ref，无"白拉一次"；
   mergedStyle(FALLBACK_STYLE) 对空 sources/layers 安全，图层无 text-field/glyphs 依赖，撤销底图不会挂样式；
   手动重试会先清掉在跑的自动重试定时器，无重复调度。
```

| # | 发现 | 处置（已修 / 不改 + 理由，附文件与行号） |
|---|---|---|
| 1 | 关开关不 abort 在途 `fetch`（"不发任何底图请求"只在冷启动成立） | **成立，已修**：`MapLibreViewer.vue` 加 `inflightCtrl`，在「关」分支与 `onUnmounted` 里 `abort()` |
| 2 | 关态注脚「OSM 署名见地图内」指向不存在的东西 | **不成立，不改**（实机核过）：路网那一份 `.attribution` 只要几何是 OSM（站点包 Z 就是）就渲染，**关态实测仍在图上**（box `337,230`、`href` 正确、可见）；跟着底图消失的只有 MapLibre 自带署名控件（关态只剩「MapLibre」，开态含「OpenFreeMap © OpenMapTiles Data from OpenStreetMap」）。已在 `work/frontend/README.md` 写明这条口径，避免下次又被读成"署名跟着底图走" |

- [x] 每条发现都已处置：成立就修；不成立就用文件与行号（+ 实机数据）说明理由
- [x] 修复**明显改变了做法**时，已换一个全新上下文再跑一次 —— 第 2 轮即为此跑；第 2 轮的两条处置后各复跑一次实测（abort：关态刷新 0 请求；署名：关态 `.attribution` 仍在）

## 有没有影响别人

- [x] **没动契约字段**
- [x] **没改别人的目录**（改动全部在 `work/frontend/**`；`work/twin/` `work/perception/` `work/engine/` `stations/` 未碰）
- [x] **没动公共文件**（根 `README.md` / `.gitignore` / `.gitee/` / `docs/数据契约.md` 未碰；`work/frontend/README.md` 是本模块文档）
- [x] `git status` 里**没有** `.env` / `*.mp4` / `*.ckpt` / 图片数据集 / `node_modules/`（截图落仓库外）

## 卡点

- **车辆动点 0 个不是回归**：站点包 Z 的 `vehicleBases: []`（业主口径"用路段级着色表达路况"）→ `/api/traffic/vehicles` 返回 0 条；能力（prop + 渲染 + 图例）已保留，数据侧要给车时不用改本组件。
- **推荐路线恒不显示**：父组件 `:route-segments="[]"`（改动前亦然）；若要真画，需把站点包 Z 的 `recommend.arrival_segments` / `departure_segments` 接进 `DashboardView.vue` —— 建议另开单，不在本单。
- **对外发布前**：OpenFreeMap 自身条款尚未进 `docs/条款核实.md`，OSM 底图也没有审图号（见 `MapLibreViewer.vue` 文件头「合规」）。**现在多了一条可控口子**：底图可在顶栏「设置」里关掉，断网/外网不可控的场合可以直接以"只画路网"演示。
- 删掉自绘 SVG 后，"零依赖断网演示"这条保障由**底图解耦 + 底图开关**接管：底图挂了或关掉，看到的就是"只有路网"。

---

- [x] **我请了 Reviewer**：兜底审三人任一（Gitee 不写 CODEOWNERS 账号，靠纪律）；**作者不合并自己的 PR**

### 评论（0 条）

无评论（平台 `list_comments` 返回空数组）。

---

## PR !22 · feat(packs): 站点包只剩 Z：删除 A 包，单包时收起切换器（IKM4XX）

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/IKM4KP-station-pack-z-primary` → `main` |
| 创建 / 合并 | 2026-10-16T09:59:32+08:00 / 2026-10-16T09:59:43+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/22 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（0 条）

无评论（平台 `list_comments` 返回空数组）。

---

## PR !21 · [IKM4XX] 站点包只剩 Z：删除 A 包，单包时收起切换器（叠在 !20 之上）（L1）

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/IKM4XX-station-pack-z-only` → `task/IKM4KP-station-pack-z-primary` |
| 创建 / 合并 | 2026-10-16T09:52:36+08:00 / 2026-10-16T09:55:16+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/21 |
| 正文来源 | 本机会话存档 `mcp__gitee__create_pull` |

### 正文

> ⚠️ **叠在 PR !20 之上**（base = `task/IKM4KP-station-pack-z-primary`）。**请先合 !20**；`!20` 合入 `main` 后，**把本 PR 的 base 改回 `main`**（或按合并顺序直接合）。

## 改了什么

**站点包只剩 Z**：删除 A 包（`src/station-packs/stationA.ts` + 注册表项），顶栏「线路图切换器」在**只有一个包时不再渲染**，README / 注释 / `.env.z` 同步。**选择器层一个字没删**。

关联 Issue：**IKM4XX**（本单）· 前置 **IKM4KP / !20**（默认包改 Z、删 B / Y）· 下游 **IKM4TE**（Z 数据补齐）· **IKM4B4**（范围与路段数量按站配置）。

| 类别 | 内容 |
|---|---|
| 删包 | `src/station-packs/stationA.ts`（−545 行，A 的路网 / 基线 / 断面 / 点位 / 告警 / 场景 / 分流 / 通道全在这一个文件里） |
| 注册表 | `index.ts`：去 `STATION_A` import 与 `PACKS.A`；`DEFAULT_PACK_KEY` / `activePack()` 兜底**仍为 Z** |
| **保留不动** | `activePack` / `setActivePackKey` / `restorePackKey` / `switchPack`（§8.4「换站只改配置」靠它成立；加站 = 加一个包 + 一行 env） |
| 切换器 | `AppShell.vue`：`v-if="packList.length > 1"` —— 单包不留只有单项的死控件；包多起来自动回来 |
| 文档 | `work/frontend/README.md` §11.2 改「只有一个包 Z」、§11.3 改「唯一站点包 Z 的现状」、§11.4 口径红线同步；§12 起的历史记录加「包 A 已随 IKM4XX 删除」标记；`app-html/README.md` 一处去点名 |
| 注释 / env | `main.ts`、`vite.config.ts`、`mock/traffic.ts`、`shared/cameras.ts`、`shared/demoNetwork.ts`、`shared/demoDecision.ts`、`DashboardView.vue`、`.env.z` |

提交：`df9c092`。**13 文件、+72 / −597。**

## 填表报告

- [ ] 已按 `docs/填表报告.md` 第五节在台账末尾加了一行
- [ ] 表格是唯一入口
- [x] **本次不涉及**填表报告（没动 `stations/*.json`、也没动表格转换脚本）

## 实现方式

- 用了什么方式：**按推荐做法**——站点包 = 配置。删的是"包"，不是"选择包的机制"；选择器层保留，加站仍是"加一个包 + 一行 env"。
- 为什么不用默认推荐：——（无偏离；切换器"单包不渲染"是推荐做法里没写、但属于本单最小改法的一处，已在此说明）
- **契约与判定不变的证明**：未动 `types.ts`、数据契约、`stations/`、`work/engine/`、`work/twin/`、`docs/`；页面逻辑未改（`AppShell.vue` 只加一个 `v-if`）；全仓（`src` / 配置 / README）grep 无 `stationA` / `STATION_A` 悬空引用（`docs/历史台账/` 归档除外）。

## 怎么验证的

- [x] 本地门禁过了：`python scripts/doc_gate.py`（**7/7 通过**，exit 0）
- [x] 第 7 组（填表报告台账）是 `[通过]`
- [x] `npm run build`（`vue-tsc -b && vite build`）**通过**
- [x] 我这个模块能单独用 mock 模式跑通（`npm run dev`）
- [x] 输出 JSON 字段名对照过契约：**未改任何字段**
- [x] 产物存在性断言：本次无脚本产物；被删文件已核实不存在
- [ ] 同一输入连续跑 3 次一致：**不涉及**（无判级 / 无产物生成逻辑改动）
- [ ] CI：**本仓库不挂流水线**，门禁按 `docs/仓库设置清单.md` 第 3 节在本地跑

**实测证据**

```text
① 选择器探针（headless import station-packs/index.ts）
   PACKS 键: Z          DEFAULT_PACK_KEY: Z        默认包: Z / 肇庆东站
   切换器条目数: 1      localStorage 残留 'A' → restorePackKey -> Z | activePack -> Z

② 悬空引用：src / 配置 / README grep stationA|STATION_A → ✅ 无命中（历史台账除外）

③ 浏览器实测（Tabbit，:5173 真实页面，与 IKM4KP 之后逐项对照）
   线路图切换器节点数 = 0        ← 本单唯一的行为变化（按预期收起）
   站点 chip = 肇庆东站
   路段 id = SZ-01 / SZ-03 / SZ-05 / SZ-07 / SZ-12（无 SEG-* 串味）
   页脚 = 底图来源:OpenFreeMap(OpenStreetMap 数据,ODbL) · 署名见地图内 · 不缓存瓦片 · 路网:路网几何为真值（OSM 切片）
   → 除"切换器没了"以外，**逐字与 IKM4KP 之后一致**
```

**如实记（不阻塞）**：**A 是数据最全的演示包**（10 路段 / 4 断面 / 落客点 / 候客区 / 告警 / 场景 / 分流）。删掉之后，「切回有数据的演示站」这条路**没有了** —— 大屏与决策页**如实显示"本站无此数据"**（IKM4KP 已确认的口径），补齐走 **IKM4TE**（范围先由 **IKM4B4** 定）。

## 审查记录（**必填**）

### （1）AI 预审（作者自查）

- 预审意见原文：作者自查四条——① 改了什么：只有"删 A + 单包收切换器 + 注释/文档同步"，无夹带；② 契约与别人目录：未动 `types.ts` / 契约 / `stations/` / 三块他人目录；③ 密钥与口径：无密钥、无大文件、无新增数值，口径方向是**收紧**（如实标注"示例 / 演示值""不接桥接"）；④ 悬空引用：`src` 与两份 README 已清，历史台账为归档不动。自查**未发现阻断项**，主动补了三条核对：选择器四个函数逐字保留、`PACKS` 只剩 `Z`、单包时切换器 `v-if` 生效。

### （2）快速独立审查（全新上下文，目标 ≤ 5 分钟）

- 审查者（全新上下文，写清工具 / 模型）：**全新上下文子代理**（独立会话、不复用写代码时的对话；模型 = deepseek-flash）
- 我只提供了：改动范围（本单分支相对基线分支的 diff）+ 那 4 个问题（未提供实现思路、可疑点、既有结论、预期结果）
- **4 问结论**：**4 问全过，未发现可执行问题**（1 条环境须知 + 1 条非阻塞备注）
- **审查者原始结论原文**（照录，含它自己的前提说明）：

> 【快速审查 · IKM4XX 站点包只剩 Z】结论：**4 问全过，未发现可执行问题**（1 条环境须知 + 1 条非阻塞备注）
>
> 前提（重要）：`task/IKM4KP-station-pack-z-primary`...HEAD 与 `HEAD` 三者 SHA 完全相同（2a23b54），指定的 diff **为空**；实际改动在**未提交的工作区**（`git diff HEAD --stat` = 13 files, +72/-597）。以下按工作区 diff 审查。
>
> - ① 与口径一致：文件集只有删 `stationA.ts`、`station-packs/index.ts` 去 A 注册（选择器 4 函数全保留）、`AppShell.vue` 加 `v-if="packList.length > 1"`、README/.env.z/vite.config.ts/main.ts 注释与历史改写。无夹带。
> - ② 未碰契约字段、未碰 `stations/`、`work/engine/`、`work/twin/`、`docs/`（docs 零改动）。触及的公共文件只有 `work/frontend/README.md` 与 `app-html/README.md`，均为口径同步。
> - ③ 无密钥、无大文件、无新增二进制；口径方向是**反向**的——新增「示例/演示值」「不接孪生桥接」等如实标注，未把模拟数据说成实测。
> - ④ 无遗留 `STATION_A` / `stationA` 导入（仅 `docs/历史台账/*.md` 历史文本仍提及，属既有内容、本单未动）。`DEFAULT_PACK_KEY='Z'` 与 `main.ts` / `vite.config.ts` 兜底同为 Z；`restorePackKey` 对残留 'A'/'B'/'Y' 有 `PACKS[k]` 兜底。接口/字段无不一致。
> - 非阻塞：`work/frontend/README.md:421,430` 新引用的 IKM4TE / IKM4B4 在 `docs/历史台账/issue-归档.md` 里检索不到；若该台账是权威登记处，需登记后才能保证追踪成立（不影响代码）。
> - 环境须知：改动尚未提交（`stationA.ts` 在工作区为 `D` 未 staged），需按本单流程落成提交。

| # | 发现 | 处置（已修 / 不改 + 理由，附文件与行号） |
|---|---|---|
| 1 | `work/frontend/README.md:421,430` 引用的 IKM4TE / IKM4B4 在 `docs/历史台账/issue-归档.md` 里检索不到 | **不改**：`docs/历史台账/` 是**归档**（收录迁移前与当次已归档的单），IKM4B4 / IKM4TE / IKM4KP / IKM4XX 是 Gitee 上的**在办单**，本就不会出现在归档文本里；**追踪以 Gitee issue 为准**（口径写在 `docs/历史台账/` 的用法里）。 |
| 2 | 审查时改动尚未提交（工作区 `D` / `M`） | **已处置**：本条提交 `df9c092`；提交后 `git diff --cached --stat` = **13 files / +72 / −597**，与审查者报的数字**逐字一致**。 |

- [x] 每条发现都已处置（1 条不改 + 理由；1 条已落提交）
- [ ] 修复**明显改变了做法**时换新上下文重跑 —— 本次两处处置都**没有改变做法**（一条是说明、一条是落提交），故不重跑

## 有没有影响别人

- [x] **没动契约字段**（`segments.json` / `routes.json` / `vehicles.json` / `render.json`）
- [x] **没改别人的目录**（`work/twin/` `work/perception/` `work/engine/` `work/assembly/` `stations/` 全未动；`work/frontend/` 归接口与双端）
- [x] **没动公共文件**（根 `README.md`、`.gitignore`、`.gitee/`、`docs/数据契约.md`、`app/main.py`）
- [x] `git status` 里没有新增 `.env` / 视频 / 权重 / `node_modules`（本次只把**已入库**的 `.env.z` 改了一行注释，无新增、无密钥）

## 卡点

- **技术卡点：无。**
- **流程卡点**：本 PR **叠在 `!20` 之上**（base 是那条分支）—— 请先合 `!20`，再把本 PR 的 base 改回 `main`。
- **需人**：按 `docs/协作规范.md` 第 4 节，作者不得审 / 合并自己的 PR —— 请**兜底审三人任一**过一眼「影响别人」与「对外口径」两件事后合并。
- 本次浏览器验证未截图（页面变化只有"切换器消失"一项，节点数 0 已由 DOM 断言证明）；需要截图我补。

---

- [ ] **我请了 Reviewer**（`CODEOWNERS` 会自动带上；没带上就手动加）—— Gitee 侧本会话无法指定 reviewer 账号，**已在上面写明请兜底审三人任一**；作者不合并自己的 PR。

### 评论（0 条）

无评论（平台 `list_comments` 返回空数组）。

---

## PR !20 · [IKM4KP] 站点包以 Z 为主：默认包改 Z、删除 B / Y 两个包（含 env / dev 脚本 / README 同步）（L1）

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/IKM4KP-station-pack-z-primary` → `main` |
| 创建 / 合并 | 2026-10-16T09:42:34+08:00 / 2026-10-16T09:45:04+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/20 |
| 正文来源 | 本机会话存档 `mcp__gitee__create_pull` |

### 正文

## 改了什么

**站点包以 Z 为主**：默认包从 A 改为 Z，**删除 B / Y 两个包**（含 env / dev 脚本 / README 同步）。**A 包保留**为可切换次包。

关联 Issue：**IKM4KP**（本单）。另：**IKM4B4**（站点范围与路段数量按站配置）、**IKM4TE**（Z 的数据补齐）已开单，均不在本 PR。

| 类别 | 内容 |
|---|---|
| 删包 | `stationB.ts`、`stationB.network.ts`、`stationY.ts`、`stationY.network.ts`（共 −1209 行） |
| 默认改 Z（**三处**） | `station-packs/index.ts`（`DEFAULT_PACK_KEY = 'Z'` + `activePack()` 兜底 `STATION_Z`）、`src/main.ts`（`?? 'Z'`）、`vite.config.ts`（mock 注入兜底 `\|\| 'Z'`） |
| 注册表 | `PACKS` 只剩 `A` / `Z`（顶栏切换器自动只剩两项） |
| env / 脚本 | 删 `.env.station2`、`.env.y`；`package.json` 删 `dev:station2`、`dev:y`；`dev:z`（:6895）保留 |
| 文档 | `work/frontend/README.md` §11.2 改写为"以 Z 为主"、§11.3 改为 **A / Z 对照**、§11.4 改为**包 Z 口径红线**；`docs/历史台账/` 归档原文未动 |
| 去悬空引用 | `shared/demoNetwork.ts`、`shared/demoDecision.ts` 注释；`.env.z` 注释（审查发现，见下） |

**两个提交**：`80bffb6`（主体）+ `2a23b54`（审查发现的 `.env.z` 过期注释）。分支 `task/IKM4KP-station-pack-z-primary`。合计 14 文件、+74 / −1286。

## 填表报告

- [ ] 已按 `docs/填表报告.md` 第五节在台账末尾加了一行
- [ ] 表格是唯一入口
- [x] **本次不涉及**填表报告（没动 `stations/*.json`、也没动表格转换脚本）

## 实现方式

- 用了什么方式：**按推荐做法**——站点包 = 配置，换站只改配置、不改引擎代码（手册 §8.4）。删包 + 三处默认值改 Z + env / 脚本 / README 同步。
- 为什么不用默认推荐：——（按推荐做法，无偏离）
- **契约与判定不变的证明**：未动 `types.ts`、未动数据契约、未动 `stations/`；`views/` 与 `mock/` 的**逻辑一行未改**（只改了 `shared/` 两个文件的注释）；`X-Station-Pack` 语义未变；全仓 grep 无 `STATION_B / STATION_Y / stationB / stationY / dev:station2 / .env.station2` 悬空引用（`docs/历史台账/` 归档除外）。

## 怎么验证的

- [x] 本地门禁过了：`python scripts/doc_gate.py`（**7/7 通过**，exit 0）
- [x] 第 7 组（填表报告台账）是 `[通过]`
- [x] 我这个模块**能单独用 mock 模式跑通**：`npm run dev`（:5173）与 `npm run dev:z`（:6895）
- [x] 输出 JSON 字段名对照过契约：**未改任何字段**
- [x] 产物存在性断言：本 PR 无脚本产物；**删除的文件已逐个核实不存在**
- [ ] 同一输入连续跑 3 次一致：**不涉及**（无判级 / 无产物生成逻辑改动）
- [ ] CI：**本仓库不挂流水线**，门禁按 `docs/仓库设置清单.md` 第 3 节在本地跑（上一条）

**实测证据**

```text
① 构建（改动后）：npm run build → vue-tsc -b && vite build 通过，dist 正常产出
② 门禁：python scripts/doc_gate.py → 7/7 通过
③ 选择器探针（headless import station-packs/index.ts）
   PACKS 键: A,Z      DEFAULT_PACK_KEY: Z      默认包: Z / 肇庆东站
   localStorage 残留 'Y' / 'B' → restorePackKey 一律落回 Z（不白屏）
④ 运行中的 dev server :5173（真实浏览器实测，Tabbit）
   左栏「选择监控」= 5 个路段；路段 id = SZ-01/03/05/07/12
   页脚：底图来源:OpenFreeMap(OpenStreetMap 数据,ODbL)· 署名见地图内 · 不缓存瓦片 · 路网:路网几何为真值（OSM 切片）
   地图标签：底图：OpenFreeMap · OSM；6 个摄像头图钉在位
   → 浏览器侧与 mock 注入侧取的**是同一个包 Z**（"页面画一个站、mock 发另一个站"的风险已排除）
⑤ 悬空引用：grep 仅剩两处"包 B / Y 已删除"的说明性注释
```

**如实记一点（不阻塞）**：Z 是**薄包**，mock 的 `/api/traffic/segments` 只出 **5 条**（有基线的摄像头覆盖段），其余 16 段只作为几何灰轮廓画在图上；断面 / 点位 / 告警 / 场景面板**如实显示"本站无此数据"**，**未拿包 A 的演示值去填**。补齐见 **IKM4TE**。

## 审查记录（**必填**）

### （1）AI 预审（作者自查）

- 预审意见原文：作者自查四条——① 改了什么：三处默认值同为 Z（已用 headless 探针 + 运行中 dev server 双向核对）；② 契约：未动 `types.ts` / 契约 / `stations/`；③ 密钥与口径：diff 内无密钥、无大文件，未新增任何数值，Z 的"几何真值 / 指标演示"口径未变；④ 悬空引用：`src` 与 README 已清（历史台账为归档，不动）；自查**未发现阻断项**，但主动补了一条自查发现——`.env.z` 注释仍写"第四站 / 与二站 6880 / Y 站 6890 并存"，属过期描述，**已在本 PR 第二个提交修掉**。

### （2）快速独立审查（全新上下文，目标 ≤ 5 分钟）

- 审查者（全新上下文，写清工具 / 模型）：**全新上下文子代理**（独立会话、不复用写代码时的对话；模型 = deepseek-flash）
- 我只提供了：改动范围（`git diff main...HEAD`）+ 那 4 个问题（未提供实现思路、可疑点、既有结论、预期结果）
- **4 问结论**（≤ 10 行）：②③④ 全过；① 仅一处过期注释（`.env.z:1-2`），无夹带、无阻断。
- **审查者原始结论原文**：

> 只读审查结果（task/IKM4KP-station-pack-z-primary vs main，13 文件 / +73 −1286）：
>
> ① 与口径一致，无夹带：改动仅 work/frontend/README.md、ui-vue/package.json、vite.config.ts、src/main.ts、src/shared/demoDecision.ts、src/shared/demoNetwork.ts、src/station-packs/index.ts + 删 .env.station2/.env.y/stationB(.network).ts/stationY(.network).ts；未动 stations/、work/engine/、work/twin/、docs/、契约文件。
> ② 未碰契约字段：无 X-Station-Pack / 数据契约 / types.ts 改动（X-Station-Pack 仅调 activePackKey() 未改语义）；stationA.ts、main 分支已有文件均未改。
> ③ 无真实密钥、无大文件、无口径反串：diff 密钥扫描为空，最大净增仅 README 45 行，删除的 stationB/Y.network.ts 为纯删；stationZ.ts:29/35-37 hasVideo:false 与 stationZ.ts:264 bridge.enabled:false、stationZ.ts:184 osm:true 与 README §11.4 口径一致。
> ④ 默认值双点已同步（main.ts:18 与 vite.config.ts:20 同为 'Z'，index.ts:22 DEFAULT_PACK_KEY='Z'、index.ts:82 兜底 STATION_Z）；全仓 grep 无 STATION_B/STATION_Y/stationB/stationY/dev:station2 悬空引用；切换器读 PACKS，只列 A/Z，老 localStorage 的 B/Y 经 PACKS[k] 落回 Z。
>
> 可执行发现（1 条，均非阻断）：
> - work/frontend/ui-vue/.env.z:1-2 — 注释仍写「第四站 / 与默认站(5173)/二站(6880)/Y 站(6890) 并存」，与删包后现状矛盾（该文件本单未改，非夹带）。
>
> 其余 3 问全过。未运行构建/测试（限时只读审查）。

| # | 发现 | 处置（已修 / 不改 + 理由，附文件与行号） |
|---|---|---|
| 1 | `work/frontend/ui-vue/.env.z:1-2` 注释仍写"第四站 / 与二站 6880 / Y 站 6890 并存" | **已修**：改为"主包（`npm run dev:z`）… 与 `npm run dev`（5173，同为包 Z）并存，方便同包不同端口对照着看"（提交 `2a23b54`）；`doc_gate` 重跑仍 7/7 |

- [x] 每条发现都已处置：成立就修（见上表），无"不改"项
- [ ] 修复**明显改变了做法**时，已换一个全新上下文再跑一次 —— 本次修复**只改注释**、未改变做法，故不重跑

## 有没有影响别人

- [x] **没动契约字段**（`segments.json` / `routes.json` / `vehicles.json` / `render.json`）
- [x] **没改别人的目录**（`work/twin/` `work/perception/` `work/engine/` `work/assembly/` `stations/` 全未动；`work/frontend/` 归接口与双端）
- [x] **没动公共文件**（根 `README.md`、`.gitignore`、`.gitee/`、`docs/数据契约.md`、`app/main.py`）
- [ ] `git status` 里没有 `.env` —— **如实说明**：本次**删除**了两个**已入库**的站点环境文件（`.env.station2`、`.env.y`，与既有的 `.env.mock` / `.env.production` / `.env.remote` / `.env.z` 同类，只含 `VITE_USE_MOCK` / `VITE_STATION_PACK` / `VITE_DEV_PORT` 三个开关，**无任何密钥**），所以这一栏留空不勾；未**新增**任何 `.env`，无视频 / 权重 / `node_modules`。

## 卡点

- **技术卡点：无。**
- **需人**：按 `docs/协作规范.md` 第 4 节，作者不得审 / 合并自己的 PR —— 请**兜底审三人任一**（`@YONEK0` / `@ouu2006` / `@2652201498w-wq`）过一眼"影响别人"与"对外口径"两件事后合并。
- 截图（举证）在本地：`（本机路径已隐去）`（2544×1267，Tabbit 实拍 :5173 大屏，含 6 个摄像头图钉 + 5 条路段 + 矢量底图页脚）。**Gitee MCP 没有图床**，需要的话我把它拖进评论。

---

- [ ] **我请了 Reviewer**（`CODEOWNERS` 会自动带上；没带上就手动加）—— Gitee 侧本会话无法指定 reviewer 账号，**已在上面写明请兜底审三人任一**；作者不合并自己的 PR。

### 评论（1 条）

**1 · @ozxowx · 2026-10-16T09:53:00+08:00**

**给审查人一条前置提醒**：本 PR 的分支 `task/IKM4KP-station-pack-z-primary` 现在同时是 **[!21](https://gitee.com/ozxowx/hubflow/pulls/21)** 的 base（业主 2026-10-16 追加口径：**A 包也删掉**，站点包只留 Z）。

建议合并顺序：

1. 先审并合并**本 PR（!20）**——它就是"默认包改 Z + 删 B / Y"这一单；
2. 再合 **!21**（删 A + 单包收起切换器），合前把 !21 的 base 从本分支改回 `main`（!21 的 diff 只含它自己那 13 文件 / +72 / −587）。

两单的边界很清楚：**!20 改默认与删两个包；!21 只删剩下的 A 并收起切换器**，各自带独立的快速独立审查留痕。

---

## PR !19 · web端监控大屏的底图采用OpenFreeMap+osm+描绘线路网组成的路段监控画面

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/dashboard-openfreemap-basemap` → `main` |
| 创建 / 合并 | 2026-10-15T22:22:37+08:00 / 2026-10-15T22:42:08+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/19 |
| 正文来源 | 本机会话存档 `mcp__gitee__create_pull` |

### 正文

## 改了什么

监控大屏中栏底图**新增「矢量地图」视图**（MapLibre GL + OpenFreeMap 的 OSM 真实底图），与原有「示例路网」自绘视图**可切换**；**默认底图按当前路网是否为真 OSM 几何来定**。业主 2026-10-15 口径：「想要的效果更接近矢量地图」——**真实道路叠真实 OSM 底图**，配合站点包 Z 已有的摄像头布点，构成「底图 + 分段路网 + 每段一个摄像头」的路段监控画面。

**核心收益：站点包坐标是 WGS-84，直接喂给 MapLibre 即可，不需要任何坐标转换。** 对比高德方案：高德底图是 GCJ-02，不转会整体偏约 600 m（实测）；且高德需要 Key + 安全密钥，并有「商业目的须先购买技术服务许可」（高德 3.2.1）的条款风险。OpenFreeMap **免 Key / 免注册 / 免安全密钥**。

| 文件 | 改动 |
|---|---|
| `src/views/dashboard/components/MapLibreViewer.vue` | **新增**（388 行）：MapLibre 底图 + 路段线 + 选中高亮 + 摄像头图钉 |
| `src/views/dashboard/DashboardView.vue` | 中栏加「示例路网 / 矢量地图」切换条；默认底图按 `isOsmNetwork()` 定 |
| `src/station-packs/index.ts` | 包键**持久化**（`restorePackKey` + `switchPack` 落 localStorage） |
| `src/main.ts` | 启动时读回上次选的包 |
| `src/api/http.ts` | 每个请求带 `X-Station-Pack` 头 |
| `src/mock/index.ts` | mock 按该头取包 |
| `package.json` / `package-lock.json` | 新增 `maplibre-gl@^6.14.0` |
| `vite.config.ts` | `optimizeDeps.exclude: ['maplibre-gl']` |
| `.env.mock` / `.env.production` / `.env.remote` | 注明地图**不需要任何 Key** |

**配套修复两处旧问题（不修的话本单没法验）**：

1. **顶栏线路图切换器是坏的**：`AppShell.choosePack()` 选完会 `window.location.reload()`，而包键 `injectedKey` 只是模块级变量 → **刷新即退回默认包**。修法：`switchPack()` 落一份 localStorage，`main.ts` 启动时 `restorePackKey()` 读回。
2. **mock 收不到包键**：mock 中间件跑在 vite 的 **Node 进程**里，浏览器侧 `switchPack()` 改不到它 → 切包后「**几何按新包画、基线仍出默认包**」，同一页两套路网。修法：`src/api/http.ts` 每个请求带 `X-Station-Pack`，mock 侧按它 `setActivePackKey()`。

## 填表报告

- [x] **本次不涉及**填表报告（没动 `stations/*.json`、也没动表格转换脚本）

## 实现方式

- **用了什么方式**：底图 = **MapLibre GL 6 + OpenFreeMap 的 Liberty 样式**（矢量瓦片，数据来自 OpenStreetMap），按 `maplibre-gl` **npm 依赖**引入（可锁版本、可审查），**不用 CDN**。摄像头布点与「只摄像头段上色」**复用上游既有的共享口径 `shared/cameras.ts`**（`cameraPins()` / `isCameraCovered()` / `perceptionHref()`），**不在两个视图里各写一份规则**。
- **为什么不用默认推荐**：既有大屏是**自绘 SVG 路网**（一期口径「不挂第三方底图层」）。业主 2026-10-15 改口径要真实底图，故新增矢量视图；**但自绘视图一字未删**，两个标签并存、可切 —— 断网演示仍走自绘，不依赖任何外部服务。
- **契约与判定不变的证明**：**未动任何契约字段** —— `/api/traffic/*` 的响应形状、`docs/数据契约.md`、`stations/*.json` 一字未改。本单只改**渲染层**（换底图）+ 顶栏切换器的**客户端持久化**。判级 / CI / 四级编码口径未动；`is_simulated` 语义未动。
- **影响面**：只动 `work/frontend/ui-vue/`（本模块自己的目录）；未动 `work/twin/` `work/perception/` `work/engine/` `stations/`。

> **技术栈选型申报**（`docs/开发规范.md` 文首：技术栈与选型 → **队长 / 业主拍板**）：本单**新增了一个前端地图库依赖**（`maplibre-gl`）与**一个第三方底图服务**（OpenFreeMap）。已由**业主 2026-10-15 当面拍板**（原话：「想要的效果更接近矢量地图」）。**请兜底审复核这一条。**

## 怎么验证的

- [x] 本地门禁过了：`python scripts/doc_gate.py` → **7/7 全绿**（第 7 组填表报告台账 `[通过]`）
- [x] **第 7 组（填表报告台账）是 `[通过]`**
- [x] 我这个模块**能单独用样例文件跑通**：`npm run dev` 起 5173，`/#/dashboard` 可开；mock 模式（`VITE_USE_MOCK=1`）正常出快照
- [x] 输出 JSON **字段名 / 必填字段对照过 `docs/数据契约.md` v2.0** —— 本单**未改任何输出字段**
- [x] **产物存在性断言**过了：`npm run build` 产出 `dist/assets/maplibre-gl-worker-DxGNRm0a.mjs`（**508,314 字节**，非 0）
- [x] 同一输入连续跑 3 次，结果一致：默认底图由 `isOsmNetwork()` 决定，是纯函数判定；三次刷新落点一致
- [ ] CI 已跑完且全绿 —— **本仓库不挂流水线**，门禁靠本地 `doc_gate`（已全绿）；Gitee 侧无 check

**实跑证据（浏览器，`/#/dashboard`）**：

| 场景 | 结果 |
|---|---|
| 站点包 **Z**（真 OSM 路网 + 6 路摄像头） | 默认落 **矢量地图**；`mapTag=底图：OpenFreeMap · OSM`；**6 个摄像头图钉全在**（C-01…C-06，标题含「未接入视频源 · 本期留空 · 点击进感知层」，空心样式与 `hasVideo:false` 一致）；署名 `MapLibre \| OpenFreeMap © OpenMapTiles Data from OpenStreetMap`；比例尺 200 m |
| 站点包 **A / B / Y**（占位 / 示意几何） | 默认落 **示例路网**（自绘 SVG），**未回归** |
| 控制台 | **零报错**（`errors: []`） |
| 生产构建 | `dist/assets/maplibre-gl-worker-*.mjs` 在；主 chunk 2,234 kB（gzip 664 kB） |

> ⚠️ **两个必须说明的技术坑**（都是实测踩出来的，已修并写进代码注释）：
> ① **dev**：MapLibre 的矢量瓦片解析跑在独立 worker（508 KB）里，主包按 `new URL('./maplibre-gl-worker.mjs', import.meta.url)` 找它；Vite 的**依赖预打包只产出 `deps/maplibre-gl.js`、不产出那个 worker** → 运行时 worker URL 落空、报 `Worker failed to load`、底图整块空白。修法 `optimizeDeps.exclude: ['maplibre-gl']`。
> ② **生产构建**：修完 ① 后 `npm run build` **成功且 exit 0**，但 dist 里**只有 3 个产物、worker 根本没被产出**；`vite preview` 一跑就空白，且**不报 HTTP 错**（worker 加载失败不走 response 事件）——只测 dev 永远发现不了。修法：`import workerUrl from '...maplibre-gl-worker.mjs?url'` + `setWorkerUrl(workerUrl)`。

**合规（按 `docs/条款核实.md` 的纪律）**：OSM/ODbL **保留署名** —— MapLibre 默认 AttributionControl 不隐藏、不被 UI 遮挡（截图可见）；**不缓存瓦片、不做离线包**（代码里没有瓦片缓存层）。⚠️ 遗留：OpenFreeMap 作为**第三方瓦片托管方**，其自身条款**尚未进过本仓库的条款核实清单**；且 OSM 底图**没有审图号** —— 对外发布前须补核（已写进 `MapLibreViewer.vue` 文件头）。

## 审查记录（**必填**）

### （1）AI 预审（作者自查）

按 `docs/开发规范.md` §11 四条自检 + 门禁逐条过（**预审意见原文**）：

> ① 能单独跑通：`npm run dev` 起 5173，`/#/dashboard` 打开、中栏两个标签可切；`npm run build` exit 0。
> ② 字段名对得上契约：**本单不产出契约文件、不改任何输出字段**；只改渲染层与客户端持久化。
> ③ 没改别人的目录：`git status` 只有 `work/frontend/ui-vue/**`（本模块目录）。
> ④ 没有 Key / 视频 / 权重：改动里无 `.env` 真值（`.env.*` 只加注释，**注明地图不需要 Key**）、无 `*.mp4` / `*.ckpt`。`package-lock.json` 因新增 `maplibre-gl` 而变（+228 行，属依赖锁文件，应入仓库）。
> ⑤ 门禁：`python scripts/doc_gate.py` **7/7 全绿**。
> 另：本单**新增了一个前端依赖 + 一个第三方底图服务**，属 `开发规范.md` 文首的「技术栈与选型」——已在 PR 里单独申报，请兜底审复核。

### （2）快速独立审查（**全新上下文，目标 ≤ 5 分钟**）

- 审查者（全新上下文，写清工具 / 模型）：**独立子代理（全新上下文，deepseek-flash）**，只读 `git diff`
- 我只提供了：改动范围（分支 `task/dashboard-openfreemap-basemap`）+ 那 4 个问题（**未提供**实现思路、可疑点、既有结论、预期结果）
- **4 问结论**（≤ 10 行）：

> ① 与「改了什么」不一致（夹带无关改动）：`src/api/http.ts:27`、`src/mock/index.ts:38-41`、`src/station-packs/index.ts:28-66`、`src/main.ts:12` 新增「线路图切换器」包键 localStorage 持久化 + 每请求 `X-Station-Pack` 头，与 OpenFreeMap 底图无关，提交说明未提。其中 mock 中间件按请求头改写**进程级** `injectedKey`，多客户端会互相覆盖。
> ② 未改契约字段、未动别人目录；`http.ts` 属公共请求层但只加请求头，未改契约。
> ③ 无密钥（OpenFreeMap 免 Key）、无大文件；底图来源与 `is_simulated` 口径自洽。
> ④ `MapLibreViewer.vue:95` `net = DEMO_NETWORK.segments` 为模块级常量只读一次（NetMap 是惰性读包），切包/孪生覆盖后矢量视图路网不更新。
> ④ `MapLibreViewer.vue:169-174` `cameraPins()` 只在 load 时执行一次，切包后图钉不重绘。
> ④ `package-lock.json:163-169` 传递依赖 `@mapbox/jsonlint-lines-primitives` 声明 `engines node>=22`，与 `package.json` 的 `>=20.19` 冲突（Node 20 + `engine-strict` 会安装失败）。
> ④ `v-if/v-else` 配对（`DashboardView.vue:859-878`）已核对正确；`setWorkerUrl` 与 `./dist/maplibre-gl-worker.mjs` 在 maplibre-gl 6.14.0 均存在，非问题。

- **审查者原始结论原文**：

> 快速审查结果（分支 task/dashboard-openfreemap-basemap vs origin/main，只读 git diff）：
> ① 与「改了什么」不一致（夹带无关改动）：src/api/http.ts:27、src/mock/index.ts:38-41、src/station-packs/index.ts:28-66、src/main.ts:12 新增「线路图切换器」包键 localStorage 持久化 + 每请求 X-Station-Pack 头，与 OpenFreeMap 底图无关，提交说明未提。其中 mock 中间件按请求头改写进程级 injectedKey，多客户端会互相覆盖。
> ② 未改契约字段、未动别人目录；http.ts 属公共请求层但只加请求头，未改契约。
> ③ 无密钥（OpenFreeMap 免 Key）、无大文件；底图来源与 is_simulated 口径自洽。
> ④ 逻辑/下游：
> - MapLibreViewer.vue:95 `net = DEMO_NETWORK.segments` 为模块级常量只读一次（NetMap 是惰性读包），切包/孪生覆盖后矢量视图路网不更新。
> - MapLibreViewer.vue:169-174 cameraPins() 只在 load 时执行一次，切包后图钉不重绘，与本文件「切换即整套跟着换」注释口径不符。
> - package-lock.json:163-169 传递依赖 @mapbox/jsonlint-lines-primitives 声明 engines node>=22，与 package.json engines.node>=20.19 冲突（Node 20 + engine-strict 会安装失败）。
> - v-if/v-else 配对（DashboardView.vue:859-878）已核对正确，setWorkerUrl 与 ./dist/maplibre-gl-worker.mjs 在 maplibre-gl 6.14.0 均存在，非问题。

| # | 发现 | 处置（已修 / 不改 + 理由，附文件与行号） |
|---|---|---|
| 1 | ① **夹带无关改动**：`http.ts` / `mock/index.ts` / `station-packs/index.ts` / `main.ts` 的切换器持久化 + `X-Station-Pack` 头，「提交说明未提」 | **描述问题成立，已处置**：这四处是**本单的必要配套** —— 不修则**切不到站点包 Z**，矢量底图这套效果无从验证（Z 不是默认包）。**PR 正文「改了什么」已单独列出这两处配套修复**（提交说明一行放不下，以 PR 正文为准）。**代码保留** |
| 2 | ① 其中 **mock 按请求头改写进程级 `injectedKey`，多客户端会互相覆盖** | **成立，如实记为已知限制**（不修，理由随附）：mock 中间件**只在 dev / `preview:mock` 跑**，且本单只是让"一个浏览器切包"能生效；正确修法是把包键**作为参数**穿透 `mock/traffic.ts` 的调用链（那里 `activePack()` 有几十处调用点），属独立一单。**已在 PR「有没有影响别人」第 ④ 条与 `src/mock/index.ts` 注释里写明**，请兜底审知悉 |
| 3 | ④ `MapLibreViewer.vue:95` `net` 只读一次；`:169-174` `cameraPins()` 只在 load 时执行一次 → 切包/孪生覆盖后不重绘 | **不成立（附依据）**：① `const net = DEMO_NETWORK.segments` 写在 **`<script setup>` 内**，是**每实例**求值、不是模块级常量；视图切换是 `v-if/v-else` 的**挂载 / 卸载**（`DashboardView.vue`），**重挂即重读**；② 切包走 `AppShell.choosePack()` 的 `window.location.reload()`，整页重建；③ 孪生覆盖在 `main.ts` **挂载前**完成。故当前无实害。**已在 `MapLibreViewer.vue` 注释里留警示**：将来若把切包改成"不刷新"，这里必须补 `watch` 重读 `net` 与重画图钉 |
| 4 | ④ `package-lock.json:163-169` 传递依赖 `@mapbox/jsonlint-lines-primitives` 声明 `node>=22`，与 `package.json` 的 `>=20.19` 冲突 | **成立（警告级，不改）**：实测本机 `npm config get engine-strict` = **`false`** → npm **只警告、不失败**；`maplibre-gl` 自身声明 `node>=16.14.0`，该传递依赖**只在构建期**用。**不动 `engines.node`** —— 提高全队最低 Node 版本属团队决定，不在本单范围。已在 PR 里写明，请兜底审知悉 |
| 5 | ④ `v-if/v-else` 配对、`setWorkerUrl` 与 worker 路径在 6.14.0 均存在 | 已核对，**确认非问题**（审查者自己也标了"非问题"） |

- [x] 每条发现都已处置：**成立就修；不成立就用文件与行号说明理由**
- [x] 修复**明显改变了做法**时，已换一个全新上下文再跑一次 —— 本轮**未改做法**（第 1/2/4 条为保留 + 写明，第 3 条为说明不成立），故未重跑第二轮独立审查

## 有没有影响别人

- [x] **没动契约字段**（`segments.json` / `routes.json` / `vehicles.json` / `render.json`）
- [x] **没改别人的目录** —— 只动 `work/frontend/ui-vue/`（本模块目录）
- [x] **没动公共文件**（根 `README.md`、`.gitignore`、`.gitee/`、`docs/数据契约.md`、`app/main.py` 路由注册）
- [x] `git status` 里**没有** `.env` 真值 / 视频（`*.mp4`）/ 模型权重（`*.ckpt`）/ 图片数据集 / `node_modules/`

**如果动了契约字段，必须在这里写明**：**未动契约字段**。

> ⚠️ **对别人的影响（如实说）**：
> ① **新增前端依赖 `maplibre-gl`**（+约 1.1 MB 进主 chunk）——会影响所有人的 `npm install` 与构建体积；
> ② **默认底图会变**：路网是真 OSM 几何的包（**当前只有站点包 Z**）默认从「自绘」变「矢量底图」，需要联网才能出底图；**断网时切回「示例路网」标签即可**（该视图零外部依赖）。A/B/Y 三个包的默认**没变**。
> ③ **改动了 `src/api/http.ts`（所有请求都加一个头 `X-Station-Pack`）与 `src/mock/index.ts`** —— 这是 `work/frontend/` 内两个**公共文件**（不只大屏用）。若后端 / 别的前端模块有按请求头分流的行为，需知会。**这是本 PR 最需要兜底审看一眼的一条。**
> ④ **已知限制（独立审查指出，如实登记）**：mock 中间件**按请求头改写进程级** `injectedKey` —— 同一台 dev server 上若有**两个浏览器选了不同的包**，会互相覆盖。mock 只在 dev / `preview:mock` 跑，本单只保证"一个浏览器切包"能生效；**正确修法**是把包键作为**参数**穿透 `mock/traffic.ts` 的调用链（那里 `activePack()` 有几十处调用点），留作独立一单。
> ⑤ **`npm install` 会多一条 `EBADENGINE` 警告**：`maplibre-gl` 的传递依赖 `@mapbox/jsonlint-lines-primitives` 声明 `node>=22`，而本项目 `engines.node` 是 `>=20.19`。实测 `engine-strict=false`（默认）→ **只警告、不失败**；`maplibre-gl` 自身是 `node>=16.14.0`。**未改 `engines.node`**（提高全队最低 Node 版本不属本单范围）。

## 卡点

无。

---

- [x] **我请了 Reviewer**（`CODEOWNERS` 会自动带上；没带上就手动加）—— 已按 `CODEOWNERS` 指派
      —— **不要自己合并自己的 PR**

### 评论（1 条）

**1 · @ozxowx · 2026-10-15T22:41:48+08:00**

## 审查记录（AI 独立审查 · 2026-10-15）

**改动范围**：`work/frontend/ui-vue/`——新增 MapLibre 矢量底图 + 中栏「示例路网 / 矢量地图」切换；顺带修顶栏切换器（localStorage 记忆 + mock 按请求头取包）；`.env.*` 只加「地图不需要 Key」注释（无密钥）。

**怎么验的**：
- `npm run build`（`vue-tsc -b && vite build`）**通过**；产物里 `dist/assets/maplibre-gl-worker-*.mjs`（508 KB）确实产出 —— 即「生产构建底图空白」那条修法生效。
- `python scripts/doc_gate.py` **7 组全过**（含第 5 组密钥扫描）。
- 起 dev（mock）实测顶栏切换器那条链：`/api/traffic/network` 的 `note`、`/api/traffic/segments` 的段号都随 `X-Station-Pack` 变（A → `SEG-00x`，Z → `SZ-0x`），说明「浏览器选包 → mock 供数」确实通了。
- 逐条核对：`.env.*` 无密钥；`optimizeDeps.exclude` + worker `?url` + `setWorkerUrl()` 三处配套；署名控件未隐藏、未被遮挡（ODbL 义务）；`isOsmNetwork()` 判据在 mount 前已定（`main.ts:39` 的 `await loadTwinNetwork()`），默认视图不会晚一步；站点包坐标是 WGS-84，未做多余坐标转换。

**发现（不阻塞，建议另开 Issue）**：

| # | 发现 | 处置 |
|---|---|---|
| 1 | mock 进程里的 `DEMO_NETWORK` 是**首次使用即定包**（`shared/demoNetwork.ts` 的 `ensureInit()`），而 `activePack()` 现在随请求头变 —— 于是 `mock/traffic.ts:513 buildNetwork()` 可能出现「新包的 note + 旧包的 segments」；`buildVehiclesSnapshot()` 的合成车回退路径同理。本 PR 修好了 `segmentBases` 这条主线，**这两处仍是首次那个包** | 不阻塞：`getTrafficNetwork()` 的返回值在页面里没有消费方（`DashboardView.vue:203 / 333` 只赋值不读）；合成车回退要「桥接挂掉 + 现场切过包」才碰到。建议另开 Issue 收口 |
| 2 | `MapLibreViewer.vue` 声明了 `ts` prop，模板里没用（图例没用到时间戳） | 仅记录 |

**结论**：主功能（矢量底图）与两处顺带修复都验过，**可以合**；第 1 条另开 Issue 跟踪。

---

## PR !18 · fix(twin_preview): 启发式选段改按真实道路链——修掉「拿路口接头当路段」与「截断长路」

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/twin-preview-roadchain` → `main` |
| 创建 / 合并 | 2026-10-15T21:50:26+08:00 / 2026-10-15T22:42:02+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/18 |
| 正文来源 | 本机会话存档 `mcp__gitee__create_pull` |

### 正文

## 改了什么

`work/frontend/tools/twin_preview/server.py` 的启发式选段（不给 `--assignment` 时的老路子）改按**真实道路链**选段：修掉「把路口接头碎片当路段」与「把长路截断」两个问题。README 同步新口径，并修正原文写错的路名（湖滨大道 → 鼎湖大道）。

**实测症状**（改前，`/api/twin/network` 实跑）：

| 路段 | 长度 |
|---|---|
| SEG-003 站区连接线A | **3.6 m**（2 个点） |
| SEG-008 站区连接线F | **4.1 m**（2 个点） |
| …另 6 条 | 24 / 27.8 / 33.5 / 35.2 / 49.1 / 52.6 m |
| SEG-001 吉庆大道 | 607.0 m（真值 1925.7 m，**被截断**） |
| SEG-002 鼎湖大道 | 35.2 m（真值 759.8 m，**被截断**） |

全网只跨 **340 m × 600 m**，10 条"路段"里 8 条是碎片。

**病因**：原实现每个街名只取「离站最近的那一条链」，再用**离站最近的单条无街名边**补足到 `seg_count` —— 而离站最近的无街名边恰是路口接头（实测 #1 = 3.5 m、#6 = 4.0 m）；同时 `CHAIN_MAX_HOPS = 8` 把长链截断。

**改后**：

| | 改前 | 改后 |
|---|---|---|
| 最短路段 | 3.6 m | **49.1 m** |
| 中位长度 | — | **759.8 m** |
| 吉庆大道 | 607.0 m | **1925.7 m**（按里程拆 2 段） |
| 鼎湖大道 | 35.2 m | **759.8 m** |
| 全网跨度 | 340 × 600 m | **1688 × 1737 m** |

## 填表报告

- [x] **本次不涉及**填表报告（没动 `stations/*.json`、也没动表格转换脚本）

## 实现方式

- **用了什么方式**：① 可通行边拼**极大链**（跳数 8 → `CHAIN_MAX_HOPS=64`，加 `visited` 防环，候选取**转角最小**的一条）；② **每个街名只留最长的那条链**；③ 无名链按**截面键不相交**贪心去重；④ 剔掉 `< MIN_SEG_LEN_M`(30 m) 的接头碎片与超出 `STATION_RADIUS_M`(1200 m) 的链；⑤ 段数不够就把最长的段**按里程对半拆**。
- **为什么不用默认推荐**：无「默认推荐」可循 —— 这就是那份推荐做法本身的实现修复。老路子（街名 + 站房位置）的**适用边界没变**（README 仍写明：无名 / 无地理配准的网必须给 `--assignment`），改的只是它在**适用网**上的选段质量。
- **契约与判定不变的证明**：`/api/twin/network` 的 `segments[]` 字段名与形状**一字未改**（`segment_id` / `name` / `kind` / `coords`，另带原本就有的 `edge_ids` / `shape_xy` 供内部用）；段号仍是 `SEG-00N`；`kind` 仍只有 `main` / `ramp`；`select_segments()` / `pick_drop_segment()` 的**签名与返回字段未变**，`make_assignment.py` 仍直接可用（实跑 10 SEG / 31 边）。未碰 `docs/数据契约.md`。

## 怎么验证的

- [x] 本地门禁过了：`python scripts/doc_gate.py` → **7/7 全绿**（`[通过]`；第 7 组填表报告台账 `[通过]`）
- [x] **第 7 组（填表报告台账）是 `[通过]`**
- [x] 我这个模块**能单独用样例文件跑通**：`python work/frontend/tools/twin_preview/server.py` 起 8102，`GET /api/twin/network` 返 10 段
- [x] 输出 JSON **字段名 / 必填字段对照过 `docs/数据契约.md` v2.0**
- [x] **产物存在性断言**过了：`/api/twin/network` 实跑返回 10 段、`segment_id` 为 `SEG-001…SEG-010`、`coords` 非空
- [x] 同一输入连续跑 3 次，结果一致：`select_segments()` 是纯函数（同样的 `station.net.xml` + 锚点），三次输出逐字一致
- [ ] CI 已跑完且全绿 —— **本仓库不挂流水线**，门禁靠本地 `doc_gate`（已全绿）；Gitee 侧无 check

**另跑的两条定向验证**（审查发现的 4 处修正）：
1. **单边链对半拆**：`_split_chain()` 对 `edge_ids=['E1']`、长 200 m 的链，两段都拿到 `edge_ids`（修前前半段为空）。
2. **真实网回归**：10 段、`edge_ids` 无空段、落客段 `edge_ids` 非空（`run_sim` 里 `drop["edge_ids"][0]` 的路径安全）。

> 关键数字来自实跑：`最短 49.1 m / 中位 759.8 m / 最长 962.9 m`；`make_assignment.py` 输出 **10 SEG / 31 边**（无一条边被重复归属）。

## 审查记录（**必填**）

### （1）AI 预审（作者自查）

按 `docs/开发规范.md` §11 四条自检 + 门禁逐条过（**预审意见原文**）：

> ① 能单独跑通：`server.py` 起 8102 返 10 段；`make_assignment.py --net station.net.xml` 实跑通过（10 SEG / 31 边）；`py_compile server.py make_assignment.py` exit 0。
> ② 字段名对得上契约：本 PR **不产出契约文件**，只改 `/api/twin/network` 的**几何选择**；`segments[]` 仍是 `segment_id / name / kind / coords`，未增删字段、未改名。
> ③ 没改别人的目录：`git status` 只有 `work/frontend/tools/twin_preview/{server.py,README.md}`（本模块自己的目录）。
> ④ 没有 Key / 视频 / 权重：两个文件都是文本，无 `.env` / `*.mp4` / `*.ckpt`。
> ⑤ 门禁：`python scripts/doc_gate.py` **7/7 全绿**。
> 另：`docs/开发规范.md` §11 第 ② 条点名的字段名自作主张（`eta_min`→`eta` 这类）在本 PR 不适用——没有新增任何输出字段。

### （2）快速独立审查（**全新上下文，目标 ≤ 5 分钟**）

- 审查者（全新上下文，写清工具 / 模型）：**独立子代理（全新上下文，deepseek-flash）**，只读 `git diff`
- 我只提供了：改动范围（分支 `task/twin-preview-roadchain`）+ 那 4 个问题（**未提供**实现思路、可疑点、既有结论、预期结果）
- **4 问结论**（≤ 10 行；没有发现就写"4 问全过，未发现可执行问题"）：

> ① 一致：仅 `work/frontend/tools/twin_preview/{server.py,README.md}`，无夹带无关改动。
> ② 未碰契约字段 / 他人目录：返回字段仍为 `segment_id` / `name` / `kind` / `coords` / `edge_ids`，未改公共文件。
> ③ 无密钥、无大文件；但 `server.py:108` 写 3.5 m / 4.0 m 与 `server.py:309`、`README.md:66` 的 3.6 m / 4.1 m 同一改动内互相矛盾（两套"实测"数字）。
> ④ `server.py:368` `max(picked, ...)` 未防空：全网无街名、或所有无名链被 30 m/1200 m 过滤掉时 `picked` 为空 → ValueError，整条预览直接落 `state.error`，旧实现不会。
> ④ `server.py:286/293` 单边链被对半拆时前半段 `centre==mid` 不满足 `centre < hi`，前半段 `edge_ids` 为空；`pick_drop_segment()` 按 ramp 就近可能正好返回它，`server.py:491` `drop["edge_ids"][0]` → IndexError。

- **审查者原始结论原文**（贴进来，别只写"审过了"）：

> 快速独立审查 `origin/main...task/twin-preview-roadchain`（只读 diff；注意：审查期间工作树被切到 task/dashboard-openfreemap-basemap，行号取自 `git show task/twin-preview-roadchain:...` 的 blob）
> ① 一致：仅 `work/frontend/tools/twin_preview/{server.py,README.md}`，无夹带无关改动。
> ② 未碰契约字段 / 他人目录：返回字段仍为 segment_id/name/kind/coords/edge_ids，未改公共文件。
> ③ 无密钥、无大文件；但 server.py:108 写 3.5 m/4.0 m 与 server.py:309、README.md:66 的 3.6 m/4.1 m 同一改动内互相矛盾（两套"实测"数字）。
> ④ server.py:368 `longest = max(picked, ...)` 未防空：全网无街名、或所有无名链被 30 m/1200 m 过滤掉（正是文档里"无名/无地理配准的网"）时 picked 为空 → ValueError，整条预览直接落 state.error，旧实现不会。
> ④ server.py:286/293 单边链被对半拆时前半段 centre==mid 不满足 `centre < hi`，前半段 edge_ids 为空；pick_drop_segment(:413) 按 ramp 就近可能正好返回它，server.py:491 `drop["edge_ids"][0]` → IndexError。

| # | 发现 | 处置（已修 / 不改 + 理由，附文件与行号） |
|---|---|---|
| 1 | `server.py:108` 3.5 m / 4.0 m 与 `server.py:309`、`README.md:66` 的 3.6 m / 4.1 m 互相矛盾 | **已修**：统一成 API 实跑可见的 **3.6 m / 4.1 m**（`server.py:108`） |
| 2 | `server.py:368` `max(picked, ...)` 未防空 → 无名网下 `picked` 为空 → ValueError | **已修**：加 `if not picked:` + `RuntimeError`，报错里写明「这类网请改用 `--assignment <映射表>`」。**不返回空表**——下游 `pick_drop_segment()` 会对空列表 `min()` |
| 3 | `server.py:286/293` 单边链对半拆时前半段 `edge_ids` 为空 → 下游 `drop["edge_ids"][0]` IndexError | **已修**：归段判据改成以 `mid` 为界 `<` / `>=` **二分**（每条边恰好落进一段）；另加空 `edge_ids` 兜底。**已用单边链定向测试验证**（两段都非空） |

- [x] 每条发现都已处置：**成立就修；不成立就用文件与行号说明理由**
- [x] 修复**明显改变了做法**时，已换一个全新上下文再跑一次 —— 三处都是**修 bug 而非改做法**（选段口径本身没动），故未重跑第二轮独立审查

## 有没有影响别人

- [x] **没动契约字段**（`segments.json` / `routes.json` / `vehicles.json` / `render.json`）
- [x] **没改别人的目录** —— 只动 `work/frontend/tools/twin_preview/`（本模块目录）
- [x] **没动公共文件**（根 `README.md`、`.gitignore`、`.gitee/`、`docs/数据契约.md`、`app/main.py` 路由注册）
- [x] `git status` 里**没有** `.env` / 视频（`*.mp4`）/ 模型权重（`*.ckpt`）/ 图片数据集 / `node_modules/`

**如果动了契约字段，必须在这里写明**：**未动契约字段**。

> ⚠️ **对外口径**：本 PR 只改**演示工具**的选段几何。改后地图上画的仍是**示例 / 演示数据**，`is_simulated` 语义不变；**不得**据此说成实测路网或实测拥堵。

## 卡点

无。

---

- [x] **我请了 Reviewer**（`CODEOWNERS` 会自动带上；没带上就手动加）—— 已按 `CODEOWNERS` 指派
      —— **不要自己合并自己的 PR**

### 评论（1 条）

**1 · @ozxowx · 2026-10-15T22:41:40+08:00**

## 审查记录（AI 独立审查 · 2026-10-15）

**改动范围**：`work/frontend/tools/twin_preview/{server.py,README.md}`——`select_segments()` 启发式选段重写。

**怎么验的（不是只读代码，是跑对照）**：用仓库自带的 `station.net.xml` + 默认站房锚点，把 main 版与新版 `select_segments()` 载进同一进程对照跑：

- 旧版：10 段里 8 段是碎片（3.6 / 4.1 / 24 / 28 m…），最长 606 m，全网只跨 346 m × 595 m；「吉庆大道」607 m、「鼎湖大道」35 m —— 与 PR 描述的数字**一致**。
- 新版：最短 48.8 m / 中位 663.7 m / 最长 962 m，全网跨 1692 m × 1745 m；`make_assignment.py` 端到端 10 SEG / 31 边 OK。
- 同一输入连跑 3 次结果完全一致。

**发现与处置**：

| # | 发现 | 处置 |
|---|---|---|
| 1 | `_split_chain()` 里「某段拿不到边就复制整链 `edge_ids`」的兜底**会真的触发**（原注释以为只在边长全 0 时才走）：链在路口跳过 SUMO 内部边，折线长度比边长之和长（实测每跳 +9~15 m，13 条边的吉庆大道链 +169 m），于是所有边中点落进 `mid` 同一侧 → 后一段为空 → 兜底复制。实测 `--seg-count 12` 有 3 条边、`14` 有 5 条边**同时落进两个 SEG**；`edge2seg` 后写覆盖先写 → 一半路段永远收不到车 | **已修**：`360fbfe` 改成先算分界下标 `k`，两段各取 `edge_ids[:k]` / `edge_ids[k:]`（都非空、且不共享边）；单边链不拆，拆不动就换下一条 |
| 2 | README 第 4 条「剔掉 < 30 m 的碎片」写在通用规则里，实际只作用于**无名链**（命名道路一律保留，包括很短的） | 不改（命名道路保留是刻意的）；仅记录 |

**修复后复验**：`seg_count` 取 1/2/3/5/8/10/11/12/13/14/16/20/30 各跑 3 次 —— 段数达标、结果稳定、**无重复边**、无空 `edge_ids`；`make_assignment.py` 10 SEG OK；`python scripts/doc_gate.py` 全过。

**结论**：修完**可以合**。

---

## PR !17 · 文档：总纲新增 D10「一期前 · 前端完善」阶段（前端先行、不含后端）——一期范围不变

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `docs/frontend-phase-d10` → `main` |
| 创建 / 合并 | 2026-10-15T21:14:36+08:00 / 2026-10-15T22:41:56+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/17 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（1 条）

**1 · @ozxowx · 2026-10-15T22:41:40+08:00**

## 审查记录（AI 独立审查 · 2026-10-15）

**改动范围**：4 份文档（全流程计划 / 分工表 / 技术方案与实施手册 / 数据契约）——只动版本戳、裁定编号与新增 D10 段落，不含代码。

**怎么验的**：
- `python scripts/doc_gate.py` 在 `docs/frontend-phase-d10` 工作树上跑：**7 组全过**（第 7 组一条既有 `[注意]`，与 main 相同）。
- 逐条核对引用一致性：D10 → 总纲 §1 / §2.0 / §8 阶段表 F 行 / §12.1.1 第 12 条 → 分工表 §8.0.1（F1–F6）→ 手册修订表第 45 条 / §11.2 / §15.9；「修订表第 45 条」在分工表与手册两侧对得上。
- 全仓搜 `九条裁定` / `D1′–D9`：剩下的都在历史台账与「V2.1 原文」语境里，没有与 V2.2 冲突的现行口径。
- 二期内容与契约字段**未动**。

**发现与处置**：

| # | 发现 | 处置 |
|---|---|---|
| 1 | 总纲 H1 还写着 `· V2.1`，而同一份文件的版本行已升 V2.2（分工表标题、手册「文档版本」都已升）——历史台账第 382 / 386 行记过同类漏改（V2.0 → V2.1 那次是标题 / 版本行 / 第 1 节标题一起改的） | **已修**：`62b4572`，只改标题一行 |
| 2 | 提交信息写「修订表新增第 44 条」，实际新增的是第 45 条（44 已在 main 上） | 不改历史提交，仅记录；以第 45 条为准 |

**结论**：口径自洽、门禁全过，**可以合**。

---

## PR !16 · IKLLXG 大屏右栏关联告警判级取路段快照：四处收口唯一实现 + 清死代码

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/IKLLXG-alert-level` → `main` |
| 创建 / 合并 | 2026-10-15T19:25:16+08:00 / 2026-10-15T19:25:51+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/16 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（0 条）

无评论（平台 `list_comments` 返回空数组）。

---

## PR !15 · IKLLX4 表格模板实体 T1~T8 下发 + 共享盘口径收窄为「只放表格与记录」

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/43-table-templates` → `main` |
| 创建 / 合并 | 2026-10-15T18:23:05+08:00 / 2026-10-15T18:34:20+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/15 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（0 条）

无评论（平台 `list_comments` 返回空数组）。

---

## PR !14 · 孪生：肇庆东站真路网入站点包 Z（OSM 21 段 + 大屏摄像头布点，只摄像头段上色）（IKLX5Y）

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/IKLX5Y-station-z-roadmap` → `main` |
| 创建 / 合并 | 2026-10-15T15:39:18+08:00 / 2026-10-15T15:42:51+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/14 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（0 条）

无评论（平台 `list_comments` 返回空数组）。

---

## PR !13 · IKLX9B 司机端 App 前端先用单文件 HTML 顶替：站点 Z 上色 + 保留全览 + 不做生成路线

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/IKLX9B-app-html-nav` → `main` |
| 创建 / 合并 | 2026-10-15T13:53:53+08:00 / 2026-10-15T15:43:09+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/13 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（0 条）

无评论（平台 `list_comments` 返回空数组）。

---

## PR !12 · feat: 顶栏线路图切换器——选包即换路网（A/B/Y 三站）

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/topbar-network-switcher` → `main` |
| 创建 / 合并 | 2026-10-14T21:31:43+08:00 / 2026-10-14T22:49:31+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/12 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（0 条）

无评论（平台 `list_comments` 返回空数组）。

---

## PR !11 · 接口：twin_preview 桥接服务参数化——换网不再靠猜路段（#IKLOJ6 第 1 条）

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/bridge-swap-net` → `main` |
| 创建 / 合并 | 2026-10-14T19:09:01+08:00 / 2026-10-14T19:39:19+08:00 |
| 作者 | W2652201498 |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/11 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（0 条）

无评论（平台 `list_comments` 返回空数组）。

---

## PR !10 · feat: Issue IKLR30 Y型交叉口V0演示（几何→数据→大屏全链路）

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/IKLR30-y-junction-dashboard` → `main` |
| 创建 / 合并 | 2026-10-14T19:00:51+08:00 / 2026-10-14T21:18:28+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/10 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（0 条）

无评论（平台 `list_comments` 返回空数组）。

---

## PR !9 · 孪生：Y 型示意路网 + SUMO 场景全链路（演示底座，非 #IKLOB6 交付）

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/demo-y-sumo-chain` → `main` |
| 创建 / 合并 | 2026-10-14T18:58:42+08:00 / 2026-10-14T19:39:21+08:00 |
| 作者 | W2652201498 |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/9 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（1 条）

**1 · @W2652201498 · 2026-10-14T21:26:05+08:00**

## 补充：`capture_screen.py` **已经跑通了**（本 PR 正文里说"跑不通"，现在作废）

装了 XQuartz 之后，在本机**实测跑通**，14 秒出一帧：

```
[capture] 产物 frame.png：1390×714，9.2 KB
[capture] 非白占比 1.84%｜非白包围盒跨度 82%×91%
✅ 非空白，且是**路网画面**（不是窗口占位）—— sumo-gui 的真实像素拿到手了
```

### 踩出来四条，都写进脚本文档串了

| # | 坑 | 结论 |
|---|---|---|
| 1 | macOS 上 `sumo-gui` 链 `libFOX`+`libX11`，是 X11 程序 | **必须装 XQuartz**；装完 `open -a XQuartz` 即可 —— **实测不用注销重登** |
| 2 | TraCI 握手超时 40 s，卡在 `getVersion`（端口明明在 LISTEN） | ⭐ **必须给 `sumo-gui` 加 `--start`** —— GUI 默认等你在界面上点"播放"才动 |
| 3 | `Fontconfig error: Cannot load default config file` | `FONTCONFIG_PATH` 指到 `/opt/X11/etc/X11/fontconfig` |
| 4 | `traci.close()` **永远不返回** | GUI 进程不退 → 用 `os._exit(0)` 收尾 |

另两条（issue 里记的，本次一并复现）：`gui.screenshot` **必须再走一次 `simulationStep`** 文件才落盘；取景只能靠 `gui.setBoundary`。

### 一处**判据要改**（重要）

`work/assembly/技术栈.md` 那条「**458 种颜色**（非空白图）」是**在一张 OSM 大网上**量的（街名文字抗锯齿会产生几百种颜色）。
**本 Y 网只有 4 节点 / 6 边 —— 实测只有 5 种颜色**，拿"颜色种数 ≥ 30"当门槛会**把真画面误判成空白**。

本脚本改用**几何判据**：**非白像素占比 + 非白像素包围盒跨度**（实测真画面 1.8% / 82%×91%）。
**建议后续做单 3 时沿用这条**，别直接套那个颜色数。

### 但这**不等于单 3 做完了**

本件验的是**「能不能拿到 sumo-gui 的真实像素」**这个技术前提。
单 3 的**主体**（画面通道端点 + 大屏组件 + 五条件举证）**还没做**，而且它要：
① 单 1 的那张网（本件用的是 Y 型演示网）；② 单 3 的**第一步口径修订**（`assembly/README.md:60` 那句"不新增视频流/画面端点"与手册风险表第 20 条）也**还没走**。

**别把这张 PR 当成 #IKLOL9 的交付。**

---

## PR !8 · 决策：--sample 输出口径三处修正 + 登记口径两处（Issue #IKLLXT / 旧 #94）

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/94-pr82-backlog` → `main` |
| 创建 / 合并 | 2026-10-14T17:56:27+08:00 / 2026-10-14T18:39:25+08:00 |
| 作者 | W2652201498 |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/8 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（0 条）

无评论（平台 `list_comments` 返回空数组）。

---

## PR !7 · !81 大屏三栏可横向拖拽：/dashboard 主体三栏改 ElSplitter

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/81-dashboard-col-resize` → `main` |
| 创建 / 合并 | 2026-10-14T17:21:48+08:00 / 2026-10-14T17:31:45+08:00 |
| 作者 | XIXIXIXXXI |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/7 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（0 条）

无评论（平台 `list_comments` 返回空数组）。

---

## PR !6 · [接口与双端] 鸿蒙 App 拆分 A：工程骨架 + P0 四页 UI（数据用工程内 fixture，不联网）

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `task/88-harmony-app-skeleton` → `main` |
| 创建 / 合并 | 2026-10-14T15:29:11+08:00 / 2026-10-14T16:08:30+08:00 |
| 作者 | xixiu-dev2 |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/6 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（3 条）

**1 · @pull_review_bot_f98ef886cd91d5e2 · 2026-10-14T15:29:13+08:00**

|评审规则|评审内容|评审结论|完成时间|
|-|-|-|-|
|功能性与逻辑|代码是否按预期执行？有无逻辑错误或未处理的边缘情况？|❌ 未通过|2026-10-14 15:34:04|
|安全性|是否存在 SQL 注入、XSS、命令注入、敏感信息泄露等风险？|⚠️ 待优化|2026-10-14 15:34:04|
|性能|是否有明显的性能瓶颈（如循环嵌套过深、冗余查询、内存泄漏）？|⚠️ 待优化|2026-10-14 15:34:04|
|可维护性|代码是否清晰易读？注释是否充分？命名是否合理？|❌ 未通过|2026-10-14 15:34:04|


## 🤖 AI 队友审查结果
### 📊 审查结论
⛔ 发现 2 个阻断项，3 个改进项。请修改后再合并。

### 风险与影响
- **风险等级**：low  
- **潜在影响**：主要风险在于 `degraded` 状态在部分页面缺少差异化 UI 处理，可能导致验收时行为不一致（功能性影响）。颜色值分散属于可维护性问题，不影响当前功能正确性和运行时性能。整体代码质量较高，ArkUI 状态管理模式的使用正确，fixture 设计与数据契约对齐良好。

---

### 🔍 改动检查

本次 PR 实现了鸿蒙司机端 App 的工程骨架与 P0 四页 UI（Issue #88），包含推荐路线、落客候客、离站路线、我的行程四个页签。核心亮点包括：1）使用 `@Observed` + `@State` + `@ObjectLink` 组合实现跨 Tabs 页签的状态同步，解决了 ArkUI 状态管理的典型踩坑；2）所有页面数据来源于工程内 fixture（`Fixture.ts`），严格对照数据契约 v2.0，不写网络代码；3）实现了四级路况等级的「颜色+图标+文字」三重编码（`LevelMeta.ets`），并支持去色校验模式；4）设计了四个互斥演示开关（应急态/数据不可用/拒绝授权降级/去色校验），覆盖手册 §11.1(3) 和 TC-11 等关键需求。整体代码结构清晰，注释详尽，对 ArkUI 特性有深入理解。

---
### 🚫 阻断项
1. **`degraded`（拒绝授权降级）状态在部分页面未做差异化处理** (功能性与逻辑) : `work/frontend/harmony/entry/src/main/ets/pages/DropoffPage.ets`  
   - **问题描述**：DropoffPage 和 DeparturePage 的 build() 中仅判断了 `this.store.emergency` 分支，当 `store.degraded=true` 时（此时 `unavailable=false`），这两个页面会直接展示正常内容，没有任何降级提示或特殊 UI 表现。这与 RecommendPage 中对 `degraded` 状态做了专门 UI 处理不一致。由于四个开关是互斥的，当用户切换到「拒绝授权(降级)」模式时，落客候客和离站路线页面的行为与推荐路线页面不同，可能导致验收人困惑。  
   - **修正建议**：在 DropoffPage 和 DeparturePage 中也增加对 `store.degraded` 的判断分支，给出降级提示 UI，保持四页行为一致。  

2. **硬编码颜色值分散在多个文件中，缺乏统一管理** (可维护性) : `work/frontend/harmony/entry/src/main/ets/components/Common.ets`  
   - **问题描述**：大量颜色值（如 `#1A1A1A`、`#666666`、`#8B8B8B`、`#FAFAFA`、`#F5F5F5`、`#0052D9`、`#D54941` 等）以字符串字面量形式硬编码在 Index.ets、RecommendPage.ets、Common.ets、DeparturePage.ets、HistoryPage.ets、LevelMeta.ets 等多个文件中。虽然 LevelMeta.ets 内部封装了路况等级色值，但页面布局层面的通用色值（文字色、背景色、边框色等）没有集中管理。这导致后续主题调整时需要修改多处文件，容易遗漏或不一致。  
   - **修正建议**：建议在 `common/` 下新建 `Colors.ets` 模块集中定义所有复用色值常量，或在 `resources/base/element/color.json` 中补充资源定义并使用 `$r('app.color.xxx')` 引用。例如将 `#1A1A1A` 提取为 `TEXT_PRIMARY`，`#666666` 提取为 `TEXT_SECONDARY` 等，各页面统一引用。  

### ⚠️ 改进项
1. **`demoVehicle()` 函数在每次渲染时被重复调用** (性能) : `work/frontend/harmony/entry/src/main/ets/pages/RecommendPage.ets`  
   - **问题描述**：在 RecommendPage 的 build() 中，`demoVehicle()` 被调用了 4 次（分别用于 vehicle_id、segment_id、state/guided 属性）。该函数内部遍历 VEHICLES_FIXTURE.vehicles 数组查找匹配项，每次都会执行循环。虽然 VEHICLES_FIXTURE 是静态 fixture 数据且规模极小，不影响实际性能，但从代码优雅性角度，建议将结果缓存为组件成员变量或使用 @Prop/@State 传入。  
   - **修正建议**：将 demoVehicle() 的返回值提升为 RecommendPage 的成员变量，在 build 之前计算一次并缓存，避免重复调用。  

2. **EmergencyCard 组件在不同页面间存在样式不一致** (可维护性) : `work/frontend/harmony/entry/src/main/ets/components/Common.ets`  
   - **问题描述**：EmergencyCard 在 Common.ets 中被定义为红色背景卡片（`#D54941`），但在 HistoryPage.ets 中又内联编写了一个类似的应急提示条（浅红背景 `#FDECEA` + 深红文字 `#8A1F1F`），语义相同但样式不同。如果未来需要调整应急态的视觉规范，需要同时修改两处。  
   - **修正建议**：将 HistoryPage 中的应急提示条也统一使用 Common.ets 中的 EmergencyCard 组件，或将其抽象为一个更通用的 AlertBanner 组件，消除重复。  

3. **`.gitignore` 中已正确忽略敏感文件，但需确认签名文件未被意外提交** (安全性) : `.gitignore`  
   - **问题描述**：PR 已在 `.gitignore` 中添加了鸿蒙工程的敏感文件忽略规则（`*.p12`、`*.cer`、`*.p7b`、`local.properties` 等），这是正确的做法。从 diff 来看，签名相关文件确实没有被提交到仓库中，符合安全要求。无需额外操作。  
   - **修正建议**：当前处理正确，无需修改。建议在 CI 流程中增加一步检查，确保无签名文件混入提交。  



---
@xixiu-dev2 PR 审查已完成

**2 · @pull_review_bot_f98ef886cd91d5e2 · 2026-10-14T16:08:15+08:00**

|评审规则|评审内容|评审结论|完成时间|
|-|-|-|-|
|功能性与逻辑|代码是否按预期执行？有无逻辑错误或未处理的边缘情况？|❌ 未通过|2026-10-14 16:18:07|
|安全性|是否存在 SQL 注入、XSS、命令注入、敏感信息泄露等风险？|✅ 通过|2026-10-14 16:18:07|
|性能|是否有明显的性能瓶颈（如循环嵌套过深、冗余查询、内存泄漏）？|✅ 通过|2026-10-14 16:18:07|
|可维护性|代码是否清晰易读？注释是否充分？命名是否合理？|⚠️ 待优化|2026-10-14 16:18:07|


## 🤖 AI 队友审查结果
### 📊 审查结论
⛔ 发现 3 个阻断项，2 个改进项。请修改后再合并。

### 风险与影响
- **风险等级**：high  
- **潜在影响**：当前存在多处编译错误（缺失 import 和错误的装饰器用法），导致代码无法构建运行。此外，硬编码的路段数据可能导致降级模式下的功能展示不完整。修复这些问题后，代码结构清晰，状态管理符合 ArkTS 最佳实践。

---

### 🔍 改动检查

本 PR 为鸿蒙司机端 App 的工程骨架与 P0 四页 UI 实现。新增了 `work/frontend/harmony/` 目录，包含 ArkTS 源码、资源配置及构建脚本。核心变更包括：定义了符合数据契约 v2.0 的本地 Fixture 数据（`Fixture.ts`）；实现了推荐路线、落客候客、离站路线、我的行程四个页面组件；封装了通用的 UI 组件（如 `RouteCard`, `SegmentBar`, `LevelLegend`）以支持三重编码和去色校验；引入了 `DemoStore` 单例管理演示状态（应急、数据不可用、降级、去色），并通过 `@ObjectLink` 实现跨页面状态同步；更新了 `.gitignore` 和技术栈文档。

---
### 🚫 阻断项
1. **`@State` 装饰器误用于模块顶层导致编译错误** (功能性与逻辑) : ``work/frontend/harmony/entry/src/main/ets/pages/RecommendPage.ets``  
   - **问题描述**：ArkTS 的 `@State` 装饰器只能在 `@Component` struct 内部使用，当前代码将其置于文件作用域，会导致编译失败或语义失效。

```typescript
@State private demoVehicleCache: Vehicle = (() => {
  for (let i = 0; i < VEHICLES_FIXTURE.vehicles.length; i++) {
    if (VEHICLES_FIXTURE.vehicles[i].vehicle_id === DEMO_VEHICLE_ID) {
      return VEHICLES_FIXTURE.vehicles[i];
    }
  }
  return VEHICLES_FIXTURE.vehicles[0];
})()
;
```

   - **修正建议**：由于该数据源自静态 fixture 且永不变化，建议改为模块级 `const`，或在 `RecommendPage` struct 内声明。

```typescript
// 方案 A：模块级 const
const DEMO_VEHICLE: Vehicle = VEHICLES_FIXTURE.vehicles.find(
  v => v.vehicle_id === DEMO_VEHICLE_ID
) ?? VEHICLES_FIXTURE.vehicles[0];
```

2. **`RecommendPage.ets` 缺少必要的颜色常量导入** (功能性与逻辑) : ``work/frontend/harmony/entry/src/main/ets/pages/RecommendPage.ets``  
   - **问题描述**：代码中使用了 `TEXT_WHITE`、`BG_HIGHLIGHT` 和 `ACCENT_DEGRADED`，但 import 语句中未包含这些常量，将导致编译报错。

```typescript
import { TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, BG_GRAY_LIGHT, BG_GRAY_OFF, BG_GRAY_LIGHTER, ACCENT_COLOR_BLIND, BORDER_ACCENT, STATE_ADOPTED, STATE_REJECTED } from '../common/Colors';
```

   - **修正建议**：在 import 语句中补充缺失的常量。

```typescript
import { TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, TEXT_WHITE, BG_GRAY_LIGHT, BG_GRAY_OFF, BG_GRAY_LIGHTER, BG_HIGHLIGHT, ACCENT_COLOR_BLIND, ACCENT_DEGRADED, BORDER_ACCENT, STATE_ADOPTED, STATE_REJECTED } from '../common/Colors';
```

3. **`Index.ets` 缺少必要的颜色常量导入** (功能性与逻辑) : ``work/frontend/harmony/entry/src/main/ets/pages/Index.ets``  
   - **问题描述**：代码中使用了 `TEXT_PRIMARY` 和 `BG_BASE`，但 import 语句中未包含这些常量，将导致编译报错。

```typescript
import { TEXT_WHITE, ACCENT_EMERGENCY, ACCENT_UNAVAILABLE, ACCENT_DEGRADED, ACCENT_COLOR_BLIND, BG_GRAY_OFF, TEXT_TERTIARY } from '../common/Colors';
```

   - **修正建议**：在 import 语句中补充缺失的常量。

```typescript
import { TEXT_WHITE, TEXT_PRIMARY, ACCENT_EMERGENCY, ACCENT_UNAVAILABLE, ACCENT_DEGRADED, ACCENT_COLOR_BLIND, BG_GRAY_OFF, BG_BASE, TEXT_TERTIARY } from '../common/Colors';
```

### ⚠️ 改进项
1. **降级模式路段列表硬编码且与 Fixture 数据不同步** (可维护性) : ``work/frontend/harmony/entry/src/main/ets/pages/RecommendPage.ets``  
   - **问题描述**：降级模式下硬编码了 `['SEG-001', 'SEG-002', 'SEG-004']`，遗漏了 `SEGMENTS_FIXTURE` 中的 `SEG-007` 和 `SEG-009`，且硬编码易导致数据不一致。

```typescript
ForEach(['SEG-001', 'SEG-002', 'SEG-004'], (road: string) => {
  // ...
}, (road: string) => `${road}_${this.pickedRoad}`)
```

   - **修正建议**：建议从 `SEGMENTS_FIXTURE` 动态获取路段 ID，或提取为命名常量并添加注释说明筛选逻辑。

```typescript
// 从 fixture 派生，确保数据一致性
const DEGRADED_ROADS: string[] = SEGMENTS_FIXTURE.segments.map(s => s.segment_id);
ForEach(DEGRADED_ROADS, (road: string) => { ... })
```

2. **`build-profile.json5` 引用了不存在的混淆规则文件** (可维护性) : ``work/frontend/harmony/entry/build-profile.json5``  
   - **问题描述**：配置中引用了 `./obfuscation-rules.txt`，但该文件在仓库中不存在。虽然当前 `enable: false`，但在 Release 模式下启用混淆时会报错。

```json5
"files": [
  "./obfuscation-rules.txt"
]
```

   - **修正建议**：创建一个空的 `obfuscation-rules.txt` 占位文件，或在未启用混淆时移除该配置项。  



---
@xixiu-dev2 @ozxowx PR 审查已完成

**3 · @pull_review_bot_f98ef886cd91d5e2 · 2026-10-14T16:18:08+08:00**

降级模式硬编码路段列表，遗漏 SEGMENTS_FIXTURE 中的 SEG-007 和 SEG-009，并且与 fixture 数据不同步。
建议从 SEGMENTS_FIXTURE 派生路段 ID，确保口径一致。

```typescript
import { Segment } from '../common/Contract';
import { SEGMENTS_FIXTURE } from '../common/Fixture';

const DEGRADED_ROADS: string[] = SEGMENTS_FIXTURE.segments.map((s: Segment) => s.segment_id);

ForEach(DEGRADED_ROADS, (road: string) => {
  // ...
}, (road: string) => `${road}_${this.pickedRoad}`);
```

---

## PR !5 · 文档：历史台账状态校正——早期 8 条「每条线 W1」单按缺席证据判为 CLOSED

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `docs/ledger-state-fix` → `main` |
| 创建 / 合并 | 2026-10-14T11:29:28+08:00 / 2026-10-14T11:29:52+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/5 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（1 条）

**1 · @pull_review_bot_f98ef886cd91d5e2 · 2026-10-14T11:29:30+08:00**

|评审规则|评审内容|评审结论|完成时间|
|-|-|-|-|
|功能性与逻辑|代码是否按预期执行？有无逻辑错误或未处理的边缘情况？|✅ 通过|2026-10-14 11:30:34|
|安全性|是否存在 SQL 注入、XSS、命令注入、敏感信息泄露等风险？|✅ 通过|2026-10-14 11:30:34|
|性能|是否有明显的性能瓶颈（如循环嵌套过深、冗余查询、内存泄漏）？|✅ 通过|2026-10-14 11:30:34|
|可维护性|代码是否清晰易读？注释是否充分？命名是否合理？|✅ 通过|2026-10-14 11:30:34|


## 🤖 AI 队友审查结果
### 📊 审查结论
✅ 未发现问题，可以合并。

### 风险与影响
- **风险等级**：low  
- **潜在影响**：此次变更为纯文档修正，不影响代码逻辑、安全性或性能。主要影响在于提升了项目历史台账数据的准确性和可维护性，确保了迁移后状态的一致性。

---

### 🔍 改动检查

本次 PR 对 `docs/历史台账/README.md` 和 `docs/历史台账/issue-归档.md` 两个文件进行了状态校正。依据 `gh issue list` 的全量 OPEN 列表证据，将 Issue #2 至 #9 的状态从 `OPEN` 统一更新为 `CLOSED`，确保台账记录与 GitHub 实际状态一致，且未修改其他字段内容。


---
@ozxowx PR 审查已完成

---

## PR !4 · 文档：重建 GitHub 侧历史 Issue / PR 台账（39 条 Issue + 56 条 PR 的正文与评论）

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `docs/history-ledger` → `main` |
| 创建 / 合并 | 2026-10-14T11:13:28+08:00 / 2026-10-14T11:26:51+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/4 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（1 条）

**1 · @pull_review_bot_f98ef886cd91d5e2 · 2026-10-14T11:13:30+08:00**

|评审规则|评审内容|评审结论|完成时间|
|-|-|-|-|
|功能性与逻辑|代码是否按预期执行？有无逻辑错误或未处理的边缘情况？|❌ 未通过|2026-10-14 11:15:51|
|安全性|是否存在 SQL 注入、XSS、命令注入、敏感信息泄露等风险？|✅ 通过|2026-10-14 11:15:51|
|性能|是否有明显的性能瓶颈（如循环嵌套过深、冗余查询、内存泄漏）？|✅ 通过|2026-10-14 11:15:51|
|可维护性|代码是否清晰易读？注释是否充分？命名是否合理？|⚠️ 待优化|2026-10-14 11:15:51|


## 🤖 AI 队友审查结果
### 📊 审查结论
⛔ 发现 1 个阻断项，2 个改进项。请修改后再合并。

### 风险与影响
- **风险等级**：medium  
- **潜在影响**：主要影响存档的可信度与查阅效率：PR #60 的错误内容会直接误导查阅者对历史决策的理解；终端残留和不一致的占位符标记降低了文档的专业性和可读性。整体结构清晰、安全合规、链接有效，仅需修正上述局部问题即可达到高质量归档标准。

---

### 🔍 改动检查

本 PR 为纯文档变更，新增 `docs/历史台账/` 目录（3 个文件，约 8500+ 行），归档 GitHub 侧封号前重建的 39 条 Issue 与 56 条 PR 正文及评论；同步更新 `docs/仓库设置清单.md` 和根 `README.md` 的状态描述。无代码、无契约字段改动、无密钥泄露风险。


---
### 🚫 阻断项
1. **PR #60 正文内容与标题严重不符——数据完整性错误** (功能性与逻辑) : ``docs/历史台账/pr-归档.md``  
   - **问题描述**：该节标题声称是 Issue #59 的决策工作台页，但正文开头即写：

```markdown
## PR #60 · 决策层:决策工作台页 /decision……(Issue #59)

## 内容(Issue #54,感知层 = 三层前端之一)

**推翻本 PR 早期版本(SVG 假框演示层):页面数据源改为真实 YOLO 推理产物。**

### 感知演示服务(work/perception/,新增)
```

这是 **PR #56/#64（感知层检测画面页）** 的内容被错误关联到了 PR #60 下。  
   - **修正建议**：核实 PR #60 的实际正文并替换；若确实无法恢复，应在该节显式标注「⚠️ 原文未正确恢复，当前内容为 PR #56 误植」，并在 README 索引表里修正来源字段。

```markdown
## PR #60 · 决策层:决策工作台页 /decision……(Issue #59)

> ⚠️ 原文未正确恢复，当前内容为 PR #56 误植。请核实后替换或补充实际正文。
```

### ⚠️ 改进项
1. **PR #20 中嵌入了终端输出残留** (可维护性) : ``docs/历史台账/pr-归档.md``  
   - **问题描述**：在 PR #20 的 `## Bug Fixes:` 段之后出现一行不属于原始内容的文本：

```text
Shell cwd was reset to （本机路径已隐去）
```

这是会话重建时意外捕获的终端状态信息，混入正文后会误导读者以为是原始 PR 描述的一部分。  
   - **修正建议**：删除该行终端输出残留。

```markdown
<!-- 已删除 'Shell cwd was reset to （本机路径已隐去）' -->
```

2. **未填写审查栏位的标记不一致** (可维护性) : ``docs/历史台账/pr-归档.md``  
   - **问题描述**：多个条目存在空缺审查记录，但标记方式不统一：PR #24 使用 `<待填>`（HTML 标签形式），PR #63 使用纯文本 `待填` / `待兜底审`，PR #90 整段留空。`<待填>` 在 Markdown 渲染时会被当作未知 HTML 标签吞掉或原样显示，与其他条目的纯文本风格不一致，降低可读性。

```markdown
### （1）AI 预审（作者自查）

- 预审意见原文：<待填>

### （2）快速独立审查（全新上下文，目标 ≤ 5 分钟）

- 审查者（全新上下文，写清工具 / 模型）：待填
```

   - **修正建议**：统一为一种显式标记，例如 `（原文未填写——行内审查意见不可恢复）`，与 README 顶部的口径声明呼应。

```markdown
### （1）AI 预审（作者自查）

- 预审意见原文：（原文未填写——行内审查意见不可恢复）

### （2）快速独立审查（全新上下文，目标 ≤ 5 分钟）

- 审查者（全新上下文，写清工具 / 模型）：（原文未填写——行内审查意见不可恢复）
```



---
@ozxowx PR 审查已完成

---

## PR !3 · 设置清单补记：成员清理 / 保护规则实测值 / 历史重写全过程（含临时摘保护的操作记录）

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `docs/settings-after-rewrite` → `main` |
| 创建 / 合并 | 2026-10-14T09:59:27+08:00 / 2026-10-14T10:00:34+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/3 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（0 条）

无评论（平台 `list_comments` 返回空数组）。

---

## PR !2 · 去掉流水线（ci）+ 切断外部仓库依赖：门禁改本地跑，仓库自包含

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `chore/no-ci-no-upstream` → `main` |
| 创建 / 合并 | 2026-10-14T09:35:56+08:00 / 2026-10-14T09:37:13+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/2 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（1 条）

**1 · @pull_review_bot_f98ef886cd91d5e2 · 2026-10-14T09:35:58+08:00**

|评审规则|评审内容|评审结论|完成时间|
|-|-|-|-|
|数据契约字段一致性检测|审查新增或改动的 JSON 字段名是否遵守已冻结的《数据契约.md》——...|✅ 通过|2026-10-14 09:39:07|
|跨目录导入禁令检测|检查是否存在跨目录的 Python import（如 work/engi...|✅ 通过|2026-10-14 09:39:07|
|硬编码站点信息检测|审查引擎代码中是否出现具体站点名、坐标、路名的硬编码字符串。站点差异应全...|✅ 通过|2026-10-14 09:39:07|
|密钥与敏感文件泄露检测|扫描改动中是否有高德/百度 Key 等地图凭证的直接字面量、.env 文...|✅ 通过|2026-10-14 09:39:07|
|外部依赖升级检测|若 PR 涉及 requirements-mindspore.txt 或...|✅ 通过|2026-10-14 09:39:07|
|魔法数字与待标定阈值检测|审查判级/决策算法中的常量是否被提取为 UPPER_SNAKE_CASE...|✅ 通过|2026-10-14 09:39:07|
|子进程调用安全审计|对使用 subprocess.run() 调用外部工具（如 SUMO n...|✅ 通过|2026-10-14 09:39:07|
|UTF-8 与 LF 编码...|检查新增/修改的 Python 和文本文件中读写 JSON 时是否显式指...|✅ 通过|2026-10-14 09:39:07|
|输出可复现性与确定性检测|审查核心算法逻辑（判级、推荐、仿真主循环）是否具备确定性和可回放性——同...|⚠️ 待优化|2026-10-14 09:39:07|
|表驱动配置文件完整性检测|审查 stations/ 目录下配置文件的生成方式是否正确——应由表格（...|✅ 通过|2026-10-14 09:39:07|


## 🤖 AI 队友审查结果
### 📊 审查结论
⚠️ 无阻断项，但发现 1 个改进建议，可优化后合并。

### 风险与影响
- **风险等级**：low  
- **潜在影响**：低风险。本 PR 主要影响开发流程纪律（门禁从平台强制变为本地自觉），对代码正确性无实质改变；`dump_monitor_data.py` 的参数化改动向后兼容，默认值命中时行为与原脚本一致；文档口径变更不涉及运行时逻辑，但需确保团队成员知悉新门禁流程以避免提交未过检的 PR。

---

### 🔍 改动检查

本 PR 按业主裁定落地三项变更：① 删除 `.gitee/workflows/ci.yml`，取消平台流水线，门禁改为本地跑 `python scripts/doc_gate.py`；② 切断外部仓库依赖，将 `dump_monitor_data.py` 中硬编码的 `UPSTREAM_CORE` 路径参数化为 `--detector-root` CLI 参数并增加目录校验报错逻辑；③ 全仓约 18 个文档文件同步更新口径，将 CI 检查名 `ci` 相关表述统一替换为本地门禁说明，保留历史留档（`SOURCE.md`、`现状核实.md`）并加注不再作为依赖。契约字段 `ci`（拥挤指数）正确保留不动。


---
### ⚠️ 改进项
1. **`_load_detector()` 内 `# noqa: E402` 注释已无实际作用** (输出可复现性与确定性检测) : `work/perception/tools/dump_monitor_data.py`  
   - **问题描述**：函数体内的 import 语句不会触发 flake8 的 E402 规则（该规则仅检测模块级非 import 语句之后的 import），保留 `# noqa: E402` 会给后续维护者造成此处曾有 lint 问题的误解。

```python
from core.mindspore_detector import MindSporeDetector  
# noqa: E402
    from core.tracker import ByteTracker  
# noqa: E402
```

   - **修正建议**：移除函数体内两处多余的 `# noqa: E402` 注释，保持代码整洁且避免误导。

```python
from core.mindspore_detector import MindSporeDetector
    from core.tracker import ByteTracker
```



---
@ozxowx PR 审查已完成

---

## PR !1 · 仓库迁到 Gitee：历史搬迁 + 模板/流水线配置改写 + 设置清单重写（迁移落地单）

| 项 | 值 |
|---|---|
| 状态 | merged |
| 源 → 目标 | `chore/migrate-to-gitee` → `main` |
| 创建 / 合并 | 2026-10-14T07:59:10+08:00 / 2026-10-14T08:03:04+08:00 |
| 作者 | ozxowx |
| 链接 | https://gitee.com/ozxowx/hubflow/pulls/1 |
| 正文来源 | 本机无记录 |

### 正文

本机无记录。

本机会话存档里没有这条 PR 的 `create_pull` / `update_pull` 调用记录 —— 该 PR 的正文原文没有留在本机；平台接口 `get_pull_detail` 不返回 body，Gitee 网页也读不到，故无从照录。**不代为拟稿。**

### 评论（0 条）

无评论（平台 `list_comments` 返回空数组）。
