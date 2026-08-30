import { createApiClient, adminTokenStorage } from '@shared'

export const api = createApiClient({
  baseURL: '/api',
  tokenStorage: adminTokenStorage,
  refreshUrl: '/api/auth/refresh',
  unwrapResponse: true,
  onUnauthorized: () => {
    adminTokenStorage.clear()
    window.location.href = '/login'
  },
})

export default api
export type { ApiResponse, PaginatedData } from '@shared'
