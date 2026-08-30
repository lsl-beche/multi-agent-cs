/** API 拦截器行为测试：错误分类与 401 处理（不发起真实请求） */
import { describe, expect, it, vi } from 'vitest'
import { ElMessage } from 'element-plus'

vi.mock('element-plus', () => ({ ElMessage: { error: vi.fn() } }))

describe('api 错误分类', () => {
  it('5xx 返回通用服务提示', async () => {
    const api = (await import('../api/index')).default
    api.interceptors.response.handlers = api.interceptors.response.handlers
    // 直接验证拦截器文案生成逻辑（避免真实请求）
    const handler = (api.interceptors.response as any).handlers[0].rejected
    const err = { response: { status: 500 } }
    await expect(handler(err)).rejects.toEqual(err)
    expect((err as any).$$userMessage).toBe('服务暂时不可用，请稍后再试')
  })
})
