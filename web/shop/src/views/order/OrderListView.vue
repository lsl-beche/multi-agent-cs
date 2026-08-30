<!--
  ═══════════════════════════════════════════════════════════
  茗韵茶庄商城 · 我的订单列表页（OrderListView.vue）
  ───────────────────────────────────────────────────────────
  职责说明：
    分页展示当前用户的订单列表，支持：
      1. 顶部状态 Tab 筛选：全部 / 待付款 / 待发货 / 待收货 / 已完成；
      2. 订单卡片展示订单号、下单时间、状态标签与商品摘要；
      3. 按状态提供操作按钮：
         - 待付款：去付款、取消订单（handleCancel，带二次确认）；
         - 待收货：确认收货（handleConfirm，带二次确认）；
         - 所有状态均可查看订单详情；
      4. 底部 el-pagination 分页（切换页码触发 fetchData）；
      5. 无订单时展示空状态并提供"去购物"入口。
  ═══════════════════════════════════════════════════════════
-->
<template>
  <div class="shop-container orders-page">
    <h2 class="page-title">我的订单</h2>
    <!-- 状态筛选：单选按钮组，切换时重新拉取数据 -->
    <div class="order-tabs">
      <el-radio-group v-model="statusFilter" @change="fetchData" size="large">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="pending">待付款</el-radio-button>
        <el-radio-button value="confirmed">待发货</el-radio-button>
        <el-radio-button value="shipped">待收货</el-radio-button>
        <el-radio-button value="completed">已完成</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 订单列表：加载中显示遮罩 -->
    <div v-loading="loading">
      <!-- 有订单数据时渲染订单卡片 -->
      <template v-if="orders.length > 0">
        <div v-for="order in orders" :key="order.id" class="order-card">
          <!-- 卡片头部：订单号 + 下单时间 + 状态标签 -->
          <div class="order-header">
            <span class="order-no">订单号：{{ order.order_no }}</span>
            <span class="order-time">{{ order.created_at }}</span>
            <el-tag :type="statusType(order.status)" size="small">{{ statusLabel(order.status) }}</el-tag>
          </div>
          <!-- 订单商品摘要列表 -->
          <div class="order-items">
            <div v-for="item in order.items" :key="item.id" class="order-item">
              <!-- 商品图：加载失败用 emoji 占位 -->
              <div class="oi-img-wrap">
                <el-image :src="item.image || ''" fit="cover" class="oi-img">
                  <template #error><span style="font-size:22px">🍵</span></template>
                </el-image>
              </div>
              <div class="oi-info">
                <p class="oi-name">{{ item.product_name }}</p>
                <p class="oi-sku">{{ item.sku_name }}</p>
              </div>
              <!-- 单价与数量 -->
              <div class="oi-right">
                <span class="oi-price">¥{{ item.price?.toFixed(2) }}</span>
                <span class="oi-qty">x{{ item.quantity }}</span>
              </div>
            </div>
          </div>
          <!-- 卡片底部：件数/合计 + 状态相关操作按钮 -->
          <div class="order-footer">
            <span>共 {{ order.items?.length }} 件，合计 <b>¥{{ order.total_amount?.toFixed(2) }}</b></span>
            <div class="order-actions">
              <!-- 待付款：去付款（跳转支付页） -->
              <el-button v-if="order.status === 'pending'" type="primary" size="small" round>去付款</el-button>
              <!-- 待付款：取消订单（带确认框） -->
              <el-button v-if="order.status === 'pending'" size="small" round @click="handleCancel(order.id)">取消</el-button>
              <!-- 待收货：确认收货（带确认框） -->
              <el-button v-if="order.status === 'shipped'" type="success" size="small" round @click="handleConfirm(order.id)">确认收货</el-button>
              <!-- 所有状态：查看详情 -->
              <el-button size="small" round @click="$router.push(`/order/${order.id}`)">订单详情</el-button>
            </div>
          </div>
        </div>
        <!-- 分页组件：切换页码触发重新拉取 -->
        <div class="pagination-wrap" v-if="total > 0">
          <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" background @current-change="fetchData" />
        </div>
      </template>
      <!-- 空状态：无订单 -->
      <el-empty v-else description="暂无订单">
        <el-button type="primary" @click="$router.push('/products')">去购物</el-button>
      </el-empty>
    </div>
  </div>
</template>

<script setup lang="ts">
// ── 依赖引入 ──
import { ref, onMounted } from 'vue' // Vue 响应式与生命周期
import { getOrders, cancelOrder, confirmOrder, type Order } from '@/api/orders' // 订单相关 API 与类型
import { ElMessage, ElMessageBox } from 'element-plus' // 消息提示与确认框

// ── 状态定义 ──
const orders = ref<Order[]>([]) // 当前页订单列表
const loading = ref(false) // 加载中标记
const page = ref(1) // 当前页码
const pageSize = 10 // 每页条数（固定 10）
const total = ref(0) // 订单总数（驱动分页）
const statusFilter = ref('') // 状态筛选条件（空串表示全部）

// ── 订单状态文案映射 ──
// 作用：将订单状态码转为中文文案；未匹配时原样返回
const statusLabel = (s: string) =>
  ({ pending: '待付款', confirmed: '待发货', shipped: '待收货', completed: '已完成', cancelled: '已取消' } as Record<string, string>)[s] || s

// ── 订单状态标签类型映射 ──
// 作用：将订单状态码映射为 el-tag 的 type（warning 待付款 / success 待收货 / info 已完成 / danger 已取消）
const statusType = (s: string) =>
  ({ pending: 'warning', confirmed: '', shipped: 'success', completed: 'info', cancelled: 'danger' } as Record<string, string>)[s] || ''

// ── 拉取订单列表 ──
// 作用：按当前页码与状态筛选请求订单数据，成功写入列表与总数
// 参数：无；返回值：Promise<void>
async function fetchData() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize } // 基础分页参数
    if (statusFilter.value) params.status = statusFilter.value // 有筛选条件时附带状态参数
    const res = await getOrders(params) // 请求订单列表
    orders.value = res.data.data?.items || []
    total.value = res.data.data?.total || 0
  } catch { orders.value = [] } finally { loading.value = false } // 失败置空列表；最终复位 loading
}

// ── 取消订单 ──
// 作用：弹出二次确认框，确认后调用 cancelOrder 取消订单并刷新列表
// 参数：id —— 订单 ID；返回值：Promise<void>
async function handleCancel(id: number) {
  await ElMessageBox.confirm('确定要取消该订单吗？', '提示', { type: 'warning' }) // 二次确认（取消则抛错中止）
  await cancelOrder(id) // 调用取消接口
  ElMessage.success('订单已取消')
  fetchData() // 刷新列表
}

// ── 确认收货 ──
// 作用：弹出二次确认框，确认后调用 confirmOrder 完成收货并刷新列表
// 参数：id —— 订单 ID；返回值：Promise<void>
async function handleConfirm(id: number) {
  await ElMessageBox.confirm('确认已收到商品？', '提示', { type: 'info' }) // 二次确认
  await confirmOrder(id) // 调用确认收货接口
  ElMessage.success('已确认收货')
  fetchData() // 刷新列表
}

// ── 页面挂载后拉取首屏数据 ──
onMounted(fetchData)
</script>

<style scoped>
/* ── 页面容器 ── */
.orders-page { padding: 30px 20px 50px; }

/* ── 状态筛选区 ── */
.order-tabs { margin-bottom: 20px; }

/* ── 订单卡片 ── */
.order-card {
  background: #fff;
  border-radius: 12px;
  margin-bottom: 18px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(61, 50, 39, 0.05);
}

/* 卡片头部：订单号 + 时间 + 状态标签，浅米色底 */
.order-header {
  display: flex; align-items: center; gap: 16px;
  padding: 14px 20px; background: #faf7f2;
  font-size: 13px; color: #6b6257;
  border-bottom: 1px solid #e6ddca;
}

.order-no { font-weight: 500; color: #2c2a26; }
.order-time { color: #a3967f; }

/* ── 商品摘要行 ── */
.oi-img-wrap { width: 64px; height: 64px; border-radius: 8px; overflow: hidden; background: #faf6ef; flex-shrink: 0; display: flex; align-items: center; justify-content: center; }
.oi-img { width: 100%; height: 100%; }

.order-item { display: flex; align-items: center; gap: 14px; padding: 14px 20px; border-bottom: 1px solid #f5f0e8; }
.oi-info { flex: 1; }
.oi-name { font-size: 14px; color: #2c2a26; margin-bottom: 2px; }
.oi-sku { font-size: 12px; color: #6b6257; }
.oi-right { text-align: right; }
.oi-price { color: #b3453a; font-weight: 600; display: block; }
.oi-qty { color: #6b6257; font-size: 12px; }

/* ── 卡片底部：汇总 + 操作按钮 ── */
.order-footer {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 20px; font-size: 14px; color: #6b6257;
}
/* 合计金额：朱砂加粗 */
.order-footer b { color: #b3453a; font-size: 16px; margin-left: 4px; }
.order-actions { display: flex; gap: 8px; }

/* ── 分页区：居中 ── */
.pagination-wrap { display: flex; justify-content: center; margin-top: 30px; }
</style>
