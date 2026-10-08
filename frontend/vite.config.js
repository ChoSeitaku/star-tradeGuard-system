import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/',
  server: {
    port: 5176,
    // 开发模式下把 /api 代理到后端，生产由 FastAPI 直接托管 dist
    proxy: {
      '/api': { target: 'http://127.0.0.1:8005', changeOrigin: true }
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    chunkSizeWarningLimit: 2000
  }
})
