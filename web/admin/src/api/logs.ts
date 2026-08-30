/**
 * 操作日志模块 API
 *
 * 文件作用：封装后台管理系统「操作日志」的接口请求（分页查询管理员/用户的操作日志）。
 * 所属模块：日志模块（logs）。
 * 对外导出：getOperationLogs（分页查询操作日志）、LogItem（日志条目类型）。
 * 说明：所有请求基于 ./index 的 axios 实例，实际路径带 /api 前缀。
 */

import api, { type PaginatedData } from './index'

/**
 * 操作日志条目（记录后台某个账号在某个模块执行的操作）
 */
export interface LogItem {
  id: number // 日志 ID
  username: string // 操作者用户名（哪个账号执行的操作）
  module: string // 所属业务模块（如 orders、products、users 等）
  action: string // 操作动作（如 create、update、delete、ban 等）
  target_id?: string // 操作对象 ID（如被修改的订单号/商品 ID，可选）
  detail?: Record<string, unknown> // 操作详情（如修改前后的字段对比 JSON，可选）
  ip_address?: string // 操作者 IP 地址（可选，用于安全审计）
  created_at: string // 操作发生时间
}

/**
 * 分页查询操作日志
 * @param params 查询参数（如 page、page_size、username、module、action、时间范围等筛选条件）
 * @returns Promise<PaginatedData<LogItem>> 分页的操作日志数据
 * @description 对应后端接口：GET /api/admin/logs
 */
export const getOperationLogs = (params: Record<string, unknown>) => api.get<PaginatedData<LogItem>>('/admin/logs', { params }) // 供审计与安全排查使用
