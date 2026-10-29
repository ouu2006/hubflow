/**
 * _start_marker_probe.js —— 起点标记口径核对（在真页面里算，不手抄公式）
 *
 * 判据（lead 定，2026-10-29）：
 *   大屏没有 `start_point` 时，起点标记走 `pointAtOffset(coords, offset_m)`；
 *   有 `start_point` 时走后端给的 lon/lat。两条口径必须一致，否则换数据源就错位。
 *   本探针：对同一批 (segment_id, offset_m) 取后端 `start_point`，再在页面里用
 *   `V.pointAt(coords, offset_m)`（与前端 pointAtOffset 同式、同 coords）算一遍，
 *   比较两点距离 < 2 m。
 *
 * 依赖：cdp_eval.mjs 注入的 `V`（page lib）。
 */
  const m = V.getMap()
  if (!m) return { ok: false, error: 'no-map' }
  // 1) 页面自己加载的那份站点包几何（不是仓库文件）：组件树里的 `net`
  const comp = V.allComponents().find((c) => c.setupState && 'net' in c.setupState)
  const netRaw = comp ? comp.setupState.net : null
  const net = Array.isArray(netRaw) ? netRaw : (netRaw && netRaw.value) || []
  if (!net.length) return { ok: false, error: 'no-net' }
  const coordsById = {}
  const nodesById = {}
  for (const s of net) {
    if (s && s.segment_id && Array.isArray(s.coords)) {
      coordsById[s.segment_id] = s.coords
      nodesById[s.segment_id] = { from: s.from_node, to: s.to_node }
    }
  }
  // 行进朝向：方向层要素上的 dir_kind（backward = reverse）
  const kindById = {}
  const dirData = V.sourceData(m, 'hubflow-direction')
  for (const f of (dirData && dirData.features) || []) {
    kindById[f.properties.segment_id] = f.properties.dir_kind
  }
  const travelTo = (sid) => {
    const n = nodesById[sid] || {}
    return kindById[sid] === 'backward' ? n.from : n.to
  }

  // 2) 用例：reverse 段 + forward 段各若干 offset（含 0 与中点）
  const cases = []
  const offsetsFor = (sid) => {
    const c = coordsById[sid]
    if (!c) return []
    const len = V.lens(c).total
    return [0, 10, 20, len * 0.25, len * 0.5, len * 0.75, Math.max(0, len - 5)]
      .map((v) => Math.round(v * 10) / 10)
      .filter((v, i, a) => a.indexOf(v) === i)
  }
  const targets = ['SZ-004', 'SZ-001', 'SZ-023', 'SZ-036'].filter((s) => coordsById[s])
  for (const sid of targets) for (const off of offsetsFor(sid)) cases.push([sid, off])

  // 3) 逐条：后端 start_point ↔ 页面 pointAt
  const R = 6371008.8
  const dist = (a, b) => {
    const lat0 = (Math.PI / 180) * ((a[1] + b[1]) / 2)
    const dx = (Math.PI / 180) * (b[0] - a[0]) * Math.cos(lat0) * R
    const dy = (Math.PI / 180) * (b[1] - a[1]) * R
    return Math.hypot(dx, dy)
  }
  const rows = []
  for (const [sid, off] of cases) {
    const coords = coordsById[sid]
    // 终点直接取本段两个端点坐标（站网一定有）：reverse 段只有顺着行进的一端可达，故两个都试
    const ends = [coords[0], coords[coords.length - 1]].filter(Boolean)
    let sp = null
    for (const end of ends) {
      try {
        const res = await fetch('/api/traffic/route/plan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ origin: { segment_id: sid, offset_m: off }, destination: { lon: end[0], lat: end[1] }, with_departure: false }),
        })
        const j = await res.json()
        if (j && j.start_point) { sp = j.start_point; break }
      } catch (e) { /* 换下一个端点 */ }
    }
    if (!sp) { rows.push({ segment_id: sid, offset_m: off, skipped: 'both-directions-unreachable' }); continue }
    const mine = V.pointAt(coords, off)
    const backend = sp.lon != null ? [sp.lon, sp.lat] : null
    rows.push({
      segment_id: sid,
      offset_m: off,
      direction: sp.direction,
      offset_travel_m: sp.offset_travel_m,
      backend_lonlat: backend,
      frontend_pointAt: mine,
      dist_m: backend ? Math.round(dist(backend, mine) * 100) / 100 : null,
    })
  }
  const measurable = rows.filter((r) => r.dist_m != null)
  return {
    ok: measurable.length > 0 && measurable.every((r) => r.dist_m < 2),
    criterion: 'dist(后端 start_point.lonlat, 页面 pointAt(coords, offset_m)) < 2 m',
    canvas: (() => {
      const c = m.getCanvas()
      return [c.clientWidth, c.clientHeight]
    })(),
    counts: { cases: rows.length, measurable: measurable.length, max_dist_m: measurable.length ? Math.max(...measurable.map((r) => r.dist_m)) : null },
    rows,
  }
