const m = V.map;
const ids = m.getStyle().layers.map(l => l.id);
const dir = ids.filter(i => /direction|route-arrow/i.test(i));
const info = dir.map(id => ({ id, type: m.getLayer(id).type, vis: m.getLayoutProperty(id, 'visibility') ?? 'visible' }));
return { total: ids.length, dir };
