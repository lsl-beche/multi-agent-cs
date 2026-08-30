<!--
  ═══════════════════════════════════════════════════════════
  茗韵茶庄商城 · 注册页（RegisterView.vue）
  ───────────────────────────────────────────────────────────
  职责说明：
    提供用户注册表单（用户名 + 密码 + 确认密码）：
      1. 用户名 3~20 位必填、密码至少 6 位必填；
      2. 自定义校验器 validatePass 校验两次密码一致性；
      3. 校验通过后调用 auth 仓库的 register() 完成注册；
      4. 注册成功后提示并跳转首页；
      5. 提供"立即登录"与"返回首页"入口。
    样式复用全局 styles/auth.css（茶山意境分栏布局）。
  ═══════════════════════════════════════════════════════════
-->
<template>
  <div class="login-page">
    <div class="login-wrapper">
      <!-- 左侧品牌区：品牌 Logo 与标语 -->
      <div class="login-left">
        <div class="brand">
          <span class="brand-icon">🍵</span>
          <h1>茗韵茶庄</h1>
          <p>加入我们，开启品茶之旅</p>
        </div>
      </div>
      <!-- 右侧表单区：注册表单 -->
      <div class="login-card">
        <h2>创建账号</h2>
        <p class="login-sub">注册成为会员</p>
        <!-- 注册表单：提交时触发 handleRegister，带规则校验与密码一致性校验 -->
        <el-form ref="formRef" :model="form" :rules="rules" label-width="0" size="large" @submit.prevent="handleRegister">
          <!-- 用户名输入框 -->
          <el-form-item prop="username">
            <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" />
          </el-form-item>
          <!-- 密码输入框 -->
          <el-form-item prop="password">
            <el-input v-model="form.password" type="password" placeholder="密码" :prefix-icon="Lock" show-password />
          </el-form-item>
          <!-- 确认密码输入框：与密码一致性由 validatePass 校验 -->
          <el-form-item prop="confirmPassword">
            <el-input v-model="form.confirmPassword" type="password" placeholder="确认密码" show-password />
          </el-form-item>
          <!-- 提交按钮：提交期间显示 loading -->
          <el-form-item>
            <el-button type="primary" native-type="submit" :loading="loading" class="submit-btn">注册</el-button>
          </el-form-item>
        </el-form>
        <!-- 登录入口 -->
        <div class="login-footer">
          已有账号？<router-link to="/login"><span class="link">立即登录</span></router-link>
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
import { ref, reactive } from 'vue' // Vue 响应式：ref / reactive
import { useRouter } from 'vue-router' // 路由：注册成功后跳转首页
import { useAuthStore } from '@/stores/auth' // 认证状态仓库（register 方法）
import { ElMessage } from 'element-plus' // 消息提示
import { User, Lock } from '@element-plus/icons-vue' // 输入框前缀图标

// ── 状态定义 ──
const router = useRouter() // 路由实例
const auth = useAuthStore() // 认证仓库：调用注册接口
const formRef = ref() // 表单组件引用：用于触发 validate 校验
const loading = ref(false) // 注册请求进行中标记
const form = reactive({
  username: '', password: '', confirmPassword: '', // 注册表单：用户名/密码/确认密码
})

// ── 密码一致性自定义校验器 ──
// 作用：比对确认密码与密码是否一致，不一致则返回错误信息
// 参数：_ —— 未使用的 rule 占位；value —— 当前输入值（确认密码）；
//       cb —— Element Plus 校验回调（传入 Error 表示校验失败，undefined 表示通过）
const validatePass = (_: any, value: string, cb: any) => {
  cb(value !== form.password ? new Error('两次密码不一致') : undefined)
}

// ── 表单校验规则 ──
// 用户名：必填且长度 3~20 位；密码：必填且至少 6 位；
// 确认密码：必填 + 一致性校验（validatePass）
const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度 3-20 位', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validatePass, trigger: 'blur' },
  ],
}

// ── 注册提交 ──
// 作用：校验表单 → 调用注册接口 → 成功提示并跳转首页
// 参数：无；返回值：Promise<void>
async function handleRegister() {
  const valid = await formRef.value.validate().catch(() => false) // 校验失败返回 false
  if (!valid) return // 校验未通过则中止
  loading.value = true // 进入请求中状态
  try {
    await auth.register({ username: form.username, password: form.password }) // 仅提交用户名与密码，确认密码不提交
    ElMessage.success('注册成功，欢迎加入茗韵茶庄！')
    router.push('/') // 注册成功后回首页（登录态由仓库内部处理）
  } catch { /* handled */ } finally { loading.value = false } // 失败提示由拦截器统一处理；最终复位 loading
}
</script>

<style src="../../styles/auth.css"></style>
