/**
 * ============================================================
 * 模块说明：前端应用入口文件（main.ts）
 *
 * 职责：
 *   - 创建 Vue 应用实例，并依次注册各类插件：
 *       Pinia（状态管理）、Vue Router（路由）、Element Plus（UI 组件库）
 *   - 引入并注册 Element Plus 的全量图标组件（模板中可用 <component :is="图标名"> 使用）
 *   - 引入全局样式：Element Plus 基础样式 + 项目自定义样式
 *   - 将应用挂载到 index.html 中 id 为 app 的 DOM 节点
 *
 * 说明：Element Plus 使用 zh-cn 中文语言包，使内置组件（分页器、日期选择器、
 *       表格空状态等）默认显示中文文案。
 * ============================================================
 */

// Vue 核心：createApp 用于创建应用实例
import { createApp } from 'vue'
// Pinia 状态管理库：createPinia 创建全局状态容器（替代 Vuex）
import { createPinia } from 'pinia'
// Element Plus UI 组件库（表单、表格、弹窗、菜单等业务组件）
import ElementPlus from 'element-plus'
// Element Plus 基础样式文件（需在组件使用前全局引入）
import 'element-plus/dist/index.css'
// Element Plus 中文语言包（使组件内置文案显示为中文）
import zhCn from 'element-plus/es/locale/lang/zh-cn'
// Element Plus 全部图标组件（注册为全局组件后可直接在模板中使用）
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import { PermissionDirective } from '@shared'

// 根组件
import App from './App.vue'
// 路由实例（见 router/index.ts，含全局前置守卫做登录鉴权）
import router from './router'
// 项目全局自定义样式（通用页面容器、工具栏、统计卡片等）
import './styles/index.css'

// 创建 Vue 应用实例（以 App 根组件为入口）
const app = createApp(App)
// 注册 Pinia 状态管理插件（创建全局唯一的状态容器）
app.use(createPinia())
// 注册 Vue Router 插件（启用路由导航能力）
app.use(router)
app.directive('permission', PermissionDirective)
// 注册 Element Plus 插件，并指定中文语言包
app.use(ElementPlus, { locale: zhCn })

// 注册所有 Element Plus 图标
// 将图标库中的每一个图标组件注册为全局组件（key 即组件名，如 User、Lock）
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  // 通过 app.component 注册为全局组件，模板中即可直接用 <User /> 或 <component :is="'User'">
  app.component(key, component)
}

// 将应用挂载到 index.html 中 id 为 app 的 DOM 节点上，开始渲染
app.mount('#app')
