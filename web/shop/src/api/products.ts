/**
 * 商品 API 模块
 *
 * 文件作用：封装商城系统中与"商品"相关的后端接口调用，
 *      包括商品列表查询、商品详情查询以及商品类目列表查询。
 * 所属模块：前端 shop 商城项目的 API 请求层（src/api）。
 * 对外导出内容：
 *  - Product：商品数据结构定义（TypeScript 接口）
 *  - Sku：商品 SKU（库存量单位）数据结构定义
 *  - Category：商品类目数据结构定义
 *  - getProducts：分页/条件查询商品列表
 *  - getProductDetail：查询商品详情
 *  - getCategories：查询商品类目列表
 *
 * 说明：本模块基于 src/api/index.ts 的 axios 实例发起请求，
 *      错误信息由响应拦截器统一提示。
 */
import api from './index'

/**
 * 商品（Product）数据结构
 * 对应后端返回的商品主信息，列表中与详情中字段基本一致。
 */
export interface Product {
  /** 商品唯一 id（后端自增主键） */
  id: number
  /** 商品名称 */
  name: string
  /** 商品详细描述 */
  description: string
  /** 所属类目 id */
  category_id: number
  /** 所属类目名称，便于列表直接展示 */
  category_name: string
  /** 商品图片 URL 数组（第一张通常为主图） */
  images: string[]
  /** 商品售价（元） */
  price: number
  /** 累计销量（可选，用于"热销"排序或展示） */
  total_sales?: number
  /** 原价/划线价（可选，用于展示促销折扣） */
  original_price?: number
  /** 推荐理由（可选，用于"为你推荐"卡片展示） */
  reason?: string
  /** 商品状态，如上架/下架（on_sale / off_shelf 等，由后端定义） */
  status: string
  /** 商品创建时间（ISO 字符串） */
  created_at: string
  /** 该商品下的全部 SKU 列表 */
  skus: Sku[]
}

/**
 * 商品 SKU（库存量单位）数据结构
 * 表示商品的具体售卖规格（如颜色、尺码组合）及其库存与价格。
 */
export interface Sku {
  /** SKU 唯一 id */
  id: number
  /** 所属商品 id */
  product_id: number
  /** SKU 名称，例如"红色 / L码" */
  name: string
  /** 该 SKU 的售价（元） */
  price: number
  /** 该 SKU 的库存数量 */
  stock: number
  /** 规格属性键值对，例如 { color: "红色", size: "L" } */
  attrs: Record<string, string>
}

/**
 * 商品类目（Category）数据结构
 * 支持父子层级，用于前台导航与商品筛选。
 */
export interface Category {
  /** 类目唯一 id */
  id: number
  /** 类目名称 */
  name: string
  /** 父类目 id；null 表示顶级类目 */
  parent_id: number | null
  /** 子类目列表（可选，仅查询包含子级时返回） */
  children?: Category[]
}

// 商品列表
/**
 * 查询商品列表
 *
 * 作用：按分页、关键词、类目、价格区间与排序条件查询商品列表，
 *      供商品列表页筛选与搜索使用。
 * 参数：
 *  - params?: {
 *      page?: number          页码（从 1 开始）
 *      page_size?: number     每页条数
 *      keyword?: string       关键词（按商品名称模糊搜索）
 *      category_id?: number   按类目过滤
 *      sort?: string          排序规则（如价格、销量，由后端约定取值）
 *      min_price?: number     最低价格过滤
 *      max_price?: number     最高价格过滤
 *    }
 * 返回值：Axios Promise，响应体 data 中包含商品列表与分页信息
 * 依赖接口：GET /products
 */
export function getProducts(params?: {
  page?: number
  page_size?: number
  keyword?: string
  category_id?: number
  sort?: string
  min_price?: number
  max_price?: number
}) {
  // 将筛选条件以 URL query 参数形式附加到 /products 请求上
  return api.get('/products', { params })
}

// 商品详情
/**
 * 查询商品详情
 *
 * 作用：按商品 id 获取商品完整信息（含描述、图片、SKU 列表等），
 *      供商品详情页渲染使用。
 * 参数：
 *  - id: number 商品 id
 * 返回值：Axios Promise，响应体 data 中携带商品详情对象
 * 依赖接口：GET /products/{id}
 */
export function getProductDetail(id: number) {
  // 将商品 id 拼入 URL 路径，请求 /products/{id} 获取详情
  return api.get(`/products/${id}`)
}

// 为你推荐（协同过滤 + 偏好 + 热销；未登录返回热销兜底）
export function getRecommended(limit = 8) {
  return api.get('/products/recommend', { params: { limit } })
}

// 类目列表
/**
 * 查询商品类目列表
 *
 * 作用：获取全部商品类目（含父子层级），
 *      用于前台导航菜单与商品筛选条件的渲染。
 * 参数：无
 * 返回值：Axios Promise，响应体 data 中携带类目数组
 * 依赖接口：GET /products/categories/all
 */
export function getCategories() {
  // 调用 /products/categories/all 获取全部类目数据
  return api.get('/products/categories/all')
}
