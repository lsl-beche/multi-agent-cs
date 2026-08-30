/**
 * 订单 API 模块
 *
 * 文件作用：封装商城系统中与"订单"相关的后端接口调用，
 *      包括创建订单、订单列表、订单详情、取消订单与确认收货等操作。
 * 所属模块：前端 shop 商城项目的 API 请求层（src/api）。
 * 对外导出内容：
 *  - OrderItem：订单条目数据结构定义
 *  - Order：订单主数据结构定义
 *  - OrderAddress：订单收货地址数据结构定义
 *  - createOrder：创建订单
 *  - getOrders：分页/按状态查询订单列表
 *  - getOrderDetail：查询订单详情
 *  - cancelOrder：取消订单
 *  - confirmOrder：确认收货
 *
 * 说明：本模块基于 src/api/index.ts 的 axios 实例发起请求，
 *      错误信息由响应拦截器统一提示。
 */
import api from './index'

/**
 * 订单条目（OrderItem）数据结构
 * 表示订单中单件商品的快照信息（下单时的价格与名称）。
 */
export interface OrderItem {
  /** 订单条目唯一 id */
  id: number
  /** 商品 id */
  product_id: number
  /** 商品名称（下单时快照） */
  product_name: string
  /** SKU 名称，例如"黑色 / M码" */
  sku_name: string
  /** 下单时的成交单价（元） */
  price: number
  /** 购买数量 */
  quantity: number
  /** 商品主图 URL */
  image: string
}

/**
 * 订单（Order）主数据结构
 * 对应后端返回的订单主体信息，包含状态、金额、条目与时间节点。
 */
export interface Order {
  /** 订单记录唯一 id */
  id: number
  /** 订单编号（对外展示的流水号，如含日期前缀的字符串） */
  order_no: string
  /** 订单状态（如 pending_payment / paid / shipped / finished / cancelled 等） */
  status: string
  /** 订单应付总金额（元） */
  total_amount: number
  /** 订单包含的商品条目列表 */
  items: OrderItem[]
  /** 订单收货地址快照 */
  address: OrderAddress
  /** 订单创建时间（ISO 字符串） */
  created_at: string
  /** 支付时间；未支付时为 null */
  paid_at: string | null
  /** 发货时间；未发货时为 null */
  shipped_at: string | null
  /** 完成（确认收货）时间；未完成为 null */
  finished_at: string | null
}

/**
 * 订单收货地址（OrderAddress）数据结构
 * 下单时从用户地址簿快照过来的完整收货信息。
 */
export interface OrderAddress {
  /** 收货人姓名 */
  receiver_name: string
  /** 收货人手机号 */
  receiver_phone: string
  /** 省份 */
  province: string
  /** 城市 */
  city: string
  /** 区/县 */
  district: string
  /** 详细地址（街道、门牌号等） */
  detail: string
}

// 创建订单
/**
 * 创建订单
 *
 * 作用：将购物车中选中的商品条目（按 SKU 与数量）连同收货地址提交到后端，
 *      后端校验库存与金额后生成新订单。
 * 参数：
 *  - data: {
 *      items: { sku_id: number; quantity: number }[]  订单包含的 SKU 及数量列表
 *      address_id: number                              选中的收货地址 id
 *      remark?: string                                 订单备注（可选）
 *    }
 * 返回值：Axios Promise，响应体 data 中携带新创建的订单信息（含订单 id）
 * 依赖接口：POST /orders
 */
export function createOrder(data: {
  items: { sku_id: number; quantity: number }[]
  address_id: number
  remark?: string
}) {
  // 将条目、地址与备注以 JSON 请求体 POST 到 /orders 创建订单
  return api.post('/orders', data)
}

// 订单列表
/**
 * 查询订单列表
 *
 * 作用：分页查询当前用户的订单，支持按订单状态过滤，
 *      供"我的订单"页面按状态分页展示。
 * 参数：
 *  - params?: {
 *      page?: number      页码（从 1 开始）
 *      page_size?: number 每页条数
 *      status?: string    按订单状态过滤（可选）
 *    }
 * 返回值：Axios Promise，响应体 data 中包含订单列表与分页信息
 * 依赖接口：GET /orders
 */
export function getOrders(params?: { page?: number; page_size?: number; status?: string }) {
  // 将分页与状态条件以 query 参数形式附加到 /orders 请求上
  return api.get('/orders', { params })
}

// 订单详情
/**
 * 查询订单详情
 *
 * 作用：按订单 id 获取订单的完整信息（含商品条目与收货地址），
 *      供订单详情页展示。
 * 参数：
 *  - id: number 订单 id
 * 返回值：Axios Promise，响应体 data 中携带订单详情对象
 * 依赖接口：GET /orders/{id}
 */
export function getOrderDetail(id: number) {
  // 将订单 id 拼入 URL 路径，请求 /orders/{id} 获取详情
  return api.get(`/orders/${id}`)
}

// 取消订单
/**
 * 取消订单
 *
 * 作用：在订单尚未支付或允许取消的时限内，将指定订单置为已取消。
 * 参数：
 *  - id: number 要取消的订单 id
 * 返回值：Axios Promise，成功时表示订单已取消
 * 依赖接口：PUT /orders/{id}/cancel
 */
export function cancelOrder(id: number) {
  // 通过 PUT /orders/{id}/cancel 触发订单取消流程
  return api.put(`/orders/${id}/cancel`)
}

// 确认收货
/**
 * 确认收货
 *
 * 作用：买家确认已收到货物，将订单状态推进为已完成（finished）。
 * 参数：
 *  - id: number 要确认收货的订单 id
 * 返回值：Axios Promise，成功时表示订单已完成
 * 依赖接口：PUT /orders/{id}/confirm
 */
export function confirmOrder(id: number) {
  // 通过 PUT /orders/{id}/confirm 触发确认收货流程
  return api.put(`/orders/${id}/confirm`)
}
