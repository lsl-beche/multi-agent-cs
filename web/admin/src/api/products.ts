/**
 * 商品模块 API
 *
 * 文件作用：封装后台管理系统「商品管理」的接口请求（商品列表/详情、新增/编辑/删除、上下架、分类管理、图片上传）。
 * 所属模块：商品模块（products）。
 * 对外导出：getProducts（分页查询商品）、getProduct（商品详情）、createProduct（新增商品）、updateProduct（编辑商品）、
 *          deleteProduct（删除商品）、onlineProduct（上架）、offlineProduct（下架）、
 *          getCategories（查询分类树）、createCategory（新增分类）、uploadProductImage（上传商品图片），
 *          以及 ProductItem、SkuItem、ImageItem、CategoryItem 类型。
 * 说明：所有请求基于 ./index 的 axios 实例，实际路径带 /api 前缀。
 */

import api, { type ApiResponse, type PaginatedData } from './index'

/**
 * 商品条目（SPU 维度，含可选的 SKU 与图片列表）
 * - id: 商品 ID
 * - spu_code: SPU 编码（商品唯一业务编号）
 * - name: 商品名称
 * - subtitle: 商品副标题/卖点（可选）
 * - category_id: 所属分类 ID（可选）
 * - brand: 品牌名称（可选）
 * - main_image: 主图 URL（可选）
 * - status: 商品状态（如 online 在售、offline 下架、draft 草稿等）
 * - min_price: SKU 最低售价（用于列表价格展示）
 * - max_price: SKU 最高售价
 * - total_sales: 累计销量
 * - created_at: 创建时间
 * - skus: SKU 列表（可选，详情接口返回）
 * - images: 图片列表（可选，详情接口返回）
 */
export interface ProductItem {
  id: number; spu_code: string; name: string; subtitle?: string;
  category_id?: number; brand?: string; main_image?: string;
  status: string; min_price: number; max_price: number;
  total_sales: number; created_at: string;
  skus?: SkuItem[]; images?: ImageItem[];
}

/**
 * SKU 条目（商品的具体售卖规格）
 * - id: SKU ID
 * - sku_code: SKU 编码（库存/物流维度的业务编号）
 * - spec_info: 规格信息（如 { 颜色: 红色, 尺码: XL }，结构随商品不同）
 * - price: 当前售价
 * - original_price: 原价/划线价（可选，用于展示折扣）
 * - barcode: 条形码（可选）
 * - status: SKU 状态（如 online 在售、offline 停售）
 */
export interface SkuItem { id: number; sku_code: string; spec_info: Record<string, string>; price: number; original_price?: number; barcode?: string; status: string }

/**
 * 商品图片条目
 * - id: 图片 ID
 * - url: 图片地址
 * - sort_order: 排序值（越小越靠前）
 * - is_main: 是否为主图
 */
export interface ImageItem { id: number; url: string; sort_order: number; is_main: boolean }

/**
 * 商品分类节点
 * - id: 分类 ID
 * - name: 分类名称
 * - parent_id: 父分类 ID（可选，一级分类无父级）
 * - level: 分类层级（如 1 一级、2 二级）
 * - children: 子分类列表（可选，树形结构返回时存在）
 */
export interface CategoryItem { id: number; name: string; parent_id?: number; level: number; children?: CategoryItem[] }

/**
 * 分页查询商品列表
 * @param params 查询参数（如 page、page_size、name、status、category_id 等筛选条件）
 * @returns Promise<PaginatedData<ProductItem>> 分页的商品数据
 * @description 对应后端接口：GET /api/admin/products
 */
export const getProducts = (params: Record<string, unknown>) => api.get<PaginatedData<ProductItem>>('/admin/products', { params }) // 携带筛选参数请求商品列表

/**
 * 查询商品详情
 * @param id 商品 ID
 * @returns Promise<ApiResponse<ProductItem>> 商品完整信息（含 SKU 列表、图片列表）
 * @description 对应后端接口：GET /api/admin/products/{id}
 */
export const getProduct = (id: number) => api.get<ApiResponse<ProductItem>>(`/admin/products/${id}`) // 按 ID 拉取商品全量信息

/**
 * 新增商品
 * @param data 商品创建数据（SPU 信息 + SKU 列表 + 图片等）
 * @returns Promise<ApiResponse<unknown>> 创建结果，成功时返回新商品信息
 * @description 对应后端接口：POST /api/admin/products
 */
export const createProduct = (data: Record<string, unknown>) => api.post<ApiResponse<Record<string, unknown>>>('/admin/products', data) // 提交商品及 SKU 配置到后端

/**
 * 编辑商品
 * @param id 商品 ID
 * @param data 商品更新数据（仅传需要修改的字段）
 * @returns Promise<ApiResponse<unknown>> 更新结果，成功时返回更新后的商品信息
 * @description 对应后端接口：PUT /api/admin/products/{id}
 */
export const updateProduct = (id: number, data: Record<string, unknown>) => api.put<ApiResponse<Record<string, unknown>>>(`/admin/products/${id}`, data) // 按 ID 提交商品信息修改

/**
 * 删除商品
 * @param id 商品 ID
 * @returns Promise 删除成功时正常 resolve
 * @description 对应后端接口：DELETE /api/admin/products/{id}
 */
export const deleteProduct = (id: number) => api.delete(`/admin/products/${id}`) // 按 ID 删除商品（通常为软删除）

/**
 * 商品上架
 * @param id 商品 ID
 * @returns Promise 上架成功时正常 resolve
 * @description 对应后端接口：PUT /api/admin/products/{id}/online
 */
export const onlineProduct = (id: number) => api.put(`/admin/products/${id}/online`) // 将商品状态置为在售

/**
 * 商品下架
 * @param id 商品 ID
 * @returns Promise 下架成功时正常 resolve
 * @description 对应后端接口：PUT /api/admin/products/{id}/offline
 */
export const offlineProduct = (id: number) => api.put(`/admin/products/${id}/offline`) // 将商品状态置为停售

/**
 * 查询全部分类（树形结构）
 * @returns Promise<ApiResponse<CategoryItem[]>> 分类树数组
 * @description 对应后端接口：GET /api/admin/products/categories/all
 */
export const getCategories = () => api.get<ApiResponse<CategoryItem[]>>('/admin/products/categories/all') // 用于分类下拉/树形选择组件

/**
 * 新增商品分类
 * @param data 分类创建数据（名称、父级 ID、层级等）
 * @returns Promise<ApiResponse<unknown>> 创建结果，成功时返回新分类信息
 * @description 对应后端接口：POST /api/admin/products/categories
 */
export const createCategory = (data: Record<string, unknown>) => api.post<ApiResponse<Record<string, unknown>>>('/admin/products/categories', data) // 提交分类配置到后端

/**
 * 上传商品图片（multipart/form-data）
 * @param file 待上传的图片文件（File 对象）
 * @returns Promise 上传成功时返回图片 URL 等信息
 * @description 对应后端接口：POST /api/admin/products/upload-image
 */
export function uploadProductImage(file: File) {
  const formData = new FormData() // 构造表单数据，用于文件上传
  formData.append('file', file) // 将图片文件放入 form-data 的 file 字段
  return api.post<ApiResponse<{ url: string }>>('/admin/products/upload-image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' } // 指定文件上传的内容类型
  })
}
