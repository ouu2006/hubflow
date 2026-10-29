/**
 * _page_lib.js —— 注入到真页面的工具集（cdp_eval.mjs / cdp_measure.mjs 共用）。
 *
 * 硬约束：**不许 import 产品代码**（`src/shared/directions.ts` 等），两边必须独立实现，
 * 否则「拿同一份实现自己比自己」等于没验。算法口径照抄「平面近似 + 经度按 cos(lat0) 压缩」。
 *
 * 提供：window.__vf.{getMap, lens, pointAt, tangentAt, bearingDeg, sourceData, findComponent}
 *   · getMap()          —— 从 Vue 开发态组件树 `setupState.*` 摸出真 MapLibre 实例（无产品改动）
 *   · findComponent(pred) —— 遍历组件树，pred(setupState) 为真则返回该 setupState 的键值摘要
 */
window.__vf = (() => {
  const R = 111320;

  function pick(o) {
    return o && typeof o.project === 'function' && typeof o.getSource === 'function';
  }

  function walk(onSetup, depth) {
    const seen = new Set();
    let hit = null;
    const visit = (comp, d) => {
      if (!comp || seen.has(comp) || d > 40 || hit) return;
      seen.add(comp);
      try {
        const ss = comp.setupState;
        if (ss) {
          const r = onSetup(ss, comp);
          if (r) { hit = r; return }
        }
      } catch (e) {}
      visit(comp.parent, d + 1);
    };
    const rootEl = document.querySelector('#app');
    if (rootEl && rootEl.__vue_app__) visit(rootEl.__vue_app__._instance, 0);
    if (!hit) {
      const el = document.querySelector('.maplibregl-map');
      if (el && el.__vueParentComponent) visit(el.__vueParentComponent, 0);
    }
    return hit;
  }

  function getMap() {
    if (window.__vfMap) return window.__vfMap;
    window.__vfMap = walk((ss) => {
      for (const k of Object.keys(ss)) {
        let v; try { v = ss[k] } catch (e) { continue }
        if (pick(v)) return v;
        if (v && typeof v === 'object' && pick(v.value)) return v.value;
      }
      return null;
    });
    return window.__vfMap;
  }

  /**
   * 收集页面上所有组件实例。
   * 为什么不能只从 root instance 往下走：root 的 parent 是 null，我原来的遍历其实是「往上爬」，
   * 一行都碰不到子组件。开发态每个元素都挂了 `__vueParentComponent`，从 DOM 抓最省事。
   */
  function allComponents() {
    const out = [];
    const seen = new Set();
    for (const el of document.querySelectorAll('*')) {
      const c = el.__vueParentComponent;
      if (c && !seen.has(c)) { seen.add(c); out.push(c) }
    }
    return out;
  }

  /** 遍历组件树，收集每个组件 setupState 里命中的键（用于找 mapScope / motionPhase 之类状态） */
  function survey(filterKeys) {
    const out = [];
    for (const comp of allComponents()) {
      try {
        const ss = comp.setupState;
        if (ss) {
          const keys = Object.keys(ss).filter((k) => !filterKeys || filterKeys.some((f) => k === f));
          if (keys.length) {
            const vals = {};
            for (const k of keys) {
              let v; try { v = ss[k] } catch (e) { vals[k] = '<unreadable>'; continue }
              const t = typeof v;
              vals[k] = (v === null || v === undefined) ? String(v)
                : t === 'function' ? '<fn>'
                : t === 'object' ? (Array.isArray(v) ? `Array(${v.length})` : (v.constructor && v.constructor.name) || 'object')
                : String(v);
            }
            out.push({ comp: comp.type && (comp.type.name || comp.type.__name || comp.type.__file || '?'), keys: vals });
          }
        }
      } catch (e) {}
    }
    return out;
  }

  /** 在组件树里按 setupState 键名找一个可写状态并赋值（用于把页面切到站内视角） */
  function setSetupStateKey(key, value) {
    let done = false;
    for (const comp of allComponents()) {
      try {
        const ss = comp.setupState;
        if (ss && key in ss) {
          ss[key] = value;
          done = true;
          break;
        }
      } catch (e) {}
    }
    return done;
  }

  /** 找一个函数并在其组件上下文里调用（例如组件暴露的「进站内」方法） */
  function callSetupFn(name, ...args) {
    for (const comp of allComponents()) {
      try {
        const ss = comp.setupState;
        if (ss && name in ss && typeof ss[name] === 'function') {
          return { called: true, result: ss[name](...args) };
        }
      } catch (e) { return { called: false, error: String(e) } }
    }
    return { called: false };
  }

  // —— 独立几何实现（与产品代码同口径，但代码是两份）——
  function lens(coords) {
    const lat0 = coords[0][1] * Math.PI / 180;
    const sx = Math.cos(lat0);
    const out = []; let total = 0;
    for (let i = 1; i < coords.length; i++) {
      const dx = (coords[i][0] - coords[i - 1][0]) * R * sx;
      const dy = (coords[i][1] - coords[i - 1][1]) * R;
      const len = Math.hypot(dx, dy);
      out.push(len); total += len;
    }
    return { lens: out, total };
  }

  function pointAt(coords, s) {
    const { lens: L, total } = lens(coords);
    if (total <= 0) return coords[0].slice();
    let remain = Math.min(total, Math.max(0, s));
    for (let i = 0; i < L.length; i++) {
      const len = L[i];
      if (remain <= len || i === L.length - 1) {
        const t = len <= 0 ? 0 : Math.min(1, remain / len);
        return [coords[i][0] + (coords[i + 1][0] - coords[i][0]) * t,
                coords[i][1] + (coords[i + 1][1] - coords[i][1]) * t];
      }
      remain -= len;
    }
    return coords[coords.length - 1].slice();
  }

  function bearingDeg(a, b) {
    const latRad = ((a[1] + b[1]) / 2) * Math.PI / 180;
    const east = (b[0] - a[0]) * Math.cos(latRad);
    const north = b[1] - a[1];
    return ((Math.atan2(east, north) * 180 / Math.PI) + 360) % 360;
  }

  function tangentAt(coords, fraction, spanM) {
    const { total } = lens(coords);
    if (total <= 0) return bearingDeg(coords[0], coords[coords.length - 1]);
    const half = Math.min(spanM, total / 4);
    const c = total * fraction;
    const a = pointAt(coords, Math.max(0, c - half));
    const b = pointAt(coords, Math.min(total, c + half));
    return bearingDeg(a, b);
  }

  function sourceData(map, id) {
    const src = map.getSource(id);
    if (!src) return null;
    let d = null;
    try { d = src._data } catch (e) {}
    if (!d) { try { d = src.serialize().data } catch (e) {} }
    if (typeof d === 'string') { try { d = JSON.parse(d) } catch (e) { d = null } }
    return d && d.features ? d : null;
  }

  return { getMap, survey, setSetupStateKey, callSetupFn, allComponents, lens, pointAt, tangentAt, bearingDeg, sourceData, walk };
})();
window.__vfReady = true;
true;
