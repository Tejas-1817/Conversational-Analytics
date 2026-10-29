import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const apiProxy = {
  target: 'http://127.0.0.1:8000',
  changeOrigin: true,
  configure: (proxy: any) => {
    proxy.on('error', (_err: any, _req: any, res: any) => {
      if (res && !res.headersSent && typeof res.writeHead === 'function') {
        res.writeHead(503, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            error: 'Backend service is starting up or temporarily unavailable. Please retry in a moment.',
            code: 'BACKEND_STARTING',
          })
        );
      }
    });
  },
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
      '/domains': apiProxy,
      '/api': apiProxy,
      '/code-repos': apiProxy,
      '/tenants': apiProxy,
      '/eval': apiProxy,
      '/api-keys': apiProxy
    }
  },
  test: {
    environment: 'jsdom',
    globals: true,
  }
} as any)
