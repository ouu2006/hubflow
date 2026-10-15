# 评审资料 · Issue #88 / Gitee #IKLLXL（拆分 A · 前端 UI）

> 本文件是提PR 时的评审入口。评审请按「一、完成判定逐条对照」→「二、本轮修了什么」→「三、自查与门禁」→「四、口径自查」→「五、已知限制」的顺序看。
> 所有截图均为**模拟器实跑画面**（Pura 90 / HarmonyOS 6.1.1 / API 24），非界面原型，见 `work/frontend/harmony/.evidence/`。

---

## 一、完成判定逐条对照

| 判定项 | 落点 | 举证 |
|---|---|---|
| **C-3四页**①推荐路线 | `pages/RecommendPage.ets` | `.evidence/01-推荐路线.jpg` |
| C-3 四页②落客候客 | `pages/DropoffPage.ets` | `.evidence/02-落客候客.jpg` |
| C-3 四页③离站路线 | `pages/DeparturePage.ets` | `.evidence/11-离站选路.jpg` |
| C-3 四页④我的行程 | `pages/HistoryPage.ets` | `.evidence/04-我的行程.jpg` |
| **TC-12** `departure_route` 必现 | `DeparturePage` 离站路线 P-5 + 告知文案| `.evidence/03-离站路线.jpg` |
| **TC-11** 数据不可用显示灰色、**绝非蓝色** | `StateTopBar.ets:120` 灰蓝条 `#5A6570` | `.evidence/07-数据不可用.jpg`（像素：灰条270010 / 红 443） |
| **手册 §11.1(3)** 应急态停止引导→「请服从现场指挥」 | `StateTopBar` + `NavBar` + `Common.EmergencyCard` + `RoadNetMap.stopGuidance` | `.evidence/06-应急态.jpg`、`06b-应急态-落客页.jpg` |
| **TC-05（App 侧）** 拒绝授权降级、**流程不中断** | `DegradedBanner.ets`（**只叠加不删正文**） | `.evidence/08-拒绝授权降级.jpg` |
| **手册 §11.3** 三重编码（色+图标+文字） | `LevelMeta.ets` 四级 `○◇▲■` + `LevelChip`/`LevelLegend` | `.evidence/05b-去色校验.jpg` |
| **M1-7** 角标必现 | `Index.ets` 四页固定底部 | 全部截图 |
| 不联网/ 不改契约 / 不加字段 | 数据全读 `Fixture.ts`（逐字取契约 v2.0） | `grep` 无网络代码 |

---

## 二、本轮修了什么（提交前自查发现并修完的问题）

这一批是**评审最容易挑出来的类型**，逐条列出修法与举证，便于复核。

### A. 口径类（撞条款）

| # | 问题 | 修法 | 举证 |
|---|---|---|---|
| 1 | **数据不可用时地图把路段画成蓝色**（`levelColor` 对 `level<1` 返回导航蓝 `#0D5FB4`），与图例「数据不可用」自相矛盾，且撞 TC-11 | 统一返回 `C_CLOSED` 灰，与 `LevelMeta.UNAVAILABLE_META` 同源 | `SelfDrawRenderer.ets:339` |
| 2 | 应急态下**落客页/离站页地图仍在画推荐路线**，而导航页因 `navMode` 被置空走了空分支 —— 四态语义自相矛盾 | 新增 `RoadNetMap.stopGuidance` prop，组件内 `blank \|\| stopGuidance`；三页统一传 `store.emergency` | 像素：常态路线蓝 23167 → 应急 5772（差额即页头标签） |

### B. 功能正确性类

| # | 问题 | 修法 |
|---|---|---|
| 3 | **离站转向序列与地图几何反向**：`REAL_MANEUVER_MARKS` 按到站标定，离站几何 `ROUTE_D1` 是它的反向，导致离站导航第一个转向显示「出发」而车标落在终点 | `buildManeuvers(segments, isDeparture)`：反转顺序 + 里程改`total - d` + **首尾 type 对调** |
| 4 | 离站导航文案全错：显示「到达落客点 / 进入 站前路 / DROP-03」 | `maneuverText(type, isDeparture)` 按场景出词；`toRoad` 离站用「离站通道」；导航页 `dropLabel` 离站用「离站出口」 |
| 5 | **离站地图画出一条到站备选路线**（`buildPlanRoute(p, false)` 写死 false） | 改传 `isDeparture` |
| 6 | 「X米后」实现与注释声明的公式不一致（减的是 `passedMeters()` 而非当前转向里程），巡航中会算出「0 米后」 | 统一为 `list[cur+1].distM - list[cur].distM`，并对 `cur` 做 `Math.max(0,...)` 夹紧防越界 |
| 7 | 应急/不可用态点已选卡片**仍会跳转到导航页**（`switchTab` 未拦） | `DropoffPage.onActivate` 首行加 `routeLocked()` 守卫，与卡片点击守卫对齐 |
| 8 | App 退后台后 40ms 巡航定时器**不停**（单例不随页面销毁），切回来时车已跑了一段 | `EntryAbility.onBackground()` 调 `stopCruise()` |
| 9 | 离站方案切到 P-1 后，地图角标仍写死「P-5 离站」 | 改 `dropLabel: \`${this.plan().pathId} 离站\`` |
| 10 | 离站页 `ForEach` 缓存键**漏了 `routeLocked()`**，开应急后卡片可能不变灰 | 键补 `_${routeLocked()}` |
| 11 | 降级态「手动确认所在道路」直读`arrival_route.segments`，离站导航时列的仍是到站路段 | 改读 `pickedSegments()`，与地图/卡片/图例同源 |
| 12 | 渲染后端**每帧 `new` 一个**（巡航 40ms 一帧）且 `dispose()` 从不调用 | 实例缓存复用 + `aboutToDisappear` 统一 `dispose()` |

### C. 代码卫生类（评审会点名「死代码/重复定义」）

| # | 问题 | 修法 |
|---|---|---|
| 13 | `YRouteMap.ets` **413 行里约 380 行零引用**（真实路网早已改用 `RealNet`），只有两个字符串映射函数还被用着—— 评审翻代码会误判「Y 字路线还在生效」 | 两个映射函数迁到新建 `ManeuverMeta.ets`，**整份 `YRouteMap.ets` 删除** |
| 14 | 慢速系数 `1.0/0.6/0.35/0.2` **两处逐字重复**，任一处漏改就出现「车在畅通段飞驰、导航条说这段要 3 分钟」 | 提取为 `LevelMeta.levelSpeedFactorOf()`，三处共用 |
| 15 | `RoutePlan` 内**函数中声明箭头函数**，与同文件自己的规范注释直接冲突（`arkts-no-nested-funcs`） | 随14 一并消除 |
| 16 | 零引用导出/方法：`carPoint`、`carPointAtRatio`、`advanceNav`、`advanceManeuver`、`retreatManeuver`、`restartManeuver`、`realManeuvers`、`REAL_ORIGIN_LNG/LAT`、`MAP_BACKEND_AMAP/OSM`、`markKindOf`、`forceRepaint`、`remainCount`、`distToNext`、`maneuverIndex` prop | 全部删除。**其中 `carPoint` 带着 20 行注释论证「车标里程=转向点里程」，而实际车标早已改由 `driveRatio` 插值驱动 —— 属「注释与实现不符」的高风险残留** |
| 17 | 两处 `if (true) { ... }` 恒真残留（为规避大段重排留下的临时代码） | 去壳，块内语句上提 |
| 18 | `degrade()` 未覆盖四级等级的 `textColor`，漏登记的颜色会**原样保留彩色** | 一并匹配 `textColor`，并给`return c` 兜底加注释说明其为非语义色 |
| 19 | 过时注释指向已删对象（`Y_MANEUVERS`、`carPoint`、`restartManeuver`、`RoutePlan.carPoint`） | 全部改正或改为解释「为什么不再这样」 |

---

## 三、自查与门禁

```bash
# 门禁一：前端专项（11 项，本次新增/改写 3 条规则）
python scripts/frontend_gate.py          # → 11/11 全绿
# 门禁二：文档与契约（7 项，仓库既有）
python scripts/doc_gate.py               # → 全部通过
```

**构建**：DevEco Studio 6.1.1/ hvigorw 6.24.5 / SDK 6.1.1(API 24)
`hvigorw --mode module -p module=entry@default assembleHap` → **BUILD SUCCESSFUL，零 error 零 warning**

**门禁规则随代码同步修正**（不是放水，是规则本身在检查已不存在的代码）：
- 第 11 项原要求 `RoadNetMap` 有 `maneuverIndex` 入参 —— 车标早已改由 `driveRatio` 插值驱动，该 prop 已删；
- 第 11 项原校验 `advanceManeuver/retreatManeuver/restartManeuver` 三个方法 —— 全部零调用已删，底部按钮走 `startCruise`/`restartNav`；
- 第 2 项未使用 import 检查真实生效（清掉了 `RealNet` 的 `Maneuver`）。

---

## 四、口径自查（红线逐条）

| 红线 | 状态 |
|---|---|
| 用户可见文案不出现「实测 / 实时 / 现场」 | ✅ 全量 grep：命中项**全部在注释里**；唯一用户可见的「现场」是手册 §11.1(3) 固定措辞「请服从现场指挥」 |
| `is_simulated` 恒 `true` | ✅ 全部 15 处均为 true，页头明示 |
| 位置来源标「一期孪生真值，**非真实定位**」 | ✅ `RecommendPage:345` |
| 不声称已接入真实定位 | ✅ 全工程无此类表述 |
| 不改契约、不加字段 | ✅ 全部字段名逐字对照契约 v2.0 |
| 提示只**叠加**、绝不删正文 | ✅ 门禁第 9 项专盯；应急/降级/不可用均只加提示条 |
| 地图条款（不引地图 SDK、不落盘） | ✅ 一期自绘 OSM 路网图，`createRenderer()` 一行换档位 |

---

## 五、已知限制（如实写）

1. **仅模拟器验证，未上真机**（Pura 90 / API 24）。W4 判定以模拟器跑起来为准。
2. **数据源是工程内 fixture**，不联网、不申请权限 —— 真实接口由 #89 数据接驳单接管，**页面结构不动**。
3. **离站只有两条路线**：契约 `departure_route` 没有 `alternatives` 字段，只给了一条离站主选 P-5；备选从系统 `alternatives` 取一条合法路径（P-1）。**宁少不多** —— 多画一条等于编造契约里不存在的路线。等后端给 departure 的 alternatives 才能补第三条，这不是漏做，是数据边界。
4. **`pickup_route` 一期为 null**（D1 送客场景无接客路线），页面不展示该项。
5. **未做真机 GPS 定位**，位置来源标注为孪生真值。