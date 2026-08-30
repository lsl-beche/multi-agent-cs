import { createApiClient, shopTokenStorage } from '@shared'

export const api = createApiClient({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  tokenStorage: shopTokenStorage,
  refreshUrl: '/api/auth/refresh',
  onUnauthorized: () => {
    shopTokenStorage.clear()
    window.location.href = '/login'
  },
})

export default api
export type { ApiResponse, PaginatedData } from '@shared'
