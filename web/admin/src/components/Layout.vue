<!--
 * ============================================================
 * 模块说明：后台整体布局组件（components/Layout.vue）
 *
 * 职责：
 *   - 搭建后台管理系统的整体页面框架：
 *       ├─ 左侧：Logo + 侧边导航菜单（支持折叠）
 *       ├─ 顶部：折叠按钮 + 当前页面标题 + 用户角色/用户名 + 退出按钮
 *       └─ 中间：内容区（嵌套 router-view 渲染各业务页面）
 *   - 菜单项由 menuItems 数组驱动，点击菜单通过路由跳转切换页面
 *   - 通过 auth Store 展示当前登录用户信息，并支持退出登录
 *
 * 使用位置：App.vue 在用户已登录时渲染本组件
 * ============================================================
 -->
<script setup lang="ts">
// Vue 响应式工具：ref 创建响应式状态、computed 创建计算属性
import { ref, computed } from 'vue'
// Vue Router 组合式 API：useRoute 读取当前路由、useRouter 获取路由实例（用于跳转）
import { useRoute, useRouter } from 'vue-router'
// 认证状态管理：用于获取当前用户信息与执行退出登录
import { useAuthStore } from '@/stores/auth'

// 当前路由对象（读取 meta.title 展示页面标题、path 用于菜单高亮）
const route = useRoute()
// 路由实例（菜单跳转、退出后跳转登录页）
const router = useRouter()
// 认证 Store 实例（读取用户角色/用户名、调用 logout）
const auth = useAuthStore()
// 侧边栏是否折叠（true 时仅显示图标，宽度收窄为 64px）
const isCollapse = ref(false)

/**
 * 侧边菜单配置列表
 * 每项包含：
 *  - path:  路由路径（点击菜单后的跳转目标，同时作为菜单高亮 index）
 *  - title: 菜单显示名称
 *  - icon:  Element Plus 图标组件名（已在 main.ts 全局注册，用 <component :is> 渲染）
 */
const menuItems = [
  { path: '/dashboard', title: '数据看板', icon: 'DataAnalysis' },
  { path: '/products', title: '商品管理', icon: 'Goods' },
  { path: '/orders', title: '订单管理', icon: 'Document' },
  { path: '/users', title: '用户管理', icon: 'User' },
  { path: '/inventory', title: '库存管理', icon: 'Box' },
  { path: '/marketing', title: '营销中心', icon: 'Present' },
  { path: '/reviews', title: '评价管理', icon: 'Star' },
  { path: '/payments', title: '支付管理', icon: 'Money' },
  { path: '/shipments', title: '物流管理', icon: 'Van' },
  { path: '/reports', title: '客服看板', icon: 'Monitor' },
  { path: '/agents', title: 'AI Agent', icon: 'Cpu' },
  { path: '/openapi', title: '开放平台', icon: 'Link' },
  { path: '/tickets', title: '客服工单', icon: 'Headset' },
  { path: '/logs', title: '操作日志', icon: 'Notebook' },
]

/**
 * 当前激活菜单（计算属性）
 * 直接取当前路由路径，与菜单项的 index 一一对应，
 * 实现路由切换/页面刷新后菜单高亮自动跟随
 * @returns {string} 当前路由的完整路径，如 '/dashboard'
 */
const activeMenu = computed(() => route.path)

/**
 * 菜单点击处理函数
 * 根据被点击菜单项的 index（即路由路径）进行路由跳转
 * @param path 被点击菜单项的 index 值
 */
function handleSelect(path: string) {
  router.push(path)
}

/**
 * 退出登录处理函数
 * 调用 auth Store 清理登录态（token、用户信息、localStorage），
 * 并跳转到登录页
 */
function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <!-- 整体布局容器（左右结构：左侧侧边栏 + 右侧主体区） -->
  <el-container class="layout">
    <!-- 左侧侧边栏：宽度随折叠状态切换（折叠 64px / 展开 220px） -->
    <el-aside :width="isCollapse ? '64px' : '220px'" class="aside">
      <!-- Logo 区：咖啡图标 + 系统名称（折叠时隐藏文字） -->
      <div class="logo">
        <el-icon :size="24"><Coffee /></el-icon>
        <span v-show="!isCollapse" class="logo-text">CSagent</span>
      </div>

      <!-- 侧边导航菜单：高亮跟随当前路由，点击菜单触发路由跳转 -->
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :collapse-transition="false"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        @select="handleSelect"
      >
        <!-- 遍历菜单配置渲染菜单项：图标 + 标题 -->
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 右侧主体区域（纵向排列：顶栏 + 内容区） -->
    <el-container>
      <!-- 顶部栏：左侧为折叠按钮与页面标题，右侧为当前用户信息与退出按钮 -->
      <el-header class="header">
        <!-- 左侧：折叠/展开按钮 + 当前页面标题 -->
        <div class="header-left">
          <!-- 折叠按钮：点击切换 isCollapse，图标随折叠状态切换（Fold/Expand） -->
          <el-icon class="collapse-btn" :size="20" @click="isCollapse = !isCollapse">
            <Fold v-if="!isCollapse" /><Expand v-else />
          </el-icon>
          <!-- 当前页面标题：取自路由 meta.title -->
          <span class="page-title">{{ route.meta.title }}</span>
        </div>
        <!-- 右侧：角色标签 + 用户名 + 退出按钮 -->
        <div class="header-right">
          <!-- 当前用户角色标签（如 super_admin / admin / viewer） -->
          <el-tag type="info" size="small">{{ auth.user?.role || '' }}</el-tag>
          <!-- 当前登录用户名 -->
          <span class="username">{{ auth.user?.username || '' }}</span>
          <!-- 退出登录按钮 -->
          <el-button text @click="handleLogout">退出</el-button>
        </div>
      </el-header>

      <!-- 内容区：渲染当前路由对应的业务页面 -->
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
/* ---------- 布局与侧边栏 ---------- */
/* 整体布局容器：占满整个视口高度 */
.layout { height: 100vh; }
/* 侧边栏：深色背景，隐藏溢出内容 */
.aside { background-color: #304156; overflow: hidden; }
/* Logo 区：垂直水平居中，白色文字，折叠时文字不换行 */
.logo { height: 60px; display: flex; align-items: center; justify-content: center; gap: 8px; color: #fff; font-size: 18px; font-weight: 700; white-space: nowrap; }
/* Logo 文字：字距微调 */
.logo-text { letter-spacing: 1px; }

/* ---------- 顶部栏 ---------- */
/* 顶部栏：白底、左右两端布局、底部细分割线 */
.header { background: #fff; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e4e7ed; padding: 0 20px; }
/* 顶部栏左侧（折叠按钮 + 页面标题） */
.header-left { display: flex; align-items: center; gap: 12px; }
/* 折叠按钮：手型光标提示可点击 */
.collapse-btn { cursor: pointer; }
/* 页面标题文字 */
.page-title { font-size: 16px; font-weight: 500; }
/* 顶部栏右侧（用户信息 + 退出按钮） */
.header-right { display: flex; align-items: center; gap: 12px; }
/* 用户名文字颜色 */
.username { color: #606266; }

/* ---------- 内容区 ---------- */
/* 内容区：浅灰背景 + 内边距 */
.main { background-color: #f0f2f5; padding: 20px; }
</style>
