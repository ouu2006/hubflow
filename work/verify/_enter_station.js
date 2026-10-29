/**
 * _enter_station.js —— 把页面推进「站内」视角（业主实际看箭头的那一档）。
 *
 * 为什么能这么做：开发态 `setupState` 暴露了 MapLibreViewer 的 `motionPhase` ref，
 * 给它赋 'station' 等价于用户点进站内；相机由组件自己的 applyViewState 重新取景，
 * 我不改任何产品代码，也不伪造图层状态。
 */
const map = V.getMap();
const okSet = V.setSetupStateKey('motionPhase', 'station');
await new Promise((r) => setTimeout(r, 4000));
await new Promise((r) => {
  let done = false;
  const fin = () => { if (!done) { done = true; r() } };
  try { if (map.loaded() && map.isStyleLoaded()) { fin() } } catch (e) {}
  map.once('idle', fin);
  setTimeout(fin, 6000);
});
return {
  okSet,
  motionPhaseNow: (V.survey(['motionPhase'])[0] || {}).keys || null,
  cam: { center: map.getCenter().toArray(), zoom: map.getZoom(), bearing: map.getBearing(), pitch: map.getPitch() },
  dirVisibility: map.getLayoutProperty('hubflow-direction-marker', 'visibility'),
  dirFeatCount: ((V.sourceData(map, 'hubflow-direction') || { features: [] }).features.length),
  renderedDir: (() => { try { return map.queryRenderedFeatures({ layers: ['hubflow-direction-marker'] }).length } catch (e) { return 'ERR:' + e.message } })(),
  iconSizeExpr: map.getLayoutProperty('hubflow-direction-marker', 'icon-size'),
  iconRotateExpr: map.getLayoutProperty('hubflow-direction-marker', 'icon-rotate'),
  iconOffset: map.getLayoutProperty('hubflow-direction-marker', 'icon-offset') ?? null,
};
