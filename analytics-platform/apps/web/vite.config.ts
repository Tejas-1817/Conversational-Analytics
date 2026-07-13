import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/auth': 'http://127.0.0.1:8000',
      '/users': 'http://127.0.0.1:8000',
      '/sources': 'http://127.0.0.1:8000',
      '/jobs': 'http://127.0.0.1:8000',
      '/metadata': 'http://127.0.0.1:8000',
      '/semantic': 'http://127.0.0.1:8000',
      '/engine': 'http://127.0.0.1:8000',
      '/dashboards': 'http://127.0.0.1:8000'
    }
  },
  test: {
    environment: 'jsdom',
    globals: true,
  }
} as any)
