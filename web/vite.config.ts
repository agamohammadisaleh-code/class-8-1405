import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// پروکسی /api به سرور FastAPI تا مرورگر هرگز مستقیم به localhost دیگری وصل نشود
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: true,
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
    allowedHosts: true,
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
