import type { Directive, DirectiveBinding } from 'vue'

export const PermissionDirective: Directive<HTMLElement, string | string[]> = {
  mounted(el, binding: DirectiveBinding<string | string[]>) {
    const required = Array.isArray(binding.value) ? binding.value : [binding.value]
    const raw = window.localStorage.getItem('permissions') || '[]'
    let permissions: string[] = []
    try {
      permissions = JSON.parse(raw)
    } catch {
      permissions = []
    }
    if (!required.some((permission) => permissions.includes(permission))) {
      el.style.display = 'none'
    }
  },
}

