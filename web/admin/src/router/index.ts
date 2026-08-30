/**
 * ============================================================
 * 模块说明：前端路由配置（router/index.ts）
 *
 * 职责：
 *   - 定义后台管理系统的完整路由表（登录页 + 各业务模块页面）
 *   - 创建 Vue Router 实例（HTML5 History 模式，URL 不带 #，需后端回退到 index.html）
 *   - 注册全局前置守卫（beforeEach）：
 *       1) 依据路由 meta.title 动态设置浏览器标签页标题
 *       2) 登录鉴权：未登录访问受保护页面 → 重定向到 /login
 *       3) 已登录访问登录页 → 自动跳回 /dashboard
 *
 * 路由与页面模块对应关系：
 *   /login 登录页 | /dashboard 数据看板 | /products 商品管理 | /orders 订单管理
 *   /users 用户管理 | /inventory 库存管理 | /marketing 营销中心 | /reviews 评价管理
 *   /reports 客服看板 | /payments 支付管理 | /shipments 物流管理 | /logs 操作日志
 *   /tickets 客服工单
 *
 * 说明：所有业务页面均使用懒加载（() => import(...)），按需分包加载，减小首屏体积。
 * ============================================================
 */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { adminTokenStorage } from '@shared'

/**
 * 路由表定义
 * 约定：
 *  - meta.noAuth = true：该路由无需登录即可访问（当前仅登录页）
 *  - meta.title：页面标题，用于浏览器标签页与顶部栏展示
 */
const routes: RouteRecordRaw[] = [
  // 登录页：无需鉴权；已登录用户访问会被守卫重定向到 /dashboard
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/LoginView.vue'),
    meta: { title: '登录', noAuth: true },
  },
  // 根路径：直接重定向到数据看板
  {
    path: '/',
    redirect: '/dashboard',
  },
  // 数据看板：近 7 日订单/销售额等核心指标与图表
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/dashboard/DashboardView.vue'),
    meta: { title: '数据看板' },
  },
  // 商品管理：商品列表、新增/编辑（含规格 SKU 生成）、上下架、类目管理
  {
    path: '/products',
    name: 'Products',
    component: () => import('@/views/products/ProductsView.vue'),
    meta: { title: '商品管理' },
  },
  // 订单管理：订单列表、状态流转（确认/发货/取消/完成）、订单详情时间线
  {
    path: '/orders',
    name: 'Orders',
    component: () => import('@/views/orders/OrdersView.vue'),
    meta: { title: '订单管理' },
  },
  // 用户管理：用户列表、新增/编辑、封禁/解封、收货地址查看
  {
    path: '/users',
    name: 'Users',
    component: () => import('@/views/users/UsersView.vue'),
    meta: { title: '用户管理' },
  },
  // 库存管理：库存列表、低库存预警、库存调整与流水
  {
    path: '/inventory',
    name: 'Inventory',
    component: () => import('@/views/inventory/InventoryView.vue'),
    meta: { title: '库存管理' },
  },
  // 营销中心：优惠券创建/发放/停用、促销活动创建
  {
    path: '/marketing',
    name: 'Marketing',
    component: () => import('@/views/marketing/MarketingView.vue'),
    meta: { title: '营销中心' },
  },
  // 评价管理：商品评价审核（通过/驳回）与商家回复
  {
    path: '/reviews',
    name: 'Reviews',
    component: () => import('@/views/reviews/ReviewsView.vue'),
    meta: { title: '评价管理' },
  },
  // 客服看板：CSAT 满意度、会话/工单统计大屏
  {
    path: '/reports',
    name: 'Reports',
    component: () => import('@/views/reports/ReportsView.vue'),
    meta: { title: '客服看板' },
  },
  // 支付管理：支付流水查询、退款审批（通过/驳回）
  {
    path: '/payments',
    name: 'Payments',
    component: () => import('@/views/payments/PaymentsView.vue'),
    meta: { title: '支付管理' },
  },
  // 物流管理：物流单列表、更新物流轨迹、物流详情
  {
    path: '/shipments',
    name: 'Shipments',
    component: () => import('@/views/shipments/ShipmentsView.vue'),
    meta: { title: '物流管理' },
  },
  // 操作日志：按模块/操作人/时间检索的后台操作审计日志
  {
    path: '/logs',
    name: 'Logs',
    component: () => import('@/views/logs/OperationLogsView.vue'),
    meta: { title: '操作日志' },
  },
  // 客服工单：工单认领、客服与用户实时对话（WebSocket）
  {
    path: '/tickets',
    name: 'Tickets',
    component: () => import('@/views/tickets/TicketsView.vue'),
    meta: { title: '客服工单' },
  },
]

// 创建路由实例：使用 HTML5 History 模式（URL 中不含 #，需服务端配置回退到 index.html）
const router = createRouter({
  history: createWebHistory(),
  routes,
})

/**
 * 全局前置守卫（beforeEach）：在每次路由跳转前执行
 * 职责：
 *   1) 根据路由 meta.title 设置浏览器标签页标题，缺省使用 'CSagent 管理后台'
 *   2) 鉴权控制：
 *      - 访问 noAuth 页面（登录页）：
 *          已登录 → 重定向到 /dashboard（避免重复登录）
 *          未登录 → 放行，进入登录页
 *      - 访问受保护页面：未登录 → 重定向到 /login；已登录 → 放行
 * @param to     目标路由对象（含 meta、path 等）
 * @param _from  来源路由对象（此处未使用，下划线前缀表示有意省略）
 * @param next   路由放行 / 重定向函数
 */
router.beforeEach((to, _from, next) => {
  const token = adminTokenStorage.accessToken
  // 动态设置浏览器标签页标题：优先使用路由 meta.title，缺省用后台名称
  document.title = (to.meta.title as string) || 'CSagent 管理后台'

  // 无需鉴权的页面（如登录页）
  if (to.meta.noAuth) {
    // 已登录用户访问登录页 → 直接跳转到数据看板
    if (token) return next('/dashboard')
    // 未登录 → 正常放行进入登录页
    return next()
  }

  // 受保护页面：未登录 → 重定向到登录页
  if (!token) return next('/login')
  // 已登录 → 放行，继续本次导航
  next()
})

// 导出路由实例，供 main.ts 注册到 Vue 应用
export default router
