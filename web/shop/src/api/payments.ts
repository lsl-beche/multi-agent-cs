/**
 * 支付 API 模块
 *
 * 文件作用：封装商城系统中与"支付"相关的后端接口调用，
 *      包括发起订单支付与查询支付状态。
 * 所属模块：前端 shop 商城项目的 API 请求层（src/api）。
 * 对外导出内容：
 *  - payOrder：发起订单支付
 *  - getPaymentStatus：查询订单支付状态
 *
 * 说明：本模块基于 src/api/index.ts 的 axios 实例发起请求，
 *      错误信息由响应拦截器统一提示。
 */
import api from './index'

/**
 * 发起订单支付
 *
 * 作用：将订单 id 与支付渠道提交到后端，后端生成对应的支付请求
 *      （如微信支付的支付参数/二维码链接），供前端拉起支付流程。
 * 参数：
 *  - orderId: number      待支付的订单 id
 *  - channel: string      支付渠道，默认为 'wechat'（微信支付）
 * 返回值：Axios Promise，响应体 data 中携带支付所需的参数（如 prepay 信息）
 * 依赖接口：POST /payments/pay
 */
export function payOrder(orderId: number, channel: string = 'wechat') {
  // 将订单 id 与支付渠道以 JSON 请求体 POST 到 /payments/pay 发起支付
  return api.post('/payments/pay', { order_id: orderId, channel })
}

/**
 * 查询订单支付状态
 *
 * 作用：查询指定订单的支付结果（如是否已支付成功），
 *      供支付页在支付完成后轮询或回跳时确认支付结果。
 * 参数：
 *  - orderId: number 订单 id
 * 返回值：Axios Promise，响应体 data 中携带支付状态信息
 * 依赖接口：GET /payments/{orderId}/status
 */
export function getPaymentStatus(orderId: number) {
  // 将订单 id 拼入 URL 路径，请求 /payments/{orderId}/status 查询支付状态
  return api.get(`/payments/${orderId}/status`)
}

/**
 * 确认支付（沙箱模拟回调）
 *
 * 作用：携带发起支付时返回的 payment_no / signature / timestamp，
 *      调用后端沙箱回调确认支付成功。生产环境由微信/支付宝回调替代。
 */
export function confirmPayment(paymentNo: string, signature: string, timestamp: number) {
  return api.post('/payments/confirm', {
    payment_no: paymentNo,
    signature,
    timestamp,
  })
}
