<!--
  ═══════════════════════════════════════════════════════════
  茗韵茶庄商城 · 确认订单页（CheckoutView.vue）
  ───────────────────────────────────────────────────────────
  职责说明：
    结算前确认页面，展示并处理：
      1. 收货地址（默认地址优先展示；无地址时引导去添加）；
      2. 待结算商品清单（来自购物车已选商品 selectedItems）；
      3. 优惠券选择（校验优惠券是否满足门槛并实时计算减免金额）；
      4. 金额汇总：商品合计 / 优惠减免 / 应付金额；
      5. 提交订单（createOrder）成功后刷新购物车并跳转订单列表；
      6. 兼容"立即购买"流程：从 localStorage 读取 shop_buy_now 临时加购。
  ═══════════════════════════════════════════════════════════
-->
<template>
  <div class="shop-container checkout-page">
    <h2 class="page-title">确认订单</h2>

    <!-- 页面主体：加载期间显示遮罩 -->
    <div v-loading="loading">
      <!-- 有待结算商品时展示订单确认内容 -->
      <template v-if="confirmItems.length > 0">
        <!-- 收货地址区块 -->
        <div class="checkout-section">
          <h3><span class="section-icon">📍</span> 收货地址</h3>
          <!-- 有默认地址：展示收货人/电话/详细地址，绿色高亮边框表示选中 -->
          <div v-if="defaultAddr" class="address-card selected">
            <div class="addr-icon">🏠</div>
            <div class="addr-content">
              <div class="addr-header">
                <span class="addr-name">{{ defaultAddr.receiver_name }}</span>
                <span class="addr-phone">{{ defaultAddr.receiver_phone }}</span>
                <el-tag v-if="defaultAddr.is_default" type="primary" size="small">默认</el-tag>
              </div>
              <p class="addr-detail">{{ defaultAddr.province }}{{ defaultAddr.city }}{{ defaultAddr.district }} {{ defaultAddr.detail }}</p>
            </div>
          </div>
          <!-- 无地址：提示并引导去地址管理页添加 -->
          <div v-else class="no-address">
            <p>🧭 还没有收货地址</p>
            <el-button type="primary" @click="$router.push('/addresses')">添加地址</el-button>
          </div>
        </div>

        <!-- 商品信息区块 -->
        <div class="checkout-section">
          <h3><span class="section-icon">📦</span> 商品信息</h3>
          <div class="order-items">
            <!-- 遍历待结算商品：图片 + 名称/SKU + 单价数量 + 小计 -->
            <div v-for="item in confirmItems" :key="item.id" class="order-item">
              <div class="oi-image">
                <el-image :src="item.image || ''" fit="cover" class="oi-img">
                  <template #error><TeaIcon name="bowl" style="font-size:28px" /></template>
                </el-image>
              </div>
              <div class="oi-info">
                <p class="oi-name">{{ item.product_name }} / {{ item.sku_name }}</p>
                <div class="oi-meta">
                  <span class="oi-price">¥{{ item.price?.toFixed(2) }}</span>
                  <span class="oi-qty">x{{ item.quantity }}</span>
                </div>
              </div>
              <span class="oi-total">¥{{ (item.price * item.quantity).toFixed(2) }}</span>
            </div>
          </div>
        </div>

        <!-- 优惠券 -->
        <div class="checkout-section">
          <h3><span class="section-icon">🎫</span> 优惠券</h3>
          <!-- 有可用优惠券：卡片式展示，点击选择/取消 -->
          <template v-if="coupons.length > 0">
            <div class="coupon-list">
              <!-- 每张优惠券卡片：点击触发 onSelectCoupon 选择/取消选择 -->
              <div
                v-for="c in coupons"
                :key="c.id"
                class="coupon-card"
                :class="{ selected: selectedCouponId === c.id }"
                @click="onSelectCoupon(c)"
              >
                <!-- 左侧面额区：满减券显示 ¥金额，折扣券显示 数字+折 -->
                <div class="coupon-left">
                  <div class="coupon-value">
                    <template v-if="c.coupon_type === 'fixed'">
                      <span class="cv-num">¥{{ c.value }}</span>
                    </template>
                    <template v-else>
                      <span class="cv-num">{{ c.value }}</span><span class="cv-unit">折</span>
                    </template>
                  </div>
                  <div class="coupon-type-tag">{{ c.coupon_type === 'fixed' ? '满减券' : '折扣券' }}</div>
                </div>
                <!-- 右侧信息区：名称 / 使用门槛 / 有效期 -->
                <div class="coupon-right">
                  <p class="coupon-name">{{ c.name }}</p>
                  <p class="coupon-desc">满 ¥{{ c.threshold }} 可用</p>
                  <p class="coupon-expiry">有效期至 {{ c.end_time?.slice(0, 10) }}</p>
                </div>
                <!-- 选中标记 -->
                <div v-if="selectedCouponId === c.id" class="coupon-check">✓</div>
              </div>
            </div>
            <!-- 优惠券校验结果提示（如未达门槛），失败时红色显示 -->
            <p class="no-coupon-tip" v-if="couponValidateMsg" :class="{ 'tip-error': !couponValid }">{{ couponValidateMsg }}</p>
          </template>
          <!-- 无可用优惠券 -->
          <p v-else class="no-coupon-tip">暂无可用优惠券</p>
        </div>

        <!-- 底部金额汇总 + 提交订单 -->
        <div class="checkout-bottom">
          <div class="bottom-summary">
            <div class="summary-lines">
              <!-- 商品合计 -->
              <div class="summary-line">
                <span>商品合计：</span>
                <span>¥{{ totalAmount.toFixed(2) }}</span>
              </div>
              <!-- 优惠减免（有优惠时才显示） -->
              <div v-if="discountAmount > 0" class="summary-line discount-line">
                <span>优惠减免：</span>
                <span>-¥{{ discountAmount.toFixed(2) }}</span>
              </div>
              <!-- 应付金额：商品合计 - 优惠减免，最低为 0 -->
              <div class="summary-line total-line">
                <span>应付金额：</span>
                <span class="total-amount">¥{{ payAmount.toFixed(2) }}</span>
              </div>
            </div>
          </div>
          <!-- 提交订单按钮：无地址时禁用，提交期间 loading -->
          <el-button type="primary" size="large" :disabled="!defaultAddr" :loading="submitting" class="submit-order-btn" @click="submitOrder">
            提交订单
          </el-button>
        </div>
      </template>
      <!-- 无可结算商品：空状态 + 返回购物车 -->
      <el-empty v-else description="没有待结算的商品">
        <el-button type="primary" @click="$router.push('/cart')">返回购物车</el-button>
      </el-empty>
    </div>
  </div>
</template>

<script setup lang="ts">
// ── 依赖引入 ──
import { ref, computed, onMounted } from 'vue' // Vue 响应式/计算属性/生命周期
import { useRouter } from 'vue-router' // 路由：提交成功后跳转订单列表
import { useCartStore } from '@/stores/cart' // 购物车仓库（已选商品、合计金额）
import { getAddresses, type Address } from '@/api/user' // 地址相关 API 与类型
import { createOrder } from '@/api/orders' // 创建订单 API
import { getUserCoupons, validateCoupon } from '@/api/coupon' // 优惠券 API（列表 + 校验）
import { ElMessage } from 'element-plus' // 消息提示
import TeaIcon from '@/components/TeaIcon.vue' // 主题图标（商品图失败占位）

// ── 基础状态 ──
const router = useRouter() // 路由实例
const cart = useCartStore() // 购物车仓库
const loading = ref(false) // 页面初始化加载中标记
const submitting = ref(false) // 提交订单进行中标记
const addresses = ref<Address[]>([]) // 用户收货地址列表
const coupons = ref<any[]>([]) // 用户可用优惠券列表
const selectedCouponId = ref<number | null>(null) // 当前选中的优惠券 ID（null 表示未选）
const discountAmount = ref(0) // 优惠券减免金额
const couponValid = ref(false) // 优惠券校验是否通过
const couponValidateMsg = ref('') // 优惠券校验结果提示文案

// ── 优惠券数据结构类型声明 ──
interface CouponItem {
  id: number // 用户优惠券实例 ID
  coupon_id: number // 优惠券模板 ID
  name: string // 优惠券名称
  coupon_type: string // 类型：fixed（满减）/ discount（折扣）
  threshold: number // 使用门槛金额
  value: number // 面额（满减为金额，折扣为折数）
  status: string // 状态：unused/used/expired
  start_time: string | null // 生效时间
  end_time: string | null // 过期时间
  created_at: string | null // 领取时间
}

// ── 计算属性 ──
// 默认地址：优先取 is_default 标记的地址，否则取列表第一个
const defaultAddr = computed(() => addresses.value.find((a) => a.is_default) || addresses.value[0])
// 待结算商品：购物车中勾选（selected）的商品
const confirmItems = computed(() => cart.selectedItems)
// 已选商品总件数
const totalCount = computed(() => cart.totalCount)
// 已选商品金额合计
const totalAmount = computed(() => cart.totalAmount)
// 应付金额：商品合计 - 优惠减免（最小为 0，防止折扣超额）
const payAmount = computed(() => Math.max(0, totalAmount.value - discountAmount.value))

// ── 选择/取消优惠券 ──
// 作用：点击优惠券卡片时切换选中状态；选中后调用 validateCoupon 校验门槛，
//       通过则更新减免金额与提示文案，不通过则给出错误提示
// 参数：c —— 被点击的优惠券对象（CouponItem）；返回值：Promise<void>
async function onSelectCoupon(c: CouponItem) {
  // 再次点击同一张券：取消选择，清除减免
  if (selectedCouponId.value === c.id) {
    selectedCouponId.value = null
    discountAmount.value = 0
    couponValid.value = false
    couponValidateMsg.value = ''
    return
  }
  try {
    const res = await validateCoupon(c.id, totalAmount.value) // 携带当前商品金额校验券是否可用
    const data = res.data?.data
    if (data?.valid) { // 校验通过：选中并应用减免
      selectedCouponId.value = c.id
      discountAmount.value = data.discount
      couponValid.value = true
      couponValidateMsg.value = data.message
    } else { // 校验不通过：提示原因（如未达门槛）
      couponValid.value = false
      couponValidateMsg.value = data?.message || '优惠券不可用'
      ElMessage.warning(data?.message || '优惠券不可用')
    }
  } catch {
    couponValidateMsg.value = '校验失败' // 接口异常时给出兜底文案
  }
}

// ── 提交订单 ──
// 作用：组装订单请求体（已选商品 sku 与数量 + 地址 + 可选优惠券），
//       调用 createOrder 创建订单；成功后刷新购物车并跳转订单列表
// 参数：无；返回值：Promise<void>
async function submitOrder() {
  if (!defaultAddr.value) { ElMessage.warning('请选择收货地址'); return } // 无地址禁止提交
  submitting.value = true // 进入提交中状态
  try {
    const body: any = {
      items: confirmItems.value.map((i) => ({ sku_id: i.sku_id, quantity: i.quantity })), // 待结算商品明细
      address_id: defaultAddr.value.id, // 收货地址 ID
    }
    if (selectedCouponId.value) { // 选了优惠券则附带优惠券 ID
      body.coupon_id = selectedCouponId.value
    }
    await createOrder(body) // 调用创建订单接口
    ElMessage.success('订单已提交')
    await cart.fetchCart() // 刷新购物车（已结算商品被清空）
    router.push('/orders') // 跳转订单列表页
  } catch { /* */ } finally { submitting.value = false } // 失败提示由拦截器统一处理；最终复位 submitting
}

// ── 页面挂载后初始化 ──
// 作用：并行加载地址列表、购物车数据与可用优惠券；
//       同时兼容"立即购买"流程：若 localStorage 存在 shop_buy_now，
//       则将其对应 SKU 加入购物车并只选中该商品，再清理标记
onMounted(async () => {
  loading.value = true
  try {
    const res = await getAddresses() // 拉取收货地址
    addresses.value = res.data.data || []
    await cart.fetchCart() // 拉取购物车
    const buyNow = localStorage.getItem('shop_buy_now') // 读取立即购买标记
    if (buyNow) { // 立即购买流程：临时加购指定 SKU
      const parsed = JSON.parse(buyNow)
      await cart.addItem(parsed.sku_id, parsed.quantity) // 把"立即购买"的商品加入购物车
      localStorage.removeItem('shop_buy_now') // 清理标记，避免重复触发
      await cart.fetchCart()
      if (cart.items.length > 0) await cart.toggleSelectItem(cart.items[cart.items.length - 1].id, true) // 只选中最后加入的这件商品
    }
  } catch { /* */ } finally { loading.value = false }

  try {
    const cres = await getUserCoupons() // 拉取用户可用优惠券
    coupons.value = cres.data?.data || []
  } catch { /* ignore */ } // 优惠券拉取失败不影响结算
})
</script>

<style scoped>
/* ── 页面容器：上下留白 ── */
.checkout-page { padding: 30px 20px 50px; }

/* ── 结算区块卡片：白底圆角 + 轻阴影 ── */
.checkout-section {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: 0 2px 12px rgba(61, 50, 39, 0.05);
}

/* 区块标题：底部浅米色分隔线 */
.checkout-section h3 { font-size: 16px; color: #2c2a26; margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid #f2ead9; display: flex; align-items: center; gap: 6px; }

/* 标题前的 emoji 图标 */
.section-icon { font-size: 18px; }

/* ── 收货地址卡片：绿色边框 + 浅绿渐变底，表示当前选中的地址 ── */
.address-card {
  display: flex; gap: 14px;
  padding: 16px; border: 2px solid #3f5d4a; border-radius: 10px;
  background: linear-gradient(135deg, #f8faf6, #f0f5ef);
}

/* 地址图标：房子 emoji */
.addr-icon { font-size: 32px; flex-shrink: 0; }

/* 地址头部行：姓名 + 电话 + 默认标签 */
.addr-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.addr-name { font-weight: 600; font-size: 16px; }
.addr-phone { color: #6b6257; }
.addr-detail { color: #6b6257; font-size: 13px; }

/* 无地址提示区 */
.no-address { text-align: center; padding: 30px; color: #6b6257; }

/* ── 商品信息列表 ── */
.oi-image { width: 80px; height: 80px; border-radius: 8px; overflow: hidden; background: #faf6ef; flex-shrink: 0; display: flex; align-items: center; justify-content: center; }
.oi-img { width: 100%; height: 100%; }

.order-item { display: flex; align-items: center; gap: 14px; padding: 14px 0; border-bottom: 1px solid #f5f0e8; }
.oi-info { flex: 1; }
.oi-name { font-size: 14px; color: #2c2a26; margin-bottom: 4px; }
.oi-meta { display: flex; gap: 16px; }
.oi-price { color: #b3453a; font-weight: 600; }
.oi-qty { color: #6b6257; font-size: 13px; }
.oi-total { color: #b3453a; font-weight: 700; font-size: 16px; }

/* 优惠券 */
/* 优惠券列表：弹性换行排列 */
.coupon-list { display: flex; flex-wrap: wrap; gap: 12px; }
/* 优惠券卡片：左侧面额区 + 右侧信息区，hover/选中态有边框高亮 */
.coupon-card {
  display: flex; align-items: stretch;
  border: 2px solid #e6ddca; border-radius: 10px;
  overflow: hidden; cursor: pointer;
  transition: all 0.2s; min-width: 280px;
  background: #fcfaf6; position: relative;
}
.coupon-card:hover { border-color: #b08d57; box-shadow: 0 2px 8px rgba(200, 155, 100, 0.15); }
/* 选中态：茶青边框 + 浅绿渐变底 */
.coupon-card.selected { border-color: #3f5d4a; background: linear-gradient(135deg, #f8faf6, #eef5ef); box-shadow: 0 2px 12px rgba(74, 124, 89, 0.12); }

/* 左侧面额区：茶青渐变底白字 */
.coupon-left {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 14px 18px; background: linear-gradient(135deg, #3f5d4a, #5a8f6a);
  color: #fff; min-width: 90px;
}
/* 选中时左侧底色加深 */
.coupon-card.selected .coupon-left { background: linear-gradient(135deg, #3d6b4a, #3f5d4a); }

/* 面额数字与单位 */
.cv-num { font-size: 22px; font-weight: 700; }
.cv-unit { font-size: 14px; margin-left: 2px; }
/* 券类型小标签：半透明白底圆角 */
.coupon-type-tag { font-size: 11px; margin-top: 4px; opacity: 0.85; background: rgba(255,255,255,0.2); padding: 2px 8px; border-radius: 10px; }

/* 右侧信息区：名称 / 门槛 / 有效期 */
.coupon-right { padding: 14px 16px; flex: 1; display: flex; flex-direction: column; justify-content: center; }
.coupon-name { font-size: 14px; font-weight: 600; color: #2c2a26; margin-bottom: 4px; }
.coupon-desc { font-size: 12px; color: #6b6257; margin-bottom: 2px; }
.coupon-expiry { font-size: 11px; color: #b8a48e; }

/* 右上角选中对勾标记 */
.coupon-check {
  position: absolute; top: 0; right: 0;
  width: 28px; height: 28px;
  background: #3f5d4a; color: #fff;
  display: flex; align-items: center; justify-content: center;
  border-radius: 0 10px 0 12px; font-size: 14px; font-weight: 700;
}

/* 优惠券提示文案（默认次级色，错误时红色） */
.no-coupon-tip { font-size: 13px; color: #6b6257; padding: 8px 0; }
.tip-error { color: #b3453a; }

/* ── 底部金额汇总栏 ── */
.checkout-bottom {
  display: flex; justify-content: space-between; align-items: flex-end; gap: 20px;
  background: #fff; padding: 20px 24px; border-radius: 12px;
  box-shadow: 0 2px 12px rgba(61, 50, 39, 0.05);
}

/* 汇总区：右对齐纵向排列 */
.bottom-summary { display: flex; flex-direction: column; align-items: flex-end; color: #6b6257; font-size: 14px; }

.summary-lines { display: flex; flex-direction: column; gap: 4px; }
.summary-line { display: flex; justify-content: space-between; gap: 20px; font-size: 13px; color: #6b6257; }
/* 优惠减免行：茶青加粗 */
.discount-line { color: #3f5d4a; font-weight: 600; }
/* 应付金额行：顶部虚线分隔 */
.total-line { font-size: 15px; color: #2c2a26; padding-top: 6px; border-top: 1px dashed #e6ddca; margin-top: 4px; }

/* 应付金额数字：大号朱砂 */
.total-amount { font-size: 26px; color: #b3453a; font-weight: 700; display: inline; }

/* 提交订单按钮：茶青底大按钮 */
.submit-order-btn {
  background: #3f5d4a !important; border-color: #3f5d4a !important;
  font-weight: 600 !important; font-size: 16px !important;
  padding: 14px 36px !important; border-radius: 12px !important;
}
</style>
