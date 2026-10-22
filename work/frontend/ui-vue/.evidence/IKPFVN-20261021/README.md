# IKPFVN 验收证据（2026-10-21）

被测分支：`task/IKPFVN-national-map`（基于 `main` = `5623e63`，即 IKPFR4 合入后的 main）。
被测服务：`npx vite --mode mock --port 5200`（`VITE_USE_MOCK=1`，前端 + mock 中间件自成一体）。
浏览器：Edge headless 155（`--headless=new`，1920×1080 视口），由 CDP 脚本点击 / 读 `map.getZoom()` / 截图。

> 为什么用 mock 模式截图：本机 remote 模式要经 vite 代理转 `traffic.py:8000`，该链路在本机上会周期性卡住
> （`/overview` 20 s 超时，改前 `main` 上同样卡，已用 `git stash` A/B 过）。镜头 / 图层 / 版式走的是同一段前端代码。

## 每个文件对应哪条完成判定

| 文件 | 拍的是什么 | 对应判定 |
|---|---|---|
| `01-national.png` | 全国首屏：`data-map-mode=national`，`map.getZoom()=3.01`，只显示两站 pin + 站点浮层卡片（「已接入车站 2 个 / 肇庆东站 61 段 / 广州南站 708 段 / 演示数据」），路网 / 路线 / 落客点 / 摄像头全部不可见，左右栏收起、地图占满内容区（1862 px） | 全国视角 + 版式 |
| `02-arrived-GZ.png` | 点「广州南站」后 2.2 s 到站：`phase=station`，站区路网 + 路线 + 图例出现，左右栏滑入 | 分镜可见 / 到站 |
| `03-station-GZ-settled.png` | GZ 站区定型：`data-station=GZ`，708 段列表、KPI 17.8 km/h、热力矩阵、`← 全国` 按钮在场 | 单站渲染 / 信息切换 |
| `04-back-national.png` | 点「← 全国」：`phase=national`、`zoom=3.01`、pin 回来、路网与左右栏收起 | 「← 全国」入口 + 镜头可逆 |
| `05-rapid-final-national.png` | 连点 GZ→Z→GZ→Z 后回到全国视角的画面（数字见下方 ⑤：最终停在 **Z**，路线段号全 `SZ-`） | 连点/打断 |
| `06-deeplink-GZ.png` | `#/dashboard?station=GZ` 新文档直达站区（无动画、起手即 `station`） | 深链 |
| `07-basemap-blocked.png` | 屏蔽 `*openfreemap.org*` 与 `*/basemap/*` 后：中国轮廓 + 两站 pin + 「底图不可用 · 仅显示站点与站区路网」+ Natural Earth 口径注，**不白屏** | 底图失败兜底 |
| `08-reduced-motion.png` | `prefers-reduced-motion: reduce` 下切站：不缩远不平移，893 ms 直接到站区 | 减弱动效 |

## 同一次运行里测到的数字（CDP 脚本输出）

```text
① 全国首屏：mode=national zoom=3.01 routeSegs=0 netVisible=none pinVisible=visible
   cards=[肇庆东站 61 段 演示数据, 广州南站 708 段 演示数据] leftCol 不存在 mapW=1862
② 镜头采样（点「广州南站」后逐帧读 map.getZoom()）：
   56ms z3.01 national → 218ms z4.07 → 381ms z5.11 → 548ms z5.47 panning
   → 632ms z5.50 entering → 881ms z8.19 → 1297ms z11.95 → 1491ms z12.20 entering
   → 到站 2203ms（phase=station，总时长落在 1.8–3.0 s）
③ 到站后：mode=station station=GZ zoom=12.52 routeSegs=2194 routePrefixes=[GZ-]（2194 = 瓦片重复计数，段号全 GZ-）
④ 回全国：mode=national zoom=3.01 pin 回来、路网 none
⑤ 连点 GZ→Z→GZ→Z：最终 mode=station station=Z zoom=15.13 prefixes=[SZ-] routeSegs=80
⑥ 深链 ?station=GZ：mode=station station=GZ zoom=12.52 prefixes=[GZ-]
⑦ 底图屏蔽：mode=national zoom=3.01 outline(fill/line)=visible pins=visible networkLine=none
   note=「底图不可用 · 仅显示站点与站区路网 重试」+「轮廓简化，仅作示意，不代表边界主张（Natural Earth 1:110m）」
⑧ 减弱动效：minZoom=3.01，893 ms 到站（不做"缩远→平移"，只一次 fitBounds）
⑨ console error：0 条（IKP5BD 遗留的 `icon-size` 表达式报错已随本单修掉）
```

**信息不串站（过渡期逐帧读面板）**：

```text
309ms  phase=panning  chip=广州南站  kpi=—km/h   rows=0   skeleton=true
622ms  phase=panning  chip=广州南站  kpi=—km/h   rows=0   skeleton=true
1038ms phase=entering chip=广州南站  kpi=—km/h   rows=0   skeleton=true
2452ms phase=station  chip=广州南站  kpi=17.8km/h rows=708 skeleton=false
```

即：**镜头在飞的时候面板是"空的 + 骨架"，落地那一刻才换上目标站数据**，不会出现「广州南 + SZ-xxx」这种混排。

## 已知问题（不在本单范围，改前就存在）

- GZ 站全段偏中性灰：GZ 站点包 `channels: []`（无摄像头登记），`MapLibreViewer.coveredOf()` 以「有摄像头」为上色前提。
  改前改后一致（IKP5DM 的 `colorPolicy: 'all'` 没有落到 `MapLibreViewer` 的上色门槛上，属另单）。
- 全国缩放下两站 pin 相距约 7 px（Z/GZ 实际相距约 100 km），站名标签交给 MapLibre 碰撞检测，通常只显示一个；
  精确选站以站点浮层卡片与悬停浮牌为准（卡片上两站都在）。
