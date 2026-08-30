/**
 * 商品评价 API 模块
 *
 * 文件作用：封装商城系统中与"商品评价/评论"相关的后端接口调用，
 *      包括提交评价与分页查询某商品的全部评价。
 * 所属模块：前端 shop 商城项目的 API 请求层（src/api）。
 * 对外导出内容：
 *  - submitReview：提交商品评价
 *  - getProductReviews：分页查询商品评价列表
 *
 * 说明：本模块基于 src/api/index.ts 的 axios 实例发起请求，
 *      错误信息由响应拦截器统一提示。
 */
import request from './index'

/**
 * 提交商品评价
 *
 * 作用：对已完成的订单中的商品提交评分与文字评价，
 *      可支持匿名评价。
 * 参数：
 *  - data: {
 *      order_id: number      所属订单 id（确保已购后评价）
 *      product_id: number    被评价的商品 id
 *      rating: number        评分（如 1~5 星）
 *      content: string       评价文字内容
 *      is_anonymous?: boolean 是否匿名评价（可选，默认由后端决定）
 *    }
 * 返回值：Axios Promise，成功时表示评价已提交
 * 依赖接口：POST /reviews
 */
export function submitReview(data: { order_id: number; product_id: number; rating: number; content: string; is_anonymous?: boolean }) {
  // 将订单、商品、评分、内容与匿名标记以 JSON 请求体 POST 到 /reviews
  return request.post('/reviews', data)
}

/**
 * 分页查询商品评价列表
 *
 * 作用：按商品 id 分页获取该商品的全部评价，
 *      供商品详情页的评价列表展示（含评分与内容）。
 * 参数：
 *  - productId: number 商品 id
 *  - page: number      页码，默认 1
 *  - pageSize: number  每页条数，默认 10
 * 返回值：Axios Promise，响应体 data 中包含评价列表与分页信息
 * 依赖接口：GET /reviews/product/{productId}
 */
export function getProductReviews(productId: number, page: number = 1, pageSize: number = 10) {
  // 将商品 id 拼入 URL 路径，分页参数以 query 形式附加（page_size 为后端约定字段名）
  return request.get('/reviews/product/' + productId, { params: { page, page_size: pageSize } })
}
