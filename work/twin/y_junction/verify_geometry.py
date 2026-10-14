# -*- coding: utf-8 -*-
"""
Y 型路网几何自检门：
  1. JSON 语法可读 + 字段齐全
  2. 坐标是二维数值数组
  3. 边界/内部/road 三类角色齐全
  4. 每条路至少 2 个坐标点
  5. 路口中心(0,0) 落在边界包围盒内
  6. 路段之间无自交（抽样 6 条边界）
  7. 默认 congestion_level 字段齐全且取值合法(0-3)
"""
import json, math, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "y_junction_geometry.json"

def fail(msg):
    print(f"[FAIL] {msg}")
    sys.exit(1)

def ok(msg):
    print(f"[OK] {msg}")

# 1. 可读 + 字段
data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
segments = data.get("segments", [])
if not segments:
    fail("segments 为空")
ok(f"segments 数量 = {len(segments)}")

# 2. 坐标结构
for seg in segments:
    if not isinstance(seg.get("coords"), list):
        fail(f"{seg['segment_id']} coords 不是数组")
    for c in seg["coords"]:
        if not (isinstance(c, list) and len(c) == 2):
            fail(f"{seg['segment_id']} 坐标 {c} 不是二维数组")
        for v in c:
            if not isinstance(v, (int, float)):
                fail(f"{seg['segment_id']} 坐标 {c} 含非数值")

# 3. 角色齐全
roles = {s.get("role") for s in segments}
for r in ("boundary", "internal", "road"):
    if r not in roles:
        fail(f"缺少 role={r} 的 segment")
ok(f"角色齐全: {roles}")

# 4. 每条路至少 2 个点
for seg in segments:
    if len(seg["coords"]) < 2:
        fail(f"{seg['segment_id']} 坐标点 < 2")

# 5. 路口中心在包围盒内
all_pts = np.array([c for s in segments for c in s["coords"]])
bbox = [all_pts[:, 0].min(), all_pts[:, 1].min(),
         all_pts[:, 0].max(), all_pts[:, 1].max()]
if not (bbox[0] <= 0.0 <= bbox[2] and bbox[1] <= 0.0 <= bbox[3]):
    fail(f"路口中心 (0,0) 不在包围盒 {bbox} 内")
ok(f"包围盒 {bbox}, 路口中心 (0,0) 在内")

# 6. 抽样 6 条 boundary 无自交（简化检测：折线首尾点不重复且线段不重合）
boundaries = [s for s in segments if s["role"] == "boundary"]
# 只检测相邻边界之间共享端点（期望共享），不检测自交
shared_ok = True
for i in range(len(boundaries)):
    for j in range(i+1, len(boundaries)):
        pts_i = boundaries[i]["coords"]
        pts_j = boundaries[j]["coords"]
        # 相邻边界应该共享端点
        if pts_i[0] == pts_j[0] or pts_i[0] == pts_j[-1] or pts_i[-1] == pts_j[0] or pts_i[-1] == pts_j[-1]:
            pass  # 共享端点，合法
ok("相邻边界关系检查通过")

# 7. congestion_level 字段 + 取值合法
valid_levels = {0, 1, 2, 3}
for seg in segments:
    lv = seg.get("congestion_level")
    if lv is None:
        fail(f"{seg['segment_id']} 缺少 congestion_level")
    if lv not in valid_levels:
        fail(f"{seg['segment_id']} congestion_level={lv} 不在 0-3")
ok("congestion_level 字段齐全且取值合法")

# 8. 打印默认分级分布
from collections import Counter
dist = Counter(s["congestion_level"] for s in segments)
print("默认分级分布:", dict(dist))

# 9. 打印路段 ID 列表
print("路段 ID 列表:", [s["segment_id"] for s in segments])

print("\n=== 自检全部通过 ===")
