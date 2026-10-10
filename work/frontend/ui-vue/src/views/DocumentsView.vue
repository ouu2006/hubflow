<script setup lang="ts">
import { Delete, Refresh, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadRequestOptions } from 'element-plus'
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { deleteDocument, listDocuments, uploadDocument } from '../api'
import { MAX_UPLOAD_BYTES, formatBytes, type DocRecord, type DocStatus } from '../shared/protocol'

// 任务 B:列表 / 上传(multipart + 进度条)/ 删除(confirm)/ 版本态展示 / >16MB 前端预检。

const route = useRoute()
const docs = ref<DocRecord[]>([])
const loading = ref(false)
const uploading = ref(false)
const percent = ref(0)
const uploadName = ref('')
let pollTimer: ReturnType<typeof setTimeout> | undefined

// 溯源页「跳转文档」落地:?doc_id= 高亮对应行并滚动定位
const focusId = computed(() => (typeof route.query.doc_id === 'string' ? route.query.doc_id : ''))

const STATUS_META: Record<DocStatus, { label: string; tag: 'success' | 'warning' | 'danger' }> = {
  ready: { label: '就绪', tag: 'success' },
  processing: { label: '处理中', tag: 'warning' },
  failed: { label: '失败', tag: 'danger' },
}

async function refresh(): Promise<void> {
  loading.value = true
  try {
    docs.value = await listDocuments()
    schedulePoll()
    void scrollFocus()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '文档列表加载失败')
  } finally {
    loading.value = false
  }
}

async function silentRefresh(): Promise<void> {
  try {
    docs.value = await listDocuments()
  } catch {
    /* 轮询失败静默,下一轮再试 */
  }
  schedulePoll()
}

// 版本态流水演示:存在 processing 文档时每 2s 轮询直至收敛
function schedulePoll(): void {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = undefined
  }
  if (!docs.value.some((d) => d.status === 'processing')) return
  pollTimer = setTimeout(() => void silentRefresh(), 2000)
}

onUnmounted(() => {
  if (pollTimer) clearTimeout(pollTimer)
})

async function doUpload(opts: UploadRequestOptions): Promise<unknown> {
  const file: File = opts.file
  if (file.size > MAX_UPLOAD_BYTES) {
    ElMessage.warning(
      `「${file.name}」为 ${formatBytes(file.size)},超过 16 MB 上限,前端预检拒绝上传(与后端桥帧限护栏呼应)`,
    )
    return Promise.reject(new Error('OVERSIZE'))
  }
  uploading.value = true
  percent.value = 0
  uploadName.value = file.name
  try {
    const res = await uploadDocument(file, { onProgress: (p) => (percent.value = p) })
    ElMessage.success(`上传成功:${res.doc_id}(${res.stored_path}),入库处理中…`)
    await refresh()
    return res
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '上传失败')
    return Promise.reject(e)
  } finally {
    uploading.value = false
    uploadName.value = ''
  }
}

async function onDelete(doc: DocRecord): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除文档「${doc.name}」(v${doc.version})?`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteDocument(doc.doc_id)
    ElMessage.success(`已删除:${doc.doc_id}`)
    await refresh()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

function rowClassName({ row }: { row: DocRecord }): string {
  return row.doc_id === focusId.value ? 'row-focus' : ''
}

function scrollFocus(): void {
  void nextTick(() => {
    if (!focusId.value) return
    const el = document.querySelector('.row-focus')
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  })
}

onMounted(() => {
  void refresh()
})
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h2>文档管理</h2>
      <el-button :icon="Refresh" :loading="loading" @click="refresh()">刷新</el-button>
    </div>

    <el-card shadow="never" class="upload-card">
      <el-upload
        drag
        :show-file-list="false"
        :http-request="doUpload"
        :disabled="uploading"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">
          {{ uploading ? `正在上传「${uploadName}」…` : '拖拽文件到此处,或点击选择文件上传' }}
        </div>
        <template #tip>
          <div class="upload-tip">单文件 ≤ 16 MB(前端预检 + 后端桥帧限护栏呼应)</div>
          <el-progress
            v-if="uploading"
            :percentage="percent"
            :stroke-width="10"
            striped
            striped-flow
          />
        </template>
      </el-upload>
    </el-card>

    <el-table
      :data="docs"
      v-loading="loading"
      :row-class-name="rowClassName"
      stripe
      class="doc-table"
    >
      <el-table-column prop="name" label="文档名" min-width="240" show-overflow-tooltip />
      <el-table-column prop="doc_id" label="doc_id" width="130">
        <template #default="{ row }">
          <span class="mono">{{ row.doc_id }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="version" label="版本" width="90" align="center">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">v{{ row.version }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="110" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="STATUS_META[row.status as DocStatus].tag">
            {{ STATUS_META[row.status as DocStatus].label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" align="center">
        <template #default="{ row }">
          <el-button size="small" type="danger" link :icon="Delete" @click="onDelete(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
      <template #empty>暂无文档,请上传</template>
    </el-table>
  </div>
</template>

<style scoped>
.upload-card {
  margin-bottom: 16px;
}
.upload-card :deep(.el-upload-dragger) {
  padding: 24px 16px;
}
.upload-icon {
  font-size: 40px;
  color: #a0cfff;
  margin-bottom: 8px;
}
.upload-text {
  font-size: 14px;
  color: #606266;
}
.upload-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 6px;
}
.doc-table {
  width: 100%;
}
.row-focus {
  --el-table-tr-bg-color: var(--el-color-warning-light-8) !important;
}
:deep(.row-focus) {
  background: var(--el-color-warning-light-8);
}
.mono {
  font-family: Consolas, Menlo, monospace;
  font-size: 12px;
}
</style>
