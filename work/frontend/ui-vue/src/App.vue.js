/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="D:/项目/hubflow/work/frontend/ui-vue/node_modules/.pnpm/@vue+language-core@3.3.13/node_modules/@vue/language-core/types/props-fallback.d.ts" />
// 切站（Issue IKPFR4）：监控大屏自己注册了"原地切站"钩子（缓存优先、不重建地图），
// 它切站时**不走这里**；决策层 / 感知层还没接缓存链路，靠换 key 让页面重新 setup
// （数据按新包重取），**不重新请求文档、不重下底图**，也算不上整页刷新。
import { stationRemountKey } from './shared/stationSwitch';
const __VLS_ctx = {};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
void __VLS_ctx, __VLS_components, __VLS_intrinsics, __VLS_directives;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.routerView | typeof __VLS_components.RouterView | typeof __VLS_components['router-view']} */
routerView;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    // @ts-ignore
    key: (__VLS_unwrap(stationRemountKey, {})),
}));
const __VLS_2 = __VLS_1({
    key: (__VLS_unwrap(stationRemountKey, {})),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
// @ts-ignore
[stationRemountKey,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
