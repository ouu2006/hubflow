<script setup lang="ts">
// 四级徽章 = 三重编码的"图标 + 文字"(颜色由使用处的 currentColor / 边框承担):
// 竖条数图标照手册 §6.2(单/双/三/四竖条);数据陈旧显示灰色问号(非等级状态)。
import { computed } from 'vue'
import { LEVELS, UNAVAILABLE, type CongestionLevel } from '../../../shared/traffic'

const props = defineProps<{
  level: CongestionLevel
  stale?: boolean
  name?: string
}>()

const style = computed(() => (props.stale === true ? UNAVAILABLE : LEVELS[props.level]))
const text = computed(() => props.name ?? style.value.name)
</script>

<template>
  <span class="lv-badge" :style="{ color: style.color }">
    <span v-if="style.bars === 0" class="unknown">?</span>
    <span v-else class="bars">
      <i v-for="n in style.bars" :key="n" />
    </span>
    <span class="txt">{{ text }}</span>
  </span>
</template>

<style scoped>
.lv-badge {
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}
.bars {
  display: inline-flex;
  align-items: flex-end;
  gap: 2px;
}
.bars i {
  width: 4px;
  height: 13px;
  background: currentColor;
  border-radius: 1px;
}
.unknown {
  width: 15px;
  height: 15px;
  border: 1.5px solid currentColor;
  border-radius: 50%;
  font-size: 10px;
  font-weight: 700;
  line-height: 12px;
  text-align: center;
}
.txt {
  margin-left: 6px;
  font-size: 12px;
}
</style>
