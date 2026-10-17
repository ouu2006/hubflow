#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""站点范围登记表读取器（Issue IKM4B4）。

**唯一登记载体**：`work/twin/site-ranges.json`（每站一条记录）。
口径（业主 2026-10-17 最新裁定，见 `work/twin/netpack/README.md`）：
  · 演示范围 `range_m` 与拉取范围 `pull_bbox` **分开登记**（拉取要大一圈，留 boundary 断面）；
  · `range_source` 只取 `manual` / `script` / `ai-assisted`；
  · `script` / `ai-assisted` 只出**候选范围**，写进配置前**必须人工确认**（AI 不直接定范围）；
  · 范围不是官方划定、不报精度数字；几何真值来自 OSM。

本模块只做「读 + 校验 + 取默认值」，**不改配置**（改配置只能人工编辑 JSON）。
换站 = 在 JSON 里加一条记录，脚本一行不改。

用法：
    from site_config import load_site, DEFAULT_CONFIG_PATH
    site = load_site("zhaoqingdong")          # 未指定则取 default_site / 第一条
    site["range_m"], site["anchor_lonlat"]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

#: 仓库根（本文件位于 work/twin/site_config.py）
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT / "work/twin/site-ranges.json"

#: 每条站点记录必须有的字段
REQUIRED_KEYS = (
    "site_id",
    "site_name",
    "anchor_lonlat",
    "range_m",
    "pull_bbox",
    "seg_target",
    "range_source",
    "date",
)
RANGE_SOURCES = ("manual", "script", "ai-assisted")


def _fail(msg: str) -> "NoReturn":  # noqa: F821 —— 仅为类型标注可读
    raise SystemExit(f"❌ site-ranges.json：{msg}")


def load_site_ranges(config_path: str | Path | None = None) -> dict:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        _fail(f"找不到配置文件 {path}（换站先加一条记录，再跑脚本）")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _fail(f"{path} 不是合法 JSON：{exc}")
    sites = data.get("sites")
    if not isinstance(sites, list) or not sites:
        _fail("缺少非空 sites 数组")
    for s in sites:
        miss = [k for k in REQUIRED_KEYS if k not in s]
        if miss:
            _fail(f"{s.get('site_id') or '?'} 缺字段 {miss}")
        if tuple(s["anchor_lonlat"]) and len(s["anchor_lonlat"]) != 2:
            _fail(f"{s['site_id']} anchor_lonlat 必须是 [lon, lat]")
        if len(s["pull_bbox"]) != 4:
            _fail(f"{s['site_id']} pull_bbox 必须是 [min_lon, min_lat, max_lon, max_lat]")
        if s["range_source"] not in RANGE_SOURCES:
            _fail(f"{s['site_id']} range_source={s['range_source']} 不合法（只许 {RANGE_SOURCES}）")
    ids = [s["site_id"] for s in sites]
    if len(ids) != len(set(ids)):
        _fail("site_id 有重复")
    default = data.get("default_site")
    if default and default not in ids:
        _fail(f"default_site={default} 不在 sites 里")
    return data


def load_site(site_id: str | None = None, config_path: str | Path | None = None) -> dict:
    data = load_site_ranges(config_path)
    sites = data["sites"]
    wanted = site_id or data.get("default_site") or sites[0]["site_id"]
    for s in sites:
        if s["site_id"] == wanted:
            return s
    ids = ", ".join(s["site_id"] for s in sites)
    raise SystemExit(f"❌ 配置里没有 site_id={wanted}（现有：{ids}）")


def bbox_wsn(bbox) -> tuple[float, float, float, float]:
    """[min_lon, min_lat, max_lon, max_lat] → (west, south, east, north)。"""
    if len(bbox) != 4:
        raise SystemExit(f"❌ pull_bbox 必须是 4 元组，收到 {bbox}")
    return float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])


def repo_path(rel: str) -> Path:
    """配置里的路径一律相对仓库根。"""
    return (ROOT / rel).resolve()


if __name__ == "__main__":
    site = load_site(sys.argv[1] if len(sys.argv) > 1 else None)
    print(json.dumps(site, ensure_ascii=False, indent=2))
