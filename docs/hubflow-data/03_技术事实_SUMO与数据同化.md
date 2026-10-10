# SUMO 技术事实与数据同化（一期孪生线）

> 性质：**技术事实文档**。覆盖：OSM→SUMO 转换、虚拟检测器、`<calibrator>` 数据同化、TraCI 控制面、许可与版本、K 最短路实现。
> 版本：v1.0（2026-10-10）。基准版本：**SUMO 1.28.0**（2026-10-08 发布；上一稳定版 1.27.1）。
> 来源以官方文档 sumo.dlr.de 为准，源码级事实已标注。

---

## 1. OSM → SUMO 转换（netconvert）

### 1.1 官方推荐命令

```bash
netconvert --osm-files map.osm.xml -o map.net.xml \
  --geometry.remove --ramps.guess --junctions.join \
  --tls.guess-signals --tls.discard-simple --tls.join \
  --tls.default-type actuated
```

要点（官方文档）：`--geometry.remove` 简化网络；`--ramps.guess` 猜测加减速车道；`--junctions.join` 合并交叉口簇；tls 组修正信号语义；`--tls.default-type actuated` 避免静态配时表现差。**左行国家加 `--lefthand`。**

关键默认值：`--junctions.join-dist 10`、`--tls.guess-signals.dist 25`、`--tls.green.time 31`；`--ramps.guess`/`--junctions.join`/`--tls.guess-signals` 默认均 false。

### 1.2 bbox 提取（含版本坑）

- 推荐：`osmGet.py --bbox <W,S,E,N> --prefix <NAME>` → `osmBuild.py --osm-file <NAME>.osm.xml`
- **bbox 顺序坑**：当前源码为 `west,south,east,north`（minLon,minLat,maxLon,maxLat），历史文档/邮件列表曾写 `north,south,west,east`——**以本机 `--help` 为准**；或改用 `osmconvert -b=lon,lat,...`（顺序在官方页有明文）
- 只要高速：`osmosis --way-key-value keyValueList="highway.motorway,highway.motorway_link" --used-node`

### 1.3 已知坑与处理

| 坑 | 处理 |
|---|---|
| 匝道缺失（OSM 不标 accel/decel） | `--ramps.guess` |
| 路口被拆碎/形状怪 | `--junctions.join`（复杂簇需手工核对）；`--junctions.join-exclude` 排除误合并 |
| 信号缺失/位置错 | `--tls.guess-signals`（猜测 id 前缀 `GS_`）；清 OSM 自带信号用 `--osm.discard-tls` 后 `.nod.xml` 补 |
| 铁路/步行道混入 | `--remove-edges.by-vclass rail_slow,rail_fast,bicycle,pedestrian`；`--keep-edges.by-vclass passenger` |
| 车道数不对 | 无官方 FAQ 专条；ScenarioGuide 四种修正法：plain-xml 重建 / netconvert patch / netedit 手改 / NetDiff |
| typemap 缺 | `osmBuild.py --type-file`；**显式指定 typemap 会丢默认值**，需叠加 `osmNetconvert.typ.xml` |
| 二次加载 .edg.xml 报 type 错 | `--ignore-errors.edge-type` |

**Patch 兜底**（官方确认）：`netconvert --sumo-net-file mynet.net.xml --edg-files patch.edg.xml -o fixed.net.xml`，可改 numLanes/speed/allow/connections，`<connection reset="true"/>` 重置、`<delete id/>` 删边。

## 2. 虚拟检测器选型

| 类型 | 形态 | 适用 | 关键字段 |
|---|---|---|---|
| **E1 inductionLoop** | 单 lane + pos（点） | **断面过车统计（本项目选它）** | nVehContrib（完全通过）、flow（外推小时流）、occupancy、speed、harmonicMeanSpeed、nVehEntered |
| E2 laneAreaDetector | lane/lanes + 区段 | 排队长度、占有率、延误 | nVehEntered/nVehLeft、meanSpeed、meanTimeLoss、jamLength 系列——**无 flow/nVehContrib** |
| E3 entryExit | 进口-出口对 | 行程时间、区间速度 | meanTravelTime、vehicleSum |

**结论**：断面断面统计用 E1（每断面每 lane 一个）；count 用 `nVehContrib`（完全通过）或 `nVehEntered`（触到即计）；E2 覆盖整幅断面时流量需自己换算；**勿用 E3 做过车统计**。

## 3. `<calibrator>` 数据同化（核心）

### 3.1 定义与属性（官方文档逐字核对）

挂在 **edge 或 lane 二选一**（"Either edge or lane must be specified"）：

| 属性 | 含义 |
|---|---|
| id / edge / lane | 标识与挂载位置 |
| pos | **当前被忽略**（issue #1331） |
| period (freq) | 校准尝试间隔；默认 step-length；**设大值会限制可达最大流** |
| routeProbe | 从该 probe 取路线分布 |
| **jamThreshold** | 均值速度低于 `FLOAT × speedLimit` 视为"异常拥堵"并清车；范围 [0,1]，默认 0.5（meso 0.8） |
| output | 校准统计输出文件（schema 无官方文档，见风险） |
| vTypes | 参与计数/移除的车型；默认 "" 全部 |

`flow` 子元素：须给 `vehsPerHour` 或 `speed`（或组合）；edge calibrator 默认 `departLane='free'`、`departSpeed='max'`。

### 3.2 工作原理

逐字："A calibrator will remove vehicles in excess of the specified flow and it will insert new vehicles ... if the normal traffic demand ... does not meet the specified number of vehsPerHour."——**流量少了补车、多了删车**；速度按指定值调整（类似 variableSpeedSign）；并清"异常拥堵"。

**jamThreshold 源码语义**（MSCalibrator.cpp 核对）：车道车辆 <4 不计；`meanSpeed < threshold × speedLimit` 且**剩余容量不足 1 辆**才判定 invalid jam 并清车——它是"清车开关"而非"定义堵"，**默认 0.5 即可，勿设太小**。

### 3.3 TraCI 接口

```python
import traci
traci.start(["sumo", "-c", "sim.sumocfg", "--additional-files", "calib.add.xml"])

# 更新校准区间（参数序：id, begin, end, vehsPerHour, speed, typeID, routeID, departLane, departSpeed）
traci.calibrator.setFlow("calibtest_edge", 0, 3600, 2500.0, 27.8, "t0", "c1", "free", "max")

# 对账三件套
passed   = traci.calibrator.getPassed("calibtest_edge")    # 本区间通过数
inserted = traci.calibrator.getInserted("calibtest_edge")  # 插入数
removed  = traci.calibrator.getRemoved("calibtest_edge")   # 移除数
```

- **在线文档与 pydoc 不一致**：Change_Calibrator_State 页只列 `setFlow`；pydoc 有全套 getter（getPassed/getInserted/getRemoved/getVehsPerHour/getSpeed…）
- **无 `setSpeed`**：纯改速度只能重发 `setFlow` 且 `vehsPerHour < 0`（源码 `calibrateFlow = q >= 0` 推论，**需实测确认**）
- 示例 XML：

```xml
<additional>
  <calibrator id="calib_boundary_north" edge="E_boundary_N" pos="0" output="calib_out.xml">
    <flow begin="0" end="1800" route="route_r1" vehsPerHour="2500" speed="27.8"
          type="car" departPos="free" departSpeed="max"/>
  </calibrator>
</additional>
```

### 3.4 降级备选

- `<variableSpeedSign>`：只能限速、不能补删车——calibrator 失效时流量同化退化为"只限速+需求文件灌流"
- TraCI 车辆级手工注入（最灵活、最重）

### 3.5 已知限制（有出处）

- `pos` 被忽略（issue #1331）→ 断面精确定位靠"把断面 edge 拆短/单独设边"
- `period > 1` 曾在 1.26.0 前异常（#6589，已修）；变道瞬间被移除的车可能计入他 lane 致计数波动
- 1.25.0 GUI 建 flow 回归（#17399）；meso 不支持 type calibration
- 拥堵时插不进车 → `departSpeed="max"`、`departLane="free"/"random"` 排障

### 3.6 对 HubFlow 设计的关键推论

**calibrator 会"删掉超出目标流量的车"→ 站内（有自生成需求的路段）布 calibrator 会与站内车流互相打架。**
因此「边界断面灌、站内不灌」的既定方案在技术上是**必须**：calibrator 只放边界/进口 edge；站内断面只放 E1（纯观测、无干预）。

## 4. TraCI 车辆控制面

### 4.1 路线重指派三件套

| 方法 | 语义 | 适用 |
|---|---|---|
| `setRoute(vehID, edgeList)` | 直接给边序列（首边=当前边）；**车辆在路口内时改路线无效** | 施加 K 条候选路线（强制改道） |
| `setRouteID(vehID, routeID)` | 按已命名路线切换（须从当前边开始） | 路线库/多方案切换 |
| `rerouteTraveltime(vehID, currentTravelTimes=True)` | 按当前通行时间重算到原终点 | 阻抗变化后的重规划 |

辅助：`getRoute/getRouteID/getRouteIndex/isRouteValid`；`moveToXY` 强制位姿（keepRoute 位掩码）。

### 4.2 插入控制（关键参数）

- `traci.vehicle.add(vehID, routeID, typeID, depart, departLane, departPos, departSpeed, ...)`
- **无 setDepartSpeed/setDepartLane**——插入参数只能走 `add`
- `departLane`：`first`（默认最右）/`random`/`free`（最空）/`allowed`/`best`/索引；`departSpeed`：默认 0 / `max`/`desired`/`speedLimit`/`random`/数值
- **边界灌流必须 `departSpeed="max"` + `departLane="free"`**，否则默认 0 速度拖慢断面流率

### 4.3 存档/恢复

- `traci.simulation.saveState(FILE)` / `loadState(FILE)`（快载，保留网络与 additional）
- 限制：**flow 车辆可能不在状态里**（"Vehicles from an incrementally loaded route file as well as flow-vehicles may be missing"）——用 `<vehicle>/<trip>` + `--additional-files` 非增量加载可保证完整；`--save-state.rng` **平台相关（Windows/Linux 不互通）**；加载后订阅需重建
- 版本坑：1.16/1.17 有 `traci.load` 回归记录

## 5. 许可与版本

### 5.1 EPL-2.0 商用要点（对闭源演示系统）

- `src/` 与 `tools/`（除 foreign/contributed）自 r26300 (2017-10-03) 起 **EPL-2.0 或 GPL-2.0-or-later**；数据文件默认 EPL-2.0（3D 资产 CC0、OSM 测试输入 ODbL）
- EPL-2.0 正文明确 "**intended to facilitate the commercial use**"→ 允许商用
- 分发义务：保留声明、提供 SUMO（含改动文件）源码或获取途径、附 EPL 文本
- **工程结论：以独立进程 + TraCI 通信集成，不修改/不静态链接源码，闭源演示系统合规无碍**；修改过的 SUMO 源码再分发需按 EPL 提供该文件源码
- **Windows "all extras" 安装含 GPL 代码，商用集成分发应避开**

### 5.2 版本锁定建议

- 当前稳定 1.28.0（发布仅 2 天，2026-10-08）；**保守建议锁 1.27.1（2026-06-25）**，或锁 1.28.0 的 pip 三件套同版本
- pip：`eclipse-sumo` / `traci` / `libsumo` / `sumolib` 同号发布；requirements 锁 `traci==1.28.0`
- Windows 安装：.msi / zip；winget 可用（仅 latest）

## 6. K 最短路径实现

### 6.1 networkx（推荐实现路径）

- **没有 `k_shortest_paths` 函数**（官方文档只有 recipe）；真正函数 `nx.shortest_simple_paths(G, s, t, weight)`——generator、Yen 算法，"first K paths requires O(KN³)"；不支持 Multi(Di)Graph

```python
from itertools import islice
import networkx as nx

def k_shortest_paths(G, source, target, k, weight=None):
    return list(islice(nx.shortest_simple_paths(G, source, target, weight=weight), k))

cands = k_shortest_paths(G, "gate_north", "zone_central", k=3, weight="traveltime")
```

- 站前规模（N 数百、K=3~5）实际耗时毫秒~百毫秒级，**可行**；风险在 N 上千且 K 大时（公开 benchmark：COL 网络 k=300 时 Yen 约 80s）
- 策略：K 严格 ≤5、bbox 裁剪后建图、generator + islice 不 list 全展开

### 6.2 SUMO 自带 alternatives

```bash
duarouter -n station.net.xml -r trips.xml -o routes.rou.xml \
  --alternatives-output routes.rou.alt.xml --max-alternatives 5 \
  --routing-algorithm dijkstra
```

- 产出 `.rou.alt.xml`（每车 `<routeDistribution>`，带 cost/probability）
- **不是严格 K 短路**：DUA 迭代语义、上限 5（默认）、不保证边互异
- 工程结论：**精确可解释的 K 条候选用 networkx Yen 生成 →校验连通→写入 routes 或 `setRoute` 施加**；duarouter alternatives 作"流量分配式"对照

## 7. 技术风险清单

**需实测/读源码兜底**：
1. calibrator `pos` 被忽略（#1331 未修）→ 断面定位靠拆边
2. calibrator 输出文件无官方 schema → 监控走 TraCI getter
3. TraCI calibrator 在线文档与 pydoc 不一致 → 以 pydoc+源码为准
4. 「只改速度不改流量」（setFlow + vehsPerHour<0）无明文 → **1.28.0 实测确认**
5. netconvert 车道/匝道错误无官方 FAQ → ScenarioGuide 四法兜底
6. `osmGet.py` bbox 顺序历史文档矛盾 → 以本机 --help 为准
7. duarouter alternatives 生成算法无文档 → 不作精确 K 短路用
8. E2 无 flow 字段，勿误用

**升级回归项**：校准器 period 行为（1.26.0 修）、saveState 平台相关、OSM 导入行为逐版变动（**升级 SUMO 必须重跑 netconvert + NetDiff**）。

**转换质量兜底组合**：osmGet/osmconvert 裁剪 → netconvert 推荐选项 + vclass 过滤 → plain-xml patch/netedit 二次修正 → netcheck + sumo-gui 连接检查。

## 8. 来源汇总

官方文档：OpenStreetMap 导入 / netconvert / PlainXML / ScenarioGuide / FAQ / E1 / E2 / E3 / Calibrator / Change_Calibrator_State / Change_Vehicle_State / SaveAndLoad / Variable_Speed_Signs / Vehicles / duarouter / DUA / Libraries_Licenses / Downloads / ChangeLog（均 sumo.dlr.de）
pydoc：https://sumo.dlr.de/pydoc/traci/_calibrator.html ；源码：tools/osmGet.py、tools/traci/_calibrator.py、src/microsim/trigger/MSCalibrator.cpp
issues：#1331、#6589、#17399；networkx：shortest_simple_paths 文档页
