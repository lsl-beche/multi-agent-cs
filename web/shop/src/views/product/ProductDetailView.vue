<!--
  ═══════════════════════════════════════════════════════════
  茗韵茶庄商城 · 商品详情页（ProductDetailView.vue）
  ───────────────────────────────────────────────────────────
  职责说明：
    单个商品详情展示与购买操作页（路由 /product/:id），包含：
      1. 左侧：主图 + 缩略图列表（点击切换主图）；
      2. 右侧：面包屑、商品名/描述、价格（当前 SKU 价或商品价）、
         SKU 规格选择（售罄禁用）、数量选择（受库存约束）、
         加入购物车 / 立即购买 / 服务承诺；
      3. 下方：商品评价区（平均分、评价列表、分页加载更多）；
      4. 立即购买：写入 localStorage "shop_buy_now" 后跳转结算页，
         由结算页读取并仅结算该商品；
      5. 页面挂载时加载商品详情与第一页评价。
  ═══════════════════════════════════════════════════════════
-->
<template>
  <div class="shop-container detail-page">
    <!-- 页面主体：加载中显示遮罩 -->
    <div v-loading="loading">
      <!-- 有商品数据时展示详情 -->
      <div v-if="product" class="product-detail">
        <!-- 左侧图片 -->
        <div class="detail-images">
          <!-- 主图：展示当前选中图片（默认第一张），失败用茶碗图标占位 -->
          <div class="main-image">
            <el-image :src="currentImage || product.images?.[0] || ''" fit="contain" class="main-img">
              <template #error>
                <div class="image-placeholder">
                  <TeaIcon name="bowl" class="placeholder-icon" />
                </div>
              </template>
            </el-image>
          </div>
          <!-- 缩略图列表：点击切换主图，当前图高亮 -->
          <div class="thumb-list" v-if="product.images?.length">
            <div
              v-for="(img, idx) in product.images"
              :key="idx"
              class="thumb-item"
              :class="{ active: currentImage === img }"
              @click="currentImage = img"
            >
              <img :src="img" alt="" />
            </div>
          </div>
        </div>

        <!-- 右侧信息 -->
        <div class="detail-info">
          <!-- 面包屑：品牌 / 类目 -->
          <div class="info-breadcrumb">
            <span>茗韵茶庄</span>
            <span class="sep">/</span>
            <span>{{ product.category_name || '全部商品' }}</span>
          </div>
          <!-- 商品名称与描述 -->
          <h1 class="product-title">{{ product.name }}</h1>
          <p class="product-desc-text">{{ product.description }}</p>

          <!-- 价格区：当前售价（SKU 价优先）+ 市场价（售价 x1.3 虚拟划线价） -->
          <div class="price-box">
            <div class="price-row">
              <span class="label">售价</span>
              <span class="current-price">¥{{ selectedSku?.price?.toFixed(2) || product.price?.toFixed(2) }}</span>
            </div>
            <span class="original-price" v-if="product.price">
              市场价 ¥{{ (product.price * 1.3).toFixed(2) }}
            </span>
          </div>

          <!-- SKU 选择 -->
          <!-- 规格列表：点击选择 SKU，售罄项禁用显示"已售罄" -->
          <div v-if="product.skus?.length" class="sku-section">
            <div class="section-label">规格选择</div>
            <div class="sku-list">
              <div
                v-for="sku in product.skus"
                :key="sku.id"
                class="sku-card"
                :class="{ active: selectedSku?.id === sku.id, disabled: sku.stock <= 0 }"
                @click="selectSku(sku)"
              >
                <span class="sku-name">{{ sku.name }}</span>
                <span class="sku-price">¥{{ sku.price?.toFixed(2) }}</span>
                <span class="sku-stock" v-if="sku.stock <= 0">已售罄</span>
              </div>
            </div>
          </div>

          <!-- 数量 -->
          <!-- 数量选择：1 ~ 当前 SKU 库存 -->
          <div class="quantity-section">
            <span class="section-label">数量</span>
            <el-input-number v-model="quantity" :min="1" :max="selectedSku?.stock || 1" size="large" class="qty-input" />
            <span class="stock-text">库存 {{ selectedSku?.stock ?? 0 }} 件</span>
          </div>

          <!-- 操作 -->
          <!-- 加入购物车 / 立即购买：未选 SKU 或售罄时禁用 -->
          <div class="action-buttons">
            <el-button size="large" class="btn-cart" @click="addToCart" :disabled="!selectedSku || selectedSku.stock <= 0">
              <el-icon><ShoppingCart /></el-icon>加入购物车
            </el-button>
            <el-button size="large" class="btn-buy" @click="buyNow" :disabled="!selectedSku || selectedSku.stock <= 0">
              立即购买
            </el-button>
          </div>

          <!-- 服务承诺 -->
          <div class="service-tags">
            <span>🍃 原产地直供</span>
            <span>📦 保鲜包装</span>
            <span>🛡️ 七天退换</span>
            <span>🚚 满99包邮</span>
          </div>
        </div>
      </div>

      <!-- 商品评价 -->
      <div v-if="product" class="reviews-section">
        <!-- 评价头部：标题 + 平均分汇总 -->
        <div class="reviews-header">
          <h2>商品评价</h2>
          <!-- 有评价时展示平均星级/分数/条数 -->
          <div class="reviews-summary" v-if="reviewTotal > 0">
            <span class="avg-stars">{{ starDisplay(avgRating) }}</span>
            <span class="avg-text">{{ avgRating.toFixed(1) }} 分</span>
            <span class="review-count">（{{ reviewTotal }} 条评价）</span>
          </div>
        </div>

        <!-- 评价列表 -->
        <div v-if="reviews.length > 0" class="review-list">
          <div v-for="r in reviews" :key="r.id" class="review-card">
            <div class="review-top">
              <span class="review-stars">{{ starDisplay(r.rating) }}</span>
              <span class="review-date">{{ formatDate(r.created_at) }}</span>
            </div>
            <p class="review-content">{{ r.content }}</p>
            <!-- 商家回复 -->
            <div v-if="r.reply" class="review-reply">
              <span class="reply-label">商家回复：</span>{{ r.reply }}
            </div>
          </div>
        </div>
        <!-- 已加载但无评价 -->
        <div v-else-if="reviewLoaded" class="review-empty">
          <span>暂无评价，成为第一个评价的人吧～</span>
        </div>

        <!-- 加载更多：未到最后一页时展示 -->
        <div v-if="reviewPage < reviewTotalPages" class="load-more-wrap">
          <el-button text class="btn-load-more" :loading="loadingMore" @click="loadMoreReviews">
            加载更多评价
          </el-button>
        </div>
      </div>

      <!-- 商品不存在 -->
      <el-empty v-else description="商品不存在" />
    </div>
  </div>
</template>

<script setup lang="ts">
// ── 依赖引入 ──
import { ref, onMounted, computed } from 'vue' // Vue 响应式/生命周期/计算属性
import { useRoute, useRouter } from 'vue-router' // 路由：读取商品 ID + 跳转结算页
import { getProductDetail, type Product, type Sku } from '@/api/products' // 商品详情 API 与类型
import { getProductReviews } from '@/api/reviews' // 商品评价 API
import { useCartStore } from '@/stores/cart' // 购物车仓库（加入购物车）
import { ElMessage } from 'element-plus' // 消息提示
import { ShoppingCart } from '@element-plus/icons-vue' // 购物车图标
import TeaIcon from '@/components/TeaIcon.vue' // 主题图标（图片失败占位）

// ── 基础状态 ──
const route = useRoute() // 当前路由（读取商品 ID）
const router = useRouter() // 路由实例（立即购买跳转）
const cart = useCartStore() // 购物车仓库

const product = ref<Product | null>(null) // 商品详情数据
const loading = ref(false) // 详情加载中标记
const quantity = ref(1) // 购买数量（默认 1）
const currentImage = ref('') // 当前展示的主图地址（点击缩略图切换）
const selectedSku = ref<Sku | null>(null) // 当前选中的 SKU（规格）

// ── 评价相关 ──
const reviews = ref<any[]>([]) // 已加载的评价列表
const reviewTotal = ref(0) // 评价总数
const reviewPage = ref(1) // 当前评价页码
const reviewLoaded = ref(false) // 评价是否已加载完成（控制空态展示）
const loadingMore = ref(false) // "加载更多"请求中标记
const pageSize = 10 // 评价每页条数（固定 10）

// ── 平均评分（计算属性） ──
// 作用：对已加载评价的评分取平均；无评价时返回 0
const avgRating = computed(() => {
  if (reviewTotal.value === 0) return 0
  const sum = reviews.value.reduce((acc, r) => acc + r.rating, 0)
  return sum / reviews.value.length || 0
})

// ── 评价总页数（计算属性） ──
// 作用：根据评价总数与每页条数计算总页数，用于"加载更多"显隐判断
const reviewTotalPages = computed(() => Math.ceil(reviewTotal.value / pageSize))

// ── 星级文案 ──
// 作用：将评分转为"★★★★☆"形式的星级字符串
// 参数：rating —— 评分（1~5）；返回值：星级字符串
function starDisplay(rating: number) {
  return '★'.repeat(rating) + '☆'.repeat(5 - rating)
}

// ── 日期格式化 ──
// 作用：截取日期字符串前 10 位（YYYY-MM-DD），空值返回空串
// 参数：dateStr —— 日期字符串或 null；返回值：格式化后的日期
function formatDate(dateStr: string | null) {
  if (!dateStr) return ''
  return dateStr.slice(0, 10)
}

// ── 加载第一页评价 ──
// 作用：请求商品第一页评价并写入列表/总数/页码，同时标记已加载
// 参数：productId —— 商品 ID；返回值：Promise<void>
async function loadReviews(productId: number) {
  try {
    const res = await getProductReviews(productId, 1, pageSize) // 请求第一页评价
    const d = res.data.data
    reviews.value = d.items || []
    reviewTotal.value = d.total || 0
    reviewPage.value = 1
    reviewLoaded.value = true
  } catch { reviewLoaded.value = true } // 失败也标记已加载，展示空态
}

// ── 加载更多评价 ──
// 作用：请求下一页评价并追加到列表尾部，更新页码与总数
// 参数：无；返回值：Promise<void>
async function loadMoreReviews() {
  loadingMore.value = true
  try {
    const nextPage = reviewPage.value + 1 // 下一页页码
    const res = await getProductReviews(product.value!.id, nextPage, pageSize) // 请求下一页
    const d = res.data.data
    reviews.value = reviews.value.concat(d.items || []) // 追加到已有列表
    reviewTotal.value = d.total || 0
    reviewPage.value = nextPage // 更新当前页码
    // recalc total
    reviewTotal.value = d.total || reviewTotal.value // 兜底：以服务端 total 为准
  } catch { /* ignore */ } finally { loadingMore.value = false }
}

// ── 选择 SKU 规格 ──
// 作用：选中某规格并重置数量为 1；售罄规格点击无效
// 参数：sku —— 被点击的 SKU 对象；返回值：无
function selectSku(sku: Sku) {
  if (sku.stock <= 0) return // 售罄不可选
  selectedSku.value = sku
  quantity.value = 1 // 切换规格后重置数量
}

// ── 加入购物车 ──
// 作用：将当前选中 SKU 与数量加入购物车并提示
// 参数：无；返回值：Promise<void>
async function addToCart() {
  if (!selectedSku.value) return // 未选规格直接返回
  await cart.addItem(selectedSku.value.id, quantity.value) // 调用购物车仓库加入
  ElMessage.success('已加入购物车')
}

// ── 立即购买 ──
// 作用：将所选 SKU 与数量写入 localStorage "shop_buy_now"，
//       再跳转结算页（由结算页读取该标记并仅结算此商品）
// 参数：无；返回值：无
function buyNow() {
  if (!selectedSku.value) return
  localStorage.setItem('shop_buy_now', JSON.stringify({ sku_id: selectedSku.value.id, quantity: quantity.value }))
  router.push('/checkout')
}

// ── 页面挂载后加载商品详情 ──
// 作用：按路由参数加载商品详情；默认选中第一个有库存的 SKU；
//       默认展示第一张图片；同时加载第一页评价
onMounted(async () => {
  loading.value = true
  try {
    const id = Number(route.params.id) // 从路由取商品 ID
    const res = await getProductDetail(id) // 请求商品详情
    product.value = res.data.data
    if (product.value?.skus?.length) {
      const f = product.value.skus.find((s) => s.stock > 0) // 默认选第一个有货的规格
      if (f) selectedSku.value = f
    }
    if (product.value?.images?.length) currentImage.value = product.value.images[0] // 默认主图取第一张
    if (product.value?.id) loadReviews(product.value.id) // 加载第一页评价
  } catch { product.value = null } finally { loading.value = false }
})
</script>

<style scoped>
/* ── 页面容器 ── */
.detail-page { padding: 30px 20px; }

/* ── 详情主体：左右两栏（图片 / 信息），白底卡片 ── */
.product-detail {
  display: flex;
  gap: 40px;
  background: #fff;
  padding: 32px;
  border-radius: 16px;
  box-shadow: 0 2px 16px rgba(61, 50, 39, 0.06);
}

/* 移动端：改为纵向单栏 */
@media (max-width: 768px) { .product-detail { flex-direction: column; } }

/* ── Left: Images ── */
/* 左栏图片区：固定宽度 */
.detail-images { width: 460px; flex-shrink: 0; }

/* 主图容器：正方形区域，浅米底 */
.main-image {
  width: 100%;
  height: 460px;
  border-radius: 12px;
  overflow: hidden;
  background: #faf6ef;
  border: 1px solid #e6ddca;
}

.main-img { width: 100%; height: 100%; }

/* 图片加载失败占位 */
.image-placeholder {
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  background: #f2ead9;
}

.placeholder-icon { font-size: 64px; }

/* 缩略图列表：横向排列 */
.thumb-list { display: flex; gap: 10px; margin-top: 14px; }

/* 缩略图：选中时茶青边框 */
.thumb-item {
  width: 68px; height: 68px;
  border: 2px solid transparent;
  border-radius: 8px; overflow: hidden; cursor: pointer;
  transition: border-color 0.2s;
}

.thumb-item.active { border-color: #3f5d4a; }

.thumb-item img { width: 100%; height: 100%; object-fit: cover; }

/* ── Right: Info ── */
/* 右侧信息区：弹性撑开 */
.detail-info { flex: 1; }

/* 面包屑：品牌 / 类目 */
.info-breadcrumb { font-size: 13px; color: #6b6257; margin-bottom: 12px; }
.info-breadcrumb .sep { margin: 0 6px; color: #d9c6a3; }

/* 商品名：大号加粗 */
.product-title { font-size: 26px; font-weight: 700; color: #2c2a26; margin-bottom: 10px; letter-spacing: 1px; }

/* 商品描述 */
.product-desc-text { color: #6b6257; font-size: 14px; margin-bottom: 24px; line-height: 1.6; }

/* 价格区：浅金渐变底卡片 */
.price-box {
  background: linear-gradient(135deg, #fdf8f0, #fef5e7);
  padding: 20px 24px;
  border-radius: 12px;
  margin-bottom: 24px;
  border: 1px solid #f0e1c8;
}

/* 售价行：标签 + 大号朱砂价格 */
.price-row { display: flex; align-items: baseline; gap: 12px; }
.price-row .label { font-size: 14px; color: #6b6257; }

.current-price { font-size: 32px; color: #b3453a; font-weight: 700; letter-spacing: 1px; }

/* 市场价：划线灰色 */
.original-price { font-size: 14px; color: #a3967f; text-decoration: line-through; margin-top: 6px; display: block; }

/* ── SKU 选择 ── */
.sku-section { margin-bottom: 24px; }
.section-label { font-size: 14px; color: #2c2a26; margin-bottom: 10px; font-weight: 500; }

.sku-list { display: flex; gap: 12px; flex-wrap: wrap; }

/* 规格卡：描边可点，选中态金色边框 + 右上角对勾，售罄置灰禁用 */
.sku-card {
  min-width: 108px;
  padding: 12px 16px;
  border: 2px solid var(--line);
  border-radius: 10px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
  transition: all 0.2s;
  background: var(--card);
  position: relative;
}

.sku-card:hover:not(.disabled) {
  border-color: var(--gold);
  transform: translateY(-2px);
}

/* 选中态：金色边框 + 浅茶青底 */
.sku-card.active {
  border-color: var(--gold);
  background: var(--tea-soft);
  box-shadow: var(--shadow-sm);
}

/* 选中态右上角对勾 */
.sku-card.active::after {
  content: '✓';
  position: absolute;
  top: 6px;
  right: 9px;
  color: var(--gold-deep);
  font-weight: 700;
  font-size: 13px;
}

/* 规格名称/价格/库存文案 */
.sku-name {
  font-size: 14px;
  color: var(--ink);
  font-weight: 500;
}

.sku-price {
  font-size: 16px;
  color: var(--cinnabar);
  font-weight: 700;
  font-family: var(--font-serif);
}

.sku-stock {
  font-size: 11px;
  color: var(--ink-soft);
}

/* 售罄：置灰不可点 */
.sku-card.disabled {
  cursor: not-allowed;
  background: var(--paper);
  opacity: 0.65;
}

/* ── 数量选择 ── */
.quantity-section { display: flex; align-items: center; gap: 16px; margin-bottom: 28px; }

/* 数量输入框加减按钮：浅米底茶青字 */
.qty-input :deep(.el-input-number__decrease),
.qty-input :deep(.el-input-number__increase) {
  background: #faf6ef;
  color: #3f5d4a;
}

.stock-text { font-size: 13px; color: #6b6257; }

/* ── 操作按钮 ── */
.action-buttons { display: flex; gap: 14px; margin-bottom: 24px; }

/* 加入购物车：白底茶青描边 */
.btn-cart {
  flex: 1;
  background: #fff !important;
  border: 2px solid #3f5d4a !important;
  color: #3f5d4a !important;
  font-weight: 600 !important;
  font-size: 16px !important;
  height: 50px !important;
  border-radius: 12px !important;
}

.btn-cart:hover { background: #e8efe9 !important; }

/* 立即购买：朱砂底白字 */
.btn-buy {
  flex: 1;
  background: #b3453a !important;
  border-color: #b3453a !important;
  color: #fff !important;
  font-weight: 600 !important;
  font-size: 16px !important;
  height: 50px !important;
  border-radius: 12px !important;
}

.btn-buy:hover { background: #a8453e !important; }

/* 服务承诺标签：顶部描边分隔 */
.service-tags {
  display: flex; gap: 20px;
  padding-top: 20px;
  border-top: 1px solid #f2ead9;
  font-size: 13px;
  color: #6b6257;
}

/* ── 评价区域 ── */
.reviews-section {
  margin-top: 20px;
  background: #fff;
  border-radius: 16px;
  padding: 28px 32px;
  box-shadow: 0 2px 16px rgba(61, 50, 39, 0.06);
}

/* 评价头部：标题 + 汇总 */
.reviews-header {
  display: flex;
  align-items: baseline;
  gap: 16px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f2ead9;
}

.reviews-header h2 {
  font-size: 20px;
  color: #2c2a26;
  font-weight: 700;
  margin: 0;
}

/* 平均分汇总：星级 + 分数 + 条数 */
.reviews-summary {
  display: flex;
  align-items: center;
  gap: 8px;
}

.avg-stars {
  color: #e6a817;
  font-size: 18px;
  letter-spacing: 2px;
}

.avg-text {
  font-size: 16px;
  font-weight: 600;
  color: #b3453a;
}

.review-count {
  font-size: 13px;
  color: #6b6257;
}

/* 评价列表 */
.review-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 单条评价卡：浅米底 */
.review-card {
  padding: 16px;
  background: #faf7f2;
  border-radius: 10px;
  border: 1px solid #f2ead9;
}

/* 评价头部：星级 + 日期 */
.review-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.review-stars {
  color: #e6a817;
  font-size: 15px;
  letter-spacing: 2px;
}

.review-date {
  font-size: 12px;
  color: #a3967f;
}

/* 评价正文 */
.review-content {
  font-size: 14px;
  color: #5a4a3a;
  line-height: 1.7;
  margin: 0;
}

/* 商家回复：浅绿底块 */
.review-reply {
  margin-top: 12px;
  padding: 10px 14px;
  background: #e8efe9;
  border-radius: 8px;
  font-size: 13px;
  color: #3f5d4a;
  border: 1px solid #d4e5d8;
}

.reply-label {
  font-weight: 600;
}

/* 无评价空态 */
.review-empty {
  text-align: center;
  padding: 32px;
  color: #a3967f;
  font-size: 14px;
}

/* 加载更多按钮区 */
.load-more-wrap {
  text-align: center;
  margin-top: 20px;
}

.btn-load-more {
  color: #3f5d4a !important;
  font-size: 14px;
}
</style>
