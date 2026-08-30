<!--
 * ============================================================
 * 模块说明：营销中心页面（views/marketing/MarketingView.vue）
 *
 * 职责（两个 Tab）：
 *   1) 优惠券：列表分页、新建优惠券（满减/折扣）、发放给指定用户、
 *      停用（删除）优惠券
 *   2) 促销活动：列表分页、新建满减/秒杀活动（规则以 JSON 提交，
 *      适用商品以逗号分隔的商品 ID 提交）
 * ============================================================
 -->
<script setup lang="ts">
// Vue 响应式工具与生命周期钩子
import { ref, reactive, onMounted } from 'vue'
// Element Plus 消息提示与确认框
import { ElMessage, ElMessageBox } from 'element-plus'
// 营销模块相关 API：优惠券（列表/创建/删除/发放）、促销活动（列表/创建）及数据类型
import {
  getCoupons, createCoupon, deleteCoupon, grantCoupon,
  getPromotions, createPromotion,
  type CouponItem, type PromotionItem,
} from '@/api/marketing'

// ── TAB ──
// 当前激活的 Tab：'coupons'（优惠券）/ 'promotions'（促销活动）
const activeTab = ref('coupons')

// ── 优惠券 ──
// 优惠券列表加载状态（表格 loading 遮罩）
const couponLoading = ref(false)
// 优惠券列表数据
const couponList = ref<CouponItem[]>([])
// 优惠券总条数（分页用）
const couponTotal = ref(0)
// 优惠券分页参数：页码、每页条数
const couponPage = reactive({ page: 1, page_size: 20 })

/**
 * 拉取优惠券列表（异步）
 * 按当前分页参数请求数据，写入 couponList 与 couponTotal
 */
async function fetchCoupons() {
  couponLoading.value = true
  const res = await getCoupons(couponPage)
  couponList.value = res.data || []
  couponTotal.value = res.total
  couponLoading.value = false
}

// 新建优惠券弹窗显示/隐藏
const couponVisible = ref(false)
// 新建优惠券表单：名称、类型（fixed 满减/percent 折扣）、门槛、面值/折扣率、
// 发放总量、每人限领、起止时间
const couponForm = reactive({
  name: '', coupon_type: 'fixed', threshold: 0, value: 0,
  total_count: 100, user_limit: 1,
  start_time: '', end_time: '',
})
/**
 * 提交创建优惠券（异步）
 * 调用创建接口，成功后提示、关闭弹窗并刷新列表
 */
async function handleCreateCoupon() {
  await createCoupon(couponForm)
  ElMessage.success('创建成功')
  couponVisible.value = false
  fetchCoupons()
}

/**
 * 停用优惠券（异步）
 * 弹窗确认后调用删除（停用）接口，成功后刷新列表
 * @param id 优惠券 ID
 */
async function handleDeleteCoupon(id: number) {
  await ElMessageBox.confirm('确定停用？', '提示', { type: 'warning' })
  await deleteCoupon(id)
  fetchCoupons()
}

// 发放优惠券弹窗显示/隐藏
const grantVisible = ref(false)
// 发券表单：目标优惠券 ID、目标用户 ID 列表（逗号分隔字符串）
const grantForm = reactive({ coupon_id: 0, user_ids: '' })
/**
 * 打开发券弹窗
 * @param row 优惠券行数据，取其 ID 写入表单
 */
function openGrant(row: CouponItem) { grantForm.coupon_id = row.id; grantForm.user_ids = ''; grantVisible.value = true }
/**
 * 提交发放优惠券（异步）
 * 将逗号分隔的用户 ID 字符串解析为数字数组（过滤空值），
 * 调用发放接口后提示发放张数并刷新列表
 */
async function handleGrant() {
  // 解析用户 ID：按逗号拆分 → 转数字 → 过滤 0/NaN 等假值
  const ids = grantForm.user_ids.split(',').map(Number).filter(Boolean)
  // 调用发放接口，返回实际发放张数
  const res = await grantCoupon(grantForm.coupon_id, { user_ids: ids })
  ElMessage.success(`已发放 ${res.data.granted} 张`)
  grantVisible.value = false
  fetchCoupons()
}

// ── 促销活动 ──
// 促销活动列表加载状态（表格 loading 遮罩）
const promoLoading = ref(false)
// 促销活动列表数据
const promoList = ref<PromotionItem[]>([])
// 促销活动总条数（分页用）
const promoTotal = ref(0)
// 促销活动分页参数：页码、每页条数
const promoPage = reactive({ page: 1, page_size: 20 })

/**
 * 拉取促销活动列表（异步）
 * 按当前分页参数请求数据，写入 promoList 与 promoTotal
 */
async function fetchPromotions() {
  promoLoading.value = true
  const res = await getPromotions(promoPage)
  promoList.value = res.data || []
  promoTotal.value = res.total
  promoLoading.value = false
}

// 新建活动弹窗显示/隐藏
const promoVisible = ref(false)
// 新建活动表单：名称、类型（满减/秒杀）、规则 JSON 字符串、
// 适用商品 ID（逗号分隔字符串）、起止时间
const promoForm = reactive({ name: '', promo_type: 'full_reduction', rules: '{}', product_ids: '', start_time: '', end_time: '' })
/**
 * 提交创建促销活动（异步）
 * 提交前将 rules 由 JSON 字符串解析为对象、product_ids 解析为数字数组，
 * 成功后提示、关闭弹窗并刷新列表
 */
async function handleCreatePromo() {
  await createPromotion({
    ...promoForm,
    // 将规则 JSON 字符串解析为对象
    rules: JSON.parse(promoForm.rules),
    // 将商品 ID 逗号分隔字符串解析为数字数组（过滤空值）
    product_ids: promoForm.product_ids.split(',').map(Number).filter(Boolean),
  })
  ElMessage.success('创建成功')
  promoVisible.value = false
  fetchPromotions()
}

// 页面挂载：并行初始化优惠券与促销活动列表
onMounted(() => { fetchCoupons(); fetchPromotions() })
</script>

<template>
  <!-- 页面容器（通用白底卡片样式） -->
  <div class="page-container">
    <!-- Tab 切换：优惠券 / 促销活动 -->
    <el-tabs v-model="activeTab">
      <!-- 优惠券 Tab：列表 + 新建/发券/停用操作 -->
      <el-tab-pane label="优惠券" name="coupons">
        <!-- 右上角操作区：新建优惠券按钮 -->
        <div style="display:flex;justify-content:flex-end;margin-bottom:16px">
          <el-button type="primary" @click="couponVisible = true">新建优惠券</el-button>
        </div>
        <!-- 优惠券列表表格 -->
        <el-table :data="couponList" v-loading="couponLoading" stripe>
          <el-table-column prop="name" label="名称" min-width="140" />
          <!-- 优惠券类型：满减/折扣 -->
          <el-table-column label="类型" width="90"><template #default="{row}">{{ row.coupon_type === 'fixed' ? '满减' : '折扣' }}</template></el-table-column>
          <!-- 门槛/面值：满减显示 ¥ 面值，折扣显示百分比 -->
          <el-table-column label="门槛/面值" width="130"><template #default="{row}">满¥{{ row.threshold }}减{{ row.coupon_type==='fixed'?`¥${row.value}`:`${row.value}%` }}</template></el-table-column>
          <!-- 发放库存：已用/总量 -->
          <el-table-column label="库存" width="100"><template #default="{row}">{{ row.used_count }}/{{ row.total_count }}</template></el-table-column>
          <!-- 每人限领数量 -->
          <el-table-column label="限领" width="60"><template #default="{row}">{{ row.user_limit }}</template></el-table-column>
          <!-- 有效期（取日期部分） -->
          <el-table-column label="有效期" width="200"><template #default="{row}">{{ row.start_time?.slice(0,10) }} ~ {{ row.end_time?.slice(0,10) }}</template></el-table-column>
          <!-- 状态：启用/停用 -->
          <el-table-column label="状态" width="80"><template #default="{row}"><el-tag :type="row.status==='active'?'success':'info'">{{ row.status==='active'?'启用':'停用' }}</el-tag></template></el-table-column>
          <!-- 行操作：发券 / 停用 -->
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <!-- 发放给指定用户 -->
              <el-button text type="primary" size="small" @click="openGrant(row)">发券</el-button>
              <!-- 停用该优惠券（需确认） -->
              <el-button text type="danger" size="small" @click="handleDeleteCoupon(row.id)">停用</el-button>
            </template>
          </el-table-column>
        </el-table>
        <!-- 分页器：切换页码触发重新查询 -->
        <el-pagination v-model:current-page="couponPage.page" :total="couponTotal" :page-size="20" layout="total,prev,pager,next" style="margin-top:16px;justify-content:flex-end" @change="fetchCoupons" />
      </el-tab-pane>

      <!-- 促销活动 Tab：列表 + 新建活动 -->
      <el-tab-pane label="促销活动" name="promotions">
        <!-- 右上角操作区：新建活动按钮 -->
        <div style="display:flex;justify-content:flex-end;margin-bottom:16px">
          <el-button type="primary" @click="promoVisible = true">新建活动</el-button>
        </div>
        <!-- 促销活动列表表格 -->
        <el-table :data="promoList" v-loading="promoLoading" stripe>
          <el-table-column prop="name" label="名称" min-width="140" />
          <el-table-column prop="promo_type" label="类型" width="120" />
          <!-- 适用商品数量 -->
          <el-table-column label="适用商品" width="100"><template #default="{row}">{{ (row.product_ids||[]).length }}个</template></el-table-column>
          <!-- 活动时间（取日期部分） -->
          <el-table-column label="活动时间" width="200"><template #default="{row}">{{ row.start_time?.slice(0,10) }} ~ {{ row.end_time?.slice(0,10) }}</template></el-table-column>
          <!-- 活动状态 -->
          <el-table-column label="状态" width="80"><template #default="{row}"><el-tag>{{ row.status }}</el-tag></template></el-table-column>
        </el-table>
        <!-- 分页器：切换页码触发重新查询 -->
        <el-pagination v-model:current-page="promoPage.page" :total="promoTotal" :page-size="20" layout="total,prev,pager,next" style="margin-top:16px;justify-content:flex-end" @change="fetchPromotions" />
      </el-tab-pane>
    </el-tabs>

    <!-- 新建优惠券弹窗：名称/类型/门槛/面值/发放总量/限领/有效期 -->
    <el-dialog title="新建优惠券" v-model="couponVisible" width="500px">
      <el-form :model="couponForm" label-width="80px">
        <!-- 名称与类型（满减/折扣） -->
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="名称"><el-input v-model="couponForm.name" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="类型"><el-select v-model="couponForm.coupon_type" style="width:100%"><el-option label="满减" value="fixed" /><el-option label="折扣" value="percent" /></el-select></el-form-item></el-col>
        </el-row>
        <!-- 门槛与面值/折扣率（标签随类型切换） -->
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="门槛"><el-input-number v-model="couponForm.threshold" :min="0" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item :label="couponForm.coupon_type==='fixed'?'面值':'折扣率'"><el-input-number v-model="couponForm.value" :min="0" style="width:100%" /></el-form-item></el-col>
        </el-row>
        <!-- 发放总量与每人限领 -->
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="发放总量"><el-input-number v-model="couponForm.total_count" :min="1" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="每人限领"><el-input-number v-model="couponForm.user_limit" :min="1" :max="10" style="width:100%" /></el-form-item></el-col>
        </el-row>
        <!-- 有效期：开始/结束时间 -->
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="开始时间"><el-date-picker v-model="couponForm.start_time" type="datetime" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="结束时间"><el-date-picker v-model="couponForm.end_time" type="datetime" style="width:100%" /></el-form-item></el-col>
        </el-row>
      </el-form>
      <!-- 弹窗底部按钮：取消 / 创建 -->
      <template #footer><el-button @click="couponVisible=false">取消</el-button><el-button type="primary" @click="handleCreateCoupon">创建</el-button></template>
    </el-dialog>

    <!-- 发券弹窗：输入目标用户 ID（逗号分隔） -->
    <el-dialog title="发放优惠券" v-model="grantVisible" width="400px">
      <el-form :model="grantForm" label-width="80px">
        <!-- 用户 ID 列表输入 -->
        <el-form-item label="用户ID"><el-input v-model="grantForm.user_ids" placeholder="多个用逗号分隔，如 1,2,3" /></el-form-item>
      </el-form>
      <!-- 弹窗底部按钮：取消 / 发放 -->
      <template #footer><el-button @click="grantVisible=false">取消</el-button><el-button type="primary" @click="handleGrant">发放</el-button></template>
    </el-dialog>

    <!-- 新建活动弹窗：名称/类型/规则 JSON/适用商品/有效期 -->
    <el-dialog title="新建促销活动" v-model="promoVisible" width="500px">
      <el-form :model="promoForm" label-width="80px">
        <el-form-item label="名称"><el-input v-model="promoForm.name" /></el-form-item>
        <!-- 活动类型：满减/秒杀 -->
        <el-form-item label="类型"><el-select v-model="promoForm.promo_type" style="width:100%"><el-option label="满减" value="full_reduction" /><el-option label="秒杀" value="flash_sale" /></el-select></el-form-item>
        <!-- 规则 JSON 输入（提交时解析为对象） -->
        <el-form-item label="规则JSON"><el-input v-model="promoForm.rules" type="textarea" :rows="3" placeholder='如 {"full":200,"reduce":20}' /></el-form-item>
        <!-- 适用商品 ID（逗号分隔） -->
        <el-form-item label="适用商品"><el-input v-model="promoForm.product_ids" placeholder="商品ID逗号分隔" /></el-form-item>
        <!-- 有效期：开始/结束时间 -->
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="开始时间"><el-date-picker v-model="promoForm.start_time" type="datetime" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="结束时间"><el-date-picker v-model="promoForm.end_time" type="datetime" style="width:100%" /></el-form-item></el-col>
        </el-row>
      </el-form>
      <!-- 弹窗底部按钮：取消 / 创建 -->
      <template #footer><el-button @click="promoVisible=false">取消</el-button><el-button type="primary" @click="handleCreatePromo">创建</el-button></template>
    </el-dialog>
  </div>
</template>
