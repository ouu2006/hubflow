# work/twin/netpack · 站点 OSM 切片 → 站点包路网（Issue IKLX5Y）

> **一句话**：把仓库里那份 OSM 切片**归并成可点击的路段**，产出前端站点包要用的几何，
> 让大屏上的路网**是这张真路网**——不是手画的示意几何。
> **几何取自 OSM（真值）；路况指标一律是演示数据（模拟）。**

## 一键复现

```bash
# 在仓库根执行（产物之一落在前端站点包里，路径写死在这个脚本里，不用手抄）
python work/twin/netpack/build_station_pack.py \
    --osm work/frontend/tools/twin_preview/station.osm \
    --site 肇庆东站 \
    --out-json work/twin/netpack/network.json \
    --out-ts   work/frontend/ui-vue/src/station-packs/stationZ.network.ts

# 只校验：重跑一遍与既有产物**逐字节**比对（不写盘，不一致非 0 退出）
python work/twin/netpack/build_station_pack.py ... --check
```

## 输入 / 输出 / 关键口径

| | 内容 |
|---|---|
| **输入** | `work/frontend/tools/twin_preview/station.osm`（已在库；175 节点 / 70 way，way 上带 `name` / `highway` / `service` 标签）。**不联网、不拉新数据** |
| **输出** | ① `network.json`（机器可读真值，每段带组成它的 OSM way id，可追溯）；② `stationZ.network.ts`（前端站点包几何，**脚本产物、勿手改**） |
| **关键口径** | **按路名归并**（业主 2026-10-15 裁定）→ 约 20 段可点击路段；脚本里**不出现任何站点名与坐标**（手册 §8.4：换站只改参数） |

## 归并的四步（都在这一个脚本里）

1. **归并键**：有名用 `name`；无名按 `service`；再退 `highway`（想加别的口径改 `group_key`）。
2. **串链**：同组内共享 OSM 节点的 way 首尾相接成一串。
3. **并片**：串完还剩下的"片"，若**端点相距 ≤ `SNAP_M`（默认 30 m）** 就算同一个路口的两侧，接起来。
   OSM 在路口处常常各 way 各用一个独立节点，不并片会把一个路口切成好几截，图上全是断口。
4. **剔碎**：不足 `MIN_SEG_M`（默认 60 m）的片丢弃（都是路口连接的小碎段，画在图上只是噪点）。

同一归并键最终仍是多片的，名字加方位后缀（如「鼎湖大道·由西向东第1片」）以示区分。

**调这两个阈值会改变段数**（实测：30/60 → 21 段；30/120 → 17 段）。改了就重跑并**在 PR 里说明为什么**。

## 不做什么

- **不装 SUMO、不跑 `netconvert`、不碰后端**：本目录只出"可点击路段"，仿真链路是另一条线。
- **不判定主干 / 分支**：业主明说先不定；走廊落位另开单。
- **不带任何指标**：`network.json` 里没有 `level` / `q_vph` 之类的字段——那些是演示数据，
  在前端站点包 `stationZ.ts` 里，与几何**分开两份**（几何可重建，指标是编的，不能混）。

## 一处需要留意的坑

**图必须建在折线顶点级**：干道是一条长折线，场区通道挂在它的**中间顶点**上。
只用首尾点建边会把场区判成不连通——本项目已经因此踩过三次（详见 `parking-corridor-scope` 的口径）。
本脚本产出的折线**保留了全部顶点**，下游按它建图不会再踩。
