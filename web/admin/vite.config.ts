import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  build: {
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules/element-plus')) return 'vendor-element-plus'
          if (id.includes('node_modules/vue') || id.includes('node_modules/@vue')) return 'vendor-vue'
          if (id.includes('node_modules/echarts')) return 'vendor-charts'
          if (id.includes('node_modules/axios')) return 'vendor-http'
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@shared': resolve(__dirname, '../shared/src'),
      'vue': resolve(__dirname, 'node_modules/vue'),
      'axios': resolve(__dirname, 'node_modules/axios'),
      'element-plus': resolve(__dirname, 'node_modules/element-plus'),
      '@element-plus/icons-vue': resolve(__dirname, 'node_modules/@element-plus/icons-vue'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
