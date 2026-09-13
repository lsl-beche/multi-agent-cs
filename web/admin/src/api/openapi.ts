/**
 * 开放平台 / ISV API Key 管理
 */
import api, { type ApiResponse } from './index'

export interface TenantItem {
  id: number
  name: string
  slug: string
  contact_email?: string | null
  status: string
  created_at?: string
  updated_at?: string
}

export interface ApiKeyItem {
  id: number
  name: string
  tenant_id?: number | null
  status: string
  scopes: Record<string, unknown>
  expires_at?: string | null
  last_used_at?: string | null
  created_at?: string
  api_key?: string
}

export const getOpenApiKeys = () =>
  api.get<ApiResponse<ApiKeyItem[]>>('/openapi/keys')

export const createOpenApiKey = (payload: {
  tenant_id?: number
  name: string
  scopes?: string[]
  expires_days?: number
}) => api.post<ApiResponse<ApiKeyItem>>('/openapi/keys', payload)

export const revokeOpenApiKey = (id: number) =>
  api.post<ApiResponse<unknown>>(`/openapi/keys/${id}/revoke`)

export const getTenants = () =>
  api.get<ApiResponse<TenantItem[]>>('/openapi/tenants')

export const createTenant = (payload: {
  name: string
  slug: string
  contact_email?: string
}) => api.post<ApiResponse<TenantItem>>('/openapi/tenants', payload)
