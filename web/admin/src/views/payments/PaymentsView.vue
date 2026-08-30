<!--
 * ============================================================
 * 模块说明：支付管理页面（views/payments/PaymentsView.vue）
 *
 * 职责（两个 Tab）：
 *   1) 支付流水：按渠道/状态筛选分页展示，含流水号、交易号、金额等
 *   2) 退款审批：按状态筛选分页展示，对待审核退款执行通过/驳回操作
 * ============================================================
 -->
<script setup lang="ts">
// Vue 响应式工具与生命周期钩子
import { ref, reactive, onMounted } from 'vue'
// Element Plus 消息提示
import { ElMessage } from 'element-plus'
// 支付模块相关 API：支付流水/退款列表/退款审批及数据类型
import { getPayments, getRefunds, approveRefund, rejectRefund, type PaymentItem, type RefundItem } from '@/api/payments'

// ── TAB ──
// 当前激活的 Tab：'payments'（支付流水）/ 'refunds'（退款审批）
const activeTab = ref('payments')

// ── 支付流水 ──
// 支付流水列表加载状态
const payLoading = ref(false)
// 支付流水列表数据
const payList = ref<PaymentItem[]>([])
// 支付流水总条数（分页用）
const payTotal = ref(0)
// 支付流水筛选与分页参数：渠道、状态、页码、每页条数
const paySearch = reactive({ channel: '', status: '', page: 1, page_size: 20 })

/**
 * 拉取支付流水列表（异步）
 * 按当前筛选条件请求分页数据，写入 payList 与 payTotal
 */
async function fetchPayments() {
  payLoading.value = true
  const res = await getPayments(paySearch)
  payList.value = res.data || []
  payTotal.value = res.total
  payLoading.value = false
}

// 支付渠道 → 中文文案的映射
const channelMap: Record<string, string> = { wechat: '微信支付', alipay: '支付宝', bank: '银行卡' }
// 支付状态 → 中文文案的映射
const payStatusMap: Record<string, string> = { paid: '已支付', refunding: '退款中', refunded: '已退款' }
// 支付状态 → Element Plus 标签类型的映射
const payStatusTag: Record<string, string> = { paid: 'success', refunding: 'warning', refunded: 'info' }

// ── 退款审批 ──
// 退款列表加载状态
const refundLoading = ref(false)
// 退款列表数据
const refundList = ref<RefundItem[]>([])
// 退款总条数（分页用）
const refundTotal = ref(0)
// 退款筛选与分页参数：状态（默认待审核）、页码、每页条数
const refundSearch = reactive({ status: 'pending', page: 1, page_size: 20 })

/**
 * 拉取退款列表（异步）
 * 按当前筛选条件请求分页数据，写入 refundList 与 refundTotal
 */
async function fetchRefunds() {
  refundLoading.value = true
  const res = await getRefunds(refundSearch)
  refundList.value = res.data || []
  refundTotal.value = res.total
  refundLoading.value = false
}

/**
 * 通过退款申请（异步）
 * @param id 退款单 ID
 */
async function handleApprove(id: number) {
  await approveRefund(id)
  ElMessage.success('退款已通过')
  fetchRefunds()
}

/**
 * 驳回退款申请（异步）
 * @param id 退款单 ID
 */
async function handleReject(id: number) {
  await rejectRefund(id)
  ElMessage.success('退款已拒绝')
  fetchRefunds()
}

// 退款状态 → Element Plus 标签类型的映射（待审核黄/通过绿/驳回红）
const refundStatusTag: Record<string, string> = { pending: 'warning', approved: 'success', rejected: 'danger' }
// 退款状态 → 中文文案的映射
const refundStatusText: Record<string, string> = { pending: '待审核', approved: '已通过', rejected: '已驳回' }

// 页面挂载：并行初始化支付流水与退款列表
onMounted(() => { fetchPayments(); fetchRefunds() })
</script>

<template>
  <!-- 页面容器（通用白底卡片样式） -->
  <div class="page-container">
    <!-- Tab 切换：支付流水 / 退款审批 -->
    <el-tabs v-model="activeTab">
      <!-- 支付流水 Tab：按渠道/状态筛选分页展示 -->
      <el-tab-pane label="支付流水" name="payments">
        <!-- 工具栏：渠道与支付状态筛选 -->
        <div class="toolbar">
          <div class="toolbar-left">
            <!-- 支付渠道筛选：微信/支付宝/银行卡 -->
            <el-select v-model="paySearch.channel" placeholder="支付渠道" clearable style="width:130px" @change="fetchPayments">
              <el-option label="微信支付" value="wechat" />
              <el-option label="支付宝" value="alipay" />
              <el-option label="银行卡" value="bank" />
            </el-select>
            <!-- 支付状态筛选：已支付/退款中/已退款 -->
            <el-select v-model="paySearch.status" placeholder="支付状态" clearable style="width:130px" @change="fetchPayments">
              <el-option label="已支付" value="paid" />
              <el-option label="退款中" value="refunding" />
              <el-option label="已退款" value="refunded" />
            </el-select>
          </div>
        </div>

        <!-- 支付流水表格：流水号/订单/金额/渠道/交易号/状态/时间 -->
        <el-table :data="payList" v-loading="payLoading" stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="payment_no" label="流水号" width="180" />
          <el-table-column prop="order_id" label="订单ID" width="90" />
          <!-- 支付金额 -->
          <el-table-column prop="amount" label="金额" width="100">
            <template #default="{ row }">¥{{ row.amount }}</template>
          </el-table-column>
          <!-- 支付渠道中文名 -->
          <el-table-column label="渠道" width="100">
            <template #default="{ row }">{{ channelMap[row.channel] || row.channel }}</template>
          </el-table-column>
          <!-- 第三方交易号（过长时省略号展示） -->
          <el-table-column prop="trade_no" label="交易号" width="200" show-overflow-tooltip />
          <!-- 支付状态标签 -->
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="payStatusTag[row.status]">{{ payStatusMap[row.status] || row.status }}</el-tag>
            </template>
          </el-table-column>
          <!-- 支付时间（格式化去掉 T） -->
          <el-table-column prop="paid_at" label="支付时间" width="170">
            <template #default="{ row }">{{ row.paid_at?.slice(0, 19).replace('T', ' ') }}</template>
          </el-table-column>
        </el-table>

        <!-- 分页器：切换页码触发重新查询 -->
        <el-pagination
          v-model:current-page="paySearch.page" :total="payTotal" :page-size="20"
          layout="total,prev,pager,next" style="margin-top:16px;justify-content:flex-end"
          @change="fetchPayments"
        />
      </el-tab-pane>

      <!-- 退款审批 Tab：对待审核退款执行通过/驳回 -->
      <el-tab-pane label="退款审批" name="refunds">
        <!-- 工具栏：退款状态筛选 -->
        <div class="toolbar">
          <div class="toolbar-left">
            <!-- 状态筛选：待审核/已通过/已驳回 -->
            <el-select v-model="refundSearch.status" placeholder="状态" clearable style="width:130px" @change="fetchRefunds">
              <el-option label="待审核" value="pending" />
              <el-option label="已通过" value="approved" />
              <el-option label="已驳回" value="rejected" />
            </el-select>
          </div>
        </div>

        <!-- 退款列表表格：退款编号/订单/金额/原因/状态/申请时间 -->
        <el-table :data="refundList" v-loading="refundLoading" stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="refund_no" label="退款编号" width="180" />
          <el-table-column prop="order_id" label="订单ID" width="90" />
          <!-- 退款金额 -->
          <el-table-column prop="amount" label="退款金额" width="110">
            <template #default="{ row }">¥{{ row.amount }}</template>
          </el-table-column>
          <!-- 退款原因（过长时省略号展示） -->
          <el-table-column prop="reason" label="退款原因" min-width="160" show-overflow-tooltip />
          <!-- 退款状态标签 -->
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="refundStatusTag[row.status]">{{ refundStatusText[row.status] || row.status }}</el-tag>
            </template>
          </el-table-column>
          <!-- 申请时间（格式化去掉 T） -->
          <el-table-column prop="created_at" label="申请时间" width="170">
            <template #default="{ row }">{{ row.created_at?.slice(0, 19).replace('T', ' ') }}</template>
          </el-table-column>
          <!-- 行操作：待审核时显示通过/驳回按钮，其余显示占位符 -->
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <template v-if="row.status === 'pending'">
                <!-- 通过退款申请 -->
                <el-button text type="success" size="small" @click="handleApprove(row.id)">通过</el-button>
                <!-- 驳回退款申请 -->
                <el-button text type="danger" size="small" @click="handleReject(row.id)">驳回</el-button>
              </template>
              <!-- 已处理（通过/驳回）的退款无操作，展示占位符 -->
              <span v-else style="color:#909399">-</span>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页器：切换页码触发重新查询 -->
        <el-pagination
          v-model:current-page="refundSearch.page" :total="refundTotal" :page-size="20"
          layout="total,prev,pager,next" style="margin-top:16px;justify-content:flex-end"
          @change="fetchRefunds"
        />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>
