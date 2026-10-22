<!-- 应用壳:仅路由出口。harness 管理台壳(导航/health 轮询/登录态)已随 2026-10-11 架构裁定移除;
     态势大屏全屏沉浸、自带顶栏,感知画面页(PR #56)同为自绘页头。 -->
<script setup lang="ts">
// 切站（Issue IKPFR4）：监控大屏自己注册了"原地切站"钩子（缓存优先、不重建地图），
// 它切站时**不走这里**；决策层 / 感知层还没接缓存链路，靠换 key 让页面重新 setup
// （数据按新包重取），**不重新请求文档、不重下底图**，也算不上整页刷新。
import { stationRemountKey } from './shared/stationSwitch'
</script>

<template>
  <router-view :key="stationRemountKey" />
</template>
