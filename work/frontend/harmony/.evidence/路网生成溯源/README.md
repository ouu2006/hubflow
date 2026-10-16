# 路网与路线数据的生成溯源

本目录存放 `entry/src/main/ets/common/RealNet.ets`、`RoutePlan.ets` 中
**路网几何与三条候选路线**的原始生成脚本与输入数据，用于回答评审提问
「地图上的路网和路线是手写编造的，还是有依据算出来的？」。

结论：**是算出来的，且脚本可复现**。

## 文件清单

| 文件 | 作用 |
|---|---|
| `realmap.json` | 第一版路网原始输入（22 条路的节点串） |
| `realmap2.json` | 定稿路网原始输入（最终用于生成 `RealNet.ets`） |
| `gen_realnet.py` | 读取 `realmap2.json`，做 RDP 抽稀后输出 `RealNet.ets` 的几何数据段 |
| `gen_routes_dijkstra.py` | 在路网上跑 **Dijkstra k 最短路**（指数惩罚 +40/+400/+4000），算出三条互不相同的候选路线 |
| `emit_realnet_ets.py` | 把抽稀后的几何按 ArkTS 语法落盘为 `RealNet.ets` |
| `paths.json` | `gen_routes_dijkstra.py` 的输出：三条路线的节点序列与里程 |

## 三条路线的对应关系（与契约 reason 一一对应）

| 界面显示 | 生成脚本输出 | 里程 | 对应契约 reason |
|---|---|---|---|
| 路线一（推荐） | `paths.json` 第 1 条 | 5044 m | 主选，耗时最短 |
| 路线二 | `paths.json` 第 2 条 | 5059 m | `alternatives[0]` |
| 路线三 | `paths.json` 第 3 条 | 5120 m | `alternatives[1]` |

三条路线在路网上的重合度 0.64 ~ 0.71，因此地图上共用路段显示主线色
（与高德等商业导航的表现一致），**不是渲染 bug**。

## 复现方式

```bash
python gen_realnet.py       # 输出 RealNet.ets 的几何段
python gen_routes_dijkstra.py  # 输出 paths.json（三条路线 + 里程）
python emit_realnet_ets.py  # 落盘 RealNet.ets
```

## 口径声明

- 路网为**一期孪生真值**，用于演示与流程验证，**非高德/任何商业地图 SDK 的产物**。
- 高德地图服务条款明文禁止存储/缓存/截图/落盘，因此本项目地图**一律自绘**，
  未引入任何第三方地图 SDK，不存在条款合规风险。
- 页面用户可见文案不含「实测/实时/现场」（「请服从现场指挥」为手册 §11.1(3) 固定措辞，例外）。
- `is_simulated` 恒为 `true`；位置来源标注为「twin（一期孪生真值，非真实定位）」。
