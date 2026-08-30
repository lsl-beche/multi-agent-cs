/**
 * 用户（个人中心）API 模块
 *
 * 文件作用：封装商城系统中与"个人用户中心"相关的后端接口调用，
 *      包括收货地址的增删改查、个人资料更新以及修改密码。
 * 所属模块：前端 shop 商城项目的 API 请求层（src/api）。
 * 对外导出内容：
 *  - Address：收货地址数据结构定义
 *  - getAddresses：查询收货地址列表
 *  - createAddress：新增收货地址
 *  - updateAddress：更新收货地址
 *  - deleteAddress：删除收货地址
 *  - updateProfile：更新个人资料
 *  - changePassword：修改登录密码
 *
 * 说明：本模块基于 src/api/index.ts 的 axios 实例发起请求，
 *      错误信息由响应拦截器统一提示。
 */
import api from './index'

/**
 * 收货地址（Address）数据结构
 * 对应后端保存的一条完整收货地址记录。
 */
export interface Address {
  /** 地址记录唯一 id */
  id: number
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
  /** 是否为默认地址（下单时优先选中） */
  is_default: boolean
}

// 地址列表
/**
 * 查询收货地址列表
 *
 * 作用：获取当前用户保存的全部收货地址，
 *      供"收货地址管理"页与下单选择地址时使用。
 * 参数：无
 * 返回值：Axios Promise，响应体 data 中携带地址列表
 * 依赖接口：GET /user/addresses
 */
export function getAddresses() {
  // 调用后端 /user/addresses 接口获取当前用户的地址列表
  return api.get('/user/addresses')
}

// 新增地址
/**
 * 新增收货地址
 *
 * 作用：将新填写的收货地址保存到当前用户地址簿。
 * 参数：
 *  - data: Omit<Address, 'id'> 地址信息（不含 id，id 由后端生成），包含
 *      receiver_name、receiver_phone、province、city、district、detail、is_default 等字段
 * 返回值：Axios Promise，成功时返回新建的地址记录
 * 依赖接口：POST /user/addresses
 */
export function createAddress(data: Omit<Address, 'id'>) {
  // 将地址数据以 JSON 请求体 POST 到 /user/addresses 完成新增
  return api.post('/user/addresses', data)
}

// 更新地址
/**
 * 更新收货地址
 *
 * 作用：修改已保存的某条收货地址信息（编辑地址功能）。
 * 参数：
 *  - id: number 要更新的地址 id
 *  - data: Omit<Address, 'id'> 更新后的地址信息（不含 id）
 * 返回值：Axios Promise，成功时返回更新后的地址记录
 * 依赖接口：PUT /user/addresses/{id}
 */
export function updateAddress(id: number, data: Omit<Address, 'id'>) {
  // 将地址 id 拼入 URL，并通过 PUT /user/addresses/{id} 提交更新后的数据
  return api.put(`/user/addresses/${id}`, data)
}

// 删除地址
/**
 * 删除收货地址
 *
 * 作用：从当前用户地址簿中移除指定地址。
 * 参数：
 *  - id: number 要删除的地址 id
 * 返回值：Axios Promise，成功时表示地址已删除
 * 依赖接口：DELETE /user/addresses/{id}
 */
export function deleteAddress(id: number) {
  // 通过 DELETE /user/addresses/{id} 删除指定地址
  return api.delete(`/user/addresses/${id}`)
}

// 更新个人信息
/**
 * 更新个人信息
 *
 * 作用：更新当前登录用户的昵称、手机号、邮箱或头像等资料，
 *      供"个人中心"资料编辑页使用。
 * 参数：
 *  - data: { nickname?: string; phone?: string; email?: string; avatar?: string }
 *      均为可选字段，只提交需要修改的项即可
 * 返回值：Axios Promise，成功时返回更新后的用户资料
 * 依赖接口：PUT /user/profile
 */
export function updateProfile(data: { nickname?: string; phone?: string; email?: string; avatar?: string }) {
  // 将需要更新的资料字段以 JSON 请求体 PUT 到 /user/profile
  return api.put('/user/profile', data)
}

// 修改密码
/**
 * 修改登录密码
 *
 * 作用：校验旧密码后设置新密码，用于用户主动修改登录密码。
 * 参数：
 *  - data: { old_password: string; new_password: string }，其中：
 *      - old_password: string 原密码，用于身份校验
 *      - new_password: string 新密码
 * 返回值：Axios Promise，成功时表示密码已修改
 * 依赖接口：PUT /user/password
 */
export function changePassword(data: { old_password: string; new_password: string }) {
  // 将旧密码与新密码以 JSON 请求体 PUT 到 /user/password 完成修改
  return api.put('/user/password', data)
}
