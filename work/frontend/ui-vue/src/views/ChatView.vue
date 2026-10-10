<script setup lang="ts">
import { Plus, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { chatStream, createSession } from '../api'
import { ApiError } from '../api/http'
import type { UsagePayload } from '../shared/protocol'

// 任务 C:会话创建 → chat SSE 流式渲染(delta 追加打字机、usage 角标、finish 收尾、error 通知),
// 每轮回答带「溯源」入口(answer_id → 溯源页)。
// 契约只有 POST /api/sessions(无会话列表端点),会话清单由本地持久化,不臆造端点。

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  question?: string
  answerId?: string
  usage?: UsagePayload
  error?: string
  done: boolean
}

interface ChatSession {
  id: string
  title: string
  createdAt: number
  messages: ChatMessage[]
}

const STORE_KEY = 'harness-ui.sessions.v1'
const router = useRouter()

const sessions = ref<ChatSession[]>(loadSessions())
const currentId = ref('')
const input = ref('')
const streaming = ref(false)
const msgsEl = ref<HTMLElement | null>(null)
let controller: AbortController | null = null

const current = computed(() => sessions.value.find((s) => s.id === currentId.value))

function loadSessions(): ChatSession[] {
  try {
    const raw = localStorage.getItem(STORE_KEY)
    return raw ? (JSON.parse(raw) as ChatSession[]) : []
  } catch {
    return []
  }
}

function persist(): void {
  try {
    const trimmed = sessions.value.slice(0, 50).map((s) => ({ ...s, messages: s.messages.slice(-200) }))
    localStorage.setItem(STORE_KEY, JSON.stringify(trimmed))
  } catch {
    /* 配额满等异常不影响页内交互 */
  }
}

function rid(): string {
  return `m-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

function scrollBottom(): void {
  void nextTick(() => {
    const el = msgsEl.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function newSession(): Promise<void> {
  try {
    const { session_id } = await createSession()
    sessions.value.unshift({
      id: session_id,
      title: `会话 ${new Date().toLocaleTimeString()}`,
      createdAt: Date.now(),
      messages: [],
    })
    currentId.value = session_id
    persist()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '会话创建失败')
  }
}

function switchSession(id: string): void {
  if (streaming.value) {
    ElMessage.warning('正在生成中,请先停止再切换会话')
    return
  }
  currentId.value = id
}

interface SseData {
  text?: unknown
  answer_id?: unknown
  message?: unknown
  prompt_tokens?: unknown
  completion_tokens?: unknown
  total_tokens?: unknown
}

function makeHandler(am: ChatMessage): (event: string, data: string) => void {
  return (event, data) => {
    let payload: SseData | null = null
    try {
      payload = JSON.parse(data) as SseData
    } catch {
      payload = null
    }
    if (event === 'delta' && typeof payload?.text === 'string') {
      am.text += payload.text
      scrollBottom()
    } else if (event === 'usage' && payload) {
      am.usage = {
        prompt_tokens: Number(payload.prompt_tokens ?? 0),
        completion_tokens: Number(payload.completion_tokens ?? 0),
        total_tokens: Number(payload.total_tokens ?? 0),
      }
    } else if (event === 'finish' && typeof payload?.answer_id === 'string') {
      am.answerId = payload.answer_id
    } else if (event === 'error') {
      am.error = (typeof payload?.message === 'string' && payload.message) || data || '未知错误'
      ElMessage.error(`生成失败:${am.error}`)
    }
  }
}

async function send(): Promise<void> {
  const text = input.value.trim()
  const session = current.value
  if (!text || streaming.value || !session) return
  input.value = ''
  session.messages.push({ id: rid(), role: 'user', text, done: true })
  if (session.messages.length === 1) session.title = text.slice(0, 16)
  const am: ChatMessage = { id: rid(), role: 'assistant', text: '', question: text, done: false }
  session.messages.push(am)
  streaming.value = true
  controller = new AbortController()
  scrollBottom()
  const run = (signal: AbortSignal): Promise<void> => chatStream(session.id, text, makeHandler(am), signal)
  try {
    try {
      await run(controller.signal)
    } catch (e) {
      // mock 重启后旧 session_id 失效:自动重建会话重试一次(其余错误不重试)
      if (e instanceof ApiError && e.code === 'SESSION_NOT_FOUND') {
        const { session_id } = await createSession()
        session.id = session_id
        currentId.value = session_id
        await run(controller.signal)
      } else {
        throw e
      }
    }
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      if (!am.text) am.text = '(已手动停止)'
    } else if (e instanceof ApiError) {
      am.error = e.message
      ElMessage.error(`生成失败:${e.message}`)
    } else {
      am.error = e instanceof Error ? e.message : String(e)
    }
  } finally {
    am.done = true
    streaming.value = false
    controller = null
    persist()
    scrollBottom()
  }
}

function stop(): void {
  controller?.abort()
}

function traceJump(am: ChatMessage): void {
  if (!am.answerId) return
  void router.push({ name: 'trace', params: { answerId: am.answerId }, query: am.question ? { q: am.question } : {} })
}

function onEnterKey(e: KeyboardEvent): void {
  if (e.isComposing) return
  e.preventDefault()
  void send()
}

function fmtTime(ts: number): string {
  return new Date(ts).toLocaleString()
}

onMounted(() => {
  if (!sessions.value.length) void newSession()
  else if (!current.value) currentId.value = sessions.value[0].id
})
</script>

<template>
  <div class="chat-page">
    <el-aside width="230px" class="chat-side">
      <el-button type="primary" plain :icon="Plus" class="new-btn" @click="newSession()">
        新建会话
      </el-button>
      <el-scrollbar class="side-list">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="side-item"
          :class="{ active: s.id === currentId }"
          @click="switchSession(s.id)"
        >
          <div class="side-title">{{ s.title }}</div>
          <div class="side-time">{{ fmtTime(s.createdAt) }}</div>
        </div>
      </el-scrollbar>
    </el-aside>

    <section class="chat-main">
      <div ref="msgsEl" class="chat-msgs">
        <div v-if="!current || current.messages.length === 0" class="chat-empty">
          <p>已创建会话,输入问题开始对话。</p>
          <p class="dim">回答以 SSE 流式返回:delta 增量渲染 → usage 用量角标 → finish 收尾(携带 answer_id)。</p>
        </div>
        <template v-for="m in current?.messages" :key="m.id">
          <div v-if="m.role === 'user'" class="msg user">
            <div class="bubble">{{ m.text }}</div>
          </div>
          <div v-else class="msg assistant">
            <div class="bubble" :class="{ 'has-error': m.error }">
              <div class="content">{{ m.text }}<span v-if="!m.done" class="cursor" /></div>
              <el-alert
                v-if="m.error"
                :title="`生成失败:${m.error}`"
                type="error"
                :closable="false"
                class="msg-error"
              />
              <div v-if="m.done && !m.error" class="msg-foot">
                <el-button
                  v-if="m.answerId"
                  size="small"
                  type="primary"
                  link
                  :icon="Search"
                  @click="traceJump(m)"
                >
                  溯源
                </el-button>
                <el-tag v-if="m.usage" size="small" type="info" effect="plain">
                  tokens {{ m.usage.prompt_tokens }}/{{ m.usage.completion_tokens }}/{{ m.usage.total_tokens }}
                </el-tag>
              </div>
            </div>
          </div>
        </template>
      </div>

      <div class="chat-input">
        <el-input
          v-model="input"
          type="textarea"
          resize="none"
          :autosize="{ minRows: 2, maxRows: 6 }"
          placeholder="输入问题,Enter 发送(Shift+Enter 换行)"
          @keydown.enter.exact="onEnterKey"
        />
        <div class="chat-actions">
          <el-button v-if="streaming" type="danger" plain @click="stop">停止生成</el-button>
          <el-button v-else type="primary" :disabled="!input.trim()" @click="send()">发送</el-button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  height: 100%;
  gap: 12px;
}
.chat-side {
  border-right: 1px solid var(--el-border-color-light);
  padding: 12px 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.new-btn {
  width: 100%;
}
.side-list {
  flex: 1;
}
.side-item {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
}
.side-item:hover {
  background: var(--el-fill-color-light);
}
.side-item.active {
  background: var(--el-color-primary-light-9);
}
.side-title {
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.side-time {
  font-size: 11px;
  color: #a8abb2;
  margin-top: 2px;
}
.chat-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.chat-msgs {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px 16px;
}
.chat-empty {
  text-align: center;
  color: #909399;
  margin-top: 18vh;
}
.chat-empty .dim {
  font-size: 12px;
}
.msg {
  display: flex;
  margin-bottom: 14px;
}
.msg.user {
  justify-content: flex-end;
}
.msg.assistant {
  justify-content: flex-start;
}
.bubble {
  max-width: 78%;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 14px;
  line-height: 1.7;
}
.msg.user .bubble {
  background: var(--el-color-primary);
  color: #fff;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg.assistant .bubble {
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  white-space: pre-wrap;
  word-break: break-word;
}
.msg.assistant .bubble.has-error {
  border-color: var(--el-color-danger-light-5);
}
.content {
  min-height: 1.7em;
}
.cursor {
  display: inline-block;
  width: 7px;
  background: var(--el-color-primary);
  animation: blink 1s step-end infinite;
  margin-left: 2px;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}
.msg-error {
  margin-top: 8px;
  --el-alert-message-font-size: 12px;
}
.msg-foot {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.chat-input {
  border-top: 1px solid var(--el-border-color-light);
  padding: 12px;
  display: flex;
  gap: 10px;
  align-items: flex-end;
}
.chat-input :deep(.el-textarea__inner) {
  --el-input-bg-color: var(--el-fill-color-blank);
}
.chat-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
