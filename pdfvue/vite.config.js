import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
// 必须导入resolve
import { resolve } from 'path'

export default defineConfig({
  // base: '/static/',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  build: {
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('pdfjs-dist')) return 'pdfjs'
          if (id.includes('@vueuse/core')) return 'vueuse'
        }
      }
    }
  }
})