<!--
 * ============================================================
 * 模块说明：登录页（views/login/LoginView.vue）
 *
 * 职责：
 *   - 提供管理员登录表单（用户名 + 密码），支持回车提交
 *   - 登录成功后调用 auth Store 的 login（内部完成 token 持久化、
 *     用户信息拉取），并跳转到数据看板 /dashboard
 *   - 登录按钮带 loading 状态，防止重复提交
 *
 * 说明：
 *   - 该路由在 router 中标记 noAuth，无需登录即可访问；
 *     已登录用户访问时会被路由守卫自动重定向到 /dashboard
 *   - 默认账号：admin / admin123（开发演示用）
 * ============================================================
 -->
<script setup lang="ts">
// Vue 响应式工具：reactive 创建对象型响应式数据、ref 创建基础类型响应式数据
import { reactive, ref } from 'vue'
// Vue Router：useRouter 获取路由实例（登录成功后跳转）
import { useRouter } from 'vue-router'
// 认证状态管理：调用 login 完成登录动作
import { useAuthStore } from '@/stores/auth'

// 路由实例（登录成功后跳转到数据看板）
const router = useRouter()
// 认证 Store 实例（调用 login 方法）
const auth = useAuthStore()
// 登录按钮加载状态：提交中为 true，按钮显示 loading 并禁用（防止重复提交）
const loading = ref(false)

/**
 * 登录表单数据
 * 初始填充默认演示账号（admin / admin123），便于开发调试
 */
const form = reactive({ username: 'admin', password: 'admin123' })
/**
 * 表单校验规则（Element Plus 表单校验）
 * - username: 必填，失焦时校验
 * - password: 必填，失焦时校验
 */
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

// 登录表单组件引用（用于调用表单实例的 validate 方法做整体校验）
const formRef = ref()

/**
 * 登录提交处理函数（异步）
 * 流程：整体表单校验 → 开启 loading → 调用 auth.login →
 *       成功跳转 /dashboard → finally 中关闭 loading
 * @returns {Promise<void>} 校验失败会抛出异常，由 Element Plus 表单拦截
 */
async function handleSubmit() {
  // 触发表单整体校验（任一必填项为空则在此抛错，不继续执行）
  await formRef.value.validate()
  // 开启按钮 loading，防止重复提交
  loading.value = true
  try {
    // 调用认证 Store 的登录动作（内部完成 token 持久化与用户信息拉取）
    await auth.login(form.username, form.password)
    // 登录成功：跳转到数据看板
    router.push('/dashboard')
  } finally {
    // 无论成功失败，最终都关闭 loading
    loading.value = false
  }
}
</script>

<template>
  <!-- 登录页根容器：全屏渐变背景，用于居中承载登录卡片 -->
  <div class="login-page">
    <!-- 登录卡片：标题 + 登录表单 + 默认账号提示 -->
    <div class="login-card">
      <!-- 系统名称标题 -->
      <h2 class="title">CSagent 管理后台</h2>
      <!-- 系统副标题说明 -->
      <p class="subtitle">电商平台管理系统</p>
      <!-- 登录表单：绑定表单数据与校验规则，回车键可直接触发登录 -->
      <el-form ref="formRef" :model="form" :rules="rules" size="large" @keyup.enter="handleSubmit">
        <!-- 用户名输入项（必填校验，回车/点击登录时触发） -->
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" prefix-icon="User" />
        </el-form-item>
        <!-- 密码输入项（必填校验，带显示/隐藏切换） -->
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码" prefix-icon="Lock" show-password />
        </el-form-item>
        <!-- 登录按钮：loading 状态防止重复提交，点击触发 handleSubmit -->
        <el-form-item>
          <el-button type="primary" :loading="loading" style="width:100%" @click="handleSubmit">登 录</el-button>
        </el-form-item>
      </el-form>
      <!-- 默认账号提示（开发演示用） -->
      <p class="hint">默认账号: admin / admin123</p>
    </div>
  </div>
</template>

<style scoped>
/* ---------- 登录页整体 ---------- */
/* 全屏铺底：垂直水平居中，使用渐变背景（紫蓝色）营造品牌氛围 */
.login-page { height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
/* 登录卡片：白底圆角卡片，带深色投影突出层次感 */
.login-card { width: 400px; padding: 40px; background: #fff; border-radius: 12px; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
/* 标题：居中大号深色字 */
.title { text-align: center; font-size: 24px; color: #303133; margin-bottom: 4px; }
/* 副标题：居中灰色小号字 */
.subtitle { text-align: center; font-size: 13px; color: #909399; margin-bottom: 32px; }
/* 底部提示：默认账号说明，浅灰色 */
.hint { text-align: center; font-size: 12px; color: #c0c4cc; margin-top: 16px; }
</style>
