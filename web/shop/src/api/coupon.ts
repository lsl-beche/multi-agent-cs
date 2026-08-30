/**
 * 优惠券 API 模块
 *
 * 文件作用：封装商城系统中与"优惠券"相关的后端接口调用，
 *      包括查询用户优惠券列表、校验优惠券在订单中是否可用。
 * 所属模块：前端 shop 商城项目的 API 请求层（src/api）。
 * 对外导出内容：
 *  - getUserCoupons：获取当前登录用户的优惠券列表
 *  - validateCoupon：校验指定用户优惠券在给定订单金额下是否可用
 *
 * 说明：本模块通过 src/api/index.ts 导出的 axios 实例发起请求，
 *      请求会自动携带登录 token，错误信息由响应拦截器统一处理。
 */
import request from './index'

/**
 * 获取当前用户的优惠券列表
 *
 * 作用：拉取登录用户拥有的全部优惠券（含面额、使用门槛、有效期、状态等），
 *      供"我的优惠券"页面列表展示使用。
 * 参数：无
 * 返回值：Axios Promise，响应体 data 中携带优惠券列表数据
 * 依赖接口：GET /user/coupons
 */
export function getUserCoupons() {
  // 调用后端 /user/coupons 接口获取当前用户的优惠券列表
  return request.get('/user/coupons')
}

/**
 * 校验优惠券在订单中是否可用
 *
 * 作用：在下单/结算流程中，将用户选中的优惠券与本次订单金额一同提交给后端，
 *      后端判断是否满足使用门槛并返回抵扣后的金额或校验失败原因。
 * 参数：
 *  - userCouponId: number 用户优惠券记录 id（即用户领取后的券实例 id，而非券模板 id）
 *  - orderAmount: number  本次订单的应付金额，用于判断是否达到优惠券使用门槛
 * 返回值：Axios Promise，响应体 data 中携带优惠券校验结果（如实际抵扣金额）
 * 依赖接口：POST /orders/validate-coupon
 */
export function validateCoupon(userCouponId: number, orderAmount: number) {
  // 将用户优惠券 id 与订单金额按后端约定的 snake_case 字段名提交校验
  return request.post('/orders/validate-coupon', { user_coupon_id: userCouponId, order_amount: orderAmount })
}
