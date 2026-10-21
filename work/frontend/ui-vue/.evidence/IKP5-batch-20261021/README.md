# IKP5 批次 · 大屏渲染截图（2026-10-21）

> 截图环境：1920×1080，`npm run dev:remote` + `python work/assembly/traffic.py --port 8000`（站点包 Z 为默认站）。
> 采集方式：无头 Chromium（SwiftShader WebGL）经 CDP 截图；只作页面渲染留证，不是现场照片。
> 所有数据均为 `is_simulated = true` 的演示产物；地图底图因无外网瓦片会显示「底图不可用 · 路网照画」，路网 / 标记 / 路线由页面自绘。

| 文件 | 对应判定 | 看什么 |
|---|---|---|
| `01-dashboard-default.png` | IKP5BD / IKP5BZ / IKP5CK 总览 | 顶栏「运行 remote」chip（IKP58M）；地图上的方向箭头、摄像头图钉、落客点「落」/场区「场」标记；右栏「本段附近的落客点 / 场区」；图例四色 + 「凸显路线 开」 |
| `02-route-card-start-end.png` | IKP5C6 | 「本次起点」段号 `SZ-003` + 路段名「吉庆大道」+ 来源「孪生真值」+ offset 0.0 m + match_confidence 1.00 + 未确认角标 + 「以这里为起点」/「手动选起点」；「本次终点」落客点位为空窗并给出 `why` 原因与末段 `SZ-002` 兜底 |
| `03-route-emphasis-off.png` | IKP5CK 凸显开关 | 工具条按钮变「凸显路线 关」、图例写「关 — 满图等级色，路线叠加」；与 01 的「开 — 非路线段中性灰细线」对照 |
| `04-settings-direction-switch.png` | IKP5BD 开关 | 顶栏「设置」内两项：矢量底图 + 方向标记（默认开，文案写明双向段中点前后各一支） |
| `05-directions-hidden.png` | IKP5BD 关后无箭头 | 方向标记关闭后地图无方向箭头；图例出现「当前已隐藏方向标记」 |
| `06-start-confirmed.png` | IKP5C6 确认动作 | 点击「以这里为起点」后起点角标由「未确认」变「已确认」 |
| `07-gz-landmarks.png` | IKP5BZ GZ 站 | 切到「广州南站 · 708 段」后地图上的落客点 / 场区标记（GZ 5+4 演示点）；底图注记为 1000 m 演示范围 |
| `08-z21-fallback.png` | IKP5D3 Z21 兜底 | 浏览器 localStorage 残留 `Z21` 键时页面回落「肇庆东站」（PACKS 已无 Z21，不再全站 404） |
| `09-route-endpoints.png` | IKP5C6 追加：起终点标注 | 地图上的「起」（蓝，SZ-003 外围边界断面 P-B02）与「终」（琥珀，停车场落客点 DROP-02，演示点）；路线卡「位置类型 外围边界断面 P-B02」；OD 下拉开始显示「起点 段号（路段名）」；Z 站 OD 已收敛为 **4 个外围入口 × 落客点终点**（终点 `SZ-036` 末端 `N-028` = `SZ-036`/`SZ-024` 交界，对应 `DROP-02`） |

**已知限制（如实记）**：GZ 站在 remote 模式首次加载时 `/api/traffic/overview` 单次耗时约 11–27 s（既有性能问题，非本批改动），超过前端 10 s 超时会让 GZ 页的 KPI / 路段列表显示空态；本截图的 GZ 证据只覆盖「地图上的落客点 / 场区标记」。Z 站不受影响。该性能问题建议单独开单。

**复核命令**：见 `work/frontend/README.md` 第二十三节 §23.9。
