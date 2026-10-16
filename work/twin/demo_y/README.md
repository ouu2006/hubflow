# Y 型演示路网

> **这是什么**：一个**凭空造的示意路网**（形状是一个 **Y**——一条主干 + 在交汇点分出的两条臂），
> 用来把「**路网 → 导入 SUMO → 场景跑通**」这条链立起来。
>
> **两条几何纪律（照抄仓库口径，别松）**：
> 1. **不做地理配准** —— 坐标是**占位锚点**，图上任何一点都**不是真实地点**；
> 2. **不是真实数据的地图** —— 对外物料一律按「演示数据（模拟）」标注。
>
> ⚠️ **与 `work/twin/netbuild.py` 的关系**：那个脚本走的是「**OSM 真路网**」管线（`netconvert` 转真实切片，
> 产出 `stations/sumo/*.net.xml`）；本目录是「**凭空造的示意路网**」。**两者并列、互不覆盖**，口径完全不同，别混。

## 一键复现

```bash
export SUMO_HOME=<SUMO 安装根目录>      # 该目录下应有 bin/ 与 tools/；缺了会报可操作的错，不静默跳过

python3 build_network.py                # ① 建网：自绘 nod/edg/con → netconvert → network/demo_y.net.xml
python3 build_scenario.py               # ② 出车流 + 跑 SUMO → out/fcd.xml / out/tripinfo.xml
python3 draw_network.py                 # ③ 画线路图 → figures/*.png（深色演示版 / 打印版）
python3 build_scenario.py --demand-scale 5   # 峰值工况（需求 ×5）
python3 build_network.py --clean        # 删掉产物重建（验证"一键重建"）
```

## 路网长什么样

```
n_stem ──────────── n_junction ──┬── n_arm_a
                                 └── n_arm_b
```

| 边 | 走向 | 车道 | 限速 |
|---|---|---|---|
| `e_stem_in` / `e_stem_out` | `n_stem` ↔ `n_junction` | 2 | 60 km/h |
| `e_arm_a_in` / `e_arm_a_out` | `n_junction` ↔ `n_arm_a` | 2 | 50 km/h |
| `e_arm_b_in` / `e_arm_b_out` | `n_junction` ↔ `n_arm_b` | 2 | 50 km/h |

**每个方向各一条边**（共 6 条）——单向性靠"有没有反向边"表达，不设 `oneway` 字段。
交汇点是**三岔口**：主干进来可拐向任一条臂，两条臂都汇回主干。

## 场景

4 类车流，区间 `0–600 s`，**随机种子写进 `sim/demo_y.sumocfg`**（`<random_number><seed value="42"/>`，**不读系统时间**）：

| 车流 | 路线 | 基础发车率 |
|---|---|---|
| `flow_stem_to_a` | `e_stem_in e_arm_a_in` | 600 辆/h |
| `flow_stem_to_b` | `e_stem_in e_arm_b_in` | 600 辆/h |
| `flow_a_to_stem` | `e_arm_a_out e_stem_out` | 400 辆/h |
| `flow_b_to_stem` | `e_arm_b_out e_stem_out` | 400 辆/h |

## 产物分层（**按仓库口径**）

| 进仓库（小文本） | 不进仓库（大件） |
|---|---|
| `network/*.nod.xml` / `.edg.xml` / `.con.xml` / `.net.xml`（9 KB） | `out/fcd.xml`（4 MB；倍率 5 时上百 MB） |
| `sim/*.rou.xml` / `*.sumocfg` | `out/tripinfo.xml` |
| `figures/*.png`（47 KB） | 任何 `.mp4` / 动画 |

`.gitignore` 已拦 `out/`。

## 怎么验（**别只信退出码**）

| 验什么 | 判据 |
|---|---|
| **一键重建** | `build_network.py --clean` 跑两遍，`network/demo_y.net.xml` **逐字节一致** |
| **场景可复现** | `build_scenario.py --clean` 跑两遍，`out/fcd.xml` 与 `out/tripinfo.xml` **逐字节一致**（含 4 MB 那个） |
| **产物真的落盘** | `tripinfo.xml` 必须以 `</tripinfos>` 收尾 —— **没收尾就是跑到一半被中断的半成品**，不认 |
| **无本机路径** | `grep -nE "D:\\\\\|/Users/"` 在脚本里**零命中**（SUMO 位置只认 `SUMO_HOME`） |

### 两个必须知道的坑：SUMO 会往产物里写「时间戳」和「本机路径」

`netconvert` / `sumo` **每次**都会：

1. 往产物**第一行**写 `<!-- generated on <时间> by Eclipse SUMO ... -->` ——
   不处理的话，"重跑"**必然**产生一条毫无意义的时间戳 diff；
2. `netconvert` 还会往 `.net.xml` 里回显一个 **`<netconvertConfiguration>` 块**，
   里面**按本机绝对路径**写了输入的 `.nod/.edg/.con.xml` 与输出路径 ——
   产物**换台机器或换个目录就不一致**，而且**把本机目录泄进仓库**（仓库明写"本机具体目录不写入团队文档"）。

`sumo_common.py` 的两个函数分别处理这两件事（`--keep-timestamp` 可关）：

| 函数 | 做什么 | 为什么不算"手改生成物" |
|---|---|---|
| `strip_sumo_timestamp()` | 抹掉首行注释里的时间 | **不碰任何内容**；要改产物请改输入后重跑 |
| `strip_local_paths()` | 删掉 `<netconvertConfiguration>` 回显块 | 那是**选项回显**，SUMO 运行时不读；实测删后仿真照跑（280 次行程不变） |

**这是「删掉产物能一键重建」这条能立住的前提** —— 不处理这两样，产物永远不可能逐字节一致。

## 已知限制

1. **`capture_screen.py` 依赖 XQuartz（macOS）** —— `sumo-gui` 在 macOS 上链的是 `libFOX` + `libX11`，
   是 **X11 程序**。不装 XQuartz 会报 `FXApp::openDisplay: unable to open display :0.0`。
   **装好后的用法**（实测**不用注销重登**）：

   ```bash
   brew install --cask xquartz      # 要管理员密码
   open -a XQuartz                   # 起 X 服务
   export DISPLAY=:0
   python3 capture_screen.py
   ```

   **另有三条实测坑**（都写进 `capture_screen.py` 的文档串了）：**必须给 `sumo-gui` 加 `--start`**
   （否则 GUI 等你在界面上点"播放"，TraCI 端口在听却不回话）；`FONTCONFIG_PATH` 要指到
   `/opt/X11/etc/X11/fontconfig`；**`traci.close()` 会永远卡住**（GUI 进程不退），得用 `os._exit`。
2. **`draw_network.py` 是「画」不是「截」** —— 它读 `.net.xml` 自己画示意图，
   **不能替代** sumo-gui 的真实画面（那是另一件事）。两张图别混。
3. **非空白判据用「几何」不用「数颜色」** —— `work/assembly/技术栈.md` 那条「458 种颜色」是在一张
   **OSM 大网**上量的；**本 Y 网只有 4 节点 / 6 边，实测只有 5 种颜色**，拿"颜色种数 ≥ 30"当门槛会
   **误判成空白**。`capture_screen.py` 改用**非白像素占比 + 包围盒跨度**（实测真画面：1.8% / 82%×91%）。
