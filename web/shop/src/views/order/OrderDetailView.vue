<!--
  ═══════════════════════════════════════════════════════════
  茗韵茶庄商城 · 订单详情页（OrderDetailView.vue）
  ───────────────────────────────────────────────────────────
  职责说明：
    展示单个订单的完整信息（路由 /order/:id），包含：
      1. 返回订单列表入口 + 订单状态与订单号（状态徽标）；
      2. 收货信息（收货人/电话/详细地址）；
      3. 商品信息列表（图片/名称/SKU/单价与数量）；
      4. 金额汇总（商品总额/运费/实付金额）；
      5. 订单时间线（创建/付款/发货/完成时间，按字段存在与否展示）；
      6. 已完成订单提供"评价商品"入口，弹窗内为每件商品打分、
         填写评价内容并支持匿名评价（submitReview 逐件提交）。
  ═══════════════════════════════════════════════════════════
-->
<template>
  <div class="shop-container order-detail-page">
    <!-- 返回订单列表 -->
    <div class="back-link">
      <el-button text @click="$router.push('/orders')"><el-icon><ArrowLeft /></el-icon> 返回订单列表</el-button>
    </div>
    <!-- 页面主体：加载中显示遮罩 -->
    <div v-loading="loading">
      <!-- 有订单数据时展示详情 -->
      <template v-if="order">
        <!-- 订单状态头部：状态图标 + 状态文案 + 订单号 -->
        <div class="status-header">
          <div class="status-badge">
            <span class="status-icon" :class="'status-' + order.status">📋</span>
            <div>
              <h2>{{ statusLabel(order.status) }}</h2>
              <p class="order-no">订单号：{{ order.order_no }}</p>
            </div>
          </div>
        </div>

        <!-- 收货信息（有地址数据时展示） -->
        <div class="detail-section" v-if="order.address">
          <h3>📍 收货信息</h3>
          <div class="addr-block">
            <p class="addr-name">{{ order.address.receiver_name }} <span class="addr-phone">{{ order.address.receiver_phone }}</span></p>
            <p class="addr-text">{{ order.address.province }}{{ order.address.city }}{{ order.address.district }} {{ order.address.detail }}</p>
          </div>
        </div>

        <!-- 商品信息列表 -->
        <div class="detail-section">
          <h3>📦 商品信息</h3>
          <div v-for="item in order.items" :key="item.id" class="detail-item">
            <!-- 商品图：加载失败时用 emoji 占位 -->
            <div class="di-img">
              <el-image :src="item.image || ''" fit="cover" class="di-img-inner">
                <template #error><span style="font-size:24px">🍵</span></template>
              </el-image>
            </div>
            <div class="di-info">
              <p class="di-name">{{ item.product_name }}</p>
              <p class="di-sku">{{ item.sku_name }}</p>
            </div>
            <!-- 单价 x 数量 -->
            <span class="di-price">¥{{ item.price?.toFixed(2) }} x{{ item.quantity }}</span>
          </div>
        </div>

        <!-- 金额汇总 -->
        <div class="detail-section total-section">
          <div class="total-row"><span>商品总额</span><b>¥{{ order.total_amount?.toFixed(2) }}</b></div>
          <div class="total-row"><span>运费</span><b class="free">免运费</b></div>
          <div class="total-row grand"><span>实付金额</span><b>¥{{ order.total_amount?.toFixed(2) }}</b></div>
        </div>

        <!-- 订单时间线 -->
        <div class="detail-section">
          <h3>⏱ 时间线</h3>
          <div class="timeline">
            <div class="tl-item"><span class="tl-dot"></span>创建时间：{{ order.created_at }}</div>
            <div class="tl-item" v-if="order.paid_at"><span class="tl-dot"></span>付款时间：{{ order.paid_at }}</div>
            <div class="tl-item" v-if="order.shipped_at"><span class="tl-dot"></span>发货时间：{{ order.shipped_at }}</div>
            <div class="tl-item" v-if="order.finished_at"><span class="tl-dot done"></span>完成时间：{{ order.finished_at }}</div>
          </div>
        </div>

        <!-- 评价按钮 -->
        <!-- 仅已完成订单展示"评价商品"入口 -->
        <div v-if="order.status === 'completed'" class="review-action">
          <el-button type="primary" class="btn-review" @click="showReviewDialog = true">
            <el-icon><EditPen /></el-icon> 评价商品
          </el-button>
        </div>
      </template>

      <!-- 评价弹窗 -->
      <el-dialog v-model="showReviewDialog" title="商品评价" width="480px" destroy-on-close>
        <div class="review-dialog">
          <!-- 逐件商品：名称 + 星级选择 -->
          <div v-for="item in order?.items" :key="item.id" class="review-product">
            <div class="rp-info">
              <span class="rp-name">{{ item.product_name }}</span>
              <span class="rp-sku">{{ item.sku_name }}</span>
            </div>
            <!-- 星级评分：点击 ★ 设置该商品评分 -->
            <div class="rp-rating">
              <span
                v-for="s in 5" :key="s"
                class="star-btn"
                :class="{ active: reviewSelections[item.product_id]?.rating >= s }"
                @click="setRating(item.product_id, s)"
              >★</span>
            </div>
          </div>

          <!-- 评价内容输入区 -->
          <div class="review-content-wrap">
            <el-input
              v-model="reviewContent"
              type="textarea"
              :rows="4"
              placeholder="分享您的品茶体验吧～"
              maxlength="500"
              show-word-limit
            />
          </div>

          <!-- 匿名评价开关 -->
          <el-checkbox v-model="isAnonymous" class="anon-check">匿名评价</el-checkbox>
        </div>
        <!-- 弹窗底部操作 -->
        <template #footer>
          <el-button @click="showReviewDialog = false">取消</el-button>
          <el-button type="primary" :loading="submittingReview" @click="handleSubmitReview">提交评价</el-button>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<script setup lang="ts">
// ── 依赖引入 ──
import { ref, reactive, onMounted } from 'vue' // Vue 响应式（ref/reactive）与生命周期
import { useRoute } from 'vue-router' // 路由：读取订单 ID
import { getOrderDetail, type Order } from '@/api/orders' // 订单详情 API 与类型
import { submitReview } from '@/api/reviews' // 提交评价 API
import { ArrowLeft, EditPen } from '@element-plus/icons-vue' // 返回/评价图标
import { ElMessage } from 'element-plus' // 消息提示

// ── 基础状态 ──
const route = useRoute() // 当前路由
const order = ref<Order | null>(null) // 订单详情数据（未加载时为 null）
const loading = ref(false) // 详情加载中标记

// ── 订单状态文案映射 ──
// 作用：将订单状态码转为中文文案；未匹配时原样返回
const statusLabel = (s: string) =>
  ({ pending: '待付款', confirmed: '待发货', shipped: '待收货', completed: '已完成', cancelled: '已取消' } as any)[s] || s

// ── 评价弹窗 ──
const showReviewDialog = ref(false) // 评价弹窗显隐
const reviewContent = ref('') // 评价内容（所有商品共用一份文案）
const isAnonymous = ref(false) // 是否匿名评价
const submittingReview = ref(false) // 评价提交中标记
// 各商品的评分记录：key 为商品 ID，value 为 { rating }
const reviewSelections = reactive<Record<number, { rating: number }>>({})

// ── 设置商品评分 ──
// 作用：记录某商品被点击的星级数
// 参数：productId —— 商品 ID；rating —— 星级（1~5）；返回值：无
function setRating(productId: number, rating: number) {
  reviewSelections[productId] = { rating }
}

// ── 提交评价 ──
// 作用：校验至少一件商品已评分，随后逐件调用 submitReview 提交评价
//       （订单 ID/商品 ID/评分/内容/是否匿名），成功后关闭弹窗并重置表单
// 参数：无；返回值：Promise<void>
async function handleSubmitReview() {
  if (!order.value) return // 无订单数据直接返回
  
  // 过滤出已评分（rating > 0）的商品
  const items = order.value.items.filter(
    (item) => reviewSelections[item.product_id]?.rating > 0
  )
  if (items.length === 0) { // 未评任何商品则提示
    ElMessage.warning('请至少为一件商品评分')
    return
  }

  submittingReview.value = true // 进入提交中状态
  try {
    // 逐件提交评价（每件商品独立请求）
    for (const item of items) {
      await submitReview({
        order_id: order.value.id,
        product_id: item.product_id,
        rating: reviewSelections[item.product_id].rating,
        content: reviewContent.value,
        is_anonymous: isAnonymous.value,
      })
    }
    ElMessage.success('评价提交成功')
    showReviewDialog.value = false // 关闭弹窗
    reviewContent.value = '' // 清空内容
    isAnonymous.value = false // 复位匿名开关
  } catch { /* error handled by interceptor */ } finally {
    submittingReview.value = false // 复位提交中状态
  }
}

// ── 页面挂载后拉取订单详情 ──
// 作用：按路由参数 id 请求订单详情，失败时订单置空
onMounted(async () => {
  loading.value = true
  try {
    const id = Number(route.params.id) // 从路由取订单 ID
    const res = await getOrderDetail(id) // 请求订单详情
    order.value = res.data.data
  } catch { order.value = null } finally { loading.value = false }
})
</script>

<style scoped>
/* ── 页面容器与返回入口 ── */
.order-detail-page { padding: 30px 20px 50px; }
.back-link { margin-bottom: 18px; }

/* ── 订单状态头部：暖白渐变卡 ── */
.status-header {
  background: linear-gradient(135deg, #fff, #faf7f2);
  border: 1px solid #e6ddca;
  padding: 24px;
  border-radius: 12px;
  margin-bottom: 16px;
}

/* 状态徽标区：图标 + 文案 + 订单号 */
.status-badge { display: flex; align-items: center; gap: 16px; }
.status-badge h2 { font-size: 22px; color: #2c2a26; }
.order-no { font-size: 13px; color: #6b6257; margin-top: 4px; }

/* ── 详情区块卡片 ── */
.detail-section {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 14px;
  box-shadow: 0 2px 12px rgba(61, 50, 39, 0.04);
}

.detail-section h3 { font-size: 16px; color: #2c2a26; margin-bottom: 14px; }

/* 收货信息块：浅米色底圆角 */
.addr-block { padding: 12px; background: #faf7f2; border-radius: 8px; }
.addr-name { font-weight: 600; font-size: 15px; color: #2c2a26; margin-bottom: 4px; }
.addr-phone { font-weight: 400; color: #6b6257; margin-left: 10px; }
.addr-text { color: #6b6257; font-size: 13px; }

/* 商品行：图 + 信息 + 价格 */
.di-img { width: 64px; height: 64px; border-radius: 8px; overflow: hidden; background: #faf6ef; flex-shrink: 0; display: flex; align-items: center; justify-content: center; }
.di-img-inner { width: 100%; height: 100%; }

.detail-item { display: flex; align-items: center; gap: 14px; padding: 12px 0; border-bottom: 1px solid #f5f0e8; }
.di-info { flex: 1; }
.di-name { font-size: 14px; color: #2c2a26; }
.di-sku { font-size: 12px; color: #6b6257; }
.di-price { color: #b3453a; font-weight: 600; }

/* 金额汇总区：右对齐 */
.total-section { text-align: right; font-size: 14px; }
.total-row { display: flex; justify-content: flex-end; gap: 20px; margin-bottom: 6px; color: #6b6257; }
.total-row b { color: #2c2a26; }
.total-row .free { color: #3f5d4a; }
/* 实付金额行：顶部虚线分隔，金额朱砂大字 */
.total-row.grand { font-size: 16px; margin-top: 10px; padding-top: 10px; border-top: 1px solid #e6ddca; }
.total-row.grand b { color: #b3453a; font-size: 22px; }

/* 时间线：圆点 + 文字列表 */
.timeline { padding-left: 8px; }
.tl-item { font-size: 14px; color: #6b6257; padding: 8px 0; display: flex; align-items: center; gap: 10px; }
/* 圆点：默认金色，完成节点为茶青 */
.tl-dot { width: 8px; height: 8px; border-radius: 50%; background: #d9c6a3; flex-shrink: 0; }
.tl-dot.done { background: #3f5d4a; }

/* ── 评价按钮 ── */
/* 已完成订单的评价入口：居中展示 */
.review-action {
  text-align: center;
  padding: 20px 0;
}

.btn-review {
  background: #3f5d4a !important;
  border-color: #3f5d4a !important;
  font-size: 15px !important;
  border-radius: 10px !important;
  padding: 12px 32px !important;
}

.btn-review:hover {
  background: #3d6b4a !important;
}

/* ── 评价弹窗 ── */
/* 每个商品的评分行：名称 + 星级 */
.review-dialog .review-product {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f2ead9;
}

.rp-info { flex: 1; }
.rp-name { font-size: 14px; color: #2c2a26; }
.rp-sku { font-size: 12px; color: #6b6257; margin-left: 8px; }

/* 星级按钮：默认灰色，选中/悬停变金色 */
.rp-rating { display: flex; gap: 4px; }
.star-btn {
  font-size: 22px;
  color: #d4cdc0;
  cursor: pointer;
  transition: color 0.15s;
}
.star-btn.active { color: #e6a817; }
.star-btn:hover { color: #e6a817; }

/* 评价内容输入区 */
.review-content-wrap { margin-top: 16px; }

/* 匿名评价开关 */
.anon-check { margin-top: 14px; }
</style>
