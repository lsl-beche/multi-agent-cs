<template>
  <!--
    客服悬浮窗根节点：open 类控制展开/收起状态。
    整体包含：悬浮按钮（chat-fab）+ 对话面板（chat-panel，带展开动画）。
    通信方式：优先 WebSocket（流式回复），断开时自动降级为 HTTP 轮询兜底。
  -->
  <div class="chat-widget" :class="{ open: visible }">
    <!-- 悬浮按钮：点击切换面板开合；未展开时显示印章图标 + 未读消息数徽标 -->
    <div class="chat-fab" @click="toggleChat">
      <img v-if="!visible" src="/seal.svg" alt="客服" class="fab-seal" />
      <span v-else class="fab-icon">✕</span>
      <span v-if="unreadCount > 0 && !visible" class="fab-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
    </div>

    <!-- 对话窗口：仅在 visible 为 true 时渲染，带 chat-slide 展开动画 -->
    <transition name="chat-slide">
      <div v-if="visible" class="chat-panel">
        <!-- 面板头部：品牌信息 + 在线状态 + 转人工/关闭按钮 -->
        <div class="chat-header">
          <div class="header-left">
            <img src="/seal.svg" alt="茗韵" class="header-icon" />
            <div>
              <h4>茗韵茶庄 · 智能客服</h4>
              <!-- 连接状态指示：绿点在线 / 红点离线 -->
              <p class="header-status">{{ wsConnected ? '🟢 在线' : '🔴 离线' }}</p>
            </div>
          </div>
          <div class="header-right">
            <!-- 转人工：发送"转人工"消息触发人工客服接入 -->
            <el-button text size="small" class="transfer-btn" @click="requestHuman">转人工</el-button>
            <!-- 关闭面板 -->
            <el-button text size="small" @click="visible = false">✕</el-button>
          </div>
        </div>

        <!-- 消息滚动区：承载欢迎语、消息气泡、输入中动画，ref 用于自动滚动到底部 -->
        <div class="chat-body" ref="chatBodyRef">
          <!-- 欢迎区：无消息时展示，含快捷提问词 -->
          <div class="chat-welcome" v-if="messages.length === 0">
            <img src="/seal.svg" alt="茗韵" class="welcome-icon" />
            <p>您好，欢迎来到茗韵茶庄！</p>
            <p class="welcome-sub">有任何问题都可以问我哦~</p>
            <!-- 快捷提问词：点击直接发送对应问题 -->
            <div class="suggestion-chips">
              <span
                v-for="s in defaultSuggestions"
                :key="s"
                class="suggestion-chip"
                @click="sendMessage(s)"
              >{{ s }}</span>
            </div>
          </div>

          <!-- 消息列表：根据 role 渲染不同角色气泡（assistant 智能客服 / agent 人工客服 / user 用户） -->
          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            class="chat-message"
            :class="msg.role"
          >
            <!-- 智能客服头像：印章图 -->
            <div class="msg-avatar" v-if="msg.role === 'assistant'">
              <img src="/seal.svg" alt="茗韵" class="avatar-img" />
            </div>
            <!-- 人工客服头像：耳机表情 -->
            <div class="msg-avatar" v-if="msg.role === 'agent'">🎧</div>
            <!-- 消息气泡：展示发送人（人工客服）、正文、时间 -->
            <div class="msg-bubble" :class="msg.role">
              <div class="msg-sender" v-if="msg.handler && msg.role === 'agent'">{{ msg.handler }}</div>
              <div class="msg-text">{{ msg.content }}</div>
              <div class="msg-time">{{ msg.time }}</div>
            </div>
            <!-- 用户头像：人形表情 -->
            <div class="msg-avatar" v-if="msg.role === 'user'">👤</div>
          </div>

          <!-- "对方正在输入"动画：等待回复期间展示三个跳动圆点 -->
          <div v-if="typing" class="chat-message assistant">
            <div class="msg-avatar">🍵</div>
            <div class="msg-bubble assistant typing">
              <span class="dot"></span><span class="dot"></span><span class="dot"></span>
            </div>
          </div>
        </div>

        <!-- 底部输入区（在线时）：输入框 + 发送按钮，回车或点击发送 -->
        <div class="chat-footer" v-if="wsConnected">
          <el-input
            v-model="input"
            placeholder="输入您的问题..."
            @keyup.enter="sendMessage()"
            :disabled="typing"
            class="chat-input"
          >
            <template #append>
              <el-button :icon="Promotion" @click="sendMessage()" :disabled="typing || !input.trim()" />
            </template>
          </el-input>
        </div>
        <!-- 底部重连区（离线时）：提示连接断开并提供重新连接按钮 -->
        <div class="chat-footer disconnected" v-else>
          <p>连接已断开</p>
          <el-button size="small" @click="connect" :loading="connecting">重新连接</el-button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
// ── 依赖引入 ──
import { ref, nextTick, onBeforeUnmount, onMounted, watch } from 'vue' // Vue 响应式/生命周期/DOM 更新后回调
import { useAuthStore } from '@/stores/auth' // 认证状态仓库（获取用户 ID 标识身份）
import { ElMessage } from 'element-plus' // Element Plus 消息提示
import { Promotion } from '@element-plus/icons-vue' // 发送按钮图标
import api from '@/api' // 全局 axios 实例（HTTP 兜底请求）

// ── 基础 UI 状态 ──
const auth = useAuthStore() // 认证状态：取 auth.user.id 作为用户标识
const visible = ref(false) // 聊天面板是否展开
const input = ref('') // 输入框内容（双向绑定）
// 消息列表：role 取值 'user'（用户）/ 'assistant'（智能客服）/ 'agent'（人工客服），
// handler 为人工客服昵称（可选），time 为消息发送时刻（HH:mm）
const messages = ref<{ role: string; content: string; time: string; handler?: string }[]>([])
const typing = ref(false) // 是否正在等待回复（控制"输入中"动画）
const wsConnected = ref(false) // WebSocket 是否已连接（决定面板头部在线状态与底部输入区）
const connecting = ref(false) // 是否正在建立连接（用于重连按钮 loading 态）
const unreadCount = ref(0) // 未读消息数（面板收起时新消息计数，展示在悬浮按钮徽标）
const chatBodyRef = ref<HTMLElement>() // 消息滚动区 DOM 引用，用于自动滚动到底部

// ── WebSocket 连接状态 ──
let ws: WebSocket | null = null // 当前 WebSocket 实例（未连接为 null）
let reconnectTimer: ReturnType<typeof setTimeout> | null = null // 断线重连定时器句柄

// ── 流式接收状态 ──
const streamingContent = ref('')       // 当前累积的流式内容
let streamingMsgIndex = -1             // 当前流式消息在 messages 数组中的索引

// ── 会话与历史状态 ──
const sessionId = getOrCreateSessionId() // 会话 ID：从 localStorage 读取或首次生成并持久化
let historyLoaded = false // 历史消息是否已加载（避免重复请求）
let wsTimeoutRef: ReturnType<typeof setTimeout> | null = null // WS 超时兜底定时器句柄

// 快捷提问词列表：欢迎区展示，点击后直接作为消息发送
const defaultSuggestions = [
  '茶叶怎么保存？',
  '有什么适合送礼的茶？',
  '如何查询我的订单？',
  '龙井和碧螺春有什么区别？',
]

// ── 会话 ID 管理 ──
// 作用：从 localStorage 读取会话 ID；若不存在则生成新 ID（时间戳 + 随机串）并持久化
// 参数：无；返回值：会话 ID 字符串（形如 sess_<时间戳>_<随机串>）
function getOrCreateSessionId(): string {
  let sid = localStorage.getItem('chat_session_id')
  if (!sid) {
    sid = 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8)
    localStorage.setItem('chat_session_id', sid)
  }
  return sid
}

// ── 用户身份标识 ──
// 作用：已登录用户返回其用户 ID；未登录用户返回 "guest_" + 会话 ID，作为游客标识
// 参数：无；返回值：用户标识字符串
function getUserId(): string {
  return auth.user?.id ? String(auth.user.id) : 'guest_' + sessionId
}

// ── 当前时刻格式化 ──
// 作用：返回 "HH:mm" 格式的当前时间（用于消息气泡时间戳）
// 参数：无；返回值：格式化后的时间字符串
function now() {
  const d = new Date()
  return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0')
}

// ── 历史消息加载 ──

// 作用：面板首次打开时从服务端拉取该会话的历史消息并渲染；
//       已加载或列表非空时直接返回，避免重复请求
// 参数：无；返回值：Promise<void>
async function loadChatHistory() {
  if (historyLoaded || messages.value.length > 0) return // 已加载过则跳过
  try {
    const res = await api.get('/chat/history', { params: { session_id: sessionId } }) // 按会话 ID 请求历史
    const history = res.data?.data?.messages || []
    if (history.length > 0) {
      // 将服务端历史格式转换为前端格式
      messages.value = history.map((h: { role: string; content: string; ts?: number; time?: string }) => ({
        role: h.role === 'user' ? 'user' : (h.role === 'agent' ? 'agent' : 'assistant'),
        content: h.content,
        time: h.ts ? formatTimestamp(h.ts) : '',
      }))
      scrollToBottom() // 渲染后滚动到最新消息
    }
  } catch {
    // 静默失败，聊天功能仍然可用
  }
  historyLoaded = true // 无论成功与否都标记已加载，避免重复请求
}

// ── 时间戳格式化 ──
// 作用：将服务端返回的秒级时间戳转为 "HH:mm" 显示格式
// 参数：ts —— 秒级 Unix 时间戳；返回值：格式化后的时间字符串
function formatTimestamp(ts: number): string {
  const d = new Date(ts * 1000)
  return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0')
}

// ── 滚动到底部 ──
// 作用：DOM 更新完成后将消息区滚动条置于最底部，保证最新消息可见
// 参数：无；返回值：无
function scrollToBottom() {
  nextTick(() => {
    if (chatBodyRef.value) {
      chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
    }
  })
}

// ── WS 超时兜底 ──

// 作用：清除 WS 回复超时定时器，避免内存泄漏或误触发 HTTP 兜底
// 参数：无；返回值：无
function clearWsTimeout() {
  if (wsTimeoutRef) { clearTimeout(wsTimeoutRef); wsTimeoutRef = null }
}

// ── HTTP 兜底请求 ──
// 作用：WebSocket 发送后长时间无回复（超时）时，改用 HTTP POST /chat 获取一次完整回复；
//       仅在等待回复（typing 为 true）时才执行，避免重复兜底
// 参数：msg —— 用户发送的原始消息文本；返回值：Promise<void>
async function fallbackToHttp(msg: string) {
  if (!typing.value) return
  try {
    const res = await api.post('/chat', {
      session_id: sessionId,
      user_id: getUserId(),
      message: msg,
    })
    typing.value = false // 收到回复后结束等待态
    addMessage('assistant', res.data?.data?.answer || res.data?.answer || '抱歉，暂时无法回复。')
  } catch {
    typing.value = false
    addMessage('assistant', '抱歉，回复超时，请稍后再试。')
  }
}

// ── WS 消息处理 ──

// 作用：处理 WebSocket 收到的服务端消息（JSON 字符串），按消息类型分发：
//       chunk —— 流式回复分片，逐字追加到当前气泡；
//       done  —— 流式回复结束，若携带 replace 则用完整回复替换被污染的流式内容；
//       error —— 服务端错误，展示错误提示；
//       agent —— 人工客服推送的完整消息。
// 参数：event —— WebSocket MessageEvent（data 为 JSON 字符串）；返回值：无
function handleWsMessage(event: MessageEvent) {
  try {
    const data = JSON.parse(event.data)
    if (data.type === 'chunk') {
      const token = data.content as string
      if (!token) return

      if (streamingMsgIndex === -1) {
        // 第一个 token：结束 typing 动画，创建新消息气泡
        typing.value = false
        streamingContent.value = token
        streamingMsgIndex = messages.value.length
        messages.value.push({ role: 'assistant', content: token, time: now() })
      } else {
        // 后续 token：追加到当前气泡
        streamingContent.value += token
        messages.value[streamingMsgIndex].content = streamingContent.value
      }
      scrollToBottom()
    } else if (data.type === 'done') {
      clearWsTimeout()
      typing.value = false
      // tool_call 场景：用干净最终回复替换被污染的流式内容
      if (data.replace && streamingMsgIndex >= 0) {
        messages.value[streamingMsgIndex].content = data.replace
      }
      streamingContent.value = ''
      streamingMsgIndex = -1
    } else if (data.type === 'error') {
      clearWsTimeout()
      typing.value = false
      streamingContent.value = ''
      streamingMsgIndex = -1
      addMessage('assistant', '抱歉，服务暂时不可用：' + (data.detail || '未知错误'))
    } else if (data.type === 'agent') {
      // 人工客服消息推送（完整消息，非流式）
      typing.value = false
      streamingContent.value = ''
      streamingMsgIndex = -1
      addMessage('agent', data.content, data.handler)
    }
  } catch {
    // ignore invalid JSON
  }
}

// ── 面板开合控制 ──
// 作用：切换聊天面板展开/收起；展开时清零未读数、加载历史消息、
//       若未连接则建立连接，并滚动到底部
// 参数：无；返回值：无
function toggleChat() {
  visible.value = !visible.value
  if (visible.value) {
    unreadCount.value = 0 // 打开面板视为已读
    loadChatHistory() // 首次打开时加载历史消息
    if (!wsConnected.value && !connecting.value) {
      connect() // 未连接则自动建立连接
    }
    scrollToBottom()
  }
}

// ── WebSocket ──
// 作用：构建 WebSocket 连接地址并建立连接：
//       开发环境（localhost/127.0.0.1）直连 127.0.0.1:8000，
//       生产环境使用当前站点 host；协议随页面协议自动选择 ws/wss
// 参数：无；返回值：无
function connect() {
  if (connecting.value) return // 已在连接中则跳过
  connecting.value = true

  const token = localStorage.getItem('shop_token') || ''
  const tokenSuffix = token ? `?token=${encodeURIComponent(token)}` : ''
  // 生产化：VITE_WS_URL 配置优先（如 wss://mall.example.com/api/chat/ws）
  const envWs = import.meta.env.VITE_WS_URL as string | undefined
  if (envWs) {
    tryConnect(`${envWs}${envWs.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`)
    return
  }
  // 动态构建 WebSocket URL：开发环境直连 8000，生产环境用相对路径
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = location.hostname === 'localhost' || location.hostname === '127.0.0.1'
    ? '127.0.0.1:8000'
    : location.host
  const wsUrl = `${proto}//${host}/api/chat/ws${tokenSuffix}`
  tryConnect(wsUrl)
}

// 作用：实际创建 WebSocket 实例并绑定 onopen/onmessage/onclose/onerror 回调；
//       断开或出错时若面板仍打开则按不同延迟自动重连
// 参数：url —— WebSocket 服务地址；返回值：无
function tryConnect(url: string) {
  if (ws) { // 若存在旧连接先解除回调并关闭，避免重复监听
    ws.onerror = null
    ws.onclose = null
    ws.close()
    ws = null
  }

  try {
    ws = new WebSocket(url)
  } catch {
    connecting.value = false
    return
  }

  // 连接成功：更新在线状态与连接中标记
  ws.onopen = () => {
    wsConnected.value = true
    connecting.value = false
  }

  // 收到消息：统一交给 handleWsMessage 分发处理
  ws.onmessage = handleWsMessage

  // 连接关闭：标记离线；面板打开时 3 秒后自动重连
  ws.onclose = () => {
    wsConnected.value = false
    connecting.value = false
    ws = null
    if (visible.value) {
      reconnectTimer = setTimeout(connect, 3000)
    }
  }

  // 连接出错：标记离线并关闭连接；面板打开时 5 秒后自动重连
  ws.onerror = () => {
    wsConnected.value = false
    connecting.value = false
    ws?.close()
    ws = null
    if (visible.value) {
      reconnectTimer = setTimeout(connect, 5000)
    }
  }
}

// ── 发送消息 ──
// 作用：发送用户消息：先本地追加用户气泡，随后优先走 WebSocket；
//       若 WS 未连接则走 HTTP 兜底；WS 发送后 60 秒无回复自动切 HTTP 兜底
// 参数：text —— 可选，直接传入要发送的文本（如快捷提问词）；不传则取输入框内容；
//       返回值：Promise<void>
async function sendMessage(text?: string) {
  const msg = (text || input.value).trim() // 取输入内容并去除首尾空格
  if (!msg || typing.value) return // 空消息或正在等待回复时忽略
  if (!text) input.value = '' // 手动输入发送后清空输入框（快捷词不清空）

  // 如果上一轮流式还没完成，先结束它
  if (streamingMsgIndex !== -1) {
    streamingContent.value = ''
    streamingMsgIndex = -1
  }

  addMessage('user', msg) // 本地先渲染用户消息
  typing.value = true // 进入等待回复状态（显示"输入中"动画）

  try {
    // 优先走 WebSocket
    if (wsConnected.value && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        session_id: sessionId,
        user_id: getUserId(),
        message: msg,
      }))

      // 60秒内无回复自动切 HTTP 兜底
      wsTimeoutRef = setTimeout(fallbackToHttp, 60000, msg)
    } else {
      // HTTP 兜底
      const res = await api.post('/chat', {
        session_id: sessionId,
        user_id: getUserId(),
        message: msg,
      })
      typing.value = false
      addMessage('assistant', res.data.answer || '抱歉，暂时无法回复。')
    }
  } catch {
    typing.value = false
    // HTTP 也失败了，尝试重连 WebSocket
    if (!wsConnected.value) {
      addMessage('assistant', '连接失败，正在尝试重新连接...')
      connect()
    } else {
      addMessage('assistant', '抱歉，发送失败，请稍后再试。')
    }
  }
}

// ── 转人工 ──
// 作用：发送"转人工"消息，触发服务端接入人工客服
// 参数：无；返回值：无
function requestHuman() {
  sendMessage('转人工')
}

// ── 追加消息 ──
// 作用：将一条消息追加到消息列表末尾，并自动滚动到底部；
//       面板收起时未读计数 +1
// 参数：role —— 消息角色（user/assistant/agent）；content —— 消息正文；
//       handler —— 人工客服昵称（可选）；返回值：无
function addMessage(role: string, content: string, handler?: string) {
  const msg: { role: string; content: string; time: string; handler?: string } = { role, content, time: now() }
  if (handler) msg.handler = handler
  messages.value.push(msg)
  if (!visible.value) unreadCount.value++ // 面板未打开时累计未读数
  scrollToBottom()
}

// 面板打开时自动连接
watch(visible, (val) => {
  if (val && !wsConnected.value && !connecting.value) {
    connect()
  }
})

onMounted(() => {
  // 预连接（后台静默连接，不阻塞页面）
  connect()
})

onBeforeUnmount(() => {
  // 组件卸载前清理：清除重连定时器并关闭 WebSocket，防止泄漏
  if (reconnectTimer) clearTimeout(reconnectTimer)
  ws?.close()
  ws = null
})
</script>

<style scoped>
/* ── 根节点：固定悬浮于视口右下角，层级最高 ── */
.chat-widget {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 9999;
}

/* ── 悬浮按钮 ── */
.chat-fab {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3f5d4a, #26392e);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow:
    0 6px 22px rgba(63, 93, 74, 0.45),
    inset 0 0 0 1.5px rgba(217, 198, 163, 0.45);
  transition: all 0.3s;
  position: relative;
}

.chat-fab:hover {
  transform: scale(1.08);
  box-shadow:
    0 8px 30px rgba(63, 93, 74, 0.55),
    inset 0 0 0 1.5px rgba(217, 198, 163, 0.65);
}

.open .chat-fab {
  background: #2c2a26;
  box-shadow: 0 4px 20px rgba(44, 42, 38, 0.45);
}

.fab-seal {
  width: 32px;
  height: 32px;
  border-radius: 8px;
}

.fab-icon {
  font-size: 22px;
  line-height: 1;
}

.fab-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  background: #b3453a;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  min-width: 20px;
  height: 20px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 5px;
  border: 2px solid #fff;
}

/* ── 对话面板 ── */
.chat-panel {
  position: absolute;
  bottom: 72px;
  right: 0;
  width: 380px;
  height: 520px;
  background: var(--card);
  border-radius: 18px;
  border: 1px solid var(--line);
  box-shadow: 0 18px 54px rgba(44, 42, 38, 0.22);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── 进入/离开动画 ── */
.chat-slide-enter-active,
.chat-slide-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.chat-slide-enter-from,
.chat-slide-leave-to {
  opacity: 0;
  transform: translateY(20px) scale(0.95);
}

/* ── Header ── */
.chat-header {
  background: linear-gradient(135deg, #26392e, #3f5d4a);
  padding: 14px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  border-bottom: 2px solid var(--gold);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-icon {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.header-left h4 {
  color: var(--gold-soft);
  font-size: 14px;
  margin-bottom: 2px;
  letter-spacing: 1px;
}

.header-status {
  color: rgba(250, 246, 239, 0.62);
  font-size: 11px;
}

.header-right {
  display: flex;
  gap: 4px;
}

.transfer-btn {
  color: var(--gold-soft) !important;
  font-size: 12px !important;
}

.header-right .el-button {
  color: rgba(250, 246, 239, 0.72) !important;
  font-size: 16px !important;
}

/* ── Body ── */
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: var(--paper);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 消息区细滚动条样式 */
.chat-body::-webkit-scrollbar { width: 4px; }
.chat-body::-webkit-scrollbar-track { background: transparent; }
.chat-body::-webkit-scrollbar-thumb { background: var(--gold-soft); border-radius: 2px; }

/* Welcome */
.chat-welcome {
  text-align: center;
  padding: 30px 10px;
}

.welcome-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  margin-bottom: 12px;
  box-shadow: 0 4px 16px rgba(63, 93, 74, 0.25);
}

.chat-welcome p {
  color: var(--ink);
  font-size: 15px;
  font-weight: 600;
  font-family: var(--font-serif);
}

.welcome-sub {
  color: var(--ink-soft) !important;
  font-size: 13px !important;
  font-weight: 400 !important;
  margin-top: 4px;
  font-family: var(--font-sans) !important;
}

.suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
  justify-content: center;
}

.suggestion-chip {
  display: inline-block;
  background: var(--card);
  border: 1px solid var(--tea);
  color: var(--tea);
  font-size: 12px;
  padding: 5px 12px;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.suggestion-chip:hover {
  background: var(--tea);
  color: #fff;
}

/* ── Message ── */
.chat-message {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.chat-message.user {
  flex-direction: row-reverse;
}

.msg-avatar {
  font-size: 22px;
  flex-shrink: 0;
  line-height: 1;
}

.avatar-img {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  box-shadow: 0 1px 6px rgba(44, 42, 38, 0.25);
}

.msg-bubble {
  max-width: 75%;
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.msg-bubble.assistant {
  background: var(--card);
  color: var(--ink);
  border-bottom-left-radius: 4px;
  border: 1px solid var(--line);
  box-shadow: var(--shadow-sm);
}

.msg-bubble.user {
  background: linear-gradient(135deg, #3f5d4a, #314a3b);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.msg-bubble.agent {
  background: linear-gradient(135deg, #b08d57, #a17d4a);
  color: #fff;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 6px rgba(176, 141, 87, 0.3);
}

.msg-sender {
  font-size: 10px;
  color: rgba(255,255,255,0.7);
  margin-bottom: 2px;
}

.msg-bubble.typing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 14px 18px;
}

.msg-bubble.typing .dot {
  width: 7px;
  height: 7px;
  background: #a9c4b3;
  border-radius: 50%;
  animation: typing-bounce 1.4s infinite;
}

/* "输入中"三个圆点：依次延迟 0.2s/0.4s 实现波浪式跳动 */
.msg-bubble.typing .dot:nth-child(2) { animation-delay: 0.2s; }
.msg-bubble.typing .dot:nth-child(3) { animation-delay: 0.4s; }

/* ── 圆点跳动动画关键帧 ── */
@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-6px); }
}

.msg-time {
  font-size: 10px;
  color: var(--ink-soft);
  margin-top: 4px;
  opacity: 0.8;
}

.msg-bubble.user .msg-time {
  color: rgba(255, 255, 255, 0.7);
}

/* ── Footer ── */
.chat-footer {
  padding: 10px 12px;
  border-top: 1px solid var(--line);
  background: var(--card);
  flex-shrink: 0;
}

.chat-footer.disconnected {
  text-align: center;
  padding: 14px;
}

.chat-footer.disconnected p {
  color: var(--ink-soft);
  font-size: 12px;
  margin-bottom: 8px;
}

/* 输入框圆角与配色定制（深挖 Element Plus 内部类） */
.chat-input :deep(.el-input__wrapper) {
  border-radius: 20px !important;
  background: var(--paper);
}

.chat-input :deep(.el-input-group__append) {
  background: var(--tea);
  border: none;
  border-radius: 0 20px 20px 0;
}

.chat-input :deep(.el-input-group__append .el-button) {
  color: #fff;
}

/* ── Responsive ── */
/* 移动端：面板宽度自适应视口，高度限制为 60vh */
@media (max-width: 480px) {
  .chat-panel {
    width: calc(100vw - 32px);
    height: 60vh;
    right: -8px;
  }
}
</style>
