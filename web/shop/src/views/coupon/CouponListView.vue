<!--
  ═══════════════════════════════════════════════════════════
  茗韵茶庄商城 · 我的优惠券页（CouponListView.vue）
  ───────────────────────────────────────────────────────────
  职责说明：
    展示当前用户领取的所有优惠券，按状态分类浏览：
      1. 顶部 Tab 切换：可使用 / 已使用 / 已过期（activeTab）；
      2. filteredCoupons 计算属性按状态过滤优惠券列表；
      3. 每张券卡片展示面额、类型、名称、使用门槛、有效期与状态标签；
      4. 不同状态卡片呈现不同视觉（可用-茶青高亮 / 已用-置灰 / 过期-更灰）；
      5. 页面挂载时调用 getUserCoupons() 拉取优惠券数据；
      6. 无数据时展示空状态并提供"去逛逛"入口。
  ═══════════════════════════════════════════════════════════
-->
<template>
  <div class="shop-container coupon-page">
    <h2 class="page-title">我的优惠券</h2>

    <!-- 状态筛选 Tab：可使用/已使用/已过期 -->
    <div class="coupon-tabs">
      <span
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-item"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >{{ tab.label }}</span>
    </div>

    <!-- 优惠券列表：加载中显示遮罩 -->
    <div v-loading="loading">
      <!-- 有符合条件的优惠券：网格展示 -->
      <template v-if="filteredCoupons.length > 0">
        <div class="coupon-grid">
          <!-- 每张优惠券卡片：按状态应用不同样式类 -->
          <div
            v-for="c in filteredCoupons"
            :key="c.id"
            class="coupon-card"
            :class="{
              active: c.status === 'unused',
              used: c.status === 'used',
              expired: c.status === 'expired',
            }"
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
            <!-- 右侧信息区：名称 / 门槛 / 有效期 / 状态标签 -->
            <div class="coupon-right">
              <p class="coupon-name">{{ c.name }}</p>
              <p class="coupon-desc">满 ¥{{ c.threshold }} 可用</p>
              <p class="coupon-expiry">有效期至 {{ c.end_time?.slice(0, 10) }}</p>
              <div class="coupon-status-tag">
                <span v-if="c.status === 'unused'" class="tag-active">可使用</span>
                <span v-else-if="c.status === 'used'" class="tag-used">已使用</span>
                <span v-else class="tag-expired">已过期</span>
              </div>
            </div>
          </div>
        </div>
      </template>
      <!-- 空状态：无优惠券时展示 -->
      <el-empty v-else description="暂无优惠券">
        <el-button type="primary" @click="$router.push('/products')">去逛逛</el-button>
      </el-empty>
    </div>
  </div>
</template>

<script setup lang="ts">
// ── 依赖引入 ──
import { ref, computed, onMounted } from 'vue' // Vue 响应式/计算属性/生命周期
import { getUserCoupons } from '@/api/coupon' // 获取用户优惠券 API

// ── 优惠券数据结构类型声明 ──
interface CouponItem {
  id: number // 用户优惠券实例 ID
  coupon_id: number // 优惠券模板 ID
  name: string // 优惠券名称
  coupon_type: string // 类型：fixed（满减）/ discount（折扣）
  threshold: number // 使用门槛金额
  value: number // 面额（满减为金额，折扣为折数）
  status: string // 状态：unused（可使用）/ used（已使用）/ expired（已过期）
  start_time: string | null // 生效时间
  end_time: string | null // 过期时间
  created_at: string | null // 领取时间
}

// ── 状态定义 ──
const loading = ref(false) // 数据加载中标记（控制 v-loading）
const coupons = ref<CouponItem[]>([]) // 全部优惠券数据
const activeTab = ref('unused') // 当前激活的筛选 Tab（默认"可使用"）

// Tab 配置：key 对应优惠券 status 取值，label 为展示文案
const tabs = [
  { key: 'unused', label: '可使用' },
  { key: 'used', label: '已使用' },
  { key: 'expired', label: '已过期' },
]

// ── 按状态过滤优惠券 ──
// 作用：根据当前激活的 Tab 筛选出对应状态的优惠券列表
const filteredCoupons = computed(() => {
  return coupons.value.filter((c) => c.status === activeTab.value)
})

// ── 页面挂载后拉取优惠券数据 ──
onMounted(async () => {
  loading.value = true
  try {
    const cres = await getUserCoupons() // 请求用户优惠券列表
    coupons.value = cres.data?.data || []
  } catch { /* ignore */ } finally { loading.value = false }
})
</script>

<style scoped>
/* ── 页面容器：上下留白 ── */
.coupon-page { padding: 30px 20px 50px; }

/* ── 状态筛选 Tab：胶囊容器 ── */
.coupon-tabs {
  display: flex; gap: 0;
  background: #faf7f2; border-radius: 10px;
  padding: 4px; margin-bottom: 20px;
}
/* Tab 项：等宽分布，激活态茶青底白字 */
.tab-item {
  flex: 1; text-align: center; padding: 10px 0;
  font-size: 14px; color: #6b6257; cursor: pointer;
  border-radius: 8px; transition: all 0.2s;
}
.tab-item.active { background: #3f5d4a; color: #fff; font-weight: 600; }
.tab-item:hover:not(.active) { color: #2c2a26; }

/* ── 优惠券网格：自适应列数 ── */
.coupon-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }

/* ── 优惠券卡片 ── */
.coupon-card {
  display: flex; align-items: stretch;
  border-radius: 12px; overflow: hidden;
  border: 2px solid #e6ddca;
  background: #fcfaf6;
  transition: all 0.2s;
}
/* 状态样式：可用-茶青高亮；已使用-置灰；已过期-更深置灰 */
.coupon-card.active { border-color: #3f5d4a; background: linear-gradient(135deg, #f8faf6, #eef5ef); box-shadow: 0 2px 12px rgba(74, 124, 89, 0.12); }
.coupon-card.used { opacity: 0.75; filter: grayscale(0.3); }
.coupon-card.expired { opacity: 0.6; filter: grayscale(0.6); }

/* 左侧面额区：随状态呈现不同渐变底色 */
.coupon-left {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 18px 20px; min-width: 100px;
  color: #fff;
}
.coupon-card.active .coupon-left { background: linear-gradient(135deg, #3f5d4a, #5a8f6a); }
.coupon-card.used .coupon-left { background: linear-gradient(135deg, #6b6257, #a08b70); }
.coupon-card.expired .coupon-left { background: linear-gradient(135deg, #b8a48e, #c4b5a5); }

/* 面额数字与类型标签 */
.cv-num { font-size: 24px; font-weight: 700; }
.cv-unit { font-size: 14px; margin-left: 2px; }
.coupon-type-tag { font-size: 11px; margin-top: 4px; opacity: 0.85; background: rgba(255,255,255,0.2); padding: 2px 8px; border-radius: 10px; }

/* 右侧信息区 */
.coupon-right { padding: 16px; flex: 1; display: flex; flex-direction: column; justify-content: center; }
.coupon-name { font-size: 15px; font-weight: 600; color: #2c2a26; margin-bottom: 4px; }
.coupon-desc { font-size: 12px; color: #6b6257; margin-bottom: 2px; }
.coupon-expiry { font-size: 11px; color: #b8a48e; margin-bottom: 6px; }

/* 状态小标签：可使用-浅绿 / 已使用-浅灰 / 已过期-米灰 */
.coupon-status-tag { margin-top: 4px; }
.tag-active { font-size: 11px; color: #3f5d4a; font-weight: 600; padding: 2px 10px; background: #e8f5e9; border-radius: 10px; }
.tag-used { font-size: 11px; color: #6b6257; padding: 2px 10px; background: #efebe5; border-radius: 10px; }
.tag-expired { font-size: 11px; color: #b8a48e; padding: 2px 10px; background: #f3f0e8; border-radius: 10px; }
</style>
