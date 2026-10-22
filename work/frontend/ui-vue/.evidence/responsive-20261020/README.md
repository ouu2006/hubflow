# 管理端 Web 自适应 · 截图证据（Issue IKP3EV，2026-10-20）

本目录是 Issue IKP3EV「管理端 Web 自适应：适配 1080×1920 及以下屏幕」的本机截图证据。

- 来源：本机 `work/frontend/ui-vue` 的 `npm run dev`（mock 模式，Vite）页面，用 Edge headless + CDP 按视口截图；
  原图 1920/1366/1024 宽已缩放到 1100 宽，1080/390 宽保持原宽，统一转 JPEG（quality 82）以控制仓库体积。
- 数据：**全部为演示数据（mock）**，`is_simulated = true`；不是现场实测。
- 注意：截图里感知页若出现「感知服务未连接 / 感知服务不可用」，是本地没启动
  `work/perception/server.py`（127.0.0.1:8101）所致，属于接口未起的如实空态，与响应式布局无关。

| 文件 | 页面 | 视口 | 说明 |
|---|---|---|---|
| `dashboard-1920x1080.jpg` | 监控大屏 | 1920×1080 | 桌面基线，与改前一致（不退化） |
| `dashboard-1080x1920.jpg` | 监控大屏 | 1080×1920 | 本单主目标：三栏纵向单列、地图可读、图例折叠 |
| `dashboard-1024x768.jpg` | 监控大屏 | 1024×768 | 单列 + 整页滚动 |
| `dashboard-390x844.jpg` | 监控大屏 | 390×844 | 手机宽：KPI 两列、顶栏换行、无横向滚动 |
| `decision-1920x1080-queue.jpg` | 决策层（处置队列） | 1920×1080 | 桌面基线，与改前一致 |
| `decision-1080x1920-queue.jpg` | 决策层（处置队列） | 1080×1920 | 三栏纵向单列，工作台/因素/预测/同化依次排列 |
| `decision-390x844-queue.jpg` | 决策层（处置队列） | 390×844 | 手机宽：页头控件换行、按钮可点 |
| `perception-1920x1080.jpg` | 感知层 | 1920×1080 | 桌面基线，三栏 254/弹/372 与改前一致 |
| `perception-1366x768.jpg` | 感知层 | 1366×768 | 低高度桌面：整页滚动（原先把监控墙裁掉且无滚动条） |
| `perception-1080x1920.jpg` | 感知层 | 1080×1920 | 三栏单列，监控墙 3 列可读 |
| `perception-390x844.jpg` | 感知层 | 390×844 | 手机宽：监控墙 1 列、环境条折行 |

多视口审计（8 视口 × 3 页，强制整页 reload）结果：所有组合
`document.documentElement.scrollWidth - document.documentElement.clientWidth = 0`（无页面级横向溢出）；
1920×1080 三页布局与改前一致。断点与验证命令见 `work/frontend/README.md` 第二十二节。
