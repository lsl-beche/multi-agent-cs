<!--
  ═══════════════════════════════════════════════════════════
  茗韵茶庄商城 · 个人中心页（ProfileView.vue）
  ───────────────────────────────────────────────────────────
  职责说明：
    展示并编辑当前用户的基础资料，包含：
      1. 用户头像（用户名首字母）+ 用户名 + 会员标识；
      2. 资料表单：用户名（只读展示）、手机号、邮箱（可编辑）；
      3. 保存修改：调用 updateProfile() 更新资料，成功后
         重新拉取用户信息（auth.fetchProfile()）并同步本地显示；
      4. 快捷入口卡片：收货地址 / 我的订单 / 购物车（点击跳转）；
      5. 页面挂载时刷新一次用户资料并回填表单。
  ═══════════════════════════════════════════════════════════
-->
<template>
  <div class="shop-container profile-page">
    <h2 class="page-title">个人中心</h2>

    <!-- 资料卡片：头像 + 编辑表单 -->
    <div class="profile-card">
      <!-- 头像区：首字母头像 + 用户名 + 会员标识 -->
      <div class="avatar-section">
        <el-avatar :size="88" class="user-avatar">{{ user?.username?.charAt(0)?.toUpperCase() || 'U' }}</el-avatar>
        <div class="avatar-info">
          <h3>{{ user?.username || '用户' }}</h3>
          <p>茗韵会员</p>
        </div>
      </div>

      <!-- 资料编辑表单 -->
      <el-form :model="form" label-width="80px" class="profile-form">
        <!-- 用户名：只读 -->
        <el-form-item label="用户名">
          <el-input :model-value="user?.username" disabled />
        </el-form-item>
        <!-- 手机号 -->
        <el-form-item label="手机号">
          <el-input v-model="form.phone" placeholder="请输入手机号" />
        </el-form-item>
        <!-- 邮箱 -->
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>
        <!-- 保存按钮 -->
        <el-form-item>
          <el-button type="primary" :loading="saving" class="save-btn" @click="saveProfile">保存修改</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 快捷入口卡片 -->
    <div class="quick-links">
      <!-- 收货地址入口 -->
      <div class="quick-card" @click="$router.push('/addresses')">
        <span class="qc-icon">📍</span>
        <span class="qc-label">收货地址</span>
        <span class="qc-desc">管理您的收货地址</span>
      </div>
      <!-- 我的订单入口 -->
      <div class="quick-card" @click="$router.push('/orders')">
        <span class="qc-icon">📋</span>
        <span class="qc-label">我的订单</span>
        <span class="qc-desc">查看订单状态</span>
      </div>
      <!-- 购物车入口 -->
      <div class="quick-card" @click="$router.push('/cart')">
        <span class="qc-icon">🛒</span>
        <span class="qc-label">购物车</span>
        <span class="qc-desc">管理购物车商品</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// ── 依赖引入 ──
import { ref, reactive, onMounted } from 'vue' // Vue 响应式与生命周期
import { useAuthStore } from '@/stores/auth' // 认证仓库（用户信息 + 资料更新）
import { updateProfile } from '@/api/user' // 更新用户资料 API
import { ElMessage } from 'element-plus' // 消息提示

// ── 状态定义 ──
const auth = useAuthStore() // 认证仓库
const user = ref(auth.user) // 当前用户信息（用于界面展示）
const saving = ref(false) // 保存请求中标记
// 可编辑资料表单：手机号 / 邮箱（初始值取自当前用户）
const form = reactive({
  phone: user.value?.phone || '',
  email: user.value?.email || '',
})

// ── 保存资料 ──
// 作用：调用 updateProfile 更新手机号/邮箱，成功后重新拉取用户资料并同步到本地
// 参数：无；返回值：Promise<void>
async function saveProfile() {
  saving.value = true // 进入保存中状态
  try {
    await updateProfile(form) // 调用更新接口（提交 phone/email）
    ElMessage.success('保存成功')
    await auth.fetchProfile() // 重新拉取最新用户资料（token 同步刷新）
    user.value = auth.user // 同步本地展示数据
  } catch { /* */ } finally { saving.value = false } // 失败提示由拦截器统一处理；最终复位 saving
}

// ── 页面挂载后：刷新用户资料并回填表单 ──
onMounted(async () => {
  await auth.fetchProfile() // 刷新用户资料（确保显示最新数据）
  user.value = auth.user
  form.phone = user.value?.phone || '' // 回填手机号
  form.email = user.value?.email || '' // 回填邮箱
})
</script>

<style scoped>
/* ── 页面容器 ── */
.profile-page { padding: 30px 20px 50px; }

/* ── 资料卡片：白底大圆角 ── */
.profile-card {
  background: #fff;
  border-radius: 16px;
  padding: 36px;
  box-shadow: 0 2px 12px rgba(61, 50, 39, 0.05);
}

/* ── 头像区：头像 + 信息，底部描边分隔 ── */
.avatar-section {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 32px;
  padding-bottom: 24px;
  border-bottom: 1px solid #f2ead9;
}

/* 首字母头像：茶青渐变底白字 */
.user-avatar {
  background: linear-gradient(135deg, #3f5d4a, #5f7d6c) !important;
  font-size: 36px !important;
  color: #fff !important;
}

.avatar-info h3 { font-size: 20px; color: #2c2a26; margin-bottom: 4px; }
.avatar-info p { font-size: 13px; color: #6b6257; }

/* ── 表单区：限制宽度 ── */
.profile-form { max-width: 480px; }

/* 保存按钮：茶青底 */
.save-btn {
  background: #3f5d4a !important;
  border-color: #3f5d4a !important;
  border-radius: 8px !important;
}

/* ── 快捷入口：三列网格卡片 ── */
.quick-links {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-top: 24px;
}

/* 入口卡片：居中文字，hover 上浮变色 */
.quick-card {
  background: #fff;
  border-radius: 12px;
  padding: 28px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.25s;
  box-shadow: 0 2px 12px rgba(61, 50, 39, 0.04);
}

.quick-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(61, 50, 39, 0.1);
  background: #f8faf6;
}

/* 图标 / 标题 / 描述 */
.qc-icon { font-size: 32px; display: block; margin-bottom: 10px; }
.qc-label { display: block; font-size: 15px; font-weight: 600; color: #2c2a26; margin-bottom: 4px; }
.qc-desc { font-size: 12px; color: #6b6257; }
</style>
