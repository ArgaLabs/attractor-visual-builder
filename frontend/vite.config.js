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
      '/pipelines': 'http://localhost:8000',
      '/validate': 'http://localhost:8000',
      '/generate-dot': 'http://localhost:8000',
    },
  },
})
