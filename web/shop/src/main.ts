import { createApp } from 'vue'
import { createPinia } from 'pinia'
import {
  ElAvatar,
  ElButton,
  ElCheckbox,
  ElCol,
  ElConfigProvider,
  ElDialog,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElIcon,
  ElImage,
  ElInput,
  ElInputNumber,
  ElLoading,
  ElPagination,
  ElRadioButton,
  ElRadioGroup,
  ElRow,
  ElTag,
} from 'element-plus'
import { ArrowDown, EditPen, Lock, Promotion, Search, ShoppingCart, User } from '@element-plus/icons-vue'
import { PermissionDirective } from '@shared'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import '@/styles/index.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.directive('permission', PermissionDirective)

// 全局错误处理（ErrorBoundary 语义）：组件渲染/事件异常统一记录，
// 避免未捕获异常导致白屏且无日志
app.config.errorHandler = (err, _instance, info) => {
  console.error('[app error]', info, err)
}
app.config.warnHandler = (msg) => {
  if (import.meta.env.DEV) console.warn('[app warn]', msg)
}

// 按需注册 Element Plus 组件（替代全量引入，显著减小首包体积）
const epComponents = [
  ElAvatar, ElButton, ElCheckbox, ElCol, ElConfigProvider, ElDialog,
  ElDropdown, ElDropdownItem, ElDropdownMenu, ElEmpty, ElForm, ElFormItem,
  ElIcon, ElImage, ElInput, ElInputNumber, ElPagination, ElRadioButton,
  ElRadioGroup, ElRow, ElTag,
]
// 直接用 app.component 注册：本版本部分组件（如 ElRadioButton/ElRadioGroup）
// 的 install 是空函数，app.use 不会生效
epComponents.forEach((c) => app.component(c.name!, c)) // 遍历组件数组并逐个全局注册
app.use(ElLoading) // v-loading 指令

// 仅注册实际用到的图标
const icons = { ArrowDown, EditPen, Lock, Promotion, Search, ShoppingCart, User }
for (const [key, component] of Object.entries(icons)) {
  app.component(key, component) // 将图标按名称注册为全局组件，模板中可直接 <el-icon><Search /></el-icon> 使用
}

// 挂载应用到 HTML 中 id 为 "app" 的根节点
app.mount('#app')
