import { ElMessage } from 'element-plus'

export type ToastType = 'success' | 'warning' | 'error' | 'info'

export function showToast(message: string, type: ToastType = 'success') {
  ElMessage({ message, type, duration: 2500 })
}

