#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IKM4TE 自检：站点包 Z 的 mock 数据 + GZ 点位「能指回本站路网、形状自洽、口径如实」。

跑（仓库根）：
    python work/frontend/scripts/check_station_data.py
退出码 0 = 全过；1 = 有对不上的项。

检查项（对应 Issue IKM4TE「完成判定」的可机器判定部分）：
  ① 断面/点位/告警/分流/同化引用的段号都能在 61 段真路网里找到（零悬空）；
  ② 断面 role 自洽：boundary/internal 都有；assimilation 里 internal 一律 enabled=false（TC-20 第②项）；
  ③ 告警四态齐全；seedDispatch 的 key 必须是已存在的 alert_id；
  ④ 分流建议引用的目标段存在；场景因素编号合法（F01~F14）；
  ⑤ mock 数据必须带「演示 / 候选 / 待冻结 / 模拟」字样（口径红线：不冒充真实数据）；
  ⑥ 广州南站（GZ）点位：数量恰为 5 落客点 + 4 候客/上客区、id 前缀正确、名称带演示标记、
     坐标落在本站路网包络内、坐标不重合、推荐落客点非悬空（IKM4TE，只校验点位，不套 Z 站九项）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NET_TS = ROOT / "work/frontend/ui-vue/src/station-packs/stationZ.network.ts"
PACK_TS = ROOT / "work/frontend/ui-vue/src/station-packs/stationZ.ts"
GEN_TS = ROOT / "work/frontend/ui-vue/src/station-packs/cameraChannels.generated.ts"
# 广州南站（IKNB9F / 本单补点位）：只校验点位，不套 Z 站那九项（GZ 包没有 Z 站的告警/分流语义）
GZ_NET_TS = ROOT / "work/frontend/ui-vue/src/station-packs/stationGZ.network.ts"
GZ_PACK_TS = ROOT / "work/frontend/ui-vue/src/station-packs/stationGZ.ts"

MOCK_MARKERS = ("演示", "候选", "待冻结", "模拟", "mock", "DEMO")
SCENARIO_KEYS = {"baseline", "rain-peak", "fog-night", "train-burst", "accident-loop"}
ENV_FACTORS = {"F01", "F02", "F03", "F10"}
STATUSES = ("待认领", "处置中", "已闭环", "误报")
# GZ 点位数量（IKM4TE 完成判定：5 落客点 + 4 候客/上客区；删点/漏解析必须报错，不能 fail-open）
EXPECTED_GZ_MARKS = {"dropoffs": 5, "zones": 4}


def block(text: str, field: str) -> str:
    """粗抽 `field: [...]` / `field: {...}` 的块（够本自检用；不追求通用 TS 解析）。"""
    m = re.search(rf"\b{field}:\s*([\[{{])", text)
    if not m:
        return ""
    open_ch = m.group(1)
    close_ch = "]" if open_ch == "[" else "}"
    depth = 0
    for i in range(m.start(1), len(text)):
        ch = text[i]
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[m.start(1): i + 1]
    return ""


def segs_in(text: str) -> set[str]:
    return set(re.findall(r"segment_id:\s*'(SZ-\d+)'", text))


def main() -> int:
    errors: list[str] = []
    net_ids = set(re.findall(r"segment_id:\s*'(SZ-\d+)'", NET_TS.read_text(encoding="utf-8")))
    pack_text = PACK_TS.read_text(encoding="utf-8")
    print(f"[路网] 61 段：{len(net_ids)} 段")

    # ① sections
    sec = block(pack_text, "sections")
    sec_ids = segs_in(sec)
    bad = sorted(sec_ids - net_ids)
    if bad:
        errors.append(f"sections 段号悬空：{bad}")
    if not sec_ids:
        errors.append("sections 为空（IKM4TE 要求落断面 mock 数据）")
    roles = re.findall(r"role:\s*'(boundary|internal)'", sec)
    print(f"[断面] {len(re.findall(r'point_id:', sec))} 条 · boundary {roles.count('boundary')} / internal {roles.count('internal')}")
    if "boundary" not in roles or "internal" not in roles:
        errors.append("sections 必须同时有 boundary / internal 两类回灌角色")

    # ② assimilation
    ass = block(pack_text, "assimilation")
    ass_rows = re.findall(
        r"segment_id:\s*'(SZ-\d+)',\s*role:\s*'(boundary|internal)',\s*enabled:\s*(true|false)",
        ass,
    )
    if len(ass_rows) < 2:
        errors.append("assimilation 至少要有 2 条 mock 记录（边界 + 内部）")
    for sid, role, enabled in ass_rows:
        if sid not in net_ids:
            errors.append(f"assimilation 段号悬空：{sid}")
        if role == "internal" and enabled == "true":
            errors.append(f"{sid} internal 断面 enabled=true（TC-20 第②项：内部断面禁止回灌）")
    ass_boundary = [r for r in ass_rows if r[1] == "boundary"]
    if not ass_boundary:
        errors.append("assimilation 缺 boundary 记录（M1-10 只允许边界断面回灌）")
    print(f"[同化] {len(ass_rows)} 条 · boundary {len(ass_boundary)} / internal {len(ass_rows) - len(ass_boundary)}")

    # ③ alerts
    alerts = block(pack_text, "alerts")
    alert_ids = [a for a in re.findall(r"alert_id:\s*'([^']+)'", alerts) if "AL-" in a]
    st = re.findall(r"status:\s*'([^']+)'", alerts)
    print(f"[告警] {len(alert_ids)} 条 · 状态 {sorted(set(st))}")
    if len(alert_ids) < 4:
        errors.append(f"alerts 至少 4 条（四态各一条），实际 {len(alert_ids)}")
    for a in alert_ids:
        if not a.startswith("DEMO-AL-"):
            errors.append(f"告警 id {a} 未带 DEMO- 前缀（mock 值必须在页面上可辨认）")
    for s in STATUSES:
        if s not in st:
            errors.append(f"alerts 缺状态：{s}")
    bad = sorted(set(re.findall(r"segment_id:\s*'(SZ-\d+)'", alerts)) - net_ids)
    if bad:
        errors.append(f"alerts 段号悬空：{bad}")

    # ④ seedDispatch
    seeds = block(pack_text, "seedDispatch")
    seed_ids = re.findall(r"'((?:DEMO-)?AL-[^']+)':\s*\{", seeds)
    for sid in seed_ids:
        if sid not in alert_ids:
            errors.append(f"seedDispatch 的 key {sid} 不是已存在的 alert_id")
    print(f"[下发] 预置回执 {len(seed_ids)} 条")

    # ⑤ diversion
    div = block(pack_text, "diversion")
    div_keys = re.findall(r"'?(SZ-\d+)'?:\s*\{", div)
    div_targets = re.findall(r"target_segment_id:\s*'(SZ-\d+)'", div)
    for sid in set(div_keys) | set(div_targets):
        if sid not in net_ids:
            errors.append(f"diversion 段号悬空：{sid}")
    print(f"[分流] 建议 {len(div_keys)} 条 · 目标段 {sorted(set(div_targets))}")

    # ⑥ scenarios（必须与 ScenarioInjectPanel 的 applyPreset key 对得上；环境侧只许 F01/F02/F03/F10）
    scen = block(pack_text, "scenarios")
    keys = re.findall(r"key:\s*'([^']+)'", scen)
    factors = re.findall(r"'(F\d{2})'", scen)
    bad_keys = [k for k in keys if k not in SCENARIO_KEYS]
    if bad_keys:
        errors.append(f"scenarios key 与 ScenarioInjectPanel.applyPreset 不匹配：{bad_keys}")
    bad_f = [f for f in factors if f not in ENV_FACTORS]
    if bad_f:
        errors.append(f"scenarios 因素编号越出环境侧（F01/F02/F03/F10）：{bad_f}")
    print(f"[场景] {len(keys)} 条 · key {keys} · 因素 {sorted(set(factors))}")

    # ⑦ 点位 / 场区块存在（且落客点与候客区坐标不得完全重合）
    coords: dict[str, tuple[str, str]] = {}
    for field in ("dropoffs", "zones"):
        blk = block(pack_text, field)
        if not re.search(r"\bid:", blk):
            errors.append(f"{field} 为空（IKM4TE 要求落 mock 点位）")
        else:
            print(f"[点位] {field}: {len(re.findall(r'id:', blk))} 条")
        for rid, lon, lat in re.findall(r"id:\s*'([^']+)'.*?lon:\s*([\d.]+),\s*lat:\s*([\d.]+)", blk):
            coords.setdefault(f"{lon},{lat}", []).append(rid)
    for coord, ids in coords.items():
        if len(ids) > 1:
            errors.append(f"点位坐标重合（图上会叠在一起）：{coord} → {ids}")

    # ⑧ mock 数据必须带「演示 / 候选 / 待冻结 / 模拟 / DEMO」标记（口径红线；检查值本身，不看上方注释）
    for field in ("sections", "alerts", "diversion", "assimilation", "scenarios", "dropoffs", "zones"):
        blk = block(pack_text, field)
        if not any(m in blk for m in MOCK_MARKERS):
            errors.append(f"{field} 的值里找不到「演示/候选/待冻结/模拟/DEMO」标记，疑似冒充真实数据")

    # ⑨ 摄像头生成物段号零悬空（IKMDKY 联动；2026-10-25 起含演示层生成物 Z+GZ 两站）
    gen_ids = set(re.findall(r"segment_id:\s*'(SZ-\d+)'", GEN_TS.read_text(encoding="utf-8")))
    bad = sorted(gen_ids - net_ids)
    if bad:
        errors.append(f"cameraChannels.generated.ts 段号悬空：{bad}")

    DEMO_TS = ROOT / "work/frontend/ui-vue/src/station-packs/demoCameraChannels.generated.ts"
    gz_net_ids = set(re.findall(r"segment_id:\s*'(GZ-\d+)'", GZ_NET_TS.read_text(encoding="utf-8")))
    if not DEMO_TS.exists():
        errors.append("demoCameraChannels.generated.ts 缺失（先跑 gen_station_channels.py）")
    else:
        demo_text = DEMO_TS.read_text(encoding="utf-8")
        demo_sz = set(re.findall(r"segment_id:\s*'(SZ-\d+)'", demo_text))
        demo_gz = set(re.findall(r"segment_id:\s*'(GZ-\d+)'", demo_text))
        bad_sz = sorted(demo_sz - net_ids)
        bad_gz = sorted(demo_gz - gz_net_ids)
        if bad_sz:
            errors.append(f"demoCameraChannels.generated.ts Z 段号悬空：{bad_sz}")
        if bad_gz:
            errors.append(f"demoCameraChannels.generated.ts GZ 段号悬空：{bad_gz}")
        # 口径核对：演示层 + 源台账 = 站点包 channels 总数 = 路段数（每段 1 路）
        ledger_sz = len(re.findall(r"segment_id:\s*'(SZ-\d+)'", GEN_TS.read_text(encoding="utf-8")))
        z_total = ledger_sz + len(demo_sz)
        print(f"[摄像头] Z: 源台账 {ledger_sz} + 演示层 {len(demo_sz)} = {z_total} 路（netpack {len(net_ids)} 段）")
        if z_total != len(net_ids):
            errors.append(f"Z 摄像头 {z_total} 路 ≠ netpack {len(net_ids)} 段（N 段 = N 摄像头口径破了）")
        if len(demo_gz) != len(gz_net_ids):
            errors.append(
                f"GZ 摄像头 {len(demo_gz)} 路 ≠ netpack {len(gz_net_ids)} 段（N 段 = N 摄像头口径破了）"
            )
        else:
            print(f"[摄像头] GZ: 演示层 {len(demo_gz)} 路（netpack {len(gz_net_ids)} 段）")

    # ⑩ 广州南站（GZ）点位自检：id 唯一 · 名称带演示标记 · 坐标落在这个包自己的路网范围内 · 无重合
    #    为什么不复用 ①~⑧：GZ 包还没有 Z 站那套 alerts / diversion / assimilation 演示骨架，
    #    套上去只会得到「GZ 缺告警」这种与本单无关的噪声。这里只钉点位这一件事。
    if not GZ_PACK_TS.exists() or not GZ_NET_TS.exists():
        errors.append("GZ 站点包文件缺失（stationGZ.ts / stationGZ.network.ts）")
    else:
        gz_pack = GZ_PACK_TS.read_text(encoding="utf-8")
        gz_net = GZ_NET_TS.read_text(encoding="utf-8")
        gz_ids = set(re.findall(r"segment_id:\s*'(GZ-\d+)'", gz_net))
        print(f"[GZ 路网] {len(gz_ids)} 段")
        # 路网经纬度包络（点位必须落在范围内，防止手滑写到别的城市）
        pts = [
            (float(lon), float(lat))
            for lon, lat in re.findall(r"\[\s*([\d.]+),\s*([\d.]+)\s*\]", gz_net)
        ]
        if not pts:
            errors.append("GZ 路网里没解析到任何坐标，无法核对点位范围")
        else:
            lons = [p[0] for p in pts]
            lats = [p[1] for p in pts]
            lon_min, lon_max = min(lons), max(lons)
            lat_min, lat_max = min(lats), max(lats)
            print(f"[GZ 范围] lon {lon_min:.5f}~{lon_max:.5f} · lat {lat_min:.5f}~{lat_max:.5f}")
        gz_coords: dict[str, list[str]] = {}
        gz_mark_count = {"dropoffs": 0, "zones": 0}
        for field in ("dropoffs", "zones"):
            blk = block(gz_pack, field)
            marks = re.findall(
                # \bid 防止误匹配 segment_id；name 允许 TS 转义引号（\' / \\）
                r"\bid:\s*'([^']+)',\s*\n\s*name:\s*'((?:[^'\\]|\\.)*)',\s*\n\s*lon:\s*([\d.]+),\s*\n\s*lat:\s*([\d.]+),",
                blk,
            )
            gz_mark_count[field] = len(marks)
            print(f"[GZ 点位] {field}: {len(marks)} 条（应为 {EXPECTED_GZ_MARKS[field]} 条）")
            if len(marks) != EXPECTED_GZ_MARKS[field]:
                errors.append(
                    f"GZ {field} 应为 {EXPECTED_GZ_MARKS[field]} 条，实际 {len(marks)} 条"
                    "（本单要求 5 落客点 + 4 候客/上客区；删点 / 漏解析都必须报错）"
                )
            seen_ids: set[str] = set()
            prefix = "GZ-DROP-" if field == "dropoffs" else "GZ-ZONE-"
            for mark_id, mark_name, lon_s, lat_s in marks:
                if mark_id in seen_ids:
                    errors.append(f"GZ {field} 点位 id 重复：{mark_id}")
                seen_ids.add(mark_id)
                if not mark_id.startswith(prefix):
                    errors.append(f"GZ {field} 点位 id {mark_id} 未用 {prefix} 前缀")
                if not any(m in mark_name for m in MOCK_MARKERS):
                    errors.append(
                        f"GZ {field} 点位 {mark_id} 的名称里找不到「演示」标记，疑似冒充真实点位：{mark_name}"
                    )
                lon, lat = float(lon_s), float(lat_s)
                gz_coords.setdefault(f"{lon},{lat}", []).append(mark_id)
                if pts and not (lon_min <= lon <= lon_max and lat_min <= lat <= lat_max):
                    errors.append(
                        f"GZ {field} 点位 {mark_id} 坐标落在本站路网范围外（{lon},{lat}）：疑似写错站"
                    )
        for coord, ids in gz_coords.items():
            if len(ids) > 1:
                errors.append(f"GZ 点位坐标重合（图上会叠在一起）：{coord} → {ids}")
        # 推荐路线指向的落客点必须真实存在（本单前它是悬空的 'GZ-DROP-EAST'）
        ref = re.search(r"arrival_dropoff_point:\s*'([^']+)'", gz_pack)
        if not ref:
            errors.append("GZ 站点包缺 arrival_dropoff_point")
        else:
            ref_id = ref.group(1)
            defined = set(re.findall(r"id:\s*'(GZ-DROP-[^']+)'", block(gz_pack, "dropoffs")))
            print(f"[GZ 推荐] arrival_dropoff_point = {ref_id}")
            if ref_id not in defined:
                errors.append(
                    f"GZ arrival_dropoff_point={ref_id} 不在 dropoffs 里（悬空引用，前端会显示空窗）："
                    f"已定义 {sorted(defined)}"
                )

    if errors:
        print(f"\n❌ 自检失败：{len(errors)} 项")
        for e in errors:
            print(f"   ❌ {e}")
        return 1
    print("\n✅ 站点包自检通过（Z mock + GZ 点位）：段号零悬空 · 断面 role 自洽 · 告警四态齐 · "
          "分流/场景可解析 · mock 标记齐全 · GZ 恰 5 落客点 + 4 候客/上客区且坐标落在本站包络内")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main())
