# work/verify · 箭头标向验收（L1 / L2 / L3）

> 对应方案：[docs/方案-路段箭头方向-20261029.md](../../docs/方案-路段箭头方向-20261029.md) §4「三层确认箭头标向」。
> 本目录只放**验收证据**，不改任何实现代码。写盘范围见文末 §7。
> **一页结论**：[箭头标向-验收报告.md](箭头标向-验收报告.md)（11 条判据逐条通过/不通过 + 三个证据源交叉 + 盲区 + 复跑命令）；
> 本 README 是它的证据手册（怎么复现、每个数字怎么来的）。

## 0. 交付物与状态

| 层 | 交付物 | 谁产出 | 状态 |
|---|---|---|---|
| L1 | `work/engine/tools/audit_segment_direction.py` 的断言输出（`work/engine/tools/out/segment_direction_audit*.json`） | 开发A | ✅ 已落地（Z 16/16、GZ 15/15 全 PASS，见 §4） |
| L2 | `work/verify/direction_snapshot.json`（61 段逐段标向数值快照） | 本目录（开发C） | ✅ 已生成（§2） |
| L3-a | `work/verify/direction_sheet.svg`（19 面板真值图版） | 本目录（开发C） | ✅ 已生成（§3） |
| L3-b | 五档视口截图 + 逐段像素测量（`work/verify/measure_summary.json`、`shots/**`）+ 叠加复核图 + 跨档一致性 | 本目录（开发C） | ✅ 已跑（§5.3）；两项"矮容器"缺陷**已由开发B 修好并复测**（§5.4） |
| L3-c | 离站回程三方对照（静态方向层 / 路线箭头 / 后端 steps 几何） | 本目录（开发C） | ✅ 已跑（§5.5，`departure_check.json`） |
| P1/P2 | 路线箭头权威化 + `/route/plan` trim 口径 + 起点标记口径 | 本目录（开发C） | ✅ 已跑（§6，12/12 与 28/28） |

一句话结论：真网 61 段里 **14 条 `direction="reverse"`**，其 `coords` 与行车方向相反；
图版上彩线（行进序）与灰线（coords 序）**几何重合、顺序相反**，箭头锥尖全部指向 `to_node` —— 这就是业主所说
「起点标在段另一端 / 箭头很乱」的机器侧画像。

前端这一层实测**已对齐**：五档视口（1280×720 / 1440×900 / 1920×1080 / 2560×1440 / 375×812）下箭头中心与路段弧长中点偏差
**≤0.068 px**、`icon-rotate` 与独立算的行进方位角差 **≤0.0002°**、跨档像素偏移 **spread = 0.0 px**，
且没有任何随视口变化的偏移量（`icon-offset = null`）。
曾经"某些窗口下看不见箭头"的两项（1280×720 抛 `Invalid LngLat (NaN,-90)`、1440/375 自然取景 zoom 掉到 13.0~13.5 低于淡出阈）
**已由开发B 修好**：进站取景加 `minZoom = DIR_ZOOM_FULL(15.5)`，五档自然取景现在全部 ≥15.5、方向层 61/61（375 档 57，4 条在视野外）可见 —— 修前/修后见 §5.4。

## 0.1 本轮修了什么 / 没修什么（业主先看这一节）

一轮下来，箭头这件事被拆成"已经改好的"和"明确不改、留档的"两堆。**改好的都在证据里，没改的都不该被当成"已修"。**

| ✅ 修了（有证据） | ❌ 没修 / 明确不做（原因） |
|---|---|
| **箭头中间化**：方向标记锚点 = 路段**弧长中点**（`pointAtFraction(coords, 0.5)`），不再按 `offset_m` 贴到端点 → §5.3、`measure_summary.json` 逐段 `d_pos_px ≤ 0.068` | **进站 zoom 淡出**：1440×900 / 375×812 自然取景只到 zoom **13.02 / 13.49**，低于淡出阈 15.0 ⇒ 方向箭头**全透明**（业主在小屏/窗口化时"看不见箭头"的直接原因）。**已交 dev-B**，修法 = 进站 `fitBounds` 加 `minZoom` = `DIR_ZOOM_FULL`(15.5)；本目录只记档不动代码 → §5.4-b |
| **随段缩放**：`icon-size` 为 zoom 插值表达式（14.5→半个基准，15.5→基准，22→基准），不再用 `icon-offset` / 固定像素去"对位置" → §5.3 `icon_size_at_zoom` | **双向段画一支双头箭头**，而不是两支方向相反的箭头分开画（`DIR_BIDIR_MIN_LEN_M = 25` 以下退化为中点圆点）。UI 取舍，非标向错误；图纸上给两支仅作**示意**，不代表 UI 会画两支 |
| **路线箭头跟 steps**：路线箭头几何改吃 `GET /api/traffic/route/{request_id}/steps` 的 `steps[].geometry`（行进序），不再靠"链式首尾相接"猜方向 → §6 P1 | **SZ-052（16.3 m）不画箭头**：低于 `DIR_BIDIR_MIN_LEN_M = 25`（图纸口径 30 m）下限，短到画上去就是糊一团。阈值取舍，已记档 |
| **起点标记位置**：`offset_m` 先经 `coords_offset_to_travel` 折算再取点，28 例与后端 `start_point.lon/lat` 偏差 **≤0.55 m** → §6 P2 | |
| **trim 口径**：`steps[].trim_head_m / trim_tail_m` 不再头尾互换（12/12 例 PASS，逐段 ≤0.10 m） → §6 P2 | |
| **`icon-offset` 删掉**：方向层不再挂 `icon-offset`（那是"同一箭头在不同分辨率下差几像素"的来源），改由 `icon-size` 表达式 + 中点锚点负责 → §5.3 `iconOffset: null` | |
| **`originByConnectivity` 只在反向投影用**：仅在 `direction === "reverse"` 的边重建时按连通性定起点，不再对所有边普适套用 | |

> 一句话给业主：**"箭头乱"这一条已修完并有五档视口数字背书；"某些窗口下看不见箭头"这一条也已修好并复测通过**
> ——根因是地图容器太矮导致进站取景 zoom 掉到淡出阈以下（1280×720 还会抛 `NaN`），开发B 修后五档自然取景全部 ≥15.5、方向层 61/61 可见，
> 修前/修后同视口对比图见 §5.4（`work/verify/before_after_1440x900.png`、`before_after_375x812.png`）。

## 1. 复现（全部命令在仓库根 `D:/hubflow/_arrows` 下执行）

> **写盘铁律（CRLF 坑，白跑过两轮）**：本目录所有脚本输出文本一律 `newline="\n"`，否则 `scripts/doc_gate.py` 判死；**提交前必须跑 `python scripts/doc_gate.py`**。
> 根因：Windows 上 `pathlib.write_text()` 默认文本模式会把 `\n` 翻成 `\r\n`，而门禁按 LF 校验。

```bash
# L2 + L3 一起生成（纯标准库，不依赖后端接口改造进度）
python scripts/verify_arrow_direction.py

# 只打印抽样清单与自检统计（不改盘）
python scripts/verify_arrow_direction.py --list

# L2 判定：重新生成并与仓库里的快照逐字节比对，diff 为空才算方向没被改错
python scripts/verify_arrow_direction.py --check

# 图纸覆盖全部 61 段（默认只画 14 条反向段 + 5 条双向段 = 19 面板）
python scripts/verify_arrow_direction.py --all
```

退出码：`0` = 全部自检通过；`1` = 有断言失败（逐条打印段 id）；`2` = 入参/来源文件问题。

数据来源（脚本自动择一，优先 enriched）：
`work/twin/netpack/network_junction.enriched.json` → 缺则退回 `work/twin/netpack/network_junction.json`。
快照里记了 `source` 与 `source_sha256`，**换源会被 diff 抓到**。

## 2. L2 · 数值快照 `direction_snapshot.json`

### 2.1 每段字段

| 字段 | 含义 |
|---|---|
| `from` / `to` | netpack 产物里的节点名（几何口径；`coords[0]` 恒等于 `from` 坐标，脚本断言） |
| `travel_from` / `travel_to` | **行进口径**的端点；`reverse` 时与 `from`/`to` 互换（适配层重建边用的就是这一口径） |
| `direction` | `forward` / `reverse` / `bidirectional` |
| `oneway` / `kind` / `boundary` | 原始 OSM 属性透传，便于回溯 |
| `length_m` | 段长（米）；`length_m_calc` 是按 coords 反算的弦长，用于交叉核对 |
| `bearing_coords_order` | 50% 弧长点处、沿 **coords 顺序**的局部切线方位角（正北 0，顺时针） |
| `bearing_travel` | 同一点处、沿**行进顺序**的方位角；`reverse` 段应等于前值 +180° |
| `midpoint_coords_order` / `midpoint_travel` | 两个口径的中点经纬度（`reverse` 段两者相同，`bidirectional` 同） |

`_meta` 里另记：`counts`、`reverse_segments` 清单、`coincident_opposite_pairs`、`reverse_subgraph`
（反向段端点连通性）、`reverse_count_note`（结论文字）、`definitions`、`tolerances`。

**为什么可 diff**：键排序固定、小数位固定（bearing 1 位 / length 1 位 / lonlat 7 位）、**不写时间戳**。
任何一条段的 `direction` 或端点被改错 → `--check` 逐段打印「旧 vs 新」并退出 1。

### 2.2 当前摘要（实测）

| 项 | 值 |
|---|---|
| site / 段数 | 肇庆东站 / 61 段 |
| `counts` | `reverse` **14** · `bidirectional` **33** · `forward` **14** |
| reverse 组成 | **SZ-001 ~ SZ-013 连续 13 条 + SZ-061**（`SZ-014` 是 `forward`，不在这 14 条里） |
| reverse 端点连通性 | 只用这 14 条构图 → **1 个连通分量 / 15 个节点**（N-001…N-040 子集） |
| reverse 里程 | **1468.6 m**，占全站 4593.6 m 的 **32.0%** |
| 对向重合对 | `SZ-013` ↔ `SZ-060`（`opposite_segment_id` 相互指认、几何重合、同为 27.6 m；`SZ-060` 是 `forward`） |

**这条观测值得写进结论**：14 条反向段不是散布的孤例，端点连成一整片（1 个连通分量），
覆盖全站 32% 的里程 —— 所以前端看到的不是「几个箭头歪了」，而是**一整片道路的箭头同时朝反方向**，
这正是业主「箭头很乱、很难分辨对不对」的观感来源。

> 口径备注：若适配层把 `SZ-013`/`SZ-060` 这对合并成一条双向边，`reverse` 会记 13 条；
> 验收按 **14 条全量核对**（快照取的是 enriched 产物里的 `direction` 原值）。

### 2.3 SZ-004 逐字段样例（方案 §1.1 的举例段）

```json
{"from":"N-022","to":"N-040","travel_from":"N-040","travel_to":"N-022",
 "direction":"reverse","length_m":120.7,
 "bearing_coords_order":120.1,"bearing_travel":300.1}
```

读法：几何 from→to 是 N-022→N-040（方位 120.1°，东南），**行车方向是 N-040→N-022**（300.1°，西北）；
两者相差 180°，`coords` 仍是 N-022→N-040 的原始顺序 —— 前端按 `coords` 顺序解释 `offset_m`
就会把起点镜像到段另一端（相距恰好 120.7 m = 整段长度）。

## 3. L3 · 图版 `direction_sheet.svg`

一张 SVG（1280 宽，北向上，右上指北针）。左侧/下侧每面板自带比例尺与 `1 m = x px`。

| 图元 | 含义 |
|---|---|
| 灰线 | `coords` 顺序（netpack 文件里的几何顺序），两端标 `from` / `to` 节点名 |
| 彩线 | 行进顺序（`reverse` 反向），沿线 3 个箭头，**锥尖朝 to_node**；两端标 `起点` / `终点` |
| 空心红圈 | 行进终点（锥尖指向的那一端） |
| 面板标题行 | 段号 + `direction` + 段长，第二行给两个方位角（coords 序 / 行进） |

判定只看两件事：① 箭头锥尖朝 to_node；② 彩线与灰线在同一几何上的相对位置一致、差异只在「顺序」。

覆盖：**A 段 = 全部 14 条 `reverse`（全量，不抽样）**；B 段 = 抽样 5 条 `bidirectional`；共 19 面板。
`--all` 可扩到 61 段全量。

> ⚠ **双向段的图版口径 ≠ UI 口径**：图纸为看清两个方向，在 40%/60% 弧长各画一支箭头；
> **UI 实际渲染是一支双头箭头，落在 0.5 弧长点、零横向偏移**（开发B 定案：本包 13 段双向段只有
> 16.3~19.2 m，两支 34px 图标必然重叠；且 `icon-offset` 是屏幕空间偏移，做不到真法向）。
> 验收双向段以 UI 口径为准，**别拿两支去对图**。

### 3.0 为什么"兜底会指反"会变成**用户可见**的错误（关键一环）

同一份代码里，两个图层的箭头字形是不一样的：

- **路线箭头 = 单头**：`work/frontend/ui-vue/src/views/dashboard/components/MapLibreViewer.vue:924-955`
  `routeArrowIconImage()` 只画一个 `tipY`（锥尖在 canvas 顶端）。**单头箭头指哪边，用户就信哪边。**
- **方向层双向段 = 双头**：同文件 `:698-745` `paintArrowGlyph(..., double = true)`，两头都有锥尖，
  所以双向段"画反"在视觉上**看不出来**（也正因如此，双向段的方向只能靠 steps 几何证，见 §5.5）。

于是当"权威来源"缺失时，前端会走兜底 `orientByConnectivity()`
（`work/frontend/ui-vue/src/shared/routeArrows.ts:93-168`）——靠端点连通性猜朝向；
而双向段的 `segments[]` 里**不带 `edge_id`**（分不清 `SZ-036` 与 `SZ-036_rev`），猜错就画出一支**单头**箭头指向反方向。
**这不是"看不出来"，是明确指反。** 这也是本轮把路线箭头改为吃 `steps[].geometry`（行进序）的原因：
只要后端给了行进序几何，前端就不需要猜。

### 3.1 转成 PNG 看（可选，便于评审查阅）

```bash
# 方式一：LibreOffice（仓库外依赖，本机已装）
soffice --headless --convert-to png --outdir work/verify/_render work/verify/direction_sheet.svg

# 方式二：Edge headless（按 SVG 原生像素，2x 更清晰）
"/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" --headless=new \
  --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
  --window-size=1280,<SVG高度> \
  --screenshot=work/verify/_render/full2x.png \
  "file:///D:/hubflow/_arrows/work/verify/direction_sheet.svg"
```

`_render/` 是**中间产物目录，不进证据链**（可随时删）。

## 4. L1 · 开发A 的自检（回填位）

- 脚本：**`work/engine/tools/audit_segment_direction.py`**（原先误记在 `work/backend/tools/`，
  仓库无 `work/backend/` 目录，已按 lead 纠偏更正）
- 复现：`python work/engine/tools/audit_segment_direction.py`（全跑，写报告到 `work/engine/tools/out/`）
- 报的口径：A 行进序几何端点 · B 段级方向计数（reverse 14 / bidirectional 33 / forward 14 / 共 61）·
  C 折算互逆 · D reverse 段 `offset_m=0` 起点 == `coords[0]` · E `steps` 链首尾相接 ·
  F `Σsteps.length - trim ≈ routes.length` · G `snap` 回显口径
- **L1 验收结论：✅ 通过（两站点全 PASS，实测于 12:10 / 12:18 的报告）**
  - `zhaoqingdong`：**16/16 通过**，`work/engine/tools/out/segment_direction_audit.json`（`ok: true`，`failed: 0`）
  - `guangzhounan`：**15/15 通过**，`work/engine/tools/out/segment_direction_audit_gz.json`（708 段：forward 297 / reverse 367 / bidirectional 44）
  - 关键断言实测值（Z 站）：A 94 条遍历边几何首末点最大偏差 **0.0000 m**；
    B reverse 段号集合 == SZ-001…SZ-013 + SZ-061（14 条、编号不连续，多出/少了均空）；
    C 141 个取样点折算往返误差 **2.84e-14 m**；D 12/12 段 `start_point == coords[0]` 偏差 **0.000 m**；
    E 24 条路线 steps 链最大断口 **0.0000 m**。
  - ⚠ **盲区（照实记）**：D 组对 Z 站只覆盖 **12/14** 条 reverse 段，跳过 `SZ-001@N-038`、`SZ-003@N-001`
    （起点节点无出边，无法构造 `offset_m=0` 的算路）；这两段的起点标记指向由我在 L3 端用
    `pointAtOffset` 独立复核（`work/verify/start_marker_probe.json`，28/28 例最大偏差 0.55 m），
    并非漏验，只是换了一条证据链。

> 已消项：该脚本 docstring「用法」段原写 `work/backend/tools/audit_segment_direction.py`（仓库无该目录），
> 开发A 已改；现在照文档跑得通。

## 5. 多档视口截图与像素测量（1280×720 / 1440×900 / 1920×1080 / 2560×1440 / 375×812 五档已跑，结果见 5.3）

### 5.1 起服务（**本工作树自己的实例**，两个坑先看）

> ⚠ 坑1 · 端口被主工作树占着：本机 `:5173` / `:8000` / `:8101` 现在跑的是
> **`D:\hubflow\hubflow`（主工作树）**的 vite / traffic.py / perception（`psutil` 查到的 cwd 就是主树，
> 且 vite 参数是 `--mode remote`）。**拿它们截图等于验收主树代码，不是 `task/route-arrow-redo-20261029`**。
> 所以 _arrows 必须用**错开的端口**起自己的一套（下面用 8001 / 5373），或先确认主树服务已停。
>
> ⚠ 坑2 · 默认 `npm run dev` 是 **mock 模式**（`.env` 里没有 `VITE_USE_MOCK`，vite.config.ts 里
> `useMock = env.VITE_USE_MOCK !== '0'` → 为真），走的是 `src/mock` 中间件，
> **方向层数据不是真后端的**。验收必须 `dev:remote`（`.env.remote`：`VITE_USE_MOCK=0`、`/api → :8000`）。

```bash
# ① 接口层（错开端口，:8001）
python work/assembly/traffic.py --port 8001
#   就绪判据：GET http://127.0.0.1:8001/api/traffic/meta 返回 200

# ② 前端：remote 模式（真后端），端口错开 + 代理指向 8001
cd work/frontend/ui-vue
VITE_DEV_PORT=5373 VITE_API_BASE=http://127.0.0.1:8001 npm run dev:remote
#   页面：http://127.0.0.1:5373/dashboard   （方向层所在页面 = 监控大屏 DashboardView）
#   判据：页面数据来自真后端（非 mock）——Network 面板里 /api/traffic/meta 命中 8001
```

> `work/frontend/ui-vue/node_modules` 在本工作树里是**指向主树 node_modules 的软链**（不起第二个安装），
> 起 dev 前确认软链在：`ls -ld work/frontend/ui-vue/node_modules`。

### 5.2 怎么截、怎么量（不是裸 `--screenshot`）

裸 `msedge --screenshot` 干不了这件事，两个原因：
① 它截的是"当前这一帧"，而 `queryRenderedFeatures` 是**按相机现算**的 —— 相机刚 `jumpTo` 完就能查到要素，
   但画布还没重绘，截出来是空白（我第一次就截到过没有箭头的图，见下面「坑 · 空白帧」）；
② 「偏差 <1px」只能靠 `map.project()` 把经纬度换成 CSS 像素来算，肉眼看 PNG 给不出 1px 的结论。

所以用 CDP 驱动（`work/verify/cdp_measure.mjs` + `_measure_body.js` + `_page_lib.js`）：

```bash
# 五档，一档一次（每档 100~200 s；--skip-rotated / --skip-clean 可减 pass）
node work/verify/cdp_measure.mjs --width 1280 --height 720
node work/verify/cdp_measure.mjs --width 1440 --height 900
node work/verify/cdp_measure.mjs --width 1920 --height 1080
node work/verify/cdp_measure.mjs --width 2560 --height 1440
node work/verify/cdp_measure.mjs --width 375  --height 812      # 手机竖屏兜底档

# 叠加图：把我独立算出的「行进方向」画回截图，给眼睛复核（20 段，2x 放大）
python work/verify/_overlay_check.py 2560x1440

# 汇总（逐档条件 + 逐段数字 + 跨档一致性）
python work/verify/summarize_measure.py
python work/verify/pixel_vs_projection.py

# 离站回程三方对照（静态方向层 / 路线箭头 / 后端 steps 几何，判据分「单向段」与「双向段」两类）
python work/verify/verify_departure_arrows.py
```

每档产出（`work/verify/shots/<WxH>/`）：

| 文件 | 内容 |
|---|---|
| `direction-pinned.png`（2560 档为 `.jpg`，quality 88） | 钉死 `center = 站点包几何中位数`、`zoom = 16.2`（同相机换视口才可比）——**唯一跟图的全景**，业主看的是这一张 |
| `measure.json` | 逐段数值：`arrow_px`、`mid_px`、`d_pos_px`、`rotate_data`、`expected_rotate_deg`、`d_rotate_deg`、`px_poly`、`containerRect`、`layout`（icon-size/offset/anchor/rotation-alignment 实取值） |

> 体积策略：`direction-natural.png` / `direction-rotated.png` / `direction-clean.png` 是**过程产物**，
> 它们能说明的数都已在 `measure.json` 里，按 lead 要求不跟图（重跑命令会把这三张写回来，提交前删掉）。
> 逐段 61 段的量尺聚合在 `work/verify/measure_summary.json`。
> 现跟图的只有五张全景（1280/1440/1920/2560/375 各一）+ 叠加复核图 `arrow_overlay_check.png` + 离站回程图 `shots/shot_departure_1440.png`
> + `shots/shot_station_1440.png` + 两张修前/修后对比 `before_after_*.png`。
> **提交前实测体积：`work/verify` = 6.00 MB / 85 个文件 / 10 张 png（+1 张 2560 档 jpg）**（lead 限 ≤6 MB）。
> 2560×1440 那张转 `quality=88` 的 jpg 是 lead 批准的瘦身手段，分辨率信息仍在图上（可看出是 2560×1440）。
> `measure.json` 里 `clean` pass 只留计数（其 `rows`/`layerDump` 已删）—— 那是"关层差值"路线的基线，墨迹法已废弃（见 §6.1-2）。

判据怎么算（每段独立重算，不复用前端代码）：

- `d_pos_px` = |方向层要素坐标的屏幕位置 − 我按**弧长 50%** 自己插值出来的中点|（两者都过 `map.project()`；
  平面近似按 `cos(lat0)` 修正经度）。
- `d_rotate_deg` = |图层 `icon-rotate` 的实测数据 − 我按 `coords` 顺序独立算出的**行进**方位角|；
  `forward` = 切线方位，`backward`(reverse) = 切线 +180°，双向短段(<25 m) = 0。
  另给 `d_screen_bearing_deg`（扣掉地图 `bearing` 后比屏幕向量）。
- 箭头**锥尖**朝向 = 图标画法（`paintArrowGlyph` 把锥尖画在 canvas 顶端）× `icon-rotate`；
  所以把 `icon-rotate` 量准，再用 `arrow_overlay_check.png` 眼睛复核。

> ⚠ 坑 · 空白帧：截图前必须等一次 `map.once('idle')` + 400 ms。**不要**用 `requestAnimationFrame`——
> headless 里页面不可见时 rAF 可能一直不触发，会把 `awaitPromise` 挂死（我这版挂过一次，被 `timeout` 杀掉）。
>
> ⚠ 坑 · 容器原点：`map.project()` 给的是**容器内**坐标，截整页图时要加 `containerRect`。
> 第一版裁图没加，局部图整体偏 (325, 245)，一度误以为"箭头不在中点"——数值一直是对的。

### 5.3 五档结果（实测，`work/verify/measure_summary.json`）

> **五档各自的作用**：1440×900 / 1920×1080 / 2560×1440 是**目标设备档**（笔记本窗口 / 1080p / 1440p 全屏）；
> 1280×720 是**最小可用桌面档**（曾抛 `NaN`，修好后回归）；**375×812 不是目标设备**，它是**"最小容器"边界样本**——
> 用来反证"箭头落点与视口大小无关"这条结论在极端小容器下依然成立，不为手机竖屏背书。
> 每档的测试条件（viewport / canvas / zoom / center）在 `measure_summary.json` 的 `conditions` 里逐档写明，`pixel_vs_projection.json` 的
> `viewports[vp].viewport/canvas/zoom/center` 同义；不翻代码就能知道"这 0.047 px 是在什么条件下测的"。

| 视口 | 地图画布 | 自然取景 zoom | 方向层实测可见（`queryRenderedFeatures`） | 落点偏差 max `d_pos_px`（natural / pinned） | 锥尖偏差 max `d_rotate_deg` | 北偏 30° 档 | 结论 |
|---|---|---|---|---|---|---|---|
| 1280×720 | 562×164 | **15.50** | **61/61** | **0.046 / 0.047 px** | **0.0002°** | 0.047 px / 0.0002° | ✅ 通过（修前抛 `NaN`，见 5.4-a） |
| 1440×900 | 698×221 | **15.50** | **61/61** | **0.056 / 0.047 px** | **0.0002°** | 0.047 px / 0.0002° | ✅ 通过（修前 zoom 13.02 全透明，见 5.4-b） |
| 1920×1080 | 1174×488 | **15.76** | **61/61** | **0.066 / 0.047 px** | **0.0002°** | 0.047 px / 0.0002° | ✅ 通过 |
| 2560×1440 | 1811×848 | **16.73** | **61/61** | **0.068 / 0.047 px** | **0.0002°** | 0.047 px / 0.0002° | ✅ 通过 |
| 375×812 | 357×243 | **15.50** | **57/61**（4 条落在视野外，不是"看不见"） | **0.056 / 0.047 px** | **0.0002°** | 0.047 px / 0.0002° | ✅ 通过（边界样本） |

- 61 个要素按类型：`forward` 14 / `backward`(reverse) 14 / `bidirectional` 33 —— 与 L2 快照逐类一致。
- `icon-size` / `icon-offset` / `icon-anchor` / `icon-rotation-alignment` 五档实测**完全相同**
  （`icon-offset = null`、`icon-anchor = null`（默认 center）、`icon-rotation-alignment = map`、
  `icon-size` 是 zoom 插值表达式）—— 即**没有任何随视口变化的偏移量**。
- 跨档一致性（`work/verify/pixel_vs_projection.json`）：相机钉成同 zoom/center 后，同一段箭头相对画布中心的
  偏移在五档里**逐像素相同**（spread = **0.0 px**，限 1 px）；逐段 `ratio = 实测弧长比例 / 0.5` 的跨档 spread
  也是 **0.0**。业主说的"分辨率不同会错位"，在箭头图层这一层已经不存在：偏差是 0.05 px 量级的浮点噪声。
- `arrow_to_chord_mid_px` 最大 99~143 px 属**正常**：弧长中点 ≠ 弦中点（弯道必然不同），
  所以判据用弧长中点，别拿弦中点当基准。
- 眼睛复核：`work/verify/arrow_overlay_check.png`（20 段、2x 放大；青线 = 独立投影的折线，
  黄箭头 = 独立算的行进方向，红十字 = 图标实测中心，白圈 = 弧长中点）——
  14 条 reverse 段的棕色箭头与黄箭头同向，红十字与白圈重合。

### 5.4 两处「矮地图容器」缺陷：修前 / 修后（已由开发B 修好并复测）

这两项都不是箭头标向算错，而是**地图容器太矮 → 进站取景落到极远 zoom**，于是箭头要么不画、要么全透明。
开发B 修好后本目录复测通过，修前证据与修后数字一起记档。

#### 5.4-a 1280×720 进站取景抛 `Invalid LngLat (NaN,-90)`（修前 → 已修）

修前（本目录 11:5x 实测，`shots/1280x720/measure.json` 的 `consoleLog`）：

```
[exception] Error: Invalid LngLat object: (NaN, -90)
  at lngLatFromWorld → cameraForBoxAndBearing → cameraForBounds
  at flyToStation (src/shared/mapMotion.ts)  ← runCameraSync (MapLibreViewer.vue)
```

- 现象：进站后相机停在 `center≈[108.5056, 26.4362] zoom≈0.2481`（全国视野），方向层 `rendered = 0` —— 数据在、画面在几千公里外。
- 算术原因：`stationPadding()` 的竖直留白 = 顶 `36+20+settle` + 底 `36+28+settle` = **120 + 2·settle px**；
  1280×720 实测地图容器只有 **562×164**，留白吃掉全部高度 → 可视框退化为负值 → MapLibre unproject 出 `(NaN, -90)`。
- 修法（开发B，`src/shared/mapMotion.ts`）：`fitStationCamera()` 给 `fitBounds` 加 **`minZoom = DIR_ZOOM_FULL`(15.5)**，
  并加 `isUsableCamera()` 守卫，把算出来是 `NaN`/非有限的相机帧直接丢弃（不再喂给 `flyToStation`）；
  方向层 zoom 常量抽到 `src/shared/directionZoom.ts`，viewer 与 mapMotion 共用一份。
- 修后实测：**1280×720 自然取景 zoom = 15.50、`rendered = 61/61`、`consoleLog` 无 exception**（`shots/1280x720/measure.json`）。

#### 5.4-b 矮容器档「箭头看不见」：自然取景 zoom 低于淡出阈（修前 → 已修）

方向层 `paint.icon-opacity = ["interpolate", ["linear"], ["zoom"], 15, 0, 15.5, 1]`
（`work/verify/layer-dump.json` → `layers[3].paint`），即 **zoom < 15.0 完全透明**。

| 视口 | 地图画布 | 修前自然取景 zoom | 修后自然取景 zoom | 修前方向层 | 修后方向层 |
|---|---|---|---|---|---|
| 1280×720 | 562×164 | —（`NaN` 异常） | **15.50** | 不可用 | **61/61 可见** |
| 1440×900 | 698×221 | **13.02** | **15.50** | 全透明 | **61/61 可见** |
| 375×812 | 357×243 | **13.49** | **15.50** | 全透明 | **57/61 可见**（4 条出视野） |
| 1920×1080 | 1174×488 | 15.76 | 15.76 | 可见 | 61/61 可见 |
| 2560×1440 | 1811×848 | 16.73 | 16.73 | 可见 | 61/61 可见 |

修前/修后同视口对比图：`work/verify/before_after_1440x900.png`、`work/verify/before_after_375x812.png`
（左右并排，左=修前、右=修后，同视口同位置；生成脚本 `work/verify/before_after.py`）。

> 说明：修前那一侧的自然取景是**应用自己 `fitBounds` 算出来的**，不是探针硬设的相机；
> 重生方式是回退到修复前的提交再跑 `cdp_measure.mjs`，本目录只存对比图，不存旧代码。

### 5.5 离站回程三方对照（静态方向层 / 路线箭头 / 后端 steps 几何）

截图：`work/verify/shots/shot_departure_1440.png`（1440×900，`?view=departure`，相机 `zoom 16.33`、`center [112.65599, 23.21462]`）。
数据：`work/verify/departure_check.json`（复现：`python work/verify/verify_departure_arrows.py`）。

**为什么要看这一屏**：默认视图（arrival）里看不到"同一段上静态方向箭头与路线箭头是否打架"，离站回程这一屏正好三条双向段全在视野内。

**判据分两类**（lead 2026-10-29 定，必须分开写，不能混）：

| 段类 | 段 | 静态层能证什么 | 实测 | 结论 |
|---|---|---|---|---|
| **单向段**（`oneway=yes` 正向 / `oneway=-1` 反向） | SZ-005 / SZ-011 / SZ-002 / SZ-012 / SZ-010 / SZ-007（反向单行）+ SZ-015（正向） | 静态 `rotate` 与 steps 行进序方位**应逐度相等** —— **硬判据** | 7 段 Δ 最大 **0.050°** | ✅ 通过 |
| **双向段**（共轴双头，`rotate` 只是轴、没有正反） | SZ-036 / SZ-023 / SZ-035 | 只能证「轴一致」（`\|Δ mod 180\| ≈ 0`）；方向对不对**只能**靠 steps 几何 + 端点标记 | 轴 Δ 最大 **0.034°**；同 3 段的路线箭头 vs 行进方位 Δ **0.03°** | ✅ 共轴通过（方向由 steps 证） |

其它硬数（同一脚本，16 步全量）：

- **路线箭头 == steps 行进方位**：视野内 10 支，Δ 最大 **0.050°**（限 0.5°）。
- **netpack 反推方位 == 后端 `steps[].geometry` 方位**：16 步，Δ 最大 **0.000°** —— 两份独立几何互相印证。
- **端点标记 == 行进序端点**：16 步 `geometry[0]` 距声明的 `from_node` 最大 **0.000 m**、`geometry[-1]` 距 `to_node` 最大 **0.000 m**（限 0.5 m）。
  即"起点/终点标记"跟的是**行进序**，不是 `coords` 序 —— 这正是业主说的"起点被标到段另一端"的那个错位方向的反面。
- 视野外 6 步（SZ-046 / SZ-048 / SZ-016 / SZ-038_rev / SZ-049_rev / SZ-052_rev）没有浏览器读数，
  只参与了"几何 + 端点"两项；它们的几何方位与链路一致，链路首尾相接。
- `start_point` / `destination_point`（后端回显，来自同一 `/steps` 响应）：
  `start_point = {node N-028, segment SZ-036_rev, offset_travel_m 0.0, lon 112.6583471, lat 23.21514}`、
  `destination_point = {node N-003, segment SZ-015, offset_m 54.3, lon 112.6535729, lat 23.2150334}`。

> ⚠ **这张图的底图瓦片是离线的**：画面里的灰色折线是**前端自绘的站区几何**，不是真实底图。
> 该图只用于核对**箭头朝向与段号**，**不代表底图观感** —— 业主若问"为什么地图是空白"，答案是这个。

## 6. 验收结论（逐条 通过/不通过 + 证据路径）

| 项 | 判据 | 结论 | 证据 |
|---|---|---|---|
| **L1** 后端口径自检 | `audit_segment_direction.py` 断言 A–G 全 PASS（Z / GZ 两站点） | ✅ **通过**（Z 16/16、GZ 15/15，`failed: 0`）；盲区：Z 站 D 组 12/14（2 段起点无出边） | `work/engine/tools/out/segment_direction_audit.json`、`..._gz.json` |
| **L2** 数值快照 | `--check` diff 为空；61 段齐；reverse 14 / bidir 33 / forward 14；reverse 占网 32.0%、连成 1 个分量 | ✅ **通过** | `work/verify/direction_snapshot.json` |
| **L3-a** 图纸 | 14 条 reverse + 5 条双向全量入图；灰线(coords 顺序)/彩线(行进顺序)并排；锥尖朝 to_node；端点标 from/to 节点名；指北针 + 比例尺 | ✅ **通过** | `work/verify/direction_sheet.svg` |
| **L3-b** 五档 · 落点 | 箭头中心 = 路段弧长中点，偏差 <1 px | ✅ **通过**（1280/1440/1920/2560/375 五档最大 **0.068 px**（natural）/ 0.047 px（pinned）；每档 canvas 与 zoom 逐档记在 `conditions`） | `work/verify/measure_summary.json` + `work/verify/shots/*/measure.json` |
| **L3-b** 五档 · 锥尖 | 锥尖朝行进方向；`icon-rotate` 与独立算的方位角 ≤2° | ✅ **通过**（五档均 **0.0002°**；含 `bearing=30°` 档） | 同上 + `arrow_overlay_check.png` |
| **L3-b** 五档 · 分辨率无关 | 同相机同段跨档像素偏移 = 0、无随视口变化的 offset | ✅ **通过**（跨档 spread **0.0 px**；`icon-offset/anchor/alignment` 五档完全一致） | `work/verify/pixel_vs_projection.json`、`shots/*/measure.json` → `layout` |
| **L3-c** 1280×720 自然取景 | 应用自己的进站 `fitBounds` 不异常、站内可见方向层 | ✅ **通过**（开发B 修后：zoom **15.50**、`rendered 61/61`、`consoleLog` 无 exception；修前曾 `Invalid LngLat (NaN,-90)` → 见 5.4-a） | `work/verify/shots/1280x720/measure.json` |
| **L3-d** 矮容器档箭头可见性 | 进站自然取景 zoom ≥ `DIR_ZOOM_FADE`(15.0)，方向层要素真的被渲染 | ✅ **通过**（五档自然取景 **15.50 / 15.50 / 15.76 / 16.73 / 15.50**，`queryRenderedFeatures` 实测 61/61/61/61/57；修前 1440 落 13.02、375 落 13.49 ⇒ 全透明 → 见 5.4-b） | 各档 `measure.json` 的 `natural.visibility` + `layer-dump.json` → `layers[3].paint.icon-opacity` |
| **L3-e** 离站回程三方对照 | 单向段静态 `rotate` 与 steps 行进方位逐度相等（硬判据）；双向段仅证轴一致；路线箭头 == steps 行进方位；端点标记 == 行进序端点 | ✅ **通过**（单向 7 段 Δ≤**0.050°**；双向 3 段轴 Δ≤**0.034°**；路线箭头 10 支 Δ≤**0.050°**；netpack vs `steps[].geometry` Δ=**0.000°**；端点 **0.000 m**） | `work/verify/departure_check.json` + `shots/shot_departure_1440.png` + §5.5 |
| **P1** 路线箭头权威化 | 路线箭头方向 == 后端 `steps[].geometry` 行进序（逐支），同段静态/路线朝向不打架 | ✅ **通过**（4 支 0.0° 差：SZ-004 300.1° / SZ-035 29.8° / SZ-023 300.5° / SZ-036 28.7°；模块级直跑真前端 `routeArrowGeoJson()`，**非浏览器截图**） | `work/verify/路线箭头联调-报告.md`、`work/verify/verify-route-arrows.mjs` |
| **P2** trim 口径洞（`/api/traffic/route/plan`） | 首末段按**行进里程**裁切、`Σsteps.length − trim ≈ routes.length`、`routes[]` 级 `trim_head_m/trim_tail_m` 有值 | ✅ **通过**（12/12 用例全 PASS；`trim_head_m` 与「起点→几何首点」实测距离偏差 **0.00 m**、`trim_tail` **0.00 m**、长度一致性 **0.00 m**、`routes[]` 级 trim 12/12 有值）——dev-A 修前那一版曾是 `null`，已复测确认修好 | `work/verify/route_plan_trim.json`（矩阵：SZ-004 reverse / SZ-023 forward × 0.25/0.5/0.75 × 起/终点在段中） |
| **起点标记口径** | 同一 `offset_m` 下「后端 `start_point`」与「前端 `pointAtOffset(coords, offset_m)`」一致（<2 m），reverse 段不得镜像到另一端 | ✅ **通过**（28/28 例，最大偏差 **0.55 m**；含 SZ-004/SZ-001/SZ-023/SZ-036 多档 offset） | `work/verify/start_marker_probe.json`、`work/verify/起点标记口径-自证报告.md` |

> 汇总：**十一条判据全部通过**——后端口径（L1 / L2）、前端箭头标向与落点（L3-a / L3-b）、
> 五档取景与箭头可见性（L3-c / L3-d）、离站回程三方对照（L3-e）、路线箭头权威化（P1）、trim 口径（P2）、起点标记口径。
>
> 需要说清楚的两件事：
> 1. **曾经不通过的两项**（1280×720 取景抛 `Invalid LngLat (NaN,-90)`；1440×900 / 375×812 自然取景 zoom 掉到 13.0~13.5 低于淡出阈 ⇒ 箭头全透明）
>    都不是箭头标向算错，而是**地图容器太矮 → 进站取景落到极远 zoom**；开发B 修好后（`minZoom = DIR_ZOOM_FULL` + `isUsableCamera` 守卫）本目录已复测通过，修前/修后证据见 §5.4。
> 2. **双向段的"方向"不能靠静态层证**：双头箭头两头都有锥尖，画反了也看不出来；双向段的方向由 §5.5 的 steps 行进序几何 + 端点标记证明，
>    而**路线箭头是单头**（`routeArrowIconImage()` 只画一个锥尖），一旦兜底猜反就是用户可见的指反 —— 这是本轮把路线箭头改为吃 `steps[].geometry` 的直接动因（见 §3.0）。

### 6.1 盲区（照实记，别当已验）

1. **L1 D 组覆盖 12/14**：Z 站 `SZ-001@N-038`、`SZ-003@N-001` 起点节点无出边，构造不出 `offset_m=0` 的算路；
   这两段改用前端 `pointAtOffset` 口径复核（`start_marker_probe.json`），**不是**后端 `steps` 级验证。
2. **像素级「墨迹中心 ↔ `map.project`」没做成自动化**：色值匹配被路线线色污染、开-关差值拿不到干净对照帧
   （详见 `work/verify/pixel_vs_projection.py` docstring）。替代证据是 `arrow_overlay_check.png` 的 20 面板裁剪
   （肉眼：红十字落在图标中心）+ 跨档 spread = 0 + 逐段 `d_pos_px ≤ 0.068`。
3. **`/api/traffic/vehicles` 不能用于几何校验**：`twin-D1-####` 的 lon/lat 与站点包几何全线偏 ~530 m（旧口径 mock 快照），
   本次所有几何核对都绕开它（dev-B 亦独立确认同一结论）。
4. **只验了 `zhaoqingdong` 一个站点的前端表现**（61 段）：`guangzhounan`（708 段）只跑了后端 L1 自检，
   前端未起该站 —— 样本面不同，结论不能直接外推到 GZ。
5. **`shots/shot_departure_1440.png` 的底图瓦片是离线的**：画面里的灰色折线是前端自绘的站区几何。这张图只能核对箭头朝向与段号，
   **不能**当作"底图观感"的证据（业主若问"地图为什么是空白/没有路网"，原因在此，与箭头标向无关）。
6. **双向段的静态层方向不可视证**：双头箭头本身看不出正反（§3.0），所以"双向段方向对不对"只能由 steps 几何 + 端点标记证明，
   静态层仅证"轴一致"。**不要**拿双向段的双头箭头当作方向证据。
7. **离站回程有 6 步在视野外**：`SZ-046 / SZ-048 / SZ-016 / SZ-038_rev / SZ-049_rev / SZ-052_rev` 没有浏览器读数，
   只参与了"几何方位 + 端点标记"两项（这两项 16 步全量通过）；它们的**屏幕像素**未测。
8. **视野外 6 步里有 3 步走的是双向段**（`SZ-038_rev` / `SZ-049_rev` / `SZ-052`，快照里 `direction="bidirectional"`，长度 19.1 / 17.4 / 16.3 m）：
   双头箭头只能证轴、不能证向（§3.0），所以这 3 步的方向只由 `steps[].geometry` 行进序证明，静态层不参与判向。

## 7. 写盘范围（硬约束）

- 只写：`scripts/verify_arrow_direction.py`、`work/verify/**`
- **不动**：`work/engine/**`、`work/backend/**`（无此目录）、`work/frontend/**`、`docs/**`
- **不** `git commit` / `git push`
- **文本一律 LF**：本目录所有脚本输出文本一律 `newline="\n"`，否则 `scripts/doc_gate.py` 判死；提交前必须跑 `python scripts/doc_gate.py`。
  （Windows 下 `pathlib.write_text()` 默认文本模式会把 `\n` 翻成 `\r\n`；同理**不要**用「全库 CRLF→LF」的批量脚本扫本目录，会把 PNG 一并写坏。）

