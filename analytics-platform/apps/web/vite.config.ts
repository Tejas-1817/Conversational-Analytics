import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const apiProxy = {
  target: 'http://127.0.0.1:8000',
  changeOrigin: true,
  bypass: (req: any) => {
    if (req.headers && req.headers.accept && req.headers.accept.includes('text/html')) {
      return '/index.html';
    }
  }
};

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/auth': apiProxy,
      '/users': apiProxy,
      '/sources': apiProxy,
      '/jobs': apiProxy,
      '/metadata': apiProxy,
      '/semantic': apiProxy,
      '/schema': apiProxy,
      '/engine': apiProxy,
      '/dashboards': apiProxy,
      '/api': apiProxy
    }
  },
  test: {
    environment: 'jsdom',
    globals: true,
  }
} as any)
