import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import { AppErrorBoundary, AsyncState, TokenStorage } from '@shared'

describe('shared frontend package', () => {
  it('TokenStorage persists and clears tokens', () => {
    const storage = new TokenStorage('a', 'b', { storage: 'session' })
    storage.setTokens('access', 'refresh')
    expect(storage.accessToken).toBe('access')
    expect(storage.refreshToken).toBe('refresh')
    storage.clear()
    expect(storage.isAuthenticated()).toBe(false)
  })

  it('AsyncState renders empty state', () => {
    const wrapper = mount(AsyncState, { props: { empty: true } })
    expect(wrapper.text()).toContain('暂无数据')
  })

  it('AppErrorBoundary captures errors', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const wrapper = mount({
      components: { AppErrorBoundary },
      template: '<AppErrorBoundary><span>content</span></AppErrorBoundary>',
    })
    expect(wrapper.text()).toContain('content')
    spy.mockRestore()
  })
})
