import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@shared': fileURLToPath(new URL('../shared/src', import.meta.url)),
      'vue': fileURLToPath(new URL('./node_modules/vue', import.meta.url)),
      'axios': fileURLToPath(new URL('./node_modules/axios', import.meta.url)),
      'element-plus': fileURLToPath(new URL('./node_modules/element-plus', import.meta.url)),
      '@element-plus/icons-vue': fileURLToPath(new URL('./node_modules/@element-plus/icons-vue', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
