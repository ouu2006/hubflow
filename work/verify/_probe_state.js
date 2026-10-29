/**
 * _probe_state.js —— 勘察：页面当前处于哪个视角、方向层为什么没画。
 * 关键问题：`directionDrawable = directionsAvailable && directionsVisible`，
 * 而图层可见性还要 `motionPhase === 'station'`。先确认这几个状态在哪、值是多少。
 */
const map = V.getMap();
const cam = map ? {
  center: map.getCenter().toArray(), zoom: map.getZoom(),
  bearing: map.getBearing(), pitch: map.getPitch(),
} : null;
const keys = ['mapScope', 'motionPhase', 'directionsVisible', 'directionsAvailable',
  'dirInfo', 'directionInfo', 'net', 'pack', 'station', 'stationKey', 'showStation',
  'mapMode', 'phase', 'segmentCount', 'segments'];
return {
  cam,
  layers: map ? map.getStyle().layers.filter((l) => String(l.id).includes('hubflow-dir') || String(l.id).includes('arrow'))
    .map((l) => ({ id: l.id, visibility: (l.layout || {}).visibility || 'visible' })) : null,
  dirFeatCount: map ? ((V.sourceData(map, 'hubflow-direction') || { features: [] }).features.length) : null,
  routeFeatCount: map ? ((V.sourceData(map, 'hubflow-route') || { features: [] }).features.length) : null,
  survey: V.survey(keys),
};
