export interface ApiResponse<T = unknown> {
  code: number
  data: T
  message?: string
}

export interface PaginatedData<T> extends ApiResponse<T[]> {
  total: number
  page: number
  page_size: number
}

export interface UserProfile {
  id: number
  username: string
  email?: string
  phone?: string
  role?: string
  permissions?: string[]
}

export interface AddressItem {
  id: number
  receiver: string
  receiver_name?: string
  phone: string
  receiver_phone?: string
  province: string
  city: string
  district: string
  detail: string
  is_default: boolean
}

export interface CartItem {
  id: number
  product_id: number
  product_name: string
  sku_id: number
  sku_name: string
  price: number
  quantity: number
  image: string
  selected: boolean
}

export interface ProductSummary {
  id: number
  name: string
  description: string
  category_id?: number | null
  category_name?: string
  images: string[]
  price: number
  status: string
  created_at: string
  total_sales: number
}

export interface ProductDetail extends ProductSummary {
  skus: Array<{
    id: number
    product_id: number
    name: string
    price: number
    stock: number
    attrs: Record<string, string>
  }>
}

export interface OrderItem {
  id: number
  product_id: number
  product_name: string
  sku_name: string
  price: number
  quantity: number
  image: string
}

export interface OrderSummary {
  id: number
  order_no: string
  status: string
  pay_status: string
  total_amount: number
  items?: OrderItem[]
  address?: AddressItem | null
  created_at: string
  paid_at?: string | null
  shipped_at?: string | null
  finished_at?: string | null
}
