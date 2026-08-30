<!--
  ═══════════════════════════════════════════════════════════
  茗韵茶庄商城 · 应用根组件（App.vue）
  ───────────────────────────────────────────────────────────
  职责说明：
    1. 使用 el-config-provider 全局注入 Element Plus 中文语言包，
       使组件内置文案（分页、弹窗按钮、日期等）显示为中文；
    2. 仅放置一个 <router-view />，所有页面均为路由渲染的子页面，
       页面级通用布局（顶部导航/页脚/客服悬浮窗）由 ShopLayout 统一承载。
  ═══════════════════════════════════════════════════════════
-->
<template>
  <!-- Element Plus 全局配置：注入中文 locale，让组件内置文案显示为中文 -->
  <el-config-provider :locale="zhCn">
    <!-- 路由出口：根据当前路由地址渲染对应页面组件 -->
    <router-view />
  </el-config-provider>
</template>

<script setup lang="ts">
// 引入 Element Plus 官方中文语言包（zh-cn.mjs）
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
</script>
