<template>
  <!-- 工单页根容器：左右分栏（左工单列表 + 右对话区） -->
  <div class="tickets-page">
    <!-- 左侧：工单列表 -->
    <div class="ticket-list-panel">
      <!-- 列表面板头部：标题 + 状态筛选 -->
      <div class="panel-header">
        <h3>客服工单</h3>
        <!-- 状态筛选：全部/待处理/已认领/已回复，切换即重新加载列表 -->
        <el-radio-group v-model="filterStatus" size="small" @change="loadTickets">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="pending">待处理</el-radio-button>
          <el-radio-button value="claimed">已认领</el-radio-button>
          <el-radio-button value="replied">已回复</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 工单列表区：遍历渲染工单项，点击切换右侧对话 -->
      <div class="ticket-list">
        <!-- 单个工单项：当前选中项高亮，点击触发 selectTicket -->
        <div
          v-for="t in tickets"
          :key="t.ticket_id"
          class="ticket-item"
          :class="{ active: activeTicketId === t.ticket_id }"
          @click="selectTicket(t)"
        >
          <!-- 工单项顶部：状态标签 + 工单号 -->
          <div class="ticket-top">
            <el-tag :type="statusTagType(t.status)" size="small">{{ statusLabel(t.status) }}</el-tag>
            <span class="ticket-id">{{ t.ticket_id }}</span>
          </div>
          <!-- 工单描述（无描述显示「转人工请求」） -->
          <p class="ticket-desc">{{ t.description || '转人工请求' }}</p>
          <!-- 创建时间 -->
          <span class="ticket-time">{{ formatTime(t.created_at) }}</span>
        </div>
        <!-- 无工单时的空状态 -->
        <el-empty v-if="tickets.length === 0" description="暂无工单" />
      </div>
    </div>

    <!-- 右侧：对话区（选中工单时显示） -->
    <div class="chat-panel" v-if="activeTicket">
      <!-- 对话区头部：工单号/状态/在线状态 + 认领/关闭按钮 -->
      <div class="chat-header">
        <div>
          <strong>{{ activeTicket.ticket_id }}</strong>
          <el-tag :type="statusTagType(activeTicket.status)" size="small" class="ml8">
            {{ statusLabel(activeTicket.status) }}
          </el-tag>
          <!-- 用户在线状态标识（在线时绿色高亮） -->
          <span class="online-dot" :class="{ on: detail?.user_online }">
            {{ detail?.user_online ? '用户在线' : '用户离线' }}
          </span>
        </div>
        <div>
          <!-- 待处理工单显示「认领」按钮 -->
          <el-button
            v-if="activeTicket.status === 'pending'"
            type="primary"
            size="small"
            @click="handleClaim"
          >
            认领工单
          </el-button>
          <!-- 关闭当前工单（清空选中状态并断开连接） -->
          <el-button size="small" @click="closeTicket">关闭工单</el-button>
        </div>
      </div>

      <!-- 对话消息区：滚动展示消息列表 -->
      <div class="chat-body" ref="chatBodyRef">
        <!-- 无消息时的空状态 -->
        <div class="chat-empty" v-if="detailMessages.length === 0">
          暂无对话记录
        </div>
        <!-- 遍历消息渲染气泡（按角色区分左右与样式） -->
        <div
          v-for="(m, i) in detailMessages"
          :key="i"
          class="chat-msg"
          :class="m.role"
        >
          <!-- 消息头：角色名 + 时间 -->
          <div class="msg-label">
            {{ roleLabel(m.role) }}
            <span class="msg-time">{{ m.time }}</span>
          </div>
          <!-- 消息气泡内容 -->
          <div class="msg-bubble" :class="m.role">
            {{ m.content }}
          </div>
        </div>
      </div>

      <!-- 输入区：可回复状态（已认领/已回复）显示输入框，否则显示提示 -->
      <div class="chat-input-area" v-if="canReply()">
        <!-- 回复内容输入框（Ctrl+Enter 快捷发送） -->
        <el-input
          v-model="replyText"
          placeholder="输入回复内容..."
          :rows="2"
          type="textarea"
          @keyup.enter.ctrl="sendReply"
        />
        <!-- 发送按钮：内容为空时禁用 -->
        <el-button type="primary" size="small" @click="sendReply" :disabled="!replyText.trim()" class="mt8">
          发送 (Ctrl+Enter)
        </el-button>
      </div>
      <!-- 不可回复状态提示：待处理需先认领 / 已关闭不可操作 -->
      <div class="chat-input-area disabled" v-else>
        <p>{{ activeTicket.status === 'pending' ? '请先认领工单' : '工单已关闭' }}</p>
      </div>
    </div>

    <!-- 空状态：未选中工单时展示 -->
    <div class="empty-panel" v-else>
      <el-empty description="请选择一个工单查看详情" />
    </div>
  </div>
</template>

<!--
 * ============================================================
 * 模块说明：客服工单页面（views/tickets/TicketsView.vue）
 *
 * 职责：
 *   - 左侧工单列表：按状态筛选（全部/待处理/已认领/已回复），点击选中工单
 *   - 右侧对话区：展示工单详情与历史消息（用户/AI 客服/人工客服三种角色气泡）
 *   - 工单操作：认领工单、发送回复、关闭工单
 *   - 实时通信：优先使用 WebSocket 推送消息；WebSocket 不可用时
 *     自动降级为 HTTP 接口发送 + 每 5 秒轮询兜底
 *
 * 消息角色（role）：user（用户）/ assistant（AI 客服）/ agent（人工客服）
 * ============================================================
 -->
<script setup lang="ts">
// Vue 组合式 API：ref 响应式状态、nextTick DOM 更新后回调、
// onBeforeUnmount 卸载清理、watch 监听变化（轮询启停）
import { ref, nextTick, onBeforeUnmount, watch } from 'vue'
// 工单模块相关 API：列表/详情/认领/回复及数据类型
import { getTickets, getTicketDetail, claimTicket, replyTicket, type TicketItem, type TicketDetail } from '@/api/tickets'
// Element Plus 消息提示
import { ElMessage } from 'element-plus'

// 工单列表状态筛选值（'' 表示全部）
const filterStatus = ref('')
// 工单列表数据
const tickets = ref<TicketItem[]>([])
// 当前选中的工单（null 表示未选中）
const activeTicket = ref<TicketItem | null>(null)
// 当前工单详情（含用户在线状态、历史消息）
const detail = ref<TicketDetail | null>(null)
// 当前对话区的消息列表（角色 + 内容 + 时间）
const detailMessages = ref<Array<{ role: string; content: string; time: string }>>([])
// 回复输入框内容
const replyText = ref('')
// 对话消息区 DOM 引用（用于滚动到底部）
const chatBodyRef = ref<HTMLElement>()

// WebSocket 实例（当前工单的管理员通道；null 表示未连接）
let ws: WebSocket | null = null
// 轮询定时器句柄（WebSocket 不可用时的兜底）
let pollTimer: ReturnType<typeof setInterval> | null = null

// ── Computed ──

// 当前选中工单的 ID（用于列表高亮与轮询监听）
const activeTicketId = ref('')

/**
 * 当前是否可发送回复（判定函数，供模板 v-if 使用）
 * 仅工单处于「已认领 / 已回复」状态时可回复
 * @returns {boolean} 可回复返回 true
 */
const canReply = () => {
  const status = activeTicket.value?.status
  return status === 'claimed' || status === 'replied'
}

// ── Helpers ──

/**
 * 工单状态 → 中文文案
 * @param s 状态值（pending/claimed/replied/closed）
 * @returns {string} 中文文案，未知状态原样返回
 */
function statusLabel(s: string) {
  const map: Record<string, string> = { pending: '待处理', claimed: '已认领', replied: '已回复', closed: '已关闭' }
  return map[s] || s
}

/**
 * 工单状态 → Element Plus 标签类型（待处理红/已认领黄/已回复绿/已关闭灰）
 * @param s 状态值
 * @returns 标签类型字符串
 */
function statusTagType(s: string): '' | 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, '' | 'success' | 'warning' | 'danger' | 'info'> = {
    pending: 'danger', claimed: 'warning', replied: 'success', closed: 'info',
  }
  return map[s] || 'info'
}

/**
 * 消息角色 → 中文名称
 * @param r 角色值（user/assistant/agent）
 * @returns {string} 中文角色名，未知角色原样返回
 */
function roleLabel(r: string) {
  const map: Record<string, string> = { user: '用户', assistant: 'AI客服', agent: '人工客服' }
  return map[r] || r
}

/**
 * 时间格式化：ISO 字符串去掉 T 并截取到分钟
 * @param t 原始时间字符串
 * @returns {string} 格式化后的时间（如 '2026-08-22 10:30'），空值返回 ''
 */
function formatTime(t: string) {
  if (!t) return ''
  return t.replace('T', ' ').slice(0, 16)
}

/**
 * 滚动对话区到底部
 * 等待 DOM 更新后，将滚动条置于内容最底部（展示最新消息）
 */
function scrollToBottom() {
  nextTick(() => {
    if (chatBodyRef.value) {
      chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
    }
  })
}

// ── 数据加载 ──

/**
 * 加载工单列表（异步）
 * 按当前状态筛选请求列表；失败时提示错误信息
 */
async function loadTickets() {
  try {
    const res = await getTickets(filterStatus.value || undefined)
    tickets.value = res.data.tickets || []
  } catch {
    ElMessage.error('加载工单列表失败')
  }
}

/**
 * 选中工单并加载详情（异步）
 * 步骤：设置选中状态 → 清空旧回复/详情/消息 →
 *       拉取工单详情 → 建立 WebSocket 连接 → 滚动到底部
 * @param t 被点击的工单数据
 */
async function selectTicket(t: TicketItem) {
  // 记录当前选中工单
  activeTicket.value = t
  activeTicketId.value = t.ticket_id
  // 清空回复输入框与上一工单的详情/消息
  replyText.value = ''
  detail.value = null
  detailMessages.value = []

  try {
    // 拉取工单详情（含历史消息与用户在线状态）
    const res = await getTicketDetail(t.ticket_id)
    detail.value = res.data
    detailMessages.value = detail.value?.messages || []

    // 连接管理员 WebSocket（实时接收该工单的新消息）
    connectAdminWS(t.ticket_id)
    scrollToBottom()
  } catch {
    ElMessage.error('加载工单详情失败')
  }
}

// ── WebSocket 实时通信 ──

/**
 * 连接指定工单的管理员 WebSocket 通道
 * 连接建立后监听 message 事件：收到服务端 'sent' 确认消息时，
 * 将本地已发送的回复追加到消息列表并清空输入框
 * @param ticketId 工单 ID
 */
function connectAdminWS(ticketId: string) {
  // 先断开旧连接，避免重复连接
  disconnectAdminWS()
  // 使用当前页面 host（默认 127.0.0.1）拼接 WebSocket 地址（后端 8000 端口）
  const host = window.location.hostname || '127.0.0.1'
  ws = new WebSocket(`ws://${host}:8000/api/ticket/admin/ws/${ticketId}`)
  // 收到服务端推送消息
  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      if (data.type === 'sent') {
        // 自己的消息已发送，追加到列表
        detailMessages.value.push({ role: 'agent', content: replyText.value, time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) })
        replyText.value = ''
        scrollToBottom()
      }
    } catch { /* ignore */ }
  }
  // 连接关闭时清空引用（触发轮询兜底）
  ws.onclose = () => { ws = null }
}

/**
 * 断开当前 WebSocket 连接并清空引用
 */
function disconnectAdminWS() {
  ws?.close()
  ws = null
}

// ── 操作 ──

/**
 * 认领工单（异步）
 * 调用认领接口，成功后本地更新工单状态为已认领并提示
 */
async function handleClaim() {
  // 未选中工单时直接返回
  if (!activeTicket.value) return
  try {
    // 调用后端认领接口
    await claimTicket(activeTicket.value.ticket_id)
    // 本地同步状态为已认领（驱动 UI 刷新）
    activeTicket.value.status = 'claimed'
    ElMessage.success('工单已认领')
  } catch {
    ElMessage.error('认领失败')
  }
}

/**
 * 发送回复（异步）
 * 优先走 WebSocket（实时推送）；WebSocket 未连接时降级为 HTTP 发送
 */
async function sendReply() {
  // 去除首尾空白后的回复内容
  const txt = replyText.value.trim()
  // 无内容、未选中工单或 WebSocket 未就绪时走兜底
  if (!txt || !activeTicket.value || !ws || ws.readyState !== WebSocket.OPEN) {
    if (!ws || ws?.readyState !== WebSocket.OPEN) {
      // WebSocket 不可用时走 HTTP 兜底
      await sendReplyHttp(txt)
    }
    return
  }
  // WebSocket 可用：发送 agent_message 消息（handler 固定为 '客服'）
  ws.send(JSON.stringify({ type: 'agent_message', content: txt, handler: '客服' }))
}

/**
 * HTTP 兜底发送回复（异步）
 * WebSocket 不可用时调用 HTTP 回复接口，成功后本地追加消息
 * @param content 回复内容
 */
async function sendReplyHttp(content: string) {
  // 未选中工单时直接返回
  if (!activeTicket.value) return
  try {
    // 调用 HTTP 回复接口
    await replyTicket(activeTicket.value.ticket_id, content, '客服')
    // 本地追加一条客服消息并清空输入框
    detailMessages.value.push({
      role: 'agent',
      content,
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    })
    replyText.value = ''
    scrollToBottom()
    ElMessage.success('已发送')
  } catch {
    ElMessage.error('发送失败')
  }
}

/**
 * 关闭当前工单（返回未选中状态）
 * 清空选中工单、详情与消息，并断开 WebSocket 连接
 */
function closeTicket() {
  activeTicket.value = null
  activeTicketId.value = ''
  detail.value = null
  detailMessages.value = []
  disconnectAdminWS()
}

// ── 轮询（WebSocket 不可用时的兜底） ──

/**
 * 监听当前选中工单 ID 变化：
 *  - 切换工单时先清除旧定时器
 *  - 有新选中工单时启动每 5 秒的轮询，拉取最新消息；
 *    若消息数量变化则刷新列表并滚动到底部
 */
watch(activeTicketId, (val) => {
  // 切换工单：先清除上一个定时器
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  if (val) {
    // 启动轮询定时器
    pollTimer = setInterval(async () => {
      // 工单已被关闭（ID 清空）时跳过
      if (!activeTicketId.value) return
      try {
        const res = await getTicketDetail(activeTicketId.value)
        const msgs = res.data.messages || []
        // 仅当消息数量发生变化时才更新（避免无意义的重渲染）
        if (msgs.length !== detailMessages.value.length) {
          detailMessages.value = msgs
          scrollToBottom()
        }
      } catch { /* ignore */ }
    }, 5000)
  }
})

// ── 生命周期 ──

// 组件初始化：加载工单列表（等价于 onMounted 内的首次加载）
loadTickets()

/**
 * 组件卸载前清理（生命周期钩子 onBeforeUnmount）
 * 断开 WebSocket 连接并清除轮询定时器，避免内存泄漏
 */
onBeforeUnmount(() => {
  disconnectAdminWS()
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
/* ---------- 整体布局 ---------- */
/* 页面容器：左右分栏，占满高度（顶部栏下方），白底圆角，隐藏溢出 */
.tickets-page { display: flex; height: calc(100vh - 120px); gap: 0; background: #fff; border-radius: 8px; overflow: hidden; }

/* ---------- 左侧工单列表面板 ---------- */
/* 列表面板：固定 320px 宽，右侧分割线，纵向排列 */
.ticket-list-panel { width: 320px; border-right: 1px solid #ebeef5; display: flex; flex-direction: column; }
/* 面板头部：内边距 + 底部细分割线 */
.panel-header { padding: 16px; border-bottom: 1px solid #ebeef5; }
/* 面板标题 */
.panel-header h3 { margin-bottom: 12px; font-size: 16px; }

/* 工单列表滚动区 */
.ticket-list { flex: 1; overflow-y: auto; padding: 8px; }
/* 单个工单项：圆角卡片，可点击，悬停高亮 */
.ticket-item { padding: 12px; border-radius: 6px; cursor: pointer; margin-bottom: 6px; border: 1px solid transparent; transition: all 0.2s; }
/* 悬停状态：浅灰背景 */
.ticket-item:hover { background: #f5f7fa; }
/* 选中状态：浅蓝背景 + 蓝色边框 */
.ticket-item.active { background: #ecf5ff; border-color: #409eff; }
/* 工单项顶部行（状态标签 + 工单号） */
.ticket-top { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
/* 工单号：灰色小号字 */
.ticket-id { font-size: 12px; color: #909399; }
/* 工单描述：单行省略号截断 */
.ticket-desc { font-size: 13px; color: #303133; margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
/* 创建时间：浅灰小号字 */
.ticket-time { font-size: 11px; color: #c0c4cc; }

/* ---------- 右侧对话面板 ---------- */
/* 对话面板：占据剩余宽度，纵向排列 */
.chat-panel { flex: 1; display: flex; flex-direction: column; }
/* 对话头部：两端布局，底部细分割线 */
.chat-header { padding: 12px 16px; border-bottom: 1px solid #ebeef5; display: flex; justify-content: space-between; align-items: center; }
/* 消息滚动区：浅灰背景，纵向排列 */
.chat-body { flex: 1; overflow-y: auto; padding: 16px; background: #f5f7fa; display: flex; flex-direction: column; gap: 12px; }
/* 无消息空状态 */
.chat-empty { text-align: center; color: #909399; padding: 40px; }

/* 消息气泡：最大宽度 75%，按角色左右对齐 */
.chat-msg { max-width: 75%; }
.chat-msg.user { align-self: flex-end; }
.chat-msg.assistant { align-self: flex-start; }
.chat-msg.agent { align-self: flex-end; }

/* 消息标签行（角色 + 时间） */
.msg-label { font-size: 11px; color: #909399; margin-bottom: 4px; }
.msg-time { margin-left: 6px; font-size: 10px; }

/* 消息气泡主体：圆角 + 文字排版 */
.msg-bubble { padding: 10px 14px; border-radius: 10px; font-size: 13px; line-height: 1.5; word-break: break-word; }
/* 用户消息：墨绿底白字 */
.msg-bubble.user { background: #4a7c59; color: #fff; }
/* AI 客服消息：白底灰字带边框 */
.msg-bubble.assistant { background: #fff; color: #303133; border: 1px solid #e4e7ed; }
/* 人工客服消息：蓝色底白字 */
.msg-bubble.agent { background: #409eff; color: #fff; }

/* 输入区：顶部细分割线 */
.chat-input-area { padding: 12px 16px; border-top: 1px solid #ebeef5; }
/* 不可回复状态的提示区（居中灰字） */
.chat-input-area.disabled { text-align: center; color: #909399; padding: 20px; }

/* 未选中工单时的空面板：居中 */
.empty-panel { flex: 1; display: flex; align-items: center; justify-content: center; }

/* 通用间距工具类 */
.ml8 { margin-left: 8px; }
.mt8 { margin-top: 8px; }
/* 用户在线状态文字：默认灰，在线时绿色 */
.online-dot { font-size: 11px; color: #c0c4cc; margin-left: 8px; }
.online-dot.on { color: #67c23a; }
</style>
