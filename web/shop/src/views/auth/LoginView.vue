<!--
  ═══════════════════════════════════════════════════════════
  茗韵茶庄商城 · 登录页（LoginView.vue）
  ───────────────────────────────────────────────────────────
  职责说明：
    提供用户登录表单（用户名 + 密码）：
      1. 表单提交前先通过 Element Plus 校验规则（非空）校验；
      2. 校验通过后调用 auth 仓库的 login() 完成登录；
      3. 登录成功后跳转到 redirect 查询参数指定的页面（默认首页）；
      4. 提供"立即注册"与"返回首页"入口。
    样式复用全局 styles/auth.css（茶山意境分栏布局）。
  ═══════════════════════════════════════════════════════════
-->
<template>
  <div class="shop-container login-page">
    <div class="login-wrapper">
      <!-- 左侧品牌区：品牌 Logo 与标语 -->
      <div class="login-left">
        <div class="brand">
          <span class="brand-icon">🍵</span>
          <h1>茗韵茶庄</h1>
          <p>一盏清茶，品味东方</p>
        </div>
      </div>
      <!-- 右侧表单区：登录表单 -->
      <div class="login-card">
        <h2>欢迎回来</h2>
        <p class="login-sub">登录您的账户</p>
        <!-- 登录表单：提交时触发 handleLogin，带非空校验 -->
        <el-form ref="formRef" :model="form" :rules="rules" label-width="0" size="large" @submit.prevent="handleLogin">
          <!-- 用户名输入框（带用户图标前缀） -->
          <el-form-item prop="username">
            <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" />
          </el-form-item>
          <!-- 密码输入框（带锁图标前缀，可切换明文） -->
          <el-form-item prop="password">
            <el-input v-model="form.password" type="password" placeholder="密码" :prefix-icon="Lock" show-password />
          </el-form-item>
          <!-- 提交按钮：提交期间显示 loading -->
          <el-form-item>
            <el-button type="primary" native-type="submit" :loading="loading" class="submit-btn">登录</el-button>
          </el-form-item>
        </el-form>
        <!-- 注册入口 -->
        <div class="login-footer">
          还没有账号？<router-link to="/register"><span class="link">立即注册</span></router-link>
        </div>
        <!-- 返回首页入口 -->
        <div class="back-home">
          <router-link to="/">← 返回首页</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// ── 依赖引入 ──
import { ref, reactive } from 'vue' // Vue 响应式：ref（引用值）/ reactive（对象）
import { useRouter, useRoute } from 'vue-router' // 路由：跳转 + 读取重定向参数
import { useAuthStore } from '@/stores/auth' // 认证状态仓库（login 方法）
import { ElMessage } from 'element-plus' // 消息提示
import { User, Lock } from '@element-plus/icons-vue' // 表单输入框前缀图标

// ── 状态定义 ──
const router = useRouter() // 路由实例：用于登录成功后跳转
const route = useRoute() // 当前路由：读取 ?redirect= 参数实现登录后回跳
const auth = useAuthStore() // 认证仓库：调用登录接口、管理登录态
const formRef = ref() // 表单组件引用：用于触发 validate 校验
const loading = ref(false) // 登录请求进行中标记（控制按钮 loading）
const form = reactive({ username: '123', password: '123456' }) // 登录表单数据（username/password，带默认演示值）
// 表单校验规则：用户名与密码均为必填，失焦（blur）时校验
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

// ── 登录提交 ──
// 作用：校验表单 → 调用登录接口 → 成功提示并跳转（支持 redirect 回跳）
// 参数：无；返回值：Promise<void>
async function handleLogin() {
  const valid = await formRef.value.validate().catch(() => false) // 校验失败时返回 false
  if (!valid) return // 校验未通过则中止
  loading.value = true // 进入请求中状态
  try {
    await auth.login(form) // 调用认证仓库的登录方法（内部处理 token 存储）
    ElMessage.success('登录成功') // 登录成功提示
    router.push((route.query.redirect as string) || '/') // 优先跳转登录前页面，否则回首页
  } catch { /* handled */ } finally { loading.value = false } // 失败提示由仓库内拦截器统一处理；最终复位 loading
}
</script>

<style src="../../styles/auth.css"></style>
