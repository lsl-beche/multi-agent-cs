import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/api'

export function useChatWidget() {
  const auth = useAuthStore()
  const visible = ref(false)
  const input = ref('')
  const messages = ref<Array<{ role: string; content: string; time: string; handler?: string }>>([])
  const typing = ref(false)
  const wsConnected = ref(false)
  const connecting = ref(false)
  const unreadCount = ref(0)
  const chatBodyRef = ref<HTMLElement>()
  const streamingContent = ref('')

  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let streamingMsgIndex = -1
  let historyLoaded = false
  let wsTimeoutRef: ReturnType<typeof setTimeout> | null = null

  const sessionId = getOrCreateSessionId()
  const defaultSuggestions = [
    '茶叶怎么保存？',
    '有什么适合送礼的茶？',
    '如何查询我的订单？',
    '龙井和碧螺春有什么区别？',
  ]

  function getOrCreateSessionId(): string {
    let sid = localStorage.getItem('chat_session_id')
    if (!sid) {
      sid = 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8)
      localStorage.setItem('chat_session_id', sid)
    }
    return sid
  }

  function getUserId(): string {
    return auth.user?.id ? String(auth.user.id) : 'guest_' + sessionId
  }

  function now(): string {
    const d = new Date()
    return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0')
  }

  function formatTimestamp(ts: number): string {
    const d = new Date(ts * 1000)
    return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0')
  }

  function scrollToBottom() {
    nextTick(() => {
      if (chatBodyRef.value) chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
    })
  }

  function clearWsTimeout() {
    if (wsTimeoutRef) {
      clearTimeout(wsTimeoutRef)
      wsTimeoutRef = null
    }
  }

  async function loadChatHistory() {
    if (historyLoaded || messages.value.length > 0) return
    try {
      const res = await api.get('/chat/history', { params: { session_id: sessionId } })
      const history = res.data?.data?.messages || []
      if (Array.isArray(history) && history.length > 0) {
        messages.value = history.map((h: { role: string; content: string; ts?: number; time?: string }) => ({
          role: h.role === 'agent' ? 'agent' : h.role === 'user' ? 'user' : 'assistant',
          content: h.content,
          time: h.ts ? formatTimestamp(h.ts) : h.time || '',
        }))
        scrollToBottom()
      }
    } catch {
      // 静默失败，聊天仍可用
    }
    historyLoaded = true
  }

  function addMessage(role: string, content: string, handler?: string) {
    const msg: { role: string; content: string; time: string; handler?: string } = { role, content, time: now() }
    if (handler) msg.handler = handler
    messages.value.push(msg)
    if (!visible.value) unreadCount.value++
    scrollToBottom()
  }

  async function fallbackToHttp(msg: string) {
    if (!typing.value) return
    try {
      const res = await api.post('/chat', { session_id: sessionId, user_id: getUserId(), message: msg })
      typing.value = false
      addMessage('assistant', res.data?.data?.answer || res.data?.answer || '抱歉，暂时无法回复。')
    } catch {
      typing.value = false
      addMessage('assistant', '抱歉，回复超时，请稍后再试。')
    }
  }

  function handleWsMessage(event: MessageEvent) {
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'chunk') {
        const token = data.content as string
        if (!token) return
        if (streamingMsgIndex === -1) {
          typing.value = false
          streamingContent.value = token
          streamingMsgIndex = messages.value.length
          messages.value.push({ role: 'assistant', content: token, time: now() })
        } else {
          streamingContent.value += token
          messages.value[streamingMsgIndex].content = streamingContent.value
        }
        scrollToBottom()
      } else if (data.type === 'done') {
        clearWsTimeout()
        typing.value = false
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
        typing.value = false
        streamingContent.value = ''
        streamingMsgIndex = -1
        addMessage('agent', data.content, data.handler)
      }
    } catch {
      // ignore
    }
  }

  function connect() {
    if (connecting.value) return
    connecting.value = true
    const token = localStorage.getItem('shop_token') || ''
    const tokenSuffix = token ? `?token=${encodeURIComponent(token)}` : ''
    const envWs = import.meta.env.VITE_WS_URL as string | undefined
    if (envWs) {
      tryConnect(`${envWs}${envWs.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`)
      return
    }
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = location.hostname === 'localhost' || location.hostname === '127.0.0.1' ? '127.0.0.1:8000' : location.host
    tryConnect(`${proto}//${host}/api/chat/ws${tokenSuffix}`)
  }

  function tryConnect(url: string) {
    if (ws) {
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
    ws.onopen = () => {
      wsConnected.value = true
      connecting.value = false
    }
    ws.onmessage = handleWsMessage
    ws.onclose = () => {
      wsConnected.value = false
      connecting.value = false
      ws = null
      if (visible.value) reconnectTimer = setTimeout(connect, 3000)
    }
    ws.onerror = () => {
      wsConnected.value = false
      connecting.value = false
      ws?.close()
      ws = null
      if (visible.value) reconnectTimer = setTimeout(connect, 5000)
    }
  }

  function toggleChat() {
    visible.value = !visible.value
    if (visible.value) {
      unreadCount.value = 0
      loadChatHistory()
      if (!wsConnected.value && !connecting.value) connect()
      scrollToBottom()
    }
  }

  async function sendMessage(text?: string) {
    const msg = (text || input.value).trim()
    if (!msg || typing.value) return
    if (!text) input.value = ''
    if (streamingMsgIndex !== -1) {
      streamingContent.value = ''
      streamingMsgIndex = -1
    }
    addMessage('user', msg)
    typing.value = true
    try {
      if (wsConnected.value && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ session_id: sessionId, user_id: getUserId(), message: msg }))
        wsTimeoutRef = setTimeout(fallbackToHttp, 60000, msg)
      } else {
        const res = await api.post('/chat', { session_id: sessionId, user_id: getUserId(), message: msg })
        typing.value = false
        addMessage('assistant', res.data.answer || '抱歉，暂时无法回复。')
      }
    } catch {
      typing.value = false
      if (!wsConnected.value) {
        addMessage('assistant', '连接失败，正在尝试重新连接...')
        connect()
      } else {
        addMessage('assistant', '抱歉，发送失败，请稍后再试。')
      }
    }
  }

  function requestHuman() {
    sendMessage('转人工')
  }

  watch(visible, (val) => {
    if (val && !wsConnected.value && !connecting.value) connect()
  })
  onMounted(() => connect())
  onBeforeUnmount(() => {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    ws?.close()
    ws = null
  })

  return {
    visible,
    input,
    messages,
    typing,
    wsConnected,
    connecting,
    unreadCount,
    chatBodyRef,
    defaultSuggestions,
    toggleChat,
    sendMessage,
    requestHuman,
  }
}
