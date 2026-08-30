/**
 * Token 存储策略：
 * 默认使用 sessionStorage，避免 token 跨标签页长期暴露；
 * 通过 storage 选项可切换 localStorage。
 */
export interface TokenStorageOptions {
  storage?: 'session' | 'local'
}

export class TokenStorage {
  private readonly storage: Storage
  readonly accessKey: string
  readonly refreshKey: string

  constructor(accessKey: string, refreshKey: string, options: TokenStorageOptions = {}) {
    this.accessKey = accessKey
    this.refreshKey = refreshKey
    this.storage = options.storage === 'local' ? window.localStorage : window.sessionStorage
  }

  get accessToken(): string {
    return this.storage.getItem(this.accessKey) || ''
  }

  get refreshToken(): string {
    return this.storage.getItem(this.refreshKey) || ''
  }

  setTokens(accessToken: string, refreshToken = '') {
    this.storage.setItem(this.accessKey, accessToken)
    if (refreshToken) {
      this.storage.setItem(this.refreshKey, refreshToken)
    }
  }

  clear() {
    this.storage.removeItem(this.accessKey)
    this.storage.removeItem(this.refreshKey)
  }

  isAuthenticated() {
    return Boolean(this.accessToken)
  }
}

export const shopTokenStorage = new TokenStorage('shop_token', 'shop_refresh_token')
export const adminTokenStorage = new TokenStorage('token', 'refresh_token')

export function createTokenStorage(options: TokenStorageOptions = {}) {
  return new TokenStorage('shop_token', 'shop_refresh_token', options)
}

