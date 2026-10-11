# twin_preview · 大屏 SUMO 真值预览(Issue #61)

> **定位**:演示底座,不是孪生实现。正式路网归 #36(`netbuild.py`)/#37(`map_ingest.py`)、
> 仿真主循环归 #38(`work/twin/`,开发A)。本目录只回答一个问题:**把 SUMO 真值接进大屏,
> 车辆动点能不能真动起来**——业主 2026-10-11 拍板的预览单。

## 组成

| 文件 | 作用 |
|---|---|
| `build_net.py` | (可选)Overpass 下载站点周边 OSM → `netconvert` 转网;产物已入库,平时不用跑 |
| `station.osm` | 肇庆东站(贵广高铁)周边 ~1.3 km 车行道路切片(31 KB) |
| `station.net.xml` | SUMO 路网(带街名,~400 KB) |
| `server.py` | 桥接服务 `127.0.0.1:8102`:TraCI 小仿真 → 契约 vehicles 真值 + 底图折线 |

## 跑法

```bash
# 1. 桥接服务(需 SUMO_HOME、PYTHONPATH 含 %SUMO_HOME%\tools、fastapi+uvicorn)
python work/frontend/tools/twin_preview/server.py

# 2. 前端(任一 ui-vue 工作树)
npm run dev   # /twin-api 代理指向 8102
```

打开 `/#/dashboard`:底图自动替换为 OSM 真路网(吉庆大道/鼎湖大道 + 站区连接线),
车辆动点为 SUMO 真值(D1 送客会驶向落客段停驻约 12 s 再离开)。**桥接服务不在时页面
自动回落示例路网 + 合成车**,不白屏。

## 口径

- 车辆字段逐字对照 `docs/数据契约.md` v2.0 vehicles 元素;`is_simulated` 只在信封层。
- 路段判级仍来自 traffic mock(演示基线),不是 SUMO 输出——本单只接"车辆真值 + 底图"。
- 页面标注:底图水印/页脚在真路网生效时显示"OSM 真路网 · SUMO 仿真演示"。
- 不嵌 sumo-gui 画面、不做 3D 大屏(手册风险表第 20 条);不动 `work/twin/`。
