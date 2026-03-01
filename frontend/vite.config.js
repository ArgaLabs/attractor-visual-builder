import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../attractor/server/static',
    emptyOutDir: true,
  },
  server: {
    port: 3000,
    proxy: {
      '/pipelines': { target: 'http://localhost:8000', changeOrigin: true },
      '/validate': { target: 'http://localhost:8000', changeOrigin: true },
      '/generate-dot': { target: 'http://localhost:8000', changeOrigin: true },
      '/upload': { target: 'http://localhost:8000', changeOrigin: true },
      '/schedules': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
