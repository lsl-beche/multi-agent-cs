<!--
  ═══════════════════════════════════════════════════════════
  茗韵茶庄商城 · 购物车页（CartView.vue）
  ───────────────────────────────────────────────────────────
  职责说明：
    展示当前用户的购物车商品列表，支持：
      1. 勾选/取消勾选单个商品（toggleSelectItem）与全选/取消全选（toggleSelectAll）；
      2. 修改商品数量（updateItem，受库存上下限约束）；
      3. 删除商品（removeItem）；
      4. 底部实时汇总：已选件数（totalCount）与合计金额（totalAmount）；
      5. 点击"去结算"跳转确认订单页 /checkout；
      6. 购物车为空时展示空状态组件并提供"去逛逛"入口。
    页面挂载时拉取购物车数据（cart.fetchCart()）。
  ═══════════════════════════════════════════════════════════
-->
<template>
  <div class="shop-container cart-page">
    <h2 class="page-title">购物车</h2>
    <!-- 购物车主体：加载期间显示 v-loading 遮罩 -->
    <div v-loading="cart.loading">
      <!-- 有商品时展示购物车表格 -->
      <template v-if="cart.items.length > 0">
        <div class="cart-table">
          <!-- 表头：全选 + 各列标题 -->
          <div class="cart-header">
            <el-checkbox v-model="allSelected" @change="onSelectAll" />
            <span class="col-name">商品</span>
            <span class="col-price">单价</span>
            <span class="col-qty">数量</span>
            <span class="col-subtotal">小计</span>
            <span class="col-action">操作</span>
          </div>
          <!-- 商品行列表 -->
          <div class="cart-body">
            <div v-for="item in cart.items" :key="item.id" class="cart-item">
              <!-- 单品勾选：切换选中状态 -->
              <el-checkbox v-model="item.selected" @change="(v: boolean) => cart.toggleSelectItem(item.id, v)" />
              <!-- 商品信息：图片 + 名称 + SKU -->
              <div class="item-product">
                <div class="item-image">
                  <!-- 商品图：加载失败时用 TeaIcon 茶碗占位 -->
                  <el-image :src="item.image || ''" fit="cover" class="product-img">
                    <template #error><TeaIcon name="bowl" class="img-fallback" /></template>
                  </el-image>
                </div>
                <div class="item-info">
                  <p class="item-name">{{ item.product_name }}</p>
                  <p class="item-sku">{{ item.sku_name }}</p>
                </div>
              </div>
              <!-- 单价 -->
              <span class="col-price">¥{{ item.price?.toFixed(2) }}</span>
              <!-- 数量调整：1 ~ 库存，变更后调用 updateItem 同步到后端 -->
              <div class="col-qty">
                <el-input-number v-model="item.quantity" :min="1" :max="item.stock" size="small" controls-position="right" @change="() => cart.updateItem(item.id, item.quantity)" />
              </div>
              <!-- 小计：单价 x 数量 -->
              <span class="col-subtotal">¥{{ (item.price * item.quantity).toFixed(2) }}</span>
              <!-- 删除操作 -->
              <div class="col-action">
                <el-button type="danger" link @click="cart.removeItem(item.id)">删除</el-button>
              </div>
            </div>
          </div>
        </div>

        <!-- 底部汇总栏：全选 + 已选件数/合计 + 去结算 -->
        <div class="cart-footer">
          <div class="footer-left">
            <el-checkbox v-model="allSelected" @change="onSelectAll">全选</el-checkbox>
          </div>
          <div class="footer-right">
            <span class="total-label">已选 <b>{{ cart.totalCount }}</b> 件，合计：</span>
            <span class="total-price">¥{{ cart.totalAmount.toFixed(2) }}</span>
            <!-- 未选中任何商品时禁用结算按钮 -->
            <el-button type="primary" size="large" :disabled="cart.totalCount === 0" class="checkout-btn" @click="goCheckout">
              去结算
            </el-button>
          </div>
        </div>
      </template>
      <!-- 空购物车：展示 EmptyTea 空状态 + 去逛逛 -->
      <el-empty v-else>
        <template #image><EmptyTea>购物车空空如也</EmptyTea></template>
        <el-button type="primary" @click="$router.push('/products')">去逛逛</el-button>
      </el-empty>
    </div>
  </div>
</template>

<script setup lang="ts">
// ── 依赖引入 ──
import { computed, onMounted } from 'vue' // Vue 计算属性与生命周期
import { useRouter } from 'vue-router' // 路由：跳转结算页
import { useCartStore } from '@/stores/cart' // 购物车状态仓库
import TeaIcon from '@/components/TeaIcon.vue' // 主题图标（商品图失败占位）
import EmptyTea from '@/components/EmptyTea.vue' // 空状态组件

// ── 状态定义 ──
const router = useRouter() // 路由实例
const cart = useCartStore() // 购物车仓库：商品列表/加载态/总件数/总金额

// ── 全选状态计算属性 ──
// 作用：购物车非空且所有商品均为选中态时返回 true（驱动表头/底部全选框）
const allSelected = computed(() => cart.items.length > 0 && cart.items.every((i) => i.selected))

// ── 全选/取消全选 ──
// 作用：将全选框的布尔值交给仓库批量切换所有商品的选中态
// 参数：v —— 全选框的新状态（string | number | boolean，由 el-checkbox 的 change 事件传入）；
//       返回值：Promise<void>
async function onSelectAll(v: string | number | boolean) {
  await cart.toggleSelectAll(!!v) // 转为布尔后调用仓库的全选切换
}

// ── 去结算 ──
// 作用：跳转到确认订单页
// 参数：无；返回值：无
function goCheckout() { router.push('/checkout') }

// ── 页面挂载后拉取购物车数据 ──
onMounted(() => cart.fetchCart())
</script>

<style scoped>
/* ── 页面容器：上下留白 ── */
.cart-page { padding: 30px 20px 50px; }

/* ── 购物车表格容器：白底圆角卡片 ── */
.cart-table {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(61, 50, 39, 0.05);
}

/* ── 表头行：浅米色底 + 各列对齐 ── */
.cart-header {
  display: flex;
  align-items: center;
  padding: 14px 20px;
  background: #faf7f2;
  font-size: 14px;
  color: #6b6257;
  gap: 12px;
  border-bottom: 1px solid #e6ddca;
}

/* ── 商品行：水平排列，hover 高亮 ── */
.cart-item {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  gap: 12px;
  border-bottom: 1px solid #f5f0e8;
  transition: background 0.15s;
}

.cart-item:hover { background: #fdfcf8; }

/* 商品信息区：弹性撑开 */
.item-product { flex: 1; display: flex; gap: 14px; align-items: center; }

/* 商品图容器：固定 88px 见方，圆角溢出隐藏 */
.item-image { width: 88px; height: 88px; border-radius: 8px; overflow: hidden; background: #faf6ef; flex-shrink: 0; display: flex; align-items: center; justify-content: center; }

.product-img { width: 100%; height: 100%; }

/* 图片加载失败时的茶碗占位图标 */
.img-fallback { font-size: 36px; }

/* 商品名与 SKU 信息 */
.item-name { font-size: 15px; font-weight: 500; color: #2c2a26; margin-bottom: 4px; }
.item-sku { font-size: 12px; color: #6b6257; }

/* 各列固定宽度与对齐 */
.col-name { flex: 1; }
.col-price { width: 100px; text-align: center; }
.col-qty { width: 140px; text-align: center; }
.col-subtotal { width: 100px; text-align: center; color: #b3453a; font-weight: 700; font-size: 15px; }
.col-action { width: 60px; text-align: center; }

/* ── 底部汇总栏：全选 + 合计 + 结算按钮 ── */
.cart-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
  padding: 18px 24px;
  border-radius: 12px;
  margin-top: 20px;
  box-shadow: 0 2px 12px rgba(61, 50, 39, 0.05);
}

.footer-right { display: flex; align-items: center; gap: 16px; }

/* 已选件数文案：件数用朱砂色强调 */
.total-label { font-size: 14px; color: #6b6257; }
.total-label b { color: #b3453a; }

/* 合计金额：大号朱砂加粗 */
.total-price { font-size: 24px; color: #b3453a; font-weight: 700; }

/* 结算按钮：茶青底圆角（覆盖 Element Plus 默认） */
.checkout-btn {
  background: #3f5d4a !important;
  border-color: #3f5d4a !important;
  font-weight: 600 !important;
  padding: 12px 32px !important;
  font-size: 16px !important;
  border-radius: 10px !important;
}
</style>
