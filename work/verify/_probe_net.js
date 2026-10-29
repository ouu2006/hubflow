/**
 * _probe_net.js —— 勘察站点包几何：`net` 里每段有哪些字段、coords 在哪、
 * 以及方向层要素（渲染出来的）属性能不能和 segment_id 对上。
 */
const comp = V.allComponents().find((c) => c.setupState && 'net' in c.setupState);
const net = comp ? comp.setupState.net : null;
const segs = Array.isArray(net) ? net : (net && net.value) || [];
const sample = segs.slice(0, 3).map((s) => ({ keys: Object.keys(s), segment_id: s.segment_id, dir: s.direction ?? null, from: s.from_node, to: s.to_node, n: (s.coords || []).length, len: s.length_m }));
const map = V.getMap();
const rendered = (() => { try { return map.queryRenderedFeatures({ layers: ['hubflow-direction-marker'] }).map((f) => ({ props: f.properties, geom: f.geometry.coordinates })) } catch (e) { return 'ERR:' + e.message } })();
const lineLayers = map.getStyle().layers.filter((l) => l.type === 'line').map((l) => ({ id: l.id, src: l.source }));
// 站点包坐标范围（用于钉相机）
let minLon = Infinity, maxLon = -Infinity, minLat = Infinity, maxLat = -Infinity;
for (const s of segs) for (const c of (s.coords || [])) {
  minLon = Math.min(minLon, c[0]); maxLon = Math.max(maxLon, c[0]);
  minLat = Math.min(minLat, c[1]); maxLat = Math.max(maxLat, c[1]);
}
return {
  segCount: segs.length,
  sample,
  lineLayers,
  renderedCount: Array.isArray(rendered) ? rendered.length : rendered,
  renderedSample: Array.isArray(rendered) ? rendered.slice(0, 3) : null,
  bounds: [minLon, minLat, maxLon, maxLat],
};
