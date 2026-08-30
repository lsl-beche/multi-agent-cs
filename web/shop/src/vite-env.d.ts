/**
 * ═══════════════════════════════════════════════════════════
 * Vite 环境类型声明文件（vite-env.d.ts）
 * ───────────────────────────────────────────────────────────
 * 职责说明：
 *   1. 引入 Vite 客户端类型（import.meta.env、静态资源导入类型等）；
 *   2. 为 "*.vue" 模块补充模块声明，使 TypeScript 能正确识别
 *      .vue 单文件组件的导入（默认导出 Vue 组件）；
 *   3. 声明 Element Plus 中文语言包模块（无类型定义，直接声明为 any）。
 * ═══════════════════════════════════════════════════════════
 */
/// <reference types="vite/client" />

// 为所有 .vue 单文件组件声明模块类型：TS 在 import xxx from '*.vue' 时
// 不再报"找不到模块"，且默认导出被识别为 Vue 组件
declare module '*.vue' {
  import type { DefineComponent } from 'vue' // Vue 组件类型定义
  // 泛型参数含义：组件 props / 普通事件 / 其他（此处放宽为 any 以兼容各类组件）
  const component: DefineComponent<{}, {}, any>
  export default component // .vue 文件默认导出一个 Vue 组件
}

// Element Plus 中文语言包是 .mjs 文件且无配套类型声明，这里显式声明该模块，
// 避免在 App.vue 中 import 时报 TS 类型错误
declare module 'element-plus/dist/locale/zh-cn.mjs'
