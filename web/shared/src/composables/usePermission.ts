import { computed, ref } from 'vue'

export function usePermission() {
  const permissions = ref<string[]>(readPermissions())

  function readPermissions(): string[] {
    try {
      return JSON.parse(window.localStorage.getItem('permissions') || '[]') as string[]
    } catch {
      return []
    }
  }

  const hasPermission = (required: string | string[]) => {
    const list = Array.isArray(required) ? required : [required]
    return list.some((permission) => permissions.value.includes(permission))
  }

  const isAdmin = computed(() => permissions.value.includes('system:read') || permissions.value.includes('*'))

  return { permissions, hasPermission, isAdmin }
}

