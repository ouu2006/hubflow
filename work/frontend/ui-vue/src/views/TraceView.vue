<script setup lang="ts">
import { Back, Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getTrace } from '../api'
import { extractKeywords, type TraceItem } from '../shared/protocol'

// 任务 D:按 answer_id 拉取溯源列表(doc_id/snippet/score/source),
// 片段高亮(以对话页带来的问题关键词 ?q= 为锚)+ 跳转文档(doc_id → 文档管理页定位)。

const route = useRoute()
const router = useRouter()

const items = ref<TraceItem[]>([])
const loading = ref(false)
const failed = ref('')

const answerId = computed(() => String(route.params.answerId ?? ''))
const question = computed(() => (typeof route.query.q === 'string' ? route.query.q : ''))
const keywords = computed(() => extractKeywords(question.value))

async function load(): Promise<void> {
  if (!answerId.value) return
  loading.value = true
  failed.value = ''
  items.value = []
  try {
    items.value = await getTrace(answerId.value)
  } catch (e) {
    failed.value = e instanceof Error ? e.message : '溯源加载失败'
    ElMessage.error(failed.value)
  } finally {
    loading.value = false
  }
}

watch(answerId, () => void load(), { immediate: true })

function escapeHtml(s: string): string {
  return s
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function escapeRegExp(s: string): string {
  return s.replaceAll(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// 片段高亮:先整体转义再包 <mark>,关键词同步转义保证与转义后文本可匹配
function highlightHtml(snippet: string): string {
  const esc = escapeHtml(snippet)
  if (!keywords.value.length) return esc
  const parts = [...keywords.value].sort((a, b) => b.length - a.length).map(escapeRegExp)
  const re = new RegExp(`(${parts.join('|')})`, 'gi')
  return esc.replace(re, '<mark class="kw">$1</mark>')
}

function gotoDoc(docId: string): void {
  void router.push({ path: '/documents', query: { doc_id: docId } })
}

function goBack(): void {
  router.back()
}
</script>

<template>
  <div class="page trace-page">
    <div class="page-head">
      <div class="head-left">
        <el-button :icon="Back" circle @click="goBack()" />
        <h2>溯源引用</h2>
        <span class="mono answer-id">{{ answerId }}</span>
      </div>
      <span v-if="question" class="question">问题:{{ question }}</span>
    </div>

    <div v-if="keywords.length" class="kw-row">
      高亮关键词:
      <el-tag v-for="k in keywords" :key="k" size="small" type="warning" effect="plain">{{ k }}</el-tag>
    </div>

    <div v-if="loading" v-loading="loading" class="trace-loading" element-loading-text="拉取溯源中…" />

    <el-alert v-else-if="failed" :title="`溯源加载失败:${failed}`" type="error" :closable="false" />

    <el-empty v-else-if="!items.length" description="该回答无溯源片段" />

    <el-card v-for="it in items" v-else :key="it.doc_id + it.source" shadow="never" class="trace-card">
      <template #header>
        <div class="trace-head">
          <span class="mono doc-id">{{ it.doc_id }}</span>
          <el-tag size="small" type="info" effect="plain">{{ it.source }}</el-tag>
          <div class="score">
            <span class="score-num">{{ it.score.toFixed(3) }}</span>
            <el-progress
              :percentage="Math.round(it.score * 100)"
              :stroke-width="8"
              :show-text="false"
              class="score-bar"
            />
          </div>
          <el-button size="small" type="primary" plain :icon="Document" @click="gotoDoc(it.doc_id)">
            跳转文档
          </el-button>
        </div>
      </template>
      <!-- snippet 为 mock/后端给定的纯文本;此处经 escapeHtml 后仅注入 <mark> -->
      <div class="snippet" v-html="highlightHtml(it.snippet)" />
    </el-card>
  </div>
</template>

<style scoped>
.trace-page {
  max-width: 960px;
}
.head-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.head-left h2 {
  margin: 0;
}
.question {
  font-size: 13px;
  color: #606266;
  max-width: 46%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kw-row {
  font-size: 12px;
  color: #909399;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.trace-loading {
  min-height: 240px;
}
.trace-card {
  margin-bottom: 12px;
}
.trace-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.doc-id {
  font-weight: 600;
}
.score {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.score-num {
  font-size: 12px;
  color: #606266;
  font-family: Consolas, Menlo, monospace;
}
.score-bar {
  width: 140px;
}
.snippet {
  font-size: 14px;
  line-height: 1.8;
  color: #303133;
}
.snippet :deep(mark.kw) {
  background: #f8e3b5;
  color: #8a5a00;
  padding: 0 2px;
  border-radius: 2px;
}
.mono {
  font-family: Consolas, Menlo, monospace;
  font-size: 12px;
}
.answer-id {
  color: #909399;
}
</style>
