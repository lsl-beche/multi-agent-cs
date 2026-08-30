<!--
  ═══════════════════════════════════════════════════════════
  茗韵茶庄商城 · 全局页面布局组件（ShopLayout.vue）
  ───────────────────────────────────────────────────────────
  职责说明：
    商城所有页面的通用"外壳"布局，由路由配置中的父级路由统一承载：
      1. 顶部导航（header）：品牌 Logo、搜索框、用户菜单/登录注册、购物车入口；
      2. 类目导航（category-nav）：首页 + 各茶叶类目入口；
      3. 主内容区（main）：嵌套 <router-view /> 渲染子页面，带页面切换过渡动画；
      4. 页脚（footer）：品牌文案与版权信息；
      5. 客服悬浮窗（ChatWidget）：固定在右下角的在线客服。
    同时负责登录态初始化：拉取用户信息、购物车数量与类目列表。
  ═══════════════════════════════════════════════════════════
-->
<template>
  <div class="shop-layout">
    <!-- 顶部导航 -->
    <header class="shop-header">
      <div class="shop-container header-top">
        <!-- 品牌 Logo：点击返回首页 -->
        <router-link to="/" class="shop-logo">
          <img src="/seal.svg" alt="茗韵" class="logo-seal" />
          <span class="logo-text">
            <span class="logo-cn">茗韵茶庄</span>
            <span class="logo-en">MINGYUN TEA</span>
          </span>
        </router-link>
        <!-- 全局搜索框：回车或点击搜索按钮跳转到商品列表页并携带 keyword 查询参数 -->
        <div class="header-search">
          <el-input
            v-model="keyword"
            placeholder="搜一搜，茶香自来..."
            clearable
            @keyup.enter="doSearch"
          >
            <template #append>
              <el-button :icon="Search" @click="doSearch" />
            </template>
          </el-input>
        </div>
        <!-- 右侧操作区：登录后展示用户菜单，未登录展示登录/注册入口 -->
        <div class="header-actions">
          <!-- 已登录：我的订单 + 用户下拉菜单（个人中心/收货地址/退出登录） -->
          <template v-if="auth.isLoggedIn()">
            <router-link to="/orders">
              <el-button text>我的订单</el-button>
            </router-link>
            <!-- 用户下拉菜单：通过 command 回调分发菜单指令 -->
            <el-dropdown @command="handleUserCommand">
              <span class="el-dropdown-link">
                {{ auth.user?.username || '用户' }}
                <el-icon><ArrowDown /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                  <el-dropdown-item command="addresses">收货地址</el-dropdown-item>
                  <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <!-- 未登录：登录 / 注册入口 -->
          <template v-else>
            <router-link to="/login">
              <el-button text>登录</el-button>
            </router-link>
            <router-link to="/register">
              <el-button type="primary" size="small">注册</el-button>
            </router-link>
          </template>
          <!-- 购物车入口：右上角红点徽标显示数量，超过 99 显示 99+ -->
          <router-link to="/cart" class="header-cart">
            <el-icon><ShoppingCart /></el-icon>
            <span v-if="cartCount > 0" class="cart-badge">{{ cartCount > 99 ? '99+' : cartCount }}</span>
          </router-link>
        </div>
      </div>
      <!-- 类目导航：首页 + 动态渲染的茶叶类目（高亮当前路由对应项） -->
      <div class="shop-container category-nav">
        <router-link to="/" :class="{ active: route.path === '/' }">首页</router-link>
        <!-- 遍历类目列表生成导航链接，带 category_id 查询参数；根据当前路由查询高亮 -->
        <router-link
          v-for="c in categories"
          :key="c.id"
          :to="`/products?category_id=${c.id}`"
          :class="{ active: route.query.category_id === String(c.id) }"
        >{{ c.name }}</router-link>
      </div>
    </header>

    <!-- 主内容：嵌套路由出口，页面切换时执行淡入淡出 + 位移动画 -->
    <main class="shop-main">
      <transition name="page" mode="out-in">
        <router-view />
      </transition>
    </main>

    <!-- 底部：品牌与版权信息 -->
    <footer class="shop-footer">
      <p class="footer-brand">茗韵茶庄</p>
      <p>一叶知春秋，一盏品人生</p>
      <p>品质保证 · 产地直供 · 匠心制作</p>
      <p style="margin-top:8px; font-size:12px; opacity:0.6">&copy; 2026 茗韵茶庄 All rights reserved.</p>
    </footer>
  </div>

  <!-- 客服悬浮窗：固定在页面右下角，全站可见 -->
  <ChatWidget />
</template>

<script setup lang="ts">
// ── 依赖引入 ──
import { ref, onMounted } from 'vue' // Vue 响应式与生命周期
import { useRouter, useRoute } from 'vue-router' // 路由：编程式导航 + 当前路由信息
import { useAuthStore } from '@/stores/auth' // 用户认证状态仓库
import { useCartStore } from '@/stores/cart' // 购物车状态仓库
import { getCategories, type Category } from '@/api/products' // 获取商品类目列表的 API
import ChatWidget from '@/components/ChatWidget.vue' // 客服悬浮窗组件
import { ShoppingCart, Search, ArrowDown } from '@element-plus/icons-vue' // 顶部导航用到的图标

// ── 状态定义 ──
const router = useRouter() // 路由实例：用于页面跳转
const route = useRoute() // 当前路由对象：读取 path/query 判断高亮
const auth = useAuthStore() // 认证状态：用户信息、登录态判断
const cart = useCartStore() // 购物车状态：读取商品总数

const keyword = ref('') // 搜索框双向绑定的关键词
const categories = ref<Category[]>([]) // 茶叶类目列表（顶部类目导航数据源）
const cartCount = ref(0) // 购物车商品总件数（用于头部徽标展示）

// ── 搜索功能 ──
// 作用：将搜索关键词带入商品列表页；关键词为空时不做跳转
// 参数：无；返回值：无（void）
function doSearch() {
  if (keyword.value.trim()) { // 去除首尾空格后非空才发起搜索
    router.push({ name: 'products', query: { keyword: keyword.value.trim() } }) // 跳转到商品列表页并携带 keyword 参数
  }
}

// ── 用户下拉菜单指令分发 ──
// 作用：根据用户点击的下拉菜单项（command）执行对应操作
// 参数：cmd —— 菜单项指令字符串（'logout' | 'profile' | 'addresses'）；返回值：无
function handleUserCommand(cmd: string) {
  if (cmd === 'logout') { // 退出登录：清除登录态并返回首页
    auth.logout()
    router.push('/')
  } else if (cmd === 'profile') { // 进入个人中心页
    router.push('/profile')
  } else if (cmd === 'addresses') { // 进入收货地址管理页
    router.push('/addresses')
  }
}

// ── 页面挂载后初始化 ──
// 作用：拉取类目列表；若已登录则同步拉取用户资料与购物车数据，更新头部徽标数量
onMounted(async () => {
  try {
    const res = await getCategories() // 请求商品类目列表
    categories.value = res.data.data || [] // 写入类目数据（失败时保持空数组）
  } catch { /* ignore */ } // 类目请求失败静默处理，不影响页面使用
  if (auth.isLoggedIn()) { // 已登录用户：初始化用户信息与购物车
    await auth.fetchProfile() // 拉取最新用户资料
    await cart.fetchCart() // 拉取购物车数据
    cartCount.value = cart.totalCount // 同步购物车总件数到头部徽标
  }
})
</script>

<style scoped>
/* ── 整体布局：纵向 flex，占满视口高度，主内容区弹性撑开将页脚推到底部 ── */
.shop-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

/* ── 主内容区：占据剩余空间 ── */
.shop-main {
  flex: 1;
}

/* ── 顶部用户下拉菜单触发器样式 ── */
.el-dropdown-link {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: #cfc4b0;
}

/* ── Logo 文字区：中英文上下两行排列 ── */
.logo-text {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
}

/* ── Logo 中文名 ── */
.logo-cn {
  font-size: 23px;
  font-weight: 700;
  letter-spacing: 3px;
}
</style>
