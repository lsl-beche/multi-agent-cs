import axios, {
  AxiosError,
  AxiosInstance,
  AxiosRequestConfig,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios'
import { ElMessage } from 'element-plus'

import type { TokenStorage } from '../auth/token'

export interface ApiClientOptions {
  baseURL: string
  tokenStorage: TokenStorage
  refreshUrl?: string
  unwrapResponse?: boolean
  onUnauthorized?: () => void
}

export interface ApiClientUnwrap {
  get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>
  post<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  put<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  delete<T = unknown>(url: string): Promise<T>
}

export function createApiClient(options: ApiClientOptions & { unwrapResponse: true }): ApiClientUnwrap
export function createApiClient(options: ApiClientOptions & { unwrapResponse?: false }): AxiosInstance
export function createApiClient(options: ApiClientOptions): AxiosInstance | ApiClientUnwrap {
  const client = axios.create({
    baseURL: options.baseURL,
    timeout: 15000,
  })

  let refreshing = false
  let pending: Array<(token: string) => void> = []

  client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    const token = options.tokenStorage.accessToken
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  })

  client.interceptors.response.use(
    (response: AxiosResponse) => (options.unwrapResponse ? response.data : response),
    async (error: AxiosError) => {
      const original = error.config as AxiosRequestConfig & { _retry?: boolean }
      const status = error.response?.status

      if (status === 401 && !original._retry && options.refreshUrl) {
        if (refreshing) {
          return new Promise((resolve) => {
            pending.push((token) => {
              original.headers = original.headers || {}
              ;(original.headers as Record<string, string>).Authorization = `Bearer ${token}`
              resolve(client(original))
            })
          })
        }
        original._retry = true
        refreshing = true
        try {
          const refreshToken = options.tokenStorage.refreshToken
          if (!refreshToken) throw new Error('missing refresh token')
          const res = await axios.post(options.refreshUrl, { refresh_token: refreshToken })
          const accessToken = res.data?.data?.access_token || res.data?.access_token
          if (!accessToken) throw new Error('invalid refresh response')
          options.tokenStorage.setTokens(accessToken, refreshToken)
          pending.forEach((callback) => callback(accessToken))
          pending = []
          original.headers = original.headers || {}
          ;(original.headers as Record<string, string>).Authorization = `Bearer ${accessToken}`
          return client(original)
        } catch {
          options.tokenStorage.clear()
          options.onUnauthorized?.()
          return Promise.reject(error)
        } finally {
          refreshing = false
        }
      }

      const responseData = (error.response?.data || {}) as { detail?: string; message?: string }
      const serverMessage = responseData.detail || responseData.message || ''
      const requestStatus = error.response?.status
      const message =
        serverMessage ||
        (requestStatus && requestStatus >= 500 ? '服务暂时不可用，请稍后再试' : error.message || '请求失败')
      ElMessage.error(message)
      return Promise.reject(error)
    },
  )

  if (!options.unwrapResponse) {
    return client
  }

  const unwrap = <T>(promise: Promise<AxiosResponse<T>>): Promise<T> => promise.then((response) => response.data)
  return {
    get: <T = unknown>(url: string, config?: AxiosRequestConfig) => unwrap<T>(client.get(url, config)),
    post: <T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
      unwrap<T>(client.post(url, data, config)),
    put: <T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
      unwrap<T>(client.put(url, data, config)),
    delete: <T = unknown>(url: string) => unwrap<T>(client.delete(url)),
  }
}
