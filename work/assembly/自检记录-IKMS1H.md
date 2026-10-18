# IKMS1H 自检记录：处置闭环持久化（真跑输出）

- 生成时间：2026-10-18T14:12:39+0800
- Python：3.12.10；服务端口：**8000**（默认 8000；被占才用 8010）
- 运行态文件（默认）：`work/assembly/data/dispatch.json`（gitignored；见 [data/.gitignore](data/.gitignore)）
- 代码：[traffic.py](traffic.py) · [README.md](README.md) · [selfcheck_ikms1h.py](selfcheck_ikms1h.py)
- 运行产物：使用工作树现有运行产物（不生成 fixture）
- 隔离：默认运行态文件不存在（测试结束后清理）；`--state-path` 用 `out/` 临时文件单独验过

## 一、断言汇总

**60/60 条断言通过** ✅

| # | 场景 | 期望 | 实际 | 结果 |
|---|---|---|---|---|
| 1 | GET /alerts 返回 200 且带信封 | is_simulated=true | True | ✅ |
| 2 | 告警信封带演示态 / 持久化 note | note 含「持久化」 | 告警运行态持久化在 work/assembly/data/dispatch.json（演示态、无真实下发通道；重启不复位）；复位走 POST /api/traf | ✅ |
| 3 | 当前快照有可测的派生告警 | ≥1 条告警 | 1 条 | ✅ |
| 4 | 初始告警状态=待认领 | 待认领 | 待认领 | ✅ |
| 5 | 初始运行态未落盘（干净起点） | alerts 为空 | None | ✅ |
| 6 | 无回执回写被拒（TC-07 顺序） | 409 ACK_NO_DISPATCH | 409 ACK_NO_DISPATCH | ✅ |
| 7 | 被拒后运行态未变 | alerts 为空 | None | ✅ |
| 8 | 下发返回 200 回执 | 200 | 200 | ✅ |
| 9 | 回执 persisted=true（已落盘） | True | True | ✅ |
| 10 | 首次下发 idempotent=false | False | False | ✅ |
| 11 | 首次下发审计 seq=1 | 1 | 1 | ✅ |
| 12 | 运行态文件：状态=处置中 | 处置中 | 处置中 | ✅ |
| 13 | 运行态文件：渠道 / 比例 / 时间 / 操作者齐全 | channels/ratio/dispatch_at/operator 齐全 | {'channels': ['情报板'], 'dispatch_ratio_pct': 30.0, 'dispatch_at': '2026-10-18 14:10:25', 'dispatch_operator': '值班员A'} | ✅ |
| 14 | 重复下发返回 200 且 idempotent=true | 200 idempotent=true | 200 idempotent=True | ✅ |
| 15 | 重复下发沿用首次回执时间（不重复落盘） | 2026-10-18 14:10:25 | 2026-10-18 14:10:25 | ✅ |
| 16 | 重复下发不重复写审计 | 1 | 1 | ✅ |
| 17 | 重启后状态仍在=处置中 | 处置中 | 处置中 | ✅ |
| 18 | 重启后渠道 / 比例 / 操作者 / 回执时间仍在 | 渠道=情报板 / 比例=30 / 操作者=值班员A / 时间不变 | {'channels': ['情报板'], 'dispatch_ratio_pct': 30.0, 'dispatch_operator': '值班员A', 'dispatch_at': '2026-10-18 14:10:25'} | ✅ |
| 19 | 重启后审计仍在（audit_total=1） | 1 | 1 | ✅ |
| 20 | 重启后运行态文件仍含该告警 | 运行态含 AL | ['AL-SZ-005'] | ✅ |
| 21 | 回写返回 200 且状态=已闭环 | 200 已闭环 | 200 已闭环 | ✅ |
| 22 | 回执四项留痕：谁 / 何时 / 做了什么 / 结果 | operator/action/result/at 齐全 | {'operator': '值班员A', 'operator_action': '分流', 'result': '已缓解', 'at': '2026-10-18 14:10:28'} | ✅ |
| 23 | 回写后审计总数=2 | 2 | 2 | ✅ |
| 24 | 终态告警不可再下发 | 409 ALERT_TERMINAL | 409 ALERT_TERMINAL | ✅ |
| 25 | 终态告警不可翻转（换结果回写被拒） | 409 ALERT_TERMINAL | 409 ALERT_TERMINAL | ✅ |
| 26 | 同内容重复回写按幂等回放（200） | 200 idempotent=true | 200 idempotent=True | ✅ |
| 27 | 幂等回放不写新审计（仍为 2） | 2 | 2 | ✅ |
| 28 | 重启后状态仍在=已闭环 | 已闭环 | 已闭环 | ✅ |
| 29 | 重启后回写留痕仍在（谁/何时/动作/结果） | writeback 四项齐全 | {'operator': '值班员A', 'action': '分流', 'result': '已缓解', 'at': '2026-10-18 14:10:28', 'audit_seq': 2} | ✅ |
| 30 | 重启后审计总数=2 | 2 | 2 | ✅ |
| 31 | 重启后终态仍不可下发 | 409 ALERT_TERMINAL | 409 ALERT_TERMINAL | ✅ |
| 32 | POST /alerts/reset 返回 200 reset=true | 200 reset=true | 200 reset=True | ✅ |
| 33 | 复位结果：清掉 1 条 / seed 0 条 / reset_count=1 / audit_seq=3 | cleared=1 seed=0 reset_count=1 audit_seq=3 | {'cleared_alerts': 1, 'seed_alerts': 0, 'reset_count': 1, 'audit_seq': 3} | ✅ |
| 34 | 复位后 GET /alerts 回「待认领」 | 待认领 | 待认领 | ✅ |
| 35 | 复位后运行态文件清空 | alerts 为空 | {} | ✅ |
| 36 | 复位已留审计（最后一条 action=reset） | 末尾 action=reset | reset | ✅ |
| 37 | 重启后仍是复位态（待认领） | 待认领 | 待认领 | ✅ |
| 38 | 重启后 reset_count=1 / 审计总数=3 | reset_count=1 audit_total=3 | {'reset_count': 1, 'audit_total': 3} | ✅ |
| 39 | CLI --reset-state 退出码 0 | 0 | 0 | ✅ |
| 40 | CLI 复位留痕（reset_count=2 / audit_seq=4） | 输出含 reset_count=2 / audit_seq=4 | 已复位处置闭环运行态：work/assembly/data/dispatch.json /   cleared_alerts=0 · seed_alerts=0 · reset_count=2 · audit_seq=4 /   审计总数  | ✅ |
| 41 | CLI 复位后仍是复位态（待认领） | 待认领 | 待认领 | ✅ |
| 42 | CLI 复位后审计总数=4 | 4 | 4 | ✅ |
| 43 | 审计按序可重建：dispatch → ack → reset → reset | ['dispatch','ack','reset','reset'] | ['dispatch', 'ack', 'reset', 'reset'] | ✅ |
| 44 | 审计记录字段齐全（alert_id/动作/渠道/比例/操作者/时间/结果） | 每条都含必需字段 | [['action', 'alert_id', 'at', 'channel', 'operator', 'ratio_pct', 'result', 'segment_id', 'seq', 'status_after']] | ✅ |
| 45 | 审计 store_path 指向默认运行态文件 | work/assembly/data/dispatch.json | work/assembly/data/dispatch.json | ✅ |
| 46 | 审计 limit=1000：生效 limit=1000 且 total 为未截断总数 | limit=1000 / total=4 / returned=4 | {'limit': 1000, 'total': 4, 'returned': 4} | ✅ |
| 47 | 审计 limit=2：returned=2 但 total 仍为未截断 4 | returned=2 / total=4 | {'limit': 2, 'total': 4, 'returned': 2} | ✅ |
| 48 | 持久化层锁内不变量：并发 16 线程终态回写 / 下发全部 409 冲突 | 16/16 均为 ALERT_TERMINAL 冲突 | 16 条结果，exit=0 | ✅ |
| 49 | 持久化层锁内不变量：并发后终态未被翻转（已闭环）且审计不增（=2） | 已闭环 / audit_total=2 | {'final_status': '已闭环', 'audit_total': 2} | ✅ |
| 50 | 持久化层锁内不变量：终态同人同动作同结果仍可幂等回放 | ok=true idempotent=true | {'ok': True, 'idempotent': True} | ✅ |
| 51 | 持久化层锁内不变量：无回执回写（锁内复查）→ ACK_NO_DISPATCH | ACK_NO_DISPATCH | ACK_NO_DISPATCH | ✅ |
| 52 | --state-path 误传已跟踪文件 / 非 .json / 白名单外路径 → 退出码 2 | 5/5 退出码 2 | [2, 2, 2, 2, 2] | ✅ |
| 53 | --state-path 拒绝时目标文件未被改动（README 哈希不变） | 哈希不变 | 不变 | ✅ |
| 54 | --state-path 白名单内 .json 仍可用（--check 退出码 0） | 0 | 0 | ✅ |
| 55 | --state-path 自定义路径：下发写自定义文件 | store_path=work/assembly/out/ikms1h_selfcheck/custom_dispatch.json 且文件存在 | {'status': 200, 'store_path': 'work/assembly/out/ikms1h_selfcheck/custom_dispatch.json', 'file_exists': True} | ✅ |
| 56 | 自定义路径测试不影响默认运行态文件（哈希不变） | 哈希不变 | 不变 | ✅ |
| 57 | 跨页同源（API 层）：大屏 / 决策页两次 GET /alerts 完全一致 | 两次响应逐字段一致 | 一致 | ✅ |
| 58 | 运行态文件被 gitignore 拦截 | git check-ignore 退出码 0 | 0 | ✅ |
| 59 | 运行态文件不在 git 索引 | git ls-files 输出为空 | (空) | ✅ |
| 60 | --check 能读出持久化运行态 | 输出含「处置闭环运行态（持久化）」+ 默认路径 | 输出已包含 | ✅ |

## 二、重启持久化证据（停服务 → 重启 → 再读）

- 被测告警：`AL-SZ-005`（路段 `SZ-005`）；自检从干净初始态开跑。

### 2.1 第一次重启前：下发回执（POST /plan/dispatch，200）

```json
{
  "alert_id": "AL-SZ-005",
  "channel": "情报板",
  "ratio_pct": 30.0,
  "receipt": "情报板已确认",
  "at": "2026-10-18 14:10:25",
  "is_simulated": true,
  "persisted": true,
  "idempotent": false,
  "dispatch_operator": "值班员A",
  "audit_seq": 1,
  "store_path": "work/assembly/data/dispatch.json",
  "note": "回执已写入持久化运行态（重启不复位）。演示态、无真实下发通道。"
}
```

### 2.2 第一次重启后：GET /alerts 读到的同一条告警（状态仍在=处置中）

```json
{
  "alert_id": "AL-SZ-005",
  "segment_id": "SZ-005",
  "segment_name": "SZ-005",
  "level": 3,
  "triggered_by": [
    "v"
  ],
  "first_seen": "2026-10-13 18:42:55",
  "status": "处置中",
  "factor_ids": [],
  "channels": [
    "情报板"
  ],
  "dispatch_at": "2026-10-18 14:10:25",
  "dispatch_ratio_pct": 30.0,
  "dispatch_operator": "值班员A"
}
```

### 2.3 回写后再次重启：GET /alerts 读到终态 + 回写留痕

```json
{
  "alert_id": "AL-SZ-005",
  "segment_id": "SZ-005",
  "segment_name": "SZ-005",
  "level": 3,
  "triggered_by": [
    "v"
  ],
  "first_seen": "2026-10-13 18:42:55",
  "status": "已闭环",
  "factor_ids": [],
  "channels": [
    "情报板"
  ],
  "dispatch_at": "2026-10-18 14:10:25",
  "dispatch_ratio_pct": 30.0,
  "dispatch_operator": "值班员A",
  "writeback": {
    "operator": "值班员A",
    "action": "分流",
    "result": "已缓解",
    "at": "2026-10-18 14:10:28",
    "audit_seq": 2
  }
}
```

### 2.4 复位（POST /alerts/reset）→ 重启后仍为复位态

复位回执：

```json
{
  "reset": true,
  "is_simulated": true,
  "cleared_alerts": 1,
  "seed_alerts": 0,
  "reset_count": 1,
  "audit_seq": 3,
  "persisted": true,
  "store_path": "work/assembly/data/dispatch.json",
  "note": "已清空处置闭环运行态并重放 seed_dispatch（接口层默认 seed 为空 → 所有派生告警回「待认领」）；本次 reset 已写入审计留痕。演示态、无真实下发通道；持久化文件重启不复位，需要再 reset 才会清。"
}
```

复位并重启后的告警：

```json
{
  "alert_id": "AL-SZ-005",
  "segment_id": "SZ-005",
  "segment_name": "SZ-005",
  "level": 3,
  "triggered_by": [
    "v"
  ],
  "first_seen": "2026-10-13 18:42:55",
  "status": "待认领",
  "factor_ids": []
}
```

复位后运行态文件（alerts 已清空、reset 审计保留）：

```json
{
  "schema_version": 1,
  "is_simulated": true,
  "note": "演示态、无真实下发通道；运行态随本文件持久化（重启不复位）",
  "updated_at": "2026-10-18T14:10:32+08:00",
  "alerts": {},
  "seed_dispatch": {},
  "audit": [
    {
      "seq": 1,
      "at": "2026-10-18 14:10:25",
      "action": "dispatch",
      "alert_id": "AL-SZ-005",
      "segment_id": "SZ-005",
      "channel": "情报板",
      "ratio_pct": 30.0,
      "operator": "值班员A",
      "result": null,
      "status_after": "处置中"
    },
    {
      "seq": 2,
      "at": "2026-10-18 14:10:28",
      "action": "ack",
      "alert_id": "AL-SZ-005",
      "segment_id": "SZ-005",
      "channel": null,
      "ratio_pct": null,
      "operator": "值班员A",
      "operator_action": "分流",
      "result": "已缓解",
      "status_after": "已闭环"
    },
    {
      "seq": 3,
      "at": "2026-10-18 14:10:32",
      "action": "reset",
      "alert_id": null,
      "segment_id": null,
      "channel": null,
      "ratio_pct": null,
      "operator": null,
      "result": null,
      "status_after": "initial",
      "cleared_alerts": 1,
      "seed_alerts": 0
    }
  ],
  "audit_seq": 3,
  "audit_total": 3,
  "reset_count": 1
}
```

### 2.5 复位命令 `traffic.py --reset-state` 输出

```text
已复位处置闭环运行态：work/assembly/data/dispatch.json
  cleared_alerts=0 · seed_alerts=0 · reset_count=2 · audit_seq=4
  审计总数 4 条（reset 已留痕）；演示态、无真实下发通道
```

## 三、幂等 / 顺序 / 终态 / 审计专项

- **幂等**：同告警 + 同渠道 + 同比例重复下发 → `idempotent:true`，沿用首次回执时间，审计不重复；
  同人同动作同结果重复回写 → `idempotent:true` 回放既有回执，审计不重复。
- **顺序**：无下发回执先回写 → 409 `ACK_NO_DISPATCH`（TC-07 闭环顺序）；
  终态（已闭环 / 误报）再下发或换结果回写 → 409 `ALERT_TERMINAL`，不可翻转。
- **审计**：每条记录含 seq / at / action / alert_id / segment_id / channel / ratio_pct / operator / result / status_after；ack 另有 operator_action；reset 另有 cleared_alerts / seed_alerts。

审计全量（GET /plan/audit）：

```json
{
  "ts": "2026-10-18T14:10:40+08:00",
  "is_simulated": true,
  "records": [
    {
      "seq": 1,
      "at": "2026-10-18 14:10:25",
      "action": "dispatch",
      "alert_id": "AL-SZ-005",
      "segment_id": "SZ-005",
      "channel": "情报板",
      "ratio_pct": 30.0,
      "operator": "值班员A",
      "result": null,
      "status_after": "处置中"
    },
    {
      "seq": 2,
      "at": "2026-10-18 14:10:28",
      "action": "ack",
      "alert_id": "AL-SZ-005",
      "segment_id": "SZ-005",
      "channel": null,
      "ratio_pct": null,
      "operator": "值班员A",
      "operator_action": "分流",
      "result": "已缓解",
      "status_after": "已闭环"
    },
    {
      "seq": 3,
      "at": "2026-10-18 14:10:32",
      "action": "reset",
      "alert_id": null,
      "segment_id": null,
      "channel": null,
      "ratio_pct": null,
      "operator": null,
      "result": null,
      "status_after": "initial",
      "cleared_alerts": 1,
      "seed_alerts": 0
    },
    {
      "seq": 4,
      "at": "2026-10-18 14:10:37",
      "action": "reset",
      "alert_id": null,
      "segment_id": null,
      "channel": null,
      "ratio_pct": null,
      "operator": null,
      "result": null,
      "status_after": "initial",
      "cleared_alerts": 0,
      "seed_alerts": 0
    }
  ],
  "total": 4,
  "returned": 4,
  "limit": 50,
  "limit_max": 1000,
  "audit_total": 4,
  "reset_count": 2,
  "store_path": "work/assembly/data/dispatch.json",
  "note": "处置闭环审计（只读辅助端点，非契约端点；limit 允许 1~1000，默认 50）：records 为最近 limit 条、total 为过滤后未截断总数、returned 为本次返回条数；每条记录含 alert_id / action / channel / ratio_pct / operator / result / at；演示态、无真实下发通道。"
}
```

## 四、独立审查修复验证（锁内不变量 / 审计 limit / 路径安全）

> 对应独立审查 3 条非阻断发现：终态并发不变量、`audit limit` 截断语义、`--state-path` 目标路径校验。

### 4.1 持久化层锁内不变量（真线程：16 并发 × ack/dispatch）

已闭环告警上并发 16 线程「未改善回写（会把状态改回处置中）」+「再下发」；锁内复查必须全部 409 冲突、终态不被翻转、审计不增：

```json
{
  "outcomes": [
    {
      "ack": "ALERT_TERMINAL",
      "dispatch": "ALERT_TERMINAL",
      "ack_ok": false,
      "dispatch_ok": false
    },
    {
      "ack": "ALERT_TERMINAL",
      "dispatch": "ALERT_TERMINAL",
      "ack_ok": false,
      "dispatch_ok": false
    },
    {
      "ack": "ALERT_TERMINAL",
      "dispatch": "ALERT_TERMINAL",
      "ack_ok": false,
      "dispatch_ok": false
    },
    {
      "ack": "ALERT_TERMINAL",
      "dispatch": "ALERT_TERMINAL",
      "ack_ok": false,
      "dispatch_ok": false
    },
    {
      "ack": "ALERT_TERMINAL",
      "dispatch": "ALERT_TERMINAL",
      "ack_ok": false,
      "dispatch_ok": false
    },
    {
      "ack": "ALERT_TERMINAL",
      "dispatch": "ALERT_TERMINAL",
      "ack_ok": false,
      "dispatch_ok": false
    },
    {
      "ack": "ALERT_TERMINAL",
      "dispatch": "ALERT_TERMINAL",
      "ack_ok": false,
      "dispatch_ok": false
    },
    {
      "ack": "ALERT_TERMINAL",
      "dispatch": "ALERT_TERMINAL",
      "ack_ok": false,
      "dispatch_ok": false
    },
    {
      "ack": "ALERT_TERMINAL",
      "dispatch": "ALERT_TERMINAL",
      "ack_ok": false,
      "dispatch_ok": false
    },
    {
      "ack": "ALERT_TERMINAL",
      "dispatch": "ALERT_TERMINAL",
      "ack_ok": false,
      "dispatch_ok": false
    },
    {
      "ack": "ALERT_TERMINAL",
      "dispatch": "ALERT_TERMINAL",
      "ack_ok": false,
      "dispatch_ok": false
    },
    {
      "ack": "ALERT_TERMINAL",
      "dispatch": "ALERT_TERMINAL",
      "ack_ok": false,
      "dispatch_ok": false
    },
    {
      "ack": "ALERT_TERMINAL",
      "dispatch": "ALERT_TERMINAL",
      "ack_ok": false,
      "dispatch_ok": false
    },
    {
      "ack": "ALERT_TERMINAL",
      "dispatch": "ALERT_TERMINAL",
      "ack_ok": false,
      "dispatch_ok": false
    },
    {
      "ack": "ALERT_TERMINAL",
      "dispatch": "ALERT_TERMINAL",
      "ack_ok": false,
      "dispatch_ok": false
    },
    {
      "ack": "ALERT_TERMINAL",
      "dispatch": "ALERT_TERMINAL",
      "ack_ok": false,
      "dispatch_ok": false
    }
  ],
  "final_status": "已闭环",
  "audit_total": 2,
  "idempotent_replay": {
    "ok": true,
    "idempotent": true
  },
  "fresh_conflict": "ACK_NO_DISPATCH",
  "exit_code": 0
}
```

### 4.2 审计 limit 语义（`total` = 过滤后未截断总数）

```json
{
  "limit_1000": {
    "limit": 1000,
    "total": 4,
    "returned": 4,
    "audit_total": 4
  },
  "limit_2": {
    "limit": 2,
    "total": 4,
    "returned": 2,
    "audit_total": 4
  }
}
```

### 4.3 `--state-path` 安全校验（误传已跟踪文件不会改名覆盖）

```json
{
  "invalid": [
    {
      "state_path": "work/assembly/README.md",
      "exit_code": 2,
      "output_first_line": "参数错误：--state-path 运行态文件必须是 .json（收到 'work/assembly/README.md'）"
    },
    {
      "state_path": "work/assembly/traffic.py",
      "exit_code": 2,
      "output_first_line": "参数错误：--state-path 运行态文件必须是 .json（收到 'work/assembly/traffic.py'）"
    },
    {
      "state_path": "work/assembly/out/state.txt",
      "exit_code": 2,
      "output_first_line": "参数错误：--state-path 运行态文件必须是 .json（收到 'work/assembly/out/state.txt'）"
    },
    {
      "state_path": "work/assembly/not_allowed.json",
      "exit_code": 2,
      "output_first_line": "参数错误：--state-path 运行态文件只允许放在 work/assembly/data / work/assembly/out 下（收到 'work/assembly/not_allowed.json'）"
    },
    {
      "state_path": "docs/数据契约.md",
      "exit_code": 2,
      "output_first_line": "参数错误：--state-path 运行态文件必须是 .json（收到 'docs/数据契约.md'）"
    }
  ],
  "readme_unchanged": true,
  "valid_out_json_exit": 0
}
```

## 五、跨页同源（大屏 / 决策页读同一后端状态）

- API 层：连续两次 `GET /api/traffic/alerts` 逐字段一致：**✅ 是**
- 前端源码（只读引用）：两个页面调同一套 `src/api/traffic.ts` 函数（同一个后端状态，页面刷新 / 切换不丢）：
  - `work/frontend/ui-vue/src/views/dashboard/components/SegmentDispatchCard.vue`：`import { postPlanAck, postPlanDispatch } from '../../../api/traffic'`
  - `work/frontend/ui-vue/src/views/dashboard/components/SegmentDispatchCard.vue`：`const r = await postPlanDispatch({`
  - `work/frontend/ui-vue/src/views/dashboard/components/SegmentDispatchCard.vue`：`const r = await postPlanAck({`
  - `work/frontend/ui-vue/src/views/dashboard/DashboardView.vue`：`getTrafficAlerts,`
  - `work/frontend/ui-vue/src/views/dashboard/DashboardView.vue`：`subscribeTrafficSnapshot,`
  - `work/frontend/ui-vue/src/views/dashboard/DashboardView.vue`：`getTrafficAlerts(),`
  - `work/frontend/ui-vue/src/views/dashboard/DashboardView.vue`：`unsubscribe = subscribeTrafficSnapshot(`
  - `work/frontend/ui-vue/src/views/decision/DecisionView.vue`：`getTrafficAlerts,`
  - `work/frontend/ui-vue/src/views/decision/DecisionView.vue`：`postPlanAck,`
  - `work/frontend/ui-vue/src/views/decision/DecisionView.vue`：`postPlanDispatch,`
- 说明：本机未起 `npm run dev:remote`（前端 dev server），故以同一后端接口的两次独立读取 + 源码同源引用证明「同一份状态」；重启持久化证据见第二节。

## 六、运行态文件不提交（gitignore / git 索引）

- `git check-ignore -v`：`work/assembly/data/.gitignore:4:*	work/assembly/data/dispatch.json`
- `git ls-files` 命中运行态文件：否 ✅

## 七、`--check` 读持久化运行态（输出尾部）

```text
车辆：3 辆
同化断面：2 条（boundary 1 / internal 1）
告警（从快照派生）：1 条
处置闭环运行态（持久化）：work/assembly/data/dispatch.json（存在）
  已落盘告警运行态 0 条 · 审计 4 条（保留最近 1000 条）· 复位 2 次
写端点内存态（factors / scenario 仍是进程内存；--check 是新进程，恒为空）：人工置位 0 条 · 场景注入 未注入

检查完成：缺失的数据源会按三层回落 / 空壳 + note 处理，不报 500。
```

## 八、仓库门禁 doc_gate

- 命令：`python scripts/doc_gate.py`（8 组）
- 首次运行：退出码 **0**
- 复检（本记录写全后）：退出码 **0** ✅ 8/8 通过

```text
门禁根目录：<repo>
受管文件：318 个（已跟踪 318 个，内容取自 git 索引）

[通过] 1/8 编码与换行（UTF-8 无 BOM / LF）（检查 248 个目标）
[通过] 2/8 大文件与禁入类型（检查 318 个目标）
[通过] 3/8 Markdown 相对链接（检查 54 个目标）
[通过] 4/8 JSON 可解析（含数据契约示例）（检查 41 个目标）
[通过] 5/8 密钥扫描（检查 248 个目标）
[通过] 6/8 契约字段命名（snake_case）（检查 15 个目标）
[通过] 7/8 填表报告台账（格式 / 产物覆盖 / 结果语义）（检查 15 个目标）
[注意] docs/填表报告.md:123  `结果` 是「占位」（**T1~T9** → `stations/network.json` / `stations/points.json` / `stations/signal_plan.json` / `stations/demand.json` / `stations/factors.json` / `stations/scenarios.json` / `stations/thresholds.json` / `stations/calibration.json` / `stations/map_source.json`）—— 登记的是「还没有表格出处」的产物（结构骨架 / 运行产物 / 基线）；它只说明**在场**，**不代表数据可用**，不要拿它当「已转」的证据
[注意] docs/填表报告.md:125  `结果` 是「占位」（T1~T9 → `stations/calibration.json`）—— 登记的是「还没有表格出处」的产物（结构骨架 / 运行产物 / 基线）；它只说明**在场**，**不代表数据可用**，不要拿它当「已转」的证据
[注意] docs/填表报告.md:126  `结果` 是「占位」（T1~T9 → `stations/thresholds.json`）—— 登记的是「还没有表格出处」的产物（结构骨架 / 运行产物 / 基线）；它只说明**在场**，**不代表数据可用**，不要拿它当「已转」的证据
[通过] 8/8 任务记录台账（格式 / 结果枚举 / 日期）（检查 120 个目标）

门禁全部通过。
```

## 九、结论与遗留

- 本单完成判定：TC-07（状态可推进 + 四项留痕 + 重启仍在）/ 顺序校验 / 终态不可翻转 / 幂等 / 复位可留痕 / 审计可重建 / 跨页同源（API 层）—— 自检 **60/60** 通过。
- 独立审查 3 条非阻断发现（终态并发不变量 / 审计 limit 截断语义 / `--state-path` 目标路径校验）已修复并纳入断言（见第四节）。
- 遗留：① 运行态是**一进程一文件仓**（JSON，单 worker），多 worker / 并发写库场景留给二期 openGauss；② 大屏 / 决策页真实浏览器联调未在本机跑（无前端 dev server），以 API 层同源 + 源码引用为证；③ `work/frontend/README.md` 的处置闭环章节按 Issue 原文应同步，但本单写入范围限定 `work/assembly/**`，留给前端 owner / 文档 owner 收口。
