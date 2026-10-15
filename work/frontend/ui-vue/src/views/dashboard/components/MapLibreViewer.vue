<script setup lang="ts">
// 矢量底图版路网图:MapLibre GL + OpenFreeMap(底图为 OpenStreetMap 数据)。
//
// 为什么不走高德(2026-10-15 换):
//   ① **坐标系不用转** —— 站点包统一存 WGS-84(`stations/README.md`),OpenFreeMap 的 OSM 数据
//      也是 WGS-84,画上去天然对齐;高德是 GCJ-02,必须转,不转整体偏约 600 m;
//   ② **不需要 Key / 注册 / 安全密钥** —— 没有高德「商业目的须先购买技术服务许可」
//      (高德 3.2.1)那条风险,也没有 INVALID_USER_SCODE 这类坑;
//   ③ 与仓库既定方向一致 —— 手册 §8.3 / D7 的口径就是「路网走 OSM」。
//
// 合规(改之前先读 `docs/条款核实.md`):
//   · OSM 数据受 ODbL 约束,**必须署名** —— 故保留 MapLibre 默认的 AttributionControl,
//     不得隐藏、不得被 UI 遮挡(署名文案由瓦片服务声明,实测为
//     「OpenFreeMap © OpenMapTiles Data from OpenStreetMap」);
//   · **不缓存瓦片、不做离线包**。断网演示的正解是**自建瓦片**(OSM 数据本身允许),
//     不是缓存别人的公共服务;
//   · OpenFreeMap 是第三方免费公共服务(无 SLA),其自身条款**尚未进过本仓库的条款核实清单** ——
//     一期若只在队内演示可用,对外发布前须补核(另见「审图号」要求,OSM 底图无审图号)。
//
// 语义纪律(与 NetMap 一致):路段色只表示拥挤度/等级;品牌蓝只画「当前/已选」。
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  ScaleControl,
  setWorkerUrl,
  type ExpressionSpecification,
  type FilterSpecification,
  type GeoJSONSource,
  type LineLayerSpecification,
} from 'maplibre-gl'
// ⚠️ 必须显式指定 worker 地址,否则**生产构建底图空白**(实测踩过):
//   MapLibre 的矢量瓦片解析跑在独立 worker 里(508 KB),主包按
//   `new URL('./maplibre-gl-worker.mjs', import.meta.url)` 找它。dev 下(已 exclude 出依赖预打包)
//   它恰好与主包同目录、能被 Vite 直接端出来;但**打包后那个兄弟文件不会被产出** ——
//   dist 里只有 index.js/css,运行时去要 `/assets/maplibre-gl-worker.mjs` 直接落空,
//   报「Worker failed to load」,地图整块空白且不报 HTTP 错(worker 加载失败不走 response 事件)。
//   用 `?url` 让 Vite 把这个 worker 文件真正产出到 assets/ 并返回它的地址。
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
// ⚠️ 也必须显式 import:`tsconfig.app.json` 的 `types: ["vite/client"]` 只放行 vite/client,
//    所以 `@types/geojson` 的全局 `GeoJSON` 命名空间**不可见**(用 `GeoJSON.FeatureCollection`
//    会报 TS2503 Cannot find namespace 'GeoJSON')。
import type { FeatureCollection } from 'geojson'
import 'maplibre-gl/dist/maplibre-gl.css'

setWorkerUrl(maplibreWorkerUrl)
import { DEMO_NETWORK } from '../../../shared/demoNetwork'
import type { DemoSegment } from '../../../shared/demoNetwork'
import { TD } from '../../../shared/theme'
// 摄像头布点 / 只摄像头段上色 / 感知层深链 —— **与自绘视图(NetMap)共用同一套口径**
// (Issue IKLX5Y:单一真值来源 = 站点包 channels;规则不在两个视图里各写一份)
import { cameraPins, isCameraCovered, perceptionHref } from '../../../shared/cameras'
import {
  ciStyleColor,
  levelStyle,
  UNAVAILABLE,
  type CongestionViewMode,
  type SegmentRecord,
} from '../../../shared/traffic'

/** OpenFreeMap 的 Liberty 样式(免 Key、免注册;数据来自 OpenStreetMap) */
const STYLE_URL = 'https://tiles.openfreemap.org/styles/liberty'
const SRC = 'hubflow-route'
const LAYER_CASING = `${SRC}-casing`
const LAYER_LINE = `${SRC}-line`
const LAYER_SELECTED = `${SRC}-selected`

const BRAND = TD.brand

/** 摄像头 Marker(重绘 / 卸载时移除) */
let camMarkers: Marker[] = []

const props = withDefaults(
  defineProps<{
    segments: SegmentRecord[]
    selectedId: string | null
    mode?: CongestionViewMode
    /** 快照时间(仅用于图例展示) */
    ts?: string
  }>(),
  {
    mode: 'level',
    ts: '',
  },
)

const emit = defineEmits<{ (e: 'select', segmentId: string): void }>()

/** 容器**始终渲染**(不用 v-if 挂载),从根上避免「容器还没进 DOM 就初始化」那类静默失败 */
const containerRef = ref<HTMLDivElement | null>(null)
const mapRef = ref<MapLibreMap | null>(null)
const ready = ref(false)
const notice = ref('')

const net = DEMO_NETWORK.segments
const segById = computed(() => new Map(props.segments.map((s) => [s.segment_id, s])))
const isIndex = computed(() => props.mode === 'index')

/**
 * 路段色:四级判级色 / CI 色阶;无记录一律灰(数据不可用)——与 NetMap 同一口径。
 * 「只摄像头段上色」策略(站点包 `colorPolicy === 'camera-covered'`)下,没摄像头覆盖的段
 * 也走灰;它靠**更细的线宽 + 更低透明度**与"有摄像头但没数据"区分开(见 `widthExpr`),
 * 免得两种灰在图上长得一样。
 */
function colorOf(seg: DemoSegment): string {
  if (!isCameraCovered(seg.segment_id)) return UNAVAILABLE.color
  const rec = segById.value.get(seg.segment_id)
  if (!rec) return UNAVAILABLE.color
  return isIndex.value ? ciStyleColor(rec) : levelStyle(rec).color
}

/** 站点包坐标是 WGS-84,**直接喂给 MapLibre 即可** —— 不做任何坐标转换 */
function routeGeoJson(): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: net.map((seg) => ({
      type: 'Feature',
      properties: {
        segment_id: seg.segment_id,
        name: seg.name,
        kind: seg.kind,
        color: colorOf(seg),
        /** 该段是否有摄像头覆盖(策略 'all' 时恒 true)—— 线宽/透明度按它分档 */
        covered: isCameraCovered(seg.segment_id),
      },
      geometry: { type: 'LineString', coordinates: seg.coords },
    })),
  }
}

/**
 * 线宽 = 主/支两档 × 「没摄像头覆盖」系数。
 * 收细 + 压透明度是「只摄像头段上色」策略下"这段没监控"的画法(业主 2026-10-15),
 * 与"有摄像头但当前没数据"的灰区分开(后者是正常线宽)。
 */
const widthExpr = (main: number, ramp: number): ExpressionSpecification => [
  '*',
  ['case', ['==', ['get', 'kind'], 'main'], main, ramp],
  ['case', ['==', ['get', 'covered'], false], 0.55, 1],
]

function addRouteLayers(map: MapLibreMap): void {
  if (map.getSource(SRC)) return

  map.addSource(SRC, { type: 'geojson', data: routeGeoJson() })

  // 白色描边底衬:让彩色路段在浅底图上分得开(与 NetMap 同一手法)
  map.addLayer({
    id: LAYER_CASING,
    type: 'line',
    source: SRC,
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': '#FFFFFF', 'line-width': widthExpr(11, 9) },
  } satisfies LineLayerSpecification)

  map.addLayer({
    id: LAYER_LINE,
    type: 'line',
    source: SRC,
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': ['get', 'color'],
      'line-width': widthExpr(5.5, 4.5),
      'line-opacity': ['case', ['==', ['get', 'covered'], false], 0.4, 1],
    },
  } satisfies LineLayerSpecification)

  // 选中路段描边:品牌蓝(「当前/已选」语义),虚线,不覆盖判级色
  map.addLayer({
    id: LAYER_SELECTED,
    type: 'line',
    source: SRC,
    filter: selectedFilter(),
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': BRAND,
      'line-width': 2.2,
      'line-dasharray': [2, 2],
      'line-opacity': 0.9,
    },
  } satisfies LineLayerSpecification)

  // 交互:点击选中 / 悬停变手型(与 NetMap 的「hover 即切换」不同,
  // 这里只做**点击**选中 —— MapLibre 的 mouseenter 在快速划过时抖动明显)
  map.on('click', LAYER_LINE, (e) => {
    const id = e.features?.[0]?.properties?.segment_id
    if (typeof id === 'string' && id) emit('select', id)
  })
  map.on('mouseenter', LAYER_LINE, () => {
    map.getCanvas().style.cursor = 'pointer'
  })
  map.on('mouseleave', LAYER_LINE, () => {
    map.getCanvas().style.cursor = ''
  })
}

function selectedFilter(): FilterSpecification {
  return ['==', ['get', 'segment_id'], props.selectedId ?? '']
}

/**
 * 摄像头布点(Issue IKLX5Y):与自绘视图(NetMap)**同一套口径** ——
 * 位置取站点包 `channels[].lon/lat`(落在该段折线上的示意点,**不是路测点位**),
 * 点击跳到感知层对应通道。矢量底图上用 MapLibre Marker 画。
 * 实心 = 有视频源、空心 = 未接入视频源(本期留空)——两件事在页面上要分开说。
 */
function addCameraPins(map: MapLibreMap): void {
  for (const p of cameraPins()) {
    const el = document.createElement('div')
    el.className = p.hasVideo ? 'cam-pin' : 'cam-pin empty'
    el.textContent = p.cid.replace('C-', '')
    el.title = `${p.cid} ${p.name} · ${p.segment_id} · ${
      p.hasVideo ? '有视频源' : '未接入视频源 · 本期留空'
    } · 点击进感知层`
    el.addEventListener('click', () => {
      window.location.href = perceptionHref(p.source)
    })
    camMarkers.push(new Marker({ element: el }).setLngLat([p.lon, p.lat]).addTo(map))
  }
}

/** 视野适配到整张路网(边界留白,避免线贴边) */
function fitToNetwork(map: MapLibreMap): void {
  const lons = net.flatMap((s) => s.coords.map((c) => c[0]))
  const lats = net.flatMap((s) => s.coords.map((c) => c[1]))
  if (lons.length === 0) return
  map.fitBounds(
    [
      [Math.min(...lons), Math.min(...lats)],
      [Math.max(...lons), Math.max(...lats)],
    ],
    { padding: 56, duration: 0 },
  )
}

function initMap(): void {
  if (!containerRef.value) return
  const map = new MapLibreMap({
    container: containerRef.value,
    style: STYLE_URL,
    center: [112.67, 23.2],
    zoom: 13,
    // 不隐藏默认署名控件:OSM/ODbL 要求署名(见文件头「合规」)
  })
  mapRef.value = map
  map.addControl(new NavigationControl({ visualizePitch: true }), 'top-right')
  map.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-left')

  let timeoutId = 0

  map.on('load', () => {
    window.clearTimeout(timeoutId)
    addRouteLayers(map)
    addCameraPins(map)
    fitToNetwork(map)
    ready.value = true
  })

  // 只在**样式/底图加载不出来**时给软提示;单块瓦片失败不报错、不遮挡地图
  map.on('error', (e: unknown) => {
    if (ready.value) return
    const msg =
      e && typeof e === 'object' && 'error' in e && e.error instanceof Error
        ? e.error.message
        : '样式或瓦片加载失败'
    notice.value = `底图加载异常:${msg}`
  })

  // 12 s 还没 load:大概率离线。给一句实话,而不是让用户对着空白地图猜
  timeoutId = window.setTimeout(() => {
    if (!ready.value) notice.value = '底图加载超时(可能处于离线状态)—— 路网线仍按当前数据绘制'
  }, 12000)
}

/** 重绘:数据 / 视图模式变化时只换 GeoJSON,不重建地图 */
watch(
  () => [props.segments, props.mode] as const,
  () => {
    const map = mapRef.value
    if (!map || !ready.value) return
    // 源由本组件用固定 id 创建,断言安全;用 GeoJSONSource 才能真正拿到 setData 的类型
    const src = map.getSource(SRC) as GeoJSONSource | undefined
    if (src) void src.setData(routeGeoJson())
  },
)

/** 选中变化:只改高亮层的 filter,不动数据 */
watch(
  () => props.selectedId,
  () => {
    const map = mapRef.value
    if (!map || !ready.value || !map.getLayer(LAYER_SELECTED)) return
    map.setFilter(LAYER_SELECTED, selectedFilter())
  },
)

onMounted(async () => {
  // 容器始终在 DOM 里,nextTick 只为确保布局尺寸已就绪(尺寸为 0 时地图会渲染成空白)
  await nextTick()
  initMap()
})

onUnmounted(() => {
  camMarkers.forEach((m) => m.remove())
  camMarkers = []
  mapRef.value?.remove()
  mapRef.value = null
  ready.value = false
})
</script>

<template>
  <div class="mlmap">
    <div ref="containerRef" class="mlmap-canvas" />
    <div v-if="!ready" class="mlmap-state">
      <div class="mlmap-state-main">{{ notice || '底图加载中…' }}</div>
      <div class="mlmap-state-sub">底图:OpenFreeMap(OpenStreetMap 数据)</div>
    </div>
  </div>
</template>

<style scoped>
.mlmap {
  position: relative;
  width: 100%;
  height: 100%;
  background: #f7f8fa;
  border-radius: 6px;
  overflow: hidden;
}
.mlmap-canvas {
  width: 100%;
  height: 100%;
}
.mlmap-state {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  background: #f7f8fa;
  z-index: 2;
  pointer-events: none;
}
.mlmap-state-main {
  font-size: 12px;
  color: #666666;
}
.mlmap-state-sub {
  font-size: 11px;
  color: #999999;
}

/* MapLibre 自己生成的 DOM 不在 scoped 作用域内,须用 :deep() 才生效。
   署名控件只调字号,**不隐藏、不遮挡**(OSM/ODbL 署名义务)。 */
:deep(.maplibregl-ctrl-attrib) {
  font-size: 10px;
}
:deep(.maplibregl-ctrl-scale) {
  font-size: 10px;
  background: rgba(255, 255, 255, 0.85);
}

/* 摄像头图钉(Issue IKLX5Y):与自绘视图同款语义 ——
   实心深灰 = 有视频源;空心白底 = 未接入视频源(本期留空)。
   品牌蓝只作描边(「可操作」语义),不当填充色用。
   Marker 的 DOM 由 document.createElement 造,不在 scoped 作用域内,故用 :deep()。 */
:deep(.cam-pin) {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #455a64;
  border: 2px solid v-bind('BRAND');
  color: #ffffff;
  font-size: 10px;
  line-height: 16px;
  text-align: center;
  cursor: pointer;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25);
}
:deep(.cam-pin.empty) {
  background: #ffffff;
  color: #455a64;
}
</style>
