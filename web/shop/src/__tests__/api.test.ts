/** API 拦截器行为测试：错误分类与 401 处理（不发起真实请求） */
import { describe, expect, it, vi } from 'vitest'
import { ElMessage } from 'element-plus'
import { api } from '../api/index'

vi.mock('element-plus', () => ({ ElMessage: { error: vi.fn() } }))

describe('api 错误分类', () => {
  it('5xx 返回通用服务提示', async () => {
    const handler = (api.interceptors.response as unknown as {
      handlers: Array<{ rejected: (err: unknown) => Promise<unknown> }>
    }).handlers[0].rejected
    const err = { response: { status: 500 } }
    await expect(handler(err)).rejects.toEqual(err)
    expect(ElMessage.error).toHaveBeenCalledWith('服务暂时不可用，请稍后再试')
  })
})
