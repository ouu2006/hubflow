# 历史台账：GitHub 侧 Issue 与 PR（2026-10-09 ~ 2026-10-13）

> **这不是权威文档，是存档。** 权威顺序仍是：手册 / 总纲 / 分工表 / 协作规范（见根 `README.md`）。
> 本目录只在一种情况下翻：**要查某条历史单的原文**（讨论、审查记录、当时的判定依据）。

## 一、这是什么

本仓库在 **2026-10-14 从 GitHub 迁到 Gitee**（原因与落地见 [`../仓库设置清单.md`](../仓库设置清单.md) 第 5 节）。
GitHub 侧账号被封后，**原仓库的 39 条 Issue 与 56 条 PR 全部不可访问**。本目录是它们的**本地重建件**：
正文与评论逐条恢复，来源有三处（都在本机、仓库外）：

| 来源 | 是什么 | 拿到什么 |
|---|---|---|
| ZCode 会话库 | 历史会话的工具调用记录 | 创建 / 编辑 / 评论命令里的**原始正文**（最大头） |
| dsh 会话存档 | 另一套助手的历史会话（`session.v4.jsonl.zstd` 压缩流） | 2026-10-09 ~ 10-10 期间的创建命令与正文 |
| 仓库内残留草稿 | `_issue_draft/`、`_PR_*.md`、系统临时目录里的 `*.md` | 早期几单的正文文件本体 |

**没有做的事**（避免误解）：PR 的**行内审查意见**（Sourcery / 快速独立审查的逐行评论）随平台一起丢了，本档只到**评论级**；
`Issue #NN` / `PR #NN` 编号一律是 **GitHub 侧编号**，与 Gitee 侧新单不通用。

## 二、取回率

- Issue 正文：**39/39** 条有正文（无缺口）
- PR 正文：**55/56** 条有正文（缺 ['95']，其中 #95 由队友在 GitHub 侧创建，本机无记录）
- 评论：Issue 侧 28 条，PR 侧 21 条
- 全文：每条 Issue / PR 的正文与评论见 [`issue-归档.md`](issue-归档.md) 与 [`pr-归档.md`](pr-归档.md)

## 三、Issue 索引（39 条）

    https://github.com/ouu2006/hubflow/issues/NN


| # | 标题 | 状态 | 标签 | 正文 | 取回来源 | 评论 |
|---|---|---|---|---|---|---|
| 2 | [感知线] W1：跑通 segments.json | OPEN | — | 1553 字 | `edit-append` | 1 |
| 3 | [决策线] W1：站点包结构定稿 + 跑通 routes.json + 地图 Key 申请 | OPEN | — | 1879 字 | `edit-append` | 0 |
| 4 | [前端] W1：管理端页面壳 + 鸿蒙最小可用页 | OPEN | — | 1520 字 | `edit-append` | 0 |
| 5 | [后端] W1：run_all.py 骨架 + 契约冻结通知 + 中文路径裁定 | OPEN | — | 1824 字 | `edit-append` | 1 |
| 6 | [数据与标注] W1：抽帧启动 + 标注规范 v1 + 控制点拾取 | OPEN | — | 1199 字 | `edit-append` | 1 |
| 7 | [验收与测试] W1：验收用例转可勾选检查表 + 缺陷清单模板 | OPEN | — | 1111 字 | `edit-append` | 0 |
| 8 | [文档与演示] W1：数据来源清单模板 + 演示脚本骨架 | OPEN | — | 1019 字 | `edit-append` | 0 |
| 9 | [队长] 开工阻塞项：填分工表 + 邀请协作者 + 裁定中文路径 + 离线缓存许可 | OPEN | — | 1139 字 | `prior-heredoc` | 4 |
| 29 | [阶段0·0-2] SUMO 安装与官方示例验证（L0 · 系列 S） | CLOSED | L0, 系列S | 2352 字 | `Write-tool-global` | 3 |
| 36 | [阶段0·0-3A] 站点 OSM → netbuild.py → stations/sumo/*.net.xml（L1 · 站点/踏勘） | OPEN | L1 | 4562 字 | `disk:D:/hubflow/_issue_draft/_ready/A1-0-3-netbuild.body.md` | 1 |
| 37 | [阶段0·0-3B] map_ingest.py → network.json + map_source.json（L1 · 站点/踏勘） | OPEN | L1, L0 | 4599 字 | `disk-manual:D:/hubflow/_issue_draft/_ready/B1-0-3-map-ingest.body.md` | 1 |
| 38 | [W0骨架] work/twin/ 骨架 + samples/ + 像素轨迹补时间戳（L1 · 站点/踏勘） | CLOSED | L1, L0 | 3664 字 | `disk-manual:D:/hubflow/_issue_draft/_ready/A2-twin-skeleton.body.md` | 0 |
| 39 | [W0骨架] 站点包九件结构定稿 + run.py --sample（L1 · 站点/踏勘） | CLOSED | L1, L0 | 3762 字 | `disk-manual:D:/hubflow/_issue_draft/_ready/B2-station-contract.body.md` | 2 |
| 40 | [W0骨架] 上游 Vue 管理端跑通 + 接口层/一键脚本骨架（L0 · 接口/双端） | CLOSED | L1, L0, 系列P, 系列S | 3090 字 | `view-json` | 2 |
| 41 | [W0骨架] T1/T2 转换脚本骨架（表格 → points.json / network.json 属性补录）（L1 · 站点/踏勘） | OPEN | L1 | 4346 字 | `disk:D:/hubflow/_issue_draft/_ready/B3-t1t2-ingest.body.md` | 0 |
| 43 | [阶段0·0-4] 表格模板实体（T1~T6）下发 + 共享盘物理路径写定（L0 · 系列 S） | OPEN | L0, 系列S | 4163 字 | `edit-cmd:same-cmd-heredoc` | 1 |
| 44 | [阶段0·0-5] 地图 Key 申请（底图核对用，只进本地 .env）（L0 · 系列 S） | CLOSED | L0, 系列S | 2934 字 | `global-heredoc` | 2 |
| 46 | [裁定] 手册 BPR 行程时间函数量纲错误：t⁰·[1+α(x/c)^β] 应为 t⁰·(1+α·x^β)（4 处） | CLOSED | documentation | 1774 字 | `edit-cmd:same-cmd-heredoc` | 1 |
| 47 | [裁定] hubflow-plan/02 与 03 的处置：并入 / 标暂不并入 / 删除（含 4 处冲突逐条） | CLOSED | documentation | 2702 字 | `edit-cmd:same-cmd-heredoc` | 1 |
| 52 | [接口与双端] 交通态势大屏 M1——工程落位 + 态势总览页（壳 + 四级染色三重编码） | CLOSED | L1 | 4842 字 | `Write-tool-global` | 0 |
| 54 | [接口与双端] 感知层前端——YOLO 检测画面页（画面示例占位 + 检测框叠加 + 感知指标快照） | CLOSED | L1 | 2025 字 | `Write-tool` | 0 |
| 55 | [接口与双端] 决策层可视化前端核验——harness 四页新落位下的 mock 全链路验证与台账 | CLOSED | L1 | 1352 字 | `Write-tool` | 0 |
| 59 | [接口与双端] 决策层工作台页——告警驱动处置工作流 + 因素与预测 + 效果对比 + 同化状态(三层前端之二) | CLOSED | L2 | 1295 字 | `inline-body` | 0 |
| 61 | 大屏 SUMO 预览：OSM 真路网 + TraCI 车辆真值接入 mock SSE（demo） | CLOSED | L1 | 1096 字 | `prior-heredoc` | 0 |
| 66 | [接口与双端] 补齐 P0 页面缺口——拥挤度热力·拥挤指数视图 + 决策层三处口径对齐(手册 §11.2 / C-2) | CLOSED | L1 | 3418 字 | `view-json` | 2 |
| 68 | [接口与双端] 缺陷台账——#66 期间的只读代码盘点发现（契约/确定性/阈值/工程，22 项） | OPEN | bug | 5454 字 | `Write-tool-global` | 1 |
| 71 | [接口与双端] 管理端四页按设计稿重做——TDesign Light 配色迁移 + 接口面按页面重新规划（L2） | CLOSED | — | 1542 字 | `disk-manual:D:/hubflow/_issue_body71.md` | 0 |
| 73 | [接口与双端] 站点包层：第二个站接入——实测手册 §8.4「换站只改配置」在前端成不成立（L2） | CLOSED | L2 | 1373 字 | `prior-heredoc` | 0 |
| 75 | [接口与双端] 演示前四页浏览器实测与修复——热力矩阵列数/数据源死控件/判级口径/因素时效(L1) | CLOSED | L1 | 2743 字 | `prior-heredoc` | 2 |
| 77 | [接口与双端] 管理端 Web 收敛为三页：感知层 / 决策层 / 监控大屏（热力并入，决策新增加可视化） | CLOSED | L2 | 2074 字 | `view-json` | 0 |
| 80 | [接口与双端] 司机端鸿蒙 App：P0 四页 + 绑定一台演示车（数据全用虚拟，双端同源）（L2） | OPEN | L2 | 4028 字 | `Write-tool` | 0 |
| 81 | [接口与双端] 监控大屏窗口可拖拽调宽——主体三栏 + 底部热力带（L1） | OPEN | L1 | 4940 字 | `Write-tool` | 0 |
| 83 | [W1前置] PR #79 兜底审确认的 6 条 Sourcery 待办：孪生骨架输入校验与诊断补齐 | CLOSED | L1 | 1470 字 | `inline-body` | 0 |
| 85 | [接口与双端] 大屏右栏「关联告警」判级回归——#77 迁移时丢了 #75 第④条的等级重映射（L1） | OPEN | L1 | 2323 字 | `Write-tool` | 0 |
| 86 | [流程] 新增「填表报告」：每次提交留一行「哪张表第几版 → 哪个产物」，门禁第 7 组强制（L1 · 站点/踏勘） | CLOSED | — | 1430 字 | `prior-heredoc` | 0 |
| 88 | [接口与双端] 鸿蒙 App 拆分 A：工程骨架 + P0 四页 UI（数据用工程内 fixture，不联网）（L2） | OPEN | L2 | 4182 字 | `Write-tool` | 0 |
| 89 | [接口与双端] 鸿蒙 App 拆分 B：接驳后端与 Web 端（同一套 mock）+ 双端同源举证（L2） | OPEN | L2 | 5229 字 | `Write-tool` | 0 |
| 91 | [文档与合规] 填表报告 `结果` 增补第五种取值「占位」：结构骨架 / 运行产物 / 基线登记有名字可登记（L1 · 文档与合规） | CLOSED | L1 | 1592 字 | `prior-heredoc` | 1 |
| 94 | [决策与定位 + 判级] PR #82 兜底审遗留五项：--sample 输出口径三处 + 登记口径两处（L1） | OPEN | L1 | 2184 字 | `prior-heredoc` | 1 |

## 四、PR 索引（56 条）

    https://github.com/ouu2006/hubflow/pull/NN

| # | 标题 | 状态 | 标签 | 正文 | 取回来源 | 评论 |
|---|---|---|---|---|---|---|
| 1 | 文档：补开发规范、密钥规范、PR/Issue 模板与现状核实 | MERGED | — | 1935 字 | `inline-heredoc` | 2 |
| 10 | 【测试】门禁拦截验证（稍后关闭） | CLOSED | — | 35 字 | `inline-body` | 0 |
| 11 | 【测试】验证 CODEOWNERS 自动指派（稍后关闭） | CLOSED | — | 50 字 | `inline-body` | 0 |
| 12 | 文档：分工表补「完成判定」——每个位置干到什么程度才算做完 | MERGED | — | 1500 字 | `inline-heredoc` | 1 |
| 13 | 文档：补三场景专节、SUMO 分工口径、全周期分工表（W0–W8） | MERGED | — | 1808 字 | `inline-heredoc` | 0 |
| 14 | 文档：微调落到感知线 + 修掉 14.1 的死链 | MERGED | — | 1671 字 | `inline-heredoc` | 0 |
| 15 | 文档：V2.0 计划修订（一期孪生驱动 / 协同分流 / 多因素 / 二期预测，分工改 3 开发 + 4 非技术） | MERGED | — | 5510 字 | `Write-tool-global` | 0 |
| 16 | 计划：协作成员口径（可参与部分技术开发）+ 队长不占代码目录 | MERGED | — | 3242 字 | `edit-cmd:Write-tool-global` | 0 |
| 17 | 计划：一期改为双数据源（D1′）——YOLO 在一期就算真实路段 | MERGED | — | 3998 字 | `Write-tool-global` | 0 |
| 18 | 计划：新增架构层职责表（九层 + 两条横切，一层一个 owner） | MERGED | — | 2701 字 | `Write-tool` | 0 |
| 19 | 计划：架构层职责表改为占位（由上级统一编写，本项目组不自拟） | MERGED | — | 1525 字 | `Write-tool-global` | 0 |
| 20 | (标题未取到) | MERGED | — | 2072 字 | `view-reconstruct:recovered_bodies/pr20.md` | 0 |
| 21 | 文档：PR 评审加快速独立审查与 CI 门禁（新增 ci 工作流、门禁脚本、仓库设置清单） | MERGED | — | 3396 字 | `Write-tool` | 1 |
| 22 | 文档：合并门槛改为 CI 强制（取消「必须人工 approve」） | MERGED | — | 4797 字 | `edit-cmd:same-cmd-herestring-any` | 0 |
| 23 | 文档：统一模块与文件归属口径（谁写哪个文件写死；C 的两份 README 补到 D1′） | MERGED | — | 6794 字 | `Write-tool` | 0 |
| 24 | 文档：分工口径 V2.1 落地——判级归开发B + 任务池认领制 + 任务分支制；#20 分工表设为项目分工表 | MERGED | — | 1976 字 | `Write-tool-global` | 0 |
| 25 | 文档：分工表不预设人——派活改为「谁认领谁干，可单人也可多人组队」 | MERGED | — | 1734 字 | `edit-cmd:same-cmd-herestring` | 0 |
| 26 | 文档：兜底审改为三个账号任一（@YONEK0 / @ouu2006 / @2652201498w-wq） | MERGED | — | 2032 字 | `prior-herestring` | 0 |
| 27 | 文档：取消 ABC 互审（评审改三道关）+ 不再按人映射开发账号 | MERGED | — | 2362 字 | `edit-cmd:same-cmd-herestring` | 0 |
| 28 | 文档：开发 = 区域负责人（派活方）——拆活发布、只发布不点名；协作成员 = 接活方 | MERGED | — | 2057 字 | `edit-cmd:same-cmd-herestring` | 0 |
| 30 | 文档：底层框架固定、后面拆分出来的工作给推荐方式——不锁死做法（+ 换法必须申报） | MERGED | — | 3598 字 | `edit-cmd:same-cmd-herestring` | 0 |
| 31 | 文档：增补框架层修改权——开发A/B/C 作为框架作者可改底层框架（按类型走流程） | MERGED | — | 2801 字 | `edit-cmd:same-cmd-herestring` | 0 |
| 32 | 接口：新建技术栈台账（SUMO 1.28.0 装 D 盘 + 许可核查落盘，关闭 T-07） | MERGED | — | 5664 字 | `global-heredoc` | 0 |
| 33 | 接口：技术栈台账补功能完整性核对 + 桌面入口（SUMO 1.28.0 装法复核） | MERGED | — | 4489 字 | `global-heredoc` | 0 |
| 34 | 文档：0-6 视频链路逐段复跑留痕 + README 出门条件对齐总纲（处置独立核查） | MERGED | — | 4163 字 | `prior-heredoc` | 0 |
| 35 | 文档：Issue 只管提——放宽任务粒度/拆小要求，明确「Issue 与 PR 不对应」 | MERGED | — | 3680 字 | `prior-heredoc` | 0 |
| 42 | 文档：手册/总纲 D1 期残留口径改到 D1′、统一版本戳、重写 Issue 模板 | MERGED | — | 5510 字 | `Write-tool-global` | 0 |
| 45 | 文档：旧分工表 W0–W10 判定迁入分工表并删除旧表、补手册→证据层引用链、修 L2 交付物名 | MERGED | — | 5841 字 | `Write-tool-global` | 0 |
| 48 | 文档：hubflow-plan/02、03 补「未并入」状态段、修 99 假声明、溯源孤儿判定（含两条裁定 Issue） | MERGED | — | 5705 字 | `Write-tool` | 0 |
| 49 | 文档：修手册 BPR 行程时间函数量纲错误（t⁰·[1+α(x/c)^β] → t⁰·(1+α·x^β)，Issue #46） | MERGED | — | 4581 字 | `Write-tool` | 0 |
| 50 | 文档：执行 #47 裁定——hubflow-plan/02 标「暂不并入」、03 标「参考稿」（含两条连带小项） | MERGED | — | 4226 字 | `Write-tool` | 0 |
| 51 | 接口：W0 骨架——traffic.py 接口层 + 一键脚本 + 路由注册现状说明（Issue #40） | CLOSED | — | 4083 字 | `Write-tool` | 0 |
| 53 | 前端:态势大屏 M1——ui-vue 工程落位 + /dashboard 三栏页 + traffic mock/SSE(Issue #52) | MERGED | — | 5144 字 | `prior-heredoc` | 4 |
| 56 | 前端:感知层检测画面页——/perception 示例画面+检测框叠加+双链路指标快照(Issue #54) | CLOSED | — | 3761 字 | `edit-cmd:disk:C:/Users/ou/AppData/Local/Temp/p56_body_new.md` | 1 |
| 57 | 文档:决策层四页运行核验台账 + 管理端三层路由总览(Issue #55) | CLOSED | — | 1372 字 | `Write-tool` | 0 |
| 58 | 文档：管理端改「新建 Vue 3 工程」口径，删除复用现有工程表述；团队记录抹除本机绝对路径 | MERGED | — | 1403 字 | `Write-tool` | 0 |
| 60 | 决策层:决策工作台页 /decision——处置工作流+因素置位+同化状态+效果对比(Issue #59) | MERGED | — | 3761 字 | `edit-cmd:disk:C:/Users/ou/AppData/Local/Temp/p56_body_new.md` | 0 |
| 62 | 前端:大屏 SUMO 真值预览——OSM 真路网底图 + TraCI 车辆真值接入 mock 车辆快照(Issue #61) | CLOSED | — | 3148 字 | `edit-cmd:same-cmd-heredoc` | 1 |
| 63 | 定位：高德两把 Key 已申请并实测可用，进度表同步 | MERGED | — | 1267 字 | `prior-heredoc` | 1 |
| 64 | 感知层:YOLO 路面监控页 + 感知演示服务——真实样本视频检测流回放(帧播放器+逐帧检测框/轨迹+通道切换+实时统计)+ video/twi | MERGED | — | 3955 字 | `disk:C:/Users/ou/AppData/Local/Temp/p56_new_pr_body.md` | 0 |
| 65 | 前端:大屏 SUMO 真值预览——OSM 真路网底图 + TraCI 车辆真值接入 mock 车辆快照(Issue #61) | MERGED | — | 3378 字 | `disk:C:/Users/ou/AppData/Local/Temp/p62_new_pr_body.md` | 0 |
| 67 | 文档：搬迁后清洗本机绝对路径（5 文件 12 处 （本机路径已隐去） 盘符路径 → 仓库相对路径表述） | MERGED | — | 8670 字 | `edit-cmd:Write-tool` | 1 |
| 69 | 前端:拥挤度热力页 /heat(可切拥挤指数视图)+ 决策层四处判定口径对齐(手册 §11.2)(Issue #66) | MERGED | — | 4912 字 | `Write-tool-global` | 0 |
| 70 | 前端:PR #69 合入后修复——4 路独立审查 + 浏览器实测 10 项(状态机串台/派生键残留/布局叠压/口径不实)(Issue #66) | MERGED | — | 135 字 | `Write-tool` | 1 |
| 72 | 前端:四页按设计稿整体重做——TDesign Light 配色迁移 + 接口面按页面重新规划(Issue #71) | MERGED | — | 4190 字 | `view-reconstruct:recovered_bodies/pr72.md` | 0 |
| 74 | 前端：站点包层——第二个站接入管理端，实测手册 §8.4「换站只改配置」(Issue #73) | MERGED | — | 5441 字 | `Write-tool` | 0 |
| 76 | 前端:演示前四页浏览器实测修复——热力矩阵列数/数据源死控件/判级口径/因素时效(Issue #75) | MERGED | — | 4546 字 | `edit-cmd:disk:C:/Users/ou/AppData/Local/Temp/pr75.md` | 0 |
| 78 | 前端:Web 收敛为三层 3 页——感知层/决策层/监控大屏(热力并入大屏,决策新增加决策可视化)(Issue #77) | MERGED | — | 5671 字 | `prior-heredoc` | 1 |
| 79 | 孪生：work/twin/ 骨架 + samples 样例 + 像素轨迹补时间戳（Issue #38） | MERGED | — | 9142 字 | `view-json` | 1 |
| 82 | (标题未取到) | MERGED | — | 9371 字 | `view-reconstruct:recovered_bodies/pr82.md` | 4 |
| 84 | 孪生：W0 骨架六处输入校验与诊断补齐（Issue #83，PR #79 兜底审待办） | MERGED | — | 3627 字 | `prior-heredoc` | 0 |
| 87 | 文档：新增「填表报告」——每次提交留一行「哪张表第几版 → 哪个产物」，门禁升级为七组（Issue #86） | MERGED | — | 6295 字 | `prior-heredoc` | 0 |
| 90 | 文档：Issue #44 收口——一期只申请高德一家，百度留二期备选；Key 安全设置与配额状态登记 | MERGED | — | 5002 字 | `Write-tool` | 0 |
| 92 | 文档：填表报告 `结果` 增补第五种取值「占位」+ 门禁第 7 组同步（Issue #91） | MERGED | — | 4314 字 | `prior-heredoc` | 2 |
| 93 | 文档：表格模板实体 T1~T8 下发 + 共享盘口径收窄为「只放表格与记录」（Issue #43） | OPEN | — | 6022 字 | `prior-heredoc` | 0 |
| 95 | 决策：T1/T2 转换脚本骨架——表格 → points.json / network.json 属性补录（Issue #41） | OPEN | — | 0 字 | `未取到` | 0 |

## 五、怎么用

1. **要查历史讨论原文** → 本目录按编号翻（正文 + 评论；行内审查意见不可恢复）。
2. **要接着做没做完的活** → 迁移时仍 OPEN 的 11 条（#36 / #37 / #41 / #43 / #68 / #80 / #81 / #85 / #88 / #89 / #94）
   已在 Gitee 侧重建为新单，正文开头标了「对应 GitHub 旧 #NN」。
3. **要看某条结论有没有落地** → 仍以 [`../技术方案与实施手册.md`](../技术方案与实施手册.md) 修订表、
   [`../分工表.md`](../分工表.md)、[`../填表报告.md`](../填表报告.md) 三份台账为准（本目录只是原文，不承担结论）。
