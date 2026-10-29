/**
 * _measure_body.js —— 页面内测量主体（由 cdp_measure.mjs 以 `(async () => { ... })()` 执行）。
 *
 * 输入：可选全局 `__PIN__`（{center, zoom}），为空则用应用自己的取景。
 * 输出：纯 JSON（cam / layout / rows / 汇总误差）。
 *
 * 校验口径（每条都写清「为什么这样比」）：
 *   ① 位置：方向层要素的坐标 vs 我用**独立实现**重算的 50% 弧长点，`map.project()` 成 CSS px 后取欧氏距离。
 *      为什么不是「到端点距离的一半」：弯道上中点不等于弦中点，必须按弧长。
 *   ② 朝向：`properties.rotate`（= icon-rotate 的取值，orientation 已在 MapLibre 里） vs
 *      我独立重算的「行进切线方位角」（backward 段 +180°，因为几何 from/to 与行车方向相反）。
 *   ③ 屏幕朝向：`icon-rotation-alignment: map` ⇒ 屏幕角 = 数据角 − map.bearing；bearing=0 时两者相等，
 *      非 0 时用它验「旋转地图后箭头是否仍贴合路面」。
 *   ④ 尺寸/偏移：dump `icon-size` 表达式与 `icon-offset`（必须是 null）= 分辨率无关的结构性证据。
 */
const pin = (typeof window.__PIN__ !== 'undefined') ? window.__PIN__ : null;
const map = V.getMap();
if (!map) return { ok: false, reason: 'map 实例没拿到' };

const settle = (ms) => new Promise((res) => {
  let done = false;
  const fin = () => { if (!done) { done = true; res() } };
  try { if (map.loaded() && map.isStyleLoaded()) { fin(); return } } catch (e) {}
  map.once('idle', fin);
  setTimeout(fin, ms);
});

if (pin) {
  map.jumpTo({ center: pin.center, zoom: pin.zoom, bearing: pin.bearing ?? 0, pitch: pin.pitch ?? 0 });
  await settle(9000);
}

// —— 站点包几何（方向层的唯一几何来源：MapLibreViewer 的 `net`）——
const comp = V.allComponents().find((c) => c.setupState && 'net' in c.setupState);
const netRaw = comp ? comp.setupState.net : null;
const segs = Array.isArray(netRaw) ? netRaw : (netRaw && netRaw.value) || [];
const coordsOf = new Map();
for (const s of segs) if (s && s.segment_id && Array.isArray(s.coords) && s.coords.length >= 2) coordsOf.set(s.segment_id, s.coords.map((c) => [c[0], c[1]]));
const nameOf = new Map(segs.map((s) => [s.segment_id, s.name || null]));

// —— 渲染出来的方向要素（真在屏幕上的那批）——
let rendered = [];
try { rendered = map.queryRenderedFeatures({ layers: ['hubflow-direction-marker'] }) } catch (e) { rendered = [] }
const seen = new Set();
const dirFeats = [];
for (const f of rendered) {
  const sid = f.properties && f.properties.segment_id;
  if (!sid || seen.has(sid)) continue;
  seen.add(sid);
  dirFeats.push({ segment_id: sid, rotate: f.properties.rotate, dir_kind: f.properties.dir_kind, icon: f.properties.icon, lonlat: f.geometry.coordinates });
}
// 兜底：渲染要素不全时（比如被视口裁掉），用 source query 拿全量
if (!dirFeats.length) {
  try {
    for (const f of map.querySourceFeatures('hubflow-direction')) {
      const sid = f.properties && f.properties.segment_id;
      if (!sid || seen.has(sid)) continue;
      seen.add(sid);
      dirFeats.push({ segment_id: sid, rotate: f.properties.rotate, dir_kind: f.properties.dir_kind, icon: f.properties.icon, lonlat: f.geometry.coordinates });
    }
  } catch (e) {}
}

const cam = {
  center: map.getCenter().toArray(), zoom: map.getZoom(), bearing: map.getBearing(), pitch: map.getPitch(),
  canvas: [map.getCanvas().clientWidth, map.getCanvas().clientHeight],
  inner: [window.innerWidth, window.innerHeight], dpr: window.devicePixelRatio,
};

const LAYER = 'hubflow-direction-marker';

// 方向层在**当前 zoom** 下的实得样式值（业主那类"进站看不见箭头"的问题就看这两个数：
// icon-opacity 是淡出曲线，natural 取景 zoom 落进 <15.0 就是全透明）。
// 只解 linear / exponential 两种 interpolate（本项目用的就这两种），不引第三方库。
function evalZoomExpr(expr, z) {
  if (typeof expr === 'number') return expr;
  if (!Array.isArray(expr) || expr[0] !== 'interpolate') return null;
  const interp = expr[1];
  const stops = [];
  for (let i = 3; i + 1 < expr.length; i += 2) stops.push([expr[i], expr[i + 1]]);
  if (!stops.length) return null;
  if (z <= stops[0][0]) return stops[0][1];
  if (z >= stops[stops.length - 1][0]) return stops[stops.length - 1][1];
  for (let i = 1; i < stops.length; i++) {
    if (z <= stops[i][0]) {
      const [z0, v0] = stops[i - 1];
      const [z1, v1] = stops[i];
      let t = (z - z0) / (z1 - z0);
      if (Array.isArray(interp) && interp[0] === 'exponential') {
        const base = interp[1] || 1;
        t = base === 1 ? t : (Math.pow(base, t) - 1) / (base - 1);
      }
      return v0 + (v1 - v0) * t;
    }
  }
  return null;
}

const opacityExpr = (() => { try { return map.getPaintProperty(LAYER, 'icon-opacity') ?? null } catch (e) { return null } })();
const sizeExpr = map.getLayoutProperty(LAYER, 'icon-size');

const layout = {
  iconSize: sizeExpr,
  iconRotate: map.getLayoutProperty(LAYER, 'icon-rotate'),
  iconOffset: map.getLayoutProperty(LAYER, 'icon-offset') ?? null,
  iconAnchor: map.getLayoutProperty(LAYER, 'icon-anchor') ?? null,
  iconRotationAlignment: map.getLayoutProperty(LAYER, 'icon-rotation-alignment') ?? null,
  iconAllowOverlap: map.getLayoutProperty(LAYER, 'icon-allow-overlap') ?? null,
  visibility: map.getLayoutProperty(LAYER, 'visibility') ?? null,
  iconOpacityExpr: opacityExpr,
  iconOpacityAtZoom: evalZoomExpr(opacityExpr, map.getZoom()),
  iconSizeAtZoom: evalZoomExpr(sizeExpr, map.getZoom()),
};

// 地图容器在**整页**里的位置：map.project() 给的是容器内坐标，截整页时要把这个原点加上，
// 否则裁出来的窗口会整体偏一个容器原点（我第一版就踩了这个坑）。
const rect = map.getContainer().getBoundingClientRect();
const containerRect = { x: rect.left + window.scrollX, y: rect.top + window.scrollY, w: rect.width, h: rect.height };

// 站点包坐标范围（钉相机用；取所有段顶点的中位数，抗个别离群点）
let siteCenter = null;
{
  const pts = [];
  for (const cs of coordsOf.values()) for (const c of cs) pts.push(c);
  if (pts.length) {
    const med = (a) => { const s = [...a].sort((x, y) => x - y); return s[Math.floor(s.length / 2)] };
    siteCenter = [med(pts.map((p) => p[0])), med(pts.map((p) => p[1]))];
  }
}

const rows = [];
for (const f of dirFeats) {
  const coords = coordsOf.get(f.segment_id) || null;
  const arrowPx = map.project(f.lonlat);
  const row = {
    segment_id: f.segment_id,
    name: nameOf.get(f.segment_id) || null,
    dir_kind: f.dir_kind,
    icon: f.icon,
    rotate_data: f.rotate,
    arrow_lonlat: f.lonlat,
    arrow_px: [arrowPx.x, arrowPx.y],
  };
  if (coords) {
    const { total } = V.lens(coords);
    const mid = V.pointAt(coords, total / 2);
    const midPx = map.project(mid);
    const tangent = V.tangentAt(coords, 0.5, 15);
    const shortBidir = f.dir_kind === 'bidirectional' && total < 25;
    const expectedRotate = shortBidir ? 0
      : f.dir_kind === 'backward' ? (tangent + 180) % 360
      : tangent;
    row.length_m = total;
    row.coords_n = coords.length;
    row.mid_lonlat = mid;
    row.mid_px = [midPx.x, midPx.y];
    row.d_pos_px = Math.hypot(arrowPx.x - midPx.x, arrowPx.y - midPx.y);
    row.d_lonlat_deg = Math.hypot(f.lonlat[0] - mid[0], f.lonlat[1] - mid[1]);
    row.tangent_geom_order_deg = tangent;
    row.expected_rotate_deg = expectedRotate;
    row.d_rotate_deg = Math.abs(((f.rotate - expectedRotate + 540) % 360) - 180);
    row.expected_screen_bearing_deg = (expectedRotate - cam.bearing + 360) % 360;
    row.actual_screen_bearing_deg = (f.rotate - cam.bearing + 360) % 360;
    row.d_screen_bearing_deg = Math.abs(((row.actual_screen_bearing_deg - row.expected_screen_bearing_deg + 540) % 360) - 180);
    // 到两端点 / 到弦中点的屏幕距离（跨视口比「相对几何」用）
    const a = map.project(coords[0]);
    const b = map.project(coords[coords.length - 1]);
    const chordMid = map.project([(coords[0][0] + coords[coords.length - 1][0]) / 2, (coords[0][1] + coords[coords.length - 1][1]) / 2]);
    row.arrow_to_coords0_px = Math.hypot(arrowPx.x - a.x, arrowPx.y - a.y);
    row.arrow_to_coordsLast_px = Math.hypot(arrowPx.x - b.x, arrowPx.y - b.y);
    row.span_px = Math.hypot(a.x - b.x, a.y - b.y);
    row.chord_mid_px = [chordMid.x, chordMid.y];
    row.arrow_to_chord_mid_px = Math.hypot(arrowPx.x - chordMid.x, arrowPx.y - chordMid.y);
    // 整条折线的屏幕坐标：Python 端据此在截图上画叠加图（独立复核锥尖朝向）
    row.px_poly = coords.map((c) => { const p = map.project(c); return [p.x, p.y]; });
  }
  rows.push(row);
}

const nums = (k) => rows.map((r) => r[k]).filter((v) => typeof v === 'number');
const max = (k) => (nums(k).length ? Math.max(...nums(k)) : null);

// 每段的「图标中心到段线」的粗略几何：用 50% 点已覆盖；这里额外给出屏幕包围盒，供 Python 裁图用
const bbox = rows.reduce((acc, r) => {
  const [x, y] = r.arrow_px;
  return [Math.min(acc[0], x), Math.min(acc[1], y), Math.max(acc[2], x), Math.max(acc[3], y)];
}, [Infinity, Infinity, -Infinity, -Infinity]);


// ——— 现场 dump：图层配置 + DOM 尺寸（老板要的「同一视野的图层/DOM dump」）———
const layerDump = (() => {
  const style = map.getStyle() || {};
  const keep = (style.layers || []).filter((l) => /direction|route|station/.test(l.id));
  const cnt = (id) => {
    try { const src = map.getSource(id); return src && src._data ? (src._data.features || []).length : null } catch (e) { return null }
  };
  const rectOf = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: +r.x.toFixed(2), y: +r.y.toFixed(2), w: +r.width.toFixed(2), h: +r.height.toFixed(2) };
  };
  return {
    viewport: { inner: [window.innerWidth, window.innerHeight], dpr: window.devicePixelRatio },
    containerRect,
    canvas: {
      attr: [map.getCanvas().width, map.getCanvas().height],
      css: [map.getCanvas().clientWidth, map.getCanvas().clientHeight],
    },
    cam: {
      center: map.getCenter().toArray(), zoom: map.getZoom(),
      bearing: map.getBearing(), pitch: map.getPitch(),
    },
    layers: keep.map((l) => ({
      id: l.id, type: l.type, source: l.source, sourceLayer: l['source-layer'] ?? null,
      minzoom: l.minzoom ?? null, maxzoom: l.maxzoom ?? null,
      layout: l.layout ?? {}, paint: l.paint ?? {},
    })),
    sources: {
      'hubflow-direction': cnt('hubflow-direction'),
      'hubflow-route-arrow': cnt('hubflow-route-arrow'),
      'hubflow-station': cnt('hubflow-station'),
    },
    dom: {
      canvas: rectOf('.maplibregl-canvas'),
      mapContainer: rectOf('#map, .map-canvas, .maplibregl-map'),
      directionLegend: rectOf('.map-legend, .legend'),
    },
    renderedCounts: {
      direction: (() => { try { return map.queryRenderedFeatures({ layers: [LAYER] }).length } catch (e) { return 'ERR:' + e.message } })(),
    },
  };
})();

return {
  ok: true,
  cam, layout, containerRect, layerDump,
  counts: {
    netSegments: coordsOf.size,
    dirFeatures: dirFeats.length,
    withGeom: rows.filter((r) => r.d_pos_px != null).length,
    byKind: rows.reduce((a, r) => { a[r.dir_kind] = (a[r.dir_kind] || 0) + 1; return a }, {}),
  },
  max: {
    d_pos_px: max('d_pos_px'),
    d_rotate_deg: max('d_rotate_deg'),
    d_screen_bearing_deg: max('d_screen_bearing_deg'),
    arrow_to_chord_mid_px: max('arrow_to_chord_mid_px'),
  },
  arrowBBox: bbox,
  siteCenter,
  rows,
};
