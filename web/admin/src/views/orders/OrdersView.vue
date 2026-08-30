<!--
 * ============================================================
 * 模块说明：订单管理页面（views/orders/OrdersView.vue）
 *
 * 职责：
 *   - 订单列表：按订单状态 Tab / 关键词筛选，分页展示
 *   - 订单详情：基础信息 + 状态流转时间线 + 商品明细
 *   - 订单操作：确认订单、取消订单（填原因）、发货（填物流）、完成订单
 *     操作按钮按订单当前状态条件渲染
 *
 * 订单状态机（order_status）：
 *   pending → confirmed → shipped → delivered → completed
 *   （任意非终态可 cancelled 取消）
 * ============================================================
 -->
<script setup lang="ts">
// Vue 响应式工具与生命周期钩子
import { ref, reactive, onMounted } from 'vue'
// Element Plus 消息提示与输入弹窗（取消原因输入用 prompt）
import { ElMessage, ElMessageBox } from 'element-plus'
// 订单模块相关 API：列表/详情/确认/发货/取消/完成及数据类型
import {
  getOrders, getOrder, confirmOrder, shipOrder, cancelOrder, completeOrder,
  type OrderItem,
} from '@/api/orders'

// ── 列表 ──
// 列表加载状态（表格 loading 遮罩）
const loading = ref(false)
// 订单列表数据
const list = ref<OrderItem[]>([])
// 订单总条数（分页用）
const total = ref(0)
// 列表筛选与分页参数：关键词、订单状态、支付状态、时间范围、页码、每页条数
const search = reactive({
  keyword: '', order_status: '', pay_status: '', start_time: '', end_time: '', page: 1, page_size: 20,
})

// 订单状态 → 中文文案的映射（用于表格与详情展示）
const statusMap: Record<string, string> = { pending: '待处理', confirmed: '已确认', shipped: '已发货', delivered: '已送达', completed: '已完成', cancelled: '已取消' }
// 订单状态 → Element Plus 标签类型的映射（待处理黄/终态绿/取消灰）
const statusTag: Record<string, string> = { pending: 'warning', confirmed: '', shipped: '', delivered: 'success', completed: 'success', cancelled: 'info' }

/**
 * 拉取订单列表（异步）
 * 按当前筛选条件请求分页数据，写入 list 与 total
 */
async function fetchList() {
  loading.value = true
  const res = await getOrders(search)
  list.value = res.data || []
  total.value = res.total
  loading.value = false
}

// ── 详情 ──
// 详情弹窗显示/隐藏
const detailVisible = ref(false)
// 当前查看的订单详情数据（null 表示未加载）
const detail = ref<OrderItem | null>(null)
/**
 * 打开订单详情弹窗（异步）
 * 根据订单 ID 拉取完整详情（含状态日志与商品明细）并展示
 * @param id 订单 ID
 */
async function openDetail(id: number) {
  const res = await getOrder(id)
  detail.value = res.data
  detailVisible.value = true
}

// ── 操作 ──
/**
 * 确认订单（异步）：仅待处理订单可确认
 * @param id 订单 ID
 */
async function handleConfirm(id: number) { await confirmOrder(id); ElMessage.success('已确认'); fetchList() }
/**
 * 取消订单（异步）
 * 弹窗输入取消原因后调用取消接口（空原因也允许提交）
 * @param id 订单 ID
 */
async function handleCancel(id: number) {
  // 弹出输入框让管理员填写取消原因
  const { value } = await ElMessageBox.prompt('请输入取消原因', '取消订单')
  await cancelOrder(id, { reason: value || '' })
  ElMessage.success('已取消')
  fetchList()
}
/**
 * 完成订单（异步）：仅已送达订单可标记完成
 * @param id 订单 ID
 */
async function handleComplete(id: number) { await completeOrder(id); ElMessage.success('已完成'); fetchList() }

// 发货弹窗
// 发货弹窗显示/隐藏
const shipVisible = ref(false)
// 发货表单：订单 ID、物流公司（默认顺丰）、物流单号（选填）
const shipForm = reactive({ order_id: 0, carrier: '顺丰', tracking_no: '' })
/**
 * 打开发货弹窗
 * @param id 订单 ID，写入表单后弹出
 */
function openShip(id: number) { shipForm.order_id = id; shipVisible.value = true }
/**
 * 提交发货（异步）
 * 调用发货接口（物流单号为空时传 undefined），成功后关闭弹窗并刷新列表
 */
async function handleShip() {
  await shipOrder(shipForm.order_id, { carrier: shipForm.carrier, tracking_no: shipForm.tracking_no || undefined })
  ElMessage.success('发货成功')
  shipVisible.value = false
  fetchList()
}

// 页面挂载：初始化加载订单列表
onMounted(fetchList)
</script>

<template>
  <!-- 页面容器（通用白底卡片样式） -->
  <div class="page-container">
    <!-- 工具栏：左侧为订单状态 Tab 筛选，右侧为关键词搜索 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <!-- 订单状态 Tab：切换即触发查询（全部/待处理/已确认/已发货/已完成/已取消） -->
        <el-tabs v-model="search.order_status" @tab-change="fetchList" style="margin-bottom:-17px">
          <el-tab-pane label="全部" name="" />
          <el-tab-pane label="待处理" name="pending" />
          <el-tab-pane label="已确认" name="confirmed" />
          <el-tab-pane label="已发货" name="shipped" />
          <el-tab-pane label="已完成" name="completed" />
          <el-tab-pane label="已取消" name="cancelled" />
        </el-tabs>
      </div>
      <!-- 关键词搜索：订单号/商品名，输入后回车或失焦触发查询 -->
      <el-input v-model="search.keyword" placeholder="订单号/商品名" clearable style="width:200px" @change="fetchList" />
    </div>

    <!-- 订单列表表格：订单号/金额/状态/支付状态/下单时间 -->
    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="order_no" label="订单号" width="180" />
      <el-table-column prop="id" label="ID" width="70" />
      <!-- 订单实付金额 -->
      <el-table-column prop="pay_amount" label="金额" width="100"><template #default="{row}">¥{{ row.pay_amount }}</template></el-table-column>
      <!-- 订单状态标签（颜色与文案随状态变化） -->
      <el-table-column label="订单状态" width="100"><template #default="{row}"><el-tag :type="statusTag[row.order_status]">{{ statusMap[row.order_status] || row.order_status }}</el-tag></template></el-table-column>
      <!-- 支付状态：已支付/未支付 -->
      <el-table-column label="支付状态" width="100"><template #default="{row}">{{ row.pay_status === 'paid' ? '已支付' : row.pay_status === 'unpaid' ? '未支付' : row.pay_status }}</template></el-table-column>
      <!-- 下单时间（格式化去掉 T，取前 19 位） -->
      <el-table-column prop="created_at" label="下单时间" width="170">
        <template #default="{row}">{{ row.created_at?.slice(0,19).replace('T',' ') }}</template>
      </el-table-column>
      <!-- 行操作：详情 + 按状态条件渲染的流转按钮 -->
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <!-- 查看订单详情 -->
          <el-button text type="primary" size="small" @click="openDetail(row.id)">详情</el-button>
          <!-- 待处理 → 确认订单 -->
          <el-button v-if="row.order_status==='pending'" text type="success" size="small" @click="handleConfirm(row.id)">确认</el-button>
          <!-- 已确认 → 发货 -->
          <el-button v-if="row.order_status==='confirmed'" text type="warning" size="small" @click="openShip(row.id)">发货</el-button>
          <!-- 非终态（未完成/未取消）→ 取消订单 -->
          <el-button v-if="!['completed','cancelled'].includes(row.order_status)" text type="danger" size="small" @click="handleCancel(row.id)">取消</el-button>
          <!-- 已送达 → 标记完成 -->
          <el-button v-if="row.order_status==='delivered'" text type="success" size="small" @click="handleComplete(row.id)">完成</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页器：切换页码触发重新查询 -->
    <el-pagination v-model:current-page="search.page" :total="total" :page-size="20" layout="total,prev,pager,next" style="margin-top:16px;justify-content:flex-end" @change="fetchList" />

    <!-- 详情弹窗（时间线）：基础信息 + 状态流转时间线 + 商品明细 -->
    <el-dialog title="订单详情" v-model="detailVisible" width="650px">
      <template v-if="detail">
        <!-- 订单基础信息描述列表 -->
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="订单号">{{ detail.order_no }}</el-descriptions-item>
          <el-descriptions-item label="金额">¥{{ detail.pay_amount }}</el-descriptions-item>
          <el-descriptions-item label="订单状态"><el-tag :type="statusTag[detail.order_status]">{{ statusMap[detail.order_status] }}</el-tag></el-descriptions-item>
          <el-descriptions-item label="支付状态">{{ detail.pay_status }}</el-descriptions-item>
        </el-descriptions>

        <!-- 状态流转时间线：下单/支付节点 + 后端返回的状态变更日志 -->
        <el-divider>状态流转</el-divider>
        <el-timeline>
          <!-- 下单节点 -->
          <el-timeline-item v-if="detail.created_at" timestamp="下单" :time="detail.created_at?.slice(0,19)" color="#409eff" />
          <!-- 支付节点 -->
          <el-timeline-item v-if="detail.paid_at" timestamp="支付" :time="detail.paid_at?.slice(0,19)" color="#67c23a" />
          <!-- 后端记录的状态变更日志（确认/发货/取消等） -->
          <el-timeline-item v-if="detail.logs" v-for="log in detail.logs" :key="log.id" :timestamp="log.action" :time="log.created_at?.slice(0,19)" color="#e6a23c">
            {{ log.detail }}
          </el-timeline-item>
        </el-timeline>

        <!-- 订单商品明细表格 -->
        <el-divider>订单明细</el-divider>
        <el-table :data="detail.items || []" size="small">
          <el-table-column prop="product_name" label="商品" />
          <el-table-column prop="quantity" label="数量" width="60" />
          <!-- 商品单价 -->
          <el-table-column label="单价" width="100"><template #default="{row}">¥{{ row.unit_price }}</template></el-table-column>
          <!-- 小计（数量 × 单价） -->
          <el-table-column label="小计" width="100"><template #default="{row}">¥{{ row.total_price }}</template></el-table-column>
        </el-table>
      </template>
    </el-dialog>

    <!-- 发货弹窗：填写物流公司与物流单号 -->
    <el-dialog title="发货" v-model="shipVisible" width="400px">
      <el-form :model="shipForm" label-width="80px">
        <!-- 物流公司 -->
        <el-form-item label="物流公司"><el-input v-model="shipForm.carrier" /></el-form-item>
        <!-- 物流单号（选填） -->
        <el-form-item label="物流单号"><el-input v-model="shipForm.tracking_no" placeholder="选填" /></el-form-item>
      </el-form>
      <!-- 弹窗底部按钮：取消 / 确认发货 -->
      <template #footer><el-button @click="shipVisible=false">取消</el-button><el-button type="primary" @click="handleShip">确认发货</el-button></template>
    </el-dialog>
  </div>
</template>
