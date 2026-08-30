/**
 * Vue Router 路由配置模块
 *
 * 文件作用：定义 shop 商城前端的所有路由（含嵌套布局路由、懒加载组件
 *      与页面标题元信息），并通过全局前置守卫完成页面标题设置
 *      与"需登录页面"的登录鉴权拦截。
 * 所属模块：前端 shop 商城项目的路由层（src/router）。
 * 对外导出内容：
 *  - 默认导出：配置完成并挂载了全局守卫的 router 实例
 *    （在 main.ts 中注册到 Vue 应用）
 *
 * 说明：
 *  - 除登录/注册页外，其余页面均嵌套在 ShopLayout 布局组件下；
 *  - 涉及个人操作的路由通过 meta.requiresAuth 标记，由守卫统一拦截。
 */
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// 创建路由实例（使用 HTML5 History 模式，URL 中不携带 #）
const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      // 商城主布局路由：路径前缀为根路径，子路由渲染在 ShopLayout 布局内
      path: '/',
      // 懒加载布局组件：仅首次访问时才加载 ShopLayout.vue
      component: () => import('@/components/ShopLayout.vue'),
      children: [
        // 首页（空子路径，访问 / 时命中）
        { path: '', name: 'home', component: () => import('@/views/home/HomeView.vue'), meta: { title: '首页' } },
        // 商品列表页（支持关键词搜索与筛选）
        { path: 'products', name: 'products', component: () => import('@/views/product/ProductListView.vue'), meta: { title: '商品列表' } },
        // 商品详情页（:id 为商品 id 动态参数）
        { path: 'product/:id', name: 'product-detail', component: () => import('@/views/product/ProductDetailView.vue'), meta: { title: '商品详情' } },
        // 购物车页（需登录）
        { path: 'cart', name: 'cart', component: () => import('@/views/cart/CartView.vue'), meta: { title: '购物车', requiresAuth: true } },
        // 提交订单页（需登录）
        { path: 'checkout', name: 'checkout', component: () => import('@/views/checkout/CheckoutView.vue'), meta: { title: '提交订单', requiresAuth: true } },
        // 确认支付页（:orderId 为订单 id 动态参数，需登录）
        { path: 'pay/:orderId', name: 'pay', component: () => import('@/views/checkout/PayView.vue'), meta: { title: '确认支付', requiresAuth: true } },
        // 我的订单列表页（需登录）
        { path: 'orders', name: 'orders', component: () => import('@/views/order/OrderListView.vue'), meta: { title: '我的订单', requiresAuth: true } },
        // 订单详情页（:id 为订单 id 动态参数，需登录）
        { path: 'order/:id', name: 'order-detail', component: () => import('@/views/order/OrderDetailView.vue'), meta: { title: '订单详情', requiresAuth: true } },
        // 个人中心页（需登录）
        { path: 'profile', name: 'profile', component: () => import('@/views/user/ProfileView.vue'), meta: { title: '个人中心', requiresAuth: true } },
        // 收货地址管理页（需登录）
        { path: 'addresses', name: 'addresses', component: () => import('@/views/user/AddressView.vue'), meta: { title: '收货地址', requiresAuth: true } },
        // 我的优惠券页（需登录）
        { path: 'coupons', name: 'coupons', component: () => import('@/views/coupon/CouponListView.vue'), meta: { title: '我的优惠券', requiresAuth: true } },
      ],
    },
    {
      // 登录页（独立于主布局渲染）
      path: '/login',
      name: 'login',
      component: () => import('@/views/auth/LoginView.vue'),
      meta: { title: '登录' },
    },
    {
      // 注册页（独立于主布局渲染）
      path: '/register',
      name: 'register',
      component: () => import('@/views/auth/RegisterView.vue'),
      meta: { title: '注册' },
    },
  ],
})

// 全局前置守卫：每次路由跳转前执行，负责设置页面标题与登录鉴权
router.beforeEach((to, _from, next) => {
  // 依据路由 meta.title 动态设置浏览器标签页标题，缺省使用商城默认名称
  document.title = (to.meta.title as string) || 'CSagent 商城'
  // 获取认证 Store 以判断当前登录状态
  const auth = useAuthStore()
  // 目标路由要求登录但当前未登录时，拦截并跳转到登录页
  if (to.meta.requiresAuth && !auth.isLoggedIn()) {
    // 携带 redirect 参数记录来源地址，登录成功后便于跳回原页面
    next({ name: 'login', query: { redirect: to.fullPath } })
  } else {
    // 已登录或目标页无需登录时放行
    next()
  }
})

export default router
