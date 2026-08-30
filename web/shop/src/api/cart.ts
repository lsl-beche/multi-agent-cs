/**
 * 购物车 API 模块
 *
 * 文件作用：封装商城系统中与"购物车"相关的后端接口调用，
 *      包括购物车查询、加入购物车、修改数量、删除条目、
 *      单项选中/取消选中以及全选/取消全选等操作。
 * 所属模块：前端 shop 商城项目的 API 请求层（src/api）。
 * 对外导出内容：
 *  - CartItem：购物车条目的数据结构定义（TypeScript 接口）
 *  - getCart：获取当前用户的购物车列表
 *  - addToCart：将指定 SKU 加入购物车
 *  - updateCartItem：更新购物车条目的购买数量
 *  - removeCartItem：删除购物车中的指定条目
 *  - selectAll：全选 / 取消全选购物车
 *  - selectItem：选中 / 取消选中购物车中的某一条目
 *
 * 说明：本模块基于 src/api/index.ts 的 axios 实例发起请求，
 *      请求会自动携带登录 token，错误信息由响应拦截器统一提示。
 */
import api from './index'

/**
 * 购物车条目（CartItem）数据结构
 * 对应后端返回的购物车中单条商品记录的完整字段。
 */
export interface CartItem {
  /** 购物车条目唯一 id（后端自增主键） */
  id: number
  /** 商品 id，可用于跳转到商品详情页 */
  product_id: number
  /** 商品名称，用于购物车列表展示 */
  product_name: string
  /** 该条目对应的 SKU（库存量单位）id */
  sku_id: number
  /** SKU 名称，例如"红色 / L码"等规格组合 */
  sku_name: string
  /** 当前 SKU 的单价（元） */
  price: number
  /** 购物车中该条目的数量 */
  quantity: number
  /** 商品主图 URL，用于列表缩略图展示 */
  image: string
  /** 当前 SKU 的库存量，用于前端校验可购买数量上限 */
  stock: number
  /** 是否被勾选，勾选状态决定是否参与结算合计 */
  selected: boolean
}

// 获取购物车
/**
 * 获取购物车列表
 *
 * 作用：拉取当前登录用户的购物车全部条目（含商品与 SKU 信息），
 *      供购物车页面渲染及结算页读取选中商品使用。
 * 参数：无
 * 返回值：Axios Promise，响应体 data.data 中携带 items 购物车条目数组
 * 依赖接口：GET /cart
 */
export function getCart() {
  // 调用后端 /cart 接口获取当前用户的购物车条目列表
  return api.get('/cart')
}

// 添加到购物车
/**
 * 添加商品到购物车
 *
 * 作用：将指定 SKU 以指定数量加入当前用户的购物车；
 *      若该 SKU 已存在，后端通常按累加数量处理。
 * 参数：
 *  - data: { sku_id: number; quantity: number }，其中：
 *      - sku_id: number 要加入购物车的 SKU id
 *      - quantity: number 加入的数量（须大于 0 且不超过库存）
 * 返回值：Axios Promise，成功时返回新增/更新后的购物车信息
 * 依赖接口：POST /cart
 */
export function addToCart(data: { sku_id: number; quantity: number }) {
  // 将 sku_id 与 quantity 以 JSON 请求体 POST 到 /cart 完成加入购物车
  return api.post('/cart', data)
}

// 更新购物车项数量
/**
 * 更新购物车条目的数量
 *
 * 作用：修改购物车中某一条目的购买数量（加减操作后的结果同步到后端）。
 * 参数：
 *  - id: number 购物车条目 id
 *  - quantity: number 更新后的目标数量（须大于 0 且不超过库存）
 * 返回值：Axios Promise，成功时返回更新结果
 * 依赖接口：PUT /cart/{id}
 */
export function updateCartItem(id: number, quantity: number) {
  // 将新数量封装进请求体，通过 PUT /cart/{id} 更新该条目数量
  return api.put(`/cart/${id}`, { quantity })
}

// 删除购物车项
/**
 * 删除购物车条目
 *
 * 作用：从购物车中移除指定的某一条目（单条删除操作）。
 * 参数：
 *  - id: number 要删除的购物车条目 id
 * 返回值：Axios Promise，成功时表示已删除
 * 依赖接口：DELETE /cart/{id}
 */
export function removeCartItem(id: number) {
  // 通过 DELETE /cart/{id} 删除指定购物车条目
  return api.delete(`/cart/${id}`)
}

// 全选/取消全选
/**
 * 全选 / 取消全选购物车
 *
 * 作用：一键勾选或取消勾选购物车中的全部条目，
 *      常用于"全部选中后统一结算"或"清空勾选"场景。
 * 参数：
 *  - selected: boolean true 表示全选，false 表示取消全选
 * 返回值：Axios Promise，成功时返回更新结果
 * 依赖接口：PUT /cart/select-all
 */
export function selectAll(selected: boolean) {
  // 将全选状态以请求体提交到 /cart/select-all 接口
  return api.put('/cart/select-all', { selected })
}

// 选中某条
/**
 * 选中 / 取消选中购物车中的某一条目
 *
 * 作用：单独勾选或取消勾选购物车中的某一条目，
 *      只有被选中的条目才会计入合计金额并参与结算。
 * 参数：
 *  - id: number 购物车条目 id
 *  - selected: boolean true 表示选中，false 表示取消选中
 * 返回值：Axios Promise，成功时返回更新结果
 * 依赖接口：PUT /cart/{id}/select
 */
export function selectItem(id: number, selected: boolean) {
  // 将选中状态以请求体提交到 /cart/{id}/select 接口
  return api.put(`/cart/${id}/select`, { selected })
}
