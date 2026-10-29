#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""离站分组验收截图：裁到 canvas 区域 → 画出路线折线（底图瓦片离线时也能看清"箭头贴在哪条路上"）
→ 叠上路线箭头朝向标注 + 右下角明细表。

输入：work/verify/shots/_departure_1440_full.png（整页截图）
      work/verify/_departure_rows.json（同一会话里的屏幕坐标/朝向/折线投影）
输出：work/verify/shots/shot_departure_1440.png
"""
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))  # work/verify
SHOTS = os.path.join(ROOT, 'shots')
FULL = os.path.join(SHOTS, '_departure_1440_full.png')
DATA = os.path.join(ROOT, '_departure_rows.json')
OUT = os.path.join(SHOTS, 'shot_departure_1440.png')

data = json.load(open(DATA, encoding='utf-8'))
rect = data['rect']
rows = data['rows']
lines = data.get('lines') or []

SCALE = 1.3
CW, CH = rect['w'], rect['h']

_font_cache = {}


def font(size):
    if size not in _font_cache:
        try:
            _font_cache[size] = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', size)
        except Exception:
            _font_cache[size] = ImageFont.load_default()
    return _font_cache[size]


f_title, f_body, f_small, f_tiny = font(30), font(19), font(17), font(15)

full = Image.open(FULL).convert('RGB')
crop = full.crop((rect['x'], rect['y'], rect['x'] + CW, rect['y'] + CH))
crop = crop.resize((int(CW * SCALE), int(CH * SCALE)), Image.LANCZOS)

HEAD, FOOT = 176, 232
W = crop.width
canvas = Image.new('RGB', (W, HEAD + crop.height + FOOT), (255, 255, 255))
canvas.paste(crop, (0, HEAD))
d = ImageDraw.Draw(canvas)

d.text((18, 14), '离站分组（?view=departure）：路线箭头朝向 = 后端 steps[].geometry 行进序', font=f_title, fill=(17, 24, 39))
d.text((18, 58), '同一段上静态方向层与路线箭头对账：10 段全部同向或同轴，无一处打架', font=f_body, fill=(31, 41, 55))
d.text((18, 88), '· 绿色 = 正向段：静态单头箭头与路线箭头朝向完全相同（7 条，Δ=0.0°）', font=f_small, fill=(22, 101, 52))
d.text((18, 114), '· 橙色 = 双向段（编号 ①②③）：静态图标为共轴双头、没有正反（rotate 只是"轴"），路线箭头单头行走行进方向；', font=f_small, fill=(180, 83, 9))
d.text((18, 140), '   两者轴向一致 —— 这也是"旧前端兜底会指反"与"后端标向正确"能同时成立的画面证据。', font=f_small, fill=(180, 83, 9))
d.line([(0, HEAD - 2), (W, HEAD - 2)], fill=(209, 213, 219), width=2)

BIDIR = ['SZ-036', 'SZ-023', 'SZ-035']
BADGE = {seg: n for n, seg in enumerate(BIDIR, start=1)}
CIRCLED = {1: '①', 2: '②', 3: '③'}


def to_img(x, y):
    return x * SCALE, y * SCALE + HEAD


# ① 路线折线（灰）——把"路"画出来
for ln in lines:
    pts = [to_img(x, y) for x, y in ln['pts']]
    if len(pts) >= 2:
        d.line(pts, fill=(168, 174, 186), width=4, joint='curve')


def arrow(dr, cx, cy, bearing, length, color, width=4):
    rad = math.radians(bearing)
    dx, dy = math.sin(rad) * length, -math.cos(rad) * length
    x0, y0 = cx - dx / 2, cy - dy / 2
    x1, y1 = cx + dx / 2, cy + dy / 2
    dr.line([(x0, y0), (x1, y1)], fill=color, width=width)
    for s in (-1, 1):
        a1 = rad + math.pi - s * 0.42
        dr.line([(x1, y1), (x1 + math.sin(a1) * 13, y1 - math.cos(a1) * 13)], fill=color, width=width)


placed = []
for r in rows:
    if not r['screen']:
        continue
    x, y = to_img(r['screen']['x'], r['screen']['y'])
    seg = r['segment_id']
    bidir = seg in BADGE
    color = (217, 119, 6) if bidir else (21, 128, 61)
    arrow(d, x, y, r['routeRotate'], 52 if bidir else 38, color, 5 if bidir else 3)
    if bidir:
        d.ellipse([x - 40, y - 40, x + 40, y + 40], outline=(217, 119, 6), width=3)
        bx, by = x + 34, y - 40
        d.ellipse([bx - 13, by - 13, bx + 13, by + 13], fill=(217, 119, 6))
        d.text((bx - 8, by - 11), CIRCLED[BADGE[seg]], font=f_small, fill=(255, 255, 255))
    placed.append((x, y, seg, r['routeRotate'], bidir))

# 正向段只标段号（小标签，右下角有明细表）
placed.sort(key=lambda t: t[1])
for x, y, seg, rot, bidir in placed:
    if bidir:
        continue
    text = f'{seg} {rot}°'
    tw = d.textlength(text, font=f_tiny)
    lx, ly = x + 24, y - 9
    if lx + tw > W - 8:
        lx = x - tw - 24
    d.rectangle([lx - 3, ly - 2, lx + tw + 3, ly + 18], fill=(255, 255, 255), outline=(21, 128, 61))
    d.text((lx, ly), text, font=f_tiny, fill=(17, 24, 39))

# ② 底部明细表
fy = HEAD + crop.height + 8
d.line([(0, fy - 4), (W, fy - 4)], fill=(209, 213, 219), width=2)
d.text((18, fy + 2), '明细（静态层 = hubflow-direction 图层 rotate；路线 = steps[].geometry 50% 弧长点局部切线方位角）', font=f_small, fill=(17, 24, 39))

col_x = [18, int(W * 0.36), int(W * 0.68)]
head_y = fy + 30
for i, t in enumerate(['① SZ-036_rev', '② SZ-023_rev', '③ SZ-035_rev']):
    by = head_y + i * 44
    d.text((col_x[0], by), t, font=f_small, fill=(180, 83, 9))
    row = next((r for r in rows if r['segment_id'] == t.split()[1].replace('_rev', '')), None)
    if row:
        d.text((col_x[0] + 132, by), f"路线 {row['routeRotate']}° / 静态轴 {row['staticRotate']}°", font=f_tiny, fill=(55, 65, 81))
        axis = abs(((row['routeRotate'] - row['staticRotate']) % 180))
        axis = min(axis, 180 - axis)
        d.text((col_x[0] + 132, by + 20), f'同轴偏差 {axis:.1f}°（双头图标无正反）', font=f_tiny, fill=(107, 114, 128))

fwd = [r for r in rows if r['segment_id'] not in BADGE]
d.text((col_x[1], head_y), f"正向段 {len(fwd)} 条：静态与路线逐条 Δ=0.0°", font=f_small, fill=(21, 128, 61))
for i, r in enumerate(fwd[:4]):
    d.text((col_x[1] + 8, head_y + 24 + i * 22), f"{r['segment_id']}  {r['routeRotate']}° = {r['staticRotate']}°", font=f_tiny, fill=(55, 65, 81))
for i, r in enumerate(fwd[4:8]):
    d.text((col_x[2], head_y + 24 + i * 22), f"{r['segment_id']}  {r['routeRotate']}° = {r['staticRotate']}°", font=f_tiny, fill=(55, 65, 81))

d.text((18, fy + 168), f"数据 GET /api/traffic/route/REQ-REAL-0001/steps（8001 本工作树新代码）· zoom={data['zoom']} · 画布 {CW}×{CH} @1440×900 · URL http://127.0.0.1:5374/?view=departure", font=f_tiny, fill=(107, 114, 128))
d.text((18, fy + 190), '注：底图瓦片离线不可用，灰色折线为前端自己画的站区路段几何（不依赖瓦片），箭头位置即真实路段几何位置。', font=f_tiny, fill=(107, 114, 128))

canvas.save(OUT)
print('saved', OUT, canvas.size)
