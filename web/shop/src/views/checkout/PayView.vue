<!--
  ═══════════════════════════════════════════════════════════
  茗韵茶庄商城 · 支付页（PayView.vue）
  ───────────────────────────────────────────────────────────
  职责说明：
    订单支付页面，路由形如 /pay/:orderId?amount=xx，职责：
      1. 展示订单编号与应付金额（从路由参数读取）；
      2. 提供支付方式选择（微信支付 / 支付宝，默认微信）；
      3. 调用 payOrder() 发起支付，成功切换为"支付成功"视图；
      4. 页面加载时先查询订单支付状态（getPaymentStatus），
         若已支付（paid）则直接展示成功视图，防止重复支付；
      5. 支付成功视图提供"查看订单详情 / 返回订单列表"入口。
  ═══════════════════════════════════════════════════════════
-->
<template>
  <div class="shop-container pay-page">
    <!-- 未支付成功：展示支付表单 -->
    <template v-if="!paySuccess">
      <h2 class="page-title">确认支付</h2>

      <!-- 订单信息 -->
      <div class="pay-section order-info-card">
        <!-- 订单编号行 -->
        <div class="order-info-row">
          <span class="info-label">订单编号</span>
          <span class="info-value">{{ orderNo }}</span>
        </div>
        <!-- 支付金额行 -->
        <div class="order-info-row">
          <span class="info-label">支付金额</span>
          <span class="info-value amount">¥{{ amount.toFixed(2) }}</span>
        </div>
      </div>

      <!-- 支付方式选择 -->
      <div class="pay-section">
        <h3 class="section-title">选择支付方式</h3>
        <div class="channel-list">
          <!-- 微信支付卡片：选中时高亮 -->
          <div
            class="channel-card"
            :class="{ selected: channel === 'wechat' }"
            @click="channel = 'wechat'"
          >
            <!-- 单选圆点 -->
            <div class="channel-radio">
              <span class="radio-dot" v-if="channel === 'wechat'"></span>
            </div>
            <span class="channel-icon">🟢</span>
            <div class="channel-info">
              <span class="channel-name">微信支付</span>
              <span class="channel-desc">使用微信扫码支付</span>
            </div>
            <!-- 选中对勾 -->
            <span class="channel-check" v-if="channel === 'wechat'">✓</span>
          </div>
          <!-- 支付宝卡片：选中时高亮 -->
          <div
            class="channel-card"
            :class="{ selected: channel === 'alipay' }"
            @click="channel = 'alipay'"
          >
            <div class="channel-radio">
              <span class="radio-dot" v-if="channel === 'alipay'"></span>
            </div>
            <span class="channel-icon">🔵</span>
            <div class="channel-info">
              <span class="channel-name">支付宝</span>
              <span class="channel-desc">使用支付宝扫码支付</span>
            </div>
            <span class="channel-check" v-if="channel === 'alipay'">✓</span>
          </div>
        </div>
      </div>

      <!-- 沙箱支付确认 -->
      <div v-if="pendingPayment" class="pay-section sandbox-box">
        <h3 class="section-title">沙箱支付（模拟）</h3>
        <p class="sandbox-tip">支付单已创建（{{ pendingPayment.payment_no }}），点击下方按钮模拟支付成功回调。</p>
        <el-button type="primary" size="large" class="sandbox-confirm-btn" :loading="confirming" @click="handleConfirm">
          模拟支付成功
        </el-button>
      </div>

      <!-- 支付按钮 -->
      <div class="pay-bottom" v-if="!pendingPayment">
        <!-- 确认支付按钮：支付中显示 loading 文案与转圈动画 -->
        <button class="pay-btn" :disabled="paying" @click="handlePay">
          <span v-if="!paying">确认支付 ¥{{ amount.toFixed(2) }}</span>
          <span v-else class="paying-text">
            <span class="spinner"></span> 支付中...
          </span>
        </button>
      </div>
    </template>

    <!-- 支付成功 -->
    <div v-else class="pay-success-wrap">
      <!-- 成功动画：SVG 对勾描边动画 -->
      <div class="success-animation">
        <div class="checkmark-circle">
          <svg class="checkmark" viewBox="0 0 52 52">
            <circle class="checkmark-circle-bg" cx="26" cy="26" r="25" fill="none" />
            <path class="checkmark-check" fill="none" d="M14 27l7 7 16-16" />
          </svg>
        </div>
      </div>
      <h2 class="success-title">支付成功</h2>
      <p class="success-amount">已支付 ¥{{ amount.toFixed(2) }}</p>
      <!-- 成功后的操作入口 -->
      <div class="success-actions">
        <el-button class="action-btn primary" @click="$router.push(`/order/${orderId}`)">
          去查看订单
        </el-button>
        <el-button class="action-btn" @click="$router.push('/orders')">
          返回订单列表
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// ── 依赖引入 ──
import { ref, onMounted } from 'vue' // Vue 响应式与生命周期
import { useRoute } from 'vue-router' // 路由：读取订单 ID 与金额参数
import { payOrder, getPaymentStatus, confirmPayment } from '@/api/payments' // 支付 API（发起支付 / 查询状态 / 沙箱确认）
import { ElMessage } from 'element-plus' // 消息提示

// ── 状态定义 ──
const route = useRoute() // 当前路由
const orderId = Number(route.params.orderId) // 订单 ID（路由参数）
const amount = ref(Number(route.query.amount) || 0) // 支付金额（查询参数，缺省 0）
const orderNo = ref('') // 展示用订单编号（由订单 ID 格式化）
const channel = ref('wechat') // 当前选择的支付方式（wechat / alipay），默认微信
const paying = ref(false) // 是否正在发起支付（控制按钮 loading）
const confirming = ref(false) // 是否正在确认支付（沙箱回调）
const paySuccess = ref(false) // 是否已支付成功（控制成功视图切换）
const pendingPayment = ref<{ payment_no: string; signature: string; timestamp: number } | null>(null)

// ── 页面挂载后：查询订单支付状态 ──
// 作用：若订单已支付（paid）则直接展示成功视图；否则生成展示用订单编号
onMounted(async () => {
  try {
    const res = await getPaymentStatus(orderId) // 查询订单支付状态
    const data = res.data.data
    if (data.pay_status === 'paid') { // 已支付：直接进入成功视图
      paySuccess.value = true
      return
    }
    orderNo.value = `ORD${String(orderId).padStart(6, '0')}` // 格式化订单编号（如 ORD000123）
  } catch {
    // 降级：用 orderId 拼接显示
    orderNo.value = `ORD${String(orderId).padStart(6, '0')}`
  }
})

// ── 发起支付 ──
// 作用：调用支付接口；成功提示并切换为成功视图，失败提示重试
// 参数：无；返回值：Promise<void>
async function handlePay() {
  if (paying.value) return // 防止重复点击
  paying.value = true // 进入支付中状态
  try {
    const res = await payOrder(orderId, channel.value) // 调用支付接口（携带订单 ID 与支付方式）
    const data = res.data.data
    // 沙箱模式：先展示"模拟支付成功"确认
    pendingPayment.value = {
      payment_no: data.payment_no,
      signature: data.signature,
      timestamp: data.timestamp,
    }
    ElMessage.success('支付单已创建')
  } catch {
    ElMessage.error('支付失败，请重试') // 支付失败提示
  } finally {
    paying.value = false // 复位支付中状态
  }
}

// ── 沙箱确认支付 ──
async function handleConfirm() {
  if (!pendingPayment.value || confirming.value) return
  confirming.value = true
  try {
    await confirmPayment(
      pendingPayment.value.payment_no,
      pendingPayment.value.signature,
      pendingPayment.value.timestamp,
    )
    ElMessage.success('支付成功')
    paySuccess.value = true
  } catch {
    ElMessage.error('确认失败，请重试')
  } finally {
    confirming.value = false
  }
}
</script>

<style scoped>
/* ── 页面容器：窄幅居中，上下留白 ── */
.pay-page {
  padding: 30px 20px 50px;
  max-width: 520px;
  margin: 0 auto;
}

/* 页面标题：居中大标题 */
.page-title {
  font-size: 22px;
  color: #2c2a26;
  text-align: center;
  margin-bottom: 24px;
  font-weight: 700;
}

/* ── 支付区块卡片：白底圆角 ── */
.pay-section {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: 0 2px 12px rgba(61, 50, 39, 0.05);
}

.section-title {
  font-size: 15px;
  color: #2c2a26;
  margin-bottom: 14px;
  font-weight: 600;
}

/* 订单信息 */
/* 信息行：左右分布，行间用虚线分隔 */
.order-info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
}
.order-info-row + .order-info-row {
  border-top: 1px dashed #f2ead9;
  padding-top: 12px;
  margin-top: 4px;
}
.info-label {
  color: #6b6257;
  font-size: 14px;
}
.info-value {
  color: #2c2a26;
  font-size: 14px;
  font-weight: 600;
}
/* 金额值：朱砂色大字 */
.info-value.amount {
  color: #b3453a;
  font-size: 20px;
}

/* 支付方式 */
/* 渠道列表：纵向排列 */
.channel-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 支付方式卡片：点击选择，选中态茶青边框 + 浅绿渐变底 */
.channel-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border: 2px solid #e8e0d5;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fdfcf9;
}
.channel-card:hover {
  border-color: #b8d4c0;
  background: #f8faf6;
}
.channel-card.selected {
  border-color: #3f5d4a;
  background: linear-gradient(135deg, #f0f5ef, #f8faf6);
}

/* 单选圆点：外层圆环，选中时内芯显示茶青圆点 */
.channel-radio {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid #c4b8a8;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: border-color 0.2s;
}
.channel-card.selected .channel-radio {
  border-color: #3f5d4a;
}
.radio-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #3f5d4a;
}

/* 支付渠道图标：微信绿 / 支付宝蓝 emoji */
.channel-icon {
  font-size: 30px;
  flex-shrink: 0;
}

/* 渠道名称与描述 */
.channel-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.channel-name {
  font-size: 16px;
  font-weight: 600;
  color: #2c2a26;
}
.channel-desc {
  font-size: 12px;
  color: #a89880;
}

/* 右侧选中对勾 */
.channel-check {
  font-size: 18px;
  color: #3f5d4a;
  font-weight: 700;
  flex-shrink: 0;
}

/* 支付按钮 */
.pay-bottom {
  margin-top: 24px;
}
/* 全宽大按钮：茶青底，悬停上浮加深 */
.pay-btn {
  width: 100%;
  padding: 16px;
  border: none;
  border-radius: 12px;
  background: #3f5d4a;
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.pay-btn:hover:not(:disabled) {
  background: #314a3b;
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(74, 124, 89, 0.35);
}
.pay-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

/* 支付中文案：转圈图标 + 文字 */
.paying-text {
  display: flex;
  align-items: center;
  gap: 10px;
}
/* 转圈动画：白色圆环旋转 */
.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 支付成功 */
/* 成功视图：居中展示，顶部留白 */
.pay-success-wrap {
  text-align: center;
  padding-top: 60px;
}

.success-animation {
  margin-bottom: 24px;
}
/* 对勾圆环容器 */
.checkmark-circle {
  width: 80px;
  height: 80px;
  margin: 0 auto;
}
/* 圆环底色描边 */
.checkmark-circle-bg {
  stroke: #3f5d4a;
  stroke-width: 2;
}
/* 对勾路径：初始隐藏（dashoffset=48），延迟 0.3s 后描边绘制动画 */
.checkmark-check {
  stroke: #3f5d4a;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 48;
  stroke-dashoffset: 48;
  animation: draw 0.5s ease 0.3s forwards;
}
@keyframes draw {
  to { stroke-dashoffset: 0; }
}

.success-title {
  font-size: 24px;
  color: #2c2a26;
  margin-bottom: 8px;
  font-weight: 700;
}
.success-amount {
  font-size: 16px;
  color: #6b6257;
  margin-bottom: 32px;
}
/* 成功后的操作按钮：纵向排列，主按钮茶青底 */
.success-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 280px;
  margin: 0 auto;
}
.action-btn {
  width: 100%;
  padding: 12px 0;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  border: 1px solid #d4cfc3;
  background: #fff;
  color: #2c2a26;
  cursor: pointer;
  transition: all 0.2s;
}
.action-btn:hover {
  border-color: #b8a88c;
  background: #faf8f5;
}
/* 主按钮：茶青底白字 */
.action-btn.primary {
  background: #3f5d4a;
  border-color: #3f5d4a;
  color: #fff;
}
.action-btn.primary:hover {
  background: #314a3b;
  border-color: #314a3b;
}
</style>
