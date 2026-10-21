# IKPFR4 验收证据（2026-10-21）

被测分支：`task/IKPFR4-inplace-switch`（基于 `main` = `bf2ca78`）。
被测服务：`npx vite --mode mock --port 5200`（`VITE_USE_MOCK=1`，前端 + mock 中间件自成一体）。
浏览器：Edge headless 155（`--headless=new`，1920×1080 视口），经 CDP 脚本驱动点击并截图。

> 为什么用 mock 模式截图：本机 5173/5199 的 **remote** 模式要经 vite 代理转 `traffic.py:8000`，
> 该链路在本机上会周期性卡住（`/overview` 20 s 超时；**改前 main 上同样卡**，已用 `git stash`
> 做过 A/B，与本单无关）。切站链路本身在 mock 与 remote 下走同一段前端代码。

## 每个文件对应哪条完成判定

| 文件 | 拍的是什么 | 对应完成判定 |
|---|---|---|
| `01-station-Z.png` | 首屏 Z：`站点包路网 61 段 · 本次快照 61 段`，KPI 20.3 km/h | 首屏基线（改前改后都是这一屏） |
| `02-station-GZ.png` | 点「广州南站 · 708 段」**后 184 ms**：站名、KPI（17.8 km/h）、路段列表、热力矩阵、页脚 `708 段` 全部已是 GZ；顶部亮「缓存 · 刷新中 —— 缓存于 6 s 前…缓存数据不代表最新态势」 | 热缓存秒开（≤0.3 s）+ 无串站 + 缓存有标识 |
| `03-station-GZ-settled.png` | 后台刷新落地后：缓存条消失（数据不再是缓存）、选中态按新站默认规则重选 | 缓存不冒充最新 |
| `04-back-to-Z.png` | 切回 Z（65 ms）：`61 段`、KPI 20.4、缓存条再次出现 | 双向切换正确 |
| `05-rapid-final.png` | 连点 GZ→Z→GZ→Z 之后：停在 **Z**（61 段 / 肇庆东站） | 连点不叠加、最终状态 = 最后点击的站 |
| `06-deeplink-GZ.png` | `#/dashboard?pack=GZ` 直达：站名 广州南站、`708 段`、`localStorage['hubflow.stationPack']='GZ'` | `?pack=` 深链 |

## 同一次运行里测到的数字（CDP 脚本输出）

```text
① 首屏(Z)：chip=肇庆东站 kpi=20.3km/h rows=6 foot=站点包路网 61 段 · 本次快照 61 段 navEntries=1
② 预热缓存（首屏 6 s 内）：Z {segs:6, hasOverview:true} / GZ {segs:708, hasOverview:true}
③ 切到 GZ：msToChip=184 msToRows=184，probe 未丢（页面未重载），hash=#/dashboard?pack=GZ，
   切站瞬间 selected=0（状态已重置）、scrollTop=0
④ 切回 Z：msToChip=65 msToRows=65
⑤ 连点 Z→GZ→Z→GZ→Z：最终 chip=肇庆东站 rows=6 navEntries=1（probe 全程不丢）
⑥ 深链 ?pack=GZ：chip=广州南站 foot=站点包路网 708 段 stored=GZ
```

`window.__probe` 是切站前打在页面上的标记：整页刷新会把它清掉，全程不丢即证明**没有重新下载文档**
（另见 grep：`grep -rn "location.reload" src/` 代码 0 命中，只剩 2 处历史注释）。

## 已知问题（不在本单范围，改前就存在）

- 控制台有一条 `layers.hubflow-direction-marker.layout.icon-size: "zoom" expression may only be used as
  input to a top-level "step" or "interpolate" expression`：**IKP5BD 遗留在 main 上的表达式不合法**，
  会让「底图那份样式合进来」这一步抛错（截图里地图左上角一直停在「底图加载中…」，只有路网没有底图）。
  已用 `git stash` 在 `main` 上复现同样报错，**与本单无关**，另单修。
- GZ 站全段中性灰：GZ 站点包 `channels: []`（没有摄像头登记），`MapLibreViewer` 的 `coveredOf()`
  以「有摄像头」为上色前提。改前改后一致，不在本单。
