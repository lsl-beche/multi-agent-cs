<!--
 * ============================================================
 * 模块说明：应用根组件（App.vue）
 *
 * 职责：
 *   - 作为整个后台管理系统的根组件，承载顶层路由出口（router-view）
 *   - 根据登录状态（Pinia 认证 Store 中的 token）在「登录页」与「后台布局」之间切换：
 *       ├─ 未登录（无 token）→ 仅渲染路由出口，此时当前路由即为登录页
 *       └─ 已登录（有 token）→ 渲染整体布局组件 Layout，由 Layout 内部的
 *          嵌套路由出口再渲染各业务管理页面
 *
 * 依赖：
 *   - @/stores/auth：Pinia 认证状态管理（token、用户信息等）
 *   - @/components/Layout.vue：后台整体布局（左侧菜单栏 + 顶部栏 + 内容区）
 * ============================================================
 -->
<script setup lang="ts">
// 引入认证状态管理 Store（通过 auth.token 判断登录态，驱动根组件切换视图）
import { useAuthStore } from '@/stores/auth'
// 引入后台整体布局组件（登录后展示的框架：侧边栏 + 顶栏 + 内容区）
import Layout from '@/components/Layout.vue'

// 创建认证 Store 实例，供模板中读取 token 判断当前是否已登录
const auth = useAuthStore()
</script>

<template>
  <!-- 未登录（auth.token 为空）：仅渲染路由出口，展示登录页等无需鉴权的页面 -->
  <router-view v-if="!auth.token" />
  <!-- 已登录（auth.token 非空）：渲染后台整体布局，内部通过嵌套路由出口展示各业务页面 -->
  <Layout v-else />
</template>
