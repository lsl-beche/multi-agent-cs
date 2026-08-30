/**
 * ============================================================
 * 模块说明：Vite 环境类型声明文件（vite-env.d.ts）
 *
 * 职责：
 *   - 引入 Vite 客户端类型声明，使 TypeScript 识别 import.meta.env、
 *     CSS/JSON 等静态资源的模块导入
 *   - 为 .vue 单文件组件补充模块类型声明，使 TypeScript 能够正常
 *     import 以 .vue 结尾的组件文件
 * ============================================================
 */

// Vite 客户端类型引用（提供 import.meta.env、静态资源导入等类型支持）
/// <reference types="vite/client" />

// 声明 .vue 文件模块：让 TypeScript 将 .vue 导入识别为 Vue 组件类型
declare module '*.vue' {
  // 引入 Vue 的泛型组件类型 DefineComponent
  import type { DefineComponent } from 'vue'
  // 导出组件定义（props/events 未约束时使用默认泛型参数，any 兜底）
  const component: DefineComponent<{}, {}, any>
  export default component
}
